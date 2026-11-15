#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
port_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source_dir=${1:?Pass prepared kernel source directory}
output_dir=${2:?Pass a new kernel output directory}
source_dir=$(realpath -- "$source_dir")
mkdir -- "$output_dir"
output_dir=$(realpath -- "$output_dir")
cp -- "$port_dir/kernel/config/linux-7.3.4-v40.config" "$output_dir/.config"
export KBUILD_BUILD_USER=codex KBUILD_BUILD_HOST=v40-mainline-builder KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='2026-11-14 00:00:00 UTC'
export ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
make -C "$source_dir" O="$output_dir" olddefconfig
cmp -- "$port_dir/kernel/config/linux-7.3.4-v40.config" "$output_dir/.config"
make -C "$source_dir" O="$output_dir" -j"${JOBS:-8}" Image modules rockchip/rk3326-v40-max.dtb
make -C "$source_dir" O="$output_dir" INSTALL_MOD_PATH="$output_dir/modules-root" modules_install
depmod -b "$output_dir/modules-root" 7.3.4-v40.1
sha256sum "$output_dir/arch/arm64/boot/Image" "$output_dir/arch/arm64/boot/dts/rockchip/rk3326-v40-max.dtb" "$output_dir/.config" "$output_dir/Module.symvers"
