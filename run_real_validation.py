#!/usr/bin/env python3
"""
Alpha FX Hub — One-Click Real Data Validation
===============================================
Run on your Mac: python3 run_real_validation.py

This is a convenience wrapper that:
1. Downloads XAUUSD M15 data from multiple free sources
2. Saves it to xauusd_m15_data.csv in the same folder
3. Runs the full V2 backtest with fixed bugs
4. Outputs all results

No config needed. Just run it.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Load .env from alpha_fx_hub directory (for TWELVE_DATA_API_KEY etc.)
_script_dir = Path(__file__).parent.absolute()
_env_file = _script_dir / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
        print(f"  Loaded .env from {_script_dir}")
    except ImportError:
        # Manual .env loading if dotenv not installed
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def download_xauusd_data(output_csv: str = "xauusd_m15_data.csv") -> bool:
    """Download XAUUSD M15 from multiple free sources. Return True if successful."""

    print("\n" + "=" * 70)
    print("  DOWNLOADING REAL XAUUSD M15 DATA")
    print("=" * 70)

    script_dir = Path(__file__).parent.absolute()
    csv_path = script_dir / output_csv

    # 1. Try yfinance (easiest, no API key needed)
    print("\n[1/4] Attempting yfinance (GC=F gold futures, M15, 60 days)...")
    try:
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="60d", interval="15m")

        if not df.empty:
            df = df.reset_index()
            df = df.rename(columns={
                "Datetime": "time", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume"
            })
            df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
            df = df[["time", "open", "high", "low", "close", "volume"]].dropna()

            if len(df) > 100:
                df.to_csv(csv_path, index=False)
                print(f"  SUCCESS: {len(df)} bars downloaded from yfinance")
                print(f"           Range: {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
                print(f"           Saved: {csv_path}")
                return True
    except ImportError:
        print("  SKIPPED: yfinance not installed (pip install yfinance)")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 2. Try Twelve Data API (if env var is set)
    print("\n[2/4] Attempting Twelve Data API (if TWELVE_DATA_API_KEY is set)...")
    api_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if api_key and api_key != "paste_your_twelve_data_key_here":
        try:
            import urllib.request
            import pandas as pd

            url = (
                f"https://api.twelvedata.com/time_series?"
                f"symbol=XAU/USD&interval=15min&outputsize=5000"
                f"&apikey={api_key}&format=JSON"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "AlphaFXHub/3.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            if "values" in data:
                rows = data["values"]
                df = pd.DataFrame(rows)
                df["time"] = pd.to_datetime(df["datetime"])
                for col in ["open", "high", "low", "close"]:
                    df[col] = df[col].astype(float)
                df = df.sort_values("time").reset_index(drop=True)
                df["volume"] = ((df["high"] - df["low"]) * 1000).astype(int).clip(lower=100)
                df = df[["time", "open", "high", "low", "close", "volume"]]

                if len(df) > 100:
                    df.to_csv(csv_path, index=False)
                    print(f"  SUCCESS: {len(df)} bars downloaded from Twelve Data")
                    print(f"           Range: {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
                    print(f"           Saved: {csv_path}")
                    return True
        except Exception as e:
            print(f"  FAILED: {e}")
    else:
        print("  SKIPPED: TWELVE_DATA_API_KEY not set")
        print("           (Get free key at: https://twelvedata.com)")

    # 3. Try ejtraderLabs GitHub CSV
    print("\n[3/4] Attempting ejtraderLabs GitHub (free, no auth)...")
    try:
        import urllib.request
        import pandas as pd
        from io import StringIO

        url = "https://raw.githubusercontent.com/ejtraderLabs/historical-data/main/XAUUSD/XAUUSDm15.csv"
        req = urllib.request.Request(url, headers={"User-Agent": "AlphaFXHub/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')

        df = pd.read_csv(StringIO(content))

        # Normalize column names
        col_map = {}
        for col in df.columns:
            cl = col.lower().strip()
            if cl in ("time", "datetime", "date", "timestamp"):
                col_map[col] = "time"
            elif cl in ("open", "o"):
                col_map[col] = "open"
            elif cl in ("high", "h"):
                col_map[col] = "high"
            elif cl in ("low", "l"):
                col_map[col] = "low"
            elif cl in ("close", "c"):
                col_map[col] = "close"
            elif cl in ("volume", "vol", "v", "tick_volume"):
                col_map[col] = "volume"

        df = df.rename(columns=col_map)
        required = {"time", "open", "high", "low", "close"}
        if required.issubset(set(df.columns)):
            df["time"] = pd.to_datetime(df["time"])
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)
            if "volume" not in df.columns:
                df["volume"] = 1000
            df = df.sort_values("time").reset_index(drop=True)
            df = df[["time", "open", "high", "low", "close", "volume"]]

            if len(df) > 100:
                df.to_csv(csv_path, index=False)
                print(f"  SUCCESS: {len(df)} bars downloaded from ejtraderLabs")
                print(f"           Range: {df['time'].iloc[0].date()} to {df['time'].iloc[-1].date()}")
                print(f"           Saved: {csv_path}")
                return True
    except Exception as e:
        print(f"  FAILED: {e}")

    # 4. Ask for user CSV
    print("\n[4/4] All automatic sources failed.")
    print("\n  OPTION: Provide your own CSV file")
    print("  ────────────────────────────────────")
    print("  Export XAUUSD M15 data from TradingView or MT5 as CSV.")
    print("  Then run:")
    print(f"    python3 run_real_validation.py --csv yourfile.csv")
    print()

    return False


def run_backtest(csv_file: str = None, balance: float = 10000.0,
                 risk: float = 2.0, use_delay: bool = False):
    """Import and run the V2 backtester."""

    print("\n" + "=" * 70)
    print("  RUNNING BACKTEST")
    print("=" * 70)

    # Import the backtest module
    try:
        # Try importing as module (if in same directory)
        from real_data_backtest_v2 import (
            get_real_data, add_indicators, run_real_backtest,
            print_report, print_stress_report, print_walkforward_report,
            walk_forward
        )
    except ImportError:
        print("\nERROR: Could not import real_data_backtest_v2.py")
        print("Make sure it's in the same directory as this script.")
        sys.exit(1)

    # Get data
    df, source = get_real_data(csv_path=csv_file)
    total_bars = len(df)

    # Indicators
    print("\n📈 Computing indicators...")
    df = add_indicators(df)
    print(f"  ✓ Indicators computed on {len(df)} bars")
    print(f"  ATR range: ${df['atr14'].min():.2f} - ${df['atr14'].max():.2f}")
    print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # Main backtest
    print("\n🔬 Running main backtest (spread 2.0 + slip 0.5)...")
    main_result = run_real_backtest(df, spread_pips=2.0, slippage_pips=0.5,
                                   starting_balance=balance, risk_pct=risk,
                                   execution_delay=use_delay)
    print()
    print_report(main_result, source, total_bars)

    # Stress tests
    print("\n🔥 Running stress tests...")
    stress_configs = [
        (2.0, 0.5),
        (2.5, 0.5),
        (3.0, 1.0),
        (4.0, 1.5),
    ]
    stress_results = []
    for sp, sl in stress_configs:
        r = run_real_backtest(df, spread_pips=sp, slippage_pips=sl,
                             starting_balance=balance, risk_pct=risk,
                             execution_delay=use_delay)
        stress_results.append(r)
    print_stress_report(stress_results)

    # Walk-forward
    if total_bars > 1500:
        print("\n📊 Running walk-forward validation...")
        wf = walk_forward(df, n_folds=5, spread_pips=2.0, slippage_pips=0.5)
        print_walkforward_report(wf)
    else:
        print(f"\n⚠️  Skipping walk-forward: only {total_bars} bars (need >1500)")

    # Verdict
    print("\n" + "=" * 70)
    print("  HONEST VERDICT")
    print("=" * 70)
    if main_result.get("total_trades", 0) == 0:
        print("  Cannot assess — no trades generated.")
        print("  Try with more data or a different period.\n")
    else:
        pf = main_result["profit_factor"]
        wr = main_result["win_rate_pct"]
        med_r = main_result["median_r_multiple"]
        dd = main_result["max_drawdown_pct"]
        top1 = main_result["outlier_top1_pct"]
        ret_dd = main_result["return_to_dd_ratio"]

        edge = "POSITIVE" if pf > 1.3 and med_r > -0.5 else "MARGINAL" if pf > 1.0 else "NEGATIVE"

        print(f"  Strategy Edge:         {edge}")
        print(f"  Key Metric (Median R): {med_r:.2f}R per trade")
        print(f"  Profit Factor:         {pf:.2f}")
        print(f"  Return-to-DD Ratio:    {ret_dd:.2f}")
        print(f"  Drawdown Risk:         {'ACCEPTABLE' if dd < 20 else 'HIGH' if dd < 35 else 'DANGEROUS'}")
        print(f"  Outlier Dependency:    {'LOW' if top1 < 30 else 'MODERATE' if top1 < 60 else 'HIGH'}")
        print()

        print("  STRATEGY WEAKNESSES:")
        weaknesses = []
        if pf < 1.3:
            weaknesses.append("    - Profit factor below 1.3 (weak profitability)")
        if med_r < 0.5:
            weaknesses.append("    - Median R negative or near zero (no edge)")
        if wr < 40:
            weaknesses.append("    - Win rate below 40% (unprofitable for most)")
        if dd > 25:
            weaknesses.append("    - Max drawdown exceeds 25% (dangerous)")
        if top1 > 50:
            weaknesses.append("    - Heavily dependent on outlier trades (unreliable)")
        if ret_dd < 1.0:
            weaknesses.append("    - Return-to-DD ratio < 1.0 (drawdown > profit)")
        if not weaknesses:
            weaknesses.append("    - None identified (looks reasonable!)")

        for w in weaknesses:
            print(w)
        print()

        if edge == "POSITIVE" and dd < 25:
            print("  → RECOMMENDATION: Proceed to small-size live test")
            print("    Use 0.01 lot for 4-6 weeks before scaling.")
        elif edge == "MARGINAL":
            print("  → RECOMMENDATION: Strategy needs refinement")
            print("    Optimize signal filters before live testing.")
        else:
            print("  → RECOMMENDATION: Do NOT trade live")
            print("    Review strategy and data before proceeding.")

    print()

    # Save outputs
    print("💾 Saving CSV and report...")
    try:
        import pandas as pd

        if "trades" in main_result and main_result["trades"]:
            trade_rows = []
            for t in main_result["trades"]:
                trade_rows.append({
                    "num": t.num,
                    "entry_time": t.entry_time,
                    "entry_price": t.entry_price,
                    "direction": t.direction,
                    "initial_sl": t.initial_sl,
                    "grade": t.grade,
                    "score": t.score,
                    "pnl_usd": t.pnl_usd,
                    "r_multiple": t.r_multiple,
                })
            trade_df = pd.DataFrame(trade_rows)
            trade_df.to_csv("real_backtest_trades.csv", index=False)
            print("  ✓ Trade log saved: real_backtest_trades.csv")

        with open("real_backtest_report.txt", "w") as f:
            f.write("=" * 70 + "\n")
            f.write("  ALPHA FX HUB BACKTEST REPORT\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Total Trades:     {main_result['total_trades']}\n")
            f.write(f"Win Rate:         {main_result['win_rate_pct']}%\n")
            f.write(f"Profit Factor:    {main_result['profit_factor']}\n")
            f.write(f"Final Balance:    ${main_result['final_balance']:,.2f}\n")
            f.write(f"Total Return:     ${main_result['total_return_usd']:,.2f}\n")
            f.write(f"Max Drawdown:     ${main_result['max_drawdown_usd']:,.2f}\n")
            f.write(f"Median R:         {main_result['median_r_multiple']:.2f}R\n")

        print("  ✓ Report saved: real_backtest_report.txt")
        print()
    except Exception as e:
        print(f"  Warning: Could not save output files: {e}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Alpha FX Hub — One-Click Real Data Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_real_validation.py
    Download data and run backtest

  python3 run_real_validation.py --csv mydata.csv
    Use your own CSV file

  python3 run_real_validation.py --balance 50000 --risk 1.5
    Custom starting balance and risk per trade
        """)

    parser.add_argument("--csv", help="Path to your XAUUSD M15 CSV file (optional)")
    parser.add_argument("--balance", type=float, default=10000.0,
                       help="Starting balance (default: $10,000)")
    parser.add_argument("--risk", type=float, default=2.0,
                       help="Risk per trade in %% (default: 2.0%%)")
    parser.add_argument("--delay", action="store_true",
                       help="Enable execution delay (entry on next bar)")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  ALPHA FX HUB — ONE-CLICK REAL DATA VALIDATION")
    print("  Strategy: V3 Trend-Following with Fixed SL Logic")
    print("=" * 70)

    # Determine data source
    csv_to_use = None
    if args.csv:
        # User provided CSV
        csv_to_use = args.csv
        if not os.path.exists(csv_to_use):
            print(f"\nERROR: CSV file not found: {csv_to_use}")
            sys.exit(1)
        print(f"\nUsing provided CSV: {csv_to_use}")
    else:
        # Try to download
        success = download_xauusd_data()
        if success:
            csv_to_use = "xauusd_m15_data.csv"
        else:
            print("\nERROR: Could not download data and no CSV provided.")
            print("Run with: python3 run_real_validation.py --csv yourfile.csv")
            sys.exit(1)

    # Run backtest
    try:
        run_backtest(csv_file=csv_to_use, balance=args.balance,
                    risk=args.risk, use_delay=args.delay)
    except Exception as e:
        print(f"\nERROR during backtest: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("=" * 70)
    print("  ALL DONE!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review the console output above")
    print("  2. Check real_backtest_trades.csv for trade details")
    print("  3. Read real_backtest_report.txt for full summary")
    print("\nTo test with different settings:")
    print("  python3 run_real_validation.py --balance 50000 --risk 1.5")
    print()


if __name__ == "__main__":
    main()
