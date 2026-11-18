#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

if [[ $# != 2 ]]; then
    printf 'Usage: bash %s WORK_DIRECTORY OUTPUT_ROOT_OVERLAY\n' "$0" >&2
    exit 2
fi

port_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=$(realpath -m -- "$1")
output=$(realpath -ms -- "$2")
jobs=${JOBS:-$(nproc)}
if [[ ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
    printf 'JOBS must be a positive integer\n' >&2
    exit 2
fi
mkdir -p -- "$work"
if [[ -n $(ls -A -- "$work") || -e "$output" || -L "$output" ]]; then
    printf 'Use an empty work directory and a new overlay path\n' >&2
    exit 2
fi
mkdir -p -- "$work/source" "$work/mesa-archives"
export LC_ALL=C.UTF-8
export GIT_TERMINAL_PROMPT=0
# Mesa uses the Debian Python modules rather than the device-tree tool's venv.
export PATH=/usr/bin:/bin
dpkg-query -W -f='${Package}:${Architecture}\t${Version}\n' > "$work/toolchain-packages.tsv"

# The optional mirrors let offline builds reuse the same verified public inputs.
# Each component is replayed in a new checkout and checked against the locked tree.
python3 - "$port_dir" "$work" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

port, work = map(Path, sys.argv[1:])
mirror = os.environ.get("V40_COMPONENT_SOURCE_DIR")
for component in json.loads((port / "components/source-lock.json").read_text()):
    name = component["component"]
    source = work / "source" / name
    remote = Path(mirror) / name if mirror else component["repository"]

    subprocess.run(["git", "init", "-q", source], check=True)
    git = ["git", "-C", str(source), "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*git, "fetch", "--no-tags", "--depth=1", remote, component["base_commit"]], check=True)
    subprocess.run([*git, "checkout", "-q", "--detach", "FETCH_HEAD"], check=True)
    base = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    if base != component["base_commit"]:
        raise SystemExit(f"{name} checkout does not match locked base")

    patches = [port / "components" / name / filename for filename in component["patches"]]
    subprocess.run(
        [*git, "-c", "user.name=V40 Build", "-c", "user.email=builder@example.invalid",
         "am", "--keep-cr", "--committer-date-is-author-date", *patches],
        check=True,
    )
    tree = subprocess.check_output([*git, "rev-parse", "HEAD^{tree}"], text=True).strip()
    if tree != component["accepted_tree"]:
        raise SystemExit(f"{name} patch replay produced unexpected tree {tree}")
    for submodule, revision in component.get("submodules", {}).items():
        locked = subprocess.check_output([*git, "rev-parse", f"HEAD:{submodule}"], text=True).strip()
        if locked != revision:
            raise SystemExit(f"Unexpected gitlink for {name}/{submodule}: {locked}")
        options = []
        if mirror:
            options = ["-c", "protocol.file.allow=always",
                       "-c", f"submodule.{submodule}.url={Path(mirror) / name / submodule}"]
        subprocess.run([*git, *options, "submodule", "update", "--init", "--depth=1", "--", submodule], check=True)
        head = subprocess.check_output(["git", "-C", source / submodule, "rev-parse", "HEAD"], text=True).strip()
        if head != revision:
            raise SystemExit(f"{name}/{submodule} checkout does not match locked revision")

archive_mirror = os.environ.get("V40_MESA_ARCHIVE_DIR")
mesa_lock = json.loads((port / "graphics/source-lock.json").read_text())
for item in mesa_lock["files"]:
    archive = work / "mesa-archives" / item["name"]
    if archive_mirror:
        shutil.copyfile(Path(archive_mirror) / item["name"], archive)
    else:
        with urlopen(item["url"], timeout=60) as remote, archive.open("xb") as output:
            shutil.copyfileobj(remote, output)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != item["sha256"]:
        raise SystemExit(f"Mesa source digest mismatch: {archive.name}")

descriptor = next((work / "mesa-archives").glob("*.dsc"))
mesa = work / "source/mesa"
# The descriptor and every archive it names have already passed the sealed digest checks.
subprocess.run(["dpkg-source", "--no-check", "-x", descriptor, mesa], check=True)
(mesa / "VERSION").write_text(mesa_lock["local_version"] + "\n")
PY

graphics_root="$work/graphics-root"
prefix=/usr/local/lib/v40-mainline
private="$graphics_root$prefix"
glvnd_packages=(libegl1 libgles1 libgles2 libglvnd0 libgl1 libglx0 libopengl0)
for triplet in aarch64-linux-gnu arm-linux-gnueabihf; do
    case "$triplet" in
        aarch64-linux-gnu)
            arch=arm64
            cpu=aarch64
            cpu_flags="'-march=armv8-a', '-mtune=cortex-a35'"
            ;;
        arm-linux-gnueabihf)
            arch=armhf
            cpu=arm
            cpu_flags="'-march=armv7-a', '-mfpu=neon-vfpv4', '-mfloat-abi=hard', '-mtune=cortex-a35'"
            ;;
    esac
    export PKG_CONFIG_LIBDIR="/usr/lib/$triplet/pkgconfig:/usr/share/pkgconfig"

    # Build a Mesa-compatible SDL2 for each emulator ABI.
    toolchain="$work/$triplet.cmake"
    cat > "$toolchain" <<EOF
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR $cpu)
set(CMAKE_C_COMPILER $triplet-gcc)
set(CMAKE_CXX_COMPILER $triplet-g++)
set(CMAKE_FIND_ROOT_PATH /usr/$triplet)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
EOF
    sdl_build="$work/sdl-$triplet"
    cmake -S "$work/source/sdl" -B "$sdl_build" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$toolchain" -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DCMAKE_SKIP_RPATH=ON -DCMAKE_INSTALL_PREFIX="$prefix" \
        -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TEST=OFF \
        -DSDL_KMSDRM=ON -DSDL_KMSDRM_SHARED=ON -DSDL_OFFSCREEN=ON \
        -DGBM_LIB="/usr/lib/$triplet/libgbm.so" -DDRM_LIB="/usr/lib/$triplet/libdrm.so" \
        -DSDL_X11=OFF -DSDL_WAYLAND=OFF -DSDL_PULSEAUDIO=OFF -DSDL_PIPEWIRE=OFF \
        -DSDL_JACK=OFF -DSDL_SNDIO=OFF -DSDL_ARTS=OFF -DSDL_ESD=OFF
    sdl_config="$sdl_build/include-config-relwithdebinfo/SDL2/SDL_config.h"
    grep -Fxq '#define SDL_VIDEO_DRIVER_KMSDRM_DYNAMIC_GBM "libgbm.so.1"' "$sdl_config"
    grep -Fxq '#define SDL_AUDIO_DRIVER_ALSA 1' "$sdl_config"
    cmake --build "$sdl_build" --parallel "$jobs"

    # The distribution Mesa libraries omit GLES1, which this frontend uses.
    cross_file="$work/$triplet.meson"
    cat > "$cross_file" <<EOF
[binaries]
c = '$triplet-gcc'
cpp = '$triplet-g++'
ar = '$triplet-ar'
strip = '$triplet-strip'
pkg-config = 'pkg-config'
[host_machine]
system = 'linux'
cpu_family = '$cpu'
cpu = 'cortex-a35'
endian = 'little'
[properties]
needs_exe_wrapper = true
[built-in options]
c_args = [$cpu_flags]
cpp_args = [$cpu_flags]
pkg_config_path = ['/usr/lib/$triplet/pkgconfig', '/usr/share/pkgconfig']
EOF
    mesa_build="$work/mesa-$triplet"
    meson setup "$mesa_build" "$work/source/mesa" --cross-file "$cross_file" \
        --prefix="$prefix" --libdir="lib/$triplet" --buildtype=release \
        -Dplatforms=x11 -Dgallium-drivers=panfrost,softpipe -Dvulkan-drivers= \
        -Dglx=dri -Degl=enabled -Dgbm=enabled -Dglvnd=enabled \
        -Dgles1=enabled -Dgles2=enabled -Dopengl=true -Dshared-glapi=enabled \
        -Dllvm=disabled -Dgallium-va=disabled -Dgallium-vdpau=disabled \
        -Dgallium-opencl=disabled -Dgallium-rusticl=false -Dgallium-nine=false -Dgallium-xa=disabled \
        -Dvideo-codecs= -Dbuild-tests=false -Dtools= -Dteflon=false -Dlibunwind=disabled -Dlmsensors=disabled
    ninja -C "$mesa_build" -j "$jobs"
    DESTDIR="$graphics_root" meson install -C "$mesa_build" --no-rebuild --strip

    libs="$private/lib/$triplet"
    # Copy only the authenticated Debian GLVND dispatch libraries. Mesa itself
    # came from the source build above, so no distro DRI or proprietary Mali is used.
    for package in "${glvnd_packages[@]}"; do
        dpkg-query -W -f='${Package}:${Architecture}\t${Version}\n' "$package:$arch" >> "$work/glvnd-packages.tsv"
        dpkg-query -L "$package:$arch" |
            awk -v prefix="/usr/lib/$triplet/" 'index($0,prefix)==1 && /\.so(\.|$)/' |
            while IFS= read -r library; do cp -a -- "$library" "$libs/"; done
    done
    ln -sfn libEGL.so.1 "$libs/libEGL.so"
    ln -sfn libGLESv1_CM.so.1 "$libs/libGLESv1_CM.so"
    ln -sfn libGLESv2.so.2 "$libs/libGLESv2.so"
    ln -sfn libgbm.so.1 "$libs/libgbm.so"

    sdl="$libs/libSDL2-2.0.so.0.3200.10"
    install -m 0644 "$sdl_build/${sdl##*/}" "$sdl"
    "$triplet-strip" --strip-unneeded "$sdl"
    ln -s "${sdl##*/}" "$libs/libSDL2-2.0.so.0"
    ln -s libSDL2-2.0.so.0 "$libs/libSDL2.so"

    "$triplet-gcc" -shared -fPIC -O2 -Wl,-soname,libMali.so -Wl,-z,defs \
        "$port_dir/graphics/mesa-legacy-soname.c" -o "$libs/libMali.so" \
        -Wl,--no-as-needed "/usr/lib/$triplet/libEGL.so.1" "/usr/lib/$triplet/libGLESv1_CM.so.1" \
        "/usr/lib/$triplet/libGLESv2.so.2" "/usr/lib/$triplet/libgbm.so.1"
    ln -s libMali.so "$libs/libMali.so.1"
done

export PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig
frontend="$work/source/frontend"
cmake -S "$frontend" -B "$work/frontend" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$work/aarch64-linux-gnu.cmake" \
    -DCMAKE_BUILD_TYPE=Release -DGLES=ON -DCEC=OFF -DENABLE_MPP_VIDEO=OFF \
    -DFreeImage_INCLUDE_DIRS=/usr/include -DFreeImage_LIBRARIES=/usr/lib/aarch64-linux-gnu/libfreeimage.so \
    -DCMAKE_CXX_FLAGS='-march=armv8-a -mtune=cortex-a35' -DCMAKE_SKIP_RPATH=ON
cmake --build "$work/frontend" --parallel "$jobs"

export CARGO_HOME="$work/cargo-home"
export CARGO_TARGET_DIR="$work/hotkey-target"
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc
export PKG_CONFIG_ALLOW_CROSS=1
if [[ -n "${V40_CARGO_HOME:-}" ]]; then
    mkdir -p "$CARGO_HOME/registry"
    cp -a --reflink=auto "$V40_CARGO_HOME"/registry/{cache,index} "$CARGO_HOME/registry/"
fi
hotkey_manifest="$work/source/hotkey/Cargo.toml"
cargo metadata --manifest-path "$hotkey_manifest" --locked --format-version 1 \
    --filter-platform aarch64-unknown-linux-gnu > "$work/hotkey-metadata.json"

# The registry tarball includes libevdev sources without its submodule metadata.
# Use Debian's ARM64 libevdev via the cross-architecture pkg-config paths above.
python3 - "$port_dir" "$work" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib

port, work = map(Path, sys.argv[1:])
packages = json.loads((work / "hotkey-metadata.json").read_text())["packages"]
lock = tomllib.loads((work / "source/hotkey/Cargo.lock").read_text())
locked_checksums = {(p["name"], p["version"]): p["checksum"] for p in lock["package"] if "checksum" in p}
cargo_registry = Path(os.environ["CARGO_HOME"]) / "registry"
crates = work / "hotkey-crates"
crates.mkdir()
registry_sources = {}
for package in packages:
    if package["source"] is None:
        continue
    source = Path(package["manifest_path"]).parent
    name = package["name"]
    version = package["version"]
    archive = cargo_registry / "cache" / source.parent.name / f"{name}-{version}.crate"
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != locked_checksums[name, version]:
        raise SystemExit(f"Registry archive digest mismatch: {archive.name}")
    shutil.copyfile(archive, crates / archive.name)
    registry_sources[archive.name] = digest

    if (name, version) == ("evdev-sys", "0.2.2"):
        # Patch the verified build script in this build's isolated Cargo cache.
        with tarfile.open(archive) as tar:
            upstream_build_script = tar.extractfile("evdev-sys-0.2.2/build.rs").read()
        build_script = source / "build.rs"
        if build_script.read_bytes() != upstream_build_script:
            raise SystemExit("Extracted evdev-sys build script differs from its registry archive")
        patch = port / "components/hotkey/evdev-sys-cross-pkg-config.patch"
        subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", patch], cwd=source, check=True)

(work / "hotkey-crates.json").write_text(json.dumps(registry_sources, sort_keys=True, indent=2) + "\n")
PY
cargo build --manifest-path "$hotkey_manifest" --locked --offline --release \
    --target aarch64-unknown-linux-gnu --jobs "$jobs"
hotkey="$CARGO_TARGET_DIR/aarch64-unknown-linux-gnu/release/ogage"
aarch64-linux-gnu-readelf -d "$hotkey" | grep -Fq 'Shared library: [libevdev.so.2]'

overlay="$work/overlay"
python3 "$port_dir/scripts/stage_runtime.py" --frontend "$frontend/emulationstation" \
    --resources "$frontend/resources" --hotkey "$hotkey" \
    --graphics-root "$graphics_root" --output "$overlay"

notices="$overlay/usr/local/share/v40-mainline/licenses"
install -Dm0644 "$frontend/LICENSE.md" "$notices/frontend/LICENSE.md"
install -Dm0644 "$frontend/opensans_license.txt" "$notices/frontend/opensans_license.txt"
install -Dm0644 "$frontend/external/pugixml/LICENSE.md" "$notices/frontend/pugixml-LICENSE.md"
install -Dm0644 "$work/source/sdl/LICENSE.txt" "$notices/SDL2-LICENSE.txt"
install -Dm0644 "$work/source/hotkey/LICENSE" "$notices/ogage/LICENSE"
install -Dm0644 "$work/source/mesa/debian/copyright" "$notices/mesa/copyright"
for package in "${glvnd_packages[@]}"; do
    install -Dm0644 "/usr/share/doc/$package/copyright" "$notices/$package/copyright"
done

# Exercise both ELF loaders and software GLES1 without claiming display or hardware acceptance.
mkdir -p -- "$work/smoke-home"
for triplet in aarch64-linux-gnu arm-linux-gnueabihf; do
    case "$triplet" in
        aarch64-linux-gnu) emulator=qemu-aarch64; cpu=cortex-a35 ;;
        arm-linux-gnueabihf) emulator=qemu-arm; cpu=cortex-a15 ;;
    esac
    libs="$overlay$prefix/lib/$triplet"
    loader_probe="$work/loader-$triplet"
    gles_probe="$work/gles1-$triplet"
    "$triplet-gcc" -Wall -Wextra -Werror -O2 "$port_dir/graphics/runtime-loader-probe.c" -ldl -o "$loader_probe"
    "$triplet-gcc" -Wall -Wextra -Werror -O2 "$port_dir/graphics/gles1-context-probe.c" -o "$gles_probe" \
        "/usr/lib/$triplet/libEGL.so.1" "/usr/lib/$triplet/libGLESv1_CM.so.1"
    env_args=(
        -E "LD_LIBRARY_PATH=$libs:/usr/lib/$triplet"
        -E "HOME=$work/smoke-home"
        -E "__EGL_VENDOR_LIBRARY_FILENAMES=$overlay/usr/local/share/v40-mainline/50_mesa.json"
        -E "LIBGL_DRIVERS_PATH=$libs/dri"
        -E "GBM_BACKENDS_PATH=$libs/gbm"
        -E GALLIUM_DRIVER=softpipe -E LIBGL_ALWAYS_SOFTWARE=1 -E LP_NUM_THREADS=1
    )
    timeout 45 "$emulator" -cpu "$cpu" -L / "${env_args[@]}" "$loader_probe" \
        libEGL.so.1 libEGL_mesa.so.0 libGLESv1_CM.so.1 libGLESv2.so.2 libgbm.so.1 \
        libGL.so.1 libGLX_mesa.so.0 libMali.so libSDL2-2.0.so.0 \
        "$libs/dri/panfrost_dri.so" "$libs/gbm/dri_gbm.so"
    timeout 45 "$emulator" -cpu "$cpu" -L / "${env_args[@]}" "$gles_probe"
done
timeout 45 qemu-aarch64 -cpu cortex-a35 -L / \
    -E "LD_LIBRARY_PATH=$overlay$prefix/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu" \
    -E "HOME=$work/smoke-home" "$overlay$prefix/emulationstation" --help

python3 - "$port_dir" "$work" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

port, work = map(Path, sys.argv[1:])
overlay = work / "overlay"
files = {}
for path in sorted(overlay.rglob("*")):
    record = None
    if path.is_symlink():
        record = {"symlink": str(path.readlink())}
    elif path.is_file():
        with path.open("rb") as stream:
            record = {"sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
    if record is not None:
        files[str(path.relative_to(overlay))] = record
report = {
    "components": json.loads((port / "components/source-lock.json").read_text()),
    "mesa": json.loads((port / "graphics/source-lock.json").read_text()),
    "hotkey_registry": json.loads((work / "hotkey-crates.json").read_text()),
    "hotkey_libevdev_correction_sha256": hashlib.sha256(
        (port / "components/hotkey/evdev-sys-cross-pkg-config.patch").read_bytes()
    ).hexdigest(),
    "glvnd_packages": dict(line.split("\t") for line in (work / "glvnd-packages.tsv").read_text().splitlines()),
    "toolchain_packages": dict(line.split("\t") for line in (work / "toolchain-packages.tsv").read_text().splitlines()),
    "qemu_checks": ["aarch64-library-loader", "armhf-library-loader", "aarch64-gles1", "armhf-gles1", "frontend-help"],
    "files": files,
}
(work / "runtime-build.json").write_text(json.dumps(report, indent=2) + "\n")
PY

sources="$work/runtime-sources"
mkdir -p "$sources"/{frontend,sdl,hotkey,build-inputs/scripts}
for component in frontend sdl hotkey; do
    git -C "$work/source/$component" archive HEAD | tar -xf - -C "$sources/$component"
done
mkdir -p "$sources/frontend/external/pugixml"
git -C "$frontend/external/pugixml" archive HEAD | tar -xf - -C "$sources/frontend/external/pugixml"
cp -a "$work"/{mesa-archives,hotkey-crates,hotkey-crates.json,runtime-build.json} "$sources/"
cp -a "$port_dir"/{Dockerfile,components,graphics,runtime} "$sources/build-inputs/"
cp -a "$port_dir"/scripts/{build_image_runtime.sh,stage_runtime.py} "$sources/build-inputs/scripts/"
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf - -C "$work" runtime-sources |
    xz -T2 -3 > "$work/runtime-sources.tar.xz"

mkdir -p -- "$(dirname -- "$output")"
mv -T --no-clobber -- "$overlay" "$output"
test ! -e "$overlay"
