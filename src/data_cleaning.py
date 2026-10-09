"""Cleaning and transformation for BTS On-Time Performance data.

Design: each raw monthly CSV is read in chunks (bounded memory), each chunk is
reduced to the columns we need and cleaned, then the month is de-duplicated and
given tail-number rotation features before being written to Parquet.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

SEED = 42
CHUNK_ROWS = 200_000

# Only the columns the research questions need. Reading ~25 of ~110 columns is
# the single biggest memory win.
USECOLS = [
    "Year", "Quarter", "Month", "DayofMonth", "DayOfWeek", "FlightDate",
    "Reporting_Airline", "Tail_Number", "Flight_Number_Reporting_Airline",
    "Origin", "OriginState", "Dest", "DestState",
    "CRSDepTime", "DepTime", "DepDelay", "DepDel15", "TaxiOut",
    "CRSArrTime", "ArrTime", "ArrDelay", "ArrDel15",
    "Cancelled", "CancellationCode", "Diverted",
    "CRSElapsedTime", "ActualElapsedTime", "Distance",
    "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay",
]

DTYPES = {
    "Year": "int16", "Quarter": "int8", "Month": "int8", "DayofMonth": "int8",
    "DayOfWeek": "int8", "Reporting_Airline": "string", "Tail_Number": "string",
    "Flight_Number_Reporting_Airline": "string", "Origin": "string",
    "OriginState": "string", "Dest": "string", "DestState": "string",
    "CancellationCode": "string",
}

CAUSE_COLS = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]
DEDUP_KEY = ["FlightDate", "Reporting_Airline", "Flight_Number_Reporting_Airline",
             "Origin", "Dest", "CRSDepTime", "Tail_Number"]


def _hhmm_to_minutes(s: pd.Series) -> pd.Series:
    """BTS stores times as hhmm (e.g. 1435). 2400 is midnight. Returns minutes since 00:00."""
    s = pd.to_numeric(s, errors="coerce")
    s = s.where(s != 2400, 0)
    return (s // 100) * 60 + (s % 100)


def clean_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Type casting and text standardization on a single chunk."""
    df = df.copy()
    df["FlightDate"] = pd.to_datetime(df["FlightDate"], errors="coerce")
    df = df.dropna(subset=["FlightDate", "Origin", "Dest", "Reporting_Airline"])

    for c in ["Reporting_Airline", "Tail_Number", "Origin", "Dest", "OriginState", "DestState"]:
        df[c] = df[c].str.strip().str.upper()
    # placeholder tail numbers carry no aircraft identity, so rotation features must skip them
    df.loc[df["Tail_Number"].isin(["", "UNKNOWN", "000000", "0"]), "Tail_Number"] = pd.NA

    for c in ["Cancelled", "Diverted"]:
        df[c] = df[c].fillna(0).astype("int8")
    return df


def split_cancel_divert(df: pd.DataFrame):
    """Cancelled/diverted flights have null times by design (plan Section 6), so they
    are routed to their own table instead of being imputed into the delay data."""
    bad = (df["Cancelled"] == 1) | (df["Diverted"] == 1)
    return df.loc[~bad].copy(), df.loc[bad].copy()


def handle_delay_causes(df: pd.DataFrame) -> pd.DataFrame:
    """Cause minutes are only reported for flights 15+ min late, so a null usually means
    'not applicable'. We fill with 0 but keep a flag for delayed flights whose causes
    are all missing (genuinely unreported), so they can be excluded from decomposition."""
    delayed = df["ArrDel15"] == 1
    all_null = df[CAUSE_COLS].isna().all(axis=1)
    df["cause_unreported"] = (delayed & all_null).astype("int8")
    df[CAUSE_COLS] = df[CAUSE_COLS].fillna(0).astype("float32")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df["dep_hour"] = (_hhmm_to_minutes(df["CRSDepTime"]) // 60).astype("Int8")
    df["is_weekend"] = df["DayOfWeek"].isin([6, 7]).astype("int8")
    df["season"] = df["Month"].map(
        {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
         6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}
    ).astype("category")
    df["route"] = df["Origin"] + "-" + df["Dest"]
    df["distance_bin"] = pd.cut(df["Distance"], [0, 500, 1000, 1500, 2500, 10_000],
                                labels=["<500", "500-1000", "1000-1500", "1500-2500", "2500+"])
    df["arr_delay_log"] = np.sign(df["ArrDelay"]) * np.log1p(df["ArrDelay"].abs())
    df["dep_delay_log"] = np.sign(df["DepDelay"]) * np.log1p(df["DepDelay"].abs())
    return df


def add_rotation_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cascade features: for each aircraft (tail number), how late was its previous leg?

    Sorted by tail and scheduled departure within the day. Only valid within a single
    calendar day (overnight legs are not treated as inherited delay).
    """
    df = df.sort_values(["Tail_Number", "FlightDate", "CRSDepTime"], kind="stable")
    g = df.groupby(["Tail_Number", "FlightDate"], sort=False, observed=True)
    df["prev_arr_delay"] = g["ArrDelay"].shift(1)
    df["prev_dest"] = g["Dest"].shift(1)
    # keep only true rotations: previous leg landed where this one departs
    df.loc[df["prev_dest"] != df["Origin"], "prev_arr_delay"] = np.nan
    df["leg_of_day"] = (g.cumcount() + 1).astype("int8")
    return df.drop(columns=["prev_dest"])


def clean_month_file(csv_path: Path, chunk_rows: int = CHUNK_ROWS):
    """Process one raw monthly CSV. Returns (clean_df, cancelled_df, stats dict)."""
    kept, dropped, rows_in = [], [], 0
    reader = pd.read_csv(csv_path, usecols=USECOLS, dtype=DTYPES, chunksize=chunk_rows,
                         low_memory=False)
    for i, chunk in enumerate(reader):
        rows_in += len(chunk)
        chunk = clean_chunk(chunk)
        ok, bad = split_cancel_divert(chunk)
        kept.append(ok)
        dropped.append(bad[["FlightDate", "Reporting_Airline", "Origin", "Dest",
                            "Cancelled", "CancellationCode", "Diverted"]])
        log.info("%s chunk %d (%d rows)", csv_path.name, i, len(chunk))

    df = pd.concat(kept, ignore_index=True)
    cancelled = pd.concat(dropped, ignore_index=True)

    n_before = len(df)
    df = df.drop_duplicates(subset=DEDUP_KEY, keep="first")
    n_dupes = n_before - len(df)

    df = handle_delay_causes(df)
    df = engineer_features(df)
    df = add_rotation_features(df)
    # delay can be missing on otherwise normal rows (rare); drop those, they cannot be analysed
    n_before = len(df)
    df = df.dropna(subset=["ArrDelay", "DepDelay", "ArrDel15", "DepDel15"])
    n_nodelay = n_before - len(df)

    stats = {"file": csv_path.name, "rows_in": rows_in, "rows_clean": len(df),
             "cancelled_or_diverted": len(cancelled), "duplicates_removed": n_dupes,
             "dropped_missing_delay": n_nodelay}
    return df.reset_index(drop=True), cancelled, stats
