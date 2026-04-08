#!/usr/bin/env python3
"""
Alpha FX Hub — Standalone Signal Scanner Bot
Runs independently of Streamlit. Scans all symbols, sends Telegram for A/A+ signals.
"""
import os, json, requests, time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# ── Config (reads from environment or .secrets file) ──
def _load_secrets():
    """Load secrets from .secrets file if it exists."""
    secrets_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secrets")
    if os.path.exists(secrets_file):
        with open(secrets_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

_load_secrets()

TD_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
XAI_KEY = os.environ.get("GROK_API_KEY", "") or os.environ.get("XAI_API_KEY", "")
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHANNEL = os.environ.get("TELEGRAM_PRIVATE_CHANNEL_ID", "")
TG_PUBLIC = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID", "")
TE_KEY = os.environ.get("TE_API_KEY", "")

SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
API_MAP = {"EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
           "XAUUSD": "XAU/USD", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
           "USDCHF": "USD/CHF"}
PIP_MAP = {"USDJPY": 0.01, "XAUUSD": 0.1}
PIP_VAL = {"USDJPY": 9.1, "XAUUSD": 10.0}
FOREX = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "AUDUSD", "USDCAD"}
SESSIONS_PREF = {
    "EURUSD": ["London", "Overlap", "NewYork"],
    "GBPUSD": ["London", "Overlap", "NewYork"],
    "USDJPY": ["Asian", "London", "Overlap"],
    "XAUUSD": ["London", "Overlap", "NewYork"],
    "AUDUSD": ["Asian", "London"],
    "USDCAD": ["NewYork", "Overlap"],
}

# ── Trading Economics — News Filter ──
# Which currencies affect each symbol
SYMBOL_CURRENCIES = {
    "XAUUSD": ["USD", "EUR", "GBP", "JPY", "CNY"],  # Gold reacts to all major
    "EURUSD": ["USD", "EUR"],
    "GBPUSD": ["USD", "GBP"],
    "USDJPY": ["USD", "JPY"],
    "AUDUSD": ["USD", "AUD"],
    "USDCAD": ["USD", "CAD"],
}
HIGH_IMPACT_EVENTS = [
    "Interest Rate Decision", "Fed Interest Rate Decision",
    "Non Farm Payrolls", "CPI", "Core CPI", "PPI", "Core PPI",
    "GDP Growth Rate", "Unemployment Rate", "Initial Jobless Claims",
    "Retail Sales", "ISM Manufacturing PMI", "ISM Services PMI",
    "FOMC Minutes", "Fed Chair Powell Speech",
    "ECB Interest Rate Decision", "BOE Interest Rate Decision",
    "BOJ Interest Rate Decision", "Trade Balance",
    "Consumer Confidence", "Durable Goods Orders",
    "PCE Price Index", "Core PCE Price Index",
]
_news_cache = {"data": None, "ts": None}

def fetch_economic_calendar():
    """Fetch today's economic events from Trading Economics."""
    if not TE_KEY:
        return []
    # Cache for 30 min to avoid rate limits
    now = datetime.utcnow()
    if _news_cache["data"] is not None and _news_cache["ts"]:
        if (now - _news_cache["ts"]).total_seconds() < 1800:
            return _news_cache["data"]
    try:
        today = now.strftime("%Y-%m-%d")
        parts = TE_KEY.split(":")
        if len(parts) == 2:
            auth = (parts[0], parts[1])  # Trading Economics uses basic auth
        else:
            auth = None
        url = f"https://api.tradingeconomics.com/calendar?c={TE_KEY}&d1={today}&d2={today}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            events = r.json() if isinstance(r.json(), list) else []
            _news_cache["data"] = events
            _news_cache["ts"] = now
            return events
        else:
            print(f"  TE Calendar: HTTP {r.status_code}")
            return []
    except Exception as e:
        print(f"  TE Calendar error: {e}")
        return []

def check_news_danger(symbol, events):
    """
    Check if high-impact news is within ±30 min window for this symbol.
    Returns: (danger_level, event_name)
      danger_level: 0 = safe, -10 = medium risk, -15 = high risk (skip trade)
    """
    if not events:
        return 0, None
    now = datetime.utcnow()
    affected_currencies = SYMBOL_CURRENCIES.get(symbol, ["USD"])

    for ev in events:
        try:
            ev_country = ev.get("Country", "")
            ev_currency = ev.get("Currency", ev_country)
            ev_name = ev.get("Event", "")
            ev_importance = ev.get("Importance", 0)
            ev_date_str = ev.get("Date", "")

            # Only care about currencies that affect this symbol
            if ev_currency not in affected_currencies:
                continue

            # Parse event time
            if ev_date_str:
                ev_time = pd.to_datetime(ev_date_str, utc=True, errors="coerce")
                if pd.isna(ev_time):
                    continue
                ev_time = ev_time.to_pydatetime().replace(tzinfo=None)
            else:
                continue

            mins_until = (ev_time - now).total_seconds() / 60

            # Check if event is within danger window (30 min before to 15 min after)
            if -15 <= mins_until <= 30:
                # High-impact named events = full danger
                is_high_impact = any(hi.lower() in ev_name.lower() for hi in HIGH_IMPACT_EVENTS)
                if is_high_impact or ev_importance >= 3:
                    return -15, f"⚠️ {ev_name} ({ev_currency}) in {int(mins_until)}min"
                elif ev_importance >= 2:
                    return -10, f"⚡ {ev_name} ({ev_currency}) in {int(mins_until)}min"
        except Exception:
            continue

    return 0, None

# Cooldown tracker
_sent = {}
MIN_GRADE = "A"  # A and A+ trigger alerts
MIN_SCORE = 80


def pip_size(s): return PIP_MAP.get(s, 0.0001)
def pip_value(s): return PIP_VAL.get(s, 10.0)

def fmt_price(v, sym=""):
    if v is None: return "—"
    s = sym.upper().replace("/", "")
    return f"{float(v):.3f}" if s in ("USDJPY", "XAUUSD") else f"{float(v):.5f}"


# ── Data ──
def fetch_bars(symbol, interval="15min", bars=260):
    api_sym = API_MAP.get(symbol, symbol)
    url = f"https://api.twelvedata.com/time_series"
    r = requests.get(url, params={"symbol": api_sym, "interval": interval,
                                   "outputsize": bars, "timezone": "UTC",
                                   "order": "ASC", "apikey": TD_KEY}, timeout=20)
    data = r.json()
    if data.get("status") == "error":
        raise ValueError(data.get("message", "Twelve Data error"))
    values = data.get("values", [])
    if not values:
        raise ValueError("No bars")
    df = pd.DataFrame(values)
    col = "datetime" if "datetime" in df.columns else "date"
    df["time"] = pd.to_datetime(df[col], utc=True, errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("time").dropna(subset=["time", "open", "high", "low", "close"]).reset_index(drop=True)


def add_indicators(df):
    x = df.copy()
    x["ema20"] = x["close"].ewm(span=20, adjust=False).mean()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200, adjust=False).mean()
    tr = pd.concat([x["high"] - x["low"],
                    (x["high"] - x["close"].shift()).abs(),
                    (x["low"] - x["close"].shift()).abs()], axis=1).max(axis=1)
    x["atr14"] = tr.rolling(14).mean()
    delta = x["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    x["rsi14"] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)))
    ema12 = x["close"].ewm(span=12, adjust=False).mean()
    ema26 = x["close"].ewm(span=26, adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["macd_sig"] = x["macd"].ewm(span=9, adjust=False).mean()
    x["macd_hist"] = x["macd"] - x["macd_sig"]
    x["bb_mid"] = x["close"].rolling(20).mean()
    bb_std = x["close"].rolling(20).std()
    x["bb_upper"] = x["bb_mid"] + 2 * bb_std
    x["bb_lower"] = x["bb_mid"] - 2 * bb_std
    x["bb_width"] = (x["bb_upper"] - x["bb_lower"]) / x["bb_mid"]
    x["slope20"] = x["ema20"].diff(5)
    body = (x["close"] - x["open"]).abs()
    full_range = x["high"] - x["low"]
    upper = x["high"] - x[["close", "open"]].max(axis=1)
    lower = x[["close", "open"]].min(axis=1) - x["low"]
    # Classic patterns (strict)
    x["pin_bull"] = (lower > 2 * body) & (upper < 0.3 * body)
    x["pin_bear"] = (upper > 2 * body) & (lower < 0.3 * body)
    x["engulf_bull"] = (x["close"] > x["open"]) & (x["close"].shift() <= x["open"].shift()) & \
                       (x["close"] > x["open"].shift()) & (x["open"] < x["close"].shift())
    x["engulf_bear"] = (x["close"] < x["open"]) & (x["close"].shift() >= x["open"].shift()) & \
                       (x["close"] < x["open"].shift()) & (x["open"] > x["close"].shift())
    # Additional patterns (relaxed)
    x["hammer"] = (lower > 1.5 * body) & (upper < 0.5 * body) & (body > 0)
    x["shooting_star"] = (upper > 1.5 * body) & (lower < 0.5 * body) & (body > 0)
    x["doji"] = body < (full_range * 0.1)  # Very small body
    x["bull_candle"] = (x["close"] > x["open"]) & (body > full_range * 0.6)  # Strong bullish
    x["bear_candle"] = (x["close"] < x["open"]) & (body > full_range * 0.6)  # Strong bearish
    # Momentum candles (3-bar)
    x["three_bull"] = (x["close"] > x["open"]) & (x["close"].shift(1) > x["open"].shift(1)) & \
                      (x["close"].shift(2) > x["open"].shift(2))
    x["three_bear"] = (x["close"] < x["open"]) & (x["close"].shift(1) < x["open"].shift(1)) & \
                      (x["close"].shift(2) < x["open"].shift(2))
    return x


def trend_bias(df):
    r = df.iloc[-1]
    if r["ema20"] > r["ema50"] > r["ema200"] and r["macd_hist"] > 0: return "bull"
    if r["ema20"] < r["ema50"] < r["ema200"] and r["macd_hist"] < 0: return "bear"
    return "neutral"


def session_score(symbol, ts):
    h = ts.hour
    preferred = SESSIONS_PREF.get(symbol, ["London", "NewYork"])
    if 12 <= h < 16 and "Overlap" in preferred: return 10, "Overlap"
    if 7 <= h < 16 and "London" in preferred: return 7, "London"
    if 12 <= h < 21 and "NewYork" in preferred: return 7, "NewYork"
    if (h >= 22 or h < 7) and "Asian" in preferred: return 5, "Asian"
    return 3, "Off-peak"


# ── Scoring (V12 recalibrated 8-component, max 100) ──
# EMA(20) + Pullback(15) + MACD(15) + RSI(10) + Candle(10) + R:R(15) + Session(10) + Momentum(5)
def score_setup(row, prev, df, direction, rr, symbol):
    bd = {}

    # 1. EMA Stack (max 20) — full stack, partial, or at least 20>50
    if direction == "Buy":
        if row["ema20"] > row["ema50"] > row["ema200"]:
            bd["EMA"] = 20
        elif row["ema20"] > row["ema50"]:
            bd["EMA"] = 14
        elif row["close"] > row["ema20"]:
            bd["EMA"] = 8
        else:
            bd["EMA"] = 0
    else:
        if row["ema20"] < row["ema50"] < row["ema200"]:
            bd["EMA"] = 20
        elif row["ema20"] < row["ema50"]:
            bd["EMA"] = 14
        elif row["close"] < row["ema20"]:
            bd["EMA"] = 8
        else:
            bd["EMA"] = 0

    # 2. Pullback quality (max 15) — relaxed thresholds
    dist = abs(row["close"] - row["ema20"]) / max(row["atr14"], 1e-9)
    bd["Pullback"] = 15 if dist <= 0.5 else 12 if dist <= 0.8 else 8 if dist <= 1.2 else 4 if dist <= 2.0 else 0

    # 3. MACD confirmation (max 15) — more partial credit
    if direction == "Buy":
        if row["macd_hist"] > 0 and row["macd_hist"] > prev["macd_hist"]:
            bd["MACD"] = 15  # Positive & accelerating
        elif row["macd_hist"] > 0:
            bd["MACD"] = 10  # Positive
        elif row["macd"] > row["macd_sig"]:
            bd["MACD"] = 5   # MACD above signal (early cross)
        else:
            bd["MACD"] = 0
    else:
        if row["macd_hist"] < 0 and row["macd_hist"] < prev["macd_hist"]:
            bd["MACD"] = 15
        elif row["macd_hist"] < 0:
            bd["MACD"] = 10
        elif row["macd"] < row["macd_sig"]:
            bd["MACD"] = 5
        else:
            bd["MACD"] = 0

    # 4. RSI confirmation (max 10) — wider ranges
    rsi = row["rsi14"]
    if direction == "Buy":
        bd["RSI"] = 10 if 40 <= rsi <= 65 else 7 if 30 <= rsi <= 75 else 3 if rsi < 30 else 0
    else:
        bd["RSI"] = 10 if 35 <= rsi <= 60 else 7 if 25 <= rsi <= 70 else 3 if rsi > 70 else 0

    # 5. Candle pattern (max 10) — many more patterns recognized
    candle = 0
    if direction == "Buy":
        if row.get("pin_bull") or row.get("engulf_bull"):
            candle = 10  # Strong pattern
        elif row.get("hammer") or row.get("bull_candle") or row.get("three_bull"):
            candle = 7   # Good pattern
        elif row["close"] > row["open"]:
            candle = 3   # At least bullish candle
    else:
        if row.get("pin_bear") or row.get("engulf_bear"):
            candle = 10
        elif row.get("shooting_star") or row.get("bear_candle") or row.get("three_bear"):
            candle = 7
        elif row["close"] < row["open"]:
            candle = 3   # At least bearish candle
    bd["Candle"] = candle

    # 6. Risk:Reward (max 15) — more partial credit
    bd["R:R"] = 15 if rr >= 2.5 else 12 if rr >= 2.0 else 10 if rr >= 1.5 else 7 if rr >= 1.2 else 4 if rr >= 1.0 else 0

    # 7. Session timing (max 10)
    sess_pts, sess_name = session_score(symbol, row.get("time", pd.Timestamp.utcnow()))
    bd["Session"] = sess_pts

    # 8. Momentum bonus (max 5) — trend strength from slope
    slope = row.get("slope20", 0)
    if slope and not pd.isna(slope):
        slope_norm = abs(slope) / max(row["atr14"], 1e-9)
        if direction == "Buy" and slope > 0:
            bd["Momentum"] = 5 if slope_norm > 0.3 else 3 if slope_norm > 0.1 else 0
        elif direction == "Sell" and slope < 0:
            bd["Momentum"] = 5 if slope_norm > 0.3 else 3 if slope_norm > 0.1 else 0
        else:
            bd["Momentum"] = 0
    else:
        bd["Momentum"] = 0

    total = min(sum(bd.values()), 100)
    confluence = sum(1 for k, v in bd.items() if k not in ("Session", "Momentum") and v > 0)
    return total, bd, confluence, sess_name


def get_regime(df):
    if len(df) < 220: return "insufficient"
    r = df.iloc[-1]
    if pd.isna(r["atr14"]) or r["atr14"] <= 0: return "insufficient"
    if r["ema20"] > r["ema50"] > r["ema200"]: return "trend_up"
    if r["ema20"] < r["ema50"] < r["ema200"]: return "trend_down"
    if r["ema20"] > r["ema50"] and r["slope20"] > 0: return "trend_up"
    if r["ema20"] < r["ema50"] and r["slope20"] < 0: return "trend_down"
    if r["bb_width"] < 0.005: return "squeeze"
    if 40 <= r["rsi14"] <= 60: return "range"
    return "mean_revert"


def score_to_grade(s):
    if s >= 90: return "A+"
    if s >= 80: return "A"
    if s >= 70: return "B"
    if s >= 60: return "C"
    return "D"


def scan_symbol(symbol, events=None):
    """Scan one symbol. Returns (score, grade, direction, strategy, details) or None."""
    try:
        df = add_indicators(fetch_bars(symbol, "15min", 260))
        if len(df) < 220:
            return None

        regime = get_regime(df)
        if regime == "insufficient":
            return None

        row = df.iloc[-1]
        prev = df.iloc[-2]
        atr = row["atr14"]
        close = row["close"]
        ema20 = row["ema20"]

        if pd.isna(atr) or atr <= 0:
            return None

        # ── News danger check ──
        news_penalty, news_event = check_news_danger(symbol, events or [])

        # Determine direction based on regime
        if regime in ("trend_up", "trend_down"):
            direction = "Buy" if regime == "trend_up" else "Sell"
            strategy = "Trend Continuation"
        elif regime == "squeeze":
            if row["close"] > row["bb_upper"] and row["macd_hist"] > 0:
                direction = "Buy"
            elif row["close"] < row["bb_lower"] and row["macd_hist"] < 0:
                direction = "Sell"
            else:
                return None
            strategy = "BB Squeeze"
        else:
            dev = (close - ema20) / atr
            if abs(dev) < 0.8:
                return None
            direction = "Sell" if dev > 0 else "Buy"
            strategy = "Mean Reversion"

        # Calculate entry/SL/TP
        if direction == "Buy":
            entry = close
            sl = min(df.tail(6)["low"].min(), ema20 - 0.5 * atr)
            risk = entry - sl
            tp1 = entry + risk
            tp2 = entry + 2.0 * risk
        else:
            entry = close
            sl = max(df.tail(6)["high"].max(), ema20 + 0.5 * atr)
            risk = sl - entry
            tp1 = entry - risk
            tp2 = entry - 2.0 * risk

        rr = abs(tp2 - entry) / max(abs(entry - sl), 1e-9)
        score, breakdown, confluence, sess_name = score_setup(row, prev, df, direction, rr, symbol)

        # ── MTF alignment bonus (up to +15) ──
        # Check if higher timeframe (using EMA alignment depth) confirms direction
        if direction == "Buy":
            if row["ema20"] > row["ema50"] > row["ema200"]:
                breakdown["MTF"] = 15  # Full alignment
            elif row["ema20"] > row["ema50"]:
                breakdown["MTF"] = 8   # Partial
            else:
                breakdown["MTF"] = 0
        else:
            if row["ema20"] < row["ema50"] < row["ema200"]:
                breakdown["MTF"] = 15
            elif row["ema20"] < row["ema50"]:
                breakdown["MTF"] = 8
            else:
                breakdown["MTF"] = 0
        score = min(100, score + breakdown["MTF"])

        # ── Liquidity sweep bonus (up to +10) ──
        rh = df.iloc[-6:-1]["high"].max()
        rl = df.iloc[-6:-1]["low"].min()
        bull_sweep = row["low"] < rl and row["close"] > rl
        bear_sweep = row["high"] > rh and row["close"] < rh
        if (direction == "Buy" and bull_sweep) or (direction == "Sell" and bear_sweep):
            breakdown["Sweep"] = 10
            score = min(100, score + 10)
        else:
            breakdown["Sweep"] = 0

        # ── Apply news penalty to final score ──
        if news_penalty != 0:
            breakdown["News"] = news_penalty
            score = max(0, min(100, score + news_penalty))
            print(f"    {symbol}: News penalty {news_penalty} → {news_event}")

        grade = score_to_grade(score)

        return {
            "symbol": symbol,
            "score": score,
            "grade": grade,
            "direction": direction,
            "strategy": strategy,
            "regime": regime,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "rr": rr,
            "confluence": confluence,
            "session": sess_name,
            "rsi": float(row["rsi14"]),
            "breakdown": breakdown,
            "news_warning": news_event,
        }
    except Exception as e:
        print(f"  [{symbol}] Error: {e}")
        return None


# ── Telegram ──
def send_telegram(msg, channel_id=None):
    if not TG_BOT_TOKEN:
        print("  No Telegram bot token")
        return False
    cid = channel_id or TG_CHANNEL
    if not cid:
        print("  No channel ID")
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=10)
        if r.status_code == 200:
            print(f"  Telegram sent to {cid}")
            return True
        else:
            print(f"  Telegram failed: {r.status_code} {r.text[:100]}")
            return False
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False


def format_signal_msg(sig):
    icon = "🟢" if sig["direction"] == "Buy" else "🔴"
    news_line = ""
    if sig.get("news_warning"):
        news_line = f"\n🗞️ <b>NEWS:</b> {sig['news_warning']}\n"
    return (
        f"{icon} <b>{sig['grade']} SIGNAL — {sig['symbol']}</b>\n\n"
        f"Direction: <b>{sig['direction']}</b>\n"
        f"Score: <b>{sig['score']}/100 ({sig['grade']})</b>\n"
        f"Strategy: {sig['strategy']}\n"
        f"Regime: {sig['regime']}\n"
        f"Confluence: {sig['confluence']}/6\n\n"
        f"Entry: <code>{fmt_price(sig['entry'], sig['symbol'])}</code>\n"
        f"SL: <code>{fmt_price(sig['sl'], sig['symbol'])}</code>\n"
        f"TP1: <code>{fmt_price(sig['tp1'], sig['symbol'])}</code>\n"
        f"TP2: <code>{fmt_price(sig['tp2'], sig['symbol'])}</code>\n"
        f"R:R: 1:{sig['rr']:.2f}\n"
        f"RSI: {sig['rsi']:.1f}\n"
        f"Session: {sig['session']}\n"
        f"{news_line}\n"
        f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"📊 Alpha FX Hub"
    )


# ── Market-Wide Sentiment (crash/panic detection) ──
_SENTIMENT_SYMBOLS = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "XAUUSD"]

def get_market_sentiment():
    """Check all major pairs for market-wide risk-off / risk-on."""
    bearish = 0
    bullish = 0
    details = {}

    for sym in _SENTIMENT_SYMBOLS:
        try:
            api_sym = API_MAP.get(sym, sym[:3]+"/"+sym[3:])
            resp = requests.get("https://api.twelvedata.com/time_series", params={
                "symbol": api_sym, "interval": "15min", "outputsize": 60,
                "timezone": "UTC", "order": "ASC", "apikey": TD_KEY
            }, timeout=12)
            v = resp.json().get("values", [])
            if len(v) < 30:
                details[sym] = "INSUFFICIENT"
                continue
            closes = [float(r["close"]) for r in v]
            highs = [float(r["high"]) for r in v]
            lows = [float(r["low"]) for r in v]

            # EMA20, EMA50
            c = pd.Series(closes)
            ema20 = c.ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = c.ewm(span=50, adjust=False).mean().iloc[-1]
            ema20_prev = c.ewm(span=20, adjust=False).mean().iloc[-3]
            price = closes[-1]

            # RSI14
            delta = c.diff()
            gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
            loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
            rsi = 100 - (100 / (1 + gain / max(loss, 1e-9)))

            # MACD histogram
            ema12 = c.ewm(span=12, adjust=False).mean()
            ema26 = c.ewm(span=26, adjust=False).mean()
            macd_h = float((ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1])
            macd_h = float((ema12 - ema26).iloc[-1]) - macd_h

            below_ema20 = price < ema20
            below_ema50 = price < ema50
            ema20_falling = ema20 < ema20_prev
            rsi_oversold = rsi < 40
            macd_bearish = macd_h < 0
            bear_signals = sum([below_ema20, below_ema50, ema20_falling, rsi_oversold, macd_bearish])
            bull_signals = sum([not below_ema20, not below_ema50, not ema20_falling, rsi > 60, macd_h > 0])

            is_usd_quote = sym in ("USDJPY", "USDCHF", "USDCAD")

            if is_usd_quote:
                if bull_signals >= 3:
                    bearish += 1
                    details[sym] = "USD_STRONG"
                elif bear_signals >= 3:
                    bullish += 1
                    details[sym] = "USD_WEAK"
                else:
                    details[sym] = "NEUTRAL"
            elif sym == "XAUUSD":
                if bull_signals >= 3:
                    bearish += 1
                    details[sym] = "GOLD_RALLY"
                elif bear_signals >= 3:
                    bullish += 1
                    details[sym] = "GOLD_SELL"
                else:
                    details[sym] = "NEUTRAL"
            else:
                if bear_signals >= 3:
                    bearish += 1
                    details[sym] = "BEARISH"
                elif bull_signals >= 3:
                    bullish += 1
                    details[sym] = "BULLISH"
                else:
                    details[sym] = "NEUTRAL"
            time.sleep(0.5)
        except Exception as e:
            details[sym] = f"ERR:{e}"

    if bearish >= 5:
        return {"sentiment": "RISK_OFF", "penalty_buy": -20, "penalty_sell": 0, "bearish": bearish, "bullish": bullish, "details": details}
    elif bearish >= 4:
        return {"sentiment": "RISK_OFF", "penalty_buy": -12, "penalty_sell": 0, "bearish": bearish, "bullish": bullish, "details": details}
    elif bullish >= 5:
        return {"sentiment": "RISK_ON", "penalty_buy": 0, "penalty_sell": -20, "bearish": bearish, "bullish": bullish, "details": details}
    elif bullish >= 4:
        return {"sentiment": "RISK_ON", "penalty_buy": 0, "penalty_sell": -12, "bearish": bearish, "bullish": bullish, "details": details}
    return {"sentiment": "MIXED", "penalty_buy": 0, "penalty_sell": 0, "bearish": bearish, "bullish": bullish, "details": details}


# ── Main Scanner ──
def run_scan():
    print(f"\n{'='*50}")
    print(f"ALPHA FX SCANNER — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*50}")

    if not TD_KEY:
        print("ERROR: No TWELVE_DATA_API_KEY set")
        return

    # Check if forex market is open
    now = pd.Timestamp.utcnow()
    wd = now.weekday()
    if wd == 5:  # Saturday
        print("Market closed (Saturday)")
        return
    if wd == 6 and now.hour < 22:  # Sunday before 22:00
        print("Market closed (Sunday)")
        return

    # Fetch economic calendar once (cached 30 min)
    events = fetch_economic_calendar()
    if events:
        print(f"  Loaded {len(events)} economic events for today")
    elif TE_KEY:
        print(f"  No economic events loaded (API issue or no events today)")
    else:
        print(f"  No TE_API_KEY — skipping news filter")

    # Market-wide sentiment check
    print(f"\n  Checking market-wide sentiment...")
    mkt = get_market_sentiment()
    print(f"  Market Sentiment: {mkt['sentiment']} (Bearish:{mkt['bearish']}/7, Bullish:{mkt['bullish']}/7)")
    for s_sym, s_detail in mkt["details"].items():
        print(f"    {s_sym}: {s_detail}")
    if mkt["sentiment"] == "RISK_OFF":
        print(f"  ⚠️ RISK-OFF detected — Buy signals penalized by {mkt['penalty_buy']}")
    elif mkt["sentiment"] == "RISK_ON":
        print(f"  ⚠️ RISK-ON detected — Sell signals penalized by {mkt['penalty_sell']}")

    signals = []
    for sym in SYMBOLS:
        print(f"  Scanning {sym}...")
        result = scan_symbol(sym, events)
        if result:
            # Apply market sentiment penalty
            if result["direction"] == "Buy":
                result["score"] = max(0, min(100, result["score"] + mkt["penalty_buy"]))
            elif result["direction"] == "Sell":
                result["score"] = max(0, min(100, result["score"] + mkt["penalty_sell"]))
            result["grade"] = score_to_grade(result["score"])
            if mkt["sentiment"] != "MIXED":
                result["breakdown"]["MKT"] = mkt["penalty_buy"] if result["direction"] == "Buy" else mkt["penalty_sell"]

            bd_str = " | ".join(f"{k}:{v}" for k, v in result["breakdown"].items())
            print(f"    {sym}: {result['direction']} | Score {result['score']} ({result['grade']}) | {result['strategy']}")
            print(f"      Breakdown: {bd_str}")
            signals.append(result)
        else:
            print(f"    {sym}: No setup")
        time.sleep(1)  # Rate limit

    # Filter for A/A+ signals
    alerts = [s for s in signals if s["score"] >= MIN_SCORE]

    if not alerts:
        print(f"\nNo A/A+ signals found ({len(signals)} total setups scanned)")
        return

    print(f"\n{'!'*50}")
    print(f"  {len(alerts)} ALERT(S) FOUND!")
    print(f"{'!'*50}")

    for sig in alerts:
        # Cooldown check (30 min per symbol+direction)
        cooldown_key = f"{sig['symbol']}_{sig['direction']}"
        now_ts = datetime.utcnow()
        if cooldown_key in _sent:
            elapsed = (now_ts - _sent[cooldown_key]).total_seconds()
            if elapsed < 1800:  # 30-min cooldown
                print(f"  [{sig['symbol']}] Cooldown ({int(1800 - elapsed)}s remaining)")
                continue

        msg = format_signal_msg(sig)
        # Send to private channel
        if send_telegram(msg, TG_CHANNEL):
            _sent[cooldown_key] = now_ts
        # Also send to public channel
        if TG_PUBLIC:
            send_telegram(msg, TG_PUBLIC)

    print(f"\nScan complete. Next run in 5 minutes.")


if __name__ == "__main__":
    run_scan()
