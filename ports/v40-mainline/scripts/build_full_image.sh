#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
trap 'printf "Image build failed near line %s.\n" "$LINENO" >&2' ERR

if (( $# < 5 || $# > 7 )); then
  printf 'Usage: sudo bash %s NEW_WORK KERNEL_PAYLOAD RUNTIME_ROOT PPSSPP NEW_OUTPUT [LOCKED_BASE [LOCKED_DEB_CACHE]]\n' "$0" >&2
  exit 2
fi
if [[ $EUID != 0 ]]; then
  printf '%s\n' 'The image assembly needs root to mount its disposable loop partitions.' >&2
  exit 2
fi

port=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repo=$(cd -- "$port/../.." && pwd)
lock="$port/image-inputs.json"
work=$(realpath -m -- "$1")
kernel=$(realpath -- "$2")
runtime=$(realpath -- "$3")
ppsspp=$(realpath -- "$4")
out=$(realpath -m -- "$5")
if [[ -e "$work" || -L "$work" || -e "$out" || -L "$out" ]]; then
  printf '%s\n' 'Use new scratch and output directories.' >&2
  exit 2
fi
mkdir -p -- "$work"/{downloads,mount-root,mount-roms,roms,firmware} "$out"

download() {
  local url=$1 digest=$2 destination=$3
  curl --fail --location --retry 3 --output "$destination" "$url"
  printf '%s  %s\n' "$digest" "$destination" | sha256sum -c -
}

get_deb() {
  local key=$1 output_file=$2
  local digest
  digest=$(jq -er --arg key "$key" '.[$key].sha256' "$lock")
  if [[ -n "$deb_cache" ]]; then
    install -m 0644 "$deb_cache/$output_file" "$work/downloads/$output_file"
    printf '%s  %s\n' "$digest" "$work/downloads/$output_file" | sha256sum -c -
  else
    download "$(jq -er --arg key "$key" '.[$key].url' "$lock")" "$digest" "$work/downloads/$output_file"
  fi
}

loop=
created_nodes=()
cleanup() {
  if mountpoint -q "$work/mount-roms"; then umount "$work/mount-roms"; fi
  if mountpoint -q "$work/mount-root"; then umount "$work/mount-root"; fi
  if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
  if (( ${#created_nodes[@]} )); then rm -- "${created_nodes[@]}"; fi
}
trap cleanup EXIT

if (( $# >= 6 )); then
  base=$(realpath -- "$6")
  if [[ "$base" == *.img ]]; then
    printf '%s  %s\n' "$(jq -er .base_image_sha256 "$lock")" "$base" | sha256sum -c -
    cp --reflink=auto --sparse=always -- "$base" "$work/base.img"
  else
    printf '%s  %s\n' "$(jq -er .base_archive_sha256 "$lock")" "$base" | sha256sum -c -
    xz --decompress --stdout -- "$base" | dd of="$work/base.img" bs=1M conv=sparse status=none
  fi
else
  python3 "$port/scripts/stream_base_image.py" "$work/downloads" |
    xz --decompress --stdout |
    dd of="$work/base.img" bs=1M conv=sparse status=none
fi

deb_cache=${7:-}
get_deb busybox busybox.deb
get_deb realtek_firmware realtek.deb
dpkg-deb -x "$work/downloads/busybox.deb" "$work/busybox"
dpkg-deb -x "$work/downloads/realtek.deb" "$work/realtek"
for file in rtw89/rtw8851b_fw-1.bin rtl_bt/rtl8851bu_fw.bin rtl_bt/rtl8851bu_config.bin; do
  mkdir -p -- "$work/firmware/$(dirname -- "$file")"
  source="$work/realtek/usr/lib/firmware/$file"
  if [[ -f "$source" ]]; then
    cp -- "$source" "$work/firmware/$file"
  else
    zstd --quiet --decompress --stdout < "$source.zst" > "$work/firmware/$file"
  fi
done
printf '%s  %s\n' "$(jq -er .realtek_firmware.rtl8851bu_wlan_sha256 "$lock")" \
  "$work/firmware/rtw89/rtw8851b_fw-1.bin" | sha256sum -c -

loop=$(losetup --find --show --partscan "$work/base.img")
if command -v udevadm >/dev/null; then udevadm settle; fi
for index in 2 3; do
  node="${loop}p$index"
  if [[ ! -b "$node" ]]; then
    IFS=: read -r major minor < "/sys/class/block/${node##*/}/dev"
    mknod "$node" b "$major" "$minor"
    created_nodes+=("$node")
  fi
done
test "$(blkid -p -s LABEL -o value "${loop}p2")" = ROOTFS
test "$(blkid -p -s LABEL -o value "${loop}p3")" = EASYROMS
printf 'Verified disposable base partitions on %s.\n' "$loop"
mount -t btrfs -o nosuid,nodev,nospace_cache,subvolid=5 "${loop}p2" "$work/mount-root"
mount -o ro,nosuid,nodev,noexec "${loop}p3" "$work/mount-roms"
while IFS= read -r -d '' relative; do
  mkdir -p -- "$work/roms/$relative"
done < <(find "$work/mount-roms" -mindepth 1 -maxdepth 1 -type d -printf '%P\0')
umount "$work/mount-roms"
mkdir -p -- "$work/roms/bios" "$work/roms/psp"
cp -a -- "$port/runtime/roms/." "$work/roms/"
printf '%s\n' 'Add your own games and BIOS files to the appropriate folders.' > "$work/roms/README.txt"

python3 "$port/scripts/prepare_image_rootfs.py" --rootfs "$work/mount-root" --donor-image "$work/base.img" \
  --overlay "$runtime" --modules "$kernel/modules/7.3.4-v40.1" --firmware "$work/firmware" --ppsspp "$ppsspp"

notices="$work/mount-root/usr/share/doc/arkos4clone-v40"
install -D -m 0644 "$port/image-inputs.json" "$notices/image-inputs.json"
install -m 0644 "$port/IMAGE.md" "$port/UPSTREAM.md" "$notices/"
install -m 0644 "$work/realtek/usr/share/doc/linux-firmware-realtek/copyright" "$notices/realtek-firmware.copyright"
install -m 0644 "$work/busybox/usr/share/doc/busybox-static/copyright" "$notices/busybox-static.copyright"
sync -f "$work/mount-root"
if ! fstrim "$work/mount-root"; then
  printf '%s\n' 'Discard is unavailable for the scratch ROOTFS. Continuing with the existing allocation.' >&2
fi

name=ArkOS4Clone-V40-Max-Linux-7.3.4-v40.1
image="$out/$name.img"
python3 "$port/scripts/build_image.py" --rootfs "$work/mount-root" --roms "$work/roms" \
  --busybox-static "$work/busybox/usr/bin/busybox" --image "$kernel/Image" \
  --dtb "$kernel/rk3326-v40-max.dtb" --uboot-dtb "$kernel/bootstrap.dtb" \
  --uboot-dir "$repo/uboot" --rom-mib 3072 --output "$image"
cleanup
loop=
created_nodes=()
trap - EXIT
rm -- "$work/base.img"

(cd "$out" && sha256sum "$name.img" > IMAGE-SHA256SUMS)
printf 'Built %s\n' "$image"
