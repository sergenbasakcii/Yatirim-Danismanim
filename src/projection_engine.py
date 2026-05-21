"""
HedgeFund AI — İleriye Dönük Projeksiyon Motoru
================================================
Kullanıcı bir varlığı belirli tarihte alıp belirli tarihte satarsa
ne olabileceğini istatistiksel olarak modeller.

Yöntemler:
  1. Tarihsel benzer dönem analizi   (geçmiş veri varsa)
  2. Monte Carlo simülasyonu         (1000 yol, geometric Brownian motion)
  3. Senaryo ağacı                   (Boğa / Baz / Ayı)
  4. Risk metrikleri                 (VaR, MaxDD, volatilite)
  5. Karşılaştırma                   (SPY / altın ile yan yana)
"""

from __future__ import annotations

import logging
import math
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

_CACHE_DIR = _ROOT / "data" / "raw"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_HOURS = 4


# ══════════════════════════════════════════════════════════════════════════════
# RESULT DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScenarioResult:
    name: str           # "Boğa" / "Baz" / "Ayı"
    emoji: str
    probability_pct: int
    return_pct: float
    final_value: float   # başlangıç miktarı × (1 + return/100)
    profit_loss: float   # final_value - başlangıç
    annualized_return_pct: float
    description: str


@dataclass
class MonteCarloResult:
    percentile_5: float    # %5 en kötü (VaR benzeri)
    percentile_25: float
    percentile_50: float   # medyan
    percentile_75: float
    percentile_95: float   # %5 en iyi
    mean_return: float
    positive_prob_pct: float   # kârlı çıkma olasılığı %
    paths_sample: list = field(default_factory=list)   # görselleştirme için 20 yol


@dataclass
class HistoricalPeriodResult:
    found: bool
    periods_analyzed: int
    avg_return_pct: float
    best_return_pct: float
    worst_return_pct: float
    positive_count: int
    negative_count: int
    positive_pct: float
    description: str


@dataclass
class ProjectionResult:
    # ── Girdi ────────────────────────────────────────────────────────────────
    symbol: str
    name: str
    asset_type: str
    buy_date: date
    sell_date: date
    amount: float           # yatırım tutarı
    currency: str

    # ── Fiyat bilgisi ────────────────────────────────────────────────────────
    current_price: float
    buy_price_estimate: float    # alış tarihi tahmini fiyat
    holding_days: int
    holding_years: float

    # ── Volatilite & risk ─────────────────────────────────────────────────────
    annual_volatility_pct: float
    daily_volatility_pct: float
    sharpe_estimate: float
    max_drawdown_historical: float  # geçmiş max DD (%)

    # ── Senaryo ağacı ─────────────────────────────────────────────────────────
    scenario_bull: ScenarioResult = None
    scenario_base: ScenarioResult = None
    scenario_bear: ScenarioResult = None

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    monte_carlo: MonteCarloResult = None

    # ── Tarihsel benzer dönemler ──────────────────────────────────────────────
    historical: HistoricalPeriodResult = None

    # ── Karşılaştırma ─────────────────────────────────────────────────────────
    benchmark_spy_return_pct: float = 0.0    # SPY aynı vadede beklenen getiri
    benchmark_gold_return_pct: float = 0.0
    vs_spy_advantage_pct: float = 0.0        # base senaryoda SPY'e karşı avantaj

    # ── Risk uyarıları ────────────────────────────────────────────────────────
    risk_warnings: list = field(default_factory=list)
    education_notes: list = field(default_factory=list)

    # ── Özet ─────────────────────────────────────────────────────────────────
    summary_verdict: str = ""   # tek cümle karar
    confidence_score: float = 50.0


# ══════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_history(symbol: str, period: str = "5y") -> Optional[pd.DataFrame]:
    """yfinance'dan geçmiş fiyat verisi çek, cache'e yaz."""
    cache_path = _CACHE_DIR / f"proj_{symbol.replace('-','_').replace('.','_')}.json"

    if cache_path.exists():
        age = (time.time() - cache_path.stat().st_mtime) / 3600
        if age < _CACHE_TTL_HOURS:
            try:
                import json
                with open(cache_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                df = pd.DataFrame(data)
                df.index = pd.to_datetime(df.index, errors="coerce")
                df.columns = [c.lower() for c in df.columns]
                return df
            except Exception:
                pass

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, auto_adjust=True)
        if df is None or df.empty:
            return None
        df.columns = [c.lower() for c in df.columns]
        if hasattr(df.index, "tz") and df.index.tz:
            df.index = df.index.tz_localize(None)
        # Cache
        import json
        payload = {str(k): v for k, v in df.to_dict("list").items()}
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return df
    except Exception as exc:
        logger.warning("Fetch failed for %s: %s", symbol, exc)
        return None


def _annualized_return(total_return_pct: float, years: float) -> float:
    """Toplam getiriyi yıllıklaştır."""
    if years <= 0:
        return 0.0
    try:
        return ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100
    except Exception:
        return 0.0


def _years_between(d1: date, d2: date) -> float:
    return max(0.0, (d2 - d1).days / 365.25)


# ══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO SİMÜLASYONU
# ══════════════════════════════════════════════════════════════════════════════

def _run_monte_carlo(
    initial_price: float,
    daily_return_mean: float,
    daily_return_std: float,
    n_days: int,
    n_simulations: int = 1000,
    n_sample_paths: int = 20,
) -> MonteCarloResult:
    """
    Geometric Brownian Motion ile Monte Carlo simülasyonu.
    Returns: MonteCarloResult
    """
    rng = np.random.default_rng(42)  # tekrarlanabilirlik için sabit seed

    # n_simulations × n_days matris
    daily_shocks = rng.normal(
        loc=daily_return_mean,
        scale=daily_return_std,
        size=(n_simulations, n_days),
    )

    # Fiyat yolları: kümülatif çarpım
    price_paths = initial_price * np.exp(np.cumsum(daily_shocks, axis=1))

    final_prices = price_paths[:, -1]
    final_returns = (final_prices / initial_price - 1) * 100

    # Yüzdelikler
    p5  = float(np.percentile(final_returns, 5))
    p25 = float(np.percentile(final_returns, 25))
    p50 = float(np.percentile(final_returns, 50))
    p75 = float(np.percentile(final_returns, 75))
    p95 = float(np.percentile(final_returns, 95))
    mean_ret = float(np.mean(final_returns))
    pos_prob = float(np.mean(final_returns > 0) * 100)

    # Görselleştirme için örnek yollar
    sample_indices = rng.choice(n_simulations, size=min(n_sample_paths, n_simulations), replace=False)
    sample_paths = []
    for idx in sample_indices:
        path = price_paths[idx].tolist()
        sample_paths.append(path[::max(1, n_days // 50)])  # max 50 nokta

    return MonteCarloResult(
        percentile_5=round(p5, 2),
        percentile_25=round(p25, 2),
        percentile_50=round(p50, 2),
        percentile_75=round(p75, 2),
        percentile_95=round(p95, 2),
        mean_return=round(mean_ret, 2),
        positive_prob_pct=round(pos_prob, 1),
        paths_sample=sample_paths,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TARİHSEL BENZER DÖNEM ANALİZİ
# ══════════════════════════════════════════════════════════════════════════════

def _analyze_historical_periods(
    close: pd.Series,
    holding_days: int,
) -> HistoricalPeriodResult:
    """
    Geçmişte aynı uzunlukta tutma dönemlerinin getirilerini analiz et.
    Örn: "THY'yi 200 gün tutan kişilerin %72'si kârdaydı"
    """
    returns = []
    step = max(1, holding_days // 5)  # örtüşmeyi azalt

    for i in range(0, len(close) - holding_days, step):
        start_p = float(close.iloc[i])
        end_p   = float(close.iloc[i + holding_days])
        if start_p > 0:
            ret = (end_p / start_p - 1) * 100
            returns.append(ret)

    if not returns:
        return HistoricalPeriodResult(
            found=False, periods_analyzed=0,
            avg_return_pct=0, best_return_pct=0, worst_return_pct=0,
            positive_count=0, negative_count=0, positive_pct=0,
            description="Yeterli geçmiş veri bulunamadı.",
        )

    pos = [r for r in returns if r > 0]
    neg = [r for r in returns if r <= 0]

    return HistoricalPeriodResult(
        found=True,
        periods_analyzed=len(returns),
        avg_return_pct=round(float(np.mean(returns)), 2),
        best_return_pct=round(float(max(returns)), 2),
        worst_return_pct=round(float(min(returns)), 2),
        positive_count=len(pos),
        negative_count=len(neg),
        positive_pct=round(len(pos) / len(returns) * 100, 1),
        description=(
            f"Geçmişte {len(returns)} farklı {holding_days} günlük dönem analiz edildi. "
            f"Ortalama getiri %{float(np.mean(returns)):.1f}, "
            f"%{len(pos)/len(returns)*100:.0f}'si kârlıydı."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# SENARYO AĞACI OLUŞTURUCU
# ══════════════════════════════════════════════════════════════════════════════

def _build_scenarios(
    amount: float,
    holding_years: float,
    annual_vol: float,
    mc: MonteCarloResult,
    asset_type: str,
) -> tuple:
    """Boğa / Baz / Ayı senaryoları oluştur."""
    base_ret  = mc.percentile_50
    bull_ret  = mc.percentile_75
    bear_ret  = mc.percentile_5

    # Annualized için düzeltme
    ann_base  = _annualized_return(base_ret,  holding_years)
    ann_bull  = _annualized_return(bull_ret,  holding_years)
    ann_bear  = _annualized_return(bear_ret,  holding_years)

    def make_sc(name, emoji, prob, ret, ann, desc):
        final_val = amount * (1 + ret / 100)
        return ScenarioResult(
            name=name, emoji=emoji,
            probability_pct=prob,
            return_pct=round(ret, 2),
            final_value=round(final_val, 2),
            profit_loss=round(final_val - amount, 2),
            annualized_return_pct=round(ann, 2),
            description=desc,
        )

    # Olasılık dağılımı: kâr olasılığına göre dinamik
    pos_prob = mc.positive_prob_pct
    bull_prob = max(15, min(45, int(pos_prob * 0.6)))
    base_prob = max(30, min(55, int(pos_prob * 0.5)))
    bear_prob = max(10, 100 - bull_prob - base_prob)

    type_notes = {
        "crypto": "Kripto piyasasının yüksek volatilitesi bu aralığı geniş tutuyor.",
        "stock":  "Hisse senedi performansı makro koşullara bağlı.",
        "bist":   "BIST hisseleri TL bazlı; kur etkisi dâhil değil.",
        "etf":    "ETF çeşitlendirmesi riski sınırlar.",
    }
    note = type_notes.get(asset_type, "")

    bull = make_sc("Boğa", "📈", bull_prob, bull_ret, ann_bull,
                   f"Piyasa beklentilerin üzerinde performans gösteriyor. {note}")
    base = make_sc("Baz",  "📊", base_prob, base_ret, ann_base,
                   f"Tarihsel ortalamaya uygun seyir. {note}")
    bear = make_sc("Ayı",  "📉", bear_prob, bear_ret, ann_bear,
                   f"Olumsuz senaryo — stop-loss veya çeşitlendirme ile yönetilebilir.")

    return bull, base, bear


# ══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ══════════════════════════════════════════════════════════════════════════════

def run_projection(
    symbol: str,
    name: str,
    asset_type: str,
    buy_date: date,
    sell_date: date,
    amount: float,
    currency: str = "USD",
    n_simulations: int = 1000,
) -> Optional[ProjectionResult]:
    """
    Belirli varlık, tarih aralığı ve tutar için projeksiyon hesapla.

    Returns:
        ProjectionResult veya None (veri yoksa)
    """
    if sell_date <= buy_date:
        logger.warning("Satış tarihi alış tarihinden önce olamaz.")
        return None

    holding_days  = (sell_date - buy_date).days
    holding_years = holding_days / 365.25

    # ── Geçmiş veri çek ──────────────────────────────────────────────────────
    period = "10y" if holding_years > 3 else "5y"
    df = _fetch_history(symbol, period=period)

    if df is None or len(df) < 30:
        logger.warning("Yetersiz veri: %s", symbol)
        return None

    if "close" not in df.columns:
        return None

    close = df["close"].dropna().astype(float)
    current_price = float(close.iloc[-1])

    # ── Temel istatistikler ───────────────────────────────────────────────────
    daily_rets = close.pct_change().dropna()
    daily_mean = float(daily_rets.mean())
    daily_std  = float(daily_rets.std())
    annual_vol = daily_std * math.sqrt(252) * 100

    rf_daily = 0.05 / 252
    sharpe = (daily_mean - rf_daily) / daily_std * math.sqrt(252) if daily_std > 0 else 0.0

    # Max drawdown
    roll_max = close.cummax()
    dd = ((close - roll_max) / roll_max * 100).min()

    # ── Alış tarihi fiyat tahmini ─────────────────────────────────────────────
    buy_date_dt = pd.Timestamp(buy_date)
    today = pd.Timestamp(date.today())

    if buy_date_dt <= today and buy_date_dt >= close.index.min():
        # Tarihe en yakın veriyi bul
        idx_loc = close.index.get_indexer([buy_date_dt], method="nearest")[0]
        buy_price = float(close.iloc[idx_loc]) if idx_loc >= 0 else current_price
    else:
        # Gelecek tarih — şimdiki fiyatı kullan
        buy_price = current_price

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    mc = _run_monte_carlo(
        initial_price=buy_price,
        daily_return_mean=daily_mean,
        daily_return_std=daily_std,
        n_days=holding_days,
        n_simulations=n_simulations,
    )

    # ── Senaryo ağacı ─────────────────────────────────────────────────────────
    bull, base, bear = _build_scenarios(
        amount=amount,
        holding_years=holding_years,
        annual_vol=annual_vol,
        mc=mc,
        asset_type=asset_type,
    )

    # ── Tarihsel dönem analizi ────────────────────────────────────────────────
    historical = _analyze_historical_periods(close, holding_days)

    # ── Benchmark karşılaştırma ───────────────────────────────────────────────
    # SPY için basit tarihsel ortalama: ~10.5% yıllık
    spy_ann = 10.5
    gold_ann = 8.0
    spy_total   = ((1 + spy_ann  / 100) ** holding_years - 1) * 100
    gold_total  = ((1 + gold_ann / 100) ** holding_years - 1) * 100
    vs_spy_adv  = base.return_pct - spy_total

    # ── Risk uyarıları ────────────────────────────────────────────────────────
    warnings = []
    if annual_vol > 60:
        warnings.append(f"⚠️  Çok yüksek volatilite (%{annual_vol:.0f}) — kısa vadede büyük salınımlar beklenir.")
    if bear.return_pct < -40:
        warnings.append(f"⚠️  Ayı senaryosunda %{abs(bear.return_pct):.0f} kayıp riski mevcut.")
    if holding_days < 30:
        warnings.append("⚠️  30 günden kısa tutma süreleri spekülatif kategori sayılır.")
    if mc.positive_prob_pct < 50:
        warnings.append(f"⚠️  Monte Carlo'ya göre kâr olasılığı %{mc.positive_prob_pct:.0f} — zarar ihtimali daha yüksek.")
    if asset_type == "crypto" and holding_days < 90:
        warnings.append("💡  Kripto varlıklarda kısa vadeli işlemler vergi ve volatilite açısından riskli.")

    # ── Eğitim notları ────────────────────────────────────────────────────────
    edu = []
    if holding_years >= 1:
        edu.append(
            f"📚 {holding_years:.1f} yıllık tutma süresi için bileşik faiz etkisi önemli: "
            f"yıllık %{base.annualized_return_pct:.1f} getiri, {holding_years:.1f} yılda "
            f"toplam %{base.return_pct:.1f}'e ulaşır."
        )
    if mc.positive_prob_pct >= 60:
        edu.append(
            f"📚 Tarihsel veriye göre bu varlığı {holding_days} gün tutanların "
            f"%{historical.positive_pct:.0f}'i kârlıydı."
        )
    edu.append(
        "📚 Monte Carlo simülasyonu 1.000 farklı piyasa senaryosu çalıştırır. "
        "Medyan (%50) en olası sonucu, %5-95 aralığı uç senaryoları gösterir."
    )

    # ── Özet karar ────────────────────────────────────────────────────────────
    if base.return_pct > 20 and mc.positive_prob_pct > 65:
        verdict = f"✅  Güçlü projeksiyon — baz senaryoda %{base.return_pct:.1f} getiri, kâr olasılığı %{mc.positive_prob_pct:.0f}."
        confidence = 75.0
    elif base.return_pct > 5 and mc.positive_prob_pct > 50:
        verdict = f"🔶  Makul projeksiyon — baz senaryoda %{base.return_pct:.1f} getiri."
        confidence = 58.0
    elif base.return_pct <= 0:
        verdict = f"🔴  Olumsuz projeksiyon — mevcut trend devam ederse zarar riski yüksek."
        confidence = 40.0
    else:
        verdict = f"⚠️  Karma sinyaller — yatırım kararı yapmadan önce risk uyarılarını inceleyin."
        confidence = 50.0

    return ProjectionResult(
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        buy_date=buy_date,
        sell_date=sell_date,
        amount=amount,
        currency=currency,
        current_price=round(current_price, 4),
        buy_price_estimate=round(buy_price, 4),
        holding_days=holding_days,
        holding_years=round(holding_years, 2),
        annual_volatility_pct=round(annual_vol, 1),
        daily_volatility_pct=round(daily_std * 100, 3),
        sharpe_estimate=round(sharpe, 3),
        max_drawdown_historical=round(float(dd), 1),
        scenario_bull=bull,
        scenario_base=base,
        scenario_bear=bear,
        monte_carlo=mc,
        historical=historical,
        benchmark_spy_return_pct=round(spy_total, 2),
        benchmark_gold_return_pct=round(gold_total, 2),
        vs_spy_advantage_pct=round(vs_spy_adv, 2),
        risk_warnings=warnings,
        education_notes=edu,
        summary_verdict=verdict,
        confidence_score=confidence,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HIZLI SEMBOL ARAMA (UI autocomplete için)
# ══════════════════════════════════════════════════════════════════════════════

_COMMON_SYMBOLS: list = [
    # Kripto
    ("BTC-USD", "Bitcoin", "crypto"),
    ("ETH-USD", "Ethereum", "crypto"),
    ("BNB-USD", "BNB", "crypto"),
    ("SOL-USD", "Solana", "crypto"),
    ("ADA-USD", "Cardano", "crypto"),
    ("AVAX-USD", "Avalanche", "crypto"),
    ("DOT-USD", "Polkadot", "crypto"),
    ("LINK-USD", "Chainlink", "crypto"),
    ("NEAR-USD", "NEAR Protocol", "crypto"),
    ("ATOM-USD", "Cosmos", "crypto"),
    # ABD Hisseleri
    ("AAPL", "Apple Inc.", "stock"),
    ("MSFT", "Microsoft", "stock"),
    ("GOOGL", "Alphabet", "stock"),
    ("AMZN", "Amazon", "stock"),
    ("NVDA", "NVIDIA", "stock"),
    ("TSLA", "Tesla", "stock"),
    ("META", "Meta Platforms", "stock"),
    ("JPM", "JPMorgan Chase", "stock"),
    ("V", "Visa", "stock"),
    ("WMT", "Walmart", "stock"),
    ("COST", "Costco", "stock"),
    ("JNJ", "Johnson & Johnson", "stock"),
    ("MA", "Mastercard", "stock"),
    # BIST
    ("THYAO.IS", "Türk Hava Yolları", "bist"),
    ("EREGL.IS", "Ereğli Demir Çelik", "bist"),
    ("ASELS.IS", "ASELSAN", "bist"),
    ("TUPRS.IS", "Tüpraş", "bist"),
    ("SISE.IS", "Şişe Cam", "bist"),
    ("KRDMD.IS", "Kardemir", "bist"),
    ("BIMAS.IS", "BİM Mağazalar", "bist"),
    ("FROTO.IS", "Ford Otosan", "bist"),
    ("EKGYO.IS", "Emlak Konut GYO", "bist"),
    ("GARAN.IS", "Garanti BBVA", "bist"),
    ("ISCTR.IS", "İş Bankası C", "bist"),
    ("AKBNK.IS", "Akbank", "bist"),
    # ETF
    ("SPY", "SPDR S&P 500 ETF", "etf"),
    ("QQQ", "Invesco Nasdaq-100 ETF", "etf"),
    ("GLD", "SPDR Gold ETF", "etf"),
    ("TLT", "iShares 20Y+ Treasury ETF", "etf"),
    ("IBIT", "iShares Bitcoin Trust ETF", "etf"),
    ("ARKK", "ARK Innovation ETF", "etf"),
    ("SOXX", "iShares Semiconductor ETF", "etf"),
]


def search_symbols(query: str, limit: int = 10) -> list:
    """
    Sembol veya isim için autocomplete listesi döndür.
    Returns: [(symbol, name, asset_type), ...]
    """
    q = query.upper().strip()
    if not q:
        return _COMMON_SYMBOLS[:limit]

    results = [
        item for item in _COMMON_SYMBOLS
        if q in item[0].upper() or q in item[1].upper()
    ]

    # Eğer listede yoksa ham sembolü döndür
    if not results:
        results = [(q, q, "unknown")]

    return results[:limit]
