"""
Alpha FX Hub — Signal Scanner
Dual-mode: Scalp (M15) + Swing (H4)
Generates signals with grades, confidence, and lot recommendations.
"""
import time
import logging
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime, timezone

from .indicators import add_indicators
from .gold_engine import gold_engine_score, detect_fvg_entry
from .levels import compute_levels, compute_10tp_levels, compute_lot_tiers
from .data import fetch_bars

logger = logging.getLogger("alpha_fx_hub.scanner")


@dataclass
class Signal:
    """A trading signal with everything a trader needs."""
    timestamp: str = ""
    mode: str = ""              # "SCALP" or "SWING"
    symbol: str = "XAUUSD"
    direction: str = ""         # "BUY" or "SELL"
    grade: str = ""
    score: int = 0
    confidence: str = ""        # "SNIPER", "HIGH", "MEDIUM"
    entry_price: float = 0.0
    entry_type: str = ""        # "MARKET" or "LIMIT"
    sl: float = 0.0
    tp_levels: List[float] = field(default_factory=list)
    risk_pips: float = 0.0
    rr_ratio: float = 0.0
    lot_conservative: float = 0.0
    lot_moderate: float = 0.0
    lot_aggressive: float = 0.0
    atr: float = 0.0
    h4_trend: str = ""
    killzone: str = ""
    confirmations: int = 0
    contradictions: int = 0
    fvg_entry: dict = field(default_factory=dict)
    modules: dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_valid(self) -> bool:
        return self.grade in ("A+", "A") and self.score > 0


class SignalScanner:
    """
    Scans XAUUSD for trading opportunities.
    Dual-mode: Scalp (M15 entry) + Swing (H4 entry).
    """

    def __init__(self, balance: float = 10000.0, api_key: str = None):
        self.balance = balance
        self.api_key = api_key
        self.last_scalp_signal_time = 0
        self.last_swing_signal_time = 0
        self.last_scalp_direction = None
        self.scalp_cooldown = 1800    # 30 min
        self.swing_cooldown = 14400   # 4 hours

    def scan(self, mode: str = "both") -> List[Signal]:
        """
        Run a full scan. Returns list of valid signals.
        mode: "scalp", "swing", or "both"
        """
        signals = []

        # Fetch data for all timeframes
        df_m15 = fetch_bars("XAU/USD", "15min", 200, self.api_key)
        df_h1 = fetch_bars("XAU/USD", "1h", 200, self.api_key)
        df_h4 = fetch_bars("XAU/USD", "4h", 200, self.api_key)

        if df_m15 is None or df_h1 is None or df_h4 is None:
            logger.error("Failed to fetch price data")
            return signals

        # Add indicators to all timeframes
        df_m15 = add_indicators(df_m15)
        df_h1 = add_indicators(df_h1)
        df_h4 = add_indicators(df_h4)

        now = time.time()
        utc_hour = datetime.now(timezone.utc).hour

        # Determine possible directions
        for direction in ["BUY", "SELL"]:
            result = gold_engine_score(df_m15, df_h1, df_h4, direction, utc_hour)

            # Check FVG second-wave opportunities
            fvg_entries = detect_fvg_entry(df_m15, df_h1)
            fvg_match = next((f for f in fvg_entries if f["direction"] == direction), None)

            # SCALP MODE
            if mode in ("scalp", "both"):
                if (now - self.last_scalp_signal_time >= self.scalp_cooldown and
                    (self.last_scalp_direction != direction or
                     now - self.last_scalp_signal_time >= self.scalp_cooldown)):

                    if result["grade"] in ("A+", "A") and result["score"] >= 78:
                        # Killzone required for scalp
                        kz = result["modules"]["killzone"].get("killzone", "")
                        if kz != "Off-hours":
                            signal = self._build_signal(
                                "SCALP", direction, result, df_m15,
                                atr_sl=1.0, atr_tp1=1.5, fvg_entry=fvg_match,
                            )
                            if signal:
                                signals.append(signal)
                                self.last_scalp_signal_time = now
                                self.last_scalp_direction = direction

            # SWING MODE
            if mode in ("swing", "both"):
                if now - self.last_swing_signal_time >= self.swing_cooldown:
                    if result["grade"] in ("A+", "A") and result["score"] >= 80:
                        if result["h4_aligned"]:
                            signal = self._build_signal(
                                "SWING", direction, result, df_m15,
                                atr_sl=1.5, atr_tp1=2.0, fvg_entry=fvg_match,
                            )
                            if signal:
                                signals.append(signal)
                                self.last_swing_signal_time = now

        return signals

    def _build_signal(self, mode: str, direction: str, engine_result: dict,
                     df: pd.DataFrame, atr_sl: float, atr_tp1: float,
                     fvg_entry: dict = None) -> Optional[Signal]:
        """Build a complete Signal object from engine results."""
        levels = compute_levels(df, direction, atr_sl_mult=atr_sl, atr_tp1_mult=atr_tp1)
        if not levels.get("valid"):
            return None

        # Compute 10 TP levels
        tp_levels = compute_10tp_levels(levels["entry"], levels["sl"], direction)

        # Lot sizing
        lots = compute_lot_tiers(self.balance, levels["risk_pips"])

        # Determine entry type
        entry_type = "MARKET"
        entry_price = levels["entry"]

        # If FVG retest opportunity, suggest LIMIT entry at optimal price
        if fvg_entry:
            entry_type = "LIMIT"
            entry_price = round(fvg_entry["optimal_entry"], 2)

        signal = Signal(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            mode=mode,
            direction=direction,
            grade=engine_result["grade"],
            score=engine_result["score"],
            confidence=engine_result["confidence"],
            entry_price=entry_price,
            entry_type=entry_type,
            sl=levels["sl"],
            tp_levels=tp_levels,
            risk_pips=levels["risk_pips"],
            rr_ratio=levels["rr_ratio"],
            lot_conservative=lots["conservative"],
            lot_moderate=lots["moderate"],
            lot_aggressive=lots["aggressive"],
            atr=levels["atr"],
            h4_trend=engine_result["modules"]["mtf_alignment"]["h4_trend"],
            killzone=engine_result["modules"]["killzone"].get("killzone", ""),
            confirmations=engine_result["confirmations"],
            contradictions=engine_result["contradictions"],
            fvg_entry=fvg_entry or {},
            modules=engine_result["modules"],
        )

        # Add notes
        notes = []
        if signal.confidence == "SNIPER":
            notes.append("SNIPER SETUP - Maximum conviction")
        if fvg_entry:
            notes.append(f"FVG LIMIT entry at ${entry_price:.2f}")
        if engine_result["modules"]["fibonacci"].get("ote"):
            notes.append("OTE confluence detected")
        if engine_result["modules"]["liquidity_sweep"].get("detected"):
            notes.append("Liquidity sweep confirmed")

        signal.notes = " | ".join(notes)
        return signal

    def get_market_overview(self) -> dict:
        """Get current market state without generating signals."""
        df_m15 = fetch_bars("XAU/USD", "15min", 200, self.api_key)
        df_h1 = fetch_bars("XAU/USD", "1h", 200, self.api_key)
        df_h4 = fetch_bars("XAU/USD", "4h", 200, self.api_key)

        if df_m15 is None:
            return {"error": "No data available"}

        df_m15 = add_indicators(df_m15)
        df_h1 = add_indicators(df_h1) if df_h1 is not None else None
        df_h4 = add_indicators(df_h4) if df_h4 is not None else None

        price = float(df_m15["close"].iloc[-1])
        atr = float(df_m15["atr14"].iloc[-1]) if "atr14" in df_m15.columns else 0
        rsi = float(df_m15["rsi14"].iloc[-1]) if "rsi14" in df_m15.columns else 50

        # Score both directions
        buy_result = gold_engine_score(df_m15, df_h1, df_h4, "BUY")
        sell_result = gold_engine_score(df_m15, df_h1, df_h4, "SELL")

        # Determine bias
        if buy_result["score"] > sell_result["score"] + 10:
            bias = "BULLISH"
        elif sell_result["score"] > buy_result["score"] + 10:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        # Check for FVG entries
        fvg_entries = detect_fvg_entry(df_m15, df_h1)

        return {
            "price": price,
            "atr": round(atr, 2),
            "rsi": round(rsi, 1),
            "bias": bias,
            "buy_score": buy_result["score"],
            "buy_grade": buy_result["grade"],
            "sell_score": sell_result["score"],
            "sell_grade": sell_result["grade"],
            "h4_trend": buy_result["modules"]["mtf_alignment"]["h4_trend"],
            "h1_trend": buy_result["modules"]["mtf_alignment"]["h1_trend"],
            "killzone": buy_result["modules"]["killzone"].get("killzone", ""),
            "structure": buy_result["modules"]["market_structure"].get("structure", "unknown"),
            "fvg_opportunities": fvg_entries,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
