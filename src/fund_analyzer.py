"""
HedgeFund AI — Fon Analiz Motoru
TEFAS ve ETF fonları için teknik + performans analizi.
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FundResult:
    code:          str
    name:          str
    fund_type:     str = ""
    manager:       str = ""
    source:        str = ""   # "TEFAS" veya "ETF"

    # Fiyat
    current_price: Optional[float] = None

    # Getiriler
    return_1d:  Optional[float] = None
    return_1w:  Optional[float] = None
    return_1m:  Optional[float] = None
    return_3m:  Optional[float] = None
    return_6m:  Optional[float] = None
    return_1y:  Optional[float] = None

    # Risk
    sharpe:       Optional[float] = None
    max_drawdown: Optional[float] = None
    volatility:   Optional[float] = None

    # Skor
    score:    float = 50.0
    rating:   str   = "NÖTR"     # GÜÇLÜ AL / AL / NÖTR / SAT / GÜÇLÜ SAT
    signals:  list  = field(default_factory=list)
    summary:  str   = ""


def analyze_fund(
    code: str,
    name: str,
    fund_type: str,
    manager: str,
    history_df: pd.DataFrame,
    source: str = "ETF",
    metrics: Optional[dict] = None,
) -> FundResult:
    """Bir fon için kapsamlı analiz yap."""

    r = FundResult(
        code=code, name=name,
        fund_type=fund_type, manager=manager,
        source=source,
    )

    # Metrikler direkt verilmişse kullan (ETF screener'dan)
    if metrics:
        r.current_price = metrics.get("price")
        r.return_1d     = metrics.get("return_1d")
        r.return_1w     = metrics.get("return_1w")
        r.return_1m     = metrics.get("return_1m")
        r.return_3m     = metrics.get("return_3m")
        r.return_6m     = metrics.get("return_6m")
        r.return_1y     = metrics.get("return_1y")
        r.sharpe        = metrics.get("sharpe")
        r.max_drawdown  = metrics.get("max_drawdown")
        r.volatility    = metrics.get("volatility")

    # Tarihsel veriden hesapla
    elif not history_df.empty and "price" in history_df.columns:
        prices = history_df["price"].astype(float).dropna()
        if len(prices) > 1:
            last = float(prices.iloc[-1])
            r.current_price = round(last, 4)

            def ret(n):
                if len(prices) > n:
                    old = float(prices.iloc[-(n+1)])
                    return round((last - old) / old * 100, 2) if old > 0 else None
                return None

            r.return_1d = ret(1)
            r.return_1w = ret(5)
            r.return_1m = ret(21)
            r.return_3m = ret(63)
            r.return_6m = ret(126)
            r.return_1y = ret(252)

            daily = prices.pct_change().dropna()
            if len(daily) > 5 and daily.std() > 0:
                r.sharpe     = round(float(daily.mean() / daily.std() * np.sqrt(252)), 3)
                r.volatility = round(float(daily.std() * np.sqrt(252) * 100), 2)

            roll_max    = prices.cummax()
            dd          = (prices - roll_max) / roll_max
            r.max_drawdown = round(float(dd.min() * 100), 2)

    # Skor hesapla
    r.score, r.rating, r.signals = _score_fund(r)
    r.summary = _build_summary(r)
    return r


def _score_fund(r: FundResult) -> tuple[float, str, list]:
    score   = 50.0
    signals = []

    # 1 Yıllık getiri (en önemli)
    if r.return_1y is not None:
        if r.return_1y > 50:
            score += 20; signals.append(f"1Y getiri: %{r.return_1y:.1f} → Olağanüstü")
        elif r.return_1y > 25:
            score += 12; signals.append(f"1Y getiri: %{r.return_1y:.1f} → Güçlü")
        elif r.return_1y > 10:
            score += 6;  signals.append(f"1Y getiri: %{r.return_1y:.1f} → İyi")
        elif r.return_1y > 0:
            score += 2;  signals.append(f"1Y getiri: %{r.return_1y:.1f} → Pozitif")
        elif r.return_1y > -10:
            score -= 8;  signals.append(f"1Y getiri: %{r.return_1y:.1f} → Negatif")
        else:
            score -= 18; signals.append(f"1Y getiri: %{r.return_1y:.1f} → Zayıf")

    # 3 Aylık momentum
    if r.return_3m is not None:
        if r.return_3m > 15:
            score += 10; signals.append(f"3A momentum: %{r.return_3m:.1f} → Güçlü")
        elif r.return_3m > 5:
            score += 5;  signals.append(f"3A momentum: %{r.return_3m:.1f} → Pozitif")
        elif r.return_3m < -10:
            score -= 10; signals.append(f"3A momentum: %{r.return_3m:.1f} → Zayıf")

    # Sharpe oranı (risk-adjusted return)
    if r.sharpe is not None:
        if r.sharpe > 2.0:
            score += 15; signals.append(f"Sharpe: {r.sharpe:.2f} → Mükemmel risk/getiri")
        elif r.sharpe > 1.0:
            score += 8;  signals.append(f"Sharpe: {r.sharpe:.2f} → İyi risk/getiri")
        elif r.sharpe > 0:
            score += 3;  signals.append(f"Sharpe: {r.sharpe:.2f} → Kabul edilebilir")
        else:
            score -= 12; signals.append(f"Sharpe: {r.sharpe:.2f} → Risk karşılıksız")

    # Max Drawdown (risk)
    if r.max_drawdown is not None:
        if r.max_drawdown > -5:
            score += 8;  signals.append(f"Max DD: %{r.max_drawdown:.1f} → Düşük risk")
        elif r.max_drawdown > -15:
            score += 3;  signals.append(f"Max DD: %{r.max_drawdown:.1f} → Orta risk")
        elif r.max_drawdown > -30:
            score -= 5;  signals.append(f"Max DD: %{r.max_drawdown:.1f} → Yüksek risk")
        else:
            score -= 12; signals.append(f"Max DD: %{r.max_drawdown:.1f} → Çok yüksek risk!")

    # Volatilite
    if r.volatility is not None:
        if r.volatility < 10:
            signals.append(f"Volatilite: %{r.volatility:.1f} → Düşük (istikrarlı)")
        elif r.volatility > 40:
            score -= 5
            signals.append(f"Volatilite: %{r.volatility:.1f} → Çok yüksek (dikkat)")

    # Kısa vadeli trend (1m vs 3m)
    if r.return_1m and r.return_3m:
        monthly_avg = r.return_3m / 3
        if r.return_1m > monthly_avg * 1.5:
            score += 5; signals.append("Momentum ivmeleniyor → son ay güçlü")
        elif r.return_1m < monthly_avg * 0.3:
            score -= 5; signals.append("Momentum zayıflıyor → son ay düşük")

    score = round(max(0, min(100, score)), 1)

    if score >= 75:   rating = "GÜÇLÜ AL"
    elif score >= 62: rating = "AL"
    elif score >= 42: rating = "NÖTR"
    elif score >= 30: rating = "SAT"
    else:             rating = "GÜÇLÜ SAT"

    return score, rating, signals


def _build_summary(r: FundResult) -> str:
    parts = []
    if r.return_1y is not None:
        parts.append(f"1Y: %{r.return_1y:+.1f}")
    if r.return_3m is not None:
        parts.append(f"3A: %{r.return_3m:+.1f}")
    if r.sharpe is not None:
        parts.append(f"Sharpe: {r.sharpe:.2f}")
    if r.max_drawdown is not None:
        parts.append(f"MaxDD: %{r.max_drawdown:.1f}")
    return "  |  ".join(parts)


def compare_funds(results: list[FundResult]) -> pd.DataFrame:
    """Birden fazla fonu karşılaştırma tablosu olarak döndür."""
    rows = []
    for r in results:
        rows.append({
            "Kod/Ticker":  r.code,
            "Fon Adı":    r.name[:35],
            "Tür":        r.fund_type,
            "Puan":       r.score,
            "Rating":     r.rating,
            "1G %":       r.return_1d,
            "1H %":       r.return_1w,
            "1A %":       r.return_1m,
            "3A %":       r.return_3m,
            "1Y %":       r.return_1y,
            "Sharpe":     r.sharpe,
            "Max DD %":   r.max_drawdown,
            "Volatilite": r.volatility,
        })
    df = pd.DataFrame(rows)
    if "Puan" in df.columns:
        df = df.sort_values("Puan", ascending=False)
    return df.reset_index(drop=True)
