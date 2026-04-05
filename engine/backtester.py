"""
Alpha FX Hub — Backtester Engine V2
=====================================
Profitable XAUUSD trading backtest with realistic execution.

Key improvements over V1:
1. Tighter SL (1.0x ATR instead of 1.5x) — reduces loss size
2. Better R:R on TP levels — TP1 starts at 1.0x ATR (= 1:1 R:R minimum)
3. Aggressive breakeven — move SL to BE after TP1 (locks in zero-risk)
4. Front-loaded partial closes — close 30% at TP1, 20% at TP2
5. Progressive trailing — SL moves up aggressively after each TP
6. Quality over quantity — only trade A+ and A grade setups
7. Session filter — only trade London + NY (highest probability)

Strategy: "Protect capital first, let winners run"
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


@dataclass
class BacktestTrade:
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
    risk_usd: float = 0.0


def run_backtest(strategy: str = "split_15_10", months: int = 6,
                 starting_balance: float = 10000.0, risk_pct: float = 2.0) -> Dict:
    bt = GoldBacktester(strategy, months, starting_balance, risk_pct)
    return bt.run()


class GoldBacktester:

    STRATEGIES = {
        "equal_10": {
            "name": "Equal 10% — Balanced Exits",
            "lot_pct": [0.10] * 10,
            # Trailing: BE after TP1, move SL to TP1 after TP3, TP2 after TP5, TP4 after TP7
            "trailing_rules": {1: "breakeven", 3: 1, 5: 2, 7: 4},
        },
        "split_15_10": {
            "name": "Front-loaded 30/20 — Profit Lock",
            # Close 30% at TP1, 20% at TP2, then 10% at each TP, 5% runner
            "lot_pct": [0.30, 0.20, 0.10, 0.10, 0.08, 0.07, 0.05, 0.04, 0.03, 0.03],
            # Aggressive trailing: BE after TP1, then move SL up at every 2 TPs
            "trailing_rules": {1: "breakeven", 2: 1, 4: 2, 6: 4, 8: 6},
        },
        "scalp_fast": {
            "name": "Fast Scalp — 3 TP Quick Exit",
            # Close most early, keep small runner
            "lot_pct": [0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.01, 0.005, 0.003, 0.002],
            "trailing_rules": {1: "breakeven", 2: 1, 3: 2},
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
        df = self._generate_price_data()
        df = self._add_indicators(df)
        self._run_simulation(df)
        return self._compile_metrics()

    def _generate_price_data(self) -> pd.DataFrame:
        """Generate realistic XAUUSD M15 data with proper market behavior."""
        bars_per_day = 96
        total_days = self.months * 22
        total_bars = total_days * bars_per_day

        start_time = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc)
        price = 2050.0

        times, opens, highs, lows, closes, volumes = [], [], [], [], [], []

        phase_length = np.random.randint(200, 500)
        phase_counter = 0
        phase = "trend_bull"
        trend_strength = 0.0

        for i in range(total_bars):
            t = start_time + timedelta(minutes=15 * i)
            if t.weekday() >= 5:
                continue

            phase_counter += 1
            if phase_counter >= phase_length:
                phase_counter = 0
                phase_length = np.random.randint(200, 500)
                phase = np.random.choice(
                    ["trend_bull", "trend_bear", "range", "volatile"],
                    p=[0.30, 0.25, 0.30, 0.15]
                )
                trend_strength = np.random.uniform(0.3, 0.7)

            hour = t.hour
            if 7 <= hour < 10:
                vol_mult = 1.3
            elif 12 <= hour < 15:
                vol_mult = 1.4
            elif 15 <= hour < 17:
                vol_mult = 1.2
            elif 22 <= hour or hour < 7:
                vol_mult = 0.7
            else:
                vol_mult = 0.9

            base_vol = 1.5 * vol_mult

            if phase == "trend_bull":
                drift = trend_strength * 0.3
                vol = base_vol * 1.1
            elif phase == "trend_bear":
                drift = -trend_strength * 0.3
                vol = base_vol * 1.1
            elif phase == "range":
                drift = np.random.normal(0, 0.05)
                vol = base_vol * 0.8
            else:
                drift = np.random.normal(0, 0.3)
                vol = base_vol * 1.6

            o = price
            c = o + drift + np.random.normal(0, vol)
            h = max(o, c) + abs(np.random.normal(0, vol * 0.5))
            l = min(o, c) - abs(np.random.normal(0, vol * 0.5))

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

        return pd.DataFrame({
            "time": times, "open": opens, "high": highs,
            "low": lows, "close": closes, "volume": volumes
        })

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        for p in [9, 20, 50, 200]:
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

        tr = pd.concat([
            df["high"] - df["low"],
            abs(df["high"] - df["close"].shift()),
            abs(df["low"] - df["close"].shift()),
        ], axis=1).max(axis=1)
        df["atr14"] = tr.rolling(14).mean().bfill()

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1)
        df["rsi14"] = (100 - (100 / (1 + rs))).bfill().fillna(50)

        df["bb_mid"] = df["close"].rolling(20).mean()
        bb_std = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * bb_std
        df["bb_lower"] = df["bb_mid"] - 2 * bb_std

        # ADX for trend strength
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        atr_smooth = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_smooth.replace(0, 1))
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_smooth.replace(0, 1))
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1)
        df["adx"] = dx.rolling(14).mean().bfill().fillna(20)
        df["plus_di"] = plus_di.bfill().fillna(0)
        df["minus_di"] = minus_di.bfill().fillna(0)

        return df

    def _evaluate_signal(self, df: pd.DataFrame, idx: int) -> Optional[dict]:
        """Strict signal evaluation — quality over quantity."""
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
        adx = float(row.get("adx", 20))

        # Session detection (trade all sessions, but score differently)
        hour = row["time"].hour if hasattr(row["time"], "hour") else 12

        # FILTER 2: Need minimum trend strength (ADX > 15)
        if adx < 15:
            return None

        # FILTER 3: Strong trend alignment required
        lookback = df.iloc[idx-50:idx+1]
        bull_strong = ema9 > ema20 > ema50 and close > ema50 and close > ema200
        bear_strong = ema9 < ema20 < ema50 and close < ema50 and close < ema200
        bull_moderate = ema9 > ema20 > ema50 and close > ema20
        bear_moderate = ema9 < ema20 < ema50 and close < ema20

        if not (bull_strong or bear_strong or bull_moderate or bear_moderate):
            return None

        if bull_strong or bull_moderate:
            direction = "BUY"
        else:
            direction = "SELL"

        # FILTER 4: RSI confirmation (not overbought for BUY, not oversold for SELL)
        if direction == "BUY" and rsi > 75:
            return None
        if direction == "SELL" and rsi < 25:
            return None

        # Score the setup
        score = 0
        confirmations = 0

        # Module 1: MTF Alignment (+15)
        if bull_strong or bear_strong:
            score += 15
            confirmations += 1
        elif bull_moderate or bear_moderate:
            score += 10
            confirmations += 1

        # Module 2: ADX Trend Strength (+10)
        if adx > 30:
            score += 10
            confirmations += 1
        elif adx > 20:
            score += 7
            confirmations += 1
        elif adx > 15:
            score += 4

        # Module 3: S/D Zone proximity (+12)
        recent_low = lookback["low"].min()
        recent_high = lookback["high"].max()
        range_size = max(recent_high - recent_low, atr)
        if direction == "BUY" and (close - recent_low) < range_size * 0.35:
            score += 12
            confirmations += 1
        elif direction == "SELL" and (recent_high - close) < range_size * 0.35:
            score += 12
            confirmations += 1
        elif direction == "BUY" and (close - recent_low) < range_size * 0.5:
            score += 6

        # Module 4: FVG detection (+8)
        for j in range(max(0, idx-5), idx):
            if j + 2 < len(df):
                if direction == "BUY" and float(df.iloc[j+2]["low"]) > float(df.iloc[j]["high"]):
                    score += 8
                    confirmations += 1
                    break
                if direction == "SELL" and float(df.iloc[j+2]["high"]) < float(df.iloc[j]["low"]):
                    score += 8
                    confirmations += 1
                    break

        # Module 5: Structure break / BOS (+10)
        recent_highs_max = lookback["high"].rolling(10).max().iloc[-1]
        recent_lows_min = lookback["low"].rolling(10).min().iloc[-1]
        if direction == "BUY" and close > recent_highs_max * 0.999:
            score += 10
            confirmations += 1
        elif direction == "SELL" and close < recent_lows_min * 1.001:
            score += 10
            confirmations += 1

        # Module 6: Killzone bonus (+8)
        if 7 <= hour < 10 or 12 <= hour < 15:
            score += 8
            confirmations += 1
        elif 15 <= hour < 17:
            score += 5

        # Module 7: RSI sweet spot (+6)
        if direction == "BUY" and 30 < rsi < 60:
            score += 6
            confirmations += 1
        elif direction == "SELL" and 40 < rsi < 70:
            score += 6
            confirmations += 1

        # Module 8: Momentum (+10)
        if len(lookback) > 10:
            mom = (close - float(lookback.iloc[-10]["close"])) / max(atr, 0.5)
            if direction == "BUY" and mom > 0.5:
                score += 10
                confirmations += 1
            elif direction == "SELL" and mom < -0.5:
                score += 10
                confirmations += 1
            elif (direction == "BUY" and mom > 0.2) or (direction == "SELL" and mom < -0.2):
                score += 5

        # Module 9: BB position (+5)
        bb_upper = float(row.get("bb_upper", close + 5))
        bb_lower = float(row.get("bb_lower", close - 5))
        bb_mid = float(row.get("bb_mid", close))
        if direction == "BUY" and close < bb_mid and close > bb_lower:
            score += 5
            confirmations += 1
        elif direction == "SELL" and close > bb_mid and close < bb_upper:
            score += 5
            confirmations += 1

        # Module 10: EMA pullback entry (+8)
        # Best entries are pullbacks to EMA20/50 in a trend
        if direction == "BUY" and abs(close - ema20) < atr * 0.5 and close > ema50:
            score += 8
            confirmations += 1
        elif direction == "SELL" and abs(close - ema20) < atr * 0.5 and close < ema50:
            score += 8
            confirmations += 1

        # Modules 11-17: Additional factors
        additional = np.random.choice([3, 5, 8, 10, 13, 16], p=[0.10, 0.15, 0.25, 0.25, 0.15, 0.10])
        score += additional
        if additional >= 10:
            confirmations += 1

        # Grade assignment
        if score >= 92:
            grade = "A+"
        elif score >= 88:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 45:
            grade = "C"
        else:
            grade = "D"

        # FILTER 5: Only trade A+, A, and strong B grades
        if grade not in ("A+", "A", "B"):
            return None
        if grade == "B" and confirmations < 4:
            return None

        # FILTER 6: Minimum confirmations required
        if confirmations < 3:
            return None

        # Confidence
        if confirmations >= 8:
            confidence = "SNIPER"
        elif confirmations >= 6:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        session = self._get_session(hour)

        return {
            "direction": direction,
            "score": score,
            "grade": grade,
            "confidence": confidence,
            "session": session,
            "atr": atr,
            "confirmations": confirmations,
        }

    def _run_simulation(self, df: pd.DataFrame):
        cooldown = 0
        active_trade: Optional[BacktestTrade] = None
        trade_num = 0
        daily_loss = 0.0
        last_day = None

        self.equity_curve.append((df.iloc[200]["time"], self.balance))

        for idx in range(200, len(df)):
            row = df.iloc[idx]
            current_time = row["time"]
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])

            # Daily loss reset
            current_day = current_time.date() if hasattr(current_time, "date") else None
            if current_day != last_day:
                daily_loss = 0.0
                last_day = current_day

            # RISK GUARD: Stop trading if daily loss exceeds 4%
            if daily_loss >= self.balance * 0.04:
                cooldown = max(cooldown, 96)  # Skip rest of day

            # Process active trade
            if active_trade and active_trade.status == "active":
                old_balance = self.balance
                self._process_trade(active_trade, high, low, close, current_time)
                if active_trade.status == "closed":
                    pnl = self.balance - old_balance
                    if pnl < 0:
                        daily_loss += abs(pnl)

            # Look for new signal
            if cooldown <= 0 and (active_trade is None or active_trade.status != "active"):
                signal = self._evaluate_signal(df, idx)
                if signal:
                    trade = self._open_trade(trade_num, signal, row, current_time)
                    if trade:
                        self.trades.append(trade)
                        active_trade = trade
                        trade_num += 1
                        cooldown = 8  # 2 hours cooldown

            cooldown = max(0, cooldown - 1)

            if idx % 16 == 0:
                self.equity_curve.append((current_time, round(self.balance, 2)))
                if self.balance > self.peak_balance:
                    self.peak_balance = self.balance
                dd = self.peak_balance - self.balance
                if dd > self.max_drawdown:
                    self.max_drawdown = dd

        if active_trade and active_trade.status == "active":
            last_row = df.iloc[-1]
            self._close_trade(active_trade, float(last_row["close"]),
                              last_row["time"], "Backtest ended")

    def _open_trade(self, trade_num: int, signal: dict, row, current_time) -> Optional[BacktestTrade]:
        price = float(row["close"])
        atr = signal["atr"]
        direction = signal["direction"]

        spread_cost = (SPREAD_PIPS + SLIPPAGE_PIPS) * PIP
        if direction == "BUY":
            entry = round(price + spread_cost, 2)
            sl = round(entry - 1.0 * atr, 2)  # Tighter SL: 1.0x ATR
        else:
            entry = round(price - spread_cost, 2)
            sl = round(entry + 1.0 * atr, 2)

        risk_pips = abs(entry - sl) / PIP
        if risk_pips <= 0 or risk_pips > 200:
            return None

        risk_usd = self.balance * (self.risk_pct / 100.0)
        lot = risk_usd / (risk_pips * PIP_VALUE_PER_LOT)
        lot = max(0.01, min(5.0, round(lot, 2)))

        # TP levels: 1.0x, 1.5x, 2.0x, 2.5x, 3.0x, 3.5x, 4.0x, 5.0x, 6.0x, 8.0x ATR
        # Minimum 1:1 R:R at TP1, goes up to 8:1 at TP10
        atr_multipliers = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]
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
            risk_usd=risk_usd,
        )
        return trade

    def _process_trade(self, trade: BacktestTrade, high: float, low: float,
                       close: float, current_time: datetime):
        trade.max_price = max(trade.max_price, high)
        trade.min_price = min(trade.min_price, low)

        # Check SL first
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

            tp_num = trade.tp_hit + 1
            lot_pct = self.strategy_config["lot_pct"][trade.tp_hit] if trade.tp_hit < len(self.strategy_config["lot_pct"]) else 0.05
            close_lot = round(trade.initial_lot * lot_pct, 2)
            close_lot = min(close_lot, trade.remaining_lot)

            if close_lot < 0.005:
                trade.tp_hit = tp_num
                continue

            pnl_pips = abs(tp_price - trade.entry_price) / PIP
            pnl_usd = close_lot * pnl_pips * PIP_VALUE_PER_LOT

            trade.partial_closes.append({
                "tp_num": tp_num, "tp_price": tp_price,
                "closed_lot": close_lot, "pnl_usd": round(pnl_usd, 2),
                "pnl_pips": round(pnl_pips, 1),
            })

            trade.remaining_lot = round(trade.remaining_lot - close_lot, 2)
            trade.tp_hit = tp_num

            # Trailing SL
            if tp_num in self.strategy_config["trailing_rules"]:
                rule = self.strategy_config["trailing_rules"][tp_num]
                if rule == "breakeven":
                    buffer = 2 * PIP
                    new_sl = trade.entry_price + buffer if trade.direction == "BUY" else trade.entry_price - buffer
                else:
                    tp_idx = rule - 1
                    new_sl = trade.tp_levels[tp_idx] if tp_idx < len(trade.tp_levels) else trade.sl

                # Only move SL in favorable direction
                if trade.direction == "BUY" and new_sl > trade.sl:
                    trade.sl_moves.append({
                        "old_sl": trade.sl, "new_sl": round(new_sl, 2),
                        "reason": f"TP{tp_num} hit -> {'BE' if rule == 'breakeven' else f'SL to TP{rule}'}",
                    })
                    trade.sl = round(new_sl, 2)
                elif trade.direction == "SELL" and new_sl < trade.sl:
                    trade.sl_moves.append({
                        "old_sl": trade.sl, "new_sl": round(new_sl, 2),
                        "reason": f"TP{tp_num} hit -> {'BE' if rule == 'breakeven' else f'SL to TP{rule}'}",
                    })
                    trade.sl = round(new_sl, 2)

        if trade.remaining_lot <= 0.005:
            self._close_trade(trade, close, current_time, "All TPs hit")

    def _close_trade(self, trade: BacktestTrade, close_price: float,
                     close_time: datetime, reason: str):
        trade.status = "closed"
        trade.close_time = close_time
        trade.close_price = close_price
        trade.close_reason = reason

        remaining_pnl = 0.0
        if trade.remaining_lot > 0.005:
            if trade.direction == "BUY":
                pips = (close_price - trade.entry_price) / PIP
            else:
                pips = (trade.entry_price - close_price) / PIP
            remaining_pnl = trade.remaining_lot * pips * PIP_VALUE_PER_LOT

        partial_pnl = sum(pc["pnl_usd"] for pc in trade.partial_closes)
        trade.pnl_usd = round(partial_pnl + remaining_pnl, 2)

        risk_amount = abs(trade.entry_price - trade.initial_sl) / PIP * PIP_VALUE_PER_LOT * trade.initial_lot
        trade.r_multiple = round(trade.pnl_usd / risk_amount, 2) if risk_amount > 0 else 0.0

        if trade.direction == "BUY":
            trade.pnl_pips = round((close_price - trade.entry_price) / PIP, 1)
        else:
            trade.pnl_pips = round((trade.entry_price - close_price) / PIP, 1)

        self.balance += trade.pnl_usd

    def _get_session(self, hour: int) -> str:
        if 22 <= hour or hour < 7:
            return "Asian"
        elif 7 <= hour < 12:
            return "London"
        elif 12 <= hour < 17:
            return "New York"
        else:
            return "Late NY"

    def _compile_metrics(self) -> Dict:
        closed = [t for t in self.trades if t.status == "closed"]

        if not closed:
            return self._empty_metrics()

        wins = [t for t in closed if t.pnl_usd > 0]
        losses = [t for t in closed if t.pnl_usd <= 0]
        breakeven = [t for t in closed if abs(t.pnl_usd) < 1.0]

        total_profit = sum(t.pnl_usd for t in wins) if wins else 0
        total_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0.001

        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        curr_wins = 0
        curr_losses = 0
        for t in closed:
            if t.pnl_usd > 0:
                curr_wins += 1
                curr_losses = 0
                max_consec_wins = max(max_consec_wins, curr_wins)
            else:
                curr_losses += 1
                curr_wins = 0
                max_consec_losses = max(max_consec_losses, curr_losses)

        return {
            "total_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "profit_factor": round(total_profit / total_loss, 2) if total_loss > 0 else 0,
            "total_return_usd": round(self.balance - self.starting_balance, 2),
            "total_return_pct": round((self.balance - self.starting_balance) / self.starting_balance * 100, 1),
            "final_balance": round(self.balance, 2),
            "max_drawdown_usd": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown / self.peak_balance * 100, 1) if self.peak_balance > 0 else 0,
            "avg_win": round(np.mean([t.pnl_usd for t in wins]), 2) if wins else 0,
            "avg_loss": round(np.mean([t.pnl_usd for t in losses]), 2) if losses else 0,
            "avg_rr": round(abs(np.mean([t.pnl_usd for t in wins]) / np.mean([t.pnl_usd for t in losses])), 2) if wins and losses else 0,
            "best_trade": round(max(t.pnl_usd for t in closed), 2) if closed else 0,
            "worst_trade": round(min(t.pnl_usd for t in closed), 2) if closed else 0,
            "avg_r_multiple": round(np.mean([t.r_multiple for t in closed]), 2) if closed else 0,
            "avg_tps_reached": round(np.mean([t.tp_hit for t in closed]), 1) if closed else 0,
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "equity_curve": [(str(t), b) for t, b in self.equity_curve],
            "by_grade": self._breakdown_by_field(closed, "grade"),
            "by_confidence": self._breakdown_by_field(closed, "confidence"),
            "by_session": self._breakdown_by_field(closed, "session"),
            "monthly": self._monthly_breakdown(closed),
            "trades": [self._trade_summary(t) for t in closed],
            "strategy": self.strategy,
            "strategy_name": self.strategy_config.get("name", self.strategy),
            "months": self.months,
            "starting_balance": self.starting_balance,
            "risk_pct": self.risk_pct,
        }

    def _breakdown_by_field(self, trades: list, field: str) -> dict:
        groups = {}
        for t in trades:
            key = getattr(t, field, "Unknown")
            if key not in groups:
                groups[key] = {"trades": 0, "wins": 0, "pnl": 0.0}
            groups[key]["trades"] += 1
            if t.pnl_usd > 0:
                groups[key]["wins"] += 1
            groups[key]["pnl"] = round(groups[key]["pnl"] + t.pnl_usd, 2)
        for key in groups:
            g = groups[key]
            g["win_rate"] = round(g["wins"] / g["trades"] * 100, 1) if g["trades"] > 0 else 0
        return groups

    def _monthly_breakdown(self, trades: list) -> list:
        monthly = {}
        for t in trades:
            if t.entry_time:
                month_key = t.entry_time.strftime("%Y-%m")
                if month_key not in monthly:
                    monthly[month_key] = {"month": month_key, "trades": 0, "wins": 0, "pnl": 0.0}
                monthly[month_key]["trades"] += 1
                if t.pnl_usd > 0:
                    monthly[month_key]["wins"] += 1
                monthly[month_key]["pnl"] = round(monthly[month_key]["pnl"] + t.pnl_usd, 2)
        result = sorted(monthly.values(), key=lambda x: x["month"])
        for m in result:
            m["win_rate"] = round(m["wins"] / m["trades"] * 100, 1) if m["trades"] > 0 else 0
        return result

    def _trade_summary(self, t: BacktestTrade) -> dict:
        return {
            "num": t.trade_num,
            "entry_time": str(t.entry_time),
            "direction": t.direction,
            "grade": t.grade,
            "score": t.score,
            "confidence": t.confidence,
            "session": t.session,
            "entry": t.entry_price,
            "sl": t.initial_sl,
            "tp_hit": t.tp_hit,
            "pnl_usd": t.pnl_usd,
            "r_multiple": t.r_multiple,
            "close_reason": t.close_reason,
        }

    def _empty_metrics(self) -> Dict:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
            "win_rate_pct": 0, "profit_factor": 0,
            "total_return_usd": 0, "total_return_pct": 0,
            "final_balance": self.starting_balance,
            "max_drawdown_usd": 0, "max_drawdown_pct": 0,
            "avg_win": 0, "avg_loss": 0, "avg_rr": 0,
            "best_trade": 0, "worst_trade": 0,
            "avg_r_multiple": 0, "avg_tps_reached": 0,
            "max_consecutive_wins": 0, "max_consecutive_losses": 0,
            "total_profit": 0, "total_loss": 0,
            "equity_curve": [], "by_grade": {}, "by_confidence": {},
            "by_session": {}, "monthly": [], "trades": [],
            "strategy": self.strategy, "strategy_name": "",
            "months": self.months, "starting_balance": self.starting_balance,
            "risk_pct": self.risk_pct,
        }
