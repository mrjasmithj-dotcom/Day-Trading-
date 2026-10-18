import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
import requests

st.set_page_config(page_title="Day Trading", layout="wide")

PT = pytz.timezone("America/Vancouver")

def now_pt():
    return datetime.now(PT)

st.title("Day Trading")
st.caption("Pacific Time · Multi-bot scanner · Top Shorts & Top Rises")

st.warning("""
**Educational prototype only. Not financial advice.**  
Free Yahoo data can lag. Leveraged/inverse products reset daily and carry decay risk.  
Do not hold overnight. You can lose money.
""")

# Simple candidate universe for scanner
CANDIDATES = ["CRWV", "NBIS", "IREN", "SMCI", "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "META",
              "SPY", "QQQ", "IWM", "SMH", "XLE", "XLF"]

def price_bot(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="5m", prepost=True)
        if hist.empty:
            return None, None, None
        hist["vwap"] = (hist["Volume"] * (hist["High"] + hist["Low"] + hist["Close"]) / 3).cumsum() / hist["Volume"].cumsum()
        live = hist["Close"].iloc[-1]
        vol = hist["Volume"].sum()
        avg_vol = stock.info.get("averageVolume", vol) or vol
        rvol = vol / avg_vol if avg_vol else 1.0
        return hist, live, rvol
    except:
        return None, None, None

def news_bot(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        catalysts = [n for n in news if any(k in n.get("title", "").lower() for k in ["contract", "deal", "terminate", "upgrade", "downgrade", "beat", "miss"])]
        return news[:5], catalysts
    except:
        return [], []

def peer_bot(ticker):
    # Simplified peer check
    return {"relative": "In-line", "basket": "Mixed"}

def gex_bot(ticker):
    return {"regime": "neutral", "call_wall": None, "put_wall": None}

def scenario_group(live_price, vwap, rvol, gex, news_titles, catalysts, peer_info, ticker):
    scenarios = []
    if live_price and vwap:
        if live_price > vwap and rvol and rvol > 1.5 and catalysts:
            scenarios.append(("Hot / Up", 75, "Above VWAP + volume + catalyst"))
        elif live_price < vwap and rvol and rvol > 1.5:
            scenarios.append(("Down", 70, "Below VWAP + volume"))
        else:
            scenarios.append(("Chop", 50, "Near VWAP or mixed signals"))
    else:
        scenarios.append(("Chop", 45, "Limited data"))
    return scenarios

def master_consensus(scenarios):
    if not scenarios:
        return "Chop / Neutral", 40, "No clear signal"
    best = max(scenarios, key=lambda x: x[1])
    avg = np.mean([s[1] for s in scenarios])
    confidence = min(90, max(40, best[1] - avg + 50))
    grade = best[0]
    if best[1] < 45:
        grade = "Chop / Neutral"
    return grade, confidence, best[2]

def score_out_of_10(grade, conf):
    if "Hot" in grade or "Up" in grade:
        return min(10, int(conf / 10))
    if "Down" in grade:
        return min(10, int(conf / 10))
    return 5

# Sidebar / Search
st.sidebar.header("Ticker Search")
search_ticker = st.sidebar.text_input("Enter ticker", "").upper()
if st.sidebar.button("Scan Ticker") and search_ticker:
    st.session_state["selected"] = search_ticker

# Auto-scan lists (simplified stable ranking)
st.header("Top Shorts")
shorts = []
for t in CANDIDATES:
    hist, price, rvol = price_bot(t)
    if price:
        _, conf, reason = master_consensus(scenario_group(price, hist["vwap"].iloc[-1] if hist is not None else None, rvol, {}, [], [], {}, t))
        if "Down" in reason or (hist is not None and price < hist["vwap"].iloc[-1]):
            shorts.append((t, score_out_of_10("Down", conf), reason))
shorts = sorted(shorts, key=lambda x: x[1], reverse=True)[:5]

for t, score, reason in shorts:
    if st.button(f"{t}  ·  Conviction {score}/10", key=f"short_{t}"):
        st.session_state["selected"] = t

st.header("Top Rises")
rises = []
for t in CANDIDATES:
    hist, price, rvol = price_bot(t)
    if price:
        grade, conf, reason = master_consensus(scenario_group(price, hist["vwap"].iloc[-1] if hist is not None else None, rvol, {}, [], [], {}, t))
        if "Hot" in grade or "Up" in grade:
            rises.append((t, score_out_of_10(grade, conf), reason))
rises = sorted(rises, key=lambda x: x[1], reverse=True)[:5]

for t, score, reason in rises:
    if st.button(f"{t}  ·  Conviction {score}/10", key=f"rise_{t}"):
        st.session_state["selected"] = t

# Detail view
if "selected" in st.session_state:
    ticker = st.session_state["selected"]
    st.divider()
    st.subheader(f"{ticker} Detail")
    hist, live_price, rvol = price_bot(ticker)
    news, catalysts = news_bot(ticker)
    vwap = hist["vwap"].iloc[-1] if hist is not None and not hist.empty else None
    scenarios = scenario_group(live_price, vwap, rvol, {}, [n.get("title","") for n in news], catalysts, {}, ticker)
    grade, conf, reason = master_consensus(scenarios)
    news_score = min(10, len(catalysts)*3 + 4)
    conv_score = score_out_of_10(grade, conf)

    col1, col2, col3 = st.columns(3)
    col1.metric("Live Price", f"${live_price:.2f}" if live_price else "N/A")
    col2.metric("News Score", f"{news_score}/10")
    col3.metric("Conviction", f"{conv_score}/10")
    st.write(f"**Grade:** {grade}")
    st.write(f"**Reason:** {reason}")

    if hist is not None and not hist.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"], name="Price"))
        fig.add_trace(go.Scatter(x=hist.index, y=hist["vwap"], mode="lines", name="VWAP", line=dict(color="orange")))
        fig.update_layout(title=f"{ticker} 5m Candles + VWAP", xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

    st.write("**Latest Headlines:**")
    for n in news:
        st.write(f"- {n.get('title', 'No title')}")

st.caption(f"Last update: {now_pt().strftime('%Y-%m-%d %H:%M %Z')}")
