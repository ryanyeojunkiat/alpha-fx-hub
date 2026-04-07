"""
Alpha FX Hub — Signal Scanner V6 Callisto
Dual-mode: Scalp (M15) + Swing (H4)
Built on Callisto FX TRC Framework with 5M entry triggers.
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

# Calendar import for news filter
try:
    from academy.calendar import fetch_economic_calendar, get_gold_impact_events
except ImportError:
    # Fallback if calendar module not available
    def fetch_economic_calendar(**kwargs):
        return []
    def get_gold_impact_events(events):
        return events

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
    confidence: str = ""        # "SNIPER", "HIGH", "MEDIUM", "LOW"
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
    institutional_bias: str = ""    # "BULLISH", "BEARISH", "NEUTRAL"
    news_danger: str = ""           # "CLEAR", "CAUTION", "DANGER"
    institutional_score: int = 0
    # Callisto FX V6 fields
    callisto_grade: str = ""        # "SNIPER", "A+", "A", "B", "C"
    trc_setup: bool = False         # TRC Steps 1+2 confirmed
    trc_full: bool = False          # TRC Steps 1+2+3 (full entry trigger)
    callisto_2of3: bool = False     # 2/3 HTF rule met
    callisto_score: int = 0         # Score from Callisto modules only
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    # V6 Optimized: Layered order fields
    layered_lot: float = 0.01           # Per-order lot size
    layered_orders: int = 5              # Number of orders
    layered_tps: List[float] = field(default_factory=list)  # 5 TP prices
    layered_sl: float = 0.0             # Shared SL price
    risk_per_trade: float = 0.0         # Total risk in $
    best_case_profit: float = 0.0       # All 5 TPs hit

    @property
    def is_valid(self) -> bool:
        return self.grade == "A+" and self.score > 0  # V6 Optimized: A+ ONLY


class SignalScanner:
    """
    Scans XAUUSD for trading opportunities.
    Dual-mode: Scalp (M15 entry) + Swing (H4 entry).
    """

    def __init__(self, balance: float = 10000.0, api_key: str = None, te_api_key: str = ""):
        self.balance = balance
        self.api_key = api_key
        self.te_api_key = te_api_key  # Trading Economics key for news filter
        self.last_scalp_signal_time = 0
        self.last_swing_signal_time = 0
        self.last_scalp_direction = None
        self.scalp_cooldown = 1800    # 30 min
        self.swing_cooldown = 14400   # 4 hours
        self.daily_losses = 0          # Callisto FX: track daily losses
        self.last_loss_date = None     # Reset counter each day

    def scan(self, mode: str = "both") -> List[Signal]:
        """
        Run a full scan — V6 Callisto edition.
        Fetches Daily + 5M for TRC framework alongside original TFs.
        mode: "scalp", "swing", or "both"
        """
        signals = []

        # Reset daily loss counter if new day
        today = datetime.now(timezone.utc).date()
        if self.last_loss_date != today:
            self.daily_losses = 0
            self.last_loss_date = today

        # Fetch data for all timeframes (V6: added Daily + 5M for Callisto TRC)
        df_5m = fetch_bars("XAU/USD", "5min", 200, self.api_key)
        df_m15 = fetch_bars("XAU/USD", "15min", 200, self.api_key)
        df_h1 = fetch_bars("XAU/USD", "1h", 200, self.api_key)
        df_h4 = fetch_bars("XAU/USD", "4h", 200, self.api_key)
        df_daily = fetch_bars("XAU/USD", "1day", 200, self.api_key)

        if df_m15 is None or df_h1 is None or df_h4 is None:
            logger.error("Failed to fetch price data")
            return signals

        # Add indicators to all timeframes
        if df_5m is not None:
            df_5m = add_indicators(df_5m)
        df_m15 = add_indicators(df_m15)
        df_h1 = add_indicators(df_h1)
        df_h4 = add_indicators(df_h4)
        if df_daily is not None:
            df_daily = add_indicators(df_daily)

        # Fetch economic calendar for news filter (Module 19)
        try:
            calendar_events = fetch_economic_calendar(api_key=self.te_api_key)
            gold_events = get_gold_impact_events(calendar_events)
        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}")
            gold_events = []

        now = time.time()
        utc_hour = datetime.now(timezone.utc).hour

        # Determine possible directions
        for direction in ["BUY", "SELL"]:
            result = gold_engine_score(
                df_m15, df_h1, df_h4, direction, utc_hour,
                events=gold_events, td_api_key=self.api_key or "",
                df_5m=df_5m, df_daily=df_daily,
                daily_losses=self.daily_losses,
            )

            # RISK ENFORCER HARD BLOCK (Callisto FX — session/loss limits)
            if result.get("risk_blocked"):
                reason = result.get("risk_reason", "unknown")
                logger.info(f"Signal BLOCKED by Callisto risk enforcer: {reason} — {direction} skipped")
                continue

            # NEWS FILTER HARD BLOCK — do not generate signal if high-impact event imminent
            if result.get("news_blocked"):
                blocking_event = result["modules"].get("news_filter", {}).get("blocking_event", "")
                logger.info(f"Signal BLOCKED by news filter: {blocking_event} — {direction} skipped")
                continue

            # Check FVG second-wave opportunities
            fvg_entries = detect_fvg_entry(df_m15, df_h1)
            fvg_match = next((f for f in fvg_entries if f["direction"] == direction), None)

            # SCALP MODE
            if mode in ("scalp", "both"):
                if (now - self.last_scalp_signal_time >= self.scalp_cooldown and
                    (self.last_scalp_direction != direction or
                     now - self.last_scalp_signal_time >= self.scalp_cooldown)):

                    if result["grade"] == "A+" and result["score"] >= 80:
                        # V6 Optimized: A+ ONLY for maximum conviction
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
                    if result["grade"] == "A+" and result["score"] >= 82:
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

        # V6 Optimized: Compute layered order levels
        from config import LAYERED_LOT_SIZE, LAYERED_NUM_ORDERS, LAYERED_TP_PIPS, FIXED_SL_PIPS
        PIP = 0.1
        PIP_VALUE = LAYERED_LOT_SIZE * 10.0  # $ per pip per micro lot

        layered_tps = []
        for tp_pips in LAYERED_TP_PIPS:
            if direction == "BUY":
                layered_tps.append(round(entry_price + tp_pips * PIP, 2))
            else:
                layered_tps.append(round(entry_price - tp_pips * PIP, 2))

        risk_per_trade = PIP_VALUE * FIXED_SL_PIPS * LAYERED_NUM_ORDERS
        best_case = sum(PIP_VALUE * tp for tp in LAYERED_TP_PIPS)

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
            institutional_bias=engine_result.get("institutional_bias", "NEUTRAL"),
            news_danger=engine_result["modules"].get("news_filter", {}).get("danger_level", "CLEAR"),
            institutional_score=engine_result.get("institutional_score", 0),
            # Callisto FX V6 fields
            callisto_grade=engine_result.get("callisto_grade", ""),
            trc_setup=engine_result.get("trc_setup", False),
            trc_full=engine_result.get("trc_full", False),
            callisto_2of3=engine_result.get("callisto_2of3", False),
            callisto_score=engine_result.get("callisto_score", 0),
            # V6 Optimized: Layered order fields
            layered_lot=LAYERED_LOT_SIZE,
            layered_orders=LAYERED_NUM_ORDERS,
            layered_tps=layered_tps,
            layered_sl=levels["sl"],
            risk_per_trade=risk_per_trade,
            best_case_profit=best_case,
        )

        # Add notes
        notes = []

        # Callisto FX TRC framework notes (top priority)
        if signal.trc_full:
            notes.append("TRC FULL SETUP - All 3 steps confirmed (Trend+Reversal+Continuation)")
        elif signal.trc_setup:
            notes.append("TRC Steps 1+2 confirmed — waiting for retest entry")

        if signal.callisto_grade == "SNIPER":
            notes.append("CALLISTO SNIPER — Maximum conviction entry")
        elif signal.confidence == "SNIPER":
            notes.append("SNIPER SETUP - Maximum conviction")

        if signal.callisto_2of3:
            notes.append("Callisto 2/3 HTF rule confirmed")

        if fvg_entry:
            notes.append(f"FVG LIMIT entry at ${entry_price:.2f}")
        if engine_result["modules"]["fibonacci"].get("ote"):
            notes.append("OTE confluence detected")
        if engine_result["modules"]["liquidity_sweep"].get("detected"):
            notes.append("Liquidity sweep confirmed")

        # Callisto module-specific notes
        trc_notes = engine_result["modules"].get("trc", {}).get("notes", [])
        if trc_notes:
            notes.append(trc_notes[-1])  # Add latest TRC insight
        wcr_notes = engine_result["modules"].get("wcr_range", {}).get("notes", [])
        if wcr_notes:
            notes.append(wcr_notes[0])
        bb_notes = engine_result["modules"].get("breaker_block", {}).get("notes", [])
        if bb_notes:
            notes.append(bb_notes[0])
        pd_notes = engine_result["modules"].get("premium_discount", {}).get("notes", [])
        if pd_notes:
            notes.append(pd_notes[0])

        # Institutional notes
        inst_bias = engine_result.get("institutional_bias", "NEUTRAL")
        if inst_bias != "NEUTRAL":
            notes.append(f"Institutional bias: {inst_bias}")
        cot_notes = engine_result["modules"].get("cot_dxy", {}).get("notes", [])
        if cot_notes:
            notes.append(cot_notes[0])
        vol_notes = engine_result["modules"].get("volume", {}).get("notes", [])
        if vol_notes:
            notes.append(vol_notes[0])

        signal.notes = " | ".join(notes)
        return signal

    def record_loss(self):
        """Record a trade loss for Callisto FX daily loss tracking."""
        today = datetime.now(timezone.utc).date()
        if self.last_loss_date != today:
            self.daily_losses = 0
            self.last_loss_date = today
        self.daily_losses += 1
        logger.info(f"Loss recorded: {self.daily_losses}/2 daily max (Callisto FX)")

    def get_market_overview(self) -> dict:
        """Get current market state — V6 Callisto edition."""
        df_5m = fetch_bars("XAU/USD", "5min", 200, self.api_key)
        df_m15 = fetch_bars("XAU/USD", "15min", 200, self.api_key)
        df_h1 = fetch_bars("XAU/USD", "1h", 200, self.api_key)
        df_h4 = fetch_bars("XAU/USD", "4h", 200, self.api_key)
        df_daily = fetch_bars("XAU/USD", "1day", 200, self.api_key)

        if df_m15 is None:
            return {"error": "No data available"}

        if df_5m is not None:
            df_5m = add_indicators(df_5m)
        df_m15 = add_indicators(df_m15)
        df_h1 = add_indicators(df_h1) if df_h1 is not None else None
        df_h4 = add_indicators(df_h4) if df_h4 is not None else None
        if df_daily is not None:
            df_daily = add_indicators(df_daily)

        price = float(df_m15["close"].iloc[-1])
        atr = float(df_m15["atr14"].iloc[-1]) if "atr14" in df_m15.columns else 0
        rsi = float(df_m15["rsi14"].iloc[-1]) if "rsi14" in df_m15.columns else 50

        # Score both directions with V6 engine
        buy_result = gold_engine_score(
            df_m15, df_h1, df_h4, "BUY",
            df_5m=df_5m, df_daily=df_daily,
            daily_losses=self.daily_losses,
        )
        sell_result = gold_engine_score(
            df_m15, df_h1, df_h4, "SELL",
            df_5m=df_5m, df_daily=df_daily,
            daily_losses=self.daily_losses,
        )

        # Determine bias
        if buy_result["score"] > sell_result["score"] + 10:
            bias = "BULLISH"
        elif sell_result["score"] > buy_result["score"] + 10:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        # Check for FVG entries
        fvg_entries = detect_fvg_entry(df_m15, df_h1)

        # Callisto FX premium/discount assessment
        from .indicators import detect_premium_discount
        pd_zone = detect_premium_discount(df_h4) if df_h4 is not None else None

        return {
            "price": price,
            "atr": round(atr, 2),
            "rsi": round(rsi, 1),
            "bias": bias,
            "buy_score": buy_result["score"],
            "buy_grade": buy_result["grade"],
            "sell_score": sell_result["score"],
            "sell_grade": sell_result["grade"],
            "h4_trend": buy_result["modules"].get("mtf_alignment", {}).get("h4_trend", "neutral"),
            "h1_trend": buy_result["modules"].get("mtf_alignment", {}).get("h1_trend", "neutral"),
            "daily_trend": buy_result["modules"].get("mtf_alignment", {}).get("daily_trend", "neutral"),
            "killzone": buy_result["modules"].get("killzone", {}).get("killzone", ""),
            "structure": buy_result["modules"].get("market_structure", {}).get("structure", "unknown"),
            "fvg_opportunities": fvg_entries,
            # Callisto FX V6 fields
            "callisto_buy_grade": buy_result.get("callisto_grade", ""),
            "callisto_sell_grade": sell_result.get("callisto_grade", ""),
            "trc_buy_setup": buy_result.get("trc_setup", False),
            "trc_sell_setup": sell_result.get("trc_setup", False),
            "premium_discount": pd_zone,
            "callisto_2of3_buy": buy_result.get("callisto_2of3", False),
            "callisto_2of3_sell": sell_result.get("callisto_2of3", False),
            "daily_losses": self.daily_losses,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "engine_version": "V6 Callisto",
        }
