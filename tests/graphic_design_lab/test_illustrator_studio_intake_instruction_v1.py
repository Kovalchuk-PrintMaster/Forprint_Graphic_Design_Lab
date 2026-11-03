#!/usr/bin/env python3
"""Phase 2A regression: deterministic versioned Intake instructions, no native side effects."""
from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

REPO=Path(__file__).resolve().parents[2]
SCRIPT=REPO/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_intake_instruction_v1.py'
SPEC=importlib.util.spec_from_file_location('studio_intake_generator',SCRIPT)
mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)
BASE=REPO/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'

class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.tmp=Path(self.t.name);self.repo=self.tmp/'repo';self.share=self.tmp/'share'
        dst=self.repo/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'
        shutil.copytree(BASE,dst)
        self.share.mkdir()
        self.client='Тестовий клієнт'
        (self.share/self.client/'_forprint_automation').mkdir(parents=True)
    def test_catalog_and_one_active_recipe(self):
        rows=mod.load_catalog(self.repo)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'ACTIVE')
        self.assertEqual(len(rows[0]['content']),13)
    def test_deterministic_zip_and_release(self):
        rows=mod.load_catalog(self.repo);a,f=mod.render(self.repo,rows[0]);b,g=mod.render(self.repo,rows[0]);self.assertEqual(a,b);self.assertEqual(f,g)
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            self.assertIsNone(z.testzip())
            names=set(z.namelist())
            self.assertIn('INTAKE_OPERATOR_PROMPT_UA_v1.md',names)
            self.assertIn('reference_contracts/normalized_batch_contract_v0_1.yaml',names)
            rel=json.loads(z.read('RELEASE_INFO.json'))
            self.assertEqual(rel['source_fingerprint_sha256'],f)
            self.assertFalse(rel['native_dispatch'])
            self.assertFalse(rel['production_ready'])
            for n,digest in rel['content_sha256'].items():self.assertEqual(mod.sha(z.read(n)),digest)
    def test_generate_reuse_and_private_storage(self):
        with redirect_stdout(io.StringIO()):
            a=mod.generate(self.repo,self.share,self.client)
            b=mod.generate(self.repo,self.share,self.client)
        self.assertEqual(a,b);self.assertTrue(a.exists())
        self.assertEqual(a.parent.name,'intake_instruction')
        self.assertEqual(len(list(a.parent.glob('*.zip'))),1)
        self.assertEqual(mod.verify_client(self.repo,self.share,self.client),0)
    def test_tampered_stored_package_blocked(self):
        with redirect_stdout(io.StringIO()): p=mod.generate(self.repo,self.share,self.client)
        p.write_bytes(b'broken')
        with self.assertRaisesRegex(mod.Blocked,'EXISTING_PACKAGE_CONFLICT_OR_TAMPER'):
            mod.generate(self.repo,self.share,self.client)
    def test_source_drift_requires_new_catalog_version(self):
        src=self.repo/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake/00_START_HERE_UA.md'
        src.write_text(src.read_text('utf8')+'altered','utf8')
        with self.assertRaisesRegex(mod.Blocked,'CANONICAL_SOURCE_DRIFT_VERSION_BUMP_REQUIRED'):
            mod.load_catalog(self.repo)
    def test_use_existing_folder_with_spaces(self):
        base=self.share/self.client/'_forprint_automation'
        (base/'Intake Instruction').mkdir()
        with redirect_stdout(io.StringIO()):path=mod.generate(self.repo,self.share,self.client)
        self.assertEqual(path.parent.name,'Intake Instruction')
        self.assertFalse((base/'intake_instruction').exists())
    def test_use_existing_folder_in_client_root(self):
        direct=self.share/self.client/'Intake Instruction'
        direct.mkdir()
        with redirect_stdout(io.StringIO()):path=mod.generate(self.repo,self.share,self.client)
        self.assertEqual(path.parent,direct)
        self.assertFalse((self.share/self.client/'_forprint_automation'/'intake_instruction').exists())
    def test_duplicate_instruction_folders_blocked(self):
        base=self.share/self.client/'_forprint_automation'
        (base/'Intake Instruction').mkdir();(base/'intake_instruction').mkdir()
        with self.assertRaisesRegex(mod.Blocked,'MULTIPLE_INTAKE'):
            mod.generate(self.repo,self.share,self.client)
    def test_symlink_instruction_folder_blocked(self):
        base=self.share/self.client/'_forprint_automation'
        (base/'intake_instruction').symlink_to(self.tmp,target_is_directory=True)
        with self.assertRaisesRegex(mod.Blocked,'INSTRUCTION_DIR_SYMLINK'):
            mod.generate(self.repo,self.share,self.client)
    def test_client_traversal_rejected(self):
        for client in ('../hi','hi/there','hi\\there','', '.', '..'):
            self.assertFalse(mod.valid_client(client))
    def test_explicit_version_and_unknown_version(self):
        rows=mod.load_catalog(self.repo)
        self.assertEqual(mod.choose_recipe(rows,'greeting_card@1.0.0')['version'],'1.0.0')
        with self.assertRaisesRegex(mod.Blocked,'RECIPE_NOT_FOUND'):mod.choose_recipe(rows,'greeting_card@9.9.9')
    def test_path_traversal_catalog_rejected(self):
        path=self.repo/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake/intake_instruction_catalog_v1.json'
        d=json.loads(path.read_text('utf8'));d['recipes'][0]['content'][0]['source']='../source'
        path.write_text(json.dumps(d),'utf8')
        with self.assertRaisesRegex(mod.Blocked,'RECIPE_PATH_UNSAFE'):mod.load_catalog(self.repo)
    def test_no_other_client_touch(self):
        other=self.share/'Other'/'_forprint_automation';other.mkdir(parents=True)
        with redirect_stdout(io.StringIO()):mod.generate(self.repo,self.share,self.client)
        self.assertEqual(list(other.iterdir()),[])

if __name__=='__main__':unittest.main()
