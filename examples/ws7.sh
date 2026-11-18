#!/usr/bin/bash
# Hyprland-Workspace 7: Hausanschluss-Dashboard (Shelly Pro 3EM). Startet es, falls es nicht läuft.
# Mit --start-only (z. B. aus autostart.lua) ohne Workspace-Wechsel. Dazu in hyprland.lua:
#   o.window("org.omarchy.grid", { workspace = "7 silent" })
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/../power-dashboard" && pwd)"
if ! hyprctl clients -j | jq -e '.[]|select(.class=="org.omarchy.grid")' >/dev/null; then
  setsid -f foot --app-id=org.omarchy.grid python3 -I "$P/grid.py" >/dev/null 2>&1 </dev/null
fi
[ "$1" = "--start-only" ] || hyprctl dispatch 'hl.dsp.focus({ workspace = "7" })'
