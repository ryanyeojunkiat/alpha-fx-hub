#!/usr/bin/env python3
"""
XAUUSD V5 — Short-Range Liquidity Sweep Strategy
==================================================
Philosophy: Take what the market gives. Don't be greedy.

Timeframes:
  - H1: Market structure bias (HH/HL or LH/LL)
  - M15: Liquidity sweep detection + entry trigger
  - (M5 data not available from M15 CSV, so M15 is lowest TF)

Strategy:
  1. H1 determines direction (bullish structure = buy only, etc.)
  2. M15 detects liquidity sweep of prior swing high/low
  3. Enter on the sweep candle close or next candle open
  4. SL: Behind the sweep wick + ATR buffer (confident, not tight)
  5. TP: Conservative — TP1 at 1.5R (close 50%), TP2 at 2.5R (close 30%), trail rest
  6. Move SL to BE after TP1

Sessions: London (07-10) + NY (12-15) + Pre-London (05-07)
Max 2 trades per day. 2-hour cooldown after SL.
"""

import sys
import argparse
import os
from typing import List, Tuple, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ============================================================================
# CONSTANTS
# ============================================================================
PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
DEFAULT_BALANCE = 10000
DEFAULT_RISK_PCT = 1.5  # Conservative for 0.1 lot users
DEFAULT_LOT_SIZE = 0.1  # Fixed lot mode (0 = dynamic risk-based)
DEFAULT_SPREAD_PIPS = 2.5
DEFAULT_SLIPPAGE_PIPS = 0.5
MAX_SL_PIPS = 60  # Hard cap: max $60 risk at 0.1 lot
MIN_SL_PIPS = 15  # Don't be too tight either

# Sessions (UTC)
SESSIONS = {
    "PRE_LONDON": (5, 7),
    "LONDON": (7, 10),
    "NY": (12, 15),
}

# ============================================================================
# DATA LOADING & AGGREGATION
# ============================================================================

def load_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    required = ["time", "open", "high", "low", "close", "volume"]
    if not all(c in df.columns for c in required):
        raise ValueError(f"CSV needs columns: {required}")
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


def aggregate_to_h1(m15: pd.DataFrame) -> pd.DataFrame:
    df = m15.copy()
    df["hour"] = df["time"].dt.floor("h")
    h1 = df.groupby("hour").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).reset_index().rename(columns={"hour": "time"})
    return h1


# ============================================================================
# INDICATORS
# ============================================================================

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ============================================================================
# SWING DETECTION
# ============================================================================

def find_swings(df: pd.DataFrame, lookback: int = 3) -> Tuple[List, List]:
    """Returns (swing_highs, swing_lows) as [(df_index, price), ...]"""
    highs, lows = [], []
    for i in range(lookback, len(df) - lookback):
        h = df.iloc[i]["high"]
        l = df.iloc[i]["low"]

        if all(h > df.iloc[j]["high"] for j in range(i - lookback, i)) and \
           all(h > df.iloc[j]["high"] for j in range(i + 1, i + lookback + 1)):
            highs.append((df.index[i], h))

        if all(l < df.iloc[j]["low"] for j in range(i - lookback, i)) and \
           all(l < df.iloc[j]["low"] for j in range(i + 1, i + lookback + 1)):
            lows.append((df.index[i], l))

    return highs, lows


def get_h1_bias(swing_highs: List, swing_lows: List) -> str:
    """HH+HL = BULLISH, LH+LL = BEARISH, else NEUTRAL."""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "NEUTRAL"
    hh = swing_highs[-1][1] > swing_highs[-2][1]
    hl = swing_lows[-1][1] > swing_lows[-2][1]
    lh = swing_highs[-1][1] < swing_highs[-2][1]
    ll = swing_lows[-1][1] < swing_lows[-2][1]
    if hh and hl:
        return "BULLISH"
    if lh and ll:
        return "BEARISH"
    return "NEUTRAL"


# ============================================================================
# BACKTESTER
# ============================================================================

class ShortRangeSweepBacktester:
    def __init__(
        self,
        m15_df: pd.DataFrame,
        initial_balance: float = DEFAULT_BALANCE,
        risk_pct: float = DEFAULT_RISK_PCT,
        fixed_lot: float = DEFAULT_LOT_SIZE,
        spread_pips: float = DEFAULT_SPREAD_PIPS,
        slippage_pips: float = DEFAULT_SLIPPAGE_PIPS,
    ):
        self.m15 = m15_df.copy()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_pct = risk_pct
        self.fixed_lot = fixed_lot  # If > 0, use fixed lot instead of risk-based
        self.spread = spread_pips
        self.slippage = slippage_pips

        # Indicators on M15
        self.m15["atr"] = calc_atr(self.m15, 14)
        self.m15["ema50"] = calc_ema(self.m15["close"], 50)

        # Build H1
        print("Building H1 data...")
        self.h1 = aggregate_to_h1(self.m15)
        self.h1["atr"] = calc_atr(self.h1, 14)

        # H1 swings for bias (recalculated rolling during backtest)
        # M15 swings for liquidity levels
        print("Detecting M15 swing levels...")
        self.m15_swing_highs, self.m15_swing_lows = find_swings(self.m15, lookback=4)
        print(f"  M15 swing highs: {len(self.m15_swing_highs)}")
        print(f"  M15 swing lows:  {len(self.m15_swing_lows)}")

        # TP system: short range
        # TP1: 1.5R (close 50%), TP2: 2.5R (close 30%), TP3: 3.5R (close remaining 20%)
        self.tp_levels = [1.5, 2.5, 3.5]
        self.tp_close_pct = [0.50, 0.30, 0.20]

        # State
        self.trades = []
        self.trade_log = []
        self.last_trade_time = None
        self.last_sl_hit_time = None
        self.equity_curve = []

        # Debug
        self.debug = {
            "bars": 0,
            "in_session": 0,
            "h1_bias_ok": 0,
            "sweep_found": 0,
            "entry_confirmed": 0,
            "trades_entered": 0,
            "blocked_open": 0,
            "blocked_daily": 0,
            "blocked_cooldown": 0,
        }

    def _has_open_trade(self) -> bool:
        return any(t["status"] == "OPEN" for t in self.trades)

    def _get_session(self, hour: int) -> Optional[str]:
        for name, (start, end) in SESSIONS.items():
            if start <= hour < end:
                return name
        return None

    def _get_h1_bias_at(self, bar_time: pd.Timestamp) -> str:
        """Rolling H1 bias calculation using bars before this timestamp."""
        h1_before = self.h1[self.h1["time"] < bar_time]
        if len(h1_before) < 20:
            return "NEUTRAL"
        # Use last 40 H1 bars for swing detection
        recent = h1_before.tail(40).reset_index(drop=True)
        sh, sl = find_swings(recent, lookback=2)
        return get_h1_bias(sh, sl)

    def _get_recent_swing_lows(self, before_idx: int, count: int = 8) -> List[Tuple[int, float]]:
        """M15 swing lows before a given index."""
        result = []
        for idx, price in reversed(self.m15_swing_lows):
            if idx < before_idx - 3:  # Must be at least 3 bars old
                result.append((idx, price))
                if len(result) >= count:
                    break
        return result

    def _get_recent_swing_highs(self, before_idx: int, count: int = 8) -> List[Tuple[int, float]]:
        result = []
        for idx, price in reversed(self.m15_swing_highs):
            if idx < before_idx - 3:
                result.append((idx, price))
                if len(result) >= count:
                    break
        return result

    def run(self):
        """Main loop over M15 bars."""
        print(f"\nRunning V5 on {len(self.m15)} M15 bars...")
        print(f"Date range: {self.m15.iloc[0]['time']} to {self.m15.iloc[-1]['time']}")

        for i in range(50, len(self.m15)):
            self.debug["bars"] += 1
            self._check_exits(i)
            self._check_entry(i)

            # Track equity
            open_pnl = 0
            for t in self.trades:
                if t["status"] == "OPEN":
                    bar = self.m15.iloc[i]
                    if t["direction"] == "BUY":
                        open_pnl += (bar["close"] - t["entry_price"]) * t["lot_size"] * PIP_VALUE_PER_LOT
                    else:
                        open_pnl += (t["entry_price"] - bar["close"]) * t["lot_size"] * PIP_VALUE_PER_LOT
            self.equity_curve.append(self.balance + open_pnl)

        # Close remaining
        if any(t["status"] == "OPEN" for t in self.trades):
            last = self.m15.iloc[-1]
            for t in self.trades:
                if t["status"] == "OPEN":
                    self._close_trade(t, last["close"], "END_OF_DATA", last["time"])

    def _check_entry(self, idx: int):
        if self._has_open_trade():
            self.debug["blocked_open"] += 1
            return

        bar = self.m15.iloc[idx]
        bar_time = bar["time"]
        atr = bar["atr"]

        if pd.isna(atr) or atr < 1.0:
            return

        # Session check
        session = self._get_session(bar_time.hour)
        if session is None:
            return
        self.debug["in_session"] += 1

        # Max 2 trades per day
        day = bar_time.date()
        day_trades = sum(1 for t in self.trades
                         if hasattr(t["entry_time"], "date") and t["entry_time"].date() == day)
        if day_trades >= 2:
            self.debug["blocked_daily"] += 1
            return

        # 2-hour cooldown after SL
        if self.last_sl_hit_time:
            if bar_time - self.last_sl_hit_time < timedelta(hours=2):
                self.debug["blocked_cooldown"] += 1
                return

        # Daily loss limit: -5% of initial
        daily_pnl = sum(t["pnl"] for t in self.trade_log
                        if hasattr(t["entry_time"], "date") and t["entry_time"].date() == day)
        if daily_pnl <= -0.05 * self.initial_balance:
            return

        # H1 bias
        h1_bias = self._get_h1_bias_at(bar_time)
        if h1_bias == "NEUTRAL":
            return
        self.debug["h1_bias_ok"] += 1

        # ── LIQUIDITY SWEEP DETECTION ──
        # Check current bar and 2 previous bars for sweep of M15 swing levels

        if h1_bias == "BULLISH":
            swing_lows = self._get_recent_swing_lows(idx, count=8)
            if not swing_lows:
                return

            for sw_idx, sw_price in swing_lows:
                # Skip if swing is too old (> 200 bars = ~3 days)
                if idx - sw_idx > 200:
                    continue

                # Check last 3 bars for sweep
                for lb in range(0, 3):
                    ci = idx - lb
                    if ci < 0:
                        continue
                    c_bar = self.m15.iloc[ci]

                    # SWEEP: wick below swing low, close above it
                    if c_bar["low"] < sw_price and c_bar["close"] > sw_price:
                        self.debug["sweep_found"] += 1
                        sweep_wick = sw_price - c_bar["low"]

                        # Confirm: next bar(s) should show buying pressure
                        # (current bar closing above sweep level IS the confirmation)
                        # Also check EMA alignment
                        ema_ok = bar["close"] > bar["ema50"]

                        # Strong sweep: wick depth > 0.3 ATR
                        if sweep_wick < 0.15 * atr:
                            continue  # Too shallow, likely just noise

                        self.debug["entry_confirmed"] += 1

                        # ── ENTER BUY ──
                        entry_price = bar["close"] + (self.spread + self.slippage) * PIP

                        # SL: below sweep wick + ATR buffer (confident SL)
                        sl_price = c_bar["low"] - atr * 0.3
                        sl_pips = (entry_price - sl_price) / PIP

                        # Hard clamp SL for 0.1 lot users
                        sl_pips = max(MIN_SL_PIPS, min(MAX_SL_PIPS, sl_pips))
                        sl_price = entry_price - sl_pips * PIP

                        if sl_pips <= 0:
                            continue

                        # Lot size: fixed lot or risk-based
                        if self.fixed_lot > 0:
                            lot_size = self.fixed_lot
                            risk_usd = sl_pips * PIP_VALUE_PER_LOT * lot_size
                        else:
                            risk_usd = self.balance * self.risk_pct / 100
                            lot_size = risk_usd / (sl_pips * PIP_VALUE_PER_LOT)
                        if lot_size <= 0:
                            continue

                        # Score quality (simple: sweep depth + EMA + session)
                        quality = 0
                        quality += min(20, int(sweep_wick / atr * 30))
                        quality += 15 if ema_ok else 0
                        quality += 15 if session == "LONDON" else (10 if session == "NY" else 5)
                        quality += 10 if h1_bias == "BULLISH" else 0

                        grade = "A" if quality >= 45 else ("B" if quality >= 30 else "C")
                        if quality < 25:
                            continue

                        self._enter_trade(
                            "BUY", bar_time, entry_price, sl_price, sl_pips,
                            lot_size, risk_usd, grade, quality, session,
                            sweep_wick / PIP
                        )
                        return

        elif h1_bias == "BEARISH":
            swing_highs = self._get_recent_swing_highs(idx, count=8)
            if not swing_highs:
                return

            for sw_idx, sw_price in swing_highs:
                if idx - sw_idx > 200:
                    continue

                for lb in range(0, 3):
                    ci = idx - lb
                    if ci < 0:
                        continue
                    c_bar = self.m15.iloc[ci]

                    # SWEEP: wick above swing high, close below it
                    if c_bar["high"] > sw_price and c_bar["close"] < sw_price:
                        self.debug["sweep_found"] += 1
                        sweep_wick = c_bar["high"] - sw_price

                        ema_ok = bar["close"] < bar["ema50"]

                        if sweep_wick < 0.15 * atr:
                            continue

                        self.debug["entry_confirmed"] += 1

                        # ── ENTER SELL ──
                        entry_price = bar["close"] - (self.spread + self.slippage) * PIP

                        sl_price = c_bar["high"] + atr * 0.3
                        sl_pips = (sl_price - entry_price) / PIP

                        # Hard clamp SL for 0.1 lot users
                        sl_pips = max(MIN_SL_PIPS, min(MAX_SL_PIPS, sl_pips))
                        sl_price = entry_price + sl_pips * PIP

                        if sl_pips <= 0:
                            continue

                        # Lot size: fixed lot or risk-based
                        if self.fixed_lot > 0:
                            lot_size = self.fixed_lot
                            risk_usd = sl_pips * PIP_VALUE_PER_LOT * lot_size
                        else:
                            risk_usd = self.balance * self.risk_pct / 100
                            lot_size = risk_usd / (sl_pips * PIP_VALUE_PER_LOT)
                        if lot_size <= 0:
                            continue

                        quality = 0
                        quality += min(20, int(sweep_wick / atr * 30))
                        quality += 15 if ema_ok else 0
                        quality += 15 if session == "LONDON" else (10 if session == "NY" else 5)
                        quality += 10 if h1_bias == "BEARISH" else 0

                        grade = "A" if quality >= 45 else ("B" if quality >= 30 else "C")
                        if quality < 25:
                            continue

                        self._enter_trade(
                            "SELL", bar_time, entry_price, sl_price, sl_pips,
                            lot_size, risk_usd, grade, quality, session,
                            sweep_wick / PIP
                        )
                        return

    def _enter_trade(
        self, direction, entry_time, entry_price, sl_price, sl_pips,
        lot_size, risk_usd, grade, quality, session, sweep_pips
    ):
        trade = {
            "entry_time": entry_time,
            "entry_price": entry_price,
            "direction": direction,
            "sl_price": sl_price,
            "sl_pips": sl_pips,
            "lot_size": lot_size,
            "risk_usd": risk_usd,
            "grade": grade,
            "quality": quality,
            "status": "OPEN",
            "tp_hit": 0,
            "close_price": None,
            "close_reason": None,
            "close_time": None,
            "pnl": 0,
            "r_multiple": 0,
            "session": session,
            "sweep_pips": sweep_pips,
            "partial_pnl": 0,
            "remaining_pct": 1.0,
        }
        self.trades.append(trade)
        self.last_trade_time = entry_time
        self.debug["trades_entered"] += 1

    # ================================================================
    # EXIT LOGIC — SHORT RANGE TP
    # ================================================================

    def _check_exits(self, idx: int):
        bar = self.m15.iloc[idx]
        bar_time = bar["time"]

        for trade in self.trades:
            if trade["status"] != "OPEN":
                continue

            entry = trade["entry_price"]
            sl_dist = trade["sl_pips"] * PIP

            if trade["direction"] == "BUY":
                # SL check
                if bar["low"] <= trade["sl_price"]:
                    close_price = min(bar["open"], trade["sl_price"])
                    close_price -= self.slippage * PIP
                    self._close_trade(trade, close_price, "SL_HIT", bar_time)
                    self.last_sl_hit_time = bar_time
                    continue

                # TP levels (short range: 1.5R, 2.5R, 3.5R)
                prev_tp = trade["tp_hit"]
                for tp_lvl in range(prev_tp, len(self.tp_levels)):
                    tp_price = entry + sl_dist * self.tp_levels[tp_lvl]
                    if bar["high"] >= tp_price:
                        trade["tp_hit"] = tp_lvl + 1
                        pct = self.tp_close_pct[tp_lvl]

                        # Book partial profit
                        partial = (tp_price - entry) * pct * trade["lot_size"] * PIP_VALUE_PER_LOT
                        trade["partial_pnl"] += partial
                        trade["remaining_pct"] -= pct

                        # Move SL after TP1
                        if tp_lvl == 0:
                            trade["sl_price"] = entry + 1 * PIP  # BE + 1 pip
                        elif tp_lvl == 1:
                            trade["sl_price"] = max(
                                trade["sl_price"],
                                entry + sl_dist * self.tp_levels[0]  # Lock TP1
                            )
                    else:
                        break

                # All TPs hit
                if trade["tp_hit"] >= len(self.tp_levels):
                    final_tp = entry + sl_dist * self.tp_levels[-1]
                    self._close_trade(trade, final_tp, "ALL_TP", bar_time)

            elif trade["direction"] == "SELL":
                if bar["high"] >= trade["sl_price"]:
                    close_price = max(bar["open"], trade["sl_price"])
                    close_price += self.slippage * PIP
                    self._close_trade(trade, close_price, "SL_HIT", bar_time)
                    self.last_sl_hit_time = bar_time
                    continue

                prev_tp = trade["tp_hit"]
                for tp_lvl in range(prev_tp, len(self.tp_levels)):
                    tp_price = entry - sl_dist * self.tp_levels[tp_lvl]
                    if bar["low"] <= tp_price:
                        trade["tp_hit"] = tp_lvl + 1
                        pct = self.tp_close_pct[tp_lvl]

                        partial = (entry - tp_price) * pct * trade["lot_size"] * PIP_VALUE_PER_LOT
                        trade["partial_pnl"] += partial
                        trade["remaining_pct"] -= pct

                        if tp_lvl == 0:
                            trade["sl_price"] = entry - 1 * PIP
                        elif tp_lvl == 1:
                            trade["sl_price"] = min(
                                trade["sl_price"],
                                entry - sl_dist * self.tp_levels[0]
                            )
                    else:
                        break

                if trade["tp_hit"] >= len(self.tp_levels):
                    final_tp = entry - sl_dist * self.tp_levels[-1]
                    self._close_trade(trade, final_tp, "ALL_TP", bar_time)

    def _close_trade(self, trade: Dict, close_price: float, reason: str, close_time):
        trade["close_price"] = close_price
        trade["close_reason"] = reason
        trade["close_time"] = close_time

        entry = trade["entry_price"]
        remaining = trade["remaining_pct"]

        # PnL from remaining position
        if trade["direction"] == "BUY":
            remaining_pnl = (close_price - entry) * remaining * trade["lot_size"] * PIP_VALUE_PER_LOT
        else:
            remaining_pnl = (entry - close_price) * remaining * trade["lot_size"] * PIP_VALUE_PER_LOT

        total_pnl = trade["partial_pnl"] + remaining_pnl
        trade["pnl"] = total_pnl
        trade["r_multiple"] = total_pnl / trade["risk_usd"] if trade["risk_usd"] > 0 else 0
        trade["status"] = "CLOSED"

        self.balance += total_pnl

        self.trade_log.append({
            "entry_time": trade["entry_time"],
            "close_time": close_time,
            "direction": trade["direction"],
            "entry_price": entry,
            "close_price": close_price,
            "grade": trade["grade"],
            "quality": trade["quality"],
            "r_multiple": trade["r_multiple"],
            "pnl": total_pnl,
            "tp_hit": trade["tp_hit"],
            "reason": reason,
            "session": trade["session"],
            "sweep_pips": trade["sweep_pips"],
            "sl_pips": trade["sl_pips"],
        })

    # ================================================================
    # REPORT
    # ================================================================

    def print_report(self):
        if not self.trade_log:
            print("\nNo trades executed.")
            return

        tdf = pd.DataFrame(self.trade_log)
        n = len(tdf)
        wins = (tdf["pnl"] > 0).sum()
        losses = (tdf["pnl"] < 0).sum()
        be = (tdf["pnl"] == 0).sum()
        wr = wins / n * 100

        gp = tdf[tdf["pnl"] > 0]["pnl"].sum()
        gl = abs(tdf[tdf["pnl"] < 0]["pnl"].sum())
        pf = gp / gl if gl > 0 else float("inf")
        total_pnl = tdf["pnl"].sum()

        avg_r = tdf["r_multiple"].mean()
        median_r = tdf["r_multiple"].median()

        avg_win = tdf[tdf["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
        avg_loss = tdf[tdf["pnl"] < 0]["pnl"].mean() if losses > 0 else 0
        expectancy = (wr / 100 * avg_win) + ((1 - wr / 100) * avg_loss)

        # Drawdown
        cum = tdf["pnl"].cumsum()
        peak = cum.expanding().max()
        dd = cum - peak
        max_dd = dd.min()
        max_dd_pct = max_dd / self.initial_balance * 100

        ret_dd = total_pnl / abs(max_dd) if max_dd != 0 else 0

        # Streaks
        tdf["win"] = tdf["pnl"] > 0
        tdf["streak"] = (tdf["win"] != tdf["win"].shift()).cumsum()
        max_wins = tdf[tdf["win"]].groupby("streak").size().max() if wins > 0 else 0
        max_losses = tdf[~tdf["win"]].groupby("streak").size().max() if losses > 0 else 0

        # By session
        sessions = {}
        for sess in ["LONDON", "NY", "PRE_LONDON"]:
            s_df = tdf[tdf["session"] == sess]
            if len(s_df) > 0:
                s_wr = (s_df["pnl"] > 0).sum() / len(s_df) * 100
                sessions[sess] = {"n": len(s_df), "wr": s_wr, "pnl": s_df["pnl"].sum(), "avg_r": s_df["r_multiple"].mean()}

        # By grade
        for g in ["A", "B", "C"]:
            g_df = tdf[tdf["grade"] == g]
            if len(g_df) > 0:
                pass  # Will print below

        # TP distribution
        tp_dist = tdf["tp_hit"].value_counts().sort_index()

        print(f"\n{'='*70}")
        print(f"  XAUUSD V5 — SHORT-RANGE LIQUIDITY SWEEP")
        print(f"  H1 Bias + M15 Sweep + Conservative TP")
        print(f"{'='*70}")

        print(f"\n  PERFORMANCE")
        print(f"    Trades:             {n}")
        print(f"    Wins:               {wins} ({wr:.1f}%)")
        print(f"    Losses:             {losses}")
        print(f"    Breakeven:          {be}")
        print(f"    Profit Factor:      {pf:.2f}")
        print(f"    Total PnL:          ${total_pnl:,.2f}")
        print(f"    Return:             {total_pnl / self.initial_balance * 100:+.2f}%")
        print(f"    Final Balance:      ${self.balance:,.2f}")

        print(f"\n  RISK")
        print(f"    Avg R:              {avg_r:+.2f}R")
        print(f"    Median R:           {median_r:+.2f}R")
        print(f"    Max Drawdown:       ${max_dd:,.2f} ({max_dd_pct:.2f}%)")
        print(f"    Return/DD:          {ret_dd:.2f}")
        print(f"    Expectancy/Trade:   ${expectancy:,.2f}")
        print(f"    Avg Win:            ${avg_win:,.2f}")
        print(f"    Avg Loss:           ${avg_loss:,.2f}")

        print(f"\n  STREAKS")
        print(f"    Max Consecutive W:  {max_wins}")
        print(f"    Max Consecutive L:  {max_losses}")

        print(f"\n  TP DISTRIBUTION")
        for tp_lvl, count in tp_dist.items():
            pct = count / n * 100
            label = f"TP{tp_lvl}" if tp_lvl > 0 else "No TP (SL)"
            print(f"    {label}: {count} ({pct:.0f}%)")

        print(f"\n  BY SESSION")
        for sess, data in sessions.items():
            print(f"    {sess:12s}: {data['n']:>3} trades, WR {data['wr']:.0f}%, PnL ${data['pnl']:>+8,.0f}, Avg {data['avg_r']:+.2f}R")

        print(f"\n  BY GRADE")
        for g in ["A", "B", "C"]:
            g_df = tdf[tdf["grade"] == g]
            if len(g_df) > 0:
                g_wr = (g_df["pnl"] > 0).sum() / len(g_df) * 100
                print(f"    Grade {g}: {len(g_df)} trades, WR {g_wr:.0f}%, PnL ${g_df['pnl'].sum():>+8,.0f}, Avg {g_df['r_multiple'].mean():+.2f}R")

        # Monthly
        tdf["month"] = pd.to_datetime(tdf["entry_time"]).dt.to_period("M")
        monthly = tdf.groupby("month").agg(
            trades=("pnl", "count"),
            pnl=("pnl", "sum"),
            wr=("pnl", lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0)
        )
        print(f"\n  MONTHLY")
        for period, row in monthly.iterrows():
            print(f"    {period}: {int(row['trades']):>3} trades, ${row['pnl']:>+8,.0f}, WR {row['wr']:.0f}%")

        # Trade log
        print(f"\n  TRADE LOG (Last 25)")
        print(f"  {'Time':<16} {'Dir':<5} {'Gr':<3} {'R':>6} {'PnL':>8} {'TP':>3} {'SL':>5} {'Reason':<10} {'Sess':<10}")
        print(f"  {'-'*75}")
        for _, r in tdf.tail(25).iterrows():
            ts = r["entry_time"]
            ts_str = ts.strftime("%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)[:11]
            print(f"  {ts_str:<16} {r['direction']:<5} {r['grade']:<3} {r['r_multiple']:>+6.2f} ${r['pnl']:>7,.0f} {r['tp_hit']:>3} {r['sl_pips']:>5.0f} {r['reason']:<10} {r['session']:<10}")

        # Verdict
        print(f"\n{'='*70}")
        print(f"  VERDICT")
        print(f"{'='*70}")

        if pf >= 1.5 and wr >= 40 and max_dd_pct > -15:
            print(f"  TRADEABLE EDGE. Proceed to 2-week paper trading.")
            print(f"  Expected: ~{n // 6:.0f} trades/month, ${expectancy:,.0f}/trade expectancy")
        elif pf >= 1.2 and wr >= 35:
            print(f"  MARGINAL EDGE. Needs refinement before live trading.")
            if wr < 40:
                print(f"  - Win rate {wr:.0f}% is borderline. Tighten entry filters.")
            if max_dd_pct < -15:
                print(f"  - Drawdown {max_dd_pct:.1f}% too deep. Lower risk to 1.5%.")
        elif pf >= 1.0:
            print(f"  BREAKEVEN. Strategy doesn't have enough edge yet.")
        else:
            print(f"  NEGATIVE. Strategy loses money on this dataset.")
            if wr < 35:
                print(f"  - Win rate too low ({wr:.0f}%). Sweep detection needs tuning.")
            if avg_r < -0.3:
                print(f"  - Average R too negative ({avg_r:.2f}). SL/TP structure broken.")

        print(f"\n{'='*70}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="XAUUSD V5 Short-Range Sweep")
    parser.add_argument("--csv", default="dukascopy_xauusd_m15.csv")
    parser.add_argument("--balance", type=float, default=DEFAULT_BALANCE)
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--lot", type=float, default=DEFAULT_LOT_SIZE,
                        help="Fixed lot size (0.1 = micro). Set 0 for dynamic risk-based sizing.")
    args = parser.parse_args()

    try:
        df = load_csv(args.csv)
        print(f"Loaded {len(df)} M15 bars from {args.csv}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    bt = ShortRangeSweepBacktester(df, args.balance, args.risk, args.lot)
    bt.run()

    # Pipeline debug
    d = bt.debug
    print(f"\n{'='*60}")
    print(f"  PIPELINE DEBUG")
    print(f"{'='*60}")
    print(f"  Bars scanned:        {d['bars']}")
    print(f"  In active session:   {d['in_session']}")
    print(f"  H1 bias confirmed:   {d['h1_bias_ok']}")
    print(f"  Sweeps detected:     {d['sweep_found']}")
    print(f"  Entry confirmed:     {d['entry_confirmed']}")
    print(f"  Trades entered:      {d['trades_entered']}")
    print(f"  Blocked (open):      {d['blocked_open']}")
    print(f"  Blocked (daily):     {d['blocked_daily']}")
    print(f"  Blocked (cooldown):  {d['blocked_cooldown']}")
    print(f"{'='*60}")

    bt.print_report()


if __name__ == "__main__":
    main()
