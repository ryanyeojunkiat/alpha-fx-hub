"""
Alpha FX Hub — Auto News Poster
Posts gold-relevant economic news to the PUBLIC Telegram channel every 1 hour.
Includes live XAUUSD price, dynamic S/R levels, and detailed event analysis.
Highlights upcoming high-impact events with countdown timers.

Runs as a background thread inside bot_runner.py.
"""
import os
import sys
import logging
import time
import threading
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from academy.calendar import fetch_economic_calendar, get_gold_impact_events
from engine.data import fetch_price, fetch_bars
from telegram.notifications import NotificationManager

logger = logging.getLogger("alpha_fx_hub.news_poster")


def _importance_stars(level: int) -> str:
    if level >= 3:
        return "\u2b50\u2b50\u2b50"
    elif level >= 2:
        return "\u2b50\u2b50"
    return "\u2b50"


def _impact_emoji(level: str) -> str:
    return {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f7e2"}.get(level, "\u26aa")


def _format_time_until(hours: float) -> str:
    if hours < 1:
        return f"{int(hours * 60)} min"
    elif hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        return f"{int(hours / 24)}d {int(hours % 24)}h"


def _round_level(price: float) -> float:
    """Round to nearest $5 for cleaner S/R levels."""
    return round(price / 5) * 5


def _get_session_name() -> str:
    """Get current trading session based on UTC hour."""
    hour = datetime.now(timezone.utc).hour
    if 22 <= hour or hour < 7:
        return "\U0001f311 Asian Session"
    elif 7 <= hour < 12:
        return "\U0001f1ec\U0001f1e7 London Session"
    elif 12 <= hour < 16:
        return "\U0001f1ec\U0001f1e7\U0001f1fa\U0001f1f8 London/NY Overlap"
    elif 16 <= hour < 21:
        return "\U0001f1fa\U0001f1f8 New York Session"
    else:
        return "\U0001f30d Late NY / Pre-Asia"


def _get_dynamic_levels(bars) -> dict:
    """Calculate dynamic support/resistance from recent price action."""
    if bars is None or bars.empty:
        return {}

    recent = bars.tail(100)  # Last ~25 hours of M15 data
    current = float(recent["close"].iloc[-1])
    high_24h = float(recent.tail(96)["high"].max())   # 96 x 15min = 24h
    low_24h = float(recent.tail(96)["low"].min())
    high_4h = float(recent.tail(16)["high"].max())     # 16 x 15min = 4h
    low_4h = float(recent.tail(16)["low"].min())

    # ATR for volatility context
    recent["tr"] = recent["high"] - recent["low"]
    atr = float(recent["tr"].tail(14).mean())

    # Simple pivot points from 24h data
    pivot = (high_24h + low_24h + current) / 3
    r1 = 2 * pivot - low_24h
    s1 = 2 * pivot - high_24h
    r2 = pivot + (high_24h - low_24h)
    s2 = pivot - (high_24h - low_24h)

    # Daily range
    daily_range = high_24h - low_24h

    # Trend based on recent closes
    close_20 = float(recent["close"].tail(20).mean())
    close_50 = float(recent["close"].tail(50).mean())
    if current > close_20 > close_50:
        trend = "\U0001f7e2 Bullish"
    elif current < close_20 < close_50:
        trend = "\U0001f534 Bearish"
    else:
        trend = "\U0001f7e1 Ranging"

    return {
        "current": current,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "high_4h": high_4h,
        "low_4h": low_4h,
        "atr": atr,
        "daily_range": daily_range,
        "pivot": _round_level(pivot),
        "r1": _round_level(r1),
        "r2": _round_level(r2),
        "s1": _round_level(s1),
        "s2": _round_level(s2),
        "trend": trend,
    }


def _event_detail(event_name: str) -> str:
    """Return detailed explanation for specific events."""
    name = event_name.lower()

    if "interest rate" in name or "fed " in name:
        return (
            "The Fed sets the benchmark interest rate that affects all USD-denominated assets. "
            "Higher rates strengthen USD and pressure gold lower. Lower rates weaken USD and "
            "push gold higher. Watch for dot plot projections and forward guidance language."
        )
    if "non farm" in name or "nfp" in name:
        return (
            "NFP measures monthly jobs added in the US economy (excluding farms). "
            "A strong number (above forecast) = USD bullish / gold bearish. "
            "A weak number = USD bearish / gold bullish. Watch unemployment rate alongside."
        )
    if "cpi" in name and "core" not in name:
        return (
            "Consumer Price Index measures inflation at the consumer level. "
            "Higher-than-expected CPI = potential rate hikes = gold initially bearish, "
            "but persistent high inflation is ultimately gold bullish as inflation hedge."
        )
    if "core cpi" in name:
        return (
            "Core CPI strips out volatile food and energy prices. "
            "This is the Fed's preferred measure — a hot core CPI signals sticky inflation "
            "and potential for more rate hikes, creating gold volatility."
        )
    if "pce" in name:
        return (
            "PCE Price Index is the Fed's PREFERRED inflation gauge. "
            "This carries more weight than CPI for monetary policy decisions. "
            "Higher PCE = hawkish Fed = USD strength = gold pressure."
        )
    if "gdp" in name:
        return (
            "GDP measures total economic output. Strong GDP reduces gold's safe-haven appeal "
            "as investors favor riskier assets. Weak GDP increases recession fears and "
            "drives capital into gold."
        )
    if "unemployment" in name:
        return (
            "Rising unemployment signals economic weakness, which is bullish for gold. "
            "Falling unemployment suggests economic strength, giving the Fed room to "
            "maintain higher rates — bearish for gold."
        )
    if "jobless" in name:
        return (
            "Weekly Initial Jobless Claims provide a real-time view of labor market health. "
            "Rising claims (above forecast) = economic weakness = gold bullish. "
            "Falling claims = labor market strength = gold pressure."
        )
    if "fomc" in name or "minutes" in name:
        return (
            "FOMC Minutes reveal the Fed's internal debate about policy direction. "
            "Hawkish language (inflation concerns, rate hike bias) = gold bearish. "
            "Dovish language (growth concerns, rate cut hints) = gold bullish."
        )
    if "powell" in name:
        return (
            "Fed Chair Powell's speeches can move gold $20-50+ as markets parse every word "
            "for policy clues. Watch for tone shifts on inflation, employment, "
            "and the path of interest rates."
        )
    if "ecb" in name:
        return (
            "ECB rate decisions affect EUR/USD, which inversely correlates with gold. "
            "A hawkish ECB (rates up) strengthens EUR, weakens USD, and supports gold. "
            "Dovish ECB has the opposite effect."
        )
    if "retail sales" in name:
        return (
            "Retail Sales measure consumer spending, the backbone of the US economy. "
            "Strong retail = economic strength = Fed hawkish = gold bearish. "
            "Weak retail = recession fears = gold bullish."
        )
    if "ism" in name and "manufacturing" in name:
        return (
            "ISM Manufacturing PMI above 50 = expansion, below 50 = contraction. "
            "A contracting manufacturing sector increases recession risk and "
            "drives safe-haven demand for gold."
        )
    if "trade balance" in name:
        return (
            "Trade deficit/surplus affects USD strength. Widening trade deficit "
            "weakens USD and supports gold. Narrowing deficit strengthens USD."
        )
    if "gold reserve" in name:
        return (
            "Central bank gold purchases directly increase demand and support prices. "
            "Major buyers (China, Russia, India) have been accumulating gold, "
            "providing a structural floor for prices."
        )
    if "durable goods" in name:
        return (
            "Durable Goods Orders measure demand for long-lasting manufactured items. "
            "Strong orders signal business confidence and economic growth, "
            "which can pressure gold. Weak orders boost safe-haven demand."
        )
    if "consumer confidence" in name:
        return (
            "Consumer Confidence reflects household spending outlook. "
            "High confidence = risk-on sentiment = gold pressure. "
            "Low confidence = risk-off sentiment = gold support."
        )

    return "Monitor USD reaction — gold typically moves inverse to the US dollar."


def _event_source_link(event_name: str) -> str:
    """Return relevant news/data source links for each event type."""
    name = event_name.lower()

    links = []
    # Always include these
    links.append("https://www.forexfactory.com/calendar")

    if any(x in name for x in ["fed", "fomc", "interest rate", "powell"]):
        links.append("https://www.federalreserve.gov/monetarypolicy.htm")
    elif any(x in name for x in ["cpi", "ppi", "pce", "inflation"]):
        links.append("https://www.bls.gov/cpi/")
    elif any(x in name for x in ["non farm", "nfp", "unemployment", "jobless"]):
        links.append("https://www.bls.gov/ces/")
    elif "gdp" in name:
        links.append("https://www.bea.gov/data/gdp")
    elif "ecb" in name:
        links.append("https://www.ecb.europa.eu/mopo/decisions/html/index.en.html")
    elif any(x in name for x in ["retail", "consumer"]):
        links.append("https://www.census.gov/retail/index.html")
    elif "ism" in name:
        links.append("https://www.ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/")

    links.append("https://tradingeconomics.com/calendar")
    return "\n".join(f"  \U0001f517 {l}" for l in links)


def build_hourly_update(events: list, price_data: dict, td_api_key: str = "") -> str:
    """Build detailed hourly news update with live price and dynamic levels."""
    now = datetime.now(timezone.utc)
    gold_events = get_gold_impact_events(events)

    session = _get_session_name()

    # Price section
    lines = ["\U0001f4f0 <b>ALPHA FX HUB — GOLD HOURLY UPDATE</b>"]
    lines.append(f"\U0001f552 {now.strftime('%a %d %b %Y | %H:%M UTC')} | {session}")
    lines.append("")

    if price_data:
        current = price_data.get("current", 0)
        trend = price_data.get("trend", "N/A")
        atr = price_data.get("atr", 0)
        h24 = price_data.get("high_24h", 0)
        l24 = price_data.get("low_24h", 0)
        daily_range = price_data.get("daily_range", 0)

        lines.append(f"\U0001f4b0 <b>XAUUSD: ${current:.2f}</b>  |  {trend}")
        lines.append(f"\U0001f4ca 24h Range: ${l24:.2f} — ${h24:.2f} (${daily_range:.1f})")
        lines.append(f"\U0001f4cf ATR(14): ${atr:.1f} | Volatility: {'High' if atr > 15 else 'Normal' if atr > 8 else 'Low'}")
        lines.append("")
        lines.append(f"<b>Key Levels (Pivot):</b>")
        lines.append(f"  R2: ${price_data.get('r2', 0):.0f}  |  R1: ${price_data.get('r1', 0):.0f}")
        lines.append(f"  Pivot: ${price_data.get('pivot', 0):.0f}")
        lines.append(f"  S1: ${price_data.get('s1', 0):.0f}  |  S2: ${price_data.get('s2', 0):.0f}")
    else:
        lines.append("\U0001f4b0 <b>XAUUSD:</b> Price data unavailable (check API key)")

    lines.append("")
    lines.append("\u2500" * 25)
    lines.append("")

    # Upcoming events
    upcoming = []
    recent_results = []

    for evt in gold_events:
        try:
            evt_time = datetime.fromisoformat(evt["time"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        hours_diff = (evt_time - now).total_seconds() / 3600

        if 0 < hours_diff <= 48:
            evt["hours_until"] = hours_diff
            upcoming.append(evt)
        elif -12 < hours_diff <= 0 and evt.get("actual"):
            evt["hours_ago"] = abs(hours_diff)
            recent_results.append(evt)

    if upcoming:
        upcoming.sort(key=lambda x: x["hours_until"])
        lines.append("\U0001f4c5 <b>UPCOMING GOLD-IMPACT EVENTS:</b>")
        lines.append("")

        for evt in upcoming[:6]:
            stars = _importance_stars(evt["importance"])
            impact = evt.get("gold_impact", {})
            impact_level = impact.get("level", "LOW")
            emoji = _impact_emoji(impact_level)
            countdown = _format_time_until(evt["hours_until"])

            lines.append(f"{emoji} <b>{evt['event']}</b>")
            lines.append(f"   \U0001f3f3\ufe0f {evt.get('country', 'N/A')} | {stars} | \u23f0 In <b>{countdown}</b>")

            if evt.get("forecast") or evt.get("previous"):
                fc = evt.get("forecast", "N/A")
                prev = evt.get("previous", "N/A")
                lines.append(f"   Forecast: <b>{fc}</b> | Previous: <b>{prev}</b>")

            # Detailed analysis
            detail = _event_detail(evt["event"])
            lines.append(f"   \U0001f4a1 <i>{detail}</i>")

            # Expected gold reaction
            if impact.get("typical_impact"):
                lines.append(f"   \U0001f4ca Gold: <b>{impact['typical_impact']}</b>")
            if impact.get("volatility"):
                lines.append(f"   \u26a1 Volatility: {impact['volatility']}")

            # Source links
            sources = _event_source_link(evt["event"])
            lines.append(f"   {sources}")
            lines.append("")

    # Recent results
    if recent_results:
        recent_results.sort(key=lambda x: x["hours_ago"])
        lines.append("\u2500" * 25)
        lines.append("")
        lines.append("\U0001f4ca <b>RECENT DATA RELEASES:</b>")
        lines.append("")

        for evt in recent_results[:4]:
            actual = evt.get("actual", "N/A")
            forecast = evt.get("forecast", "N/A")
            previous = evt.get("previous", "N/A")

            beat_emoji = ""
            try:
                act_val = float(str(actual).replace("%", "").replace("K", "000").replace("M", "000000").strip())
                fct_val = float(str(forecast).replace("%", "").replace("K", "000").replace("M", "000000").strip())
                if act_val > fct_val:
                    beat_emoji = " \U0001f7e2 BEAT"
                elif act_val < fct_val:
                    beat_emoji = " \U0001f534 MISS"
                else:
                    beat_emoji = " \u2796 In Line"
            except (ValueError, TypeError):
                pass

            hours_ago = _format_time_until(evt.get("hours_ago", 0))
            lines.append(f"\u2022 <b>{evt['event']}</b>{beat_emoji} ({hours_ago} ago)")
            lines.append(f"  Actual: <b>{actual}</b> | Forecast: {forecast} | Prev: {previous}")

            # What it means for gold
            detail = _event_detail(evt["event"])
            lines.append(f"  \U0001f4a1 <i>{detail[:120]}...</i>")
            lines.append("")

    if not upcoming and not recent_results:
        lines.append("\U0001f4c5 <b>No major gold-impact events in the next 48 hours.</b>")
        lines.append("Lower volatility expected — range trading conditions likely.")
        lines.append("")

    # Footer
    lines.append("\u2500" * 25)
    lines.append("\u26a0\ufe0f <i>High-impact events cause $20-50+ gold moves. Manage risk accordingly.</i>")
    lines.append(f"\U0001f310 <b>Full Platform:</b> https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app")
    lines.append(f"\U0001f517 <b>Sources:</b> https://tradingeconomics.com/calendar | https://www.forexfactory.com/calendar")
    lines.append("")
    lines.append("\U0001f4ca <b>Alpha FX Hub</b> | Gold Signal Engine V4")

    return "\n".join(lines)


def build_event_alert(event: dict, hours_until: float, price_data: dict = None) -> str:
    """Build an urgent alert for an imminent high-impact event."""
    impact = event.get("gold_impact", {})
    countdown = _format_time_until(hours_until)
    detail = _event_detail(event["event"])

    price_line = ""
    if price_data and price_data.get("current"):
        price_line = f"\n\U0001f4b0 <b>XAUUSD Now: ${price_data['current']:.2f}</b> | {price_data.get('trend', '')}\n"

    msg = f"""
\u26a0\ufe0f\u26a0\ufe0f <b>HIGH-IMPACT EVENT ALERT</b> \u26a0\ufe0f\u26a0\ufe0f

\U0001f534 <b>{event['event']}</b>
\U0001f3f3\ufe0f {event.get('country', 'N/A')} | Releases in <b>{countdown}</b>
{price_line}
Forecast: <b>{event.get('forecast', 'N/A')}</b> | Previous: <b>{event.get('previous', 'N/A')}</b>

\U0001f4a1 <b>What This Means:</b>
{detail}

\U0001f4ca <b>Gold Impact:</b> {impact.get('typical_impact', 'May affect gold through USD')}
\u26a1 <b>Expected Volatility:</b> {impact.get('volatility', 'Medium to High')}

\u26a0\ufe0f <b>Trader Action Required:</b>
\u2022 Reduce position size or close trades before release
\u2022 Widen stop losses — spreads will spike
\u2022 Wait 5-15 min after release for price to settle
\u2022 Watch for fakeout moves in the first 2 minutes

\U0001f517 <b>Live Data:</b>
  https://www.forexfactory.com/calendar
  https://tradingeconomics.com/calendar

<i>Alpha FX Hub — Protecting your capital first.</i>
""".strip()
    return msg


def build_weekend_prediction(price_data: dict, events: list, td_api_key: str = "") -> str:
    """Build a weekend prediction signal for Monday market open."""
    now = datetime.now(timezone.utc)

    lines = ["\U0001f52e <b>WEEKEND ANALYSIS — MONDAY OPEN PREDICTION</b>"]
    lines.append(f"\U0001f552 {now.strftime('%a %d %b %Y | %H:%M UTC')}")
    lines.append("")

    # Last known price
    price = price_data.get("current", 0)
    if price:
        lines.append(f"\U0001f4b0 <b>Friday Close:</b> ${price:.2f}")

    # S/R levels
    r2 = price_data.get("r2", 0)
    r1 = price_data.get("r1", 0)
    pivot = price_data.get("pivot", 0)
    s1 = price_data.get("s1", 0)
    s2 = price_data.get("s2", 0)

    if pivot:
        lines.append("")
        lines.append("\U0001f4ca <b>KEY LEVELS FOR MONDAY:</b>")
        lines.append(f"  R2: ${r2:.2f}")
        lines.append(f"  R1: ${r1:.2f}")
        lines.append(f"  Pivot: ${pivot:.2f}")
        lines.append(f"  S1: ${s1:.2f}")
        lines.append(f"  S2: ${s2:.2f}")

    # Trend analysis
    trend = price_data.get("trend", "")
    atr = price_data.get("atr", 0)
    high_24h = price_data.get("high_24h", 0)
    low_24h = price_data.get("low_24h", 0)

    lines.append("")
    lines.append("\U0001f4c8 <b>TECHNICAL OUTLOOK:</b>")
    if trend:
        lines.append(f"  Trend: <b>{trend.upper()}</b>")
    if atr:
        lines.append(f"  ATR(14): ${atr:.2f}")
    if high_24h and low_24h:
        lines.append(f"  Friday Range: ${low_24h:.2f} — ${high_24h:.2f}")

    # Bias calculation
    bias = "NEUTRAL"
    reasoning = []
    if price and pivot:
        if price > pivot:
            reasoning.append("Price above pivot = bullish bias")
            bias = "BULLISH"
        else:
            reasoning.append("Price below pivot = bearish bias")
            bias = "BEARISH"

    if trend:
        if "bullish" in trend.lower():
            reasoning.append("Overall trend is bullish")
            if bias != "BEARISH":
                bias = "BULLISH"
        elif "bearish" in trend.lower():
            reasoning.append("Overall trend is bearish")
            if bias != "BULLISH":
                bias = "BEARISH"

    bias_emoji = "\U0001f7e2" if bias == "BULLISH" else "\U0001f534" if bias == "BEARISH" else "\U0001f7e1"
    lines.append("")
    lines.append(f"{bias_emoji} <b>MONDAY BIAS: {bias}</b>")
    for r in reasoning:
        lines.append(f"  \u2022 {r}")

    # Scenario planning
    lines.append("")
    lines.append("\U0001f3af <b>SCENARIOS FOR MONDAY:</b>")
    if price and atr:
        bull_target = price + atr * 1.5
        bear_target = price - atr * 1.5
        if bias == "BULLISH":
            lines.append(f"  \U0001f7e2 Bullish: Gap up → target R1 (${r1:.2f}) then R2 (${r2:.2f})")
            lines.append(f"  \U0001f534 Risk: If breaks below ${s1:.2f}, bears take control → ${s2:.2f}")
            lines.append(f"  \U0001f4a1 <b>Plan:</b> Look for BUY entries at ${pivot:.2f}-${s1:.2f} zone")
        elif bias == "BEARISH":
            lines.append(f"  \U0001f534 Bearish: Gap down → target S1 (${s1:.2f}) then S2 (${s2:.2f})")
            lines.append(f"  \U0001f7e2 Risk: If breaks above ${r1:.2f}, bulls take control → ${r2:.2f}")
            lines.append(f"  \U0001f4a1 <b>Plan:</b> Look for SELL entries at ${pivot:.2f}-${r1:.2f} zone")
        else:
            lines.append(f"  Watch ${r1:.2f} (resistance) and ${s1:.2f} (support) for direction")
            lines.append(f"  \U0001f4a1 <b>Plan:</b> Wait for clear breakout before entering")

    # Upcoming week events
    gold_events = get_gold_impact_events(events)
    week_events = []
    for evt in gold_events:
        try:
            evt_time = datetime.fromisoformat(evt["time"].replace("Z", "+00:00"))
            if now < evt_time < now + timedelta(days=7) and evt["importance"] >= 2:
                week_events.append(evt)
        except (ValueError, TypeError):
            continue

    if week_events:
        lines.append("")
        lines.append("\U0001f4c5 <b>KEY EVENTS THIS WEEK:</b>")
        for evt in week_events[:8]:
            try:
                evt_time = datetime.fromisoformat(evt["time"].replace("Z", "+00:00"))
                day_name = evt_time.strftime("%a %d %b")
                time_str = evt_time.strftime("%H:%M UTC")
            except Exception:
                day_name = "TBD"
                time_str = ""
            stars = _importance_stars(evt["importance"])
            lines.append(f"  {stars} {evt['event']} — {day_name} {time_str}")

    lines.append("")
    lines.append("\u26a0\ufe0f <b>Risk Warning:</b> Weekend gaps can be significant. Use pending orders with proper SL.")
    lines.append("")
    lines.append("\U0001f4ca <b>Alpha FX Hub</b> | Weekend Analysis")

    return "\n".join(lines)


class NewsPoster:
    """Runs in background thread, posts gold news every hour."""

    def __init__(self, notifier: NotificationManager, te_api_key: str = "",
                 td_api_key: str = "", interval_seconds: int = 3600):
        self.notifier = notifier
        self.te_api_key = te_api_key
        self.td_api_key = td_api_key
        self.interval = interval_seconds  # 3600 = 1 hour
        self.alert_check_interval = 300   # Check every 5 min
        self._running = False
        self._alerted_events = set()
        self._weekend_posted = False

    def start(self):
        if self._running:
            return
        self._running = True

        t1 = threading.Thread(target=self._regular_loop, daemon=True)
        t1.start()

        t2 = threading.Thread(target=self._alert_loop, daemon=True)
        t2.start()

        t3 = threading.Thread(target=self._weekend_loop, daemon=True)
        t3.start()

        logger.info(f"News poster started — hourly updates + 5-min event alerts + weekend predictions")

    def stop(self):
        self._running = False

    def _get_price_data(self) -> dict:
        """Fetch live XAUUSD price and calculate dynamic S/R levels."""
        try:
            bars = fetch_bars(
                symbol="XAU/USD", interval="15min",
                outputsize=200, api_key=self.td_api_key
            )
            if bars is not None and not bars.empty:
                return _get_dynamic_levels(bars)
        except Exception as e:
            logger.error(f"Price fetch error: {e}")

        # Fallback: just get spot price
        try:
            price = fetch_price(symbol="XAU/USD", api_key=self.td_api_key)
            if price:
                return {"current": price, "trend": "N/A"}
        except Exception:
            pass

        return {}

    def _regular_loop(self):
        """Post hourly gold news update."""
        time.sleep(30)  # Wait before first post

        while self._running:
            try:
                events = fetch_economic_calendar(api_key=self.te_api_key)
                price_data = self._get_price_data()
                msg = build_hourly_update(events, price_data, self.td_api_key)

                if msg:
                    success = self.notifier.broadcast_public(msg)
                    logger.info(f"Hourly news posted: {'OK' if success else 'FAILED'}")
                else:
                    logger.info("No content to post this hour")

            except Exception as e:
                logger.error(f"News poster error: {e}")

            time.sleep(self.interval)

    def _alert_loop(self):
        """Check for imminent high-impact events every 5 minutes."""
        time.sleep(60)

        while self._running:
            try:
                events = fetch_economic_calendar(api_key=self.te_api_key)
                gold_events = get_gold_impact_events(events)
                now = datetime.now(timezone.utc)

                for evt in gold_events:
                    if evt["importance"] < 3:
                        continue

                    try:
                        evt_time = datetime.fromisoformat(evt["time"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        continue

                    hours_until = (evt_time - now).total_seconds() / 3600
                    event_key = f"{evt['event']}_{evt['time']}"

                    # Alert 1 hour before high-impact events
                    if 0.5 < hours_until <= 1.0 and event_key not in self._alerted_events:
                        price_data = self._get_price_data()
                        msg = build_event_alert(evt, hours_until, price_data)

                        success = self.notifier.broadcast_public(msg)
                        self.notifier.broadcast(
                            f"\u26a0\ufe0f <b>EVENT WARNING:</b> {evt['event']} in {_format_time_until(hours_until)}\n"
                            f"Consider managing open positions."
                        )

                        if success:
                            self._alerted_events.add(event_key)
                            logger.info(f"Event alert sent: {evt['event']}")

            except Exception as e:
                logger.error(f"Alert loop error: {e}")

            time.sleep(self.alert_check_interval)

    def _weekend_loop(self):
        """Post weekend prediction on Saturday morning (once per weekend)."""
        time.sleep(120)  # Wait 2 min before first check

        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Post on Saturday between 6-10 UTC (once)
                is_saturday = now.weekday() == 5  # 5 = Saturday
                is_morning = 6 <= now.hour <= 10

                if is_saturday and is_morning and not self._weekend_posted:
                    events = fetch_economic_calendar(api_key=self.te_api_key)
                    price_data = self._get_price_data()

                    if price_data:
                        msg = build_weekend_prediction(price_data, events, self.td_api_key)
                        # Post to PRIVATE channel (premium content)
                        success = self.notifier.broadcast(msg)
                        if success:
                            self._weekend_posted = True
                            logger.info("Weekend prediction posted to private channel")

                # Reset flag on Monday
                if now.weekday() == 0:  # Monday
                    self._weekend_posted = False

            except Exception as e:
                logger.error(f"Weekend prediction error: {e}")

            time.sleep(1800)  # Check every 30 min
