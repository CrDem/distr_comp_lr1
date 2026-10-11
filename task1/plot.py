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
MODES = ["static", "mutex", "spin", "atomic", "dynamic"]
COLORS = dict(zip(MODES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
MARKERS = dict(zip(MODES, ["o", "s", "^", "D", "v"]))
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
PHYS_CORES, LOGICAL_CORES = 8, 16

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
            key = (r["exp"], r["mode"], int(r["threads"]), int(r["points"]), int(r["chunk"]))
            groups[key].append(float(r["compute"]))
    return {k: (statistics.median(v), min(v), max(v)) for k, v in groups.items()}


def series(stats, exp, mode, x_index):
    rows = sorted((k[x_index], v) for k, v in stats.items() if k[0] == exp and k[1] == mode)
    xs = [x for x, _ in rows]
    med = [v[0] for _, v in rows]
    err = [[v[0] - v[1] for _, v in rows], [v[2] - v[0] for _, v in rows]]
    return xs, med, err


def draw(ax, xs, ys, mode, err=None):
    ax.errorbar(xs, ys, yerr=err, color=COLORS[mode], marker=MARKERS[mode], markersize=5,
                linewidth=2, elinewidth=1, capsize=2, label=mode)


def log_axis(axis, subs=(1, 2, 5)):
    axis.set_major_locator(LogLocator(subs=subs))
    axis.set_major_formatter(FormatStrFormatter("%g"))
    axis.set_minor_formatter(FormatStrFormatter(""))


def mark_cores(ax):
    for x, text in [(PHYS_CORES, "8 ядер"), (LOGICAL_CORES, "16 потоков SMT")]:
        ax.axvline(x, color=MUTED, linewidth=1, linestyle=":")
        ax.annotate(text, (x, 1), xycoords=("data", "axes fraction"), xytext=(3, -12),
                    textcoords="offset points", color=MUTED, fontsize=8)


def plot_threads(stats):
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for row, kind in enumerate(["heavy", "light"]):
        exp = f"threads_{kind}"
        t1 = next(v[0] for k, v in stats.items() if k[0] == exp and k[1] == "static" and k[2] == 1)
        ax_t, ax_s = axes[row]
        for mode in MODES:
            xs, med, err = series(stats, exp, mode, 2)
            if not xs:
                continue
            draw(ax_t, xs, med, mode, err)
            draw(ax_s, xs, [t1 / m for m in med], mode)
        top = max(k[2] for k in stats if k[0] == exp)
        ax_s.plot([1, top], [1, top], color=MUTED, linestyle="--", linewidth=1)
        ax_s.annotate("идеальное", (11, 13.5), color=MUTED, fontsize=8, rotation=38)
        label = "тяжёлая проверка" if kind == "heavy" else "лёгкая проверка (-s)"
        ax_t.set(title=f"Время, {label}", xlabel="потоки", ylabel="время, с (медиана; min–max)",
                 yscale="log")
        log_axis(ax_t.yaxis)
        ax_s.set(title=f"Ускорение T(static, 1) / T, {label}", xlabel="потоки", ylabel="ускорение",
                 ylim=(0, 19))
        for ax in (ax_t, ax_s):
            mark_cores(ax)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(MODES), bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def plot_points(stats):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, kind in zip(axes, ["heavy", "light"]):
        for mode in MODES:
            xs, med, err = series(stats, f"points_{kind}", mode, 3)
            if xs:
                draw(ax, xs, med, mode, err)
        label = "тяжёлая проверка" if kind == "heavy" else "лёгкая проверка (-s)"
        ax.set(title=f"16 потоков, {label}", xlabel="число точек", ylabel="время, с",
               xscale="log", yscale="log")
        log_axis(ax.yaxis)
        ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


def plot_chunk(stats):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    xs, med, err = series(stats, "chunk_light", "dynamic", 4)
    draw(ax, xs, med, "dynamic", err)
    points = next(k[3] for k in stats if k[0] == "chunk_light")
    for mode in ["static", "mutex", "atomic"]:
        ref = stats.get(("threads_light", mode, 16, points, 1024))
        if ref:
            ax.axhline(ref[0], color=COLORS[mode], linestyle="--", linewidth=1.2, label=f"{mode} (16 потоков)")
    npts = f"{points:,}".replace(",", " ")
    ax.set(title=f"dynamic: размер порции (16 потоков, {npts} точек, -s)",
           xlabel="chunk (точек за один захват мьютекса)", ylabel="время, с", xscale="log", yscale="log")
    log_axis(ax.yaxis, subs=(1, 1.5, 2, 3, 5, 7))
    ax.legend(loc="upper right", bbox_to_anchor=(1, 0.92))
    fig.tight_layout()
    return fig


def plot_set(csv_path, limit=200_000):
    xs, ys = [], []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for i, (x, y) in enumerate(reader):
            if i >= limit:
                break
            xs.append(float(x))
            ys.append(float(y))
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(xs, ys, s=0.2, color=COLORS["static"], linewidths=0)
    ax.set(title=f"{len(xs):,} точек множества Мандельброта".replace(",", " "),
           xlabel="Re c", ylabel="Im c", xlim=(-2, 0.5), ylim=(-1.25, 1.25), aspect="equal")
    ax.grid(False)
    fig.tight_layout()
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(RESULTS, "bench.csv"))
    ap.add_argument("--set", metavar="CSV", help="also draw points from mandelbrot output")
    args = ap.parse_args()

    stats = load(args.data)
    exps = {k[0] for k in stats}
    figs = {}
    if {"threads_heavy", "threads_light"} <= exps:
        figs["threads.png"] = plot_threads(stats)
    if {"points_heavy", "points_light"} <= exps:
        figs["points.png"] = plot_points(stats)
    if "chunk_light" in exps:
        figs["chunk.png"] = plot_chunk(stats)
    if args.set:
        figs["set.png"] = plot_set(args.set)
    for name, fig in figs.items():
        path = os.path.join(RESULTS, name)
        fig.savefig(path, dpi=130)
        print("saved", path)


if __name__ == "__main__":
    main()
