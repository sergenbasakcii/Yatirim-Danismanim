"""
HedgeFund AI — Projeksiyon
Monte Carlo simülasyonu ile yatırım senaryoları
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date
from ui_pages.styles import C, apple_layout, page_header, render_ticker, sym_search, fmt_pct
from ui_pages.components import (
    section_header, kpi_tile, pill, empty_state, divider, vspace,
)


def _detect_asset_type(symbol: str) -> str:
    s = symbol.upper()
    if "-USD" in s:        return "crypto"
    if s.endswith(".IS"):  return "bist"
    return "stock"


def render():
    render_ticker()
    page_header("Projeksiyon",
                "Monte Carlo simülasyonu ile yatırım senaryoları")

    # ── Parametreler ──────────────────────────────────────────────────────────
    r1c1, r1c2, r1c3 = st.columns([4, 1, 1])
    with r1c1:
        symbol = sym_search("proj_search", "Sembol ara")
    with r1c2:
        amount = st.number_input("Yatırım", value=1000.0,
                                  min_value=1.0, step=500.0, key="proj_amount_w")
    with r1c3:
        currency = st.selectbox("Birim", ["USD", "TRY"], key="proj_cur_w")

    r2c1, r2c2, r2c3 = st.columns([2, 2, 2])
    with r2c1:
        buy_date = st.date_input("Alış Tarihi", value=date.today(),
                                  key="proj_buy_w")
    with r2c2:
        sell_date = st.date_input(
            "Satış Tarihi",
            value=date(date.today().year + 1,
                       date.today().month,
                       date.today().day),
            key="proj_sell_w")
    with r2c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        run_btn = st.button("Projeksiyon Hesapla", type="primary",
                            use_container_width=True, key="proj_run_btn")

    if run_btn:
        if sell_date <= buy_date:
            st.error("Satış tarihi alış tarihinden sonra olmalı.")
        elif not symbol:
            st.warning("Sembol seçin.")
        else:
            st.session_state["proj_result"]   = None
            st.session_state["proj_sym"]      = symbol
            st.session_state["proj_amt_val"]  = amount
            st.session_state["proj_cur_val"]  = currency
            st.session_state["proj_buy_date"] = buy_date
            st.session_state["proj_sell_date"] = sell_date
            st.session_state["proj_run"]      = True

    if st.session_state.get("proj_run"):
        st.session_state["proj_run"] = False
        sym_r = st.session_state.get("proj_sym", "")
        amt_r = st.session_state.get("proj_amt_val", amount)
        cur_r = st.session_state.get("proj_cur_val", currency)
        bd    = st.session_state.get("proj_buy_date", buy_date)
        sd    = st.session_state.get("proj_sell_date", sell_date)

        with st.spinner(f"{sym_r} Monte Carlo simülasyonu çalışıyor..."):
            try:
                from src.projection_engine import run_projection
                res = run_projection(
                    symbol=sym_r,
                    name=sym_r,
                    asset_type=_detect_asset_type(sym_r),
                    buy_date=bd,
                    sell_date=sd,
                    amount=amt_r,
                    currency=cur_r,
                    n_simulations=1000,
                )
                if res is None:
                    st.error(f"Veri yetersiz veya çekilemedi: {sym_r}")
                else:
                    st.session_state["proj_result"] = res
            except Exception as e:
                st.error(f"Projeksiyon hatası: {e}")
                with st.expander("Hata detayı"):
                    import traceback
                    st.code(traceback.format_exc())

    res = st.session_state.get("proj_result")
    if not res:
        vspace(32)
        empty_state(
            "Projeksiyon parametreleri eksik",
            "Sembol, yatırım tutarı ve tarih aralığını seçip "
            "‘Projeksiyon Hesapla’ya basın. 1000 Monte Carlo simülasyonu çalışır.",
            icon="◉",
        )
        return

    sym_r = res.symbol
    amt_r = res.amount
    cur_r = res.currency
    days  = res.holding_days

    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)

    # ── Özet kart ─────────────────────────────────────────────────────────────
    verdict_col = (C["buy"] if res.confidence_score >= 60
                   else C["warn"] if res.confidence_score >= 40 else C["sell"])
    st.markdown(f"""
<div class="card" style="padding:20px 24px;margin-bottom:20px;
     border-left:3px solid {verdict_col};">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
    <div>
      <div class="lbl">{res.asset_type.upper()} · {sym_r}</div>
      <div style="font-size:18px;font-weight:600;color:{C['t1']};margin-top:6px;">
        {res.summary_verdict or '—'}</div>
    </div>
    <div style="text-align:right;">
      <div class="lbl">GÜVEN</div>
      <div style="font-size:28px;font-weight:700;color:{verdict_col};
                  font-variant-numeric:tabular-nums;margin-top:4px;">
        {res.confidence_score:.0f}%</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── Senaryo kartları ──────────────────────────────────────────────────────
    section_header("Senaryo Analizi", kicker="ÜÇ SENARYO",
                   meta=f"{days} gün vade")

    sc_list = [
        (res.scenario_bull, C["buy"]),
        (res.scenario_base, C["warn"]),
        (res.scenario_bear, C["sell"]),
    ]
    sc_cols = st.columns(3)
    for sc_col, (sc, col_hex) in zip(sc_cols, sc_list):
        if sc is None:
            sc_col.markdown(f"""
<div class="card" style="padding:20px;text-align:center;border-top:2px solid {col_hex};
     min-height:180px;display:flex;align-items:center;justify-content:center;">
  <div style="font-size:13px;color:{C['t3']};">Veri yok</div>
</div>""", unsafe_allow_html=True)
            continue
        ret_bg = (C["buy_dim"] if sc.return_pct > 0
                  else C["sell_dim"] if sc.return_pct < 0 else C["warn_dim"])
        sc_col.markdown(f"""
<div class="card" style="padding:20px;text-align:center;
     border-top:2px solid {col_hex};">
  <div style="font-size:24px;margin-bottom:4px;">{sc.emoji}</div>
  <div class="lbl" style="color:{col_hex};margin-bottom:8px;">{sc.name}</div>
  <div style="font-size:28px;font-weight:700;color:{col_hex};
              font-variant-numeric:tabular-nums;margin-bottom:8px;">
    {fmt_pct(sc.return_pct)}</div>
  <div style="font-size:13px;color:{C['t2']};margin-bottom:8px;">
    {amt_r:,.0f} → <b style="color:{C['t1']};">{sc.final_value:,.0f} {cur_r}</b>
  </div>
  <div style="font-size:12px;color:{C['t3']};margin-bottom:8px;">
    Yıllık: <b>{fmt_pct(sc.annualized_return_pct)}</b>
  </div>
  <span style="background:{ret_bg};color:{col_hex};border-radius:980px;
               font-size:12px;font-weight:500;padding:3px 10px;">
    Olasılık: %{sc.probability_pct}
  </span>
  <div style="font-size:11px;color:{C['t3']};margin-top:10px;line-height:1.4;">
    {sc.description}
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)

    # ── Monte Carlo Grafiği ───────────────────────────────────────────────────
    mc = res.monte_carlo
    if mc is not None:
        st.markdown(f"<div style='font-size:20px;font-weight:700;color:{C['t1']};margin-bottom:16px;'>Monte Carlo — 1000 Simülasyon</div>",
                    unsafe_allow_html=True)

        # MC özet metrikleri — 5'li KPI strip
        m1, m2, m3, m4, m5 = st.columns(5, gap="small")
        with m1:
            kpi_tile("P5 — EN KÖTÜ %5",
                     f"{mc.percentile_5:,.0f} {cur_r}",
                     sub="aşağı uç")
        with m2:
            kpi_tile("P25 — ALT ÇEYREK",
                     f"{mc.percentile_25:,.0f} {cur_r}",
                     sub="kötümser")
        with m3:
            kpi_tile("MEDYAN",
                     f"{mc.percentile_50:,.0f} {cur_r}",
                     sub="orta nokta")
        with m4:
            kpi_tile("P75 — ÜST ÇEYREK",
                     f"{mc.percentile_75:,.0f} {cur_r}",
                     sub="iyimser")
        with m5:
            kpi_tile("P95 — EN İYİ %5",
                     f"{mc.percentile_95:,.0f} {cur_r}",
                     sub="yukarı uç")

        vspace(12)

        # Path grafiği (örnek path'lerden)
        try:
            paths = mc.paths_sample or []
            if paths and isinstance(paths[0], (list, tuple, np.ndarray)):
                mc_arr = np.array([np.array(p) for p in paths if len(p) > 0])
                if mc_arr.ndim == 2 and mc_arr.shape[0] > 0:
                    x_days = list(range(mc_arr.shape[1]))
                    median = np.median(mc_arr, axis=0)
                    p10    = np.percentile(mc_arr, 10, axis=0)
                    p25    = np.percentile(mc_arr, 25, axis=0)
                    p75    = np.percentile(mc_arr, 75, axis=0)
                    p90    = np.percentile(mc_arr, 90, axis=0)

                    fig_mc = go.Figure()

                    fig_mc.add_trace(go.Scatter(
                        x=x_days + x_days[::-1],
                        y=p90.tolist() + p10.tolist()[::-1],
                        fill="toself", fillcolor="rgba(91,140,255,0.05)",
                        line=dict(color="rgba(0,0,0,0)"),
                        name="%10–90", hoverinfo="skip",
                    ))
                    fig_mc.add_trace(go.Scatter(
                        x=x_days + x_days[::-1],
                        y=p75.tolist() + p25.tolist()[::-1],
                        fill="toself", fillcolor="rgba(91,140,255,0.10)",
                        line=dict(color="rgba(0,0,0,0)"),
                        name="%25–75", hoverinfo="skip",
                    ))
                    for path in mc_arr[:30]:
                        fig_mc.add_trace(go.Scatter(
                            x=x_days, y=path, mode="lines",
                            line=dict(color="rgba(91,140,255,0.05)", width=1),
                            showlegend=False, hoverinfo="skip",
                        ))
                    fig_mc.add_trace(go.Scatter(
                        x=x_days, y=median, mode="lines", name="Medyan",
                        line=dict(color=C["accent"], width=2.5),
                        hovertemplate=f"Gün %{{x}}<br>Medyan: %{{y:,.2f}} {cur_r}<extra></extra>",
                    ))
                    fig_mc.add_hline(
                        y=amt_r, line_dash="dot",
                        line_color=C["t4"], line_width=1,
                        annotation_text=f"Başlangıç: {amt_r:,.0f}",
                        annotation_font_color=C["t3"],
                        annotation_font_size=10)

                    fig_mc.update_layout(**apple_layout(
                        height=420,
                        title=dict(
                            text=f"{sym_r} — {days} Günlük Projeksiyon",
                            font=dict(color=C["t2"], size=13)),
                        xaxis_title="Gün",
                        yaxis_title=f"Değer ({cur_r})",
                        hovermode="x unified",
                        showlegend=True,
                        legend=dict(orientation="h", y=1.08),
                    ))
                    st.plotly_chart(fig_mc, use_container_width=True,
                                    config={"displayModeBar": False})
        except Exception as e:
            st.warning(f"Grafik oluşturulamadı: {e}")

        # Pozitif çıkma olasılığı
        st.markdown(f"""
<div class="card" style="padding:14px 20px;margin-top:12px;
     border-left:3px solid {C['accent']};">
  <span style="color:{C['t2']};font-size:13px;">Kârlı çıkma olasılığı: </span>
  <b style="color:{C['accent']};font-size:15px;">%{mc.positive_prob_pct:.1f}</b>
  <span style="color:{C['t3']};font-size:12px;">&nbsp;·&nbsp;Ortalama getiri: </span>
  <b style="color:{C['t1']};">{fmt_pct(mc.mean_return)}</b>
</div>""", unsafe_allow_html=True)

    st.markdown(f"<div style='height:1px;background:{C['divider']};margin:24px 0;'></div>",
                unsafe_allow_html=True)

    # ── Risk metrikleri ───────────────────────────────────────────────────────
    section_header("Risk Metrikleri", kicker="VOLATİLİTE & DD")

    rm_data = [
        ("YILLIK VOLATİLİTE", f"{res.annual_volatility_pct:.1f}%", "yıllık std"),
        ("GÜNLÜK VOLATİLİTE", f"{res.daily_volatility_pct:.2f}%", "günlük std"),
        ("SHARPE TAHMİNİ",    f"{res.sharpe_estimate:.2f}",       "risk-ayar getiri"),
        ("GEÇMİŞ MAX DD",     f"{res.max_drawdown_historical:.1f}%", "tarihsel düşüş"),
        ("VADE",              f"{days} gün",                      "tutma süresi"),
        ("YIL",               f"{res.holding_years:.2f}",         "yıl cinsi"),
    ]
    rm_cols = st.columns(len(rm_data), gap="small")
    for col, (lbl_r, val, sub) in zip(rm_cols, rm_data):
        with col:
            kpi_tile(lbl_r, val, sub=sub)

    # ── Karşılaştırma ─────────────────────────────────────────────────────────
    if res.benchmark_spy_return_pct or res.benchmark_gold_return_pct:
        vspace(14)
        section_header("Benchmark Karşılaştırması", kicker="GÖRELI PERFORMANS")
        bm_cols = st.columns(3, gap="small")
        bm_data = [
            (f"{sym_r} (BAZ)",  res.scenario_base.return_pct if res.scenario_base else 0),
            ("S&P 500",         res.benchmark_spy_return_pct),
            ("ALTIN",           res.benchmark_gold_return_pct),
        ]
        for col, (lbl_b, val) in zip(bm_cols, bm_data):
            with col:
                kpi_tile(lbl_b, fmt_pct(val), delta=val, sub="dönem getirisi")

    # ── Tarihsel benzer dönemler ──────────────────────────────────────────────
    hist = res.historical
    if hist and hist.found:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:17px;font-weight:600;color:{C['t1']};margin-bottom:12px;'>Geçmiş Benzer Dönemler</div>",
                    unsafe_allow_html=True)
        st.markdown(f"""
<div class="card" style="padding:18px 20px;">
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
              gap:14px;margin-bottom:12px;">
    <div>
      <div class="lbl">Analiz Edilen</div>
      <div style="font-size:18px;font-weight:600;color:{C['t1']};margin-top:4px;">
        {hist.periods_analyzed} dönem</div>
    </div>
    <div>
      <div class="lbl">Ortalama</div>
      <div style="font-size:18px;font-weight:600;color:{C['accent']};margin-top:4px;">
        {fmt_pct(hist.avg_return_pct)}</div>
    </div>
    <div>
      <div class="lbl">En İyi</div>
      <div style="font-size:18px;font-weight:600;color:{C['buy']};margin-top:4px;">
        {fmt_pct(hist.best_return_pct)}</div>
    </div>
    <div>
      <div class="lbl">En Kötü</div>
      <div style="font-size:18px;font-weight:600;color:{C['sell']};margin-top:4px;">
        {fmt_pct(hist.worst_return_pct)}</div>
    </div>
    <div>
      <div class="lbl">Pozitif Oran</div>
      <div style="font-size:18px;font-weight:600;color:{C['buy']};margin-top:4px;">
        %{hist.positive_pct:.0f}</div>
    </div>
  </div>
  <div style="font-size:13px;color:{C['t2']};line-height:1.5;
              padding-top:12px;border-top:1px solid {C['divider']};">
    {hist.description}
  </div>
</div>""", unsafe_allow_html=True)

    # ── Risk uyarıları ────────────────────────────────────────────────────────
    if res.risk_warnings:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        warns_html = "".join(
            f'<div style="display:flex;gap:8px;padding:6px 0;">'
            f'<span style="color:{C["warn"]};">⚠</span>'
            f'<span style="color:{C["t2"]};font-size:13px;">{w}</span></div>'
            for w in res.risk_warnings
        )
        st.markdown(f"""
<div class="warn-bar" style="padding:14px 18px;">
  <div class="lbl" style="color:{C['warn']};margin-bottom:8px;">RİSK UYARILARI</div>
  {warns_html}
</div>""", unsafe_allow_html=True)

    # ── Eğitim notları ────────────────────────────────────────────────────────
    if res.education_notes:
        with st.expander("Eğitim Notları"):
            for note in res.education_notes:
                st.markdown(f'<div style="color:{C["t2"]};font-size:13px;'
                            f'padding:6px 0;">▸ {note}</div>',
                            unsafe_allow_html=True)

    st.markdown(f"""
<div class="warn-bar" style="padding:14px 16px;margin-top:24px;">
  <b>Yasal Uyarı</b>&ensp;Monte Carlo simülasyonu geçmiş fiyat verisi kullanılarak
  üretilmiştir. Gerçek sonuçlar önemli ölçüde farklılık gösterebilir.
  Yatırım tavsiyesi değildir.
</div>""", unsafe_allow_html=True)
