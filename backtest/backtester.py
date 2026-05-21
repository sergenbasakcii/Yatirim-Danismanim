"""
HedgeFund AI — Backtester
Simulates strategy performance on historical data.
Supports: simple composite-threshold strategy, commission, slippage.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

import sys
if getattr(sys, "frozen", False):
    CONFIG_PATH = Path(sys.executable).parent / "config" / "settings.yaml"
else:
    CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_cfg() -> dict:
    from src.config_loader import load_settings
    return load_settings(CONFIG_PATH)


@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_capital: float
    final_capital: float
    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    equity_curve: pd.Series = field(default_factory=pd.Series)
    trades_log: pd.DataFrame = field(default_factory=pd.DataFrame)


class Backtester:
    """
    Strategy logic:
      - Compute RSI + MACD + EMA-trend on rolling window
      - BUY signal  : RSI < 35 AND MACD histogram > 0 AND price > EMA50
      - SELL signal : RSI > 70 OR price < EMA50 * 0.97  (trailing stop equivalent)
      - Commission  : settings.yaml backtest.commission_pct per side
    """

    def __init__(self):
        self.cfg = _load_cfg()
        self.bt_cfg = self.cfg.get("backtest", {})
        self.tech_cfg = self.cfg.get("technical", {})

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        initial_capital: Optional[float] = None,
    ) -> BacktestResult:

        start = start or self.bt_cfg.get("default_start", "2023-01-01")
        end   = end   or self.bt_cfg.get("default_end",   "2024-12-31")
        cap   = initial_capital or float(self.bt_cfg.get("initial_capital", 100_000))
        commission = float(self.bt_cfg.get("commission_pct", 0.1)) / 100

        # Slice date range
        df = df.copy()
        if isinstance(df.index, pd.DatetimeIndex):
            df = df[start:end]
        if len(df) < 60:
            logger.warning(f"Not enough data for backtest of {symbol} ({len(df)} rows)")
            return BacktestResult(symbol=symbol, start=start, end=end,
                                  initial_capital=cap, final_capital=cap)

        close = df["close"].astype(float).reset_index(drop=True)

        # ── Indicators ────────────────────────────────────────────────────────
        rsi_period = self.tech_cfg.get("rsi_period", 14)
        rsi = self._rsi(close, rsi_period)

        fast = self.tech_cfg.get("macd_fast", 12)
        slow = self.tech_cfg.get("macd_slow", 26)
        sig  = self.tech_cfg.get("macd_signal", 9)
        _, _, macd_hist = self._macd(close, fast, slow, sig)

        ema50  = close.ewm(span=50,  adjust=False).mean()
        ema200 = close.ewm(span=200, adjust=False).mean()

        # ── Simulation ────────────────────────────────────────────────────────
        cash       = cap
        position   = 0.0        # units held
        equity     = []
        trades     = []
        entry_price = 0.0

        for i in range(200, len(close)):
            price = close.iloc[i]
            equity_val = cash + position * price
            equity.append(equity_val)

            if position == 0:
                # BUY condition
                if (rsi.iloc[i] < 35 and
                        macd_hist.iloc[i] > 0 and
                        price > ema50.iloc[i]):
                    units = (cash * 0.95) / (price * (1 + commission))
                    if units > 0:
                        cost        = units * price * (1 + commission)
                        cash       -= cost
                        position    = units
                        entry_price = price
                        trades.append({
                            "date":   i,
                            "action": "BUY",
                            "price":  round(price, 6),
                            "units":  round(units, 6),
                            "value":  round(cost, 2),
                        })
            else:
                # SELL condition
                trailing_stop = entry_price * 0.93
                if (rsi.iloc[i] > 70 or
                        price < ema50.iloc[i] * 0.97 or
                        price < trailing_stop):
                    proceeds   = position * price * (1 - commission)
                    pnl_pct    = (price - entry_price) / entry_price * 100
                    cash      += proceeds
                    trades.append({
                        "date":    i,
                        "action":  "SELL",
                        "price":   round(price, 6),
                        "units":   round(position, 6),
                        "value":   round(proceeds, 2),
                        "pnl_pct": round(pnl_pct, 2),
                    })
                    position    = 0.0
                    entry_price = 0.0

        # Close any open position at last price
        if position > 0:
            price     = close.iloc[-1]
            proceeds  = position * price * (1 - commission)
            pnl_pct   = (price - entry_price) / entry_price * 100
            cash     += proceeds
            trades.append({
                "date": len(close)-1, "action": "SELL (close)",
                "price": round(price, 6), "units": round(position, 6),
                "value": round(proceeds, 2), "pnl_pct": round(pnl_pct, 2),
            })
            equity[-1] = cash

        equity_s  = pd.Series(equity)
        final_cap = cash

        # ── Metrics ───────────────────────────────────────────────────────────
        total_return = (final_cap - cap) / cap * 100
        n_days       = len(equity_s)
        n_years      = max(n_days / 252, 0.01)
        annual_ret   = ((final_cap / cap) ** (1 / n_years) - 1) * 100

        # Max drawdown
        roll_max = equity_s.cummax()
        dd       = (equity_s - roll_max) / roll_max
        max_dd   = float(dd.min() * 100)

        # Sharpe / Sortino (annualised, rf=0)
        daily_ret = equity_s.pct_change().dropna()
        sharpe    = 0.0
        sortino   = 0.0
        if daily_ret.std() > 0:
            sharpe  = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        neg = daily_ret[daily_ret < 0]
        if len(neg) > 0 and neg.std() > 0:
            sortino = float(daily_ret.mean() / neg.std() * np.sqrt(252))

        # Trade stats
        sell_trades = [t for t in trades if "SELL" in t.get("action", "")]
        wins   = [t for t in sell_trades if t.get("pnl_pct", 0) > 0]
        losses = [t for t in sell_trades if t.get("pnl_pct", 0) <= 0]
        win_rate   = len(wins) / max(len(sell_trades), 1) * 100
        avg_win    = float(np.mean([t["pnl_pct"] for t in wins]))    if wins   else 0
        avg_loss   = float(np.mean([t["pnl_pct"] for t in losses]))  if losses else 0
        gross_win  = sum(t["pnl_pct"] for t in wins)
        gross_loss = abs(sum(t["pnl_pct"] for t in losses))
        pf         = gross_win / gross_loss if gross_loss > 0 else float("inf")

        return BacktestResult(
            symbol=symbol, start=start, end=end,
            initial_capital=cap,
            final_capital=round(final_cap, 2),
            total_return_pct=round(total_return, 2),
            annual_return_pct=round(annual_ret, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            win_rate_pct=round(win_rate, 1),
            total_trades=len(sell_trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win_pct=round(avg_win, 2),
            avg_loss_pct=round(avg_loss, 2),
            profit_factor=round(pf, 2),
            equity_curve=equity_s,
            trades_log=pd.DataFrame(trades),
        )

    # ── Indicator helpers ─────────────────────────────────────────────────────

    def _rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(period).mean()
        loss  = (-delta.clip(upper=0)).rolling(period).mean()
        rs    = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _macd(self, close: pd.Series, fast: int, slow: int, sig: int):
        ef   = close.ewm(span=fast, adjust=False).mean()
        es   = close.ewm(span=slow, adjust=False).mean()
        macd = ef - es
        signal = macd.ewm(span=sig, adjust=False).mean()
        return macd, signal, macd - signal

    def format_report(self, r: BacktestResult) -> str:
        lines = [
            f"\n{'═'*58}",
            f"  BACKTEST REPORT — {r.symbol}",
            f"  Period : {r.start}  →  {r.end}",
            f"{'═'*58}",
            f"  Initial Capital   : ${r.initial_capital:>12,.2f}",
            f"  Final Capital     : ${r.final_capital:>12,.2f}",
            f"  Total Return      : {r.total_return_pct:>+8.2f}%",
            f"  Annualised Return : {r.annual_return_pct:>+8.2f}%",
            f"  Max Drawdown      : {r.max_drawdown_pct:>8.2f}%",
            f"  Sharpe Ratio      : {r.sharpe_ratio:>8.3f}",
            f"  Sortino Ratio     : {r.sortino_ratio:>8.3f}",
            f"{'─'*58}",
            f"  Total Trades      : {r.total_trades}",
            f"  Win Rate          : {r.win_rate_pct:.1f}%  "
            f"({r.winning_trades}W / {r.losing_trades}L)",
            f"  Avg Win           : {r.avg_win_pct:>+.2f}%",
            f"  Avg Loss          : {r.avg_loss_pct:>+.2f}%",
            f"  Profit Factor     : {r.profit_factor:.2f}",
            f"{'═'*58}",
        ]
        return "\n".join(lines)


class __init_module__:
    pass
