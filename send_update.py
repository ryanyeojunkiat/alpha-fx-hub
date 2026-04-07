"""One-time script to broadcast system upgrade announcement.
Run: python3 send_update.py
Delete after use.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_PUBLIC_CHANNEL_ID, TELEGRAM_PRIVATE_CHANNEL_ID
from telegram.notifications import NotificationManager

notifier = NotificationManager(
    bot_token=TELEGRAM_BOT_TOKEN,
    private_channel_id=TELEGRAM_PRIVATE_CHANNEL_ID,
    public_channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
)

msg = """
🚀 <b>ALPHA FX HUB — MAJOR UPDATE v2.1</b> 🚀

<b>Introducing: Gold Decision Assistant</b>
Your new semi-automated XAUUSD trading companion is LIVE.

━━━━━━━━━━━━━━━━━━━━━━━━━

🧠 <b>What's New:</b>

<b>1. Market Bias Engine</b>
Continuous H1 structure analysis — tells you if gold is Bullish (HH/HL), Bearish (LH/LL), or Neutral. Updated every 60 seconds with EMA50/200 alignment and ATR.

<b>2. Smart Entry Zone Detection</b>
Identifies high-probability entry zones based on liquidity sweeps + Fibonacci OTE pullbacks. Each zone includes entry range, SL, TP1/TP2/TP3, R:R ratio, and confidence score.

<b>3. Real-Time Telegram Alerts</b>
⏳ <b>Approaching Zone</b> — notifies when price is within $1 of an entry zone
🎯 <b>Zone Hit</b> — alerts when price enters the zone
📊 <b>Trade Management</b> — suggestions for SL trailing, partial close, exit

<b>4. Session-Filtered Precision</b>
Only scans during London (07-10 UTC) and New York (12-15 UTC) killzones. No noisy signals during Asian session. Max 3 setups per day.

<b>5. Trade Manager Dashboard</b>
Register your trades on the website. System tracks live P&L, detects TP hits (TP1 → close 50%, move SL to BE), warns on structure changes (CHoCH).

━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>IMPORTANT — This is NOT auto-trading.</b>
The system <b>assists</b> your decisions. YOU execute every trade.
Alerts are suggestions, not financial advice.

━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 <b>Access the Decision Assistant:</b>
Open Alpha FX Hub → Sidebar → 🤖 Decision Assistant

📡 Alerts are now running 24/7 during active sessions.

<i>Trade smart. Trade gold. Trade with an edge.</i>
💎 <b>Alpha FX Hub</b> | v2.1
""".strip()

print("Sending to PUBLIC channel...")
r1 = notifier.broadcast_public(msg)
print(f"  Public: {'✅ Sent' if r1 else '❌ Failed'}")

print("Sending to PRIVATE channel...")
r2 = notifier.broadcast(msg)
print(f"  Private: {'✅ Sent' if r2 else '❌ Failed'}")

if r1 and r2:
    print("\n🎉 Update announcement sent to both channels!")
    print("You can delete this file now: rm send_update.py")
