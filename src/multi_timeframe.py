"""
HedgeFund AI — Multi-Timeframe (MTF) Analiz
1D + 4H + 1H verisi çekip aynı teknik analizi 3 timeframe'de uygular.
Tüm timeframe'ler aynı yönü gösteriyorsa → güçlü sinyal.

"Triple Screen" metodolojisi (Elder):
  1D  = trend yönü (büyük resim)
  4H  = giriş zamanlaması
  1H  = hassas giriş
"""

import logging
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MTFResult:
    symbol:        str
    tf_1d_score:   float = 50.0
    tf_4h_score:   float = 50.0
    tf_1h_score:   float = 50.0
    tf_1d_trend:   str = "UNKNOWN"
    tf_4h_trend:   str = "UNKNOWN"
    tf_1h_trend:   str = "UNKNOWN"
    tf_1d_rsi:     float = 50.0
    tf_4h_rsi:     float = 50.0
    tf_1h_rsi:     float = 50.0
    composite:     float = 50.0
    agreement:     str = "MIXED"     # STRONG_BUY / STRONG_SELL / MIXED
    confidence_boost: float = 0.0   # extra confidence added to decision
    signals:       list = field(default_factory=list)


class MultiTimeframeAnalyzer:

    WEIGHTS = {"1d": 0.50, "4h": 0.30, "1h": 0.20}

    def analyze(self, symbol: str) -> MTFResult:
        r = MTFResult(symbol=symbol)

        dfs = {}
        for tf in ["1d", "4h", "1h"]:
            df = self._fetch(symbol, tf)
            if df is not None and len(df) >= 50:
                dfs[tf] = df

        if not dfs:
            r.signals.append("MTF: Yetersiz veri")
            return r

        scores = {}
        for tf, df in dfs.items():
            score, trend, rsi = self._score_tf(df)
            scores[tf] = score
            setattr(r, f"tf_{tf.replace('h','h')}_score", score)
            setattr(r, f"tf_{tf.replace('h','h')}_trend", trend)
            setattr(r, f"tf_{tf.replace('h','h')}_rsi",   rsi)

        # Weighted composite
        total_w = sum(self.WEIGHTS[tf] for tf in scores)
        r.composite = sum(
            scores[tf] * self.WEIGHTS[tf] for tf in scores
        ) / total_w

        # Agreement
        bullish = sum(1 for s in scores.values() if s >= 60)
        bearish = sum(1 for s in scores.values() if s <= 40)
        n       = len(scores)

        if bullish == n:
            r.agreement       = "STRONG_BUY"
            r.confidence_boost = 15.0
            r.signals.append(f"MTF: Tüm {n} zaman dilimi YUKARI → güçlü BUY konfirmasyonu")
        elif bearish == n:
            r.agreement       = "STRONG_SELL"
            r.confidence_boost = 15.0
            r.signals.append(f"MTF: Tüm {n} zaman dilimi AŞAĞI → güçlü SELL konfirmasyonu")
        elif bullish > bearish:
            r.agreement       = "LEAN_BUY"
            r.confidence_boost = 5.0
            r.signals.append(f"MTF: {bullish}/{n} zaman dilimi yükseliş eğiliminde")
        elif bearish > bullish:
            r.agreement       = "LEAN_SELL"
            r.confidence_boost = 5.0
            r.signals.append(f"MTF: {bearish}/{n} zaman dilimi düşüş eğiliminde")
        else:
            r.agreement       = "MIXED"
            r.confidence_boost = -5.0
            r.signals.append("MTF: Zaman dilimleri çelişiyor → dikkatli ol")

        # Detail signals
        for tf, score in scores.items():
            trend = getattr(r, f"tf_{tf}_trend", "?")
            rsi   = getattr(r, f"tf_{tf}_rsi",   50)
            r.signals.append(
                f"MTF {tf.upper()}: skor={score:.0f}, trend={trend}, RSI={rsi:.1f}"
            )

        return r

    def _fetch(self, symbol: str, tf: str):
        try:
            from src.data_collector import fetch_crypto_ohlcv, fetch_stock_ohlcv
            if "/" in symbol:
                # ccxt timeframes: 1d, 4h, 1h
                return fetch_crypto_ohlcv(symbol, tf, limit=200)
            else:
                # yfinance intervals: 1d, 1h (no 4h directly)
                import yfinance as yf
                interval_map = {"1d": "1d", "4h": "1h", "1h": "60m"}
                period_map   = {"1d": "6mo", "4h": "60d", "1h": "7d"}
                t    = yf.Ticker(symbol)
                df   = t.history(
                    period=period_map[tf],
                    interval=interval_map[tf],
                )
                if df.empty:
                    return None
                df = df[["Open","High","Low","Close","Volume"]].rename(columns=str.lower)
                # For 4h simulation: resample 1h → 4h
                if tf == "4h" and interval_map[tf] == "1h":
                    df = df.resample("4h").agg({
                        "open":   "first",
                        "high":   "max",
                        "low":    "min",
                        "close":  "last",
                        "volume": "sum",
                    }).dropna()
                return df
        except Exception as e:
            logger.warning(f"MTF fetch failed {symbol} {tf}: {e}")
            return None

    def _score_tf(self, df: pd.DataFrame) -> tuple[float, str, float]:
        close = df["close"].astype(float)
        score = 50.0

        # RSI
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = float((100 - 100 / (1 + rs)).iloc[-1])

        if rsi < 30:   score += 15
        elif rsi > 70: score -= 15
        elif rsi > 50: score += 5
        else:          score -= 5

        # EMA trend
        ema20  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        ema50  = float(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        price  = float(close.iloc[-1])

        bull = sum([price > ema20, price > ema50, price > ema200])
        if bull == 3:
            trend = "UPTREND";   score += 10
        elif bull == 0:
            trend = "DOWNTREND"; score -= 10
        else:
            trend = "SIDEWAYS"

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd  = ema12 - ema26
        sig   = macd.ewm(span=9, adjust=False).mean()
        if float((macd - sig).iloc[-1]) > 0:
            score += 8
        else:
            score -= 8

        return round(max(0, min(100, score)), 1), trend, round(rsi, 1)
