import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

st.set_page_config(page_title="Day Trading", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    h1, h2, h3 { color: #f8fafc !important; }
    .stCaption { color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

PT = pytz.timezone("America/Vancouver")
st.title("Day Trading")
st.caption(f"Pacific Time · {datetime.now(PT).strftime('%H:%M %Z')}")

CANDIDATES = ["CRWV", "NBIS", "IREN", "SMCI", "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "META", "SPY", "QQQ", "SMH"]

@st.cache_data(ttl=90)
def get_full(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="5m", prepost=True)
        if hist.empty:
            return None
        hist["vwap"] = (hist["Volume"] * (hist["High"] + hist["Low"] + hist["Close"]) / 3).cumsum() / hist["Volume"].cumsum()
        price = round(float(hist["Close"].iloc[-1]), 2)
        vwap = round(float(hist["vwap"].iloc[-1]), 2)
        news = t.news or []
        return {"ticker": ticker, "hist": hist.tail(60), "price": price, "vwap": vwap, "news": news[:3]}
    except:
        return None

def classify(d):
    if not d: return None
    pct = (d["price"] - d["vwap"]) / d["vwap"] * 100
    news_score = min(10, 5 + len(d["news"]))
    if pct < -0.4:
        bias, conv = "Short", min(10, 6 + int(abs(pct)))
        reason = f"{pct:.1f}% below VWAP"
    elif pct > 0.4:
        bias, conv = "Rise", min(10, 6 + int(pct))
        reason = f"{pct:.1f}% above VWAP"
    else:
        bias, conv = "Neutral", 5
        reason = "Near VWAP"
    return {**d, "bias": bias, "conviction": conv, "news_score": news_score, "reason": reason}

def render_chart(d):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=d["hist"].index, open=d["hist"].Open, high=d["hist"].High,
        low=d["hist"].Low, close=d["hist"].Close,
        increasing_line_color="#22c55e", decreasing_line_color="#ef4444"
    ))
    fig.add_trace(go.Scatter(x=d["hist"].index, y=d["hist"].vwap, mode="lines",
                             name="VWAP", line=dict(color="#f59e0b", width=2)))
    fig.update_layout(template="plotly_dark", height=320, margin=dict(l=10, r=10, t=30, b=10),
                      xaxis_rangeslider_visible=False, showlegend=False,
                      paper_bgcolor="#0f172a", plot_bgcolor="#1e293b")
    return fig

with st.spinner("Loading..."):
    data = [classify(get_full(t)) for t in CANDIDATES]
    data = [x for x in data if x]

shorts = sorted([x for x in data if x["bias"] == "Short"], key=lambda x: x["conviction"], reverse=True)[:4]
rises = sorted([x for x in data if x["bias"] == "Rise"], key=lambda x: x["conviction"], reverse=True)[:4]
if len(shorts) < 3:
    shorts = sorted(data, key=lambda x: x["price"] - x["vwap"])[:4]
if len(rises) < 3:
    rises = sorted(data, key=lambda x: x["vwap"] - x["price"])[:4]

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top Shorts")
    for item in shorts:
        st.markdown(f"### {item['ticker']}  ·  ${item['price']}")
        st.markdown(f"**Conviction {item['conviction']}/10**  ·  News {item['news_score']}/10  ·  {item['reason']}")
        st.plotly_chart(render_chart(item), use_container_width=True, key="sc"+item["ticker"])
        st.write("**News**")
        for n in item["news"]:
            st.caption("• " + n.get("title", "No title"))
        st.divider()

with col2:
    st.subheader("Top Rises")
    for item in rises:
        st.markdown(f"### {item['ticker']}  ·  ${item['price']}")
        st.markdown(f"**Conviction {item['conviction']}/10**  ·  News {item['news_score']}/10  ·  {item['reason']}")
        st.plotly_chart(render_chart(item), use_container_width=True, key="rc"+item["ticker"])
        st.write("**News**")
        for n in item["news"]:
            st.caption("• " + n.get("title", "No title"))
        st.divider()

st.caption("Each card shows ticker, scores, chart with VWAP, then news. Refresh to update.")
