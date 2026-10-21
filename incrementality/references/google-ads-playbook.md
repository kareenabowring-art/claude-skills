# Running incrementality tests in Google Ads (Australia)

Facts below were checked in October 2026. Google changes eligibility often; confirm in the account before promising a client a specific test.

## Google Ads Conversion Lift
- **User-based**: self-serve for Video, Demand Gen, Display, and (from 7 Oct 2026) Search and Performance Max. Reported minimums: ~1,000 observed conversions (excluding supplementary data) and a ≈$5,000 campaign budget; Google estimates required budget from historical conversions at setup and shows a feasibility rating. Run only at "High" feasibility; treat "Medium" with caution; never run at "Low".
- **Geography-based**: covers Search, Shopping, PMax, Display, Video, Demand Gen, App; supports online and offline conversions and cross-channel measurement; campaigns must target a single country; budgets tend to be higher than user-based; access via a Google account rep. Holdback and go-dark studies are in beta.
- **Bayesian methodology** (since May 2025): results use priors, report probability of lift and credible intervals; tests can conclude with less data, but results depend on the priors. Ask the rep what prior was used; report it.
- Location: Tools → Measurement → Conversion Lift (if the account is eligible; availability varies by account).
- Treat Google-run results as one input; corroborate with backend data where possible, since Google is grading its own ads.

## Campaign experiments are NOT incrementality tests
Google Ads "Experiments" (drafts, A/B bid strategy tests) split traffic between two versions of a campaign that both serve ads. They measure which version performs better on attributed metrics, not whether ads cause sales. Use them for optimisation, not for "is this channel incremental".

## DIY geo tests in Google Ads
1. **Pick geos**: Australia has 8 states/territories, too few. Use smaller units Google Ads can target:
   - Postcodes (targetable) grouped into clusters, or
   - ABS **SA4** regions (~90 nationally), built from postcodes; or Google's own sub-state regions/cities where available.
   Build the daily KPI per geo from Shopify/backend shipping postcode (best) or GA4 region/city (acceptable, less precise).
2. **Run `geo_test.py design`** on 6–12+ months of daily geo data to pick a balanced treatment group and estimate MDE.
3. **Implement**:
   - Holdout: add treatment geos as **excluded locations** to every campaign in scope.
   - Heavy-up: keep the original campaigns unchanged, and add a separate campaign targeting only the treatment geos that carries just the extra budget. (If you instead exclude treatment geos from the originals, the new campaign must carry base + extra budget.)
   - Set location options to **"Presence: people in or regularly in your included locations"** to reduce leakage; apply the same setting to all campaigns in scope.
   - Lower campaign budgets in proportion to the excluded share, so Smart Bidding doesn't reallocate the freed budget into control geos (which would inflate control and bias the result).
4. **Verify** on day 1–3: geo report (Reports → Predefined → Geographic / "Where your users were") shows near-zero spend in holdout geos.
5. **Cool-down**: keep exclusions for the test window only; analyse 7–14 days after for lagged effects.

## Brand search tests
- Question: how many brand-search sales would come through organic results anyway?
- Design: geo holdout pausing brand campaigns in treatment geos. PMax will pick up the brand traffic unless it's blocked too, and the test then only measures channel shifting. PMax brand exclusions apply to a whole campaign, not per geo, so split PMax into two geo-specific campaigns: one targeting the treatment geos with brand exclusions, one targeting the rest as usual.
- Measure: total backend revenue and total brand clicks (paid + organic from Search Console, if available by region), not paid brand conversions.
- Risk: competitors bidding on the brand. Check Auction Insights before; if competitors are present, expect higher incrementality, and monitor competitor impression share in the treatment geos during the test.

## Performance Max tests
- PMax mixes brand, remarketing and prospecting. Ask what the decision is:
  - "Is PMax incremental overall?" → geo holdout of PMax (or user-based Conversion Lift, self-serve since Oct 2026).
  - "Is PMax cannibalising brand/remarketing?" → 3-cell geo test: control (as-is) / PMax with brand exclusions / PMax off. Build it with geo-specific PMax campaigns (brand exclusions are campaign-level, not per geo): one campaign for control geos as-is, one for cell-2 geos with brand exclusions, and cell-3 geos excluded from PMax entirely. Splitting PMax resets learning, so set the campaigns up 2+ weeks before the test starts and keep that time in the pre-period. Analyse each cell against the control with `geo_test.py analyze` (one run per cell, other cell's geos excluded via `--exclude-geos`).
- Check the PMax channel/search terms insights and new-customer acquisition settings first; high brand-term share is a diagnostic red flag.

## Data pulls (Windsor.ai connector)
- Google Ads: `date`, `campaign`, `spend`, `clicks`, `impressions`, `conversions`, `conversion_value`, with geo breakdown (user location region/city/postcode where available) for test design and verification.
- Backend (Shopify connector or export): daily orders and revenue by shipping postcode/state, new vs returning flag.
- GA4: sessions and conversions by region/city as a cross-check.
Save pulls to CSV and run the scripts on files; don't paste large tables through the conversation.

## Australian calendar watch-list (avoid or balance)
Click Frenzy (Nov), Black Friday/Cyber Monday, Boxing Day sales, EOFY (June), Mother's/Father's Day, Valentine's, Easter, school holidays (differ by state), state public holidays (e.g. King's Birthday dates differ in WA and QLD; Melbourne Cup Day in VIC; show days), and major weather events. State-specific events hit some geos and not others: either avoid them or ensure treatment and control are balanced across states.
