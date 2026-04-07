"""
Alpha FX Hub — Price Data Fetching
Supports Twelve Data API and MetaApi for MT5.
"""
import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("alpha_fx_hub.data")

# Cache to avoid API rate limits
_cache = {}
_CACHE_TTL = 30  # seconds


def fetch_bars(
    symbol: str = "XAU/USD",
    interval: str = "15min",
    outputsize: int = 200,
    api_key: str = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV bars from Twelve Data API.
    Intervals: 1min, 5min, 15min, 30min, 1h, 4h, 1day
    """
    if api_key is None:
        api_key = os.environ.get("TWELVE_DATA_API_KEY", "")

    if not api_key:
        logger.warning("No Twelve Data API key configured")
        return _generate_demo_data(interval, outputsize)

    cache_key = f"{symbol}_{interval}_{outputsize}"
    if cache_key in _cache:
        cached_time, cached_df = _cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_df

    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": api_key,
            "format": "JSON",
            "timezone": "UTC",
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if "values" not in data:
            logger.error(f"Twelve Data error: {data.get('message', 'Unknown')}")
            return _generate_demo_data(interval, outputsize)

        rows = data["values"]
        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        _cache[cache_key] = (time.time(), df)
        return df

    except Exception as e:
        logger.error(f"Failed to fetch bars: {e}")
        return _generate_demo_data(interval, outputsize)


def fetch_price(symbol: str = "XAU/USD", api_key: str = None) -> Optional[float]:
    """Fetch current price — tries MetaAPI first (live MT5), then Twelve Data."""
    # Try MetaAPI first for live MT5 price
    metaapi_price = fetch_metaapi_price()
    if metaapi_price:
        return metaapi_price

    # Fall back to Twelve Data
    if api_key is None:
        api_key = os.environ.get("TWELVE_DATA_API_KEY", "")

    if not api_key:
        return None

    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": symbol, "apikey": api_key}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        return float(data.get("price", 0))
    except Exception as e:
        logger.error(f"Failed to fetch price: {e}")
        return None


def fetch_metaapi_price(symbol: str = "XAUUSD") -> Optional[float]:
    """Fetch live price from MetaAPI (MT5 connection)."""
    try:
        from config import METAAPI_TOKEN, METAAPI_ACCOUNT
    except ImportError:
        METAAPI_TOKEN = os.environ.get("METAAPI_TOKEN", "")
        METAAPI_ACCOUNT = os.environ.get("METAAPI_ACCOUNT", "")

    if not METAAPI_TOKEN or not METAAPI_ACCOUNT:
        return None

    cache_key = f"metaapi_{symbol}"
    if cache_key in _cache:
        cached_time, cached_price = _cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_price

    try:
        url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{METAAPI_ACCOUNT}/symbols/{symbol}/current-price"
        headers = {
            "auth-token": METAAPI_TOKEN,
            "Content-Type": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            bid = data.get("bid", 0)
            ask = data.get("ask", 0)
            price = round((bid + ask) / 2, 2) if bid and ask else bid or ask
            if price:
                _cache[cache_key] = (time.time(), price)
                logger.info(f"MetaAPI live price: {symbol} = ${price}")
                return price

        logger.warning(f"MetaAPI price fetch failed ({resp.status_code}): {resp.text[:200]}")
        return None

    except Exception as e:
        logger.debug(f"MetaAPI price fetch error: {e}")
        return None


def get_metaapi_open_trades() -> Optional[list]:
    """Fetch all open positions from MT5 via MetaAPI.

    Returns list of dicts, each with:
        id, symbol, type (buy/sell), volume, openPrice, currentPrice,
        profit, stopLoss, takeProfit, unrealizedProfit, etc.
    """
    try:
        from config import METAAPI_TOKEN, METAAPI_ACCOUNT
    except ImportError:
        METAAPI_TOKEN = os.environ.get("METAAPI_TOKEN", "")
        METAAPI_ACCOUNT = os.environ.get("METAAPI_ACCOUNT", "")

    if not METAAPI_TOKEN or not METAAPI_ACCOUNT:
        return None

    cache_key = "metaapi_open_trades"
    if cache_key in _cache:
        cached_time, cached_data = _cache[cache_key]
        if time.time() - cached_time < 10:  # Cache 10s for trades (needs to be fresh)
            return cached_data

    try:
        url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{METAAPI_ACCOUNT}/positions"
        headers = {"auth-token": METAAPI_TOKEN}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            _cache[cache_key] = (time.time(), data)
            return data

        logger.warning(f"MetaAPI positions fetch failed: {resp.status_code}")
        return None

    except Exception as e:
        logger.debug(f"MetaAPI positions error: {e}")
        return None


def get_metaapi_pending_orders() -> Optional[list]:
    """Fetch all pending orders from MT5 via MetaAPI."""
    try:
        from config import METAAPI_TOKEN, METAAPI_ACCOUNT
    except ImportError:
        METAAPI_TOKEN = os.environ.get("METAAPI_TOKEN", "")
        METAAPI_ACCOUNT = os.environ.get("METAAPI_ACCOUNT", "")

    if not METAAPI_TOKEN or not METAAPI_ACCOUNT:
        return None

    try:
        url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{METAAPI_ACCOUNT}/orders"
        headers = {"auth-token": METAAPI_TOKEN}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            return resp.json()
        return None

    except Exception as e:
        logger.debug(f"MetaAPI orders error: {e}")
        return None


def analyze_trade_liquidity_risk(trades: list, symbol: str,
                                  current_price: float, pip: float = 0.1) -> dict:
    """Analyze open trades for liquidity sweep risk.

    Checks if SL levels are clustered at obvious liquidity zones
    that smart money might target (equal lows, round numbers, etc.)

    Returns dict with:
        at_risk: bool — True if trades have SL near liquidity zones
        risk_level: HIGH/MEDIUM/LOW
        trades_at_risk: list of trade IDs at risk
        recommendation: str — what to do
        sl_cluster: float — the SL price cluster
        nearest_liquidity: float — nearest liquidity level
    """
    symbol_trades = [t for t in (trades or []) if t.get("symbol", "").upper() == symbol.upper()]

    if not symbol_trades:
        return {"at_risk": False, "risk_level": "NONE", "trades_at_risk": [],
                "recommendation": "No open trades for this symbol."}

    # Collect all SL levels
    sl_levels = []
    for t in symbol_trades:
        sl = t.get("stopLoss", 0)
        if sl and sl > 0:
            sl_levels.append(sl)

    if not sl_levels:
        return {"at_risk": True, "risk_level": "HIGH", "trades_at_risk": [t.get("id") for t in symbol_trades],
                "recommendation": "DANGER: Trades have NO stop loss set! Add SL immediately."}

    avg_sl = sum(sl_levels) / len(sl_levels)
    sl_range_pips = (max(sl_levels) - min(sl_levels)) / pip if len(sl_levels) > 1 else 0

    # Check if SL is at a round number (liquidity magnet)
    round_check = pip * 500  # For gold, this is $50 levels
    nearest_round = round(avg_sl / round_check) * round_check
    dist_to_round = abs(avg_sl - nearest_round) / pip

    # Check distance from current price to SL
    dist_to_sl = abs(current_price - avg_sl) / pip

    # Risk assessment
    at_risk_ids = []
    risk_level = "LOW"
    recommendations = []

    # Rule 1: SL too close to current price (might get swept)
    if dist_to_sl < 50:  # Less than 50 pips for Gold
        risk_level = "HIGH"
        at_risk_ids = [t.get("id") for t in symbol_trades]
        recommendations.append(f"SL only {dist_to_sl:.0f} pips from price — high sweep risk!")

    # Rule 2: SL at a round number (liquidity zone)
    if dist_to_round < 20:  # Within 20 pips of round number
        risk_level = "HIGH" if risk_level != "HIGH" else risk_level
        recommendations.append(f"SL cluster near ${nearest_round:.2f} (round number liquidity zone)")
        at_risk_ids = [t.get("id") for t in symbol_trades]

    # Rule 3: All SLs at same level (clustered = obvious target)
    if sl_range_pips < 5 and len(sl_levels) > 1:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        recommendations.append("All SLs clustered at same level — easy target for smart money")

    # Rule 4: SL at equal lows/highs pattern
    # (This would need more historical data, simplified here)

    if not recommendations:
        recommendations.append("Trade positions look adequately protected.")

    return {
        "at_risk": risk_level in ("HIGH", "MEDIUM"),
        "risk_level": risk_level,
        "trades_at_risk": at_risk_ids,
        "recommendation": " | ".join(recommendations),
        "sl_cluster": avg_sl,
        "nearest_liquidity": nearest_round,
        "dist_to_sl_pips": dist_to_sl,
        "dist_to_round_pips": dist_to_round,
        "total_trades": len(symbol_trades),
        "total_volume": sum(t.get("volume", 0) for t in symbol_trades),
        "total_profit": sum(t.get("profit", 0) for t in symbol_trades),
    }


def get_metaapi_account_info() -> Optional[dict]:
    """Get MT5 account info (balance, equity, margin, etc.)."""
    try:
        from config import METAAPI_TOKEN, METAAPI_ACCOUNT
    except ImportError:
        METAAPI_TOKEN = os.environ.get("METAAPI_TOKEN", "")
        METAAPI_ACCOUNT = os.environ.get("METAAPI_ACCOUNT", "")

    if not METAAPI_TOKEN or not METAAPI_ACCOUNT:
        return None

    cache_key = "metaapi_account_info"
    if cache_key in _cache:
        cached_time, cached_data = _cache[cache_key]
        if time.time() - cached_time < 60:  # Cache for 60s
            return cached_data

    try:
        url = f"https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai/users/current/accounts/{METAAPI_ACCOUNT}/account-information"
        headers = {"auth-token": METAAPI_TOKEN}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            _cache[cache_key] = (time.time(), data)
            return data

        logger.warning(f"MetaAPI account info failed: {resp.status_code}")
        return None

    except Exception as e:
        logger.debug(f"MetaAPI account info error: {e}")
        return None


def _generate_demo_data(interval: str = "15min", size: int = 200) -> pd.DataFrame:
    """Generate realistic gold demo data for testing/demo mode."""
    import numpy as np

    np.random.seed(42)
    base_price = 3100.0

    # Generate realistic price movement
    returns = np.random.normal(0, 0.001, size)
    prices = base_price * np.cumprod(1 + returns)

    # Add intraday pattern (more volatile during London/NY)
    volatility_pattern = np.sin(np.linspace(0, 4 * np.pi, size)) * 0.0005
    prices = prices * (1 + volatility_pattern)

    # Build OHLCV
    data = []
    for i in range(size):
        c = prices[i]
        spread = abs(np.random.normal(0, 2.0))
        o = c + np.random.normal(0, 1.5)
        h = max(o, c) + abs(np.random.normal(0, spread))
        l = min(o, c) - abs(np.random.normal(0, spread))
        v = int(np.random.uniform(1000, 50000))
        data.append({"open": round(o, 2), "high": round(h, 2),
                     "low": round(l, 2), "close": round(c, 2), "volume": v})

    df = pd.DataFrame(data)
    # Create datetime index
    freq_map = {"1min": "1min", "5min": "5min", "15min": "15min",
                "30min": "30min", "1h": "1h", "4h": "4h", "1day": "1D"}
    freq = freq_map.get(interval, "15min")
    df.index = pd.date_range(end=datetime.now(timezone.utc), periods=size, freq=freq)
    df.index.name = "datetime"
    return df
