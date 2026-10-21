#!/usr/bin/env python3
"""Render OpenSEO get_local_rank_grid results as a colour-coded grid image for client reports.

Usage:
  python3 grid_map.py --grid grid1.json [--grid grid2.json ...] --business "Acme Plumbing" --out grid.png
  (each grid file = the JSON returned by get_local_rank_grid; the keyword is taken from --labels or the file name)
  Optional: --labels "gutter installation,gutter repair"  --compare before.json  (shows before vs after)

Colours: 1-3 green, 4-10 amber, 11-20 red, not found grey. The centre cell is outlined.
"""
import argparse
import json
import math
import os
import sys


def load(path):
    with open(path) as f:
        d = json.load(f)
    if "grid" not in d:
        sys.exit(f"{path}: no 'grid' key (expected get_local_rank_grid output)")
    return d


def colour(rank):
    if rank is None:
        return "#c9ccd1"
    if rank <= 3:
        return "#2e9e5b"
    if rank <= 10:
        return "#f0b429"
    return "#d64545"


def draw(ax, d, title):
    cells = d["grid"]
    n = int(math.isqrt(len(cells)))
    for c in cells:
        r, k = c["row"], c["col"]
        rank = c.get("rank")
        ax.add_patch(__import__("matplotlib").patches.Rectangle((k, n - 1 - r), 0.94, 0.94, color=colour(rank)))
        ax.text(k + 0.47, n - 1 - r + 0.47, "–" if rank is None else str(rank), ha="center", va="center",
                fontsize=16 if n <= 3 else 12, color="white" if rank is not None else "#444", weight="bold")
    mid = n // 2
    ax.add_patch(__import__("matplotlib").patches.Rectangle((mid - 0.02, n - 1 - mid - 0.02), 0.98, 0.98,
                                                            fill=False, lw=2.5, ec="#222"))
    s = d.get("summary", {})
    found = s.get("pointsFound", sum(1 for c in cells if c.get("rank") is not None))
    top3 = s.get("top3Count", sum(1 for c in cells if c.get("rank") and c["rank"] <= 3))
    avg = s.get("averageRank")
    sub = f"found in {found}/{len(cells)} points · top 3 in {top3}" + (f" · avg rank {avg:.1f}" if avg else "")
    ax.set_title(f"{title}\n{sub}", fontsize=11)
    ax.set_xlim(-0.1, n)
    ax.set_ylim(-0.1, n)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grid", action="append", required=True, help="Grid JSON file (repeat for several keywords)")
    p.add_argument("--labels", default="", help="Comma list of keyword labels, same order as --grid")
    p.add_argument("--compare", action="append", default=[], help="Earlier grid JSON files, same order, for before/after")
    p.add_argument("--business", default="", help="Business name for the figure title")
    p.add_argument("--out", default="grid.png")
    a = p.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    grids = [load(g) for g in a.grid]
    labels = [s.strip() for s in a.labels.split(",")] if a.labels else [os.path.splitext(os.path.basename(g))[0] for g in a.grid]
    before = [load(g) for g in a.compare]
    rows = 2 if before else 1
    cols = len(grids)
    fig, axes = plt.subplots(rows, cols, figsize=(max(3.6 * cols, 6.4), 3.9 * rows + 0.9), squeeze=False)
    for i, g in enumerate(grids):
        draw(axes[rows - 1][i], g, labels[i] + (" (now)" if before else ""))
        if before and i < len(before):
            draw(axes[0][i], before[i], labels[i] + " (before)")
        elif before:
            axes[0][i].axis("off")
    fig.legend(handles=[Patch(color="#2e9e5b", label="1–3"), Patch(color="#f0b429", label="4–10"),
                        Patch(color="#d64545", label="11–20"), Patch(color="#c9ccd1", label="not in top 20")],
               loc="lower center", ncol=4, frameon=False)
    fig.suptitle(f"Google Maps rankings{(' · ' + a.business) if a.business else ''}\n(outlined centre = business location)",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    fig.savefig(a.out, dpi=150)
    print(f"Saved {a.out}")


if __name__ == "__main__":
    main()
