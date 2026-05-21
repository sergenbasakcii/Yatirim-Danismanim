"""
HedgeFund AI — Paylaşılan UI Widget'ları
=========================================
Tüm sayfalarda kullanılan ortak bileşenler:
  • SmartSearchEntry  — tıklayınca tüm listeyi gösterir, yazınca daraltır
  • DatePicker        — Gün/Ay/Yıl dropdown, elle yazma yok
"""

from __future__ import annotations
import calendar
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

# ── Renk paleti ───────────────────────────────────────────────────────────────
BG        = "#f6f8fa"
BG_CARD   = "#ffffff"
BG_INPUT  = "#eaeef2"
BORDER    = "#d0d7de"
ACCENT    = "#0969da"
TEXT1     = "#1f2328"
TEXT2     = "#57606a"
BUY_C     = "#1a7f37"
SELL_C    = "#cf222e"
HOLD_C    = "#9a6700"

F_BODY  = ("Segoe UI", 11)
F_SMALL = ("Segoe UI", 10)
F_TINY  = ("Segoe UI", 9)

# ══════════════════════════════════════════════════════════════════════════════
# SEMBOL VERİTABANI
# ══════════════════════════════════════════════════════════════════════════════
# Format: (sembol, isim, kategori)
ALL_SYMBOLS: list[tuple[str, str, str]] = [

    # ── KRİPTO ────────────────────────────────────────────────────────────────
    ("BTC-USD",   "Bitcoin",            "Kripto"),
    ("ETH-USD",   "Ethereum",           "Kripto"),
    ("BNB-USD",   "BNB",                "Kripto"),
    ("SOL-USD",   "Solana",             "Kripto"),
    ("XRP-USD",   "Ripple",             "Kripto"),
    ("ADA-USD",   "Cardano",            "Kripto"),
    ("AVAX-USD",  "Avalanche",          "Kripto"),
    ("DOT-USD",   "Polkadot",           "Kripto"),
    ("LINK-USD",  "Chainlink",          "Kripto"),
    ("MATIC-USD", "Polygon",            "Kripto"),
    ("DOGE-USD",  "Dogecoin",           "Kripto"),
    ("SHIB-USD",  "Shiba Inu",          "Kripto"),
    ("LTC-USD",   "Litecoin",           "Kripto"),
    ("BCH-USD",   "Bitcoin Cash",       "Kripto"),
    ("ATOM-USD",  "Cosmos",             "Kripto"),
    ("UNI-USD",   "Uniswap",            "Kripto"),
    ("AAVE-USD",  "Aave",               "Kripto"),
    ("NEAR-USD",  "NEAR Protocol",      "Kripto"),
    ("APT-USD",   "Aptos",              "Kripto"),
    ("OP-USD",    "Optimism",           "Kripto"),
    ("ARB-USD",   "Arbitrum",           "Kripto"),
    ("INJ-USD",   "Injective",          "Kripto"),
    ("SUI-USD",   "Sui",                "Kripto"),
    ("TON-USD",   "Toncoin",            "Kripto"),
    ("TRX-USD",   "TRON",               "Kripto"),
    ("XLM-USD",   "Stellar",            "Kripto"),
    ("VET-USD",   "VeChain",            "Kripto"),
    ("ALGO-USD",  "Algorand",           "Kripto"),
    ("SAND-USD",  "The Sandbox",        "Kripto"),
    ("MANA-USD",  "Decentraland",       "Kripto"),
    ("FTM-USD",   "Fantom",             "Kripto"),
    ("CRV-USD",   "Curve DAO",          "Kripto"),
    ("MKR-USD",   "Maker",              "Kripto"),
    ("COMP-USD",  "Compound",           "Kripto"),
    ("LDO-USD",   "Lido DAO",           "Kripto"),
    ("RUNE-USD",  "THORChain",          "Kripto"),
    ("FIL-USD",   "Filecoin",           "Kripto"),
    ("ETC-USD",   "Ethereum Classic",   "Kripto"),
    ("HBAR-USD",  "Hedera",             "Kripto"),
    ("ICP-USD",   "Internet Computer",  "Kripto"),
    ("GRT-USD",   "The Graph",          "Kripto"),
    ("EGLD-USD",  "MultiversX",         "Kripto"),
    ("STX-USD",   "Stacks",             "Kripto"),
    ("IMX-USD",   "Immutable X",        "Kripto"),
    ("PEPE-USD",  "Pepe",               "Kripto"),
    ("WLD-USD",   "Worldcoin",          "Kripto"),
    ("BLUR-USD",  "Blur",               "Kripto"),
    ("SEI-USD",   "Sei",                "Kripto"),
    ("JUP-USD",   "Jupiter",            "Kripto"),
    ("PYTH-USD",  "Pyth Network",       "Kripto"),

    # ── BIST (Türk Hisseleri) ─────────────────────────────────────────────────
    ("THYAO.IS", "Türk Hava Yolları",           "BIST"),
    ("BIMAS.IS", "BİM Mağazalar",               "BIST"),
    ("SISE.IS",  "Şişecam",                     "BIST"),
    ("AKBNK.IS", "Akbank",                      "BIST"),
    ("EREGL.IS", "Ereğli Demir Çelik",          "BIST"),
    ("KCHOL.IS", "Koç Holding",                 "BIST"),
    ("TUPRS.IS", "Tüpraş",                      "BIST"),
    ("GARAN.IS", "Garanti BBVA",                "BIST"),
    ("ISCTR.IS", "İş Bankası (C)",              "BIST"),
    ("SAHOL.IS", "Sabancı Holding",             "BIST"),
    ("FROTO.IS", "Ford Otosan",                 "BIST"),
    ("TOASO.IS", "Tofaş",                       "BIST"),
    ("PGSUS.IS", "Pegasus Hava Yolları",        "BIST"),
    ("ASELS.IS", "Aselsan",                     "BIST"),
    ("TKFEN.IS", "Tekfen Holding",              "BIST"),
    ("HEKTS.IS", "Hektaş",                      "BIST"),
    ("TCELL.IS", "Turkcell",                    "BIST"),
    ("ARCLK.IS", "Arçelik",                     "BIST"),
    ("ENKAI.IS", "Enka İnşaat",                 "BIST"),
    ("KOZAL.IS", "Koza Altın",                  "BIST"),
    ("KRDMD.IS", "Kardemir (D)",                "BIST"),
    ("PETKM.IS", "Petkim",                      "BIST"),
    ("MGROS.IS", "Migros",                      "BIST"),
    ("ULKER.IS", "Ülker Bisküvi",               "BIST"),
    ("TTKOM.IS", "Türk Telekom",                "BIST"),
    ("EKGYO.IS", "Emlak Konut GYO",             "BIST"),
    ("VESTL.IS", "Vestel",                      "BIST"),
    ("LOGO.IS",  "Logo Yazılım",                "BIST"),
    ("DOAS.IS",  "Doğuş Otomotiv",              "BIST"),
    ("OTKAR.IS", "Otokar",                      "BIST"),
    ("SODA.IS",  "Soda Sanayii",                "BIST"),
    ("TAVHL.IS", "TAV Havalimanları",           "BIST"),
    ("AGHOL.IS", "AG Anadolu Grubu",            "BIST"),
    ("ALARK.IS", "Alarko Holding",              "BIST"),
    ("BRISA.IS", "Brisa",                       "BIST"),
    ("CCOLA.IS", "Coca-Cola İçecek",            "BIST"),
    ("CLEBI.IS", "Çelebi Hava Servisi",         "BIST"),
    ("DOHOL.IS", "Doğan Holding",               "BIST"),
    ("EGEEN.IS", "Ege Endüstri",                "BIST"),
    ("GUBRF.IS", "Gübre Fabrikaları",           "BIST"),
    ("ISGYO.IS", "İş GYO",                      "BIST"),
    ("KARSN.IS", "Karsan Otomotiv",             "BIST"),
    ("KONTR.IS", "Kontrolmatik",                "BIST"),
    ("KOZAA.IS", "Koza Madencilik",             "BIST"),
    ("MAVI.IS",  "Mavi Giyim",                  "BIST"),
    ("OYAKC.IS", "Oyak Çimento",                "BIST"),
    ("SOKM.IS",  "Şok Marketler",               "BIST"),
    ("TABGD.IS", "TAB Gıda (Burger King TR)",   "BIST"),
    ("TSKB.IS",  "TSKB",                        "BIST"),
    ("TURSG.IS", "Turkcell Superonline",         "BIST"),
    ("VAKBN.IS", "Vakıfbank",                   "BIST"),
    ("YKBNK.IS", "Yapı Kredi",                  "BIST"),
    ("SKBNK.IS", "Şekerbank",                   "BIST"),
    ("SELEC.IS", "Selçuk Ecza",                 "BIST"),
    ("RYSAS.IS", "Reysaş Lojistik",             "BIST"),
    ("QUAGR.IS", "Quarton International",        "BIST"),
    ("PRKAB.IS", "Türk Prysmian Kablo",         "BIST"),
    ("NETAS.IS", "Netaş Telekomünikasyon",      "BIST"),
    ("INDES.IS", "İndeks Bilgisayar",           "BIST"),
    ("CEMAS.IS", "Çemaş Döküm",                 "BIST"),
    ("ODAS.IS",  "Odaş Elektrik",               "BIST"),
    ("IPEKE.IS", "İpek Doğal Enerji",           "BIST"),
    ("ZRGYO.IS", "Ziraat GYO",                  "BIST"),

    # ── ABD HİSSELERİ ────────────────────────────────────────────────────────
    ("AAPL",  "Apple",               "ABD Hisse"),
    ("MSFT",  "Microsoft",           "ABD Hisse"),
    ("GOOGL", "Alphabet (Google)",   "ABD Hisse"),
    ("AMZN",  "Amazon",              "ABD Hisse"),
    ("NVDA",  "NVIDIA",              "ABD Hisse"),
    ("TSLA",  "Tesla",               "ABD Hisse"),
    ("META",  "Meta Platforms",      "ABD Hisse"),
    ("JPM",   "JPMorgan Chase",      "ABD Hisse"),
    ("V",     "Visa",                "ABD Hisse"),
    ("JNJ",   "Johnson & Johnson",   "ABD Hisse"),
    ("WMT",   "Walmart",             "ABD Hisse"),
    ("UNH",   "UnitedHealth",        "ABD Hisse"),
    ("MA",    "Mastercard",          "ABD Hisse"),
    ("HD",    "Home Depot",          "ABD Hisse"),
    ("PG",    "Procter & Gamble",    "ABD Hisse"),
    ("BAC",   "Bank of America",     "ABD Hisse"),
    ("XOM",   "ExxonMobil",          "ABD Hisse"),
    ("KO",    "Coca-Cola",           "ABD Hisse"),
    ("PFE",   "Pfizer",              "ABD Hisse"),
    ("ABBV",  "AbbVie",              "ABD Hisse"),
    ("AVGO",  "Broadcom",            "ABD Hisse"),
    ("LLY",   "Eli Lilly",           "ABD Hisse"),
    ("COST",  "Costco",              "ABD Hisse"),
    ("MRK",   "Merck",               "ABD Hisse"),
    ("CVX",   "Chevron",             "ABD Hisse"),
    ("MCD",   "McDonald's",          "ABD Hisse"),
    ("DIS",   "Walt Disney",         "ABD Hisse"),
    ("NFLX",  "Netflix",             "ABD Hisse"),
    ("ADBE",  "Adobe",               "ABD Hisse"),
    ("CRM",   "Salesforce",          "ABD Hisse"),
    ("AMD",   "AMD",                 "ABD Hisse"),
    ("INTC",  "Intel",               "ABD Hisse"),
    ("QCOM",  "Qualcomm",            "ABD Hisse"),
    ("IBM",   "IBM",                 "ABD Hisse"),
    ("ORCL",  "Oracle",              "ABD Hisse"),
    ("CSCO",  "Cisco",               "ABD Hisse"),
    ("GE",    "GE Aerospace",        "ABD Hisse"),
    ("BA",    "Boeing",              "ABD Hisse"),
    ("CAT",   "Caterpillar",         "ABD Hisse"),
    ("F",     "Ford Motor",          "ABD Hisse"),
    ("GM",    "General Motors",      "ABD Hisse"),
    ("UBER",  "Uber",                "ABD Hisse"),
    ("PYPL",  "PayPal",              "ABD Hisse"),
    ("SQ",    "Block (Square)",      "ABD Hisse"),
    ("SHOP",  "Shopify",             "ABD Hisse"),
    ("COIN",  "Coinbase",            "ABD Hisse"),
    ("PLTR",  "Palantir",            "ABD Hisse"),
    ("HOOD",  "Robinhood",           "ABD Hisse"),
    ("SOFI",  "SoFi Technologies",   "ABD Hisse"),
    ("RIVN",  "Rivian",              "ABD Hisse"),
    ("LCID",  "Lucid Motors",        "ABD Hisse"),
    ("NIO",   "NIO",                 "ABD Hisse"),
    ("BABA",  "Alibaba",             "ABD Hisse"),
    ("TSM",   "TSMC",                "ABD Hisse"),
    ("ASML",  "ASML Holding",        "ABD Hisse"),
    ("SAP",   "SAP SE",              "ABD Hisse"),

    # ── ABD ETF'LERİ ─────────────────────────────────────────────────────────
    ("SPY",   "S&P 500 ETF",                  "ETF"),
    ("QQQ",   "Nasdaq-100 ETF",               "ETF"),
    ("IWM",   "Russell 2000 ETF",             "ETF"),
    ("DIA",   "Dow Jones ETF",                "ETF"),
    ("VOO",   "Vanguard S&P 500 ETF",         "ETF"),
    ("VTI",   "Vanguard Total Market ETF",    "ETF"),
    ("VT",    "Vanguard Total World ETF",     "ETF"),
    ("VEA",   "Developed Markets ETF",        "ETF"),
    ("VWO",   "Emerging Markets ETF",         "ETF"),
    ("EEM",   "iShares MSCI EM ETF",          "ETF"),
    ("EFA",   "iShares MSCI EAFE ETF",        "ETF"),
    ("GLD",   "SPDR Gold Shares",             "ETF"),
    ("IAU",   "iShares Gold ETF",             "ETF"),
    ("SLV",   "iShares Silver ETF",           "ETF"),
    ("PPLT",  "Platinum ETF",                 "ETF"),
    ("USO",   "United States Oil ETF",        "ETF"),
    ("UNG",   "Natural Gas ETF",              "ETF"),
    ("TLT",   "20+ Year Treasury Bond ETF",   "ETF"),
    ("IEF",   "7-10 Year Treasury ETF",       "ETF"),
    ("SHY",   "1-3 Year Treasury ETF",        "ETF"),
    ("HYG",   "High Yield Corporate Bond ETF","ETF"),
    ("LQD",   "Investment Grade Bond ETF",    "ETF"),
    ("VNQ",   "Vanguard Real Estate ETF",     "ETF"),
    ("ARKK",  "ARK Innovation ETF",           "ETF"),
    ("ARKG",  "ARK Genomic Revolution ETF",   "ETF"),
    ("ARKW",  "ARK Next Gen Internet ETF",    "ETF"),
    ("XLF",   "Financials Sector ETF",        "ETF"),
    ("XLK",   "Technology Sector ETF",        "ETF"),
    ("XLE",   "Energy Sector ETF",            "ETF"),
    ("XLV",   "Healthcare Sector ETF",        "ETF"),
    ("XLI",   "Industrials Sector ETF",       "ETF"),
    ("XLU",   "Utilities Sector ETF",         "ETF"),
    ("XLB",   "Materials Sector ETF",         "ETF"),
    ("SMH",   "Semiconductor ETF",            "ETF"),
    ("SOXX",  "iShares Semiconductor ETF",    "ETF"),
    ("BOTZ",  "Global Robotics & AI ETF",     "ETF"),
    ("ROBO",  "ROBO Global Robotics ETF",     "ETF"),
    ("ICLN",  "Clean Energy ETF",             "ETF"),
    ("TAN",   "Solar Energy ETF",             "ETF"),
    ("FAN",   "Wind Energy ETF",              "ETF"),
    ("DRIV",  "Electric Vehicles ETF",        "ETF"),
    ("HACK",  "Cybersecurity ETF",            "ETF"),
    ("CIBR",  "First Trust Cybersecurity ETF","ETF"),
    ("SKYY",  "Cloud Computing ETF",          "ETF"),
    ("WCLD",  "WisdomTree Cloud Computing",   "ETF"),
    ("BITO",  "Bitcoin Strategy ETF",         "ETF"),
    ("IBIT",  "iShares Bitcoin ETF",          "ETF"),
    ("FBTC",  "Fidelity Bitcoin ETF",         "ETF"),

    # ── BIST ETF'LERİ (Borsa İstanbul) ───────────────────────────────────────
    ("GOLD.IS",   "Altın ETF (BIST)",        "BIST ETF"),
    ("GMSTR.IS",  "Altın Master Fon",        "BIST ETF"),
    ("SGOLD.IS",  "Serbest Altın Fon",       "BIST ETF"),
    ("DJIST.IS",  "Dow Jones İstanbul ETF",  "BIST ETF"),
    ("NFIST.IS",  "BIST 30 ETF",             "BIST ETF"),
    ("KGX30.IS",  "Katılım 30 ETF",          "BIST ETF"),

    # ── YATIRIM FONLARI (TEFAS — popüler fonlar) ──────────────────────────────
    # Not: Bu fonlar yfinance üzerinden direkt çekilemez, TEFAS API gerektirir.
    # Semboller bilgi amaçlıdır.
    ("AFA.F",   "Ak Portföy Birinci Fon",                "Yatırım Fonu"),
    ("AGF.F",   "Ak Portföy Gelir Amaçlı Fon",          "Yatırım Fonu"),
    ("AK1.F",   "Ak Portföy Para Piyasası Fonu",         "Yatırım Fonu"),
    ("AKC.F",   "Ak Portföy Hisse Senedi Fonu",          "Yatırım Fonu"),
    ("GAF.F",   "Garanti Portföy Hisse Fonu",            "Yatırım Fonu"),
    ("GBF.F",   "Garanti Portföy Birinci Fon",           "Yatırım Fonu"),
    ("GCF.F",   "Garanti Portföy Para Piyasası",         "Yatırım Fonu"),
    ("GAH.F",   "Garanti Portföy Altın Fonu",            "Yatırım Fonu"),
    ("IEF.F",   "İş Portföy Birinci Değişken Fon",       "Yatırım Fonu"),
    ("IPF.F",   "İş Portföy Para Piyasası Fonu",         "Yatırım Fonu"),
    ("IAF.F",   "İş Portföy Altın Fonu",                 "Yatırım Fonu"),
    ("IHF.F",   "İş Portföy Hisse Senedi Fonu",          "Yatırım Fonu"),
    ("YKF.F",   "Yapı Kredi Portföy Fon",                "Yatırım Fonu"),
    ("YKH.F",   "Yapı Kredi Portföy Hisse Fonu",         "Yatırım Fonu"),
    ("YKA.F",   "Yapı Kredi Portföy Altın Fonu",         "Yatırım Fonu"),
    ("DPF.F",   "Deniz Portföy Para Piyasası Fonu",      "Yatırım Fonu"),
    ("DAF.F",   "Deniz Portföy Altın Fonu",              "Yatırım Fonu"),
    ("DHF.F",   "Deniz Portföy Hisse Fonu",              "Yatırım Fonu"),
    ("FBF.F",   "Finans Portföy Birinci Fon",            "Yatırım Fonu"),
    ("FAF.F",   "Finans Portföy Altın Fonu",             "Yatırım Fonu"),
    ("FHF.F",   "Finans Portföy Hisse Fonu",             "Yatırım Fonu"),
    ("TBF.F",   "TSKB Portföy Birinci Fon",              "Yatırım Fonu"),
    ("ZPF.F",   "Ziraat Portföy Para Piyasası Fonu",     "Yatırım Fonu"),
    ("ZAF.F",   "Ziraat Portföy Altın Fonu",             "Yatırım Fonu"),
    ("ZHF.F",   "Ziraat Portföy Hisse Fonu",             "Yatırım Fonu"),
    ("ZBF.F",   "Ziraat Portföy BIST 30 Fonu",           "Yatırım Fonu"),
    ("VKF.F",   "Vakıf Portföy Para Piyasası Fonu",      "Yatırım Fonu"),
    ("VAF.F",   "Vakıf Portföy Altın Fonu",              "Yatırım Fonu"),
    ("VHF.F",   "Vakıf Portföy Hisse Fonu",              "Yatırım Fonu"),
    ("TFF.F",   "TEB Portföy Para Piyasası Fonu",        "Yatırım Fonu"),
    ("TAF.F",   "TEB Portföy Altın Fonu",                "Yatırım Fonu"),
    ("QNF.F",   "QNB Finans Portföy Fonu",               "Yatırım Fonu"),
    ("HLF.F",   "HSBC Portföy Para Piyasası Fonu",       "Yatırım Fonu"),

    # ── EMTİA / DİĞER ─────────────────────────────────────────────────────────
    ("GC=F",   "Altın Vadeli (COMEX)",     "Emtia"),
    ("SI=F",   "Gümüş Vadeli",            "Emtia"),
    ("CL=F",   "Ham Petrol (WTI) Vadeli", "Emtia"),
    ("BZ=F",   "Brent Petrol Vadeli",     "Emtia"),
    ("NG=F",   "Doğalgaz Vadeli",         "Emtia"),
    ("HG=F",   "Bakır Vadeli",            "Emtia"),
    ("ZW=F",   "Buğday Vadeli",           "Emtia"),
    ("ZS=F",   "Soya Fasulyesi Vadeli",   "Emtia"),

    # ── DÖVİZ ─────────────────────────────────────────────────────────────────
    ("EURUSD=X",  "Euro / USD",           "Döviz"),
    ("GBPUSD=X",  "Sterlin / USD",        "Döviz"),
    ("USDJPY=X",  "USD / Japon Yeni",     "Döviz"),
    ("USDTRY=X",  "USD / Türk Lirası",    "Döviz"),
    ("EURTRY=X",  "Euro / Türk Lirası",   "Döviz"),
    ("GBPTRY=X",  "Sterlin / TL",         "Döviz"),
    ("XAUUSD=X",  "Altın / USD (Spot)",   "Döviz"),
]

# Hızlı arama için (sembol, isim, kategori) tuple listesi
_SYMBOLS_FLAT = [(s, n, c) for s, n, c in ALL_SYMBOLS]

# Sadece sembol stringleri gereken yerler için
SYMBOL_LIST = [s for s, _, _ in ALL_SYMBOLS]

# Kategori renkleri
CAT_COLORS: dict[str, tuple[str, str]] = {
    "Kripto":       ("#ddf4ff", "#0550ae"),
    "BIST":         ("#dafbe1", "#1a7f37"),
    "ABD Hisse":    ("#fff8c5", "#9a6700"),
    "ETF":          ("#f3e8ff", "#6e40c9"),
    "BIST ETF":     ("#e6f4ea", "#2d6a4f"),
    "Yatırım Fonu": ("#fce8d0", "#c05621"),
    "Emtia":        ("#fff0f0", "#c0392b"),
    "Döviz":        ("#f0f4ff", "#2c3e7b"),
}


def search_symbols(query: str, limit: int = 20) -> list[tuple[str, str, str]]:
    """Sembol/isim/kategori içinde arama yapar. Boş query → tüm liste başı."""
    if not query:
        return _SYMBOLS_FLAT[:limit]
    q = query.upper()
    exact  = [t for t in _SYMBOLS_FLAT if t[0].upper().startswith(q)]
    sym    = [t for t in _SYMBOLS_FLAT if q in t[0].upper() and t not in exact]
    name   = [t for t in _SYMBOLS_FLAT if q in t[1].upper() and t not in exact and t not in sym]
    result = (exact + sym + name)[:limit]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# DATE PICKER
# ══════════════════════════════════════════════════════════════════════════════
class DatePicker(ctk.CTkFrame):
    """Gün / Ay / Yıl dropdown'larından oluşan tarih seçici — elle yazma yok."""

    MONTHS_TR = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]

    def __init__(self, master, initial_date: date = None,
                 min_year: int = 2020, max_year: int = 2035,
                 on_change: Callable = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_change_cb = on_change
        if initial_date is None:
            initial_date = date.today()

        self._day_var   = ctk.StringVar(value=str(initial_date.day))
        self._month_var = ctk.StringVar(value=self.MONTHS_TR[initial_date.month - 1])
        self._year_var  = ctk.StringVar(value=str(initial_date.year))

        _om_kw = dict(
            height=32, fg_color=BG_INPUT, button_color=BORDER,
            font=F_BODY, text_color=TEXT1,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT1,
        )

        ctk.CTkOptionMenu(self, variable=self._day_var,
                          values=[str(d) for d in range(1, 32)],
                          width=60, command=self._changed, **_om_kw
                          ).pack(side="left", padx=(0, 3))

        ctk.CTkOptionMenu(self, variable=self._month_var,
                          values=self.MONTHS_TR,
                          width=100, command=self._changed, **_om_kw
                          ).pack(side="left", padx=(0, 3))

        ctk.CTkOptionMenu(self, variable=self._year_var,
                          values=[str(y) for y in range(min_year, max_year + 1)],
                          width=78, command=self._changed, **_om_kw
                          ).pack(side="left")

    def _changed(self, _=None):
        if self._on_change_cb:
            self._on_change_cb(self.get_date())

    def get_date(self) -> Optional[date]:
        try:
            day   = int(self._day_var.get())
            month = self.MONTHS_TR.index(self._month_var.get()) + 1
            year  = int(self._year_var.get())
            day   = min(day, calendar.monthrange(year, month)[1])
            return date(year, month, day)
        except Exception:
            return None

    def set_date(self, d: date):
        self._day_var.set(str(d.day))
        self._month_var.set(self.MONTHS_TR[d.month - 1])
        self._year_var.set(str(d.year))


# ══════════════════════════════════════════════════════════════════════════════
# SMART SEARCH ENTRY
# ══════════════════════════════════════════════════════════════════════════════
class SmartSearchEntry(ctk.CTkFrame):
    """
    Akıllı sembol arama kutusu:
      • Tıklayınca hemen tüm listeyi gösterir (ilk 20)
      • Yazınca sembol/isim/kategori içinde daraltır
      • Kategori renk badge'i gösterir
      • Enter veya tıklama ile seçer
    """

    def __init__(self, master, width: int = 300,
                 on_select: Callable[[str, str, str], None] = None,
                 placeholder: str = "Sembol ara... (BTC-USD, THYAO.IS, AAPL...)",
                 **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_select  = on_select
        self._dropdown   = None
        self._width      = width
        self._selected   = None   # son seçilen (symbol, name, cat)

        self._var = ctk.StringVar()
        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            width=width, height=36,
            fg_color=BG_INPUT, border_color=BORDER,
            font=("Segoe UI", 11, "bold"),
            text_color=TEXT1,
            placeholder_text=placeholder,
        )
        self._entry.pack(fill="x")

        self._var.trace_add("write", self._on_type)
        self._entry.bind("<FocusIn>",  self._on_focus_in)
        self._entry.bind("<FocusOut>", lambda e: self.after(180, self._hide))
        self._entry.bind("<Return>",   self._on_enter)
        self._entry.bind("<Escape>",   lambda e: self._hide())
        self._entry.bind("<Down>",     self._focus_first)

    # ── Events ────────────────────────────────────────────────────────────────
    def _on_focus_in(self, _=None):
        """Tıklandığında dropdown'ı göster."""
        self._show_dropdown(self._var.get().strip())

    def _on_type(self, *_):
        q = self._var.get().strip()
        self._show_dropdown(q)

    def _on_enter(self, _=None):
        q = self._var.get().strip().upper()
        hits = search_symbols(q, 1)
        if hits:
            self._select(*hits[0])
        self._hide()

    def _focus_first(self, _=None):
        if self._dropdown:
            children = self._dropdown.winfo_children()
            if children:
                children[0].focus_set()

    # ── Dropdown ──────────────────────────────────────────────────────────────
    def _show_dropdown(self, query: str):
        hits = search_symbols(query, 20)
        if not hits:
            self._hide()
            return

        # Destroy old dropdown
        self._hide(force=True)

        # Create new dropdown attached to root window
        root = self.winfo_toplevel()
        self._dropdown = ctk.CTkFrame(
            root,
            fg_color=BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
        )

        # Scrollable inner frame
        inner = ctk.CTkScrollableFrame(
            self._dropdown,
            fg_color="transparent",
            scrollbar_button_color=BORDER,
        )
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        _last_cat = None
        for sym, name, cat in hits:
            # Category header
            if cat != _last_cat:
                cat_bg, cat_fg = CAT_COLORS.get(cat, (BG_INPUT, TEXT2))
                ctk.CTkLabel(
                    inner,
                    text=f"  {cat}",
                    font=("Segoe UI", 9, "bold"),
                    text_color=cat_fg,
                    fg_color=cat_bg,
                    corner_radius=0,
                    height=20,
                    anchor="w",
                ).pack(fill="x", pady=(2, 0))
                _last_cat = cat

            row = ctk.CTkFrame(inner, fg_color="transparent", cursor="hand2")
            row.pack(fill="x", pady=0)

            # Highlight symbol
            ctk.CTkLabel(
                row,
                text=sym,
                font=("Segoe UI", 10, "bold"),
                text_color=TEXT1,
                width=90,
                anchor="w",
            ).pack(side="left", padx=(6, 0))
            ctk.CTkLabel(
                row,
                text=name,
                font=F_TINY,
                text_color=TEXT2,
                anchor="w",
            ).pack(side="left", padx=4)

            # Bind click
            _sym, _name, _cat = sym, name, cat
            for widget in (row,):
                widget.bind("<Button-1>", lambda e, s=_sym, n=_name, c=_cat: self._select(s, n, c))
                widget.bind("<Enter>",    lambda e, w=widget: w.configure(fg_color=BG_INPUT))
                widget.bind("<Leave>",    lambda e, w=widget: w.configure(fg_color="transparent"))

            # Also bind labels inside row
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, s=_sym, n=_name, c=_cat: self._select(s, n, c))

        # Position below entry
        self._entry.update_idletasks()
        root.update_idletasks()
        ex = self._entry.winfo_rootx() - root.winfo_rootx()
        ey = (self._entry.winfo_rooty() - root.winfo_rooty()
              + self._entry.winfo_height() + 2)
        ew = max(self._width, self._entry.winfo_width())
        n  = len(hits)
        # Estimate height: ~22px per item + ~18px per category header
        cats = len(set(c for _, _, c in hits))
        est_h = min(n * 24 + cats * 22 + 8, 340)

        self._dropdown.place(x=ex, y=ey, width=ew, height=est_h)
        self._dropdown.lift()

    def _hide(self, force=False):
        if self._dropdown:
            try:
                self._dropdown.place_forget()
                self._dropdown.destroy()
            except Exception:
                pass
            self._dropdown = None

    def _select(self, sym: str, name: str, cat: str):
        self._var.set(sym)
        self._selected = (sym, name, cat)
        self._hide()
        if self._on_select:
            self._on_select(sym, name, cat)

    # ── Public API ────────────────────────────────────────────────────────────
    def get(self) -> str:
        return self._var.get().strip().upper()

    def set(self, v: str):
        self._var.set(v)
        self._hide()

    def get_selected(self) -> Optional[tuple[str, str, str]]:
        """(symbol, name, category) veya None."""
        return self._selected


# ══════════════════════════════════════════════════════════════════════════════
# TOOLTIP SİSTEMİ
# ══════════════════════════════════════════════════════════════════════════════

# ── Terim açıklamaları sözlüğü ────────────────────────────────────────────────
TOOLTIPS: dict[str, str] = {

    # ── Genel Kararlar ────────────────────────────────────────────────────────
    "BUY":
        "AL sinyali — Analizler bu varlığın değer kazanabileceğine işaret ediyor.\n"
        "Bu bir garanti değil, istatistiksel bir eğilimdir.",
    "SELL":
        "SAT sinyali — Analizler bu varlığın değer kaybedebileceğine işaret ediyor.\n"
        "Elinde varsa satmayı, yoksa alım yapmamayı önerir.",
    "HOLD":
        "BEKLE sinyali — Ne almak ne satmak için net bir gerekçe yok.\n"
        "Mevcut pozisyonu korumak veya beklemek mantıklı.",

    # ── Güven ve Puanlar ─────────────────────────────────────────────────────
    "Güven":
        "Kararın ne kadar güvenilir olduğunun yüzdesi.\n"
        "%70+ güçlü sinyal, %50 altı zayıf sinyal anlamına gelir.\n"
        "Düşük güven = piyasa kararsız veya veri yetersiz.",
    "Kompozit Skor":
        "Tüm analizlerin (teknik + fundamental + haber + makro) birleşik puanı.\n"
        "0–100 arası. 60+ AL bölgesi, 40 altı SAT bölgesi.",
    "Teknik Skor":
        "Grafik ve fiyat hareketlerine dayalı puan.\n"
        "RSI, MACD, EMA, Bollinger Bantları gibi göstergelerden hesaplanır.\n"
        "Yüksek = teknik tablo olumlu.",
    "Fundamental Skor":
        "Şirketin mali durumuna (bilanço, kâr, büyüme) dayalı puan.\n"
        "Kripto için bu skor genellikle 50 sabit kalır (temel veri yok).",
    "Sentiment Skor":
        "Haberlerdeki ve sosyal medyadaki genel duygu analizi puanı.\n"
        "Yüksek = haberler olumlu, düşük = haberler olumsuz.",
    "Makro Skor":
        "Faiz oranı, dolar endeksi, altın gibi küresel ekonomik göstergelerin puanı.\n"
        "Makro ortam kötüyse en iyi hisse bile baskı altında kalabilir.",
    "On-Chain Skor":
        "Kripto paralar için blockchain üzerindeki gerçek işlem ve cüzdan verisi puanı.\n"
        "Borsalardan kripto çıkışı artıyorsa (HOLD için iyi işaret) gibi sinyaller içerir.",

    # ── Teknik İndikatörler ───────────────────────────────────────────────────
    "RSI":
        "Göreceli Güç Endeksi (Relative Strength Index) — 0 ile 100 arasında.\n"
        "▸ 70 üzeri: Aşırı alım — fiyat çok hızlı yükseldi, düzeltme gelebilir.\n"
        "▸ 30 altı: Aşırı satım — fiyat çok düştü, toparlanma gelebilir.\n"
        "▸ 30–70 arası: Normal bölge.",
    "RSI (14)":
        "Son 14 günün kapanış fiyatlarından hesaplanan RSI değeri.\n"
        "70 üzeri = aşırı alım (dikkat!), 30 altı = aşırı satım (fırsat olabilir).",
    "MACD":
        "Hareketli Ortalama Yakınsama/Iraksama (Moving Average Convergence Divergence).\n"
        "İki farklı hareketli ortalamanın farkından oluşur.\n"
        "▸ MACD > 0 ve yukarı kesim: Yükseliş sinyali\n"
        "▸ MACD < 0 ve aşağı kesim: Düşüş sinyali",
    "MACD Hist":
        "MACD Histogramı — MACD çizgisi ile sinyal çizgisi arasındaki fark.\n"
        "Pozitif ve büyüyorsa momentum güçleniyor, negatife dönerse zayıflıyor.",
    "EMA 20":
        "20 Günlük Üssel Hareketli Ortalama.\n"
        "Son 20 günün ağırlıklı fiyat ortalaması. Kısa vadeli trend gösterir.\n"
        "Fiyat EMA20 üzerindeyse kısa vadeli trend YUKARI.",
    "EMA 50":
        "50 Günlük Üssel Hareketli Ortalama.\n"
        "Orta vadeli trendi gösterir. Fiyat EMA50 üzerindeyse trend sağlıklı.",
    "EMA 200":
        "200 Günlük Üssel Hareketli Ortalama.\n"
        "Uzun vadeli ana trendi gösterir. 'Altın kesişim' olarak bilinir.\n"
        "Fiyat EMA200 üzerindeyse uzun vadeli BOĞA piyasası.",
    "BB Pozisyon":
        "Bollinger Bantları içindeki konum (0%–100%).\n"
        "▸ %80 üzeri: Üst banda yakın — aşırı alım olabilir.\n"
        "▸ %20 altı: Alt banda yakın — aşırı satım, toparlanma ihtimali.\n"
        "▸ %50 civarı: Ortabant — nötr.",
    "Hacim Oranı":
        "Bugünkü işlem hacminin son 20 günün ortalamasına oranı.\n"
        "▸ 2x = ortalamadan 2 kat fazla işlem → fiyat hareketini teyit eder.\n"
        "▸ 0.5x = işlem az → hareket güvenilir olmayabilir.",
    "Trend":
        "Fiyatın genel yönü.\n"
        "▸ UPTREND: Fiyat yükseliş eğiliminde\n"
        "▸ DOWNTREND: Fiyat düşüş eğiliminde\n"
        "▸ SIDEWAYS: Fiyat yatay seyrediyor",
    "Kırılım":
        "Fiyatın önemli bir direnç seviyesini yukarı kırdığını gösterir.\n"
        "Kırılım + yüksek hacim = güçlü yükseliş sinyali.",

    # ── Fiyat Seviyeleri ──────────────────────────────────────────────────────
    "Giriş":
        "Önerilen alım fiyatı.\n"
        "Bu seviyede veya altında alım yapmak daha iyi risk/ödül oranı sağlar.",
    "Stop-Loss":
        "Zarar kes seviyesi — fiyat buraya düşerse pozisyonu kapat.\n"
        "Sermayeni korumak için kritik. Bu seviyeyi asla görmezden gelme!\n"
        "Örnek: 100$'a aldın, stop-loss 92$ → maksimum %8 kayıpla çıkarsın.",
    "Take-Profit 1":
        "1. Kâr al hedefi — ilk hedef fiyat.\n"
        "Pozisyonun bir kısmını burada satabilirsin (genellikle %30–50).",
    "Take-Profit 2":
        "2. Kâr al hedefi — orta vadeli hedef.\n"
        "Fiyat buraya ulaşırsa ek kâr realizasyonu yapabilirsin.",
    "Take-Profit 3":
        "3. Kâr al hedefi — en iyimser hedef.\n"
        "Gerçekleşme olasılığı daha düşük ama gerçekleşirse en yüksek kazanç.",

    # ── Pozisyon Boyutu ───────────────────────────────────────────────────────
    "Miktar":
        "Tavsiye edilen alım miktarı (adet veya lot).\n"
        "Portföy büyüklüğüne ve risk toleransına göre hesaplanmıştır.",
    "Dolar Değeri":
        "Tavsiye edilen pozisyonun toplam dolar karşılığı.\n"
        "Portföyünün ne kadarını bu varlığa yatırman gerektiğini gösterir.",
    "Risk Tutarı":
        "Bu işlemde kaybedebileceğin maksimum miktar (stop-loss'a göre).\n"
        "Portföyünün %1–2'sini aşmaması önerilir.",
    "R:R (TP1)":
        "Risk/Ödül Oranı — 1. hedefe göre.\n"
        "▸ 1:2 = 1 birim riske karşılık 2 birim kazanç potansiyeli\n"
        "▸ 1:3 ve üzeri iyi bir oran sayılır.\n"
        "▸ 1:1 altı işlem yapmak mantıklı değil.",
    "Half-Kelly":
        "Kelly Kriteri'nin yarısı kadar pozisyon boyutu önerisi.\n"
        "Kelly = matematiksel olarak optimal bahis büyüklüğü formülü.\n"
        "Yarısını kullanmak riski azaltır, aşırı kayıpların önüne geçer.",

    # ── Portföy Metrikleri ────────────────────────────────────────────────────
    "Sharpe Oranı":
        "Alınan risk başına kazanılan getiri ölçütü.\n"
        "▸ 0 altı: Risksiz mevduattan bile kötü\n"
        "▸ 0–1 arası: Ortalama\n"
        "▸ 1–2 arası: İyi\n"
        "▸ 2 üzeri: Mükemmel\n"
        "Formül: (Getiri − Risksiz faiz) ÷ Volatilite",
    "Sortino Oranı":
        "Sharpe gibi ama sadece KÖTÜ yönlü (aşağı) dalgalanmayı ölçer.\n"
        "Yükselen fiyat dalgalanmasını cezalandırmaz, daha adil bir ölçüttür.\n"
        "Sharpe'tan yüksekse varlık genellikle yukarı hareket ediyor.",
    "VaR %95":
        "Value at Risk — Değer Riski.\n"
        "Normal piyasa koşullarında 1 günde %95 ihtimalle\n"
        "kaybedebileceğin maksimum yüzde.\n"
        "Örnek: VaR %5 → günde en fazla %5 kayıp beklenir (20 günden 19'unda).",
    "CVaR":
        "Koşullu Değer Riski — VaR sınırı aşıldığında beklenen ortalama kayıp.\n"
        "Kötü senaryolarda gerçek kayıbın ne kadar olacağını tahmin eder.\n"
        "VaR'dan daha muhafazakâr bir risk ölçütüdür.",
    "Max Drawdown":
        "Tepe-dip arası en büyük düşüş yüzdesi.\n"
        "Tarihsel olarak bu varlık en kötüsünde ne kadar düştü?\n"
        "Örnek: %40 → zirve noktasından dibe %40 düşmüş demek.\n"
        "Yatırımcının ne kadar dayanabileceğini anlamak için kritik.",
    "Max Drawdown (Tarihsel)":
        "Bu varlığın geçmişte yaşadığı en büyük tepe-dip düşüşü.\n"
        "Gelecekte benzer bir düşüş yaşanabilir. Hazır mısın?",
    "Korelasyon Skoru":
        "Portföydeki varlıkların birbirinden ne kadar bağımsız hareket ettiği.\n"
        "▸ Yüksek skor: Varlıklar birlikte hareket etmiyor (iyi çeşitlendirme)\n"
        "▸ Düşük skor: Hepsi aynı yönde hareket ediyor (risk artıyor)",
    "Portföy Volatilitesi":
        "Portföyün fiyatının ne kadar dalgalandığının yıllık yüzdesi.\n"
        "Düşük = daha sakin, yüksek = daha heyecanlı ama riskli.",
    "Allokasyon Güveni":
        "Portföy dağılımının ne kadar optimal olduğuna dair güven puanı.\n"
        "Korelasyon, volatilite ve çeşitlendirme faktörlerine göre hesaplanır.",

    # ── Projeksiyon / Monte Carlo ─────────────────────────────────────────────
    "Monte Carlo":
        "1000 farklı rastgele fiyat senaryosu simüle edilerek\n"
        "olası sonuçların dağılımı hesaplanır.\n"
        "Gelecek tahmin edilemez ama olasılık dağılımı ortaya konabilir.",
    "5. Persentil (En Kötü %5)":
        "1000 simülasyonun en kötü %5'inin sınırı.\n"
        "100 senaryonun 5'i bu değerin altında kaldı — kötü senaryo tahmini.",
    "50. Persentil (Medyan)":
        "Ortanca sonuç — 1000 simülasyonun tam ortası.\n"
        "Beklenen 'tipik' sonucu temsil eder.",
    "95. Persentil (En İyi %5)":
        "1000 simülasyonun en iyi %5'inin sınırı — iyimser senaryo.",
    "Kârlı Çıkma Olasılığı":
        "1000 simülasyonun kaçında pozitif getiri elde edildi?\n"
        "%55 üzeri = olasılıklar lehine, %45 altı = aleyhine.",
    "Ortalama Beklenen Getiri":
        "Tüm Monte Carlo simülasyonlarının getiri ortalaması.\n"
        "Medyandan farklıdır — uç senaryolar ortalaayı etkileyebilir.",
    "Yıllık Volatilite":
        "Fiyatın bir yıl içinde ne kadar dalgalanabileceği (standart sapma).\n"
        "▸ %5–15: Düşük risk (tahvil, altın benzeri)\n"
        "▸ %15–30: Orta risk (hisseler)\n"
        "▸ %50+: Yüksek risk (kripto)",
    "Günlük Volatilite":
        "Fiyatın bir günde ne kadar dalgalanabileceği.\n"
        "Yıllık volatilite ÷ √252 ile hesaplanır.",
    "Sharpe (Tahmin)":
        "Beklenen risk/ödül oranı tahmini.\n"
        "1'in üzeri: iyi, 2'nin üzeri: mükemmel, 0'ın altı: mevduatı yerine geçemiyor.",
    "SPY'e Karşı Avantaj":
        "Baz senaryodaki beklenen getirinin S&P 500 endeksine göre farkı.\n"
        "Pozitif = piyasa ortalamasını yenme potansiyeli var\n"
        "Negatif = neden SPY ETF almıyorsun?",

    # ── Conviction & Timing ───────────────────────────────────────────────────
    "Conviction Score":
        "Bu fırsata ne kadar güvenildiğinin birleşik puanı (0–100).\n"
        "▸ 70+: Yüksek güven — tüm göstergeler uyumlu\n"
        "▸ 40–70: Orta güven — bazı sinyaller çelişkili\n"
        "▸ 40 altı: Düşük güven — bekle veya küçük pozisyon al",
    "Timing Score":
        "Şu an giriş için doğru zaman mı? (0–100)\n"
        "▸ 70+: İyi zamanlama — teknik ve momentum uyumlu\n"
        "▸ 40 altı: Kötü zamanlama — 'doğru varlık, yanlış zaman' durumu olabilir",
    "Zamanlama":
        "Mevcut piyasa koşullarında bu varlığa girmek için zamanlamanın kalitesi.\n"
        "RSI, Bollinger, momentum ve EMA pozisyonuna göre hesaplanır.",

    # ── Senaryo ──────────────────────────────────────────────────────────────
    "Boğa Senaryosu":
        "İyimser senaryo — her şeyin iyi gittiği durum.\n"
        "Genellikle %25–35 olasılık. Gerçekleşmesi için olumlu katalizörler gerekir.",
    "Baz Senaryo":
        "En olası senaryo — normal koşullar altında beklenen sonuç.\n"
        "Genellikle %40–50 olasılık. Planlamanı buna göre yap.",
    "Ayı Senaryosu":
        "Kötümser senaryo — olumsuz gelişmelerin yaşandığı durum.\n"
        "Genellikle %25–35 olasılık. Bu senaryoya dayanabilir misin?",
    "Katalizör":
        "Fiyatı önemli ölçüde etkileyebilecek beklenen olay veya gelişme.\n"
        "Örnek: faiz kararı, kazanç raporu, regülasyon haberi.",
    "İptal Olayı":
        "Bu gelişme yaşanırsa analiz geçersiz sayılır, pozisyondan çıkılır.\n"
        "Risk yönetiminin en önemli parçası: 'Ne zaman yanıldım?' sorusunun cevabı.",

    # ── Fırsatlar Sayfası ─────────────────────────────────────────────────────
    "Fırsat Kalitesi":
        "Bu yatırım fırsatının genel kalite puanı.\n"
        "Teknik + fundamental + sentiment skorlarının ağırlıklı ortalaması.",
    "Zamanlama Kalitesi":
        "Şu anki piyasa koşullarında bu fırsata girilmesi için zamanlamanın kalitesi.\n"
        "Yüksek = şu an ideal giriş noktası yakın.",
    "Risk/Ödül":
        "Stop-loss ile take-profit arasındaki oran.\n"
        "Ne kadar risk alıp ne kadar kazanabileceğinin karşılaştırması.\n"
        "1:3 ve üzeri = her 1 birim riske 3 birim kazanç potansiyeli.",
    "Portföy Uyumu":
        "Bu varlığın mevcut portföyünle ne kadar uyumlu olduğu.\n"
        "Yüksek korelasyonlu varlıklar düşük puan alır (çeşitlendirme azalır).",
    "Profil Uygunluğu":
        "Yatırımcı risk profilinle ne kadar eşleştiği.\n"
        "Muhafazakâr profil için kripto düşük puan alır.",
    "Alternatif Maliyet":
        "Bu varlığa yatırım yapmak yerine başka bir fırsatı kaçırıyor musun?\n"
        "Yüksek puan = bu fırsat alternatiflerine göre üstün.",

    # ── Backtest ──────────────────────────────────────────────────────────────
    "Toplam Getiri":
        "Backtest döneminde başlangıç sermayesine göre toplam kazanç/kayıp yüzdesi.",
    "Yıllık Getiri":
        "Toplam getiriyi yıl bazına indirgenmiş hali.\n"
        "Farklı vade uzunluklarını karşılaştırmak için kullanılır.",
    "Kazanma Oranı":
        "Kârlı kapanan işlemlerin toplam işlemlere oranı.\n"
        "%50 üzeri = işlemlerin çoğu kârlı. Tek başına yeterli değil;\n"
        "ortalama kazanç/kayıp büyüklüğü de önemli.",
    "Kâr Faktörü":
        "Toplam kâr ÷ Toplam kayıp.\n"
        "▸ 1'in altı: Strateji genel olarak kaybettiriyor\n"
        "▸ 1–1.5: Kırılgan kârlı\n"
        "▸ 1.5+: Sağlıklı kârlı strateji",
    "Ort. Kazanç":
        "Kârlı işlemlerde ortalama kazanç yüzdesi.",
    "Ort. Kayıp":
        "Zararlı işlemlerde ortalama kayıp yüzdesi.\n"
        "Ort. Kazanç > Ort. Kayıp olması önemlidir.",
}


class Tooltip:
    """
    Herhangi bir tkinter widget'ına mouse hover açıklaması ekler.

    Kullanım:
        lbl = ctk.CTkLabel(parent, text="RSI (14)")
        Tooltip(lbl, "RSI açıklaması buraya...")

        # ya da sözlükten anahtar ile:
        Tooltip.by_key(lbl, "RSI (14)")
    """

    _BG   = "#1f2328"   # koyu arka plan
    _FG   = "#ffffff"   # beyaz metin
    _FONT = ("Segoe UI", 10)
    _PAD  = 10
    _WRAP = 340

    def __init__(self, widget, text: str, delay_ms: int = 500):
        self._widget   = widget
        self._text     = text
        self._delay    = delay_ms
        self._tip_win  = None
        self._after_id = None

        widget.bind("<Enter>",    self._on_enter, add="+")
        widget.bind("<Leave>",    self._on_leave, add="+")
        widget.bind("<Button-1>", self._on_leave, add="+")

    @classmethod
    def by_key(cls, widget, key: str, delay_ms: int = 500) -> "Tooltip | None":
        """Sözlükten anahtar ile tooltip ekle. Anahtar yoksa sessizce geç."""
        text = TOOLTIPS.get(key)
        if text:
            return cls(widget, text, delay_ms)
        return None

    def _on_enter(self, event=None):
        self._after_id = self._widget.after(self._delay, self._show)

    def _on_leave(self, event=None):
        if self._after_id:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._hide()

    def _show(self):
        if self._tip_win:
            return
        try:
            import tkinter as tk
            x = self._widget.winfo_rootx() + 20
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

            self._tip_win = tk.Toplevel(self._widget)
            self._tip_win.wm_overrideredirect(True)
            self._tip_win.wm_attributes("-topmost", True)
            self._tip_win.configure(bg=self._BG)

            # Çerçeve
            frame = tk.Frame(self._tip_win, bg=self._BG, padx=self._PAD, pady=6)
            frame.pack()

            lbl = tk.Label(
                frame,
                text=self._text,
                font=self._FONT,
                bg=self._BG, fg=self._FG,
                justify="left",
                wraplength=self._WRAP,
            )
            lbl.pack()

            # Ekran sınırlarını aş
            self._tip_win.update_idletasks()
            tw = self._tip_win.winfo_width()
            th = self._tip_win.winfo_height()
            sw = self._widget.winfo_screenwidth()
            sh = self._widget.winfo_screenheight()
            if x + tw > sw:
                x = sw - tw - 8
            if y + th > sh:
                y = self._widget.winfo_rooty() - th - 4

            self._tip_win.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _hide(self):
        if self._tip_win:
            try:
                self._tip_win.destroy()
            except Exception:
                pass
            self._tip_win = None


def tip(widget, key_or_text: str) -> None:
    """
    Kısa yol: Tooltip(widget, metin) veya Tooltip.by_key(widget, anahtar).
    Otomatik olarak sözlükte arar; yoksa verilen metni direkt kullanır.
    """
    text = TOOLTIPS.get(key_or_text, key_or_text)
    Tooltip(widget, text)
