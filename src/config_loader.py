"""
HedgeFund AI — Config Loader
---------------------------------
Loads `config/settings.yaml` and transparently overlays any
secret values from:

  1. Environment variables   (highest priority)
  2. Streamlit secrets       (st.secrets["api_keys"], st.secrets["telegram"])
  3. The YAML file itself    (fallback — should be EMPTY in git)

This lets us keep `config/settings.yaml` committed without secrets,
and inject real credentials via env or `.streamlit/secrets.toml`
in production.

Env var names follow `HFAI_<SECTION>_<KEY>` upper-snake convention:

  HFAI_API_KEYS_BINANCE_API_KEY
  HFAI_API_KEYS_BINANCE_SECRET
  HFAI_API_KEYS_FINNHUB
  HFAI_API_KEYS_NEWSAPI
  HFAI_API_KEYS_FRED
  HFAI_API_KEYS_GLASSNODE
  HFAI_TELEGRAM_BOT_TOKEN
  HFAI_TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml


# ── Path resolution: frozen exe vs source ──────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = _ROOT / "config" / "settings.yaml"


# Secret fields we will overlay. (section, key, env_var)
_SECRET_FIELDS = [
    ("api_keys", "binance_api_key", "HFAI_API_KEYS_BINANCE_API_KEY"),
    ("api_keys", "binance_secret",  "HFAI_API_KEYS_BINANCE_SECRET"),
    ("api_keys", "finnhub",         "HFAI_API_KEYS_FINNHUB"),
    ("api_keys", "newsapi",         "HFAI_API_KEYS_NEWSAPI"),
    ("api_keys", "fred",            "HFAI_API_KEYS_FRED"),
    ("api_keys", "glassnode",       "HFAI_API_KEYS_GLASSNODE"),
    ("telegram", "bot_token",       "HFAI_TELEGRAM_BOT_TOKEN"),
    ("telegram", "chat_id",         "HFAI_TELEGRAM_CHAT_ID"),
    ("alerts",   "smtp_host",       "HFAI_ALERTS_SMTP_HOST"),
    ("alerts",   "smtp_port",       "HFAI_ALERTS_SMTP_PORT"),
    ("alerts",   "smtp_user",       "HFAI_ALERTS_SMTP_USER"),
    ("alerts",   "smtp_pass",       "HFAI_ALERTS_SMTP_PASS"),
    ("alerts",   "alert_email",     "HFAI_ALERTS_ALERT_EMAIL"),
]


def _streamlit_secret(section: str, key: str) -> Any:
    """Return st.secrets[section][key] if available, else None.

    Safe to call when streamlit isn't running — returns None on any error.
    """
    try:
        import streamlit as st  # type: ignore
        if section in st.secrets and key in st.secrets[section]:
            return st.secrets[section][key]
    except Exception:
        return None
    return None


def _overlay_secrets(cfg: dict) -> dict:
    """Overlay env vars / streamlit secrets onto a loaded config dict."""
    for section, key, env_var in _SECRET_FIELDS:
        env_val = os.environ.get(env_var)
        secret_val = _streamlit_secret(section, key)
        override = env_val if env_val not in (None, "") else secret_val
        if override in (None, ""):
            continue
        cfg.setdefault(section, {})
        # Preserve numeric type for smtp_port
        if key == "smtp_port":
            try:
                override = int(override)
            except (TypeError, ValueError):
                pass
        cfg[section][key] = override
    return cfg


def load_settings(path: Path | str | None = None) -> dict:
    """Load settings.yaml and overlay env/streamlit secrets.

    Always returns a dict; missing file yields {} + secrets overlay.
    """
    p = Path(path) if path else CONFIG_PATH
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    return _overlay_secrets(cfg)


def save_settings(cfg: dict, path: Path | str | None = None) -> None:
    """Write cfg back to YAML, redacting any field currently sourced from
    env vars / streamlit secrets. Prevents the desktop "Save Settings"
    flow from accidentally persisting overlaid secrets into a committed file.
    """
    import copy
    p = Path(path) if path else CONFIG_PATH
    out = copy.deepcopy(cfg)
    for section, key, env_var in _SECRET_FIELDS:
        env_val = os.environ.get(env_var)
        secret_val = _streamlit_secret(section, key)
        if (env_val not in (None, "")) or (secret_val not in (None, "")):
            # Source is external — keep file blank so secrets stay out of git
            if section in out and key in out[section]:
                out[section][key] = "" if not isinstance(out[section][key], (int, float)) else 0
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(out, f, default_flow_style=False, allow_unicode=True)


# Convenience alias
load_config = load_settings
