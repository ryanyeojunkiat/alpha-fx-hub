#!/usr/bin/env python3
"""
XAUUSD M15 Smart Money Concepts (SMC) Backtester v4
Liquidity Sweep + FVG Retest Strategy
Complete standalone implementation
"""

import sys
import argparse
import os
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json

# ============================================================================
# CONSTANTS
# ============================================================================
PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
DEFAULT_BALANCE = 10000
DEFAULT_RISK_PCT = 2.0
DEFAULT_SPREAD_PIPS = 2.0
DEFAULT_SLIPPAGE_PIPS = 0.5

# Killzone times (UTC)
LONDON_OPEN_START = 7
LONDON_OPEN_END = 10
NY_OPEN_START = 12
NY_OPEN_END = 15

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_env_file(path=".env") -> Dict[str, str]:
    """Load environment variables from .env file"""
    env_vars = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


def load_csv_data(filepath: str) -> pd.DataFrame:
    """Load XAUUSD M15 data from CSV"""
    df = pd.read_csv(filepath)

    # Ensure required columns exist
    required = ["time", "open", "high", "low", "close", "volume"]
    if not all(col in df.columns for col in required):
        raise ValueError(f"CSV must have columns: {required}")

    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    return atr


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (simplified)"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    # Plus and Minus Directional Movement
    up = high.diff()
    down = low.diff() * -1

    plus_dm = up.copy()
    plus_dm[up <= down] = 0
    plus_dm[plus_dm < 0] = 0

    minus_dm = down.copy()
    minus_dm[down <= up] = 0
    minus_dm[minus_dm < 0] = 0

    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smoothed DM and TR
    atr_val = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr_val)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr_val)

    # ADX
    di_diff = abs(plus_di - minus_di)
    di_sum = plus_di + minus_di
    di_ratio = di_diff / di_sum
    adx = 100 * di_ratio.rolling(window=period).mean()

    return adx.fillna(0)


def aggregate_to_h1(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate M15 data into H1 bars"""
    df_copy = df.copy()
    df_copy["hour"] = df_copy["time"].dt.floor("h")

    h1_data = df_copy.groupby("hour").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).reset_index()

    h1_data.rename(columns={"hour": "time"}, inplace=True)
    return h1_data


def find_h1_swings(h1_df: pd.DataFrame, lookback: int = 3) -> Tuple[pd.Series, pd.Series]:
    """Find H1 swing highs and swing lows"""
    swing_highs = pd.Series(False, index=h1_df.index)
    swing_lows = pd.Series(False, index=h1_df.index)

    for i in range(lookback, len(h1_df) - lookback):
        high_val = h1_df.iloc[i]["high"]
        low_val = h1_df.iloc[i]["low"]

        # Swing high: higher than lookback bars on each side
        if all(high_val > h1_df.iloc[j]["high"] for j in range(i - lookback, i)) and \
           all(high_val > h1_df.iloc[j]["high"] for j in range(i + 1, i + lookback + 1)):
            swing_highs.iloc[i] = True

        # Swing low: lower than lookback bars on each side
        if all(low_val < h1_df.iloc[j]["low"] for j in range(i - lookback, i)) and \
           all(low_val < h1_df.iloc[j]["low"] for j in range(i + 1, i + lookback + 1)):
            swing_lows.iloc[i] = True

    return swing_highs, swing_lows


def get_h1_bias(h1_df: pd.DataFrame, swing_highs: pd.Series, swing_lows: pd.Series) -> str:
    """Determine H1 market bias (Bullish, Bearish, Neutral)"""
    recent_swing_high_idx = None
    recent_swing_low_idx = None
    prev_swing_high_idx = None
    prev_swing_low_idx = None

    # Find the two most recent swing highs and lows
    for i in range(len(h1_df) - 1, -1, -1):
        if swing_highs.iloc[i] and recent_swing_high_idx is None:
            recent_swing_high_idx = i
        elif swing_highs.iloc[i] and prev_swing_high_idx is None:
            prev_swing_high_idx = i

        if swing_lows.iloc[i] and recent_swing_low_idx is None:
            recent_swing_low_idx = i
        elif swing_lows.iloc[i] and prev_swing_low_idx is None:
            prev_swing_low_idx = i

        if recent_swing_high_idx is not None and recent_swing_low_idx is not None and \
           prev_swing_high_idx is not None and prev_swing_low_idx is not None:
            break

    if recent_swing_high_idx is None or recent_swing_low_idx is None or \
       prev_swing_high_idx is None or prev_swing_low_idx is None:
        return "NEUTRAL"

    recent_high = h1_df.iloc[recent_swing_high_idx]["high"]
    recent_low = h1_df.iloc[recent_swing_low_idx]["low"]
    prev_high = h1_df.iloc[prev_swing_high_idx]["high"]
    prev_low = h1_df.iloc[prev_swing_low_idx]["low"]

    # Bullish: HH and HL
    if recent_high > prev_high and recent_low > prev_low:
        return "BULLISH"

    # Bearish: LH and LL
    if recent_high < prev_high and recent_low < prev_low:
        return "BEARISH"

    return "NEUTRAL"


def is_in_killzone(timestamp: pd.Timestamp) -> Tuple[bool, str]:
    """Check if timestamp is in a killzone and return which one"""
    hour = timestamp.hour

    if LONDON_OPEN_START <= hour < LONDON_OPEN_END:
        return True, "LONDON"
    elif NY_OPEN_START <= hour < NY_OPEN_END:
        return True, "NY"

    return False, ""


def detect_candle_strength(row: Dict, atr: float) -> bool:
    """Check if candle is strong enough (body > 60%, range > 0.5x ATR)"""
    body = abs(row["close"] - row["open"])
    range_val = row["high"] - row["low"]

    if range_val == 0:
        return False

    body_pct = body / range_val

    return body_pct > 0.60 and range_val > 0.5 * atr


def detect_fvg(df: pd.DataFrame, idx: int, direction: str, atr: float) -> Optional[Tuple[float, float]]:
    """
    Detect Fair Value Gap (FVG)
    direction: "BUY" or "SELL"
    Returns: (fvg_low, fvg_high) or None if no FVG
    """
    if idx < 2:
        return None

    candle_2 = df.iloc[idx - 2]
    candle_0 = df.iloc[idx]

    min_fvg_size = 0.3 * atr

    if direction == "BUY":
        # candle[i-2].high < candle[i].low
        if candle_2["high"] < candle_0["low"]:
            fvg_size = candle_0["low"] - candle_2["high"]
            if fvg_size >= min_fvg_size:
                return (candle_2["high"], candle_0["low"])

    elif direction == "SELL":
        # candle[i-2].low > candle[i].high
        if candle_2["low"] > candle_0["high"]:
            fvg_size = candle_2["low"] - candle_0["high"]
            if fvg_size >= min_fvg_size:
                return (candle_0["high"], candle_2["low"])

    return None


def calculate_trade_grade(
    h1_bias_strength: int,
    sweep_pips: float,
    displacement_strength: int,
    fvg_size: float,
    atr: float,
    killzone: str,
    adx: float
) -> int:
    """Calculate trade entry grade (max 85)"""
    grade = 0

    # H1 bias strength (0-15)
    grade += h1_bias_strength

    # Sweep quality (0-15): more pips = better
    sweep_grade = min(15, int((sweep_pips / atr) * 10))
    grade += sweep_grade

    # Displacement candle strength (0-15)
    grade += displacement_strength

    # FVG size relative to ATR (0-10)
    fvg_grade = min(10, int((fvg_size / atr) * 5))
    grade += fvg_grade

    # Killzone timing
    if killzone == "LONDON":
        grade += 10
    elif killzone == "NY":
        grade += 8

    # ADX trend confirmation (0-10)
    if adx > 25:
        grade += 10
    elif adx > 15:
        grade += 5

    # Cap at 85
    return min(85, grade)


# ============================================================================
# BACKTESTER CLASS
# ============================================================================

class SMCBacktester:
    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = DEFAULT_BALANCE,
        risk_pct: float = DEFAULT_RISK_PCT,
        spread_pips: float = DEFAULT_SPREAD_PIPS,
        slippage_pips: float = DEFAULT_SLIPPAGE_PIPS
    ):
        self.df = df.copy()
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_pct = risk_pct
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips

        # Calculate indicators
        self.df["atr"] = calculate_atr(self.df, 14)
        self.df["adx"] = calculate_adx(self.df, 14)

        # Map M15 bars to H1 for bias detection
        h1_df = aggregate_to_h1(self.df)
        swing_highs, swing_lows = find_h1_swings(h1_df)

        # Map H1 bias back to M15
        self.df["h1_time"] = self.df["time"].dt.floor("h")
        h1_df_indexed = h1_df.set_index("time")
        self.df["h1_bias"] = self.df["h1_time"].apply(
            lambda t: self._get_bias_for_time(t, h1_df, swing_highs, swing_lows)
        )

        self.h1_df = h1_df
        self.swing_highs = swing_highs
        self.swing_lows = swing_lows

        # Trade tracking
        self.trades = []
        self.trade_log = []
        self.last_trade_time = None
        self.last_trade_direction = None
        self.last_sl_hit_time = None
        self.daily_loss = {}

        # Debug counters for pipeline visibility
        self.debug = {
            "bars_scanned": 0,
            "in_killzone": 0,
            "bias_ok": 0,
            "sweeps_found": 0,
            "setups_found": 0,
            "trades_entered": 0,
            "blocked_by_open_trade": 0,
            "blocked_by_daily_limit": 0,
            "blocked_by_cooldown": 0,
        }

        # TP system configuration
        self.tp_multiples = [2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 9.0, 12.0]
        self.tp_lot_split = [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]

    def _get_bias_for_time(
        self,
        h1_time: pd.Timestamp,
        h1_df: pd.DataFrame,
        swing_highs: pd.Series,
        swing_lows: pd.Series
    ) -> str:
        """Get H1 bias for a given H1 time"""
        mask = h1_df["time"] == h1_time
        if not mask.any():
            return "NEUTRAL"

        idx = h1_df[mask].index[0]
        bias = get_h1_bias(h1_df.iloc[:idx+1], swing_highs.iloc[:idx+1], swing_lows.iloc[:idx+1])
        return bias

    def _pips_to_price(self, pips: float, current_price: float) -> float:
        """Convert pips to price movement"""
        return pips * PIP

    def _get_lot_size(self, risk_usd: float, sl_pips: float, current_price: float) -> float:
        """Calculate lot size based on risk"""
        sl_price = self._pips_to_price(sl_pips, current_price)
        if sl_price == 0:
            return 0
        return risk_usd / (sl_price * PIP_VALUE_PER_LOT)

    def run_backtest(self):
        """Execute the full backtest"""
        for i in range(len(self.df)):
            current_bar = self.df.iloc[i]

            # Skip if not enough data
            if pd.isna(self.df.iloc[i]["atr"]) or pd.isna(self.df.iloc[i]["adx"]):
                continue

            # Check if we should enter a trade
            self._check_entry(i)

            # Check exits for open trades
            self._check_exits(i)

        # Close any remaining open trades at last price
        if self.trades:
            last_bar = self.df.iloc[-1]
            for trade in self.trades:
                if trade["status"] == "OPEN":
                    self._close_trade(trade, last_bar["close"], "END_OF_DATA", last_bar["time"])

    def _has_open_trade(self) -> bool:
        """Check if there's currently an open trade."""
        return any(t["status"] == "OPEN" for t in self.trades)

    def _find_m15_swing_lows(self, df_slice: pd.DataFrame, n: int = 3) -> list:
        """Find swing lows in a slice of M15 data. Returns list of (index, price)."""
        swings = []
        for i in range(n, len(df_slice) - n):
            low_val = df_slice.iloc[i]["low"]
            if all(low_val < df_slice.iloc[j]["low"] for j in range(i - n, i)) and \
               all(low_val < df_slice.iloc[j]["low"] for j in range(i + 1, min(i + n + 1, len(df_slice)))):
                swings.append((df_slice.index[i], low_val))
        return swings

    def _find_m15_swing_highs(self, df_slice: pd.DataFrame, n: int = 3) -> list:
        """Find swing highs in a slice of M15 data. Returns list of (index, price)."""
        swings = []
        for i in range(n, len(df_slice) - n):
            high_val = df_slice.iloc[i]["high"]
            if all(high_val > df_slice.iloc[j]["high"] for j in range(i - n, i)) and \
               all(high_val > df_slice.iloc[j]["high"] for j in range(i + 1, min(i + n + 1, len(df_slice)))):
                swings.append((df_slice.index[i], high_val))
        return swings

    def _check_entry(self, bar_idx: int):
        """Check for entry signals using proper SMC liquidity sweep logic."""
        self.debug["bars_scanned"] += 1

        # Only allow one open trade at a time
        if self._has_open_trade():
            self.debug["blocked_by_open_trade"] += 1
            return

        current_bar = self.df.iloc[bar_idx]
        current_time = current_bar["time"]

        # Killzone check
        in_killzone, killzone_type = is_in_killzone(current_time)
        if not in_killzone:
            return
        self.debug["in_killzone"] += 1

        # Max 1 trade per day (UTC day)
        day_key = current_time.date()
        if self.last_trade_time and self.last_trade_time.date() == day_key:
            self.debug["blocked_by_daily_limit"] += 1
            return

        # 4-hour cooldown after SL hit
        if self.last_sl_hit_time:
            cooldown = timedelta(hours=4)
            if current_time - self.last_sl_hit_time < cooldown:
                self.debug["blocked_by_cooldown"] += 1
                return

        # Daily loss limit
        if day_key in self.daily_loss and self.daily_loss[day_key] <= -0.04 * self.initial_balance:
            return

        # H1 bias check
        h1_bias = current_bar["h1_bias"]
        if h1_bias == "NEUTRAL":
            return
        self.debug["bias_ok"] += 1

        # Minimum ATR
        atr = current_bar["atr"]
        if atr < 2.0:
            return

        # Need enough history for swing detection
        if bar_idx < 40:
            return

        # ── PROPER SMC SWEEP DETECTION ──
        # Step 1: Find liquidity levels from REFERENCE window (bars 10-40 back)
        #   These are prior swing highs/lows = resting liquidity
        ref_start = max(0, bar_idx - 40)
        ref_end = max(0, bar_idx - 5)  # exclude recent bars
        if ref_end <= ref_start:
            return

        ref_slice = self.df.iloc[ref_start:ref_end]

        # Step 2: Check if recent bars (last 5) swept a reference level then reversed
        recent_bars = self.df.iloc[max(0, bar_idx - 5):bar_idx + 1]

        if h1_bias == "BULLISH":
            # Find swing lows from reference window = buy-side liquidity below
            swing_lows = self._find_m15_swing_lows(ref_slice, n=2)
            if not swing_lows:
                # Fallback: just use the minimum of the reference range
                ref_min = ref_slice["low"].min()
                swing_lows = [(ref_start, ref_min)]

            # Check if any recent bar swept below a swing low then reversed
            for sw_idx, sw_price in swing_lows:
                for j in range(len(recent_bars)):
                    bar = recent_bars.iloc[j]
                    bar_real_idx = recent_bars.index[j]

                    # Sweep: wick below swing low, then close above it
                    if bar["low"] < sw_price and bar["close"] > sw_price:
                        self.debug["sweeps_found"] += 1
                        # We have a sweep! Now look for displacement + FVG
                        sweep_result = self._find_buy_setup_after_sweep(
                            bar_real_idx, bar_idx, sw_price, atr
                        )
                        if sweep_result:
                            self.debug["setups_found"] += 1
                            fvg_zone, disp_strength = sweep_result
                            self._execute_buy_setup_v2(
                                bar_idx, sw_price, fvg_zone, disp_strength,
                                atr, killzone_type
                            )
                            return

        elif h1_bias == "BEARISH":
            # Find swing highs from reference window = sell-side liquidity above
            swing_highs = self._find_m15_swing_highs(ref_slice, n=2)
            if not swing_highs:
                ref_max = ref_slice["high"].max()
                swing_highs = [(ref_start, ref_max)]

            for sw_idx, sw_price in swing_highs:
                for j in range(len(recent_bars)):
                    bar = recent_bars.iloc[j]
                    bar_real_idx = recent_bars.index[j]

                    # Sweep: wick above swing high, then close below it
                    if bar["high"] > sw_price and bar["close"] < sw_price:
                        self.debug["sweeps_found"] += 1
                        sweep_result = self._find_sell_setup_after_sweep(
                            bar_real_idx, bar_idx, sw_price, atr
                        )
                        if sweep_result:
                            self.debug["setups_found"] += 1
                            fvg_zone, disp_strength = sweep_result
                            self._execute_sell_setup_v2(
                                bar_idx, sw_price, fvg_zone, disp_strength,
                                atr, killzone_type
                            )
                            return

    def _find_buy_setup_after_sweep(
        self, sweep_bar_idx: int, current_idx: int, sweep_level: float, atr: float
    ) -> Optional[Tuple[Tuple[float, float], int]]:
        """
        After a bullish sweep (bar wicked below swing low then closed above),
        look for displacement candle + FVG in the bars that follow.
        Returns (fvg_zone, displacement_strength) or None.
        """
        # Look at bars after the sweep bar for displacement + FVG
        for offset in range(0, min(4, current_idx - sweep_bar_idx + 1)):
            disp_idx = sweep_bar_idx + offset
            if disp_idx >= len(self.df):
                break

            disp_bar = self.df.iloc[disp_idx]
            disp_strength = 0

            # Displacement = strong bullish candle (close > open)
            if disp_bar["close"] > disp_bar["open"]:
                body = disp_bar["close"] - disp_bar["open"]
                range_val = disp_bar["high"] - disp_bar["low"]
                if range_val > 0:
                    body_pct = body / range_val
                    if body_pct > 0.60 and range_val > 0.5 * atr:
                        disp_strength = 12
                    elif body_pct > 0.45 and range_val > 0.3 * atr:
                        disp_strength = 8
                    elif body_pct > 0.35:
                        disp_strength = 5

            if disp_strength == 0:
                continue

            # Look for FVG in the next 1-3 bars after displacement
            for fvg_offset in range(1, 4):
                fvg_idx = disp_idx + fvg_offset
                if fvg_idx >= len(self.df) or fvg_idx > current_idx:
                    break

                fvg = detect_fvg(self.df, fvg_idx, "BUY", atr)
                if fvg:
                    return (fvg, disp_strength)

            # Also allow entry without strict FVG if displacement is strong
            # Use the displacement candle's body as an "implied FVG" zone
            if disp_strength >= 8:
                implied_fvg = (disp_bar["open"], disp_bar["open"] + (disp_bar["close"] - disp_bar["open"]) * 0.5)
                return (implied_fvg, disp_strength)

        return None

    def _find_sell_setup_after_sweep(
        self, sweep_bar_idx: int, current_idx: int, sweep_level: float, atr: float
    ) -> Optional[Tuple[Tuple[float, float], int]]:
        """
        After a bearish sweep (bar wicked above swing high then closed below),
        look for displacement candle + FVG in the bars that follow.
        Returns (fvg_zone, displacement_strength) or None.
        """
        for offset in range(0, min(4, current_idx - sweep_bar_idx + 1)):
            disp_idx = sweep_bar_idx + offset
            if disp_idx >= len(self.df):
                break

            disp_bar = self.df.iloc[disp_idx]
            disp_strength = 0

            # Displacement = strong bearish candle (close < open)
            if disp_bar["close"] < disp_bar["open"]:
                body = disp_bar["open"] - disp_bar["close"]
                range_val = disp_bar["high"] - disp_bar["low"]
                if range_val > 0:
                    body_pct = body / range_val
                    if body_pct > 0.60 and range_val > 0.5 * atr:
                        disp_strength = 12
                    elif body_pct > 0.45 and range_val > 0.3 * atr:
                        disp_strength = 8
                    elif body_pct > 0.35:
                        disp_strength = 5

            if disp_strength == 0:
                continue

            # Look for FVG
            for fvg_offset in range(1, 4):
                fvg_idx = disp_idx + fvg_offset
                if fvg_idx >= len(self.df) or fvg_idx > current_idx:
                    break

                fvg = detect_fvg(self.df, fvg_idx, "SELL", atr)
                if fvg:
                    return (fvg, disp_strength)

            # Implied FVG from strong displacement
            if disp_strength >= 8:
                implied_fvg = (disp_bar["open"] - (disp_bar["open"] - disp_bar["close"]) * 0.5, disp_bar["open"])
                return (implied_fvg, disp_strength)

        return None

    def _execute_buy_setup_v2(
        self, bar_idx: int, sweep_level: float,
        fvg_zone: Tuple[float, float], disp_strength: int,
        atr: float, killzone: str
    ):
        """Execute a BUY trade from confirmed SMC setup."""
        current_bar = self.df.iloc[bar_idx]
        current_time = current_bar["time"]

        # Entry: current bar's close (we enter on the bar that completes the setup)
        entry_price = current_bar["close"]

        # Apply spread + slippage
        entry_price += self._pips_to_price(self.spread_pips + self.slippage_pips, entry_price)

        # SL below sweep level with buffer
        sl_buffer = max(2.0, atr * 0.2 / PIP)  # At least 2 pips below sweep
        sl_price = sweep_level - self._pips_to_price(sl_buffer, sweep_level)
        sl_pips = (entry_price - sl_price) / PIP

        # Constraint SL between 0.8x and 3x ATR (in pips)
        atr_pips = atr / PIP
        sl_pips = max(0.8 * atr_pips, min(3.0 * atr_pips, sl_pips))
        sl_price = entry_price - sl_pips * PIP

        if sl_pips <= 0:
            return

        # Calculate risk and lot size
        risk_usd = self.current_balance * self.risk_pct / 100
        lot_size = risk_usd / (sl_pips * PIP * PIP_VALUE_PER_LOT / PIP)
        # Simplified: lot_size = risk_usd / (sl_distance_in_dollars * pip_value)
        sl_distance_usd = sl_pips * PIP  # price distance
        lot_size = risk_usd / (sl_distance_usd * (PIP_VALUE_PER_LOT / PIP))

        if lot_size <= 0:
            return

        # Calculate grade
        h1_bias_strength = 15
        fvg_size = fvg_zone[1] - fvg_zone[0]
        adx = current_bar["adx"]

        grade = calculate_trade_grade(
            h1_bias_strength, sl_pips * PIP / atr * 10, disp_strength,
            fvg_size, atr, killzone, adx
        )

        grade_letter = "A" if grade >= 60 else ("B" if grade >= 45 else ("C" if grade >= 30 else "D"))

        if grade < 30:
            return  # Skip very low quality setups

        # Create trade
        trade = {
            "entry_time": current_time,
            "entry_price": entry_price,
            "direction": "BUY",
            "sl_price": sl_price,
            "sl_pips": sl_pips,
            "lot_size": lot_size,
            "risk_usd": risk_usd,
            "grade": grade_letter,
            "grade_score": grade,
            "status": "OPEN",
            "tp_hit": 0,
            "close_price": None,
            "close_reason": None,
            "close_time": None,
            "pnl": 0,
            "r_multiple": 0,
            "killzone": killzone
        }

        self.trades.append(trade)
        self.last_trade_time = current_time
        self.last_trade_direction = "BUY"

    def _execute_sell_setup_v2(
        self, bar_idx: int, sweep_level: float,
        fvg_zone: Tuple[float, float], disp_strength: int,
        atr: float, killzone: str
    ):
        """Execute a SELL trade from confirmed SMC setup."""
        current_bar = self.df.iloc[bar_idx]
        current_time = current_bar["time"]

        # Entry: current bar's close
        entry_price = current_bar["close"]

        # Apply spread + slippage
        entry_price -= self._pips_to_price(self.spread_pips + self.slippage_pips, entry_price)

        # SL above sweep level with buffer
        sl_buffer = max(2.0, atr * 0.2 / PIP)
        sl_price = sweep_level + self._pips_to_price(sl_buffer, sweep_level)
        sl_pips = (sl_price - entry_price) / PIP

        # Constraint SL
        atr_pips = atr / PIP
        sl_pips = max(0.8 * atr_pips, min(3.0 * atr_pips, sl_pips))
        sl_price = entry_price + sl_pips * PIP

        if sl_pips <= 0:
            return

        # Calculate risk and lot size
        risk_usd = self.current_balance * self.risk_pct / 100
        sl_distance_usd = sl_pips * PIP
        lot_size = risk_usd / (sl_distance_usd * (PIP_VALUE_PER_LOT / PIP))

        if lot_size <= 0:
            return

        # Calculate grade
        h1_bias_strength = 15
        fvg_size = fvg_zone[1] - fvg_zone[0]
        adx = current_bar["adx"]

        grade = calculate_trade_grade(
            h1_bias_strength, sl_pips * PIP / atr * 10, disp_strength,
            fvg_size, atr, killzone, adx
        )

        grade_letter = "A" if grade >= 60 else ("B" if grade >= 45 else ("C" if grade >= 30 else "D"))

        if grade < 30:
            return

        # Create trade
        trade = {
            "entry_time": current_time,
            "entry_price": entry_price,
            "direction": "SELL",
            "sl_price": sl_price,
            "sl_pips": sl_pips,
            "lot_size": lot_size,
            "risk_usd": risk_usd,
            "grade": grade_letter,
            "grade_score": grade,
            "status": "OPEN",
            "tp_hit": 0,
            "close_price": None,
            "close_reason": None,
            "close_time": None,
            "pnl": 0,
            "r_multiple": 0,
            "killzone": killzone
        }

        self.trades.append(trade)
        self.last_trade_time = current_time
        self.last_trade_direction = "SELL"

    def _check_exits(self, bar_idx: int):
        """Check stop-losses and take-profits with multi-level TP system."""
        current_bar = self.df.iloc[bar_idx]
        current_time = current_bar["time"]

        for trade in self.trades:
            if trade["status"] != "OPEN":
                continue

            entry = trade["entry_price"]
            sl_dist = trade["sl_pips"] * PIP  # SL distance in price

            if trade["direction"] == "BUY":
                # Check SL hit first
                if current_bar["low"] <= trade["sl_price"]:
                    close_price = min(current_bar["open"], trade["sl_price"])
                    close_price -= self._pips_to_price(self.slippage_pips, close_price)
                    self._close_trade(trade, close_price, "SL_HIT", current_time)
                    self.last_sl_hit_time = current_time
                    continue

                # Check TP levels progressively
                highest_tp_hit = trade["tp_hit"]
                for tp_level in range(highest_tp_hit + 1, len(self.tp_multiples) + 1):
                    if tp_level > len(self.tp_multiples):
                        break
                    tp_price = entry + sl_dist * self.tp_multiples[tp_level - 1]
                    if current_bar["high"] >= tp_price:
                        trade["tp_hit"] = tp_level

                        # Move SL to breakeven after TP1
                        if tp_level == 1:
                            trade["sl_price"] = entry + 2 * PIP  # BE + 2 pip buffer
                        elif tp_level >= 3:
                            # Trail SL to TP1 level
                            trade["sl_price"] = max(
                                trade["sl_price"],
                                entry + sl_dist * self.tp_multiples[0]
                            )
                        elif tp_level >= 6:
                            # Trail SL to TP3 level
                            trade["sl_price"] = max(
                                trade["sl_price"],
                                entry + sl_dist * self.tp_multiples[2]
                            )
                    else:
                        break

                # Close when all TP hit or after TP7+ and price reverses
                if trade["tp_hit"] >= len(self.tp_multiples):
                    tp_price = entry + sl_dist * self.tp_multiples[-1]
                    self._close_trade(trade, tp_price, "ALL_TP_HIT", current_time)

            elif trade["direction"] == "SELL":
                # Check SL hit
                if current_bar["high"] >= trade["sl_price"]:
                    close_price = max(current_bar["open"], trade["sl_price"])
                    close_price += self._pips_to_price(self.slippage_pips, close_price)
                    self._close_trade(trade, close_price, "SL_HIT", current_time)
                    self.last_sl_hit_time = current_time
                    continue

                # Check TP levels
                highest_tp_hit = trade["tp_hit"]
                for tp_level in range(highest_tp_hit + 1, len(self.tp_multiples) + 1):
                    if tp_level > len(self.tp_multiples):
                        break
                    tp_price = entry - sl_dist * self.tp_multiples[tp_level - 1]
                    if current_bar["low"] <= tp_price:
                        trade["tp_hit"] = tp_level

                        if tp_level == 1:
                            trade["sl_price"] = entry - 2 * PIP
                        elif tp_level >= 3:
                            trade["sl_price"] = min(
                                trade["sl_price"],
                                entry - sl_dist * self.tp_multiples[0]
                            )
                        elif tp_level >= 6:
                            trade["sl_price"] = min(
                                trade["sl_price"],
                                entry - sl_dist * self.tp_multiples[2]
                            )
                    else:
                        break

                if trade["tp_hit"] >= len(self.tp_multiples):
                    tp_price = entry - sl_dist * self.tp_multiples[-1]
                    self._close_trade(trade, tp_price, "ALL_TP_HIT", current_time)

    def _close_trade(self, trade: Dict, close_price: float, reason: str, close_time=None):
        """Close a trade with proper PnL calculation."""
        trade["close_price"] = close_price
        trade["close_reason"] = reason
        trade["close_time"] = close_time if close_time else self.df.iloc[-1]["time"]

        # Calculate PnL using the TP lot split if TPs were hit
        # For simplicity: calculate weighted average exit considering partial closes
        tp_hit = trade["tp_hit"]
        entry = trade["entry_price"]
        sl_dist = trade["sl_pips"] * PIP

        if tp_hit > 0 and reason == "SL_HIT":
            # Partial profits were taken at TP levels, then remaining hit SL
            total_pnl = 0
            remaining_pct = 1.0

            for tp_level in range(1, tp_hit + 1):
                if tp_level <= len(self.tp_lot_split):
                    pct = self.tp_lot_split[tp_level - 1]
                    if trade["direction"] == "BUY":
                        tp_price = entry + sl_dist * self.tp_multiples[tp_level - 1]
                        tp_pnl = (tp_price - entry) * pct * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)
                    else:
                        tp_price = entry - sl_dist * self.tp_multiples[tp_level - 1]
                        tp_pnl = (entry - tp_price) * pct * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)
                    total_pnl += tp_pnl
                    remaining_pct -= pct

            # Remaining position hit SL
            if trade["direction"] == "BUY":
                sl_pnl = (close_price - entry) * remaining_pct * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)
            else:
                sl_pnl = (entry - close_price) * remaining_pct * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)
            total_pnl += sl_pnl
            pnl = total_pnl
        else:
            # Simple close (no partial TPs, or all TPs hit)
            if trade["direction"] == "BUY":
                pnl = (close_price - entry) * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)
            else:
                pnl = (entry - close_price) * trade["lot_size"] * (PIP_VALUE_PER_LOT / PIP)

        # R-multiple based on original risk
        original_sl_dist = trade["sl_pips"] * PIP
        if original_sl_dist > 0:
            if trade["direction"] == "BUY":
                r_multiple = pnl / trade["risk_usd"] if trade["risk_usd"] > 0 else 0
            else:
                r_multiple = pnl / trade["risk_usd"] if trade["risk_usd"] > 0 else 0
        else:
            r_multiple = 0

        trade["pnl"] = pnl
        trade["r_multiple"] = r_multiple

        # Update balance
        self.current_balance += pnl

        # Track daily loss
        day_key = trade["entry_time"].date()
        if day_key not in self.daily_loss:
            self.daily_loss[day_key] = 0
        self.daily_loss[day_key] += pnl

        # Add to trade log
        self.trade_log.append({
            "entry_time": trade["entry_time"],
            "close_time": trade["close_time"],
            "direction": trade["direction"],
            "entry_price": trade["entry_price"],
            "close_price": close_price,
            "grade": trade["grade"],
            "r_multiple": r_multiple,
            "pnl": pnl,
            "tp_hit": trade["tp_hit"],
            "reason": reason,
            "killzone": trade["killzone"]
        })

        trade["status"] = "CLOSED"

    def print_report(self):
        """Print comprehensive backtest report"""
        if not self.trade_log:
            print("No trades executed.")
            return

        trade_df = pd.DataFrame(self.trade_log)

        # Basic metrics
        total_trades = len(trade_df)
        winning_trades = (trade_df["pnl"] > 0).sum()
        losing_trades = (trade_df["pnl"] < 0).sum()
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        gross_profit = trade_df[trade_df["pnl"] > 0]["pnl"].sum()
        gross_loss = abs(trade_df[trade_df["pnl"] < 0]["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        total_pnl = trade_df["pnl"].sum()

        avg_r = trade_df["r_multiple"].mean()
        median_r = trade_df["r_multiple"].median()

        # Drawdown
        cumulative_pnl = trade_df["pnl"].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown_usd = drawdown.min()
        max_drawdown_pct = (max_drawdown_usd / self.initial_balance * 100) if self.initial_balance > 0 else 0

        # Return to DD ratio
        return_to_dd = total_pnl / abs(max_drawdown_usd) if max_drawdown_usd != 0 else 0

        # Consecutive trades
        trade_df["win"] = trade_df["pnl"] > 0
        trade_df["win_streak"] = (trade_df["win"] != trade_df["win"].shift()).cumsum()
        max_consecutive_wins = (trade_df[trade_df["win"]].groupby("win_streak").size().max()) if any(trade_df["win"]) else 0
        max_consecutive_losses = (trade_df[~trade_df["win"]].groupby("win_streak").size().max()) if any(~trade_df["win"]) else 0

        # Outliers
        top_trade = trade_df["pnl"].max()
        top_3_trades = trade_df.nlargest(3, "pnl")["pnl"].sum()

        # By session
        london_trades = trade_df[trade_df["killzone"] == "LONDON"]
        ny_trades = trade_df[trade_df["killzone"] == "NY"]

        print("\n" + "=" * 80)
        print("XAUUSD M15 SMC BACKTESTER v4 - FINAL REPORT")
        print("=" * 80)

        print(f"\nPERFORMANCE SUMMARY")
        print(f"  Total Trades:            {total_trades}")
        print(f"  Winning Trades:          {winning_trades} ({win_rate:.1f}%)")
        print(f"  Losing Trades:           {losing_trades}")
        print(f"  Profit Factor:           {profit_factor:.2f}")
        print(f"  Total PnL:               ${total_pnl:,.2f}")
        print(f"  Return %:                {(total_pnl / self.initial_balance * 100):.2f}%")

        print(f"\nRISK METRICS")
        print(f"  Avg R per Trade:         {avg_r:.2f}R")
        print(f"  Median R per Trade:      {median_r:.2f}R")
        print(f"  Max Drawdown (USD):      ${max_drawdown_usd:,.2f}")
        print(f"  Max Drawdown (pct):      {max_drawdown_pct:.2f}%")
        print(f"  Return/DD Ratio:         {return_to_dd:.2f}")

        print(f"\nCONSECUTIVE RESULTS")
        print(f"  Max Consecutive Wins:    {max_consecutive_wins}")
        print(f"  Max Consecutive Losses:  {max_consecutive_losses}")

        print(f"\nOUTLIER CONTRIBUTION")
        print(f"  Top Trade PnL:           ${top_trade:,.2f}")
        print(f"  Top 3 Trades Combined:   ${top_3_trades:,.2f}")
        print(f"  Top 3 as % of Total:     {(top_3_trades / total_pnl * 100) if total_pnl > 0 else 0:.1f}%")

        print(f"\nBY SESSION")
        print(f"  London Open Trades:      {len(london_trades)}")
        if len(london_trades) > 0:
            london_wr = (london_trades["pnl"] > 0).sum() / len(london_trades) * 100
            print(f"    Win Rate:              {london_wr:.1f}%")
            print(f"    Avg R:                 {london_trades['r_multiple'].mean():.2f}R")

        print(f"  NY Open Trades:          {len(ny_trades)}")
        if len(ny_trades) > 0:
            ny_wr = (ny_trades["pnl"] > 0).sum() / len(ny_trades) * 100
            print(f"    Win Rate:              {ny_wr:.1f}%")
            print(f"    Avg R:                 {ny_trades['r_multiple'].mean():.2f}R")

        print(f"\nTRADE LOG (Last 20)")
        print(f"{'Entry Time':<20} {'Dir':<5} {'Grade':<6} {'R':<8} {'PnL':<12} {'TP':<4} {'Reason':<15}")
        print("-" * 80)

        for _, row in trade_df.tail(20).iterrows():
            entry_str = row["entry_time"].strftime("%Y-%m-%d %H:%M")
            r_str = f"{row['r_multiple']:.2f}"
            pnl_str = f"${row['pnl']:,.0f}"
            print(f"{entry_str:<20} {row['direction']:<5} {row['grade']:<6} {r_str:<8} {pnl_str:<12} {row['tp_hit']:<4} {row['reason']:<15}")

        # Honest verdict
        print(f"\n" + "=" * 80)
        print("HONEST VERDICT")
        print("=" * 80)

        if profit_factor > 1.3 and median_r > 0:
            verdict = "POSITIVE EDGE — proceed to paper trading"
        elif profit_factor > 1.0:
            verdict = "MARGINAL — needs more data or refinement"
        else:
            verdict = "NEGATIVE — SMC detection needs improvement or gold M15 is not suitable"

        print(f"Verdict: {verdict}")

        # Strategy weaknesses
        print(f"\nSTRATEGY WEAKNESSES")
        weaknesses = []

        if win_rate < 40:
            weaknesses.append("  - Low win rate (<40%): FVG detection may be too loose")

        if max_consecutive_losses > 3:
            weaknesses.append(f"  - High consecutive losses ({max_consecutive_losses}): Needs better bias confirmation")

        if max_drawdown_pct > 10:
            weaknesses.append(f"  - High drawdown ({max_drawdown_pct:.1f}%): Risk management may be too aggressive")

        if len(london_trades) == 0 and len(ny_trades) == 0:
            weaknesses.append("  - No trades in main killzones: Entry logic needs review")

        if avg_r < 0.5:
            weaknesses.append("  - Low average R: Trade structure (R:R) needs improvement")

        if profit_factor < 1.0:
            weaknesses.append("  - Losing money: Strategy fundamentals are flawed")

        if weaknesses:
            for w in weaknesses:
                print(w)
        else:
            print("  None identified. Strategy shows consistent profitability.")

        print("\n" + "=" * 80)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="XAUUSD M15 SMC Backtester v4")
    parser.add_argument("--csv", type=str, default="dukascopy_xauusd_m15.csv",
                        help="Path to CSV data file")
    parser.add_argument("--balance", type=float, default=DEFAULT_BALANCE,
                        help="Initial balance, default 10000")
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT,
                        help="Risk per trade percent, default 2")

    args = parser.parse_args()

    # Load data
    try:
        df = load_csv_data(args.csv)
        print(f"Loaded {len(df)} M15 bars from {args.csv}")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        sys.exit(1)

    # Run backtest
    backtester = SMCBacktester(
        df,
        initial_balance=args.balance,
        risk_pct=args.risk
    )

    backtester.run_backtest()

    # Print pipeline debug summary
    d = backtester.debug
    print(f"\n{'='*60}")
    print("PIPELINE DEBUG SUMMARY")
    print(f"{'='*60}")
    print(f"  Bars scanned:            {d['bars_scanned']}")
    print(f"  In killzone:             {d['in_killzone']}")
    print(f"  H1 bias OK:             {d['bias_ok']}")
    print(f"  Sweeps detected:         {d['sweeps_found']}")
    print(f"  Full setups found:       {d['setups_found']}")
    print(f"  Trades entered:          {len(backtester.trade_log)}")
    print(f"  Blocked by open trade:   {d['blocked_by_open_trade']}")
    print(f"  Blocked by daily limit:  {d['blocked_by_daily_limit']}")
    print(f"  Blocked by cooldown:     {d['blocked_by_cooldown']}")
    print(f"{'='*60}")

    backtester.print_report()


if __name__ == "__main__":
    main()
