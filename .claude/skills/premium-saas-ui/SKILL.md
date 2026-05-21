---
name: premium-saas-ui
description: |
  Streamlit (Python) tabanlı "Yatırım Danışmanım" uygulaması için premium SaaS
  dashboard tasarım standartları. Linear / Vercel / Stripe Dashboard / Raycast /
  Attio / Supabase kalitesi hedeftir; ancak Streamlit'in olanakları içinde
  uygulanır (Tailwind / shadcn / React YOK).
  Bu skill UI değişikliği yapıldığında MUTLAKA referans alınır.
trigger:
  - "UI iyileştirmesi, redesign, refactor"
  - "Yeni component, kart, tablo, modal, form"
  - "Dashboard, sidebar, header düzenleme"
  - "Loading / empty / error state ekleme"
  - "Responsive / accessibility / animation"
tags: [streamlit, ui, design-system, premium-saas]
---

# Premium SaaS UI — Yatırım Danışmanım

## 0. Felsefe

> "Bir Bloomberg terminali kadar **dense**, bir Stripe Dashboard kadar **temiz**,
> bir Linear kadar **hassas**, bir Raycast kadar **hızlı** hissettir."

**Üç ana kural:**
1. **Hiyerarşi her şeydir.** Eşit önem yok. Bir ekranda **bir** birincil aksiyon olur.
2. **Density > clutter.** Daha çok bilgi göstermek için spacing'i azaltma — gereksizi at.
3. **Boyalı renkler değil, **doğru aralık**.** Renk = anlam (semantic). Süs değil.

---

## 1. Design Tokens — Kanonik Kaynak

**Tek doğru:** `ui_pages/styles.py` → `C` dict.

### Color palette (DİKKAT: yeni renk EKLEME, var olanı kullan)

```
Canvas / surfaces:
  bg            #0a0d12   graphite canvas
  bg_elev       #11151c   elevated panel
  surface       rgba(20,25,33,0.86)
  surface_alt   rgba(15,19,26,0.70)
  sidebar       #07090d

Borders:
  border        rgba(148,163,184,0.08)
  border_strong rgba(148,163,184,0.18)  hover/active
  divider       rgba(148,163,184,0.06)
  border_solid  #1a1f2a                 hard divider

Text:
  t1  #e6ebf2  primary
  t2  #94a3b8  muted / secondary
  t3  #64748b  label / caption
  t4  #475569  faint / hint / disabled

Accent (SINGLE primary accent — institutional steel blue):
  accent       #5b8cff
  accent_hover #7aa3ff
  accent_dim   rgba(91,140,255,0.10)   tint
  accent_glow  rgba(91,140,255,0.24)   focus ring
  accent_deep  #3b6ee0                  border

Secondary accent (AI / insight tag ONLY — başka yerde kullanma):
  accent2      #f5b25b (amber)
  accent2_dim  rgba(245,178,91,0.12)

Semantic (market direction ONLY — UI chrome değil):
  buy   #22c55e   sell   #ef4444
  warn  #f59e0b   info   #5b8cff
  + _dim varyantları rgba 0.12 alpha
```

**Kural:** UI chrome (button, sidebar, link) **sadece** `accent` (mavi) kullanır.
Yeşil/kırmızı **yalnızca** piyasa yön bilgisi için (al/sat, P&L pozitif/negatif).

### Typography scale

```
font-family: 'Inter Tight' (display) | 'Inter' (body) | 'JetBrains Mono' (numerics)

24px  display / page title
19px  section heading
16px  card title
14px  body
13.5px secondary body / table cell
12.5px label
11px  micro label (UPPERCASE + letter-spacing 0.12em)
10.5px footnote
10px  legal / footer micro

Weights: 400 / 500 / 600 / 700 only.
Numerics: always `font-variant-numeric: tabular-nums`.
```

### Spacing — 4px grid (STRICT)

```
4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64
```

Padding/margin sadece bu değerlerden. 13px, 17px, 27px **YASAK**.

### Radius

```
6px   tag / badge / chip
8px   button / input
10px  card (default)
12px  card_lg / dialog
999px pill / dot
```

### Shadow

```
soft:   0 1px 2px rgba(0,0,0,0.20)
card:   0 1px 0 rgba(255,255,255,0.04) inset, 0 4px 12px -4px rgba(0,0,0,0.40)
focus:  0 0 0 3px {accent_glow}
elev:   0 12px 32px -12px rgba(0,0,0,0.60)
```

### Motion

```
duration:   120ms (micro), 180ms (default), 240ms (modal)
easing:     cubic-bezier(0.22, 0.61, 0.36, 1)   /* "swift in-out" */
properties: transform, opacity, border-color, background-color
```

Asla `transition: all` kullanma — performans + jank.

---

## 2. Component Standartları

### Button

| Variant | Bg | Text | Border | Hover |
|---|---|---|---|---|
| Primary | `accent` | white | none | `accent_hover` + scale(1.02) |
| Secondary | `surface_alt` | `t1` | `border` | `surface` + `border_strong` |
| Ghost | transparent | `t2` | none | `surface_alt` |
| Destructive | `sell` | white | none | brightness(1.1) |

- Padding: `10px 16px` (md), `8px 12px` (sm), `12px 20px` (lg)
- Radius: `8px`
- Focus: `accent_glow` 3px ring
- Loading: spinner içeride, text aria-hidden, button width sabit

### Card

```
background: {surface}
border:     1px solid {border}
radius:     10px
padding:    20px (default) | 24px (lg) | 16px (sm)
```

- Hover (interactive): border → `border_strong`, +1px elev shadow
- Title: 16px / 600 / `t1`
- Kicker: 11px UPPERCASE / `t3` / letter-spacing 0.12em
- Body: 14px / `t2`

### Input / Select

```
height: 38px
padding: 0 12px
background: {bg_elev}
border: 1px solid {border}
radius: 8px
text: 14px / 400 / {t1}
placeholder: {t3}
focus: border {accent}, ring {accent_glow}
```

### Table — Dense

- Row height: 44px (data) / 36px (compact)
- Header: 11px UPPERCASE `t3`, bg `surface_alt`, border-bottom `border_solid`
- Cell: 13.5px `t1`, numerics tabular, right-aligned
- Row hover: bg `surface_alt`
- Zebra: NONE (kurumsal arınmış look)

### Pill / Badge

- Padding `4px 8px`, radius `999px`
- 11px / 600 / UPPERCASE / letter-spacing 0.08em
- Bg `*_dim`, text `*` (semantic family)

### Sidebar

- Width: 240px (fixed)
- Bg: `sidebar` (deeper than canvas)
- Nav item: 36px h, 12px padding-x, 13.5px text
- Active: bg `accent_dim`, left-border 2px `accent`, text `t1`
- Inactive: text `t2`, hover bg `surface_alt`

### Modal / Dialog

- Overlay: `rgba(0,0,0,0.60)` + backdrop-filter blur(4px)
- Panel: max-width 480px, padding 32px, radius 12px, shadow `elev`
- Close: top-right ghost icon
- Stack: title (19px/600) → body (14px/t2) → actions (right-aligned)

### Tabs (segmented control)

- Container: bg `surface_alt`, radius 8px, padding 2px
- Tab: 32px h, 12px padding-x, 13.5px / 500
- Active: bg `bg_elev`, text `t1`, shadow soft
- Inactive: text `t2`

---

## 3. State Patterns (HEPSİ ZORUNLU)

### Loading
```python
from ui_pages.components import skeleton
skeleton(rows=3, h=44, gap=8)   # bekleyen tablo
skeleton(rows=1, h=160)         # bekleyen kart
```

### Empty
```python
from ui_pages.components import empty_state
empty_state(
    title="Henüz veri yok",
    hint="İlk varlığını eklediğinde burada görünecek.",
    icon="○",   # nötr geometrik, emoji DEĞİL
)
```

### Error
- Banner: bg `sell_dim`, border-left 3px `sell`, padding 12px 16px
- Mesaj sade, eylem-odaklı: "Veri yüklenemedi. Tekrar dene →"

### Disabled
- Opacity 0.5, pointer-events none, cursor not-allowed

---

## 4. Streamlit-Spesifik Kurallar

### HTML Sınırları
- `st.markdown` her çağrı **ayrı container**'da wrap'lanır.
- `<div>` açıp **sonraki çağrıda kapatamayız**. Self-contained kart yazın.
- `st.columns(...)` her sütun ayrı bir container.

### CSS Önceliği
```css
/* Global rule'u override etmek için: */
html body section.main .block-container { … !important }
```

### Sidebar Collapse
- `[data-testid="stHeader"]` collapse kontrolünü içerir → SADECE `background: transparent; height: 0`
- `display: none` YAPMA — buton kaybolur.

### Page config
```python
st.set_page_config(
    page_title="Yatırım Danışmanım",
    page_icon="📊",   # veya inline SVG data URI
    layout="wide",
    initial_sidebar_state="expanded",
)
```

---

## 5. Accessibility

- Kontrast: t1/bg ≥ 12:1, t2/bg ≥ 7:1, t3/bg ≥ 4.5:1 (geçildi)
- Focus ring: her interaktif element için 3px `accent_glow`
- `aria-label` her ikon-only butonda
- Klavye: tab order doğal HTML akışını takip etsin; Streamlit native widget'ları zaten erişilebilir
- Motion-reduce: `@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }`

---

## 6. Responsive

Streamlit'in mobile davranışı sınırlı. Kurallar:
- `st.columns(...)` mobile'da otomatik wrap eder — `gap="small"` tercih et
- Min content width: 320px
- Sidebar mobile'da auto-collapse — buton mutlaka erişilebilir
- Tablolar mobile'da yatay scroll içinde — sarmalama: `overflow-x: auto`
- KPI strip → mobile'da 2x2 grid (her tile ≥ 140px)

---

## 7. Animation / Micro-interaction

| Olay | Animasyon |
|---|---|
| Hover | `transform: translateY(-1px)` + border shift (180ms) |
| Click | `transform: scale(0.98)` (120ms) |
| Modal aç | `opacity 0→1 + scale 0.96→1` (240ms) |
| Toast | `slide-in-right 200ms` + auto-dismiss 4s |
| Tab change | bg transition 180ms |
| Loading dot | 1.2s infinite ease-in-out pulse |

Yasak: parallax, full-page entrance, bouncy easing, marquee, glitter.

---

## 8. Plotly Chart Standartları

Her chart **mutlaka** `apple_layout()` kullanır (bkz. `styles.py`):
- Grid: subtle `border` color
- Axis: tick `t3`, label `t2`
- Colorway: steel-blue primary + analogous
- Margin: t=12, r=12, b=24, l=40
- Font: Inter 11px
- Hover: dark elev panel, no animation

Asla chart içine emoji veya başlık ikon koyma.

---

## 9. Yapma Listesi

❌ Yeni accent renk (mavi dışında UI chrome)
❌ Inline hex code
❌ Gradient (sadece çok subtle accent_dim → transparent OK)
❌ Drop shadow > 32px blur
❌ Glassmorphism (premium değil, dated)
❌ Neon glow (oyun tarzı)
❌ Emoji ikon ciddi UI bölgesinde
❌ Birden fazla font weight kademesi atlatma (örn: 400 → 700 OK; 400 → 500 → 600 OK; 400 → 600 atlama tutarsız)

---

## 10. Yeni İş Akışı

1. **İhtiyacı tanı.** Hangi sayfa? Hangi state? Mevcut primitive var mı?
2. **`components.py`'a bak.** Reusable varsa kullan. Yoksa **ekle**, ad-hoc HTML yazma.
3. **`C` dict'ten renk seç.** Yeni renk yazma.
4. **4px grid spacing.** Diğer değer **yok**.
5. **State'leri ekle.** loading / empty / error / disabled — hepsi.
6. **Compile + HTTP teyit.** `py_compile` + `curl localhost:8501`.
7. **(Varsa) visual snapshot.** `python scripts/snap.py`.

---

## 11. Referans Estetik Hedefleri

Şu ekranlara bakarak çalış:

- **Linear** — sidebar density, command palette, micro-typography
- **Stripe Dashboard** — table, KPI tile, time-range selector
- **Vercel** — dark canvas, accent restraint, monospace numerics
- **Raycast** — list/detail layout, keyboard hints
- **Attio** — table interactions, inline edit, filter chips
- **Supabase** — code-adjacent UI, status indicators, log viewer

**Asla** TradingView, Robinhood, Coinbase Pro'yu referans alma — bunlar daha yüksek
chroma + flashier; bizim hedef "**institutional sober**".
