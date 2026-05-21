"""
HedgeFund AI — Telegram Bot
Komutlar:
  /start           — karşılama
  /scan            — tüm watchlist tara
  /analyze AAPL    — tek sembol analizi
  /price BTC       — anlık fiyat
  /alert AAPL 250 below — fiyat alarmı kur
  /alerts          — aktif alarmlar
  /status          — sistem durumu
  /help            — yardım
"""

import asyncio
import threading
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        ContextTypes, filters,
    )
    from telegram.constants import ParseMode
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False
    logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")


def _fmt(p) -> str:
    if p is None: return "—"
    try:
        p = float(p)
        return f"{p:,.2f}" if p >= 1 else f"{p:.6f}"
    except: return "—"


def build_signal_message(symbol: str, decision, tech, sizing, macro: dict) -> str:
    action_icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(decision.action, "⚪")
    trend_icon  = {"UPTREND": "📈", "DOWNTREND": "📉", "SIDEWAYS": "➡️"}.get(tech.trend, "")
    vix = macro.get("VIX", {}).get("current", "?")
    dxy = macro.get("DXY", {}).get("current", "?")

    top_signals = "\n".join(
        f"  ⚡ {s}" for s in decision.all_signals[:4]
    )

    msg = (
        f"🏦 *HedgeFund AI Sinyali*\n"
        f"{'─'*32}\n"
        f"{action_icon} *{decision.action}* — `{symbol}`\n"
        f"💰 Fiyat: `{_fmt(tech.price)}`\n"
        f"📊 Güven: `{decision.confidence:.0f}%`\n"
        f"🎯 Kompozit: `{decision.composite:.1f}/100`\n\n"
        f"*Fiyat Seviyeleri*\n"
        f"  Giriş  : `{_fmt(decision.entry)}`\n"
        f"  Stop   : `{_fmt(decision.stop_loss)}`\n"
        f"  TP1    : `{_fmt(decision.take_profit_1)}`\n"
        f"  TP2    : `{_fmt(decision.take_profit_2)}`\n"
        f"  TP3    : `{_fmt(decision.take_profit_3)}`\n\n"
        f"*Skorlar*\n"
        f"  Teknik: `{decision.tech_score:.0f}` | "
        f"Sentiment: `{decision.sent_score:.0f}` | "
        f"Makro: `{decision.macro_score:.0f}`\n\n"
        f"*Teknik*\n"
        f"  RSI: `{tech.rsi}` | Trend: {trend_icon} `{tech.trend}`\n"
        f"  Kırılım: `{'EVET ✔' if tech.breakout else 'Hayır'}`\n\n"
        f"*Sinyaller*\n{top_signals}\n\n"
        f"*Makro*\n"
        f"  VIX: `{vix}` | DXY: `{dxy}`\n\n"
        f"*Pozisyon*\n"
        f"  Miktar: `{sizing.units:,.6g}` | "
        f"Değer: `${sizing.dollar_amount:,.2f}`\n"
        f"  R:R → 1:`{sizing.risk_reward_1}`\n\n"
        f"⏰ `{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}`\n"
        f"⚠️ _Bu bir analiz aracıdır, yatırım tavsiyesi değildir._"
    )
    return msg


def build_alert_message(symbol: str, alert_type: str, message: str, severity: str) -> str:
    icon = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(severity, "")
    return (
        f"{icon} *{severity}* — `{symbol}`\n"
        f"Tür: `{alert_type}`\n"
        f"{message}\n"
        f"⏰ `{datetime.utcnow().strftime('%H:%M UTC')}`"
    )


class TelegramNotifier:
    """
    Thread-safe Telegram notifier + bot command handler.
    Runs in a background daemon thread.
    """

    def __init__(self, token: str, chat_id: str, cfg: dict):
        self.token   = token
        self.chat_id = str(chat_id)
        self.cfg     = cfg
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._app    = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # Will be injected by main app
        self.on_scan_request    = None   # callback: () → list[dict]
        self.on_analyze_request = None   # callback: (symbol) → dict
        self.price_alert_mgr    = None

    # ── Public API (call from any thread) ────────────────────

    def start(self):
        if not TELEGRAM_OK:
            logger.error("python-telegram-bot not installed!")
            return
        if not self.token or self.token.startswith("YOUR_"):
            logger.info("Telegram token not configured — bot disabled")
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Telegram bot thread started")

    def stop(self):
        self._running = False

    def send_signal(self, symbol: str, decision, tech, sizing, macro: dict):
        """Push a trading signal. Call from any thread."""
        min_conf = self.cfg.get("telegram", {}).get("min_confidence", 60)
        if decision.action == "HOLD" and not self.cfg.get("telegram", {}).get("send_on_hold", False):
            return
        if decision.confidence < min_conf:
            return
        msg = build_signal_message(symbol, decision, tech, sizing, macro)
        self._send_async(msg)

    def send_alert(self, symbol: str, alert_type: str, message: str, severity: str):
        """Push a system alert. Call from any thread."""
        msg = build_alert_message(symbol, alert_type, message, severity)
        self._send_async(msg)

    def send_text(self, text: str):
        """Send plain text message. Call from any thread."""
        self._send_async(text)

    # ── Internal ─────────────────────────────────────────────

    def _send_async(self, text: str):
        if not self._loop or not self._running:
            return
        asyncio.run_coroutine_threadsafe(
            self._do_send(text), self._loop
        )

    async def _do_send(self, text: str):
        try:
            await self._app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_bot())

    async def _start_bot(self):
        try:
            self._app = Application.builder().token(self.token).build()

            self._app.add_handler(CommandHandler("start",   self._cmd_start))
            self._app.add_handler(CommandHandler("help",    self._cmd_help))
            self._app.add_handler(CommandHandler("scan",    self._cmd_scan))
            self._app.add_handler(CommandHandler("analyze", self._cmd_analyze))
            self._app.add_handler(CommandHandler("price",   self._cmd_price))
            self._app.add_handler(CommandHandler("alert",   self._cmd_alert))
            self._app.add_handler(CommandHandler("alerts",  self._cmd_alerts))
            self._app.add_handler(CommandHandler("status",  self._cmd_status))

            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started")

            # Keep alive
            while self._running:
                await asyncio.sleep(1)

            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        except Exception as e:
            logger.error(f"Telegram bot error: {e}\n{traceback.format_exc()}")

    # ── Command handlers ──────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        # Auto-capture chat_id
        cid = str(update.effective_chat.id)
        await update.message.reply_text(
            f"🏦 *HedgeFund AI'ye hoş geldiniz!*\n\n"
            f"Chat ID'niz: `{cid}`\n\n"
            f"Bu ID'yi settings.yaml → telegram.chat\\_id alanına girin.\n\n"
            f"/help → komut listesi",
            parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📋 *Komutlar*\n\n"
            "/scan — tüm watchlist tara\n"
            "/analyze AAPL — sembol analizi\n"
            "/price BTC — anlık fiyat\n"
            "/alert AAPL 250 below — fiyat alarmı\n"
            "/alerts — aktif alarmlar\n"
            "/status — sistem durumu\n",
            parse_mode=ParseMode.MARKDOWN
        )

    async def _cmd_scan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔄 Tarama başlatıldı, bekleyin...")
        if self.on_scan_request:
            threading.Thread(
                target=self._scan_and_reply,
                args=(update,), daemon=True
            ).start()
        else:
            await update.message.reply_text("⚠️ Tarama callback bağlı değil.")

    def _scan_and_reply(self, update: Update):
        try:
            results = self.on_scan_request()
            for r in results:
                d    = r.get("decision")
                tech = r.get("tech")
                sz   = r.get("sizing")
                mac  = r.get("macro", {})
                if d and (d.action in ("BUY","SELL") and d.confidence >= 60):
                    msg = build_signal_message(d.symbol, d, tech, sz, mac)
                    asyncio.run_coroutine_threadsafe(
                        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN),
                        self._loop
                    )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(f"❌ Hata: {e}"),
                self._loop
            )

    async def _cmd_analyze(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        args = ctx.args
        if not args:
            await update.message.reply_text("Kullanım: /analyze AAPL")
            return
        sym = args[0].upper()
        await update.message.reply_text(f"🔍 {sym} analiz ediliyor...")
        if self.on_analyze_request:
            threading.Thread(
                target=self._analyze_and_reply,
                args=(update, sym), daemon=True
            ).start()

    def _analyze_and_reply(self, update: Update, sym: str):
        try:
            r   = self.on_analyze_request(sym)
            msg = build_signal_message(sym, r["decision"], r["tech"],
                                       r["sizing"], r["macro"])
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN),
                self._loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                update.message.reply_text(f"❌ Hata: {e}"),
                self._loop
            )

    async def _cmd_price(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        args = ctx.args
        sym  = (args[0].upper() if args else "BTC") + ("/USDT" if "/" not in (args[0] if args else "") else "")
        try:
            import yfinance as yf
            from src.data_collector import fetch_crypto_ohlcv, fetch_stock_ohlcv, detect_type
            atype = "crypto" if "/" in sym else "stock"
            if atype == "crypto":
                df = fetch_crypto_ohlcv(sym)
            else:
                df = fetch_stock_ohlcv(sym)
            price = float(df["close"].iloc[-1])
            chg   = float(df["close"].pct_change().iloc[-1] * 100)
            icon  = "📈" if chg >= 0 else "📉"
            await update.message.reply_text(
                f"{icon} `{sym}`\n"
                f"Fiyat: `{price:,.4f}`\n"
                f"Değişim: `{chg:+.2f}%`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Fiyat alınamadı: {e}")

    async def _cmd_alert(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        # /alert AAPL 250 below
        args = ctx.args
        if len(args) < 3:
            await update.message.reply_text(
                "Kullanım: /alert SEMBOL FİYAT above|below\n"
                "Örnek: /alert BTC/USDT 80000 above"
            )
            return
        sym, price_str, condition = args[0].upper(), args[1], args[2].lower()
        if condition not in ("above","below"):
            await update.message.reply_text("Koşul: above veya below")
            return
        try:
            price = float(price_str)
            if self.price_alert_mgr:
                self.price_alert_mgr.add_alert(sym, price, condition)
            await update.message.reply_text(
                f"✅ Alarm kuruldu!\n`{sym}` fiyatı `{price:,.2f}` değerinin "
                f"{'üstüne çıkınca' if condition=='above' else 'altına düşünce'} "
                f"haberdar edileceksiniz.",
                parse_mode=ParseMode.MARKDOWN
            )
        except ValueError:
            await update.message.reply_text("❌ Geçersiz fiyat formatı.")

    async def _cmd_alerts(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if self.price_alert_mgr:
            alerts = self.price_alert_mgr.list_alerts()
            if not alerts:
                await update.message.reply_text("📭 Aktif fiyat alarmı yok.")
                return
            lines = ["📋 *Aktif Fiyat Alarmları*\n"]
            for a in alerts:
                lines.append(
                    f"• `{a['symbol']}` → "
                    f"{'>' if a['condition']=='above' else '<'} "
                    f"`{a['price']:,.2f}`"
                )
            await update.message.reply_text(
                "\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("Alarm sistemi aktif değil.")

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        from src.data_collector import load_config
        cfg = load_config()
        keys = cfg.get("api_keys", {})
        def chk(k): return "✅" if keys.get(k,"").replace("YOUR_","") else "❌"
        await update.message.reply_text(
            f"🏦 *HedgeFund AI Durum*\n\n"
            f"{chk('newsapi')} NewsAPI\n"
            f"{chk('fred')} FRED\n"
            f"{chk('finnhub')} Finnhub\n"
            f"{chk('binance_api_key')} Binance\n\n"
            f"⏰ `{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}`",
            parse_mode=ParseMode.MARKDOWN
        )
