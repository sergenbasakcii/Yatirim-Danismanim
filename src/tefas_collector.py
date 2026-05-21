"""
HedgeFund AI — TEFAS Türk Yatırım Fonları
Tüm TEFAS fonlarını çeker, önbelleğe alır ve analiz için hazırlar.
"""

import json
import logging
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent.parent / "data" / "raw" / "tefas_cache.json"
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
CACHE_TTL  = 3600 * 6  # 6 saat

TEFAS_LIST_URL    = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"
TEFAS_DETAIL_URL  = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
TEFAS_HEADERS     = {
    "Content-Type":  "application/x-www-form-urlencoded;charset=UTF-8",
    "Origin":        "https://www.tefas.gov.tr",
    "Referer":       "https://www.tefas.gov.tr/TarihselVeriler.aspx",
    "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Fon kategorileri
FON_TIPLERI = {
    "HIS": "Hisse Senedi",
    "BOR": "Borçlanma Araçları",
    "KAR": "Karma",
    "PAR": "Para Piyasası",
    "ALT": "Altın",
    "EMT": "Emtia",
    "FON": "Fon Sepeti",
    "END": "Endeks",
    "KOR": "Koruma Amaçlı",
    "GAY": "Gayrimenkul",
    "YAB": "Yabancı Menkul",
    "TEC": "Teknoloji",
}


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data
        except Exception:
            pass
    return {}


def _save_cache(data: dict):
    data["ts"] = time.time()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"TEFAS cache save failed: {e}")


def fetch_all_funds(force_refresh: bool = False) -> pd.DataFrame:
    """Tüm TEFAS fon listesini ve son fiyatlarını döndürür."""
    cache = _load_cache()
    if not force_refresh and "funds" in cache:
        logger.info("TEFAS fund list loaded from cache")
        return pd.DataFrame(cache["funds"])

    today  = datetime.now().strftime("%d.%m.%Y")
    week   = (datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y")

    try:
        logger.info("Fetching TEFAS fund list...")
        payload = f"fontip=YAT&bastarih={week}&bittarih={today}&fonkod=&fonturkod="
        r = requests.post(TEFAS_LIST_URL, data=payload,
                          headers=TEFAS_HEADERS, timeout=30)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        raw = r.json()
        rows = raw.get("data", raw) if isinstance(raw, dict) else raw
        if not rows:
            raise Exception("Empty response")

        df = pd.DataFrame(rows)
        df = _clean_fund_df(df)
        cache["funds"] = df.to_dict(orient="records")
        _save_cache(cache)
        logger.info(f"Fetched {len(df)} TEFAS funds")
        return df

    except Exception as e:
        logger.error(f"TEFAS fetch failed: {e}")
        return _fallback_funds()


def fetch_fund_history(fund_code: str, days: int = 90) -> pd.DataFrame:
    """Tek bir fonun tarihsel fiyat verisini çeker."""
    end   = datetime.now().strftime("%d.%m.%Y")
    start = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")

    try:
        payload = (f"fontip=YAT&bastarih={start}&bittarih={end}"
                   f"&fonkod={fund_code}&fonturkod=")
        r = requests.post(TEFAS_DETAIL_URL, data=payload,
                          headers=TEFAS_HEADERS, timeout=20)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")

        raw  = r.json()
        rows = raw.get("data", raw) if isinstance(raw, dict) else raw
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Kolon eşleştirme
        col_map = {
            "TARIH": "date", "BIRIMPAYFIYATI": "price",
            "TEDPAYSAYISI": "shares", "PORTFOYBUYUKLUGU": "aum",
            "FONKODU": "code", "FONUNVAN": "title",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns},
                  inplace=True)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
            df = df.sort_values("date")
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce")

        return df

    except Exception as e:
        logger.error(f"TEFAS history fetch failed for {fund_code}: {e}")
        return pd.DataFrame()


def calculate_fund_returns(df: pd.DataFrame) -> dict:
    """Verilen tarihsel veri için getiri metriklerini hesaplar."""
    if df.empty or "price" not in df.columns:
        return {}

    prices = df["price"].dropna()
    if len(prices) < 2:
        return {}

    last = float(prices.iloc[-1])

    def ret(n_days):
        if len(prices) > n_days:
            old = float(prices.iloc[-(n_days + 1)])
            return round((last - old) / old * 100, 2) if old > 0 else None
        return None

    return {
        "current_price": round(last, 4),
        "return_1d":  ret(1),
        "return_1w":  ret(5),
        "return_1m":  ret(21),
        "return_3m":  ret(63),
        "return_6m":  ret(126),
        "return_1y":  ret(252),
    }


def _clean_fund_df(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {
        "FONKODU":           "code",
        "FONUNVAN":          "title",
        "BIRIMPAYFIYATI":    "price",
        "PORTFOYBUYUKLUGU":  "aum",
        "YATIRIMCIICIN1":    "return_1m",
        "YATIRIMCIICIN3":    "return_3m",
        "YATIRIMCIICIN6":    "return_6m",
        "YATIRIMCIICIN12":   "return_1y",
        "FONTURU":           "type_code",
        "FONTURACIKLAMA":    "type_name",
        "KURUCUADI":         "manager",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns},
              inplace=True)

    for col in ["price", "aum", "return_1m", "return_3m", "return_6m", "return_1y"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Deduplicate: en son tarih
    if "code" in df.columns:
        df = df.drop_duplicates(subset=["code"], keep="last")

    return df.reset_index(drop=True)


def _fallback_funds() -> pd.DataFrame:
    """API başarısız olursa popüler fonların statik listesi."""
    return pd.DataFrame([
        {"code": "AKB", "title": "Ak Portföy Hisse Senedi Fonu",         "type_name": "Hisse Senedi", "manager": "Ak Portföy"},
        {"code": "GAF", "title": "Garanti Portföy Altın Fonu",            "type_name": "Altın",        "manager": "Garanti Portföy"},
        {"code": "IPB", "title": "İş Portföy Para Piyasası Fonu",         "type_name": "Para Piyasası","manager": "İş Portföy"},
        {"code": "TTE", "title": "TEB Portföy Teknoloji Fonu",            "type_name": "Teknoloji",   "manager": "TEB Portföy"},
        {"code": "YAS", "title": "Yapı Kredi Portföy Hisse Senedi Fonu",  "type_name": "Hisse Senedi", "manager": "YKP"},
        {"code": "FBK", "title": "Fiba Portföy Karma Fonu",               "type_name": "Karma",       "manager": "Fiba Portföy"},
        {"code": "AFA", "title": "Ak Portföy Altın Fonu",                 "type_name": "Altın",       "manager": "Ak Portföy"},
        {"code": "NNF", "title": "NN Hayat Portföy Hisse Fonu",           "type_name": "Hisse Senedi","manager": "NN Portföy"},
    ])


def search_funds(df: pd.DataFrame, query: str = "",
                 fund_type: str = "", sort_by: str = "return_1y") -> pd.DataFrame:
    """Fonları filtrele ve sırala."""
    result = df.copy()

    if query:
        q = query.upper()
        mask = (
            result.get("code",  pd.Series()).str.upper().str.contains(q, na=False) |
            result.get("title", pd.Series()).str.upper().str.contains(q, na=False) |
            result.get("manager", pd.Series()).str.upper().str.contains(q, na=False)
        )
        result = result[mask]

    if fund_type and fund_type != "Tümü":
        if "type_name" in result.columns:
            result = result[result["type_name"].str.contains(fund_type, na=False)]

    if sort_by in result.columns:
        result = result.sort_values(sort_by, ascending=False, na_position="last")

    return result.reset_index(drop=True)
