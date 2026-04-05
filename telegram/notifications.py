"""
Alpha FX Hub — Telegram Notification Manager
Handles all alert types:
  RED ALERT:    H1 CHoCH — structure broken against your trade
  YELLOW:       M15 CHoCH — early warning
  GREEN:        TP hit notifications with partial close details
  BLUE:         FVG second-wave entry opportunity
  WHITE:        General info / signal broadcast
"""
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("alpha_fx_hub.notifications")


class NotificationManager:
    """Sends formatted Telegram notifications for all alert types.

    Dual-channel system:
      - Public (Alpha FX Hub): news, tips, general updates
      - Private (Alpha FX Edge): signals, TP alerts, CHoCH warnings
    """

    def __init__(self, bot_token: str, private_channel_id: str = "",
                 public_channel_id: str = ""):
        self.bot_token = bot_token
        self.private_channel_id = private_channel_id
        self.public_channel_id = public_channel_id
        # Legacy: channel_id maps to private for backward compat
        self.channel_id = private_channel_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a Telegram chat/channel."""
        if not self.bot_token:
            logger.warning("No Telegram bot token configured")
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id or self.private_channel_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def broadcast(self, text: str) -> bool:
        """Broadcast to PRIVATE channel (Alpha FX Edge — premium signals)."""
        return self.send(self.private_channel_id, text)

    def broadcast_public(self, text: str) -> bool:
        """Broadcast to PUBLIC channel (Alpha FX Hub — news & tips)."""
        return self.send(self.public_channel_id, text)

    # ── SIGNAL BROADCAST ────────────────────────────────────
    def send_signal(self, signal: dict) -> bool:
        """Send a new trading signal to the channel."""
        confidence_emoji = {
            "SNIPER": "\U0001f3af",  # target
            "HIGH": "\U0001f7e2",    # green circle
            "MEDIUM": "\U0001f7e1",  # yellow circle
        }
        direction_emoji = "\U0001f7e2" if signal["direction"] == "BUY" else "\U0001f534"
        grade = signal.get("grade", "")
        conf = signal.get("confidence", "MEDIUM")

        # Build TP levels string
        tp_levels = signal.get("tp_levels", [])
        tp_str = ""
        for i, tp in enumerate(tp_levels[:10], 1):
            tp_str += f"  TP{i}: <b>${tp:.2f}</b>\n"

        # Build reasoning string
        modules = signal.get("modules", {})
        reasons = []
        if modules.get("supply_demand", {}).get("score", 0) > 0:
            zone = modules["supply_demand"].get("zone", {})
            if zone:
                reasons.append(f"S/D Zone ({'Fresh' if zone.get('fresh') else 'Tested'})")
        if modules.get("fvg", {}).get("score", 0) > 0:
            reasons.append("Fair Value Gap")
        if modules.get("choch", {}).get("score", 0) > 0:
            reasons.append("CHoCH Confirmed")
        if modules.get("bos", {}).get("bos"):
            reasons.append("Break of Structure")
        if modules.get("order_blocks", {}).get("ob"):
            reasons.append("Order Block")
        if modules.get("fibonacci", {}).get("ote"):
            reasons.append("Optimal Trade Entry (OTE)")
        elif modules.get("fibonacci", {}).get("golden_pocket"):
            reasons.append("Golden Pocket")
        if modules.get("liquidity_sweep", {}).get("detected"):
            reasons.append("Liquidity Sweep")
        if modules.get("rsi_divergence", {}).get("type"):
            reasons.append(modules["rsi_divergence"]["type"].replace("_", " ").title())
        if modules.get("displacement", {}).get("score", 0) > 0:
            reasons.append("Displacement Candle")

        reason_str = "\n".join(f"  \u2713 {r}" for r in reasons) if reasons else "  Multi-factor confluence"

        msg = f"""
{direction_emoji} <b>ALPHA FX HUB SIGNAL</b> {confidence_emoji.get(conf, '')}

<b>{signal['direction']} XAUUSD</b>  |  {signal.get('mode', 'SCALP')}
Grade: <b>{grade}</b>  |  Score: <b>{signal.get('score', 0)}/100</b>
Confidence: <b>{conf}</b>

Entry: <b>${signal['entry_price']:.2f}</b> ({signal.get('entry_type', 'MARKET')})
Stop Loss: <b>${signal['sl']:.2f}</b>
Risk: <b>{signal.get('risk_pips', 0)} pips</b>

<b>Take Profit Levels:</b>
{tp_str}
<b>Why This Signal:</b>
{reason_str}

<b>Position Size (Recommended):</b>
  Conservative (2%): {signal.get('lot_conservative', 0.01)} lot
  Moderate (3%): {signal.get('lot_moderate', 0.01)} lot
  Aggressive (5%): {signal.get('lot_aggressive', 0.01)} lot

H4 Trend: {signal.get('h4_trend', 'N/A')} | KZ: {signal.get('killzone', 'N/A')}
{signal.get('confirmations', 0)} confirmations | {signal.get('contradictions', 0)} contradictions

\u26a0\ufe0f <i>Risk Disclaimer: Trade at your own risk. Past signals do not guarantee future results.</i>

\U0001f4ca <b>Alpha FX Hub</b> | Gold Signal Engine V4
"""
        return self.broadcast(msg.strip())

    # ── RED ALERT: H1 CHoCH ─────────────────────────────────
    def send_choch_red_alert(self, alert: dict, trade: dict) -> bool:
        """Send RED ALERT for H1 CHoCH against open trade."""
        msg = f"""
\U0001f534\U0001f534\U0001f534 <b>RED ALERT — STRUCTURE BROKEN</b> \U0001f534\U0001f534\U0001f534

<b>H1 Change of Character Detected!</b>

{alert.get('message', '')}

<b>Your Open Position:</b>
  Direction: {trade.get('direction', 'N/A')}
  Entry: ${trade.get('entry_price', 0):.2f}
  Current SL: ${trade.get('sl', 0):.2f}
  TPs Hit: {trade.get('tp_hit', 0)}/10

<b>Recommended Action:</b>
  \u2022 Tighten stop loss immediately
  \u2022 Consider partial/full exit
  \u2022 Wait for H1 candle close confirmation

<i>This is an automated structural alert from Alpha FX Hub.</i>
"""
        return self.broadcast(msg.strip())

    # ── YELLOW WARNING: M15 CHoCH ───────────────────────────
    def send_choch_yellow_warning(self, alert: dict, trade: dict) -> bool:
        """Send YELLOW WARNING for M15 CHoCH."""
        msg = f"""
\U0001f7e1 <b>EARLY WARNING — M15 Structure Shift</b>

{alert.get('message', '')}

<b>Your Position:</b> {trade.get('direction', '')} @ ${trade.get('entry_price', 0):.2f}
<b>Current SL:</b> ${trade.get('sl', 0):.2f}

<b>H1 Structure:</b> {'Still intact' if not alert.get('h1_broken') else 'ALSO BROKEN'}

<i>Monitor closely. H1 structure is the key timeframe.</i>
"""
        return self.broadcast(msg.strip())

    # ── GREEN: TP HIT ───────────────────────────────────────
    def send_tp_hit(self, tp_num: int, action: dict, trade: dict) -> bool:
        """Send TP hit notification with partial close details."""
        msg = f"""
\U0001f7e2 <b>TP{tp_num} REACHED!</b>

<b>XAUUSD {trade.get('direction', '')}</b>
  Entry: ${trade.get('entry_price', 0):.2f}
  TP{tp_num}: ${action.get('tp_price', 0):.2f}

<b>Action Taken:</b>
  Closed: {action.get('closed_lot', 0)} lot
  Remaining: {action.get('remaining_lot', 0)} lot
  Profit: +${action.get('pnl_usd', 0):.2f} (+{action.get('pnl_pips', 0)} pips)

<b>Stop Loss Update:</b>
  {'Moved to BREAKEVEN' if tp_num == 1 else f"Trailed to ${trade.get('sl', 0):.2f}"}

\U0001f4b0 Running total: {tp_num}/10 TPs hit
{tp_num * chr(0x1f7e9)}{(10 - tp_num) * chr(0x2b1c)}

<b>Alpha FX Hub</b> | Partial Close Strategy
"""
        return self.broadcast(msg.strip())

    # ── BLUE: FVG ENTRY OPPORTUNITY ─────────────────────────
    def send_fvg_entry(self, opportunity: dict) -> bool:
        """Send FVG second-wave entry alert."""
        msg = f"""
\U0001f535 <b>FVG ENTRY OPPORTUNITY</b>

<b>{opportunity.get('direction', '')} XAUUSD</b>
Type: Institution Displacement + FVG Retest

<b>FVG Zone:</b> ${opportunity.get('fvg_bottom', 0):.2f} — ${opportunity.get('fvg_top', 0):.2f}
<b>Optimal Entry:</b> ${opportunity.get('optimal_entry', 0):.2f}
<b>Current Price:</b> ${opportunity.get('current_price', 0):.2f}
<b>Distance:</b> {opportunity.get('distance_pips', 0)} pips

{opportunity.get('message', '')}

<i>Set a LIMIT order at the optimal entry level for the best fill.</i>

<b>Alpha FX Hub</b> | Smart Money Concepts
"""
        return self.broadcast(msg.strip())

    # ── TRADE CLOSE SUMMARY ─────────────────────────────────
    def send_trade_closed(self, trade: dict) -> bool:
        """Send trade close summary."""
        pnl = trade.get("pnl_usd", 0)
        emoji = "\U0001f4b0" if pnl > 0 else "\U0001f534"

        msg = f"""
{emoji} <b>TRADE CLOSED</b>

<b>XAUUSD {trade.get('direction', '')}</b>
  Entry: ${trade.get('entry_price', 0):.2f}
  Exit Reason: {trade.get('close_reason', 'Unknown')}
  TPs Hit: {trade.get('tp_hit', 0)}/10

<b>Result:</b>
  PnL: {'+'  if pnl > 0 else ''}${pnl:.2f}
  Pips: {'+'  if trade.get('pnl_pips', 0) > 0 else ''}{trade.get('pnl_pips', 0)}
  Grade: {trade.get('grade', 'N/A')}

<b>Alpha FX Hub</b> | Trade Complete
"""
        return self.broadcast(msg.strip())

    # ── DAILY SUMMARY ───────────────────────────────────────
    def send_daily_summary(self, stats: dict) -> bool:
        """Send daily performance summary."""
        msg = f"""
\U0001f4ca <b>DAILY SUMMARY — Alpha FX Hub</b>

<b>Today's Performance:</b>
  Trades: {stats.get('total_trades', 0)}
  Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}
  Win Rate: {stats.get('win_rate', 0)}%
  PnL: {'+'  if stats.get('total_pnl', 0) > 0 else ''}${stats.get('total_pnl', 0):.2f}

<b>Account:</b>
  Balance: ${stats.get('balance', 0):.2f}
  Drawdown: {stats.get('drawdown_pct', 0)}%
  Profit Factor: {stats.get('profit_factor', 0)}

<b>Alpha FX Hub</b> | Daily Report
"""
        return self.broadcast(msg.strip())
