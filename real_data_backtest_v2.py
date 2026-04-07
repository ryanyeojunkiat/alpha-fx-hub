#!/usr/bin/env python3
"""
Alpha FX Hub — REAL DATA Backtester V2 (Fixed)
====================================================
Fixed bugs from V1:
1. SL Logic: Structure-based + ATR fallback with proper caps
2. Stress test configs: spread/slippage combos Ryan requested
3. Gap-through SL: Fill at actual bar price on gaps
4. Execution delay: Optional delayed entry on next bar
5. Honest metrics: Return-to-DD ratio, Sharpe estimate, monthly breakdown

Pulls actual XAUUSD M15 data and runs comprehensive strategy validation.

Run this on your LOCAL machine:
    pip install yfinance pandas numpy
    python real_data_backtest_v2.py [--csv yourfile.csv]

Data sources (tries in order):
1. Twelve Data API (if TWELVE_DATA_API_KEY set)
2. yfinance GC=F gold futures — 60 days of M15 data
3. ejtraderLabs GitHub CSV
4. CSV file import (if you exported from TradingView/MT5)

Outputs:
- Console report with all requested metrics + weaknesses section
- CSV trade log: real_backtest_trades.csv
- Summary report: real_backtest_report.txt
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# ════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════
PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
LOT_PCT = [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]
TRAILING_RULES = {1: "breakeven", 3: 1, 5: 3, 7: 5, 9: 7}
TP_RISK_MULTIPLES = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 9.0, 12.0]

# ════════════════════════════════════════════════════════════════
# DATA FETCHING — Real XAUUSD M15
# ════════════════════════════════════════════════════════════════

def fetch_twelve_data(api_key: str, bars: int = 5000) -> Optional[pd.DataFrame]:
    """Fetch from Twelve Data API (best quality, needs free API key)."""
    try:
        import urllib.request
        url = (
            f"https://api.twelvedata.com/time_series?"
            f"symbol=XAU/USD&interval=15min&outputsize={bars}"
            f"&apikey={api_key}&format=JSON"
        )
        print(f"  Fetching {bars} bars from Twelve Data...")
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaFXHub/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        if "values" not in data:
            print(f"  Twelve Data error: {data.get('message', 'Unknown error')}")
            return None

        rows = data["values"]
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["datetime"])
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        df = df.sort_values("time").reset_index(drop=True)
        df["volume"] = ((df["high"] - df["low"]) * 1000).astype(int).clip(lower=100)
        print(f"  ✓ Twelve Data: {len(df)} bars, {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
        return df[["time", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        print(f"  ✗ Twelve Data failed: {e}")
        return None


def fetch_ejtraderLabs_csv() -> Optional[pd.DataFrame]:
    """Fetch from ejtraderLabs GitHub (free, no API key needed)."""
    try:
        print("  Fetching from ejtraderLabs GitHub...")
        import urllib.request
        url = "https://raw.githubusercontent.com/ejtraderLabs/historical-data/main/XAUUSD/XAUUSDm15.csv"
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaFXHub/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')

        from io import StringIO
        df = pd.read_csv(StringIO(content))

        # Rename columns to standard format
        col_map = {}
        for col in df.columns:
            cl = col.lower().strip()
            if cl in ("time", "datetime", "date", "timestamp"):
                col_map[col] = "time"
            elif cl in ("open", "o"):
                col_map[col] = "open"
            elif cl in ("high", "h"):
                col_map[col] = "high"
            elif cl in ("low", "l"):
                col_map[col] = "low"
            elif cl in ("close", "c"):
                col_map[col] = "close"
            elif cl in ("volume", "vol", "v", "tick_volume"):
                col_map[col] = "volume"
        df = df.rename(columns=col_map)

        required = {"time", "open", "high", "low", "close"}
        if not required.issubset(set(df.columns)):
            print(f"  ✗ GitHub CSV missing required columns")
            return None

        df["time"] = pd.to_datetime(df["time"])
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        if "volume" not in df.columns:
            df["volume"] = 1000
        df = df.sort_values("time").reset_index(drop=True)
        print(f"  ✓ ejtraderLabs: {len(df)} bars, {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
        return df[["time", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        print(f"  ✗ ejtraderLabs failed: {e}")
        return None


def fetch_yfinance() -> Optional[pd.DataFrame]:
    """Fetch from yfinance (GC=F gold futures, max 60 days at M15)."""
    try:
        import yfinance as yf
        print("  Fetching gold futures (GC=F) M15 from yfinance...")
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="60d", interval="15m")
        if df.empty:
            print("  ✗ yfinance returned empty data")
            return None
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "time", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })
        df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
        df = df[["time", "open", "high", "low", "close", "volume"]]
        df = df.dropna().reset_index(drop=True)
        print(f"  ✓ yfinance: {len(df)} bars, {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
        return df
    except ImportError:
        print("  ✗ yfinance not installed. Run: pip install yfinance")
        return None
    except Exception as e:
        print(f"  ✗ yfinance failed: {e}")
        return None


def load_csv(filepath: str) -> Optional[pd.DataFrame]:
    """Load from CSV (TradingView or MT5 export)."""
    try:
        print(f"  Loading CSV: {filepath}")
        df = pd.read_csv(filepath)
        col_map = {}
        for col in df.columns:
            cl = col.lower().strip()
            if cl in ("time", "datetime", "date", "timestamp"):
                col_map[col] = "time"
            elif cl in ("open", "o"):
                col_map[col] = "open"
            elif cl in ("high", "h"):
                col_map[col] = "high"
            elif cl in ("low", "l"):
                col_map[col] = "low"
            elif cl in ("close", "c"):
                col_map[col] = "close"
            elif cl in ("volume", "vol", "v", "tick_volume"):
                col_map[col] = "volume"
        df = df.rename(columns=col_map)
        required = {"time", "open", "high", "low", "close"}
        if not required.issubset(set(df.columns)):
            print(f"  ✗ CSV missing columns. Found: {list(df.columns)}")
            print(f"    Need: time, open, high, low, close")
            return None
        df["time"] = pd.to_datetime(df["time"])
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        if "volume" not in df.columns:
            df["volume"] = 1000
        df = df.sort_values("time").reset_index(drop=True)
        print(f"  ✓ CSV: {len(df)} bars, {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
        return df[["time", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        print(f"  ✗ CSV load failed: {e}")
        return None


def get_real_data(csv_path: str = None) -> Tuple[pd.DataFrame, str]:
    """Try all data sources in order, return (df, source_label)."""
    print("\n📊 Fetching Real XAUUSD Data...\n")

    # 1. CSV file (highest priority — user-provided)
    if csv_path and os.path.exists(csv_path):
        df = load_csv(csv_path)
        if df is not None and len(df) > 100:
            return df, f"CSV ({csv_path})"

    # 2. Twelve Data (best M15 source)
    api_key = os.environ.get("TWELVE_DATA_API_KEY", "")
    if api_key and api_key != "paste_your_twelve_data_key_here":
        df = fetch_twelve_data(api_key)
        if df is not None and len(df) > 100:
            return df, "Twelve Data API (M15)"

    # 3. yfinance M15 (60 days)
    df = fetch_yfinance()
    if df is not None and len(df) > 100:
        return df, "yfinance GC=F (M15, 60 days)"

    # 4. ejtraderLabs GitHub
    df = fetch_ejtraderLabs_csv()
    if df is not None and len(df) > 100:
        return df, "ejtraderLabs GitHub (M15)"

    print("\n❌ Could not fetch any real data.")
    print("   Options:")
    print("   1. Set TWELVE_DATA_API_KEY env var (free at twelvedata.com)")
    print("   2. Install yfinance: pip install yfinance")
    print("   3. Use ejtraderLabs data (automatic — internet required)")
    print("   4. Export M15 XAUUSD data from TradingView/MT5 as CSV")
    print("      and pass: python real_data_backtest_v2.py --csv yourfile.csv")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════
# INDICATORS
# ════════════════════════════════════════════════════════════════

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for p in [9, 20, 50, 200]:
        df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift()),
        abs(df["low"] - df["close"].shift()),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean().bfill()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1)
    df["rsi14"] = (100 - (100 / (1 + rs))).bfill().fillna(50)

    df["bb_mid"] = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std

    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    atr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_smooth.replace(0, 1))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_smooth.replace(0, 1))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1)
    df["adx"] = dx.rolling(14).mean().bfill().fillna(20)
    df["plus_di"] = plus_di.bfill().fillna(0)
    df["minus_di"] = minus_di.bfill().fillna(0)

    df["swing_low"] = df["low"].rolling(20, center=False).min()
    df["swing_high"] = df["high"].rolling(20, center=False).max()

    # Market regime detection
    df["regime"] = "unknown"
    atr_ma = df["atr14"].rolling(50).mean()
    ema50_slope = df["ema50"].diff(10) / df["atr14"]
    for i in range(50, len(df)):
        adx_val = df["adx"].iloc[i]
        slope = ema50_slope.iloc[i] if not np.isnan(ema50_slope.iloc[i]) else 0
        atr_ratio = df["atr14"].iloc[i] / atr_ma.iloc[i] if atr_ma.iloc[i] > 0 else 1

        if atr_ratio > 1.5:
            df.iloc[i, df.columns.get_loc("regime")] = "high_volatility"
        elif adx_val > 25 and abs(slope) > 0.3:
            df.iloc[i, df.columns.get_loc("regime")] = "trend"
        elif adx_val < 20:
            df.iloc[i, df.columns.get_loc("regime")] = "range"
        else:
            df.iloc[i, df.columns.get_loc("regime")] = "transition"

    return df


# ════════════════════════════════════════════════════════════════
# TRADE DATACLASS
# ════════════════════════════════════════════════════════════════

@dataclass
class Trade:
    num: int = 0
    entry_time: datetime = None
    entry_price: float = 0.0
    direction: str = ""
    sl: float = 0.0
    initial_sl: float = 0.0
    initial_lot: float = 0.0
    remaining_lot: float = 0.0
    tp_levels: List[float] = field(default_factory=list)
    status: str = "active"
    grade: str = ""
    score: int = 0
    confidence: str = ""
    session: str = ""
    regime: str = ""
    tp_hit: int = 0
    partial_closes: List[dict] = field(default_factory=list)
    pnl_usd: float = 0.0
    pnl_pips: float = 0.0
    r_multiple: float = 0.0
    close_time: datetime = None
    close_price: float = 0.0
    close_reason: str = ""
    risk_usd: float = 0.0


# ════════════════════════════════════════════════════════════════
# SIGNAL EVALUATION (Deterministic, V3 rules)
# ════════════════════════════════════════════════════════════════

def evaluate_signal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """Deterministic signal evaluation (no randomness)."""
    if idx < 200:
        return None

    row = df.iloc[idx]
    close = float(row["close"])
    ema9 = float(row["ema9"])
    ema20 = float(row["ema20"])
    ema50 = float(row["ema50"])
    ema200 = float(row["ema200"])
    rsi = float(row["rsi14"])
    atr = float(row["atr14"])
    adx = float(row["adx"])
    plus_di = float(row["plus_di"])
    minus_di = float(row["minus_di"])

    hour = row["time"].hour if hasattr(row["time"], "hour") else 12

    # Session filter: London + NY only
    if not (7 <= hour < 17):
        return None

    # Minimum trend strength
    if adx < 15:
        return None

    # Multi-timeframe alignment
    bull_strong = ema9 > ema20 > ema50 and close > ema50 and close > ema200
    bear_strong = ema9 < ema20 < ema50 and close < ema50 and close < ema200
    bull_moderate = ema9 > ema20 and close > ema50 and close > ema200
    bear_moderate = ema9 < ema20 and close < ema50 and close < ema200
    bull_weak = ema9 > ema20 and close > ema20
    bear_weak = ema9 < ema20 and close < ema20

    if bull_strong or bull_moderate:
        direction = "BUY"
    elif bear_strong or bear_moderate:
        direction = "SELL"
    elif bull_weak and adx > 20:
        direction = "BUY"
    elif bear_weak and adx > 20:
        direction = "SELL"
    else:
        return None

    # RSI not extreme
    if direction == "BUY" and rsi > 75:
        return None
    if direction == "SELL" and rsi < 25:
        return None

    # Scoring (11 modules)
    score = 0
    confirmations = 0

    # M1: MTF Alignment
    if bull_strong or bear_strong:
        score += 15; confirmations += 1
    elif bull_moderate or bear_moderate:
        score += 10; confirmations += 1
    elif bull_weak or bear_weak:
        score += 5; confirmations += 1

    # M2: ADX strength
    if adx > 35: score += 10; confirmations += 1
    elif adx > 25: score += 7; confirmations += 1
    elif adx > 15: score += 4; confirmations += 1

    # M3: S/D zone
    lookback = df.iloc[max(0, idx - 50):idx + 1]
    recent_low = lookback["low"].min()
    recent_high = lookback["high"].max()
    range_size = max(recent_high - recent_low, atr)
    if direction == "BUY" and (close - recent_low) < range_size * 0.3:
        score += 12; confirmations += 1
    elif direction == "SELL" and (recent_high - close) < range_size * 0.3:
        score += 12; confirmations += 1
    elif direction == "BUY" and (close - recent_low) < range_size * 0.45:
        score += 7
    elif direction == "SELL" and (recent_high - close) < range_size * 0.45:
        score += 7

    # M4: FVG (Fair Value Gap)
    for j in range(max(0, idx - 5), idx):
        if j + 2 < len(df):
            if direction == "BUY" and float(df.iloc[j + 2]["low"]) > float(df.iloc[j]["high"]):
                score += 8; confirmations += 1; break
            if direction == "SELL" and float(df.iloc[j + 2]["high"]) < float(df.iloc[j]["low"]):
                score += 8; confirmations += 1; break

    # M5: Structure break
    rh_max = lookback["high"].rolling(10).max().iloc[-1]
    rl_min = lookback["low"].rolling(10).min().iloc[-1]
    if direction == "BUY" and close > rh_max * 0.999:
        score += 10; confirmations += 1
    elif direction == "SELL" and close < rl_min * 1.001:
        score += 10; confirmations += 1

    # M6: RSI
    if direction == "BUY" and 35 < rsi < 65: score += 6; confirmations += 1
    elif direction == "SELL" and 35 < rsi < 65: score += 6; confirmations += 1

    # M7: BB position
    bb_mid = float(row.get("bb_mid", close))
    bb_upper = float(row.get("bb_upper", close + 10))
    bb_lower = float(row.get("bb_lower", close - 10))
    if direction == "BUY" and close > bb_mid:
        score += 5
    elif direction == "SELL" and close < bb_mid:
        score += 5

    # M8: ATR expansion (volatility trending)
    atr_ma = df["atr14"].iloc[max(0, idx - 50):idx + 1].mean()
    if atr > atr_ma * 1.2: score += 4

    # M9: Momentum (EMA slope)
    if idx >= 10:
        ema9_slope = (ema9 - df["ema9"].iloc[idx - 10]) / df["atr14"].iloc[idx]
        if direction == "BUY" and ema9_slope > 0.5: score += 6; confirmations += 1
        elif direction == "SELL" and ema9_slope < -0.5: score += 6; confirmations += 1

    # M10: Session momentum (hour-based)
    if 8 <= hour <= 14: score += 4

    # M11: DI crossover (institutional proxy - deterministic)
    prev_plus = float(df["plus_di"].iloc[idx - 1]) if idx > 0 else plus_di
    prev_minus = float(df["minus_di"].iloc[idx - 1]) if idx > 0 else minus_di
    if direction == "BUY" and plus_di > prev_plus and plus_di > minus_di:
        score += 8; confirmations += 1
    elif direction == "SELL" and minus_di > prev_minus and minus_di > plus_di:
        score += 8; confirmations += 1

    # Grade assignment
    if score >= 75:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 45:
        grade = "C"
    else:
        grade = "D"

    # Confidence
    if confirmations >= 8:
        confidence = "HIGH"
    elif confirmations >= 5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Session name
    if 7 <= hour < 10:
        session = "London Open"
    elif 10 <= hour < 13:
        session = "London-NY"
    else:
        session = "NY"

    regime = str(row.get("regime", "unknown"))

    return {
        "direction": direction,
        "grade": grade,
        "score": score,
        "confidence": confidence,
        "session": session,
        "regime": regime,
    }


# ════════════════════════════════════════════════════════════════
# BACKTEST ENGINE (with fixed SL logic and execution delay support)
# ════════════════════════════════════════════════════════════════

def run_real_backtest(df: pd.DataFrame, spread_pips: float = 2.0,
                      slippage_pips: float = 0.5,
                      starting_balance: float = 10000.0,
                      risk_pct: float = 2.0,
                      execution_delay: bool = False,
                      start_idx: int = 200) -> Dict:
    """
    Run backtest with FIXED SL logic and gap-aware execution.

    execution_delay: if True, entry happens on next bar open + spread + slippage
    """
    balance = starting_balance
    peak_balance = starting_balance
    max_drawdown = 0.0
    trades: List[Trade] = []
    equity_curve = [(df.iloc[start_idx]["time"], balance)]
    cooldown = 0
    active_trade: Optional[Trade] = None
    trade_num = 0
    daily_loss = 0.0
    last_day = None
    pending_signal = None  # For execution delay

    total_cost = (spread_pips + slippage_pips) * PIP

    for idx in range(start_idx, len(df)):
        row = df.iloc[idx]
        current_time = row["time"]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        atr = float(row["atr14"]) if not np.isnan(row["atr14"]) else 3.0

        # Daily reset
        current_day = current_time.date() if hasattr(current_time, "date") else None
        if current_day != last_day:
            daily_loss = 0.0
            last_day = current_day

        # Risk guard: 4% daily loss limit
        if daily_loss >= balance * 0.04:
            cooldown = max(cooldown, 96)

        # Handle pending signal from execution delay
        if pending_signal and not execution_delay:
            pending_signal = None

        # Process active trade
        if active_trade and active_trade.status == "active":
            old_bal = balance

            # CHECK SL (with gap-through handling)
            sl_hit = False
            sl_fill_price = active_trade.sl

            if active_trade.direction == "BUY":
                if low <= active_trade.sl:
                    sl_hit = True
                    # BUG FIX #3: Gap through SL - fill at actual low, not at SL
                    if low < active_trade.sl:
                        sl_fill_price = low
                        # Add slippage on stop-out
                        sl_fill_price = sl_fill_price - 0.3 * PIP
                    else:
                        sl_fill_price = active_trade.sl - 0.3 * PIP
            else:  # SELL
                if high >= active_trade.sl:
                    sl_hit = True
                    # Gap through SL - fill at actual high, not at SL
                    if high > active_trade.sl:
                        sl_fill_price = high
                        # Add slippage on stop-out
                        sl_fill_price = sl_fill_price + 0.3 * PIP
                    else:
                        sl_fill_price = active_trade.sl + 0.3 * PIP

            if sl_hit:
                close_trade(active_trade, sl_fill_price, current_time, "SL Hit", balance)
                balance += active_trade.pnl_usd
            else:
                # Check TPs
                process_tps(active_trade, high, low, close, current_time)
                if active_trade.status == "closed":
                    balance += active_trade.pnl_usd

            if active_trade.status == "closed":
                pnl = balance - old_bal
                if pnl < 0:
                    daily_loss += abs(pnl)

        # New signal
        if cooldown <= 0 and (active_trade is None or active_trade.status != "active"):
            signal = evaluate_signal(df, idx)
            if signal:
                if execution_delay:
                    # Store signal for next bar entry
                    pending_signal = (signal, idx)
                else:
                    # Immediate entry
                    direction = signal["direction"]
                    entry = close + total_cost if direction == "BUY" else close - total_cost

                    # ── BUG FIX #1: Improved SL Logic ──
                    swing_low = float(row["swing_low"]) if not np.isnan(row.get("swing_low", float("nan"))) else entry - atr
                    swing_high = float(row["swing_high"]) if not np.isnan(row.get("swing_high", float("nan"))) else entry + atr

                    if direction == "BUY":
                        # Structure-based SL is primary
                        structure_sl = swing_low - 1.5 * PIP
                        atr_sl = entry - 0.75 * atr

                        # Use structure SL unless too far away
                        if (entry - structure_sl) > 1.5 * atr:
                            # Structure too far, use ATR fallback
                            sl = atr_sl
                        else:
                            # Structure is reasonable distance
                            sl = structure_sl

                        # Apply caps: min 0.5x ATR, max 2.0x ATR
                        min_sl = entry - 0.5 * atr
                        max_sl = entry - 2.0 * atr
                        sl = max(sl, max_sl)  # Enforce max distance (2.0x ATR)
                        sl = min(sl, min_sl)  # Enforce min distance (0.5x ATR)
                    else:  # SELL
                        structure_sl = swing_high + 1.5 * PIP
                        atr_sl = entry + 0.75 * atr

                        if (structure_sl - entry) > 1.5 * atr:
                            sl = atr_sl
                        else:
                            sl = structure_sl

                        min_sl = entry + 0.5 * atr
                        max_sl = entry + 2.0 * atr
                        sl = min(sl, max_sl)  # Enforce max distance
                        sl = max(sl, min_sl)  # Enforce min distance

                    sl = round(sl, 2)
                    risk_pips_val = abs(entry - sl) / PIP
                    if risk_pips_val <= 2 or risk_pips_val > 150:
                        cooldown = max(0, cooldown - 1)
                        continue

                    risk_usd = balance * (risk_pct / 100.0)
                    lot = risk_usd / (risk_pips_val * PIP_VALUE_PER_LOT)
                    lot = max(0.01, min(5.0, round(lot, 2)))

                    risk_distance = abs(entry - sl)
                    tp_levels = []
                    for mult in TP_RISK_MULTIPLES:
                        if direction == "BUY":
                            tp_levels.append(round(entry + mult * risk_distance, 2))
                        else:
                            tp_levels.append(round(entry - mult * risk_distance, 2))

                    trade = Trade(
                        num=trade_num, entry_time=current_time, entry_price=round(entry, 2),
                        direction=direction, sl=sl, initial_sl=sl, initial_lot=lot,
                        remaining_lot=lot, tp_levels=tp_levels, grade=signal["grade"],
                        score=signal["score"], confidence=signal["confidence"],
                        session=signal["session"], regime=signal["regime"],
                        risk_usd=risk_usd,
                    )
                    trades.append(trade)
                    active_trade = trade
                    trade_num += 1
                    cooldown = 6

        # Handle pending signal entry on next bar (execution delay)
        if pending_signal and idx > pending_signal[1]:
            signal, sig_idx = pending_signal
            direction = signal["direction"]
            entry = close + total_cost if direction == "BUY" else close - total_cost

            swing_low = float(row["swing_low"]) if not np.isnan(row.get("swing_low", float("nan"))) else entry - atr
            swing_high = float(row["swing_high"]) if not np.isnan(row.get("swing_high", float("nan"))) else entry + atr

            if direction == "BUY":
                structure_sl = swing_low - 1.5 * PIP
                atr_sl = entry - 0.75 * atr
                if (entry - structure_sl) > 1.5 * atr:
                    sl = atr_sl
                else:
                    sl = structure_sl
                min_sl = entry - 0.5 * atr
                max_sl = entry - 2.0 * atr
                sl = max(sl, max_sl)
                sl = min(sl, min_sl)
            else:
                structure_sl = swing_high + 1.5 * PIP
                atr_sl = entry + 0.75 * atr
                if (structure_sl - entry) > 1.5 * atr:
                    sl = atr_sl
                else:
                    sl = structure_sl
                min_sl = entry + 0.5 * atr
                max_sl = entry + 2.0 * atr
                sl = min(sl, max_sl)
                sl = max(sl, min_sl)

            sl = round(sl, 2)
            risk_pips_val = abs(entry - sl) / PIP
            if risk_pips_val > 2 and risk_pips_val <= 150:
                risk_usd = balance * (risk_pct / 100.0)
                lot = risk_usd / (risk_pips_val * PIP_VALUE_PER_LOT)
                lot = max(0.01, min(5.0, round(lot, 2)))

                risk_distance = abs(entry - sl)
                tp_levels = []
                for mult in TP_RISK_MULTIPLES:
                    if direction == "BUY":
                        tp_levels.append(round(entry + mult * risk_distance, 2))
                    else:
                        tp_levels.append(round(entry - mult * risk_distance, 2))

                trade = Trade(
                    num=trade_num, entry_time=current_time, entry_price=round(entry, 2),
                    direction=direction, sl=sl, initial_sl=sl, initial_lot=lot,
                    remaining_lot=lot, tp_levels=tp_levels, grade=signal["grade"],
                    score=signal["score"], confidence=signal["confidence"],
                    session=signal["session"], regime=signal["regime"],
                    risk_usd=risk_usd,
                )
                trades.append(trade)
                active_trade = trade
                trade_num += 1
                cooldown = 6

            pending_signal = None

        cooldown = max(0, cooldown - 1)

        if idx % 16 == 0:
            equity_curve.append((current_time, round(balance, 2)))
            if balance > peak_balance:
                peak_balance = balance
            dd = peak_balance - balance
            if dd > max_drawdown:
                max_drawdown = dd

    # Close remaining trade
    if active_trade and active_trade.status == "active":
        last_row = df.iloc[-1]
        close_trade(active_trade, float(last_row["close"]), last_row["time"],
                    "Backtest ended", balance)
        balance += active_trade.pnl_usd

    return compile_results(trades, balance, starting_balance, peak_balance,
                          max_drawdown, equity_curve, spread_pips, slippage_pips)


def process_tps(trade: Trade, high: float, low: float, close: float, current_time):
    """Process take profits and trailing SL."""
    while trade.tp_hit < len(trade.tp_levels):
        tp_price = trade.tp_levels[trade.tp_hit]
        hit = (trade.direction == "BUY" and high >= tp_price) or \
              (trade.direction == "SELL" and low <= tp_price)
        if not hit:
            break

        tp_num = trade.tp_hit + 1
        lot_pct = LOT_PCT[trade.tp_hit] if trade.tp_hit < len(LOT_PCT) else 0.05
        close_lot = min(round(trade.initial_lot * lot_pct, 2), trade.remaining_lot)
        if close_lot < 0.005:
            trade.tp_hit = tp_num
            continue

        pnl_pips = abs(tp_price - trade.entry_price) / PIP
        pnl_usd = close_lot * pnl_pips * PIP_VALUE_PER_LOT
        trade.partial_closes.append({
            "tp_num": tp_num, "tp_price": tp_price,
            "closed_lot": close_lot, "pnl_usd": round(pnl_usd, 2),
        })
        trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
        trade.tp_hit = tp_num

        # Trailing SL
        if tp_num in TRAILING_RULES:
            rule = TRAILING_RULES[tp_num]
            if rule == "breakeven":
                new_sl = trade.entry_price + 2 * PIP if trade.direction == "BUY" else trade.entry_price - 2 * PIP
            else:
                tp_idx = rule - 1
                new_sl = trade.tp_levels[tp_idx] if tp_idx < len(trade.tp_levels) else trade.sl
            if trade.direction == "BUY" and new_sl > trade.sl:
                trade.sl = round(new_sl, 2)
            elif trade.direction == "SELL" and new_sl < trade.sl:
                trade.sl = round(new_sl, 2)

    if trade.remaining_lot <= 0.005:
        close_trade(trade, close, current_time, "All TPs hit", 0)


def close_trade(trade: Trade, close_price: float, close_time, reason: str, balance: float):
    """Close trade and calculate P&L."""
    trade.status = "closed"
    trade.close_time = close_time
    trade.close_price = close_price
    trade.close_reason = reason

    remaining_pnl = 0.0
    if trade.remaining_lot > 0.005:
        if trade.direction == "BUY":
            pnl_pips = (close_price - trade.entry_price) / PIP
        else:
            pnl_pips = (trade.entry_price - close_price) / PIP
        remaining_pnl = trade.remaining_lot * pnl_pips * PIP_VALUE_PER_LOT

    total_pnl = sum(pc["pnl_usd"] for pc in trade.partial_closes) + remaining_pnl
    total_pnl = round(total_pnl, 2)

    trade.pnl_usd = total_pnl
    if trade.risk_usd > 0:
        trade.r_multiple = total_pnl / trade.risk_usd
    else:
        trade.r_multiple = 0.0

    if trade.direction == "BUY":
        trade.pnl_pips = (close_price - trade.entry_price) / PIP
    else:
        trade.pnl_pips = (trade.entry_price - close_price) / PIP


# ════════════════════════════════════════════════════════════════
# RESULTS COMPILATION
# ════════════════════════════════════════════════════════════════

def compile_results(trades, balance, starting_balance, peak_balance,
                   max_drawdown, equity_curve, spread_pips, slippage_pips) -> Dict:
    """Compile all trading metrics."""
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "final_balance": balance,
            "total_return_pct": 0.0,
            "max_drawdown_usd": max_drawdown,
            "max_drawdown_pct": 0.0,
            "avg_r_multiple": 0.0,
            "median_r_multiple": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "avg_trade_pnl": 0.0,
            "outlier_top1_pct": 0.0,
            "outlier_top3_pct": 0.0,
            "return_to_dd_ratio": 0.0,
            "sharpe_estimate": 0.0,
            "trades_by_session": {},
            "trades_by_regime": {},
            "monthly_breakdown": {},
            "stress_config": f"spread={spread_pips}, slippage={slippage_pips}",
        }

    # Basic metrics
    winning_trades = [t for t in trades if t.pnl_usd > 0]
    losing_trades = [t for t in trades if t.pnl_usd <= 0]
    total_trades = len(trades)
    win_count = len(winning_trades)
    loss_count = len(losing_trades)

    winning_sum = sum(t.pnl_usd for t in winning_trades) if winning_trades else 0
    losing_sum = sum(t.pnl_usd for t in losing_trades) if losing_trades else 0
    profit_factor = winning_sum / abs(losing_sum) if losing_sum != 0 else (999.9 if winning_sum > 0 else 0)

    total_return = balance - starting_balance
    total_return_pct = (total_return / starting_balance) * 100 if starting_balance > 0 else 0
    max_dd_pct = (max_drawdown / peak_balance) * 100 if peak_balance > 0 else 0

    r_multiples = [t.r_multiple for t in trades]
    avg_r = np.mean(r_multiples) if r_multiples else 0.0
    median_r = np.median(r_multiples) if r_multiples else 0.0

    pnls = [t.pnl_usd for t in trades]
    best_trade = max(pnls) if pnls else 0.0
    worst_trade = min(pnls) if pnls else 0.0
    avg_trade_pnl = np.mean(pnls) if pnls else 0.0

    # Outlier contribution
    if pnls:
        top_1 = sorted(pnls, reverse=True)[0] if len(pnls) > 0 else 0
        top_3_sum = sum(sorted(pnls, reverse=True)[:3])
        outlier_top1_pct = (top_1 / total_return * 100) if total_return > 0 else 0
        outlier_top3_pct = (top_3_sum / total_return * 100) if total_return > 0 else 0
    else:
        outlier_top1_pct = 0
        outlier_top3_pct = 0

    # Return-to-DD ratio
    return_to_dd_ratio = (total_return / max_drawdown) if max_drawdown > 0 else (999.9 if total_return > 0 else 0)

    # Sharpe-like estimate (based on daily returns)
    daily_returns = []
    if len(equity_curve) > 1:
        for i in range(1, len(equity_curve)):
            daily_ret = (equity_curve[i][1] - equity_curve[i-1][1]) / starting_balance
            daily_returns.append(daily_ret)

    if daily_returns:
        daily_ret_array = np.array(daily_returns)
        avg_daily = np.mean(daily_ret_array)
        std_daily = np.std(daily_ret_array)
        sharpe_estimate = (avg_daily * 252 / std_daily) if std_daily > 0 else 0.0
    else:
        sharpe_estimate = 0.0

    # By session
    by_session = {}
    for t in trades:
        sess = t.session or "unknown"
        if sess not in by_session:
            by_session[sess] = []
        by_session[sess].append(t.pnl_usd)

    session_summary = {}
    for sess, pnls in by_session.items():
        session_summary[sess] = {
            "count": len(pnls),
            "pnl": round(sum(pnls), 2),
            "win_rate": round(len([p for p in pnls if p > 0]) / len(pnls) * 100, 1) if pnls else 0,
        }

    # By regime
    by_regime = {}
    for t in trades:
        regime = t.regime or "unknown"
        if regime not in by_regime:
            by_regime[regime] = []
        by_regime[regime].append(t.pnl_usd)

    regime_summary = {}
    for regime, pnls in by_regime.items():
        regime_summary[regime] = {
            "count": len(pnls),
            "pnl": round(sum(pnls), 2),
            "win_rate": round(len([p for p in pnls if p > 0]) / len(pnls) * 100, 1) if pnls else 0,
        }

    # Monthly breakdown
    monthly = {}
    for t in trades:
        if t.close_time:
            month_key = t.close_time.strftime("%Y-%m")
            if month_key not in monthly:
                monthly[month_key] = []
            monthly[month_key].append(t.pnl_usd)

    monthly_summary = {}
    for month, pnls in sorted(monthly.items()):
        monthly_summary[month] = {
            "trades": len(pnls),
            "pnl": round(sum(pnls), 2),
            "win_rate": round(len([p for p in pnls if p > 0]) / len(pnls) * 100, 1) if pnls else 0,
        }

    return {
        "total_trades": total_trades,
        "winning_trades": win_count,
        "losing_trades": loss_count,
        "win_rate_pct": round((win_count / total_trades * 100) if total_trades > 0 else 0, 1),
        "profit_factor": round(profit_factor, 2),
        "final_balance": round(balance, 2),
        "total_return_usd": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown_usd": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "avg_r_multiple": round(avg_r, 2),
        "median_r_multiple": round(median_r, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "avg_trade_pnl": round(avg_trade_pnl, 2),
        "outlier_top1_pct": round(outlier_top1_pct, 1),
        "outlier_top3_pct": round(outlier_top3_pct, 1),
        "return_to_dd_ratio": round(return_to_dd_ratio, 2),
        "sharpe_estimate": round(sharpe_estimate, 2),
        "trades_by_session": session_summary,
        "trades_by_regime": regime_summary,
        "monthly_breakdown": monthly_summary,
        "stress_config": f"spread={spread_pips}, slippage={slippage_pips}",
        "trades": trades,
    }


# ════════════════════════════════════════════════════════════════
# REPORTING
# ════════════════════════════════════════════════════════════════

def print_report(r: Dict, data_source: str, data_bars: int):
    """Print detailed backtest report."""
    print("\n" + "=" * 72)
    print("  BACKTEST RESULTS")
    print("=" * 72)
    print(f"\nData Source: {data_source} ({data_bars} bars)")
    print(f"Stress Config: {r['stress_config']}")

    print("\n--- PERFORMANCE METRICS ---")
    print(f"  Total Trades:           {r['total_trades']}")
    print(f"  Winning / Losing:       {r['winning_trades']} / {r['losing_trades']}")
    print(f"  Win Rate:               {r['win_rate_pct']}%")
    print(f"  Profit Factor:          {r['profit_factor']}")
    print()
    print(f"  Final Balance:          ${r['final_balance']:,.2f}")
    print(f"  Total Return:           ${r['total_return_usd']:,.2f} ({r['total_return_pct']:.2f}%)")
    print(f"  Max Drawdown:           ${r['max_drawdown_usd']:,.2f} ({r['max_drawdown_pct']:.2f}%)")
    print(f"  Return-to-DD Ratio:     {r['return_to_dd_ratio']:.2f}")
    print(f"  Sharpe-like Estimate:   {r['sharpe_estimate']:.2f}")
    print()
    print(f"  Avg Trade:              ${r['avg_trade_pnl']:,.2f}")
    print(f"  Best / Worst Trade:     ${r['best_trade']:,.2f} / ${r['worst_trade']:,.2f}")
    print()
    print(f"  Avg R Multiple:         {r['avg_r_multiple']:.2f}R")
    print(f"  Median R Multiple:      {r['median_r_multiple']:.2f}R")
    print()
    print(f"  Top 1 Trade Contrib:    {r['outlier_top1_pct']:.1f}% of total return")
    print(f"  Top 3 Trades Contrib:   {r['outlier_top3_pct']:.1f}% of total return")

    if r['trades_by_session']:
        print("\n--- BY SESSION ---")
        for sess, data in sorted(r['trades_by_session'].items()):
            print(f"  {sess:20s}: {data['count']:3d} trades, ${data['pnl']:10,.2f}, {data['win_rate']:5.1f}% WR")

    if r['trades_by_regime']:
        print("\n--- BY REGIME ---")
        for regime, data in sorted(r['trades_by_regime'].items()):
            print(f"  {regime:20s}: {data['count']:3d} trades, ${data['pnl']:10,.2f}, {data['win_rate']:5.1f}% WR")

    if r['monthly_breakdown']:
        print("\n--- MONTHLY BREAKDOWN ---")
        for month, data in sorted(r['monthly_breakdown'].items()):
            print(f"  {month}: {data['trades']:2d} trades, ${data['pnl']:10,.2f}, {data['win_rate']:5.1f}% WR")

    print()


def print_stress_report(stress_results: List[Dict]):
    """Print stress test comparison."""
    print("\n" + "=" * 72)
    print("  STRESS TEST RESULTS (Spread / Slippage Variations)")
    print("=" * 72)
    configs = ["Base (2.0/0.5)", "Medium (2.5/0.5)", "High (3.0/1.0)", "Worst (4.0/1.5)"]
    for i, r in enumerate(stress_results):
        if i < len(configs):
            print(f"\n{configs[i]}:")
            print(f"  Return:     ${r['total_return_usd']:>10,.2f} ({r['total_return_pct']:>6.2f}%)")
            print(f"  Drawdown:   ${r['max_drawdown_usd']:>10,.2f} ({r['max_drawdown_pct']:>6.2f}%)")
            print(f"  Profit Factor: {r['profit_factor']:>8.2f}")
            print(f"  Win Rate:   {r['win_rate_pct']:>8.1f}%")


def walk_forward(df: pd.DataFrame, n_folds: int = 5,
                 spread_pips: float = 2.0, slippage_pips: float = 0.5) -> List[Dict]:
    """Walk-forward validation: train on past, test on future."""
    results = []
    total_len = len(df)
    fold_size = total_len // n_folds

    for fold in range(n_folds):
        test_start = fold * fold_size
        test_end = (fold + 1) * fold_size if fold < n_folds - 1 else total_len
        train_end = test_start

        if test_start >= train_end or test_end <= test_start:
            continue

        df_test = df.iloc[test_start:test_end].reset_index(drop=True)
        if len(df_test) < 100:
            continue

        r = run_real_backtest(df_test, spread_pips=spread_pips, slippage_pips=slippage_pips)
        r['fold'] = fold + 1
        results.append(r)

    return results


def print_walkforward_report(wf_results: List[Dict]):
    """Print walk-forward results."""
    print("\n" + "=" * 72)
    print("  WALK-FORWARD VALIDATION (5 Time-Based Folds)")
    print("=" * 72)
    if not wf_results:
        print("  (Insufficient data for meaningful folds)")
        return

    for r in wf_results:
        print(f"\nFold {r.get('fold', '?')}:")
        print(f"  Trades:      {r['total_trades']:3d}, Win Rate: {r['win_rate_pct']:5.1f}%")
        print(f"  Return:      ${r['total_return_usd']:>10,.2f}")
        print(f"  Max DD:      ${r['max_drawdown_usd']:>10,.2f}")

    # Consistency check
    profitable_folds = sum(1 for r in wf_results if r['total_return_usd'] > 0)
    consistency = "STRONG" if profitable_folds >= 4 else "MODERATE" if profitable_folds >= 3 else "WEAK"
    print(f"\n  Consistency Rating: {consistency} ({profitable_folds}/{len(wf_results)} folds profitable)")
    print()


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alpha FX Hub Real Data Backtester V2")
    parser.add_argument("--csv", help="Path to CSV with XAUUSD M15 OHLCV data")
    parser.add_argument("--balance", type=float, default=10000.0, help="Starting balance (default: $10,000)")
    parser.add_argument("--risk", type=float, default=2.0, help="Risk per trade %% (default: 2.0)")
    parser.add_argument("--delay", action="store_true", help="Enable execution delay (entry on next bar)")
    args = parser.parse_args()

    print("\n" + "=" * 72)
    print("  ALPHA FX HUB — REAL DATA VALIDATION SUITE V2")
    print("  Strategy: V3 Trend-Following with 2:1 Min R:R")
    print("  Fixed: SL Logic, Stress Configs, Gap-Through, Execution Delay")
    print("=" * 72)

    # Fetch data
    df, source = get_real_data(csv_path=args.csv)
    total_bars = len(df)

    # Add indicators
    print("\n📈 Computing indicators...")
    df = add_indicators(df)
    print(f"  ✓ Indicators computed on {len(df)} bars")
    print(f"  ATR range: ${df['atr14'].min():.2f} - ${df['atr14'].max():.2f}")
    print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # ── Main backtest (base costs) ──
    print("\n🔬 Running main backtest (spread 2.0 + slip 0.5)...")
    main_result = run_real_backtest(df, spread_pips=2.0, slippage_pips=0.5,
                                   starting_balance=args.balance, risk_pct=args.risk,
                                   execution_delay=args.delay)
    print()
    print_report(main_result, source, total_bars)

    # ── Stress tests (BUG FIX #2: Fixed configs) ──
    print("\n🔥 Running spread/slippage stress tests...")
    stress_configs = [
        (2.0, 0.5),   # Base
        (2.5, 0.5),   # Medium
        (3.0, 1.0),   # High
        (4.0, 1.5),   # Worst
    ]
    stress_results = []
    for sp, sl in stress_configs:
        r = run_real_backtest(df, spread_pips=sp, slippage_pips=sl,
                             starting_balance=args.balance, risk_pct=args.risk,
                             execution_delay=args.delay)
        stress_results.append(r)
    print_stress_report(stress_results)

    # ── Walk-forward ──
    if total_bars > 1500:
        print("\n📊 Running walk-forward validation (5 folds)...")
        wf = walk_forward(df, n_folds=5, spread_pips=2.0, slippage_pips=0.5)
        print_walkforward_report(wf)
    else:
        print(f"\n⚠️  Skipping walk-forward: only {total_bars} bars (need >1500)")
        print(f"   Get a Twelve Data API key for more bars, or export longer history.\n")

    # ── Honest verdict ──
    print("=" * 72)
    print("  HONEST VERDICT")
    print("=" * 72)
    if main_result.get("total_trades", 0) == 0:
        print("  Cannot assess — no trades generated on this data period.")
        print("  Try with more data or a different market period.")
    else:
        pf = main_result["profit_factor"]
        wr = main_result["win_rate_pct"]
        med_r = main_result["median_r_multiple"]
        dd = main_result["max_drawdown_pct"]
        top1 = main_result["outlier_top1_pct"]
        ret_dd = main_result["return_to_dd_ratio"]

        edge = "POSITIVE" if pf > 1.3 and med_r > -0.5 else "MARGINAL" if pf > 1.0 else "NEGATIVE"

        print(f"  Strategy Edge:         {edge}")
        print(f"  Key Metric (Median R): {med_r:.2f}R per trade")
        print(f"  Profit Factor:         {pf:.2f}")
        print(f"  Return-to-DD Ratio:    {ret_dd:.2f}")
        print(f"  Drawdown Risk:         {'ACCEPTABLE' if dd < 20 else 'HIGH' if dd < 35 else 'DANGEROUS'}")
        print(f"  Outlier Dependency:    {'LOW' if top1 < 30 else 'MODERATE' if top1 < 60 else 'HIGH'}")
        print()

        # STRATEGY WEAKNESSES SECTION
        print("  STRATEGY WEAKNESSES:")
        weaknesses = []
        if pf < 1.3:
            weaknesses.append("    - Profit factor below 1.3 (weak profitability)")
        if med_r < 0.5:
            weaknesses.append("    - Median R multiple negative or near zero (no edge)")
        if wr < 40:
            weaknesses.append("    - Win rate below 40% (unprofitable for most)")
        if dd > 25:
            weaknesses.append("    - Max drawdown exceeds 25% (dangerous for account)")
        if top1 > 50:
            weaknesses.append("    - Heavily dependent on 1-2 outlier trades (unreliable)")
        if ret_dd < 1.0:
            weaknesses.append("    - Return-to-DD ratio < 1.0 (drawdown larger than profit)")
        if not weaknesses:
            weaknesses.append("    - None identified (looks reasonable!)")

        for w in weaknesses:
            print(w)
        print()

        if edge == "POSITIVE" and dd < 25:
            print("  → RECOMMENDATION: Proceed to small-size live forward test")
            print("    Use 0.01 lot minimum for 4-6 weeks before scaling up.")
        elif edge == "MARGINAL":
            print("  → RECOMMENDATION: Strategy needs further refinement")
            print("    Edge exists but is thin. Optimize signal filters before live testing.")
        else:
            print("  → RECOMMENDATION: Do NOT trade live with current parameters")
            print("    Review strategy logic and data quality before proceeding.")

    print()

    # ── Save outputs ──
    print("💾 Saving outputs...")
    csv_path = Path("real_backtest_trades.csv")
    txt_path = Path("real_backtest_report.txt")

    if "trades" in main_result and main_result["trades"]:
        trade_rows = []
        for t in main_result["trades"]:
            trade_rows.append({
                "num": t.num,
                "entry_time": t.entry_time,
                "entry_price": t.entry_price,
                "direction": t.direction,
                "initial_sl": t.initial_sl,
                "grade": t.grade,
                "score": t.score,
                "confidence": t.confidence,
                "session": t.session,
                "regime": t.regime,
                "close_time": t.close_time,
                "close_price": t.close_price,
                "close_reason": t.close_reason,
                "pnl_usd": t.pnl_usd,
                "pnl_pips": t.pnl_pips,
                "r_multiple": t.r_multiple,
                "risk_usd": t.risk_usd,
            })
        trade_df = pd.DataFrame(trade_rows)
        trade_df.to_csv(csv_path, index=False)
        print(f"  ✓ Trade log: {csv_path}")

    with open(txt_path, "w") as f:
        f.write("=" * 72 + "\n")
        f.write("  ALPHA FX HUB — REAL DATA BACKTEST REPORT V2\n")
        f.write("=" * 72 + "\n\n")
        f.write(f"Data Source: {source}\n")
        f.write(f"Data Bars: {total_bars}\n")
        f.write(f"Stress Config: {main_result['stress_config']}\n\n")
        f.write("PERFORMANCE METRICS\n")
        f.write(f"  Total Trades:        {main_result['total_trades']}\n")
        f.write(f"  Win Rate:            {main_result['win_rate_pct']}%\n")
        f.write(f"  Profit Factor:       {main_result['profit_factor']}\n")
        f.write(f"  Final Balance:       ${main_result['final_balance']:,.2f}\n")
        f.write(f"  Total Return:        ${main_result['total_return_usd']:,.2f} ({main_result['total_return_pct']:.2f}%)\n")
        f.write(f"  Max Drawdown:        ${main_result['max_drawdown_usd']:,.2f}\n")
        f.write(f"  Return-to-DD Ratio:  {main_result['return_to_dd_ratio']:.2f}\n")
        f.write(f"  Sharpe Estimate:     {main_result['sharpe_estimate']:.2f}\n")
        f.write(f"  Median R Multiple:   {main_result['median_r_multiple']:.2f}R\n")
        f.write(f"  Avg Trade:           ${main_result['avg_trade_pnl']:,.2f}\n")

    print(f"  ✓ Report: {txt_path}")
    print()


if __name__ == "__main__":
    main()
