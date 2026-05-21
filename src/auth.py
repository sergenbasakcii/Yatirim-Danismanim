"""
HedgeFund AI — Auth Engine
==========================
SQLite-backed local user management, PBKDF2 password hashing with a
transparent legacy-SHA256 upgrade path, OTP email verification and
password-reset codes.

DB lives at  ``<repo>/data/users.db``  (created on first run).
SMTP is read from environment variables / Streamlit secrets — if not
configured, codes are returned in the API response so the UI can display
them as a development fallback.

Environment variables (or `.streamlit/secrets.toml`):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM

Tables:
    users           : (id, email, password, is_admin, is_verified,
                       full_name, created_at, password_updated_at)
    otp_codes       : (email, code, expires_at, used)
    password_resets : (email, code, expires_at, used)
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import smtplib
import sqlite3
import secrets
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "data" / "users.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ── Default admin (rotate via the UI after first login) ──────────────────────
DEFAULT_ADMIN_EMAIL    = "admin@hedgefund.local"
DEFAULT_ADMIN_PASSWORD = "Efsane4747++**"
DEFAULT_ADMIN_NAME     = "Administrator"

# ── Tunables ──────────────────────────────────────────────────────────────────
PBKDF2_ITERATIONS  = 200_000
OTP_TTL_MINUTES    = 10
RESET_TTL_MINUTES  = 15
PASSWORD_MIN_LEN   = 8  # for *new* registrations / resets — admin override OK

# Basic RFC-ish email regex — good enough for UI gating.
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ══════════════════════════════════════════════════════════════════════════════
# DB plumbing
# ══════════════════════════════════════════════════════════════════════════════
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db() -> None:
    """Create schema, run idempotent migrations, ensure the default admin."""
    conn = _get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            email                TEXT    UNIQUE NOT NULL,
            password             TEXT    NOT NULL,
            is_admin             INTEGER DEFAULT 0,
            is_verified          INTEGER DEFAULT 0,
            full_name            TEXT    DEFAULT '',
            created_at           TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS otp_codes (
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS password_resets (
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_otp_email   ON otp_codes (email);
        CREATE INDEX IF NOT EXISTS idx_reset_email ON password_resets (email);
    """)

    # ── Schema migrations (additive only) ────────────────────────────────────
    # SQLite forbids non-constant defaults on ADD COLUMN, so we add the column
    # with no default and backfill existing rows with the current timestamp.
    cols = _table_columns(conn, "users")
    if "password_updated_at" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN password_updated_at TEXT")
        c.execute("UPDATE users SET password_updated_at = datetime('now') "
                  "WHERE password_updated_at IS NULL")

    # ── Default-admin migration (idempotent) ────────────────────────────────
    _ensure_default_admin(conn)
    conn.commit()
    conn.close()


def _ensure_default_admin(conn: sqlite3.Connection) -> None:
    """Guarantee a single admin account with the canonical credentials.

    Behaviour:
      • If there's a legacy row with email "admin", migrate it to
        ``DEFAULT_ADMIN_EMAIL`` and rotate the password.
      • If neither exists, create the canonical admin.
      • If the canonical admin exists, leave its password alone unless
        ``HEDGEFUND_FORCE_ADMIN_RESET=1`` is set in the environment.
    """
    c = conn.cursor()
    legacy = c.execute("SELECT id FROM users WHERE email='admin'").fetchone()
    canonical = c.execute(
        "SELECT id FROM users WHERE email=?",
        (DEFAULT_ADMIN_EMAIL,),
    ).fetchone()

    new_pw_hash = _hash(DEFAULT_ADMIN_PASSWORD)

    if legacy and not canonical:
        # Migrate legacy admin row to canonical email + rotate password.
        c.execute(
            """UPDATE users
                  SET email=?, password=?, is_admin=1, is_verified=1,
                      full_name=COALESCE(NULLIF(full_name,''), ?),
                      password_updated_at=datetime('now')
                WHERE id=?""",
            (DEFAULT_ADMIN_EMAIL, new_pw_hash, DEFAULT_ADMIN_NAME, legacy["id"]),
        )
        return

    if legacy and canonical:
        # Both rows exist — remove legacy, keep canonical untouched.
        c.execute("DELETE FROM users WHERE id=?", (legacy["id"],))
        return

    if not canonical:
        c.execute(
            """INSERT INTO users
                   (email, password, is_admin, is_verified, full_name,
                    password_updated_at)
                 VALUES (?, ?, 1, 1, ?, datetime('now'))""",
            (DEFAULT_ADMIN_EMAIL, new_pw_hash, DEFAULT_ADMIN_NAME),
        )
        return

    # canonical exists, no legacy — optional forced reset
    if os.getenv("HEDGEFUND_FORCE_ADMIN_RESET") == "1":
        c.execute(
            """UPDATE users
                  SET password=?, is_verified=1, is_admin=1,
                      password_updated_at=datetime('now')
                WHERE email=?""",
            (new_pw_hash, DEFAULT_ADMIN_EMAIL),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Hashing — PBKDF2 with transparent legacy-SHA256 upgrade
# ══════════════════════════════════════════════════════════════════════════════
def _hash(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                              salt, PBKDF2_ITERATIONS)
    return ("pbkdf2_sha256$"
            f"{PBKDF2_ITERATIONS}$"
            f"{base64.b64encode(salt).decode('ascii')}$"
            f"{base64.b64encode(dk).decode('ascii')}")


def _verify(password: str, stored: str) -> bool:
    """Return True if *password* matches *stored* (either format)."""
    if not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt_b64, dk_b64 = stored.split("$")
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(dk_b64)
            calc = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, int(iters))
            return secrets.compare_digest(calc, expected)
        except Exception:
            return False
    # Legacy: bare SHA-256 hex
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(legacy, stored)


def _is_legacy_hash(stored: str) -> bool:
    return bool(stored) and not stored.startswith("pbkdf2_sha256$")


# ══════════════════════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════════════════════
def _norm_email(email: str) -> str:
    return (email or "").lower().strip()


def _is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def _password_strength_msg(pw: str) -> Optional[str]:
    """Returns an error string if too weak, otherwise None."""
    if len(pw) < PASSWORD_MIN_LEN:
        return f"Şifre en az {PASSWORD_MIN_LEN} karakter olmalı."
    return None


def _clean_expired() -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM otp_codes       WHERE expires_at < datetime('now')")
    conn.execute("DELETE FROM password_resets WHERE expires_at < datetime('now')")
    conn.commit()
    conn.close()


def _new_code() -> str:
    return f"{secrets.randbelow(900_000) + 100_000:06d}"


# ══════════════════════════════════════════════════════════════════════════════
# Registration / login
# ══════════════════════════════════════════════════════════════════════════════
def register_user(email: str, password: str, full_name: str = "") -> dict:
    """Create a new account (unverified)."""
    email = _norm_email(email)
    if not email or not password:
        return {"ok": False, "msg": "Email ve şifre gerekli."}
    if not _is_valid_email(email):
        return {"ok": False, "msg": "Geçerli bir email adresi girin."}
    weak = _password_strength_msg(password)
    if weak:
        return {"ok": False, "msg": weak}

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO users
                   (email, password, is_verified, full_name,
                    password_updated_at)
                 VALUES (?, ?, 0, ?, datetime('now'))""",
            (email, _hash(password), (full_name or "").strip()),
        )
        conn.commit()
        return {"ok": True,
                "msg": "Kayıt başarılı. Email doğrulama kodu gönderildi."}
    except sqlite3.IntegrityError:
        return {"ok": False, "msg": "Bu email adresi zaten kayıtlı."}
    finally:
        conn.close()


def login_user(email: str, password: str) -> dict:
    """Authenticate. On success, transparently rotate legacy hashes to PBKDF2."""
    email = _norm_email(email)
    if not email or not password:
        return {"ok": False, "user": None, "msg": "Email ve şifre gerekli."}

    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "user": None, "msg": "Email veya şifre hatalı."}

    if not _verify(password, row["password"]):
        conn.close()
        return {"ok": False, "user": None, "msg": "Email veya şifre hatalı."}

    # Transparent legacy → PBKDF2 upgrade
    if _is_legacy_hash(row["password"]):
        conn.execute(
            """UPDATE users SET password=?, password_updated_at=datetime('now')
                WHERE email=?""",
            (_hash(password), email),
        )
        conn.commit()

    if not row["is_verified"]:
        conn.close()
        return {"ok": False, "user": dict(row),
                "msg": "Email doğrulanmamış.",
                "needs_verify": True}

    conn.close()
    return {"ok": True, "user": dict(row), "msg": "Giriş başarılı."}


def get_user(email: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?",
                       (_norm_email(email),)).fetchone()
    conn.close()
    return dict(row) if row else None


def user_exists(email: str) -> bool:
    return get_user(email) is not None


# ══════════════════════════════════════════════════════════════════════════════
# OTP (email verification)
# ══════════════════════════════════════════════════════════════════════════════
def generate_otp(email: str) -> str:
    _clean_expired()
    email = _norm_email(email)
    code  = _new_code()
    expires = (datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)
               ).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    conn.execute("DELETE FROM otp_codes WHERE email=?", (email,))
    conn.execute(
        "INSERT INTO otp_codes (email, code, expires_at) VALUES (?,?,?)",
        (email, code, expires),
    )
    conn.commit()
    conn.close()
    return code


def verify_otp(email: str, code: str) -> dict:
    _clean_expired()
    email = _norm_email(email)
    code  = (code or "").strip()
    conn = _get_conn()
    row = conn.execute(
        """SELECT * FROM otp_codes
            WHERE email=? AND code=? AND used=0
              AND expires_at > datetime('now')""",
        (email, code),
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "msg": "Kod hatalı veya süresi dolmuş."}
    conn.execute("UPDATE otp_codes SET used=1 WHERE email=? AND code=?",
                 (email, code))
    conn.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
    conn.commit()
    conn.close()
    return {"ok": True, "msg": "Email doğrulandı. Giriş yapabilirsiniz."}


# ══════════════════════════════════════════════════════════════════════════════
# Password reset
# ══════════════════════════════════════════════════════════════════════════════
def request_password_reset(email: str) -> dict:
    """Generate a reset code for *email* and email it (or return as fallback).

    NOTE: To prevent user enumeration we return ``ok=True`` even when the
    account doesn't exist — the caller sees the same success UI either way.
    """
    _clean_expired()
    email = _norm_email(email)

    if not _is_valid_email(email):
        return {"ok": False, "msg": "Geçerli bir email adresi girin."}

    # Same success response regardless of existence
    if not user_exists(email):
        return {"ok": True, "msg": "Eğer hesap varsa, sıfırlama kodu gönderildi.",
                "exists": False}

    code = _new_code()
    expires = (datetime.now() + timedelta(minutes=RESET_TTL_MINUTES)
               ).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    conn.execute("DELETE FROM password_resets WHERE email=?", (email,))
    conn.execute(
        "INSERT INTO password_resets (email, code, expires_at) VALUES (?,?,?)",
        (email, code, expires),
    )
    conn.commit()
    conn.close()

    mail_res = send_reset_email(email, code)
    return {
        "ok": True,
        "msg": "Sıfırlama kodu gönderildi." if mail_res["ok"]
               else "SMTP kurulu değil — kod ekranda gösteriliyor.",
        "exists": True,
        "mail_ok": mail_res["ok"],
        "fallback_code": code if not mail_res["ok"] else None,
    }


def reset_password(email: str, code: str, new_password: str) -> dict:
    """Validate the reset code and set a new password."""
    _clean_expired()
    email = _norm_email(email)
    code  = (code or "").strip()

    weak = _password_strength_msg(new_password)
    if weak:
        return {"ok": False, "msg": weak}

    conn = _get_conn()
    row = conn.execute(
        """SELECT * FROM password_resets
            WHERE email=? AND code=? AND used=0
              AND expires_at > datetime('now')""",
        (email, code),
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "msg": "Kod hatalı veya süresi dolmuş."}

    conn.execute("UPDATE password_resets SET used=1 WHERE email=? AND code=?",
                 (email, code))
    conn.execute(
        """UPDATE users
              SET password=?, password_updated_at=datetime('now'),
                  is_verified=1
            WHERE email=?""",
        (_hash(new_password), email),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "msg": "Şifreniz güncellendi. Giriş yapabilirsiniz."}


def change_password(email: str, old_password: str, new_password: str) -> dict:
    """Authenticated password change (for a logged-in user)."""
    email = _norm_email(email)
    user = get_user(email)
    if not user:
        return {"ok": False, "msg": "Kullanıcı bulunamadı."}
    if not _verify(old_password, user["password"]):
        return {"ok": False, "msg": "Mevcut şifre hatalı."}
    weak = _password_strength_msg(new_password)
    if weak:
        return {"ok": False, "msg": weak}

    conn = _get_conn()
    conn.execute(
        """UPDATE users
              SET password=?, password_updated_at=datetime('now')
            WHERE email=?""",
        (_hash(new_password), email),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "msg": "Şifre güncellendi."}


# ══════════════════════════════════════════════════════════════════════════════
# SMTP helpers
# ══════════════════════════════════════════════════════════════════════════════
def _smtp_config() -> dict:
    """Pull SMTP config from env vars OR Streamlit secrets.

    Streamlit secrets only resolve when called from within a Streamlit
    runtime; we guard the import to keep the engine importable from CLI.
    """
    cfg = {
        "host":      os.getenv("SMTP_HOST", ""),
        "port":      int(os.getenv("SMTP_PORT", "587") or 587),
        "user":      os.getenv("SMTP_USER", ""),
        "pwd":       os.getenv("SMTP_PASS", ""),
        "from":      os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", ""),
        "from_name": os.getenv("SMTP_FROM_NAME", "Yatırım Danışmanım"),
    }
    if not cfg["host"]:
        try:
            import streamlit as st  # noqa: WPS433
            sec = st.secrets.get("smtp", {})  # type: ignore[attr-defined]
            if sec:
                cfg["host"]      = sec.get("host", cfg["host"])
                cfg["port"]      = int(sec.get("port", cfg["port"]))
                cfg["user"]      = sec.get("user", cfg["user"])
                cfg["pwd"]       = sec.get("password", cfg["pwd"])
                cfg["from"]      = sec.get("from", cfg["from"]) or cfg["user"]
                cfg["from_name"] = sec.get("from_name", cfg["from_name"])
        except Exception:
            pass
    return cfg


def _send_html_mail(to_addr: str, subject: str, body_html: str) -> dict:
    cfg = _smtp_config()
    if not cfg["host"] or not cfg["user"]:
        return {"ok": False, "msg": "SMTP ayarlanmamış."}
    try:
        from email.utils import formataddr
        from_header = formataddr((cfg.get("from_name") or "", cfg["from"]))
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = from_header
        msg["To"]      = to_addr
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.starttls()
            s.login(cfg["user"], cfg["pwd"])
            # Envelope-from must be the plain address (no display name)
            s.sendmail(cfg["from"], to_addr, msg.as_string())
        return {"ok": True, "msg": "Gönderildi."}
    except Exception as e:
        return {"ok": False, "msg": f"Email gönderilemedi: {e}"}


def _branded_code_email(title: str, intro: str, code: str, ttl_min: int) -> str:
    return f"""
<html><body style="font-family:-apple-system,'Inter',sans-serif;
                   background:#0a0d12;padding:40px;color:#e6ebf2;">
  <div style="max-width:440px;margin:0 auto;background:#11151c;
              border-radius:12px;padding:32px;border:1px solid #1a1f2a;">
    <div style="font-size:18px;font-weight:700;margin-bottom:6px;">
      Yatırım Danışmanım</div>
    <div style="font-size:13px;color:#94a3b8;margin-bottom:8px;">{title}</div>
    <div style="font-size:13px;color:#94a3b8;margin-bottom:22px;line-height:1.5;">
      {intro}</div>
    <div style="font-size:32px;font-weight:700;color:#7aa3ff;
                letter-spacing:0.18em;text-align:center;
                background:#0a0d12;border:1px solid #1a1f2a;
                border-radius:10px;padding:18px;
                font-family:'JetBrains Mono',monospace;">
      {code}</div>
    <div style="font-size:12px;color:#64748b;margin-top:14px;text-align:center;">
      Bu kod {ttl_min} dakika geçerlidir. Bu işlemi siz başlatmadıysanız
      mesajı görmezden gelin.</div>
  </div>
</body></html>"""


def send_otp_email(email: str, code: str) -> dict:
    return _send_html_mail(
        to_addr=email,
        subject="Yatırım Danışmanım — Email Doğrulama Kodu",
        body_html=_branded_code_email(
            title="Email doğrulama kodunuz",
            intro="Hesabınızı aktive etmek için aşağıdaki 6 haneli kodu girin.",
            code=code, ttl_min=OTP_TTL_MINUTES,
        ),
    )


def send_reset_email(email: str, code: str) -> dict:
    return _send_html_mail(
        to_addr=email,
        subject="Yatırım Danışmanım — Şifre Sıfırlama Kodu",
        body_html=_branded_code_email(
            title="Şifre sıfırlama kodunuz",
            intro="Şifrenizi sıfırlamak için aşağıdaki 6 haneli kodu girin.",
            code=code, ttl_min=RESET_TTL_MINUTES,
        ),
    )


# ── Initialize on import ─────────────────────────────────────────────────────
init_db()
