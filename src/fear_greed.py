"""
HedgeFund AI — Kripto Fear & Greed Index
Kaynak: alternative.me (ücretsiz, API key gerektirmez)
0  = Aşırı Korku (alım fırsatı)
100 = Aşırı Açgözlülük (dikkat)
"""

import logging
import time
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE = {"value": None, "label": None, "fetched_at": 0}
_TTL   = 3600  # 1 saat cache


def fetch_fear_greed() -> dict:
    now = time.time()
    if _CACHE["value"] is not None and (now - _CACHE["fetched_at"]) < _TTL:
        return dict(_CACHE)

    try:
        url = "https://api.alternative.me/fng/?limit=7&format=json"
        r   = requests.get(url, timeout=10)
        if r.status_code == 200:
            data    = r.json()["data"]
            current = data[0]
            history = [
                {"date":  datetime.fromtimestamp(int(d["timestamp"])).strftime("%d.%m"),
                 "value": int(d["value"]),
                 "label": d["value_classification"]}
                for d in data
            ]
            _CACHE.update({
                "value":     int(current["value"]),
                "label":     current["value_classification"],
                "history":   history,
                "fetched_at": now,
            })
            return dict(_CACHE)
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")

    return {"value": 50, "label": "Neutral", "history": []}


def fear_greed_signal(value: int) -> tuple[str, float]:
    """
    Returns (action_bias, score_adjustment)
    Contrarian: extreme fear → BUY bias, extreme greed → SELL bias
    """
    if value <= 20:
        return "STRONG_BUY",  +12.0
    elif value <= 35:
        return "BUY",          +6.0
    elif value >= 80:
        return "STRONG_SELL", -12.0
    elif value >= 65:
        return "SELL",         -6.0
    else:
        return "NEUTRAL",       0.0


def format_fear_greed(data: dict) -> str:
    v   = data.get("value", 50)
    lbl = data.get("label", "Neutral")

    bar_len  = 20
    filled   = int(v / 100 * bar_len)
    bar      = "█" * filled + "░" * (bar_len - filled)

    if v <= 20:    color_hint = "🔵 (Alım bölgesi)"
    elif v <= 35:  color_hint = "🟢 (Biraz korku)"
    elif v >= 80:  color_hint = "🔴 (Aşırı açgözlülük)"
    elif v >= 65:  color_hint = "🟠 (Dikkat)"
    else:          color_hint = "🟡 (Nötr)"

    return (
        f"😨 Fear & Greed: {v}/100 — {lbl} {color_hint}\n"
        f"   [{bar}]"
    )
