#!/usr/bin/env python3
"""Shelly Pro 3EM (Gen2 RPC): Messwerte der drei Phasen. Host aus $SHELLY_HOST oder ~/.config/shelly-grid.json."""
import json, math, os, re, threading, time, urllib.request

HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:[0-9]{1,5})?$")
MAX_BYTES = 200_000

def host():
    h = os.environ.get("SHELLY_HOST")
    if not h:
        with open(os.path.expanduser("~/.config/shelly-grid.json")) as f:
            h = json.load(f)["host"]
    if not isinstance(h, str) or not HOST_RE.match(h):       # kein Pfad, kein @, keine Leerzeichen in der URL
        raise ValueError("ungueltiger Shelly-Host")
    return h

def fetch(h, timeout=2.0):
    with urllib.request.urlopen(f"http://{h}/rpc/EM.GetStatus?id=0", timeout=timeout) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Antwort zu gross")
    d = json.loads(raw)
    phases = []
    for p in "abc":
        P, S = d[f"{p}_act_power"], d[f"{p}_aprt_power"]
        phases.append({"u": d[f"{p}_voltage"], "i": d[f"{p}_current"], "p": P, "s": S,
                       "q": math.sqrt(max(0.0, S * S - P * P)),   # Blindleistung (Betrag) aus S und P
                       "pf": d[f"{p}_pf"], "f": d[f"{p}_freq"]})
    P, S = d["total_act_power"], d["total_aprt_power"]
    return {"t": time.time(), "phases": phases,
            "total": {"i": d["total_current"], "p": P, "s": S,
                      "q": sum(x["q"] for x in phases), "pf": P / S if S else 0.0}}

class Poller(threading.Thread):
    """Fragt im Hintergrund ab, damit die Zeigeranimation nie auf das Netz wartet."""
    def __init__(self, every=1.0):
        super().__init__(daemon=True)
        self.h, self.every, self.data, self.err = host(), every, None, None

    def run(self):
        while True:
            try:
                self.data, self.err = fetch(self.h), None
            except Exception as e:
                self.err = f"{self.h}: {e}"
            time.sleep(self.every)
