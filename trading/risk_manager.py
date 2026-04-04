"""
Alpha FX Hub — Risk Manager
Account-level risk controls and position sizing.
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger("alpha_fx_hub.risk_manager")

PIP = 0.1
PIP_VALUE = 10.0  # USD per pip per standard lot


class RiskManager:
    """
    Manages account-level risk.
    Enforces: max concurrent trades, daily loss limit, max drawdown.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        max_concurrent: int = 3,
        max_daily_loss_pct: float = 6.0,
        max_drawdown_pct: float = 20.0,
    ):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.peak_balance = initial_balance
        self.max_concurrent = max_concurrent
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct

        self.daily_pnl = 0.0
        self.daily_reset_date = datetime.now(timezone.utc).date()
        self.active_positions = 0
        self.total_exposure_lots = 0.0

    def can_trade(self) -> Dict[str, any]:
        """Check if a new trade is allowed based on risk rules."""
        self._check_daily_reset()

        reasons = []
        allowed = True

        # Max concurrent trades
        if self.active_positions >= self.max_concurrent:
            allowed = False
            reasons.append(f"Max concurrent trades reached ({self.max_concurrent})")

        # Daily loss limit
        daily_loss_limit = self.current_balance * (self.max_daily_loss_pct / 100)
        if self.daily_pnl <= -daily_loss_limit:
            allowed = False
            reasons.append(f"Daily loss limit hit (${daily_loss_limit:.2f})")

        # Max drawdown
        drawdown_pct = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        if drawdown_pct >= self.max_drawdown_pct:
            allowed = False
            reasons.append(f"Max drawdown reached ({drawdown_pct:.1f}%)")

        return {
            "allowed": allowed,
            "reasons": reasons,
            "active_positions": self.active_positions,
            "daily_pnl": round(self.daily_pnl, 2),
            "drawdown_pct": round(drawdown_pct, 2),
            "balance": round(self.current_balance, 2),
        }

    def calculate_lot(self, risk_pct: float, sl_pips: float) -> float:
        """Calculate position size based on risk %."""
        if sl_pips <= 0:
            return 0.01
        risk_amount = self.current_balance * (risk_pct / 100)
        lot = risk_amount / (sl_pips * PIP_VALUE)
        return max(0.01, min(5.0, round(lot, 2)))

    def calculate_all_tiers(self, sl_pips: float) -> dict:
        """Calculate lot sizes for all risk tiers."""
        return {
            "conservative": {"risk_pct": 2.0, "lot": self.calculate_lot(2.0, sl_pips),
                           "risk_usd": round(self.current_balance * 0.02, 2)},
            "moderate":     {"risk_pct": 3.0, "lot": self.calculate_lot(3.0, sl_pips),
                           "risk_usd": round(self.current_balance * 0.03, 2)},
            "aggressive":   {"risk_pct": 5.0, "lot": self.calculate_lot(5.0, sl_pips),
                           "risk_usd": round(self.current_balance * 0.05, 2)},
        }

    def record_trade_open(self, lot: float):
        """Record a new trade opening."""
        self.active_positions += 1
        self.total_exposure_lots += lot

    def record_trade_close(self, lot: float, pnl: float):
        """Record a trade closing."""
        self.active_positions = max(0, self.active_positions - 1)
        self.total_exposure_lots = max(0, self.total_exposure_lots - lot)
        self.daily_pnl += pnl
        self.current_balance += pnl
        self.peak_balance = max(self.peak_balance, self.current_balance)

    def get_status(self) -> dict:
        """Get current risk status."""
        self._check_daily_reset()
        drawdown = ((self.peak_balance - self.current_balance) / max(self.peak_balance, 1)) * 100
        daily_limit = self.current_balance * (self.max_daily_loss_pct / 100)

        return {
            "balance": round(self.current_balance, 2),
            "peak_balance": round(self.peak_balance, 2),
            "drawdown_pct": round(drawdown, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_limit": round(daily_limit, 2),
            "daily_limit_remaining": round(daily_limit + self.daily_pnl, 2),
            "active_positions": self.active_positions,
            "total_exposure": round(self.total_exposure_lots, 2),
            "can_trade": self.can_trade()["allowed"],
        }

    def _check_daily_reset(self):
        """Reset daily PnL at midnight UTC."""
        today = datetime.now(timezone.utc).date()
        if today > self.daily_reset_date:
            self.daily_pnl = 0.0
            self.daily_reset_date = today
