#!/usr/bin/env python3
"""GC47AI isolated deterministic tests, never use live SMB/SSH/Illustrator."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards/gc47ai_illustrator_first_launcher_r001.py'
spec = importlib.util.spec_from_file_location('gc47ai_under_test', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeReturn:
    def __init__(self, returncode=0): self.returncode = returncode

class TestGC47AI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def zfile(self, files=None):
        p=self.root/'a.zip'
        with zipfile.ZipFile(p,'w') as z:
            for k,v in (files or {'accepted_constructor_bundle.yaml':'x','artifact_manifest.yaml':'y'}).items():
                z.writestr(k,v)
        return p

    def test_01_good_zip_crc_sha(self):
        p=self.zfile(); v=m.inspect_zip(p)
        self.assertEqual(v['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertTrue(v['crc_checked'])
    def test_02_metadata_non_authorizing(self):
        p=self.zfile(); self.assertEqual(m.inspect_zip(p,False)['crc_checked'],False)
    def test_03_reject_parent(self):
        with self.assertRaisesRegex(m.Blocked,'ZIP_MEMBER_PATH'):
            m.inspect_zip(self.zfile({'../escape':'bad'}))
    def test_04_reject_absolute(self):
        with self.assertRaises(m.Blocked): m.inspect_zip(self.zfile({'/tmp/evil':'bad'}))
    def test_05_reject_windows_backslash(self):
        with self.assertRaises(m.Blocked): m.inspect_zip(self.zfile({'..\\bad':'bad'}))
    def test_06_reject_drive(self):
        with self.assertRaises(m.Blocked): m.inspect_zip(self.zfile({'C:/evil':'bad'}))
    def test_07_reject_duplicate_members(self):
        import warnings
        p=self.root/'dup.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('x','a');z.writestr('x','b')
        with self.assertRaisesRegex(m.Blocked,'ZIP_DUPLICATE'):m.inspect_zip(p)
    def test_08_reject_corrupt_zip(self):
        p=self.root/'bad.zip';p.write_bytes(b'not-a-zip')
        with self.assertRaises(zipfile.BadZipFile):m.inspect_zip(p)
    def test_09_reject_too_large(self):
        p=self.zfile()
        with patch.object(m,'MAX_ZIP',10):
            with self.assertRaises(m.Blocked):m.inspect_zip(p)
    def test_10_reject_symlink_zip(self):
        p=self.zfile(); q=self.root/'link.zip';q.symlink_to(p)
        with self.assertRaises(m.Blocked):m.inspect_zip(q)
    def test_11_workspace_inside_share(self):
        sh=self.root/'share';w=sh/'A'/'_forprint_automation'
        for part in ('input','output','template_studio'):(w/part).mkdir(parents=True)
        self.assertEqual(m.workspace('A',sh),w)
    def test_12_workspace_path_traversal(self):
        with self.assertRaisesRegex(m.Blocked,'CLIENT_NAME_INVALID'):m.workspace('../A',self.root)
    def test_13_workspace_symlink(self):
        sh=self.root/'share';sh.mkdir();(sh/'A').symlink_to(self.root)
        with self.assertRaises(m.Blocked):m.workspace('A',sh)
    def test_14_client_discovery(self):
        sh=self.root/'share';w=sh/'A'/'_forprint_automation'
        for part in ('input','output','template_studio'):(w/part).mkdir(parents=True)
        self.assertEqual(m.clients(sh),['A'])
    def test_15_input_zip_selection(self):
        w=self.root/'w';(w/'input').mkdir(parents=True)
        (w/'input'/'ignore.txt').write_text('x')
        self.zfile().replace(w/'input'/'b.zip')
        self.assertEqual([p.name for p in m.input_zips(w)],['b.zip'])
    def test_16_server_route_does_not_dispatch(self):
        with patch.object(m,'selected_job',side_effect=AssertionError('must not access input')):
            self.assertEqual(m.pilot('A','job-id','server-local',False),2)
    def test_17_illustrator_needs_confirmation(self):
        with self.assertRaisesRegex(m.Blocked,'EXPLICIT_SINGLE_USE'):
            m.pilot('A','job-id','illustrator',False)
    def test_18_illustrator_requires_accepted_job(self):
        with patch.object(m,'selected_job',side_effect=m.Blocked('JOB_NOT_ACCEPTED')):
            with self.assertRaisesRegex(m.Blocked,'JOB_NOT_ACCEPTED'):
                m.pilot('A','job-id','illustrator',True)
    def test_19_dispatch_uses_existing_modules(self):
        calls=[]
        profile={'profile':{'front':'STANDARD','image':'DEFAULT_ASSET','signature':'GRIGO'},'illustrator_supported':True}
        def fake(script,args,runner):calls.append((script.name,args))
        with patch.object(m,'selected_job',return_value=profile),patch.object(m,'call_existing',side_effect=fake):
            self.assertEqual(m.pilot('A','job-test','illustrator',True),0)
        self.assertEqual(len(calls),3)
        self.assertEqual([c[1][1] for c in calls],['gate','check','pilot'])
        self.assertIn('--confirm-native-once',calls[-1][1])
    def test_20_gate_failure_prevents_pilot(self):
        calls=[]
        profile={'profile':{'front':'STANDARD','image':'DEFAULT_ASSET','signature':'GRIGO'},'illustrator_supported':True}
        def fake(script,args,runner):calls.append(args);raise m.Blocked('GATE_BLOCKED')
        with patch.object(m,'selected_job',return_value=profile),patch.object(m,'call_existing',side_effect=fake):
            with self.assertRaises(m.Blocked):m.pilot('A','job-test','illustrator',True)
        self.assertEqual(len(calls),1)
    def test_21_failed_subprocess_no_retry(self):
        count=[]
        def fake(argv,**kwargs):count.append(argv);return FakeReturn(2)
        with patch.object(m,'source_guard'):
            with self.assertRaisesRegex(m.Blocked,'EXISTING_CHAIN_FAILED'):
                m.call_existing(m.GC47T,['--mode','pilot'],fake)
        self.assertEqual(len(count),1)
    def test_22_collect_requires_explicit_confirm(self):
        with patch.object(m,'workspace'):
            with self.assertRaisesRegex(m.Blocked,'EXPLICIT_COLLECTION'):
                m.status_or_collect('collect','A','job-test','p20261101153052-10e4b79f')
    def test_23_attempt_format(self):
        with self.assertRaises(m.Blocked):m.status_or_collect('status','A','job-test','../evil')
    def test_24_status_calls_existing_readonly(self):
        calls=[]
        with patch.object(m,'workspace'),patch.object(m,'call_existing',side_effect=lambda script,args,runner:calls.append(args)):
            self.assertEqual(m.status_or_collect('status','A','job-test','p20261101153052-10e4b79f'),0)
        self.assertEqual(calls[0][1],'status')
        self.assertNotIn('--confirm-native-once',calls[0])
    def test_25_no_source_overwrite_in_launcher(self):
        text=SCRIPT.read_text('utf-8')
        self.assertNotIn('subprocess.Popen(',text)
        self.assertNotIn('shell=True',text)
        self.assertNotIn('shutil.rmtree(',text)
        self.assertIn('GC47T',text)
        self.assertIn('GC47U',text)

if __name__ == '__main__':unittest.main(verbosity=2)
