#!/usr/bin/env python3
"""
Alpha FX Hub — Real Data Backtester V3.1 (FIXED)
===================================================
Addresses all structural problems found in autopsy:

FIX 1: Grade filter — ONLY trade A+ and A grades (score >= 68)
FIX 2: Confirmation candle — require bullish/bearish close after signal
FIX 3: Wider SL — minimum 1.0x ATR, max 2.5x ATR
FIX 4: Cooldown — 4 hours minimum between trades (16 bars on M15)
FIX 5: Volatility filter — skip low-vol (ADX < 20) and extreme-vol (ATR spike)
FIX 6: Session filter — ONLY London Open KZ (07-10) and NY Open KZ (12-15)
FIX 7: Trend confirmation — EMA50 slope must be strong (> 0.5 ATR per 10 bars)
FIX 8: No re-entry same direction after SL — wait for structure shift

Philosophy: 5 high-quality trades > 30 random ones getting stopped out.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from pathlib import Path

PIP = 0.1
PIP_VALUE_PER_LOT = 10.0


# ════════════════════════════════════════════════════════════════
# DATA FETCHING (same as V2)
# ════════════════════════════════════════════════════════════════

def load_csv(filepath: str) -> Optional[pd.DataFrame]:
    try:
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
            return None
        df["time"] = pd.to_datetime(df["time"])
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        if "volume" not in df.columns:
            df["volume"] = 1000
        df = df.sort_values("time").reset_index(drop=True)
        return df[["time", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        print(f"  CSV load failed: {e}")
        return None


def fetch_yfinance() -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="60d", interval="15m")
        if df.empty:
            return None
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "time", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })
        df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
        df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
        return df
    except:
        return None


def get_real_data(csv_path: str = None) -> Tuple[pd.DataFrame, str]:
    if csv_path and os.path.exists(csv_path):
        df = load_csv(csv_path)
        if df is not None and len(df) > 100:
            return df, f"CSV ({csv_path})"
    
    api_key = os.environ.get("TWELVE_DATA_API_KEY", "")
    if api_key and len(api_key) > 5:
        try:
            import urllib.request
            url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5000&apikey={api_key}&format=JSON"
            req = urllib.request.Request(url, headers={"User-Agent": "AlphaFXHub/3.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            if "values" in data:
                rows = data["values"]
                df = pd.DataFrame(rows)
                df["time"] = pd.to_datetime(df["datetime"])
                for col in ["open", "high", "low", "close"]:
                    df[col] = df[col].astype(float)
                df = df.sort_values("time").reset_index(drop=True)
                df["volume"] = ((df["high"] - df["low"]) * 1000).astype(int).clip(lower=100)
                df = df[["time", "open", "high", "low", "close", "volume"]]
                if len(df) > 100:
                    return df, "Twelve Data API (M15)"
        except:
            pass

    df = fetch_yfinance()
    if df is not None and len(df) > 100:
        return df, "yfinance GC=F (M15, 60 days)"

    print("No data source available. Use --csv or set TWELVE_DATA_API_KEY.")
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

    df["swing_low_5"] = df["low"].rolling(5).min()
    df["swing_high_5"] = df["high"].rolling(5).max()
    df["swing_low_20"] = df["low"].rolling(20).min()
    df["swing_high_20"] = df["high"].rolling(20).max()

    # EMA50 slope (trend strength)
    df["ema50_slope"] = df["ema50"].diff(10) / df["atr14"].replace(0, 1)

    # ATR moving average for volatility regime
    df["atr_ma50"] = df["atr14"].rolling(50).mean().bfill()

    # Market regime
    df["regime"] = "unknown"
    for i in range(50, len(df)):
        adx_val = df["adx"].iloc[i]
        slope = df["ema50_slope"].iloc[i] if not np.isnan(df["ema50_slope"].iloc[i]) else 0
        atr_ratio = df["atr14"].iloc[i] / df["atr_ma50"].iloc[i] if df["atr_ma50"].iloc[i] > 0 else 1

        if atr_ratio > 1.8:
            df.iloc[i, df.columns.get_loc("regime")] = "high_volatility"
        elif adx_val > 25 and abs(slope) > 0.5:
            df.iloc[i, df.columns.get_loc("regime")] = "trend"
        elif adx_val < 20:
            df.iloc[i, df.columns.get_loc("regime")] = "range"
        else:
            df.iloc[i, df.columns.get_loc("regime")] = "transition"

    return df


# ════════════════════════════════════════════════════════════════
# SIGNAL EVALUATION V3.1 — Quality over quantity
# ════════════════════════════════════════════════════════════════

def evaluate_signal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """
    V3.1 Signal Evaluation — STRICT filters.
    
    Key changes from V3:
    - Require ADX >= 20 (was 15)
    - Require EMA50 slope > 0.5 ATR/10bars (trend confirmation)
    - ONLY trade during killzones: London 07-10, NY 12-15
    - Score threshold: minimum A grade (68+)
    - Confirmation: last candle must close in signal direction
    """
    if idx < 200:
        return None

    row = df.iloc[idx]
    prev = df.iloc[idx - 1]
    close = float(row["close"])
    prev_close = float(prev["close"])
    prev_open = float(prev["open"])
    ema9 = float(row["ema9"])
    ema20 = float(row["ema20"])
    ema50 = float(row["ema50"])
    ema200 = float(row["ema200"])
    rsi = float(row["rsi14"])
    atr = float(row["atr14"])
    adx = float(row["adx"])
    atr_ratio = float(row["atr14"]) / float(row["atr_ma50"]) if float(row["atr_ma50"]) > 0 else 1
    ema50_slope = float(row["ema50_slope"]) if not np.isnan(row["ema50_slope"]) else 0

    hour = row["time"].hour if hasattr(row["time"], "hour") else 12

    # ══ STRICT FILTERS ══

    # FIX 6: Killzone ONLY — London Open (07-10 UTC) and NY Open (12-15 UTC)
    in_killzone = (7 <= hour < 10) or (12 <= hour < 15)
    if not in_killzone:
        return None

    # FIX 5: ADX minimum 20 (was 15) — need real trend
    if adx < 20:
        return None

    # FIX 5: Skip extreme volatility (ATR spike > 2x normal)
    if atr_ratio > 2.0:
        return None

    # FIX 7: EMA50 slope must show real trend momentum
    if abs(ema50_slope) < 0.3:
        return None

    # Multi-timeframe alignment (STRONG only)
    bull_strong = ema9 > ema20 > ema50 and close > ema50 and close > ema200
    bear_strong = ema9 < ema20 < ema50 and close < ema50 and close < ema200
    bull_moderate = ema9 > ema20 and close > ema50 and close > ema200
    bear_moderate = ema9 < ema20 and close < ema50 and close < ema200

    if bull_strong or bull_moderate:
        direction = "BUY"
    elif bear_strong or bear_moderate:
        direction = "SELL"
    else:
        return None  # No weak signals in V3.1

    # FIX 7: Slope must agree with direction
    if direction == "BUY" and ema50_slope < 0.3:
        return None
    if direction == "SELL" and ema50_slope > -0.3:
        return None

    # RSI filter (tighter)
    if direction == "BUY" and rsi > 70:
        return None
    if direction == "SELL" and rsi < 30:
        return None

    # FIX 2: Confirmation candle — previous candle must close in signal direction
    if direction == "BUY" and prev_close <= prev_open:
        return None  # Need bullish candle
    if direction == "SELL" and prev_close >= prev_open:
        return None  # Need bearish candle

    # ══ SCORING ══
    score = 0
    confirmations = 0

    # M1: MTF Alignment
    if bull_strong or bear_strong:
        score += 15; confirmations += 1
    elif bull_moderate or bear_moderate:
        score += 10; confirmations += 1

    # M2: ADX
    if adx > 35: score += 12; confirmations += 1
    elif adx > 25: score += 8; confirmations += 1
    elif adx > 20: score += 5; confirmations += 1

    # M3: S/D Zone Proximity
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

    # M4: FVG
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

    # M6: Killzone bonus (already filtered, but grade higher for prime zones)
    if 7 <= hour < 10:
        score += 8; confirmations += 1  # London open = best
    elif 12 <= hour < 15:
        score += 8; confirmations += 1  # NY open = best

    # M7: RSI sweet spot
    if direction == "BUY" and 35 < rsi < 55:
        score += 7; confirmations += 1
    elif direction == "SELL" and 45 < rsi < 65:
        score += 7; confirmations += 1

    # M8: Momentum
    if len(lookback) > 10:
        mom = (close - float(lookback.iloc[-10]["close"])) / max(atr, 0.5)
        if direction == "BUY" and mom > 0.8:
            score += 12; confirmations += 1
        elif direction == "SELL" and mom < -0.8:
            score += 12; confirmations += 1
        elif (direction == "BUY" and mom > 0.4) or (direction == "SELL" and mom < -0.4):
            score += 6

    # M9: EMA pullback entry (price near ema20, in direction of ema50)
    if direction == "BUY" and abs(close - ema20) < atr * 0.4 and close > ema50:
        score += 10; confirmations += 1
    elif direction == "SELL" and abs(close - ema20) < atr * 0.4 and close < ema50:
        score += 10; confirmations += 1

    # M10: DI confirmation (institutional proxy)
    plus_di = float(row.get("plus_di", 0))
    minus_di = float(row.get("minus_di", 0))
    di_spread = abs(plus_di - minus_di)
    if direction == "BUY" and plus_di > minus_di and di_spread > 12:
        score += 10; confirmations += 1
    elif direction == "SELL" and minus_di > plus_di and di_spread > 12:
        score += 10; confirmations += 1

    # FIX 1: STRICT grade — only A+ and A
    if score >= 85: grade = "A+"
    elif score >= 68: grade = "A"
    elif score >= 55: grade = "B"
    else: grade = "BLOCKED"

    if grade == "BLOCKED" or grade == "B":
        return None

    if confirmations < 5:
        return None  # Need at least 5 independent confirmations

    if confirmations >= 8: confidence = "SNIPER"
    elif confirmations >= 6: confidence = "HIGH"
    else: confidence = "MEDIUM"

    session = "London Open" if 7 <= hour < 10 else "NY Open" if 12 <= hour < 15 else "Other"
    regime = str(row.get("regime", "unknown"))

    # FIX: Don't trade range or unknown regimes
    if regime in ("range", "unknown"):
        return None

    return {
        "direction": direction, "score": score, "grade": grade,
        "confidence": confidence, "session": session, "atr": atr,
        "confirmations": confirmations, "regime": regime,
    }


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
# BACKTEST ENGINE V3.1
# ════════════════════════════════════════════════════════════════

LOT_PCT = [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]
TRAILING_RULES = {1: "breakeven", 3: 1, 5: 3, 7: 5, 9: 7}
TP_RISK_MULTIPLES = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 9.0, 12.0]


def run_real_backtest(df: pd.DataFrame, spread_pips: float = 2.0,
                      slippage_pips: float = 0.5,
                      starting_balance: float = 10000.0,
                      risk_pct: float = 2.0, start_idx: int = 200) -> Dict:

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
    last_sl_direction = None  # FIX 8: Track last SL direction

    total_cost = (spread_pips + slippage_pips) * PIP

    for idx in range(start_idx, len(df)):
        row = df.iloc[idx]
        current_time = row["time"]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        atr = float(row["atr14"]) if not np.isnan(row["atr14"]) else 3.0

        current_day = current_time.date() if hasattr(current_time, "date") else None
        if current_day != last_day:
            daily_loss = 0.0
            last_day = current_day
            last_sl_direction = None  # Reset at day boundary

        if daily_loss >= balance * 0.04:
            cooldown = max(cooldown, 96)

        # Process active trade
        if active_trade and active_trade.status == "active":
            old_bal = balance

            # Check SL with gap-through
            if active_trade.direction == "BUY" and low <= active_trade.sl:
                fill_price = min(active_trade.sl, low) - 0.3 * PIP  # Slippage on stop
                close_trade(active_trade, fill_price, current_time, "SL Hit", balance)
                balance += active_trade.pnl_usd
                last_sl_direction = "BUY"
            elif active_trade.direction == "SELL" and high >= active_trade.sl:
                fill_price = max(active_trade.sl, high) + 0.3 * PIP
                close_trade(active_trade, fill_price, current_time, "SL Hit", balance)
                balance += active_trade.pnl_usd
                last_sl_direction = "SELL"
            else:
                process_tps(active_trade, high, low, close, current_time)
                if active_trade.status == "closed":
                    balance += active_trade.pnl_usd
                    last_sl_direction = None  # Winner resets

            if active_trade.status == "closed":
                pnl = balance - old_bal
                if pnl < 0:
                    daily_loss += abs(pnl)

        # New signal — with all V3.1 fixes
        if cooldown <= 0 and (active_trade is None or active_trade.status != "active"):
            signal = evaluate_signal(df, idx)
            if signal:
                # FIX 8: Don't re-enter same direction after SL
                if last_sl_direction and signal["direction"] == last_sl_direction:
                    cooldown = max(0, cooldown - 1)
                    continue

                direction = signal["direction"]
                entry = close + total_cost if direction == "BUY" else close - total_cost

                # FIX 3: WIDER SL — minimum 1.0x ATR, structure-based with ATR buffer
                swing_low = float(row["swing_low_20"]) if not np.isnan(row.get("swing_low_20", float("nan"))) else entry - atr
                swing_high = float(row["swing_high_20"]) if not np.isnan(row.get("swing_high_20", float("nan"))) else entry + atr

                if direction == "BUY":
                    structure_sl = swing_low - 2.0 * PIP  # Below swing with buffer
                    atr_sl = entry - 1.0 * atr  # Minimum 1.0x ATR
                    sl = min(structure_sl, atr_sl)  # Use the WIDER one (further from entry)
                    # Clamp: min 1.0 ATR, max 2.5 ATR
                    if abs(entry - sl) < 1.0 * atr:
                        sl = entry - 1.0 * atr
                    if abs(entry - sl) > 2.5 * atr:
                        sl = entry - 2.5 * atr
                else:
                    structure_sl = swing_high + 2.0 * PIP
                    atr_sl = entry + 1.0 * atr
                    sl = max(structure_sl, atr_sl)
                    if abs(sl - entry) < 1.0 * atr:
                        sl = entry + 1.0 * atr
                    if abs(sl - entry) > 2.5 * atr:
                        sl = entry + 2.5 * atr

                sl = round(sl, 2)
                risk_pips_val = abs(entry - sl) / PIP
                if risk_pips_val <= 5 or risk_pips_val > 200:
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
                cooldown = 16  # FIX 4: 4 hours (16 x M15 bars)

        cooldown = max(0, cooldown - 1)

        if idx % 16 == 0:
            equity_curve.append((current_time, round(balance, 2)))
            if balance > peak_balance:
                peak_balance = balance
            dd = peak_balance - balance
            if dd > max_drawdown:
                max_drawdown = dd

    if active_trade and active_trade.status == "active":
        last_row = df.iloc[-1]
        close_trade(active_trade, float(last_row["close"]), last_row["time"],
                    "Backtest ended", balance)
        balance += active_trade.pnl_usd

    return compile_results(trades, balance, starting_balance, peak_balance,
                          max_drawdown, equity_curve, spread_pips, slippage_pips)


def process_tps(trade: Trade, high: float, low: float, close: float, current_time):
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
    trade.status = "closed"
    trade.close_time = close_time
    trade.close_price = close_price
    trade.close_reason = reason

    remaining_pnl = 0.0
    if trade.remaining_lot > 0.005:
        if trade.direction == "BUY":
            pips = (close_price - trade.entry_price) / PIP
        else:
            pips = (trade.entry_price - close_price) / PIP
        remaining_pnl = trade.remaining_lot * pips * PIP_VALUE_PER_LOT

    partial_pnl = sum(pc["pnl_usd"] for pc in trade.partial_closes)
    trade.pnl_usd = round(partial_pnl + remaining_pnl, 2)

    risk_amount = abs(trade.entry_price - trade.initial_sl) / PIP * PIP_VALUE_PER_LOT * trade.initial_lot
    trade.r_multiple = round(trade.pnl_usd / risk_amount, 2) if risk_amount > 0 else 0.0

    if trade.direction == "BUY":
        trade.pnl_pips = round((close_price - trade.entry_price) / PIP, 1)
    else:
        trade.pnl_pips = round((trade.entry_price - close_price) / PIP, 1)


# ════════════════════════════════════════════════════════════════
# RESULTS COMPILATION
# ════════════════════════════════════════════════════════════════

def compile_results(trades, balance, starting_balance, peak_balance,
                   max_drawdown, equity_curve, spread_pips, slippage_pips) -> Dict:
    closed = [t for t in trades if t.status == "closed"]
    if not closed:
        return {"total_trades": 0, "error": "No trades generated"}

    wins = [t for t in closed if t.pnl_usd > 0]
    losses = [t for t in closed if t.pnl_usd <= 0]
    total_profit = sum(t.pnl_usd for t in wins) if wins else 0
    total_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0.001

    r_multiples = [t.r_multiple for t in closed]
    pnls = sorted([t.pnl_usd for t in closed], reverse=True)

    max_consec_w = max_consec_l = cur_w = cur_l = 0
    for t in closed:
        if t.pnl_usd > 0:
            cur_w += 1; cur_l = 0; max_consec_w = max(max_consec_w, cur_w)
        else:
            cur_l += 1; cur_w = 0; max_consec_l = max(max_consec_l, cur_l)

    total_pnl = sum(pnls)
    top1_pct = pnls[0] / abs(total_pnl) * 100 if total_pnl != 0 else 0
    top3_pct = sum(pnls[:3]) / abs(total_pnl) * 100 if total_pnl != 0 and len(pnls) >= 3 else 0
    without_top1 = sum(pnls[1:])
    without_top3 = sum(pnls[3:]) if len(pnls) > 3 else 0

    by_session = {}
    for t in closed:
        s = t.session
        if s not in by_session:
            by_session[s] = {"trades": 0, "wins": 0, "pnl": 0.0, "r_multiples": []}
        by_session[s]["trades"] += 1
        if t.pnl_usd > 0: by_session[s]["wins"] += 1
        by_session[s]["pnl"] += t.pnl_usd
        by_session[s]["r_multiples"].append(t.r_multiple)

    by_regime = {}
    for t in closed:
        r = t.regime
        if r not in by_regime:
            by_regime[r] = {"trades": 0, "wins": 0, "pnl": 0.0, "r_multiples": []}
        by_regime[r]["trades"] += 1
        if t.pnl_usd > 0: by_regime[r]["wins"] += 1
        by_regime[r]["pnl"] += t.pnl_usd
        by_regime[r]["r_multiples"].append(t.r_multiple)

    ret_dd = round((balance - starting_balance) / max_drawdown, 2) if max_drawdown > 0 else 0

    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "profit_factor": round(total_profit / total_loss, 2),
        "total_return_usd": round(balance - starting_balance, 2),
        "total_return_pct": round((balance - starting_balance) / starting_balance * 100, 2),
        "final_balance": round(balance, 2),
        "avg_r_multiple": round(np.mean(r_multiples), 2),
        "median_r_multiple": round(float(np.median(r_multiples)), 2),
        "max_drawdown_usd": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown / peak_balance * 100, 1) if peak_balance > 0 else 0,
        "max_consecutive_wins": max_consec_w,
        "max_consecutive_losses": max_consec_l,
        "best_trade": round(max(t.pnl_usd for t in closed), 2),
        "worst_trade": round(min(t.pnl_usd for t in closed), 2),
        "avg_tps_reached": round(np.mean([t.tp_hit for t in closed]), 1),
        "outlier_top1_pct": round(top1_pct, 1),
        "outlier_top3_pct": round(top3_pct, 1),
        "without_top1_profitable": without_top1 > 0,
        "without_top1_pnl": round(without_top1, 2),
        "return_to_dd_ratio": ret_dd,
        "spread_pips": spread_pips,
        "slippage_pips": slippage_pips,
        "by_session": by_session,
        "by_regime": by_regime,
        "trades": closed,
    }


# ════════════════════════════════════════════════════════════════
# REPORT + WALK-FORWARD
# ════════════════════════════════════════════════════════════════

def print_report(r: Dict, source: str, bars: int):
    print("=" * 72)
    print("  ALPHA FX HUB — V3.1 BACKTEST (FIXED STRATEGY)")
    print("=" * 72)
    print(f"  Data: {source} ({bars} bars)")
    print(f"  Spread: {r['spread_pips']} + {r['slippage_pips']} slip = {r['spread_pips']+r['slippage_pips']} total")
    print()

    if r.get("total_trades", 0) == 0:
        print("  NO TRADES — filters are very strict. Need more data or adjust.")
        return

    print(f"  Total Trades:     {r['total_trades']}")
    print(f"  Win/Loss:         {r['wins']}/{r['losses']}")
    print(f"  Win Rate:         {r['win_rate_pct']}%")
    print(f"  Profit Factor:    {r['profit_factor']}")
    print(f"  Total Return:     ${r['total_return_usd']:+,.2f} ({r['total_return_pct']:+.2f}%)")
    print(f"  Max Drawdown:     ${r['max_drawdown_usd']:,.2f} ({r['max_drawdown_pct']:.1f}%)")
    print(f"  Return/DD Ratio:  {r['return_to_dd_ratio']:.2f}")
    print(f"  Avg R:            {r['avg_r_multiple']:.2f}R")
    print(f"  Median R:         {r['median_r_multiple']:.2f}R")
    print(f"  Consec W/L:       {r['max_consecutive_wins']}/{r['max_consecutive_losses']}")
    print(f"  Outlier Top1:     {r['outlier_top1_pct']:.0f}%")
    print()

    print("  BY SESSION:")
    for s_name in ["London Open", "NY Open", "Other"]:
        s = r["by_session"].get(s_name, {})
        if s.get("trades", 0):
            wr = s["wins"] / s["trades"] * 100
            mr = np.median(s["r_multiples"]) if s["r_multiples"] else 0
            print(f"    {s_name:15s} {s['trades']:2d}t | WR {wr:.0f}% | PnL ${s['pnl']:+,.2f} | MedR {mr:+.2f}")

    print("\n  BY REGIME:")
    for regime in ["trend", "transition", "high_volatility"]:
        rg = r["by_regime"].get(regime, {})
        if rg.get("trades", 0):
            wr = rg["wins"] / rg["trades"] * 100
            mr = np.median(rg["r_multiples"]) if rg["r_multiples"] else 0
            print(f"    {regime:18s} {rg['trades']:2d}t | WR {wr:.0f}% | PnL ${rg['pnl']:+,.2f} | MedR {mr:+.2f}")
    print()

    # Individual trades
    print("  TRADE LOG:")
    for t in r["trades"]:
        sym = "+" if t.pnl_usd > 0 else "-"
        print(f"    #{t.num:2d} {str(t.entry_time)[:16]} {t.direction:<4s} {t.grade:3s} s={t.score:3d} "
              f"R={t.r_multiple:+.2f} ${t.pnl_usd:+8.2f} TP{t.tp_hit} [{t.close_reason}]")
    print()


def walk_forward(df, n_folds=5, spread_pips=2.0, slippage_pips=0.5):
    usable = len(df) - 200
    fold_size = usable // n_folds
    results = []
    for fold in range(n_folds):
        start = 200 + fold * fold_size
        end = min(start + fold_size, len(df))
        fold_df = df.iloc[:end].copy().reset_index(drop=True)
        r = run_real_backtest(fold_df, spread_pips, slippage_pips, start_idx=start)
        r["fold"] = fold + 1
        results.append(r)
    return results


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alpha FX Hub V3.1 Backtester")
    parser.add_argument("--csv", help="Path to XAUUSD M15 CSV")
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--risk", type=float, default=2.0)
    args = parser.parse_args()

    # Load .env
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"'))

    print("\n" + "=" * 72)
    print("  ALPHA FX HUB — V3.1 REAL DATA VALIDATION")
    print("  8 fixes applied from autopsy analysis")
    print("=" * 72)

    # Use existing downloaded data if available
    csv_path = args.csv
    if not csv_path:
        default_csv = Path(__file__).parent / "xauusd_m15_data.csv"
        if default_csv.exists():
            csv_path = str(default_csv)
            print(f"\n  Using existing data: {csv_path}")

    df, source = get_real_data(csv_path=csv_path)
    bars = len(df)
    print(f"  Data: {source} — {bars} bars")

    df = add_indicators(df)
    print(f"  Indicators computed. ATR: ${df['atr14'].min():.2f}-${df['atr14'].max():.2f}")

    # Main backtest
    print("\n  Running V3.1 backtest...")
    result = run_real_backtest(df, spread_pips=2.0, slippage_pips=0.5,
                               starting_balance=args.balance, risk_pct=args.risk)
    print_report(result, source, bars)

    # Stress test
    print("  STRESS TESTS:")
    for sp, sl in [(2.0, 0.5), (2.5, 0.5), (3.0, 1.0), (4.0, 1.5)]:
        r = run_real_backtest(df, sp, sl, args.balance, args.risk)
        t = r["total_trades"]
        if t == 0:
            print(f"    {sp}/{sl}: No trades")
        else:
            print(f"    {sp}/{sl}: {t:2d}t | WR {r['win_rate_pct']}% | PF {r['profit_factor']:.2f} "
                  f"| Ret {r['total_return_pct']:+.2f}% | MedR {r['median_r_multiple']:+.2f} | DD {r['max_drawdown_pct']:.1f}%")
    print()

    # Save
    if result.get("trades"):
        rows = [{"num": t.num, "time": t.entry_time, "dir": t.direction,
                 "grade": t.grade, "score": t.score, "r": t.r_multiple,
                 "pnl": t.pnl_usd, "tp_hit": t.tp_hit, "reason": t.close_reason}
                for t in result["trades"]]
        pd.DataFrame(rows).to_csv("v31_backtest_trades.csv", index=False)
        print("  Saved: v31_backtest_trades.csv")

    # Verdict
    print("\n" + "=" * 72)
    if result["total_trades"] == 0:
        print("  V3.1 produced 0 trades on this data.")
        print("  This means the filters are working — garbage trades are blocked.")
        print("  Need more data (3-6 months minimum) to see if quality setups exist.")
        print("  OR the signal logic itself needs rethinking for real XAUUSD.")
    elif result["profit_factor"] > 1.3 and result["median_r_multiple"] > 0:
        print("  V3.1 shows POSITIVE EDGE. Proceed to forward test with 0.01 lots.")
    elif result["profit_factor"] > 1.0:
        print("  V3.1 shows MARGINAL EDGE. Needs more data to confirm.")
    else:
        print("  V3.1 still NEGATIVE. Strategy concept may need fundamental rework.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
