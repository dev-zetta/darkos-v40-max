#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render the tested runtime source into a NEW overlay directory; no card writes."""
from pathlib import Path
import argparse,hashlib,json,shutil

PORT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--frontend',type=Path,required=True)
 parser.add_argument('--resources',type=Path,required=True)
 parser.add_argument('--hotkey',type=Path,required=True)
 parser.add_argument('--graphics-root',type=Path,required=True,help='Prepared private Mesa/SDL/GLVND closure under usr/local/lib/v40-mainline')
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 for source in (args.frontend,args.hotkey):
  header=source.read_bytes()[:20]
  if header[:6]!=b'\x7fELF\x02\x01' or header[18:20]!=b'\xb7\x00':raise ValueError('Expected little-endian AArch64 ELF: '+str(source))
 for name in ('window_icon_256.png','opensans_hebrew_condensed_regular.ttf','opensans_hebrew_condensed_light.ttf','OpenSans-CondBold.ttf','fallback.ttf','glyphs.ttf'):
  if not (args.resources/name).is_file():raise ValueError('Missing frontend resource: '+name)
 if args.output.exists():raise ValueError('Output already exists')
 if not (args.graphics_root/'usr/local/lib/v40-mainline/lib/aarch64-linux-gnu').is_dir():raise ValueError('Missing ARM64 private graphics closure')
 if not (args.graphics_root/'usr/local/lib/v40-mainline/lib/arm-linux-gnueabihf').is_dir():raise ValueError('Missing ARM32 private graphics closure')
 digest=hashlib.sha256(args.frontend.read_bytes()).hexdigest()
 shutil.copytree(PORT/'runtime/root',args.output,symlinks=True)
 # The graphics closure is a separate build product, never proprietary global Mali.
 private=Path('usr/local/lib/v40-mainline')
 for path in args.output.rglob('*'):
  if path.is_file() and not path.is_symlink():
   data=path.read_bytes()
   if b'@FRONTEND_SHA256@' in data:path.write_bytes(data.replace(b'@FRONTEND_SHA256@',digest.encode()))
 native=args.output/private;native.mkdir(parents=True,exist_ok=True)
 shutil.copytree(args.graphics_root/private/'lib',native/'lib',symlinks=True)
 shutil.copyfile(args.frontend,native/'emulationstation');(native/'emulationstation').chmod(0o755)
 shutil.copyfile(args.hotkey,native/'ogage');(native/'ogage').chmod(0o755)
 shutil.copytree(args.resources,native/'resources',symlinks=True)
 print(json.dumps({'frontend_sha256':digest,'output':str(args.output),'installed':False,'settings_copied':False},indent=2))
if __name__=='__main__':main()
