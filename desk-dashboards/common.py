"""Gemeinsame Basis der Desk-Dashboards: Terminal-Schleife, ANSI-Helfer (aus power-dashboard/dashboard.py)."""
import argparse, os, select, shutil, sys, termios, time, tty

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "power-dashboard"))
from dashboard import (Canvas, sty, col, vlen, clip, render_screen, center,  # noqa: E402,F401
                       BOLD, DIM, RST, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN)

ORANGE = "\x1b[38;2;217;119;87m"      # Claude-Orange: einzige feste Farbe, alles andere folgt dem Theme


def pad(s, width):
    s = clip(s, width)
    return s + " " * (width - vlen(s))


def halfblocks(px, w, h, style):
    """Bitmap (Funktion px(x,y)->bool) als Halbblock-Zeilen; zwei Pixelzeilen pro Textzeile."""
    out = []
    for y in range(0, h, 2):
        row = []
        for x in range(w):
            t, b = px(x, y), px(x, y + 1) if y + 1 < h else False
            row.append("█" if t and b else "▀" if t else "▄" if b else " ")
        out.append(style + "".join(row) + RST)
    return out


def side_by_side(left, right, gap=2):
    """Zwei Textspalten nebeneinander (left hat feste sichtbare Breite)."""
    lw = max((vlen(l) for l in left), default=0)
    n = max(len(left), len(right))
    left = left + [""] * (n - len(left))
    right = right + [""] * (n - len(right))
    return [l + " " * (lw - vlen(l) + gap) + r for l, r in zip(left, right)]


def run(frame, fps=10, once_size=(90, 28)):
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--cols", type=int)
    ap.add_argument("--rows", type=int)
    a = ap.parse_args()
    if a.once:
        time.sleep(1.5)       # Hintergrund-Poller kurz zu Wort kommen lassen
        print("\n".join(frame(a.cols or once_size[0], a.rows or once_size[1], time.time())))
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        last = None
        while True:
            size = shutil.get_terminal_size((90, 28))
            if size != last:
                sys.stdout.write("\x1b[2J")
                last = size
            sys.stdout.write(render_screen(frame(size.columns, size.lines, time.time()), size.columns, size.lines))
            sys.stdout.flush()
            if select.select([sys.stdin], [], [], 1 / fps)[0] and sys.stdin.read(1) in ("q", "Q", "\x03"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
