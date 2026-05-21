"""
HedgeFund AI — Alert System
Generates structured alerts for RSI extremes, volume spikes,
news shocks, earnings proximity and macro events.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

import sys
if getattr(sys, "frozen", False):
    CONFIG_PATH = Path(sys.executable).parent / "config" / "settings.yaml"
else:
    CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_cfg() -> dict:
    from src.config_loader import load_settings
    return load_settings(CONFIG_PATH)


SEVERITY = {
    "INFO":    "ℹ️ ",
    "WARNING": "⚠️ ",
    "CRITICAL":"🚨",
}


class Alert:
    def __init__(self, symbol: str, alert_type: str, message: str, severity: str = "WARNING"):
        self.symbol    = symbol
        self.type      = alert_type
        self.message   = message
        self.severity  = severity
        self.timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def __str__(self):
        icon = SEVERITY.get(self.severity, "")
        return f"[{self.timestamp}] {icon} [{self.severity}] {self.symbol} | {self.type} | {self.message}"


class AlertSystem:

    def __init__(self):
        self.cfg     = _load_cfg()
        self.alerts  = []
        self._setup_logging()

    def _setup_logging(self):
        alert_cfg = self.cfg.get("alerts", {})
        if alert_cfg.get("enable_log_file"):
            log_path = Path(alert_cfg.get("log_path", "logs/alerts.log"))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path)
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(message)s"))
            logging.getLogger("hedge_alerts").addHandler(fh)

    def check_and_alert(
        self,
        symbol: str,
        tech,
        sent,
        fund_data: Optional[dict] = None,
        macro: Optional[dict] = None,
    ) -> list[Alert]:

        triggered = []
        cfg_tech = self.cfg.get("technical", {})

        # RSI extremes
        if tech.rsi is not None:
            ob = cfg_tech.get("rsi_overbought", 70)
            os_ = cfg_tech.get("rsi_oversold", 30)
            if tech.rsi >= ob:
                triggered.append(Alert(
                    symbol, "RSI_OVERBOUGHT",
                    f"RSI={tech.rsi:.1f} — overbought zone. Consider reducing long exposure.",
                    "WARNING"
                ))
            elif tech.rsi <= os_:
                triggered.append(Alert(
                    symbol, "RSI_OVERSOLD",
                    f"RSI={tech.rsi:.1f} — oversold zone. Watch for reversal / capitulation end.",
                    "WARNING"
                ))

        # Volume spike
        spike = cfg_tech.get("volume_spike_multiplier", 2.5)
        if tech.volume_ratio and tech.volume_ratio >= spike:
            triggered.append(Alert(
                symbol, "VOLUME_SPIKE",
                f"Volume is {tech.volume_ratio:.1f}x the 20-day average. "
                f"Unusual activity — confirm direction before acting.",
                "WARNING"
            ))

        # Breakout
        if tech.breakout:
            triggered.append(Alert(
                symbol, "BREAKOUT",
                f"Price broke above 20-period resistance. Momentum trade opportunity.",
                "INFO"
            ))

        # Sentiment shock
        if sent.score <= 25:
            triggered.append(Alert(
                symbol, "NEGATIVE_SENTIMENT",
                f"Sentiment score={sent.score:.0f}/100 — extreme negative news flow. "
                f"{sent.negative_count} negative articles detected.",
                "CRITICAL"
            ))
        elif sent.score >= 80:
            triggered.append(Alert(
                symbol, "EUPHORIA_WARNING",
                f"Sentiment score={sent.score:.0f}/100 — extreme euphoria. "
                f"Contrarian caution advised.",
                "WARNING"
            ))

        # VIX spike (macro)
        if macro:
            vix = macro.get("VIX", {}).get("current")
            vix_chg = macro.get("VIX", {}).get("change_1d")
            if vix and vix > 30:
                triggered.append(Alert(
                    symbol, "VIX_SPIKE",
                    f"VIX={vix} — elevated fear in markets. Risk-off environment, reduce size.",
                    "CRITICAL"
                ))
            elif vix_chg and vix_chg > 15:
                triggered.append(Alert(
                    symbol, "VIX_SURGE",
                    f"VIX surged {vix_chg:.1f}% intraday. Volatility regime shift.",
                    "WARNING"
                ))

        # Bollinger squeeze breakout
        if tech.bb_pct is not None:
            if tech.bb_pct > 0.98:
                triggered.append(Alert(
                    symbol, "BB_UPPER_BREACH",
                    f"Price at {tech.bb_pct*100:.0f}% of Bollinger Band. Possible mean reversion.",
                    "INFO"
                ))
            elif tech.bb_pct < 0.02:
                triggered.append(Alert(
                    symbol, "BB_LOWER_BREACH",
                    f"Price at lower Bollinger Band. Watch for bounce or breakdown.",
                    "INFO"
                ))

        for a in triggered:
            self._dispatch(a)
        self.alerts.extend(triggered)
        return triggered

    def _dispatch(self, alert: Alert):
        alert_str = str(alert)

        if self.cfg.get("alerts", {}).get("enable_console", True):
            print(alert_str)

        if self.cfg.get("alerts", {}).get("enable_log_file"):
            logging.getLogger("hedge_alerts").info(alert_str)

        smtp_host = self.cfg.get("alerts", {}).get("smtp_host", "")
        to_email  = self.cfg.get("alerts", {}).get("alert_email", "")
        if smtp_host and to_email and alert.severity == "CRITICAL":
            self._send_email(alert, to_email)

    def _send_email(self, alert: Alert, to_email: str):
        try:
            cfg = self.cfg.get("alerts", {})
            msg = MIMEText(str(alert))
            msg["Subject"] = f"HedgeFund AI Alert: {alert.symbol} — {alert.type}"
            msg["From"]    = cfg.get("smtp_user", "")
            msg["To"]      = to_email
            with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587)) as s:
                s.starttls()
                s.login(cfg["smtp_user"], cfg["smtp_pass"])
                s.sendmail(cfg["smtp_user"], to_email, msg.as_string())
        except Exception as e:
            logger.error(f"Email alert failed: {e}")

    def summary(self) -> str:
        if not self.alerts:
            return "No alerts triggered."
        lines = ["\n── ALERTS ──────────────────────────────────────────"]
        for a in self.alerts:
            lines.append(str(a))
        return "\n".join(lines)
