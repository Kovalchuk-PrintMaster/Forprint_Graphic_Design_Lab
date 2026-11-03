#!/usr/bin/env python3
"""Offline safety contract tests; private sources only evaluated on s01."""
import importlib.util, io, json, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SRC=HERE.parent.parent/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_dynamic_preflight_v1.py'
if not SRC.is_file():
    SRC=Path(__file__).parents[3]/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_dynamic_preflight_v1.py'
spec=importlib.util.spec_from_file_location('dynamic',SRC)
dynamic=importlib.util.module_from_spec(spec);spec.loader.exec_module(dynamic)

class Safety(unittest.TestCase):
    def job(self):
        return {'job_id':'gdl_new_0001','structured_greeting_data':{'greeting_text':'A'*30},
                'signature_selection':{'variant_id':'GRIGO'},
                'builder_v1':{'front':{'family':'STANDARD','occasion':{'kind':'BIRTHDAY',
                    'display_text':'Привітання з нагоди Дня Народження!'}},
                'inside_image':{'mode':'DEFAULT_ASSET','asset_id':'flowers.default.v1',
                    'asset_sha256':'d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67'},
                'sender_text':{'signature_variant_id':'GRIGO','lines':[{'text':'Row'}]*3}}}
    def test_dynamic_job(self):
        self.assertEqual(dynamic.decide_job(self.job())['job_id'],'gdl_new_0001')
    def test_reject_signer_mismatch(self):
        j=self.job();j['signature_selection']['variant_id']='HERASYMENKO'
        with self.assertRaisesRegex(dynamic.Blocked,'SIGNATURE_SELECTION_CONFLICT'):dynamic.decide_job(j)
    def test_reject_unsupported_signer(self):
        j=self.job();j['builder_v1']['sender_text']['signature_variant_id']='DUAL_GRIGO_HERASYMENKO'
        with self.assertRaisesRegex(dynamic.Blocked,'SIGNATURE_NATIVE_UNSUPPORTED'):dynamic.decide_job(j)
    def test_reject_long_greeting(self):
        j=self.job();j['structured_greeting_data']['greeting_text']='A'*1101
        with self.assertRaisesRegex(dynamic.Blocked,'GREETING_EXCEEDS'):dynamic.decide_job(j)
    def test_reject_empty_greeting(self):
        j=self.job();j['structured_greeting_data']['greeting_text']=''
        with self.assertRaises(dynamic.Blocked):dynamic.decide_job(j)
    def test_reject_nonbirthday(self):
        j=self.job();j['builder_v1']['front']['occasion']['kind']='ANNIVERSARY'
        with self.assertRaisesRegex(dynamic.Blocked,'OCCASION_NOT_SUPPORTED'):dynamic.decide_job(j)
    def test_reject_changed_front(self):
        j=self.job();j['builder_v1']['front']['family']='BILINGUAL_OCCASION'
        with self.assertRaisesRegex(dynamic.Blocked,'FRONT_FAMILY_NOT_SUPPORTED'):dynamic.decide_job(j)
    def test_reject_other_title(self):
        j=self.job();j['builder_v1']['front']['occasion']['display_text']='Вітаємо!'
        with self.assertRaisesRegex(dynamic.Blocked,'OCCASION_TITLE_LAYOUT_UNSUPPORTED'):dynamic.decide_job(j)
    def test_reject_excess_sender_rows(self):
        j=self.job();j['builder_v1']['sender_text']['lines']=[{'text':'Row'}]*5
        with self.assertRaisesRegex(dynamic.Blocked,'SENDER_ROWS_UNSUPPORTED'):dynamic.decide_job(j)
    def test_reject_empty_sender_row(self):
        j=self.job();j['builder_v1']['sender_text']['lines'][0]={'text':' '}
        with self.assertRaisesRegex(dynamic.Blocked,'SENDER_LINE_INVALID'):dynamic.decide_job(j)
    def test_reject_unsupported_mode(self):
        j=self.job();j['builder_v1']['inside_image']['mode']='AUTO'
        with self.assertRaisesRegex(dynamic.Blocked,'P03_IMAGE_MODE_UNSUPPORTED'):dynamic.decide_job(j)
    def test_reject_path_job_id(self):
        j=self.job();j['job_id']='../../etc'
        with self.assertRaisesRegex(dynamic.Blocked,'JOB_ID_UNSAFE'):dynamic.decide_job(j)
    def test_valid_portrait_mode(self):
        j=self.job();j['builder_v1']['inside_image']['mode']='PORTRAIT'
        self.assertEqual(dynamic.decide_job(j)['image_mode'],'PORTRAIT')
    def test_asset_hash(self):
        payload=b'\x89PNG\r\n\x1a\n'+b'data'
        with tempfile.TemporaryFile() as fh:
            with zipfile.ZipFile(fh,'w') as z:z.writestr('assets/x.png',payload)
            fh.seek(0)
            with zipfile.ZipFile(fh) as z:
                doc={'ref':{'sha256':dynamic.sha(payload),'path':'assets/x.png'}}
                self.assertEqual(dynamic.read_verified_asset(z,doc,'ref',dynamic.sha(payload)),payload)
    def test_asset_mismatch(self):
        with tempfile.TemporaryFile() as fh:
            with zipfile.ZipFile(fh,'w') as z:z.writestr('assets/x.png',b'wrong')
            fh.seek(0)
            with zipfile.ZipFile(fh) as z:
                with self.assertRaises(dynamic.Blocked):dynamic.read_verified_asset(z,{'ref':{'sha256':'0'*64,'path':'assets/x.png'}},'ref','0'*64)
    def test_portrait_proof_rgba(self):
        from PIL import Image,ImageDraw
        im=Image.new('RGBA',(200,240),(0,0,0,0));d=ImageDraw.Draw(im);d.rectangle((40,40,160,180),fill=(200,100,100,255))
        b=io.BytesIO();im.save(b,'PNG')
        self.assertTrue(dynamic.portrait_proof(b.getvalue())['alpha_present'])
    def test_portrait_reject_opaque(self):
        from PIL import Image
        im=Image.new('RGBA',(200,240),(200,200,200,255));b=io.BytesIO();im.save(b,'PNG')
        with self.assertRaisesRegex(dynamic.Blocked,'PORTRAIT_ALPHA_NOT_MEANINGFUL'):dynamic.portrait_proof(b.getvalue())
    def test_portrait_reject_jpg(self):
        from PIL import Image
        im=Image.new('RGB',(200,240));b=io.BytesIO();im.save(b,'JPEG')
        with self.assertRaisesRegex(dynamic.Blocked,'PORTRAIT_MUST_BE_RGBA_PNG'):dynamic.portrait_proof(b.getvalue())
    def test_selected_input_path_guard(self):
        class Audit:
            def client_input_dir(self,client):return Path('/tmp/nothing')
        with self.assertRaisesRegex(dynamic.Blocked,'SELECTED_ZIP_FILENAME_INVALID'):
            dynamic.input_archive(Audit(),'abc','../evil.zip')
    def test_filename_reject_absolute(self):
        self.assertIsNone(dynamic.SAFE_PACKAGE.fullmatch('/abs.zip'))
    def test_no_native_import(self):
        source=SRC.read_text('utf8')
        self.assertNotIn('controller_command(',source)
        self.assertNotIn('stage_remote(',source)
        self.assertNotIn('start_one(',source)
        self.assertIn("'native_dispatch':False",source)
        self.assertNotIn('os.system(',source)
    def test_no_tmp_runtime(self):
        source=SRC.read_text('utf8')
        self.assertIn('TemporaryDirectory(',source)
        self.assertIn("ROOT / 'tmp'",source)
        self.assertNotIn('tmp/illustrator_studio',source)
    def test_scene_shadow_does_not_infer_operator_review(self):
        self.assertIn("'review_independent_attestation':'NOT_ESTABLISHED'",SRC.read_text('utf8'))

if __name__=='__main__':unittest.main()
