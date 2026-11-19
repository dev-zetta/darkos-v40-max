#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

source_dir=$(realpath -- "${1:?Pass the prepared kernel source}")
kernel=$(realpath -- "${2:?Pass its completed kernel build directory}")
port=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
release=7.3.4-v40.1
manifest="$port/kernel/release-$release.json"

python3 - "$manifest" "$kernel" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

manifest = json.loads(Path(sys.argv[1]).read_text())
build = Path(sys.argv[2])
for filename, key in ((".config", "config_sha256"), ("Module.symvers", "module_symvers_sha256")):
    with (build / filename).open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest[key]:
            raise SystemExit(f"Kernel input digest mismatch for {filename}")
PY

addon="$kernel/v40-input-addon"
mkdir -- "$addon"
mkdir -- "$addon/misc"
cp -- "$source_dir/drivers/input/input-compat.h" "$addon/"
cp -- "$source_dir/drivers/input/misc/uinput.c" "$addon/misc/"
printf 'obj-m += uinput.o\n' > "$addon/misc/Makefile"
export ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
export KBUILD_BUILD_USER=codex KBUILD_BUILD_HOST=v40-mainline-builder KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='2026-11-14 00:00:00 UTC'
make -C "$source_dir" O="$kernel" M="$addon/misc" modules

module="$addon/misc/uinput.ko"
test "$(modinfo -F vermagic "$module" | cut -d ' ' -f 1)" = "$release"
"${CROSS_COMPILE}readelf" -h "$module" | grep -q 'Machine:.*AArch64'
modprobe --dump-modversions "$module" > "$addon/imports.txt"
python3 - "$kernel/Module.symvers" "$addon/imports.txt" <<'PY'
from pathlib import Path
import sys

exports = {name: int(crc, 16) for crc, name, *_ in
           (row.split() for row in Path(sys.argv[1]).read_text().splitlines())}
imports = [(name, int(crc, 16)) for crc, name in
           (row.split() for row in Path(sys.argv[2]).read_text().splitlines())]
if len(imports) != 50 or any(exports.get(name) != crc for name, crc in imports):
    raise SystemExit("uinput imports do not match the verified V40 kernel ABI")
print(f"Verified all {len(imports)} uinput symbol versions")
PY

root="$kernel/modules-root"
install -D -m 0644 "$module" "$root/lib/modules/$release/updates/v40-input/uinput.ko"
depmod -b "$root" "$release"
grep -q '^updates/v40-input/uinput.ko:' "$root/lib/modules/$release/modules.dep"
