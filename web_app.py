"""
HedgeFund AI — Application shell & router
=========================================
Institutional terminal entry point. Owns: page config, global CSS injection,
auth gate, sidebar navigation, status indicators, and route dispatch.
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
    initial_sidebar_state="expanded",
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
    ("Dashboard",      "Dashboard",      "⬡", "G D"),
    ("Fırsatlar",      "Fırsatlar",      "◈", "G O"),
    ("Analiz",         "Analiz",         "◎", "G A"),
    ("Karar Asistanı", "Karar Asistanı", "⌬", "G K"),
    ("Portföy",        "Portföy",        "◧", "G P"),
    ("Projeksiyon",    "Projeksiyon",    "◉", "G R"),
]

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── Brand header ──────────────────────────────────────────────────────────
    st.markdown(
        f"""
<div style="padding:20px 20px 18px 20px;border-bottom:1px solid {C['border_solid']};">
  <div style="display:flex;align-items:center;gap:11px;">
    <div style="width:30px;height:30px;background:{C['accent']};
                border-radius:7px;display:flex;align-items:center;justify-content:center;
                box-shadow:
                  0 1px 0 0 rgba(255,255,255,0.18) inset,
                  0 -1px 0 0 rgba(0,0,0,0.20) inset,
                  0 0 0 1px {C['accent_deep']},
                  0 4px 12px -4px rgba(91,140,255,0.45);">
      <span style="font-family:Inter Tight,sans-serif;font-size:14px;
                   color:#ffffff;font-weight:700;line-height:1;">Y</span>
    </div>
    <div>
      <div style="font-family:Inter Tight,sans-serif;font-size:15px;
                  font-weight:700;color:{C['t1']};letter-spacing:-0.01em;
                  line-height:1;">Yatırım Danışmanım</div>
      <div style="font-size:9.5px;font-weight:600;color:{C['t3']};
                  letter-spacing:0.14em;text-transform:uppercase;
                  margin-top:4px;line-height:1;">Terminal · v1.0</div>
    </div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Search hint (placeholder for future ⌘K) ──────────────────────────────
    st.markdown(
        f"""
<div style="padding:14px 18px 6px;">
  <div style="display:flex;align-items:center;gap:8px;
              padding:7px 10px;border:1px solid {C['border_solid']};
              border-radius:7px;background:rgba(15,19,26,0.60);
              cursor:default;opacity:0.78;">
    <span style="color:{C['t3']};font-size:13px;">⌕</span>
    <span style="color:{C['t3']};font-size:12px;flex:1;">Hızlı arama…</span>
    <span style="color:{C['t4']};font-size:9.5px;font-weight:600;
                 letter-spacing:0.10em;border:1px solid {C['border_solid']};
                 padding:1px 5px;border-radius:3px;
                 font-family:JetBrains Mono,monospace;">⌘K</span>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Section label ─────────────────────────────────────────────────────────
    st.markdown(
        f"""
<div style="padding:8px 22px 4px;display:flex;align-items:center;gap:8px;">
  <div style="height:1px;width:12px;background:{C['accent']};opacity:0.6;"></div>
  <div style="font-size:10px;font-weight:700;text-transform:uppercase;
              letter-spacing:0.14em;color:{C['t3']};">MODÜLLER</div>
</div>""",
        unsafe_allow_html=True,
    )

    # ── Nav buttons ───────────────────────────────────────────────────────────
    for key, label, icon, kbd in NAV:
        is_active = st.session_state["page"] == key
        if is_active:
            st.markdown(
                f"""
<div style="border-left:2px solid {C['accent']};
            background:linear-gradient(90deg,
              rgba(91,140,255,0.10) 0%,
              rgba(91,140,255,0.02) 80%,
              transparent 100%);
            margin:2px 8px 2px 0;border-radius:0 6px 6px 0;">""",
                unsafe_allow_html=True,
            )
        if st.button(label, key=f"nav_{key}",
                     use_container_width=True, type="secondary"):
            st.session_state["page"] = key
            st.rerun()
        if is_active:
            st.markdown("</div>", unsafe_allow_html=True)

    # ── User block + logout ───────────────────────────────────────────────────
    user_name = st.session_state.get("user_name", "")
    user_email = st.session_state.get("user_email", "")
    is_admin = st.session_state.get("user_admin", False)
    admin_tag = (
        f'<span style="font-size:9.5px;font-weight:700;color:{C["accent_hover"]};'
        f'background:{C["accent_dim"]};padding:1px 5px;border-radius:3px;'
        f'text-transform:uppercase;letter-spacing:0.08em;'
        f'border:1px solid rgba(91,140,255,0.28);margin-left:6px;">Admin</span>'
        if is_admin else ""
    )
    initial = (user_name or user_email or "U")[0].upper()

    st.markdown(
        f"""
<div style="border-top:1px solid {C['border_solid']};padding:14px 20px 10px;
            margin-top:8px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
    <div style="width:30px;height:30px;border-radius:50%;
                background:{C['accent']};
                display:flex;align-items:center;justify-content:center;
                flex-shrink:0;
                box-shadow:
                  0 1px 0 0 rgba(255,255,255,0.18) inset,
                  0 0 0 1px {C['accent_deep']},
                  0 3px 8px -3px rgba(91,140,255,0.40);">
      <span style="font-size:13px;font-weight:700;color:#ffffff;
                   font-family:Inter Tight,sans-serif;">{initial}</span>
    </div>
    <div style="flex:1;min-width:0;">
      <div style="font-size:12.5px;font-weight:600;color:{C['t1']};
                  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                  letter-spacing:-0.005em;">
        {user_name or user_email or "Kullanıcı"}{admin_tag}</div>
      <div style="font-size:10.5px;color:{C['t3']};white-space:nowrap;
                  overflow:hidden;text-overflow:ellipsis;
                  letter-spacing:0.01em;">{user_email}</div>
    </div>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

    if st.button("Çıkış Yap", key="logout_btn",
                 use_container_width=True, type="secondary"):
        for k in ["authenticated", "user_email", "user_name", "user_admin"]:
            st.session_state[k] = False if k == "authenticated" else None
        st.rerun()

    # ── Footer status (dynamic market clock) ──────────────────────────────────
    _now = datetime.now()
    _hm = _now.hour * 60 + _now.minute
    _wd = _now.weekday()  # 0=Mon ... 6=Sun
    # Borsa İstanbul:  Mon-Fri 10:00-18:00 (TR)
    _bist_open = (_wd < 5) and (10 * 60 <= _hm < 18 * 60)
    # US equities (TR time, DST naive): Mon-Fri 16:30-23:00
    _us_open   = (_wd < 5) and (16 * 60 + 30 <= _hm < 23 * 60)
    # Crypto: 24/7

    if _bist_open and _us_open:
        _label, _tone = "BIST + ABD AÇIK", C["buy"]
    elif _bist_open:
        _label, _tone = "BIST AÇIK", C["buy"]
    elif _us_open:
        _label, _tone = "ABD AÇIK", C["buy"]
    else:
        _label, _tone = "PIYASA KAPALI", C["t3"]

    now_str = _now.strftime("%H:%M")
    st.markdown(
        f"""
<div class="sb-footer" style="position:fixed;bottom:0;left:0;width:240px;
            max-width:100%;
            background:{C['sidebar']};
            border-top:1px solid {C['border_solid']};
            padding:12px 20px 14px;">
  <div style="font-size:10px;font-weight:700;text-transform:uppercase;
              letter-spacing:0.14em;color:{C['t3']};margin-bottom:8px;
              display:flex;align-items:center;gap:8px;">
    <div style="height:1px;width:12px;background:{C['accent']};opacity:0.6;"></div>
    PIYASA DURUMU
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span class="dot {'live' if _bist_open or _us_open else 'idle'}"></span>
    <span style="font-size:13px;color:{C['t1']};font-weight:600;
                 font-variant-numeric:tabular-nums;letter-spacing:-0.01em;
                 font-family:JetBrains Mono,monospace;">{now_str}</span>
    <span style="font-size:10px;color:{_tone};font-weight:700;
                 letter-spacing:0.10em;margin-left:auto;
                 text-transform:uppercase;">{_label}</span>
  </div>
  <div style="margin-top:6px;font-size:9.5px;color:{C['t4']};
              letter-spacing:0.04em;line-height:1.4;">
    Kripto · 7/24 açık
  </div>
</div>""",
        unsafe_allow_html=True,
    )

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
