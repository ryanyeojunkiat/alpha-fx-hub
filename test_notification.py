"""
Quick test — sends a TEST signal + news to both Telegram channels.
Uses LIVE XAUUSD price from Twelve Data.
Run: python3 test_notification.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pathlib import Path

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from telegram.notifications import NotificationManager
from telegram.news_poster import build_hourly_update, _get_dynamic_levels
from engine.data import fetch_price, fetch_bars
from academy.calendar import fetch_economic_calendar

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PUBLIC_ID = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID", "")
PRIVATE_ID = os.environ.get("TELEGRAM_PRIVATE_CHANNEL_ID", "")
TD_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
TE_API_KEY = os.environ.get("TE_API_KEY", "")

print(f"Bot token: {'SET' if BOT_TOKEN else 'MISSING'}")
print(f"Public channel: {PUBLIC_ID}")
print(f"Private channel: {PRIVATE_ID}")
print(f"Twelve Data API: {'SET' if TD_API_KEY else 'MISSING'}")
print(f"TE API: {'SET' if TE_API_KEY else 'MISSING (will use demo data)'}")

notifier = NotificationManager(
    bot_token=BOT_TOKEN,
    private_channel_id=PRIVATE_ID,
    public_channel_id=PUBLIC_ID,
)

# ── Get live XAUUSD price ──
print("\n--- Fetching live XAUUSD price ---")
live_price = fetch_price(api_key=TD_API_KEY)
print(f"Live price: ${live_price:.2f}" if live_price else "Price fetch failed")

bars = fetch_bars(symbol="XAU/USD", interval="15min", outputsize=200, api_key=TD_API_KEY)
price_data = _get_dynamic_levels(bars) if bars is not None else {}

if price_data:
    print(f"24h High: ${price_data.get('high_24h', 0):.2f}")
    print(f"24h Low:  ${price_data.get('low_24h', 0):.2f}")
    print(f"Trend:    {price_data.get('trend', 'N/A')}")
    print(f"R1: ${price_data.get('r1', 0):.0f} | S1: ${price_data.get('s1', 0):.0f}")

current = price_data.get("current", live_price or 3200)

# ── Test 1: Signal to PRIVATE channel (Alpha FX Edge) ──
print("\n--- Sending TEST signal to Private Channel ---")

# Build realistic TPs based on live price
sl = round(current - 7.5, 2)
tps = [round(current + (3 * (i + 1)), 2) for i in range(10)]

test_signal = {
    "direction": "BUY",
    "mode": "SCALP",
    "grade": "A+",
    "score": 92,
    "confidence": "SNIPER",
    "entry_price": current,
    "sl": sl,
    "risk_pips": 75,
    "entry_type": "MARKET",
    "tp_levels": tps,
    "lot_conservative": 0.05,
    "lot_moderate": 0.08,
    "lot_aggressive": 0.13,
    "h4_trend": price_data.get("trend", "BULLISH").split()[-1] if price_data else "BULLISH",
    "killzone": "London_Open",
    "confirmations": 14,
    "contradictions": 1,
    "modules": {
        "supply_demand": {"score": 12, "zone": {"fresh": True}},
        "fvg": {"score": 8},
        "choch": {"score": 10},
        "bos": {"bos": True},
        "order_blocks": {"ob": True},
        "fibonacci": {"ote": True},
        "liquidity_sweep": {"detected": True},
        "rsi_divergence": {"type": "regular_bullish"},
        "displacement": {"score": 7},
    }
}

result = notifier.send_signal(test_signal)
print(f"Signal sent: {'SUCCESS' if result else 'FAILED'}")

# ── Test 2: Hourly news update to PUBLIC channel ──
print("\n--- Sending HOURLY NEWS UPDATE to Public Channel ---")
events = fetch_economic_calendar(api_key=TE_API_KEY)
news_msg = build_hourly_update(events, price_data, TD_API_KEY)
result2 = notifier.broadcast_public(news_msg)
print(f"News sent: {'SUCCESS' if result2 else 'FAILED'}")

print("\n✅ Done! Check both Telegram channels.")
