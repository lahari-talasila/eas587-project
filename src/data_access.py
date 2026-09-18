"""
Download monthly Airline On-Time Performance (and, optionally, T-100) files from the
U.S. DOT Bureau of Transportation Statistics (TranStats).

The primary On-Time table is Table_ID=236. Monthly "prezipped" files follow the pattern:

  https://www.transtats.bts.gov/PREZIP/
      On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_<YYYY>_<M>.zip

BTS occasionally adjusts this filename; verify a single month before batch-downloading.

Usage:
  python src/data_access.py --dataset ontime --year 2024 --month 1 --out data/raw
  python src/data_access.py --dataset ontime --year 2023 --months 1-12 --out data/raw
"""

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import requests

BASE = "https://www.transtats.bts.gov/PREZIP"
ONTIME_TMPL = "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_{year}_{month}.zip"
HEADERS = {"User-Agent": "EAS587-course-project/1.0 (educational use)"}


def parse_months(month, months):
    """Return a list of month ints from --month N or --months A-B / A,B,C."""
    if months:
        if "-" in months:
            a, b = months.split("-")
            return list(range(int(a), int(b) + 1))
        return [int(m) for m in months.split(",")]
    return [int(month)]


def download_ontime(year, month, out_dir, retries=3, pause=2.0):
    """Download and extract one month of On-Time data. Returns the CSV path or None."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{ONTIME_TMPL.format(year=year, month=month)}"
    print(f"[ontime] {year}-{month:02d}  ->  {url}")

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            if resp.status_code == 200 and resp.content[:2] == b"PK":  # zip magic
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                    if not csv_names:
                        print("  ! no CSV inside the zip")
                        return None
                    zf.extractall(out_dir)
                    csv_path = out_dir / csv_names[0]
                    size_mb = csv_path.stat().st_size / 1e6
                    print(f"  extracted {csv_path.name}  ({size_mb:.1f} MB)")
                    return csv_path
            print(f"  attempt {attempt}: HTTP {resp.status_code} "
                  f"(or not a zip) — retrying")
        except requests.RequestException as exc:
            print(f"  attempt {attempt}: {exc} — retrying")
        time.sleep(pause * attempt)  # simple backoff; be polite to the server

    print("  ! failed after retries. Verify the current filename on the TranStats portal:")
    print("    https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=236&DB_Short_Name=On-Time")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download BTS TranStats monthly files.")
    ap.add_argument("--dataset", choices=["ontime"], default="ontime",
                    help="ontime = Reporting Carrier On-Time Performance (Table 236). "
                         "T-100 is downloaded from the TranStats portal; see data/raw/README.md.")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, default=1, help="single month (1-12)")
    ap.add_argument("--months", type=str, default=None,
                    help="range 'A-B' or list 'A,B,C' (overrides --month)")
    ap.add_argument("--out", default="data/raw")
    args = ap.parse_args(argv)

    months = parse_months(args.month, args.months)
    ok = 0
    for m in months:
        if download_ontime(args.year, m, args.out):
            ok += 1
        time.sleep(1.0)  # throttle between months
    print(f"\nDone: {ok}/{len(months)} file(s) downloaded to {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
