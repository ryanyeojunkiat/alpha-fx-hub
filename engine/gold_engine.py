"""
Alpha FX Hub — Gold Engine V6 Callisto
========================================
26-module XAUUSD analysis system built on the Callisto FX framework:

CORE FRAMEWORK: T.R.C. (Trend × Reversal × Continuation)
- Multi-timeframe analysis: Daily → 4H → 1H → 15M → 5M
- 2/3 rule: need 2 out of 3 higher TFs aligned
- CHoCH on 5M with BODY close (wick-only = invalid)
- Retest of CHoCH level for entry
- 3 layers of defense minimum

ORIGINAL MODULES (1-20): Carried forward from V5
MODULE 21: TRC Score (Trend × Reversal × Continuation)
MODULE 22: WCR Range Detection (William-Certified Range)
MODULE 23: Breaker Block + SMA44 Strategy
MODULE 24: Premium/Discount Array (ICT Fib 50% equilibrium)
MODULE 25: Expanded Candlestick Patterns (Callisto FX full set)
MODULE 26: Callisto Risk Enforcer (max 2 losses/day, session lock)

Callisto FX — 90.7% tracked win rate framework.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
import logging

from .indicators import (
    add_indicators, find_swing_points, fibonacci_levels,
    detect_displacement, detect_fvg_candles, detect_engulfing,
    bb_squeeze_active, detect_candlestick_patterns,
    detect_breaker_blocks, detect_wcr_range, detect_premium_discount,
)
from .institutional import score_cot_dxy, score_news_filter, score_volume, COTAnalyzer

logger = logging.getLogger("alpha_fx_hub.gold_engine")

# Shared COT analyzer (singleton, caches data)
_cot = COTAnalyzer()


# ════════════════════════════════════════════════════════════════
# MODULE 1: Multi-Timeframe Trend Alignment
# ════════════════════════════════════════════════════════════════
def _trend_from_emas(df: pd.DataFrame) -> str:
    """Returns 'bull' | 'bear' | 'bull_weak' | 'bear_weak' | 'neutral'."""
    if df is None or len(df) < 50:
        return "neutral"
    r = df.iloc[-1]
    e20 = float(r.get("ema20", r["close"]))
    e50 = float(r.get("ema50", r["close"]))
    e200 = float(r.get("ema200", r["close"]))
    close = float(r["close"])

    if close > e50 and e50 > e200 and e20 > e50:
        return "bull"
    if close < e50 and e50 < e200 and e20 < e50:
        return "bear"
    if close > e200:
        return "bull_weak"
    if close < e200:
        return "bear_weak"
    return "neutral"


def _mtf_alignment(df_entry, df_h1, df_h4, direction: str,
                    df_daily=None) -> dict:
    """
    Score multi-timeframe alignment — Callisto FX 2/3 Rule.

    Callisto TRC Framework:
    - Analyze Daily → 4H → 1H → 15M (top-down)
    - Need 2 out of 3 higher TFs aligned for A+ bias
    - 3+ TF alignment = maximum conviction entry
    """
    daily_trend = _trend_from_emas(df_daily) if df_daily is not None else "neutral"
    h4_trend = _trend_from_emas(df_h4)
    h1_trend = _trend_from_emas(df_h1) if df_h1 is not None else "neutral"

    entry_trend = "neutral"
    if df_entry is not None and len(df_entry) > 0:
        r = df_entry.iloc[-1]
        e9 = float(r.get("ema9", r["close"]))
        e21 = float(r.get("ema21", r["close"]))
        entry_trend = "bull" if e9 > e21 else "bear" if e9 < e21 else "neutral"

    aligned = 0
    opposed = 0
    target = "bull" if direction == "BUY" else "bear"

    # Check all 4 timeframes (Callisto top-down: Daily → 4H → 1H → Entry)
    tf_results = {}
    for name, trend in [("daily", daily_trend), ("h4", h4_trend),
                        ("h1", h1_trend), ("entry", entry_trend)]:
        if target in trend:
            aligned += 1
            tf_results[name] = "aligned"
        elif ("bull" in trend and target == "bear") or ("bear" in trend and target == "bull"):
            opposed += 1
            tf_results[name] = "opposed"
        else:
            tf_results[name] = "neutral"

    h4_aligned = target in h4_trend

    # Callisto 2/3 Rule: check higher TFs (Daily, 4H, 1H)
    htf_aligned = sum(1 for k in ["daily", "h4", "h1"] if tf_results.get(k) == "aligned")
    htf_opposed = sum(1 for k in ["daily", "h4", "h1"] if tf_results.get(k) == "opposed")

    # Scoring based on Callisto framework
    if aligned >= 4:
        score = 18  # All 4 TFs aligned — maximum conviction
    elif htf_aligned >= 3:
        score = 15  # 3 HTFs aligned — A+ bias (Callisto rule)
    elif htf_aligned >= 2:
        score = 10  # 2/3 HTFs aligned — valid entry (Callisto 2/3 rule)
    elif htf_aligned == 1 and htf_opposed == 0:
        score = 3   # Only 1 HTF aligned, no opposition
    elif htf_opposed >= 2:
        score = -12  # 2+ HTFs opposed — DO NOT TRADE (Callisto rule)
    else:
        score = 0

    return {
        "score": score,
        "daily_trend": daily_trend,
        "h4_trend": h4_trend,
        "h1_trend": h1_trend,
        "entry_trend": entry_trend,
        "h4_aligned": h4_aligned,
        "aligned": aligned,
        "opposed": opposed,
        "htf_aligned": htf_aligned,
        "tf_results": tf_results,
        "callisto_2of3": htf_aligned >= 2,
    }


# ════════════════════════════════════════════════════════════════
# MODULE 2: Supply & Demand Zones (with Freshness Tracking)
# ════════════════════════════════════════════════════════════════
def _detect_sd_zones(df: pd.DataFrame, pivot_len: int = 4) -> list:
    """Detect supply/demand zones with freshness tracking."""
    zones = []
    if df is None or len(df) < pivot_len * 3:
        return zones

    highs, lows = find_swing_points(df, left=pivot_len, right=pivot_len)

    # Demand zones (from swing lows)
    for low in lows[-8:]:
        idx = low["index"]
        if idx >= len(df):
            continue
        zone_low = low["price"]
        zone_high = zone_low + float(df["atr14"].iloc[min(idx, len(df)-1)]) * 0.5
        visits = sum(1 for j in range(idx + 1, len(df))
                     if float(df["low"].iloc[j]) <= zone_high and float(df["low"].iloc[j]) >= zone_low * 0.999)

        # Departure strength
        if idx + 1 < len(df):
            max_departure = max(float(df["high"].iloc[j]) - zone_high
                              for j in range(idx + 1, min(idx + 20, len(df))))
        else:
            max_departure = 0

        strength = min(100, max(0, int((max_departure / max(float(df["atr14"].iloc[-1]), 0.01)) * 33 + 50)))

        zones.append({
            "type": "demand",
            "top": zone_high,
            "bottom": zone_low,
            "strength": strength,
            "visits": visits,
            "fresh": visits == 0,
            "index": idx,
        })

    # Supply zones (from swing highs)
    for high in highs[-8:]:
        idx = high["index"]
        if idx >= len(df):
            continue
        zone_high = high["price"]
        zone_low = zone_high - float(df["atr14"].iloc[min(idx, len(df)-1)]) * 0.5
        visits = sum(1 for j in range(idx + 1, len(df))
                     if float(df["high"].iloc[j]) >= zone_low and float(df["high"].iloc[j]) <= zone_high * 1.001)

        if idx + 1 < len(df):
            max_departure = max(zone_low - float(df["low"].iloc[j])
                              for j in range(idx + 1, min(idx + 20, len(df))))
        else:
            max_departure = 0

        strength = min(100, max(0, int((max_departure / max(float(df["atr14"].iloc[-1]), 0.01)) * 33 + 50)))

        zones.append({
            "type": "supply",
            "top": zone_high,
            "bottom": zone_low,
            "strength": strength,
            "visits": visits,
            "fresh": visits == 0,
            "index": idx,
        })

    return zones


def _score_sd_zone(zones: list, price: float, direction: str) -> dict:
    """Score proximity to S/D zone."""
    best_score = 0
    best_zone = None
    pip = 0.1

    for z in zones:
        near_demand = (z["type"] == "demand" and direction == "BUY"
                      and z["bottom"] - 30 * pip <= price <= z["top"] + 10 * pip)
        near_supply = (z["type"] == "supply" and direction == "SELL"
                      and z["bottom"] - 10 * pip <= price <= z["top"] + 30 * pip)

        if near_demand or near_supply:
            if z["fresh"] and z["strength"] >= 60:
                score = 12
            elif z["visits"] <= 1:
                score = 6
            elif z["visits"] <= 2:
                score = 2
            else:
                score = 0

            if score > best_score:
                best_score = score
                best_zone = z

    return {"score": best_score, "zone": best_zone}


# ════════════════════════════════════════════════════════════════
# MODULE 3: Fair Value Gap Detection
# ════════════════════════════════════════════════════════════════
def _score_fvg(df: pd.DataFrame, price: float, direction: str) -> dict:
    """Score FVG proximity and alignment."""
    fvgs = detect_fvg_candles(df, min_size=0.5)
    if not fvgs:
        return {"score": 0, "fvg": None}

    recent_fvgs = [f for f in fvgs if f["index"] >= len(df) - 20]
    best_score = 0
    best_fvg = None

    for fvg in recent_fvgs:
        if fvg["type"] == "bullish" and direction == "BUY":
            if fvg["bottom"] <= price <= fvg["top"]:
                best_score = 8
                best_fvg = fvg
        elif fvg["type"] == "bearish" and direction == "SELL":
            if fvg["bottom"] <= price <= fvg["top"]:
                best_score = 8
                best_fvg = fvg

    return {"score": best_score, "fvg": best_fvg}


# ════════════════════════════════════════════════════════════════
# MODULE 4: Change of Character (CHoCH) Detection
# ════════════════════════════════════════════════════════════════
def _detect_choch(df: pd.DataFrame, lookback: int = 30,
                   require_body_close: bool = False) -> dict:
    """
    Detect Change of Character on given timeframe.

    Callisto FX Rules:
    - Bullish CHoCH: series of LL then breaks a LH (higher high after downtrend)
    - Bearish CHoCH: series of HH then breaks a HL (lower low after uptrend)
    - On 5M: BODY close required (wick-only break = INVALID)
    - require_body_close=True enforces the Callisto body-close rule
    """
    result = {"detected": False, "direction": None, "strength": 0, "price": 0,
              "body_confirmed": False}
    if df is None or len(df) < lookback:
        return result

    highs, lows = find_swing_points(df, left=3, right=3)
    if len(highs) < 3 or len(lows) < 3:
        return result

    recent_highs = [h["price"] for h in highs[-5:]]
    recent_lows = [l["price"] for l in lows[-5:]]
    last_close = float(df["close"].iloc[-1])

    # Bearish CHoCH: was making HH/HL, now broke below last HL
    if len(recent_highs) >= 3 and len(recent_lows) >= 3:
        was_uptrend = recent_highs[-3] < recent_highs[-2]
        broke_low = recent_lows[-1] < recent_lows[-2]

        if was_uptrend and broke_low:
            # Callisto body-close check: the CLOSE must be below the level
            body_confirmed = last_close < recent_lows[-2]
            if require_body_close and not body_confirmed:
                # Wick-only break — INVALID per Callisto FX
                return result

            result = {
                "detected": True,
                "direction": "bearish",
                "strength": abs(recent_lows[-1] - recent_lows[-2]),
                "price": recent_lows[-1],
                "prev_structure": "uptrend",
                "body_confirmed": body_confirmed,
                "choch_level": recent_lows[-2],  # Level to watch for retest
            }
            return result

    # Bullish CHoCH: was making LL/LH, now broke above last LH
    if len(recent_highs) >= 3 and len(recent_lows) >= 3:
        was_downtrend = recent_lows[-3] > recent_lows[-2]
        broke_high = recent_highs[-1] > recent_highs[-2]

        if was_downtrend and broke_high:
            body_confirmed = last_close > recent_highs[-2]
            if require_body_close and not body_confirmed:
                return result

            result = {
                "detected": True,
                "direction": "bullish",
                "strength": abs(recent_highs[-1] - recent_highs[-2]),
                "price": recent_highs[-1],
                "prev_structure": "downtrend",
                "body_confirmed": body_confirmed,
                "choch_level": recent_highs[-2],
            }

    return result


def _score_choch(df: pd.DataFrame, direction: str) -> dict:
    """Score CHoCH alignment with trade direction."""
    choch = _detect_choch(df)
    if not choch["detected"]:
        return {"score": 0, "choch": choch}

    aligned = ((choch["direction"] == "bullish" and direction == "BUY") or
               (choch["direction"] == "bearish" and direction == "SELL"))

    score = 10 if aligned else -8
    return {"score": score, "choch": choch}


# ════════════════════════════════════════════════════════════════
# MODULE 5: ICT Killzone Timing
# ════════════════════════════════════════════════════════════════
def _score_killzone(utc_hour: int) -> dict:
    """Score based on ICT killzone timing."""
    from config import KILLZONES_UTC

    for name, (start, end) in KILLZONES_UTC.items():
        if start <= end:
            in_zone = start <= utc_hour < end
        else:
            in_zone = utc_hour >= start or utc_hour < end

        if in_zone:
            if name in ("London_Open", "NY_Open", "LN_Overlap"):
                return {"score": 8, "killzone": name}
            elif name == "London_Close":
                return {"score": 5, "killzone": name}
            elif name == "Asian_KZ":
                return {"score": 3, "killzone": name}

    return {"score": -3, "killzone": "Off-hours"}


# ════════════════════════════════════════════════════════════════
# MODULE 6: RSI Divergence (Regular + Hidden)
# ════════════════════════════════════════════════════════════════
def _score_rsi_divergence(df: pd.DataFrame, direction: str) -> dict:
    """Detect regular and hidden RSI divergence."""
    result = {"score": 0, "type": None}
    if df is None or len(df) < 30 or "rsi14" not in df.columns:
        return result

    _, lows = find_swing_points(df, left=3, right=3)
    highs, _ = find_swing_points(df, left=3, right=3)

    if direction == "BUY" and len(lows) >= 2:
        last_low = lows[-1]
        prev_low = lows[-2]
        # Regular bullish: price lower low, RSI higher low
        if (last_low["price"] < prev_low["price"] and
            float(df["rsi14"].iloc[last_low["index"]]) > float(df["rsi14"].iloc[prev_low["index"]])):
            result = {"score": 8, "type": "regular_bullish_divergence"}
        # Hidden bullish: price higher low, RSI lower low (trend continuation)
        elif (last_low["price"] > prev_low["price"] and
              float(df["rsi14"].iloc[last_low["index"]]) < float(df["rsi14"].iloc[prev_low["index"]])):
            result = {"score": 6, "type": "hidden_bullish_divergence"}

    elif direction == "SELL" and len(highs) >= 2:
        last_high = highs[-1]
        prev_high = highs[-2]
        # Regular bearish: price higher high, RSI lower high
        if (last_high["price"] > prev_high["price"] and
            float(df["rsi14"].iloc[last_high["index"]]) < float(df["rsi14"].iloc[prev_high["index"]])):
            result = {"score": 8, "type": "regular_bearish_divergence"}
        # Hidden bearish
        elif (last_high["price"] < prev_high["price"] and
              float(df["rsi14"].iloc[last_high["index"]]) > float(df["rsi14"].iloc[prev_high["index"]])):
            result = {"score": 6, "type": "hidden_bearish_divergence"}

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 7: Liquidity Sweep
# ════════════════════════════════════════════════════════════════
def _score_liquidity_sweep(df: pd.DataFrame, direction: str) -> dict:
    """Detect liquidity sweep (stop hunt then reversal)."""
    result = {"score": 0, "detected": False}
    if df is None or len(df) < 20:
        return result

    highs, lows = find_swing_points(df, left=5, right=2)

    if direction == "BUY" and len(lows) >= 2:
        prev_low = lows[-2]["price"]
        last_bar_low = float(df["low"].iloc[-1])
        last_bar_close = float(df["close"].iloc[-1])
        # Price swept below previous low then closed back above
        if last_bar_low < prev_low and last_bar_close > prev_low:
            result = {"score": 10, "detected": True, "type": "bullish_sweep"}

    elif direction == "SELL" and len(highs) >= 2:
        prev_high = highs[-2]["price"]
        last_bar_high = float(df["high"].iloc[-1])
        last_bar_close = float(df["close"].iloc[-1])
        if last_bar_high > prev_high and last_bar_close < prev_high:
            result = {"score": 10, "detected": True, "type": "bearish_sweep"}

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 8: Asian Range Breakout
# ════════════════════════════════════════════════════════════════
def _score_asian_breakout(df: pd.DataFrame, direction: str) -> dict:
    """Check if price broke out of Asian session range."""
    result = {"score": 0, "asian_high": 0, "asian_low": 0}
    if df is None or len(df) < 30:
        return result

    # Filter Asian session bars (22:00-08:00 UTC)
    if hasattr(df.index, 'hour'):
        asian_mask = (df.index.hour >= 22) | (df.index.hour < 8)
        asian_bars = df[asian_mask].tail(20)
        if len(asian_bars) > 0:
            asian_high = float(asian_bars["high"].max())
            asian_low = float(asian_bars["low"].min())
            price = float(df["close"].iloc[-1])

            result["asian_high"] = asian_high
            result["asian_low"] = asian_low

            if direction == "BUY" and price > asian_high:
                result["score"] = 8
            elif direction == "SELL" and price < asian_low:
                result["score"] = 8
            elif asian_low <= price <= asian_high:
                result["score"] = -3

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 9: Momentum Filter
# ════════════════════════════════════════════════════════════════
def _score_momentum(df: pd.DataFrame, direction: str) -> dict:
    """Score momentum alignment (5-bar and 20-bar)."""
    if df is None or len(df) < 20:
        return {"score": 0}

    c = df["close"].astype(float)
    mom5 = float(c.iloc[-1] - c.iloc[-5])
    mom20 = float(c.iloc[-1] - c.iloc[-20])

    score = 0
    if direction == "BUY":
        if mom5 > 0:
            score += 7
        if mom20 > 0:
            score += 8
    else:
        if mom5 < 0:
            score += 7
        if mom20 < 0:
            score += 8

    return {"score": min(score, 15), "mom5": mom5, "mom20": mom20}


# ════════════════════════════════════════════════════════════════
# MODULE 10: Overextension Guard
# ════════════════════════════════════════════════════════════════
def _check_overextension(df: pd.DataFrame) -> dict:
    """Flag overextended moves (4x+ ATR in 20 bars)."""
    if df is None or len(df) < 20 or "atr14" not in df.columns:
        return {"overextended": False, "score": 0}

    move = abs(float(df["close"].iloc[-1]) - float(df["close"].iloc[-20]))
    atr = float(df["atr14"].iloc[-1])

    if atr > 0 and move > 4.0 * atr:
        return {"overextended": True, "score": -10, "move_atr_ratio": move / atr}
    return {"overextended": False, "score": 0, "move_atr_ratio": move / max(atr, 0.01)}


# ════════════════════════════════════════════════════════════════
# MODULE 11: Market Structure (HH/HL/LH/LL)
# ════════════════════════════════════════════════════════════════
def _score_market_structure(df: pd.DataFrame, direction: str) -> dict:
    """Score market structure pattern."""
    if df is None or len(df) < 30:
        return {"score": 0, "structure": "unknown"}

    highs, lows = find_swing_points(df, left=3, right=3)
    if len(highs) < 2 or len(lows) < 2:
        return {"score": 0, "structure": "unknown"}

    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"] > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"] < lows[-2]["price"]

    if hh and hl:
        structure = "uptrend"
    elif lh and ll:
        structure = "downtrend"
    else:
        structure = "ranging"

    if (structure == "uptrend" and direction == "BUY") or (structure == "downtrend" and direction == "SELL"):
        score = 5
    elif structure == "ranging":
        score = 0
    else:
        score = -5

    return {"score": score, "structure": structure}


# ════════════════════════════════════════════════════════════════
# MODULE 12: Break of Structure (BOS)
# ════════════════════════════════════════════════════════════════
def _score_bos(df: pd.DataFrame, direction: str) -> dict:
    """Detect Break of Structure confirmation."""
    if df is None or len(df) < 20:
        return {"score": 0, "bos": False}

    highs, lows = find_swing_points(df, left=3, right=2)

    if direction == "BUY" and len(highs) >= 2:
        if highs[-1]["price"] > highs[-2]["price"]:
            return {"score": 8, "bos": True, "type": "bullish_bos"}

    if direction == "SELL" and len(lows) >= 2:
        if lows[-1]["price"] < lows[-2]["price"]:
            return {"score": 8, "bos": True, "type": "bearish_bos"}

    return {"score": 0, "bos": False}


# ════════════════════════════════════════════════════════════════
# MODULE 13: Order Blocks (BOS-validated)
# ════════════════════════════════════════════════════════════════
def _score_order_blocks(df: pd.DataFrame, price: float, direction: str, bos_confirmed: bool) -> dict:
    """Detect and score order blocks near current price."""
    if df is None or len(df) < 20:
        return {"score": 0, "ob": None}

    atr = float(df["atr14"].iloc[-1]) if "atr14" in df.columns else 1.0
    best_score = 0
    best_ob = None

    for i in range(2, min(30, len(df))):
        idx = len(df) - i
        if idx < 1:
            break

        bar_open = float(df["open"].iloc[idx])
        bar_close = float(df["close"].iloc[idx])
        bar_body = abs(bar_close - bar_open)

        # Need impulsive move after the OB candle
        if idx + 1 < len(df):
            next_move = abs(float(df["close"].iloc[idx + 1]) - float(df["close"].iloc[idx]))
        else:
            continue

        if next_move < atr * 0.8:
            continue

        # Bullish OB: bearish candle before bullish impulse
        if direction == "BUY" and bar_close < bar_open:
            ob_top = bar_open
            ob_bottom = bar_close
            if ob_bottom <= price <= ob_top + atr * 0.3:
                score = 12 if bos_confirmed else 6
                if score > best_score:
                    best_score = score
                    best_ob = {"type": "bullish_ob", "top": ob_top, "bottom": ob_bottom, "index": idx}

        # Bearish OB: bullish candle before bearish impulse
        elif direction == "SELL" and bar_close > bar_open:
            ob_top = bar_close
            ob_bottom = bar_open
            if ob_bottom - atr * 0.3 <= price <= ob_top:
                score = 12 if bos_confirmed else 6
                if score > best_score:
                    best_score = score
                    best_ob = {"type": "bearish_ob", "top": ob_top, "bottom": ob_bottom, "index": idx}

    return {"score": best_score, "ob": best_ob}


# ════════════════════════════════════════════════════════════════
# MODULE 14: Fibonacci + Golden Pocket + OTE
# ════════════════════════════════════════════════════════════════
def _score_fibonacci(df: pd.DataFrame, price: float, direction: str,
                    has_ob: bool = False, has_fvg: bool = False) -> dict:
    """Score Fibonacci confluence including Golden Pocket and OTE."""
    result = {"score": 0, "level": None, "ote": False, "golden_pocket": False}
    if df is None or len(df) < 30:
        return result

    highs, lows = find_swing_points(df, left=5, right=5)
    if not highs or not lows:
        return result

    swing_high = max(h["price"] for h in highs[-3:])
    swing_low = min(l["price"] for l in lows[-3:])
    fib_dir = "bull" if direction == "BUY" else "bear"
    fibs = fibonacci_levels(swing_high, swing_low, fib_dir)

    pip = 0.1
    tolerance = 20 * pip  # 20 pips tolerance for gold

    # Check Golden Pocket (61.8% - 65%)
    gp_low = fibs["0.618"]
    gp_high = fibs["0.65"]
    if min(gp_low, gp_high) - tolerance <= price <= max(gp_low, gp_high) + tolerance:
        result["golden_pocket"] = True
        result["score"] = 10
        result["level"] = "golden_pocket"

    # Check OTE (62-79% fib + OB or FVG)
    ote_low = fibs["0.618"]
    ote_high = fibs["0.786"]
    if min(ote_low, ote_high) - tolerance <= price <= max(ote_low, ote_high) + tolerance:
        if has_ob or has_fvg:
            result["ote"] = True
            result["score"] = 15
            result["level"] = "ote"

    # Standard fib levels
    if result["score"] == 0:
        for level_name, level_price in fibs.items():
            if abs(price - level_price) <= tolerance:
                result["score"] = 6
                result["level"] = f"fib_{level_name}"
                break

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 15: Displacement Candles
# ════════════════════════════════════════════════════════════════
def _score_displacement(df: pd.DataFrame, direction: str) -> dict:
    """Score recent displacement candles supporting direction."""
    displacements = detect_displacement(df, lookback=10, threshold=1.8)
    if not displacements:
        return {"score": 0}

    for d in reversed(displacements):
        if (d["direction"] == "bull" and direction == "BUY") or \
           (d["direction"] == "bear" and direction == "SELL"):
            return {"score": 7, "displacement": d}

    return {"score": 0}


# ════════════════════════════════════════════════════════════════
# MODULE 16: BB Squeeze + RSI Combo
# ════════════════════════════════════════════════════════════════
def _score_bb_squeeze(df: pd.DataFrame, direction: str) -> dict:
    """Score Bollinger Band squeeze with RSI extreme."""
    if df is None or "rsi14" not in df.columns:
        return {"score": 0}

    squeeze = bb_squeeze_active(df)
    rsi = float(df["rsi14"].iloc[-1])

    if squeeze:
        if (direction == "BUY" and rsi < 35) or (direction == "SELL" and rsi > 65):
            return {"score": 7, "squeeze": True, "rsi": rsi}

    return {"score": 0, "squeeze": squeeze, "rsi": rsi}


# ════════════════════════════════════════════════════════════════
# MODULE 17: Round Number / Psychological Levels
# ════════════════════════════════════════════════════════════════
def _score_round_numbers(price: float) -> dict:
    """Score proximity to psychological levels for gold."""
    pip = 0.1
    score = 0
    level = None

    # Ultra-major: $100 levels (2000, 2100, 2200, 3000, 3100...)
    if abs(price % 100) < 30 * pip or abs(price % 100 - 100) < 30 * pip:
        score = 5
        level = f"${int(round(price / 100) * 100)}"
    # Major: $50 levels
    elif abs(price % 50) < 20 * pip or abs(price % 50 - 50) < 20 * pip:
        score = 4
        level = f"${int(round(price / 50) * 50)}"
    # Minor: $10 levels
    elif abs(price % 10) < 10 * pip or abs(price % 10 - 10) < 10 * pip:
        score = 3
        level = f"${int(round(price / 10) * 10)}"

    return {"score": score, "level": level}


# ════════════════════════════════════════════════════════════════
# MODULE 21: TRC SCORE (Trend × Reversal × Continuation)
# Callisto FX core framework — 90.7% tracked win rate
# ════════════════════════════════════════════════════════════════
def _score_trc(df_5m: pd.DataFrame, df_m15: pd.DataFrame, df_h1: pd.DataFrame,
               df_h4: pd.DataFrame, direction: str, df_daily: pd.DataFrame = None) -> dict:
    """
    Score the T.R.C. (Trend × Reversal × Continuation) framework.

    Step 1 (TREND): MTF analysis with 2/3 rule across 4H/1H/15M
    Step 2 (REVERSAL): CHoCH on 5M with BODY close required
    Step 3 (CONTINUATION): Retest of CHoCH level for entry

    Score range: -10 to +20 (highest weight module — this IS the framework)
    """
    result = {"score": 0, "step1_trend": False, "step2_choch": False,
              "step3_retest": False, "entry_type": None, "notes": []}

    target = "bull" if direction == "BUY" else "bear"

    # ── STEP 1: Trend (2/3 rule on higher TFs) ──
    tf_aligned = 0
    for df in [df_h4, df_h1, df_m15]:
        if df is not None:
            trend = _trend_from_emas(df)
            if target in trend:
                tf_aligned += 1

    if tf_aligned >= 2:
        result["step1_trend"] = True
        result["score"] += 5
        result["notes"].append(f"TRC Step 1 ✓: {tf_aligned}/3 TFs aligned ({target})")
    else:
        result["notes"].append(f"TRC Step 1 ✗: Only {tf_aligned}/3 TFs aligned")
        return result  # Can't proceed without trend

    # ── STEP 2: Reversal (CHoCH on 5M with body close) ──
    if df_5m is not None and len(df_5m) >= 20:
        choch_5m = _detect_choch(df_5m, lookback=30, require_body_close=True)
        if choch_5m["detected"]:
            choch_aligned = ((choch_5m["direction"] == "bullish" and direction == "BUY") or
                           (choch_5m["direction"] == "bearish" and direction == "SELL"))
            if choch_aligned:
                result["step2_choch"] = True
                result["score"] += 8
                result["notes"].append(
                    f"TRC Step 2 ✓: {choch_5m['direction']} CHoCH on 5M "
                    f"(body confirmed={choch_5m['body_confirmed']})")

                # ── STEP 3: Retest of CHoCH level ──
                choch_level = choch_5m.get("choch_level", 0)
                if choch_level > 0:
                    price = float(df_5m["close"].iloc[-1])
                    pip = 0.1
                    tolerance = 15 * pip  # 15 pip tolerance for gold

                    if direction == "BUY" and abs(price - choch_level) <= tolerance:
                        result["step3_retest"] = True
                        result["score"] += 7
                        result["entry_type"] = "pro_trend_choch_retest"
                        result["notes"].append(
                            f"TRC Step 3 ✓: Price retesting CHoCH level ${choch_level:.2f}")
                    elif direction == "SELL" and abs(price - choch_level) <= tolerance:
                        result["step3_retest"] = True
                        result["score"] += 7
                        result["entry_type"] = "pro_trend_choch_retest"
                        result["notes"].append(
                            f"TRC Step 3 ✓: Price retesting CHoCH level ${choch_level:.2f}")
                    else:
                        result["notes"].append(
                            f"TRC Step 3: Waiting for retest of ${choch_level:.2f} "
                            f"(current ${price:.2f})")
            else:
                result["notes"].append("TRC Step 2 ✗: CHoCH opposes trade direction")
        else:
            result["notes"].append("TRC Step 2: No 5M CHoCH detected (waiting)")
    else:
        # Fallback to 15M CHoCH if no 5M data
        choch_15m = _detect_choch(df_m15, lookback=30, require_body_close=True)
        if choch_15m["detected"]:
            choch_aligned = ((choch_15m["direction"] == "bullish" and direction == "BUY") or
                           (choch_15m["direction"] == "bearish" and direction == "SELL"))
            if choch_aligned:
                result["step2_choch"] = True
                result["score"] += 6  # Slightly less weight for 15M
                result["notes"].append(f"TRC Step 2 ✓ (15M fallback): {choch_15m['direction']} CHoCH")

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 22: WCR RANGE DETECTION (William-Certified Range)
# ════════════════════════════════════════════════════════════════
def _score_wcr_range(df_h1: pd.DataFrame, df_h4: pd.DataFrame,
                     direction: str) -> dict:
    """
    Score William-Certified Range strategy.

    Rules:
    - S&R with 2+ touches
    - Range on 1H/4H/Daily, minimum 100-150 pips wide
    - Buy at support, sell at resistance
    - Swing trade focus

    Score range: -5 to +12
    """
    result = {"score": 0, "range": None, "notes": []}

    # Try H4 range first (higher TF = stronger range)
    wcr = detect_wcr_range(df_h4, min_range_pips=100, min_touches=2)
    source_tf = "4H"

    if wcr is None:
        wcr = detect_wcr_range(df_h1, min_range_pips=100, min_touches=2)
        source_tf = "1H"

    if wcr is None:
        return result

    result["range"] = wcr

    if direction == "BUY" and wcr["near_support"]:
        result["score"] = 12
        result["notes"].append(
            f"WCR BUY at support ${wcr['support']:.2f} "
            f"({wcr['support_touches']} touches, {source_tf} range, "
            f"{wcr['range_pips']:.0f} pips wide)")
    elif direction == "SELL" and wcr["near_resistance"]:
        result["score"] = 12
        result["notes"].append(
            f"WCR SELL at resistance ${wcr['resistance']:.2f} "
            f"({wcr['resistance_touches']} touches, {source_tf} range, "
            f"{wcr['range_pips']:.0f} pips wide)")
    elif wcr["price_in_range"]:
        result["score"] = 0
        result["notes"].append(
            f"WCR range detected ({source_tf}: ${wcr['support']:.2f}-${wcr['resistance']:.2f}) "
            f"but price is mid-range — wait for edges")
    else:
        # Price outside range — potential breakout
        result["score"] = -3
        result["notes"].append(
            f"Price outside WCR range — breakout or invalidated range")

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 23: BREAKER BLOCK + SMA44 STRATEGY
# Callisto FX BB+Indicator framework
# ════════════════════════════════════════════════════════════════
def _score_breaker_block(df: pd.DataFrame, price: float, direction: str) -> dict:
    """
    Score Breaker Block + SMA44 strategy (Callisto FX).

    Rules:
    - Breaker Block = failed order block that flipped
    - BUY: break lower high + price above SMA44 + breaker block retest
    - SELL: break higher low + price below SMA44 + breaker block retest
    - Strict 1:2 R:R
    - "X" sign during retest = invalidation

    Score range: -5 to +12
    """
    result = {"score": 0, "breaker": None, "sma44_aligned": False, "notes": []}

    if df is None or len(df) < 44:
        return result

    breakers = detect_breaker_blocks(df, lookback=50)
    sma44 = float(df["sma44"].iloc[-1]) if "sma44" in df.columns else None

    if sma44 is None:
        return result

    # SMA44 alignment check
    sma44_bullish = price > sma44
    sma44_bearish = price < sma44
    result["sma44_aligned"] = (
        (direction == "BUY" and sma44_bullish) or
        (direction == "SELL" and sma44_bearish)
    )

    if not result["sma44_aligned"]:
        result["score"] = -3
        result["notes"].append(
            f"BB Strategy: Price {'above' if sma44_bullish else 'below'} SMA44 "
            f"— conflicts with {direction}")
        return result

    # Find relevant breaker block near price
    pip = 0.1
    atr = float(df["atr14"].iloc[-1]) if "atr14" in df.columns else 1.0
    tolerance = atr * 0.5

    for bb in reversed(breakers):
        if bb["direction"] != direction:
            continue

        # Check if price is near/at the breaker block zone for retest
        near_bb = (bb["bottom"] - tolerance <= price <= bb["top"] + tolerance)

        if near_bb:
            result["score"] = 10
            result["breaker"] = bb
            result["notes"].append(
                f"BB+SMA44 CONFIRMED: {bb['type']} retest at "
                f"${bb['bottom']:.2f}-${bb['top']:.2f}, "
                f"price {'above' if sma44_bullish else 'below'} SMA44 "
                f"(${sma44:.2f})")

            # Extra points if SMA44 and breaker align tightly
            if abs(sma44 - (bb["top"] + bb["bottom"]) / 2) < tolerance:
                result["score"] += 2
                result["notes"].append("BB+SMA44 confluence — high probability zone")

            return result

    # SMA44 aligned but no breaker block nearby
    if result["sma44_aligned"]:
        result["score"] = 2
        result["notes"].append(
            f"SMA44 aligned ({direction}) but no breaker block at current price")

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 24: PREMIUM/DISCOUNT ARRAY
# Callisto FX ICT concept
# ════════════════════════════════════════════════════════════════
def _score_premium_discount(df_h4: pd.DataFrame, direction: str) -> dict:
    """
    Score Premium/Discount Array (ICT concept from Callisto FX).

    Below Fib 50% = Discount zone → look for buys
    Above Fib 50% = Premium zone → look for sells

    Score range: -8 to +10
    """
    result = {"score": 0, "zone": None, "notes": []}

    pd_data = detect_premium_discount(df_h4)
    if pd_data is None:
        return result

    result["zone"] = pd_data

    zone = pd_data["zone"]
    bias = pd_data["bias"]
    pct = pd_data["position_pct"]

    if bias == direction:
        if "deep" in zone:
            result["score"] = 10
            result["notes"].append(
                f"DEEP {zone.upper()}: Price at {pct:.0f}% of swing range — "
                f"institutional {direction} zone")
        else:
            result["score"] = 6
            result["notes"].append(
                f"{zone.upper()}: Price at {pct:.0f}% — favorable for {direction}")
    elif bias != "NEUTRAL" and bias != direction:
        result["score"] = -8
        result["notes"].append(
            f"WARNING: Price in {zone.upper()} ({pct:.0f}%) — "
            f"unfavorable for {direction} (smart money sells in premium, buys in discount)")
    else:
        result["notes"].append(
            f"Price near equilibrium ({pct:.0f}%) — no premium/discount edge")

    return result


# ════════════════════════════════════════════════════════════════
# MODULE 25: EXPANDED CANDLESTICK PATTERNS
# Full Callisto FX pattern set
# ════════════════════════════════════════════════════════════════
def _score_candlestick_patterns(df: pd.DataFrame, direction: str) -> dict:
    """
    Score expanded candlestick patterns from Callisto FX.

    Includes: Doji, Hammer, Shooting Star, Engulfing, Tweezer,
    Morning/Evening Star patterns.

    Score range: -3 to +8
    """
    result = {"score": 0, "patterns": [], "notes": []}

    patterns = detect_candlestick_patterns(df, lookback=5)
    if not patterns:
        return result

    # Only care about the most recent pattern at the last few candles
    recent = [p for p in patterns if p["index"] >= len(df) - 3]
    if not recent:
        return result

    best_score = 0
    for p in recent:
        aligned = ((p["bias"] == "bullish" and direction == "BUY") or
                  (p["bias"] == "bearish" and direction == "SELL"))
        opposed = ((p["bias"] == "bullish" and direction == "SELL") or
                  (p["bias"] == "bearish" and direction == "BUY"))

        if aligned:
            pts = min(8, p["strength"] * 2 + 2)
            if pts > best_score:
                best_score = pts
                result["patterns"].append(p["pattern"])
                result["notes"].append(
                    f"Candlestick: {p['pattern'].replace('_', ' ').title()} "
                    f"confirms {direction}")
        elif opposed:
            pts = -(p["strength"] + 1)
            if pts < -best_score:
                best_score = pts
                result["notes"].append(
                    f"Candlestick warning: {p['pattern'].replace('_', ' ').title()} "
                    f"opposes {direction}")

    result["score"] = max(-3, min(8, best_score))
    return result


# ════════════════════════════════════════════════════════════════
# MODULE 26: CALLISTO RISK ENFORCER
# Session lock + max 2 losses/day + counter-trend rules
# ════════════════════════════════════════════════════════════════
def _score_risk_enforcer(utc_hour: int, direction: str,
                         daily_losses: int = 0,
                         is_counter_trend: bool = False) -> dict:
    """
    Callisto FX Risk Management Enforcer.

    Non-negotiable rules:
    - Max 2 losses per day → no more trading
    - London + NY sessions only (no Asian trading)
    - Counter-trend requires CHoCH retest + BOS (extra confirmation)
    - SL to BE at 10-20 pips profit
    - No FOMO entries
    - Avoid high-impact news (handled by Module 19)

    Score range: -20 to +5
    """
    result = {"score": 0, "blocked": False, "reason": None, "notes": []}

    # ── Max 2 losses/day hard block ──
    if daily_losses >= 2:
        result["score"] = -20
        result["blocked"] = True
        result["reason"] = "max_daily_losses"
        result["notes"].append(
            f"BLOCKED: {daily_losses} losses today — Callisto FX max 2 losses/day rule. "
            f"STOP TRADING. Come back tomorrow.")
        return result

    # ── Session enforcement: London + NY only ──
    # London: 07:00-16:00 UTC, NY: 12:00-21:00 UTC
    in_london = 7 <= utc_hour < 16
    in_ny = 12 <= utc_hour < 21

    if not in_london and not in_ny:
        result["score"] = -15
        result["blocked"] = True
        result["reason"] = "outside_session"
        result["notes"].append(
            f"BLOCKED: Current hour {utc_hour}:00 UTC — outside London/NY sessions. "
            f"Callisto FX: Trade London and NY sessions ONLY.")
        return result

    # Bonus for overlap session (highest probability)
    if in_london and in_ny:
        result["score"] += 3
        result["notes"].append("London/NY overlap — highest probability window")
    elif in_london:
        result["score"] += 2
        result["notes"].append("London session active")
    elif in_ny:
        result["score"] += 2
        result["notes"].append("New York session active")

    # ── Counter-trend penalty ──
    if is_counter_trend:
        result["score"] -= 5
        result["notes"].append(
            "Counter-trend trade — Callisto FX requires CHoCH retest + BOS "
            "for counter-trend entries. Extra confirmation needed.")

    return result


# ════════════════════════════════════════════════════════════════
# MAIN SCORING FUNCTION
# ════════════════════════════════════════════════════════════════
def gold_engine_score(
    df_m15: pd.DataFrame,
    df_h1: pd.DataFrame,
    df_h4: pd.DataFrame,
    direction: str,
    utc_hour: int = None,
    events: list = None,
    td_api_key: str = "",
    df_5m: pd.DataFrame = None,
    df_daily: pd.DataFrame = None,
    daily_losses: int = 0,
) -> dict:
    """
    Gold Engine V6 Callisto — Run all 26 modules and produce final score + grade.

    Modules 1-17: Pure technical (Gold Engine V4 foundation)
    Module 18-20: Institutional edge (V5)
    Module 21: TRC Score (Callisto FX core framework)
    Module 22: WCR Range Detection (William-Certified Range)
    Module 23: Breaker Block + SMA44 Strategy
    Module 24: Premium/Discount Array (ICT Fib 50%)
    Module 25: Expanded Candlestick Patterns
    Module 26: Callisto Risk Enforcer (session + loss limits)

    Returns dict with:
        score, grade, confidence, direction, modules (detail per module),
        h4_aligned, confirmations, contradictions, blocked, institutional_bias,
        trc_setup, callisto_grade
    """
    if utc_hour is None:
        utc_hour = datetime.now(timezone.utc).hour

    price = float(df_m15["close"].iloc[-1]) if df_m15 is not None and len(df_m15) > 0 else 0

    # ── CALLISTO RISK ENFORCER (Module 26) — Check FIRST ──
    # Determine if this is a counter-trend trade
    h4_trend = _trend_from_emas(df_h4)
    target = "bull" if direction == "BUY" else "bear"
    is_counter_trend = (target not in h4_trend) and h4_trend != "neutral"

    m26 = _score_risk_enforcer(utc_hour, direction, daily_losses, is_counter_trend)

    # If risk enforcer blocks, return immediately
    if m26.get("blocked"):
        return {
            "score": 0,
            "raw_score": 0,
            "technical_score": 0,
            "institutional_score": 0,
            "callisto_score": m26["score"],
            "grade": "D",
            "confidence": "BLOCKED",
            "direction": direction,
            "price": price,
            "h4_aligned": False,
            "confirmations": 0,
            "contradictions": 0,
            "news_blocked": False,
            "risk_blocked": True,
            "risk_reason": m26.get("reason"),
            "institutional_bias": "NEUTRAL",
            "trc_setup": False,
            "callisto_grade": "BLOCKED",
            "modules": {"risk_enforcer": m26},
        }

    # ── Run original V5 modules (1-20) ──
    m1 = _mtf_alignment(df_m15, df_h1, df_h4, direction, df_daily)
    m2 = _score_sd_zone(_detect_sd_zones(df_h4), price, direction)
    m3 = _score_fvg(df_m15, price, direction)
    m4 = _score_choch(df_h1, direction)
    m5 = _score_killzone(utc_hour)
    m6 = _score_rsi_divergence(df_h1, direction)
    m7 = _score_liquidity_sweep(df_m15, direction)
    m8 = _score_asian_breakout(df_m15, direction)
    m9 = _score_momentum(df_m15, direction)
    m10 = _check_overextension(df_m15)
    m11 = _score_market_structure(df_h1, direction)
    m12 = _score_bos(df_h1, direction)
    m13 = _score_order_blocks(df_m15, price, direction, m12.get("bos", False))
    m14 = _score_fibonacci(df_h4, price, direction,
                           has_ob=m13.get("ob") is not None,
                           has_fvg=m3.get("fvg") is not None)
    m15 = _score_displacement(df_m15, direction)
    m16 = _score_bb_squeeze(df_m15, direction)
    m17 = _score_round_numbers(price)

    # Institutional Modules (18-20)
    cot_data = _cot.fetch_cot_data()
    dxy_data = _cot.fetch_dxy_trend(td_api_key)
    m18 = score_cot_dxy(direction, cot_data, dxy_data)
    m19 = score_news_filter(events or [], direction)
    m20 = score_volume(df_m15, direction)

    # ── NEW: Callisto FX Modules (21-25) ──
    m21 = _score_trc(df_5m, df_m15, df_h1, df_h4, direction, df_daily)
    m22 = _score_wcr_range(df_h1, df_h4, direction)
    m23 = _score_breaker_block(df_m15, price, direction)
    m24 = _score_premium_discount(df_h4, direction)
    m25 = _score_candlestick_patterns(df_m15, direction)

    # ── Sum scores ──
    technical_score = sum([
        m1["score"], m2["score"], m3["score"], m4["score"],
        m5["score"], m6["score"], m7["score"], m8["score"],
        m9["score"], m10["score"], m11["score"], m12["score"],
        m13["score"], m14["score"], m15["score"], m16["score"],
        m17["score"],
    ])
    institutional_score = m18["score"] + m19["score"] + m20["score"]
    callisto_score = (m21["score"] + m22["score"] + m23["score"] +
                      m24["score"] + m25["score"] + m26["score"])
    raw_score = technical_score + institutional_score + callisto_score

    # Normalize to 0-100 range
    # Max possible: ~220 (140 tech + 27 institutional + ~57 callisto)
    score = max(0, min(100, int(raw_score * 0.45 + 25)))

    # Count confirmations and contradictions
    all_modules = [m1, m2, m3, m4, m5, m6, m7, m8, m9, m11, m12, m13,
                   m14, m15, m16, m17, m18, m20, m21, m22, m23, m24, m25]
    confirmations = sum(1 for m in all_modules if m["score"] > 0)
    contradictions = sum(1 for m in [m1, m4, m8, m10, m11, m18, m19, m20, m24, m26]
                        if m["score"] < 0)

    # Hard caps
    h4_aligned = m1.get("h4_aligned", False)
    overextended = m10.get("overextended", False)
    news_blocked = m19.get("danger_level") == "BLOCKED"

    # ── TRC setup quality assessment ──
    trc_setup = m21.get("step1_trend") and m21.get("step2_choch")
    trc_full = trc_setup and m21.get("step3_retest")
    callisto_2of3 = m1.get("callisto_2of3", False)

    # ── Grade assignment with Callisto framework priority ──
    if news_blocked:
        grade = "D"
    elif trc_full and callisto_2of3:
        # Full TRC setup with 2/3 HTF alignment — highest conviction
        if score >= 68:
            grade = "A+"
        elif score >= 58:
            grade = "A"
        else:
            grade = "B"
    elif trc_setup and callisto_2of3:
        # TRC step 1+2 but waiting for retest
        if score >= 72:
            grade = "A"
        elif score >= 58:
            grade = "B"
        else:
            grade = "C"
    elif trc_setup and confirmations >= 8:
        # Strong TRC setup without full 2/3 HTF but many confirmations
        if score >= 75:
            grade = "A+"
        elif score >= 65:
            grade = "A"
        else:
            grade = "B"
    else:
        grade = _assign_grade(score, h4_aligned, overextended, confirmations, contradictions)

    # ── Callisto-specific grade (independent assessment) ──
    if trc_full and m24.get("score", 0) >= 6:
        callisto_grade = "SNIPER"
    elif trc_full:
        callisto_grade = "A+"
    elif trc_setup:
        callisto_grade = "A"
    elif callisto_2of3:
        callisto_grade = "B"
    else:
        callisto_grade = "C"

    confidence = _assign_confidence_v6(
        score, grade, h4_aligned,
        m5.get("killzone", ""), m1.get("h4_trend", ""),
        trc_full, callisto_2of3
    )

    # Determine institutional bias
    inst_bias = "NEUTRAL"
    if m18["score"] >= 5:
        inst_bias = "BULLISH" if direction == "BUY" else "BEARISH"
    elif m18["score"] <= -5:
        inst_bias = "BEARISH" if direction == "BUY" else "BULLISH"

    modules = {
        "mtf_alignment": m1,
        "supply_demand": m2,
        "fvg": m3,
        "choch": m4,
        "killzone": m5,
        "rsi_divergence": m6,
        "liquidity_sweep": m7,
        "asian_breakout": m8,
        "momentum": m9,
        "overextension": m10,
        "market_structure": m11,
        "bos": m12,
        "order_blocks": m13,
        "fibonacci": m14,
        "displacement": m15,
        "bb_squeeze": m16,
        "round_numbers": m17,
        "cot_dxy": m18,
        "news_filter": m19,
        "volume": m20,
        "trc": m21,
        "wcr_range": m22,
        "breaker_block": m23,
        "premium_discount": m24,
        "candlestick_patterns": m25,
        "risk_enforcer": m26,
    }

    return {
        "score": score,
        "raw_score": raw_score,
        "technical_score": technical_score,
        "institutional_score": institutional_score,
        "callisto_score": callisto_score,
        "grade": grade,
        "callisto_grade": callisto_grade,
        "confidence": confidence,
        "direction": direction,
        "price": price,
        "h4_aligned": h4_aligned,
        "confirmations": confirmations,
        "contradictions": contradictions,
        "news_blocked": news_blocked,
        "risk_blocked": False,
        "institutional_bias": inst_bias,
        "trc_setup": trc_setup,
        "trc_full": trc_full,
        "callisto_2of3": callisto_2of3,
        "modules": modules,
    }


def _assign_grade(score: int, h4_aligned: bool, overextended: bool,
                  confirmations: int, contradictions: int) -> str:
    """Assign grade with hard caps."""
    if not h4_aligned:
        if score >= 45:
            return "C"
        return "D"

    if overextended:
        if score >= 80:
            return "B"
        elif score >= 45:
            return "C"
        return "D"

    if contradictions >= 3 and confirmations < contradictions:
        if score >= 80:
            return "B"

    if score >= 78 and confirmations >= 8:
        return "A+"
    elif score >= 70 and confirmations >= 6:
        return "A"
    elif score >= 60:
        return "B"
    elif score >= 45:
        return "C"
    return "D"


def _assign_confidence(score: int, grade: str, h4_aligned: bool,
                       killzone: str, h4_trend: str) -> str:
    """Assign confidence level (legacy V5 — kept for backward compat)."""
    points = 0
    if score >= 95:
        points += 4
    elif score >= 88:
        points += 2

    if grade == "A+":
        points += 3
    elif grade == "A":
        points += 2

    if h4_aligned and killzone in ("London_Open", "NY_Open", "LN_Overlap"):
        points += 2

    if h4_trend in ("bull", "bear"):
        points += 1

    if points >= 9:
        return "SNIPER"
    elif points >= 6:
        return "HIGH"
    return "MEDIUM"


def _assign_confidence_v6(score: int, grade: str, h4_aligned: bool,
                          killzone: str, h4_trend: str,
                          trc_full: bool = False,
                          callisto_2of3: bool = False) -> str:
    """
    Assign confidence level — V6 Callisto edition.
    TRC full setup + premium/discount = SNIPER
    TRC setup + 2/3 rule = HIGH
    Otherwise fallback to V5 logic.
    """
    points = 0

    # Callisto TRC bonuses (highest weight)
    if trc_full:
        points += 5
    if callisto_2of3:
        points += 2

    # Score-based
    if score >= 92:
        points += 4
    elif score >= 82:
        points += 2

    # Grade-based
    if grade == "A+":
        points += 3
    elif grade == "A":
        points += 2

    # Session quality
    if h4_aligned and killzone in ("London_Open", "NY_Open", "LN_Overlap"):
        points += 2

    if h4_trend in ("bull", "bear"):
        points += 1

    if points >= 12:
        return "SNIPER"
    elif points >= 8:
        return "HIGH"
    elif points >= 4:
        return "MEDIUM"
    return "LOW"


# ════════════════════════════════════════════════════════════════
# REAL-TIME CHoCH MONITORING (for open trade protection)
# ════════════════════════════════════════════════════════════════
def detect_choch_realtime(df_h1: pd.DataFrame, df_m15: pd.DataFrame,
                         trade_direction: str) -> dict:
    """
    Monitor CHoCH against an open trade position.
    Returns alert level and details if structure shifts against the trade.

    RED ALERT: H1 CHoCH confirmed (2+ candle closes) against trade direction
    YELLOW WARNING: M15 CHoCH detected against trade direction
    """
    alerts = []

    # Check H1 CHoCH
    h1_choch = _detect_choch(df_h1, lookback=50)
    if h1_choch["detected"]:
        against_trade = (
            (trade_direction == "BUY" and h1_choch["direction"] == "bearish") or
            (trade_direction == "SELL" and h1_choch["direction"] == "bullish")
        )
        if against_trade:
            alerts.append({
                "level": "RED",
                "timeframe": "H1",
                "message": f"STRUCTURE BROKEN on H1! {h1_choch['direction'].upper()} CHoCH confirmed. "
                          f"Previous structure was {h1_choch.get('prev_structure', 'unknown')}. "
                          f"Your {trade_direction} position is at risk.",
                "choch": h1_choch,
            })

    # Check M15 CHoCH
    m15_choch = _detect_choch(df_m15, lookback=30)
    if m15_choch["detected"]:
        against_trade = (
            (trade_direction == "BUY" and m15_choch["direction"] == "bearish") or
            (trade_direction == "SELL" and m15_choch["direction"] == "bullish")
        )
        if against_trade:
            alerts.append({
                "level": "YELLOW",
                "timeframe": "M15",
                "message": f"Early warning: M15 showing {m15_choch['direction']} shift. "
                          f"H1 structure {'also broken' if any(a['level'] == 'RED' for a in alerts) else 'still intact'}. "
                          f"Monitor closely.",
                "choch": m15_choch,
            })

    return {
        "has_alert": len(alerts) > 0,
        "alerts": alerts,
        "highest_level": alerts[0]["level"] if alerts else None,
    }


# ════════════════════════════════════════════════════════════════
# FVG SECOND-WAVE ENTRY DETECTION
# ════════════════════════════════════════════════════════════════
def detect_fvg_entry(df_m15: pd.DataFrame, df_h1: pd.DataFrame) -> list:
    """
    Detect FVG zones created by institutional displacement,
    then check if price is retracing into the gap for a second-wave entry.

    Returns list of actionable FVG entry opportunities.
    """
    opportunities = []
    if df_m15 is None or len(df_m15) < 20:
        return opportunities

    # Find displacement candles on M15 (institutions entering)
    displacements = detect_displacement(df_m15, lookback=30, threshold=2.0)

    # Find FVGs near displacement candles
    fvgs = detect_fvg_candles(df_m15, min_size=1.5)  # 15 pips minimum for gold

    price = float(df_m15["close"].iloc[-1])

    for fvg in fvgs:
        # Only recent FVGs (within last 20 candles)
        if fvg["index"] < len(df_m15) - 30:
            continue

        # Check if a displacement occurred near this FVG
        displacement_nearby = any(
            abs(d["index"] - fvg["index"]) <= 2 for d in displacements
        )
        if not displacement_nearby:
            continue

        # Calculate retest zone (50-61.8% of FVG)
        fvg_mid = (fvg["top"] + fvg["bottom"]) / 2
        fvg_618 = fvg["bottom"] + (fvg["top"] - fvg["bottom"]) * 0.618

        # Check if price is approaching or inside the FVG
        pip = 0.1
        buffer = 20 * pip  # 20 pip approach zone

        if fvg["type"] == "bullish":
            # Price should be coming down into the gap
            if fvg["bottom"] - buffer <= price <= fvg["top"]:
                opportunities.append({
                    "type": "bullish_fvg_retest",
                    "direction": "BUY",
                    "fvg_top": fvg["top"],
                    "fvg_bottom": fvg["bottom"],
                    "optimal_entry": fvg_618,
                    "current_price": price,
                    "distance_pips": round(abs(price - fvg_618) / pip, 1),
                    "has_displacement": True,
                    "message": f"Bullish FVG retest zone: ${fvg['bottom']:.2f}-${fvg['top']:.2f}. "
                              f"Optimal entry near ${fvg_618:.2f} (61.8% of gap). "
                              f"Institution displacement confirmed.",
                })

        elif fvg["type"] == "bearish":
            if fvg["bottom"] <= price <= fvg["top"] + buffer:
                opportunities.append({
                    "type": "bearish_fvg_retest",
                    "direction": "SELL",
                    "fvg_top": fvg["top"],
                    "fvg_bottom": fvg["bottom"],
                    "optimal_entry": fvg_mid,
                    "current_price": price,
                    "distance_pips": round(abs(price - fvg_mid) / pip, 1),
                    "has_displacement": True,
                    "message": f"Bearish FVG retest zone: ${fvg['bottom']:.2f}-${fvg['top']:.2f}. "
                              f"Optimal entry near ${fvg_mid:.2f} (50% of gap). "
                              f"Institution displacement confirmed.",
                })

    return opportunities
