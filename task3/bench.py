#!/usr/bin/env python3
import csv
import os
import re
import statistics
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
BINARIES = {"pthread_rwlock": "ll_pthread", "my_rwlock": "ll_my"}
MIXES = {"99.9% поиск": (0.999, 0.0005), "80% поиск, 10% вставка, 10% удаление": (0.8, 0.1)}
THREADS = [1, 2, 4, 8, 16]
KEYS, OPS, REPS = 1000, 100000, 5


def run(binary, threads, search, insert):
    stdin = f"{KEYS}\n{OPS}\n{search}\n{insert}\n"
    out = subprocess.run([os.path.join(HERE, binary), str(threads)], input=stdin,
                         capture_output=True, text=True, check=True).stdout
    return float(re.search(r"Elapsed time = (\S+)", out).group(1))


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for rep in range(REPS):
        for mix, (search, insert) in MIXES.items():
            for t in THREADS:
                for impl, binary in BINARIES.items():
                    rows.append((mix, impl, t, rep, run(binary, t, search, insert)))
                    print(f"\r[{len(rows)}/{REPS * len(MIXES) * len(THREADS) * len(BINARIES)}]", end="", flush=True)
    print()
    with open(os.path.join(RESULTS, "bench.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mix", "impl", "threads", "rep", "time"])
        w.writerows(rows)

    med = {}
    for mix, impl, t, _, time in rows:
        med.setdefault((mix, impl, t), []).append(time)
    med = {k: statistics.median(v) for k, v in med.items()}

    fig, axes = plt.subplots(1, len(MIXES), figsize=(12, 4.5))
    for ax, mix in zip(axes, MIXES):
        print(f"\n{mix} (медиана из {REPS}, с)")
        print(f"{'потоки':>7} {'pthread':>10} {'my':>10} {'my/pthread':>11}")
        for t in THREADS:
            a, b = med[(mix, "pthread_rwlock", t)], med[(mix, "my_rwlock", t)]
            print(f"{t:>7} {a:>10.4f} {b:>10.4f} {b / a:>11.2f}")
        for impl, color, marker in [("pthread_rwlock", "#2a78d6", "o"), ("my_rwlock", "#eb6834", "s")]:
            ax.plot(THREADS, [med[(mix, impl, t)] for t in THREADS], color=color, marker=marker,
                    linewidth=2, label=impl)
        ax.set(title=mix, xlabel="потоки", ylabel="время, с (медиана)", xticks=THREADS)
        ax.set_ylim(bottom=0)
        ax.grid(True, color="#e4e3df")
        ax.legend(frameon=False)
    fig.suptitle(f"Список: {KEYS} ключей в начале, {OPS} операций")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "rwlock.png"), dpi=130)
    print(f"\nsaved {os.path.join(RESULTS, 'rwlock.png')}")


if __name__ == "__main__":
    main()
