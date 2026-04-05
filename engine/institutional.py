"""
Alpha FX Hub — Institutional Edge Modules
==========================================
Three institutional-grade overlays for the Gold Engine:

Module 18: COT Data + DXY Correlation
  - Fetches weekly CFTC Commitment of Traders data
  - Tracks commercial vs speculative positioning
  - DXY (US Dollar Index) inverse correlation filter
  - Score: -10 to +12

Module 19: Smart News Filter
  - Auto-detects upcoming high-impact events (NFP, FOMC, CPI)
  - Blocks/penalizes entries within danger windows
  - Score: -15 to +5 (mostly penalty-based)

Module 20: Volume Confirmation
  - Volume surge detection on breakouts
  - Accumulation/distribution pattern recognition
  - Climax volume reversal detection
  - Score: -5 to +10

These modules follow institutional money — not retail noise.
"""
import logging
import time
import json
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger("alpha_fx_hub.institutional")

# Cache directory
_CACHE_DIR = Path(__file__).parent.parent / "data" / "institutional_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════════
# MODULE 18: COT DATA + DXY CORRELATION
# ════════════════════════════════════════════════════════════════

class COTAnalyzer:
    """
    Fetches and analyzes CFTC Commitment of Traders data for Gold futures.

    What institutions tell us:
    - Commercials (hedgers/producers): Smart money. When they go NET LONG,
      gold usually rallies. They HEDGE at extremes.
    - Large Speculators (hedge funds): Trend followers. Extreme positioning
      = potential reversal (crowded trade).
    - Small Speculators (retail): Usually wrong at extremes.

    DXY Correlation:
    - Gold has ~-0.80 correlation with USD Index
    - If DXY is falling → gold bullish bias
    - If DXY is rising → gold bearish bias
    """

    # CFTC COT report codes
    # Gold futures: 088691 (COMEX Gold)
    GOLD_CODE = "088691"

    # Cache COT data for 24 hours (reports are weekly anyway)
    CACHE_TTL = 86400

    def __init__(self):
        self._cot_cache = None
        self._cot_cache_time = 0
        self._dxy_cache = None
        self._dxy_cache_time = 0

    def fetch_cot_data(self) -> Optional[dict]:
        """
        Fetch latest COT data for Gold futures from CFTC.
        Uses the public CFTC API (no key needed).
        Returns positioning data or cached version.
        """
        now = time.time()
        if self._cot_cache and (now - self._cot_cache_time < self.CACHE_TTL):
            return self._cot_cache

        # Try cache file first
        cache_file = _CACHE_DIR / "cot_gold.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cached = json.load(f)
                if now - cached.get("fetched_at", 0) < self.CACHE_TTL:
                    self._cot_cache = cached
                    self._cot_cache_time = now
                    return cached
            except Exception:
                pass

        try:
            # CFTC Disaggregated Futures API (public, no key)
            url = (
                "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"
                f"?cftc_commodity_code={self.GOLD_CODE}"
                "&$order=report_date_as_yyyy_mm_dd DESC"
                "&$limit=8"
            )
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"COT fetch failed: {resp.status_code}")
                return self._cot_cache or self._get_fallback_cot()

            rows = resp.json()
            if not rows:
                return self._cot_cache or self._get_fallback_cot()

            latest = rows[0]
            previous = rows[1] if len(rows) > 1 else latest
            oldest = rows[-1] if len(rows) > 4 else rows[0]

            # Extract positioning
            # Managed Money (hedge funds/speculators)
            mm_long = int(latest.get("m_money_positions_long_all", 0))
            mm_short = int(latest.get("m_money_positions_short_all", 0))
            mm_net = mm_long - mm_short

            # Previous week
            mm_long_prev = int(previous.get("m_money_positions_long_all", 0))
            mm_short_prev = int(previous.get("m_money_positions_short_all", 0))
            mm_net_prev = mm_long_prev - mm_short_prev

            # Producer/Merchant (commercials — the smart money)
            prod_long = int(latest.get("prod_merc_positions_long_all", 0))
            prod_short = int(latest.get("prod_merc_positions_short_all", 0))
            prod_net = prod_long - prod_short

            prod_long_prev = int(previous.get("prod_merc_positions_long_all", 0))
            prod_short_prev = int(previous.get("prod_merc_positions_short_all", 0))
            prod_net_prev = prod_long_prev - prod_short_prev

            # Swap Dealers (institutional)
            swap_long = int(latest.get("swap_positions_long_all", 0))
            swap_short = int(latest.get("swap_positions_short_all", 0))
            swap_net = swap_long - swap_short

            # Open Interest
            oi = int(latest.get("open_interest_all", 0))
            oi_prev = int(previous.get("open_interest_all", 0))

            # Calculate net change (weekly shift)
            mm_change = mm_net - mm_net_prev
            prod_change = prod_net - prod_net_prev
            oi_change = oi - oi_prev

            # Historical range for extremes (use available weeks)
            mm_nets = []
            for r in rows:
                try:
                    ml = int(r.get("m_money_positions_long_all", 0))
                    ms = int(r.get("m_money_positions_short_all", 0))
                    mm_nets.append(ml - ms)
                except (ValueError, TypeError):
                    pass

            mm_percentile = 50
            if len(mm_nets) >= 4:
                mm_sorted = sorted(mm_nets)
                idx = mm_sorted.index(mm_net) if mm_net in mm_sorted else len(mm_sorted) // 2
                mm_percentile = int((idx / max(len(mm_sorted) - 1, 1)) * 100)

            result = {
                "report_date": latest.get("report_date_as_yyyy_mm_dd", ""),
                "managed_money_net": mm_net,
                "managed_money_change": mm_change,
                "managed_money_long": mm_long,
                "managed_money_short": mm_short,
                "producer_net": prod_net,
                "producer_change": prod_change,
                "swap_net": swap_net,
                "open_interest": oi,
                "oi_change": oi_change,
                "mm_percentile": mm_percentile,
                "fetched_at": now,
                "source": "cftc_api",
            }

            # Cache to file
            try:
                with open(cache_file, "w") as f:
                    json.dump(result, f, indent=2)
            except Exception:
                pass

            self._cot_cache = result
            self._cot_cache_time = now
            return result

        except Exception as e:
            logger.error(f"COT data fetch error: {e}")
            return self._cot_cache or self._get_fallback_cot()

    def _get_fallback_cot(self) -> dict:
        """Neutral fallback when COT data unavailable."""
        return {
            "managed_money_net": 0,
            "managed_money_change": 0,
            "producer_net": 0,
            "producer_change": 0,
            "swap_net": 0,
            "open_interest": 0,
            "oi_change": 0,
            "mm_percentile": 50,
            "source": "fallback",
        }

    def fetch_dxy_trend(self, td_api_key: str = "") -> Optional[dict]:
        """
        Fetch DXY (US Dollar Index) trend from Twelve Data.
        Gold correlation: ~-0.80 with DXY.
        """
        now = time.time()
        if self._dxy_cache and (now - self._dxy_cache_time < 3600):
            return self._dxy_cache

        if not td_api_key:
            return {"trend": "neutral", "change_pct": 0, "source": "no_key"}

        try:
            url = (
                f"https://api.twelvedata.com/time_series"
                f"?symbol=DXY&interval=4h&outputsize=50&apikey={td_api_key}"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return self._dxy_cache or {"trend": "neutral", "change_pct": 0}

            data = resp.json()
            values = data.get("values", [])
            if not values or len(values) < 10:
                return self._dxy_cache or {"trend": "neutral", "change_pct": 0}

            # Latest close vs 20-period SMA
            closes = [float(v["close"]) for v in values[:20]]
            current = closes[0]
            sma20 = sum(closes) / len(closes)

            # 5-period momentum
            recent_5 = closes[:5]
            momentum = (recent_5[0] - recent_5[-1]) / recent_5[-1] * 100

            # Trend determination
            if current > sma20 and momentum > 0.1:
                trend = "rising"           # DXY up → gold bearish
            elif current < sma20 and momentum < -0.1:
                trend = "falling"          # DXY down → gold bullish
            elif abs(momentum) < 0.05:
                trend = "flat"
            else:
                trend = "mixed"

            # Daily change
            day_change = (closes[0] - closes[min(6, len(closes)-1)]) / closes[min(6, len(closes)-1)] * 100

            result = {
                "trend": trend,
                "current": current,
                "sma20": round(sma20, 3),
                "momentum_pct": round(momentum, 3),
                "day_change_pct": round(day_change, 3),
                "source": "twelve_data",
            }

            self._dxy_cache = result
            self._dxy_cache_time = now
            return result

        except Exception as e:
            logger.error(f"DXY fetch error: {e}")
            return self._dxy_cache or {"trend": "neutral", "change_pct": 0}


def score_cot_dxy(direction: str, cot_data: dict = None, dxy_data: dict = None) -> dict:
    """
    MODULE 18: Score based on institutional positioning + DXY correlation.

    Score range: -10 to +12

    Logic:
    - COT managed money heavily long + BUY direction = bullish confirmation (+5)
    - COT managed money heavily long + SELL direction = contrarian warning (-5)
    - COT extreme positioning (>90th percentile) = reversal risk (-5 to -10)
    - Producers (commercials) shifting = smart money signal (+3 to +5)
    - DXY falling + BUY gold = confirmation (+4)
    - DXY rising + SELL gold = confirmation (+4)
    - DXY opposed to direction = penalty (-3)
    """
    score = 0
    notes = []

    if cot_data is None:
        cot_data = {}
    if dxy_data is None:
        dxy_data = {}

    is_buy = direction == "BUY"

    # ── COT Positioning Analysis ──
    mm_net = cot_data.get("managed_money_net", 0)
    mm_change = cot_data.get("managed_money_change", 0)
    prod_change = cot_data.get("producer_change", 0)
    mm_percentile = cot_data.get("mm_percentile", 50)
    oi_change = cot_data.get("oi_change", 0)

    if cot_data.get("source") != "fallback":
        # 1. Managed Money direction alignment
        if mm_net > 0 and is_buy:
            score += 4
            notes.append(f"Hedge funds NET LONG ({mm_net:+,} contracts) — confirms BUY")
        elif mm_net < 0 and not is_buy:
            score += 4
            notes.append(f"Hedge funds NET SHORT ({mm_net:+,} contracts) — confirms SELL")
        elif mm_net > 0 and not is_buy:
            score -= 3
            notes.append(f"Warning: Hedge funds NET LONG but signal is SELL (contrarian)")
        elif mm_net < 0 and is_buy:
            score -= 3
            notes.append(f"Warning: Hedge funds NET SHORT but signal is BUY (contrarian)")

        # 2. Weekly positioning change (momentum of institutional flow)
        if mm_change > 5000 and is_buy:
            score += 3
            notes.append(f"Funds added {mm_change:+,} longs this week — accumulating")
        elif mm_change < -5000 and not is_buy:
            score += 3
            notes.append(f"Funds cut {abs(mm_change):,} longs this week — liquidating")
        elif abs(mm_change) > 10000:
            # Big shift against direction
            if (mm_change > 0 and not is_buy) or (mm_change < 0 and is_buy):
                score -= 2
                notes.append(f"Institutional flow ({mm_change:+,}) opposes signal direction")

        # 3. Extreme positioning (contrarian signal)
        if mm_percentile >= 90:
            score -= 5
            notes.append(f"CAUTION: Spec positioning at {mm_percentile}th percentile — crowded long, reversal risk")
        elif mm_percentile <= 10:
            if is_buy:
                score += 3
                notes.append(f"Specs at {mm_percentile}th percentile — extreme bearish = contrarian BUY opportunity")

        # 4. Commercial (producer) smart money signal
        if prod_change > 3000 and is_buy:
            score += 2
            notes.append(f"Producers reducing hedges — bullish smart money signal")
        elif prod_change < -3000 and not is_buy:
            score += 2
            notes.append(f"Producers increasing hedges — bearish smart money signal")

        # 5. Open interest confirmation
        if oi_change > 10000 and mm_change > 0 and is_buy:
            score += 1
            notes.append(f"Rising OI + fund buying = new money entering long")
        elif oi_change < -10000 and mm_change < 0:
            notes.append(f"Falling OI + fund selling = long liquidation underway")

    # ── DXY Correlation ──
    dxy_trend = dxy_data.get("trend", "neutral")
    dxy_momentum = dxy_data.get("momentum_pct", 0)

    if dxy_trend != "neutral" and dxy_data.get("source") != "no_key":
        # Gold-DXY inverse correlation
        if dxy_trend == "falling" and is_buy:
            score += 4
            notes.append(f"DXY falling ({dxy_momentum:+.2f}%) — supports gold BUY")
        elif dxy_trend == "rising" and not is_buy:
            score += 4
            notes.append(f"DXY rising ({dxy_momentum:+.2f}%) — supports gold SELL")
        elif dxy_trend == "falling" and not is_buy:
            score -= 3
            notes.append(f"DXY falling but signal is SELL — USD weakness supports gold UP")
        elif dxy_trend == "rising" and is_buy:
            score -= 3
            notes.append(f"DXY rising but signal is BUY — USD strength pressures gold DOWN")
        elif dxy_trend == "flat":
            notes.append(f"DXY flat — no directional bias from USD")

    # Cap the score
    score = max(-10, min(12, score))

    return {
        "score": score,
        "notes": notes,
        "mm_net": mm_net,
        "mm_change": mm_change,
        "mm_percentile": mm_percentile,
        "dxy_trend": dxy_trend,
    }


# ════════════════════════════════════════════════════════════════
# MODULE 19: SMART NEWS FILTER
# ════════════════════════════════════════════════════════════════

# Events that can move gold $20-50+ in minutes
EXTREME_IMPACT_EVENTS = [
    "Fed Interest Rate Decision",
    "Interest Rate Decision",
    "Non Farm Payrolls",
    "FOMC Minutes",
    "Fed Chair Powell Speech",
]

HIGH_IMPACT_EVENTS = [
    "CPI", "Core CPI",
    "PPI", "Core PPI",
    "GDP Growth Rate",
    "PCE Price Index", "Core PCE Price Index",
    "Unemployment Rate",
    "Retail Sales",
    "ISM Manufacturing PMI",
    "ECB Interest Rate Decision",
]

# Time windows to avoid trading (in minutes before event)
DANGER_WINDOW_EXTREME = 60    # 1 hour before Fed/NFP
DANGER_WINDOW_HIGH = 30       # 30 min before CPI/GDP
POST_EVENT_COOLDOWN = 15      # 15 min after event (let dust settle)


def score_news_filter(events: list, direction: str) -> dict:
    """
    MODULE 19: Penalize or block entries near high-impact news events.

    Score range: -15 to +5

    Logic:
    - Event in next 60 min (extreme): -15 (HARD BLOCK — engine should reject)
    - Event in next 30 min (high):    -10 (strong penalty)
    - Event in next 2-4 hours:        -3 to -5 (mild caution)
    - No events next 4 hours:         +3 (clean window — safer entry)
    - Event just passed (15 min ago):  -5 (post-event volatility)
    - Event aligns with direction:     +2 bonus (post-data trade)
    """
    now = datetime.now(timezone.utc)
    score = 0
    notes = []
    danger_level = "CLEAR"  # CLEAR, CAUTION, DANGER, BLOCKED
    blocking_event = None

    if not events:
        score += 3
        notes.append("No calendar events loaded — clean window assumed")
        return {"score": score, "notes": notes, "danger_level": "CLEAR"}

    nearest_extreme_min = float("inf")
    nearest_high_min = float("inf")
    recent_event = None

    for evt in events:
        evt_name = evt.get("event", "")

        try:
            evt_time = datetime.fromisoformat(
                evt.get("time", "").replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        minutes_until = (evt_time - now).total_seconds() / 60
        importance = evt.get("importance", 1)

        # Check if this is an extreme or high impact event
        is_extreme = any(e.lower() in evt_name.lower() for e in EXTREME_IMPACT_EVENTS)
        is_high = any(e.lower() in evt_name.lower() for e in HIGH_IMPACT_EVENTS) or importance >= 3

        # ── UPCOMING EVENTS ──
        if minutes_until > 0:
            if is_extreme:
                nearest_extreme_min = min(nearest_extreme_min, minutes_until)

                if minutes_until <= DANGER_WINDOW_EXTREME:
                    score -= 15
                    danger_level = "BLOCKED"
                    blocking_event = evt_name
                    notes.append(
                        f"🚫 BLOCKED: {evt_name} in {int(minutes_until)} min — "
                        f"DO NOT ENTER. Expected $20-50 gold move."
                    )
                elif minutes_until <= 120:
                    score -= 5
                    if danger_level not in ("BLOCKED", "DANGER"):
                        danger_level = "DANGER"
                    notes.append(
                        f"⚠️ DANGER: {evt_name} in {int(minutes_until)} min — "
                        f"reduce position size or wait"
                    )
                elif minutes_until <= 240:
                    score -= 2
                    if danger_level == "CLEAR":
                        danger_level = "CAUTION"
                    notes.append(f"⏰ {evt_name} in {int(minutes_until/60):.1f}h — be cautious")

            elif is_high:
                nearest_high_min = min(nearest_high_min, minutes_until)

                if minutes_until <= DANGER_WINDOW_HIGH:
                    score -= 10
                    if danger_level not in ("BLOCKED",):
                        danger_level = "DANGER"
                    blocking_event = evt_name
                    notes.append(
                        f"⚠️ DANGER: {evt_name} in {int(minutes_until)} min — "
                        f"high volatility expected"
                    )
                elif minutes_until <= 120:
                    score -= 3
                    if danger_level == "CLEAR":
                        danger_level = "CAUTION"
                    notes.append(f"⏰ {evt_name} in {int(minutes_until/60):.1f}h — monitor closely")

        # ── RECENT EVENTS (just released) ──
        elif -POST_EVENT_COOLDOWN <= minutes_until <= 0:
            score -= 5
            if danger_level == "CLEAR":
                danger_level = "CAUTION"
            notes.append(
                f"📊 {evt_name} just released {int(abs(minutes_until))} min ago — "
                f"post-event volatility, wait for price to settle"
            )

            # Check if event result aligns with direction
            actual = evt.get("actual")
            forecast = evt.get("forecast")
            if actual and forecast:
                try:
                    act_val = float(str(actual).replace("%", "").replace("K", "000").strip())
                    fct_val = float(str(forecast).replace("%", "").replace("K", "000").strip())
                    beat = act_val > fct_val

                    # For gold: bad USD data = gold bullish, good USD data = gold bearish
                    country = evt.get("country", "").upper()
                    if "US" in country or "UNITED STATES" in country:
                        if beat and direction == "SELL":
                            score += 2
                            notes.append("Data beat → USD strong → supports gold SELL")
                        elif not beat and direction == "BUY":
                            score += 2
                            notes.append("Data missed → USD weak → supports gold BUY")
                except (ValueError, TypeError):
                    pass

    # Bonus for clean calendar
    if nearest_extreme_min > 240 and nearest_high_min > 120:
        if danger_level == "CLEAR":
            score += 3
            notes.append("✅ Clear calendar next 2-4 hours — safe trading window")

    # Cap score
    score = max(-15, min(5, score))

    return {
        "score": score,
        "notes": notes,
        "danger_level": danger_level,
        "blocking_event": blocking_event,
        "nearest_extreme_min": nearest_extreme_min if nearest_extreme_min < float("inf") else None,
        "nearest_high_min": nearest_high_min if nearest_high_min < float("inf") else None,
    }


# ════════════════════════════════════════════════════════════════
# MODULE 20: VOLUME CONFIRMATION
# ════════════════════════════════════════════════════════════════

def score_volume(df: pd.DataFrame, direction: str) -> dict:
    """
    MODULE 20: Confirm signals using volume analysis.

    Score range: -5 to +10

    Institutional volume patterns:
    1. Volume Surge Breakout (+5 to +8):
       Price breaks key level WITH 2x+ average volume = real breakout

    2. Accumulation Pattern (+3 to +5):
       Price consolidating with rising volume = institutions loading

    3. Low Volume Breakout (-3 to -5):
       Price breaks out but volume is below average = likely fakeout/trap

    4. Climax Volume Reversal Warning (-3):
       Extreme volume spike (3x+) at price extreme = potential exhaustion

    5. Volume-Price Divergence (-2 to +2):
       Price making new highs on declining volume = weakness
       Price making new lows on declining volume = selling exhaustion
    """
    score = 0
    notes = []

    if df is None or len(df) < 50:
        return {"score": 0, "notes": ["Insufficient data for volume analysis"]}

    # Ensure volume column exists and has data
    if "volume" not in df.columns:
        return {"score": 0, "notes": ["No volume data available"]}

    vol = df["volume"].astype(float)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # Skip if volume is all zeros (common with some forex feeds)
    if vol.tail(20).sum() == 0:
        return {"score": 0, "notes": ["Volume data not available from feed"]}

    current_vol = float(vol.iloc[-1])
    current_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])

    # Volume averages
    vol_sma20 = float(vol.tail(20).mean())
    vol_sma50 = float(vol.tail(50).mean()) if len(vol) >= 50 else vol_sma20
    vol_ratio = current_vol / vol_sma20 if vol_sma20 > 0 else 1.0

    is_buy = direction == "BUY"
    price_up = current_close > prev_close
    price_down = current_close < prev_close

    # ── 1. Volume Surge Detection ──
    # Current candle volume vs 20-period average
    if vol_ratio >= 2.5:
        # Massive volume — check alignment
        if (price_up and is_buy) or (price_down and not is_buy):
            score += 6
            notes.append(
                f"📊 VOLUME SURGE: {vol_ratio:.1f}x average — institutional entry confirmed"
            )
        elif (price_up and not is_buy) or (price_down and is_buy):
            score -= 3
            notes.append(
                f"⚠️ Volume surge ({vol_ratio:.1f}x) opposes signal direction"
            )
    elif vol_ratio >= 1.8:
        if (price_up and is_buy) or (price_down and not is_buy):
            score += 4
            notes.append(f"Volume elevated ({vol_ratio:.1f}x avg) — confirms direction")
        elif (price_up and not is_buy) or (price_down and is_buy):
            score -= 2
            notes.append(f"Elevated volume opposes signal")

    # ── 2. Breakout Volume Confirmation ──
    # Check if price is at a recent high/low (potential breakout)
    high_20 = float(high.tail(20).max())
    low_20 = float(low.tail(20).min())

    near_high = current_close >= high_20 * 0.998  # Within 0.2% of 20-bar high
    near_low = current_close <= low_20 * 1.002

    if near_high and is_buy:
        if vol_ratio >= 1.5:
            score += 3
            notes.append("Breakout to 20-bar high WITH volume — legitimate breakout")
        elif vol_ratio < 0.8:
            score -= 3
            notes.append("⚠️ New high on LOW volume — likely fakeout/trap")

    elif near_low and not is_buy:
        if vol_ratio >= 1.5:
            score += 3
            notes.append("Breakdown to 20-bar low WITH volume — legitimate breakdown")
        elif vol_ratio < 0.8:
            score -= 3
            notes.append("⚠️ New low on LOW volume — likely bear trap")

    # ── 3. Accumulation/Distribution Detection ──
    # Rising volume during consolidation = institutional accumulation
    recent_vol = vol.tail(10)
    older_vol = vol.tail(20).head(10)
    recent_range = float(high.tail(10).max()) - float(low.tail(10).min())
    older_range = float(high.tail(20).head(10).max()) - float(low.tail(20).head(10).min())

    vol_increasing = float(recent_vol.mean()) > float(older_vol.mean()) * 1.3
    range_contracting = recent_range < older_range * 0.7

    if vol_increasing and range_contracting:
        score += 3
        notes.append("📈 Accumulation: Volume rising while price consolidates — institutional loading")

    # ── 4. Climax Volume Reversal Warning ──
    # Extreme volume (3x+) at price extreme = exhaustion/reversal
    if vol_ratio >= 3.0:
        # Check if at recent extreme
        if near_high and not is_buy:
            score += 2
            notes.append("Climax volume at high — SELL signal confirms potential reversal")
        elif near_low and is_buy:
            score += 2
            notes.append("Climax volume at low — BUY signal confirms potential reversal")
        elif near_high and is_buy:
            score -= 2
            notes.append("⚠️ Climax volume at high — exhaustion risk for BUY entries")
        elif near_low and not is_buy:
            score -= 2
            notes.append("⚠️ Climax volume at low — exhaustion risk for SELL entries")

    # ── 5. Volume-Price Divergence ──
    # Price making new highs but volume declining = hidden weakness
    if len(close) >= 30:
        # Compare last 10 bars vs previous 10 bars
        recent_highs = float(high.tail(10).max())
        older_highs = float(high.tail(20).head(10).max())
        recent_avg_vol = float(vol.tail(10).mean())
        older_avg_vol = float(vol.tail(20).head(10).mean())

        if recent_highs > older_highs and recent_avg_vol < older_avg_vol * 0.7:
            if is_buy:
                score -= 2
                notes.append("⚠️ Price at highs but volume declining — buying exhaustion")
            else:
                score += 2
                notes.append("Price at highs with declining volume — supports SELL")

        elif float(low.tail(10).min()) < float(low.tail(20).head(10).min()) and recent_avg_vol < older_avg_vol * 0.7:
            if not is_buy:
                score -= 2
                notes.append("⚠️ Price at lows but volume declining — selling exhaustion")
            else:
                score += 2
                notes.append("Price at lows with declining volume — supports BUY")

    # ── 6. Volume Profile Zone ──
    # Is current price at a high-volume node (strong S/R) or low-volume area (fast move)?
    if len(close) >= 50:
        # Simple volume profile: divide price range into buckets
        price_min = float(low.tail(50).min())
        price_max = float(high.tail(50).max())
        price_range = price_max - price_min

        if price_range > 0:
            n_buckets = 10
            bucket_size = price_range / n_buckets
            vol_by_bucket = [0.0] * n_buckets

            for i in range(max(0, len(df) - 50), len(df)):
                mid_price = (float(high.iloc[i]) + float(low.iloc[i])) / 2
                bucket = min(int((mid_price - price_min) / bucket_size), n_buckets - 1)
                vol_by_bucket[bucket] += float(vol.iloc[i])

            current_bucket = min(int((current_close - price_min) / bucket_size), n_buckets - 1)
            avg_bucket_vol = sum(vol_by_bucket) / n_buckets
            current_bucket_vol = vol_by_bucket[current_bucket]

            if current_bucket_vol > avg_bucket_vol * 1.5:
                notes.append(f"Price at high-volume node — strong S/R zone, expect reaction")
            elif current_bucket_vol < avg_bucket_vol * 0.5:
                score += 1
                notes.append(f"Price in low-volume zone — fast move expected if breakout")

    # Cap score
    score = max(-5, min(10, score))

    return {
        "score": score,
        "notes": notes,
        "vol_ratio": round(vol_ratio, 2),
        "vol_sma20": round(vol_sma20, 0),
        "current_vol": round(current_vol, 0),
    }


# ════════════════════════════════════════════════════════════════
# COMBINED INSTITUTIONAL ANALYSIS
# ════════════════════════════════════════════════════════════════

# Singleton analyzer
_cot_analyzer = COTAnalyzer()


def get_institutional_score(
    direction: str,
    df_m15: pd.DataFrame = None,
    events: list = None,
    td_api_key: str = "",
) -> dict:
    """
    Run all 3 institutional modules and return combined result.

    Returns:
        {
            "total_score": int,     # Combined score from all 3 modules
            "cot_dxy": dict,        # Module 18 result
            "news_filter": dict,    # Module 19 result
            "volume": dict,         # Module 20 result
            "blocked": bool,        # True if news filter says DO NOT TRADE
            "institutional_bias": str,  # "BULLISH", "BEARISH", "NEUTRAL"
        }
    """
    # Module 18: COT + DXY
    cot_data = _cot_analyzer.fetch_cot_data()
    dxy_data = _cot_analyzer.fetch_dxy_trend(td_api_key)
    m18 = score_cot_dxy(direction, cot_data, dxy_data)

    # Module 19: News Filter
    m19 = score_news_filter(events or [], direction)

    # Module 20: Volume
    m20 = score_volume(df_m15, direction)

    total = m18["score"] + m19["score"] + m20["score"]
    blocked = m19.get("danger_level") == "BLOCKED"

    # Determine overall institutional bias
    if m18["score"] >= 5 and m20["score"] >= 3:
        bias = "BULLISH" if direction == "BUY" else "BEARISH"
    elif m18["score"] <= -5 or m20["score"] <= -3:
        opp = "BEARISH" if direction == "BUY" else "BULLISH"
        bias = opp
    else:
        bias = "NEUTRAL"

    return {
        "total_score": total,
        "cot_dxy": m18,
        "news_filter": m19,
        "volume": m20,
        "blocked": blocked,
        "institutional_bias": bias,
    }
