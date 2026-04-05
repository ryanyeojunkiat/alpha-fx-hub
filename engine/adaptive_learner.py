"""
Alpha FX Hub — Adaptive Learning Engine
Analyzes trade history to discover patterns and improve signal quality.

Learns from:
- Which sessions (Asian/London/NY) perform best
- Which days of week are most profitable
- Optimal entry conditions (RSI, ADX, ATR ranges)
- Best grade/confidence levels
- Trend direction accuracy
- Volatility regime performance
- News impact correlation

Outputs adjustable weights that the signal scanner can use to filter/boost signals.
"""
import logging
import json
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger("alpha_fx_hub.adaptive_learner")


@dataclass
class LearningInsight:
    """A single insight from trade history analysis."""
    category: str       # session, day, grade, trend, volatility, news, indicator
    key: str            # e.g. "London", "Monday", "A+", "bullish"
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    total_pnl: float = 0.0
    avg_rr: float = 0.0          # Average risk:reward realized
    recommendation: str = ""     # "boost" / "avoid" / "neutral"
    weight_adjustment: float = 1.0  # Multiplier: >1 = boost, <1 = reduce, 0 = block


@dataclass
class AdaptiveProfile:
    """Aggregated learning profile for signal adjustments."""
    total_trades_analyzed: int = 0
    last_updated: str = ""

    # Session preferences (weight multipliers)
    session_weights: Dict[str, float] = field(default_factory=lambda: {
        "Asian": 1.0, "London": 1.0, "New York": 1.0, "Late NY": 1.0
    })

    # Day-of-week preferences
    day_weights: Dict[str, float] = field(default_factory=lambda: {
        "Monday": 1.0, "Tuesday": 1.0, "Wednesday": 1.0,
        "Thursday": 1.0, "Friday": 1.0
    })

    # Optimal indicator ranges (learned from profitable trades)
    optimal_rsi_range: Tuple[float, float] = (30.0, 70.0)
    optimal_adx_min: float = 15.0
    optimal_atr_range: Tuple[float, float] = (5.0, 50.0)

    # Grade performance
    grade_weights: Dict[str, float] = field(default_factory=lambda: {
        "A+": 1.0, "A": 1.0, "B": 1.0, "C": 0.5
    })

    # Trend alignment
    trend_weights: Dict[str, float] = field(default_factory=lambda: {
        "bullish": 1.0, "bearish": 1.0, "ranging": 0.8
    })

    # Volatility
    volatility_weights: Dict[str, float] = field(default_factory=lambda: {
        "low": 1.0, "normal": 1.0, "high": 1.0, "extreme": 0.5
    })

    # Best performing strategy
    best_strategy: str = "split_15_10"

    # Key insights (human-readable)
    insights: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert tuples to lists for JSON serialization
        d["optimal_rsi_range"] = list(self.optimal_rsi_range)
        d["optimal_atr_range"] = list(self.optimal_atr_range)
        return d


class AdaptiveLearner:
    """
    Analyzes trade history and produces an AdaptiveProfile
    that the signal scanner can use for better signal filtering.
    """

    MIN_TRADES_FOR_LEARNING = 10  # Need at least this many trades to start learning
    MIN_CATEGORY_TRADES = 3       # Need 3+ trades in a category to form opinion

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.profile = AdaptiveProfile()
        self._load_profile()

    def analyze(self, trades: List[dict]) -> AdaptiveProfile:
        """
        Analyze trade history and update the adaptive profile.
        trades: list of trade dicts with learning metadata.
        """
        if len(trades) < self.MIN_TRADES_FOR_LEARNING:
            logger.info(f"Only {len(trades)} trades — need {self.MIN_TRADES_FOR_LEARNING} to start learning")
            self.profile.insights = [
                f"Need {self.MIN_TRADES_FOR_LEARNING - len(trades)} more trades to start adaptive learning."
            ]
            return self.profile

        from datetime import datetime, timezone
        self.profile.total_trades_analyzed = len(trades)
        self.profile.last_updated = datetime.now(timezone.utc).isoformat()
        self.profile.insights = []

        # ── Analyze by category ──
        self._analyze_sessions(trades)
        self._analyze_days(trades)
        self._analyze_grades(trades)
        self._analyze_trends(trades)
        self._analyze_volatility(trades)
        self._analyze_indicators(trades)
        self._analyze_strategies(trades)
        self._analyze_news_impact(trades)

        self._save_profile()
        return self.profile

    def get_signal_multiplier(self, signal_context: dict) -> float:
        """
        Given signal context, return an overall weight multiplier.
        >1.0 = boosted signal, <1.0 = reduced confidence, 0 = block.
        """
        multiplier = 1.0

        session = signal_context.get("session_name", "")
        if session in self.profile.session_weights:
            multiplier *= self.profile.session_weights[session]

        day = signal_context.get("day_name", "")
        if day in self.profile.day_weights:
            multiplier *= self.profile.day_weights[day]

        grade = signal_context.get("grade", "")
        if grade in self.profile.grade_weights:
            multiplier *= self.profile.grade_weights[grade]

        trend = signal_context.get("trend", "")
        if trend in self.profile.trend_weights:
            multiplier *= self.profile.trend_weights[trend]

        vol = signal_context.get("volatility_regime", "")
        if vol in self.profile.volatility_weights:
            multiplier *= self.profile.volatility_weights[vol]

        return round(multiplier, 3)

    # ── Category Analyzers ─────────────────────────────────────

    def _analyze_sessions(self, trades: List[dict]):
        """Which trading sessions perform best?"""
        stats = self._group_stats(trades, "session_name")
        for session, s in stats.items():
            if s["count"] >= self.MIN_CATEGORY_TRADES:
                weight = self._calculate_weight(s)
                self.profile.session_weights[session] = weight
                if weight > 1.15:
                    self.profile.insights.append(
                        f"Strong performance in {session} session "
                        f"({s['win_rate']:.0f}% WR, avg ${s['avg_pnl']:.1f})"
                    )
                elif weight < 0.7:
                    self.profile.insights.append(
                        f"Weak performance in {session} session "
                        f"({s['win_rate']:.0f}% WR, avg ${s['avg_pnl']:.1f}) — reducing weight"
                    )

    def _analyze_days(self, trades: List[dict]):
        """Which days of the week are most profitable?"""
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for t in trades:
            dow = t.get("day_of_week")
            if dow is not None and 0 <= dow <= 6:
                t["_day_name"] = day_names[dow]
            else:
                t["_day_name"] = "Unknown"

        stats = self._group_stats(trades, "_day_name")
        for day, s in stats.items():
            if day in self.profile.day_weights and s["count"] >= self.MIN_CATEGORY_TRADES:
                weight = self._calculate_weight(s)
                self.profile.day_weights[day] = weight
                if weight > 1.15:
                    self.profile.insights.append(
                        f"{day}s are strong ({s['win_rate']:.0f}% WR, +${s['total_pnl']:.0f} total)"
                    )
                elif weight < 0.7:
                    self.profile.insights.append(
                        f"{day}s underperform ({s['win_rate']:.0f}% WR, ${s['total_pnl']:.0f}) — be cautious"
                    )

    def _analyze_grades(self, trades: List[dict]):
        """Which signal grades actually deliver?"""
        stats = self._group_stats(trades, "grade")
        for grade, s in stats.items():
            if grade in self.profile.grade_weights and s["count"] >= self.MIN_CATEGORY_TRADES:
                weight = self._calculate_weight(s)
                self.profile.grade_weights[grade] = weight

    def _analyze_trends(self, trades: List[dict]):
        """Trend alignment performance."""
        stats = self._group_stats(trades, "trend_at_entry")
        for trend, s in stats.items():
            if trend in self.profile.trend_weights and s["count"] >= self.MIN_CATEGORY_TRADES:
                weight = self._calculate_weight(s)
                self.profile.trend_weights[trend] = weight
                if trend == "ranging" and weight < 0.8:
                    self.profile.insights.append(
                        "Ranging market trades underperform — prefer trending conditions"
                    )

    def _analyze_volatility(self, trades: List[dict]):
        """How does volatility regime affect results?"""
        stats = self._group_stats(trades, "volatility_regime")
        for vol, s in stats.items():
            if vol in self.profile.volatility_weights and s["count"] >= self.MIN_CATEGORY_TRADES:
                weight = self._calculate_weight(s)
                self.profile.volatility_weights[vol] = weight
                if vol == "extreme" and weight < 0.6:
                    self.profile.insights.append(
                        "Extreme volatility hurts — consider sitting out during major spikes"
                    )

    def _analyze_indicators(self, trades: List[dict]):
        """Find optimal indicator ranges from winning trades."""
        winners = [t for t in trades if (t.get("pnl_usd") or 0) > 0]
        if len(winners) < self.MIN_CATEGORY_TRADES:
            return

        # RSI
        rsi_vals = [t["rsi_at_entry"] for t in winners if t.get("rsi_at_entry")]
        if len(rsi_vals) >= 5:
            rsi_vals.sort()
            p10 = rsi_vals[int(len(rsi_vals) * 0.1)]
            p90 = rsi_vals[int(len(rsi_vals) * 0.9)]
            self.profile.optimal_rsi_range = (round(p10, 1), round(p90, 1))
            self.profile.insights.append(
                f"Winning trades RSI sweet spot: {p10:.0f}-{p90:.0f}"
            )

        # ADX
        adx_vals = [t["adx_at_entry"] for t in winners if t.get("adx_at_entry")]
        if len(adx_vals) >= 5:
            adx_vals.sort()
            p25 = adx_vals[int(len(adx_vals) * 0.25)]
            self.profile.optimal_adx_min = round(p25, 1)
            self.profile.insights.append(
                f"Winning trades typically have ADX > {p25:.0f}"
            )

        # ATR
        atr_vals = [t["atr_at_entry"] for t in winners if t.get("atr_at_entry")]
        if len(atr_vals) >= 5:
            atr_vals.sort()
            p10 = atr_vals[int(len(atr_vals) * 0.1)]
            p90 = atr_vals[int(len(atr_vals) * 0.9)]
            self.profile.optimal_atr_range = (round(p10, 2), round(p90, 2))

    def _analyze_strategies(self, trades: List[dict]):
        """Which TP/SL strategy performs best?"""
        stats = self._group_stats(trades, "strategy")
        best_strat = None
        best_pnl = float("-inf")
        for strat, s in stats.items():
            if s["count"] >= self.MIN_CATEGORY_TRADES and s["avg_pnl"] > best_pnl:
                best_pnl = s["avg_pnl"]
                best_strat = strat
        if best_strat:
            self.profile.best_strategy = best_strat
            self.profile.insights.append(
                f"Best performing strategy: {best_strat} (avg ${best_pnl:.1f}/trade)"
            )

    def _analyze_news_impact(self, trades: List[dict]):
        """Performance around high-impact news."""
        stats = self._group_stats(trades, "news_impact")
        for impact, s in stats.items():
            if impact == "high" and s["count"] >= self.MIN_CATEGORY_TRADES:
                if s["win_rate"] < 40:
                    self.profile.insights.append(
                        f"High-impact news trades are risky ({s['win_rate']:.0f}% WR) — consider avoiding"
                    )
                elif s["win_rate"] > 60:
                    self.profile.insights.append(
                        f"High-impact news trades performing well ({s['win_rate']:.0f}% WR)"
                    )

    # ── Utility Methods ────────────────────────────────────────

    def _group_stats(self, trades: List[dict], key: str) -> Dict[str, dict]:
        """Group trades by a key and compute stats."""
        groups = defaultdict(list)
        for t in trades:
            val = t.get(key, "Unknown")
            if val:
                groups[str(val)].append(t)

        stats = {}
        for group_name, group_trades in groups.items():
            pnls = [(t.get("pnl_usd") or 0) for t in group_trades]
            wins = sum(1 for p in pnls if p > 0)
            total = len(pnls)
            stats[group_name] = {
                "count": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": (wins / total * 100) if total > 0 else 0,
                "avg_pnl": sum(pnls) / total if total > 0 else 0,
                "total_pnl": sum(pnls),
            }
        return stats

    def _calculate_weight(self, stats: dict) -> float:
        """Calculate a weight multiplier from category stats.
        Based on win rate and average PnL relative to overall."""
        wr = stats["win_rate"]
        avg = stats["avg_pnl"]

        # Win rate component (50% = neutral)
        wr_factor = (wr - 50) / 50  # -1 to +1 range

        # PnL component (positive = good)
        pnl_factor = 0.0
        if avg > 0:
            pnl_factor = min(avg / 50, 1.0)  # Cap at +$50 effect
        elif avg < 0:
            pnl_factor = max(avg / 50, -1.0)

        # Combined weight: 1.0 = neutral, range 0.3 to 1.5
        weight = 1.0 + (wr_factor * 0.25) + (pnl_factor * 0.25)
        return round(max(0.3, min(1.5, weight)), 2)

    def _save_profile(self):
        """Save learning profile to local JSON."""
        try:
            path = self.data_dir / "adaptive_profile.json"
            with open(path, "w") as f:
                json.dump(self.profile.to_dict(), f, indent=2)
            logger.info("Adaptive profile saved")
        except Exception as e:
            logger.error(f"Failed to save adaptive profile: {e}")

    def _load_profile(self):
        """Load learning profile from local JSON."""
        path = self.data_dir / "adaptive_profile.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.profile.total_trades_analyzed = data.get("total_trades_analyzed", 0)
            self.profile.last_updated = data.get("last_updated", "")
            self.profile.session_weights.update(data.get("session_weights", {}))
            self.profile.day_weights.update(data.get("day_weights", {}))
            self.profile.grade_weights.update(data.get("grade_weights", {}))
            self.profile.trend_weights.update(data.get("trend_weights", {}))
            self.profile.volatility_weights.update(data.get("volatility_weights", {}))
            self.profile.best_strategy = data.get("best_strategy", "split_15_10")
            self.profile.insights = data.get("insights", [])

            rsi = data.get("optimal_rsi_range", [30, 70])
            self.profile.optimal_rsi_range = (rsi[0], rsi[1])
            atr = data.get("optimal_atr_range", [5, 50])
            self.profile.optimal_atr_range = (atr[0], atr[1])
            self.profile.optimal_adx_min = data.get("optimal_adx_min", 15.0)

            logger.info(f"Loaded adaptive profile ({self.profile.total_trades_analyzed} trades analyzed)")
        except Exception as e:
            logger.error(f"Failed to load adaptive profile: {e}")
