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

    # ── SMA 44 (Callisto FX BB+Indicator Strategy) ──
    if len(c) >= 44:
        df["sma44"] = c.rolling(44).mean()
    else:
        df["sma44"] = c

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


# ════════════════════════════════════════════════════════════════
# CALLISTO FX — EXPANDED CANDLESTICK PATTERN RECOGNITION
# ════════════════════════════════════════════════════════════════
def detect_candlestick_patterns(df: pd.DataFrame, lookback: int = 5) -> List[dict]:
    """
    Detect all Callisto FX candlestick patterns:
    Doji, Shooting Star, Hammer, Engulfing, Tweezer Top/Bottom,
    Morning/Evening Star, Double Top/Bottom, Head & Shoulders (simplified).
    Returns list of detected patterns with direction bias.
    """
    patterns = []
    if df is None or len(df) < max(lookback, 3):
        return patterns

    o = df["open"].astype(float)
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)

    for i in range(max(2, len(df) - lookback), len(df)):
        body = abs(c.iloc[i] - o.iloc[i])
        upper_wick = h.iloc[i] - max(c.iloc[i], o.iloc[i])
        lower_wick = min(c.iloc[i], o.iloc[i]) - l.iloc[i]
        total_range = h.iloc[i] - l.iloc[i]
        if total_range == 0:
            continue

        # ── Doji: body < 10% of range ──
        if body < total_range * 0.10:
            patterns.append({"pattern": "doji", "index": i, "bias": "neutral",
                           "strength": 1})

        # ── Hammer: small body at top, long lower wick >=2x body ──
        if lower_wick >= body * 2 and upper_wick < body * 0.5 and body > 0:
            patterns.append({"pattern": "hammer", "index": i, "bias": "bullish",
                           "strength": 2})

        # ── Shooting Star: small body at bottom, long upper wick >=2x body ──
        if upper_wick >= body * 2 and lower_wick < body * 0.5 and body > 0:
            patterns.append({"pattern": "shooting_star", "index": i, "bias": "bearish",
                           "strength": 2})

        # Multi-candle patterns (need i >= 1)
        if i >= 1:
            prev_body = abs(c.iloc[i-1] - o.iloc[i-1])
            prev_bullish = c.iloc[i-1] > o.iloc[i-1]
            curr_bullish = c.iloc[i] > o.iloc[i]

            # ── Bullish Engulfing ──
            if not prev_bullish and curr_bullish:
                if c.iloc[i] > o.iloc[i-1] and o.iloc[i] < c.iloc[i-1]:
                    patterns.append({"pattern": "bullish_engulfing", "index": i,
                                   "bias": "bullish", "strength": 3})

            # ── Bearish Engulfing ──
            if prev_bullish and not curr_bullish:
                if c.iloc[i] < o.iloc[i-1] and o.iloc[i] > c.iloc[i-1]:
                    patterns.append({"pattern": "bearish_engulfing", "index": i,
                                   "bias": "bearish", "strength": 3})

            # ── Tweezer Top: 2 candles, similar highs, first bull then bear ──
            if prev_bullish and not curr_bullish:
                if abs(h.iloc[i] - h.iloc[i-1]) < total_range * 0.05:
                    patterns.append({"pattern": "tweezer_top", "index": i,
                                   "bias": "bearish", "strength": 2})

            # ── Tweezer Bottom: 2 candles, similar lows, first bear then bull ──
            if not prev_bullish and curr_bullish:
                if abs(l.iloc[i] - l.iloc[i-1]) < total_range * 0.05:
                    patterns.append({"pattern": "tweezer_bottom", "index": i,
                                   "bias": "bullish", "strength": 2})

        # 3-candle patterns (need i >= 2)
        if i >= 2:
            first_bullish = c.iloc[i-2] > o.iloc[i-2]
            mid_body = abs(c.iloc[i-1] - o.iloc[i-1])
            mid_range = h.iloc[i-1] - l.iloc[i-1]

            # ── Morning Star: bearish, small body/doji, bullish ──
            if not first_bullish and mid_body < mid_range * 0.3 and c.iloc[i] > o.iloc[i]:
                if c.iloc[i] > (o.iloc[i-2] + c.iloc[i-2]) / 2:
                    patterns.append({"pattern": "morning_star", "index": i,
                                   "bias": "bullish", "strength": 3})

            # ── Evening Star: bullish, small body/doji, bearish ──
            if first_bullish and mid_body < mid_range * 0.3 and c.iloc[i] < o.iloc[i]:
                if c.iloc[i] < (o.iloc[i-2] + c.iloc[i-2]) / 2:
                    patterns.append({"pattern": "evening_star", "index": i,
                                   "bias": "bearish", "strength": 3})

    return patterns


def detect_breaker_blocks(df: pd.DataFrame, lookback: int = 50) -> List[dict]:
    """
    Detect Breaker Blocks (Callisto FX ICT concept).
    A breaker block is a failed order block — when an OB fails and price
    breaks through it, the OB flips to become a breaker block
    (resistance becomes support or vice versa).

    Logic:
    1. Find order blocks (last opposing candle before impulse move)
    2. Check if price subsequently broke through the OB
    3. The broken OB zone becomes a breaker block for retest entries
    """
    breakers = []
    if df is None or len(df) < 20:
        return breakers

    o = df["open"].astype(float)
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    atr = float(df["atr14"].iloc[-1]) if "atr14" in df.columns else 1.0

    start = max(2, len(df) - lookback)

    for i in range(start, len(df) - 3):
        bar_open = o.iloc[i]
        bar_close = c.iloc[i]
        bar_body = abs(bar_close - bar_open)

        if bar_body < atr * 0.3:
            continue

        # Check for impulse move after this candle
        next_move = abs(c.iloc[i+1] - c.iloc[i])
        if next_move < atr * 0.8:
            continue

        # Bullish OB that later FAILS (breaks below) → Bearish Breaker Block
        if bar_close > bar_open:  # Bullish candle (potential bullish OB)
            ob_bottom = bar_open
            ob_top = bar_close
            # Check if price later broke below this OB
            for j in range(i + 2, min(i + 20, len(df))):
                if c.iloc[j] < ob_bottom:
                    # OB failed — this is now a bearish breaker block
                    # Price retesting this zone from below = sell opportunity
                    breakers.append({
                        "type": "bearish_breaker",
                        "top": ob_top,
                        "bottom": ob_bottom,
                        "created_index": i,
                        "broken_index": j,
                        "direction": "SELL",
                    })
                    break

        # Bearish OB that later FAILS (breaks above) → Bullish Breaker Block
        elif bar_close < bar_open:  # Bearish candle (potential bearish OB)
            ob_bottom = bar_close
            ob_top = bar_open
            # Check if price later broke above this OB
            for j in range(i + 2, min(i + 20, len(df))):
                if c.iloc[j] > ob_top:
                    # OB failed — this is now a bullish breaker block
                    breakers.append({
                        "type": "bullish_breaker",
                        "top": ob_top,
                        "bottom": ob_bottom,
                        "created_index": i,
                        "broken_index": j,
                        "direction": "BUY",
                    })
                    break

    return breakers


def detect_wcr_range(df: pd.DataFrame, min_range_pips: float = 100,
                     min_touches: int = 2) -> Optional[dict]:
    """
    Detect William-Certified Range (Callisto FX WCR Strategy).
    S&R with 2+ touches, minimum 100-150 pips wide on 1H/4H/Daily.
    Returns the current range if detected, else None.
    """
    if df is None or len(df) < 30:
        return None

    pip = 0.1
    highs, lows = find_swing_points(df, left=5, right=5)

    if len(highs) < 2 or len(lows) < 2:
        return None

    # Find the most prominent resistance (cluster of highs)
    high_prices = [h["price"] for h in highs[-8:]]
    low_prices = [l["price"] for l in lows[-8:]]

    # Cluster highs within tolerance
    tolerance = 30 * pip  # 30 pips clustering for gold
    resistance = _find_level_cluster(high_prices, tolerance)
    support = _find_level_cluster(low_prices, tolerance)

    if resistance is None or support is None:
        return None

    range_pips = (resistance["level"] - support["level"]) / pip

    if range_pips < min_range_pips:
        return None

    if resistance["touches"] < min_touches or support["touches"] < min_touches:
        return None

    price = float(df["close"].iloc[-1])

    return {
        "resistance": resistance["level"],
        "support": support["level"],
        "range_pips": round(range_pips, 1),
        "resistance_touches": resistance["touches"],
        "support_touches": support["touches"],
        "price_in_range": support["level"] <= price <= resistance["level"],
        "near_support": abs(price - support["level"]) < tolerance,
        "near_resistance": abs(price - resistance["level"]) < tolerance,
    }


def _find_level_cluster(prices: List[float], tolerance: float) -> Optional[dict]:
    """Find the most-touched price level within a tolerance band."""
    if not prices:
        return None

    best_level = None
    best_count = 0

    for ref in prices:
        count = sum(1 for p in prices if abs(p - ref) <= tolerance)
        if count > best_count:
            best_count = count
            avg_price = np.mean([p for p in prices if abs(p - ref) <= tolerance])
            best_level = {"level": round(avg_price, 2), "touches": count}

    return best_level


def detect_premium_discount(df: pd.DataFrame) -> Optional[dict]:
    """
    Detect Premium/Discount Array (Callisto FX ICT concept).
    Uses Fibonacci 50% equilibrium:
    - Below 50% = Discount zone (look for buys)
    - Above 50% = Premium zone (look for sells)
    Returns zone classification and Fib levels.
    """
    if df is None or len(df) < 30:
        return None

    highs, lows = find_swing_points(df, left=5, right=5)
    if not highs or not lows:
        return None

    # Use recent swing structure
    swing_high = max(h["price"] for h in highs[-5:])
    swing_low = min(l["price"] for l in lows[-5:])
    price = float(df["close"].iloc[-1])
    swing_range = swing_high - swing_low

    if swing_range <= 0:
        return None

    equilibrium = swing_low + swing_range * 0.5
    position_pct = (price - swing_low) / swing_range * 100

    if position_pct <= 30:
        zone = "deep_discount"
        bias = "BUY"
    elif position_pct <= 50:
        zone = "discount"
        bias = "BUY"
    elif position_pct >= 70:
        zone = "deep_premium"
        bias = "SELL"
    elif position_pct >= 50:
        zone = "premium"
        bias = "SELL"
    else:
        zone = "equilibrium"
        bias = "NEUTRAL"

    return {
        "zone": zone,
        "bias": bias,
        "position_pct": round(position_pct, 1),
        "equilibrium": round(equilibrium, 2),
        "swing_high": swing_high,
        "swing_low": swing_low,
        "price": price,
    }
