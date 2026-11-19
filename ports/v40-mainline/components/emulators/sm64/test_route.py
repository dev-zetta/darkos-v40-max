#!/usr/bin/env python3
"""Verify the published launch paths in a disposable executable directory."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / "source-lock.json").read_text())


class Route(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix=".sm64-route-", dir=Path.cwd())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home/ark"
        self.target = self.root / "opt/retroarch/v40-mainline/sm64"
        self.rom = self.root / "roms/n64" / LOCK["rom"]["basename"]
        self.put(self.rom, b"fixture ROM identity")
        self.config = self.home / ".config/retroarch32/retroarch.cfg"
        self.core = self.config.parent / "cores/parallel_n64_libretro.so"
        self.put(self.config, b"shared config")
        self.put(self.core, b"shared core")
        self.put(self.target / "pacing.cfg", (HERE / "pacing.cfg").read_bytes())
        self.put(self.target / "jit/parallel_n64_libretro.so", b"private core")
        fake = (b'#!/bin/sh\nprintf "%s\\n" '
                b'"$MESA_SHADER_CACHE_DIR" "$MESA_SHADER_CACHE_MAX_SIZE" "$MESA_SHADER_CACHE_DISABLE" '
                b'"$RETROARCH_V40_DRM_WORKER" "$V40_JIT_WARMUP" "$V40_RICE_LAZY_COMBINER" '
                b'"$V40_N64_STOP_AFTER_JAL" "$@"\n')
        self.put(self.target / "retroarch32", fake, 0o755)
        rewritten = (HERE / "route.sh").read_text()
        for token in ("/home/ark", "/opt/retroarch/v40-mainline/sm64", "/roms/n64"):
            rewritten = rewritten.replace(token, str(self.root) + token)
        rewritten = rewritten.replace(LOCK["rom"]["sha256"], hashlib.sha256(self.rom.read_bytes()).hexdigest())
        self.put(self.target / "route.sh", rewritten.encode())
        self.entry = self.root / "wrapper"
        self.put(self.entry, f'#!/bin/sh\nset -eu\n. "{self.target}/route.sh"\nprintf "fallback\\n"\n'.encode())
        self.args = ["-c", str(self.config), "-L", str(self.core), str(self.rom)]
        self.cache = self.home / ".cache/v40-sm64"

    @staticmethod
    def put(path, data, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)

    def launch(self, args):
        environment = {"PATH": os.environ["PATH"], "V40_N64_STOP_AFTER_JAL": "1"}
        return subprocess.check_output(["/bin/sh", self.entry, *args],
                                       env=environment, text=True).splitlines()

    def test_qualified_title_creates_private_cache_and_uses_scoped_core(self):
        self.assertFalse(self.cache.exists())
        expected = [str(self.cache), "32M", "false", "1", "1", "1", "",
                    f"--appendconfig={self.target}/pacing.cfg",
                    "-c", str(self.config), "-L", str(self.target / "jit/parallel_n64_libretro.so"),
                    str(self.rom)]
        self.assertEqual(self.launch(self.args), expected)
        self.assertEqual(self.cache.stat().st_mode & 0o777, 0o700)
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertEqual(self.launch(self.args), expected)
        self.assertEqual(self.core.read_bytes(), b"shared core")

    def test_routes_other_launches_to_common_frontend(self):
        self.assertEqual(self.launch(self.args[:-1] + [str(self.rom.with_name("Mario Kart 64.n64"))]), ["fallback"])
        self.assertEqual(self.launch(self.args + ["--verbose"]), ["fallback"])
        changed_core = [*self.args]
        changed_core[3] = str(self.core.with_name("mupen64plus_next_libretro.so"))
        self.assertEqual(self.launch(changed_core), ["fallback"])
        self.rom.write_bytes(b"different ROM bytes under the same path")
        self.assertEqual(self.launch(self.args), ["fallback"])
        self.assertFalse(self.cache.exists())

    def test_refuses_to_use_redirected_or_public_cache(self):
        self.cache.mkdir(parents=True, mode=0o755)
        self.assertEqual(self.launch(self.args), ["fallback"])
        self.cache.rmdir()
        self.cache.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.launch(self.args), ["fallback"])


if __name__ == "__main__":
    unittest.main()
