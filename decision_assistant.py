#!/usr/bin/env python3
"""
Alpha FX Hub — Gold Decision Assistant v1.0
============================================
Semi-automated XAUUSD decision support system.
NOT auto-trading. YOU make every trade decision.

Components:
  A. Market Bias Engine — continuous structure analysis
  B. Smart Entry Zone — defines entry/SL/TP when setup exists
  C. Telegram Alerts — only when price APPROACHES a zone
  D. Trade Manager — tracks your manual trades, suggests management

Run: python3 decision_assistant.py
"""

import os
import sys
import time
import json
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ============================================================================
# SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("decision_assistant")

# Load .env
def load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()

# ============================================================================
# CONFIGURATION
# ============================================================================

SYMBOL = "XAUUSD"
PIP = 0.1

# API Keys
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_PRIVATE_CHANNEL_ID", "")

# Sessions (UTC)
SESSIONS = {
    "LONDON": (7, 10),
    "NY": (12, 15),
    "LN_OVERLAP": (12, 16),
}

# Alert distance: trigger when price is within $ALERT_DISTANCE of entry zone
ALERT_DISTANCE = 1.0  # $1 from entry zone

# Scan interval
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "30"))

# Max setups per day
MAX_SETUPS_PER_DAY = 3


# ============================================================================
# DATA FETCHING
# ============================================================================

_price_cache = {}
_bars_cache = {}

def fetch_live_price() -> Optional[float]:
    """Fetch current XAUUSD price via Twelve Data."""
    cache_key = "live_price"
    if cache_key in _price_cache:
        ts, price = _price_cache[cache_key]
        if time.time() - ts < 10:
            return price

    if not TWELVE_DATA_KEY:
        log.warning("No TWELVE_DATA_API_KEY — cannot fetch live price")
        return None

    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": "XAU/USD", "apikey": TWELVE_DATA_KEY}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        price = float(data.get("price", 0))
        if price > 0:
            _price_cache[cache_key] = (time.time(), price)
            return price
    except Exception as e:
        log.error(f"Price fetch error: {e}")

    # Fallback: try MetaAPI
    try:
        meta_token = os.environ.get("METAAPI_TOKEN", "")
        meta_account = os.environ.get("METAAPI_ACCOUNT", "")
        if meta_token and meta_account:
            url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{meta_account}/symbols/XAUUSD/current-price"
            headers = {"auth-token": meta_token}
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            price = float(data.get("ask", 0))
            if price > 0:
                _price_cache[cache_key] = (time.time(), price)
                return price
    except Exception as e:
        log.debug(f"MetaAPI fallback failed: {e}")

    return None


def fetch_bars(interval: str = "15min", count: int = 200) -> Optional[pd.DataFrame]:
    """Fetch OHLCV bars from Twelve Data."""
    cache_key = f"bars_{interval}_{count}"
    if cache_key in _bars_cache:
        ts, df = _bars_cache[cache_key]
        if time.time() - ts < 30:
            return df

    if not TWELVE_DATA_KEY:
        return None

    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": "XAU/USD",
            "interval": interval,
            "outputsize": count,
            "apikey": TWELVE_DATA_KEY,
            "format": "JSON",
            "timezone": "UTC",
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if "values" not in data:
            log.error(f"Twelve Data error: {data.get('message', 'No values')}")
            return None

        rows = data["values"]
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["datetime"])
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("time").reset_index(drop=True)

        _bars_cache[cache_key] = (time.time(), df)
        return df
    except Exception as e:
        log.error(f"Bar fetch error: {e}")
        return None


# ============================================================================
# TELEGRAM NOTIFICATIONS
# ============================================================================

class TelegramAlerts:
    """Manages all Telegram notifications with anti-spam control."""

    def __init__(self, token: str, channel_id: str):
        self.token = token
        self.channel_id = channel_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_sent = {}  # key -> timestamp (anti-spam)

    def _can_send(self, key: str, cooldown_sec: int = 300) -> bool:
        """Anti-spam: only send same alert type every N seconds."""
        now = time.time()
        if key in self.last_sent and now - self.last_sent[key] < cooldown_sec:
            return False
        self.last_sent[key] = now
        return True

    def send(self, text: str, key: str = "", cooldown: int = 300) -> bool:
        """Send message with anti-spam check."""
        if not self.token or not self.channel_id:
            log.warning("Telegram not configured")
            return False

        if key and not self._can_send(key, cooldown):
            return False

        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.channel_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                log.info(f"Telegram sent: {key or 'alert'}")
                return True
            else:
                log.error(f"Telegram error {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            log.error(f"Telegram send failed: {e}")
            return False

    # ── ALERT TEMPLATES ──

    def approaching_zone(self, direction: str, bias: str, entry_low: float,
                         entry_high: float, current_price: float, sl: float,
                         tp1: float, tp2: float, tp3: float,
                         confidence: int, session: str):
        """Price is within $1 of entry zone."""
        emoji = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
        msg = (
            f"{emoji} <b>XAUUSD Approaching {direction} Zone</b>\n"
            f"\n"
            f"Bias: <b>{bias}</b>\n"
            f"Session: <b>{session}</b>\n"
            f"Entry: <b>${entry_low:.2f} – ${entry_high:.2f}</b>\n"
            f"Current Price: <b>${current_price:.2f}</b>\n"
            f"\n"
            f"SL: ${sl:.2f}\n"
            f"TP1: ${tp1:.2f}\n"
            f"TP2: ${tp2:.2f}\n"
            f"TP3: ${tp3:.2f}\n"
            f"Confidence: <b>{confidence}%</b>\n"
            f"\n"
            f"\u23f3 <i>Wait for confirmation candle</i>"
        )
        self.send(msg, key=f"approach_{direction}_{entry_low:.0f}", cooldown=600)

    def entry_zone_hit(self, direction: str, entry_low: float,
                       entry_high: float, current_price: float):
        """Price entered the zone."""
        emoji = "\U0001f3af"
        msg = (
            f"{emoji} <b>XAUUSD IN ENTRY ZONE</b>\n"
            f"\n"
            f"Direction: <b>{direction}</b>\n"
            f"Zone: ${entry_low:.2f} – ${entry_high:.2f}\n"
            f"Current: <b>${current_price:.2f}</b>\n"
            f"\n"
            f"\u26a0\ufe0f <i>Watch for confirmation — Do NOT auto trade</i>"
        )
        self.send(msg, key=f"inzone_{direction}_{entry_low:.0f}", cooldown=600)

    def trade_update(self, direction: str, entry: float, current: float,
                     pips: float, message: str, action: str):
        """Trade management update."""
        status_emoji = "\U0001f7e2" if pips > 0 else "\U0001f534"
        msg = (
            f"{status_emoji} <b>Trade Update — {direction} XAUUSD</b>\n"
            f"\n"
            f"Entry: ${entry:.2f}\n"
            f"Current: ${current:.2f}\n"
            f"P&L: <b>{pips:+.1f} pips</b>\n"
            f"\n"
            f"\U0001f4ca {message}\n"
            f"\n"
            f"\u27a1\ufe0f <b>Suggestion: {action}</b>"
        )
        self.send(msg, key=f"trade_update_{entry:.0f}", cooldown=120)

    def exit_suggestion(self, direction: str, entry: float, current: float,
                        pips: float, reason: str):
        """Suggest closing or reducing position."""
        msg = (
            f"\U0001f6a8 <b>EXIT SUGGESTION — {direction} XAUUSD</b>\n"
            f"\n"
            f"Entry: ${entry:.2f}\n"
            f"Current: ${current:.2f}\n"
            f"P&L: <b>{pips:+.1f} pips</b>\n"
            f"\n"
            f"Reason: <b>{reason}</b>\n"
            f"\n"
            f"\u26a0\ufe0f <i>Consider closing or reducing position</i>"
        )
        self.send(msg, key=f"exit_{entry:.0f}", cooldown=300)


# ============================================================================
# A. MARKET BIAS ENGINE
# ============================================================================

@dataclass
class MarketBias:
    bias: str = "NEUTRAL"       # BULLISH / BEARISH / NEUTRAL
    strength: str = "WEAK"       # STRONG / MODERATE / WEAK
    h1_structure: str = ""       # HH/HL or LH/LL
    key_high: float = 0.0
    key_low: float = 0.0
    liquidity_above: List[float] = field(default_factory=list)
    liquidity_below: List[float] = field(default_factory=list)
    pullback_zone_buy: Tuple[float, float] = (0, 0)
    pullback_zone_sell: Tuple[float, float] = (0, 0)
    ema50: float = 0.0
    ema200: float = 0.0
    atr: float = 0.0
    timestamp: str = ""


class BiasEngine:
    """Continuously analyzes XAUUSD market structure."""

    def analyze(self, m15_df: pd.DataFrame, h1_df: pd.DataFrame) -> MarketBias:
        """Full bias analysis from M15 + H1 data."""
        bias = MarketBias()
        bias.timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        if h1_df is None or len(h1_df) < 30:
            return bias

        # ATR
        h, l, c = h1_df["high"], h1_df["low"], h1_df["close"]
        tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
        bias.atr = tr.rolling(14).mean().iloc[-1]

        # EMAs
        bias.ema50 = h1_df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
        bias.ema200 = h1_df["close"].ewm(span=200, adjust=False).mean().iloc[-1]

        # H1 Swing Detection
        swing_highs, swing_lows = self._find_swings(h1_df, lookback=3)

        # Structure: HH/HL or LH/LL
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            sh1 = swing_highs[-1][1]
            sh2 = swing_highs[-2][1]
            sl1 = swing_lows[-1][1]
            sl2 = swing_lows[-2][1]

            hh = sh1 > sh2
            hl = sl1 > sl2
            lh = sh1 < sh2
            ll = sl1 < sl2

            if hh and hl:
                bias.bias = "BULLISH"
                bias.h1_structure = "HH/HL"
            elif lh and ll:
                bias.bias = "BEARISH"
                bias.h1_structure = "LH/LL"
            else:
                bias.bias = "NEUTRAL"
                bias.h1_structure = "RANGE"

            bias.key_high = sh1
            bias.key_low = sl1

        # Strength from EMA alignment
        price = h1_df["close"].iloc[-1]
        if bias.bias == "BULLISH" and price > bias.ema50 > bias.ema200:
            bias.strength = "STRONG"
        elif bias.bias == "BEARISH" and price < bias.ema50 < bias.ema200:
            bias.strength = "STRONG"
        elif bias.bias != "NEUTRAL":
            bias.strength = "MODERATE"
        else:
            bias.strength = "WEAK"

        # Liquidity levels (swing highs above price = sell-side, swing lows below = buy-side)
        current_price = price
        bias.liquidity_above = sorted([p for _, p in swing_highs if p > current_price])[:5]
        bias.liquidity_below = sorted([p for _, p in swing_lows if p < current_price], reverse=True)[:5]

        # Pullback zones (using Fibonacci 0.5-0.618 of last swing)
        if len(swing_highs) >= 1 and len(swing_lows) >= 1:
            recent_high = swing_highs[-1][1]
            recent_low = swing_lows[-1][1]
            swing_range = recent_high - recent_low

            if bias.bias == "BULLISH" and swing_range > 0:
                # Buy pullback zone: 50-61.8% retrace from recent swing low to high
                pb_high = recent_high - swing_range * 0.5
                pb_low = recent_high - swing_range * 0.618
                bias.pullback_zone_buy = (round(pb_low, 2), round(pb_high, 2))

            elif bias.bias == "BEARISH" and swing_range > 0:
                # Sell pullback zone: 50-61.8% retrace from recent swing high to low
                pb_low = recent_low + swing_range * 0.5
                pb_high = recent_low + swing_range * 0.618
                bias.pullback_zone_sell = (round(pb_low, 2), round(pb_high, 2))

        return bias

    def _find_swings(self, df, lookback=3):
        highs, lows = [], []
        for i in range(lookback, len(df) - lookback):
            h = df.iloc[i]["high"]
            l = df.iloc[i]["low"]
            if all(h > df.iloc[j]["high"] for j in range(i-lookback, i)) and \
               all(h > df.iloc[j]["high"] for j in range(i+1, i+lookback+1)):
                highs.append((df.index[i], h))
            if all(l < df.iloc[j]["low"] for j in range(i-lookback, i)) and \
               all(l < df.iloc[j]["low"] for j in range(i+1, i+lookback+1)):
                lows.append((df.index[i], l))
        return highs, lows


# ============================================================================
# B. SMART ENTRY ZONE DETECTOR
# ============================================================================

@dataclass
class EntryZone:
    direction: str = ""          # BUY / SELL
    entry_low: float = 0.0       # Bottom of entry zone
    entry_high: float = 0.0      # Top of entry zone
    sl: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    rr_ratio: float = 0.0       # Risk:Reward at TP1
    confidence: int = 0          # 0-100
    reason: str = ""             # Why this zone
    session: str = ""
    valid_until: str = ""        # Expiry time
    triggered: bool = False
    entered: bool = False


class EntryZoneDetector:
    """Detects high-quality entry zones based on liquidity sweep + pullback."""

    def detect(self, m15_df: pd.DataFrame, h1_df: pd.DataFrame,
               bias: MarketBias, current_price: float) -> Optional[EntryZone]:
        """
        Returns an EntryZone if a valid setup exists, None otherwise.
        Strict filters: structure + session + sweep + quality.
        """
        if bias.bias == "NEUTRAL" or bias.strength == "WEAK":
            return None

        now = datetime.now(timezone.utc)
        hour = now.hour

        # Session filter: London or NY only
        session = None
        for name, (start, end) in SESSIONS.items():
            if start <= hour < end:
                session = name
                break
        if session is None:
            return None

        if m15_df is None or len(m15_df) < 50:
            return None

        atr = bias.atr
        if atr < 1.0:
            return None

        # M15 swing detection for liquidity levels
        m15_swings_h, m15_swings_l = self._find_m15_swings(m15_df)

        if bias.bias == "BULLISH":
            return self._detect_buy_zone(
                m15_df, bias, current_price, atr, m15_swings_l, session, now
            )
        elif bias.bias == "BEARISH":
            return self._detect_sell_zone(
                m15_df, bias, current_price, atr, m15_swings_h, session, now
            )

        return None

    def _detect_buy_zone(self, m15_df, bias, price, atr, swing_lows, session, now):
        """Detect a BUY entry zone from liquidity sweep of M15 swing low."""
        if not swing_lows:
            return None

        # Find recent swing lows that could have been swept
        for sw_idx, sw_price in swing_lows[-8:]:
            # Has price swept below this level recently? (wick below, close above)
            recent = m15_df.tail(10)
            swept = False
            sweep_wick_low = None

            for _, bar in recent.iterrows():
                if bar["low"] < sw_price and bar["close"] > sw_price:
                    swept = True
                    sweep_wick_low = bar["low"]
                    break

            if not swept:
                # Check if price is approaching this level (within pullback zone)
                if bias.pullback_zone_buy[0] > 0:
                    pb_low, pb_high = bias.pullback_zone_buy
                    if pb_low <= price <= pb_high + ALERT_DISTANCE:
                        # Price is in pullback zone — create entry zone around it
                        entry_low = pb_low
                        entry_high = pb_high
                        sl = entry_low - atr * 1.2
                        sweep_wick_low = entry_low
                    else:
                        continue
                else:
                    continue
            else:
                # Swept: entry zone is the sweep area
                entry_low = sw_price - atr * 0.1
                entry_high = sw_price + atr * 0.3
                sl = sweep_wick_low - atr * 0.3

            # SL constraints
            sl_pips = (entry_low - sl) / PIP
            sl_pips = max(15, min(60, sl_pips))
            sl = entry_low - sl_pips * PIP

            # TPs: conservative
            tp1 = entry_high + sl_pips * PIP * 1.5  # 1.5R
            tp2 = entry_high + sl_pips * PIP * 2.5  # 2.5R
            tp3 = entry_high + sl_pips * PIP * 3.5  # 3.5R

            rr = 1.5  # At TP1

            # Confidence scoring
            confidence = 0
            confidence += 20 if bias.strength == "STRONG" else 10
            confidence += 15 if session == "LONDON" else 10
            confidence += 15 if swept else 5
            confidence += 10 if price > bias.ema50 else 0
            confidence += 10 if atr > 3 else 5
            # Proximity to Fib level
            if bias.pullback_zone_buy[0] > 0:
                pb_low, pb_high = bias.pullback_zone_buy
                if pb_low <= price <= pb_high:
                    confidence += 20

            confidence = min(95, confidence)

            if confidence < 50:
                continue

            reason = f"{'Swept' if swept else 'Pullback to'} M15 swing low ${sw_price:.2f}"
            if bias.pullback_zone_buy[0] > 0:
                reason += f" | Fib OTE zone"

            return EntryZone(
                direction="BUY",
                entry_low=round(entry_low, 2),
                entry_high=round(entry_high, 2),
                sl=round(sl, 2),
                tp1=round(tp1, 2),
                tp2=round(tp2, 2),
                tp3=round(tp3, 2),
                rr_ratio=round(rr, 1),
                confidence=confidence,
                reason=reason,
                session=session,
                valid_until=(now + timedelta(hours=2)).strftime("%H:%M UTC"),
            )

        return None

    def _detect_sell_zone(self, m15_df, bias, price, atr, swing_highs, session, now):
        """Detect a SELL entry zone from liquidity sweep of M15 swing high."""
        if not swing_highs:
            return None

        for sw_idx, sw_price in swing_highs[-8:]:
            recent = m15_df.tail(10)
            swept = False
            sweep_wick_high = None

            for _, bar in recent.iterrows():
                if bar["high"] > sw_price and bar["close"] < sw_price:
                    swept = True
                    sweep_wick_high = bar["high"]
                    break

            if not swept:
                if bias.pullback_zone_sell[0] > 0:
                    pb_low, pb_high = bias.pullback_zone_sell
                    if pb_low - ALERT_DISTANCE <= price <= pb_high:
                        entry_low = pb_low
                        entry_high = pb_high
                        sl = entry_high + atr * 1.2
                        sweep_wick_high = entry_high
                    else:
                        continue
                else:
                    continue
            else:
                entry_low = sw_price - atr * 0.3
                entry_high = sw_price + atr * 0.1
                sl = sweep_wick_high + atr * 0.3

            sl_pips = (sl - entry_high) / PIP
            sl_pips = max(15, min(60, sl_pips))
            sl = entry_high + sl_pips * PIP

            tp1 = entry_low - sl_pips * PIP * 1.5
            tp2 = entry_low - sl_pips * PIP * 2.5
            tp3 = entry_low - sl_pips * PIP * 3.5

            rr = 1.5

            confidence = 0
            confidence += 20 if bias.strength == "STRONG" else 10
            confidence += 15 if session == "LONDON" else 10
            confidence += 15 if swept else 5
            confidence += 10 if price < bias.ema50 else 0
            confidence += 10 if atr > 3 else 5
            if bias.pullback_zone_sell[0] > 0:
                pb_low, pb_high = bias.pullback_zone_sell
                if pb_low <= price <= pb_high:
                    confidence += 20

            confidence = min(95, confidence)
            if confidence < 50:
                continue

            reason = f"{'Swept' if swept else 'Pullback to'} M15 swing high ${sw_price:.2f}"
            if bias.pullback_zone_sell[0] > 0:
                reason += f" | Fib OTE zone"

            return EntryZone(
                direction="SELL",
                entry_low=round(entry_low, 2),
                entry_high=round(entry_high, 2),
                sl=round(sl, 2),
                tp1=round(tp1, 2),
                tp2=round(tp2, 2),
                tp3=round(tp3, 2),
                rr_ratio=round(rr, 1),
                confidence=confidence,
                reason=reason,
                session=session,
                valid_until=(now + timedelta(hours=2)).strftime("%H:%M UTC"),
            )

        return None

    def _find_m15_swings(self, df, lookback=4):
        highs, lows = [], []
        for i in range(lookback, len(df) - lookback):
            h = df.iloc[i]["high"]
            l = df.iloc[i]["low"]
            if all(h > df.iloc[j]["high"] for j in range(i-lookback, i)) and \
               all(h > df.iloc[j]["high"] for j in range(i+1, i+lookback+1)):
                highs.append((df.index[i], h))
            if all(l < df.iloc[j]["low"] for j in range(i-lookback, i)) and \
               all(l < df.iloc[j]["low"] for j in range(i+1, i+lookback+1)):
                lows.append((df.index[i], l))
        return highs, lows


# ============================================================================
# D. TRADE MANAGER (Manual Trade Tracking + Suggestions)
# ============================================================================

@dataclass
class ActiveTrade:
    direction: str
    entry_price: float
    sl: float
    original_sl: float
    tp1: float
    tp2: float
    tp3: float
    opened_at: str
    sl_moved_to_be: bool = False
    tp1_hit: bool = False
    tp2_hit: bool = False
    partial_closed: float = 0.0  # % already closed


class TradeAdvisor:
    """Tracks your manual trades and provides management suggestions."""

    def __init__(self, telegram: TelegramAlerts):
        self.active_trade: Optional[ActiveTrade] = None
        self.telegram = telegram
        self.last_suggestion_time = 0

    def open_trade(self, direction: str, entry_price: float,
                   sl: float, tp1: float, tp2: float, tp3: float):
        """Register a manually opened trade."""
        self.active_trade = ActiveTrade(
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            original_sl=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            opened_at=datetime.now(timezone.utc).strftime("%H:%M UTC"),
        )
        log.info(f"Trade registered: {direction} @ {entry_price}")

    def close_trade(self):
        """Mark trade as closed."""
        self.active_trade = None
        log.info("Trade closed")

    def check(self, current_price: float, bias: MarketBias) -> Optional[str]:
        """
        Check active trade against current price and market conditions.
        Returns suggestion text or None.
        """
        if not self.active_trade:
            return None

        trade = self.active_trade
        entry = trade.entry_price

        if trade.direction == "BUY":
            pips = (current_price - entry) / PIP
        else:
            pips = (entry - current_price) / PIP

        # ── TP1 HIT — Move SL to Breakeven ──
        if not trade.tp1_hit:
            if trade.direction == "BUY" and current_price >= trade.tp1:
                trade.tp1_hit = True
                trade.sl = entry + 1 * PIP  # BE + buffer
                trade.sl_moved_to_be = True
                msg = "TP1 hit! SL moved to breakeven"
                action = "Close 50% — Move SL to BE"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

            elif trade.direction == "SELL" and current_price <= trade.tp1:
                trade.tp1_hit = True
                trade.sl = entry - 1 * PIP
                trade.sl_moved_to_be = True
                msg = "TP1 hit! SL moved to breakeven"
                action = "Close 50% — Move SL to BE"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

        # ── TP2 HIT ──
        if trade.tp1_hit and not trade.tp2_hit:
            if trade.direction == "BUY" and current_price >= trade.tp2:
                trade.tp2_hit = True
                trade.sl = trade.tp1  # Lock TP1 profit
                msg = "TP2 hit! SL moved to TP1 level"
                action = "Close 30% more — Trail SL to TP1"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

            elif trade.direction == "SELL" and current_price <= trade.tp2:
                trade.tp2_hit = True
                trade.sl = trade.tp1
                msg = "TP2 hit! SL moved to TP1 level"
                action = "Close 30% more — Trail SL to TP1"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

        # ── TP3 HIT — Full Close ──
        if trade.tp2_hit:
            if trade.direction == "BUY" and current_price >= trade.tp3:
                msg = "TP3 reached! Full target achieved"
                action = "Close remaining position — Full profit"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

            elif trade.direction == "SELL" and current_price <= trade.tp3:
                msg = "TP3 reached! Full target achieved"
                action = "Close remaining position — Full profit"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
                return action

        # ── STRUCTURE CHANGE WARNING ──
        # If bias flips against trade direction
        if trade.direction == "BUY" and bias.bias == "BEARISH":
            if time.time() - self.last_suggestion_time > 300:
                self.last_suggestion_time = time.time()
                reason = f"Bearish CHoCH detected — H1 structure now {bias.h1_structure}"
                self.telegram.exit_suggestion(
                    trade.direction, entry, current_price, pips, reason
                )
                if trade.tp1_hit:
                    return "Close remaining — Structure changed against you"
                else:
                    return "Consider closing — Structure changed against you"

        elif trade.direction == "SELL" and bias.bias == "BULLISH":
            if time.time() - self.last_suggestion_time > 300:
                self.last_suggestion_time = time.time()
                reason = f"Bullish CHoCH detected — H1 structure now {bias.h1_structure}"
                self.telegram.exit_suggestion(
                    trade.direction, entry, current_price, pips, reason
                )
                if trade.tp1_hit:
                    return "Close remaining — Structure changed against you"
                else:
                    return "Consider closing — Structure changed against you"

        # ── RUNNING TRADE UPDATE (every 5 min) ──
        if time.time() - self.last_suggestion_time > 300:
            self.last_suggestion_time = time.time()
            if pips > 0:
                target = trade.tp1 if not trade.tp1_hit else (trade.tp2 if not trade.tp2_hit else trade.tp3)
                if trade.direction == "BUY":
                    pips_to_target = (target - current_price) / PIP
                else:
                    pips_to_target = (current_price - target) / PIP

                msg = f"Trade running +{pips:.0f} pips"
                action = f"Hold — {pips_to_target:.0f} pips to next target"
                self.telegram.trade_update(
                    trade.direction, entry, current_price, pips, msg, action
                )
            elif pips < -20:
                msg = f"Trade in drawdown {pips:.0f} pips"
                action = "Monitor closely — SL will protect if price continues"
                # Don't send negative updates to Telegram to avoid panic
                # Just log locally

        return None


# ============================================================================
# MAIN LOOP
# ============================================================================

class DecisionAssistant:
    """Main orchestrator — ties bias, zones, alerts, and trade management."""

    def __init__(self):
        self.telegram = TelegramAlerts(TELEGRAM_TOKEN, TELEGRAM_CHANNEL)
        self.bias_engine = BiasEngine()
        self.zone_detector = EntryZoneDetector()
        self.trade_advisor = TradeAdvisor(self.telegram)

        self.current_bias: Optional[MarketBias] = None
        self.current_zone: Optional[EntryZone] = None
        self.zones_today = 0
        self.last_zone_date = None

        # State file for trade persistence
        self.state_file = Path(__file__).parent / "data" / "assistant_state.json"

    def run_once(self) -> Dict:
        """Single analysis cycle. Returns status dict."""
        now = datetime.now(timezone.utc)
        status = {"time": now.strftime("%H:%M:%S UTC"), "actions": []}

        # Reset daily counter
        if self.last_zone_date != now.date():
            self.zones_today = 0
            self.last_zone_date = now.date()

        # Fetch data
        price = fetch_live_price()
        if price is None:
            status["error"] = "Cannot fetch price"
            return status

        m15 = fetch_bars("15min", 200)
        h1 = fetch_bars("1h", 100)

        status["price"] = price

        # A. Market Bias
        self.current_bias = self.bias_engine.analyze(m15, h1)
        status["bias"] = self.current_bias.bias
        status["strength"] = self.current_bias.strength
        status["structure"] = self.current_bias.h1_structure

        # B. Entry Zone Detection (max 3/day)
        if self.zones_today < MAX_SETUPS_PER_DAY:
            zone = self.zone_detector.detect(m15, h1, self.current_bias, price)
            if zone and zone.confidence >= 50:
                self.current_zone = zone
                status["zone"] = asdict(zone)
                status["actions"].append(f"New {zone.direction} zone: ${zone.entry_low}-${zone.entry_high}")
        else:
            status["actions"].append("Max setups for today reached")

        # C. Zone Proximity Alerts
        if self.current_zone and not self.current_zone.entered:
            zone = self.current_zone
            in_zone = False
            approaching = False

            if zone.direction == "BUY":
                if zone.entry_low <= price <= zone.entry_high:
                    in_zone = True
                elif zone.entry_low - ALERT_DISTANCE <= price <= zone.entry_high + ALERT_DISTANCE:
                    approaching = True

            elif zone.direction == "SELL":
                if zone.entry_low <= price <= zone.entry_high:
                    in_zone = True
                elif zone.entry_low - ALERT_DISTANCE <= price <= zone.entry_high + ALERT_DISTANCE:
                    approaching = True

            if in_zone:
                self.telegram.entry_zone_hit(
                    zone.direction, zone.entry_low, zone.entry_high, price
                )
                self.current_zone.entered = True
                self.zones_today += 1
                status["actions"].append(f"ENTRY ZONE HIT — {zone.direction}")

            elif approaching:
                self.telegram.approaching_zone(
                    zone.direction, self.current_bias.bias,
                    zone.entry_low, zone.entry_high, price,
                    zone.sl, zone.tp1, zone.tp2, zone.tp3,
                    zone.confidence,
                    zone.session
                )
                self.current_zone.triggered = True
                status["actions"].append(f"APPROACHING — {zone.direction} zone")

        # D. Trade Management
        suggestion = self.trade_advisor.check(price, self.current_bias)
        if suggestion:
            status["trade_suggestion"] = suggestion
            status["actions"].append(f"Trade: {suggestion}")

        return status

    def run_loop(self):
        """Continuous monitoring loop."""
        print(f"\n{'='*60}")
        print(f"  Alpha FX Hub — Gold Decision Assistant v1.0")
        print(f"  XAUUSD | Semi-Automated | NOT Auto-Trading")
        print(f"{'='*60}")
        print(f"  Telegram: {'configured' if TELEGRAM_TOKEN else 'NOT configured'}")
        print(f"  Price Feed: {'Twelve Data' if TWELVE_DATA_KEY else 'NOT configured'}")
        print(f"  Scan Interval: {SCAN_INTERVAL}s")
        print(f"  Max Setups/Day: {MAX_SETUPS_PER_DAY}")
        print(f"  Alert Distance: ${ALERT_DISTANCE}")
        print(f"{'='*60}\n")

        if not TWELVE_DATA_KEY:
            print("ERROR: Set TWELVE_DATA_API_KEY in .env to use live price feed")
            sys.exit(1)

        print("Commands (type while running):")
        print("  BUY <price>  — Register manual buy trade")
        print("  SELL <price> — Register manual sell trade")
        print("  CLOSE        — Close active trade")
        print("  STATUS       — Show current analysis")
        print("  QUIT         — Exit\n")

        import threading
        import select

        # Input handler thread
        self._running = True
        self._command_queue = []

        def input_thread():
            while self._running:
                try:
                    if sys.stdin.readable():
                        line = input().strip()
                        if line:
                            self._command_queue.append(line)
                except (EOFError, KeyboardInterrupt):
                    break

        # Start input thread
        t = threading.Thread(target=input_thread, daemon=True)
        t.start()

        try:
            while self._running:
                # Process commands
                while self._command_queue:
                    cmd = self._command_queue.pop(0)
                    self._handle_command(cmd)

                # Run analysis
                status = self.run_once()
                self._print_status(status)

                time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self._running = False

    def _handle_command(self, cmd: str):
        """Handle user commands."""
        parts = cmd.upper().split()
        if not parts:
            return

        if parts[0] in ("BUY", "SELL") and len(parts) >= 2:
            try:
                entry_price = float(parts[1])
                direction = parts[0]

                # Use current zone's SL/TP if available
                if self.current_zone and self.current_zone.direction == direction:
                    z = self.current_zone
                    self.trade_advisor.open_trade(
                        direction, entry_price, z.sl, z.tp1, z.tp2, z.tp3
                    )
                    print(f"\n  Trade registered: {direction} @ ${entry_price:.2f}")
                    print(f"  SL: ${z.sl:.2f} | TP1: ${z.tp1:.2f} | TP2: ${z.tp2:.2f} | TP3: ${z.tp3:.2f}")
                else:
                    # No zone — use ATR-based defaults
                    atr = self.current_bias.atr if self.current_bias else 5.0
                    if direction == "BUY":
                        sl = entry_price - atr * 1.5
                        tp1 = entry_price + atr * 2.0
                        tp2 = entry_price + atr * 3.5
                        tp3 = entry_price + atr * 5.0
                    else:
                        sl = entry_price + atr * 1.5
                        tp1 = entry_price - atr * 2.0
                        tp2 = entry_price - atr * 3.5
                        tp3 = entry_price - atr * 5.0

                    self.trade_advisor.open_trade(direction, entry_price, sl, tp1, tp2, tp3)
                    print(f"\n  Trade registered: {direction} @ ${entry_price:.2f}")
                    print(f"  SL: ${sl:.2f} | TP1: ${tp1:.2f} | TP2: ${tp2:.2f} | TP3: ${tp3:.2f}")

            except ValueError:
                print(f"  Invalid price: {parts[1]}")

        elif parts[0] == "CLOSE":
            self.trade_advisor.close_trade()
            print("  Trade closed")

        elif parts[0] == "STATUS":
            self._print_full_status()

        elif parts[0] == "QUIT":
            self._running = False

    def _print_status(self, status: Dict):
        """Print compact status line."""
        price = status.get("price", 0)
        bias = status.get("bias", "?")
        strength = status.get("strength", "?")
        t = status.get("time", "")

        # Compact one-liner
        bias_icon = {"BULLISH": "\u2191", "BEARISH": "\u2193", "NEUTRAL": "\u2194"}.get(bias, "?")
        trade_str = ""
        if self.trade_advisor.active_trade:
            tr = self.trade_advisor.active_trade
            if tr.direction == "BUY":
                pips = (price - tr.entry_price) / PIP
            else:
                pips = (tr.entry_price - price) / PIP
            trade_str = f" | Trade: {tr.direction} {pips:+.0f}p"

        zone_str = ""
        if self.current_zone and not self.current_zone.entered:
            z = self.current_zone
            zone_str = f" | Zone: {z.direction} ${z.entry_low:.0f}-${z.entry_high:.0f} ({z.confidence}%)"

        actions = status.get("actions", [])
        action_str = f" | {actions[0]}" if actions else ""

        print(f"  [{t}] ${price:.2f} {bias_icon}{bias} ({strength}){zone_str}{trade_str}{action_str}")

    def _print_full_status(self):
        """Print detailed current analysis."""
        print(f"\n{'='*50}")
        print(f"  CURRENT ANALYSIS")
        print(f"{'='*50}")

        if self.current_bias:
            b = self.current_bias
            print(f"  Bias:       {b.bias} ({b.strength})")
            print(f"  Structure:  {b.h1_structure}")
            print(f"  Key High:   ${b.key_high:.2f}")
            print(f"  Key Low:    ${b.key_low:.2f}")
            print(f"  EMA50:      ${b.ema50:.2f}")
            print(f"  EMA200:     ${b.ema200:.2f}")
            print(f"  ATR(H1):    ${b.atr:.2f}")
            if b.liquidity_above:
                print(f"  Liq Above:  {', '.join(f'${p:.2f}' for p in b.liquidity_above[:3])}")
            if b.liquidity_below:
                print(f"  Liq Below:  {', '.join(f'${p:.2f}' for p in b.liquidity_below[:3])}")

        if self.current_zone:
            z = self.current_zone
            print(f"\n  Active Zone: {z.direction}")
            print(f"  Entry:  ${z.entry_low:.2f} – ${z.entry_high:.2f}")
            print(f"  SL:     ${z.sl:.2f}")
            print(f"  TP1:    ${z.tp1:.2f} | TP2: ${z.tp2:.2f} | TP3: ${z.tp3:.2f}")
            print(f"  R:R:    1:{z.rr_ratio}")
            print(f"  Conf:   {z.confidence}%")
            print(f"  Reason: {z.reason}")
            print(f"  Valid:  {z.valid_until}")

        if self.trade_advisor.active_trade:
            t = self.trade_advisor.active_trade
            print(f"\n  Active Trade: {t.direction} @ ${t.entry_price:.2f}")
            print(f"  SL: ${t.sl:.2f} | TP1: ${t.tp1:.2f}")
            print(f"  BE: {'Yes' if t.sl_moved_to_be else 'No'}")
            print(f"  TP1 Hit: {'Yes' if t.tp1_hit else 'No'}")

        print(f"  Setups Today: {self.zones_today}/{MAX_SETUPS_PER_DAY}")
        print(f"{'='*50}\n")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    assistant = DecisionAssistant()
    assistant.run_loop()


if __name__ == "__main__":
    main()
