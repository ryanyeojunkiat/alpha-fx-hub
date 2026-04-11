"""
Alpha FX Hub — Price Action Engine V2
=====================================
Replaces the indicator-stacking scoring system with real price action analysis.

Core concepts:
1. Market Structure: Swing H/L → HH/HL/LH/LL → Trend determination
2. Key Levels: Support/Resistance from significant swing points
3. Liquidity Sweep: Price takes out a key level then reverses (smart money)
4. Entry Confirmation: Rejection candle at key level after sweep
5. Structural SL: Behind the sweep point, not ATR-based
6. TP at next key level: Not arbitrary R:R multiples

Designed for XAUUSD first, then extensible to all pairs.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


# ============================================================
# 1. SWING DETECTION — Foundation of everything
# ============================================================
def detect_swings(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """Detect swing highs and swing lows using N-bar fractal method.

    A swing high: bar whose high is higher than the `lookback` bars on each side.
    A swing low:  bar whose low is lower than the `lookback` bars on each side.

    For real-time (rightmost bars), we use 3-bar confirmation instead of 5.
    """
    x = df.copy()
    x["swing_high"] = False
    x["swing_low"] = False
    x["swing_high_price"] = np.nan
    x["swing_low_price"] = np.nan

    highs = x["high"].values
    lows = x["low"].values
    n = len(x)

    for i in range(lookback, n - lookback):
        # Swing High: higher than lookback bars on each side
        if all(highs[i] > highs[i - j] for j in range(1, lookback + 1)) and \
           all(highs[i] > highs[i + j] for j in range(1, lookback + 1)):
            x.iloc[i, x.columns.get_loc("swing_high")] = True
            x.iloc[i, x.columns.get_loc("swing_high_price")] = highs[i]

        # Swing Low: lower than lookback bars on each side
        if all(lows[i] < lows[i - j] for j in range(1, lookback + 1)) and \
           all(lows[i] < lows[i + j] for j in range(1, lookback + 1)):
            x.iloc[i, x.columns.get_loc("swing_low")] = True
            x.iloc[i, x.columns.get_loc("swing_low_price")] = lows[i]

    # Real-time: use 3-bar confirmation for the most recent bars
    rt_lb = min(3, lookback)
    for i in range(n - lookback, n - rt_lb):
        if all(highs[i] > highs[i - j] for j in range(1, rt_lb + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, min(rt_lb + 1, n - i))):
            x.iloc[i, x.columns.get_loc("swing_high")] = True
            x.iloc[i, x.columns.get_loc("swing_high_price")] = highs[i]
        if all(lows[i] < lows[i - j] for j in range(1, rt_lb + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, min(rt_lb + 1, n - i))):
            x.iloc[i, x.columns.get_loc("swing_low")] = True
            x.iloc[i, x.columns.get_loc("swing_low_price")] = lows[i]

    return x


def get_recent_swings(df: pd.DataFrame, max_swings: int = 10) -> Tuple[List[dict], List[dict]]:
    """Extract the most recent swing highs and lows as lists of dicts.
    Each dict: {"idx": int, "price": float, "time": timestamp}
    """
    swing_highs = []
    swing_lows = []

    for i in range(len(df) - 1, -1, -1):
        row = df.iloc[i]
        if row.get("swing_high", False) and not pd.isna(row.get("swing_high_price", np.nan)):
            swing_highs.append({
                "idx": i,
                "price": float(row["swing_high_price"]),
                "time": row.get("time", row.name) if "time" in df.columns else i
            })
            if len(swing_highs) >= max_swings:
                break
        if row.get("swing_low", False) and not pd.isna(row.get("swing_low_price", np.nan)):
            swing_lows.append({
                "idx": i,
                "price": float(row["swing_low_price"]),
                "time": row.get("time", row.name) if "time" in df.columns else i
            })
            if len(swing_lows) >= max_swings:
                break

    # Re-scan for the other type if we hit max on one side
    if len(swing_highs) < max_swings:
        for i in range(len(df) - 1, -1, -1):
            row = df.iloc[i]
            if row.get("swing_high", False) and not pd.isna(row.get("swing_high_price", np.nan)):
                if not any(s["idx"] == i for s in swing_highs):
                    swing_highs.append({"idx": i, "price": float(row["swing_high_price"])})
                    if len(swing_highs) >= max_swings:
                        break

    return swing_highs, swing_lows


# ============================================================
# 2. MARKET STRUCTURE — HH/HL/LH/LL
# ============================================================
@dataclass
class StructurePoint:
    type: str       # "HH", "HL", "LH", "LL"
    price: float
    idx: int
    time: object = None


def analyze_structure(df: pd.DataFrame) -> dict:
    """Analyze market structure from swing points.

    Returns:
      trend: "BULLISH", "BEARISH", "RANGING"
      structure_points: list of StructurePoint
      last_bos: last Break of Structure info
      last_choch: last Change of Character info
    """
    swing_highs, swing_lows = get_recent_swings(df, max_swings=8)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {
            "trend": "INSUFFICIENT",
            "structure_points": [],
            "last_bos": None,
            "last_choch": None,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
        }

    # Sort by index (chronological)
    swing_highs = sorted(swing_highs, key=lambda x: x["idx"])
    swing_lows = sorted(swing_lows, key=lambda x: x["idx"])

    # Classify each swing point
    points = []

    # Process highs: compare consecutive
    for i in range(1, len(swing_highs)):
        prev_h = swing_highs[i - 1]["price"]
        curr_h = swing_highs[i]["price"]
        if curr_h > prev_h:
            points.append(StructurePoint("HH", curr_h, swing_highs[i]["idx"]))
        else:
            points.append(StructurePoint("LH", curr_h, swing_highs[i]["idx"]))

    # Process lows: compare consecutive
    for i in range(1, len(swing_lows)):
        prev_l = swing_lows[i - 1]["price"]
        curr_l = swing_lows[i]["price"]
        if curr_l > prev_l:
            points.append(StructurePoint("HL", curr_l, swing_lows[i]["idx"]))
        else:
            points.append(StructurePoint("LL", curr_l, swing_lows[i]["idx"]))

    # Sort all points chronologically
    points.sort(key=lambda p: p.idx)

    # Determine trend from last 4-6 structure points
    recent = points[-6:] if len(points) >= 6 else points
    types = [p.type for p in recent]

    hh_count = types.count("HH")
    hl_count = types.count("HL")
    lh_count = types.count("LH")
    ll_count = types.count("LL")

    # Break of Structure (BOS) = trend continuation confirmed
    # Change of Character (CHoCH) = trend reversal signal
    last_bos = None
    last_choch = None

    if len(points) >= 2:
        last_two = types[-2:]
        # BOS: HH in uptrend, LL in downtrend
        if last_two == ["HH", "HL"] or last_two == ["HL", "HH"]:
            last_bos = {"type": "BULLISH_BOS", "point": points[-1]}
        elif last_two == ["LL", "LH"] or last_two == ["LH", "LL"]:
            last_bos = {"type": "BEARISH_BOS", "point": points[-1]}
        # CHoCH: first LH in uptrend, first HL in downtrend
        if (hh_count + hl_count > lh_count + ll_count) and types[-1] in ("LH", "LL"):
            last_choch = {"type": "BEARISH_CHOCH", "point": points[-1]}
        elif (lh_count + ll_count > hh_count + hl_count) and types[-1] in ("HH", "HL"):
            last_choch = {"type": "BULLISH_CHOCH", "point": points[-1]}

    # Determine overall trend
    bull_score = hh_count + hl_count
    bear_score = lh_count + ll_count

    if bull_score >= bear_score + 2:
        trend = "BULLISH"
    elif bear_score >= bull_score + 2:
        trend = "BEARISH"
    elif bull_score > bear_score:
        trend = "BULLISH_WEAK"
    elif bear_score > bull_score:
        trend = "BEARISH_WEAK"
    else:
        trend = "RANGING"

    return {
        "trend": trend,
        "structure_points": points,
        "last_bos": last_bos,
        "last_choch": last_choch,
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "hh": hh_count, "hl": hl_count,
        "lh": lh_count, "ll": ll_count,
    }


# ============================================================
# 3. KEY LEVELS — Support / Resistance Zones
# ============================================================
@dataclass
class KeyLevel:
    price: float
    type: str           # "SUPPORT", "RESISTANCE", "S/R_FLIP"
    strength: int       # 1-5: how many times tested
    last_test_idx: int  # when last tested
    swept: bool = False # has it been swept (liquidity taken)?
    sweep_idx: int = -1


def find_key_levels(df: pd.DataFrame, atr: float, merge_threshold: float = 0.5) -> List[KeyLevel]:
    """Find key support/resistance levels from swing points.

    Levels within `merge_threshold * ATR` of each other are merged.
    Strength = number of touches/tests.
    """
    swing_highs, swing_lows = get_recent_swings(df, max_swings=15)

    # Collect all significant prices
    raw_levels = []
    for sh in swing_highs:
        raw_levels.append({"price": sh["price"], "type": "RESISTANCE", "idx": sh["idx"]})
    for sl in swing_lows:
        raw_levels.append({"price": sl["price"], "type": "SUPPORT", "idx": sl["idx"]})

    if not raw_levels:
        return []

    # Sort by price
    raw_levels.sort(key=lambda x: x["price"])

    # Merge nearby levels
    merged = []
    zone_range = atr * merge_threshold

    i = 0
    while i < len(raw_levels):
        cluster = [raw_levels[i]]
        j = i + 1
        while j < len(raw_levels) and abs(raw_levels[j]["price"] - cluster[0]["price"]) < zone_range:
            cluster.append(raw_levels[j])
            j += 1

        # Merge cluster: average price, combined type, strength = count
        avg_price = np.mean([c["price"] for c in cluster])
        types = set(c["type"] for c in cluster)
        if "SUPPORT" in types and "RESISTANCE" in types:
            level_type = "S/R_FLIP"  # Acted as both — very strong
        elif "RESISTANCE" in types:
            level_type = "RESISTANCE"
        else:
            level_type = "SUPPORT"

        strength = len(cluster)
        last_idx = max(c["idx"] for c in cluster)

        merged.append(KeyLevel(
            price=round(avg_price, 3),
            type=level_type,
            strength=min(strength, 5),
            last_test_idx=last_idx,
        ))
        i = j

    # Check if any levels have been swept
    current_price = float(df.iloc[-1]["close"])
    recent_high = float(df.iloc[-5:]["high"].max())
    recent_low = float(df.iloc[-5:]["low"].min())

    for level in merged:
        if level.type in ("RESISTANCE", "S/R_FLIP"):
            # Swept if price went above then came back below
            if recent_high > level.price and current_price < level.price:
                level.swept = True
                level.sweep_idx = len(df) - 1
        elif level.type == "SUPPORT":
            # Swept if price went below then came back above
            if recent_low < level.price and current_price > level.price:
                level.swept = True
                level.sweep_idx = len(df) - 1

    return merged


def nearest_support(levels: List[KeyLevel], price: float) -> Optional[KeyLevel]:
    """Find the nearest support level below current price."""
    supports = [l for l in levels if l.price < price and l.type in ("SUPPORT", "S/R_FLIP")]
    if not supports:
        return None
    return max(supports, key=lambda l: l.price)  # Closest below


def nearest_resistance(levels: List[KeyLevel], price: float) -> Optional[KeyLevel]:
    """Find the nearest resistance level above current price."""
    resistances = [l for l in levels if l.price > price and l.type in ("RESISTANCE", "S/R_FLIP")]
    if not resistances:
        return None
    return min(resistances, key=lambda l: l.price)  # Closest above


# ============================================================
# 4. LIQUIDITY SWEEP DETECTION (Smart Money)
# ============================================================
@dataclass
class SweepSignal:
    detected: bool = False
    direction: str = ""      # "BULLISH" (swept lows, going up) or "BEARISH" (swept highs, going down)
    sweep_price: float = 0   # The extreme price that swept the level
    level_price: float = 0   # The key level that was swept
    recovery_price: float = 0  # Price after recovery
    strength: str = "LOW"    # "HIGH", "MEDIUM", "LOW"
    candle_idx: int = -1


def detect_liquidity_sweep(df: pd.DataFrame, levels: List[KeyLevel], atr: float) -> List[SweepSignal]:
    """Detect liquidity sweeps in the last few candles.

    A bullish sweep: price dips below support, then closes back above it.
    A bearish sweep: price spikes above resistance, then closes back below it.
    """
    sweeps = []
    if len(df) < 5 or atr <= 0:
        return sweeps

    # Check last 3 candles for sweeps
    for offset in range(1, 4):
        if offset >= len(df):
            break
        row = df.iloc[-offset]
        prev_close = float(df.iloc[-offset - 1]["close"]) if offset + 1 < len(df) else float(row["open"])

        for level in levels:
            # Bullish sweep: wick below support, close back above
            if level.type in ("SUPPORT", "S/R_FLIP"):
                if float(row["low"]) < level.price and float(row["close"]) > level.price:
                    wick_depth = level.price - float(row["low"])
                    strength = "HIGH" if wick_depth > 0.5 * atr else "MEDIUM" if wick_depth > 0.2 * atr else "LOW"
                    sweeps.append(SweepSignal(
                        detected=True,
                        direction="BULLISH",
                        sweep_price=float(row["low"]),
                        level_price=level.price,
                        recovery_price=float(row["close"]),
                        strength=strength,
                        candle_idx=len(df) - offset,
                    ))

            # Bearish sweep: wick above resistance, close back below
            if level.type in ("RESISTANCE", "S/R_FLIP"):
                if float(row["high"]) > level.price and float(row["close"]) < level.price:
                    wick_depth = float(row["high"]) - level.price
                    strength = "HIGH" if wick_depth > 0.5 * atr else "MEDIUM" if wick_depth > 0.2 * atr else "LOW"
                    sweeps.append(SweepSignal(
                        detected=True,
                        direction="BEARISH",
                        sweep_price=float(row["high"]),
                        level_price=level.price,
                        recovery_price=float(row["close"]),
                        strength=strength,
                        candle_idx=len(df) - offset,
                    ))

    return sweeps


# ============================================================
# 5. ENTRY CONFIRMATION — Rejection candles at key levels
# ============================================================
@dataclass
class EntrySignal:
    valid: bool = False
    direction: str = ""        # "BUY" or "SELL"
    entry_type: str = ""       # "SWEEP_REVERSAL", "KEY_LEVEL_REJECTION", "BOS_RETEST", "CHOCH_ENTRY"
    entry_price: float = 0
    sl_price: float = 0
    tp1_price: float = 0
    tp2_price: float = 0
    tp3_price: float = 0
    rr: float = 0
    score: int = 0
    grade: str = "D"
    breakdown: Dict[str, int] = field(default_factory=dict)
    reason: str = ""
    confluence: List[str] = field(default_factory=list)


def check_rejection_candle(df: pd.DataFrame, direction: str, lookback: int = 2) -> dict:
    """Check if recent candles show rejection (pin bar, engulfing, hammer, etc.)

    Returns dict with: found, pattern_name, strength (1-3)
    """
    if len(df) < lookback + 1:
        return {"found": False, "pattern": "", "strength": 0}

    for offset in range(lookback):
        row = df.iloc[-(offset + 1)]
        body = abs(float(row["close"]) - float(row["open"]))
        full_range = float(row["high"]) - float(row["low"])
        if full_range == 0:
            continue

        upper_wick = float(row["high"]) - max(float(row["close"]), float(row["open"]))
        lower_wick = min(float(row["close"]), float(row["open"])) - float(row["low"])
        is_bullish = float(row["close"]) > float(row["open"])

        if direction == "BUY":
            # Pin bar (bullish): long lower wick
            if lower_wick > 2 * body and upper_wick < 0.3 * full_range:
                return {"found": True, "pattern": "PIN_BAR", "strength": 3}
            # Hammer
            if lower_wick > 1.5 * body and upper_wick < 0.5 * full_range and is_bullish:
                return {"found": True, "pattern": "HAMMER", "strength": 2}
            # Bullish engulfing
            if offset == 0 and len(df) >= 2:
                prev = df.iloc[-2]
                if is_bullish and float(prev["close"]) < float(prev["open"]) and \
                   float(row["close"]) > float(prev["open"]) and float(row["open"]) < float(prev["close"]):
                    return {"found": True, "pattern": "ENGULFING", "strength": 3}
            # Strong bullish candle (body > 60% of range)
            if is_bullish and body > 0.6 * full_range:
                return {"found": True, "pattern": "STRONG_BULL", "strength": 1}

        elif direction == "SELL":
            # Pin bar (bearish): long upper wick
            if upper_wick > 2 * body and lower_wick < 0.3 * full_range:
                return {"found": True, "pattern": "PIN_BAR", "strength": 3}
            # Shooting star
            if upper_wick > 1.5 * body and lower_wick < 0.5 * full_range and not is_bullish:
                return {"found": True, "pattern": "SHOOTING_STAR", "strength": 2}
            # Bearish engulfing
            if offset == 0 and len(df) >= 2:
                prev = df.iloc[-2]
                if not is_bullish and float(prev["close"]) > float(prev["open"]) and \
                   float(row["close"]) < float(prev["open"]) and float(row["open"]) > float(prev["close"]):
                    return {"found": True, "pattern": "ENGULFING", "strength": 3}
            # Strong bearish candle
            if not is_bullish and body > 0.6 * full_range:
                return {"found": True, "pattern": "STRONG_BEAR", "strength": 1}

    return {"found": False, "pattern": "", "strength": 0}


# ============================================================
# 6. HONEST SCORING — Based on actual edge factors
# ============================================================
def score_setup(
    structure: dict,
    levels: List[KeyLevel],
    sweeps: List[SweepSignal],
    rejection: dict,
    direction: str,
    rr: float,
    htf_trend: str,
    atr: float,
    current_price: float,
) -> Tuple[int, Dict[str, int], str]:
    """Score a setup based on real edge factors.

    Components (max 100):
      1. Structure Clarity (25): Is the trend clear from HH/HL or LH/LL?
      2. Key Level Quality (20): How strong is the level we're trading from?
      3. Sweep Quality (20): Was liquidity taken? How clean?
      4. Rejection Candle (15): Pin bar/engulfing at key level?
      5. Risk:Reward (10): Higher R:R = better
      6. MTF Alignment (10): Does higher timeframe agree?
    """
    bd: Dict[str, int] = {}
    reasons: List[str] = []

    # 1. Structure Clarity (max 25)
    trend = structure.get("trend", "INSUFFICIENT")
    bos = structure.get("last_bos")
    choch = structure.get("last_choch")

    if direction == "BUY":
        if trend == "BULLISH":
            bd["Structure"] = 25
            reasons.append("Clear bullish structure (HH/HL)")
        elif trend == "BULLISH_WEAK":
            bd["Structure"] = 15
            reasons.append("Weak bullish structure")
        elif trend == "RANGING":
            bd["Structure"] = 8
            reasons.append("Ranging — trade from support")
        elif choch and choch["type"] == "BULLISH_CHOCH":
            bd["Structure"] = 20
            reasons.append("Bullish CHoCH detected")
        else:
            bd["Structure"] = 0
            reasons.append("Bearish structure — BUY risky")
    else:  # SELL
        if trend == "BEARISH":
            bd["Structure"] = 25
            reasons.append("Clear bearish structure (LH/LL)")
        elif trend == "BEARISH_WEAK":
            bd["Structure"] = 15
            reasons.append("Weak bearish structure")
        elif trend == "RANGING":
            bd["Structure"] = 8
            reasons.append("Ranging — trade from resistance")
        elif choch and choch["type"] == "BEARISH_CHOCH":
            bd["Structure"] = 20
            reasons.append("Bearish CHoCH detected")
        else:
            bd["Structure"] = 0
            reasons.append("Bullish structure — SELL risky")

    # 2. Key Level Quality (max 20)
    if direction == "BUY":
        level = nearest_support(levels, current_price)
    else:
        level = nearest_resistance(levels, current_price)

    if level:
        dist = abs(current_price - level.price)
        if dist < atr * 0.8:  # Close to the level
            base = min(level.strength * 4, 16)  # 4 pts per touch, max 16
            if level.type == "S/R_FLIP":
                base += 4  # S/R flip = very strong
            bd["Level"] = min(base, 20)
            reasons.append(f"Near {level.type} @ {level.price:.1f} (strength {level.strength})")
        elif dist < atr * 1.5:
            bd["Level"] = min(level.strength * 3, 12)
            reasons.append(f"Approaching {level.type} @ {level.price:.1f}")
        elif dist < atr * 2.5:
            bd["Level"] = min(level.strength * 1, 5)
            reasons.append(f"Distant {level.type} @ {level.price:.1f}")
        else:
            bd["Level"] = 0
            reasons.append("Not near any key level")
    else:
        bd["Level"] = 0
        reasons.append("No key level found")

    # 3. Sweep Quality (max 20)
    matching_sweeps = [s for s in sweeps if
                       (direction == "BUY" and s.direction == "BULLISH") or
                       (direction == "SELL" and s.direction == "BEARISH")]

    if matching_sweeps:
        best = max(matching_sweeps, key=lambda s: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[s.strength])
        if best.strength == "HIGH":
            bd["Sweep"] = 20
            reasons.append(f"Strong liquidity sweep @ {best.sweep_price:.1f}")
        elif best.strength == "MEDIUM":
            bd["Sweep"] = 14
            reasons.append(f"Medium sweep @ {best.sweep_price:.1f}")
        else:
            bd["Sweep"] = 8
            reasons.append(f"Weak sweep @ {best.sweep_price:.1f}")
    else:
        bd["Sweep"] = 0
        # Not having a sweep is OK for trend continuation, not ideal for reversals

    # 4. Rejection Candle (max 15)
    if rejection["found"]:
        bd["Candle"] = rejection["strength"] * 5  # 5/10/15
        reasons.append(f"{rejection['pattern']} rejection ({rejection['strength']}/3)")
    else:
        bd["Candle"] = 0
        reasons.append("No clear rejection candle")

    # 5. Risk:Reward (max 10)
    if rr >= 3.0:
        bd["R:R"] = 10
    elif rr >= 2.0:
        bd["R:R"] = 8
    elif rr >= 1.5:
        bd["R:R"] = 6
    elif rr >= 1.0:
        bd["R:R"] = 3
    else:
        bd["R:R"] = 0

    # 6. MTF Alignment (max 10)
    if direction == "BUY":
        if htf_trend in ("BULLISH", "bull"):
            bd["MTF"] = 10
        elif htf_trend in ("BULLISH_WEAK", "bull_weak"):
            bd["MTF"] = 6
        elif htf_trend in ("RANGING", "neutral"):
            bd["MTF"] = 3
        else:
            bd["MTF"] = 0  # Counter-trend
    else:
        if htf_trend in ("BEARISH", "bear"):
            bd["MTF"] = 10
        elif htf_trend in ("BEARISH_WEAK", "bear_weak"):
            bd["MTF"] = 6
        elif htf_trend in ("RANGING", "neutral"):
            bd["MTF"] = 3
        else:
            bd["MTF"] = 0

    total = sum(bd.values())
    total = max(0, min(100, total))

    # Grade
    if total >= 90:
        grade = "A+"
    elif total >= 80:
        grade = "A"
    elif total >= 65:
        grade = "B"
    elif total >= 45:
        grade = "C"
    else:
        grade = "D"

    return total, bd, grade


# ============================================================
# 7. GENERATE TRADE PLAN — Putting it all together
# ============================================================
@dataclass
class TradePlan:
    valid: bool = False
    symbol: str = ""
    direction: str = "Wait"     # "Buy", "Sell", "Wait"
    entry_type: str = ""        # "SWEEP_REVERSAL", "KEY_LEVEL_REJECTION", "BOS_CONTINUATION", "CHOCH_REVERSAL"
    entry: float = 0
    sl: float = 0
    tp1: float = 0
    tp2: float = 0
    tp3: float = 0
    rr: float = 0
    score: int = 0
    grade: str = "D"
    breakdown: Dict[str, int] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    confluence_count: int = 0
    structure_trend: str = ""
    market_sentiment: str = ""
    entry_level: Optional[KeyLevel] = None
    sweep: Optional[SweepSignal] = None
    rejection: dict = field(default_factory=dict)
    ready: bool = False


def generate_plan(
    df: pd.DataFrame,
    symbol: str = "XAUUSD",
    htf_trend: str = "neutral",
    htf_df: pd.DataFrame = None,
) -> TradePlan:
    """Main entry point: analyze price action and generate a trade plan.

    Steps:
    1. Detect swings → build market structure
    2. Find key levels from swings
    3. Check for liquidity sweeps at key levels
    4. Look for rejection candle confirmation
    5. Calculate structural SL and key-level TP
    6. Score the setup honestly
    """
    plan = TradePlan(symbol=symbol)

    if len(df) < 50:
        plan.reasons.append("Insufficient data")
        return plan

    row = df.iloc[-1]
    atr = float(row.get("atr14", 0))
    if atr <= 0:
        plan.reasons.append("Invalid ATR")
        return plan

    price = float(row["close"])

    # Step 1: Detect swings and analyze structure
    df_swings = detect_swings(df, lookback=5)
    structure = analyze_structure(df_swings)
    plan.structure_trend = structure["trend"]

    if structure["trend"] == "INSUFFICIENT":
        plan.reasons.append("Insufficient swing data for structure")
        return plan

    # Step 2: Find key levels
    levels = find_key_levels(df_swings, atr, merge_threshold=0.6)

    # Step 3: Detect liquidity sweeps
    sweeps = detect_liquidity_sweep(df, levels, atr)

    # Step 4: Determine direction and check rejection
    direction = _determine_direction(structure, sweeps, levels, price, atr, htf_trend)

    if direction == "Wait":
        plan.direction = "Wait"
        plan.reasons.append("No clear setup — waiting")
        return plan

    rejection = check_rejection_candle(df, direction, lookback=2)

    # Step 5: Calculate structural SL and TP
    entry = price
    sl, tp1, tp2, tp3, entry_type = _calc_levels(
        direction, price, levels, sweeps, structure, atr, df
    )

    if sl == 0 or tp1 == 0:
        plan.reasons.append("Could not calculate valid SL/TP")
        return plan

    risk = abs(entry - sl)
    if risk <= 0:
        plan.reasons.append("Invalid risk (SL too close)")
        return plan

    reward = abs(tp1 - entry)
    rr = reward / risk

    # Don't take trades with R:R < 1.0
    if rr < 1.0:
        plan.direction = "Wait"
        plan.reasons.append(f"R:R too low ({rr:.2f})")
        return plan

    # Step 6: Score
    score, breakdown, grade = score_setup(
        structure, levels, sweeps, rejection, direction, rr, htf_trend, atr, price
    )

    # Count confluence (components with > 0 score)
    confluence = sum(1 for v in breakdown.values() if v > 0)

    # Determine readiness — must have structure + at least one more confluence
    has_structure = breakdown.get("Structure", 0) >= 15
    has_level_or_sweep = breakdown.get("Level", 0) >= 5 or breakdown.get("Sweep", 0) >= 8
    has_candle = breakdown.get("Candle", 0) >= 5
    ready = score >= 60 and rr >= 1.5 and has_structure and has_level_or_sweep

    # Build plan
    plan.valid = True
    plan.direction = "Buy" if direction == "BUY" else "Sell"
    plan.entry_type = entry_type
    plan.entry = entry
    plan.sl = sl
    plan.tp1 = tp1
    plan.tp2 = tp2
    plan.tp3 = tp3
    plan.rr = rr
    plan.score = score
    plan.grade = grade
    plan.breakdown = breakdown
    plan.confluence_count = confluence
    plan.rejection = rejection
    plan.ready = ready

    # Build reason list
    for r in _build_reasons(structure, levels, sweeps, rejection, direction, rr, htf_trend):
        plan.reasons.append(r)

    return plan


def _determine_direction(structure, sweeps, levels, price, atr, htf_trend) -> str:
    """Decide trade direction based on structure, sweeps, and levels.

    Decision hierarchy:
    1. Sweep + structure alignment → highest conviction
    2. CHoCH → reversal signal
    3. BOS + pullback to key level → continuation
    4. Key level reaction in clear trend
    5. Trend + pullback (even without perfect sweep)
    """
    trend = structure["trend"]
    bos = structure.get("last_bos")
    choch = structure.get("last_choch")
    bull_sweeps = [s for s in sweeps if s.direction == "BULLISH"]
    bear_sweeps = [s for s in sweeps if s.direction == "BEARISH"]

    support = nearest_support(levels, price)
    resistance = nearest_resistance(levels, price)
    near_support = support and abs(price - support.price) < atr * 1.2
    near_resistance = resistance and abs(price - resistance.price) < atr * 1.2

    # Priority 1: Liquidity sweep → trade the reversal direction
    if bull_sweeps and any(s.strength in ("HIGH", "MEDIUM") for s in bull_sweeps):
        # Bullish sweep (price dipped below support, recovered) → BUY
        if trend in ("BULLISH", "BULLISH_WEAK", "RANGING"):
            return "BUY"
        # Even in weak bearish, if HTF is bullish, a sweep can be a reversal
        if htf_trend in ("BULLISH", "BULLISH_WEAK", "bull", "bull_weak"):
            return "BUY"

    if bear_sweeps and any(s.strength in ("HIGH", "MEDIUM") for s in bear_sweeps):
        if trend in ("BEARISH", "BEARISH_WEAK", "RANGING"):
            return "SELL"
        if htf_trend in ("BEARISH", "BEARISH_WEAK", "bear", "bear_weak"):
            return "SELL"

    # Priority 2: CHoCH → trade the new direction
    if choch:
        if choch["type"] == "BULLISH_CHOCH":
            return "BUY"
        elif choch["type"] == "BEARISH_CHOCH":
            return "SELL"

    # Priority 3: BOS + near key level → continuation
    if trend in ("BULLISH", "BULLISH_WEAK") and near_support:
        return "BUY"
    if trend in ("BEARISH", "BEARISH_WEAK") and near_resistance:
        return "SELL"

    # Priority 4: Clear trend + any pullback signal
    # Even without perfect key level, if trend is clear and price pulled back
    if trend == "BULLISH":
        # Check if there's been a recent pullback (price below EMA20 or near recent low)
        if bull_sweeps:  # Any sweep, even LOW strength
            return "BUY"
    elif trend == "BEARISH":
        if bear_sweeps:
            return "SELL"

    # Priority 5: Ranging market — trade from extremes only
    if trend == "RANGING":
        if near_support and bull_sweeps:
            return "BUY"
        if near_resistance and bear_sweeps:
            return "SELL"

    return "Wait"


def _calc_levels(direction, price, levels, sweeps, structure, atr, df) -> Tuple[float, float, float, float, str]:
    """Calculate structural SL, TP1/2/3, and entry type."""
    entry_type = "KEY_LEVEL_REJECTION"
    sl = 0.0
    tp1 = tp2 = tp3 = 0.0

    matching_sweeps = [s for s in sweeps if
                       (direction == "BUY" and s.direction == "BULLISH") or
                       (direction == "SELL" and s.direction == "BEARISH")]

    if direction == "BUY":
        # SL: below the sweep low OR below the nearest swing low
        if matching_sweeps:
            sweep_low = min(s.sweep_price for s in matching_sweeps)
            sl = sweep_low - atr * 0.3  # Buffer below sweep
            entry_type = "SWEEP_REVERSAL"
        else:
            # Below last swing low
            swing_lows = structure.get("swing_lows", [])
            if swing_lows:
                recent_low = min(s["price"] for s in swing_lows[:3])
                sl = recent_low - atr * 0.3
            else:
                sl = price - atr * 1.5  # Fallback

        # Ensure SL is not too tight (min 0.8 ATR for gold)
        if abs(price - sl) < atr * 0.8:
            sl = price - atr * 1.0

        # Ensure SL is not too wide (max 3.0 ATR)
        if abs(price - sl) > atr * 3.0:
            sl = price - atr * 2.5

        # TP: at next resistance levels
        resistance = nearest_resistance(levels, price)
        if resistance:
            tp1 = resistance.price
        else:
            tp1 = price + abs(price - sl) * 1.5  # Minimum 1.5R

        # TP2: next resistance above TP1
        higher_res = [l for l in levels if l.price > tp1 + atr * 0.3 and l.type in ("RESISTANCE", "S/R_FLIP")]
        if higher_res:
            tp2 = min(l.price for l in higher_res)
        else:
            tp2 = price + abs(price - sl) * 2.5

        tp3 = price + abs(price - sl) * 3.5  # Extended target

    else:  # SELL
        # SL: above the sweep high OR above the nearest swing high
        if matching_sweeps:
            sweep_high = max(s.sweep_price for s in matching_sweeps)
            sl = sweep_high + atr * 0.3
            entry_type = "SWEEP_REVERSAL"
        else:
            swing_highs = structure.get("swing_highs", [])
            if swing_highs:
                recent_high = max(s["price"] for s in swing_highs[:3])
                sl = recent_high + atr * 0.3
            else:
                sl = price + atr * 1.5

        if abs(sl - price) < atr * 0.8:
            sl = price + atr * 1.0
        if abs(sl - price) > atr * 3.0:
            sl = price + atr * 2.5

        support = nearest_support(levels, price)
        if support:
            tp1 = support.price
        else:
            tp1 = price - abs(sl - price) * 1.5

        lower_sup = [l for l in levels if l.price < tp1 - atr * 0.3 and l.type in ("SUPPORT", "S/R_FLIP")]
        if lower_sup:
            tp2 = max(l.price for l in lower_sup)
        else:
            tp2 = price - abs(sl - price) * 2.5

        tp3 = price - abs(sl - price) * 3.5

    # Detect CHoCH or BOS entry type
    choch = structure.get("last_choch")
    bos = structure.get("last_bos")
    if choch:
        if (direction == "BUY" and choch["type"] == "BULLISH_CHOCH") or \
           (direction == "SELL" and choch["type"] == "BEARISH_CHOCH"):
            entry_type = "CHOCH_REVERSAL"
    elif bos:
        if (direction == "BUY" and bos["type"] == "BULLISH_BOS") or \
           (direction == "SELL" and bos["type"] == "BEARISH_BOS"):
            entry_type = "BOS_CONTINUATION"

    return sl, tp1, tp2, tp3, entry_type


def _build_reasons(structure, levels, sweeps, rejection, direction, rr, htf_trend) -> List[str]:
    """Build human-readable reason list for the trade."""
    reasons = []
    trend = structure.get("trend", "?")
    reasons.append(f"Structure: {trend}")

    matching_sweeps = [s for s in sweeps if
                       (direction == "BUY" and s.direction == "BULLISH") or
                       (direction == "SELL" and s.direction == "BEARISH")]
    if matching_sweeps:
        best = matching_sweeps[0]
        reasons.append(f"Sweep: {best.strength} @ {best.sweep_price:.1f}")

    if rejection.get("found"):
        reasons.append(f"Candle: {rejection['pattern']}")

    reasons.append(f"R:R: {rr:.2f}")
    reasons.append(f"HTF: {htf_trend}")

    return reasons


# ============================================================
# 8. MULTI-TIMEFRAME ANALYSIS
# ============================================================
def get_htf_structure(df_h1: pd.DataFrame = None, df_h4: pd.DataFrame = None) -> str:
    """Determine higher timeframe trend from H1 and H4 data."""
    trends = []

    for label, df in [("H4", df_h4), ("H1", df_h1)]:
        if df is None or len(df) < 50:
            continue
        df_sw = detect_swings(df, lookback=5)
        struct = analyze_structure(df_sw)
        trends.append(struct["trend"])

    if not trends:
        return "neutral"

    # If both agree → strong signal
    if len(trends) >= 2 and trends[0] == trends[1]:
        return trends[0]

    # If one is bullish/bearish and other is weak → use the stronger
    bull = sum(1 for t in trends if "BULLISH" in t)
    bear = sum(1 for t in trends if "BEARISH" in t)

    if bull > bear:
        return "BULLISH_WEAK"
    elif bear > bull:
        return "BEARISH_WEAK"

    return "RANGING"
