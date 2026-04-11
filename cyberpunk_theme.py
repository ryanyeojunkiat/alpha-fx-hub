import streamlit as st
from typing import Optional


def inject_cyberpunk_css():
    """
    Injects a massive CSS block for a cyberpunk neon theme into Streamlit.
    Includes glowing effects, grid backgrounds, glitch animations, and more.
    """
    cyberpunk_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Space+Mono:wght@400;700&family=Share+Tech+Mono&display=swap');

    /* Root Color Variables */
    :root {
        --dark-bg-1: #0a0a1a;
        --dark-bg-2: #0d0b1e;
        --neon-cyan: #00fff2;
        --neon-pink: #ff2d7b;
        --neon-magenta: #ff00ff;
        --neon-purple: #9d4edd;
        --neon-green: #39ff14;
        --dark-text: #e0e0e0;
        --shadow-color: #00fff2;
    }

    /* Global Styles */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {
        background-color: var(--dark-bg-1) !important;
        color: var(--dark-text) !important;
        font-family: 'Space Mono', monospace !important;
    }

    /* Grid Background Pattern */
    [data-testid="stAppViewContainer"]::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image:
            linear-gradient(90deg, transparent 24%, rgba(0, 255, 242, 0.02) 25%, rgba(0, 255, 242, 0.02) 26%, transparent 27%, transparent 74%, rgba(0, 255, 242, 0.02) 75%, rgba(0, 255, 242, 0.02) 76%, transparent 77%, transparent),
            linear-gradient(0deg, transparent 24%, rgba(0, 255, 242, 0.02) 25%, rgba(0, 255, 242, 0.02) 26%, transparent 27%, transparent 74%, rgba(0, 255, 242, 0.02) 75%, rgba(0, 255, 242, 0.02) 76%, transparent 77%, transparent);
        background-size: 50px 50px;
        pointer-events: none;
        z-index: -1;
    }

    /* Scanline Overlay Effect */
    [data-testid="stAppViewContainer"]::after {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: repeating-linear-gradient(
            0deg,
            rgba(0, 0, 0, 0.03),
            rgba(0, 0, 0, 0.03) 1px,
            transparent 1px,
            transparent 2px
        );
        pointer-events: none;
        z-index: -1;
    }

    /* Glitch Animation */
    @keyframes glitch {
        0% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(0);
        }
        20% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(-2px, 2px);
        }
        40% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(-2px, -2px);
        }
        60% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(2px, 2px);
        }
        80% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(2px, -2px);
        }
        100% {
            text-shadow: -2px 0 var(--neon-magenta), 2px 0 var(--neon-cyan);
            transform: translate(0);
        }
    }

    @keyframes glitch-flicker {
        0% {
            opacity: 1;
        }
        19% {
            opacity: 1;
        }
        20% {
            opacity: 0;
        }
        24% {
            opacity: 0;
        }
        25% {
            opacity: 1;
        }
        54% {
            opacity: 1;
        }
        55% {
            opacity: 0;
        }
        59% {
            opacity: 0;
        }
        60% {
            opacity: 1;
        }
        100% {
            opacity: 1;
        }
    }

    @keyframes neon-glow {
        0%, 100% {
            text-shadow: 0 0 10px rgba(0, 255, 242, 0.3), 0 0 20px rgba(0, 255, 242, 0.2);
        }
        50% {
            text-shadow: 0 0 20px rgba(0, 255, 242, 0.6), 0 0 30px rgba(0, 255, 242, 0.4), 0 0 40px rgba(0, 255, 242, 0.2);
        }
    }

    @keyframes border-glow {
        0%, 100% {
            box-shadow: 0 0 5px rgba(0, 255, 242, 0.3), inset 0 0 5px rgba(0, 255, 242, 0.1);
        }
        50% {
            box-shadow: 0 0 20px rgba(0, 255, 242, 0.6), inset 0 0 10px rgba(0, 255, 242, 0.2);
        }
    }

    @keyframes pulse-glow {
        0%, 100% {
            opacity: 0.7;
        }
        50% {
            opacity: 1;
        }
    }

    /* Headings with Neon Glow */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Orbitron', sans-serif !important;
        color: var(--neon-cyan) !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5), 0 0 20px rgba(0, 255, 242, 0.3) !important;
        font-weight: 700 !important;
        letter-spacing: 2px !important;
    }

    h1 {
        font-size: 2.5rem !important;
        text-shadow: 0 0 20px rgba(0, 255, 242, 0.7), 0 0 40px rgba(0, 255, 242, 0.4), 0 0 60px rgba(0, 255, 242, 0.2) !important;
    }

    .cyberpunk-glitch-title {
        animation: glitch 2s infinite !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: var(--dark-bg-2) !important;
        border-right: 2px solid var(--neon-cyan) !important;
        box-shadow: -10px 0 30px rgba(0, 255, 242, 0.15) !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: var(--dark-text) !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: var(--neon-cyan) !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5) !important;
    }

    /* Cards and Containers */
    .neon-card {
        background-color: rgba(13, 11, 30, 0.8) !important;
        border: 2px solid var(--neon-cyan) !important;
        border-radius: 8px !important;
        padding: 20px !important;
        margin: 15px 0 !important;
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.3), inset 0 0 10px rgba(0, 255, 242, 0.05) !important;
        animation: border-glow 3s ease-in-out infinite !important;
    }

    .neon-card-pink {
        border-color: var(--neon-pink) !important;
        box-shadow: 0 0 20px rgba(255, 45, 123, 0.3), inset 0 0 10px rgba(255, 45, 123, 0.05) !important;
    }

    .neon-card-magenta {
        border-color: var(--neon-magenta) !important;
        box-shadow: 0 0 20px rgba(255, 0, 255, 0.3), inset 0 0 10px rgba(255, 0, 255, 0.05) !important;
    }

    .neon-card-purple {
        border-color: var(--neon-purple) !important;
        box-shadow: 0 0 20px rgba(157, 78, 221, 0.3), inset 0 0 10px rgba(157, 78, 221, 0.05) !important;
    }

    .neon-card-green {
        border-color: var(--neon-green) !important;
        box-shadow: 0 0 20px rgba(57, 255, 20, 0.3), inset 0 0 10px rgba(57, 255, 20, 0.05) !important;
    }

    .neon-card h3 {
        color: var(--neon-cyan) !important;
        margin-top: 0 !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5) !important;
    }

    /* Button Styling */
    button, [data-testid="baseButton-primary"],
    .stButton > button {
        background-color: rgba(0, 255, 242, 0.1) !important;
        color: var(--neon-cyan) !important;
        border: 2px solid var(--neon-cyan) !important;
        border-radius: 6px !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 0 10px rgba(0, 255, 242, 0.2) !important;
    }

    button:hover, [data-testid="baseButton-primary"]:hover,
    .stButton > button:hover {
        background-color: rgba(0, 255, 242, 0.2) !important;
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.6), inset 0 0 10px rgba(0, 255, 242, 0.2) !important;
        color: var(--neon-cyan) !important;
        transform: translate(0, -2px) !important;
    }

    button:active, [data-testid="baseButton-primary"]:active,
    .stButton > button:active {
        box-shadow: 0 0 30px rgba(0, 255, 242, 0.8), inset 0 0 15px rgba(0, 255, 242, 0.3) !important;
    }

    /* Input and Selectbox Styling */
    input, textarea, select,
    [data-testid="textInputRootElement"],
    [data-testid="stSelectbox"] input,
    [data-baseweb="select"] {
        background-color: rgba(13, 11, 30, 0.9) !important;
        color: var(--neon-cyan) !important;
        border: 2px solid var(--neon-purple) !important;
        border-radius: 6px !important;
        font-family: 'Space Mono', monospace !important;
        caret-color: var(--neon-cyan) !important;
        transition: all 0.3s ease !important;
        box-shadow: inset 0 0 5px rgba(157, 78, 221, 0.2) !important;
    }

    input:focus, textarea:focus, select:focus,
    [data-testid="textInputRootElement"]:focus,
    [data-testid="stSelectbox"] input:focus {
        border-color: var(--neon-cyan) !important;
        box-shadow: inset 0 0 10px rgba(0, 255, 242, 0.2), 0 0 15px rgba(0, 255, 242, 0.3) !important;
        outline: none !important;
    }

    input::placeholder {
        color: rgba(224, 224, 224, 0.4) !important;
    }

    /* Tabs and Radio Buttons */
    [data-testid="stTabs"] [role="tablist"] button {
        color: var(--dark-text) !important;
        border-bottom: 3px solid transparent !important;
        font-family: 'Orbitron', sans-serif !important;
        transition: all 0.3s ease !important;
    }

    [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"] {
        color: var(--neon-cyan) !important;
        border-bottom-color: var(--neon-cyan) !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5) !important;
        box-shadow: 0 4px 0 -2px var(--neon-cyan), 0 0 15px rgba(0, 255, 242, 0.3) !important;
    }

    [role="radio"] {
        accent-color: var(--neon-cyan) !important;
    }

    /* Scrollbar Styling */
    ::-webkit-scrollbar {
        width: 12px !important;
        height: 12px !important;
    }

    ::-webkit-scrollbar-track {
        background: rgba(13, 11, 30, 0.5) !important;
    }

    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, var(--neon-cyan), var(--neon-purple)) !important;
        border-radius: 6px !important;
        box-shadow: 0 0 10px rgba(0, 255, 242, 0.4) !important;
    }

    ::-webkit-scrollbar-thumb:hover {
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.7) !important;
    }

    /* Metric/KPI Styles */
    .neon-metric {
        background-color: rgba(13, 11, 30, 0.8) !important;
        border: 2px solid var(--neon-cyan) !important;
        border-radius: 8px !important;
        padding: 20px !important;
        text-align: center !important;
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.3), inset 0 0 10px rgba(0, 255, 242, 0.05) !important;
        animation: border-glow 3s ease-in-out infinite !important;
    }

    .neon-metric-label {
        color: var(--dark-text) !important;
        font-size: 0.9rem !important;
        font-family: 'Space Mono', monospace !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        margin-bottom: 10px !important;
    }

    .neon-metric-value {
        color: var(--neon-cyan) !important;
        font-size: 2rem !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5), 0 0 20px rgba(0, 255, 242, 0.3) !important;
        animation: neon-glow 2s ease-in-out infinite !important;
    }

    .neon-metric-pink .neon-metric-value {
        color: var(--neon-pink) !important;
        text-shadow: 0 0 10px rgba(255, 45, 123, 0.5), 0 0 20px rgba(255, 45, 123, 0.3) !important;
    }

    .neon-metric-magenta .neon-metric-value {
        color: var(--neon-magenta) !important;
        text-shadow: 0 0 10px rgba(255, 0, 255, 0.5), 0 0 20px rgba(255, 0, 255, 0.3) !important;
    }

    .neon-metric-purple .neon-metric-value {
        color: var(--neon-purple) !important;
        text-shadow: 0 0 10px rgba(157, 78, 221, 0.5), 0 0 20px rgba(157, 78, 221, 0.3) !important;
    }

    .neon-metric-green .neon-metric-value {
        color: var(--neon-green) !important;
        text-shadow: 0 0 10px rgba(57, 255, 20, 0.5), 0 0 20px rgba(57, 255, 20, 0.3) !important;
    }

    /* Divider Line */
    hr {
        border: none !important;
        border-top: 2px solid var(--neon-cyan) !important;
        box-shadow: 0 0 10px rgba(0, 255, 242, 0.3) !important;
        margin: 20px 0 !important;
    }

    /* Code Block Styling */
    code, pre, [data-testid="stCodeBlock"] {
        background-color: rgba(13, 11, 30, 0.9) !important;
        color: var(--neon-green) !important;
        border: 1px solid var(--neon-green) !important;
        border-radius: 6px !important;
        font-family: 'Space Mono', monospace !important;
        text-shadow: 0 0 5px rgba(57, 255, 20, 0.3) !important;
    }

    /* Data Table Styling */
    [data-testid="stDataFrame"] {
        background-color: rgba(13, 11, 30, 0.8) !important;
        border: 2px solid var(--neon-purple) !important;
        border-radius: 6px !important;
        box-shadow: 0 0 15px rgba(157, 78, 221, 0.2) !important;
    }

    [data-testid="stDataFrame"] table {
        color: var(--dark-text) !important;
    }

    [data-testid="stDataFrame"] th {
        background-color: rgba(157, 78, 221, 0.2) !important;
        color: var(--neon-cyan) !important;
        font-family: 'Orbitron', sans-serif !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.3) !important;
        border-color: var(--neon-purple) !important;
    }

    [data-testid="stDataFrame"] td {
        border-color: rgba(157, 78, 221, 0.3) !important;
        font-family: 'Space Mono', monospace !important;
    }

    /* Streamlit Metric Override */
    [data-testid="metric-container"] {
        background-color: rgba(13, 11, 30, 0.8) !important;
        border: 2px solid var(--neon-cyan) !important;
        border-radius: 8px !important;
        padding: 15px !important;
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.3) !important;
    }

    [data-testid="metric-container"] label {
        color: var(--dark-text) !important;
        font-family: 'Space Mono', monospace !important;
    }

    [data-testid="metric-container"] span {
        color: var(--neon-cyan) !important;
        font-family: 'Orbitron', sans-serif !important;
        text-shadow: 0 0 10px rgba(0, 255, 242, 0.5) !important;
    }

    /* Expander Styling */
    [data-testid="stExpander"] button {
        color: var(--neon-cyan) !important;
        font-family: 'Orbitron', sans-serif !important;
        border-left: 3px solid var(--neon-cyan) !important;
        padding-left: 12px !important;
    }

    [data-testid="stExpander"] > div {
        background-color: rgba(13, 11, 30, 0.6) !important;
        border: 1px solid var(--neon-purple) !important;
        border-radius: 6px !important;
    }

    /* Info, Warning, Error, Success Messages */
    [data-testid="stAlert"] {
        border-radius: 6px !important;
        font-family: 'Space Mono', monospace !important;
    }

    [data-testid="stAlert-info"] {
        background-color: rgba(0, 255, 242, 0.1) !important;
        border: 2px solid var(--neon-cyan) !important;
        color: var(--neon-cyan) !important;
        box-shadow: 0 0 15px rgba(0, 255, 242, 0.2) !important;
    }

    [data-testid="stAlert-success"] {
        background-color: rgba(57, 255, 20, 0.1) !important;
        border: 2px solid var(--neon-green) !important;
        color: var(--neon-green) !important;
        box-shadow: 0 0 15px rgba(57, 255, 20, 0.2) !important;
    }

    [data-testid="stAlert-warning"] {
        background-color: rgba(255, 45, 123, 0.1) !important;
        border: 2px solid var(--neon-pink) !important;
        color: var(--neon-pink) !important;
        box-shadow: 0 0 15px rgba(255, 45, 123, 0.2) !important;
    }

    [data-testid="stAlert-error"] {
        background-color: rgba(255, 0, 255, 0.1) !important;
        border: 2px solid var(--neon-magenta) !important;
        color: var(--neon-magenta) !important;
        box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) !important;
    }

    /* Header Override */
    [data-testid="stHeader"] {
        background-color: rgba(10, 10, 26, 0.9) !important;
        border-bottom: 2px solid var(--neon-cyan) !important;
        box-shadow: 0 4px 20px rgba(0, 255, 242, 0.15) !important;
    }

    </style>
    """
    st.markdown(cyberpunk_css, unsafe_allow_html=True)


def cyberpunk_header(title: str, subtitle: str = ""):
    """
    Renders an animated cyberpunk header with glitch effect.

    Parameters:
    -----------
    title : str
        Main title text with glitch animation
    subtitle : str, optional
        Subtitle text (no glitch animation)
    """
    header_html = f"""
    <div style="text-align: center; margin: 30px 0 40px 0;">
        <h1 class="cyberpunk-glitch-title" style="
            font-family: 'Orbitron', sans-serif;
            font-size: 3.5rem;
            font-weight: 900;
            color: #00fff2;
            text-shadow: 0 0 20px rgba(0, 255, 242, 0.7), 0 0 40px rgba(0, 255, 242, 0.4), 0 0 60px rgba(0, 255, 242, 0.2);
            letter-spacing: 4px;
            margin: 0;
            padding: 20px 0;
            animation: glitch 2s infinite;
        ">
            {title}
        </h1>
    """

    if subtitle:
        header_html += f"""
        <p style="
            font-family: 'Space Mono', monospace;
            font-size: 1.2rem;
            color: #9d4edd;
            text-shadow: 0 0 10px rgba(157, 78, 221, 0.5);
            letter-spacing: 2px;
            margin: 10px 0 0 0;
        ">
            {subtitle}
        </p>
        """

    header_html += """
    </div>
    """

    st.markdown(header_html, unsafe_allow_html=True)


def neon_card(title: str, content: str, color: str = "#00fff2"):
    """
    Renders a card with neon border glow effect.

    Parameters:
    -----------
    title : str
        Title of the card
    content : str
        HTML or text content inside the card
    color : str, optional
        Neon color for the border (#00fff2 cyan, #ff2d7b pink, #ff00ff magenta, #9d4edd purple, #39ff14 green)
    """
    # Map color names to CSS classes
    color_map = {
        "#00fff2": "neon-cyan",
        "#ff2d7b": "neon-pink",
        "#ff00ff": "neon-magenta",
        "#9d4edd": "neon-purple",
        "#39ff14": "neon-green",
    }

    # Determine which class to use
    color_class = ""
    if color in ["#ff2d7b", "pink"]:
        color_class = "neon-card-pink"
    elif color in ["#ff00ff", "magenta"]:
        color_class = "neon-card-magenta"
    elif color in ["#9d4edd", "purple"]:
        color_class = "neon-card-purple"
    elif color in ["#39ff14", "green"]:
        color_class = "neon-card-green"

    card_html = f"""
    <div class="neon-card {color_class}">
        <h3>{title}</h3>
        <div style="color: #e0e0e0; font-family: 'Space Mono', monospace;">
            {content}
        </div>
    </div>
    """

    st.markdown(card_html, unsafe_allow_html=True)


def neon_metric(label: str, value: str, color: str = "#00fff2"):
    """
    Renders a KPI-style metric with neon styling.

    Parameters:
    -----------
    label : str
        Label for the metric
    value : str
        The metric value to display
    color : str, optional
        Neon color for the metric (#00fff2 cyan, #ff2d7b pink, #ff00ff magenta, #9d4edd purple, #39ff14 green)
    """
    # Determine which class to use based on color
    color_class = ""
    if color in ["#ff2d7b", "pink"]:
        color_class = "neon-metric-pink"
    elif color in ["#ff00ff", "magenta"]:
        color_class = "neon-metric-magenta"
    elif color in ["#9d4edd", "purple"]:
        color_class = "neon-metric-purple"
    elif color in ["#39ff14", "green"]:
        color_class = "neon-metric-green"

    metric_html = f"""
    <div class="neon-metric {color_class}">
        <div class="neon-metric-label">{label}</div>
        <div class="neon-metric-value">{value}</div>
    </div>
    """

    st.markdown(metric_html, unsafe_allow_html=True)
