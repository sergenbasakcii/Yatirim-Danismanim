"""
HedgeFund AI — Login / Register / Forgot Password
=================================================
Single auth shell that switches between five views via session state:

    auth_view ∈ { "login", "register", "otp", "forgot", "reset" }

Narrow centered card on a calm graphite canvas. Matches the institutional
design system (steel blue accent, refined typography).
"""
from __future__ import annotations

import streamlit as st

from ui_pages.styles import C


# ══════════════════════════════════════════════════════════════════════════════
# AUTH-SHELL CSS  (also wins over the global 1480px container)
# ══════════════════════════════════════════════════════════════════════════════
def _auth_shell_css():
    st.markdown(f"""
<style>
[data-testid="stSidebar"]                  {{ display:none !important; }}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"]           {{ display:none !important; }}
#MainMenu, footer,
[data-testid="stDecoration"],
.stDeployButton                            {{ display:none !important; }}
[data-testid="stHeader"]                   {{ background:transparent !important;
                                              height:0 !important; }}

html, body, .stApp {{
  background: {C['bg']} !important;
  background-image:
    radial-gradient(ellipse 50% 36% at 50% 0%,
      rgba(91,140,255,0.06), transparent 70%) !important;
  background-attachment: fixed !important;
}}

html body section.main .block-container,
html body [data-testid="stAppViewContainer"] section.main .block-container,
html body [data-testid="stMain"] .block-container {{
  max-width: 440px !important;
  padding: 56px 20px 40px 20px !important;
  margin: 0 auto !important;
}}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
  width: 100% !important;
  background: rgba(15,19,26,0.70) !important;
  border: 1px solid {C['border_solid']} !important;
  border-radius: 8px !important;
  padding: 3px !important;
  gap: 0 !important;
}}
.stTabs [data-baseweb="tab"] {{
  flex: 1 1 0 !important;
  text-align: center !important;
  justify-content: center !important;
  border-radius: 6px !important;
  font-size: 13.5px !important;
  font-weight: 600 !important;
  color: {C['t2']} !important;
  background: transparent !important;
  padding: 8px 14px !important;
}}
.stTabs [data-baseweb="tab"]:hover {{
  background: rgba(148,163,184,0.06) !important;
  color: {C['t1']} !important;
}}
.stTabs [aria-selected="true"] {{
  background: {C['accent']} !important;
  color: #ffffff !important;
  font-weight: 600 !important;
}}

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput input {{
  border: 1px solid {C['border_solid']} !important;
  border-radius: 8px !important;
  padding: 13px 14px !important;
  font-size: 15px !important;
  background: rgba(15,19,26,0.85) !important;
  color: {C['t1']} !important;
  transition: border-color 160ms ease, box-shadow 160ms ease !important;
}}
.stTextInput input::placeholder {{ color: {C['t4']} !important; font-size: 14.5px; }}
.stTextInput input:focus {{
  border-color: {C['accent']} !important;
  box-shadow: 0 0 0 3px {C['accent_glow']} !important;
}}

.field-lbl {{
  font-size: 12.5px !important;
  font-weight: 600 !important;
  color: {C['t2']} !important;
  letter-spacing: 0.005em !important;
  margin: -4px 0 14px 4px !important;
}}

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {{
  background: {C['accent']} !important;
  color: #ffffff !important;
  border: 1px solid transparent !important;
  border-radius: 8px !important;
  font-size: 14.5px !important;
  font-weight: 600 !important;
  padding: 13px 0 !important;
  width: 100% !important;
  min-height: 46px !important;
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.14) inset,
    0 4px 14px -4px rgba(91,140,255,0.40) !important;
  transition: background 140ms ease, box-shadow 140ms ease !important;
}}
.stButton > button[kind="primary"]:hover {{
  background: {C['accent_hover']} !important;
  box-shadow:
    0 1px 0 0 rgba(255,255,255,0.18) inset,
    0 0 0 3px {C['accent_glow']},
    0 6px 18px -4px rgba(91,140,255,0.50) !important;
}}
.stButton > button[kind="secondary"] {{
  background: rgba(20,25,33,0.70) !important;
  color: {C['t1']} !important;
  border: 1px solid {C['border_solid']} !important;
  border-radius: 8px !important;
  font-size: 13.5px !important;
  font-weight: 500 !important;
  padding: 11px 0 !important;
  min-height: 42px !important;
}}
.stButton > button[kind="secondary"]:hover {{
  background: rgba(28,35,46,0.90) !important;
  border-color: {C['border_strong']} !important;
}}

/* ── Inline text-button (link look) ──────────────────────────────────── */
.link-btn .stButton > button {{
  background: transparent !important;
  border: none !important;
  color: {C['accent_hover']} !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  padding: 4px 0 !important;
  min-height: 0 !important;
  text-decoration: none !important;
  box-shadow: none !important;
  width: auto !important;
  letter-spacing: 0 !important;
}}
.link-btn .stButton > button:hover {{
  color: {C['accent']} !important;
  text-decoration: underline !important;
  background: transparent !important;
  box-shadow: none !important;
  transform: none !important;
}}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Building blocks
# ══════════════════════════════════════════════════════════════════════════════
def _logo():
    st.markdown(f"""
<div style="text-align:center;padding:8px 0 28px;">
  <div style="display:inline-flex;align-items:center;justify-content:center;
              width:54px;height:54px;
              background:{C['accent']};
              border-radius:12px;margin-bottom:16px;
              box-shadow:
                0 1px 0 0 rgba(255,255,255,0.18) inset,
                0 -1px 0 0 rgba(0,0,0,0.18) inset,
                0 0 0 1px {C['accent_deep']},
                0 10px 28px -8px rgba(91,140,255,0.45);">
    <span style="font-family:'Inter Tight',sans-serif;font-size:24px;
                 color:#ffffff;font-weight:700;line-height:1;">Y</span>
  </div>
  <div style="font-family:'Inter Tight',sans-serif;font-size:22px;
              font-weight:700;color:{C['t1']};letter-spacing:-0.02em;
              line-height:1;">Yatırım Danışmanım</div>
  <div style="font-size:11px;font-weight:600;color:{C['t3']};
              margin-top:8px;letter-spacing:0.16em;text-transform:uppercase;">
    Yapay Zeka Destekli Asistan
  </div>
</div>""", unsafe_allow_html=True)


def _field_label(text: str):
    st.markdown(f'<div class="field-lbl">{text}</div>', unsafe_allow_html=True)


def _link_button(label: str, key: str) -> bool:
    """Inline text-button that looks like a hyperlink."""
    st.markdown('<div class="link-btn">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, type="secondary")
    st.markdown('</div>', unsafe_allow_html=True)
    return clicked


def _set_view(v: str):
    st.session_state["auth_view"] = v
    st.rerun()


def _flash(msg: str, ok: bool = True):
    """Store a one-shot toast for the next render."""
    st.session_state["auth_flash"] = {"msg": msg, "ok": ok}


def _consume_flash():
    f = st.session_state.pop("auth_flash", None)
    if not f:
        return
    (st.success if f["ok"] else st.error)(f["msg"])


# ══════════════════════════════════════════════════════════════════════════════
# Router
# ══════════════════════════════════════════════════════════════════════════════
def render():
    _auth_shell_css()

    # Legacy compat: existing OTP flag jumps straight to OTP view
    if st.session_state.get("auth_otp_pending"):
        st.session_state["auth_view"] = "otp"

    st.session_state.setdefault("auth_view", "login")
    view = st.session_state["auth_view"]

    if view == "otp":
        _otp_screen()
        return
    if view == "forgot":
        _forgot_screen()
        return
    if view == "reset":
        _reset_screen()
        return

    # login / register tabs
    _logo()
    _consume_flash()
    tab_idx = 1 if view == "register" else 0
    tab_login, tab_reg = st.tabs(["Giriş Yap", "Kayıt Ol"])
    with tab_login:
        if tab_idx == 0:
            _login_form()
        else:
            _login_form()  # always render — Streamlit tabs are independent
    with tab_reg:
        _register_form()

    st.markdown(
        f'<div style="text-align:center;margin-top:24px;font-size:11.5px;'
        f'color:{C["t3"]};letter-spacing:0.02em;">'
        f'Yatırım tavsiyesi niteliği taşımaz.</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════
def _login_form():
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    email = st.text_input("Email", placeholder="ornek@mail.com",
                          key="login_email", label_visibility="collapsed")
    _field_label("Email")

    password = st.text_input("Şifre", type="password",
                             placeholder="Şifreniz",
                             key="login_password", label_visibility="collapsed")
    _field_label("Şifre")

    if st.button("Giriş Yap", type="primary",
                 use_container_width=True, key="login_btn"):
        _do_login(email, password)

    # Forgot-password link — right aligned, link-style
    fc1, fc2 = st.columns([3, 2])
    with fc2:
        if _link_button("Şifremi unuttum →", "to_forgot"):
            st.session_state["forgot_email_prefill"] = email
            _set_view("forgot")


def _do_login(email: str, password: str):
    if not email or not password:
        st.error("Email ve şifre gerekli.")
        return
    from src.auth import login_user
    res = login_user(email, password)
    if res["ok"]:
        u = res["user"]
        st.session_state.update({
            "authenticated": True,
            "user_email":    u["email"],
            "user_name":     u.get("full_name") or u["email"],
            "user_admin":    bool(u.get("is_admin")),
            "auth_view":     "login",
        })
        st.rerun()
    elif res.get("needs_verify"):
        _send_otp(email)
    else:
        st.error(res["msg"])


# ══════════════════════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════════════════════
def _register_form():
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    full_name = st.text_input("Ad Soyad", placeholder="Ad Soyad",
                              key="reg_name", label_visibility="collapsed")
    _field_label("Ad Soyad")

    email = st.text_input("Email", placeholder="ornek@mail.com",
                          key="reg_email", label_visibility="collapsed")
    _field_label("Email")

    password = st.text_input("Şifre", type="password",
                             placeholder="En az 8 karakter",
                             key="reg_password", label_visibility="collapsed")
    _field_label("Şifre")

    password2 = st.text_input("Şifre Tekrar", type="password",
                              placeholder="Şifrenizi tekrar girin",
                              key="reg_password2", label_visibility="collapsed")
    _field_label("Şifre Tekrar")

    if st.button("Kayıt Ol", type="primary",
                 use_container_width=True, key="reg_btn"):
        if not email or not password:
            st.error("Email ve şifre gerekli.")
            return
        if password != password2:
            st.error("Şifreler eşleşmiyor.")
            return
        from src.auth import register_user
        res = register_user(email, password, full_name)
        if res["ok"]:
            _send_otp(email)
        else:
            st.error(res["msg"])


# ══════════════════════════════════════════════════════════════════════════════
# OTP (email verification)
# ══════════════════════════════════════════════════════════════════════════════
def _send_otp(email: str):
    from src.auth import generate_otp, send_otp_email
    code = generate_otp(email)
    mail_res = send_otp_email(email, code)
    st.session_state["auth_otp_pending"] = True
    st.session_state["auth_otp_email"] = email
    st.session_state["auth_otp_fallback_code"] = code if not mail_res["ok"] else None
    st.session_state["auth_view"] = "otp"
    st.rerun()


def _otp_screen():
    email    = st.session_state.get("auth_otp_email", "")
    fallback = st.session_state.get("auth_otp_fallback_code")

    _logo()

    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
        f'border-radius:10px;padding:22px 22px 20px;">'
        f'  <div style="font-size:17px;font-weight:700;color:{C["t1"]};'
        f'              margin-bottom:6px;">Email Doğrulama</div>'
        f'  <div style="font-size:13.5px;color:{C["t2"]};margin-bottom:18px;'
        f'              line-height:1.5;">'
        f'    <b style="color:{C["accent_hover"]};">{email}</b> adresine '
        f'    gönderilen 6 haneli kodu girin.</div>',
        unsafe_allow_html=True,
    )

    if fallback:
        _fallback_code_box("SMTP kurulu değil · Doğrulama Kodu", fallback)

    code = st.text_input("6 Haneli Kod", placeholder="123456",
                         max_chars=6, key="otp_code_input",
                         label_visibility="collapsed")
    _field_label("Doğrulama Kodu")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Doğrula", type="primary",
                     use_container_width=True, key="otp_verify_btn"):
            _do_verify_otp(email, code)
    with c2:
        if st.button("Geri Dön", use_container_width=True,
                     key="otp_back_btn", type="secondary"):
            _reset_otp_state()
            _set_view("login")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("Kodu Yeniden Gönder", key="otp_resend_btn",
                 use_container_width=True, type="secondary"):
        _send_otp(email)


def _do_verify_otp(email: str, code: str):
    if not code:
        st.error("Kodu girin.")
        return
    from src.auth import verify_otp, get_user
    res = verify_otp(email, code)
    if not res["ok"]:
        st.error(res["msg"])
        return
    user = get_user(email)
    if not user:
        st.error("Kullanıcı bulunamadı.")
        return
    st.session_state.update({
        "authenticated":          True,
        "user_email":             user["email"],
        "user_name":              user.get("full_name") or user["email"],
        "user_admin":             bool(user.get("is_admin")),
    })
    _reset_otp_state()
    st.session_state["auth_view"] = "login"
    st.rerun()


def _reset_otp_state():
    st.session_state["auth_otp_pending"] = False
    st.session_state["auth_otp_email"] = None
    st.session_state["auth_otp_fallback_code"] = None


# ══════════════════════════════════════════════════════════════════════════════
# FORGOT PASSWORD — step 1 (request code)
# ══════════════════════════════════════════════════════════════════════════════
def _forgot_screen():
    _logo()
    _consume_flash()

    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
        f'border-radius:10px;padding:22px;">'
        f'  <div style="font-size:17px;font-weight:700;color:{C["t1"]};'
        f'              margin-bottom:6px;">Şifremi Unuttum</div>'
        f'  <div style="font-size:13.5px;color:{C["t2"]};margin-bottom:18px;'
        f'              line-height:1.5;">'
        f'    Email adresinizi girin. Hesabınız varsa size 6 haneli bir '
        f'    sıfırlama kodu göndereceğiz.</div>',
        unsafe_allow_html=True,
    )

    prefill = st.session_state.pop("forgot_email_prefill", "")
    email = st.text_input("Email", value=prefill, placeholder="ornek@mail.com",
                          key="forgot_email", label_visibility="collapsed")
    _field_label("Email")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Kod Gönder", type="primary",
                     use_container_width=True, key="forgot_send_btn"):
            _do_request_reset(email)
    with c2:
        if st.button("Geri Dön", use_container_width=True,
                     key="forgot_back_btn", type="secondary"):
            _set_view("login")

    st.markdown("</div>", unsafe_allow_html=True)


def _do_request_reset(email: str):
    if not email:
        st.error("Email girin.")
        return
    from src.auth import request_password_reset
    res = request_password_reset(email)
    if not res["ok"]:
        st.error(res["msg"])
        return
    # Privacy: always proceed to reset screen, even if account doesn't exist.
    st.session_state["reset_email"] = email
    st.session_state["reset_fallback_code"] = res.get("fallback_code")
    st.session_state["reset_mail_ok"] = res.get("mail_ok", True)
    _flash(res["msg"], ok=True)
    _set_view("reset")


# ══════════════════════════════════════════════════════════════════════════════
# RESET PASSWORD — step 2 (enter code + new password)
# ══════════════════════════════════════════════════════════════════════════════
def _reset_screen():
    _logo()
    _consume_flash()

    email    = st.session_state.get("reset_email", "")
    fallback = st.session_state.get("reset_fallback_code")

    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
        f'border-radius:10px;padding:22px;">'
        f'  <div style="font-size:17px;font-weight:700;color:{C["t1"]};'
        f'              margin-bottom:6px;">Yeni Şifre Belirle</div>'
        f'  <div style="font-size:13.5px;color:{C["t2"]};margin-bottom:18px;'
        f'              line-height:1.5;">'
        f'    <b style="color:{C["accent_hover"]};">{email or "—"}</b> adresine '
        f'    gönderilen 6 haneli kodu girin ve yeni şifrenizi belirleyin.</div>',
        unsafe_allow_html=True,
    )

    if fallback:
        _fallback_code_box("SMTP kurulu değil · Sıfırlama Kodu", fallback)

    code = st.text_input("Kod", placeholder="123456", max_chars=6,
                         key="reset_code", label_visibility="collapsed")
    _field_label("Sıfırlama Kodu")

    new_pw = st.text_input("Yeni Şifre", type="password",
                           placeholder="En az 8 karakter",
                           key="reset_new_pw", label_visibility="collapsed")
    _field_label("Yeni Şifre")

    new_pw2 = st.text_input("Şifre Tekrar", type="password",
                            placeholder="Yeni şifrenizi tekrar girin",
                            key="reset_new_pw2", label_visibility="collapsed")
    _field_label("Şifre Tekrar")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Şifreyi Sıfırla", type="primary",
                     use_container_width=True, key="reset_submit_btn"):
            _do_reset_password(email, code, new_pw, new_pw2)
    with c2:
        if st.button("Geri Dön", use_container_width=True,
                     key="reset_back_btn", type="secondary"):
            _clear_reset_state()
            _set_view("login")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("Kodu Yeniden Gönder", key="reset_resend_btn",
                 use_container_width=True, type="secondary"):
        _do_request_reset(email)


def _do_reset_password(email: str, code: str, new_pw: str, new_pw2: str):
    if not (email and code and new_pw):
        st.error("Tüm alanları doldurun.")
        return
    if new_pw != new_pw2:
        st.error("Şifreler eşleşmiyor.")
        return
    from src.auth import reset_password
    res = reset_password(email, code, new_pw)
    if not res["ok"]:
        st.error(res["msg"])
        return
    _clear_reset_state()
    _flash("Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.",
           ok=True)
    _set_view("login")


def _clear_reset_state():
    for k in ("reset_email", "reset_fallback_code", "reset_mail_ok",
              "reset_code", "reset_new_pw", "reset_new_pw2"):
        st.session_state.pop(k, None)


# ══════════════════════════════════════════════════════════════════════════════
# Shared widgets
# ══════════════════════════════════════════════════════════════════════════════
def _fallback_code_box(title: str, code: str):
    st.markdown(
        f'<div style="background:{C["accent_dim"]};'
        f'border:1px solid rgba(91,140,255,0.30);'
        f'border-radius:8px;padding:14px;text-align:center;margin-bottom:18px;">'
        f'  <div style="font-size:10.5px;font-weight:700;letter-spacing:0.12em;'
        f'              text-transform:uppercase;color:{C["t3"]};'
        f'              margin-bottom:6px;">{title}</div>'
        f'  <div style="font-size:34px;font-weight:700;color:{C["accent_hover"]};'
        f'              letter-spacing:0.14em;font-family:JetBrains Mono,monospace;">'
        f'    {code}</div>'
        f'  <div style="font-size:11px;color:{C["t3"]};margin-top:6px;">'
        f'    Geçici geliştirme modu</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
