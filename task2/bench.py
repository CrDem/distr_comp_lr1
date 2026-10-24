#!/usr/bin/env python3
import argparse
import csv
import os
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "nbody")
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
THREADS = [1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]
FIELDS = ["exp", "mode", "threads", "n", "steps", "rep", "compute"]


def steps_for(n):
    return max(3, min(2000, round(1e8 / (n * n))))


def experiments(quick):
    threads = [1, 2, 4, 8, 16, 32] if quick else THREADS
    for n, steps in ([(500, 40), (2000, 6)] if quick else [(500, 200), (2000, 30)]):
        for mode in ["naive", "local"]:
            for t in threads:
                yield "threads", mode, t, n, steps
    sizes = [100, 500, 2000] if quick else [100, 200, 500, 1000, 2000, 5000, 10000]
    for n in sizes:
        for mode in ["naive", "local"]:
            for t in [1, 16]:
                yield "size", mode, t, n, max(1, steps_for(n) // (10 if quick else 1))


def input_file(n):
    path = os.path.join(DATA, f"bench_{n}.txt")
    if not os.path.exists(path):
        subprocess.run(["python3", os.path.join(HERE, "gen.py"), "cloud", str(n), "-o", path],
                       check=True, capture_output=True)
    return path


def run_once(mode, t, n, steps):
    dt = 0.1
    cmd = [BIN, str(steps * dt), input_file(n), "-d", str(dt), "-e", "0.1", "-m", mode, "-t", str(t), "-n"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return dict(kv.split("=") for kv in out.split())


def machine_info():
    lines = [f"platform: {platform.platform()}", f"nproc: {os.cpu_count()}"]
    lscpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
    keep = ("Model name", "Thread(s) per core", "Core(s) per socket", "L2", "L3")
    lines += [l.strip() for l in lscpu.splitlines() if l.strip().startswith(keep)]
    lines.append(subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0])
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", help="comma-separated experiments: threads,size")
    args = ap.parse_args()

    exps = list(experiments(args.quick))
    if args.only:
        exps = [e for e in exps if e[0] in args.only.split(",")]
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "machine.txt"), "w") as f:
        f.write(machine_info())

    total, done = len(exps) * args.reps, 0
    with open(os.path.join(RESULTS, "bench.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for rep in range(args.reps):
            for exp, mode, t, n, steps in exps:
                r = run_once(mode, t, n, steps)
                writer.writerow({"exp": exp, "mode": mode, "threads": t, "n": n,
                                 "steps": r["steps"], "rep": rep, "compute": r["compute"]})
                done += 1
                print(f"\r[{done}/{total}] {exp:8} {mode:5} t={t:<3} n={n:<6} {r['compute']}s   ",
                      end="", flush=True)
            f.flush()
    print(f"\nsaved {os.path.join(RESULTS, 'bench.csv')}")


if __name__ == "__main__":
    main()
