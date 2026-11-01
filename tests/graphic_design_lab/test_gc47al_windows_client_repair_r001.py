"""GC47AL offline tests. No Windows/SSH/native attempt; temp SMB fixture only."""
from __future__ import annotations

import base64
import importlib.util
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

al = load('gc47al', HERE / 'gc47al_windows_client_repair_r001.py')
legacy_root = Path(os.environ['GC47AL_GDL_ROOT'])
ak = al.read_ak(legacy_root / 'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_client_deploy_r001.py')

class RepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='gc47al_')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'repo'
        self.share=Path(temp.name)/'share'
        self.share.mkdir()
        (self.root/'tmp').mkdir(parents=True)
        self.client='Виктория Беспалова _+380 67 793 00 15'
        self.ws=self.share/self.client/'_forprint_automation'
        for name in ('input','output','template_studio'):
            (self.ws/name).mkdir(parents=True,exist_ok=True)
        for name,content in ((al.CLIENT_CMD,ak.cmd_bytes()),(al.CLIENT_PS1,ak.ps1_bytes()),(al.CLIENT_HELP,ak.help_bytes())):
            (self.ws/'input'/name).write_bytes(content)

    def inspect(self):
        return al.inspect(self.client,self.share,self.root,ak)

    def repair(self):
        return al.repair(self.client,self.share,self.root,ak)

    def test_01_pinned_ak_generator_sha(self):
        self.assertEqual(al.sha(ak.ps1_bytes()),al.OLD_HASHES[al.CLIENT_PS1])
    def test_02_pinned_cmd_sha(self):
        self.assertEqual(al.sha(ak.cmd_bytes()),al.OLD_HASHES[al.CLIENT_CMD])
    def test_03_pinned_help_sha(self):
        self.assertEqual(al.sha(ak.help_bytes()),al.OLD_HASHES[al.CLIENT_HELP])
    def test_04_repair_before_install(self):
        ws,s,items=self.inspect()
        self.assertTrue(all(x=='OLD' for x in s.values()))
    def test_05_utf8_bom_ps1(self):
        self.assertTrue(al.generate_ps1(self.client,ak).startswith(b'\xef\xbb\xbf'))
    def test_06_utf8_bom_help(self):
        self.assertTrue(al.generate_help(ak).startswith(b'\xef\xbb\xbf'))
    def test_07_embedded_client_token(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        token=base64.b64encode(self.client.encode('utf-8')).decode('ascii')
        self.assertIn(token,s)
    def test_08_old_regex_removed(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertNotIn('GC47AK_ORIGINAL_CLIENT_UNC_REQUIRED',s)
    def test_09_path_suffix_required(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertIn('GC47AL_CLIENT_FOLDER_LAYOUT_REQUIRED',s)
        self.assertIn('_forprint_automation',s)
    def test_10_client_name_bound(self):
        self.assertIn('GC47AL_CLIENT_FOLDER_NOT_BOUND_TO_INSTALL',al.generate_ps1(self.client,ak).decode('utf-8-sig'))
    def test_11_unc_case(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertIn('GC47AL_NETWORK_PATH=VERIFIED_UNC_SHAPE',s)
    def test_12_mapped_network_check(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertIn('Get-CimInstance',s)
        self.assertIn('Get-WmiObject',s)
        self.assertIn('GC47AL_MAPPED_NETWORK_DRIVE_NOT_VERIFIED',s)
    def test_13_local_copy_denied(self):
        self.assertIn('GC47AL_LOCAL_COPY_NOT_ALLOWED',al.generate_ps1(self.client,ak).decode('utf-8-sig'))
    def test_14_utf8_encoding_both_directions(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertIn('[Console]::InputEncoding = $utf8',s)
        self.assertIn('[Console]::OutputEncoding = $utf8',s)
    def test_15_ssh_once(self):
        self.assertEqual(al.generate_ps1(self.client,ak).count(b'& $ssh.Source'),1)
    def test_16_ssh_strict_host_check(self):
        self.assertIn(b'StrictHostKeyChecking=yes',al.generate_ps1(self.client,ak))
    def test_17_no_render_or_retry_python(self):
        s=Path(al.__file__).read_text()
        self.assertNotIn('subprocess.run(',s)
        self.assertNotIn('os.system(',s)
    def test_18_cmd_untouched(self):
        old=(self.ws/'input'/al.CLIENT_CMD).read_bytes()
        self.repair()
        self.assertEqual((self.ws/'input'/al.CLIENT_CMD).read_bytes(),old)
    def test_19_live_scripts_changed_only_two(self):
        self.assertEqual(self.repair(),'REPAIRED_GUARDED_WITH_BACKUP')
        _,state,_=self.inspect()
        self.assertEqual(state[al.CLIENT_PS1],'NEW')
        self.assertEqual(state[al.CLIENT_HELP],'NEW')
        self.assertEqual(state[al.CLIENT_CMD],'OLD')
    def test_20_no_duplicate_repair(self):
        self.repair()
        self.assertEqual(self.repair(),'ALREADY_REPAIRED')
    def test_21_private_backup(self):
        self.repair()
        folder=self.root/'tmp'/'gc47al_windows_client_backups_r001'/al.sha(self.client.encode('utf-8'))[:20]
        self.assertEqual((folder/al.CLIENT_PS1).read_bytes(),ak.ps1_bytes())
        self.assertEqual(folder.stat().st_mode & 0o777,0o700)
    def test_22_no_old_launcher_write(self):
        old=self.ws/'input'/'Створити_листівку.cmd'
        old.write_bytes(b'ORIGINAL LEGACY CMD')
        self.repair()
        self.assertEqual(old.read_bytes(),b'ORIGINAL LEGACY CMD')
    def test_23_reject_modified_old_ps1(self):
        (self.ws/'input'/al.CLIENT_PS1).write_bytes(b'TAMPERED')
        with self.assertRaises(al.Blocked):self.repair()
    def test_24_reject_modified_old_help(self):
        (self.ws/'input'/al.CLIENT_HELP).write_bytes(b'TAMPERED')
        with self.assertRaises(al.Blocked):self.repair()
    def test_25_reject_missing_ps1(self):
        (self.ws/'input'/al.CLIENT_PS1).unlink()
        with self.assertRaises(al.Blocked):self.repair()
    def test_26_reject_partial_repair(self):
        (self.ws/'input'/al.CLIENT_PS1).write_bytes(al.generate_ps1(self.client,ak))
        with self.assertRaises(al.Blocked):self.inspect()
    def test_27_reject_symlink_ps1(self):
        p=self.ws/'input'/al.CLIENT_PS1
        p.unlink();p.symlink_to(self.ws/'input'/al.CLIENT_CMD)
        with self.assertRaises(al.Blocked):self.inspect()
    def test_28_reject_client_name_path(self):
        with self.assertRaises(ak.Blocked):al.inspect('../foo',self.share,self.root,ak)
    def test_29_reject_not_existing_client(self):
        with self.assertRaises(ak.Blocked):al.inspect('OtherClient',self.share,self.root,ak)
    def test_30_no_change_during_check(self):
        before={p.name:al.sha(p.read_bytes()) for p in (self.ws/'input').iterdir()}
        self.inspect()
        after={p.name:al.sha(p.read_bytes()) for p in (self.ws/'input').iterdir()}
        self.assertEqual(before,after)
    def test_31_second_client_different_token(self):
        s=al.generate_ps1('Інший Клієнт',ak)
        self.assertNotEqual(al.generate_ps1(self.client,ak),s)
    def test_32_no_windows_key_storage(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertNotIn('IdentityFile',s)
        self.assertNotIn('password=',s.lower())
    def test_33_original_ssh_destination_preserved(self):
        s=al.generate_ps1(self.client,ak).decode('utf-8-sig')
        self.assertIn('gc47ak_windows_bridge_r001.py',s)
        self.assertIn('--mode interactive --client-b64 ',s)
    def test_34_output_help_explains_font(self):
        s=al.generate_help(ak).decode('utf-8-sig')
        self.assertIn('Consolas',s)
        self.assertIn('Windows Terminal',s)
    def test_35_no_prepress_hub(self):
        self.assertNotIn('forprint_prepress_hub',Path(al.__file__).read_text())

if __name__=='__main__':unittest.main(verbosity=2)
