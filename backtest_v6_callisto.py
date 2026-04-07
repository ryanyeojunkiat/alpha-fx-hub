#!/usr/bin/env python3
"""
XAUUSD V6 — Callisto FX Backtester
====================================
Full backtest of Gold Engine V6 Callisto framework on real Dukascopy data.

Framework: T.R.C. (Trend × Reversal × Continuation)
SL: Fixed 40 pips always
TP: TP1 = 40 pips, TP2 = 80, TP3 = 120 ... TP10 = 630 pips
Sessions: London (07-16 UTC) + NY (12-21 UTC) only
Max: 2 losses per day
Risk: 2% per trade (conservative)

Data: Dukascopy XAUUSD M15 (Oct 2025 — Apr 2026)
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# ============================================================================
# CONSTANTS
# ============================================================================
PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
FIXED_SL_PIPS = 40.0
SPREAD_PIPS = 2.5
SLIPPAGE_PIPS = 0.5

# 10-TP system: cumulative pips from entry
TP_PIPS = [40, 80, 120, 160, 210, 270, 350, 430, 530, 630]
# Percentage to close at each TP
TP_CLOSE_PCT = [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]

# Session hours (UTC)
LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21

# Risk
DEFAULT_BALANCE = 10_000
RISK_PCT = 2.0
MAX_DAILY_LOSSES = 2


# ============================================================================
# DATA LOADING & AGGREGATION
# ============================================================================
def load_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def aggregate_tf(m15: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate M15 bars to higher TF (1h, 4h, 1D)."""
    df = m15.copy()
    df = df.set_index("time")
    agg = df.resample(freq).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna()
    return agg.reset_index()


# ============================================================================
# INDICATORS (lightweight for backtest speed)
# ============================================================================
def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def add_bt_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add indicators needed for backtest."""
    df = df.copy()
    c = df["close"].astype(float)
    df["ema9"] = calc_ema(c, 9)
    df["ema20"] = calc_ema(c, 20)
    df["ema21"] = calc_ema(c, 21)
    df["ema50"] = calc_ema(c, 50)
    df["ema200"] = calc_ema(c, 200)
    df["sma44"] = c.rolling(44).mean()
    df["atr14"] = calc_atr(df, 14)
    df["rsi14"] = calc_rsi(c, 14)
    return df


# ============================================================================
# SWING POINTS
# ============================================================================
def find_swings(df: pd.DataFrame, left: int = 5, right: int = 5):
    """Find swing highs and swing lows."""
    highs, lows = [], []
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    for i in range(left, len(df) - right):
        if h[i] == max(h[i-left:i+right+1]):
            highs.append({"idx": i, "price": h[i]})
        if l[i] == min(l[i-left:i+right+1]):
            lows.append({"idx": i, "price": l[i]})
    return highs, lows


# ============================================================================
# CALLISTO FX SIGNAL LOGIC
# ============================================================================
def get_trend(df: pd.DataFrame) -> str:
    """Simple EMA-based trend."""
    if df is None or len(df) < 50:
        return "neutral"
    r = df.iloc[-1]
    e20, e50 = float(r["ema20"]), float(r["ema50"])
    c = float(r["close"])
    if "ema200" in df.columns:
        e200 = float(r["ema200"])
        if c > e50 and e50 > e200 and e20 > e50:
            return "bull"
        if c < e50 and e50 < e200 and e20 < e50:
            return "bear"
        if c > e200:
            return "bull_weak"
        if c < e200:
            return "bear_weak"
    else:
        if c > e50 and e20 > e50:
            return "bull"
        if c < e50 and e20 < e50:
            return "bear"
    return "neutral"


def detect_choch(df: pd.DataFrame, lookback: int = 30) -> dict:
    """Detect CHoCH with body-close check."""
    result = {"detected": False, "direction": None, "level": 0}
    if df is None or len(df) < lookback:
        return result

    highs, lows = find_swings(df, left=3, right=3)
    if len(highs) < 3 or len(lows) < 3:
        return result

    rh = [h["price"] for h in highs[-5:]]
    rl = [l["price"] for l in lows[-5:]]
    last_close = float(df["close"].iloc[-1])

    # Bearish CHoCH
    if rh[-3] < rh[-2] and rl[-1] < rl[-2]:
        if last_close < rl[-2]:
            result = {"detected": True, "direction": "bearish", "level": rl[-2]}
            return result

    # Bullish CHoCH
    if rl[-3] > rl[-2] and rh[-1] > rh[-2]:
        if last_close > rh[-2]:
            result = {"detected": True, "direction": "bullish", "level": rh[-2]}

    return result


def detect_bos(df: pd.DataFrame, direction: str) -> bool:
    """Detect Break of Structure."""
    if df is None or len(df) < 20:
        return False
    highs, lows = find_swings(df, left=3, right=2)
    if direction == "BUY" and len(highs) >= 2:
        return highs[-1]["price"] > highs[-2]["price"]
    if direction == "SELL" and len(lows) >= 2:
        return lows[-1]["price"] < lows[-2]["price"]
    return False


def detect_premium_discount(df: pd.DataFrame) -> dict:
    """Premium/Discount zone."""
    if df is None or len(df) < 30:
        return {"zone": "neutral", "bias": "NEUTRAL", "pct": 50}
    highs, lows = find_swings(df, left=5, right=5)
    if not highs or not lows:
        return {"zone": "neutral", "bias": "NEUTRAL", "pct": 50}
    sh = max(h["price"] for h in highs[-5:])
    sl = min(l["price"] for l in lows[-5:])
    price = float(df["close"].iloc[-1])
    rng = sh - sl
    if rng <= 0:
        return {"zone": "neutral", "bias": "NEUTRAL", "pct": 50}
    pct = (price - sl) / rng * 100
    if pct <= 40:
        return {"zone": "discount", "bias": "BUY", "pct": pct}
    elif pct >= 60:
        return {"zone": "premium", "bias": "SELL", "pct": pct}
    return {"zone": "equilibrium", "bias": "NEUTRAL", "pct": pct}


def callisto_signal(i: int, m15: pd.DataFrame, h1: pd.DataFrame,
                    h4: pd.DataFrame) -> Optional[dict]:
    """
    Generate Callisto FX signal at bar index i.

    TRC Framework:
    1. MTF alignment (2/3 rule on H4, H1, M15)
    2. CHoCH detected on M15 (body close)
    3. Premium/Discount array favorable
    4. Session = London or NY
    5. BOS confirmation bonus

    Returns signal dict or None.
    """
    if i < 200:
        return None

    bar = m15.iloc[i]
    hour = bar["time"].hour
    price = float(bar["close"])

    # ── Session filter: London + NY only ──
    in_london = LONDON_START <= hour < LONDON_END
    in_ny = NY_START <= hour < NY_END
    if not in_london and not in_ny:
        return None

    # Get H1 and H4 slices up to current time
    bar_time = bar["time"]
    h1_slice = h1[h1["time"] <= bar_time].tail(200)
    h4_slice = h4[h4["time"] <= bar_time].tail(200)
    m15_slice = m15.iloc[max(0, i-200):i+1]

    if len(h1_slice) < 50 or len(h4_slice) < 20 or len(m15_slice) < 50:
        return None

    # ── Step 1: MTF Trend Alignment (2/3 rule) ──
    h4_trend = get_trend(h4_slice)
    h1_trend = get_trend(h1_slice)
    m15_trend = get_trend(m15_slice)

    for direction in ["BUY", "SELL"]:
        target = "bull" if direction == "BUY" else "bear"
        aligned = 0
        for trend in [h4_trend, h1_trend, m15_trend]:
            if target in trend:
                aligned += 1

        if aligned < 2:
            continue  # Need 2/3 TFs

        # ── Step 2: CHoCH on M15 (body close) ──
        choch = detect_choch(m15_slice, lookback=30)
        if not choch["detected"]:
            continue
        choch_aligned = ((choch["direction"] == "bullish" and direction == "BUY") or
                        (choch["direction"] == "bearish" and direction == "SELL"))
        if not choch_aligned:
            continue

        # ── Step 3: Premium/Discount check ──
        pd_zone = detect_premium_discount(h4_slice)
        pd_favorable = (pd_zone["bias"] == direction or pd_zone["bias"] == "NEUTRAL")

        # ── BOS confirmation ──
        has_bos = detect_bos(h1_slice, direction)

        # ── SMA44 alignment (Breaker Block strategy) ──
        sma44 = float(m15_slice["sma44"].iloc[-1]) if "sma44" in m15_slice.columns and not pd.isna(m15_slice["sma44"].iloc[-1]) else None
        sma44_ok = False
        if sma44 is not None:
            sma44_ok = (direction == "BUY" and price > sma44) or (direction == "SELL" and price < sma44)

        # ── Score the setup ──
        score = 0
        score += aligned * 5       # MTF (10 or 15)
        score += 8                  # CHoCH confirmed
        score += 6 if pd_favorable else -5
        score += 5 if has_bos else 0
        score += 3 if sma44_ok else -2
        score += 3 if (in_london and in_ny) else 1  # overlap bonus

        # Only take score >= 18 (selective)
        if score < 18:
            continue

        # Determine grade
        if score >= 28 and pd_favorable and has_bos:
            grade = "A+"
        elif score >= 24:
            grade = "A"
        elif score >= 20:
            grade = "B"
        else:
            grade = "C"

        if grade not in ("A+", "A", "B"):
            continue  # Only take B or better

        return {
            "direction": direction,
            "price": price,
            "score": score,
            "grade": grade,
            "aligned": aligned,
            "choch": choch["direction"],
            "pd_zone": pd_zone["zone"],
            "pd_pct": pd_zone["pct"],
            "has_bos": has_bos,
            "sma44_ok": sma44_ok,
            "session": "LN/NY overlap" if (in_london and in_ny) else "London" if in_london else "NY",
            "bar_time": bar_time,
        }

    return None


# ============================================================================
# TRADE MANAGEMENT
# ============================================================================
@dataclass
class Trade:
    entry_time: datetime = None
    direction: str = ""
    entry_price: float = 0.0
    sl: float = 0.0
    tp_levels: list = field(default_factory=list)
    lot_size: float = 0.1
    grade: str = ""
    score: int = 0
    signal: dict = field(default_factory=dict)
    # State
    is_open: bool = True
    sl_moved_to_be: bool = False
    current_tp_idx: int = 0
    remaining_lot: float = 0.0
    partials_taken: list = field(default_factory=list)
    # Result
    exit_time: datetime = None
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0


def open_trade(signal: dict, balance: float) -> Trade:
    """Open a new trade from a signal."""
    direction = signal["direction"]
    price = signal["price"]
    spread_cost = SPREAD_PIPS * PIP
    slip_cost = SLIPPAGE_PIPS * PIP

    if direction == "BUY":
        entry = price + spread_cost + slip_cost
        sl = entry - FIXED_SL_PIPS * PIP
        tps = [round(entry + tp_pip * PIP, 2) for tp_pip in TP_PIPS]
    else:
        entry = price - spread_cost - slip_cost
        sl = entry + FIXED_SL_PIPS * PIP
        tps = [round(entry - tp_pip * PIP, 2) for tp_pip in TP_PIPS]

    # Lot sizing: risk % of balance on 40-pip SL
    risk_amount = balance * (RISK_PCT / 100)
    lot = risk_amount / (FIXED_SL_PIPS * PIP_VALUE_PER_LOT)
    lot = max(0.01, min(5.0, round(lot, 2)))

    return Trade(
        entry_time=signal["bar_time"],
        direction=direction,
        entry_price=round(entry, 2),
        sl=round(sl, 2),
        tp_levels=tps,
        lot_size=lot,
        remaining_lot=lot,
        grade=signal["grade"],
        score=signal["score"],
        signal=signal,
    )


def manage_trade(trade: Trade, bar) -> Trade:
    """Check SL/TP hits on a bar, handle partials and trailing."""
    if not trade.is_open:
        return trade

    high = float(bar["high"])
    low = float(bar["low"])
    bar_time = bar["time"]

    is_buy = trade.direction == "BUY"

    # ── Check SL hit ──
    sl_hit = (low <= trade.sl) if is_buy else (high >= trade.sl)
    if sl_hit:
        trade.is_open = False
        trade.exit_time = bar_time
        trade.exit_price = trade.sl
        trade.exit_reason = "SL"
        total_pips = ((trade.sl - trade.entry_price) / PIP) if is_buy else ((trade.entry_price - trade.sl) / PIP)
        trade.pnl_pips = round(total_pips, 1)
        trade.pnl_usd = round(trade.remaining_lot * total_pips * PIP_VALUE_PER_LOT, 2)
        # Add PnL from any partials already taken
        for p in trade.partials_taken:
            trade.pnl_usd += p["pnl_usd"]
        return trade

    # ── Check TP levels ──
    while trade.current_tp_idx < len(trade.tp_levels):
        tp = trade.tp_levels[trade.current_tp_idx]
        tp_hit = (high >= tp) if is_buy else (low <= tp)

        if not tp_hit:
            break

        # TP hit — close partial
        close_pct = TP_CLOSE_PCT[trade.current_tp_idx]
        close_lot = round(trade.lot_size * close_pct, 2)
        close_lot = min(close_lot, trade.remaining_lot)

        if close_lot > 0:
            pips = TP_PIPS[trade.current_tp_idx]
            partial_pnl = round(close_lot * pips * PIP_VALUE_PER_LOT, 2)
            trade.partials_taken.append({
                "tp": trade.current_tp_idx + 1,
                "price": tp,
                "lot": close_lot,
                "pips": pips,
                "pnl_usd": partial_pnl,
            })
            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)

        # ── Move SL to breakeven after TP1 (Callisto rule) ──
        if trade.current_tp_idx == 0 and not trade.sl_moved_to_be:
            buffer = 2 * PIP
            if is_buy:
                trade.sl = trade.entry_price + buffer
            else:
                trade.sl = trade.entry_price - buffer
            trade.sl_moved_to_be = True

        # ── Trail SL at TP4 → move to TP2 level ──
        if trade.current_tp_idx == 3:
            trade.sl = trade.tp_levels[1]

        # ── Trail SL at TP7 → move to TP5 level ──
        if trade.current_tp_idx == 6:
            trade.sl = trade.tp_levels[4]

        trade.current_tp_idx += 1

        # If all TPs hit or no remaining lot
        if trade.current_tp_idx >= len(trade.tp_levels) or trade.remaining_lot <= 0.005:
            trade.is_open = False
            trade.exit_time = bar_time
            trade.exit_price = tp
            trade.exit_reason = f"TP{trade.current_tp_idx}"
            trade.pnl_pips = TP_PIPS[trade.current_tp_idx - 1]
            trade.pnl_usd = sum(p["pnl_usd"] for p in trade.partials_taken)
            return trade

    return trade


# ============================================================================
# MAIN BACKTEST
# ============================================================================
def run_backtest(csv_path: str):
    print("=" * 70)
    print("  GOLD ENGINE V6 CALLISTO — HISTORICAL BACKTEST")
    print("  Callisto FX TRC Framework | Fixed 40-Pip SL | 10-TP System")
    print("=" * 70)

    # Load data
    print("\n  Loading data...")
    m15 = load_csv(csv_path)
    m15 = add_bt_indicators(m15)

    h1 = aggregate_tf(m15, "1h")
    h1 = add_bt_indicators(h1)

    h4 = aggregate_tf(m15, "4h")
    h4 = add_bt_indicators(h4)

    print(f"  M15 bars: {len(m15):,}")
    print(f"  H1 bars:  {len(h1):,}")
    print(f"  H4 bars:  {len(h4):,}")
    print(f"  Period:   {m15['time'].iloc[0].date()} → {m15['time'].iloc[-1].date()}")
    print(f"  Price:    ${m15['close'].min():.2f} → ${m15['close'].max():.2f}")

    # Run backtest
    print("\n  Running backtest...")
    balance = DEFAULT_BALANCE
    peak_balance = balance
    max_drawdown = 0
    trades: List[Trade] = []
    open_trade_obj: Optional[Trade] = None
    daily_losses = {}
    cooldown_until = None

    for i in range(200, len(m15)):
        bar = m15.iloc[i]
        bar_date = bar["time"].date()
        bar_time = bar["time"]

        # Reset daily loss counter
        if bar_date not in daily_losses:
            daily_losses[bar_date] = 0

        # ── Manage open trade ──
        if open_trade_obj and open_trade_obj.is_open:
            open_trade_obj = manage_trade(open_trade_obj, bar)

            if not open_trade_obj.is_open:
                # Trade closed
                balance += open_trade_obj.pnl_usd
                trades.append(open_trade_obj)

                if open_trade_obj.exit_reason == "SL":
                    daily_losses[bar_date] = daily_losses.get(bar_date, 0) + 1
                    # Callisto: 2-hour cooldown after loss
                    cooldown_until = bar_time + timedelta(hours=2)

                # Track drawdown
                peak_balance = max(peak_balance, balance)
                dd = (peak_balance - balance) / peak_balance * 100
                max_drawdown = max(max_drawdown, dd)

                open_trade_obj = None
            continue

        # ── Check if we can trade ──
        if open_trade_obj and open_trade_obj.is_open:
            continue  # Already in a trade

        # Callisto: max 2 losses per day
        if daily_losses.get(bar_date, 0) >= MAX_DAILY_LOSSES:
            continue

        # Cooldown after loss
        if cooldown_until and bar_time < cooldown_until:
            continue

        # ── Generate signal ──
        signal = callisto_signal(i, m15, h1, h4)
        if signal is None:
            continue

        # ── Open trade ──
        open_trade_obj = open_trade(signal, balance)

    # Close any remaining open trade at last bar
    if open_trade_obj and open_trade_obj.is_open:
        last_bar = m15.iloc[-1]
        open_trade_obj.is_open = False
        open_trade_obj.exit_time = last_bar["time"]
        open_trade_obj.exit_price = float(last_bar["close"])
        open_trade_obj.exit_reason = "END"
        pip_diff = (open_trade_obj.exit_price - open_trade_obj.entry_price) / PIP
        if open_trade_obj.direction == "SELL":
            pip_diff = -pip_diff
        open_trade_obj.pnl_pips = round(pip_diff, 1)
        partial_pnl = sum(p["pnl_usd"] for p in open_trade_obj.partials_taken)
        remaining_pnl = open_trade_obj.remaining_lot * pip_diff * PIP_VALUE_PER_LOT
        open_trade_obj.pnl_usd = round(partial_pnl + remaining_pnl, 2)
        balance += open_trade_obj.pnl_usd
        trades.append(open_trade_obj)

    # ============================================================================
    # RESULTS
    # ============================================================================
    print_results(trades, balance, max_drawdown)
    save_trades_csv(trades)
    return trades, balance


def print_results(trades: List[Trade], final_balance: float, max_dd: float):
    """Print comprehensive backtest results."""
    if not trades:
        print("\n  NO TRADES GENERATED")
        return

    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd < 0]
    breakeven = [t for t in trades if t.pnl_usd == 0]

    total_pnl = sum(t.pnl_usd for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = np.mean([t.pnl_usd for t in wins]) if wins else 0
    avg_loss = np.mean([t.pnl_usd for t in losses]) if losses else 0
    profit_factor = abs(sum(t.pnl_usd for t in wins) / min(sum(t.pnl_usd for t in losses), -0.01)) if losses else float('inf')

    # Pips
    total_pips = sum(t.pnl_pips for t in trades)
    avg_win_pips = np.mean([t.pnl_pips for t in wins]) if wins else 0
    avg_loss_pips = np.mean([t.pnl_pips for t in losses]) if losses else 0

    # By grade
    grades = {}
    for t in trades:
        g = t.grade
        if g not in grades:
            grades[g] = {"count": 0, "wins": 0, "pnl": 0}
        grades[g]["count"] += 1
        if t.pnl_usd > 0:
            grades[g]["wins"] += 1
        grades[g]["pnl"] += t.pnl_usd

    # TP distribution
    tp_dist = {}
    for t in trades:
        reason = t.exit_reason
        tp_dist[reason] = tp_dist.get(reason, 0) + 1

    # Streak analysis
    max_win_streak = 0
    max_loss_streak = 0
    current_streak = 0
    for t in trades:
        if t.pnl_usd > 0:
            current_streak = max(0, current_streak) + 1
            max_win_streak = max(max_win_streak, current_streak)
        elif t.pnl_usd < 0:
            current_streak = min(0, current_streak) - 1
            max_loss_streak = max(max_loss_streak, abs(current_streak))
        else:
            current_streak = 0

    # Session breakdown
    sessions = {"London": [], "NY": [], "LN/NY overlap": []}
    for t in trades:
        sess = t.signal.get("session", "Unknown")
        if sess in sessions:
            sessions[sess].append(t)

    print("\n" + "=" * 70)
    print("  BACKTEST RESULTS — GOLD ENGINE V6 CALLISTO")
    print("=" * 70)

    print(f"""
  ┌─────────────────────────────────────────────────────┐
  │  PERFORMANCE SUMMARY                                │
  ├─────────────────────────────────────────────────────┤
  │  Starting Balance:  ${DEFAULT_BALANCE:>10,.2f}                  │
  │  Final Balance:     ${final_balance:>10,.2f}                  │
  │  Net P&L:           ${total_pnl:>+10,.2f}  ({total_pnl/DEFAULT_BALANCE*100:+.1f}%)          │
  │  Total Pips:        {total_pips:>+10,.1f}                     │
  │  Max Drawdown:      {max_dd:>10.1f}%                     │
  ├─────────────────────────────────────────────────────┤
  │  TRADE STATISTICS                                   │
  ├─────────────────────────────────────────────────────┤
  │  Total Trades:      {len(trades):>10d}                       │
  │  Winners:           {len(wins):>10d}                       │
  │  Losers:            {len(losses):>10d}                       │
  │  Breakeven:         {len(breakeven):>10d}                       │
  │  Win Rate:          {win_rate:>10.1f}%                     │
  │  Profit Factor:     {profit_factor:>10.2f}                     │
  ├─────────────────────────────────────────────────────┤
  │  AVERAGES                                           │
  ├─────────────────────────────────────────────────────┤
  │  Avg Win:           ${avg_win:>+10,.2f}  ({avg_win_pips:+.0f} pips)     │
  │  Avg Loss:          ${avg_loss:>+10,.2f}  ({avg_loss_pips:+.0f} pips)    │
  │  Avg Win / Loss:    {abs(avg_win/min(avg_loss,-0.01)):>10.2f}x                     │
  ├─────────────────────────────────────────────────────┤
  │  STREAKS                                            │
  ├─────────────────────────────────────────────────────┤
  │  Max Win Streak:    {max_win_streak:>10d}                       │
  │  Max Loss Streak:   {max_loss_streak:>10d}                       │
  └─────────────────────────────────────────────────────┘""")

    print(f"\n  EXIT DISTRIBUTION:")
    for reason, count in sorted(tp_dist.items(), key=lambda x: -x[1]):
        pct = count / len(trades) * 100
        bar = "█" * int(pct / 2)
        print(f"    {reason:8s}: {count:3d} ({pct:5.1f}%) {bar}")

    print(f"\n  GRADE BREAKDOWN:")
    for g in sorted(grades.keys()):
        info = grades[g]
        wr = info["wins"] / info["count"] * 100 if info["count"] > 0 else 0
        print(f"    {g:4s}: {info['count']:3d} trades | WR: {wr:5.1f}% | P&L: ${info['pnl']:+,.2f}")

    print(f"\n  SESSION BREAKDOWN:")
    for sess, sess_trades in sessions.items():
        if sess_trades:
            sess_wins = sum(1 for t in sess_trades if t.pnl_usd > 0)
            sess_pnl = sum(t.pnl_usd for t in sess_trades)
            sess_wr = sess_wins / len(sess_trades) * 100
            print(f"    {sess:16s}: {len(sess_trades):3d} trades | WR: {sess_wr:5.1f}% | P&L: ${sess_pnl:+,.2f}")

    # Last 10 trades
    print(f"\n  LAST 10 TRADES:")
    print(f"    {'Time':20s} {'Dir':4s} {'Entry':>10s} {'Exit':>10s} {'Grade':5s} {'Exit':6s} {'P&L':>10s} {'Pips':>8s}")
    print(f"    {'─'*20} {'─'*4} {'─'*10} {'─'*10} {'─'*5} {'─'*6} {'─'*10} {'─'*8}")
    for t in trades[-10:]:
        print(f"    {str(t.entry_time)[:19]:20s} {t.direction:4s} ${t.entry_price:>9.2f} ${t.exit_price:>9.2f}"
              f" {t.grade:5s} {t.exit_reason:6s} ${t.pnl_usd:>+9.2f} {t.pnl_pips:>+7.1f}")


def save_trades_csv(trades: List[Trade]):
    """Save trade log to CSV."""
    rows = []
    for t in trades:
        rows.append({
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "sl": t.sl,
            "grade": t.grade,
            "score": t.score,
            "exit_reason": t.exit_reason,
            "lot_size": t.lot_size,
            "pnl_pips": t.pnl_pips,
            "pnl_usd": t.pnl_usd,
            "partials": len(t.partials_taken),
            "session": t.signal.get("session", ""),
            "choch": t.signal.get("choch", ""),
            "pd_zone": t.signal.get("pd_zone", ""),
            "aligned": t.signal.get("aligned", 0),
            "has_bos": t.signal.get("has_bos", False),
        })
    df = pd.DataFrame(rows)
    out_path = os.path.join(os.path.dirname(csv_path), "v6_callisto_trades.csv")
    df.to_csv(out_path, index=False)
    print(f"\n  Trade log saved: {out_path}")


# ============================================================================
if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "dukascopy_xauusd_m15.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: Data file not found: {csv_path}")
        sys.exit(1)
    run_backtest(csv_path)
