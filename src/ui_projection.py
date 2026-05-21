"""
HedgeFund AI — İleriye Dönük Projeksiyon Sayfası
=================================================
Kullanıcı bir varlık, alış tarihi, satış tarihi ve yatırım tutarı girerek
olası kâr/zarar/risk senaryolarını görür.

Özellikler:
  • SmartSearchEntry  — tıklayınca tüm liste, yazınca daralan arama
  • DatePicker        — Gün/Ay/Yıl dropdown, elle yazma yok
  • Monte Carlo grafiği (matplotlib)
  • Senaryo kartları (Boğa / Baz / Ayı)
  • Tarihsel dönem analizi
  • Benchmark karşılaştırması (SPY / Altın)
  • Risk uyarıları & eğitim notları
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Optional

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from src.ui_widgets import SmartSearchEntry, DatePicker, tip as _tip

# ── Renk paleti ───────────────────────────────────────────────────────────────
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
RED_DIM   = "#ffebe9"
GREEN_DIM = "#dafbe1"
GOLD_DIM  = "#fff8c5"
BLUE_DIM  = "#ddf4ff"

F_TITLE = ("Segoe UI", 20, "bold")
F_HEAD  = ("Segoe UI", 13, "bold")
F_BODY  = ("Segoe UI", 11)
F_SMALL = ("Segoe UI", 10)
F_TINY  = ("Segoe UI", 9)

# ── Yardımcı ──────────────────────────────────────────────────────────────────
def _pct_color(v: float) -> str:
    return BUY_C if v > 0 else SELL_C if v < 0 else TEXT2

def _fmt_money(v: float, currency: str = "USD") -> str:
    sym = "₺" if currency == "TRY" else "$"
    if abs(v) >= 1_000_000:
        return f"{sym}{v/1_000_000:+.2f}M"
    if abs(v) >= 1_000:
        return f"{sym}{v:+,.0f}"
    return f"{sym}{v:+.2f}"

def _section_label(parent, text: str):
    ctk.CTkLabel(parent, text=text, font=F_HEAD, text_color=ACCENT
                 ).pack(anchor="w", padx=16, pady=(14, 2))
    ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=(0, 6))

def _row(parent, label: str, value: str, val_color=TEXT1):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", padx=16, pady=2)
    lbl_w = ctk.CTkLabel(f, text=label, font=F_SMALL, text_color=TEXT2,
                         width=185, anchor="w")
    lbl_w.pack(side="left")
    _tip(lbl_w, label)
    ctk.CTkLabel(f, text=value, font=("Segoe UI", 11, "bold"),
                 text_color=val_color).pack(side="right")


# ══════════════════════════════════════════════════════════════════════════════
# PROJEKSİYON SAYFASI
# ══════════════════════════════════════════════════════════════════════════════
class ProjectionPage(ctk.CTkFrame):
    """İleriye dönük projeksiyon ana sayfası."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._result = None
        self._fig    = None
        self._canvas = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        # Başlık
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 6))
        ctk.CTkLabel(hdr, text="📈 İleriye Dönük Projeksiyon",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")
        ctk.CTkLabel(hdr, text="Monte Carlo + Senaryo Analizi",
                     font=F_SMALL, text_color=TEXT2).pack(side="left", padx=12)

        # ── Giriş paneli ────────────────────────────────────────────────────
        input_card = ctk.CTkFrame(self, fg_color=BG_CARD,
                                   corner_radius=12, border_width=1,
                                   border_color=BORDER)
        input_card.pack(fill="x", padx=20, pady=(0, 10))

        fields = ctk.CTkFrame(input_card, fg_color="transparent")
        fields.pack(fill="x", padx=16, pady=(14, 10))

        # Satır 1: Sembol + Tutar + Para birimi
        row1 = ctk.CTkFrame(fields, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(row1, text="Varlık Sembolü", font=F_SMALL,
                     text_color=TEXT2, width=115, anchor="w").pack(side="left")
        self._sym_entry = SmartSearchEntry(
            row1, width=290,
            on_select=self._on_symbol_selected,
        )
        self._sym_entry.pack(side="left", padx=(0, 28))

        ctk.CTkLabel(row1, text="Yatırım Tutarı", font=F_SMALL,
                     text_color=TEXT2, width=110, anchor="w").pack(side="left")
        self._amount_entry = ctk.CTkEntry(
            row1, width=130, height=36,
            fg_color=BG_INPUT, border_color=BORDER,
            font=("Segoe UI", 11, "bold"), text_color=TEXT1,
            placeholder_text="10000",
        )
        self._amount_entry.pack(side="left", padx=(0, 8))

        self._currency_var = ctk.StringVar(value="USD")
        ctk.CTkOptionMenu(
            row1, variable=self._currency_var,
            values=["USD", "TRY", "EUR"],
            width=72, height=36,
            fg_color=BG_INPUT, button_color=BORDER,
            font=F_BODY, text_color=TEXT1,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT1,
        ).pack(side="left")

        # Satır 2: Alış tarihi + Satış tarihi + Hesapla butonu
        row2 = ctk.CTkFrame(fields, fg_color="transparent")
        row2.pack(fill="x")

        today     = date.today()
        next_year = date(today.year + 1, today.month, today.day)

        ctk.CTkLabel(row2, text="Alış Tarihi", font=F_SMALL,
                     text_color=TEXT2, width=115, anchor="w").pack(side="left")
        self._buy_picker = DatePicker(row2, initial_date=today,
                                      min_year=2020, max_year=2035)
        self._buy_picker.pack(side="left", padx=(0, 28))

        ctk.CTkLabel(row2, text="Tahmini Satış", font=F_SMALL,
                     text_color=TEXT2, width=110, anchor="w").pack(side="left")
        self._sell_picker = DatePicker(row2, initial_date=next_year,
                                       min_year=2020, max_year=2035)
        self._sell_picker.pack(side="left", padx=(0, 20))

        self._btn = ctk.CTkButton(
            row2, text="▶  Projeksiyon Hesapla",
            width=200, height=36,
            font=("Segoe UI", 11, "bold"),
            fg_color=ACCENT,
            command=self._run,
        )
        self._btn.pack(side="left", padx=(8, 0))

        # İlerleme çubuğu
        self._pbar = ctk.CTkProgressBar(input_card, height=3, corner_radius=0)
        self._pbar.set(0)
        self._pbar.pack(fill="x")

        # ── Sonuç alanı ─────────────────────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        # Sol — grafik
        self._chart_frame = ctk.CTkFrame(
            content, fg_color=BG_CARD,
            corner_radius=12, border_width=1, border_color=BORDER)
        self._chart_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._chart_ph = ctk.CTkLabel(
            self._chart_frame,
            text="Projeksiyon hesaplandıktan sonra\nMonte Carlo grafiği burada görünür",
            font=F_BODY, text_color=TEXT2, justify="center")
        self._chart_ph.place(relx=0.5, rely=0.5, anchor="center")

        # Sağ — sonuçlar
        self._results_scroll = ctk.CTkScrollableFrame(
            content, fg_color=BG_CARD,
            corner_radius=12, border_width=1, border_color=BORDER)
        self._results_scroll.grid(row=0, column=1, sticky="nsew")
        self._results_ph = ctk.CTkLabel(
            self._results_scroll,
            text="Senaryo analizi burada görünecek\n\n"
                 "Sembolü seç ve 'Projeksiyon Hesapla'ya tıkla",
            font=F_BODY, text_color=TEXT2, justify="center")
        self._results_ph.pack(pady=60)

    # ── Sembol seçimi ─────────────────────────────────────────────────────────
    def _on_symbol_selected(self, sym: str, name: str, cat: str):
        """Para birimini kategoriye göre otomatik ayarla."""
        if cat in ("BIST", "BIST ETF", "Yatırım Fonu"):
            self._currency_var.set("TRY")
        else:
            self._currency_var.set("USD")

    # ── Hesapla ───────────────────────────────────────────────────────────────
    def _run(self):
        sym = self._sym_entry.get()
        if not sym:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", "Lütfen bir sembol seçin veya girin.")
            return

        buy_date  = self._buy_picker.get_date()
        sell_date = self._sell_picker.get_date()
        if not buy_date or not sell_date:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", "Geçerli tarihler seçin.")
            return
        if sell_date <= buy_date:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", "Satış tarihi alış tarihinden sonra olmalıdır.")
            return

        amt_txt = self._amount_entry.get().strip()
        try:
            amount = float(amt_txt.replace(",", "")) if amt_txt else 10_000.0
        except ValueError:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", "Geçerli bir tutar girin.")
            return

        currency = self._currency_var.get()

        # Varlık türü belirle
        selected = self._sym_entry.get_selected()
        cat = selected[2] if selected else ""
        if "Kripto" in cat or "-USD" in sym or "-BTC" in sym:
            asset_type = "crypto"
        elif "BIST" in cat or sym.endswith(".IS"):
            asset_type = "bist"
        elif cat == "ETF":
            asset_type = "etf"
        else:
            asset_type = "stock"

        self._btn.configure(state="disabled", text="Hesaplanıyor...")
        self._pbar.configure(mode="indeterminate")
        self._pbar.start()

        threading.Thread(
            target=self._worker,
            args=(sym, asset_type, buy_date, sell_date, amount, currency),
            daemon=True,
        ).start()

    def _worker(self, sym, asset_type, buy_date, sell_date, amount, currency):
        try:
            from src.projection_engine import run_projection
            result = run_projection(
                symbol=sym, name=sym,
                asset_type=asset_type,
                buy_date=buy_date, sell_date=sell_date,
                amount=amount, currency=currency,
            )
            self.after(0, lambda: self._apply_result(result, None))
        except Exception:
            import traceback
            err = traceback.format_exc()
            self.after(0, lambda: self._apply_result(None, err))

    def _apply_result(self, result, error):
        self._pbar.stop()
        self._pbar.configure(mode="determinate")
        self._pbar.set(1 if not error else 0)
        self._btn.configure(state="normal", text="▶  Projeksiyon Hesapla")

        if error:
            from tkinter import messagebox
            messagebox.showerror("Hata", f"Projeksiyon hesaplanamadı:\n{error[:400]}")
            return
        if result is None:
            from tkinter import messagebox
            messagebox.showerror("Hata",
                "Veri alınamadı.\n\nSembolü ve internet bağlantısını kontrol edin.\n"
                "Yatırım Fonu sembolleri (.F) için TEFAS bağlantısı gereklidir.")
            return

        self._result = result
        self._draw_chart(result)
        self._draw_results(result)

    # ── Monte Carlo Grafiği ────────────────────────────────────────────────────
    def _draw_chart(self, r):
        if self._canvas:
            try:
                self._canvas.get_tk_widget().destroy()
            except Exception:
                pass
        if self._fig:
            plt.close(self._fig)
        self._chart_ph.place_forget()

        mc       = r.monte_carlo
        amount   = r.amount
        n_days   = r.holding_days
        currency = r.currency
        cur_sym  = "₺" if currency == "TRY" else "$"
        x        = list(range(n_days + 1))

        plt.style.use("default")
        self._fig = plt.Figure(figsize=(7, 5), facecolor=BG_CARD)
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT2, labelsize=8)
        ax.grid(color=BORDER, linewidth=0.4, alpha=0.8)
        ax.spines[:].set_color(BORDER)

        # Yol örnekleri
        if mc and mc.paths_sample:
            for path in mc.paths_sample:
                vals = [amount * p for p in path]
                ax.plot(x[:len(vals)], vals, color=ACCENT, alpha=0.07, linewidth=0.7)

        # Persentil bantları
        if mc:
            def _proj(pct_r):
                final = amount * (1 + pct_r / 100)
                return [amount + (final - amount) * t / n_days for t in range(n_days + 1)]

            ax.fill_between(x, _proj(mc.percentile_25), _proj(mc.percentile_75),
                            color=ACCENT, alpha=0.15, label="25–75. persentil")
            ax.fill_between(x, _proj(mc.percentile_5),  _proj(mc.percentile_95),
                            color=ACCENT, alpha=0.07,  label="5–95. persentil")
            ax.plot(x, _proj(mc.percentile_50), color=ACCENT, linewidth=2,
                    label=f"Medyan ({mc.percentile_50:+.1f}%)")

        # Senaryo çizgileri
        def _draw_s(sc, color, style):
            if not sc: return
            final = amount * (1 + sc.return_pct / 100)
            yv = [amount + (final - amount) * t / n_days for t in range(n_days + 1)]
            ax.plot(x, yv, color=color, linewidth=1.6,
                    linestyle=style, label=f"{sc.name} ({sc.return_pct:+.0f}%)")

        _draw_s(r.scenario_bull, BUY_C,  "--")
        _draw_s(r.scenario_base, HOLD_C, "-")
        _draw_s(r.scenario_bear, SELL_C, "--")

        ax.axhline(amount, color=TEXT2, linewidth=0.8, linestyle=":", alpha=0.7,
                   label="Başlangıç")

        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{cur_sym}{v:,.0f}"))
        ax.set_xlabel("Gün", color=TEXT2, fontsize=9)
        ax.set_ylabel(f"Portföy Değeri ({currency})", color=TEXT2, fontsize=9)
        ax.set_title(
            f"{r.symbol} — Monte Carlo ({r.holding_days} gün / {r.holding_years:.1f} yıl)",
            color=TEXT1, fontsize=10, pad=8)
        ax.legend(fontsize=7, framealpha=0.7, loc="upper left")
        self._fig.patch.set_facecolor(BG_CARD)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self._chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # ── Sonuç Paneli ──────────────────────────────────────────────────────────
    def _draw_results(self, r):
        for w in self._results_scroll.winfo_children():
            w.destroy()

        currency = r.currency
        amount   = r.amount
        mc       = r.monte_carlo
        hist     = r.historical

        # ── Özet kart ───────────────────────────────────────────────────────
        v_col = (BUY_C  if any(k in r.summary_verdict.lower()
                               for k in ("pozitif","karlı","iyi"))
                 else SELL_C if any(k in r.summary_verdict.lower()
                                    for k in ("olumsuz","kayıp","kötü"))
                 else HOLD_C)
        v_bg = GREEN_DIM if v_col == BUY_C else RED_DIM if v_col == SELL_C else GOLD_DIM

        sc = ctk.CTkFrame(self._results_scroll, fg_color=v_bg,
                           corner_radius=10, border_width=1, border_color=BORDER)
        sc.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(sc, text=r.summary_verdict,
                     font=("Segoe UI", 11, "bold"), text_color=v_col,
                     wraplength=280, justify="left").pack(anchor="w", padx=12, pady=(8, 4))

        meta = ctk.CTkFrame(sc, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 8))
        for txt in [
            f"🎯 Güven: {r.confidence_score:.0f}%",
            f"⏱ {r.holding_days} gün ({r.holding_years:.1f} yıl)",
            f"📉 Vol: {r.annual_volatility_pct:.1f}%/yıl",
        ]:
            ctk.CTkLabel(meta, text=txt, font=F_TINY,
                         text_color=TEXT2).pack(side="left", padx=(0, 14))

        # ── Senaryo kartları ─────────────────────────────────────────────────
        _section_label(self._results_scroll, "📊 Senaryo Ağacı")

        for scenario, bg, border_c in [
            (r.scenario_bull, "#e6f4ea", "#34a853"),
            (r.scenario_base, GOLD_DIM,  HOLD_C),
            (r.scenario_bear, RED_DIM,   SELL_C),
        ]:
            if not scenario:
                continue
            card = ctk.CTkFrame(self._results_scroll, fg_color=bg,
                                 corner_radius=8, border_width=1,
                                 border_color=border_c)
            card.pack(fill="x", padx=12, pady=3)

            tr = ctk.CTkFrame(card, fg_color="transparent")
            tr.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(tr, text=f"{scenario.emoji} {scenario.name.upper()}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=TEXT1).pack(side="left")
            ctk.CTkLabel(tr, text=f"{scenario.probability_pct}% olasılık",
                         font=F_TINY, text_color=TEXT2).pack(side="right")

            vr = ctk.CTkFrame(card, fg_color="transparent")
            vr.pack(fill="x", padx=10, pady=(0, 4))
            rc = BUY_C if scenario.return_pct >= 0 else SELL_C
            ctk.CTkLabel(vr, text=f"{scenario.return_pct:+.1f}%",
                         font=("Segoe UI", 18, "bold"),
                         text_color=rc).pack(side="left")
            ctk.CTkLabel(vr, text=f"  {_fmt_money(scenario.profit_loss, currency)}",
                         font=("Segoe UI", 13, "bold"),
                         text_color=rc).pack(side="left")
            ctk.CTkLabel(vr, text=f"Yıllık: {scenario.annualized_return_pct:+.1f}%",
                         font=F_TINY, text_color=TEXT2).pack(side="right")

            ctk.CTkLabel(card, text=scenario.description,
                         font=F_TINY, text_color=TEXT2,
                         wraplength=260, anchor="w", justify="left",
                         ).pack(anchor="w", padx=10, pady=(0, 8))

        # ── Monte Carlo istatistikleri ────────────────────────────────────────
        if mc:
            _section_label(self._results_scroll, "🎲 Monte Carlo (1000 Simülasyon)")

            prob_col = (BUY_C  if mc.positive_prob_pct >= 55
                        else HOLD_C if mc.positive_prob_pct >= 45
                        else SELL_C)
            prob_bg  = (GREEN_DIM if mc.positive_prob_pct >= 55
                        else GOLD_DIM  if mc.positive_prob_pct >= 45
                        else RED_DIM)

            pc = ctk.CTkFrame(self._results_scroll, fg_color=prob_bg,
                               corner_radius=8, border_width=1, border_color=BORDER)
            pc.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(pc,
                         text=f"Kârlı Çıkma Olasılığı: {mc.positive_prob_pct:.1f}%",
                         font=("Segoe UI", 12, "bold"),
                         text_color=prob_col).pack(anchor="w", padx=12, pady=(8, 4))
            pb = ctk.CTkProgressBar(pc, height=8, corner_radius=4,
                                     progress_color=prob_col)
            pb.set(mc.positive_prob_pct / 100)
            pb.pack(fill="x", padx=12, pady=(0, 8))

            mc_f = ctk.CTkFrame(self._results_scroll, fg_color="transparent")
            mc_f.pack(fill="x", padx=12, pady=2)
            for lbl, val in [
                ("5. Persentil (En Kötü %5)",   mc.percentile_5),
                ("25. Persentil",                mc.percentile_25),
                ("50. Persentil (Medyan)",        mc.percentile_50),
                ("75. Persentil",                mc.percentile_75),
                ("95. Persentil (En İyi %5)",    mc.percentile_95),
                ("Ortalama Beklenen Getiri",     mc.mean_return),
            ]:
                _row(mc_f, lbl,
                     f"{val:+.1f}%  ({_fmt_money(amount * val / 100, currency)})",
                     _pct_color(val))

        # ── Tarihsel dönem analizi ────────────────────────────────────────────
        if hist and hist.found:
            _section_label(self._results_scroll, "📅 Tarihsel Benzer Dönemler")
            _row(self._results_scroll, "Analiz Edilen Dönem Sayısı",
                 str(hist.periods_analyzed))
            _row(self._results_scroll, "Ortalama Getiri",
                 f"{hist.avg_return_pct:+.1f}%", _pct_color(hist.avg_return_pct))
            _row(self._results_scroll, "En İyi Dönem",
                 f"{hist.best_return_pct:+.1f}%", BUY_C)
            _row(self._results_scroll, "En Kötü Dönem",
                 f"{hist.worst_return_pct:+.1f}%", SELL_C)
            total = hist.positive_count + hist.negative_count
            if total > 0:
                _row(self._results_scroll, "Pozitif Dönem Oranı",
                     f"{hist.positive_pct:.1f}%  ({hist.positive_count}/{total})",
                     BUY_C if hist.positive_pct >= 55 else SELL_C)

        # ── Risk metrikleri ───────────────────────────────────────────────────
        _section_label(self._results_scroll, "⚠️ Risk Metrikleri")
        _row(self._results_scroll, "Yıllık Volatilite",
             f"{r.annual_volatility_pct:.1f}%")
        _row(self._results_scroll, "Günlük Volatilite",
             f"{r.daily_volatility_pct:.2f}%")
        _row(self._results_scroll, "Sharpe Oranı (Tahmin)",
             f"{r.sharpe_estimate:.2f}",
             BUY_C if r.sharpe_estimate > 1
             else HOLD_C if r.sharpe_estimate > 0
             else SELL_C)
        _row(self._results_scroll, "Max Drawdown (Tarihsel)",
             f"{r.max_drawdown_historical:.1f}%", SELL_C)

        # ── Benchmark karşılaştırma ───────────────────────────────────────────
        _section_label(self._results_scroll, "🏁 Benchmark Karşılaştırması")
        base_ret = r.scenario_base.return_pct if r.scenario_base else 0
        _row(self._results_scroll, f"{r.symbol} — Baz Senaryo",
             f"{base_ret:+.1f}%", _pct_color(base_ret))
        _row(self._results_scroll, "SPY (S&P 500 Beklenen)",
             f"{r.benchmark_spy_return_pct:+.1f}%",
             _pct_color(r.benchmark_spy_return_pct))
        _row(self._results_scroll, "Altın (Beklenen)",
             f"{r.benchmark_gold_return_pct:+.1f}%",
             _pct_color(r.benchmark_gold_return_pct))
        adv = r.vs_spy_advantage_pct
        _row(self._results_scroll, "SPY'e Karşı Avantaj",
             f"{adv:+.1f}% puan", BUY_C if adv > 0 else SELL_C)

        # ── Risk uyarıları ────────────────────────────────────────────────────
        if r.risk_warnings:
            _section_label(self._results_scroll, "🚨 Risk Uyarıları")
            for w in r.risk_warnings:
                wc = ctk.CTkFrame(self._results_scroll, fg_color=RED_DIM,
                                   corner_radius=6, border_width=1,
                                   border_color="#f5c6cb")
                wc.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(wc, text=f"⚠  {w}", font=F_SMALL,
                             text_color=SELL_C, wraplength=270,
                             anchor="w", justify="left").pack(anchor="w", padx=10, pady=6)

        # ── Eğitim notları ────────────────────────────────────────────────────
        if r.education_notes:
            _section_label(self._results_scroll, "💡 Eğitim Notları")
            for note in r.education_notes:
                nc = ctk.CTkFrame(self._results_scroll, fg_color=BLUE_DIM,
                                   corner_radius=6, border_width=1,
                                   border_color="#c8e6fa")
                nc.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(nc, text=note, font=F_TINY,
                             text_color="#0550ae", wraplength=270,
                             anchor="w", justify="left").pack(anchor="w", padx=10, pady=6)

        # Yasal uyarı
        ctk.CTkLabel(
            self._results_scroll,
            text="⚖️ Bu analiz yatırım tavsiyesi değildir. Geçmiş performans "
                 "geleceği garanti etmez.",
            font=("Segoe UI", 8), text_color=TEXT2,
            wraplength=280, justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 8))
