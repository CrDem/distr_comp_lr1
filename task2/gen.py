#!/usr/bin/env python3
import argparse
import math
import os
import random

G = 6.67430e-11


def two():
    m, r = 1e10, 1.0
    v = math.sqrt(G * m / (4 * r))
    bodies = [(m, -r, 0.0, 0.0, -v), (m, r, 0.0, 0.0, v)]
    return bodies, "./nbody 40 {f} -d 0.001 -k 10"


def solar():
    sun = 1.989e30
    planets = [  # mass, semi-major axis (m)
        (3.30e23, 5.79e10), (4.87e24, 1.082e11), (5.97e24, 1.496e11), (6.42e23, 2.279e11),
        (1.898e27, 7.785e11), (5.68e26, 1.4335e12), (8.68e25, 2.8725e12), (1.02e26, 4.4951e12),
    ]
    bodies = [(sun, 0.0, 0.0, 0.0, 0.0)]
    for mass, a in planets:
        phi = random.uniform(0, 2 * math.pi)
        v = math.sqrt(G * sun / a)
        bodies.append((mass, a * math.cos(phi), a * math.sin(phi), -v * math.sin(phi), v * math.cos(phi)))
    return bodies, "./nbody 3.156e8 {f} -d 3600 -k 48"


def disk(n, cx=0.0, cy=0.0, cvx=0.0, cvy=0.0, mc=1e10, rmin=1.0, rmax=4.0, spin=1):
    bodies = [(mc, cx, cy, cvx, cvy)]
    md = 0.05 * mc / max(n, 1)
    for _ in range(n):
        r = math.sqrt(random.uniform(rmin * rmin, rmax * rmax))
        phi = random.uniform(0, 2 * math.pi)
        v = spin * math.sqrt(G * mc / r)
        bodies.append((md, cx + r * math.cos(phi), cy + r * math.sin(phi),
                       cvx - v * math.sin(phi), cvy + v * math.cos(phi)))
    return bodies


def galaxy(n):
    return disk(n), "./nbody 60 {f} -d 0.002 -e 0.05 -k 10"


def galaxies(n):
    a = disk(n // 2, -8.0, -2.0, 0.12, 0.0)
    b = disk(n - n // 2, 8.0, 2.0, -0.12, 0.0, spin=-1)
    return a + b, "./nbody 200 {f} -d 0.002 -e 0.1 -k 50"


def cloud(n):
    bodies = [(random.uniform(0.5e8, 1.5e8), random.uniform(-10, 10), random.uniform(-10, 10),
               random.uniform(-1e-3, 1e-3), random.uniform(-1e-3, 1e-3)) for _ in range(n)]
    return bodies, "./nbody 100 {f} -d 0.1 -e 0.1 -k 5"


PRESETS = {"two": two, "solar": solar, "galaxy": galaxy, "galaxies": galaxies, "cloud": cloud}


def write(path, bodies):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(f"{len(bodies)}\n")
        for b in bodies:
            f.write(" ".join(f"{v:.17g}" for v in b) + "\n")


def main():
    ap = argparse.ArgumentParser(description="generate nbody input files (m x y vx vy per line)")
    ap.add_argument("preset", choices=PRESETS)
    ap.add_argument("n", type=int, nargs="?", default=1000, help="body count for galaxy/galaxies/cloud")
    ap.add_argument("-o", "--out", help="output file (default data/<preset>.txt)")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    random.seed(args.seed)
    fn = PRESETS[args.preset]
    bodies, cmd = fn(args.n) if args.preset in ("galaxy", "galaxies", "cloud") else fn()
    out = args.out or os.path.join("data", f"{args.preset}.txt")
    write(out, bodies)
    print(f"{out}: {len(bodies)} bodies")
    print("suggested run:", cmd.format(f=out), "-o", os.path.splitext(os.path.basename(out))[0] + ".csv")


if __name__ == "__main__":
    main()
