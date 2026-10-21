# Incrementality test: pre-registration and results

## Part A: Pre-registration (sign off before launch)

**Client / account:**
**Prepared by / date:**

**Decision this test informs:** (e.g. "Whether to cut retargeting from $20k to $8k/month")

**Hypothesis:** (e.g. "Retargeting drives incremental revenue with iROAS ≥ 2.0")

**Channel / campaigns in scope:**

**Design:** holdout / go-dark / heavy-up / multi-cell; geo or user split
- Treatment group: (geos or % of users, how assigned)
- Control group:
- Exclusions applied in campaigns:
- Leakage controls (PMax, location presence setting, budget caps):

**Dates:** pre-period ____ to ____; test ____ to ____; cool-down ____ to ____

**Primary KPI (one):** (e.g. backend revenue per geo per day)
**Secondary KPIs:** (e.g. orders, new customers, platform conversions)

**Analysis method:** (e.g. synthetic control + TBR via geo_test.py, placebo inference; or ITT holdout via holdout_test.py)

**Power:** MDE = __% at 80% power over __ days; expected effect = __% (reasoning)

**Economics:** AOV $__; gross margin __%; break-even iROAS = __

**Decision rules:**
- If iROAS < __ (or interval entirely below break-even): __
- If iROAS between __ and __: __
- If iROAS > __: __
- If inconclusive: __

**Guardrails / early stop:** (e.g. stop if treatment revenue falls >__% vs forecast for 7 consecutive days)

**Known events during test:**

**Sign-off:** client ____ agency ____

## Part B: Results report

### Headline (3–4 sentences, plain language)
"For every $1 spent on ___, about $__ of sales would not have happened otherwise (likely range $__–$__). After product costs, that's $__ of profit per $1. We recommend ___, which we estimate adds $__ profit per year."

### The numbers
| Metric | Estimate | Interval (90%) |
|---|---|---|
| Incremental revenue | | |
| Incremental orders | | |
| Lift % vs counterfactual | | |
| Spend change | | n/a |
| iROAS | | |
| iPOAS (profit ÷ spend) | | |
| Platform-reported ROAS (same period/scope) | | n/a |
| Incrementality factor | | |
| Cost per incremental order | | |

### Decision
Apply pre-registered rules. State the recommended budget change and the expected annualised profit impact, with the range.

### Chart
Actual vs counterfactual (treatment group), and cumulative incremental revenue with interval.

### How we tested (short)
Design, dates, groups, KPI, method, and fit quality (pre-period MAPE / R²), placebo p-value, agreement between methods.

### Caveats
Leakage, events during test, how lag/cool-down was handled, what the test cannot tell us (e.g. average vs marginal return; one season).

### Next test
(e.g. retargeting lookback window 7 vs 30 days; heavy-up to find the marginal return)
