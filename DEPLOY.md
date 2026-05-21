# 🚀 Deploy — Yatırım Danışmanım

Streamlit Community Cloud üzerine **0 TL** ile yayına alma talimatı.
Toplam süre: ~10 dakika.

---

## ✅ Önceden Hazırlanan (Senin için yapıldı)

- [x] `requirements.txt` — cloud-uyumlu (streamlit, plotly dahil; customtkinter yorumlandı)
- [x] `runtime.txt` — `python-3.11`
- [x] `.gitignore` — `secrets.toml`, `data/`, `logs/`, `*.db` hariç tutuldu
- [x] `src/config_loader.py` — API anahtarları `st.secrets`'tan okur
- [x] Git init + ilk commit yapıldı (`719686d`)
- [x] Hiçbir secret git'te değil — sadece `.example` dosyası var

---

## ADIM 1 · GitHub'a Push (3 dakika)

### 1.1 — GitHub'da yeni repo oluştur
1. https://github.com/new aç
2. Repository name: **`yatirim-danismanim`** (veya istediğin)
3. Visibility: **Private** (Streamlit Cloud free plan private repo destekler)
4. **README/gitignore/license ekleme** (boş repo)
5. **Create repository** tıkla

### 1.2 — Local'i GitHub'a bağla
GitHub repo oluştuktan sonra terminalde (proje klasöründe):

```bash
cd C:\Users\MB\Desktop\HedgeFundAI
git remote add origin https://github.com/KULLANICI_ADIN/yatirim-danismanim.git
git push -u origin main
```

> GitHub şifre sormaz — **Personal Access Token (PAT)** ister.
> Token yoksa: https://github.com/settings/tokens → "Generate new token (classic)" →
> `repo` scope seç → kopyala. Şifre yerine bunu yapıştır.

---

## ADIM 2 · Streamlit Community Cloud (5 dakika)

### 2.1 — Hesap aç + Streamlit Cloud
1. https://share.streamlit.io aç
2. **"Continue with GitHub"** → GitHub hesabınla giriş yap
3. Streamlit'e GitHub repo'na erişim izni ver

### 2.2 — Yeni app oluştur
1. **"Create app"** → **"Deploy a public app from GitHub"**
2. Form:
   - **Repository:** `KULLANICI_ADIN/yatirim-danismanim`
   - **Branch:** `main`
   - **Main file path:** `web_app.py`
   - **App URL (custom subdomain):** `yatirim-danismanim` _(istersen)_
3. **"Advanced settings"** aç:
   - **Python version:** `3.11`
   - **Secrets:** ↓ aşağıdaki bloğu yapıştır

### 2.3 — Secrets bloğunu yapıştır (KRİTİK)

`.streamlit/secrets.toml` dosyandaki içeriği **aynen** kopyala
ve Streamlit Cloud paneline yapıştır:

```toml
[smtp]
host      = "smtp.gmail.com"
port      = 587
user      = "sergenbasakci@gmail.com"
password  = "ssfn bspq vqsc sdsa"
from      = "sergenbasakci@gmail.com"
from_name = "Yatırım Danışmanım"

[api_keys]
binance_api_key = ""
binance_secret  = ""
finnhub         = ""
newsapi         = ""
fred            = ""
glassnode       = ""

[telegram]
bot_token = ""
chat_id   = ""

[alerts]
smtp_host   = ""
smtp_port   = 587
smtp_user   = ""
smtp_pass   = ""
alert_email = ""
```

### 2.4 — Deploy
**"Deploy"** tıkla → 2-3 dakika içinde:
- ✅ `requirements.txt` yüklenir
- ✅ `web_app.py` başlatılır
- ✅ Uygulama canlı: `https://yatirim-danismanim.streamlit.app`

---

## ADIM 3 · İlk Test (2 dakika)

1. Canlı URL'i aç
2. Admin hesabıyla gir:
   - Email: `admin@hedgefund.local`
   - Şifre: `Efsane4747++**`
3. Sidebar'ı kontrol et (Dashboard / Fırsatlar / Analiz vb.)
4. **Yeni hesap oluştur** dene → Gmail'ine OTP gelmeli

---

## 🔁 Sonraki Güncellemeler

Kod değiştirdiğinde:
```bash
git add .
git commit -m "açıklama"
git push
```

Streamlit Cloud **otomatik algılar** ve uygulamayı 30 saniye içinde yeniden deploy eder.

---

## ⚠️ Önemli Notlar

| Durum | Bilgi |
|-------|-------|
| **Veritabanı kalıcılığı** | Streamlit Cloud disk'i ephemeral — kullanıcı DB her deploy'da sıfırlanabilir. Kalıcı için Supabase/PostgreSQL eklemek gerekir. |
| **Cold start** | App 7 gün inaktif kalırsa uyur, ilk istekte 15-30 sn açılır. |
| **RAM limiti** | Free plan 1 GB. Mevcut app rahat sığar. |
| **Public erişim** | URL'i bilen herkes erişebilir. Kayıt zorunlu olduğu için spam minimum. |
| **Domain** | Streamlit subdomain bedava. Kendi domain'in için DNS CNAME → `share.streamlit.app` (Cloud paneli üzerinden). |

---

## 🆘 Sorun Giderme

| Hata | Çözüm |
|------|-------|
| `ModuleNotFoundError: customtkinter` | `requirements.txt`'te yorum satırı olduğundan emin ol; cloud'a push et |
| `No SMTP configured` | Streamlit Cloud Secrets paneline `[smtp]` bloğunu yapıştırdın mı? |
| `OperationalError: database is locked` | DB ephemeral, kabul edilebilir; persistent için Supabase kur |
| Mail spam'a düşüyor | Gmail'de "Spam değil" işaretle, sonrakiler inbox'a düşer |
| App uyuyor | Free plan davranışı — Pro ($20/ay) ile kapatabilirsin |

---

## 🎉 Tamamlandığında

Linki bana gönder, birlikte testlerden geçirelim.
