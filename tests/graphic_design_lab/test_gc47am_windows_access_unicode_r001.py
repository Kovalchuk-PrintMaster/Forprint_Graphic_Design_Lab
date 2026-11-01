#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).resolve()
SRC=HERE.parents[2]/'scripts/graphic_design_lab/greeting_cards/gc47am_windows_access_unicode_r001.py'
PKG=HERE.parents[3]

def module(path,name):
 spec=importlib.util.spec_from_file_location(name,path)
 x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)
 return x

am=module(SRC,'am_test')
ak_src=Path(os.environ.get('GC47AM_AK_TEST_SRC','/mnt/data/gc47ak_build/payload/scripts/graphic_design_lab/greeting_cards/gc47ak_windows_client_deploy_r001.py'))
al_src=Path(os.environ.get('GC47AM_AL_TEST_SRC','/mnt/data/gc47al_build/payload/scripts/graphic_design_lab/greeting_cards/gc47al_windows_client_repair_r001.py'))
# In the actual s01 installation, reference modules live inside GDL rather than /mnt/data.
if not ak_src.exists() or not al_src.exists():
 root=Path(os.environ['GC47AM_GDL_ROOT'])
 ak_src=root/'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_client_deploy_r001.py'
 al_src=root/'scripts/graphic_design_lab/greeting_cards/gc47al_windows_client_repair_r001.py'

class TestGC47AM(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  base=Path(self.tmp.name)
  self.root=base/'forprint_graphic_design_lab'
  self.rel=am.REL
  (self.root/self.rel).mkdir(parents=True)
  (self.root/'tmp').mkdir()
  (self.root/'.git').mkdir()
  (self.root/'.venv_gdl/bin').mkdir(parents=True)
  (self.root/'.venv_gdl/bin/python').touch()
  shutil.copyfile(ak_src,self.root/self.rel/'gc47ak_windows_client_deploy_r001.py')
  shutil.copyfile(al_src,self.root/self.rel/'gc47al_windows_client_repair_r001.py')
  self.ak=module(self.root/self.rel/'gc47ak_windows_client_deploy_r001.py','akfixture'+str(id(self)))
  self.al=module(self.root/self.rel/'gc47al_windows_client_repair_r001.py','alfixture'+str(id(self)))
  self.share=base/'smb';self.share.mkdir()
  self.client='Виктория Беспалова _+380 67 793 00 15'
  self.input=self.share/self.client/'_forprint_automation'/'input'
  self.input.mkdir(parents=True)
  (self.input.parent/'output').mkdir()
  (self.input.parent/'template_studio').mkdir()
  (self.input/'ForPrint_Launcher.cmd').write_bytes(self.ak.cmd_bytes())
  (self.input/'ForPrint_Launcher.ps1').write_bytes(self.al.generate_ps1(self.client,self.ak))
  (self.input/'ForPrint_Launcher_ПОЧАТИ_ТУТ.txt').write_bytes(self.al.generate_help(self.ak))
  os.chmod(self.input/'ForPrint_Launcher.cmd',0o644)
  os.chmod(self.input/'ForPrint_Launcher.ps1',0o644)
 def info(self):return am.context(self.client,self.root,self.share)
 def repair(self):return am.apply(self.client,self.root,self.share)
 def path(self,n):return self.input/n
 def mode(self,n):return stat.S_IMODE(self.path(n).stat().st_mode)
 def assert_blocked(self, message):
  with self.assertRaises(am.Blocked) as cm:self.repair()
  self.assertIn(message,str(cm.exception))
 def test_01_cmd_source_ascii(self):self.assertTrue(all(x<128 for x in am.CMD_NEW))
 def test_02_terminal_bootstrap(self):self.assertIn(b'wt.exe',am.CMD_NEW)
 def test_03_terminal_no_double_host(self):self.assertIn(b'if defined WT_SESSION',am.CMD_NEW)
 def test_04_terminal_fallback(self):self.assertIn(b'CLASSIC_CMD_UTF8_FALLBACK',am.CMD_NEW)
 def test_05_terminal_no_autorun_native(self):
  self.assertNotIn(b'--mode interactive',am.CMD_NEW)
  self.assertNotIn(b'LAUNCH ',am.CMD_NEW)
  self.assertEqual(am.CMD_NEW.count(b'ForPrint_Launcher.ps1'),1)
 def test_06_permission_0644(self):self.assertEqual(am.with_execute_where_read(0o644),0o755)
 def test_07_permission_0640(self):self.assertEqual(am.with_execute_where_read(0o640),0o750)
 def test_08_permission_0600(self):self.assertEqual(am.with_execute_where_read(0o600),0o700)
 def test_09_permission_no_new_writes(self):
  for m in (0o444,0o600,0o640,0o644,0o750):
   self.assertEqual(am.with_execute_where_read(m)&0o222,m&0o222)
   self.assertEqual(am.with_execute_where_read(m)&0o444,m&0o444)
 def test_10_source_sha_matches(self):self.assertEqual(am.sha(self.ak.cmd_bytes()),am.CMD_OLD_SHA)
 def test_11_inspect_current(self):
  self.assertEqual(self.info()[3],am.CMD_OLD_SHA)
 def test_12_repair(self):
  self.assertEqual(self.repair(),'REPAIRED_GUARDED_WINDOWS_TERMINAL_AND_SCRIPT_EXECUTE')
  self.assertEqual(self.path('ForPrint_Launcher.cmd').read_bytes(),am.CMD_NEW)
  self.assertEqual(self.mode('ForPrint_Launcher.cmd'),0o755)
  self.assertEqual(self.mode('ForPrint_Launcher.ps1'),0o755)
 def test_13_idempotent(self):
  self.repair();self.assertEqual(self.repair(),'ALREADY_REPAIRED')
 def test_14_ps1_source_unchanged(self):
  before=self.path('ForPrint_Launcher.ps1').read_bytes()
  self.repair();self.assertEqual(before,self.path('ForPrint_Launcher.ps1').read_bytes())
 def test_15_help_unchanged(self):
  before=self.path('ForPrint_Launcher_ПОЧАТИ_ТУТ.txt').read_bytes()
  self.repair();self.assertEqual(before,self.path('ForPrint_Launcher_ПОЧАТИ_ТУТ.txt').read_bytes())
 def test_16_backup_created_private(self):
  self.repair()
  base=self.root/'tmp'/'gc47am_windows_client_backup_r001'/am.sha(self.client.encode('utf8'))[:20]
  self.assertEqual((base/'ForPrint_Launcher.cmd.original').read_bytes(),self.ak.cmd_bytes())
  self.assertEqual(stat.S_IMODE((base/'state.json').stat().st_mode),0o600)
 def test_17_other_launcher_not_changed(self):
  p=self.input/'Створити_листівку.cmd';p.write_bytes(b'LEGACY')
  self.repair();self.assertEqual(p.read_bytes(),b'LEGACY')
 def test_18_reject_modified_cmd(self):
  self.path('ForPrint_Launcher.cmd').write_bytes(b'ALTERED')
  self.assert_blocked('CMD_CHANGED')
 def test_19_reject_modified_ps1(self):
  self.path('ForPrint_Launcher.ps1').write_bytes(b'ALTERED')
  self.assert_blocked('PS1_CHANGED')
 def test_20_reject_cmd_symlink(self):
  p=self.path('ForPrint_Launcher.cmd');p.unlink();p.symlink_to(self.path('ForPrint_Launcher.ps1'))
  self.assert_blocked('CLIENT_SCRIPT_MISSING')
 def test_21_reject_ps1_symlink(self):
  p=self.path('ForPrint_Launcher.ps1');p.unlink();p.symlink_to(self.path('ForPrint_Launcher.cmd'))
  self.assert_blocked('CLIENT_SCRIPT_MISSING')
 def test_22_reject_outside_share_client(self):
  with self.assertRaises(Exception):am.context('../bad',self.root,self.share)
 def test_23_no_python_ssh_calls(self):
  source=SRC.read_text()
  self.assertNotIn('subprocess.run(',source)
  self.assertNotIn('paramiko',source)
 def test_24_reject_extended_acl(self):
  orig=am.acl_state
  with mock.patch.object(am,'acl_state',side_effect=lambda p:'EXTENDED_POSIX_ACL' if p.name.endswith('.cmd') else orig(p)):
   self.assert_blocked('EXTENDED_FILE_ACL_REVIEW_REQUIRED')
 def test_25_no_world_writable(self):
  os.chmod(self.path('ForPrint_Launcher.cmd'),0o646)
  self.assert_blocked('WORLD_WRITABLE')
 def test_26_preserve_0640_access_classes(self):
  for n in ('ForPrint_Launcher.cmd','ForPrint_Launcher.ps1'):os.chmod(self.path(n),0o640)
  self.repair();self.assertEqual(self.mode('ForPrint_Launcher.cmd'),0o750)
  self.assertEqual(self.mode('ForPrint_Launcher.ps1'),0o750)
 def test_27_preserve_0600_access_classes(self):
  for n in ('ForPrint_Launcher.cmd','ForPrint_Launcher.ps1'):os.chmod(self.path(n),0o600)
  self.repair();self.assertEqual(self.mode('ForPrint_Launcher.cmd'),0o700)
  self.assertEqual(self.mode('ForPrint_Launcher.ps1'),0o700)
 def test_28_client_id_bound_in_ps1(self):
  self.assertIn(self.client.encode('utf-8')[:4],self.client.encode('utf-8'))
  self.assertIn(b'gc47ak_windows_bridge_r001.py',self.path('ForPrint_Launcher.ps1').read_bytes())
 def test_29_prevent_unreadable_script(self):
  os.chmod(self.path('ForPrint_Launcher.cmd'),0)
  self.assert_blocked('SCRIPT_NOT_READABLE')
 def test_30_read_only_report(self):
  orig=self.path('ForPrint_Launcher.cmd').read_bytes()
  import io,contextlib
  with contextlib.redirect_stdout(io.StringIO()):am.report(self.client,self.root,self.share)
  self.assertEqual(orig,self.path('ForPrint_Launcher.cmd').read_bytes())
 def test_31_repair_does_not_change_folder_modes(self):
  old=stat.S_IMODE(self.input.stat().st_mode)
  self.repair()
  self.assertEqual(old,stat.S_IMODE(self.input.stat().st_mode))
 def test_32_no_extra_dotfiles_in_client_input(self):
  old={x.name for x in self.input.iterdir()}
  self.repair()
  self.assertEqual(old,{x.name for x in self.input.iterdir()})
 def test_33_no_render_gates_modified(self):
  src=SRC.read_text()
  self.assertNotIn('GC47T_VARIANT=',src)
  self.assertNotIn('git commit',src)
 def test_34_refuse_invalid_src_hash(self):
  p=self.root/self.rel/'gc47al_windows_client_repair_r001.py'
  p.write_text('tampered')
  self.assert_blocked('PINNED_MODULE_CHANGED')
 def test_35_new_cmd_has_no_cyrillic_bom(self):
  self.assertFalse(am.CMD_NEW.startswith(b'\xef\xbb\xbf'))

if __name__=='__main__':unittest.main()
