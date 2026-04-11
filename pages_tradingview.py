"""
TradingView Integration Page for Alpha FX Hub
Professional forex trading app with TradingView charts, trade planning, and AI analysis
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
from typing import Dict, Tuple, Optional
import json

# Symbol mapping for TradingView
SYMBOL_MAP = {
    "XAUUSD": "OANDA:XAUUSD",
    "EURUSD": "OANDA:EURUSD",
    "GBPUSD": "OANDA:GBPUSD",
    "USDJPY": "OANDA:USDJPY",
    "AUDUSD": "OANDA:AUDUSD",
    "NZDUSD": "OANDA:NZDUSD",
    "USDCAD": "OANDA:USDCAD",
    "USDCHF": "OANDA:USDCHF",
    "BTCUSD": "BITSTAMP:BTCUSD",
    "ETHUSD": "BITSTAMP:ETHUSD",
    "SPX500": "SNPINDEX:SPX",
    "US100": "NASDAQ:US100",
}

# Cyberpunk styling
CYBERPUNK_CSS = """
<style>
    :root {
        --dark-bg: #0a0a1a;
        --neon-cyan: #00fff2;
        --neon-pink: #ff006e;
        --neon-green: #00ff41;
        --neon-purple: #b300ff;
    }

    .cyber-container {
        background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 100%);
        border: 2px solid #00fff2;
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.3);
        font-family: 'Courier New', monospace;
    }

    .cyber-header {
        font-family: 'Courier New', monospace;
        color: #00fff2;
        text-shadow: 0 0 10px #00fff2, 0 0 20px #00fff2;
        font-weight: bold;
        font-size: 1.5em;
        margin-bottom: 15px;
        border-bottom: 2px solid #00fff2;
        padding-bottom: 10px;
    }

    .cyber-input {
        background: #0a0a1a !important;
        border: 2px solid #00fff2 !important;
        color: #00fff2 !important;
        border-radius: 5px;
        padding: 10px;
        font-family: 'Courier New', monospace;
        box-shadow: inset 0 0 10px rgba(0, 255, 242, 0.1);
    }

    .cyber-button {
        background: linear-gradient(135deg, #00fff2 0%, #00cc99 100%) !important;
        color: #0a0a1a !important;
        border: 2px solid #00fff2 !important;
        border-radius: 5px;
        font-weight: bold;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5);
        box-shadow: 0 0 15px rgba(0, 255, 242, 0.4);
    }

    .cyber-button:hover {
        box-shadow: 0 0 30px rgba(0, 255, 242, 0.8) !important;
    }

    .risk-reward-box {
        background: linear-gradient(135deg, rgba(0, 255, 242, 0.05) 0%, rgba(179, 0, 255, 0.05) 100%);
        border-left: 4px solid #00fff2;
        border-right: 4px solid #b300ff;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
    }

    .metric-label {
        color: #00fff2;
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .metric-value {
        color: #00ff41;
        font-size: 1.3em;
        font-weight: bold;
        text-shadow: 0 0 10px #00ff41;
    }

    .analysis-result {
        background: linear-gradient(135deg, rgba(0, 255, 242, 0.08) 0%, rgba(0, 255, 65, 0.08) 100%);
        border: 2px solid #00fff2;
        border-radius: 8px;
        padding: 15px;
        margin: 15px 0;
        font-family: 'Courier New', monospace;
        color: #e0e0e0;
        line-height: 1.6;
    }

    .confidence-high {
        color: #00ff41;
        text-shadow: 0 0 10px #00ff41;
    }

    .confidence-medium {
        color: #ffff00;
        text-shadow: 0 0 10px #ffff00;
    }

    .confidence-low {
        color: #ff006e;
        text-shadow: 0 0 10px #ff006e;
    }
</style>
"""


def render_tradingview_chart(symbol: str) -> None:
    """
    Render TradingView Advanced Chart widget
    Uses public embed widget - no authentication needed
    Users can only view the chart, cannot access owner's TradingView account
    """
    tv_symbol = SYMBOL_MAP.get(symbol, symbol)

    tv_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart" style="height:600px;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "15",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#0a0a1a",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    components.html(tv_html, height=620)


def calculate_risk_reward(
    entry: float,
    stop_loss: float,
    tp1: float,
    direction: str,
    lot_size: float,
    risk_amount: float,
) -> Dict:
    """Calculate risk:reward metrics"""

    if direction == "Buy":
        risk_pips = (entry - stop_loss) * 10000
        reward1_pips = (tp1 - entry) * 10000
    else:  # Sell
        risk_pips = (stop_loss - entry) * 10000
        reward1_pips = (entry - tp1) * 10000

    if risk_pips <= 0:
        return {
            "valid": False,
            "error": "Invalid stop loss placement",
            "risk_pips": 0,
            "reward_pips": 0,
            "ratio": 0,
            "potential_profit": 0,
            "potential_loss": 0,
        }

    ratio = reward1_pips / risk_pips if risk_pips > 0 else 0

    potential_loss = risk_amount
    potential_profit = risk_amount * ratio

    return {
        "valid": True,
        "error": None,
        "risk_pips": round(risk_pips, 1),
        "reward_pips": round(reward1_pips, 1),
        "ratio": round(ratio, 2),
        "potential_profit": round(potential_profit, 2),
        "potential_loss": round(potential_loss, 2),
        "lot_size": lot_size,
    }


def get_ai_trade_analysis(trade_plan: Dict, grok_api_key: str) -> Optional[str]:
    """
    Call Grok API to analyze trade plan against market structure
    Uses grok-3-mini-fast for quick analysis
    """

    if not grok_api_key or grok_api_key.strip() == "":
        return "⚠️ Grok API key not configured. Add it in sidebar to enable AI analysis."

    system_prompt = """You are a professional forex and crypto analyst with 15+ years of experience.
Analyze trade plans for:
1. Entry alignment with key levels and support/resistance
2. Trade direction matching current trend structure
3. Risk:Reward ratio acceptability (aim for 1:2 minimum)
4. Potential news events that could impact the trade
5. Overall confidence score (1-10)

Provide structured analysis with clear recommendations."""

    user_content = f"""
Analyze this trade plan:
- Symbol: {trade_plan['symbol']}
- Direction: {trade_plan['direction']}
- Entry Price: {trade_plan['entry']}
- Stop Loss: {trade_plan['stop_loss']}
- Take Profit: {trade_plan['tp1']}
- Lot Size: {trade_plan['lot_size']}
- Risk Amount: ${trade_plan['risk_amount']}
- Risk:Reward Ratio: {trade_plan['ratio']}

Provide brief, actionable analysis."""

    headers = {
        "Authorization": f"Bearer {grok_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": st.session_state.get("grok_model", "grok-4-1-fast-non-reasoning"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 600,
        "temperature": 0.3,
    }

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=25,
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "⚠️ Could not connect to Grok API. Check your internet connection."
    except requests.exceptions.Timeout:
        return "⚠️ Grok API request timed out. Try again."
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "⚠️ Invalid Grok API key. Check your credentials."
        elif response.status_code == 429:
            return "⚠️ Rate limited. Wait a moment and try again."
        return f"⚠️ API Error: {e}"
    except KeyError:
        return "⚠️ Unexpected response format from Grok API."
    except Exception as e:
        return f"⚠️ Error analyzing trade: {str(e)}"


def get_confidence_color(score: int) -> str:
    """Return CSS class for confidence score coloring"""
    if score >= 7:
        return "confidence-high"
    elif score >= 5:
        return "confidence-medium"
    else:
        return "confidence-low"


def render_tradingview_page(grok_api_key: str) -> None:
    """
    Main function to render the TradingView trading page
    Args:
        grok_api_key: API key for Grok AI analysis
    """

    # Apply cyberpunk styling
    st.markdown(CYBERPUNK_CSS, unsafe_allow_html=True)

    # Page header
    st.markdown(
        """
        <h1 style="color: #00fff2; text-shadow: 0 0 20px #00fff2; text-align: center; font-family: 'Courier New', monospace; margin-bottom: 30px;">
        ⚡ TRADINGVIEW PRO TERMINAL ⚡
        </h1>
        """,
        unsafe_allow_html=True,
    )

    # Create two columns for layout
    chart_col, sidebar_col = st.columns([3, 1])

    with sidebar_col:
        st.markdown(
            '<div class="cyber-header">⚙️ SETTINGS</div>',
            unsafe_allow_html=True,
        )

        selected_symbol = st.selectbox(
            "📊 Select Symbol",
            options=list(SYMBOL_MAP.keys()),
            index=1,  # Default to EURUSD
            key="symbol_select",
        )

    with chart_col:
        # Section 1: TradingView Chart Widget
        st.markdown(
            '<div class="cyber-header">📈 LIVE MARKET FEED</div>',
            unsafe_allow_html=True,
        )
        render_tradingview_chart(selected_symbol)

    # Section 2: Trade Plan Builder
    st.markdown(
        '<div class="cyber-header">🎯 TRADE PLAN BUILDER</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="cyber-container">', unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        with col1:
            direction = st.radio(
                "Direction",
                ["Buy", "Sell"],
                horizontal=True,
                key="direction_radio",
            )

        with col2:
            entry_price = st.number_input(
                "Entry Price",
                min_value=0.0,
                value=1.0950,
                step=0.0001,
                format="%.4f",
                key="entry_input",
            )

        with col3:
            stop_loss = st.number_input(
                "Stop Loss",
                min_value=0.0,
                value=1.0900,
                step=0.0001,
                format="%.4f",
                key="sl_input",
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            tp1 = st.number_input(
                "Take Profit 1",
                min_value=0.0,
                value=1.1000,
                step=0.0001,
                format="%.4f",
                key="tp1_input",
            )

        with col5:
            tp2 = st.number_input(
                "Take Profit 2 (Optional)",
                min_value=0.0,
                value=1.1050,
                step=0.0001,
                format="%.4f",
                key="tp2_input",
            )

        with col6:
            lot_size = st.number_input(
                "Lot Size",
                min_value=0.01,
                value=1.0,
                step=0.01,
                format="%.2f",
                key="lot_input",
            )

        col7, col8 = st.columns(2)

        with col7:
            risk_amount = st.number_input(
                "Risk Amount ($)",
                min_value=1.0,
                value=50.0,
                step=1.0,
                format="%.2f",
                key="risk_input",
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # Real-time Risk:Reward Calculation
    if entry_price > 0 and stop_loss > 0 and tp1 > 0:
        rr_calc = calculate_risk_reward(
            entry_price, stop_loss, tp1, direction, lot_size, risk_amount
        )

        st.markdown(
            '<div class="cyber-header">📊 RISK:REWARD ANALYSIS</div>',
            unsafe_allow_html=True,
        )

        if rr_calc["valid"]:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(
                    f"""
                    <div class="risk-reward-box">
                    <div class="metric-label">Risk Pips</div>
                    <div class="metric-value">{rr_calc['risk_pips']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown(
                    f"""
                    <div class="risk-reward-box">
                    <div class="metric-label">Reward Pips</div>
                    <div class="metric-value">{rr_calc['reward_pips']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col3:
                ratio_color = "#00ff41" if rr_calc["ratio"] >= 2 else "#ffff00" if rr_calc["ratio"] >= 1 else "#ff006e"
                st.markdown(
                    f"""
                    <div class="risk-reward-box">
                    <div class="metric-label">R:R Ratio</div>
                    <div class="metric-value" style="color: {ratio_color};">1:{rr_calc['ratio']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col4:
                profit_color = "#00ff41" if rr_calc["ratio"] >= 2 else "#ffff00"
                st.markdown(
                    f"""
                    <div class="risk-reward-box">
                    <div class="metric-label">Potential Profit</div>
                    <div class="metric-value" style="color: {profit_color};">${rr_calc['potential_profit']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Store trade plan in session state for analysis
            st.session_state.current_trade = {
                "symbol": selected_symbol,
                "direction": direction,
                "entry": entry_price,
                "stop_loss": stop_loss,
                "tp1": tp1,
                "tp2": tp2,
                "lot_size": lot_size,
                "risk_amount": risk_amount,
                "ratio": rr_calc["ratio"],
            }
        else:
            st.error(f"⚠️ {rr_calc['error']}")

    # Section 3: AI Structure Analysis
    st.markdown(
        '<div class="cyber-header">🤖 AI MARKET STRUCTURE ANALYSIS</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            analyze_clicked = st.button(
                "🔍 Analyze My Trade Plan",
                use_container_width=True,
                key="analyze_btn",
            )

        with col2:
            refresh_clicked = st.button(
                "🔄 Refresh",
                use_container_width=True,
                key="refresh_btn",
            )

        with col3:
            clear_clicked = st.button(
                "✖️ Clear",
                use_container_width=True,
                key="clear_btn",
            )

    # Perform analysis
    if analyze_clicked and hasattr(st.session_state, "current_trade"):
        with st.spinner("⚡ Analyzing trade structure with AI..."):
            analysis = get_ai_trade_analysis(
                st.session_state.current_trade, grok_api_key
            )

            if analysis:
                st.session_state.last_analysis = analysis

    # Display analysis results
    if hasattr(st.session_state, "last_analysis") and st.session_state.last_analysis:
        st.markdown(
            '<div class="analysis-result">',
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state.last_analysis)
        st.markdown('</div>', unsafe_allow_html=True)

    # Clear analysis if button clicked
    if clear_clicked:
        st.session_state.last_analysis = None
        st.rerun()

    # Footer
    st.markdown(
        """
        <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #00fff2; text-align: center; color: #00fff2; font-family: 'Courier New', monospace; font-size: 0.85em;">
        <p>⚡ ALPHA FX HUB TRADINGVIEW PRO TERMINAL ⚡</p>
        <p style="color: #888; font-size: 0.75em; margin-top: 10px;">
        Chart widget provided by TradingView • Account data secured • Grok AI Analysis
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    # This allows the page to be run directly
    grok_key = st.sidebar.text_input(
        "🔐 Grok API Key",
        type="password",
        help="Your X.AI Grok API key for trade analysis",
    )
    render_tradingview_page(grok_key)
