"""
HedgeFund AI — Opportunity Engine
Tüm varlık sınıflarını tarar, fırsatları puanlar ve sıralar.

Scoring pipeline:
  tech_score      (max ±40)  — RSI, MACD, EMA, BB, breakout, volume
  momentum_score  (max ±30)  — 1w/1m/3m returns + acceleration
  risk_score      (max 0–20) — drawdown + volatility deductions
  quality_score   (max ±10)  — Sharpe ratio bonus

  composite = clamp(50 + tech + momentum + risk + quality, 0, 100)
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd
import yaml

# ── Path resolution (frozen EXE + dev mode) ──────────────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent      # dist/HedgeFundAI/
else:
    _ROOT = Path(__file__).parent.parent     # repo root

_CACHE_DIR   = _ROOT / "data" / "raw"
_CONFIG_PATH = _ROOT / "config" / "asset_universe.yaml"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Optional TechnicalAnalyzer import ────────────────────────────────────────
try:
    from src.analyzer import TechnicalAnalyzer, TechnicalResult  # type: ignore
    _ANALYZER = TechnicalAnalyzer()
    _TECH_CFG: dict = {
        "rsi_period": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "ema_periods": [20, 50, 200],
        "bb_period": 20,
        "bb_std": 2,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "volume_spike_multiplier": 2.5,
    }
    logger.info("TechnicalAnalyzer loaded successfully.")
except ImportError:
    _ANALYZER = None  # type: ignore
    _TECH_CFG = {}
    logger.warning("TechnicalAnalyzer not available — tech scores will be 0.")

# ── Cache TTL ─────────────────────────────────────────────────────────────────
_CACHE_TTL_HOURS = 4


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OpportunityResult:
    # ── Identity ──────────────────────────────────────────────────────────────
    symbol: str = ""
    name: str = ""
    asset_type: str = ""          # "crypto" | "stock" | "bist" | "etf"
    sector: str = ""
    category: str = ""

    # ── Price ─────────────────────────────────────────────────────────────────
    current_price: float = 0.0
    currency: str = "USD"
    price_change_display: str = ""   # e.g. "+2.3%"

    # ── Returns ───────────────────────────────────────────────────────────────
    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_1y: Optional[float] = None

    # ── Risk metrics ──────────────────────────────────────────────────────────
    volatility: Optional[float] = None   # annualised %, e.g. 25.4
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None  # negative %, e.g. -18.5

    # ── Technical signals ─────────────────────────────────────────────────────
    rsi: Optional[float] = None
    trend: str = "UNKNOWN"
    macd_signal: str = "neutral"   # "bullish" | "bearish" | "neutral"
    bb_position: Optional[float] = None
    volume_signal: str = "normal"  # "high" | "normal" | "low"
    breakout: bool = False

    # ── Scores ────────────────────────────────────────────────────────────────
    tech_score: float = 0.0        # 0–40 (capped after clamp)
    momentum_score: float = 0.0    # 0–30
    risk_score: float = 0.0        # 0–20
    composite_score: float = 50.0  # 0–100

    # ── Labels & decision ─────────────────────────────────────────────────────
    opportunity_label: str = ""
    opportunity_type: str = "izleme"
    decision: str = "İZLE"
    decision_confidence: float = 50.0

    # ── Narrative ─────────────────────────────────────────────────────────────
    why_buy: list = field(default_factory=list)
    why_not_buy: list = field(default_factory=list)
    catalysts: list = field(default_factory=list)
    risks: list = field(default_factory=list)

    # ── Trade levels ──────────────────────────────────────────────────────────
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    target_3: Optional[float] = None

    # ── Profile ───────────────────────────────────────────────────────────────
    time_horizon: str = "orta"     # "kısa" | "orta" | "uzun"
    suitable_for: list = field(default_factory=list)
    risk_level: str = "orta"
    risk_score_num: float = 50.0   # 0–100

    # ── Scenario & education ──────────────────────────────────────────────────
    invalidation: str = ""
    alternative_scenario: str = ""
    education_note: str = ""

    # ── Meta ──────────────────────────────────────────────────────────────────
    last_updated: str = ""

    # ── Institutional conviction & timing ─────────────────────────────────────
    conviction_score: float = 50.0        # composite × timing-adjusted, 0-100
    timing_score: float = 50.0            # "is NOW the right time?", 0-100
    timing_quality: str = "orta"          # "iyi" | "orta" | "kötü" | "çok kötü"
    timing_warning: str = ""              # "Doğru varlık, yanlış zaman" note or ""
    allocation_confidence: float = 50.0   # how confident the system is in this allocation

    # ── Catalyst map (structured) ─────────────────────────────────────────────
    catalyst_map: list = field(default_factory=list)
    # Each item: {"catalyst": str, "probability": "yüksek"|"orta"|"düşük", "impact": "yüksek"|"orta"|"düşük", "timeframe": str}

    # ── Scenario tree ─────────────────────────────────────────────────────────
    scenario_bull: dict = field(default_factory=dict)
    # {"trigger": str, "price_target": float, "return_pct": float, "probability_pct": int, "notes": str}
    scenario_base: dict = field(default_factory=dict)
    scenario_bear: dict = field(default_factory=dict)

    # ── Multi-dimensional analysis (6 axes, each 0-100) ───────────────────────
    dim_opportunity_quality: float = 50.0   # Fırsat kalitesi
    dim_timing_quality: float = 50.0        # Zamanlama kalitesi
    dim_risk_reward: float = 50.0           # Risk/ödül oranı
    dim_portfolio_fit: float = 50.0         # Portföy uyumu
    dim_profile_fit: float = 50.0           # Kullanıcı profiline uygunluk
    dim_alternative_cost: float = 50.0      # Alternatif maliyet skoru (yüksek = düşük fırsat maliyeti)
    alternative_cost_note: str = ""         # "Bu para X'te %Y getirebilir" tipi not

    # ── Invalidation events (structured) ─────────────────────────────────────
    invalidation_events: list = field(default_factory=list)
    # Each: {"event": str, "threshold": str, "action": str}


# ══════════════════════════════════════════════════════════════════════════════
# ASSET UNIVERSE LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_asset_universe() -> dict:
    """
    Load asset_universe.yaml.
    Returns dict with keys: 'crypto', 'us_stocks', 'bist', 'priority_etfs'.
    """
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        universe = {
            "crypto":        raw.get("crypto", []),
            "us_stocks":     raw.get("us_stocks", []),
            "bist":          raw.get("bist", []),
            "priority_etfs": raw.get("priority_etfs", []),
        }
        total = sum(len(v) for v in universe.values())
        logger.info("Asset universe loaded: %d assets total.", total)
        return universe
    except FileNotFoundError:
        logger.error("asset_universe.yaml not found at %s", _CONFIG_PATH)
        return {"crypto": [], "us_stocks": [], "bist": [], "priority_etfs": []}
    except Exception as exc:
        logger.error("Failed to load asset universe: %s", exc)
        return {"crypto": [], "us_stocks": [], "bist": [], "priority_etfs": []}


# ══════════════════════════════════════════════════════════════════════════════
# CACHE-BACKED DATA FETCH
# ══════════════════════════════════════════════════════════════════════════════

def _cache_file(symbol: str) -> Path:
    """Return cache file path for a symbol."""
    safe = symbol.replace("/", "_").replace(".", "_").replace("-", "_")
    return _CACHE_DIR / f"opp_cache_{safe}.json"


def _fetch_with_cache(symbol: str, force: bool = False) -> Optional[pd.DataFrame]:
    """
    Fetch 1y of daily OHLCV from yfinance with a 4-hour JSON cache.
    Returns a DataFrame with lowercase columns or None on failure.
    """
    cache_path = _cache_file(symbol)

    # ── Try reading from cache ────────────────────────────────────────────────
    if not force and cache_path.exists():
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < _CACHE_TTL_HOURS:
            try:
                with open(cache_path, encoding="utf-8") as fh:
                    cached = json.load(fh)
                df = pd.DataFrame(cached)
                df.index = pd.to_datetime(df.index)
                logger.debug("Cache hit for %s (%.1fh old).", symbol, age_hours)
                return df
            except Exception as exc:
                logger.warning("Cache read failed for %s: %s", symbol, exc)

    # ── Fetch from yfinance ───────────────────────────────────────────────────
    try:
        import yfinance as yf  # imported locally so module loads without yf

        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", auto_adjust=True)

        if df is None or df.empty:
            logger.warning("yfinance returned empty data for %s.", symbol)
            return None

        # Normalise column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Drop timezone from index for consistent JSON serialisation
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # ── Persist to cache ──────────────────────────────────────────────────
        try:
            cache_payload = df.to_dict(orient="index")
            # Convert Timestamp keys to strings for JSON
            cache_payload = {str(k): v for k, v in cache_payload.items()}
            with open(cache_path, "w", encoding="utf-8") as fh:
                json.dump(cache_payload, fh)
        except Exception as exc:
            logger.warning("Cache write failed for %s: %s", symbol, exc)

        logger.debug("Fetched %d rows from yfinance for %s.", len(df), symbol)
        return df

    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", symbol, exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# RETURN METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _calculate_returns(close: pd.Series) -> dict:
    """
    Compute return over standard look-back windows, plus volatility,
    Sharpe ratio, and maximum drawdown.

    Returns a dict with keys:
      return_1d, return_1w, return_1m, return_3m, return_6m, return_1y,
      volatility, sharpe, max_drawdown
    All return values are percentages (float, may be None if insufficient data).
    """
    result: dict = {
        "return_1d":   None,
        "return_1w":   None,
        "return_1m":   None,
        "return_3m":   None,
        "return_6m":   None,
        "return_1y":   None,
        "volatility":  None,
        "sharpe":      None,
        "max_drawdown": None,
    }

    if close is None or len(close) < 2:
        return result

    close = close.dropna()
    n = len(close)
    last = float(close.iloc[-1])

    def _pct(lookback_bars: int) -> Optional[float]:
        if n > lookback_bars:
            ref = float(close.iloc[-(lookback_bars + 1)])
            if ref != 0:
                return round((last / ref - 1) * 100, 2)
        return None

    result["return_1d"] = _pct(1)
    result["return_1w"] = _pct(5)
    result["return_1m"] = _pct(21)
    result["return_3m"] = _pct(63)
    result["return_6m"] = _pct(126)
    result["return_1y"] = _pct(252)

    # Annualised volatility (daily returns, std * sqrt(252))
    if n >= 20:
        daily_rets = close.pct_change().dropna()
        vol = float(daily_rets.std()) * (252 ** 0.5) * 100
        result["volatility"] = round(vol, 2)

        # Sharpe (risk-free ≈ 5% / 252 per day)
        rf_daily = 0.05 / 252
        excess   = daily_rets - rf_daily
        if float(daily_rets.std()) > 0:
            sharpe = float(excess.mean()) / float(daily_rets.std()) * (252 ** 0.5)
            result["sharpe"] = round(sharpe, 3)

    # Maximum drawdown
    if n >= 10:
        roll_max  = close.cummax()
        drawdowns = (close - roll_max) / roll_max * 100
        result["max_drawdown"] = round(float(drawdowns.min()), 2)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SCORING
# ══════════════════════════════════════════════════════════════════════════════

def _score_opportunity(
    metrics: dict,
    tech_result,  # TechnicalResult | None
) -> tuple:
    """
    Score a single opportunity.

    Returns:
        (tech_score, momentum_score, risk_score, quality_score, composite_score)

    Component ranges:
        tech_score      roughly -30 … +40
        momentum_score  roughly -24 … +30
        risk_score        0 … 20  (starts at 20, deducted for risk)
        quality_score   roughly  -3 … +10
        composite       clamp(50 + sum, 0, 100)
    """

    # ── 1. Technical score ────────────────────────────────────────────────────
    tech_score = 0.0

    if tech_result is not None:
        rsi             = tech_result.rsi
        macd_hist       = tech_result.macd_histogram
        macd_val        = tech_result.macd
        macd_sig        = tech_result.macd_signal
        price           = tech_result.price or 0.0
        ema20           = tech_result.ema20
        ema50           = tech_result.ema50
        ema200          = tech_result.ema200
        bb_pct          = tech_result.bb_pct
        breakout        = tech_result.breakout
        volume_ratio    = tech_result.volume_ratio

        # RSI component
        if rsi is not None:
            if rsi < 25:
                tech_score += 12
            elif rsi < 35:
                tech_score += 8
            elif rsi < 45:
                tech_score += 4
            elif rsi < 55:
                tech_score += 0
            elif rsi < 65:
                tech_score -= 2
            elif rsi < 75:
                tech_score -= 6
            else:
                tech_score -= 12

        # MACD component — histogram direction
        if macd_hist is not None and macd_val is not None and macd_sig is not None:
            if macd_hist > 0 and macd_val > macd_sig:
                tech_score += 8
            elif macd_hist < 0 and macd_val < macd_sig:
                tech_score -= 8
            # else neutral: 0

        # EMA stack
        if price and ema200:
            tech_score += 6 if price > ema200 else -6
        if price and ema50:
            tech_score += 4 if price > ema50 else -4
        if price and ema20:
            tech_score += 3 if price > ema20 else -3

        # Bollinger Band position
        if bb_pct is not None:
            if bb_pct < 0.2:
                tech_score += 5   # oversold within bands
            elif bb_pct > 0.8:
                tech_score -= 5   # overbought within bands

        # Breakout
        if breakout:
            tech_score += 5

        # Volume confirmation
        if volume_ratio is not None and volume_ratio > 1.5:
            tech_score += 3

    # ── 2. Momentum score ─────────────────────────────────────────────────────
    momentum_score = 0.0

    ret_1w = metrics.get("return_1w")
    ret_1m = metrics.get("return_1m")
    ret_3m = metrics.get("return_3m")

    if ret_1w is not None:
        if ret_1w > 10:
            momentum_score += 8
        elif ret_1w > 5:
            momentum_score += 5

    if ret_1m is not None:
        if ret_1m > 20:
            momentum_score += 12
        elif ret_1m > 10:
            momentum_score += 8
        elif ret_1m < -20:
            momentum_score -= 12
        elif ret_1m < -10:
            momentum_score -= 8

    if ret_3m is not None:
        if ret_3m > 40:
            momentum_score += 12
        elif ret_3m > 20:
            momentum_score += 8
        elif ret_3m < -15:
            momentum_score -= 8

    # Momentum acceleration: is recent 1m pace faster than implied 3m pace?
    if ret_1m is not None and ret_3m is not None:
        implied_monthly_3m = ret_3m / 3.0
        if ret_1m > implied_monthly_3m + 2:
            momentum_score += 4   # accelerating
        elif ret_1m < implied_monthly_3m - 2:
            momentum_score -= 4   # decelerating

    # ── 3. Risk score (starts at 20, deducted) ────────────────────────────────
    risk_score = 20.0

    max_dd  = metrics.get("max_drawdown")   # negative value, e.g. -25.0
    vol     = metrics.get("volatility")     # annualised %, e.g. 35.0

    if max_dd is not None:
        if max_dd > -10:
            pass                        # 0 deduction
        elif max_dd > -25:
            risk_score -= 3
        elif max_dd > -40:
            risk_score -= 6
        else:
            risk_score -= 10

    if vol is not None:
        if vol < 15:
            pass                        # 0 deduction
        elif vol < 30:
            risk_score -= 2
        elif vol < 50:
            risk_score -= 5
        else:
            risk_score -= 8

    risk_score = max(0.0, risk_score)

    # ── 4. Quality / Sharpe score ─────────────────────────────────────────────
    quality_score = 0.0
    sharpe = metrics.get("sharpe")
    if sharpe is not None:
        if sharpe > 2:
            quality_score += 10
        elif sharpe > 1:
            quality_score += 7
        elif sharpe > 0.5:
            quality_score += 4
        elif sharpe > 0:
            quality_score += 2
        else:
            quality_score -= 3

    # ── 5. Composite ─────────────────────────────────────────────────────────
    raw = 50.0 + tech_score + momentum_score + risk_score + quality_score
    composite = float(np.clip(raw, 0.0, 100.0))

    return (
        round(tech_score, 2),
        round(momentum_score, 2),
        round(risk_score, 2),
        round(quality_score, 2),
        round(composite, 2),
    )


# ══════════════════════════════════════════════════════════════════════════════
# INSTITUTIONAL TIMING & CONVICTION
# ══════════════════════════════════════════════════════════════════════════════

def _calculate_timing_score(
    metrics: dict,
    tech_result,
    rsi: Optional[float],
    vol: Optional[float],
) -> tuple:
    """
    Assess whether NOW is the right time to enter a position.

    Returns:
        (timing_score 0-100, timing_quality str, timing_warning str)
    """
    score = 50.0

    rsi_val = rsi or 0.0
    vol_val = vol or 0.0
    ret_1w  = metrics.get("return_1w") or 0.0
    ret_1m  = metrics.get("return_1m") or 0.0

    # RSI-based timing
    if rsi is not None:
        if rsi_val < 30:
            score += 20   # oversold = good timing
        elif rsi_val > 70:
            score -= 20   # overbought = bad timing
        elif rsi_val <= 45:
            score += 10
        elif rsi_val >= 55:
            score -= 10

    # EMA position (pullback entry vs extended)
    if tech_result is not None:
        price  = tech_result.price or 0.0
        ema20  = tech_result.ema20
        ema50  = tech_result.ema50
        ema200 = tech_result.ema200

        if price and ema20 and ema50:
            if price < ema20 and price < ema50:
                score += 15   # pullback entry opportunity
        if price and ema20 and ema50 and ema200:
            if price > ema20 and price > ema50 and price > ema200:
                score -= 10   # already extended above all EMAs

    # Recent return adjustments
    if ret_1w > 15:
        score -= 15   # chasing after a big move
    elif ret_1w < -10:
        score += 10   # dip opportunity

    if ret_1m > 30:
        score -= 20   # very extended short-term
    elif ret_1m < -20:
        score += 15

    # Bollinger Band position
    if tech_result is not None:
        bb_pct = tech_result.bb_pct
        if bb_pct is not None:
            if bb_pct < 0.2:
                score += 10   # near lower band = good entry
            elif bb_pct > 0.8:
                score -= 15   # near upper band = risky entry

    # High volatility reduces timing confidence
    if vol_val > 60:
        score -= 10

    # Clamp to [0, 100]
    score = float(np.clip(score, 0.0, 100.0))

    # Timing quality label
    if score >= 70:
        timing_quality = "iyi"
    elif score >= 55:
        timing_quality = "orta"
    elif score >= 40:
        timing_quality = "zayıf"
    else:
        timing_quality = "kötü"

    # Timing warning — placeholder composite; will be set properly in caller
    # We use score itself to generate the warning text here
    timing_warning = ""
    # Warning will be enriched in _generate_labels after composite is known

    return (round(score, 2), timing_quality, timing_warning)


def _calculate_conviction_score(
    composite: float,
    timing: float,
    quality_score: float,
) -> tuple:
    """
    Blend composite and timing scores into a single institutional conviction score.

    Args:
        composite:     Composite score 0-100
        timing:        Timing score 0-100
        quality_score: Risk score component -3 to +10

    Returns:
        (conviction_score 0-100, allocation_confidence 0-100)
    """
    conviction_raw = composite * 0.6 + timing * 0.4
    quality_bonus  = quality_score * 0.5   # quality_score is -3 to +10
    conviction     = float(np.clip(conviction_raw + quality_bonus, 0.0, 100.0))

    # Allocation confidence tiers
    timing_deviation = timing - 50.0  # positive = above mid, negative = below
    noise = timing_deviation * 0.1    # ±5 max contribution

    if conviction >= 70 and timing >= 60:
        base_conf = 75.0 + (conviction - 70) * 0.5   # scales 75–82.5 for cv 70-85
        base_conf = min(base_conf + noise, 90.0)
    elif conviction >= 55:
        base_conf = 50.0 + (conviction - 55) * 1.0 + noise
    else:
        base_conf = 20.0 + (conviction / 55.0) * 25.0 + noise

    allocation_confidence = float(np.clip(base_conf, 0.0, 100.0))

    return (round(conviction, 2), round(allocation_confidence, 2))


# ══════════════════════════════════════════════════════════════════════════════
# CATALYST MAP
# ══════════════════════════════════════════════════════════════════════════════

def _build_catalyst_map(result: OpportunityResult) -> list:
    """
    Build a structured list of 3-5 catalysts for the opportunity.

    Each catalyst dict:
        {"catalyst": str, "probability": "yüksek"|"orta"|"düşük",
         "impact": "yüksek"|"orta"|"düşük", "timeframe": str}
    """
    catalysts: list = []

    at = result.asset_type

    # Asset-type specific macro catalysts
    if at == "crypto":
        catalysts.append({
            "catalyst": "BTC spot ETF ek fon girişleri",
            "probability": "yüksek",
            "impact": "yüksek",
            "timeframe": "1-3 ay",
        })
        catalysts.append({
            "catalyst": "Zincir üstü metrik iyileşmesi ve kullanıcı büyümesi",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-6 ay",
        })
        catalysts.append({
            "catalyst": "Kurumsal benimseme ve hazine tahsisi artışı",
            "probability": "orta",
            "impact": "yüksek",
            "timeframe": "3-12 ay",
        })
    elif at in ("stock", "us_stocks"):
        catalysts.append({
            "catalyst": "Kazanç sezonu sürprizi",
            "probability": "orta",
            "impact": "yüksek",
            "timeframe": "1-4 hafta",
        })
        catalysts.append({
            "catalyst": "Fed faiz indirim döngüsü ve likidite genişlemesi",
            "probability": "orta",
            "impact": "yüksek",
            "timeframe": "3-6 ay",
        })
        catalysts.append({
            "catalyst": "Sektör rotasyonu ve kurumsal para akışları",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-3 ay",
        })
    elif at == "bist":
        catalysts.append({
            "catalyst": "TCMB faiz indirim döngüsü",
            "probability": "yüksek",
            "impact": "yüksek",
            "timeframe": "3-6 ay",
        })
        catalysts.append({
            "catalyst": "Yabancı yatırımcı geri dönüş süreci",
            "probability": "orta",
            "impact": "yüksek",
            "timeframe": "3-9 ay",
        })
        catalysts.append({
            "catalyst": "Enflasyon normalleşmesi ve reel getiri artışı",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "6-12 ay",
        })
    elif at == "etf":
        catalysts.append({
            "catalyst": "S&P 500 yeni ATH denemesi",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-3 ay",
        })
        catalysts.append({
            "catalyst": "Makro iyileşme ve risk iştahı artışı",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-6 ay",
        })
        catalysts.append({
            "catalyst": "Güçlü temettü ve geri alım programları",
            "probability": "yüksek",
            "impact": "orta",
            "timeframe": "3-12 ay",
        })
    else:
        catalysts.append({
            "catalyst": "Genel piyasa momentumu ve risk iştahı iyileşmesi",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-3 ay",
        })

    # Technical catalysts
    if result.breakout:
        catalysts.append({
            "catalyst": "Teknik direnç kırılımı teyidi",
            "probability": "yüksek",
            "impact": "orta",
            "timeframe": "1-2 hafta",
        })

    if result.rsi is not None and result.rsi < 35:
        catalysts.append({
            "catalyst": "RSI aşırı satım toparlanması",
            "probability": "yüksek",
            "impact": "orta",
            "timeframe": "3-10 gün",
        })

    if result.volume_signal == "high":
        catalysts.append({
            "catalyst": "Yüksek hacim — kurumsal akümülasyon işareti",
            "probability": "orta",
            "impact": "orta",
            "timeframe": "1-4 hafta",
        })

    # Return at most 5
    return catalysts[:5]


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO TREE
# ══════════════════════════════════════════════════════════════════════════════

def _build_scenario_tree(result: OpportunityResult) -> tuple:
    """
    Build bull / base / bear scenario dicts.

    Returns:
        (scenario_bull dict, scenario_base dict, scenario_bear dict)
    """
    price = result.current_price or 1.0
    vol   = result.volatility or 30.0
    cs    = result.composite_score

    # ── Bull scenario ─────────────────────────────────────────────────────────
    bull_prob = int(np.clip(cs * 0.6, 15, 55))
    bull_target = price * (1 + (vol / 100) * 1.5)
    bull_return = (bull_target / price - 1) * 100

    if result.asset_type == "crypto":
        bull_trigger = "BTC liderliğinde güçlü boğa rallisi ve ETF girişleri"
    elif result.asset_type in ("stock", "us_stocks"):
        bull_trigger = "Beklentilerin üzerinde kazanç + Fed pivot sürprizi"
    elif result.asset_type == "bist":
        bull_trigger = "Hızlı faiz indirim döngüsü + yabancı sermaye girişi"
    elif result.asset_type == "etf":
        bull_trigger = "Risk iştahı patlaması, güçlü makro veri akışı"
    else:
        bull_trigger = "Tüm katalizörlerin eş zamanlı gerçekleşmesi"

    if result.breakout:
        bull_trigger += " + breakout kırılımı onaylandı"

    scenario_bull = {
        "trigger": bull_trigger,
        "price_target": round(bull_target, 6),
        "return_pct": round(bull_return, 2),
        "probability_pct": bull_prob,
        "notes": (
            "Katalizörler gerçekleşirse kademeli kar realizasyonu yapılabilir. "
            f"Hedef: {bull_target:.4g} seviyesi."
        ),
    }

    # ── Base scenario ─────────────────────────────────────────────────────────
    base_prob   = int(np.clip(40 + (cs - 50) * 0.3, 30, 50))
    base_target = price * (1 + (vol / 100) * 0.4)
    base_return = (base_target / price - 1) * 100

    scenario_base = {
        "trigger": "Mevcut trend devam eder, beklentileri karşılar",
        "price_target": round(base_target, 6),
        "return_pct": round(base_return, 2),
        "probability_pct": base_prob,
        "notes": "Zaman ufku içinde kademeli değer artışı bekleniyor.",
    }

    # ── Bear scenario ─────────────────────────────────────────────────────────
    bear_prob   = max(100 - bull_prob - base_prob, 5)
    bear_target = price * (1 - (vol / 100) * 0.8)
    bear_return = (bear_target / price - 1) * 100

    if result.asset_type == "crypto":
        bear_trigger = "Regülasyon şoku veya BTC sert düşüşü"
    elif result.asset_type in ("stock", "us_stocks"):
        bear_trigger = "Kazanç hayal kırıklığı + makro resesyon korkusu"
    elif result.asset_type == "bist":
        bear_trigger = "TCMB politika tersine dönüşü veya jeopolitik risk artışı"
    elif result.asset_type == "etf":
        bear_trigger = "Risk-off ortamı, küresel satış dalgası"
    else:
        bear_trigger = "Makro şok ve genel piyasa satış baskısı"

    stop_note = f"Stop-loss seviyesi: {result.stop_loss:.4g}" if result.stop_loss else "Stop-loss: pozisyon büyüklüğünü sınırlayın"

    scenario_bear = {
        "trigger": bear_trigger,
        "price_target": round(bear_target, 6),
        "return_pct": round(bear_return, 2),
        "probability_pct": bear_prob,
        "notes": stop_note + ". Zararı azaltmak için hızlı aksiyon alın.",
    }

    return (scenario_bull, scenario_base, scenario_bear)


# ══════════════════════════════════════════════════════════════════════════════
# INVALIDATION EVENTS
# ══════════════════════════════════════════════════════════════════════════════

def _build_invalidation_events(result: OpportunityResult) -> list:
    """
    Build 2-4 structured invalidation events.

    Each event dict:
        {"event": str, "threshold": str, "action": str}
    """
    events: list = []

    # Primary technical invalidation
    if result.stop_loss:
        events.append({
            "event": "Haftalık kapanış EMA50 altında",
            "threshold": f"${result.stop_loss:.4g}",
            "action": "Pozisyonu kapat",
        })
    else:
        events.append({
            "event": "Trend yapısı kırılır, düşük dip oluşur",
            "threshold": "Önceki dip seviyesi",
            "action": "Pozisyonu gözden geçir ve azalt",
        })

    # Asset-type specific invalidation
    if result.asset_type == "crypto":
        events.append({
            "event": "BTC haftalık kapanışı kritik destek altında",
            "threshold": "BTC %20 düşüş",
            "action": "Kripto ağırlığını azalt",
        })
    elif result.asset_type in ("stock", "us_stocks"):
        events.append({
            "event": "Kazanç açıklaması beklentinin altında",
            "threshold": "EPS miss >%10",
            "action": "Pozisyon yeniden değerlendir",
        })
    elif result.asset_type == "bist":
        events.append({
            "event": "TCMB beklenmedik faiz artışı",
            "threshold": "Politika faizi +200 baz puan",
            "action": "BIST pozisyonlarını azalt",
        })
    elif result.asset_type == "etf":
        events.append({
            "event": "S&P 500 200-günlük EMA altına düşer",
            "threshold": "SPX -10% düzeltme",
            "action": "ETF ağırlığını azalt, nakit artır",
        })

    # Technical invalidation
    if result.trend == "UPTREND":
        events.append({
            "event": "EMA 20 × EMA 50 ölüm kesişimi (death cross)",
            "threshold": "EMA20 < EMA50 haftalık kapanış",
            "action": "Trendin tersine döndüğünü kabul et, çık",
        })

    # Universal macro invalidation — always added last
    events.append({
        "event": "Fed sürpriz faiz artışı",
        "threshold": "Endeks -5% tepkisi",
        "action": "Risk azalt, nakit artır",
    })

    return events[:4]


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-DIMENSIONAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _calculate_multi_dimensional(result: OpportunityResult) -> dict:
    """
    Compute 6 institutional analysis dimensions, each 0-100.

    Returns dict with keys:
        opp_quality, timing_quality, risk_reward, portfolio_fit,
        profile_fit, alt_cost, alt_cost_note
    """
    cs    = result.composite_score
    sharpe = result.sharpe or 0.0
    price  = result.current_price or 1.0
    stop   = result.stop_loss
    tgt1   = result.target_1

    # 1. Opportunity quality
    breakout_bonus = 5.0 if result.breakout else 0.0
    opp_quality = float(np.clip(cs * 0.7 + sharpe * 10 + breakout_bonus, 0.0, 100.0))

    # 2. Timing quality (reuse already-computed timing_score)
    timing_quality_score = result.timing_score

    # 3. Risk/Reward ratio
    if stop is not None and tgt1 is not None and price > 0:
        downside = price - stop
        upside   = tgt1 - price
        if downside > 0:
            rr = upside / downside
        else:
            rr = 0.0
    else:
        # Volatility-based estimate when levels not available
        vol = result.volatility or 30.0
        rr = max(0.5, (vol / 20.0))   # rough proxy

    if rr >= 3:
        risk_reward_score = 90.0
    elif rr >= 2:
        risk_reward_score = 75.0
    elif rr >= 1.5:
        risk_reward_score = 60.0
    elif rr >= 1:
        risk_reward_score = 45.0
    else:
        risk_reward_score = 25.0

    # 4. Portfolio fit (by asset type, adjusted for risk)
    base_portfolio_fit = {
        "crypto":    60.0,
        "stock":     75.0,
        "us_stocks": 75.0,
        "etf":       85.0,
        "bist":      65.0,
    }.get(result.asset_type, 65.0)

    if result.risk_level in ("yüksek", "spekülatif"):
        base_portfolio_fit -= 15.0

    portfolio_fit = float(np.clip(base_portfolio_fit, 0.0, 100.0))

    # 5. Profile fit — distance from mid-risk (50) penalises extremes
    rsn = result.risk_score_num
    profile_fit = float(np.clip(100.0 - abs(rsn - 50.0) * 0.8, 20.0, 95.0))

    # 6. Alternative cost — "Could this money do better elsewhere?"
    if cs >= 75:
        alt_cost = 80.0
        alt_cost_note = "Bu fırsat yüksek getiri potansiyeliyle portföyde birincil sıraya aday."
    elif cs >= 60:
        alt_cost = 65.0
        alt_cost_note = "Orta-yüksek getiri beklentisi; alternatif varlıklarla kıyaslanmalı."
    elif cs >= 50:
        alt_cost = 50.0
        alt_cost_note = "Bu para endeks ETF'inde %8-12 potansiyel sunabilir — karşılaştırın."
    else:
        alt_cost = 35.0
        alt_cost_note = "Alternatif yatırımlar daha iyi risk-getiri dengesi sunabilir."

    return {
        "opp_quality":   round(opp_quality, 2),
        "timing_quality": round(timing_quality_score, 2),
        "risk_reward":   round(risk_reward_score, 2),
        "portfolio_fit": round(portfolio_fit, 2),
        "profile_fit":   round(profile_fit, 2),
        "alt_cost":      round(alt_cost, 2),
        "alt_cost_note": alt_cost_note,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LABEL & DECISION GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _risk_hint_to_label(risk_hint: str) -> str:
    """Map YAML risk_level values to display-friendly Turkish labels."""
    mapping = {
        "cok_dusuk":   "çok düşük",
        "dusuk":       "düşük",
        "orta":        "orta",
        "orta_yuksek": "orta-yüksek",
        "yuksek":      "yüksek",
        "cok_yuksek":  "çok yüksek",
        "spekulatif":  "spekülatif",
    }
    return mapping.get(risk_hint, "orta")


def _risk_level_to_num(risk_label: str) -> float:
    """Return a 0-100 numeric risk score from a display label."""
    mapping = {
        "çok düşük":   15.0,
        "düşük":       28.0,
        "orta":        45.0,
        "orta-yüksek": 58.0,
        "yüksek":      72.0,
        "çok yüksek":  85.0,
        "spekülatif":  95.0,
    }
    return mapping.get(risk_label, 50.0)


def _generate_labels(
    result: OpportunityResult,
    metrics: dict = None,
    tech_result=None,
) -> OpportunityResult:
    """
    Populate opportunity_label, opportunity_type, decision, decision_confidence,
    why_buy, why_not_buy, catalysts, risks, trade levels, time_horizon,
    suitable_for, narrative fields, and institutional enrichment fields
    based on computed scores and metrics.

    Mutates and returns the same object.
    """
    if metrics is None:
        metrics = {}

    cs   = result.composite_score
    rsi  = result.rsi
    vol  = result.volatility
    ret_1w = result.return_1w
    ret_1m = result.return_1m
    ret_3m = result.return_3m
    sharpe = result.sharpe
    dd     = result.max_drawdown
    price  = result.current_price

    # ── Opportunity label ─────────────────────────────────────────────────────
    momentum_strong = (ret_1w or 0) > 5 or (ret_1m or 0) > 10

    if cs >= 78 and momentum_strong:
        result.opportunity_label = "⚡ Momentum Fırsatı"
        result.opportunity_type  = "momentum"
    elif cs >= 75:
        result.opportunity_label = "🚀 Büyüme Fırsatı"
        result.opportunity_type  = "buyume"
    elif cs >= 65 and (rsi is not None) and rsi < 40:
        result.opportunity_label = "💎 Değer Fırsatı"
        result.opportunity_type  = "deger"
    elif cs >= 60 and (vol is not None) and vol < 20:
        result.opportunity_label = "🛡️ Savunmacı Fırsat"
        result.opportunity_type  = "savunmaci"
    elif cs >= 55:
        result.opportunity_label = "⚖️ Dengeli Fırsat"
        result.opportunity_type  = "denge"
    elif cs >= 45 and (vol is not None) and vol > 30:
        result.opportunity_label = "🎯 Yüksek Risk/Ödül"
        result.opportunity_type  = "yuksek_risk"
    elif cs >= 40:
        result.opportunity_label = "👁 İzleme Listesi"
        result.opportunity_type  = "izleme"
    elif cs >= 35:
        result.opportunity_label = "📈 Kademeli Toplama"
        result.opportunity_type  = "birikim"
    else:
        result.opportunity_label = "🔥 Spekülatif"
        result.opportunity_type  = "spekulatif"

    # ── Decision ──────────────────────────────────────────────────────────────
    if cs >= 78:
        result.decision = "GÜÇLÜ AL"
        conf_base = cs
    elif cs >= 68:
        result.decision = "AL"
        conf_base = cs
    elif cs >= 58:
        result.decision = "BİRİKTİR"
        conf_base = cs
    elif cs >= 50:
        result.decision = "İZLE"
        conf_base = max(50.0, cs)
    elif cs >= 42:
        result.decision = "TUTE"
        conf_base = 100.0 - cs
    elif cs >= 35:
        result.decision = "AZALT"
        conf_base = 100.0 - cs
    elif cs >= 25:
        result.decision = "SAT"
        conf_base = 100.0 - cs
    else:
        result.decision = "KAÇIN"
        conf_base = 100.0 - cs

    result.decision_confidence = round(float(np.clip(conf_base, 0, 100)), 1)

    # ── Why buy (bull case, dynamic) ─────────────────────────────────────────
    bulls: list = []

    if rsi is not None and rsi < 35:
        bulls.append(
            f"RSI {rsi:.0f} — aşırı satım bölgesinde, teknik toparlanma potansiyeli yüksek"
        )
    elif rsi is not None and rsi < 50:
        bulls.append(
            f"RSI {rsi:.0f} — nötr-negatif bölge, geri çekilme sonrası giriş fırsatı"
        )

    if ret_1w is not None and ret_1w > 5:
        bulls.append(
            f"Son 1 haftada %{ret_1w:.1f} momentum — kısa vadeli ivme pozitif"
        )
    if ret_1m is not None and ret_1m > 10:
        bulls.append(
            f"Son 1 ayda %{ret_1m:.1f} momentum — güçlü trend devam ediyor"
        )
    if ret_3m is not None and ret_3m > 20:
        bulls.append(
            f"Son 3 ayda %{ret_3m:.1f} getiri — orta vadeli ivme güçlü"
        )

    if result.trend == "UPTREND":
        bulls.append("EMA 20/50/200 üzerinde kapanış — yapısal yükseliş trendi korunuyor")
    elif result.trend == "SIDEWAYS" and cs >= 55:
        bulls.append("Yatay konsolidasyon sona erer gibi görünüyor — kırılım beklentisi")

    if sharpe is not None and sharpe > 1:
        bulls.append(
            f"Sharpe {sharpe:.2f} — risk-getiri oranı sektör ortalamasının üzerinde"
        )

    if dd is not None and dd > -15:
        bulls.append(
            f"Max drawdown %{dd:.1f} — sınırlı geçmiş kayıp, güçlü savunma profili"
        )

    if result.breakout:
        bulls.append("Direnç kırılımı tespit edildi — teknik breakout sinyali aktif")

    if result.volume_signal == "high":
        bulls.append("Ortalamanın üzerinde hacim — kurumsal ilgi sinyali")

    if cs >= 65:
        bulls.append(
            f"Kompozit skor {cs:.0f}/100 — güçlü çok faktörlü fırsat puanı"
        )

    # Ensure 3–5 bullets
    if len(bulls) < 3:
        bulls.append("Genel piyasa momentumu bu varlık sınıfını destekliyor")
    if len(bulls) < 3:
        bulls.append("Uzun vadeli ortalama seviyelerinde dengeli değerleme")
    result.why_buy = bulls[:5]

    # ── Why not buy (bear case) ───────────────────────────────────────────────
    bears: list = []

    if vol is not None and vol > 30:
        bears.append(
            f"Yüksek volatilite (%{vol:.0f}) kayıp riskini artırıyor"
        )
    if rsi is not None and rsi > 65:
        bears.append("Kısa vadeli aşırı alım mevcut, düzeltme riski")
    if ret_1m is not None and ret_1m < -10:
        bears.append(
            f"Son 1 ayda %{ret_1m:.1f} düşüş — negatif trend henüz kırılmadı"
        )
    if dd is not None and dd < -30:
        bears.append(
            f"Geçmişte %{dd:.1f} maksimum düşüş yaşandı — yüksek geçici kayıp riski"
        )

    bears.append("Makro belirsizlik bu varlık sınıfını olumsuz etkileyebilir")

    result.why_not_buy = bears[:3]

    # ── Catalysts ─────────────────────────────────────────────────────────────
    catalysts: list = []
    if result.asset_type == "crypto":
        catalysts += [
            "BTC ETF ek giriş akışları ve kurumsal benimseme",
            "Zincir üstü kullanım metrikleri iyileşme kaydediyor",
        ]
    elif result.asset_type in ("stock", "us_stocks"):
        catalysts += [
            "Güçlü kazanç sezonu beklentisi",
            "Fed faiz indirim döngüsü başlangıcı",
        ]
    elif result.asset_type == "bist":
        catalysts += [
            "TCMB parasal sıkılaştırma normalizasyonu",
            "Yabancı yatırımcı geri dönüş süreci",
        ]
    elif result.asset_type == "etf":
        catalysts += [
            "Sektör rotasyonu ve güçlü para akışları",
            "Makro iyileşme sektörü olumlu etkiliyor",
        ]
    if result.breakout:
        catalysts.append("Teknik direnç kırılımı ek momentum yaratabilir")
    result.catalysts = catalysts

    # ── Risks ─────────────────────────────────────────────────────────────────
    risks: list = []
    if vol is not None and vol > 40:
        risks.append(f"Yüksek volatilite (%{vol:.0f}) portföy dalgalanmasına yol açabilir")
    risks.append("Küresel makro şok senaryosunda korelasyon artışı riski")
    risks.append("Likidite daralması dönemlerinde değerleme baskısı")
    if result.asset_type == "crypto":
        risks.append("Regülasyon riski ve piyasa duyarlılığı kaynaklı sert düşüşler")
    result.risks = risks

    # ── Trade levels ──────────────────────────────────────────────────────────
    if price and price > 0:
        dd_abs = abs(dd) if dd is not None else 5.0
        sl_pct = max(dd_abs * 0.5 / 100, 0.05)

        result.entry_zone_low  = round(price * 0.97, 6)
        result.entry_zone_high = round(price * 1.02, 6)
        result.stop_loss       = round(price * (1 - sl_pct), 6)
        result.target_1        = round(price * 1.08, 6)
        result.target_2        = round(price * 1.18, 6)
        result.target_3        = round(price * 1.32, 6)

    # ── Time horizon ──────────────────────────────────────────────────────────
    if (ret_1w or 0) > 5 and (ret_1m or 0) > 10:
        result.time_horizon = "kısa"
    elif (ret_3m or 0) > 0 and result.trend in ("UPTREND", "SIDEWAYS"):
        result.time_horizon = "orta"
    elif (sharpe or 0) > 1 and result.risk_level in ("çok düşük", "düşük", "orta"):
        result.time_horizon = "uzun"
    else:
        result.time_horizon = "orta"

    # ── Suitable for ─────────────────────────────────────────────────────────
    rl = result.risk_level
    if rl in ("çok düşük", "düşük") and cs >= 55:
        result.suitable_for = ["Yeni başlayan", "Orta seviye yatırımcı", "Uzun vadeli yatırımcı"]
    elif rl in ("orta",):
        result.suitable_for = ["Orta seviye yatırımcı", "İleri seviye yatırımcı"]
    elif rl in ("orta-yüksek", "yüksek"):
        result.suitable_for = ["İleri seviye yatırımcı", "Kısa vadeli yatırımcı"]
    else:
        result.suitable_for = ["İleri seviye yatırımcı"]

    # ── Scenario / education ─────────────────────────────────────────────────
    result.invalidation = (
        f"Fiyat stop-loss seviyesi {result.stop_loss:.4g}'in altına kapanırsa "
        f"veya {result.trend} trendi tersine dönerse bu tez geçersiz sayılır."
        if result.stop_loss
        else "Trendin tersine dönmesi veya beklenen katalizörlerin gerçekleşmemesi tezi geçersiz kılar."
    )

    result.alternative_scenario = (
        "Makro ortamın bozulması durumunda savunmacı değer varlıklarına "
        "geçiş ve nakit pozisyonu artırmak alternatif strateji olarak değerlendirilebilir."
    )

    result.education_note = (
        "Teknik analiz geçmiş fiyat hareketlerine dayalıdır; gelecekteki performansı "
        "garanti etmez. Yatırım kararlarınızı kişisel risk toleransınıza göre verin. "
        "Bu analiz bilgilendirme amaçlıdır, yatırım tavsiyesi değildir."
    )

    # ── Timing analysis ────────────────────────────────────────────────────────
    t_score, t_quality, _t_warning = _calculate_timing_score(
        metrics, tech_result, result.rsi, result.volatility
    )
    result.timing_score   = t_score
    result.timing_quality = t_quality

    # Generate timing warning using composite score (now available)
    if t_score < 45 and cs > 60:
        result.timing_warning = (
            "⚠️ Doğru varlık, yanlış zaman — fiyat kısa vadede geri çekilebilir. "
            "Kademeli giriş veya bekleme önerilebilir."
        )
    elif t_score < 35:
        result.timing_warning = (
            "🔴 Zamanlama olumsuz — acele alım yapmayın. "
            "Teknik yapı düzelene kadar izleyin."
        )
    else:
        result.timing_warning = ""

    # ── Conviction & confidence ────────────────────────────────────────────────
    result.conviction_score, result.allocation_confidence = _calculate_conviction_score(
        result.composite_score, result.timing_score, result.risk_score
    )

    # ── Catalyst map ──────────────────────────────────────────────────────────
    result.catalyst_map = _build_catalyst_map(result)

    # ── Scenario tree ─────────────────────────────────────────────────────────
    result.scenario_bull, result.scenario_base, result.scenario_bear = _build_scenario_tree(result)

    # ── Invalidation events ────────────────────────────────────────────────────
    result.invalidation_events = _build_invalidation_events(result)

    # ── Multi-dimensional ─────────────────────────────────────────────────────
    dims = _calculate_multi_dimensional(result)
    result.dim_opportunity_quality = dims["opp_quality"]
    result.dim_timing_quality      = dims["timing_quality"]
    result.dim_risk_reward         = dims["risk_reward"]
    result.dim_portfolio_fit       = dims["portfolio_fit"]
    result.dim_profile_fit         = dims["profile_fit"]
    result.dim_alternative_cost    = dims["alt_cost"]
    result.alternative_cost_note   = dims["alt_cost_note"]

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE ASSET ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_single_asset(
    symbol: str,
    name: str,
    asset_type: str,
    sector: str,
    risk_hint: str,
    category: str = "",
    force: bool = False,
) -> Optional[OpportunityResult]:
    """
    Fetch data, run technical analysis, compute scores, and build an
    OpportunityResult for a single asset. Returns None on failure.
    """
    logger.debug("Analysing %s (%s)…", symbol, asset_type)

    # ── Fetch price data ──────────────────────────────────────────────────────
    df = _fetch_with_cache(symbol, force=force)
    if df is None or len(df) < 30:
        logger.warning("Insufficient data for %s — skipping.", symbol)
        return None

    if "close" not in df.columns:
        logger.warning("No 'close' column for %s — skipping.", symbol)
        return None

    close  = df["close"].dropna().astype(float)
    last_p = float(close.iloc[-1])

    # ── Returns & risk metrics ────────────────────────────────────────────────
    metrics = _calculate_returns(close)

    # ── Technical analysis ────────────────────────────────────────────────────
    tech: Optional[object] = None
    if _ANALYZER is not None:
        try:
            tech = _ANALYZER.analyze(df, _TECH_CFG)
        except Exception as exc:
            logger.warning("TechnicalAnalyzer failed for %s: %s", symbol, exc)

    # ── Scoring ───────────────────────────────────────────────────────────────
    t_score, m_score, r_score, q_score, composite = _score_opportunity(metrics, tech)

    # ── Build result object ───────────────────────────────────────────────────
    result = OpportunityResult()
    result.symbol      = symbol
    result.name        = name
    result.asset_type  = asset_type
    result.sector      = sector
    result.category    = category
    result.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Currency heuristic
    if symbol.endswith(".IS"):
        result.currency = "TRY"
    elif asset_type == "bist":
        result.currency = "TRY"
    else:
        result.currency = "USD"

    # Price & display
    result.current_price = round(last_p, 6)

    ret_1d = metrics.get("return_1d")
    if ret_1d is not None:
        sign = "+" if ret_1d >= 0 else ""
        result.price_change_display = f"{sign}{ret_1d:.1f}%"
    else:
        result.price_change_display = "N/A"

    # Returns
    result.return_1d  = metrics.get("return_1d")
    result.return_1w  = metrics.get("return_1w")
    result.return_1m  = metrics.get("return_1m")
    result.return_3m  = metrics.get("return_3m")
    result.return_6m  = metrics.get("return_6m")
    result.return_1y  = metrics.get("return_1y")

    # Risk metrics
    result.volatility   = metrics.get("volatility")
    result.sharpe       = metrics.get("sharpe")
    result.max_drawdown = metrics.get("max_drawdown")

    # Technical fields from TechnicalResult
    if tech is not None:
        result.rsi         = tech.rsi
        result.trend       = tech.trend
        result.bb_position = tech.bb_pct
        result.breakout    = tech.breakout

        # MACD signal direction
        hist = tech.macd_histogram
        if hist is not None:
            if hist > 0:
                result.macd_signal = "bullish"
            elif hist < 0:
                result.macd_signal = "bearish"
            else:
                result.macd_signal = "neutral"

        # Volume signal
        vr = tech.volume_ratio
        if vr is not None:
            if vr > 1.5:
                result.volume_signal = "high"
            elif vr < 0.7:
                result.volume_signal = "low"
            else:
                result.volume_signal = "normal"

    # Scores
    result.tech_score       = t_score
    result.momentum_score   = m_score
    result.risk_score       = r_score
    result.composite_score  = composite

    # Risk level mapping
    result.risk_level     = _risk_hint_to_label(risk_hint)
    result.risk_score_num = _risk_level_to_num(result.risk_level)

    # Generate labels, decision, narrative, trade levels and institutional fields
    result = _generate_labels(result, metrics=metrics, tech_result=tech)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def scan_asset_type(asset_type: str, force_refresh: bool = False) -> list:
    """
    Scan all assets of a given type from the universe.

    Args:
        asset_type: One of 'crypto', 'us_stocks', 'bist', 'priority_etfs'.
        force_refresh: Bypass cache and re-fetch from yfinance.

    Returns:
        List of OpportunityResult sorted by composite_score descending.
    """
    universe = load_asset_universe()
    assets   = universe.get(asset_type, [])

    if not assets:
        logger.warning("No assets found for type '%s'.", asset_type)
        return []

    # Normalise asset_type label
    at_label = "etf" if asset_type == "priority_etfs" else asset_type.rstrip("s")
    if at_label == "us_stock":
        at_label = "stock"

    def _analyse_entry(entry: dict):
        symbol    = entry.get("symbol", "")
        name      = entry.get("name", symbol)
        sector    = entry.get("sector", "")
        category  = entry.get("category", "")
        risk_hint = entry.get("risk_level", "orta")
        try:
            return _analyze_single_asset(
                symbol=symbol, name=name, asset_type=at_label,
                sector=sector, risk_hint=risk_hint, category=category,
                force=force_refresh,
            )
        except Exception as exc:
            logger.warning("Unexpected error analysing %s: %s", symbol, exc)
            return None

    # ── Paralel tarama (10 iş parçacığı) ─────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed
    _MAX_WORKERS = 10
    results: list = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_analyse_entry, entry): entry for entry in assets}
        for fut in as_completed(futures):
            opp = fut.result()
            if opp is not None:
                results.append(opp)

    results.sort(key=lambda r: r.composite_score, reverse=True)
    logger.info(
        "scan_asset_type('%s') → %d/%d results.",
        asset_type,
        len(results),
        len(assets),
    )
    return results


def scan_all_opportunities(force_refresh: bool = False) -> list:
    """
    Scan all asset types in the universe and return a unified, ranked list.

    Args:
        force_refresh: Bypass all caches.

    Returns:
        All OpportunityResults sorted by composite_score descending.
    """
    # 4 varlık sınıfını da paralel tara
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    all_results: list = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {
            pool.submit(scan_asset_type, at, force_refresh): at
            for at in ("crypto", "us_stocks", "bist", "priority_etfs")
        }
        for fut in _as_completed(futs):
            try:
                all_results.extend(fut.result())
            except Exception as exc:
                logger.warning("scan_asset_type failed: %s", exc)

    all_results.sort(key=lambda r: r.composite_score, reverse=True)
    logger.info("scan_all_opportunities() → %d total results.", len(all_results))
    return all_results


def get_top_opportunities(
    n: int = 20,
    min_composite: float = 55.0,
    asset_types: Optional[list] = None,
    risk_levels: Optional[list] = None,
) -> list:
    """
    Return the top N opportunities matching optional filter criteria.

    Args:
        n:             Maximum number of results to return.
        min_composite: Minimum composite score threshold (default 55).
        asset_types:   Optional list of asset types to include, e.g. ['crypto', 'stock'].
                       Accepts both 'us_stocks'/'stock' variants.
        risk_levels:   Optional list of risk_level labels to include,
                       e.g. ['düşük', 'orta', 'orta-yüksek'].

    Returns:
        Up to N OpportunityResults sorted by composite_score descending.
    """
    all_opps = scan_all_opportunities()

    # Normalise asset_type filters (accept plural/singular variants)
    _at_map = {
        "us_stocks": "stock",
        "us_stock":  "stock",
        "priority_etfs": "etf",
        "priority_etf":  "etf",
        "cryptos": "crypto",
    }
    normalised_types: Optional[set] = None
    if asset_types:
        normalised_types = {_at_map.get(a, a) for a in asset_types}

    filtered: list = []
    for opp in all_opps:
        if opp.composite_score < min_composite:
            continue
        if normalised_types and opp.asset_type not in normalised_types:
            continue
        if risk_levels and opp.risk_level not in risk_levels:
            continue
        filtered.append(opp)
        if len(filtered) >= n:
            break

    logger.info(
        "get_top_opportunities(n=%d, min_composite=%.0f) → %d results.",
        n,
        min_composite,
        len(filtered),
    )
    return filtered


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT (quick smoke-test)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    print("\n=== HedgeFund AI — Opportunity Engine Smoke Test ===\n")
    print("Loading asset universe…")
    universe = load_asset_universe()
    for k, v in universe.items():
        print(f"  {k}: {len(v)} assets")

    print("\nScanning top 5 opportunities (min_composite=50)…")
    top = get_top_opportunities(n=5, min_composite=50)
    for i, opp in enumerate(top, 1):
        print(
            f"  {i}. [{opp.composite_score:5.1f}] {opp.symbol:<16} {opp.name:<30} "
            f"{opp.decision:<10} {opp.opportunity_label}"
        )
    print("\nDone.")
