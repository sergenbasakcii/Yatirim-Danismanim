"""
HedgeFund AI — Detaylı Analiz
Pro Trading Terminal · Kesin AL/SAT görüşü · Trade planı · Senaryo analizi
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from ui_pages.styles import (
    C, DEC_MAP, apple_layout, page_header, render_ticker,
    candle_chart, sym_search, dec_badge, fmt_pct, fmt_price,
    score_ring, trade_plan_html, conviction_arc, radar_chart, score_bar,
)
from ui_pages.components import (
    section_header, kpi_tile, pill, empty_state, vspace,
)


@st.cache_data(ttl=300, show_spinner=False)
def _run_full_analysis(symbol: str, period: str):
    try:
        from src.opportunity_engine import _analyze_single_asset
        at = ("crypto" if "-USD" in symbol
              else "bist"  if symbol.endswith(".IS")
              else "stock")
        return _analyze_single_asset(
            symbol=symbol, name=symbol, asset_type=at,
            sector="", risk_hint="orta", category="", force=True)
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ohlcv(symbol: str, period: str):
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def _indicator_row(label, value, status, note=""):
    col_map = {"bull": C["buy"],  "bear": C["sell"], "neutral": C["warn"]}
    dot_col = col_map.get(status, C["t3"])
    col_val = col_map.get(status, C["t2"])
    note_html = (f'<div style="font-size:11px;color:{C["t3"]};margin-top:2px;">{note}</div>'
                 if note else "")
    return f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:10px 14px;border-bottom:1px solid {C['divider']};">
  <div style="display:flex;align-items:center;gap:8px;">
    <div style="width:7px;height:7px;border-radius:50%;background:{dot_col};flex-shrink:0;"></div>
    <span style="color:{C['t2']};font-size:13px;">{label}</span>
  </div>
  <div style="text-align:right;">
    <span style="color:{col_val};font-weight:600;font-size:13px;
                 font-variant-numeric:tabular-nums;">{value}</span>
    {note_html}
  </div>
</div>"""


def _render_ai_analysis(res, sym, decision, confidence, conviction,
                        timing, price, currency):
    """AI-generated analysis paragraph. Silently skipped if no key configured."""
    try:
        from src.ai_commentary import ai_generate, ai_enabled, SYSTEM_ANALYST
    except Exception:
        return
    if not ai_enabled():
        return

    # Compact, factual context for the model (no hallucinated numbers)
    rsi   = getattr(res, "rsi", None)
    trend = getattr(res, "trend", "") or ""
    ret1m = getattr(res, "return_1m", None)
    ret3m = getattr(res, "return_3m", None)
    why   = getattr(res, "why_enter", "") or getattr(res, "opportunity_label", "") or ""

    prompt = (
        f"Varlık: {res.name or sym} ({sym}), tür: {res.asset_type}\n"
        f"Karar: {decision} | Güven: {confidence:.0f}% | "
        f"Konviksiyon: {conviction:.0f} | Timing: {timing:.0f}\n"
        f"Fiyat: {fmt_price(price, currency)}\n"
        f"RSI: {rsi if rsi is not None else 'yok'} | Trend: {trend}\n"
        f"1A getiri: {ret1m if ret1m is not None else 'yok'} | "
        f"3A getiri: {ret3m if ret3m is not None else 'yok'}\n"
        f"Motor notu: {why[:300]}\n\n"
        f"Bu analizi yatırımcı için 3-4 cümlede yorumla: kararın arkasındaki "
        f"mantık, en önemli risk, ve zamanlama açısından dikkat edilmesi gereken "
        f"nokta. Sade Türkçe, tek paragraf, abartısız."
    )
    ck = f"an:{sym}:{decision}:{confidence:.0f}:{conviction:.0f}"
    with st.spinner("AI yorumu hazırlanıyor…"):
        ai = ai_generate(prompt, system=SYSTEM_ANALYST, cache_key=ck,
                         max_tokens=360, temperature=0.45)
    if not (ai.get("ok") and ai.get("text")):
        return

    from html import escape
    txt = escape(ai["text"]).replace("\n\n", "<br><br>").replace("\n", " ")
    section_header("AI Yorum", kicker="YAPAY ZEKÂ")
    st.markdown(
        f'<div class="ai-card fade-up">'
        f'  <span class="ai-tag">◆ AI ANALİZ · GEMINI</span>'
        f'  <div class="ai-body" style="font-size:13px;line-height:1.6;">{txt}</div>'
        f'  <div style="font-size:10.5px;color:{C["t4"]};margin-top:10px;'
        f'              line-height:1.4;">Yapay zekâ üretimi yorumdur; '
        f'yatırım tavsiyesi değildir. Kararı kendi araştırmanızla doğrulayın.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    vspace(18)


def render():
    render_ticker()
    page_header("Analiz",
                "Yapay zeka destekli teknik + temel + duygu analizi · Kesin AL/SAT görüşü")

    # ── Sembol + Periyot seçimi ───────────────────────────────────────────────
    s_col, p_col, run_col = st.columns([4, 1, 1])
    with s_col:
        symbol = sym_search("analysis_search", "Sembol ara")
    with p_col:
        period = st.selectbox(
            "Periyot",
            ["1mo", "3mo", "6mo", "1y", "2y"], index=2,
            key="an_period",
            format_func=lambda x: {"1mo": "1 Ay", "3mo": "3 Ay",
                                    "6mo": "6 Ay", "1y": "1 Yıl",
                                    "2y": "2 Yıl"}.get(x, x))
    with run_col:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        run_btn = st.button("Analiz Et", type="primary",
                            use_container_width=True, key="an_run")

    if run_btn and symbol:
        _run_full_analysis.clear()
        st.session_state["analysis_result"]  = None
        st.session_state["analysis_run_sym"] = symbol
        st.session_state["analysis_run_per"] = period

    sym = st.session_state.get("analysis_run_sym")
    if not sym:
        vspace(32)
        empty_state(
            "Analiz için sembol seçin",
            "BTC, ETH, THYAO, AAPL — herhangi bir varlık desteklenir. "
            "Sembol seçip ‘Analiz Et’e basın.",
            icon="◎",
        )
        return

    # ── Analiz çalıştır ───────────────────────────────────────────────────────
    per = st.session_state.get("analysis_run_per", "6mo")
    if not st.session_state.get("analysis_result"):
        with st.spinner(f"{sym} tam analiz çalışıyor — teknik, temel, duygu…"):
            res = _run_full_analysis(sym, per)
            if res:
                st.session_state["analysis_result"] = res
            else:
                st.error(f"Analiz başarısız: {sym} için veri alınamadı.")
                return

    res = st.session_state.get("analysis_result")
    if not res:
        return

    decision   = res.decision
    confidence = res.decision_confidence
    conviction = res.conviction_score
    timing     = res.timing_score
    tq         = res.timing_quality
    price      = res.current_price
    currency   = res.currency
    dm         = DEC_MAP.get(decision, DEC_MAP["İZLE"])
    dc         = dm["col"]

    # ── Karar baneri ─────────────────────────────────────────────────────────
    tq_col  = {"iyi": C["buy"], "orta": C["warn"],
                "kötü": C["sell"], "çok kötü": C["sell"]}.get(tq, C["t2"])
    ret1d   = res.return_1d or 0
    ret1d_c = C["buy"] if ret1d >= 0 else C["sell"]
    ret1d_bg = C["buy_dim"] if ret1d >= 0 else C["sell_dim"]

    # Karar baneri — üç self-contained card yan yana (HTML açma/kapama hatası
    # ve Streamlit sanitizer karşı dayanıklı tasarım)
    section_header(f"{sym}", kicker="ANALİZ",
                   meta=f"{res.asset_type.upper()} · {res.name or sym}")

    bcol_l, bcol_m, bcol_r = st.columns([5, 3, 2], gap="small")

    with bcol_l:
        warn_html = (
            f'<div style="color:{C["warn"]};font-size:12.5px;margin-top:8px;'
            f'padding:6px 10px;background:{C["warn_dim"]};border-radius:6px;'
            f'border:1px solid rgba(245,158,11,0.22);">'
            f'⚠ {res.timing_warning}</div>'
            if res.timing_warning else ""
        )
        st.markdown(
            f'<div class="card" style="padding:18px 20px;border-top:2px solid {dc};">'
            f'  <div class="lbl">KARAR</div>'
            f'  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
            f'              margin-top:8px;">'
            f'    {dec_badge(decision, size="lg", active=True)}'
            f'    {pill(f"Güven {confidence:.0f}%", "accent")}'
            f'    {pill(f"Timing: {tq.upper()}", "warn" if tq not in ("iyi",) else "positive")}'
            f'  </div>'
            f'  <div style="font-size:12.5px;color:{C["t3"]};margin-top:10px;'
            f'              line-height:1.5;">{res.opportunity_label or ""}</div>'
            f'  {warn_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with bcol_m:
        arrow = "▲" if ret1d >= 0 else "▼"
        tone = "positive" if ret1d >= 0 else "negative"
        st.markdown(
            f'<div class="card" style="padding:18px 20px;text-align:center;">'
            f'  <div class="lbl">GÜNCEL FİYAT</div>'
            f'  <div style="font-size:28px;font-weight:700;color:{C["t1"]};'
            f'              font-variant-numeric:tabular-nums;'
            f'              margin:10px 0 10px;letter-spacing:-0.02em;line-height:1;">'
            f'    {fmt_price(price, currency)}</div>'
            f'  <div>{pill(f"{arrow} {abs(ret1d):.2f}% bugün", tone)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with bcol_r:
        st.markdown(
            f'<div class="card" style="padding:14px;text-align:center;">'
            f'  {conviction_arc(conviction, timing, 110)}'
            f'  <div style="font-size:10px;color:{C["t3"]};margin-top:4px;'
            f'              letter-spacing:0.10em;text-transform:uppercase;'
            f'              font-weight:600;">'
            f'    Dış · Konviksiyon&nbsp;&nbsp;İç · Timing</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    vspace(18)

    # ── Trade Planı ───────────────────────────────────────────────────────────
    section_header("Trade Planı", kicker="PLAN")
    st.markdown(trade_plan_html(res, currency), unsafe_allow_html=True)

    vspace(18)

    # ── AI Yorum (ücretsiz Gemini; key yoksa bu bölüm gizlenir) ───────────────
    _render_ai_analysis(res, sym, decision, confidence, conviction, timing, price, currency)

    # ── Ana bölüm: Grafik + Sağ Panel ────────────────────────────────────────
    chart_col, right_col = st.columns([3, 1])

    with chart_col:
        df = fetch_ohlcv(sym, per)
        tab_chart, tab_rsi, tab_macd = st.tabs(["Mum Grafiği", "RSI", "MACD"])

        with tab_chart:
            if not df.empty:
                ema20  = df["Close"].ewm(span=20).mean()
                ema50  = df["Close"].ewm(span=50).mean()
                ema200 = df["Close"].ewm(span=200).mean()
                fig    = candle_chart(df, sym, ema20, ema50, ema200, height=460)
                if res.stop_loss:
                    fig.add_hline(
                        y=res.stop_loss, line_dash="dot",
                        line_color=C["sell"], line_width=1.5,
                        annotation_text=f"SL {fmt_price(res.stop_loss, currency)}",
                        annotation_font_color=C["sell"],
                        annotation_font_size=10, row=1, col=1)
                for tp, lbl in [(res.target_1, "TP1"),
                                (res.target_2, "TP2"),
                                (res.target_3, "TP3")]:
                    if tp:
                        fig.add_hline(
                            y=tp, line_dash="dot",
                            line_color=C["buy"], line_width=1,
                            annotation_text=f"{lbl} {fmt_price(tp, currency)}",
                            annotation_font_color=C["buy"],
                            annotation_font_size=10, row=1, col=1)
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": True,
                                        "modeBarButtonsToRemove": ["lasso2d", "select2d"]})
            else:
                st.markdown(f"""
<div class="card" style="text-align:center;padding:48px;">
  <div style="font-size:13px;color:{C['t3']};">Grafik verisi alınamadı.</div>
</div>""", unsafe_allow_html=True)

        with tab_rsi:
            if not df.empty:
                close = df["Close"]
                delta = close.diff()
                gain  = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
                loss  = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
                rsi_s = (100 - 100 / (1 + gain / loss.replace(0, 1e-9))).round(2)

                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(
                    x=df.index, y=rsi_s, name="RSI",
                    line=dict(color=C["accent"], width=2),
                    hovertemplate="RSI: %{y:.1f}<extra></extra>",
                ))
                fig_rsi.add_hrect(
                    y0=70, y1=100,
                    fillcolor="rgba(255,59,48,0.05)", line_width=0,
                    annotation_text="Aşırı Alım",
                    annotation_font_color=C["sell"],
                    annotation_position="top left")
                fig_rsi.add_hrect(
                    y0=0, y1=30,
                    fillcolor="rgba(52,199,89,0.05)", line_width=0,
                    annotation_text="Aşırı Satım",
                    annotation_font_color=C["buy"],
                    annotation_position="bottom left")
                fig_rsi.add_hline(
                    y=70, line_dash="dash",
                    line_color="rgba(255,59,48,0.4)", line_width=1)
                fig_rsi.add_hline(
                    y=50, line_dash="dot",
                    line_color=C["t4"], line_width=1)
                fig_rsi.add_hline(
                    y=30, line_dash="dash",
                    line_color="rgba(52,199,89,0.4)", line_width=1)
                if len(rsi_s) > 0:
                    cur_rsi = rsi_s.iloc[-1]
                    rsi_col = (C["sell"] if cur_rsi > 70
                               else C["buy"] if cur_rsi < 30 else C["warn"])
                    fig_rsi.add_annotation(
                        x=df.index[-1], y=cur_rsi,
                        text=f"  RSI: {cur_rsi:.1f}",
                        font=dict(color=rsi_col, size=12,
                                  family="-apple-system,sans-serif"),
                        showarrow=False, xanchor="left")
                fig_rsi.update_layout(**apple_layout(
                    height=360,
                    yaxis=dict(range=[0, 100], gridcolor=C["divider"],
                               tickfont=dict(color=C["t3"]))))
                st.plotly_chart(fig_rsi, use_container_width=True,
                                config={"displayModeBar": False})

        with tab_macd:
            if not df.empty:
                close  = df["Close"]
                ema12  = close.ewm(span=12, adjust=False).mean()
                ema26  = close.ewm(span=26, adjust=False).mean()
                macd_l = ema12 - ema26
                signal = macd_l.ewm(span=9, adjust=False).mean()
                hist   = macd_l - signal

                hist_colors = [C["buy"] if v >= 0 else C["sell"] for v in hist]
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Bar(
                    x=df.index, y=hist, name="Histogram",
                    marker_color=hist_colors, opacity=0.6,
                ))
                fig_macd.add_trace(go.Scatter(
                    x=df.index, y=macd_l, name="MACD",
                    line=dict(color=C["accent"], width=2),
                    hovertemplate="MACD: %{y:.4f}<extra></extra>",
                ))
                fig_macd.add_trace(go.Scatter(
                    x=df.index, y=signal, name="Sinyal",
                    line=dict(color=C["warn"], width=1.5, dash="dot"),
                    hovertemplate="Sinyal: %{y:.4f}<extra></extra>",
                ))
                fig_macd.add_hline(y=0, line_color=C["border"], line_width=1)

                cur_hist    = hist.iloc[-1] if len(hist) > 0 else 0
                macd_status = "Bullish" if cur_hist > 0 else "Bearish"
                macd_col    = C["buy"]  if cur_hist > 0 else C["sell"]
                macd_border = ("rgba(52,199,89,0.3)"  if cur_hist > 0
                               else "rgba(255,59,48,0.3)")
                fig_macd.add_annotation(
                    x=0.02, y=0.95, xref="paper", yref="paper",
                    text=f"MACD: {macd_status}",
                    font=dict(color=macd_col, size=11,
                              family="-apple-system,sans-serif"),
                    showarrow=False,
                    bgcolor=C["surface"],
                    bordercolor=macd_border,
                    borderwidth=1, borderpad=4)
                fig_macd.update_layout(**apple_layout(height=360))
                st.plotly_chart(fig_macd, use_container_width=True,
                                config={"displayModeBar": False})

    # ── Sağ panel ─────────────────────────────────────────────────────────────
    with right_col:
        st.markdown(f"<div class='lbl' style='margin-bottom:4px;'>İNDİKATÖR DURUMLARI</div>",
                    unsafe_allow_html=True)
        inds_html = ""
        rsi_val = res.rsi
        if rsi_val is not None:
            if rsi_val > 70:
                st_, note = "bear", "Aşırı alım"
            elif rsi_val < 30:
                st_, note = "bull", "Aşırı satım"
            elif rsi_val > 55:
                st_, note = "bull", "Güçlü momentum"
            elif rsi_val < 45:
                st_, note = "bear", "Zayıf momentum"
            else:
                st_, note = "neutral", "Nötr bölge"
            inds_html += _indicator_row(f"RSI ({rsi_val:.0f})", f"{rsi_val:.1f}", st_, note)

        macd_s    = res.macd_signal
        macd_stat = {"bullish": "bull", "bearish": "bear",
                     "neutral": "neutral"}.get(macd_s, "neutral")
        macd_note = {"bullish": "MACD > Sinyal",
                     "bearish": "MACD < Sinyal",
                     "neutral": "Kesişim bölgesi"}.get(macd_s, "")
        inds_html += _indicator_row("MACD", macd_s.upper(), macd_stat, macd_note)

        trend  = res.trend
        t_stat = {"UPTREND": "bull", "DOWNTREND": "bear",
                  "SIDEWAYS": "neutral"}.get(trend, "neutral")
        t_lbl  = {"UPTREND": "Yükseliş", "DOWNTREND": "Düşüş",
                  "SIDEWAYS": "Yatay"}.get(trend, trend)
        inds_html += _indicator_row("Trend", t_lbl, t_stat)

        bb_pos = res.bb_position
        if bb_pos is not None:
            if bb_pos > 0.8:
                bp_s, bp_n = "bear", "Üst banda yakın"
            elif bb_pos < 0.2:
                bp_s, bp_n = "bull", "Alt banda yakın"
            else:
                bp_s, bp_n = "neutral", f"Bant: %{bb_pos*100:.0f}"
            inds_html += _indicator_row("Bollinger", f"{bb_pos*100:.0f}%", bp_s, bp_n)

        vol_s    = res.volume_signal
        vol_stat = {"high": "bull", "low": "bear", "normal": "neutral"}.get(vol_s, "neutral")
        vol_note = {"high": "Yüksek hacim", "low": "Düşük hacim",
                    "normal": "Normal hacim"}.get(vol_s, "")
        inds_html += _indicator_row("Hacim", vol_s.upper(), vol_stat, vol_note)

        if res.breakout:
            inds_html += _indicator_row("Breakout", "KIRILIM", "bull", "Fiyat kırılımda")

        st.markdown(
            f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
            f'border-radius:12px;overflow:hidden;">{inds_html}</div>',
            unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='lbl' style='margin-bottom:4px;'>SKOR ANALİZİ</div>",
                    unsafe_allow_html=True)
        st.markdown(
            score_bar("Teknik",      res.tech_score or 0)
            + score_bar("Momentum",  res.momentum_score or 0)
            + score_bar("Risk",      res.risk_score or 0)
            + score_bar("Kompozit",  res.composite_score or 0)
            + score_bar("Konviksiyon", res.conviction_score or 0)
            + score_bar("Zamanlama", res.timing_score or 0),
            unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='lbl' style='margin-bottom:4px;'>GETİRİ & RİSK</div>",
                    unsafe_allow_html=True)
        for lbl_r, val in [("1G", res.return_1d), ("1H", res.return_1w),
                            ("1A", res.return_1m), ("3A", res.return_3m),
                            ("6A", res.return_6m), ("1Y", res.return_1y)]:
            if val is None:
                continue
            vc = C["buy"] if val >= 0 else C["sell"]
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;padding:7px 0;
            border-bottom:1px solid {C['divider']};">
  <span style="font-size:13px;color:{C['t2']};">{lbl_r}</span>
  <span style="color:{vc};font-size:13px;font-weight:600;
               font-variant-numeric:tabular-nums;">
    {'▲' if val >= 0 else '▼'} {abs(val):.2f}%
  </span>
</div>""", unsafe_allow_html=True)

        if res.volatility:
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;padding:7px 0;
            border-bottom:1px solid {C['divider']};">
  <span style="font-size:13px;color:{C['t2']};">Volatilite</span>
  <span style="color:{C['warn']};font-size:13px;font-weight:600;">
    {res.volatility:.1f}%</span>
</div>""", unsafe_allow_html=True)
        if res.sharpe:
            vc = C["buy"] if res.sharpe > 1 else C["sell"] if res.sharpe < 0 else C["warn"]
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;padding:7px 0;">
  <span style="font-size:13px;color:{C['t2']};">Sharpe</span>
  <span style="color:{vc};font-size:13px;font-weight:600;">{res.sharpe:.2f}</span>
</div>""", unsafe_allow_html=True)

    # ── Alt bölüm: Neden AL / RİSK / Katalizörler ────────────────────────────
    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)
    bot1, bot2, bot3 = st.columns(3)

    def _reason_card(col, title, items, accent_color):
        with col:
            items_html = ""
            for item in (items or ["Veri bekleniyor..."])[:6]:
                items_html += f"""
  <div style="display:flex;gap:8px;padding:8px 0;
              border-bottom:1px solid {C['divider']};">
    <span style="color:{accent_color};flex-shrink:0;font-size:13px;">▸</span>
    <span style="color:{C['t2']};font-size:13px;line-height:1.5;">{item}</span>
  </div>"""
            st.markdown(f"""
<div class="card" style="padding:20px;border-top:2px solid {accent_color};height:100%;">
  <div class="lbl" style="color:{accent_color};margin-bottom:12px;">{title}</div>
  {items_html}
</div>""", unsafe_allow_html=True)

    _reason_card(bot1, "NEDEN AL",     res.why_buy,     C["buy"])
    _reason_card(bot2, "RİSKLER",      res.why_not_buy, C["sell"])
    _reason_card(bot3, "KATALİZÖRLER", res.catalysts,   C["warn"])

    # ── Senaryo analizi ───────────────────────────────────────────────────────
    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:20px;font-weight:700;color:{C['t1']};margin-bottom:16px;'>Senaryo Analizi</div>",
                unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns(3)
    for col, sc_dict, title, col_hex in [
        (sc1, res.scenario_bull, "BOĞA SENARYOSU",  C["buy"]),
        (sc2, res.scenario_base, "BAZ SENARYO",      C["warn"]),
        (sc3, res.scenario_bear, "AYI SENARYOSU",    C["sell"]),
    ]:
        with col:
            if sc_dict:
                trigger = sc_dict.get("trigger", "—")
                target  = sc_dict.get("price_target", None)
                ret     = sc_dict.get("return_pct", None)
                prob    = sc_dict.get("probability_pct", "?")
                notes   = sc_dict.get("notes", "")
                ret_str = f"{ret:+.0f}%" if ret is not None else "—"
                tgt_str = fmt_price(target, currency) if target else "—"
                st.markdown(f"""
<div class="card" style="padding:20px;border-top:2px solid {col_hex};min-height:160px;">
  <div class="lbl" style="color:{col_hex};margin-bottom:8px;">{title}</div>
  <div style="font-size:28px;font-weight:700;color:{col_hex};
              font-variant-numeric:tabular-nums;margin-bottom:8px;">{ret_str}</div>
  <div style="font-size:13px;color:{C['t2']};margin-bottom:8px;">
    Hedef:&nbsp;<b style="color:{C['t1']};">{tgt_str}</b>
    &nbsp;·&nbsp;Olas.:&nbsp;<b>%{prob}</b>
  </div>
  <div style="font-size:12px;color:{C['t3']};font-style:italic;">{trigger}</div>
  {f'<div style="font-size:11px;color:{C["t3"]};margin-top:6px;">{notes}</div>' if notes else ''}
</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div class="card" style="padding:20px;border-top:2px solid {col_hex};
     min-height:160px;display:flex;align-items:center;justify-content:center;">
  <div style="font-size:13px;color:{C['t3']};text-align:center;">{title}<br>Veri yok</div>
</div>""", unsafe_allow_html=True)

    # ── 6-Boyutlu Radar + Sinyaller ───────────────────────────────────────────
    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)
    radar_col, sig_col = st.columns([1, 2])

    with radar_col:
        st.markdown(f"<div style='font-size:17px;font-weight:600;color:{C['t1']};margin-bottom:12px;'>6 Boyutlu Analiz</div>",
                    unsafe_allow_html=True)
        dims = {
            "Fırsat Kalitesi": res.dim_opportunity_quality,
            "Zamanlama":       res.dim_timing_quality,
            "Risk/Ödül":       res.dim_risk_reward,
            "Portföy Uyumu":   res.dim_portfolio_fit,
            "Profil Uyumu":    res.dim_profile_fit,
            "Alt. Maliyet":    res.dim_alternative_cost,
        }
        st.plotly_chart(radar_chart(dims, 280), use_container_width=True,
                        config={"displayModeBar": False})

    with sig_col:
        st.markdown(f"<div style='font-size:17px;font-weight:600;color:{C['t1']};margin-bottom:12px;'>Sinyal Özeti</div>",
                    unsafe_allow_html=True)
        bull_signals = (res.why_buy     or [])[:8]
        bear_signals = (res.why_not_buy or [])[:5]

        if bull_signals:
            st.markdown(
                f'<div class="lbl" style="color:{C["buy"]};margin-bottom:8px;">'
                f'Yükseliş Sinyalleri</div>',
                unsafe_allow_html=True,
            )
            for s in bull_signals:
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 0;'
                    f'border-bottom:1px solid {C["divider"]};align-items:flex-start;">'
                    f'  <span style="color:{C["buy"]};flex-shrink:0;font-size:12px;'
                    f'               line-height:1.5;">▲</span>'
                    f'  <span style="color:{C["t2"]};font-size:13px;'
                    f'               line-height:1.5;">{s}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if bear_signals:
            st.markdown(
                f'<div class="lbl" style="color:{C["sell"]};margin:16px 0 8px;">'
                f'Düşüş Sinyalleri</div>',
                unsafe_allow_html=True,
            )
            for s in bear_signals:
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:8px 0;'
                    f'border-bottom:1px solid {C["divider"]};align-items:flex-start;">'
                    f'  <span style="color:{C["sell"]};flex-shrink:0;font-size:12px;'
                    f'               line-height:1.5;">▼</span>'
                    f'  <span style="color:{C["t2"]};font-size:13px;'
                    f'               line-height:1.5;">{s}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── İnvalidasyon ─────────────────────────────────────────────────────────
    if res.invalidation or res.invalidation_events:
        st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:17px;font-weight:600;color:{C['t1']};margin-bottom:12px;'>İnvalidasyon Koşulları</div>",
                    unsafe_allow_html=True)
        if res.invalidation:
            st.markdown(f"""
<div class="warn-bar" style="padding:14px 16px;">
  <b style="color:{C['sell']};">Senaryo Bozulma Koşulu:</b>
  <span style="color:{C['t2']};"> {res.invalidation}</span>
</div>""", unsafe_allow_html=True)

    # ── Yasal uyarı ───────────────────────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown(f"""
<div class="warn-bar" style="padding:14px 16px;">
  <b>Yasal Uyarı</b>&ensp;Tüm analizler algoritma tabanlı olup yatırım tavsiyesi
  niteliği taşımaz. Geçmiş performans gelecek sonuçları garanti etmez.
  Yatırım kararlarınızı kendi araştırmanıza dayandırın.
</div>""", unsafe_allow_html=True)
