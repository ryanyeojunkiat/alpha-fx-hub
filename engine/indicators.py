"""
Alpha FX Hub — Technical Indicators
Carries forward best indicators from Gold Engine V4.
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to OHLCV dataframe."""
    if df is None or len(df) < 5:
        return df

    df = df.copy()
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)

    # ── EMAs ──
    for period in [9, 20, 21, 50, 200]:
        col = f"ema{period}"
        if len(c) >= period:
            df[col] = c.ewm(span=period, adjust=False).mean()
        else:
            df[col] = c

    # ── ATR (14) ──
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs()
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    # ── RSI (14) ──
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df["rsi14"] = 100 - (100 / (1 + rs))

    # ── MACD ──
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ── Bollinger Bands (20, 2) ──
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_mid"] = sma20
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20

    # ── Stochastic RSI ──
    rsi = df["rsi14"]
    rsi_min = rsi.rolling(14).min()
    rsi_max = rsi.rolling(14).max()
    rsi_range = rsi_max - rsi_min
    df["stoch_rsi"] = ((rsi - rsi_min) / rsi_range.replace(0, 1e-10)) * 100
    df["stoch_rsi_k"] = df["stoch_rsi"].rolling(3).mean()
    df["stoch_rsi_d"] = df["stoch_rsi_k"].rolling(3).mean()

    # ── ADX (14) ──
    plus_dm = h.diff()
    minus_dm = -l.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr_smooth = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, min_periods=14, adjust=False).mean() / atr_smooth.replace(0, 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, min_periods=14, adjust=False).mean() / atr_smooth.replace(0, 1e-10))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10))
    df["adx"] = dx.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    return df


def find_swing_points(df: pd.DataFrame, left: int = 5, right: int = 5) -> Tuple[List[dict], List[dict]]:
    """Find swing highs and swing lows using pivot detection."""
    highs, lows = [], []
    if df is None or len(df) < left + right + 1:
        return highs, lows

    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)

    for i in range(left, len(df) - right):
        # Swing high: highest point in window
        if h[i] == max(h[i - left: i + right + 1]):
            highs.append({"index": i, "price": h[i], "time": df.index[i] if hasattr(df.index, '__getitem__') else i})
        # Swing low: lowest point in window
        if l[i] == min(l[i - left: i + right + 1]):
            lows.append({"index": i, "price": l[i], "time": df.index[i] if hasattr(df.index, '__getitem__') else i})

    return highs, lows


def fibonacci_levels(swing_high: float, swing_low: float, direction: str) -> dict:
    """Calculate Fibonacci retracement levels."""
    diff = swing_high - swing_low
    if direction == "bull":
        return {
            "0.0": swing_low,
            "0.236": swing_low + 0.236 * diff,
            "0.382": swing_low + 0.382 * diff,
            "0.5":   swing_low + 0.5 * diff,
            "0.618": swing_low + 0.618 * diff,
            "0.65":  swing_low + 0.65 * diff,
            "0.786": swing_low + 0.786 * diff,
            "1.0":   swing_high,
        }
    else:
        return {
            "0.0": swing_high,
            "0.236": swing_high - 0.236 * diff,
            "0.382": swing_high - 0.382 * diff,
            "0.5":   swing_high - 0.5 * diff,
            "0.618": swing_high - 0.618 * diff,
            "0.65":  swing_high - 0.65 * diff,
            "0.786": swing_high - 0.786 * diff,
            "1.0":   swing_low,
        }


def detect_displacement(df: pd.DataFrame, lookback: int = 10, threshold: float = 2.0) -> list:
    """Detect displacement candles (large body relative to ATR)."""
    displacements = []
    if df is None or len(df) < lookback or "atr14" not in df.columns:
        return displacements

    for i in range(max(1, len(df) - lookback), len(df)):
        body = abs(float(df["close"].iloc[i]) - float(df["open"].iloc[i]))
        atr = float(df["atr14"].iloc[i])
        if atr > 0 and body > threshold * atr:
            direction = "bull" if df["close"].iloc[i] > df["open"].iloc[i] else "bear"
            displacements.append({
                "index": i,
                "direction": direction,
                "body_atr_ratio": round(body / atr, 2),
                "open": float(df["open"].iloc[i]),
                "close": float(df["close"].iloc[i]),
                "high": float(df["high"].iloc[i]),
                "low": float(df["low"].iloc[i]),
            })
    return displacements


def detect_fvg_candles(df: pd.DataFrame, min_size: float = 0.0) -> list:
    """
    Detect Fair Value Gaps (imbalances between 3 candles).
    Returns list of FVG dicts with zone boundaries.
    """
    fvgs = []
    if df is None or len(df) < 3:
        return fvgs

    for i in range(2, len(df)):
        h0 = float(df["high"].iloc[i - 2])
        l0 = float(df["low"].iloc[i - 2])
        h2 = float(df["high"].iloc[i])
        l2 = float(df["low"].iloc[i])

        # Bullish FVG: candle 3 low > candle 1 high (gap up)
        if l2 > h0 and (l2 - h0) >= min_size:
            fvgs.append({
                "type": "bullish",
                "top": l2,
                "bottom": h0,
                "size": l2 - h0,
                "index": i,
                "filled": False,
            })
        # Bearish FVG: candle 3 high < candle 1 low (gap down)
        elif h2 < l0 and (l0 - h2) >= min_size:
            fvgs.append({
                "type": "bearish",
                "top": l0,
                "bottom": h2,
                "size": l0 - h2,
                "index": i,
                "filled": False,
            })

    return fvgs


def detect_engulfing(df: pd.DataFrame) -> Optional[str]:
    """Detect bullish/bearish engulfing on last 2 candles."""
    if df is None or len(df) < 2:
        return None
    prev_o, prev_c = float(df["open"].iloc[-2]), float(df["close"].iloc[-2])
    curr_o, curr_c = float(df["open"].iloc[-1]), float(df["close"].iloc[-1])

    prev_body = abs(prev_c - prev_o)
    curr_body = abs(curr_c - curr_o)

    if curr_body < prev_body * 0.5:
        return None

    # Bullish engulfing: prev bearish, curr bullish, curr body engulfs prev
    if prev_c < prev_o and curr_c > curr_o and curr_c > prev_o and curr_o < prev_c:
        return "bullish_engulfing"
    # Bearish engulfing
    if prev_c > prev_o and curr_c < curr_o and curr_c < prev_o and curr_o > prev_c:
        return "bearish_engulfing"
    return None


def bb_squeeze_active(df: pd.DataFrame) -> bool:
    """Check if Bollinger Band squeeze is active (low volatility buildup)."""
    if df is None or "bb_width" not in df.columns or len(df) < 20:
        return False
    current_width = float(df["bb_width"].iloc[-1])
    avg_width = float(df["bb_width"].iloc[-20:].mean())
    return current_width < avg_width * 0.6
