"""
Yatırım Danışmanım — AI Commentary Layer
=========================================
Provider-agnostic natural-language commentary for the terminal.

Design goals
------------
• ZERO mandatory cost. Default provider is Google Gemini's FREE tier
  (Gemini Flash). The free tier hard-limits requests — when the quota is
  exceeded the API returns 429 and we fall back to the static engine.
  No credit card, no overage billing.
• Never crash the UI. If no key is configured, the network fails, or the
  quota is hit, every call returns ``{"ok": False, ...}`` and the caller
  shows its existing static text.
• Cheap by construction. Responses are cached (st.cache_data) so the same
  context never costs a second request, and a per-session rate guard caps
  the number of live calls.
• Swappable. ``_PROVIDER`` can later be pointed at Groq / Claude without
  touching call sites.

Key resolution order
--------------------
  1. env  GEMINI_API_KEY
  2. st.secrets["ai"]["gemini_key"]   (Streamlit Cloud panel)

Usage
-----
    from src.ai_commentary import ai_generate, ai_enabled
    res = ai_generate("BTC analizini yorumla", system="Sen bir analistsin")
    if res["ok"]:
        st.write(res["text"])      # AI output
    else:
        st.write(static_text)      # graceful fallback
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Provider config ───────────────────────────────────────────────────────────
_PROVIDER = "gemini"
_GEMINI_MODEL = "gemini-2.0-flash"        # free-tier, fast, good quality
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)
_TIMEOUT = 20            # seconds — fail fast, never hang the page
_MAX_CALLS_PER_SESSION = 40   # soft guard so a single session can't spam quota

# In-process call counter (resets on app restart / new worker)
_session_calls = {"n": 0, "blocked": False}


# ══════════════════════════════════════════════════════════════════════════════
# KEY RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════
def _get_key() -> str:
    """Resolve the Gemini API key from env or Streamlit secrets."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st  # local import keeps engine CLI-importable
        sec = st.secrets.get("ai", {})  # type: ignore[attr-defined]
        if sec:
            return str(sec.get("gemini_key", "")).strip()
    except Exception:
        pass
    return ""


def ai_enabled() -> bool:
    """True when a key is configured (does not guarantee quota is available)."""
    return bool(_get_key())


# ══════════════════════════════════════════════════════════════════════════════
# CORE CALL (uncached) — Gemini REST
# ══════════════════════════════════════════════════════════════════════════════
def _gemini_call(prompt: str, system: str, max_tokens: int,
                 temperature: float) -> dict:
    key = _get_key()
    if not key:
        return {"ok": False, "text": "", "source": "no_key"}

    # Per-session soft guard
    if _session_calls["n"] >= _MAX_CALLS_PER_SESSION:
        _session_calls["blocked"] = True
        return {"ok": False, "text": "", "source": "rate_guard"}

    url = _GEMINI_URL.format(model=_GEMINI_MODEL, key=key)
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]},
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "topP": 0.95,
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    try:
        _session_calls["n"] += 1
        r = requests.post(url, json=body, timeout=_TIMEOUT)
        if r.status_code == 429:
            logger.info("Gemini free-tier quota hit (429) — falling back.")
            return {"ok": False, "text": "", "source": "quota"}
        if r.status_code != 200:
            logger.warning("Gemini HTTP %s: %s", r.status_code, r.text[:200])
            return {"ok": False, "text": "", "source": f"http_{r.status_code}"}

        data = r.json()
        cands = data.get("candidates", [])
        if not cands:
            return {"ok": False, "text": "", "source": "empty"}
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            return {"ok": False, "text": "", "source": "empty"}
        return {"ok": True, "text": text, "source": "gemini"}

    except requests.Timeout:
        logger.warning("Gemini request timed out after %ss.", _TIMEOUT)
        return {"ok": False, "text": "", "source": "timeout"}
    except Exception as e:  # noqa: BLE001
        logger.warning("Gemini call failed: %s", e)
        return {"ok": False, "text": "", "source": "error"}


# ══════════════════════════════════════════════════════════════════════════════
# CACHED PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def _cached_generate(cache_key: str, prompt: str, system: str,
                     max_tokens: int, temperature: float) -> dict:
    """Streamlit-cached wrapper. ``cache_key`` makes identical contexts free."""
    try:
        import streamlit as st

        @st.cache_data(ttl=900, show_spinner=False)
        def _inner(_k: str, _p: str, _s: str, _mt: int, _t: float) -> dict:
            return _gemini_call(_p, _s, _mt, _t)

        return _inner(cache_key, prompt, system, max_tokens, temperature)
    except Exception:
        # No Streamlit runtime (CLI/tests) — call directly, no cache
        return _gemini_call(prompt, system, max_tokens, temperature)


def ai_generate(prompt: str,
                system: str = "",
                cache_key: Optional[str] = None,
                max_tokens: int = 320,
                temperature: float = 0.4) -> dict:
    """Generate a natural-language commentary.

    Returns ``{"ok": bool, "text": str, "source": str}``.
    On any failure ``ok`` is False and the caller should show static text.

    Parameters
    ----------
    prompt      : user content / context for the model
    system      : optional system instruction (persona + guardrails)
    cache_key   : stable string for caching (e.g. "dash:BTC:32:buy3"). If
                  None, the prompt itself is used as the key.
    max_tokens  : output cap (keeps responses tight + cheap)
    temperature : 0.0–1.0 creativity
    """
    if not _get_key():
        return {"ok": False, "text": "", "source": "no_key"}
    ck = cache_key or prompt
    return _cached_generate(ck, prompt, system, max_tokens, temperature)


# ── Shared persona / guardrails for the whole app ────────────────────────────
SYSTEM_ANALYST = (
    "Sen 'Yatırım Danışmanım' adlı kurumsal yatırım terminalinin yapay zekâ "
    "analiz motorusun. Türkçe, net, profesyonel ve öz yaz. Asla yatırım "
    "tavsiyesi/garantisi verme; olasılık ve risk dilini kullan. Sayısal "
    "bağlamı yorumla, uydurma veri ekleme. Kısa paragraf veya 2-3 madde halinde, "
    "abartısız ve sakin bir tonda konuş. Cümlelerin uygulanabilir olsun."
)
