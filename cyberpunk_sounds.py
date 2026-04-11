"""
Cyberpunk Sound Effects Module for Alpha FX Hub
Uses Web Audio API to synthesize futuristic UI sounds.
No external audio files needed — all sounds are generated in-browser.
"""

import streamlit as st
import streamlit.components.v1 as components


def inject_cyberpunk_sounds():
    """
    Injects a JavaScript audio engine into the Streamlit page.
    Generates cyberpunk-style synth sounds for:
      - Hover over buttons/interactive elements
      - Click on buttons/nav items
      - Page transitions
      - Success/error feedback tones
    All sounds are synthesized using Web Audio API oscillators + filters.
    """

    sound_js = """
    <script>
    (function() {
        // Prevent double-init
        if (window.__cyberpunkAudioInit) return;
        window.__cyberpunkAudioInit = true;

        // Lazy-init AudioContext on first user interaction (browser policy)
        let audioCtx = null;

        function getCtx() {
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            return audioCtx;
        }

        // ─── HOVER SOUND: soft high-freq tick ───
        function playHover() {
            try {
                const ctx = getCtx();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                const filter = ctx.createBiquadFilter();

                osc.type = 'sine';
                osc.frequency.setValueAtTime(2800, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(3400, ctx.currentTime + 0.04);

                filter.type = 'highpass';
                filter.frequency.value = 2000;

                gain.gain.setValueAtTime(0.06, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);

                osc.connect(filter);
                filter.connect(gain);
                gain.connect(ctx.destination);

                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.06);
            } catch(e) {}
        }

        // ─── CLICK SOUND: punchy cyberpunk blip ───
        function playClick() {
            try {
                const ctx = getCtx();

                // Layer 1: sharp attack
                const osc1 = ctx.createOscillator();
                const gain1 = ctx.createGain();
                osc1.type = 'square';
                osc1.frequency.setValueAtTime(1200, ctx.currentTime);
                osc1.frequency.exponentialRampToValueAtTime(600, ctx.currentTime + 0.08);
                gain1.gain.setValueAtTime(0.1, ctx.currentTime);
                gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1);
                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.start(ctx.currentTime);
                osc1.stop(ctx.currentTime + 0.1);

                // Layer 2: sub bass thump
                const osc2 = ctx.createOscillator();
                const gain2 = ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.setValueAtTime(180, ctx.currentTime);
                osc2.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.12);
                gain2.gain.setValueAtTime(0.12, ctx.currentTime);
                gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.start(ctx.currentTime);
                osc2.stop(ctx.currentTime + 0.12);
            } catch(e) {}
        }

        // ─── NAV CLICK: sweeping transition whoosh ───
        function playNavClick() {
            try {
                const ctx = getCtx();

                // Sweep oscillator
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                const filter = ctx.createBiquadFilter();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(400, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(2000, ctx.currentTime + 0.06);
                osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.15);

                filter.type = 'bandpass';
                filter.frequency.setValueAtTime(1200, ctx.currentTime);
                filter.Q.value = 2;

                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.linearRampToValueAtTime(0.12, ctx.currentTime + 0.04);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18);

                osc.connect(filter);
                filter.connect(gain);
                gain.connect(ctx.destination);

                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.18);

                // Confirm ping
                const ping = ctx.createOscillator();
                const pingGain = ctx.createGain();
                ping.type = 'sine';
                ping.frequency.setValueAtTime(1800, ctx.currentTime + 0.05);
                pingGain.gain.setValueAtTime(0, ctx.currentTime);
                pingGain.gain.linearRampToValueAtTime(0.07, ctx.currentTime + 0.06);
                pingGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
                ping.connect(pingGain);
                pingGain.connect(ctx.destination);
                ping.start(ctx.currentTime + 0.05);
                ping.stop(ctx.currentTime + 0.2);
            } catch(e) {}
        }

        // ─── SUCCESS TONE: ascending arpeggio ───
        function playSuccess() {
            try {
                const ctx = getCtx();
                const notes = [800, 1000, 1200, 1600];
                notes.forEach((freq, i) => {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.value = freq;
                    gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.06);
                    gain.gain.linearRampToValueAtTime(0.08, ctx.currentTime + i * 0.06 + 0.02);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.06 + 0.12);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + i * 0.06);
                    osc.stop(ctx.currentTime + i * 0.06 + 0.12);
                });
            } catch(e) {}
        }

        // ─── ERROR TONE: descending buzz ───
        function playError() {
            try {
                const ctx = getCtx();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'square';
                osc.frequency.setValueAtTime(400, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.2);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.25);
            } catch(e) {}
        }

        // ─── DATA SCAN SOUND: digital data stream ───
        function playDataScan() {
            try {
                const ctx = getCtx();
                for (let i = 0; i < 5; i++) {
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    const freq = 1500 + Math.random() * 2000;
                    osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.03);
                    gain.gain.setValueAtTime(0.04, ctx.currentTime + i * 0.03);
                    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.03 + 0.04);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(ctx.currentTime + i * 0.03);
                    osc.stop(ctx.currentTime + i * 0.03 + 0.04);
                }
            } catch(e) {}
        }

        // Expose globally for manual triggers
        window.cyberpunkSFX = {
            hover: playHover,
            click: playClick,
            navClick: playNavClick,
            success: playSuccess,
            error: playError,
            dataScan: playDataScan
        };

        // ─── AUTO-ATTACH TO STREAMLIT ELEMENTS ───
        // Use MutationObserver to catch dynamically rendered elements

        let hoverThrottle = 0;

        function attachSounds() {
            // Buttons
            document.querySelectorAll('button:not([data-sfx])').forEach(btn => {
                btn.setAttribute('data-sfx', '1');

                btn.addEventListener('mouseenter', () => {
                    const now = Date.now();
                    if (now - hoverThrottle > 80) {
                        hoverThrottle = now;
                        playHover();
                    }
                });

                // Nav buttons get special sound
                const text = (btn.textContent || '').toLowerCase();
                const isNav = btn.closest('[data-testid="stSidebar"]') &&
                              (text.includes('dashboard') || text.includes('news') ||
                               text.includes('mt5') || text.includes('aria') ||
                               text.includes('academy') || text.includes('community') ||
                               text.includes('backtest') || text.includes('journal'));

                btn.addEventListener('click', () => {
                    if (isNav) {
                        playNavClick();
                    } else {
                        playClick();
                    }
                });
            });

            // Selectboxes, inputs
            document.querySelectorAll('select:not([data-sfx]), input:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('focus', () => {
                    const now = Date.now();
                    if (now - hoverThrottle > 120) {
                        hoverThrottle = now;
                        playHover();
                    }
                });
            });

            // Expanders
            document.querySelectorAll('[data-testid="stExpander"]:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('click', () => playClick());
            });

            // Tabs
            document.querySelectorAll('[data-baseweb="tab"]:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('click', () => playNavClick());
                el.addEventListener('mouseenter', () => {
                    const now = Date.now();
                    if (now - hoverThrottle > 80) {
                        hoverThrottle = now;
                        playHover();
                    }
                });
            });

            // Slider thumbs
            document.querySelectorAll('[role="slider"]:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('mousedown', () => playClick());
            });

            // Links / anchors
            document.querySelectorAll('a:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('mouseenter', () => {
                    const now = Date.now();
                    if (now - hoverThrottle > 80) {
                        hoverThrottle = now;
                        playHover();
                    }
                });
                el.addEventListener('click', () => playClick());
            });

            // Neon cards (custom class)
            document.querySelectorAll('.neon-card:not([data-sfx]), .panel:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('mouseenter', () => {
                    const now = Date.now();
                    if (now - hoverThrottle > 150) {
                        hoverThrottle = now;
                        playHover();
                    }
                });
            });

            // ARIA avatar
            document.querySelectorAll('.aria-avatar:not([data-sfx])').forEach(el => {
                el.setAttribute('data-sfx', '1');
                el.addEventListener('mouseenter', () => playDataScan());
                el.addEventListener('click', () => playSuccess());
            });
        }

        // Initial attach
        setTimeout(attachSounds, 500);

        // Re-attach when Streamlit re-renders
        const observer = new MutationObserver(() => {
            setTimeout(attachSounds, 100);
        });
        observer.observe(document.body, { childList: true, subtree: true });

        // Boot-up sound on first load
        document.addEventListener('click', function bootSound() {
            document.removeEventListener('click', bootSound);
            // Small delay so AudioContext is unlocked
            setTimeout(() => {
                try {
                    const ctx = getCtx();
                    // Boot sequence: 3 ascending tones
                    [600, 900, 1400].forEach((freq, i) => {
                        const osc = ctx.createOscillator();
                        const gain = ctx.createGain();
                        osc.type = 'sine';
                        osc.frequency.value = freq;
                        gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.08);
                        gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + i * 0.08 + 0.02);
                        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.08 + 0.15);
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.start(ctx.currentTime + i * 0.08);
                        osc.stop(ctx.currentTime + i * 0.08 + 0.15);
                    });
                } catch(e) {}
            }, 100);
        }, { once: true });

        console.log('[ALPHA FX HUB] Cyberpunk SFX engine loaded');
    })();
    </script>
    """

    st.markdown(f"<div style='display:none'>{sound_js}</div>", unsafe_allow_html=True)
