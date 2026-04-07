#!/usr/bin/env python3
"""
XAUUSD V6 Callisto — Micro Lot Backtest
=========================================
Strategy:
  - 5 orders x 0.01 lot at the SAME entry (total 0.05 lots)
  - SL: 40 pips for ALL orders
  - TP1: 40 pips  → close Order 1 (0.01 lot)
  - TP2: 80 pips  → close Order 2 (0.01 lot)
  - TP3: 120 pips → close Order 3 (0.01 lot)
  - TP4: 160 pips → close Order 4 (0.01 lot)
  - TP5: 200 pips → close Order 5 (0.01 lot)
  - Once TP1 hits: move SL to breakeven for remaining 4 orders
  - Capital: $1,200

Risk per full SL hit (no TP1): 5 x 0.01 x 40 x $10 = $20 (1.67%)
If TP1 hits + rest at BE: profit = $4, loss = $0 → net +$4
Best case (all 5 TPs): $4+$8+$12+$16+$20 = $60
"""

import sys, os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, field

PIP = 0.1
PIP_VALUE_PER_LOT = 10.0  # $10 per pip per standard lot
LOT_SIZE = 0.01            # ← MICRO LOT (broker minimum)
PIP_VALUE = LOT_SIZE * PIP_VALUE_PER_LOT  # $0.10 per pip per 0.01 lot
NUM_ORDERS = 5
FIXED_SL_PIPS = 40.0
TP_PIPS = [40, 80, 120, 160, 200]
SPREAD_PIPS = 2.5
SLIPPAGE_PIPS = 0.5
STARTING_BALANCE = 1200.0
MAX_DAILY_LOSSES = 2

LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21


# ============================================================================
# DATA
# ============================================================================
def load_csv(filepath):
    df = pd.read_csv(filepath)
    df["time"] = pd.to_datetime(df["time"])
    return df.sort_values("time").reset_index(drop=True)


def aggregate_tf(m15, freq):
    df = m15.copy().set_index("time")
    return df.resample(freq).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna().reset_index()


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


# ============================================================================
# SIGNAL LOGIC — Callisto TRC on M15
# ============================================================================
def get_trend(df):
    if df is None or len(df) < 50:
        return "neutral"
    r = df.iloc[-1]
    c = float(r["close"])
    e20, e50, e200 = float(r["ema20"]), float(r["ema50"]), float(r.get("ema200", c))
    if c > e50 and e50 > e200 and e20 > e50:
        return "bull"
    if c < e50 and e50 < e200 and e20 < e50:
        return "bear"
    if c > e200:
        return "bull_weak"
    if c < e200:
        return "bear_weak"
    return "neutral"


def is_rejection(bar, direction):
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    body = abs(c - o)
    total = h - l
    if total < PIP * 3:
        return False
    uw = h - max(o, c)
    lw = min(o, c) - l
    if direction == "BUY":
        return lw > body * 1.5 and uw < body * 0.5
    else:
        return uw > body * 1.5 and lw < body * 0.5


def is_engulfing(prev, curr, direction):
    po, pc = float(prev["open"]), float(prev["close"])
    co, cc = float(curr["open"]), float(curr["close"])
    if direction == "BUY":
        return pc < po and cc > co and cc > po and co < pc
    else:
        return pc > po and cc < co and cc < po and co > pc


def generate_signal(i, m15, h1, h4):
    """Callisto TRC signal: MTF alignment + CHoCH + candle confirmation."""
    if i < 200:
        return None

    bar = m15.iloc[i]
    prev = m15.iloc[i-1]
    hour = bar["time"].hour
    price = float(bar["close"])
    bar_time = bar["time"]

    # Session filter
    in_london = LONDON_START <= hour < LONDON_END
    in_ny = NY_START <= hour < NY_END
    if not in_london and not in_ny:
        return None

    h1s = h1[h1["time"] <= bar_time].tail(200)
    h4s = h4[h4["time"] <= bar_time].tail(200)
    m15s = m15.iloc[max(0, i-200):i+1]

    if len(h1s) < 50 or len(h4s) < 20 or len(m15s) < 50:
        return None

    # Trends
    h4t = get_trend(h4s)
    h1t = get_trend(h1s)
    m15t = get_trend(m15s)

    # Swings for CHoCH
    highs, lows = find_swings(m15s, left=3, right=3)
    if len(highs) < 3 or len(lows) < 3:
        return None

    rh = [h["price"] for h in highs[-5:]]
    rl = [l["price"] for l in lows[-5:]]

    for direction in ["BUY", "SELL"]:
        target = "bull" if direction == "BUY" else "bear"

        # 2/3 MTF alignment
        aligned = sum(1 for t in [h4t, h1t, m15t] if target in t)
        if aligned < 2:
            continue

        # CHoCH check (body close)
        has_choch = False
        if direction == "BUY":
            if rl[-3] > rl[-2] and rh[-1] > rh[-2] and price > rh[-2]:
                has_choch = True
        else:
            if rh[-3] < rh[-2] and rl[-1] < rl[-2] and price < rl[-2]:
                has_choch = True

        if not has_choch:
            continue

        # Candle confirmation (rejection or engulfing)
        has_confirm = is_rejection(bar, direction) or is_engulfing(prev, bar, direction)

        # SMA44 alignment
        sma44 = float(m15s["sma44"].iloc[-1]) if not pd.isna(m15s["sma44"].iloc[-1]) else None
        sma44_ok = False
        if sma44:
            sma44_ok = (direction == "BUY" and price > sma44) or (direction == "SELL" and price < sma44)

        # BOS check on H1
        h1_highs, h1_lows = find_swings(h1s, left=3, right=2)
        has_bos = False
        if direction == "BUY" and len(h1_highs) >= 2:
            has_bos = h1_highs[-1]["price"] > h1_highs[-2]["price"]
        elif direction == "SELL" and len(h1_lows) >= 2:
            has_bos = h1_lows[-1]["price"] < h1_lows[-2]["price"]

        # Score
        score = aligned * 5 + 8  # MTF + CHoCH base
        if has_confirm:
            score += 5
        if sma44_ok:
            score += 3
        if has_bos:
            score += 4
        if in_london and in_ny:
            score += 3
        elif in_london or in_ny:
            score += 1

        # Need minimum 18 to trade
        if score < 18:
            continue

        grade = "A+" if score >= 28 else "A" if score >= 24 else "B" if score >= 20 else "C"
        if grade == "C":
            continue

        session = "LN/NY" if (in_london and in_ny) else "London" if in_london else "NY"

        return {
            "direction": direction, "price": price, "score": score,
            "grade": grade, "aligned": aligned, "has_choch": True,
            "has_confirm": has_confirm, "sma44_ok": sma44_ok,
            "has_bos": has_bos, "session": session, "bar_time": bar_time,
        }

    return None


# ============================================================================
# LAYERED TRADE — MICRO LOT
# ============================================================================
@dataclass
class LayeredTrade:
    entry_time: datetime = None
    direction: str = ""
    entry_price: float = 0.0
    sl_price: float = 0.0
    tp_prices: list = field(default_factory=list)
    grade: str = ""
    score: int = 0
    signal: dict = field(default_factory=dict)
    orders_open: list = field(default_factory=lambda: [True]*5)
    sl_at_be: bool = False
    is_open: bool = True
    exit_time: datetime = None
    exit_reason: str = ""
    tp_hits: list = field(default_factory=list)
    pnl_usd: float = 0.0
    pnl_breakdown: list = field(default_factory=list)


def open_layered_trade(signal):
    d = signal["direction"]
    price = signal["price"]
    cost = (SPREAD_PIPS + SLIPPAGE_PIPS) * PIP

    entry = price + cost if d == "BUY" else price - cost
    entry = round(entry, 2)

    if d == "BUY":
        sl = round(entry - FIXED_SL_PIPS * PIP, 2)
        tps = [round(entry + tp * PIP, 2) for tp in TP_PIPS]
    else:
        sl = round(entry + FIXED_SL_PIPS * PIP, 2)
        tps = [round(entry - tp * PIP, 2) for tp in TP_PIPS]

    return LayeredTrade(
        entry_time=signal["bar_time"], direction=d,
        entry_price=entry, sl_price=sl, tp_prices=tps,
        grade=signal["grade"], score=signal["score"], signal=signal,
    )


def manage_layered_trade(trade, bar):
    if not trade.is_open:
        return trade

    h, l = float(bar["high"]), float(bar["low"])
    is_buy = trade.direction == "BUY"

    # ── Check SL for all open orders ──
    sl_hit = (l <= trade.sl_price) if is_buy else (h >= trade.sl_price)

    if sl_hit:
        for idx in range(NUM_ORDERS):
            if trade.orders_open[idx]:
                trade.orders_open[idx] = False
                if trade.sl_at_be:
                    pnl = PIP_VALUE * 2  # 2-pip BE buffer
                    trade.pnl_breakdown.append({
                        "order": idx+1, "tp": "SL@BE", "pips": 2, "pnl": round(pnl, 2)
                    })
                    trade.pnl_usd += pnl
                else:
                    pnl = -(PIP_VALUE * FIXED_SL_PIPS)
                    trade.pnl_breakdown.append({
                        "order": idx+1, "tp": "SL", "pips": -FIXED_SL_PIPS, "pnl": round(pnl, 2)
                    })
                    trade.pnl_usd += pnl

        trade.is_open = False
        trade.exit_time = bar["time"]
        trade.exit_reason = "SL@BE" if trade.sl_at_be else "SL"
        return trade

    # ── Check TPs in order ──
    for idx in range(NUM_ORDERS):
        if not trade.orders_open[idx]:
            continue

        tp = trade.tp_prices[idx]
        tp_hit = (h >= tp) if is_buy else (l <= tp)

        if tp_hit:
            trade.orders_open[idx] = False
            pips = TP_PIPS[idx]
            pnl = PIP_VALUE * pips
            trade.pnl_breakdown.append({
                "order": idx+1, "tp": f"TP{idx+1}", "pips": pips, "pnl": round(pnl, 2)
            })
            trade.pnl_usd += pnl
            trade.tp_hits.append(idx+1)

            # TP1 hit → move all remaining orders to BE
            if idx == 0 and not trade.sl_at_be:
                buffer = 2 * PIP
                if is_buy:
                    trade.sl_price = trade.entry_price + buffer
                else:
                    trade.sl_price = trade.entry_price - buffer
                trade.sl_at_be = True

    if not any(trade.orders_open):
        trade.is_open = False
        trade.exit_time = bar["time"]
        trade.exit_reason = f"TP{max(trade.tp_hits)}" if trade.tp_hits else "ALL_CLOSED"

    return trade


# ============================================================================
# MAIN BACKTEST
# ============================================================================
def run_backtest(csv_path):
    # Risk calculations
    risk_per_order = PIP_VALUE * FIXED_SL_PIPS  # $0.10 x 40 = $4.00
    risk_per_trade = risk_per_order * NUM_ORDERS  # $4.00 x 5 = $20.00
    risk_pct = risk_per_trade / STARTING_BALANCE * 100

    # TP rewards per order
    tp_rewards = [PIP_VALUE * tp for tp in TP_PIPS]
    best_case = sum(tp_rewards)

    print("=" * 70)
    print("  GOLD ENGINE V6 CALLISTO — MICRO LOT BACKTEST")
    print("=" * 70)
    print(f"""
  Strategy:  5 x {LOT_SIZE} lot at same entry ({LOT_SIZE*5} lots total)
  SL:        40 pips for all orders
  TP1:       40 pips  → close Order 1 → move rest to BE
  TP2:       80 pips  → close Order 2
  TP3:       120 pips → close Order 3
  TP4:       160 pips → close Order 4
  TP5:       200 pips → close Order 5
  Capital:   ${STARTING_BALANCE:,.2f}

  ┌─────────────────────────────────────────────────┐
  │  ORDER SETUP (per trade)                        │
  ├─────────────────────────────────────────────────┤
  │  Order  Lot     SL        TP      $ Risk  $ TP  │
  │  ─────  ─────   ──────    ──────  ──────  ───── │
  │  #1     {LOT_SIZE}   40 pips   40p    ${risk_per_order:.2f}  ${tp_rewards[0]:.2f} │
  │  #2     {LOT_SIZE}   40 pips   80p    ${risk_per_order:.2f}  ${tp_rewards[1]:.2f} │
  │  #3     {LOT_SIZE}   40 pips   120p   ${risk_per_order:.2f}  ${tp_rewards[2]:.2f} │
  │  #4     {LOT_SIZE}   40 pips   160p   ${risk_per_order:.2f}  ${tp_rewards[3]:.2f} │
  │  #5     {LOT_SIZE}   40 pips   200p   ${risk_per_order:.2f}  ${tp_rewards[4]:.2f} │
  ├─────────────────────────────────────────────────┤
  │  TOTAL RISK: ${risk_per_trade:.2f} ({risk_pct:.2f}% of capital)    │
  │  BEST CASE:  ${best_case:.2f} (all 5 TPs hit)            │
  │  TP1→BE:     ${tp_rewards[0]:.2f} + $0 (rest at breakeven)   │
  │  R:R range:  1:1 → 1:10                         │
  │  Max 2 losses/day = max -${risk_per_trade*2:.2f}/day       │
  └─────────────────────────────────────────────────┘
""")

    m15 = load_csv(csv_path)
    m15 = add_ind(m15)
    h1 = aggregate_tf(m15, "1h")
    h1 = add_ind(h1)
    h4 = aggregate_tf(m15, "4h")
    h4 = add_ind(h4)

    print(f"  Data: {len(m15):,} M15 bars | {m15['time'].iloc[0].date()} → {m15['time'].iloc[-1].date()}")
    print(f"  Price: ${m15['close'].min():.2f} → ${m15['close'].max():.2f}")

    balance = STARTING_BALANCE
    peak = balance
    max_dd = 0
    max_dd_usd = 0
    trades: List[LayeredTrade] = []
    open_t: Optional[LayeredTrade] = None
    daily_losses = {}
    cooldown = None
    equity_curve = []

    for i in range(200, len(m15)):
        bar = m15.iloc[i]
        d = bar["time"].date()
        t = bar["time"]
        if d not in daily_losses:
            daily_losses[d] = 0

        # Manage open trade
        if open_t and open_t.is_open:
            open_t = manage_layered_trade(open_t, bar)
            if not open_t.is_open:
                balance += open_t.pnl_usd
                balance = round(balance, 2)
                trades.append(open_t)
                if open_t.exit_reason == "SL":
                    daily_losses[d] += 1
                    cooldown = t + timedelta(hours=2)
                peak = max(peak, balance)
                dd = (peak - balance) / peak * 100
                max_dd = max(max_dd, dd)
                max_dd_usd = max(max_dd_usd, peak - balance)
                open_t = None

            equity_curve.append({"time": t, "balance": balance})
            continue

        # Can we trade?
        if daily_losses.get(d, 0) >= MAX_DAILY_LOSSES:
            continue
        if cooldown and t < cooldown:
            continue

        # Margin check — much lower with micro lots
        if balance < 50:
            continue

        sig = generate_signal(i, m15, h1, h4)
        if sig:
            open_t = open_layered_trade(sig)
            equity_curve.append({"time": t, "balance": balance})

    # Close remaining
    if open_t and open_t.is_open:
        last = m15.iloc[-1]
        for idx in range(NUM_ORDERS):
            if open_t.orders_open[idx]:
                open_t.orders_open[idx] = False
                pip_d = (float(last["close"]) - open_t.entry_price) / PIP
                if open_t.direction == "SELL":
                    pip_d = -pip_d
                pnl = PIP_VALUE * pip_d
                open_t.pnl_breakdown.append({
                    "order": idx+1, "tp": "END", "pips": round(pip_d, 1), "pnl": round(pnl, 2)
                })
                open_t.pnl_usd += pnl
        open_t.is_open = False
        open_t.exit_time = last["time"]
        open_t.exit_reason = "END"
        balance += open_t.pnl_usd
        trades.append(open_t)

    print_results(trades, balance, peak, max_dd, max_dd_usd, equity_curve)
    save_csv(trades, csv_path)
    return trades, balance


def print_results(trades, final, peak, max_dd, max_dd_usd, equity_curve):
    if not trades:
        print("\n  NO TRADES — signals too strict for this data.")
        return

    total_pnl = sum(t.pnl_usd for t in trades)
    risk_per_trade = PIP_VALUE * FIXED_SL_PIPS * NUM_ORDERS

    full_sl = [t for t in trades if t.exit_reason == "SL"]
    sl_be = [t for t in trades if t.exit_reason == "SL@BE"]
    tp_exits = [t for t in trades if t.exit_reason.startswith("TP")]

    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd < 0]

    wr = len(wins) / len(trades) * 100 if trades else 0
    avg_w = np.mean([t.pnl_usd for t in wins]) if wins else 0
    avg_l = np.mean([t.pnl_usd for t in losses]) if losses else 0
    pf = abs(sum(t.pnl_usd for t in wins) / min(sum(t.pnl_usd for t in losses), -0.01)) if losses else float('inf')

    tp1_hits = sum(1 for t in trades if 1 in t.tp_hits)
    tp2_hits = sum(1 for t in trades if 2 in t.tp_hits)
    tp3_hits = sum(1 for t in trades if 3 in t.tp_hits)
    tp4_hits = sum(1 for t in trades if 4 in t.tp_hits)
    tp5_hits = sum(1 for t in trades if 5 in t.tp_hits)

    scenario_a = len(full_sl)
    scenario_b = sum(1 for t in trades if len(t.tp_hits) == 1 and t.exit_reason == "SL@BE")
    scenario_c = sum(1 for t in trades if len(t.tp_hits) >= 2)

    # Grade breakdown
    grades = {}
    for t in trades:
        g = t.grade
        if g not in grades:
            grades[g] = {"n": 0, "w": 0, "pnl": 0}
        grades[g]["n"] += 1
        if t.pnl_usd > 0:
            grades[g]["w"] += 1
        grades[g]["pnl"] += t.pnl_usd

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
            cs = max(0, cs) + 1; max_ws = max(max_ws, cs)
        elif t.pnl_usd < 0:
            cs = min(0, cs) - 1; max_ls = max(max_ls, abs(cs))
        else:
            cs = 0

    # Survival analysis
    min_balance = STARTING_BALANCE
    running = STARTING_BALANCE
    survived = True
    for t in trades:
        running += t.pnl_usd
        min_balance = min(min_balance, running)
        if running <= 0:
            survived = False
            break

    print(f"""
{'='*70}
  MICRO LOT BACKTEST RESULTS — V6 CALLISTO
{'='*70}

  ┌─────────────────────────────────────────────────────────┐
  │  ACCOUNT PERFORMANCE                                    │
  ├─────────────────────────────────────────────────────────┤
  │  Starting Capital:   ${STARTING_BALANCE:>10,.2f}                     │
  │  Final Balance:      ${final:>10,.2f}                     │
  │  Net P&L:            ${total_pnl:>+10,.2f}  ({total_pnl/STARTING_BALANCE*100:+.1f}%)            │
  │  Peak Balance:       ${peak:>10,.2f}                     │
  │  Lowest Balance:     ${min_balance:>10,.2f}                     │
  │  Max Drawdown:       {max_dd:>10.1f}%  (${max_dd_usd:>,.2f})          │
  │  Account Survived:   {'YES ✓' if survived else 'NO ✗':>10s}                          │
  ├─────────────────────────────────────────────────────────┤
  │  RISK PER TRADE                                         │
  ├─────────────────────────────────────────────────────────┤
  │  Lot Size:           {LOT_SIZE:>10.2f} per order                │
  │  Total Exposure:     {LOT_SIZE*NUM_ORDERS:>10.2f} lots                     │
  │  Risk (full SL):     ${risk_per_trade:>10,.2f} ({risk_per_trade/STARTING_BALANCE*100:.2f}%)         │
  │  Max Daily Risk:     ${risk_per_trade*2:>10,.2f} (2 losses)              │
  ├─────────────────────────────────────────────────────────┤
  │  TRADE STATISTICS                                       │
  ├─────────────────────────────────────────────────────────┤
  │  Total Trades:       {len(trades):>10d}                          │
  │  Winners (P&L > 0):  {len(wins):>10d}                          │
  │  Losers (P&L < 0):   {len(losses):>10d}                          │
  │  Win Rate:           {wr:>10.1f}%                        │
  │  Profit Factor:      {pf:>10.2f}                        │
  │  Avg Win:            ${avg_w:>+10,.2f}                     │
  │  Avg Loss:           ${avg_l:>+10,.2f}                     │
  │  Max Win Streak:     {max_ws:>10d}                          │
  │  Max Loss Streak:    {max_ls:>10d}                          │
  ├─────────────────────────────────────────────────────────┤
  │  SCENARIO BREAKDOWN                                     │
  ├─────────────────────────────────────────────────────────┤
  │  Full SL (5x loss):         {scenario_a:>4d}  (-${risk_per_trade:.2f} each)      │
  │  TP1 hit → rest BE:         {scenario_b:>4d}  (+${PIP_VALUE*40:.2f} each)        │
  │  TP1+more TPs hit:          {scenario_c:>4d}  (big winners)          │
  ├─────────────────────────────────────────────────────────┤
  │  TP HIT RATES                                           │
  ├─────────────────────────────────────────────────────────┤
  │  TP1 (40p):  {tp1_hits:>3d}/{len(trades):>3d} ({tp1_hits/len(trades)*100 if trades else 0:5.1f}%)  +${PIP_VALUE*40:.2f}/order     │
  │  TP2 (80p):  {tp2_hits:>3d}/{len(trades):>3d} ({tp2_hits/len(trades)*100 if trades else 0:5.1f}%)  +${PIP_VALUE*80:.2f}/order     │
  │  TP3 (120p): {tp3_hits:>3d}/{len(trades):>3d} ({tp3_hits/len(trades)*100 if trades else 0:5.1f}%)  +${PIP_VALUE*120:.2f}/order    │
  │  TP4 (160p): {tp4_hits:>3d}/{len(trades):>3d} ({tp4_hits/len(trades)*100 if trades else 0:5.1f}%)  +${PIP_VALUE*160:.2f}/order    │
  │  TP5 (200p): {tp5_hits:>3d}/{len(trades):>3d} ({tp5_hits/len(trades)*100 if trades else 0:5.1f}%)  +${PIP_VALUE*200:.2f}/order    │
  └─────────────────────────────────────────────────────────┘""")

    print(f"\n  GRADE BREAKDOWN:")
    for g in sorted(grades.keys()):
        info = grades[g]
        gwr = info["w"] / info["n"] * 100 if info["n"] else 0
        print(f"    {g:4s}: {info['n']:3d} trades | WR: {gwr:5.1f}% | P&L: ${info['pnl']:+,.2f}")

    print(f"\n  MONTHLY PERFORMANCE:")
    running = STARTING_BALANCE
    for m in sorted(monthly.keys()):
        info = monthly[m]
        running += info["pnl"]
        mwr = info["w"] / info["n"] * 100 if info["n"] else 0
        bar = "+" * max(0, int(info["pnl"] / 4)) if info["pnl"] > 0 else "-" * max(0, int(abs(info["pnl"]) / 4))
        print(f"    {m}: {info['n']:3d} trades | WR: {mwr:5.1f}% | P&L: ${info['pnl']:+,.2f} | Bal: ${running:,.2f}  {bar}")

    print(f"\n  TRADE LOG (all {len(trades)} trades):")
    print(f"    {'#':>3s} {'Time':20s} {'Dir':4s} {'Entry':>10s} {'SL':>10s} {'Grade':5s} {'TPs Hit':10s} {'Exit':8s} {'P&L':>10s} {'Balance':>10s}")
    print(f"    {'─'*3} {'─'*20} {'─'*4} {'─'*10} {'─'*10} {'─'*5} {'─'*10} {'─'*8} {'─'*10} {'─'*10}")
    running = STARTING_BALANCE
    for idx, t in enumerate(trades, 1):
        running += t.pnl_usd
        tp_str = ",".join([f"TP{x}" for x in t.tp_hits]) if t.tp_hits else "none"
        print(f"    {idx:3d} {str(t.entry_time)[:19]:20s} {t.direction:4s} ${t.entry_price:>9.2f} ${t.sl_price:>9.2f} "
              f"{t.grade:5s} {tp_str:10s} {t.exit_reason:8s} ${t.pnl_usd:>+9.2f} ${running:>9.2f}")

    # Best / worst
    if wins:
        best = max(trades, key=lambda t: t.pnl_usd)
        print(f"\n  BEST TRADE:")
        print(f"    {best.entry_time} | {best.direction} @ ${best.entry_price:.2f} | P&L: ${best.pnl_usd:+,.2f}")
        for bd in best.pnl_breakdown:
            print(f"      Order {bd['order']}: {bd['tp']:6s} | {bd['pips']:+.0f} pips | ${bd['pnl']:+,.2f}")

    if losses:
        worst = min(trades, key=lambda t: t.pnl_usd)
        print(f"\n  WORST TRADE:")
        print(f"    {worst.entry_time} | {worst.direction} @ ${worst.entry_price:.2f} | P&L: ${worst.pnl_usd:+,.2f}")
        for bd in worst.pnl_breakdown:
            print(f"      Order {bd['order']}: {bd['tp']:6s} | {bd['pips']:+.0f} pips | ${bd['pnl']:+,.2f}")

    # ── LIVE TRADING ORDER TEMPLATE ──
    print(f"""
{'='*70}
  LIVE TRADING ORDER TEMPLATE
{'='*70}
  Use this template for EVERY trade entry:

  ┌─────────────────────────────────────────────────────────┐
  │  ENTRY CHECKLIST (before placing orders)                │
  ├─────────────────────────────────────────────────────────┤
  │  [ ] MTF alignment: 2/3 TFs agree on direction          │
  │  [ ] CHoCH confirmed on M15 (body close, not wick)      │
  │  [ ] Candle confirmation (rejection/engulfing)           │
  │  [ ] London or NY session active                         │
  │  [ ] Daily losses < 2                                    │
  │  [ ] Grade B or above                                    │
  ├─────────────────────────────────────────────────────────┤
  │  ORDER PLACEMENT (example for BUY @ $XXXX.XX)           │
  ├─────────────────────────────────────────────────────────┤
  │  #1: BUY  0.01 lot | SL = Entry - $4.00 | TP = Entry + $4.00   │
  │  #2: BUY  0.01 lot | SL = Entry - $4.00 | TP = Entry + $8.00   │
  │  #3: BUY  0.01 lot | SL = Entry - $4.00 | TP = Entry + $12.00  │
  │  #4: BUY  0.01 lot | SL = Entry - $4.00 | TP = Entry + $16.00  │
  │  #5: BUY  0.01 lot | SL = Entry - $4.00 | TP = Entry + $20.00  │
  ├─────────────────────────────────────────────────────────┤
  │  AFTER TP1 HITS:                                        │
  │  → Move SL for orders #2-#5 to Entry + $0.20 (BE+2pip) │
  │  → Let remaining orders run to their TPs                │
  ├─────────────────────────────────────────────────────────┤
  │  RISK SUMMARY:                                          │
  │  Full SL loss:  -${PIP_VALUE * FIXED_SL_PIPS * NUM_ORDERS:.2f} ({PIP_VALUE * FIXED_SL_PIPS * NUM_ORDERS / STARTING_BALANCE * 100:.2f}% of account)           │
  │  TP1 only:      +${PIP_VALUE * 40:.2f} (rest at BE)                      │
  │  All 5 TPs:     +${sum(PIP_VALUE * tp for tp in TP_PIPS):.2f}                                   │
  └─────────────────────────────────────────────────────────┘
""")


def save_csv(trades, csv_path):
    rows = []
    running = STARTING_BALANCE
    for t in trades:
        running += t.pnl_usd
        rows.append({
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "direction": t.direction, "entry_price": t.entry_price,
            "sl": t.sl_price,
            "tp1": t.tp_prices[0], "tp2": t.tp_prices[1],
            "tp3": t.tp_prices[2], "tp4": t.tp_prices[3],
            "tp5": t.tp_prices[4],
            "grade": t.grade, "score": t.score,
            "exit_reason": t.exit_reason,
            "tp_hits": ",".join(str(x) for x in t.tp_hits),
            "pnl_usd": round(t.pnl_usd, 2),
            "balance": round(running, 2),
            "session": t.signal.get("session", ""),
            "lot_per_order": LOT_SIZE,
        })
    df = pd.DataFrame(rows)
    out = os.path.join(os.path.dirname(csv_path), "v6_micro_trades.csv")
    df.to_csv(out, index=False)
    print(f"\n  Trade log saved: {out}")


def run_multi_lot_comparison(csv_path):
    """Run backtest across multiple lot sizes for comparison."""
    lot_sizes = [0.01, 0.02, 0.03, 0.05]

    print("\n" + "=" * 70)
    print("  MULTI-LOT SIZE COMPARISON")
    print("=" * 70)
    print(f"\n  Testing lot sizes: {lot_sizes}")
    print(f"  Capital: ${STARTING_BALANCE:,.2f} | SL: 40 pips | 5 orders per trade")
    print(f"  TPs: 40 / 80 / 120 / 160 / 200 pips")
    print()

    results = []
    for lot in lot_sizes:
        global LOT_SIZE, PIP_VALUE
        LOT_SIZE = lot
        PIP_VALUE = LOT_SIZE * PIP_VALUE_PER_LOT

        risk_per_trade = PIP_VALUE * FIXED_SL_PIPS * NUM_ORDERS
        risk_pct = risk_per_trade / STARTING_BALANCE * 100

        # Quick silent run
        m15 = load_csv(csv_path)
        m15 = add_ind(m15)
        h1 = aggregate_tf(m15, "1h")
        h1 = add_ind(h1)
        h4 = aggregate_tf(m15, "4h")
        h4 = add_ind(h4)

        balance = STARTING_BALANCE
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
                open_t = manage_layered_trade(open_t, bar)
                if not open_t.is_open:
                    balance += open_t.pnl_usd
                    balance = round(balance, 2)
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
            if balance < 50:
                continue

            sig = generate_signal(i, m15, h1, h4)
            if sig:
                open_t = open_layered_trade(sig)

        if open_t and open_t.is_open:
            last = m15.iloc[-1]
            for idx in range(NUM_ORDERS):
                if open_t.orders_open[idx]:
                    open_t.orders_open[idx] = False
                    pip_d = (float(last["close"]) - open_t.entry_price) / PIP
                    if open_t.direction == "SELL":
                        pip_d = -pip_d
                    pnl = PIP_VALUE * pip_d
                    open_t.pnl_breakdown.append({"order": idx+1, "tp": "END", "pips": round(pip_d, 1), "pnl": round(pnl, 2)})
                    open_t.pnl_usd += pnl
            open_t.is_open = False
            balance += open_t.pnl_usd
            trades.append(open_t)

        total_pnl = sum(t.pnl_usd for t in trades)
        wins = [t for t in trades if t.pnl_usd > 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        min_bal = STARTING_BALANCE
        r = STARTING_BALANCE
        for t in trades:
            r += t.pnl_usd
            min_bal = min(min_bal, r)

        results.append({
            "lot": lot, "trades": len(trades), "wins": len(wins),
            "wr": wr, "pnl": total_pnl, "final": balance,
            "max_dd": max_dd, "min_bal": min_bal,
            "risk_per_trade": risk_per_trade, "risk_pct": risk_pct,
            "survived": min_bal > 0,
        })

    # Print comparison table
    print(f"  {'Lot':>5s} │ {'Total':>5s} │ {'Risk/Trade':>10s} │ {'Risk%':>6s} │ {'Trades':>6s} │ {'WR':>6s} │ {'Net P&L':>10s} │ {'Final Bal':>10s} │ {'Max DD':>7s} │ {'Low Bal':>10s} │ {'Alive':>5s}")
    print(f"  {'─'*5} │ {'─'*5} │ {'─'*10} │ {'─'*6} │ {'─'*6} │ {'─'*6} │ {'─'*10} │ {'─'*10} │ {'─'*7} │ {'─'*10} │ {'─'*5}")
    for r in results:
        print(f"  {r['lot']:>5.2f} │ {r['lot']*5:>5.2f} │ ${r['risk_per_trade']:>9.2f} │ {r['risk_pct']:>5.2f}% │ {r['trades']:>6d} │ {r['wr']:>5.1f}% │ ${r['pnl']:>+9.2f} │ ${r['final']:>9.2f} │ {r['max_dd']:>6.1f}% │ ${r['min_bal']:>9.2f} │ {'YES' if r['survived'] else 'NO':>5s}")

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  RECOMMENDATION                                         │
  ├─────────────────────────────────────────────────────────┤""")

    # Find best surviving lot
    surviving = [r for r in results if r["survived"]]
    if surviving:
        best = max(surviving, key=lambda r: r["final"])
        print(f"  │  Best lot size: {best['lot']:.2f} (${best['risk_per_trade']:.2f}/trade = {best['risk_pct']:.2f}%)     │")
        print(f"  │  Final balance: ${best['final']:,.2f} | Max DD: {best['max_dd']:.1f}%          │")
    else:
        print(f"  │  All lot sizes blow the account — need wider SL      │")

    print(f"  │                                                       │")
    print(f"  │  Rule of thumb for $1,200:                             │")
    print(f"  │  • 0.01 lot = safest (can take 60 full SL losses)     │")
    print(f"  │  • 0.02 lot = moderate (can take 30 full SL losses)   │")
    print(f"  │  • 0.03 lot = aggressive (can take 20 full SL losses) │")
    print(f"  │  • 0.05 lot = very aggressive (12 full SL losses)     │")
    print(f"  └─────────────────────────────────────────────────────────┘")

    # Now run full detailed report for 0.01 lot
    LOT_SIZE = 0.01
    PIP_VALUE = LOT_SIZE * PIP_VALUE_PER_LOT
    print(f"\n\n{'='*70}")
    print(f"  DETAILED REPORT FOR 0.01 LOT (SAFEST)")
    print(f"{'='*70}")
    run_backtest(csv_path)


if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "dukascopy_xauusd_m15.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)
    run_multi_lot_comparison(csv_path)
