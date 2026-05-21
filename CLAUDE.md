# Yatırım Danışmanım — Proje Kuralları (CLAUDE.md)

> Bu dosya Claude için kalıcı proje kurallarıdır. Her oturumda baştan okunur.
> Aşağıdaki kurallar **business logic, auth, API, routing, state management** ve
> diğer çalışan davranışı **kırmadan** premium SaaS seviyesinde UI üretmek içindir.

---

## 1. Stack — Olduğu Gibi

| Katman | Teknoloji |
|---|---|
| Frontend | **Streamlit (Python)** — JSX, Tailwind, shadcn, React YOK |
| Styling | `st.markdown(..., unsafe_allow_html=True)` üzerinden enjekte edilen **özel CSS** (bkz. `ui_pages/styles.py`) |
| Charts | **Plotly** (`apple_layout()` teması) — Recharts/D3 yok |
| State | `st.session_state` |
| Auth | `src/auth.py` (SQLite + PBKDF2 + SMTP OTP) |
| Backend | Python — `src/*.py` (data_collector, decision_engine, vb.) |
| Config | `config/settings.yaml` + `.streamlit/secrets.toml` |

**Yasak:** Bu projeye Tailwind, shadcn/ui, lucide-react, framer-motion, Next.js,
Vite, npm/pnpm/yarn **eklenmez**. Streamlit server-side render eder; bu kütüphaneler
uygulanabilir değildir. JS toolchain talepleri Streamlit-eşdeğerlerine çevrilir
(örn. lucide-react → SVG inline veya emoji; framer-motion → CSS keyframe animasyon).

---

## 2. Dokunulmaz Sınırlar

Aşağıdakileri **değiştirme** (kullanıcı açıkça istemedikçe):

- `src/*.py` içindeki business logic, decision engine, data fetch katmanı
- `src/auth.py` içindeki kripto/hash/SMTP davranışı (UI metni değiştirilebilir)
- `config/settings.yaml` şeması, decision weights, risk parametreleri
- SQLite şeması (`data/users.db` migration mantığı)
- `web_app.py` içindeki page routing ve session_state akışı
- API key yükleme yolu (`src/config_loader.py` overlay önceliği)

**Değişebilir:**
- `ui_pages/*.py` görsel düzenleme (yapı, kart, başlık, spacing)
- `ui_pages/styles.py` — design tokens, primitives, CSS
- `ui_pages/components.py` — reusable UI primitives
- Renkler, tipografi, spacing, hover/focus/loading durumları

---

## 3. UI Geliştirme Standartları

### Design System — Kanonik Kaynak
- **Tek doğru:** `ui_pages/styles.py` → `C` dict (color tokens) ve `inject_css()`
- Yeni renk **eklemeyin**; mevcutları kullanın
- Component primitive'ler: `ui_pages/components.py` (pill, kpi_tile, section_header, ai_insight_card, skeleton, empty_state, data_table)
- Yeni primitive **components.py'a eklenir**, ad-hoc HTML her dosyada tekrar üretilmez

### Streamlit-Spesifik Kurallar
- `st.markdown` her çağrı **kendi container'ında** wrap'lanır — bir `<div>` açıp sonraki çağrıda kapatmak **çalışmaz**. Kart layout'ları **self-contained** olmalı.
- `st.columns(...)` her sütun ayrı bir container'dır — `<div>` köprülemesi yapma.
- Yüksek-spesifite gerekirse `html body section.main .block-container { … !important }`.
- `[data-testid="stHeader"]` sidebar collapse kontrolünü barındırır → `display:none` yapma, sadece `background: transparent; height: 0`.

### Her Component'te Bulunmalı
- ✅ Hover state (border veya bg shift)
- ✅ Focus state (accent ring: `box-shadow: 0 0 0 3px {C['accent_glow']}`)
- ✅ Loading skeleton (`components.skeleton()`)
- ✅ Empty state (`components.empty_state()`)
- ✅ Error/warning hattı (semantic renk + ikon)
- ✅ Tabular numerics (`font-variant-numeric: tabular-nums`)

### Yasak Anti-pattern'ler
- ❌ Inline yeni renk kodu (örn `color: #ff0000`) — `C[...]` kullan
- ❌ Tek seferlik component HTML — `components.py`'a ekle
- ❌ Birden fazla `st.markdown` arası `<div>` köprüsü
- ❌ Plotly chart'lara renk hardcode — `apple_layout()` tema kullan
- ❌ Emoji ikonlar ciddi kurumsal alanlarda (örn: KPI tile'larda) — sadece nötr SVG / monogram

---

## 4. Değişiklik Sonrası Kontrol Listesi

Her UI değişikliğinden sonra çalıştır:

```bash
# 1. Compile-check
python -m py_compile web_app.py ui_pages/*.py src/auth.py src/config_loader.py

# 2. Streamlit canlı mı?
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501

# 3. (Opsiyonel) Visual snapshot — Playwright kuruluysa
python scripts/snap.py
```

**Streamlit lint/typecheck yoktur** — `py_compile` syntax garantisi verir; runtime hataları
için Streamlit konsolunu izle. `mypy` projeye dahil değildir.

---

## 5. Çalışma Kuralı

- **Mevcut çalışan davranışı bozma** — özellikle auth/API/data flow
- Sadece **gerekli dosyaları** değiştir
- Büyük refactor'ı **küçük parçalara** böl (her parça compile + HTTP teyitten geçsin)
- Hata gördüğünde **bırakma**, düzeltmeden devam etme
- **Gereksiz açıklama yok** — uygulanabilir değişiklik yap

---

## 6. Marka

- **Görünen ad:** Yatırım Danışmanım
- **Mail göndericisi:** Yatırım Danışmanım (`.streamlit/secrets.toml` → `[smtp].from_name`)
- **Browser tab:** Yatırım Danışmanım
- **Sidebar logosu:** Steel-blue kare + monogram **Y**
- **Subtitle:** Yapay Zeka Destekli Asistan

Yeni metin eklerken Türkçe → kısa, kurumsal, lower-key. Emoji minimum.

---

## 7. Skill: Premium SaaS UI

UI işlerinde **mutlaka** `.claude/skills/premium-saas-ui/SKILL.md` referans alınır.
Linear, Vercel, Stripe Dashboard, Raycast, Attio, Supabase kalitesi hedeftir —
ama **Streamlit'in olanakları içinde**.
