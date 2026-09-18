# Research Plan
## Cover Page

|  |  |
|---|---|
| **Research Project Title** | Predicting &amp; Explaining Flight-Delay Cascades Across the U.S. Air Network |
| **Created By** | Lahari Talasila · Karthika Sounderarajan |
| **Version** | 1.0 |
| **Target Community of Interest** | Airlines &amp; network schedulers, the FAA / U.S. DOT, airport operators, air passengers, and travel- and delay-prediction technology companies |
| **Date Created** | September 16, 2026 |
| **Last Updated** | September 17, 2026 |
| **GitHub Repository** | `https://github.com/lahari-talasila/eas587-project.git` |

---

## Section 1. Research Goal

Flight delays are one of the most visible and costly failures of the U.S. transportation system: roughly one in five domestic flights arrives 15 or more minutes late, and the delays are not independent events. A single aircraft delayed in the morning can propagate through its day of scheduled rotations and, at congested hub airports, seed dozens of downstream delays by evening. This project investigates **what drives significant (15+ minute) flight delays and how those delays cascade through the U.S. air network**, using the full historical record of domestic flights published by the U.S. Bureau of Transportation Statistics (BTS). Our general approach is to acquire this genuinely large dataset at scale, engineer pre-departure and route-level congestion features, and build scalable analytics and a predictive model that both *forecasts* significant delays from information known before departure and *explains* how much of a delay is inherited ("late aircraft") versus independently caused (weather, carrier, National Airspace System, security). The expected outcome is a quantified, reproducible account of delay-cascade behavior at major hubs together with a baseline predictive model, a foundation we will scale and enrich with distributed computing in later phases.

**Primary research question.** Can features known before departure such as  carrier, route, scheduled time, day, and season together with route-level congestion predict whether a flight will be significantly delayed (15+ minutes), and how do those delays propagate through major U.S. hub airports over the course of a day?


---

## Section 2. Background and Motivation

Air-travel delays impose large, widely distributed costs. A frequently cited national study (Ball et al., 2010, for NEXTOR) estimated the total cost of U.S. flight delays in the tens of billions of dollars per year once passenger time, airline operating costs, lost demand, and indirect effects are included. Those costs fall on many parties at once: passengers lose time and connections, airlines burn extra fuel and disrupt crew schedules, and airports and the FAA must absorb congestion. Understanding not just *whether* a flight is delayed but *why* and *how the delay spreads* is therefore of direct interest to schedulers, regulators, and travelers.

A substantial research literature already studies flight delay. Sternberg et al. (2017) survey delay-prediction methods and note that most published work operates on relatively narrow slices of data, a few airports, carriers, or months  and that scaling to the full national record is itself a challenge. Rebollo and Balakrishnan (2014) characterize and predict air-traffic delays using network features. What remains comparatively under-explored, and what this project contributes, is a **full-scale, reproducible treatment**: rather than a cleaned, pre-plated sample, we work from the complete BTS record across decades, confront the real engineering problems of acquiring and sampling data too large to hold in memory, and *fuse* the On-Time record with route-level capacity data (T-100) so that congestion becomes an explicit, measured feature rather than an unobserved confounder.

---

## Section 3. Research Objectives and Scope


1. **Acquire and characterize the primary dataset at scale**: the BTS On-Time record downloaded and quantified (size, rows, columns, in-memory footprint), with a working, scripted acquisition path and a committed representative sample.
2. **Clean and profile the data (Phase 2 EDA, Tukey-guided)**: a documented account of structure, missingness, and quality issues (e.g., the structured missingness of delay-cause fields) and first exploratory findings on delay distributions by carrier, airport, and season.
3. **Engineer pre-departure and congestion features** : a feature set combining flight attributes with route-level capacity from T-100, at a clearly defined join grain.
4. **Model and explain delays**: a baseline classifier for significant (15+ min) delay and a decomposition of delay by cause, including a tail-number-based measure of inherited delay and its cascade at hubs.
5. **Scale the pipeline (Phase 3)** : the analytics re-implemented on distributed infrastructure (Apache Spark / Lakehouse) and enriched with at least one additional data source.

**In scope.** Domestic U.S. flights of major reporting carriers, prediction of significant delay from pre-departure features, delay-cause decomposition and cascade analysis at major hubs, fusion of On-Time with T-100 capacity data, scalable acquisition, sampling, storage, and processing.

**Out of scope .** International flights and foreign carriers, real-time / streaming prediction, passenger-level fare or itinerary modeling (DB1B), causal claims about individual weather events, and any operational deployment.


## Section 4. Prior Research and References


- **Fleurquin, Ramasco &amp; Eguíluz (2013), *Systemic delay propagation in the US airport network*, Scientific Reports 3:1159.** Used BTS On-Time data to model delay propagation as a network process and identified reactionary (late-aircraft) delay as a primary spreading mechanism. *We extend this by adding route-level capacity (T-100) as an explicit congestion feature and by framing propagation as a predictive, per-flight problem rather than only a descriptive network one.*
- **Rebollo &amp; Balakrishnan (2014), *Characterization and prediction of air traffic delays*, Transportation Research Part C 44:231–241.** Predicts delays using network-level features and classification models. *We test whether pre-departure features alone suffice at national scale and compare against a congestion-augmented model.*
- **Sternberg, Soares, Carvalho &amp; Ogasawara (2017), *A Review on Flight Delay Prediction*, arXiv:1703.06118.** Surveys datasets, features, and methods, noting most studies use limited data slices. *We respond directly by working from the complete multi-decade record and documenting the scaling problem.*

- **U.S. Bureau of Transportation Statistics — *Reporting Carrier On-Time Performance (1987–present)*, TranStats database (Table 236), field documentation.** The authoritative source and schema reference for the primary dataset.
- **U.S. Bureau of Transportation Statistics — *T-100 Domestic Segment (U.S. Carriers)*, TranStats.** The route-level capacity source used for fusion.


## Section 5. Supporting Data and Resources

**Primary big dataset — BTS Airline (Reporting Carrier) On-Time Performance.**
- **Source / access.** U.S. DOT, Bureau of Transportation Statistics, via the TranStats portal (`DL_SelectFields.asp?Table_ID=236`). Monthly files are downloaded as zipped CSV directly over HTTPS (U.S. public-domain data). Acquisition is scripted against the prezipped monthly-file URL pattern (see `src/data_access.py`).
- **Scale.** Coverage 1987–present, ~500,000–600,000 flight records per month, ~110 columns per flight, CSV format, partitioned as one file per month (by year/month). Full historical footprint is well over 10 GB uncompressed (on the order of 30+ GB / 200M+ records), a single month alone exceeds the 250,000-record sample floor.
- **In-memory footprint (worked estimate).** Holding the full history as one in-memory table ≈ *rows × columns × bytes/value* ≈ 200,000,000 × 110 × 8 B ≈ **~176 GB**, plus pandas/object overhead roughly an order of magnitude beyond the 16 GB RAM of our laptops. Even a single year (~6M rows × 110 cols) is several GB before overhead, so wholesale `read_csv` of the corpus is infeasible. This is why we sample/subset.

**Fusion dataset — BTS T-100 Domestic Segment.** Same portal, monthly, one row per carrier–origin–destination–aircraft-type. Adds seats, passengers, departures performed, and available seat-miles, giving us route-level capacity/congestion. Joined to On-Time on carrier + origin + destination + year + month.


---

 ## Section 6. Risks, Constraints, Assumptions, and Open Questions

| Risk / constraint | Potential impact | Mitigation / alternative |
|---|---|---|
| **Structured missingness in delay-cause fields.** Carrier/weather/NAS/late-aircraft/security minutes are populated only for flights 15+ min late; most rows are null there by design. | Naive handling could bias cause decomposition and cascade attribution. | Treat nulls as "not applicable / on-time," analyze cause fields conditionally on delayed flights, and document the mechanism explicitly. |
| **Carrier-code drift across mergers.** BTS reuses/reassigns carrier codes over the long time series. | Incorrect joins to T-100 and mis-attributed trends. | Restrict modeling to a recent, stable window (e.g., 2015–present) for the main analysis; validate join match rates. |
| **Grain mismatch (On-Time per-flight vs. T-100 per-route-month).** | A row-for-row merge is not possible. | Attach T-100 capacity as *monthly route context* (a feature), not a row join — stated as an explicit design decision. |
| **Data volume vs. laptop RAM/storage.** | Cannot process the corpus locally. | Subset by month/year and hub; convert to Parquet, scale to Spark/Dask in Phase 3 | |
| **Cancelled/diverted flights carry null times.** | Skewed delay statistics if mixed in. | Separate cancellations from delay analysis; model cancellation as its own outcome if time permits. |


---

## Section 7. Research Approach, Tasks, and Timeline


**Weeks 1–4.**

- **Week 1 (Sep 15–19) — Phase 1.** Finalize research question and plan; create the repo; script and verify TranStats acquisition; download a sample month; quantify scale and in-memory footprint; commit a representative sample. *Deliverable: `research_plan.md`, workshop slides, sample data (Sep 17).*
- **Week 2 (Sep 22–26) — Acquisition at scale.** Automate multi-month downloads, choose the modeling window (target 2015–present); convert CSV → Parquet, stand up local storage layout. *Deliverable: acquisition + conversion scripts.*
- **Week 3 (Sep 29–Oct 3) — Cleaning &amp; profiling.** Handle structured missingness, cancellations, carrier-code drift, profile distributions and quality (Tukey-guided). *Deliverable: cleaning module + data-quality notes.*
- **Week 4 (Oct 6–10) — First scalable EDA + fusion.** Delay distributions by carrier/airport/season trial On-Time × T-100 join and match-rate validation; first cascade view via tail-number rotations. *Deliverable: EDA notebook/figures for Phase 2.*

**Weeks 5–12.**

- **Week 5 (Oct 13–16) — Phase 2 presentation.** Present cleaning, EDA, and first scalable results (Oct 14–16). *Milestone deliverable.*
- **Weeks 6–7 (Oct 19–30) — Feature engineering &amp; baseline model.** Build the pre-departure + congestion feature set; train and evaluate a baseline significant-delay classifier.
- **Weeks 8–9 (Nov 2–13) — Cascade modeling &amp; cause decomposition.** Quantify inherited vs. independent delay, measure propagation at focus hubs; refine features.
- **Weeks 10–11 (Nov 16–27) — Scale-out (Phase 3).** Re-implement analytics on Apache Spar k,add an enrichment source (e.g., aircraft age or weather); tune and validate at larger volume.
- **Week 12 (Nov 30–Dec 4) — Packaging.** Finalize results, visualizations, and reproducibility.
- **Week of Dec 7 — Final presentation.** *Milestone deliverable.*

---

## Design Decisions

1. **Primary dataset: BTS On-Time.** Chosen because it is a genuinely large, authoritative, public-domain federal record that must be sampled/subsetted to work with locally satisfying the course's big-data requirement  and because it directly supports the delay-cascade question.
2. **Fusion with T-100, joined as monthly route context.** On-Time lacks capacity; T-100 supplies it. Because On-Time is per-flight and T-100 is per-route-month, we attach T-100 as a *monthly contextual feature* (carrier + origin + dest + year + month) rather than a row-for-row merge which is  a deliberate methodological decision.
3. **CSV → Parquet, partitioned local subsets.** We convert downloaded CSV to columnar Parquet for predicate-pushdown, column pruning, and far smaller memory use; we develop on month/year/hub subsets and defer full-corpus processing to distributed compute in Phase 3.
4. **Modeling window 2015–present (main analysis).** Balances data volume against carrier-code stability and schema consistency, reducing join and trend artifacts, the full history remains available for scale demonstrations.
5. **Significance threshold = 15 minutes.** Matches the BTS/industry definition of a "delayed" flight and the delay-cause reporting trigger, keeping our target aligned with how the data is generated.
6. **Raw data kept out of the repo.** Only a small representative sample is committed (`data/samples/`); raw monthly files are reproduced via `src/data_access.py` and documented in `data/raw/README.md`, keeping the repository lightweight and the pipeline reproducible.
