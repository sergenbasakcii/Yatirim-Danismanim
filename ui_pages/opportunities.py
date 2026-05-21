"""
HedgeFund AI — Fırsatlar (Opportunity Discovery)
================================================
Institutional discovery surface. Header KPI strip · refined filter bar ·
dense list with sparklines · structured detail panel with trade plan,
score distribution, technical chart, thesis & risks.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui_pages.styles import (
    C, DEC_MAP, apple_layout, page_header, render_ticker,
    score_ring, dec_badge, fmt_pct, fmt_price, trade_plan_html,
    score_bar, spark_svg,
)
from ui_pages.components import (
    section_header, kpi_tile, pill, empty_state, divider, vspace,
)


# ══════════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def fetch_spark(symbol: str):
    try:
        import yfinance as yf
        df = yf.download(symbol, period="7d", interval="1h",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df["Close"].dropna().tolist() if not df.empty else []
    except Exception:
        return []


def _dtype(dec: str) -> str:
    if dec in {"GÜÇLÜ AL", "AL", "BİRİKTİR"}: return "buy"
    if dec in {"SAT", "KAÇIN", "AZALT"}:       return "sell"
    return "hold"


# ══════════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════════
def render():
    render_ticker()
    page_header(
        "Fırsatlar",
        "Yapay zekâ destekli piyasa taraması · 80+ varlık · kesin AL / SAT görüşleri",
    )

    # ── Filter bar ────────────────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3, scan_c = st.columns([2, 2.2, 1.6, 1])
    with ctrl1:
        min_score = st.slider("Min Skor", 0, 100, 50, key="opp_min_score")
    with ctrl2:
        asset_filter = st.multiselect(
            "Varlık Tipi",
            ["crypto", "us_stocks", "bist", "priority_etfs"],
            default=["crypto", "us_stocks", "bist", "priority_etfs"],
            format_func=lambda x: {
                "crypto": "Kripto", "us_stocks": "ABD",
                "bist": "BIST", "priority_etfs": "ETF"
            }.get(x, x),
            key="opp_asset_filter")
    with ctrl3:
        sort_by = st.selectbox(
            "Sırala",
            ["Konviksiyon", "Skor", "Getiri 1A", "Zamanlama"],
            key="opp_sort")
    with scan_c:
        vspace(22)
        scan_btn = st.button("⟳ Tara", type="primary",
                             use_container_width=True, key="opp_scan")

    if scan_btn:
        st.session_state["opp_results"] = None
        st.session_state["opp_detail"] = None
        st.session_state["opp_scanning"] = True

    if st.session_state.get("opp_scanning"):
        st.session_state["opp_scanning"] = False
        types = asset_filter or ["crypto", "us_stocks", "bist", "priority_etfs"]
        all_results = []
        pb = st.progress(0, text="Tarama başlıyor…")
        lbl = st.empty()
        try:
            from src.opportunity_engine import scan_asset_type
            for i, at in enumerate(types):
                name = {"crypto": "Kripto", "us_stocks": "ABD",
                        "bist": "BIST", "priority_etfs": "ETF"}.get(at, at)
                lbl.markdown(
                    f'<span style="color:{C["t2"]};font-size:13px;">'
                    f'Taranıyor: <b style="color:{C["accent_hover"]};">{name}</b>'
                    f'&nbsp;({i + 1}/{len(types)})</span>',
                    unsafe_allow_html=True)
                results = scan_asset_type(at, force_refresh=False)
                all_results.extend(results)
                pb.progress((i + 1) / len(types),
                            text=f"{len(all_results)} fırsat bulundu…")
            st.session_state["opp_results"] = all_results
            pb.progress(1.0)
            lbl.empty()
        except Exception as e:
            st.error(f"Tarama hatası: {e}")
            pb.empty(); lbl.empty()

    results = st.session_state.get("opp_results")
    if results is None:
        vspace(48)
        empty_state(
            "Piyasayı Tara",
            "80+ varlık yapay zekâ ile analiz edilir · yaklaşık 20–40 saniye sürer. "
            "Yukarıdan filtreleri ayarlayıp ‘Tara’ düğmesine basın.",
            icon="◈",
        )
        return

    # ── Quick decision filter (segmented) ────────────────────────────────────
    filter_opts = ["Tümü", "AL", "TUT", "SAT"]
    st.session_state.setdefault("opp_quick_filter", "Tümü")
    f_cols = st.columns([1, 1, 1, 1, 4])
    for i, fo in enumerate(filter_opts):
        is_active = st.session_state["opp_quick_filter"] == fo
        with f_cols[i]:
            if st.button(fo, key=f"qf_{fo}",
                         type="primary" if is_active else "secondary",
                         use_container_width=True):
                st.session_state["opp_quick_filter"] = fo
                st.rerun()

    qf = st.session_state["opp_quick_filter"]
    filtered = [r for r in results if r.composite_score >= min_score]
    if qf == "AL":
        filtered = [r for r in filtered
                    if r.decision in {"GÜÇLÜ AL", "AL", "BİRİKTİR"}]
    elif qf == "TUT":
        filtered = [r for r in filtered
                    if r.decision in {"İZLE", "TUTE", "AZALT"}]
    elif qf == "SAT":
        filtered = [r for r in filtered if r.decision in {"SAT", "KAÇIN"}]

    sort_map = {
        "Konviksiyon": lambda x: getattr(x, "conviction_score", 0),
        "Getiri 1A":   lambda x: getattr(x, "return_1m", 0) or 0,
        "Zamanlama":   lambda x: getattr(x, "timing_score", 0),
        "Skor":        lambda x: x.composite_score,
    }
    filtered.sort(key=sort_map.get(sort_by, lambda x: x.composite_score),
                  reverse=True)

    if not filtered:
        vspace(16)
        empty_state(
            "Sonuç yok",
            "Filtre kriterlerine uyan fırsat bulunamadı. Min skoru düşürün "
            "veya farklı varlık tipi seçin.",
            icon="◇",
        )
        return

    # ── KPI strip ────────────────────────────────────────────────────────────
    vspace(8)
    buy_n = sum(1 for r in filtered if _dtype(r.decision) == "buy")
    hold_n = sum(1 for r in filtered if _dtype(r.decision) == "hold")
    sell_n = sum(1 for r in filtered if _dtype(r.decision) == "sell")
    avg_sc = sum(r.composite_score for r in filtered) / max(len(filtered), 1)
    top = max(filtered, key=lambda r: r.composite_score, default=None)

    k1, k2, k3, k4 = st.columns(4, gap="small")
    with k1:
        kpi_tile("TOPLAM FIRSAT", str(len(filtered)),
                 sub=f"min skor {min_score}")
    with k2:
        kpi_tile("ORT. KOMPOZİT", f"{avg_sc:.0f}",
                 sub=f"{len(results)} taranan")
    with k3:
        kpi_tile("AL · TUT · SAT",
                 f"{buy_n} · {hold_n} · {sell_n}",
                 sub="karar dağılımı")
    with k4:
        if top:
            kpi_tile("EN YÜKSEK KONVİKSİYON",
                     f"{top.symbol}",
                     sub=f"skor {top.composite_score:.0f}")
        else:
            kpi_tile("EN YÜKSEK KONVİKSİYON", "—")

    vspace(18)

    # ── List + detail layout ─────────────────────────────────────────────────
    list_col, detail_col = st.columns([5, 7], gap="medium")

    # ── List ─────────────────────────────────────────────────────────────────
    with list_col:
        section_header(
            "Fırsat Listesi",
            kicker="SIRALAMA",
            meta=f"{len(filtered)} sonuç · {sort_by.upper()}",
        )

        for i, opp in enumerate(filtered[:40]):
            dm = DEC_MAP.get(opp.decision, DEC_MAP["İZLE"])
            ret1m = getattr(opp, "return_1m", None)
            ret_str = (f"{'+' if (ret1m or 0) >= 0 else ''}{ret1m:.1f}%"
                       if ret1m is not None else "—")
            ret_tone = "positive" if (ret1m or 0) >= 0 else "negative"
            spark = fetch_spark(opp.symbol)
            spark_h = spark_svg(spark, width=72, height=24) if spark else ""
            price = fmt_price(opp.current_price, opp.currency)
            is_sel = st.session_state.get("opp_detail_sym") == opp.symbol
            bl = f"2px solid {C['accent']}" if is_sel else "2px solid transparent"
            bg = "rgba(91,140,255,0.04)" if is_sel else "transparent"

            st.markdown(
                f'<div style="padding:12px 16px;background:{bg};border-left:{bl};'
                f'border:1px solid {C["border"]};border-radius:8px;'
                f'margin-bottom:6px;transition:border-color 160ms ease,'
                f'background 160ms ease;">'
                f'  <div style="display:flex;justify-content:space-between;'
                f'              align-items:flex-start;margin-bottom:8px;gap:12px;">'
                f'    <div style="min-width:0;">'
                f'      <div style="font-size:13.5px;font-weight:700;color:{C["t1"]};'
                f'                  letter-spacing:-0.005em;">{escape(opp.symbol)}</div>'
                f'      <div style="font-size:11.5px;color:{C["t3"]};margin-top:1px;'
                f'                  overflow:hidden;text-overflow:ellipsis;'
                f'                  white-space:nowrap;max-width:200px;">'
                f'        {escape(opp.name or "")}</div>'
                f'    </div>'
                f'    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">'
                f'      {score_ring(opp.composite_score, 34)}'
                f'      {dec_badge(opp.decision, size="sm")}'
                f'    </div>'
                f'  </div>'
                f'  <div style="display:flex;justify-content:space-between;'
                f'              align-items:flex-end;gap:12px;">'
                f'    <div>'
                f'      <div style="font-size:13.5px;font-weight:700;color:{C["t1"]};'
                f'                  font-variant-numeric:tabular-nums;line-height:1.2;">'
                f'        {price}</div>'
                f'      <div style="margin-top:4px;">'
                f'        {pill(ret_str + " · 1A", ret_tone)}</div>'
                f'    </div>'
                f'    <div>{spark_h}</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("Detay →", key=f"opp_sel_{i}_{opp.symbol}",
                         use_container_width=True, type="secondary"):
                st.session_state["opp_detail_sym"] = opp.symbol
                st.session_state["opp_detail"] = opp
                st.rerun()

    # ── Detail panel ─────────────────────────────────────────────────────────
    with detail_col:
        opp = st.session_state.get("opp_detail")
        if opp is None:
            section_header("Detay", kicker="SEÇİM")
            empty_state(
                "Bir fırsat seçin",
                "Soldaki listeden bir sembol seçtiğinizde tüm trade planı, "
                "skor dağılımı ve teknik grafik burada görünecek.",
                icon="◈",
            )
            return

        dm = DEC_MAP.get(opp.decision, DEC_MAP["İZLE"])
        price = opp.current_price
        cur = opp.currency
        ret1d = opp.return_1d or 0
        ret_tone = "positive" if ret1d >= 0 else "negative"

        section_header(
            opp.symbol, kicker="DETAY",
            meta=escape(opp.name or ""),
        )

        # Header card
        st.markdown(
            f'<div class="card" style="padding:18px 22px;margin-bottom:14px;">'
            f'  <div style="display:flex;justify-content:space-between;'
            f'              align-items:flex-start;gap:16px;flex-wrap:wrap;">'
            f'    <div>'
            f'      <div style="display:flex;align-items:center;gap:10px;'
            f'                  margin-bottom:8px;flex-wrap:wrap;">'
            f'        {dec_badge(opp.decision, size="lg")}'
            f'        {pill(f"Güven {getattr(opp, "decision_confidence", 0):.0f}%", "accent")}'
            f'        {pill("Zamanlama " + str(getattr(opp, "timing_quality", "orta")).upper(), "warn")}'
            f'      </div>'
            f'      <div style="font-size:11.5px;color:{C["t3"]};">'
            f'        {escape(getattr(opp, "opportunity_label", "") or "")}</div>'
            f'    </div>'
            f'    <div style="text-align:right;">'
            f'      <div class="lbl" style="margin-bottom:4px;">GÜNCEL FİYAT</div>'
            f'      <div style="font-size:26px;font-weight:700;color:{C["t1"]};'
            f'                  font-variant-numeric:tabular-nums;line-height:1;'
            f'                  letter-spacing:-0.02em;">{fmt_price(price, cur)}</div>'
            f'      <div style="margin-top:6px;">'
            f'        {pill(("+" if ret1d >= 0 else "") + f"{ret1d:.2f}% bugün", ret_tone)}'
            f'      </div>'
            f'    </div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Trade plan grid
        section_header("Trade Planı", kicker="PLAN")
        st.markdown(trade_plan_html(opp, cur), unsafe_allow_html=True)

        # Score distribution
        vspace(4)
        section_header("Skor Dağılımı", kicker="SKORLAR")
        sc_l, sc_r = st.columns(2, gap="medium")
        items = [
            ("Teknik",      opp.tech_score),
            ("Momentum",    opp.momentum_score),
            ("Kompozit",    opp.composite_score),
            ("Konviksiyon", opp.conviction_score),
            ("Risk",        opp.risk_score),
            ("Zamanlama",   opp.timing_score),
        ]
        for i, (slbl, sval) in enumerate(items):
            (sc_l if i % 2 == 0 else sc_r).markdown(
                score_bar(slbl, sval or 0), unsafe_allow_html=True)

        # 30-day technical chart
        vspace(8)
        section_header("Teknik Analiz", kicker="30 GÜN")
        try:
            import yfinance as yf
            df30 = yf.download(opp.symbol, period="30d", interval="1d",
                               progress=False, auto_adjust=True)
            if isinstance(df30.columns, pd.MultiIndex):
                df30.columns = [c[0] for c in df30.columns]
            if not df30.empty:
                cl = df30["Close"]
                fig30 = go.Figure()
                fig30.add_trace(go.Scatter(
                    x=df30.index, y=cl,
                    line=dict(color=C["accent"], width=1.6),
                    fill="tozeroy", fillcolor="rgba(91,140,255,0.06)",
                    hovertemplate="%{x|%d %b}<br>%{y:,.2f}<extra></extra>",
                ))
                if getattr(opp, "stop_loss", None):
                    fig30.add_hline(y=opp.stop_loss, line_dash="dot",
                                    line_color=C["sell"], line_width=1,
                                    annotation_text="SL",
                                    annotation_font_color=C["sell"],
                                    annotation_font_size=10)
                if getattr(opp, "target_1", None):
                    fig30.add_hline(y=opp.target_1, line_dash="dot",
                                    line_color=C["buy"], line_width=1,
                                    annotation_text="TP1",
                                    annotation_font_color=C["buy"],
                                    annotation_font_size=10)
                fig30.update_layout(**apple_layout(height=180, showlegend=False))
                fig30.update_yaxes(autorange=True)
                st.plotly_chart(fig30, use_container_width=True,
                                config={"displayModeBar": False})
        except Exception:
            pass

        # Thesis / risks
        vspace(4)
        why_l, why_r = st.columns(2, gap="medium")
        with why_l:
            section_header("Neden AL", kicker="TEZ")
            for item in (opp.why_buy or ["—"])[:5]:
                st.markdown(
                    f'<div style="display:flex;gap:8px;padding:7px 0;'
                    f'border-bottom:1px solid {C["divider"]};">'
                    f'  <span style="color:{C["buy"]};font-size:12px;'
                    f'               flex-shrink:0;line-height:1.5;">▲</span>'
                    f'  <span style="color:{C["t2"]};font-size:12.5px;'
                    f'               line-height:1.5;">{escape(item)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        with why_r:
            section_header("Riskler", kicker="UYARI")
            for item in (opp.why_not_buy or ["—"])[:5]:
                st.markdown(
                    f'<div style="display:flex;gap:8px;padding:7px 0;'
                    f'border-bottom:1px solid {C["divider"]};">'
                    f'  <span style="color:{C["sell"]};font-size:12px;'
                    f'               flex-shrink:0;line-height:1.5;">▼</span>'
                    f'  <span style="color:{C["t2"]};font-size:12.5px;'
                    f'               line-height:1.5;">{escape(item)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        vspace(14)
        if st.button("→ Tam Analize Geç", key="opp_goto_analysis",
                     type="primary", use_container_width=True):
            st.session_state["_preload_symbol"] = opp.symbol
            st.session_state["analysis_run_sym"] = opp.symbol
            st.session_state["analysis_result"] = None
            st.session_state["page"] = "Analiz"
            st.rerun()
