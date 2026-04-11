"""
MT5 Trade Analysis Page for Streamlit Trading App
Provides comprehensive trade history analysis, performance metrics, and AI-powered insights.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import time

# ============================================================================
# CONFIGURATION & STYLING
# ============================================================================

NEON_COLORS = {
    "primary": "#00FF41",      # Neon green
    "secondary": "#FF006E",    # Neon pink
    "accent": "#00D9FF",       # Cyan
    "warning": "#FFB703",      # Orange
    "danger": "#FF0000",       # Red
    "success": "#00FF41",      # Green
    "background": "#0A0E27",   # Dark blue
}

METAAPI_BASE_URL = "https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# ============================================================================
# CACHE & DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)  # 5-minute cache
def fetch_trade_history(
    metaapi_token: str,
    metaapi_account: str,
    days_back: int = 30
) -> Tuple[Optional[List[Dict]], str]:
    """
    Fetch trade history from MetaAPI for the last N days.

    Args:
        metaapi_token: MetaAPI authentication token
        metaapi_account: MetaAPI account ID
        days_back: Number of days to fetch history for

    Returns:
        Tuple of (trades_list, status_message)
    """
    try:
        # Calculate time range
        end_timestamp = int(time.time() * 1000)
        start_timestamp = int((time.time() - days_back * 86400) * 1000)

        # Build URL
        url = f"{METAAPI_BASE_URL}/users/current/accounts/{metaapi_account}/history-deals/time/{start_timestamp}/{end_timestamp}"

        # Make request
        headers = {"auth-token": metaapi_token}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        deals = response.json()

        if not deals:
            return [], "No trades found in the selected period."

        return deals, f"Successfully fetched {len(deals)} trades"

    except requests.exceptions.Timeout:
        return None, "⏱️ Request timed out. MetaAPI server may be unreachable."
    except requests.exceptions.ConnectionError:
        return None, "🔌 Connection error. Check your internet connection or MetaAPI status."
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return None, "🔐 Authentication failed. Check your MetaAPI token."
        elif e.response.status_code == 404:
            return None, "❌ Account not found. Verify your MetaAPI account ID."
        return None, f"API Error: {e.response.status_code}"
    except Exception as e:
        return None, f"Error fetching trades: {str(e)}"

# ============================================================================
# DATA PROCESSING
# ============================================================================

def process_trades(deals: List[Dict]) -> pd.DataFrame:
    """
    Convert raw MetaAPI deals to a structured DataFrame with metrics.

    Args:
        deals: List of deal dictionaries from MetaAPI

    Returns:
        Processed DataFrame with calculated metrics
    """
    if not deals:
        return pd.DataFrame()

    trades = []
    for deal in deals:
        trade = {
            "id": deal.get("id", ""),
            "ticket": deal.get("ticket", deal.get("id", "")),
            "symbol": deal.get("symbol", "UNKNOWN"),
            "type": deal.get("type", "BUY"),
            "entry_time": datetime.fromtimestamp(deal.get("time", 0) / 1000),
            "close_time": datetime.fromtimestamp(deal.get("time", 0) / 1000),
            "entry_price": deal.get("entryPrice", 0),
            "close_price": deal.get("price", deal.get("entryPrice", 0)),
            "volume": deal.get("volume", deal.get("quantity", 0)),
            "profit": deal.get("profit", 0),
            "commission": deal.get("commission", 0),
            "swap": deal.get("swap", 0),
            "pnl": deal.get("profit", 0),
        }

        # Calculate metrics
        if trade["volume"] > 0 and trade["entry_price"] > 0:
            if trade["type"].upper() == "BUY":
                trade["pips"] = (trade["close_price"] - trade["entry_price"]) * 10000
            else:
                trade["pips"] = (trade["entry_price"] - trade["close_price"]) * 10000
        else:
            trade["pips"] = 0

        trade["is_win"] = trade["pnl"] > 0
        trade["day_of_week"] = trade["entry_time"].strftime("%A")
        trade["hour"] = trade["entry_time"].hour

        trades.append(trade)

    return pd.DataFrame(trades)

def calculate_performance_metrics(df: pd.DataFrame) -> Dict:
    """
    Calculate comprehensive performance metrics from trades.

    Args:
        df: DataFrame of processed trades

    Returns:
        Dictionary of performance metrics
    """
    if df.empty:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "total_pnl": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "avg_holding_time": "0h",
        }

    wins = df[df["is_win"]]
    losses = df[~df["is_win"]]

    total_trades = len(df)
    total_wins = len(wins)
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    total_pnl = df["pnl"].sum()
    best_trade = df["pnl"].max() if len(df) > 0 else 0
    worst_trade = df["pnl"].min() if len(df) > 0 else 0

    avg_win = wins["pnl"].mean() if len(wins) > 0 else 0
    avg_loss = losses["pnl"].mean() if len(losses) > 0 else 0

    # Calculate consecutive wins/losses
    df_sorted = df.sort_values("entry_time").reset_index(drop=True)
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_wins = 0
    current_losses = 0

    for is_win in df_sorted["is_win"]:
        if is_win:
            current_wins += 1
            current_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
        else:
            current_losses += 1
            current_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, current_losses)

    # Calculate average holding time
    df_sorted["holding_time"] = (df_sorted["close_time"] - df_sorted["entry_time"]).dt.total_seconds() / 3600
    avg_holding_hours = df_sorted["holding_time"].mean() if len(df_sorted) > 0 else 0
    avg_holding_time = f"{avg_holding_hours:.1f}h"

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "consecutive_wins": max_consecutive_wins,
        "consecutive_losses": max_consecutive_losses,
        "avg_holding_time": avg_holding_time,
    }

# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def plot_equity_curve(df: pd.DataFrame) -> go.Figure:
    """
    Create equity curve (cumulative PnL) chart.

    Args:
        df: DataFrame of trades

    Returns:
        Plotly figure
    """
    df_sorted = df.sort_values("entry_time").copy()
    df_sorted["cumulative_pnl"] = df_sorted["pnl"].cumsum()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_sorted["entry_time"],
        y=df_sorted["cumulative_pnl"],
        mode="lines",
        name="Equity Curve",
        line=dict(color=NEON_COLORS["primary"], width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 255, 65, 0.1)",
    ))

    fig.update_layout(
        title="Equity Curve (Cumulative PnL)",
        xaxis_title="Date",
        yaxis_title="Cumulative PnL ($)",
        hovermode="x unified",
        plot_bgcolor=NEON_COLORS["background"],
        paper_bgcolor=NEON_COLORS["background"],
        font=dict(color=NEON_COLORS["primary"]),
        height=400,
    )

    return fig

def plot_win_rate_by_day(df: pd.DataFrame) -> go.Figure:
    """
    Create win rate by day of week chart.

    Args:
        df: DataFrame of trades

    Returns:
        Plotly figure
    """
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    day_stats = df.groupby("day_of_week").apply(
        lambda x: (x["is_win"].sum() / len(x) * 100) if len(x) > 0 else 0
    ).reindex(day_order, fill_value=0)

    fig = go.Figure()

    colors = [NEON_COLORS["success"] if rate >= 50 else NEON_COLORS["danger"] for rate in day_stats.values]

    fig.add_trace(go.Bar(
        x=day_stats.index,
        y=day_stats.values,
        marker=dict(color=colors),
        name="Win Rate %",
    ))

    fig.update_layout(
        title="Win Rate by Day of Week",
        xaxis_title="Day",
        yaxis_title="Win Rate (%)",
        showlegend=False,
        plot_bgcolor=NEON_COLORS["background"],
        paper_bgcolor=NEON_COLORS["background"],
        font=dict(color=NEON_COLORS["primary"]),
        height=400,
    )

    return fig

def plot_pnl_distribution(df: pd.DataFrame) -> go.Figure:
    """
    Create PnL distribution histogram.

    Args:
        df: DataFrame of trades

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    wins = df[df["is_win"]]["pnl"]
    losses = df[~df["is_win"]]["pnl"]

    fig.add_trace(go.Histogram(
        x=wins,
        name="Wins",
        marker=dict(color=NEON_COLORS["success"]),
        opacity=0.7,
    ))

    fig.add_trace(go.Histogram(
        x=losses,
        name="Losses",
        marker=dict(color=NEON_COLORS["danger"]),
        opacity=0.7,
    ))

    fig.update_layout(
        title="PnL Distribution",
        xaxis_title="Profit/Loss ($)",
        yaxis_title="Number of Trades",
        barmode="overlay",
        plot_bgcolor=NEON_COLORS["background"],
        paper_bgcolor=NEON_COLORS["background"],
        font=dict(color=NEON_COLORS["primary"]),
        height=400,
    )

    return fig

def plot_win_rate_by_session(df: pd.DataFrame) -> go.Figure:
    """
    Create win rate by trading session (Asian/London/NY).

    Args:
        df: DataFrame of trades

    Returns:
        Plotly figure
    """
    def get_session(hour: int) -> str:
        if 0 <= hour < 8:
            return "Asian"
        elif 8 <= hour < 16:
            return "London"
        else:
            return "NY"

    df["session"] = df["hour"].apply(get_session)

    session_order = ["Asian", "London", "NY"]
    session_stats = df.groupby("session").apply(
        lambda x: (x["is_win"].sum() / len(x) * 100) if len(x) > 0 else 0
    ).reindex(session_order, fill_value=0)

    fig = go.Figure()

    colors = [NEON_COLORS["success"] if rate >= 50 else NEON_COLORS["danger"] for rate in session_stats.values]

    fig.add_trace(go.Bar(
        x=session_stats.index,
        y=session_stats.values,
        marker=dict(color=colors),
        name="Win Rate %",
    ))

    fig.update_layout(
        title="Win Rate by Trading Session",
        xaxis_title="Session",
        yaxis_title="Win Rate (%)",
        showlegend=False,
        plot_bgcolor=NEON_COLORS["background"],
        paper_bgcolor=NEON_COLORS["background"],
        font=dict(color=NEON_COLORS["primary"]),
        height=400,
    )

    return fig

# ============================================================================
# AI ANALYSIS FUNCTIONS
# ============================================================================

def generate_trade_summary(df: pd.DataFrame, metrics: Dict) -> str:
    """
    Generate a text summary of trading performance for AI analysis.

    Args:
        df: DataFrame of trades
        metrics: Performance metrics dictionary

    Returns:
        Text summary of trades
    """
    summary = f"""
TRADING PERFORMANCE SUMMARY
===========================
Period: Last {len(df)} trades
Date Range: {df['entry_time'].min().strftime('%Y-%m-%d')} to {df['entry_time'].max().strftime('%Y-%m-%d')}

KEY METRICS:
- Total Trades: {metrics['total_trades']}
- Win Rate: {metrics['win_rate']:.1f}%
- Profit Factor: {metrics['profit_factor']:.2f}
- Total P&L: ${metrics['total_pnl']:.2f}
- Best Trade: ${metrics['best_trade']:.2f}
- Worst Trade: ${metrics['worst_trade']:.2f}
- Avg Win: ${metrics['avg_win']:.2f}
- Avg Loss: ${metrics['avg_loss']:.2f}
- Max Consecutive Wins: {metrics['consecutive_wins']}
- Max Consecutive Losses: {metrics['consecutive_losses']}
- Avg Holding Time: {metrics['avg_holding_time']}

TRADING SYMBOLS:
{df['symbol'].value_counts().to_string()}

HOURLY DISTRIBUTION:
{df['hour'].value_counts().sort_index().to_string()}

TOP 5 WINNING TRADES:
{df.nlargest(5, 'pnl')[['symbol', 'entry_time', 'pnl', 'pips']].to_string(index=False)}

TOP 5 LOSING TRADES:
{df.nsmallest(5, 'pnl')[['symbol', 'entry_time', 'pnl', 'pips']].to_string(index=False)}
"""
    return summary

def send_to_grok(api_key: str, trade_summary: str) -> Optional[str]:
    """
    Send trade summary to Grok for AI analysis.

    Args:
        api_key: Grok API key
        trade_summary: Trade summary text

    Returns:
        AI analysis response or None if failed
    """
    if not api_key or api_key.strip() == "":
        return None

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        prompt = f"""Analyze the following trading performance data and provide actionable insights.

Focus on:
1. What trading patterns are working well?
2. What patterns are causing losses?
3. Specific recommendations to improve performance
4. Risk management observations
5. Optimal trading times based on the data

{trade_summary}

Provide your analysis in a clear, actionable format."""

        data = {
            "model": "grok-beta",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.7,
        }

        response = requests.post(
            GROK_API_URL,
            headers=headers,
            json=data,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "No response received.")

    except Exception as e:
        return f"Error communicating with Grok: {str(e)}"

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_metric_card(label: str, value: str, color: str = NEON_COLORS["primary"]) -> None:
    """
    Render a neon-styled metric card.

    Args:
        label: Metric label
        value: Metric value
        color: Neon color to use
    """
    st.markdown(f"""
    <div style="
        border: 2px solid {color};
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        background-color: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.05);
        margin: 10px 0;
    ">
        <p style="color: {color}; font-size: 12px; margin: 0; text-transform: uppercase; letter-spacing: 2px;">
            {label}
        </p>
        <p style="color: {color}; font-size: 28px; margin: 10px 0 0 0; font-weight: bold;">
            {value}
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_trade_table(df: pd.DataFrame) -> None:
    """
    Render interactive trade table with color coding.

    Args:
        df: DataFrame of trades
    """
    if df.empty:
        st.info("No trades to display.")
        return

    display_df = df[[
        "ticket", "symbol", "type", "entry_time", "volume",
        "entry_price", "close_price", "pips", "pnl"
    ]].copy()

    display_df = display_df.sort_values("entry_time", ascending=False)
    display_df["entry_time"] = display_df["entry_time"].dt.strftime("%Y-%m-%d %H:%M")
    display_df["entry_price"] = display_df["entry_price"].apply(lambda x: f"{x:.5f}")
    display_df["close_price"] = display_df["close_price"].apply(lambda x: f"{x:.5f}")
    display_df["pips"] = display_df["pips"].apply(lambda x: f"{x:.1f}")
    display_df["pnl"] = display_df["pnl"].apply(lambda x: f"${x:.2f}")

    # Rename columns for display
    display_df.columns = ["Ticket", "Symbol", "Type", "Entry Time", "Volume", "Entry Price", "Close Price", "Pips", "P&L"]

    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
    )

# ============================================================================
# MAIN RENDER FUNCTION
# ============================================================================

def render_mt5_analysis(
    metaapi_token: str,
    metaapi_account: str,
    grok_api_key: str = ""
) -> None:
    """
    Main function to render the MT5 Trade Analysis page.

    Args:
        metaapi_token: MetaAPI authentication token
        metaapi_account: MetaAPI account ID
        grok_api_key: Grok API key for AI analysis (optional)
    """
    st.set_page_config(
        page_title="MT5 Trade Analysis",
        page_icon="📊",
        layout="wide",
    )

    # Custom CSS for neon styling
    st.markdown(f"""
    <style>
    :root {{
        --primary-color: {NEON_COLORS['primary']};
        --secondary-color: {NEON_COLORS['secondary']};
        --accent-color: {NEON_COLORS['accent']};
    }}

    body {{
        background-color: {NEON_COLORS['background']};
        color: {NEON_COLORS['primary']};
    }}

    .stMetricLabel {{
        color: {NEON_COLORS['accent']};
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: {NEON_COLORS['primary']};
        text-shadow: 0 0 10px {NEON_COLORS['primary']};
    }}
    </style>
    """, unsafe_allow_html=True)

    st.title("🚀 MT5 TRADE ANALYSIS - ARIA")
    st.markdown("---")

    # Check if credentials are provided
    if not metaapi_token or not metaapi_account:
        st.warning("⚠️ MetaAPI credentials not configured")
        st.info("""
        **How to connect your MetaAPI account:**

        1. Sign up at [MetaAPI](https://metaapi.cloud)
        2. Create a new MT5 account connection
        3. Copy your account ID and authentication token
        4. Configure them in the settings panel

        Once connected, you'll see real-time trade analysis with:
        - Live equity curves
        - Performance metrics
        - AI-powered trade insights
        - Advanced analytics
        """)
        return

    # Fetch trade history
    trades, status_msg = fetch_trade_history(metaapi_token, metaapi_account)

    if trades is None:
        st.error(f"❌ {status_msg}")
        return

    if not trades:
        st.info(f"ℹ️ {status_msg}")
        return

    # Process trades
    df = process_trades(trades)
    metrics = calculate_performance_metrics(df)

    st.success(f"✅ {status_msg}")

    # ====================================================================
    # PERFORMANCE OVERVIEW
    # ====================================================================
    st.subheader("📊 Performance Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card(
            "Total Trades",
            str(metrics["total_trades"]),
            NEON_COLORS["primary"]
        )
    with col2:
        color = NEON_COLORS["success"] if metrics["win_rate"] >= 50 else NEON_COLORS["danger"]
        render_metric_card(
            "Win Rate",
            f"{metrics['win_rate']:.1f}%",
            color
        )
    with col3:
        render_metric_card(
            "Profit Factor",
            f"{metrics['profit_factor']:.2f}",
            NEON_COLORS["accent"]
        )
    with col4:
        color = NEON_COLORS["success"] if metrics["total_pnl"] >= 0 else NEON_COLORS["danger"]
        render_metric_card(
            "Total P&L",
            f"${metrics['total_pnl']:.2f}",
            color
        )

    # Additional metrics
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        color = NEON_COLORS["success"] if metrics["best_trade"] >= 0 else NEON_COLORS["danger"]
        render_metric_card(
            "Best Trade",
            f"${metrics['best_trade']:.2f}",
            color
        )
    with col6:
        color = NEON_COLORS["danger"] if metrics["worst_trade"] < 0 else NEON_COLORS["success"]
        render_metric_card(
            "Worst Trade",
            f"${metrics['worst_trade']:.2f}",
            color
        )
    with col7:
        render_metric_card(
            "Avg Win",
            f"${metrics['avg_win']:.2f}",
            NEON_COLORS["success"]
        )
    with col8:
        render_metric_card(
            "Avg Holding Time",
            metrics["avg_holding_time"],
            NEON_COLORS["accent"]
        )

    st.markdown("---")

    # ====================================================================
    # CHARTS
    # ====================================================================
    st.subheader("📈 Trade Analytics")

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.plotly_chart(plot_equity_curve(df), use_container_width=True)

    with chart_col2:
        st.plotly_chart(plot_win_rate_by_day(df), use_container_width=True)

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.plotly_chart(plot_pnl_distribution(df), use_container_width=True)

    with chart_col4:
        st.plotly_chart(plot_win_rate_by_session(df), use_container_width=True)

    st.markdown("---")

    # ====================================================================
    # AI ANALYSIS
    # ====================================================================
    if grok_api_key:
        st.subheader("🤖 ARIA AI Analysis")

        col_btn1, col_btn2 = st.columns([1, 4])

        with col_btn1:
            if st.button("🔮 Ask ARIA", key="analyze_btn"):
                with st.spinner("ARIA is analyzing your trades..."):
                    trade_summary = generate_trade_summary(df, metrics)
                    analysis = send_to_grok(grok_api_key, trade_summary)

                    if analysis:
                        st.markdown(f"""
                        <div style="
                            border: 2px solid {NEON_COLORS['accent']};
                            border-radius: 10px;
                            padding: 20px;
                            background-color: rgba(0, 217, 255, 0.05);
                        ">
                            <h4 style="color: {NEON_COLORS['accent']}; margin-top: 0;">ARIA's Analysis</h4>
                            <p style="color: {NEON_COLORS['primary']}; line-height: 1.6;">
                                {analysis}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

        st.markdown("---")

    # ====================================================================
    # TRADE LOG
    # ====================================================================
    st.subheader("📋 Trade Log")

    # Filters
    col_filter1, col_filter2, col_filter3 = st.columns(3)

    with col_filter1:
        symbol_filter = st.multiselect(
            "Filter by Symbol",
            options=sorted(df["symbol"].unique()),
            default=sorted(df["symbol"].unique())[:5],
            key="symbol_filter"
        )

    with col_filter2:
        type_filter = st.multiselect(
            "Filter by Type",
            options=["BUY", "SELL"],
            default=["BUY", "SELL"],
            key="type_filter"
        )

    with col_filter3:
        result_filter = st.multiselect(
            "Filter by Result",
            options=["Wins", "Losses", "All"],
            default=["All"],
            key="result_filter"
        )

    # Apply filters
    filtered_df = df[
        (df["symbol"].isin(symbol_filter)) &
        (df["type"].isin(type_filter))
    ]

    if "Wins" in result_filter and "Losses" not in result_filter:
        filtered_df = filtered_df[filtered_df["is_win"]]
    elif "Losses" in result_filter and "Wins" not in result_filter:
        filtered_df = filtered_df[~filtered_df["is_win"]]

    # Render table
    render_trade_table(filtered_df)

    st.markdown("---")

    # Footer
    st.markdown(f"""
    <div style="text-align: center; color: {NEON_COLORS['accent']}; opacity: 0.7; margin-top: 40px;">
        <p>📡 MT5 Trade Analysis powered by MetaAPI | 🤖 AI Analysis by ARIA (Grok)</p>
        <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# ENTRY POINT FOR STREAMLIT
# ============================================================================

if __name__ == "__main__":
    # Example usage - in production, these would come from Streamlit secrets
    metaapi_token = st.secrets.get("metaapi_token", "")
    metaapi_account = st.secrets.get("metaapi_account", "")
    grok_api_key = st.secrets.get("grok_api_key", "")

    render_mt5_analysis(metaapi_token, metaapi_account, grok_api_key)
