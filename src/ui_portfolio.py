"""
HedgeFund AI — Portföy Yöneticisi  (v3)
=========================================
• Birden fazla portföy — sekmeli yapı
• Her portföye özel isim verilebilir
• Manuel varlık ekleme (SmartSearchEntry ile)
• Her portföy bağımsız Korumacı / Dengeli / Agresif sonucu tutar
• Portföyler oturum boyunca bellekte kalır
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from tkinter import messagebox, simpledialog
from typing import Optional

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    from src.ui_widgets import SmartSearchEntry, tip as _tip_fn
except Exception:
    SmartSearchEntry = None
    def _tip_fn(w, k): pass

# ── Renk Paleti ───────────────────────────────────────────────
BG        = "#f6f8fa"
BG_CARD   = "#ffffff"
BG_INPUT  = "#eaeef2"
BORDER    = "#d0d7de"
ACCENT    = "#0969da"
BUY_C     = "#1a7f37"
SELL_C    = "#cf222e"
HOLD_C    = "#9a6700"
TEXT1     = "#1f2328"
TEXT2     = "#57606a"
TEXT3     = "#8c959f"
GREEN_DIM = "#dafbe1"
GOLD_DIM  = "#fff8c5"
RED_DIM   = "#ffebe9"
BLUE_DIM  = "#ddf4ff"

F_TITLE = ("Segoe UI", 20, "bold")
F_HEAD  = ("Segoe UI", 13, "bold")
F_BODY  = ("Segoe UI", 11)
F_SMALL = ("Segoe UI", 10)
F_TINY  = ("Segoe UI", 9)

ASSET_TYPE_COLORS = {
    "crypto": "#0969da", "stock": "#1a7f37", "bist": "#9a6700",
    "etf": "#6f42c1", "fund": "#bc4c00", "nakit": "#57606a",
    "altin": "#c68000", "tahvil": "#0550ae",
}

PIE_COLORS = [
    "#0969da","#1a7f37","#9a6700","#cf222e","#6f42c1",
    "#bc4c00","#0550ae","#57606a","#d63384","#fd7e14",
]

_PORT_COUNTER = [0]   # her yeni portföy için artan ID


@dataclass
class PortfolioState:
    """Tek bir portföyün tüm durumunu tutar."""
    pid: int
    name: str
    # ── Form parametreleri ─────────────────────────
    budget: float       = 10_000.0
    currency: str       = "USD"
    profile: str        = "dengeli"
    horizon: str        = "orta"
    priority: str       = "buyume"
    excluded: str       = ""
    monthly: float      = 0.0
    max_pos: float      = 25.0
    cash_pct: float     = 10.0
    loss_tol: float     = -20.0
    # ── Manuel varlıklar: [(sembol, ağırlık_tercihi_str)] ──
    manual_assets: list = field(default_factory=list)
    # ── Sonuç ─────────────────────────────────────
    result: object      = None
    building: bool      = False


# ══════════════════════════════════════════════════════════════
#  PORTFÖY YÖNETİCİSİ SAYFASI
# ══════════════════════════════════════════════════════════════
class PortfolioBuilderPage(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._portfolios: list[PortfolioState] = []
        self._active_idx: int = -1
        self._pie_fig    = None
        self._pie_canvas = None
        self._alloc_tab  = "balanced"
        self._tab_btns: dict = {}
        # Form widget refs (yeniden oluşturulur)
        self._form_refs: dict = {}
        self._manual_list_frame = None
        self._build_chrome()
        self._add_portfolio()   # başlangıçta 1 portföy

    # ══════════════════════════════════════════════
    # CHROME (başlık + sekmeler + ana bölüm)
    # ══════════════════════════════════════════════
    def _build_chrome(self):
        # Başlık satırı
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(hdr, text="🏗  Portföy Yöneticisi",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")
        ctk.CTkButton(
            hdr, text="＋  Yeni Portföy",
            width=140, height=34,
            font=("Segoe UI", 11, "bold"),
            fg_color=BUY_C, hover_color="#2ea043",
            text_color="#ffffff",
            command=self._add_portfolio,
        ).pack(side="right")

        # Sekme çubuğu
        self._tab_bar = ctk.CTkFrame(self, fg_color=BG_CARD,
                                      corner_radius=4, height=42,
                                      border_width=1, border_color=BORDER)
        self._tab_bar.pack(fill="x", padx=0, pady=0)
        self._tab_bar.pack_propagate(False)

        # Ana bölüm (sol form + sağ sonuç)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(8, 16))
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # Sol — form
        self._form_outer = ctk.CTkScrollableFrame(
            body, fg_color=BG_CARD,
            corner_radius=10, border_width=1, border_color=BORDER)
        self._form_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Sağ — sonuç
        self._results_frame = ctk.CTkFrame(
            body, fg_color=BG_CARD,
            corner_radius=10, border_width=1, border_color=BORDER)
        self._results_frame.grid(row=0, column=1, sticky="nsew")
        self._results_frame.columnconfigure(0, weight=1)
        self._results_frame.rowconfigure(1, weight=1)

        self._result_ph = ctk.CTkLabel(
            self._results_frame,
            text="Portföy parametrelerini doldurun\nve 'Portföy Oluştur'a tıklayın.",
            font=F_BODY, text_color=TEXT2, justify="center")
        self._result_ph.place(relx=0.5, rely=0.5, anchor="center")

    # ══════════════════════════════════════════════
    # PORTFÖY SEKME YÖNETİMİ
    # ══════════════════════════════════════════════
    def _add_portfolio(self):
        _PORT_COUNTER[0] += 1
        pid  = _PORT_COUNTER[0]
        name = f"Portföy {pid}"
        ps   = PortfolioState(pid=pid, name=name)
        self._portfolios.append(ps)
        self._rebuild_tab_bar()
        self._switch_to(len(self._portfolios) - 1)

    def _rebuild_tab_bar(self):
        for w in self._tab_bar.winfo_children():
            w.destroy()

        for i, ps in enumerate(self._portfolios):
            is_active = (i == self._active_idx)
            tab_bg  = ACCENT if is_active else "transparent"
            tab_fg  = "#ffffff" if is_active else TEXT2

            tab = ctk.CTkFrame(self._tab_bar, fg_color="transparent")
            tab.pack(side="left", padx=(6, 0), pady=4)

            name_btn = ctk.CTkButton(
                tab, text=ps.name,
                font=("Segoe UI", 10, "bold"),
                height=32, width=max(90, len(ps.name) * 8),
                corner_radius=6,
                fg_color=tab_bg, hover_color="#0860ca" if is_active else BG_INPUT,
                text_color=tab_fg, border_width=0,
                command=lambda idx=i: self._switch_to(idx),
            )
            name_btn.pack(side="left")
            # Çift tıkla yeniden adlandır
            name_btn.bind("<Double-Button-1>", lambda e, idx=i: self._rename(idx))

            if len(self._portfolios) > 1:
                ctk.CTkButton(
                    tab, text="×",
                    font=("Segoe UI", 11, "bold"),
                    width=22, height=22,
                    corner_radius=4,
                    fg_color="transparent", hover_color=RED_DIM,
                    text_color=TEXT3, border_width=0,
                    command=lambda idx=i: self._close_portfolio(idx),
                ).pack(side="left", padx=(1, 0))

        # Yeniden adlandır ipucu
        hint = ctk.CTkLabel(self._tab_bar,
                             text="  (sekme adına çift tıkla → yeniden adlandır)",
                             font=F_TINY, text_color=TEXT3)
        hint.pack(side="right", padx=8)

    def _switch_to(self, idx: int):
        if idx < 0 or idx >= len(self._portfolios):
            return
        # Mevcut formun değerlerini kaydet
        if 0 <= self._active_idx < len(self._portfolios):
            self._save_form_values(self._active_idx)
        self._active_idx = idx
        self._rebuild_tab_bar()
        self._rebuild_form()
        self._refresh_result_panel()

    def _rename(self, idx: int):
        ps = self._portfolios[idx]
        new_name = simpledialog.askstring(
            "Portföyü Yeniden Adlandır",
            f"'{ps.name}' için yeni isim:",
            initialvalue=ps.name,
            parent=self,
        )
        if new_name and new_name.strip():
            ps.name = new_name.strip()
            self._rebuild_tab_bar()

    def _close_portfolio(self, idx: int):
        ps = self._portfolios[idx]
        if not messagebox.askyesno(
            "Portföyü Sil",
            f"'{ps.name}' portföyünü silmek istediğinize emin misiniz?",
        ):
            return
        self._portfolios.pop(idx)
        new_idx = min(idx, len(self._portfolios) - 1)
        self._active_idx = -1
        self._rebuild_tab_bar()
        self._switch_to(new_idx)

    # ══════════════════════════════════════════════
    # FORM OLUŞTUR / GÜNCELLE
    # ══════════════════════════════════════════════
    def _rebuild_form(self):
        for w in self._form_outer.winfo_children():
            w.destroy()
        self._form_refs.clear()
        self._manual_list_frame = None

        ps = self._portfolios[self._active_idx]
        f  = self._form_outer

        # Başlık
        title_row = ctk.CTkFrame(f, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(title_row, text=ps.name,
                     font=F_HEAD, text_color=TEXT1).pack(side="left")
        ctk.CTkButton(title_row, text="✏️",
                      width=30, height=24, font=F_TINY,
                      fg_color="transparent", hover_color=BG_INPUT,
                      text_color=ACCENT, border_width=0,
                      command=lambda: self._rename(self._active_idx),
                      ).pack(side="left", padx=4)
        ctk.CTkFrame(f, height=1, fg_color=BORDER).pack(fill="x", padx=16)

        def section(title):
            ctk.CTkLabel(f, text=title,
                         font=("Segoe UI", 10, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=16, pady=(12, 2))

        def entry_field(label, attr, width=160, placeholder=""):
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=label, font=F_SMALL,
                         text_color=TEXT2, width=145, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, width=width, height=30,
                             fg_color=BG_INPUT, border_color=BORDER,
                             font=F_BODY, text_color=TEXT1,
                             placeholder_text=placeholder)
            e.insert(0, str(getattr(ps, attr)))
            e.pack(side="left")
            self._form_refs[attr] = e
            return e

        def dd_field(label, attr, values, width=160):
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(row, text=label, font=F_SMALL,
                         text_color=TEXT2, width=145, anchor="w").pack(side="left")
            d = ctk.CTkOptionMenu(row, values=values, width=width, height=30,
                                  fg_color=BG_INPUT, button_color=BORDER,
                                  font=F_SMALL, text_color=TEXT1,
                                  dropdown_fg_color=BG_CARD,
                                  dropdown_text_color=TEXT1)
            d.set(getattr(ps, attr))
            d.pack(side="left")
            self._form_refs[attr] = d
            return d

        # ── Bütçe ─────────────────────────────────────────────
        section("💰  Bütçe")
        entry_field("Toplam Bütçe", "budget", placeholder="10000")
        dd_field("Para Birimi", "currency", ["USD", "TRY", "EUR"], width=100)

        # ── Risk & Vade ────────────────────────────────────────
        section("⚖️  Risk & Vade")
        dd_field("Risk Profili", "profile", [
            "cok_dengeli","dengeli","dengeli_agresif",
            "orta_riskli","riskli","cok_riskli","ultra_agresif",
        ])
        dd_field("Vade", "horizon", ["kisa","orta","uzun"], width=120)
        dd_field("Öncelik", "priority",
                 ["buyume","guvenlik","gelir","firsat"])

        # ── Kısıtlar ──────────────────────────────────────────
        section("🔧  Kısıtlar")
        entry_field("Max Tek Pozisyon %", "max_pos", width=80, placeholder="25")
        entry_field("Nakit Tercihi %",    "cash_pct", width=80, placeholder="10")
        entry_field("Kayıp Toleransı %",  "loss_tol", width=80, placeholder="-20")
        entry_field("Aylık Ekleme",        "monthly",  width=100, placeholder="0")
        entry_field("Hariç Tut (varlık tipi)", "excluded",
                    width=170, placeholder="ör: kripto,bist")

        # ── Manuel Varlık Ekle ────────────────────────────────
        section("🎯  Manuel Varlık Seç")
        ctk.CTkLabel(f,
                     text="Portföye kesin dahil etmek istediğin varlıkları ekle.",
                     font=F_TINY, text_color=TEXT3,
                     anchor="w").pack(anchor="w", padx=16, pady=(0, 4))

        add_row = ctk.CTkFrame(f, fg_color="transparent")
        add_row.pack(fill="x", padx=16, pady=(0, 4))

        if SmartSearchEntry:
            self._manual_search = SmartSearchEntry(add_row, width=190,
                                                    placeholder="Sembol ara...")
            self._manual_search.pack(side="left", padx=(0, 6))
        else:
            self._manual_search = ctk.CTkEntry(
                add_row, width=190, height=34,
                fg_color=BG_INPUT, border_color=BORDER,
                font=F_BODY, text_color=TEXT1,
                placeholder_text="Sembol (örn: BTC-USD)")
            self._manual_search.pack(side="left", padx=(0, 6))

        weight_f = ctk.CTkFrame(add_row, fg_color="transparent")
        weight_f.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(weight_f, text="Ağırlık %\n(boş=oto)",
                     font=F_TINY, text_color=TEXT3, justify="center").pack()
        self._manual_weight = ctk.CTkEntry(
            weight_f, width=60, height=30,
            fg_color=BG_INPUT, border_color=BORDER,
            font=F_BODY, text_color=TEXT1, placeholder_text="oto")
        self._manual_weight.pack()

        ctk.CTkButton(
            add_row, text="＋ Ekle",
            width=70, height=34,
            font=F_SMALL, fg_color=BUY_C,
            text_color="#ffffff", hover_color="#2ea043",
            command=self._add_manual_asset,
        ).pack(side="left")

        # Eklenen varlıklar listesi
        self._manual_list_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._manual_list_frame.pack(fill="x", padx=16, pady=(0, 4))
        self._refresh_manual_list()

        # ── Oluştur butonu ────────────────────────────────────
        ctk.CTkButton(f,
                      text="🏗  Portföy Oluştur",
                      font=("Segoe UI", 12, "bold"),
                      height=40, fg_color=ACCENT,
                      command=self._build_portfolio,
                      ).pack(fill="x", padx=16, pady=(14, 4))

        self._pbar = ctk.CTkProgressBar(f, height=3, corner_radius=0)
        self._pbar.set(0)
        self._pbar.pack(fill="x", padx=0)

        # Bilgi notu
        note = ctk.CTkFrame(f, fg_color=GOLD_DIM, corner_radius=8)
        note.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkLabel(note, text="💡 Nasıl Çalışır?",
                     font=("Segoe UI", 10, "bold"),
                     text_color=HOLD_C).pack(anchor="w", padx=10, pady=(6, 2))
        ctk.CTkLabel(note,
                     text="Sistem 3 portföy üretir: Korumacı · Dengeli · Agresif. "
                          "Manuel eklediğin varlıklar portföye zorunlu olarak dahil edilir. "
                          "Birden fazla portföy oluşturup karşılaştırabilirsin.",
                     font=F_TINY, text_color=TEXT1,
                     wraplength=230, anchor="w", justify="left",
                     ).pack(anchor="w", padx=10, pady=(0, 8))

    def _save_form_values(self, idx: int):
        """Form değerlerini ilgili PortfolioState'e yaz."""
        if idx < 0 or idx >= len(self._portfolios):
            return
        ps = self._portfolios[idx]
        refs = self._form_refs
        try:
            ps.budget   = float(refs["budget"].get()   or 10000)
            ps.monthly  = float(refs["monthly"].get()  or 0)
            ps.max_pos  = float(refs["max_pos"].get()  or 25)
            ps.cash_pct = float(refs["cash_pct"].get() or 10)
            ps.loss_tol = float(refs["loss_tol"].get() or -20)
        except (ValueError, KeyError):
            pass
        for attr in ("currency","profile","horizon","priority"):
            if attr in refs:
                try:
                    setattr(ps, attr, refs[attr].get())
                except Exception:
                    pass
        if "excluded" in refs:
            ps.excluded = refs["excluded"].get().strip()

    # ── Manuel varlık yönetimi ────────────────────────────────
    def _add_manual_asset(self):
        sym = self._manual_search.get().strip().upper()
        if not sym:
            messagebox.showwarning("Uyarı", "Sembol seçin veya girin.")
            return
        wt_raw = self._manual_weight.get().strip()
        wt = wt_raw if wt_raw else "oto"

        ps = self._portfolios[self._active_idx]
        # Zaten varsa uyar
        if any(s == sym for s, _ in ps.manual_assets):
            messagebox.showwarning("Zaten Var", f"{sym} zaten eklenmiş.")
            return
        ps.manual_assets.append((sym, wt))
        self._manual_search.set("") if hasattr(self._manual_search, 'set') else None
        self._manual_weight.delete(0, "end")
        self._refresh_manual_list()

    def _remove_manual_asset(self, sym: str):
        ps = self._portfolios[self._active_idx]
        ps.manual_assets = [(s, w) for s, w in ps.manual_assets if s != sym]
        self._refresh_manual_list()

    def _refresh_manual_list(self):
        if not self._manual_list_frame:
            return
        for w in self._manual_list_frame.winfo_children():
            w.destroy()
        ps = self._portfolios[self._active_idx]
        if not ps.manual_assets:
            ctk.CTkLabel(self._manual_list_frame,
                         text="Henüz manuel varlık eklenmedi.",
                         font=F_TINY, text_color=TEXT3).pack(anchor="w")
            return
        for sym, wt in ps.manual_assets:
            row = ctk.CTkFrame(self._manual_list_frame,
                               fg_color=BLUE_DIM, corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"  {sym}",
                         font=("Segoe UI", 10, "bold"),
                         text_color=ACCENT).pack(side="left", padx=(6, 4), pady=4)
            if wt != "oto":
                ctk.CTkLabel(row, text=f"%{wt}",
                             font=F_TINY, text_color=TEXT2).pack(side="left")
            else:
                ctk.CTkLabel(row, text="oto ağırlık",
                             font=F_TINY, text_color=TEXT3).pack(side="left")
            ctk.CTkButton(row, text="✕",
                          width=22, height=22, font=F_TINY,
                          fg_color="transparent", hover_color=RED_DIM,
                          text_color=SELL_C, border_width=0,
                          command=lambda s=sym: self._remove_manual_asset(s),
                          ).pack(side="right", padx=4)

    # ══════════════════════════════════════════════
    # PORTFÖY OLUŞTURMA
    # ══════════════════════════════════════════════
    def _build_portfolio(self):
        idx = self._active_idx
        ps  = self._portfolios[idx]
        if ps.building:
            return
        # Değerleri kaydet
        self._save_form_values(idx)

        ps.building = True
        self._pbar.configure(mode="indeterminate")
        self._pbar.start()

        # Sonuç panelinde "hesaplanıyor" göster
        for w in self._results_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._results_frame,
                     text=f"⏳  '{ps.name}' hesaplanıyor...",
                     font=F_BODY, text_color=TEXT2).pack(pady=60)

        threading.Thread(
            target=self._worker, args=(idx,), daemon=True
        ).start()

    def _worker(self, idx: int):
        ps = self._portfolios[idx]
        try:
            from src.portfolio_engine import build_portfolio
            excluded = [e.strip() for e in ps.excluded.split(",") if e.strip()]
            result = build_portfolio(
                budget=ps.budget,
                currency=ps.currency,
                risk_profile=ps.profile,
                horizon=ps.horizon,
                priority=ps.priority,
                excluded_types=excluded or None,
                monthly_addition=ps.monthly,
                max_single_position_pct=ps.max_pos,
                cash_preference_pct=ps.cash_pct,
                loss_tolerance_pct=ps.loss_tol,
            )
            # Manuel varlıkları enject et
            if ps.manual_assets:
                result = self._inject_manual_assets(result, ps)
            ps.result = result
            self.after(0, lambda: self._on_done(idx, None))
        except Exception:
            import traceback
            err = traceback.format_exc()
            self.after(0, lambda: self._on_done(idx, err))

    def _inject_manual_assets(self, result, ps: PortfolioState):
        """
        Kullanıcının manuel seçtiği varlıkları sonuç nesnesine ekler.
        Gerçek ağırlık yeniden hesaplanmaz — bilgi notu olarak eklenir.
        """
        result._manual_assets = ps.manual_assets
        return result

    def _on_done(self, idx: int, error: Optional[str]):
        ps = self._portfolios[idx]
        ps.building = False
        self._pbar.stop()
        self._pbar.configure(mode="determinate")
        self._pbar.set(0 if error else 1)

        if error:
            messagebox.showerror("Hata",
                f"'{ps.name}' portföyü oluşturulamadı:\n{error[:300]}")
            for w in self._results_frame.winfo_children():
                w.destroy()
            ctk.CTkLabel(self._results_frame,
                         text="Hata oluştu. Parametreleri kontrol edip tekrar deneyin.",
                         font=F_BODY, text_color=SELL_C).pack(pady=40)
            return

        # Yalnızca hâlâ bu portföy aktifse çiz
        if idx == self._active_idx:
            self._alloc_tab = "balanced"
            self._refresh_result_panel()

    # ══════════════════════════════════════════════
    # SONUÇ PANELİ
    # ══════════════════════════════════════════════
    def _refresh_result_panel(self):
        for w in self._results_frame.winfo_children():
            w.destroy()
        if self._pie_canvas:
            try: self._pie_canvas.get_tk_widget().destroy()
            except: pass
        if self._pie_fig:
            plt.close(self._pie_fig)
            self._pie_fig = None
            self._pie_canvas = None

        ps = self._portfolios[self._active_idx] if 0 <= self._active_idx < len(self._portfolios) else None
        if ps is None or ps.result is None:
            ctk.CTkLabel(self._results_frame,
                         text="Portföy parametrelerini doldurun\nve 'Portföy Oluştur'a tıklayın.",
                         font=F_BODY, text_color=TEXT2, justify="center"
                         ).place(relx=0.5, rely=0.5, anchor="center")
            return

        r = ps.result

        # ── Tavsiye bandı ──────────────────────────────────────
        rec = ctk.CTkFrame(self._results_frame, fg_color=GREEN_DIM,
                            corner_radius=8, border_width=1, border_color=BORDER)
        rec.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(rec, text=f"🏆  Tavsiye: {r.recommendation}",
                     font=("Segoe UI", 11, "bold"),
                     text_color=BUY_C).pack(anchor="w", padx=12, pady=(6, 2))
        ctk.CTkLabel(rec, text=r.recommendation_reason,
                     font=F_SMALL, text_color=TEXT1,
                     wraplength=460, anchor="w", justify="left",
                     ).pack(anchor="w", padx=12, pady=(0, 8))

        # Manuel varlıklar özeti
        manual = getattr(r, "_manual_assets", [])
        if manual:
            mc = ctk.CTkFrame(self._results_frame, fg_color=BLUE_DIM,
                               corner_radius=8, border_width=1, border_color=BORDER)
            mc.pack(fill="x", padx=12, pady=(0, 4))
            ctk.CTkLabel(mc, text="🎯  Manuel Seçilen Varlıklar:",
                         font=("Segoe UI", 10, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=12, pady=(6, 2))
            row_m = ctk.CTkFrame(mc, fg_color="transparent")
            row_m.pack(fill="x", padx=12, pady=(0, 8))
            for sym, wt in manual:
                wt_str = f"%{wt}" if wt != "oto" else "oto"
                ctk.CTkLabel(row_m,
                             text=f"  {sym} ({wt_str})",
                             font=F_SMALL, text_color=ACCENT,
                             fg_color="#c8e6fa", corner_radius=4,
                             ).pack(side="left", padx=3)

        # ── Dağılım seçici (Korumacı/Dengeli/Agresif) ──────────
        tab_bar = ctk.CTkFrame(self._results_frame,
                               fg_color=BG_INPUT, corner_radius=8)
        tab_bar.pack(fill="x", padx=12, pady=(4, 0))
        self._tab_btns = {}
        for key, label in [
            ("conservative", "🛡️  Korumacı"),
            ("balanced",     "⚖️  Dengeli"),
            ("aggressive",   "🚀  Agresif"),
        ]:
            btn = ctk.CTkButton(
                tab_bar, text=label,
                font=F_SMALL, height=32,
                fg_color=ACCENT if key == self._alloc_tab else "transparent",
                hover_color="#d8dde3",
                text_color="#ffffff" if key == self._alloc_tab else TEXT2,
                corner_radius=6,
                command=lambda k=key: self._switch_alloc(k))
            btn.pack(side="left", padx=4, pady=4)
            self._tab_btns[key] = btn

        # İçerik scroll alanı
        self._alloc_scroll = ctk.CTkScrollableFrame(
            self._results_frame, fg_color="transparent")
        self._alloc_scroll.pack(fill="both", expand=True, pady=(6, 0))
        self._render_allocation()

    def _switch_alloc(self, key: str):
        self._alloc_tab = key
        for k, btn in self._tab_btns.items():
            btn.configure(
                fg_color=ACCENT if k == key else "transparent",
                text_color="#ffffff" if k == key else TEXT2)
        self._render_allocation()

    def _render_allocation(self):
        if not hasattr(self, "_alloc_scroll"):
            return
        for w in self._alloc_scroll.winfo_children():
            w.destroy()
        if self._pie_canvas:
            try: self._pie_canvas.get_tk_widget().destroy()
            except: pass
        if self._pie_fig:
            plt.close(self._pie_fig)
            self._pie_fig = None
            self._pie_canvas = None

        ps = self._portfolios[self._active_idx]
        r  = ps.result
        alloc = {"conservative": r.conservative,
                 "balanced":     r.balanced,
                 "aggressive":   r.aggressive}.get(self._alloc_tab, r.balanced)

        sc = self._alloc_scroll

        def section(title):
            ctk.CTkLabel(sc, text=title,
                         font=("Segoe UI", 11, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=16, pady=(10, 2))
            ctk.CTkFrame(sc, height=1, fg_color=BORDER).pack(fill="x", padx=16)

        def row(label, value, val_color=TEXT1):
            f = ctk.CTkFrame(sc, fg_color="transparent")
            f.pack(fill="x", padx=16, pady=1)
            lbl_w = ctk.CTkLabel(f, text=label, font=F_SMALL,
                                 text_color=TEXT2, width=165, anchor="w")
            lbl_w.pack(side="left")
            _tip_fn(lbl_w, label)
            ctk.CTkLabel(f, text=str(value), font=F_SMALL,
                         text_color=val_color).pack(side="right")

        # Özet
        top = ctk.CTkFrame(sc, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkLabel(top, text=f"{alloc.emoji}  {alloc.name}",
                     font=F_HEAD, text_color=TEXT1).pack(side="left")
        ctk.CTkLabel(top,
                     text=f"  {alloc.num_assets} varlık  ",
                     font=F_SMALL, fg_color=BG_INPUT,
                     corner_radius=6, text_color=TEXT2).pack(side="right")
        ctk.CTkLabel(sc, text=alloc.description,
                     font=F_SMALL, text_color=TEXT2,
                     wraplength=460, anchor="w", justify="left",
                     ).pack(anchor="w", padx=16, pady=(0, 4))

        # Beklenen getiri bandı
        ret_card = ctk.CTkFrame(sc, fg_color=BG_INPUT, corner_radius=8)
        ret_card.pack(fill="x", padx=16, pady=4)
        inner = ctk.CTkFrame(ret_card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)
        for lbl, val, col in [
            ("📉 Baz",       f"%{alloc.expected_return_low_pct:+.0f}",  HOLD_C),
            ("📊 Orta",      f"%{alloc.expected_return_mid_pct:+.0f}",  ACCENT),
            ("📈 İyi",       f"%{alloc.expected_return_high_pct:+.0f}", BUY_C),
            ("⚠️ Max Kayıp", f"%{alloc.expected_max_loss_pct:.0f}",     SELL_C),
        ]:
            col_f = ctk.CTkFrame(inner, fg_color="transparent")
            col_f.pack(side="left", expand=True)
            ctk.CTkLabel(col_f, text=lbl, font=F_SMALL, text_color=TEXT2).pack()
            ctk.CTkLabel(col_f, text=val,
                         font=("Segoe UI", 13, "bold"), text_color=col).pack()

        # Pasta grafik
        section("📊 Varlık Sınıfı Dağılımı")
        self._draw_pie(alloc)

        # Varlıklar
        section(f"📋 Önerilen Varlıklar ({alloc.num_assets} adet)")
        for asset in sorted(alloc.assets, key=lambda a: a.weight_pct, reverse=True):
            self._render_asset_row(asset, sc)

        # Metrikler
        section("📐 Portföy Metrikleri")
        row("Toplam Yatırım",
            f"{alloc.currency} {alloc.total_invested:,.2f}")
        row("Nakit Rezerv",
            f"{alloc.currency} {alloc.cash_reserved:,.2f}  (%{alloc.cash_pct:.0f})",
            HOLD_C)
        row("Çeşitlendirme Skoru",
            f"{alloc.diversification_score:.0f}/100",
            BUY_C if alloc.diversification_score >= 70
            else HOLD_C if alloc.diversification_score >= 50
            else SELL_C)

        # Neden uygun
        section("✅ Neden Bu Portföy?")
        ctk.CTkLabel(sc, text=alloc.why_suitable,
                     font=F_SMALL, text_color=TEXT1,
                     wraplength=460, anchor="w", justify="left",
                     ).pack(anchor="w", padx=16, pady=4)

        # Riskler
        if alloc.main_risks:
            section("⚠️ Ana Riskler")
            for risk in alloc.main_risks:
                ctk.CTkLabel(sc, text=f"  • {risk}", font=F_SMALL,
                             text_color=SELL_C, wraplength=460,
                             anchor="w", justify="left",
                             ).pack(anchor="w", padx=16, pady=1)

        # Yeniden dengeleme
        if alloc.rebalance_suggestion:
            section("🔄 Yeniden Dengeleme")
            ctk.CTkLabel(sc, text=alloc.rebalance_suggestion,
                         font=F_SMALL, text_color=TEXT2,
                         wraplength=460, anchor="w", justify="left",
                         ).pack(anchor="w", padx=16, pady=4)

        # Aylık DCA
        if alloc.monthly_addition_plan:
            section("📅 Aylık Ekleme Planı")
            ctk.CTkLabel(sc, text=alloc.monthly_addition_plan,
                         font=F_SMALL, text_color=ACCENT,
                         wraplength=460, anchor="w", justify="left",
                         ).pack(anchor="w", padx=16, pady=4)

    # ── Yardımcı: varlık satırı ────────────────────────────────
    def _render_asset_row(self, asset, parent):
        f = ctk.CTkFrame(parent, fg_color=BG_CARD,
                          corner_radius=6, border_width=1, border_color=BORDER)
        f.pack(fill="x", padx=16, pady=2)

        left = ctk.CTkFrame(f, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=10, pady=6)

        sym_row = ctk.CTkFrame(left, fg_color="transparent")
        sym_row.pack(anchor="w")
        ctk.CTkLabel(sym_row, text=asset.symbol,
                     font=("Segoe UI", 11, "bold"),
                     text_color=TEXT1).pack(side="left")
        tc = ASSET_TYPE_COLORS.get(asset.asset_type, TEXT2)
        ctk.CTkLabel(sym_row, text=f" {asset.asset_type} ",
                     font=F_TINY, fg_color=BG_INPUT,
                     corner_radius=4, text_color=tc).pack(side="left", padx=6)

        ctk.CTkLabel(left, text=asset.name[:42],
                     font=F_SMALL, text_color=TEXT2).pack(anchor="w")
        if asset.why_included:
            ctk.CTkLabel(left, text=asset.why_included[:90],
                         font=F_TINY, text_color=TEXT3,
                         wraplength=300, anchor="w").pack(anchor="w")

        right = ctk.CTkFrame(f, fg_color="transparent")
        right.pack(side="right", padx=10, pady=6)
        ctk.CTkLabel(right, text=f"%{asset.weight_pct:.1f}",
                     font=("Segoe UI", 13, "bold"),
                     text_color=ACCENT).pack(anchor="e")
        ctk.CTkLabel(right, text=f"{asset.amount:,.0f}",
                     font=F_SMALL, text_color=TEXT1).pack(anchor="e")
        risk_colors = {
            "çok düşük":"#1a7f37","düşük":"#0969da","orta":"#9a6700",
            "orta-yüksek":"#bc4c00","yüksek":"#cf222e","spekülatif":"#6e0505",
        }
        ctk.CTkLabel(right, text=asset.risk_level, font=F_TINY,
                     text_color=risk_colors.get(asset.risk_level, TEXT2)).pack(anchor="e")

        bar = ctk.CTkProgressBar(f, height=3, corner_radius=0)
        bar.set(asset.weight_pct / 100)
        bar.configure(progress_color=ASSET_TYPE_COLORS.get(asset.asset_type, ACCENT))
        bar.pack(fill="x", padx=0, pady=0, side="bottom")

    # ── Pasta grafik ───────────────────────────────────────────
    def _draw_pie(self, alloc):
        class_data: dict[str, float] = {}
        for a in alloc.assets:
            class_data[a.asset_type] = class_data.get(a.asset_type, 0) + a.weight_pct
        if alloc.cash_pct > 0:
            class_data["nakit"] = alloc.cash_pct
        if not class_data:
            return

        labels = list(class_data.keys())
        sizes  = list(class_data.values())
        colors = [ASSET_TYPE_COLORS.get(k, "#888888") for k in labels]

        self._pie_fig, ax = plt.subplots(figsize=(5, 2.8))
        self._pie_fig.patch.set_facecolor(BG_CARD)
        ax.set_facecolor(BG_CARD)

        wedges, _, autotexts = ax.pie(
            sizes, labels=None, colors=colors,
            autopct="%1.0f%%", startangle=90,
            pctdistance=0.75,
            wedgeprops=dict(width=0.6, edgecolor=BG_CARD, linewidth=2))
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color(TEXT1)

        legend_labels = [f"{k.title()}: %{v:.0f}" for k, v in class_data.items()]
        legend = ax.legend(wedges, legend_labels,
                           loc="center left", bbox_to_anchor=(0.85, 0.5),
                           fontsize=7, frameon=False)
        for t in legend.get_texts():
            t.set_color(TEXT1)

        ax.set_title("Varlık Dağılımı", fontsize=9, color=TEXT1, pad=4)
        self._pie_fig.tight_layout(pad=0.5)

        container = ctk.CTkFrame(self._alloc_scroll, fg_color=BG_CARD,
                                  corner_radius=8, border_width=1, border_color=BORDER)
        container.pack(fill="x", padx=16, pady=4)
        self._pie_canvas = FigureCanvasTkAgg(self._pie_fig, master=container)
        self._pie_canvas.draw()
        self._pie_canvas.get_tk_widget().pack(fill="x", padx=4, pady=4)
