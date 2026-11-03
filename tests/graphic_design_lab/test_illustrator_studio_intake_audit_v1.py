import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import hashlib

D=Path(__file__).resolve().parents[2]
P=D/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_audit_v1.py'
spec=importlib.util.spec_from_file_location('studio_intake_audit_v1',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
 def test_client_path_guard(self):
  with self.assertRaisesRegex(m.Invalid,'CLIENT_NAME_INVALID'):m.client_input_dir('../unsafe')
 def test_safe_name(self):
  self.assertFalse(m.safe_name('../secret'))
  self.assertFalse(m.safe_name('C:/windows'))
  self.assertFalse(m.safe_name('x\\foo'))
  self.assertTrue(m.safe_name('assets/file.png'))
 def test_unknown_zip_not_handoff(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'unknown.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('a.txt','b')
   self.assertEqual(m.audit(p)['status'],'RAW_OR_UNKNOWN_INTAKE_ONLY')
 def test_staging_classified(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'staging.zip'
   with zipfile.ZipFile(p,'w') as z:z.writestr('BLOCKERS.yaml','blockers:\n- code: BLOCKER\n')
   self.assertEqual(m.audit(p)['blockers'],['BLOCKER'])
 def test_invalid_bundle_sha_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.zip'
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('accepted_constructor_bundle.yaml','a: b\n')
    z.writestr('artifact_manifest.yaml','a: b\n')
    z.writestr('handoff_manifest.json',json.dumps({'schema_version':'gdl_intake_builder_handoff_v0_1','mode':'REVIEW_ONLY','accepted_bundle_file_sha256':'0'*64,'artifact_manifest_file_sha256':'0'*64}))
   with self.assertRaisesRegex(m.Invalid,'BUNDLE_FILE_SHA_MISMATCH'):m.audit(p)
 def test_no_native_code(self):
  s=P.read_text()
  for forbidden in ('subprocess','Start-Process','DoJavaScript','os.system','make gdl-studio-launch'):
   self.assertNotIn(forbidden,s)
 def test_contract_and_prompt(self):
  b=D/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'
  p=json.loads((b/'intake_interface_contract_v1.json').read_text())
  self.assertEqual(p['studio_runtime_bridge']['phase_2_status'],'NOT_IMPLEMENTED')
  self.assertFalse(p['governance']['native_dispatch_phase_1'])
  self.assertIn('CREATOR_HANDOFF_READY',(b/'INTAKE_OPERATOR_PROMPT_UA_v1.md').read_text())

if __name__=='__main__':unittest.main(verbosity=2)
