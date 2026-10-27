#!/usr/bin/env python3
"""GC30 r002 Phase A: build audited SINGLE-ticket offline transfer bundle on s01.

No network calls, no Windows access, no SMB mutation, no Illustrator. Must not be
mistaken for staging/execution. Use phase B SFTP handoff only after operator review.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
SHARE=Path('/srv/smb/In_Progress/data')
PILOT='gdl_gc_deg_20261011__34b9b61741d5ca'
JOB='gdl_gc_deg_20261011'
WORKER='illustrator-primary'
D_ROOT=r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
TICKET_SCHEMA='forprint_gdl_gc30_dispatch_ticket_v0_1'
SCENE_SCHEMA='gdl_gc29_native_scene_v0_1'
SOURCE_GUARDS={
 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py':'c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42',
 'scripts/graphic_design_lab/greeting_cards/gc30_dedicated_dispatch_v0_1.py':'78227599af7c61c2f43576afe86da0e1dfb0defb0cc49916759c821d342b068f',
}
NAME=re.compile(r'^p\d\d_[a-z0-9_]+\.(?:png|svg|eps)$')
SHA=re.compile(r'^[a-f0-9]{64}$')
class Blocked(ValueError):pass
def need(v,code):
 if not v:raise Blocked(code)
def regular(p):
 try:return stat.S_ISREG(p.lstat().st_mode)
 except FileNotFoundError:return False
def folder(p):
 try:return stat.S_ISDIR(p.lstat().st_mode)
 except FileNotFoundError:return False
def digest(data):return sha256(data).hexdigest()
def check_parts(path,top):
 # The top level is pre-trusted by the operator; all descendants must be real.
 need(folder(top),'GC30_R002_TOP_DIR_UNSAFE')
 cur=top
 for name in path.relative_to(top).parts:
  cur=cur/name
  need(folder(cur) if cur!=path else (regular(cur) or folder(cur)), 'GC30_R002_UNSAFE_PATH_COMPONENT')

def source(client,*,root=ROOT,share=SHARE):
 need(isinstance(client,str) and bool(client) and client not in ('.','..') and not any(c in client for c in '/\\\x00'),'GC30_R002_CLIENT_INVALID')
 for name,want in SOURCE_GUARDS.items():
  p=root/name
  need(regular(p) and digest(p.read_bytes())==want,'GC30_R002_CODE_SOURCE_DRIFT_'+Path(name).name)
 ws=share/client/'_forprint_automation'
 need(folder(share) and folder(ws) and folder(ws/'input') and folder(ws/'template_studio'), 'GC30_R002_WORKSPACE_MISSING')
 need(ws.resolve(strict=True).parent.parent==share.resolve(strict=True),'GC30_R002_WORKSPACE_ESCAPE')
 q=ws/'template_studio'/'dispatch'/'queued'
 need(folder(q),'GC30_R002_QUEUE_MISSING')
 items=sorted(q.iterdir())
 need(len(items)==1 and items[0].name==PILOT+'.json','GC30_R002_QUEUE_NOT_EXACT_ONE')
 ticketfile=items[0]
 need(regular(ticketfile) and ticketfile.stat().st_size<128000,'GC30_R002_TICKET_UNSAFE')
 ticket_bytes=ticketfile.read_bytes()
 t=json.loads(ticket_bytes)
 need(t.get('schema_version')==TICKET_SCHEMA and t.get('ticket_id')==PILOT and t.get('job_id')==JOB,'GC30_R002_TICKET_ID_DRIFT')
 need(t.get('worker_id')==WORKER and t.get('worker_machine')=='PREPRESS' and t.get('worker_user')=='Work','GC30_R002_WORKER_BINDING_DRIFT')
 need(t.get('client_folder')==client and t.get('status')=='QUEUED' and t.get('review_only') is True and t.get('production_ready') is False,'GC30_R002_AUTHORITY_DRIFT')
 need(t.get('run_relative')=='template_studio/native_runs/'+PILOT,'GC30_R002_RUN_RELATIVE_INVALID')
 need(SHA.fullmatch(t.get('accepted_zip_sha256','')) is not None,'GC30_R002_ACCEPTED_SHA_MISSING')
 candidates=[]
 for f in (ws/'input').glob('*.zip'):
  if regular(f) and 0<f.stat().st_size<=40*1024*1024:
   with zipfile.ZipFile(f) as z:
    if {'accepted_constructor_bundle.yaml','artifact_manifest.yaml','handoff_manifest.json'}.issubset(z.namelist()):candidates.append(f)
 need(len(candidates)==1,'GC30_R002_ACCEPTED_ARCHIVE_NOT_UNIQUE')
 with candidates[0].open('rb') as inp:
  h=sha256()
  for b in iter(lambda:inp.read(1048576),b''):h.update(b)
 need(h.hexdigest()==t['accepted_zip_sha256'],'GC30_R002_ACCEPTED_ARCHIVE_SHA_DRIFT')
 run=ws/'template_studio'/'native_runs'/PILOT
 need(folder(run) and folder(run/'assets') and folder(run.parent),'GC30_R002_RUN_DIR_UNSAFE')
 source_files={'ticket.json':ticket_bytes}
 for name,key in (('scene_manifest.json','scene_manifest_sha256'),('run_in_illustrator.jsx','jsx_sha256')):
  p=run/name
  need(regular(p),'GC30_R002_RUN_FILE_MISSING_'+name)
  data=p.read_bytes()
  need(SHA.fullmatch(t.get(key,'')) is not None and digest(data)==t[key],'GC30_R002_RUN_HASH_DRIFT_'+name)
  source_files[name]=data
 s=json.loads(source_files['scene_manifest.json'])
 need(s.get('schema_version')==SCENE_SCHEMA and s.get('pages')==4,'GC30_R002_SCENE_INVALID')
 need(s.get('production_ready') is False and s.get('job_id')==JOB and s.get('accepted_zip_sha256')==t['accepted_zip_sha256'],'GC30_R002_SCENE_AUTHORITY_DRIFT')
 need(s.get('jsx_sha256')==t['jsx_sha256'] and isinstance(s.get('asset_sha256'),dict),'GC30_R002_SCENE_BINDING_DRIFT')
 assets=s['asset_sha256']
 need(len(assets)==12 and assets==t.get('asset_sha256'),'GC30_R002_ASSET_SET_DRIFT')
 for name,want in sorted(assets.items()):
  need(NAME.fullmatch(name) is not None and SHA.fullmatch(want) is not None,'GC30_R002_UNSAFE_ASSET_NAME')
  p=run/'assets'/name
  need(regular(p),'GC30_R002_ASSET_MISSING')
  data=p.read_bytes()
  need(digest(data)==want,'GC30_R002_ASSET_HASH_DRIFT_'+name)
  source_files['assets/'+name]=data
 need(all(not x.is_symlink() for x in (ws/'template_studio',q,run,run/'assets')),'GC30_R002_LINK_FORBIDDEN')
 meta={
  'schema_version':'forprint_gc30_offline_sftp_payload_r002',
  'scope':'EXACT_ONE_NON_PRODUCTION_DEG_PILOT',
  'ticket_id':PILOT, 'job_id':JOB, 'worker_id':WORKER,
  'worker_machine':'PREPRESS','worker_user':'Work',
  'target_root':D_ROOT,'target_subtree':'jobs/'+PILOT,
  'config_policy':'DO_NOT_TOUCH_EXISTING_CONFIG_OR_GC32',
  'source_workspace_not_exported':True,
  'illustrator_launch':False,'production_ready':False,
  'automatic_accept':False,'network_delivery_performed':False,
  'source_file_sha256':{n:digest(b) for n,b in sorted(source_files.items())},
  'assets_count':len(assets),
 }
 return source_files,meta

def zip_bytes(files,meta):
 payload={**files,'offline_payload_manifest.json':(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf8')}
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,b in sorted(payload.items()):
   info=zipfile.ZipInfo(n,date_time=(2026,1,1,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED
   info.external_attr=0o100600<<16
   z.writestr(info,b)
 return out.getvalue()

def run(client,mode,confirm,*,root=ROOT,share=SHARE,out_dir=None):
 need(mode in ('check','package'),'GC30_R002_MODE_INVALID')
 need(confirm==(mode=='package'),'GC30_R002_CONFIRMATION_MISMATCH')
 files,meta=source(client,root=root,share=share)
 print('GC30_R002_EXACT_TICKET=PASS ID='+meta['ticket_id'])
 print('GC30_R002_SCENE=PASS PAGES=4')
 print('GC30_R002_ASSETS=PASS COUNT='+str(meta['assets_count']))
 print('GC30_R002_SOURCE_SHA256=PASS')
 print('GC30_R002_DROOT_TOPOLOGY=EXISTING_JOBS_SUBTREE_NO_CLIENTS_NO_SHARED')
 if mode=='check':
  print('GC30_R002_PACKAGE=NOT_EXECUTED_READ_ONLY')
  print('GC30_R002_SFTP=NOT_EXECUTED')
  return None
 need(out_dir is not None,'GC30_R002_OUTPUT_DIR_REQUIRED')
 out_dir=Path(out_dir)
 need(out_dir.is_absolute() and out_dir.is_relative_to(root/'tmp'),'GC30_R002_OUTPUT_OUTSIDE_PROJECT_TMP')
 need(not out_dir.exists() and not out_dir.is_symlink(),'GC30_R002_OUTPUT_ALREADY_EXISTS')
 bundle=zip_bytes(files,meta)
 # Fail before any writes on excessively large payloads.
 need(len(bundle)<=150*1024*1024,'GC30_R002_PAYLOAD_TOO_LARGE')
 out_dir.mkdir(mode=0o700,parents=False)
 target=out_dir/'gc30_exact_deg_sftp_payload_r002.zip'
 import os
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
 with os.fdopen(fd,'wb') as f:f.write(bundle);f.flush();os.fsync(f.fileno())
 need(digest(target.read_bytes())==digest(bundle),'GC30_R002_PACKAGE_HASH_DRIFT')
 with zipfile.ZipFile(target) as z:
  names=set(z.namelist())
  need(names==set(files)|{'offline_payload_manifest.json'},'GC30_R002_ZIP_MEMBERS_DRIFT')
  for name,data in files.items():need(z.read(name)==data,'GC30_R002_ZIP_VERIFY_'+name)
 print('GC30_R002_PACKAGE=READY_SERVER_ONLY')
 print('GC30_R002_PACKAGE_PATH='+str(target.relative_to(root)))
 print('GC30_R002_PACKAGE_SHA256='+digest(bundle))
 print('GC30_R002_SFTP=NOT_EXECUTED')
 print('GC30_R002_LOCAL_STAGE=NOT_EXECUTED')
 return target

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--mode',choices=('check','package'),required=True)
 p.add_argument('--client-name',required=True)
 p.add_argument('--gdl-root',default=str(ROOT))
 p.add_argument('--output-dir')
 p.add_argument('--confirm-local-package',action='store_true')
 a=p.parse_args()
 try:
  root=Path(a.gdl_root).resolve()
  need(root==ROOT.resolve(),'GC30_R002_PROJECT_ROOT_MISMATCH')
  run(a.client_name,a.mode,a.confirm_local_package,root=root,out_dir=a.output_dir)
  return 0
 except (Blocked,OSError,KeyError,ValueError,zipfile.BadZipFile,TypeError) as e:
  print('GC30_R002=BLOCKED reason='+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
