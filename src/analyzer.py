"""
HedgeFund AI — Analyzer
Computes technical indicators, fundamental scores, sentiment & macro signals.
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TechnicalResult:
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_pct: Optional[float] = None          # position within bands 0-1
    volume_ratio: Optional[float] = None    # current vol / 20d avg vol
    price: Optional[float] = None
    trend: str = "UNKNOWN"                  # UPTREND / DOWNTREND / SIDEWAYS
    breakout: bool = False
    score: float = 50.0                     # 0-100 bullish score
    signals: list = field(default_factory=list)


@dataclass
class FundamentalResult:
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    revenue_growth: Optional[float] = None
    debt_equity: Optional[float] = None
    score: float = 50.0
    signals: list = field(default_factory=list)


@dataclass
class SentimentResult:
    score: float = 50.0                     # 0=extreme fear, 100=extreme greed
    label: str = "NEUTRAL"
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    hype_score: float = 0.0
    signals: list = field(default_factory=list)


@dataclass
class OnChainResult:
    net_flow: Optional[float] = None
    whale_activity: str = "NORMAL"
    sopr: Optional[float] = None
    mvrv_z: Optional[float] = None
    score: float = 50.0
    signals: list = field(default_factory=list)


# ── Technical Analysis ────────────────────────────────────────────────────────

class TechnicalAnalyzer:

    def analyze(self, df: pd.DataFrame, cfg: dict) -> TechnicalResult:
        r = TechnicalResult()
        if df is None or len(df) < 50:
            logger.warning("Insufficient data for technical analysis")
            return r

        close = df["close"].astype(float)
        high  = df["high"].astype(float)
        low   = df["low"].astype(float)
        vol   = df["volume"].astype(float)

        r.price = round(float(close.iloc[-1]), 6)

        # RSI
        r.rsi = self._rsi(close, cfg.get("rsi_period", 14))

        # MACD
        r.macd, r.macd_signal, r.macd_histogram = self._macd(
            close,
            cfg.get("macd_fast", 12),
            cfg.get("macd_slow", 26),
            cfg.get("macd_signal", 9),
        )

        # EMAs
        for p in cfg.get("ema_periods", [20, 50, 200]):
            val = round(float(close.ewm(span=p, adjust=False).mean().iloc[-1]), 6)
            setattr(r, f"ema{p}", val)

        # Bollinger Bands
        bb_p = cfg.get("bb_period", 20)
        bb_std = cfg.get("bb_std", 2)
        sma = close.rolling(bb_p).mean()
        std = close.rolling(bb_p).std()
        r.bb_upper  = round(float((sma + bb_std * std).iloc[-1]), 6)
        r.bb_middle = round(float(sma.iloc[-1]), 6)
        r.bb_lower  = round(float((sma - bb_std * std).iloc[-1]), 6)
        if r.bb_upper != r.bb_lower:
            r.bb_pct = round((r.price - r.bb_lower) / (r.bb_upper - r.bb_lower), 4)

        # Volume ratio
        vol_avg = float(vol.rolling(20).mean().iloc[-1])
        if vol_avg > 0:
            r.volume_ratio = round(float(vol.iloc[-1]) / vol_avg, 2)

        # Trend
        r.trend = self._determine_trend(r)

        # Breakout detection
        resistance = float(high.rolling(20).max().iloc[-2])  # prior period high
        r.breakout = r.price > resistance * 1.005

        # Score & signals
        r.score, r.signals = self._score(r, cfg)
        return r

    def _rsi(self, close: pd.Series, period: int) -> float:
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 2)

    def _macd(self, close: pd.Series, fast: int, slow: int, sig: int):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd     = ema_fast - ema_slow
        signal   = macd.ewm(span=sig, adjust=False).mean()
        hist     = macd - signal
        return (
            round(float(macd.iloc[-1]), 6),
            round(float(signal.iloc[-1]), 6),
            round(float(hist.iloc[-1]), 6),
        )

    def _determine_trend(self, r: TechnicalResult) -> str:
        price = r.price
        bullish = 0
        if r.ema20 and price > r.ema20: bullish += 1
        if r.ema50 and price > r.ema50: bullish += 1
        if r.ema200 and price > r.ema200: bullish += 1
        if bullish >= 3: return "UPTREND"
        if bullish == 0: return "DOWNTREND"
        return "SIDEWAYS"

    def _score(self, r: TechnicalResult, cfg: dict) -> tuple[float, list]:
        score   = 50.0
        signals = []

        ob = cfg.get("rsi_overbought", 70)
        os = cfg.get("rsi_oversold", 30)
        if r.rsi is not None:
            if r.rsi < os:
                score += 15; signals.append(f"RSI={r.rsi:.1f} → Oversold (BUY signal)")
            elif r.rsi > ob:
                score -= 15; signals.append(f"RSI={r.rsi:.1f} → Overbought (SELL signal)")
            elif r.rsi > 50:
                score += 5;  signals.append(f"RSI={r.rsi:.1f} → Bullish momentum")
            else:
                score -= 5;  signals.append(f"RSI={r.rsi:.1f} → Bearish momentum")

        if r.macd_histogram is not None:
            if r.macd_histogram > 0 and r.macd > r.macd_signal:
                score += 10; signals.append("MACD → Bullish crossover")
            elif r.macd_histogram < 0:
                score -= 10; signals.append("MACD → Bearish crossover")

        if r.trend == "UPTREND":
            score += 10; signals.append("EMA stack → Uptrend confirmed")
        elif r.trend == "DOWNTREND":
            score -= 10; signals.append("EMA stack → Downtrend confirmed")

        if r.bb_pct is not None:
            if r.bb_pct < 0.1:
                score += 8; signals.append("Bollinger → Near lower band (potential bounce)")
            elif r.bb_pct > 0.9:
                score -= 8; signals.append("Bollinger → Near upper band (potential reversal)")

        if r.volume_ratio is not None:
            vm = cfg.get("volume_spike_multiplier", 2.5)
            if r.volume_ratio > vm:
                signals.append(f"Volume spike: {r.volume_ratio:.1f}x average (watch direction)")
                if r.trend == "UPTREND": score += 5
                else: score -= 5

        if r.breakout:
            score += 12; signals.append("Breakout above 20-period resistance")

        return round(max(0, min(100, score)), 1), signals


# ── Fundamental Analysis ──────────────────────────────────────────────────────

class FundamentalAnalyzer:

    def analyze(self, data: dict) -> FundamentalResult:
        r = FundamentalResult()
        if not data or data.get("source") == "unavailable":
            r.signals.append("Fundamental data unavailable")
            return r

        r.pe_ratio       = data.get("pe_ratio")
        r.peg_ratio      = data.get("peg_ratio")
        r.roe            = data.get("roe")
        r.roic           = data.get("roic")
        r.revenue_growth = data.get("revenue_growth")
        r.debt_equity    = data.get("debt_equity")

        score = 50.0
        sigs  = []

        # P/E
        if r.pe_ratio is not None:
            if r.pe_ratio < 15:
                score += 12; sigs.append(f"P/E={r.pe_ratio:.1f} → Undervalued vs market avg")
            elif r.pe_ratio < 25:
                score += 5;  sigs.append(f"P/E={r.pe_ratio:.1f} → Fair valuation")
            elif r.pe_ratio > 40:
                score -= 12; sigs.append(f"P/E={r.pe_ratio:.1f} → Expensive, growth must justify")

        # PEG
        if r.peg_ratio is not None:
            if r.peg_ratio < 1:
                score += 10; sigs.append(f"PEG={r.peg_ratio:.2f} → Growth underpriced")
            elif r.peg_ratio > 2:
                score -= 8;  sigs.append(f"PEG={r.peg_ratio:.2f} → Growth overpriced")

        # ROE
        if r.roe is not None:
            roe_pct = r.roe * 100 if r.roe < 2 else r.roe
            if roe_pct > 20:
                score += 10; sigs.append(f"ROE={roe_pct:.1f}% → Excellent capital efficiency")
            elif roe_pct < 5:
                score -= 8;  sigs.append(f"ROE={roe_pct:.1f}% → Poor capital efficiency")

        # Revenue growth
        if r.revenue_growth is not None:
            rg_pct = r.revenue_growth * 100 if r.revenue_growth < 2 else r.revenue_growth
            if rg_pct > 20:
                score += 10; sigs.append(f"Revenue growth={rg_pct:.1f}% → Strong topline")
            elif rg_pct < 0:
                score -= 12; sigs.append(f"Revenue growth={rg_pct:.1f}% → Shrinking revenues")

        # Debt/Equity
        if r.debt_equity is not None:
            de = r.debt_equity / 100 if r.debt_equity > 10 else r.debt_equity
            if de > 2:
                score -= 8; sigs.append(f"D/E={de:.2f} → High leverage risk")
            elif de < 0.5:
                score += 5; sigs.append(f"D/E={de:.2f} → Conservative balance sheet")

        r.score   = round(max(0, min(100, score)), 1)
        r.signals = sigs
        return r


# ── Sentiment Analysis ────────────────────────────────────────────────────────

POSITIVE_WORDS = {
    "surge", "soar", "rally", "breakout", "bullish", "beat", "exceed",
    "growth", "profit", "upgrade", "buy", "strong", "momentum", "record",
    "all-time high", "outperform", "positive", "gain", "jump",
}
NEGATIVE_WORDS = {
    "crash", "plunge", "drop", "bearish", "miss", "loss", "downgrade",
    "sell", "risk", "concern", "fear", "weak", "decline", "recession",
    "default", "crisis", "warning", "cut", "fall", "tumble",
}


class SentimentAnalyzer:

    def analyze(self, articles: list[dict]) -> SentimentResult:
        r = SentimentResult()
        if not articles:
            r.signals.append("No news data available")
            return r

        scores = []
        for a in articles:
            text = (
                (a.get("title") or "") + " " + (a.get("description") or "")
            ).lower()

            hint = a.get("sentiment_hint", "")
            if hint == "positive":
                label = "positive"
            elif hint == "negative":
                label = "negative"
            else:
                pos = sum(1 for w in POSITIVE_WORDS if w in text)
                neg = sum(1 for w in NEGATIVE_WORDS if w in text)
                if pos > neg:   label = "positive"
                elif neg > pos: label = "negative"
                else:           label = "neutral"

            if label == "positive":
                r.positive_count += 1; scores.append(70)
            elif label == "negative":
                r.negative_count += 1; scores.append(30)
            else:
                r.neutral_count  += 1; scores.append(50)

        r.score    = round(float(np.mean(scores)), 1) if scores else 50.0
        r.hype_score = round(r.positive_count / max(len(articles), 1) * 100, 1)

        if r.score >= 65:
            r.label = "BULLISH"
            r.signals.append(f"Sentiment: {r.positive_count}/{len(articles)} positive articles")
        elif r.score <= 35:
            r.label = "BEARISH"
            r.signals.append(f"Sentiment: {r.negative_count}/{len(articles)} negative articles")
        else:
            r.label = "NEUTRAL"
            r.signals.append("Sentiment: Mixed news flow")

        return r


# ── On-Chain Analysis ─────────────────────────────────────────────────────────

class OnChainAnalyzer:

    def analyze(self, data: dict) -> OnChainResult:
        r = OnChainResult()
        if not data:
            return r

        r.net_flow = data.get("net_flow")
        r.sopr     = data.get("sopr")
        r.mvrv_z   = data.get("mvrv_z_score")
        whales     = data.get("whale_transactions", 0)

        score = 50.0
        sigs  = []

        # Net flow (negative = accumulation = bullish)
        if r.net_flow is not None:
            if r.net_flow < -5000:
                score += 12; sigs.append(f"Net outflow {r.net_flow:,.0f} → Coins leaving exchanges (bullish)")
            elif r.net_flow > 5000:
                score -= 12; sigs.append(f"Net inflow {r.net_flow:,.0f} → Coins entering exchanges (bearish)")

        # Whale activity
        if whales > 80:
            r.whale_activity = "HIGH"
            sigs.append(f"Whale txs: {whales} (elevated — watch direction)")
        else:
            r.whale_activity = "NORMAL"

        # SOPR (Spent Output Profit Ratio)
        if r.sopr is not None:
            if r.sopr > 1.02:
                score -= 8; sigs.append(f"SOPR={r.sopr} → Holders taking profit (distribution)")
            elif r.sopr < 0.99:
                score += 8; sigs.append(f"SOPR={r.sopr} → Capitulation / accumulation zone")

        # MVRV Z-Score
        if r.mvrv_z is not None:
            if r.mvrv_z > 7:
                score -= 20; sigs.append(f"MVRV Z={r.mvrv_z} → Extreme overvaluation (sell zone)")
            elif r.mvrv_z < 0:
                score += 20; sigs.append(f"MVRV Z={r.mvrv_z} → Historic undervaluation (buy zone)")
            elif r.mvrv_z < 2:
                score += 8;  sigs.append(f"MVRV Z={r.mvrv_z} → Fair-to-cheap valuation")

        r.score   = round(max(0, min(100, score)), 1)
        r.signals = sigs
        return r
