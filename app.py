"""
Alpha FX Hub — Main Application
XAUUSD Gold Trading Platform

Pages:
  1. Landing / Home
  2. Signal Dashboard (with annotated charts)
  3. Trading Academy (lessons + signal manual)
  4. Economic Calendar (gold impact analysis)
  5. Risk Calculator & Position Sizer
  6. Live Trade Tracker (10-TP system)
  7. Performance Scoreboard
  8. Market Regime Indicator
"""
import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    PLATFORM_NAME, VERSION, SYMBOL, SYMBOL_PIP,
    TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_IDS,
    TELEGRAM_PUBLIC_CHANNEL_ID, TELEGRAM_PRIVATE_CHANNEL_ID,
    TELEGRAM_PUBLIC_CHANNEL_LINK, TELEGRAM_PRIVATE_CHANNEL_LINK,
    FP_MARKETS_LINK, FP_MARKETS_CODE,
    TE_API_KEY, TWELVE_DATA_API_KEY,
    SUPABASE_URL, SUPABASE_KEY,
    KILLZONES_UTC, TP_LEVELS_PIPS, TP_LOT_PCT,
    GRADE_THRESHOLDS, MODULE_WEIGHTS,
    RISK_CONSERVATIVE_PCT, RISK_MODERATE_PCT, RISK_AGGRESSIVE_PCT,
    MAX_DAILY_LOSS_PCT, MAX_DRAWDOWN_PCT,
    GOLD_IMPACT_EVENTS,
)
# Legacy alias
TELEGRAM_CHANNEL_ID = TELEGRAM_PRIVATE_CHANNEL_ID
from engine.indicators import add_indicators, detect_fvg_candles, find_swing_points
from engine.gold_engine import gold_engine_score, detect_choch_realtime, detect_fvg_entry
from engine.levels import compute_levels, compute_10tp_levels, compute_lot_tiers, compute_trailing_sl
from engine.data import fetch_bars, fetch_price, fetch_metaapi_price, get_metaapi_account_info
from engine.signal_scanner import SignalScanner, Signal
from trading.trade_manager import TradeManager, Trade, STRATEGIES
from trading.risk_manager import RiskManager
from academy.lessons import ACADEMY_LESSONS, SIGNAL_MANUAL
from academy.lessons_zh import SIGNAL_MANUAL_ZH, ACADEMY_LESSONS_ZH
from academy.calendar import fetch_economic_calendar, get_gold_impact_events, is_high_impact_soon
from engine.backtester import run_backtest
# NOTE: TelegramBot polling runs on Railway (bot_runner.py) — NOT here
# Only import NotificationManager for sending signals to channels
from telegram.notifications import NotificationManager
from auth.supabase_auth import SupabaseAuth, render_auth_page
from trading.cloud_sync import CloudTradeSync
from engine.adaptive_learner import AdaptiveLearner

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

# ── Logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("alpha_fx_hub")

# ── Page Config ──
st.set_page_config(
    page_title=PLATFORM_NAME,
    page_icon="\u25c8",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

    .main .block-container { padding-top: 1rem; max-width: 1400px; }

    .gold-header {
        background: linear-gradient(135deg, #0a0e17 0%, #0d1b2a 50%, #0f2847 100%);
        border: 1px solid rgba(0,212,255,0.25);
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 20px;
    }
    .gold-header h1 {
        font-family: 'Space Mono', monospace;
        background: linear-gradient(135deg, #c0c0c0, #00d4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 28px;
        margin: 0;
    }
    .gold-header .subtitle {
        color: #7dd3fc;
        font-size: 14px;
        margin-top: 4px;
    }

    .metric-card {
        background: #111827;
        border: 1px solid rgba(0,212,255,0.15);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-card .label { color: #9ca3af; font-size: 12px; text-transform: uppercase; }
    .metric-card .value { color: #00d4ff; font-size: 24px; font-weight: 700; font-family: 'Space Mono', monospace; }

    .signal-card {
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
    }
    .signal-buy {
        background: linear-gradient(135deg, #064e3b, #065f46);
        border: 1px solid #10b981;
    }
    .signal-sell {
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        border: 1px solid #ef4444;
    }

    .grade-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-family: 'Space Mono', monospace;
    }
    .grade-aplus { background: linear-gradient(135deg, #00d4ff, #0ea5e9); color: #000; }
    .grade-a { background: #10b981; color: #000; }
    .grade-b { background: #3b82f6; color: #fff; }
    .grade-c { background: #6b7280; color: #fff; }

    .alert-red {
        background: rgba(239,68,68,0.15);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 12px;
    }
    .alert-yellow {
        background: rgba(0,212,255,0.1);
        border: 1px solid #00d4ff;
        border-radius: 8px;
        padding: 12px;
    }
    .alert-green {
        background: rgba(16,185,129,0.15);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 12px;
    }
    .alert-blue {
        background: rgba(59,130,246,0.15);
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 12px;
    }

    .lesson-card {
        background: #111827;
        border: 1px solid rgba(245,166,35,0.15);
        border-radius: 10px;
        padding: 20px;
        margin: 8px 0;
        cursor: pointer;
    }
    .lesson-card:hover { border-color: #F5A623; }

    .tp-bar { height: 20px; border-radius: 4px; display: inline-block; }
    .tp-hit { background: #10b981; }
    .tp-pending { background: #374151; }

    div[data-testid="stSidebar"] {
        background: #0a0e17;
        border-right: 1px solid rgba(0,212,255,0.1);
    }
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═════════════════════════════════════════════════════════════
def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "scanner" not in st.session_state:
        st.session_state.scanner = SignalScanner(balance=10000, api_key=TWELVE_DATA_API_KEY)

    # ── Cloud Sync (trade history to Supabase) ──
    if "cloud_sync" not in st.session_state:
        if SUPABASE_URL and SUPABASE_KEY:
            st.session_state.cloud_sync = CloudTradeSync(SUPABASE_URL, SUPABASE_KEY)
        else:
            st.session_state.cloud_sync = None

    if "trade_manager" not in st.session_state:
        st.session_state.trade_manager = TradeManager(
            strategy="split_15_10",
            data_dir=os.path.join(os.path.dirname(__file__), "data"),
            cloud_sync=st.session_state.cloud_sync,
        )

    # ── Adaptive Learner ──
    if "adaptive_learner" not in st.session_state:
        st.session_state.adaptive_learner = AdaptiveLearner(
            data_dir=os.path.join(os.path.dirname(__file__), "data")
        )

    if "risk_manager" not in st.session_state:
        st.session_state.risk_manager = RiskManager(initial_balance=10000)
    if "signals_history" not in st.session_state:
        st.session_state.signals_history = []
    if "tp_strategy" not in st.session_state:
        st.session_state.tp_strategy = "split_15_10"
    if "balance" not in st.session_state:
        st.session_state.balance = 10000.0

    # ── Notification Manager (for sending signals to channels) ──
    # NOTE: Telegram bot polling runs separately via bot_runner.py on Railway
    if "notifier" not in st.session_state:
        st.session_state.notifier = NotificationManager(
            bot_token=TELEGRAM_BOT_TOKEN,
            private_channel_id=TELEGRAM_PRIVATE_CHANNEL_ID,
            public_channel_id=TELEGRAM_PUBLIC_CHANNEL_ID,
        )
    st.session_state.telegram_bot = None

init_state()

# ═════════════════════════════════════════════════════════════
# AUTHENTICATION GATE
# ═════════════════════════════════════════════════════════════
_auth_client = None
if SUPABASE_URL and SUPABASE_KEY:
    _auth_client = SupabaseAuth(SUPABASE_URL, SUPABASE_KEY)
    if not render_auth_page(_auth_client):
        st.stop()  # Not authenticated — stop here, don't render the app

    # Wire up cloud sync with authenticated user
    if st.session_state.get("cloud_sync") and st.session_state.get("user"):
        user_id = st.session_state.user.get("id", "")
        access_token = st.session_state.get("access_token", "")
        if user_id:
            st.session_state.cloud_sync.set_user(user_id, access_token)


# ═════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ═════════════════════════════════════════════════════════════
with st.sidebar:
    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.markdown(f"""
        <div style="text-align:center; padding: 16px 0;">
            <div style="font-family:'Space Mono',monospace; color:#00d4ff; font-size:22px; font-weight:700;">
                {PLATFORM_NAME}
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown(f"""<div style="text-align:center; color:#6b7280; font-size:11px; margin-top:-8px;">
        XAUUSD Gold Trading Platform v{VERSION}
    </div>""", unsafe_allow_html=True)

    st.divider()

    pages = {
        "home": ("\U0001f3e0", "Home"),
        "dashboard": ("\U0001f4ca", "Signal Dashboard"),
        "academy": ("\U0001f393", "Trading Academy"),
        "manual": ("\U0001f4d6", "Signal Manual"),
        "calendar": ("\U0001f4c5", "Economic Calendar"),
        "risk_calc": ("\U0001f9ee", "Risk Calculator"),
        "tracker": ("\U0001f4cc", "Live Trade Tracker"),
        "scoreboard": ("\U0001f3c6", "Performance Scoreboard"),
        "regime": ("\U0001f30d", "Market Regime"),
        "assistant": ("\U0001f916", "Decision Assistant"),
        "backtest": ("\U0001f52c", "Backtest Engine"),
        "ai_insights": ("\U0001f9e0", "AI Learning"),
    }

    for key, (icon, label) in pages.items():
        is_active = st.session_state.page == key
        if st.button(
            f"{icon}  {label}",
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.page = key
            st.rerun()

    st.divider()

    # TP Strategy selector
    st.markdown("**TP/SL Strategy**")
    strategy = st.selectbox(
        "Choose strategy",
        options=list(STRATEGIES.keys()),
        format_func=lambda x: STRATEGIES[x]["name"],
        index=list(STRATEGIES.keys()).index(st.session_state.tp_strategy),
        key="strategy_select",
        label_visibility="collapsed",
    )
    if strategy != st.session_state.tp_strategy:
        st.session_state.tp_strategy = strategy
        st.session_state.trade_manager.set_strategy(strategy)
    st.caption(STRATEGIES[strategy]["description"])

    st.divider()
    # Balance input
    balance = st.number_input("Account Balance ($)", value=st.session_state.balance,
                              min_value=100.0, step=100.0, key="bal_input")
    if balance != st.session_state.balance:
        st.session_state.balance = balance
        st.session_state.scanner.balance = balance
        st.session_state.risk_manager.current_balance = balance

    # ── User Info & Logout ──
    if st.session_state.get("user"):
        st.divider()
        user = st.session_state.user
        user_email = user.get("email", "User")
        st.markdown(f"""<div style="color:#9ca3af; font-size:12px;">
            Logged in as:<br><strong style="color:#7dd3fc;">{user_email}</strong>
        </div>""", unsafe_allow_html=True)
        if st.button("Logout", key="logout_btn", use_container_width=True):
            if _auth_client:
                _auth_client.sign_out(st.session_state.get("access_token", ""))
            for k in ["access_token", "refresh_token", "user"]:
                st.session_state.pop(k, None)
            st.rerun()


# ═════════════════════════════════════════════════════════════
# CHART BUILDER WITH ANNOTATIONS
# ═════════════════════════════════════════════════════════════
def build_annotated_chart(df: pd.DataFrame, engine_result: dict = None,
                         levels: dict = None, title: str = "XAUUSD") -> go.Figure:
    """Build a Plotly candlestick chart with signal annotations."""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=[title, "RSI (14)", "MACD"],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="XAUUSD",
        increasing_line_color="#10b981", decreasing_line_color="#ef4444",
    ), row=1, col=1)

    # EMAs
    if "ema20" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], name="EMA20",
                                line=dict(color="#00d4ff", width=1)), row=1, col=1)
    if "ema50" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA50",
                                line=dict(color="#3b82f6", width=1)), row=1, col=1)
    if "ema200" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["ema200"], name="EMA200",
                                line=dict(color="#ef4444", width=1, dash="dot")), row=1, col=1)

    # RSI
    if "rsi14" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi14"], name="RSI",
                                line=dict(color="#00d4ff", width=1.5)), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(239,68,68,0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(16,185,129,0.5)", row=2, col=1)

    # MACD
    if "macd" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD",
                                line=dict(color="#3b82f6", width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal",
                                line=dict(color="#00d4ff", width=1)), row=3, col=1)
        colors = ["#10b981" if v >= 0 else "#ef4444" for v in df["macd_hist"]]
        fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Histogram",
                            marker_color=colors), row=3, col=1)

    # ── SIGNAL ANNOTATIONS ──
    if engine_result and levels and levels.get("valid"):
        price = levels["entry"]
        sl = levels["sl"]
        direction = engine_result["direction"]
        modules = engine_result.get("modules", {})

        # Entry line
        fig.add_hline(y=price, line_dash="solid", line_color="#00d4ff",
                     annotation_text=f"ENTRY ${price:.2f}", row=1, col=1)

        # SL line
        fig.add_hline(y=sl, line_dash="dash", line_color="#ef4444",
                     annotation_text=f"SL ${sl:.2f}", row=1, col=1)

        # TP lines (first 3 for clarity)
        tp_levels = compute_10tp_levels(price, sl, direction)
        tp_colors = ["#10b981", "#22d3ee", "#818cf8"]
        for i, tp in enumerate(tp_levels[:3]):
            fig.add_hline(y=tp, line_dash="dot",
                         line_color=tp_colors[i % len(tp_colors)],
                         annotation_text=f"TP{i+1} ${tp:.2f}", row=1, col=1)

        # S/D Zone annotation
        sd = modules.get("supply_demand", {})
        zone = sd.get("zone")
        if zone:
            color = "rgba(16,185,129,0.15)" if zone["type"] == "demand" else "rgba(239,68,68,0.15)"
            border = "#10b981" if zone["type"] == "demand" else "#ef4444"
            fig.add_hrect(y0=zone["bottom"], y1=zone["top"],
                         fillcolor=color, line=dict(color=border, width=1),
                         annotation_text=f"{'Demand' if zone['type'] == 'demand' else 'Supply'} Zone "
                                        f"({'Fresh' if zone.get('fresh') else str(zone.get('visits', 0)) + ' visits'})",
                         row=1, col=1)

        # FVG annotation
        fvg_data = modules.get("fvg", {})
        fvg = fvg_data.get("fvg")
        if fvg:
            fvg_color = "rgba(59,130,246,0.15)"
            fig.add_hrect(y0=fvg["bottom"], y1=fvg["top"],
                         fillcolor=fvg_color,
                         line=dict(color="#3b82f6", width=1, dash="dot"),
                         annotation_text="Fair Value Gap",
                         row=1, col=1)

        # Order Block annotation
        ob_data = modules.get("order_blocks", {})
        ob = ob_data.get("ob")
        if ob:
            ob_color = "rgba(168,85,247,0.15)"
            fig.add_hrect(y0=ob["bottom"], y1=ob["top"],
                         fillcolor=ob_color,
                         line=dict(color="#a855f7", width=1),
                         annotation_text=f"Order Block ({'BOS' if ob_data.get('score', 0) >= 12 else 'Std'})",
                         row=1, col=1)

        # Add text annotation with signal reasoning
        reasons = []
        if sd.get("score", 0) > 0:
            reasons.append(f"S/D Zone (+{sd['score']})")
        if fvg_data.get("score", 0) > 0:
            reasons.append(f"FVG (+{fvg_data['score']})")
        choch = modules.get("choch", {})
        if choch.get("score", 0) > 0:
            reasons.append(f"CHoCH (+{choch['score']})")
        bos = modules.get("bos", {})
        if bos.get("bos"):
            reasons.append(f"BOS (+{bos['score']})")
        fib = modules.get("fibonacci", {})
        if fib.get("ote"):
            reasons.append("OTE (+15)")
        elif fib.get("golden_pocket"):
            reasons.append("Golden Pocket (+10)")
        liq = modules.get("liquidity_sweep", {})
        if liq.get("detected"):
            reasons.append(f"Liq Sweep (+{liq['score']})")

        if reasons:
            reason_text = " | ".join(reasons)
            fig.add_annotation(
                x=df.index[-1], y=price,
                text=f"<b>WHY:</b> {reason_text}",
                showarrow=True, arrowhead=2,
                font=dict(size=11, color="#00d4ff"),
                bgcolor="rgba(0,0,0,0.8)",
                bordercolor="#00d4ff",
                row=1, col=1,
            )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0e17",
        plot_bgcolor="#0a0e17",
        font=dict(family="Inter, sans-serif", color="#e5e7eb"),
        height=650,
        showlegend=True,
        legend=dict(orientation="h", y=1.02),
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=40, b=30),
    )

    return fig


# ═════════════════════════════════════════════════════════════
# PAGE: HOME / LANDING
# ═════════════════════════════════════════════════════════════
def page_home():
    # Auto-refresh home page every 60 seconds for live price
    if st_autorefresh:
        st_autorefresh(interval=15000, limit=None, key="home_refresh")

    # Hero with logo
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    col_l, col_logo, col_r = st.columns([1, 2, 1])
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
    st.markdown("""
    <div class="gold-header" style="text-align:center;">
        <div class="subtitle" style="font-size:16px;">Professional XAUUSD Gold Trading Platform | 20-Module Institutional Signal Engine</div>
    </div>
    """, unsafe_allow_html=True)

    # Live overview
    overview = st.session_state.scanner.get_market_overview()

    # Try MetaAPI live price first
    mt5_price = fetch_metaapi_price()
    price_source = "MT5 LIVE" if mt5_price else "DELAYED"
    display_price = mt5_price if mt5_price else overview.get('price', 0)
    source_color = "#10b981" if mt5_price else "#f59e0b"

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Gold Price <span style="color:{source_color}; font-size:9px;">● {price_source}</span></div>
            <div class="value">${display_price:,.2f}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        bias = overview.get("bias", "NEUTRAL")
        bias_color = "#10b981" if bias == "BULLISH" else "#ef4444" if bias == "BEARISH" else "#6b7280"
        st.markdown(f"""<div class="metric-card">
            <div class="label">Market Bias</div>
            <div class="value" style="color:{bias_color}">{bias}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="label">ATR (14)</div>
            <div class="value">${overview.get('atr', 0):.2f}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        rsi = overview.get("rsi", 50)
        rsi_color = "#ef4444" if rsi > 70 else "#10b981" if rsi < 30 else "#F5A623"
        st.markdown(f"""<div class="metric-card">
            <div class="label">RSI</div>
            <div class="value" style="color:{rsi_color}">{rsi:.1f}</div>
        </div>""", unsafe_allow_html=True)
    with col5:
        kz = overview.get("killzone", "Off-hours")
        st.markdown(f"""<div class="metric-card">
            <div class="label">Session</div>
            <div class="value" style="font-size:16px">{kz}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Feature grid
    col1, col2, col3 = st.columns(3)
    features = [
        ("\U0001f4ca", "Signal Dashboard", "Real-time XAUUSD signals with 17-module AI scoring, annotated charts showing WHY every signal fires."),
        ("\U0001f393", "Trading Academy", "From beginner to advanced — learn trends, S/D zones, FVGs, CHoCH, and how to read our signals."),
        ("\U0001f4c5", "Economic Calendar", "Gold-impact events from Trading Economics. Know when Fed, NFP, CPI will move gold."),
        ("\U0001f9ee", "Risk Calculator", "Position sizing for 3 risk tiers. Never risk more than you should."),
        ("\U0001f4cc", "Live Trade Tracker", "10-TP partial close system with real-time P&L tracking."),
        ("\U0001f3c6", "Performance Scoreboard", "Win rate, profit factor, drawdown — see how the signals perform."),
    ]
    for i, (icon, title, desc) in enumerate(features):
        with [col1, col2, col3][i % 3]:
            st.markdown(f"""<div class="metric-card" style="text-align:left; min-height:140px;">
                <div style="font-size:28px; margin-bottom:8px;">{icon}</div>
                <div style="color:#00d4ff; font-weight:600; margin-bottom:4px;">{title}</div>
                <div style="color:#9ca3af; font-size:13px;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Telegram CTA
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0a0e17,#0d1b2a); border:1px solid rgba(0,212,255,0.3);
                border-radius:12px; padding:24px; text-align:center; margin:20px 0;">
        <div style="font-size:20px; color:#00d4ff; font-weight:700; margin-bottom:8px;">
            Get Signals on Telegram
        </div>
        <div style="color:#9ca3af; margin-bottom:16px;">
            Register under our FP Markets referral to receive real-time XAUUSD signals,
            CHoCH alerts, TP notifications, and FVG entry opportunities directly on Telegram.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE: SIGNAL DASHBOARD
# ═════════════════════════════════════════════════════════════
def page_dashboard():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f4ca Signal Dashboard</h1>
        <div class="subtitle">XAUUSD Gold Signals | 20-Module Institutional Engine | Annotated Charts</div>
    </div>""", unsafe_allow_html=True)

    if st_autorefresh:
        st_autorefresh(interval=15000, limit=None, key="dash_refresh")

    # Fetch data
    df_m15 = fetch_bars("XAU/USD", "15min", 200, TWELVE_DATA_API_KEY)
    df_h1 = fetch_bars("XAU/USD", "1h", 200, TWELVE_DATA_API_KEY)
    df_h4 = fetch_bars("XAU/USD", "4h", 200, TWELVE_DATA_API_KEY)

    if df_m15 is not None:
        df_m15 = add_indicators(df_m15)
    if df_h1 is not None:
        df_h1 = add_indicators(df_h1)
    if df_h4 is not None:
        df_h4 = add_indicators(df_h4)

    # Scan both directions
    buy_result = gold_engine_score(df_m15, df_h1, df_h4, "BUY") if df_m15 is not None else None
    sell_result = gold_engine_score(df_m15, df_h1, df_h4, "SELL") if df_m15 is not None else None

    # Display scores
    col1, col2 = st.columns(2)
    if buy_result:
        with col1:
            grade_class = f"grade-{'aplus' if buy_result['grade'] == 'A+' else buy_result['grade'].lower()}"
            st.markdown(f"""<div class="signal-card signal-buy">
                <div style="font-size:18px; font-weight:700; color:#10b981;">
                    \U0001f7e2 BUY Signal
                    <span class="grade-badge {grade_class}">{buy_result['grade']}</span>
                </div>
                <div style="color:#d1d5db; margin-top:8px;">
                    Score: <b>{buy_result['score']}/100</b> |
                    Confidence: <b>{buy_result['confidence']}</b> |
                    Confirmations: {buy_result['confirmations']}
                </div>
            </div>""", unsafe_allow_html=True)

    if sell_result:
        with col2:
            grade_class = f"grade-{'aplus' if sell_result['grade'] == 'A+' else sell_result['grade'].lower()}"
            st.markdown(f"""<div class="signal-card signal-sell">
                <div style="font-size:18px; font-weight:700; color:#ef4444;">
                    \U0001f534 SELL Signal
                    <span class="grade-badge {grade_class}">{sell_result['grade']}</span>
                </div>
                <div style="color:#d1d5db; margin-top:8px;">
                    Score: <b>{sell_result['score']}/100</b> |
                    Confidence: <b>{sell_result['confidence']}</b> |
                    Confirmations: {sell_result['confirmations']}
                </div>
            </div>""", unsafe_allow_html=True)

    # Determine best signal
    best = None
    if buy_result and sell_result:
        best = buy_result if buy_result["score"] >= sell_result["score"] else sell_result
    elif buy_result:
        best = buy_result
    elif sell_result:
        best = sell_result

    # Chart with annotations
    if df_m15 is not None and best:
        levels = compute_levels(df_m15, best["direction"])
        fig = build_annotated_chart(df_m15, best, levels,
                                   title=f"XAUUSD M15 | {best['direction']} {best['grade']} ({best['score']}/100)")
        st.plotly_chart(fig, use_container_width=True)

    # Module breakdown
    if best:
        st.markdown("### Module Breakdown")
        modules = best.get("modules", {})
        module_names = {
            "mtf_alignment": "Multi-TF Alignment",
            "supply_demand": "Supply & Demand",
            "fvg": "Fair Value Gap",
            "choch": "Change of Character",
            "killzone": "ICT Killzone",
            "rsi_divergence": "RSI Divergence",
            "liquidity_sweep": "Liquidity Sweep",
            "asian_breakout": "Asian Breakout",
            "momentum": "Momentum",
            "overextension": "Overextension Guard",
            "market_structure": "Market Structure",
            "bos": "Break of Structure",
            "order_blocks": "Order Blocks",
            "fibonacci": "Fibonacci/OTE",
            "displacement": "Displacement",
            "bb_squeeze": "BB Squeeze",
            "round_numbers": "Round Numbers",
        }

        cols = st.columns(4)
        for i, (key, label) in enumerate(module_names.items()):
            mod = modules.get(key, {})
            score = mod.get("score", 0)
            color = "#10b981" if score > 0 else "#ef4444" if score < 0 else "#6b7280"
            with cols[i % 4]:
                st.markdown(f"""<div style="background:#111827; border-radius:8px; padding:10px; margin:4px 0;
                                border-left:3px solid {color};">
                    <div style="color:#9ca3af; font-size:11px;">{label}</div>
                    <div style="color:{color}; font-size:18px; font-weight:700;">{'+' if score > 0 else ''}{score}</div>
                </div>""", unsafe_allow_html=True)

    # FVG Opportunities
    if df_m15 is not None and df_h1 is not None:
        fvg_entries = detect_fvg_entry(df_m15, df_h1)
        if fvg_entries:
            st.markdown("### FVG Second-Wave Entry Opportunities")
            for opp in fvg_entries:
                st.markdown(f"""<div class="alert-blue">
                    <b>\U0001f535 {opp['direction']} Entry Opportunity</b><br>
                    {opp['message']}
                </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE: TRADING ACADEMY
# ═════════════════════════════════════════════════════════════
def page_academy():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f393 Trading Academy</h1>
        <div class="subtitle">Learn gold trading from beginner to advanced</div>
    </div>""", unsafe_allow_html=True)

    level = st.selectbox("Choose your level",
                        ["beginner", "intermediate", "advanced"],
                        format_func=lambda x: x.title())

    lessons = ACADEMY_LESSONS.get(level, [])

    for lesson in lessons:
        with st.expander(f"{lesson['title']}  |  {lesson.get('duration', '')}  |  {lesson.get('level', '')}",
                        expanded=False):
            st.markdown(lesson["content"])

            # Video embed if available
            video_url = lesson.get("video_url")
            if video_url:
                st.markdown("**Video Lesson:**")
                st.video(video_url)

            # Interactive chart placeholder
            chart_type = lesson.get("interactive_chart")
            if chart_type:
                st.markdown("**Interactive Chart Example:**")
                _render_lesson_chart(chart_type)


def _render_lesson_chart(chart_type: str):
    """Render an interactive educational chart."""
    df = fetch_bars("XAU/USD", "1h", 100, TWELVE_DATA_API_KEY)
    if df is None:
        st.info("Chart data unavailable in demo mode")
        return

    df = add_indicators(df)
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="XAUUSD",
        increasing_line_color="#10b981", decreasing_line_color="#ef4444",
    ))

    if chart_type == "trend_analysis":
        if "ema20" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], name="EMA20 (Fast)",
                                    line=dict(color="#00d4ff", width=2)))
            fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA50 (Medium)",
                                    line=dict(color="#3b82f6", width=2)))

        # Mark HH/HL or LH/LL
        highs, lows = find_swing_points(df, left=3, right=3)
        for h in highs[-5:]:
            fig.add_annotation(x=df.index[h["index"]], y=h["price"],
                             text="SH", showarrow=True, arrowhead=2,
                             font=dict(color="#ef4444", size=10))
        for l in lows[-5:]:
            fig.add_annotation(x=df.index[l["index"]], y=l["price"],
                             text="SL", showarrow=True, arrowhead=2, ay=20,
                             font=dict(color="#10b981", size=10))

    elif chart_type == "supply_demand":
        from engine.gold_engine import _detect_sd_zones
        zones = _detect_sd_zones(df)
        for zone in zones[-6:]:
            color = "rgba(16,185,129,0.2)" if zone["type"] == "demand" else "rgba(239,68,68,0.2)"
            border = "#10b981" if zone["type"] == "demand" else "#ef4444"
            label = f"{'Demand' if zone['type'] == 'demand' else 'Supply'} ({'Fresh' if zone['fresh'] else 'Tested'})"
            fig.add_hrect(y0=zone["bottom"], y1=zone["top"],
                         fillcolor=color, line=dict(color=border, width=1),
                         annotation_text=label)

    elif chart_type == "fvg":
        fvgs = detect_fvg_candles(df, min_size=0.5)
        for fvg in fvgs[-5:]:
            color = "rgba(59,130,246,0.2)"
            fig.add_hrect(y0=fvg["bottom"], y1=fvg["top"],
                         fillcolor=color,
                         line=dict(color="#3b82f6", width=1, dash="dot"),
                         annotation_text=f"{'Bullish' if fvg['type'] == 'bullish' else 'Bearish'} FVG")

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
        height=450, xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=30, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════
# PAGE: SIGNAL MANUAL
# ═════════════════════════════════════════════════════════════
def page_manual():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f4d6 Signal Manual</h1>
        <div class="subtitle">How to read, understand, and trade our signals</div>
    </div>""", unsafe_allow_html=True)

    lang = st.radio("Language / 语言", ["English", "中文"], horizontal=True, key="manual_lang")
    manual = SIGNAL_MANUAL if lang == "English" else SIGNAL_MANUAL_ZH

    for section in manual["sections"]:
        with st.expander(section["title"], expanded=(section["id"] == "intro")):
            st.markdown(section["content"])


# ═════════════════════════════════════════════════════════════
# PAGE: ECONOMIC CALENDAR
# ═════════════════════════════════════════════════════════════
def page_calendar():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f4c5 Economic Calendar</h1>
        <div class="subtitle">Events that move gold | Trading Economics API</div>
    </div>""", unsafe_allow_html=True)

    events = fetch_economic_calendar(TE_API_KEY)
    gold_events = get_gold_impact_events(events)

    # High impact warning
    warning = is_high_impact_soon(events)
    if warning.get("warning"):
        st.markdown(f"""<div class="alert-red">
            <b>\u26a0\ufe0f HIGH IMPACT EVENT IN {warning['hours_until']:.1f} HOURS</b><br>
            <b>{warning['event']}</b><br>
            {warning['impact'].get('typical_impact', '')}<br>
            <i>{warning['impact'].get('volatility', '')}</i><br><br>
            <b>Recommendation:</b> {warning['recommendation']}
        </div>""", unsafe_allow_html=True)
        st.markdown("")

    # Events table
    if gold_events:
        for event in gold_events:
            importance = event.get("importance", 0)
            if importance >= 3:
                border_color = "#ef4444"
                badge = "\U0001f534 HIGH"
            elif importance >= 2:
                border_color = "#F5A623"
                badge = "\U0001f7e1 MEDIUM"
            else:
                border_color = "#6b7280"
                badge = "\u26aa LOW"

            impact = event.get("gold_impact", {})

            st.markdown(f"""<div style="background:#111827; border-left:4px solid {border_color};
                            border-radius:8px; padding:14px; margin:8px 0;">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <b style="color:#e5e7eb;">{event['event']}</b>
                        <span style="color:#6b7280; font-size:12px; margin-left:8px;">{event['country']}</span>
                    </div>
                    <div style="font-size:12px;">{badge}</div>
                </div>
                <div style="color:#9ca3af; font-size:12px; margin-top:6px;">
                    Time: {event.get('time', 'TBD')} |
                    Forecast: {event.get('forecast', 'N/A')} |
                    Previous: {event.get('previous', 'N/A')}
                </div>
                <div style="color:#00d4ff; font-size:12px; margin-top:4px;">
                    <b>Gold Impact:</b> {impact.get('typical_impact', 'N/A')}
                </div>
                <div style="color:#6b7280; font-size:11px; margin-top:2px;">
                    {impact.get('explanation', '')} | {impact.get('volatility', '')}
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No gold-impacting events found for the next 7 days.")


# ═════════════════════════════════════════════════════════════
# PAGE: RISK CALCULATOR
# ═════════════════════════════════════════════════════════════
def page_risk_calc():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f9ee Risk Calculator</h1>
        <div class="subtitle">Position sizing for XAUUSD | Never risk more than you should</div>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        balance = st.number_input("Account Balance ($)", value=st.session_state.balance,
                                  min_value=100.0, step=100.0)
        sl_pips = st.number_input("Stop Loss (pips)", value=100.0, min_value=1.0, step=10.0,
                                  help="For gold: 1 pip = $0.10. 100 pips = $10.00 move")
        entry_price = st.number_input("Entry Price ($)", value=3100.0, step=0.10)

    with col2:
        direction = st.selectbox("Direction", ["BUY", "SELL"])
        risk_pct = st.slider("Custom Risk %", min_value=0.5, max_value=10.0, value=2.0, step=0.5)

    # Calculate
    rm = st.session_state.risk_manager
    rm.current_balance = balance
    tiers = rm.calculate_all_tiers(sl_pips)

    st.markdown("### Position Size by Risk Tier")
    col1, col2, col3 = st.columns(3)

    for i, (tier_name, tier_data) in enumerate(tiers.items()):
        with [col1, col2, col3][i]:
            color = "#10b981" if tier_name == "conservative" else "#F5A623" if tier_name == "moderate" else "#ef4444"
            st.markdown(f"""<div class="metric-card" style="border-color:{color}">
                <div class="label">{tier_name.title()} ({tier_data['risk_pct']}%)</div>
                <div class="value">{tier_data['lot']} lot</div>
                <div style="color:#9ca3af; font-size:12px;">Risk: ${tier_data['risk_usd']:.2f}</div>
            </div>""", unsafe_allow_html=True)

    # Custom calculation
    custom_lot = rm.calculate_lot(risk_pct, sl_pips)
    custom_risk = balance * (risk_pct / 100)
    st.markdown(f"""
    ### Custom: {risk_pct}% Risk
    **Lot Size:** {custom_lot} | **Risk Amount:** ${custom_risk:.2f} | **SL Distance:** {sl_pips} pips (${sl_pips * 0.1:.2f})
    """)

    # 10 TP levels preview
    st.markdown("### 10 TP Level Preview")
    if direction == "BUY":
        sl_price = entry_price - sl_pips * SYMBOL_PIP
    else:
        sl_price = entry_price + sl_pips * SYMBOL_PIP

    tp_levels = compute_10tp_levels(entry_price, sl_price, direction)
    lot_pcts = STRATEGIES[st.session_state.tp_strategy]["lot_pct"]

    tp_data = []
    for i, tp in enumerate(tp_levels):
        tp_data.append({
            "TP": f"TP{i+1}",
            "Price": f"${tp:.2f}",
            "Close %": f"{lot_pcts[i]*100:.0f}%",
            "Close Lot": f"{custom_lot * lot_pcts[i]:.2f}",
            "Pips from Entry": f"{abs(tp - entry_price)/SYMBOL_PIP:.0f}",
        })

    st.dataframe(pd.DataFrame(tp_data), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════
# PAGE: LIVE TRADE TRACKER
# ═════════════════════════════════════════════════════════════
def page_tracker():
    if st_autorefresh:
        st_autorefresh(interval=15000, limit=None, key="tracker_refresh")

    st.markdown("""<div class="gold-header">
        <h1>\U0001f4cc Live Trade Tracker</h1>
        <div class="subtitle">10-TP partial close system | {strategy}</div>
    </div>""".format(strategy=STRATEGIES[st.session_state.tp_strategy]["name"]),
    unsafe_allow_html=True)

    tm = st.session_state.trade_manager

    # Active trades
    st.markdown("### Active Trades")
    if tm.active_trades:
        for tid, trade in tm.active_trades.items():
            tp_bar = ""
            for i in range(10):
                if i < trade.tp_hit:
                    tp_bar += '<div class="tp-bar tp-hit" style="width:9%">&nbsp;</div>'
                else:
                    tp_bar += '<div class="tp-bar tp-pending" style="width:9%">&nbsp;</div>'

            color = "signal-buy" if trade.direction == "BUY" else "signal-sell"
            st.markdown(f"""<div class="signal-card {color}">
                <div style="font-size:16px; font-weight:700;">
                    {trade.direction} XAUUSD | {trade.grade} | Entry: ${trade.entry_price:.2f}
                </div>
                <div style="margin:8px 0;">
                    SL: ${trade.sl:.2f} | Lot: {trade.remaining_lot}/{trade.initial_lot} |
                    TPs Hit: {trade.tp_hit}/10
                </div>
                <div style="display:flex; gap:2px; margin:8px 0;">{tp_bar}</div>
            </div>""", unsafe_allow_html=True)

            # Trade actions log
            with st.expander(f"Trade Log — {tid}"):
                for action in trade.actions:
                    st.text(f"{action.get('time', '')}: {action.get('action', '')} — {action.get('detail', action.get('reason', ''))}")
    else:
        st.info("No active trades. Signals will appear here when the engine fires.")

    # Recent closed trades
    st.markdown("### Recently Closed Trades")
    if tm.closed_trades:
        for trade in reversed(tm.closed_trades[-10:]):
            pnl_color = "#10b981" if trade.pnl_usd > 0 else "#ef4444"
            emoji = "\U0001f4b0" if trade.pnl_usd > 0 else "\U0001f534"
            st.markdown(f"""<div style="background:#111827; border-radius:8px; padding:12px; margin:4px 0;
                            border-left:3px solid {pnl_color};">
                {emoji} <b>{trade.direction}</b> @ ${trade.entry_price:.2f} |
                TPs Hit: {trade.tp_hit}/10 |
                PnL: <span style="color:{pnl_color}">{'+'if trade.pnl_usd>0 else ''}${trade.pnl_usd:.2f}</span> |
                {trade.close_reason}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No closed trades yet.")


# ═════════════════════════════════════════════════════════════
# PAGE: PERFORMANCE SCOREBOARD
# ═════════════════════════════════════════════════════════════
def page_scoreboard():
    st.markdown("""<div class="gold-header">
        <h1>\U0001f3c6 Performance Scoreboard</h1>
        <div class="subtitle">Signal performance metrics | Transparency builds trust</div>
    </div>""", unsafe_allow_html=True)

    tm = st.session_state.trade_manager
    stats = tm.get_performance_stats()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("Total Trades", stats["total_trades"], "#F5A623"),
        ("Win Rate", f"{stats['win_rate']}%", "#10b981" if stats["win_rate"] > 50 else "#ef4444"),
        ("Total PnL", f"${stats['total_pnl']:+.2f}", "#10b981" if stats["total_pnl"] > 0 else "#ef4444"),
        ("Profit Factor", f"{stats['profit_factor']}", "#10b981" if stats["profit_factor"] > 1 else "#ef4444"),
    ]
    for i, (label, value, color) in enumerate(metrics):
        with [col1, col2, col3, col4][i]:
            st.markdown(f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="value" style="color:{color}">{value}</div>
            </div>""", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    metrics2 = [
        ("Wins", stats["wins"], "#10b981"),
        ("Losses", stats["losses"], "#ef4444"),
        ("Best Trade", f"${stats['best_trade']:+.2f}", "#10b981"),
        ("Max Drawdown", f"${stats['max_drawdown']:.2f}", "#ef4444"),
    ]
    for i, (label, value, color) in enumerate(metrics2):
        with [col1, col2, col3, col4][i]:
            st.markdown(f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="value" style="color:{color}">{value}</div>
            </div>""", unsafe_allow_html=True)

    # Equity curve
    cumulative = stats.get("cumulative_pnl", [])
    if cumulative:
        st.markdown("### Equity Curve")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=cumulative, mode="lines+markers",
            line=dict(color="#00d4ff", width=2),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor="rgba(245,166,35,0.1)",
        ))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
            height=350, yaxis_title="Cumulative PnL ($)",
            xaxis_title="Trade Number",
            margin=dict(l=50, r=50, t=30, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Performance data will appear once trades are recorded.")


# ═════════════════════════════════════════════════════════════
# PAGE: MARKET REGIME
# ═════════════════════════════════════════════════════════════
def page_regime():
    if st_autorefresh:
        st_autorefresh(interval=30000, limit=None, key="regime_refresh")

    st.markdown("""<div class="gold-header">
        <h1>\U0001f30d Market Regime Indicator</h1>
        <div class="subtitle">Is gold trending, ranging, or volatile?</div>
    </div>""", unsafe_allow_html=True)

    overview = st.session_state.scanner.get_market_overview()

    # Regime detection
    h4_trend = overview.get("h4_trend", "neutral")
    h1_trend = overview.get("h1_trend", "neutral")
    structure = overview.get("structure", "unknown")
    atr = overview.get("atr", 0)
    rsi = overview.get("rsi", 50)

    # Determine regime
    if "bull" in h4_trend and "bull" in h1_trend:
        regime = "STRONG UPTREND"
        regime_color = "#10b981"
        regime_desc = "Gold is in a confirmed uptrend across H4 and H1. Look for BUY signals on pullbacks."
    elif "bear" in h4_trend and "bear" in h1_trend:
        regime = "STRONG DOWNTREND"
        regime_color = "#ef4444"
        regime_desc = "Gold is in a confirmed downtrend across H4 and H1. Look for SELL signals on rallies."
    elif h4_trend != h1_trend and "neutral" not in (h4_trend, h1_trend):
        regime = "TRANSITION"
        regime_color = "#F5A623"
        regime_desc = "H4 and H1 are showing different trends. Market may be transitioning. Be cautious with new entries."
    else:
        regime = "RANGING / CONSOLIDATION"
        regime_color = "#6b7280"
        regime_desc = "Gold is consolidating. Wait for a breakout with clear structure before entering."

    st.markdown(f"""<div style="background:#111827; border:2px solid {regime_color};
                    border-radius:12px; padding:24px; text-align:center; margin:20px 0;">
        <div style="color:{regime_color}; font-size:32px; font-weight:700; font-family:'Space Mono',monospace;">
            {regime}
        </div>
        <div style="color:#9ca3af; font-size:14px; margin-top:8px;">{regime_desc}</div>
    </div>""", unsafe_allow_html=True)

    # Timeframe breakdown
    col1, col2, col3, col4 = st.columns(4)
    tf_data = [
        ("H4 Trend", h4_trend.replace("_", " ").title()),
        ("H1 Trend", h1_trend.replace("_", " ").title()),
        ("Structure", structure.title()),
        ("Volatility", f"ATR ${atr:.2f}"),
    ]
    for i, (label, value) in enumerate(tf_data):
        with [col1, col2, col3, col4][i]:
            st.markdown(f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="value" style="font-size:18px">{value}</div>
            </div>""", unsafe_allow_html=True)

    # Regime chart
    df = fetch_bars("XAU/USD", "4h", 100, TWELVE_DATA_API_KEY)
    if df is not None:
        df = add_indicators(df)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="XAUUSD H4",
            increasing_line_color="#10b981", decreasing_line_color="#ef4444",
        ))
        if "ema50" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA50",
                                    line=dict(color="#3b82f6", width=2)))
        if "ema200" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["ema200"], name="EMA200",
                                    line=dict(color="#ef4444", width=2, dash="dot")))
        if "bb_upper" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], name="BB Upper",
                                    line=dict(color="rgba(168,85,247,0.3)", width=1)))
            fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], name="BB Lower",
                                    line=dict(color="rgba(168,85,247,0.3)", width=1),
                                    fill="tonexty", fillcolor="rgba(168,85,247,0.05)"))

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
            height=500, xaxis_rangeslider_visible=False,
            title=f"XAUUSD H4 | Regime: {regime}",
            margin=dict(l=50, r=50, t=40, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════
# PAGE: BACKTEST ENGINE
# ═════════════════════════════════════════════════════════════
def page_backtest():
    # Restrict to creator only
    CREATOR_EMAIL = "junkiatyeo96@gmail.com"
    user_email = st.session_state.get("user", {}).get("email", "")
    if user_email.lower() != CREATOR_EMAIL.lower():
        st.markdown("""<div class="gold-header">
            <h1>\U0001f52c Backtest Engine</h1>
            <div class="subtitle">Admin-only feature</div>
        </div>""", unsafe_allow_html=True)
        st.warning("The Backtest Engine is restricted to the platform administrator. "
                   "Contact the Alpha FX Hub team for access.")
        return

    st.markdown("""<div class="gold-header">
        <h1>\U0001f52c Backtest Engine</h1>
        <div class="subtitle">Test our strategy against historical gold data</div>
    </div>""", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bt_strategy = st.selectbox("TP Strategy", ["split_15_10", "equal_10"],
                                    format_func=lambda x: "15/10 Split + Trailing" if x == "split_15_10" else "Equal 10%",
                                    key="bt_strategy")
    with col2:
        period_options = {
            "1 Day": 1, "3 Days": 3, "1 Week": 5, "2 Weeks": 10,
            "1 Month": 22, "3 Months": 66, "6 Months": 132, "12 Months": 264,
        }
        bt_period_label = st.selectbox("Test Period", list(period_options.keys()), index=4, key="bt_period")
        bt_days = period_options[bt_period_label]
    with col3:
        bt_balance = st.number_input("Starting Balance ($)", value=10000, step=1000, key="bt_balance")
    with col4:
        bt_risk = st.selectbox("Risk Per Trade", [2.0, 3.0, 5.0], index=0, key="bt_risk",
                                format_func=lambda x: f"{x:.0f}%")

    if st.button("\U0001f680 Run Backtest", use_container_width=True, type="primary"):
        with st.spinner("Running backtest... Analyzing historical gold data..."):
            try:
                results = run_backtest(
                    strategy=bt_strategy,
                    months=1,
                    starting_balance=bt_balance,
                    risk_pct=bt_risk,
                    days=bt_days,
                )
                st.session_state.bt_results = results
            except Exception as e:
                st.error(f"Backtest error: {e}")
                logger.error(f"Backtest failed: {e}", exc_info=True)
                return

    results = st.session_state.get("bt_results")
    if results is None:
        st.info("Configure parameters above and click **Run Backtest** to test the strategy against historical data.")
        return

    # ── Summary Cards ──
    st.markdown("### \U0001f4ca Performance Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trades", results.get("total_trades", 0))
    c2.metric("Win Rate", f"{results.get('win_rate_pct', 0):.1f}%")
    c3.metric("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
    c4.metric("Total Return", f"${results.get('total_return_usd', 0):,.2f}",
              delta=f"{results.get('total_return_pct', 0):.1f}%")
    c5.metric("Max Drawdown", f"${results.get('max_drawdown_usd', 0):,.2f}",
              delta=f"-{results.get('max_drawdown_pct', 0):.1f}%", delta_color="inverse")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Wins / Losses", f"{results.get('wins', 0)} / {results.get('losses', 0)}")
    c7.metric("Avg Win", f"${results.get('avg_win', 0):,.2f}")
    c8.metric("Avg Loss", f"${results.get('avg_loss', 0):,.2f}")
    c9.metric("Avg TPs Hit", f"{results.get('avg_tps_reached', 0):.1f} / 10")

    # ── Equity Curve ──
    equity_data = results.get("equity_curve", [])
    if equity_data:
        st.markdown("### \U0001f4c8 Equity Curve")
        eq_df = pd.DataFrame(equity_data, columns=["time", "balance"])
        eq_df["time"] = pd.to_datetime(eq_df["time"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eq_df["time"], y=eq_df["balance"],
            mode="lines", name="Equity",
            line=dict(color="#00d4ff", width=2),
            fill="tozeroy", fillcolor="rgba(0,212,255,0.08)",
        ))
        fig.add_hline(y=bt_balance, line_dash="dash", line_color="#6b7280",
                      annotation_text="Starting Balance")
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#0a0e17", plot_bgcolor="#0a0e17",
            height=400, margin=dict(l=50, r=50, t=30, b=30),
            yaxis_title="Account Balance ($)", xaxis_title="Date",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Win Rate Breakdown ──
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### \U0001f3af Win Rate by Grade")
        grade_data = results.get("by_grade", {})
        if grade_data:
            grade_df = pd.DataFrame([
                {"Grade": g, "Win Rate": f"{d.get('win_rate', 0):.1f}%", "Trades": d.get("trades", 0)}
                for g, d in grade_data.items() if d.get("trades", 0) > 0
            ])
            st.dataframe(grade_df, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("### \U0001f3af Win Rate by Confidence")
        conf_data = results.get("by_confidence", {})
        if conf_data:
            conf_df = pd.DataFrame([
                {"Confidence": c, "Win Rate": f"{d.get('win_rate', 0):.1f}%", "Trades": d.get("trades", 0)}
                for c, d in conf_data.items() if d.get("trades", 0) > 0
            ])
            st.dataframe(conf_df, use_container_width=True, hide_index=True)

    # ── Session Performance ──
    session_data = results.get("by_session", {})
    if session_data:
        st.markdown("### \U0001f553 Performance by Session")
        sess_df = pd.DataFrame([
            {"Session": s, "Win Rate": f"{d.get('win_rate', 0):.1f}%",
             "Trades": d.get("trades", 0), "Avg P&L": f"${d.get('avg_pnl', 0):,.2f}"}
            for s, d in session_data.items() if d.get("trades", 0) > 0
        ])
        st.dataframe(sess_df, use_container_width=True, hide_index=True)

    # ── Monthly Breakdown ──
    monthly = results.get("monthly", [])
    if monthly:
        st.markdown("### \U0001f4c5 Monthly Breakdown")
        month_df = pd.DataFrame(monthly)
        if not month_df.empty:
            st.dataframe(month_df, use_container_width=True, hide_index=True)

    # ── Trade Log ──
    trades_log = results.get("trades", [])
    if trades_log:
        with st.expander(f"Full Trade Log ({len(trades_log)} trades)"):
            log_df = pd.DataFrame(trades_log)
            display_cols = [c for c in ["trade_num", "entry_time", "direction", "entry_price",
                                         "sl", "grade", "confidence", "tps_reached", "pnl",
                                         "r_multiple", "status"] if c in log_df.columns]
            if display_cols:
                st.dataframe(log_df[display_cols], use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════
# PAGE: AI LEARNING INSIGHTS
# ═════════════════════════════════════════════════════════════
def page_ai_insights():
    # Restrict to creator only
    CREATOR_EMAIL = "junkiatyeo96@gmail.com"
    user_email = st.session_state.get("user", {}).get("email", "")
    if user_email.lower() != CREATOR_EMAIL.lower():
        st.markdown("""<div class="gold-header">
            <h1>AI Learning Insights</h1>
            <div class="subtitle">Admin-only feature</div>
        </div>""", unsafe_allow_html=True)
        st.warning("AI Learning Insights is restricted to the platform administrator.")
        return

    st.markdown("""<div class="gold-header">
        <h1>AI Learning Insights</h1>
        <div class="subtitle">Adaptive engine that learns from your trade history to improve signals</div>
    </div>""", unsafe_allow_html=True)

    learner = st.session_state.adaptive_learner
    cloud = st.session_state.get("cloud_sync")
    profile = learner.profile

    # ── Refresh / Re-learn Button ──
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Re-Analyze Trades", type="primary", use_container_width=True):
            # Try cloud first, then fall back to local
            trades_data = []
            if cloud:
                trades_data = cloud.fetch_trades_for_learning(limit=500)
            if not trades_data:
                # Fall back to local closed trades
                trades_data = [t.to_dict() for t in st.session_state.trade_manager.closed_trades]
            if trades_data:
                profile = learner.analyze(trades_data)
                st.success(f"Analyzed {len(trades_data)} trades — insights updated!")
                st.rerun()
            else:
                st.warning("No trade history yet. Complete some trades first!")

    with col1:
        st.markdown(f"**Trades Analyzed:** {profile.total_trades_analyzed}")
        if profile.last_updated:
            st.caption(f"Last updated: {profile.last_updated[:19]}")

    st.divider()

    # ── Key Insights ──
    if profile.insights:
        st.markdown("### Key Insights")
        for insight in profile.insights:
            # Color-code based on content
            if any(w in insight.lower() for w in ["strong", "well", "sweet spot", "best"]):
                st.markdown(f"""<div class="alert-green" style="margin:6px 0; padding:10px 14px;">
                    {insight}</div>""", unsafe_allow_html=True)
            elif any(w in insight.lower() for w in ["weak", "underperform", "risky", "avoid", "caution", "hurt"]):
                st.markdown(f"""<div class="alert-red" style="margin:6px 0; padding:10px 14px;">
                    {insight}</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="alert-yellow" style="margin:6px 0; padding:10px 14px;">
                    {insight}</div>""", unsafe_allow_html=True)
    else:
        st.info("No insights yet — need at least 10 closed trades for the AI to start learning.")

    st.divider()

    # ── Weight Tables ──
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### Session Performance Weights")
        session_df = pd.DataFrame([
            {"Session": k, "Weight": f"{v:.2f}",
             "Signal": "Boost" if v > 1.1 else ("Reduce" if v < 0.8 else "Normal")}
            for k, v in profile.session_weights.items()
        ])
        st.dataframe(session_df, use_container_width=True, hide_index=True)

        st.markdown("### Day-of-Week Weights")
        day_df = pd.DataFrame([
            {"Day": k, "Weight": f"{v:.2f}",
             "Signal": "Boost" if v > 1.1 else ("Reduce" if v < 0.8 else "Normal")}
            for k, v in profile.day_weights.items()
        ])
        st.dataframe(day_df, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("### Grade Weights")
        grade_df = pd.DataFrame([
            {"Grade": k, "Weight": f"{v:.2f}",
             "Signal": "Boost" if v > 1.1 else ("Reduce" if v < 0.8 else "Normal")}
            for k, v in profile.grade_weights.items()
        ])
        st.dataframe(grade_df, use_container_width=True, hide_index=True)

        st.markdown("### Trend Alignment")
        trend_df = pd.DataFrame([
            {"Trend": k, "Weight": f"{v:.2f}",
             "Signal": "Boost" if v > 1.1 else ("Reduce" if v < 0.8 else "Normal")}
            for k, v in profile.trend_weights.items()
        ])
        st.dataframe(trend_df, use_container_width=True, hide_index=True)

        st.markdown("### Volatility Regime")
        vol_df = pd.DataFrame([
            {"Regime": k, "Weight": f"{v:.2f}",
             "Signal": "Boost" if v > 1.1 else ("Reduce" if v < 0.8 else "Normal")}
            for k, v in profile.volatility_weights.items()
        ])
        st.dataframe(vol_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Optimal Indicator Ranges ──
    st.markdown("### Optimal Indicator Ranges (from winning trades)")
    ind_col1, ind_col2, ind_col3 = st.columns(3)
    with ind_col1:
        st.metric("RSI Sweet Spot", f"{profile.optimal_rsi_range[0]:.0f} - {profile.optimal_rsi_range[1]:.0f}")
    with ind_col2:
        st.metric("Min ADX", f"{profile.optimal_adx_min:.0f}")
    with ind_col3:
        st.metric("Best Strategy", profile.best_strategy)

    # ── Cloud Sync Status ──
    st.divider()
    st.markdown("### Cloud Sync Status")
    if cloud and st.session_state.get("user"):
        st.success("Connected to Supabase — trades auto-sync to cloud")
        sync_col1, sync_col2 = st.columns(2)
        with sync_col1:
            if st.button("Sync All Local Trades to Cloud"):
                local_trades = [t.to_dict() for t in st.session_state.trade_manager.closed_trades]
                if local_trades:
                    count = cloud.upload_trades_batch(local_trades)
                    st.success(f"Synced {count} trades to cloud!")
                else:
                    st.info("No local trades to sync.")
        with sync_col2:
            if st.button("Load Trades from Cloud"):
                cloud_trades = cloud.fetch_trades(limit=200)
                st.info(f"Found {len(cloud_trades)} trades in cloud.")
    else:
        st.warning("Cloud sync not connected — trades saved locally only. Log in to enable cloud sync.")

    # ── SQL Setup Helper ──
    with st.expander("Supabase Setup (run once in SQL Editor)"):
        st.code(CloudTradeSync.ensure_table_sql(None), language="sql")
        st.caption("Copy this SQL and run it in your Supabase Dashboard > SQL Editor to create the trade_history table.")


# ═════════════════════════════════════════════════════════════
# PAGE: DECISION ASSISTANT
# ═════════════════════════════════════════════════════════════

def page_decision_assistant():
    """Semi-automated Gold Decision Assistant — NOT auto-trading."""
    from decision_assistant import BiasEngine, EntryZoneDetector, MarketBias, TelegramAlerts

    st.markdown("""<div class="gold-header">
        <h1>\U0001f916 Gold Decision Assistant</h1>
        <div class="subtitle">Semi-Automated | H1 Bias + M15 Entry | YOU Trade, System Assists</div>
    </div>""", unsafe_allow_html=True)

    # Initialize session state
    if "da_active_trade" not in st.session_state:
        st.session_state.da_active_trade = None
    if "da_last_zone" not in st.session_state:
        st.session_state.da_last_zone = None
    if "da_zones_today" not in st.session_state:
        st.session_state.da_zones_today = 0

    # Auto-refresh every 30s
    if st_autorefresh:
        st_autorefresh(interval=30000, limit=None, key="da_refresh")

    # ── FETCH LIVE DATA ──
    price = fetch_price(api_key=TWELVE_DATA_API_KEY)
    m15_df = fetch_bars(interval="15min", outputsize=200, api_key=TWELVE_DATA_API_KEY)
    h1_df = fetch_bars(interval="1h", outputsize=100, api_key=TWELVE_DATA_API_KEY)

    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour

    # Session detection
    session_name = "OFF"
    if 7 <= hour < 10:
        session_name = "LONDON"
    elif 12 <= hour < 15:
        session_name = "NEW YORK"
    elif 12 <= hour < 16:
        session_name = "LN OVERLAP"
    elif 5 <= hour < 7:
        session_name = "PRE-LONDON"
    elif 0 <= hour < 5 or hour >= 21:
        session_name = "ASIAN"

    # ── A. MARKET BIAS ENGINE ──
    bias_engine = BiasEngine()
    bias = bias_engine.analyze(m15_df, h1_df) if m15_df is not None and h1_df is not None else MarketBias()

    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="label">XAUUSD</div>
            <div class="value">${price:.2f}</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        bias_color = "#10b981" if bias.bias == "BULLISH" else ("#ef4444" if bias.bias == "BEARISH" else "#6b7280")
        st.markdown(f"""<div class="metric-card">
            <div class="label">Market Bias</div>
            <div class="value" style="color:{bias_color}">{bias.bias}</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Strength</div>
            <div class="value">{bias.strength}</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        sess_color = "#10b981" if session_name in ("LONDON", "NEW YORK", "LN OVERLAP") else "#6b7280"
        st.markdown(f"""<div class="metric-card">
            <div class="label">Session</div>
            <div class="value" style="color:{sess_color}">{session_name}</div>
        </div>""", unsafe_allow_html=True)

    with col5:
        st.markdown(f"""<div class="metric-card">
            <div class="label">H1 Structure</div>
            <div class="value">{bias.h1_structure or 'N/A'}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── MARKET STRUCTURE DETAILS ──
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### Market Structure")

        struct_col1, struct_col2, struct_col3 = st.columns(3)
        with struct_col1:
            st.metric("Key High", f"${bias.key_high:.2f}" if bias.key_high else "—")
            st.metric("EMA 50", f"${bias.ema50:.2f}" if bias.ema50 else "—")
        with struct_col2:
            st.metric("Key Low", f"${bias.key_low:.2f}" if bias.key_low else "—")
            st.metric("EMA 200", f"${bias.ema200:.2f}" if bias.ema200 else "—")
        with struct_col3:
            st.metric("ATR (H1)", f"${bias.atr:.2f}" if bias.atr else "—")
            st.metric("Setups Today", f"{st.session_state.da_zones_today}/3")

        # Liquidity levels
        if bias.liquidity_above or bias.liquidity_below:
            st.markdown("**Liquidity Levels**")
            liq_col1, liq_col2 = st.columns(2)
            with liq_col1:
                st.markdown("Sell-side (above):")
                for lvl in (bias.liquidity_above or [])[:4]:
                    dist = lvl - price
                    st.markdown(f"&nbsp;&nbsp; `${lvl:.2f}` (+${dist:.1f})")
            with liq_col2:
                st.markdown("Buy-side (below):")
                for lvl in (bias.liquidity_below or [])[:4]:
                    dist = price - lvl
                    st.markdown(f"&nbsp;&nbsp; `${lvl:.2f}` (-${dist:.1f})")

    with col_right:
        # ── B. SMART ENTRY ZONE ──
        st.markdown("### Entry Zone")

        zone_detector = EntryZoneDetector()
        zone = None
        if m15_df is not None and h1_df is not None and st.session_state.da_zones_today < 3:
            zone = zone_detector.detect(m15_df, h1_df, bias, price)

        if zone and zone.confidence >= 50:
            st.session_state.da_last_zone = zone
            dir_color = "#10b981" if zone.direction == "BUY" else "#ef4444"
            dir_bg = "signal-buy" if zone.direction == "BUY" else "signal-sell"

            st.markdown(f"""<div class="signal-card {dir_bg}">
                <span style="font-size:20px; font-weight:700; color:white;">{zone.direction} ZONE</span><br>
                <span style="font-size:14px; color:#d1d5db;">Entry: <b>${zone.entry_low:.2f} – ${zone.entry_high:.2f}</b></span><br>
                <span style="color:#9ca3af;">SL: ${zone.sl:.2f}</span><br>
                <span style="color:#9ca3af;">TP1: ${zone.tp1:.2f} | TP2: ${zone.tp2:.2f} | TP3: ${zone.tp3:.2f}</span><br>
                <span style="color:#9ca3af;">R:R: 1:{zone.rr_ratio}</span><br>
                <span style="color:#00d4ff; font-weight:600;">Confidence: {zone.confidence}%</span><br>
                <span style="color:#6b7280; font-size:12px;">{zone.reason}</span><br>
                <span style="color:#6b7280; font-size:12px;">Valid until: {zone.valid_until}</span>
            </div>""", unsafe_allow_html=True)

            # Check proximity to zone for alert
            in_zone = zone.entry_low <= price <= zone.entry_high
            near_zone = (zone.entry_low - 1.0 <= price <= zone.entry_high + 1.0) and not in_zone

            if in_zone:
                st.warning(f"\U0001f3af **PRICE IN ENTRY ZONE** — Watch for confirmation candle")
                # Send Telegram
                telegram = TelegramAlerts(TELEGRAM_BOT_TOKEN, TELEGRAM_PRIVATE_CHANNEL_ID)
                telegram.entry_zone_hit(zone.direction, zone.entry_low, zone.entry_high, price)
            elif near_zone:
                st.info(f"\u23f3 Price approaching zone (${abs(price - zone.entry_low):.1f} away)")
                telegram = TelegramAlerts(TELEGRAM_BOT_TOKEN, TELEGRAM_PRIVATE_CHANNEL_ID)
                telegram.approaching_zone(
                    zone.direction, bias.bias, zone.entry_low, zone.entry_high,
                    price, zone.sl, zone.tp1, zone.tp2, zone.tp3,
                    zone.confidence, zone.session
                )
        else:
            if st.session_state.da_last_zone:
                z = st.session_state.da_last_zone
                st.markdown(f"""<div style="background:#1f2937; border:1px solid #374151; border-radius:10px; padding:16px;">
                    <span style="color:#6b7280;">Last zone: {z.direction} ${z.entry_low:.2f}–${z.entry_high:.2f}</span><br>
                    <span style="color:#4b5563; font-size:12px;">Waiting for new setup...</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""<div style="background:#1f2937; border:1px solid #374151; border-radius:10px; padding:16px;">
                    <span style="color:#6b7280;">No active zone</span><br>
                    <span style="color:#4b5563; font-size:12px;">Scanning for liquidity sweep + pullback...</span>
                </div>""", unsafe_allow_html=True)

    st.divider()

    # ── D. TRADE MANAGER ──
    st.markdown("### Trade Manager")
    st.caption("Enter your trade manually after you execute it. The system will track and suggest management actions.")

    trade_col1, trade_col2 = st.columns([1, 2])

    with trade_col1:
        with st.form("trade_entry_form"):
            direction = st.selectbox("Direction", ["BUY", "SELL"])
            entry_price = st.number_input("Entry Price", value=float(f"{price:.2f}"), step=0.1, format="%.2f")

            # Auto-fill from zone if available
            z = st.session_state.da_last_zone
            if z and z.direction == direction:
                default_sl = z.sl
                default_tp1 = z.tp1
                default_tp2 = z.tp2
                default_tp3 = z.tp3
            else:
                atr = bias.atr if bias.atr > 0 else 5.0
                if direction == "BUY":
                    default_sl = entry_price - atr * 1.5
                    default_tp1 = entry_price + atr * 2.0
                    default_tp2 = entry_price + atr * 3.5
                    default_tp3 = entry_price + atr * 5.0
                else:
                    default_sl = entry_price + atr * 1.5
                    default_tp1 = entry_price - atr * 2.0
                    default_tp2 = entry_price - atr * 3.5
                    default_tp3 = entry_price - atr * 5.0

            sl = st.number_input("Stop Loss", value=float(f"{default_sl:.2f}"), step=0.1, format="%.2f")
            tp1 = st.number_input("TP1", value=float(f"{default_tp1:.2f}"), step=0.1, format="%.2f")
            tp2 = st.number_input("TP2", value=float(f"{default_tp2:.2f}"), step=0.1, format="%.2f")
            tp3 = st.number_input("TP3", value=float(f"{default_tp3:.2f}"), step=0.1, format="%.2f")

            submitted = st.form_submit_button("Register Trade", type="primary", use_container_width=True)
            if submitted:
                st.session_state.da_active_trade = {
                    "direction": direction,
                    "entry_price": entry_price,
                    "sl": sl,
                    "original_sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "sl_at_be": False,
                    "opened_at": now_utc.strftime("%H:%M UTC"),
                }
                st.session_state.da_zones_today += 1
                st.success(f"Trade registered: {direction} @ ${entry_price:.2f}")

        if st.session_state.da_active_trade:
            if st.button("Close Trade", use_container_width=True):
                st.session_state.da_active_trade = None
                st.rerun()

    with trade_col2:
        trade = st.session_state.da_active_trade
        if trade:
            entry = trade["entry_price"]
            if trade["direction"] == "BUY":
                pips = (price - entry) / SYMBOL_PIP
                pnl_color = "#10b981" if pips > 0 else "#ef4444"
            else:
                pips = (entry - price) / SYMBOL_PIP
                pnl_color = "#10b981" if pips > 0 else "#ef4444"

            st.markdown(f"""<div class="metric-card" style="text-align:left; padding:20px;">
                <div style="font-size:18px; font-weight:700; color:white;">{trade['direction']} Trade Active</div>
                <div style="color:#9ca3af; margin-top:8px;">Entry: ${entry:.2f} | Current: ${price:.2f}</div>
                <div style="color:{pnl_color}; font-size:28px; font-weight:700; font-family:'Space Mono',monospace; margin:10px 0;">
                    {pips:+.1f} pips
                </div>
                <div style="color:#9ca3af;">SL: ${trade['sl']:.2f} {'(at BE)' if trade['sl_at_be'] else ''}</div>
                <div style="color:#9ca3af;">TP1: ${trade['tp1']:.2f} {'✓' if trade['tp1_hit'] else ''} | TP2: ${trade['tp2']:.2f} {'✓' if trade['tp2_hit'] else ''} | TP3: ${trade['tp3']:.2f}</div>
            </div>""", unsafe_allow_html=True)

            # ── LIVE TRADE SUGGESTIONS ──
            suggestions = []

            # TP1 hit check
            if not trade["tp1_hit"]:
                if (trade["direction"] == "BUY" and price >= trade["tp1"]) or \
                   (trade["direction"] == "SELL" and price <= trade["tp1"]):
                    trade["tp1_hit"] = True
                    trade["sl_at_be"] = True
                    if trade["direction"] == "BUY":
                        trade["sl"] = entry + 1 * SYMBOL_PIP
                    else:
                        trade["sl"] = entry - 1 * SYMBOL_PIP
                    suggestions.append(("success", "\U0001f3af **TP1 Hit!** Close 50% — SL moved to breakeven"))
                    # Telegram
                    telegram = TelegramAlerts(TELEGRAM_BOT_TOKEN, TELEGRAM_PRIVATE_CHANNEL_ID)
                    telegram.trade_update(trade["direction"], entry, price, pips,
                                          "TP1 hit! SL moved to breakeven", "Close 50% — Move SL to BE")

            # TP2 hit check
            if trade["tp1_hit"] and not trade["tp2_hit"]:
                if (trade["direction"] == "BUY" and price >= trade["tp2"]) or \
                   (trade["direction"] == "SELL" and price <= trade["tp2"]):
                    trade["tp2_hit"] = True
                    trade["sl"] = trade["tp1"]
                    suggestions.append(("success", "\U0001f3af **TP2 Hit!** Close 30% more — SL trailed to TP1"))
                    telegram = TelegramAlerts(TELEGRAM_BOT_TOKEN, TELEGRAM_PRIVATE_CHANNEL_ID)
                    telegram.trade_update(trade["direction"], entry, price, pips,
                                          "TP2 hit! SL moved to TP1", "Close 30% more — Trail SL to TP1")

            # TP3 check
            if trade["tp2_hit"]:
                if (trade["direction"] == "BUY" and price >= trade["tp3"]) or \
                   (trade["direction"] == "SELL" and price <= trade["tp3"]):
                    suggestions.append(("success", "\U0001f389 **TP3 Hit!** Full target achieved — Close remaining position"))

            # Structure change warning
            if trade["direction"] == "BUY" and bias.bias == "BEARISH":
                suggestions.append(("warning", f"\u26a0\ufe0f **Bearish CHoCH** — H1 structure now {bias.h1_structure}. Consider {'closing remaining' if trade['tp1_hit'] else 'reducing position'}"))
            elif trade["direction"] == "SELL" and bias.bias == "BULLISH":
                suggestions.append(("warning", f"\u26a0\ufe0f **Bullish CHoCH** — H1 structure now {bias.h1_structure}. Consider {'closing remaining' if trade['tp1_hit'] else 'reducing position'}"))

            # Running in profit suggestion
            if pips > 0 and not suggestions:
                if trade["direction"] == "BUY":
                    next_target = trade["tp1"] if not trade["tp1_hit"] else (trade["tp2"] if not trade["tp2_hit"] else trade["tp3"])
                    pips_to_target = (next_target - price) / SYMBOL_PIP
                else:
                    next_target = trade["tp1"] if not trade["tp1_hit"] else (trade["tp2"] if not trade["tp2_hit"] else trade["tp3"])
                    pips_to_target = (price - next_target) / SYMBOL_PIP
                suggestions.append(("info", f"\U0001f4ca Running +{pips:.0f} pips — {pips_to_target:.0f} pips to next target. **Hold.**"))

            elif pips < -20 and not suggestions:
                suggestions.append(("warning", f"\U0001f4c9 Trade in drawdown ({pips:.0f} pips). SL will protect at ${trade['sl']:.2f}."))

            for level, msg in suggestions:
                if level == "success":
                    st.success(msg)
                elif level == "warning":
                    st.warning(msg)
                else:
                    st.info(msg)

        else:
            st.markdown("""<div style="background:#1f2937; border:1px solid #374151; border-radius:10px; padding:30px; text-align:center;">
                <span style="color:#6b7280; font-size:16px;">No active trade</span><br>
                <span style="color:#4b5563; font-size:13px;">Use the form to register your trade after manual execution</span>
            </div>""", unsafe_allow_html=True)

    # ── NOTIFICATION STATUS ──
    st.divider()
    notif_col1, notif_col2 = st.columns(2)
    with notif_col1:
        st.markdown("**Notification Rules**")
        st.markdown("""
        - Price approaching entry zone ($1 away)
        - Entry zone hit
        - TP1/TP2/TP3 hit with management action
        - Structure change (CHoCH) against trade
        - NO spam during Asian session
        """)
    with notif_col2:
        st.markdown("**Active Filters**")
        st.markdown(f"""
        - Direction: **{bias.bias} only** (structure filter)
        - Session: **{'Active' if session_name in ('LONDON', 'NEW YORK', 'LN OVERLAP') else 'Inactive — ' + session_name}**
        - Sweep required before entry zone
        - Max 3 setups per day
        """)


# ═════════════════════════════════════════════════════════════
# PAGE ROUTER
# ═════════════════════════════════════════════════════════════
PAGE_MAP = {
    "home": page_home,
    "dashboard": page_dashboard,
    "assistant": page_decision_assistant,
    "academy": page_academy,
    "manual": page_manual,
    "calendar": page_calendar,
    "risk_calc": page_risk_calc,
    "tracker": page_tracker,
    "scoreboard": page_scoreboard,
    "regime": page_regime,
    "backtest": page_backtest,
    "ai_insights": page_ai_insights,
}

# Route to current page
current_page = st.session_state.get("page", "home")
page_fn = PAGE_MAP.get(current_page, page_home)
page_fn()

# Footer
st.markdown("""
<div style="text-align:center; padding:20px 0; color:#4b5563; font-size:11px; border-top:1px solid #1f2937; margin-top:40px;">
    \u25c8 Alpha FX Hub v{version} | XAUUSD Gold Trading Platform<br>
    <i>Risk Disclaimer: Trading involves substantial risk. Past performance does not guarantee future results.
    Only trade with capital you can afford to lose.</i>
</div>
""".format(version=VERSION), unsafe_allow_html=True)
