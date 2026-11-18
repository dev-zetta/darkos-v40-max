#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
    printf 'Usage: bash %s WORK_DIRECTORY OUTPUT_PPSSPP_DIRECTORY [SOURCE_ARCHIVE]\n' "$0" >&2
    exit 2
fi

version=1.20.4
archive_name=ppsspp-$version.tar.xz
archive_url=https://github.com/hrydgard/ppsspp/releases/download/v$version/$archive_name
archive_sha256=4de21db3105d9d81a465a8a7e78c68ee3c0e0bf6597d1c1d530f7555f3ad8b31
work=$(realpath -m -- "$1")
output=$(realpath -m -- "$2")
jobs=${JOBS:-$(nproc)}
if [[ ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
    printf 'JOBS must be a positive integer\n' >&2
    exit 2
fi
mkdir -p -- "$work"
if [[ -n $(ls -A -- "$work") || -e "$output" || -L "$output" ]]; then
    printf 'Use an empty work directory and a new PPSSPP output path\n' >&2
    exit 2
fi

archive="$work/$archive_name"
if (( $# == 3 )); then
    cp -- "$3" "$archive"
else
    python3 - "$archive_url" "$archive" <<'PY'
import shutil
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=120) as source, open(sys.argv[2], "xb") as destination:
    shutil.copyfileobj(source, destination)
PY
fi
printf '%s  %s\n' "$archive_sha256" "$archive" | sha256sum --check --strict -

source="$work/source"
build="$work/build"
triplet=aarch64-linux-gnu
export LC_ALL=C.UTF-8
export PKG_CONFIG_LIBDIR="/usr/lib/$triplet/pkgconfig:/usr/share/pkgconfig"
unset FFMPEG_DIR PKG_CONFIG_PATH
mkdir -- "$source"
tar -xJf "$archive" -C "$source" --strip-components=1 --no-same-owner --no-same-permissions

# The release archive includes the fork's FFmpeg source. Use upstream's decoder
# selection for PSP media and build the ARM64 libraries from that same archive.
(
    cd -- "$source/ffmpeg"
    MAKEFLAGS="-j$jobs" bash linux_arm64.sh
)

toolchain="$work/aarch64.cmake"
cat > "$toolchain" <<'EOF'
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
EOF

# Match the handheld's SDL/OpenGL ES launcher. Its runtime chooses the private
# KMSDRM SDL2, Mesa and ALSA libraries through the V40 environment.
cmake -S "$source" -B "$build" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_SKIP_RPATH=ON -DCMAKE_INSTALL_PREFIX=/usr \
    -DUSING_EGL=ON -DUSING_GLES2=ON -DUSING_X11_VULKAN=OFF -DUSE_WAYLAND_WSI=OFF \
    -DUSE_SYSTEM_LIBSDL2=ON -DUSE_SYSTEM_FFMPEG=OFF -DUSE_FFMPEG=ON \
    -DFFMPEG_DIR="$source/ffmpeg/linux/aarch64" \
    -DGOLD=OFF -DHEADLESS=OFF -DUNITTEST=OFF -DATLAS_TOOL=OFF -DUSE_DISCORD=OFF
cmake --build "$build" --target PPSSPPSDL --parallel "$jobs"

binary="$work/PPSSPPSDL"
assets="$build/assets"
# Only stage the emulator and its data. The general CMake install also installs
# development targets that aren't built by the standalone emulator target.
"$triplet-strip" --strip-unneeded -o "$binary" "$build/PPSSPPSDL"
readelf -h "$binary" > "$work/elf-header.txt"
readelf -d "$binary" > "$work/elf-dynamic.txt"
grep -Eq 'Machine: +AArch64$' "$work/elf-header.txt"
for library in libSDL2-2.0.so.0 libSDL2_ttf-2.0.so.0 libfontconfig.so.1 libEGL.so.1 libGLESv2.so.2; do
    grep -Fq "Shared library: [$library]" "$work/elf-dynamic.txt"
done
test -s "$assets/gamecontrollerdb.txt"
test -s "$assets/compat.ini"

mkdir -p -- "$output"
install -m0755 "$binary" "$output/PPSSPPSDL"
# Match the upstream Linux asset install's exclusions.
tar -C "$build" --exclude='.git*' --exclude=assets/mime --exclude=assets/lang/README.md -cf - assets | \
    tar -C "$output" -xf - --no-same-owner --no-same-permissions
install -m0644 "$source/LICENSE.TXT" "$output/LICENSE.TXT"
install -m0644 "$source/ffmpeg/COPYING.LGPLv2.1" "$output/FFMPEG-LICENSE.txt"
