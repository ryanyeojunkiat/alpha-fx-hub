"""
Alpha FX Hub — Central Configuration
XAUUSD-focused gold trading platform.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)

# ── Helper: read from Streamlit secrets OR os.environ ────────
def _get_secret(key: str, default: str = "") -> str:
    """Try st.secrets first (Streamlit Cloud), then os.environ, then default."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)

# ── Platform Identity ────────────────────────────────────────
PLATFORM_NAME = "Alpha FX Hub"
ENGINE_NAME = "Alpha FX Engine"
PLATFORM_TAG = "alpha_fx_hub"
VERSION = "1.1.0"

# ── Telegram Configuration ───────────────────────────────────
# Bot: Alpha FX Pilot @alphaedge_gold_bot
TELEGRAM_BOT_TOKEN = _get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = "alphaedge_gold_bot"

# Public Channel: Alpha FX Hub (news + basic strategy for everyone)
TELEGRAM_PUBLIC_CHANNEL_ID = _get_secret("TELEGRAM_PUBLIC_CHANNEL_ID")
TELEGRAM_PUBLIC_CHANNEL_LINK = "https://t.me/+CskTnfXWW4s1YWI1"

# Private Channel: Alpha FX Edge (premium signals for subscribers)
TELEGRAM_PRIVATE_CHANNEL_ID = _get_secret("TELEGRAM_PRIVATE_CHANNEL_ID")
TELEGRAM_PRIVATE_CHANNEL_LINK = "https://t.me/+6EFH7b6AJNNjNTQ1"

# Legacy alias (for backward compatibility)
TELEGRAM_CHANNEL_ID = _get_secret("TELEGRAM_PRIVATE_CHANNEL_ID")

ADMIN_TELEGRAM_IDS = [
    int(x.strip()) for x in _get_secret("ADMIN_TELEGRAM_IDS").split(",")
    if x.strip().isdigit()
]

# Subscription pricing (free period currently)
SUBSCRIPTION_PRICE_USD = 99.0
IS_FREE_PERIOD = True

# ── MetaAPI (MT5 Connection) ────────────────────────────────
METAAPI_TOKEN = _get_secret("METAAPI_TOKEN")
METAAPI_ACCOUNT = _get_secret("METAAPI_ACCOUNT")

# ── Supabase ─────────────────────────────────────────────────
SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

# ── Trading Economics (Calendar/News) ───────────────────────
TE_API_KEY = _get_secret("TE_API_KEY")

# ── Twelve Data (Price Feed) ────────────────────────────────
TWELVE_DATA_API_KEY = _get_secret("TWELVE_DATA_API_KEY")

# ── FP Markets Referral ─────────────────────────────────────
FP_MARKETS_LINK = _get_secret(
    "FP_MARKETS_LINK",
    "https://portal.fpmarkets.com/register?fpm-affiliate-utm-source=IB&fpm-affiliate-agt=66209"
)
FP_MARKETS_CODE = _get_secret("FP_MARKETS_CODE", "M4-66209")

# ── Scan Settings ────────────────────────────────────────────
SCAN_INTERVAL = int(_get_secret("SCAN_INTERVAL_SECONDS", "60"))

# ═════════════════════════════════════════════════════════════
# XAUUSD CONFIGURATION
# ═════════════════════════════════════════════════════════════
SYMBOL = "XAUUSD"
SYMBOL_PIP = 0.1          # Gold: 1 pip = $0.10
SYMBOL_DEC = 2             # 2 decimal places
SYMBOL_SUFFIX = ".r"       # Broker suffix (FP Markets)
PIP_VALUE_PER_LOT = 10.0   # USD per pip per standard lot

# ── Session Definitions (UTC) ───────────────────────────────
SESSIONS_UTC = {
    "Asian":   (22, 7),
    "London":  (7, 16),
    "NewYork": (12, 21),
    "Overlap": (12, 16),
}

# ── ICT Killzones (UTC) — HIGH PROBABILITY WINDOWS ─────────
KILLZONES_UTC = {
    "London_Open":    (7, 10),
    "NY_Open":        (12, 15),
    "London_Close":   (15, 17),
    "LN_Overlap":     (12, 16),
    "Asian_KZ":       (0, 3),
}

# ── Gold-Specific TP Levels (in pips) ───────────────────────
# 10-level take profit system tuned for gold volatility
# Using the 15/10 split + trailing approach
TP_LEVELS_PIPS = [20, 20, 20, 20, 30, 40, 50, 50, 60, 60]

# Lot percentage to close at each TP level (15/10 split + runner)
TP_LOT_PCT = [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]

# Trailing SL rules: after which TP, move SL to which TP level
# Format: {tp_number: trail_sl_to_tp_level}
TRAILING_SL_RULES = {
    1: "breakeven",   # TP1 hit → SL to breakeven + 2 pip buffer
    4: 2,             # TP4 hit → SL to TP2 level
    7: 5,             # TP7 hit → SL to TP5 level
}

# ── Scoring Thresholds ──────────────────────────────────────
GRADE_THRESHOLDS = {
    "A+": 90,
    "A":  88,
    "B":  80,
    "C":  45,
    "D":  0,
}

# Signal minimum requirements
SIGNAL_MIN_GRADE_SCALP = "A"    # Scalp requires A or A+
SIGNAL_MIN_GRADE_SWING = "A"    # Swing requires A or A+
SIGNAL_MIN_SCORE_SCALP = 78
SIGNAL_MIN_SCORE_SWING = 80

# ── ATR Multipliers for SL/TP ───────────────────────────────
ATR_SL_MULT = 1.5       # SL = 1.5x ATR
ATR_TP1_MULT = 2.0      # TP1 = 2.0x ATR
ATR_TP2_MULT = 4.5      # TP2 = 4.5x ATR (swing target)

# ── Risk Management ─────────────────────────────────────────
RISK_CONSERVATIVE_PCT = 2.0
RISK_MODERATE_PCT = 3.0
RISK_AGGRESSIVE_PCT = 5.0
MAX_CONCURRENT_TRADES = 3
MAX_DAILY_LOSS_PCT = 6.0   # Hard stop: -6% daily drawdown
MAX_DRAWDOWN_PCT = 20.0    # Hard stop: -20% total drawdown

# ── Gold Engine V4 Module Weights ───────────────────────────
# Maximum bonus each module can contribute
MODULE_WEIGHTS = {
    "mtf_alignment":     15,   # Multi-timeframe trend
    "supply_demand":     12,   # Fresh S/D zone
    "fvg":                8,   # Fair Value Gap
    "choch":             10,   # Change of Character
    "killzone":           8,   # ICT Killzone timing
    "rsi_divergence":     8,   # RSI divergence (regular)
    "rsi_hidden_div":     6,   # RSI hidden divergence
    "liquidity_sweep":   10,   # Liquidity sweep
    "asian_breakout":     8,   # Asian range breakout
    "momentum":          15,   # Momentum filter
    "overextension":    -10,   # Overextension penalty
    "market_structure":   5,   # HH/HL/LH/LL
    "bos":                8,   # Break of Structure
    "order_blocks":      12,   # BOS-validated OBs
    "fib_ote":           15,   # OTE (highest probability)
    "fib_golden":        10,   # Golden Pocket
    "displacement":       7,   # Displacement candles
    "bb_squeeze":         7,   # BB Squeeze + RSI
    "round_numbers":      5,   # Psychological levels
}

# ── Alert Priority Levels ───────────────────────────────────
ALERT_RED = "RED"        # H1 CHoCH — urgent, structure broken
ALERT_YELLOW = "YELLOW"  # M15 CHoCH — early warning
ALERT_GREEN = "GREEN"    # TP hit notifications
ALERT_BLUE = "BLUE"      # FVG entry opportunity
ALERT_WHITE = "WHITE"    # General info

# ── CHoCH Detection Settings ────────────────────────────────
CHOCH_H1_LOOKBACK = 50       # Candles to scan for H1 structure
CHOCH_M15_LOOKBACK = 30      # Candles to scan for M15 structure
CHOCH_CONFIRM_CANDLES = 2    # For aggressive: 1 candle close confirms
FVG_MIN_SIZE_PIPS = 15       # Minimum FVG size worth alerting (gold pips)
FVG_RETEST_ZONE_PCT = 0.618  # Alert when price reaches 61.8% of FVG

# ── Trading Economics Calendar ──────────────────────────────
# Events that directly impact XAUUSD
GOLD_IMPACT_EVENTS = [
    "Interest Rate Decision",
    "Fed Interest Rate Decision",
    "Non Farm Payrolls",
    "CPI", "Core CPI",
    "PPI", "Core PPI",
    "GDP Growth Rate",
    "Unemployment Rate",
    "Initial Jobless Claims",
    "Retail Sales",
    "ISM Manufacturing PMI",
    "ISM Services PMI",
    "FOMC Minutes",
    "Fed Chair Powell Speech",
    "ECB Interest Rate Decision",
    "BOE Interest Rate Decision",
    "BOJ Interest Rate Decision",
    "Gold Reserves",
    "Trade Balance",
    "Consumer Confidence",
    "Durable Goods Orders",
    "PCE Price Index",
    "Core PCE Price Index",
    "Treasury Auction",
    "Crude Oil Inventories",
]

GOLD_IMPACT_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CNY"]
