#!/usr/bin/env python3
"""Offline progress/attestation tests. Never starts Windows or Illustrator."""
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]/'scripts/graphic_design_lab/greeting_cards'

def load(filename,name):
    spec=importlib.util.spec_from_file_location(name,SRC/filename)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
p=load('illustrator_studio_progress_v1.py','studio_progress_unit')
n=load('illustrator_studio_intake_dynamic_native_v1.py','studio_native_progress_unit')

class FakeS:
    REQUIRED_NATIVE=('design.ai','review.pdf','preview_p01.png','result.json')
    def __init__(self,root):self.root=root
    def review_dir(self,ws,jid,attempt):return self.root/'output'/jid/attempt
    def pilot_dir(self,ws,jid,attempt):return self.root/'runs'/jid/attempt
    def verify_native(self,folder,state):
        return {name:p.filehash(folder/name) for name in self.REQUIRED_NATIVE}

class ProgressTests(unittest.TestCase):
    JOB='gdl_gc_new_20261103';ATT='p20261103123456-01234567';ZIP='a'*64
    def setup_review(self,root):
        s=FakeS(root)
        folder=s.review_dir(root,self.JOB,self.ATT);folder.mkdir(parents=True)
        statepath=s.pilot_dir(root,self.JOB,self.ATT)/'state.json';statepath.parent.mkdir(parents=True)
        state={'job_id':self.JOB,'attempt_id':self.ATT,'native_jsx_sha256':'b'*64}
        statepath.write_text(json.dumps(state))
        hashes={}
        for name in s.REQUIRED_NATIVE:
            f=folder/name;f.write_bytes(('valid:'+name).encode());hashes[name]=p.filehash(f)
        v={'job_id':self.JOB,'attempt_id':self.ATT,'source_jsx_sha256':'b'*64,'files_sha256':hashes,
           'visual_approved':False,'production_ready':False}
        (folder/'verify.json').write_text(json.dumps(v))
        return s,folder
    def test_not_published_no_fake_ready(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(p.published_review_state(FakeS(Path(td)),Path(td),self.JOB,self.ATT)['status'],'NOT_PUBLISHED')
    def test_valid_attested_review_only(self):
        with tempfile.TemporaryDirectory() as td:
            s,folder=self.setup_review(Path(td))
            result=p.published_review_state(s,Path(td),self.JOB,self.ATT)
            self.assertEqual(result['status'],p.READY)
            self.assertEqual(result['files_verified'],4)
            self.assertIn('output/',result['review_relative'])
    def test_tampering_blocks_green(self):
        with tempfile.TemporaryDirectory() as td:
            s,folder=self.setup_review(Path(td))
            (folder/'design.ai').write_bytes(b'tampered')
            self.assertEqual(p.published_review_state(s,Path(td),self.JOB,self.ATT)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_missing_artifact_blocks_green(self):
        with tempfile.TemporaryDirectory() as td:
            s,folder=self.setup_review(Path(td))
            (folder/'review.pdf').unlink()
            self.assertEqual(p.published_review_state(s,Path(td),self.JOB,self.ATT)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_source_drift_blocks_green(self):
        with tempfile.TemporaryDirectory() as td:
            s,folder=self.setup_review(Path(td))
            v=json.loads((folder/'verify.json').read_text());v['source_jsx_sha256']='c'*64
            (folder/'verify.json').write_text(json.dumps(v))
            self.assertEqual(p.published_review_state(s,Path(td),self.JOB,self.ATT)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_review_parent_symlink_cannot_mark_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s,folder=self.setup_review(root)
            real=folder.parent
            moved=root/'outside';real.rename(moved)
            real.symlink_to(moved, target_is_directory=True)
            self.assertEqual(p.published_review_state(s,root,self.JOB,self.ATT)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_archive_lineage_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);s,folder=self.setup_review(root)
            self.assertEqual(p.published_review_state(s,root,self.JOB,self.ATT,'a'*64)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_no_visual_approval_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            s,folder=self.setup_review(Path(td))
            v=json.loads((folder/'verify.json').read_text());v['visual_approved']=True
            (folder/'verify.json').write_text(json.dumps(v))
            self.assertEqual(p.published_review_state(s,Path(td),self.JOB,self.ATT)['status'],'REVIEW_VERIFICATION_BLOCKED')
    def test_claim_safely_counts_pending_and_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ws=root/'client';(ws/'template_studio').mkdir(parents=True)
            start=p.attempt_from_claim(ws,self.ZIP,self.JOB)
            self.assertEqual(start['status'],'NOT_STARTED')
            self.assertFalse((ws/'template_studio'/'studio_intake_dynamic_native_claims_v1').exists())
            claims=ws/'template_studio'/'studio_intake_dynamic_native_claims_v1';claims.mkdir()
            key=hashlib.sha256((self.ZIP+'\n'+self.JOB).encode()).hexdigest()
            (claims/(key+'.json')).write_text(json.dumps({'state':'CLAIMED_SINGLE_USE','job_id':self.JOB,'archive_sha256':self.ZIP}))
            self.assertEqual(p.attempt_from_claim(ws,self.ZIP,self.JOB)['status'],'CLAIMED_NO_ATTEMPT')
            (claims/(key+'.attempt.json')).write_text(json.dumps({'job_id':self.JOB,'archive_sha256':self.ZIP,'attempt_id':self.ATT}))
            self.assertEqual(p.attempt_from_claim(ws,self.ZIP,self.JOB)['attempt_id'],self.ATT)
    def test_claim_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            ws=Path(td);(ws/'template_studio').mkdir()
            claims=ws/'template_studio'/'studio_intake_dynamic_native_claims_v1';claims.mkdir()
            key=hashlib.sha256((self.ZIP+'\n'+self.JOB).encode()).hexdigest()
            (claims/(key+'.json')).symlink_to('/etc/passwd')
            self.assertEqual(p.attempt_from_claim(ws,self.ZIP,self.JOB)['status'],'CLAIM_UNSAFE')
    def test_plain_and_colored_terminal(self):
        stream=io.StringIO()
        c=p.ConsoleProgress(self.JOB,'test.zip',stream=stream)
        c.milestone('INPUT');c.heartbeat(12,'NOT_RECORDED');c.warning('Review needed');c.ready('output/test')
        self.assertNotIn('\x1b[',stream.getvalue());self.assertIn('ГОТОВО ДО ВІЗУАЛЬНОЇ ПЕРЕВІРКИ',stream.getvalue())
        class TTY(io.StringIO):
            def isatty(self):return True
        colored=TTY()
        with patch.dict(os.environ,{'NO_COLOR':''}):
            p.ConsoleProgress(self.JOB,'test.zip',stream=colored).milestone('INPUT')
        self.assertIn('\x1b[32m',colored.getvalue())
    def test_batch_counter_counts_only_verified_ready(self):
        stream=io.StringIO();c=p.ConsoleProgress('BATCH','accepted.zip',stream=stream)
        c.batch([{'job_id':'a','status':p.READY},{'job_id':'b','status':'CLAIMED_NO_ATTEMPT'},
                 {'job_id':'c','status':'REVIEW_VERIFICATION_BLOCKED'}])
        self.assertIn('1 З 3',stream.getvalue())
    def test_read_only_batch_status_no_native_calls(self):
        with tempfile.TemporaryDirectory() as td:
            ws=Path(td);(ws/'template_studio').mkdir()
            archive=ws/'test.zip'
            import zipfile
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('accepted_constructor_bundle.yaml','any')
            class Audit:
                def audit(self,archive):return {'status':'HANDOFF_STRUCTURAL_PASS_STUDIO_BINDING_REQUIRED'}
                def load_yaml(self,_):return {'jobs':[{'job_id':selfjob} for selfjob in ['gdl_gc_001','gdl_gc_002']]}
            class Shadow:
                AUDIT=Path('audit')
                GC47S=Path('s')
                def load_py(self,path,name):return Audit() if str(path)=='audit' else S()
                def input_archive(self,audit,client,zip_name):return archive
            class S:
                ID_RE=__import__('re').compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
                def workspace(self,client):return ws
            t=object();fake=(Shadow(),object(),t)
            stream=io.StringIO()
            with patch.object(n,'load_sources',return_value=fake),patch('sys.stdout',stream):
                self.assertEqual(n.batch_status('client','test.zip'),0)
            self.assertIn('0 З 2',stream.getvalue())
            self.assertIn('"automatic_queue": false',stream.getvalue())
            self.assertFalse((ws/'template_studio'/'studio_intake_dynamic_native_claims_v1').exists())
    def test_no_second_renderer_or_auto_retry(self):
        code=(SRC/'illustrator_studio_intake_dynamic_native_v1.py').read_text()
        self.assertNotIn('function greeting(font)',code)
        self.assertIn('with bc.Exclusive()',code)
        self.assertIn('single_use',code.lower())
        self.assertIn("'batch-status'",code)
        self.assertIn('published_review_state',code)

if __name__=='__main__':unittest.main()
