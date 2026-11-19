#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the first-boot controller profile against the V40 SDL mapping."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_image_rootfs import MAPPING, seed_frontend_controller


class FrontendInputTest(unittest.TestCase):
    def test_fresh_image_profile_matches_known_pad(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "etc/emulationstation/es_input.cfg"
            with patch("prepare_image_rootfs.os.chown") as chown:
                seed_frontend_controller(root)
            chown.assert_called_once_with(profile, 1000, 1000)
            self.assertEqual(profile.stat().st_mode & 0o777, 0o644)
            guid, name, *fields = MAPPING.rstrip(",").split(",")
            mapping = dict(field.split(":", 1) for field in fields)
            node, = ET.parse(profile).getroot().findall("inputConfig")
            self.assertEqual(node.attrib, {"type": "joystick", "deviceName": name, "deviceGUID": guid})
            entries = {entry.get("name"): (entry.get("type"), entry.get("id"), entry.get("value"))
                       for entry in node.findall("input")}
            aliases = {"up": "dpup", "down": "dpdown", "left": "dpleft", "right": "dpright",
                       "select": "back", "leftthumb": "leftstick", "rightthumb": "rightstick",
                       "pageup": "leftshoulder", "pagedown": "rightshoulder",
                       "hotkeyenable": "guide", "system_hk": "guide"}
            for button in ("a", "b", "x", "y", "start", "leftshoulder", "rightshoulder",
                           "lefttrigger", "righttrigger", *aliases):
                self.assertEqual(entries[button], ("button", mapping[aliases.get(button, button)][1:], "1"))
            for stick in ("left", "right"):
                for direction, axis, value in (("up", "y", "-1"), ("down", "y", "1"),
                                               ("left", "x", "-1"), ("right", "x", "1")):
                    self.assertEqual(entries[stick + "analog" + direction],
                                     ("axis", mapping[stick + axis][1:], value))
            self.assertEqual(len(node.findall("input")), 28)

    def test_existing_profile_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "etc/emulationstation/es_input.cfg"
            profile.parent.mkdir(parents=True)
            profile.write_text("existing profile\n")
            seed_frontend_controller(root)
            self.assertEqual(profile.read_text(), "existing profile\n")
