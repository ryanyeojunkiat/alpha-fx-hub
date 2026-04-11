import streamlit as st
from datetime import datetime

def render_academy():
    """Trading Academy with visual learning modules and cyberpunk styling."""

    # Initialize session state for progress tracking
    if "academy_progress" not in st.session_state:
        st.session_state.academy_progress = {level: False for level in range(1, 8)}

    if "completed_quizzes" not in st.session_state:
        st.session_state.completed_quizzes = set()

    # Cyberpunk styling
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');

    .academy-container {
        font-family: 'Orbitron', monospace;
        background: linear-gradient(135deg, #0a0e27 0%, #16213e 100%);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }

    .academy-header {
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5em;
        font-weight: 900;
        margin-bottom: 10px;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
    }

    .level-card {
        background: linear-gradient(135deg, #1a1f3a 0%, #2a1f5a 100%);
        border: 2px solid #00ff88;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.2), inset 0 0 10px rgba(0, 255, 136, 0.1);
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .level-card:hover {
        box-shadow: 0 0 30px rgba(0, 255, 136, 0.4), inset 0 0 15px rgba(0, 255, 136, 0.2);
        transform: translateX(5px);
    }

    .level-card.completed {
        border-color: #00ff88;
        background: linear-gradient(135deg, #1a3a2a 0%, #2a5a3a 100%);
    }

    .level-title {
        color: #00ff88;
        font-size: 1.4em;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .level-subtitle {
        color: #00d4ff;
        font-size: 0.9em;
        margin-bottom: 12px;
    }

    .lesson-content {
        background: rgba(0, 255, 136, 0.05);
        border-left: 3px solid #00d4ff;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 15px;
    }

    .key-takeaway {
        background: rgba(0, 212, 255, 0.1);
        border-left: 3px solid #00ff88;
        padding: 10px 15px;
        margin: 8px 0;
        border-radius: 4px;
        color: #e0e0e0;
    }

    .quiz-box {
        background: linear-gradient(135deg, #3a1a2a 0%, #5a2a3a 100%);
        border: 2px solid #ff0080;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
    }

    .quiz-title {
        color: #ff0080;
        font-weight: 700;
        margin-bottom: 10px;
    }

    .progress-bar {
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        height: 8px;
        border-radius: 4px;
        margin: 10px 0;
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
    }

    .diagram-container {
        background: rgba(0, 0, 0, 0.3);
        border: 1px dashed #00ff88;
        border-radius: 6px;
        padding: 20px;
        margin: 15px 0;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    .candlestick-bullish {
        display: inline-block;
        position: relative;
        margin: 0 20px;
    }

    .candlestick-bearish {
        display: inline-block;
        position: relative;
        margin: 0 20px;
    }

    .pattern-label {
        text-align: center;
        color: #00d4ff;
        font-weight: 700;
        margin-top: 10px;
    }

    .completion-badge {
        display: inline-block;
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        color: #0a0e27;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 700;
        margin-left: 10px;
    }

    .stat-box {
        background: linear-gradient(135deg, #1a1f3a 0%, #2a1f5a 100%);
        border: 2px solid #00d4ff;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        color: #00ff88;
        font-weight: 700;
        margin: 10px;
        display: inline-block;
        min-width: 150px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="academy-header">⚡ TRADING ACADEMY</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #00d4ff; margin-bottom: 20px; font-size: 0.9em;">Master forex trading from fundamentals to advanced strategies</div>', unsafe_allow_html=True)

    # Progress tracking
    completed = sum(st.session_state.academy_progress.values())
    total = len(st.session_state.academy_progress)
    progress_pct = (completed / total) * 100

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="stat-box">Levels: {completed}/{total}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-box">Progress: {progress_pct:.0f}%</div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-box">Quizzes: {len(st.session_state.completed_quizzes)}</div>', unsafe_allow_html=True)

    # Level 1: Getting Started
    with st.container():
        st.markdown('<div class="level-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([0.95, 0.05])
        with col1:
            st.markdown('<div class="level-title">📚 Level 1: Getting Started</div>', unsafe_allow_html=True)
            st.markdown('<div class="level-subtitle">Foundation: MT5, Forex Basics & Trade Execution</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.academy_progress[1] or st.checkbox("Expand Level 1", key="level1_expand"):
            st.session_state.academy_progress[1] = True

            st.markdown('<div class="lesson-content"><strong>Lesson 1.1: What is Forex Trading?</strong><br>Forex (Foreign Exchange) is the global marketplace where currencies are traded. It operates 24/5 with trillions in daily volume.</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="key-takeaway">• Currency pairs are quoted as BASE/QUOTE (e.g., EUR/USD)</div>
            <div class="key-takeaway">• Forex trades on margin, amplifying both gains and losses</div>
            <div class="key-takeaway">• Market structure: Asian → European → US sessions</div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="lesson-content"><strong>Lesson 1.2: MetaTrader 5 Setup</strong><br>MT5 is the industry-standard platform. Key components:</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="key-takeaway">• Market Watch: View all available pairs</div>
            <div class="key-takeaway">• Charts: Analyze price action in multiple timeframes</div>
            <div class="key-takeaway">• Terminal: Monitor positions, news, and economic calendar</div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="lesson-content"><strong>Lesson 1.3: How to Place a Trade</strong><br>Execute trades with proper risk management:</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="key-takeaway">• BUY (Long): Profit when price goes up</div>
            <div class="key-takeaway">• SELL (Short): Profit when price goes down</div>
            <div class="key-takeaway">• Set Stop Loss and Take Profit BEFORE entering</div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 1</div><p>What does the first currency in a pair (BASE) represent?</p></div>', unsafe_allow_html=True)
            quiz_answer_1 = st.radio("Select answer:", ["The currency being quoted", "The currency being bought/sold", "The reference currency"], key="q1")
            if st.button("Submit Quiz 1.1", key="submit_q1"):
                if quiz_answer_1 == "The currency being bought/sold":
                    st.success("✓ Correct! The base currency is what you're trading.")
                    st.session_state.completed_quizzes.add("level1")
                else:
                    st.error("✗ Incorrect. Try again!")

    # Level 2: Reading Charts
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">📊 Level 2: Reading Charts</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">Candlesticks, Timeframes & Support/Resistance</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[2] or st.checkbox("Expand Level 2", key="level2_expand"):
        st.session_state.academy_progress[2] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 2.1: Candlestick Patterns</strong><br>Each candlestick represents OHLC data in your chosen timeframe:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Open: Price when candle opened</div>
        <div class="key-takeaway">• High: Highest price during the period</div>
        <div class="key-takeaway">• Low: Lowest price during the period</div>
        <div class="key-takeaway">• Close: Price when candle closed</div>
        """, unsafe_allow_html=True)

        # SVG Candlestick diagrams
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="200" height="200" viewBox="0 0 200 200" style="display: inline-block;">
            <!-- Bullish Candlestick -->
            <text x="100" y="20" text-anchor="middle" fill="#00ff88" font-weight="bold">BULLISH</text>
            <line x1="100" y1="30" x2="100" y2="160" stroke="#00ff88" stroke-width="2"/>
            <rect x="80" y="80" width="40" height="70" fill="#00ff88" stroke="#00ff88" stroke-width="2"/>
            <text x="100" y="185" text-anchor="middle" fill="#00d4ff" font-size="12">Close > Open</text>
        </svg>
        """, unsafe_allow_html=True)

        st.markdown("""
        <svg width="200" height="200" viewBox="0 0 200 200" style="display: inline-block;">
            <!-- Bearish Candlestick -->
            <text x="100" y="20" text-anchor="middle" fill="#ff0080" font-weight="bold">BEARISH</text>
            <line x1="100" y1="30" x2="100" y2="160" stroke="#ff0080" stroke-width="2"/>
            <rect x="80" y="60" width="40" height="70" fill="none" stroke="#ff0080" stroke-width="2"/>
            <text x="100" y="185" text-anchor="middle" fill="#00d4ff" font-size="12">Close < Open</text>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 2.2: Timeframes</strong><br>Different timeframes suit different trading styles:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• M1-M5 (Scalping): High frequency, low profit per trade</div>
        <div class="key-takeaway">• M15-H1 (Day Trading): Follow daily trends</div>
        <div class="key-takeaway">• H4-D1 (Swing Trading): Hold for days/weeks</div>
        <div class="key-takeaway">• W1-MN (Position Trading): Long-term trends</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 2.3: Support & Resistance</strong><br>Price levels where buying/selling pressure meets:</div>', unsafe_allow_html=True)

        # Support/Resistance diagram
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="300" height="200" viewBox="0 0 300 200">
            <!-- Resistance line -->
            <line x1="20" y1="50" x2="280" y2="50" stroke="#ff0080" stroke-width="2" stroke-dasharray="5,5"/>
            <text x="290" y="55" fill="#ff0080" font-size="12">RESISTANCE</text>

            <!-- Support line -->
            <line x1="20" y1="150" x2="280" y2="150" stroke="#00ff88" stroke-width="2" stroke-dasharray="5,5"/>
            <text x="290" y="155" fill="#00ff88" font-size="12">SUPPORT</text>

            <!-- Price bouncing -->
            <polyline points="30,80 60,50 90,80 120,50 150,80 180,50 210,80 240,50 270,75" stroke="#00d4ff" stroke-width="2" fill="none"/>
            <text x="150" y="190" text-anchor="middle" fill="#00d4ff" font-size="12">Price bounces off levels</text>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="key-takeaway">• Support: Price floor where buying interest emerges</div>
        <div class="key-takeaway">• Resistance: Price ceiling where selling pressure appears</div>
        <div class="key-takeaway">• Bounce trades: Enter near support (long) or resistance (short)</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 2</div><p>In a bullish candlestick, which is true?</p></div>', unsafe_allow_html=True)
        quiz_answer_2 = st.radio("Select answer:", ["Close < Open", "Close > Open", "High = Low"], key="q2")
        if st.button("Submit Quiz 2.1", key="submit_q2"):
            if quiz_answer_2 == "Close > Open":
                st.success("✓ Correct! Bullish means the close is above the open.")
                st.session_state.completed_quizzes.add("level2")
            else:
                st.error("✗ Incorrect. Try again!")

    # Level 3: Technical Analysis
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">📈 Level 3: Technical Analysis</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">EMA, RSI, MACD & Bollinger Bands Explained</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[3] or st.checkbox("Expand Level 3", key="level3_expand"):
        st.session_state.academy_progress[3] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 3.1: EMA (Exponential Moving Average)</strong><br>Weighted average that emphasizes recent price action:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• EMA 20/50/200: Common periods for trend identification</div>
        <div class="key-takeaway">• Price above EMA = Uptrend, Below = Downtrend</div>
        <div class="key-takeaway">• EMA crossovers signal trend changes</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 3.2: RSI (Relative Strength Index)</strong><br>Momentum oscillator measuring overbought/oversold conditions:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• RSI > 70: Overbought (potential pullback)</div>
        <div class="key-takeaway">• RSI < 30: Oversold (potential bounce)</div>
        <div class="key-takeaway">• RSI divergence: Hidden clues of trend reversal</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 3.3: MACD (Moving Average Convergence Divergence)</strong><br>Trend-following momentum indicator with signal line:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• MACD line (12/26): Difference between two EMAs</div>
        <div class="key-takeaway">• Signal line (9): EMA of MACD</div>
        <div class="key-takeaway">• Histogram: Visual gap showing momentum strength</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 3.4: Bollinger Bands</strong><br>Volatility bands showing overbought/oversold extremes:</div>', unsafe_allow_html=True)

        # Bollinger Bands diagram
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="300" height="200" viewBox="0 0 300 200">
            <!-- Upper band -->
            <line x1="20" y1="40" x2="280" y2="40" stroke="#ff0080" stroke-width="2"/>
            <text x="285" y="45" fill="#ff0080" font-size="11">Upper Band</text>

            <!-- Middle band (SMA) -->
            <line x1="20" y1="100" x2="280" y2="100" stroke="#00d4ff" stroke-width="2"/>
            <text x="285" y="105" fill="#00d4ff" font-size="11">SMA (20)</text>

            <!-- Lower band -->
            <line x1="20" y1="160" x2="280" y2="160" stroke="#00ff88" stroke-width="2"/>
            <text x="285" y="165" fill="#00ff88" font-size="11">Lower Band</text>

            <!-- Price action -->
            <polyline points="30,80 60,50 90,85 120,70 150,95 180,65 210,110 240,90 270,100" stroke="#ffff00" stroke-width="2" fill="none"/>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="key-takeaway">• Price touches upper band: Potentially overbought</div>
        <div class="key-takeaway">• Price touches lower band: Potentially oversold</div>
        <div class="key-takeaway">• Squeeze: Low volatility before big moves</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 3</div><p>What does RSI > 70 typically indicate?</p></div>', unsafe_allow_html=True)
        quiz_answer_3 = st.radio("Select answer:", ["Strong uptrend", "Overbought condition", "Oversold condition"], key="q3")
        if st.button("Submit Quiz 3.1", key="submit_q3"):
            if quiz_answer_3 == "Overbought condition":
                st.success("✓ Correct! High RSI shows potential pullback territory.")
                st.session_state.completed_quizzes.add("level3")
            else:
                st.error("✗ Incorrect. Try again!")

    # Level 4: Price Action
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">🔥 Level 4: Price Action Trading</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">Market Structure, Key Levels & Pattern Recognition</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[4] or st.checkbox("Expand Level 4", key="level4_expand"):
        st.session_state.academy_progress[4] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 4.1: Higher High/Lower Low (HH/HL)</strong><br>Core concept for identifying market structure:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Uptrend: Each swing high is higher, each swing low is higher</div>
        <div class="key-takeaway">• Downtrend: Each swing high is lower, each swing low is lower</div>
        <div class="key-takeaway">• Range: HH meets HL resistance, LL meets LH support</div>
        """, unsafe_allow_html=True)

        # HH/HL diagram
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="300" height="180" viewBox="0 0 300 180">
            <text x="150" y="20" text-anchor="middle" fill="#00ff88" font-weight="bold" font-size="14">UPTREND (HH & HL)</text>
            <polyline points="20,150 50,100 80,120 110,80 140,100 170,60 200,80 230,40 260,70" stroke="#00ff88" stroke-width="2" fill="none"/>
            <circle cx="50" cy="100" r="4" fill="#00ff88"/>
            <text x="50" y="115" text-anchor="middle" fill="#00d4ff" font-size="10">HL</text>
            <circle cx="110" cy="80" r="4" fill="#ff0080"/>
            <text x="110" y="65" text-anchor="middle" fill="#ff0080" font-size="10">HH</text>
            <circle cx="170" cy="60" r="4" fill="#ff0080"/>
            <text x="170" y="45" text-anchor="middle" fill="#ff0080" font-size="10">HH</text>
            <circle cx="80" cy="120" r="3" fill="#00d4ff"/>
            <circle cx="140" cy="100" r="3" fill="#00d4ff"/>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 4.2: Head & Shoulders Pattern</strong><br>Reversal pattern signaling trend exhaustion:</div>', unsafe_allow_html=True)

        # Head and Shoulders diagram
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="300" height="200" viewBox="0 0 300 200">
            <text x="150" y="20" text-anchor="middle" fill="#ff0080" font-weight="bold">HEAD & SHOULDERS</text>
            <!-- Neckline -->
            <line x1="30" y1="140" x2="270" y2="140" stroke="#00d4ff" stroke-width="1" stroke-dasharray="3,3"/>
            <!-- Left shoulder -->
            <polyline points="40,140 60,100 80,140" stroke="#00ff88" stroke-width="2" fill="none"/>
            <!-- Head -->
            <polyline points="80,140 120,60 160,140" stroke="#ff0080" stroke-width="3" fill="none"/>
            <!-- Right shoulder -->
            <polyline points="160,140 200,100 220,140" stroke="#00ff88" stroke-width="2" fill="none"/>
            <!-- Breakdown -->
            <line x1="220" y1="140" x2="260" y2="170" stroke="#ff0080" stroke-width="2" stroke-dasharray="5,5"/>
            <text x="150" y="185" text-anchor="middle" fill="#00d4ff" font-size="12">Neckline breakdow = Sell signal</text>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 4.3: Double Top & Bottom</strong><br>Reversal patterns showing rejection at key levels:</div>', unsafe_allow_html=True)

        # Double Top/Bottom diagrams
        st.markdown('<div class="diagram-container">', unsafe_allow_html=True)
        st.markdown("""
        <svg width="140" height="200" viewBox="0 0 140 200" style="display: inline-block;">
            <text x="70" y="20" text-anchor="middle" fill="#ff0080" font-weight="bold" font-size="12">DOUBLE TOP</text>
            <polyline points="20,120 40,60 60,100 80,60 100,120 120,170" stroke="#ff0080" stroke-width="2" fill="none"/>
            <line x1="40" y1="65" x2="80" y2="65" stroke="#ff0080" stroke-width="1" stroke-dasharray="2,2"/>
            <text x="70" y="185" text-anchor="middle" fill="#00d4ff" font-size="10">Sell Signal</text>
        </svg>
        <svg width="140" height="200" viewBox="0 0 140 200" style="display: inline-block;">
            <text x="70" y="20" text-anchor="middle" fill="#00ff88" font-weight="bold" font-size="12">DOUBLE BOTTOM</text>
            <polyline points="20,60 40,120 60,80 80,120 100,60 120,30" stroke="#00ff88" stroke-width="2" fill="none"/>
            <line x1="40" y1="125" x2="80" y2="125" stroke="#00ff88" stroke-width="1" stroke-dasharray="2,2"/>
            <text x="70" y="185" text-anchor="middle" fill="#00d4ff" font-size="10">Buy Signal</text>
        </svg>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 4</div><p>In an uptrend, what confirms higher quality?</p></div>', unsafe_allow_html=True)
        quiz_answer_4 = st.radio("Select answer:", ["Higher lows only", "Higher highs AND higher lows", "Lower lows"], key="q4")
        if st.button("Submit Quiz 4.1", key="submit_q4"):
            if quiz_answer_4 == "Higher highs AND higher lows":
                st.success("✓ Correct! Both conditions confirm uptrend strength.")
                st.session_state.completed_quizzes.add("level4")
            else:
                st.error("✗ Incorrect. Try again!")

    # Level 5: Smart Money Concepts
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">💎 Level 5: Smart Money Concepts</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">Liquidity, Sweeps, Order Blocks & BOS/CHoCH</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[5] or st.checkbox("Expand Level 5", key="level5_expand"):
        st.session_state.academy_progress[5] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 5.1: Liquidity</strong><br>The volume of buyers/sellers that institutions seek:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Previous highs/lows: Where retail stop losses cluster</div>
        <div class="key-takeaway">• Smart money collects liquidity by moving price to sweep stops</div>
        <div class="key-takeaway">• Trading against the liquidity = Higher probability</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 5.2: Liquidity Sweeps</strong><br>When price temporarily takes out support/resistance:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Price breaks a level, sweeps lows/highs, then reverses</div>
        <div class="key-takeaway">• Institutions fill orders above resistance, create reverse</div>
        <div class="key-takeaway">• Entry after the sweep = Higher win rate</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 5.3: Order Blocks</strong><br>Areas where institutions likely have large orders:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Imbalance zones: Price moved fast, few transactions</div>
        <div class="key-takeaway">• Order blocks often become support/resistance</div>
        <div class="key-takeaway">• Look for order blocks in direction of larger trend</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 5.4: BOS & CHoCH</strong><br>Market structure breaks indicating trend changes:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• BOS (Break of Structure): Breaks a swing low in downtrend</div>
        <div class="key-takeaway">• CHoCH (Change of Character): Price action becomes opposite</div>
        <div class="key-takeaway">• Combined: Most reliable trend reversal signals</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 5</div><p>What is a liquidity sweep?</p></div>', unsafe_allow_html=True)
        quiz_answer_5 = st.radio("Select answer:", ["A smooth price move", "Price breaks a level, takes stops, then reverses", "A technical indicator"], key="q5")
        if st.button("Submit Quiz 5.1", key="submit_q5"):
            if quiz_answer_5 == "Price breaks a level, takes stops, then reverses":
                st.success("✓ Correct! Sweeps are institutional liquidity grabs.")
                st.session_state.completed_quizzes.add("level5")
            else:
                st.error("✗ Incorrect. Try again!")

    # Level 6: Risk Management
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">🛡️ Level 6: Risk Management</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">Position Sizing, Risk:Reward & Drawdown Control</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[6] or st.checkbox("Expand Level 6", key="level6_expand"):
        st.session_state.academy_progress[6] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 6.1: Position Sizing</strong><br>Risking a fixed % per trade protects your account:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Risk 1-2% of account per trade (standard)</div>
        <div class="key-takeaway">• Position Size = (Risk $ ÷ Pips at Risk) × Pip Value</div>
        <div class="key-takeaway">• Example: $10,000 account, risk 1% = $100 max loss</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 6.2: Risk:Reward Ratio</strong><br>Profitable trading requires proper R:R ratios:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• 1:1 R:R: Win/loss balanced (need >50% win rate)</div>
        <div class="key-takeaway">• 1:2 R:R: Win twice the risk (profitable with 50% wins)</div>
        <div class="key-takeaway">• 1:3 R:R: High reward (less frequent perfect setups)</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 6.3: Maximum Daily Loss</strong><br>Hard stops prevent catastrophic account drawdown:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Set daily loss limit (e.g., 5% of account)</div>
        <div class="key-takeaway">• Once hit, STOP trading for the day (no revenge trading)</div>
        <div class="key-takeaway">• Protects against emotional, reckless decisions</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 6</div><p>With $10,000 account risking 2% per trade, max loss per trade?</p></div>', unsafe_allow_html=True)
        quiz_answer_6 = st.radio("Select answer:", ["$100", "$200", "$500"], key="q6")
        if st.button("Submit Quiz 6.1", key="submit_q6"):
            if quiz_answer_6 == "$200":
                st.success("✓ Correct! $10,000 × 2% = $200 risk per trade.")
                st.session_state.completed_quizzes.add("level6")
            else:
                st.error("✗ Incorrect. Try again!")

    # Level 7: Trading Psychology
    st.markdown('<div class="level-card">', unsafe_allow_html=True)
    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        st.markdown('<div class="level-title">🧠 Level 7: Trading Psychology</div>', unsafe_allow_html=True)
        st.markdown('<div class="level-subtitle">FOMO, Revenge Trading, Discipline & Consistency</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.academy_progress[7] or st.checkbox("Expand Level 7", key="level7_expand"):
        st.session_state.academy_progress[7] = True

        st.markdown('<div class="lesson-content"><strong>Lesson 7.1: FOMO (Fear of Missing Out)</strong><br>The enemy of disciplined trading:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Entering trades outside your plan = FOMO trading</div>
        <div class="key-takeaway">• Miss 1 trade? 100 more will come this month</div>
        <div class="key-takeaway">• Track missed trades to prove discipline pays off</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 7.2: Revenge Trading</strong><br>Emotional response to losses that compounds damage:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• After a loss, emotion makes you trade bigger</div>
        <div class="key-takeaway">• Bigger positions + emotional decisions = catastrophic losses</div>
        <div class="key-takeaway">• Solution: Hard daily loss limit, mandatory break</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="lesson-content"><strong>Lesson 7.3: Discipline & Routine</strong><br>Consistency beats occasional brilliance:</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="key-takeaway">• Same setup analysis every day builds skill</div>
        <div class="key-takeaway">• Stick to your plan even when you're "sure" it'll fail</div>
        <div class="key-takeaway">• Log every trade: builds pattern recognition</div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="quiz-box"><div class="quiz-title">🎯 Quiz: Level 7</div><p>What should you do after hitting your daily loss limit?</p></div>', unsafe_allow_html=True)
        quiz_answer_7 = st.radio("Select answer:", ["Take bigger risk to recover", "Stop trading for the day", "Trade a different pair"], key="q7")
        if st.button("Submit Quiz 7.1", key="submit_q7"):
            if quiz_answer_7 == "Stop trading for the day":
                st.success("✓ Correct! Discipline > Revenge. Walk away, review, return tomorrow.")
                st.session_state.completed_quizzes.add("level7")
            else:
                st.error("✗ Incorrect. Try again!")

    # Final stats
    st.divider()
    st.markdown('<div style="text-align: center; color: #00ff88; font-weight: 700; margin-top: 30px;">Academy Complete!</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align: center; color: #00d4ff;">You have completed {len(st.session_state.completed_quizzes)}/{total} levels.</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    render_academy()
