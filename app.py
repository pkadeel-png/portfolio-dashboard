import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

st.set_page_config(
    page_title="AI Portfolio Dashboard",
    page_icon="📡",
    layout="wide"
)

# ── STYLE ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #2a2a3e;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .ticker-label { font-size: 18px; font-weight: 700; color: #e8e8f0; font-family: monospace; }
    .signal-high  { color: #ef4444; font-weight: 600; }
    .signal-mid   { color: #f59e0b; font-weight: 600; }
    .signal-low   { color: #22c55e; font-weight: 600; }
    div[data-testid="stMetric"] { background: #1e1e2e; border-radius: 8px; padding: 10px 14px; }
</style>
""", unsafe_allow_html=True)

# ── CONFIG ───────────────────────────────────────────────────────────────────
DEFAULT_TICKERS = ['AAOI', 'MU', 'GLW', 'ONTO', 'POET', 'MRVL', 'KLIC', 'LSRCY', 'SAP', 'AMBA', 'BE', 'AIS']

def signal_badge(pct):
    if pct is None: return "⚪ N/A", "signal-low"
    v = pct * 100 if pct < 1 else pct
    if v >= 20: return f"🔴 HIGH  ({v:.1f}%)", "signal-high"
    if v >= 10: return f"🟡 MODERATE  ({v:.1f}%)", "signal-mid"
    return f"🟢 LOW  ({v:.1f}%)", "signal-low"

def fmt_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    try:
        v = float(v)
        if abs(v) >= 1e9: return f"{v/1e9:.2f}B"
        if abs(v) >= 1e6: return f"{v/1e6:.1f}M"
        if abs(v) >= 1e3: return f"{v/1e3:.0f}K"
        return str(int(v))
    except: return "—"

def fmt_pct(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    try:
        v = float(v)
        return f"{v*100:.1f}%" if v < 1 else f"{v:.1f}%"
    except: return "—"

@st.cache_data(ttl=3600)
def fetch_short_interest(tickers):
    rows = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            rows.append({
                "Ticker":         ticker,
                "Short % Float":  info.get("shortPercentOfFloat"),
                "Days to Cover":  info.get("shortRatio"),
                "Shares Short":   info.get("sharesShort"),
                "Float Shares":   info.get("floatShares"),
                "Avg Volume":     info.get("averageVolume"),
                "52w High":       info.get("fiftyTwoWeekHigh"),
                "52w Low":        info.get("fiftyTwoWeekLow"),
                "Price":          info.get("currentPrice") or info.get("regularMarketPrice"),
            })
            time.sleep(0.25)
        except Exception as e:
            rows.append({"Ticker": ticker, "Short % Float": None, "Days to Cover": None,
                         "Shares Short": None, "Float Shares": None, "Avg Volume": None,
                         "52w High": None, "52w Low": None, "Price": None})
    return rows

@st.cache_data(ttl=3600)
def fetch_institutional(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.institutional_holders
        if df is not None and not df.empty:
            return df
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_insider(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.insider_transactions
        if df is not None and not df.empty:
            return df.head(8)
    except:
        pass
    return None

# ── HEADER ───────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.title("📡 AI Supply Chain Portfolio")
    st.caption(f"Short interest · Institutional flow (13F) · Insider trades  |  Last loaded: {datetime.now().strftime('%d %b %Y %H:%M')}")
with col_refresh:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    selected = st.multiselect(
        "Tickers to track",
        options=DEFAULT_TICKERS,
        default=DEFAULT_TICKERS
    )
    add_ticker = st.text_input("Add a ticker", placeholder="e.g. NVDA").upper().strip()
    if add_ticker and add_ticker not in selected:
        selected.append(add_ticker)

    st.divider()
    st.markdown("**Signal thresholds**")
    high_thresh = st.slider("High short % (red)", 10, 40, 20)
    mid_thresh  = st.slider("Moderate short % (yellow)", 5, 20, 10)

    st.divider()
    st.markdown("**Data sources**")
    st.markdown("- Short interest: Yahoo Finance / FINRA (bi-monthly)")
    st.markdown("- Institutional: Yahoo Finance / SEC 13F (quarterly)")
    st.markdown("- Insider trades: Yahoo Finance / SEC Form 4")
    st.markdown("- No API key required")

if not selected:
    st.warning("Select at least one ticker in the sidebar.")
    st.stop()

# ── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Short Interest", "🏛️ Fund Flow (13F)", "👤 Insider Activity"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SHORT INTEREST
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.spinner("Fetching short interest data..."):
        data = fetch_short_interest(tuple(selected))

    # Summary KPI row
    valid = [d for d in data if d["Short % Float"] is not None]
    if valid:
        avg_short = sum((d["Short % Float"]*100 if d["Short % Float"] < 1 else d["Short % Float"]) for d in valid) / len(valid)
        high_count = sum(1 for d in valid if (d["Short % Float"]*100 if d["Short % Float"]<1 else d["Short % Float"]) >= high_thresh)
        most_shorted = max(valid, key=lambda d: d["Short % Float"])
        ms_pct = most_shorted["Short % Float"]
        ms_val = ms_pct*100 if ms_pct < 1 else ms_pct

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Short % (portfolio)", f"{avg_short:.1f}%")
        c2.metric("High-short names (≥ red threshold)", high_count)
        c3.metric("Most shorted", most_shorted["Ticker"], f"{ms_val:.1f}% of float")
        c4.metric("Tickers tracked", len(selected))
        st.divider()

    # Per-ticker cards
    cols = st.columns(2)
    for i, d in enumerate(data):
        with cols[i % 2]:
            pct_raw = d["Short % Float"]
            pct_val = (pct_raw * 100 if pct_raw is not None and pct_raw < 1 else pct_raw) if pct_raw else None
            badge, badge_cls = signal_badge(pct_raw)

            with st.container(border=True):
                r1, r2 = st.columns([2, 3])
                with r1:
                    st.markdown(f"### {d['Ticker']}")
                    st.markdown(f"<span class='{badge_cls}'>{badge}</span>", unsafe_allow_html=True)
                with r2:
                    m1, m2 = st.columns(2)
                    m1.metric("Days to Cover", f"{d['Days to Cover']:.1f}" if d['Days to Cover'] else "—")
                    m2.metric("Shares Short", fmt_num(d['Shares Short']))

                st.caption(
                    f"Float: {fmt_num(d['Float Shares'])}  ·  "
                    f"Avg Vol: {fmt_num(d['Avg Volume'])}  ·  "
                    f"Price: ${d['Price']:.2f}" if d['Price'] else
                    f"Float: {fmt_num(d['Float Shares'])}  ·  Avg Vol: {fmt_num(d['Avg Volume'])}"
                )

    # Full table
    st.divider()
    st.subheader("Full table")
    table_rows = []
    for d in data:
        pct = d["Short % Float"]
        pct_val = (pct * 100 if pct < 1 else pct) if pct else None
        table_rows.append({
            "Ticker": d["Ticker"],
            "Price": f"${d['Price']:.2f}" if d['Price'] else "—",
            "Short % Float": fmt_pct(pct),
            "Days to Cover": f"{d['Days to Cover']:.1f}" if d['Days to Cover'] else "—",
            "Shares Short": fmt_num(d['Shares Short']),
            "Float": fmt_num(d['Float Shares']),
            "Avg Volume": fmt_num(d['Avg Volume']),
            "Signal": "🔴 High" if pct_val and pct_val >= high_thresh else ("🟡 Moderate" if pct_val and pct_val >= mid_thresh else ("🟢 Low" if pct_val else "—")),
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — INSTITUTIONAL FLOW
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Institutional Holders (SEC 13F, quarterly)")
    st.caption("Shows current top holders and share counts. Quarter-over-quarter change requires prior quarter data — use WhaleWisdom for full history.")

    for ticker in selected:
        with st.expander(f"**{ticker}** — Top Institutional Holders", expanded=False):
            with st.spinner(f"Loading {ticker}..."):
                df_inst = fetch_institutional(ticker)

            if df_inst is not None and not df_inst.empty:
                display = df_inst.copy()
                # Format columns
                for col in display.columns:
                    if col == 'Shares':
                        display[col] = display[col].apply(fmt_num)
                    elif col == '% Out':
                        display[col] = display[col].apply(fmt_pct)
                    elif col == 'Value':
                        display[col] = display[col].apply(lambda x: f"${fmt_num(x)}")
                    elif col == 'Date Reported':
                        display[col] = pd.to_datetime(display[col], errors='coerce').dt.strftime('%Y-%m-%d')

                st.dataframe(display, use_container_width=True, hide_index=True)

                # Simple bar chart of top holders by % out
                if '% Out' in df_inst.columns and 'Holder' in df_inst.columns:
                    chart_df = df_inst[['Holder', '% Out']].dropna().copy()
                    chart_df['% Out'] = chart_df['% Out'].apply(lambda x: float(x)*100 if float(x) < 1 else float(x))
                    chart_df = chart_df.set_index('Holder').head(8)
                    st.bar_chart(chart_df, height=220)
            else:
                st.info(f"No institutional holder data available for {ticker} from Yahoo Finance.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — INSIDER ACTIVITY
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Insider Transactions (SEC Form 4)")
    st.caption("Recent buy/sell activity by executives and directors.")

    all_insider_rows = []
    for ticker in selected:
        df_ins = fetch_insider(ticker)
        if df_ins is not None and not df_ins.empty:
            df_ins = df_ins.copy()
            df_ins.insert(0, "Ticker", ticker)
            all_insider_rows.append(df_ins)

    if all_insider_rows:
        combined = pd.concat(all_insider_rows, ignore_index=True)
        # Clean up columns
        for col in combined.columns:
            if 'Shares' in col or 'Value' in col:
                combined[col] = combined[col].apply(fmt_num)
            if 'Date' in col or 'date' in col:
                try:
                    combined[col] = pd.to_datetime(combined[col], errors='coerce').dt.strftime('%Y-%m-%d')
                except: pass
        st.dataframe(combined, use_container_width=True, hide_index=True)
    else:
        st.info("No recent insider transaction data found.")

st.divider()
st.caption("Data via Yahoo Finance (FINRA short interest, SEC 13F institutional holdings, SEC Form 4 insider trades). Refreshes every hour. Not financial advice.")
