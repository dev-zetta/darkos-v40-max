#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify that the V40 default changes only RetroArch's modifier."""

from pathlib import Path
import runpy
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "components/emulators/configure-image.py"
change_hotkey = runpy.run_path(str(SCRIPT))["change_hotkey"]


class RetroArchHotkeyTest(unittest.TestCase):
    def test_select_and_start_keep_their_game_bindings(self):
        original = (b'input_player1_select_btn = "12"\r\n'
                    b'input_enable_hotkey_btn = "12"\r\n'
                    b'input_exit_emulator_btn = "13"\r\n'
                    b'input_player1_start_btn = "13"\r\n')
        expected = original.replace(b'input_enable_hotkey_btn = "12"',
                                    b'input_enable_hotkey_btn = "16"')
        self.assertEqual(change_hotkey(original), expected)
        self.assertEqual(change_hotkey(expected), expected)

    def test_rejects_ambiguous_or_unrecognized_modifier(self):
        for data in (b'', b'input_enable_hotkey_btn = "14"\n',
                     b'input_enable_hotkey_btn = "12"\ninput_enable_hotkey_btn = "16"\n'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                change_hotkey(data)
