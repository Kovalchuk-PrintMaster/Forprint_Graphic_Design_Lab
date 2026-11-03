#!/usr/bin/env python3
"""Offline tests for bounded Phase2C native LAB bridge; no Windows contact."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SRC=HERE.parents[2]/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_dynamic_native_v1.py'
if not SRC.is_file(): SRC=Path(__file__).resolve().parents[5]/'payload/scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_dynamic_native_v1.py'
# Works both in installed repo and unpacked payload.
if not SRC.is_file(): SRC=Path(__file__).resolve().parent.parent.parent/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_dynamic_native_v1.py'
spec=importlib.util.spec_from_file_location('dynamic2c',SRC)
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)

class TestNative(unittest.TestCase):
    def test_public_plan_no_authority(self):
        obj=n.public_plan({'job_id':'gdl_gc_new_0001','zip_name':'job.zip','archive_sha256':'a'*64,
             'native_supported':True,'record':{'native_jsx_sha256':'b'*64,'manifest_sha256':'c'*64,
              'asset_count':12,'front_family':'STANDARD','image_mode':'DEFAULT_ASSET',
              'signature_variant':'GRIGO','sender_rows':4}})
        self.assertEqual(obj['status'],'READY_FOR_OPERATOR_LAB_SINGLE_USE')
        self.assertFalse(obj['native_dispatch']);self.assertFalse(obj['review_independently_attested'])
        self.assertFalse(obj['production_ready']);self.assertFalse(obj['automatic_retry'])

    def test_portrait_native_blocked(self):
        row={'native_jsx_sha256':'b'*64,'manifest_sha256':'c'*64,'asset_count':12,
             'front_family':'STANDARD','image_mode':'PORTRAIT','signature_variant':'GRIGO','sender_rows':4}
        data={'job_id':'gdl_gc_new_0001','zip_name':'job.zip','archive_sha256':'a'*64,'native_supported':False,'record':row}
        self.assertEqual(n.public_plan(data)['status'],'BLOCKED_NATIVE_PORTRAIT_TRANSPORT_NOT_WIRED')
        with self.assertRaisesRegex(n.Blocked,'PORTRAIT_NATIVE'):
            n.source_pilot(data)

    def test_claim_exactly_once_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Path(tmp);(ws/'template_studio').mkdir()
            data={'ws':ws,'job_id':'gdl_gc_new_0001','archive_sha256':'a'*64,
                  'record':{'native_jsx_sha256':'b'*64}}
            path=n.create_claim(data)
            self.assertTrue(path.is_file());self.assertIn('CLAIMED_SINGLE_USE',path.read_text())
            with self.assertRaisesRegex(n.Blocked,'SINGLE_USE_ALREADY_CLAIMED'):
                n.create_claim(data)
            n.store_claim_attempt(data,'p20261103123456-01234567')
            capture=io.StringIO()
            with patch('sys.stdout',capture):n.claim_status(data)
            self.assertEqual(json.loads(capture.getvalue())['attempt_id'],'p20261103123456-01234567')

    def test_claim_isolation_by_zip_and_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws=Path(tmp);(ws/'template_studio').mkdir()
            a={'ws':ws,'job_id':'gdl_gc_1','archive_sha256':'a'*64,'record':{'native_jsx_sha256':'b'*64}}
            b={**a,'job_id':'gdl_gc_2'}
            c={**a,'archive_sha256':'c'*64}
            self.assertEqual(len({n.claim_token(a),n.claim_token(b),n.claim_token(c)}),3)
            for d in (a,b,c):n.create_claim(d)

    def test_no_terminal_no_native(self):
        data={'job_id':'j','archive_sha256':'b'*64}
        with patch.object(sys.stdin,'isatty',return_value=False):
            with self.assertRaisesRegex(n.Blocked,'INTERACTIVE_OPERATOR_TTY_REQUIRED'):
                n.confirm_once(data)

    def test_confirmation_exact_token(self):
        data={'job_id':'gdl_gc_new_0001','archive_sha256':'b'*64}
        with patch.object(sys.stdin,'isatty',return_value=True),patch.object(sys.stdout,'isatty',return_value=True):
            with patch('builtins.input',return_value='wrong'):
                with self.assertRaisesRegex(n.Blocked,'DID_NOT_CONFIRM'):
                    n.confirm_once(data)
            with patch('builtins.input',return_value='LAB_NATIVE_ONCE gdl_gc_new_0001 bbbbbbbbbbbb'):
                n.confirm_once(data)

    def test_binding_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'assets').mkdir()
            attempt='p20261103123456-01234567';jid='gdl_gc_new_0001'
            work={'jsx':b'abc','manifest':b'{}','assets':{'asset.png':b'xxx'}}
            (base/'run_in_illustrator.jsx').write_bytes(work['jsx']);(base/'scene_manifest.json').write_bytes(work['manifest'])
            (base/'assets'/'asset.png').write_bytes(b'xxx')
            receipt={'schema_version':n.SCHEMA,'job_id':jid,'attempt_id':attempt,'archive_sha256':'a'*64,
                     'jsx_sha256':n.sha(b'abc'),'manifest_sha256':n.sha(b'{}'),'native_dispatch_count_max':1,
                     'automatic_retry':False,'visual_approved':False,'production_ready':False,
                     'independent_intake_review_attested':False}
            state={'native_jsx_sha256':n.sha(b'abc'),'accepted_zip_sha256':'a'*64}
            class S:
                def pilot_dir(self,*_):return base
                def native_run_dir(self,*_):return base
                def read_obj(self,p):
                    if p.name==n.BINDING:return receipt
                    return state
            d={'s':S(),'ws':base,'job_id':jid,'archive_sha256':'a'*64,
               'record':{'native_jsx_sha256':n.sha(b'abc'),'manifest_sha256':n.sha(b'{}')},
               'work':work}
            n.bind_attempt(d,attempt)
            (base/'assets'/'asset.png').write_bytes(b'changed')
            with self.assertRaisesRegex(n.Blocked,'NATIVE_ASSET_TAMPER'):
                n.bind_attempt(d,attempt)

    def test_source_has_no_parallel_renderer(self):
        src=SRC.read_text('utf8')
        self.assertNotIn('function greeting(font)',src)
        self.assertIn('capture_material=True',src)
        self.assertIn('t.make_transport(',src)
        self.assertIn('s.start_one(',src)
        self.assertNotIn('os.system(',src)

    def test_native_entrypoints(self):
        p=n.argparse.ArgumentParser()
        self.assertEqual(n.SCHEMA,'forprint_illustrator_studio_dynamic_native_lab_v1')
        self.assertTrue(n.ATTEMPT.fullmatch('p20261103123456-01234567'))
        self.assertFalse(bool(n.ATTEMPT.fullmatch('../wrong')))

    def test_capture_material_patch_preserves_shadow(self):
        shadow=SRC.with_name('illustrator_studio_intake_dynamic_preflight_v1.py')
        txt=shadow.read_text('utf8')
        self.assertIn('capture_material=False',txt)
        self.assertIn('if capture_material:',txt)
        self.assertIn('return report,',txt)
        self.assertIn('return report\n',txt)

    def test_stage_preparation_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);repo=home/'repo';renderer=repo/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_renderer_v1.jsx'
            renderer.parent.mkdir(parents=True);renderer.write_bytes(b'renderer')
            ws=home/'client';(ws/'template_studio'/'native_runs').mkdir(parents=True)
            (ws/'template_studio'/n.CLAIMS).mkdir()
            attempt='p20261103123456-01234567';jid='gdl_gc_new_0001'
            data={'job_id':jid,'archive_sha256':'a'*64,'record':{'native_jsx_sha256':n.sha(b'jsx')},
                  'ws':ws,'zip_name':'a.zip','archive':home/'a.zip','job':{'job_id':jid},
                  'work':{'jsx':b'jsx','manifest':json.dumps({'jsx_sha256':n.sha(b'jsx'), 'asset_sha256':{'one.png':n.sha(b'bytes')}}).encode(),'assets':{'one.png':b'bytes'}}}
            class GC29:
                def prepare(self,*args):raise Exception('legacy prepare must never run')
            gc29=GC29()
            class S:
                def native_run_dir(self,ws,jid,att):return ws/'template_studio'/'native_runs'/(jid+'__'+att)
                def pilot_dir(self,ws,jid,att):return ws/'template_studio'/('pilot_'+att)
                def current_passport(self):return {},{'schema_version':'fake'}
                def read_obj(self,p):return json.loads(p.read_text())
                def write_json_x(self,p,obj):
                    p.parent.mkdir(parents=True,exist_ok=True)
                    p.write_text(json.dumps(obj))
                def start_one(self,gc29,ws,job,archive,passport,selected):
                    gc29.prepare(ws,selected,attempt)
                    folder=self.pilot_dir(ws,selected,attempt);folder.mkdir()
                    (folder/'state.json').write_text(json.dumps({'native_jsx_sha256':n.sha(b'jsx'),'accepted_zip_sha256':'a'*64}))
                    return {'attempt':attempt,'state':'PREPARED_WINDOWS_EXECUTION_NOT_WIRED'}
            data['record']['manifest_sha256']=n.sha(data['work']['manifest'])
            data['s']=S();data['gc29']=gc29
            with patch.object(n,'ROOT',repo):
                got=n.staged_prepare(data)
            self.assertEqual(got,attempt)
            self.assertEqual((data['s'].native_run_dir(ws,jid,attempt)/'run_in_illustrator.jsx').read_bytes(),b'jsx')
            self.assertEqual((data['s'].pilot_dir(ws,jid,attempt)/n.BINDING).is_file(),True)
            self.assertTrue((ws/'template_studio'/n.CLAIMS/(n.claim_token(data)+'.attempt.json')).is_file())

if __name__=='__main__':unittest.main()
