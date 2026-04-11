"""
Alpha FX Hub — Cyberpunk Trading Command Center
Personal AI-powered trading assistant with neon city aesthetics.
- Cyberpunk Neon City UI
- ARIA AI Assistant (Grok-powered)
- News Dashboard + MT5 Analysis + Academy + Forum
- Price Action engine V2
"""

import os, json, re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import streamlit.components.v1 as st_components

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Import internal modules
from config import (
    PLATFORM_NAME, VERSION, TELEGRAM_BOT_TOKEN, TELEGRAM_PRIVATE_CHANNEL_ID,
    TELEGRAM_PUBLIC_CHANNEL_ID, SUPABASE_URL, SUPABASE_KEY, TWELVE_DATA_API_KEY,
    METAAPI_TOKEN, METAAPI_ACCOUNT, SYMBOLS, ACTIVE_SYMBOLS, TE_API_KEY
)
from telegram.notifications import NotificationManager
from auth.supabase_auth import SupabaseAuth, render_auth_page, _clear_browser_session
from pa_engine import (
    detect_swings, analyze_structure, find_key_levels,
    detect_liquidity_sweep, check_rejection_candle, score_setup as pa_score_setup,
    generate_plan as pa_generate_plan, get_htf_structure, TradePlan as PATradePlan
)

# Import new cyberpunk modules
from cyberpunk_theme import inject_cyberpunk_css, cyberpunk_header, neon_card, neon_metric
from pages_news import render_news_dashboard
from pages_grok_chat import render_grok_chat as render_aria_chat
from pages_mt5_analysis import render_mt5_analysis
from pages_academy import render_academy
from pages_forum import render_forum

# GROK_API_KEY may not be in config, use xAI key pattern instead
try:
    from config import GROK_API_KEY
except ImportError:
    GROK_API_KEY = os.getenv("XAI_API_KEY", "")

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="ALPHA FX HUB // NEON CITY",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject the cyberpunk theme
inject_cyberpunk_css()

# Additional app-specific styles on top of cyberpunk theme
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Space+Mono:wght@400;700&family=Share+Tech+Mono&display=swap');
.signal-box{padding:10px 18px;border-radius:8px;font-family:'Orbitron',monospace;font-size:13px;font-weight:700;letter-spacing:.08em;text-align:center;display:inline-block;min-width:180px;text-shadow:0 0 10px currentColor;}
.signal-buy{background:rgba(57,255,20,.12);border:1px solid rgba(57,255,20,.4);color:#39ff14;box-shadow:0 0 15px rgba(57,255,20,.2);}
.signal-sell{background:rgba(255,45,123,.12);border:1px solid rgba(255,45,123,.4);color:#ff2d7b;box-shadow:0 0 15px rgba(255,45,123,.2);}
.signal-wait{background:rgba(157,78,221,.12);border:1px solid rgba(157,78,221,.4);color:#9d4edd;box-shadow:0 0 15px rgba(157,78,221,.2);}
.panel{background:linear-gradient(135deg,#0a0a1a 0%,#0d0b1e 100%);border:1px solid rgba(0,255,242,0.12);border-radius:8px;padding:12px 14px;margin-bottom:10px;box-shadow:0 0 10px rgba(0,255,242,0.05);}
.mono-title{color:#00fff2;font-size:11px;font-family:'Orbitron',monospace;letter-spacing:.15em;margin-bottom:8px;text-shadow:0 0 8px rgba(0,255,242,0.5);}
.kv{display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid rgba(0,255,242,0.06);font-size:13px;}
.kv:last-child{border-bottom:none;}
.muted{color:#8b9ab0;}.good{color:#39ff14;}.bad{color:#ff2d7b;}.warn{color:#9d4edd;}.info{color:#00fff2;}
.ai-bubble{background:rgba(157,78,221,.08);border:1px solid rgba(157,78,221,.25);border-left:3px solid #9d4edd;border-radius:8px;padding:12px 14px;margin:8px 0;font-size:12px;color:#c7d2fe;line-height:1.75;}
.ai-header{font-family:'Orbitron',monospace;font-size:10px;color:#9d4edd;letter-spacing:.12em;margin-bottom:6px;text-shadow:0 0 6px rgba(157,78,221,0.5);}
.conf-bar{height:6px;border-radius:3px;margin:4px 0;}
/* Anime assistant floating avatar */
.aria-avatar{position:fixed;bottom:20px;right:20px;z-index:9999;width:80px;height:80px;border-radius:50%;border:2px solid #ff2d7b;box-shadow:0 0 20px rgba(255,45,123,0.4),0 0 40px rgba(255,45,123,0.2);cursor:pointer;transition:all 0.3s ease;background:linear-gradient(135deg,#1a1a3e,#0d0b1e);display:flex;align-items:center;justify-content:center;font-size:36px;}
.aria-avatar:hover{transform:scale(1.1);box-shadow:0 0 30px rgba(255,45,123,0.6),0 0 60px rgba(255,45,123,0.3);}
/* Neon sidebar nav */
.nav-item{padding:10px 16px;margin:4px 8px;border-radius:8px;font-family:'Orbitron',monospace;font-size:11px;letter-spacing:.1em;cursor:pointer;transition:all 0.3s ease;border:1px solid transparent;}
.nav-item:hover{border-color:rgba(0,255,242,0.3);background:rgba(0,255,242,0.05);}
.nav-active{border-color:#00fff2!important;background:rgba(0,255,242,0.1)!important;color:#00fff2!important;box-shadow:0 0 15px rgba(0,255,242,0.15);}
</style>""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================
APP_VERSION = "V12.0"
_ENV_TD = TWELVE_DATA_API_KEY or os.getenv("TWELVE_DATA_API_KEY", "").strip()
_ENV_XAI = GROK_API_KEY or os.getenv("XAI_API_KEY", "").strip()

INTERNAL_SYMBOLS = list(ACTIVE_SYMBOLS or ["EURUSD","GBPUSD","USDJPY","XAUUSD","EURCHF",
                    "AUDUSD","USDCAD","NZDUSD","USDCHF","BTCUSD"])
API_SYMBOL_MAP = {
    "EURUSD":"EUR/USD","GBPUSD":"GBP/USD","USDJPY":"USD/JPY",
    "XAUUSD":"XAU/USD","EURCHF":"EUR/CHF","AUDUSD":"AUD/USD",
    "USDCAD":"USD/CAD","NZDUSD":"NZD/USD","USDCHF":"USD/CHF","BTCUSD":"BTC/USD"
}
SYMBOL_NAMES = {
    "EURUSD":"EUR/USD Euro vs US Dollar","GBPUSD":"GBP/USD British Pound vs USD",
    "USDJPY":"USD/JPY US Dollar vs Japanese Yen","XAUUSD":"Gold (XAU/USD)",
    "EURCHF":"EUR/CHF","AUDUSD":"AUD/USD Australian Dollar","USDCAD":"USD/CAD",
    "NZDUSD":"NZD/USD New Zealand Dollar","USDCHF":"USD/CHF","BTCUSD":"Bitcoin vs USD"
}
INTERVAL_MAP = {"1 Min":"1min","5 Min":"5min","15 Min":"15min",
                "30 Min":"30min","1 Hour":"1h","4 Hours":"4h"}
PIP_SIZE_MAP = {"USDJPY":0.01,"XAUUSD":0.1,"BTCUSD":1.0}
PIP_VALUE_MAP = {"USDJPY":9.1,"XAUUSD":10.0,"BTCUSD":1.0}
FOREX_SYMBOLS = {s for s in INTERNAL_SYMBOLS if s!="BTCUSD"}
XAU_SESSIONS_UTC = [(7,16),(12,21)]

SESSIONS = {
    "London":  (7,16),
    "NewYork": (12,21),
    "Overlap": (12,16),
    "Asian":   (22, 7),
}
PAIR_SESSIONS = {
    "EURUSD":["London","Overlap","NewYork"],
    "GBPUSD":["London","Overlap","NewYork"],
    "USDJPY":["Asian","London","Overlap"],
    "EURCHF":["London","Overlap"],
    "AUDUSD":["Asian","London"],
    "USDCAD":["NewYork","Overlap"],
    "NZDUSD":["Asian","London"],
    "USDCHF":["London","Overlap","NewYork"],
    "BTCUSD":["London","NewYork","Overlap"],
    "XAUUSD":["London","Overlap","NewYork"],
}

MT5_SYMBOL_MAP: Dict[str,str] = {
    "EURUSD":"EURUSD","GBPUSD":"GBPUSD","USDJPY":"USDJPY",
    "XAUUSD":"XAUUSD","AUDUSD":"AUDUSD","USDCAD":"USDCAD",
    "NZDUSD":"NZDUSD","USDCHF":"USDCHF","BTCUSD":"BTCUSD",
}

# ============================================================
# HELPERS
# ============================================================
def norm(s):
    return str(s).upper().replace("/","").strip()

def to_api_symbol(s):
    return API_SYMBOL_MAP.get(norm(s), norm(s))

def pip_size(s):
    return PIP_SIZE_MAP.get(norm(s), 0.0001)

def pip_value(s):
    return PIP_VALUE_MAP.get(norm(s), 10.0)

def get_td_key():
    return st.session_state.get("td_key","") or _ENV_TD

def get_xai_key():
    return st.session_state.get("xai_key","") or _ENV_XAI

def get_grok_model():
    return st.session_state.get("grok_model","grok-4-1-fast-non-reasoning")

def get_ma_token():
    return st.session_state.get("ma_token","") or METAAPI_TOKEN

def get_ma_account():
    return st.session_state.get("ma_account","") or METAAPI_ACCOUNT

def mt5_symbol(s:str) -> str:
    suffix = st.session_state.get("ma_sym_suffix","")
    base = MT5_SYMBOL_MAP.get(norm(s), norm(s))
    return base + suffix

# ============================================================
# TRADING ECONOMICS — ECONOMIC CALENDAR
# ============================================================
_SYMBOL_CURRENCIES = {
    "XAUUSD": ["USD","EUR","GBP","JPY","CNY"],
    "EURUSD": ["USD","EUR"], "GBPUSD": ["USD","GBP"],
    "USDJPY": ["USD","JPY"], "AUDUSD": ["USD","AUD"],
    "USDCAD": ["USD","CAD"], "USDCHF": ["USD","CHF"],
    "NZDUSD": ["USD","NZD"], "BTCUSD": ["USD"], "ETHUSD": ["USD"],
}
_HIGH_IMPACT = [
    "Interest Rate Decision","Fed Interest Rate Decision",
    "Non Farm Payrolls","CPI","Core CPI","PPI","Core PPI",
    "GDP Growth Rate","Unemployment Rate","Initial Jobless Claims",
    "Retail Sales","ISM Manufacturing PMI","ISM Services PMI",
    "FOMC Minutes","Fed Chair Powell Speech",
    "ECB Interest Rate Decision","BOE Interest Rate Decision",
    "BOJ Interest Rate Decision","Trade Balance",
    "Consumer Confidence","Durable Goods Orders",
    "PCE Price Index","Core PCE Price Index",
]

@st.cache_data(ttl=1800)
def fetch_te_calendar():
    """Fetch today's economic calendar from Trading Economics (cached 30 min)."""
    te_key = TE_API_KEY
    if not te_key:
        return []
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        url = f"https://api.tradingeconomics.com/calendar?c={te_key}&d1={today}&d2={today}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
        return []
    except Exception:
        return []

def te_news_check(symbol:str, events:list):
    """Check for upcoming high-impact news affecting this symbol.
    Returns (penalty, event_str, upcoming_events_list)."""
    if not events:
        return 0, None, []
    now = datetime.utcnow()
    affected = _SYMBOL_CURRENCIES.get(norm(symbol), ["USD"])
    upcoming = []
    worst_penalty = 0
    worst_event = None

    for ev in events:
        try:
            ev_cur = ev.get("Currency", ev.get("Country",""))
            ev_name = ev.get("Event","")
            ev_imp = ev.get("Importance", 0)
            ev_date = ev.get("Date","")
            if ev_cur not in affected:
                continue
            if ev_date:
                ev_time = pd.to_datetime(ev_date, utc=True, errors="coerce")
                if pd.isna(ev_time):
                    continue
                ev_time = ev_time.to_pydatetime().replace(tzinfo=None)
            else:
                continue
            mins_until = (ev_time - now).total_seconds() / 60
            # Show upcoming events within 4 hours
            if -30 <= mins_until <= 240:
                time_str = ev_time.strftime("%H:%M UTC")
                imp_icon = "🔴" if ev_imp >= 3 else "🟡" if ev_imp >= 2 else "⚪"
                upcoming.append(f"{imp_icon} {time_str} — {ev_name} ({ev_cur})")
            # Danger window: 30 min before to 15 min after
            if -15 <= mins_until <= 30:
                is_high = any(h.lower() in ev_name.lower() for h in _HIGH_IMPACT)
                if is_high or ev_imp >= 3:
                    if -15 < worst_penalty:
                        worst_penalty = -15
                        worst_event = f"⚠️ {ev_name} ({ev_cur}) in {int(mins_until)}min"
                elif ev_imp >= 2:
                    if -10 < worst_penalty or worst_penalty == 0:
                        worst_penalty = -10
                        worst_event = f"⚡ {ev_name} ({ev_cur}) in {int(mins_until)}min"
        except Exception:
            continue
    return worst_penalty, worst_event, upcoming

# ============================================================
# METAAPI REST
# ============================================================
_MA_PROVISION_URL = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"

@st.cache_data(ttl=120)
def _ma_get_region(token:str, account_id:str) -> str:
    try:
        r = requests.get(f"{_MA_PROVISION_URL}/users/current/accounts/{account_id}",
                         headers={"auth-token":token}, timeout=8)
        if r.status_code == 200:
            return r.json().get("region","new-york")
    except Exception:
        pass
    return "new-york"

def _ma_client_url(token:str, account_id:str) -> str:
    region = _ma_get_region(token, account_id)
    return f"https://mt-client-api-v1.{region}.agiliumtrade.ai"

@st.cache_data(ttl=3)
def fetch_mt5_price(symbol:str, token:str, account_id:str) -> Optional[Dict]:
    if not token or not account_id:
        return None
    base = _ma_client_url(token, account_id)
    sym = mt5_symbol(symbol)
    def _try(s):
        try:
            r = requests.get(f"{base}/users/current/accounts/{account_id}/symbols/{s}/current-price",
                             headers={"auth-token":token}, timeout=5)
            if r.status_code == 200:
                d = r.json()
                bid = float(d.get("bid",0))
                ask = float(d.get("ask",0))
                mid = (bid+ask)/2
                ps = pip_size(symbol)
                spread = round(abs(ask-bid)/ps, 1) if ps else 0
                return {"bid":bid,"ask":ask,"mid":mid,"spread_pips":spread,
                        "symbol":symbol,"mt5_sym":s,"ts":d.get("time","")}
        except Exception:
            pass
        return None
    result = _try(sym)
    if result is None and sym != norm(symbol):
        result = _try(norm(symbol))
    return result

@st.cache_data(ttl=5)
def fetch_mt5_positions(token:str, account_id:str) -> List[Dict]:
    if not token or not account_id:
        return []
    base = _ma_client_url(token, account_id)
    try:
        r = requests.get(f"{base}/users/current/accounts/{account_id}/positions",
                         headers={"auth-token":token}, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=30)
def fetch_mt5_account_info(token:str, account_id:str) -> Optional[Dict]:
    if not token or not account_id:
        return None
    base = _ma_client_url(token, account_id)
    try:
        r = requests.get(f"{base}/users/current/accounts/{account_id}/account-information",
                         headers={"auth-token":token}, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def test_mt5_connection(token:str, account_id:str) -> Tuple[bool,str]:
    lines = []
    headers = {"auth-token": token}
    prov_url = f"{_MA_PROVISION_URL}/users/current/accounts/{account_id}"
    lines.append(f"Provisioning API...")
    region = "new-york"
    try:
        rp = requests.get(prov_url, headers=headers, timeout=8)
        lines.append(f"HTTP {rp.status_code}")
        if rp.status_code == 200:
            acc = rp.json()
            region = acc.get("region", "new-york")
            state = acc.get("state","?")
            lines.append(f"region={region}  state={state}")
        elif rp.status_code == 401:
            return False, "401 Unauthorised — token is wrong or expired"
        elif rp.status_code == 404:
            return False, "404 Account not found"
    except Exception as e:
        lines.append(f"ERROR: {e}")

    client_base = f"https://mt-client-api-v1.{region}.agiliumtrade.ai"
    info_url = f"{client_base}/users/current/accounts/{account_id}/account-information"
    lines.append(f"Client API ({region})...")
    try:
        rc = requests.get(info_url, headers=headers, timeout=8)
        lines.append(f"HTTP {rc.status_code}")
        if rc.status_code == 200:
            d = rc.json()
            bal = d.get("balance","?")
            cur = d.get("currency","USD")
            name = d.get("name","?")
            return True, f"Connected — {name}  Balance: {bal} {cur}"
    except Exception as e:
        lines.append(f"ERROR: {e}")

    return False, "\n".join(lines)

def deploy_mt5_account(token:str, account_id:str) -> Tuple[bool,str]:
    url = f"{_MA_PROVISION_URL}/users/current/accounts/{account_id}/deploy"
    try:
        r = requests.post(url, headers={"auth-token":token}, timeout=10)
        if r.status_code in (200,204):
            return True,"Deploy sent. Wait 30s then Test again."
        else:
            return False,f"Deploy failed HTTP {r.status_code}"
    except Exception as e:
        return False,f"Deploy error: {e}"

# ============================================================
# FORMATTING
# ============================================================
def fmt_price(v, sym=""):
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return "—"
    s = norm(sym)
    return f"{float(v):.3f}" if s in ("USDJPY","XAUUSD","BTCUSD") else f"{float(v):.5f}"

def fmt_num(v, d=2):
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return "—"
    return f"{float(v):.{d}f}"

def fmt_rr(v):
    if v is None or (isinstance(v,float) and pd.isna(v)):
        return "—"
    return f"1:{float(v):.2f}"

def score_to_grade(s):
    if s >= 90:
        return "A+"
    if s >= 80:
        return "A"
    if s >= 70:
        return "B"
    if s >= 60:
        return "C"
    return "D"

def grade_color(g):
    return {"A+":"#00d4aa","A":"#10b981","B":"#84cc16","C":"#f59e0b","D":"#ef4444"}.get(g,"#8b9ab0")

def market_is_open(symbol):
    now = pd.Timestamp.utcnow()
    wd = now.weekday()
    s = norm(symbol)
    if s in FOREX_SYMBOLS:
        if wd == 5:
            return False,"CLOSED"
        if wd == 6 and now.hour < 22:
            return False,"CLOSED"
    return True,"LIVE"

def is_xau_session_ok(ts):
    h = int(ts.hour)
    return any(a <= h <= b for a,b in XAU_SESSIONS_UTC)

def session_score(symbol:str, ts:pd.Timestamp) -> Tuple[int,str]:
    h = ts.hour
    s = norm(symbol)
    preferred = PAIR_SESSIONS.get(s, ["London","NewYork"])
    if 12 <= h < 16 and "Overlap" in preferred:
        return 15,"London/NY Overlap"
    if SESSIONS["London"][0] <= h < SESSIONS["London"][1] and "London" in preferred:
        return 10,"London Session"
    if SESSIONS["NewYork"][0] <= h < SESSIONS["NewYork"][1] and "NewYork" in preferred:
        return 10,"NY Session"
    if "Asian" in preferred and (h >= 22 or h < 7):
        return 5,"Asian Session (weak)"
    if h >= 22 or h < 7:
        return 0,"Asian Session (avoid)"
    return 5,"Off-peak"

# ============================================================
# GROK CLIENT
# ============================================================
def _grok(messages:List[Dict], max_tokens:int=400, temperature:float=0.25,
          api_key:str="", model:str="") -> Optional[str]:
    key = api_key or get_xai_key()
    if not key:
        return None
    mdl = model or get_grok_model()
    try:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {
            "model": mdl,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": float(max(0.0, min(1.0, temperature))),
        }
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers=headers, json=payload, timeout=25)
        if r.status_code != 200:
            try:
                body = r.json()
                msg = body.get("error", {}).get("message") or body.get("message") or r.text[:120]
            except Exception:
                msg = r.text[:120]
            return f"[Grok {r.status_code}: {msg}]"
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"[Grok error: {exc}]"

def test_grok_connection(api_key:str="") -> Tuple[bool,str]:
    mdl = get_grok_model()
    result = _grok([{"role":"user","content":"Reply with OK"}],
                   max_tokens=5, temperature=0, api_key=api_key)
    if result is None:
        return False, "No API key"
    if result.startswith("[Grok"):
        return False, result
    return True, f"Connected (model: {mdl})"

@st.cache_data(ttl=90)
def get_news_sentiment(symbol:str, xai_key:str) -> Dict[str,Any]:
    if not xai_key:
        return {"risk":"LOW","adj":0,"bias":"neutral","summary":"No key","events":[],"ok":False}
    sym_name = SYMBOL_NAMES.get(norm(symbol), symbol)
    system_msg = ("You are a forex analyst. Be concise. UTC: " + pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M"))
    user_msg = f"""Analyze CURRENT market news sentiment for {sym_name}.
Return ONLY valid JSON:
{{"risk":"HIGH|MEDIUM|LOW","adj":<int -15 to 15>,"bias":"bull|bear|neutral","summary":"<20 words>","events":["<e1>","<e2>"]}}"""
    raw = _grok([{"role":"system","content":system_msg},{"role":"user","content":user_msg}],
                max_tokens=200, temperature=0.1, api_key=xai_key)
    if not raw or raw.startswith("[Grok error"):
        return {"risk":"LOW","adj":0,"bias":"neutral","summary":raw or "Unavailable","events":[],"ok":False}
    try:
        obj = json.loads(re.sub(r"```json|```","",raw).strip())
        return {"risk":obj.get("risk","LOW"),"adj":int(obj.get("adj",0)),"bias":obj.get("bias","neutral"),
                "summary":obj.get("summary",""),"events":obj.get("events",[]),"ok":True}
    except:
        return {"risk":"LOW","adj":0,"bias":"neutral","summary":raw[:100],"events":[],"ok":False}

def get_ai_trade_advice(plan, df:pd.DataFrame, live_health:Optional[Dict],
                        news:Optional[Dict], user_question:str="") -> str:
    key = get_xai_key()
    if not key:
        return "No xAI key."
    row = df.iloc[-1]
    recent = df.tail(10)[["open","high","low","close"]].round(5).to_string(index=False)
    h_info = (f"R={live_health['r_now']:+.2f}, {live_health['status']}"
              if live_health else "not in trade")
    n_info = (f"Risk={news['risk']}, {news['summary']}" if (news and news.get("ok")) else "no news")
    q_line = f"\nQuestion: {user_question}" if user_question.strip() else ""
    msg = f"""Trade: {plan.symbol} {plan.direction}
Entry={fmt_price(plan.entry,plan.symbol)} SL={fmt_price(plan.sl,plan.symbol)}
TP1={fmt_price(plan.tp1,plan.symbol)} TP2={fmt_price(plan.tp2,plan.symbol)}
Score={plan.setup_score} ({plan.final_grade})
Price={fmt_price(float(row['close']),plan.symbol)} RSI={fmt_num(row.get('rsi14'),1)}
Health: {h_info}
News: {n_info}
Last 10 bars:
{recent}{q_line}
-> HOLD/EXIT/MOVE SL?"""
    return _grok([{"role":"system","content":"You are a forex risk manager. Be concise."},
                  {"role":"user","content":msg}],
                 max_tokens=300, temperature=0.3, api_key=key) or "Empty."

# ============================================================
# DATA & INDICATORS
# ============================================================
def td_get(endpoint:str, params:Dict) -> Dict:
    key = get_td_key()
    if not key:
        raise ValueError("No Twelve Data key")
    url = f"https://api.twelvedata.com/{endpoint}"
    p = dict(params)
    p["apikey"] = key
    r = requests.get(url, params=p, timeout=20)
    r.raise_for_status()
    data = r.json()
    if isinstance(data,dict) and data.get("status")=="error":
        raise ValueError(data.get("message","Error"))
    return data

def parse_td(values:List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(values)
    if df.empty:
        return df
    col = "datetime" if "datetime" in df.columns else "date"
    df["time"] = pd.to_datetime(df[col], utc=True, errors="coerce")
    for c in ["open","high","low","close","volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("time").dropna(subset=["time","open","high","low","close"]).reset_index(drop=True)

@st.cache_data(ttl=60)
def fetch_bars(symbol:str, interval:str, bars:int, td_key:str) -> pd.DataFrame:
    data = td_get("time_series", {"symbol":to_api_symbol(symbol),"interval":interval,
                                  "outputsize":int(bars),"timezone":"UTC","order":"ASC"})
    v = data.get("values",[])
    if not v:
        raise ValueError("No bars")
    return parse_td(v)

def add_indicators(df:pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ema20"] = x["close"].ewm(span=20,adjust=False).mean()
    x["ema50"] = x["close"].ewm(span=50,adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200,adjust=False).mean()
    tr = pd.concat([x["high"]-x["low"],
                    (x["high"]-x["close"].shift()).abs(),
                    (x["low"]-x["close"].shift()).abs()],axis=1).max(axis=1)
    x["atr14"] = tr.rolling(14).mean()
    delta = x["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    x["rsi14"] = 100-(100/(1+gain.rolling(14).mean()/loss.rolling(14).mean().replace(0,np.nan)))
    ema12 = x["close"].ewm(span=12,adjust=False).mean()
    ema26 = x["close"].ewm(span=26,adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["macd_sig"] = x["macd"].ewm(span=9,adjust=False).mean()
    x["macd_hist"] = x["macd"] - x["macd_sig"]
    x["bb_mid"] = x["close"].rolling(20).mean()
    bb_std = x["close"].rolling(20).std()
    x["bb_upper"] = x["bb_mid"] + 2*bb_std
    x["bb_lower"] = x["bb_mid"] - 2*bb_std
    x["bb_width"] = (x["bb_upper"]-x["bb_lower"])/x["bb_mid"]
    x["hh20"] = x["high"].rolling(20).max()
    x["ll20"] = x["low"].rolling(20).min()
    x["slope20"] = x["ema20"].diff(5)
    body = (x["close"]-x["open"]).abs()
    full_range = x["high"] - x["low"]
    upper = x["high"] - x[["close","open"]].max(axis=1)
    lower = x[["close","open"]].min(axis=1) - x["low"]
    # Classic patterns (strict)
    x["pin_bull"] = (lower > 2*body) & (upper < 0.3*body)
    x["pin_bear"] = (upper > 2*body) & (lower < 0.3*body)
    x["engulf_bull"] = (x["close"]>x["open"]) & (x["close"].shift()<=x["open"].shift()) & \
                       (x["close"]>x["open"].shift()) & (x["open"]<x["close"].shift())
    x["engulf_bear"] = (x["close"]<x["open"]) & (x["close"].shift()>=x["open"].shift()) & \
                       (x["close"]<x["open"].shift()) & (x["open"]>x["close"].shift())
    # Additional patterns (relaxed)
    x["hammer"] = (lower > 1.5*body) & (upper < 0.5*body) & (body > 0)
    x["shooting_star"] = (upper > 1.5*body) & (lower < 0.5*body) & (body > 0)
    x["bull_candle"] = (x["close"]>x["open"]) & (body > full_range*0.6)
    x["bear_candle"] = (x["close"]<x["open"]) & (body > full_range*0.6)
    x["three_bull"] = (x["close"]>x["open"]) & (x["close"].shift(1)>x["open"].shift(1)) & \
                      (x["close"].shift(2)>x["open"].shift(2))
    x["three_bear"] = (x["close"]<x["open"]) & (x["close"].shift(1)<x["open"].shift(1)) & \
                      (x["close"].shift(2)<x["open"].shift(2))
    return x

def trend_bias(df:pd.DataFrame) -> str:
    r = df.iloc[-1]
    if r["ema20"] > r["ema50"] > r["ema200"] and r["macd_hist"] > 0:
        return "bull"
    if r["ema20"] < r["ema50"] < r["ema200"] and r["macd_hist"] < 0:
        return "bear"
    if r["ema20"] > r["ema50"] > r["ema200"]:
        return "bull_weak"
    if r["ema20"] < r["ema50"] < r["ema200"]:
        return "bear_weak"
    return "neutral"

def detect_sweep(df:pd.DataFrame, symbol:str) -> Dict:
    if len(df) < 8:
        return {"detected":False,"severity":"LOW","desc":"Insufficient"}
    row = df.iloc[-1]
    prev = df.iloc[-6:-1]
    atr = row.get("atr14")
    if pd.isna(atr) or atr <= 0:
        return {"detected":False,"severity":"LOW","desc":"ATR unavailable"}
    rh = prev["high"].max()
    rl = prev["low"].min()
    if row["high"] > rh and row["close"] < rh:
        sev = "HIGH" if (row["high"]-rh)/atr > 1.2 else "MEDIUM"
        return {"detected":True,"severity":sev,"desc":f"Upper sweep"}
    if row["low"] < rl and row["close"] > rl:
        sev = "HIGH" if (rl-row["low"])/atr > 1.2 else "MEDIUM"
        return {"detected":True,"severity":sev,"desc":f"Lower sweep"}
    return {"detected":False,"severity":"LOW","desc":"No sweep"}

# ============================================================
# PLAN DATACLASS
# ============================================================
@dataclass
class Plan:
    symbol:str
    regime:str = "insufficient"
    strategy:str = "No Strategy"
    direction:str = "Wait"
    execution_status:str = "Wait"
    setup_score:int = 20
    setup_grade:str = "D"
    entry:Optional[float] = None
    sl:Optional[float] = None
    tp1:Optional[float] = None
    tp2:Optional[float] = None
    tp3:Optional[float] = None
    rr:Optional[float] = None
    reason:str = "No valid setup"
    entry_reasons:List[str] = field(default_factory=list)
    exit_conditions:List[str] = field(default_factory=list)
    score_breakdown:Dict[str,int] = field(default_factory=dict)
    confluence_count:int = 0
    confluence_needed:int = 3
    session_label:str = ""
    session_score:int = 0
    mtf_aligned:bool = False
    base_lot:float = 0.0
    suggested_lot:float = 0.0
    news_adj:int = 0
    news_risk:str = "LOW"
    news_bias:str = "neutral"
    news_summary:str = ""
    news_events:List[str] = field(default_factory=list)
    news_ok:bool = False
    final_score:int = 20
    final_grade:str = "D"
    # Market sentiment
    market_sentiment:str = "UNKNOWN"
    market_bearish:int = 0
    market_bullish:int = 0
    sentiment_adj:int = 0
    # TE calendar
    te_penalty:int = 0
    te_warning:str = ""
    te_upcoming:List[str] = field(default_factory=list)

    def to_dict(self):
        return self.__dict__.copy()

# ============================================================
# SCORING ENGINE (7-component, max 100)
# ============================================================
def _score_plan(row:pd.Series, prev_row:pd.Series, df:pd.DataFrame,
                direction:str, rr:float, symbol:str) -> Tuple[int, Dict[str,int], int, int]:
    """Returns (total_score, breakdown, confluence, session_pts).
    Recalibrated 8-component scoring: EMA(20)+Pullback(15)+MACD(15)+RSI(10)+Candle(10)+R:R(15)+Session(10)+Momentum(5)=100
    """
    bd: Dict[str,int] = {}

    # 1. EMA Stack (max 20) — full stack, partial, or price>ema20
    if direction == "Buy":
        if row["ema20"]>row["ema50"]>row["ema200"]:
            bd["EMA Stack"] = 20
        elif row["ema20"]>row["ema50"]:
            bd["EMA Stack"] = 14
        elif row["close"]>row["ema20"]:
            bd["EMA Stack"] = 8
        else:
            bd["EMA Stack"] = 0
    else:
        if row["ema20"]<row["ema50"]<row["ema200"]:
            bd["EMA Stack"] = 20
        elif row["ema20"]<row["ema50"]:
            bd["EMA Stack"] = 14
        elif row["close"]<row["ema20"]:
            bd["EMA Stack"] = 8
        else:
            bd["EMA Stack"] = 0

    # 2. Pullback quality (max 15) — relaxed thresholds
    dist = abs(row["close"]-row["ema20"])/max(row["atr14"],1e-9)
    bd["Pullback"] = 15 if dist<=0.5 else 12 if dist<=0.8 else 8 if dist<=1.2 else 4 if dist<=2.0 else 0

    # 3. MACD confirmation (max 15) — more partial credit
    if direction == "Buy":
        if row["macd_hist"]>0 and row["macd_hist"]>prev_row["macd_hist"]:
            bd["MACD"] = 15
        elif row["macd_hist"]>0:
            bd["MACD"] = 10
        elif row["macd"]>row["macd_sig"]:
            bd["MACD"] = 5
        else:
            bd["MACD"] = 0
    else:
        if row["macd_hist"]<0 and row["macd_hist"]<prev_row["macd_hist"]:
            bd["MACD"] = 15
        elif row["macd_hist"]<0:
            bd["MACD"] = 10
        elif row["macd"]<row["macd_sig"]:
            bd["MACD"] = 5
        else:
            bd["MACD"] = 0

    # 4. RSI confirmation (max 10) — directional
    rsi = row["rsi14"]
    if direction == "Buy":
        bd["RSI"] = 10 if 40<=rsi<=65 else 7 if 30<=rsi<=75 else 3 if rsi<30 else 0
    else:
        bd["RSI"] = 10 if 35<=rsi<=60 else 7 if 25<=rsi<=70 else 3 if rsi>70 else 0

    # 5. Candle pattern (max 10) — many patterns recognized
    candle = 0
    if direction == "Buy":
        if row.get("pin_bull",False) or row.get("engulf_bull",False):
            candle = 10
        elif row.get("hammer",False) or row.get("bull_candle",False) or row.get("three_bull",False):
            candle = 7
        elif row["close"]>row["open"]:
            candle = 3
    else:
        if row.get("pin_bear",False) or row.get("engulf_bear",False):
            candle = 10
        elif row.get("shooting_star",False) or row.get("bear_candle",False) or row.get("three_bear",False):
            candle = 7
        elif row["close"]<row["open"]:
            candle = 3
    bd["Candle"] = candle

    # 6. R:R (max 15) — more partial credit
    bd["R:R"] = 15 if rr>=2.5 else 12 if rr>=2.0 else 10 if rr>=1.5 else 7 if rr>=1.2 else 4 if rr>=1.0 else 0

    # 7. Session timing (max 10)
    sess_pts, _ = session_score(symbol, row.get("time", pd.Timestamp.utcnow()))
    bd["Session"] = sess_pts

    # 8. Momentum bonus (max 5)
    slope = row.get("slope20",0)
    if slope and not pd.isna(slope):
        slope_norm = abs(slope)/max(row["atr14"],1e-9)
        if direction=="Buy" and slope>0:
            bd["Momentum"] = 5 if slope_norm>0.3 else 3 if slope_norm>0.1 else 0
        elif direction=="Sell" and slope<0:
            bd["Momentum"] = 5 if slope_norm>0.3 else 3 if slope_norm>0.1 else 0
        else:
            bd["Momentum"] = 0
    else:
        bd["Momentum"] = 0

    total = sum(bd.values())
    confluence = sum(1 for k,v in bd.items() if k not in ("Session","Momentum") and v>0)
    return min(total,100), bd, confluence, sess_pts

# ============================================================
# REGIME
# ============================================================
def get_regime(df:pd.DataFrame) -> str:
    if len(df) < 220:
        return "insufficient"
    r = df.iloc[-1]
    if pd.isna(r["atr14"]) or r["atr14"] <= 0:
        return "insufficient"
    # Full EMA alignment = strong trend
    if r["ema20"]>r["ema50"]>r["ema200"]:
        return "trend_up"
    if r["ema20"]<r["ema50"]<r["ema200"]:
        return "trend_down"
    # Partial alignment (20>50 with positive slope) = weak trend
    if r["ema20"]>r["ema50"] and r["slope20"]>0:
        return "trend_up"
    if r["ema20"]<r["ema50"] and r["slope20"]<0:
        return "trend_down"
    if r["bb_width"]<0.005:
        return "squeeze"
    if 40<=r["rsi14"]<=60:
        return "range"
    return "mean_revert"

def _empty(symbol, regime, reason="No valid setup"):
    return Plan(symbol=symbol, regime=regime, reason=reason, entry_reasons=[reason])

# ============================================================
# PLAN BUILDERS
# ============================================================
def _get_htf_bias(symbol:str, td_key:str) -> str:
    try:
        df1h = add_indicators(fetch_bars(symbol,"1h",260,td_key))
        return trend_bias(df1h)
    except:
        return "neutral"

def _trend_plan(df:pd.DataFrame, symbol:str, regime:str, htf_bias:str) -> Plan:
    row = df.iloc[-1]
    prev = df.iloc[-2]
    atr = row["atr14"]
    close = row["close"]
    ema20 = row["ema20"]
    p = _empty(symbol, regime)

    if pd.isna(atr) or atr <= 0:
        return p

    direction = "Buy" if regime=="trend_up" else "Sell"
    mtf_ok = (htf_bias in ("bull","bull_weak") and direction=="Buy") or \
             (htf_bias in ("bear","bear_weak") and direction=="Sell") or \
             htf_bias=="neutral"
    if not mtf_ok:
        p.reason = f"1H bias opposes {direction}"
        p.entry_reasons = [p.reason]
        return p

    dist = abs(close-ema20)/atr
    if dist > 2.5:
        p.reason = f"Too extended"
        return p

    if direction=="Buy":
        entry = float(close)
        sl = float(min(df.tail(6)["low"].min(), ema20-0.5*atr))
        risk = entry-sl
        tp1 = float(entry+risk)
        tp2 = float(entry+2.0*risk)
        tp3 = float(entry+3.0*risk)
    else:
        entry = float(close)
        sl = float(max(df.tail(6)["high"].max(), ema20+0.5*atr))
        risk = sl-entry
        tp1 = float(entry-risk)
        tp2 = float(entry-2.0*risk)
        tp3 = float(entry-3.0*risk)

    rr = abs(tp2-entry)/max(abs(entry-sl),1e-9)
    score, breakdown, confluence, sess_pts = _score_plan(row,prev,df,direction,rr,symbol)
    sess_pts2, sess_name = session_score(symbol, row.get("time",pd.Timestamp.utcnow()))
    ready = (score>=80 and rr>=1.0 and confluence>=2)

    p2 = Plan(
        symbol=symbol, regime=regime, strategy="Trend Continuation", direction=direction,
        execution_status="Ready to Enter" if ready else "Wait",
        setup_score=score, setup_grade=score_to_grade(score),
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, tp3=tp3, rr=float(rr),
        score_breakdown=breakdown, confluence_count=confluence,
        session_label=sess_name, session_score=sess_pts2, mtf_aligned=mtf_ok,
        reason=f"{regime} continuation"
    )
    p2.entry_reasons = [
        f"EMA: {breakdown['EMA Stack']}/20",
        f"MACD: {breakdown['MACD']}/15",
        f"RSI: {breakdown['RSI']}/10",
        f"Pullback: {breakdown['Pullback']}/15",
        f"R:R: {breakdown['R:R']}/20",
        f"Session: {sess_name} ({sess_pts2}/10)",
    ]
    p2.exit_conditions = [
        f"TP1 {fmt_price(tp1,symbol)}: 50%",
        f"TP2 {fmt_price(tp2,symbol)}: 40%",
        f"TP3 {fmt_price(tp3,symbol)}: 10%",
        f"SL {fmt_price(sl,symbol)}: exit",
    ]
    return p2

def _mean_rev_plan(df:pd.DataFrame, symbol:str, regime:str) -> Plan:
    row = df.iloc[-1]
    prev = df.iloc[-2]
    atr = row["atr14"]
    if pd.isna(atr) or atr <= 0:
        return _empty(symbol, regime)

    close = row["close"]
    ema20 = row["ema20"]
    dev = (close-ema20)/atr

    if abs(dev) < 0.8:
        return _empty(symbol, regime, "Deviation too small")

    bb_touch = (close<=row["bb_lower"] and dev<0) or (close>=row["bb_upper"] and dev>0)
    direction = "Sell" if dev>0 else "Buy"
    entry = float(close)

    if direction=="Buy":
        sl = float(close-0.85*atr)
        tp1 = float(ema20)
        tp2 = float(close+1.7*atr)
    else:
        sl = float(close+0.85*atr)
        tp1 = float(ema20)
        tp2 = float(close-1.7*atr)

    rr = abs(tp2-entry)/max(abs(entry-sl),1e-9)
    score, breakdown, confluence, sess_pts = _score_plan(row,prev,df,direction,rr,symbol)
    base = min(20, int(abs(dev)*8))
    if bb_touch:
        base += 10
    score = min(100, score+base)
    sess_pts2, sess_name = session_score(symbol, row.get("time",pd.Timestamp.utcnow()))
    ready = (score>=80 and rr>=1.0 and confluence>=2)

    p = Plan(
        symbol=symbol, regime=regime, strategy="Mean Reversion", direction=direction,
        execution_status="Ready to Enter" if ready else "Wait",
        setup_score=score, setup_grade=score_to_grade(score),
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, rr=float(rr),
        score_breakdown=breakdown, confluence_count=confluence, confluence_needed=2,
        session_label=sess_name, session_score=sess_pts2, mtf_aligned=True,
        reason="Mean reversion"
    )
    p.entry_reasons = [
        f"Deviation {abs(dev):.2f} ATR",
        f"BB touch: {'Yes' if bb_touch else 'No'}",
        f"RSI: {breakdown['RSI']}/10",
    ]
    p.exit_conditions = [
        f"TP1 {fmt_price(tp1,symbol)}: target",
        f"TP2 {fmt_price(tp2,symbol)}: extended",
        f"SL {fmt_price(sl,symbol)}: exit",
    ]
    return p

def _squeeze_plan(df:pd.DataFrame, symbol:str) -> Plan:
    row = df.iloc[-1]
    prev = df.iloc[-2]
    atr = row["atr14"]

    if pd.isna(atr) or atr <= 0:
        return _empty(symbol, "squeeze")

    direction = "Buy" if row["close"]>row["bb_upper"] and row["macd_hist"]>0 else \
                "Sell" if row["close"]<row["bb_lower"] and row["macd_hist"]<0 else None
    if direction is None:
        return _empty(symbol, "squeeze", "Squeeze present")

    entry = float(row["close"])
    if direction=="Buy":
        sl = float(row["bb_mid"]-0.5*atr)
        tp1 = float(entry+atr)
        tp2 = float(entry+2*atr)
    else:
        sl = float(row["bb_mid"]+0.5*atr)
        tp1 = float(entry-atr)
        tp2 = float(entry-2*atr)

    rr = abs(tp2-entry)/max(abs(entry-sl),1e-9)
    score, breakdown, confluence, _ = _score_plan(row,prev,df,direction,rr,symbol)
    score = min(100, score+15)
    sess_pts2, sess_name = session_score(symbol, row.get("time",pd.Timestamp.utcnow()))
    ready = (score>=80 and rr>=1.0)

    p = Plan(
        symbol=symbol, regime="squeeze", strategy="BB Squeeze Breakout", direction=direction,
        execution_status="Ready to Enter" if ready else "Wait",
        setup_score=score, setup_grade=score_to_grade(score),
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, rr=float(rr),
        score_breakdown=breakdown, confluence_count=confluence, confluence_needed=2,
        session_label=sess_name, session_score=sess_pts2, mtf_aligned=True,
        reason="BB Squeeze"
    )
    p.entry_reasons = [
        f"Squeeze breakout {direction}",
        f"MACD: {breakdown['MACD']}/15",
    ]
    p.exit_conditions = [
        f"TP1 {fmt_price(tp1,symbol)}: 1 ATR",
        f"TP2 {fmt_price(tp2,symbol)}: 2 ATR",
        f"SL {fmt_price(sl,symbol)}: back in BB",
    ]
    return p

def _xau_plan(df5:pd.DataFrame, df15:pd.DataFrame, df1h:pd.DataFrame, symbol:str) -> Plan:
    row = df5.iloc[-1]
    prev = df5.iloc[-2]
    atr = row["atr14"]
    p = _empty(symbol, "gold_scalp")

    if pd.isna(atr) or atr <= 0:
        return p

    b5 = trend_bias(df5)
    b15 = trend_bias(df15)
    b1h = trend_bias(df1h)

    aligned_bull = all(b in ("bull","bull_weak") for b in [b5,b15,b1h])
    aligned_bear = all(b in ("bear","bear_weak") for b in [b5,b15,b1h])
    # Partial alignment: at least 2 of 3 timeframes agree
    biases = [b5, b15, b1h]
    bull_count = sum(1 for b in biases if b in ("bull","bull_weak"))
    bear_count = sum(1 for b in biases if b in ("bear","bear_weak"))
    partial_bull = bull_count >= 2
    partial_bear = bear_count >= 2

    dist = abs(row["close"]-row["ema20"])/atr
    too_ext = dist > 2.0
    last3 = df5.tail(3)
    vert = (last3["close"]-last3["open"]).abs().sum() > atr*2.5

    rh = df5.iloc[-6:-1]["high"].max()
    rl = df5.iloc[-6:-1]["low"].min()
    bull_sw = row["low"]<rl and row["close"]>rl
    bear_sw = row["high"]>rh and row["close"]<rh

    # Relaxed entry: partial alignment OK, EMA cross OR sweep OR just trending
    long_t = (aligned_bull or partial_bull) and not too_ext and not vert and (
        row["close"]>row["ema20"] or bull_sw)
    short_t = (aligned_bear or partial_bear) and not too_ext and not vert and (
        row["close"]<row["ema20"] or bear_sw)

    if not long_t and not short_t:
        p.entry_reasons = [f"5m={b5} 15m={b15} 1h={b1h}"]
        return p

    tp_pts = 20.0
    if long_t:
        entry = float(row["close"])
        sl = float(min(df5.tail(8)["low"].min(), entry-0.8*atr))
        tp1 = float(entry+tp_pts)
        tp2 = float(entry+35.0)
        risk = entry-sl
        rr = (tp1-entry)/max(risk,1e-9)
        direction = "Buy"
    else:
        entry = float(row["close"])
        sl = float(max(df5.tail(8)["high"].max(), entry+0.8*atr))
        tp1 = float(entry-tp_pts)
        tp2 = float(entry-35.0)
        risk = sl-entry
        rr = (entry-tp1)/max(risk,1e-9)
        direction = "Sell"

    if rr < 0.8:
        p.reason = "TP20pts SL mismatch"
        return p

    score, breakdown, confluence, _ = _score_plan(row,prev,df5,direction,rr,symbol)
    mtf_bonus = 20 if (aligned_bull or aligned_bear) else 0
    sw_bonus = 15 if (bull_sw or bear_sw) else 0
    score = min(100, score+mtf_bonus+sw_bonus)
    sess_pts2, sess_name = session_score(symbol, row.get("time",pd.Timestamp.utcnow()))

    p2 = Plan(
        symbol=symbol, regime="gold_scalp", strategy="XAU 20pt Scalp", direction=direction,
        execution_status="Ready to Enter" if score>=80 else "Wait",
        setup_score=score, setup_grade=score_to_grade(score),
        entry=entry, sl=sl, tp1=tp1, tp2=tp2, rr=float(rr),
        score_breakdown=breakdown, confluence_count=confluence,
        session_label=sess_name, session_score=sess_pts2, mtf_aligned=True,
        reason="XAU MTF aligned"
    )
    p2.entry_reasons = [
        f"MTF: 5m={b5} 15m={b15} 1h={b1h}",
        f"Sweep: {'Yes' if bull_sw or bear_sw else 'No'}",
    ]
    p2.exit_conditions = [
        f"TP1 {fmt_price(tp1,symbol)}: 70%",
        f"TP2 {fmt_price(tp2,symbol)}: runner",
        f"SL {fmt_price(sl,symbol)}: hard exit",
    ]
    return p2

# ============================================================
# MARKET-WIDE SENTIMENT (crash / panic detection)
# ============================================================
_SENTIMENT_SYMBOLS = ["EURUSD","GBPUSD","AUDUSD","USDJPY","USDCHF","USDCAD","XAUUSD"]

@st.cache_data(ttl=120)
def get_market_sentiment(td_key: str) -> dict:
    """Check all major pairs to detect market-wide risk-off / risk-on.

    Returns dict with:
      - bearish_count: how many symbols show strong bearish momentum
      - bullish_count: how many symbols show strong bullish momentum
      - sentiment: "RISK_OFF", "RISK_ON", or "MIXED"
      - penalty_buy: score penalty to apply to Buy signals during risk-off
      - penalty_sell: score penalty to apply to Sell signals during risk-on
      - details: per-symbol momentum info
    """
    details = {}
    bearish = 0
    bullish = 0

    for sym in _SENTIMENT_SYMBOLS:
        try:
            df = fetch_bars(sym, "15min", 60, td_key)
            df = add_indicators(df)
            row = df.iloc[-1]
            # Check multiple bearish/bullish signals
            price = float(row["close"])
            ema20 = float(row["ema20"])
            ema50 = float(row["ema50"])
            rsi = float(row.get("rsi14", 50))
            macd_h = float(row.get("macd_hist", 0))

            # For USD pairs (USDJPY, USDCHF, USDCAD), USD strength = price going UP
            # For non-USD pairs (EURUSD, GBPUSD, AUDUSD), risk-off = price going DOWN
            # For XAUUSD, panic = gold going UP (safe haven)
            is_usd_quote = sym in ("USDJPY", "USDCHF", "USDCAD")

            # Calculate momentum: price vs ema20, ema20 slope, RSI, MACD
            below_ema20 = price < ema20
            below_ema50 = price < ema50
            ema20_falling = float(row["ema20"]) < float(df.iloc[-3]["ema20"]) if len(df) > 3 else False
            rsi_oversold = rsi < 40
            macd_bearish = macd_h < 0

            # Count bearish signals for this symbol
            bear_signals = sum([below_ema20, below_ema50, ema20_falling, rsi_oversold, macd_bearish])
            bull_signals = sum([not below_ema20, not below_ema50, not ema20_falling, rsi > 60, macd_h > 0])

            if is_usd_quote:
                # USD quote pairs: price UP = USD strong = risk-off for non-USD
                if bull_signals >= 3:
                    bearish += 1  # USD strength = risk-off
                    details[sym] = "USD_STRONG"
                elif bear_signals >= 3:
                    bullish += 1
                    details[sym] = "USD_WEAK"
                else:
                    details[sym] = "NEUTRAL"
            elif sym == "XAUUSD":
                # Gold UP = panic/risk-off
                if bull_signals >= 3:
                    bearish += 1  # Gold rallying = fear
                    details[sym] = "GOLD_RALLY"
                elif bear_signals >= 3:
                    bullish += 1
                    details[sym] = "GOLD_SELL"
                else:
                    details[sym] = "NEUTRAL"
            else:
                # Standard pairs: price DOWN = risk-off
                if bear_signals >= 3:
                    bearish += 1
                    details[sym] = "BEARISH"
                elif bull_signals >= 3:
                    bullish += 1
                    details[sym] = "BULLISH"
                else:
                    details[sym] = "NEUTRAL"
        except Exception:
            details[sym] = "ERR"

    total = len(_SENTIMENT_SYMBOLS)
    # Risk-off: 5+ out of 7 symbols showing bearish (or USD strong / gold rally)
    # Risk-on: 5+ out of 7 showing bullish
    if bearish >= 5:
        sentiment = "RISK_OFF"
        penalty_buy = -20   # Heavy penalty on Buy signals
        penalty_sell = 0
    elif bearish >= 4:
        sentiment = "RISK_OFF"
        penalty_buy = -12
        penalty_sell = 0
    elif bullish >= 5:
        sentiment = "RISK_ON"
        penalty_buy = 0
        penalty_sell = -20
    elif bullish >= 4:
        sentiment = "RISK_ON"
        penalty_buy = 0
        penalty_sell = -12
    else:
        sentiment = "MIXED"
        penalty_buy = 0
        penalty_sell = 0

    return {
        "bearish_count": bearish,
        "bullish_count": bullish,
        "total": total,
        "sentiment": sentiment,
        "penalty_buy": penalty_buy,
        "penalty_sell": penalty_sell,
        "details": details,
    }


def select_plan(symbol:str, interval:str, bars:int, td_key:str) -> Tuple[pd.DataFrame,Plan]:
    """V2 Plan selection — Price Action engine with structural analysis."""
    s = norm(symbol)

    # Fetch entry timeframe data
    df = add_indicators(fetch_bars(s, interval, max(300, bars), td_key))

    # Fetch higher timeframe data for MTF alignment
    try:
        df_h1 = add_indicators(fetch_bars(s, "1h", 200, td_key))
    except Exception:
        df_h1 = None
    try:
        df_h4 = add_indicators(fetch_bars(s, "4h", 200, td_key))
    except Exception:
        df_h4 = None

    # Get HTF structure
    htf_trend = get_htf_structure(df_h1, df_h4)

    # Generate PA-based trade plan
    pa_plan = pa_generate_plan(df, symbol=s, htf_trend=htf_trend, htf_df=df_h4)

    # Convert PATradePlan → legacy Plan dataclass for compatibility
    if pa_plan.valid and pa_plan.direction in ("Buy", "Sell"):
        # Determine strategy name from entry type
        strategy_map = {
            "SWEEP_REVERSAL": "Sweep Reversal",
            "KEY_LEVEL_REJECTION": "Key Level Rejection",
            "BOS_CONTINUATION": "BOS Continuation",
            "CHOCH_REVERSAL": "CHoCH Reversal",
        }
        strategy = strategy_map.get(pa_plan.entry_type, "Price Action")

        # Build session info
        sess_pts, sess_name = session_score(s, df.iloc[-1].get("time", pd.Timestamp.utcnow()))

        ready_status = "Ready to Enter" if pa_plan.ready else "Wait"

        plan = Plan(
            symbol=s,
            regime=pa_plan.structure_trend.lower().replace("_weak", ""),
            strategy=strategy,
            direction=pa_plan.direction,
            execution_status=ready_status,
            setup_score=pa_plan.score,
            setup_grade=pa_plan.grade,
            entry=pa_plan.entry,
            sl=pa_plan.sl,
            tp1=pa_plan.tp1,
            tp2=pa_plan.tp2,
            tp3=pa_plan.tp3,
            rr=pa_plan.rr,
            reason="; ".join(pa_plan.reasons[:3]),
            entry_reasons=pa_plan.reasons,
            score_breakdown=pa_plan.breakdown,
            confluence_count=pa_plan.confluence_count,
            session_label=sess_name,
            session_score=sess_pts,
            mtf_aligned=(pa_plan.breakdown.get("MTF", 0) >= 6),
        )
        return df, plan

    # No valid setup — return empty plan
    regime = pa_plan.structure_trend if pa_plan.structure_trend else "ranging"
    reason = pa_plan.reasons[0] if pa_plan.reasons else "No setup"
    return df, _empty(s, regime.lower(), reason)


def select_plan_legacy(symbol:str, interval:str, bars:int, td_key:str) -> Tuple[pd.DataFrame,Plan]:
    """Legacy V1 plan selection (indicator-based). Kept for comparison."""
    s = norm(symbol)
    if s == "XAUUSD":
        df5 = add_indicators(fetch_bars(s,"5min",max(260,bars),td_key))
        df15 = add_indicators(fetch_bars(s,"15min",max(260,bars),td_key))
        df1h = add_indicators(fetch_bars(s,"1h",max(260,bars),td_key))
        return df5, _xau_plan(df5,df15,df1h,s)
    df = add_indicators(fetch_bars(s,interval,bars,td_key))
    regime = get_regime(df)
    if regime == "insufficient":
        return df, _empty(s,regime)
    htf_bias = _get_htf_bias(s, td_key) if interval not in ("1h","4h") else "neutral"
    if regime in ("trend_up","trend_down"):
        return df, _trend_plan(df,s,regime,htf_bias)
    if regime == "squeeze":
        return df, _squeeze_plan(df,s)
    return df, _mean_rev_plan(df,s,regime)

def finalize_plan(plan:Plan, balance:float, risk_pct:float) -> Plan:
    risk_amount = balance*(risk_pct/100)
    if plan.entry and plan.sl:
        stop_pips = abs(plan.entry-plan.sl)/max(pip_size(plan.symbol),1e-9)
        plan.base_lot = max(0.0,round(risk_amount/(stop_pips*pip_value(plan.symbol)),3)) if stop_pips>0 else 0.0
    plan.suggested_lot = plan.base_lot
    xai = get_xai_key()
    news = get_news_sentiment(plan.symbol, xai)
    plan.news_adj = news["adj"]
    plan.news_risk = news["risk"]
    plan.news_bias = news["bias"]
    plan.news_summary = news["summary"]
    plan.news_events = news.get("events",[])
    plan.news_ok = news.get("ok",False)
    # ── Trading Economics calendar integration ──
    te_events = fetch_te_calendar()
    te_penalty, te_warning, te_upcoming = te_news_check(plan.symbol, te_events)
    plan.te_penalty = te_penalty
    plan.te_warning = te_warning
    plan.te_upcoming = te_upcoming
    total_news_adj = plan.news_adj + te_penalty

    # ── Market-wide sentiment filter (crash/panic detection) ──
    try:
        mkt_sent = get_market_sentiment(get_td_key())
        plan.market_sentiment = mkt_sent["sentiment"]
        plan.market_bearish = mkt_sent["bearish_count"]
        plan.market_bullish = mkt_sent["bullish_count"]
        if plan.direction == "Buy":
            sentiment_adj = mkt_sent["penalty_buy"]
        elif plan.direction == "Sell":
            sentiment_adj = mkt_sent["penalty_sell"]
        else:
            sentiment_adj = 0
        total_news_adj += sentiment_adj
        plan.sentiment_adj = sentiment_adj
    except Exception:
        plan.market_sentiment = "UNKNOWN"
        plan.market_bearish = 0
        plan.market_bullish = 0
        plan.sentiment_adj = 0

    plan.final_score = int(max(0,min(100,plan.setup_score+total_news_adj)))
    plan.final_grade = score_to_grade(plan.final_score)

    # Block execution during high-risk conditions
    if te_penalty <= -15 and plan.execution_status=="Ready to Enter":
        plan.execution_status="HIGH NEWS RISK"
    elif plan.news_risk=="HIGH" and plan.execution_status=="Ready to Enter":
        plan.execution_status="HIGH NEWS RISK"
    elif getattr(plan, 'market_sentiment', '') == "RISK_OFF" and plan.direction == "Buy" and plan.execution_status == "Ready to Enter":
        plan.execution_status = "RISK OFF — WAIT"
    elif getattr(plan, 'market_sentiment', '') == "RISK_ON" and plan.direction == "Sell" and plan.execution_status == "Ready to Enter":
        plan.execution_status = "RISK ON — WAIT"
    return plan

# ============================================================
# LIVE HEALTH
# ============================================================
def compute_live_health(entry:float, sl:float, direction:str, df:pd.DataFrame,
                        mt5_price:Optional[float]=None) -> Dict:
    if mt5_price and mt5_price > 0:
        close = mt5_price
        price_src = "MT5"
    else:
        close = float(df.iloc[-1]["close"])
        price_src = "TD"

    risk = abs(entry-sl)
    if risk <= 0:
        return {"r_now":0.0,"status":"Invalid","advice":"Stop=0","health_pct":50,"color":"#8b9ab0","price_src":price_src,"close":close}

    r_now = (close-entry)/risk if direction=="Buy" else (entry-close)/risk
    hp = int(max(5,min(95,50+r_now*25)))

    if r_now >= 1.0:
        return {"r_now":round(r_now,2),"status":"Profit","advice":"TP1 hit","health_pct":hp,"color":"#10b981","price_src":price_src,"close":close}
    if r_now >= 0.0:
        return {"r_now":round(r_now,2),"status":"In trade","advice":"In profit","health_pct":hp,"color":"#00d4aa","price_src":price_src,"close":close}
    if r_now >= -0.5:
        return {"r_now":round(r_now,2),"status":"Drawdown","advice":"Normal.","health_pct":hp,"color":"#f59e0b","price_src":price_src,"close":close}
    if r_now >= -0.8:
        return {"r_now":round(r_now,2),"status":"Near SL","advice":"Approaching.","health_pct":hp,"color":"#f97316","price_src":price_src,"close":close}
    return {"r_now":round(r_now,2),"status":"SL Hit","advice":"Exit now.","health_pct":hp,"color":"#ef4444","price_src":price_src,"close":close}

# ============================================================
# CHART
# ============================================================
def build_chart(df:pd.DataFrame, plan:Plan, symbol:str) -> go.Figure:
    n = min(120,len(df))
    dfc = df.tail(n)
    fig = make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[0.72,0.28],
                        vertical_spacing=0.04)

    fig.add_trace(go.Candlestick(x=dfc["time"],open=dfc["open"],high=dfc["high"],
                                  low=dfc["low"],close=dfc["close"],name="Price",
                                  increasing_fillcolor="#10b981",increasing_line_color="#10b981",
                                  decreasing_fillcolor="#ef4444",decreasing_line_color="#ef4444"),row=1,col=1)

    for col2,color,nm in [("ema20","#00d4aa","EMA20"),("ema50","#f59e0b","EMA50"),("ema200","#8b9ab0","EMA200")]:
        if col2 in dfc.columns:
            fig.add_trace(go.Scatter(x=dfc["time"],y=dfc[col2],mode="lines",name=nm,
                                     line=dict(color=color,width=1.2)),row=1,col=1)

    if "bb_upper" in dfc.columns:
        fig.add_trace(go.Scatter(x=dfc["time"],y=dfc["bb_upper"],mode="lines",name="BB Upper",
                                 line=dict(color="rgba(99,102,241,0.4)",width=1,dash="dot")),row=1,col=1)
        fig.add_trace(go.Scatter(x=dfc["time"],y=dfc["bb_lower"],mode="lines",name="BB Lower",
                                 line=dict(color="rgba(99,102,241,0.4)",width=1,dash="dot"),
                                 fill="tonexty",fillcolor="rgba(99,102,241,0.04)"),row=1,col=1)

    for lbl,val,col3 in [("Entry",plan.entry,"#00d4aa"),("SL",plan.sl,"#ef4444"),
                          ("TP1",plan.tp1,"#a78bfa"),("TP2",plan.tp2,"#10b981")]:
        if val:
            fig.add_hline(y=val,line=dict(color=col3,width=1,dash="dot"),
                           annotation_text=lbl,annotation_font_color=col3,row=1,col=1)

    if "macd_hist" in dfc.columns:
        colors = ["#10b981" if v>=0 else "#ef4444" for v in dfc["macd_hist"]]
        fig.add_trace(go.Bar(x=dfc["time"],y=dfc["macd_hist"],name="MACD Hist",
                              marker_color=colors,opacity=0.7),row=2,col=1)
        fig.add_trace(go.Scatter(x=dfc["time"],y=dfc["macd"],mode="lines",name="MACD",
                                 line=dict(color="#00d4aa",width=1)),row=2,col=1)
        fig.add_trace(go.Scatter(x=dfc["time"],y=dfc["macd_sig"],mode="lines",name="Signal",
                                 line=dict(color="#f59e0b",width=1)),row=2,col=1)

    fig.update_layout(template="plotly_dark",height=500,margin=dict(l=8,r=8,t=8,b=8),
                      xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="right",x=1))
    return fig

# ============================================================
# PANEL HELPERS
# ============================================================
def render_kv_panel(title, rows):
    html = ["<div class='panel'>",f"<div class='mono-title'>{title}</div>"]
    for k,v,klass in rows:
        c = f" class='{klass}'" if klass else ""
        html.append(f"<div class='kv'><span class='muted'>{k}</span><span{c}>{v}</span></div>")
    html.append("</div>")
    st.markdown("".join(html),unsafe_allow_html=True)

def render_signal_badge(direction, status):
    if "HIGH NEWS" in status:
        cls, text = "signal-sell", "HIGH NEWS"
    elif status != "Ready to Enter":
        cls, text = "signal-wait", "WAIT"
    elif direction == "Buy":
        cls, text = "signal-buy", "BUY"
    elif direction == "Sell":
        cls, text = "signal-sell", "SELL"
    else:
        cls, text = "signal-wait", "WAIT"
    st.markdown(f"<div class='signal-box {cls}'>{text}</div>",unsafe_allow_html=True)

def render_score_panel(plan:Plan, df:pd.DataFrame, active_entry=None, active_sl=None, active_dir=None):
    gc = grade_color(plan.final_grade)
    adj = plan.news_adj
    adj_html = (f"<span style='color:#10b981;'>+{adj}</span>" if adj>0
                else f"<span style='color:#ef4444;'>{adj}</span>" if adj<0
                else "<span style='color:#8b9ab0;'>0</span>")

    filled = plan.confluence_count
    total = 6
    conf_color = "#10b981" if filled>=4 else "#f59e0b" if filled>=2 else "#ef4444"
    conf_dots = "".join([f"<span style='color:{conf_color};'>●</span>" if i<filled
                         else "<span style='color:#2a3441;'>●</span>" for i in range(total)])

    bd_html = ""
    for k,v in plan.score_breakdown.items():
        maxv = {"EMA Stack":20,"Pullback":15,"MACD":15,"RSI":10,"Candle":10,"R:R":20,"Session":10}.get(k,10)
        pct = int(v/max(maxv,1)*100)
        bar_col = "#10b981" if pct>=70 else "#f59e0b" if pct>=40 else "#ef4444"
        bd_html += (f"<div style='display:flex;align-items:center;gap:8px;margin:3px 0;font-size:11px;'>"
                    f"<span style='color:#8b9ab0;width:70px;flex-shrink:0;'>{k}</span>"
                    f"<div style='background:#131a22;border-radius:3px;flex:1;height:5px;'>"
                    f"<div style='width:{pct}%;height:100%;background:{bar_col};border-radius:3px;'></div></div>"
                    f"<span style='color:{bar_col};width:28px;text-align:right;font-family:Space Mono,monospace;'>{v}</span>"
                    f"</div>")

    st.markdown(f"""<div class='panel'>
      <div class='mono-title'>SIGNAL SCORE</div>
      <div style='display:flex;align-items:center;gap:14px;margin-bottom:8px;flex-wrap:wrap;'>
        <div><div style='font-size:10px;color:#8b9ab0;'>TECH</div>
          <div style='font-family:Space Mono,monospace;font-size:26px;font-weight:700;color:{grade_color(plan.setup_grade)};'>{plan.setup_score}</div></div>
        <div style='color:#4a5568;font-size:18px;'>+</div>
        <div><div style='font-size:10px;color:#8b9ab0;'>NEWS</div>
          <div style='font-family:Space Mono,monospace;font-size:26px;font-weight:700;'>{adj_html}</div></div>
        <div style='color:#4a5568;font-size:18px;'>=</div>
        <div><div style='font-size:10px;color:#8b9ab0;'>FINAL</div>
          <div style='font-family:Space Mono,monospace;font-size:26px;font-weight:700;color:{gc};'>
            {plan.final_score}<span style='font-size:14px;'> {plan.final_grade}</span></div></div>
      </div>
      <div style='background:#131a22;border-radius:4px;height:5px;margin-bottom:10px;overflow:hidden;'>
        <div style='height:100%;border-radius:4px;background:{gc};width:{plan.final_score}%;'></div></div>
      <div style='margin-bottom:8px;'>
        <span style='font-size:10px;color:#8b9ab0;font-family:Space Mono,monospace;'>CONFLUENCE </span>
        {conf_dots}
        <span style='font-size:10px;color:{conf_color};font-family:Space Mono,monospace;'> {filled}/{total}</span>
      </div>
{bd_html}
<div style='font-size:11px;color:#8b9ab0;border-top:1px solid rgba(255,255,255,0.05);padding-top:6px;margin-top:6px;'>
<b style='color:#e8edf2;'>Session:</b> {plan.session_label} | <b style='color:#e8edf2;'>MTF:</b> {'Aligned' if plan.mtf_aligned else 'Conflict'}
</div>
</div>""",unsafe_allow_html=True)

    live_health = None
    if active_entry and active_sl and active_dir:
        _ma_tick = fetch_mt5_price(plan.symbol,get_ma_token(),get_ma_account()) if (get_ma_token() and get_ma_account()) else None
        _mt5_price = _ma_tick["bid"] if _ma_tick else None
        live_health = compute_live_health(active_entry,active_sl,active_dir,df,mt5_price=_mt5_price)
        hc = live_health["color"]
        hp = live_health["health_pct"]
        src_label = live_health.get("price_src","TD")
        src_col = "#00d4aa" if src_label=="MT5" else "#f59e0b"
        src_note = f"<span style='font-size:9px;color:{src_col};margin-left:6px;'>price: {src_label}</span>"
        st.markdown(f"""<div class='panel'>
          <div class='mono-title'>LIVE HEALTH{src_note}</div>
          <div style='display:flex;align-items:center;gap:14px;margin-bottom:8px;'>
            <div style='font-family:Space Mono,monospace;font-size:26px;font-weight:700;color:{hc};'>{hp}%</div>
            <div><div style='font-size:13px;font-weight:600;color:{hc};'>{live_health['status']}</div>
              <div style='font-size:11px;color:#8b9ab0;'>R = {live_health['r_now']:+.2f}</div></div>
          </div>
          <div style='background:#131a22;border-radius:4px;height:5px;margin-bottom:8px;overflow:hidden;'>
            <div style='height:100%;border-radius:4px;background:{hc};width:{hp}%;'></div></div>
          <div style='font-size:12px;color:#e8edf2;padding:8px;background:#131a22;border-radius:5px;'>{live_health['advice']}</div>
        </div>""",unsafe_allow_html=True)
    else:
        st.markdown("""<div class='panel' style='border-color:rgba(255,255,255,0.04);'>
          <div class='mono-title' style='color:#4a5568;'>LIVE HEALTH</div>
        </div>""",unsafe_allow_html=True)

    _render_ai_panel(plan, df, live_health, active_entry, active_sl, active_dir)

def _render_ai_panel(plan, df, live_health, active_entry, active_sl, active_dir):
    xai = get_xai_key()
    st.markdown("""<div style='background:#0d1117;border:1px solid rgba(99,102,241,0.2);
        border-left:3px solid #6366f1;border-radius:8px;padding:12px 14px;margin-bottom:10px;'>
        <div style='color:#6366f1;font-size:11px;font-family:Space Mono,monospace;
        letter-spacing:.12em;margin-bottom:8px;'>GROK AI</div>
        </div>""", unsafe_allow_html=True)

    if not xai:
        st.markdown("<div style='font-size:12px;color:#4a5568;margin:-6px 0 8px;'>No xAI key.</div>",unsafe_allow_html=True)
        return

    if active_entry is None:
        st.markdown("<div style='font-size:12px;color:#4a5568;margin:-6px 0 8px;'>Enter trade to activate.</div>",unsafe_allow_html=True)
        return

    trade_key = f"ai_{plan.symbol}_{active_entry:.5f}"
    news_dict = {"risk":plan.news_risk,"bias":plan.news_bias,"summary":plan.news_summary,"ok":plan.news_ok}

    if trade_key not in st.session_state:
        with st.spinner("Grok..."):
            st.session_state[trade_key] = get_ai_trade_advice(plan,df,live_health,news_dict)

    advice = st.session_state.get(trade_key,"")
    if advice:
        safe_advice = advice.replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
        st.markdown(f"""<div class='ai-bubble'>
            <div class='ai-header'>ANALYSIS</div>{safe_advice}</div>""",
            unsafe_allow_html=True)

    user_q = st.text_input("Ask Grok...", placeholder="SL strategy?", key=f"gq_{plan.symbol}")
    if st.button("Ask", key=f"gb_{plan.symbol}"):
        if user_q.strip():
            with st.spinner("Thinking..."):
                st.session_state[f"gr_{plan.symbol}"] = get_ai_trade_advice(plan,df,live_health,news_dict,user_q)
        else:
            st.warning("Type first.")

    reply = st.session_state.get(f"gr_{plan.symbol}","")
    if reply:
        safe_reply = reply.replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
        st.markdown(f"""<div class='ai-bubble' style='border-left-color:#0ea5e9;background:rgba(14,165,233,.06);'>
            <div class='ai-header' style='color:#0ea5e9;'>REPLY</div>{safe_reply}</div>""",
            unsafe_allow_html=True)

def render_news_panel(plan:Plan):
    xai = get_xai_key()
    if not xai:
        st.markdown("<div class='panel'><div class='mono-title' style='color:#4a5568;'>GROK NEWS</div></div>",unsafe_allow_html=True)
        return

    risk = plan.news_risk
    adj = plan.news_adj
    bias = plan.news_bias
    risk_col = {"HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#10b981"}.get(risk,"#10b981")
    bias_col = {"bull":"#10b981","bear":"#ef4444"}.get(bias,"#8b9ab0")
    adj_str = (f"+{adj}" if adj>0 else str(adj))
    adj_col = "#10b981" if adj>0 else "#ef4444" if adj<0 else "#8b9ab0"
    safe_summary = str(plan.news_summary).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    evts = "".join(
        f"<div style='font-size:11px;color:#8b9ab0;padding:2px 0;'>{str(e).replace('<','&lt;').replace('>','&gt;')}</div>"
        for e in (plan.news_events or []))

    # ── Trading Economics upcoming events ──
    te_upcoming = getattr(plan, "te_upcoming", [])
    te_warning = getattr(plan, "te_warning", None)
    te_penalty = getattr(plan, "te_penalty", 0)
    te_html = ""
    if te_upcoming:
        te_items = "".join(f"<div style='font-size:11px;color:#c7d2fe;padding:2px 0;'>{e}</div>" for e in te_upcoming[:8])
        te_warn_html = ""
        if te_warning:
            te_warn_html = f"<div style='font-size:12px;color:#ef4444;font-weight:700;margin-bottom:4px;'>{te_warning} (penalty: {te_penalty})</div>"
        te_html = f"""<div style='border-top:1px solid rgba(255,255,255,0.08);padding-top:8px;margin-top:8px;'>
<div style='font-size:11px;color:#8b9ab0;font-weight:600;margin-bottom:4px;'>ECONOMIC CALENDAR</div>
{te_warn_html}{te_items}</div>"""
    elif TE_API_KEY:
        te_html = "<div style='border-top:1px solid rgba(255,255,255,0.08);padding-top:8px;margin-top:8px;font-size:11px;color:#4a5568;'>No upcoming events for this symbol</div>"

    st.markdown(f"""<div class='panel'>
<div class='mono-title'>GROK NEWS</div>
<div style='display:flex;align-items:center;gap:12px;margin-bottom:8px;'>
<div><span style='color:{risk_col};font-weight:700;'>{risk}</span></div>
<div><span style='color:{adj_col};font-weight:700;'>{adj_str}</span></div>
<div><span style='color:{bias_col};'>●</span> {bias}</div>
</div>
<div style='font-size:12px;color:#c7d2fe;margin-bottom:6px;'>{safe_summary}</div>
<div style='border-top:1px solid rgba(255,255,255,0.05);padding-top:6px;'>{evts}</div>
{te_html}
</div>""",unsafe_allow_html=True)

def render_trade_tracker(plan: Plan, current_price: float, df: pd.DataFrame):
    """Renders trade entry form + active trades. Returns (entry, sl, direction) or None."""
    if "active_trades" not in st.session_state:
        st.session_state.active_trades = []
    trades = st.session_state.active_trades
    n_trades = len(trades)
    badge = (f" <span style='color:#00d4aa;font-size:11px;background:rgba(0,212,170,0.1);"
             f"padding:2px 8px;border-radius:3px;'>{n_trades} open</span>") if n_trades else ""
    st.markdown(f"<div class='panel'><div class='mono-title'>TRADE TRACKER{badge}</div>", unsafe_allow_html=True)

    with st.expander("Enter New Trade", expanded=(n_trades == 0)):
        c1, c2 = st.columns(2)
        me = c1.number_input("Entry", value=float(plan.entry or current_price), format="%.5f", key="te_e")
        ms = c2.number_input("Stop Loss", value=float(plan.sl or current_price), format="%.5f", key="te_s")
        md = c1.selectbox("Direction", ["Buy", "Sell"], index=0 if plan.direction == "Buy" else 1, key="te_d")
        ml = c2.number_input("Lot", value=float(max(plan.suggested_lot, 0.01)), format="%.3f", key="te_l")
        tc1, tc2 = st.columns(2)
        mtp1 = tc1.number_input("TP1", value=float(plan.tp1 or current_price), format="%.5f", key="te_tp1")
        mtp2 = tc2.number_input("TP2", value=float(plan.tp2 or current_price), format="%.5f", key="te_tp2")

        if st.button("Enter Trade", key="btn_enter"):
            import uuid
            new_trade = {
                "id": str(uuid.uuid4())[:8],
                "symbol": plan.symbol,
                "entry": me, "sl": ms, "direction": md, "lot": ml,
                "tp1": mtp1, "tp2": mtp2,
                "locked_score": plan.setup_score,
                "locked_final": plan.final_score,
                "locked_grade": plan.setup_grade,
            }
            st.session_state.active_trades.append(new_trade)
            st.success(f"Trade entered! ({plan.symbol} {md})")
            st.rerun()

    # Active trade cards
    if not trades:
        st.markdown("<div style='font-size:12px;color:#4a5568;padding:6px 0;'>No open trades.</div>", unsafe_allow_html=True)
    else:
        for t in trades:
            tid = t.get("id", "0")
            t_dir = t["direction"]
            t_entry = float(t["entry"])
            t_sl = float(t["sl"])
            t_risk = abs(t_entry - t_sl)
            dir_col = "#10b981" if t_dir == "Buy" else "#ef4444"
            _move = (current_price - t_entry) if t_dir == "Buy" else (t_entry - current_price)
            _pnl_r = _move / t_risk if t_risk > 0 else 0
            pnl_col = "#10b981" if _pnl_r >= 0 else "#ef4444"

            st.markdown(
                f"<div style='border:1px solid rgba(255,255,255,0.07);border-radius:6px;padding:8px 10px;margin:6px 0;background:#090e14;'>"
                f"<div style='font-size:10px;color:#8b9ab0;margin-bottom:4px;'>"
                f"<span style='color:{dir_col};font-weight:700;'>{t_dir}</span>"
                f" <span style='color:#4a5568;'>· {t.get('lot', 0.01)} lot · #{tid}</span></div>"
                f"<div style='display:flex;gap:10px;font-size:12px;'>"
                f"<div><span class='muted'>Entry</span> <b style='color:#00d4aa;font-family:Space Mono,monospace;'>{fmt_price(t_entry, plan.symbol)}</b></div>"
                f"<div><span class='muted'>SL</span> <b style='color:#ef4444;font-family:Space Mono,monospace;'>{fmt_price(t_sl, plan.symbol)}</b></div>"
                f"<div><span class='muted'>P&L</span> <b style='color:{pnl_col};font-family:Space Mono,monospace;'>{_pnl_r:+.2f}R</b></div>"
                f"</div></div>",
                unsafe_allow_html=True)

            if st.button(f"Close #{tid}", key=f"btn_close_{tid}"):
                st.session_state.active_trades = [x for x in st.session_state.active_trades if x.get("id") != tid]
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Return active trade for Live Health
    for t in trades:
        if t.get("symbol", plan.symbol) == plan.symbol:
            return t["entry"], t["sl"], t["direction"]
    if trades:
        return trades[0]["entry"], trades[0]["sl"], trades[0]["direction"]
    return None

# ============================================================
# MARKET OVERVIEW TABLE
# ============================================================
def build_overview_row(sym, balance, risk_pct, td_key):
    try:
        df, plan = select_plan(sym, "15min", 260, td_key)
        plan = finalize_plan(plan, balance, risk_pct)
        price = float(df["close"].iloc[-1])
        row = {"Symbol": sym, "Price": fmt_price(price, sym), "Signal": plan.direction,
                "Status": plan.execution_status[:18], "Tech": plan.setup_score,
                "News Adj": plan.news_adj, "Final": plan.final_score, "Grade": plan.final_grade,
                "R:R": fmt_rr(plan.rr), "Session": plan.session_label[:15], "News": plan.news_risk}
        return row, plan
    except Exception as e:
        return {"Symbol": sym, "Price": "ERR", "Signal": "—", "Status": str(e)[:18],
                "Tech": 0, "News Adj": 0, "Final": 0, "Grade": "D", "R:R": "—", "Session": "—", "News": "—"}, None


# ============================================================
# TELEGRAM AUTO-SEND (A / A+ signals — score >= 80)
# ============================================================
def _maybe_send_telegram(plan: Plan, notifier):
    """Auto-send Telegram for A/A+ signals (score>=80) with 30-min cooldown per symbol."""
    if not notifier:
        return
    if plan.final_score < 80 or plan.execution_status != "Ready to Enter":
        return
    if plan.direction not in ("Buy", "Sell"):
        return

    # Cooldown by symbol+direction ONLY (not score) to prevent spam when score fluctuates
    cooldown_key = f"{plan.symbol}_{plan.direction}"
    sent_signals = st.session_state.get("tg_sent_signals", {})
    now = datetime.utcnow()

    if cooldown_key in sent_signals:
        last_sent = sent_signals[cooldown_key]
        if (now - last_sent).total_seconds() < 1800:  # 30-min cooldown
            return

    try:
        grade_label = "A+" if plan.final_score >= 90 else "A"
        dir_emoji = "🟢" if plan.direction == "Buy" else "🔴"
        msg = (f"{dir_emoji} <b>{grade_label} SIGNAL — {plan.symbol}</b>\n\n"
               f"Direction: <b>{plan.direction}</b>\n"
               f"Score: <b>{plan.final_score}/100 ({plan.final_grade})</b>\n"
               f"Strategy: {plan.strategy}\n"
               f"Entry: <code>{fmt_price(plan.entry, plan.symbol)}</code>\n"
               f"SL: <code>{fmt_price(plan.sl, plan.symbol)}</code>\n"
               f"TP1: <code>{fmt_price(plan.tp1, plan.symbol)}</code>\n"
               f"TP2: <code>{fmt_price(plan.tp2, plan.symbol)}</code>\n"
               f"R:R: {fmt_rr(plan.rr)}\n"
               f"Regime: {plan.regime}\n"
               f"Session: {plan.session_label}\n"
               f"Confluence: {plan.confluence_count}/6\n\n"
               f"⚡ <b>READY TO ENTER</b>")
        notifier.broadcast(msg)
        sent_signals[cooldown_key] = now
        st.session_state["tg_sent_signals"] = sent_signals
    except Exception as e:
        import logging
        logging.error(f"Telegram send failed: {e}")


# ============================================================
# MAIN RENDER: LIVE ANALYSIS (Cyberpunk Dashboard)
# ============================================================
def render_live(symbol, interval, bars, balance, risk_pct, notifier):
    cyberpunk_header("LIVE DASHBOARD", f"{symbol} // Real-time Price Action Analysis")
    is_open, mkt = market_is_open(symbol)
    try:
        df, plan = select_plan(symbol, interval, bars, get_td_key())
        latest = df.iloc[-1]
        td_price = float(latest["close"])
        prev = float(df.iloc[-2]["close"]) if len(df) > 1 else td_price
        sweep = detect_sweep(df, symbol)
        if not is_open and norm(symbol) in FOREX_SYMBOLS:
            plan = _empty(symbol, "closed", "MARKET CLOSED")
        plan = finalize_plan(plan, balance, risk_pct)
    except Exception as e:
        st.error(f"Error: {e}")
        return

    # ── MT5 live price ──
    _ma_tok = get_ma_token()
    _ma_acc = get_ma_account()
    mt5_tick = fetch_mt5_price(symbol, _ma_tok, _ma_acc) if (_ma_tok and _ma_acc) else None
    if mt5_tick:
        price = mt5_tick["bid"]
        price_src_label = f"MT5 {fmt_price(mt5_tick['bid'], symbol)}/{fmt_price(mt5_tick['ask'], symbol)}  spread {mt5_tick['spread_pips']}p"
        price_src_col = "#00d4aa"
    else:
        price = td_price
        price_src_label = "Twelve Data (delayed)"
        price_src_col = "#f59e0b"
    chg = price - prev
    chg_pct = (chg / prev * 100) if prev else 0

    # ── Auto Telegram for A/A+ ──
    _maybe_send_telegram(plan, notifier)

    # ── A/A+ POPUP ALERT WITH SOUND ──
    if plan.final_score >= 80 and plan.direction in ("Buy", "Sell"):
        alert_key = f"alert_{symbol}_{plan.direction}_{plan.final_score}"
        if alert_key not in st.session_state:
            st.session_state[alert_key] = True
            dir_emoji = "🟢" if plan.direction == "Buy" else "🔴"
            st.markdown(f"""
<div id="fx-alert" style="position:fixed;top:80px;left:50%;transform:translateX(-50%);z-index:9999;
background:linear-gradient(135deg,#0f2027,#203a43);border:2px solid {'#10b981' if plan.direction=='Buy' else '#ef4444'};
border-radius:12px;padding:20px 32px;box-shadow:0 8px 32px rgba(0,0,0,0.6);text-align:center;min-width:380px;animation:fadeIn 0.3s ease-in;">
<div style="font-size:28px;margin-bottom:6px;">{dir_emoji}</div>
<div style="font-family:Space Mono,monospace;font-size:20px;font-weight:700;color:{'#10b981' if plan.direction=='Buy' else '#ef4444'};letter-spacing:0.1em;">
{plan.final_grade} SIGNAL — {plan.direction.upper()}</div>
<div style="font-size:32px;font-weight:800;color:#e8edf2;margin:8px 0;">{SYMBOL_NAMES.get(symbol,symbol)}</div>
<div style="font-size:14px;color:#c7d2fe;">Score: {plan.final_score}/100 | R:R {fmt_rr(plan.rr)} | {plan.strategy}</div>
<div style="font-size:13px;color:#8b9ab0;margin-top:6px;">Entry: {fmt_price(plan.entry,symbol)} | SL: {fmt_price(plan.sl,symbol)} | TP1: {fmt_price(plan.tp1,symbol)}</div>
<div style="margin-top:12px;font-size:12px;color:#00d4aa;font-weight:600;letter-spacing:0.15em;">READY TO ENTER</div>
</div>
<style>@keyframes fadeIn{{from{{opacity:0;transform:translateX(-50%) translateY(-20px);}}to{{opacity:1;transform:translateX(-50%) translateY(0);}}}}</style>
<script>
(function(){{
  try {{
    var ctx = new (window.AudioContext||window.webkitAudioContext)();
    var o = ctx.createOscillator();
    var g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.type = 'sine';
    g.gain.value = 0.3;
    // Play alert tone: 3 beeps
    var t = ctx.currentTime;
    o.frequency.setValueAtTime(880, t);
    g.gain.setValueAtTime(0.3, t);
    g.gain.setValueAtTime(0, t+0.15);
    g.gain.setValueAtTime(0.3, t+0.25);
    g.gain.setValueAtTime(0, t+0.4);
    g.gain.setValueAtTime(0.3, t+0.5);
    g.gain.setValueAtTime(0, t+0.65);
    o.start(t); o.stop(t+0.7);
  }} catch(e) {{}}
  // Auto-dismiss after 8 seconds
  setTimeout(function(){{
    var el = document.getElementById('fx-alert');
    if(el) el.style.display='none';
  }}, 8000);
}})();
</script>""", unsafe_allow_html=True)

    # ── MT5 open positions ──
    mt5_positions = fetch_mt5_positions(_ma_tok, _ma_acc) if (_ma_tok and _ma_acc) else []

    # ── SIGNAL OVERVIEW DASHBOARD (all symbols at a glance) ──
    st.markdown("<div class='mono-title' style='font-size:13px;margin-bottom:6px;'>SIGNAL OVERVIEW — ALL SYMBOLS</div>", unsafe_allow_html=True)
    overview_syms = [s for s in INTERNAL_SYMBOLS if s != symbol][:6]  # top 6 other symbols
    ov_cols = st.columns(min(len(overview_syms) + 1, 7))
    # Current symbol first (highlighted)
    with ov_cols[0]:
        dir_icon = "BUY" if plan.direction == "Buy" else "SELL" if plan.direction == "Sell" else "WAIT"
        dir_c = "#10b981" if plan.direction == "Buy" else "#ef4444" if plan.direction == "Sell" else "#f59e0b"
        gc_ov = grade_color(plan.final_grade)
        st.markdown(f"<div style='background:#0d1117;border:2px solid {dir_c};border-radius:8px;padding:10px;text-align:center;'>"
                    f"<div style='font-size:12px;font-weight:700;color:#00d4aa;'>{symbol}</div>"
                    f"<div style='font-size:18px;font-weight:700;color:{dir_c};margin:4px 0;'>{dir_icon}</div>"
                    f"<div style='font-size:11px;color:{gc_ov};'>{plan.final_score} {plan.final_grade}</div>"
                    f"<div style='font-size:10px;color:#8b9ab0;'>{plan.strategy[:12]}</div></div>", unsafe_allow_html=True)
    # Other symbols
    for idx, ov_sym in enumerate(overview_syms):
        with ov_cols[idx + 1]:
            try:
                ov_row, ov_plan = build_overview_row(ov_sym, balance, risk_pct, get_td_key())
                # Send Telegram for A/A+ signals on ANY symbol
                if ov_plan:
                    _maybe_send_telegram(ov_plan, notifier)
                ov_dir = ov_row.get("Signal", "—")
                ov_dir_c = "#10b981" if ov_dir == "Buy" else "#ef4444" if ov_dir == "Sell" else "#f59e0b"
                ov_grade = ov_row.get("Grade", "D")
                ov_gc = grade_color(ov_grade)
                ov_label = "BUY" if ov_dir == "Buy" else "SELL" if ov_dir == "Sell" else "WAIT"
                st.markdown(f"<div style='background:#0d1117;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:10px;text-align:center;'>"
                            f"<div style='font-size:11px;font-weight:600;color:#8b9ab0;'>{ov_sym}</div>"
                            f"<div style='font-size:16px;font-weight:700;color:{ov_dir_c};margin:4px 0;'>{ov_label}</div>"
                            f"<div style='font-size:11px;color:{ov_gc};'>{ov_row.get('Final',0)} {ov_grade}</div>"
                            f"<div style='font-size:10px;color:#8b9ab0;'>{ov_row.get('Status','—')[:12]}</div></div>", unsafe_allow_html=True)
            except Exception:
                st.markdown(f"<div style='background:#0d1117;border:1px solid rgba(255,255,255,0.07);border-radius:8px;padding:10px;text-align:center;'>"
                            f"<div style='font-size:11px;color:#8b9ab0;'>{ov_sym}</div>"
                            f"<div style='font-size:14px;color:#4a5568;margin:4px 0;'>—</div></div>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Title bar ──
    top1, top2, top3 = st.columns([2, 3, 1])
    with top1:
        render_signal_badge(plan.direction, plan.execution_status)
    with top2:
        pc = "#10b981" if chg >= 0 else "#ef4444"
        st.markdown(
            f"<div style='font-family:Space Mono,monospace;font-size:22px;font-weight:700;padding-top:4px;'>"
            f"{fmt_price(price, symbol)}"
            f"<span style='font-size:13px;color:{pc};'> {chg:+.5f} ({chg_pct:+.3f}%)</span>"
            f"<span style='font-size:10px;color:{price_src_col};margin-left:8px;'>{price_src_label}</span></div>",
            unsafe_allow_html=True)
    with top3:
        lc = "#10b981" if mkt == "LIVE" else "#f59e0b"
        st.markdown(f"<div style='text-align:right;padding-top:8px;'><span style='font-family:Space Mono,monospace;font-size:11px;padding:4px 10px;border-radius:4px;border:1px solid rgba(255,255,255,.08);color:{lc};'>{mkt}</span></div>", unsafe_allow_html=True)

    # ── MT5 positions panel ──
    if mt5_positions:
        pos_rows = []
        for p in mt5_positions:
            sym_p = p.get("symbol", "?")
            typ = p.get("type", "?").replace("POSITION_TYPE_", "")
            vol = p.get("volume", 0)
            op = p.get("openPrice", 0)
            cp = p.get("currentPrice", 0)
            profit = p.get("profit", 0)
            sl_p = p.get("stopLoss", 0)
            tp_p = p.get("takeProfit", 0)
            pos_rows.append({"Symbol": sym_p, "Type": typ, "Vol": vol,
                             "Open": fmt_price(op, sym_p), "Current": fmt_price(cp, sym_p),
                             "SL": fmt_price(sl_p, sym_p) if sl_p else "—",
                             "TP": fmt_price(tp_p, sym_p) if tp_p else "—",
                             "P&L": f"${profit:+.2f}"})
        st.markdown("<div style='font-family:Space Mono,monospace;font-size:11px;color:#00d4aa;letter-spacing:.08em;margin:4px 0 2px;'>MT5 OPEN POSITIONS</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)

    # ── KPI BAR (V12 style with 12 inline metrics) ──
    gc = grade_color(plan.final_grade)
    rsi_val = fmt_num(latest.get("rsi14"), 1)
    rsi_col = "#ef4444" if rsi_val != "—" and float(rsi_val) > 70 else "#10b981" if rsi_val != "—" and float(rsi_val) < 30 else "#e8edf2"
    news_col = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}.get(plan.news_risk, "#8b9ab0")
    conf_col = "#10b981" if plan.confluence_count >= 4 else "#f59e0b" if plan.confluence_count >= 2 else "#ef4444"
    adj_col = "#10b981" if plan.news_adj > 0 else "#ef4444" if plan.news_adj < 0 else "#8b9ab0"
    dir_col = "#10b981" if plan.direction == "Buy" else "#ef4444" if plan.direction == "Sell" else "#f59e0b"

    def kpi(lbl, val, col="#e8edf2"):
        return (f"<div style='background:#0d1117;border:1px solid rgba(255,255,255,0.07);border-radius:6px;padding:12px 14px;min-width:100px;'>"
                f"<div style='font-size:10px;color:#8b9ab0;font-family:Space Mono,monospace;letter-spacing:.07em;margin-bottom:6px;'>{lbl}</div>"
                f"<div style='font-size:15px;font-weight:700;color:{col};font-family:Space Mono,monospace;'>{val}</div></div>")

    adj_str = ("+" + str(plan.news_adj)) if plan.news_adj >= 0 else str(plan.news_adj)
    # Market sentiment display
    mkt_sent = getattr(plan, 'market_sentiment', 'UNKNOWN')
    mkt_bear = getattr(plan, 'market_bearish', 0)
    mkt_bull = getattr(plan, 'market_bullish', 0)
    sent_adj = getattr(plan, 'sentiment_adj', 0)
    sent_col = "#ef4444" if mkt_sent == "RISK_OFF" else "#10b981" if mkt_sent == "RISK_ON" else "#f59e0b"
    sent_label = f"{mkt_sent}" if mkt_sent != "UNKNOWN" else "—"
    sent_adj_str = f"{sent_adj:+d}" if sent_adj != 0 else "0"
    st.markdown(f"""<div style='display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:14px 0;'>
{kpi("STRATEGY", plan.strategy[:18], "#00d4aa")}
{kpi("TECH", str(plan.setup_score), grade_color(plan.setup_grade))}
{kpi("NEWS", adj_str, adj_col)}
{kpi("FINAL", str(plan.final_score), gc)}
{kpi("GRADE", plan.final_grade, gc)}
{kpi("CONFLUENCE", f"{plan.confluence_count}/6", conf_col)}
</div>
<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin:0 0 14px;'>
{kpi("SESSION", plan.session_label[:14], "#8b9ab0")}
{kpi("NEWS RISK", plan.news_risk, news_col)}
{kpi("DIRECTION", plan.direction, dir_col)}
{kpi("R:R", fmt_rr(plan.rr), "#a78bfa")}
{kpi("RSI14", rsi_val, rsi_col)}
{kpi("LOT", fmt_num(plan.suggested_lot, 3), "#00d4aa")}
{kpi("MARKET", f"{sent_label} ({sent_adj_str})", sent_col)}
</div>""", unsafe_allow_html=True)
    st.markdown("---")

    # ── 3-COLUMN LAYOUT ──
    col_l, col_c, col_r = st.columns([1.05, 2.2, 1.15])

    with col_l:
        render_kv_panel("ENTRY LEVELS", [
            ("ENTRY", fmt_price(plan.entry, symbol), "good"),
            ("STOP LOSS", fmt_price(plan.sl, symbol), "bad"),
            ("TP1", fmt_price(plan.tp1, symbol), "warn"),
            ("TP2", fmt_price(plan.tp2, symbol), "good"),
            ("TP3", fmt_price(plan.tp3, symbol), "info") if plan.tp3 else ("TP3", "—", "muted"),
        ])
        render_kv_panel("EXIT RULES", [(f"#{i+1}", r, "") for i, r in enumerate(plan.exit_conditions or ["No exit plan"])])
        if sweep["detected"]:
            render_kv_panel("SWEEP", [("Severity", sweep["severity"], "bad" if sweep["severity"] == "HIGH" else "warn"), ("Detail", sweep["desc"], "")])
        render_news_panel(plan)

        # ── GROK PRE-ENTRY ANALYSIS (confirm before entering) ──
        xai_key = get_xai_key()
        if xai_key and plan.direction in ("Buy", "Sell"):
            with st.expander("GROK AI — Confirm Trade?", expanded=False):
                grok_pre_key = f"grok_pre_{symbol}_{plan.direction}_{plan.setup_score}"
                if st.button("Analyze Setup", key="btn_grok_pre"):
                    with st.spinner("Grok analyzing..."):
                        row = df.iloc[-1]
                        recent = df.tail(10)[["open", "high", "low", "close"]].round(5).to_string(index=False)
                        msg = (f"I'm considering a {plan.direction} on {SYMBOL_NAMES.get(symbol, symbol)}.\n"
                               f"Strategy: {plan.strategy} | Regime: {plan.regime}\n"
                               f"Score: {plan.setup_score}/100 ({plan.setup_grade}) | Confluence: {plan.confluence_count}/6\n"
                               f"Entry: {fmt_price(plan.entry, symbol)} | SL: {fmt_price(plan.sl, symbol)} | "
                               f"TP1: {fmt_price(plan.tp1, symbol)} | TP2: {fmt_price(plan.tp2, symbol)}\n"
                               f"R:R: {fmt_rr(plan.rr)} | RSI: {fmt_num(row.get('rsi14'), 1)}\n"
                               f"News: {plan.news_risk} risk, {plan.news_bias} bias\n"
                               f"Session: {plan.session_label}\n"
                               f"Last 10 bars:\n{recent}\n"
                               f"Should I take this trade? ENTER or SKIP? Brief reasoning (3-4 sentences).")
                        result = _grok(
                            [{"role": "system", "content": "You are a professional forex risk manager. Be direct. Say ENTER or SKIP first, then explain why."},
                             {"role": "user", "content": msg}],
                            max_tokens=300, temperature=0.3, api_key=xai_key)
                        st.session_state[grok_pre_key] = result or "No response"
                pre_advice = st.session_state.get(grok_pre_key, "")
                if pre_advice:
                    safe = pre_advice.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    st.markdown(f"<div class='ai-bubble'><div class='ai-header'>GROK VERDICT</div>{safe}</div>", unsafe_allow_html=True)

    with col_c:
        st.plotly_chart(build_chart(df, plan, symbol), use_container_width=True)
        # Entry reasoning
        if plan.entry_reasons:
            st.markdown("<div class='panel'><div class='mono-title'>WHY THIS TRADE</div>", unsafe_allow_html=True)
            for reason in plan.entry_reasons:
                safe_r = str(reason).replace("<", "&lt;").replace(">", "&gt;")
                st.markdown(f"<div style='font-size:12px;color:#c7d2fe;padding:3px 0;border-bottom:1px solid rgba(255,255,255,0.04);'>{safe_r}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with col_r:
        active = render_trade_tracker(plan, price, df)
        ae, asl, ad = (active if active else (None, None, None))
        render_score_panel(plan, df, ae, asl, ad)
        render_kv_panel("RISK PLAN", [
            ("Balance", f"${balance:,.2f}", ""),
            ("Risk %", f"{risk_pct:.1f}%", ""),
            ("Risk $", f"${balance * risk_pct / 100:,.2f}", "warn"),
            ("Lot", fmt_num(plan.suggested_lot, 3), "good"),
            ("Status", plan.execution_status[:20],
             "good" if plan.execution_status == "Ready to Enter" else "bad" if "HIGH NEWS" in plan.execution_status else "warn"),
        ])

        # ── GROK AI CHAT ──
        render_grok_chat(plan, df, symbol, price)


def render_grok_chat(plan: Plan, df: pd.DataFrame, symbol: str, current_price: float):
    """Interactive Grok AI chat panel — user asks, Grok sees the full chart context."""
    xai_key = get_xai_key()
    st.markdown("<div class='panel'><div class='mono-title'>GROK AI CHAT</div>", unsafe_allow_html=True)

    if not xai_key:
        st.markdown("<div style='font-size:12px;color:#4a5568;'>Add Grok API key in sidebar to enable AI chat</div></div>", unsafe_allow_html=True)
        return

    # Initialize chat history
    chat_key = f"grok_chat_{symbol}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    # Display chat history
    for msg in st.session_state[chat_key]:
        role_col = "#00d4aa" if msg["role"] == "assistant" else "#c7d2fe"
        role_label = "GROK" if msg["role"] == "assistant" else "YOU"
        safe_text = msg["content"].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        st.markdown(f"<div style='margin:6px 0;padding:8px 10px;background:rgba(255,255,255,0.03);border-radius:6px;border-left:2px solid {role_col};'>"
                    f"<span style='font-size:10px;color:{role_col};font-weight:600;'>{role_label}</span><br>"
                    f"<span style='font-size:12px;color:#e8edf2;'>{safe_text}</span></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Chat input
    user_msg = st.text_input("Ask Grok about the chart...", key=f"grok_input_{symbol}", placeholder="e.g. Should I buy now? What's the trend?")

    if st.button("Send", key=f"grok_send_{symbol}") and user_msg.strip():
        row = df.iloc[-1]
        recent_bars = df.tail(8)[["open","high","low","close"]].round(5).to_string(index=False)

        # Build full context of what the user sees on screen
        context = (
            f"Current symbol: {SYMBOL_NAMES.get(symbol, symbol)} ({symbol})\n"
            f"Price: {fmt_price(current_price, symbol)} | Spread: MT5 live\n"
            f"Strategy: {plan.strategy} | Regime: {plan.regime}\n"
            f"Direction: {plan.direction} | Score: {plan.setup_score}/100 ({plan.setup_grade})\n"
            f"Confluence: {plan.confluence_count}/6\n"
            f"Entry: {fmt_price(plan.entry, symbol)} | SL: {fmt_price(plan.sl, symbol)}\n"
            f"TP1: {fmt_price(plan.tp1, symbol)} | TP2: {fmt_price(plan.tp2, symbol)}\n"
            f"R:R: {fmt_rr(plan.rr)} | RSI: {fmt_num(row.get('rsi14'), 1)}\n"
            f"MACD Hist: {fmt_num(row.get('macd_hist'), 5)} | EMA20: {fmt_price(row.get('ema20'), symbol)}\n"
            f"EMA50: {fmt_price(row.get('ema50'), symbol)} | EMA200: {fmt_price(row.get('ema200'), symbol)}\n"
            f"BB Upper: {fmt_price(row.get('bb_upper'), symbol)} | BB Lower: {fmt_price(row.get('bb_lower'), symbol)}\n"
            f"ATR14: {fmt_num(row.get('atr14'), 5)}\n"
            f"News Risk: {plan.news_risk} | News Bias: {plan.news_bias}\n"
            f"Session: {plan.session_label}\n"
            f"Score Breakdown: {plan.score_breakdown}\n"
            f"Last 8 candles (15min):\n{recent_bars}\n"
        )

        # Build messages with history
        messages = [
            {"role": "system", "content": (
                "You are Grok, a professional forex/gold trading analyst embedded in Alpha FX Hub. "
                "The trader is watching a live chart and asking you questions. You can see all their indicators and data below. "
                "Be concise (2-5 sentences), direct, and actionable. Use trading language. "
                "If they ask about entries, reference specific price levels. "
                "Always consider the score, R:R, confluence, and news risk in your answers.\n\n"
                f"CURRENT CHART DATA:\n{context}"
            )}
        ]
        # Add chat history (last 6 messages to keep context manageable)
        for msg in st.session_state[chat_key][-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_msg})

        with st.spinner("Grok thinking..."):
            reply = _grok(messages, max_tokens=400, temperature=0.3, api_key=xai_key)

        if reply:
            st.session_state[chat_key].append({"role": "user", "content": user_msg})
            st.session_state[chat_key].append({"role": "assistant", "content": reply})
            st.rerun()
        else:
            st.error("Grok didn't respond. Check API key.")


# ============================================================
# BACKTEST ENGINE
# ============================================================
def render_backtest(td_key):
    cyberpunk_header("BACKTEST ENGINE", "Test your strategies against historical data")
    bc1, bc2, bc3, bc4 = st.columns(4)
    bt_sym = bc1.selectbox("Symbol", INTERNAL_SYMBOLS, index=INTERNAL_SYMBOLS.index("XAUUSD") if "XAUUSD" in INTERNAL_SYMBOLS else 0, key="bt_sym")
    bt_int = bc2.selectbox("Interval", ["15min", "1h", "4h"], index=0, key="bt_int")
    bt_bal = bc3.number_input("Balance", min_value=10.0, value=500.0, step=50.0, key="bt_bal")
    bt_rsk = bc4.number_input("Risk %", min_value=0.1, max_value=5.0, value=1.0, step=0.1, key="bt_rsk")
    fc1, fc2 = st.columns(2)
    score_thresh = fc1.slider("Min Score to trade", 40, 90, 70, 5, key="bt_thresh")
    max_bars = fc2.slider("History bars", 400, 1000, 700, 50, key="bt_bars")

    if not st.button("Run Backtest"):
        return
    with st.spinner("Fetching data and running simulation..."):
        try:
            s = norm(bt_sym)
            df = add_indicators(fetch_bars(s, bt_int, max_bars, td_key))
            results = []
            for i in range(220, len(df) - 20):
                chunk = df.iloc[:i + 1].copy()
                regime = get_regime(chunk)
                if regime == "insufficient":
                    continue
                if regime in ("trend_up", "trend_down"):
                    plan = _trend_plan(chunk, s, regime, "neutral")
                elif regime == "squeeze":
                    plan = _squeeze_plan(chunk, s)
                else:
                    plan = _mean_rev_plan(chunk, s, regime)
                if plan.execution_status != "Ready to Enter" or plan.entry is None:
                    continue
                if plan.setup_score < score_thresh:
                    continue
                future = df.iloc[i + 1:i + 21]
                outcome = None
                er = None
                for _, row in future.iterrows():
                    if plan.direction == "Buy":
                        if row["low"] <= plan.sl:
                            outcome = -1.0
                            er = "SL"
                            break
                        if row["high"] >= plan.tp1:
                            outcome = abs(plan.tp1 - plan.entry) / max(abs(plan.entry - plan.sl), 1e-9)
                            er = "TP1"
                            break
                    else:
                        if row["high"] >= plan.sl:
                            outcome = -1.0
                            er = "SL"
                            break
                        if row["low"] <= plan.tp1:
                            outcome = abs(plan.entry - plan.tp1) / max(abs(plan.sl - plan.entry), 1e-9)
                            er = "TP1"
                            break
                if outcome is None:
                    lc = float(future.iloc[-1]["close"])
                    outcome = (lc - plan.entry) / max(abs(plan.entry - plan.sl), 1e-9) if plan.direction == "Buy" else (plan.entry - lc) / max(abs(plan.sl - plan.entry), 1e-9)
                    er = "Time"
                pnl = outcome * bt_bal * (bt_rsk / 100)
                results.append({"time": chunk.iloc[-1]["time"], "symbol": s, "direction": plan.direction,
                                "strategy": plan.strategy, "grade": plan.setup_grade, "score": plan.setup_score,
                                "regime": plan.regime, "r_mult": round(outcome, 3), "pnl": round(pnl, 2),
                                "exit": er})
            tdf = pd.DataFrame(results)
        except Exception as e:
            st.error(f"Backtest error: {e}")
            return

    if tdf.empty:
        st.warning("No trades generated at this score threshold.")
        return
    tdf["cum_pnl"] = tdf["pnl"].cumsum()
    tdf["win"] = (tdf["pnl"] > 0).astype(int)

    # Top metrics
    wins = tdf["win"].sum()
    losses = len(tdf) - wins
    wr = wins / len(tdf) * 100
    gross_p = tdf[tdf["pnl"] > 0]["pnl"].sum()
    gross_l = abs(tdf[tdf["pnl"] < 0]["pnl"].sum())
    pf = gross_p / max(gross_l, 1e-9)
    net = tdf["pnl"].sum()
    avg_r = tdf["r_mult"].mean()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Trades", len(tdf))
    m2.metric("Win Rate", f"{wr:.1f}%")
    m3.metric("Profit Factor", f"{pf:.2f}")
    m4.metric("Net PnL", f"${net:,.2f}")
    m5.metric("Avg R", f"{avg_r:.2f}")

    # Equity curve
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=tdf["time"], y=tdf["cum_pnl"] + bt_bal, mode="lines", name="Equity",
                                 line=dict(color="#00d4aa", width=2), fill="tozeroy",
                                 fillcolor="rgba(0,212,170,0.06)"))
    fig_eq.add_hline(y=bt_bal, line=dict(color="#8b9ab0", width=1, dash="dot"))
    fig_eq.update_layout(template="plotly_dark", height=300, margin=dict(l=8, r=8, t=8, b=8), yaxis_title="Equity (USD)")
    st.plotly_chart(fig_eq, use_container_width=True)

    # Performance by grade
    for g in ["A+", "A", "B", "C", "D"]:
        sub = tdf[tdf["grade"] == g]
        if not sub.empty:
            sw = sub["win"].sum()
            sn = len(sub)
            st.markdown(f"**{g}**: {sn} trades, {sw / sn * 100:.0f}% WR, ${sub['pnl'].sum():.2f} net")

    with st.expander("Full Trade Log"):
        st.dataframe(tdf.drop(columns=["win", "cum_pnl"]), use_container_width=True, hide_index=True)
        st.download_button("Download CSV", tdf.to_csv(index=False).encode(), "backtest.csv", "text/csv")


# ============================================================
# JOURNAL
# ============================================================
JOURNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal.json")

def load_journal() -> List[dict]:
    try:
        if os.path.exists(JOURNAL_FILE):
            with open(JOURNAL_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_journal(journal: List[dict]):
    try:
        with open(JOURNAL_FILE, "w") as f:
            json.dump(journal, f, indent=2)
    except Exception:
        pass

def render_journal():
    cyberpunk_header("TRADE JOURNAL", "Track your performance, learn from every trade")
    j = load_journal()
    if not j:
        st.info("No trades logged yet. Enter a live trade and close it to start recording.")
        return

    total = len(j)
    wins = sum(1 for t in j if t.get("result") == "Win")
    losses = sum(1 for t in j if t.get("result") == "Loss")
    pnls = [t.get("pnl_r", 0) for t in j]
    wr = wins / total * 100 if total else 0
    total_r = sum(pnls)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Trades", total)
    m2.metric("Win Rate", f"{wr:.0f}%")
    m3.metric("W / L", f"{wins} / {losses}")
    m4.metric("Total R", f"{total_r:+.1f}")

    df_j = pd.DataFrame(j)
    if "pnl_r" in df_j.columns:
        df_j["cum_r"] = df_j["pnl_r"].cumsum()
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=list(range(1, len(df_j) + 1)), y=df_j["cum_r"],
                                    mode="lines+markers", name="Cumulative R",
                                    line=dict(color="#00d4aa", width=2)))
        fig_eq.add_hline(y=0, line=dict(color="#8b9ab0", dash="dot", width=1))
        fig_eq.update_layout(plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
                             font=dict(color="#e8edf2"), height=280, margin=dict(t=20, b=20),
                             xaxis_title="Trade #", yaxis_title="Cumulative R")
        st.plotly_chart(fig_eq, use_container_width=True)

    display_cols = [c for c in ["id", "ts", "symbol", "dir", "entry", "sl", "exit", "result", "pnl_r", "grade", "final", "notes"] if c in df_j.columns]
    st.dataframe(df_j[display_cols], use_container_width=True, hide_index=True)
    st.download_button("Export CSV", df_j.to_csv(index=False).encode(), "trade_journal.csv", "text/csv")


# ============================================================
# SIDEBAR + AUTH + MAIN
# ============================================================
# Auth gate
_auth_client = None
if SUPABASE_URL and SUPABASE_KEY:
    _auth_client = SupabaseAuth(SUPABASE_URL, SUPABASE_KEY)
    if not render_auth_page(_auth_client):
        st.stop()

# Initialize session state
if "active_trades" not in st.session_state:
    st.session_state.active_trades = []
if "tg_sent_signals" not in st.session_state:
    st.session_state.tg_sent_signals = {}

# Notification Manager
_notifier = None
if TELEGRAM_BOT_TOKEN and TELEGRAM_PRIVATE_CHANNEL_ID:
    _notifier = NotificationManager(
        bot_token=TELEGRAM_BOT_TOKEN,
        private_channel_id=TELEGRAM_PRIVATE_CHANNEL_ID,
        public_channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
    )

# ── CYBERPUNK SIDEBAR ──
with st.sidebar:
    # Neon logo header
    st.markdown("""
    <div style='text-align:center;padding:16px 0 8px;'>
        <div style='font-family:Orbitron,monospace;font-size:14px;font-weight:900;color:#00fff2;letter-spacing:.2em;
                    text-shadow:0 0 10px rgba(0,255,242,0.6),0 0 20px rgba(0,255,242,0.3);'>
            ALPHA FX HUB
        </div>
        <div style='font-family:Share Tech Mono,monospace;font-size:10px;color:#ff2d7b;letter-spacing:.15em;margin-top:4px;
                    text-shadow:0 0 8px rgba(255,45,123,0.4);'>
            NEON CITY // COMMAND CENTER
        </div>
        <div style='height:2px;background:linear-gradient(90deg,transparent,#00fff2,#ff2d7b,#9d4edd,transparent);margin:10px 0;'></div>
    </div>
    """, unsafe_allow_html=True)

    # Navigation mode selector
    NAV_PAGES = {
        "Dashboard": "⚡",
        "News Intel": "📡",
        "MT5 Analysis": "📊",
        "ARIA Chat": "🤖",
        "Academy": "🎓",
        "Community": "💬",
        "Backtest": "🧪",
        "Journal": "📓",
    }

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Dashboard"

    st.markdown("<div style='font-family:Orbitron,monospace;font-size:9px;color:#9d4edd;letter-spacing:.2em;padding:4px 12px;'>NAVIGATION</div>", unsafe_allow_html=True)

    for page_name, icon in NAV_PAGES.items():
        is_active = st.session_state["nav_page"] == page_name
        if st.button(
            f"{icon}  {page_name.upper()}",
            key=f"nav_{page_name}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state["nav_page"] = page_name
            st.rerun()

    st.markdown("<div style='height:2px;background:linear-gradient(90deg,transparent,#9d4edd,transparent);margin:12px 0;'></div>", unsafe_allow_html=True)

    # Trading settings (shown for Dashboard/Backtest)
    current_page = st.session_state["nav_page"]
    if current_page in ("Dashboard", "Backtest"):
        st.markdown("<div style='font-family:Orbitron,monospace;font-size:9px;color:#00fff2;letter-spacing:.2em;padding:4px 0;'>TRADE CONFIG</div>", unsafe_allow_html=True)
        if current_page == "Dashboard":
            auto_refresh = st.toggle("Auto Refresh", value=True)
            refresh_sec = st.selectbox("Interval (s)", [15, 30, 60, 120], index=1)
            if auto_refresh and st_autorefresh:
                st_autorefresh(interval=int(refresh_sec) * 1000, key="ar_v12")
        symbol = st.selectbox("Symbol", INTERNAL_SYMBOLS, index=INTERNAL_SYMBOLS.index("XAUUSD") if "XAUUSD" in INTERNAL_SYMBOLS else 0)
        interval_label = st.selectbox("Interval", list(INTERVAL_MAP.keys()), index=2)
        bars = st.slider("Bars", 220, 1000, 400, 20)
        balance = st.number_input("Balance (USD)", min_value=10.0, value=500.0, step=50.0)
        risk_pct = st.number_input("Risk %", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    else:
        symbol = "XAUUSD"
        interval_label = "15 Min"
        bars = 400
        balance = 500.0
        risk_pct = 1.0

    st.markdown("<div style='height:2px;background:linear-gradient(90deg,transparent,#ff2d7b,transparent);margin:12px 0;'></div>", unsafe_allow_html=True)

    # API Keys section
    with st.expander("🔑 API KEYS", expanded=False):
        _td = st.text_input("Twelve Data", value=st.session_state.get("td_key", _ENV_TD), type="password", key="td_inp", placeholder="paste key...")
        _xai = st.text_input("xAI Grok", value=st.session_state.get("xai_key", _ENV_XAI), type="password", key="xai_inp", placeholder="paste key...")
        if _td:
            st.session_state["td_key"] = _td
        if _xai:
            st.session_state["xai_key"] = _xai
        _GROK_MODELS = ["grok-4-1-fast-non-reasoning", "grok-4-1-fast-reasoning", "grok-4.20-0309-non-reasoning"]
        _gm = st.selectbox("Grok Model", _GROK_MODELS, index=0, key="grok_model_sel")
        st.session_state["grok_model"] = _gm
        td_ok = "✅" if _td else "❌"
        xai_ok = "✅" if _xai else "❌"
        st.markdown(f"<div style='font-size:11px;color:#8b9ab0;font-family:Share Tech Mono,monospace;'>{td_ok} TD &nbsp; {xai_ok} xAI</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if _xai and c1.button("Test Grok"):
            ok, msg = test_grok_connection(_xai)
            (st.success if ok else st.error)(msg)
        if _xai and c2.button("List Models"):
            try:
                _r = requests.get("https://api.x.ai/v1/models",
                                  headers={"Authorization": f"Bearer {_xai}"}, timeout=10)
                if _r.status_code == 200:
                    _ids = [m["id"] for m in _r.json().get("data", [])]
                    st.success("Available: " + ", ".join(_ids) if _ids else "No models returned")
                else:
                    st.error(f"HTTP {_r.status_code}: {_r.text[:120]}")
            except Exception as e:
                st.error(str(e))

    # MT5 section
    with st.expander("📡 MT5 LIVE", expanded=False):
        _ma_tok = st.text_input("MetaApi Token", value=st.session_state.get("ma_token", ""), type="password", key="ma_tok_inp")
        _ma_acc = st.text_input("Account ID", value=st.session_state.get("ma_account", ""), key="ma_acc_inp")
        _ma_sfx = st.text_input("Symbol suffix", value=st.session_state.get("ma_sym_suffix", ".r"), key="ma_sfx_inp")
        if _ma_tok:
            st.session_state["ma_token"] = _ma_tok
        if _ma_acc:
            st.session_state["ma_account"] = _ma_acc
        st.session_state["ma_sym_suffix"] = _ma_sfx
        _mab1, _mab2 = st.columns(2)
        if _ma_tok and _ma_acc and _mab1.button("Test MT5"):
            _ok, _msg = test_mt5_connection(_ma_tok, _ma_acc)
            (st.success if _ok else st.error)(_msg)
        if _ma_tok and _ma_acc and _mab2.button("Deploy"):
            _ok, _msg = deploy_mt5_account(_ma_tok, _ma_acc)
            (st.success if _ok else st.error)(_msg)

    # Logout
    if st.session_state.get("user"):
        st.markdown("<div style='height:2px;background:linear-gradient(90deg,transparent,#39ff14,transparent);margin:12px 0;'></div>", unsafe_allow_html=True)
        user = st.session_state.user
        user_email = user.get("email", "User")
        st.markdown(f"<div style='color:#8b9ab0;font-size:11px;font-family:Share Tech Mono,monospace;'>Logged in as:<br><strong style='color:#39ff14;text-shadow:0 0 6px rgba(57,255,20,0.4);'>{user_email}</strong></div>", unsafe_allow_html=True)
        if st.button("⚡ Logout", use_container_width=True):
            if _auth_client:
                _auth_client.sign_out(st.session_state.get("access_token", ""))
            for k in ["access_token", "refresh_token", "user"]:
                st.session_state.pop(k, None)
            _clear_browser_session()
            st.rerun()

    # ARIA anime avatar in sidebar
    st.markdown("""
    <div style='text-align:center;padding:16px 0 8px;'>
        <div style='display:inline-block;width:60px;height:60px;border-radius:50%;
                    border:2px solid #ff2d7b;box-shadow:0 0 15px rgba(255,45,123,0.4);
                    background:linear-gradient(135deg,#1a1a3e,#0d0b1e);
                    display:flex;align-items:center;justify-content:center;margin:0 auto;'>
            <span style='font-size:28px;'>🌸</span>
        </div>
        <div style='font-family:Orbitron,monospace;font-size:9px;color:#ff2d7b;letter-spacing:.15em;margin-top:6px;
                    text-shadow:0 0 6px rgba(255,45,123,0.4);'>
            A.R.I.A // ONLINE
        </div>
        <div style='font-size:8px;color:#8b9ab0;font-family:Share Tech Mono,monospace;'>
            AI Research & Intelligence Assistant
        </div>
    </div>
    """, unsafe_allow_html=True)

interval = INTERVAL_MAP[interval_label]

# ── ANIME AI ASSISTANT FLOATING ELEMENT ──
st.markdown("""
<div class='aria-avatar' title='ARIA - Your AI Trading Assistant'>
    🌸
</div>
""", unsafe_allow_html=True)

# ── MAIN PAGE ROUTING ──
if current_page == "Dashboard":
    render_live(symbol, interval, bars, balance, risk_pct, _notifier)

elif current_page == "News Intel":
    cyberpunk_header("NEWS INTELLIGENCE", "Real-time market intel powered by ARIA")
    _grok_key = get_xai_key()
    _te_key = TE_API_KEY
    render_news_dashboard(_grok_key, _te_key)

elif current_page == "MT5 Analysis":
    cyberpunk_header("MT5 TRADE ANALYSIS", "Deep-dive into your trading performance")
    _ma_tok_val = get_ma_token()
    _ma_acc_val = get_ma_account()
    _grok_key = get_xai_key()
    render_mt5_analysis(_ma_tok_val, _ma_acc_val, _grok_key)

elif current_page == "ARIA Chat":
    cyberpunk_header("A.R.I.A", "AI Research & Intelligence Assistant")
    _grok_key = get_xai_key()
    render_aria_chat(_grok_key)

elif current_page == "Academy":
    cyberpunk_header("TRADING ACADEMY", "Level up your trading skills")
    render_academy()

elif current_page == "Community":
    cyberpunk_header("COMMUNITY NEXUS", "Share trades, learn together")
    render_forum()

elif current_page == "Backtest":
    render_backtest(get_td_key())

elif current_page == "Journal":
    render_journal()
