"""
Grok AI Chat Interface for Alpha FX Hub Trading Platform
Provides ARIA - the AI assistant for trading strategy, market analysis, and news summarization
"""

import streamlit as st
import requests
import json
from typing import Optional
from datetime import datetime


# ============================================================================
# CHAT RENDERING FUNCTION
# ============================================================================

def render_grok_chat(grok_api_key: str) -> None:
    """
    Render the Grok AI chat interface for Alpha FX Hub.

    Features:
    - Cyberpunk-styled chat UI with neon message bubbles
    - Session-based conversation history
    - Real-time typing indicators
    - Error handling and graceful degradation

    Args:
        grok_api_key: xAI Grok API key for authentication
    """

    # Initialize session state for conversation history
    if "grok_messages" not in st.session_state:
        st.session_state.grok_messages = []

    if "grok_loading" not in st.session_state:
        st.session_state.grok_loading = False

    # Cyberpunk CSS styling
    cyberpunk_css = """
    <style>
    .grok-chat-container {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
        border: 2px solid #00ffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 0 20px rgba(0, 255, 255, 0.3), inset 0 0 20px rgba(0, 255, 255, 0.05);
        font-family: 'Courier New', monospace;
    }

    .grok-messages-area {
        max-height: 500px;
        overflow-y: auto;
        margin-bottom: 20px;
        padding: 15px;
        background: rgba(0, 20, 40, 0.8);
        border: 1px solid #00ffff;
        border-radius: 8px;
        box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.1);
    }

    .grok-message {
        margin-bottom: 15px;
        animation: slideIn 0.3s ease-out;
    }

    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .grok-message-user {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 15px;
    }

    .grok-message-user .message-bubble {
        background: linear-gradient(135deg, #00ffff, #00cc99);
        color: #000;
        padding: 12px 16px;
        border-radius: 12px;
        max-width: 70%;
        word-wrap: break-word;
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.5), 0 0 30px rgba(0, 204, 153, 0.3);
        border: 1px solid rgba(0, 255, 255, 0.8);
        font-weight: 600;
    }

    .grok-message-assistant {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 15px;
    }

    .grok-message-assistant .message-bubble {
        background: linear-gradient(135deg, rgba(255, 0, 127, 0.2), rgba(255, 0, 255, 0.2));
        color: #00ffff;
        padding: 12px 16px;
        border-radius: 12px;
        max-width: 70%;
        word-wrap: break-word;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.4), 0 0 30px rgba(255, 0, 255, 0.2);
        border: 1px solid rgba(255, 0, 127, 0.6);
    }

    .message-timestamp {
        font-size: 0.75rem;
        opacity: 0.6;
        margin-top: 5px;
        text-align: right;
    }

    .grok-typing-indicator {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 12px 16px;
        background: linear-gradient(135deg, rgba(255, 0, 127, 0.2), rgba(255, 0, 255, 0.2));
        border: 1px solid rgba(255, 0, 127, 0.6);
        border-radius: 12px;
        width: fit-content;
        box-shadow: 0 0 15px rgba(255, 0, 127, 0.4);
    }

    .grok-typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #00ffff;
        animation: typing 1.4s infinite;
    }

    .grok-typing-dot:nth-child(2) {
        animation-delay: 0.2s;
    }

    .grok-typing-dot:nth-child(3) {
        animation-delay: 0.4s;
    }

    @keyframes typing {
        0%, 60%, 100% {
            opacity: 0.5;
            transform: translateY(0);
        }
        30% {
            opacity: 1;
            transform: translateY(-10px);
        }
    }

    .grok-input-container {
        display: flex;
        gap: 10px;
        margin-top: 20px;
    }

    .grok-input-field {
        flex: 1;
        padding: 12px 16px;
        background: rgba(0, 20, 40, 0.9);
        border: 2px solid #00ffff;
        border-radius: 8px;
        color: #00ffff;
        font-family: 'Courier New', monospace;
        font-size: 14px;
        box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.1);
        transition: all 0.3s ease;
    }

    .grok-input-field:focus {
        outline: none;
        box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2), 0 0 20px rgba(0, 255, 255, 0.3);
        border-color: #00ffff;
    }

    .grok-send-button {
        padding: 12px 24px;
        background: linear-gradient(135deg, #00ffff, #00cc99);
        color: #000;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        cursor: pointer;
        box-shadow: 0 0 15px rgba(0, 255, 255, 0.5);
        transition: all 0.3s ease;
    }

    .grok-send-button:hover {
        box-shadow: 0 0 25px rgba(0, 255, 255, 0.8), 0 0 40px rgba(0, 204, 153, 0.4);
        transform: translateY(-2px);
    }

    .grok-send-button:active {
        transform: translateY(0);
    }

    .grok-error-message {
        background: linear-gradient(135deg, rgba(255, 0, 0, 0.2), rgba(255, 100, 100, 0.2));
        border: 1px solid rgba(255, 0, 0, 0.6);
        color: #ff6464;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 0 0 15px rgba(255, 0, 0, 0.3);
        font-weight: 600;
    }

    .grok-header {
        color: #00ffff;
        text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        margin-bottom: 15px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    </style>
    """

    # Render CSS
    st.markdown(cyberpunk_css, unsafe_allow_html=True)

    # Header
    st.markdown(
        '<div class="grok-header">⚡ ARIA - Alpha FX Trading Assistant</div>',
        unsafe_allow_html=True
    )

    # Chat container
    st.markdown('<div class="grok-chat-container">', unsafe_allow_html=True)

    # Messages display area
    st.markdown('<div class="grok-messages-area">', unsafe_allow_html=True)

    # Display conversation history
    for message in st.session_state.grok_messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = message.get("timestamp", "")

        if role == "user":
            st.markdown(
                f'''
                <div class="grok-message grok-message-user">
                    <div>
                        <div class="message-bubble">{content}</div>
                        <div class="message-timestamp">{timestamp}</div>
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'''
                <div class="grok-message grok-message-assistant">
                    <div>
                        <div class="message-bubble">{content}</div>
                        <div class="message-timestamp">{timestamp}</div>
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

    # Show typing indicator if loading
    if st.session_state.grok_loading:
        st.markdown(
            '''
            <div class="grok-message grok-message-assistant">
                <div class="grok-typing-indicator">
                    <div class="grok-typing-dot"></div>
                    <div class="grok-typing-dot"></div>
                    <div class="grok-typing-dot"></div>
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)  # Close messages area

    # Input area
    col1, col2 = st.columns([0.9, 0.1])

    with col1:
        user_input = st.text_input(
            "Your message",
            placeholder="Ask about trading strategies, market news, or chart analysis...",
            label_visibility="collapsed"
        )

    with col2:
        send_button = st.button("Send", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)  # Close chat container

    # Handle user message
    if send_button and user_input and not st.session_state.grok_loading:
        # Add user message to history
        st.session_state.grok_messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M")
        })

        # Set loading state
        st.session_state.grok_loading = True
        st.rerun()

    # Get response from Grok if loading
    if st.session_state.grok_loading and st.session_state.grok_messages:
        last_message = st.session_state.grok_messages[-1]

        if last_message["role"] == "user":
            # Call Grok API
            response = _call_grok_api(
                grok_api_key,
                last_message["content"],
                st.session_state.grok_messages[:-1]  # Exclude current user message from history
            )

            # Add assistant response
            st.session_state.grok_messages.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().strftime("%H:%M")
            })

            # Clear loading state
            st.session_state.grok_loading = False
            st.rerun()


def _call_grok_api(
    api_key: str,
    user_message: str,
    message_history: list
) -> str:
    """
    Call the Grok API (xAI) with proper error handling.

    Args:
        api_key: xAI API key
        user_message: Current user message
        message_history: Previous messages in conversation

    Returns:
        Response from Grok or error message
    """

    system_prompt = """You are ARIA, the AI Assistant for the Alpha FX Hub trading platform.
You are an expert in foreign exchange (FX) trading and financial markets.

Your capabilities include:
- Analyzing financial news and summarizing market-moving events
- Discussing and explaining various trading strategies
- Helping analyze price charts and technical analysis patterns
- Answering general questions about trading, FX markets, and finance
- Assisting with any other task the user asks for

You communicate in a friendly but professional manner. You provide accurate, helpful information
and always acknowledge when you're uncertain about something. You never provide guaranteed predictions
or advice that could lead to financial loss. You emphasize risk management and proper trading practices."""

    # Build messages for API call
    messages = [
        {"role": "user" if msg["role"] == "user" else "assistant", "content": msg["content"]}
        for msg in message_history
    ]
    messages.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": st.session_state.get("grok_model", "grok-4-1-fast-non-reasoning"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content",
                "Error: No response content received from Grok")
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"⚠️ API Error ({response.status_code}): {error_msg}"

    except requests.exceptions.Timeout:
        return "⚠️ Request timeout. Grok took too long to respond. Please try again."
    except requests.exceptions.ConnectionError:
        return "⚠️ Connection error. Unable to reach Grok API. Please check your internet connection."
    except json.JSONDecodeError:
        return "⚠️ Error parsing response from Grok. Please try again."
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"


# ============================================================================
# HELPER FUNCTIONS FOR NEWS AND TRADE ANALYSIS
# ============================================================================

def grok_summarize_news(api_key: str, topic: str) -> str:
    """
    Ask Grok to summarize recent news about a given topic.
    Useful for the news dashboard to provide trading context.

    Args:
        api_key: xAI Grok API key
        topic: Trading topic or currency pair to summarize news for

    Returns:
        News summary from Grok or error message
    """

    user_message = f"""Please provide a brief summary of recent market news and events related to {topic}.

Include:
- Key news events and announcements
- Market impact assessment
- Any upcoming economic data or events
- Sentiment overview for traders

Keep the summary concise (3-5 sentences) but informative."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": st.session_state.get("grok_model", "grok-4-1-fast-non-reasoning"),
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a financial market analyst providing concise news summaries for FX traders."
                    },
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.6,
                "max_tokens": 500
            },
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content",
                "Error: No response from Grok")
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"Error ({response.status_code}): {error_msg}"

    except requests.exceptions.Timeout:
        return "Error: Request timeout while fetching news summary"
    except requests.exceptions.ConnectionError:
        return "Error: Unable to connect to Grok API"
    except Exception as e:
        return f"Error: {str(e)}"


def grok_analyze_trades(api_key: str, trades_data: str) -> str:
    """
    Send trade history to Grok for analysis and feedback.
    Useful for analyzing trading performance and strategy effectiveness.

    Args:
        api_key: xAI Grok API key
        trades_data: Trade history data (formatted as string with trade details)

    Returns:
        Analysis and feedback from Grok or error message
    """

    user_message = f"""Please analyze my recent trades and provide constructive feedback:

{trades_data}

Please provide:
- Overall performance assessment
- Strengths in the trading approach
- Areas for improvement
- Risk management observations
- Any notable patterns in wins/losses
- Suggestions for strategy optimization

Be constructive and focus on learning opportunities."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": st.session_state.get("grok_model", "grok-4-1-fast-non-reasoning"),
                "messages": [
                    {
                        "role": "system",
                        "content": """You are an expert FX trading coach and mentor. You analyze trading records with
a focus on continuous improvement, risk management, and strategy effectiveness. Be analytical,
constructive, and supportive in your feedback."""
                    },
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.6,
                "max_tokens": 1024
            },
            timeout=20
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content",
                "Error: No response from Grok")
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"Error ({response.status_code}): {error_msg}"

    except requests.exceptions.Timeout:
        return "Error: Request timeout while analyzing trades"
    except requests.exceptions.ConnectionError:
        return "Error: Unable to connect to Grok API"
    except Exception as e:
        return f"Error: {str(e)}"
