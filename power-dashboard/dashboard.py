#!/usr/bin/env python3
"""IDEAPAD STROM - Terminal-Dashboard mit analogen Rundinstrumenten.

Vier Zeigerinstrumente (Akku, Leistung, Spannung, Strom) aus Braille-Punkten, darunter
Statuszeilen und ein Leistungsverlauf. Der Zeiger folgt den Messwerten mit Traegheit wie ein
echtes Drehspulinstrument. Die Messwerte kommen aus power.py (/sys, kein root noetig).

Farben: ausschliesslich ANSI-Indexfarben, damit foot sie mit der Palette des aktiven
Omarchy-Themes belegt - ein Theme-Wechsel zieht also mit.

Start:  python3 -I dashboard.py            (Beenden mit q)
Test:   python3 -I dashboard.py --once [--cols 90 --rows 17]
"""
import argparse
import math
import os
import re
import select
import shutil
import sys
import termios
import time
import tty
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from power import sample  # noqa: E402

RST, BOLD, DIM = "\x1b[0m", "\x1b[1m", "\x1b[2m"
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN = 1, 2, 3, 4, 5, 6
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SWEEP_START, SWEEP = 210.0, 240.0      # Skala von links unten ueber oben nach rechts unten
FPS = 12
SAMPLE_EVERY_S = 1.0
HISTORY = 240


def col(n, text, bold=False, dim=False):
    return f"{BOLD if bold else ''}{DIM if dim else ''}\x1b[3{n}m{text}{RST}"


def vlen(s):
    return len(ANSI_RE.sub("", s))


def clip(s, width):
    """Auf sichtbare Breite kuerzen; Escape-Sequenzen zaehlen nicht mit."""
    out, n, i = [], 0, 0
    while i < len(s):
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group())
            i = m.end()
        elif n < width:
            out.append(s[i])
            n += 1
            i += 1
        else:
            break
    return "".join(out) + RST


def center(s, width):
    pad = max(0, width - vlen(s))
    return " " * (pad // 2) + s + " " * (pad - pad // 2)


# --- Braille-Leinwand ---------------------------------------------------------------------------
# Jede Zelle hat 2x4 Punkte; bei ueblichen 1:2-Zellen sind die Punkte quadratisch, Kreise bleiben rund.
BRAILLE_BIT = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (1, 0): 0x08,
               (1, 1): 0x10, (1, 2): 0x20, (0, 3): 0x40, (1, 3): 0x80}


class Canvas:
    def __init__(self, wc, hc):
        self.wc, self.hc = wc, hc
        self.W, self.H = wc * 2, hc * 4
        self.mask = [[0] * wc for _ in range(hc)]
        self.style = [[""] * wc for _ in range(hc)]

    def set(self, x, y, style):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.W and 0 <= y < self.H:
            cx, cy = x // 2, y // 4
            self.mask[cy][cx] |= BRAILLE_BIT[(x % 2, y % 4)]
            self.style[cy][cx] = style   # der zuletzt gezeichnete Punkt bestimmt die Zellfarbe

    def line(self, x0, y0, x1, y1, style):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
        for i in range(n + 1):
            t = i / n
            self.set(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, style)

    def rows(self):
        for cy in range(self.hc):
            yield "".join(f"{self.style[cy][cx]}{chr(0x2800 + m)}{RST}" if m else " "
                          for cx, m in enumerate(self.mask[cy]))


def sty(color, bold=False, dim=False):
    return f"{BOLD if bold else ''}{DIM if dim else ''}\x1b[3{color}m"


# --- Instrument ---------------------------------------------------------------------------------
class Gauge:
    """Ein Rundinstrument. `target` ist der Messwert, `shown` die (traege) Zeigerstellung."""

    def __init__(self, label, unit, lo, hi, zones, decimals=1):
        self.label, self.unit, self.lo, self.hi = label, unit, lo, hi
        self.zones, self.decimals = zones, decimals
        self.target = self.shown = lo
        self.caption = ""

    def step(self, dt):
        # Exponentielles Nachlaufen: wirkt wie die Daempfung eines mechanischen Zeigers.
        self.shown += (self.target - self.shown) * min(1.0, dt * 6)

    def frac(self, v):
        return min(1.0, max(0.0, (v - self.lo) / (self.hi - self.lo)))

    def zone_color(self, f):
        for end, c in self.zones:
            if f <= end:
                return c
        return self.zones[-1][1]

    def render(self, width, height):
        """Liefert `height` Zeilen mit exakt `width` sichtbaren Zeichen."""
        text_rows = 2 if height >= 6 else 1
        hc = max(1, height - text_rows)
        cv = Canvas(width, hc)
        r = min(cv.W / 2 - 1, (cv.H - 2) / 1.5)
        cx = (cv.W - 1) / 2
        cy = (cv.H - 1.5 * r) / 2 + r
        f_now = self.frac(self.shown)
        if r >= 4:
            ang = lambda f: math.radians(SWEEP_START - SWEEP * f)
            # Skalenbogen: bis zum Zeiger kraeftig, dahinter gedimmt - zeigt den Ausschlag auf einen Blick.
            steps = int(SWEEP * r / 8) + 8
            for i in range(steps + 1):
                f = i / steps
                st = sty(self.zone_color(f), bold=f <= f_now, dim=f > f_now)
                a = ang(f)
                for rr in (r, r - 1):
                    cv.set(cx + rr * math.cos(a), cy - rr * math.sin(a), st)
            # Teilstriche innen, grosse Striche alle 10 %.
            for i in range(21):
                f = i / 20
                a = ang(f)
                r1 = r - 3
                r2 = r - (6 if i % 2 == 0 else 5)
                if r2 > 2:
                    st = sty(7, dim=True) if i % 2 else sty(7)
                    cv.line(cx + r1 * math.cos(a), cy - r1 * math.sin(a),
                            cx + r2 * math.cos(a), cy - r2 * math.sin(a), st)
            # Zeiger und Nabe.
            a = ang(f_now)
            tip = max(3, r - 7)
            needle = sty(7, bold=True)
            cv.line(cx, cy, cx + tip * math.cos(a), cy - tip * math.sin(a), needle)
            cv.line(cx + 1, cy, cx + 1 + tip * math.cos(a), cy - tip * math.sin(a), needle)
            for dx in (-1, 0, 1, 2):
                for dy in (-1, 0, 1):
                    cv.set(cx + dx, cy + dy, needle)
        lines = [ln for ln in cv.rows()]
        c = self.zone_color(self.frac(self.target))
        val = f"{self.target:.{self.decimals}f}"
        value_line = col(c, val, bold=True) + " " + col(7, self.unit, dim=True)
        lo_s, hi_s = f"{self.lo:g}", f"{self.hi:g}"
        gap = width - len(lo_s) - len(hi_s) - 2   # je 1 Leerzeichen Rand, damit Nachbarinstrumente nicht verschmelzen
        if text_rows == 2 and gap > vlen(value_line) + 2:
            mid = center(value_line, gap)
            lines.append(" " + col(7, lo_s, dim=True) + mid + col(7, hi_s, dim=True) + " ")
            lines.append(center(col(7, self.label, dim=True) + (" " + self.caption if self.caption else ""), width))
        else:
            lines.append(center(value_line, width))
        return [clip(ln, width) + " " * (width - vlen(clip(ln, width))) for ln in lines[:height]]


def pick_scale(value, steps):
    """Kleinste Skala, in die der Wert passt - so bleibt der Zeiger bei kleinen Lasten lesbar."""
    for s in steps:
        if value <= s * 0.92:
            return s
    return steps[-1]


# --- Dashboard ----------------------------------------------------------------------------------
class Dashboard:
    def __init__(self):
        self.akku = Gauge("AKKU", "%", 0, 100, [(0.2, RED), (0.4, YELLOW), (1, GREEN)], 0)
        self.power = Gauge("LEISTUNG", "W", 0, 70, [(0.5, GREEN), (0.8, YELLOW), (1, RED)], 1)
        self.volt = Gauge("SPANNUNG", "V", 10.5, 13.5, [(0.1, RED), (1, CYAN)], 2)
        self.amp = Gauge("STROM", "A", 0, 6, [(0.6, GREEN), (0.85, YELLOW), (1, RED)], 2)
        self.gauges = [self.akku, self.power, self.volt, self.amp]
        self.hist = deque(maxlen=HISTORY)
        self.s = None
        self.err = None

    def update(self, s):
        self.s = s
        self.hist.append(s["power_signed_w"])
        self.akku.target = s["percent"] or 0
        self.power.target = s["power_w"]
        self.power.hi = pick_scale(s["power_w"], (15, 30, 70, 100, 140))
        self.power.caption = col(CYAN if s["status"] == "Charging" else YELLOW,
                                 "lädt" if s["status"] == "Charging" else
                                 "entlädt" if s["status"] == "Discharging" else "")
        self.volt.target = s["voltage_v"]
        self.amp.target = s["current_a"]
        self.amp.hi = pick_scale(s["current_a"], (2, 4, 6, 10))

    def settle(self):
        for g in self.gauges:
            g.shown = g.target

    def step(self, dt):
        for g in self.gauges:
            g.step(dt)

    def sparkline(self, width):
        data = list(self.hist)[-width:]
        if not data:
            return ""
        top = max(max(data), 1.0)
        bars = " ▁▂▃▄▅▆▇█"
        return "".join(col(CYAN if v >= 0 else YELLOW, bars[min(8, int(abs(v) / top * 8 + 0.5))]) for v in data)

    def frame(self, cols, rows):
        s = self.s
        out = []
        now = time.strftime("%H:%M:%S")
        title = col(CYAN, "▌IDEAPAD STROM", bold=True)
        if s:
            ac = col(GREEN, "Netzteil", bold=True) if s["ac"] else col(YELLOW, "Akku", bold=True)
            title += col(7, "  ·  ", dim=True) + ac
        out.append(title + " " * max(1, cols - vlen(title) - len(now)) + col(7, now, dim=True))
        if not s:
            out.append(col(RED, self.err or "warte auf Messwerte …"))
            return out
        foot = 3 if rows >= 14 else 2 if rows >= 10 else 1
        area = max(3, rows - 1 - foot)
        per = 4 if cols >= 72 else 2 if cols >= 36 else 1
        nrow = math.ceil(len(self.gauges) / per)
        gh, gw = area // nrow, cols // per
        for r in range(nrow):
            cells = [g.render(gw, gh) for g in self.gauges[r * per:(r + 1) * per]]
            for i in range(gh):
                out.append("".join(c[i] for c in cells))
        stat = {"Charging": col(CYAN, "▲ lädt", bold=True), "Discharging": col(YELLOW, "▼ entlädt", bold=True),
                "Full": col(GREEN, "● voll", bold=True)}.get(s["status"], col(7, s["status"] or "?", bold=True))
        h = s["hours_left"]
        eta = "" if h is None else col(7, "bis voll " if s["status"] == "Charging" else "Restzeit ", dim=True) \
            + f"{int(h)}:{int(h % 1 * 60):02d} h"
        sep = col(7, "  ·  ", dim=True)
        l1 = stat + (sep + eta if eta else "") + sep + f"{s['energy_wh']:.1f}/{s['full_wh']:.1f} Wh"
        t = s["temps"]
        l2 = sep.join(x for x in (
            f"Gesundheit {s['health_pct']:.0f} %", f"{s['cycles']} Zyklen",
            f"GPU {s['gpu_w']:.1f} W" if s["gpu_w"] is not None else "",
            f"CPU {s['cpu_mhz'] / 1000:.1f} GHz" if s["cpu_mhz"] else "",
            f"NVMe {t['NVMe']:.0f} °C" if "NVMe" in t else "",
            s["profile"] or "") if x)
        extra = [l1, l2, col(7, "P ", dim=True) + self.sparkline(cols - 2)]
        out.extend(extra[:foot] if foot == 3 else [extra[0], extra[1]][:foot])
        return out


def render_screen(lines, cols, rows):
    buf = ["\x1b[H"]
    for i in range(rows):
        ln = clip(lines[i], cols) if i < len(lines) else ""
        buf.append(ln + "\x1b[K" + ("\r\n" if i < rows - 1 else ""))
    return "".join(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="einen Frame ausgeben und beenden")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--rows", type=int)
    a = ap.parse_args()
    d = Dashboard()
    if a.once:
        d.update(sample())
        d.settle()
        size = shutil.get_terminal_size((90, 17))
        cols, rows = a.cols or size.columns, a.rows or size.lines
        print("\n".join(d.frame(cols, rows)))
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        last_sample, last_t, last_size = 0.0, time.time(), None
        while True:
            now = time.time()
            if now - last_sample >= SAMPLE_EVERY_S:
                try:
                    d.update(sample())
                    d.err = None
                except Exception as e:  # Sensor weg oder nicht lesbar: im Fenster sagen, nicht still weitermachen
                    d.err = f"Messfehler: {e}"
                last_sample = now
            d.step(now - last_t)
            last_t = now
            size = shutil.get_terminal_size((90, 17))
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
