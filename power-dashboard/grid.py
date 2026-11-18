#!/usr/bin/env python3
"""HAUSANSCHLUSS - Terminal-Dashboard fuer den Shelly Pro 3EM.

Neun Zeigerinstrumente (Spannung, Strom, Wirkleistung je Phase L1-L3), darunter eine Tabelle mit
allen Werten (U, I, P, S, Q, PF, f) und der Verlauf der Gesamtleistung. Optik und Farben wie dashboard.py
(nur ANSI-Indexfarben -> folgt dem Omarchy-Theme).

Start:  python3 -I grid.py        (Beenden mit q)
Test:   python3 -I grid.py --once [--cols 120 --rows 40]
"""
import argparse, math, os, select, shutil, sys, termios, time, tty
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard import (Gauge, Canvas, sty, col, vlen, clip, render_screen, pick_scale,  # noqa: E402
                       RED, GREEN, YELLOW, CYAN, MAGENTA, FPS, HISTORY)
from shelly import Poller, fetch, host  # noqa: E402

PH_COL = (YELLOW, CYAN, MAGENTA)     # L1/L2/L3 in drei Farben, ueber die Theme-Palette
U_ZONES = [(0.117, RED), (0.883, GREEN), (1, RED)]      # 200..260 V, gruen = 207..253 V (+-10 %)
I_MAX = 63          # feste Skala 0..63 A (Hausanschluss), gelb ab ~70 %, rot ab ~90 %
P_SCALES = (500, 1000, 2500, 5000, 10000, 25000)


class Grid:
    def __init__(self):
        self.gu = [Gauge(f"L{n + 1} SPANNUNG", "V", 200, 260, U_ZONES, 1) for n in range(3)]
        self.gi = [Gauge(f"L{n + 1} STROM", "A", 0, I_MAX, [(0.7, GREEN), (0.9, YELLOW), (1, RED)], 2) for n in range(3)]
        self.gp = [Gauge(f"L{n + 1} LEISTUNG", "W", 0, 1000, [(0.6, GREEN), (0.85, YELLOW), (1, RED)], 0) for n in range(3)]
        self.gauges = self.gu + self.gi + self.gp
        self.hist = deque(maxlen=HISTORY)
        self.s = None
        self.err = None

    def update(self, s):
        self.s = s
        self.hist.append(s["total"]["p"])
        for n, ph in enumerate(s["phases"]):
            self.gu[n].target = ph["u"]
            self.gi[n].target = ph["i"]
            g = self.gp[n]
            g.target = abs(ph["p"])
            g.hi = pick_scale(abs(ph["p"]), P_SCALES)
            feed = ph["p"] < -1
            g.zones = [(1, GREEN)] if feed else [(0.6, GREEN), (0.85, YELLOW), (1, RED)]
            g.caption = col(GREEN, "Einspeisung") if feed else ""

    def settle(self):
        for g in self.gauges:
            g.shown = g.target

    def step(self, dt):
        for g in self.gauges:
            g.step(dt)

    def sparkline(self, width):
        data = list(self.hist)[-width:]
        top = max(max((abs(v) for v in data), default=1.0), 1.0)
        bars = " ▁▂▃▄▅▆▇█"
        return "".join(col(GREEN if v < 0 else CYAN, bars[min(8, int(abs(v) / top * 8 + 0.5))]) for v in data)

    TW = 9   # Spaltenbreite der Tabelle

    def wave(self, width, height):
        """Drehstrom: drei um 120 Grad versetzte Sinuswellen, die nach rechts durchlaufen."""
        cv = Canvas(width, height)
        mid, amp = (cv.H - 1) / 2, (cv.H - 1) / 2 - 1
        ph0 = time.time() * 2 * math.pi * 0.5      # 0,5 Umdrehungen/s - echte 50 Hz waeren nur ein Flimmern
        for x in range(0, cv.W, 2):
            cv.set(x, mid, sty(7, dim=True))
        for n in range(3):
            st = sty(PH_COL[n], bold=True)
            for x in range(cv.W):
                a = 2 * math.pi * 2.0 * x / cv.W - ph0 - n * 2 * math.pi / 3
                cv.set(x, mid - amp * math.sin(a), st)
        return list(cv.rows())

    def table(self, cols):
        s = self.s
        hdr = ["", "U/V", "I/A", "P/W", "S/VA", "Q/var", "PF", "f/Hz"]
        w = self.TW
        row = lambda cells, style=None: "".join(
            (col(7, c.rjust(w) if i else c.ljust(4), dim=True, bold=False) if style == "h" else
             (c.rjust(w) if i else c.ljust(4))) for i, c in enumerate(cells))
        out = [row(hdr, "h")]
        for n, ph in enumerate(s["phases"]):
            cells = [f"L{n + 1}", f"{ph['u']:.1f}", f"{ph['i']:.3f}", f"{ph['p']:.1f}", f"{ph['s']:.1f}",
                     f"{ph['q']:.1f}", f"{ph['pf']:.2f}", f"{ph['f']:.1f}"]
            out.append(col(PH_COL[n], cells[0].ljust(4), bold=True) + row(cells)[4:])
        t = s["total"]
        cells = ["Σ", "", f"{t['i']:.3f}", f"{t['p']:.1f}", f"{t['s']:.1f}", f"{t['q']:.1f}", f"{t['pf']:.2f}", ""]
        out.append(col(7, "Σ".ljust(4), bold=True) + col(7, row(cells)[4:], bold=True))
        return out

    def frame(self, cols, rows):
        out = []
        now = time.strftime("%H:%M:%S")
        title = col(CYAN, "▌HAUSANSCHLUSS", bold=True)
        if self.s:
            p = self.s["total"]["p"]
            title += col(7, "  ·  ", dim=True) + (col(GREEN, f"▼ Einspeisung {-p:.0f} W", bold=True) if p < -1
                                                  else col(YELLOW, f"▲ Bezug {p:.0f} W", bold=True))
        if self.err:
            title += col(7, "  ·  ", dim=True) + col(RED, "Messfehler: " + self.err, bold=True)
        out.append(title + " " * max(1, cols - vlen(title) - len(now)) + col(7, now, dim=True))
        if not self.s:
            out.append(col(RED, self.err or "warte auf Messwerte …"))
            return out
        foot = 9 if rows >= 34 else 7 if rows >= 28 else 2   # Tabelle (5) + Luft + Verlauf (+ Platz fuer die Welle)
        area = max(6, rows - 1 - foot)
        gh, gw = area // 3, cols // 3
        for r in range(3):
            cells = [g.render(gw, gh) for g in self.gauges[r * 3:(r + 1) * 3]]
            for i in range(gh):
                out.append("".join(c[i] for c in cells))
        if foot > 2:
            tbl = self.table(cols)
            tw = 4 + 7 * self.TW
            tbl += [""] * (foot - 1 - len(tbl))
            if cols >= tw + 24:
                wv = self.wave(cols - tw - 2, foot - 1)
                tbl = [clip(t, tw) + " " * (tw - vlen(clip(t, tw))) + "  " + wv[i] for i, t in enumerate(tbl)]
            out.extend(tbl)
        out.append(col(7, "Σ P ", dim=True) + self.sparkline(cols - 4))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="einen Frame ausgeben und beenden")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--rows", type=int)
    a = ap.parse_args()
    d = Grid()
    if a.once:
        d.update(fetch(host()))
        d.settle()
        size = shutil.get_terminal_size((120, 40))
        print("\n".join(d.frame(a.cols or size.columns, a.rows or size.lines)))
        return
    poller = Poller()
    poller.start()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        last_t, last_size, last_data = time.time(), None, None
        while True:
            now = time.time()
            if poller.data is not last_data:
                last_data = poller.data
                d.update(last_data)
            d.err = poller.err
            d.step(now - last_t)
            last_t = now
            size = shutil.get_terminal_size((120, 40))
            if size != last_size:
                sys.stdout.write("\x1b[2J")
                last_size = size
            sys.stdout.write(render_screen(d.frame(size.columns, size.lines), size.columns, size.lines))
            sys.stdout.flush()
            if select.select([sys.stdin], [], [], 1 / FPS)[0]:
                if sys.stdin.read(1) in ("q", "Q", "\x03"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
