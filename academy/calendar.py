"""
Alpha FX Hub — Economic Calendar
Trading Economics API integration with XAUUSD impact analysis.
"""
import os
import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger("alpha_fx_hub.calendar")

# Cache
_cal_cache = {"data": None, "fetched": 0}
_CAL_CACHE_TTL = 3600  # 1 hour (500 req/month quota)


def fetch_economic_calendar(
    api_key: str = None,
    days_ahead: int = 7,
) -> List[Dict]:
    """
    Fetch economic calendar from Trading Economics API.
    Filters for events that impact gold (XAUUSD).
    """
    if api_key is None:
        api_key = os.environ.get("TE_API_KEY", "")

    # Check cache
    now = time.time()
    if _cal_cache["data"] and (now - _cal_cache["fetched"]) < _CAL_CACHE_TTL:
        return _cal_cache["data"]

    if not api_key:
        logger.warning("No Trading Economics API key — using demo data")
        return _get_demo_calendar()

    try:
        start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        url = f"https://api.tradingeconomics.com/calendar"
        params = {
            "c": api_key,
            "d1": start,
            "d2": end,
            "f": "json",
        }
        resp = requests.get(url, params=params, timeout=15)

        if resp.status_code != 200:
            logger.error(f"TE Calendar API error: {resp.status_code}")
            return _get_demo_calendar()

        events = resp.json()
        _cal_cache["data"] = events
        _cal_cache["fetched"] = now
        return events

    except Exception as e:
        logger.error(f"Calendar fetch error: {e}")
        return _get_demo_calendar()


def get_gold_impact_events(events: List[Dict]) -> List[Dict]:
    """
    Filter calendar events that specifically impact XAUUSD.
    Returns events sorted by impact level and time.
    """
    from config import GOLD_IMPACT_EVENTS, GOLD_IMPACT_CURRENCIES

    gold_events = []
    for event in events:
        event_name = event.get("Event", event.get("event", ""))
        country = event.get("Country", event.get("country", ""))
        currency = event.get("Currency", event.get("currency", ""))
        importance = event.get("Importance", event.get("importance", 0))

        # Check if this event impacts gold
        is_gold_event = False

        # Direct match on event name
        for ge in GOLD_IMPACT_EVENTS:
            if ge.lower() in event_name.lower():
                is_gold_event = True
                break

        # Currency-based impact (USD events affect gold most)
        if currency in GOLD_IMPACT_CURRENCIES and importance >= 2:
            is_gold_event = True

        if is_gold_event:
            # Determine gold impact direction
            gold_impact = _assess_gold_impact(event_name, event)

            gold_events.append({
                "time": event.get("Date", event.get("date", "")),
                "event": event_name,
                "country": country,
                "currency": currency,
                "importance": importance,
                "actual": event.get("Actual", event.get("actual", "")),
                "forecast": event.get("Forecast", event.get("forecast", "")),
                "previous": event.get("Previous", event.get("previous", "")),
                "gold_impact": gold_impact,
            })

    # Sort by importance (high first) then by time
    gold_events.sort(key=lambda x: (-x["importance"], x["time"]))
    return gold_events


def _assess_gold_impact(event_name: str, event: dict) -> dict:
    """
    Assess how an event typically impacts gold price.
    Returns impact assessment with direction and explanation.
    """
    name_lower = event_name.lower()

    # Fed / Interest Rate events
    if any(x in name_lower for x in ["interest rate", "fed ", "fomc", "federal reserve"]):
        return {
            "level": "HIGH",
            "typical_impact": "Rate hike = bearish gold, Rate cut = bullish gold",
            "explanation": "Higher rates make USD stronger, reducing gold appeal as a non-yielding asset.",
            "volatility": "Extreme — expect $20-50+ moves",
        }

    # Inflation data
    if any(x in name_lower for x in ["cpi", "ppi", "pce price", "inflation"]):
        return {
            "level": "HIGH",
            "typical_impact": "High inflation = bullish gold (safe haven), Low inflation = bearish gold",
            "explanation": "Gold is traditionally an inflation hedge. High CPI drives demand for gold.",
            "volatility": "High — expect $10-30 moves",
        }

    # Employment data
    if any(x in name_lower for x in ["non farm", "nfp", "unemployment", "jobless"]):
        return {
            "level": "HIGH",
            "typical_impact": "Strong jobs = bearish gold (strong USD), Weak jobs = bullish gold",
            "explanation": "Strong employment supports rate hikes, strengthening USD and weakening gold.",
            "volatility": "High — expect $15-40 moves",
        }

    # GDP
    if "gdp" in name_lower:
        return {
            "level": "MEDIUM",
            "typical_impact": "Strong GDP = bearish gold, Weak GDP = bullish gold",
            "explanation": "Strong economic growth reduces safe-haven demand for gold.",
            "volatility": "Medium — expect $10-20 moves",
        }

    # Trade / Geopolitical
    if any(x in name_lower for x in ["trade balance", "tariff", "sanctions"]):
        return {
            "level": "MEDIUM",
            "typical_impact": "Trade tensions = bullish gold (safe haven bid)",
            "explanation": "Geopolitical uncertainty drives demand for gold as a store of value.",
            "volatility": "Variable",
        }

    # Default
    return {
        "level": "LOW",
        "typical_impact": "Indirect impact on gold through USD correlation",
        "explanation": "Monitor USD reaction — gold typically moves inverse to USD.",
        "volatility": "Low to Medium",
    }


def is_high_impact_soon(events: List[Dict], hours_ahead: float = 2.0) -> Dict:
    """
    Check if a high-impact gold event is coming in the next N hours.
    Returns warning dict if true.
    """
    now = datetime.now(timezone.utc)
    gold_events = get_gold_impact_events(events)

    for event in gold_events:
        try:
            event_time = datetime.fromisoformat(event["time"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        hours_until = (event_time - now).total_seconds() / 3600

        if 0 < hours_until <= hours_ahead and event["importance"] >= 3:
            return {
                "warning": True,
                "event": event["event"],
                "time": event["time"],
                "hours_until": round(hours_until, 1),
                "impact": event["gold_impact"],
                "recommendation": "Consider reducing position size or avoiding new trades until after the event.",
            }

    return {"warning": False}


def _get_demo_calendar() -> List[Dict]:
    """Demo calendar data for testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "Date": (now + timedelta(hours=2)).isoformat(),
            "Event": "Fed Interest Rate Decision",
            "Country": "United States",
            "Currency": "USD",
            "Importance": 3,
            "Actual": "",
            "Forecast": "5.50%",
            "Previous": "5.50%",
        },
        {
            "Date": (now + timedelta(hours=6)).isoformat(),
            "Event": "Non Farm Payrolls",
            "Country": "United States",
            "Currency": "USD",
            "Importance": 3,
            "Actual": "",
            "Forecast": "180K",
            "Previous": "175K",
        },
        {
            "Date": (now + timedelta(days=1)).isoformat(),
            "Event": "CPI YoY",
            "Country": "United States",
            "Currency": "USD",
            "Importance": 3,
            "Actual": "",
            "Forecast": "3.2%",
            "Previous": "3.1%",
        },
        {
            "Date": (now + timedelta(days=1, hours=4)).isoformat(),
            "Event": "ECB Interest Rate Decision",
            "Country": "Euro Area",
            "Currency": "EUR",
            "Importance": 3,
            "Actual": "",
            "Forecast": "4.25%",
            "Previous": "4.50%",
        },
        {
            "Date": (now + timedelta(days=2)).isoformat(),
            "Event": "Initial Jobless Claims",
            "Country": "United States",
            "Currency": "USD",
            "Importance": 2,
            "Actual": "",
            "Forecast": "215K",
            "Previous": "210K",
        },
        {
            "Date": (now + timedelta(days=3)).isoformat(),
            "Event": "GDP Growth Rate QoQ",
            "Country": "United States",
            "Currency": "USD",
            "Importance": 3,
            "Actual": "",
            "Forecast": "2.1%",
            "Previous": "2.0%",
        },
    ]
