"""
Alpha FX Hub — Supabase Authentication
Email + Password login/signup using Supabase REST API.
No supabase Python SDK needed — pure requests to avoid dependency issues on Streamlit Cloud.
"""
import requests
import streamlit as st
from typing import Optional, Dict, Tuple


class SupabaseAuth:
    """Lightweight Supabase auth client using REST API (no SDK dependency)."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Content-Type": "application/json",
        }

    def sign_up(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """Register a new user. Returns (success, message, user_data)."""
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/signup",
                json={"email": email, "password": password},
                headers=self.headers,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("id"):
                # User created — check if email confirmation is required
                if data.get("confirmed_at") or (data.get("identities") and len(data["identities"]) > 0):
                    return True, "Account created successfully! You can now log in.", data
                else:
                    return True, "Account created! Check your email to confirm, then log in.", data

            # Handle errors
            error_msg = data.get("error_description") or data.get("msg") or data.get("message", "")
            if "already registered" in error_msg.lower() or "already been registered" in str(data).lower():
                return False, "This email is already registered. Please log in instead.", None
            if "password" in error_msg.lower() and ("short" in error_msg.lower() or "least" in error_msg.lower()):
                return False, "Password must be at least 6 characters.", None
            return False, error_msg or "Sign up failed. Please try again.", None

        except requests.exceptions.Timeout:
            return False, "Connection timed out. Please try again.", None
        except Exception as e:
            return False, f"Error: {str(e)}", None

    def sign_in(self, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """Log in with email + password. Returns (success, message, session_data)."""
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/token?grant_type=password",
                json={"email": email, "password": password},
                headers=self.headers,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("access_token"):
                return True, "Login successful!", data

            error_msg = data.get("error_description") or data.get("msg") or data.get("message", "")
            if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
                return False, "Invalid email or password. Please try again.", None
            if "not confirmed" in error_msg.lower():
                return False, "Please confirm your email before logging in. Check your inbox.", None
            return False, error_msg or "Login failed. Please try again.", None

        except requests.exceptions.Timeout:
            return False, "Connection timed out. Please try again.", None
        except Exception as e:
            return False, f"Error: {str(e)}", None

    def get_user(self, access_token: str) -> Optional[Dict]:
        """Get current user profile from access token."""
        try:
            resp = requests.get(
                f"{self.url}/auth/v1/user",
                headers={**self.headers, "Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def refresh_session(self, refresh_token: str) -> Optional[Dict]:
        """Use refresh token to get a new access token (keeps user logged in)."""
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/token?grant_type=refresh_token",
                json={"refresh_token": refresh_token},
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("access_token"):
                    return data
            return None
        except Exception:
            return None

    def sign_out(self, access_token: str) -> bool:
        """Sign out / invalidate token."""
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/logout",
                headers={**self.headers, "Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def reset_password(self, email: str) -> Tuple[bool, str]:
        """Send password reset email."""
        try:
            resp = requests.post(
                f"{self.url}/auth/v1/recover",
                json={"email": email},
                headers=self.headers,
                timeout=15,
            )
            if resp.status_code in (200, 204):
                return True, "Password reset email sent! Check your inbox."
            data = resp.json()
            return False, data.get("error_description", "Failed to send reset email.")
        except Exception as e:
            return False, f"Error: {str(e)}"


def _save_session_to_browser(access_token: str, refresh_token: str):
    """Save session tokens to browser via query params (survives page reload)."""
    try:
        # Use Streamlit's built-in cookie-like persistence via local storage
        # We store the refresh_token which is long-lived (can regenerate access_token)
        if refresh_token:
            st.query_params["rt"] = refresh_token
    except Exception:
        pass  # Older Streamlit versions may not support this


def _load_session_from_browser() -> str:
    """Load refresh token from browser query params."""
    try:
        return st.query_params.get("rt", "")
    except Exception:
        return ""


def _clear_browser_session():
    """Clear saved session from browser."""
    try:
        if "rt" in st.query_params:
            del st.query_params["rt"]
    except Exception:
        pass


def render_auth_page(auth: SupabaseAuth) -> bool:
    """
    Render the login/signup page.
    Returns True if user is authenticated, False otherwise.
    Sets st.session_state.user and st.session_state.access_token on success.

    Persistent login: Uses browser query params to store refresh token.
    User stays logged in until they explicitly log out.
    """
    # ── Step 1: Check if already logged in this session ──
    if st.session_state.get("access_token"):
        user = auth.get_user(st.session_state.access_token)
        if user:
            st.session_state.user = user
            return True
        else:
            # Token expired — try refresh
            refresh_token = st.session_state.get("refresh_token", "")
            if refresh_token:
                new_session = auth.refresh_session(refresh_token)
                if new_session and new_session.get("access_token"):
                    st.session_state.access_token = new_session["access_token"]
                    st.session_state.refresh_token = new_session.get("refresh_token", refresh_token)
                    st.session_state.user = new_session.get("user", st.session_state.get("user", {}))
                    _save_session_to_browser(new_session["access_token"], new_session.get("refresh_token", refresh_token))
                    return True
            # Clear everything
            st.session_state.pop("access_token", None)
            st.session_state.pop("refresh_token", None)
            st.session_state.pop("user", None)

    # ── Step 2: Try to restore session from browser (persistent login) ──
    if not st.session_state.get("access_token"):
        saved_rt = _load_session_from_browser()
        if saved_rt:
            new_session = auth.refresh_session(saved_rt)
            if new_session and new_session.get("access_token"):
                st.session_state.access_token = new_session["access_token"]
                st.session_state.refresh_token = new_session.get("refresh_token", saved_rt)
                st.session_state.user = new_session.get("user", {})
                _save_session_to_browser(new_session["access_token"], new_session.get("refresh_token", saved_rt))
                return True
            else:
                # Saved token is dead — clear it
                _clear_browser_session()

    # ── Auth Page Layout ──
    st.markdown("""
    <style>
        .auth-container {
            max-width: 440px;
            margin: 0 auto;
            padding: 40px 0;
        }
        .auth-header {
            text-align: center;
            margin-bottom: 32px;
        }
        .auth-header h1 {
            font-family: 'Space Mono', monospace;
            background: linear-gradient(135deg, #c0c0c0, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 32px;
            margin-bottom: 8px;
        }
        .auth-header p {
            color: #7dd3fc;
            font-size: 14px;
        }
        .auth-divider {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 24px 0;
            color: #6b7280;
            font-size: 12px;
        }
        .auth-divider::before, .auth-divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: #374151;
        }
    </style>
    """, unsafe_allow_html=True)

    # Center the form
    col_left, col_mid, col_right = st.columns([1, 2, 1])

    with col_mid:
        st.markdown("""
        <div class="auth-header">
            <h1>Alpha FX Hub</h1>
            <p>XAUUSD Gold Trading Platform</p>
        </div>
        """, unsafe_allow_html=True)

        # Tab selection
        if "auth_tab" not in st.session_state:
            st.session_state.auth_tab = "login"

        tab_cols = st.columns(3)
        with tab_cols[0]:
            if st.button("Login", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "login" else "secondary"):
                st.session_state.auth_tab = "login"
                st.rerun()
        with tab_cols[1]:
            if st.button("Sign Up", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "signup" else "secondary"):
                st.session_state.auth_tab = "signup"
                st.rerun()
        with tab_cols[2]:
            if st.button("Reset", use_container_width=True,
                         type="primary" if st.session_state.auth_tab == "reset" else "secondary"):
                st.session_state.auth_tab = "reset"
                st.rerun()

        st.markdown("---")

        # ── LOGIN ──
        if st.session_state.auth_tab == "login":
            with st.form("login_form"):
                st.markdown("#### Welcome Back")
                email = st.text_input("Email", placeholder="your@email.com", key="login_email")
                password = st.text_input("Password", type="password", placeholder="Your password", key="login_pass")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

                if submitted:
                    if not email or not password:
                        st.error("Please fill in both email and password.")
                    else:
                        with st.spinner("Logging in..."):
                            success, msg, data = auth.sign_in(email.strip(), password)
                        if success:
                            st.session_state.access_token = data["access_token"]
                            st.session_state.refresh_token = data.get("refresh_token", "")
                            st.session_state.user = data.get("user", {})
                            # Save to browser for persistent login
                            _save_session_to_browser(data["access_token"], data.get("refresh_token", ""))
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # ── SIGN UP ──
        elif st.session_state.auth_tab == "signup":
            with st.form("signup_form"):
                st.markdown("#### Create Account")
                email = st.text_input("Email", placeholder="your@email.com", key="signup_email")
                password = st.text_input("Password", type="password", placeholder="Min 6 characters", key="signup_pass")
                password2 = st.text_input("Confirm Password", type="password", placeholder="Repeat password", key="signup_pass2")
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

                if submitted:
                    if not email or not password:
                        st.error("Please fill in all fields.")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif password != password2:
                        st.error("Passwords do not match.")
                    else:
                        with st.spinner("Creating account..."):
                            success, msg, data = auth.sign_up(email.strip(), password)
                        if success:
                            st.success(msg)
                            st.session_state.auth_tab = "login"
                        else:
                            st.error(msg)

        # ── PASSWORD RESET ──
        elif st.session_state.auth_tab == "reset":
            with st.form("reset_form"):
                st.markdown("#### Reset Password")
                st.caption("Enter your email and we'll send you a password reset link.")
                email = st.text_input("Email", placeholder="your@email.com", key="reset_email")
                submitted = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")

                if submitted:
                    if not email:
                        st.error("Please enter your email.")
                    else:
                        with st.spinner("Sending..."):
                            success, msg = auth.reset_password(email.strip())
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)

        # Footer info
        st.markdown("---")
        st.markdown("""
        <div style="text-align:center; color:#6b7280; font-size:11px;">
            <p>By creating an account, you agree to our Terms of Service.</p>
            <p>Trading involves substantial risk. Only trade with capital you can afford to lose.</p>
        </div>
        """, unsafe_allow_html=True)

    return False
