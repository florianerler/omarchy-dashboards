#!/usr/bin/env python3
"""CLAUDE SITZUNGEN - laufende Claude-Code-Sitzungen (aus ~/.claude/sessions) mit animiertem Maskottchen.

Liest nur die Status-JSONs (pid, name, cwd, status, Zeitstempel); die .key-Dateien werden nie angefasst.
"""
import glob, json, os, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ORANGE, RST, col, vlen, clip, pad, halfblocks, side_by_side, run,
                    RED, GREEN, YELLOW, CYAN)

SESS = os.path.expanduser("~/.claude/sessions")
HOME = os.path.expanduser("~")
state = {"sessions": [], "ws": {}}

# Clawd als Pixelbild; E = Auge, A = Arm (wird animiert), L = Bein
BODY = ["  XXXXXXXXXXX  ",
        "  XXXXXXXXXXX  ",
        "  XXXXXXXXXXX  ",
        "  XXXXXXXXXXX  ",
        "  XXXXXXXXXXX  ",
        "  XXXXXXXXXXX  "]


def clawd_pixels(t, mode):
    """Liefert Funktion px(x,y) und (w,h). mode: busy -> Arme wippen, Augen blinzeln selten; sonst ruhig."""
    w, h = 15, 9
    blink = (t % 4.0) < 0.15
    arm_y = 3 + (int(t * 4) % 2 if mode == "busy" else 0)
    legs = int(t * 3) % 2 if mode == "busy" else 0
    grid = [[False] * w for _ in range(h)]
    for y, row in enumerate(BODY):
        for x, c in enumerate(row):
            grid[y][x] = c == "X"
    for dy in (0, 1):                                  # Arme links und rechts
        for x in (0, 1, 13, 14):
            grid[arm_y + dy][x] = True
    for lx in (3, 5, 9, 11):                           # vier Beine
        for dy in (0, 1):
            grid[6 + dy + (1 if (lx in (3, 9)) == bool(legs) and mode == "busy" and dy == 1 else 0)][lx] = True
    if not blink:                                      # Augen = Aussparungen im Körper
        for ex in (5, 9):
            for ey in (2, 3):
                grid[ey][ex] = False
    return (lambda x, y: 0 <= y < h and 0 <= x < w and grid[y][x]), (w, h)


def foot_pids():
    try:
        out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2).stdout
        return {c["pid"]: c["workspace"]["id"] for c in json.loads(out)}
    except Exception:
        return {}


def ppid(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return int(f.read().rsplit(")", 1)[1].split()[1])
    except Exception:
        return 0


def workspace_of(pid, wins):
    for _ in range(12):
        if pid in wins:
            return wins[pid]
        pid = ppid(pid)
        if pid <= 1:
            break
    return None


def poll():
    while True:
        wins = foot_pids()
        rows = []
        for f in glob.glob(SESS + "/*.json"):
            try:
                with open(f) as fh:
                    d = json.load(fh)
                pid = int(d["pid"])
                if not os.path.exists(f"/proc/{pid}"):
                    continue                           # veraltete Datei einer beendeten Sitzung
                rows.append({"pid": pid, "name": d.get("name") or "?", "cwd": d.get("cwd", ""),
                             "status": str(d.get("status") or "?"), "since": (d.get("statusUpdatedAt") or d.get("updatedAt") or 0) / 1000,
                             "ws": workspace_of(pid, wins)})
            except Exception:
                continue
        rows.sort(key=lambda r: (r["status"] != "busy", r["name"]))
        state["sessions"] = rows
        time.sleep(1.5)


def ago(sec):
    sec = max(0, int(sec))
    return f"{sec}s" if sec < 60 else f"{sec // 60}m" if sec < 3600 else f"{sec // 3600}h{sec % 3600 // 60:02d}"


def short(path):
    return "~" + path[len(HOME):] if path.startswith(HOME) else path


QUOTES_BUSY = ["denkt …", "tüftelt am Code", "kompiliert im Kopf", "Tokens glühen", "gleich fertig™", "rm -rf Zweifel",
               "git blame sagt: warst du", "liest 400 Dateien, tippt 3 Zeilen", "fast so schnell wie der Kaffee", "hmm, interessant …"]
QUOTES_IDLE = ["Feierabend?", "Zeit für einen Kaffee ☕", "wartet auf Befehle", "alles ruhig im Maschinenraum",
               "Ctrl+Z fürs Leben gesucht", "schläft mit offenen Augen", "kein Bug in Sicht", "bitte nicht stören. Doch, gern!",
               "scrollt durch alte Commits", "es läuft. Rühr nichts an."]


def quote(busy, t):
    qs = QUOTES_BUSY if busy else QUOTES_IDLE
    i = int(t // 9)                                    # alle 9 s ein neuer Spruch, reihum gemischt
    return qs[(i * 7 + (3 if busy else 0)) % len(qs)]


SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def frame(cols, rows, t):
    ss = state["sessions"]
    busy = [s for s in ss if s["status"] == "busy"]
    mode = "busy" if busy else "idle"
    out = [col(CYAN, "▌CLAUDE SITZUNGEN", bold=True)]
    px, (w, h) = clawd_pixels(t, mode)
    scale = 3 if cols >= 84 and rows >= 24 else 2 if cols >= 56 and rows >= 22 else 1
    sprite = halfblocks(lambda x, y: px(x // scale, y // scale), w * scale, h * scale, ORANGE)
    summary = [col(7, "Sitzungen  ", dim=True) + col(7, str(len(ss)), bold=True),
               col(7, "arbeitet   ", dim=True) + col(YELLOW, str(len(busy)), bold=True),
               col(7, "wartet     ", dim=True) + col(GREEN, str(len(ss) - len(busy)), bold=True),
               "",
               col(7, "„" + quote(bool(busy), t) + "“", dim=True)]
    if scale == 1 or rows >= 14:
        head = side_by_side(sprite, [""] * max(0, (len(sprite) - len(summary)) // 2) + summary, gap=3)
        out += head
    out.append("")
    now = time.time()
    for s in ss[:max(1, rows - len(out) - 2)]:
        st = s["status"]
        if st == "busy":
            mark = col(YELLOW, SPIN[int(t * 10) % len(SPIN)], bold=True)
        elif st == "idle":
            mark = col(GREEN, "●")
        else:
            mark = col(CYAN, "◆")
        ws = f"WS{s['ws']}" if s["ws"] else "  -"
        line = f"{mark} {col(7, s['name'], bold=True)}  {col(7, short(s['cwd']), dim=True)}"
        right = f"{st} {ago(now - s['since'])}  {ws}"
        out.append(pad(line, cols - len(right) - 3) + " " + col(7, right, dim=True))
    if not ss:
        out.append(col(7, "keine laufende Sitzung gefunden", dim=True))
    return out


if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    run(frame, fps=10)
