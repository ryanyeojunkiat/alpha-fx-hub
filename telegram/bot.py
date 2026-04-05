"""
Alpha FX Pilot — Telegram Bot
@alphaedge_gold_bot

Full onboarding flow with data collection, dual-channel system:
  PUBLIC channel (Alpha FX Hub): News + basic strategy for everyone
  PRIVATE channel (Alpha FX Edge): Premium signals for subscribers

Onboarding questions:
  1. Income range
  2. Trading experience
  3. Current job/industry
  4. Planned deposit amount (USD)
  5. Trading goals
  6. How did you find us
  7. FP Markets referral signup + proof

Admin commands: /approve, /reject, /users, /stats, /broadcast, /news
"""
import json
import logging
import os
import threading
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger("alpha_fx_hub.bot")

# ── Onboarding States ────────────────────────────────────────
STATE_NEW = "new"
STATE_Q1_INCOME = "q1_income"
STATE_Q2_EXPERIENCE = "q2_experience"
STATE_Q3_JOB = "q3_job"
STATE_Q4_DEPOSIT = "q4_deposit"
STATE_Q5_GOALS = "q5_goals"
STATE_Q6_SOURCE = "q6_source"
STATE_REFERRAL = "referral_signup"
STATE_WAITING_PROOF = "waiting_proof"
STATE_PENDING_APPROVAL = "pending_approval"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"


# ── Question Definitions ─────────────────────────────────────
QUESTIONS = {
    STATE_Q1_INCOME: {
        "question": (
            "<b>Question 1/6 — Monthly Income</b>\n\n"
            "What is your approximate monthly income?\n\n"
            "A) Below $1,000 USD\n"
            "B) $1,000 — $3,000 USD\n"
            "C) $3,000 — $5,000 USD\n"
            "D) $5,000 — $10,000 USD\n"
            "E) Above $10,000 USD\n\n"
            "<i>Reply with A, B, C, D, or E</i>"
        ),
        "field": "income",
        "valid": {"a": "Below $1,000", "b": "$1,000-$3,000", "c": "$3,000-$5,000",
                  "d": "$5,000-$10,000", "e": "Above $10,000"},
        "next": STATE_Q2_EXPERIENCE,
    },
    STATE_Q2_EXPERIENCE: {
        "question": (
            "<b>Question 2/6 — Trading Experience</b>\n\n"
            "How long have you been trading?\n\n"
            "A) Brand new — never traded before\n"
            "B) Less than 6 months\n"
            "C) 6 months — 1 year\n"
            "D) 1 — 3 years\n"
            "E) 3+ years (experienced)\n\n"
            "<i>Reply with A, B, C, D, or E</i>"
        ),
        "field": "experience",
        "valid": {"a": "Brand new", "b": "Less than 6 months", "c": "6 months - 1 year",
                  "d": "1-3 years", "e": "3+ years"},
        "next": STATE_Q3_JOB,
    },
    STATE_Q3_JOB: {
        "question": (
            "<b>Question 3/6 — Current Job</b>\n\n"
            "What industry do you work in?\n\n"
            "A) Finance / Banking\n"
            "B) Technology / IT\n"
            "C) Business Owner / Entrepreneur\n"
            "D) Healthcare / Medical\n"
            "E) Other (please type your job)\n\n"
            "<i>Reply with A, B, C, D, E, or type your answer</i>"
        ),
        "field": "job",
        "valid": {"a": "Finance/Banking", "b": "Technology/IT", "c": "Business Owner",
                  "d": "Healthcare/Medical", "e": "Other"},
        "next": STATE_Q4_DEPOSIT,
        "allow_freetext": True,
    },
    STATE_Q4_DEPOSIT: {
        "question": (
            "<b>Question 4/6 — Planned Deposit</b>\n\n"
            "How much are you planning to deposit for trading?\n"
            "<i>(Please enter the amount in USD, e.g. 500 or $1,000)</i>"
        ),
        "field": "deposit",
        "type": "amount",
        "next": STATE_Q5_GOALS,
    },
    STATE_Q5_GOALS: {
        "question": (
            "<b>Question 5/6 — Trading Goals</b>\n\n"
            "What do you want to achieve with gold trading?\n\n"
            "A) Side income — earn extra money consistently\n"
            "B) Full-time trading — replace my job income\n"
            "C) Learn to trade — education is my priority\n"
            "D) Grow my savings — long-term wealth building\n"
            "E) Other (please type)\n\n"
            "<i>Reply with A, B, C, D, E, or type your answer</i>"
        ),
        "field": "goals",
        "valid": {"a": "Side income", "b": "Full-time trading", "c": "Learn to trade",
                  "d": "Grow savings", "e": "Other"},
        "next": STATE_Q6_SOURCE,
        "allow_freetext": True,
    },
    STATE_Q6_SOURCE: {
        "question": (
            "<b>Question 6/6 — How Did You Find Us?</b>\n\n"
            "A) Social media (Instagram, TikTok, etc.)\n"
            "B) Friend / referral\n"
            "C) YouTube\n"
            "D) Google search\n"
            "E) Telegram search\n"
            "F) Other (please type)\n\n"
            "<i>Reply with A, B, C, D, E, F, or type your answer</i>"
        ),
        "field": "source",
        "valid": {"a": "Social media", "b": "Friend/Referral", "c": "YouTube",
                  "d": "Google search", "e": "Telegram search", "f": "Other"},
        "next": STATE_REFERRAL,
        "allow_freetext": True,
    },
}


class TelegramBot:
    """
    Alpha FX Pilot — the main Telegram bot.

    Handles:
    1. User onboarding with 6-question data collection
    2. FP Markets referral signup flow
    3. Dual-channel management (public + private)
    4. Admin commands
    5. Auto news posting to public channel
    """

    def __init__(self, bot_token: str, public_channel_id: str, private_channel_id: str,
                 admin_ids: list, fp_link: str, fp_code: str,
                 public_channel_link: str = "", private_channel_link: str = "",
                 data_dir: str = None):
        self.bot_token = bot_token
        self.public_channel_id = public_channel_id
        self.private_channel_id = private_channel_id
        self.admin_ids = admin_ids
        self.fp_link = fp_link
        self.fp_code = fp_code
        self.public_channel_link = public_channel_link or "https://t.me/+CskTnfXWW4s1YWI1"
        self.private_channel_link = private_channel_link or "https://t.me/+6EFH7b6AJNNjNTQ1"
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.users = self._load_users()
        self._polling = False
        self._offset = self._load_offset()
        self._lock_file = self.data_dir / ".bot_lock"
        self._offset_file = self.data_dir / ".bot_offset"

    # ═══════════════════════════════════════════════════════════
    # OFFSET PERSISTENCE — prevents re-processing old messages
    # ═══════════════════════════════════════════════════════════
    def _load_offset(self) -> int:
        """Load last processed offset from file so restarts skip old messages."""
        offset_file = (Path(self.data_dir) if hasattr(self, 'data_dir') else Path(__file__).parent.parent / "data") / ".bot_offset"
        try:
            if offset_file.exists():
                return int(offset_file.read_text().strip())
        except Exception:
            pass
        return 0

    def _save_offset(self):
        """Persist current offset to disk."""
        try:
            self._offset_file.write_text(str(self._offset))
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # FILE-BASED LOCK — only ONE polling process at a time
    # ═══════════════════════════════════════════════════════════
    def _acquire_lock(self) -> bool:
        """Try to acquire file lock. Returns True if this is the only poller."""
        try:
            import fcntl
            self._lock_fd = open(self._lock_file, 'w')
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True
        except (IOError, OSError):
            # Another process already holds the lock
            logger.info("Another bot process already polling — skipping")
            return False

    def _release_lock(self):
        """Release the file lock."""
        try:
            import fcntl
            if hasattr(self, '_lock_fd') and self._lock_fd:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # POLLING
    # ═══════════════════════════════════════════════════════════
    def start_polling(self):
        """Start polling for messages in a background thread."""
        if self._polling or not self.bot_token:
            return
        self._polling = True
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()
        logger.info("Alpha FX Pilot bot polling started")

    def stop_polling(self):
        self._polling = False
        self._release_lock()

    def _poll_loop(self):
        # Acquire file lock — if another process is already polling, exit
        if not self._acquire_lock():
            self._polling = False
            return

        # Flush any pending updates on startup so we don't replay old messages
        try:
            resp = requests.get(
                f"{self.base_url}/getUpdates",
                params={"offset": self._offset, "timeout": 0},
                timeout=10,
            )
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                if updates:
                    self._offset = updates[-1]["update_id"] + 1
                    self._save_offset()
                    logger.info(f"Flushed {len(updates)} old updates on startup")
        except Exception:
            pass

        while self._polling:
            try:
                resp = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={
                        "offset": self._offset,
                        "timeout": 30,
                        "allowed_updates": json.dumps(["message", "chat_join_request"]),
                    },
                    timeout=35,
                )
                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                updates = resp.json().get("result", [])
                for update in updates:
                    self._offset = update["update_id"] + 1
                    self._save_offset()
                    self._handle_update(update)

            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)

        self._release_lock()

    # ═══════════════════════════════════════════════════════════
    # MESSAGE ROUTING
    # ═══════════════════════════════════════════════════════════
    def _handle_update(self, update: dict):
        # Handle chat join requests (user clicked private channel link)
        join_req = update.get("chat_join_request")
        if join_req:
            self._handle_join_request(join_req)
            return

        msg = update.get("message", {})
        if not msg:
            return

        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "").strip()
        user_info = msg.get("from", {})
        user_name = user_info.get("first_name", "Trader")
        username = user_info.get("username", "")

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
            elif text.startswith("/broadcast"):
                self._cmd_broadcast(chat_id, text)
                return
            elif text.startswith("/news"):
                self._cmd_news(chat_id, text)
                return

        # User commands
        if text == "/start":
            self._start_onboarding(chat_id, user_name, username)
        elif text == "/status":
            self._cmd_status(chat_id)
        elif text == "/help":
            self._cmd_help(chat_id)
        elif text == "/guide":
            self._cmd_guide(chat_id)
        else:
            self._process_onboarding(chat_id, text, user_name, username)

    # ═══════════════════════════════════════════════════════════
    # ONBOARDING FLOW
    # ═══════════════════════════════════════════════════════════
    def _start_onboarding(self, chat_id: str, name: str, username: str = ""):
        """Welcome message and start question flow."""
        self.users[chat_id] = {
            "name": name,
            "username": username,
            "state": STATE_Q1_INCOME,
            "joined": datetime.now(timezone.utc).isoformat(),
            "answers": {},
        }
        self._save_users()

        welcome = f"""
\U0001f31f <b>Welcome to Alpha FX Hub!</b> \U0001f31f

Hi {name}! I'm <b>Alpha FX Pilot</b>, your personal assistant.

<b>Alpha FX Hub</b> is a professional XAUUSD (Gold) trading platform powered by our <b>Alpha FX Engine</b> — a 17-module AI signal system built with institutional Smart Money Concepts.

\U0001f4ca <b>What we provide:</b>
  \u2022 Real-time gold trading signals (A+ to B grade)
  \u2022 10-TP partial close system with trailing SL
  \u2022 CHoCH structure break alerts (RED & YELLOW)
  \u2022 FVG second-wave entry opportunities
  \u2022 Economic calendar with gold-impact analysis
  \u2022 Complete Trading Academy (beginner to advanced)

\U0001f4b0 <b>Subscription:</b> Currently in <b>FREE TRIAL</b> period!
(Regular price: $99 USD/month)

Before we get started, I have a few quick questions to better serve you.
Let's go! \U0001f680
"""
        self._send(chat_id, welcome.strip())
        time.sleep(0.5)

        # Send first question
        self._send(chat_id, QUESTIONS[STATE_Q1_INCOME]["question"])

    def _process_onboarding(self, chat_id: str, text: str, name: str, username: str = ""):
        """Process onboarding answers based on current state."""
        user = self.users.get(chat_id)
        if not user:
            self._start_onboarding(chat_id, name, username)
            return

        state = user.get("state", STATE_NEW)

        # Handle question states
        if state in QUESTIONS:
            q = QUESTIONS[state]
            answer = self._validate_answer(text, q)

            if answer is None:
                self._send(chat_id, "Please choose one of the options above, or type your answer.")
                return

            # Save answer
            user["answers"][q["field"]] = answer
            next_state = q["next"]
            user["state"] = next_state
            self._save_users()

            # If deposit question, validate amount
            if q.get("type") == "amount":
                user["answers"]["deposit_raw"] = text

            # Send confirmation + next question or move to referral
            if next_state in QUESTIONS:
                self._send(chat_id, f"\u2705 Got it!\n\n{QUESTIONS[next_state]['question']}")
            elif next_state == STATE_REFERRAL:
                self._send_referral_step(chat_id, user)

        elif state == STATE_REFERRAL:
            # They should be going to FP Markets — any reply moves to proof
            user["state"] = STATE_WAITING_PROOF
            self._save_users()
            self._send(chat_id,
                "\U0001f4f8 <b>Great!</b> Now please send me a screenshot showing:\n\n"
                "  \u2022 Your FP Markets account is active\n"
                "  \u2022 The referral code M4-66209 is applied\n\n"
                "You can send a screenshot or photo here.")

        elif state == STATE_WAITING_PROOF:
            # Any message (photo or text) is treated as proof
            user["state"] = STATE_PENDING_APPROVAL
            user["proof_submitted"] = datetime.now(timezone.utc).isoformat()
            self._save_users()

            self._send(chat_id,
                "\u2705 <b>Registration complete!</b>\n\n"
                "Your application is being reviewed.\n"
                "You'll be notified once approved (usually within a few hours).\n\n"
                "<b>\u261d\ufe0f IMPORTANT — Do this now:</b>\n"
                f"Click the private channel link below and tap <b>\"Request to Join\"</b>:\n"
                f"\U0001f449 {self.private_channel_link}\n"
                "<i>Once approved, you'll be added automatically — no extra steps needed.</i>\n\n"
                "\U0001f4e2 Also join our <b>public channel</b> for free gold news:\n"
                f"\U0001f449 {self.public_channel_link}\n\n"
                "\U0001f310 Explore our <b>web platform</b>:\n"
                "\U0001f449 https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app")

            # Notify admins
            self._notify_admins_new_user(chat_id, user)

        elif state == STATE_APPROVED:
            self._send(chat_id,
                "\u2705 You're already a member!\n\n"
                f"\U0001f4e2 Public Channel: {self.public_channel_link}\n"
                f"\U0001f510 Private Signals: {self.private_channel_link}\n"
                f"\U0001f310 Website: https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app\n\n"
                "Use /status to check your account. Use /help for commands.")

        elif state == STATE_REJECTED:
            self._send(chat_id,
                "Your previous application was not approved.\n"
                "Send /start to try again.")

    def _validate_answer(self, text: str, question: dict) -> Optional[str]:
        """Validate and normalize user answer."""
        text_lower = text.lower().strip()

        # Amount type (deposit question)
        if question.get("type") == "amount":
            try:
                amount = float(text_lower.replace("$", "").replace(",", "").replace("usd", "").strip())
                return f"${amount:,.0f} USD"
            except ValueError:
                return None

        # Multiple choice
        valid = question.get("valid", {})
        if text_lower in valid:
            return valid[text_lower]

        # Allow free text for some questions
        if question.get("allow_freetext") and len(text) >= 2:
            return text

        return None

    def _send_referral_step(self, chat_id: str, user: dict):
        """Send FP Markets + MT5 setup instructions."""
        answers = user.get("answers", {})
        deposit = answers.get("deposit", "N/A")

        # Message 1: Profile summary
        msg1 = f"""
\u2705 <b>All questions answered!</b> Thanks for sharing.

<b>Your Profile:</b>
  \U0001f4b0 Income: {answers.get('income', 'N/A')}
  \U0001f4c8 Experience: {answers.get('experience', 'N/A')}
  \U0001f4bc Job: {answers.get('job', 'N/A')}
  \U0001f4b5 Deposit: {deposit}
  \U0001f3af Goal: {answers.get('goals', 'N/A')}

Now let me guide you through setting up your trading account step by step! \U0001f447
"""
        self._send(chat_id, msg1.strip())
        time.sleep(1)

        # Message 2: FP Markets account setup
        msg2 = f"""
\U0001f3c6 <b>STEP 1 — Open FP Markets Account</b>

FP Markets is our trusted broker — tight spreads, fast execution, and MT5 support.

\u26a0\ufe0f <b>IMPORTANT for Malaysia users:</b>
Before opening the link, you MUST install <b>1.1.1.1</b> (Cloudflare WARP) app first and turn on the VPN.
  \u2022 iPhone: Search "1.1.1.1" in App Store
  \u2022 Android: Search "1.1.1.1" in Play Store
  \u2022 Turn it ON, then open the link below

<b>Registration Link (with our referral):</b>
\U0001f449 {self.fp_link}

<b>Referral Code:</b> <code>{self.fp_code}</code>

<b>How to register:</b>
1. Open the link above (VPN on for MY users)
2. Click "Open Live Account"
3. Fill in your details (name, email, phone)
4. Choose account type: <b>Standard</b>
5. Choose platform: <b>MetaTrader 5 (MT5)</b>
6. Choose leverage: <b>1:500</b> (recommended)
7. Base currency: <b>USD</b>
8. Complete verification (upload IC/passport)
9. Make sure referral code <code>{self.fp_code}</code> is applied

\u23f3 Verification usually takes 1-2 business days.
"""
        self._send(chat_id, msg2.strip())
        time.sleep(1)

        # Message 3: MT5 setup
        msg3 = """
\U0001f4f1 <b>STEP 2 — Install MetaTrader 5 (MT5)</b>

MT5 is the trading platform where you execute trades.

<b>Download MT5:</b>
  \u2022 iPhone: Search "MetaTrader 5" in App Store
  \u2022 Android: Search "MetaTrader 5" in Play Store
  \u2022 PC/Mac: https://www.metatrader5.com/en/download

<b>How to connect your FP Markets account:</b>
1. Open MT5 app
2. Tap "Settings" (gear icon) or "Accounts"
3. Tap "+ New Account" or "Login to existing account"
4. Search for broker: <b>FP Markets</b> or <b>FPMarkets-Live</b>
5. Enter your MT5 login number (from FP Markets email)
6. Enter your MT5 password
7. Tap "Sign In"

<b>You should see:</b>
  \u2713 Your account balance at the top
  \u2713 XAUUSD in the market list (search "XAUUSD" or "Gold")
  \u2713 Connection status: green icon = connected

\u2753 <i>Can't find XAUUSD? Make sure you selected MT5 (not MT4) when registering.</i>
"""
        self._send(chat_id, msg3.strip())
        time.sleep(1)

        # Message 4: Deposit + proof
        msg4 = f"""
\U0001f4b5 <b>STEP 3 — Deposit Your Trading Capital</b>

Deposit: {deposit}

<b>Deposit methods on FP Markets:</b>
  \u2022 Bank Transfer (0% fee, 1-2 days)
  \u2022 Credit/Debit Card (instant)
  \u2022 Skrill / Neteller (instant)
  \u2022 Crypto (USDT, BTC — instant)

<b>To deposit:</b>
1. Login to FP Markets Client Portal
2. Go to "Funding" > "Deposit"
3. Choose your method and amount
4. Follow the instructions

\U0001f4f8 <b>STEP 4 — Send Me Proof</b>

Once your account is set up and funded, send me a screenshot showing:
  \u2022 Your FP Markets dashboard (account is active)
  \u2022 OR your MT5 app showing your balance

Just send the screenshot as a photo here and I'll process your registration!

\u2753 <i>Already have an FP Markets account? Just send me a screenshot of your MT5 dashboard.</i>
"""
        self._send(chat_id, msg4.strip())

    def _notify_admins_new_user(self, chat_id: str, user: dict):
        """Notify all admins about a new registration."""
        answers = user.get("answers", {})
        admin_msg = f"""
\U0001f514 <b>NEW REGISTRATION</b>

Name: {user.get('name', 'Unknown')}
Username: @{user.get('username', 'N/A')}
Chat ID: {chat_id}
Joined: {user.get('joined', 'N/A')[:10]}

<b>Answers:</b>
  Income: {answers.get('income', 'N/A')}
  Experience: {answers.get('experience', 'N/A')}
  Job: {answers.get('job', 'N/A')}
  Deposit: {answers.get('deposit', 'N/A')}
  Goals: {answers.get('goals', 'N/A')}
  Source: {answers.get('source', 'N/A')}

Reply: /approve {chat_id} or /reject {chat_id}
"""
        for admin_id in self.admin_ids:
            self._send(str(admin_id), admin_msg.strip())

    # ═══════════════════════════════════════════════════════════
    # ADMIN COMMANDS
    # ═══════════════════════════════════════════════════════════
    def _cmd_approve(self, admin_id: str, text: str):
        parts = text.split()
        if len(parts) < 2:
            self._send(admin_id, "Usage: /approve <chat_id>")
            return

        user_id = parts[1]
        if user_id not in self.users:
            self._send(admin_id, f"User {user_id} not found.")
            return

        self.users[user_id]["state"] = STATE_APPROVED
        self.users[user_id]["approved_at"] = datetime.now(timezone.utc).isoformat()
        self._save_users()

        # Try to directly approve their pending join request first
        direct_added = self._approve_channel_request(user_id)

        if direct_added:
            # User was directly added — no link needed
            channel_line = "\n\u2705 <b>You've been added to Alpha FX Edge Private Channel!</b>\n<i>Check your Telegram chats — you should see it now.</i>\n"
            admin_note = "directly added to private channel"
        else:
            # No pending join request — send invite link as fallback
            invite_result = self._create_private_invite(user_id)
            if invite_result:
                channel_line = f"\n\U0001f511 <b>Click to join the Private Channel:</b>\n  \U0001f449 {invite_result}\n"
            else:
                channel_line = f"\n\U0001f510 <b>Join Private Channel:</b>\n  \U0001f449 {self.private_channel_link}\n"
            admin_note = "invite link sent (user hadn't clicked channel link yet)"

        # Message 1: Approval notification
        self._send(user_id, f"""
\U0001f389 <b>Congratulations! You've been APPROVED!</b>

Welcome to the Alpha FX family, {self.users[user_id].get('name', 'Trader')}!
{channel_line}
\U0001f4e2 <b>Public Channel:</b> {self.public_channel_link}
\U0001f310 <b>Web Platform:</b> https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app

Type /guide for our full Getting Started guide.
""".strip())

        # Message 2: Full Getting Started guide (auto-sent)
        time.sleep(1)
        self._send_guide(user_id)

        self._send(admin_id, f"\u2705 User {user_id} ({self.users[user_id].get('name')}) approved — {admin_note}.")

    def _cmd_reject(self, admin_id: str, text: str):
        parts = text.split()
        if len(parts) < 2:
            self._send(admin_id, "Usage: /reject <chat_id> [reason]")
            return

        user_id = parts[1]
        reason = " ".join(parts[2:]) or "Requirements not met at this time."

        if user_id in self.users:
            self.users[user_id]["state"] = STATE_REJECTED
            self._save_users()
            self._send(user_id,
                f"Thank you for your interest in Alpha FX Hub.\n\n"
                f"Unfortunately, your application was not approved at this time.\n"
                f"Reason: {reason}\n\n"
                f"You can still join our public channel for free content:\n"
                f"\U0001f449 {self.public_channel_link}\n\n"
                f"Send /start to reapply anytime.")
            self._send(admin_id, f"User {user_id} rejected.")
        else:
            self._send(admin_id, f"User {user_id} not found.")

    def _cmd_users(self, admin_id: str):
        total = len(self.users)
        approved = sum(1 for u in self.users.values() if u.get("state") == STATE_APPROVED)
        pending = sum(1 for u in self.users.values() if u.get("state") == STATE_PENDING_APPROVAL)
        onboarding = sum(1 for u in self.users.values() if u.get("state", "").startswith("q"))
        rejected = sum(1 for u in self.users.values() if u.get("state") == STATE_REJECTED)

        # Pending users detail
        pending_list = ""
        for cid, u in self.users.items():
            if u.get("state") == STATE_PENDING_APPROVAL:
                pending_list += f"\n  \u2022 {u.get('name', '?')} (@{u.get('username', 'N/A')}) — /approve {cid}"

        msg = f"""
\U0001f4ca <b>User Statistics</b>

Total users: {total}
\u2705 Approved: {approved}
\u23f3 Pending: {pending}
\U0001f4dd Onboarding: {onboarding}
\u274c Rejected: {rejected}
{f'<b>Pending approvals:</b>{pending_list}' if pending_list else ''}
"""
        self._send(admin_id, msg.strip())

    def _cmd_stats(self, admin_id: str):
        """Show detailed stats."""
        approved_users = [u for u in self.users.values() if u.get("state") == STATE_APPROVED]
        if not approved_users:
            self._send(admin_id, "No approved users yet.")
            return

        # Experience breakdown
        exp_counts = {}
        for u in approved_users:
            exp = u.get("answers", {}).get("experience", "Unknown")
            exp_counts[exp] = exp_counts.get(exp, 0) + 1

        # Source breakdown
        src_counts = {}
        for u in approved_users:
            src = u.get("answers", {}).get("source", "Unknown")
            src_counts[src] = src_counts.get(src, 0) + 1

        exp_str = "\n".join(f"  {k}: {v}" for k, v in exp_counts.items())
        src_str = "\n".join(f"  {k}: {v}" for k, v in src_counts.items())

        self._send(admin_id, f"""
\U0001f4ca <b>Detailed Stats ({len(approved_users)} approved)</b>

<b>Experience:</b>
{exp_str}

<b>Source:</b>
{src_str}
""".strip())

    def _cmd_broadcast(self, admin_id: str, text: str):
        """Admin broadcast to all approved users."""
        msg_text = text.replace("/broadcast", "", 1).strip()
        if not msg_text:
            self._send(admin_id, "Usage: /broadcast <message>")
            return

        count = 0
        for cid, u in self.users.items():
            if u.get("state") == STATE_APPROVED:
                self._send(cid, f"\U0001f4e2 <b>Alpha FX Hub Broadcast</b>\n\n{msg_text}")
                count += 1
        self._send(admin_id, f"Broadcast sent to {count} approved users.")

    def _cmd_news(self, admin_id: str, text: str):
        """Manually post news to public channel."""
        news_text = text.replace("/news", "", 1).strip()
        if not news_text:
            self._send(admin_id, "Usage: /news <your news message>")
            return

        result = self.post_to_public(f"\U0001f4f0 <b>Gold Market Update</b>\n\n{news_text}\n\n<i>— Alpha FX Hub</i>")
        self._send(admin_id, "News posted to public channel." if result else "Failed to post.")

    def _cmd_status(self, chat_id: str):
        user = self.users.get(chat_id)
        if not user:
            self._send(chat_id, "You're not registered. Send /start to begin.")
            return

        state = user.get("state", "unknown")
        state_display = {
            STATE_APPROVED: "\u2705 Approved — Full access",
            STATE_PENDING_APPROVAL: "\u23f3 Pending admin review",
            STATE_WAITING_PROOF: "\U0001f4f8 Waiting for your FP Markets screenshot",
            STATE_REJECTED: "\u274c Not approved — send /start to reapply",
        }
        status_text = state_display.get(state, f"Onboarding in progress ({state})")
        self._send(chat_id, f"<b>Your Status:</b> {status_text}")

    def _cmd_help(self, chat_id: str):
        is_admin = int(chat_id) in self.admin_ids
        msg = """
\u2753 <b>Alpha FX Pilot Commands</b>

/start — Begin registration
/guide — How to use Alpha FX Hub (full guide)
/status — Check your account status
/help — Show this help message
"""
        if is_admin:
            msg += """
<b>Admin Commands:</b>
/approve <chat_id> — Approve a user
/reject <chat_id> [reason] — Reject a user
/users — Show user statistics
/stats — Detailed user breakdown
/broadcast <message> — Send to all approved users
/news <message> — Post news to public channel
"""
        self._send(chat_id, msg.strip())

    def _cmd_guide(self, chat_id: str):
        """Send the full platform guide."""
        user = self.users.get(chat_id, {})
        if user.get("state") != STATE_APPROVED:
            self._send(chat_id, "Complete your registration first. Send /start to begin.")
            return
        self._send_guide(chat_id)

    def _send_guide(self, chat_id: str):
        """Send the comprehensive Getting Started guide (4 messages)."""

        # Part 1: Platform Overview + Website Registration
        self._send(chat_id, """
\U0001f4d6 <b>GETTING STARTED — ALPHA FX HUB</b>
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

\U0001f3af <b>What is Alpha FX Hub?</b>
A professional XAUUSD (Gold) trading signal platform powered by a 20-module institutional AI engine. We track smart money moves and deliver high-probability trade signals.

\U0001f4cd <b>Our Platform has 2 parts — you NEED both:</b>

<b>1\ufe0f\u20e3 Telegram</b> (you're here!)
  \u2022 <b>Alpha FX Hub</b> (Public) — Gold news, hourly market updates, economic calendar
  \u2022 <b>Alpha FX Edge</b> (Private) — LIVE trade signals + weekend predictions ONLY
  \u2022 <i>No chatting in channels — signals and news only</i>

<b>2\ufe0f\u20e3 Website Dashboard</b> \u2b07\ufe0f\u2b07\ufe0f <b>MUST REGISTER</b>
  \U0001f449 https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app

\u261d\ufe0f <b>You MUST create an account on the website to access:</b>
  \u2022 \U0001f4ca <b>Signal Dashboard</b> — See all active signals with charts
  \u2022 \U0001f3eb <b>Trading Academy</b> — Learn gold trading from beginner to advanced
  \u2022 \U0001f9ee <b>Risk Calculator</b> — Calculate exact lot size before every trade
  \u2022 \U0001f4c8 <b>Live Trade Tracker</b> — Track your open positions
  \u2022 \U0001f4c5 <b>Economic Calendar</b> — Upcoming events with gold impact analysis
  \u2022 \U0001f30d <b>Market Overview</b> — Live price, trend, support/resistance levels

\u26a0\ufe0f <b>Telegram gives you the signals. The website teaches you HOW to trade them properly.</b>
""".strip())

        time.sleep(1)

        # Part 2: Website Registration Steps
        self._send(chat_id, """
\U0001f310 <b>STEP 1: REGISTER ON OUR WEBSITE</b>
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

\u261d\ufe0f <b>Do this NOW before anything else:</b>

1\ufe0f\u20e3 Open our website:
  \U0001f449 https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app

2\ufe0f\u20e3 Click <b>"Sign Up"</b> and create your account
  \u2022 Use the same email you want for your trading journey
  \u2022 Set a strong password

3\ufe0f\u20e3 Log in and explore:
  \u2022 <b>\U0001f3eb Academy</b> — Start here if you're new to gold trading. Covers candlesticks, support/resistance, risk management, and our signal system
  \u2022 <b>\U0001f9ee Risk Calculator</b> — Enter your account balance + signal's SL to get exact lot sizes. USE THIS EVERY TRADE
  \u2022 <b>\U0001f4ca Dashboard</b> — See detailed signal charts and analysis
  \u2022 <b>\U0001f4c5 Calendar</b> — 1-month economic calendar with gold impact ratings

\U0001f4a1 <b>Pro tip:</b> Study the Academy BEFORE placing your first trade. Knowledge = money saved.
""".strip())

        time.sleep(1)

        # Part 3: How Signals Work
        self._send(chat_id, f"""
\U0001f4e1 <b>STEP 2: HOW TO FOLLOW OUR SIGNALS</b>
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

<b>When a signal fires in Alpha FX Edge, you'll see:</b>
  \U0001f7e2 BUY or \U0001f534 SELL direction
  \u2b50 Grade (A+ = best, A = strong)
  \U0001f3af Entry Price
  \U0001f6d1 Stop Loss (ALWAYS set this!)
  \U0001f4b0 10 Take Profit levels (TP1-TP10)
  \U0001f3e6 Institutional bias (COT + DXY analysis)

<b>6-Step Process:</b>
  1\ufe0f\u20e3 Signal appears in Alpha FX Edge
  2\ufe0f\u20e3 Go to <b>website Risk Calculator</b> \u2192 enter your balance + SL pips \u2192 get lot size
  3\ufe0f\u20e3 Open MT5 \u2192 enter trade at the Entry Price
  4\ufe0f\u20e3 Set your Stop Loss IMMEDIATELY
  5\ufe0f\u20e3 TP1 hits? Close 30%, move SL to breakeven
  6\ufe0f\u20e3 Let remaining position ride with trailing SL

\u26a0\ufe0f <b>NEVER trade without a Stop Loss. NEVER risk more than 2-3% per trade.</b>
\U0001f4a1 <b>Not sure about something? Check the Academy on the website — it covers everything.</b>
""".strip())

        time.sleep(1)

        # Part 4: MT5 Setup + Quick Links
        self._send(chat_id, f"""
\U0001f4f1 <b>STEP 3: MT5 BROKER SETUP</b>
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

<b>Step 1:</b> Download MetaTrader 5 (MT5)
  \u2022 iPhone: App Store \u2192 "MetaTrader 5"
  \u2022 Android: Play Store \u2192 "MetaTrader 5"
  \u2022 PC: mt5.com/en/download

<b>Step 2:</b> Open MT5 and search for broker:
  \U0001f50d <b>First Prudential Markets Limited - SC Live</b>

<b>Step 3:</b> Log in with your FP Markets account
  (If you haven't registered yet, use our link):
  \U0001f449 {self.fp_link}
  Referral code: <code>{self.fp_code}</code>

<b>Step 4:</b> Find <b>XAUUSD</b> in Market Watch
  Long press \u2192 New Order \u2192 Enter trade details

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

\u2705 <b>CHECKLIST — Make sure you've done all 3:</b>
  \u2610 Registered on our website (signal dashboard + academy)
  \u2610 Joined Alpha FX Edge private channel (live signals)
  \u2610 Set up MT5 with FP Markets broker

\U0001f517 <b>QUICK LINKS:</b>
  \U0001f310 Website: https://alpha-fx-app-nwontubrtr6mymaqfdtknx.streamlit.app
  \U0001f4e2 Public Channel: {self.public_channel_link}
  \U0001f510 Private Signals: {self.private_channel_link}
  \U0001f4b1 FP Markets: {self.fp_link}

\U0001f4ac <b>Bot Commands:</b>
  /guide — See this guide again
  /status — Check your membership status
  /help — All available commands

\U0001f947 Trade smart. Protect your capital. Let's grow together!
""".strip())

    # ═══════════════════════════════════════════════════════════
    # CHANNEL POSTING
    # ═══════════════════════════════════════════════════════════
    def post_to_public(self, text: str) -> bool:
        """Post a message to the PUBLIC channel (Alpha FX Hub)."""
        return self._send(self.public_channel_id, text)

    def post_to_private(self, text: str) -> bool:
        """Post a message to the PRIVATE channel (Alpha FX Edge)."""
        return self._send(self.private_channel_id, text)

    def post_news_auto(self, events: list) -> bool:
        """Auto-post Trading Economics news to public channel."""
        if not events:
            return False

        msg = "\U0001f4f0 <b>Gold Market News — Economic Calendar</b>\n\n"
        for event in events[:5]:  # Top 5 events
            importance = event.get("importance", 0)
            stars = "\u2b50" * min(importance, 3)
            name = event.get("event", "Unknown")
            country = event.get("country", "")
            date_str = event.get("date", "")[:10]
            impact = event.get("gold_impact", {})
            typical = impact.get("typical_impact", "")

            msg += f"{stars} <b>{name}</b>"
            if country:
                msg += f" ({country})"
            msg += f"\n  Date: {date_str}"
            if typical:
                msg += f"\n  Gold Impact: {typical}"
            msg += "\n\n"

        msg += "<i>Stay informed. Trade smart.\n— Alpha FX Hub</i>"
        return self.post_to_public(msg)

    def post_strategy_tip(self, tip: str) -> bool:
        """Post a trading strategy tip to the public channel."""
        msg = f"\U0001f4a1 <b>Gold Trading Tip</b>\n\n{tip}\n\n<i>— Alpha FX Hub Academy</i>"
        return self.post_to_public(msg)

    # ═══════════════════════════════════════════════════════════
    # CHANNEL MANAGEMENT
    # ═══════════════════════════════════════════════════════════
    def _handle_join_request(self, join_req: dict):
        """Handle when a user clicks the private channel link and requests to join.
        If already approved, auto-accept. Otherwise, note the pending request."""
        user = join_req.get("from", {})
        user_id = str(user.get("id", ""))
        chat_id = str(join_req.get("chat", {}).get("id", ""))
        user_name = user.get("first_name", "Unknown")

        logger.info(f"Join request from {user_name} ({user_id}) for chat {chat_id}")

        # If user is already approved, accept them immediately
        if user_id in self.users and self.users[user_id].get("state") == STATE_APPROVED:
            success = self._approve_channel_request(user_id)
            if success:
                logger.info(f"Auto-approved join request for already-approved user {user_id}")
                self._send(user_id, "\u2705 You've been added to the private channel! Check your chats.")
            return

        # Otherwise, mark that they have a pending join request (for when admin approves later)
        if user_id in self.users:
            self.users[user_id]["has_join_request"] = True
            self._save_users()
            logger.info(f"Stored pending join request for user {user_id}")

    def _approve_channel_request(self, user_id: str) -> bool:
        """Directly approve a user's pending join request for the private channel.
        Requires the private channel to have 'Approve New Members' enabled."""
        if not self.private_channel_id:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/approveChatJoinRequest",
                json={
                    "chat_id": self.private_channel_id,
                    "user_id": int(user_id),
                },
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info(f"Approved join request for user {user_id} — added to private channel")
                return True
            logger.warning(f"approveChatJoinRequest failed for {user_id}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Approve join request error: {e}")
            return False

    def _create_private_invite(self, user_id: str) -> Optional[str]:
        """Fallback: create a one-time invite link if direct approval fails."""
        if not self.private_channel_id:
            return None
        try:
            resp = requests.post(
                f"{self.base_url}/createChatInviteLink",
                json={
                    "chat_id": self.private_channel_id,
                    "member_limit": 1,
                    "creates_join_request": False,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result", {}).get("invite_link"):
                    link = data["result"]["invite_link"]
                    logger.info(f"Created fallback invite for user {user_id}: {link}")
                    return link
            return None
        except Exception as e:
            logger.error(f"Create invite error: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════
    def _send(self, chat_id: str, text: str) -> bool:
        if not self.bot_token or not chat_id:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text,
                      "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.error(f"Telegram API error: {resp.text}")
                return False
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
            self.data_dir.mkdir(exist_ok=True)
            with open(self.data_dir / "users.json", "w") as f:
                json.dump(self.users, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Save users failed: {e}")

    def get_approved_users(self) -> list:
        return [cid for cid, u in self.users.items() if u.get("state") == STATE_APPROVED]

    def get_user_count(self) -> dict:
        total = len(self.users)
        approved = sum(1 for u in self.users.values() if u.get("state") == STATE_APPROVED)
        pending = sum(1 for u in self.users.values() if u.get("state") == STATE_PENDING_APPROVAL)
        return {"total": total, "approved": approved, "pending": pending}
