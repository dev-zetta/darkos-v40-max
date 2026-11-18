#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stream the pinned, stored XZ member from its three 7z volumes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib

LOCK = Path(__file__).resolve().parents[1] / "image-inputs.json"
HEADER_SIZE = 32
XZ_MAGIC = b"\xfd7zXZ\0"


def copy_member(lock, workspace, local):
    combined = hashlib.sha256()
    remaining = lock["base_xz_size_bytes"]
    for index, (name, expected) in enumerate(lock["base_parts"].items()):
        with tempfile.TemporaryDirectory(dir=workspace, prefix="volume-") as temporary:
            part = (local / name) if local else (Path(temporary) / name)
            if not local:
                subprocess.run([
                    "curl", "--fail", "--location", "--retry", "3",
                    "--output", str(part), f"{lock['base_release']}/{name}",
                ], check=True)
            with part.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError(f"Base volume checksum mismatch: {name}")
                stream.seek(0)
                offset = 0
                if index == 0:
                    header = stream.read(HEADER_SIZE)
                    if len(header) != HEADER_SIZE or header[:6] != b"7z\xbc\xaf'\x1c":
                        raise ValueError("Invalid 7z start header")
                    checksum, packed_size = struct.unpack_from("<IQ", header, 8)
                    if checksum != zlib.crc32(header[12:]) or packed_size != remaining:
                        raise ValueError("Unexpected stored 7z member range")
                    if stream.read(len(XZ_MAGIC)) != XZ_MAGIC:
                        raise ValueError("Expected the XZ member at the start of the 7z data")
                    offset = HEADER_SIZE
                    stream.seek(offset)
                available = min(remaining, part.stat().st_size - offset)
                remaining -= available
                while available:
                    data = stream.read(min(2**20, available))
                    if not data:
                        raise EOFError(f"Short volume: {name}")
                    combined.update(data)
                    sys.stdout.buffer.write(data)
                    available -= len(data)
            print(f"Verified base volume {name}", file=sys.stderr)
    if remaining or combined.hexdigest() != lock["base_archive_sha256"]:
        raise ValueError("Extracted XZ member differs from the locked input")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--local-parts", type=Path)
    args = parser.parse_args()
    copy_member(json.loads(LOCK.read_text()), args.workspace, args.local_parts)


if __name__ == "__main__":
    main()
