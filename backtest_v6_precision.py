#!/usr/bin/env python3
"""
XAUUSD V6 Callisto — Precision Scalp Backtester
=================================================
Fixed 40-pip SL — entries only when structure is within 40 pips.

The key principle: 40-pip SL on gold only works when you enter at
a structural level (swing low/high, CHoCH level, S&R) so the SL
sits behind that structure. Random entries with 40-pip SL = death.

Entry Rules:
1. MTF alignment (2/3 rule: H4, H1, M15)
2. M15 CHoCH detected + body close confirmed
3. Price MUST be within 20 pips of a recent swing point (structure)
4. SL placed behind the structure (max 40 pips)
5. Rejection candle or engulfing at the level = confirmation
6. Session = London or NY only
7. Premium/Discount array favorable

TP: 40-pip minimum, scales with structure.
Partials: 50% at TP1 (40 pips), SL to BE, trail runner.
"""

import sys, os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, field

PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
FIXED_SL_PIPS = 40.0
SPREAD_PIPS = 2.5
SLIPPAGE_PIPS = 0.5

# Simplified TP: TP1 at 40, close 50%. TP2 at 80, close 30%. Trail rest.
TP1_PIPS = 40
TP2_PIPS = 80
TP3_PIPS = 160
TP1_CLOSE_PCT = 0.50
TP2_CLOSE_PCT = 0.30
# Remaining 20% = runner

LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21
DEFAULT_BALANCE = 10_000
RISK_PCT = 2.0
MAX_DAILY_LOSSES = 2


def load_csv(filepath):
    df = pd.read_csv(filepath)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def aggregate_tf(m15, freq):
    df = m15.copy().set_index("time")
    agg = df.resample(freq).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return agg.reset_index()


def calc_ema(s, p):
    return s.ewm(span=p, adjust=False).mean()


def calc_atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_ind(df):
    df = df.copy()
    c = df["close"].astype(float)
    df["ema9"] = calc_ema(c, 9)
    df["ema20"] = calc_ema(c, 20)
    df["ema50"] = calc_ema(c, 50)
    df["ema200"] = calc_ema(c, 200)
    df["sma44"] = c.rolling(44).mean()
    df["atr14"] = calc_atr(df)
    return df


def find_swings(df, left=5, right=5):
    highs, lows = [], []
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    for i in range(left, len(df) - right):
        if h[i] == max(h[i-left:i+right+1]):
            highs.append({"idx": i, "price": h[i]})
        if l[i] == min(l[i-left:i+right+1]):
            lows.append({"idx": i, "price": l[i]})
    return highs, lows


def get_trend(df):
    if df is None or len(df) < 50:
        return "neutral"
    r = df.iloc[-1]
    e20, e50 = float(r["ema20"]), float(r["ema50"])
    c = float(r["close"])
    e200 = float(r.get("ema200", c))
    if c > e50 and e50 > e200 and e20 > e50:
        return "bull"
    if c < e50 and e50 < e200 and e20 < e50:
        return "bear"
    if c > e200:
        return "bull_weak"
    if c < e200:
        return "bear_weak"
    return "neutral"


def is_rejection_candle(bar, direction):
    """Check if bar is a rejection candle (hammer/shooting star)."""
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    body = abs(c - o)
    total = h - l
    if total < PIP * 5:  # Too small
        return False
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    if direction == "BUY":
        # Hammer: long lower wick, small body at top
        return lower_wick > body * 1.5 and upper_wick < body * 0.5
    else:
        # Shooting star: long upper wick, small body at bottom
        return upper_wick > body * 1.5 and lower_wick < body * 0.5


def is_engulfing(prev_bar, curr_bar, direction):
    """Check bullish/bearish engulfing."""
    po, pc = float(prev_bar["open"]), float(prev_bar["close"])
    co, cc = float(curr_bar["open"]), float(curr_bar["close"])
    if direction == "BUY":
        return pc < po and cc > co and cc > po and co < pc
    else:
        return pc > po and cc < co and cc < po and co > pc


def precision_signal(i, m15, h1, h4):
    """
    Precision entry: only when structure is within 40 pips.

    Logic:
    1. Find nearest swing point (support for BUY, resistance for SELL)
    2. Price must be within 20 pips of that swing (close to structure)
    3. SL goes behind the swing (structure_price - buffer)
    4. Total SL distance must be <= 40 pips
    5. Need MTF alignment + CHoCH + rejection/engulfing confirmation
    """
    if i < 200:
        return None

    bar = m15.iloc[i]
    prev_bar = m15.iloc[i-1]
    hour = bar["time"].hour
    price = float(bar["close"])
    bar_time = bar["time"]

    # Session filter
    in_london = LONDON_START <= hour < LONDON_END
    in_ny = NY_START <= hour < NY_END
    if not in_london and not in_ny:
        return None

    # Slice data
    h1_slice = h1[h1["time"] <= bar_time].tail(200)
    h4_slice = h4[h4["time"] <= bar_time].tail(200)
    m15_slice = m15.iloc[max(0, i-200):i+1]

    if len(h1_slice) < 50 or len(h4_slice) < 20 or len(m15_slice) < 50:
        return None

    # MTF trends
    h4_trend = get_trend(h4_slice)
    h1_trend = get_trend(h1_slice)
    m15_trend = get_trend(m15_slice)

    # Find swing points on M15
    highs, lows = find_swings(m15_slice, left=3, right=3)
    if len(highs) < 3 or len(lows) < 3:
        return None

    for direction in ["BUY", "SELL"]:
        target = "bull" if direction == "BUY" else "bear"

        # ── 2/3 MTF alignment ──
        aligned = sum(1 for t in [h4_trend, h1_trend, m15_trend] if target in t)
        if aligned < 2:
            continue

        # ── CHoCH detection ──
        rh = [h["price"] for h in highs[-5:]]
        rl = [l["price"] for l in lows[-5:]]
        last_close = price

        has_choch = False
        choch_level = 0

        if direction == "BUY":
            # Bullish CHoCH: was making LL, now broke a LH
            if len(rl) >= 3 and len(rh) >= 3:
                if rl[-3] > rl[-2] and rh[-1] > rh[-2] and last_close > rh[-2]:
                    has_choch = True
                    choch_level = rh[-2]
        else:
            # Bearish CHoCH: was making HH, now broke a HL
            if len(rh) >= 3 and len(rl) >= 3:
                if rh[-3] < rh[-2] and rl[-1] < rl[-2] and last_close < rl[-2]:
                    has_choch = True
                    choch_level = rl[-2]

        if not has_choch:
            continue

        # ── Find nearest structural level within 40 pips ──
        structure_price = 0
        sl_price = 0

        if direction == "BUY":
            # Find nearest swing low below price (support to hide SL behind)
            nearby_lows = [l for l in lows if l["price"] < price and (price - l["price"]) / PIP <= 45]
            if not nearby_lows:
                continue
            # Use the closest one
            nearest = max(nearby_lows, key=lambda x: x["price"])
            structure_price = nearest["price"]
            sl_price = structure_price - 5 * PIP  # 5 pip buffer below structure
            sl_distance = (price - sl_price) / PIP

            if sl_distance > FIXED_SL_PIPS or sl_distance < 10:
                continue
        else:
            # Find nearest swing high above price (resistance to hide SL behind)
            nearby_highs = [h for h in highs if h["price"] > price and (h["price"] - price) / PIP <= 45]
            if not nearby_highs:
                continue
            nearest = min(nearby_highs, key=lambda x: x["price"])
            structure_price = nearest["price"]
            sl_price = structure_price + 5 * PIP
            sl_distance = (sl_price - price) / PIP

            if sl_distance > FIXED_SL_PIPS or sl_distance < 10:
                continue

        # ── Rejection candle or engulfing confirmation ──
        has_rejection = is_rejection_candle(bar, direction)
        has_engulfing = is_engulfing(prev_bar, bar, direction)
        has_candle_confirm = has_rejection or has_engulfing

        # ── SMA44 alignment ──
        sma44 = float(m15_slice["sma44"].iloc[-1]) if not pd.isna(m15_slice["sma44"].iloc[-1]) else None
        sma44_ok = False
        if sma44:
            sma44_ok = (direction == "BUY" and price > sma44) or (direction == "SELL" and price < sma44)

        # ── Premium/Discount check ──
        pd_favorable = True
        if len(h4_slice) >= 30:
            h4_highs, h4_lows = find_swings(h4_slice, left=5, right=5)
            if h4_highs and h4_lows:
                sh = max(h["price"] for h in h4_highs[-5:])
                sl_val = min(l["price"] for l in h4_lows[-5:])
                rng = sh - sl_val
                if rng > 0:
                    pct = (price - sl_val) / rng * 100
                    if direction == "BUY" and pct > 75:
                        pd_favorable = False  # Buying in premium = bad
                    elif direction == "SELL" and pct < 25:
                        pd_favorable = False  # Selling in discount = bad

        # ── Score ──
        score = 0
        score += aligned * 5          # 10-15 for MTF
        score += 8                     # CHoCH confirmed
        score += 5 if has_candle_confirm else 0
        score += 3 if sma44_ok else 0
        score += 4 if pd_favorable else -4
        score += 3 if (in_london and in_ny) else 1

        # STRICT: need at least 20 points (strong setup)
        # Also MUST have candle confirmation since SL is so tight
        if score < 20 or not has_candle_confirm:
            continue

        # Grade
        if score >= 30 and pd_favorable and has_candle_confirm:
            grade = "A+"
        elif score >= 25:
            grade = "A"
        elif score >= 20:
            grade = "B"
        else:
            continue

        return {
            "direction": direction,
            "price": price,
            "sl_price": round(sl_price, 2),
            "sl_pips": round(sl_distance, 1),
            "structure_price": round(structure_price, 2),
            "score": score,
            "grade": grade,
            "aligned": aligned,
            "has_choch": True,
            "has_rejection": has_rejection,
            "has_engulfing": has_engulfing,
            "sma44_ok": sma44_ok,
            "pd_favorable": pd_favorable,
            "session": "LN/NY overlap" if (in_london and in_ny) else "London" if in_london else "NY",
            "bar_time": bar_time,
        }

    return None


@dataclass
class Trade:
    entry_time: datetime = None
    direction: str = ""
    entry_price: float = 0.0
    sl: float = 0.0
    sl_pips: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    lot_size: float = 0.0
    grade: str = ""
    score: int = 0
    signal: dict = field(default_factory=dict)
    is_open: bool = True
    sl_moved_be: bool = False
    tp1_hit: bool = False
    tp2_hit: bool = False
    remaining_lot: float = 0.0
    partial_pnl: float = 0.0
    exit_time: datetime = None
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_pips: float = 0.0
    pnl_usd: float = 0.0


def open_trade(signal, balance):
    d = signal["direction"]
    price = signal["price"]
    cost = (SPREAD_PIPS + SLIPPAGE_PIPS) * PIP

    entry = price + cost if d == "BUY" else price - cost
    sl = signal["sl_price"]
    sl_pips = signal["sl_pips"]

    # TP based on actual SL distance (proportional)
    tp1_dist = max(TP1_PIPS, sl_pips) * PIP  # At least 1:1
    tp2_dist = max(TP2_PIPS, sl_pips * 2) * PIP
    tp3_dist = max(TP3_PIPS, sl_pips * 4) * PIP

    if d == "BUY":
        tp1 = round(entry + tp1_dist, 2)
        tp2 = round(entry + tp2_dist, 2)
        tp3 = round(entry + tp3_dist, 2)
    else:
        tp1 = round(entry - tp1_dist, 2)
        tp2 = round(entry - tp2_dist, 2)
        tp3 = round(entry - tp3_dist, 2)

    risk_amt = balance * (RISK_PCT / 100)
    lot = risk_amt / (sl_pips * PIP_VALUE_PER_LOT)
    lot = max(0.01, min(5.0, round(lot, 2)))

    return Trade(
        entry_time=signal["bar_time"], direction=d,
        entry_price=round(entry, 2), sl=round(sl, 2), sl_pips=sl_pips,
        tp1=tp1, tp2=tp2, tp3=tp3,
        lot_size=lot, remaining_lot=lot,
        grade=signal["grade"], score=signal["score"], signal=signal,
    )


def manage_trade(trade, bar):
    if not trade.is_open:
        return trade

    h, l = float(bar["high"]), float(bar["low"])
    is_buy = trade.direction == "BUY"

    # Check SL
    sl_hit = (l <= trade.sl) if is_buy else (h >= trade.sl)
    if sl_hit:
        trade.is_open = False
        trade.exit_time = bar["time"]
        trade.exit_price = trade.sl
        if trade.tp1_hit:
            trade.exit_reason = "SL@BE"
            # Already took TP1 partial, SL at BE = small profit from partial
            trade.pnl_pips = 0
            trade.pnl_usd = trade.partial_pnl  # Only partial profits
        else:
            trade.exit_reason = "SL"
            trade.pnl_pips = -trade.sl_pips
            trade.pnl_usd = round(-trade.lot_size * trade.sl_pips * PIP_VALUE_PER_LOT, 2)
        return trade

    # Check TP1
    if not trade.tp1_hit:
        tp1_hit = (h >= trade.tp1) if is_buy else (l <= trade.tp1)
        if tp1_hit:
            trade.tp1_hit = True
            close_lot = round(trade.lot_size * TP1_CLOSE_PCT, 2)
            pips = abs(trade.tp1 - trade.entry_price) / PIP
            trade.partial_pnl += round(close_lot * pips * PIP_VALUE_PER_LOT, 2)
            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
            # Move SL to BE + 2 pip buffer
            buffer = 2 * PIP
            trade.sl = trade.entry_price + buffer if is_buy else trade.entry_price - buffer
            trade.sl_moved_be = True

    # Check TP2
    if trade.tp1_hit and not trade.tp2_hit:
        tp2_hit = (h >= trade.tp2) if is_buy else (l <= trade.tp2)
        if tp2_hit:
            trade.tp2_hit = True
            close_lot = round(trade.lot_size * TP2_CLOSE_PCT, 2)
            close_lot = min(close_lot, trade.remaining_lot)
            pips = abs(trade.tp2 - trade.entry_price) / PIP
            trade.partial_pnl += round(close_lot * pips * PIP_VALUE_PER_LOT, 2)
            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
            # Trail SL to TP1
            trade.sl = trade.tp1

    # Check TP3 (runner)
    if trade.tp2_hit:
        tp3_hit = (h >= trade.tp3) if is_buy else (l <= trade.tp3)
        if tp3_hit:
            trade.is_open = False
            trade.exit_time = bar["time"]
            trade.exit_price = trade.tp3
            pips = abs(trade.tp3 - trade.entry_price) / PIP
            trade.partial_pnl += round(trade.remaining_lot * pips * PIP_VALUE_PER_LOT, 2)
            trade.pnl_pips = pips
            trade.pnl_usd = trade.partial_pnl
            trade.exit_reason = "TP3"
            return trade

    return trade


def run_backtest(csv_path):
    print("=" * 70)
    print("  GOLD ENGINE V6 CALLISTO — PRECISION SCALP BACKTEST")
    print("  40-Pip SL Behind Structure | Rejection/Engulfing Entries")
    print("=" * 70)

    m15 = load_csv(csv_path)
    m15 = add_ind(m15)
    h1 = aggregate_tf(m15, "1h")
    h1 = add_ind(h1)
    h4 = aggregate_tf(m15, "4h")
    h4 = add_ind(h4)

    print(f"\n  Data: {len(m15):,} M15 bars | {m15['time'].iloc[0].date()} → {m15['time'].iloc[-1].date()}")
    print(f"  Price: ${m15['close'].min():.2f} → ${m15['close'].max():.2f}")
    print(f"  SL: Fixed 40 pips (behind nearest structure)")
    print(f"  TP: 50% at TP1 (40p min), 30% at TP2 (80p min), 20% runner to TP3")

    balance = DEFAULT_BALANCE
    peak = balance
    max_dd = 0
    trades = []
    open_t = None
    daily_losses = {}
    cooldown = None

    for i in range(200, len(m15)):
        bar = m15.iloc[i]
        d = bar["time"].date()
        t = bar["time"]
        if d not in daily_losses:
            daily_losses[d] = 0

        if open_t and open_t.is_open:
            open_t = manage_trade(open_t, bar)
            if not open_t.is_open:
                balance += open_t.pnl_usd
                trades.append(open_t)
                if open_t.exit_reason == "SL":
                    daily_losses[d] += 1
                    cooldown = t + timedelta(hours=2)
                peak = max(peak, balance)
                dd = (peak - balance) / peak * 100
                max_dd = max(max_dd, dd)
                open_t = None
            continue

        if daily_losses.get(d, 0) >= MAX_DAILY_LOSSES:
            continue
        if cooldown and t < cooldown:
            continue

        sig = precision_signal(i, m15, h1, h4)
        if sig:
            open_t = open_trade(sig, balance)

    # Close remaining
    if open_t and open_t.is_open:
        last = m15.iloc[-1]
        open_t.is_open = False
        open_t.exit_time = last["time"]
        open_t.exit_price = float(last["close"])
        open_t.exit_reason = "END"
        pip_d = (open_t.exit_price - open_t.entry_price) / PIP
        if open_t.direction == "SELL":
            pip_d = -pip_d
        rem_pnl = open_t.remaining_lot * pip_d * PIP_VALUE_PER_LOT
        open_t.pnl_pips = round(pip_d, 1)
        open_t.pnl_usd = round(open_t.partial_pnl + rem_pnl, 2)
        balance += open_t.pnl_usd
        trades.append(open_t)

    print_results(trades, balance, max_dd)
    save_csv(trades)
    return trades, balance


def print_results(trades, final, max_dd):
    if not trades:
        print("\n  NO TRADES — entry criteria too strict for this data.")
        print("  This can happen when 40-pip structure setups are rare on M15.")
        return

    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd < 0]
    be = [t for t in trades if abs(t.pnl_usd) < 1]

    total_pnl = sum(t.pnl_usd for t in trades)
    wr = len(wins) / len(trades) * 100 if trades else 0
    avg_w = np.mean([t.pnl_usd for t in wins]) if wins else 0
    avg_l = np.mean([t.pnl_usd for t in losses]) if losses else 0
    pf = abs(sum(t.pnl_usd for t in wins) / min(sum(t.pnl_usd for t in losses), -0.01)) if losses else float('inf')

    avg_w_pips = np.mean([t.pnl_pips for t in wins]) if wins else 0
    avg_l_pips = np.mean([t.pnl_pips for t in losses]) if losses else 0
    total_pips = sum(t.pnl_pips for t in trades)

    # Exit reasons
    exits = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1

    # Grade stats
    grades = {}
    for t in trades:
        g = t.grade
        if g not in grades:
            grades[g] = {"n": 0, "w": 0, "pnl": 0}
        grades[g]["n"] += 1
        if t.pnl_usd > 0:
            grades[g]["w"] += 1
        grades[g]["pnl"] += t.pnl_usd

    # Sessions
    sessions = {}
    for t in trades:
        s = t.signal.get("session", "?")
        if s not in sessions:
            sessions[s] = {"n": 0, "w": 0, "pnl": 0}
        sessions[s]["n"] += 1
        if t.pnl_usd > 0:
            sessions[s]["w"] += 1
        sessions[s]["pnl"] += t.pnl_usd

    # Monthly
    monthly = {}
    for t in trades:
        m = t.entry_time.strftime("%Y-%m")
        if m not in monthly:
            monthly[m] = {"n": 0, "w": 0, "pnl": 0}
        monthly[m]["n"] += 1
        if t.pnl_usd > 0:
            monthly[m]["w"] += 1
        monthly[m]["pnl"] += t.pnl_usd

    # Streaks
    max_ws, max_ls, cs = 0, 0, 0
    for t in trades:
        if t.pnl_usd > 0:
            cs = max(0, cs) + 1
            max_ws = max(max_ws, cs)
        elif t.pnl_usd < 0:
            cs = min(0, cs) - 1
            max_ls = max(max_ls, abs(cs))
        else:
            cs = 0

    print(f"""
{'='*70}
  PRECISION BACKTEST RESULTS — V6 CALLISTO (40-PIP SL)
{'='*70}

  ┌─────────────────────────────────────────────────────┐
  │  Starting Balance:  ${DEFAULT_BALANCE:>10,.2f}                  │
  │  Final Balance:     ${final:>10,.2f}                  │
  │  Net P&L:           ${total_pnl:>+10,.2f}  ({total_pnl/DEFAULT_BALANCE*100:+.1f}%)          │
  │  Total Pips:        {total_pips:>+10,.1f}                     │
  │  Max Drawdown:      {max_dd:>10.1f}%                     │
  ├─────────────────────────────────────────────────────┤
  │  Total Trades:      {len(trades):>10d}                       │
  │  Winners:           {len(wins):>10d}                       │
  │  Losers:            {len(losses):>10d}                       │
  │  Breakeven (SL@BE): {len(be):>10d}                       │
  │  Win Rate:          {wr:>10.1f}%                     │
  │  Profit Factor:     {pf:>10.2f}                     │
  ├─────────────────────────────────────────────────────┤
  │  Avg Win:           ${avg_w:>+10,.2f}  ({avg_w_pips:+.0f} pips)     │
  │  Avg Loss:          ${avg_l:>+10,.2f}  ({avg_l_pips:+.0f} pips)    │
  │  Max Win Streak:    {max_ws:>10d}                       │
  │  Max Loss Streak:   {max_ls:>10d}                       │
  └─────────────────────────────────────────────────────┘""")

    print(f"\n  EXIT DISTRIBUTION:")
    for reason, count in sorted(exits.items(), key=lambda x: -x[1]):
        pct = count / len(trades) * 100
        bar = "█" * int(pct / 2)
        print(f"    {reason:8s}: {count:3d} ({pct:5.1f}%) {bar}")

    print(f"\n  GRADE BREAKDOWN:")
    for g in sorted(grades.keys()):
        info = grades[g]
        gwr = info["w"] / info["n"] * 100 if info["n"] else 0
        print(f"    {g:4s}: {info['n']:3d} trades | WR: {gwr:5.1f}% | P&L: ${info['pnl']:+,.2f}")

    print(f"\n  SESSION BREAKDOWN:")
    for s in sorted(sessions.keys()):
        info = sessions[s]
        swr = info["w"] / info["n"] * 100 if info["n"] else 0
        print(f"    {s:16s}: {info['n']:3d} trades | WR: {swr:5.1f}% | P&L: ${info['pnl']:+,.2f}")

    print(f"\n  MONTHLY PERFORMANCE:")
    for m in sorted(monthly.keys()):
        info = monthly[m]
        mwr = info["w"] / info["n"] * 100 if info["n"] else 0
        bar = "+" * max(0, int(info["pnl"] / 50)) if info["pnl"] > 0 else "-" * max(0, int(abs(info["pnl"]) / 50))
        print(f"    {m}: {info['n']:3d} trades | WR: {mwr:5.1f}% | P&L: ${info['pnl']:+,.2f}  {bar}")

    print(f"\n  LAST 10 TRADES:")
    print(f"    {'Time':20s} {'Dir':4s} {'Entry':>10s} {'SL':>10s} {'Exit':>10s} {'Gr':3s} {'Reason':7s} {'P&L':>10s}")
    print(f"    {'─'*20} {'─'*4} {'─'*10} {'─'*10} {'─'*10} {'─'*3} {'─'*7} {'─'*10}")
    for t in trades[-10:]:
        print(f"    {str(t.entry_time)[:19]:20s} {t.direction:4s} ${t.entry_price:>9.2f} ${t.sl:>9.2f} "
              f"${t.exit_price:>9.2f} {t.grade:3s} {t.exit_reason:7s} ${t.pnl_usd:>+9.2f}")


def save_csv(trades):
    rows = []
    for t in trades:
        rows.append({
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "direction": t.direction, "entry_price": t.entry_price,
            "sl": t.sl, "sl_pips": t.sl_pips,
            "exit_price": t.exit_price, "exit_reason": t.exit_reason,
            "grade": t.grade, "score": t.score,
            "lot_size": t.lot_size,
            "pnl_pips": t.pnl_pips, "pnl_usd": t.pnl_usd,
            "session": t.signal.get("session", ""),
            "tp1_hit": t.tp1_hit, "tp2_hit": t.tp2_hit,
        })
    df = pd.DataFrame(rows)
    out = os.path.join(os.path.dirname(csv_path), "v6_precision_trades.csv")
    df.to_csv(out, index=False)
    print(f"\n  Trade log saved: {out}")


if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "dukascopy_xauusd_m15.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)
    run_backtest(csv_path)
