#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
if [[ $# != 2 ]]; then
    printf 'Usage: bash %s NEW_WORK OUTPUT_ROOT\n' "$0" >&2
    exit 2
fi
port=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
component="$port/components/emulators"
work=$(realpath -ms -- "$1")
root=$(realpath -ms -- "$2")
jobs=${JOBS:-$(nproc)}
if [[ "$work" == "$root" || "$work" == / || "$root" == / ||
      -e "$work" || -L "$work" || -e "$root" || -L "$root" ||
      ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
    printf '%s\n' 'Use two new paths and a positive JOBS value.' >&2
    exit 2
fi
mkdir -p -- "$work/inputs" "$root"
export LC_ALL=C
# Freeze the compile-time version strings at the hardware-tested timestamp.
export SOURCE_DATE_EPOCH=1795082646

# Verify compressed source inputs before unpacking. The optional mirror uses the same pins.
python3 - "$component/source-lock.json" "$work/inputs" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen

lock, output = map(Path, sys.argv[1:])
mirror = os.environ.get('V40_EMULATOR_SOURCE_DIR')
for item in json.loads(lock.read_text()).values():
    name = item['archive']
    path = output / name
    source = (Path(mirror) / name).open('rb') if mirror else urlopen(item['url'], timeout=90)
    with source, path.open('xb') as destination:
        shutil.copyfileobj(source, destination)
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
            raise SystemExit(f'Unexpected emulator source digest: {name}')
PY

private="$root/opt/retroarch/v40-mainline"
install -d "$private/bin" "$private/cores" "$private/mesa-armhf"
retroarch_archive="$work/inputs/RetroArch-v1.22.2.tar.gz"
common=(--enable-kms --enable-egl --enable-opengles --enable-opengles3 --enable-opengles3_1
        --enable-udev --enable-alsa --enable-zlib --disable-x11 --disable-wayland --disable-glx
        --disable-qt --disable-sdl --disable-sdl2 --disable-pulse --disable-pipewire
        --disable-vulkan --disable-ffmpeg --disable-discord)

build_retroarch() (
    local triplet=$1 name=$2
    shift 2
    mkdir "$work/$triplet"
    tar -xzf "$retroarch_archive" --strip-components=1 -C "$work/$triplet"
    cd "$work/$triplet"
    export CC="$triplet-gcc" CXX="$triplet-g++"
    export PKG_CONFIG_LIBDIR="/usr/lib/$triplet/pkgconfig:/usr/share/pkgconfig"
    export CFLAGS="-O2 -mcpu=cortex-a35 $1" CXXFLAGS="-O2 -mcpu=cortex-a35 $1"
    shift
    if [[ "$name" == retroarch ]]; then
        # The tested AArch64 build's toolchain had no Fontconfig development package.
        export HAVE_FONTCONFIG=no
    fi
    ./configure --host="$triplet" "${common[@]}" "$@" > "$work/$name-configure.log" 2>&1
    local feature
    for feature in KMS EGL OPENGLES OPENGLES3 UDEV ALSA ZLIB MENU; do
        grep -Fxq "#define HAVE_$feature 1" config.h
    done
    if [[ "$name" == retroarch ]]; then
        grep -Fxq '#define HAVE_RGUI 1' config.h
        grep -Fxq '/* #undef HAVE_FONTCONFIG */' config.h
    else
        grep -Fxq '#define HAVE_PLAIN_DRM 1' config.h
    fi
    if grep -Eq '^#define HAVE_(ODROIDGO2|RGA) 1$' config.h; then
        exit 1
    fi
    make -j"$jobs" > "$work/$name-make.log" 2>&1
    install -m 0755 retroarch "$private/bin/$name"
)

build_retroarch aarch64-linux-gnu retroarch '' --prefix=/usr \
    --enable-opengles3_2 --enable-rgui --enable-ozone --enable-xmb --enable-materialui \
    --disable-odroidgo2 --disable-jack --disable-oss
build_retroarch arm-linux-gnueabihf retroarch32 '-mfpu=neon-fp-armv8 -mfloat-abi=hard' \
    --enable-plain_drm --enable-threads --disable-cheevos

pcsx_revision=7b0e8f8fadfbce3d170d195b9d9eecaabfa08c8e
mkdir "$work/pcsx"
tar -xzf "$work/inputs/pcsx-rearmed-$pcsx_revision.tar.gz" --strip-components=1 -C "$work/pcsx"
CFLAGS='-O3 -mcpu=cortex-a35 -mfpu=neon-fp-armv8 -mfloat-abi=hard -marm' \
LDFLAGS='-Wl,-z,noexecstack' \
    make -C "$work/pcsx" -j"$jobs" -f Makefile.libretro platform=unix \
        CC=arm-linux-gnueabihf-gcc CXX=arm-linux-gnueabihf-g++ \
        AR=arm-linux-gnueabihf-ar LD=arm-linux-gnueabihf-ld \
        ARCH=arm DYNAREC=ari64 BUILTIN_GPU=neon HAVE_NEON_ASM=1 \
        GIT_VERSION="\" ${pcsx_revision:0:9}\"" > "$work/pcsx-make.log" 2>&1
pcsx="$private/cores/pcsx_rearmed_neon_libretro.so"
install -m 0755 "$work/pcsx/pcsx_rearmed_libretro.so" "$pcsx"

# ARMHF uses Debian's GLVND dispatch and GBM with the installed Mesa EGL vendor.
for library in libEGL.so.1 libGLESv2.so.2 libGLdispatch.so.0 libgbm.so.1; do
    install -m 0644 "$(readlink -e "/usr/lib/arm-linux-gnueabihf/$library")" "$private/mesa-armhf/$library"
done
ln -s libEGL.so.1 "$private/mesa-armhf/libEGL.so"
ln -s libGLESv2.so.2 "$private/mesa-armhf/libGLESv2.so"
ln -s libgbm.so.1 "$private/mesa-armhf/libgbm.so"

notices="$root/usr/local/share/v40-mainline/licenses"
install -Dm0644 "$work/aarch64-linux-gnu/COPYING" "$notices/retroarch/COPYING"
install -Dm0644 "$work/pcsx/COPYING" "$notices/pcsx_rearmed/COPYING"
install -Dm0644 /usr/share/doc/libgbm1/copyright "$notices/libgbm1-armhf/copyright"

for file in "$private/bin/retroarch32" "$pcsx" "$private/mesa-armhf/"*.so.[01-2]; do
    readelf -h "$file" > "$work/$(basename "$file").elf"
    grep -Eq 'Class:[[:space:]]+ELF32' "$work/$(basename "$file").elf"
    grep -Eq 'Machine:[[:space:]]+ARM$' "$work/$(basename "$file").elf"
    grep -q 'hard-float ABI' "$work/$(basename "$file").elf"
done
readelf -h "$private/bin/retroarch" > "$work/retroarch.elf"
grep -Eq 'Class:[[:space:]]+ELF64' "$work/retroarch.elf"
grep -Eq 'Machine:[[:space:]]+AArch64$' "$work/retroarch.elf"
readelf -Wl "$pcsx" > "$work/pcsx-stack.elf"
grep -Eq 'GNU_STACK[[:space:]].*[[:space:]]RW[[:space:]]' "$work/pcsx-stack.elf"

# Record the actual output and Debian dispatch versions used by this build.
dpkg-query -W -f='${Package}:${Architecture}\t${Version}\t${source:Package}\t${source:Version}\n' \
    libegl1:armhf libgles2:armhf libglvnd0:armhf libgbm1:armhf \
    gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf > "$work/emulator-packages.tsv"
python3 - "$component" "$root" "$work" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

component, root, work = map(Path, sys.argv[1:])
files = {}
for path in sorted(root.rglob('*')):
    if path.is_symlink():
        files[str(path.relative_to(root))] = {'link': str(path.readlink())}
    elif path.is_file():
        with path.open('rb') as stream:
            files[str(path.relative_to(root))] = {'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
launchers = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(component.glob('*-launch'))}
manifest = {'sources': json.loads((component / 'source-lock.json').read_text()),
            'files': files, 'launchers': launchers, 'source_date_epoch': int(os.environ['SOURCE_DATE_EPOCH']),
            'packages': (work / 'emulator-packages.tsv').read_text().splitlines()}
(work / 'emulator-build.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
PY

# Keep the exact upstream tarballs, local wiring, and rebuild recipes together.
tar --sort=name --mtime='UTC 2026-11-19' --owner=0 --group=0 --numeric-owner \
    -cJf "$work/emulator-sources.tar.xz" -C "$work" inputs emulator-build.json \
    -C "$port" scripts/build_image_emulators.sh \
    components/emulators/{source-lock.json,configure-image.py,retroarch-launch,retroarch32-launch,flycast-r7-launch,README.md}
xz -t "$work/emulator-sources.tar.xz"
