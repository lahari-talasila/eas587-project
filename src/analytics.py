"""First analytics and EDA figures for Phase 2. Reads ONLY the processed Parquet files.

Each function saves one figure to figures/ and (where useful) a small results table
to reports/. The notebook imports these so figures in the report and notebook match.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
FIGS = ROOT / "figures"
REPORTS = ROOT / "reports"
SEED = 42
CAUSES = ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]
sns.set_theme(style="whitegrid", context="talk", font_scale=0.7)

LOAD_COLS = ["FlightDate", "Year", "Month", "DayOfWeek", "Reporting_Airline", "Origin", "Dest",
             "route", "dep_hour", "season", "distance_bin", "Distance", "DepDelay", "ArrDelay",
             "DepDel15", "ArrDel15", "arr_delay_log", "prev_arr_delay", "leg_of_day",
             "cause_unreported", "origin_hour_flights", "dest_hour_flights",
             "origin_day_flights", "arr_outlier_iqr"] + CAUSES


def load(columns: list[str] | None = None) -> pd.DataFrame:
    """Load the processed dataset (all monthly Parquet parts) with column pruning."""
    parts = sorted((PROCESSED / "ontime_clean").glob("*.parquet"))
    if not parts:
        raise FileNotFoundError("No processed data. Run: python src/pipeline.py")
    return pd.concat([pd.read_parquet(p, columns=columns or LOAD_COLS) for p in parts],
                     ignore_index=True)


def _save(fig, name: str) -> Path:
    FIGS.mkdir(exist_ok=True)
    path = FIGS / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _sample(df: pd.DataFrame, n: int = 300_000) -> pd.DataFrame:
    return df if len(df) <= n else df.sample(n, random_state=SEED)


# ------------------------------------------------------------ univariate
def fig_delay_distribution(df: pd.DataFrame):
    """Raw vs log re-expressed arrival delay (Tukey: re-express skewed data)."""
    s = _sample(df)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].hist(s["ArrDelay"].clip(-60, 300), bins=120, color="#3b6ea5")
    ax[0].set(title="Arrival delay (clipped to -60..300 min)", xlabel="Minutes", ylabel="Flights")
    ax[1].hist(s["arr_delay_log"], bins=120, color="#c0504d")
    ax[1].set(title="Signed log re-expression", xlabel="sign(x)*log(1+|x|)", ylabel="Flights")
    q = df["ArrDelay"].quantile([0, .25, .5, .75, 1]).round(1)
    q.index = ["min", "Q1", "median", "Q3", "max"]
    q.to_csv(REPORTS / "five_number_arr_delay.csv", header=["ArrDelay"])
    return _save(fig, "01_delay_distribution.png")


# ------------------------------------------------------------ categorical
def table_carrier_summary(df: pd.DataFrame) -> pd.DataFrame:
    t = df.groupby("Reporting_Airline").agg(
        flights=("ArrDelay", "size"), delay15_rate=("ArrDel15", "mean"),
        median_arr_delay=("ArrDelay", "median"),
        iqr_arr_delay=("ArrDelay", lambda x: x.quantile(.75) - x.quantile(.25)))
    t = t.sort_values("delay15_rate", ascending=False)
    t.to_csv(REPORTS / "carrier_summary.csv")
    return t


def fig_carrier_box(df: pd.DataFrame):
    order = table_carrier_summary(df).index.tolist()
    s = _sample(df)
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.boxplot(data=s, x="Reporting_Airline", y="ArrDelay", order=order, showfliers=False, ax=ax,
                color="#8fb4d9")
    ax.set(title="Arrival delay by carrier (outliers hidden; ordered by 15+ min rate)",
           xlabel="Carrier code", ylabel="Arrival delay (min)")
    return _save(fig, "02_carrier_boxplot.png")


# ------------------------------------------------------------ bivariate + residuals
def fig_dep_vs_arr_hexbin(df: pd.DataFrame):
    s = _sample(df)
    fig, ax = plt.subplots(figsize=(7, 6))
    hb = ax.hexbin(s["DepDelay"].clip(-30, 240), s["ArrDelay"].clip(-60, 300), gridsize=70,
                   bins="log", cmap="viridis", mincnt=1)
    fig.colorbar(hb, label="log10(flights)")
    ax.set(title="Departure vs arrival delay", xlabel="Departure delay (min)",
           ylabel="Arrival delay (min)")
    return _save(fig, "03_dep_vs_arr_hexbin.png")


def inherited_delay_table(df: pd.DataFrame, bin_width: int = 15) -> pd.DataFrame:
    """Resistant summary: median departure delay by the previous leg's arrival delay."""
    d = df.dropna(subset=["prev_arr_delay"]).copy()
    d["prev_bin"] = (d["prev_arr_delay"].clip(-30, 240) // bin_width) * bin_width
    t = d.groupby("prev_bin").agg(n=("DepDelay", "size"), median_dep=("DepDelay", "median"),
                                  q1=("DepDelay", lambda x: x.quantile(.25)),
                                  q3=("DepDelay", lambda x: x.quantile(.75))).reset_index()
    t = t[t["n"] >= 200]
    t.to_csv(REPORTS / "inherited_delay_table.csv", index=False)
    return t


def fig_inherited_delay_with_residuals(df: pd.DataFrame):
    """Cascade evidence: later legs inherit lateness. Fits a resistant (Theil-Sen) line on the
    binned medians, then plots the residuals (Tukey: always look at residuals)."""
    from scipy.stats import theilslopes
    t = inherited_delay_table(df)
    slope, intercept, _, _ = theilslopes(t["median_dep"], t["prev_bin"])
    resid = t["median_dep"] - (intercept + slope * t["prev_bin"])
    pd.DataFrame({"slope": [slope], "intercept": [intercept]}).to_csv(
        REPORTS / "inherited_delay_fit.csv", index=False)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    ax[0].fill_between(t["prev_bin"], t["q1"], t["q3"], alpha=.25, label="IQR")
    ax[0].plot(t["prev_bin"], t["median_dep"], "o-", label="median")
    ax[0].plot(t["prev_bin"], intercept + slope * t["prev_bin"], "--", color="k",
               label=f"Theil-Sen slope {slope:.2f}")
    ax[0].set(title="Departure delay vs previous leg's arrival delay",
              xlabel="Previous leg arrival delay (min, binned)", ylabel="Departure delay (min)")
    ax[0].legend()
    ax[1].axhline(0, color="gray")
    ax[1].plot(t["prev_bin"], resid, "o-", color="#c0504d")
    ax[1].set(title="Residuals of the resistant line", xlabel="Previous leg arrival delay (min)",
              ylabel="Residual (min)")
    return _save(fig, "04_inherited_delay_residuals.png")


# ------------------------------------------------------------ cascade through the day
def fig_delay_by_hour_hubs(df: pd.DataFrame, n_hubs: int = 6):
    hubs = df["Origin"].value_counts().head(n_hubs).index
    t = (df[df["Origin"].isin(hubs)].groupby(["Origin", "dep_hour"])["DepDelay"]
         .median().reset_index())
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=t, x="dep_hour", y="DepDelay", hue="Origin", marker="o", ax=ax)
    ax.set(title="Median departure delay by scheduled hour at the busiest airports",
           xlabel="Scheduled departure hour", ylabel="Median departure delay (min)")
    return _save(fig, "05_delay_by_hour_hubs.png")


# ------------------------------------------------------------ causes
def table_cause_shares(df: pd.DataFrame) -> pd.DataFrame:
    d = df[(df["ArrDel15"] == 1) & (df["cause_unreported"] == 0)]
    t = d.groupby("Month")[CAUSES].sum()
    t = t.div(t.sum(axis=1), axis=0)
    t.to_csv(REPORTS / "cause_shares_by_month.csv")
    return t


def fig_cause_shares(df: pd.DataFrame):
    t = table_cause_shares(df)
    fig, ax = plt.subplots(figsize=(9, 5))
    t.plot(kind="bar", stacked=True, ax=ax, colormap="tab10")
    ax.set(title="Share of delay minutes by cause (flights 15+ min late)", xlabel="Month",
           ylabel="Share of delay minutes")
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left")
    return _save(fig, "06_cause_shares.png")


# ------------------------------------------------------------ temporal
def fig_daily_trend(df: pd.DataFrame):
    d = df.groupby("FlightDate")["ArrDel15"].mean()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(d.index, d.values, alpha=.35, label="daily rate")
    ax.plot(d.index, d.rolling(7, center=True).mean(), lw=2.5, label="7-day rolling mean")
    ax.set(title="Share of flights arriving 15+ min late", xlabel="Date", ylabel="Delay rate")
    ax.legend()
    return _save(fig, "07_daily_trend.png")


# ------------------------------------------------------------ missingness
def fig_missingness(df: pd.DataFrame):
    """Where is the previous-flight delay missing? By leg of day (a plane's first flight has
    no earlier leg) and by carrier (is any group systematically incomplete?)."""
    by_leg = df.groupby("leg_of_day")["prev_arr_delay"].apply(lambda x: x.isna().mean()).head(8)
    by_car = (df.groupby("Reporting_Airline")["prev_arr_delay"]
              .apply(lambda x: x.isna().mean()).sort_values())
    pd.DataFrame({"missing_by_leg": by_leg}).to_csv(REPORTS / "missing_prev_by_leg.csv")
    by_car.rename("missing_share").to_csv(REPORTS / "missing_prev_by_carrier.csv")
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    by_leg.plot(kind="bar", ax=ax[0], color="#3b6ea5")
    ax[0].set(title="Missing previous-leg delay by leg of day", xlabel="Leg of day",
              ylabel="Share missing")
    ax[1].barh(by_car.index, by_car.values * 100, color="#c0504d")
    ax[1].set(title="Missing previous-leg delay by carrier", xlabel="% of flights",
              ylabel="Carrier")
    return _save(fig, "08_missingness.png")


# ------------------------------------------------------------ airports and routes
def table_worst_airports(df: pd.DataFrame, min_flights: int = 5000) -> pd.DataFrame:
    t = df.groupby("Origin").agg(flights=("DepDelay", "size"),
                                 dep_delay15=("DepDel15", "mean"),
                                 median_dep_delay=("DepDelay", "median"))
    t = t[t["flights"] >= min_flights].sort_values("dep_delay15", ascending=False)
    t.to_csv(REPORTS / "airport_delay_ranking.csv")
    return t


def fig_worst_airports(df: pd.DataFrame, k: int = 15):
    t = table_worst_airports(df).head(k).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(t.index, t["dep_delay15"] * 100, color="#c0504d")
    ax.set(title=f"Top {k} airports by share of 15+ min departure delays",
           xlabel="% of departures delayed 15+ min", ylabel="Origin airport")
    return _save(fig, "09_worst_airports.png")


def fig_season_violin(df: pd.DataFrame):
    s = _sample(df, 150_000)
    s = s[s["ArrDelay"].between(-60, 240)]
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.violinplot(data=s, x="season", y="ArrDelay", cut=0, inner="quartile", ax=ax,
                   color="#8fb4d9")
    ax.set(title="Arrival delay by season (-60..240 min)", xlabel="Season",
           ylabel="Arrival delay (min)")
    return _save(fig, "10_season_violin.png")


def table_congestion(df: pd.DataFrame, bin_width: int = 5) -> pd.DataFrame:
    d = df.copy()
    cap = int(d["origin_hour_flights"].quantile(.99))
    d["cong_bin"] = (d["origin_hour_flights"].clip(upper=cap) // bin_width) * bin_width
    t = d.groupby("cong_bin").agg(flights=("DepDelay", "size"), delay15_rate=("DepDel15", "mean"),
                                  median_dep_delay=("DepDelay", "median")).reset_index()
    t = t[t["flights"] >= 500]
    t.to_csv(REPORTS / "congestion_table.csv", index=False)
    return t


def fig_congestion(df: pd.DataFrame):
    """Does a busier scheduled hour at the origin mean more delays? (pre-departure feature)"""
    t = table_congestion(df)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
    ax[0].plot(t["cong_bin"], t["delay15_rate"] * 100, "o-", color="#3b6ea5")
    ax[0].set(title="15+ min departure delays vs scheduled congestion",
              xlabel="Flights scheduled from the same airport in the same hour (binned)",
              ylabel="% of departures delayed 15+ min")
    ax[1].plot(t["cong_bin"], t["median_dep_delay"], "o-", color="#c0504d")
    ax[1].set(title="Median departure delay vs scheduled congestion",
              xlabel="Flights scheduled from the same airport in the same hour (binned)",
              ylabel="Median departure delay (min)")
    return _save(fig, "11_congestion.png")


def fig_advance_heatmap(df: pd.DataFrame):
    """Delay chance using ONLY schedule-time information (weekday and hour). Everything on
    this chart is known months before departure, which is what an advance-notice model could use."""
    t = df.pivot_table(index="DayOfWeek", columns="dep_hour", values="DepDel15", aggfunc="mean") * 100
    t.to_csv(REPORTS / "delay_rate_by_weekday_hour.csv")
    fig, ax = plt.subplots(figsize=(11, 4.5))
    sns.heatmap(t, cmap="viridis", ax=ax, cbar_kws={"label": "% of departures delayed 15+ min"})
    ax.set(title="Delay chance by weekday and scheduled hour (schedule-only information)",
           xlabel="Scheduled departure hour", ylabel="Day of week (1 = Monday)")
    return _save(fig, "12_weekday_hour_heatmap.png")


def run_all() -> None:
    REPORTS.mkdir(exist_ok=True)
    df = load()
    for fn in (fig_delay_distribution, fig_carrier_box, fig_dep_vs_arr_hexbin,
               fig_inherited_delay_with_residuals, fig_delay_by_hour_hubs, fig_cause_shares,
               fig_daily_trend, fig_missingness, fig_worst_airports, fig_season_violin,
               fig_congestion, fig_advance_heatmap):
        print("saved", fn(df))


if __name__ == "__main__":
    run_all()
