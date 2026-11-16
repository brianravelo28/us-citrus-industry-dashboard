# Methodology

What the code does and why. Headline results are in the [README](../README.md); the numbers here are the supporting detail.

Contents: [Terms](#terms) · [Data sources](#data-sources) · [Data and cleaning](#data-and-cleaning) · [Totals and gaps](#totals-and-gaps) · [Checks on the data](#checks-on-the-data) · [Constant dollars, shares and units](#constant-dollars-shares-and-units) · [Reproducibility](#reproducibility) · [Deployment notes](#deployment-notes)

## Terms

| Term | Meaning |
|---|---|
| NASS | USDA National Agricultural Statistics Service |
| QuickStats | NASS's online database and API |
| Bearing acres | Acres of trees old enough to bear fruit |
| Utilized production | The part of the crop that was used, sold fresh or processed, counted in boxes |
| Value of production | Utilized production valued at the packinghouse-door price |
| PHD equivalent | Packinghouse-door equivalent: a price or value measured at the packinghouse door, the point of first sale after packing costs are taken out, so fruit sold fresh and fruit processed are on one basis. NASS's Citrus Fruits Summary defines the packinghouse-door price this way |
| Season | A crop year, labeled by its end year (2023 is the 2022-23 season) |
| HLB | Huanglongbing, citrus greening disease |
| BLS | US Bureau of Labor Statistics |
| CPI-U | Consumer price index for all urban consumers, all items: a measure of the general price level |
| Constant dollars | Dollars expressed in the prices of one chosen season, here 2025, so that different seasons can be compared |

## Data sources

| Source | What | Version used |
|---|---|---|
| USDA NASS QuickStats, survey data at state level | Bearing acres, yield, utilized production (boxes and tons), value of production and price per box for oranges, grapefruit, tangerines, lemons and tangelos in Florida, California, Texas and Arizona, 1990-2026: `data/citrus_by_state.csv` | Pulled 2026-11-10; checksum in `data/manifest.json` |
| USDA NASS QuickStats, commodity `CITRUS TOTALS` | NASS's own state totals across all citrus for bearing acres and value of production, 2008-2026: `data/citrus_totals_by_state.csv` | Pulled 2026-11-10; checksum in `data/manifest.json` |
| BLS CPI-U, all items, US city average, not seasonally adjusted (series CUUR0000SA0) | Monthly consumer price index, October 1989 to October 2026: `data/cpi_u_monthly.csv` | Retrieved 2026-11-10; checksum in `data/manifest.json` |

**Data foundation.** *Provenance:* the citrus series are NASS's published state-level survey estimates, the figures of its annual Citrus Fruits report, read through QuickStats; the price index is BLS's. *Time coverage:* annual seasons, 1990 to 2026 (this project's start), with NASS's all-citrus totals from 2008 and a monthly price index from October 1989. The season ending in 2026 is NASS's preliminary estimate and is revised a year later, so each pull is a snapshot of its date. *Sampling:* these are survey estimates, not a census. QuickStats's coefficient-of-variation field, the one place NASS would publish sampling error, is blank on every row checked (7,818 rows across six queries, on 2026-11-10), so no sampling error is carried through. *Quality and labels:* blanks, one conflicting yield and three small mismatches are counted below. *Real or synthetic:* all values are real observations; none is synthetic. *Licence:* NASS data are used under the NASS API Terms of Service, which require the notice "This product uses the NASS API but is not endorsed or certified by NASS" (shown in the dashboard); BLS content is in the public domain, and BLS's API terms ask for the retrieval date and the statement that BLS.gov cannot vouch for the data or analyses derived from them once retrieved (also shown). *A better source:* NASS's own state totals are used from 2008; the Census of Agriculture, every five years, would give acreage to cross-check against and is not used.

## Data and cleaning

**Measure.** `src/fetch_industry_data.py` pulls one statistic and unit per measure from QuickStats (`agg_level_desc=STATE`, `source_desc=SURVEY`) for each fruit and writes one row per fruit, state, year and measure. It also pulls NASS's own state totals (`CITRUS TOTALS`) for bearing acres and value. Both files were pulled on 2026-11-10.

| Measure | QuickStats statistic and unit | Notes |
|---|---|---|
| Bearing acres | `AREA BEARING`, `ACRES` | |
| Yield | `YIELD`, `BOXES / ACRE` | Florida oranges also carry a gallons-per-box series; only boxes per acre is used |
| Utilized production | `PRODUCTION`, `BOXES` and `TONS`, utilization `UTILIZED` | Boxes cover 1990-2026; tons exist only for recent years (151 rows), so tons are fetched but not used by any chart |
| Value of production | `PRODUCTION`, `$, PHD EQUIV` | Packinghouse-door equivalent dollars, as reported by NASS |
| Price per box | `PRICE RECEIVED`, `$ / BOX, PHD EQUIV`, marketing year | |

**Exclusions.** The fetch keeps the all-classes total and drops the rest, counting rows at each step in the order shown (`data/fetch_report.json`, written by the fetch):

| Step | Rows dropped | Rows left |
|---|---|---|
| Rows the 30 fruit-and-measure queries return (state level, survey, 1990-2026 as requested) | | 20,671 |
| Not the all-classes total (single varieties and types) | 8,269 | 12,402 |
| Not the stated utilization (the fresh and processing splits, or the all-practices row) | 5,585 | 6,817 |
| A domain split instead of the total | 0 | 6,817 |
| Not the final annual value: the monthly forecasts of the same season (`YEAR - JAN FORECAST` and so on) and the monthly price rows | 4,312 | 2,505 |
| A season after 2026: NASS's forecast for the coming season | 22 | 2,483 |

The final table has 2,483 rows. The two queries for NASS's all-citrus totals return 152 rows and drop none, so `data/citrus_totals_by_state.csv` has 152 rows. The script stops if a state-year has more than one row after the filters.

- **Seasons.** The season ending in 2026 is NASS's preliminary estimate (published August 2026) and is marked `status = preliminary`; all earlier seasons are `reported`.
- **Forecast rows are dropped.** QuickStats can return NASS's forecast for the coming season even when the request stops at 2026; it returned 22 production rows for the season ending in 2027 (issued October 2026). A forecast is not data, so anything after the last season is dropped, the drop is counted above, and a test checks the file.
- **Blanks stay blank.** A value NASS withheld ("(D)") or marked not available is kept as a blank row with the reason in the `note` column. Of 2,483 rows, 63 are blank (48 withheld, 15 not available), mostly California and Arizona value and price figures for tangerines and lemons in 2009-2016 and Arizona oranges in 2010-2012. For Texas oranges and grapefruit, 1991 has a bearing-acres row and no yield, production, value or price row.
- **Counts under charts.** The count under each chart is the number of NASS values behind it; under 30 it carries an asterisk. The only charts under 30 are the six Florida tangelos charts (27 values each).

## Totals and gaps

**Sums of the fruit values.** A total built from the fruit rows (for a year, a state or a fruit) is shown only when every series NASS publishes in that year has a value. A series counts as published in a year if the year falls between its first and last published year (`src/citrus_data.py`). So a withheld value, a missing year (Texas 1991) or a series that has not started leaves a visible gap, while a series that has ended (Arizona oranges after 2012) simply stops being part of the total. Stacked charts leave a whole year empty instead of drawing a partial stack. On this rule alone the acreage total has a gap in 2010-2012 and the value total in 1991 and 2009-2016.

**NASS's own state totals.** QuickStats publishes state totals across all citrus (`CITRUS TOTALS`) for bearing acres and value of production from 2008, and these include the values NASS withholds at the fruit level. From 2008 the US and state totals on the dashboard are NASS's totals; before 2008 they are the sums above (`combined_total` in `src/citrus_data.py`). A US total is stated only when NASS's totals cover all four states. Consequences: the acreage total has no gap; the value total has one, 1991 (Texas has no value row and NASS publishes no totals before 2008); the value-by-fruit stacks stay empty in 1991 and 2009-2016, and the total is drawn as a line across them. As reported by NASS, the US value total is highest in 2012 ($3.71 billion), with $3.70 billion in 2014, $3.53 billion in 2017 and $3.15 billion in 2026 (preliminary); in constant dollars the order changes (see Constant dollars below). Acreage peaks and per-state figures use each total's own complete years.

## Checks on the data

- **Yield against production and acreage.** NASS defines yield as utilized boxes divided by bearing acres, and in the data the two agree. The fetch compares every published yield with that ratio (463 fruit-state-years) and flags any that differ by more than 15%. **One does: California oranges in 2022.** QuickStats publishes 58 boxes per acre, but the same database gives 39.1 million utilized boxes and 137,000 bearing acres for 2022, which imply about 285 (the 2022 crop fell about 20% from 2021 in a drought year, but not to 58). NASS's printed [Citrus Fruits 2022 Summary](https://esmis.nal.usda.gov/sites/default/release-files/j9602060k/pn89ff24k/1544cx74m/cfrt0922.txt) (September 2022, table "Orange Acreage, Yield, Utilization, Price, and Value by Type") gives California all oranges for 2021-22 as 140,000 acres, 289 boxes per acre and 40,400 thousand boxes, with later revisions to the production and acreage figures. The published 58 is therefore at odds with the printed report and with two other values in QuickStats. It stays in the data file; the dashboard draws it as a gap with a footnote, and does not substitute a computed value. How the error entered QuickStats is not known.
- **Fruit values against NASS's totals.** For the 76 state-years in 2008-2026 the fetch compares the sum of the fruit values with NASS's own state total. For bearing acres the two are equal in all 76. For value of production they are equal in 57; in 16 the fruit sum is partial because a fruit value is blank (California and Arizona, 2009-2016); in 3 every fruit value is present and the fruit sum is slightly above NASS's total: California 2018 (0.93%), Florida 2018 (0.32%) and Florida 2020 (0.03%). The cause is not known; the fruit rows and the total row of each were loaded into QuickStats on the same date (2024-01-03), so it is not a later revision of one side. So the change from sums to NASS's totals in 2008 moves no acreage figure, and moves a value figure by at most 0.93% where both are complete. A test checks all of this.
- **Other unusual values.** The fetch also prints yields and prices more than three times away from their own series' median. The ones examined (Florida after 2023, Texas 1992) agree with NASS's production and acreage: Florida's collapse and the Texas freeze-year lows are real, not data errors.

## Constant dollars, shares and units

- **Two ways to show dollars.** NASS reports value of production and price in the dollars of the season they were earned (nominal). The dashboard shows them as reported or in constant 2025 dollars, chosen with a toggle (constant dollars by default). Each state's **share** of the US value in the same year is unaffected either way, so the headline uses shares and physical measures (acres, boxes) for change over time.
- **Constant dollars.** A season's nominal value is multiplied by CPI(2025 season) divided by CPI(that season), where CPI is the BLS CPI-U (all items, US city average, not seasonally adjusted; series CUUR0000SA0) averaged over the season's twelve months, October of the year before to September of its end year (`season_cpi` and `real_factors` in `src/citrus_data.py`). The base is the 2025 season, the last NASS reports as final, and its factor is exactly 1; the factor is 2.49 for 1990, 1.87 for 2000, 1.47 for 2010 and 0.97 for the 2026 season. The index measures general purchasing power. It is not a citrus price index, so a real value shows what the dollars could buy in general, not whether citrus became cheaper or dearer relative to other goods. The data file runs from October 1989 so the 1990 season has its twelve months.
- **Season alignment.** The season is lined up with its own months rather than with the calendar year of its end year. The two choices give factors within 1.1% of each other in every season from 1990 to 2025 (mean difference 0.24%), and the same highest year; a test checks the bound.
- **A month BLS did not publish.** BLS published no CPI-U value for October 2025 (the lapse in federal appropriations); the fetch keeps the month as a blank row with BLS's reason. The season ending in 2026 (October 2025 to September 2026) therefore averages its other 11 months, and a season needs at least 11 of its 12. Dropping any one month from a season in 1990-2025 changes its mean by at most 0.35% (October 2021, the 2022 season); for the 2026 season the real values would be about 0.16% higher if October were replaced by the average of September and November. Tests check both bounds.
- **What changes with the choice of dollars.** The US value of production is highest in 2012 ($3.71 billion) as reported and in 1990 ($5.49 billion, the first year of the data) in 2025 dollars; in 2026 it is 15% and 45% below those, respectively. California's value is highest in 2026 as reported and in 2018 ($3.07 billion) in 2025 dollars; Florida's is highest in 2012 as reported and in 1991 ($3.72 billion) in 2025 dollars. Tests recompute these figures.
- **Yield units differ by state.** Box weights differ across states, so raw boxes per acre are not comparable across states. The dashboard offers yield as a share of each state's own peak, and notes this on the yield chart.
- **Dollars add up, boxes do not.** Different fruits and states have different box weights, so totals across them use acres and dollars only.

## Reproducibility

**Run order.** `python src/fetch_industry_data.py` (needs the `NASS_KEY` environment variable; nothing is stored in the code) writes the two NASS files, `data/fetch_report.json` and their manifest entries; `python src/fetch_cpi.py` (no key) writes the price-index file and its manifest entry. The dashboard and the tests read the committed files. Each fetch retries transient failures, then stops and writes nothing if any request fails, a response reports success and returns nothing, a state-year has more than one citrus row, or a month of the price index is missing inside the range.

**Determinism.** The fetch has no random step: the same QuickStats and BLS responses give the same files, and a changed response gives a different file (both tested against mocked responses). Reruns in a clean Python 3.14.7 environment with the pinned packages gave files identical to the committed ones (the NASS fetch on 2026-11-10, the price-index fetch on 2026-11-16); NASS and BLS revise their newest values, so a later pull can differ.

**Data version.** `data/manifest.json` records each data file's source, the date it was pulled, its row count and its SHA-256 (computed with line endings normalized, so a Windows and a Linux checkout agree); the fetch scripts write it, the dashboard's source notice reads the dates from it, and a test fails if a data file changes without its entry.

**Software.** `requirements.txt` pins every package (Python 3.12 or newer; numpy 2.5 needs 3.12); `requirements-dev.txt` adds pytest. The live service runs Python 3.14.8. CI runs the tests on Python 3.12, 3.13 and 3.14 and starts the app under gunicorn to call `/healthz`, `/debugz` and the front page.

**Tests.** Tests (`tests/`) cover the totals rule, the use of NASS's totals, the yield cross-check, the committed data and the manifest (each data file matches its recorded SHA-256 and row count), the fetch against mocked QuickStats responses (the filters, the row counts in the table above, and the failures: a duplicate state-year, a response that reports success and returns nothing, an unexpected value), constant dollars (the base season has a factor of 1; the bounds on the season alignment and the missing October 2025 month), the price-index fetch against mocked responses (including one that reports success and returns nothing), every dashboard control in both dollar modes, the layout (a collapsed "About this chart" section and a correct count under every chart, the asterisk under 30 values, the source notices), and `/healthz` and `/debugz`; they do not call the NASS or BLS APIs and do not check how the page looks, which is checked by hand after each deploy. `src/doc_figures.py` recomputes every figure quoted in the README, this document and the schema doc from the committed data, and a test fails if a document no longer states it.

## Deployment notes

The dashboard runs on Render's free plan from `main` (`render.yaml`), started with `gunicorn src.app:server`; the health check path is `/healthz`, and the Render dashboard's settings override `render.yaml`. On 2026-11-16 `/debugz` on the live service reported Python 3.14.8 and the pinned package versions (dash 4.5.0, plotly 7.1.0, pandas 3.1.1, numpy 2.5.5, gunicorn 27.0.1), and a resident memory of 122.1 MB 286 seconds after the process started, before any page had been loaded, and 136.3 MB after all three tabs and both dollar modes had been used. These are hosted figures from one process; local figures differ.
