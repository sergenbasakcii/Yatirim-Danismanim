"""
HedgeFund AI — Fiyat Alarmı & Aktif Pozisyon Monitörü
Her 60 saniyede fiyatları kontrol eder,
kullanıcı tanımlı seviyelere ulaşıldığında Telegram push gönderir.
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import sys
_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
ALERTS_FILE = _ROOT / "data" / "price_alerts.json"
ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)


class PriceAlertManager:

    def __init__(self, telegram_notifier=None):
        self.tg       = telegram_notifier
        self._alerts  = self._load()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ── CRUD ─────────────────────────────────────────────────

    def add_alert(self, symbol: str, price: float, condition: str,
                  note: str = ""):
        """condition: 'above' or 'below'"""
        alert = {
            "symbol":    symbol,
            "price":     price,
            "condition": condition,
            "note":      note,
            "created":   datetime.utcnow().isoformat(),
            "triggered": False,
        }
        self._alerts.append(alert)
        self._save()
        logger.info(f"Price alert added: {symbol} {condition} {price}")

    def remove_alert(self, symbol: str, price: float):
        self._alerts = [
            a for a in self._alerts
            if not (a["symbol"] == symbol and a["price"] == price)
        ]
        self._save()

    def list_alerts(self) -> list[dict]:
        return [a for a in self._alerts if not a.get("triggered")]

    # ── Monitor loop ──────────────────────────────────────────

    def start_monitoring(self, interval_seconds: int = 60):
        self._running = True
        self._thread  = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,), daemon=True
        )
        self._thread.start()
        logger.info(f"Price monitor started (interval: {interval_seconds}s)")

    def stop_monitoring(self):
        self._running = False

    def _monitor_loop(self, interval: int):
        while self._running:
            try:
                self._check_all()
            except Exception as e:
                logger.error(f"Price monitor error: {e}")
            time.sleep(interval)

    def _check_all(self):
        active = [a for a in self._alerts if not a.get("triggered")]
        if not active:
            return

        # Batch fetch prices
        symbols = list({a["symbol"] for a in active})
        prices  = self._batch_prices(symbols)

        for alert in active:
            sym   = alert["symbol"]
            price = prices.get(sym)
            if price is None:
                continue

            triggered = (
                (alert["condition"] == "above" and price >= alert["price"]) or
                (alert["condition"] == "below" and price <= alert["price"])
            )

            if triggered:
                self._fire_alert(alert, price)
                alert["triggered"] = True
                alert["triggered_at"]    = datetime.utcnow().isoformat()
                alert["triggered_price"] = price

        self._save()

    def _fire_alert(self, alert: dict, current_price: float):
        sym   = alert["symbol"]
        cond  = "üstüne çıktı 📈" if alert["condition"] == "above" else "altına düştü 📉"
        icon  = "🚨"
        msg   = (
            f"{icon} *Fiyat Alarmı!*\n\n"
            f"Sembol   : `{sym}`\n"
            f"Hedef    : `{alert['price']:,.4f}`\n"
            f"Güncel   : `{current_price:,.4f}`\n"
            f"Durum    : Hedef fiyatın {cond}\n"
        )
        if alert.get("note"):
            msg += f"Not      : {alert['note']}\n"
        msg += f"\n⏰ `{datetime.utcnow().strftime('%H:%M UTC')}`"

        logger.info(f"Price alert fired: {sym} @ {current_price}")
        if self.tg:
            self.tg.send_text(msg)

    def _batch_prices(self, symbols: list[str]) -> dict[str, float]:
        """Fetch latest close prices for a list of symbols."""
        prices = {}
        for sym in symbols:
            try:
                from src.data_collector import fetch_crypto_ohlcv, fetch_stock_ohlcv
                if "/" in sym:
                    df = fetch_crypto_ohlcv(sym)
                else:
                    df = fetch_stock_ohlcv(sym)
                prices[sym] = float(df["close"].iloc[-1])
            except Exception as e:
                logger.warning(f"Price fetch failed for {sym}: {e}")
        return prices

    # ── Persistence ───────────────────────────────────────────

    def _load(self) -> list[dict]:
        if ALERTS_FILE.exists():
            try:
                with open(ALERTS_FILE) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save(self):
        try:
            with open(ALERTS_FILE, "w") as f:
                json.dump(self._alerts, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save price alerts: {e}")
