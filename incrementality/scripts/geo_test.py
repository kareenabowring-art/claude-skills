#!/usr/bin/env python3
"""Geo incrementality toolkit: design (pick groups, estimate MDE) and analyze (estimate lift).

Input: a long CSV with one row per date x geo: date, geo, KPI (revenue or orders).
Geos can be any regions (postcode clusters, SA4 regions, cities). For a national
natural-experiment analysis, pass series names as "geos" (e.g. the advertised
product line as the treated series and unaffected lines/organic sessions as controls).

Methods
- Synthetic control (SC): convex weights on scaled control geos + intercept, fitted on pre-period.
- Time-based regression (TBR): treated aggregate ~ a + b * control aggregate, fitted on pre-period;
  analytic interval for the cumulative effect.
- Placebo inference: in-time (fake test windows inside the pre-period) and in-space
  (random control groups as fake treatment). These capture autocorrelation and model error
  that the analytic interval ignores.

Usage: python3 geo_test.py design --help ; python3 geo_test.py analyze --help
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import optimize, stats

Z_POWER80 = 0.8416


# ---------------------------------------------------------------- data

def load_wide(path, date_col, geo_col, kpi_col):
    df = pd.read_csv(path)
    for c in (date_col, geo_col, kpi_col):
        if c not in df.columns:
            sys.exit(f"Column '{c}' not in CSV. Columns: {list(df.columns)}")
    df[date_col] = pd.to_datetime(df[date_col])
    df[geo_col] = df[geo_col].astype(str).str.strip()
    wide = df.pivot_table(index=date_col, columns=geo_col, values=kpi_col, aggfunc="sum")
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    missing = len(full) - len(wide.index)
    wide = wide.reindex(full).sort_index()
    gaps = wide.isna().sum()
    gaps = gaps[gaps > 0]
    if missing:
        print(f"Note: {missing} dates with no rows at all, filled with 0.")
    if len(gaps):
        print(f"WARNING: {len(gaps)} geos have missing days filled with 0 (a geo that starts late gets fake zeros): "
              + ", ".join(f"{g} ({n}d)" for g, n in gaps.sort_values(ascending=False).head(10).items())
              + ". Exclude them with --exclude-geos or fix the data if they are not true zero-sales days.")
    return wide.fillna(0.0)


def parse_list(s):
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


# ---------------------------------------------------------------- models

def fit_tbr(y, x):
    """OLS y = a + b x. Returns params, sigma, (X'X)^-1, n."""
    X = np.column_stack([np.ones_like(x), x])
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    n = len(y)
    sigma = np.sqrt(resid @ resid / max(n - 2, 1))
    return beta, sigma, xtx_inv, n


def tbr_effect(y_pre, x_pre, y_test, x_test, level=0.90):
    beta, sigma, xtx_inv, n = fit_tbr(y_pre, x_pre)
    pred = beta[0] + beta[1] * x_test
    effect = float(np.sum(y_test - pred))
    T = len(y_test)
    v = np.array([T, np.sum(x_test)])
    se = sigma * np.sqrt(T + v @ xtx_inv @ v)
    tq = stats.t.ppf(0.5 + level / 2, max(n - 2, 1))
    return {"effect": effect, "lo": effect - tq * se, "hi": effect + tq * se, "se": float(se),
            "counterfactual": pred, "a": float(beta[0]), "b": float(beta[1])}


def fit_sc(y_pre, X_pre):
    """Convex weights on scaled controls + intercept (demeaned least squares)."""
    k = X_pre.shape[1]
    scale = np.where(X_pre.mean(axis=0) > 0, y_pre.mean() / np.maximum(X_pre.mean(axis=0), 1e-12), 0.0)
    Xs = X_pre * scale
    yc = y_pre - y_pre.mean()
    Xc = Xs - Xs.mean(axis=0)
    w0 = np.full(k, 1.0 / k)
    obj = lambda w: np.sum((yc - Xc @ w) ** 2)
    grad = lambda w: -2 * Xc.T @ (yc - Xc @ w)
    res = optimize.minimize(obj, w0, jac=grad, method="SLSQP", bounds=[(0, 1)] * k,
                            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1,
                                          "jac": lambda w: np.ones_like(w)}],
                            options={"maxiter": 500, "ftol": 1e-10})
    w = np.clip(res.x, 0, None)
    w = w / w.sum() if w.sum() > 0 else w0
    intercept = y_pre.mean() - (Xs.mean(axis=0) @ w)
    return w, scale, intercept


def sc_predict(X, w, scale, intercept):
    return intercept + (X * scale) @ w


def fit_quality(y, yhat):
    resid = y - yhat
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - np.sum(resid ** 2) / ss_tot if ss_tot > 0 else float("nan")
    denom = np.where(np.abs(y) > 0, np.abs(y), np.nan)
    mape = float(np.nanmean(np.abs(resid) / denom))
    return float(r2), mape


def rel_effect_tbr(y_pre, x_pre, y_test, x_test):
    r = tbr_effect(y_pre, x_pre, y_test, x_test)
    base = r["counterfactual"].sum()
    return r["effect"] / base if base else np.nan


def rel_effect_sc(y_pre, X_pre, y_test, X_test):
    w, sc, ic = fit_sc(y_pre, X_pre)
    cf = sc_predict(X_test, w, sc, ic)
    return (y_test.sum() - cf.sum()) / cf.sum() if cf.sum() else np.nan


# ---------------------------------------------------------------- placebo / backtests

def backtest_windows(n_days, test_days, min_train, step):
    """(train_end, test_end) index pairs of fake test windows inside the given span."""
    out = []
    end = n_days
    while end - test_days >= min_train:
        out.append((end - test_days, end))
        end -= step
    return out[::-1]


def in_time_placebo(y, X, test_days, method="tbr", min_train=None, step=None):
    """Relative cumulative 'effects' on fake windows where true effect is 0. y, X are pre-period only."""
    n = len(y)
    min_train = min_train or max(28, 2 * test_days)
    step = step or max(1, test_days // 4)
    rels = []
    for tr_end, te_end in backtest_windows(n, test_days, min_train, step):
        y_tr, y_te = y[:tr_end], y[tr_end:te_end]
        if method == "tbr":
            x = X.sum(axis=1)
            rels.append(rel_effect_tbr(y_tr, x[:tr_end], y_te, x[tr_end:te_end]))
        else:
            rels.append(rel_effect_sc(y_tr, X[:tr_end], y_te, X[tr_end:te_end]))
    return np.array([r for r in rels if np.isfinite(r)])


# ---------------------------------------------------------------- design

def candidate_split(geos_sorted, share, rng, forced_t, forced_c):
    """Stratified random assignment: consecutive size-sorted blocks, pick treatment within each."""
    free = [g for g in geos_sorted if g not in forced_t and g not in forced_c]
    treat = list(forced_t)
    if not free:
        return treat
    # forced treatment geos count toward the target
    target = share * len(geos_sorted) - len(forced_t)
    share_eff = min(max(target / len(free), 0.0), 1.0)
    if share_eff <= 0:
        return treat
    m = max(2, int(round(1 / share_eff))) if share_eff < 0.5 else 4
    for i in range(0, len(free), m):
        block = free[i:i + m]
        exp = share_eff * len(block)
        n_pick = int(np.floor(exp)) + (1 if rng.random() < exp - np.floor(exp) else 0)  # randomised rounding
        if n_pick:
            treat += list(rng.choice(block, size=min(n_pick, len(block)), replace=False))
    return treat


def cmd_design(a):
    wide = load_wide(a.data, a.date_col, a.geo_col, a.kpi_col)
    if a.end:
        wide = wide.loc[: pd.Timestamp(a.end)]
    if a.start:
        wide = wide.loc[pd.Timestamp(a.start):]
    excl = set(parse_list(a.exclude_geos))
    wide = wide[[g for g in wide.columns if g not in excl]]
    forced_t, forced_c = parse_list(a.force_treatment), parse_list(a.force_control)
    geos = list(wide.mean().sort_values(ascending=False).index)
    n_days, n_geos = len(wide), len(geos)
    print(f"Data: {n_days} days, {n_geos} geos ({wide.index.min().date()} to {wide.index.max().date()}).")
    if n_geos < 10:
        print("WARNING: fewer than 10 geos. Geo tests will be noisy; consider finer geos (postcode clusters / SA4).")
    if n_days < 4 * a.test_days:
        print("WARNING: history shorter than 4x the test length; too few backtest windows, MDE will be unreliable.")

    rng = np.random.default_rng(a.seed)
    Y = wide.values
    total = Y.sum()
    cand = []
    seen = set()
    for _ in range(a.n_candidates):
        t = candidate_split(geos, a.treatment_share, rng, forced_t, forced_c)
        key = tuple(sorted(t))
        if key in seen or not t or len(t) >= n_geos - 1:
            continue
        seen.add(key)
        ti = [wide.columns.get_loc(g) for g in t]
        ci = [i for i in range(n_geos) if i not in ti]
        y, X = Y[:, ti].sum(axis=1), Y[:, ci]
        rels = in_time_placebo(y, X, a.test_days, "tbr")
        if len(rels) < 3:
            sys.exit("Not enough history to backtest this test length. Use more history or a shorter test.")
        share = y.sum() / total
        sd = float(np.sqrt(np.mean(rels ** 2)))  # RMSE around true zero (captures bias too)
        penalty = abs(share - a.treatment_share) * a.balance_weight
        cand.append((sd + penalty, sd, share, t))
    cand.sort(key=lambda r: r[0])
    top = cand[: a.top]

    # refine top candidates with SC backtests
    results = []
    for score, sd_tbr, share, t in top:
        ti = [wide.columns.get_loc(g) for g in t]
        ci = [i for i in range(n_geos) if i not in ti]
        y, X = Y[:, ti].sum(axis=1), Y[:, ci]
        rels_sc = in_time_placebo(y, X, a.test_days, "sc")
        sd_sc = float(np.sqrt(np.mean(rels_sc ** 2)))
        results.append({"treatment_geos": sorted(t), "kpi_share": share,
                        "backtest_rmse_tbr": sd_tbr, "backtest_rmse_sc": sd_sc,
                        "n_backtests": int(len(rels_sc))})
    key = "backtest_rmse_sc" if a.primary == "sc" else "backtest_rmse_tbr"
    results.sort(key=lambda r: r[key] + abs(r["kpi_share"] - a.treatment_share) * a.balance_weight)
    best = results[0]
    ti = [wide.columns.get_loc(g) for g in best["treatment_geos"]]
    ci = [i for i in range(n_geos) if i not in ti]
    y, X = Y[:, ti].sum(axis=1), Y[:, ci]

    z_alpha = stats.norm.ppf(1 - a.alpha / 2)
    mde_rows = []
    for L in sorted(set([14, 21, 28, 42, 56, a.test_days])):
        if n_days < max(28, 2 * L) + L:
            continue
        # Same noise measure and method the analysis uses for its reported interval
        r_t = in_time_placebo(y, X, L, a.primary)
        if len(r_t) < 5:
            continue
        sd = float(np.sqrt(np.mean(r_t ** 2)))
        mde = (z_alpha + Z_POWER80) * sd
        base_daily = y[-56:].mean()
        mde_rows.append({"test_days": L, "noise_rmse_pct": round(100 * sd, 2), "mde_pct": round(100 * mde, 2),
                         "mde_kpi_units": round(mde * base_daily * L, 2), "n_backtests": int(len(r_t))})

    out = {"best_design": best, "alternatives": results[1:], "mde_by_test_length": mde_rows,
           "alpha_two_sided": a.alpha, "power": 0.8,
           "control_geos": [wide.columns[i] for i in ci]}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "design.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    print("\nRecommended treatment geos (%d, %.1f%% of KPI):" % (len(best["treatment_geos"]), 100 * best["kpi_share"]))
    print("  " + ", ".join(best["treatment_geos"]))
    print(f"Backtest noise (RMSE of relative cumulative error, {a.test_days}-day windows): "
          f"TBR {100*best['backtest_rmse_tbr']:.2f}%, SC {100*best['backtest_rmse_sc']:.2f}%")
    print(f"\nMinimum detectable effect ({'synthetic control' if a.primary == 'sc' else 'TBR'}, 80% power, "
          f"alpha={a.alpha} two-sided), as % of treatment-group KPI:")
    print("(Optimistic: the split was chosen on these same backtests, and windows overlap. Add a 25% buffer; "
          "rows with <10 backtests are rough.)")
    if not mde_rows:
        print("  None: not enough history for >=5 backtest windows at any test length. Get more history.")
    for r in mde_rows:
        print(f"  {r['test_days']:>3} days: MDE {r['mde_pct']:.1f}%  (~{r['mde_kpi_units']:,.0f} KPI units)  "
              f"[{r['n_backtests']} backtests]")
    print("\nCompare MDE to expected lift = (channel spend in treatment geos x expected iROAS) / treatment KPI.")
    print("If the expected lift is below the MDE, lengthen the test, raise the treatment share, use a heavy-up, or don't test.")
    print(f"In analyze, use a pre-period of at least {4 * a.test_days} days (ideally all {n_days} days used here) "
          f"and the same --primary {a.primary}, so the reported interval matches this MDE.")
    print(f"Saved {os.path.join(a.out, 'design.json')}")
    _plot_design(wide, best["treatment_geos"], a.out)


def _plot_design(wide, treat, outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    t = wide[treat].sum(axis=1)
    c = wide[[g for g in wide.columns if g not in treat]].sum(axis=1)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t.index, t / t.mean(), label="Treatment (indexed)", lw=1.2)
    ax.plot(c.index, c / c.mean(), label="Control (indexed)", lw=1.2, alpha=0.8)
    ax.set_title("Treatment vs control, indexed to mean (should move together)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "design_fit.png"), dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- analyze

def cmd_analyze(a):
    wide = load_wide(a.data, a.date_col, a.geo_col, a.kpi_col)
    treat = parse_list(a.treatment_geos)
    missing = [g for g in treat if g not in wide.columns]
    if missing:
        sys.exit(f"Treatment geos not in data: {missing}")
    excl = set(parse_list(a.exclude_geos))
    controls = [g for g in wide.columns if g not in treat and g not in excl]
    if len(controls) < 2:
        sys.exit("Need at least 2 control geos.")
    if len(controls) + len(treat) < 10:
        print("WARNING: fewer than 10 geos in total. Results will be noisy and placebo inference limited.")
    pre = wide.loc[pd.Timestamp(a.pre_start): pd.Timestamp(a.pre_end)]
    test = wide.loc[pd.Timestamp(a.test_start): pd.Timestamp(a.test_end)]
    if len(pre) < 14 or len(test) < 1:
        sys.exit(f"Pre-period has {len(pre)} days and test {len(test)} days; need at least 14 pre days.")
    T = len(test)
    if a.spend_change is not None and a.spend_change < 0:
        print("Note: --spend-change is the amount of spend removed or added; using its absolute value.")
        a.spend_change = abs(a.spend_change)
    if a.kpi_type == "orders" and not a.value_per_unit:
        print("Note: KPI is orders and no --value-per-unit (AOV) given: reporting incremental orders and cost per "
              "incremental order, not iROAS.")
    if len(pre) < 4 * T:
        print(f"WARNING: pre-period ({len(pre)} days) is shorter than 4x the test ({4*T} days). Too few in-time "
              "placebo windows; the interval will fall back to in-space placebos or the TBR analytic interval.")

    y_pre, y_test = pre[treat].sum(axis=1).values, test[treat].sum(axis=1).values
    X_pre, X_test = pre[controls].values, test[controls].values
    x_pre, x_test = X_pre.sum(axis=1), X_test.sum(axis=1)

    # TBR
    tbr = tbr_effect(y_pre, x_pre, y_test, x_test, level=a.level)
    tbr_fit = tbr["a"] + tbr["b"] * x_pre
    # SC
    w, scale, ic = fit_sc(y_pre, X_pre)
    sc_fit = sc_predict(X_pre, w, scale, ic)
    sc_cf = sc_predict(X_test, w, scale, ic)
    sc_eff = float(y_test.sum() - sc_cf.sum())

    r2_tbr, mape_tbr = fit_quality(y_pre, tbr_fit)
    r2_sc, mape_sc = fit_quality(y_pre, sc_fit)

    # in-time placebo (pre-period only)
    pt_tbr = in_time_placebo(y_pre, X_pre, T, "tbr")
    pt_sc = in_time_placebo(y_pre, X_pre, T, "sc")

    # in-space placebo: random control groups of the same size as fake treatment
    rng = np.random.default_rng(a.seed)
    n_t = len(treat)
    ps_tbr, ps_sc = [], []
    if len(controls) >= n_t + 3:
        for _ in range(a.n_placebo):
            fake = list(rng.choice(controls, size=n_t, replace=False))
            donors = [g for g in controls if g not in fake]
            yp, yt = pre[fake].sum(axis=1).values, test[fake].sum(axis=1).values
            ps_tbr.append(rel_effect_tbr(yp, pre[donors].sum(axis=1).values, yt, test[donors].sum(axis=1).values))
            if len(ps_sc) < a.n_placebo_sc:
                ps_sc.append(rel_effect_sc(yp, pre[donors].values, yt, test[donors].values))
    ps_tbr, ps_sc = np.array([r for r in ps_tbr if np.isfinite(r)]), np.array([r for r in ps_sc if np.isfinite(r)])

    def summarise(name, eff, cf_sum, placebo_time, placebo_space, analytic=None):
        rel = eff / cf_sum if cf_sum else np.nan
        q_hi = 1 - (1 - a.level) / 2
        z = stats.norm.ppf(q_hi)
        d = {"method": name, "effect": eff, "counterfactual_total": float(cf_sum), "actual_total": float(y_test.sum()),
             "lift_pct": 100 * rel}
        if len(placebo_time) >= 5:
            sd_t = float(np.sqrt(np.mean(placebo_time ** 2)))
            d["interval_in_time"] = [(rel - z * sd_t) * cf_sum, (rel + z * sd_t) * cf_sum]
            d["p_in_time"] = float((1 + np.sum(np.abs(placebo_time) >= abs(rel))) / (1 + len(placebo_time)))
            d["n_in_time"] = int(len(placebo_time))
        if len(placebo_space) >= 10:
            sd_s = float(np.sqrt(np.mean(placebo_space ** 2)))
            d["interval_in_space"] = [(rel - z * sd_s) * cf_sum, (rel + z * sd_s) * cf_sum]
            d["p_in_space"] = float((1 + np.sum(np.abs(placebo_space) >= abs(rel))) / (1 + len(placebo_space)))
            d["n_in_space"] = int(len(placebo_space))
        if analytic:
            d["interval_analytic"] = analytic
        # One pre-registered rule, matching the design MDE: in-time placebo noise; fallbacks in order.
        for basis in ("interval_in_time", "interval_in_space", "interval_analytic"):
            if basis in d:
                d["interval_reported"], d["interval_basis"] = d[basis], basis.replace("interval_", "")
                break
        if "interval_reported" in d:
            w0 = d["interval_reported"][1] - d["interval_reported"][0]
            wider = [(k, v) for k, v in d.items() if k.startswith("interval_") and k not in ("interval_reported", "interval_basis")
                     and (v[1] - v[0]) > 1.25 * w0]
            if wider:
                d["wider_checks"] = {k.replace("interval_", ""): v for k, v in wider}
        return d

    res_tbr = summarise("TBR", tbr["effect"], tbr["counterfactual"].sum(), pt_tbr, ps_tbr, [tbr["lo"], tbr["hi"]])
    res_sc = summarise("Synthetic control", sc_eff, sc_cf.sum(), pt_sc, ps_sc)
    primary = res_sc if a.primary == "sc" else res_tbr
    if "interval_reported" not in primary:
        print("NOTE: synthetic control has no valid inference here (too few geos/history); using TBR as primary.")
        primary = res_tbr

    # money
    sign = -1 if a.design == "holdout" else 1  # holdout: ads' contribution = counterfactual - actual
    vpu = a.value_per_unit if a.kpi_type == "orders" else 1.0
    money = {}
    for r in (res_tbr, res_sc):
        m = {}
        iv = r.get("interval_reported", [np.nan, np.nan])
        units = r["effect"] * sign
        units_iv = sorted([iv[0] * sign, iv[1] * sign])
        m["incremental_kpi_driven_by_ads"] = units
        m["incremental_kpi_interval"] = units_iv
        if a.kpi_type == "orders" and a.spend_change:
            m["cost_per_incremental_order"] = a.spend_change / units if units > 0 else None
        if vpu:
            m["incremental_revenue"] = units * vpu
            m["incremental_revenue_interval"] = [x * vpu for x in units_iv]
            if a.spend_change:
                m["iroas"] = m["incremental_revenue"] / a.spend_change
                m["iroas_interval"] = [x / a.spend_change for x in m["incremental_revenue_interval"]]
                if a.margin:
                    m["ipoas"] = m["iroas"] * a.margin
                    m["ipoas_interval"] = [x * a.margin for x in m["iroas_interval"]]
                    m["breakeven_iroas"] = 1 / a.margin
        if a.platform_attributed:
            m["incrementality_factor"] = units / a.platform_attributed
        money[r["method"]] = m

    out = {"design": a.design, "kpi_type": a.kpi_type,
           "treatment_geos": treat, "n_controls": len(controls), "pre_days": len(pre), "test_days": T,
           "fit": {"TBR": {"r2": r2_tbr, "mape": mape_tbr}, "SC": {"r2": r2_sc, "mape": mape_sc}},
           "results": [res_tbr, res_sc], "money": money, "primary": primary["method"],
           "sc_top_weights": sorted([(controls[i], float(w[i])) for i in range(len(w)) if w[i] > 0.01],
                                    key=lambda t: -t[1])[:15],
           "inputs": {k: v for k, v in vars(a).items() if k != "func"}}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=lambda o: float(o) if isinstance(o, np.floating) else str(o))

    _print_analysis(out, a)
    _plot_analysis(pre, test, treat, y_pre, y_test, sc_fit, sc_cf, tbr_fit, tbr["counterfactual"], primary, a)


def _fmt(x, d=0):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:,.{d}f}"


def _print_analysis(o, a):
    lvl = int(a.level * 100)
    print(f"\nDesign: {o['design']}; {len(o['treatment_geos'])} treatment geos, {o['n_controls']} controls; "
          f"pre {o['pre_days']} days, test {o['test_days']} days.")
    for m, f in o["fit"].items():
        flag = "  <- weak fit, treat result with caution" if (f["mape"] > 0.15 or (f["r2"] == f["r2"] and f["r2"] < 0.6)) else ""
        print(f"Pre-period fit {m}: R2 {f['r2']:.2f}, daily MAPE {100*f['mape']:.1f}%{flag}")
    for r in o["results"]:
        print(f"\n[{r['method']}] actual {_fmt(r['actual_total'])} vs counterfactual {_fmt(r['counterfactual_total'])}"
              f" -> effect {_fmt(r['effect'])} ({r['lift_pct']:+.1f}%)")
        if "interval_reported" in r:
            print(f"  {lvl}% interval ({r['interval_basis'].replace('_', '-')} basis): "
                  f"{_fmt(r['interval_reported'][0])} to {_fmt(r['interval_reported'][1])}")
        else:
            print("  No valid interval for this method (too few geos or too little history).")
        for k, v in r.get("wider_checks", {}).items():
            print(f"  Wider check ({k.replace('_', '-')}): {_fmt(v[0])} to {_fmt(v[1])}; mention this uncertainty in the report.")
        if "p_in_time" in r:
            floor = 1 / (1 + r["n_in_time"])
            note = "  (at its floor; windows overlap, so evidence is weaker than the count suggests)" \
                if r["p_in_time"] <= floor + 1e-9 else ""
            print(f"  p (in-time placebo, {r['n_in_time']} overlapping windows): {r['p_in_time']:.3f}{note}")
        if "p_in_space" in r:
            print(f"  p (in-space placebo, {r['n_in_space']} groups): {r['p_in_space']:.3f}")
        m = o["money"][r["method"]]
        unit = "revenue" if o["kpi_type"] == "revenue" else "orders"
        print(f"  Incremental {unit} driven by ads: {_fmt(m['incremental_kpi_driven_by_ads'])} "
              f"[{_fmt(m['incremental_kpi_interval'][0])}, {_fmt(m['incremental_kpi_interval'][1])}]")
        if m.get("cost_per_incremental_order"):
            print(f"  Cost per incremental order: {m['cost_per_incremental_order']:,.2f}")
        if o["kpi_type"] == "orders" and "incremental_revenue" in m:
            print(f"  Incremental revenue (x AOV): {_fmt(m['incremental_revenue'])}")
        if "iroas" in m:
            print(f"  iROAS {m['iroas']:.2f} [{m['iroas_interval'][0]:.2f}, {m['iroas_interval'][1]:.2f}]", end="")
            if "ipoas" in m:
                print(f"; iPOAS {m['ipoas']:.2f} [{m['ipoas_interval'][0]:.2f}, {m['ipoas_interval'][1]:.2f}]"
                      f"; break-even iROAS {m['breakeven_iroas']:.2f}", end="")
            print()
        if "incrementality_factor" in m:
            print(f"  Incrementality factor vs platform-attributed: {m['incrementality_factor']:.2f}")
    e = [r["lift_pct"] for r in o["results"]]
    if abs(e[0] - e[1]) > max(2.0, 0.5 * max(abs(e[0]), abs(e[1]))):
        print("\nNOTE: TBR and synthetic control disagree materially. Report both and investigate fit/shocks.")
    print(f"\nPrimary method: {o['primary']}. Saved {os.path.join(a.out, 'results.json')} and analysis.png")


def _plot_analysis(pre, test, treat, y_pre, y_test, sc_fit, sc_cf, tbr_fit, tbr_cf, primary, a):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    use_sc = primary["method"] == "Synthetic control"
    fit, cf = (sc_fit, sc_cf) if use_sc else (tbr_fit, tbr_cf)
    idx = pre.index.append(test.index)
    actual = np.concatenate([y_pre, y_test])
    model = np.concatenate([fit, cf])
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))
    ax1.plot(idx, actual, label="Actual (treatment geos)", lw=1.3)
    ax1.plot(idx, model, label=f"Counterfactual ({primary['method']})", lw=1.3, ls="--")
    ax1.axvspan(test.index[0], test.index[-1], color="grey", alpha=0.15, label="Test period")
    ax1.set_title("Treatment geos: actual vs counterfactual")
    ax1.legend()
    ax1.grid(alpha=0.3)
    cum = np.cumsum(y_test - cf)
    ax2.plot(test.index, cum, lw=1.5, label="Cumulative effect")
    if "interval_reported" in primary:
        lo, hi = primary["interval_reported"]
        ax2.errorbar([test.index[-1]], [cum[-1]], yerr=[[cum[-1] - lo], [hi - cum[-1]]], fmt="o", color="C3",
                     capsize=6, label=f"Total effect, {int(a.level*100)}% interval")
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_title("Cumulative effect during test (negative = sales lost by removing ads)")
    ax2.legend()
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(a.out, "analysis.png"), dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- cli

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--data", required=True, help="Long CSV: one row per date x geo")
        sp.add_argument("--date-col", default="date")
        sp.add_argument("--geo-col", default="geo")
        sp.add_argument("--kpi-col", default="revenue")
        sp.add_argument("--exclude-geos", default="", help="Comma list of geos to drop (e.g. known outliers)")
        sp.add_argument("--seed", type=int, default=7)
        sp.add_argument("--out", default="geo_out")

    d = sub.add_parser("design", help="Choose treatment geos and estimate MDE from history")
    common(d)
    d.add_argument("--start", help="Use history from this date")
    d.add_argument("--end", help="Use history up to this date")
    d.add_argument("--test-days", type=int, default=28)
    d.add_argument("--treatment-share", type=float, default=0.3, help="Target share of geos/KPI in treatment")
    d.add_argument("--n-candidates", type=int, default=1000)
    d.add_argument("--top", type=int, default=5, help="Candidates refined with synthetic control backtests")
    d.add_argument("--balance-weight", type=float, default=0.05, help="Penalty for KPI share off target")
    d.add_argument("--force-treatment", default="", help="Comma list of geos that must be treatment")
    d.add_argument("--force-control", default="", help="Comma list of geos that must be control (e.g. big metros)")
    d.add_argument("--alpha", type=float, default=0.10, help="Two-sided false-positive rate for MDE")
    d.add_argument("--primary", choices=["sc", "tbr"], default="sc", help="Method you will report in analyze")
    d.set_defaults(func=cmd_design)

    an = sub.add_parser("analyze", help="Estimate the effect of a completed geo test")
    common(an)
    an.add_argument("--treatment-geos", required=True, help="Comma list")
    an.add_argument("--pre-start", required=True)
    an.add_argument("--pre-end", required=True)
    an.add_argument("--test-start", required=True)
    an.add_argument("--test-end", required=True, help="Include the cool-down if lagged effects are expected")
    an.add_argument("--design", choices=["holdout", "heavyup"], required=True,
                    help="holdout/go-dark: ads removed in treatment geos; heavyup: spend added in treatment geos")
    an.add_argument("--spend-change", type=float, default=None,
                    help="Amount of spend removed (holdout) or added (heavy-up) in treatment geos over the test. Positive number.")
    an.add_argument("--kpi-type", choices=["revenue", "orders"], default="revenue")
    an.add_argument("--value-per-unit", type=float, default=None,
                    help="AOV, when --kpi-type orders, to convert incremental orders to revenue for iROAS")
    an.add_argument("--margin", type=float, default=None, help="Gross margin (0-1) for iPOAS")
    an.add_argument("--platform-attributed", type=float, default=None,
                    help="In the same units as the KPI. Platform-attributed value/orders the treated spend normally claims for the same length of time "
                         "(holdout: the treatment geos' attributed value in a comparable pre-period; heavy-up: the "
                         "extra attributed value in treatment geos). Used for the incrementality factor.")
    an.add_argument("--level", type=float, default=0.90, help="Interval level")
    an.add_argument("--n-placebo", type=int, default=300)
    an.add_argument("--n-placebo-sc", type=int, default=60, help="SC in-space placebos (slower)")
    an.add_argument("--primary", choices=["sc", "tbr"], default="sc")
    an.set_defaults(func=cmd_analyze)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
