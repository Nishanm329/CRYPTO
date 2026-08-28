"""
Fetch historical klines for the research symbol basket, cache to CSV,
and write the TRAIN/VALIDATE/HOLDOUT time-based split boundaries.

Run: .venv/bin/python -m research.data_setup   (from backend/)
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from binance_client import get_historical_klines

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
TIMEFRAME = "4h"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

# 6 years back, ms
START_MS = int(pd.Timestamp("2019-01-01", tz="UTC").timestamp() * 1000)


async def fetch_symbol(symbol: str) -> pd.DataFrame:
    df = await get_historical_klines(symbol, TIMEFRAME, START_MS)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)

    split_config = {}
    for symbol in SYMBOLS:
        print(f"Fetching {symbol} {TIMEFRAME}...")
        df = await fetch_symbol(symbol)

        # Data integrity check: gaps in the 4h grid
        expected_delta = pd.Timedelta(hours=4)
        gaps = (df.index.to_series().diff().dropna() != expected_delta).sum()
        if gaps > 5:
            print(f"  WARNING: {symbol} has {gaps} timestamp gaps — flagged for audit")

        path = os.path.join(DATA_DIR, f"{symbol}_{TIMEFRAME}.csv")
        df.to_csv(path)

        n = len(df)
        train_end = int(n * 0.6)
        val_end = int(n * 0.8)
        split_config[symbol] = {
            "n_candles": n,
            "train_start": str(df.index[0]),
            "train_end": str(df.index[train_end - 1]),
            "validate_start": str(df.index[train_end]),
            "validate_end": str(df.index[val_end - 1]),
            "holdout_start": str(df.index[val_end]),
            "holdout_end": str(df.index[-1]),
        }
        print(f"  {n} candles: TRAIN<={split_config[symbol]['train_end']} "
              f"VALIDATE<={split_config[symbol]['validate_end']} "
              f"HOLDOUT<={split_config[symbol]['holdout_end']}")

    with open(os.path.join(CONFIG_DIR, "data_split.json"), "w") as f:
        json.dump(
            {
                "symbols": SYMBOLS,
                "timeframe": TIMEFRAME,
                "split_ratio": {"train": 0.6, "validate": 0.2, "holdout": 0.2},
                "per_symbol": split_config,
            },
            f,
            indent=2,
        )
    print("Wrote config/data_split.json")


if __name__ == "__main__":
    asyncio.run(main())
