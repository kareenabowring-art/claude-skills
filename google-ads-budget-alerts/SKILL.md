---
name: google-ads-budget-alerts
description: Same-day Google Ads alerts from hourly Windsor.ai data. Catches budgets running out early, overspend, stopped campaigns or accounts, cost-per-click spikes and missing conversions, and emails only when something new needs action. Use for "budget alerts", "check the ads now", or scheduled intraday checks.
---

# Google Ads same-day budget alerts

Runs several times a day. Compares each campaign's spend so far today with its own usual hourly pattern (last 28 days) and its daily budget, and sends a short email only when something new needs attention. Quiet runs send nothing.

## Alerts
| Alert | Level | Fires when |
|---|---|---|
| Account stopped | red | Whole account has spent $0 by 10am+ when it usually spends $10+ by then (billing, suspension, everything paused). Replaces the per-campaign "stopped" alerts. |
| Campaign stopped | red | No impressions or spend by 10am+ when it usually spends $8+ (or 25% of its day) by then. |
| Near the 2x cap | red | Spent ≥1.8× the daily budget today (Google can spend up to 2× on one day). |
| Overspend pace | amber | From midday, with ≥75% of budget spent and ≥40% of the usual day elapsed, on track for ≥1.5× budget. |
| Budget used up early | amber | 95% of the daily budget gone by 5pm (`--capped-before 16`). Includes the last 7 days' cost per lead or ROAS, and how often it has happened in the last 28 days. Judged by the clock, because a campaign that is always capped has an "early-ending" pattern that looks normal. |
| Underspend | amber | Spent under 25% of what it usually has by now (disapprovals, lowered budget, policy limits). |
| No conversions | amber | From midday, 0 conversions from 10+ clicks when it usually has 3+ by now (tag or checkout check; conversions can lag). |
| Cost-per-click spike | amber | Today's CPC ≥2× the 14-day average on 8+ clicks. |
Paused or removed campaigns are skipped.

## Steps
1. **Script**: `scripts/alerts.py` from https://github.com/kareenabowring-art/claude-skills/tree/main/google-ads-budget-alerts (`git clone --depth 1 https://github.com/kareenabowring-art/claude-skills`). Needs pandas and numpy.
2. **Pull hourly data** (Windsor.ai `google_ads`, last 28 days including today):
   ```
   get_data(connector="google_ads", date_preset="last_28dT", fields=["date","hour","account_name","account_currency_code",
     "campaign","campaign_status","spend","clicks","impressions","conversions","conversion_value","budget_amount"])
   ```
   The result is large and is saved to a file automatically; use that path as `--data`. Don't pass `force_refresh` (not on the current Windsor plan); cached data is usually only about an hour behind. Hours are in the account's time zone.
3. **Find alerts already sent today** so they aren't repeated: Gmail `search_threads` with `in:sent subject:"Google Ads alert" newer_than:1d`, open today's messages with `get_thread`, and copy the "Alert IDs:" line from each footer (comma-separated `account|campaign|type@spend` keys). Only count emails sent today in Sydney time.
4. **Run**: `python3 alerts.py --data hourly.json --sent-keys "<ids>" [--config accounts.json] [--tz Australia/Sydney] --out out/`. It prints every campaign's spend vs usual vs budget and the alerts, and writes `out/alerts.json`. If there's something new it also writes `out/alert_email.html` and `out/alert_email.json` (subject and keys). A repeated red alert is sent again only if spend has grown more than 25% since.
5. **Sanity check** before sending: if `alerts.json` has a `stale` note (latest data 3+ hours old), add one line about it and don't send "stopped" or "underspend" alerts, which may just be missing data. If an alert looks like a data glitch (e.g. spend with zero clicks), say so.
6. **Send** only if `send` is true: Gmail `send_message`, `to` kareena.bowring@99degrees.tech (or whoever the user named), `subject` from `alert_email.json`, `htmlBody` = contents of `alert_email.html`. Use Gmail, not Outlook (Outlook's connector strips the styling). If nothing new: send nothing, and just report "no new alerts" in the run.
7. **Never change the ads.** Alerts suggest actions; budgets and pauses are changed by Kareena, or by Claude only on her explicit instruction (Windsor.ai has Google Ads write actions; confirm each change first).

## Optional config (`accounts.json`)
```json
{"Client C": {"exclude": true},
 "Client A": {"daily_budget_override": {"Campaign name": 45}}}
```

## Scheduling
Create a scheduled task (the session's scheduling tools, not local cron) in Sydney time, e.g. `CRON_TZ=Australia/Sydney 7 10,13,16,19 * * *` (10am, 1pm, 4pm and 7pm daily; ads run on weekends too), with the prompt: "Run the google-ads-budget-alerts skill for all Google Ads accounts and email any new alerts to kareena.bowring@99degrees.tech. Send nothing if there are no new alerts." Fewer runs means slower alerts; more runs means more Windsor pulls.

## Relationship to the daily digest
The digest (google-ads-daily-digest) covers yesterday and weekly trends every morning. These alerts cover today. A campaign that keeps running out of budget will show up in both: in the alerts as "today", in the digest as lost impression share with a budget recommendation.
