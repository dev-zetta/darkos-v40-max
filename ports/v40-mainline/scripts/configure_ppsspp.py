#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare V40 PSP settings; writes require --apply and a new backup directory."""
from pathlib import Path
import argparse,hashlib,json,os,re,stat,tempfile

MAPPING='1900bb3e4b4800000011000000010000,GO-Super Gamepad,a:b1,b:b0,x:b2,y:b3,back:b12,start:b13,guide:b16,leftshoulder:b4,rightshoulder:b5,lefttrigger:b6,righttrigger:b7,leftstick:b14,rightstick:b15,dpup:b8,dpdown:b9,dpleft:b10,dpright:b11,leftx:a0,lefty:a1,rightx:a2,righty:a3,platform:Linux,'
def sha(data):return hashlib.sha256(data).hexdigest()
def setting(data,section,key,value,append=False):
 text=data.decode('utf-8-sig');lines=text.splitlines(keepends=True);active=False;found=0
 for i,line in enumerate(lines):
  match=re.match(r'^\s*\[([^]]+)\]',line)
  if match:active=match[1]==section
  if active and re.match(r'^'+re.escape(key)+r'\s*=',line):
   found+=1;old=line.split('=',1)[1].strip()
   new=(old if value in old.split(',') else old+','+value) if append else value
   if old!=new:lines[i]=line.split('=',1)[0]+'= '+new+('\r\n' if line.endswith('\r\n') else '\n')
 if found!=1:raise ValueError(f'Expected one [{section}] {key}, got {found}')
 return (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'')+''.join(lines).encode()
def syncdir(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def replace(path,data,meta):
 fd,tmp=tempfile.mkstemp(prefix='.v40-psp-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:
   f.write(data);f.flush();current=os.fstat(f.fileno())
   if (current.st_uid,current.st_gid)!=(meta.st_uid,meta.st_gid):os.fchown(f.fileno(),meta.st_uid,meta.st_gid)
   if stat.S_IMODE(current.st_mode)!=stat.S_IMODE(meta.st_mode):os.fchmod(f.fileno(),stat.S_IMODE(meta.st_mode))
   os.fsync(f.fileno())
  os.replace(tmp,path);syncdir(path.parent)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def no_game():
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:exe=os.readlink(p/'exe')
  except OSError:continue
  if 'ppsspp' in exe.lower():raise RuntimeError('Exit PPSSPP before editing its settings')
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--database',type=Path,required=True)
 parser.add_argument('--system-dir',type=Path,required=True)
 parser.add_argument('--apply',action='store_true')
 parser.add_argument('--backup-dir',type=Path)
 args=parser.parse_args();changes=[]
 def add(path,transform):
  st=path.lstat()
  if not stat.S_ISREG(st.st_mode):raise ValueError('Not a regular file: '+str(path))
  before=path.read_bytes();after=transform(before)
  if before!=after:changes.append((path,before,after,st))
 def mapping(data):
  matches=[line for line in data.decode().splitlines() if line.startswith(MAPPING.split(',')[0]+',')]
  if matches:
   if matches!=[MAPPING]:raise ValueError('An existing CRC-specific V40 mapping differs; review it first')
   return data
  return MAPPING.encode()+b'\n'+data
 add(args.database,mapping)
 add(args.system_dir/'controls.ini',lambda b:setting(b,'ControlMapping','Pause','10-4',True))
 for name in ('ppsspp.ini','ppsspp.ini.sdl'):add(args.system_dir/name,lambda b:setting(b,'Graphics','SkipBufferEffects','False'))
 for path in sorted(args.system_dir.glob('*_ppsspp.ini')):
  if re.search(r'^\s*\[ControlMapping\]',path.read_text(encoding='utf-8-sig'),re.M):
   add(path,lambda b:setting(b,'ControlMapping','Pause','10-4',True))
 report={'applied':False,'changes':[{'path':str(p),'before_sha256':sha(a),'after_sha256':sha(b),'uid':m.st_uid,'gid':m.st_gid,'mode':stat.S_IMODE(m.st_mode)} for p,a,b,m in changes]}
 if args.apply and changes:
  if args.backup_dir is None:parser.error('--apply requires --backup-dir')
  no_game();args.backup_dir.mkdir(mode=0o700,parents=False,exist_ok=False)
  for i,(p,before,after,meta) in enumerate(changes):
   dest=args.backup_dir/f'{i}-{p.name}'
   with dest.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
  with (args.backup_dir/'manifest.json').open('x') as f:json.dump(report,f,indent=2);f.flush();os.fsync(f.fileno())
  syncdir(args.backup_dir);syncdir(args.backup_dir.parent);attempted=[]
  try:
   for path,before,after,meta in changes:
    no_game()
    if path.read_bytes()!=before:raise RuntimeError('File changed since inspection: '+str(path))
    attempted.append((path,before,after,meta));replace(path,after,meta)
    st=path.stat()
    if path.read_bytes()!=after or (st.st_uid,st.st_gid,stat.S_IMODE(st.st_mode))!=(meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode)):raise RuntimeError('Readback differs: '+str(path))
  except BaseException:
   for path,before,after,meta in reversed(attempted):
    current=path.read_bytes()
    if current not in (before,after):raise RuntimeError('Concurrent change prevents rollback: '+str(path))
    if current!=before:replace(path,before,meta)
   raise
  report['applied']=True
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
