---
name: google-ads-daily-digest
description: Build and email a professional Google Ads daily digest across client accounts (KPIs vs last week, budget pacing, charts, alerts, recommendations) from Windsor.ai data. Use for "daily Google Ads digest", "how did the ads do yesterday", or a scheduled morning report.
---

# Google Ads daily digest

A morning email covering every active Google Ads account: what happened, what changed, what needs doing. It reads like an analyst wrote it: numbers first, then a short judgement and specific recommendations. One account or many.

## What it covers (per account)
- **Status light**: green (on track), amber (watch), red (action needed), from rule-based alerts.
- **KPI tiles, last 7 days vs the 7 before**: spend, conversions/leads, cost per lead or ROAS, revenue or conversion rate. Mixed accounts (ecommerce + lead campaigns, e.g. a shop plus a booking campaign) show revenue/ROAS and leads/cost per lead separately, because lead campaigns usually count each lead as $1 and would otherwise pollute ROAS.
- **Yesterday line**: spend, clicks, conversions, revenue.
- **Budget pacing**: month to date and projected month-end spend vs budget.
- **Charts** (email-safe HTML, no images): daily spend, daily revenue and/or leads for 30 days, and weekly efficiency for the last 4 weeks.
- **Recommendations**: 2–4 specific actions written by you (Claude) from the numbers.
- **Campaign table**: 7-day spend, conversions, CPA/ROAS with change, search impression share.

Why 7-day windows: yesterday's conversions keep arriving for days (conversion lag), so day-on-day swings mislead. Yesterday is shown for context; judgements use 7-day comparisons and the 4-week trend.

## Data
Windsor.ai connector `google_ads` (accounts are listed by `get_connectors`). Pull 60 days, per day per campaign:
```
get_data(connector="google_ads", date_preset="last_60d", fields=[
  "date","account_name","account_id","account_currency_code","campaign","campaign_type","campaign_status",
  "spend","clicks","impressions","conversions","conversion_value","search_impression_share",
  "search_budget_lost_impression_share","search_rank_lost_impression_share","budget_amount","bidding_strategy_type"])
```
The response is large and gets saved to a file automatically; use that file path as `--data` (or write the JSON to a file). Pass `accounts=[...]` to limit to some accounts. Accounts with no spend in 30 days are left out and noted in the footer.

Optional `accounts.json` (client names and targets are confidential: keep this file out of the public repo; the scheduled task prompt holds the live version):
```json
{"Client A": {"target_poas": 3, "margin": 0.45, "monthly_budget": 1900},
 "Client B": {"mode": "leads", "target_cpa": 100},
 "Client C": {"exclude": true}}
```
`mode` forces leads/ecommerce; otherwise it's detected per campaign (value per conversion under ~1.5 = leads). `target_poas` (profit on ad spend) needs `margin`; it is converted to a ROAS target (target_poas ÷ margin). For mixed accounts, `target_cpa` applies to the lead campaigns and `target_roas`/`target_poas` to the ecommerce ones. `monthly_budget` overrides "daily budgets × days in month".

## Steps
1. **Get the script**: `scripts/digest.py` from https://github.com/kareenabowring-art/claude-skills/tree/main/google-ads-daily-digest (`git clone --depth 1 https://github.com/kareenabowring-art/claude-skills`). Needs pandas and matplotlib.
2. **Pull data** (above). Check the latest date in the data covers the report date (yesterday in the accounts' time zone, default Australia/Sydney); if not, say the data hasn't refreshed and use the latest full day.
3. **Analyze**: `python3 digest.py analyze --data ads.json [--config accounts.json] [--tz Australia/Sydney] --out out/`. It prints a summary and flags, and writes `out/metrics.json`.
4. **Investigate before writing.** For each red or amber flag, look deeper where it changes the advice:
   - Revenue or conversions dropped to near zero for days → likely tracking, stock, site or feed issue. Check the daily series in metrics.json and, if useful, pull `conversion_action_name` by date to see which conversion stopped.
   - Lost impression share to budget with good efficiency → budget increase candidate; size it (e.g. +20–30%) and note the expected effect.
   - Lost impression share to rank → bids, ad relevance, landing page; suggest checking search terms.
   - Big spend jump → check bidding strategy changes or new campaigns.
   Don't invent causes. Say "check X" when the data can't tell.
5. **Write recommendations** to `recs.json`:
   ```json
   {"overview": "2–3 plain sentences: the headline across accounts.",
    "accounts": {"Account name": ["Specific action with the number behind it.", "..."]}}
   ```
   Rules: 2–4 per account, most important first; each names the campaign, the number, and the action (e.g. "Raise the [campaign] budget from $20 to $30 a day: leads cost $11.79 this week but the ads stopped on half of searches"). Use the 4-week trend to separate a blip from a slide. Mention sample size when conversions are low (<10). Plain words, Australian English, no jargon, no hype. If an account is fine, one line saying so is enough.
6. **Render**: `python3 digest.py render --out out/ --recs recs.json [--brand "99 Degrees Tech"]`. Produces `out/digest.html` (email), `out/preview.html` and `out/chart_*.png` (image charts for a browser or report), and `out/email.json` (subject line).
7. **Check** the email before sending: numbers in the recommendations match the tiles; no account missing; status lights make sense. Optionally screenshot `digest.html` with Playwright to eyeball it.
8. **Send** with Gmail `send_message`: `htmlBody` = the full contents of `out/digest.html`, `subject` from `email.json`, `to` = Kareena's work address (kareena.bowring@99degrees.tech) unless told otherwise. Don't use Outlook for this email: its connector strips the styling the charts rely on. Never send a digest to a client unless Kareena has asked for that specific client email.
   If the user wants a document instead, or a shareable page, publish `preview.html` with the PNG charts as an artifact.

## Scheduling
When asked for a daily email, create a scheduled task (the session's scheduling tools, not local cron) that runs these steps every morning, e.g. 7:30am Sydney time on weekdays, with the prompt: "Run the google-ads-daily-digest skill for all active Google Ads accounts and email it to kareena.bowring@99degrees.tech." Mondays can cover the weekend (the 7-day windows already do).

## Alert rules (built into the script)
- Red: no spend yesterday after spending in the last 7 days; no conversions for 3 days when the account usually gets 1.5+/day (tracking check); 7 days of spend with no leads; ecommerce ROAS below 1 (or below break-even when margin is set).
- Amber: cost per lead up >30% week on week; ROAS down >25%; worse than target; month pacing >110% or <80% of budget; campaign losing ≥20% of search impressions to budget while efficient.
- Info: losing ≥50% of impressions to rank; campaign spend ±50% week on week; a day's spend >1.6× daily budget.
