#!/usr/bin/env python3
import argparse
import csv
import os
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "mandelbrot")
RESULTS = os.path.join(HERE, "results")
MODES = ["static", "mutex", "spin", "atomic", "dynamic"]
THREADS = [1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]
FIELDS = ["exp", "mode", "threads", "points", "max_iter", "shortcut", "chunk", "rep", "compute"]


def experiments(quick):
    scale = 10 if quick else 1
    threads = [1, 2, 4, 8, 16, 32] if quick else THREADS
    for kind, opts in [("heavy", []), ("light", ["-s"])]:
        for mode in MODES:
            for t in threads:
                yield f"threads_{kind}", [t, 1_000_000 // scale, "-m", mode, *opts]
        for mode in MODES:
            for n in [10**k for k in range(2, 8 if not quick else 6)]:
                yield f"points_{kind}", [16, n, "-m", mode, *opts]
    for chunk in [1, 4, 16, 64, 256, 1024, 4096, 16384, 65536]:
        yield "chunk_light", [16, 1_000_000 // scale, "-m", "dynamic", "-s", "-b", chunk]


def run_once(args):
    out = subprocess.run([BIN, *map(str, args), "-n"], capture_output=True, text=True, check=True)
    return dict(kv.split("=") for kv in out.stdout.split())


def machine_info():
    lines = [f"platform: {platform.platform()}", f"nproc: {os.cpu_count()}"]
    lscpu = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
    keep = ("Model name", "Thread(s) per core", "Core(s) per socket", "CPU max MHz", "L2", "L3")
    lines += [l.strip() for l in lscpu.splitlines() if l.strip().startswith(keep)]
    lines.append(subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0])
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--quick", action="store_true", help="smaller sizes for a fast sanity run")
    ap.add_argument("--only", help="comma-separated experiment prefixes, e.g. threads_light,chunk")
    args = ap.parse_args()

    exps = list(experiments(args.quick))
    if args.only:
        exps = [e for e in exps if e[0].startswith(tuple(args.only.split(",")))]
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "machine.txt"), "w") as f:
        f.write(machine_info())

    total = len(exps) * args.reps
    with open(os.path.join(RESULTS, "bench.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        done = 0
        for rep in range(args.reps):
            for exp, cmd in exps:
                r = run_once(cmd)
                writer.writerow({"exp": exp, "mode": r["mode"], "threads": r["threads"],
                                 "points": r["points"], "max_iter": r["max_iter"],
                                 "shortcut": r["shortcut"], "chunk": r["chunk"],
                                 "rep": rep, "compute": r["compute"]})
                done += 1
                print(f"\r[{done}/{total}] {exp:14} {' '.join(map(str, cmd)):40} {r['compute']}s",
                      end="", flush=True)
            f.flush()
    print(f"\nsaved {os.path.join(RESULTS, 'bench.csv')}")


if __name__ == "__main__":
    main()
