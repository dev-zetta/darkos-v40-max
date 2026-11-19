#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

if [[ $# != 2 ]]; then
    printf 'Usage: bash %s NEW_WORK OUTPUT_ROOT\n' "$0" >&2
    exit 2
fi

component=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
work=$(realpath -m -- "$1")
output=$(realpath -ms -- "$2")
jobs=${JOBS:-$(nproc)}
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { printf '%s\n' 'Invalid JOBS' >&2; exit 2; }
mkdir -- "$work"
mkdir -p -- "$output"
[[ "$(realpath -- "$output")" == "$output" ]]
target=opt/retroarch/v40-mainline/sm64
documentation=usr/local/share/v40-mainline/emulators/sm64
for relative in "$target" "$documentation"; do
    [[ ! -e "$output/$relative" && ! -L "$output/$relative" ]]
    [[ "$(realpath -m -- "$output/${relative%/*}")" == "$output/${relative%/*}" ]]
done

export LC_ALL=C.UTF-8 SOURCE_DATE_EPOCH=1763600000
export PKG_CONFIG_LIBDIR=/usr/lib/arm-linux-gnueabihf/pkgconfig:/usr/share/pkgconfig
mkdir -- "$work/upstream" "$work/retroarch" "$work/parallel-n64"
python3 - "$component" "$work" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

component, work = map(Path, sys.argv[1:])
lock = json.loads((component / "source-lock.json").read_text())
mirror = os.environ.get("V40_EMULATOR_SOURCE_DIR")


def verify(path, expected):
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise SystemExit(f"SHA-256 mismatch for {path.name}: {actual}")


for name, digest in lock["file_hashes"].items():
    verify(component / name, digest)

rom = lock["rom"]
profile = (component / "jit-warm-profile.h").read_text()
if (f'"{rom["md5"]}"' not in profile or profile.count("{UINT32_C(") != rom["profile_blocks"] or
        rom["sha256"] not in (component / "route.sh").read_text()):
    raise SystemExit("The core profile and launcher ROM pins must agree")

for key, directory in [("retroarch", "retroarch"), ("parallel_n64", "parallel-n64")]:
    source = lock[key]
    archive = work / "upstream" / source["name"]
    if mirror:
        shutil.copyfile(Path(mirror) / source["name"], archive)
    else:
        with urlopen(source["url"], timeout=90) as remote, archive.open("xb") as dest:
            shutil.copyfileobj(remote, dest)
    verify(archive, source["sha256"])
    tree = work / directory
    subprocess.run(["tar", "-xzf", archive, "--strip-components=1", "-C", tree], check=True)
    for patch in source["patches"]:
        subprocess.run(["patch", "--batch", "--forward", "-p1", "-i",
                        component / "patches" / patch], cwd=tree, check=True)

dynarec = work / "parallel-n64/mupen64plus-core/src/r4300/new_dynarec"
for name in ["jit-warm-dispatch.h", "jit-warm-profile.h"]:
    shutil.copyfile(component / name, dynarec / name)
PY

triplet=arm-linux-gnueabihf
map="-ffile-prefix-map=$work=/usr/src/v40-sm64"
(
    cd -- "$work/retroarch"
    export CFLAGS="-O2 -mcpu=cortex-a35 -mfpu=neon-fp-armv8 -mfloat-abi=hard $map"
    export CXXFLAGS="$CFLAGS"
    export LDFLAGS=-Wl,-z,noexecstack
    ./configure --host="$triplet" \
        --enable-kms --enable-plain_drm --enable-egl --enable-opengles \
        --enable-opengles3 --enable-opengles3_1 --enable-udev --enable-alsa \
        --enable-threads --enable-zlib \
        --disable-x11 --disable-wayland --disable-glx --disable-qt \
        --disable-sdl --disable-sdl2 --disable-pulse --disable-pipewire \
        --disable-vulkan --disable-ffmpeg --disable-cheevos --disable-discord
    for flag in KMS EGL OPENGLES UDEV ALSA; do
        grep -Fx "HAVE_$flag = 1" config.mk
    done
    make -j"$jobs"
) >"$work/retroarch-build.log" 2>&1 || { tail -n 60 "$work/retroarch-build.log"; exit 1; }

(
    export CFLAGS="-g -Wno-error=implicit-int -DV40_TRACE_DYNAREC $map"
    export CXXFLAGS="-g $map"
    export LDFLAGS=-Wl,-z,noexecstack
    make -C "$work/parallel-n64" -j"$jobs" platform=Odroidgoa DEBUG=0 \
        CC="$triplet-gcc" CXX="$triplet-g++" AR="$triplet-ar" GIT_VERSION='" 1922f4a6"'
) >"$work/parallel-n64-build.log" 2>&1 || { tail -n 60 "$work/parallel-n64-build.log"; exit 1; }

ra="$work/retroarch/retroarch"
core="$work/parallel-n64/parallel_n64_libretro.so"
for elf in "$ra" "$core"; do
    "$triplet-readelf" -h "$elf" | grep -E 'Flags:.*Version5 EABI, hard-float ABI'
    "$triplet-readelf" -Wl "$elf" | grep -E 'GNU_STACK[[:space:]].*[[:space:]]RW[[:space:]]'
    "$triplet-readelf" -d "$elf" | grep -F 'Shared library: [libGLESv2.so.2]'
done
"$triplet-readelf" -Wl "$ra" | grep -F '[Requesting program interpreter: /lib/ld-linux-armhf.so.3]'
"$triplet-readelf" -h "$core" | grep -E 'Type:[[:space:]]+DYN'
core_symbols=$("$triplet-readelf" --dyn-syms --wide "$core")
for symbol in retro_init retro_get_system_info retro_load_game retro_run; do
    grep -Eq "[[:space:]]GLOBAL[[:space:]]+DEFAULT[[:space:]]+[0-9]+[[:space:]]+$symbol$" <<<"$core_symbols"
done
sh -n "$component/route.sh"

stage="$work/overlay"
install -Dm0755 "$ra" "$stage/$target/retroarch32"
install -Dm0644 "$core" "$stage/$target/jit/parallel_n64_libretro.so"
install -Dm0644 "$component/route.sh" "$stage/$target/route.sh"
install -Dm0644 "$component/pacing.cfg" "$stage/$target/pacing.cfg"
install -Dm0644 "$component/README.md" "$stage/$documentation/README.md"
install -Dm0644 "$work/retroarch/COPYING" "$stage/$documentation/RetroArch-COPYING"
for path in mupen64plus-core/LICENSES mupen64plus-core/doc/gpl-license \
            mupen64plus-rsp-cxd4/COPYING gles2n64/src/COPYING \
            mupen64plus-rsp-paraLLEl/LICENSE mupen64plus-video-paraLLEl/parallel-rdp/LICENSE; do
    install -Dm0644 "$work/parallel-n64/$path" "$stage/$documentation/ParaLLEl-N64/$path"
done

python3 - "$component" "$work" "$target" "$documentation" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

component, work = map(Path, sys.argv[1:3])
target, documentation = sys.argv[3:]
stage = work / "overlay"
report = {
    "sources": json.loads((component / "source-lock.json").read_text()),
    "compiler": subprocess.check_output(["arm-linux-gnueabihf-gcc", "--version"], text=True).splitlines()[0],
    "packages": dict(item.split("\t") for item in subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Package}:${Architecture}\t${Version}\n"], text=True).splitlines()),
    "enabled_features": ["RETROARCH_V40_DRM_WORKER", "V40_JIT_WARMUP", "V40_RICE_LAZY_COMBINER"],
    "shader_cache": "generated during ordinary play on the target",
    "hardware_tested": False,
    "files": {},
}
for relative in sorted((stage / target).rglob("*")):
    if relative.is_file():
        with relative.open("rb") as stream:
            report["files"][str(relative.relative_to(stage))] = hashlib.file_digest(stream, "sha256").hexdigest()
data = json.dumps(report, indent=2, sort_keys=True) + "\n"
(work / "sm64-build.json").write_text(data)
(stage / documentation / "build.json").write_text(data)
PY

sources="$work/sm64-sources"
mkdir -- "$sources"
cp -a -- "$work/upstream" "$sources/"
cp -a -- "$component"/{build.sh,source-lock.json,README.md,route.sh,pacing.cfg,patches,jit-warm-dispatch.h,jit-warm-profile.h} "$sources/"
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
    --mode='u+rwX,go+rX,go-w' -cf - -C "$work" sm64-sources |
    xz -T2 -3 > "$work/sm64-sources.tar.xz"

for relative in "$target" "$documentation"; do
    mkdir -p -- "$output/${relative%/*}"
    cp -aT --no-clobber "$stage/$relative" "$output/$relative"
done
