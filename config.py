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
VERSION = "3.1.0"  # V6 Callisto Optimized — 200-pip SL, A+ Only

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
# MULTI-SYMBOL CONFIGURATION
# ═════════════════════════════════════════════════════════════
SYMBOL = "XAUUSD"          # Primary symbol (gold)
SYMBOL_PIP = 0.1           # Gold: 1 pip = $0.10
SYMBOL_DEC = 2             # 2 decimal places
SYMBOL_SUFFIX = ".r"       # Broker suffix (FP Markets)
PIP_VALUE_PER_LOT = 10.0   # USD per pip per standard lot

# ── All Supported Symbols ───────────────────────────────────
# Each symbol has: twelve_data_code, pip_size, pip_value_per_lot, decimals, sl_pips, tp_multipliers
SYMBOLS = {
    "XAUUSD": {
        "name": "Gold",
        "td_code": "XAU/USD",       # Twelve Data symbol
        "mt5_code": "XAUUSD",       # MetaAPI/MT5 symbol
        "pip": 0.1,                  # 1 pip = $0.10
        "pip_value": 10.0,           # $ per pip per 1.0 lot
        "decimals": 2,
        "sl_pips": 200,              # Optimized SL
        "tp_pips": [200, 400, 600, 800, 1000],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "commodity",
        "sessions": ["London", "NewYork"],
    },
    "EURUSD": {
        "name": "EUR/USD",
        "td_code": "EUR/USD",
        "mt5_code": "EURUSD",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 30,
        "tp_pips": [30, 60, 90, 120, 150],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["London", "NewYork"],
    },
    "GBPUSD": {
        "name": "GBP/USD",
        "td_code": "GBP/USD",
        "mt5_code": "GBPUSD",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 35,
        "tp_pips": [35, 70, 105, 140, 175],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["London", "NewYork"],
    },
    "USDJPY": {
        "name": "USD/JPY",
        "td_code": "USD/JPY",
        "mt5_code": "USDJPY",
        "pip": 0.01,
        "pip_value": 6.67,           # Approx for JPY pairs
        "decimals": 3,
        "sl_pips": 30,
        "tp_pips": [30, 60, 90, 120, 150],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["Asian", "London", "NewYork"],
    },
    "AUDUSD": {
        "name": "AUD/USD",
        "td_code": "AUD/USD",
        "mt5_code": "AUDUSD",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 25,
        "tp_pips": [25, 50, 75, 100, 125],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["Asian", "London", "NewYork"],
    },
    "USDCHF": {
        "name": "USD/CHF",
        "td_code": "USD/CHF",
        "mt5_code": "USDCHF",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 25,
        "tp_pips": [25, 50, 75, 100, 125],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["London", "NewYork"],
    },
    "USDCAD": {
        "name": "USD/CAD",
        "td_code": "USD/CAD",
        "mt5_code": "USDCAD",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 25,
        "tp_pips": [25, 50, 75, 100, 125],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["London", "NewYork"],
    },
    "NZDUSD": {
        "name": "NZD/USD",
        "td_code": "NZD/USD",
        "mt5_code": "NZDUSD",
        "pip": 0.0001,
        "pip_value": 10.0,
        "decimals": 5,
        "sl_pips": 25,
        "tp_pips": [25, 50, 75, 100, 125],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "forex",
        "sessions": ["Asian", "London", "NewYork"],
    },
    "BTCUSD": {
        "name": "Bitcoin",
        "td_code": "BTC/USD",
        "mt5_code": "BTCUSD",
        "pip": 1.0,                  # 1 pip = $1.00 for BTC
        "pip_value": 1.0,            # $ per pip per 1.0 lot
        "decimals": 2,
        "sl_pips": 500,
        "tp_pips": [500, 1000, 1500, 2000, 2500],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "crypto",
        "sessions": ["All"],         # Crypto trades 24/7
    },
    "ETHUSD": {
        "name": "Ethereum",
        "td_code": "ETH/USD",
        "mt5_code": "ETHUSD",
        "pip": 0.1,
        "pip_value": 1.0,
        "decimals": 2,
        "sl_pips": 50,
        "tp_pips": [50, 100, 150, 200, 250],
        "lot_size": 0.01,
        "num_orders": 5,
        "category": "crypto",
        "sessions": ["All"],
    },
}

# Active symbols for scanning (toggle on/off)
ACTIVE_SYMBOLS = list(SYMBOLS.keys())

# ── Grok xAI Configuration ─────────────────────────────────
GROK_API_KEY = _get_secret("GROK_API_KEY")
GROK_MODEL = "grok-3-mini-fast"     # Fast model for real-time decisions
GROK_ANALYSIS_MODEL = "grok-3-mini"  # Deeper analysis model
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

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
# 5-level layered order system — V6 Callisto Optimized
# SL: 200 pips | 5 x 0.01 lot per trade
# Backtested: 51.8% WR, 1.47 PF, +209% on $1,200 (6 months)
# A+ only filter: 51.4% WR, 1.66 PF, 23.8% max DD
TP_LEVELS_PIPS = [200, 200, 200, 200, 200]  # Non-cumulative: TP1=200, TP2=400, TP3=600, TP4=800, TP5=1000

# Lot percentage to close at each TP level (5 equal orders)
TP_LOT_PCT = [0.20, 0.20, 0.20, 0.20, 0.20]

# Layered order settings — V6 Callisto Optimized
LAYERED_LOT_SIZE = 0.01       # Per order lot size
LAYERED_NUM_ORDERS = 5        # 5 orders at same entry
LAYERED_TP_PIPS = [200, 400, 600, 800, 1000]  # Cumulative TP targets

# Trailing SL rules: after which TP, move SL to which TP level
# Format: {tp_number: trail_sl_to_tp_level}
TRAILING_SL_RULES = {
    1: "breakeven",   # TP1 hit → SL to breakeven + 2 pip buffer
    3: 1,             # TP3 hit → SL to TP1 level
    5: 3,             # TP5 hit → SL to TP3 level
}

# ── Scoring Thresholds ──────────────────────────────────────
GRADE_THRESHOLDS = {
    "A+": 72,   # V6.1: Strong multi-confluence setup (8+ modules, killzone active)
    "A":  64,   # V6.1: Good setup but missing 1-2 confluences
    "B":  52,   # V6.1: Marginal — don't trade, wait for better
    "C":  40,
    "D":  0,
}

# Signal minimum requirements
SIGNAL_MIN_GRADE_SCALP = "A+"   # V6 Optimized: A+ only (1.66 PF, 23.8% DD)
SIGNAL_MIN_GRADE_SWING = "A+"   # V6 Optimized: A+ only for max conviction
SIGNAL_MIN_SCORE_SCALP = 80
SIGNAL_MIN_SCORE_SWING = 82

# ── ATR Multipliers for SL/TP ───────────────────────────────
# SL is FIXED at 40 pips (Callisto FX rule). ATR multipliers
# only used for TP scaling when ATR > 40 pips.
ATR_SL_MULT = 1.5       # Legacy (overridden by fixed SL)
ATR_TP1_MULT = 2.0      # TP1 scale factor (legacy)
ATR_TP2_MULT = 4.5      # TP2 scale factor (legacy)
FIXED_SL_PIPS = 200      # V6 Optimized: 200-pip SL (backtested profitable)
FIXED_TP1_MIN_PIPS = 200  # V6 Optimized: TP1 = 200 pips (1:1 floor)

# ── Risk Management (Callisto FX Rules) ────────────────────
RISK_CONSERVATIVE_PCT = 2.0
RISK_MODERATE_PCT = 3.0
RISK_AGGRESSIVE_PCT = 5.0
MAX_CONCURRENT_TRADES = 3
MAX_DAILY_LOSS_PCT = 6.0   # Hard stop: -6% daily drawdown
MAX_DRAWDOWN_PCT = 20.0    # Hard stop: -20% total drawdown
MAX_DAILY_LOSSES = 2        # Callisto FX: Max 2 losses/day — NO MORE TRADING
SL_TO_BE_PIPS = 15          # Callisto: SL to breakeven at 10-20 pips profit (mid=15)
PARTIAL_CLOSE_PCT_1 = 0.25  # Callisto: 20-25% partials initially
PARTIAL_CLOSE_PCT_2 = 0.25  # Callisto: Another 25% at key HTF levels
MIN_RR_RATIO = 2.0           # Callisto BB Strategy: Strict 1:2 R:R minimum

# ── Gold Engine V6 Callisto Module Weights ──────────────────
# Maximum bonus each module can contribute
MODULE_WEIGHTS = {
    # Technical Modules (1-17)
    "mtf_alignment":     18,   # Multi-timeframe trend (upgraded: 4-TF 2/3 rule)
    "supply_demand":     12,   # Fresh S/D zone
    "fvg":                8,   # Fair Value Gap
    "choch":             10,   # Change of Character (body-close enforced)
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
    # Institutional Modules (18-20)
    "cot_dxy":           12,   # COT positioning + DXY correlation
    "news_filter":       -15,  # News event danger (mostly penalty)
    "volume":            10,   # Volume confirmation
    # Callisto FX Modules (21-26)
    "trc":               20,   # TRC Framework (HIGHEST WEIGHT — core system)
    "wcr_range":         12,   # William-Certified Range
    "breaker_block":     12,   # Breaker Block + SMA44
    "premium_discount":  10,   # ICT Premium/Discount Array
    "candlestick":        8,   # Expanded candlestick patterns
    "risk_enforcer":    -20,   # Risk enforcer (mostly penalty/blocker)
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
