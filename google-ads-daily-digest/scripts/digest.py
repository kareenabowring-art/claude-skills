#!/usr/bin/env python3
"""Google Ads daily digest: KPIs, alerts, charts and an email-ready HTML report from Windsor.ai data.

Step 1  analyze: compute metrics + rule-based flags  ->  out/metrics.json (read it, then write recommendations)
Step 2  render:  build charts + HTML email (with your recommendations) -> out/digest.html, out/chart_*.png, out/email.json

  python3 digest.py analyze --data ads.json [--config accounts.json] [--date 2026-10-20] [--tz Australia/Sydney] --out out/
  python3 digest.py render  --out out/ [--recs recs.json] [--title "Google Ads daily digest"] [--brand "99 Degrees Tech"]

--data: Windsor get_data output ({"data":[...]}) or a plain list of rows. Needs per-day, per-campaign rows with:
  date, account_name, campaign, campaign_type, spend, clicks, impressions, conversions, conversion_value
  optional: account_id, account_currency_code, campaign_status, budget_amount, search_impression_share,
            search_budget_lost_impression_share, search_rank_lost_impression_share, bidding_strategy_type
  Pull at least the last 35 days (60 is better).
--config (optional JSON) per account name: {"Acme": {"mode": "leads"|"ecommerce", "target_cpa": 80, "target_roas": 4,
  "monthly_budget": 2500, "margin": 0.4, "exclude": false}}. Without it, mode is auto-detected per campaign.
--recs (optional JSON): {"overview": "2-3 sentences", "accounts": {"Acme": ["rec 1", "rec 2"]}}
"""
import argparse
import calendar
import datetime as dt
import html
import json
import os
import sys

import pandas as pd

NUM = ["spend", "clicks", "impressions", "conversions", "conversion_value", "budget_amount",
       "search_impression_share", "search_budget_lost_impression_share", "search_rank_lost_impression_share"]
COL = {"ink": "#1f2933", "muted": "#616e7c", "line": "#e4e7eb", "bg": "#f5f7fa", "brand": "#1d3557",
       "good": "#2e7d32", "bad": "#c62828", "warn": "#b26a00", "accent": "#3a7bd5", "accent2": "#f4a261"}


# ------------------------------------------------------------------ load

def load(path):
    with open(path) as f:
        d = json.load(f)
    rows = d.get("data", d) if isinstance(d, dict) else d
    if not rows:
        sys.exit("No rows in data file.")
    df = pd.DataFrame(rows)
    need = ["date", "account_name", "campaign", "spend", "clicks", "impressions", "conversions", "conversion_value"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        sys.exit(f"Missing columns: {miss}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for c in NUM:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("campaign_type", "campaign_status", "account_currency_code", "bidding_strategy_type"):
        if c not in df.columns:
            df[c] = ""
    return df


def detect_mode(g):
    """'leads' if conversion value is absent or ~1 per conversion (lead counting), else 'ecommerce'."""
    conv, val = g["conversions"].sum(), g["conversion_value"].sum()
    if conv <= 0:
        return "leads" if val <= 0 else "ecommerce"
    return "leads" if val / conv < 1.5 else "ecommerce"


def agg(g):
    s = {k: float(g[k].sum()) for k in ("spend", "clicks", "impressions", "conversions", "conversion_value")}
    s["ctr"] = s["clicks"] / s["impressions"] if s["impressions"] else None
    s["cpc"] = s["spend"] / s["clicks"] if s["clicks"] else None
    s["cvr"] = s["conversions"] / s["clicks"] if s["clicks"] else None
    s["cpa"] = s["spend"] / s["conversions"] if s["conversions"] else None
    s["roas"] = s["conversion_value"] / s["spend"] if s["spend"] else None
    # impression-share metrics: impression-weighted mean over Search rows
    srch = g[g["campaign_type"].astype(str).str.upper().eq("SEARCH")] if "search_impression_share" in g else g.iloc[0:0]
    if len(srch) and srch["impressions"].sum() > 0:
        w = srch["impressions"]
        for k in ("search_impression_share", "search_budget_lost_impression_share", "search_rank_lost_impression_share"):
            if k in srch:
                s[k] = float((srch[k].fillna(0) * w).sum() / w.sum())
    return s


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a - b) / b


# ------------------------------------------------------------------ analyze

def analyze(a):
    df = load(a.data)
    cfg = json.load(open(a.config)) if a.config else {}
    if a.date:
        day = dt.date.fromisoformat(a.date)
    else:
        try:
            from zoneinfo import ZoneInfo
            today = dt.datetime.now(ZoneInfo(a.tz)).date()
        except Exception:
            today = dt.date.today()
        day = today - dt.timedelta(days=1)
    df = df[df["date"] <= day]
    if df.empty:
        sys.exit(f"No data on or before {day}.")
    if df["date"].max() < day:
        print(f"WARNING: latest data is {df['date'].max()}, report date {day}. Data may not be refreshed yet.")
    w_this = (day - dt.timedelta(days=6), day)
    w_prev = (day - dt.timedelta(days=13), day - dt.timedelta(days=7))
    d30 = (day - dt.timedelta(days=29), day)
    mstart = day.replace(day=1)
    dim = calendar.monthrange(day.year, day.month)[1]

    def between(g, w):
        return g[(g["date"] >= w[0]) & (g["date"] <= w[1])]

    out = {"report_date": day.isoformat(), "generated": dt.datetime.now().isoformat(timespec="minutes"),
           "windows": {"last7": [str(w_this[0]), str(w_this[1])], "prev7": [str(w_prev[0]), str(w_prev[1])]},
           "accounts": []}
    for acct, g in df.groupby("account_name"):
        c = dict(cfg.get(acct, {}))
        if c.get("exclude"):
            continue
        if c.get("target_poas") and c.get("margin") and not c.get("target_roas"):
            c["target_roas"] = c["target_poas"] / c["margin"]
        cur = (g["account_currency_code"].dropna().astype(str).replace("", pd.NA).dropna().iloc[0]
               if g["account_currency_code"].astype(str).str.len().gt(0).any() else "")
        g30 = between(g, d30)
        if g30["spend"].sum() == 0 and not c:
            out.setdefault("inactive", []).append(acct)
            continue
        camp_modes = {k: c.get("mode") or detect_mode(between(cg, d30)) for k, cg in g.groupby("campaign")}
        modes = set(camp_modes.values())
        acct_mode = c.get("mode") or (modes.pop() if len(modes) == 1 else "mixed")
        g = g.assign(_mode=g["campaign"].map(camp_modes))
        y = agg(g[g["date"] == day])
        l7, p7, m30 = agg(between(g, w_this)), agg(between(g, w_prev)), agg(g30)
        if acct_mode == "mixed":
            # leads and ecommerce reported separately so lead counts don't pollute revenue/ROAS
            for nm, w in (("yesterday", (day, day)), ("last7", w_this), ("prev7", w_prev), ("last30", d30)):
                tgt = {"yesterday": y, "last7": l7, "prev7": p7, "last30": m30}[nm]
                e, l = agg(between(g[g["_mode"] == "ecommerce"], w)), agg(between(g[g["_mode"] == "leads"], w))
                tgt["ecom"] = {k: e[k] for k in ("spend", "conversions", "conversion_value", "roas", "cpa")}
                tgt["leads"] = {k: l[k] for k in ("spend", "conversions", "cpa", "cvr")}
                tgt["conversion_value"] = e["conversion_value"]
                tgt["roas"] = e["roas"]
        mtd = agg(g[(g["date"] >= mstart) & (g["date"] <= day)])
        elapsed = (day - mstart).days + 1
        # budget: config monthly budget, else sum of latest daily campaign budgets * days in month
        latest_budget = None
        if "budget_amount" in g and g["budget_amount"].notna().any():
            lb = g[g["date"] == g["date"].max()].groupby("campaign")["budget_amount"].max()
            act = g[(g["date"] == g["date"].max()) & (g["spend"] > 0)]["campaign"].unique()
            latest_budget = float(lb[lb.index.isin(act)].sum()) if len(act) else float(lb.sum())
        month_budget = c.get("monthly_budget") or (latest_budget * dim if latest_budget else None)
        projected = mtd["spend"] / elapsed * dim if elapsed else None
        pacing = projected / month_budget if month_budget else None

        # daily series (30d) for charts
        series = (g30.groupby("date")[["spend", "conversions", "conversion_value", "clicks"]].sum()
                  .reindex(pd.date_range(d30[0], d30[1]).date, fill_value=0))
        ser = {"dates": [str(x) for x in series.index], "spend": series["spend"].round(2).tolist(),
               "conversions": series["conversions"].round(2).tolist(),
               "conversion_value": series["conversion_value"].round(2).tolist(),
               "clicks": series["clicks"].tolist()}
        if acct_mode == "mixed":
            idx = pd.date_range(d30[0], d30[1]).date
            for nm in ("ecommerce", "leads"):
                sg = g30[g30["campaign"].map(camp_modes) == nm].groupby("date")[["spend", "conversions", "conversion_value"]].sum().reindex(idx, fill_value=0)
                ser[nm] = {k: sg[k].round(2).tolist() for k in ("spend", "conversions", "conversion_value")}

        camps = []
        for k, cg in g.groupby("campaign"):
            cy, c7, cp7, c30 = agg(cg[cg["date"] == day]), agg(between(cg, w_this)), agg(between(cg, w_prev)), agg(between(cg, d30))
            status = str(cg.sort_values("date")["campaign_status"].iloc[-1]) if "campaign_status" in cg else ""
            if c30["spend"] == 0:
                continue
            bud = None
            if "budget_amount" in cg and cg["budget_amount"].notna().any():
                bud = float(cg.sort_values("date")["budget_amount"].iloc[-1])
            camps.append({"campaign": k, "type": str(cg["campaign_type"].iloc[-1]), "status": status,
                          "bidding": str(cg["bidding_strategy_type"].iloc[-1]), "mode": camp_modes[k],
                          "daily_budget": bud, "yesterday": cy, "last7": c7, "prev7": cp7, "last30": c30})
        camps.sort(key=lambda x: -x["last7"]["spend"])

        flags = build_flags(acct_mode, c, y, l7, p7, m30, camps, pacing, g, day)
        g = g.drop(columns="_mode")
        out["accounts"].append({"account": acct, "currency": cur, "mode": acct_mode, "config": c,
                                "yesterday": y, "last7": l7, "prev7": p7, "last30": m30, "mtd": mtd,
                                "month": {"days_elapsed": elapsed, "days_in_month": dim, "budget": month_budget,
                                          "projected_spend": projected, "pacing": pacing,
                                          "budget_source": "config" if c.get("monthly_budget") else
                                          ("daily budgets x days" if month_budget else None)},
                                "series": ser, "campaigns": camps, "flags": flags,
                                "status": "red" if any(f["level"] == "red" for f in flags) else
                                ("amber" if any(f["level"] == "amber" for f in flags) else "green")})
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "metrics.json"), "w") as f:
        json.dump(out, f, indent=2, default=lambda o: None if o != o else o)
    print_summary(out)


def build_flags(mode, c, y, l7, p7, m30, camps, pacing, g, day):
    F = []

    def add(level, msg, campaign=None):
        F.append({"level": level, "campaign": campaign, "message": msg})

    # tracking / delivery
    if y["spend"] > 0 and y["impressions"] == 0:
        add("red", "Spend recorded with zero impressions yesterday; check data refresh.")
    if y["spend"] == 0 and l7["spend"] > 0:
        add("red", "No spend yesterday although the account spent in the last 7 days: campaigns may be paused, "
                   "disapproved, out of budget, or billing failed.")
    daily_conv = m30["conversions"] / 30
    if daily_conv >= 1.5:
        last3 = g[g["date"] >= day - dt.timedelta(days=2)]["conversions"].sum()
        if last3 == 0:
            add("red", f"No conversions in 3 days (usually ~{daily_conv:.1f}/day). Check conversion tracking.")
    # efficiency vs prior week (mixed accounts: check the lead and ecommerce parts separately)
    parts = []
    if mode in ("leads", "ecommerce"):
        parts.append((mode, l7, p7, ""))
    else:
        parts += [("leads", l7["leads"], p7["leads"], "Lead campaigns: "), ("ecommerce", l7["ecom"], p7["ecom"], "Ecommerce campaigns: ")]
    for kind, a7, b7, pre in parts:
        if not a7["spend"]:
            continue
        if kind == "leads":
            tgt = c.get("target_cpa")
            if a7["cpa"] and b7["cpa"] and a7["cpa"] > 1.3 * b7["cpa"] and a7["conversions"] >= 3:
                add("amber", f"{pre}cost per lead up {pct(a7['cpa'], b7['cpa']):.0%} vs previous 7 days "
                             f"({a7['cpa']:.0f} vs {b7['cpa']:.0f}).")
            if tgt and a7["cpa"] and a7["cpa"] > 1.1 * tgt:
                add("amber" if a7["cpa"] <= 1.5 * tgt else "red",
                    f"{pre}7-day cost per lead {a7['cpa']:.2f} is above the {tgt:.0f} target.")
            if a7["conversions"] == 0:
                add("red", f"{pre}{a7['spend']:.0f} spent in 7 days with no leads.")
        else:
            tgt = c.get("target_roas")
            if a7["roas"] is not None and b7["roas"] and a7["roas"] < 0.75 * b7["roas"] and a7["spend"] > 50:
                add("amber", f"{pre}ROAS down {abs(pct(a7['roas'], b7['roas'])):.0%} vs previous 7 days "
                             f"({a7['roas']:.2f}x vs {b7['roas']:.2f}x).")
            if tgt and not c.get("target_poas") and a7["roas"] is not None and a7["roas"] < 0.8 * tgt:
                add("amber", f"{pre}7-day ROAS {a7['roas']:.2f}x is below the {tgt:.1f}x target.")
            if c.get("target_poas") and not c.get("margin"):
                add("info", f"{pre}POAS target {c['target_poas']}x set, but no product margin: can't measure profit yet. "
                            "Add the margin to the config.")
            if c.get("target_poas") and c.get("margin") and a7["roas"] is not None and a7["roas"] * c["margin"] < c["target_poas"]:
                add("amber" if a7["roas"] * c["margin"] >= 1 else "red",
                    f"{pre}7-day POAS {a7['roas'] * c['margin']:.2f}x (ROAS {a7['roas']:.2f}x at {c['margin']:.0%} margin) "
                    f"vs the {c['target_poas']:.1f}x target.")
            elif c.get("margin") and a7["roas"] is not None and a7["roas"] * c["margin"] < 1:
                add("red", f"{pre}7-day ROAS {a7['roas']:.2f}x is below break-even ({1 / c['margin']:.2f}x at "
                           f"{c['margin']:.0%} margin).")
            elif a7["roas"] is not None and a7["roas"] < 1 and a7["spend"] > 50:
                add("red", f"{pre}7-day ROAS {a7['roas']:.2f}x: tracked revenue is below ad spend.")
    if pacing is not None:
        if pacing > 1.1:
            add("amber", f"Month on track to spend {pacing:.0%} of budget.")
        elif pacing < 0.8:
            add("amber", f"Month on track to spend only {pacing:.0%} of budget.")
    for cp in camps:
        n, c7, cp7 = cp["campaign"], cp["last7"], cp["prev7"]
        if cp["status"] and cp["status"].upper() not in ("ENABLED", "", "NAN") and cp["yesterday"]["spend"] > 0:
            add("amber", f"Status {cp['status']} but still spending.", n)
        lost_b = c7.get("search_budget_lost_impression_share")
        lost_r = c7.get("search_rank_lost_impression_share")
        c30 = cp["last30"]
        good_eff = ((cp["mode"] == "leads" and c7["cpa"] and c30["cpa"] and c7["cpa"] <= c30["cpa"] * 1.05) or
                    (cp["mode"] == "ecommerce" and c7["roas"] and c30["roas"] and c7["roas"] >= c30["roas"] * 0.95))
        if lost_b is not None and lost_b >= 0.2:
            add("amber" if good_eff else "info",
                f"Losing {lost_b:.0%} of search impressions to budget"
                + (" while efficiency is at or better than average: candidate for more budget." if good_eff
                   else "; fix efficiency before adding budget."), n)
        if lost_r is not None and lost_r >= 0.5:
            add("info", f"Losing {lost_r:.0%} of search impressions to ad rank (bids, ad quality, landing page).", n)
        if c7["spend"] > 0 and cp7["spend"] > 0 and abs(pct(c7["spend"], cp7["spend"])) > 0.5:
            add("info", f"Spend {'up' if c7['spend'] > cp7['spend'] else 'down'} "
                        f"{abs(pct(c7['spend'], cp7['spend'])):.0%} week on week.", n)
        if cp["daily_budget"] and cp["yesterday"]["spend"] > 1.6 * cp["daily_budget"]:
            add("info", f"Spent {cp['yesterday']['spend']:.0f} yesterday on a {cp['daily_budget']:.0f} daily budget "
                        "(Google allows up to 2x on a day; monthly cap is ~30.4x).", n)
        if cp["mode"] == "leads" and c7["spend"] > 0 and c7["conversions"] == 0 and c7["spend"] >= 0.15 * (m30["spend"] / 30 * 7 or 1) and mode != "leads":
            add("amber", f"{c7['spend']:.0f} spent in 7 days with no conversions.", n)
    return F


def fmt_money(v, cur=""):
    if v is None:
        return "–"
    sym = "$" if cur in ("AUD", "USD", "NZD", "CAD", "") else ""
    return f"{sym}{v:,.0f}" if abs(v) >= 100 else f"{sym}{v:,.2f}"


def print_summary(out):
    print(f"Report date {out['report_date']}  (last 7 = {out['windows']['last7']}, prev 7 = {out['windows']['prev7']})")
    for A in out["accounts"]:
        y, l7, p7 = A["yesterday"], A["last7"], A["prev7"]
        k = "cpa" if A["mode"] == "leads" else "roas"
        print(f"\n[{A['status'].upper()}] {A['account']} ({A['mode']}, {A['currency']})")
        if A["mode"] == "mixed":
            print(f"  Ecommerce 7d: spend {l7['ecom']['spend']:.2f}, revenue {l7['ecom']['conversion_value']:.2f}, ROAS "
                  f"{l7['ecom']['roas'] if l7['ecom']['roas'] is None else round(l7['ecom']['roas'], 2)} vs "
                  f"{p7['ecom']['roas'] if p7['ecom']['roas'] is None else round(p7['ecom']['roas'], 2)}")
            print(f"  Leads 7d: spend {l7['leads']['spend']:.2f}, leads {l7['leads']['conversions']:.1f}, CPL "
                  f"{l7['leads']['cpa'] if l7['leads']['cpa'] is None else round(l7['leads']['cpa'], 2)} vs "
                  f"{p7['leads']['cpa'] if p7['leads']['cpa'] is None else round(p7['leads']['cpa'], 2)}")
        print(f"  Yesterday: spend {y['spend']:.2f}, conv {y['conversions']:.1f}, value {y['conversion_value']:.2f}")
        print(f"  Last 7: spend {l7['spend']:.2f} ({pct(l7['spend'], p7['spend']) or 0:+.0%}), conv {l7['conversions']:.1f} "
              f"({pct(l7['conversions'], p7['conversions']) or 0:+.0%}), {k} {l7[k] if l7[k] is None else round(l7[k], 2)} "
              f"vs {p7[k] if p7[k] is None else round(p7[k], 2)}")
        m = A["month"]
        if m["pacing"]:
            print(f"  Month: projected {m['projected_spend']:.0f} vs budget {m['budget']:.0f} ({m['pacing']:.0%}, {m['budget_source']})")
        for fl in A["flags"]:
            print(f"  - {fl['level']}: {(fl['campaign'] + ': ') if fl['campaign'] else ''}{fl['message']}")
    if out.get("inactive"):
        print("\nNo spend in 30 days (left out): " + ", ".join(out["inactive"]))


# ------------------------------------------------------------------ render

def charts(A, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    s = A["series"]
    x = pd.to_datetime(s["dates"])
    spend = pd.Series(s["spend"], index=x)
    conv = pd.Series(s["conversions"], index=x)
    val = pd.Series(s["conversion_value"], index=x)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": COL["line"], "axes.labelcolor": COL["muted"],
                         "xtick.color": COL["muted"], "ytick.color": COL["muted"]})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 2.9), dpi=150)
    ax1.bar(x, spend, color=COL["accent"], width=0.8, label="Spend")
    ax1.set_title("Spend and conversions, last 30 days", fontsize=10, color=COL["ink"], loc="left")
    ax1b = ax1.twinx()
    ax1b.plot(x, conv.rolling(7, min_periods=1).mean(), color=COL["accent2"], lw=2, label="Conversions (7-day avg)")
    ax1b.scatter(x, conv, color=COL["accent2"], s=8, alpha=0.6)
    ax1b.set_ylim(bottom=0)
    ax1.legend(handles=[ax1.patches[0] if ax1.patches else None, ax1b.lines[0]][1:] if not ax1.patches else
               [ax1.containers[0], ax1b.lines[0]], labels=["Spend", "Conversions (7-day avg)"],
               loc="upper left", frameon=False, fontsize=8)
    def line(ax, y, title, tgt=None, tlabel=" target", color=COL["brand"]):
        ax.plot(x, y, color=color, lw=2)
        ax.set_title(title, fontsize=10, color=COL["ink"], loc="left")
        if tgt:
            ax.axhline(tgt, color=COL["bad"], ls="--", lw=1)
            ax.text(x[0], tgt, tlabel, color=COL["bad"], va="bottom", fontsize=8)

    def roll_ratio(num, den):
        return num.rolling(7, min_periods=3).sum() / den.rolling(7, min_periods=3).sum().replace(0, float("nan"))

    cfg = A["config"]
    if A["mode"] == "leads":
        line(ax2, roll_ratio(spend, conv), "Cost per lead, 7-day rolling", cfg.get("target_cpa"))
    elif A["mode"] == "ecommerce":
        tgt = cfg.get("target_roas") or (1 / cfg["margin"] if cfg.get("margin") else None)
        line(ax2, roll_ratio(val, spend), "ROAS, 7-day rolling", tgt, " target" if cfg.get("target_roas") else " break-even")
    else:
        e, l = s["ecommerce"], s["leads"]
        es, ev = pd.Series(e["spend"], index=x), pd.Series(e["conversion_value"], index=x)
        ls_, lc = pd.Series(l["spend"], index=x), pd.Series(l["conversions"], index=x)
        line(ax2, roll_ratio(ev, es), "ROAS (ecommerce) and cost per lead, 7-day", cfg.get("target_roas"))
        ax2r = ax2.twinx()
        ax2r.plot(x, roll_ratio(ls_, lc), color=COL["accent2"], lw=1.6, ls="--")
        ax2r.set_ylim(bottom=0)
        ax2r.spines[["top"]].set_visible(False)
        ax2.legend(handles=[ax2.lines[0], ax2r.lines[0]], labels=["ROAS (left)", "Cost per lead (right)"],
                   loc="upper left", frameon=False, fontsize=8)
    ax2.set_ylim(bottom=0)
    for ax in (ax1, ax2):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        ax.grid(axis="y", color=COL["line"], lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    ax1b.spines[["top"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def html_bars(values, color, height=56, title="", fmt=lambda v: f"{v:,.0f}", dates=None, line=None):
    """Email-safe bar chart from table cells (no images). Gmail and Outlook web render it."""
    vals = [0 if v is None else float(v) for v in values]
    mx = max(vals) if vals and max(vals) > 0 else 1
    cells = ""
    for v in vals:
        h = int(round(v / mx * height))
        if v > 0 and h < 2:
            h = 2
        cells += (f'<td valign="bottom" style="padding:0 1px"><div style="height:{h}px;font-size:0;line-height:0;'
                  f'background:{color}"></div></td>')
    left = dates[0] if dates else ""
    right = dates[-1] if dates else ""
    tot = f"{title}" + (f' <span style="color:{COL["muted"]};font-weight:400">· max {fmt(mx)}</span>' if mx else "")
    return (f'<div style="font-size:11px;font-weight:600;color:{COL["ink"]};margin:0 0 4px">{tot}</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;table-layout:fixed;'
            f'border-bottom:1px solid {COL["line"]};height:{height}px"><tr>{cells}</tr></table>'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-size:10px;color:{COL["muted"]}"><tr>'
            f'<td style="padding-top:2px">{left}</td><td align="right" style="padding-top:2px">{right}</td></tr></table>')


def weekly_eff(A):
    """Last 4 weeks of CPA or ROAS (by 7-day blocks ending at report date) for a compact trend row."""
    s = A["series"]
    n = len(s["dates"])
    blocks = []
    for k in range(4):
        hi = n - 7 * k
        lo = max(0, hi - 7)
        if hi <= 0:
            break
        if A["mode"] == "mixed":
            sp = sum(s["ecommerce"]["spend"][lo:hi]); val = sum(s["ecommerce"]["conversion_value"][lo:hi])
            lsp = sum(s["leads"]["spend"][lo:hi]); lc = sum(s["leads"]["conversions"][lo:hi])
            blocks.append((s["dates"][lo], (val / sp if sp else None), (lsp / lc if lc else None)))
        else:
            sp = sum(s["spend"][lo:hi]); cv = sum(s["conversions"][lo:hi]); val = sum(s["conversion_value"][lo:hi])
            blocks.append((s["dates"][lo], (val / sp if sp else None) if A["mode"] == "ecommerce" else None,
                           (sp / cv if cv else None) if A["mode"] == "leads" else None))
    return list(reversed(blocks))


def delta_html(v, good_when_up=True, neutral=False):
    if v is None:
        return f'<span style="color:{COL["muted"]}">–</span>'
    arrow = "▲" if v > 0 else ("▼" if v < 0 else "")
    if neutral or abs(v) < 0.005:
        col = COL["muted"]
    else:
        col = COL["good"] if (v > 0) == good_when_up else COL["bad"]
    return f'<span style="color:{col}">{arrow} {abs(v):.0%}</span>'


def tile(label, value, sub):
    return (f'<td width="25%" style="padding:10px 8px;border:1px solid {COL["line"]};border-radius:6px;background:#ffffff;'
            f'vertical-align:top"><div style="font-size:11px;color:{COL["muted"]};text-transform:uppercase;'
            f'letter-spacing:.04em">{label}</div><div style="font-size:20px;font-weight:700;color:{COL["ink"]};'
            f'margin:4px 0 2px">{value}</div><div style="font-size:11px">{sub}</div></td>')


def render(a):
    path = os.path.join(a.out, "metrics.json")
    if not os.path.exists(path):
        sys.exit("Run analyze first.")
    M = json.load(open(path))
    R = json.load(open(a.recs)) if a.recs else {}
    day = dt.date.fromisoformat(M["report_date"])
    E = html.escape
    dot = {"green": COL["good"], "amber": COL["warn"], "red": COL["bad"]}
    label = {"green": "On track", "amber": "Watch", "red": "Action needed"}
    attachments = []
    parts = []
    # header
    parts.append(f'''<tr><td style="background:{COL["brand"]};padding:22px 24px;border-radius:8px 8px 0 0">
<div style="font-size:12px;color:#c9d6ea;letter-spacing:.06em;text-transform:uppercase">{E(a.brand)}</div>
<div style="font-size:22px;font-weight:700;color:#ffffff;margin-top:4px">{E(a.title)}</div>
<div style="font-size:13px;color:#c9d6ea;margin-top:4px">{day.strftime("%A %-d %B %Y")} · last 7 days vs the 7 before</div>
</td></tr>''')
    # overview
    rows = ""
    for A in M["accounts"]:
        k = "Cost/lead" if A["mode"] == "leads" else ("ROAS (ecom)" if A["mode"] == "mixed" else "ROAS")
        v7 = A["last7"]["cpa"] if A["mode"] == "leads" else A["last7"]["roas"]
        vp = A["prev7"]["cpa"] if A["mode"] == "leads" else A["prev7"]["roas"]
        vtxt = fmt_money(v7, A["currency"]) if A["mode"] == "leads" else (f"{v7:.2f}x" if v7 is not None else "–")
        conv_txt = (f'{A["last7"]["ecom"]["conversions"]:.0f} sales · {A["last7"]["leads"]["conversions"]:.0f} leads'
                    if A["mode"] == "mixed" else f'{A["last7"]["conversions"]:.0f}')
        rows += (f'<tr><td style="padding:8px 6px;border-bottom:1px solid {COL["line"]}"><span style="display:inline-block;'
                 f'width:9px;height:9px;border-radius:50%;background:{dot[A["status"]]};margin-right:6px"></span>'
                 f'<b>{E(A["account"])}</b><br><span style="font-size:11px;color:{dot[A["status"]]}">{label[A["status"]]}</span></td>'
                 f'<td align="right" style="padding:8px 6px;border-bottom:1px solid {COL["line"]}">{fmt_money(A["last7"]["spend"], A["currency"])}'
                 f'<br><span style="font-size:11px">{delta_html(pct(A["last7"]["spend"], A["prev7"]["spend"]), neutral=True)}</span></td>'
                 f'<td align="right" style="padding:8px 6px;border-bottom:1px solid {COL["line"]}">{conv_txt}'
                 f'<br><span style="font-size:11px">{delta_html(pct(A["last7"]["conversions"], A["prev7"]["conversions"]))}</span></td>'
                 f'<td align="right" style="padding:8px 6px;border-bottom:1px solid {COL["line"]}">{vtxt} <span style="font-size:11px;'
                 f'color:{COL["muted"]}">{k}</span><br><span style="font-size:11px">'
                 f'{delta_html(pct(v7, vp), good_when_up=(A["mode"] != "leads"))}</span></td></tr>')
    overview = R.get("overview", "")
    parts.append(f'''<tr><td style="background:#ffffff;padding:20px 24px">
{f'<p style="margin:0 0 14px;font-size:14px;line-height:1.55;color:{COL["ink"]}">{E(overview)}</p>' if overview else ''}
<table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;color:{COL["ink"]};border-collapse:collapse">
<tr style="color:{COL["muted"]};font-size:11px;text-transform:uppercase;letter-spacing:.04em">
<td style="padding:6px">Account</td><td align="right" style="padding:6px">Spend 7d</td>
<td align="right" style="padding:6px">Conv. 7d</td><td align="right" style="padding:6px">Efficiency</td></tr>{rows}</table>
</td></tr>''')
    # per account
    for i, A in enumerate(M["accounts"]):
        cur, y, l7, p7 = A["currency"], A["yesterday"], A["last7"], A["prev7"]
        chart = os.path.join(a.out, f"chart_{i}.png")
        charts(A, chart)
        attachments.append({"path": chart, "filename": f"chart_{i}.png", "inline": True, "mimeType": "image/png"})
        cid = len(attachments) - 1
        ser = A["series"]
        dl = [dt.date.fromisoformat(d).strftime("%-d %b") for d in ser["dates"]]
        money = lambda v: fmt_money(v, A["currency"])
        if A["mode"] == "mixed":
            second = html_bars(ser["ecommerce"]["conversion_value"], COL["good"], title="Daily revenue (ecommerce)", fmt=money, dates=[dl[0], dl[-1]])
            third = html_bars(ser["leads"]["conversions"], COL["accent2"], title="Daily leads", dates=[dl[0], dl[-1]])
        elif A["mode"] == "ecommerce":
            second = html_bars(ser["conversion_value"], COL["good"], title="Daily revenue", fmt=money, dates=[dl[0], dl[-1]])
            third = html_bars(ser["conversions"], COL["accent2"], title="Daily conversions", fmt=lambda v: f"{v:,.1f}", dates=[dl[0], dl[-1]])
        else:
            second = html_bars(ser["conversions"], COL["accent2"], title="Daily leads", fmt=lambda v: f"{v:,.0f}", dates=[dl[0], dl[-1]])
            third = ""
        first = html_bars(ser["spend"], COL["accent"], title="Daily spend", fmt=money, dates=[dl[0], dl[-1]])
        wk = weekly_eff(A)
        wk_cells = ""
        for start, roas_v, cpa_v in wk:
            lab = dt.date.fromisoformat(start).strftime("w/c %-d %b")
            val = []
            if roas_v is not None or A["mode"] in ("ecommerce",):
                val.append("–" if roas_v is None else f"{roas_v:.2f}x ROAS")
            if cpa_v is not None or A["mode"] == "leads":
                val.append("–" if cpa_v is None else f"{money(cpa_v)} per lead")
            if A["mode"] == "mixed" and roas_v is None and cpa_v is None:
                val = ["–"]
            wk_cells += (f'<td style="padding:6px;border:1px solid {COL["line"]};font-size:11px;text-align:center">'
                         f'<div style="color:{COL["muted"]}">{lab}</div><div style="font-weight:600;color:{COL["ink"]}">'
                         f'{"<br>".join(val)}</div></td>')
        html_charts = (f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0 4px"><tr>'
                       f'<td width="{50 if third else 50}%" valign="top" style="padding-right:8px">{first}</td>'
                       f'<td width="50%" valign="top" style="padding-left:8px">{second}</td></tr>'
                       + (f'<tr><td colspan="2" style="padding-top:10px">{third}</td></tr>' if third else "")
                       + f'</table><div style="font-size:11px;font-weight:600;color:{COL["ink"]};margin:10px 0 4px">'
                       f'Weekly efficiency, last 4 weeks</div><table width="100%" cellpadding="0" cellspacing="0" '
                       f'style="border-collapse:collapse"><tr>{wk_cells}</tr></table>')
        chart_block = (html_charts if a.charts == "html" else
                       f'<img src="cid:{cid}" width="592" alt="Charts for {E(A["account"])}" style="display:block;width:100%;'
                       f'max-width:592px;margin:14px 0 4px;border:0">')
        lead = A["mode"] == "leads"
        mixed = A["mode"] == "mixed"
        spend_tile = tile("Spend (7d)", fmt_money(l7["spend"], cur),
                          delta_html(pct(l7["spend"], p7["spend"]), neutral=True) + f'<span style="color:{COL["muted"]}">&nbsp;vs prev</span>')
        roas_txt = lambda r: f"{r:.2f}x" if r is not None else "–"
        cfgA = A["config"]

        def tgt_txt(kind):
            if kind == "cpa" and cfgA.get("target_cpa"):
                return f'<br><span style="color:{COL["muted"]}">target {fmt_money(cfgA["target_cpa"], cur)}</span>'
            if kind == "roas" and cfgA.get("target_poas"):
                return (f'<br><span style="color:{COL["muted"]}">target POAS {cfgA["target_poas"]:g}x'
                        + (f' (= {cfgA["target_roas"]:.1f}x ROAS)' if cfgA.get("target_roas") else ", margin needed") + '</span>')
            if kind == "roas" and cfgA.get("target_roas"):
                return f'<br><span style="color:{COL["muted"]}">target {cfgA["target_roas"]:g}x</span>'
            return ""
        if mixed:
            e7, ep7, q7, qp7 = l7["ecom"], p7["ecom"], l7["leads"], p7["leads"]
            t = [spend_tile,
                 tile("Revenue · ROAS (7d)", f'{fmt_money(e7["conversion_value"], cur)} · {roas_txt(e7["roas"])}',
                      delta_html(pct(e7["roas"], ep7["roas"])) + f'<span style="color:{COL["muted"]}">&nbsp;ROAS</span>' + tgt_txt("roas")),
                 tile("Leads (7d)", f'{q7["conversions"]:.0f}', delta_html(pct(q7["conversions"], qp7["conversions"]))),
                 tile("Cost per lead", fmt_money(q7["cpa"], cur), delta_html(pct(q7["cpa"], qp7["cpa"]), good_when_up=False) + tgt_txt("cpa"))]
        else:
            t = [spend_tile,
                 tile("Leads (7d)" if lead else "Conversions (7d)", f'{l7["conversions"]:.0f}',
                      delta_html(pct(l7["conversions"], p7["conversions"]))),
                 tile("Cost per lead" if lead else "ROAS (7d)",
                      fmt_money(l7["cpa"], cur) if lead else roas_txt(l7["roas"]),
                      delta_html(pct(l7["cpa"], p7["cpa"]) if lead else pct(l7["roas"], p7["roas"]), good_when_up=not lead)
                      + tgt_txt("cpa" if lead else "roas")),
                 tile("Revenue (7d)" if not lead else "Conv. rate (7d)",
                      fmt_money(l7["conversion_value"], cur) if not lead else (f'{l7["cvr"]:.1%}' if l7["cvr"] is not None else "–"),
                      delta_html(pct(l7["conversion_value"], p7["conversion_value"]) if not lead else pct(l7["cvr"], p7["cvr"])))]
        m = A["month"]
        pace = ""
        if m["pacing"]:
            col = COL["good"] if 0.9 <= m["pacing"] <= 1.05 else COL["warn"]
            pace = (f'Month to date {fmt_money(A["mtd"]["spend"], cur)} · projected {fmt_money(m["projected_spend"], cur)} of '
                    f'{fmt_money(m["budget"], cur)} budget (<span style="color:{col}"><b>{m["pacing"]:.0%}</b></span>)')
        if mixed:
            yline = (f'Yesterday: {fmt_money(y["spend"], cur)} spend · {y["clicks"]:.0f} clicks · '
                     f'{fmt_money(y["ecom"]["conversion_value"], cur)} revenue · {y["leads"]["conversions"]:.0f} leads')
        else:
            yline = (f'Yesterday: {fmt_money(y["spend"], cur)} spend · {y["clicks"]:.0f} clicks · {y["conversions"]:.1f} '
                     f'{"leads" if lead else "conversions"}' + ("" if lead else f' · {fmt_money(y["conversion_value"], cur)} revenue'))
        recs = R.get("accounts", {}).get(A["account"], [])
        flags = [f for f in A["flags"] if f["level"] in ("red", "amber")]
        rec_html = ""
        if recs:
            rec_html = "".join(f'<li style="margin:0 0 6px">{E(r)}</li>' for r in recs)
            rec_html = (f'<div style="font-size:12px;font-weight:700;color:{COL["ink"]};margin:14px 0 6px;text-transform:uppercase;'
                        f'letter-spacing:.04em">Recommendations</div><ol style="margin:0;padding-left:18px;font-size:13px;'
                        f'line-height:1.5;color:{COL["ink"]}">{rec_html}</ol>')
        elif flags:
            rec_html = "".join(f'<li style="margin:0 0 6px">{E((f["campaign"] + ": ") if f["campaign"] else "")}{E(f["message"])}</li>' for f in flags)
            rec_html = (f'<div style="font-size:12px;font-weight:700;margin:14px 0 6px;text-transform:uppercase">Watch</div>'
                        f'<ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.5">{rec_html}</ul>')
        crow = ""
        for cp in A["campaigns"]:
            c7, cp7 = cp["last7"], cp["prev7"]
            effv = (fmt_money(c7["cpa"], cur) if cp["mode"] == "leads" else (f'{c7["roas"]:.2f}x' if c7["roas"] is not None else "–"))
            effd = delta_html(pct(c7["cpa"], cp7["cpa"]) if cp["mode"] == "leads" else pct(c7["roas"], cp7["roas"]),
                              good_when_up=cp["mode"] != "leads")
            isv = c7.get("search_impression_share")
            crow += (f'<tr><td style="padding:7px 6px;border-bottom:1px solid {COL["line"]}">{E(cp["campaign"])}<br>'
                     f'<span style="font-size:11px;color:{COL["muted"]}">{E(cp["type"].replace("_", " ").title())}'
                     f'{" · budget " + fmt_money(cp["daily_budget"], cur) + "/day" if cp["daily_budget"] else ""}</span></td>'
                     f'<td align="right" style="padding:7px 6px;border-bottom:1px solid {COL["line"]}">{fmt_money(c7["spend"], cur)}</td>'
                     f'<td align="right" style="padding:7px 6px;border-bottom:1px solid {COL["line"]}">{c7["conversions"]:.1f}</td>'
                     f'<td align="right" style="padding:7px 6px;border-bottom:1px solid {COL["line"]}">{effv}<br>'
                     f'<span style="font-size:11px">{effd}</span></td>'
                     f'<td align="right" style="padding:7px 6px;border-bottom:1px solid {COL["line"]}">'
                     f'{"–" if isv is None else f"{isv:.0%}"}</td></tr>')
        parts.append(f'''<tr><td style="background:{COL["bg"]};padding:4px 0"></td></tr>
<tr><td style="background:#ffffff;padding:20px 24px">
<div style="font-size:17px;font-weight:700;color:{COL["ink"]}"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;
background:{dot[A["status"]]};margin-right:8px"></span>{E(A["account"])}</div>
<div style="font-size:12px;color:{COL["muted"]};margin:3px 0 12px">{"Lead generation" if lead else ("Ecommerce + lead generation" if mixed else "Ecommerce")} · {E(cur)} · {yline}</div>
<table width="100%" cellpadding="0" cellspacing="6" style="border-collapse:separate"><tr>{"".join(t)}</tr></table>
{f'<div style="font-size:12px;color:{COL["muted"]};margin:8px 0 0">{pace}</div>' if pace else ''}
{chart_block}
{rec_html}
<div style="font-size:12px;font-weight:700;color:{COL["ink"]};margin:16px 0 4px;text-transform:uppercase;letter-spacing:.04em">Campaigns, last 7 days</div>
<table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;color:{COL["ink"]};border-collapse:collapse">
<tr style="color:{COL["muted"]};font-size:10px;text-transform:uppercase"><td style="padding:5px 6px">Campaign</td>
<td align="right" style="padding:5px 6px">Spend</td><td align="right" style="padding:5px 6px">Conv.</td>
<td align="right" style="padding:5px 6px">{"CPA" if lead else ("ROAS / CPA" if mixed else "ROAS")}</td><td align="right" style="padding:5px 6px">Search IS</td></tr>{crow}</table>
</td></tr>''')
    note = ("Conversions for recent days are still being attributed (especially for longer purchase cycles), so yesterday's "
            "numbers often rise over the next few days. Trends use 7-day windows for that reason.")
    if M.get("inactive"):
        note += " No spend in the last 30 days: " + ", ".join(M["inactive"]) + "."
    parts.append(f'''<tr><td style="background:#ffffff;padding:14px 24px 20px;border-radius:0 0 8px 8px;border-top:1px solid {COL["line"]}">
<div style="font-size:11px;line-height:1.5;color:{COL["muted"]}">{E(note)} Data: Google Ads via Windsor.ai, refreshed {E(M["generated"][:16].replace("T", " "))}.</div>
</td></tr>''')
    body = (f'<!doctype html><html><body style="margin:0;padding:0;background:{COL["bg"]};font-family:-apple-system,Segoe UI,Roboto,'
            f'Helvetica,Arial,sans-serif"><table width="100%" cellpadding="0" cellspacing="0" style="background:{COL["bg"]}">'
            f'<tr><td align="center" style="padding:20px 10px"><table width="640" cellpadding="0" cellspacing="0" '
            f'style="width:100%;max-width:640px">{"".join(parts)}</table></td></tr></table></body></html>')
    import re
    body = re.sub(r">\s+<", "><", body)
    with open(os.path.join(a.out, "digest.html"), "w") as f:
        f.write(body)
    # browser preview with images inlined from files
    prev = body
    for idx, att in enumerate(attachments):
        prev = prev.replace(f'cid:{idx}"', f'{os.path.basename(att["path"])}"')
    with open(os.path.join(a.out, "preview.html"), "w") as f:
        f.write(prev)
    reds = sum(A["status"] == "red" for A in M["accounts"])
    subj = f"Google Ads daily digest · {day.strftime('%a %-d %b')}" + (f" · {reds} need action" if reds else "")
    with open(os.path.join(a.out, "email.json"), "w") as f:
        json.dump({"subject": subj, "html_file": os.path.join(a.out, "digest.html"),
                   "attachments": attachments if a.charts == "png" else [],
                   "chart_images": [x["path"] for x in attachments]}, f, indent=2)
    print(f"Saved {a.out}/digest.html (email, images as cid:0..n), preview.html (browser), email.json. Subject: {subj}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze")
    an.add_argument("--data", required=True)
    an.add_argument("--config")
    an.add_argument("--date", help="Report date (default: yesterday in --tz)")
    an.add_argument("--tz", default="Australia/Sydney")
    an.add_argument("--out", default="digest_out")
    an.set_defaults(func=analyze)
    r = sub.add_parser("render")
    r.add_argument("--out", default="digest_out")
    r.add_argument("--recs")
    r.add_argument("--title", default="Google Ads daily digest")
    r.add_argument("--brand", default="99 Degrees Tech")
    r.add_argument("--charts", choices=["html", "png"], default="html",
                   help="html: email-safe table charts, no attachments (default). png: inline images (needs attachments).")
    r.set_defaults(func=render)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
