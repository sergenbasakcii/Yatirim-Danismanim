"""
HedgeFund AI — Zamanlayıcı
APScheduler ile belirli saatlerde otomatik tarama ve sinyal gönderimi.

Özellikler:
  - Günlük sabah brifing (08:30)
  - Piyasa açılış taraması (09:30)
  - Öğle taraması (12:00)
  - Kapanış öncesi uyarı (16:30)
  - Özelleştirilebilir zamanlar (settings.yaml)
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    APSCHEDULER_OK = True
except ImportError:
    APSCHEDULER_OK = False
    logger.warning("APScheduler not installed. Run: pip install apscheduler")


class SignalScheduler:
    """
    Configurable scheduler that runs analysis at preset times
    and pushes results to Telegram.
    """

    def __init__(self, cfg: dict, telegram_notifier=None):
        self.cfg        = cfg
        self.tg         = telegram_notifier
        self._scheduler = None
        self._running   = False

        # Callbacks set by main app
        self.on_scheduled_scan:   Optional[Callable] = None   # () → list[dict]
        self.on_scheduled_analyze: Optional[Callable] = None  # (sym) → dict

    def start(self):
        if not APSCHEDULER_OK:
            logger.error("APScheduler not installed")
            return
        sched_cfg = self.cfg.get("scheduler", {})
        if not sched_cfg.get("enabled", True):
            logger.info("Scheduler disabled in settings")
            return

        tz = sched_cfg.get("timezone", "Europe/Istanbul")
        self._scheduler = BackgroundScheduler(timezone=tz)

        # ── Morning briefing ─────────────────────────────────
        t = sched_cfg.get("morning_briefing", "08:30")
        h, m = map(int, t.split(":"))
        self._scheduler.add_job(
            self._morning_briefing, CronTrigger(hour=h, minute=m),
            id="morning_briefing", replace_existing=True
        )

        # ── Market open scan ─────────────────────────────────
        t = sched_cfg.get("market_open_scan", "09:30")
        h, m = map(int, t.split(":"))
        self._scheduler.add_job(
            self._market_open_scan, CronTrigger(hour=h, minute=m),
            id="market_open", replace_existing=True
        )

        # ── Midday scan ───────────────────────────────────────
        t = sched_cfg.get("midday_scan", "12:00")
        h, m = map(int, t.split(":"))
        self._scheduler.add_job(
            self._midday_scan, CronTrigger(hour=h, minute=m),
            id="midday", replace_existing=True
        )

        # ── Pre-close alert ───────────────────────────────────
        t = sched_cfg.get("preclose_alert", "16:30")
        h, m = map(int, t.split(":"))
        self._scheduler.add_job(
            self._preclose_alert, CronTrigger(hour=h, minute=m),
            id="preclose", replace_existing=True
        )

        # ── Evening summary ───────────────────────────────────
        t = sched_cfg.get("evening_summary", "18:00")
        h, m = map(int, t.split(":"))
        self._scheduler.add_job(
            self._evening_summary, CronTrigger(hour=h, minute=m),
            id="evening", replace_existing=True
        )

        # ── Weekly report (Monday 07:00) ──────────────────────
        self._scheduler.add_job(
            self._weekly_report,
            CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="weekly", replace_existing=True
        )

        self._scheduler.start()
        self._running = True
        logger.info(f"Scheduler started (TZ: {tz})")

    def stop(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
        self._running = False

    def get_jobs(self) -> list[dict]:
        if not self._scheduler:
            return []
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id":       job.id,
                "name":     job.name,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M") if next_run else "—",
            })
        return jobs

    def add_custom_job(self, job_id: str, hour: int, minute: int,
                       symbol: Optional[str] = None):
        """Add a one-off or recurring custom job for a specific symbol."""
        if not self._scheduler:
            return
        fn = (lambda sym=symbol: self._custom_analyze(sym)) if symbol \
             else self._market_open_scan
        self._scheduler.add_job(
            fn, CronTrigger(hour=hour, minute=minute),
            id=job_id, replace_existing=True
        )
        logger.info(f"Custom job added: {job_id} at {hour:02d}:{minute:02d}")

    # ── Scheduled task implementations ───────────────────────

    def _morning_briefing(self):
        now = datetime.now().strftime("%d.%m.%Y")
        msg = (
            f"🌅 *Günaydın — {now}*\n\n"
            f"HedgeFund AI günlük brifing başlıyor.\n"
            f"Piyasa taraması 09:30'da otomatik çalışacak.\n\n"
            f"Makro gündem:\n"
            f"• ABD borsaları 09:30'da açılıyor\n"
            f"• BIST 10:00'da açılıyor\n"
            f"• Kripto piyasası 7/24 açık\n\n"
            f"İyi işlemler! 📊"
        )
        if self.tg:
            self.tg.send_text(msg)
        logger.info("Morning briefing sent")

    def _market_open_scan(self):
        logger.info("Market open scan running...")
        if self.tg:
            self.tg.send_text("🔔 *Piyasa açılış taraması başladı...*")
        self._run_full_scan("📈 Açılış Taraması")

    def _midday_scan(self):
        logger.info("Midday scan running...")
        self._run_full_scan("☀️ Öğle Taraması")

    def _preclose_alert(self):
        if self.tg:
            self.tg.send_text(
                "⏰ *Kapanış öncesi uyarı*\n\n"
                "Piyasa kapanışına 30 dakika kaldı.\n"
                "Açık pozisyonlarınızı gözden geçirin.\n"
                "Stop-loss seviyelerinizi kontrol edin."
            )
        logger.info("Pre-close alert sent")

    def _evening_summary(self):
        logger.info("Evening summary running...")
        self._run_full_scan("🌙 Akşam Özeti")

    def _weekly_report(self):
        if self.tg:
            self.tg.send_text(
                "📅 *Haftalık Rapor — Pazartesi*\n\n"
                "Yeni haftaya başlarken tarama yapılıyor..."
            )
        self._run_full_scan("📅 Haftalık Rapor")

    def _custom_analyze(self, symbol: str):
        logger.info(f"Custom scheduled analysis for {symbol}")
        if self.on_scheduled_analyze and symbol:
            try:
                r = self.on_scheduled_analyze(symbol)
                if self.tg and r:
                    self.tg.send_signal(
                        symbol, r["decision"], r["tech"],
                        r["sizing"], r["macro"]
                    )
            except Exception as e:
                logger.error(f"Custom analyze failed for {symbol}: {e}")

    def _run_full_scan(self, label: str):
        if not self.on_scheduled_scan:
            return
        threading.Thread(
            target=self._scan_thread, args=(label,), daemon=True
        ).start()

    def _scan_thread(self, label: str):
        try:
            results = self.on_scheduled_scan()
            buy_signals  = []
            sell_signals = []
            hold_count   = 0

            for r in results:
                d = r.get("decision")
                if not d:
                    continue
                if d.action == "BUY"  and d.confidence >= 60:
                    buy_signals.append(r)
                elif d.action == "SELL" and d.confidence >= 60:
                    sell_signals.append(r)
                else:
                    hold_count += 1

            # Summary message
            summary = (
                f"📊 *{label} Sonuçları*\n"
                f"{'─'*28}\n"
                f"🟢 BUY Sinyali   : {len(buy_signals)}\n"
                f"🔴 SELL Sinyali  : {len(sell_signals)}\n"
                f"🟡 HOLD          : {hold_count}\n\n"
            )
            if buy_signals:
                summary += "🟢 *Alım Fırsatları:*\n"
                for r in buy_signals:
                    d = r["decision"]
                    t = r["tech"]
                    summary += (
                        f"  • `{d.symbol}` — `{t.price:,.4g}` "
                        f"(%{d.confidence:.0f} güven)\n"
                    )
            if sell_signals:
                summary += "\n🔴 *Satış Sinyalleri:*\n"
                for r in sell_signals:
                    d = r["decision"]
                    t = r["tech"]
                    summary += (
                        f"  • `{d.symbol}` — `{t.price:,.4g}` "
                        f"(%{d.confidence:.0f} güven)\n"
                    )

            if self.tg:
                self.tg.send_text(summary)

            # Send detail for each BUY/SELL signal
            for r in buy_signals + sell_signals:
                if self.tg:
                    self.tg.send_signal(
                        r["decision"].symbol,
                        r["decision"], r["tech"],
                        r["sizing"], r["macro"]
                    )

        except Exception as e:
            logger.error(f"Scan thread error: {e}")
            if self.tg:
                self.tg.send_text(f"❌ Tarama hatası: {e}")
