from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import zipfile

SOURCE=Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/greeting_cards/gc30_sftp_payload_r002.py'
spec=importlib.util.spec_from_file_location('gc30r002',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture(tmp):
 root=tmp/'project'; root.mkdir();(root/'tmp').mkdir()
 for p,h in m.SOURCE_GUARDS.items():
  q=root/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b'fixture_source')
 # local-only fake source, explicit test-only guards
 m.SOURCE_GUARDS={p:hashlib.sha256(b'fixture_source').hexdigest() for p in m.SOURCE_GUARDS}
 share=tmp/'share';share.mkdir()
 client='Test Client'
 ws=share/client/'_forprint_automation';ws.mkdir(parents=True)
 (ws/'input').mkdir()
 bio=io.BytesIO()
 with zipfile.ZipFile(bio,'w') as z:
  for n in ('accepted_constructor_bundle.yaml','artifact_manifest.yaml','handoff_manifest.json'):z.writestr(n,'test')
 accepted=bio.getvalue();(ws/'input'/'accepted.zip').write_bytes(accepted)
 run=ws/'template_studio'/'native_runs'/m.PILOT; (run/'assets').mkdir(parents=True)
 files={f'p01_image{i:02}.png':b'png'+bytes([i]) for i in range(12)}
 for n,b in files.items(): (run/'assets'/n).write_bytes(b)
 jsx=b'// JSX pilot candidate';(run/'run_in_illustrator.jsx').write_bytes(jsx)
 scene={'schema_version':m.SCENE_SCHEMA,'pages':4,'production_ready':False,'job_id':m.JOB,'accepted_zip_sha256':m.digest(accepted),'jsx_sha256':m.digest(jsx),'asset_sha256':{n:m.digest(b) for n,b in files.items()}}
 scene_b=json.dumps(scene).encode();(run/'scene_manifest.json').write_bytes(scene_b)
 q=ws/'template_studio'/'dispatch'/'queued';q.mkdir(parents=True)
 t={'schema_version':m.TICKET_SCHEMA,'ticket_id':m.PILOT,'job_id':m.JOB,'worker_id':m.WORKER,'worker_machine':'PREPRESS','worker_user':'Work','client_folder':client,'status':'QUEUED','review_only':True,'production_ready':False,'run_relative':'template_studio/native_runs/'+m.PILOT,'accepted_zip_sha256':m.digest(accepted),'scene_manifest_sha256':m.digest(scene_b),'jsx_sha256':m.digest(jsx),'asset_sha256':scene['asset_sha256']}
 (q/(m.PILOT+'.json')).write_text(json.dumps(t))
 return root,share,client,q,run

def test_check_read_only(tmp_path,capsys):
 root,share,client,q,run=fixture(tmp_path)
 assert m.run(client,'check',False,root=root,share=share) is None
 assert 'PACKAGE=NOT_EXECUTED' in capsys.readouterr().out
 assert list((root/'tmp').iterdir())==[]

def test_package_exact_members_and_hashes(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 f=m.run(client,'package',True,root=root,share=share,out_dir=root/'tmp'/'pilot_r002')
 assert f.is_file()
 with zipfile.ZipFile(f) as z:
  assert len(z.namelist())==16
  meta=json.loads(z.read('offline_payload_manifest.json'))
  assert meta['target_subtree']=='jobs/'+m.PILOT
  assert meta['production_ready'] is False
  assert meta['config_policy']=='DO_NOT_TOUCH_EXISTING_CONFIG_OR_GC32'
  for n,h in meta['source_file_sha256'].items():assert m.digest(z.read(n))==h

def test_reject_queue_two(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 (q/'other.json').write_text('{}')
 try:m.run(client,'check',False,root=root,share=share)
 except m.Blocked as e:assert str(e)=='GC30_R002_QUEUE_NOT_EXACT_ONE'
 else:assert False

def test_reject_tampered_asset(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 (run/'assets'/'p01_image00.png').write_bytes(b'WRONG')
 try:m.run(client,'check',False,root=root,share=share)
 except m.Blocked as e:assert str(e).startswith('GC30_R002_ASSET_HASH_DRIFT')
 else:assert False

def test_reject_wrong_machine(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 f=q/(m.PILOT+'.json');t=json.loads(f.read_text());t['worker_machine']='OTHER';f.write_text(json.dumps(t))
 try:m.run(client,'check',False,root=root,share=share)
 except m.Blocked as e:assert str(e)=='GC30_R002_WORKER_BINDING_DRIFT'
 else:assert False

def test_reject_existing_bundle(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 out=root/'tmp'/'pilot_r002';out.mkdir()
 try:m.run(client,'package',True,root=root,share=share,out_dir=out)
 except m.Blocked as e:assert str(e)=='GC30_R002_OUTPUT_ALREADY_EXISTS'
 else:assert False

def test_reject_false_production(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 f=q/(m.PILOT+'.json');t=json.loads(f.read_text());t['production_ready']=True;f.write_text(json.dumps(t))
 try:m.run(client,'check',False,root=root,share=share)
 except m.Blocked as e:assert str(e)=='GC30_R002_AUTHORITY_DRIFT'
 else:assert False

def test_reject_confirm_mismatch(tmp_path):
 root,share,client,q,run=fixture(tmp_path)
 try:m.run(client,'check',True,root=root,share=share)
 except m.Blocked as e:assert str(e)=='GC30_R002_CONFIRMATION_MISMATCH'
 else:assert False
