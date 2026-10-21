#!/usr/bin/env python3
"""Same-day Google Ads budget and delivery alerts from Windsor.ai hourly data.

  python3 alerts.py --data hourly.json [--config accounts.json] [--tz Australia/Sydney] [--now "2026-10-21 14:30"]
                    [--sent-keys "acct|camp|type,..."] --out out/

--data: Windsor get_data rows with date, hour, account_name, campaign, spend, clicks, impressions, conversions,
        conversion_value, budget_amount (optional: account_currency_code, campaign_status). Pull the last 28 days
        INCLUDING today (date_preset "last_28dT"). Hours are in the account's time zone.
--config: optional {"Account": {"exclude": true, "daily_budget_override": {...}, "quiet_hours": [22, 7]}}
--sent-keys: alert keys already emailed today (from the footer of earlier alert emails); repeats are suppressed
             unless the alert got worse (level rises, or spend has grown >25% since).
Outputs out/alerts.json (all checks, including OK ones) and, only if there is something new to report,
out/alert_email.html + out/alert_email.json (subject). Exit code 0 always; read alerts.json "send" field.
"""
import argparse
import datetime as dt
import html
import json
import os
import sys

import numpy as np
import pandas as pd

COL = {"ink": "#1f2933", "muted": "#616e7c", "line": "#e4e7eb", "bg": "#f5f7fa", "red": "#c62828",
       "amber": "#b26a00", "blue": "#1d3557", "good": "#2e7d32"}


def load(path):
    with open(path) as f:
        d = json.load(f)
    rows = d.get("data", d) if isinstance(d, dict) else d
    df = pd.DataFrame(rows)
    need = ["date", "hour", "account_name", "campaign", "spend", "clicks", "impressions", "conversions"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        sys.exit(f"Missing columns: {miss} (pull hourly data with the 'hour' field)")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").astype(int)
    for c in ("spend", "clicks", "impressions", "conversions", "conversion_value", "budget_amount"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0.0
    for c in ("account_currency_code", "campaign_status"):
        if c not in df.columns:
            df[c] = ""
    return df


def money(v):
    return f"${v:,.0f}" if abs(v) >= 100 else f"${v:,.2f}"


def hour_label(h):
    h = int(h) % 24
    return f"{(h % 12) or 12}{'am' if h < 12 else 'pm'}"


def campaign_checks(today, hist, now_h, budget, status, a_cutoff=16):
    """Return metrics + list of alerts for one campaign. today: rows for today; hist: previous full days."""
    A = []
    spend_t = float(today["spend"].sum())
    clicks_t = float(today["clicks"].sum())
    impr_t = float(today["impressions"].sum())
    conv_t = float(today["conversions"].sum())
    # history: daily totals and cumulative share of spend by end of each hour
    days = sorted(hist["date"].unique())
    daily = hist.groupby("date")[["spend", "clicks", "conversions", "impressions"]].sum()
    recent = daily.tail(14)
    typ_spend = float(recent["spend"].median()) if len(recent) else 0.0
    typ_conv = float(recent["conversions"].median()) if len(recent) else 0.0
    cpc_hist = float(recent["spend"].sum() / recent["clicks"].sum()) if recent["clicks"].sum() else None
    by_h = hist.pivot_table(index="date", columns="hour", values="spend", aggfunc="sum").reindex(columns=range(24)).fillna(0)
    tot = by_h.sum(axis=1)
    by_h = by_h[tot > 0]
    share = (by_h.cumsum(axis=1).div(by_h.sum(axis=1), axis=0)).median() if len(by_h) else pd.Series(
        np.linspace(1 / 24, 1, 24), index=range(24))
    conv_h = hist.pivot_table(index="date", columns="hour", values="conversions", aggfunc="sum").reindex(columns=range(24)).fillna(0)
    ctot = conv_h.sum(axis=1)
    conv_h = conv_h[ctot > 0]
    cshare = (conv_h.cumsum(axis=1).div(conv_h.sum(axis=1), axis=0)).median() if len(conv_h) >= 5 else share
    sh = float(share.get(now_h, 1.0))
    expected = typ_spend * sh
    projected = spend_t / sh if sh >= 0.25 else None
    # how often the budget ran out in history, and usual last spending hour
    exhaust_hours, last_hours = [], []
    if budget:
        for d_, g in hist.groupby("date"):
            g = g.sort_values("hour")
            cs = g["spend"].cumsum()
            hit = g["hour"][cs >= 0.95 * budget]
            if len(hit):
                exhaust_hours.append(int(hit.iloc[0]))
            sp = g["hour"][g["spend"] > 0]
            if len(sp):
                last_hours.append(int(sp.max()))
    n_days = max(len(days), 1)
    m = {"spend_today": spend_t, "clicks_today": clicks_t, "impressions_today": impr_t, "conversions_today": conv_t,
         "typical_daily_spend": typ_spend, "typical_share_by_now": sh, "expected_spend_by_now": expected,
         "projected_spend": projected, "daily_budget": budget, "cpc_today": spend_t / clicks_t if clicks_t else None,
         "cpc_typical": cpc_hist, "budget_ran_out_days": len(exhaust_hours), "history_days": n_days,
         "usual_runout_hour": int(np.median(exhaust_hours)) if exhaust_hours else None,
         "usual_last_spend_hour": int(np.median(last_hours)) if last_hours else None}

    def add(level, kind, msg, action):
        A.append({"level": level, "type": kind, "message": msg, "action": action})

    if status and status.upper() not in ("ENABLED", "", "NAN"):
        return m, A  # paused/removed campaigns: no delivery alerts
    # 1. near the 2x daily cap / overspend pace
    if budget:
        if spend_t >= 1.8 * budget:
            add("red", "overspend", f"Spent {money(spend_t)} today on a {money(budget)} daily budget (Google's cap is 2x on a single day).",
                "Check for a budget or bid change, or a surge in expensive clicks. Pause or lower the budget if this wasn't intended.")
        elif projected and projected >= 1.5 * budget and spend_t >= 0.75 * budget and 12 <= now_h < 20 and sh >= 0.4:
            add("amber", "overspend_pace", f"On pace to spend about {money(projected)} today vs a {money(budget)} daily budget "
                f"({money(spend_t)} so far by {hour_label(now_h + 1)}).",
                "Fine if it averages out over the month (monthly cap is ~30.4x daily); otherwise check recent bid or budget changes.")
        # 2. budget exhausted early (judged by the clock, not the learned curve: a campaign that is
        #    always capped has a "normal" curve that already ends early)
        tt = today.sort_values("hour")
        hit = tt["hour"][tt["spend"].cumsum() >= 0.95 * budget]
        overspending = any(x["type"] in ("overspend", "overspend_pace") for x in A)
        if len(hit) and int(hit.iloc[0]) <= a_cutoff and not overspending:
            hit_h = int(hit.iloc[0])
            last_sp = int(tt["hour"][tt["spend"] > 0].max())
            often = (f" It has run out early on {len(exhaust_hours)} of the last {n_days} days"
                     + (f", usually by about {hour_label(int(np.median(exhaust_hours)) + 1)}." if exhaust_hours else ".")
                     if len(exhaust_hours) >= 3 else "")
            quiet = f" No spend since the {hour_label(last_sp)} hour." if now_h - last_sp >= 2 else ""
            w7 = hist[hist["date"].isin(days[-7:])] if days else hist
            sp7, cv7, val7 = float(w7["spend"].sum()), float(w7["conversions"].sum()), float(w7["conversion_value"].sum())
            eff = ""
            if cv7 > 0 and val7 / cv7 < 1.5:
                eff = f" Over the last 7 days it got {cv7:.0f} leads at {money(sp7 / cv7)} each."
            elif sp7 > 0 and val7 > 0:
                eff = f" Over the last 7 days it returned {val7 / sp7:.2f}x its spend ({money(val7)} from {money(sp7)})."
            elif sp7 > 0:
                eff = f" It recorded no conversions in the last 7 days ({money(sp7)} spent)."
            quiet += eff
            add("amber", "budget_capped", f"Daily budget used up by {hour_label(hit_h + 1)}: {money(spend_t)} spent on a "
                f"{money(budget)} budget, so ads are mostly off for the rest of the day.{quiet}{often}",
                "If cost per conversion is healthy, raise the daily budget; otherwise tighten keywords, locations or the ad "
                "schedule so the budget covers your best hours.")
    # 3. stopped / under-delivering
    if now_h >= 10 and expected >= max(8.0, 0.25 * typ_spend) and typ_spend > 0:
        if spend_t == 0 and impr_t == 0:
            add("red", "stopped", f"No impressions or spend today by {hour_label(now_h + 1)}; it usually spends about "
                f"{money(expected)} by now.", "Check campaign status, ad disapprovals, billing/payment and the account's notifications.")
        elif spend_t < 0.25 * expected:
            add("amber", "underspend", f"Only {money(spend_t)} spent by {hour_label(now_h + 1)} vs about {money(expected)} usually.",
                "Check for disapproved ads, a lowered budget or bid target, limited by policy, or a big drop in searches.")
    # 4. conversions missing (possible tracking break)
    exp_conv = typ_conv * float(cshare.get(now_h, sh))
    if now_h >= 12 and exp_conv >= 3 and conv_t == 0 and clicks_t >= 10:
        add("amber", "no_conversions", f"No conversions recorded today by {hour_label(now_h + 1)} from {clicks_t:.0f} clicks; "
            f"usually about {exp_conv:.0f} by now.",
            "Conversions can lag, but check the conversion tag fires (test a purchase/form) and the site checkout works.")
    # 5. CPC spike
    if cpc_hist and clicks_t >= 8 and spend_t / clicks_t >= 2 * cpc_hist:
        add("amber", "cpc_spike", f"Average cost per click today is {money(spend_t / clicks_t)} vs {money(cpc_hist)} usually.",
            "Check auction insights for a new competitor, recent bid strategy changes, or broad-match terms matching expensive searches.")
    return m, A


def run(a):
    df = load(a.data)
    cfg = json.load(open(a.config)) if a.config else {}
    try:
        from zoneinfo import ZoneInfo
        now = dt.datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else dt.datetime.now(ZoneInfo(a.tz)).replace(tzinfo=None)
    except Exception:
        now = dt.datetime.now()
    today = now.date()
    sent = set(k.strip() for k in (a.sent_keys or "").split(",") if k.strip())
    sent_spend = {}
    for k in list(sent):  # keys may carry spend: acct|camp|type@123.45
        if "@" in k:
            base, sp = k.rsplit("@", 1)
            sent.discard(k)
            sent.add(base)
            try:
                sent_spend[base] = float(sp)
            except ValueError:
                pass
    T = df[(df["date"] == today) & (df["hour"] <= now.hour)]
    H = df[(df["date"] < today) & (df["date"] >= today - dt.timedelta(days=28))]
    out = {"now": now.strftime("%Y-%m-%d %H:%M"), "today": str(today), "accounts": [], "send": False}
    if T.empty:
        out["note"] = "No rows for today yet (data not refreshed, or nothing has run today)."
    data_hour = int(T["hour"].max()) if len(T) else None
    out["data_through_hour"] = data_hour
    if data_hour is not None and now.hour - data_hour >= 3:
        out["stale"] = f"Latest data is for the {hour_label(data_hour)} hour; it's now {now.strftime('%-I:%M%p').lower()}."
    new_alerts = []
    for acct in sorted(set(df["account_name"])):
        c = cfg.get(acct, {})
        if c.get("exclude"):
            continue
        hA, tA = H[H["account_name"] == acct], T[T["account_name"] == acct]
        if hA["spend"].sum() == 0 and tA["spend"].sum() == 0:
            continue
        now_h = int(tA["hour"].max()) if len(tA) else (data_hour if data_hour is not None else now.hour - 1)
        # account quiet hours (e.g. don't alert overnight)
        acc = {"account": acct, "currency": str(df[df["account_name"] == acct]["account_currency_code"].iloc[0]),
               "through_hour": now_h, "campaigns": []}
        for camp in sorted(set(df[df["account_name"] == acct]["campaign"])):
            hc, tc = hA[hA["campaign"] == camp], tA[tA["campaign"] == camp]
            if hc["spend"].sum() == 0 and tc["spend"].sum() == 0:
                continue
            allc = pd.concat([hc, tc])
            budget = float(allc.sort_values(["date", "hour"])["budget_amount"].iloc[-1]) if len(allc) else 0.0
            budget = c.get("daily_budget_override", {}).get(camp, budget)
            status = str(allc.sort_values(["date", "hour"])["campaign_status"].iloc[-1]) if len(allc) else ""
            m, al = campaign_checks(tc, hc, now_h, budget, status, a.capped_before)
            for x in al:
                key = f"{acct}|{camp}|{x['type']}"
                x["key"] = key
                x["spend_at_alert"] = round(m["spend_today"], 2)
                repeat = key in sent and not (key in sent_spend and m["spend_today"] > 1.25 * sent_spend[key] and x["level"] == "red")
                x["new"] = not repeat
                if x["new"]:
                    new_alerts.append((acct, camp, x))
            acc["campaigns"].append({"campaign": camp, "metrics": m, "alerts": al})
        # account-level: everything stopped
        if all(cc["metrics"]["spend_today"] == 0 for cc in acc["campaigns"]) and acc["campaigns"] and now_h >= 10:
            exp = sum(cc["metrics"]["expected_spend_by_now"] for cc in acc["campaigns"])
            if exp >= 10:
                x = {"level": "red", "type": "account_stopped", "key": f"{acct}|*|account_stopped",
                     "message": f"The whole account has spent nothing today by {hour_label(now_h + 1)} (usually ~{money(exp)} by now).",
                     "action": "Check billing/payment method, account suspension notices, and whether campaigns were paused.",
                     "spend_at_alert": 0}
                x["new"] = x["key"] not in sent
                acc["account_alerts"] = [x]
                # one account-level alert replaces the per-campaign "stopped" ones
                new_alerts[:] = [t for t in new_alerts if not (t[0] == acct and t[2]["type"] == "stopped")]
                for cc in acc["campaigns"]:
                    cc["alerts"] = [y for y in cc["alerts"] if y["type"] != "stopped"]
                if x["new"]:
                    new_alerts.append((acct, "", x))
        out["accounts"].append(acc)
    out["send"] = bool(new_alerts)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "alerts.json"), "w") as f:
        json.dump(out, f, indent=2, default=lambda o: None if o != o else o)
    print_summary(out, new_alerts)
    if new_alerts:
        render(out, new_alerts, a)


def print_summary(out, new_alerts):
    print(f"Now {out['now']}; data through the {hour_label(out['data_through_hour'])} hour" if out.get("data_through_hour") is not None
          else f"Now {out['now']}; no data for today")
    if out.get("stale"):
        print("STALE:", out["stale"])
    for A in out["accounts"]:
        print(f"\n{A['account']} (through {hour_label(A['through_hour'])} hour)")
        for C in A["campaigns"]:
            m = C["metrics"]
            proj = f", projected {m['projected_spend']:.0f}" if m["projected_spend"] else ""
            print(f"  {C['campaign']}: spent {m['spend_today']:.2f} of {m['daily_budget']:.0f} budget; usually "
                  f"{m['expected_spend_by_now']:.2f} by now{proj}; ran out of budget on {m['budget_ran_out_days']}/{m['history_days']} days")
            for x in C["alerts"]:
                print(f"    [{x['level']}{'' if x['new'] else ', already sent'}] {x['message']}")
        for x in A.get("account_alerts", []):
            print(f"  [{x['level']}] {x['message']}")
    print(f"\nSend email: {out['send']} ({len(new_alerts)} new alert(s))")


def render(out, new_alerts, a):
    E = html.escape
    reds = sum(1 for _, _, x in new_alerts if x["level"] == "red")
    n = len(new_alerts)
    when = dt.datetime.strptime(out["now"], "%Y-%m-%d %H:%M")
    rows = ""
    for acct, camp, x in sorted(new_alerts, key=lambda t: (t[2]["level"] != "red", t[0], t[1])):
        col = COL["red"] if x["level"] == "red" else COL["amber"]
        rows += (f'<tr><td style="padding:14px 16px;border-left:4px solid {col};background:#ffffff;border-bottom:1px solid {COL["line"]}">'
                 f'<div style="font-size:11px;color:{col};font-weight:700;text-transform:uppercase;letter-spacing:.04em">'
                 f'{"Action needed" if x["level"] == "red" else "Check today"}</div>'
                 f'<div style="font-size:14px;font-weight:700;color:{COL["ink"]};margin:3px 0">{E(acct)}'
                 f'{" · " + E(camp) if camp else ""}</div>'
                 f'<div style="font-size:13px;color:{COL["ink"]};line-height:1.5">{E(x["message"])}</div>'
                 f'<div style="font-size:12px;color:{COL["muted"]};line-height:1.5;margin-top:4px"><b>What to do:</b> {E(x["action"])}</div>'
                 f'</td></tr><tr><td style="height:8px;font-size:0;line-height:0">&nbsp;</td></tr>')
    keys = ",".join(f'{x["key"]}@{x["spend_at_alert"]}' for _, _, x in new_alerts)
    stale = f'<div style="font-size:12px;color:{COL["amber"]};margin-top:6px">{E(out["stale"])}</div>' if out.get("stale") else ""
    body = (f'<!doctype html><html><body style="margin:0;padding:0;background:{COL["bg"]};font-family:-apple-system,Segoe UI,'
            f'Roboto,Helvetica,Arial,sans-serif"><table width="100%" cellpadding="0" cellspacing="0" style="background:{COL["bg"]}">'
            f'<tr><td align="center" style="padding:16px 10px"><table width="600" cellpadding="0" cellspacing="0" '
            f'style="width:100%;max-width:600px"><tr><td style="background:{COL["blue"]};padding:16px 18px;border-radius:8px 8px 0 0">'
            f'<div style="font-size:11px;color:#c9d6ea;text-transform:uppercase;letter-spacing:.06em">{E(a.brand)} · Google Ads</div>'
            f'<div style="font-size:18px;font-weight:700;color:#ffffff;margin-top:3px">Same-day alert: {n} issue{"s" if n > 1 else ""}</div>'
            f'<div style="font-size:12px;color:#c9d6ea;margin-top:3px">{when.strftime("%A %-d %B, %-I:%M%p").replace("AM", "am").replace("PM", "pm")} '
            f'· data through the {hour_label(out["data_through_hour"])} hour</div>{stale}</td></tr>'
            f'<tr><td style="padding:10px 0 0">'
            f'<table width="100%" cellpadding="0" cellspacing="0">{rows}</table></td></tr>'
            f'<tr><td style="padding:8px 4px;font-size:11px;color:{COL["muted"]};line-height:1.5">Hourly spend compared with each '
            f'campaign\'s usual pattern over the last 28 days. Conversions can take hours or days to record. '
            f'You only get an email when something new needs attention.<br><span style="color:#9aa5b1;font-size:9px">Alert IDs: {E(keys)}</span>'
            f'</td></tr></table></td></tr></table></body></html>')
    import re
    body = re.sub(r">\s+<", "><", body)
    with open(os.path.join(a.out, "alert_email.html"), "w") as f:
        f.write(body)
    subj = (f"{'🔴' if reds else '🟠'} Google Ads alert · {n} issue{'s' if n > 1 else ''} · "
            f"{when.strftime('%-I:%M%p').lower()} {when.strftime('%a %-d %b')}")
    with open(os.path.join(a.out, "alert_email.json"), "w") as f:
        json.dump({"subject": subj, "html_file": os.path.join(a.out, "alert_email.html"), "keys": keys}, f, indent=2)
    print(f"Saved {a.out}/alert_email.html  Subject: {subj}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True)
    p.add_argument("--config")
    p.add_argument("--tz", default="Australia/Sydney")
    p.add_argument("--now", help='Local time "YYYY-MM-DD HH:MM" (default: now in --tz)')
    p.add_argument("--sent-keys", default="", help="Alert IDs already emailed today (from earlier alert emails)")
    p.add_argument("--brand", default="99 Degrees Tech")
    p.add_argument("--capped-before", type=int, default=16,
                   help="Alert when the budget runs out in or before this hour (default 16 = by 5pm)")
    p.add_argument("--out", default="alerts_out")
    run(p.parse_args())


if __name__ == "__main__":
    main()
