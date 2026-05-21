"""
HedgeFund AI — KARAR ASİSTANI (UI)
Pre-Trade Confidence Gate · 7 aşamalı güven kontrolü
"""
import streamlit as st
from ui_pages.styles import (
    C, page_header, render_ticker, sym_search, fmt_price, score_ring,
)


STATUS_COLOR = {
    "green":  C["buy"],
    "yellow": C["warn"],
    "red":    C["sell"],
}
STATUS_ICON = {"green": "●", "yellow": "●", "red": "●"}
STATUS_LABEL = {"green": "GÜVENLİ", "yellow": "DİKKAT", "red": "RİSKLİ"}


def _detect_asset_type(symbol: str) -> str:
    s = (symbol or "").upper()
    if "-USD" in s:        return "crypto"
    if s.endswith(".IS"):  return "bist"
    return "stock"


def _confidence_dial(score: float, tone: str, size: int = 200) -> str:
    """Büyük güven göstergesi — ring + sayı + verdict tonu."""
    col = (C["buy"] if tone == "buy"
           else C["warn"] if tone == "warn" else C["sell"])
    r    = (size - 16) / 2
    circ = 2 * 3.14159 * r
    fill = circ * (max(0, min(100, score)) / 100)
    cx = cy = size / 2
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"
     style="transform:rotate(-90deg);">
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
          stroke="{C['divider']}" stroke-width="10"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
          stroke="{col}" stroke-width="10"
          stroke-dasharray="{fill:.1f} {circ:.1f}" stroke-linecap="round"/>
  <text x="50%" y="46%" dominant-baseline="middle" text-anchor="middle"
        fill="{col}" font-size="{int(size * 0.30)}" font-weight="700"
        style="transform:rotate(90deg);transform-origin:center;
               font-family:-apple-system,sans-serif;
               font-variant-numeric:tabular-nums;">{score:.0f}</text>
  <text x="50%" y="62%" dominant-baseline="middle" text-anchor="middle"
        fill="{C['t3']}" font-size="11" font-weight="600"
        style="transform:rotate(90deg);transform-origin:center;
               font-family:-apple-system,sans-serif;
               letter-spacing:0.12em;">/ 100</text>
</svg>"""


def _check_row(check, idx: int) -> str:
    if check is None:
        return ""
    col = STATUS_COLOR.get(check.status, C["t3"])
    bg  = ("rgba(52,199,89,0.06)"  if check.status == "green"
           else "rgba(255,159,10,0.06)" if check.status == "yellow"
           else "rgba(255,59,48,0.06)")
    return f"""
<div class="card" style="margin-bottom:10px;padding:14px 16px;
     border-left:3px solid {col};background:{bg};">
  <div style="display:flex;align-items:flex-start;gap:14px;">
    <div style="flex-shrink:0;width:32px;height:32px;border-radius:50%;
                background:{col};display:flex;align-items:center;
                justify-content:center;color:#fff;font-weight:700;font-size:13px;">
      {idx}
    </div>
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:10px;
                  justify-content:space-between;flex-wrap:wrap;margin-bottom:6px;">
        <div style="font-size:14px;font-weight:600;color:{C['t1']};">
          {check.name}</div>
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:11px;font-weight:600;color:{col};
                       background:{col}1a;padding:2px 10px;border-radius:980px;
                       letter-spacing:0.06em;">{STATUS_LABEL[check.status]}</span>
          <span style="font-size:13px;font-weight:700;color:{col};
                       font-variant-numeric:tabular-nums;">
            {check.score:.0f}/100</span>
        </div>
      </div>
      <div style="font-size:14px;font-weight:500;color:{C['t1']};
                  margin-bottom:4px;">
        {check.headline}</div>
      <div style="font-size:13px;color:{C['t2']};line-height:1.5;">
        {check.detail}</div>
    </div>
  </div>
</div>"""


def render():
    render_ticker()
    page_header(
        "Karar Asistanı",
        "İşlem öncesi 7 aşamalı güven kontrolü · pozisyon, risk, zamanlama")

    st.markdown(f"""
<div class="warn-bar" style="padding:14px 18px;margin-bottom:24px;">
  <b>Pre-Trade Gate</b>&ensp;Bu modül, satın alma kararından önce
  pozisyonu boyutlandırır, tarihsel konumu test eder, olay takvimini tarar,
  duygu çelişkisini ölçer, benzer setup'ları geçmişle kıyaslar, worst-case
  kaybı hesaplar ve giriş stratejisini önerir.
  <span style="color:{C['t3']};">Kontroller geçmedikçe işlem önerilmez.</span>
</div>""", unsafe_allow_html=True)

    # ── GİRDİ FORMU ───────────────────────────────────────────────────────────
    st.markdown(f"<div class='lbl' style='margin-bottom:8px;'>İŞLEM PARAMETRELERİ</div>",
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        symbol = sym_search("da_sym", "Sembol ara (BTC, AAPL, THYAO, ...)")
    with c2:
        capital = st.number_input(
            "Toplam Sermaye", min_value=100.0, value=10000.0, step=500.0,
            key="da_capital_w")
    with c3:
        risk_profile = st.selectbox(
            "Risk Profili",
            ["korumacı", "dengeli", "agresif", "çok_agresif"],
            index=1, key="da_risk_w",
            format_func=lambda x: {
                "korumacı": "Korumacı (max %1)",
                "dengeli":   "Dengeli (max %2)",
                "agresif":   "Agresif (max %3.5)",
                "çok_agresif": "Çok Agresif (max %5)",
            }.get(x, x))

    # ── Sembol değiştiğinde mevcut piyasa fiyatını otomatik çek ──────────────
    cur_market_price = 0.0
    if symbol:
        cached = st.session_state.get("da_price_cache", {})
        if symbol in cached:
            cur_market_price = cached[symbol]
        else:
            try:
                import yfinance as yf
                cur_market_price = float(
                    yf.Ticker(symbol).fast_info.last_price or 0)
                cached[symbol] = cur_market_price
                st.session_state["da_price_cache"] = cached
            except Exception:
                cur_market_price = 0.0

        # Sembol değişince entry/stop default'larını yenile
        last_sym = st.session_state.get("da_last_sym")
        if last_sym != symbol and cur_market_price > 0:
            st.session_state["da_entry_w"] = float(round(cur_market_price, 2))
            st.session_state["da_stop_w"]  = float(round(cur_market_price * 0.92, 2))
            st.session_state["da_last_sym"] = symbol
            st.rerun()

    # Mevcut fiyat bilgi şeridi
    if cur_market_price > 0:
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;padding:10px 16px;
     background:{C['accent_dim']};border-radius:10px;margin:12px 0;
     border-left:3px solid {C['accent']};">
  <span style="font-size:11px;font-weight:600;color:{C['t3']};
               text-transform:uppercase;letter-spacing:0.06em;">
    Canlı Piyasa Fiyatı</span>
  <span style="font-size:18px;font-weight:700;color:{C['accent']};
               font-variant-numeric:tabular-nums;">
    {fmt_price(cur_market_price, 'USD')}</span>
  <span style="font-size:12px;color:{C['t3']};margin-left:auto;">
    Giriş & stop varsayılanları otomatik dolduruldu (-%8)</span>
</div>""", unsafe_allow_html=True)

    c4, c5, c6, c7 = st.columns([1, 1, 1, 1])
    with c4:
        entry_price = st.number_input(
            "Giriş Fiyatı", min_value=0.0, step=0.01,
            key="da_entry_w",
            help="Sembol seçince mevcut piyasa fiyatı otomatik gelir")
    with c5:
        stop_price = st.number_input(
            "Stop-Loss", min_value=0.0, step=0.01,
            key="da_stop_w",
            help="Otomatik %8 altında öneri — değiştirebilirsin")
    with c6:
        decision_hint = st.selectbox(
            "Yönelim",
            ["AL", "GÜÇLÜ AL", "BİRİKTİR", "İZLE", "SAT"],
            index=0, key="da_decision_w")
    with c7:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        run_btn = st.button("Güven Kontrolü Çalıştır",
                            type="primary", use_container_width=True,
                            key="da_run_w")

    if run_btn:
        if not symbol:
            st.error("Sembol seçin.")
            return
        if entry_price > 0 and stop_price > 0 and stop_price >= entry_price:
            st.error("Stop fiyatı giriş fiyatından düşük olmalı.")
            return
        st.session_state["da_run"]    = True
        st.session_state["da_symbol"] = symbol
        st.session_state["da_inputs"] = {
            "capital":       capital,
            "risk_profile":  risk_profile,
            "entry_price":   entry_price,
            "stop_price":    stop_price,
            "decision_hint": decision_hint,
        }
        st.session_state["da_report"] = None

    if st.session_state.get("da_run"):
        st.session_state["da_run"] = False
        sym  = st.session_state["da_symbol"]
        inp  = st.session_state["da_inputs"]

        with st.spinner(f"{sym} için 7 aşamalı güven kontrolü çalışıyor..."):
            try:
                # Giriş fiyatı 0 ise mevcut fiyatı al
                ep = inp["entry_price"]
                sp = inp["stop_price"]
                cur_price = ep
                if cur_price <= 0:
                    try:
                        import yfinance as yf
                        cur_price = float(
                            yf.Ticker(sym).fast_info.last_price or 0)
                    except Exception:
                        cur_price = 0
                if cur_price <= 0:
                    st.error(f"Fiyat alınamadı: {sym}")
                    return
                if ep <= 0:
                    ep = cur_price
                # Stop yoksa ATR-based varsayılan: -%8
                if sp <= 0:
                    sp = ep * 0.92

                from src.decision_assistant import build_confidence_report
                rep = build_confidence_report(
                    symbol=sym, name=sym,
                    asset_type=_detect_asset_type(sym),
                    current_price=cur_price, currency="USD",
                    capital=inp["capital"],
                    risk_profile=inp["risk_profile"],
                    entry_price=ep,
                    stop_price=sp,
                    decision_hint=inp["decision_hint"],
                )
                st.session_state["da_report"] = rep
            except Exception as e:
                st.error(f"Kontrol başarısız: {e}")
                with st.expander("Hata detayı"):
                    import traceback
                    st.code(traceback.format_exc())
                return

    rep = st.session_state.get("da_report")
    if not rep:
        st.markdown(f"""
<div style="text-align:center;padding:80px 24px;">
  <div style="font-size:48px;opacity:.10;color:{C['t3']};margin-bottom:16px;">⌬</div>
  <div style="font-size:17px;font-weight:600;color:{C['t1']};margin-bottom:8px;">
    İşlem parametrelerini doldur</div>
  <div style="font-size:14px;color:{C['t3']};max-width:480px;margin:0 auto;">
    7 kontrol: Pozisyon boyutu · Tarihsel konum · Olay takvimi ·
    Duygu çelişkisi · Benzer setup geçmişi · Worst case · Giriş stratejisi
  </div>
</div>""", unsafe_allow_html=True)
        return

    # ── ANA VERDICT KARTI ─────────────────────────────────────────────────────
    tone_col = (C["buy"] if rep.verdict_tone == "buy"
                else C["warn"] if rep.verdict_tone == "warn" else C["sell"])

    # Üst kart: dial (sol) + verdict text (sağ) — st.columns ile
    st.markdown(
        f"<div style='border-top:3px solid {tone_col};border-radius:16px 16px 0 0;"
        f"background:{C['surface']};border-left:1px solid {C['border']};"
        f"border-right:1px solid {C['border']};border-bottom:none;"
        f"padding:28px 32px 16px 32px;'>",
        unsafe_allow_html=True)

    dial_col, text_col = st.columns([1, 2])

    with dial_col:
        st.markdown(
            f"<div style='text-align:center;'>"
            f"{_confidence_dial(rep.confidence_score, rep.verdict_tone, 200)}"
            f"</div>",
            unsafe_allow_html=True)

    with text_col:
        t2_col = C["t2"]
        st.markdown(
            f"<div class='lbl'>{rep.asset_type.upper()} · {rep.symbol}</div>"
            f"<div style='font-size:32px;font-weight:700;color:{tone_col};"
            f"margin:8px 0 12px;letter-spacing:-0.01em;'>{rep.verdict_label}</div>"
            f"<div style='font-size:15px;color:{t2_col};line-height:1.55;"
            f"margin-bottom:8px;'>{rep.verdict_text}</div>",
            unsafe_allow_html=True)

    # Alt kısım: 4 metrik
    st.markdown(
        f"<div style='border-top:1px solid {C['divider']};margin:8px 0 0;"
        f"padding-top:16px;'></div>",
        unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    metric_cards = [
        (m1, "FİYAT",     fmt_price(rep.entry_price, rep.currency), C["t1"], ""),
        (m2, "STOP",      fmt_price(rep.stop_price,  rep.currency), C["sell"], ""),
        (m3, "POZİSYON",  f"${rep.suggested_position_usd:,.0f}",     C["accent"], ""),
        (m4, "MAX KAYIP", f"${rep.max_loss_usd:,.0f}",               C["warn"],
         f" · %{rep.portfolio_risk_pct:.1f}"),
    ]
    for col, lbl_m, val_m, col_m, sub_m in metric_cards:
        sub_html = (f"<span style='font-size:11px;color:{C['t3']};font-weight:500;'>"
                    f"{sub_m}</span>") if sub_m else ""
        col.markdown(
            f"<div class='lbl'>{lbl_m}</div>"
            f"<div style='font-size:20px;font-weight:700;color:{col_m};"
            f"margin-top:2px;font-variant-numeric:tabular-nums;'>"
            f"{val_m}{sub_html}</div>",
            unsafe_allow_html=True)

    # Kartın dış kapanışı + alt boşluk
    st.markdown(
        f"<div style='background:{C['surface']};border-left:1px solid {C['border']};"
        f"border-right:1px solid {C['border']};border-bottom:1px solid {C['border']};"
        f"border-radius:0 0 16px 16px;padding:0 32px 24px 32px;"
        f"margin-bottom:24px;'></div>",
        unsafe_allow_html=True)

    # ── 7 KONTROL LİSTESİ ─────────────────────────────────────────────────────
    st.markdown(f"<div class='lbl' style='margin:8px 0 12px;'>7 GÜVEN KONTROLÜ</div>",
                unsafe_allow_html=True)

    checks = [
        rep.check_position, rep.check_historic, rep.check_events,
        rep.check_sentiment, rep.check_backtest, rep.check_worst,
        rep.check_entry,
    ]
    rows_html = "".join(_check_row(c, i + 1) for i, c in enumerate(checks))
    st.markdown(rows_html, unsafe_allow_html=True)

    # ── DCA PLANI ─────────────────────────────────────────────────────────────
    if rep.dca_tiers:
        st.markdown(f"<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='lbl' style='margin-bottom:10px;'>ÖNERİLEN GİRİŞ PLANI</div>",
                    unsafe_allow_html=True)

        cols = st.columns(len(rep.dca_tiers))
        for col, tier in zip(cols, rep.dca_tiers):
            badge = (f"%{tier['pct_alloc']}")
            drop_text = (f"{tier['pct_drop']:+d}%" if tier['pct_drop'] != 0
                         else "Şimdi")
            col.markdown(f"""
<div class="card" style="padding:18px 16px;text-align:center;
     border-top:2px solid {C['accent']};">
  <div class="lbl" style="color:{C['accent']};">{tier['trigger']}</div>
  <div style="font-size:24px;font-weight:700;color:{C['accent']};
              margin:10px 0 6px;font-variant-numeric:tabular-nums;">
    {badge}</div>
  <div style="font-size:13px;color:{C['t2']};margin-bottom:8px;">
    {drop_text} · {fmt_price(tier['price'], rep.currency)}</div>
  <div style="padding-top:8px;border-top:1px solid {C['divider']};
              font-size:13px;color:{C['t1']};font-weight:600;
              font-variant-numeric:tabular-nums;">
    ${tier['amount_usd']:,.0f}</div>
  <div style="font-size:11px;color:{C['t3']};margin-top:2px;">
    {tier['units']:.6f} adet</div>
</div>""", unsafe_allow_html=True)

    # ── DETAY METRİKLER (expander) ────────────────────────────────────────────
    with st.expander("Detay Metrikler"):
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("**Pozisyon & Risk**")
            pm = rep.check_position.metrics
            st.markdown(
                f"- Stop mesafesi: %{pm.get('stop_distance_pct', 0):.2f}\n"
                f"- Risk bütçesi: ${pm.get('max_loss_budget', 0):,.0f}\n"
                f"- Pozisyon: ${pm.get('position_usd', 0):,.0f}\n"
                f"- Birim sayısı: {pm.get('units', 0):.6f}"
            )

            wm = rep.check_worst.metrics
            st.markdown("**Worst Case**")
            st.markdown(
                f"- Yıllık volatilite: %{wm.get('annual_vol', 0):.1f}\n"
                f"- 30g %95 VaR: -${wm.get('var_95_usd', 0):,.0f} (-%{wm.get('var_95_pct', 0):.1f})\n"
                f"- 30g %99 VaR: -${wm.get('var_99_usd', 0):,.0f} (-%{wm.get('var_99_pct', 0):.1f})\n"
                f"- Tarihsel max 30g DD: {wm.get('hist_max_dd', 0):.1f}%"
            )

        with m2:
            hm = rep.check_historic.metrics
            st.markdown("**Tarihsel Konum**")
            st.markdown(
                f"- 1Y range içinde: %{hm.get('percentile', 0):.0f}\n"
                f"- ATH (1Y): {fmt_price(hm.get('ath_1y', 0), rep.currency)} "
                f"({hm.get('dist_from_ath', 0):+.1f}%)\n"
                f"- ATL (1Y): {fmt_price(hm.get('atl_1y', 0), rep.currency)} "
                f"({hm.get('dist_from_atl', 0):+.1f}%)\n"
                f"- 200 EMA mesafesi: {hm.get('dist_from_ema200', 0):+.1f}%"
            )

            bm = rep.check_backtest.metrics
            st.markdown("**Setup Backtest**")
            st.markdown(
                f"- Mevcut RSI: {bm.get('current_rsi', 0):.1f}\n"
                f"- Benzer örnek: {bm.get('samples', 0)}\n"
                f"- Pozitif çıkma: %{bm.get('pct_positive', 0):.0f}\n"
                f"- Medyan getiri (30g): {bm.get('median_return', 0):+.1f}%"
            )

        # Olay takvimi tablosu
        ev_metrics = rep.check_events.metrics
        events = ev_metrics.get("events", [])
        if events:
            st.markdown("**Olay Takvimi (14 gün)**")
            import pandas as pd
            ev_df = pd.DataFrame(events)
            st.dataframe(ev_df, hide_index=True, use_container_width=True)

    # ── AKSİYON BUTONLARI ─────────────────────────────────────────────────────
    st.markdown(f"<div style='height:16px'></div>", unsafe_allow_html=True)

    a1, a2, a3 = st.columns([2, 2, 1])
    with a1:
        if st.button("✓ İşlemi Onayla & Journal'a Kaydet",
                     type="primary", use_container_width=True,
                     key="da_confirm_btn"):
            try:
                from src.decision_assistant import log_trade_decision
                user_email = st.session_state.get("user_email", "anon")
                rid = log_trade_decision(user_email, rep,
                                         notes=f"Verdict: {rep.verdict_label}")
                st.success(f"Trade journal'a kaydedildi (#{rid}). "
                           f"Aşağıda DCA planını uygulayabilirsin.")
            except Exception as e:
                st.error(f"Kayıt başarısız: {e}")
    with a2:
        if st.button("↻ Yeni Kontrol Çalıştır",
                     use_container_width=True, key="da_reset_btn"):
            st.session_state["da_report"] = None
            st.rerun()
    with a3:
        if st.button("✗ Vazgeç", use_container_width=True, key="da_cancel_btn"):
            st.session_state["da_report"] = None
            st.rerun()

    # ── JOURNAL GEÇMİŞİ ───────────────────────────────────────────────────────
    with st.expander("Trade Journal Geçmişi"):
        try:
            from src.decision_assistant import list_trade_decisions
            user_email = st.session_state.get("user_email", "anon")
            history = list_trade_decisions(user_email, limit=20)
            if not history:
                empty_col = C["t3"]
                st.markdown(
                    f"<div style='color:{empty_col};font-size:13px;'>"
                    f"Henüz kaydedilmiş işlem yok.</div>",
                    unsafe_allow_html=True)
            else:
                import pandas as pd
                rows = [{
                    "Tarih":      h["created_at"],
                    "Sembol":     h["symbol"],
                    "Karar":      h["decision"],
                    "Güven":      f"{h['confidence']:.0f}",
                    "Verdict":    h["verdict_label"],
                    "Pozisyon":   f"${h['position_usd']:,.0f}",
                    "Max Kayıp":  f"${h['max_loss_usd']:,.0f}",
                } for h in history]
                st.dataframe(pd.DataFrame(rows),
                             hide_index=True, use_container_width=True)
        except Exception as e:
            st.warning(f"Journal okunamadı: {e}")
