"""
Anime Visual Theme Module for Alpha FX Hub
Adds N.A.M.I AI assistant character and anime-inspired cyberpunk aesthetics
Uses streamlit.components.v1.html() for reliable HTML rendering
"""

import streamlit as st
import streamlit.components.v1 as components


def render_nami_character():
    """
    Renders N.A.M.I character in the sidebar using components.html()
    This guarantees HTML/CSS renders correctly (no code block issues)
    """
    nami_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: transparent; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100%; overflow: hidden; }

@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
}
@keyframes glow-pulse {
    0%, 100% { filter: drop-shadow(0 0 8px #00ffff) drop-shadow(0 0 15px #ff00ff); }
    50% { filter: drop-shadow(0 0 15px #00ffff) drop-shadow(0 0 25px #ff00ff); }
}
@keyframes eye-sparkle {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.nami-wrap {
    animation: float 3s ease-in-out infinite;
    text-align: center;
}
.nami-svg {
    animation: glow-pulse 2s ease-in-out infinite;
}
.nami-eye {
    animation: eye-sparkle 1.5s ease-in-out infinite;
}
.nami-label {
    color: #ff00ff;
    font-weight: bold;
    font-size: 13px;
    margin-top: 6px;
    font-family: 'Segoe UI', sans-serif;
    text-shadow: 0 0 8px #ff00ff;
}
.nami-sub {
    color: #00ffff;
    font-size: 9px;
    letter-spacing: 2px;
    font-family: monospace;
    text-shadow: 0 0 5px #00ffff;
}
</style>
</head>
<body>
<div class="nami-wrap">
    <svg viewBox="0 0 200 320" width="160" height="260" class="nami-svg">
        <defs>
            <radialGradient id="aG" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#ff00ff;stop-opacity:0.3"/>
                <stop offset="100%" style="stop-color:#00ffff;stop-opacity:0"/>
            </radialGradient>
            <linearGradient id="hG" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ff1493"/>
                <stop offset="50%" style="stop-color:#ff69b4"/>
                <stop offset="100%" style="stop-color:#ba55d3"/>
            </linearGradient>
            <linearGradient id="sG" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ffe4c4"/>
                <stop offset="100%" style="stop-color:#ffd4a3"/>
            </linearGradient>
        </defs>
        <circle cx="100" cy="160" r="95" fill="url(#aG)" stroke="#ff00ff" stroke-width="1.5" opacity="0.4"/>
        <path d="M 60 80 Q 50 100 55 140 Q 50 170 70 200 L 70 240 Q 70 260 80 280 L 120 280 Q 130 260 130 240 L 130 200 Q 150 170 145 140 Q 150 100 140 80 Z" fill="url(#hG)" stroke="#ff1493" stroke-width="1.5"/>
        <path d="M 65 90 Q 60 120 65 160" stroke="#ff69b4" stroke-width="2" fill="none" opacity="0.8"/>
        <path d="M 135 90 Q 140 120 135 160" stroke="#ba55d3" stroke-width="2" fill="none" opacity="0.8"/>
        <path d="M 75 85 Q 70 115 80 155" stroke="#fff" stroke-width="1.5" fill="none" opacity="0.5"/>
        <circle cx="100" cy="110" r="35" fill="url(#sG)" stroke="#ff69b4" stroke-width="1"/>
        <g class="nami-eye">
            <ellipse cx="82" cy="105" rx="8" ry="12" fill="#fff" stroke="#00ffff" stroke-width="1.5"/>
            <circle cx="82" cy="107" r="5" fill="#00ffff" opacity="0.9"/>
            <circle cx="81" cy="105" r="2" fill="#fff"/>
            <ellipse cx="118" cy="105" rx="8" ry="12" fill="#fff" stroke="#00ffff" stroke-width="1.5"/>
            <circle cx="118" cy="107" r="5" fill="#00ffff" opacity="0.9"/>
            <circle cx="117" cy="105" r="2" fill="#fff"/>
            <circle cx="82" cy="105" r="10" fill="none" stroke="#00ffff" stroke-width="1" opacity="0.4"/>
            <circle cx="118" cy="105" r="10" fill="none" stroke="#00ffff" stroke-width="1" opacity="0.4"/>
        </g>
        <path d="M 75 95 Q 82 92 89 94" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M 111 94 Q 118 92 125 95" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
        <line x1="100" y1="110" x2="100" y2="118" stroke="#ffb6c1" stroke-width="1"/>
        <path d="M 90 125 Q 100 130 110 125" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M 70 145 Q 70 150 75 155 L 125 155 Q 130 150 130 145 Z" fill="#00ffff" stroke="#00ffff" stroke-width="1.5" opacity="0.8"/>
        <ellipse cx="100" cy="180" rx="32" ry="40" fill="#1a1a2e" stroke="#00ffff" stroke-width="2"/>
        <rect x="82" y="155" width="36" height="35" rx="4" fill="#00ffff" opacity="0.2" stroke="#00ffff" stroke-width="2"/>
        <line x1="82" y1="170" x2="118" y2="170" stroke="#ff00ff" stroke-width="1" opacity="0.6"/>
        <line x1="82" y1="185" x2="118" y2="185" stroke="#ff00ff" stroke-width="1" opacity="0.6"/>
        <path d="M 68 150 Q 60 165 65 190 L 70 185 Q 75 165 75 150 Z" fill="#16213e" stroke="#00ffff" stroke-width="1.5"/>
        <path d="M 132 150 Q 140 165 135 190 L 130 185 Q 125 165 125 150 Z" fill="#16213e" stroke="#00ffff" stroke-width="1.5"/>
        <line x1="68" y1="170" x2="50" y2="200" stroke="#1a1a2e" stroke-width="12" stroke-linecap="round"/>
        <line x1="50" y1="200" x2="45" y2="240" stroke="#1a1a2e" stroke-width="10" stroke-linecap="round"/>
        <line x1="132" y1="170" x2="150" y2="200" stroke="#1a1a2e" stroke-width="12" stroke-linecap="round"/>
        <line x1="150" y1="200" x2="155" y2="240" stroke="#1a1a2e" stroke-width="10" stroke-linecap="round"/>
        <circle cx="45" cy="240" r="8" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.9"/>
        <circle cx="155" cy="240" r="8" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.9"/>
        <path d="M 78 215 L 122 215 L 130 280 L 70 280 Z" fill="#1a0f2e" stroke="#00ffff" stroke-width="1.5"/>
        <line x1="75" y1="230" x2="125" y2="230" stroke="#ff00ff" stroke-width="1" opacity="0.5"/>
        <line x1="72" y1="250" x2="128" y2="250" stroke="#ff00ff" stroke-width="1" opacity="0.5"/>
        <line x1="82" y1="280" x2="80" y2="310" stroke="#0a0a0a" stroke-width="8" stroke-linecap="round"/>
        <line x1="118" y1="280" x2="120" y2="310" stroke="#0a0a0a" stroke-width="8" stroke-linecap="round"/>
        <circle cx="80" cy="310" r="6" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>
        <circle cx="120" cy="310" r="6" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>
        <circle cx="110" cy="70" r="2" fill="#00ffff" opacity="0.7"/>
        <circle cx="55" cy="130" r="2" fill="#ff00ff" opacity="0.7"/>
        <circle cx="145" cy="140" r="2" fill="#00ffff" opacity="0.7"/>
        <circle cx="70" cy="220" r="2" fill="#ff00ff" opacity="0.7"/>
        <circle cx="130" cy="210" r="2" fill="#00ffff" opacity="0.7"/>
    </svg>
    <div class="nami-label">N.A.M.I</div>
    <div class="nami-sub">NEURAL ALGORITHMIC MARKET INTELLIGENCE</div>
</div>
</body>
</html>
"""
    components.html(nami_html, height=320, scrolling=False)


def render_anime_welcome(username="Trader"):
    """
    Renders anime welcome splash using components.html()
    Guarantees proper HTML rendering without code block issues
    """
    welcome_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: transparent; font-family: 'Segoe UI', sans-serif; padding: 10px; }}

@keyframes text-glow {{
    0%, 100% {{ text-shadow: 0 0 5px #00ffff, 0 0 10px #ff00ff; color: #fff; }}
    50% {{ text-shadow: 0 0 15px #00ffff, 0 0 25px #ff00ff, 0 0 35px #ff1493; color: #ffff00; }}
}}
@keyframes bubble-bounce {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.02); }}
}}
@keyframes particle-float {{
    0% {{ transform: translateY(0) rotate(0deg); opacity: 0.8; }}
    100% {{ transform: translateY(-60px) rotate(360deg); opacity: 0; }}
}}

.welcome-box {{
    background: linear-gradient(135deg, #0f0f23, #1a0f2e);
    border: 2px solid #ff00ff;
    border-radius: 15px;
    padding: 25px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 20px rgba(255,0,255,0.5), inset 0 0 20px rgba(0,255,255,0.1);
}}
.welcome-title {{
    animation: text-glow 3s ease-in-out infinite;
    font-size: 26px;
    font-weight: 900;
    text-align: center;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #fff;
    margin-bottom: 15px;
}}
.speech-bubble {{
    background: linear-gradient(135deg, #00ffff, #ff00ff);
    padding: 2px;
    border-radius: 15px;
    margin: 10px 0;
    animation: bubble-bounce 2s ease-in-out infinite;
}}
.bubble-inner {{
    background: #0a0a15;
    border-radius: 13px;
    padding: 15px 20px;
    color: #fff;
    font-size: 14px;
    font-style: italic;
    letter-spacing: 0.5px;
}}
.username {{
    color: #ffff00;
    font-weight: bold;
    text-shadow: 0 0 10px #ffff00;
}}
.subtitle {{
    text-align: center;
    color: #00ffff;
    font-size: 11px;
    margin-top: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-shadow: 0 0 5px #00ffff;
}}
.particle {{
    position: absolute;
    width: 6px;
    height: 6px;
    background: radial-gradient(circle, #ffff00, #ff00ff);
    border-radius: 50%;
    pointer-events: none;
    animation: particle-float 3s ease-out infinite;
}}
</style>
</head>
<body>
<div class="welcome-box">
    <div class="particle" style="left:10%;bottom:10%;animation-delay:0s;"></div>
    <div class="particle" style="left:30%;bottom:5%;animation-delay:0.5s;"></div>
    <div class="particle" style="left:60%;bottom:8%;animation-delay:1s;"></div>
    <div class="particle" style="left:80%;bottom:12%;animation-delay:1.5s;"></div>
    <div class="particle" style="left:90%;bottom:6%;animation-delay:2s;"></div>

    <div class="welcome-title">Welcome Back!</div>

    <div class="speech-bubble">
        <div class="bubble-inner">
            Ready to navigate the markets, <span class="username">{username}</span>? Let's find that treasure! &#x1F3F4;&#x200D;&#x2620;&#xFE0F;
        </div>
    </div>

    <div class="subtitle">Powered by N.A.M.I &mdash; Neural Algorithmic Market Intelligence</div>
</div>
</body>
</html>
"""
    components.html(welcome_html, height=220, scrolling=False)


def render_anime_sidebar_decor():
    """
    Sidebar decoration — compact power scanner + anime nav icons
    Uses components.html() for reliable rendering
    """
    sidebar_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: transparent; font-family: 'Segoe UI', sans-serif; padding: 5px; }

@keyframes scouter-scan {
    0%, 100% { color: #00ff00; text-shadow: 0 0 10px #00ff00; }
    50% { color: #ff0000; text-shadow: 0 0 15px #ff0000; }
}
@keyframes power-pulse {
    0%, 100% { width: 60%; box-shadow: 0 0 10px #00ff00; }
    50% { width: 75%; box-shadow: 0 0 20px #ffff00; }
}
@keyframes katana-glow {
    0%, 100% { box-shadow: 0 0 5px #ff1493; }
    50% { box-shadow: 0 0 15px #ff1493, 0 0 25px #00ffff; }
}

.decor-box {
    background: rgba(15,15,35,0.8);
    border-radius: 10px;
    padding: 10px;
}
.divider {
    height: 3px;
    background: linear-gradient(90deg, transparent, #ff1493, #00ffff, #ff1493, transparent);
    border-radius: 2px;
    margin: 8px 0;
    animation: katana-glow 2s ease-in-out infinite;
}
.scouter {
    background: linear-gradient(135deg, #001a00, #003300);
    border: 2px solid #00ff00;
    border-radius: 10px;
    padding: 10px;
    text-align: center;
    box-shadow: inset 0 0 10px rgba(0,255,0,0.3), 0 0 15px rgba(0,255,0,0.5);
    animation: scouter-scan 3s ease-in-out infinite;
}
.scouter-title {
    color: #00ff00;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.power-meter {
    height: 6px;
    background: #001a00;
    border: 1px solid #00ff00;
    border-radius: 3px;
    overflow: hidden;
    margin: 6px 0;
}
.power-bar {
    height: 100%;
    background: linear-gradient(90deg, #00ff00, #ffff00, #ff6600);
    border-radius: 3px;
    animation: power-pulse 2s ease-in-out infinite;
}
.power-value {
    color: #00ff00;
    font-size: 11px;
    font-weight: bold;
    font-family: monospace;
    margin-top: 4px;
}
.pirate-row {
    text-align: center;
    margin-top: 8px;
    font-size: 11px;
    color: #ff1493;
    letter-spacing: 1px;
    text-shadow: 0 0 5px #ff1493;
}
</style>
</head>
<body>
<div class="decor-box">
    <div class="divider"></div>
    <div class="scouter">
        <div class="scouter-title">&#x26A1; Power Scanner &#x26A1;</div>
        <div class="power-meter"><div class="power-bar"></div></div>
        <div class="power-value">POWER: OVER 9000!!</div>
    </div>
    <div class="divider"></div>
    <div class="pirate-row">&#x1F3F4; NAVIGATE MARKETS &#x1F3F4;</div>
</div>
</body>
</html>
"""
    components.html(sidebar_html, height=160, scrolling=False)


def inject_anime_css():
    """
    Injects global CSS-only anime theme into the Streamlit app.
    NO script tags — only pure CSS that Streamlit won't strip.
    """
    anime_css = """<style>
@keyframes petal-fall {
    0% { top: -100px; opacity: 1; transform: translateX(0) rotateZ(0deg); }
    100% { top: 100vh; opacity: 0; transform: translateX(100px) rotateZ(720deg); }
}
@keyframes katana-glow {
    0%, 100% { box-shadow: 0 4px 0 #ff1493, 0 -4px 0 #ff1493; }
    50% { box-shadow: 0 4px 10px #ff1493, 0 -4px 10px #ff1493, inset 0 0 10px #ff00ff; }
}
@keyframes neon-flicker {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.8; }
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0a0a0f 0%, #1a0f2e 50%, #0f1a2e 100%) !important;
}

.katana-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, #ff1493, #00ffff, #ff1493, transparent);
    margin: 20px 0;
    box-shadow: 0 0 15px rgba(255,0,255,0.6), 0 0 25px rgba(0,255,255,0.3);
    animation: katana-glow 2s ease-in-out infinite;
}

.anime-card {
    background: linear-gradient(135deg, #1a0f2e, #2a1a4e);
    border: 2px solid #ff00ff;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 0 20px rgba(255,0,255,0.4), inset 0 0 10px rgba(0,255,255,0.1);
}

.neon-text {
    color: #00ffff;
    text-shadow: 0 0 5px #00ffff, 0 0 10px #00ffff, 0 0 20px #ff00ff;
    letter-spacing: 2px;
    font-weight: bold;
}
</style>"""
    st.markdown(anime_css, unsafe_allow_html=True)


def apply_anime_theme():
    """Convenience function to apply the anime theme."""
    inject_anime_css()
