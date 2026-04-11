"""
Anime Visual Theme Module for Alpha FX Hub
Adds ARIA AI assistant character and anime-inspired cyberpunk aesthetics
"""

import streamlit as st
from datetime import datetime


def render_aria_character():
    """
    Renders ARIA - the cyberpunk anime AI assistant
    A beautiful anime girl character with neon effects and floating animation
    Uses detailed SVG art for a true anime waifu mascot
    """

    aria_svg = """
    <style>
        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(1deg); }
        }

        @keyframes glow-pulse {
            0%, 100% { filter: drop-shadow(0 0 10px #00ffff) drop-shadow(0 0 20px #ff00ff); }
            50% { filter: drop-shadow(0 0 20px #00ffff) drop-shadow(0 0 40px #ff00ff); }
        }

        @keyframes eye-sparkle {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .aria-character {
            animation: float 3s ease-in-out infinite;
            filter: drop-shadow(0 0 15px #ff00ff) drop-shadow(0 0 30px #00ffff);
        }

        .aria-aura {
            animation: glow-pulse 2s ease-in-out infinite;
        }

        .aria-eye {
            animation: eye-sparkle 1.5s ease-in-out infinite;
        }
    </style>

    <div style="display: flex; justify-content: center; margin: 20px 0;">
        <svg viewBox="0 0 200 320" width="200" height="320" class="aria-aura">
            <!-- Neon Aura Background -->
            <defs>
                <radialGradient id="auraGradient" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" style="stop-color:#ff00ff;stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:#00ffff;stop-opacity:0" />
                </radialGradient>

                <linearGradient id="hairGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#ff1493;stop-opacity:1" />
                    <stop offset="50%" style="stop-color:#ff69b4;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#ba55d3;stop-opacity:1" />
                </linearGradient>

                <linearGradient id="skinGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#ffe4c4;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#ffd4a3;stop-opacity:1" />
                </linearGradient>
            </defs>

            <!-- Aura Circle -->
            <circle cx="100" cy="160" r="100" fill="url(#auraGradient)" stroke="#ff00ff" stroke-width="2" opacity="0.5"/>

            <!-- Hair (flowing and ethereal) -->
            <path d="M 60 80 Q 50 100 55 140 Q 50 170 70 200 L 70 240 Q 70 260 80 280 L 120 280 Q 130 260 130 240 L 130 200 Q 150 170 145 140 Q 150 100 140 80 Z"
                  fill="url(#hairGradient)" stroke="#ff1493" stroke-width="1.5"/>

            <!-- Hair highlights (flowing strands) -->
            <path d="M 65 90 Q 60 120 65 160" stroke="#ff69b4" stroke-width="2" fill="none" opacity="0.8"/>
            <path d="M 135 90 Q 140 120 135 160" stroke="#ba55d3" stroke-width="2" fill="none" opacity="0.8"/>
            <path d="M 75 85 Q 70 115 80 155" stroke="#ffffff" stroke-width="1.5" fill="none" opacity="0.6"/>

            <!-- Head -->
            <circle cx="100" cy="110" r="35" fill="url(#skinGradient)" stroke="#ff69b4" stroke-width="1"/>

            <!-- Ears with anime style -->
            <ellipse cx="68" cy="95" rx="10" ry="15" fill="url(#skinGradient)" stroke="#ff69b4" stroke-width="1"/>
            <ellipse cx="132" cy="95" rx="10" ry="15" fill="url(#skinGradient)" stroke="#ff69b4" stroke-width="1"/>

            <!-- Eyes (large and expressive - anime style) -->
            <g class="aria-eye">
                <!-- Left Eye -->
                <ellipse cx="82" cy="105" rx="8" ry="12" fill="#ffffff" stroke="#00ffff" stroke-width="1.5"/>
                <circle cx="82" cy="107" r="5" fill="#00ffff" opacity="0.9"/>
                <circle cx="81" cy="105" r="2" fill="#ffffff"/>

                <!-- Right Eye -->
                <ellipse cx="118" cy="105" rx="8" ry="12" fill="#ffffff" stroke="#00ffff" stroke-width="1.5"/>
                <circle cx="118" cy="107" r="5" fill="#00ffff" opacity="0.9"/>
                <circle cx="117" cy="105" r="2" fill="#ffffff"/>

                <!-- Eye glow effect -->
                <circle cx="82" cy="105" r="10" fill="none" stroke="#00ffff" stroke-width="1" opacity="0.5"/>
                <circle cx="118" cy="105" r="10" fill="none" stroke="#00ffff" stroke-width="1" opacity="0.5"/>
            </g>

            <!-- Eyebrows (anime style, curved) -->
            <path d="M 75 95 Q 82 92 89 94" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
            <path d="M 111 94 Q 118 92 125 95" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>

            <!-- Nose (simple anime style) -->
            <line x1="100" y1="110" x2="100" y2="118" stroke="#ffb6c1" stroke-width="1"/>

            <!-- Mouth (cute smile) -->
            <path d="M 90 125 Q 100 130 110 125" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
            <path d="M 90 125 L 110 125" stroke="#ff69b4" stroke-width="1" opacity="0.5"/>

            <!-- Cyberpunk Outfit -->
            <!-- Collar/Chest piece (neon) -->
            <path d="M 70 145 Q 70 150 75 155 L 125 155 Q 130 150 130 145 Z"
                  fill="#00ffff" stroke="#00ffff" stroke-width="1.5" opacity="0.8"/>
            <line x1="70" y1="145" x2="130" y2="145" stroke="#ff00ff" stroke-width="1"/>

            <!-- Main body/torso -->
            <ellipse cx="100" cy="180" rx="32" ry="40" fill="#1a1a2e" stroke="#00ffff" stroke-width="2"/>

            <!-- Chest armor piece (glowing) -->
            <rect x="82" y="155" width="36" height="35" rx="4" fill="#00ffff" opacity="0.2" stroke="#00ffff" stroke-width="2"/>
            <line x1="82" y1="170" x2="118" y2="170" stroke="#ff00ff" stroke-width="1" opacity="0.6"/>
            <line x1="82" y1="185" x2="118" y2="185" stroke="#ff00ff" stroke-width="1" opacity="0.6"/>

            <!-- Shoulders/Jacket -->
            <path d="M 68 150 Q 60 165 65 190 L 70 185 Q 75 165 75 150 Z"
                  fill="#16213e" stroke="#00ffff" stroke-width="1.5"/>
            <path d="M 132 150 Q 140 165 135 190 L 130 185 Q 125 165 125 150 Z"
                  fill="#16213e" stroke="#00ffff" stroke-width="1.5"/>

            <!-- Neon accent lines on body -->
            <line x1="68" y1="160" x2="75" y2="165" stroke="#ff00ff" stroke-width="1.5" opacity="0.7"/>
            <line x1="132" y1="160" x2="125" y2="165" stroke="#ff00ff" stroke-width="1.5" opacity="0.7"/>

            <!-- Arm left -->
            <line x1="68" y1="170" x2="50" y2="200" stroke="#1a1a2e" stroke-width="12" stroke-linecap="round"/>
            <line x1="50" y1="200" x2="45" y2="240" stroke="#1a1a2e" stroke-width="10" stroke-linecap="round"/>

            <!-- Arm right -->
            <line x1="132" y1="170" x2="150" y2="200" stroke="#1a1a2e" stroke-width="12" stroke-linecap="round"/>
            <line x1="150" y1="200" x2="155" y2="240" stroke="#1a1a2e" stroke-width="10" stroke-linecap="round"/>

            <!-- Glowing gloves/hands -->
            <circle cx="45" cy="240" r="8" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.9"/>
            <circle cx="155" cy="240" r="8" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.9"/>

            <!-- Skirt/Lower body -->
            <path d="M 70 215 Q 60 240 65 280 L 75 280 Q 70 240 78 215 Z"
                  fill="#2a0845" stroke="#ff00ff" stroke-width="1.5"/>
            <path d="M 130 215 Q 140 240 135 280 L 125 280 Q 130 240 122 215 Z"
                  fill="#2a0845" stroke="#ff00ff" stroke-width="1.5"/>
            <path d="M 78 215 L 122 215 L 130 280 L 70 280 Z"
                  fill="#1a0f2e" stroke="#00ffff" stroke-width="1.5"/>

            <!-- Skirt glow lines -->
            <line x1="75" y1="230" x2="125" y2="230" stroke="#ff00ff" stroke-width="1" opacity="0.5"/>
            <line x1="72" y1="250" x2="128" y2="250" stroke="#ff00ff" stroke-width="1" opacity="0.5"/>

            <!-- Legs/Boots -->
            <line x1="82" y1="280" x2="80" y2="310" stroke="#0a0a0a" stroke-width="8" stroke-linecap="round"/>
            <line x1="118" y1="280" x2="120" y2="310" stroke="#0a0a0a" stroke-width="8" stroke-linecap="round"/>

            <!-- Boot accents (neon) -->
            <circle cx="80" cy="310" r="6" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>
            <circle cx="120" cy="310" r="6" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>

            <!-- Floating energy particles around character -->
            <circle cx="110" cy="70" r="2" fill="#00ffff" opacity="0.7"/>
            <circle cx="55" cy="130" r="2" fill="#ff00ff" opacity="0.7"/>
            <circle cx="145" cy="140" r="2" fill="#00ffff" opacity="0.7"/>
            <circle cx="70" cy="220" r="2" fill="#ff00ff" opacity="0.7"/>
            <circle cx="130" cy="210" r="2" fill="#00ffff" opacity="0.7"/>
        </svg>
    </div>

    <div style="text-align: center; margin-top: 10px;">
        <p style="color: #ff00ff; font-weight: bold; font-size: 14px; margin: 5px 0;">A.R.I.A</p>
        <p style="color: #00ffff; font-size: 11px; margin: 0; letter-spacing: 2px;">AI TRADING GODDESS</p>
    </div>
    """

    st.markdown(aria_svg, unsafe_allow_html=True)


def render_anime_welcome(username="Trader"):
    """
    Renders anime welcome splash screen with ARIA greeting
    Features animated text, speech bubble, and sparkle effects
    Appears at the top of the dashboard
    """

    welcome_html = """
    <style>
        @keyframes sparkle-burst {
            0% {
                opacity: 1;
                transform: translate(0, 0) scale(1);
            }
            100% {
                opacity: 0;
                transform: translate(var(--tx), var(--ty)) scale(0);
            }
        }

        @keyframes text-glow {
            0%, 100% {
                text-shadow: 0 0 5px #00ffff, 0 0 10px #ff00ff;
                color: #ffffff;
            }
            50% {
                text-shadow: 0 0 15px #00ffff, 0 0 25px #ff00ff, 0 0 35px #ff1493;
                color: #ffff00;
            }
        }

        @keyframes slide-in {
            0% {
                opacity: 0;
                transform: translateX(-50px);
            }
            100% {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes bubble-bounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        .welcome-container {
            background: linear-gradient(135deg, #0f0f23 0%, #1a0f2e 100%);
            border: 2px solid #ff00ff;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(255, 0, 255, 0.5), inset 0 0 20px rgba(0, 255, 255, 0.1);
        }

        .welcome-title {
            animation: text-glow 3s ease-in-out infinite;
            font-size: 28px;
            font-weight: 900;
            margin: 10px 0;
            text-align: center;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        .aria-speech-bubble {
            background: linear-gradient(135deg, #00ffff 0%, #ff00ff 100%);
            padding: 2px;
            border-radius: 15px;
            margin: 15px 0;
            position: relative;
            animation: bubble-bounce 2s ease-in-out infinite;
        }

        .bubble-inner {
            background: #0a0a15;
            border-radius: 13px;
            padding: 15px 20px;
            color: #ffffff;
            font-size: 14px;
            font-style: italic;
            letter-spacing: 0.5px;
            position: relative;
            z-index: 2;
        }

        .bubble-tail {
            position: absolute;
            width: 0;
            height: 0;
            border-left: 15px solid transparent;
            border-right: 0px solid transparent;
            border-top: 15px solid #00ffff;
            left: 30px;
            bottom: -12px;
            filter: drop-shadow(-2px 2px 0px #ff00ff);
        }

        .welcome-username {
            color: #ffff00;
            font-weight: bold;
            text-shadow: 0 0 10px #ffff00;
        }

        .sparkle-particle {
            position: absolute;
            width: 8px;
            height: 8px;
            background: radial-gradient(circle, #ffff00 0%, #ff00ff 100%);
            border-radius: 50%;
            pointer-events: none;
        }

        .welcome-subtitle {
            text-align: center;
            color: #00ffff;
            font-size: 12px;
            margin-top: 15px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
    </style>

    <div class="welcome-container" id="welcomeContainer">
        <div class="welcome-title">Welcome Back!</div>

        <div style="position: relative; display: inline-block; width: 100%;">
            <div class="aria-speech-bubble">
                <div class="bubble-tail"></div>
                <div class="bubble-inner">
                    Ready to conquer the markets, <span class="welcome-username">PLACEHOLDER_USERNAME</span>?
                    Let's make those gains!
                </div>
            </div>
        </div>

        <div class="welcome-subtitle">
            Powered by A.R.I.A Trading System
        </div>
    </div>
    """

    st.markdown(welcome_html.replace("PLACEHOLDER_USERNAME", username), unsafe_allow_html=True)


def render_anime_sidebar_decor():
    """
    Adds anime-themed decorative elements to sidebar
    Includes anime icons, Dragon Ball scouter power level, and falling cherry blossoms
    """

    sidebar_decor = """
    <style>
        @keyframes fall {
            0% {
                top: -10px;
                opacity: 1;
            }
            100% {
                top: 100vh;
                opacity: 0;
            }
        }

        @keyframes sway {
            0%, 100% { transform: translateX(0px); }
            50% { transform: translateX(10px); }
        }

        @keyframes scouter-scan {
            0%, 100% {
                color: #00ff00;
                text-shadow: 0 0 10px #00ff00;
            }
            50% {
                color: #ff0000;
                text-shadow: 0 0 15px #ff0000;
            }
        }

        @keyframes power-level-pulse {
            0%, 100% {
                width: 60%;
                box-shadow: 0 0 10px #00ff00;
            }
            50% {
                width: 70%;
                box-shadow: 0 0 20px #ffff00;
            }
        }

        .cherry-blossom {
            position: fixed;
            width: 10px;
            height: 10px;
            background: radial-gradient(circle, #ff69b4 0%, #ff1493 100%);
            border-radius: 50%;
            opacity: 0.6;
            z-index: 0;
            pointer-events: none;
            box-shadow: 0 0 5px #ff1493;
        }

        .anime-nav-icon {
            display: inline-block;
            margin-right: 8px;
            font-size: 16px;
            filter: drop-shadow(0 0 3px #00ffff);
        }

        .scouter-display {
            background: linear-gradient(135deg, #001a00 0%, #003300 100%);
            border: 2px solid #00ff00;
            border-radius: 10px;
            padding: 12px;
            margin: 15px 0;
            text-align: center;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.3), 0 0 15px rgba(0, 255, 0, 0.5);
            animation: scouter-scan 3s ease-in-out infinite;
        }

        .scouter-title {
            color: #00ff00;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 8px;
            text-shadow: 0 0 5px #00ff00;
        }

        .power-meter {
            height: 6px;
            background: #001a00;
            border: 1px solid #00ff00;
            border-radius: 3px;
            overflow: hidden;
            margin: 8px 0;
        }

        .power-bar {
            height: 100%;
            background: linear-gradient(90deg, #00ff00, #ffff00, #ff6600);
            width: 60%;
            border-radius: 3px;
            animation: power-level-pulse 2s ease-in-out infinite;
        }

        .power-value {
            color: #00ff00;
            font-size: 12px;
            font-weight: bold;
            margin-top: 5px;
            font-family: monospace;
            text-shadow: 0 0 5px #00ff00;
        }

        .anime-divider {
            height: 3px;
            background: linear-gradient(90deg, transparent 0%, #ff1493 20%, #00ffff 50%, #ff1493 80%, transparent 100%);
            margin: 15px 0;
            border-radius: 2px;
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.5);
        }

        .nav-item-anime {
            display: flex;
            align-items: center;
            padding: 8px 0;
            color: #ffffff;
            font-size: 13px;
            transition: all 0.3s ease;
        }

        .nav-item-anime:hover {
            color: #00ffff;
            text-shadow: 0 0 10px #00ffff;
            transform: translateX(5px);
        }

        .pirate-flag {
            display: inline-block;
            font-size: 18px;
            margin: 0 5px;
            animation: float 3s ease-in-out infinite;
        }
    </style>

    <!-- Cherry blossom container -->
    <div id="blossomContainer" style="position: relative; width: 100%; height: 10px; margin-bottom: 20px;"></div>

    <div style="background: rgba(15, 15, 35, 0.8); border-radius: 10px; padding: 15px; margin: 10px 0;">
        <!-- Anime divider -->
        <div class="anime-divider"></div>

        <!-- Scouter Power Level Display -->
        <div class="scouter-display">
            <div class="scouter-title">⚡ Power Scanner ⚡</div>
            <div class="power-meter">
                <div class="power-bar"></div>
            </div>
            <div class="power-value" id="powerValue">POWER LEVEL: 9001+</div>
        </div>

        <!-- Navigation with anime icons -->
        <div style="margin-top: 15px;">
            <div class="nav-item-anime">
                <span class="anime-nav-icon">📊</span> Dashboard
            </div>
            <div class="nav-item-anime">
                <span class="anime-nav-icon">⚔️</span> Trading Arena
            </div>
            <div class="nav-item-anime">
                <span class="anime-nav-icon">🎐</span> Portfolio
            </div>
            <div class="nav-item-anime">
                <span class="anime-nav-icon">🔥</span> Positions
            </div>
            <div class="nav-item-anime">
                <span class="anime-nav-icon">💎</span> Strategies
            </div>
        </div>

        <!-- Divider -->
        <div class="anime-divider" style="margin-top: 15px;"></div>

        <!-- Pirate flag nod to One Piece -->
        <div style="text-align: center; margin-top: 10px; font-size: 12px; color: #ff1493;">
            <span class="pirate-flag">🏴</span>
            <span style="letter-spacing: 1px;">NAVIGATE THE SEAS</span>
            <span class="pirate-flag">🏴</span>
        </div>
    </div>

    <script>
        // Generate falling cherry blossoms
        const blossomContainer = document.getElementById('blossomContainer');
        if (blossomContainer) {
            for (let i = 0; i < 8; i++) {
                const blossom = document.createElement('div');
                blossom.className = 'cherry-blossom';
                const left = Math.random() * 100;
                const delay = Math.random() * 3;
                const duration = 4 + Math.random() * 2;

                blossom.style.left = left + '%';
                blossom.style.animation = `fall ${duration}s linear ${delay}s infinite, sway 2s ease-in-out ${delay}s infinite`;
                blossomContainer.appendChild(blossom);
            }
        }

        // Update power level display with random anime values
        function updatePowerLevel() {
            const values = ['OVER 9000!!', 'CRITICAL POWER', 'LEGENDARY MODE', '超パワー', 'SAIYAN BOOST', 'DEMON AWAKENED'];
            const randomValue = values[Math.floor(Math.random() * values.length)];
            document.getElementById('powerValue').textContent = 'POWER LEVEL: ' + randomValue;
        }

        setInterval(updatePowerLevel, 5000);
    </script>
    """

    st.markdown(sidebar_decor, unsafe_allow_html=True)


def inject_anime_css():
    """
    Injects global CSS animations and styles for anime theme
    Includes cherry blossom particles, speech bubbles, katana dividers, and effects
    """

    anime_css = """
    <style>
        /* Global anime-themed styles */

        @keyframes petal-fall {
            0% {
                top: -100px;
                opacity: 1;
                transform: translateX(0) rotateZ(0deg);
            }
            100% {
                top: 100vh;
                opacity: 0;
                transform: translateX(100px) rotateZ(720deg);
            }
        }

        @keyframes speed-lines {
            0% {
                background-position: 0 0;
            }
            100% {
                background-position: 100% 0;
            }
        }

        @keyframes katana-glow {
            0%, 100% {
                box-shadow: 0 4px 0 #ff1493, 0 -4px 0 #ff1493;
            }
            50% {
                box-shadow: 0 4px 10px #ff1493, 0 -4px 10px #ff1493, inset 0 0 10px #ff00ff;
            }
        }

        @keyframes neon-flicker {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }

        @keyframes straw-hat-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Global body enhancement */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #0a0a0f 0%, #1a0f2e 50%, #0f1a2e 100%);
            position: relative;
            overflow: hidden;
        }

        /* Falling cherry blossom particles */
        .anime-petal {
            position: fixed;
            width: 8px;
            height: 8px;
            background: radial-gradient(circle at 30% 30%, #ffb6d9 0%, #ff69b4 50%, #ff1493 100%);
            border-radius: 50%;
            opacity: 0;
            z-index: 0;
            pointer-events: none;
            box-shadow: 0 0 4px #ff1493;
        }

        /* Speech bubbles for ARIA messages */
        .aria-message {
            background: linear-gradient(135deg, #00ffff 0%, #ff00ff 100%);
            padding: 2px;
            border-radius: 12px;
            margin: 10px 0;
            position: relative;
            max-width: 90%;
        }

        .aria-message-inner {
            background: #0a0a15;
            border-radius: 10px;
            padding: 12px 16px;
            color: #ffffff;
            font-size: 13px;
            position: relative;
        }

        .aria-message-tail {
            position: absolute;
            width: 0;
            height: 0;
            border-left: 12px solid transparent;
            border-right: 0px solid transparent;
            border-top: 12px solid #00ffff;
            left: 20px;
            bottom: -10px;
            filter: drop-shadow(-1px 1px 0px #ff00ff);
        }

        /* Katana-style dividers (Demon Slayer inspired) */
        .katana-divider {
            height: 2px;
            background: linear-gradient(90deg, transparent 0%, #ff1493 15%, #00ffff 50%, #ff1493 85%, transparent 100%);
            margin: 20px 0;
            position: relative;
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.6), 0 0 25px rgba(0, 255, 255, 0.3);
            animation: katana-glow 2s ease-in-out infinite;
        }

        .katana-divider::before {
            content: '';
            position: absolute;
            left: 50%;
            top: -5px;
            width: 20px;
            height: 12px;
            background: linear-gradient(135deg, #ff1493 0%, #ff00ff 100%);
            transform: translateX(-50%) rotateZ(45deg);
            box-shadow: 0 0 10px #ff1493;
        }

        /* Speed lines on hover effects */
        .speed-lines {
            position: relative;
            overflow: hidden;
        }

        .speed-lines::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: repeating-linear-gradient(
                90deg,
                transparent,
                transparent 10px,
                rgba(255, 0, 255, 0.1) 10px,
                rgba(255, 0, 255, 0.1) 20px
            );
            opacity: 0;
            animation: speed-lines 0.6s ease-in-out;
            pointer-events: none;
        }

        /* Anime-style metric cards */
        .anime-card {
            background: linear-gradient(135deg, #1a0f2e 0%, #2a1a4e 100%);
            border: 2px solid #ff00ff;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 0 20px rgba(255, 0, 255, 0.4), inset 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
            overflow: hidden;
        }

        .anime-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.3), transparent);
            animation: neon-flicker 3s ease-in-out infinite;
        }

        /* Straw hat subtle accent (One Piece reference) */
        .straw-hat-accent {
            display: inline-block;
            font-size: 14px;
            animation: straw-hat-spin 10s linear infinite;
            margin: 0 5px;
        }

        /* Neon text effects */
        .neon-text {
            color: #00ffff;
            text-shadow:
                0 0 5px #00ffff,
                0 0 10px #00ffff,
                0 0 20px #ff00ff,
                0 0 30px #ff00ff;
            letter-spacing: 2px;
            font-weight: bold;
        }

        /* Glowing buttons */
        .anime-button {
            background: linear-gradient(135deg, #ff00ff 0%, #00ffff 100%);
            color: #000000;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.6);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .anime-button:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.8), 0 0 35px rgba(255, 0, 255, 0.8);
            transform: scale(1.05);
            letter-spacing: 1px;
        }

        .anime-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.3);
            animation: speed-lines 0.6s ease-in-out;
        }

        .anime-button:active {
            transform: scale(0.95);
        }

        /* Anime-style input fields */
        input[type="text"],
        input[type="number"],
        select,
        textarea {
            background: rgba(15, 15, 35, 0.8) !important;
            color: #00ffff !important;
            border: 1.5px solid #ff00ff !important;
            border-radius: 6px !important;
            padding: 8px 12px !important;
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.3) inset !important;
        }

        input[type="text"]:focus,
        input[type="number"]:focus,
        select:focus,
        textarea:focus {
            outline: none !important;
            border: 1.5px solid #00ffff !important;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.6), inset 0 0 10px rgba(0, 255, 255, 0.2) !important;
            background: rgba(15, 15, 35, 0.95) !important;
        }

        /* Placeholder text styling */
        input::placeholder,
        textarea::placeholder {
            color: rgba(255, 0, 255, 0.5) !important;
        }
    </style>

    <script>
        // Generate falling petals on page load
        function createFallingPetals() {
            const petalsContainer = document.querySelector('[data-testid="stAppViewContainer"]');
            if (!petalsContainer) return;

            for (let i = 0; i < 12; i++) {
                const petal = document.createElement('div');
                petal.className = 'anime-petal';
                petal.style.left = Math.random() * 100 + '%';
                petal.style.top = Math.random() * -100 + 'px';
                const duration = 8 + Math.random() * 4;
                const delay = Math.random() * 3;

                petal.style.animation = `petal-fall ${duration}s linear ${delay}s infinite`;
                petalsContainer.appendChild(petal);

                // Recreate petals at intervals
                setTimeout(() => {
                    setInterval(() => {
                        const newPetal = petal.cloneNode(true);
                        newPetal.style.left = Math.random() * 100 + '%';
                        newPetal.style.top = Math.random() * -100 + 'px';
                        petalsContainer.appendChild(newPetal);

                        // Clean up old petals to prevent memory leaks
                        setTimeout(() => newPetal.remove(), duration * 1000 + 2000);
                    }, 2000);
                }, delay * 1000);
            }
        }

        // Run when DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', createFallingPetals);
        } else {
            createFallingPetals();
        }
    </script>
    """

    st.markdown(anime_css, unsafe_allow_html=True)


# Convenience function to apply full anime theme
def apply_anime_theme():
    """
    Applies the complete anime theme to the Streamlit app
    Call this once at the top of your main app
    """
    inject_anime_css()
