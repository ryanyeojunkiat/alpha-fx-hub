"""
Alpha FX Hub — Cloud Trade Sync
Auto-syncs trade history to Supabase for persistence across sessions/devices.
Also provides the data foundation for the adaptive learning engine.

Uses Supabase REST API (no SDK dependency).
"""
import requests
import logging
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("alpha_fx_hub.cloud_sync")


class CloudTradeSync:
    """Syncs trade history to/from Supabase."""

    TABLE = "trade_history"

    def __init__(self, supabase_url: str, supabase_key: str, user_id: str = ""):
        self.url = supabase_url.rstrip("/")
        self.key = supabase_key
        self.user_id = user_id
        self.headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def set_user(self, user_id: str, access_token: str = ""):
        """Set current user for RLS-filtered queries."""
        self.user_id = user_id
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    # ── Table Creation (run once) ──────────────────────────────
    def ensure_table_sql(self) -> str:
        """Returns SQL to create the trade_history table.
        Run this in Supabase SQL Editor once."""
        return """
-- Trade History Table
CREATE TABLE IF NOT EXISTS trade_history (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    signal_id TEXT,
    symbol TEXT DEFAULT 'XAUUSD',
    direction TEXT NOT NULL,
    entry_price NUMERIC NOT NULL,
    initial_lot NUMERIC,
    remaining_lot NUMERIC DEFAULT 0,
    sl NUMERIC,
    original_sl NUMERIC,
    tp_levels JSONB DEFAULT '[]',
    tp_hit INTEGER DEFAULT 0,
    strategy TEXT DEFAULT 'split_15_10',
    status TEXT DEFAULT 'closed',
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    close_reason TEXT,
    pnl_usd NUMERIC DEFAULT 0,
    pnl_pips NUMERIC DEFAULT 0,
    grade TEXT,
    score INTEGER DEFAULT 0,
    confidence TEXT,
    notes TEXT,
    actions JSONB DEFAULT '[]',
    -- Learning metadata
    session_name TEXT,          -- Asian/London/NY/Late NY
    day_of_week INTEGER,       -- 0=Mon, 6=Sun
    hour_utc INTEGER,          -- 0-23
    atr_at_entry NUMERIC,
    adx_at_entry NUMERIC,
    rsi_at_entry NUMERIC,
    trend_at_entry TEXT,        -- bullish/bearish/ranging
    volatility_regime TEXT,     -- low/normal/high/extreme
    news_impact TEXT,           -- none/low/medium/high
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_trade_history_user ON trade_history(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status);
CREATE INDEX IF NOT EXISTS idx_trade_history_opened ON trade_history(opened_at);

-- Row Level Security
ALTER TABLE trade_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own trades" ON trade_history
    FOR ALL USING (auth.uid() = user_id);

-- Performance stats view
CREATE OR REPLACE VIEW trade_stats AS
SELECT
    user_id,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE pnl_usd > 0) as wins,
    COUNT(*) FILTER (WHERE pnl_usd <= 0) as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE pnl_usd > 0) / NULLIF(COUNT(*), 0), 1) as win_rate,
    ROUND(SUM(pnl_usd)::numeric, 2) as total_pnl,
    ROUND(AVG(pnl_usd)::numeric, 2) as avg_pnl,
    ROUND(AVG(pnl_usd) FILTER (WHERE pnl_usd > 0)::numeric, 2) as avg_win,
    ROUND(AVG(pnl_usd) FILTER (WHERE pnl_usd <= 0)::numeric, 2) as avg_loss,
    ROUND(AVG(pnl_pips)::numeric, 1) as avg_pips,
    MAX(pnl_usd) as best_trade,
    MIN(pnl_usd) as worst_trade
FROM trade_history
WHERE status = 'closed'
GROUP BY user_id;
"""

    # ── Upload Trades ──────────────────────────────────────────
    def upload_trade(self, trade_dict: dict) -> bool:
        """Upload a single trade to Supabase."""
        try:
            row = self._trade_to_row(trade_dict)
            resp = requests.post(
                f"{self.url}/rest/v1/{self.TABLE}",
                json=row,
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logger.info(f"Trade {trade_dict.get('id', '?')} synced to cloud")
                return True
            else:
                logger.warning(f"Cloud sync failed ({resp.status_code}): {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Cloud sync error: {e}")
            return False

    def upload_trades_batch(self, trades: List[dict]) -> int:
        """Upload multiple trades. Returns count of successful uploads."""
        if not trades:
            return 0
        rows = [self._trade_to_row(t) for t in trades]
        try:
            resp = requests.post(
                f"{self.url}/rest/v1/{self.TABLE}",
                json=rows,
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"},
                timeout=30,
            )
            if resp.status_code in (200, 201):
                logger.info(f"Batch synced {len(rows)} trades to cloud")
                return len(rows)
            else:
                logger.warning(f"Batch sync failed ({resp.status_code}): {resp.text[:200]}")
                return 0
        except Exception as e:
            logger.error(f"Batch sync error: {e}")
            return 0

    # ── Fetch Trades ───────────────────────────────────────────
    def fetch_trades(self, limit: int = 200, status: str = "closed") -> List[dict]:
        """Fetch user's trade history from cloud."""
        try:
            params = {
                "select": "*",
                "order": "opened_at.desc",
                "limit": str(limit),
            }
            if status:
                params["status"] = f"eq.{status}"
            if self.user_id:
                params["user_id"] = f"eq.{self.user_id}"

            resp = requests.get(
                f"{self.url}/rest/v1/{self.TABLE}",
                params=params,
                headers=self.headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"Fetch trades failed ({resp.status_code}): {resp.text[:200]}")
                return []
        except Exception as e:
            logger.error(f"Fetch trades error: {e}")
            return []

    def fetch_stats(self) -> Optional[dict]:
        """Fetch aggregated performance stats."""
        try:
            params = {"select": "*"}
            if self.user_id:
                params["user_id"] = f"eq.{self.user_id}"

            resp = requests.get(
                f"{self.url}/rest/v1/trade_stats",
                params=params,
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data[0] if data else None
            return None
        except Exception:
            return None

    # ── Learning Queries ───────────────────────────────────────
    def fetch_trades_for_learning(self, limit: int = 500) -> List[dict]:
        """Fetch trades with learning metadata for the adaptive engine."""
        try:
            resp = requests.get(
                f"{self.url}/rest/v1/{self.TABLE}",
                params={
                    "select": "direction,entry_price,pnl_usd,pnl_pips,grade,score,"
                              "session_name,day_of_week,hour_utc,atr_at_entry,"
                              "adx_at_entry,rsi_at_entry,trend_at_entry,"
                              "volatility_regime,news_impact,strategy,tp_hit,close_reason",
                    "status": "eq.closed",
                    "order": "opened_at.desc",
                    "limit": str(limit),
                },
                headers=self.headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    # ── Helpers ─────────────────────────────────────────────────
    def _trade_to_row(self, trade: dict) -> dict:
        """Convert Trade dict to Supabase row format."""
        row = {
            "id": trade.get("id", ""),
            "user_id": self.user_id or None,
            "signal_id": trade.get("signal_id", ""),
            "symbol": trade.get("symbol", "XAUUSD"),
            "direction": trade.get("direction", ""),
            "entry_price": trade.get("entry_price", 0),
            "initial_lot": trade.get("initial_lot", 0),
            "remaining_lot": trade.get("remaining_lot", 0),
            "sl": trade.get("sl", 0),
            "original_sl": trade.get("original_sl", 0),
            "tp_levels": json.dumps(trade.get("tp_levels", [])),
            "tp_hit": trade.get("tp_hit", 0),
            "strategy": trade.get("strategy", "split_15_10"),
            "status": trade.get("status", "closed"),
            "opened_at": trade.get("opened_at", None),
            "closed_at": trade.get("closed_at", None),
            "close_reason": trade.get("close_reason", ""),
            "pnl_usd": trade.get("pnl_usd", 0),
            "pnl_pips": trade.get("pnl_pips", 0),
            "grade": trade.get("grade", ""),
            "score": trade.get("score", 0),
            "confidence": trade.get("confidence", ""),
            "notes": trade.get("notes", ""),
            "actions": json.dumps(trade.get("actions", [])),
            # Learning metadata (may not always be present)
            "session_name": trade.get("session_name", None),
            "day_of_week": trade.get("day_of_week", None),
            "hour_utc": trade.get("hour_utc", None),
            "atr_at_entry": trade.get("atr_at_entry", None),
            "adx_at_entry": trade.get("adx_at_entry", None),
            "rsi_at_entry": trade.get("rsi_at_entry", None),
            "trend_at_entry": trade.get("trend_at_entry", None),
            "volatility_regime": trade.get("volatility_regime", None),
            "news_impact": trade.get("news_impact", None),
        }
        # Remove None values to let Supabase use defaults
        return {k: v for k, v in row.items() if v is not None}
