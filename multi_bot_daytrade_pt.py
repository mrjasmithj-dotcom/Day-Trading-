import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

st.set_page_config(page_title="Day Trading", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0b0e13; color: #e6e8eb; }
    h1, h2, h3 { color: #f8fafc !important; }
    .stCaption { color: #9aa3ae; }
</style>
""", unsafe_allow_html=True)

PT = pytz.timezone("America/Vancouver")
st.title("Day Trading")
st.caption(f"Pacific Time · Scores based on latest available data (Friday close + updates) · {datetime.now(PT).strftime('%H:%M %Z')}")

CANDIDATES = ["CRWV", "NBIS", "IREN", "SMCI", "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "META", "SPY", "QQQ", "SMH"]

@st.cache_data(ttl=60)
def get_full(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="5m", prepost=True)
        if hist.empty: return None
        hist["vwap"] = (hist["Volume"] * (hist["High"] + hist["Low"] + hist["Close"]) / 3).cumsum() / hist["Volume"].cumsum()
        price = round(float(hist["Close"].iloc[-1]), 2)
        vwap = round(float(hist["vwap"].iloc[-1]), 2)
        daily = t.history(period="10d")
        avg_vol = daily["Volume"].mean() if not daily.empty else hist["Volume"].sum()
        rvol = round(hist["Volume"].sum() / avg_vol, 1) if avg_vol else 1.0
        news = t.news or []
        return {"ticker": ticker, "hist": hist.tail(80), "price": price, "vwap": vwap, "rvol": rvol, "news": news[:4]}
    except:
        return None

def classify(d):
    if not d: return None
    pct = (d["price"] - d["vwap"]) / d["vwap"] * 100
    news_score = min(10, 3 + len(d["news"]) * 2)
    rvol_boost = min(2, max(0, d["rvol"] - 1))
    why = [f"Last price ${d['price']} vs VWAP ${d['vwap']} ({pct:+.1f}%)"]
    if pct < -0.4:
        bias = "Short"
        conviction = min(10, int(6 + abs(pct) * 0.6 + rvol_boost))
        why.append("Trading meaningfully below VWAP")
        if d["rvol"] > 1.2: why.append(f"RVOL {d['rvol']}x")
    elif pct > 0.4:
        bias = "Rise"
        conviction = min(10, int(6 + pct * 0.6 + rvol_boost))
        why.append("Trading meaningfully above VWAP")
        if d["rvol"] > 1.2: why.append(f"RVOL {d['rvol']}x")
    else:
        bias = "Neutral"
        conviction = 5
        why.append("Close to VWAP")
    if d["news"]:
        why.append(f"{len(d['news'])} headlines available")
    else:
        why.append("Limited headlines over weekend")
    return {**d, "bias": bias, "conviction": conviction, "news_score": news_score, "why": why}

def render_chart(d):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=d["hist"].index, open=d["hist"].Open, high=d["hist"].High,
        low=d["hist"].Low, close=d["hist"].Close,
        increasing_line_color="#22c55e", decreasing_line_color="#ef4444"
    ))
    fig.add_trace(go.Scatter(x=d["hist"].index, y=d["hist"].vwap, mode="lines",
                             name="VWAP", line=dict(color="#f59e0b", width=2.2)))
    fig.update_layout(template="plotly_dark", height=340, margin=dict(l=6,r=6,t=24,b=6),
                      xaxis_rangeslider_visible=False, showlegend=False,
                      paper_bgcolor="#0b0e13", plot_bgcolor="#11151c")
    return fig

with st.spinner("Loading latest available data..."):
    raw = [classify(get_full(t)) for t in CANDIDATES]
    data = [x for x in raw if x]

shorts = sorted([x for x in data if x["bias"] == "Short"], key=lambda x: x["conviction"], reverse=True)[:4]
rises = sorted([x for x in data if x["bias"] == "Rise"], key=lambda x: x["conviction"], reverse=True)[:4]
if len(shorts) < 2:
    shorts = sorted(data, key=lambda x: x["price"] - x["vwap"])[:4]
if len(rises) < 2:
    rises = sorted(data, key=lambda x: x["vwap"] - x["price"])[:4]

def card(item, prefix):
    st.markdown(f"### {item['ticker']} · ${item['price']}")
    st.markdown(f"**Conviction {item['conviction']}/10** · News {item['news_score']}/10")
    with st.expander("Why this score"):
        for line in item["why"]:
            st.write(f"• {line}")
    st.plotly_chart(render_chart(item), use_container_width=True, key=prefix+item["ticker"])
    st.write("**News**")
    if item["news"]:
        for n in item["news"]:
            st.caption("• " + n.get("title", ""))
    else:
        st.caption("No recent headlines available.")
    st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Top Shorts")
    for it in shorts:
        card(it, "s")
with col2:
    st.subheader("Top Rises")
    for it in rises:
        card(it, "r")

st.caption("Scores calculated from the most recent available price vs VWAP and news. Updates automatically on page refresh.")
