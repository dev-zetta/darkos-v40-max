#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare fresh V40 defaults on a disposable derivative of the public Debian base."""
import argparse
from codecs import BOM_UTF8
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from configure_ppsspp import MAPPING

PORT = Path(__file__).resolve().parents[1]
RELEASE = "7.3.4-v40.1"
PROPRIETARY_APPS = (
    "applewin", "bigpemu", "drastic", "drastic-kk", "DSperate",
    "hypseus-singe", "piemu", "ppsspp-2021",
)


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def require_image_mount(root, image):
    if not image.is_file() or not os.stat(image).st_size or root == Path("/"):
        raise ValueError("Expected a disposable regular image file and its filesystem mount")
    source, options = output("findmnt", "-rn", "-M", str(root), "-o", "SOURCE,OPTIONS").split()
    source = source.split("[", 1)[0]
    device = re.fullmatch(r"/dev/(loop\d+)p2", source)
    if not device or "rw" not in options.split(","):
        raise ValueError("Expected a writable partition belonging to a loop-mounted image")
    backing = Path(f"/sys/block/{device[1]}/loop/backing_file").read_text().strip()
    if Path(backing).resolve() != image or image.stat().st_nlink != 1:
        raise ValueError("The mounted partition does not belong to the disposable image")
    if output("blkid", "-p", "-s", "LABEL", "-o", "value", source) != "ROOTFS":
        raise ValueError("Expected the public ROOTFS partition")
    if "VERSION_CODENAME=trixie" not in (root / "etc/os-release").read_text().splitlines():
        raise ValueError("Expected the Debian 13 dArkOS4Clone base")


def target(root, relative):
    path = root / relative
    if not path.parent.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes image: {relative}")
    return path


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    path.write_text(content)
    path.chmod(mode)


def copy_tree(source, dest):
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rsync", "-aH", "--safe-links", "--chown=0:0", f"{source}/", f"{dest}/"],
        check=True,
    )


def enable(units, name):
    want = units / "multi-user.target.wants" / name
    remove(want)
    want.symlink_to(f"/etc/systemd/system/{name}")


def update_shared_controller_database(root):
    database = target(root, "opt/inttools/gamecontrollerdb.txt")
    if database.is_symlink() or not database.is_file():
        raise ValueError("Expected the donor's shared SDL controller database")
    original = database.read_bytes()
    bom = BOM_UTF8 if original.startswith(BOM_UTF8) else b""
    mapping = MAPPING.encode("ascii")
    guid = mapping.partition(b",")[0]
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    # Apply the parent project's CRC-GUID fix with the V40's tested Guide binding.
    other_rows = [line for line in original[len(bom):].splitlines(keepends=True)
                  if line.partition(b",")[0].lower() != guid]
    database.write_bytes(bom + mapping + newline + b"".join(other_rows))


def seed_frontend_controller(root):
    path = target(root, "etc/emulationstation/es_input.cfg")
    if path.exists() or path.is_symlink():
        return
    write(path, (PORT / "components/frontend/es_input.cfg").read_text())
    os.chown(path, 1000, 1000)


def set_default_settings(root):
    settings = target(root, "home/ark/.emulationstation/es_settings.cfg")
    data = settings.read_text()
    declaration = re.match(r"^<\?xml[^?]*\?>\s*", data)
    header = declaration[0] if declaration else ""
    xml = ET.fromstring("<settings>" + data[len(header):] + "</settings>")
    for kind, name, value in (
        ("string", "AudioDevice", "Playback"),
        ("bool", "audio.bgmusic", "false"),
        ("string", "ThemeSet", "v40-default"),
    ):
        for child in list(xml):
            if child.get("name") == name:
                xml.remove(child)
        ET.SubElement(xml, kind, name=name, value=value)
    write(settings, header + "\n".join(ET.tostring(child, encoding="unicode").strip() for child in xml) + "\n")
    os.chown(settings, 1000, 1000)
    home_config = target(root, "home/ark/.config/batteryplus")
    home_config.mkdir(exist_ok=True)
    os.chown(home_config, 1000, 1000)
    system_config = target(root, "etc/batteryplus.conf")
    config = system_config.read_text().replace("mode=voltage", "mode=pmic")
    if "mode=pmic" not in config:
        raise ValueError("BatteryPlus base configuration differs")
    write(system_config, config)
    write(home_config / "batteryplus.conf", config)
    os.chown(home_config / "batteryplus.conf", 1000, 1000)


def prepare_ppsspp(root, ppsspp):
    standalone = target(root, "opt/ppsspp")
    templates = standalone / "backupforromsfolder/ppsspp/PSP/SYSTEM"
    if not templates.is_dir() or not (ppsspp / "PPSSPPSDL").is_file():
        raise ValueError("Expected standard PPSSPP build and the public launcher templates")
    for name in ("assets", "PPSSPPSDL", "LICENSE.TXT"):
        remove(standalone / name)
    copy_tree(ppsspp, standalone)
    database = standalone / "assets/gamecontrollerdb.txt"
    for name in ("ppsspp.ini", "ppsspp.ini.sdl"):
        path = templates / name
        lines = path.read_text().splitlines()
        start = lines.index("[Graphics]") + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
        for key, value in (("SkipBufferEffects", "False"), ("InternalResolution", "1")):
            matches = [i for i in range(start, end) if lines[i].partition("=")[0].strip() == key]
            if matches:
                lines[matches[0]] = f"{key} = {value}"
            else:
                lines.insert(end, f"{key} = {value}")
                end += 1
        write(path, "\n".join(lines) + "\n")
    subprocess.run([
        "python3", str(PORT / "scripts/configure_ppsspp.py"), "--database", str(database),
        "--system-dir", str(templates), "--apply", "--backup-dir",
        str(target(root, "var/tmp/v40-ppsspp-defaults")),
    ], check=True)
    remove(target(root, "var/tmp/v40-ppsspp-defaults"))
    launcher = target(root, "usr/local/bin/ppsspp.sh")
    original = target(root, "usr/local/libexec/v40-ppsspp-launcher")
    if launcher.is_symlink() or not launcher.is_file() or original.exists() or original.is_symlink():
        raise ValueError("Expected the untouched donor PPSSPP launcher")
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(launcher, original)
    original.chmod(0o755)
    write(launcher, (PORT / "components/ppsspp/v40-ppsspp-instance").read_text(), 0o755)
    systems = target(root, "etc/emulationstation/es_systems.cfg")
    config = ET.parse(systems, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    for emulators in config.findall("./system[name='psp']/emulators"):
        for entry in emulators.findall("emulator[@name='standalone-2021']"):
            emulators.remove(entry)
    # EmulationStation exits when every ROM system is empty.
    system = ET.SubElement(config.getroot(), "system")
    for key, value in (
        ("name", "v40-tools"), ("fullname", "V40 Max Tools"), ("path", "/roms/v40-tools"),
        ("extension", ".sh"), ("command", "/bin/sh %ROM%"), ("theme", "v40-tools"),
    ):
        ET.SubElement(system, key).text = value
    config.write(systems, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--donor-image", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--modules", type=Path, required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--ppsspp", type=Path, required=True)
    args = parser.parse_args()
    root = args.rootfs.resolve(strict=True)
    require_image_mount(root, args.donor_image.resolve(strict=True))

    modules = args.modules.resolve(strict=True)
    if (modules.name != RELEASE or not list(modules.rglob("rtw89_8851bu.ko*"))
            or not (modules / "updates/v40-input/uinput.ko").is_file()):
        raise ValueError("Missing matching V40 kernel modules or the uinput add-on")
    if not (args.overlay / "usr/local/lib/v40-mainline/emulationstation").is_file():
        raise ValueError("Missing built V40 frontend overlay")
    if not (args.firmware / "rtw89/rtw8851b_fw-1.bin").is_file():
        raise ValueError("Missing uncompressed AX900 firmware")

    copy_tree(args.overlay, root)
    subprocess.run([
        "python3", str(PORT / "components/emulators/configure-image.py"), str(root),
    ], check=True)
    old_modules = target(root, "usr/lib/modules")
    remove(old_modules)
    copy_tree(modules, old_modules / RELEASE)
    for link in ("build", "source"):
        remove(old_modules / RELEASE / link)
    copy_tree(args.firmware, target(root, "usr/lib/firmware"))
    prepare_ppsspp(root, args.ppsspp)
    write(target(root, "etc/modules-load.d/v40-uinput.conf"), "uinput\n")
    write(target(root, "etc/udev/rules.d/70-v40-uinput.rules"),
          'SUBSYSTEM=="misc", KERNEL=="uinput", GROUP="input", MODE="0660"\n')
    update_shared_controller_database(root)

    units = target(root, "etc/systemd/system")
    for name, wanted_by in (
        ("firstboot.service", "multi-user.target"),
        ("wifi_importer.service", "multi-user.target"),
        ("welcome-message.service", "sysinit.target"),
    ):
        remove(units / f"{wanted_by}.wants" / name)
        remove(units / name)
        (units / name).symlink_to("/dev/null")
    for name in ("emulationstation.service", "ogage.service", "v40max-alsa-state.service"):
        if not (units / name).is_file():
            raise ValueError(f"Missing service: {name}")
        enable(units, name)
    remove(units / "multi-user.target.wants/ssh.service")
    remove(units / "sockets.target.wants/ssh.socket")
    for name in ("smbd.service", "nmbd.service"):
        remove(units / "multi-user.target.wants" / name)
    home = target(root, "home/ark")
    if home.is_symlink() or not home.is_dir():
        raise ValueError("Expected the donor's ark home directory")
    home.chmod(0o755)
    write(target(root, "etc/ssh/sshd_config.d/10-v40-image.conf"),
          "PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n")
    # Remote Services may first be enabled several boots after flashing the image.
    write(units / "sshd-keygen.service.d/10-v40-image.conf", """[Unit]
ConditionFirstBoot=
ConditionPathIsReadWrite=/etc/ssh
ConditionPathIsSymbolicLink=!/etc/ssh
ConditionPathExists=|!/etc/ssh/ssh_host_rsa_key
ConditionPathExists=|!/etc/ssh/ssh_host_ecdsa_key
ConditionPathExists=|!/etc/ssh/ssh_host_ed25519_key
""")
    write(target(root, "usr/local/bin/ArkOS4CloneUpdate.sh"),
          "#!/bin/sh\nprintf '%s\\n' 'Use a V40 mainline release to update this image.'\nsleep 2\n", 0o755)
    for name in ("Install to eMMC.sh", "Switch to SD2 for Roms.sh"):
        remove(target(root, f"opt/system/Advanced/{name}"))
    theme_link = target(root, "home/ark/.emulationstation/themes")
    remove(theme_link)
    theme_link.symlink_to("/roms/themes")

    for directory, pattern in (
        ("etc/ssh", "ssh_host_*"), ("etc/NetworkManager/system-connections", "*"),
        ("var/lib/bluetooth", "*"), ("var/lib/systemd/pstore", "*"),
        ("var/log/journal", "*"), ("var/cache/apt/archives", "*.deb"),
        ("var/cache/apt", "*.bin"),
    ):
        for path in target(root, directory).glob(pattern):
            remove(path)
    target(root, "var/log/journal").mkdir(mode=0o2755, exist_ok=True)
    for relative in (
        "roms.tar", "swapfile", "var/lib/systemd/random-seed", "root/.ssh",
        "home/ark/.ssh", "home/ark/.bash_history", "root/.bash_history",
        "home/ark/.config/lastgame.sh", "var/local/asound.state", "var/lib/alsa/asound.state",
    ):
        remove(target(root, relative))
    write(target(root, "etc/machine-id"), "")
    dbus_id = target(root, "var/lib/dbus/machine-id")
    remove(dbus_id)
    dbus_id.symlink_to("/etc/machine-id")

    for name in PROPRIETARY_APPS:
        remove(target(root, f"opt/{name}"))
    for triplet in ("aarch64-linux-gnu", "arm-linux-gnueabihf"):
        for glob in ("libmali-bifrost*", "libMali*", "libmali.so*"):
            for path in target(root, f"usr/lib/{triplet}").glob(glob):
                remove(path)
    seed_frontend_controller(root)
    set_default_settings(root)
    print("Prepared the V40 rootfs and fresh image defaults.")


if __name__ == "__main__":
    main()
