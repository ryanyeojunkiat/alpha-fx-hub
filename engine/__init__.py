"""Alpha FX Hub — Gold Trading Engine (V4 Hybrid)"""
from .indicators import add_indicators, find_swing_points, fibonacci_levels
from .gold_engine import gold_engine_score, detect_choch_realtime, detect_fvg_entry
from .levels import compute_levels, compute_lot, spike_adjusted_levels
from .data import fetch_bars, fetch_price
from .signal_scanner import SignalScanner, Signal
