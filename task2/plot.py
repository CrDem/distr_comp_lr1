#!/usr/bin/env python3
import argparse
import csv
import os
import statistics
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, LogLocator

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
BLUE, ORANGE = "#2a78d6", "#eb6834"
MODE_STYLE = {"naive": (BLUE, "o", "naive (без 3-го закона)"), "local": (ORANGE, "s", "local (3-й закон + уголки)")}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10, "axes.titlesize": 11, "legend.frameon": False,
})


def load(path):
    groups = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            key = (r["exp"], r["mode"], int(r["threads"]), int(r["n"]))
            groups[key].append((float(r["compute"]), int(r["steps"])))
    out = {}
    for k, v in groups.items():
        times = [t for t, _ in v]
        out[k] = (statistics.median(times), min(times), max(times), v[0][1])
    return out


def pick(stats, exp, **fixed):
    names = ["exp", "mode", "threads", "n"]
    rows = []
    for k, v in stats.items():
        d = dict(zip(names, k))
        if d["exp"] == exp and all(d[f] == val for f, val in fixed.items()):
            rows.append((d, v))
    return rows


def draw(ax, xs, med, lo, hi, color, marker, label, linestyle="-"):
    ax.errorbar(xs, med, yerr=[[m - l for m, l in zip(med, lo)], [h - m for m, h in zip(med, hi)]],
                color=color, marker=marker, markersize=5, linewidth=2, elinewidth=1, capsize=2,
                linestyle=linestyle, label=label)


def log_axis(axis, subs=(1, 2, 5)):
    axis.set_major_locator(LogLocator(subs=subs))
    axis.set_major_formatter(FormatStrFormatter("%g"))
    axis.set_minor_formatter(FormatStrFormatter(""))


def mark_cores(ax):
    for x, text in [(8, "8 ядер"), (16, "16 потоков SMT")]:
        ax.axvline(x, color=MUTED, linewidth=1, linestyle=":")
        ax.annotate(text, (x, 1), xycoords=("data", "axes fraction"), xytext=(3, -12),
                    textcoords="offset points", color=MUTED, fontsize=8)


def series(rows, xkey):
    rows = sorted(rows, key=lambda r: r[0][xkey])
    return ([r[0][xkey] for r in rows], [r[1][0] for r in rows], [r[1][1] for r in rows],
            [r[1][2] for r in rows], [r[1][3] for r in rows])


def plot_threads(stats):
    sizes = sorted({k[3] for k in stats if k[0] == "threads"})
    fig, axes = plt.subplots(len(sizes), 2, figsize=(12, 4.5 * len(sizes)), squeeze=False)
    for row, n in zip(axes, sizes):
        ax_t, ax_s = row
        base = pick(stats, "threads", mode="naive", threads=1, n=n)[0][1][0]
        steps = None
        for mode, (color, marker, label) in MODE_STYLE.items():
            xs, med, lo, hi, st = series(pick(stats, "threads", mode=mode, n=n), "threads")
            steps = st[0]
            draw(ax_t, xs, med, lo, hi, color, marker, label)
            draw(ax_s, xs, [base / m for m in med], [base / m for m in med], [base / m for m in med],
                 color, marker, label)
        top = max(xs)
        ax_s.plot([1, top], [2, 2 * top], color=MUTED, linestyle="--", linewidth=1)
        ax_s.plot([1, top], [1, top], color=MUTED, linestyle=":", linewidth=1)
        ax_s.annotate("идеальное для local (×2·p)", (3.0, 7.6), xytext=(-9, 3), textcoords="offset points", color=MUTED, fontsize=8, rotation=64)
        ax_s.annotate("идеальное для naive (×p)", (11.2, 12.4), xytext=(-9, 5), textcoords="offset points", color=MUTED, fontsize=8, rotation=46)
        ax_t.set(title=f"Время, N = {n}, {steps} шагов", xlabel="потоки", ylabel="время, с (медиана; min–max)",
                 yscale="log")
        log_axis(ax_t.yaxis)
        ax_s.set(title=f"Ускорение относительно naive на 1 потоке, N = {n}", xlabel="потоки",
                 ylabel="ускорение", ylim=(0, 20))
        for ax in row:
            mark_cores(ax)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def plot_size(stats):
    fig, (ax_t, ax_r) = plt.subplots(1, 2, figsize=(12, 4.8))
    for mode, (color, marker, label) in MODE_STYLE.items():
        for t, ls in [(1, "--"), (16, "-")]:
            xs, med, lo, hi, st = series(pick(stats, "size", mode=mode, threads=t), "n")
            per_step = lambda vals: [v / s * 1e3 for v, s in zip(vals, st)]
            draw(ax_t, xs, per_step(med), per_step(lo), per_step(hi), color, marker,
                 f"{mode}, {t} поток" + ("" if t == 1 else "ов"), linestyle=ls)
    ax_t.set(title="Время одного шага", xlabel="N (число тел)", ylabel="мс на шаг",
             xscale="log", yscale="log")
    log_axis(ax_t.yaxis)
    ax_t.legend(loc="upper left")
    for t, ls in [(1, "--"), (16, "-")]:
        xs, naive, _, _, _ = series(pick(stats, "size", mode="naive", threads=t), "n")
        _, local, _, _, _ = series(pick(stats, "size", mode="local", threads=t), "n")
        ax_r.plot(xs, [a / b for a, b in zip(naive, local)], color=ORANGE, marker="s", markersize=5,
                  linewidth=2, linestyle=ls, label=f"{t} поток" + ("" if t == 1 else "ов"))
    ax_r.axhline(2, color=MUTED, linestyle=":", linewidth=1)
    ax_r.axhline(1, color=MUTED, linestyle=":", linewidth=1)
    ax_r.annotate("теоретический предел ×2", (xs[0], 2), xytext=(0, 4), textcoords="offset points",
                  color=MUTED, fontsize=8)
    ax_r.set(title="Выигрыш от 3-го закона: T(naive) / T(local)", xlabel="N (число тел)", ylabel="раз",
             xscale="log", ylim=(0, 2.5))
    ax_r.legend(loc="lower right")
    fig.tight_layout()
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "bench.csv"))
    args = ap.parse_args()
    stats = load(args.data)
    exps = {k[0] for k in stats}
    figs = {}
    if "threads" in exps:
        figs["threads.png"] = plot_threads(stats)
    if "size" in exps:
        figs["size.png"] = plot_size(stats)
    for name, fig in figs.items():
        path = os.path.join(RESULTS, name)
        fig.savefig(path, dpi=130)
        print("saved", path)


if __name__ == "__main__":
    main()
