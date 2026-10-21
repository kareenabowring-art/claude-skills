# Retargeting incrementality

Retargeting targets people who already visited, added to cart or bought, so many would convert anyway. Platform ROAS for retargeting is routinely several times its incremental ROAS. That is the core reason to test it, and a strong selling point for an agency that can prove its retargeting beats the norm.

## Why platform ROAS overstates retargeting
- **Selection**: the audience is pre-qualified; high conversion rates are a property of the audience, not the ad.
- **View-through credit**: display/YouTube impressions on a returning visitor claim conversions that came via direct, email or organic.
- **Last-touch timing**: the ad is served moments before a purchase the user was already making.
- **Overlap**: the same users are also in email flows, SMS, organic, brand search. Each channel claims the same sale.

## Unit of analysis and groups
- Randomise **users** (or households/customer IDs), not impressions or days.
- Split must happen **before** ad delivery decisions, and the holdout must be excluded from every campaign that could serve them retargeting.
- Use a stable hash of a persistent ID (hashed email for customer-match lists, GA4 user ID / client ID for site audiences). Example: holdout = users where `int(sha256(id)[:8], 16) % 100 < 15` (15% holdout).
- Google Ads can't do this split itself. For Customer Match, upload the two groups as separate lists. For site audiences, set the bucket as a user-scoped custom dimension/user property on the site (via GTM) and build two GA4 audiences from it, then target one and exclude the other.
- Keep group membership fixed for the whole test; new users entering the audience are assigned by the same hash.

## Intent-to-treat (ITT) and dilution
Not everyone in the test group actually sees an ad (budget, frequency, they never come back online). Comparing all test users vs all control users is **ITT**: unbiased but diluted.
- ITT lift (absolute) = CR_test − CR_control (or revenue per user).
- Exposure rate e = share of test group that was actually served ≥1 impression (from the platform's reach for the list, ÷ test group size).
- **Treatment-on-treated (TOT) effect per exposed user ≈ ITT absolute effect ÷ e** (the Bloom / Wald estimator; assumes ads have no effect on unexposed users and that the would-be-exposed share in control equals e).
- Caveats: the relative lift among exposed users (TOT ÷ control rate) is biased **upward**, because exposed users have a higher baseline than the control average. Platform "reach" counts devices/cookies, so it overstates e and biases the per-exposed effect **downward**. Prefer user-level exposure flags; present the TOT figure as approximate.
- Total incremental conversions = ITT absolute effect × test group size (this is the same with or without the dilution correction; dilution correction changes the per-exposed-user rate and the relative lift among the exposed, not the total incremental count).
- **Never** compute lift as exposed-test vs all-control or exposed vs unexposed. That is selection bias and inflates lift.

## Ghost ads, PSA and ghost bids
- **PSA / placebo**: control sees a charity or unrelated ad. Identifies would-be-exposed control users, so you can compare exposed vs would-be-exposed with less noise. Costs money for the placebo impressions, and delivery optimisation may treat the placebo ad differently from the real ad, which biases who gets "exposed". Mostly a legacy method.
- **Ghost ads**: the platform logs when it *would* have shown your ad to a control user and shows another advertiser's ad instead. Low noise, no cost. Only platforms can do this; Google's Conversion Lift uses this kind of approach internally.
- **Ghost bids**: DSP version of ghost ads for programmatic retargeting; records control users you would have bid on.
- For an agency on Google Ads: use Conversion Lift where eligible (platform handles ghost-style logging), otherwise DIY ITT holdout with the dilution correction above.

## Retargeting tests worth running (in order)
1. **On vs off (holdout)**: is retargeting incremental at all? 10–20% holdout for 4–6 weeks plus 1–2 weeks cool-down.
2. **Membership duration / lookback window**: 7 vs 30 vs 90 days. Short windows often keep most of the incremental value at a fraction of the cost.
3. **Frequency**: capped vs uncapped. Incrementality usually saturates quickly.
4. **Audience exclusions**: exclude recent purchasers and people currently in email/SMS abandon flows; test whether sales drop.
5. **Creative**: dynamic product vs offer vs brand. Measure on incremental, not attributed, outcome.
Multi-cell designs (e.g. holdout / 7-day / 30-day) share one control and save time.

## PMax and remarketing leakage
PMax uses audience signals, not hard targeting, and finds returning visitors by itself. If you exclude a holdout segment from Display remarketing but PMax still reaches them, the holdout is contaminated. Options: run the test on all remarketing-capable campaigns including PMax with the customer-match exclusion where supported; use account-level customer exclusions where available; or switch to a geo test. Always report how leakage was handled and its likely direction (toward zero).

## Outcome measurement
- Primary: backend orders/revenue per user by group (Shopify customer ID or email matched to the hash), or GA4 conversions by user segment.
- Secondary: platform conversions (only meaningful in Conversion Lift, since DIY control users have no ad clicks).
- Watch for new-customer vs returning splits: retargeting is often more incremental for first-time purchasers (cart abandoners) than for repeat buyers.

## Interpreting typical results
Published and industry tests often show retargeting incrementality factors well below 1 (a large share of attributed conversions would have happened anyway), with wide variation by brand, audience freshness and frequency. Don't quote a "typical" number to clients as fact; test their account. Frame a low result as an opportunity: the same budget redeployed to prospecting or capped retargeting usually yields more incremental profit.
