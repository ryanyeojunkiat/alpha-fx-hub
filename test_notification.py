"""
Quick test — sends a TEST signal to both Telegram channels.
Run: python test_notification.py
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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PUBLIC_ID = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID", "")
PRIVATE_ID = os.environ.get("TELEGRAM_PRIVATE_CHANNEL_ID", "")

print(f"Bot token: {'SET' if BOT_TOKEN else 'MISSING'}")
print(f"Public channel: {PUBLIC_ID}")
print(f"Private channel: {PRIVATE_ID}")

notifier = NotificationManager(
    bot_token=BOT_TOKEN,
    private_channel_id=PRIVATE_ID,
    public_channel_id=PUBLIC_ID,
)

# ── Test 1: Signal to PRIVATE channel (Alpha FX Edge) ──
print("\n--- Sending TEST signal to Private Channel (Alpha FX Edge) ---")
test_signal = {
    "direction": "BUY",
    "mode": "SCALP",
    "grade": "A+",
    "score": 92,
    "confidence": "SNIPER",
    "entry_price": 3125.50,
    "sl": 3118.00,
    "risk_pips": 75,
    "entry_type": "MARKET",
    "tp_levels": [3128.50, 3131.00, 3134.00, 3137.00, 3141.00,
                  3146.00, 3152.00, 3158.00, 3165.00, 3173.00],
    "lot_conservative": 0.05,
    "lot_moderate": 0.08,
    "lot_aggressive": 0.13,
    "h4_trend": "BULLISH",
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

# ── Test 2: News to PUBLIC channel (Alpha FX Hub) ──
print("\n--- Sending TEST news to Public Channel (Alpha FX Hub) ---")
news_msg = """
📰 <b>GOLD MARKET UPDATE</b>

🔸 XAUUSD trading at $3,125 during London session
🔸 USD weakening on dovish Fed expectations
🔸 Key support: $3,100 | Resistance: $3,150
🔸 NFP data release Friday — expect volatility

⚠️ <i>This is a TEST notification from Alpha FX Hub.</i>

🌐 <b>Full analysis:</b> https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app
"""
result2 = notifier.broadcast_public(news_msg.strip())
print(f"News sent: {'SUCCESS' if result2 else 'FAILED'}")

print("\n✅ Done! Check both Telegram channels.")
