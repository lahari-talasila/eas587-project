# Raw data — download instructions

Raw monthly files are **not committed** to this repository (they are large and fully
reproducible). Use the steps below, or the `src/data_access.py` script, to obtain them.

## Primary dataset — Airline On-Time Performance (BTS, Table 236)

**Portal (field-selectable download):**
`https://www.transtats.bts.gov/DL_SelectFields.asp?Table_ID=236&DB_Short_Name=On-Time`

**Manual steps:**
1. Open the portal above (JavaScript must be enabled).
2. Set **Filter Year** and **Filter Period** (e.g., 2024 / January).
3. Check **"Prezipped File"** to get all ~110 fields, or leave it unchecked and select
   only the columns you need.
4. Click **Download** at the bottom — you receive a `.zip` containing one CSV per month.

**Scripted (recommended):**
```bash
python ../../src/data_access.py --dataset ontime --year 2024 --month 1 --out .
```
The script uses the prezipped monthly-file URL pattern:
`https://www.transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_<YYYY>_<M>.zip`
(BTS occasionally adjusts this filename format — verify one month before batch-downloading.)

## Fusion dataset — T-100 Domestic Segment (U.S. Carriers)

From TranStats: **Data Finder → Aviation → "T-100 Domestic Segment (U.S. Carriers)"**,
or the field-selection page for the T-100 segment table. Download the month(s) matching
your On-Time window. Join key: carrier + origin + destination + year + month.

## Notes
- Source: U.S. DOT, Bureau of Transportation Statistics — U.S. public-domain data.
- Each On-Time monthly zip is ≈20–30 MB compressed, expanding to a few hundred MB of CSV.
- Be polite to the server: throttle automated downloads (the script adds a delay).
