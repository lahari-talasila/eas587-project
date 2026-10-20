"""Phase 2 entry point: raw BTS On-Time CSVs -> analysis-ready Parquet -> results.

Usage (from the repo root):
    python src/pipeline.py --year 2024 --months 1 2 3        # download, profile, clean, analyze
    python src/pipeline.py --skip-acquire                     # use whatever is already in data/raw
    python src/pipeline.py --skip-acquire --stage clean       # run a single stage

Stages: acquire -> profile -> clean (includes validate) -> analytics
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_cleaning as dc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
STAGES = ["acquire", "profile", "clean", "analytics"]
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------- acquire
def acquire(year: int, months: list[int]) -> None:
    """Calls the Phase 1 downloader once per month (skips files already on disk)."""
    for m in months:
        # BTS file names sometimes include "(1987_present)", so match with a wildcard
        have = list(RAW.glob(f"On_Time_Reporting_Carrier_On_Time_Performance*_{year}_{m}.csv"))
        if have:
            log.info("already have %s", have[0].name)
            continue
        cmd = [sys.executable, str(ROOT / "src" / "data_access.py"), "--dataset", "ontime",
               "--year", str(year), "--month", str(m), "--out", str(RAW)]
        log.info("running %s", " ".join(cmd))
        subprocess.run(cmd, check=True)


def raw_files() -> list[Path]:
    files = sorted(RAW.glob("On_Time_Reporting_Carrier_On_Time_Performance*.csv"))
    if not files:
        raise FileNotFoundError(f"No raw monthly CSVs in {RAW}. Run without --skip-acquire.")
    return files


# ---------------------------------------------------------------- profile
def profile(files: list[Path], chunk_rows: int = dc.CHUNK_ROWS) -> None:
    """Chunked profiling of the RAW data: schema, row counts, nulls, cardinality of EVERY
    column, min/max for numeric columns, and duplicates. Exact distinct counts use a set
    per column; fine at monthly scale. (At billions of rows we would switch to HyperLogLog.)"""
    REPORTS.mkdir(exist_ok=True)
    total, nulls, dtypes, dupes = 0, None, None, 0
    uniques = {c: set() for c in dc.USECOLS}
    mins, maxs = {}, {}
    for f in files:
        seen = set()
        for chunk in pd.read_csv(f, usecols=dc.USECOLS, chunksize=chunk_rows, low_memory=False):
            total += len(chunk)
            n = chunk.isna().sum()
            nulls = n if nulls is None else nulls.add(n, fill_value=0)
            dtypes = chunk.dtypes.astype(str) if dtypes is None else dtypes
            for c in dc.USECOLS:
                uniques[c].update(chunk[c].dropna().unique())
            for c in chunk.select_dtypes("number").columns:
                mins[c] = min(mins.get(c, np.inf), chunk[c].min())
                maxs[c] = max(maxs.get(c, -np.inf), chunk[c].max())
            keys = pd.util.hash_pandas_object(chunk[dc.DEDUP_KEY].astype(str), index=False)
            for k in keys.values:
                if k in seen:
                    dupes += 1
                else:
                    seen.add(k)
    prof = pd.DataFrame({"dtype": dtypes, "nulls": nulls.astype(int),
                         "null_pct": (nulls / total * 100).round(2),
                         "unique": pd.Series({c: len(s) for c, s in uniques.items()}),
                         "min": pd.Series(mins), "max": pd.Series(maxs)})
    prof = prof.replace([np.inf, -np.inf], np.nan)  # all-null columns have no min/max
    prof.to_csv(REPORTS / "profile_columns.csv")
    summary = {"total_rows": total, "files": [f.name for f in files],
               "duplicate_rows": int(dupes), "columns": len(dc.USECOLS)}
    (REPORTS / "profile_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("profiled %d rows, %d columns, %d duplicates", total, len(dc.USECOLS), dupes)


# ---------------------------------------------------------------- clean
def clean(files: list[Path]) -> None:
    out = PROCESSED / "ontime_clean"
    out.mkdir(parents=True, exist_ok=True)
    all_stats, cancelled_parts, all_checks = [], [], []
    for f in files:
        t0 = time.time()
        df, cancelled, stats = dc.clean_month_file(f)
        stats["seconds"] = round(time.time() - t0, 1)
        stats["peak_df_mb"] = round(df.memory_usage(deep=True).sum() / 1e6, 1)
        year, month = int(df["Year"].iloc[0]), int(df["Month"].iloc[0])
        checks = dc.validate(df)
        checks["file"] = f.name
        all_checks.append(checks)
        if not checks["passed"]:
            log.warning("validation issues in %s: %s", f.name, checks)
        df.to_parquet(out / f"year={year}_month={month:02d}.parquet", index=False)
        cancelled_parts.append(cancelled)
        all_stats.append(stats)
        log.info("cleaned %s: %s", f.name, stats)
    pd.concat(cancelled_parts).to_parquet(PROCESSED / "cancelled_diverted.parquet", index=False)
    pd.DataFrame(all_stats).to_csv(REPORTS / "cleaning_stats.csv", index=False)
    pd.DataFrame(all_checks).to_csv(REPORTS / "validation_checks.csv", index=False)


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--year", type=int, default=2024)
    p.add_argument("--months", type=int, nargs="+", default=[1, 2, 3])
    p.add_argument("--skip-acquire", action="store_true")
    p.add_argument("--stage", choices=STAGES, help="run only this stage")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    np.random.seed(dc.SEED)

    todo = [args.stage] if args.stage else STAGES
    if "acquire" in todo and not args.skip_acquire:
        acquire(args.year, args.months)
    if "profile" in todo:
        profile(raw_files())
    if "clean" in todo:
        clean(raw_files())
    if "analytics" in todo:
        import analytics  # noqa: E402
        analytics.run_all()
    log.info("done")


if __name__ == "__main__":
    main()
