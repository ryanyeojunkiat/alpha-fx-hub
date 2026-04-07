#!/usr/bin/env python3
"""
Download XAUUSD M15 data from Dukascopy — NO Node.js needed.
Just Python + pandas.

Usage:
    python3 download_dukascopy.py
    python3 download_dukascopy.py --months 12

Then run:
    python3 real_data_backtest_v31.py --csv dukascopy_xauusd_m15.csv
"""

import struct
import lzma
import io
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    print("Need: pip install pandas numpy")
    sys.exit(1)


# Dukascopy stores data in hourly bi5 (LZMA-compressed binary) files
# URL pattern: datafeed/XAUUSD/{year}/{month-1}/{day}/{hour}h_ticks.bi5
# Month is 0-indexed in Dukascopy (Jan=0, Feb=1, etc.)

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
SYMBOL = "XAUUSD"
POINT = 0.001  # Dukascopy stores prices as integers, divide by 1/point


def download_hour(dt: datetime, retries: int = 2) -> list:
    """Download one hour of tick data from Dukascopy."""
    year = dt.year
    month = dt.month - 1  # 0-indexed
    day = dt.day
    hour = dt.hour

    url = f"{BASE_URL}/{SYMBOL}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"

    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urlopen(req, timeout=10)
            data = resp.read()

            if len(data) == 0:
                return []

            # Decompress LZMA
            try:
                decompressed = lzma.decompress(data)
            except lzma.LZMAError:
                return []

            if len(decompressed) == 0:
                return []

            # Parse binary: each tick is 20 bytes
            # Format: uint32 ms_offset, uint32 ask, uint32 bid, float32 ask_vol, float32 bid_vol
            ticks = []
            tick_size = 20
            n_ticks = len(decompressed) // tick_size

            for i in range(n_ticks):
                chunk = decompressed[i * tick_size:(i + 1) * tick_size]
                if len(chunk) < tick_size:
                    break
                ms_offset, ask_int, bid_int, ask_vol, bid_vol = struct.unpack('>IIIff', chunk)

                tick_time = dt + timedelta(milliseconds=ms_offset)
                ask_price = ask_int * POINT
                bid_price = bid_int * POINT

                ticks.append({
                    "time": tick_time,
                    "bid": round(bid_price, 3),
                    "ask": round(ask_price, 3),
                })

            return ticks

        except (URLError, HTTPError, TimeoutError):
            if attempt < retries:
                time.sleep(0.5)
            continue
        except Exception:
            return []

    return []


def ticks_to_m15(ticks: list) -> pd.DataFrame:
    """Aggregate tick data into M15 OHLCV bars."""
    if not ticks:
        return pd.DataFrame()

    df = pd.DataFrame(ticks)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time")

    # Use bid price for OHLC (standard for forex)
    ohlc = df["bid"].resample("15min").agg(
        open="first", high="max", low="min", close="last"
    ).dropna()

    # Volume = tick count per bar
    vol = df["bid"].resample("15min").count().rename("volume")

    result = pd.concat([ohlc, vol], axis=1).reset_index()
    result = result.rename(columns={"index": "time"})

    return result


def main():
    parser = argparse.ArgumentParser(description="Download Dukascopy XAUUSD M15")
    parser.add_argument("--months", type=int, default=6, help="Months of data (default: 6)")
    parser.add_argument("--output", default="dukascopy_xauusd_m15.csv", help="Output CSV file")
    args = parser.parse_args()

    output_path = Path(__file__).parent / args.output

    end_date = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=args.months * 30)

    print(f"\n{'='*60}")
    print(f"  Downloading XAUUSD from Dukascopy")
    print(f"  {start_date.date()} to {end_date.date()} ({args.months} months)")
    print(f"{'='*60}\n")

    all_ticks = []
    current = start_date
    total_hours = int((end_date - start_date).total_seconds() / 3600)
    downloaded = 0
    skipped = 0

    while current < end_date:
        # Skip weekends
        if current.weekday() < 5:
            ticks = download_hour(current)
            if ticks:
                all_ticks.extend(ticks)
                downloaded += 1
            else:
                skipped += 1

        current += timedelta(hours=1)

        # Progress every 100 hours
        hours_done = int((current - start_date).total_seconds() / 3600)
        if hours_done % 200 == 0:
            pct = hours_done / max(total_hours, 1) * 100
            print(f"  {pct:.0f}% done — {downloaded} hours downloaded, {len(all_ticks)} ticks so far...")

    print(f"\n  Total: {len(all_ticks)} ticks from {downloaded} hours")

    if not all_ticks:
        print("  ERROR: No data downloaded. Check internet connection.")
        sys.exit(1)

    # Aggregate to M15
    print("  Aggregating to M15 bars...")
    df = ticks_to_m15(all_ticks)

    # Remove weekend bars and zero-volume bars
    df = df[df["volume"] > 0].reset_index(drop=True)

    print(f"  Result: {len(df)} M15 bars")
    print(f"  Range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print(f"  Price: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    df.to_csv(output_path, index=False)
    print(f"\n  Saved: {output_path}")
    print(f"\n  Now run:")
    print(f"  python3 real_data_backtest_v31.py --csv {args.output}\n")


if __name__ == "__main__":
    main()
