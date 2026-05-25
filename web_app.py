"""
Yatırım Danışmanım — Application shell & router
================================================
Institutional terminal entry point. Owns: page config, global CSS,
auth gate, top navigation bar, and route dispatch.

Layout: sticky top navigation (no sidebar). Brand on the left,
flat module buttons in the centre, market-status pill and user
popover on the right.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Yatırım Danışmanım",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Yatırım Danışmanım — Yapay Zeka Destekli Yatırım Asistanı"},
)

from ui_pages.styles import inject_css, C  # noqa: E402

inject_css()

# ── DB init ───────────────────────────────────────────────────────────────────
from src.auth import init_db  # noqa: E402
init_db()

# ── Session defaults ─────────────────────────────────────────────────────────
DEFAULTS = {
    "page":             "Dashboard",
    "authenticated":    False,
    "user_email":       None,
    "user_name":        None,
    "user_admin":       False,
    "auth_otp_pending": False,
    "opp_scanning":     False,
    "opp_results":      None,
    "opp_detail":       None,
    "opp_detail_sym":   None,
    "analysis_result":  None,
    "analysis_run_sym": None,
    "proj_result":      None,
    "proj_run":         False,
    "proj_sym":         None,
    "proj_amt_val":     1000.0,
    "proj_cur_val":     "USD",
    "portfolios":       [{"name": "Portföy 1", "result": None, "params": {}}],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not st.session_state["authenticated"]:
    from ui_pages.login import render as login_render
    login_render()
    st.stop()

# ── Navigation config ────────────────────────────────────────────────────────
NAV = [
    ("Dashboard",      "Dashboard",      "⬡"),
    ("Fırsatlar",      "Fırsatlar",      "◈"),
    ("Analiz",         "Analiz",         "◎"),
    ("Karar Asistanı", "Karar",          "⌬"),
    ("Portföy",        "Portföy",        "◧"),
    ("Projeksiyon",    "Projeksiyon",    "◉"),
]

# ══════════════════════════════════════════════════════════════════════════════
# TOP NAVIGATION BAR
# ══════════════════════════════════════════════════════════════════════════════
def _market_status() -> tuple[str, str, bool]:
    """Return (label, hex_color, is_any_open)."""
    now = datetime.now()
    hm  = now.hour * 60 + now.minute
    wd  = now.weekday()
    bist_open = (wd < 5) and (10 * 60 <= hm < 18 * 60)
    us_open   = (wd < 5) and (16 * 60 + 30 <= hm < 23 * 60)
    if bist_open and us_open:
        return "BIST + ABD AÇIK", C["buy"], True
    if bist_open:
        return "BIST AÇIK", C["buy"], True
    if us_open:
        return "ABD AÇIK", C["buy"], True
    return "PIYASA KAPALI", C["t3"], False


def render_topnav() -> None:
    user_name  = st.session_state.get("user_name", "")
    user_email = st.session_state.get("user_email", "")
    is_admin   = st.session_state.get("user_admin", False)
    initial    = (user_name or user_email or "U")[0].upper()
    status_lbl, status_col, status_live = _market_status()
    now_str = datetime.now().strftime("%H:%M")

    # Open the top-nav wrapper
    st.markdown('<div class="topnav-wrap"><div class="topnav">', unsafe_allow_html=True)

    # 1 brand | 6 module buttons | 1 status | 1 user popover
    cols = st.columns([2.6, 0.95, 0.95, 0.95, 1.20, 0.95, 1.10, 1.55, 1.55],
                      gap="small", vertical_alignment="center")

    # ── Brand ────────────────────────────────────────────────────────────────
    with cols[0]:
        st.markdown(
            f"""
<div class="topnav-brand">
  <div class="topnav-logo">Y</div>
  <div class="topnav-brand-text">
    <div class="topnav-brand-name">Yatırım Danışmanım</div>
    <div class="topnav-brand-sub">Terminal · v1.0</div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )

    # ── Module buttons ───────────────────────────────────────────────────────
    for i, (key, label, _icon) in enumerate(NAV, start=1):
        with cols[i]:
            is_active = st.session_state["page"] == key
            st.markdown(
                f'<div class="topnav-item{" topnav-item--active" if is_active else ""}">',
                unsafe_allow_html=True,
            )
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state["page"] = key
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Market status pill ───────────────────────────────────────────────────
    with cols[7]:
        dot_cls = "live" if status_live else "idle"
        st.markdown(
            f"""
<div class="topnav-status">
  <span class="dot {dot_cls}"></span>
  <span class="topnav-status-time">{now_str}</span>
  <span class="topnav-status-label" style="color:{status_col};">{status_lbl}</span>
</div>""",
            unsafe_allow_html=True,
        )

    # ── User popover (dropdown) ──────────────────────────────────────────────
    with cols[8]:
        trigger = f"●  {user_name or user_email or 'Kullanıcı'}"
        with st.popover(trigger, use_container_width=True):
            admin_tag = (
                f'<span class="topnav-admin-tag">Admin</span>' if is_admin else ""
            )
            st.markdown(
                f"""
<div class="topnav-pop-head">
  <div class="topnav-pop-avatar">{initial}</div>
  <div class="topnav-pop-id">
    <div class="topnav-pop-name">
      {user_name or user_email or "Kullanıcı"}{admin_tag}
    </div>
    <div class="topnav-pop-email">{user_email}</div>
  </div>
</div>
<div class="topnav-pop-meta">
  <div class="topnav-pop-meta-row">
    <span>Piyasa</span>
    <span style="color:{status_col};font-weight:600;">{status_lbl}</span>
  </div>
  <div class="topnav-pop-meta-row">
    <span>Saat</span>
    <span class="mono">{now_str}</span>
  </div>
  <div class="topnav-pop-meta-row">
    <span>Kripto</span>
    <span style="color:{C['t2']};">7/24 açık</span>
  </div>
</div>""",
                unsafe_allow_html=True,
            )
            if st.button("Çıkış Yap", key="logout_btn",
                         use_container_width=True, type="secondary"):
                for k in ["authenticated", "user_email",
                          "user_name", "user_admin"]:
                    st.session_state[k] = False if k == "authenticated" else None
                st.rerun()

    # Close the wrapper
    st.markdown('</div></div>', unsafe_allow_html=True)


render_topnav()

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
page = st.session_state["page"]

if   page == "Dashboard":
    from ui_pages.dashboard         import render; render()
elif page == "Fırsatlar":
    from ui_pages.opportunities     import render; render()
elif page == "Analiz":
    from ui_pages.analysis          import render; render()
elif page == "Karar Asistanı":
    from ui_pages.decision_assistant import render; render()
elif page == "Portföy":
    from ui_pages.portfolio         import render; render()
elif page == "Projeksiyon":
    from ui_pages.projection        import render; render()
