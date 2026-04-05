"""
Alpha FX Hub — Trade Manager
10-TP level system with selectable strategies:
  Strategy A: Equal 10% per TP level
  Strategy B: 15/10 split + progressive trailing SL

Handles: partial closes, SL trailing, TP tracking, trade lifecycle.
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("alpha_fx_hub.trade_manager")

PIP = 0.1


# ── TP Strategies ───────────────────────────────────────────
STRATEGIES = {
    "equal_10": {
        "name": "Equal 10%",
        "description": "Close 10% at every TP. Simple and balanced.",
        "lot_pct": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10],
        "trailing_rules": {
            1: "breakeven",  # TP1 → breakeven
        },
    },
    "split_15_10": {
        "name": "15/10 Split + Trailing",
        "description": "15% at TP1, 10% at TP2-9, 5% runner at TP10. Progressive trailing SL.",
        "lot_pct": [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05],
        "trailing_rules": {
            1: "breakeven",  # TP1 → breakeven + buffer
            4: 2,            # TP4 → trail to TP2
            7: 5,            # TP7 → trail to TP5
        },
    },
}


@dataclass
class Trade:
    """Represents an active or closed trade."""
    id: str = ""
    signal_id: str = ""
    symbol: str = "XAUUSD"
    direction: str = ""        # "BUY" or "SELL"
    entry_price: float = 0.0
    initial_lot: float = 0.0
    remaining_lot: float = 0.0
    sl: float = 0.0
    original_sl: float = 0.0
    tp_levels: List[float] = field(default_factory=list)
    tp_hit: int = 0            # How many TPs hit so far
    strategy: str = "split_15_10"
    status: str = "pending"    # pending, active, closed
    opened_at: str = ""
    closed_at: str = ""
    close_reason: str = ""
    pnl_usd: float = 0.0
    pnl_pips: float = 0.0
    actions: List[dict] = field(default_factory=list)
    grade: str = ""
    score: int = 0
    confidence: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class TradeManager:
    """
    Manages trade lifecycle with 10-TP partial close system.
    Supports selectable TP/SL strategies.
    """

    def __init__(self, strategy: str = "split_15_10", data_dir: str = None, cloud_sync=None):
        self.strategy_key = strategy
        self.strategy = STRATEGIES.get(strategy, STRATEGIES["split_15_10"])
        self.active_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.cloud_sync = cloud_sync  # Optional CloudTradeSync instance
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self._load_trades()

    def set_strategy(self, strategy_key: str):
        """Switch TP/SL strategy."""
        if strategy_key in STRATEGIES:
            self.strategy_key = strategy_key
            self.strategy = STRATEGIES[strategy_key]
            logger.info(f"Strategy changed to: {self.strategy['name']}")

    def open_trade(self, signal: dict) -> Trade:
        """Open a new trade from a signal."""
        trade_id = f"T{int(time.time())}"
        trade = Trade(
            id=trade_id,
            signal_id=signal.get("timestamp", ""),
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            initial_lot=signal.get("lot_moderate", 0.1),
            remaining_lot=signal.get("lot_moderate", 0.1),
            sl=signal["sl"],
            original_sl=signal["sl"],
            tp_levels=signal.get("tp_levels", []),
            strategy=self.strategy_key,
            status="active",
            opened_at=datetime.now(timezone.utc).isoformat(),
            grade=signal.get("grade", ""),
            score=signal.get("score", 0),
            confidence=signal.get("confidence", ""),
            notes=signal.get("notes", ""),
        )
        trade.actions.append({
            "time": trade.opened_at,
            "action": "OPEN",
            "detail": f"{trade.direction} {trade.initial_lot} lot @ ${trade.entry_price:.2f}",
        })
        self.active_trades[trade_id] = trade
        self._save_trades()
        logger.info(f"Trade opened: {trade_id} {trade.direction} @ {trade.entry_price}")
        return trade

    def check_tp_hits(self, trade_id: str, current_price: float) -> List[dict]:
        """
        Check if any TP levels have been hit.
        Returns list of actions taken (partial closes, SL moves).
        """
        trade = self.active_trades.get(trade_id)
        if not trade or trade.status != "active":
            return []

        actions = []
        lot_pcts = self.strategy["lot_pct"]
        trailing = self.strategy["trailing_rules"]

        while trade.tp_hit < len(trade.tp_levels):
            next_tp = trade.tp_levels[trade.tp_hit]
            tp_reached = (
                (trade.direction == "BUY" and current_price >= next_tp) or
                (trade.direction == "SELL" and current_price <= next_tp)
            )

            if not tp_reached:
                break

            tp_num = trade.tp_hit + 1
            close_pct = lot_pcts[trade.tp_hit] if trade.tp_hit < len(lot_pcts) else 0.10
            close_lot = round(trade.initial_lot * close_pct, 2)
            close_lot = min(close_lot, trade.remaining_lot)

            # Record partial close
            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
            trade.tp_hit = tp_num

            pnl_pips = abs(next_tp - trade.entry_price) / PIP
            pnl_usd = close_lot * pnl_pips * 10.0  # pip value per lot

            action = {
                "time": datetime.now(timezone.utc).isoformat(),
                "action": f"TP{tp_num}_HIT",
                "tp_price": next_tp,
                "closed_lot": close_lot,
                "remaining_lot": trade.remaining_lot,
                "pnl_pips": round(pnl_pips, 1),
                "pnl_usd": round(pnl_usd, 2),
            }
            trade.actions.append(action)
            actions.append(action)

            # Check trailing SL rules
            if tp_num in trailing:
                rule = trailing[tp_num]
                if rule == "breakeven":
                    buffer = 2 * PIP
                    if trade.direction == "BUY":
                        new_sl = trade.entry_price + buffer
                    else:
                        new_sl = trade.entry_price - buffer
                else:
                    # Trail to a specific TP level
                    tp_index = rule - 1
                    if tp_index < len(trade.tp_levels):
                        new_sl = trade.tp_levels[tp_index]
                    else:
                        new_sl = trade.sl

                old_sl = trade.sl
                trade.sl = round(new_sl, 2)
                sl_action = {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "action": "SL_MOVED",
                    "old_sl": old_sl,
                    "new_sl": trade.sl,
                    "reason": f"TP{tp_num} trailing rule" if rule != "breakeven" else "Breakeven",
                }
                trade.actions.append(sl_action)
                actions.append(sl_action)

            logger.info(f"TP{tp_num} hit for {trade_id}: closed {close_lot} lot, {trade.remaining_lot} remaining")

        # Check if trade fully closed
        if trade.remaining_lot <= 0.005:
            self._close_trade(trade_id, current_price, "All TPs hit")

        self._save_trades()
        return actions

    def check_sl_hit(self, trade_id: str, current_price: float) -> Optional[dict]:
        """Check if SL has been hit."""
        trade = self.active_trades.get(trade_id)
        if not trade or trade.status != "active":
            return None

        sl_hit = (
            (trade.direction == "BUY" and current_price <= trade.sl) or
            (trade.direction == "SELL" and current_price >= trade.sl)
        )

        if sl_hit:
            return self._close_trade(trade_id, current_price, "Stop Loss hit")
        return None

    def _close_trade(self, trade_id: str, close_price: float, reason: str) -> dict:
        """Close a trade completely."""
        trade = self.active_trades.get(trade_id)
        if not trade:
            return {}

        trade.status = "closed"
        trade.closed_at = datetime.now(timezone.utc).isoformat()
        trade.close_reason = reason

        # Calculate total PnL
        if trade.direction == "BUY":
            total_pips = (close_price - trade.entry_price) / PIP
        else:
            total_pips = (trade.entry_price - close_price) / PIP

        trade.pnl_pips = round(total_pips, 1)
        trade.pnl_usd = round(trade.remaining_lot * total_pips * 10.0, 2)

        # Add to partial close PnL
        for action in trade.actions:
            if "pnl_usd" in action and action["action"].startswith("TP"):
                trade.pnl_usd += action["pnl_usd"]

        action = {
            "time": trade.closed_at,
            "action": "CLOSE",
            "price": close_price,
            "reason": reason,
            "total_pnl_pips": trade.pnl_pips,
            "total_pnl_usd": trade.pnl_usd,
        }
        trade.actions.append(action)

        self.closed_trades.append(trade)
        del self.active_trades[trade_id]
        self._save_trades()

        # Auto-sync to cloud if available
        if self.cloud_sync:
            try:
                self.cloud_sync.upload_trade(trade.to_dict())
            except Exception as e:
                logger.warning(f"Cloud sync failed for {trade_id}: {e}")

        logger.info(f"Trade closed: {trade_id}, PnL: ${trade.pnl_usd:.2f} ({trade.pnl_pips} pips)")
        return action

    def get_performance_stats(self) -> dict:
        """Calculate performance statistics from closed trades."""
        if not self.closed_trades:
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0, "total_pnl": 0, "avg_pnl": 0,
                "best_trade": 0, "worst_trade": 0, "avg_rr": 0,
                "max_drawdown": 0, "profit_factor": 0,
            }

        pnls = [t.pnl_usd for t in self.closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        # Max drawdown
        cumulative = []
        running = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            running += pnl
            cumulative.append(running)
            peak = max(peak, running)
            dd = peak - running
            max_dd = max(max_dd, dd)

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1

        return {
            "total_trades": len(self.closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / max(len(pnls), 1) * 100, 1),
            "total_pnl": round(sum(pnls), 2),
            "avg_pnl": round(sum(pnls) / max(len(pnls), 1), 2),
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
            "avg_rr": round(
                (sum(wins) / max(len(wins), 1)) / max(abs(sum(losses) / max(len(losses), 1)), 1), 2
            ) if wins and losses else 0,
            "max_drawdown": round(max_dd, 2),
            "profit_factor": round(gross_profit / max(gross_loss, 1), 2),
            "cumulative_pnl": cumulative,
        }

    def _save_trades(self):
        """Persist trades to JSON."""
        try:
            data = {
                "active": {tid: t.to_dict() for tid, t in self.active_trades.items()},
                "closed": [t.to_dict() for t in self.closed_trades[-100:]],
            }
            with open(self.data_dir / "trades.json", "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save trades: {e}")

    def _load_trades(self):
        """Load trades from JSON."""
        path = self.data_dir / "trades.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for tid, td in data.get("active", {}).items():
                self.active_trades[tid] = Trade(**{
                    k: v for k, v in td.items() if k in Trade.__dataclass_fields__
                })
            for td in data.get("closed", []):
                self.closed_trades.append(Trade(**{
                    k: v for k, v in td.items() if k in Trade.__dataclass_fields__
                }))
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
