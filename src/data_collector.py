"""
HedgeFund AI — Data Collector
Fetches OHLCV, fundamentals, macro, news & on-chain data.
All external calls are wrapped with retry + cache logic.
"""

import os, sys, time, json, logging, hashlib, requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml
import pandas as pd
import numpy as np
import yfinance as yf

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Paths: EXE (frozen) vs script mode ───────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent   # dist/HedgeFundAI/
else:
    _ROOT = Path(__file__).parent.parent  # repo root

CONFIG_PATH = _ROOT / "config" / "settings.yaml"
RAW_DIR     = _ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    # Delegate to central loader: overlays env vars + st.secrets onto YAML
    from src.config_loader import load_settings
    return load_settings(CONFIG_PATH)


CFG = load_config()


# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return RAW_DIR / f"cache_{h}.json"


def _cache_get(key: str, ttl_minutes: int) -> Optional[dict]:
    p = _cache_path(key)
    if not p.exists():
        return None
    age = (time.time() - p.stat().st_mtime) / 60
    if age > ttl_minutes:
        p.unlink(missing_ok=True)
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        p.unlink(missing_ok=True)
        return None


class _JSONEncoder(json.JSONEncoder):
    """Handle pandas Timestamp and numpy types."""
    def default(self, obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "item"):        # numpy scalar
            return obj.item()
        return super().default(obj)


def _cache_set(key: str, data: dict):
    p = _cache_path(key)
    with open(p, "w") as f:
        json.dump(data, f, cls=_JSONEncoder)


def _retry(fn, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise RuntimeError(f"All {retries} attempts failed for {fn}")


# ── Crypto Data (Binance via ccxt) ───────────────────────────────────────────

def _has_real_binance_key() -> bool:
    k = CFG["api_keys"].get("binance_api_key", "")
    return bool(k) and not k.startswith("YOUR_")


def _crypto_via_yfinance(symbol: str) -> pd.DataFrame:
    """Fallback: fetch crypto OHLCV from yfinance (BTC/USDT → BTC-USD)."""
    base  = symbol.split("/")[0]          # BTC
    yf_sym = f"{base}-USD"
    logger.info(f"Using yfinance fallback for {symbol} → {yf_sym}")
    df = yf.download(yf_sym, period="1y", interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {yf_sym}")
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    needed = [c for c in ["open","high","low","close","volume"] if c in df.columns]
    return df[needed]


def fetch_crypto_ohlcv(symbol: str, timeframe: str = "1d", limit: int = 300) -> pd.DataFrame:
    """Fetch OHLCV from Binance. Falls back to yfinance when API key not configured."""
    cache_key = f"crypto_{symbol}_{timeframe}_{limit}"
    cached = _cache_get(cache_key, CFG["data"]["cache_ttl_minutes"])
    if cached:
        df_c = pd.DataFrame(cached)
        # Restore DatetimeIndex if stored as ISO strings
        for col in ("Date", "Datetime", "timestamp", "index"):
            if col in df_c.columns:
                df_c[col] = pd.to_datetime(df_c[col], utc=True, errors="coerce")
                df_c.set_index(col, inplace=True)
                df_c.index.name = None
                break
        return df_c

    df = None

    if CCXT_AVAILABLE and _has_real_binance_key():
        try:
            def _fetch():
                exchange = ccxt.binance({
                    "apiKey": CFG["api_keys"]["binance_api_key"],
                    "secret": CFG["api_keys"]["binance_secret"],
                    "enableRateLimit": True,
                })
                raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                cols = ["timestamp", "open", "high", "low", "close", "volume"]
                df_ = pd.DataFrame(raw, columns=cols)
                df_["timestamp"] = pd.to_datetime(df_["timestamp"], unit="ms")
                df_.set_index("timestamp", inplace=True)
                return df_
            df = _retry(_fetch, retries=2, delay=3)
        except Exception as e:
            logger.warning(f"Binance failed for {symbol}, switching to yfinance: {e}")

    if df is None:
        df = _crypto_via_yfinance(symbol)

    _cache_set(cache_key, df.reset_index().to_dict(orient="list"))
    return df


def fetch_order_book(symbol: str) -> dict:
    """Fetch top-of-book bid/ask spread from Binance."""
    if not CCXT_AVAILABLE:
        return {"bid": None, "ask": None, "spread_pct": None}

    def _fetch():
        exchange = ccxt.binance({"enableRateLimit": True})
        ob = exchange.fetch_order_book(symbol, limit=5)
        bid = ob["bids"][0][0] if ob["bids"] else None
        ask = ob["asks"][0][0] if ob["asks"] else None
        spread = ((ask - bid) / bid * 100) if bid and ask else None
        return {"bid": bid, "ask": ask, "spread_pct": round(spread, 4) if spread else None}

    return _retry(_fetch)


# ── US Stocks (yfinance + Finnhub) ───────────────────────────────────────────

def fetch_stock_ohlcv(ticker: str) -> pd.DataFrame:
    cache_key = f"stock_{ticker}"
    cached = _cache_get(cache_key, CFG["data"]["cache_ttl_minutes"])
    if cached:
        df_c = pd.DataFrame(cached)
        for col in ("Date", "Datetime", "timestamp", "index"):
            if col in df_c.columns:
                df_c[col] = pd.to_datetime(df_c[col], utc=True, errors="coerce")
                df_c.set_index(col, inplace=True)
                df_c.index.name = None
                break
        return df_c

    def _fetch():
        t = yf.Ticker(ticker)
        df = t.history(
            period=CFG["data"]["stock_period"],
            interval=CFG["data"]["stock_interval"],
        )
        df = df[["Open", "High", "Low", "Close", "Volume"]].rename(columns=str.lower)
        return df

    df = _retry(_fetch)
    _cache_set(cache_key, df.reset_index().to_dict(orient="list"))
    return df


def fetch_fundamentals(ticker: str) -> dict:
    """Fetch key fundamental metrics via Finnhub (falls back to yfinance info)."""
    cache_key = f"fund_{ticker}"
    cached = _cache_get(cache_key, 240)  # fundamentals change slowly → 4h cache
    if cached:
        return cached

    # Try Finnhub
    key = CFG["api_keys"].get("finnhub", "")
    data = {}
    if key and key != "YOUR_FINNHUB_KEY":
        try:
            url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={key}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                m = r.json().get("metric", {})
                data = {
                    "pe_ratio":       m.get("peNormalizedAnnual"),
                    "peg_ratio":      m.get("pegRatio"),
                    "roe":            m.get("roeTTM"),
                    "roic":           m.get("roicTTM"),
                    "revenue_growth": m.get("revenueGrowthTTMYoy"),
                    "eps_growth":     m.get("epsGrowthTTMYoy"),
                    "debt_equity":    m.get("totalDebt/totalEquityQuarterly"),
                    "current_ratio":  m.get("currentRatioQuarterly"),
                    "source": "finnhub",
                }
        except Exception as e:
            logger.warning(f"Finnhub failed for {ticker}: {e}")

    # Fallback to yfinance
    if not data:
        try:
            info = yf.Ticker(ticker).info
            data = {
                "pe_ratio":       info.get("trailingPE"),
                "peg_ratio":      info.get("pegRatio"),
                "roe":            info.get("returnOnEquity"),
                "roic":           None,
                "revenue_growth": info.get("revenueGrowth"),
                "eps_growth":     info.get("earningsGrowth"),
                "debt_equity":    info.get("debtToEquity"),
                "current_ratio":  info.get("currentRatio"),
                "market_cap":     info.get("marketCap"),
                "sector":         info.get("sector"),
                "source": "yfinance",
            }
        except Exception as e:
            logger.warning(f"yfinance fundamentals failed for {ticker}: {e}")
            data = {"source": "unavailable"}

    _cache_set(cache_key, data)
    return data


# ── Macro Data (FRED + yfinance) ─────────────────────────────────────────────

def fetch_macro_data() -> dict:
    cache_key = "macro_data"
    cached = _cache_get(cache_key, 60)
    if cached:
        return cached

    results = {}

    # yfinance macro proxies
    macro_tickers = {
        "VIX":   "^VIX",
        "DXY":   "DX-Y.NYB",
        "Gold":  "GC=F",
        "10Y":   "^TNX",
        "SP500": "^GSPC",
    }
    for name, sym in macro_tickers.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d", interval="1d")
            if not hist.empty:
                results[name] = {
                    "current": round(float(hist["Close"].iloc[-1]), 2),
                    "change_1d": round(float(hist["Close"].pct_change().iloc[-1] * 100), 2),
                }
        except Exception as e:
            logger.warning(f"Macro fetch failed for {sym}: {e}")

    # FRED (interest rates, CPI) — optional
    fred_key = CFG["api_keys"].get("fred", "")
    if fred_key and fred_key != "YOUR_FRED_KEY":
        series = {"FedFundsRate": "FEDFUNDS", "CPI_YoY": "CPIAUCSL"}
        for label, sid in series.items():
            try:
                url = (
                    f"https://api.stlouisfed.org/fred/series/observations"
                    f"?series_id={sid}&api_key={fred_key}&file_type=json"
                    f"&sort_order=desc&limit=2"
                )
                r = requests.get(url, timeout=10)
                obs = r.json().get("observations", [])
                if obs:
                    results[label] = {
                        "current": float(obs[0]["value"]),
                        "prior":   float(obs[1]["value"]) if len(obs) > 1 else None,
                    }
            except Exception as e:
                logger.warning(f"FRED failed for {sid}: {e}")

    _cache_set(cache_key, results)
    return results


# ── News & Sentiment ─────────────────────────────────────────────────────────

def fetch_news(query: str, max_articles: int = 10) -> list[dict]:
    cache_key = f"news_{query}"
    cached = _cache_get(cache_key, 30)
    if cached:
        return cached

    key = CFG["api_keys"].get("newsapi", "")
    articles = []

    if key and key != "YOUR_NEWSAPI_KEY":
        try:
            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={query}&language=en&sortBy=publishedAt"
                f"&pageSize={max_articles}&apiKey={key}"
            )
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                raw = r.json().get("articles", [])
                articles = [
                    {
                        "title":       a.get("title", ""),
                        "description": a.get("description", ""),
                        "url":         a.get("url", ""),
                        "published":   a.get("publishedAt", ""),
                        "source":      a.get("source", {}).get("name", ""),
                    }
                    for a in raw
                ]
        except Exception as e:
            logger.warning(f"NewsAPI failed for '{query}': {e}")

    if not articles:
        # Simulate mock news when API key unavailable
        articles = _mock_news(query)

    _cache_set(cache_key, articles)
    return articles


def _mock_news(query: str) -> list[dict]:
    templates = [
        {"title": f"{query} shows strong momentum as institutional buyers accumulate",
         "description": "Analysts report increasing institutional interest.",
         "sentiment_hint": "positive"},
        {"title": f"Caution advised for {query} amid macro headwinds",
         "description": "Fed uncertainty weighs on risk assets.",
         "sentiment_hint": "negative"},
        {"title": f"{query} consolidates near key support levels",
         "description": "Technical outlook remains mixed.",
         "sentiment_hint": "neutral"},
    ]
    return templates


# ── On-Chain Data (Glassnode mock) ───────────────────────────────────────────

def fetch_onchain(symbol: str = "BTC") -> dict:
    """
    Real Glassnode integration requires a paid API key.
    Returns mock data with realistic ranges for demo purposes.
    Set api_keys.glassnode in settings.yaml to enable real data.
    """
    key = CFG["api_keys"].get("glassnode", "")
    if key and key != "YOUR_GLASSNODE_KEY":
        # Real integration skeleton (uncomment when key available)
        # base = "https://api.glassnode.com/v1/metrics"
        # headers = {"X-Api-Key": key}
        # ... fetch exchange_net_position_change, sopr, etc.
        pass

    # Mock realistic on-chain data
    rng = np.random.default_rng(seed=int(datetime.now().strftime("%Y%m%d")))
    return {
        "exchange_inflow_24h":   round(float(rng.uniform(15000, 45000)), 0),
        "exchange_outflow_24h":  round(float(rng.uniform(12000, 50000)), 0),
        "net_flow":              round(float(rng.uniform(-8000, 8000)), 0),
        "whale_transactions":    int(rng.integers(20, 120)),
        "sopr":                  round(float(rng.uniform(0.97, 1.04)), 4),
        "nupl":                  round(float(rng.uniform(0.2, 0.6)), 4),
        "mvrv_z_score":          round(float(rng.uniform(0.5, 3.5)), 2),
        "source": "mock (add Glassnode key for real data)",
    }
