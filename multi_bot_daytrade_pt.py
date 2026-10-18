"""
Multi-Bot Institutional Short-Term Outlook App
Pacific Time (Vancouver, BC) based.
Live Yahoo data where available (pre/post/regular).
Specialist bots + scenario analysis group → consensus grade.

Bots simulated:
- Price/Tape Bot: Live quote + 5m candles + session VWAP + RVOL (PT)
- News Bot: Recent headlines
- Options/GEX Bot: Regime, walls
- Technicals Bot: Levels, relative strength
- Scenario Group: Bull/Hot, Chop, Down, Bottom realities
- Master: Consensus outlook for next hours / day

NOT financial advice. Educational prototype only.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests
import pytz
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="Multi-Bot Day Trade Outlook (PT)", layout="wide")

PT = pytz.timezone("America/Los_Angeles")

DISCLAIMER = """
**⚠️ CRITICAL DISCLAIMER**

Educational prototype only. **NOT financial advice.**

- Free Yahoo data via yfinance is unofficial, can lag, and is not true exchange SIP real-time.
- Leverage/inverse products have decay and reset risk even intraday. Do not hold overnight.
- Scenario analysis is probabilistic simulation based on limited public data. Markets can reverse sharply.
- AI/sector weakness or any regime can override single-ticker signals.
- You can lose money. Do your own research. Consult a licensed advisor.
"""

st.title("Multi-Bot Short-Term Outlook (Pacific Time)")
st.caption("Vancouver / PT based. Live Yahoo stream proxies + specialist bots + multi-scenario consensus.")
st.warning(DISCLAIMER)

ticker = st.sidebar.text_input("Ticker", "NVDA").upper().strip()
auto_mode = st.sidebar.checkbox("Auto-refresh (efficient differential)", value=True)
st.sidebar.caption("Price ~10s | News 30s | Peers/GEX ~60-120s")

def now_pt():
    return datetime.now(PT)

@st.cache_data(ttl=10)
def price_bot(ticker):
    try:
        stock = yf.Ticker(ticker)
        # 5m with pre/post for extended hours awareness
        hist = stock.history(period="2d", interval="5m", prepost=True)
        if hist.empty:
            return None, None, None
        hist.index = hist.index.tz_convert(PT)
        live = stock.fast_info.get("lastPrice") or hist["Close"].iloc[-1]
        # Session VWAP approximation (regular hours preferred, but use available)
        hist["pv"] = hist["Close"] * hist["Volume"]
        hist["cum_pv"] = hist["pv"].cumsum()
        hist["cum_vol"] = hist["Volume"].cumsum()
        hist["vwap"] = hist["cum_pv"] / hist["cum_vol"].replace(0, np.nan)
        rvol = hist["Volume"].tail(6).mean() / hist["Volume"].head(20).mean() if len(hist) > 20 else 1.0
        return hist, live, rvol
    except Exception as e:
        st.error(f"Price bot error: {e}")
        return None, None, None

@st.cache_data(ttl=30)
def news_bot(ticker):
    """Enhanced News Bot: fresher headlines + catalyst detection (contracts, terminations, etc.)"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.get_news() if hasattr(stock, "get_news") else getattr(stock, "news", [])
        if not news:
            return [], []
        # Prioritize recent and high-impact keywords
        catalysts = []
        keywords = ["contract", "deal", "win", "award", "terminate", "termination", "loss", "cut", "upgrade", "downgrade", "beat", "miss", "fda", "approval"]
        for n in news[:10]:
            title = n.get("title", "").lower()
            if any(k in title for k in keywords):
                catalysts.append(n.get("title", ""))
        return news[:5], catalysts
    except Exception as e:
        return [], []

@st.cache_data(ttl=60)
def peer_bot(ticker):
    """Dedicated Peer/Basket Comparison Bot: relative performance vs same-sector peers"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        industry_key = info.get("industryKey")
        
        peers = []
        if industry_key:
            try:
                ind = yf.Industry(industry_key)
                top = ind.top_companies
                if top is not None and not top.empty:
                    peers = top.index.tolist()[:8]
            except:
                pass
        
        # Hardcoded baskets for common groups (flexible for AI/neocloud etc.)
        baskets = {
            "neocloud": ["CRWV", "NBIS", "IREN", "APLD", "CORZ", "WULF", "HUT"],
            "chip": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "INTC", "QCOM"],
            "semiconductor": ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
            "pharma": ["PFE", "MRK", "LLY", "JNJ", "ABBV", "BMY"],
            "energy": ["XOM", "CVX", "COP", "EOG", "SLB"],
            "oil": ["XOM", "CVX", "COP", "OXY"]
        }
        for key, group in baskets.items():
            if key in ticker.lower() or key in industry.lower() or key in sector.lower():
                peers = list(set(peers + group))[:10]
                break
        
        if not peers:
            return {"sector": sector, "industry": industry, "peers": [], "relative": "No peers found"}
        
        # Compare daily % change
        data = yf.download(peers + [ticker], period="1d", progress=False, threads=True)
        if data.empty:
            return {"sector": sector, "industry": industry, "peers": peers, "relative": "Data unavailable"}
        
        closes = data["Close"] if "Close" in data else data
        changes = {}
        for p in peers + [ticker]:
            if p in closes.columns and len(closes[p].dropna()) > 1:
                chg = (closes[p].iloc[-1] / closes[p].iloc[0] - 1) * 100
                changes[p] = chg
        
        ticker_chg = changes.get(ticker, 0)
        peer_avg = np.mean([v for k, v in changes.items() if k != ticker]) if len(changes) > 1 else 0
        relative = ticker_chg - peer_avg
        status = "Outperforming basket" if relative > 1 else ("Lagging basket" if relative < -1 else "In line with basket")
        
        return {
            "sector": sector,
            "industry": industry,
            "peers": peers[:6],
            "ticker_change": round(ticker_chg, 2),
            "peer_avg_change": round(peer_avg, 2),
            "relative": status,
            "relative_pct": round(relative, 2),
            "peer_changes": {k: round(v, 2) for k, v in changes.items() if k != ticker}
        }
    except Exception as e:
        return {"error": str(e), "relative": "Error"}

@st.cache_data(ttl=60)
def gex_bot(ticker):
    try:
        r = requests.get(f"https://algoxflow.com/api/gexmap?ticker={ticker}", timeout=8)
        return r.json() if r.status_code == 200 else {}
    except:
        return {}

def scenario_group(price, vwap, rvol, gex, news_titles, catalysts, peer_info, ticker):
    scenarios = []
    # Bull / Hot
    bull_score = 0
    if price and vwap and price > vwap:
        bull_score += 30
    if rvol and rvol > 1.5:
        bull_score += 20
    if gex.get("regime") == "negative":
        bull_score += 15  # trend expansion
    if any("beat" in str(t).lower() or "upgrade" in str(t).lower() or "positive" in str(t).lower() for t in news_titles):
        bull_score += 25
    scenarios.append(("Bull / Hot", bull_score, "Price reclaiming VWAP + catalysts + expansion regime"))

    # Chop
    chop_score = 40
    if price and vwap and abs(price - vwap) / vwap < 0.005:
        chop_score += 30
    if gex.get("regime") == "positive":
        chop_score += 20
    scenarios.append(("Chop / Range", chop_score, "Near VWAP, positive gamma dampening, mixed flow"))

    # Down
    down_score = 0
    if price and vwap and price < vwap:
        down_score += 30
    if any("miss" in str(t).lower() or "downgrade" in str(t).lower() or "weak" in str(t).lower() or "cut" in str(t).lower() for t in news_titles):
        down_score += 25
    # Flexible for AI/neocloud weakness
    if ticker in ["NVDA", "AMD", "SMCI", "CRWV", "NBIS", "PLTR"] or "ai" in ticker.lower():
        down_score += 15  # regime bias example
    scenarios.append(("Down", down_score, "Below VWAP + negative catalysts or sector pressure"))

    # Bottom
    bottom_score = 20
    if rvol and rvol > 2 and price and vwap and price < vwap * 0.98:
        bottom_score += 25
    scenarios.append(("Bottom / Bounce potential", bottom_score, "High volume washout near support"))

    return scenarios

# === CATIE EVALUATOR ROUTING DICTIONARY ===
ROUTING = {
    "SPY": {"long": "UPRO", "short": "SPXU", "domain": "BROAD_INDEX"},
    "QQQ": {"long": "TQQQ", "short": "SQQQ", "domain": "BROAD_INDEX"},
    "IWM": {"long": "TNA", "short": "TZA", "domain": "BROAD_INDEX"},
    "SMH": {"long": "SOXL", "short": "SOXS", "domain": "SECTOR_ETF"},
    "XLE": {"long": "ERX", "short": "ERY", "domain": "SECTOR_ETF"},
    "XLF": {"long": "FAS", "short": "FAZ", "domain": "SECTOR_ETF"},
    "XLV": {"long": "CURE", "short": "DRV", "domain": "SECTOR_ETF"},
    "XBI": {"long": "LABU", "short": "LABD", "domain": "SECTOR_ETF"},
    "GLD": {"long": "UGL", "short": "GLL", "domain": "COMMODITY_TRUST"},
    "SLV": {"long": "AGQ", "short": "ZSL", "domain": "COMMODITY_TRUST"},
    "USO": {"long": "UCO", "short": "SCO", "domain": "COMMODITY_TRUST"},
    "IBIT": {"long": "BITU", "short": "SBIT", "domain": "DIGITAL_ASSET_ETF"},
}

def classify_and_route(ticker, bias):
    if ticker in ROUTING:
        r = ROUTING[ticker]
        vehicle = r["long"] if bias == "LONG" else r["short"]
        return r["domain"], vehicle, "LEVERAGED_ETF_3X" if bias == "LONG" else "INVERSE_ETF_3X"
    # Single stock default
    return "SINGLE_STOCK_EQUITY", ticker, "EQUITY_DIRECT"

def evaluator_engine(ticker, live_price, vwap, rvol, catalysts, peer_info, scenarios):
    """CATIE Module A approximation"""
    now = now_pt()
    hour = now.hour
    # Window check (avoid before 6:45 AM PT ~09:45 EST and after 10:30 AM PT ~13:30 EST)
    in_window = 6.75 <= hour + now.minute/60 <= 10.5
    rvol_ok = rvol and rvol >= 2.5
    catalyst_ok = len(catalysts) > 0
    decision = "GO" if (in_window and rvol_ok and catalyst_ok) else "NO GO"
    bias = "LONG" if "Hot" in str(scenarios) or "Bull" in str(scenarios) else ("SHORT" if "Down" in str(scenarios) else "FLAT")
    domain, vehicle, inst_type = classify_and_route(ticker, bias)
    atr_approx = abs(live_price - vwap) * 1.5 if live_price and vwap else 1.0
    entry = live_price or 0
    return {
        "input_ticker": ticker,
        "asset_domain": domain,
        "primary_volatility_anchor": "VIX" if ticker in ["SPY", "QQQ"] else "ATR",
        "routed_execution_vehicle": vehicle,
        "execution_instrument_type": inst_type,
        "decision": decision,
        "conviction_score_pct": 65 if decision == "GO" else 40,
        "directional_bias": bias,
        "institutional_setup": "VWAP_TREND_CONTINUATION" if live_price and vwap and live_price > vwap else "NONE",
        "exact_entry_price": round(entry, 2),
        "hard_stop_loss": round(entry - atr_approx if bias == "LONG" else entry + atr_approx, 2),
        "take_profit_target_1": round(entry + atr_approx if bias == "LONG" else entry - atr_approx, 2),
        "take_profit_target_2": round(entry + atr_approx*2 if bias == "LONG" else entry - atr_approx*2, 2),
        "calculated_risk_reward": 2.0,
        "volatility_buffer_atr": round(atr_approx, 2),
        "quantitative_rationale": [
            f"RVOL {rvol:.1f}x" if rvol else "RVOL unavailable",
            f"Catalysts: {len(catalysts)}",
            f"Window active: {in_window}",
            f"Peer status: {peer_info.get('relative', 'N/A')}"
        ]
    }
    best = max(scenarios, key=lambda x: x[1])
    avg = np.mean([s[1] for s in scenarios])
    confidence = min(90, max(40, best[1] - avg + 50))
    grade = best[0]
    if best[1] < 40:
        grade = "Chop / Neutral"
    return grade, confidence, best[2]

@st.fragment(run_every="10s" if auto_mode else None)
def live_price_section():
    hist, live_price, rvol = price_bot(ticker)
    vwap = hist["vwap"].iloc[-1] if hist is not None and not hist.empty else None
    return hist, live_price, rvol, vwap

@st.fragment(run_every="30s" if auto_mode else None)
def live_news_section():
    news, catalysts = news_bot(ticker)
    return news, catalysts

@st.fragment(run_every="60s" if auto_mode else None)
def live_peer_gex_section():
    gex = gex_bot(ticker)
    peer_info = peer_bot(ticker)
    return gex, peer_info

if ticker:
    with st.spinner("Bots scanning (efficient differential refresh)..."):
        hist, live_price, rvol, vwap = live_price_section()
        news, catalysts = live_news_section()
        gex, peer_info = live_peer_gex_section()
        news_titles = [n.get("title", "") for n in news] if news else []

        scenarios = scenario_group(live_price, vwap, rvol, gex, news_titles, catalysts, peer_info, ticker)
        grade, conf, reason = master_consensus(scenarios)

    st.subheader(f"{ticker} — Consensus Outlook (PT {now_pt().strftime('%H:%M')})")
    if "Hot" in grade or "Bull" in grade:
        st.success(f"**{grade}** (confidence ~{conf:.0f}%)")
    elif "Down" in grade:
        st.error(f"**{grade}** (confidence ~{conf:.0f}%)")
    else:
        st.info(f"**{grade}** (confidence ~{conf:.0f}%)")
    st.write(f"**Primary reason:** {reason}")
    st.caption("Horizon: next few hours / rest of session. All times Pacific.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Live Price", f"${live_price:.2f}" if live_price else "N/A")
    col2.metric("vs VWAP", f"{((live_price - vwap)/vwap*100):+.2f}%" if live_price and vwap else "N/A")
    col3.metric("RVOL", f"{rvol:.2f}x" if rvol else "N/A")
    col4.metric("GEX Regime", gex.get("regime", "N/A").upper())

    # Scenarios table
    st.write("**Scenario Group (parallel realities):**")
    for name, score, desc in scenarios:
        st.write(f"- **{name}**: score {score} — {desc}")

    # Chart
    if hist is not None and not hist.empty:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"],
                                     low=hist["Low"], close=hist["Close"], name="5m"))
        fig.add_trace(go.Scatter(x=hist.index, y=hist["vwap"], name="VWAP", line=dict(color="orange")))
        if gex.get("callWall"):
            fig.add_hline(y=gex["callWall"], line_dash="dot", line_color="red", annotation_text="Call Wall")
        if gex.get("putWall"):
            fig.add_hline(y=gex["putWall"], line_dash="dot", line_color="green", annotation_text="Put Wall")
        fig.update_layout(title=f"{ticker} 5m (PT)", height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # Peer Bot
    st.write("**Peer / Basket Comparison Bot (sole job):**")
    if peer_info and "error" not in peer_info:
        st.write(f"Sector: {peer_info.get('sector')} | Industry: {peer_info.get('industry')}")
        st.write(f"**{peer_info.get('relative')}** by {peer_info.get('relative_pct', 0):+.2f}% (ticker {peer_info.get('ticker_change', 0):+.2f}% vs peer avg {peer_info.get('peer_avg_change', 0):+.2f}%)")
        if peer_info.get("peer_changes"):
            st.write("Peer moves today:", peer_info["peer_changes"])
    else:
        st.write("Peer data limited.")

    # News + Catalysts
    if catalysts:
        st.write("**Incoming / Breaking Catalysts detected:**")
        for c in catalysts[:3]:
            st.warning(f"- {c}")
    if news:
        st.write("**News Bot (latest):**")
        for n in news[:3]:
            st.write(f"- {n.get('title', 'N/A')}")

    st.markdown("---")
    st.markdown(DISCLAIMER)

st.sidebar.info("Efficient auto-refresh active when checked: Price ~10s, News 30s, Peers/GEX ~60s. Predictions update at the speed of the fastest relevant data. All times Pacific.")
