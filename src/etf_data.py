"""
HedgeFund AI — ETF & Global Fon Evreni
200+ ETF, kategorize edilmiş, yfinance ile veri çekimi.
"""

import logging
import pandas as pd
import yfinance as yf
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Kapsamlı ETF Listesi ──────────────────────────────────────
ETF_UNIVERSE = {
    # ABD Geniş Piyasa
    "ABD Geniş Piyasa": [
        ("SPY",  "SPDR S&P 500 ETF"),
        ("QQQ",  "Invesco Nasdaq-100 ETF"),
        ("IWM",  "iShares Russell 2000 ETF"),
        ("DIA",  "SPDR Dow Jones ETF"),
        ("VTI",  "Vanguard Total Stock Market ETF"),
        ("VOO",  "Vanguard S&P 500 ETF"),
        ("IVV",  "iShares Core S&P 500 ETF"),
        ("ITOT", "iShares Core S&P Total US ETF"),
        ("SCHB", "Schwab US Broad Market ETF"),
    ],
    # Sektör ETF'leri
    "Teknoloji": [
        ("XLK",  "Technology Select Sector SPDR"),
        ("VGT",  "Vanguard Information Technology ETF"),
        ("SOXX", "iShares Semiconductor ETF"),
        ("SMH",  "VanEck Semiconductor ETF"),
        ("HACK", "ETFMG Prime Cyber Security ETF"),
        ("CIBR", "First Trust Cybersecurity ETF"),
        ("AIQ",  "Global X Artificial Intelligence ETF"),
        ("BOTZ", "Global X Robotics & AI ETF"),
        ("ROBO", "ROBO Global Robotics ETF"),
        ("SKYY", "First Trust Cloud Computing ETF"),
        ("CLOU", "Global X Cloud Computing ETF"),
        ("META", "Roundhill Ball Metaverse ETF"),
    ],
    "Finans": [
        ("XLF",  "Financial Select Sector SPDR"),
        ("VFH",  "Vanguard Financials ETF"),
        ("KBE",  "SPDR S&P Bank ETF"),
        ("KRE",  "SPDR S&P Regional Banking ETF"),
    ],
    "Enerji": [
        ("XLE",  "Energy Select Sector SPDR"),
        ("VDE",  "Vanguard Energy ETF"),
        ("OIH",  "VanEck Oil Services ETF"),
        ("XOP",  "SPDR S&P Oil & Gas Exploration ETF"),
        ("ICLN", "iShares Global Clean Energy ETF"),
        ("QCLN", "First Trust NASDAQ Clean Edge ETF"),
        ("TAN",  "Invesco Solar ETF"),
        ("FAN",  "First Trust Global Wind Energy ETF"),
    ],
    "Sağlık": [
        ("XLV",  "Health Care Select Sector SPDR"),
        ("VHT",  "Vanguard Health Care ETF"),
        ("IBB",  "iShares Biotechnology ETF"),
        ("XBI",  "SPDR S&P Biotech ETF"),
        ("ARKG", "ARK Genomic Revolution ETF"),
    ],
    "Tüketim": [
        ("XLY",  "Consumer Discretionary Select SPDR"),
        ("XLP",  "Consumer Staples Select SPDR"),
        ("VCR",  "Vanguard Consumer Discretionary ETF"),
    ],
    "Sanayi": [
        ("XLI",  "Industrials Select Sector SPDR"),
        ("VIS",  "Vanguard Industrials ETF"),
        ("ITA",  "iShares U.S. Aerospace & Defense ETF"),
    ],
    "Gayrimenkul": [
        ("VNQ",  "Vanguard Real Estate ETF"),
        ("IYR",  "iShares U.S. Real Estate ETF"),
        ("SCHH", "Schwab U.S. REIT ETF"),
    ],
    # Tematik ETF'ler
    "ARK Fonları": [
        ("ARKK", "ARK Innovation ETF"),
        ("ARKG", "ARK Genomic Revolution ETF"),
        ("ARKW", "ARK Next Generation Internet ETF"),
        ("ARKF", "ARK Fintech Innovation ETF"),
        ("ARKQ", "ARK Autonomous Tech & Robotics ETF"),
        ("ARKX", "ARK Space Exploration ETF"),
    ],
    "Temalar": [
        ("ESPO", "VanEck Video Gaming and Esports ETF"),
        ("BETZ", "Roundhill Sports Betting & Gaming ETF"),
        ("POTX", "Global X Cannabis ETF"),
        ("MJ",   "ETFMG Alternative Harvest ETF"),
        ("WCLD", "WisdomTree Cloud Computing ETF"),
        ("FINX", "Global X FinTech ETF"),
        ("DRIV", "Global X Autonomous & Electric Vehicles ETF"),
        ("LIT",  "Global X Lithium & Battery Tech ETF"),
        ("COPX", "Global X Copper Miners ETF"),
        ("REMX", "VanEck Rare Earth & Strategic Metals ETF"),
    ],
    # Sabit Getirili
    "Tahvil ETF": [
        ("TLT",  "iShares 20+ Year Treasury Bond ETF"),
        ("IEF",  "iShares 7-10 Year Treasury Bond ETF"),
        ("SHY",  "iShares 1-3 Year Treasury Bond ETF"),
        ("AGG",  "iShares Core U.S. Aggregate Bond ETF"),
        ("BND",  "Vanguard Total Bond Market ETF"),
        ("HYG",  "iShares iBoxx High Yield Corporate Bond ETF"),
        ("LQD",  "iShares iBoxx Investment Grade Corporate Bond ETF"),
        ("EMB",  "iShares JP Morgan USD Emerging Markets Bond ETF"),
        ("TIP",  "iShares TIPS Bond ETF"),
        ("VTIP", "Vanguard Short-Term Inflation-Protected Securities ETF"),
    ],
    # Emtia
    "Emtia": [
        ("GLD",  "SPDR Gold Shares"),
        ("IAU",  "iShares Gold Trust"),
        ("GDX",  "VanEck Gold Miners ETF"),
        ("GDXJ", "VanEck Junior Gold Miners ETF"),
        ("SLV",  "iShares Silver Trust"),
        ("PSLV", "Sprott Physical Silver Trust"),
        ("USO",  "United States Oil Fund"),
        ("BNO",  "United States Brent Oil Fund"),
        ("UNG",  "United States Natural Gas Fund"),
        ("PDBC", "Invesco Optimum Yield Diversified Commodity ETF"),
        ("DBA",  "Invesco DB Agriculture Fund"),
        ("CORN", "Teucrium Corn Fund"),
        ("WEAT", "Teucrium Wheat Fund"),
        ("SOYB", "Teucrium Soybean Fund"),
    ],
    # Kripto ETF
    "Kripto ETF": [
        ("IBIT", "iShares Bitcoin Trust ETF"),
        ("FBTC", "Fidelity Wise Origin Bitcoin Fund"),
        ("BITB", "Bitwise Bitcoin ETF"),
        ("ARKB", "ARK 21Shares Bitcoin ETF"),
        ("GBTC", "Grayscale Bitcoin Trust"),
        ("ETHA", "iShares Ethereum Trust ETF"),
        ("BITO", "ProShares Bitcoin Strategy ETF"),
        ("MSTR", "MicroStrategy (Bitcoin proxy)"),
    ],
    # Uluslararası
    "Uluslararası Gelişmiş": [
        ("EFA",  "iShares MSCI EAFE ETF"),
        ("IEFA", "iShares Core MSCI EAFE ETF"),
        ("VEA",  "Vanguard FTSE Developed Markets ETF"),
        ("EWJ",  "iShares MSCI Japan ETF"),
        ("EWG",  "iShares MSCI Germany ETF"),
        ("EWU",  "iShares MSCI United Kingdom ETF"),
        ("EZU",  "iShares MSCI Eurozone ETF"),
        ("EWL",  "iShares MSCI Switzerland ETF"),
    ],
    "Gelişmekte Olan Piyasalar": [
        ("EEM",  "iShares MSCI Emerging Markets ETF"),
        ("VWO",  "Vanguard FTSE Emerging Markets ETF"),
        ("IEMG", "iShares Core MSCI Emerging Markets ETF"),
        ("EWZ",  "iShares MSCI Brazil ETF"),
        ("EWY",  "iShares MSCI South Korea ETF"),
        ("FXI",  "iShares China Large-Cap ETF"),
        ("MCHI", "iShares MSCI China ETF"),
        ("INDA", "iShares MSCI India ETF"),
        ("TUR",  "iShares MSCI Turkey ETF"),
        ("RSX",  "VanEck Russia ETF"),
        ("EWA",  "iShares MSCI Australia ETF"),
    ],
    # Kaldıraçlı (Riskli!)
    "Kaldıraçlı (3x)": [
        ("TQQQ", "ProShares UltraPro QQQ 3x"),
        ("SQQQ", "ProShares UltraPro Short QQQ 3x"),
        ("UPRO", "ProShares UltraPro S&P500 3x"),
        ("SPXS", "Direxion Daily S&P 500 Bear 3x"),
        ("LABU", "Direxion Daily S&P Biotech Bull 3x"),
        ("LABD", "Direxion Daily S&P Biotech Bear 3x"),
        ("FNGU", "MicroSectors FANG+ 3x"),
        ("FNGD", "MicroSectors FANG+ -3x"),
        ("UVXY", "ProShares Ultra VIX Short-Term Futures ETF"),
        ("SOXL", "Direxion Daily Semiconductor Bull 3x"),
        ("SOXS", "Direxion Daily Semiconductor Bear 3x"),
    ],
    # Vanguard Global Fonlar
    "Vanguard": [
        ("VT",   "Vanguard Total World Stock ETF"),
        ("VXUS", "Vanguard Total International Stock ETF"),
        ("VEU",  "Vanguard FTSE All-World ex-US ETF"),
        ("VSS",  "Vanguard FTSE All-World ex-US Small-Cap ETF"),
        ("VYMI", "Vanguard International High Dividend Yield ETF"),
        ("VIGI", "Vanguard International Dividend Appreciation ETF"),
        ("VIG",  "Vanguard Dividend Appreciation ETF"),
        ("VYM",  "Vanguard High Dividend Yield ETF"),
        ("VONG", "Vanguard Russell 1000 Growth ETF"),
        ("VONV", "Vanguard Russell 1000 Value ETF"),
    ],
    # BlackRock iShares
    "iShares (BlackRock)": [
        ("ACWI", "iShares MSCI ACWI ETF"),
        ("ACWX", "iShares MSCI ACWI ex US ETF"),
        ("AGZ",  "iShares Agency Bond ETF"),
        ("BKLN", "Invesco Senior Loan ETF"),
        ("IWF",  "iShares Russell 1000 Growth ETF"),
        ("IWD",  "iShares Russell 1000 Value ETF"),
        ("IWO",  "iShares Russell 2000 Growth ETF"),
        ("IWN",  "iShares Russell 2000 Value ETF"),
    ],
}


def get_all_etfs() -> pd.DataFrame:
    """Tüm ETF listesini DataFrame olarak döndür."""
    rows = []
    for category, etfs in ETF_UNIVERSE.items():
        for ticker, name in etfs:
            rows.append({
                "ticker":   ticker,
                "name":     name,
                "category": category,
            })
    return pd.DataFrame(rows)


def fetch_etf_data(tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Birden fazla ETF için fiyat verisi çek."""
    result = {}
    for ticker in tickers:
        try:
            t  = yf.Ticker(ticker)
            df = t.history(period=period, interval="1d")
            if not df.empty:
                df = df[["Open","High","Low","Close","Volume"]].rename(columns=str.lower)
                result[ticker] = df
        except Exception as e:
            logger.warning(f"ETF fetch failed {ticker}: {e}")
    return result


def calculate_etf_metrics(ticker: str, df: pd.DataFrame) -> dict:
    """ETF için performans ve risk metriklerini hesapla."""
    if df is None or df.empty:
        return {"ticker": ticker}

    import numpy as np
    close  = df["close"].astype(float)
    last   = float(close.iloc[-1])
    daily  = close.pct_change().dropna()

    def ret(n):
        return round((last / float(close.iloc[-n-1]) - 1) * 100, 2) if len(close) > n else None

    # Max Drawdown
    roll_max = close.cummax()
    dd       = (close - roll_max) / roll_max
    max_dd   = round(float(dd.min() * 100), 2)

    # Sharpe (rf=0)
    sharpe = 0.0
    if daily.std() > 0:
        sharpe = round(float(daily.mean() / daily.std() * np.sqrt(252)), 3)

    # Volatility
    vol = round(float(daily.std() * np.sqrt(252) * 100), 2)

    return {
        "ticker":      ticker,
        "price":       round(last, 2),
        "return_1d":   ret(1),
        "return_1w":   ret(5),
        "return_1m":   ret(21),
        "return_3m":   ret(63),
        "return_6m":   ret(126),
        "return_1y":   ret(252),
        "max_drawdown":max_dd,
        "sharpe":      sharpe,
        "volatility":  vol,
    }


def screen_etfs(
    category: str = "Tümü",
    sort_by: str = "return_1y",
    top_n: int = 50,
) -> tuple[pd.DataFrame, dict]:
    """
    ETF tarayıcı: kategori filtrele, metric'e göre sırala.
    Returns: (etf_list_df, metrics_dict)
    """
    all_etfs = get_all_etfs()

    if category != "Tümü":
        all_etfs = all_etfs[all_etfs["category"] == category]

    tickers = all_etfs["ticker"].tolist()[:top_n]
    price_data = fetch_etf_data(tickers, period="1y")

    metrics_list = []
    for ticker in tickers:
        df = price_data.get(ticker)
        m  = calculate_etf_metrics(ticker, df)
        # Merge with name/category
        row = all_etfs[all_etfs["ticker"] == ticker].iloc[0].to_dict()
        row.update(m)
        metrics_list.append(row)

    result = pd.DataFrame(metrics_list)
    if sort_by in result.columns:
        result = result.sort_values(sort_by, ascending=False, na_position="last")

    return result.reset_index(drop=True), price_data
