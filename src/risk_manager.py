"""
HedgeFund AI — Risk Manager
Position sizing, drawdown control, correlation analysis, portfolio-level risk.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PositionSizing:
    symbol: str
    action: str
    portfolio_value: float
    entry_price: float
    stop_loss: float
    max_risk_pct: float = 2.0

    units: float = 0.0
    dollar_amount: float = 0.0
    risk_amount: float = 0.0
    risk_reward_1: float = 0.0   # R:R to TP1
    risk_reward_2: float = 0.0   # R:R to TP2
    kelly_fraction: float = 0.0


@dataclass
class PortfolioRisk:
    total_value: float = 100_000.0
    positions: list = field(default_factory=list)
    max_drawdown: float = 0.0
    correlation_warnings: list = field(default_factory=list)
    var_95: float = 0.0          # Value at Risk 95%
    heat: float = 0.0            # portfolio heat (% at risk)


class RiskManager:

    def __init__(self, cfg: dict):
        self.cfg = cfg.get("risk", {})

    def size_position(
        self,
        symbol: str,
        action: str,
        portfolio_value: float,
        entry: float,
        stop_loss: float,
        take_profit_1: Optional[float],
        take_profit_2: Optional[float],
        confidence: float = 50.0,
    ) -> PositionSizing:

        ps = PositionSizing(
            symbol=symbol,
            action=action,
            portfolio_value=portfolio_value,
            entry_price=entry,
            stop_loss=stop_loss,
        )

        max_risk_pct = self.cfg.get("max_portfolio_risk_pct", 2.0)
        max_pos_pct  = self.cfg.get("max_single_position_pct", 10.0)

        # Scale risk down if confidence is low
        confidence_multiplier = confidence / 100.0
        effective_risk_pct = max_risk_pct * confidence_multiplier

        ps.risk_amount = portfolio_value * (effective_risk_pct / 100)

        # No position for HOLD
        if action == "HOLD":
            return ps

        # Distance from entry to stop (per unit)
        if entry <= 0 or stop_loss <= 0:
            return ps

        if action == "BUY":
            risk_per_unit = entry - stop_loss
        else:
            risk_per_unit = stop_loss - entry

        if risk_per_unit <= 0:
            logger.warning(f"Invalid stop-loss for {symbol}: entry={entry}, sl={stop_loss}")
            return ps

        # Units = total risk / risk per unit
        raw_units    = ps.risk_amount / risk_per_unit
        max_units_by_position = (portfolio_value * max_pos_pct / 100) / entry
        ps.units        = round(min(raw_units, max_units_by_position), 6)
        ps.dollar_amount = round(ps.units * entry, 2)

        # Risk:Reward
        if take_profit_1 and action == "BUY":
            reward1 = take_profit_1 - entry
            ps.risk_reward_1 = round(reward1 / risk_per_unit, 2)
        if take_profit_2 and action == "BUY":
            reward2 = take_profit_2 - entry
            ps.risk_reward_2 = round(reward2 / risk_per_unit, 2)

        # Kelly Criterion (simplified)
        win_prob = confidence / 100
        if ps.risk_reward_1 > 0:
            kelly = win_prob - (1 - win_prob) / ps.risk_reward_1
            ps.kelly_fraction = round(max(0, kelly * 0.5), 4)  # half-Kelly for safety

        return ps

    def correlation_matrix(self, price_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Compute rolling 30d correlation across assets."""
        closes = {}
        for sym, df in price_data.items():
            if df is not None and not df.empty:
                closes[sym] = df["close"].astype(float).pct_change().dropna()

        if len(closes) < 2:
            return pd.DataFrame()

        returns = pd.DataFrame(closes)
        return returns.corr().round(3)

    def check_correlations(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.85
    ) -> list[str]:
        warnings = []
        if corr_matrix.empty:
            return warnings

        seen = set()
        for col in corr_matrix.columns:
            for idx in corr_matrix.index:
                if col == idx:
                    continue
                pair = tuple(sorted([col, idx]))
                if pair in seen:
                    continue
                seen.add(pair)
                val = corr_matrix.loc[idx, col]
                if abs(val) >= threshold:
                    warnings.append(
                        f"HIGH CORRELATION: {col} ↔ {idx} = {val:.2f} "
                        f"(diversification benefit is limited)"
                    )
        return warnings

    def portfolio_var(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> float:
        """Historical VaR."""
        if returns.empty:
            return 0.0
        return round(float(np.percentile(returns, (1 - confidence) * 100)), 4)

    def max_drawdown(self, equity_curve: pd.Series) -> float:
        if equity_curve.empty:
            return 0.0
        roll_max = equity_curve.cummax()
        dd       = (equity_curve - roll_max) / roll_max
        return round(float(dd.min() * 100), 2)

    def format_sizing_report(self, ps: PositionSizing) -> str:
        lines = [
            f"\n{'═'*55}",
            f"  POSITION SIZING — {ps.symbol}",
            f"{'═'*55}",
            f"  Action          : {ps.action}",
            f"  Portfolio Value : ${ps.portfolio_value:,.2f}",
            f"  Entry Price     : {ps.entry_price:,.6g}",
            f"  Stop-Loss       : {ps.stop_loss:,.6g}",
            f"  Max Risk Amount : ${ps.risk_amount:,.2f}",
            f"  Position Size   : {ps.units:,.6g} units",
            f"  Position Value  : ${ps.dollar_amount:,.2f}",
            f"  Risk:Reward TP1 : 1:{ps.risk_reward_1}",
            f"  Risk:Reward TP2 : 1:{ps.risk_reward_2}",
            f"  Kelly Fraction  : {ps.kelly_fraction*100:.1f}%",
            f"{'═'*55}",
        ]
        return "\n".join(lines)
