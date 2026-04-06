"""
Alpha FX Hub — Decision Assistant Monitor (Railway Background Service)
=====================================================================
Runs alongside the Telegram bot on Railway.
Continuously scans XAUUSD for entry zones and sends Telegram alerts.

This is a headless monitor — no terminal input, no Streamlit.
The Streamlit page (app.py) is display-only.
"""

import os
import sys
import time
import logging
import threading
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_assistant import (
    BiasEngine, EntryZoneDetector, TelegramAlerts,
    MarketBias, EntryZone,
    SESSIONS, ALERT_DISTANCE, MAX_SETUPS_PER_DAY, SCAN_INTERVAL,
)
from engine.data import fetch_bars, fetch_price
from config import TWELVE_DATA_API_KEY

logger = logging.getLogger("decision_monitor")


class DecisionMonitor:
    """
    Background monitor that runs on Railway.
    Scans every 60s, sends Telegram alerts for:
      - Approaching entry zone ($1 away)
      - Entry zone hit
      - Trade management (when user registers a trade via bot command)
    """

    def __init__(self, bot_token: str, channel_id: str):
        self.telegram = TelegramAlerts(bot_token, channel_id)
        self.bias_engine = BiasEngine()
        self.zone_detector = EntryZoneDetector()

        self.current_bias: Optional[MarketBias] = None
        self.current_zone: Optional[EntryZone] = None
        self.zones_today = 0
        self.last_zone_date = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start monitoring in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Decision Monitor started — scanning every %ds", SCAN_INTERVAL)

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Decision Monitor stopped")

    def _monitor_loop(self):
        """Main loop — runs every SCAN_INTERVAL seconds."""
        while self._running:
            try:
                result = self._scan_once()
                if result.get("actions"):
                    for action in result["actions"]:
                        logger.info("Action: %s", action)
                elif result.get("error"):
                    logger.warning("Scan error: %s", result["error"])
            except Exception as e:
                logger.error("Monitor scan failed: %s", e, exc_info=True)

            # Sleep in small increments so stop() is responsive
            for _ in range(SCAN_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)

    def _scan_once(self) -> Dict:
        """Single analysis + alert cycle."""
        now = datetime.now(timezone.utc)
        status: Dict = {"time": now.strftime("%H:%M:%S UTC"), "actions": []}

        # Reset daily counter
        if self.last_zone_date != now.date():
            self.zones_today = 0
            self.last_zone_date = now.date()

        # Session check — only scan during London + NY
        hour = now.hour
        active_session = None
        for name, (start, end) in SESSIONS.items():
            if start <= hour < end:
                active_session = name
                break

        if active_session is None:
            return status  # Silent outside killzones

        # Fetch live data
        price = fetch_price(api_key=TWELVE_DATA_API_KEY)
        if price is None or price == 0:
            status["error"] = "Cannot fetch price"
            return status

        m15 = fetch_bars(interval="15min", outputsize=200, api_key=TWELVE_DATA_API_KEY)
        h1 = fetch_bars(interval="1h", outputsize=100, api_key=TWELVE_DATA_API_KEY)

        if m15 is None or h1 is None:
            status["error"] = "Cannot fetch candle data"
            return status

        status["price"] = price
        status["session"] = active_session

        # A. Market Bias
        self.current_bias = self.bias_engine.analyze(m15, h1)
        status["bias"] = self.current_bias.bias
        status["strength"] = self.current_bias.strength

        # B. Entry Zone Detection (max 3/day)
        if self.zones_today < MAX_SETUPS_PER_DAY:
            zone = self.zone_detector.detect(m15, h1, self.current_bias, price)
            if zone and zone.confidence >= 50:
                # Only replace zone if we don't have one or old one expired
                if self.current_zone is None or self.current_zone.entered:
                    self.current_zone = zone
                    status["actions"].append(
                        f"New {zone.direction} zone: ${zone.entry_low:.2f}-${zone.entry_high:.2f}"
                    )
        elif self.zones_today >= MAX_SETUPS_PER_DAY:
            status["actions"].append("Max setups for today reached")

        # C. Zone Proximity Alerts
        if self.current_zone and not self.current_zone.entered:
            zone = self.current_zone
            in_zone = zone.entry_low <= price <= zone.entry_high

            if zone.direction == "BUY":
                approaching = (
                    zone.entry_low - ALERT_DISTANCE <= price <= zone.entry_high + ALERT_DISTANCE
                ) and not in_zone
            else:  # SELL
                approaching = (
                    zone.entry_low - ALERT_DISTANCE <= price <= zone.entry_high + ALERT_DISTANCE
                ) and not in_zone

            if in_zone:
                self.telegram.entry_zone_hit(
                    zone.direction, zone.entry_low, zone.entry_high, price
                )
                self.current_zone.entered = True
                self.zones_today += 1
                status["actions"].append(f"ENTRY ZONE HIT — {zone.direction}")

            elif approaching and not zone.triggered:
                self.telegram.approaching_zone(
                    zone.direction, self.current_bias.bias,
                    zone.entry_low, zone.entry_high, price,
                    zone.sl, zone.tp1, zone.tp2, zone.tp3,
                    zone.confidence, zone.session
                )
                self.current_zone.triggered = True
                status["actions"].append(f"APPROACHING — {zone.direction} zone")

        return status
