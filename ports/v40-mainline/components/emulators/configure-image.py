#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply scoped emulator launch and controller settings to a prepared image."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
from tempfile import NamedTemporaryFile


COMPONENT = Path(__file__).resolve().parent
PRIVATE = Path('opt/retroarch/v40-mainline')
PROFILE = Path('autoconfig/udev/GO-Super Gamepad.cfg')
DONOR_FRONTENDS = {
    'retroarch': '81f3cf1b8850f9457730346d3f973dfb03d5316d62c4bb92b1654372bbc86e77',
    'retroarch32': '9103b282b0add6fb0ea782b3cbd86e154ec3810f9cd467c7710b62660ef1110a',
}
PCSX = 'pcsx_rearmed_neon_libretro.so'
DONOR_PCSX = 'bd8a5c804229f0fd3d4a38391185233a5c715aa9a7e3e9a401d61f09fc73088c'
DONOR_FLYCAST = 'cd6fca1d1b3c112ead8945015ed346dcc673e1f98206dbc7741b77997dc7a249'
DONOR_PROFILE = '83f21f2da1ca5434001d36d75bb3de7826809e2d0ff81d04c6eaf3d0314291fe'
DONOR_ARCADE_LAUNCHERS = {
    'dreamcast': 'e5903b36bae739f437724ad67e7d30e4fb8a0cf9b45f4d7c9c50cb831dcf27c6',
    'naomi': 'e5e7633fb256195970340701f453eb75132eef932188d391be0fb2b267128cc7',
    'atomiswave': 'ffbeb0f3546b7c0f92e03868579d3b5f422f6fb01e5cbee93025641ce27ae2bf',
}
FLYCAST_STOCK = b'FLYCAST_BIN="/opt/flycastsa/flycast-r7"'
FLYCAST_REPAIRED = b'FLYCAST_BIN="/usr/local/libexec/v40-r7"'
PROFILE_FIELDS = (
    (b'input_a_btn', b'15', b'1'),
    (b'input_l_x_plus_axis', b'-0', b'+0'),
    (b'input_l_x_minus_axis', b'+1', b'-0'),
    (b'input_l_y_plus_axis', b'-1', b'+1'),
    (b'input_l_y_minus_axis', b'+1', b'-1'),
)


def path_at(root, relative):
    path = root / relative
    if path.parent.resolve() != path.parent or path.is_symlink():
        raise ValueError(f'Unexpected symbolic link: {path}')
    return path


def donor(path, digest):
    if not path.is_file():
        raise ValueError(f'Expected a regular donor file: {path}')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'Unexpected donor checksum: {path}')
    return data


def change_profile(data):
    for key, old, new in PROFILE_FIELDS:
        prefix = rb'(?m)^(' + key + rb'[ \t]*=[ \t]*")'
        choices = b'(' + re.escape(old) + b'|' + re.escape(new) + b')'
        suffix = rb'("[ \t]*\r?)$'
        data, hits = re.subn(prefix + choices + suffix,
                             lambda match: match[1] + new + match[3], data)
        if hits != 1:
            raise ValueError(f'Unexpected GO-Super field: {key.decode()}')
    return data


def replace_file(path, data, *, owner=None, mode=None):
    if path.exists():
        original = path.stat()
        if not stat.S_ISREG(original.st_mode):
            raise ValueError(f'Expected a regular image file: {path}')
        if owner is None:
            owner = original.st_uid, original.st_gid
        if mode is None:
            mode = stat.S_IMODE(original.st_mode)
    with NamedTemporaryFile(dir=path.parent, prefix='.v40-emulator-', delete=False) as pending:
        temporary = Path(pending.name)
        try:
            pending.write(data)
            pending.flush()
            if owner is not None:
                os.fchown(pending.fileno(), *owner)
            if mode is not None:
                os.fchmod(pending.fileno(), mode)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def configure(root):
    if root == Path('/') or 'VERSION_CODENAME=trixie' not in (root / 'etc/os-release').read_text().splitlines():
        raise ValueError('Expected a prepared Debian 13 image root')

    changes = []
    for name, digest in DONOR_FRONTENDS.items():
        launcher = path_at(root, Path('opt/retroarch/bin') / name)
        donor(launcher, digest)
        if not path_at(root, PRIVATE / 'bin' / name).is_file():
            raise ValueError(f'Missing built V40 frontend: {name}')
        wrapper = (COMPONENT / f'{name}-launch').read_bytes()
        subprocess.run(['sh', '-n'], input=wrapper, check=True)
        changes.append((launcher, wrapper, {'owner': (0, 0), 'mode': 0o755}))

        profile = path_at(root, Path('home/ark/.config') / name / PROFILE)
        changes.append((profile, change_profile(donor(profile, DONOR_PROFILE)), {}))

    installed_core = path_at(root, Path('home/ark/.config/retroarch32/cores') / PCSX)
    donor(installed_core, DONOR_PCSX)
    changes.append((installed_core, path_at(root, PRIVATE / 'cores' / PCSX).read_bytes(), {}))

    donor(path_at(root, 'opt/flycastsa/flycast-r7'), DONOR_FLYCAST)
    wrapper = (COMPONENT / 'flycast-r7-launch').read_bytes()
    subprocess.run(['sh', '-n'], input=wrapper, check=True)
    changes.append((path_at(root, 'usr/local/libexec/v40-r7'), wrapper,
                    {'owner': (0, 0), 'mode': 0o755}))
    for name, digest in DONOR_ARCADE_LAUNCHERS.items():
        launcher = path_at(root, f'usr/local/bin/{name}.sh')
        data = donor(launcher, digest)
        if data.count(FLYCAST_STOCK) != 1 or FLYCAST_REPAIRED in data:
            raise ValueError(f'Expected a single Flycast r7 assignment: {launcher}')
        revised = data.replace(FLYCAST_STOCK, FLYCAST_REPAIRED)
        subprocess.run(['bash', '-n'], input=revised, check=True)
        changes.append((launcher, revised, {}))

    # Validate all known donor paths before changing the disposable image.
    for path, data, attrs in changes:
        replace_file(path, data, **attrs)
    print('Configured V40 RetroArch, PCSX ReARMed and the inherited Flycast r7 launch paths.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    configure(parser.parse_args().rootfs.resolve(strict=True))


if __name__ == '__main__':
    main()
