#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "mandelbrot")
MODES = ["static", "mutex", "spin", "atomic", "dynamic"]
MAX_ITER = 200


def in_set(cx, cy, max_iter):
    x = y = 0.0
    for _ in range(max_iter):
        x, y = x * x - y * y + cx, 2 * x * y + cy
        if x * x + y * y > 4.0:
            return False
    return True


def run(*args):
    return subprocess.run([BIN, *map(str, args)], capture_output=True, text=True)


def generate(nthreads, npoints, *opts):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out.csv")
        res = run(nthreads, npoints, "-o", out, *opts)
        if res.returncode != 0:
            raise AssertionError(res.stderr)
        with open(out, newline="") as f:
            rows = list(csv.reader(f))
    return rows[0], [(float(x), float(y)) for x, y in rows[1:]]


class MandelbrotTest(unittest.TestCase):
    def check_points(self, nthreads, npoints, mode, *opts):
        header, pts = generate(nthreads, npoints, "-m", mode, "-i", MAX_ITER, *opts)
        self.assertEqual(header, ["x", "y"])
        self.assertEqual(len(pts), npoints)
        self.assertEqual(len(set(pts)), npoints, "duplicate or unwritten slots")
        for x, y in pts:
            self.assertTrue(-2.0 <= x <= 0.5 and -1.25 <= y <= 1.25, (x, y))
            self.assertTrue(in_set(x, y, MAX_ITER), (x, y))

    def test_all_modes(self):
        for mode in MODES:
            for nthreads, npoints in [(1, 1), (3, 7), (4, 1000), (16, 2000), (32, 5)]:
                with self.subTest(mode=mode, nthreads=nthreads, npoints=npoints):
                    self.check_points(nthreads, npoints, mode)

    def test_shortcut(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.check_points(8, 2000, mode, "-s")

    def test_small_chunks(self):
        for chunk in [1, 3, 5000]:
            with self.subTest(chunk=chunk):
                self.check_points(6, 1000, "dynamic", "-b", chunk)

    def test_static_is_deterministic(self):
        a = generate(4, 500, "-m", "static", "-i", MAX_ITER)
        b = generate(4, 500, "-m", "static", "-i", MAX_ITER)
        self.assertEqual(a, b)

    def test_bad_args(self):
        for args in [[], [4], [0, 10], [4, 0], [4, 10, "-m", "nope"], [4, 10, "-b", 0]]:
            with self.subTest(args=args):
                self.assertNotEqual(run(*args).returncode, 0)


if __name__ == "__main__":
    if not os.path.exists(BIN):
        sys.exit(f"{BIN} not found, run make first")
    unittest.main(verbosity=2)
