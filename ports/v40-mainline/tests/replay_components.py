#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replay public mail patches against local pinned upstream objects, without network."""
from pathlib import Path
import argparse,hashlib,io,json,os,subprocess,tarfile,tempfile
PORT=Path(__file__).resolve().parents[1]
def extract(repo,commit,dest):
 data=subprocess.check_output(['git','-C',str(repo),'archive',commit])
 with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(dest,filter='data')
def inventory(root):
 result={}
 for p in root.rglob('*'):
  if p.is_symlink():result[str(p.relative_to(root))]=('link',os.readlink(p))
  elif p.is_file():result[str(p.relative_to(root))]=(hashlib.sha256(p.read_bytes()).hexdigest(),bool(p.stat().st_mode&0o111))
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('frontend','sdl','hotkey'):parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args();report=[]
 for component in json.loads((PORT/'components/source-lock.json').read_text()):
  name=component['component'];repo=getattr(args,name).resolve()
  with tempfile.TemporaryDirectory(prefix='v40-source-replay-') as tmp:
   actual=Path(tmp)/'actual';expected=Path(tmp)/'expected';actual.mkdir();expected.mkdir()
   extract(repo,component['base_commit'],actual);extract(repo,component['accepted_source_commit'],expected)
   for patch in component['patches']:subprocess.run(['git','apply','--whitespace=nowarn',str(PORT/'components'/name/patch)],cwd=actual,check=True)
   got,want=inventory(actual),inventory(expected)
   differences=sorted(k for k in got.keys()|want.keys() if got.get(k)!=want.get(k))
   if differences:raise ValueError(name+' replay differs: '+repr(differences))
   report.append({'component':name,'files':len(got),'patches':len(component['patches']),'accepted_tree_matched':True})
 print(json.dumps({'passed':True,'network_used':False,'components':report},indent=2))
if __name__=='__main__':main()
