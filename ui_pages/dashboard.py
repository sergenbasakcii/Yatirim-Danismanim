"""
HedgeFund AI — Dashboard (Institutional Cockpit)
================================================
Top KPI strip with sparklines · Center BTC chart with refined timeframe
selector · Right rail with Fear & Greed gauge + AI commentary · Bottom
dense market table side-by-side with AI signal stack.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui_pages.styles import (
    C, DEC_MAP, apple_layout, page_header, render_ticker,
    fetch_ticker_data, fmt_pct, fmt_price, dec_badge, spark_svg,
)
from ui_pages.components import (
    section_header, kpi_tile, data_table, ai_insight_card,
    pill, status_dot, divider, vspace, skeleton,
)


# ══════════════════════════════════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_price_history(symbol: str, period: str = "3mo") -> pd.DataFrame:
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_sparkline(symbol: str, days: int = 30) -> list:
    try:
        import yfinance as yf
        df = yf.download(symbol, period=f"{days}d", interval="1d",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        return [float(x) for x in df["Close"].dropna().tolist()]
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_fear_greed():
    try:
        from src.fear_greed import fetch_fear_greed as _f, fear_greed_signal
        data = _f()
        val = data.get("value", 50)
        lbl = data.get("label", "Nötr")
        sig, adj = fear_greed_signal(val)
        return val, lbl, sig, adj, data.get("history", [])
    except Exception:
        return 50, "Nötr", "HOLD", 0, []


@st.cache_data(ttl=600, show_spinner=False)
def fetch_market_signals():
    watch_list = [
        ("BTC-USD",  "Bitcoin",  "crypto"),
        ("ETH-USD",  "Ethereum", "crypto"),
        ("SOL-USD",  "Solana",   "crypto"),
        ("GC=F",     "Altın",    "stock"),
        ("THYAO.IS", "Thyao",    "bist"),
        ("AAPL",     "Apple",    "stock"),
    ]
    results = []
    try:
        from src.opportunity_engine import _analyze_single_asset
        for sym, name, at in watch_list:
            try:
                r = _analyze_single_asset(sym, name, at, "", "orta", "", force=False)
                if r:
                    results.append(r)
            except Exception:
                pass
    except Exception:
        pass
    return results


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _fg_color(v: float) -> str:
    if v >= 75: return C["sell"]
    if v >= 55: return C["warn"]
    if v >= 25: return C["buy"]
    return C["buy"]


def _fg_label(v: float) -> str:
    if v >= 75: return "AŞIRI AÇGÖZLÜLÜK"
    if v >= 55: return "AÇGÖZLÜLÜK"
    if v >= 45: return "NÖTR"
    if v >= 25: return "KORKU"
    return "AŞIRI KORKU"


def _ai_commentary(fg_val: int, signals: list) -> tuple[str, str, float]:
    """Generate one-line AI commentary based on F&G + signals."""
    title = "Piyasa nötr — kademeli pozisyonlanma uygun"
    body = ("Korku &amp; Açgözlülük endeksi dengeli bölgede; volatilite "
            "yönetimi ile kademeli alım stratejisi tercih edilebilir.")
    confidence = 62.0

    if signals:
        buys = sum(1 for r in signals if "AL" in (r.decision or ""))
        sells = sum(1 for r in signals if "SAT" in (r.decision or ""))
        avg = sum(getattr(r, "composite_score", 50) or 50 for r in signals) / len(signals)
        confidence = max(40.0, min(94.0, avg))

        if fg_val >= 70 and buys >= sells:
            title = "Aşırı açgözlülük — kâr realizasyonu değerlendirilmeli"
            body = (f"<b>{buys}</b> varlıkta pozitif sinyal var, ancak F&amp;G "
                    f"{fg_val} ile aşırı bölgede. Kademeli kâr alımı ve sıkı "
                    f"stop disiplini öneriliyor.")
        elif fg_val <= 25 and buys >= sells:
            title = "Aşırı korku zonu — kontra-trend fırsat penceresi"
            body = (f"Aşırı korku ({fg_val}) genelde dip formasyonlarına eşlik "
                    f"eder. Kompozit ortalama <b>{avg:.0f}</b> seviyesinde — "
                    f"kademeli birikim için elverişli.")
        elif sells > buys:
            title = "Negatif sinyaller baskın — pozisyon küçültme"
            body = (f"<b>{sells}</b> varlıkta satım baskısı tespit edildi. "
                    f"Risk azaltma ve nakit oranını yükseltme tavsiye edilir.")
        else:
            title = f"Karışık görünüm — seçici alım ({buys} pozitif, {sells} negatif)"
            body = (f"Watchlist genelinde karma sinyal yapısı. Ortalama kompozit "
                    f"<b>{avg:.0f}</b>; en yüksek skorlu varlıklara odaklanılması "
                    f"öneriliyor.")

    # ── AI overlay (ücretsiz Gemini Flash; key yoksa statik metne düşer) ──────
    ai_body, ai_tag = _maybe_ai_market_body(fg_val, signals, title, confidence)
    if ai_body:
        body = ai_body

    return title, body, confidence, ai_tag


def _maybe_ai_market_body(fg_val: int, signals: list,
                          static_title: str, conf: float) -> tuple[str, bool]:
    """Try to produce an AI market paragraph. Returns (html_body, is_ai)."""
    try:
        from src.ai_commentary import ai_generate, ai_enabled, SYSTEM_ANALYST
    except Exception:
        return "", False
    if not ai_enabled():
        return "", False

    buys = sum(1 for r in signals if "AL" in (r.decision or "")) if signals else 0
    sells = sum(1 for r in signals if "SAT" in (r.decision or "")) if signals else 0
    avg = (sum(getattr(r, "composite_score", 50) or 50 for r in signals) / len(signals)
           if signals else 50)
    top = ""
    if signals:
        ranked = sorted(signals,
                        key=lambda r: getattr(r, "composite_score", 0) or 0,
                        reverse=True)[:3]
        top = ", ".join(f"{getattr(r,'symbol','?')} ({getattr(r,'decision','?')}, "
                        f"{getattr(r,'composite_score',0) or 0:.0f})" for r in ranked)

    prompt = (
        f"Piyasa verisi:\n"
        f"- Kripto Korku & Açgözlülük Endeksi: {fg_val}/100\n"
        f"- Pozitif sinyal sayısı: {buys}, negatif: {sells}\n"
        f"- Ortalama kompozit skor: {avg:.0f}/100\n"
        f"- En yüksek skorlu varlıklar: {top or 'veri yok'}\n\n"
        f"Bu tabloyu 2-3 cümlede yorumla. Genel piyasa duygusunu, "
        f"dikkat edilmesi gereken riski ve kademeli pozisyonlanma açısından "
        f"ne anlama geldiğini söyle. Tek paragraf, sade Türkçe."
    )
    ck = f"dash:{fg_val}:{buys}:{sells}:{avg:.0f}"
    res = ai_generate(prompt, system=SYSTEM_ANALYST, cache_key=ck,
                      max_tokens=260, temperature=0.45)
    if res.get("ok") and res.get("text"):
        # Plain text → light HTML (escape, keep line breaks subtle)
        from html import escape
        txt = escape(res["text"]).replace("\n\n", "<br><br>").replace("\n", " ")
        return txt, True
    return "", False


# Kart-icin fiyat formatci (BTC vs BIST vb.)
def _fp(price: float, sym: str) -> str:
    if not price or price <= 0:
        return "—"
    if sym in ("THYAO", "BIST"):
        return f"₺{price:,.2f}" if price < 10000 else f"₺{price:,.0f}"
    if sym == "ALTIN":
        return f"${price:,.0f}"
    if price >= 1000:
        return f"${price:,.0f}"
    return f"${price:,.2f}"


# ══════════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════════
def render():
    render_ticker()
    page_header(
        "Dashboard",
        "Piyasa özetinden fırsat sinyallerine — institutional intelligence cockpit",
    )

    ticker_data = fetch_ticker_data()
    fg_val, fg_lbl, fg_sig, fg_adj, fg_hist = fetch_fear_greed()
    fg_col = _fg_color(fg_val)

    by_sym = {d["sym"]: d for d in ticker_data}

    # ── KPI STRIP ─────────────────────────────────────────────────────────────
    section_header("Piyasa Özeti", kicker="ÖZET",
                   meta=f"Son güncelleme · {pd.Timestamp.now().strftime('%H:%M')}")

    kpi_specs = [
        ("BTC / USD",   "BTC",   "BTC-USD"),
        ("ETH / USD",   "ETH",   "ETH-USD"),
        ("BIST 100",    "BIST",  "XU100.IS"),
        ("ALTIN / oz",  "ALTIN", "GC=F"),
    ]
    cols = st.columns(4, gap="small")
    for col, (label, sym, yf_sym) in zip(cols, kpi_specs):
        d = by_sym.get(sym)
        spark = fetch_sparkline(yf_sym, days=30)
        with col:
            kpi_tile(
                label=label,
                value=_fp(d["price"] if d else 0, sym),
                delta=(d["chg"] if d else None),
                sub="bugün",
                sparkline_vals=spark or None,
            )

    vspace(20)

    # ── CHART + RIGHT RAIL ────────────────────────────────────────────────────
    chart_col, rail_col = st.columns([2.2, 1], gap="medium")

    # ── BTC chart ─────────────────────────────────────────────────────────────
    with chart_col:
        section_header(
            "BTC / USD",
            kicker="ANA GRAFİK",
            meta=_fp(by_sym.get("BTC", {}).get("price", 0), "BTC"),
        )

        period_map = {"1G": "1d", "1H": "1wk", "1A": "1mo",
                      "3A": "3mo", "6A": "6mo", "1Y": "1y"}
        st.session_state.setdefault("dash_period", "3mo")

        per_cols = st.columns(len(period_map), gap="small")
        for (lbl, val), pc in zip(period_map.items(), per_cols):
            with pc:
                if st.button(
                    lbl, key=f"dp_{lbl}",
                    use_container_width=True,
                    type="primary" if st.session_state["dash_period"] == val else "secondary",
                ):
                    st.session_state["dash_period"] = val
                    st.rerun()

        df_btc = fetch_price_history("BTC-USD", st.session_state["dash_period"])
        st.markdown('<div class="card flat" style="padding:14px 16px 8px;">',
                    unsafe_allow_html=True)

        if not df_btc.empty:
            ema20 = df_btc["Close"].ewm(span=20).mean()
            line_col = C["accent"]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_btc.index, y=df_btc["Close"], name="BTC/USD",
                line=dict(color=line_col, width=1.8),
                fill="tozeroy",
                fillcolor="rgba(91,140,255,0.06)",
                hovertemplate="<b>%{x|%d %b}</b><br>$%{y:,.0f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=df_btc.index, y=ema20, name="EMA 20",
                line=dict(color=C["t3"], width=1, dash="dot"),
                hovertemplate="EMA 20: $%{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(**apple_layout(
                height=300, hovermode="x unified", showlegend=False,
            ))
            fig.update_yaxes(rangemode="tozero" if df_btc["Close"].min() > 0 else "normal",
                             autorange=True)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})

            # Inline legend
            st.markdown(
                f'<div style="display:flex;gap:18px;padding:0 4px 6px;">'
                f'  <div style="display:flex;align-items:center;gap:6px;">'
                f'    <div style="width:18px;height:2px;background:{line_col};"></div>'
                f'    <span style="font-size:11px;color:{C["t3"]};">BTC/USD</span></div>'
                f'  <div style="display:flex;align-items:center;gap:6px;">'
                f'    <div style="width:18px;border-top:1px dotted {C["t3"]};"></div>'
                f'    <span style="font-size:11px;color:{C["t3"]};">EMA 20</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            skeleton(rows=4, h=18)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Right rail: F&G + AI commentary ──────────────────────────────────────
    with rail_col:
        section_header("Piyasa Duyarlılığı", kicker="DUYARLILIK")

        r = 52; cx = cy = 64
        circ = 2 * 3.14159 * r
        arc = circ * fg_val / 100
        st.markdown(
            f'<div class="card flat" style="padding:18px;text-align:center;">'
            f'  <svg width="128" height="128" viewBox="0 0 128 128" '
            f'       style="display:block;margin:0 auto 8px;">'
            f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'            stroke="{C["divider"]}" stroke-width="8"/>'
            f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'            stroke="{fg_col}" stroke-width="8" '
            f'            stroke-dasharray="{arc:.1f} {circ:.1f}" '
            f'            stroke-linecap="round" '
            f'            transform="rotate(-90 {cx} {cy})"/>'
            f'    <text x="50%" y="46%" text-anchor="middle" '
            f'          dominant-baseline="middle" fill="{C["t1"]}" '
            f'          font-size="26" font-weight="700" '
            f'          font-family="Inter Tight,sans-serif">{fg_val}</text>'
            f'    <text x="50%" y="64%" text-anchor="middle" '
            f'          dominant-baseline="middle" fill="{C["t3"]}" '
            f'          font-size="9" font-weight="600" letter-spacing="1.4" '
            f'          font-family="Inter Tight,sans-serif">F &amp; G</text>'
            f'  </svg>'
            f'  <div style="font-size:11px;font-weight:700;color:{fg_col};'
            f'              letter-spacing:0.10em;text-transform:uppercase;">'
            f'    {_fg_label(fg_val)}'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 7-day mini bars
        if fg_hist:
            hist7 = list(reversed(fg_hist[:7]))
            days_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
            vals7 = [h.get("value", 50) for h in hist7]
            bars = ""
            for i, v in enumerate(vals7):
                cb = C["buy"] if v >= 55 else C["warn"] if v >= 40 else C["sell"]
                pct = (v / 100) * 100
                lbl = days_tr[i] if i < len(days_tr) else ""
                bars += (
                    f'<div style="flex:1;display:flex;flex-direction:column;'
                    f'align-items:center;gap:4px;">'
                    f'  <div style="width:100%;background:{C["divider"]};'
                    f'              border-radius:3px;height:36px;display:flex;'
                    f'              align-items:flex-end;overflow:hidden;">'
                    f'    <div style="width:100%;background:{cb};'
                    f'                border-radius:3px;height:{pct:.0f}%;'
                    f'                opacity:.85;"></div></div>'
                    f'  <span style="font-size:10px;color:{C["t3"]};">{lbl}</span>'
                    f'</div>'
                )
            vspace(10)
            st.markdown(
                f'<div class="card flat" style="padding:14px 16px;">'
                f'  <div class="lbl" style="margin-bottom:8px;">7 GÜNLÜK TREND</div>'
                f'  <div style="display:flex;align-items:flex-end;gap:5px;height:54px;">'
                f'    {bars}'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        vspace(14)
        market_signals = fetch_market_signals()
        title, body, conf, is_ai = _ai_commentary(fg_val, market_signals)
        ai_insight_card(title=title, body=body,
                        tag="AI YORUM · GEMINI" if is_ai else "PIYASA YORUMU",
                        confidence=conf)

    vspace(20)

    # ── BOTTOM: market table + signal stack ──────────────────────────────────
    bot_l, bot_r = st.columns([1.4, 1], gap="medium")

    # ── Market table ─────────────────────────────────────────────────────────
    with bot_l:
        section_header("Canlı Piyasa", kicker="VARLIKLAR",
                       meta=f"{len(ticker_data)} sembol")

        sym_icons = {"BTC": "₿", "ETH": "Ξ", "BNB": "◈", "SOL": "◎",
                     "XRP": "✦", "THYAO": "◆", "BIST": "◇", "ALTIN": "Au"}

        rows = []
        for d in ticker_data:
            chg = d["chg"]
            tone = "positive" if chg >= 0 else "negative"
            arrow = "+" if chg >= 0 else ""
            icon = sym_icons.get(d["sym"], "·")
            rows.append([
                (f'<span style="display:inline-flex;align-items:center;gap:8px;">'
                 f'  <span style="color:{C["t3"]};font-size:13px;width:14px;'
                 f'               display:inline-block;text-align:center;">{icon}</span>'
                 f'  <span style="font-weight:600;color:{C["t1"]};">{d["sym"]}</span>'
                 f'</span>'),
                _fp(d["price"], d["sym"]),
                pill(f'{arrow}{chg:.2f}%', tone),
            ])

        data_table(
            columns=[
                {"label": "Varlık",  "width": "1fr",   "align": "left"},
                {"label": "Fiyat",   "width": "120px", "align": "right", "cls": "num"},
                {"label": "Değişim", "width": "100px", "align": "right"},
            ],
            rows=rows,
        )

    # ── AI signal stack ──────────────────────────────────────────────────────
    with bot_r:
        section_header("YZ Karar Sinyalleri", kicker="SİNYALLER",
                       meta=f"{len(market_signals)} varlık")

        if not market_signals:
            from ui_pages.components import empty_state
            empty_state("Henüz sinyal yok",
                        "Fırsat motoru çalıştığında YZ kararları burada görünecek.",
                        icon="◇")
        else:
            # Sort by composite_score descending
            signals_sorted = sorted(
                market_signals,
                key=lambda r: getattr(r, "composite_score", 0) or 0,
                reverse=True,
            )
            rows = []
            for r in signals_sorted[:6]:
                dm = DEC_MAP.get(r.decision, DEC_MAP["İZLE"])
                ret1d = r.return_1d or 0
                tone = "positive" if ret1d >= 0 else "negative"
                arrow = "+" if ret1d >= 0 else ""
                score = int(getattr(r, "composite_score", 50) or 50)

                # Mini score bar inline
                bar = (
                    f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                    f'  <span style="font-weight:700;color:{dm["col"]};'
                    f'               font-variant-numeric:tabular-nums;">{score}</span>'
                    f'  <span style="display:inline-block;width:36px;height:3px;'
                    f'               background:rgba(148,163,184,0.12);border-radius:2px;'
                    f'               overflow:hidden;">'
                    f'    <span style="display:block;width:{score}%;height:3px;'
                    f'                 background:{dm["col"]};border-radius:2px;"></span>'
                    f'  </span>'
                    f'</span>'
                )

                rows.append([
                    f'<span style="font-weight:600;color:{C["t1"]};">{r.symbol}</span>',
                    dec_badge(r.decision, size="sm"),
                    bar,
                    pill(f'{arrow}{ret1d:.2f}%', tone),
                ])

            data_table(
                columns=[
                    {"label": "Sembol", "width": "1fr",  "align": "left"},
                    {"label": "Karar",  "width": "84px", "align": "left"},
                    {"label": "Skor",   "width": "92px", "align": "right"},
                    {"label": "1G",     "width": "82px", "align": "right"},
                ],
                rows=rows,
            )

            # Quick "Analiz Et" buttons row (top 3)
            vspace(10)
            top3 = signals_sorted[:3]
            bcols = st.columns(len(top3))
            for bc, r in zip(bcols, top3):
                with bc:
                    if st.button(f"→ {r.symbol} Analiz",
                                 key=f"dash_goto_{r.symbol}",
                                 use_container_width=True,
                                 type="secondary"):
                        st.session_state["analysis_run_sym"] = r.symbol
                        st.session_state["analysis_result"] = None
                        st.session_state["page"] = "Analiz"
                        st.rerun()

    vspace(24)

    # ── Legal ─────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="warn-bar">'
        '  <b>Yasal Uyarı</b>&ensp;Bu uygulama yalnızca bilgilendirme amaçlıdır. '
        'Yatırım tavsiyesi değildir. Geçmiş performans gelecek sonuçları garanti etmez.'
        '</div>',
        unsafe_allow_html=True,
    )
