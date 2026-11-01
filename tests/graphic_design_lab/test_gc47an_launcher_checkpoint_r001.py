#!/usr/bin/env python3
"""GC47AN offline acceptance, safe-git and negative tests; no live SMB/SSH/renderer."""
from __future__ import annotations
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
from io import StringIO
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[2]
SRC=HERE/'scripts/graphic_design_lab/greeting_cards/gc47an_launcher_checkpoint_r001.py'
s=importlib.util.spec_from_file_location('gc47an_under_test',SRC)
an=importlib.util.module_from_spec(s);s.loader.exec_module(an)

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
 def test_01_pins_twelve_previously_verified_files(self):
  self.assertEqual(len(an.LOCKED),12)
  self.assertEqual(len(set(an.LOCKED)),12)
  self.assertTrue(all(len(v)==64 for v in an.LOCKED.values()))
 def test_02_no_mutations_in_audit(self):
  text=SRC.read_text('utf-8')
  self.assertNotIn('shell=True',text)
  self.assertNotIn('shutil.rmtree',text)
  self.assertNotIn('os.chmod(',text)
  self.assertIn('--confirm-commit',text)
 def test_03_exclusive_make_tail(self):
  b='base\n'+''.join(an.FRAGMENTS)
  self.assertTrue(b.endswith(''.join(an.FRAGMENTS)))
  self.assertEqual([b.count(f) for f in an.FRAGMENTS],[1,1,1])
 def test_04_overlay_preserves_existing_index(self):
  original='existing make code\n'
  result=an.make_index_overlay(original)
  self.assertTrue(result.startswith(original))
  self.assertEqual(result,original+''.join(an.FRAGMENTS))
 def test_05_overlay_adds_only_missing_suffix(self):
  initial='original'+an.AI_FRAGMENT
  self.assertEqual(an.make_index_overlay(initial),initial+an.AJ_FRAGMENT+an.AN_FRAGMENT)
 def test_06_overlay_rejects_out_of_order(self):
  with self.assertRaises(an.Blocked):an.make_index_overlay('base'+an.AJ_FRAGMENT)
 def test_07_overlay_rejects_duplicates(self):
  with self.assertRaises(an.Blocked):an.make_index_overlay(an.AI_FRAGMENT*2)
 def test_08_parse_sums_accepts_two_space_format(self):
  d=an.parse_sums('a'*64+'  review.pdf\n')
  self.assertEqual(d,{'review.pdf':'a'*64})
 def test_09_parse_sums_accepts_binary_marker(self):
  self.assertEqual(an.parse_sums('a'*64+' *design.ai\n')['design.ai'],'a'*64)
 def test_10_parse_sums_blocks_parent(self):
  with self.assertRaises(an.Blocked):an.parse_sums('a'*64+'  ../outside\n')
 def test_11_parse_sums_blocks_duplicate(self):
  with self.assertRaises(an.Blocked):an.parse_sums(('a'*64+'  x\n')*2)
 def test_12_parse_sums_blocks_drive(self):
  with self.assertRaises(an.Blocked):an.parse_sums('a'*64+'  sub\\f\n')
 def test_13_parse_sums_blocks_bad_digest(self):
  with self.assertRaises(an.Blocked):an.parse_sums('broken  a.txt\n')
 def prepare_review(self):
  ws=self.root/'_forprint_automation';p=ws/'output/greeting_card_pilots'/"gdl_gc_test_20261101"/"p20261101164831-aa44279c"
  p.mkdir(parents=True)
  lines=[]
  for name in an.ARTIFACTS:
   if name=='SHA256SUMS':continue
   data=b'{}' if name=='passport_snapshot.json' else ('test:'+name).encode()
   (p/name).write_bytes(data)
   lines.append(hashlib.sha256(data).hexdigest()+'  '+name)
  (p/'SHA256SUMS').write_text('\n'.join(lines)+'\n','utf-8')
  return ws,p
 def test_14_complete_fixture_artifacts(self):
  ws,p=self.prepare_review();base,n=an.verify_review(ws,'gdl_gc_test_20261101','p20261101164831-aa44279c')
  self.assertEqual(base,p);self.assertEqual(n,7)
 def test_15_tamper_artifact_blocked(self):
  ws,p=self.prepare_review();(p/'review.pdf').write_text('tampered')
  with self.assertRaisesRegex(an.Blocked,'REVIEW_SHA256_INVALID'):an.verify_review(ws,'gdl_gc_test_20261101','p20261101164831-aa44279c')
 def test_16_missing_artifact_blocked(self):
  ws,p=self.prepare_review();(p/'design.ai').unlink()
  with self.assertRaisesRegex(an.Blocked,'REVIEW_ARTIFACT_MISSING'):an.verify_review(ws,'gdl_gc_test_20261101','p20261101164831-aa44279c')
 def test_17_symlink_artifact_blocked(self):
  ws,p=self.prepare_review();(p/'design.ai').unlink();(p/'design.ai').symlink_to(p/'review.pdf')
  with self.assertRaisesRegex(an.Blocked,'REVIEW_ARTIFACT_MISSING'):an.verify_review(ws,'gdl_gc_test_20261101','p20261101164831-aa44279c')
 def test_18_bad_passport_blocked(self):
  ws,p=self.prepare_review();(p/'passport_snapshot.json').write_text('not-json')
  with self.assertRaises((ValueError,an.Blocked)):an.verify_review(ws,'gdl_gc_test_20261101','p20261101164831-aa44279c')
 def test_19_invalid_job_attempt_blocked(self):
  ws,p=self.prepare_review()
  with self.assertRaisesRegex(an.Blocked,'JOB_ID_INVALID'):an.verify_review(ws,'../bad','p20261101164831-aa44279c')
 def test_20_read_only_git_plan_blocks_foreign_stage(self):
  repo=self.git_repo()
  (repo/'other.txt').write_text('modified');an.git(repo,'add','other.txt')
  with self.assertRaisesRegex(an.Blocked,'PREEXISTING_STAGED_CHANGES'):an.git_plan(repo)
 def test_21_git_plan_does_not_stage(self):
  repo=self.git_repo()
  before=an.git(repo,'diff','--cached','--name-only').stdout
  files,new,old=an.git_plan(repo)
  self.assertEqual(len(files),14)
  self.assertEqual(before,an.git(repo,'diff','--cached','--name-only').stdout)
 def test_22_commit_stages_only_scoped_paths(self):
  repo=self.git_repo()
  with patch.object(an,'verify_sources',return_value=14):
   with redirect_stdout(StringIO()):an.do_commit(repo)
  staged=an.git(repo,'show','--pretty=format:','--name-only','HEAD').stdout.decode().splitlines()
  self.assertEqual(set(staged),set(an.LOCKED)|{an.GC47AN_SELF,an.GC47AN_TEST,'Makefile'})
  # The index-only Makefile patch did not capture pre-existing worktree edits.
  base=an.git(repo,'show','HEAD:Makefile').stdout.decode()
  self.assertNotIn('unrelated operator change',base)
  self.assertIn('unrelated operator change',(repo/'Makefile').read_text())
  self.assertIn('Makefile',an.git(repo,'diff','--name-only').stdout.decode())
 def test_23_foreign_commit_not_pushed(self):
  repo=self.git_repo()
  with patch.object(an,'verify_sources',return_value=14):
   with redirect_stdout(StringIO()) as buf:an.do_commit(repo,push=False)
  self.assertIn('GC47AN_PUSH=NOT_REQUESTED',buf.getvalue())
 def test_24_missing_client_boundary(self):
  with self.assertRaises(an.Blocked):an.client_path('../x',self.root)
 def test_25_symlink_client_boundary(self):
  share=self.root/'share';share.mkdir();(share/'client').symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(an.Blocked):an.client_path('client',share)
 def test_26_cli_disallows_commit_without_approval(self):
  # Explicit option is mandatory even before Git operation is reached.
  with patch.object(an,'verify_sources',return_value=14),patch.object(an,'client_path',return_value=self.root),patch.object(an,'verify_client'),patch.object(an,'verify_review',return_value=(self.root,7)),patch.object(an,'git_plan',return_value=([], '', '')):
   with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
    self.assertEqual(an.main(['--mode','commit','--client-name','Test','--job','gdl_gc_test_20261101','--attempt','p20261101164831-aa44279c']),2)
 def git_repo(self):
  repo=self.root/'forprint_graphic_design_lab';repo.mkdir()
  def run(*args):
   subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
  run('init','-b','main')
  run('config','user.name','GC47AN Test')
  run('config','user.email','gc47an@example.invalid')
  (repo/'Makefile').write_text('base make\n')
  (repo/'other.txt').write_text('baseline')
  run('add','Makefile','other.txt')
  run('commit','-m','baseline')
  (repo/'Makefile').write_text('base make\nunrelated operator change\n'+''.join(an.FRAGMENTS))
  for name in tuple(an.LOCKED)+(an.GC47AN_SELF,an.GC47AN_TEST):
   p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('stub')
  return repo

if __name__=='__main__':unittest.main(verbosity=2)
