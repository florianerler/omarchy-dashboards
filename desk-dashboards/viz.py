#!/usr/bin/env python3
"""LORENZ - rotierender Lorenz-Attraktor aus Braille-Punkten; Schweif verblasst in Theme-Farben."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collections import deque
from common import Canvas, sty, run, col, CYAN, BLUE, MAGENTA, RED, YELLOW

TRAIL = 2600
state = [1.0, 1.0, 1.0]
trail = deque(maxlen=TRAIL)
t_last = [None]


def advance(n):
    x, y, z = state
    dt = 0.006
    for _ in range(n):
        dx, dy, dz = 10 * (y - x), x * (28 - z) - y, x * y - 8 / 3 * z
        x, y, z = x + dx * dt, y + dy * dt, z + dz * dt
        trail.append((x, y, z))
    state[:] = [x, y, z]

advance(2400)   # Schweif von Anfang an gefüllt


def frame(cols, rows, t):
    advance(14)
    cv = Canvas(cols, max(1, rows - 1))
    a, tilt = t * 0.35, 0.35 + 0.25 * math.sin(t * 0.21)
    ca, sa, ct, st = math.cos(a), math.sin(a), math.cos(tilt), math.sin(tilt)
    scale = min(cv.W / 50, cv.H / 62)
    n = len(trail)
    palette = (RED, MAGENTA, BLUE, CYAN)
    for i, (x, y, z) in enumerate(trail):
        xr, dr = x * ca - y * sa, x * sa + y * ca       # Drehung um die z-Achse
        v = -(z - 25) * ct + dr * st                    # z zeigt nach oben, leichte Kippung
        age = i / n                                      # 0 = alt, 1 = neu
        s = sty(palette[min(3, int(age * 4))], bold=age > 0.85, dim=age < 0.3)
        cv.set(cv.W / 2 + xr * scale, cv.H / 2 + v * scale, s)
    lines = list(cv.rows())
    lines.append(col(7, " LORENZ  σ=10 ρ=28 β=8/3", dim=True))
    return lines


if __name__ == "__main__":
    run(frame, fps=24)
