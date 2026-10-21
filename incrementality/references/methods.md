# Incrementality methods

## Key definitions
- **Incremental outcome** = outcome with ads − outcome without ads (the counterfactual). Never directly observed; every method is a way to estimate the counterfactual.
- **Lift %** = incremental ÷ counterfactual baseline.
- **iROAS** = incremental revenue ÷ incremental spend.
- **iPOAS** = incremental gross profit ÷ incremental spend = iROAS × gross margin. Break-even iPOAS = 1; break-even iROAS = 1 ÷ margin.
- **Incrementality factor (IF)** = incremental conversions ÷ platform-attributed conversions. "Calibrated ROAS" = platform ROAS × IF.
- **MDE** (minimum detectable effect): the smallest true lift the design detects with the chosen power (80%) at the chosen false-positive rate (10% two-sided or 5% one-sided is typical for marketing). If true lift < MDE, a "no significant effect" result is expected even when the channel works.
- **Average vs marginal return**: holdouts/go-dark measure the average return of all the spend; heavy-ups or partial cuts measure the return of the next or last dollar. Budget decisions are about the margin.

## Decision guide

| Question | Best method | Fallback |
|---|---|---|
| Is retargeting incremental? | User-based Conversion Lift (Google) | Audience holdout split → `holdout_test.py`; geo holdout |
| Is brand search incremental? | Geo holdout pausing brand in treatment geos | Time-based on/off alternating weeks (weak) |
| Is PMax / Shopping / non-brand incremental? | Geo holdout or geo-based Conversion Lift | User-based Conversion Lift (Search/PMax self-serve since Oct 2026) |
| What's the return of the next $? | Geo heavy-up (e.g. +50–100% spend in treatment geos) | Multi-cell geo test with several spend levels |
| Is the whole Google account working? | Geo go-dark (pause everything in treatment geos) | MMM (Meridian) calibrated by a geo test |
| Which retargeting setting is best (window, frequency)? | Multi-cell audience split | Sequential tests (weak) |
| Can't run a test | Natural-experiment analysis, MMM | Report diagnostics with clear caveats |

## 1. Randomised user holdout (Conversion Lift, audience split)
**How**: randomly split eligible users; control is withheld from ads; compare outcomes.
- Google Ads **user-based Conversion Lift**: self-serve for Video, Demand Gen, Display, and since 7 Oct 2026 Search and PMax; needs ~1,000+ observed conversions and ≈$5k minimum test budget; availability varies by account; uses Bayesian methods with priors since May 2025 (results come as probability of lift and credible intervals). Relies mostly on opted-in/signed-in traffic, so measurement gaps exist.
- **DIY audience split** (no Google rep needed): Google Ads can't split an audience by hash itself, so build the split outside it: (a) Customer Match: hash emails, upload test and holdout as two lists; or (b) site audiences: set a user-scoped "bucket" dimension on the site (e.g. GA4 user property = hash(user/client ID) % 100) and build two GA4 audiences from it; exclude the holdout segment from **all** campaigns that could reach them (Display, YouTube, Demand Gen, PMax via audience exclusions where possible — PMax can still reach them through other signals; note this as contamination). Measure outcomes in the client's backend by segment.
- **Analysis**: compare conversion rate and revenue per user (intent-to-treat). See `retargeting.md` for dilution correction.
- **Pros**: highest internal validity; small effects detectable with large audiences.
- **Cons**: cookie/ID loss and cross-device leakage bias toward zero; PMax and other campaigns can leak ads to the holdout; only measures the in-platform audience.

## 2. Geo experiments (matched market / synthetic control)
**How**: assign regions to treatment and control; change spend only in treatment; estimate the counterfactual for treatment from control regions using the pre-period relationship.
- **Designs**: holdout (pause in treatment), go-dark (pause everything), heavy-up (increase in treatment), multi-cell (several treatment levels).
- **Analysis (in `geo_test.py`)**:
  - *Synthetic control (SC)*: weights on control geos (non-negative, sum to 1, plus level intercept) chosen to match the treatment series in the pre-period; counterfactual = weighted control in test period.
  - *Time-based regression (TBR)*: regress treatment aggregate on control aggregate in pre-period (y = a + b·x); predict test period; interval accounts for parameter and residual uncertainty, accumulated over days. This is the method behind Google's GeoX.
  - *Inference*: (a) **in-time placebo / backtests**: run the same analysis on many fake test windows inside the pre-period, where the true effect is zero, to get the noise distribution of the cumulative effect; (b) **in-space placebo**: treat random control-geo groups as fake treatment. p-value = share of placebo effects at least as large (in relative terms) as the observed one.
- **Requirements**: enough geos (≥20 ideally; ≥10 at minimum) with stable, correlated KPIs; pre-period of at least 4× the test length (16+ weeks for a 4-week test; 6–12 months is better), so there are enough backtest windows for inference; test length usually 3–8 weeks plus cool-down.
- **Pros**: privacy-proof (no user tracking), measures total business outcomes including offline and organic spillover, works for brand search and PMax.
- **Cons**: noisier than user splits, so budgets must be larger; vulnerable to regional shocks (weather, local promos, store openings, state lockdowns or public holidays: in Australia, check state-specific holidays like the King's Birthday dates, Melbourne Cup day, Ekka, show days); geo-targeting leakage (people travel, location targeting uses "presence" settings).
- Open-source alternatives: Google Meridian GeoX (TBR, multi-cell, calibrates Meridian MMM), Meta GeoLift (augmented SC), CausalImpact (Bayesian structural time series).

## 3. Time-based on/off tests
**How**: turn the channel off (or on) for a period nationally; compare to forecast.
- Use only when geo or user tests are impossible. Strengthen with: alternating on/off blocks (e.g. weekly switching for 6–8 weeks), a control series (unaffected product line, organic sessions, a non-advertised market), and the `geo_test.py analyze` script using a "national vs control series" setup.
- **Cons**: confounded by seasonality, promos, and everything else that changes over time. Treat as directional.

## 4. PSA / ghost ads
See `retargeting.md`. Useful for platform-run tests; usually not available to an agency in Google Ads beyond what Conversion Lift does internally.

## 5. Marketing mix modelling (MMM)
- Regression of total sales on spend by channel, with adstock and saturation, controlling for seasonality, price, promo.
- Gives channel-level incremental contribution and response curves, but correlational; it needs calibration from experiments to be trusted. Google Meridian (open source, Bayesian) accepts experiment results as priors; GeoX produces those priors.
- Recommend MMM only for clients with 2+ years of weekly data and several channels of meaningful spend. Otherwise prefer experiments.

## 6. Natural experiments and diagnostics
Outages, budget caps, policy disapprovals and stock-outs create quasi-experiments. Analyse with interrupted time series plus a control series. Label as observational.

## Power and sample size
- **User holdout, conversion rate**: n per group ≈ (z₁₋α/2 + z₁₋β)² × [p₁(1−p₁) + p₂(1−p₂)] ÷ (p₁ − p₂)². With small baseline rates and small lifts, required sizes are large; e.g. baseline 1.5%, true lift 10% → ~108k per group (50/50 split) at 80% power, α = 0.05 two-sided. Use `holdout_test.py power`.
- **Revenue per user** is noisier than conversion rate (heavy tails); use bootstrap and expect larger n.
- **Geo tests**: use `geo_test.py design` backtests. Rules of thumb: MDE often 3–10% of treatment-geo KPI for 4-week tests; the share of revenue the channel drives must be comfortably above this.
- **Bigger effect, cheaper test**: test the whole channel (go-dark) before testing tweaks; use heavy-ups of 2× rather than +20%.

## Threats to validity (check every one)
1. **Contamination / leakage**: control still exposed (PMax reaching excluded users, YouTube on shared devices, geo presence vs interest settings, people commuting across regions). Biases toward zero.
2. **Spillover**: treatment affects control (national TV/brand halo, word of mouth). Biases toward zero.
3. **Budget reallocation inside the platform**: pausing a campaign in some geos can let Smart Bidding push its budget elsewhere (including into control geos), inflating control. Cap budgets or reduce them proportionally.
4. **Simultaneous changes**: promos, price changes, site launches, new campaigns, stock-outs during the test. Must be equal across groups or logged and handled.
5. **Seasonality and shocks**: pre-period that doesn't resemble the test period (e.g. pre in winter, test over BFCM). Regional shocks (weather, state holidays, local events).
6. **Novelty / carryover / lag**: effects continue after ads stop (memory, cookies, abandoned carts) → include a cool-down and measure it; first days of a holdout often understate the effect.
7. **Selection bias**: comparing exposed vs unexposed users (non-random) instead of randomised groups. Never present exposed-vs-unexposed as incrementality.
8. **Measurement**: platform conversions in both arms are not comparable when the control isn't served (no clicks → no attributed conversions). Always measure the outcome independently of the ads (backend, GA4 by geo/segment).
9. **Multiple testing / peeking**: analysing many KPIs or stopping when significant. Pre-register one primary KPI and the end date.
10. **External validity**: results from one season/budget level don't automatically transfer. Re-test periodically.

## Interpreting results
- Significant and plausible → act per pre-registered rules.
- Not significant, MDE small relative to expected effect → strong evidence the channel is weakly incremental; consider cutting or restructuring.
- Not significant, MDE large → inconclusive; say so; propose a stronger design. Report what values the interval rules out.
- Significant but implausibly large → check for data errors, shocks, leakage in the other direction, or an unbalanced design before reporting.
- Report the full interval in money terms: "between $0.60 and $2.90 of incremental revenue per $1 spent".
