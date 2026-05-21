"""
HedgeFund AI — Reusable UI primitives
=====================================
Opt-in component kit that sits on top of the design tokens / CSS in
`ui_pages.styles`. Every primitive returns an HTML string that can be
embedded with `st.markdown(..., unsafe_allow_html=True)` (or rendered
directly via the convenience helpers).

These primitives intentionally render plain HTML — Streamlit's sanitizer
copes well with single-element snippets, which keeps the entire UI
predictable across pages.
"""
from __future__ import annotations

from html import escape
from typing import Iterable, Optional, Sequence

import streamlit as st

from ui_pages.styles import C, spark_svg


# ══════════════════════════════════════════════════════════════════════════════
# PILLS / DOTS
# ══════════════════════════════════════════════════════════════════════════════
PILL_TONES = {"neutral", "positive", "negative", "warn", "info", "accent", "ai"}


def pill(text: str, tone: str = "neutral") -> str:
    tone = tone if tone in PILL_TONES else "neutral"
    return f'<span class="pill {tone}">{escape(str(text))}</span>'


def status_dot(tone: str = "live") -> str:
    tone = tone if tone in {"live", "idle", "warn", "error"} else "idle"
    return f'<span class="dot {tone}"></span>'


# ══════════════════════════════════════════════════════════════════════════════
# SECTION HEADER
# ══════════════════════════════════════════════════════════════════════════════
def section_header(title: str, kicker: Optional[str] = None,
                   meta: Optional[str] = None,
                   render: bool = True) -> Optional[str]:
    kicker_html = (f'<div class="lbl" style="margin-bottom:4px;">{escape(kicker)}</div>'
                   if kicker else "")
    meta_html = f'<div class="meta">{meta}</div>' if meta else ""
    html = (
        f'<div class="section-head">'
        f'  <div>'
        f'    {kicker_html}'
        f'    <div class="title"><span class="accent-bar"></span>{escape(title)}</div>'
        f'  </div>'
        f'  {meta_html}'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# KPI TILE
# ══════════════════════════════════════════════════════════════════════════════
def kpi_tile(label: str, value: str,
             delta: Optional[float] = None,
             delta_suffix: str = "%",
             sub: Optional[str] = None,
             sparkline_vals: Optional[Sequence[float]] = None,
             render: bool = True) -> Optional[str]:
    """A dense institutional KPI tile.

    Args:
        label:           Small uppercase label (e.g. "BTC / USD").
        value:           Big formatted value (e.g. "$67,210").
        delta:           Numeric change. Positive → green pill, negative → red.
        delta_suffix:    Suffix appended to delta ("%" by default).
        sub:             Optional muted subtext under the value.
        sparkline_vals:  Optional sequence rendered as a 110×28 sparkline.
    """
    if delta is None:
        delta_html = ""
    else:
        tone = "positive" if delta >= 0 else "negative"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = pill(f"{arrow} {abs(delta):.2f}{delta_suffix}", tone)

    spark_html = ""
    if sparkline_vals and len(sparkline_vals) >= 2:
        spark_html = (f'<div class="kpi-spark">'
                      f'{spark_svg(list(sparkline_vals), width=110, height=28)}'
                      f'</div>')

    sub_html = (f'<div class="kpi-sub">{escape(sub)}</div>' if sub else "")

    # If we have a sparkline, place delta + sparkline side-by-side under value.
    bottom = ""
    if delta_html or spark_html or sub_html:
        bottom = (
            f'<div class="kpi-row">'
            f'  <div>{delta_html}{(" " + sub_html) if (delta_html and sub_html) else sub_html}</div>'
            f'  {spark_html}'
            f'</div>'
        )

    html = (
        f'<div class="kpi fade-up">'
        f'  <div class="kpi-label">{escape(label)}</div>'
        f'  <div class="kpi-value">{value}</div>'
        f'  {bottom}'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════
def data_table(columns: Sequence[dict], rows: Sequence[Sequence],
               render: bool = True) -> Optional[str]:
    """Compact institutional table.

    Each column dict supports:
        label      str            — header label (uppercase rendered)
        width      str            — CSS grid track (e.g. "1fr", "120px")
        align      "left"|"right" — text alignment of cells
        cls        str            — extra cell class (e.g. "muted num")

    Each row is a sequence of pre-formatted strings (HTML allowed).
    """
    cols = list(columns)
    grid = " ".join(c.get("width", "1fr") for c in cols)

    head_cells = "".join(
        f'<span class="{("right" if c.get("align") == "right" else "")}">{escape(c["label"])}</span>'
        for c in cols
    )
    head = (f'<div class="dt-head" style="grid-template-columns:{grid};">'
            f'{head_cells}</div>')

    row_html = []
    for r in rows:
        cells = []
        for c, val in zip(cols, r):
            cls_parts = []
            if c.get("align") == "right":
                cls_parts.append("right")
            if c.get("cls"):
                cls_parts.append(c["cls"])
            cls = (' class="' + " ".join(cls_parts) + '"') if cls_parts else ""
            cells.append(f'<span{cls}>{val}</span>')
        row_html.append(
            f'<div class="dt-row" style="grid-template-columns:{grid};">'
            f'{"".join(cells)}</div>'
        )

    html = f'<div class="dt fade-up">{head}{"".join(row_html)}</div>'
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# AI INSIGHT CARD
# ══════════════════════════════════════════════════════════════════════════════
def ai_insight_card(title: str, body: str,
                    tag: str = "AI INSIGHT",
                    confidence: Optional[float] = None,
                    render: bool = True) -> Optional[str]:
    conf = ""
    if confidence is not None:
        conf = (f'<span class="pill ai" style="margin-left:auto;">'
                f'GÜVEN {confidence:.0f}%</span>')
    html = (
        f'<div class="ai-card fade-up">'
        f'  <div style="display:flex;align-items:center;gap:8px;">'
        f'    <span class="ai-tag">◆ {escape(tag)}</span>{conf}'
        f'  </div>'
        f'  <div class="ai-title">{escape(title)}</div>'
        f'  <div class="ai-body">{body}</div>'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# SKELETON / EMPTY STATE
# ══════════════════════════════════════════════════════════════════════════════
def skeleton(rows: int = 3, h: int = 14, gap: int = 8,
             render: bool = True) -> Optional[str]:
    bars = "".join(
        f'<div class="skel" style="height:{h}px;width:{(100 - i * 8) if i < 4 else 60}%;'
        f'margin-bottom:{gap}px;"></div>'
        for i in range(max(1, rows))
    )
    html = f'<div style="padding:4px 0;">{bars}</div>'
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


def empty_state(title: str, hint: str = "", icon: str = "◇",
                render: bool = True) -> Optional[str]:
    html = (
        f'<div class="empty">'
        f'  <div class="empty-icon">{escape(icon)}</div>'
        f'  <div class="empty-title">{escape(title)}</div>'
        f'  <div class="empty-hint">{escape(hint)}</div>'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# DIVIDER / SPACER
# ══════════════════════════════════════════════════════════════════════════════
def vspace(px: int = 16) -> None:
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# KBD (keyboard shortcut hint)
# ══════════════════════════════════════════════════════════════════════════════
def kbd(keys: str) -> str:
    """Render a keyboard shortcut hint (e.g. "⌘K", "G D")."""
    return (
        f'<span style="display:inline-block;font-family:JetBrains Mono,monospace;'
        f'font-size:10px;font-weight:600;color:{C["t3"]};'
        f'background:{C["bg_elev"]};border:1px solid {C["border_solid"]};'
        f'border-bottom-width:2px;padding:1px 6px;border-radius:4px;'
        f'letter-spacing:0.06em;line-height:1.4;">{escape(keys)}</span>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# ALERT BANNER (info / warn / error / success)
# ══════════════════════════════════════════════════════════════════════════════
_ALERT_TONES = {
    "info":    (C["info"],  C["info_dim"],  "ⓘ"),
    "warn":    (C["warn"],  C["warn_dim"],  "⚠"),
    "error":   (C["sell"],  C["sell_dim"],  "✕"),
    "success": (C["buy"],   C["buy_dim"],   "✓"),
}


def alert_banner(message: str, tone: str = "info",
                 title: Optional[str] = None,
                 render: bool = True) -> Optional[str]:
    col, dim, icon = _ALERT_TONES.get(tone, _ALERT_TONES["info"])
    title_html = (f'<div style="font-size:13px;font-weight:600;color:{C["t1"]};'
                  f'margin-bottom:2px;">{escape(title)}</div>') if title else ""
    html = (
        f'<div style="display:flex;gap:10px;align-items:flex-start;'
        f'background:{dim};border-left:3px solid {col};'
        f'padding:10px 14px;border-radius:6px;margin:8px 0;">'
        f'  <span style="color:{col};font-size:14px;line-height:1.4;'
        f'flex-shrink:0;">{icon}</span>'
        f'  <div style="flex:1;min-width:0;">'
        f'    {title_html}'
        f'    <div style="font-size:12.5px;color:{C["t2"]};'
        f'line-height:1.5;">{message}</div>'
        f'  </div>'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# STAT ROW (label · value pair, dense)
# ══════════════════════════════════════════════════════════════════════════════
def stat_row(label: str, value: str, tone: str = "neutral",
             render: bool = True) -> Optional[str]:
    val_col = {
        "positive": C["buy"], "negative": C["sell"],
        "warn": C["warn"], "accent": C["accent"],
    }.get(tone, C["t1"])
    html = (
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:baseline;padding:6px 0;'
        f'border-bottom:1px solid {C["divider"]};">'
        f'  <span style="font-size:12px;color:{C["t3"]};'
        f'letter-spacing:0.02em;">{escape(label)}</span>'
        f'  <span style="font-size:13.5px;color:{val_col};font-weight:600;'
        f'font-variant-numeric:tabular-nums;'
        f'font-family:JetBrains Mono,monospace;">{value}</span>'
        f'</div>'
    )
    if render:
        st.markdown(html, unsafe_allow_html=True)
        return None
    return html


# ══════════════════════════════════════════════════════════════════════════════
# DIVIDER (kept after the new primitives so existing imports keep working)
# ══════════════════════════════════════════════════════════════════════════════
def divider(label: Optional[str] = None) -> None:
    if not label:
        st.markdown(
            f'<div style="height:1px;background:{C["divider"]};margin:12px 0;"></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin:18px 0 10px;">'
        f'  <div class="lbl" style="margin:0;">{escape(label)}</div>'
        f'  <div style="flex:1;height:1px;background:{C["divider"]};"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
