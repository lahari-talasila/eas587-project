# Predicting & Explaining Flight-Delay Cascades Across the U.S. Air Network
**Team:** Lahari Talasila, Karthika Sundararajan


## 1. Executive Summary
- 2024 BTS On-Time data, 7,079,061 flights, 6,965,247 kept.
- About 93% of an inbound delay shows up again on the next departure (slope 0.93).
- Late aircraft is about 4 in 10 delay minutes.
- The share of departures delayed 15+ minutes goes from under 10% to about 35% depending on weekday and hour.
- Congestion counts are a weak signal.
- Why it matters: this sets up predicting 15+ minute delays in Phase 3.

## 2. Connection to Phase 1
- Main question from the plan: can pre-departure features (carrier, route, scheduled time, day, season, congestion) predict a 15+ minute delay, and how do delays spread through major hubs.
- Phase 2 covers: cleaning and EDA, congestion and schedule features (partly), inherited delay and cause breakdown (first part).
- Changes from the plan: 2024 only (plan said 2015 to present), congestion built from On-Time flight counts, and the T-100 join was not done.

## 3. Data Cleaning and Processing
- Size: 12 monthly CSVs, 7,079,061 rows, 33 raw columns. 15 carriers, 348 origin and 348 destination airports, 6,112 tail numbers, 366 dates.
- Duplicates: a row matching on date, airline, flight number, origin, destination, scheduled departure and tail number. Found: 0.
- Set aside: 113,814 cancelled or diverted flights (1.6%). Kept 6,965,247.
- Delay-cause columns: 79.5% blank in the raw data because causes are only reported for flights 15+ min late. Filled with 0, plus a cause_unreported flag.
- prev_arr_delay: left missing on purpose (same aircraft, same day, previous flight landed where this one departs). Blank for all first legs and about 1 to 2% of later legs.
- Other missing: tail number 20,152 (0.28%), departure and taxi fields about 1.3 to 1.4%. Don't claim a reason.
- Outliers: Tukey fences per month (July about -64 to 72, October about -45.5 to 30.5). 629,203 flagged (about 9%) and kept because the extremes are the cascades.
- Scalable approach: chunked CSV reading, only needed columns, fixed data types, one Parquet file per month. Peak memory 143 to 171 MB per month, about 31 seconds total. All months at once would be about 1.9 GB (an estimate). The final table does fit in memory.
- 15 new columns (48 total): cause_unreported, arr_outlier_iqr, dep_hour, arr_hour, is_weekend, season, route, distance_bin, arr_delay_log, dep_delay_log, origin_hour_flights, dest_hour_flights, origin_day_flights, prev_arr_delay, leg_of_day.


## 4. Exploratory Data Analysis
### Figure 1: Arrival delay distribution

![Figure 1: Arrival delay, raw and signed-log re-expression](figures/01_delay_distribution.png)

Most flights arrive early, with the peak about 5 to 15 minutes before schedule, and the long tail sits on the late side (the bar at 300 is every flight 300+ minutes late, clipped into one bar). After the log re-expression, the late flights show up as a smaller bump of their own, which suggests delayed flights may behave differently from on-time ones.

Drawn from a random sample of 300,000 flights (fixed seed).

### Figure 2: Arrival delay by carrier

![Figure 2: Arrival delay by carrier, ordered by 15+ minute rate](figures/02_carrier_boxplot.png)

Almost every carrier has a median arrival slightly early (roughly -11 to -1 minutes), so the typical flight isn't late for anyone. The real differences are in the upper quartile and whiskers, where F9, AA and B6 spread much further into late arrivals than HA, 9E or YX.

Drawn from a random sample of 300,000 flights (fixed seed).

### Figure 3: Departure delay vs arrival delay

![Figure 3: Departure vs arrival delay (hexbin)](figures/03_dep_vs_arr_hexbin.png)

Most flights cluster near zero departure delay and land about 10 minutes early, and from there arrival delay rises roughly one-for-one with departure delay. So a late departure mostly stays late at the destination, and the pile-up in the top right corner is just the clipping at 240 and 300.

Drawn from a random sample of 300,000 flights (fixed seed).

### Figure 4: Daily trend

![Figure 4: Share of flights arriving 15+ minutes late, daily and 7-day mean](figures/07_daily_trend.png)

The median departure delay follows the resistant line closely, and the Theil-Sen slope of 0.93 means about 93% of an inbound delay shows up again on the next departure. The residuals are flat for most of the range, but early inbound legs don't lead to early departures, and the last bin at 240 drops by about 28 minutes where the data is thin.

Computed on all 6,965,247 flights.

### Figure 5: Missing previous-leg delay

![Figure 5: Missing previous-leg delay by leg of day and by carrier](figures/08_missingness.png)

Median departure delay at the busiest airports stays slightly early through the morning, then creeps up in the afternoon and evening, DFW reaches about 13 minutes late at hour 23 and ORD about 12 at hour 22. DEN and CLT peak around 6 to 7. The CLT spike rests on 80 flights at hour 0 and only 2 at hour 1, so you're not reading anything into it. This also explains the gaps at hours 2 to 4 in Fig 5, where the airports have too few flights to plot.

Computed on all 6,965,247 flights.

### Figure 6: Arrival delay by season

![Figure 6: Arrival delay by season](figures/10_season_violin.png)

Late aircraft delay is the largest or near-largest slice in most months, at about 4 in 10 delay minutes, with carrier delay close behind at roughly a third. Weather is at most about 10% and security is barely visible, and the mix stays fairly similar across months, so it doesn't point to one cause for the January and July spikes.

Computed on all 6,965,247 flights.

### Figure 7: Inherited delay and residuals

![Figure 7: Departure delay vs previous leg's arrival delay, with residuals](figures/04_inherited_delay_residuals.png)

The 7-day rolling mean shows the share of 15+ minute arrival delays peaking in mid-January (about 0.37), mid-July (about 0.42) and late December, and falling to about 0.1 to 0.15 in September to November. Those spikes are much bigger than normal day-to-day noise, so they're real events I still need to explain.

Computed on all 6,965,247 flights.

### Figure 8: Delay causes by month

![Figure 8: Share of delay minutes by cause](figures/06_cause_shares.png)

Previous-leg delay is missing for nearly every first leg of the day and for only about 1 to 2% of later legs, so the missingness is structural, not random. By carrier it ranges from about 19% (OH) to 33% (UA), probably because airlines differ in how many first-of-day flights they run, so filling in a value would be misleading.

Computed on all 6,965,247 flights.

### Figure 9: Delay by hour at the busiest airports

![Figure 9: Median departure delay by scheduled hour at the busiest airports](figures/05_delay_by_hour_hubs.png)

ASE has the highest share of 15+ minute departure delays at about 30%, followed by BWI, DFW and a group of Florida airports (FLL, MIA, MCO, EYW, PBI), and even the 15th airport is still near 23%. The list mixes big hubs with smaller or seasonal airports, so airport size alone doesn't explain delays.

Computed on all 6,965,247 flights.

### Figure 10: Worst airports

![Figure 10: Top 15 airports by share of 15+ minute departure delays](figures/09_worst_airports.png)

Median arrival delay is slightly early in every season (roughly -9 to -4 minutes), so the middle of the distribution barely changes. The difference is in the upper quartile, where summer's sits around 15 minutes late compared with about 3 in fall, so summer has the heavier late side.

Drawn from a random sample of 150,000 flights (fixed seed).

### Figure 11: Congestion

![Figure 11: Departure delays vs scheduled congestion](figures/11_congestion.png)

The share of 15+ minute departure delays rises from about 18% at the quietest hours to about 24% near 55 scheduled flights, but the line is bumpy and drops again at the busiest bins. The median only moves from -4 to -1 minutes, so congestion on its own is a weak signal and I'll treat it as one feature among several in Phase 3.

Computed on all 6,965,247 flights.

### Figure 12: Weekday and hour

![Figure 12: Delay chance by weekday and scheduled hour](figures/12_weekday_hour_heatmap.png)

Delay chance climbs through the day, from under 10% around 5 to 7 a.m. to about 35% at 8 p.m. on Thursday, Friday and Sunday, so schedule timing alone moves the risk about fivefold. The bright cells between 0 and 4 a.m. likely come from very few flights, so you won't over-read them.

Computed on all 6,965,247 flights.


## 5. First Analytics Results
Fig 4 (04_inherited_delay_residuals.png): Theil-Sen slope 0.93. Residuals flat near 0 from 0 to about 225 min. The earliest inbound bins sit above the line (+20 and +7), and the last bin (240) is about -28 where data is thin.
Fig 6 (06_cause_shares.png): late aircraft about 4 in 10 delay minutes, carrier about a third, weather at most about 10%, similar mix every month.
Fig 5 (05_delay_by_hour_hubs.png): DFW about 13 min at hour 23, ORD about 12 at hour 22, DEN and CLT about 6 to 7. The CLT spike rests on 80 flights at hour 0 and 2 at hour 1.
Fig 9 (09_worst_airports.png): ASE about 30% (only 7,307 departures), BWI 28.5%, DFW 27.5%, even the 15th airport is about 23%.
Fig 11 (11_congestion.png): share of 15+ departure delays about 18% to 24%, bumpy, and the median only moves from -4 to -1 min. Weak signal.
Fig 12 (12_weekday_hour_heatmap.png): share of 15+ departure delays under 10% around 5 to 7 a.m. and about 35% on Thursday, Friday and Sunday around 8 p.m.

## 6. Dead Ends
- Congestion counts gave only a weak signal.
- The raw-scale histogram hid the late tail until you tried the log view.
- A stray .parquet.zip file in the processed folder broke the dataset reader.
- The conda notebook kernel (pyarrow 19) couldn't read files written by the venv (pyarrow 25).

## 7. Design Decisions
1. Outliers: kept, not deleted

What I did: you marked about 9% of flights as extreme delays and left them in the data.
What I could have done: deleted them.
Why: long delays are exactly the thing you're studying, so deleting them would delete your answer.

2. Outlier cutoff: one per month

What I did: you worked out what counts as "extreme" separately for each month.
What I could have done: used one cutoff for the whole year.
Why: July has far more big delays than October, so one cutoff would treat the two months unfairly.

3. Delay-cause columns: filled with 0 and a flag

What I did: you put 0 in the blank cause columns and added a cause_unreported column.
What I could have done: left them blank.
Why: a blank usually means "not late enough to need a cause." The flag marks the few late flights whose cause is truly unknown.

4. Previous-flight delay: left blank when there was no earlier flight

What I did: you didn't fill it in for a plane's first flight of the day.
What I could have done: filled in a guess, like 0 or an average.
Why: a guess would invent a delay that never happened.

5. Processing: chunks, one Parquet file per month

What I did: you read each month's file in small pieces and saved each month separately.
What I could have done: loaded all 7 million rows at once, or used Dask.
Why: it used only about 150 MB per month and took 31 seconds in total.

6. Plots: drawn from a random sample

What I did: the plots for Figures 1, 2, 3 and 10 use 300,000 or 150,000 flights picked at random (fixed seed, so it's repeatable).
What I could have done: plotted all 7 million.
Why: plots stay fast and readable. The tables and totals still use every flight.


## 8. Reproducibility Statement
<!-- Confirm the dry run: who ran it, on what machine/fresh environment, date. Only write this after you actually do it. -->

## 9. References
Tukey (1977), Exploratory Data Analysis. The handout gives it.
VanderPlas (2016), Python Data Science Handbook. The handout gives it.
BTS TranStats, the data source.
