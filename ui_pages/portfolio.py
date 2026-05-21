"""
HedgeFund AI — Portföy Yöneticisi
Risk profiline göre Korumacı · Dengeli · Agresif portföy
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from ui_pages.styles import C, apple_layout, page_header, render_ticker, sym_search
from ui_pages.components import (
    section_header, kpi_tile, pill, empty_state, divider, vspace,
)


PROFILE_LABELS = {
    "cok_dengeli":     "Çok Dengeli",
    "dengeli":         "Dengeli",
    "dengeli_agresif": "Dengeli-Agresif",
    "orta_riskli":     "Orta Riskli",
    "riskli":          "Riskli",
    "cok_riskli":      "Çok Riskli",
    "ultra_agresif":   "Ultra Agresif",
}

CLASS_COLORS = {
    "crypto":  C["accent"],
    "stock":   C["buy"],
    "bist":    "#5ac8fa",
    "etf":     C["warn"],
    "fund":    "#bf5af2",
    "nakit":   C["t3"],
    "altin":   C["warn"],
    "tahvil":  "#32ade6",
}


def _treemap(alloc) -> go.Figure:
    labels, parents, values, colors_list = [], [], [], []
    root = alloc.name
    labels.append(root); parents.append(""); values.append(0)

    for a in alloc.assets:
        labels.append(a.symbol)
        parents.append(root)
        values.append(a.weight_pct)
        colors_list.append(CLASS_COLORS.get(a.asset_type, C["t4"]))

    if alloc.cash_pct > 0:
        labels.append("Nakit"); parents.append(root)
        values.append(alloc.cash_pct)
        colors_list.append(CLASS_COLORS["nakit"])

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker=dict(colors=[C["surface"]] + colors_list,
                    line=dict(color=C["bg"], width=2)),
        textfont=dict(color=C["t1"], size=11,
                      family="-apple-system,sans-serif"),
        hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
    ))
    fig.update_layout(**apple_layout(height=300, margin=dict(l=0, r=0, t=8, b=0)))
    return fig


def _donut(alloc) -> go.Figure:
    class_data = {}
    for a in alloc.assets:
        class_data[a.asset_type] = class_data.get(a.asset_type, 0) + a.weight_pct
    if alloc.cash_pct > 0:
        class_data["nakit"] = alloc.cash_pct

    color_seq = [CLASS_COLORS.get(k, C["t3"]) for k in class_data]

    fig = go.Figure(go.Pie(
        labels=list(class_data.keys()),
        values=list(class_data.values()),
        hole=0.60,
        marker=dict(colors=color_seq,
                    line=dict(color=C["bg"], width=3)),
        textfont=dict(color=C["t2"], size=11,
                      family="-apple-system,sans-serif"),
        hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
    ))
    fig.update_layout(**apple_layout(
        height=280, showlegend=True,
        legend=dict(orientation="v", x=1.02,
                    font=dict(color=C["t2"], size=11)),
        margin=dict(l=0, r=80, t=8, b=0),
    ))
    return fig


def render():
    render_ticker()
    page_header("Portföy Yöneticisi",
                "Risk profiline göre Korumacı · Dengeli · Agresif portföy")

    st.markdown(
        '<div class="warn-bar" style="margin-bottom:18px;">'
        '<b>Yasal Uyarı</b>&ensp;Bu araç yalnızca bilgilendirme amaçlıdır. '
        'Yatırım tavsiyesi değildir.</div>',
        unsafe_allow_html=True,
    )

    # ── Portföy sekmeleri ─────────────────────────────────────────────────────
    if "portfolios" not in st.session_state:
        st.session_state["portfolios"] = [
            {"name": "Portföy 1", "result": None, "params": {}}]

    portfolios = st.session_state["portfolios"]
    tab_names  = [p["name"] for p in portfolios] + ["+ Yeni"]
    tabs       = st.tabs(tab_names)

    for ti, tab in enumerate(tabs):
        with tab:
            if ti == len(portfolios):
                st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
                col_new, _ = st.columns([2, 4])
                with col_new:
                    if st.button("Yeni Portföy Oluştur", type="primary",
                                 use_container_width=True, key=f"new_port_{ti}"):
                        n = len(portfolios) + 1
                        portfolios.append(
                            {"name": f"Portföy {n}", "result": None, "params": {}})
                        st.rerun()
                continue

            ps = portfolios[ti]
            form_col, res_col = st.columns([5, 7])

            with form_col:
                with st.form(key=f"port_form_{ti}"):
                    new_name = st.text_input("Portföy Adı", value=ps["name"],
                                             key=f"pn_{ti}")

                    st.markdown(f"<div class='lbl' style='margin:12px 0 6px;'>BÜTÇE</div>",
                                unsafe_allow_html=True)
                    bc1, bc2 = st.columns(2)
                    budget   = bc1.number_input(
                        "Toplam", value=float(ps["params"].get("budget", 10000)),
                        min_value=100.0, step=1000.0, key=f"pb_{ti}")
                    currency = bc2.selectbox(
                        "Birim", ["USD", "TRY", "EUR"],
                        index=["USD", "TRY", "EUR"].index(
                            ps["params"].get("currency", "USD")),
                        key=f"pc_{ti}")

                    st.markdown(f"<div class='lbl' style='margin:12px 0 6px;'>RİSK &amp; VADE</div>",
                                unsafe_allow_html=True)
                    profile = st.selectbox(
                        "Risk Profili", list(PROFILE_LABELS.keys()),
                        index=list(PROFILE_LABELS.keys()).index(
                            ps["params"].get("profile", "dengeli")),
                        format_func=lambda x: PROFILE_LABELS.get(x, x),
                        key=f"pp_{ti}")
                    hc1, hc2 = st.columns(2)
                    horizon  = hc1.selectbox(
                        "Vade", ["kisa", "orta", "uzun"],
                        index=["kisa", "orta", "uzun"].index(
                            ps["params"].get("horizon", "orta")),
                        format_func=lambda x: {"kisa": "Kısa (<1y)",
                                               "orta": "Orta (1-3y)",
                                               "uzun": "Uzun (3y+)"}.get(x, x),
                        key=f"ph_{ti}")
                    priority = hc2.selectbox(
                        "Öncelik",
                        ["buyume", "guvenlik", "gelir", "firsat"],
                        index=["buyume", "guvenlik", "gelir", "firsat"].index(
                            ps["params"].get("priority", "buyume")),
                        format_func=lambda x: {"buyume": "Büyüme",
                                               "guvenlik": "Güvenlik",
                                               "gelir": "Gelir",
                                               "firsat": "Fırsat"}.get(x, x),
                        key=f"ppr_{ti}")

                    st.markdown(f"<div class='lbl' style='margin:12px 0 6px;'>KISITLAR</div>",
                                unsafe_allow_html=True)
                    kc1, kc2 = st.columns(2)
                    max_pos  = kc1.number_input(
                        "Max Pozisyon %",
                        value=float(ps["params"].get("max_pos", 25)),
                        min_value=5.0, max_value=100.0, key=f"pmp_{ti}")
                    cash_pct = kc2.number_input(
                        "Nakit %",
                        value=float(ps["params"].get("cash_pct", 10)),
                        min_value=0.0, max_value=50.0, key=f"pcp_{ti}")
                    loss_tol = st.number_input(
                        "Kayıp Toleransı %",
                        value=float(ps["params"].get("loss_tol", -20)),
                        max_value=0.0, key=f"plt_{ti}")
                    monthly  = st.number_input(
                        "Aylık Ekleme",
                        value=float(ps["params"].get("monthly", 0)),
                        min_value=0.0, key=f"pmo_{ti}")
                    excluded = st.text_input(
                        "Hariç Tut",
                        value=ps["params"].get("excluded", ""),
                        placeholder="kripto, bist ...", key=f"pex_{ti}")

                    submitted = st.form_submit_button(
                        "Portföy Oluştur", type="primary",
                        use_container_width=True)

                if submitted:
                    ps["name"]   = new_name
                    ps["params"] = dict(
                        budget=budget, currency=currency, profile=profile,
                        horizon=horizon, priority=priority, max_pos=max_pos,
                        cash_pct=cash_pct, loss_tol=loss_tol,
                        monthly=monthly, excluded=excluded)
                    ps["result"] = None
                    ps["build"]  = True
                    st.rerun()

                # Manuel varlık (form dışı)
                st.markdown(f"<div class='lbl' style='margin:16px 0 6px;'>MANUEL VARLIK</div>",
                            unsafe_allow_html=True)
                man_sym = sym_search(f"man_srch_{ti}", "Varlık ara")
                mwc1, mwc2 = st.columns([2, 1])
                man_wt = mwc1.text_input("Ağırlık %", placeholder="oto",
                                          key=f"mw_{ti}")
                if mwc2.button("Ekle", key=f"madd_{ti}", use_container_width=True):
                    if man_sym:
                        if "manual_assets" not in ps:
                            ps["manual_assets"] = []
                        if not any(s == man_sym for s, _ in ps["manual_assets"]):
                            ps["manual_assets"].append((man_sym, man_wt or "oto"))
                            st.rerun()

                for sym_m, wt_m in (ps.get("manual_assets") or []):
                    mc1, mc2 = st.columns([5, 1])
                    mc1.markdown(
                        pill(f"{sym_m} · {wt_m}", "accent"),
                        unsafe_allow_html=True)
                    if mc2.button("✕", key=f"mrm_{ti}_{sym_m}"):
                        ps["manual_assets"] = [
                            (s, w) for s, w in ps["manual_assets"] if s != sym_m]
                        st.rerun()

            # ── Portföy engine ─────────────────────────────────────────────────
            with res_col:
                if ps.get("build") and not ps.get("result"):
                    ps["build"] = False
                    with st.spinner(f"'{ps['name']}' hesaplanıyor..."):
                        try:
                            from src.portfolio_engine import build_portfolio
                            prm  = ps["params"]
                            excl = [e.strip()
                                    for e in prm.get("excluded", "").split(",")
                                    if e.strip()]
                            ps["result"] = build_portfolio(
                                budget=prm["budget"],
                                currency=prm["currency"],
                                risk_profile=prm["profile"],
                                horizon=prm["horizon"],
                                priority=prm["priority"],
                                excluded_types=excl or None,
                                monthly_addition=prm["monthly"],
                                max_single_position_pct=prm["max_pos"],
                                cash_preference_pct=prm["cash_pct"],
                                loss_tolerance_pct=prm["loss_tol"],
                            )
                        except Exception as e:
                            st.error(f"Hata: {e}")

                result = ps.get("result")
                if not result:
                    vspace(24)
                    empty_state(
                        "Portföy parametreleri eksik",
                        "Soldan bütçe, risk profili ve kısıtları belirleyip "
                        "‘Portföy Oluştur’ düğmesine basın.",
                        icon="◧",
                    )
                    continue

                # Tavsiye banner (institutional accent)
                st.markdown(
                    f'<div class="card" style="padding:14px 18px;margin-bottom:14px;'
                    f'border-left:3px solid {C["accent"]};">'
                    f'<span class="lbl" style="margin:0 0 4px;">TAVSİYE</span>'
                    f'<div style="font-size:13px;color:{C["t1"]};line-height:1.55;">'
                    f'{result.recommendation}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                prm = ps["params"]
                section_header(
                    "Portföy Özeti",
                    kicker="ÖZET",
                    meta=f"{prm['currency']} {prm['budget']:,.0f}",
                )

                t_cons, t_bal, t_agg = st.tabs(
                    ["Korumacı", "Dengeli", "Agresif"])

                for alloc, tab_a in [
                    (result.conservative, t_cons),
                    (result.balanced,     t_bal),
                    (result.aggressive,   t_agg),
                ]:
                    with tab_a:
                        # Beklenen getiri & risk KPI strip
                        r1, r2, r3, r4 = st.columns(4, gap="small")
                        with r1:
                            kpi_tile("BAZ SENARYO",
                                     f"{alloc.expected_return_low_pct:+.0f}%",
                                     sub="kötümser tahmin")
                        with r2:
                            kpi_tile("ORTA SENARYO",
                                     f"{alloc.expected_return_mid_pct:+.0f}%",
                                     sub="beklenen getiri")
                        with r3:
                            kpi_tile("İYİ SENARYO",
                                     f"{alloc.expected_return_high_pct:+.0f}%",
                                     sub="iyimser tahmin")
                        with r4:
                            kpi_tile("MAX KAYIP",
                                     f"{alloc.expected_max_loss_pct:.0f}%",
                                     sub="aşağı yön riski")

                        vspace(14)

                        # Treemap + Donut
                        tm_col, dn_col = st.columns([3, 2], gap="medium")
                        with tm_col:
                            section_header("Varlık Dağılımı", kicker="TREEMAP")
                            st.plotly_chart(_treemap(alloc), use_container_width=True,
                                            config={"displayModeBar": False})
                        with dn_col:
                            section_header("Sınıf Dağılımı", kicker="DONUT")
                            st.plotly_chart(_donut(alloc), use_container_width=True,
                                            config={"displayModeBar": False})

                        # Varlık tablosu
                        section_header("Varlıklar",
                                       kicker="POZİSYONLAR",
                                       meta=f"{alloc.num_assets} adet")
                        rows = []
                        for a in sorted(alloc.assets,
                                        key=lambda x: x.weight_pct, reverse=True):
                            rows.append({
                                "Sembol":  a.symbol,
                                "Ad":      (a.name[:28]
                                            if hasattr(a, "name") else ""),
                                "Tür":     a.asset_type,
                                "Ağırlık": f"{a.weight_pct:.1f}%",
                                "Tutar":   f"{a.amount:,.0f} {alloc.currency}",
                                "Risk":    getattr(a, "risk_level", "—"),
                            })
                        st.dataframe(
                            pd.DataFrame(rows),
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Ağırlık": st.column_config.TextColumn(width="small"),
                                "Risk":    st.column_config.TextColumn(width="small"),
                            })

                        vspace(8)
                        am1, am2 = st.columns(2, gap="small")
                        with am1:
                            kpi_tile("ÇEŞİTLENDİRME",
                                     f"{alloc.diversification_score:.0f}/100",
                                     sub="dağılım kalitesi")
                        with am2:
                            kpi_tile("NAKİT REZERV",
                                     f"{alloc.cash_pct:.0f}%",
                                     sub="acil likidite")

                        if getattr(alloc, "why_suitable", ""):
                            with st.expander("Neden Bu Portföy?"):
                                st.markdown(
                                    f'<span style="color:{C["t2"]};font-size:14px;">'
                                    f'{alloc.why_suitable}</span>',
                                    unsafe_allow_html=True)
                        if getattr(alloc, "main_risks", []):
                            with st.expander("Ana Riskler"):
                                for risk in alloc.main_risks:
                                    st.markdown(
                                        f'<span style="color:{C["sell"]};font-size:14px;">'
                                        f'• {risk}</span>',
                                        unsafe_allow_html=True)
