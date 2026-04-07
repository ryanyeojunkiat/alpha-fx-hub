"""
Alpha FX Hub — Unified Decision Engine
═══════════════════════════════════════════════════════════════
Combines the Callisto 26-Module Technical Engine with Grok AI's
world-class strategy knowledge into ONE unified trading decision.

Flow:
  1. Callisto Engine → Scores signal (grade, score, direction, modules)
  2. Strategy Brain → Loads world-class trading knowledge
  3. Grok AI → Analyzes market data + Callisto result + all strategies
  4. Unified Engine → Merges both into FINAL decision with adjusted levels

The output is a single UnifiedSignal with:
  - Combined direction, grade, confidence
  - AI-optimized entry, SL, and TP levels (not arbitrary pips)
  - Full reasoning from both Callisto modules and Grok strategies
  - Risk management with layered orders
"""
import json
import logging
import pandas as pd
from typing import Optional, Dict
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger("alpha_fx_hub.unified")


@dataclass
class UnifiedSignal:
    """The final combined signal from Callisto + Grok."""
    symbol: str = ""
    direction: str = "NO_TRADE"         # BUY / SELL / NO_TRADE
    grade: str = "NO_TRADE"             # A+ / A / B / C / NO_TRADE
    confidence: int = 0                 # 1-100 unified confidence

    # Callisto engine data
    callisto_score: int = 0
    callisto_grade: str = ""
    callisto_direction: str = ""
    callisto_modules: dict = field(default_factory=dict)

    # Grok AI decision
    grok_agrees: bool = False
    grok_overrode: bool = False
    callisto_agreement: str = ""        # AGREE / OVERRIDE / PARTIAL

    # Unified levels (AI-optimized)
    entry_price: float = 0.0
    entry_type: str = "MARKET"          # MARKET / LIMIT / STOP
    entry_reason: str = ""

    sl_price: float = 0.0
    sl_pips: float = 0.0
    sl_reason: str = ""

    tp_levels: list = field(default_factory=list)  # [{price, pips, reason}]

    risk_reward: float = 0.0

    # Reasoning
    why_trade: str = ""
    why_not_trade: str = ""
    strategies_confirming: list = field(default_factory=list)
    strategies_warning: list = field(default_factory=list)
    session_context: str = ""

    # Risk management
    lot_size: float = 0.01
    num_orders: int = 5
    max_risk_usd: float = 0.0
    breakeven_rule: str = ""

    # Callisto "Why This Trade" (module-level reasoning)
    callisto_reasons: list = field(default_factory=list)

    # Metadata
    timestamp: str = ""
    model_used: str = ""

    @property
    def is_valid(self) -> bool:
        """Signal is tradeable only if A+ grade and confidence >= 70."""
        return self.grade == "A+" and self.confidence >= 70 and self.direction in ("BUY", "SELL")

    @property
    def is_a_plus(self) -> bool:
        return self.grade == "A+"


class UnifiedEngine:
    """Combines Callisto technical engine with Grok AI strategy brain."""

    def __init__(self, grok_engine, capital: float = 1200.0):
        """
        Args:
            grok_engine: GrokEngine instance (from engine/grok_engine.py)
            capital: Trading capital for position sizing
        """
        self.grok = grok_engine
        self.capital = capital

    def generate_signal(self, symbol: str, symbol_config: dict,
                        callisto_result: dict,
                        df_m15: pd.DataFrame,
                        df_h1: pd.DataFrame = None,
                        df_h4: pd.DataFrame = None) -> UnifiedSignal:
        """
        Generate a unified signal combining Callisto + Grok.

        Args:
            symbol: e.g. "XAUUSD"
            symbol_config: from config.SYMBOLS[symbol]
            callisto_result: Raw result from gold_engine_score()
            df_m15, df_h1, df_h4: Price dataframes with indicators

        Returns:
            UnifiedSignal with combined decision
        """
        signal = UnifiedSignal(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

        # ── Step 1: Extract Callisto engine data ──
        if callisto_result:
            signal.callisto_score = callisto_result.get("score", 0)
            signal.callisto_grade = callisto_result.get("grade", "C")
            signal.callisto_direction = callisto_result.get("direction", "NO_TRADE")
            signal.callisto_modules = callisto_result.get("modules", {})
            signal.callisto_reasons = self._extract_callisto_reasons(callisto_result)

        # ── Step 2: Get current price and basic levels ──
        price = float(df_m15["close"].iloc[-1]) if df_m15 is not None and len(df_m15) > 0 else 0
        pip = symbol_config.get("pip", 0.0001)

        # ── Step 3: If Grok is not available, use Callisto-only decision ──
        if not self.grok or not self.grok.is_available:
            return self._callisto_only_signal(signal, price, pip, symbol_config)

        # ── Step 4: Send everything to Grok for unified decision ──
        try:
            grok_decision = self._get_grok_unified_decision(
                symbol, symbol_config, callisto_result, df_m15, df_h1, df_h4, price, pip
            )

            if grok_decision:
                signal = self._merge_decision(signal, grok_decision, price, pip, symbol_config)
                signal.model_used = self.grok.analysis_model
            else:
                # Grok failed — fall back to Callisto-only
                return self._callisto_only_signal(signal, price, pip, symbol_config)

        except Exception as e:
            logger.error(f"Unified engine error for {symbol}: {e}")
            return self._callisto_only_signal(signal, price, pip, symbol_config)

        return signal

    def _get_grok_unified_decision(self, symbol: str, symbol_config: dict,
                                    callisto_result: dict,
                                    df_m15: pd.DataFrame,
                                    df_h1: pd.DataFrame = None,
                                    df_h4: pd.DataFrame = None,
                                    price: float = 0,
                                    pip: float = 0.0001) -> Optional[dict]:
        """Call Grok with full strategy brain + Callisto data for unified decision."""
        from engine.strategy_brain import get_full_brain_prompt, UNIFIED_DECISION_PROMPT

        # Build market data summary
        data_summary = self.grok._prepare_data_summary(symbol, symbol_config, df_m15, df_h1, df_h4)

        # Build Callisto result summary
        callisto_summary = self._format_callisto_for_grok(callisto_result, symbol_config)

        # Build the messages
        system_prompt = get_full_brain_prompt(symbol, self.capital) + "\n\n" + UNIFIED_DECISION_PROMPT

        user_prompt = f"""Make a UNIFIED TRADING DECISION for {symbol}.

═══ CALLISTO ENGINE RESULT ═══
{callisto_summary}

═══ LIVE MARKET DATA ═══
{data_summary}

═══ SYMBOL CONFIG ═══
Pip size: {pip}
Pip value per 0.01 lot: ${symbol_config.get('pip_value', 0.10) * 0.01:.4f}
Configured SL: {symbol_config.get('sl_pips', 200)} pips
Layered orders: {symbol_config.get('num_orders', 5)} × {symbol_config.get('lot_size', 0.01)} lot
Trading capital: ${self.capital:.0f}

═══ YOUR TASK ═══
Combine Callisto's 26-module analysis with ALL your strategy knowledge.
Output your UNIFIED decision in the JSON format specified.
If you override Callisto, explain why clearly.
Entry, SL, and TPs must be at REAL structural levels, not arbitrary pips."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.grok._call_grok(
            messages,
            model=self.grok.analysis_model,
            temperature=0.15,   # Low temperature for precise decisions
            max_tokens=3000
        )

        if response:
            try:
                clean = response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    clean = clean.strip()
                return json.loads(clean)
            except json.JSONDecodeError:
                logger.warning(f"Grok unified decision returned non-JSON for {symbol}")
                return None

        return None

    def _merge_decision(self, signal: UnifiedSignal, grok: dict,
                        price: float, pip: float,
                        symbol_config: dict) -> UnifiedSignal:
        """Merge Grok's unified decision into the signal object."""

        # Direction and confidence
        signal.direction = grok.get("unified_direction", "NO_TRADE")
        signal.confidence = grok.get("unified_confidence", 0)
        signal.grade = grok.get("unified_grade", "NO_TRADE")

        # Callisto agreement
        signal.callisto_agreement = grok.get("callisto_agreement", "PARTIAL")
        signal.grok_agrees = signal.callisto_agreement == "AGREE"
        signal.grok_overrode = signal.callisto_agreement == "OVERRIDE"

        # Entry
        entry = grok.get("entry", {})
        signal.entry_price = entry.get("price", price)
        signal.entry_type = entry.get("type", "MARKET")
        signal.entry_reason = entry.get("reason", "")

        # Stop Loss
        sl_data = grok.get("stop_loss", {})
        signal.sl_price = sl_data.get("price", 0)
        signal.sl_pips = sl_data.get("pips", symbol_config.get("sl_pips", 200))
        signal.sl_reason = sl_data.get("reason", "")

        # Take Profits
        tp_data = grok.get("take_profits", [])
        signal.tp_levels = []
        for tp in tp_data:
            signal.tp_levels.append({
                "level": tp.get("level", 0),
                "price": tp.get("price", 0),
                "pips": tp.get("pips", 0),
                "reason": tp.get("reason", ""),
            })

        # If Grok didn't provide TPs, fall back to config-based
        if not signal.tp_levels:
            cfg_tp = symbol_config.get("tp_pips", [200, 400, 600, 800, 1000])
            for i, tp_pips in enumerate(cfg_tp):
                if signal.direction == "BUY":
                    tp_price = round(signal.entry_price + tp_pips * pip, 5)
                else:
                    tp_price = round(signal.entry_price - tp_pips * pip, 5)
                signal.tp_levels.append({
                    "level": i + 1,
                    "price": tp_price,
                    "pips": tp_pips,
                    "reason": f"Config-based TP{i+1}",
                })

        # If Grok didn't provide SL price, compute from pips
        if signal.sl_price == 0 and signal.sl_pips > 0:
            if signal.direction == "BUY":
                signal.sl_price = round(signal.entry_price - signal.sl_pips * pip, 5)
            else:
                signal.sl_price = round(signal.entry_price + signal.sl_pips * pip, 5)

        # Risk:Reward
        signal.risk_reward = grok.get("risk_reward", 0)
        if signal.risk_reward == 0 and signal.sl_pips > 0 and signal.tp_levels:
            first_tp_pips = signal.tp_levels[0].get("pips", 0)
            if first_tp_pips > 0:
                signal.risk_reward = round(first_tp_pips / signal.sl_pips, 2)

        # Reasoning
        signal.why_trade = grok.get("why_trade", "")
        signal.why_not_trade = grok.get("why_not_trade", "")
        signal.strategies_confirming = grok.get("strategies_confirming", [])
        signal.strategies_warning = grok.get("strategies_warning", [])
        signal.session_context = grok.get("session_context", "")

        # Risk management
        rm = grok.get("risk_management", {})
        signal.lot_size = rm.get("lot_size", symbol_config.get("lot_size", 0.01))
        signal.num_orders = rm.get("num_orders", symbol_config.get("num_orders", 5))
        signal.max_risk_usd = rm.get("max_risk_usd", 0)
        signal.breakeven_rule = rm.get("breakeven_rule",
            "After TP1 hits, move SL to entry + 2 pips")

        # If max_risk not calculated, compute it
        if signal.max_risk_usd == 0:
            pip_value = signal.lot_size * symbol_config.get("pip_value", 10)
            signal.max_risk_usd = pip_value * signal.sl_pips * signal.num_orders

        return signal

    def _callisto_only_signal(self, signal: UnifiedSignal, price: float,
                               pip: float, symbol_config: dict) -> UnifiedSignal:
        """Build signal from Callisto only (when Grok is unavailable)."""
        signal.direction = signal.callisto_direction
        signal.grade = signal.callisto_grade
        signal.confidence = signal.callisto_score
        signal.entry_price = price
        signal.entry_type = "MARKET"
        signal.entry_reason = "Callisto engine entry (Grok unavailable)"

        sl_pips = symbol_config.get("sl_pips", 200)
        signal.sl_pips = sl_pips
        if signal.direction == "BUY":
            signal.sl_price = round(price - sl_pips * pip, 5)
        elif signal.direction == "SELL":
            signal.sl_price = round(price + sl_pips * pip, 5)

        signal.sl_reason = f"Fixed {sl_pips}-pip SL (Grok unavailable for structural SL)"

        cfg_tp = symbol_config.get("tp_pips", [200, 400, 600, 800, 1000])
        for i, tp_pips in enumerate(cfg_tp):
            if signal.direction == "BUY":
                tp_price = round(price + tp_pips * pip, 5)
            else:
                tp_price = round(price - tp_pips * pip, 5)
            signal.tp_levels.append({
                "level": i + 1,
                "price": tp_price,
                "pips": tp_pips,
                "reason": f"Config TP{i+1} ({tp_pips} pips)",
            })

        if cfg_tp and sl_pips > 0:
            signal.risk_reward = round(cfg_tp[0] / sl_pips, 2)

        signal.lot_size = symbol_config.get("lot_size", 0.01)
        signal.num_orders = symbol_config.get("num_orders", 5)
        pip_value = signal.lot_size * symbol_config.get("pip_value", 10)
        signal.max_risk_usd = pip_value * sl_pips * signal.num_orders
        signal.breakeven_rule = "After TP1 hits, move SL to entry + 2 pips"

        signal.why_trade = f"Callisto engine scored {signal.callisto_score}/100 ({signal.callisto_grade}). Grok AI unavailable for enhanced analysis."
        signal.callisto_agreement = "CALLISTO_ONLY"
        signal.model_used = "callisto-only"

        return signal

    def _extract_callisto_reasons(self, result: dict) -> list:
        """Extract human-readable reasons from Callisto module results."""
        reasons = []
        modules = result.get("modules", {})

        module_labels = {
            "trc": "\u2b50 TRC Framework",
            "mtf_alignment": "Multi-TF Alignment",
            "supply_demand": "Supply & Demand Zone",
            "fvg": "Fair Value Gap",
            "choch": "CHoCH Confirmed",
            "bos": "Break of Structure",
            "order_blocks": "Order Block",
            "fibonacci": "Fibonacci/OTE",
            "killzone": "ICT Killzone",
            "rsi_divergence": "RSI Divergence",
            "liquidity_sweep": "Liquidity Sweep",
            "displacement": "Displacement Candle",
            "momentum": "Strong Momentum",
            "premium_discount": "Premium/Discount Zone",
            "breaker_block": "Breaker Block",
            "wcr_range": "WCR Range",
            "market_structure": "Market Structure",
            "bb_squeeze": "BB Squeeze",
            "round_numbers": "Round Numbers",
            "overextension": "Overextension Guard",
            "asian_breakout": "Asian Breakout",
        }

        for key, label in module_labels.items():
            mod = modules.get(key, {})
            score = mod.get("score", 0)
            if score > 0:
                reasons.append(f"{label} (+{score})")

        return reasons

    def _format_callisto_for_grok(self, result: dict, config: dict) -> str:
        """Format Callisto result as text for Grok prompt."""
        if not result:
            return "No Callisto result available."

        parts = []
        parts.append(f"Direction: {result.get('direction', 'N/A')}")
        parts.append(f"Grade: {result.get('grade', 'N/A')}")
        parts.append(f"Score: {result.get('score', 0)}/100")
        parts.append(f"Confidence: {result.get('confidence', 'N/A')}")
        parts.append(f"Confirmations: {result.get('confirmations', 0)}")
        parts.append(f"Contradictions: {result.get('contradictions', 0)}")

        # Module breakdown
        modules = result.get("modules", {})
        if modules:
            parts.append("\nModule Scores:")
            for key, mod in sorted(modules.items()):
                score = mod.get("score", 0) if isinstance(mod, dict) else 0
                if score != 0:
                    parts.append(f"  {key}: {'+' if score > 0 else ''}{score}")

        return "\n".join(parts)


def get_unified_engine(grok_engine=None, capital: float = 1200.0) -> UnifiedEngine:
    """Factory function to create UnifiedEngine."""
    if grok_engine is None:
        from engine.grok_engine import get_grok_engine
        grok_engine = get_grok_engine()
    return UnifiedEngine(grok_engine=grok_engine, capital=capital)
