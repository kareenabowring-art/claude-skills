#!/usr/bin/env python3
"""User / audience holdout analysis and power for incrementality tests (e.g. retargeting).

analyze: from group totals (or a user-level CSV) compute intent-to-treat (ITT) lift in conversion
         rate and revenue per user, intervals, incremental conversions/revenue, iROAS/iPOAS,
         treatment-on-treated (dilution-corrected) lift, and the incrementality factor.
power:   users needed per group, or MDE for a given size.

Usage: python3 holdout_test.py analyze --help ; python3 holdout_test.py power --help
"""
import argparse
import json
import sys

import numpy as np
import pandas as pd
from scipy import stats


def two_prop(x1, n1, x2, n2, level):
    p1, p2 = x1 / n1, x2 / n2
    diff = p1 - p2
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z = stats.norm.ppf(0.5 + level / 2)
    pooled = (x1 + x2) / (n1 + n2)
    se0 = np.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    pval = 2 * (1 - stats.norm.cdf(abs(diff) / se0)) if se0 > 0 else float("nan")
    return p1, p2, diff, (diff - z * se, diff + z * se), pval


def analyze_totals(a):
    lvl = a.level
    if (a.test_revenue is None) != (a.control_revenue is None):
        sys.exit("Give both --test-revenue and --control-revenue, or neither.")
    if a.test_revenue is None and (a.platform_attributed_revenue or a.margin):
        print("WARNING: no revenue given, so iROAS/iPOAS and the revenue incrementality factor can't be computed.")
    nt, nc = a.test_users, a.control_users
    p1, p2, d, ci, pval = two_prop(a.test_conversions, nt, a.control_conversions, nc, lvl)
    rel = d / p2 if p2 > 0 else float("nan")
    rel_ci = None
    if a.test_conversions > 0 and a.control_conversions > 0:
        # delta method on log(p1/p2): accounts for uncertainty in the control rate too
        se_log = np.sqrt((1 - p1) / (p1 * nt) + (1 - p2) / (p2 * nc))
        zq = stats.norm.ppf(0.5 + lvl / 2)
        lr = np.log(p1 / p2)
        rel_ci = [100 * (np.exp(lr - zq * se_log) - 1), 100 * (np.exp(lr + zq * se_log) - 1)]
    out = {"conversion": {"cr_test": p1, "cr_control": p2, "abs_lift": d, "abs_lift_interval": ci,
                          "rel_lift_pct": 100 * rel,
                          "rel_lift_interval_pct": rel_ci,
                          "p_value": pval,
                          "incremental_conversions": d * nt,
                          "incremental_conversions_interval": [ci[0] * nt, ci[1] * nt]}}
    if a.test_revenue is not None and a.control_revenue is not None:
        rpu_t, rpu_c = a.test_revenue / nt, a.control_revenue / nc
        drpu = rpu_t - rpu_c
        rev = {"rpu_test": rpu_t, "rpu_control": rpu_c, "rpu_diff": drpu,
               "incremental_revenue": drpu * nt}
        # Interval for revenue needs per-user variance. Approximate via AOV if no user-level data.
        if a.aov_sd is not None or a.test_conversions > 0:
            aov_t = a.test_revenue / max(a.test_conversions, 1)
            aov_c = a.control_revenue / max(a.control_conversions, 1)
            sd_aov = a.aov_sd if a.aov_sd is not None else 0.8 * (aov_t + aov_c) / 2  # assumption: CV 0.8
            # revenue per user = Bernoulli(p) * AOV; Var = p*(sd^2 + mu^2) - (p*mu)^2
            var_t = p1 * (sd_aov ** 2 + aov_t ** 2) - (p1 * aov_t) ** 2
            var_c = p2 * (sd_aov ** 2 + aov_c ** 2) - (p2 * aov_c) ** 2
            se = np.sqrt(var_t / nt + var_c / nc)
            z = stats.norm.ppf(0.5 + lvl / 2)
            rev["rpu_diff_interval"] = [drpu - z * se, drpu + z * se]
            rev["incremental_revenue_interval"] = [(drpu - z * se) * nt, (drpu + z * se) * nt]
            rev["p_value"] = float(2 * (1 - stats.norm.cdf(abs(drpu) / se))) if se > 0 else None
            rev["note"] = ("Revenue interval approximated from totals assuming order-value SD "
                           f"{sd_aov:,.0f}. Provide --aov-sd or user-level --users-csv for an exact bootstrap.")
        out["revenue"] = rev
    return out


def analyze_users(a):
    df = pd.read_csv(a.users_csv)
    for c in (a.group_col, a.conv_col):
        if c not in df.columns:
            sys.exit(f"Column '{c}' not in CSV. Columns: {list(df.columns)}")
    g = df[a.group_col].astype(str).str.lower()
    t, c = df[g == a.test_label.lower()], df[g == a.control_label.lower()]
    if len(t) == 0 or len(c) == 0:
        sys.exit("Could not find both groups; check --test-label/--control-label.")
    a.test_users, a.control_users = len(t), len(c)
    a.test_conversions, a.control_conversions = float(t[a.conv_col].clip(upper=1).sum()), float(c[a.conv_col].clip(upper=1).sum())
    has_rev = a.rev_col in df.columns
    a.test_revenue = float(t[a.rev_col].sum()) if has_rev else None
    a.control_revenue = float(c[a.rev_col].sum()) if has_rev else None
    out = analyze_totals(a)
    if has_rev:
        rng = np.random.default_rng(a.seed)
        rt, rc = t[a.rev_col].values, c[a.rev_col].values
        boots = np.empty(a.n_boot)
        for i in range(a.n_boot):
            boots[i] = rng.choice(rt, len(rt)).mean() - rng.choice(rc, len(rc)).mean()
        lo, hi = np.quantile(boots, [(1 - a.level) / 2, 1 - (1 - a.level) / 2])
        out["revenue"]["rpu_diff_interval"] = [float(lo), float(hi)]
        out["revenue"]["incremental_revenue_interval"] = [float(lo) * len(rt), float(hi) * len(rt)]
        out["revenue"]["p_value"] = float(min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean())))
        out["revenue"]["note"] = f"Bootstrap interval ({a.n_boot} resamples of users)."
    return out


def add_money(out, a):
    m = {}
    rev = out.get("revenue")
    if rev and a.spend:
        m["iroas"] = rev["incremental_revenue"] / a.spend
        if "incremental_revenue_interval" in rev:
            m["iroas_interval"] = [x / a.spend for x in rev["incremental_revenue_interval"]]
        if a.margin:
            m["ipoas"] = m["iroas"] * a.margin
            if "iroas_interval" in m:
                m["ipoas_interval"] = [x * a.margin for x in m["iroas_interval"]]
            m["breakeven_iroas"] = 1 / a.margin
    if a.spend:
        ic = out["conversion"]["incremental_conversions"]
        m["cost_per_incremental_conversion"] = a.spend / ic if ic > 0 else None
    if a.platform_attributed_revenue and rev:
        m["incrementality_factor_revenue"] = rev["incremental_revenue"] / a.platform_attributed_revenue
    if a.platform_attributed_conversions:
        m["incrementality_factor_conversions"] = out["conversion"]["incremental_conversions"] / a.platform_attributed_conversions
    if a.exposure_rate:
        e = a.exposure_rate
        c = out["conversion"]
        m["tot_abs_lift_per_exposed_user"] = c["abs_lift"] / e
        # relative lift among exposed: counterfactual CR of exposed is unknown; assume equal to control CR
        m["tot_rel_lift_pct_assuming_exposed_baseline_eq_control"] = 100 * (c["abs_lift"] / e) / c["cr_control"] if c["cr_control"] else None
        m["note_tot"] = ("Dilution correction (Wald/Bloom): ITT effect / exposure rate. Total incremental "
                         "conversions are unchanged; only per-exposed-user effects change. The relative figure "
                         "assumes exposed users' baseline equals the control average (biases it upward), and "
                         "platform reach overstates exposure (biases the per-exposed effect downward).")
    out["money"] = m
    return out


def cmd_analyze(a):
    if a.users_csv:
        out = analyze_users(a)
    else:
        need = [a.test_users, a.test_conversions, a.control_users, a.control_conversions]
        if any(v is None for v in need):
            sys.exit("Provide --users-csv, or all of --test-users --test-conversions --control-users --control-conversions.")
        out = analyze_totals(a)
    out = add_money(out, a)
    out["holdout_share"] = a.control_users / (a.control_users + a.test_users)
    lvl = int(a.level * 100)
    c = out["conversion"]
    print(f"Groups: test {a.test_users:,.0f} users, control {a.control_users:,.0f} users "
          f"(holdout {100*out['holdout_share']:.1f}%)")
    print(f"Conversion rate: test {100*c['cr_test']:.3f}% vs control {100*c['cr_control']:.3f}% -> "
          f"relative lift {c['rel_lift_pct']:+.1f}%" +
          (f" [{c['rel_lift_interval_pct'][0]:+.1f}%, {c['rel_lift_interval_pct'][1]:+.1f}%] ({lvl}%)" if c['rel_lift_interval_pct'] else "") +
          f", p={c['p_value']:.3f}")
    print(f"Incremental conversions (ITT, whole test group): {c['incremental_conversions']:,.0f} "
          f"[{c['incremental_conversions_interval'][0]:,.0f}, {c['incremental_conversions_interval'][1]:,.0f}]")
    if "revenue" in out:
        r = out["revenue"]
        s = f"Revenue per user: test {r['rpu_test']:.2f} vs control {r['rpu_control']:.2f}; incremental revenue {r['incremental_revenue']:,.0f}"
        if "incremental_revenue_interval" in r:
            s += f" [{r['incremental_revenue_interval'][0]:,.0f}, {r['incremental_revenue_interval'][1]:,.0f}]"
        if r.get("p_value") is not None:
            s += f", p={r['p_value']:.3f}"
        print(s)
        if "note" in r:
            print("  " + r["note"])
    m = out["money"]
    if "iroas" in m:
        s = f"iROAS {m['iroas']:.2f}"
        if "iroas_interval" in m:
            s += f" [{m['iroas_interval'][0]:.2f}, {m['iroas_interval'][1]:.2f}]"
        if "ipoas" in m:
            s += f"; iPOAS {m['ipoas']:.2f}"
            if "ipoas_interval" in m:
                s += f" [{m['ipoas_interval'][0]:.2f}, {m['ipoas_interval'][1]:.2f}]"
            s += f"; break-even iROAS {m['breakeven_iroas']:.2f}"
        print(s)
    if m.get("cost_per_incremental_conversion"):
        print(f"Cost per incremental conversion: {m['cost_per_incremental_conversion']:,.2f}")
    for k in ("incrementality_factor_revenue", "incrementality_factor_conversions"):
        if k in m:
            print(f"{k.replace('_', ' ').capitalize()}: {m[k]:.2f}")
    if m.get("tot_rel_lift_pct_assuming_exposed_baseline_eq_control") is not None:
        print(f"Dilution-corrected lift among exposed users (exposure {100*a.exposure_rate:.0f}%): "
              f"{m['tot_rel_lift_pct_assuming_exposed_baseline_eq_control']:+.1f}% (rough: likely overstated, because "
              "exposed users convert above the control average; and platform reach counts devices/cookies, which "
              "overstates exposure and so understates the per-exposed effect. Prefer user-level exposure flags.)")
    if a.out:
        with open(a.out, "w") as f:
            json.dump(out, f, indent=2, default=float)
        print(f"Saved {a.out}")


def cmd_power(a):
    z_a = stats.norm.ppf(1 - a.alpha / 2)
    z_b = stats.norm.ppf(a.power)
    p1 = a.baseline_cr
    if a.lift is not None:
        p2 = p1 * (1 + a.lift)
        k = a.holdout_share / (1 - a.holdout_share)  # control / test ratio
        # n_control with n_test = n_control / k
        var = p2 * (1 - p2) * k + p1 * (1 - p1)
        n_c = (z_a + z_b) ** 2 * var / (p2 - p1) ** 2
        n_t = n_c / k
        print(f"Baseline CR {100*p1:.3f}%, relative lift {100*a.lift:.1f}%, holdout {100*a.holdout_share:.0f}%, "
              f"alpha {a.alpha} two-sided, power {a.power}:")
        print(f"  control users needed: {n_c:,.0f}; test users: {n_t:,.0f}; total audience: {n_c + n_t:,.0f}")
    if a.audience:
        n_c = a.audience * a.holdout_share
        n_t = a.audience - n_c
        se = np.sqrt(p1 * (1 - p1) * (1 / n_c + 1 / n_t))
        mde_abs = (z_a + z_b) * se
        print(f"Audience {a.audience:,.0f} with {100*a.holdout_share:.0f}% holdout: MDE ~ {100*mde_abs/p1:.1f}% relative lift "
              f"({100*mde_abs:.3f} pts) at baseline CR {100*p1:.3f}%")
        if a.revenue_at_risk_aov:
            print(f"  Revenue at risk if ads are fully effective at that MDE: ~{n_c * mde_abs * a.revenue_at_risk_aov:,.0f}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("analyze")
    an.add_argument("--users-csv", help="User-level CSV with group, converted (0/1), revenue")
    an.add_argument("--group-col", default="group")
    an.add_argument("--conv-col", default="converted")
    an.add_argument("--rev-col", default="revenue")
    an.add_argument("--test-label", default="test")
    an.add_argument("--control-label", default="control")
    an.add_argument("--test-users", type=float)
    an.add_argument("--test-conversions", type=float, help="Converting users (not orders) in test group")
    an.add_argument("--test-revenue", type=float)
    an.add_argument("--control-users", type=float)
    an.add_argument("--control-conversions", type=float)
    an.add_argument("--control-revenue", type=float)
    an.add_argument("--aov-sd", type=float, help="SD of revenue per converting user (for totals-only revenue interval)")
    an.add_argument("--spend", type=float, help="Ad spend on the test group during the test")
    an.add_argument("--margin", type=float, help="Gross margin 0-1")
    an.add_argument("--exposure-rate", type=float, help="Share of test group actually served >=1 impression")
    an.add_argument("--platform-attributed-revenue", type=float)
    an.add_argument("--platform-attributed-conversions", type=float)
    an.add_argument("--level", type=float, default=0.90)
    an.add_argument("--n-boot", type=int, default=2000)
    an.add_argument("--seed", type=int, default=7)
    an.add_argument("--out", help="Write JSON results here")
    an.set_defaults(func=cmd_analyze)

    pw = sub.add_parser("power")
    pw.add_argument("--baseline-cr", type=float, required=True, help="Control conversion rate per user over the test, e.g. 0.015")
    pw.add_argument("--lift", type=float, help="Relative lift to detect, e.g. 0.10")
    pw.add_argument("--audience", type=float, help="Total users available; prints MDE")
    pw.add_argument("--holdout-share", type=float, default=0.2)
    pw.add_argument("--alpha", type=float, default=0.10)
    pw.add_argument("--power", type=float, default=0.80)
    pw.add_argument("--revenue-at-risk-aov", type=float, help="AOV, to estimate revenue at risk in the holdout")
    pw.set_defaults(func=cmd_power)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
