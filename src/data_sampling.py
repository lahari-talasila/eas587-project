"""
Turn a large monthly On-Time CSV into a manageable local working set:
  * keep only the columns we need (reduces ~110 -> ~25),
  * optionally filter to a set of hub airports,
  * optionally take a representative random sample,
  * write out Parquet (columnar, far smaller & faster than CSV).

Why: the full On-Time history (~200M rows x 110 cols) is far larger than laptop RAM,
so we subset/sample and store columnar. See research_plan.md, Sections 5 & Design Decisions.

Usage:
  python src/data_sampling.py --input data/raw/<file>.csv \
      --out data/processed/ontime_2024_01.parquet --n 250000
  python src/data_sampling.py --input data/raw/<file>.csv \
      --out data/processed/hubs.parquet --hubs ATL,ORD,DFW,DEN,JFK
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Columns we actually use (names as they appear in BTS On-Time CSVs).
KEEP_COLS = [
    "FL_DATE", "OP_UNIQUE_CARRIER", "TAIL_NUM", "OP_CARRIER_FL_NUM",
    "ORIGIN", "DEST",
    "CRS_DEP_TIME", "DEP_TIME", "DEP_DELAY",
    "CRS_ARR_TIME", "ARR_TIME", "ARR_DELAY",
    "CANCELLED", "CANCELLATION_CODE", "DIVERTED",
    "CRS_ELAPSED_TIME", "ACTUAL_ELAPSED_TIME", "AIR_TIME", "DISTANCE",
    "CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY",
    "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY",
]


def load(input_path):
    """Read only the KEEP_COLS that are present (chunk-friendly for big files)."""
    input_path = Path(input_path)
    if input_path.suffix.lower() == ".parquet":
        return pd.read_parquet(input_path)

    # Peek at the header so we only request columns that exist in this file.
    header = pd.read_csv(input_path, nrows=0)
    present = [c for c in KEEP_COLS if c in header.columns]
    missing = [c for c in KEEP_COLS if c not in header.columns]
    if missing:
        print(f"  note: {len(missing)} expected column(s) not in file (schema drift): "
              f"{missing}")
    print(f"  reading {len(present)} of {header.shape[1]} columns")
    return pd.read_csv(input_path, usecols=present, low_memory=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Subset/sample On-Time data -> Parquet.")
    ap.add_argument("--input", required=True, help="raw CSV (or a .parquet) to process")
    ap.add_argument("--out", required=True, help="output .parquet path")
    ap.add_argument("--hubs", default=None,
                    help="comma-separated airport codes; keep flights touching any of them")
    ap.add_argument("--n", type=int, default=None,
                    help="take a random sample of N rows (>=250000 keeps a big sample)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    print(f"Loading {args.input}")
    df = load(args.input)
    print(f"  loaded shape: {df.shape[0]:,} rows x {df.shape[1]} cols "
          f"(~{df.memory_usage(deep=True).sum()/1e6:.0f} MB in memory)")

    if args.hubs:
        hubs = {h.strip().upper() for h in args.hubs.split(",")}
        before = len(df)
        df = df[df["ORIGIN"].isin(hubs) | df["DEST"].isin(hubs)]
        print(f"  hub filter {sorted(hubs)}: {before:,} -> {len(df):,} rows")

    if args.n and len(df) > args.n:
        df = df.sample(n=args.n, random_state=args.seed)
        print(f"  random sample: -> {len(df):,} rows")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Wrote {out}  ({out.stat().st_size/1e6:.1f} MB Parquet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
