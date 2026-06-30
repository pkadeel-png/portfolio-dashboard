import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import time
from datetime import datetime

st.set_page_config(
    page_title="AI Portfolio Dashboard",
    page_icon="📡",
    layout="wide"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .signal-high { color: #ef4444; font-weight: 600; }
    .signal-mid  { color: #f59e0b; font-weight: 600; }
    .signal-low  { color: #22c55e; font-weight: 600; }
    .news-card {
        border: 1px solid #2a2a3e;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        background: #1e1e2e;
    }
    .news-title { font-size: 14px; font-weight: 600; line-height: 1.4; }
    .news-meta  { font-size: 11px; color: #6b6b80; margin-top: 4px; }
    .news-ticker-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        background: #1a1a3e;
        color: #818cf8;
        margin-right: 6px;
    }
    a { color: #818cf8; text-decoration: none; }
    a:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_TICKERS = ['AAOI','MU','GLW','ONTO','POET','MRVL','KLIC','LSRCY','SAP','AMBA','BE','AIS']
TICKERS_FILE    = "saved_tickers.json"
CACHE_FILE      = "previous_readings.json"

# ── PERSIST TICKER LIST ───────────────────────────────────────────────────────
def load_ticker_list():
    if os.path.exists(TICKERS_FILE):
        try:
            with open(TICKERS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except:
            pass
    return DEFAULT_TICKERS.copy()

def save_ticker_list(tickers):
    with open(TICKERS_FILE, "w") as f:
        json.dump(tickers, f)

# ── SESSION STATE INIT ────────────────────────────────────────────────────────
if "ticker_list" not in st.session_state:
    st.session_state.ticker_list = load_ticker_list()
if "selected_tickers" not in st.session_state:
    st.session_state.selected_tickers = load_ticker_list()

# ── BASELINE CACHE ────────────────────────────────────────────────────────────
def load_previous():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_current(data_list):
    snapshot = {}
    for d in data_list:
        snapshot[d["Ticker"]] = {
            "short_pct": d["Short % Float"],
            "dtc":       d["Days to Cover"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    with open(CACHE_FILE, "w") as f:
        json.dump(snapshot, f)

# ── FORMAT HELPERS ────────────────────────────────────────────────────────────
def to_pct_display(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, "—"
    try:
        v = float(v)
        val = v * 100 if v < 1 else v
        return val, f"{val:.1f}%"
    except:
        return None, "—"

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

def delta_str(current, previous, unit="", higher_is_bad=True):
    if current is None or previous is None:
        return None, "off"
    try:
        diff = float(current) - float(previous)
        if abs(diff) < 0.01:
            return "no change", "off"
        arrow = "▲" if diff > 0 else "▼"
        label = f"{arrow} {abs(diff):.1f}{unit} vs last reading"
        color = "inverse" if higher_is_bad else "normal"
        return label, color
    except:
        return None, "off"

def signal_badge(pct_val, high_thresh, mid_thresh):
    if pct_val is None: return "⚪ N/A", "signal-low"
    if pct_val >= high_thresh: return f"🔴 HIGH ({pct_val:.1f}%)", "signal-high"
    if pct_val >= mid_thresh:  return f"🟡 MODERATE ({pct_val:.1f}%)", "signal-mid"
    return f"🟢 LOW ({pct_val:.1f}%)", "signal-low"

def time_ago(ts):
    """Convert a Unix timestamp or datetime to a human-readable 'X ago' string."""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            dt = pd.to_datetime(ts)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
        diff = datetime.now() - dt
        s = int(diff.total_seconds())
        if s < 3600:   return f"{s//60}m ago"
        if s < 86400:  return f"{s//3600}h ago"
        if s < 604800: return f"{s//86400}d ago"
        return dt.strftime("%d %b %Y")
    except:
        return str(ts)[:10]

# ── DATA FETCH ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_short_interest(tickers):
    rows = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            rows.append({
                "Ticker":        ticker,
                "Short % Float": info.get("shortPercentOfFloat"),
                "Days to Cover": info.get("shortRatio"),
                "Shares Short":  info.get("sharesShort"),
                "Float Shares":  info.get("floatShares"),
                "Avg Volume":    info.get("averageVolume"),
                "Price":         info.get("currentPrice") or info.get("regularMarketPrice"),
            })
            time.sleep(0.25)
        except:
            rows.append({"Ticker": ticker, "Short % Float": None, "Days to Cover": None,
                         "Shares Short": None, "Float Shares": None,
                         "Avg Volume": None, "Price": None})
    return rows

@st.cache_data(ttl=3600)
def fetch_institutional(ticker):
    try:
        df = yf.Ticker(ticker).institutional_holders
        if df is not None and not df.empty:
            return df
    except: pass
    return None

@st.cache_data(ttl=3600)
def fetch_insider(ticker):
    try:
        df = yf.Ticker(ticker).insider_transactions
        if df is not None and not df.empty:
            return df.head(8)
    except: pass
    return None

@st.cache_data(ttl=1800)   # news refreshes every 30 min
def fetch_news_for_ticker(ticker):
    """Fetch news via yfinance for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        news = t.news  # list of dicts
        if not news:
            return []
        results = []
        for item in news[:15]:
            content = item.get("content", {})
            # yfinance >= 0.2.x wraps in a 'content' dict
            if content:
                title     = content.get("title", "")
                summary   = content.get("summary", "")
                pub_date  = content.get("pubDate", "")
                link      = content.get("canonicalUrl", {}).get("url", "") or \
                            content.get("clickThroughUrl", {}).get("url", "")
                provider  = content.get("provider", {}).get("displayName", "")
            else:
                # older yfinance format
                title    = item.get("title", "")
                summary  = item.get("summary", item.get("description", ""))
                pub_date = item.get("providerPublishTime", "")
                link     = item.get("link", "")
                provider = item.get("publisher", "")

            if title:
                results.append({
                    "ticker":   ticker,
                    "title":    title,
                    "summary":  summary,
                    "date":     pub_date,
                    "link":     link,
                    "provider": provider,
                })
        return results
    except Exception as e:
        return []

@st.cache_data(ttl=1800)
def fetch_all_news(tickers):
    """Aggregate and deduplicate news across all tickers."""
    all_news = []
    seen_titles = set()
    for ticker in tickers:
        items = fetch_news_for_ticker(ticker)
        for item in items:
            key = item["title"].strip().lower()[:80]
            if key not in seen_titles:
                seen_titles.add(key)
                all_news.append(item)
        time.sleep(0.2)
    # Sort by date descending (best effort)
    def sort_key(x):
        try:
            d = x["date"]
            if isinstance(d, (int, float)):
                return float(d)
            return float(pd.to_datetime(d).timestamp())
        except:
            return 0
    all_news.sort(key=sort_key, reverse=True)
    return all_news

# ── HEADER ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([5, 1])
with c1:
    st.title("📡 AI Supply Chain Portfolio")
    st.caption(f"Short interest · Institutional flow (13F) · Insider trades · News  |  {datetime.now().strftime('%d %b %Y %H:%M')}")
with c2:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("**Manage tickers**")

    col_input, col_btn = st.columns([3, 1])
    with col_input:
        new_ticker = st.text_input(
            "Add ticker", placeholder="e.g. NVDA",
            label_visibility="collapsed", key="new_ticker_input"
        ).upper().strip()
    with col_btn:
        st.write("")
        add_clicked = st.button("Add", use_container_width=True)

    if add_clicked and new_ticker:
        if new_ticker not in st.session_state.ticker_list:
            st.session_state.ticker_list.append(new_ticker)
            st.session_state.selected_tickers.append(new_ticker)
            save_ticker_list(st.session_state.ticker_list)
            st.success(f"{new_ticker} added and saved.")
            st.rerun()
        else:
            st.info(f"{new_ticker} already in list.")

    remove_ticker = st.selectbox(
        "Remove ticker", options=["—"] + st.session_state.ticker_list,
        index=0, key="remove_select"
    )
    if st.button("Remove selected", use_container_width=True):
        if remove_ticker != "—":
            if remove_ticker in st.session_state.ticker_list:
                st.session_state.ticker_list.remove(remove_ticker)
            if remove_ticker in st.session_state.selected_tickers:
                st.session_state.selected_tickers.remove(remove_ticker)
            save_ticker_list(st.session_state.ticker_list)
            st.success(f"{remove_ticker} removed.")
            st.rerun()

    st.markdown("**Active tickers**")
    st.session_state.selected_tickers = st.multiselect(
        "Select which to show",
        options=st.session_state.ticker_list,
        default=[t for t in st.session_state.selected_tickers
                 if t in st.session_state.ticker_list],
        label_visibility="collapsed"
    )

    if st.button("↺ Reset to defaults", use_container_width=True):
        st.session_state.ticker_list      = DEFAULT_TICKERS.copy()
        st.session_state.selected_tickers = DEFAULT_TICKERS.copy()
        save_ticker_list(DEFAULT_TICKERS)
        st.rerun()

    st.divider()
    st.markdown("**Signal thresholds**")
    high_thresh = st.slider("🔴 High short %", 10, 40, 20)
    mid_thresh  = st.slider("🟡 Moderate short %", 5, 20, 10)

    st.divider()
    st.markdown("**News settings**")
    news_per_ticker = st.slider("Articles per ticker (per-ticker view)", 3, 15, 5)
    show_summary    = st.checkbox("Show article summaries", value=True)

    st.divider()
    st.markdown("**Delta tracking**")
    st.caption("▲▼ compares to last data load.")
    if st.button("🗑️ Reset baseline", use_container_width=True):
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
        st.success("Baseline cleared.")

    st.divider()
    st.markdown("**Data sources**")
    st.markdown("- Short interest: Yahoo Finance / FINRA")
    st.markdown("- Institutional: Yahoo Finance / SEC 13F")
    st.markdown("- Insider trades: Yahoo Finance / SEC Form 4")
    st.markdown("- News: Yahoo Finance (30 min cache)")
    st.markdown("- No API key required")

selected = st.session_state.selected_tickers
if not selected:
    st.warning("No tickers selected. Add or select tickers in the sidebar.")
    st.stop()

# ── LOAD MARKET DATA ──────────────────────────────────────────────────────────
previous = load_previous()
with st.spinner("Fetching live market data..."):
    data = fetch_short_interest(tuple(selected))
save_current(data)

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Short Interest",
    "🏛️ Fund Flow (13F)",
    "👤 Insider Activity",
    "📰 News"
])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — SHORT INTEREST
# ────────────────────────────────────────────────────────────────────────────
with tab1:
    valid = [d for d in data if d["Short % Float"] is not None]

    if valid:
        def to_val(d):
            v = d["Short % Float"]
            return float(v) * 100 if float(v) < 1 else float(v)

        avg_short    = sum(to_val(d) for d in valid) / len(valid)
        high_count   = sum(1 for d in valid if to_val(d) >= high_thresh)
        most_shorted = max(valid, key=lambda d: float(d["Short % Float"]))
        ms_val       = to_val(most_shorted)

        prev_vals = [
            previous[d["Ticker"]]["short_pct"] for d in valid
            if d["Ticker"] in previous and previous[d["Ticker"]]["short_pct"] is not None
        ]
        prev_avg = (sum((float(v)*100 if float(v)<1 else float(v)) for v in prev_vals) / len(prev_vals)
                    if prev_vals else None)
        prev_high = (
            sum(1 for d in valid
                if d["Ticker"] in previous
                and previous[d["Ticker"]]["short_pct"] is not None
                and ((float(previous[d["Ticker"]]["short_pct"])*100
                      if float(previous[d["Ticker"]]["short_pct"]) < 1
                      else float(previous[d["Ticker"]]["short_pct"])) >= high_thresh))
            if previous else None
        )

        avg_delta,  avg_color  = delta_str(avg_short,  prev_avg,  unit="%", higher_is_bad=True)
        high_delta, high_color = delta_str(high_count, prev_high, unit="",  higher_is_bad=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Avg Short % (portfolio)", f"{avg_short:.1f}%",
                  delta=avg_delta, delta_color=avg_color)
        k2.metric(f"High-short names (≥{high_thresh}%)", high_count,
                  delta=high_delta, delta_color=high_color)
        k3.metric("Most shorted", most_shorted["Ticker"],
                  delta=f"{ms_val:.1f}% of float")
        k4.metric("Tickers tracked", len(selected))

        sample_prev = next((previous[d["Ticker"]] for d in valid if d["Ticker"] in previous), None)
        if sample_prev:
            st.caption(f"▲▼ delta vs last reading: {sample_prev.get('timestamp','—')}")
        st.divider()

    cols = st.columns(2)
    for i, d in enumerate(data):
        pct_val, pct_str = to_pct_display(d["Short % Float"])
        dtc = d["Days to Cover"]
        prev_d       = previous.get(d["Ticker"], {})
        prev_pct_raw = prev_d.get("short_pct")
        prev_dtc     = prev_d.get("dtc")
        prev_pct_val = None
        if prev_pct_raw is not None:
            prev_pct_val = float(prev_pct_raw)*100 if float(prev_pct_raw)<1 else float(prev_pct_raw)
        pct_delta, pct_color = delta_str(pct_val, prev_pct_val, unit="%", higher_is_bad=True)
        dtc_delta, dtc_color = delta_str(dtc, prev_dtc, unit="d", higher_is_bad=True)
        badge, badge_cls     = signal_badge(pct_val, high_thresh, mid_thresh)
        with cols[i % 2]:
            with st.container(border=True):
                r1, r2 = st.columns([2, 3])
                with r1:
                    st.markdown(f"### {d['Ticker']}")
                    st.markdown(f"<span class='{badge_cls}'>{badge}</span>", unsafe_allow_html=True)
                    if d.get("Price"):
                        st.caption(f"Price: ${d['Price']:.2f}")
                with r2:
                    m1, m2 = st.columns(2)
                    m1.metric("Short % Float", pct_str, delta=pct_delta, delta_color=pct_color)
                    m2.metric("Days to Cover", f"{dtc:.1f}" if dtc else "—",
                              delta=dtc_delta, delta_color=dtc_color)
                st.caption(
                    f"Shares short: {fmt_num(d['Shares Short'])}  ·  "
                    f"Float: {fmt_num(d['Float Shares'])}  ·  "
                    f"Avg vol: {fmt_num(d['Avg Volume'])}"
                )

    st.divider()
    st.subheader("Full table")
    table_rows = []
    for d in data:
        pct_val, pct_str = to_pct_display(d["Short % Float"])
        prev_d = previous.get(d["Ticker"], {})
        prev_pct_raw = prev_d.get("short_pct")
        prev_pct_val = None
        if prev_pct_raw is not None:
            prev_pct_val = float(prev_pct_raw)*100 if float(prev_pct_raw)<1 else float(prev_pct_raw)
        if pct_val is not None and prev_pct_val is not None:
            diff = pct_val - prev_pct_val
            chg = f"▲ +{diff:.1f}%" if diff > 0.01 else (f"▼ {diff:.1f}%" if diff < -0.01 else "—")
        else:
            chg = "—"
        table_rows.append({
            "Ticker":        d["Ticker"],
            "Price":         f"${d['Price']:.2f}" if d.get("Price") else "—",
            "Short % Float": pct_str,
            "Chg vs prev":   chg,
            "Days to Cover": f"{d['Days to Cover']:.1f}" if d["Days to Cover"] else "—",
            "Shares Short":  fmt_num(d["Shares Short"]),
            "Float":         fmt_num(d["Float Shares"]),
            "Avg Volume":    fmt_num(d["Avg Volume"]),
            "Signal":        ("🔴 High" if pct_val and pct_val >= high_thresh
                              else ("🟡 Moderate" if pct_val and pct_val >= mid_thresh
                              else ("🟢 Low" if pct_val else "—"))),
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — INSTITUTIONAL FLOW
# ────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Institutional Holders — SEC 13F (quarterly)")
    st.caption("Top holders by shares held.")
    for ticker in selected:
        with st.expander(f"**{ticker}** — Top Institutional Holders", expanded=False):
            with st.spinner(f"Loading {ticker}..."):
                df_inst = fetch_institutional(ticker)
            if df_inst is not None and not df_inst.empty:
                display = df_inst.copy()
                for col in display.columns:
                    if col == "Shares":
                        display[col] = display[col].apply(fmt_num)
                    elif col == "% Out":
                        display[col] = display[col].apply(fmt_pct)
                    elif col == "Value":
                        display[col] = display[col].apply(lambda x: f"${fmt_num(x)}")
                    elif "Date" in col:
                        try:
                            display[col] = pd.to_datetime(display[col], errors="coerce").dt.strftime("%Y-%m-%d")
                        except: pass
                st.dataframe(display, use_container_width=True, hide_index=True)
                if "% Out" in df_inst.columns and "Holder" in df_inst.columns:
                    chart_df = df_inst[["Holder","% Out"]].dropna().copy()
                    chart_df["% Out"] = chart_df["% Out"].apply(
                        lambda x: float(x)*100 if float(x)<1 else float(x))
                    st.bar_chart(chart_df.set_index("Holder").head(8), height=220)
            else:
                st.info(f"No institutional holder data available for {ticker}.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — INSIDER ACTIVITY
# ────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Insider Transactions — SEC Form 4")
    st.caption("Recent buy/sell activity by executives and directors.")
    all_rows = []
    for ticker in selected:
        df_ins = fetch_insider(ticker)
        if df_ins is not None and not df_ins.empty:
            df_ins = df_ins.copy()
            df_ins.insert(0, "Ticker", ticker)
            all_rows.append(df_ins)
    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)
        for col in combined.columns:
            if "Shares" in col or "Value" in col:
                combined[col] = combined[col].apply(fmt_num)
            if "Date" in col or "date" in col:
                try:
                    combined[col] = pd.to_datetime(combined[col], errors="coerce").dt.strftime("%Y-%m-%d")
                except: pass
        st.dataframe(combined, use_container_width=True, hide_index=True)
    else:
        st.info("No recent insider transaction data found.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 4 — NEWS
# ────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("📰 Portfolio News Feed")
    st.caption("Latest news across all your tickers via Yahoo Finance · refreshes every 30 min")

    # View toggle
    news_view = st.radio(
        "View",
        ["All tickers (combined feed)", "By ticker"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.divider()

    # ── COMBINED FEED ─────────────────────────────────────────────────────────
    if news_view == "All tickers (combined feed)":
        with st.spinner("Loading news for all tickers..."):
            all_news = fetch_all_news(tuple(selected))

        if not all_news:
            st.info("No news found. Yahoo Finance may be temporarily unavailable.")
        else:
            # Ticker filter chips
            filter_tickers = st.multiselect(
                "Filter by ticker",
                options=selected,
                default=selected,
                label_visibility="collapsed"
            )
            filtered = [n for n in all_news if n["ticker"] in filter_tickers]
            st.caption(f"Showing {len(filtered)} articles")
            st.write("")

            for item in filtered:
                title    = item.get("title", "No title")
                summary  = item.get("summary", "")
                link     = item.get("link", "")
                provider = item.get("provider", "")
                date_val = item.get("date", "")
                ticker   = item.get("ticker", "")
                age      = time_ago(date_val) if date_val else ""

                with st.container(border=True):
                    # Ticker badge + age
                    meta_cols = st.columns([1, 6])
                    with meta_cols[0]:
                        st.markdown(
                            f"<span class='news-ticker-badge'>{ticker}</span>",
                            unsafe_allow_html=True
                        )
                    with meta_cols[1]:
                        st.caption(f"{provider}  ·  {age}" if provider else age)

                    # Title as link
                    if link:
                        st.markdown(f"**[{title}]({link})**")
                    else:
                        st.markdown(f"**{title}**")

                    # Summary
                    if show_summary and summary:
                        st.caption(summary[:220] + ("…" if len(summary) > 220 else ""))

    # ── BY TICKER ─────────────────────────────────────────────────────────────
    else:
        for ticker in selected:
            with st.expander(f"**{ticker}** — Latest News", expanded=False):
                with st.spinner(f"Loading news for {ticker}..."):
                    ticker_news = fetch_news_for_ticker(ticker)

                if not ticker_news:
                    st.info(f"No recent news found for {ticker}.")
                    continue

                for item in ticker_news[:news_per_ticker]:
                    title    = item.get("title", "No title")
                    summary  = item.get("summary", "")
                    link     = item.get("link", "")
                    provider = item.get("provider", "")
                    date_val = item.get("date", "")
                    age      = time_ago(date_val) if date_val else ""

                    with st.container(border=True):
                        st.caption(f"{provider}  ·  {age}" if provider else age)
                        if link:
                            st.markdown(f"**[{title}]({link})**")
                        else:
                            st.markdown(f"**{title}**")
                        if show_summary and summary:
                            st.caption(summary[:220] + ("…" if len(summary) > 220 else ""))

st.divider()
st.caption("Data via Yahoo Finance (FINRA short interest · SEC 13F · SEC Form 4 · News). Not financial advice.")
