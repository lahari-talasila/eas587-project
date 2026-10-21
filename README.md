# Predicting &amp; Explaining Flight-Delay Cascades Across the U.S. Air Network

**EAS 587 — Data-Intensive Computing · Phase 1 (Research Plan &amp; Data Charter)**

This repository contains the Phase 1 deliverables for our course project: a complete
research plan ([`research_plan.md`](research_plan.md)), a representative sample of our
primary big dataset, and illustrative source code for acquiring, sampling, and exploring
the data.

## What the project is about

We study **what drives significant (15+ minute) flight delays and how they cascade
through the U.S. air network**, using the full historical record of domestic flights
published by the U.S. Bureau of Transportation Statistics (BTS). Our primary big dataset
is the **Airline (Reporting Carrier) On-Time Performance** record (1987–present,
~500–600K flights/month, ~110 columns, one CSV file per month, 30+ GB / 200M+ records
over its full history). The plan is to add route-level capacity from the **T-100 Domestic
Segment** dataset; that join is not part of Phase 2, which builds congestion features from
On-Time flight counts instead. The data is downloaded directly from BTS TranStats.

See [`research_plan.md`](research_plan.md) for the full plan (goal, background, scope,
references, data &amp; resources, risks, 12-week timeline, and design decisions).

## Repository structure

```
.
├── README.md               # this file
├── requirements.txt        # Python dependencies
├── research_plan.md         # Phase 1 research plan (the graded report)
├── .gitignore
├── data/
│   ├── samples/         
│   │   └── ontime_sample.csv
│   ├── raw/               
│   │   └── README.md
│   └── processed/         
└── src/
```

## Setup (runs in a fresh environment)

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## How to run

**1. Inspect the committed sample (no download needed):**

```bash
python src/eda.py --input data/samples/ontime_sample.csv
```

**2. Download a real month of On-Time data from BTS (≈20–30 MB zipped):**

```bash
python src/data_access.py --dataset ontime --year 2024 --month 1 --out data/raw
```

**3. Sample / subset it and convert to Parquet:**

```bash
python src/data_sampling.py \
    --input data/raw/On_Time_Reporting_Carrier_On_Time_Performance_2024_1.csv \
    --out data/processed/ontime_2024_01.parquet \
    --n 250000
```

**4. Explore the processed data:**

```bash
python src/eda.py --input data/processed/ontime_2024_01.parquet
```

## Data source &amp; license

All data is from the U.S. DOT Bureau of Transportation Statistics (TranStats),
a U.S. public-domain source. On-Time table: `Table_ID=236`. See
[`data/raw/README.md`](data/raw/README.md) for exact download instructions and URLs.

> Note: raw monthly files and processed Parquet are intentionally **not** committed
> to keep the repo lightweight; they are fully reproducible with the
> scripts above.

## Phase 2: Cleaning, EDA and First Analytics

### Reproduce (single entry point)
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/pipeline.py --year 2024 --months 1 2 3 4 5 6 7 8 9 10 11 12
```
This runs: acquire (calls `src/data_access.py`) -> profile -> clean -> analytics.
Use `--skip-acquire` if raw CSVs are already in `data/raw/`, or `--stage clean` to run one stage.
Then open `notebooks/phase2_analysis.ipynb` (loads the processed data only).

### Outputs
- `data/processed/ontime_clean/*.parquet`: one cleaned file per month (loadable with `pandas.read_parquet`)
- `data/processed/cancelled_diverted.parquet`: cancelled/diverted flights, kept separate from delay analysis
- `reports/`: profiling and cleaning stats, summary tables
- `figures/`: all figures used in `phase2_report.md`

### Layout
`src/pipeline.py` (entry point), `src/data_cleaning.py` (cleaning + features), `src/analytics.py` (EDA and first analytics).
Random seed is fixed to 42 everywhere.
