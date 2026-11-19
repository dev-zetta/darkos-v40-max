#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the packaged PPSSPP launch guard using a disposable counter."""
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "components/ppsspp/v40-ppsspp-instance"
CLEAR_COUNTER = runpy.run_path(str(SCRIPT))["clear_counter"]
RUN_GUARD = """\
from pathlib import Path
import runpy
import sys

launch = runpy.run_path(sys.argv[1])["launch"]
try:
    launch(sys.argv[6:], launcher=Path(sys.argv[2]), counter=Path(sys.argv[3]),
           proc=Path(sys.argv[4]), lock_dir=Path(sys.argv[5]))
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(75)
"""


class InstanceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.counter = self.root / "PPSSPP_ID"
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.lock = self.root / "cache/v40-ppsspp"
        self.launcher = self.root / "launcher"
        self.started = self.root / "started"
        self.release = self.root / "release"
        self.launcher.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$1" "$2"\n'
            'if [ "$1" = standalone ]; then\n'
            '  [ ! -e "$PPSSPP_COUNTER" ] || exit 9\n'
            '  : > "$PPSSPP_STARTED"\n'
            '  while [ ! -e "$PPSSPP_RELEASE" ]; do sleep 0.02; done\n'
            "fi\n"
            "exit 17\n"
        )
        self.launcher.chmod(0o755)

    def write_counter(self):
        self.counter.write_bytes(b"\0\0\x02\x02")
        with self.counter.open("r+b") as stream:
            stream.truncate(max(4096, os.sysconf("SC_PAGE_SIZE")))

    def start(self, route):
        return subprocess.Popen(
            [sys.executable, "-B", "-c", RUN_GUARD, str(SCRIPT), str(self.launcher),
             str(self.counter), str(self.proc), str(self.lock), route, "Game title.iso"],
            env={
                **os.environ,
                "PPSSPP_COUNTER": str(self.counter),
                "PPSSPP_STARTED": str(self.started),
                "PPSSPP_RELEASE": str(self.release),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_standard_uses_legacy_arguments_and_holds_lock_during_launch(self):
        self.write_counter()
        with self.start("standalone") as first:
            try:
                deadline = time.monotonic() + 3
                while not self.started.exists() and first.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(self.started.exists())
                self.assertFalse(self.counter.exists())
                with self.start("standalone") as second:
                    try:
                        _, error = second.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        second.kill()
                        second.communicate()
                        raise
                self.assertEqual(second.returncode, 75)
                self.assertIn("Another standalone PSP launch is in progress", error)
            finally:
                self.release.touch()
            output, error = first.communicate(timeout=3)
        self.assertEqual(first.returncode, 17, error)
        self.assertEqual(output.splitlines(), [
            "V40 PPSSPP: recovered orphaned shared instance counter", "standalone", "Game title.iso",
        ])

    def test_other_route_leaves_counter_and_lock_alone(self):
        self.write_counter()
        with self.start("retroarch") as process:
            output, error = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 17, error)
        self.assertEqual(output.splitlines(), ["retroarch", "Game title.iso"])
        self.assertTrue(self.counter.is_file())
        self.assertFalse(self.lock.exists())

    def test_never_clears_counter_of_running_emulator(self):
        self.write_counter()
        emulator = self.proc / "1234"
        emulator.mkdir()
        (emulator / "exe").symlink_to("/opt/ppsspp/PPSSPPSDL (deleted)")
        with self.assertRaisesRegex(RuntimeError, "already running"):
            CLEAR_COUNTER(self.counter, self.proc, os.getuid())
        self.assertTrue(self.counter.is_file())

    def test_preserves_unexpected_counter_objects(self):
        original = self.root / "original"
        original.write_bytes(b"")
        self.counter.symlink_to(original)
        with self.assertRaisesRegex(RuntimeError, "Unexpected PPSSPP instance counter"):
            CLEAR_COUNTER(self.counter, self.proc, os.getuid())
        self.assertTrue(self.counter.is_symlink())
        self.counter.unlink()
        self.counter.write_bytes(b"unexpected")
        with self.assertRaisesRegex(RuntimeError, "Unexpected PPSSPP instance counter"):
            CLEAR_COUNTER(self.counter, self.proc, os.getuid())
        self.assertEqual(self.counter.read_bytes(), b"unexpected")
        self.counter.unlink()
        self.counter.touch()
        self.assertTrue(CLEAR_COUNTER(self.counter, self.proc, os.getuid()))
        self.assertFalse(CLEAR_COUNTER(self.counter, self.proc, os.getuid()))


if __name__ == "__main__":
    unittest.main()
