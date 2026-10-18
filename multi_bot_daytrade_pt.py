import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import pytz

st.set_page_config(page_title="Day Trading", layout="wide", initial_sidebar_state="collapsed")

# Dark theme styling
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .stMetric { background-color: #1a1f2e; padding: 10px; border-radius: 8px; }
    div[data-testid="stVerticalBlock"] > div { background-color: #161b22; padding: 12px; border-radius: 8px; margin-bottom: 8px; }
    h1, h2, h3 { color: #ffffff; }
    .stCaption { color: #8b949e; }
</style>
""", unsafe_allow_html=True)

PT = pytz.timezone("America/Vancouver")

def now_pt():
    return datetime.now(PT)

st.title("Day Trading")
st.caption(f"Pacific Time  ·  Multi-bot scanner  ·  {now_pt().strftime('%H:%M %Z')}")

st.info("Educational prototype. Free Yahoo data can lag. Not financial advice. Leveraged products reset daily.")

CANDIDATES = ["CRWV", "NBIS", "IREN", "SMCI", "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "META", "SPY", "QQQ", "SMH"]

@st.cache_data(ttl=45)
def get_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="5m", prepost=True)
        if hist.empty:
            return None
        hist["vwap"] = (hist["Volume"] * (hist["High"] + hist["Low"] + hist["Close"]) / 3).cumsum() / hist["Volume"].cumsum()
        price = round(float(hist["Close"].iloc[-1]), 2)
        vwap = round(float(hist["vwap"].iloc[-1]), 2)
        avg_vol = stock.info.get("averageVolume") or hist["Volume"].sum()
        rvol = round(hist["Volume"].sum() / avg_vol, 1) if avg_vol else 1.0
        news = stock.news or []
        return {"hist": hist, "price": price, "vwap": vwap, "rvol": rvol, "news": news[:3]}
    except:
        return None

def evaluate(ticker):
    d = get_data(ticker)
    if not d:
        return None
    price, vwap, rvol = d["price"], d["vwap"], d["rvol"]
    news_score = min(10, 5 + len(d["news"]))
    if price < vwap and rvol > 1.3:
        bias = "Short"
        conviction = min(10, int(6 + rvol))
        reason = f"Below VWAP · elevated volume ({rvol}x)"
    elif price > vwap and rvol > 1.3:
        bias = "Rise"
        conviction = min(10, int(6 + rvol))
        reason = f"Above VWAP · elevated volume ({rvol}x)"
    else:
        bias = "Neutral"
        conviction = 5
        reason = "Near VWAP or low volume"
    return {**d, "ticker": ticker, "bias": bias, "news_score": news_score, "conviction": conviction, "reason": reason}

# Search
col_search, _ = st.columns([1, 3])
with col_search:
    search = st.text_input("Search ticker", placeholder="e.g. CRWV").upper()
    if st.button("Scan", use_container_width=True) and search:
        st.session_state["selected"] = search

with st.spinner("Updating lists..."):
    evaluated = [evaluate(t) for t in CANDIDATES]
    evaluated = [e for e in evaluated if e]

shorts = sorted([e for e in evaluated if e["bias"] == "Short"], key=lambda x: x["conviction"], reverse=True)[:5]
rises = sorted([e for e in evaluated if e["bias"] == "Rise"], key=lambda x: x["conviction"], reverse=True)[:5]

left, right = st.columns(2)

with left:
    st.subheader("Top Shorts")
    for e in shorts or []:
        with st.container(border=True):
            st.markdown(f"**{e['ticker']}**  ${e['price']}   News {e['news_score']}/10   **Conviction {e['conviction']}/10**")
            st.caption(e["reason"])
            if st.button("Open", key=f"s{e['ticker']}", use_container_width=True):
                st.session_state["selected"] = e["ticker"]

with right:
    st.subheader("Top Rises")
    for e in rises or []:
        with st.container(border=True):
            st.markdown(f"**{e['ticker']}**  ${e['price']}   News {e['news_score']}/10   **Conviction {e['conviction']}/10**")
            st.caption(e["reason"])
            if st.button("Open", key=f"r{e['ticker']}", use_container_width=True):
                st.session_state["selected"] = e["ticker"]

if "selected" in st.session_state:
    ticker = st.session_state["selected"]
    data = evaluate(ticker)
    if data:
        st.divider()
        st.subheader(f"{ticker}   ${data['price']}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Price", f"${data['price']}")
        m2.metric("VWAP", f"${data['vwap']}")
        m3.metric("News", f"{data['news_score']}/10")
        m4.metric("Conviction", f"{data['conviction']}/10")
        st.write(f"**Bias:** {data['bias']}  ·  {data['reason']}")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data["hist"].index,
            open=data["hist"]["Open"], high=data["hist"]["High"],
            low=data["hist"]["Low"], close=data["hist"]["Close"],
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
            name="Price"
        ))
        fig.add_trace(go.Scatter(
            x=data["hist"].index, y=data["hist"]["vwap"],
            mode="lines", name="VWAP", line=dict(color="#ffa726", width=2)
        ))
        fig.update_layout(
            template="plotly_dark", height=500,
            xaxis_rangeslider_visible=False,
            title=f"{ticker} · 5-minute + VWAP",
            paper_bgcolor="#0e1117", plot_bgcolor="#161b22"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("News")
        for item in data["news"]:
            st.write(f"• {item.get('title', '')}")

st.caption("Dark high-contrast layout. Refresh to update. Click Open for full view.")
