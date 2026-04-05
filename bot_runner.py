"""
Alpha FX Pilot — Standalone Bot Runner
Run this separately from the Streamlit app (e.g., on Render.com free tier).

Usage:
  python bot_runner.py

Environment variables required:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_PUBLIC_CHANNEL_ID
  TELEGRAM_PRIVATE_CHANNEL_ID
  ADMIN_TELEGRAM_IDS
"""
import os
import sys
import logging
import signal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

from telegram.bot import TelegramBot

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("bot_runner")

# ── Config from env ──
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PUBLIC_CHANNEL_ID = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID", "")
PRIVATE_CHANNEL_ID = os.environ.get("TELEGRAM_PRIVATE_CHANNEL_ID", "")
ADMIN_IDS = [
    int(x.strip()) for x in os.environ.get("ADMIN_TELEGRAM_IDS", "").split(",")
    if x.strip().isdigit()
]
FP_LINK = os.environ.get(
    "FP_MARKETS_LINK",
    "https://portal.fpmarkets.com/register?fpm-affiliate-utm-source=IB&fpm-affiliate-agt=66209"
)
FP_CODE = os.environ.get("FP_MARKETS_CODE", "M4-66209")
PUBLIC_LINK = "https://t.me/+CskTnfXWW4s1YWI1"
PRIVATE_LINK = "https://t.me/+6EFH7b6AJNNjNTQ1"


def main():
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set! Exiting.")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info("Alpha FX Pilot — Starting standalone bot")
    logger.info(f"Public channel:  {PUBLIC_CHANNEL_ID}")
    logger.info(f"Private channel: {PRIVATE_CHANNEL_ID}")
    logger.info(f"Admin IDs: {ADMIN_IDS}")
    logger.info("=" * 50)

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    bot = TelegramBot(
        bot_token=BOT_TOKEN,
        public_channel_id=PUBLIC_CHANNEL_ID,
        private_channel_id=PRIVATE_CHANNEL_ID,
        admin_ids=ADMIN_IDS,
        fp_link=FP_LINK,
        fp_code=FP_CODE,
        public_channel_link=PUBLIC_LINK,
        private_channel_link=PRIVATE_LINK,
        data_dir=data_dir,
    )

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down bot...")
        bot.stop_polling()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start polling (this runs in a background thread)
    bot.start_polling()
    logger.info("Bot is running. Press Ctrl+C to stop.")

    # Keep main thread alive
    import time
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
