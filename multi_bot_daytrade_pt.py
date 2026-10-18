import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import pytz

st.set_page_config(page_title="Day Trading", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #111827; color: #f3f4f6; }
    h1 { color: #ffffff; font-weight: 700; margin-bottom: 0; }
    h2, h3 { color: #f9fafb; }
    .stCaption { color: #9ca3af; }
    .yield-box { position: fixed; top: 12px; right: 20px; background: #1f2937; padding: 8px 14px; border-radius: 8px; border: 1px solid #374151; z-index: 999; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

PT = pytz.timezone("America/Vancouver")

@st.cache_data(ttl=30)
def get_yield():
    try:
        tnx = yf.Ticker("^TNX")
        h = tnx.history(period="2d")
        if h.empty: return 5.09, 0.0
        cur = round(float(h["Close"].iloc[-1]), 2)
        prev = round(float(h["Close"].iloc[-2]), 2) if len(h) > 1 else cur
        return cur, round(cur - prev, 2)
    except:
        return 5.09, 0.0

yld, yld_chg = get_yield()
chg_color = "#22c55e" if yld_chg >= 0 else "#ef4444"
st.markdown(f'<div class="yield-box">10Y <b>{yld}%</b> <span style="color:{chg_color}">{yld_chg:+.2f}</span></div>', unsafe_allow_html=True)

st.title("Day Trading")
st.caption(f"Pacific Time · {datetime.now(PT).strftime('%H:%M %Z')} · Scores update on refresh")

CANDIDATES = ["CRWV", "NBIS", "IREN", "SMCI", "AMD", "NVDA", "TSLA", "AAPL", "MSFT", "META", "SPY", "QQQ", "SMH"]

RECENT_NEWS = {
    "CRWV": "Distressed bonds (~15% yields) and elevated CDS still covered into the weekend. Gartner 80% neocloud warning remains active.",
    "NBIS": "Continues to be cited with CRWV and IREN in neocloud financing coverage.",
    "IREN": "Group pressure from AI infrastructure debt concerns persists.",
    "SMCI": "Hardware names remain sensitive to AI funding worries.",
    "AMD": "Chip complex still weak; elevated yields and oil not supportive.",
    "NVDA": "AI trade under pressure from borrowing-cost concerns.",
    "SMH": "Semiconductors extended decline; macro yields restrictive."
}

@st.cache_data(ttl=40)
def get_data(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="5m", prepost=True)
        if hist.empty: return None
        hist["vwap"] = (hist["Volume"] * (hist["High"] + hist["Low"] + hist["Close"]) / 3).cumsum() / hist["Volume"].cumsum()
        price = round(float(hist["Close"].iloc[-1]), 2)
        vwap = round(float(hist["vwap"].iloc[-1]), 2)
        atr = round(float((hist["High"] - hist["Low"]).tail(10).mean()), 2)
        daily = t.history(period="10d")
        avg = daily["Volume"].mean() if not daily.empty else hist["Volume"].sum()
        rvol = round(hist["Volume"].sum() / avg, 1) if avg else 1.0
        return {"ticker": ticker, "hist": hist.tail(48), "price": price, "vwap": vwap, "atr": atr, "rvol": rvol}
    except:
        return None

def score(d, yld):
    if not d: return None
    pct = (d["price"] - d["vwap"]) / d["vwap"] * 100
    news = RECENT_NEWS.get(d["ticker"], "")
    factors = [f"vs VWAP {pct:+.1f}%", f"RVOL {d['rvol']}x", f"10Y {yld}%"]
    if news: factors.append(news)
    base = 5.0
    if pct < -0.4: base += 2.1
    elif pct > 0.4: base -= 1.5
    if d["rvol"] > 1.3: base += 0.6
    if yld > 5.05 and d["ticker"] in ["CRWV","NBIS","IREN","SMCI"]: base += 1.1
    if news: base += 0.8
    conv = min(10, max(3, int(base)))
    if conv >= 7:
        bias, like, pred = "Short", f"{min(76, 56+conv)}% downside likelihood", f"${round(d['price']-d['atr']*0.5,2)} – ${round(d['price']-d['atr']*0.1,2)}"
    elif conv <= 4:
        bias, like, pred = "Rise", f"{min(66, 46+(10-conv))}% bounce likelihood", f"${round(d['price']+d['atr']*0.1,2)} – ${round(d['price']+d['atr']*0.5,2)}"
    else:
        bias, like, pred = "Neutral", "~50% range", f"${round(d['price']-d['atr']*0.25,2)} – ${round(d['price']+d['atr']*0.25,2)}"
    return {**d, "bias": bias, "conviction": conv, "likelihood": like, "pred": pred, "factors": factors, "news": news}

def chart(d):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=d["hist"].index, open=d["hist"].Open, high=d["hist"].High, low=d["hist"].Low, close=d["hist"].Close,
                                 increasing_line_color="#22c55e", decreasing_line_color="#ef4444"))
    fig.add_trace(go.Scatter(x=d["hist"].index, y=d["hist"].vwap, mode="lines", line=dict(color="#f59e0b", width=2)))
    fig.update_layout(template="plotly_dark", height=270, margin=dict(l=2,r=2,t=12,b=2), xaxis_rangeslider_visible=False, showlegend=False,
                      paper_bgcolor="#111827", plot_bgcolor="#1f2937")
    return fig

with st.spinner("Updating..."):
    items = [score(get_data(t), yld) for t in CANDIDATES]
    items = [x for x in items if x]

shorts = sorted([x for x in items if x["bias"]=="Short"], key=lambda x: x["conviction"], reverse=True)[:3]
rises = sorted([x for x in items if x["bias"]=="Rise"], key=lambda x: x["conviction"], reverse=True)[:3]
if len(shorts)<2: shorts = sorted(items, key=lambda x: x["price"]-x["vwap"])[:3]
if len(rises)<2: rises = sorted(items, key=lambda x: x["vwap"]-x["price"])[:3]

def card(it, p):
    st.markdown(f"### {it['ticker']} · ${it['price']}")
    st.markdown(f"**{it['conviction']}/10** · {it['likelihood']}")
    st.caption(it["pred"])
    with st.expander("Why"):
        for f in it["factors"]:
            st.write("• " + f)
    st.plotly_chart(chart(it), use_container_width=True, key=p+it["ticker"])
    if it["news"]:
        st.caption(it["news"])
    st.divider()

c1, c2 = st.columns(2)
with c1:
    st.subheader("Top Shorts")
    for i in shorts: card(i, "s")
with c2:
    st.subheader("Top Rises")
    for i in rises: card(i, "r")

st.caption("10Y yield in corner updates on refresh. News older than ~12h is deprioritized. Educational only.")
