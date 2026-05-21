"""
HedgeFund AI — Decision Engine
Aggregates all analysis signals into a structured BUY/SELL/HOLD decision
with confidence score, entry/SL/TP levels and scenario analysis.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .analyzer import TechnicalResult, FundamentalResult, SentimentResult, OnChainResult

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    symbol: str
    asset_type: str                         # crypto | stock | bist
    action: str = "HOLD"                    # BUY | SELL | HOLD
    confidence: float = 0.0                 # 0-100
    price: Optional[float] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None

    # Composite scores
    tech_score:  float = 50.0
    fund_score:  float = 50.0
    sent_score:  float = 50.0
    macro_score: float = 50.0
    chain_score: float = 50.0
    composite:   float = 50.0

    # Narrative
    why_enter:   str = ""
    why_exit:    str = ""
    risk_event:  str = ""

    # Scenarios
    base_scenario:       str = ""
    risk_scenario:       str = ""
    black_swan_scenario: str = ""

    # All signals combined
    all_signals: list = field(default_factory=list)


class DecisionEngine:

    def __init__(self, cfg: dict):
        self.weights = cfg.get("decision_weights", {
            "technical":   0.40,
            "fundamental": 0.25,
            "sentiment":   0.20,
            "macro":       0.10,
            "onchain":     0.05,
        })
        self.risk_cfg = cfg.get("risk", {})

    def decide(
        self,
        symbol: str,
        asset_type: str,
        tech: TechnicalResult,
        fund: FundamentalResult,
        sent: SentimentResult,
        chain: OnChainResult,
        macro: dict,
    ) -> Decision:

        d = Decision(symbol=symbol, asset_type=asset_type)
        d.price = tech.price

        # ── Macro score ───────────────────────────────────────────────────────
        macro_score = self._macro_score(macro)

        # ── Composite weighted score ──────────────────────────────────────────
        weights = self.weights.copy()
        if asset_type != "crypto":
            # Redistribute on-chain weight to fundamental for stocks
            weights["fundamental"] = weights.get("fundamental", 0.25) + weights.pop("onchain", 0.05)

        composite = (
            tech.score  * weights.get("technical",   0.40) +
            fund.score  * weights.get("fundamental", 0.25) +
            sent.score  * weights.get("sentiment",   0.20) +
            macro_score * weights.get("macro",       0.10) +
            chain.score * weights.get("onchain",     0.05)
        )

        d.tech_score  = tech.score
        d.fund_score  = fund.score
        d.sent_score  = sent.score
        d.macro_score = macro_score
        d.chain_score = chain.score
        d.composite   = round(composite, 1)

        # ── All signals ───────────────────────────────────────────────────────
        d.all_signals = (
            tech.signals + fund.signals + sent.signals + chain.signals
        )

        # ── Action & confidence ───────────────────────────────────────────────
        if composite >= 65:
            d.action     = "BUY"
            d.confidence = round(min(95, (composite - 65) / 35 * 100 + 50), 1)
        elif composite <= 38:
            d.action     = "SELL"
            d.confidence = round(min(95, (38 - composite) / 38 * 100 + 50), 1)
        else:
            d.action     = "HOLD"
            d.confidence = round(40 + abs(composite - 50) * 2, 1)

        # ── Price levels ──────────────────────────────────────────────────────
        if d.price:
            d.entry = d.price  # market order at current price

            sl_pct  = self.risk_cfg.get("default_stop_loss_pct", 5.0)
            tp_pcts = self.risk_cfg.get("take_profit_levels", [8.0, 15.0, 25.0])

            if d.action == "BUY":
                d.stop_loss     = round(d.price * (1 - sl_pct  / 100), 6)
                d.take_profit_1 = round(d.price * (1 + tp_pcts[0] / 100), 6)
                d.take_profit_2 = round(d.price * (1 + tp_pcts[1] / 100), 6)
                d.take_profit_3 = round(d.price * (1 + tp_pcts[2] / 100), 6)
            elif d.action == "SELL":
                d.stop_loss     = round(d.price * (1 + sl_pct  / 100), 6)
                d.take_profit_1 = round(d.price * (1 - tp_pcts[0] / 100), 6)
                d.take_profit_2 = round(d.price * (1 - tp_pcts[1] / 100), 6)
                d.take_profit_3 = round(d.price * (1 - tp_pcts[2] / 100), 6)

        # ── Narrative ─────────────────────────────────────────────────────────
        d.why_enter, d.why_exit, d.risk_event = self._narratives(d, tech, sent, macro)

        # ── Scenarios ─────────────────────────────────────────────────────────
        d.base_scenario, d.risk_scenario, d.black_swan_scenario = (
            self._scenarios(d, macro)
        )

        return d

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _macro_score(self, macro: dict) -> float:
        score = 50.0
        vix = macro.get("VIX", {}).get("current")
        if vix:
            if vix < 15:   score += 10
            elif vix > 30: score -= 20
            elif vix > 20: score -= 8

        dxy = macro.get("DXY", {}).get("change_1d")
        if dxy is not None:
            if dxy > 0.5:  score -= 5   # strong dollar hurts risk assets
            elif dxy < -0.5: score += 5

        tnx = macro.get("10Y", {}).get("current")
        if tnx:
            if tnx > 5.0: score -= 10   # high rates = risk-off
            elif tnx < 3.5: score += 5

        return round(max(0, min(100, score)), 1)

    def _narratives(
        self, d: Decision, tech: TechnicalResult,
        sent: SentimentResult, macro: dict
    ) -> tuple[str, str, str]:

        vix = macro.get("VIX", {}).get("current", "?")

        if d.action == "BUY":
            why_enter = (
                f"Composite score {d.composite}/100 with {d.action} signal. "
                f"Technical trend is {tech.trend}, RSI={tech.rsi} (not overbought). "
                f"Sentiment is {sent.label} ({sent.score:.0f}/100). "
                f"VIX at {vix} — macro backdrop {'supportive' if (isinstance(vix,float) and vix < 20) else 'neutral'}."
            )
            why_exit = (
                f"Exit if price breaks below stop-loss {d.stop_loss} "
                f"OR RSI climbs above 75 without fundamental improvement "
                f"OR composite score drops below 40."
            )
        elif d.action == "SELL":
            why_enter = (
                f"Composite score {d.composite}/100 suggests distribution. "
                f"Technical trend is {tech.trend}, RSI={tech.rsi}. "
                f"Sentiment is {sent.label}. "
                f"Consider reducing exposure or opening short with defined risk."
            )
            why_exit = (
                f"Cover short if price reclaims {d.stop_loss} "
                f"OR RSI falls below 30 (potential reversal) "
                f"OR strong positive catalyst emerges."
            )
        else:
            why_enter = (
                f"Mixed signals — composite {d.composite}/100 is in neutral zone. "
                f"Wait for clearer technical confirmation (breakout or breakdown). "
                f"Current trend: {tech.trend}."
            )
            why_exit = "No position open. Monitor for composite moving above 65 or below 38."

        risk_event = (
            "Key risks: Fed rate decision, CPI surprise, "
            "earnings miss, geopolitical escalation, "
            "flash crash / liquidity crunch."
        )

        return why_enter, why_exit, risk_event

    def _scenarios(self, d: Decision, macro: dict) -> tuple[str, str, str]:
        sym = d.symbol

        tp1_str = _fmt_level(d.take_profit_1)
        sl_str  = _fmt_level(d.stop_loss)

        base = (
            f"{sym} follows composite score trajectory. "
            f"{'TP1=' + tp1_str + ' is primary target over 2-4 weeks.' if d.action != 'HOLD' else 'Wait for composite to break above 65 or below 38 before entering.'} "
            f"Macro backdrop remains stable."
        )
        risk = (
            f"Fed turns hawkish or CPI comes in hot → VIX spikes above 25 → "
            f"risk-off across all assets. {sym} "
            f"{'tests stop-loss at ' + sl_str if d.action != 'HOLD' else 'could see increased volatility'}. "
            f"Position sizing should account for this correlation."
        )
        black_swan = (
            f"Tail-risk event (exchange hack, regulatory ban, sovereign default, "
            f"unexpected war escalation) → {sym} could drop 30-50%+ rapidly. "
            f"Never risk more than 2% of portfolio on a single position. "
            f"Keep hard stop in place — emotions won't save you, rules will."
        )

        return base, risk, black_swan


def _fmt_level(val) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
        return f"{v:,.2f}" if v >= 1 else f"{v:.6f}"
    except Exception:
        return str(val)
