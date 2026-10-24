#!/usr/bin/env python3
import csv
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.environ.get("NBODY_BIN", os.path.join(HERE, "nbody"))
G = 6.67430e-11


def random_bodies(n, seed, mass=1e10, box=10.0, speed=0.05):
    rnd = random.Random(seed)
    return [(rnd.uniform(0.5, 1.5) * mass, rnd.uniform(-box, box), rnd.uniform(-box, box),
             rnd.uniform(-speed, speed), rnd.uniform(-speed, speed)) for _ in range(n)]


def write_input(path, bodies, columns=5):
    with open(path, "w") as f:
        f.write(f"{len(bodies)}\n")
        for m, x, y, vx, vy in bodies:
            row = (m, x, y, vx, vy) if columns == 5 else (m, x, y, 123.0, vx, vy, -7.0)
            f.write(" ".join(f"{v:.17g}" for v in row) + "\n")


def simulate(bodies, t_end, *opts):
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = os.path.join(tmp, "in.txt"), os.path.join(tmp, "out.csv")
        write_input(inp, bodies, columns=7 if "-7" in opts else 5)
        opts = [o for o in opts if o != "-7"]
        res = subprocess.run([BIN, str(t_end), inp, "-o", out, *map(str, opts)], capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError(res.stderr)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
    n = len(bodies)
    assert rows[0] == ["t"] + [c for i in range(1, n + 1) for c in (f"x{i}", f"y{i}")], rows[0][:5]
    frames = {}
    for r in rows[1:]:
        v = list(map(float, r))
        frames[round(v[0], 9)] = (v[1::2], v[2::2])
    return frames


def reference(bodies, t_end, dt, eps):
    m = [b[0] for b in bodies]
    x, y, vx, vy = ([b[k] for b in bodies] for k in (1, 2, 3, 4))
    n, eps2 = len(bodies), eps * eps
    nsteps = math.ceil(t_end / dt - 1e-9)
    frames = {0.0: (x[:], y[:])}
    for k in range(1, nsteps + 1):
        h = (t_end if k == nsteps else k * dt) - (k - 1) * dt
        fx, fy = [0.0] * n, [0.0] * n
        for i in range(n):
            for j in range(n):
                if i != j:
                    dx, dy = x[j] - x[i], y[j] - y[i]
                    r2 = dx * dx + dy * dy + eps2
                    s = G * m[i] * m[j] / (r2 * math.sqrt(r2))
                    fx[i] += s * dx
                    fy[i] += s * dy
        for i in range(n):
            x[i] += vx[i] * h
            y[i] += vy[i] * h
            vx[i] += fx[i] / m[i] * h
            vy[i] += fy[i] / m[i] * h
        frames[round(t_end if k == nsteps else k * dt, 9)] = (x[:], y[:])
    return frames


def max_rel_diff(a, b):
    scale = max(max(map(abs, ax + ay)) for ax, ay in a.values())
    worst = 0.0
    for t, (bx, by) in b.items():
        ax, ay = a[t]
        worst = max(worst, max(abs(p - q) for p, q in zip(ax + ay, bx + by)))
    return worst / scale


class NBodyTest(unittest.TestCase):
    def test_against_reference(self):
        """Slow but strict: every frame vs an independent pure-Python Euler integrator."""
        cases = [(1, 300, 2.995), (2, 300, 2.995), (3, 300, 2.995), (8, 250, 2.5), (31, 150, 1.5)]
        for n, steps, t_end in cases:
            bodies = random_bodies(n, seed=n)
            dt, eps = t_end / steps, 0.5
            ref = reference(bodies, t_end, dt, eps)
            for mode in ["naive", "local"]:
                for threads in [1, 3, 8, 40]:
                    with self.subTest(n=n, mode=mode, threads=threads):
                        got = simulate(bodies, t_end, "-d", dt, "-e", eps, "-m", mode, "-t", threads,
                                       *(["-7"] if n % 2 else []))
                        self.assertEqual(sorted(got), sorted(ref))
                        self.assertLess(max_rel_diff(ref, got), 1e-9)
            with self.subTest(n=n, every=7):
                got = simulate(bodies, t_end, "-d", dt, "-e", eps, "-t", 4, "-k", 7)
                expected = [t for i, t in enumerate(sorted(ref)) if i % 7 == 0 or i == len(ref) - 1]
                self.assertEqual(sorted(got), expected)
                self.assertLess(max_rel_diff(ref, got), 1e-9)

    def test_invariants_large(self):
        """Fast, scales to large N: centre of mass must move uniformly; naive and local must agree."""
        n = int(os.environ.get("NBODY_CHECK_N", 3000))
        bodies = random_bodies(n, seed=42, box=100.0)
        t_end, dt = 2.0, 0.2
        runs = {(mode, t): simulate(bodies, t_end, "-d", dt, "-e", 0.5, "-m", mode, "-t", t)
                for mode, t in [("naive", 16), ("local", 16), ("local", 7)]}
        mass = sum(b[0] for b in bodies)
        cx0, cy0 = (sum(b[0] * b[k] for b in bodies) / mass for k in (1, 2))
        vcx, vcy = (sum(b[0] * b[k] for b in bodies) / mass for k in (3, 4))
        for (mode, t), frames in runs.items():
            with self.subTest(mode=mode, threads=t, check="centre of mass"):
                for time, (xs, ys) in frames.items():
                    cx = sum(b[0] * p for b, p in zip(bodies, xs)) / mass
                    cy = sum(b[0] * p for b, p in zip(bodies, ys)) / mass
                    self.assertLess(math.hypot(cx - cx0 - vcx * time, cy - cy0 - vcy * time), 1e-9 * 100.0)
        base = runs[("naive", 16)]
        for key in [("local", 16), ("local", 7)]:
            with self.subTest(mode=key[0], threads=key[1], check="naive == local"):
                self.assertLess(max_rel_diff(base, runs[key]), 1e-8)


if __name__ == "__main__":
    if not os.path.exists(BIN):
        sys.exit(f"{BIN} not found, run make first")
    unittest.main(verbosity=2)
