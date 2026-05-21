"""
HedgeFund AI — Report Formatter
Renders the full investment analysis as a clean terminal report
with educational notes for each indicator / decision.
"""

from datetime import datetime
from .decision_engine import Decision
from .analyzer import TechnicalResult, FundamentalResult, SentimentResult, OnChainResult
from .risk_manager import PositionSizing


DIVIDER  = "═" * 62
THIN     = "─" * 62
ARROW    = "  ▶"

ACTION_COLOR = {
    "BUY":  "🟢",
    "SELL": "🔴",
    "HOLD": "🟡",
}

CONF_BAR_LEN = 20


def _bar(score: float, length: int = 20) -> str:
    filled = int(score / 100 * length)
    return "█" * filled + "░" * (length - filled)


def _fmt_price(p) -> str:
    if p is None:
        return "—"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "—"
    if p >= 1000:
        return f"{p:,.2f}"
    if p >= 1:
        return f"{p:.4f}"
    return f"{p:.6f}"


def render_full_report(
    decision: Decision,
    tech: TechnicalResult,
    fund: FundamentalResult,
    sent: SentimentResult,
    chain: OnChainResult,
    macro: dict,
    sizing: PositionSizing,
    articles: list,
    include_educational: bool = True,
) -> str:

    now   = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "",
        DIVIDER,
        f"  🏦  HedgeFund AI  |  {decision.symbol}  |  {decision.asset_type.upper()}",
        f"  Generated : {now}",
        DIVIDER,
    ]

    # ── Main Decision ─────────────────────────────────────────────────────────
    icon = ACTION_COLOR.get(decision.action, "⚪")
    lines += [
        f"",
        f"  {icon}  DECISION  :  {decision.action}",
        f"  Confidence:  {decision.confidence:.0f}%  [{_bar(decision.confidence)}]",
        f"  Composite :  {decision.composite:.1f}/100",
        "",
    ]

    # ── Price Levels ──────────────────────────────────────────────────────────
    lines += [
        THIN,
        "  PRICE LEVELS",
        THIN,
        f"  Current Price  :  {_fmt_price(decision.price)}",
        f"  Entry          :  {_fmt_price(decision.entry)}",
        f"  Stop-Loss      :  {_fmt_price(decision.stop_loss)}",
        f"  Take-Profit 1  :  {_fmt_price(decision.take_profit_1)}   (partial exit ~33%)",
        f"  Take-Profit 2  :  {_fmt_price(decision.take_profit_2)}   (partial exit ~33%)",
        f"  Take-Profit 3  :  {_fmt_price(decision.take_profit_3)}   (trail remainder)",
        "",
    ]

    # ── Score Breakdown ───────────────────────────────────────────────────────
    lines += [
        THIN,
        "  SCORE BREAKDOWN                      (0=Bearish, 100=Bullish)",
        THIN,
        f"  Technical   {decision.tech_score:>5.1f}/100  [{_bar(decision.tech_score)}]",
        f"  Fundamental {decision.fund_score:>5.1f}/100  [{_bar(decision.fund_score)}]",
        f"  Sentiment   {decision.sent_score:>5.1f}/100  [{_bar(decision.sent_score)}]",
        f"  Macro       {decision.macro_score:>5.1f}/100  [{_bar(decision.macro_score)}]",
        f"  On-Chain    {decision.chain_score:>5.1f}/100  [{_bar(decision.chain_score)}]",
        f"  ─────────────────────────────────────────────",
        f"  COMPOSITE   {decision.composite:>5.1f}/100  [{_bar(decision.composite)}]",
        "",
    ]

    # ── Technical Detail ──────────────────────────────────────────────────────
    lines += [
        THIN,
        "  TECHNICAL INDICATORS",
        THIN,
        f"  RSI (14)        :  {tech.rsi}",
        f"  MACD            :  {tech.macd:.6g}  |  Signal: {tech.macd_signal:.6g}  |  Hist: {tech.macd_histogram:.6g}",
        f"  EMA 20          :  {_fmt_price(tech.ema20)}",
        f"  EMA 50          :  {_fmt_price(tech.ema50)}",
        f"  EMA 200         :  {_fmt_price(tech.ema200)}",
        f"  Bollinger Upper :  {_fmt_price(tech.bb_upper)}",
        f"  Bollinger Mid   :  {_fmt_price(tech.bb_middle)}",
        f"  Bollinger Lower :  {_fmt_price(tech.bb_lower)}",
        f"  BB Position     :  {(tech.bb_pct or 0)*100:.1f}%  of band",
        f"  Volume Ratio    :  {tech.volume_ratio}x  (vs 20-day avg)",
        f"  Trend           :  {tech.trend}",
        f"  Breakout        :  {'YES ✔' if tech.breakout else 'No'}",
        "",
    ]

    if include_educational:
        lines += [
            "  📚 EDU: RSI < 30 → oversold, potential reversal. RSI > 70 → overbought.",
            "  📚 EDU: MACD histogram turning positive = momentum shift to upside.",
            "  📚 EDU: Price > EMA20 > EMA50 > EMA200 = classic uptrend stack.",
            "  📚 EDU: Bollinger Band touch ≠ automatic trade. Confirm with volume.",
            "",
        ]

    # ── Fundamental Detail ────────────────────────────────────────────────────
    lines += [THIN, "  FUNDAMENTAL METRICS", THIN]
    if fund.pe_ratio:
        lines.append(f"  P/E Ratio       :  {fund.pe_ratio:.2f}")
    if fund.peg_ratio:
        lines.append(f"  PEG Ratio       :  {fund.peg_ratio:.2f}")
    if fund.roe:
        roe_pct = fund.roe * 100 if fund.roe < 2 else fund.roe
        lines.append(f"  ROE             :  {roe_pct:.1f}%")
    if fund.revenue_growth:
        rg_pct = fund.revenue_growth * 100 if fund.revenue_growth < 2 else fund.revenue_growth
        lines.append(f"  Revenue Growth  :  {rg_pct:.1f}%")
    if fund.debt_equity:
        lines.append(f"  Debt/Equity     :  {fund.debt_equity:.2f}")
    lines.append("")

    if include_educational and decision.asset_type in ("stock", "bist"):
        lines += [
            "  📚 EDU: PEG < 1 means you're paying less than growth rate → attractive.",
            "  📚 EDU: ROE > 15% = management creates value for shareholders.",
            "  📚 EDU: High D/E in rising rate environment = balance sheet risk.",
            "",
        ]

    # ── Sentiment ─────────────────────────────────────────────────────────────
    lines += [
        THIN,
        "  SENTIMENT ANALYSIS",
        THIN,
        f"  Score     :  {sent.score:.0f}/100  →  {sent.label}",
        f"  Hype Score:  {sent.hype_score:.0f}%",
        f"  Positive Articles :  {sent.positive_count}",
        f"  Negative Articles :  {sent.negative_count}",
        f"  Neutral  Articles :  {sent.neutral_count}",
        "",
    ]

    # Show up to 3 article headlines
    if articles:
        lines.append("  Latest Headlines:")
        for i, a in enumerate(articles[:3]):
            title = (a.get("title") or "")[:70]
            lines.append(f"    {i+1}. {title}")
    lines.append("")

    if include_educational:
        lines += [
            "  📚 EDU: Sentiment is a contrarian tool at extremes.",
            "  📚 EDU: Extreme greed (score > 80) = markets may be crowded.",
            "  📚 EDU: Extreme fear (score < 20) = potential capitulation bottom.",
            "",
        ]

    # ── On-Chain (crypto only) ────────────────────────────────────────────────
    if decision.asset_type == "crypto":
        lines += [
            THIN,
            "  ON-CHAIN METRICS",
            THIN,
            f"  Exchange Net Flow  :  {chain.net_flow:+,.0f}  BTC",
            f"  Whale Activity     :  {chain.whale_activity}",
            f"  SOPR               :  {chain.sopr}",
            f"  MVRV Z-Score       :  {chain.mvrv_z}",
            "",
        ]
        if include_educational:
            lines += [
                "  📚 EDU: Negative exchange flow = coins leaving exchanges = hodling = bullish.",
                "  📚 EDU: SOPR > 1 = holders in profit, may sell. SOPR < 1 = selling at loss.",
                "  📚 EDU: MVRV Z > 7 = historic sell zone. MVRV Z < 0 = historic buy zone.",
                "",
            ]

    # ── Macro ─────────────────────────────────────────────────────────────────
    lines += [THIN, "  MACRO ENVIRONMENT", THIN]
    for label, val in macro.items():
        cur = val.get("current", "?")
        chg = val.get("change_1d", 0)
        chg_str = f"  ({chg:+.2f}%)" if chg is not None else ""
        lines.append(f"  {label:<12} :  {cur}{chg_str}")
    lines.append("")

    # ── Decision Narrative ────────────────────────────────────────────────────
    lines += [
        THIN,
        "  INVESTMENT THESIS",
        THIN,
        f"  WHY ENTER:",
        *(f"    {line}" for line in _wrap(decision.why_enter, 58)),
        "",
        f"  EXIT CONDITIONS:",
        *(f"    {line}" for line in _wrap(decision.why_exit, 58)),
        "",
        f"  KEY RISK EVENT:",
        *(f"    {line}" for line in _wrap(decision.risk_event, 58)),
        "",
    ]

    # ── Scenarios ─────────────────────────────────────────────────────────────
    lines += [
        THIN,
        "  SCENARIO ANALYSIS",
        THIN,
        "  📊 BASE SCENARIO:",
        *(f"    {line}" for line in _wrap(decision.base_scenario, 58)),
        "",
        "  ⚠️  RISK SCENARIO:",
        *(f"    {line}" for line in _wrap(decision.risk_scenario, 58)),
        "",
        "  💀 BLACK SWAN:",
        *(f"    {line}" for line in _wrap(decision.black_swan_scenario, 58)),
        "",
    ]

    # ── Position Sizing ───────────────────────────────────────────────────────
    lines += [
        THIN,
        "  POSITION SIZING",
        THIN,
        f"  Portfolio Value    :  ${sizing.portfolio_value:,.2f}",
        f"  Recommended Units  :  {sizing.units:,.6g}",
        f"  Dollar Amount      :  ${sizing.dollar_amount:,.2f}",
        f"  Max Risk Amount    :  ${sizing.risk_amount:,.2f}",
        f"  Risk:Reward TP1    :  1 : {sizing.risk_reward_1}",
        f"  Risk:Reward TP2    :  1 : {sizing.risk_reward_2}",
        f"  Half-Kelly %       :  {sizing.kelly_fraction*100:.1f}%",
        "",
    ]

    if include_educational:
        lines += [
            "  📚 EDU: Never risk more than 1-2% of portfolio per trade.",
            "  📚 EDU: R:R of 1:2 means even 40% win rate is profitable.",
            "  📚 EDU: Kelly Criterion gives optimal bet size. Half-Kelly = safety margin.",
            "",
        ]

    # ── All Signals ───────────────────────────────────────────────────────────
    lines += [THIN, "  ALL SIGNALS FIRED", THIN]
    for sig in decision.all_signals:
        lines.append(f"  {ARROW} {sig}")
    lines += ["", DIVIDER, "  ⚠️  DISCLAIMER: This is an analytical tool, NOT financial advice.",
              "  Always do your own research. Past performance ≠ future results.",
              DIVIDER, ""]

    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """Simple word wrap."""
    words   = text.split()
    lines   = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= width:
            current = (current + " " + w).strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]
