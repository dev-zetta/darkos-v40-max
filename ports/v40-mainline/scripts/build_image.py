#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assemble a fresh V40 Max disk image from staged public build inputs."""

import argparse
from contextlib import ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid


PORT = Path(__file__).resolve().parents[1]
SECTOR = 512
MIB = 1024 * 1024
BOOT_START = 16 * MIB
BOOT_BYTES = 256 * MIB
KERNEL_RELEASE = "7.3.4-v40.1"
BOOTLOADER = (
    ("idbloader.img", 64, "44300348ec207e4a3824a4a225b814b0ce549c4f5441f0931e28de611b089757"),
    ("uboot.img", 16384, "9006013726db2458befaf022982a542307a636223767ed329e81eac866169e8a"),
    ("trust.img", 24576, "7e5e7174134436f44eaa84dc2682b0fe7461a3a5f5ecc6b3b1b607ec799a64ea"),
)


def run(*args, capture=False, text_input=None):
    stdout = subprocess.PIPE if capture else sys.stderr
    result = subprocess.run(args, input=text_input, check=True, text=True, stdout=stdout)
    return result.stdout.strip() if capture else None


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def regular_file(path):
    if not path.exists() or not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    return path.resolve(strict=True)


def check_dtb(path):
    data = path.read_bytes()
    if len(data) < 40 or struct.unpack_from(">II", data) != (0xD00DFEED, len(data)):
        raise ValueError(f"Invalid flattened device tree: {path}")


def check_inputs(args):
    for arg in ("busybox_static", "image", "dtb", "uboot_dtb"):
        setattr(args, arg, regular_file(getattr(args, arg)))
    if not args.rootfs.is_dir():
        raise ValueError(f"Missing ROOTFS tree: {args.rootfs}")
    args.rootfs = args.rootfs.resolve()
    if args.rootfs == Path("/") or args.output.resolve().is_relative_to(args.rootfs):
        raise ValueError("Use a separate staged ROOTFS and a new output outside it")
    if not (args.rootfs / "sbin/init").is_file():
        raise ValueError("ROOTFS has no usable sbin/init")
    if not (args.rootfs / f"usr/lib/modules/{KERNEL_RELEASE}/modules.dep").is_file():
        raise ValueError(f"ROOTFS is missing indexed modules for {KERNEL_RELEASE}")
    if args.roms is not None:
        args.roms = args.roms.resolve(strict=True)
        if not args.roms.is_dir() or args.output.resolve().is_relative_to(args.roms):
            raise ValueError("Use a separate ROMS seed directory")
        for path in args.roms.rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise ValueError(f"EXFAT cannot preserve this ROMS entry: {path}")

    kernel = args.image.read_bytes()
    if kernel[0x38:0x3C] != b"ARM\x64" or f"Linux version {KERNEL_RELEASE} ".encode() not in kernel:
        raise ValueError(f"Expected ARM64 Image for {KERNEL_RELEASE}")
    for dtb in (args.dtb, args.uboot_dtb):
        check_dtb(dtb)
    compatible = run("fdtget", "-t", "s", args.dtb, "/", "compatible", capture=True)
    if "v40-port,rk3326-handheld" not in compatible.split():
        raise ValueError("The Linux DTB does not identify the V40 Max mainline port")

    busybox = args.busybox_static.read_bytes()
    if not (busybox[:6] == b"\x7fELF\x02\x01" and busybox[18:20] == b"\xb7\x00"):
        raise ValueError("The initramfs needs an ARM64 BusyBox binary")
    if re.search(r"^\s*INTERP\s", run("readelf", "-l", args.busybox_static, capture=True), re.M):
        raise ValueError("The initramfs BusyBox must be statically linked")


def layout(root_mib, rom_mib):
    if not 256 <= root_mib <= 256 * 1024 or not 32 <= rom_mib <= 256 * 1024:
        raise ValueError("ROOTFS must be 256 MiB–256 GiB and EASYROMS 32 MiB–256 GiB")
    root_bytes = root_mib * MIB
    rom_bytes = rom_mib * MIB
    return (
        (BOOT_START, BOOT_BYTES, "c"),
        (BOOT_START + BOOT_BYTES, root_bytes, "83"),
        (BOOT_START + BOOT_BYTES + root_bytes, rom_bytes, "7"),
    )


def write_disk(path, partitions, uboot_dir, disk_id):
    size = sum(length for _, length, _ in partitions) + BOOT_START
    with path.open("xb") as stream:
        stream.truncate(size)
        end = SECTOR
        for name, sector, digest in BOOTLOADER:
            bootloader = regular_file(uboot_dir / name)
            data = bootloader.read_bytes()
            start = sector * SECTOR
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Unrecognized public bootloader input: {name}")
            if not end <= start < start + len(data) <= BOOT_START:
                raise ValueError(f"Bootloader overlaps MBR, another blob or BOOT: {name}")
            stream.seek(start)
            stream.write(data)
            end = start + len(data)
        stream.flush()
        os.fsync(stream.fileno())
    table = f"label: dos\nlabel-id: 0x{disk_id}\nunit: sectors\n\n"
    for number, (start, length, kind) in enumerate(partitions, 1):
        flags = ", bootable" if number == 1 else ""
        table += f"start={start // SECTOR}, size={length // SECTOR}, type={kind}{flags}\n"
    run("sfdisk", "--wipe", "never", "--", path, text_input=table)
    actual = json.loads(run("sfdisk", "--json", "--", path, capture=True))["partitiontable"]
    geometry = [(part["start"] * SECTOR, part["size"] * SECTOR, part["type"])
                for part in actual["partitions"]]
    if actual["label"] != "dos" or tuple(geometry) != partitions:
        raise RuntimeError("Partition table readback differs")
    with path.open("rb") as stream:
        for name, sector, digest in BOOTLOADER:
            stream.seek(sector * SECTOR)
            size = (uboot_dir / name).stat().st_size
            if hashlib.sha256(stream.read(size)).hexdigest() != digest:
                raise RuntimeError(f"Bootloader readback differs: {name}")


def attach_image(image, cleanup):
    loop = run("losetup", "--find", "--show", "--partscan", "--nooverlap", "--", image, capture=True)
    if not re.fullmatch(r"/dev/loop[0-9]+", loop):
        raise RuntimeError(f"Unexpected loop device name: {loop!r}")
    sysfs = Path("/sys/class/block") / Path(loop).name
    cleanup.callback(run, "losetup", "--detach", loop)
    backing = Path((sysfs / "loop/backing_file").read_text().strip())
    if not backing.samefile(image):
        raise RuntimeError("Loop does not refer to the new image")
    # Every later destructive filesystem command targets only a verified
    # partition child of this new regular-file-backed loop.
    parts = [Path(f"{loop}p{i}") for i in range(1, 4)]
    part_nodes = [Path("/sys/class/block") / part.name for part in parts]
    for _ in range(100):
        if all(node.exists() for node in part_nodes):
            break
        time.sleep(0.1)
    devices = []
    for part, part_sysfs in zip(parts, part_nodes, strict=True):
        if part_sysfs.resolve(strict=True).parent != sysfs.resolve(strict=True):
            raise RuntimeError(f"Partition is not a child of the image loop: {part}")
        major, minor = [int(item) for item in (part_sysfs / "dev").read_text().strip().split(":")]
        number = os.makedev(major, minor)
        if not part.exists():
            # Containers can see kernel-created partitions in sysfs without
            # sharing the host udev namespace. Create only our own nodes.
            part = image.parent / part.name
            os.mknod(part, stat.S_IFBLK | 0o600, number)
        attributes = part.stat()
        if not stat.S_ISBLK(attributes.st_mode) or attributes.st_rdev != number:
            raise RuntimeError(f"Incorrect block device number: {part}")
        devices.append(part)
    return devices


def mount_part(device, directory, filesystem, options, cleanup):
    directory.mkdir()
    run("mount", "-t", filesystem, "-o", f"nosuid,nodev,noexec,{options}", device, directory)
    cleanup.callback(run, "umount", "--", directory)


def find_uuid(device):
    return run("blkid", "-p", "-s", "UUID", "-o", "value", device, capture=True)


def prepare_fstab(root, root_uuid, boot_uuid, roms_uuid):
    for name in ("boot", "roms", "dev", "proc", "sys"):
        directory = root / name
        if directory.is_symlink():
            raise ValueError(f"ROOTFS mount directory cannot be a symlink: {name}")
        directory.mkdir(exist_ok=True)
    if (root / "etc").is_symlink() or (root / "etc/fstab").is_symlink():
        raise ValueError("ROOTFS etc/fstab must be an ordinary file")
    (root / "etc/fstab").write_text(
        f"UUID={root_uuid} / btrfs rw,noatime,compress=zlib,ssd_spread,noacl,nospace_cache,subvolid=5 0 0\n"
        f"UUID={boot_uuid} /boot vfat defaults,uid=1000,gid=1000,umask=0022,flush 0 2\n"
        f"UUID={roms_uuid} /roms exfat defaults,noatime,uid=1000,gid=1000,umask=000 0 0\n"
    )


def initramfs(path, busybox, root_uuid):
    init = f"""#!/bin/busybox sh
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
exec </dev/console >/dev/console 2>&1
fail() {{
    echo "V40 initramfs: $*"
    while :; do sleep 60; done
}}
root=
for argument in $(cat /proc/cmdline); do
    case "$argument" in
        root=UUID=*) root=${{argument#root=UUID=}} ;;
    esac
done
[ "$root" = "{root_uuid}" ] || fail "unexpected root UUID"
attempt=0
while [ "$attempt" -lt 30 ]; do
    device=$(findfs "UUID=$root" 2>/dev/null)
    [ -b "$device" ] && break
    attempt=$((attempt + 1))
    sleep 1
done
[ -b "$device" ] || fail "root partition did not appear"
mount -t btrfs -o rw,noatime,compress=zlib,ssd_spread,noacl,nospace_cache,subvolid=5 "$device" /newroot || fail "cannot mount ROOTFS"
[ -x /newroot/sbin/init ] || fail "missing /sbin/init"
mount --move /dev /newroot/dev || fail "cannot move devtmpfs"
mount --move /proc /newroot/proc || fail "cannot move procfs"
mount --move /sys /newroot/sys || fail "cannot move sysfs"
echo 'V40 initramfs: handing off to systemd'
exec switch_root /newroot /sbin/init
"""
    # newc is the kernel's initramfs format. Encode explicit root ownership
    # and constant timestamps, independent of the host or staging directory.
    entries = [
        ("bin", stat.S_IFDIR | 0o755, b""),
        ("dev", stat.S_IFDIR | 0o755, b""),
        ("proc", stat.S_IFDIR | 0o755, b""),
        ("sys", stat.S_IFDIR | 0o755, b""),
        ("newroot", stat.S_IFDIR | 0o755, b""),
        ("bin/busybox", stat.S_IFREG | 0o755, busybox.read_bytes()),
        ("init", stat.S_IFREG | 0o755, init.encode()),
    ]
    for applet in ("sh", "cat", "mount", "findfs", "sleep", "switch_root"):
        entries.append((f"bin/{applet}", stat.S_IFLNK | 0o777, b"busybox"))
    entries.append(("TRAILER!!!", 0, b""))
    archive = bytearray()
    for inode, (filename, mode, content) in enumerate(entries, 1):
        name = filename.encode() + b"\0"
        fields = (inode, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name), 0)
        archive += b"070701" + b"".join(f"{field:08x}".encode() for field in fields) + name
        archive += b"\0" * (-len(archive) % 4) + content
        archive += b"\0" * (-len(archive) % 4)
    archive += b"\0" * (-len(archive) % 512)
    path.write_bytes(gzip.compress(archive, mtime=0))


def populate_boot(boot, args, root_uuid):
    mainline = boot / "mainline"
    mainline.mkdir()
    shutil.copyfile(args.image, mainline / "Image")
    shutil.copyfile(args.dtb, mainline / "rk3326-v40-max.dtb")
    shutil.copyfile(args.uboot_dtb, boot / "rk3326-r36splus-linux.dtb")
    shutil.copyfile(args.uboot_dtb, boot / "arkos4clone-uboot.dtb")
    initramfs(mainline / "initramfs.cpio.gz", args.busybox_static, root_uuid)
    if (mainline / "initramfs.cpio.gz").stat().st_size >= 0x01F00000 - 0x01100000:
        raise ValueError("The initramfs overlaps the DTB load address")
    if args.dtb.stat().st_size >= 0x02000000 - 0x01F00000:
        raise ValueError("The Linux DTB overlaps the kernel load address")
    script = f"""odroidgoa-uboot-config

setenv loadaddr "0x02000000"
setenv initrd_loadaddr "0x01100000"
setenv dtb_loadaddr "0x01f00000"
load mmc 1:1 ${{dtb_loadaddr}} rk3326-r36splus-linux.dtb
setenv bootargs "root=UUID={root_uuid} rootwait rw net.ifnames=0 fbcon=rotate:0 console=ttyS2,115200n8 console=tty0 consoleblank=0 panic=10 v40.mainline=1 pl330.v40_continuous=0 snd_soc_rk817.v40_dacmt_guard=1"
if load mmc 1:1 ${{loadaddr}} mainline/Image; then
    if load mmc 1:1 ${{initrd_loadaddr}} mainline/initramfs.cpio.gz; then
        setenv v40_initrd_size ${{filesize}}
        if load mmc 1:1 ${{dtb_loadaddr}} mainline/rk3326-v40-max.dtb; then
            booti ${{loadaddr}} ${{initrd_loadaddr}}:${{v40_initrd_size}} ${{dtb_loadaddr}}
        fi
    fi
fi
echo "V40 mainline could not be started. Inspect the BOOT files."
"""
    (boot / "boot.ini").write_text(script)
    (boot / "boot.ini.default").write_text(script)
    (boot / ".console").write_text("r36splus\n")


def assemble(args):
    args.output = args.output.absolute()
    if not args.output.parent.is_dir() or args.output.exists() or args.output.is_symlink():
        raise ValueError("Output must be a new regular file path under an existing directory")
    check_inputs(args)
    partitions = layout(args.root_mib, args.rom_mib)
    disk_id = uuid.uuid4().hex[:8]
    boot_id = uuid.uuid4().hex[:8]
    root_uuid = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix=".v40-image-", dir=args.output.parent) as temporary:
        work = Path(temporary).resolve()
        image = work / "disk.img"
        write_disk(image, partitions, args.uboot_dir, disk_id)
        with ExitStack() as loop_cleanup:
            boot_dev, root_dev, roms_dev = attach_image(image, loop_cleanup)
            run("mkfs.fat", "-F", "32", "-i", boot_id, "-n", "BOOT", boot_dev)
            run("mkfs.btrfs", "-f", "-s", "4096", "-n", "16384", "-U", root_uuid, "-L", "ROOTFS",
                "-O", "extref,skinny-metadata,no-holes,^free-space-tree,^block-group-tree", root_dev)
            run("mkfs.exfat", "-c", "16384", "-L", "EASYROMS", roms_dev)
            if find_uuid(root_dev) != root_uuid:
                raise RuntimeError("ROOTFS UUID differs from the boot plan")
            boot_uuid, roms_uuid = find_uuid(boot_dev), find_uuid(roms_dev)
            boot, root, roms = (work / name for name in ("boot", "root", "roms"))
            with ExitStack() as mount_cleanup:
                mount_part(boot_dev, boot, "vfat", "rw,umask=0022", mount_cleanup)
                mount_part(root_dev, root, "btrfs", "rw,noatime,compress=zlib,nospace_cache", mount_cleanup)
                mount_part(roms_dev, roms, "exfat", "rw,umask=0022", mount_cleanup)
                run("rsync", "-aHAXS", "--numeric-ids", "--one-file-system", f"{args.rootfs}/", f"{root}/")
                prepare_fstab(root, root_uuid, boot_uuid, roms_uuid)
                if args.roms is not None:
                    run("rsync", "-rt", "--no-perms", "--no-owner", "--no-group", f"{args.roms}/", f"{roms}/")
                for directory in ("bios", "themes"):
                    (roms / directory).mkdir(exist_ok=True)
                populate_boot(boot, args, root_uuid)
                boot_hashes = {str(path.relative_to(boot)): file_digest(path) for path in boot.rglob("*") if path.is_file()}
                for directory in (boot, root, roms):
                    run("sync", "-f", "--", directory)
            run("fsck.fat", "-n", boot_dev)
            run("btrfs", "check", "--readonly", "--check-data-csum", root_dev)
            run("fsck.exfat", "-n", roms_dev)
            boot.rmdir()
            with ExitStack() as readback:
                mount_part(boot_dev, boot, "vfat", "ro", readback)
                for relative, expected in boot_hashes.items():
                    if file_digest(boot / relative) != expected:
                        raise RuntimeError(f"BOOT readback differs: {relative}")
        with image.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(image, args.output)
    print(json.dumps({
        "image": str(args.output), "kernel_release": KERNEL_RELEASE,
        "size": args.output.stat().st_size, "sha256": file_digest(args.output),
        "disk_id": disk_id, "root_uuid": root_uuid, "boot_sha256": boot_hashes,
        "bootloader_sha256": {name: digest for name, _, digest in BOOTLOADER},
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", required=True, type=Path, help="Clean, prepared ROOTFS directory")
    parser.add_argument("--roms", type=Path, help="Optional public assets-only EASYROMS seed")
    parser.add_argument("--busybox-static", required=True, type=Path, help="Static AArch64 BusyBox executable")
    parser.add_argument("--image", required=True, type=Path, help="Linux ARM64 Image")
    parser.add_argument("--dtb", required=True, type=Path, help="V40 Max Linux DTB")
    parser.add_argument("--uboot-dtb", required=True, type=Path, help="Legacy U-Boot device-tree profile")
    parser.add_argument("--uboot-dir", default=PORT.parents[1] / "uboot", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New image file to create")
    parser.add_argument("--root-mib", default=11264, type=int, help="ROOTFS size in MiB (default 11264)")
    parser.add_argument("--rom-mib", default=256, type=int, help="EASYROMS size in MiB (default 256)")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Assembly needs root privileges to mount the new image's loop partitions")
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    assemble(args)


if __name__ == "__main__":
    main()
