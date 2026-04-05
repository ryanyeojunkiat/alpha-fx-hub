"""
Alpha FX Hub — Auto News Poster
Posts gold-relevant economic news to the PUBLIC Telegram channel every 2 hours.
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

from academy.calendar import fetch_economic_calendar, get_gold_impact_events, is_high_impact_soon
from telegram.notifications import NotificationManager

logger = logging.getLogger("alpha_fx_hub.news_poster")

# Track what we've already posted to avoid duplicates
_posted_events = set()
_last_regular_post = 0


def _importance_stars(level: int) -> str:
    """Convert importance level to star rating."""
    if level >= 3:
        return "\u2b50\u2b50\u2b50"
    elif level >= 2:
        return "\u2b50\u2b50"
    return "\u2b50"


def _impact_emoji(level: str) -> str:
    """Get emoji for impact level."""
    mapping = {
        "HIGH": "\U0001f534",     # red circle
        "MEDIUM": "\U0001f7e1",   # yellow circle
        "LOW": "\U0001f7e2",      # green circle
    }
    return mapping.get(level, "\u26aa")


def _format_time_until(hours: float) -> str:
    """Format hours into readable countdown."""
    if hours < 1:
        mins = int(hours * 60)
        return f"{mins} min"
    elif hours < 24:
        h = int(hours)
        m = int((hours - h) * 60)
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    else:
        days = int(hours / 24)
        remaining_h = int(hours % 24)
        return f"{days}d {remaining_h}h"


def build_regular_update(events: list) -> str:
    """Build the regular 2-hour news update message."""
    now = datetime.now(timezone.utc)
    gold_events = get_gold_impact_events(events)

    if not gold_events:
        return ""

    # Split into upcoming (next 48h) and past (last 12h with results)
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

    if not upcoming and not recent_results:
        return ""

    # Build message
    lines = ["\U0001f4f0 <b>GOLD ECONOMIC CALENDAR UPDATE</b>"]
    lines.append(f"\U0001f552 {now.strftime('%a %d %b %H:%M UTC')}")
    lines.append("")

    # Upcoming events
    if upcoming:
        upcoming.sort(key=lambda x: x["hours_until"])
        lines.append("\U0001f4c5 <b>Upcoming Events (Gold Impact):</b>")
        lines.append("")

        for evt in upcoming[:8]:  # Max 8 events
            stars = _importance_stars(evt["importance"])
            impact = evt.get("gold_impact", {})
            impact_level = impact.get("level", "LOW")
            emoji = _impact_emoji(impact_level)
            countdown = _format_time_until(evt["hours_until"])

            lines.append(f"{emoji} <b>{evt['event']}</b> ({evt['country']})")
            lines.append(f"   {stars} | In {countdown}")

            if evt.get("forecast") and evt.get("previous"):
                lines.append(f"   Forecast: {evt['forecast']} | Prev: {evt['previous']}")

            if impact.get("typical_impact"):
                lines.append(f"   <i>\U0001f4a1 {impact['typical_impact']}</i>")

            lines.append("")

    # Recent results
    if recent_results:
        recent_results.sort(key=lambda x: x["hours_ago"])
        lines.append("\U0001f4ca <b>Recent Results:</b>")
        lines.append("")

        for evt in recent_results[:5]:
            actual = evt.get("actual", "N/A")
            forecast = evt.get("forecast", "N/A")
            previous = evt.get("previous", "N/A")

            # Determine if beat/miss
            beat_emoji = ""
            try:
                act_val = float(str(actual).replace("%", "").replace("K", "000").replace("M", "000000").strip())
                fct_val = float(str(forecast).replace("%", "").replace("K", "000").replace("M", "000000").strip())
                if act_val > fct_val:
                    beat_emoji = " \U0001f7e2 Beat"
                elif act_val < fct_val:
                    beat_emoji = " \U0001f534 Miss"
                else:
                    beat_emoji = " \u2796 In line"
            except (ValueError, TypeError):
                pass

            lines.append(f"\u2022 <b>{evt['event']}</b>{beat_emoji}")
            lines.append(f"  Actual: <b>{actual}</b> | Forecast: {forecast} | Prev: {previous}")
            lines.append("")

    # Footer
    lines.append("\u26a0\ufe0f <i>High-impact events can cause $20-50+ moves in gold.</i>")
    lines.append("\U0001f310 <b>Full analysis:</b> https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app")
    lines.append("")
    lines.append("\U0001f4ca <b>Alpha FX Hub</b> | Economic Calendar")

    return "\n".join(lines)


def build_event_alert(event: dict, hours_until: float) -> str:
    """Build an urgent alert for an imminent high-impact event."""
    impact = event.get("gold_impact", {})
    countdown = _format_time_until(hours_until)

    msg = f"""
\u26a0\ufe0f\u26a0\ufe0f <b>HIGH-IMPACT EVENT ALERT</b> \u26a0\ufe0f\u26a0\ufe0f

\U0001f534 <b>{event['event']}</b>
\U0001f3f3\ufe0f {event.get('country', 'N/A')} | In <b>{countdown}</b>

Forecast: <b>{event.get('forecast', 'N/A')}</b> | Previous: <b>{event.get('previous', 'N/A')}</b>

\U0001f4a1 <b>Gold Impact:</b>
{impact.get('typical_impact', 'May impact gold through USD correlation')}

\U0001f4ca <b>Expected Volatility:</b> {impact.get('volatility', 'Medium to High')}

\u26a0\ufe0f <b>Recommended Action:</b>
\u2022 Reduce position size before the event
\u2022 Widen stop losses or exit trades
\u2022 Wait for data release before opening new trades
\u2022 Expect increased spread and slippage

<i>Alpha FX Hub — Protecting your capital first.</i>
""".strip()
    return msg


class NewsPoster:
    """Runs in a background thread, posts news every 2 hours."""

    def __init__(self, notifier: NotificationManager, te_api_key: str = "",
                 interval_seconds: int = 7200):
        self.notifier = notifier
        self.te_api_key = te_api_key
        self.interval = interval_seconds  # 7200 = 2 hours
        self.alert_check_interval = 300   # Check for imminent events every 5 min
        self._running = False
        self._alerted_events = set()

    def start(self):
        """Start the news poster in a background thread."""
        if self._running:
            return
        self._running = True

        # Thread 1: Regular 2-hour updates
        t1 = threading.Thread(target=self._regular_loop, daemon=True)
        t1.start()

        # Thread 2: Imminent event alerts (every 5 min)
        t2 = threading.Thread(target=self._alert_loop, daemon=True)
        t2.start()

        logger.info(f"News poster started — updates every {self.interval // 60} min, alerts every {self.alert_check_interval // 60} min")

    def stop(self):
        self._running = False

    def _regular_loop(self):
        """Post regular economic calendar update every 2 hours."""
        # Wait 30 seconds after startup before first post
        time.sleep(30)

        while self._running:
            try:
                events = fetch_economic_calendar(api_key=self.te_api_key)
                msg = build_regular_update(events)

                if msg:
                    success = self.notifier.broadcast_public(msg)
                    if success:
                        logger.info("Posted regular news update to public channel")
                    else:
                        logger.warning("Failed to post news update")
                else:
                    logger.info("No gold-relevant events to post")

            except Exception as e:
                logger.error(f"News poster error: {e}")

            # Sleep for 2 hours
            time.sleep(self.interval)

    def _alert_loop(self):
        """Check for imminent high-impact events every 5 minutes."""
        # Wait 60 seconds after startup
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
                        msg = build_event_alert(evt, hours_until)
                        success = self.notifier.broadcast_public(msg)

                        # Also alert private channel
                        self.notifier.broadcast(
                            f"\u26a0\ufe0f <b>EVENT WARNING:</b> {evt['event']} in {_format_time_until(hours_until)}\n"
                            f"Consider managing open positions."
                        )

                        if success:
                            self._alerted_events.add(event_key)
                            logger.info(f"Sent event alert: {evt['event']}")

            except Exception as e:
                logger.error(f"Alert loop error: {e}")

            time.sleep(self.alert_check_interval)
