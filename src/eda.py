"""
Quick exploratory pass over an On-Time sample (CSV or Parquet):
  * shape and per-column missingness,
  * share of flights delayed 15+ minutes (our target),
  * delay-cause breakdown (illustrating the *structured missingness* of cause fields),
  * saves two simple figures.

This is a starting point for the Tukey-guided EDA in Phase 2, not the full analysis.

Usage:
  python src/eda.py --input data/samples/ontime_sample.csv
  python src/eda.py --input data/processed/ontime_2024_01.parquet --figdir figures
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

CAUSES = ["CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY",
          "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY"]


def load(path):
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Basic EDA on an On-Time sample.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--figdir", default="figures")
    args = ap.parse_args(argv)

    df = load(args.input)
    print(f"\nLoaded {args.input}: {df.shape[0]:,} rows x {df.shape[1]} cols\n")

    # 1) Missingness
    print("Missingness (top 12 columns by % null):")
    miss = (df.isna().mean() * 100).sort_values(ascending=False).head(12)
    for col, pct in miss.items():
        print(f"  {col:<22} {pct:6.1f}%")

    # 2) Target: delayed 15+ minutes on arrival
    if "ARR_DELAY" in df.columns:
        arr = pd.to_numeric(df["ARR_DELAY"], errors="coerce")
        delayed15 = (arr >= 15).mean() * 100
        print(f"\nFlights arriving 15+ min late: {delayed15:.1f}%")
        print(f"Median arrival delay (min):   {arr.median():.1f}")

    # 3) Delay-cause breakdown — note the structured missingness:
    #    cause columns are populated only when a flight is 15+ min late.
    present_causes = [c for c in CAUSES if c in df.columns]
    if present_causes:
        print("\nDelay-cause fields — % of ALL rows that are non-null "
              "(low because on-time flights are blank by design):")
        for c in present_causes:
            nonnull = df[c].notna().mean() * 100
            print(f"  {c:<22} {nonnull:5.1f}% non-null")
        # Average minutes among rows where a cause is recorded (i.e., delayed flights)
        caused = df[present_causes].apply(pd.to_numeric, errors="coerce")
        totals = caused.sum(numeric_only=True)
        if totals.sum() > 0:
            print("\nShare of total attributed delay minutes by cause:")
            for c, v in (totals / totals.sum() * 100).sort_values(ascending=False).items():
                print(f"  {c:<22} {v:5.1f}%")

    # 4) Figures
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figdir = Path(args.figdir)
        figdir.mkdir(parents=True, exist_ok=True)

        if "ARR_DELAY" in df.columns:
            ax = arr.clip(-30, 180).plot(kind="hist", bins=40, color="#005BBB")
            ax.set_title("Arrival delay distribution (min)")
            ax.set_xlabel("ARR_DELAY (clipped -30..180)")
            plt.tight_layout()
            plt.savefig(figdir / "arr_delay_hist.png", dpi=120)
            plt.close()

        if present_causes and totals.sum() > 0:
            ax = (totals / totals.sum() * 100).sort_values().plot(
                kind="barh", color="#2F9FD0")
            ax.set_title("Share of attributed delay minutes by cause (%)")
            plt.tight_layout()
            plt.savefig(figdir / "delay_causes.png", dpi=120)
            plt.close()

        print(f"\nSaved figures to {figdir}/")
    except Exception as exc:  # noqa: BLE001 - EDA convenience, keep going
        print(f"\n(Skipped figures: {exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
