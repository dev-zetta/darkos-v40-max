#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the pinned archive and prepare a new source tree; never install it."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tarfile

PORT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--archive',type=Path,required=True)
 parser.add_argument('--source',type=Path,required=True)
 parser.add_argument('--continuous-dma',action='store_true',help='Include the unresolved, default-off PL330 experiment')
 parser.add_argument('--dacmt-guard',action='store_true',help='Include the default-off RK817 DAC mute diagnostic from the tested build')
 args=parser.parse_args();lock=json.loads((PORT/'kernel/source-lock.json').read_text())
 if sha(args.archive)!=lock['archive_sha256']:raise ValueError('Kernel archive SHA-256 differs')
 if args.source.exists():raise ValueError('Use a new source path; existing trees are never overwritten')
 args.source.parent.mkdir(parents=True,exist_ok=True)
 # Python 3.12+ data filter rejects traversal, devices and escaping link targets.
 with tarfile.open(args.archive,'r:xz') as archive:
  for member in archive.getmembers():
   if Path(member.name).parts[0]!='linux-'+lock['version']:raise ValueError('Unexpected archive prefix')
  staging=args.source.parent/('extract-'+args.source.name)
  staging.mkdir(exist_ok=False)
  archive.extractall(staging,filter='data')
 (staging/('linux-'+lock['version'])).rename(args.source);staging.rmdir()
 for entry in lock['changes']:
  path=args.source/entry['path']
  if entry['before_sha256'] is None:
   if path.exists():raise ValueError('Unexpected pre-existing board file')
  elif sha(path)!=entry['before_sha256']:raise ValueError('Unexpected baseline: '+str(path))
 patches=lock['default_patches']+(lock['optional_patches'] if args.continuous_dma else [])
 for patch in patches:
  patch_path=PORT/'kernel/patches'/patch
  if sha(patch_path)!=lock['patch_sha256'][patch]:raise ValueError('Patch digest differs: '+patch)
  subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','--input',str(patch_path)],cwd=args.source,check=True)
 verified=[]
 for entry in lock['changes']:
  expected=entry['after_sha256']
  if entry['path']=='drivers/dma/pl330.c' and not args.continuous_dma:expected=entry['before_sha256']
  if sha(args.source/entry['path'])!=expected:raise ValueError('Patched source differs: '+entry['path'])
  verified.append(entry['path'])
 if args.dacmt_guard:
  path=Path('sound/soc/codecs/rk817_codec.c')
  optional=PORT/'diagnostics/optional'
  metadata=json.loads((optional/'dacmt-ownership-build.json').read_text())
  patch=optional/'0001-rk817-v40-dacmt-ownership.patch'
  if sha(patch)!=metadata['patch_sha256'] or sha(args.source/path)!=metadata['base_codec_sha256']:
   raise ValueError('DAC mute guard patch or preimage differs')
  subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','--input',str(patch)],cwd=args.source,check=True)
  if sha(args.source/path)!=metadata['candidate_codec_sha256']:raise ValueError('DAC mute guard result differs')
  patches.append(patch.name)
 print(json.dumps({'version':lock['version'],'patches':patches,'verified_source_files':verified,'installed':False},indent=2))
if __name__=='__main__':main()
