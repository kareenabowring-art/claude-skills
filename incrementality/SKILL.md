---
name: incrementality
description: Design, analyse and report incrementality tests (geo holdouts, Conversion Lift, audience holdouts, on/off tests) for Google Ads, Performance Max, brand search and retargeting, giving incremental ROAS/POAS. Use when asked "is this channel incremental", "would these sales have happened anyway", "test retargeting", "lift test", "holdout", "iROAS" or "prove the ads work".
---

# Incrementality

Platform attribution answers "which ads touched the people who bought?". Incrementality answers the only question that matters for budget: **"how many sales would NOT have happened without this spend?"** The gap between the two is largest for exactly the channels this agency runs: retargeting, brand search, and Performance Max (which leans on brand and returning-customer traffic). Treat every attributed number as an upper bound until a test says otherwise.

Be thorough and honest. A test that shows retargeting is less incremental than claimed is still a win: it lets you reallocate budget and it builds credibility that a "10x ROAS" slide never will. Never shade a result to flatter the agency or the client.

## Files in this skill
- `references/methods.md` covers every test method, when to use it, formulas, and failure modes. Read it before recommending a design.
- `references/retargeting.md` covers retargeting-specific design (ITT vs exposed, dilution correction, audience holdouts, PSA vs ghost ads, frequency and window tests).
- `references/google-ads-playbook.md` covers how to run each test inside Google Ads (Conversion Lift, geo targeting in Australia, brand search tests, PMax, Shopping), plus data pulls via Windsor.ai.
- `references/report-template.md` holds the pre-registration plan and the client results report.
- `scripts/geo_test.py` is the geo test toolkit: `design` (pick treatment/control geos and estimate power/MDE) and `analyze` (synthetic control + time-based regression with placebo inference, iROAS/iPOAS).
- `scripts/holdout_test.py` analyses user/audience holdouts (conversion and revenue lift, bootstrap CIs, ITT dilution correction, iROAS/iPOAS).

Run scripts with `python3 scripts/<name>.py --help`. They need pandas, numpy, scipy and matplotlib (`pip install pandas numpy scipy matplotlib`).

## Workflow

Use a task list; this is multi-stage work. Do every stage. If the user only wants one stage (e.g. "just analyse this test"), still run the checks for that stage in full.

### 1. Frame the question
Pin down, in writing:
- **The decision** the test will inform (e.g. "cut retargeting from $20k to $8k/month?", "pause brand search?", "scale PMax 30%?"). No decision means no test; push back.
- **Channel / campaigns in scope** and the **treatment**: holdout (turn off for some), go-dark (turn off everywhere for a period), or heavy-up (increase spend for some).
- **Primary KPI**: prefer business-side truth (Shopify/backend orders and revenue, new customers) over platform-reported conversions. Platform conversions are fine as a secondary KPI.
- **Economics**: AOV, gross margin % (for POAS), and the client's break-even iROAS (= 1 / gross margin). Ask for margin; if unknown, state an assumption and show sensitivity.
- **Current claimed performance**: platform ROAS, conversions, spend for the scope, so you can compute the *incrementality factor* (incremental ÷ attributed).
- **Constraints**: minimum and maximum acceptable revenue risk, blackout dates (sales, launches, BFCM, EOFY in Australia: June), how long the client will tolerate a holdout.

If the client is present, ask for missing items (max ~4 questions at once). If not, state assumptions explicitly at the top of the plan.

### 2. Diagnose before testing (free signals)
Before spending money on a test, look for evidence already in the data. Pull 12–24 months of daily data where possible (Windsor.ai connector for Google Ads; Shopify/GA4 for backend). Check:
- **Natural experiments**: past outages, budget caps hit mid-day, paused campaigns, account suspensions, stock-outs. Run `geo_test.py analyze` with series in place of geos (the affected series as "treatment", unaffected series such as other product lines or organic sessions as controls), or simple pre/post with a control series (organic sessions or a non-advertised region/product), to see whether backend revenue moved when spend moved.
- **Spend-to-revenue elasticity**: weekly spend vs backend revenue, controlling for seasonality. Flat backend revenue across big spend swings is a red flag.
- **Audience composition**: share of conversions from returning customers, branded queries, and users who were already in checkout/cart. High shares mean high cannibalisation risk.
- **View-through and click-through mix** for display/YouTube retargeting; view-through-heavy attribution is the weakest evidence.
- **Conversion lag and frequency**: very short lags on retargeting (minutes after a site visit) suggest the ad is catching people who were already returning.
Summarise as a "prior" for each channel: likely highly / moderately / weakly incremental, with reasons. This sets expectations and helps size the test.

### 3. Choose the method
Use the decision guide in `references/methods.md`. Short version:
- **Retargeting (Display/YouTube/Demand Gen/PMax remarketing)** → user-level Conversion Lift in Google Ads if eligible (≈1,000+ conversions and ≈$5k test budget; Search and PMax became self-serve in Oct 2026), else an **audience holdout** (random split of the remarketing list, exclude the holdout half) analysed with `holdout_test.py`, else a **geo holdout**.
- **Brand search** → geo holdout (pause brand in treatment geos) or a matched on/off test, measured on *total* backend revenue and total Google clicks (brand paid + organic), never on paid brand conversions.
- **PMax / Shopping / non-brand search** → geo holdout or geo heavy-up via `geo_test.py`, or Google's geography-based Conversion Lift via a rep. Consider a 3-cell design (control / PMax off / PMax with brand exclusions) when cannibalisation is the question.
- **Whole-account "is Google working"** → geo go-dark holdout, or calibrate an MMM (Meridian) with a geo test.
- **Too small to test** (can't reach the MDE in ≤8 weeks) → say so plainly. Offer diagnostics, a longer/larger holdout, or a heavy-up test instead. Don't run an underpowered test and present noise as a result.

### 4. Design and power
For geo tests, run:
```
python3 scripts/geo_test.py design --data daily_geo.csv --date-col date --geo-col geo --kpi-col revenue \
  --test-days 28 --treatment-share 0.3 --n-candidates 2000 --out design/
```
This searches stratified random splits for the treatment group whose pre-period tracks the control best, then backtests to estimate the false-positive rate and the **minimum detectable effect (MDE)** at 80% power for several test lengths. It needs history of at least 4× the test length (e.g. 16+ weeks for a 4-week test). Use `--force-control` for geos that must stay on (e.g. a flagship metro) and `--primary sc|tbr` to match the method you'll report. Treat the MDE as optimistic (add ~25%). Read its output and decide:
- Is the MDE smaller than the effect we expect? Translate: expected lift = channel spend × expected iROAS ÷ baseline revenue in treatment geos. If MDE > expected lift, extend duration, enlarge the treatment share, use a heavy-up, or don't test.
- **Australian geos**: states are too few (8) for a good geo test. Use Google Ads targetable regions below state level: postcodes grouped into clusters, or ABS SA4 regions (~90). Keep Sydney, Melbourne and Brisbane metro either split across groups via sub-regions or held in control; never let one metro decide the result. See `references/google-ads-playbook.md`.
- Add a **cool-down** (≥ conversion lag, typically 7–14 days) after the test for lagged effects.
- For user holdouts: the holdout share (10–50%) trades revenue risk for precision. Compute power with `holdout_test.py power`.

### 5. Pre-register
Fill in the pre-registration section of `references/report-template.md` and get client sign-off **before launch**: hypothesis, treatment, geos/groups, dates, primary KPI, analysis method, MDE, decision rules ("if iROAS < 1.5 we cut to X; if > 3 we scale to Y"). Changing the KPI or method after seeing results is how tests lie.

### 6. Run and monitor
- Freeze other changes in test scope (bids, budgets, creatives, new campaigns) or apply them equally to both groups.
- Check daily for the first 3 days that the treatment actually applied: spend in holdout geos ≈ 0, impressions in holdout audience ≈ 0, and no spill from other campaigns (e.g. PMax picking up remarketing users you excluded from Display).
- Do not peek-and-stop. Only stop early for a pre-agreed guardrail breach (e.g. revenue in treatment down > X%).
- Log anything unusual (promos, stock-outs, site outages, competitor events) with dates.

### 7. Analyse
Geo:
```
python3 scripts/geo_test.py analyze --data daily_geo.csv --date-col date --geo-col geo --kpi-col revenue \
  --treatment-geos "SYD-N,MEL-E,..." --pre-start 2026-03-01 --pre-end 2026-08-31 \
  --test-start 2026-09-01 --test-end 2026-09-28 --design holdout --spend-change 12000 \
  --margin 0.45 --platform-attributed 41000 --out results/
```
- `--design holdout|heavyup` is required; it sets the sign, so results always read as "value the ads drive".
- `--spend-change` is the amount of spend removed (holdout) or added (heavy-up) in the treatment geos during the test, as a positive number.
- KPI in orders? Add `--kpi-type orders` and `--value-per-unit <AOV>`; without AOV you get incremental orders and cost per incremental order, not iROAS.
- `--platform-attributed` must be in the same units as the KPI: what the treated spend normally claims over an equally long period (holdout: the treatment geos' attributed value in a comparable pre-period).
- Use a pre-period of at least 4× the test length and the same `--primary` method as in design, so the reported interval matches the design's MDE. The script reports one interval (in-time placebo basis, with fallbacks) and prints wider checks when other inference methods disagree; mention those in the report.

User holdout:
```
python3 scripts/holdout_test.py analyze --test-users 180000 --test-conversions 2700 --test-revenue 310000 \
  --control-users 20000 --control-conversions 270 --control-revenue 30500 \
  --spend 18000 --margin 0.45 --exposure-rate 0.62 --platform-attributed-revenue 160000
```
Always check, and report:
- **Pre-period fit** (MAPE, R²). Poor fit → widen the confidence interval in your mind and say so.
- **Agreement between methods** (synthetic control vs TBR). Disagreement is a finding; report both.
- **Placebo rank / p-value and the interval**, not just the point estimate. If the interval includes zero, the honest result is "not distinguishable from zero at this test size", plus what that rules out (e.g. "iROAS above 4 is unlikely").
- **Sanity**: is the implied lift plausible relative to the spend? An iROAS of 30 on retargeting is a red flag for a broken test, not a triumph.
- Read `references/methods.md` → "Threats to validity" and go through each one.

### 8. Translate into money and decisions
Report all of:
- Incremental conversions / revenue (with interval)
- **iROAS** = incremental revenue ÷ incremental spend
- **iPOAS** = incremental gross profit ÷ incremental spend (= iROAS × margin). Below 1 means the channel loses money.
- **Incrementality factor** = incremental ÷ platform-attributed (use it to adjust platform ROAS going forward: "true ROAS ≈ platform ROAS × factor")
- **Cost per incremental conversion / new customer**
- The decision under the pre-registered rules, and the expected annualised profit impact.
Explain diminishing returns: a holdout measures the *average* return of the whole channel; the *marginal* dollar is usually worse. Heavy-up tests measure the marginal return.

### 9. Report
Use the results section of `references/report-template.md`. Lead with the decision and the money; put methodology after. Use plain language ("for every $1 spent on retargeting, about $1.80 of sales would not have happened otherwise"). Include the chart from `geo_test.py` (actual vs counterfactual, cumulative effect). If the user wants it kept or shared, publish it as a document. Recommend a re-test cadence (every 6–12 months, or after major changes) and any follow-up test (e.g. frequency cap or lookback window test for retargeting).

## Tone and guardrails
- Separate what the data shows from what you infer. Give intervals, not just points.
- Never claim significance from a single noisy test; never present a non-significant test as "no effect" without stating the MDE.
- Don't use client names in anything meant for prospects.
- If the client's data can't support a valid test, say so and propose the best feasible alternative.
