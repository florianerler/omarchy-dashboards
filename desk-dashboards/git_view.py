#!/usr/bin/env python3
"""GIT ÜBERSICHT - lokale Repos (Branch, ahead/behind, uncommitted, letzter Commit) plus GitHub-PRs, mit GitHub-Logo.

Alles lokal und read-only: kein git fetch. `gh` läuft nur im Hintergrund mit Timeout und zeigt bei Fehlern "offline".
"""
import glob, json, math, os, subprocess, sys, threading, time
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import col, vlen, clip, pad, halfblocks, side_by_side, run, RED, GREEN, YELLOW, CYAN, MAGENTA, BLUE

HOME = os.path.expanduser("~")
ROOTS = [HOME + "/Work", HOME + "/Projects", HOME + "/PycharmProjects"]
state = {"repos": [], "days": Counter(), "gh": None, "user": None, "tried": False}
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")


def find_repos():
    found = set()
    for r in ROOTS:
        for g in glob.glob(r + "/*/.git"):
            found.add(os.path.dirname(g))
    if os.path.isdir(HOME + "/dotfiles/.git"):
        found.add(HOME + "/dotfiles")
    return sorted(found)


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=10, env=ENV).stdout


def repo_info(repo):
    st = git(repo, "status", "--porcelain=v2", "--branch")
    branch, ahead, behind, dirty, upstream = "?", 0, 0, 0, False
    for ln in st.splitlines():
        if ln.startswith("# branch.head"):
            branch = ln.split()[2]
        elif ln.startswith("# branch.upstream"):
            upstream = True
        elif ln.startswith("# branch.ab"):
            _, _, a, b = ln.split()
            ahead, behind = int(a[1:]), -int(b)
        elif not ln.startswith("#"):
            dirty += 1
    last = git(repo, "log", "-1", "--format=%ct|%s").strip().split("|", 1)
    days = git(repo, "log", "--since=14 days ago", "--format=%ad", "--date=short").split()
    return {"name": os.path.basename(repo), "branch": branch, "ahead": ahead, "behind": behind,
            "dirty": dirty, "upstream": upstream,
            "ts": int(last[0]) if last[0] else 0, "subject": last[1] if len(last) > 1 else "(keine Commits)"}, days


def poll_git():
    while True:
        repos, days = [], Counter()
        for r in find_repos():
            try:
                info, d = repo_info(r)
                repos.append(info)
                days.update(d)
            except Exception:
                continue
        repos.sort(key=lambda r: -r["ts"])
        state["repos"], state["days"] = repos, days
        time.sleep(8)


def poll_gh():
    while True:
        try:
            if not state["user"]:
                state["user"] = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True,
                                               timeout=20).stdout.strip() or None
            r = subprocess.run(["gh", "search", "prs", "--author", "@me", "--state", "open", "--json",
                                "repository,number,title", "-L", "5"], capture_output=True, text=True, timeout=30)
            state["gh"] = json.loads(r.stdout) if r.returncode == 0 else None
        except Exception:
            state["gh"] = None
        state["tried"] = True
        time.sleep(120)


# Git-Logo: orange Raute, darin als Aussparung der Branch-Graph (32x32 Pixel -> 16 Zeilen)
GIT_RED = "\x1b[38;2;240;80;50m"
NODES = ((12, 9.5), (12, 22.5), (21, 15))          # Haupt-oben, Haupt-unten, Branch


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def gitlogo(x, y):
    X, Y = x + 0.5, y + 0.5
    if abs(X - 16) + abs(Y - 16) > 15.2:
        return False
    cut = any(math.hypot(X - nx, Y - ny) <= 2.6 for nx, ny in NODES)                 # Knoten
    cut |= seg_dist(X, Y, 12, 9.5, 12, 22.5) <= 1.1                                  # Stamm
    cut |= seg_dist(X, Y, 12, 19.5, 21, 15) <= 1.1                                   # Abzweig
    return not cut


LOGO = halfblocks(gitlogo, 32, 32, "\x1b[1m" + GIT_RED)


def ago(ts):
    s = max(0, int(time.time() - ts))
    return f"{s // 60}m" if s < 3600 else f"{s // 3600}h" if s < 86400 else f"{s // 86400}d"


def frame(cols, rows, t):
    repos, gh = state["repos"], state["gh"]
    today = time.strftime("%Y-%m-%d")
    out = [col(CYAN, "▌GIT ÜBERSICHT", bold=True)]
    # Commit-Aktivität der letzten 14 Tage über alle Repos
    days = [time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400 * i)) for i in range(13, -1, -1)]
    vals = [state["days"].get(d, 0) for d in days]
    top = max(max(vals), 1)
    bars = " ▁▂▃▄▅▆▇█"
    spark = "".join(col(GREEN if d == today else CYAN, bars[min(8, int(v / top * 8 + 0.5))]) for d, v in zip(days, vals))
    dirty = sum(1 for r in repos if r["dirty"])
    ahead = sum(1 for r in repos if r["ahead"])
    info = [col(7, "GitHub  ", dim=True) + col(7, state["user"] or ("offline" if state["tried"] else "…"), bold=True),
            "",
            col(7, "Repos       ", dim=True) + col(7, str(len(repos)), bold=True),
            col(7, "uncommitted ", dim=True) + col(YELLOW if dirty else GREEN, str(dirty), bold=True),
            col(7, "unpushed    ", dim=True) + col(YELLOW if ahead else GREEN, str(ahead), bold=True),
            col(7, "offene PRs  ", dim=True) + (col(MAGENTA, str(len(gh)), bold=True) if gh is not None else (col(RED, "offline") if state["tried"] else col(7, "…", dim=True))),
            "",
            col(7, "14 Tage ", dim=True) + spark,
            col(7, f"heute {state['days'].get(today, 0)} Commits", dim=True)]
    big = cols >= 62 and rows >= 24
    if big:
        out += side_by_side(LOGO, [""] * 1 + info, gap=3)
    else:
        out += info
    out.append("")
    avail = rows - len(out) - 1
    for r in repos[:max(1, avail)]:
        flags = ""
        if r["dirty"]:
            flags += col(YELLOW, f" ±{r['dirty']}", bold=True)
        if r["ahead"]:
            flags += col(GREEN, f" ↑{r['ahead']}")
        if r["behind"]:
            flags += col(RED, f" ↓{r['behind']}")
        if not r["upstream"] and r["branch"] != "?":
            flags += col(7, " (lokal)", dim=True)
        left = col(7, r["name"][:22].ljust(22), bold=True) + col(MAGENTA, (" " + r["branch"])[:14].ljust(14)) + flags
        right = col(7, f"{(ago(r['ts']) if r['ts'] else '-'):>4}  {r['subject']}", dim=True)
        out.append(pad(left, 50 if cols >= 90 else 42) + clip(right, max(0, cols - (50 if cols >= 90 else 42))))
    if gh:
        out.append("")
        for p in gh[:2]:
            out.append(col(MAGENTA, "PR ") + col(7, f"{p['repository']['nameWithOwner']}#{p['number']} {p['title']}", dim=True))
    return out


if __name__ == "__main__":
    threading.Thread(target=poll_git, daemon=True).start()
    threading.Thread(target=poll_gh, daemon=True).start()
    run(frame, fps=2)
