"""
HedgeFund AI — Main Orchestrator
=========================================================
Usage:
  python main.py                          # analyse all watchlist assets
  python main.py --symbol BTC/USDT        # single crypto asset
  python main.py --symbol AAPL            # single stock
  python main.py --symbol THYAO.IS        # single BIST stock
  python main.py --backtest --symbol AAPL # backtest mode
  python main.py --portfolio 250000       # custom portfolio size
  python main.py --no-edu                 # skip educational notes
=========================================================
"""

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

# Force UTF-8 output on Windows so emoji / unicode renders correctly
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import yaml

# ── Setup paths ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.data_collector import (
    load_config,
    fetch_crypto_ohlcv,
    fetch_stock_ohlcv,
    fetch_fundamentals,
    fetch_macro_data,
    fetch_news,
    fetch_onchain,
)
from src.analyzer import (
    TechnicalAnalyzer,
    FundamentalAnalyzer,
    SentimentAnalyzer,
    OnChainAnalyzer,
    FundamentalResult,
    OnChainResult,
)
from src.decision_engine import DecisionEngine
from src.risk_manager import RiskManager
from src.alert_system import AlertSystem
from src.report_formatter import render_full_report
from backtest.backtester import Backtester

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "hedgefund_ai.log"),
    ],
)
logger = logging.getLogger("HedgeFundAI")

# ── Config ────────────────────────────────────────────────────────────────────
CFG = load_config()


def detect_asset_type(symbol: str) -> str:
    if "/" in symbol:
        return "crypto"
    if symbol.endswith(".IS"):
        return "bist"
    return "stock"


def run_analysis(
    symbol: str,
    asset_type: str,
    portfolio_value: float,
    include_edu: bool,
    alert_sys: AlertSystem,
    tech_analyzer: TechnicalAnalyzer,
    fund_analyzer: FundamentalAnalyzer,
    sent_analyzer: SentimentAnalyzer,
    chain_analyzer: OnChainAnalyzer,
    decision_engine: DecisionEngine,
    risk_manager: RiskManager,
    macro: dict,
) -> str:
    """Run full analysis pipeline for one symbol. Returns the rendered report."""

    logger.info(f"Analysing {symbol} [{asset_type.upper()}]")

    # 1. Fetch OHLCV
    try:
        if asset_type == "crypto":
            df = fetch_crypto_ohlcv(symbol, CFG["data"]["crypto_timeframe"])
        else:
            df = fetch_stock_ohlcv(symbol)
    except Exception as e:
        logger.error(f"OHLCV fetch failed for {symbol}: {e}")
        return f"\n[ERROR] Could not fetch price data for {symbol}: {e}\n"

    # 2. Technical analysis
    tech = tech_analyzer.analyze(df, CFG["technical"])

    # 3. Fundamentals (stocks only)
    if asset_type in ("stock", "bist"):
        fund_data = fetch_fundamentals(symbol)
        fund = fund_analyzer.analyze(fund_data)
    else:
        fund_data = {}
        fund = FundamentalResult(score=50.0, signals=["Fundamental N/A for crypto"])

    # 4. Sentiment
    news_query = symbol.replace("/USDT", "").replace(".IS", "")
    articles   = fetch_news(news_query)
    sent       = sent_analyzer.analyze(articles)

    # 5. On-chain (crypto only)
    if asset_type == "crypto":
        onchain_data = fetch_onchain(symbol.split("/")[0])
        chain = chain_analyzer.analyze(onchain_data)
    else:
        chain = OnChainResult(score=50.0, signals=["On-chain N/A for equities"])

    # 6. Decision
    decision = decision_engine.decide(
        symbol=symbol,
        asset_type=asset_type,
        tech=tech,
        fund=fund,
        sent=sent,
        chain=chain,
        macro=macro,
    )

    # 7. Position sizing
    pv = portfolio_value
    sizing = risk_manager.size_position(
        symbol=symbol,
        action=decision.action,
        portfolio_value=pv,
        entry=decision.entry or tech.price or 1,
        stop_loss=decision.stop_loss or (tech.price or 1) * 0.95,
        take_profit_1=decision.take_profit_1,
        take_profit_2=decision.take_profit_2,
        confidence=decision.confidence,
    )

    # 8. Alerts
    alert_sys.check_and_alert(symbol, tech, sent, fund_data, macro)

    # 9. Report
    return render_full_report(
        decision=decision,
        tech=tech,
        fund=fund,
        sent=sent,
        chain=chain,
        macro=macro,
        sizing=sizing,
        articles=articles,
        include_educational=include_edu,
    )


def run_backtest(symbol: str, asset_type: str):
    """Run backtest for a single symbol and print the report."""
    bt = Backtester()
    try:
        if asset_type == "crypto":
            df = fetch_crypto_ohlcv(symbol, "1d", limit=730)
        else:
            import yfinance as yf
            t  = yf.Ticker(symbol)
            df = t.history(period="2y", interval="1d")
            df = df[["Open","High","Low","Close","Volume"]].rename(columns=str.lower)
    except Exception as e:
        print(f"[ERROR] Backtest data fetch failed for {symbol}: {e}")
        return

    result = bt.run(df, symbol)
    print(bt.format_report(result))

    if not result.trades_log.empty:
        processed_dir = ROOT / "data" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        path = processed_dir / f"backtest_{symbol.replace('/', '_')}.csv"
        result.trades_log.to_csv(path, index=False)
        print(f"\n  Trade log saved → {path}")


def run_correlation_monitor(portfolio_value: float):
    """Show correlation matrix for all watchlist assets."""
    print("\n── CORRELATION MATRIX ──────────────────────────────────────")
    wl = CFG["watchlist"]
    price_data = {}

    # Collect stocks + BIST
    for sym in wl.get("us_stocks", []) + wl.get("bist", []):
        try:
            price_data[sym] = fetch_stock_ohlcv(sym)
        except Exception:
            pass

    # Collect crypto
    for sym in wl.get("crypto", []):
        try:
            price_data[sym] = fetch_crypto_ohlcv(sym)
        except Exception:
            pass

    rm = RiskManager(CFG)
    if len(price_data) >= 2:
        corr = rm.correlation_matrix(price_data)
        print(corr.to_string())
        warnings = rm.check_correlations(
            corr, CFG["risk"].get("correlation_warning", 0.85)
        )
        if warnings:
            print("\n⚠️  CORRELATION WARNINGS:")
            for w in warnings:
                print(f"  • {w}")
    else:
        print("  Not enough data for correlation analysis.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HedgeFund AI — Investment Analysis System")
    parser.add_argument("--symbol",    type=str, default=None,      help="Single asset to analyse (e.g. BTC/USDT, AAPL, THYAO.IS)")
    parser.add_argument("--portfolio", type=float, default=100_000, help="Portfolio value in USD (default 100,000)")
    parser.add_argument("--backtest",  action="store_true",         help="Run backtest for --symbol")
    parser.add_argument("--corr",      action="store_true",         help="Show correlation matrix")
    parser.add_argument("--no-edu",    action="store_true",         help="Disable educational notes in report")
    args = parser.parse_args()

    include_edu    = not args.no_edu
    portfolio_val  = args.portfolio

    # ── Shared singletons
    tech_analyzer    = TechnicalAnalyzer()
    fund_analyzer    = FundamentalAnalyzer()
    sent_analyzer    = SentimentAnalyzer()
    chain_analyzer   = OnChainAnalyzer()
    decision_engine  = DecisionEngine(CFG)
    risk_manager     = RiskManager(CFG)
    alert_sys        = AlertSystem()

    # ── Fetch macro once (shared across all symbols)
    print("\n🌍  Fetching macro data...")
    macro = fetch_macro_data()

    # ── Correlation monitor
    if args.corr:
        run_correlation_monitor(portfolio_val)
        return

    # ── Single symbol
    if args.symbol:
        sym  = args.symbol.strip()
        atype = detect_asset_type(sym)

        if args.backtest:
            print(f"\n⏳  Running backtest for {sym}...")
            run_backtest(sym, atype)
        else:
            report = run_analysis(
                sym, atype, portfolio_val, include_edu,
                alert_sys, tech_analyzer, fund_analyzer,
                sent_analyzer, chain_analyzer,
                decision_engine, risk_manager, macro,
            )
            print(report)
        return

    # ── Full watchlist scan
    wl = CFG["watchlist"]
    all_symbols = []
    for atype, syms in [
        ("crypto",  wl.get("crypto", [])),
        ("stock",   wl.get("us_stocks", [])),
        ("bist",    wl.get("bist", [])),
    ]:
        for s in syms:
            all_symbols.append((s, atype))

    print(f"\n📊  Scanning {len(all_symbols)} assets...\n")

    summary_rows = []
    for sym, atype in all_symbols:
        try:
            report = run_analysis(
                sym, atype, portfolio_val, include_edu,
                alert_sys, tech_analyzer, fund_analyzer,
                sent_analyzer, chain_analyzer,
                decision_engine, risk_manager, macro,
            )
            print(report)

            # Extract action + confidence for summary table
            d_engine_tmp = DecisionEngine(CFG)
            summary_rows.append(f"  {sym:<18} {atype:<8}")
        except Exception as e:
            logger.error(f"Analysis failed for {sym}: {traceback.format_exc()}")
            print(f"\n[ERROR] {sym}: {e}\n")

    # ── Alert summary
    print(alert_sys.summary())

    print("\n✅  Scan complete. Logs → logs/hedgefund_ai.log")


if __name__ == "__main__":
    main()
