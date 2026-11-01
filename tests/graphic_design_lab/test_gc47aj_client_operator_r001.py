#!/usr/bin/env python3
"""GC47AJ: offline fake-SMB tests, no live PREPRESS/SSH or client data."""
from __future__ import annotations
from contextlib import redirect_stdout
import hashlib
import importlib.util
from io import StringIO
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT/'scripts/graphic_design_lab/greeting_cards'

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,PY/filename)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

ui=load('gc47aj_test_ui','gc47aj_client_operator_r001.py')
deployer=load('gc47aj_test_deployer','gc47aj_client_entry_deploy_r001.py')

class FakeAI:
    JOB_RE=re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
    ATTEMPT_RE=re.compile(r'^p\d{14}-[0-9a-f]{8}$')
    GC47U='trusted_gc47u.py'
    def __init__(self, root):
        self.SHARE=root/'share'
        self.ws=self.SHARE/'Test Client'/'_forprint_automation'
        for p in ('input','output','template_studio'):(self.ws/p).mkdir(parents=True,exist_ok=True)
        self.zip=self.ws/'input'/'accepted.zip'
        with zipfile.ZipFile(self.zip,'w') as z:z.writestr('accepted_constructor_bundle.yaml','ok')
        self.other=self.ws/'input'/'other.zip'
        with zipfile.ZipFile(self.other,'w') as z:z.writestr('other','ok')
        self.run_calls=[]
        self.jobs=[{'id':'gdl_gc_test_20261101','profile':{'front':'STANDARD','image':'DEFAULT_ASSET','signature':'GRIGO'},'illustrator_supported':True},
                   {'id':'gdl_gc_alt_20261101','profile':{'front':'CUSTOM','image':'PORTRAIT','signature':'GRIGO'},'illustrator_supported':False}]
    def source_guard(self):pass
    def workspace(self,client):
        if client!='Test Client':raise ValueError('Unknown client')
        return self.ws
    def input_zips(self,ws):return [self.zip,self.other]
    def inspect_zip(self,path,verify_crc=True):
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            return {'members':len(z.namelist()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    def accepted_jobs(self,client):return self.jobs,self.zip
    def pilot(self,*args,**kwargs):self.run_calls.append(('pilot',args,kwargs));return 0
    def status_or_collect(self,*args,**kwargs):self.run_calls.append(('result',args,kwargs));return 0
    def call_existing(self,*args):self.run_calls.append(('route',args));return None

class TestGC47AJ(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.fake=FakeAI(self.root)
    def emit(self,func,*args):
        f=StringIO()
        with redirect_stdout(f):x=func(*args)
        return x,f.getvalue()
    def test_01_client_path_binds_to_input(self):
        self.assertEqual(ui.resolve_context(self.fake,str(self.fake.ws/'input')),('Test Client',self.fake.ws))
    def test_02_parent_folder_not_allowed(self):
        with self.assertRaisesRegex(ui.Blocked,'NOT_CLIENT_INPUT_FOLDER'):
            ui.resolve_context(self.fake,str(self.fake.ws))
    def test_03_input_symlink_blocked(self):
        (self.fake.ws/'input_link').symlink_to(self.fake.ws/'input')
        with self.assertRaises(ui.Blocked):ui.resolve_context(self.fake,str(self.fake.ws/'input_link'))
    def test_04_other_client_folder_invalid(self):
        with self.assertRaises(ValueError):self.fake.workspace('Outside')
    def test_05_source_shows_both_zips_and_accepted(self):
        _,out=self.emit(ui.show_source,self.fake,'Test Client',self.fake.ws)
        self.assertIn('ПРИЙНЯТИЙ ДЛЯ РОБОТИ',out)
        self.assertIn('ІНФОРМАЦІЙНИЙ / НЕ ОБРАНИЙ',out)
    def test_06_accepted_zip_must_be_in_input(self):
        outside=self.root/'outside.zip'
        outside.write_bytes(self.fake.zip.read_bytes())
        self.fake.accepted_jobs=lambda c:(self.fake.jobs,outside)
        with self.assertRaisesRegex(ui.Blocked,'ACCEPTED_ZIP_OUTSIDE'):
            ui.source_summary(self.fake,'Test Client',self.fake.ws)
    def test_07_selector_zero_cancel(self):
        with patch('builtins.input',return_value='0'):
            result,_=self.emit(ui.choose,['one'],'Choose')
            self.assertIsNone(result)
    def test_08_selector_invalid_then_valid(self):
        with patch('builtins.input',side_effect=['banana','7','2']):
            result,out=self.emit(ui.choose,['one','two'],'Choose')
        self.assertEqual(result,'two')
        self.assertIn('Введи номер',out)
    def test_09_no_launch_on_operator_cancel(self):
        with patch('builtins.input',side_effect=['1','1','']):
            result,_=self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(result,0);self.assertEqual(self.fake.run_calls,[])
    def test_10_confirmation_is_exact(self):
        with patch('builtins.input',side_effect=['1','1','LAUNCH wrong']):
            self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(self.fake.run_calls,[])
    def test_11_launch_delegates_exactly_once(self):
        with patch('builtins.input',side_effect=['1','1','LAUNCH gdl_gc_test_20261101']):
            self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(len(self.fake.run_calls),1)
        self.assertEqual(self.fake.run_calls[0][1],('Test Client','gdl_gc_test_20261101','illustrator'))
        self.assertEqual(self.fake.run_calls[0][2],{'confirm':True})
    def test_12_server_is_non_dispatch(self):
        with patch('builtins.input',side_effect=['1','2']):
            _,out=self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertIn('BLOCKED_RENDERER_CAPABILITY_NOT_PROVEN',out)
        self.assertEqual(self.fake.run_calls,[])
    def test_13_unsupported_profile(self):
        with patch('builtins.input',side_effect=['2','1']):
            self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(self.fake.run_calls,[])
    def test_14_source_change_prevents_dispatch(self):
        original=ui.source_summary
        count=[0]
        def changing(*args):
            count[0]+=1
            res=original(*args)
            if count[0]==2:return (*res[:3],dict(res[3],sha256='changed'))
            return res
        with patch.object(ui,'source_summary',side_effect=changing),patch('builtins.input',side_effect=['1','1']):
            with self.assertRaisesRegex(ui.Blocked,'SOURCE_CHANGED'):self.emit(ui.launch,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(self.fake.run_calls,[])
    def test_15_attempts_read_only(self):
        base=self.fake.ws/'output/greeting_card_pilots/gdl_gc_test_20261101/p20261101164831-aa44279c'
        base.mkdir(parents=True)
        out=ui.list_attempts(self.fake,self.fake.ws)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0][2],'результат є')
        self.assertEqual(self.fake.run_calls,[])
    def test_16_unsafe_attempts_ignored(self):
        base=self.fake.ws/'output/greeting_card_pilots/gdl_gc_test_20261101/not-valid'
        base.mkdir(parents=True)
        self.assertEqual(ui.list_attempts(self.fake,self.fake.ws),[])
    def test_17_review_status_without_confirm(self):
        base=self.fake.ws/'output/greeting_card_pilots/gdl_gc_test_20261101/p20261101164831-aa44279c';base.mkdir(parents=True)
        with patch('builtins.input',side_effect=['1','1']):
            self.emit(ui.review,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(len(self.fake.run_calls),1)
        self.assertEqual(self.fake.run_calls[0][1][0],'status')
    def test_18_review_collect_requires_phrase(self):
        base=self.fake.ws/'template_studio/greeting_card_pilots/gdl_gc_test_20261101/p20261101164831-aa44279c';base.mkdir(parents=True)
        with patch('builtins.input',side_effect=['1','2','COLLECT wrong']):
            self.emit(ui.review,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(self.fake.run_calls,[])
    def test_19_review_collect_exact_phrase(self):
        base=self.fake.ws/'template_studio/greeting_card_pilots/gdl_gc_test_20261101/p20261101164831-aa44279c';base.mkdir(parents=True)
        with patch('builtins.input',side_effect=['1','2','COLLECT p20261101164831-aa44279c']):
            self.emit(ui.review,self.fake,'Test Client',self.fake.ws)
        self.assertEqual(self.fake.run_calls[0][2],{'confirm':True})
    def test_28_published_result_cannot_collect_again(self):
        base=self.fake.ws/'output/greeting_card_pilots/gdl_gc_test_20261101/p20261101164831-aa44279c';base.mkdir(parents=True)
        with patch('builtins.input',side_effect=['1','2','0']):
            _,text=self.emit(ui.review,self.fake,'Test Client',self.fake.ws)
        self.assertIn('Повторне отримання не пропоную',text)
        self.assertEqual(self.fake.run_calls,[])
    def test_20_main_readonly_check(self):
        with patch.object(ui,'ai_load',return_value=self.fake):
            result,out=self.emit(ui.main,['--input-dir',str(self.fake.ws/'input'),'--mode','check'])
        self.assertEqual(result,0);self.assertIn('GC47AJ_CLIENT_ENTRY=PASS',out)
        self.assertEqual(self.fake.run_calls,[])
    def test_21_wrapped_ui_is_minimal(self):
        body=deployer.wrapper_bytes(self.root).decode('utf-8')
        self.assertIn('--mode interactive',body)
        self.assertIn('--input-dir "$HERE"',body)
        self.assertNotIn('ssh ',body)
        self.assertNotIn('password',body.lower())
    def test_22_client_deployer_creates_side_by_side(self):
        self.setup_repo()
        self.assertEqual(deployer.install('Test Client',share=self.fake.SHARE,root=self.root),'INSTALLED_SIDE_BY_SIDE')
        self.assertTrue((self.fake.ws/'input'/deployer.ENTRY).is_file())
        self.assertEqual(deployer.install('Test Client',share=self.fake.SHARE,root=self.root),'ALREADY_INSTALLED')
    def test_23_existing_legacy_is_preserved(self):
        self.setup_repo()
        legacy=self.fake.ws/'input'/'old_runner.ps1';legacy.write_text('previous version')
        self.assertEqual(deployer.install('Test Client',share=self.fake.SHARE,root=self.root),'INSTALLED_SIDE_BY_SIDE')
        self.assertEqual(legacy.read_text(),'previous version')
    def test_24_target_conflict_not_overwritten(self):
        self.setup_repo()
        f=self.fake.ws/'input'/deployer.ENTRY;f.write_text('other work')
        with self.assertRaises(deployer.Blocked):deployer.install('Test Client',share=self.fake.SHARE,root=self.root)
        self.assertEqual(f.read_text(),'other work')
    def test_25_symlink_client_entry_blocked(self):
        self.setup_repo()
        f=self.fake.ws/'input'/deployer.ENTRY;f.symlink_to(self.fake.zip)
        with self.assertRaises(deployer.Blocked):deployer.install('Test Client',share=self.fake.SHARE,root=self.root)
    def test_26_partial_client_deployment_blocked(self):
        self.setup_repo()
        f=self.fake.ws/'input'/deployer.ENTRY;f.write_bytes(deployer.wrapper_bytes(self.root))
        with self.assertRaisesRegex(deployer.Blocked,'PARTIAL_CLIENT_DEPLOYMENT'):
            deployer.install('Test Client',share=self.fake.SHARE,root=self.root)
    def test_27_no_payload_in_client_script(self):
        text=ui.__doc__+'\n'+(PY/'gc47aj_client_operator_r001.py').read_text('utf-8')
        self.assertNotIn('subprocess.Popen(',text)
        self.assertNotIn('shell=True',text)
        self.assertNotIn('rmtree(',text)
        self.assertIn('ai.pilot(',text)
    def setup_repo(self):
        (self.root/'scripts/graphic_design_lab/greeting_cards').mkdir(parents=True,exist_ok=True)
        (self.root/'.venv_gdl/bin').mkdir(parents=True)
        (self.root/'.venv_gdl/bin/python').write_text('stub')
        (self.root/'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py').write_text('stub')

if __name__=='__main__':unittest.main(verbosity=2)
