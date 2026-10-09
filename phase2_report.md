# [Project title from Phase 1]
**Team:** Lahari Talasila, Karthika Sundararajan

<!-- Write every section in your own words. The prompts below are only reminders of what the handout asks for. Delete them as you write. Ceilings: Cleaning <= 2 pages, EDA <= 3, Analytics <= 3, everything else ~2 pages total. Every figure needs a caption and 2+ sentences of interpretation. -->

## 1. Executive Summary
<!-- 1 paragraph: what you found, why it matters. Write this LAST, with real numbers. -->

## 2. Connection to Phase 1
<!-- Which research questions does Phase 2 address? Any change to the plan (months used, T-100 fusion deferred to Phase 3?) -->

## 3. Data Cleaning and Processing
<!-- Profiling: schema, row counts, cardinality, missingness (random or systematic?), duplicates (what counts as one?). Cite reports/profile_*.csv.
Cleaning decisions per column with justification. Scalable strategy used (chunked read + column pruning + Parquet). Memory estimate and runtimes from reports/cleaning_stats.csv. -->

## 4. Exploratory Data Analysis
<!-- Figures 1-10 as needed: ![caption](figures/01_delay_distribution.png) then 2+ sentences each. Tie to Tukey: re-expression, robust summaries, residuals, the unexpected. -->

## 5. First Analytics Results
<!-- Each result tied to a specific Phase 1 question: cascade (inherited delay), cause decomposition, worst airports/hubs. -->

## 6. Dead Ends
<!-- At least 2 things that did not work and what you learned. Keep an honest log as you go (see notes in the chat). -->

## 7. Design Decisions
<!-- Decision | alternatives considered | why. e.g. chunked pandas vs Dask, outlier retain vs cap, signed log vs none, sample size. -->

## 8. Reproducibility Statement
<!-- Confirm the dry run: who ran it, on what machine/fresh environment, date. Only write this after you actually do it. -->

## 9. References
<!-- Tukey (1977); VanderPlas (2016); BTS TranStats; plus Phase 1 references you actually use. -->
