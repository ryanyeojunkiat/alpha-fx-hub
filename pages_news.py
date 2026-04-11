"""
News Dashboard for Alpha FX Hub - Streamlit Trading App
Provides real-time market news, economic calendar, sentiment analysis, and custom news search
using Grok API with aggressive caching and cyberpunk styling.
"""

import streamlit as st
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time


# ============================================================================
# CYBERPUNK STYLING
# ============================================================================

CYBERPUNK_CSS = """
<style>
    .neon-card {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 100%);
        border: 2px solid #00ff88;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.3), inset 0 0 20px rgba(0, 255, 136, 0.1);
    }

    .neon-card-pink {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 100%);
        border: 2px solid #ff006e;
        border-radius: 8px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 0 20px rgba(255, 0, 110, 0.3), inset 0 0 20px rgba(255, 0, 110, 0.1);
    }

    .neon-title {
        color: #00ff88;
        text-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
        font-size: 24px;
        font-weight: bold;
        margin: 20px 0 10px 0;
    }

    .neon-subtitle {
        color: #00d4ff;
        text-shadow: 0 0 8px #00d4ff;
        font-size: 16px;
        margin: 10px 0;
    }

    .sentiment-gauge {
        width: 100%;
        height: 30px;
        background: linear-gradient(90deg, #ff006e 0%, #ffbe0b 50%, #00ff88 100%);
        border-radius: 15px;
        box-shadow: 0 0 15px rgba(0, 255, 136, 0.5);
        margin: 15px 0;
        position: relative;
    }

    .sentiment-indicator {
        position: absolute;
        width: 4px;
        height: 100%;
        background: #ffffff;
        box-shadow: 0 0 10px #ffffff;
        border-radius: 2px;
        top: 0;
    }

    .event-high {
        background: linear-gradient(135deg, #1a0015 0%, #2d0a30 100%);
        border-left: 4px solid #ff006e;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
        box-shadow: 0 0 15px rgba(255, 0, 110, 0.2);
    }

    .event-medium {
        background: linear-gradient(135deg, #1a1500 0%, #2d1a00 100%);
        border-left: 4px solid #ffbe0b;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
        box-shadow: 0 0 15px rgba(255, 190, 11, 0.2);
    }

    .event-low {
        background: linear-gradient(135deg, #001a0f 0%, #002d20 100%);
        border-left: 4px solid #00ff88;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
        box-shadow: 0 0 15px rgba(0, 255, 136, 0.2);
    }

    .search-response {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 100%);
        border: 1px solid #00d4ff;
        border-radius: 6px;
        padding: 15px;
        margin: 10px 0;
        color: #00d4ff;
        line-height: 1.6;
    }

    .loading-text {
        color: #00ff88;
        text-shadow: 0 0 10px #00ff88;
        font-weight: bold;
    }
</style>
"""


# ============================================================================
# GROK API UTILITIES
# ============================================================================

def call_grok_api(prompt: str, api_key: str, model: str = "grok-3-mini-fast") -> Optional[str]:
    """
    Call Grok API with the provided prompt.

    Args:
        prompt: The prompt to send to Grok
        api_key: X.AI API key for Grok
        model: Model to use (default: grok-3-mini-fast)

    Returns:
        Response text from Grok, or None if request fails
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "model": model,
            "stream": False,
            "temperature": 0.7
        }

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            st.error(f"Grok API Error {response.status_code}: {response.text}")
            return None

    except requests.exceptions.Timeout:
        st.error("Grok API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Grok API request failed: {str(e)}")
        return None
    except json.JSONDecodeError:
        st.error("Failed to parse Grok API response")
        return None


# ============================================================================
# CACHED FUNCTIONS FOR API CALLS
# ============================================================================

@st.cache_data(ttl=1800)  # 30 minutes cache
def get_daily_news_summary(grok_api_key: str) -> str:
    """
    Generate a daily market news summary covering key categories.
    Cached for 30 minutes to avoid excessive API calls.
    """
    prompt = """Provide a concise daily market news summary (max 300 words) covering:

1. FOREX: Major currency movements and key pairs
2. GOLD/COMMODITIES: Recent price action and drivers
3. GEOPOLITICS: Wars, sanctions, political developments affecting markets
4. CENTRAL BANKS: Policy decisions, statements, interest rate expectations
5. ECONOMIC DATA: Today's key economic releases and impacts

Format each category clearly with a heading. Be concise and market-focused."""

    return call_grok_api(prompt, grok_api_key) or "Unable to fetch daily summary at this time"


@st.cache_data(ttl=1800)  # 30 minutes cache
def get_economic_calendar_grok(grok_api_key: str) -> str:
    """
    Generate today's key economic events using Grok.
    Cached for 30 minutes.
    """
    prompt = """Generate today's key economic calendar events in this exact format:

For each event, use this format on a new line:
[HH:MM UTC] | Event Name | Currency | Importance

Where Importance is: HIGH, MEDIUM, or LOW

Include at least 8 events. Be realistic about actual today's economic calendar.
Only include the events list, no other text."""

    return call_grok_api(prompt, grok_api_key) or "Unable to fetch economic calendar"


@st.cache_data(ttl=1800)  # 30 minutes cache
def get_market_sentiment(grok_api_key: str) -> Dict[str, Any]:
    """
    Analyze current market sentiment.
    Cached for 30 minutes.
    Returns dict with 'sentiment' (bullish/neutral/bearish), 'position' (0-100), and 'drivers'
    """
    prompt = """Analyze current global market sentiment and provide:

1. Overall sentiment: Choose ONE of: BULLISH, NEUTRAL, or BEARISH
2. Sentiment score: A number from 0 (extremely bearish) to 100 (extremely bullish), where 50 is neutral
3. Key drivers: List 3-4 key market drivers in 1-2 sentences each

Format your response as:
SENTIMENT: [bullish/neutral/bearish]
SCORE: [0-100]
DRIVERS:
- Driver 1 description
- Driver 2 description
- Driver 3 description"""

    response = call_grok_api(prompt, grok_api_key)

    if not response:
        return {
            "sentiment": "NEUTRAL",
            "position": 50,
            "drivers": ["Unable to fetch sentiment data"]
        }

    # Parse response
    lines = response.strip().split('\n')
    sentiment = "NEUTRAL"
    position = 50
    drivers = []

    try:
        for line in lines:
            if line.startswith("SENTIMENT:"):
                sentiment = line.split(":", 1)[1].strip().upper()
            elif line.startswith("SCORE:"):
                try:
                    position = int(line.split(":", 1)[1].strip())
                    position = max(0, min(100, position))
                except:
                    position = 50
            elif line.startswith("- "):
                drivers.append(line[2:].strip())
    except:
        pass

    return {
        "sentiment": sentiment,
        "position": position,
        "drivers": drivers if drivers else ["Market analysis unavailable"]
    }


@st.cache_data(ttl=600)  # 10 minutes cache for search queries
def search_news_topic(query: str, grok_api_key: str) -> str:
    """
    Search for analysis on a specific news topic.
    Cached for 10 minutes to allow repeated queries on same topic.
    """
    prompt = f"""Provide a brief market analysis (150-200 words) on: {query}

Focus on:
- Current situation and recent developments
- Impact on forex, commodities, or equities markets
- Key risks and opportunities
- What traders should watch

Be concise and actionable."""

    return call_grok_api(prompt, grok_api_key) or "Unable to fetch topic analysis"


# ============================================================================
# RENDERING FUNCTIONS
# ============================================================================

def render_daily_news_summary(grok_api_key: str):
    """Render the Daily News Summary section."""
    st.markdown("<div class='neon-title'>📰 Daily News Summary</div>", unsafe_allow_html=True)
    st.markdown("<div class='neon-subtitle'>Market overview across key categories</div>", unsafe_allow_html=True)

    with st.spinner("Fetching daily market news..."):
        summary = get_daily_news_summary(grok_api_key)

    st.markdown(f"""
    <div class='neon-card'>
        {summary.replace(chr(10), '<br>')}
    </div>
    """, unsafe_allow_html=True)


def render_economic_calendar(grok_api_key: str, te_api_key: str = ""):
    """Render the Economic Calendar section."""
    st.markdown("<div class='neon-title'>📅 Economic Calendar</div>", unsafe_allow_html=True)

    if te_api_key:
        st.markdown("<div class='neon-subtitle'>Powered by Trading Economics API</div>", unsafe_allow_html=True)
        # TODO: Implement Trading Economics API integration when API key is available
        st.info("Trading Economics API integration available with valid API key")
    else:
        st.markdown("<div class='neon-subtitle'>Powered by Grok AI</div>", unsafe_allow_html=True)

    with st.spinner("Fetching economic calendar..."):
        events_text = get_economic_calendar_grok(grok_api_key)

    # Parse and render events with color coding
    st.markdown("<div class='neon-card'>", unsafe_allow_html=True)

    lines = events_text.strip().split('\n')
    for line in lines:
        if line.strip() and '|' in line:
            try:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    time_str = parts[0]
                    event_name = parts[1]
                    currency = parts[2]
                    importance = parts[3].upper()

                    # Determine styling based on importance
                    if importance == "HIGH":
                        css_class = "event-high"
                    elif importance == "MEDIUM":
                        css_class = "event-medium"
                    else:
                        css_class = "event-low"

                    st.markdown(f"""
                    <div class='{css_class}'>
                        <strong>{time_str}</strong> | {event_name} | <span style='color: #00d4ff'>{currency}</span> | {importance}
                    </div>
                    """, unsafe_allow_html=True)
            except:
                st.markdown(f"<div style='color: #00d4ff; margin: 8px 0;'>{line}</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_market_sentiment(grok_api_key: str):
    """Render the Market Sentiment section."""
    st.markdown("<div class='neon-title'>📊 Market Sentiment</div>", unsafe_allow_html=True)
    st.markdown("<div class='neon-subtitle'>Current market sentiment analysis</div>", unsafe_allow_html=True)

    with st.spinner("Analyzing market sentiment..."):
        sentiment_data = get_market_sentiment(grok_api_key)

    sentiment = sentiment_data["sentiment"]
    position = sentiment_data["position"]
    drivers = sentiment_data["drivers"]

    # Determine sentiment color
    if sentiment == "BULLISH":
        sentiment_color = "#00ff88"
        sentiment_emoji = "📈"
    elif sentiment == "BEARISH":
        sentiment_color = "#ff006e"
        sentiment_emoji = "📉"
    else:
        sentiment_color = "#ffbe0b"
        sentiment_emoji = "➡️"

    st.markdown(f"""
    <div class='neon-card'>
        <div style='text-align: center; margin-bottom: 15px;'>
            <span style='color: {sentiment_color}; font-size: 28px; text-shadow: 0 0 10px {sentiment_color};'>
                {sentiment_emoji} {sentiment}
            </span>
        </div>

        <div class='sentiment-gauge'>
            <div class='sentiment-indicator' style='left: {position}%;'></div>
        </div>

        <div style='text-align: center; color: #00d4ff; margin-bottom: 15px;'>
            Sentiment Score: <strong>{position}/100</strong>
        </div>

        <div style='color: #00ff88;'>
            <strong>Key Drivers:</strong>
        </div>
    """, unsafe_allow_html=True)

    for driver in drivers:
        st.markdown(f"""
        <div style='color: #00d4ff; margin: 8px 0; padding-left: 15px;'>
            • {driver}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_news_search(grok_api_key: str):
    """Render the News Search section."""
    st.markdown("<div class='neon-title'>🔍 News Search & Analysis</div>", unsafe_allow_html=True)
    st.markdown("<div class='neon-subtitle'>Ask about specific market topics or news</div>", unsafe_allow_html=True)

    # Use session state to manage search input and history
    if "search_queries" not in st.session_state:
        st.session_state.search_queries = []

    search_query = st.text_input(
        "Search for market news or analysis:",
        placeholder="e.g., Iran war latest impact on oil, Fed rate decision effect on gold...",
        key="news_search_input"
    )

    col1, col2 = st.columns([4, 1])

    with col1:
        search_submitted = st.button("Search", key="search_button")

    with col2:
        clear_cache = st.button("Clear Cache", key="clear_cache_button")

    if clear_cache:
        get_daily_news_summary.clear()
        get_economic_calendar_grok.clear()
        get_market_sentiment.clear()
        search_news_topic.clear()
        st.success("Cache cleared! Next queries will fetch fresh data.")
        st.rerun()

    if search_submitted and search_query.strip():
        with st.spinner(f"Analyzing: {search_query}..."):
            result = search_news_topic(search_query, grok_api_key)

        st.markdown(f"""
        <div class='search-response'>
            <strong>Query:</strong> {search_query}<br><br>
            {result.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)


# ============================================================================
# MAIN DASHBOARD FUNCTION
# ============================================================================

def render_news_dashboard(grok_api_key: str, te_api_key: str = ""):
    """
    Main News Dashboard renderer for Alpha FX Hub.

    Args:
        grok_api_key: API key for Grok (X.AI)
        te_api_key: Optional API key for Trading Economics
    """
    # Apply cyberpunk styling
    st.markdown(CYBERPUNK_CSS, unsafe_allow_html=True)

    # Validate API key
    if not grok_api_key or not grok_api_key.strip():
        st.error("❌ Grok API key is required. Please provide a valid X.AI API key.")
        st.info("Get your API key from: https://console.x.ai")
        return

    # Main title
    st.markdown("""
    <div style='text-align: center; margin-bottom: 30px;'>
        <div style='color: #00ff88; font-size: 32px; text-shadow: 0 0 20px #00ff88; font-weight: bold;'>
            🌍 ALPHA FX HUB - NEWS DASHBOARD
        </div>
        <div style='color: #00d4ff; font-size: 14px; margin-top: 10px;'>
            Real-time market intelligence powered by Grok AI
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Create tabs for organized layout
    tab1, tab2, tab3, tab4 = st.tabs(["📰 News", "📅 Calendar", "📊 Sentiment", "🔍 Search"])

    with tab1:
        st.markdown("---")
        render_daily_news_summary(grok_api_key)

    with tab2:
        st.markdown("---")
        render_economic_calendar(grok_api_key, te_api_key)

    with tab3:
        st.markdown("---")
        render_market_sentiment(grok_api_key)

    with tab4:
        st.markdown("---")
        render_news_search(grok_api_key)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #00d4ff; font-size: 12px; margin-top: 20px;'>
        💾 Data cached aggressively to reduce API calls | Last updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC") + """
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# STREAMLIT PAGE CONFIGURATION (if running directly)
# ============================================================================

if __name__ == "__main__":
    st.set_page_config(
        page_title="Alpha FX Hub - News Dashboard",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Example usage with API keys from Streamlit secrets
    grok_key = st.secrets.get("grok_api_key", "")
    te_key = st.secrets.get("trading_economics_api_key", "")

    render_news_dashboard(grok_key, te_key)
