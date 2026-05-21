"""
HedgeFund AI — Desktop GUI
Run:   python -X utf8 app.py
Build: python build.py  →  dist/HedgeFundAI.exe
"""

import sys, os, io, threading, queue, traceback, json
from datetime import datetime
from pathlib import Path

# ── UTF-8 + path fix ────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np
import yaml

from src.data_collector import (
    load_config, fetch_crypto_ohlcv, fetch_stock_ohlcv,
    fetch_fundamentals, fetch_macro_data, fetch_news, fetch_onchain,
)
from src.analyzer import (
    TechnicalAnalyzer, FundamentalAnalyzer, SentimentAnalyzer, OnChainAnalyzer,
    FundamentalResult, OnChainResult,
)
from src.decision_engine import DecisionEngine
from src.risk_manager import RiskManager
from src.alert_system import AlertSystem
from src.multi_timeframe import MultiTimeframeAnalyzer
from src.fear_greed import fetch_fear_greed, fear_greed_signal, format_fear_greed
from backtest.backtester import Backtester

try:
    from src.telegram_bot import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

try:
    from src.scheduler import SignalScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

try:
    from src.price_alerts import PriceAlertManager
    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False

try:
    from src.ui_opportunities import OpportunitiesPage
    OPPORTUNITIES_AVAILABLE = True
except ImportError:
    OPPORTUNITIES_AVAILABLE = False

try:
    from src.ui_portfolio import PortfolioBuilderPage
    PORTFOLIO_AVAILABLE = True
except ImportError:
    PORTFOLIO_AVAILABLE = False

try:
    from src.ui_projection import ProjectionPage
    PROJECTION_AVAILABLE = True
except ImportError:
    PROJECTION_AVAILABLE = False

try:
    from src.ui_widgets import SmartSearchEntry
    SMART_SEARCH_AVAILABLE = True
except ImportError:
    SMART_SEARCH_AVAILABLE = False

# ── Palette (Light / White Theme) ────────────────────────────
BG        = "#f6f8fa"   # ana arka plan
BG_CARD   = "#ffffff"   # kart arka planı
BG_INPUT  = "#eaeef2"   # giriş alanı
SIDEBAR   = "#e8edf2"   # sol panel
BORDER    = "#d0d7de"   # kenarlık
ACCENT    = "#0969da"   # vurgu mavisi
BUY_C     = "#1a7f37"   # yeşil
SELL_C    = "#cf222e"   # kırmızı
HOLD_C    = "#9a6700"   # sarı/amber
TEXT1     = "#1f2328"   # birincil metin
TEXT2     = "#57606a"   # ikincil metin
RED_DIM   = "#ffebe9"   # açık kırmızı arka plan
GREEN_DIM = "#dafbe1"   # açık yeşil arka plan
GOLD_DIM  = "#fff8c5"   # açık sarı arka plan

# ── Fonts ────────────────────────────────────────────────────
F_TITLE = ("Segoe UI", 20, "bold")
F_HEAD  = ("Segoe UI", 13, "bold")
F_BODY  = ("Segoe UI", 11)
F_SMALL = ("Segoe UI", 10)
F_MONO  = ("Consolas",  11)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

CFG = load_config()


def detect_type(sym: str) -> str:
    if "/" in sym: return "crypto"
    if sym.endswith(".IS"): return "bist"
    return "stock"


def run_full_analysis(sym, atype, portfolio):
    """Heavy lifting — runs in background thread, returns dict."""
    ta  = TechnicalAnalyzer()
    fa  = FundamentalAnalyzer()
    sa  = SentimentAnalyzer()
    oca = OnChainAnalyzer()
    de  = DecisionEngine(CFG)
    rm  = RiskManager(CFG)

    macro = fetch_macro_data()
    if atype == "crypto":
        df = fetch_crypto_ohlcv(sym, CFG["data"]["crypto_timeframe"])
    else:
        df = fetch_stock_ohlcv(sym)

    tech = ta.analyze(df, CFG["technical"])

    if atype in ("stock", "bist"):
        fd   = fetch_fundamentals(sym)
        fund = fa.analyze(fd)
    else:
        fd, fund = {}, FundamentalResult(score=50, signals=["N/A for crypto"])

    articles = fetch_news(sym.replace("/USDT","").replace(".IS",""))
    sent     = sa.analyze(articles)

    if atype == "crypto":
        ocd   = fetch_onchain(sym.split("/")[0])
        chain = oca.analyze(ocd)
    else:
        chain = OnChainResult(score=50, signals=["N/A for equities"])

    decision = de.decide(sym, atype, tech, fund, sent, chain, macro)
    sizing   = rm.size_position(
        sym, decision.action, portfolio,
        decision.entry or tech.price or 1,
        decision.stop_loss or (tech.price or 1)*0.95,
        decision.take_profit_1, decision.take_profit_2,
        decision.confidence,
    )
    return dict(
        decision=decision, tech=tech, fund=fund,
        sent=sent, chain=chain, macro=macro,
        sizing=sizing, articles=articles, df=df,
    )


# ══════════════════════════════════════════════════════════════
#  ASSET CARD
# ══════════════════════════════════════════════════════════════
class AssetCard(ctk.CTkFrame):
    def __init__(self, master, symbol, on_analyze, **kw):
        super().__init__(master, fg_color=BG_CARD, corner_radius=10,
                         border_width=1, border_color=BORDER, **kw)
        self.symbol     = symbol
        self.on_analyze = on_analyze
        self._build()

    def _build(self):
        # Symbol row
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10,0))
        self.lbl_sym = ctk.CTkLabel(top, text=self.symbol,
                                    font=F_HEAD, text_color=TEXT1)
        self.lbl_sym.pack(side="left")
        badge_txt = "CRYPTO" if "/" in self.symbol else ("BIST" if self.symbol.endswith(".IS") else "US")
        badge_col = "#ddf4ff" if badge_txt=="CRYPTO" else ("#dafbe1" if badge_txt=="BIST" else "#fff8c5")
        badge_tc  = "#0550ae" if badge_txt=="CRYPTO" else ("#1a7f37" if badge_txt=="BIST" else "#9a6700")
        ctk.CTkLabel(top, text=badge_txt, font=F_SMALL,
                     fg_color=badge_col, corner_radius=4,
                     text_color=badge_tc).pack(side="right")

        # Price
        self.lbl_price = ctk.CTkLabel(self, text="—", font=("Segoe UI",18,"bold"),
                                       text_color=TEXT1)
        self.lbl_price.pack(anchor="w", padx=12, pady=(4,0))

        # Action badge
        self.lbl_action = ctk.CTkLabel(self, text="LOADING...",
                                        font=("Segoe UI",12,"bold"),
                                        fg_color=BG_INPUT, corner_radius=6,
                                        text_color=TEXT2, width=110)
        self.lbl_action.pack(anchor="w", padx=12, pady=(4,0))

        # Confidence bar
        bar_row = ctk.CTkFrame(self, fg_color="transparent")
        bar_row.pack(fill="x", padx=12, pady=(6,0))
        ctk.CTkLabel(bar_row, text="Confidence", font=F_SMALL,
                     text_color=TEXT2).pack(side="left")
        self.lbl_conf = ctk.CTkLabel(bar_row, text="—", font=F_SMALL,
                                      text_color=ACCENT)
        self.lbl_conf.pack(side="right")
        self.pbar = ctk.CTkProgressBar(self, height=6, corner_radius=3)
        self.pbar.set(0)
        self.pbar.pack(fill="x", padx=12, pady=(3,0))

        # Scores
        score_row = ctk.CTkFrame(self, fg_color="transparent")
        score_row.pack(fill="x", padx=12, pady=(6,0))
        for label in ["Tech","Fund","Sent"]:
            f = ctk.CTkFrame(score_row, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkLabel(f, text=label, font=F_SMALL,
                         text_color=TEXT2).pack()
            lbl = ctk.CTkLabel(f, text="—", font=("Segoe UI",10,"bold"),
                               text_color=ACCENT)
            lbl.pack()
            setattr(self, f"lbl_{label.lower()}", lbl)

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=(8,0))

        # Signals
        self.lbl_sig1 = ctk.CTkLabel(self, text="", font=F_SMALL,
                                      text_color=TEXT2, wraplength=200)
        self.lbl_sig1.pack(anchor="w", padx=12, pady=(4,0))
        self.lbl_sig2 = ctk.CTkLabel(self, text="", font=F_SMALL,
                                      text_color=TEXT2, wraplength=200)
        self.lbl_sig2.pack(anchor="w", padx=12, pady=(0,0))

        # Analyze button
        ctk.CTkButton(self, text="Detaylı Analiz →",
                      font=F_SMALL, height=28,
                      fg_color=BG_INPUT, hover_color="#c8d0d8",
                      text_color=ACCENT, corner_radius=6,
                      command=lambda: self.on_analyze(self.symbol)
                      ).pack(fill="x", padx=12, pady=(8,10))

    def set_loading(self):
        self.lbl_price.configure(text="Yükleniyor...")
        self.lbl_action.configure(text="LOADING...", fg_color=BG_INPUT, text_color=TEXT2)
        self.pbar.set(0)
        self.lbl_conf.configure(text="—")

    def set_error(self, msg="Hata"):
        self.lbl_price.configure(text="ERR")
        self.lbl_action.configure(text="ERROR", fg_color=RED_DIM, text_color=SELL_C)
        self.lbl_sig1.configure(text=str(msg)[:50])

    def update_result(self, result: dict):
        d    = result["decision"]
        tech = result["tech"]

        price = tech.price or 0
        if price >= 1000:   p_str = f"${price:,.2f}"
        elif price >= 1:    p_str = f"${price:.4f}"
        else:               p_str = f"${price:.6f}"
        self.lbl_price.configure(text=p_str)

        col_map = {"BUY": (BUY_C, GREEN_DIM), "SELL": (SELL_C, RED_DIM),
                   "HOLD": (HOLD_C, GOLD_DIM)}
        tc, bc = col_map.get(d.action, (TEXT2, BG_INPUT))
        self.lbl_action.configure(text=f"  {d.action}  ",
                                  text_color=tc, fg_color=bc)

        self.pbar.set(d.confidence / 100)
        self.pbar.configure(progress_color=tc)
        self.lbl_conf.configure(text=f"{d.confidence:.0f}%")

        self.lbl_tech.configure(text=f"{d.tech_score:.0f}")
        self.lbl_fund.configure(text=f"{d.fund_score:.0f}")
        self.lbl_sent.configure(text=f"{d.sent_score:.0f}")

        sigs = d.all_signals
        self.lbl_sig1.configure(text=f"▶ {sigs[0]}" if len(sigs) > 0 else "")
        self.lbl_sig2.configure(text=f"▶ {sigs[1]}" if len(sigs) > 1 else "")


# ══════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ══════════════════════════════════════════════════════════════
class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, result_q, on_analyze_cb, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.result_q    = result_q
        self.on_analyze  = on_analyze_cb
        self.cards: dict[str, AssetCard] = {}
        self._build()

    def _build(self):
        # Header bar
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(hdr, text="Piyasa Taraması",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")
        self.lbl_time = ctk.CTkLabel(hdr, text="", font=F_SMALL, text_color=TEXT2)
        self.lbl_time.pack(side="right", padx=8)
        ctk.CTkButton(hdr, text="↻  Tümünü Tara", width=140, height=34,
                      font=("Segoe UI",11,"bold"), fg_color=ACCENT,
                      command=self.refresh_all).pack(side="right")

        # Scrollable card grid
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0,16))

        wl = CFG["watchlist"]
        all_syms = (
            [(s,"crypto")  for s in wl.get("crypto", [])] +
            [(s,"stock")   for s in wl.get("us_stocks", [])] +
            [(s,"bist")    for s in wl.get("bist", [])]
        )

        cols = 3
        for i, (sym, _) in enumerate(all_syms):
            row, col = divmod(i, cols)
            card = AssetCard(self.scroll, sym, self.on_analyze)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.cards[sym] = card
            self.scroll.columnconfigure(col, weight=1)

    def refresh_all(self):
        self.lbl_time.configure(text="Yükleniyor...")
        wl  = CFG["watchlist"]
        syms = (
            [(s,"crypto")  for s in wl.get("crypto", [])] +
            [(s,"stock")   for s in wl.get("us_stocks", [])] +
            [(s,"bist")    for s in wl.get("bist", [])]
        )
        pv = 100_000.0
        for sym, atype in syms:
            if sym in self.cards:
                self.cards[sym].set_loading()
            threading.Thread(
                target=self._worker, args=(sym, atype, pv), daemon=True
            ).start()

    def _worker(self, sym, atype, pv):
        try:
            r = run_full_analysis(sym, atype, pv)
            self.result_q.put(("dashboard", sym, r, None))
        except Exception as e:
            self.result_q.put(("dashboard", sym, None, str(e)))

    def apply_result(self, sym, result, error):
        if sym not in self.cards:
            return
        if error:
            self.cards[sym].set_error(error)
        else:
            self.cards[sym].update_result(result)
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_time.configure(text=f"Son güncelleme: {now}")


# ══════════════════════════════════════════════════════════════
#  ANALYSIS PAGE
# ══════════════════════════════════════════════════════════════
class AnalysisPage(ctk.CTkFrame):
    def __init__(self, master, result_q, alert_sys, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.result_q  = result_q
        self.alert_sys = alert_sys
        self._fig      = None
        self._canvas   = None
        self._build()

    def _build(self):
        # ── Control bar ──────────────────────────────────────
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(ctrl, text="Detaylı Analiz",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")

        self.btn_analyze = ctk.CTkButton(
            ctrl, text="▶  Analiz Et", width=130, height=34,
            font=("Segoe UI",11,"bold"), fg_color=ACCENT,
            command=self._run)
        self.btn_analyze.pack(side="right")

        ctk.CTkLabel(ctrl, text="Portföy $", font=F_BODY,
                     text_color=TEXT2).pack(side="right", padx=(0,4))
        self.ent_pv = ctk.CTkEntry(ctrl, width=110, height=34,
                                    fg_color=BG_INPUT, border_color=BORDER,
                                    font=F_BODY, text_color=TEXT1,
                                    placeholder_text="100000")
        self.ent_pv.pack(side="right", padx=(0,8))

        if SMART_SEARCH_AVAILABLE:
            self.ent_sym = SmartSearchEntry(ctrl, width=220,
                                            placeholder="Sembol ara...")
            self.ent_sym.pack(side="right", padx=(0,8))
        else:
            ctk.CTkLabel(ctrl, text="Sembol", font=F_BODY,
                         text_color=TEXT2).pack(side="right", padx=(0,4))
            self.ent_sym = ctk.CTkEntry(ctrl, width=150, height=34,
                                         fg_color=BG_INPUT, border_color=BORDER,
                                         font=F_BODY, text_color=TEXT1,
                                         placeholder_text="BTC/USDT, AAPL...")
            self.ent_sym.pack(side="right", padx=(0,8))

        # ── Progress bar ──────────────────────────────────────
        self.pbar = ctk.CTkProgressBar(self, height=3, corner_radius=0)
        self.pbar.set(0)
        self.pbar.pack(fill="x", padx=0, pady=0)

        # ── Main split: chart left | results right ────────────
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(8,16))
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # Chart area
        self.chart_frame = ctk.CTkFrame(split, fg_color=BG_CARD,
                                         corner_radius=10, border_width=1,
                                         border_color=BORDER)
        self.chart_frame.grid(row=0, column=0, sticky="nsew", padx=(0,8))

        self.chart_placeholder = ctk.CTkLabel(
            self.chart_frame,
            text="Sembol gir ve 'Analiz Et'e tıkla",
            font=F_BODY, text_color=TEXT2)
        self.chart_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # Results panel
        self.results_frame = ctk.CTkScrollableFrame(
            split, fg_color=BG_CARD, corner_radius=10,
            border_width=1, border_color=BORDER)
        self.results_frame.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(self.results_frame,
                     text="Analiz sonucu burada görünecek",
                     font=F_BODY, text_color=TEXT2).pack(pady=40)

    def set_symbol(self, sym):
        if SMART_SEARCH_AVAILABLE and isinstance(self.ent_sym, SmartSearchEntry):
            self.ent_sym.set(sym)
        else:
            self.ent_sym.delete(0, "end")
            self.ent_sym.insert(0, sym)

    def _run(self):
        sym = self.ent_sym.get().strip().upper()
        if not sym:
            messagebox.showwarning("Uyarı", "Sembol girin!")
            return
        pv_txt = self.ent_pv.get().strip()
        pv = float(pv_txt) if pv_txt else 100_000.0

        self.btn_analyze.configure(state="disabled", text="Analiz ediliyor...")
        self.pbar.configure(mode="indeterminate")
        self.pbar.start()

        atype = detect_type(sym)
        threading.Thread(
            target=self._worker, args=(sym, atype, pv), daemon=True
        ).start()

    def _worker(self, sym, atype, pv):
        try:
            r = run_full_analysis(sym, atype, pv)
            self.result_q.put(("analysis", sym, r, None))
        except Exception as e:
            self.result_q.put(("analysis", sym, None, traceback.format_exc()))

    def apply_result(self, sym, result, error):
        self.pbar.stop()
        self.pbar.configure(mode="determinate")
        self.pbar.set(1 if not error else 0)
        self.btn_analyze.configure(state="normal", text="▶  Analiz Et")

        if error:
            messagebox.showerror("Hata", f"{sym} analiz edilemedi:\n{error[:300]}")
            return

        self.alert_sys.check_and_alert(
            sym, result["tech"], result["sent"],
            {}, result["macro"]
        )
        self._draw_chart(result)
        self._draw_results(sym, result)

    # ── Chart ─────────────────────────────────────────────────
    def _draw_chart(self, r):
        df   = r["df"]
        tech = r["tech"]

        if self._canvas:
            self._canvas.get_tk_widget().destroy()
        if self._fig:
            plt.close(self._fig)
        self.chart_placeholder.place_forget()

        plt.style.use("default")
        self._fig = plt.Figure(figsize=(7, 6), facecolor=BG_CARD)
        gs = gridspec.GridSpec(3, 1, figure=self._fig,
                               height_ratios=[3, 1, 1], hspace=0.05)
        ax1 = self._fig.add_subplot(gs[0])
        ax2 = self._fig.add_subplot(gs[1], sharex=ax1)
        ax3 = self._fig.add_subplot(gs[2], sharex=ax1)

        close = df["close"].astype(float)
        x     = range(len(close))

        # Price
        ax1.plot(x, close, color=ACCENT, linewidth=1.5, label="Price", zorder=3)
        if tech.ema20:
            ax1.plot(x, df["close"].ewm(span=20, adjust=False).mean(),
                     color="#0550ae", linewidth=1, label="EMA20", alpha=0.9)
        if tech.ema50:
            ax1.plot(x, df["close"].ewm(span=50, adjust=False).mean(),
                     color="#9a6700", linewidth=1, label="EMA50", alpha=0.9)
        if tech.ema200:
            ax1.plot(x, df["close"].ewm(span=200, adjust=False).mean(),
                     color="#cf222e", linewidth=1, label="EMA200", alpha=0.9)

        bb_p  = CFG["technical"].get("bb_period", 20)
        sma   = close.rolling(bb_p).mean()
        std   = close.rolling(bb_p).std()
        ax1.fill_between(x, (sma - 2*std), (sma + 2*std),
                         alpha=0.1, color=ACCENT, label="BB")
        ax1.legend(fontsize=7, loc="upper left", framealpha=0.6)
        ax1.set_facecolor(BG)
        ax1.tick_params(colors=TEXT2, labelsize=7)
        ax1.grid(color=BORDER, linewidth=0.4, alpha=0.8)
        ax1.spines[:].set_color(BORDER)
        ax1.set_ylabel("Price", color=TEXT2, fontsize=8)
        plt.setp(ax1.get_xticklabels(), visible=False)

        # RSI
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        ax2.plot(x, rsi, color=ACCENT, linewidth=1)
        ax2.axhline(70, color=SELL_C, linewidth=0.7, linestyle="--", alpha=0.7)
        ax2.axhline(30, color=BUY_C,  linewidth=0.7, linestyle="--", alpha=0.7)
        ax2.fill_between(x, rsi, 70, where=(rsi >= 70),
                         color=SELL_C, alpha=0.12)
        ax2.fill_between(x, rsi, 30, where=(rsi <= 30),
                         color=BUY_C,  alpha=0.12)
        ax2.set_ylim(0, 100)
        ax2.set_yticks([30, 70])
        ax2.set_facecolor(BG)
        ax2.tick_params(colors=TEXT2, labelsize=7)
        ax2.grid(color=BORDER, linewidth=0.4, alpha=0.8)
        ax2.spines[:].set_color(BORDER)
        ax2.set_ylabel("RSI", color=TEXT2, fontsize=8)
        plt.setp(ax2.get_xticklabels(), visible=False)

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd  = ema12 - ema26
        sig   = macd.ewm(span=9, adjust=False).mean()
        hist  = macd - sig
        colors_hist = [BUY_C if v >= 0 else SELL_C for v in hist]
        ax3.bar(x, hist, color=colors_hist, alpha=0.6, width=0.8)
        ax3.plot(x, macd,  color=ACCENT, linewidth=0.9)
        ax3.plot(x, sig,   color="#9a6700", linewidth=0.9)
        ax3.axhline(0, color=BORDER, linewidth=0.6)
        ax3.set_facecolor(BG)
        ax3.tick_params(colors=TEXT2, labelsize=7)
        ax3.grid(color=BORDER, linewidth=0.4, alpha=0.8)
        ax3.spines[:].set_color(BORDER)
        ax3.set_ylabel("MACD", color=TEXT2, fontsize=8)

        self._fig.patch.set_facecolor(BG_CARD)
        self._fig.subplots_adjust(left=0.08, right=0.97, top=0.97, bottom=0.04)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    # ── Results panel ─────────────────────────────────────────
    def _draw_results(self, sym, r):
        for w in self.results_frame.winfo_children():
            w.destroy()

        d    = r["decision"]
        tech = r["tech"]
        sz   = r["sizing"]

        def section(title):
            ctk.CTkLabel(self.results_frame, text=title,
                         font=("Segoe UI",11,"bold"), text_color=ACCENT
                         ).pack(anchor="w", padx=12, pady=(12,2))
            ctk.CTkFrame(self.results_frame, height=1, fg_color=BORDER
                         ).pack(fill="x", padx=12)

        try:
            from src.ui_widgets import tip as _tip
        except ImportError:
            def _tip(w, k): pass

        def row(label, value, val_color=TEXT1):
            f = ctk.CTkFrame(self.results_frame, fg_color="transparent")
            f.pack(fill="x", padx=12, pady=1)
            lbl_w = ctk.CTkLabel(f, text=label, font=F_SMALL,
                                 text_color=TEXT2, width=110, anchor="w")
            lbl_w.pack(side="left")
            _tip(lbl_w, label)
            ctk.CTkLabel(f, text=str(value), font=F_SMALL,
                         text_color=val_color).pack(side="right")

        # Decision
        section("KARAR")
        col = {"BUY": BUY_C, "SELL": SELL_C, "HOLD": HOLD_C}.get(d.action, TEXT1)
        action_lbl = ctk.CTkLabel(
            self.results_frame,
            text=f"  {d.action}  —  {d.confidence:.0f}% güven",
            font=("Segoe UI",16,"bold"),
            fg_color={"BUY":GREEN_DIM,"SELL":RED_DIM,"HOLD":GOLD_DIM}.get(d.action,BG_INPUT),
            corner_radius=8, text_color=col
        )
        action_lbl.pack(fill="x", padx=12, pady=6)
        _tip(action_lbl, d.action)

        # Scores
        section("SKORLAR")
        row("Teknik",     f"{d.tech_score:.0f}/100")
        row("Fundamental",f"{d.fund_score:.0f}/100")
        row("Sentiment",  f"{d.sent_score:.0f}/100")
        row("Makro",      f"{d.macro_score:.0f}/100")
        if d.asset_type == "crypto":
            row("On-Chain", f"{d.chain_score:.0f}/100")
        row("KOMPOZİT",   f"{d.composite:.1f}/100", ACCENT)

        # Price levels
        section("FİYAT SEVİYELERİ")

        def fmt(p):
            if p is None: return "—"
            try:
                p = float(p)
                return f"{p:,.2f}" if p >= 1 else f"{p:.6f}"
            except: return "—"

        row("Güncel Fiyat",  fmt(tech.price))
        row("Giriş",         fmt(d.entry))
        row("Stop-Loss",     fmt(d.stop_loss),     SELL_C)
        row("Take-Profit 1", fmt(d.take_profit_1), BUY_C)
        row("Take-Profit 2", fmt(d.take_profit_2), BUY_C)
        row("Take-Profit 3", fmt(d.take_profit_3), BUY_C)

        # Pozisyon
        section("POZİSYON BOYUTU")
        row("Miktar",       f"{sz.units:,.6g}")
        row("Dolar Değeri", f"${sz.dollar_amount:,.2f}")
        row("Risk Tutarı",  f"${sz.risk_amount:,.2f}")
        row("R:R (TP1)",    f"1:{sz.risk_reward_1}")
        row("Half-Kelly",   f"{sz.kelly_fraction*100:.1f}%")

        # Technical
        section("TEKNİK İNDİKATÖRLER")
        row("RSI (14)",    tech.rsi,
            BUY_C if (tech.rsi or 50) < 30 else SELL_C if (tech.rsi or 50) > 70 else TEXT1)
        row("MACD Hist",   f"{tech.macd_histogram:.4g}" if tech.macd_histogram else "—")
        row("EMA 20",      fmt(tech.ema20))
        row("EMA 50",      fmt(tech.ema50))
        row("EMA 200",     fmt(tech.ema200))
        row("BB Pozisyon", f"{(tech.bb_pct or 0)*100:.1f}%")
        row("Hacim Oranı", f"{tech.volume_ratio}x")
        row("Trend",       tech.trend,
            BUY_C if tech.trend=="UPTREND" else SELL_C if tech.trend=="DOWNTREND" else HOLD_C)
        row("Kırılım",     "EVET ✔" if tech.breakout else "Hayır",
            BUY_C if tech.breakout else TEXT2)

        # Signals
        section("SİNYALLER")
        for sig in d.all_signals:
            col_s = BUY_C if any(w in sig.lower() for w in ["buy","bullish","oversold","outflow","breakout"]) \
                    else SELL_C if any(w in sig.lower() for w in ["sell","bearish","overbought","inflow"]) \
                    else TEXT2
            ctk.CTkLabel(self.results_frame,
                         text=f"▶ {sig}", font=F_SMALL,
                         text_color=col_s, anchor="w", wraplength=260
                         ).pack(anchor="w", padx=12, pady=1)

        # Scenarios
        section("SENARYO ANALİZİ")
        for title, txt in [("📊 BAZ", d.base_scenario),
                            ("⚠️  RİSK", d.risk_scenario),
                            ("💀 KUĞU", d.black_swan_scenario)]:
            ctk.CTkLabel(self.results_frame, text=title,
                         font=("Segoe UI",10,"bold"), text_color=HOLD_C
                         ).pack(anchor="w", padx=12, pady=(6,1))
            ctk.CTkLabel(self.results_frame, text=txt,
                         font=F_SMALL, text_color=TEXT2,
                         wraplength=260, anchor="w", justify="left"
                         ).pack(anchor="w", padx=16, pady=(0,4))

        # Macro
        section("MAKRO")
        for k, v in r["macro"].items():
            cur = v.get("current","?")
            chg = v.get("change_1d")
            chg_str = f"  ({chg:+.2f}%)" if chg is not None else ""
            row(k, f"{cur}{chg_str}",
                BUY_C if chg and chg > 0 else SELL_C if chg and chg < 0 else TEXT1)


# ══════════════════════════════════════════════════════════════
#  BACKTEST PAGE
# ══════════════════════════════════════════════════════════════
class BacktestPage(ctk.CTkFrame):
    def __init__(self, master, result_q, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.result_q = result_q
        self._fig = None
        self._canvas = None
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(hdr, text="Backtest Motoru",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color=BG_CARD,
                             corner_radius=10, border_width=1, border_color=BORDER)
        ctrl.pack(fill="x", padx=20, pady=(0,12))

        fields = ctk.CTkFrame(ctrl, fg_color="transparent")
        fields.pack(fill="x", padx=16, pady=12)

        def add_field(parent, label, default, width=130):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=8)
            ctk.CTkLabel(f, text=label, font=F_SMALL, text_color=TEXT2).pack(anchor="w")
            e = ctk.CTkEntry(f, width=width, height=32, fg_color=BG_INPUT,
                              border_color=BORDER, font=F_BODY,
                              text_color=TEXT1, placeholder_text=default)
            e.pack()
            return e

        # Sembol alanı — SmartSearch varsa onu kullan
        if SMART_SEARCH_AVAILABLE:
            sym_f = ctk.CTkFrame(fields, fg_color="transparent")
            sym_f.pack(side="left", padx=8)
            ctk.CTkLabel(sym_f, text="Sembol", font=F_SMALL, text_color=TEXT2).pack(anchor="w")
            self.ent_sym = SmartSearchEntry(sym_f, width=200,
                                            placeholder="Sembol ara...")
            self.ent_sym.pack()
        else:
            self.ent_sym = add_field(fields, "Sembol", "AAPL", 140)

        self.ent_start = add_field(fields, "Başlangıç",    "2023-01-01", 120)
        self.ent_end   = add_field(fields, "Bitiş",        "2024-12-31", 120)
        self.ent_cap   = add_field(fields, "Sermaye ($)",  "100000",     110)

        self.btn_run = ctk.CTkButton(
            fields, text="▶  Backtest Çalıştır",
            width=160, height=32, font=("Segoe UI",11,"bold"),
            fg_color=ACCENT, command=self._run)
        ctk.CTkFrame(fields, fg_color="transparent", width=20).pack(side="left")
        self.btn_run.pack(side="left", padx=8, pady=14)

        self.pbar = ctk.CTkProgressBar(ctrl, height=3, corner_radius=0)
        self.pbar.set(0)
        self.pbar.pack(fill="x")

        # Results
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=20, pady=(0,16))
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)
        split.rowconfigure(0, weight=1)

        # Metrics panel
        self.metrics_frame = ctk.CTkScrollableFrame(
            split, fg_color=BG_CARD, corner_radius=10,
            border_width=1, border_color=BORDER)
        self.metrics_frame.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        ctk.CTkLabel(self.metrics_frame,
                     text="Backtest sonuçları burada görünecek",
                     font=F_BODY, text_color=TEXT2).pack(pady=40)

        # Equity curve
        self.chart_frame = ctk.CTkFrame(
            split, fg_color=BG_CARD, corner_radius=10,
            border_width=1, border_color=BORDER)
        self.chart_frame.grid(row=0, column=1, sticky="nsew")
        self._chart_ph = ctk.CTkLabel(self.chart_frame,
                                       text="Equity curve burada görünecek",
                                       font=F_BODY, text_color=TEXT2)
        self._chart_ph.place(relx=0.5, rely=0.5, anchor="center")

    def _run(self):
        sym   = self.ent_sym.get().strip().upper() or "AAPL"
        start = self.ent_start.get().strip() or "2023-01-01"
        end   = self.ent_end.get().strip()   or "2024-12-31"
        cap   = float(self.ent_cap.get().strip() or 100000)
        atype = detect_type(sym)

        self.btn_run.configure(state="disabled", text="Çalışıyor...")
        self.pbar.configure(mode="indeterminate"); self.pbar.start()
        threading.Thread(
            target=self._worker, args=(sym, atype, start, end, cap), daemon=True
        ).start()

    def _worker(self, sym, atype, start, end, cap):
        try:
            import yfinance as yf
            if atype == "crypto":
                df = fetch_crypto_ohlcv(sym, "1d", limit=730)
            else:
                t  = yf.Ticker(sym)
                df = t.history(period="3y", interval="1d")
                df = df[["Open","High","Low","Close","Volume"]].rename(columns=str.lower)
            bt  = Backtester()
            res = bt.run(df, sym, start, end, cap)
            self.result_q.put(("backtest", sym, res, None))
        except Exception as e:
            self.result_q.put(("backtest", sym, None, traceback.format_exc()))

    def apply_result(self, sym, result, error):
        self.pbar.stop()
        self.pbar.configure(mode="determinate")
        self.pbar.set(1 if not error else 0)
        self.btn_run.configure(state="normal", text="▶  Backtest Çalıştır")
        if error:
            messagebox.showerror("Hata", f"Backtest başarısız:\n{error[:400]}")
            return
        self._show_metrics(result)
        self._draw_equity(result)

    def _show_metrics(self, r):
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        def row(label, value, val_color=TEXT1):
            f = ctk.CTkFrame(self.metrics_frame, fg_color="transparent")
            f.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(f, text=label, font=F_SMALL,
                         text_color=TEXT2, width=150, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=str(value), font=("Segoe UI",11,"bold"),
                         text_color=val_color).pack(side="right")

        ctk.CTkLabel(self.metrics_frame, text=f"Backtest: {r.symbol}",
                     font=F_HEAD, text_color=TEXT1).pack(anchor="w", padx=12, pady=(12,4))
        ctk.CTkLabel(self.metrics_frame,
                     text=f"{r.start}  →  {r.end}",
                     font=F_SMALL, text_color=TEXT2).pack(anchor="w", padx=12)
        ctk.CTkFrame(self.metrics_frame, height=1, fg_color=BORDER
                     ).pack(fill="x", padx=12, pady=8)

        ret_col = BUY_C if r.total_return_pct > 0 else SELL_C
        row("Başlangıç Sermayesi", f"${r.initial_capital:,.2f}")
        row("Final Sermaye",       f"${r.final_capital:,.2f}")
        row("Toplam Getiri",       f"{r.total_return_pct:+.2f}%", ret_col)
        row("Yıllık Getiri",       f"{r.annual_return_pct:+.2f}%", ret_col)
        row("Max Drawdown",        f"{r.max_drawdown_pct:.2f}%", SELL_C)
        row("Sharpe Oranı",        f"{r.sharpe_ratio:.3f}",
            BUY_C if r.sharpe_ratio > 1 else HOLD_C if r.sharpe_ratio > 0 else SELL_C)
        row("Sortino Oranı",       f"{r.sortino_ratio:.3f}")

        ctk.CTkFrame(self.metrics_frame, height=1, fg_color=BORDER
                     ).pack(fill="x", padx=12, pady=8)
        row("Toplam İşlem",        str(r.total_trades))
        row("Kazanan",             str(r.winning_trades), BUY_C)
        row("Kaybeden",            str(r.losing_trades),  SELL_C)
        row("Kazanma Oranı",       f"{r.win_rate_pct:.1f}%",
            BUY_C if r.win_rate_pct >= 50 else SELL_C)
        row("Ort. Kazanç",         f"{r.avg_win_pct:+.2f}%", BUY_C)
        row("Ort. Kayıp",          f"{r.avg_loss_pct:+.2f}%",  SELL_C)
        row("Kâr Faktörü",         f"{r.profit_factor:.2f}",
            BUY_C if r.profit_factor > 1.5 else HOLD_C if r.profit_factor > 1 else SELL_C)

    def _draw_equity(self, r):
        if self._canvas:
            self._canvas.get_tk_widget().destroy()
        if self._fig:
            plt.close(self._fig)
        self._chart_ph.place_forget()

        plt.style.use("default")
        self._fig = plt.Figure(figsize=(7, 4.5), facecolor=BG_CARD)
        ax = self._fig.add_subplot(111)

        eq = r.equity_curve
        ax.plot(range(len(eq)), eq, color=ACCENT, linewidth=1.5, label="Strateji")
        ax.axhline(r.initial_capital, color=TEXT2, linewidth=0.8,
                   linestyle="--", alpha=0.6, label="Başlangıç")

        # Drawdown shading
        roll_max = eq.cummax()
        dd_mask  = eq < roll_max
        ax.fill_between(range(len(eq)), eq, roll_max,
                        where=dd_mask, color=SELL_C, alpha=0.12, label="Drawdown")

        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT2, labelsize=8)
        ax.grid(color=BORDER, linewidth=0.4, alpha=0.8)
        ax.spines[:].set_color(BORDER)
        ax.set_ylabel("Portföy Değeri ($)", color=TEXT2, fontsize=9)
        ax.set_xlabel("İşlem Günü", color=TEXT2, fontsize=9)
        ax.legend(fontsize=8, framealpha=0.6)
        ax.set_title(f"{r.symbol} Equity Curve", color=TEXT1, fontsize=10, pad=8)
        self._fig.patch.set_facecolor(BG_CARD)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasTkAgg(self._fig, master=self.chart_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)


# ══════════════════════════════════════════════════════════════
#  ALERTS PAGE
# ══════════════════════════════════════════════════════════════
class AlertsPage(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._build()
        self._count = 0

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(hdr, text="Uyarı Merkezi",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")
        ctk.CTkButton(hdr, text="Temizle", width=90, height=32,
                      fg_color=BG_INPUT, hover_color="#c8d0d8",
                      text_color=SELL_C, font=F_BODY,
                      command=self._clear).pack(side="right")

        self.log = ctk.CTkTextbox(
            self, fg_color=BG_CARD, corner_radius=10,
            border_width=1, border_color=BORDER,
            font=F_MONO, text_color=TEXT1, state="disabled")
        self.log.pack(fill="both", expand=True, padx=20, pady=(0,16))

        self._write("── HedgeFund AI Alert Log ─────────────────────────────\n", TEXT2)
        self._write("Analiz çalıştırıldıkça uyarılar burada görünecek.\n\n", TEXT2)

    def _write(self, text, color=TEXT1):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.configure(state="disabled")
        self.log.see("end")

    def add_alert(self, alert_obj):
        self._count += 1
        col = {"CRITICAL": SELL_C, "WARNING": HOLD_C, "INFO": BUY_C}.get(
            alert_obj.severity, TEXT1)
        icon = {"CRITICAL": "🚨", "WARNING": "⚠️ ", "INFO": "ℹ️ "}.get(
            alert_obj.severity, "")
        txt = f"{icon} [{alert_obj.timestamp}] {alert_obj.symbol} | {alert_obj.type}\n   {alert_obj.message}\n\n"
        self._write(txt, col)

    def _clear(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._write("── Log temizlendi ──────────────────────────────────────\n\n", TEXT2)
        self._count = 0


# ══════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ══════════════════════════════════════════════════════════════
class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self._entries = {}
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(hdr, text="Ayarlar",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")
        ctk.CTkButton(hdr, text="💾  Kaydet", width=110, height=34,
                      font=("Segoe UI",11,"bold"), fg_color=BUY_C,
                      text_color="#ffffff", hover_color="#2ea043",
                      command=self._save).pack(side="right")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0,16))

        cfg = load_config()

        def section(title):
            ctk.CTkLabel(scroll, text=title, font=F_HEAD,
                         text_color=ACCENT).pack(anchor="w", pady=(16,4))
            ctk.CTkFrame(scroll, height=1, fg_color=BORDER).pack(fill="x")

        def field(parent, label, key, value, show=""):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=label, font=F_BODY,
                         text_color=TEXT2, width=180, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=400, height=32, fg_color=BG_INPUT,
                              border_color=BORDER, font=F_MONO,
                              text_color=TEXT1, show=show)
            e.insert(0, str(value) if value else "")
            e.pack(side="left", padx=8)
            self._entries[key] = e

        # API Keys
        section("🔑  API Anahtarları")
        keys = cfg.get("api_keys", {})
        field(scroll, "Binance API Key",    "binance_api_key", keys.get("binance_api_key",""))
        field(scroll, "Binance Secret",     "binance_secret",  keys.get("binance_secret",""), show="●")
        field(scroll, "Finnhub",            "finnhub",         keys.get("finnhub",""))
        field(scroll, "NewsAPI",            "newsapi",         keys.get("newsapi",""))
        field(scroll, "FRED",               "fred",            keys.get("fred",""))
        field(scroll, "Glassnode",          "glassnode",       keys.get("glassnode",""))

        # Risk
        section("⚖️   Risk Yönetimi")
        risk = cfg.get("risk", {})
        field(scroll, "Max Portföy Riski (%)",  "max_portfolio_risk_pct",  risk.get("max_portfolio_risk_pct", 2.0))
        field(scroll, "Max Pozisyon (%)",        "max_single_position_pct", risk.get("max_single_position_pct",10.0))
        field(scroll, "Varsayılan Stop-Loss (%)", "default_stop_loss_pct",  risk.get("default_stop_loss_pct",5.0))

        # Backtest
        section("📈  Backtest Varsayılanları")
        bt = cfg.get("backtest", {})
        field(scroll, "Başlangıç Tarihi",   "bt_start",   bt.get("default_start","2023-01-01"))
        field(scroll, "Bitiş Tarihi",       "bt_end",     bt.get("default_end","2024-12-31"))
        field(scroll, "Başlangıç Sermayesi","bt_capital", bt.get("initial_capital",100000))

    def _save(self):
        try:
            cfg = load_config()
            e   = self._entries
            def g(k, default=""):
                return e[k].get().strip() if k in e else default

            cfg["api_keys"]["binance_api_key"] = g("binance_api_key")
            cfg["api_keys"]["binance_secret"]  = g("binance_secret")
            cfg["api_keys"]["finnhub"]         = g("finnhub")
            cfg["api_keys"]["newsapi"]         = g("newsapi")
            cfg["api_keys"]["fred"]            = g("fred")
            cfg["api_keys"]["glassnode"]       = g("glassnode")

            cfg["risk"]["max_portfolio_risk_pct"]  = float(g("max_portfolio_risk_pct", 2))
            cfg["risk"]["max_single_position_pct"] = float(g("max_single_position_pct",10))
            cfg["risk"]["default_stop_loss_pct"]   = float(g("default_stop_loss_pct",5))

            cfg["backtest"]["default_start"]    = g("bt_start","2023-01-01")
            cfg["backtest"]["default_end"]      = g("bt_end","2024-12-31")
            cfg["backtest"]["initial_capital"]  = float(g("bt_capital",100000))

            from src.config_loader import save_settings
            save_settings(cfg, ROOT / "config" / "settings.yaml")

            messagebox.showinfo("Kaydedildi", "Ayarlar başarıyla kaydedildi.")
        except Exception as ex:
            messagebox.showerror("Hata", f"Kaydetme hatası:\n{ex}")


# ══════════════════════════════════════════════════════════════
#  BOT & SCHEDULER PAGE
# ══════════════════════════════════════════════════════════════
class BotPage(ctk.CTkFrame):
    def __init__(self, master, app_ref, **kw):
        super().__init__(master, fg_color=BG, **kw)
        self.app = app_ref
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16,8))
        ctk.CTkLabel(hdr, text="Telegram Bot & Zamanlayıcı",
                     font=F_TITLE, text_color=TEXT1).pack(side="left")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0,16))

        # ── Bot Status ────────────────────────────────────────
        self._section(scroll, "📱 Telegram Bot Durumu")
        status_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8,
                                    border_width=1, border_color=BORDER)
        status_card.pack(fill="x", pady=6)
        cfg = load_config()
        tg_cfg = cfg.get("telegram", {})
        token  = tg_cfg.get("bot_token","")
        chat   = tg_cfg.get("chat_id","")
        has_token = token and not token.startswith("YOUR_")
        has_chat  = chat  and not chat.startswith("YOUR_")

        self.lbl_bot_status = ctk.CTkLabel(
            status_card,
            text="🟢 Bot Aktif" if (has_token and has_chat) else "🔴 Bot Yapılandırılmamış",
            font=("Segoe UI",13,"bold"),
            text_color=BUY_C if (has_token and has_chat) else SELL_C
        )
        self.lbl_bot_status.pack(anchor="w", padx=16, pady=(10,4))

        steps = [
            ("1.", "@BotFather'a yaz → /newbot → token al"),
            ("2.", "Bota /start yaz → Chat ID'ni öğren"),
            ("3.", "Ayarlar sekmesine gir → Telegram bölümüne ekle"),
            ("4.", "EXE'yi yeniden başlat → Bot hazır!"),
        ]
        if not has_token:
            for n, txt in steps:
                r = ctk.CTkFrame(status_card, fg_color="transparent")
                r.pack(anchor="w", padx=16, pady=1)
                ctk.CTkLabel(r, text=n, font=("Segoe UI",10,"bold"),
                             text_color=ACCENT, width=20).pack(side="left")
                ctk.CTkLabel(r, text=txt, font=F_SMALL,
                             text_color=TEXT2).pack(side="left", padx=4)
        ctk.CTkFrame(status_card, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=8)

        # Test button
        btn_row = ctk.CTkFrame(status_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0,10))
        ctk.CTkButton(btn_row, text="📤 Test Mesajı Gönder",
                      width=180, height=32, fg_color=ACCENT,
                      command=self._send_test).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_row, text="🔄 Durumu Yenile",
                      width=140, height=32, fg_color=BG_INPUT,
                      hover_color="#c8d0d8", text_color=TEXT2,
                      command=self._refresh_status).pack(side="left")

        # ── Telegram Settings ─────────────────────────────────
        self._section(scroll, "⚙️ Telegram Ayarları")
        cfg_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8,
                                 border_width=1, border_color=BORDER)
        cfg_card.pack(fill="x", pady=6)

        self._tg_entries = {}
        for label, key, default, show in [
            ("Bot Token",    "bot_token", tg_cfg.get("bot_token",""), "●"),
            ("Chat ID",      "chat_id",   tg_cfg.get("chat_id",""),   ""),
            ("Min. Güven %", "min_confidence", str(tg_cfg.get("min_confidence",60)), ""),
        ]:
            r = ctk.CTkFrame(cfg_card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(r, text=label, font=F_BODY, text_color=TEXT2,
                         width=130, anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=300, height=30, fg_color=BG_INPUT,
                              border_color=BORDER, font=F_MONO,
                              text_color=TEXT1, show=show if show else "")
            if default and not str(default).startswith("YOUR_"):
                e.insert(0, str(default))
            e.pack(side="left", padx=8)
            self._tg_entries[key] = e

        toggle_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
        toggle_row.pack(fill="x", padx=16, pady=(4,10))
        self._sw_buy  = ctk.CTkSwitch(toggle_row, text="BUY sinyali gönder",
                                       font=F_SMALL, text_color=TEXT2,
                                       progress_color=BUY_C)
        self._sw_buy.pack(side="left", padx=(0,16))
        if tg_cfg.get("send_on_buy", True): self._sw_buy.select()

        self._sw_sell = ctk.CTkSwitch(toggle_row, text="SELL sinyali gönder",
                                       font=F_SMALL, text_color=TEXT2,
                                       progress_color=SELL_C)
        self._sw_sell.pack(side="left", padx=(0,16))
        if tg_cfg.get("send_on_sell", True): self._sw_sell.select()

        self._sw_hold = ctk.CTkSwitch(toggle_row, text="HOLD sinyali gönder",
                                       font=F_SMALL, text_color=TEXT2,
                                       progress_color=HOLD_C)
        self._sw_hold.pack(side="left")

        ctk.CTkButton(cfg_card, text="💾 Kaydet", width=100, height=30,
                      fg_color=BUY_C, text_color="#ffffff",
                      command=self._save_tg_cfg).pack(anchor="e", padx=16, pady=(0,10))

        # ── Scheduler ─────────────────────────────────────────
        self._section(scroll, "⏰ Zamanlayıcı")
        sched_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8,
                                   border_width=1, border_color=BORDER)
        sched_card.pack(fill="x", pady=6)

        sched_cfg = cfg.get("scheduler", {})
        self._sched_entries = {}
        sched_fields = [
            ("Sabah Brifing",   "morning_briefing",  sched_cfg.get("morning_briefing","08:30")),
            ("Piyasa Açılışı",  "market_open_scan",  sched_cfg.get("market_open_scan","09:30")),
            ("Öğle Taraması",   "midday_scan",        sched_cfg.get("midday_scan","12:00")),
            ("Kapanış Uyarısı", "preclose_alert",     sched_cfg.get("preclose_alert","16:30")),
            ("Akşam Özeti",     "evening_summary",    sched_cfg.get("evening_summary","18:00")),
        ]
        for row_i, (label, key, default) in enumerate(sched_fields):
            r = ctk.CTkFrame(sched_card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(r, text=label, font=F_BODY, text_color=TEXT2,
                         width=160, anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=90, height=30, fg_color=BG_INPUT,
                              border_color=BORDER, font=F_MONO,
                              text_color=TEXT1, placeholder_text="HH:MM")
            e.insert(0, default)
            e.pack(side="left", padx=8)
            ctk.CTkLabel(r, text="(saat:dakika)", font=F_SMALL,
                         text_color=TEXT2).pack(side="left")
            self._sched_entries[key] = e

        r_tz = ctk.CTkFrame(sched_card, fg_color="transparent")
        r_tz.pack(fill="x", padx=16, pady=3)
        ctk.CTkLabel(r_tz, text="Zaman Dilimi", font=F_BODY, text_color=TEXT2,
                     width=160, anchor="w").pack(side="left")
        self._ent_tz = ctk.CTkEntry(r_tz, width=200, height=30,
                                     fg_color=BG_INPUT, border_color=BORDER,
                                     font=F_MONO, text_color=TEXT1)
        self._ent_tz.insert(0, sched_cfg.get("timezone","Europe/Istanbul"))
        self._ent_tz.pack(side="left", padx=8)

        ctk.CTkButton(sched_card, text="💾 Kaydet & Yeniden Başlat",
                      width=200, height=30, fg_color=ACCENT,
                      command=self._save_scheduler).pack(anchor="e", padx=16, pady=(4,10))

        # ── Fiyat Alarmı Kur ──────────────────────────────────
        self._section(scroll, "🎯 Fiyat Alarmı Kur")
        alarm_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8,
                                   border_width=1, border_color=BORDER)
        alarm_card.pack(fill="x", pady=6)

        alarm_row = ctk.CTkFrame(alarm_card, fg_color="transparent")
        alarm_row.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(alarm_row, text="Sembol", font=F_SMALL, text_color=TEXT2).pack(side="left")
        self._ent_alarm_sym = ctk.CTkEntry(alarm_row, width=130, height=30,
                                            fg_color=BG_INPUT, border_color=BORDER,
                                            font=F_BODY, text_color=TEXT1,
                                            placeholder_text="BTC/USDT")
        self._ent_alarm_sym.pack(side="left", padx=(4,12))

        ctk.CTkLabel(alarm_row, text="Fiyat", font=F_SMALL, text_color=TEXT2).pack(side="left")
        self._ent_alarm_price = ctk.CTkEntry(alarm_row, width=110, height=30,
                                              fg_color=BG_INPUT, border_color=BORDER,
                                              font=F_BODY, text_color=TEXT1,
                                              placeholder_text="80000")
        self._ent_alarm_price.pack(side="left", padx=(4,12))

        self._alarm_cond = ctk.CTkOptionMenu(alarm_row,
                                              values=["above","below"],
                                              width=100, height=30,
                                              fg_color=BG_INPUT, button_color=BORDER,
                                              font=F_BODY, text_color=TEXT1)
        self._alarm_cond.pack(side="left", padx=(0,12))

        ctk.CTkButton(alarm_row, text="+ Ekle", width=80, height=30,
                      fg_color=BUY_C, text_color="#ffffff",
                      command=self._add_price_alert).pack(side="left")

        self._alarm_list = ctk.CTkTextbox(alarm_card, height=80,
                                           fg_color=BG_INPUT, border_color=BORDER,
                                           font=F_MONO, text_color=TEXT2,
                                           state="disabled")
        self._alarm_list.pack(fill="x", padx=16, pady=(0,10))
        self._refresh_alarm_list()

        # ── Fear & Greed ──────────────────────────────────────
        self._section(scroll, "😨 Kripto Fear & Greed Index")
        fg_card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8,
                                border_width=1, border_color=BORDER)
        fg_card.pack(fill="x", pady=6)
        self.lbl_fg = ctk.CTkLabel(fg_card, text="Yükleniyor...",
                                    font=F_MONO, text_color=TEXT2)
        self.lbl_fg.pack(anchor="w", padx=16, pady=12)
        ctk.CTkButton(fg_card, text="↻ Güncelle", width=110, height=28,
                      fg_color=BG_INPUT, hover_color="#c8d0d8", text_color=ACCENT,
                      command=self._load_fg).pack(anchor="e", padx=16, pady=(0,10))
        self._load_fg()

    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title, font=F_HEAD,
                     text_color=ACCENT).pack(anchor="w", pady=(14,4))
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x")

    def _send_test(self):
        if hasattr(self.app, "_telegram") and self.app._telegram:
            self.app._telegram.send_text(
                "🏦 *HedgeFund AI — Test Mesajı*\n\nBağlantı başarılı! ✅"
            )
            from tkinter import messagebox
            messagebox.showinfo("Telegram", "Test mesajı gönderildi!")
        else:
            from tkinter import messagebox
            messagebox.showwarning("Telegram", "Bot aktif değil. Önce token ve chat_id ekleyin.")

    def _refresh_status(self):
        cfg    = load_config()
        tg_cfg = cfg.get("telegram", {})
        token  = tg_cfg.get("bot_token","")
        chat   = tg_cfg.get("chat_id","")
        ok     = bool(token and chat and
                      not token.startswith("YOUR_") and
                      not chat.startswith("YOUR_"))
        self.lbl_bot_status.configure(
            text="🟢 Bot Aktif" if ok else "🔴 Bot Yapılandırılmamış",
            text_color=BUY_C if ok else SELL_C
        )

    def _save_tg_cfg(self):
        try:
            cfg = load_config()
            cfg.setdefault("telegram", {})
            cfg["telegram"]["bot_token"]      = self._tg_entries["bot_token"].get().strip()
            cfg["telegram"]["chat_id"]        = self._tg_entries["chat_id"].get().strip()
            cfg["telegram"]["min_confidence"] = int(self._tg_entries["min_confidence"].get() or 60)
            cfg["telegram"]["send_on_buy"]    = bool(self._sw_buy.get())
            cfg["telegram"]["send_on_sell"]   = bool(self._sw_sell.get())
            cfg["telegram"]["send_on_hold"]   = bool(self._sw_hold.get())
            from src.config_loader import save_settings
            save_settings(cfg, ROOT / "config" / "settings.yaml")
            self._refresh_status()
            from tkinter import messagebox
            messagebox.showinfo("Kaydedildi", "Telegram ayarları kaydedildi.\nEXE'yi yeniden başlatın.")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Hata", str(e))

    def _save_scheduler(self):
        try:
            cfg = load_config()
            cfg.setdefault("scheduler", {})
            for key, e in self._sched_entries.items():
                cfg["scheduler"][key] = e.get().strip()
            cfg["scheduler"]["timezone"] = self._ent_tz.get().strip()
            from src.config_loader import save_settings
            save_settings(cfg, ROOT / "config" / "settings.yaml")
            from tkinter import messagebox
            messagebox.showinfo("Kaydedildi",
                "Zamanlayıcı ayarları kaydedildi.\nEXE'yi yeniden başlatın.")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Hata", str(e))

    def _add_price_alert(self):
        sym   = self._ent_alarm_sym.get().strip().upper()
        price = self._ent_alarm_price.get().strip()
        cond  = self._alarm_cond.get()
        if not sym or not price:
            from tkinter import messagebox
            messagebox.showwarning("Uyarı", "Sembol ve fiyat giriniz.")
            return
        try:
            p = float(price)
            if hasattr(self.app, "_price_alert_mgr") and self.app._price_alert_mgr:
                self.app._price_alert_mgr.add_alert(sym, p, cond)
            self._refresh_alarm_list()
            self._ent_alarm_sym.delete(0,"end")
            self._ent_alarm_price.delete(0,"end")
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Hata","Geçersiz fiyat.")

    def _refresh_alarm_list(self):
        self._alarm_list.configure(state="normal")
        self._alarm_list.delete("1.0","end")
        if hasattr(self.app, "_price_alert_mgr") and self.app._price_alert_mgr:
            alerts = self.app._price_alert_mgr.list_alerts()
            if alerts:
                for a in alerts:
                    sign = ">" if a["condition"]=="above" else "<"
                    self._alarm_list.insert(
                        "end",
                        f"  {a['symbol']}  {sign}  {a['price']:,.2f}\n"
                    )
            else:
                self._alarm_list.insert("end", "  Aktif alarm yok.\n")
        else:
            self._alarm_list.insert("end", "  Alarm sistemi başlatılmadı.\n")
        self._alarm_list.configure(state="disabled")

    def _load_fg(self):
        def _fetch():
            data = fetch_fear_greed()
            txt  = format_fear_greed(data)
            hist = data.get("history",[])
            if hist:
                txt += "\n\nSon 7 gün:\n"
                for h in hist[:7]:
                    bar = "█" * int(h["value"]/10) + "░" * (10 - int(h["value"]/10))
                    txt += f"  {h['date']}  [{bar}]  {h['value']}/100  {h['label']}\n"
            _, adj = fear_greed_signal(data.get("value",50))
            txt += f"\nKomposit Etki: {adj:+.0f} puan"
            try:
                self.after(0, lambda: self.lbl_fg.configure(text=txt))
            except RuntimeError:
                pass  # mainloop henüz başlamadı, görmezden gel
        threading.Thread(target=_fetch, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════
class HedgeFundApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HedgeFund AI  |  Investment Analysis System")
        self.geometry("1440x860")
        self.minsize(1100, 680)
        self.configure(fg_color=BG)
        self._result_q       = queue.Queue()
        self._alert_sys      = AlertSystem()
        self._telegram       = None
        self._scheduler      = None
        self._price_alert_mgr = None
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._active         = None
        self._setup()
        self._start_services()
        self.after(100, self._poll_queue)
        self.after(800, lambda: self._pages["dashboard"].refresh_all())

    def _start_services(self):
        """Start Telegram bot, scheduler and price monitor in background."""
        cfg = load_config()

        # Telegram
        if TELEGRAM_AVAILABLE:
            tg_cfg = cfg.get("telegram", {})
            token  = tg_cfg.get("bot_token","")
            chat   = tg_cfg.get("chat_id","")
            if token and not token.startswith("YOUR_"):
                self._telegram = TelegramNotifier(token, chat, cfg)
                self._telegram.on_analyze_request = self._bg_analyze
                self._telegram.on_scan_request    = self._bg_scan
                self._telegram.start()

        # Price alerts
        if ALERTS_AVAILABLE:
            self._price_alert_mgr = PriceAlertManager(self._telegram)
            self._price_alert_mgr.start_monitoring(60)

        # Scheduler
        if SCHEDULER_AVAILABLE:
            self._scheduler = SignalScheduler(cfg, self._telegram)
            self._scheduler.on_scheduled_scan    = self._bg_scan
            self._scheduler.on_scheduled_analyze = self._bg_analyze
            self._scheduler.start()

    def _bg_analyze(self, sym: str) -> dict:
        """Synchronous analysis for background threads."""
        atype = detect_type(sym)
        return run_full_analysis(sym, atype, 100_000)

    def _bg_scan(self) -> list[dict]:
        """Synchronous full-scan for background threads."""
        wl = CFG["watchlist"]
        syms = (
            [(s,"crypto") for s in wl.get("crypto",[])] +
            [(s,"stock")  for s in wl.get("us_stocks",[])] +
            [(s,"bist")   for s in wl.get("bist",[])]
        )
        results = []
        for sym, atype in syms:
            try:
                r = run_full_analysis(sym, atype, 100_000)
                results.append(r)
                # Push to Telegram if signal qualifies
                if self._telegram:
                    self._telegram.send_signal(
                        sym, r["decision"], r["tech"],
                        r["sizing"], r["macro"]
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"BG scan failed {sym}: {e}")
        return results

    def _setup(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────
        sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR,
                               corner_radius=0, width=200)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Logo
        logo_f = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_f.pack(fill="x", padx=16, pady=(24,8))
        ctk.CTkLabel(logo_f, text="🏦", font=("Segoe UI",28)).pack(side="left")
        tl = ctk.CTkFrame(logo_f, fg_color="transparent")
        tl.pack(side="left", padx=8)
        ctk.CTkLabel(tl, text="HedgeFund", font=("Segoe UI",13,"bold"),
                     text_color=TEXT1).pack(anchor="w")
        ctk.CTkLabel(tl, text="AI  v1.0", font=("Segoe UI",10),
                     text_color=ACCENT).pack(anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=12)

        # Nav buttons
        self._nav_btns = {}
        nav_items = [
            ("dashboard",    "📊  Dashboard"),
            ("opportunities","💎  Fırsatlar"),
            ("portfolio",    "🏗  Portföy Oluşturucu"),
            ("projection",   "📈  Projeksiyon"),
            ("analysis",     "🔍  Detaylı Analiz"),
            ("backtest",     "📉  Backtest"),
            ("alerts",       "🔔  Uyarılar"),
            ("bot",          "📱  Bot & Zamanlayıcı"),
            ("settings",     "⚙️   Ayarlar"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                sidebar, text=label, anchor="w",
                font=("Segoe UI",12), height=40,
                fg_color="transparent", hover_color="#d8dde3",
                text_color=TEXT2, corner_radius=8,
                command=lambda k=key: self._navigate(k),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns[key] = btn

        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=12)

        # Status
        self.lbl_status = ctk.CTkLabel(
            sidebar, text="● Hazır", font=F_SMALL, text_color=BUY_C)
        self.lbl_status.pack(anchor="w", padx=20)
        ctk.CTkLabel(sidebar,
                     text=f"NewsAPI  ✓\nFRED      ✓\nFinnhub  ✓\nBinance  ✓",
                     font=("Consolas",9), text_color=TEXT2,
                     justify="left").pack(anchor="w", padx=20, pady=4)

        # ── Main content ──────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Create pages
        dash = DashboardPage(main, self._result_q,
                             on_analyze_cb=self._go_analyze)
        ana  = AnalysisPage(main, self._result_q, self._alert_sys)
        bt   = BacktestPage(main, self._result_q)
        alrt = AlertsPage(main)
        bot  = BotPage(main, app_ref=self)
        sett = SettingsPage(main)

        # Yeni sayfalar
        if OPPORTUNITIES_AVAILABLE:
            opp = OpportunitiesPage(main, self._result_q)
        else:
            opp = ctk.CTkFrame(main, fg_color=BG)
            ctk.CTkLabel(opp, text="Fırsatlar modülü yüklenemedi.",
                         font=F_BODY, text_color=TEXT2).pack(pady=40)

        if PORTFOLIO_AVAILABLE:
            port = PortfolioBuilderPage(main)
        else:
            port = ctk.CTkFrame(main, fg_color=BG)
            ctk.CTkLabel(port, text="Portföy modülü yüklenemedi.",
                         font=F_BODY, text_color=TEXT2).pack(pady=40)

        if PROJECTION_AVAILABLE:
            proj = ProjectionPage(main)
        else:
            proj = ctk.CTkFrame(main, fg_color=BG)
            ctk.CTkLabel(proj, text="Projeksiyon modülü yüklenemedi.",
                         font=F_BODY, text_color=TEXT2).pack(pady=40)

        for name, page in [
            ("dashboard",      dash),
            ("opportunities",  opp),
            ("portfolio",      port),
            ("projection",     proj),
            ("analysis",       ana),
            ("backtest",       bt),
            ("alerts",         alrt),
            ("bot",            bot),
            ("settings",       sett),
        ]:
            page.grid(row=0, column=0, sticky="nsew")
            self._pages[name] = page

        self._navigate("dashboard")

    def _navigate(self, key):
        if key not in self._pages:
            return
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=BG_INPUT, text_color=TEXT1)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT2)
        self._pages[key].tkraise()
        self._active = key

    def _go_analyze(self, sym):
        self._navigate("analysis")
        self._pages["analysis"].set_symbol(sym)

    def _poll_queue(self):
        try:
            while True:
                item = self._result_q.get_nowait()
                kind = item[0]
                sym, result, error = item[1], item[2], item[3]

                if kind == "dashboard":
                    self._pages["dashboard"].apply_result(sym, result, error)
                    if result:
                        alerts = self._alert_sys.check_and_alert(
                            sym, result["tech"], result["sent"],
                            {}, result["macro"]
                        )
                        for a in alerts:
                            self._pages["alerts"].add_alert(a)
                        self.lbl_status.configure(
                            text=f"● {sym} tamamlandı", text_color=BUY_C)

                elif kind == "analysis":
                    self._pages["analysis"].apply_result(sym, result, error)

                elif kind == "backtest":
                    self._pages["backtest"].apply_result(sym, result, error)

        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


# ── Entry point ───────────────────────────────────────────────
def main():
    app = HedgeFundApp()
    app.mainloop()


if __name__ == "__main__":
    main()
