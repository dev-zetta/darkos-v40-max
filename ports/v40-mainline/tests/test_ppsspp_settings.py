#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise dry-run, additive per-game edits, backups and idempotence."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/configure_ppsspp.py'
class SettingsTest(unittest.TestCase):
 def test_preserves_preferences_and_backups(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);system=root/'SYSTEM';system.mkdir();db=root/'gamecontrollerdb.txt'
   db.write_text('old-controller,Generic,a:b0,\n')
   (system/'controls.ini').write_bytes(b'\xef\xbb\xbf[ControlMapping]\r\nPause = 10-106\r\nStart = 10-197\r\n')
   for f in ('ppsspp.ini','ppsspp.ini.sdl'):(system/f).write_text('[Graphics]\nSkipBufferEffects = True\nInternalResolution = 2\n[Sound]\nGameVolume = 41\n')
   (system/'GAME_ppsspp.ini').write_text('[Graphics]\nSkipBufferEffects = True\n[ControlMapping]\nPause = 10-104\nSelect = 10-196\n')
   paths=[db,*system.iterdir()];before={p:p.read_bytes() for p in paths};modes={p:p.stat().st_mode for p in paths}
   command=[sys.executable,str(SCRIPT),'--database',str(db),'--system-dir',str(system)]
   dry=json.loads(subprocess.check_output(command,text=True));self.assertFalse(dry['applied']);self.assertEqual(before,{p:p.read_bytes() for p in paths})
   backup=root/'backup';result=json.loads(subprocess.check_output(command+['--apply','--backup-dir',str(backup)],text=True));self.assertTrue(result['applied']);self.assertEqual(len(result['changes']),5)
   self.assertIn(b'Pause = 10-106,10-4\r\n', (system/'controls.ini').read_bytes());self.assertTrue((system/'controls.ini').read_bytes().startswith(b'\xef\xbb\xbf'))
   for f in ('ppsspp.ini','ppsspp.ini.sdl'):
    text=(system/f).read_text();self.assertIn('SkipBufferEffects = False',text);self.assertIn('GameVolume = 41',text);self.assertIn('InternalResolution = 2',text)
   text=(system/'GAME_ppsspp.ini').read_text();self.assertIn('SkipBufferEffects = True',text);self.assertIn('Pause = 10-104,10-4',text)
   self.assertEqual(modes,{p:p.stat().st_mode for p in paths})
   for i,item in enumerate(result['changes']):self.assertEqual((backup/f'{i}-{Path(item["path"]).name}').read_bytes(),before[Path(item['path'])])
   again=json.loads(subprocess.check_output(command,text=True));self.assertEqual(again['changes'],[])
 def test_rejects_symlink_before_mutation(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);db=root/'db';db.write_text('old\n');system=root/'SYSTEM';system.mkdir();(system/'controls.ini').symlink_to(db)
   result=subprocess.run([sys.executable,str(SCRIPT),'--database',str(db),'--system-dir',str(system),'--apply','--backup-dir',str(root/'backup')],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertEqual(db.read_text(),'old\n');self.assertFalse((root/'backup').exists())
if __name__=='__main__':unittest.main()
