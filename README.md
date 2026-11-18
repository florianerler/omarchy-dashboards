# omarchy-dashboards

Terminal-Dashboards im ANSI-Stil für **Omarchy** (Hyprland + `foot`): analoge Rundinstrumente und Grafiken aus Braille-Punkten.
Farben sind ANSI-Indexfarben und folgen deshalb dem aktiven Omarchy-Theme (Ausnahmen: Claude-Orange, Git-Rot).
Nur Python-Standardbibliothek. Beenden mit `q`.

## power-dashboard/

| Skript | Zeigt |
|---|---|
| `grid.py` | **Hausanschluss** (Shelly Pro 3EM): 9 Zeigerinstrumente (U, I, P je Phase), Tabelle mit U, I, P, S, Q, PF, f, Verlauf der Gesamtleistung, bewegte Drehstrom-Sinuswelle |
| `dashboard.py` | **IdeaPad-Strom**: Akku, Leistung, Spannung, Strom aus `/sys` (Lenovo-spezifische Teile optional) |
| `server.py` + `index.html` | Web-Variante des IdeaPad-Dashboards auf `127.0.0.1:8765` (nur lokal) |

**Shelly einrichten:** Host per `SHELLY_HOST=192.168.x.y` oder in `~/.config/shelly-grid.json`:
`{"host": "192.168.x.y"}`. Es wird `http://<host>/rpc/EM.GetStatus?id=0` (Gen2/Gen3 RPC) jede Sekunde abgefragt,
ohne Authentifizierung (bei aktivem Passwort nicht unterstützt). Q wird als √(S² − P²) berechnet, ist also immer positiv.
Die Amperemeter haben eine feste Skala 0–63 A (`I_MAX` in `grid.py`).

## desk-dashboards/

| Skript | Zeigt |
|---|---|
| `git_view.py` | Lokale Repos (Branch, ↑↓, uncommitted, letzter Commit), 14-Tage-Commit-Verlauf, offene PRs (`gh`, nur wenn angemeldet), Git-Logo |
| `claude_view.py` | Laufende **Claude-Code-Sitzungen dieses Rechners** (aus `~/.claude/sessions/*.json`) mit animiertem Maskottchen und Sprüchen |
| `viz.py` | Rotierender Lorenz-Attraktor |

Repo-Suche von `git_view.py`: `~/Work/*`, `~/Projects/*`, `~/PycharmProjects/*`, `~/dotfiles` (`ROOTS` oben im Skript).

## Starten

```
python3 -I power-dashboard/grid.py
python3 -I desk-dashboards/claude_view.py
python3 -I desk-dashboards/git_view.py
python3 -I desk-dashboards/viz.py
```

`--once [--cols N --rows N]` gibt einen einzelnen Frame aus (zum Testen). `examples/ws6.sh` baut ein 2×2-Raster mit
Git, Claude, cmatrix und Lorenz auf Hyprland-Workspace 6, `examples/ws7.sh` startet das Hausanschluss-Dashboard auf
Workspace 7. Beide sind Beispiele: Pfade ergeben sich aus dem Repo-Ort, Bindungen trägst du selbst ein.

## Datenschutz und Sicherheit

- Alles läuft lokal. Netzzugriffe: nur das Shelly in deinem LAN (HTTP, wie das Gerät es anbietet) und `gh` für die PR-Zahl.
- `claude_view.py` liest nur die Status-JSONs (pid, Name, Ordner, Status), nie die `.key`-Dateien, und zeigt nur Sitzungen mit
  lebendem Prozess. `git_view.py` ruft nur lesende Git-Befehle auf (kein `fetch`, `GIT_TERMINAL_PROMPT=0`).
- Der Shelly-Host wird vor der Nutzung geprüft (kein Pfad, kein `@`), Antworten sind auf 200 kB begrenzt.
- Im Repo stehen keine Zugangsdaten und keine persönlichen Daten; die Shelly-Adresse liegt in deiner lokalen Config.

## Tests

```
python3 -I -m unittest discover -s tests      # offline
```

Lizenz: MIT.
