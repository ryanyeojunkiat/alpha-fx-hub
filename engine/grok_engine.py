"""
Alpha FX Hub — Grok xAI Engine
================================
Uses Grok (xAI) for:
1. Market Analysis — Deep analysis of market conditions, trends, news sentiment
2. Signal Confirmation — Second opinion on A+ signals before trading
3. Trade Decision — Grok calculates and decides entry/exit levels
4. Chat Assistant — Live Q&A for trading questions

Grok API: https://api.x.ai/v1/chat/completions (OpenAI-compatible)
"""
import json
import time
import logging
import requests
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger("alpha_fx_hub.grok")

_cache = {}
_CACHE_TTL = 120  # 2 min cache for analysis


class GrokEngine:
    """Grok xAI integration for trading analysis and decisions."""

    def __init__(self, api_key: str = "", model: str = "grok-3-mini-fast",
                 analysis_model: str = "grok-3-mini"):
        self.api_key = api_key
        self.model = model
        self.analysis_model = analysis_model
        self.api_url = "https://api.x.ai/v1/chat/completions"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _call_grok(self, messages: list, model: str = None,
                   temperature: float = 0.3, max_tokens: int = 1500) -> Optional[str]:
        """Call Grok API and return response text."""
        if not self.api_key:
            return None

        model = model or self.model
        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Grok API error {resp.status_code}: {resp.text[:300]}")
                return None

        except Exception as e:
            logger.error(f"Grok API call failed: {e}")
            return None

    # ════════════════════════════════════════════════════════════
    # 1. MARKET ANALYSIS — Deep analysis of current conditions
    # ════════════════════════════════════════════════════════════
    def analyze_market(self, symbol: str, symbol_config: dict,
                       df_m15: pd.DataFrame, df_h1: pd.DataFrame = None,
                       df_h4: pd.DataFrame = None) -> Optional[dict]:
        """
        Ask Grok to analyze market conditions and give a trading decision.
        Returns structured analysis with bias, confidence, and reasoning.
        """
        cache_key = f"analysis_{symbol}_{int(time.time() // _CACHE_TTL)}"
        if cache_key in _cache:
            return _cache[cache_key]

        # Prepare market data summary for Grok
        data_summary = self._prepare_data_summary(symbol, symbol_config, df_m15, df_h1, df_h4)

        messages = [
            {
                "role": "system",
                "content": f"""{self._get_brain_prompt(symbol)}

You analyze market data and make trading decisions by synthesizing ALL world-class strategies.

IMPORTANT: You must respond in valid JSON format ONLY. No markdown, no explanation outside JSON.

Your response must follow this exact JSON structure:
{{
    "bias": "BUY" or "SELL" or "NO_TRADE",
    "confidence": 1-100,
    "grade": "A+" or "A" or "B" or "C" or "NO_TRADE",
    "analysis": {{
        "trend": "bullish/bearish/ranging",
        "key_levels": {{"support": float, "resistance": float}},
        "momentum": "strong/moderate/weak/exhausted",
        "volatility": "high/normal/low"
    }},
    "entry": {{
        "price": float or null,
        "sl": float,
        "tp1": float,
        "tp2": float,
        "tp3": float,
        "reason": "string explaining entry logic"
    }},
    "reasoning": "2-3 sentence explanation of your decision",
    "risk_warning": "any specific risks to watch for"
}}

Rules:
- Only recommend BUY/SELL when confidence >= 70
- Grade A+ requires multiple confluences (structure + momentum + key level)
- Always set SL based on structure, not arbitrary pips
- Consider the current session and volatility
- If unsure, return NO_TRADE"""
            },
            {
                "role": "user",
                "content": f"""Analyze {symbol} ({symbol_config.get('name', symbol)}) and give me your trading decision.

{data_summary}

Give me your analysis and trading decision in JSON format."""
            }
        ]

        response = self._call_grok(messages, model=self.analysis_model,
                                    temperature=0.2, max_tokens=2000)

        if response:
            try:
                # Clean response (remove markdown if present)
                clean = response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    clean = clean.strip()

                result = json.loads(clean)
                result["symbol"] = symbol
                result["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                result["model"] = self.analysis_model
                _cache[cache_key] = result
                return result
            except json.JSONDecodeError:
                logger.warning(f"Grok returned non-JSON response for {symbol}")
                return {
                    "symbol": symbol,
                    "bias": "NO_TRADE",
                    "confidence": 0,
                    "grade": "NO_TRADE",
                    "reasoning": response[:500],
                    "raw_response": response,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                }

        return None

    # ════════════════════════════════════════════════════════════
    # 2. SIGNAL CONFIRMATION — Second opinion on engine signals
    # ════════════════════════════════════════════════════════════
    def confirm_signal(self, symbol: str, symbol_config: dict,
                       engine_signal: dict, df_m15: pd.DataFrame) -> Optional[dict]:
        """
        Send an A+ signal to Grok for confirmation.
        Returns: confirmed (bool), confidence, and reasoning.
        """
        data_summary = self._prepare_data_summary(symbol, symbol_config, df_m15)

        messages = [
            {
                "role": "system",
                "content": f"""{self._get_brain_prompt(symbol)}

You are now acting as a senior trading risk manager reviewing trade signals.
Your job is to confirm or reject signals based on ALL world-class strategies.

Respond in valid JSON ONLY:
{
    "confirmed": true/false,
    "confidence": 1-100,
    "agreement": "AGREE" or "DISAGREE" or "CAUTION",
    "reasoning": "2-3 sentences explaining your decision",
    "adjustments": {
        "sl_adjust": "tighter/wider/ok",
        "entry_adjust": "wait/enter_now/better_price_at",
        "notes": "any specific adjustments"
    }
}"""
            },
            {
                "role": "user",
                "content": f"""Review this {symbol} trading signal from our engine:

Signal: {engine_signal.get('direction', 'BUY')} {symbol}
Grade: {engine_signal.get('grade', 'A+')}
Score: {engine_signal.get('score', 0)}/100
Entry: ${engine_signal.get('entry_price', 0):.5f}
SL: {symbol_config.get('sl_pips', 200)} pips
Confidence: {engine_signal.get('confidence', 'N/A')}

Market Data:
{data_summary}

Should I take this trade? Confirm or reject with reasoning."""
            }
        ]

        response = self._call_grok(messages, temperature=0.2, max_tokens=800)

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
                return {
                    "confirmed": False,
                    "confidence": 0,
                    "agreement": "CAUTION",
                    "reasoning": response[:300],
                }

        return None

    # ════════════════════════════════════════════════════════════
    # 3. CHAT ASSISTANT — Live Q&A
    # ════════════════════════════════════════════════════════════
    def chat(self, user_message: str, context: str = "") -> Optional[str]:
        """
        General trading chat with Grok.
        Context can include current market state, open positions, etc.
        """
        messages = [
            {
                "role": "system",
                "content": f"""{self._get_brain_prompt()}

You are Alpha FX Hub's AI trading assistant powered by Grok (xAI).
You help traders with market analysis, strategy questions, and trading education.
You specialize in XAUUSD (Gold), Major Forex pairs, and Crypto (BTC/ETH).

Current context:
{context if context else 'No specific market context provided.'}

Be concise, actionable, and data-driven. Reference specific strategies (ICT, SMC, Wyckoff, etc.) when relevant.
Never give financial advice — frame as analysis and education."""
            },
            {"role": "user", "content": user_message}
        ]

        return self._call_grok(messages, model=self.model, temperature=0.5, max_tokens=1500)

    # ════════════════════════════════════════════════════════════
    # 4. MULTI-SYMBOL SCAN — Let Grok rank all symbols
    # ════════════════════════════════════════════════════════════
    def rank_symbols(self, market_data: Dict[str, dict]) -> Optional[list]:
        """
        Send all symbol data to Grok and ask it to rank the best opportunities.
        Returns sorted list of symbols with Grok's analysis.
        """
        summary_parts = []
        for sym, data in market_data.items():
            summary_parts.append(
                f"{sym}: Price=${data.get('price', 0):.5f}, "
                f"RSI={data.get('rsi', 50):.1f}, "
                f"Trend={data.get('trend', 'neutral')}, "
                f"ATR={data.get('atr', 0):.5f}"
            )
        all_symbols = "\n".join(summary_parts)

        messages = [
            {
                "role": "system",
                "content": """You are an expert multi-market analyst.
Rank trading opportunities across symbols by probability of success.

Respond in valid JSON ONLY — a list of objects:
[
    {
        "symbol": "XAUUSD",
        "rank": 1,
        "bias": "BUY/SELL/NO_TRADE",
        "confidence": 1-100,
        "reason": "brief reason"
    }
]

Sort by confidence (highest first). Only include symbols with confidence >= 50."""
            },
            {
                "role": "user",
                "content": f"Rank these trading opportunities right now:\n\n{all_symbols}"
            }
        ]

        response = self._call_grok(messages, model=self.analysis_model,
                                    temperature=0.2, max_tokens=2000)
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
                return None
        return None

    # ════════════════════════════════════════════════════════════
    # STRATEGY BRAIN INTEGRATION
    # ════════════════════════════════════════════════════════════
    def _get_brain_prompt(self, symbol: str = "XAUUSD") -> str:
        """Load the world-class strategy brain prompt for a given symbol."""
        try:
            from engine.strategy_brain import get_full_brain_prompt
            return get_full_brain_prompt(symbol)
        except ImportError:
            return "You are an expert forex and commodity trader specializing in technical analysis and ICT concepts."

    # ════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════
    def _prepare_data_summary(self, symbol: str, symbol_config: dict,
                               df_m15: pd.DataFrame, df_h1: pd.DataFrame = None,
                               df_h4: pd.DataFrame = None) -> str:
        """Prepare a text summary of market data for Grok."""
        parts = []
        pip = symbol_config.get("pip", 0.0001)
        now_utc = datetime.now(timezone.utc)

        parts.append(f"Symbol: {symbol} ({symbol_config.get('name', symbol)})")
        parts.append(f"Time: {now_utc.strftime('%Y-%m-%d %H:%M UTC')} (Hour: {now_utc.hour})")
        parts.append(f"Category: {symbol_config.get('category', 'forex')}")

        if df_m15 is not None and len(df_m15) > 0:
            last = df_m15.iloc[-1]
            price = float(last["close"])
            parts.append(f"\nM15 Data (last {min(len(df_m15), 20)} candles):")
            parts.append(f"  Current Price: {price:.5f}")

            if "ema20" in df_m15.columns:
                ema20 = float(df_m15["ema20"].iloc[-1])
                ema50 = float(df_m15["ema50"].iloc[-1])
                parts.append(f"  EMA20: {ema20:.5f} | EMA50: {ema50:.5f}")
                if price > ema20 > ema50:
                    parts.append(f"  M15 Trend: BULLISH (Price > EMA20 > EMA50)")
                elif price < ema20 < ema50:
                    parts.append(f"  M15 Trend: BEARISH (Price < EMA20 < EMA50)")
                else:
                    parts.append(f"  M15 Trend: MIXED")

            if "rsi14" in df_m15.columns:
                rsi = float(df_m15["rsi14"].iloc[-1])
                parts.append(f"  RSI(14): {rsi:.1f}")

            if "atr14" in df_m15.columns:
                atr = float(df_m15["atr14"].iloc[-1])
                atr_pips = atr / pip
                parts.append(f"  ATR(14): {atr:.5f} ({atr_pips:.1f} pips)")

            # Last 5 candles
            parts.append(f"  Last 5 M15 candles:")
            for _, row in df_m15.tail(5).iterrows():
                o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
                body = "GREEN" if c > o else "RED" if c < o else "DOJI"
                parts.append(f"    O:{o:.5f} H:{h:.5f} L:{l:.5f} C:{c:.5f} [{body}]")

        if df_h1 is not None and len(df_h1) > 0:
            last_h1 = df_h1.iloc[-1]
            parts.append(f"\nH1 Data:")
            parts.append(f"  Close: {float(last_h1['close']):.5f}")
            if "ema50" in df_h1.columns:
                parts.append(f"  EMA50: {float(df_h1['ema50'].iloc[-1]):.5f}")
            if "rsi14" in df_h1.columns:
                parts.append(f"  RSI: {float(df_h1['rsi14'].iloc[-1]):.1f}")

        if df_h4 is not None and len(df_h4) > 0:
            last_h4 = df_h4.iloc[-1]
            parts.append(f"\nH4 Data:")
            parts.append(f"  Close: {float(last_h4['close']):.5f}")
            if "ema50" in df_h4.columns:
                parts.append(f"  EMA50: {float(df_h4['ema50'].iloc[-1]):.5f}")
            if "rsi14" in df_h4.columns:
                parts.append(f"  RSI: {float(df_h4['rsi14'].iloc[-1]):.1f}")

        # Session info
        hour = now_utc.hour
        sessions = []
        if 7 <= hour < 16:
            sessions.append("London")
        if 12 <= hour < 21:
            sessions.append("New York")
        if 22 <= hour or hour < 7:
            sessions.append("Asian")
        if 12 <= hour < 16:
            sessions.append("LN/NY Overlap")
        parts.append(f"\nActive Sessions: {', '.join(sessions) if sessions else 'Off-hours'}")

        return "\n".join(parts)


def get_grok_engine() -> GrokEngine:
    """Factory function to create GrokEngine with config."""
    try:
        from config import GROK_API_KEY, GROK_MODEL, GROK_ANALYSIS_MODEL
    except ImportError:
        GROK_API_KEY = ""
        GROK_MODEL = "grok-3-mini-fast"
        GROK_ANALYSIS_MODEL = "grok-3-mini"

    return GrokEngine(
        api_key=GROK_API_KEY,
        model=GROK_MODEL,
        analysis_model=GROK_ANALYSIS_MODEL,
    )
