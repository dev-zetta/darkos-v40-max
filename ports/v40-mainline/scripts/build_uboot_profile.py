#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive the bootloader's V40 panel profile from the public R36S Plus DTB."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


DONOR_SHA256 = "1c434940b210be4ffde57f6f7c3eb80e0ec19deb8b001c61d4d50c8d624d74a8"
PANEL = "/dsi@ff450000/panel@0"
TIMING = PANEL + "/display-timings/original"


def capture(*args):
    return subprocess.check_output(args, text=True).strip()


def command_records(header, name):
    pattern = rf"\bv40_{name}_commands\[\]\s*=\s*\{{(.*?)\n\}};"
    match = re.search(pattern, header, re.S)
    if not match:
        raise ValueError(f"No V40 {name} command table")
    values = []
    for line in match[1].strip().splitlines():
        fields = re.fullmatch(r"\s*\{(0x[0-9a-f]+), (\d+), (\d+), \{([^}]+)\}\},", line)
        if not fields:
            raise ValueError(f"Unrecognized panel entry: {line}")
        kind, delay, length = [int(value, 0) for value in fields.groups()[:3]]
        payload = [int(value, 0) for value in fields[4].split(",")]
        if len(payload) != length or not length:
            raise ValueError(f"Invalid V40 {name} packet length")
        values.extend((kind, delay, length, *payload))
    if not values:
        raise ValueError(f"Empty V40 {name} command table")
    return bytes(values)


def build_profile(donor, kernel_source, output):
    if hashlib.sha256(donor.read_bytes()).hexdigest() != DONOR_SHA256:
        raise ValueError("Unsupported public R36S Plus bootstrap donor")
    header = (kernel_source / "drivers/gpu/drm/panel/panel-v40-commands.h").read_text()
    fields = {name: int(value) for name, value in re.findall(r"\.(\w+) = (\d+)\b", header)}
    width, height = fields["hdisplay"], fields["vdisplay"]
    if (width, height) != (720, 720):
        raise ValueError("Expected the V40 Max 720×720 panel")
    timing = {
        "clock-frequency": fields["clock"] * 1000,
        "hactive": width,
        "vactive": height,
        "hfront-porch": fields["hsync_start"] - width,
        "hsync-len": fields["hsync_end"] - fields["hsync_start"],
        "hback-porch": fields["htotal"] - fields["hsync_end"],
        "vfront-porch": fields["vsync_start"] - height,
        "vsync-len": fields["vsync_end"] - fields["vsync_start"],
        "vback-porch": fields["vtotal"] - fields["vsync_end"],
        "hsync-active": 0,
        "vsync-active": 0,
        "de-active": 0,
        "pixelclk-active": 1,
    }
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".v40-uboot-profile-") as work:
        profile = Path(work) / "profile.dtb"
        shutil.copyfile(donor, profile)
        for role in ("init", "exit"):
            prop = f"panel-{role}-sequence"
            expected = command_records(header, role)
            subprocess.run(
                ["fdtput", "-t", "bx", profile, PANEL, prop, *(f"{n:02x}" for n in expected)],
                check=True,
            )
            actual = bytes(int(n, 16) for n in capture("fdtget", "-t", "bx", profile, PANEL, prop).split())
            if actual != expected:
                raise RuntimeError(f"Bootloader panel readback differs: {prop}")
        for prop, value in timing.items():
            subprocess.run(["fdtput", "-t", "u", profile, TIMING, prop, str(value)], check=True)
        # The donor already routes reset through GPIO3 PC0, LCD through
        # RK817 LDO8 and backlight through PWM0, like the supported V40 board.
        panel_settings = {
            "width-mm": fields["width_mm"], "height-mm": fields["height_mm"],
            "prepare-delay-ms": 2, "reset-delay-ms": 1, "init-delay-ms": 20,
            "enable-delay-ms": 120, "disable-delay-ms": 50, "unprepare-delay-ms": 20,
        }
        for prop, value in panel_settings.items():
            subprocess.run(["fdtput", "-t", "u", profile, PANEL, prop, str(value)], check=True)
        for node, properties in ((PANEL, panel_settings), (TIMING, timing)):
            for prop, value in properties.items():
                if int(capture("fdtget", "-t", "u", profile, node, prop)) != value:
                    raise RuntimeError(f"Bootloader profile readback differs: {node}/{prop}")
        os.link(profile, output)
    print(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor", required=True, type=Path)
    parser.add_argument("--kernel-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build_profile(args.donor, args.kernel_source, args.output)


if __name__ == "__main__":
    main()
