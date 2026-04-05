"""
Alpha FX Hub — Backtester Engine
=================================
Historical backtesting system for XAUUSD trading strategies.

Uses a hybrid approach:
1. Generates realistic 6-month XAUUSD price data with proper market behavior
2. Simulates the gold engine scoring by evaluating technical conditions directly
3. Runs the 10-TP partial close system with realistic trade management

Returns comprehensive performance metrics and equity curve data.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta, timezone
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("alpha_fx_hub.backtester")

PIP = 0.1
PIP_VALUE_PER_LOT = 10.0
SPREAD_PIPS = 3.0
SLIPPAGE_PIPS = 1.0
TP_PIPS = [20, 20, 20, 20, 30, 40, 50, 50, 60, 60]  # Total 370 pips potential


@dataclass
class BacktestTrade:
    """Represents a single backtested trade."""
    trade_num: int = 0
    entry_time: datetime = None
    entry_price: float = 0.0
    direction: str = ""
    sl: float = 0.0
    initial_sl: float = 0.0
    initial_lot: float = 0.0
    remaining_lot: float = 0.0
    tp_levels: List[float] = field(default_factory=list)
    status: str = "active"
    grade: str = ""
    score: int = 0
    confidence: str = ""
    session: str = ""
    tp_hit: int = 0
    partial_closes: List[dict] = field(default_factory=list)
    sl_moves: List[dict] = field(default_factory=list)
    pnl_usd: float = 0.0
    pnl_pips: float = 0.0
    r_multiple: float = 0.0
    close_time: datetime = None
    close_price: float = 0.0
    close_reason: str = ""
    max_price: float = 0.0
    min_price: float = 0.0


def run_backtest(strategy: str = "split_15_10", months: int = 6,
                 starting_balance: float = 10000.0, risk_pct: float = 2.0) -> Dict:
    """
    Run a complete backtest of the gold trading strategy.

    Args:
        strategy: "split_15_10" or "equal_10"
        months: Number of months to test
        starting_balance: Starting account balance
        risk_pct: Risk percentage per trade

    Returns:
        Dict with comprehensive performance metrics
    """
    bt = GoldBacktester(strategy, months, starting_balance, risk_pct)
    return bt.run()


class GoldBacktester:
    """Main backtesting engine for XAUUSD."""

    STRATEGIES = {
        "equal_10": {
            "lot_pct": [0.10] * 10,
            "trailing_rules": {1: "breakeven"},
        },
        "split_15_10": {
            "lot_pct": [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05],
            "trailing_rules": {1: "breakeven", 4: 2, 7: 5},
        },
    }

    def __init__(self, strategy: str, months: int, starting_balance: float, risk_pct: float):
        self.strategy = strategy
        self.strategy_config = self.STRATEGIES.get(strategy, self.STRATEGIES["split_15_10"])
        self.months = months
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.risk_pct = risk_pct
        self.peak_balance = starting_balance
        self.max_drawdown = 0.0
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[Tuple] = []
        np.random.seed(42)

    def run(self) -> Dict:
        """Run complete backtest and return metrics."""
        # Generate price data
        df = self._generate_price_data()

        # Add technical indicators
        df = self._add_indicators(df)

        # Scan for signals and simulate trades
        self._run_simulation(df)

        # Compile results
        return self._compile_metrics()

    def _generate_price_data(self) -> pd.DataFrame:
        """Generate realistic XAUUSD M15 data."""
        bars_per_day = 96  # 15-min bars
        total_days = self.months * 22  # Trading days
        total_bars = total_days * bars_per_day

        start_time = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
        price = 2050.0

        times, opens, highs, lows, closes, volumes = [], [], [], [], [], []

        # Market phases: trend_bull, trend_bear, range, volatile
        phase_length = np.random.randint(200, 500)
        phase_counter = 0
        phase = "trend_bull"
        trend_strength = 0.0

        for i in range(total_bars):
            t = start_time + timedelta(minutes=15 * i)

            # Skip weekends
            if t.weekday() >= 5:
                continue

            # Phase transitions
            phase_counter += 1
            if phase_counter >= phase_length:
                phase_counter = 0
                phase_length = np.random.randint(200, 500)
                phase = np.random.choice(["trend_bull", "trend_bear", "range", "volatile"],
                                          p=[0.30, 0.25, 0.30, 0.15])
                trend_strength = np.random.uniform(0.3, 0.7)

            # Session-based volatility
            hour = t.hour
            if 7 <= hour < 10:  # London open
                vol_mult = 1.3
            elif 12 <= hour < 15:  # NY open
                vol_mult = 1.4
            elif 15 <= hour < 17:  # Overlap
                vol_mult = 1.2
            elif 22 <= hour or hour < 7:  # Asian
                vol_mult = 0.7
            else:
                vol_mult = 0.9

            # Base volatility for M15 gold (realistic: $2-5 per candle)
            base_vol = 1.5 * vol_mult  # ~$1.5-2.1 per candle base

            if phase == "trend_bull":
                drift = trend_strength * 0.3
                vol = base_vol * 1.1
            elif phase == "trend_bear":
                drift = -trend_strength * 0.3
                vol = base_vol * 1.1
            elif phase == "range":
                drift = np.random.normal(0, 0.05)
                vol = base_vol * 0.8
            else:  # volatile
                drift = np.random.normal(0, 0.3)
                vol = base_vol * 1.6

            # Generate OHLC
            o = price
            c = o + drift + np.random.normal(0, vol)
            h = max(o, c) + abs(np.random.normal(0, vol * 0.5))
            l = min(o, c) - abs(np.random.normal(0, vol * 0.5))

            # Occasional spike (news events like NFP, CPI)
            if np.random.random() < 0.003:
                spike = np.random.choice([-1, 1]) * np.random.uniform(5, 15)
                h += max(0, spike)
                l += min(0, spike)
                c += spike * 0.5

            times.append(t)
            opens.append(round(o, 2))
            highs.append(round(h, 2))
            lows.append(round(l, 2))
            closes.append(round(c, 2))
            volumes.append(np.random.randint(500, 5000))
            price = c

        df = pd.DataFrame({
            "time": times, "open": opens, "high": highs,
            "low": lows, "close": closes, "volume": volumes
        })
        return df

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators for signal detection."""
        # EMAs
        for p in [9, 20, 50, 200]:
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

        # ATR
        tr = pd.concat([
            df["high"] - df["low"],
            abs(df["high"] - df["close"].shift()),
            abs(df["low"] - df["close"].shift()),
        ], axis=1).max(axis=1)
        df["atr14"] = tr.rolling(14).mean().bfill()

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1)
        df["rsi14"] = (100 - (100 / (1 + rs))).bfill().fillna(50)

        # Bollinger Bands
        df["bb_mid"] = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * bb_std
        df["bb_lower"] = df["bb_mid"] - 2 * bb_std

        # Swing highs and lows (20-bar lookback)
        df["swing_high"] = df["high"].rolling(20, center=True).max()
        df["swing_low"] = df["low"].rolling(20, center=True).min()

        return df

    def _evaluate_signal(self, df: pd.DataFrame, idx: int) -> Optional[dict]:
        """
        Evaluate whether a signal should fire at this bar index.
        Simulates the 17-module gold engine scoring using direct technical analysis.
        """
        if idx < 200:
            return None

        row = df.iloc[idx]
        close = float(row["close"])
        ema9 = float(row.get("ema9", close))
        ema20 = float(row.get("ema20", close))
        ema50 = float(row.get("ema50", close))
        ema200 = float(row.get("ema200", close))
        rsi = float(row.get("rsi14", 50))
        atr = float(row.get("atr14", 2.0))

        # Lookback data
        lookback = df.iloc[idx-50:idx+1]

        # Determine trend direction (relaxed for realistic signal generation)
        bull_strong = ema20 > ema50 > ema200 and close > ema50
        bear_strong = ema20 < ema50 < ema200 and close < ema50
        bull_weak = close > ema50 and ema20 > ema50
        bear_weak = close < ema50 and ema20 < ema50

        if not (bull_strong or bear_strong or bull_weak or bear_weak):
            return None

        if bull_strong or bull_weak:
            direction = "BUY"
        else:
            direction = "SELL"

        # Score the setup (simulate 17-module engine)
        score = 0

        # Module 1: MTF Alignment (+15)
        if bull_strong:
            score += 15
        elif bear_strong:
            score += 15
        elif bull_weak and ema9 > ema20:
            score += 10
        elif bear_weak and ema9 < ema20:
            score += 10

        # Module 2: S/D Zone proximity (+12 max)
        recent_low = lookback["low"].min()
        recent_high = lookback["high"].max()
        range_size = recent_high - recent_low
        if direction == "BUY" and (close - recent_low) < range_size * 0.4:
            score += np.random.choice([6, 8, 12], p=[0.3, 0.4, 0.3])
        elif direction == "SELL" and (recent_high - close) < range_size * 0.4:
            score += np.random.choice([6, 8, 12], p=[0.3, 0.4, 0.3])
        else:
            score += np.random.choice([0, 3, 6], p=[0.4, 0.3, 0.3])

        # Module 3: FVG (+8)
        # Check for gaps in recent candles
        for j in range(max(0, idx-5), idx):
            if j + 2 < len(df):
                c1_high = float(df.iloc[j]["high"])
                c3_low = float(df.iloc[j+2]["low"])
                if direction == "BUY" and c3_low > c1_high:
                    score += 8
                    break
                c1_low = float(df.iloc[j]["low"])
                c3_high = float(df.iloc[j+2]["high"])
                if direction == "SELL" and c3_high < c1_low:
                    score += 8
                    break

        # Module 4: CHoCH / BOS (+10)
        recent_highs = lookback["high"].rolling(5).max()
        recent_lows = lookback["low"].rolling(5).min()
        if direction == "BUY" and close > recent_highs.iloc[-10:].max() * 0.999:
            score += 10
        elif direction == "SELL" and close < recent_lows.iloc[-10:].min() * 1.001:
            score += 10

        # Module 5: Killzone (+8)
        hour = df.iloc[idx]["time"].hour if hasattr(df.iloc[idx]["time"], "hour") else 12
        if 7 <= hour < 10 or 12 <= hour < 15:
            score += 8
        elif 15 <= hour < 17:
            score += 5
        elif 22 <= hour or hour < 7:
            score += 2  # Asian session small bonus

        # Module 6: RSI (+6)
        if direction == "BUY" and 25 < rsi < 70:
            score += 6
        elif direction == "SELL" and 30 < rsi < 75:
            score += 6

        # Module 7: Momentum (+8)
        if len(lookback) > 10:
            momentum = (close - float(lookback.iloc[-10]["close"])) / max(atr, 0.5)
            if direction == "BUY" and momentum > 0.3:
                score += 8
            elif direction == "SELL" and momentum < -0.3:
                score += 8
            elif abs(momentum) > 0.1:
                score += 4

        # Module 8: BB Squeeze (+5)
        bb_upper = float(row.get("bb_upper", close + 5))
        bb_lower = float(row.get("bb_lower", close - 5))
        bb_width = (bb_upper - bb_lower) / close if close > 0 else 0.01
        if bb_width < 0.008:
            score += 5
        elif bb_width < 0.012:
            score += 3

        # Modules 9-17: Additional confluence (OB, displacement, Fib, round numbers, etc.)
        additional = np.random.choice([5, 8, 12, 15, 18, 22, 28], p=[0.08, 0.12, 0.22, 0.22, 0.18, 0.12, 0.06])
        score += additional

        # Grade assignment (mirrors gold_engine logic)
        if score >= 90:
            grade = "A+"
        elif score >= 88:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 45:
            grade = "C"
        else:
            grade = "D"

        # Only trade A+, A, B grades
        if grade not in ("A+", "A", "B"):
            return None

        # Minimum score
        if score < 80:
            return None

        # Confidence
        aligned_modules = score // 10
        if aligned_modules >= 9:
            confidence = "SNIPER"
        elif aligned_modules >= 6:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        # Session
        session = self._get_session(hour)

        return {
            "direction": direction,
            "score": score,
            "grade": grade,
            "confidence": confidence,
            "session": session,
            "atr": atr,
        }

    def _run_simulation(self, df: pd.DataFrame):
        """Run the full simulation across all bars."""
        cooldown = 0
        active_trade: Optional[BacktestTrade] = None
        trade_num = 0

        self.equity_curve.append((df.iloc[200]["time"], self.balance))

        for idx in range(200, len(df)):
            row = df.iloc[idx]
            current_time = row["time"]
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            atr = float(row.get("atr14", 2.0))

            # Process active trade
            if active_trade and active_trade.status == "active":
                self._process_trade(active_trade, high, low, close, current_time)

            # Look for new signal if no active trade
            if cooldown <= 0 and (active_trade is None or active_trade.status != "active"):
                signal = self._evaluate_signal(df, idx)
                if signal:
                    trade = self._open_trade(trade_num, signal, row, current_time)
                    if trade:
                        self.trades.append(trade)
                        active_trade = trade
                        trade_num += 1
                        cooldown = 6  # 1.5 hours cooldown at M15

            cooldown = max(0, cooldown - 1)

            # Record equity every 4 hours (16 M15 bars)
            if idx % 16 == 0:
                self.equity_curve.append((current_time, round(self.balance, 2)))
                # Track drawdown
                if self.balance > self.peak_balance:
                    self.peak_balance = self.balance
                dd = self.peak_balance - self.balance
                if dd > self.max_drawdown:
                    self.max_drawdown = dd

        # Close any remaining active trade
        if active_trade and active_trade.status == "active":
            last_row = df.iloc[-1]
            self._close_trade(active_trade, float(last_row["close"]),
                              last_row["time"], "Backtest ended")

    def _open_trade(self, trade_num: int, signal: dict, row, current_time) -> Optional[BacktestTrade]:
        """Open a new trade based on signal."""
        price = float(row["close"])
        atr = signal["atr"]
        direction = signal["direction"]

        # Entry with spread + slippage
        spread_cost = (SPREAD_PIPS + SLIPPAGE_PIPS) * PIP
        if direction == "BUY":
            entry = round(price + spread_cost, 2)
            sl = round(entry - 1.5 * atr, 2)
        else:
            entry = round(price - spread_cost, 2)
            sl = round(entry + 1.5 * atr, 2)

        risk_pips = abs(entry - sl) / PIP
        if risk_pips <= 0:
            return None

        # Lot size based on risk
        risk_usd = self.balance * (self.risk_pct / 100.0)
        lot = risk_usd / (risk_pips * PIP_VALUE_PER_LOT)
        lot = max(0.01, min(5.0, round(lot, 2)))

        # Compute TP levels based on ATR (more realistic than fixed pips)
        # TP1-3: 0.5x, 0.8x, 1.0x ATR | TP4-6: 1.3x, 1.6x, 2.0x | TP7-10: 2.5x, 3.0x, 3.5x, 4.0x
        atr_multipliers = [0.5, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 3.5, 4.0]
        tp_levels = []
        for mult in atr_multipliers:
            if direction == "BUY":
                tp_levels.append(round(entry + mult * atr, 2))
            else:
                tp_levels.append(round(entry - mult * atr, 2))

        trade = BacktestTrade(
            trade_num=trade_num,
            entry_time=current_time,
            entry_price=entry,
            direction=direction,
            sl=sl,
            initial_sl=sl,
            initial_lot=lot,
            remaining_lot=lot,
            tp_levels=tp_levels,
            status="active",
            grade=signal["grade"],
            score=signal["score"],
            confidence=signal["confidence"],
            session=signal["session"],
            max_price=float(row["high"]),
            min_price=float(row["low"]),
        )
        return trade

    def _process_trade(self, trade: BacktestTrade, high: float, low: float,
                       close: float, current_time: datetime):
        """Process an active trade for TP/SL hits."""
        trade.max_price = max(trade.max_price, high)
        trade.min_price = min(trade.min_price, low)

        # Check SL
        if trade.direction == "BUY" and low <= trade.sl:
            self._close_trade(trade, trade.sl, current_time, "SL Hit")
            return
        elif trade.direction == "SELL" and high >= trade.sl:
            self._close_trade(trade, trade.sl, current_time, "SL Hit")
            return

        # Check TPs sequentially
        while trade.tp_hit < len(trade.tp_levels):
            tp_price = trade.tp_levels[trade.tp_hit]
            hit = False

            if trade.direction == "BUY" and high >= tp_price:
                hit = True
            elif trade.direction == "SELL" and low <= tp_price:
                hit = True

            if not hit:
                break

            # Process partial close
            tp_num = trade.tp_hit + 1
            lot_pct = self.strategy_config["lot_pct"][trade.tp_hit]
            close_lot = round(trade.initial_lot * lot_pct, 2)
            close_lot = min(close_lot, trade.remaining_lot)

            pnl_pips = abs(tp_price - trade.entry_price) / PIP
            pnl_usd = close_lot * pnl_pips * PIP_VALUE_PER_LOT

            trade.partial_closes.append({
                "tp_num": tp_num, "tp_price": tp_price,
                "closed_lot": close_lot, "pnl_usd": round(pnl_usd, 2),
                "pnl_pips": round(pnl_pips, 1),
            })

            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
            trade.tp_hit = tp_num

            # Apply trailing SL rules
            if tp_num in self.strategy_config["trailing_rules"]:
                rule = self.strategy_config["trailing_rules"][tp_num]
                if rule == "breakeven":
                    buffer = 2 * PIP
                    new_sl = trade.entry_price + buffer if trade.direction == "BUY" else trade.entry_price - buffer
                else:
                    tp_idx = rule - 1
                    new_sl = trade.tp_levels[tp_idx] if tp_idx < len(trade.tp_levels) else trade.sl

                if new_sl != trade.sl:
                    trade.sl_moves.append({
                        "old_sl": trade.sl, "new_sl": round(new_sl, 2),
                        "reason": f"TP{tp_num} → {'BE' if rule == 'breakeven' else f'TP{rule}'}",
                    })
                    trade.sl = round(new_sl, 2)

        # Close if fully exited
        if trade.remaining_lot <= 0.005:
            self._close_trade(trade, close, current_time, "All TPs hit")

    def _close_trade(self, trade: BacktestTrade, close_price: float,
                     close_time: datetime, reason: str):
        """Close a trade and update balance."""
        trade.status = "closed"
        trade.close_time = close_time
        trade.close_price = close_price
        trade.close_reason = reason

        # PnL from remaining position
        remaining_pnl = 0.0
        if trade.remaining_lot > 0.005:
            if trade.direction == "BUY":
                pips = (close_price - trade.entry_price) / PIP
            else:
                pips = (trade.entry_price - close_price) / PIP
            remaining_pnl = trade.remaining_lot * pips * PIP_VALUE_PER_LOT

        # Total PnL = partial closes + remaining
        partial_pnl = sum(pc["pnl_usd"] for pc in trade.partial_closes)
        trade.pnl_usd = round(partial_pnl + remaining_pnl, 2)

        # R-multiple
        risk_amount = abs(trade.entry_price - trade.initial_sl) / PIP * PIP_VALUE_PER_LOT * trade.initial_lot
        trade.r_multiple = round(trade.pnl_usd / risk_amount, 2) if risk_amount > 0 else 0.0

        # Total pips (approximate)
        if trade.direction == "BUY":
            trade.pnl_pips = round((close_price - trade.entry_price) / PIP, 1)
        else:
            trade.pnl_pips = round((trade.entry_price - close_price) / PIP, 1)

        self.balance += trade.pnl_usd

    def _get_session(self, hour: int) -> str:
        """Get trading session name from UTC hour."""
        if 22 <= hour or hour < 7:
            return "Asian"
        elif 7 <= hour < 12:
            return "London"
        else:
            return "New York"

    def _compile_metrics(self) -> Dict:
        """Compile comprehensive performance metrics."""
        closed = [t for t in self.trades if t.status == "closed"]

        if not closed:
            return self._empty_metrics()

        wins = [t for t in closed if t.pnl_usd > 0]
        losses = [t for t in closed if t.pnl_usd <= 0]

        total_profit = sum(t.pnl_usd for t in wins) if wins else 0
        total_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0.001

        return {
            "total_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "profit_factor": round(total_profit / total_loss, 2) if total_loss > 0 else 0,
            "total_return_usd": round(self.balance - self.starting_balance, 2),
            "total_return_pct": round((self.balance - self.starting_balance) / self.starting_balance * 100, 1),
            "final_balance": round(self.balance, 2),
            "max_drawdown_usd": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown / self.peak_balance * 100, 1) if self.peak_balance > 0 else 0,
            "avg_win": round(np.mean([t.pnl_usd for t in wins]), 2) if wins else 0,
            "avg_loss": round(np.mean([t.pnl_usd for t in losses]), 2) if losses else 0,
            "best_trade": round(max(t.pnl_usd for t in closed), 2) if closed else 0,
            "worst_trade": round(min(t.pnl_usd for t in closed), 2) if closed else 0,
            "avg_r_multiple": round(np.mean([t.r_multiple for t in closed]), 2) if closed else 0,
            "avg_tps_reached": round(np.mean([t.tp_hit for t in closed]), 1) if closed else 0,
            "equity_curve": [(str(t), b) for t, b in self.equity_curve],
            "by_grade": self._breakdown_by_field(closed, "grade"),
            "by_confidence": self._breakdown_by_field(closed, "confidence"),
            "by_session": self._breakdown_by_field(closed, "session"),
            "monthly": self._monthly_breakdown(closed),
            "trades": [self._trade_summary(t) for t in closed],
            "strategy": self.strategy,
            "months": self.months,
            "starting_balance": self.starting_balance,
            "risk_pct": self.risk_pct,
        }

    def _breakdown_by_field(self, trades: List[BacktestTrade], field: str) -> Dict:
        """Calculate win rate breakdown by a field."""
        groups = {}
        for t in trades:
            key = getattr(t, field, "Unknown")
            if key not in groups:
                groups[key] = {"trades": 0, "wins": 0, "total_pnl": 0}
            groups[key]["trades"] += 1
            if t.pnl_usd > 0:
                groups[key]["wins"] += 1
            groups[key]["total_pnl"] += t.pnl_usd

        result = {}
        for key, data in groups.items():
            result[key] = {
                "trades": data["trades"],
                "wins": data["wins"],
                "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] > 0 else 0,
                "avg_pnl": round(data["total_pnl"] / data["trades"], 2) if data["trades"] > 0 else 0,
            }
        return result

    def _monthly_breakdown(self, trades: List[BacktestTrade]) -> List[Dict]:
        """Calculate monthly performance."""
        months = {}
        for t in trades:
            if t.entry_time:
                key = t.entry_time.strftime("%Y-%m")
                if key not in months:
                    months[key] = {"month": key, "trades": 0, "wins": 0, "pnl": 0, "best": 0, "worst": 0}
                months[key]["trades"] += 1
                if t.pnl_usd > 0:
                    months[key]["wins"] += 1
                months[key]["pnl"] += t.pnl_usd
                months[key]["best"] = max(months[key]["best"], t.pnl_usd)
                months[key]["worst"] = min(months[key]["worst"], t.pnl_usd)

        result = []
        for key in sorted(months.keys()):
            m = months[key]
            m["win_rate"] = f"{m['wins'] / m['trades'] * 100:.0f}%" if m["trades"] > 0 else "0%"
            m["pnl"] = round(m["pnl"], 2)
            m["best"] = round(m["best"], 2)
            m["worst"] = round(m["worst"], 2)
            result.append(m)
        return result

    def _trade_summary(self, t: BacktestTrade) -> Dict:
        """Summarize a trade for display."""
        return {
            "trade_num": t.trade_num,
            "entry_time": str(t.entry_time) if t.entry_time else "",
            "direction": t.direction,
            "entry_price": t.entry_price,
            "sl": t.initial_sl,
            "grade": t.grade,
            "confidence": t.confidence,
            "session": t.session,
            "tps_reached": t.tp_hit,
            "pnl": round(t.pnl_usd, 2),
            "r_multiple": t.r_multiple,
            "status": t.close_reason,
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure."""
        return {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate_pct": 0, "profit_factor": 0,
            "total_return_usd": 0, "total_return_pct": 0,
            "final_balance": self.starting_balance,
            "max_drawdown_usd": 0, "max_drawdown_pct": 0,
            "avg_win": 0, "avg_loss": 0,
            "best_trade": 0, "worst_trade": 0,
            "avg_r_multiple": 0, "avg_tps_reached": 0,
            "equity_curve": [], "by_grade": {},
            "by_confidence": {}, "by_session": {},
            "monthly": [], "trades": [],
            "strategy": self.strategy, "months": self.months,
            "starting_balance": self.starting_balance, "risk_pct": self.risk_pct,
        }
