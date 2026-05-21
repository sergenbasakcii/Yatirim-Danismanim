"""
HedgeFund AI — Fırsatlar Ekranı  (v2 — Profesyonel Yeniden Tasarım)

Tasarım İlkeleri
────────────────
• Üst özet çubuğu: tarama istatistikleri, piyasa durumu
• Filter Chip sistemi: dropdown yerine tek tıkla açma/kapama
• Skor gauge (dairesel ilerleme): her kartta baskın, okuma kolaylığı
• Karar rozeti: renk + yazı tutarlılığı
• Sıralama çubuğu: sütun başlıkları, anlık güncelleme
• Detay panel sekme sistemi: Genel / Teknik / Gerekçe / İşlem Planı / Eğitim
• Yükleme & boş durum mesajları profesyonel
"""

import math
import threading
import time
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

# Tooltip helper — modül düzeyinde yükle, hot path'te import yok
try:
    from src.ui_widgets import tip as _tip_fn
except Exception:
    def _tip_fn(w, k): pass

# ─────────────────────────────────────────────────────────────
# TEMA — app.py paleti ile %100 senkron
# ─────────────────────────────────────────────────────────────
BG        = "#f6f8fa"
BG_CARD   = "#ffffff"
BG_INPUT  = "#eaeef2"
BG_HOVER  = "#f0f4f8"
BORDER    = "#d0d7de"
BORDER_FOCUS = "#0969da"
ACCENT    = "#0969da"
ACCENT_DIM = "#ddf4ff"
BUY_C     = "#1a7f37"
SELL_C    = "#cf222e"
HOLD_C    = "#9a6700"
TEXT1     = "#1f2328"
TEXT2     = "#57606a"
TEXT3     = "#8c959f"
RED_DIM   = "#ffebe9"
GREEN_DIM = "#dafbe1"
GOLD_DIM  = "#fff8c5"
PURPLE    = "#6f42c1"
PURPLE_DIM = "#fbefff"
ORANGE    = "#bc4c00"
ORANGE_DIM = "#fff1e5"

F_TITLE  = ("Segoe UI", 20, "bold")
F_HEAD   = ("Segoe UI", 13, "bold")
F_SUB    = ("Segoe UI", 12, "bold")
F_BODY   = ("Segoe UI", 11)
F_SMALL  = ("Segoe UI", 10)
F_TINY   = ("Segoe UI", 9)
F_MONO   = ("Consolas",  10)
F_NUM    = ("Segoe UI", 14, "bold")
F_NUM_SM = ("Segoe UI", 11, "bold")

# ─────────────────────────────────────────────────────────────
# RENK SÖZLÜKLERİ
# ─────────────────────────────────────────────────────────────
DECISION_STYLE = {
    "GÜÇLÜ AL":  dict(fg=BUY_C,   bg="#dafbe1", icon="▲▲"),
    "AL":         dict(fg=BUY_C,   bg="#dafbe1", icon="▲"),
    "BİRİKTİR":  dict(fg=ACCENT,  bg=ACCENT_DIM, icon="↗"),
    "İZLE":       dict(fg=HOLD_C,  bg=GOLD_DIM,  icon="◉"),
    "TUTE":       dict(fg=TEXT2,   bg=BG_INPUT,  icon="—"),
    "AZALT":      dict(fg=SELL_C,  bg=RED_DIM,   icon="↘"),
    "SAT":        dict(fg=SELL_C,  bg=RED_DIM,   icon="▼"),
    "KAÇIN":      dict(fg="#6e0505", bg="#ffcdd2", icon="✗"),
}

RISK_STYLE = {
    "çok düşük":   dict(fg=BUY_C,   bg=GREEN_DIM,   emoji="🟢", short="ÇD"),
    "düşük":       dict(fg=ACCENT,  bg=ACCENT_DIM,  emoji="🔵", short="D"),
    "orta":        dict(fg=HOLD_C,  bg=GOLD_DIM,    emoji="🟡", short="O"),
    "orta-yüksek": dict(fg=ORANGE,  bg=ORANGE_DIM,  emoji="🟠", short="OY"),
    "yüksek":      dict(fg=SELL_C,  bg=RED_DIM,     emoji="🔴", short="Y"),
    "çok yüksek":  dict(fg="#6e0505", bg="#ffcdd2",  emoji="⛔", short="ÇY"),
    "spekülatif":  dict(fg="#6e0505", bg="#ffcdd2",  emoji="💀", short="SP"),
}

TYPE_STYLE = {
    "crypto": dict(fg="#0550ae", bg="#ddf4ff",  label="KRIPTO"),
    "stock":  dict(fg=BUY_C,    bg=GREEN_DIM,  label="US HİSSE"),
    "bist":   dict(fg=HOLD_C,   bg=GOLD_DIM,   label="BIST"),
    "etf":    dict(fg=PURPLE,   bg=PURPLE_DIM, label="ETF"),
    "fund":   dict(fg=ORANGE,   bg=ORANGE_DIM, label="FON"),
}

# Skor rengi: 0-100 arası gradient
def score_color(s: float) -> str:
    if s >= 75: return BUY_C
    if s >= 62: return ACCENT
    if s >= 50: return HOLD_C
    if s >= 38: return SELL_C
    return "#6e0505"

def score_bg(s: float) -> str:
    if s >= 75: return GREEN_DIM
    if s >= 62: return ACCENT_DIM
    if s >= 50: return GOLD_DIM
    if s >= 38: return RED_DIM
    return "#ffcdd2"

def fmt_price(p):
    if p is None: return "—"
    if p >= 10000: return f"${p:,.0f}"
    if p >= 100:   return f"${p:,.2f}"
    if p >= 1:     return f"${p:.4f}"
    return f"${p:.6f}"

def fmt_pct(v, sign=True):
    if v is None: return "—"
    return f"{'+' if sign and v >= 0 else ''}{v:.2f}%"

def pct_color(v):
    if v is None: return TEXT3
    return BUY_C if v >= 0 else SELL_C


# ═════════════════════════════════════════════════════════════
#  YARDIMCI BİLEŞENLER
# ═════════════════════════════════════════════════════════════

class Divider(ctk.CTkFrame):
    def __init__(self, master, vertical=False, **kw):
        if vertical:
            super().__init__(master, width=1, fg_color=BORDER, **kw)
        else:
            super().__init__(master, height=1, fg_color=BORDER, **kw)


class Badge(ctk.CTkLabel):
    """Küçük renkli rozet."""
    def __init__(self, master, text, fg, bg, font=F_TINY, **kw):
        super().__init__(master, text=f" {text} ",
                         font=font, text_color=fg,
                         fg_color=bg, corner_radius=4, **kw)


class FilterChip(ctk.CTkButton):
    """Toggle edilebilir filtre çipi."""
    def __init__(self, master, text, on_toggle, **kw):
        self._active = False
        self._text   = text
        self._cb     = on_toggle
        super().__init__(
            master, text=text,
            font=F_TINY, height=26, corner_radius=13,
            fg_color=BG_INPUT, hover_color=BG_HOVER,
            text_color=TEXT2, border_width=1, border_color=BORDER,
            command=self._toggle, **kw)

    def _toggle(self):
        self._active = not self._active
        self._refresh()
        self._cb(self._text, self._active)

    def _refresh(self):
        if self._active:
            self.configure(fg_color=ACCENT, text_color="#ffffff",
                           border_color=ACCENT)
        else:
            self.configure(fg_color=BG_INPUT, text_color=TEXT2,
                           border_color=BORDER)

    def set_active(self, val: bool):
        self._active = val
        self._refresh()

    @property
    def active(self):
        return self._active


class ScoreGauge(ctk.CTkCanvas):
    """
    Dairesel skor göstergesi (Canvas tabanlı).
    Dış halka → renk, İç → skor sayısı.
    """
    SIZE = 54

    def __init__(self, master, score: float, **kw):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         bg=BG_CARD, highlightthickness=0, **kw)
        self._draw(score)

    def _draw(self, score: float):
        s   = self.SIZE
        pad = 5
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        arc_deg = (score / 100) * 270
        start   = 135

        # Arka plan halkası
        self.create_arc(x0, y0, x1, y1, start=start, extent=270,
                        style="arc", outline=BORDER, width=5)
        # Skor halkası
        col = score_color(score)
        if arc_deg > 0:
            self.create_arc(x0, y0, x1, y1, start=start, extent=arc_deg,
                            style="arc", outline=col, width=5)
        # Merkez metin
        cx, cy = s / 2, s / 2 + 1
        self.create_text(cx, cy, text=f"{score:.0f}",
                         font=("Segoe UI", 11, "bold"), fill=col)


# ═════════════════════════════════════════════════════════════
#  FIRSAT KARTI  (yeniden tasarım)
# ═════════════════════════════════════════════════════════════
class OpportunityCard(ctk.CTkFrame):
    def __init__(self, master, opp, on_select, is_selected=False, **kw):
        super().__init__(master,
                         fg_color=BG_CARD, corner_radius=10,
                         border_width=1,
                         border_color=BORDER_FOCUS if is_selected else BORDER,
                         **kw)
        self.opp         = opp
        self._on_select  = on_select
        self._selected   = is_selected
        self._build()
        self.bind("<Button-1>", self._click)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._click)

    def _click(self, *_):
        self._on_select(self.opp)

    def select(self, val: bool):
        self._selected = val
        self.configure(
            border_color=BORDER_FOCUS if val else BORDER,
            border_width=2 if val else 1,
        )

    def _build(self):
        o   = opp = self.opp
        dec = DECISION_STYLE.get(o.decision, dict(fg=TEXT2, bg=BG_INPUT, icon="—"))
        rs  = RISK_STYLE.get(o.risk_level, dict(fg=TEXT2, bg=BG_INPUT, emoji="●", short="?"))
        ts  = TYPE_STYLE.get(o.asset_type, dict(fg=TEXT2, bg=BG_INPUT, label="?"))

        # ── Satır 1: Sol (sembol + rozetler) / Sağ (skor gauge) ──
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(10, 0))

        left1 = ctk.CTkFrame(row1, fg_color="transparent")
        left1.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(left1, text=o.symbol,
                     font=F_SUB, text_color=TEXT1).pack(anchor="w")

        badge_row = ctk.CTkFrame(left1, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(2, 0))
        Badge(badge_row, ts["label"], ts["fg"], ts["bg"]).pack(side="left", padx=(0, 3))
        Badge(badge_row, f"{rs['emoji']} {o.risk_level.title()}",
              rs["fg"], rs["bg"]).pack(side="left")

        # Skor gauge sağda
        gauge_frame = ctk.CTkFrame(row1, fg_color="transparent")
        gauge_frame.pack(side="right", anchor="ne")
        ScoreGauge(gauge_frame, o.composite_score).pack()
        ctk.CTkLabel(gauge_frame, text="SKOR", font=F_TINY,
                     text_color=TEXT3).pack()

        # ── Satır 2: Varlık adı ──────────────────────────────────
        ctk.CTkLabel(self, text=o.name[:34], font=F_TINY,
                     text_color=TEXT3).pack(anchor="w", padx=10)

        # ── Satır 3: Fiyat + 1G değişim ──────────────────────────
        price_row = ctk.CTkFrame(self, fg_color="transparent")
        price_row.pack(fill="x", padx=10, pady=(6, 0))

        ctk.CTkLabel(price_row, text=fmt_price(o.current_price),
                     font=F_NUM, text_color=TEXT1).pack(side="left")

        if o.return_1d is not None:
            arrow = "▲" if o.return_1d >= 0 else "▼"
            chg_c = pct_color(o.return_1d)
            ctk.CTkLabel(price_row,
                         text=f"  {arrow} {abs(o.return_1d):.2f}%",
                         font=F_SMALL, text_color=chg_c).pack(side="left")

        # ── Satır 4: Getiri tablosu (kompakt) ────────────────────
        ret_grid = ctk.CTkFrame(self, fg_color=BG_INPUT, corner_radius=6)
        ret_grid.pack(fill="x", padx=10, pady=(6, 0))
        periods = [("1H", o.return_1w), ("1A", o.return_1m),
                   ("3A", o.return_3m), ("1Y", o.return_1y)]
        for i, (lbl, val) in enumerate(periods):
            f = ctk.CTkFrame(ret_grid, fg_color="transparent")
            f.pack(side="left", expand=True, padx=0, pady=3)
            ctk.CTkLabel(f, text=lbl, font=F_TINY,
                         text_color=TEXT3).pack()
            if val is not None:
                arrow = "▲" if val >= 0 else "▼"
                ctk.CTkLabel(f, text=f"{arrow}{abs(val):.1f}%",
                             font=("Segoe UI", 9, "bold"),
                             text_color=pct_color(val)).pack()
            else:
                ctk.CTkLabel(f, text="—", font=F_TINY, text_color=TEXT3).pack()
            if i < 3:
                Divider(f, vertical=True).pack(side="right", fill="y", pady=3)

        # ── Satır 5: Karar + fırsat etiketi ──────────────────────
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(6, 10))

        ctk.CTkLabel(bot,
                     text=f" {dec['icon']}  {o.decision} ",
                     font=("Segoe UI", 10, "bold"),
                     fg_color=dec["bg"], corner_radius=5,
                     text_color=dec["fg"]).pack(side="left")

        if o.opportunity_label:
            ctk.CTkLabel(bot, text=o.opportunity_label,
                         font=F_TINY, text_color=TEXT2,
                         ).pack(side="right")

        # ── Conviction + timing satırı ────────────────────────────
        conv_row = ctk.CTkFrame(self, fg_color="transparent")
        conv_row.pack(fill="x", padx=10, pady=(0, 6))

        conv  = getattr(o, "conviction_score", o.composite_score)
        timing = getattr(o, "timing_score", 50.0)
        t_qual = getattr(o, "timing_quality", "orta")
        timing_badge_colors = {
            "iyi":   (BUY_C, GREEN_DIM),
            "orta":  (HOLD_C, GOLD_DIM),
            "zayıf": (SELL_C, RED_DIM),
            "kötü":  (SELL_C, RED_DIM),
        }
        tc, tbg = timing_badge_colors.get(t_qual, (TEXT3, BG_INPUT))

        Badge(conv_row,
              f"🎯 {conv:.0f}",
              score_color(conv), score_bg(conv),
              font=F_TINY).pack(side="left", padx=(0,3))
        Badge(conv_row,
              f"⏰ {t_qual.title()}",
              tc, tbg, font=F_TINY).pack(side="left")

        # ── Güven çubuğu (alt border gibi) ───────────────────────
        pbar = ctk.CTkProgressBar(self, height=3, corner_radius=0)
        pbar.set(o.decision_confidence / 100)
        pbar.configure(progress_color=dec["fg"],
                       fg_color=BORDER)
        pbar.pack(fill="x", padx=0, pady=0, side="bottom")


# ═════════════════════════════════════════════════════════════
#  ÖZET ÇUBUĞU  (sayfanın üstünde)
# ═════════════════════════════════════════════════════════════
class SummaryBar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_CARD,
                         corner_radius=10, border_width=1,
                         border_color=BORDER, **kw)
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        self._stats: dict = {}
        specs = [
            ("total",      "Taranan",    "—",  TEXT2),
            ("strong_buy", "Güçlü AL",   "—",  BUY_C),
            ("buy",        "AL",         "—",  BUY_C),
            ("watch",      "İzle",       "—",  HOLD_C),
            ("sell",       "SAT/Kaçın",  "—",  SELL_C),
            ("avg_score",  "Ort. Skor",  "—",  ACCENT),
            ("top_type",   "Öncü Sınıf", "—",  TEXT1),
            ("scan_time",  "Güncelleme", "—",  TEXT3),
        ]
        for i, (key, label, default, col) in enumerate(specs):
            f = ctk.CTkFrame(inner, fg_color="transparent")
            f.pack(side="left", expand=True)

            val_lbl = ctk.CTkLabel(f, text=default,
                                   font=("Segoe UI", 15, "bold"),
                                   text_color=col)
            val_lbl.pack()
            ctk.CTkLabel(f, text=label, font=F_TINY,
                         text_color=TEXT3).pack()
            self._stats[key] = val_lbl

            if i < len(specs) - 1:
                Divider(inner, vertical=True).pack(side="left", fill="y", padx=8, pady=4)

    def update_stats(self, opps: list):
        if not opps:
            return
        n = len(opps)
        strong_buy = sum(1 for o in opps if o.decision == "GÜÇLÜ AL")
        buy_       = sum(1 for o in opps if o.decision == "AL")
        sell_avoid = sum(1 for o in opps if o.decision in ("SAT", "KAÇIN", "AZALT"))
        avg_sc     = sum(o.composite_score for o in opps) / n

        from collections import Counter
        top_type   = Counter(o.asset_type for o in opps).most_common(1)[0][0]
        type_label = TYPE_STYLE.get(top_type, {}).get("label", top_type.upper())
        scan_time  = datetime.now().strftime("%H:%M")

        updates = {
            "total":      (str(n),          TEXT2),
            "strong_buy": (str(strong_buy), BUY_C),
            "buy":        (str(buy_),       BUY_C),
            "watch":      (str(sum(1 for o in opps if o.decision == "İZLE")), HOLD_C),
            "sell":       (str(sell_avoid), SELL_C),
            "avg_score":  (f"{avg_sc:.0f}", ACCENT),
            "top_type":   (type_label,      TEXT1),
            "scan_time":  (scan_time,       TEXT3),
        }
        for key, (val, col) in updates.items():
            self._stats[key].configure(text=val, text_color=col)


# ═════════════════════════════════════════════════════════════
#  FİLTRE PANELİ  (chip tabanlı)
# ═════════════════════════════════════════════════════════════
class FilterPanel(ctk.CTkFrame):
    def __init__(self, master, on_change, **kw):
        super().__init__(master, fg_color=BG_CARD,
                         corner_radius=10, border_width=1,
                         border_color=BORDER, **kw)
        self._on_change = on_change
        self._type_chips:  dict = {}
        self._risk_chips:  dict = {}
        self._opp_chips:   dict = {}
        self._sort_var     = "skor_desc"
        self._min_score    = 0
        self._search_str   = ""
        self._active_types: set = set()
        self._active_risks: set = set()
        self._active_opps:  set = set()
        self._build()

    def _build(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=12, pady=8)

        # ── Satır 1: Arama + Sıralama + Skor ──────────────────────
        row1 = ctk.CTkFrame(outer, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))

        # Arama kutusu
        self.ent_search = ctk.CTkEntry(
            row1, placeholder_text="🔍  Sembol veya isim ara...",
            width=220, height=32, font=F_SMALL,
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT1)
        self.ent_search.pack(side="left")
        self.ent_search.bind("<KeyRelease>", self._on_search)

        ctk.CTkLabel(row1, text="Sırala:", font=F_SMALL,
                     text_color=TEXT2).pack(side="left", padx=(14, 4))

        sorts = [
            ("skor_desc",    "Skor ↓"),
            ("skor_asc",     "Skor ↑"),
            ("conf_desc",    "Güven ↓"),
            ("ret1d_desc",   "1G ↓"),
            ("ret1m_desc",   "1A ↓"),
            ("ret1y_desc",   "1Y ↓"),
            ("risk_low",     "Risk ↑"),
            ("vol_low",      "Oynaklık ↑"),
        ]
        self._sort_btns = {}
        for key, label in sorts:
            btn = ctk.CTkButton(
                row1, text=label, font=F_TINY, height=28, width=68,
                corner_radius=6,
                fg_color=ACCENT if key == self._sort_var else BG_INPUT,
                hover_color=BG_HOVER,
                text_color="#ffffff" if key == self._sort_var else TEXT2,
                border_width=1, border_color=BORDER,
                command=lambda k=key: self._set_sort(k))
            btn.pack(side="left", padx=2)
            self._sort_btns[key] = btn

        # Min skor
        ctk.CTkLabel(row1, text="Min:", font=F_SMALL,
                     text_color=TEXT2).pack(side="left", padx=(14, 4))
        self.score_slider = ctk.CTkSlider(
            row1, from_=0, to=90, width=90, height=14,
            command=self._on_score)
        self.score_slider.set(0)
        self.score_slider.pack(side="left")
        self.lbl_score = ctk.CTkLabel(row1, text="0", font=F_SMALL,
                                       text_color=ACCENT, width=22)
        self.lbl_score.pack(side="left", padx=(4, 0))

        # Sıfırla
        ctk.CTkButton(row1, text="↺  Sıfırla", font=F_TINY, height=28, width=75,
                      fg_color=BG_INPUT, hover_color=BG_HOVER,
                      text_color=SELL_C, border_width=1, border_color=BORDER,
                      command=self._reset_all
                      ).pack(side="right")

        # Sonuç sayısı
        self.lbl_count = ctk.CTkLabel(row1, text="", font=F_SMALL,
                                       text_color=TEXT2)
        self.lbl_count.pack(side="right", padx=(0, 10))

        Divider(outer).pack(fill="x", pady=(0, 6))

        # ── Satır 2: Varlık Tipi Chipleri ─────────────────────────
        row2 = ctk.CTkFrame(outer, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row2, text="TÜR:", font=("Segoe UI", 9, "bold"),
                     text_color=TEXT3, width=36).pack(side="left")

        type_chips = [
            ("crypto",  "🔵 Kripto"),
            ("stock",   "🟢 ABD Hisse"),
            ("bist",    "🟡 BIST"),
            ("etf",     "🟣 ETF"),
        ]
        for key, label in type_chips:
            chip = FilterChip(row2, label, self._on_type_chip, width=95)
            chip.pack(side="left", padx=3)
            self._type_chips[key] = chip

        # ── Satır 3: Risk Tipi Chipleri ───────────────────────────
        row3 = ctk.CTkFrame(outer, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(row3, text="RİSK:", font=("Segoe UI", 9, "bold"),
                     text_color=TEXT3, width=36).pack(side="left")

        risk_chips = [
            ("çok düşük",   "🟢 Çok Düşük"),
            ("düşük",       "🔵 Düşük"),
            ("orta",        "🟡 Orta"),
            ("orta-yüksek", "🟠 Orta-Yüksek"),
            ("yüksek",      "🔴 Yüksek"),
            ("spekülatif",  "💀 Spekülatif"),
        ]
        for key, label in risk_chips:
            chip = FilterChip(row3, label, self._on_risk_chip, width=108)
            chip.pack(side="left", padx=3)
            self._risk_chips[key] = chip

        # ── Satır 4: Fırsat Tipi Chipleri ────────────────────────
        row4 = ctk.CTkFrame(outer, fg_color="transparent")
        row4.pack(fill="x", pady=(0, 0))
        ctk.CTkLabel(row4, text="TİP:", font=("Segoe UI", 9, "bold"),
                     text_color=TEXT3, width=36).pack(side="left")

        opp_chips = [
            ("momentum",    "⚡ Momentum"),
            ("buyume",      "🚀 Büyüme"),
            ("deger",       "💎 Değer"),
            ("savunmaci",   "🛡️ Savunmacı"),
            ("yuksek_risk", "🎯 Yüksek R/Ö"),
            ("birikim",     "📈 Birikim"),
            ("izleme",      "👁 İzleme"),
        ]
        for key, label in opp_chips:
            chip = FilterChip(row4, label, self._on_opp_chip, width=105)
            chip.pack(side="left", padx=3)
            self._opp_chips[key] = chip

    # ── Chip callback'leri ────────────────────────────────────
    def _on_type_chip(self, label, active):
        key = {v: k for k, v in
               {c._text: k for k, c in self._type_chips.items()}.items()
               }.get(label)
        # Doğrudan key bul
        for k, c in self._type_chips.items():
            if c._text == label:
                if active: self._active_types.add(k)
                else:       self._active_types.discard(k)
        self._on_change()

    def _on_risk_chip(self, label, active):
        for k, c in self._risk_chips.items():
            if c._text == label:
                if active: self._active_risks.add(k)
                else:       self._active_risks.discard(k)
        self._on_change()

    def _on_opp_chip(self, label, active):
        for k, c in self._opp_chips.items():
            if c._text == label:
                if active: self._active_opps.add(k)
                else:       self._active_opps.discard(k)
        self._on_change()

    def _set_sort(self, key):
        self._sort_var = key
        for k, btn in self._sort_btns.items():
            btn.configure(
                fg_color=ACCENT if k == key else BG_INPUT,
                text_color="#ffffff" if k == key else TEXT2)
        self._on_change()

    def _on_score(self, val):
        self._min_score = float(val)
        self.lbl_score.configure(text=f"{int(val)}")
        self._on_change()

    def _on_search(self, *_):
        self._search_str = self.ent_search.get().strip().upper()
        self._on_change()

    def _reset_all(self):
        self._active_types.clear()
        self._active_risks.clear()
        self._active_opps.clear()
        self._min_score  = 0
        self._search_str = ""
        self._sort_var   = "skor_desc"
        self.score_slider.set(0)
        self.lbl_score.configure(text="0")
        self.ent_search.delete(0, "end")
        for chip in list(self._type_chips.values()) + \
                    list(self._risk_chips.values()) + \
                    list(self._opp_chips.values()):
            chip.set_active(False)
        for k, btn in self._sort_btns.items():
            btn.configure(
                fg_color=ACCENT if k == "skor_desc" else BG_INPUT,
                text_color="#ffffff" if k == "skor_desc" else TEXT2)
        self._sort_var = "skor_desc"
        self._on_change()

    def set_count(self, n: int, total: int):
        self.lbl_count.configure(
            text=f"{n} / {total} sonuç" if n != total else f"{n} sonuç")

    def get_filters(self) -> dict:
        return dict(
            types=self._active_types,
            risks=self._active_risks,
            opps=self._active_opps,
            min_score=self._min_score,
            search=self._search_str,
            sort=self._sort_var,
        )


# ═════════════════════════════════════════════════════════════
#  DETAY PANELİ — SEKMELİ
# ═════════════════════════════════════════════════════════════
class DetailPanel(ctk.CTkFrame):
    TABS = [
        ("overview",   "📋 Genel"),
        ("conviction", "🎯 Karar"),
        ("technical",  "📊 Teknik"),
        ("reasoning",  "🧠 Gerekçe"),
        ("trade_plan", "💼 İşlem"),
        ("education",  "💡 Eğitim"),
    ]

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_CARD,
                         corner_radius=10, border_width=1,
                         border_color=BORDER, **kw)
        self._opp       = None
        self._active_tab = "overview"
        self._tab_btns  = {}
        self._content   = None
        self._build_skeleton()

    # ── Boş durum ─────────────────────────────────────────────
    def _build_skeleton(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(frame, text="💎", font=("Segoe UI", 40)).pack()
        ctk.CTkLabel(frame, text="Bir fırsat seçin",
                     font=F_HEAD, text_color=TEXT1).pack(pady=(8, 4))
        ctk.CTkLabel(frame, text="Sol taraftaki listeden bir fırsata\n"
                                  "tıklayarak detaylı analizi görün.",
                     font=F_BODY, text_color=TEXT2, justify="center").pack()
        self._placeholder = frame

    # ── Sekme bar ──────────────────────────────────────────────
    def _build_tab_bar(self):
        tab_bar = ctk.CTkFrame(self, fg_color=BG_INPUT,
                               corner_radius=4, height=40)
        tab_bar.pack(fill="x", padx=0, pady=0)
        tab_bar.pack_propagate(False)
        self._tab_btns = {}
        for key, label in self.TABS:
            btn = ctk.CTkButton(
                tab_bar, text=label, font=F_TINY, height=38,
                corner_radius=0,
                fg_color=BG_CARD if key == self._active_tab else "transparent",
                hover_color=BG_HOVER,
                text_color=ACCENT if key == self._active_tab else TEXT2,
                border_width=0,
                command=lambda k=key: self._switch_tab(k))
            btn.pack(side="left", padx=0)
            self._tab_btns[key] = btn
        return tab_bar

    def _switch_tab(self, key):
        self._active_tab = key
        for k, btn in self._tab_btns.items():
            btn.configure(
                fg_color=BG_CARD if k == key else "transparent",
                text_color=ACCENT if k == key else TEXT2)
        self._render_tab()

    # ── Ana show fonksiyonu ────────────────────────────────────
    def show(self, opp):
        self._opp = opp
        self._active_tab = "overview"

        # Placeholder'ı kaldır
        if self._placeholder and self._placeholder.winfo_exists():
            self._placeholder.place_forget()

        # Tüm mevcut widget'ları temizle (ilk gösterimde veya sıfırlamada)
        for w in self.winfo_children():
            w.destroy()
        self._tab_btns = {}
        self._content  = None

        # Başlık şeridi
        self._build_header()
        # Sekme bar
        self._build_tab_bar()
        # İçerik frame — bir kez oluştur, tab geçişlerinde sadece içini temizle
        self._content = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=4)
        self._content.pack(fill="both", expand=True)
        self._render_tab()

    def _build_header(self):
        o  = self._opp
        dec = DECISION_STYLE.get(o.decision, dict(fg=TEXT2, bg=BG_INPUT, icon="—"))
        ts  = TYPE_STYLE.get(o.asset_type, dict(fg=TEXT2, bg=BG_INPUT, label="?"))
        rs  = RISK_STYLE.get(o.risk_level, dict(fg=TEXT2, bg=BG_INPUT, emoji="●"))

        hdr = ctk.CTkFrame(self, fg_color=score_bg(o.composite_score),
                           corner_radius=4, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.place(x=12, y=8)

        sym_row = ctk.CTkFrame(left, fg_color="transparent")
        sym_row.pack(anchor="w")
        ctk.CTkLabel(sym_row, text=o.symbol,
                     font=("Segoe UI", 18, "bold"),
                     text_color=TEXT1).pack(side="left")
        Badge(sym_row, ts["label"], ts["fg"], ts["bg"],
              font=("Segoe UI", 9)).pack(side="left", padx=6)

        ctk.CTkLabel(left, text=o.name[:40], font=F_SMALL,
                     text_color=TEXT2).pack(anchor="w")

        badges_row = ctk.CTkFrame(left, fg_color="transparent")
        badges_row.pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(badges_row,
                     text=f" {dec['icon']}  {o.decision}  —  {o.decision_confidence:.0f}% güven ",
                     font=("Segoe UI", 10, "bold"),
                     fg_color=dec["bg"], corner_radius=4,
                     text_color=dec["fg"]).pack(side="left")
        ctk.CTkLabel(badges_row,
                     text=f"  {rs['emoji']} {o.risk_level.title()}  ",
                     font=F_TINY,
                     fg_color=rs["bg"], corner_radius=4,
                     text_color=rs["fg"]).pack(side="left", padx=6)

        # Skor sağda
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.place(relx=1, x=-12, y=8, anchor="ne")
        ScoreGauge(right, o.composite_score).pack()
        ctk.CTkLabel(right, text="Kompozit Skor",
                     font=F_TINY, text_color=TEXT3).pack()

    # ── Sekme içerikleri ───────────────────────────────────────
    def _render_tab(self):
        if not self._content:
            return
        for w in self._content.winfo_children():
            w.destroy()

        dispatch = {
            "overview":   self._tab_overview,
            "conviction": self._tab_conviction,
            "technical":  self._tab_technical,
            "reasoning":  self._tab_reasoning,
            "trade_plan": self._tab_trade_plan,
            "education":  self._tab_education,
        }
        dispatch.get(self._active_tab, self._tab_overview)()

    # ── Yardımcı widget builder'lar ────────────────────────────
    def _sec(self, title):
        ctk.CTkLabel(self._content, text=title,
                     font=("Segoe UI", 11, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=14, pady=(12, 2))
        Divider(self._content).pack(fill="x", padx=14)

    def _row(self, label, value, val_color=TEXT1, bold=False):
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=1)
        lbl_w = ctk.CTkLabel(f, text=label, font=F_SMALL,
                             text_color=TEXT2, width=130, anchor="w")
        lbl_w.pack(side="left")
        _tip_fn(lbl_w, label)
        ctk.CTkLabel(f, text=str(value),
                     font=("Segoe UI", 10, "bold") if bold else F_SMALL,
                     text_color=val_color).pack(side="right")

    def _text_block(self, text, color=TEXT2, wrap=270):
        ctk.CTkLabel(self._content, text=text, font=F_SMALL,
                     text_color=color, wraplength=wrap,
                     anchor="w", justify="left"
                     ).pack(anchor="w", padx=14, pady=(2, 4))

    def _bullet(self, items, color=TEXT2):
        for item in items:
            f = ctk.CTkFrame(self._content, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=1)
            ctk.CTkLabel(f, text="•", font=F_SMALL,
                         text_color=color, width=12).pack(side="left")
            ctk.CTkLabel(f, text=item, font=F_SMALL,
                         text_color=TEXT1, wraplength=250,
                         anchor="w", justify="left"
                         ).pack(side="left", fill="x", expand=True)

    def _score_bar(self, label, score, max_score=40):
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.pack(fill="x", padx=14, pady=2)
        lbl_w = ctk.CTkLabel(f, text=label, font=F_SMALL,
                             text_color=TEXT2, width=130, anchor="w")
        lbl_w.pack(side="left")
        _tip_fn(lbl_w, label.lstrip("🔍⏰⚖️📦👤💰 "))
        ctk.CTkLabel(f, text=f"{score:+.0f}",
                     font=("Segoe UI", 10, "bold"),
                     text_color=BUY_C if score >= 0 else SELL_C,
                     width=36).pack(side="right")
        bar = ctk.CTkProgressBar(f, height=6, corner_radius=3, width=100)
        val = max(0, min(1, (score + max_score) / (2 * max_score)))
        bar.set(val)
        bar.configure(progress_color=BUY_C if score >= 0 else SELL_C)
        bar.pack(side="right", padx=4)

    def _info_card(self, title, text, bg="#fffbdd", title_color="#9a6700"):
        card = ctk.CTkFrame(self._content, fg_color=bg,
                             corner_radius=8, border_width=1,
                             border_color=BORDER)
        card.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(card, text=title,
                     font=("Segoe UI", 10, "bold"),
                     text_color=title_color).pack(anchor="w", padx=12, pady=(6, 2))
        ctk.CTkLabel(card, text=text, font=F_SMALL,
                     text_color=TEXT1, wraplength=255,
                     anchor="w", justify="left"
                     ).pack(anchor="w", padx=12, pady=(0, 8))

    # ── SEKME 1: Genel Bakış ──────────────────────────────────
    def _tab_overview(self):
        o = self._opp
        self._sec("Fiyat & Performans")
        self._row("Güncel Fiyat", fmt_price(o.current_price), TEXT1, bold=True)
        for lbl, val in [("1 Gün", o.return_1d), ("1 Hafta", o.return_1w),
                          ("1 Ay", o.return_1m), ("3 Ay", o.return_3m),
                          ("6 Ay", o.return_6m), ("1 Yıl", o.return_1y)]:
            if val is not None:
                self._row(lbl, fmt_pct(val), pct_color(val),
                          bold=abs(val or 0) > 15)

        self._sec("Risk Profili")
        self._row("Risk Seviyesi",
                  f"{RISK_STYLE.get(o.risk_level,{}).get('emoji','?')} {o.risk_level.title()}",
                  RISK_STYLE.get(o.risk_level, {}).get("fg", TEXT2), bold=True)
        if o.volatility:
            self._row("Yıllık Volatilite", f"%{o.volatility:.1f}",
                      SELL_C if o.volatility > 40 else HOLD_C if o.volatility > 20 else BUY_C)
        if o.sharpe:
            self._row("Sharpe Oranı", f"{o.sharpe:.2f}",
                      BUY_C if o.sharpe > 1 else SELL_C if o.sharpe < 0 else TEXT1)
        if o.max_drawdown:
            self._row("Max Drawdown", f"%{o.max_drawdown:.1f}", SELL_C)

        self._sec("Fırsat Profili")
        self._row("Fırsat Tipi", o.opportunity_label or "—", ACCENT)
        self._row("Karar", o.decision,
                  DECISION_STYLE.get(o.decision, {}).get("fg", TEXT2), bold=True)
        self._row("Güven", f"%{o.decision_confidence:.0f}", ACCENT)
        self._row("Vade", o.time_horizon.title())
        self._row("Uygun Varlık Sınıfı",
                  TYPE_STYLE.get(o.asset_type, {}).get("label", "?"),
                  TYPE_STYLE.get(o.asset_type, {}).get("fg", TEXT2))
        if o.suitable_for:
            self._row("Kime Uygun?", " | ".join(o.suitable_for[:2]), TEXT2)

    # ── SEKME: Karar / Conviction (YENİ) ─────────────────────
    def _tab_conviction(self):
        o = self._opp

        # ── Conviction + Timing yan yana ─────────────────────
        self._sec("Karar Güveni & Zamanlama")

        conv  = getattr(o, "conviction_score", 50.0)
        timing = getattr(o, "timing_score", 50.0)
        t_qual = getattr(o, "timing_quality", "orta")
        alloc_conf = getattr(o, "allocation_confidence", 50.0)

        # Conviction bar
        conv_c = score_color(conv)
        self._score_bar("🎯 Conviction Skoru", conv, 100)

        # Timing bar
        timing_c = BUY_C if timing >= 65 else HOLD_C if timing >= 45 else SELL_C
        t_label_map = {"iyi": "✅ İyi", "orta": "⚠️ Orta", "zayıf": "⚠️ Zayıf", "kötü": "🔴 Kötü"}
        self._row("⏰ Zamanlama", f"{timing:.0f}/100  —  {t_label_map.get(t_qual, t_qual)}",
                  timing_c, bold=True)
        self._score_bar("Zamanlama Skoru", timing, 100)
        self._row("📊 Tahsis Güveni", f"%{alloc_conf:.0f}", score_color(alloc_conf))

        # Timing uyarısı
        t_warn = getattr(o, "timing_warning", "")
        if t_warn:
            self._info_card("", t_warn,
                            bg=RED_DIM if timing < 45 else GOLD_DIM,
                            title_color=SELL_C if timing < 45 else HOLD_C)

        # ── 6 Boyutlu Değerlendirme ──────────────────────────
        self._sec("6 Boyutlu Analiz")
        dims = [
            ("🔍 Fırsat Kalitesi",      getattr(o, "dim_opportunity_quality", 50)),
            ("⏰ Zamanlama Kalitesi",    getattr(o, "dim_timing_quality", 50)),
            ("⚖️ Risk/Ödül Oranı",      getattr(o, "dim_risk_reward", 50)),
            ("📦 Portföy Uyumu",         getattr(o, "dim_portfolio_fit", 50)),
            ("👤 Profile Uygunluk",      getattr(o, "dim_profile_fit", 50)),
            ("💰 Alternatif Maliyet",    getattr(o, "dim_alternative_cost", 50)),
        ]
        for label, val in dims:
            self._score_bar(label, val, 100)

        alt_note = getattr(o, "alternative_cost_note", "")
        if alt_note:
            self._row("Alternatif Not", alt_note, TEXT2)

        # ── Katalizör Haritası ───────────────────────────────
        catalyst_map = getattr(o, "catalyst_map", [])
        if catalyst_map:
            self._sec("Katalizör Haritası")
            prob_colors = {"yüksek": BUY_C, "orta": HOLD_C, "düşük": TEXT2}
            impact_bg   = {"yüksek": GREEN_DIM, "orta": GOLD_DIM, "düşük": BG_INPUT}
            for cat in catalyst_map[:4]:
                f = ctk.CTkFrame(self._content, fg_color=BG_INPUT, corner_radius=6)
                f.pack(fill="x", padx=14, pady=2)

                top = ctk.CTkFrame(f, fg_color="transparent")
                top.pack(fill="x", padx=8, pady=(6, 2))
                ctk.CTkLabel(top, text=cat.get("catalyst","?"),
                             font=F_SMALL, text_color=TEXT1,
                             wraplength=230, anchor="w", justify="left").pack(side="left", fill="x", expand=True)

                prob = cat.get("probability","orta")
                impact = cat.get("impact","orta")
                bot = ctk.CTkFrame(f, fg_color="transparent")
                bot.pack(fill="x", padx=8, pady=(0,6))
                Badge(bot, f"Olasılık: {prob}", prob_colors.get(prob, TEXT2),
                      impact_bg.get(prob, BG_INPUT), font=F_TINY).pack(side="left", padx=(0,4))
                Badge(bot, f"Etki: {impact}", prob_colors.get(impact, TEXT2),
                      impact_bg.get(impact, BG_INPUT), font=F_TINY).pack(side="left", padx=(0,4))
                tf = cat.get("timeframe","")
                if tf:
                    Badge(bot, f"⏱ {tf}", TEXT3, BG_INPUT, font=F_TINY).pack(side="left")

        # ── Senaryo Ağacı ────────────────────────────────────
        bull = getattr(o, "scenario_bull", {})
        base = getattr(o, "scenario_base", {})
        bear = getattr(o, "scenario_bear", {})

        if bull or base or bear:
            self._sec("Senaryo Ağacı")
            scenario_data = [
                ("📈 Boğa", bull, BUY_C, GREEN_DIM),
                ("📊 Baz",  base, ACCENT, ACCENT_DIM),
                ("📉 Ayı",  bear, SELL_C, RED_DIM),
            ]
            for label, sc, col, bg in scenario_data:
                if not sc:
                    continue
                prob   = sc.get("probability_pct", 0)
                ret    = sc.get("return_pct", 0)
                trig   = sc.get("trigger", "")
                notes  = sc.get("notes", "")

                card = ctk.CTkFrame(self._content, fg_color=bg, corner_radius=8)
                card.pack(fill="x", padx=14, pady=3)

                hdr = ctk.CTkFrame(card, fg_color="transparent")
                hdr.pack(fill="x", padx=10, pady=(8,2))
                ctk.CTkLabel(hdr, text=label, font=("Segoe UI",10,"bold"),
                             text_color=col).pack(side="left")
                ret_sign = "+" if ret >= 0 else ""
                ctk.CTkLabel(hdr, text=f"{ret_sign}{ret:.1f}%",
                             font=("Segoe UI",11,"bold"), text_color=col).pack(side="right")
                ctk.CTkLabel(hdr, text=f"Olasılık: %{prob}",
                             font=F_TINY, text_color=TEXT3).pack(side="right", padx=8)

                # Probability bar
                pbar = ctk.CTkProgressBar(card, height=4, corner_radius=2)
                pbar.set(prob / 100)
                pbar.configure(fg_color=BORDER, progress_color=col)
                pbar.pack(fill="x", padx=10, pady=(2,4))

                if trig:
                    ctk.CTkLabel(card, text=f"Tetikleyici: {trig}",
                                 font=F_TINY, text_color=TEXT2,
                                 wraplength=260, anchor="w", justify="left").pack(anchor="w", padx=10, pady=(0,2))
                if notes:
                    ctk.CTkLabel(card, text=notes, font=F_TINY, text_color=TEXT3,
                                 wraplength=260, anchor="w", justify="left").pack(anchor="w", padx=10, pady=(0,8))

        # ── İnvalidasyon Olayları ─────────────────────────────
        inv_events = getattr(o, "invalidation_events", [])
        if inv_events:
            self._sec("İnvalidasyon Olayları")
            for ev in inv_events[:3]:
                f = ctk.CTkFrame(self._content, fg_color=RED_DIM, corner_radius=6)
                f.pack(fill="x", padx=14, pady=2)
                ctk.CTkLabel(f, text=f"🚫  {ev.get('event','?')}",
                             font=F_SMALL, text_color=SELL_C,
                             wraplength=250, anchor="w", justify="left").pack(anchor="w", padx=8, pady=(6,2))
                act = ev.get("action","")
                if act:
                    ctk.CTkLabel(f, text=f"→ {act}", font=F_TINY, text_color=TEXT2,
                                 anchor="w").pack(anchor="w", padx=8, pady=(0,6))

    # ── SEKME 2: Teknik Analiz ────────────────────────────────
    def _tab_technical(self):
        o = self._opp
        self._sec("Skor Bileşenleri")
        self._score_bar("Teknik Skor",  getattr(o, "tech_score", 0), 40)
        self._score_bar("Momentum",      getattr(o, "momentum_score", 0), 30)
        self._score_bar("Risk Ayarlı",   getattr(o, "risk_score", 0), 20)
        self._score_bar("Kalite",        getattr(o, "quality_score", 10), 10)

        cbox = ctk.CTkFrame(self._content, fg_color=BG_INPUT, corner_radius=8)
        cbox.pack(fill="x", padx=14, pady=(6, 0))
        total_score = getattr(o, "composite_score", 50)
        ctk.CTkLabel(cbox,
                     text=f"Kompozit Skor: {total_score:.0f} / 100",
                     font=("Segoe UI", 12, "bold"),
                     text_color=score_color(total_score)
                     ).pack(padx=12, pady=8)

        self._sec("İndikatörler")
        if o.rsi is not None:
            rsi_c = BUY_C if o.rsi < 35 else SELL_C if o.rsi > 65 else TEXT1
            note  = "Aşırı Satım 🟢" if o.rsi < 30 else \
                    "Aşırı Alım 🔴" if o.rsi > 70 else "Nötr"
            self._row("RSI (14)", f"{o.rsi:.1f}  —  {note}", rsi_c, bold=True)

        if o.trend:
            trend_c = BUY_C if "UP" in o.trend.upper() else \
                      SELL_C if "DOWN" in o.trend.upper() else TEXT1
            self._row("Trend",    o.trend, trend_c)

        if o.macd_signal:
            macd_c = BUY_C if "bull" in o.macd_signal.lower() else \
                     SELL_C if "bear" in o.macd_signal.lower() else TEXT1
            self._row("MACD Sinyal", o.macd_signal.title(), macd_c)

        if o.bb_position is not None:
            bb_c = BUY_C if o.bb_position < 0.25 else \
                   SELL_C if o.bb_position > 0.75 else TEXT1
            self._row("BB Pozisyon",
                      f"%{o.bb_position * 100:.0f}  "
                      f"({'Aşırı Satım' if o.bb_position < 0.25 else 'Aşırı Alım' if o.bb_position > 0.75 else 'Orta Bölge'})",
                      bb_c)

        if o.volume_signal:
            self._row("Hacim Sinyali", o.volume_signal,
                      BUY_C if "high" in o.volume_signal.lower() else TEXT2)

        self._row("Kırılım Tespiti",
                  "✔  Kırılım Mevcut" if o.breakout else "✗  Yok",
                  BUY_C if o.breakout else TEXT3)

    # ── SEKME 3: Gerekçe ──────────────────────────────────────
    def _tab_reasoning(self):
        o = self._opp
        if o.why_buy:
            self._sec("Bullish Senaryosu — Neden Alınmalı?")
            self._bullet(o.why_buy, BUY_C)

        if o.why_not_buy:
            self._sec("Bearish Senaryosu — Neden Alınmamalı?")
            self._bullet(o.why_not_buy, SELL_C)

        if o.catalysts:
            self._sec("Potansiyel Katalizörler")
            self._bullet(o.catalysts, ACCENT)

        if o.risks:
            self._sec("Temel Riskler")
            self._bullet(o.risks, HOLD_C)

        if o.invalidation:
            self._info_card(
                "🔄  Geçersizleşme Koşulu",
                o.invalidation,
                bg=RED_DIM, title_color=SELL_C)

        if o.alternative_scenario:
            self._info_card(
                "📐  Alternatif Senaryo",
                o.alternative_scenario,
                bg=GOLD_DIM, title_color=HOLD_C)

    # ── SEKME 4: İşlem Planı ──────────────────────────────────
    def _tab_trade_plan(self):
        o = self._opp
        self._sec("Giriş Seviyeleri")
        self._row("Güncel Fiyat",   fmt_price(o.current_price), TEXT1, bold=True)
        self._row("Giriş Alt Sınır", fmt_price(o.entry_zone_low), ACCENT)
        self._row("Giriş Üst Sınır", fmt_price(o.entry_zone_high), ACCENT)

        self._sec("Risk Yönetimi")
        self._row("Stop-Loss",  fmt_price(o.stop_loss), SELL_C, bold=True)
        if o.stop_loss and o.current_price:
            sl_pct = (o.stop_loss - o.current_price) / o.current_price * 100
            self._row("Stop Uzaklığı", f"{sl_pct:.1f}%", SELL_C)

        self._sec("Kâr Alma Hedefleri")
        for i, (target, label) in enumerate([(o.target_1, "Hedef 1 (Kısa)"),
                                              (o.target_2, "Hedef 2 (Orta)"),
                                              (o.target_3, "Hedef 3 (İdeal)")], 1):
            if target and o.current_price:
                gain_pct = (target - o.current_price) / o.current_price * 100
                self._row(label,
                          f"{fmt_price(target)}  (+{gain_pct:.0f}%)",
                          BUY_C, bold=True)

        # R:R hesaplama
        if o.stop_loss and o.target_1 and o.current_price:
            risk   = abs(o.current_price - o.stop_loss)
            reward = abs(o.target_1      - o.current_price)
            if risk > 0:
                rr = reward / risk
                self._info_card(
                    "⚖️  Risk / Ödül Oranı (Hedef 1)",
                    f"1 : {rr:.1f}  —  "
                    f"{'Mükemmel ✅' if rr >= 3 else 'İyi ✅' if rr >= 2 else 'Kabul edilebilir 🟡' if rr >= 1.5 else 'Zayıf ❌'}",
                    bg=GREEN_DIM if rr >= 2 else GOLD_DIM if rr >= 1.5 else RED_DIM,
                    title_color=BUY_C if rr >= 2 else HOLD_C if rr >= 1.5 else SELL_C)

        self._sec("Kademeli Alım Önerisi")
        price = o.current_price or 1
        thirds = [price * 1.00, price * 0.97, price * 0.94]
        labels = ["1. Dilim — şimdi", "2. Dilim — %3 düşüşte", "3. Dilim — %6 düşüşte"]
        for lbl, target_p in zip(labels, thirds):
            self._row(lbl, fmt_price(target_p), ACCENT)

        if o.time_horizon:
            self._info_card(
                f"⏱  Beklenen Vade: {o.time_horizon.title()}",
                {"kısa": "Günler–haftalar arasında sonuç bekleniyor. Sıkı stop-loss şart.",
                 "orta": "1–6 ay zaman ufku. Volatiliteye karşı esnek olun.",
                 "uzun": "6 ay ve üzeri. DCA ve sabır en güçlü strateji."
                 }.get(o.time_horizon.lower(),
                       "Pozisyon büyüklüğünü risk seviyenize göre belirleyin."),
                bg=ACCENT_DIM, title_color=ACCENT)

    # ── SEKME 5: Eğitim ───────────────────────────────────────
    def _tab_education(self):
        o = self._opp
        # Eğitim notu
        if o.education_note:
            self._info_card("💡 Bu Fırsata Özel Not", o.education_note,
                            bg="#fffbdd", title_color=HOLD_C)

        # Fırsat tipi açıklaması
        try:
            from src.education_engine import get_opportunity_education
            opp_note = get_opportunity_education(o.opportunity_type or "")
            if opp_note:
                self._info_card(f"📚 {o.opportunity_label or 'Fırsat Tipi'} Nedir?",
                                opp_note, bg=ACCENT_DIM, title_color=ACCENT)
        except Exception:
            pass

        # RSI notu
        if o.rsi is not None:
            try:
                from src.education_engine import get_education_note
                ctx = "rsi_oversold" if o.rsi < 35 else \
                      "rsi_overbought" if o.rsi > 65 else None
                if ctx:
                    note = get_education_note(ctx, rsi=o.rsi)
                    if note:
                        self._info_card("📖 RSI Yorumu", note,
                                        bg=GREEN_DIM if o.rsi < 35 else RED_DIM,
                                        title_color=BUY_C if o.rsi < 35 else SELL_C)
            except Exception:
                pass

        # Volatilite notu
        if o.volatility and o.volatility > 30:
            try:
                from src.education_engine import get_education_note
                note = get_education_note("high_volatility",
                                          vol=o.volatility, max_pos=10)
                if note:
                    self._info_card("⚠️ Volatilite Uyarısı", note,
                                    bg=RED_DIM, title_color=SELL_C)
            except Exception:
                pass

        # Varlık tipi spesifik
        try:
            from src.education_engine import get_education_note
            ctx_map = {"crypto": "crypto_specific", "bist": "bist_specific", "etf": "etf_advantage"}
            ctx = ctx_map.get(o.asset_type)
            if ctx:
                note = get_education_note(ctx)
                if note:
                    label = {"crypto": "🔵 Kripto Dinamikleri",
                             "bist": "🇹🇷 BIST Özellikleri",
                             "etf": "📦 ETF Avantajı"}.get(o.asset_type, "Bilgi")
                    self._info_card(label, note, bg=ACCENT_DIM, title_color=ACCENT)
        except Exception:
            pass

        # Temel kavramlar
        self._sec("Temel Kavramlar")
        try:
            from src.education_engine import get_concept_explanation
            concepts = ["sharpe_ratio", "max_drawdown", "stop_loss"]
            for concept in concepts:
                data = get_concept_explanation(concept)
                if data:
                    card = ctk.CTkFrame(self._content, fg_color=BG_INPUT,
                                        corner_radius=8, border_width=1,
                                        border_color=BORDER)
                    card.pack(fill="x", padx=14, pady=4)
                    ctk.CTkLabel(card, text=data.get("title", ""),
                                 font=("Segoe UI", 10, "bold"),
                                 text_color=TEXT1).pack(anchor="w", padx=10, pady=(6, 2))
                    ctk.CTkLabel(card, text=data.get("explanation", ""),
                                 font=F_TINY, text_color=TEXT2,
                                 wraplength=255, anchor="w", justify="left"
                                 ).pack(anchor="w", padx=10)
                    ctk.CTkLabel(card, text=f"💡  {data.get('tip', '')}",
                                 font=("Segoe UI", 9, "bold"), text_color=ACCENT,
                                 wraplength=255, anchor="w", justify="left"
                                 ).pack(anchor="w", padx=10, pady=(2, 8))
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════
#  SIRALA BAŞLIĞI (liste üstünde)
# ═════════════════════════════════════════════════════════════
class ListHeader(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_INPUT, corner_radius=6,
                         height=28, **kw)
        self.pack_propagate(False)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", padx=8, pady=4)
        for text, anchor, expand in [
            ("Sembol / Varlık",       "w", True),
            ("Skor",                  "center", False),
            ("Karar",                 "center", False),
            ("1H%  1A%  3A%  1Y%",   "e",      False),
        ]:
            ctk.CTkLabel(inner, text=text, font=F_TINY,
                         text_color=TEXT3, anchor=anchor
                         ).pack(side="left", expand=expand, fill="x", padx=4)


# ═════════════════════════════════════════════════════════════
#  ANA SAYFA
# ═════════════════════════════════════════════════════════════
class OpportunitiesPage(ctk.CTkFrame):
    def __init__(self, master, result_q=None, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._result_q         = result_q
        self._all_opps: list   = []
        self._filtered: list   = []
        self._selected_symbol  = None
        self._loading          = False
        self._cards: dict      = {}
        self._build()

    # ─────────────────────────────────────────────────────────
    def _build(self):
        # ── Başlık + Tarama Butonu ────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 10))

        title_col = ctk.CTkFrame(hdr, fg_color="transparent")
        title_col.pack(side="left")
        ctk.CTkLabel(title_col, text="💎  Yatırım Fırsatları",
                     font=F_TITLE, text_color=TEXT1).pack(anchor="w")
        self.lbl_subtitle = ctk.CTkLabel(
            title_col,
            text="Tarama yapmak için butona tıklayın — tüm piyasalar analiz edilecek.",
            font=F_SMALL, text_color=TEXT2)
        self.lbl_subtitle.pack(anchor="w")

        btn_col = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_col.pack(side="right")
        self.btn_scan = ctk.CTkButton(
            btn_col,
            text="🔍  Piyasayı Tara",
            font=("Segoe UI", 12, "bold"),
            width=160, height=40, corner_radius=8,
            fg_color=ACCENT, hover_color="#0860ca",
            command=self._start_scan)
        self.btn_scan.pack()
        self.lbl_scan_time = ctk.CTkLabel(
            btn_col, text="", font=F_TINY, text_color=TEXT3)
        self.lbl_scan_time.pack(pady=(2, 0))

        # Progress bar
        self.pbar = ctk.CTkProgressBar(self, height=2, corner_radius=0)
        self.pbar.set(0)
        self.pbar.configure(fg_color=BORDER, progress_color=ACCENT)
        self.pbar.pack(fill="x")

        # Özet çubuğu
        self.summary_bar = SummaryBar(self)
        self.summary_bar.pack(fill="x", padx=20, pady=(10, 6))

        # Filtre paneli
        self.filter_panel = FilterPanel(self, on_change=self._apply_filters)
        self.filter_panel.pack(fill="x", padx=20, pady=(0, 8))

        # ── İki Kolon: Liste (sol) + Detay (sağ) ─────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        body.columnconfigure(0, weight=4)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # Sol: liste
        list_col = ctk.CTkFrame(body, fg_color="transparent")
        list_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        list_col.rowconfigure(1, weight=1)
        list_col.columnconfigure(0, weight=1)

        self.card_scroll = ctk.CTkScrollableFrame(
            list_col, fg_color="transparent", corner_radius=4)
        self.card_scroll.grid(row=1, column=0, sticky="nsew")
        self.card_scroll.columnconfigure(0, weight=1)
        self.card_scroll.columnconfigure(1, weight=1)

        # Boş durum
        self.lbl_empty = ctk.CTkLabel(
            self.card_scroll,
            text="🔍  Piyasayı Tara butonuna bas\n\n"
                 "Kripto · ABD Hisseleri · BIST · ETF\n"
                 "80+ varlık otomatik analiz edilir.\n\n"
                 "⚡ Paralel tarama — yaklaşık 20–40 saniye",
            font=F_BODY, text_color=TEXT2, justify="center")
        self.lbl_empty.grid(row=0, column=0, columnspan=2, pady=60)

        # Sağ: detay paneli
        self.detail = DetailPanel(body)
        self.detail.grid(row=0, column=1, sticky="nsew")

    # ─────────────────────────────────────────────────────────
    #  TARAMA
    # ─────────────────────────────────────────────────────────
    def _start_scan(self):
        if self._loading:
            return
        self._loading = True
        self.btn_scan.configure(state="disabled", text="⏳  Taranıyor...")
        self.lbl_subtitle.configure(
            text="Tüm piyasalar analiz ediliyor... Bu işlem 30-60 saniye sürebilir.")
        self.pbar.configure(mode="indeterminate")
        self.pbar.start()
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            from src.opportunity_engine import scan_asset_type
            all_results = []
            asset_types = [
                ("crypto",       "🔷 Kripto"),
                ("us_stocks",    "🇺🇸 ABD Hisseleri"),
                ("bist",         "🇹🇷 BIST"),
                ("priority_etfs","📦 ETF'ler"),
            ]
            total = len(asset_types)
            for i, (at, label) in enumerate(asset_types):
                self.after(0, lambda l=label, i=i, t=total:
                    self.lbl_subtitle.configure(
                        text=f"Taranıyor: {l}  ({i+1}/{t})"))
                try:
                    results = scan_asset_type(at, force_refresh=False)
                    all_results.extend(results)
                    self.after(0, lambda n=len(all_results):
                        self.lbl_subtitle.configure(
                            text=f"✓ {n} fırsat bulundu... devam ediyor"))
                except Exception:
                    pass
            self.after(0, self._scan_done, all_results, None)
        except Exception as e:
            import traceback
            self.after(0, self._scan_done, [], traceback.format_exc())

    def _scan_done(self, opps, error):
        self._loading = False
        self.pbar.stop()
        self.pbar.configure(mode="determinate")
        self.pbar.set(1 if not error else 0)
        self.btn_scan.configure(state="normal", text="🔄  Yeniden Tara")

        if error:
            messagebox.showerror(
                "Tarama Hatası",
                f"Fırsat taraması tamamlanamadı:\n\n{str(error)[:400]}")
            self.lbl_subtitle.configure(text="Tarama başarısız. Tekrar deneyin.")
            self.lbl_scan_time.configure(text="")
            return

        self._all_opps = opps
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        strong = sum(1 for o in opps if o.composite_score >= 65)
        self.lbl_subtitle.configure(
            text=f"{len(opps)} varlık tarandı  •  {strong} güçlü fırsat bulundu")
        self.lbl_scan_time.configure(text=f"Son tarama: {now}")
        self.summary_bar.update_stats(opps)
        self._apply_filters()

    # ─────────────────────────────────────────────────────────
    #  FİLTRELEME & SIRALAMA
    # ─────────────────────────────────────────────────────────
    def _apply_filters(self, *_):
        f = self.filter_panel.get_filters()
        filtered = list(self._all_opps)

        # Tür
        if f["types"]:
            filtered = [o for o in filtered if o.asset_type in f["types"]]

        # Risk
        if f["risks"]:
            filtered = [o for o in filtered if o.risk_level in f["risks"]]

        # Fırsat tipi
        if f["opps"]:
            filtered = [o for o in filtered if o.opportunity_type in f["opps"]]

        # Min skor
        if f["min_score"] > 0:
            filtered = [o for o in filtered if o.composite_score >= f["min_score"]]

        # Arama
        if f["search"]:
            s = f["search"]
            filtered = [o for o in filtered
                        if s in o.symbol.upper() or s in o.name.upper()]

        # Sıralama
        RISK_ORD = {"çok düşük": 0, "düşük": 1, "orta": 2,
                    "orta-yüksek": 3, "yüksek": 4, "çok yüksek": 5, "spekülatif": 6}
        sorts = {
            "skor_desc":  lambda o: -o.composite_score,
            "skor_asc":   lambda o:  o.composite_score,
            "conf_desc":  lambda o: -o.decision_confidence,
            "ret1d_desc": lambda o: -(o.return_1d  or -999),
            "ret1m_desc": lambda o: -(o.return_1m  or -999),
            "ret1y_desc": lambda o: -(o.return_1y  or -999),
            "risk_low":   lambda o:  RISK_ORD.get(o.risk_level, 9),
            "vol_low":    lambda o:  o.volatility or 999,
        }
        key_fn = sorts.get(f["sort"], sorts["skor_desc"])
        filtered.sort(key=key_fn)

        self._filtered = filtered
        self.filter_panel.set_count(len(filtered), len(self._all_opps))
        self._render_cards()

    # ─────────────────────────────────────────────────────────
    #  KARTLARI RENDER ET
    # ─────────────────────────────────────────────────────────
    def _render_cards(self):
        for w in self.card_scroll.winfo_children():
            w.destroy()
        self._cards = {}

        if not self._filtered:
            ctk.CTkLabel(
                self.card_scroll,
                text="Seçili filtrelere uygun fırsat bulunamadı.\n"
                     "Filtreleri gevşetin veya yeni tarama yapın.",
                font=F_BODY, text_color=TEXT2, justify="center"
            ).grid(row=0, column=0, columnspan=2, pady=50)
            return

        cols = 2
        for i, opp in enumerate(self._filtered[:80]):
            r, c = divmod(i, cols)
            is_sel = (opp.symbol == self._selected_symbol)
            card = OpportunityCard(
                self.card_scroll, opp,
                on_select=self._on_card_select,
                is_selected=is_sel)
            card.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
            self.card_scroll.columnconfigure(c, weight=1)
            self._cards[opp.symbol] = card

    def _on_card_select(self, opp):
        # Önceki seçimi kaldır
        if self._selected_symbol and self._selected_symbol in self._cards:
            self._cards[self._selected_symbol].select(False)

        self._selected_symbol = opp.symbol
        if opp.symbol in self._cards:
            self._cards[opp.symbol].select(True)

        self.detail.show(opp)
