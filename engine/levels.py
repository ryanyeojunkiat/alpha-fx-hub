"""
Alpha FX Hub — SL/TP Level Computation & Lot Sizing
ATR-based levels with spike detection and smart entry.
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger("alpha_fx_hub.levels")

PIP = 0.1  # Gold pip = $0.10
PIP_VALUE_PER_LOT = 10.0  # USD per pip per standard lot


def compute_levels(
    df: pd.DataFrame,
    direction: str,
    atr_sl_mult: float = 1.5,
    atr_tp1_mult: float = 2.0,
    atr_tp2_mult: float = 4.5,
) -> dict:
    """
    Compute SL, TP1, TP2 based on ATR.
    Returns dict with entry, sl, tp1, tp2, risk_pips, rr_ratio.
    """
    if df is None or len(df) < 14 or "atr14" not in df.columns:
        return {"valid": False}

    price = float(df["close"].iloc[-1])
    atr = float(df["atr14"].iloc[-1])

    if atr <= 0:
        return {"valid": False}

    sl_dist = atr * atr_sl_mult
    tp1_dist = atr * atr_tp1_mult
    tp2_dist = atr * atr_tp2_mult

    if direction == "BUY":
        sl = round(price - sl_dist, 2)
        tp1 = round(price + tp1_dist, 2)
        tp2 = round(price + tp2_dist, 2)
    else:
        sl = round(price + sl_dist, 2)
        tp1 = round(price - tp1_dist, 2)
        tp2 = round(price - tp2_dist, 2)

    risk_pips = round(abs(price - sl) / PIP, 1)
    reward_pips = round(abs(tp1 - price) / PIP, 1)
    rr_ratio = round(reward_pips / max(risk_pips, 0.1), 2)

    return {
        "valid": True,
        "entry": price,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "atr": round(atr, 2),
        "risk_pips": risk_pips,
        "reward_pips": reward_pips,
        "rr_ratio": rr_ratio,
        "direction": direction,
    }


def compute_10tp_levels(entry: float, sl: float, direction: str,
                        tp_pips: list = None) -> list:
    """
    Compute 10 TP levels from entry price.
    Returns list of 10 TP prices.
    """
    if tp_pips is None:
        from config import TP_LEVELS_PIPS
        tp_pips = TP_LEVELS_PIPS

    levels = []
    cumulative = 0
    for pips in tp_pips:
        cumulative += pips
        if direction == "BUY":
            tp_price = round(entry + cumulative * PIP, 2)
        else:
            tp_price = round(entry - cumulative * PIP, 2)
        levels.append(tp_price)

    return levels


def compute_lot(
    balance: float,
    risk_pct: float,
    sl_pips: float,
    pip_value: float = PIP_VALUE_PER_LOT,
) -> float:
    """Calculate lot size based on risk percentage."""
    if sl_pips <= 0 or balance <= 0:
        return 0.01

    risk_amount = balance * (risk_pct / 100.0)
    lot = risk_amount / (sl_pips * pip_value)
    lot = max(0.01, min(5.0, round(lot, 2)))
    return lot


def compute_lot_tiers(balance: float, sl_pips: float) -> dict:
    """Calculate lot sizes for all 3 risk tiers."""
    return {
        "conservative": compute_lot(balance, 2.0, sl_pips),
        "moderate": compute_lot(balance, 3.0, sl_pips),
        "aggressive": compute_lot(balance, 5.0, sl_pips),
    }


def spike_adjusted_levels(levels: dict, spike_detected: bool) -> dict:
    """Widen SL by 50% if a danger spike is detected."""
    if not spike_detected or not levels.get("valid"):
        return levels

    levels = levels.copy()
    entry = levels["entry"]
    old_sl = levels["sl"]
    sl_dist = abs(entry - old_sl)
    new_sl_dist = sl_dist * 1.5

    if levels["direction"] == "BUY":
        levels["sl"] = round(entry - new_sl_dist, 2)
    else:
        levels["sl"] = round(entry + new_sl_dist, 2)

    levels["risk_pips"] = round(new_sl_dist / PIP, 1)
    levels["spike_adjusted"] = True
    return levels


def compute_trailing_sl(
    entry: float,
    direction: str,
    current_tp_hit: int,
    tp_levels: list,
) -> float:
    """
    Compute trailing SL based on which TP has been hit.
    Uses the 15/10 split + trailing rules from config.

    Rules:
      TP1 hit → SL to breakeven + 2 pip buffer
      TP4 hit → SL to TP2 level
      TP7 hit → SL to TP5 level
    """
    buffer = 2 * PIP  # 2 pip buffer

    if current_tp_hit >= 7 and len(tp_levels) >= 5:
        return tp_levels[4]  # TP5 level
    elif current_tp_hit >= 4 and len(tp_levels) >= 2:
        return tp_levels[1]  # TP2 level
    elif current_tp_hit >= 1:
        if direction == "BUY":
            return entry + buffer
        else:
            return entry - buffer

    return None  # No trailing yet
