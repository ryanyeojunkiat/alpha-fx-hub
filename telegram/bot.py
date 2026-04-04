"""
Alpha FX Hub — Telegram Bot
Full onboarding flow + signal delivery + admin commands.
"""
import json
import logging
import os
import threading
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger("alpha_fx_hub.bot")

# Onboarding states
STATE_NEW = "new"
STATE_ASKED_CAPITAL = "asked_capital"
STATE_ASKED_EXPERIENCE = "asked_experience"
STATE_SENT_STEPS = "sent_steps"
STATE_WAITING_PROOF = "waiting_proof"
STATE_PENDING_APPROVAL = "pending_approval"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"


class TelegramBot:
    """
    Handles:
    1. User onboarding (capital check, referral, approval)
    2. Signal broadcasting
    3. Admin commands (/signal, /approve, /reject, /users, /stats)
    """

    def __init__(self, bot_token: str, channel_id: str, admin_ids: list,
                 fp_link: str, fp_code: str, data_dir: str = None):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.admin_ids = admin_ids
        self.fp_link = fp_link
        self.fp_code = fp_code
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.users = self._load_users()
        self._polling = False
        self._offset = 0

    def start_polling(self):
        """Start polling for messages in a background thread."""
        if self._polling or not self.bot_token:
            return
        self._polling = True
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()
        logger.info("Telegram bot polling started")

    def stop_polling(self):
        self._polling = False

    def _poll_loop(self):
        """Main polling loop."""
        while self._polling:
            try:
                resp = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": self._offset, "timeout": 30},
                    timeout=35,
                )
                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                updates = resp.json().get("result", [])
                for update in updates:
                    self._offset = update["update_id"] + 1
                    self._handle_update(update)

            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        """Route incoming messages."""
        msg = update.get("message", {})
        if not msg:
            return

        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()
        user_name = msg.get("from", {}).get("first_name", "Trader")

        # Admin commands
        if int(chat_id) in self.admin_ids:
            if text.startswith("/approve"):
                self._cmd_approve(chat_id, text)
                return
            elif text.startswith("/reject"):
                self._cmd_reject(chat_id, text)
                return
            elif text == "/users":
                self._cmd_users(chat_id)
                return
            elif text == "/stats":
                self._cmd_stats(chat_id)
                return

        # User commands / onboarding
        if text == "/start":
            self._start_onboarding(chat_id, user_name)
        elif text == "/status":
            self._cmd_status(chat_id)
        else:
            self._process_onboarding(chat_id, text, user_name)

    # ── ONBOARDING FLOW ─────────────────────────────────────
    def _start_onboarding(self, chat_id: str, name: str):
        """Welcome message + ask capital."""
        self.users[chat_id] = {
            "name": name,
            "state": STATE_ASKED_CAPITAL,
            "joined": datetime.now(timezone.utc).isoformat(),
            "capital": 0,
            "experience": "",
        }
        self._save_users()

        msg = f"""
Welcome to <b>Alpha FX Hub</b>, {name}! \U0001f31f

We provide professional XAUUSD (Gold) trading signals powered by our 17-module AI analysis engine.

To get started, I need to know:
<b>How much trading capital do you plan to deposit (in USD)?</b>

(Minimum: $500)
"""
        self._send(chat_id, msg.strip())

    def _process_onboarding(self, chat_id: str, text: str, name: str):
        """Process onboarding based on user's current state."""
        user = self.users.get(chat_id)
        if not user:
            self._start_onboarding(chat_id, name)
            return

        state = user.get("state", STATE_NEW)

        if state == STATE_ASKED_CAPITAL:
            try:
                capital = float(text.replace("$", "").replace(",", "").strip())
            except ValueError:
                self._send(chat_id, "Please enter a number (e.g., 1000 or $1,000):")
                return

            if capital < 500:
                self._send(chat_id,
                    "We require a minimum of <b>$500</b> starting capital to ensure "
                    "proper risk management with our signal system.\n\n"
                    "Please come back when you're ready with at least $500.")
                user["state"] = STATE_REJECTED
                user["capital"] = capital
                self._save_users()
                return

            user["capital"] = capital
            user["state"] = STATE_ASKED_EXPERIENCE
            self._save_users()
            self._send(chat_id,
                f"Great, ${capital:,.0f} is a solid starting capital.\n\n"
                "Quick question: <b>How long have you been trading?</b>\n"
                "a) Brand new\n"
                "b) Less than 1 year\n"
                "c) 1-3 years\n"
                "d) 3+ years")

        elif state == STATE_ASKED_EXPERIENCE:
            user["experience"] = text
            user["state"] = STATE_SENT_STEPS
            self._save_users()

            msg = f"""
Thanks! Here's how to get started:

<b>Step 1:</b> Open a trading account with FP Markets using our link:
{self.fp_link}

<b>Step 2:</b> Use referral code: <code>{self.fp_code}</code>

<b>Step 3:</b> Deposit your trading capital

<b>Step 4:</b> Send me a screenshot of your account dashboard showing:
  \u2022 Your account is active
  \u2022 The referral code is applied

Once verified, you'll receive:
  \u2713 Access to our premium signal channel
  \u2713 Alpha FX Hub trading manual
  \u2713 24/7 gold signals with entry, SL, and 10 TP levels
  \u2713 Real-time CHoCH alerts to protect your trades

Send your screenshot when ready!
"""
            self._send(chat_id, msg.strip())
            user["state"] = STATE_WAITING_PROOF

        elif state == STATE_WAITING_PROOF:
            # Any message at this point is treated as proof submission
            user["state"] = STATE_PENDING_APPROVAL
            user["proof_submitted"] = datetime.now(timezone.utc).isoformat()
            self._save_users()

            self._send(chat_id,
                "Thank you! Your registration is being reviewed by our admin.\n"
                "You'll be notified once approved (usually within 24 hours).")

            # Notify admins
            for admin_id in self.admin_ids:
                self._send(str(admin_id),
                    f"New registration pending:\n"
                    f"Name: {user['name']}\n"
                    f"Capital: ${user['capital']:,.0f}\n"
                    f"Experience: {user['experience']}\n"
                    f"Chat ID: {chat_id}\n\n"
                    f"Reply /approve {chat_id} or /reject {chat_id}")

        elif state == STATE_APPROVED:
            self._send(chat_id,
                "You're already approved! Check the signal channel for the latest signals.\n"
                "Use /status to check your account status.")

    # ── ADMIN COMMANDS ───────────────────────────────────────
    def _cmd_approve(self, admin_id: str, text: str):
        parts = text.split()
        if len(parts) < 2:
            self._send(admin_id, "Usage: /approve <chat_id>")
            return

        user_id = parts[1]
        if user_id in self.users:
            self.users[user_id]["state"] = STATE_APPROVED
            self.users[user_id]["approved_at"] = datetime.now(timezone.utc).isoformat()
            self._save_users()

            self._send(user_id,
                "Congratulations! You've been approved!\n\n"
                "You now have access to:\n"
                "\u2713 Premium XAUUSD signals\n"
                "\u2713 Real-time TP/SL notifications\n"
                "\u2713 CHoCH structure alerts\n"
                "\u2713 FVG entry opportunities\n\n"
                "Welcome to Alpha FX Hub!")
            self._send(admin_id, f"User {user_id} approved.")
        else:
            self._send(admin_id, f"User {user_id} not found.")

    def _cmd_reject(self, admin_id: str, text: str):
        parts = text.split()
        if len(parts) < 2:
            self._send(admin_id, "Usage: /reject <chat_id> [reason]")
            return

        user_id = parts[1]
        reason = " ".join(parts[2:]) or "Requirements not met"

        if user_id in self.users:
            self.users[user_id]["state"] = STATE_REJECTED
            self._save_users()
            self._send(user_id, f"Your registration was not approved.\nReason: {reason}")
            self._send(admin_id, f"User {user_id} rejected.")

    def _cmd_users(self, admin_id: str):
        approved = sum(1 for u in self.users.values() if u.get("state") == STATE_APPROVED)
        pending = sum(1 for u in self.users.values() if u.get("state") == STATE_PENDING_APPROVAL)
        total = len(self.users)
        self._send(admin_id,
            f"Users: {total} total\n"
            f"Approved: {approved}\n"
            f"Pending: {pending}")

    def _cmd_stats(self, admin_id: str):
        self._send(admin_id, "Use the web dashboard for full statistics.")

    def _cmd_status(self, chat_id: str):
        user = self.users.get(chat_id)
        if not user:
            self._send(chat_id, "You're not registered. Send /start to begin.")
            return
        state = user.get("state", "unknown")
        self._send(chat_id, f"Status: {state.replace('_', ' ').title()}")

    # ── HELPERS ──────────────────────────────────────────────
    def _send(self, chat_id: str, text: str) -> bool:
        if not self.bot_token:
            return False
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text,
                      "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=10,
            )
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    def _load_users(self) -> dict:
        path = self.data_dir / "users.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_users(self):
        try:
            with open(self.data_dir / "users.json", "w") as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            logger.error(f"Save users failed: {e}")

    def get_approved_users(self) -> list:
        """Get list of approved user chat IDs."""
        return [cid for cid, u in self.users.items() if u.get("state") == STATE_APPROVED]
