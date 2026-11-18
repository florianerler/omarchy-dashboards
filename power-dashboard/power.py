#!/usr/bin/env python3
"""Messwerte des IdeaPad aus /sys (kein root nötig); gemeinsame Basis für Web- und Terminal-Dashboard."""
import glob, json, os, time

PS = "/sys/class/power_supply"
IDEA = glob.glob("/sys/bus/platform/drivers/ideapad_acpi/VPC*")

def rd(p, conv=str):
    try:
        with open(p) as f:
            return conv(f.read().strip())
    except Exception:
        return None

def hwmon(name):
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if rd(d + "/name") == name:
            return d

def sample():
    b = PS + "/BAT0"
    volt = (rd(b + "/voltage_now", int) or 0) / 1e6
    power = (rd(b + "/power_now", int) or 0) / 1e6
    status = rd(b + "/status")
    e_now = (rd(b + "/energy_now", int) or 0) / 1e6
    e_full = (rd(b + "/energy_full", int) or 0) / 1e6
    e_des = (rd(b + "/energy_full_design", int) or 0) / 1e6
    amps = power / volt if volt else 0
    signed = -power if status == "Discharging" else power
    if status in ("Discharging", "Charging") and power > 0.5:
        h = (e_now / power) if status == "Discharging" else ((e_full - e_now) / power)
    else:
        h = None
    usb = [{"name": os.path.basename(d), "online": rd(d + "/online", int),
            "current_a": (rd(d + "/current_now", int) or 0) / 1e6,
            "usb_type": rd(d + "/usb_type")}
           for d in glob.glob(PS + "/ucsi-source-psy-*")]
    temps = {}
    for label, n in (("NVMe", "nvme"), ("GPU", "amdgpu"), ("ACPI", "acpitz")):
        d = hwmon(n)
        if d:
            t = rd(d + "/temp1_input", int)
            if t is not None:
                temps[label] = t / 1000
    gpu = hwmon("amdgpu")
    gpu_w = (rd(gpu + "/power1_average", int) or 0) / 1e6 if gpu else None
    freqs = [rd(f, int) for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")]
    freqs = [f / 1000 for f in freqs if f]
    idea = IDEA[0] if IDEA else None
    return {
        "t": time.time(),
        "percent": rd(b + "/capacity", int), "status": status,
        "ac": rd(PS + "/ACAD/online", int),
        "voltage_v": volt, "power_w": power, "power_signed_w": signed, "current_a": amps,
        "energy_wh": e_now, "full_wh": e_full, "design_wh": e_des,
        "health_pct": e_full / e_des * 100 if e_des else None,
        "cycles": rd(b + "/cycle_count", int), "hours_left": h,
        "model": rd(b + "/model_name"), "manufacturer": rd(b + "/manufacturer"),
        "charge_types": rd(b + "/charge_types"),
        "usb": usb, "temps": temps, "gpu_w": gpu_w,
        "cpu_mhz": sum(freqs) / len(freqs) if freqs else None,
        "profile": rd("/sys/firmware/acpi/platform_profile"),
        "conservation": rd(idea + "/conservation_mode", int) if idea else None,
    }

