# HedgeFund AI — Authentication

Local-first SQLite authentication with PBKDF2 password hashing, email
OTP verification, and password-reset codes.

---

## Default admin account

| Field    | Value                  |
| -------- | ---------------------- |
| Email    | `admin@hedgefund.local`|
| Password | `Efsane4747++**`       |

On every startup `src.auth.init_db()` ensures this account exists and is
marked verified + admin. Change the password from inside the app — the
default is only seeded if no canonical admin row exists yet.

> **First login from an old DB:** if your `data/users.db` was created
> earlier with the bare `admin`/`admin` row, the next startup will
> migrate it to the canonical email and rotate the password to
> `Efsane4747++**`. The legacy login string `admin` will no longer
> work — use the email from now on.

If you ever need to force-reset the admin password back to the seeded
value, set `HEDGEFUND_FORCE_ADMIN_RESET=1` in the environment for one
startup, then remove it.

---

## What's stored locally

`data/users.db` (SQLite). Three tables:

| Table             | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `users`           | account + PBKDF2 password hash + verified flag   |
| `otp_codes`       | one-time codes for email verification            |
| `password_resets` | one-time codes for password resets               |

Passwords are stored as `pbkdf2_sha256$<iters>$<b64-salt>$<b64-dk>` with
200 000 iterations. Pre-existing SHA-256 hashes are accepted on login
and **transparently upgraded** to PBKDF2 on the user's next successful
login (no extra step required).

`data/` is git-ignored.

---

## Auth flows

### Register
1. Email + password (≥ 8 chars) + confirm.
2. Account is created with `is_verified = 0`.
3. A 6-digit code is generated, emailed if SMTP is configured,
   otherwise displayed in the UI as a fallback (development mode).
4. User enters the code on the OTP screen → account becomes verified.

### Login
1. Email + password.
2. If `is_verified = 0` the user is sent back through the OTP flow.
3. Successful login mints a Streamlit session.

### Forgot password
1. Click **Şifremi unuttum →** under the login form.
2. Enter your email; a 6-digit reset code is generated (15-min TTL).
3. To prevent user enumeration the next screen is always shown — even
   if the email doesn't exist no reset row is written.
4. Enter code + new password twice (≥ 8 chars).
5. Password is rehashed (PBKDF2) and you're returned to the login
   screen with a success toast.

All codes (OTP & reset) are single-use and time-limited; expired rows
are pruned on every interaction.

---

## Email (SMTP) setup

Email is optional for local development — codes appear in the UI when
SMTP is not configured. For production deploys, configure SMTP via
**either** environment variables **or** `.streamlit/secrets.toml`.

### Option A — environment variables
```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your.address@gmail.com
export SMTP_PASS="abcd efgh ijkl mnop"   # Gmail App Password
export SMTP_FROM=your.address@gmail.com
```

### Option B — `.streamlit/secrets.toml`
Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
and fill it in. The file is git-ignored. On Streamlit Community Cloud
paste the same TOML under **App settings → Secrets**.

### Free SMTP providers (no card required)

| Provider | Free tier             | Notes                                      |
| -------- | --------------------- | ------------------------------------------ |
| Gmail    | ~500 mails/day        | Needs 2FA + App Password                   |
| Brevo    | 300 mails/day forever | Best deliverability; SMTP creds in panel   |
| Resend   | 3 000 mails/month     | Modern API, simple SMTP relay              |

---

## Files involved

```
src/auth.py                       # engine: hashing, DB, OTP, reset, SMTP
ui_pages/login.py                 # UI: login / register / OTP / forgot / reset
.streamlit/secrets.toml.example   # template (copy to secrets.toml)
.streamlit/config.toml            # Streamlit theme
data/users.db                     # local SQLite store (git-ignored)
```

---

## Security checklist before going public

- [ ] Rotate every key currently in `config/settings.yaml`.
- [ ] Move all API keys to `.streamlit/secrets.toml` or env vars.
- [ ] Run `git status` and confirm `secrets.toml`, `data/`, `.env*`,
      and `config/settings.yaml` (if it still holds real keys) are
      ignored.
- [ ] Confirm Binance API key has **Withdraw disabled** + IP whitelist.
- [ ] Change the default admin password right after first login.
- [ ] Configure SMTP — without it, reset codes appear in the UI
      (fine for local, **not** for production).
