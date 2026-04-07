"""
Alpha FX Hub — Telegram Notification Manager V2
Upgraded for multi-symbol + Grok AI integration.

Alert Types:
  GOLD SIGNAL:  A+ signal with Grok AI verdict + full reasoning
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

    # ── V2 SIGNAL WITH GROK AI VERDICT ─────────────────────
    def send_signal_v2(self, signal: dict, grok_verdict: dict = None) -> bool:
        """Send A+ trading signal with Grok AI verdict + full reasoning.

        Args:
            signal: Signal dict with keys: symbol, direction, grade, score,
                    confidence, entry_price, sl, tp_levels, modules,
                    risk_pips, mode, layered config, etc.
            grok_verdict: Grok confirm_signal result dict with keys:
                    confirmed, agreement, confidence, reasoning, adjustments
        """
        symbol = signal.get("symbol", "XAUUSD")
        direction = signal["direction"]
        grade = signal.get("grade", "")
        score = signal.get("score", 0)
        conf = signal.get("confidence", "MEDIUM")
        mode = signal.get("mode", "SCALP")

        direction_emoji = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
        confidence_emoji = {
            "SNIPER": "\U0001f3af",
            "HIGH": "\U0001f7e2",
            "MEDIUM": "\U0001f7e1",
        }

        # ── Build TP levels string ──
        tp_levels = signal.get("tp_levels", [])
        tp_str = ""
        for i, tp in enumerate(tp_levels[:10], 1):
            tp_str += f"  TP{i}: <b>${tp:.2f}</b>\n"

        # ── Layered order info ──
        layered_str = ""
        num_orders = signal.get("num_orders", 5)
        lot_size = signal.get("lot_size", 0.01)
        sl_pips = signal.get("risk_pips", 200)
        pip_value = signal.get("pip_value", 0.10)
        total_risk = lot_size * pip_value * sl_pips * num_orders
        layered_str = f"""
<b>\u2b50 Layered Orders:</b>
  {num_orders}x {lot_size} lot @ same entry
  SL: {sl_pips} pips | Total Risk: ${total_risk:.2f}
  TP1 hit \u2192 Move SL to BE + 2 pips"""

        # ── Build engine reasoning ("Why This Trade") ──
        modules = signal.get("modules", {})
        reasons = []

        # Callisto TRC Framework
        trc = modules.get("trc", {})
        if trc.get("score", 0) > 0:
            active = [k for k in ["trend", "reversal", "continuation"] if trc.get(k)]
            reasons.append(f"\u2b50 TRC: {'+'.join(active)} ({trc.get('count', 0)}/3 MTF)")

        # Standard modules
        module_checks = [
            ("mtf_alignment", "Multi-TF Alignment", lambda m: m.get("score", 0) > 0),
            ("supply_demand", "S/D Zone", lambda m: m.get("score", 0) > 0),
            ("fvg", "Fair Value Gap", lambda m: m.get("score", 0) > 0),
            ("choch", "CHoCH Confirmed", lambda m: m.get("score", 0) > 0),
            ("bos", "Break of Structure", lambda m: m.get("bos")),
            ("order_blocks", "Order Block", lambda m: m.get("ob")),
            ("fibonacci", "Optimal Trade Entry", lambda m: m.get("ote")),
            ("liquidity_sweep", "Liquidity Sweep", lambda m: m.get("detected")),
            ("rsi_divergence", "RSI Divergence", lambda m: m.get("type")),
            ("displacement", "Displacement Candle", lambda m: m.get("score", 0) > 0),
            ("killzone", "ICT Killzone Active", lambda m: m.get("score", 0) > 0),
            ("momentum", "Strong Momentum", lambda m: m.get("score", 0) > 0),
            ("premium_discount", "Premium/Discount Zone", lambda m: m.get("score", 0) > 0),
            ("breaker_block", "Breaker Block", lambda m: m.get("score", 0) > 0),
            ("wcr_range", "WCR Range", lambda m: m.get("score", 0) > 0),
        ]
        for key, label, check in module_checks:
            mod = modules.get(key, {})
            if check(mod):
                reasons.append(f"\u2713 {label}")

        reason_str = "\n".join(f"  {r}" for r in reasons) if reasons else "  Multi-factor confluence"
        confirmations = signal.get("confirmations", len(reasons))
        contradictions = signal.get("contradictions", 0)

        # ── Build Grok AI verdict section ──
        grok_str = ""
        if grok_verdict:
            g_confirmed = grok_verdict.get("confirmed", False)
            g_agreement = grok_verdict.get("agreement", "CAUTION")
            g_conf = grok_verdict.get("confidence", 0)
            g_reasoning = grok_verdict.get("reasoning", "No reasoning provided")

            if g_confirmed:
                grok_icon = "\u2705"
                grok_label = "APPROVED"
            elif g_agreement == "DISAGREE":
                grok_icon = "\u274c"
                grok_label = "NOT APPROVED"
            else:
                grok_icon = "\u26a0\ufe0f"
                grok_label = "CAUTION"

            grok_str = f"""
\U0001f9e0 <b>GROK AI VERDICT: {grok_icon} {grok_label}</b>
  Confidence: {g_conf}%
  <i>{g_reasoning}</i>"""

            # Grok adjustments
            adj = grok_verdict.get("adjustments", {})
            if adj:
                adj_notes = adj.get("notes", "")
                adj_sl = adj.get("sl_adjust", "")
                adj_entry = adj.get("entry_adjust", "")
                if adj_notes or adj_sl or adj_entry:
                    grok_str += "\n  <b>Grok Suggests:</b>"
                    if adj_sl:
                        grok_str += f"\n    SL: {adj_sl}"
                    if adj_entry:
                        grok_str += f"\n    Entry: {adj_entry}"
                    if adj_notes:
                        grok_str += f"\n    {adj_notes}"
        else:
            grok_str = "\n\U0001f9e0 <i>Grok AI: Not available for this signal</i>"

        # ── Compose full message ──
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        msg = f"""{direction_emoji} <b>ALPHA FX HUB — A+ SIGNAL</b> {confidence_emoji.get(conf, '')}

<b>{direction} {symbol}</b>  |  {mode}
Grade: <b>{grade}</b>  |  Score: <b>{score}/100</b>
Confidence: <b>{conf}</b>

<b>\U0001f4cd Entry:</b> <b>${signal['entry_price']:.2f}</b>
<b>\U0001f6d1 Stop Loss:</b> <b>${signal['sl']:.2f}</b> ({sl_pips} pips)

<b>\U0001f3af Take Profit Levels:</b>
{tp_str}{layered_str}

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
<b>\U0001f4a1 WHY THIS TRADE:</b>
{reason_str}
  {confirmations} confirmations | {contradictions} contradictions

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
{grok_str}

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
\u26a0\ufe0f <i>Risk Disclaimer: Trade at your own risk. Only trade with capital you can afford to lose.</i>

\U0001f4ca <b>Alpha FX Hub</b> V6 Callisto + Grok AI | {now}"""

        return self.broadcast(msg.strip())

    # ── LEGACY SIGNAL (backward compatible) ─────────────────
    def send_signal(self, signal: dict) -> bool:
        """Send signal (legacy format). Redirects to V2 without Grok."""
        return self.send_signal_v2(signal, grok_verdict=None)

    # ── RED ALERT: H1 CHoCH ─────────────────────────────────
    def send_choch_red_alert(self, alert: dict, trade: dict) -> bool:
        """Send RED ALERT for H1 CHoCH against open trade."""
        symbol = trade.get("symbol", "XAUUSD")
        msg = f"""
\U0001f534\U0001f534\U0001f534 <b>RED ALERT — STRUCTURE BROKEN</b> \U0001f534\U0001f534\U0001f534

<b>H1 Change of Character Detected!</b>
<b>Symbol:</b> {symbol}

{alert.get('message', '')}

<b>Your Open Position:</b>
  Direction: {trade.get('direction', 'N/A')}
  Entry: ${trade.get('entry_price', 0):.2f}
  Current SL: ${trade.get('sl', 0):.2f}
  TPs Hit: {trade.get('tp_hit', 0)}/{trade.get('total_tps', 5)}

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
        symbol = trade.get("symbol", "XAUUSD")
        msg = f"""
\U0001f7e1 <b>EARLY WARNING — M15 Structure Shift</b>
<b>Symbol:</b> {symbol}

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
        symbol = trade.get("symbol", "XAUUSD")
        total_tps = trade.get("total_tps", 5)
        hit = min(tp_num, total_tps)
        remaining = total_tps - hit
        progress = "\U0001f7e9" * hit + "\u2b1c" * remaining

        msg = f"""
\U0001f7e2 <b>TP{tp_num} REACHED!</b>

<b>{symbol} {trade.get('direction', '')}</b>
  Entry: ${trade.get('entry_price', 0):.2f}
  TP{tp_num}: ${action.get('tp_price', 0):.2f}

<b>Action Taken:</b>
  Closed: {action.get('closed_lot', 0)} lot
  Remaining: {action.get('remaining_lot', 0)} lot
  Profit: +${action.get('pnl_usd', 0):.2f} (+{action.get('pnl_pips', 0)} pips)

<b>Stop Loss Update:</b>
  {'Moved to BREAKEVEN + 2 pips' if tp_num == 1 else f"Trailed to ${trade.get('sl', 0):.2f}"}

\U0001f4b0 Progress: {tp_num}/{total_tps} TPs hit
{progress}

<b>Alpha FX Hub</b> | Partial Close Strategy
"""
        return self.broadcast(msg.strip())

    # ── BLUE: FVG ENTRY OPPORTUNITY ─────────────────────────
    def send_fvg_entry(self, opportunity: dict) -> bool:
        """Send FVG second-wave entry alert."""
        symbol = opportunity.get("symbol", "XAUUSD")
        msg = f"""
\U0001f535 <b>FVG ENTRY OPPORTUNITY</b>

<b>{opportunity.get('direction', '')} {symbol}</b>
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
        symbol = trade.get("symbol", "XAUUSD")
        pnl = trade.get("pnl_usd", 0)
        emoji = "\U0001f4b0" if pnl > 0 else "\U0001f534"

        msg = f"""
{emoji} <b>TRADE CLOSED</b>

<b>{symbol} {trade.get('direction', '')}</b>
  Entry: ${trade.get('entry_price', 0):.2f}
  Exit Reason: {trade.get('close_reason', 'Unknown')}
  TPs Hit: {trade.get('tp_hit', 0)}/{trade.get('total_tps', 5)}

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

<b>Alpha FX Hub</b> V6 Callisto | Daily Report
"""
        return self.broadcast(msg.strip())

    # ── GROK-ONLY ALERT (standalone Grok insight) ──────────
    def send_grok_alert(self, symbol: str, grok_result: dict) -> bool:
        """Send a standalone Grok AI market analysis alert."""
        bias = grok_result.get("bias", "NO_TRADE")
        conf = grok_result.get("confidence", 0)
        grade = grok_result.get("grade", "N/A")
        reasoning = grok_result.get("reasoning", "")

        bias_emoji = "\U0001f7e2" if bias == "BUY" else "\U0001f534" if bias == "SELL" else "\u26aa"

        entry_info = ""
        entry = grok_result.get("entry", {})
        if entry and entry.get("price"):
            entry_info = f"""
<b>Grok's Entry Plan:</b>
  Entry: ${entry.get('price', 0):.5f}
  SL: ${entry.get('sl', 0):.5f}
  TP1: ${entry.get('tp1', 0):.5f}
  TP2: ${entry.get('tp2', 0):.5f}
  TP3: ${entry.get('tp3', 0):.5f}
  Reason: {entry.get('reason', '')}"""

        msg = f"""
\U0001f9e0 <b>GROK AI MARKET INSIGHT</b>

{bias_emoji} <b>{bias} {symbol}</b>
Confidence: <b>{conf}%</b> | Grade: <b>{grade}</b>

<b>Analysis:</b>
<i>{reasoning}</i>
{entry_info}

<i>This is an AI-generated insight, not a guaranteed signal.</i>

<b>Alpha FX Hub</b> | Grok xAI
"""
        return self.broadcast(msg.strip())
