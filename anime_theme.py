"""
Anime Visual Theme Module for Alpha FX Hub
N.A.M.I AI assistant character + immersive cyberpunk anime aesthetics
All visual components use components.html() for reliable rendering
"""

import streamlit as st
import streamlit.components.v1 as components


def render_nami_character():
    """
    Renders N.A.M.I character in the sidebar with glowing anime aesthetic
    Beautiful cyberpunk anime girl with neon effects
    """
    nami_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: transparent; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; }

@keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-8px); } }
@keyframes glow-pulse { 0%, 100% { filter: drop-shadow(0 0 8px #00ffff) drop-shadow(0 0 15px #ff00ff); } 50% { filter: drop-shadow(0 0 18px #00ffff) drop-shadow(0 0 30px #ff00ff); } }
@keyframes eye-sparkle { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
@keyframes ring-rotate { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
@keyframes particle-up { 0% { transform: translateY(0) scale(1); opacity: 0.8; } 100% { transform: translateY(-40px) scale(0); opacity: 0; } }

.nami-wrap { animation: float 3s ease-in-out infinite; text-align: center; position: relative; }
.nami-svg { animation: glow-pulse 2s ease-in-out infinite; }
.nami-eye { animation: eye-sparkle 1.5s ease-in-out infinite; }

.orbit-ring {
    position: absolute; top: 50%; left: 50%; width: 180px; height: 180px;
    margin: -90px 0 0 -90px; border: 1px solid rgba(0,255,255,0.15);
    border-radius: 50%; animation: ring-rotate 8s linear infinite;
}
.orbit-ring::before {
    content: ''; position: absolute; top: -4px; left: 50%; width: 8px; height: 8px;
    background: #00ffff; border-radius: 50%; box-shadow: 0 0 10px #00ffff;
}
.orbit-ring-2 {
    position: absolute; top: 50%; left: 50%; width: 200px; height: 200px;
    margin: -100px 0 0 -100px; border: 1px solid rgba(255,0,255,0.1);
    border-radius: 50%; animation: ring-rotate 12s linear infinite reverse;
}
.orbit-ring-2::before {
    content: ''; position: absolute; bottom: -3px; right: 20%; width: 6px; height: 6px;
    background: #ff00ff; border-radius: 50%; box-shadow: 0 0 8px #ff00ff;
}

.particle {
    position: absolute; width: 4px; height: 4px; border-radius: 50%;
    animation: particle-up 2s ease-out infinite;
}

.nami-label {
    color: #ff00ff; font-weight: bold; font-size: 13px; margin-top: 8px;
    font-family: 'Segoe UI', sans-serif; text-shadow: 0 0 10px #ff00ff;
    letter-spacing: 2px;
}
.nami-sub {
    color: #00ffff; font-size: 8px; letter-spacing: 2px;
    font-family: monospace; text-shadow: 0 0 5px #00ffff; margin-top: 2px;
}
</style>
</head>
<body>
<div class="nami-wrap">
    <div class="orbit-ring"></div>
    <div class="orbit-ring-2"></div>

    <div class="particle" style="left:20%;bottom:30%;background:#00ffff;animation-delay:0s;"></div>
    <div class="particle" style="left:70%;bottom:40%;background:#ff00ff;animation-delay:0.5s;"></div>
    <div class="particle" style="left:40%;bottom:20%;background:#ffff00;animation-delay:1s;"></div>
    <div class="particle" style="left:80%;bottom:50%;background:#00ffff;animation-delay:1.5s;"></div>

    <svg viewBox="0 0 200 320" width="150" height="245" class="nami-svg">
        <defs>
            <radialGradient id="aG" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color:#ff00ff;stop-opacity:0.25"/>
                <stop offset="100%" style="stop-color:#00ffff;stop-opacity:0"/>
            </radialGradient>
            <linearGradient id="hG" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ff1493"/><stop offset="50%" style="stop-color:#ff69b4"/><stop offset="100%" style="stop-color:#ba55d3"/>
            </linearGradient>
            <linearGradient id="sG" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ffe4c4"/><stop offset="100%" style="stop-color:#ffd4a3"/>
            </linearGradient>
            <filter id="neonGlow">
                <feGaussianBlur stdDeviation="2" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
        </defs>
        <circle cx="100" cy="160" r="95" fill="url(#aG)" opacity="0.4"/>
        <!-- Hair -->
        <path d="M 55 75 Q 45 100 50 145 Q 45 175 65 210 L 65 250 Q 65 270 78 285 L 122 285 Q 135 270 135 250 L 135 210 Q 155 175 150 145 Q 155 100 145 75 Z" fill="url(#hG)" stroke="#ff1493" stroke-width="1"/>
        <path d="M 62 88 Q 55 125 62 165" stroke="#ff69b4" stroke-width="2" fill="none" opacity="0.7"/>
        <path d="M 138 88 Q 145 125 138 165" stroke="#ba55d3" stroke-width="2" fill="none" opacity="0.7"/>
        <path d="M 72 82 Q 68 118 78 158" stroke="#fff" stroke-width="1" fill="none" opacity="0.4"/>
        <!-- Face -->
        <circle cx="100" cy="108" r="36" fill="url(#sG)" stroke="#ff69b4" stroke-width="0.8"/>
        <!-- Eyes -->
        <g class="nami-eye" filter="url(#neonGlow)">
            <ellipse cx="82" cy="104" rx="9" ry="13" fill="#fff" stroke="#00ffff" stroke-width="1.5"/>
            <ellipse cx="82" cy="106" rx="6" ry="8" fill="#0088ff"/>
            <circle cx="82" cy="106" r="4" fill="#00ffff" opacity="0.9"/>
            <circle cx="80" cy="103" r="2.5" fill="#fff"/>
            <circle cx="84" cy="108" r="1.2" fill="#fff" opacity="0.6"/>
            <ellipse cx="118" cy="104" rx="9" ry="13" fill="#fff" stroke="#00ffff" stroke-width="1.5"/>
            <ellipse cx="118" cy="106" rx="6" ry="8" fill="#0088ff"/>
            <circle cx="118" cy="106" r="4" fill="#00ffff" opacity="0.9"/>
            <circle cx="116" cy="103" r="2.5" fill="#fff"/>
            <circle cx="120" cy="108" r="1.2" fill="#fff" opacity="0.6"/>
        </g>
        <!-- Eyebrows -->
        <path d="M 73 93 Q 82 89 91 92" stroke="#ff1493" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <path d="M 109 92 Q 118 89 127 93" stroke="#ff1493" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <!-- Nose + Mouth -->
        <path d="M 98 112 Q 100 116 102 112" stroke="#ffb6c1" stroke-width="1" fill="none"/>
        <path d="M 88 124 Q 100 131 112 124" stroke="#ff1493" stroke-width="2" fill="none" stroke-linecap="round"/>
        <path d="M 93 124 Q 100 127 107 124" fill="#ff69b4" opacity="0.3"/>
        <!-- Blush -->
        <ellipse cx="72" cy="118" rx="8" ry="4" fill="#ff69b4" opacity="0.25"/>
        <ellipse cx="128" cy="118" rx="8" ry="4" fill="#ff69b4" opacity="0.25"/>
        <!-- Outfit -->
        <path d="M 68 144 L 132 144 L 135 155 L 65 155 Z" fill="#00ffff" stroke="#00ffff" stroke-width="1" opacity="0.8"/>
        <ellipse cx="100" cy="182" rx="34" ry="42" fill="#0d0b1e" stroke="#00ffff" stroke-width="2"/>
        <rect x="80" y="155" width="40" height="38" rx="5" fill="rgba(0,255,255,0.12)" stroke="#00ffff" stroke-width="1.5"/>
        <!-- Neon lines on outfit -->
        <line x1="80" y1="170" x2="120" y2="170" stroke="#ff00ff" stroke-width="0.8" opacity="0.5"/>
        <line x1="80" y1="183" x2="120" y2="183" stroke="#ff00ff" stroke-width="0.8" opacity="0.5"/>
        <!-- Arms -->
        <line x1="66" y1="168" x2="48" y2="200" stroke="#0d0b1e" stroke-width="11" stroke-linecap="round"/>
        <line x1="48" y1="200" x2="42" y2="235" stroke="#0d0b1e" stroke-width="9" stroke-linecap="round"/>
        <line x1="134" y1="168" x2="152" y2="200" stroke="#0d0b1e" stroke-width="11" stroke-linecap="round"/>
        <line x1="152" y1="200" x2="158" y2="235" stroke="#0d0b1e" stroke-width="9" stroke-linecap="round"/>
        <circle cx="42" cy="235" r="7" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.85"/>
        <circle cx="158" cy="235" r="7" fill="#00ffff" stroke="#ff00ff" stroke-width="1.5" opacity="0.85"/>
        <!-- Skirt -->
        <path d="M 76 218 L 124 218 L 132 282 L 68 282 Z" fill="#1a0f2e" stroke="#ff00ff" stroke-width="1.5"/>
        <line x1="73" y1="240" x2="127" y2="240" stroke="#00ffff" stroke-width="0.8" opacity="0.4"/>
        <line x1="70" y1="260" x2="130" y2="260" stroke="#00ffff" stroke-width="0.8" opacity="0.4"/>
        <!-- Legs -->
        <line x1="82" y1="282" x2="80" y2="312" stroke="#0a0a0a" stroke-width="7" stroke-linecap="round"/>
        <line x1="118" y1="282" x2="120" y2="312" stroke="#0a0a0a" stroke-width="7" stroke-linecap="round"/>
        <circle cx="80" cy="312" r="5" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>
        <circle cx="120" cy="312" r="5" fill="#00ffff" stroke="#ff00ff" stroke-width="1" opacity="0.8"/>
    </svg>
    <div class="nami-label">N.A.M.I</div>
    <div class="nami-sub">NEURAL ALGORITHMIC MARKET INTELLIGENCE</div>
</div>
</body>
</html>
"""
    components.html(nami_html, height=310, scrolling=False)


def render_anime_welcome(username="Trader"):
    """
    Renders immersive anime welcome splash with animated particles,
    gradient waves, and N.A.M.I greeting
    """
    welcome_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: transparent; font-family: 'Segoe UI', sans-serif; padding: 8px; overflow: hidden; }}

@keyframes gradient-shift {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
@keyframes text-glow {{
    0%, 100% {{ text-shadow: 0 0 10px #00ffff, 0 0 20px #ff00ff; }}
    50% {{ text-shadow: 0 0 20px #00ffff, 0 0 40px #ff00ff, 0 0 60px #ff1493; color: #fff; }}
}}
@keyframes bubble-float {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-4px); }}
}}
@keyframes wave {{
    0% {{ transform: translateX(-100%); }}
    100% {{ transform: translateX(100%); }}
}}
@keyframes sparkle {{
    0%, 100% {{ opacity: 0; transform: scale(0); }}
    50% {{ opacity: 1; transform: scale(1); }}
}}
@keyframes border-flow {{
    0% {{ border-image-source: linear-gradient(0deg, #ff00ff, #00ffff, #ff00ff); }}
    33% {{ border-image-source: linear-gradient(120deg, #00ffff, #ff00ff, #ffff00); }}
    66% {{ border-image-source: linear-gradient(240deg, #ff00ff, #ffff00, #00ffff); }}
    100% {{ border-image-source: linear-gradient(360deg, #ff00ff, #00ffff, #ff00ff); }}
}}

.welcome-box {{
    background: linear-gradient(-45deg, #0a0a1a, #1a0f2e, #0f1a2e, #1a0a2e);
    background-size: 400% 400%;
    animation: gradient-shift 8s ease infinite;
    border: 2px solid;
    border-image: linear-gradient(45deg, #ff00ff, #00ffff, #ff00ff) 1;
    border-radius: 0px;
    padding: 25px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 30px rgba(255,0,255,0.4), 0 0 60px rgba(0,255,255,0.15), inset 0 0 30px rgba(0,255,255,0.08);
}}

.wave-bar {{
    position: absolute; bottom: 0; left: 0; width: 200%; height: 3px;
    background: linear-gradient(90deg, transparent, #00ffff, #ff00ff, #00ffff, transparent);
    animation: wave 3s linear infinite;
}}
.wave-bar-2 {{
    position: absolute; top: 0; left: 0; width: 200%; height: 2px;
    background: linear-gradient(90deg, transparent, #ff00ff, #00ffff, #ff00ff, transparent);
    animation: wave 4s linear infinite reverse;
}}

.welcome-title {{
    font-family: 'Orbitron', sans-serif;
    animation: text-glow 3s ease-in-out infinite;
    font-size: 28px; font-weight: 900; text-align: center; letter-spacing: 4px;
    text-transform: uppercase; color: #fff; margin-bottom: 18px;
}}

.speech-bubble {{
    background: linear-gradient(135deg, rgba(0,255,255,0.15), rgba(255,0,255,0.15));
    border: 1px solid rgba(0,255,255,0.4);
    border-radius: 12px; padding: 16px 20px;
    animation: bubble-float 3s ease-in-out infinite;
    position: relative;
    backdrop-filter: blur(5px);
}}
.speech-bubble::before {{
    content: ''; position: absolute; bottom: -8px; left: 30px;
    width: 0; height: 0; border-left: 10px solid transparent;
    border-right: 10px solid transparent; border-top: 8px solid rgba(0,255,255,0.4);
}}
.speech-text {{
    color: #e0e8ff; font-size: 15px; font-style: italic; letter-spacing: 0.3px; line-height: 1.5;
}}
.username {{
    color: #ffff00; font-weight: bold; text-shadow: 0 0 12px #ffff00;
    font-style: normal; font-size: 16px;
}}

.subtitle {{
    text-align: center; color: #00ffff; font-size: 10px; margin-top: 15px;
    letter-spacing: 3px; text-transform: uppercase; text-shadow: 0 0 5px #00ffff;
    font-family: monospace;
}}

.sparkle {{
    position: absolute; width: 6px; height: 6px; border-radius: 50%;
    animation: sparkle 2s ease-in-out infinite;
}}
.corner-deco {{
    position: absolute; width: 20px; height: 20px;
    border-color: #00ffff; border-style: solid;
}}
.corner-tl {{ top: 8px; left: 8px; border-width: 2px 0 0 2px; }}
.corner-tr {{ top: 8px; right: 8px; border-width: 2px 2px 0 0; }}
.corner-bl {{ bottom: 8px; left: 8px; border-width: 0 0 2px 2px; }}
.corner-br {{ bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }}
</style>
</head>
<body>
<div class="welcome-box">
    <div class="wave-bar"></div>
    <div class="wave-bar-2"></div>
    <div class="corner-deco corner-tl"></div>
    <div class="corner-deco corner-tr"></div>
    <div class="corner-deco corner-bl"></div>
    <div class="corner-deco corner-br"></div>

    <div class="sparkle" style="top:15%;left:10%;background:#ff00ff;animation-delay:0s;"></div>
    <div class="sparkle" style="top:25%;right:15%;background:#00ffff;animation-delay:0.4s;"></div>
    <div class="sparkle" style="bottom:20%;left:20%;background:#ffff00;animation-delay:0.8s;"></div>
    <div class="sparkle" style="bottom:30%;right:10%;background:#ff00ff;animation-delay:1.2s;"></div>
    <div class="sparkle" style="top:50%;left:50%;background:#00ffff;animation-delay:1.6s;"></div>
    <div class="sparkle" style="top:10%;right:30%;background:#ffff00;animation-delay:2s;"></div>

    <div class="welcome-title">Welcome Back!</div>
    <div class="speech-bubble">
        <div class="speech-text">
            Ready to navigate the markets, <span class="username">{username}</span>? Let's find that treasure! &#x1F3F4;&#x200D;&#x2620;&#xFE0F;
        </div>
    </div>
    <div class="subtitle">&#x26A1; Powered by N.A.M.I &mdash; Neural Algorithmic Market Intelligence &#x26A1;</div>
</div>
</body>
</html>
"""
    components.html(welcome_html, height=230, scrolling=False)


def render_anime_sidebar_decor():
    """
    Sidebar decoration — animated power scanner with particles
    """
    sidebar_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: transparent; font-family: 'Segoe UI', sans-serif; padding: 4px; overflow: hidden; }

@keyframes scan { 0%, 100% { color: #00ff00; text-shadow: 0 0 10px #00ff00; } 50% { color: #ff3300; text-shadow: 0 0 15px #ff3300; } }
@keyframes power-pulse { 0%, 100% { width: 55%; } 50% { width: 80%; } }
@keyframes katana { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; box-shadow: 0 0 15px #ff1493; } }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.decor { background: rgba(10,10,25,0.9); border-radius: 10px; padding: 10px; border: 1px solid rgba(0,255,255,0.2); }
.divider { height: 2px; background: linear-gradient(90deg, transparent, #ff1493, #00ffff, #ff1493, transparent); margin: 8px 0; animation: katana 2s ease-in-out infinite; }
.scouter {
    background: linear-gradient(135deg, #001a00, #002200); border: 1px solid #00ff00;
    border-radius: 8px; padding: 10px; text-align: center;
    box-shadow: inset 0 0 8px rgba(0,255,0,0.2), 0 0 12px rgba(0,255,0,0.3);
    animation: scan 3s ease-in-out infinite;
}
.scouter-title { color: #00ff00; font-size: 9px; font-weight: bold; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px; }
.power-meter { height: 5px; background: #001a00; border: 1px solid #00ff00; border-radius: 3px; overflow: hidden; margin: 5px 0; }
.power-bar { height: 100%; background: linear-gradient(90deg, #00ff00, #ffff00, #ff6600); border-radius: 3px; animation: power-pulse 2s ease-in-out infinite; }
.power-val { color: #00ff00; font-size: 10px; font-weight: bold; font-family: monospace; }
.status-row { display: flex; justify-content: space-between; margin-top: 8px; font-size: 9px; }
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px; animation: blink 1.5s ease-in-out infinite; }
.online { background: #00ff00; box-shadow: 0 0 6px #00ff00; }
.scanning { background: #ffff00; box-shadow: 0 0 6px #ffff00; animation-delay: 0.5s; }
.pirate { text-align: center; margin-top: 6px; font-size: 10px; color: #ff1493; letter-spacing: 1px; text-shadow: 0 0 5px #ff1493; }
</style>
</head>
<body>
<div class="decor">
    <div class="divider"></div>
    <div class="scouter">
        <div class="scouter-title">&#x26A1; Market Scanner &#x26A1;</div>
        <div class="power-meter"><div class="power-bar"></div></div>
        <div class="power-val">POWER: OVER 9000!!</div>
        <div class="status-row">
            <span><span class="status-dot online"></span><span style="color:#00ff00;">ONLINE</span></span>
            <span><span class="status-dot scanning"></span><span style="color:#ffff00;">SCANNING</span></span>
        </div>
    </div>
    <div class="divider"></div>
    <div class="pirate">&#x1F3F4; NAVIGATE MARKETS &#x1F3F4;</div>
</div>
</body>
</html>
"""
    components.html(sidebar_html, height=155, scrolling=False)


def render_cyberpunk_ambient():
    """
    Renders a cyberpunk ambient sound player using Web Audio API.
    Works inside components.html() iframe — JavaScript runs here!
    Plays soft synth pad + subtle rain ambiance on click.
    """
    sound_html = """
<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: transparent; font-family: 'Segoe UI', sans-serif; }

.sound-btn {
    width: 100%; padding: 10px 16px; border: 1px solid #ff00ff;
    border-radius: 8px; cursor: pointer; transition: all 0.3s ease;
    background: linear-gradient(135deg, rgba(255,0,255,0.1), rgba(0,255,255,0.1));
    color: #00ffff; font-size: 12px; font-weight: bold; letter-spacing: 1px;
    text-align: center; position: relative; overflow: hidden;
}
.sound-btn:hover {
    background: linear-gradient(135deg, rgba(255,0,255,0.25), rgba(0,255,255,0.25));
    box-shadow: 0 0 15px rgba(0,255,255,0.3);
}
.sound-btn.playing { border-color: #00ffff; color: #00ffff; }
.sound-btn.playing::before {
    content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(0,255,255,0.15), transparent);
    animation: shimmer 2s linear infinite;
}
@keyframes shimmer { 0% { left: -100%; } 100% { left: 100%; } }

.eq-bars { display: inline-flex; align-items: flex-end; gap: 2px; height: 14px; margin-right: 8px; vertical-align: middle; }
.eq-bar { width: 3px; background: #00ffff; border-radius: 1px; animation: eq 0.8s ease-in-out infinite alternate; }
.eq-bar:nth-child(1) { height: 4px; animation-delay: 0s; }
.eq-bar:nth-child(2) { height: 8px; animation-delay: 0.15s; }
.eq-bar:nth-child(3) { height: 12px; animation-delay: 0.3s; }
.eq-bar:nth-child(4) { height: 6px; animation-delay: 0.45s; }
.eq-bar:nth-child(5) { height: 10px; animation-delay: 0.6s; }
@keyframes eq { 0% { transform: scaleY(0.3); } 100% { transform: scaleY(1); } }
.eq-hidden { display: none; }
</style>
</head>
<body>
<button class="sound-btn" id="soundBtn" onclick="toggleSound()">
    <span class="eq-bars eq-hidden" id="eqBars">
        <span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span><span class="eq-bar"></span>
    </span>
    <span id="btnText">&#x1F50A; CYBERPUNK AMBIENT</span>
</button>

<script>
let audioCtx = null;
let isPlaying = false;
let nodes = [];

function createCyberpunkAmbient(ctx) {
    const master = ctx.createGain();
    master.gain.value = 0.12;
    master.connect(ctx.destination);

    // Deep pad synth
    function createPad(freq, detune) {
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = freq;
        osc.detune.value = detune;
        const gain = ctx.createGain();
        gain.gain.value = 0.06;
        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 400;
        filter.Q.value = 2;
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(master);
        osc.start();

        // Slow LFO on filter
        const lfo = ctx.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = 0.08;
        const lfoGain = ctx.createGain();
        lfoGain.gain.value = 150;
        lfo.connect(lfoGain);
        lfoGain.connect(filter.frequency);
        lfo.start();

        return [osc, lfo];
    }

    // Subtle noise (rain-like texture)
    const bufferSize = ctx.sampleRate * 2;
    const noiseBuffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const output = noiseBuffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
        output[i] = (Math.random() * 2 - 1) * 0.015;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;
    noise.loop = true;
    const noiseFilter = ctx.createBiquadFilter();
    noiseFilter.type = 'bandpass';
    noiseFilter.frequency.value = 3000;
    noiseFilter.Q.value = 0.5;
    const noiseGain = ctx.createGain();
    noiseGain.gain.value = 0.4;
    noise.connect(noiseFilter);
    noiseFilter.connect(noiseGain);
    noiseGain.connect(master);
    noise.start();

    // Create chord: Cm7 (C Eb G Bb) — moody cyberpunk
    const pad1 = createPad(65.41, 0);    // C2
    const pad2 = createPad(77.78, 5);    // Eb2
    const pad3 = createPad(98.00, -3);   // G2
    const pad4 = createPad(116.54, 7);   // Bb2

    // Subtle high shimmer
    const shimmer = ctx.createOscillator();
    shimmer.type = 'sine';
    shimmer.frequency.value = 523.25; // C5
    const shimGain = ctx.createGain();
    shimGain.gain.value = 0.008;
    const shimLfo = ctx.createOscillator();
    shimLfo.frequency.value = 0.3;
    const shimLfoGain = ctx.createGain();
    shimLfoGain.gain.value = 0.005;
    shimLfo.connect(shimLfoGain);
    shimLfoGain.connect(shimGain.gain);
    shimmer.connect(shimGain);
    shimGain.connect(master);
    shimmer.start();
    shimLfo.start();

    return { master, allNodes: [...pad1, ...pad2, ...pad3, ...pad4, noise, shimmer, shimLfo] };
}

function toggleSound() {
    const btn = document.getElementById('soundBtn');
    const eq = document.getElementById('eqBars');
    const txt = document.getElementById('btnText');

    if (!isPlaying) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const ambient = createCyberpunkAmbient(audioCtx);
        nodes = ambient.allNodes;
        btn.classList.add('playing');
        eq.classList.remove('eq-hidden');
        txt.textContent = 'AMBIENT ON';
        isPlaying = true;
    } else {
        if (audioCtx) {
            audioCtx.close();
            audioCtx = null;
        }
        nodes = [];
        btn.classList.remove('playing');
        eq.classList.add('eq-hidden');
        txt.textContent = '\\u{1F50A} CYBERPUNK AMBIENT';
        isPlaying = false;
    }
}
</script>
</body>
</html>
"""
    components.html(sound_html, height=50, scrolling=False)


def inject_anime_css():
    """
    Injects global CSS animations — floating particles, neon effects,
    smoother fonts, less 'coding' feel
    """
    anime_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&display=swap');

@keyframes subtle-glow {
    0%, 100% { box-shadow: 0 0 10px rgba(0,255,255,0.15); }
    50% { box-shadow: 0 0 25px rgba(0,255,255,0.3), 0 0 50px rgba(255,0,255,0.1); }
}
@keyframes float-particle {
    0% { transform: translateY(100vh) rotate(0deg); opacity: 0; }
    10% { opacity: 0.6; }
    90% { opacity: 0.6; }
    100% { transform: translateY(-10vh) rotate(720deg); opacity: 0; }
}
@keyframes border-breathe {
    0%, 100% { border-color: rgba(0,255,255,0.3); }
    50% { border-color: rgba(255,0,255,0.5); }
}

/* Smoother, less coding-like body font */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #080810 0%, #0f0a1e 40%, #0a1020 100%) !important;
}

/* Override monospace feel with cleaner fonts */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    font-family: 'Rajdhani', 'Segoe UI', sans-serif !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px !important;
}

/* Keep headings in Orbitron but cleaner */
h1, h2, h3 {
    font-family: 'Orbitron', sans-serif !important;
}

/* Smoother cards */
[data-testid="stExpander"],
.stTabs [data-baseweb="tab-panel"] {
    animation: subtle-glow 4s ease-in-out infinite;
    border-radius: 12px !important;
}

/* Animated border on main content */
[data-testid="stMainBlockContainer"] {
    animation: border-breathe 6s ease-in-out infinite;
}

/* Sidebar glow */
[data-testid="stSidebar"] {
    box-shadow: 2px 0 30px rgba(0,255,255,0.08), inset -2px 0 20px rgba(255,0,255,0.05) !important;
}

/* Button hover glow enhancement */
.stButton > button:hover {
    box-shadow: 0 0 25px rgba(0,255,255,0.5), 0 0 50px rgba(255,0,255,0.2) !important;
    transition: all 0.3s ease !important;
}

/* Tabs styling - more anime feel */
[data-testid="stTabs"] [role="tablist"] button[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,255,255,0.1), rgba(255,0,255,0.1)) !important;
    border-radius: 8px 8px 0 0 !important;
}

/* Selectbox and input - softer glow */
[data-baseweb="select"] {
    transition: all 0.3s ease !important;
}
[data-baseweb="select"]:hover {
    box-shadow: 0 0 15px rgba(0,255,255,0.2) !important;
}
</style>"""
    st.markdown(anime_css, unsafe_allow_html=True)


def apply_anime_theme():
    """Convenience function to apply the anime theme."""
    inject_anime_css()
