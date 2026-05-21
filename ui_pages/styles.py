"""
HedgeFund AI — Institutional Design System
==========================================
Production-grade design tokens, CSS reset, Plotly theme and shared
primitives for an institutional investment-intelligence terminal.

Design language
---------------
- Deep graphite canvas, neutral elevated panels, cool neutral borders.
- Single primary accent: institutional steel blue (#5b8cff) for selection,
  focus, primary CTA. NEVER used for market direction.
- Amber (#f5b25b) reserved for AI / insight tags only.
- Semantic green / red / amber RESERVED for market direction (P&L, signals).
- Strict 4px grid. Stable type scale. Tabular numerics everywhere.
- Refined micro-motion. No ambient backgrounds, no toy gradients, no neon.

Token names and helper signatures are preserved for backwards compatibility
with the rest of `ui_pages/*`.
"""
from __future__ import annotations

import os
import sys
import math

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ══════════════════════════════════════════════════════════════════════════════
C = {
    # ── Canvas / surfaces ────────────────────────────────────────────────────
    "bg":            "#0a0d12",                      # graphite canvas
    "bg_elev":       "#11151c",                      # elevated panel
    "bg_glow":       "rgba(91,140,255,0.04)",        # subtle accent wash
    "surface":       "rgba(20,25,33,0.86)",          # card surface
    "surface_alt":   "rgba(15,19,26,0.70)",          # nested / subtle
    "sidebar":       "#07090d",                      # deeper than canvas

    # ── Borders / dividers ───────────────────────────────────────────────────
    "border":        "rgba(148,163,184,0.08)",       # neutral cool
    "border_strong": "rgba(148,163,184,0.18)",       # hover / active
    "border_cool":   "rgba(148,163,184,0.10)",       # alias
    "divider":       "rgba(148,163,184,0.06)",       # internal divider
    "border_solid":  "#1a1f2a",                      # hard divider

    # ── Text ─────────────────────────────────────────────────────────────────
    "t1":            "#e6ebf2",                      # primary
    "t2":            "#94a3b8",                      # muted
    "t3":            "#64748b",                      # label / caption
    "t4":            "#475569",                      # faint / hint

    # ── Accent (institutional blue — sole UI accent) ────────────────────────
    "accent":        "#5b8cff",                      # primary accent
    "accent_hover":  "#7aa3ff",                      # hover lighter
    "accent_dim":    "rgba(91,140,255,0.10)",        # tint background
    "accent_glow":   "rgba(91,140,255,0.24)",        # focus ring
    "accent_deep":   "#3b6ee0",                      # darker (borders)
    "accent_warm":   "#7aa3ff",                      # back-compat alias

    # ── Secondary accent (amber — AI / insight tags ONLY) ───────────────────
    "accent2":       "#f5b25b",
    "accent2_dim":   "rgba(245,178,91,0.12)",

    # ── Semantic (market direction ONLY — never UI chrome) ──────────────────
    "buy":           "#22c55e",
    "sell":          "#ef4444",
    "warn":          "#f59e0b",
    "info":          "#5b8cff",
    "buy_dim":       "rgba(34,197,94,0.12)",
    "sell_dim":      "rgba(239,68,68,0.12)",
    "warn_dim":      "rgba(245,158,11,0.12)",
    "info_dim":      "rgba(91,140,255,0.12)",
}

# Decision pill mapping (BUY/HOLD/SELL family). BİRİKTİR = accent.
DEC_MAP = {
    "GÜÇLÜ AL":  {"col": C["buy"],    "dim": C["buy_dim"],    "label": "GÜÇLÜ AL"},
    "AL":        {"col": C["buy"],    "dim": C["buy_dim"],    "label": "AL"},
    "BİRİKTİR": {"col": C["accent"], "dim": C["accent_dim"], "label": "BİRİKTİR"},
    "İZLE":     {"col": C["warn"],   "dim": C["warn_dim"],   "label": "İZLE"},
    "TUTE":     {"col": C["t2"],     "dim": "rgba(148,163,184,0.10)", "label": "TUT"},
    "AZALT":    {"col": C["warn"],   "dim": C["warn_dim"],   "label": "AZALT"},
    "SAT":      {"col": C["sell"],   "dim": C["sell_dim"],   "label": "SAT"},
    "KAÇIN":    {"col": C["sell"],   "dim": C["sell_dim"],   "label": "KAÇIN"},
    "BUY":      {"col": C["buy"],    "dim": C["buy_dim"],    "label": "AL"},
    "SELL":     {"col": C["sell"],   "dim": C["sell_dim"],   "label": "SAT"},
    "HOLD":     {"col": C["t2"],     "dim": "rgba(148,163,184,0.10)", "label": "TUT"},
}


def get_all_symbols():
    try:
        from src.ui_widgets import ALL_SYMBOLS
        return ALL_SYMBOLS
    except Exception:
        return [("BTC-USD", "Bitcoin", "Kripto"), ("ETH-USD", "Ethereum", "Kripto")]


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
def inject_css():
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ════════════════════════════════════════════════════════════════════════════
   Yatırım Danışmanım — Institutional Terminal
   Graphite canvas · Steel blue accent · Strict 4px grid · Tabular numerics
   ════════════════════════════════════════════════════════════════════════════ */

/* ── Design Tokens (CSS variables — mirror of Python C dict) ──────────────── */
:root {{
  /* surfaces */
  --bg: {C['bg']};
  --bg-elev: {C['bg_elev']};
  --surface: {C['surface']};
  --surface-alt: {C['surface_alt']};
  --sidebar: {C['sidebar']};
  /* borders */
  --border: {C['border']};
  --border-strong: {C['border_strong']};
  --border-solid: {C['border_solid']};
  --divider: {C['divider']};
  /* text */
  --t1: {C['t1']};
  --t2: {C['t2']};
  --t3: {C['t3']};
  --t4: {C['t4']};
  /* accent */
  --accent: {C['accent']};
  --accent-hover: {C['accent_hover']};
  --accent-dim: {C['accent_dim']};
  --accent-glow: {C['accent_glow']};
  --accent-deep: {C['accent_deep']};
  /* secondary accent (AI tag only) */
  --accent2: {C['accent2']};
  --accent2-dim: {C['accent2_dim']};
  /* semantic (market direction only) */
  --buy: {C['buy']};
  --sell: {C['sell']};
  --warn: {C['warn']};
  --info: {C['info']};
  /* radius scale */
  --r-sm: 6px;
  --r-md: 8px;
  --r-lg: 10px;
  --r-xl: 12px;
  --r-pill: 999px;
  /* spacing scale (4px grid) */
  --s-1: 4px;  --s-2: 8px;  --s-3: 12px; --s-4: 16px;
  --s-5: 20px; --s-6: 24px; --s-8: 32px; --s-10: 40px;
  --s-12: 48px; --s-16: 64px;
  /* shadow scale */
  --sh-soft: 0 1px 2px rgba(0,0,0,0.20);
  --sh-card: 0 1px 0 rgba(255,255,255,0.04) inset, 0 4px 12px -4px rgba(0,0,0,0.40);
  --sh-elev: 0 12px 32px -12px rgba(0,0,0,0.60);
  --sh-focus: 0 0 0 3px {C['accent_glow']};
  /* motion */
  --ease: cubic-bezier(0.22, 0.61, 0.36, 1);
  --d-micro: 120ms;
  --d-default: 180ms;
  --d-modal: 240ms;
}}

@keyframes hfFadeUp {{
  from {{ opacity: 0; transform: translate3d(0,6px,0); }}
  to   {{ opacity: 1; transform: translate3d(0,0,0); }}
}}
@keyframes hfPulse {{
  0%, 100% {{ opacity: 0.85; }}
  50%      {{ opacity: 1; }}
}}
@keyframes hfShimmer {{
  0%   {{ background-position: -240px 0; }}
  100% {{ background-position:  240px 0; }}
}}
@keyframes hfTickerScroll {{
  0%   {{ transform: translateX(0); }}
  100% {{ transform: translateX(-33.333%); }}
}}

/* ── Reset & Base ─────────────────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; }}
html, body, .stApp {{
  background: {C["bg"]} !important;
  color: {C["t1"]} !important;
  font-family: "Inter Tight", "Inter", -apple-system, "SF Pro Text",
               "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
  font-feature-settings: "ss01", "cv11", "tnum" !important;
  font-variant-numeric: tabular-nums !important;
  letter-spacing: -0.005em !important;
}}

/* Mono used for numerics in dense tables */
.mono, .num {{
  font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace !important;
  font-feature-settings: "tnum" !important;
  font-variant-numeric: tabular-nums !important;
}}

/* Premium scrollbar */
::-webkit-scrollbar         {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track   {{ background: transparent; }}
::-webkit-scrollbar-thumb   {{
  background: rgba(148,163,184,0.16);
  border-radius: 8px;
  border: 2px solid {C["bg"]};
}}
::-webkit-scrollbar-thumb:hover {{ background: rgba(148,163,184,0.28); }}
* {{ scrollbar-color: rgba(148,163,184,0.16) transparent; scrollbar-width: thin; }}

::selection {{ background: {C["accent_glow"]}; color: {C["t1"]}; }}

/* ── Hide Streamlit chrome (but KEEP sidebar collapse controls) ────────── */
#MainMenu, footer,
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stMainMenu"],
[data-testid="stActionButtonIcon"],
[data-testid="stStatusWidget"],
[data-testid="stToolbarActions"],
.stDeployButton,
.stAppDeployButton,
button[kind="header"],
header [data-testid="baseButton-headerNoPadding"],
header [data-testid="baseButton-header"]      {{ display: none !important; }}

/* Header bar made transparent rather than removed so the sidebar
   collapse / expand button still receives clicks. */
[data-testid="stHeader"] {{
  background: transparent !important;
  height: 0 !important;
  min-height: 0 !important;
  border: none !important;
  box-shadow: none !important;
}}
[data-testid="stHeader"] > * {{ pointer-events: auto; }}

/* The collapsed-sidebar "expand" chevron — premium pill button.
   Bigger hit area + label so it's discoverable, not a lost arrow. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  z-index: 1000 !important;
  top: 16px !important;
  left: 16px !important;
}}
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="collapsedControl"] button {{
  background: linear-gradient(180deg,
              {C["bg_elev"]} 0%,
              rgba(15,19,26,0.96) 100%) !important;
  border: 1px solid {C["border_strong"]} !important;
  border-radius: 10px !important;
  color: {C["t1"]} !important;
  width: 38px !important;
  height: 38px !important;
  padding: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  box-shadow: 0 1px 0 rgba(255,255,255,0.05) inset,
              0 6px 18px -6px rgba(0,0,0,0.55) !important;
  transition: background 160ms var(--ease, ease),
              border-color 160ms var(--ease, ease),
              transform 120ms var(--ease, ease) !important;
}}
[data-testid="stSidebarCollapsedControl"] button:hover,
[data-testid="collapsedControl"] button:hover {{
  background: linear-gradient(180deg,
              {C["surface"]} 0%,
              {C["bg_elev"]} 100%) !important;
  border-color: {C["accent"]} !important;
  color: {C["accent_hover"]} !important;
  transform: translateY(-1px) !important;
}}
[data-testid="stSidebarCollapsedControl"] button svg,
[data-testid="collapsedControl"] button svg {{
  width: 18px !important;
  height: 18px !important;
  color: inherit !important;
  fill: currentColor !important;
}}

/* ── Content area ────────────────────────────────────────────────────────── */
.main .block-container {{
  max-width: 1480px !important;
  padding: 24px 32px 56px 32px !important;
  margin: 0 auto !important;
}}
@media (min-width: 1700px) {{
  .main .block-container {{ max-width: 1620px !important; }}
}}

/* ── RESPONSIVE — tablet (≤ 1024px) ──────────────────────────────────────── */
@media (max-width: 1024px) {{
  .main .block-container {{
    padding: 16px 16px 40px 16px !important;
  }}
  /* Tables / wide content: allow horizontal scroll instead of clipping */
  .dt, [data-testid="stDataFrame"], [data-testid="stTable"] {{
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }}
  /* KPI strip wraps */
  [data-testid="stHorizontalBlock"] {{
    flex-wrap: wrap !important;
    gap: 12px !important;
  }}
  [data-testid="stHorizontalBlock"] > div {{
    min-width: 200px !important;
  }}
}}

/* ── RESPONSIVE — mobile (≤ 640px) ───────────────────────────────────────── */
@media (max-width: 640px) {{
  .main .block-container {{
    padding: 12px 10px 32px 10px !important;
  }}
  /* Sidebar collapse control float higher / more reachable */
  [data-testid="stSidebarCollapsedControl"] {{
    top: 8px !important;
    left: 8px !important;
  }}
  /* Sidebar takes full width when expanded on mobile drawer */
  [data-testid="stSidebar"] {{
    min-width: 80vw !important;
    width: 80vw !important;
  }}
  /* Sidebar fixed footer: match drawer width, don't lock to 240px */
  [data-testid="stSidebar"] > div:last-child > div[style*="position:fixed"],
  [data-testid="stSidebarContent"] div[style*="position:fixed"] {{
    width: 80vw !important;
  }}
  /* KPI tiles: full-width single column */
  [data-testid="stHorizontalBlock"] > div {{
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }}
  /* Big numerics shrink one notch */
  .kpi-value {{ font-size: 22px !important; }}
  /* Page title scale-down */
  h1, .page-title {{ font-size: 20px !important; }}
  /* Hide non-critical kbd shortcuts on mobile */
  .kbd, [data-kbd] {{ display: none !important; }}
  /* Allow long tables to scroll horizontally */
  .dt-head, .dt-row {{
    min-width: 560px;
  }}
  .dt {{
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }}
}}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: {C["sidebar"]} !important;
  border-right: 1px solid {C["border_solid"]} !important;
  min-width: 240px !important;
  max-width: 240px !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 0 !important; }}
[data-testid="stSidebar"] * {{ color: {C["t1"]}; }}

[data-testid="stSidebar"] .stButton > button {{
  background: transparent !important;
  color: {C["t2"]} !important;
  border: none !important;
  border-left: 2px solid transparent !important;
  border-radius: 0 !important;
  text-align: left !important;
  padding: 9px 22px !important;
  font-size: 13.5px !important;
  font-weight: 500 !important;
  letter-spacing: -0.005em !important;
  width: 100% !important;
  box-shadow: none !important;
  text-transform: none !important;
  font-family: "Inter Tight", sans-serif !important;
  transition: background 160ms ease, color 160ms ease,
              border-color 160ms ease !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: rgba(148,163,184,0.04) !important;
  color: {C["t1"]} !important;
}}

/* ── Buttons (main area) ─────────────────────────────────────────────────── */
.stButton > button {{
  background: {C["accent"]} !important;
  color: #ffffff !important;
  border: 1px solid transparent !important;
  border-radius: 8px !important;
  padding: 8px 16px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  letter-spacing: -0.005em !important;
  text-transform: none !important;
  height: auto !important;
  min-height: 36px !important;
  font-family: "Inter Tight", sans-serif !important;
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.10) inset,
    0 1px 2px 0 rgba(0,0,0,0.30) !important;
  transition: background 140ms ease, box-shadow 140ms ease,
              transform 140ms ease, border-color 140ms ease !important;
}}
.stButton > button:hover {{
  background: {C["accent_hover"]} !important;
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.14) inset,
    0 0 0 3px {C["accent_glow"]},
    0 4px 12px -2px rgba(91,140,255,0.32) !important;
}}
.stButton > button:active {{
  background: {C["accent_deep"]} !important;
  transform: translateY(1px) !important;
}}
.stButton > button:focus-visible {{
  outline: none !important;
  box-shadow:
    0 0 0 2px {C["bg"]},
    0 0 0 4px {C["accent"]} !important;
}}

/* Secondary / ghost button */
.stButton > button[kind="secondary"] {{
  background: rgba(20,25,33,0.60) !important;
  color: {C["t1"]} !important;
  border: 1px solid {C["border_solid"]} !important;
  box-shadow: none !important;
}}
.stButton > button[kind="secondary"]:hover {{
  background: rgba(28,35,46,0.80) !important;
  border-color: {C["border_strong"]} !important;
  color: {C["t1"]} !important;
  box-shadow: none !important;
}}
.stButton > button[kind="secondary"]:active {{
  background: rgba(15,19,26,0.80) !important;
}}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stDateInput input,
textarea {{
  background: rgba(15,19,26,0.80) !important;
  border: 1px solid {C["border_solid"]} !important;
  border-radius: 8px !important;
  color: {C["t1"]} !important;
  font-size: 13.5px !important;
  font-family: "Inter Tight", sans-serif !important;
  box-shadow: none !important;
  transition: border-color 140ms ease, box-shadow 140ms ease,
              background 140ms ease !important;
}}
.stTextInput > div > div > input:hover,
.stNumberInput > div > div > input:hover,
.stDateInput input:hover {{ border-color: {C["border_strong"]} !important; }}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stDateInput input:focus,
textarea:focus {{
  border-color: {C["accent"]} !important;
  background: rgba(20,25,33,0.90) !important;
  box-shadow: 0 0 0 3px {C["accent_glow"]} !important;
}}
.stTextInput > div > div > input::placeholder,
textarea::placeholder {{ color: {C["t4"]} !important; }}

.stNumberInput button {{
  background: rgba(20,25,33,0.70) !important;
  color: {C["t2"]} !important;
  border: 1px solid {C["border_solid"]} !important;
  transition: background 140ms ease, color 140ms ease,
              border-color 140ms ease !important;
}}
.stNumberInput button:hover {{
  background: rgba(28,35,46,0.90) !important;
  color: {C["accent_hover"]} !important;
  border-color: {C["border_strong"]} !important;
}}

/* Widget labels — strict caps */
[data-testid="stWidgetLabel"],
.stTextInput label, .stNumberInput label,
.stSelectbox label, .stDateInput label {{
  color: {C["t3"]} !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  margin-bottom: 6px !important;
  font-family: "Inter Tight", sans-serif !important;
}}

/* ── Select ──────────────────────────────────────────────────────────────── */
[data-baseweb="select"] > div {{
  background: rgba(15,19,26,0.80) !important;
  border: 1px solid {C["border_solid"]} !important;
  border-radius: 8px !important;
  color: {C["t1"]} !important;
  font-size: 13.5px !important;
  box-shadow: none !important;
  transition: border-color 140ms ease, box-shadow 140ms ease !important;
}}
[data-baseweb="select"] > div:hover {{ border-color: {C["border_strong"]} !important; }}
[data-baseweb="select"] > div:focus-within {{
  border-color: {C["accent"]} !important;
  box-shadow: 0 0 0 3px {C["accent_glow"]} !important;
}}
[data-baseweb="popover"] {{
  background: {C["bg_elev"]} !important;
  border: 1px solid {C["border_strong"]} !important;
  border-radius: 10px !important;
  box-shadow:
    0 24px 56px -12px rgba(0,0,0,0.65),
    0 0 0 1px rgba(148,163,184,0.05) !important;
}}
[data-baseweb="option"] {{
  background: transparent !important;
  color: {C["t1"]} !important;
  font-size: 13.5px !important;
  transition: background 100ms ease !important;
}}
[data-baseweb="option"]:hover {{ background: rgba(148,163,184,0.06) !important; }}
[aria-selected="true"][data-baseweb="option"] {{
  background: {C["accent_dim"]} !important;
  color: {C["accent_hover"]} !important;
}}

/* ── Tabs → Segmented control ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
  background: rgba(15,19,26,0.70) !important;
  border: 1px solid {C["border_solid"]} !important;
  border-radius: 8px !important;
  padding: 3px !important;
  gap: 0 !important;
  box-shadow: 0 1px 0 0 rgba(255,255,255,0.02) inset !important;
}}
.stTabs [data-baseweb="tab"] {{
  background: transparent !important;
  color: {C["t2"]} !important;
  border-radius: 6px !important;
  padding: 6px 14px !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  letter-spacing: 0.005em !important;
  border: none !important;
  transition: background 140ms ease, color 140ms ease !important;
}}
.stTabs [data-baseweb="tab"]:hover {{
  background: rgba(148,163,184,0.06) !important;
  color: {C["t1"]} !important;
}}
.stTabs [aria-selected="true"] {{
  background: {C["accent"]} !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  box-shadow: 0 1px 2px 0 rgba(0,0,0,0.25) !important;
}}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{ display: none !important; }}

/* ── Streamlit Markdown text scale ───────────────────────────────────────── */
h1 {{
  font-family: "Inter Tight", sans-serif !important;
  font-size: 24px !important;
  font-weight: 700 !important;
  line-height: 1.20 !important;
  letter-spacing: -0.02em !important;
  color: {C["t1"]} !important;
  margin: 0 0 8px 0 !important;
}}
h2 {{
  font-size: 19px !important;
  font-weight: 600 !important;
  line-height: 1.25 !important;
  letter-spacing: -0.015em !important;
  color: {C["t1"]} !important;
  margin: 0 0 6px 0 !important;
}}
h3 {{ font-size: 16px !important; font-weight: 600 !important; color: {C["t1"]} !important; margin: 0 0 4px 0 !important; }}
h4 {{ font-size: 14px !important; font-weight: 600 !important; color: {C["t1"]} !important; margin: 0 0 4px 0 !important; }}

.stMarkdown p, .stMarkdown li {{
  color: {C["t2"]} !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
}}
.stMarkdown strong, .stMarkdown b {{ color: {C["t1"]} !important; font-weight: 600 !important; }}
.stMarkdown a {{ color: {C["accent_hover"]} !important; text-decoration: none !important; }}
.stMarkdown a:hover {{ color: {C["accent"]} !important; text-decoration: underline !important; }}
.stMarkdown code {{
  background: rgba(15,19,26,0.80) !important;
  border: 1px solid {C["border_solid"]} !important;
  border-radius: 4px !important;
  padding: 1px 6px !important;
  font-size: 12.5px !important;
  font-family: "JetBrains Mono", monospace !important;
  color: {C["accent_hover"]} !important;
}}

/* ── Card primitive ──────────────────────────────────────────────────────── */
.card {{
  background: {C["surface"]};
  border: 1px solid {C["border"]};
  border-radius: 10px;
  padding: 20px;
  position: relative;
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.02) inset,
    0 1px 2px 0 rgba(0,0,0,0.20);
  transition: border-color 180ms ease, box-shadow 180ms ease;
}}
.card:hover {{
  border-color: {C["border_strong"]};
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.03) inset,
    0 8px 24px -8px rgba(0,0,0,0.40);
}}
.card.flat {{ box-shadow: none; }}
.card.flat:hover {{ box-shadow: none; border-color: {C["border"]}; }}

.fade-up {{ animation: hfFadeUp 320ms cubic-bezier(0.2,0.7,0.3,1) both; }}

/* Global accessibility: respect reduced-motion preference everywhere */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }}
}}

/* ── Label / kicker ──────────────────────────────────────────────────────── */
.lbl, .kicker {{
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: {C["t3"]};
  margin: 0 0 6px 0;
  display: block;
  font-family: "Inter Tight", sans-serif;
}}

/* ── Pill ────────────────────────────────────────────────────────────────── */
.pill {{
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px; border-radius: 5px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.02em;
  border: 1px solid transparent;
  font-family: "Inter Tight", sans-serif;
  white-space: nowrap;
}}
.pill.neutral  {{ background: rgba(148,163,184,0.10); color: {C["t2"]};   border-color: rgba(148,163,184,0.18); }}
.pill.positive {{ background: {C["buy_dim"]};        color: {C["buy"]};   border-color: rgba(34,197,94,0.28); }}
.pill.negative {{ background: {C["sell_dim"]};       color: {C["sell"]};  border-color: rgba(239,68,68,0.28); }}
.pill.warn     {{ background: {C["warn_dim"]};       color: {C["warn"]};  border-color: rgba(245,158,11,0.28); }}
.pill.info     {{ background: {C["info_dim"]};       color: {C["info"]};  border-color: rgba(91,140,255,0.28); }}
.pill.accent   {{ background: {C["accent_dim"]};     color: {C["accent_hover"]}; border-color: rgba(91,140,255,0.28); }}
.pill.ai       {{ background: {C["accent2_dim"]};    color: {C["accent2"]}; border-color: rgba(245,178,91,0.28); }}

/* ── Status dot ──────────────────────────────────────────────────────────── */
.dot {{ width: 6px; height: 6px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
.dot.live {{
  background: {C["buy"]};
  box-shadow: 0 0 0 3px rgba(34,197,94,0.16);
  animation: hfPulse 2.4s ease-in-out infinite;
}}
.dot.idle  {{ background: {C["t3"]}; }}
.dot.warn  {{ background: {C["warn"]}; box-shadow: 0 0 0 3px rgba(245,158,11,0.16); }}
.dot.error {{ background: {C["sell"]}; box-shadow: 0 0 0 3px rgba(239,68,68,0.16); }}

/* ── Section header ──────────────────────────────────────────────────────── */
.section-head {{
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 16px; margin: 4px 0 12px 0;
}}
.section-head .title {{
  font-size: 14px; font-weight: 600; color: {C["t1"]};
  letter-spacing: -0.005em; line-height: 1.2;
  display: flex; align-items: center; gap: 8px;
}}
.section-head .title .accent-bar {{
  width: 3px; height: 14px; background: {C["accent"]}; border-radius: 2px;
}}
.section-head .meta {{
  font-size: 11.5px; color: {C["t3"]}; font-weight: 500;
  font-variant-numeric: tabular-nums;
}}

/* ── Data table ──────────────────────────────────────────────────────────── */
.dt {{
  width: 100%; border: 1px solid {C["border"]}; border-radius: 10px;
  overflow: hidden; background: {C["surface"]};
}}
.dt .dt-head, .dt .dt-row {{
  display: grid; align-items: center;
  padding: 10px 16px; gap: 12px;
}}
.dt .dt-head {{
  background: rgba(15,19,26,0.60);
  border-bottom: 1px solid {C["border_solid"]};
  font-size: 10.5px; font-weight: 600;
  letter-spacing: 0.10em; text-transform: uppercase; color: {C["t3"]};
}}
.dt .dt-row {{
  border-top: 1px solid {C["divider"]};
  font-size: 13px; color: {C["t1"]};
  transition: background 120ms ease;
}}
.dt .dt-row:first-of-type {{ border-top: none; }}
.dt .dt-row:hover {{ background: rgba(148,163,184,0.04); }}
.dt .right {{ text-align: right; font-variant-numeric: tabular-nums; }}
.dt .muted {{ color: {C["t2"]}; font-size: 12.5px; }}

/* ── KPI tile ────────────────────────────────────────────────────────────── */
.kpi {{
  background: {C["surface"]};
  border: 1px solid {C["border"]};
  border-radius: 10px;
  padding: 16px 18px 14px 18px;
  box-shadow: 0 1px 0 0 rgba(255,255,255,0.02) inset, 0 1px 2px 0 rgba(0,0,0,0.20);
  position: relative; overflow: hidden;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}}
.kpi:hover {{
  border-color: {C["border_strong"]};
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.03) inset,
    0 8px 22px -8px rgba(0,0,0,0.45);
}}
.kpi .kpi-label {{
  font-size: 10.5px; font-weight: 600; letter-spacing: 0.10em;
  text-transform: uppercase; color: {C["t3"]}; margin-bottom: 8px;
}}
.kpi .kpi-value {{
  font-size: 24px; font-weight: 700; color: {C["t1"]};
  letter-spacing: -0.02em; line-height: 1.05;
  font-variant-numeric: tabular-nums;
  margin-bottom: 6px;
}}
.kpi .kpi-row {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
.kpi .kpi-sub  {{ font-size: 12px; color: {C["t2"]}; }}
.kpi .kpi-spark {{ opacity: 0.85; }}

/* ── AI insight card ─────────────────────────────────────────────────────── */
.ai-card {{
  background: linear-gradient(180deg,
    rgba(245,178,91,0.05) 0%,
    rgba(15,19,26,0.0) 60%),
    {C["surface"]};
  border: 1px solid rgba(245,178,91,0.18);
  border-radius: 10px; padding: 16px 18px;
  position: relative;
}}
.ai-card .ai-tag {{
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 8px; border-radius: 4px;
  background: {C["accent2_dim"]}; color: {C["accent2"]};
  font-size: 10px; font-weight: 700; letter-spacing: 0.10em;
  text-transform: uppercase; margin-bottom: 10px;
  border: 1px solid rgba(245,178,91,0.28);
}}
.ai-card .ai-title {{ font-size: 14px; font-weight: 600; color: {C["t1"]}; margin-bottom: 6px; }}
.ai-card .ai-body  {{ font-size: 12.5px; color: {C["t2"]}; line-height: 1.55; }}

/* ── Skeleton ────────────────────────────────────────────────────────────── */
.skel {{
  background: linear-gradient(90deg,
    rgba(148,163,184,0.06) 0%,
    rgba(148,163,184,0.14) 50%,
    rgba(148,163,184,0.06) 100%);
  background-size: 480px 100%;
  border-radius: 6px;
  animation: hfShimmer 1.4s linear infinite;
}}

/* ── Empty state ─────────────────────────────────────────────────────────── */
.empty {{
  border: 1px dashed {C["border_strong"]};
  border-radius: 10px; padding: 32px 20px;
  text-align: center;
  background: rgba(15,19,26,0.40);
}}
.empty .empty-icon  {{ font-size: 22px; color: {C["t3"]}; margin-bottom: 8px; }}
.empty .empty-title {{ font-size: 14px; font-weight: 600; color: {C["t1"]}; margin-bottom: 4px; }}
.empty .empty-hint  {{ font-size: 12.5px; color: {C["t3"]}; }}

/* ── Warning bar ─────────────────────────────────────────────────────────── */
.warn-bar {{
  background: rgba(245,158,11,0.06);
  border: 1px solid rgba(245,158,11,0.20);
  border-left: 3px solid {C["warn"]};
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 12.5px; color: {C["t2"]};
  line-height: 1.5;
}}
.warn-bar b {{ color: {C["warn"]}; font-weight: 600; }}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-head {{
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 24px; flex-wrap: wrap;
  padding: 8px 0 18px 0;
  border-bottom: 1px solid {C["border_solid"]};
  margin-bottom: 22px;
}}
.page-head .ph-title {{
  font-family: "Inter Tight", sans-serif;
  font-size: 24px; font-weight: 700; color: {C["t1"]};
  letter-spacing: -0.02em; line-height: 1.15;
  margin-top: 4px;
}}
.page-head .ph-sub {{
  font-size: 13px; color: {C["t3"]}; margin-top: 4px;
  max-width: 720px; line-height: 1.55;
}}
.page-head .ph-status {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 10px; border-radius: 6px;
  background: rgba(34,197,94,0.06);
  border: 1px solid rgba(34,197,94,0.22);
  font-size: 10.5px; font-weight: 600; color: {C["buy"]};
  letter-spacing: 0.10em; text-transform: uppercase;
}}

/* ── Ticker strip ────────────────────────────────────────────────────────── */
.ticker-wrap {{
  overflow: hidden;
  background: {C["bg_elev"]};
  border-bottom: 1px solid {C["border_solid"]};
  height: 36px;
  display: flex; align-items: center;
  position: relative;
  margin: -16px -32px 20px -32px;
}}
.ticker-track {{
  display: flex; align-items: center;
  width: max-content;
  animation: hfTickerScroll 60s linear infinite;
  will-change: transform;
}}
.ticker-track:hover {{ animation-play-state: paused; }}
.ticker-wrap::before, .ticker-wrap::after {{
  content: ""; position: absolute; top: 0; bottom: 0; width: 56px;
  pointer-events: none; z-index: 2;
}}
.ticker-wrap::before {{ left: 0;  background: linear-gradient(90deg,  {C["bg_elev"]} 0%, transparent 100%); }}
.ticker-wrap::after  {{ right: 0; background: linear-gradient(270deg, {C["bg_elev"]} 0%, transparent 100%); }}
.ticker-chip {{
  display: flex; align-items: center; gap: 8px;
  padding: 0 18px; flex-shrink: 0; white-space: nowrap;
  border-right: 1px solid {C["divider"]};
}}
.ticker-chip .tk-sym {{ font-size: 11.5px; font-weight: 700; color: {C["t1"]}; letter-spacing: 0.04em; }}
.ticker-chip .tk-px  {{ font-size: 12px; color: {C["t2"]}; font-variant-numeric: tabular-nums; }}
.ticker-chip .tk-chg {{ font-size: 10.5px; font-weight: 600; padding: 1px 6px; border-radius: 4px; letter-spacing: 0.02em; }}
.ticker-chip .tk-chg.up   {{ background: {C["buy_dim"]};  color: {C["buy"]}; }}
.ticker-chip .tk-chg.down {{ background: {C["sell_dim"]}; color: {C["sell"]}; }}

/* ── Plotly hover labels ─────────────────────────────────────────────────── */
.hovertext, .hoverlayer text {{ font-family: "Inter Tight", sans-serif !important; }}

/* ── Streamlit alerts ────────────────────────────────────────────────────── */
[data-baseweb="notification"] {{
  background: {C["bg_elev"]} !important;
  border: 1px solid {C["border_solid"]} !important;
  border-radius: 8px !important;
}}

/* ── Misc tightening ─────────────────────────────────────────────────────── */
.row-gap-4 > div {{ gap: 4px !important; }}
hr {{ border: none !important; border-top: 1px solid {C["divider"]} !important; margin: 12px 0 !important; }}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PLOTLY THEME
# ══════════════════════════════════════════════════════════════════════════════
def apple_layout(**kw):
    """Institutional Plotly layout. Name kept for back-compat."""
    base = dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family='Inter Tight, Inter, -apple-system, sans-serif',
            color=C["t2"], size=11),
        margin=dict(l=8, r=8, t=12, b=4),
        xaxis=dict(
            gridcolor="rgba(148,163,184,0.05)",
            zerolinecolor="rgba(148,163,184,0.10)",
            linecolor="rgba(148,163,184,0.12)",
            showgrid=True,
            tickfont=dict(color=C["t3"], size=10),
            tickformat="~s",
        ),
        yaxis=dict(
            gridcolor="rgba(148,163,184,0.05)",
            zerolinecolor="rgba(148,163,184,0.10)",
            linecolor="rgba(148,163,184,0.12)",
            showgrid=True,
            tickfont=dict(color=C["t3"], size=10),
            tickformat="~s",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=C["border_solid"],
            font=dict(color=C["t2"], size=11),
        ),
        hoverlabel=dict(
            bgcolor=C["bg_elev"],
            bordercolor=C["border_strong"],
            font=dict(color=C["t1"], size=12,
                      family='Inter Tight, sans-serif'),
        ),
        colorway=[
            C["accent"],          # institutional blue
            C["accent2"],         # amber
            "#22c55e",            # green
            "#a78bfa",            # violet
            "#06b6d4",            # cyan
            "#ef4444",            # red
            C["accent_hover"],    # blue light
            "#f59e0b",            # amber-warm
        ],
    )
    base.update(kw)
    return base


def dark_layout(**kw):
    return apple_layout(**kw)


# ══════════════════════════════════════════════════════════════════════════════
# TICKER DATA + TICKER STRIP
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_ticker_data():
    pairs = [
        ("BTC-USD", "BTC"), ("ETH-USD", "ETH"), ("BNB-USD", "BNB"),
        ("SOL-USD", "SOL"), ("XRP-USD", "XRP"), ("THYAO.IS", "THYAO"),
        ("XU100.IS", "BIST"), ("GC=F", "ALTIN"),
    ]
    out = []
    try:
        import yfinance as yf
        for sym, lbl in pairs:
            try:
                fi = yf.Ticker(sym).fast_info
                p = fi.last_price or 0
                pv = fi.previous_close or p
                out.append(dict(sym=lbl, price=p,
                                chg=((p - pv) / pv * 100) if pv else 0))
            except Exception:
                out.append(dict(sym=lbl, price=0, chg=0))
    except Exception:
        pass
    return out


def _ticker_fp(p, s):
    if p <= 0:
        return "—"
    if s in ("THYAO", "BIST"):
        return f"₺{p:,.2f}" if p < 10000 else f"₺{p:,.0f}"
    if s == "ALTIN":
        return f"${p:,.0f}"
    return f"${p:,.2f}" if p < 1000 else f"${p:,.0f}"


def render_ticker():
    data = fetch_ticker_data()
    if not data:
        return

    def chip(d):
        cls = "up" if d["chg"] >= 0 else "down"
        arr = "+" if d["chg"] >= 0 else ""
        return (f'<div class="ticker-chip">'
                f'<span class="tk-sym">{d["sym"]}</span>'
                f'<span class="tk-px">{_ticker_fp(d["price"], d["sym"])}</span>'
                f'<span class="tk-chg {cls}">{arr}{d["chg"]:.2f}%</span>'
                f'</div>')

    chips = "".join(chip(d) for d in data)
    track = chips + chips + chips
    st.markdown(
        f'<div class="ticker-wrap"><div class="ticker-track">{track}</div></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════════════
def page_header(title: str, sub: str = ""):
    sub_html = f'<div class="ph-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="page-head fade-up">'
        f'  <div>'
        f'    <div class="lbl" style="margin-bottom:4px;">HEDGEFUND AI</div>'
        f'    <div class="ph-title">{title}</div>'
        f'    {sub_html}'
        f'  </div>'
        f'  <div class="ph-status">'
        f'    <span class="dot live"></span> CANLI VERİ'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# DECISION BADGE / SCORE / ARC / BAR / TRADE PLAN
# ══════════════════════════════════════════════════════════════════════════════
def dec_badge(decision: str, size: str = "md", active: bool = False) -> str:
    d = DEC_MAP.get(decision, DEC_MAP["İZLE"])
    fz = {"sm": "10.5px", "md": "11.5px", "lg": "12.5px"}.get(size, "11.5px")
    pad = {"sm": "2px 7px", "md": "3px 9px", "lg": "4px 12px"}.get(size, "3px 9px")
    border = f'1px solid {d["col"]}40'
    return (f'<span style="display:inline-flex;align-items:center;padding:{pad};'
            f'border-radius:5px;background:{d["dim"]};color:{d["col"]};'
            f'font-size:{fz};font-weight:700;letter-spacing:0.06em;'
            f'text-transform:uppercase;white-space:nowrap;border:{border};'
            f'font-family:Inter Tight,sans-serif;">{d["label"]}</span>')


def badge(action: str) -> str:
    m = {"BUY": "AL", "SELL": "SAT", "HOLD": "TUTE"}
    return dec_badge(m.get(action, action))


def score_ring(score: float, size: int = 44) -> str:
    r = (size - 6) / 2
    circ = 2 * math.pi * r
    col = C["buy"] if score >= 70 else C["warn"] if score >= 50 else C["sell"]
    fill = circ * (score / 100)
    cx = cy = size / 2
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
            f'style="transform:rotate(-90deg)">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{C["divider"]}" stroke-width="3"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{col}" stroke-width="3" '
            f'stroke-dasharray="{fill:.1f} {circ:.1f}" stroke-linecap="round"/>'
            f'<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
            f'fill="{col}" font-size="{int(size * 0.30)}" font-weight="700" '
            f'style="transform:rotate(90deg);transform-origin:center;'
            f'font-family:Inter Tight,sans-serif;">{score:.0f}</text></svg>')


def conviction_arc(conviction: float, timing: float, size: int = 120) -> str:
    def arc(cx, cy, r, pct, col, sw):
        c = 2 * math.pi * r
        f = c * min(max(pct / 100, 0), 1) / 2  # half circle
        e = c - f
        return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                f'stroke="{C["divider"]}" stroke-width="{sw}"/>'
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                f'stroke="{col}" stroke-width="{sw}" '
                f'stroke-dasharray="{f:.1f} {e:.1f}" stroke-linecap="round" '
                f'transform="rotate(-90 {cx} {cy})"/>')
    cx = cy = size // 2
    r1 = cx - 10
    r2 = r1 - 14
    c1 = C["buy"] if conviction >= 65 else C["warn"] if conviction >= 45 else C["sell"]
    c2 = C["info"] if timing >= 60 else C["warn"] if timing >= 40 else C["sell"]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'  {arc(cx, cy, r1, conviction, c1, 6)}'
            f'  {arc(cx, cy, r2, timing, c2, 4)}'
            f'  <text x="{cx}" y="{cy - 2}" text-anchor="middle" fill="{c1}" '
            f'font-size="18" font-weight="700" font-family="Inter Tight,sans-serif" '
            f'font-variant-numeric="tabular-nums">{conviction:.0f}</text>'
            f'  <text x="{cx}" y="{cy + 16}" text-anchor="middle" fill="{C["t3"]}" '
            f'font-size="9" font-weight="600" letter-spacing="0.10em" '
            f'font-family="Inter Tight,sans-serif">KONVİK</text>'
            f'</svg>')


def score_bar(label: str, value: float, max_val: float = 100) -> str:
    v = min(max(float(value or 0), 0), max_val)
    pct = v / max_val * 100
    col = C["buy"] if pct >= 65 else C["warn"] if pct >= 45 else C["sell"]
    return (f'<div style="margin-bottom:12px;">'
            f'  <div style="display:flex;justify-content:space-between;margin-bottom:5px;">'
            f'    <span style="font-size:12.5px;color:{C["t2"]};">{label}</span>'
            f'    <span style="font-size:12.5px;font-weight:700;color:{col};'
            f'font-variant-numeric:tabular-nums;">{v:.0f}</span>'
            f'  </div>'
            f'  <div style="height:4px;background:rgba(148,163,184,0.10);'
            f'border-radius:2px;overflow:hidden;">'
            f'    <div style="width:{pct:.1f}%;height:4px;background:{col};'
            f'border-radius:2px;transition:width 600ms ease;"></div>'
            f'  </div>'
            f'</div>')


def trade_plan_html(r, currency: str = "USD") -> str:
    price = getattr(r, "current_price", 0)
    el = getattr(r, "entry_zone_low",  None)
    eh = getattr(r, "entry_zone_high", None)
    sl = getattr(r, "stop_loss",  None)
    tp1 = getattr(r, "target_1",   None)
    tp2 = getattr(r, "target_2",   None)
    tp3 = getattr(r, "target_3",   None)

    entry = (f"{fmt_price(el, currency)} – {fmt_price(eh, currency)}"
             if el and eh else fmt_price(price, currency))

    def pct(target):
        return (f"<small style='color:{C['t3']};font-size:11px;margin-left:6px;'>"
                f"{(target - price) / price * 100:+.1f}%</small>") if target and price else ""

    rr = "—"
    if sl and tp1 and price:
        risk = abs(price - sl)
        reward = abs(tp1 - price)
        if risk > 0:
            rr = f"1 : {reward / risk:.1f}"

    cells = [
        ("Giriş Zonu",  entry,                                  C["t1"]),
        ("Stop Loss",   f"{fmt_price(sl, currency)}{pct(sl)}",  C["sell"]),
        ("Hedef 1",     f"{fmt_price(tp1, currency)}{pct(tp1)}", C["buy"]),
        ("Hedef 2",     f"{fmt_price(tp2, currency)}{pct(tp2)}", C["buy"]),
        ("Hedef 3",     f"{fmt_price(tp3, currency)}{pct(tp3)}", C["warn"]),
        ("Risk / Ödül", rr,                                     C["accent_hover"]),
    ]
    items = "".join(
        f'<div style="padding:12px 14px;background:{C["surface_alt"]};'
        f'border:1px solid {C["border"]};border-radius:8px;">'
        f'<div class="lbl" style="margin-bottom:6px;">{lbl}</div>'
        f'<div style="font-size:15px;font-weight:700;color:{col};'
        f'font-variant-numeric:tabular-nums;line-height:1.2;">{val}</div>'
        f'</div>' for lbl, val, col in cells
    )
    return (f'<div style="display:grid;grid-template-columns:repeat(6,1fr);'
            f'gap:10px;margin:12px 0;">{items}</div>')


def candle_chart(df, sym, ema20=None, ema50=None, ema200=None, height=420):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.02)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=sym,
        increasing=dict(line=dict(color=C["buy"],  width=1), fillcolor=C["buy"]),
        decreasing=dict(line=dict(color=C["sell"], width=1), fillcolor=C["sell"]),
        whiskerwidth=0.3,
    ), row=1, col=1)
    if ema20 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=ema20, name="EMA 20",
            line=dict(color=C["t3"], width=1, dash="dot")), row=1, col=1)
    if ema50 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=ema50, name="EMA 50",
            line=dict(color=C["accent"], width=1.2, dash="dot")), row=1, col=1)
    if ema200 is not None:
        fig.add_trace(go.Scatter(x=df.index, y=ema200, name="EMA 200",
            line=dict(color=C["accent2"], width=1.4)), row=1, col=1)
    vc = [C["buy"] if c >= o else C["sell"]
          for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color=vc, opacity=0.45, showlegend=False,
    ), row=2, col=1)
    layout = apple_layout(height=height, hovermode="x unified",
                          xaxis_rangeslider_visible=False)
    layout.pop("xaxis", None); layout.pop("yaxis", None)
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.05)", linecolor=C["border"],
                     showline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.05)", linecolor=C["border"],
                     showline=False)
    return fig


def radar_chart(dims: dict, size: int = 260) -> go.Figure:
    cats = list(dims.keys())
    vals = list(dims.values())
    fig = go.Figure(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself",
        fillcolor="rgba(91,140,255,0.12)",
        line=dict(color=C["accent"], width=1.5),
        marker=dict(color=C["accent"], size=4),
        hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(visible=True, range=[0, 100],
                            tickfont=dict(color=C["t3"], size=9),
                            gridcolor=C["border"], linecolor=C["border"]),
            angularaxis=dict(tickfont=dict(color=C["t2"], size=11),
                             gridcolor=C["border"], linecolor=C["border"]),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=20),
        height=size, showlegend=False,
        font=dict(color=C["t2"], family="Inter Tight, sans-serif"),
    )
    return fig


def spark_svg(values: list, width: int = 80, height: int = 28) -> str:
    if not values or len(values) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    mn, mx = min(values), max(values)
    rng = (mx - mn) if mx != mn else 1
    pad = 2
    ws = (width - pad * 2) / (len(values) - 1)
    pts = []
    for i, v in enumerate(values):
        x = pad + i * ws
        y = height - pad - ((v - mn) / rng) * (height - pad * 2)
        pts.append(f"{x:.1f},{y:.1f}")
    up = values[-1] >= values[0]
    col = C["buy"] if up else C["sell"]
    fcol = "rgba(34,197,94,0.10)" if up else "rgba(239,68,68,0.10)"
    poly = " ".join(pts)
    fill_pts = pts + [f"{width - pad},{height - pad}", f"{pad},{height - pad}"]
    return (f'<svg width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
            f'<polygon points="{" ".join(fill_pts)}" fill="{fcol}"/>'
            f'<polyline points="{poly}" fill="none" stroke="{col}" '
            f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'</svg>')


# ══════════════════════════════════════════════════════════════════════════════
# SYMBOL SEARCH
# ══════════════════════════════════════════════════════════════════════════════
def sym_search(key: str, label: str = "Sembol ara"):
    ALL = get_all_symbols()
    q = st.text_input(label, placeholder="BTC, Ethereum, THYAO, Apple…", key=key)
    ql = q.strip().lower()
    mtc = ([(s, n, cat) for s, n, cat in ALL
             if ql in s.lower() or ql in n.lower()]
           if ql else list(ALL[:15]))
    if not mtc:
        st.warning("Sembol bulunamadı.")
        return ""
    opts = [f"{s}  ·  {n}  ({cat})" for s, n, cat in mtc[:15]]
    syms = [s for s, n, cat in mtc[:15]]
    pre = st.session_state.get("_presym", "")
    def_i = syms.index(pre) if pre in syms else 0
    idx = st.selectbox("", range(len(opts)),
                       format_func=lambda i: opts[i],
                       index=def_i, key=key + "_dd",
                       label_visibility="collapsed")
    return syms[idx] if syms else ""


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTERS
# ══════════════════════════════════════════════════════════════════════════════
def fmt_pct(v: float, plus: bool = True) -> str:
    s = "+" if plus and v > 0 else ""
    return f"{s}{v:.2f}%"


def fmt_price(p: float, currency: str = "USD") -> str:
    if not p or p <= 0:
        return "—"
    if currency == "TRY":
        return f"₺{p:,.2f}" if p < 1000 else f"₺{p:,.0f}"
    if p >= 1000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:,.4f}"
    return f"${p:,.6f}"
