#!/usr/bin/bash
# Hyprland-Workspace 6: vier Dashboards im 2x2-Raster (Git oben links, Claude oben rechts, cmatrix unten links, Lorenz unten rechts).
# Startet nur, wenn der Workspace leer ist. Bindung z. B. in ~/.config/hypr/bindings.lua:
#   o.rebind("SUPER + 6", "Dashboards", "/pfad/zu/examples/ws6.sh")
D="$(cd "$(dirname "${BASH_SOURCE[0]}")/../desk-dashboards" && pwd)"
start() { setsid -f foot --app-id="$1" "${@:2}" >/dev/null 2>&1 </dev/null; }
hyprctl dispatch 'hl.dsp.focus({ workspace = "6" })' >/dev/null
if [ "$(hyprctl clients -j | jq '[.[]|select(.workspace.id==6)]|length')" -eq 0 ]; then
  start org.omarchy.git python3 -I "$D/git_view.py";       sleep 1
  start org.omarchy.claude python3 -I "$D/claude_view.py"; sleep 1
  start org.omarchy.viz python3 -I "$D/viz.py";            sleep 1
  hyprctl dispatch 'hl.dsp.focus({ direction = "left" })' >/dev/null; sleep 0.4
  start org.omarchy.matrix cmatrix -ab -u 6 -C cyan
fi
