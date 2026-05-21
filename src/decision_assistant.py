"""
HedgeFund AI — KARAR ASİSTANI (Pre-Trade Confidence Gate)

Bir varlığı satın almadan önce 7 aşamalı güven kontrolünden geçirir:
  1. Pozisyon Boyutlandırma   (Kelly-lite, risk-based sizing)
  2. Tarihsel Konum            (Fiyat 1Y range içinde nerede?)
  3. Olay Takvimi              (Önümüzdeki 14 gün: FOMC, kazanç, halving)
  4. Duygu Çelişkisi           (Crowd sentiment vs decision — F&G)
  5. Benzer Setup Backtest     (Aynı RSI bucket'ında geçmiş forward return)
  6. Worst Case Simülasyonu    (95% & 99% VaR — 30 günlük)
  7. Giriş Stratejisi          (DCA önerisi vs lump-sum)

Her kontrol 0-100 puan ve {'green'|'yellow'|'red'} sinyal döner.
Toplam Güven Skoru → 4 verdict: ALABİLİRSİN / DİKKATLE / BEKLE / ALMA
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# Risk profili → işlem başına maks. portföy riski (%)
RISK_BUDGETS = {
    "korumacı":      1.0,
    "dengeli":       2.0,
    "dengeli_agresif": 2.5,
    "orta":          2.0,
    "orta_riskli":   2.5,
    "agresif":       3.5,
    "riskli":        3.5,
    "çok_agresif":   5.0,
    "çok_riskli":    5.0,
    "ultra_agresif": 6.0,
}

# Bilinen FOMC toplantıları 2025–2026 (Fed kararı günleri)
FOMC_DATES = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# Bilinen büyük kripto olayları
CRYPTO_EVENTS = [
    ("2024-04-19", "BTC Halving (geçmiş)"),
    ("2028-04-15", "BTC Halving (tahmini)"),
]

# Verdict eşikleri
VERDICT_THRESHOLDS = [
    (78, "✓ ALABİLİRSİN",  "İçin rahat olabilir — setup güçlü.",                "buy"),
    (60, "⏸ DİKKATLE GİR", "Setup uygun ama bazı uyarılar var. DCA önerilir.",  "warn"),
    (40, "⚠ BEKLE",         "Riskler ağır basıyor. Daha iyi setup bekle.",       "warn"),
    (0,  "✗ ALMA",          "Şu an bu varlık için doğru zaman değil.",           "sell"),
]

# Ağırlıklar (toplam = 100)
WEIGHTS = {
    "position":  20,
    "historic":  15,
    "events":    10,
    "sentiment": 10,
    "backtest":  20,
    "worst":     15,
    "entry":     10,
}


# ══════════════════════════════════════════════════════════════════════════════
# RESULT DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CheckResult:
    name: str
    score: float = 0.0           # 0-100
    status: str = "yellow"       # "green" | "yellow" | "red"
    headline: str = ""           # Tek satır özet
    detail: str = ""             # Açıklama paragrafı
    metrics: dict = field(default_factory=dict)


@dataclass
class ConfidenceReport:
    symbol: str = ""
    name: str = ""
    asset_type: str = ""
    current_price: float = 0.0
    currency: str = "USD"

    # Girdiler
    capital: float = 0.0
    risk_profile: str = "dengeli"
    entry_price: float = 0.0
    stop_price: float = 0.0
    decision_hint: str = ""      # Mevcut analizden gelen karar

    # 7 kontrol
    check_position:  Optional[CheckResult] = None
    check_historic:  Optional[CheckResult] = None
    check_events:    Optional[CheckResult] = None
    check_sentiment: Optional[CheckResult] = None
    check_backtest:  Optional[CheckResult] = None
    check_worst:     Optional[CheckResult] = None
    check_entry:     Optional[CheckResult] = None

    # Toplam
    confidence_score: float = 0.0
    verdict_label:    str   = ""
    verdict_text:     str   = ""
    verdict_tone:     str   = "warn"   # "buy" | "warn" | "sell"

    # Önerilen işlem planı
    suggested_position_usd: float  = 0.0
    suggested_units:        float  = 0.0
    max_loss_usd:           float  = 0.0
    portfolio_risk_pct:     float  = 0.0
    dca_tiers:              list   = field(default_factory=list)
    # [{"pct_alloc": 40, "trigger": "Bugün (mevcut fiyat)", "price": 100.0, "amount_usd": 400}]


# ══════════════════════════════════════════════════════════════════════════════
# YARDIMCI: Veri çekme
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_history(symbol: str, period: str = "2y") -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.warning(f"History fetch failed: {symbol}: {e}")
        return None


def _calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs    = gain / loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def _annual_volatility(close: pd.Series) -> float:
    rets = np.log(close / close.shift(1)).dropna()
    if len(rets) < 20:
        return 30.0
    return float(rets.std() * np.sqrt(252) * 100)


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — POZİSYON BOYUTLANDIRMA
# ══════════════════════════════════════════════════════════════════════════════

def check_position_sizing(
    capital: float,
    risk_profile: str,
    entry_price: float,
    stop_price: Optional[float],
) -> tuple[CheckResult, dict]:
    """
    Kelly-lite: işlem başına portföyün en fazla X%'i risk edilir.
    Bu risk + stop mesafesi → max pozisyon büyüklüğü.
    """
    risk_pct = RISK_BUDGETS.get(risk_profile, 2.0)
    max_loss_budget = capital * risk_pct / 100

    if not stop_price or stop_price >= entry_price or entry_price <= 0:
        return CheckResult(
            name="Pozisyon Boyutlandırma",
            score=35, status="red",
            headline="Stop seviyesi tanımsız",
            detail=("Risk yönetimi için stop-loss şart. Stop olmadan pozisyon "
                    "büyüklüğü hesaplanamaz, kayıp limiti yoktur."),
            metrics={"risk_pct": risk_pct, "max_loss_budget": max_loss_budget,
                     "position_usd": 0, "units": 0},
        ), {"position_usd": 0, "units": 0, "max_loss_usd": 0,
            "portfolio_risk_pct": 0}

    stop_distance_pct = (entry_price - stop_price) / entry_price * 100
    position_usd      = max_loss_budget / (stop_distance_pct / 100)
    # Pozisyon, sermayenin maks %30'unu aşmasın
    if position_usd > capital * 0.30:
        position_usd = capital * 0.30
        actual_loss  = position_usd * stop_distance_pct / 100
        actual_risk_pct = actual_loss / capital * 100
    else:
        actual_loss     = max_loss_budget
        actual_risk_pct = risk_pct

    units = position_usd / entry_price

    if stop_distance_pct < 1.5:
        score, status = 55, "yellow"
        headline = "Stop çok yakın — slippage riski"
        detail   = (f"Stop sadece %{stop_distance_pct:.1f} uzakta. Bu kadar "
                    f"sıkı stop volatil piyasada erken tetiklenebilir.")
    elif stop_distance_pct > 15:
        score, status = 60, "yellow"
        headline = "Stop çok geniş — pozisyon küçülüyor"
        detail   = (f"Stop %{stop_distance_pct:.1f} uzakta. Bu, pozisyonu "
                    f"çok küçültür ve fırsat maliyeti yaratır.")
    else:
        score, status = 90, "green"
        headline = f"Sağlıklı sizing · Stop %{stop_distance_pct:.1f} uzakta"
        detail   = (f"Risk profilin '{risk_profile}' → işlem başına maks "
                    f"%{risk_pct:.1f} portföy riski.")

    metrics = {
        "risk_pct":            actual_risk_pct,
        "stop_distance_pct":   stop_distance_pct,
        "max_loss_budget":     max_loss_budget,
        "position_usd":        position_usd,
        "units":               units,
        "actual_loss":         actual_loss,
    }
    plan = {
        "position_usd":       position_usd,
        "units":              units,
        "max_loss_usd":       actual_loss,
        "portfolio_risk_pct": actual_risk_pct,
    }
    return CheckResult(
        name="Pozisyon Boyutlandırma", score=score, status=status,
        headline=headline, detail=detail, metrics=metrics,
    ), plan


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — TARİHSEL KONUM
# ══════════════════════════════════════════════════════════════════════════════

def check_historical_position(
    symbol: str,
    current_price: float,
    df: Optional[pd.DataFrame] = None,
) -> CheckResult:
    if df is None:
        df = _fetch_history(symbol, "1y")
    if df is None or len(df) < 60:
        return CheckResult(
            name="Tarihsel Konum", score=50, status="yellow",
            headline="Yetersiz tarihsel veri",
            detail="Geçmiş 1 yıllık fiyat verisi alınamadı; konum analizi yapılamadı.",
        )

    close = df["Close"].dropna()
    p_min = float(close.min())
    p_max = float(close.max())
    ath_1y = p_max
    atl_1y = p_min

    pct_in_range = ((current_price - p_min) / (p_max - p_min) * 100
                    if p_max > p_min else 50.0)
    dist_from_ath = (current_price - ath_1y) / ath_1y * 100
    dist_from_atl = (current_price - atl_1y) / atl_1y * 100

    ema200 = close.ewm(span=200).mean().iloc[-1] if len(close) >= 50 else None
    dist_from_ema200 = ((current_price - float(ema200)) / float(ema200) * 100
                        if ema200 else 0)

    if pct_in_range >= 88:
        score, status = 32, "red"
        headline = f"Tepe bölgesinde · 1Y range %{pct_in_range:.0f}'inde"
        detail   = (f"Fiyat 1 yıllık aralığın üst %{100-pct_in_range:.0f}'unda. "
                    f"ATH'a yalnızca %{abs(dist_from_ath):.1f} mesafede. "
                    f"Geri çekilme riski yüksek.")
    elif pct_in_range >= 70:
        score, status = 58, "yellow"
        headline = f"Aralığın üst kısmında · %{pct_in_range:.0f}"
        detail   = (f"Fiyat aralığın üst %{100-pct_in_range:.0f}'unda. "
                    f"ATH'dan -%{abs(dist_from_ath):.1f}. Yeni bir pivot "
                    f"oluşmazsa direnç bekle.")
    elif pct_in_range >= 35:
        score, status = 88, "green"
        headline = f"Sağlıklı orta bölge · %{pct_in_range:.0f}"
        detail   = (f"Fiyat orta bölgede ({pct_in_range:.0f} pct rank). "
                    f"ATL'den +%{abs(dist_from_atl):.1f}, ATH'dan "
                    f"-%{abs(dist_from_ath):.1f}.")
    else:
        score, status = 78, "green"
        headline = f"Aralığın alt kısmında · %{pct_in_range:.0f}"
        detail   = (f"Fiyat alt %{pct_in_range:.0f}'de. Dip yakını olabilir "
                    f"ama trend de zayıf olabilir — destek seviyesini doğrula.")

    return CheckResult(
        name="Tarihsel Konum", score=score, status=status,
        headline=headline, detail=detail,
        metrics={
            "percentile":      pct_in_range,
            "dist_from_ath":   dist_from_ath,
            "dist_from_atl":   dist_from_atl,
            "dist_from_ema200": dist_from_ema200,
            "ath_1y":          ath_1y,
            "atl_1y":          atl_1y,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — OLAY TAKVİMİ
# ══════════════════════════════════════════════════════════════════════════════

def check_event_calendar(symbol: str, asset_type: str) -> CheckResult:
    today = date.today()
    horizon = today + timedelta(days=14)
    events: list[dict] = []

    # FOMC
    for d in FOMC_DATES:
        ed = datetime.strptime(d, "%Y-%m-%d").date()
        if today <= ed <= horizon:
            events.append({
                "date":     ed.isoformat(),
                "days_to":  (ed - today).days,
                "name":     "FOMC Faiz Kararı",
                "impact":   "yüksek",
            })

    # Crypto events
    if asset_type == "crypto":
        for d, name in CRYPTO_EVENTS:
            ed = datetime.strptime(d, "%Y-%m-%d").date()
            if today <= ed <= horizon:
                events.append({
                    "date":    ed.isoformat(),
                    "days_to": (ed - today).days,
                    "name":    name,
                    "impact":  "yüksek",
                })

    # Hisse — yfinance .calendar (kazanç tarihi)
    if asset_type in ("stock", "bist"):
        try:
            import yfinance as yf
            cal = yf.Ticker(symbol).calendar
            if cal is not None and len(cal) > 0:
                # cal bazen dict, bazen DataFrame döner
                ed = None
                if isinstance(cal, dict):
                    e = cal.get("Earnings Date")
                    if isinstance(e, list) and e:
                        ed = pd.to_datetime(e[0]).date()
                    elif e:
                        ed = pd.to_datetime(e).date()
                else:
                    try:
                        ed = pd.to_datetime(cal.iloc[0, 0]).date()
                    except Exception:
                        ed = None
                if ed and today <= ed <= horizon:
                    events.append({
                        "date":    ed.isoformat(),
                        "days_to": (ed - today).days,
                        "name":    "Kazanç Açıklaması (Earnings)",
                        "impact":  "yüksek",
                    })
        except Exception:
            pass

    # Skor hesapla
    n_high = sum(1 for e in events if e["impact"] == "yüksek")
    if n_high == 0:
        score, status = 92, "green"
        headline = "Önümüzdeki 14 günde önemli olay yok"
        detail   = "Takvim sakin — pozisyon açmak için uygun pencere."
    elif n_high == 1:
        score, status = 60, "yellow"
        e = events[0]
        headline = f"{e['days_to']} gün sonra: {e['name']}"
        detail   = (f"{e['date']} tarihindeki {e['name']} fiyatta yüksek "
                    f"volatiliteye yol açabilir. Pozisyon büyüklüğünü gözden "
                    f"geçir veya olay sonrasını bekle.")
    else:
        score, status = 38, "red"
        names = " · ".join(e["name"] for e in events[:3])
        headline = f"{n_high} yüksek-etki olay: {names}"
        detail   = (f"Önümüzdeki 14 günde birden fazla yüksek-etki olay var. "
                    f"Fiyat hareketi öngörülemez — beklemek daha sağlıklı.")

    return CheckResult(
        name="Olay Takvimi", score=score, status=status,
        headline=headline, detail=detail,
        metrics={"events": events, "n_events": len(events)},
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — DUYGU ÇELİŞKİSİ (Crowd vs Decision)
# ══════════════════════════════════════════════════════════════════════════════

def check_sentiment_conflict(decision: str, asset_type: str) -> CheckResult:
    try:
        from src.fear_greed import fetch_fear_greed
        fg = fetch_fear_greed()
        fg_value = fg.get("value", 50)
        fg_label = fg.get("label", "Neutral")
    except Exception:
        fg_value, fg_label = 50, "Neutral"

    # F&G crypto-spesifik ama market geneli için de gösterge
    is_buy = decision in ("GÜÇLÜ AL", "AL", "BİRİKTİR", "BUY", "STRONG_BUY")
    is_sell = decision in ("SAT", "AZALT", "KAÇIN", "SELL", "STRONG_SELL")

    if is_buy:
        if fg_value <= 25:
            score, status = 95, "green"
            headline = f"Aşırı Korku ({fg_value}) + AL = kontrarian fırsat"
            detail   = ("Piyasa panikte ama sen AL diyorsun — bu klasik "
                        "smart-money zonu. Tarihsel olarak en iyi alımlar "
                        "korku zirvesinde yapıldı.")
        elif fg_value <= 45:
            score, status = 82, "green"
            headline = f"Korku ({fg_value}) + AL = duygu uyumlu"
            detail   = "Piyasa temkinli, sen pozitif. Crowd seni desteklemiyor — bu iyi."
        elif fg_value <= 65:
            score, status = 72, "green"
            headline = f"Nötr duygu ({fg_value}) + AL"
            detail   = "Piyasada belirgin uç yok. Karar fundamentals'a bağlı."
        elif fg_value <= 80:
            score, status = 50, "yellow"
            headline = f"Açgözlülük ({fg_value}) + AL = dikkat"
            detail   = ("Herkes alıyor ve sen de alıyorsun — bu pozisyon "
                        "geç kalmış olabilir. Düzeltme riski yüksek.")
        else:
            score, status = 28, "red"
            headline = f"Aşırı Açgözlülük ({fg_value}) + AL = riskli"
            detail   = ("Piyasa euforide. Tarihsel olarak F&G > 80 zonunda "
                        "yapılan alımlar 2-4 hafta içinde -%15+ düzeltme görür.")
    elif is_sell:
        if fg_value >= 75:
            score, status = 92, "green"
            headline = f"Açgözlülük ({fg_value}) + SAT = doğru zaman"
            detail   = "Crowd açgözlü, sen satıyorsun — disiplinli kâr alma."
        elif fg_value <= 25:
            score, status = 35, "red"
            headline = f"Aşırı Korku ({fg_value}) + SAT = duygusal karar olabilir"
            detail   = ("Panikte satmak çoğu zaman dipte satmak demek. "
                        "Kararı sorgula.")
        else:
            score, status = 65, "yellow"
            headline = f"Nötr duygu ({fg_value}) + SAT"
            detail   = "Satış için aşırı bir tetik yok. Kâr alma planı netleşmiş olmalı."
    else:
        score, status = 70, "green"
        headline = f"F&G: {fg_value} ({fg_label}) — pasif karar"
        detail   = "İzleme/bekleme kararı, duygu çatışması yaratmaz."

    return CheckResult(
        name="Duygu Çelişkisi", score=score, status=status,
        headline=headline, detail=detail,
        metrics={"fg_value": fg_value, "fg_label": fg_label,
                 "decision": decision},
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — BENZER SETUP BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def check_similar_setup_backtest(
    symbol: str,
    df: Optional[pd.DataFrame] = None,
    forward_days: int = 30,
    rsi_bucket: int = 5,
) -> CheckResult:
    """
    Geçmiş 2 yıl boyunca, RSI bugünkü değerin ±bucket aralığında olduğu günleri bul.
    Her birinden forward_days sonrası getiriyi hesapla.
    """
    if df is None:
        df = _fetch_history(symbol, "2y")
    if df is None or len(df) < forward_days + 60:
        return CheckResult(
            name="Benzer Setup Backtest", score=50, status="yellow",
            headline="Backtest için yetersiz veri",
            detail=f"En az {forward_days + 60} günlük veri gerekli.",
        )

    close = df["Close"].dropna()
    rsi   = _calc_rsi(close).dropna()
    if len(rsi) < forward_days + 30:
        return CheckResult(
            name="Benzer Setup Backtest", score=50, status="yellow",
            headline="RSI hesaplaması başarısız", detail="",
        )

    cur_rsi  = float(rsi.iloc[-1])
    lo, hi   = cur_rsi - rsi_bucket, cur_rsi + rsi_bucket

    # Aday günler — forward_days alanı kalan günler
    candidates = rsi.iloc[:-forward_days]
    candidates = candidates[(candidates >= lo) & (candidates <= hi)]
    if len(candidates) < 5:
        return CheckResult(
            name="Benzer Setup Backtest", score=55, status="yellow",
            headline=f"Yeterli benzer setup bulunamadı (RSI ≈ {cur_rsi:.0f})",
            detail=f"Sadece {len(candidates)} örnek bulundu. İstatistiki anlam zayıf.",
            metrics={"current_rsi": cur_rsi, "samples": len(candidates)},
        )

    fwd_rets = []
    for ts in candidates.index:
        try:
            entry_p = float(close.loc[ts])
            future_idx = close.index.get_loc(ts) + forward_days
            if future_idx >= len(close):
                continue
            exit_p  = float(close.iloc[future_idx])
            fwd_rets.append((exit_p - entry_p) / entry_p * 100)
        except Exception:
            continue

    if len(fwd_rets) < 5:
        return CheckResult(
            name="Benzer Setup Backtest", score=55, status="yellow",
            headline="Hesaplama yapılamadı",
            detail="", metrics={"samples": len(fwd_rets)},
        )

    arr = np.array(fwd_rets)
    n          = len(arr)
    median_ret = float(np.median(arr))
    mean_ret   = float(np.mean(arr))
    pct_pos    = float((arr > 0).mean() * 100)
    pct_5plus  = float((arr > 5).mean() * 100)
    worst      = float(np.min(arr))
    best       = float(np.max(arr))

    if pct_pos >= 70 and median_ret > 3:
        score, status = 92, "green"
        headline = (f"%{pct_pos:.0f} başarılı · medyan +%{median_ret:.1f} "
                    f"({n} benzer setup)")
        detail   = (f"Son 2 yılda RSI≈{cur_rsi:.0f} olan {n} günden "
                    f"%{pct_pos:.0f}'i {forward_days} gün içinde pozitif "
                    f"getiri sağladı. Medyan: +%{median_ret:.1f}, "
                    f"en kötü: %{worst:.1f}, en iyi: +%{best:.1f}.")
    elif pct_pos >= 55:
        score, status = 70, "green"
        headline = (f"%{pct_pos:.0f} başarılı · medyan {median_ret:+.1f}% "
                    f"({n} setup)")
        detail   = (f"İstatistik makul. Geçmiş %{pct_pos:.0f} başarı oranı "
                    f"ile {forward_days} gün vade için elverişli.")
    elif pct_pos >= 40:
        score, status = 50, "yellow"
        headline = (f"Karışık geçmiş · %{pct_pos:.0f} başarı, "
                    f"medyan {median_ret:+.1f}%")
        detail   = (f"Bu setup geçmişte 50/50'ye yakın. Edge net değil — "
                    f"farklı tetikleyiciler arayabilirsin.")
    else:
        score, status = 28, "red"
        headline = (f"Zayıf geçmiş · sadece %{pct_pos:.0f} başarı "
                    f"({n} setup)")
        detail   = (f"Aynı RSI bölgesinde {n} kez pozisyon açıldı, sadece "
                    f"%{pct_pos:.0f}'ı kazandırdı. Medyan {median_ret:+.1f}%.")

    return CheckResult(
        name="Benzer Setup Backtest", score=score, status=status,
        headline=headline, detail=detail,
        metrics={
            "current_rsi": cur_rsi, "samples": n,
            "pct_positive": pct_pos, "pct_5plus": pct_5plus,
            "median_return": median_ret, "mean_return": mean_ret,
            "worst": worst, "best": best,
            "forward_days": forward_days,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 6 — WORST CASE (VaR)
# ══════════════════════════════════════════════════════════════════════════════

def check_worst_case(
    symbol: str,
    position_usd: float,
    horizon_days: int = 30,
    df: Optional[pd.DataFrame] = None,
    risk_profile: str = "dengeli",
) -> CheckResult:
    if df is None:
        df = _fetch_history(symbol, "2y")
    if df is None or len(df) < 60:
        return CheckResult(
            name="Worst Case Simülasyonu", score=50, status="yellow",
            headline="Volatilite hesaplanamadı",
            detail="",
        )

    close = df["Close"].dropna()
    rets  = np.log(close / close.shift(1)).dropna()
    daily_vol = float(rets.std())
    horizon_vol = daily_vol * np.sqrt(horizon_days)

    # Parametrik VaR (normal dağılım varsayımı)
    z_95, z_99 = 1.645, 2.326
    var_95_pct  = horizon_vol * z_95 * 100
    var_99_pct  = horizon_vol * z_99 * 100
    var_95_usd  = position_usd * var_95_pct / 100
    var_99_usd  = position_usd * var_99_pct / 100

    # Tarihsel max drawdown (rolling 30g)
    rolling_max = close.rolling(window=horizon_days).max()
    drawdowns   = (close - rolling_max) / rolling_max * 100
    hist_max_dd = float(drawdowns.min())

    # Risk profili → tolerans
    tolerance_pct = {"korumacı": 8, "dengeli": 15, "agresif": 25,
                     "çok_agresif": 40, "ultra_agresif": 60}.get(
                         risk_profile, 15)

    if var_95_pct <= tolerance_pct * 0.6:
        score, status = 88, "green"
        headline = (f"Worst case kabul edilebilir · %95 VaR: "
                    f"-${var_95_usd:,.0f} (-%{var_95_pct:.1f})")
        detail   = (f"30 günlük %95 VaR pozisyonun %{var_95_pct:.1f}'i. "
                    f"Risk toleransının (%{tolerance_pct}) altında. "
                    f"Tarihsel maks. 30g düşüş: {hist_max_dd:.1f}%.")
    elif var_95_pct <= tolerance_pct:
        score, status = 65, "yellow"
        headline = (f"Sınırda risk · %95 VaR: -${var_95_usd:,.0f} "
                    f"(-%{var_95_pct:.1f})")
        detail   = (f"Worst case toleransına yakın. %99 senaryoda "
                    f"-${var_99_usd:,.0f} (-%{var_99_pct:.1f}) kayıp olası. "
                    f"Pozisyonu küçültmeyi düşün.")
    else:
        score, status = 30, "red"
        headline = (f"Yüksek worst case · -${var_95_usd:,.0f} "
                    f"(-%{var_95_pct:.1f})")
        detail   = (f"Worst case kayıp risk toleransını (%{tolerance_pct}) "
                    f"aşıyor. Pozisyonu yarıya indir veya stop'u sıkılaştır.")

    return CheckResult(
        name="Worst Case Simülasyonu", score=score, status=status,
        headline=headline, detail=detail,
        metrics={
            "var_95_pct": var_95_pct, "var_95_usd": var_95_usd,
            "var_99_pct": var_99_pct, "var_99_usd": var_99_usd,
            "hist_max_dd": hist_max_dd,
            "annual_vol": float(daily_vol * np.sqrt(252) * 100),
            "tolerance_pct": tolerance_pct,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 7 — GİRİŞ STRATEJİSİ (DCA vs LUMP)
# ══════════════════════════════════════════════════════════════════════════════

def check_entry_strategy(
    symbol: str,
    entry_price: float,
    position_usd: float,
    df: Optional[pd.DataFrame] = None,
) -> tuple[CheckResult, list]:
    if df is None:
        df = _fetch_history(symbol, "1y")

    if df is None or len(df) < 30:
        annual_vol = 35.0
    else:
        annual_vol = _annual_volatility(df["Close"].dropna())

    tiers: list[dict] = []

    if annual_vol >= 60:
        # Yüksek vol: 4 dilim
        plan = [(30, 0,    "Bugün (mevcut fiyat)"),
                (25, -7,   "-%7 düzeltmede"),
                (25, -15,  "-%15 düzeltmede"),
                (20, -25,  "-%25 düzeltmede")]
        score, status = 85, "green"
        headline = f"Yüksek volatilite (%{annual_vol:.0f}) — 4 dilimli DCA"
        detail   = ("Bu varlığın volatilitesi yüksek. Tek seferde girmek "
                    "kötü zamanlama riski yaratır. 4 dilimli kademeli alım "
                    "ortalama maliyetini önemli ölçüde iyileştirir.")
    elif annual_vol >= 35:
        plan = [(40, 0,   "Bugün (mevcut fiyat)"),
                (35, -5,  "-%5 düzeltmede"),
                (25, -12, "-%12 düzeltmede")]
        score, status = 88, "green"
        headline = f"Orta volatilite (%{annual_vol:.0f}) — 3 dilimli DCA"
        detail   = ("Volatilite sağlıklı seviyede. 3 dilimli alım hem "
                    "anında pozisyon kazandırır hem de düzeltme fırsatlarını "
                    "değerlendirir.")
    elif annual_vol >= 20:
        plan = [(60, 0,  "Bugün (mevcut fiyat)"),
                (40, -5, "-%5 düzeltmede")]
        score, status = 90, "green"
        headline = f"Düşük volatilite (%{annual_vol:.0f}) — 2 dilimli giriş"
        detail   = ("Volatilite düşük, fiyat stabil. 60/40 ile büyük kısmı "
                    "şimdi al, geri kalanı küçük düzeltmede ekle.")
    else:
        plan = [(100, 0, "Bugün (mevcut fiyat)")]
        score, status = 92, "green"
        headline = (f"Çok düşük volatilite (%{annual_vol:.0f}) — "
                    f"lump-sum uygun")
        detail   = ("Volatilite minimal — DCA istatistiki olarak avantaj "
                    "sağlamaz. Tek seferde girmek bekleme maliyetini önler.")

    # Tier listesi
    for pct_alloc, pct_drop, label in plan:
        tier_price  = entry_price * (1 + pct_drop / 100)
        tier_amount = position_usd * pct_alloc / 100
        tier_units  = tier_amount / tier_price
        tiers.append({
            "pct_alloc":  pct_alloc,
            "pct_drop":   pct_drop,
            "trigger":    label,
            "price":      tier_price,
            "amount_usd": tier_amount,
            "units":      tier_units,
        })

    return CheckResult(
        name="Giriş Stratejisi", score=score, status=status,
        headline=headline, detail=detail,
        metrics={"annual_vol": annual_vol, "n_tiers": len(plan)},
    ), tiers


# ══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON: TAM RAPOR ÜRET
# ══════════════════════════════════════════════════════════════════════════════

def build_confidence_report(
    symbol: str,
    name: str,
    asset_type: str,
    current_price: float,
    currency: str,
    capital: float,
    risk_profile: str,
    entry_price: float,
    stop_price: Optional[float],
    decision_hint: str = "",
) -> ConfidenceReport:
    """
    Tek çağrıda 7 kontrolü yapar, ConfidenceReport döner.
    """
    rep = ConfidenceReport(
        symbol=symbol, name=name, asset_type=asset_type,
        current_price=current_price, currency=currency,
        capital=capital, risk_profile=risk_profile,
        entry_price=entry_price, stop_price=stop_price or 0,
        decision_hint=decision_hint,
    )

    # Veriyi bir kez çek, her checke pasla
    df = _fetch_history(symbol, "2y")

    # 1. Pozisyon
    pos_check, plan = check_position_sizing(
        capital, risk_profile, entry_price, stop_price)
    rep.check_position           = pos_check
    rep.suggested_position_usd   = plan["position_usd"]
    rep.suggested_units          = plan["units"]
    rep.max_loss_usd             = plan["max_loss_usd"]
    rep.portfolio_risk_pct       = plan["portfolio_risk_pct"]

    # 2. Tarihsel
    rep.check_historic = check_historical_position(symbol, current_price, df=df)

    # 3. Olaylar
    rep.check_events = check_event_calendar(symbol, asset_type)

    # 4. Duygu
    rep.check_sentiment = check_sentiment_conflict(decision_hint, asset_type)

    # 5. Backtest
    rep.check_backtest = check_similar_setup_backtest(symbol, df=df)

    # 6. Worst case (pozisyon büyüklüğü ile)
    rep.check_worst = check_worst_case(
        symbol, rep.suggested_position_usd, horizon_days=30,
        df=df, risk_profile=risk_profile)

    # 7. Giriş stratejisi
    entry_check, tiers = check_entry_strategy(
        symbol, entry_price, rep.suggested_position_usd, df=df)
    rep.check_entry = entry_check
    rep.dca_tiers   = tiers

    # ── Ağırlıklı toplam skor
    total = (
        rep.check_position.score  * WEIGHTS["position"]  +
        rep.check_historic.score  * WEIGHTS["historic"]  +
        rep.check_events.score    * WEIGHTS["events"]    +
        rep.check_sentiment.score * WEIGHTS["sentiment"] +
        rep.check_backtest.score  * WEIGHTS["backtest"]  +
        rep.check_worst.score     * WEIGHTS["worst"]     +
        rep.check_entry.score     * WEIGHTS["entry"]
    ) / 100
    rep.confidence_score = float(total)

    # Verdict
    for threshold, label, text, tone in VERDICT_THRESHOLDS:
        if rep.confidence_score >= threshold:
            rep.verdict_label = label
            rep.verdict_text  = text
            rep.verdict_tone  = tone
            break

    return rep


# ══════════════════════════════════════════════════════════════════════════════
# TRADE JOURNAL (Onaylanan kararları kaydet)
# ══════════════════════════════════════════════════════════════════════════════

DB_PATH = Path(__file__).parent.parent / "data" / "trade_journal.db"
DB_PATH.parent.mkdir(exist_ok=True)


def _init_journal_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_journal (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email      TEXT,
            symbol          TEXT,
            asset_type      TEXT,
            decision        TEXT,
            confidence      REAL,
            entry_price     REAL,
            stop_price      REAL,
            position_usd    REAL,
            units           REAL,
            max_loss_usd    REAL,
            portfolio_risk  REAL,
            verdict_label   TEXT,
            notes           TEXT,
            dca_plan        TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


_init_journal_db()


def log_trade_decision(
    user_email: str,
    report: ConfidenceReport,
    notes: str = "",
) -> int:
    import json
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute(
        """INSERT INTO trade_journal
           (user_email, symbol, asset_type, decision, confidence,
            entry_price, stop_price, position_usd, units,
            max_loss_usd, portfolio_risk, verdict_label, notes, dca_plan)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_email, report.symbol, report.asset_type, report.decision_hint,
         report.confidence_score, report.entry_price, report.stop_price,
         report.suggested_position_usd, report.suggested_units,
         report.max_loss_usd, report.portfolio_risk_pct,
         report.verdict_label, notes, json.dumps(report.dca_tiers)),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def list_trade_decisions(user_email: str, limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM trade_journal WHERE user_email=? "
        "ORDER BY created_at DESC LIMIT ?",
        (user_email, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
