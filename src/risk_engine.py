"""
HedgeFund AI — Risk Sınıflandırma Motoru
Her varlık için çok faktörlü risk puanı ve seviyesi hesaplar.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AssetRiskProfile:
    symbol: str
    name: str
    asset_type: str

    # Risk components (each 0-100)
    volatility_risk: float        # based on annualized vol
    liquidity_risk: float         # market cap tier based
    drawdown_risk: float          # based on max drawdown
    correlation_risk: float       # correlation with market
    macro_sensitivity: float      # sensitivity to macro factors
    news_sensitivity: float       # based on asset type
    regulatory_risk: float        # crypto > stocks > etf
    momentum_instability: float   # momentum reversal risk

    # Composite
    total_risk_score: float       # 0-100
    risk_level: str               # çok düşük/düşük/orta/orta-yüksek/yüksek/çok yüksek/spekülatif
    risk_emoji: str               # 🟢🟡🟠🔴💀 etc

    # Narrative
    risk_summary: str             # 1-2 sentence summary
    key_risk_factors: list        # top 3 risk factors
    risk_mitigants: list          # 2-3 things that reduce risk

    # Thresholds
    max_position_pct: float       # recommended max portfolio %
    stop_loss_suggestion_pct: float  # suggested stop loss %


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _volatility_risk(vol: float) -> float:
    """Map annualized volatility % → risk score 0-100."""
    if vol < 10:
        return 5.0
    if vol < 20:
        return 20.0
    if vol < 35:
        return 40.0
    if vol < 50:
        return 60.0
    if vol < 80:
        return 78.0
    return 95.0


def _drawdown_risk(max_drawdown: float) -> float:
    """Map max drawdown % (negative value) → risk score 0-100."""
    # Normalise: accept both -30 and 30 as "30% drawdown"
    dd = abs(max_drawdown)
    if dd < 5:
        return 5.0
    if dd < 15:
        return 20.0
    if dd < 30:
        return 40.0
    if dd < 50:
        return 65.0
    return 90.0


def _liquidity_risk(market_cap_tier: str) -> float:
    """Map market cap tier string → risk score 0-100."""
    mapping = {
        "mega": 5.0,
        "large": 15.0,
        "mid": 40.0,
        "small": 70.0,
    }
    return mapping.get(market_cap_tier.lower() if market_cap_tier else "", 60.0)


def _regulatory_risk(asset_type: str) -> float:
    mapping = {
        "crypto": 70.0,
        "stock": 15.0,
        "bist": 25.0,
        "etf": 10.0,
        "fund": 8.0,
    }
    return mapping.get(asset_type.lower() if asset_type else "", 30.0)


def _news_sensitivity(asset_type: str) -> float:
    mapping = {
        "crypto": 80.0,
        "bist": 60.0,
        "stock": 40.0,
        "etf": 25.0,
    }
    return mapping.get(asset_type.lower() if asset_type else "", 40.0)


def _macro_sensitivity(asset_type: str) -> float:
    mapping = {
        "crypto": 75.0,
        "bist": 70.0,
        "stock": 50.0,
        "etf": 45.0,
    }
    return mapping.get(asset_type.lower() if asset_type else "", 50.0)


def _momentum_instability(sharpe: float) -> float:
    if sharpe > 1.5:
        return 15.0
    if sharpe >= 1.0:
        return 30.0
    if sharpe >= 0.5:
        return 50.0
    if sharpe >= 0.0:
        return 65.0
    return 80.0


def _risk_level_and_emoji(score: float) -> tuple:
    """Return (risk_level_str, emoji) for a given total_risk_score."""
    if score < 15:
        return "çok düşük", "🟢"
    if score < 30:
        return "düşük", "🟡"
    if score < 45:
        return "orta", "🟠"
    if score < 58:
        return "orta-yüksek", "🔶"
    if score < 70:
        return "yüksek", "🔴"
    if score < 82:
        return "çok yüksek", "⛔"
    return "spekülatif", "💀"


_MAX_POSITION_MAP = {
    "çok düşük": 30.0,
    "düşük": 25.0,
    "orta": 20.0,
    "orta-yüksek": 15.0,
    "yüksek": 10.0,
    "çok yüksek": 7.0,
    "spekülatif": 5.0,
}

_STOP_LOSS_MAP = {
    "çok düşük": 5.0,
    "düşük": 7.0,
    "orta": 10.0,
    "orta-yüksek": 12.0,
    "yüksek": 15.0,
    "çok yüksek": 20.0,
    "spekülatif": 25.0,
}


def _build_narrative(
    symbol: str,
    name: str,
    asset_type: str,
    risk_level: str,
    vol_risk: float,
    dd_risk: float,
    liq_risk: float,
    reg_risk: float,
    news_risk: float,
    macro_risk: float,
    mom_risk: float,
    sharpe: float,
    return_1y: float,
    sector: str,
) -> tuple:
    """Return (risk_summary, key_risk_factors, risk_mitigants)."""

    # --- Key risk factors (pick the 3 highest component scores) ---
    components = {
        "Yüksek volatilite": vol_risk,
        "Büyük maksimum düşüş": dd_risk,
        "Düşük likidite": liq_risk,
        "Düzenleyici belirsizlik": reg_risk,
        "Haber hassasiyeti": news_risk,
        "Makro duyarlılık": macro_risk,
        "Momentum istikrarsızlığı": mom_risk,
    }
    sorted_factors = sorted(components.items(), key=lambda x: x[1], reverse=True)
    key_risk_factors = [f[0] for f in sorted_factors[:3]]

    # --- Risk mitigants ---
    mitigants = []
    if sharpe > 1.0:
        mitigants.append(f"Güçlü risk/getiri oranı (Sharpe: {sharpe:.2f})")
    elif sharpe > 0.5:
        mitigants.append(f"Makul risk/getiri oranı (Sharpe: {sharpe:.2f})")

    if return_1y > 10:
        mitigants.append(f"Son 1 yılda pozitif getiri (%{return_1y:.1f})")

    if asset_type.lower() in ("etf", "fund"):
        mitigants.append("Geniş varlık çeşitlendirmesi (ETF/Fon yapısı)")

    if asset_type.lower() == "bist":
        mitigants.append("TL bazlı; döviz geliri olan şirketlerde kur avantajı")

    if liq_risk <= 15:
        mitigants.append("Yüksek piyasa likiditesi (mega/large cap)")

    if sector and sector.lower() in ("utilities", "healthcare", "consumer_staples", "savunma"):
        mitigants.append(f"Savunmacı sektör: {sector}")

    # Guarantee at least 2 mitigants
    if len(mitigants) < 2:
        mitigants.append("Düzenli piyasa takibi ile risk kontrol altında tutulabilir")
    if len(mitigants) < 2:
        mitigants.append("Stop-loss kullanımı ile maksimum kayıp sınırlandırılabilir")

    risk_mitigants = mitigants[:3]

    # --- Summary ---
    level_tr = risk_level.capitalize()
    summary = (
        f"{name} ({symbol}), {level_tr} risk profiline sahip bir {asset_type.upper()} varlığıdır. "
        f"En önemli risk faktörleri: {', '.join(key_risk_factors[:2]).lower()}. "
        f"Portföyde dikkatli pozisyon yönetimi önerilir."
    )

    return summary, key_risk_factors, risk_mitigants


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_risk_profile(
    symbol: str,
    name: str,
    asset_type: str,
    metrics: dict,
) -> AssetRiskProfile:
    """
    Calculate a full risk profile for a single asset.

    Parameters
    ----------
    symbol     : Ticker symbol (e.g. "AAPL", "BTCUSDT", "THYAO")
    name       : Human-readable name
    asset_type : One of: "crypto", "stock", "bist", "etf", "fund"
    metrics    : Dict with keys:
                   volatility      — annualised vol in %
                   max_drawdown    — max drawdown in % (negative or positive)
                   sharpe          — Sharpe ratio
                   return_1y       — 1-year return in %
                   market_cap_tier — "mega" | "large" | "mid" | "small"
                   sector          — sector string (optional)
    """
    logger.debug("Calculating risk profile for %s (%s)", symbol, asset_type)

    vol        = float(metrics.get("volatility", 30.0))
    dd         = float(metrics.get("max_drawdown", -20.0))
    sharpe     = float(metrics.get("sharpe", 0.5))
    return_1y  = float(metrics.get("return_1y", 0.0))
    cap_tier   = str(metrics.get("market_cap_tier", "unknown"))
    sector     = str(metrics.get("sector", ""))

    # --- Component scores ---
    vol_risk   = _volatility_risk(vol)
    dd_risk    = _drawdown_risk(dd)
    liq_risk   = _liquidity_risk(cap_tier)
    reg_risk   = _regulatory_risk(asset_type)
    news_risk  = _news_sensitivity(asset_type)
    macro_risk = _macro_sensitivity(asset_type)
    mom_risk   = _momentum_instability(sharpe)

    # Correlation risk: placeholder — set to a neutral value derived from asset type
    corr_risk_map = {"crypto": 35.0, "stock": 55.0, "bist": 50.0, "etf": 40.0, "fund": 35.0}
    corr_risk = corr_risk_map.get(asset_type.lower(), 50.0)

    # --- Weighted total ---
    total = (
        vol_risk   * 0.25
        + dd_risk  * 0.20
        + liq_risk * 0.10
        + reg_risk * 0.15
        + news_risk * 0.10
        + macro_risk * 0.10
        + mom_risk  * 0.10
    )
    # Clamp to [0, 100]
    total = max(0.0, min(100.0, total))

    risk_level, risk_emoji = _risk_level_and_emoji(total)
    max_pos = _MAX_POSITION_MAP[risk_level]
    stop_loss = _STOP_LOSS_MAP[risk_level]

    summary, key_factors, mitigants = _build_narrative(
        symbol, name, asset_type, risk_level,
        vol_risk, dd_risk, liq_risk, reg_risk,
        news_risk, macro_risk, mom_risk,
        sharpe, return_1y, sector,
    )

    profile = AssetRiskProfile(
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        volatility_risk=round(vol_risk, 2),
        liquidity_risk=round(liq_risk, 2),
        drawdown_risk=round(dd_risk, 2),
        correlation_risk=round(corr_risk, 2),
        macro_sensitivity=round(macro_risk, 2),
        news_sensitivity=round(news_risk, 2),
        regulatory_risk=round(reg_risk, 2),
        momentum_instability=round(mom_risk, 2),
        total_risk_score=round(total, 2),
        risk_level=risk_level,
        risk_emoji=risk_emoji,
        risk_summary=summary,
        key_risk_factors=key_factors,
        risk_mitigants=mitigants,
        max_position_pct=max_pos,
        stop_loss_suggestion_pct=stop_loss,
    )

    logger.info(
        "Risk profile for %s: score=%.1f level=%s emoji=%s",
        symbol, total, risk_level, risk_emoji,
    )
    return profile


def compare_risk_levels(profiles: list) -> pd.DataFrame:
    """
    Build a comparison DataFrame for a list of AssetRiskProfile objects.

    Columns: Symbol, Name, Asset Type, Risk Level, Risk Score, Key Factor, Max Position %
    """
    rows = []
    for p in profiles:
        rows.append({
            "Symbol":          p.symbol,
            "Name":            p.name,
            "Asset Type":      p.asset_type,
            "Risk Level":      f"{p.risk_emoji} {p.risk_level}",
            "Risk Score":      round(p.total_risk_score, 1),
            "Key Factor":      p.key_risk_factors[0] if p.key_risk_factors else "-",
            "Max Position %":  p.max_position_pct,
        })

    df = pd.DataFrame(rows, columns=[
        "Symbol", "Name", "Asset Type", "Risk Level",
        "Risk Score", "Key Factor", "Max Position %",
    ])
    df.sort_values("Risk Score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def get_portfolio_risk_summary(profiles: list, weights: list) -> dict:
    """
    Compute weighted portfolio-level risk metrics.

    Parameters
    ----------
    profiles : list of AssetRiskProfile
    weights  : list of floats (must sum to ~1.0 or will be normalised)

    Returns
    -------
    dict with keys:
        weighted_risk_score, portfolio_risk_level, portfolio_risk_emoji,
        highest_risk_asset, lowest_risk_asset,
        avg_max_position_pct, avg_stop_loss_pct,
        risk_distribution (dict level -> count),
        diversification_note
    """
    if not profiles:
        return {}

    if len(profiles) != len(weights):
        raise ValueError("profiles and weights must have the same length")

    total_w = sum(weights)
    if total_w == 0:
        raise ValueError("weights must not all be zero")
    norm_weights = [w / total_w for w in weights]

    weighted_score = sum(p.total_risk_score * w for p, w in zip(profiles, norm_weights))
    risk_level, risk_emoji = _risk_level_and_emoji(weighted_score)

    sorted_by_risk = sorted(profiles, key=lambda p: p.total_risk_score)
    lowest  = sorted_by_risk[0]
    highest = sorted_by_risk[-1]

    avg_max_pos = sum(p.max_position_pct * w for p, w in zip(profiles, norm_weights))
    avg_stop    = sum(p.stop_loss_suggestion_pct * w for p, w in zip(profiles, norm_weights))

    distribution: dict = {}
    for p in profiles:
        distribution[p.risk_level] = distribution.get(p.risk_level, 0) + 1

    n = len(profiles)
    if n <= 3:
        div_note = "Portföy çeşitlendirme açısından zayıf. En az 5-8 varlık önerilir."
    elif n <= 7:
        div_note = "Makul çeşitlendirme. Sektör veya bölge bazında daha geniş dağılım düşünülebilir."
    else:
        div_note = "İyi çeşitlendirme. Korelasyonları kontrol ederek birlikte hareket eden varlıkları izleyin."

    return {
        "weighted_risk_score":   round(weighted_score, 2),
        "portfolio_risk_level":  risk_level,
        "portfolio_risk_emoji":  risk_emoji,
        "highest_risk_asset":    {"symbol": highest.symbol, "score": highest.total_risk_score, "level": highest.risk_level},
        "lowest_risk_asset":     {"symbol": lowest.symbol,  "score": lowest.total_risk_score,  "level": lowest.risk_level},
        "avg_max_position_pct":  round(avg_max_pos, 1),
        "avg_stop_loss_pct":     round(avg_stop, 1),
        "risk_distribution":     distribution,
        "diversification_note":  div_note,
        "asset_count":           n,
    }


def format_risk_badge(risk_level: str) -> str:
    """Return a colored text badge string for the given risk level."""
    badge_map = {
        "çok düşük":   "🟢 Çok Düşük Risk",
        "düşük":       "🟡 Düşük Risk",
        "orta":        "🟠 Orta Risk",
        "orta-yüksek": "🔶 Orta-Yüksek Risk",
        "yüksek":      "🔴 Yüksek Risk",
        "çok yüksek":  "⛔ Çok Yüksek Risk",
        "spekülatif":  "💀 Spekülatif",
    }
    return badge_map.get(risk_level.lower(), f"❓ {risk_level.capitalize()}")


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    sample_assets = [
        ("AAPL",    "Apple Inc.",        "stock",  {"volatility": 18, "max_drawdown": -28, "sharpe": 1.2, "return_1y": 22, "market_cap_tier": "mega",  "sector": "technology"}),
        ("BTCUSDT", "Bitcoin",           "crypto", {"volatility": 75, "max_drawdown": -72, "sharpe": 0.4, "return_1y": 55, "market_cap_tier": "mega",  "sector": "crypto"}),
        ("THYAO",   "Türk Hava Yolları", "bist",   {"volatility": 40, "max_drawdown": -45, "sharpe": 0.7, "return_1y": 80, "market_cap_tier": "large", "sector": "transportation"}),
        ("SPY",     "S&P 500 ETF",       "etf",    {"volatility": 14, "max_drawdown": -24, "sharpe": 1.3, "return_1y": 18, "market_cap_tier": "mega",  "sector": "diversified"}),
    ]

    profiles = []
    for sym, name, atype, met in sample_assets:
        p = calculate_risk_profile(sym, name, atype, met)
        profiles.append(p)
        print(f"\n{p.risk_emoji} {p.symbol} — {p.risk_level.upper()} (score: {p.total_risk_score})")
        print(f"   Summary    : {p.risk_summary}")
        print(f"   Key Risks  : {p.key_risk_factors}")
        print(f"   Mitigants  : {p.risk_mitigants}")
        print(f"   Max Pos    : {p.max_position_pct}%  |  Stop-Loss: {p.stop_loss_suggestion_pct}%")
        print(f"   Badge      : {format_risk_badge(p.risk_level)}")

    print("\n--- Comparison Table ---")
    df = compare_risk_levels(profiles)
    print(df.to_string(index=False))

    print("\n--- Portfolio Summary (equal weight) ---")
    import json
    w = [0.25, 0.25, 0.25, 0.25]
    summary = get_portfolio_risk_summary(profiles, w)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
