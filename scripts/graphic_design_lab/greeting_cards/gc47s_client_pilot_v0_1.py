#!/usr/bin/env python3
"""GC47S: client-owned immutable greeting-card pilot loop. Non-release.

One command discovers accepted client handoff and creates one isolated attempt per
job, compiling a native GC29 scene only if that exact variant is implemented.
A separately completed Illustrator output can be verified and returned to the
same client's output. No Windows execution is claimed in this revision.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
SHARE=Path('/srv/smb/In_Progress/data')
GC29=ROOT/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py'
REGISTRY=ROOT/'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
PILOT_KEY='client_pilot_loop_v0_1'
ID_RE=re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
PRODUCT='GREETING_CARD_4_PAGE'
GC29_PY_SHA='c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42'
GC29_JSX_SHA='96b0549cc21cc82f35e1648e16f4ee25cb88fd8d9333c1ad6a38b16c9b306955'
REQUIRED_NATIVE=('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png','result.json')
MAX_OUTPUT_BYTES=600*1024*1024

class Blocked(Exception): pass

def need(value,code):
    if not value: raise Blocked(code)

def isdir(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False

def isfile(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def write_json_x(path,obj):
    with path.open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write('\n');f.flush();os.fsync(f.fileno())

def read_obj(p,limit=2_000_000):
    need(isfile(p) and p.stat().st_size<limit,'JSON_MISSING_UNSAFE_OR_OVERSIZED')
    x=json.loads(p.read_text('utf-8'))
    need(isinstance(x,dict),'JSON_ROOT_NOT_OBJECT')
    return x

def load_source():
    need(isdir(ROOT/'.git') and ROOT.name=='forprint_graphic_design_lab','GDL_ROOT_INVALID')
    need(isfile(GC29) and sha(GC29)==GC29_PY_SHA,'GC29_SOURCE_SHA_DRIFT')
    jsx=GC29.with_suffix('.jsx')
    need(isfile(jsx) and sha(jsx)==GC29_JSX_SHA,'GC29_JSX_SHA_DRIFT')
    sp=importlib.util.spec_from_file_location('gc47s_gc29_source',GC29)
    need(sp is not None and sp.loader is not None,'GC29_IMPORT_INVALID')
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    return m

def current_passport():
    d=read_obj(REGISTRY,5_000_000)
    p=d.get('greeting_card_machine_pipeline_v0_1')
    need(isinstance(p,dict),'GC47K_MACHINE_BLOCK_MISSING')
    need(p.get('schema_version')=='forprint_gdl_greeting_card_machine_pipeline_v0_1','GC47K_SCHEMA_INVALID')
    loop=p.get(PILOT_KEY)
    need(isinstance(loop,dict) and loop.get('schema_version')=='gdl_gc47s_client_pilot_loop_v0_1','GC47S_PASSPORT_NOT_INSTALLED')
    need(loop.get('production_ready') is False and loop.get('dual_runtime_enabled') is False,'PASSPORT_AUTHORITY_DRIFT')
    return d,loop

def workspace(client):
    need(isinstance(client,str) and client and client not in ('.','..') and '/' not in client and '\\' not in client and '\x00' not in client,'CLIENT_NAME_INVALID')
    need(isdir(SHARE),'SMB_SHARE_MISSING')
    root=SHARE.resolve(strict=True)
    c=SHARE/client
    w=c/'_forprint_automation'
    for p in (c,w,w/'input',w/'output',w/'template_studio'):
        need(isdir(p),'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(w.resolve(strict=True).parent.parent==root,'WORKSPACE_ESCAPED_SHARE')
    return w

def pilot_dir(ws,job,attempt):
    need(ID_RE.fullmatch(job) and ID_RE.fullmatch(attempt),'JOB_OR_ATTEMPT_ID_UNSAFE')
    return ws/'template_studio'/'greeting_card_pilots'/job/attempt

def review_dir(ws,job,attempt):
    return ws/'output'/'greeting_card_pilots'/job/attempt

def classify(job):
    b=job.get('builder_v1') or {}
    fam=(b.get('front') or {}).get('family')
    image=(b.get('inside_image') or {}).get('mode')
    sign=(b.get('sender_text') or {}).get('signature_variant_id')
    # Matches GC29 actual compile_scene guards; do not widen by invention.
    supported=(fam in ('STANDARD','RECIPIENT_BRANDING_OVERLAY') and
               image=='DEFAULT_ASSET' and sign in ('GRIGO','HERASYMENKO'))
    return {'front':fam,'image':image,'signature':sign},supported

def attempt_id():
    return 'p'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex[:8]

def native_run_dir(ws,job,attempt):
    return ws/'template_studio'/'native_runs'/(job+'__'+attempt)

def start_one(gc29,ws,job,archive,passport,job_id=None):
    jid=job.get('job_id')
    need(isinstance(jid,str) and ID_RE.fullmatch(jid),'ACCEPTED_JOB_ID_INVALID')
    if job_id is not None and jid!=job_id: return None
    variants,supported=classify(job)
    attempt=attempt_id()
    base=pilot_dir(ws,jid,attempt)
    need(isdir(base.parent) or not base.parent.exists(),'PILOT_PARENT_UNSAFE')
    base.parent.mkdir(parents=True,exist_ok=True)
    need(isdir(base.parent),'PILOT_PARENT_NOT_DIRECTORY')
    base.mkdir(mode=0o750)
    # Receipt is first and immutable. Unsupported profiles are still registered
    # honestly, never silently replaced with flowers/single signer.
    receipt={
      'schema_version':'gdl_gc47s_client_pilot_attempt_v0_1',
      'product':PRODUCT,'job_id':jid,'attempt_id':attempt,
      'accepted_zip_sha256':sha(archive),'source_gc29_sha256':sha(GC29),
      'passport_registry_sha256':sha(REGISTRY),
      'passport_schema_version':passport['schema_version'],
      'variants':variants,'renderer_supported':supported,
      'state':'INTAKE_REVIEWED','native_scene_relative':None,
      'visual_approved':False,'production_ready':False,
      'dual_runtime_enabled':False,'automatic_retry':False,
    }
    write_json_x(base/'passport_snapshot.json',passport)
    write_json_x(base/'receipt.json',receipt)
    state='BLOCKED_RENDERER_VARIANT_NOT_IMPLEMENTED' if not supported else 'PREPARING_NATIVE_GC29'
    if supported:
        try:
            gc29.prepare(ws,jid,attempt)
            run=native_run_dir(ws,jid,attempt)
            need(isdir(run) and isfile(run/'run_in_illustrator.jsx') and isfile(run/'scene_manifest.json'), 'NATIVE_PREPARED_FILES_MISSING')
            scene=read_obj(run/'scene_manifest.json')
            need(scene.get('pages')==4 and scene.get('job_id')==jid,'NATIVE_SCENE_BINDING_MISMATCH')
            receipt['native_scene_relative']=str(run.relative_to(ws))
            receipt['native_jsx_sha256']=sha(run/'run_in_illustrator.jsx')
            state='PREPARED_WINDOWS_EXECUTION_NOT_WIRED'
        except (OSError,ValueError,KeyError,Blocked) as e:
            # Fail closed and retain the immutable attempt for diagnosis.
            state='BLOCKED_NATIVE_PREPARE'
            receipt['native_prepare_error_class']=type(e).__name__
    receipt['state']=state
    write_json_x(base/'state.json',receipt)
    return {'job':jid,'attempt':attempt,'state':state}

def start(gc29,client,selected=None):
    _,passport=current_passport()
    ws=workspace(client)
    jobs,_,archive=gc29.accepted_jobs(ws) # GC25 validates source provenance.
    need(isinstance(jobs,list) and len(jobs)>0,'NO_ACCEPTED_JOBS')
    ids=[j.get('job_id') for j in jobs]
    need(len(ids)==len(set(ids)),'ACCEPTED_JOB_IDS_DUPLICATE')
    need(selected is None or selected in ids,'SELECTED_JOB_NOT_ACCEPTED')
    result=[]
    for job in jobs:
        entry=start_one(gc29,ws,job,archive,passport,selected)
        if entry:result.append(entry)
    need(result,'NO_SELECTED_JOBS')
    for x in result:
        print('GC47S_JOB='+x['job']+' ATTEMPT='+x['attempt']+' STATE='+x['state'])
    print('GC47S_PILOT=ATTEMPTS_RECORDED_'+str(len(result)))
    print('GC47S_WINDOWS_EXEC=FALSE OUTPUT_PUBLISHED=FALSE')
    print('GC47S_CHECKPOINT=CLIENT_ACCEPTED_INPUT_TO_IMMUTABLE_ATTEMPTS_NON_RELEASE')

def status(client,job,attempt):
    ws=workspace(client)
    a=pilot_dir(ws,job,attempt)
    s=read_obj(a/'state.json')
    need(s.get('job_id')==job and s.get('attempt_id')==attempt,'ATTEMPT_ID_MISMATCH')
    out=review_dir(ws,job,attempt)
    print('GC47S_ATTEMPT='+attempt)
    print('GC47S_STATE='+s['state'])
    print('GC47S_NATIVE_SCENE='+('PRESENT' if s.get('native_scene_relative') else 'ABSENT'))
    print('GC47S_REVIEW_OUTPUT='+('PRESENT' if isdir(out) else 'ABSENT'))
    print('GC47S_PRODUCTION_READY=FALSE DUAL_RUNTIME=DISABLED')

def verify_native(src,receipt):
    need(isdir(src) and not src.is_symlink(),'NATIVE_OUT_MISSING_OR_UNSAFE')
    for name in REQUIRED_NATIVE:
        p=src/name
        need(isfile(p) and 100<p.stat().st_size<MAX_OUTPUT_BYTES,'NATIVE_FILE_MISSING_OR_UNSAFE_'+name.replace('.','_').upper())
    result=read_obj(src/'result.json',1_000_000)
    need(result.get('state')=='AI_REOPENED_VISUAL_REVIEW_REQUIRED', 'NATIVE_STATE_NOT_SUCCESSFUL')
    need(result.get('pages')==4,'NATIVE_PAGES_NOT_FOUR')
    need(result.get('production_ready') is False and result.get('visual_approved') is False,'NATIVE_AUTHORITY_UNSAFE')
    need(result.get('p04_greeting_fit_state')=='VISIBLE_CONTENT_FITS','NATIVE_P04_FIT_NOT_CONFIRMED')
    need(isinstance(result.get('p04_total_chars'),int) and result['p04_total_chars']>0 and
         isinstance(result.get('p04_visible_chars'),int) and result['p04_visible_chars']>=result['p04_total_chars'],
         'NATIVE_P04_CHARACTER_COVERAGE_UNPROVEN')
    need((src/'design.ai').stat().st_size>1000,'NATIVE_AI_TOO_SMALL')
    from PIL import Image
    for n in REQUIRED_NATIVE:
        if not n.endswith('.png'):continue
        with Image.open(src/n) as image:
            need(image.format=='PNG' and image.width>100 and image.height>100,'NATIVE_PNG_INVALID')
            image.verify()
    try: import pymupdf
    except ImportError:
        try: import fitz as pymupdf
        except ImportError as e: raise Blocked('PDF_VALIDATOR_NOT_AVAILABLE') from e
    with pymupdf.open(src/'review.pdf') as pdf:
        need(len(pdf)==4,'NATIVE_PDF_NOT_FOUR_PAGES')
        mm=lambda x:round(x*25.4/72,2)
        for p in pdf:
            need(abs(mm(p.rect.width)-214)<1.0 and abs(mm(p.rect.height)-301)<1.0,'NATIVE_PDF_GEOMETRY_CHANGED')
    return {name:sha(src/name) for name in REQUIRED_NATIVE}

def collect(client,job,attempt):
    ws=workspace(client)
    base=pilot_dir(ws,job,attempt)
    s=read_obj(base/'state.json')
    need(s.get('job_id')==job and s.get('attempt_id')==attempt,'ATTEMPT_ID_MISMATCH')
    need(s.get('state')=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED','NATIVE_CANDIDATE_NOT_PREPARED')
    need(s.get('native_scene_relative')==str(native_run_dir(ws,job,attempt).relative_to(ws)),'NATIVE_RUN_BOUNDARY_MISMATCH')
    source=native_run_dir(ws,job,attempt)
    need(isfile(source/'run_in_illustrator.jsx') and sha(source/'run_in_illustrator.jsx')==s.get('native_jsx_sha256'),'JSX_SOURCE_DRIFT')
    digest=verify_native(source/'out',s)
    target=review_dir(ws,job,attempt)
    need(not target.exists() and not target.is_symlink(),'REVIEW_DEST_ALREADY_EXISTS_NO_OVERWRITE')
    need(isdir(ws/'output'),'CLIENT_OUTPUT_MISSING')
    parent=target.parent
    parent.mkdir(parents=True,exist_ok=True)
    need(isdir(parent),'REVIEW_PARENT_UNSAFE')
    temp=Path(tempfile.mkdtemp(prefix='.gc47s_review_',dir=parent))
    try:
        for n in REQUIRED_NATIVE:
            shutil.copyfile(source/'out'/n,temp/n)
            need(sha(temp/n)==digest[n],'COPIED_NATIVE_ARTIFACT_SHA_CHANGED')
        shutil.copyfile(base/'passport_snapshot.json',temp/'passport_snapshot.json')
        verify={'schema_version':'gdl_gc47s_review_verification_v0_1','job_id':job,'attempt_id':attempt,
                'files_sha256':digest,'source_jsx_sha256':s['native_jsx_sha256'],
                'ai_native_reopen':'WORKER_REPORTED','pdf_pages':4,'visual_approved':False,
                'production_ready':False,'dual_runtime_enabled':False}
        write_json_x(temp/'verify.json',verify)
        (temp/'REVIEW_REQUIRED.txt').write_text('Лабораторний пілот. Потрібне візуальне погодження оператора.\nPRODUCTION_READY=false\n',encoding='utf8')
        lines=[]
        for p in sorted(temp.iterdir()):
            need(isfile(p),'REVIEW_UNEXPECTED_ENTRY')
            lines.append(sha(p)+'  '+p.name)
        (temp/'SHA256SUMS').write_text('\n'.join(lines)+'\n',encoding='ascii')
        # GC47AB: protect files during assembly, then publish SMB group-readable.
        # tempfile.mkdtemp() defaults to 0700; rename() preserves that mode.
        group_gid=parent.stat().st_gid
        need(bool(parent.stat().st_mode & stat.S_ISGID) and
             group_gid==(ws/'output').stat().st_gid,'REVIEW_PARENT_GROUP_INHERITANCE_UNSAFE')
        for p in temp.iterdir():
            need(isfile(p) and p.stat().st_gid==group_gid,'REVIEW_FILE_GROUP_UNSAFE')
            os.chmod(p,0o640,follow_symlinks=False)
            need(stat.S_IMODE(p.stat().st_mode)==0o640,'REVIEW_FILE_MODE_UNSAFE')
        need(temp.stat().st_gid==group_gid,'REVIEW_TEMP_GROUP_UNSAFE')
        os.chmod(temp,0o2750,follow_symlinks=False)
        need(stat.S_IMODE(temp.stat().st_mode)==0o2750,'REVIEW_TEMP_MODE_UNSAFE')
        temp.rename(target)
    finally:
        if temp.exists():shutil.rmtree(temp)
    print('GC47S_REVIEW=PACKAGE_VERIFIED_PUBLISHED_CLIENT_OUTPUT')
    print('GC47S_REVIEW_RELATIVE='+str(target.relative_to(ws)))
    print('GC47S_CHECKPOINT=LAB_REVIEW_PACKAGE_READY_NOT_APPROVED')

def discover():
    need(isdir(SHARE),'SMB_SHARE_MISSING')
    result=[]
    for client in sorted(SHARE.iterdir(),key=lambda p:p.name):
        if not isdir(client):continue
        inp=client/'_forprint_automation'/'input'
        if not isdir(inp):continue
        zips=[p for p in inp.iterdir() if isfile(p) and p.suffix.lower()=='.zip']
        if zips: result.append((client.name,len(zips)))
    for name,count in result: print('GC47S_CLIENT_INPUT='+name+' ZIP_COUNT='+str(count))
    print('GC47S_DISCOVERED_CLIENTS='+str(len(result)))
    print('GC47S_CHECKPOINT=DISCOVERY_ONLY_NO_MUTATION')

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('check','discover','run','status','collect'),required=True)
    ap.add_argument('--client-name');ap.add_argument('--job-id');ap.add_argument('--attempt-id')
    ap.add_argument('--confirm-client-pilot',action='store_true')
    ap.add_argument('--confirm-review-collection',action='store_true')
    opt=ap.parse_args(argv)
    try:
        gc29=load_source();_,loop=current_passport()
        need(loop.get('operator_entrypoint')=='gdl-greeting-card-client-pilot','PASSPORT_LAUNCHER_DRIFT')
        if opt.mode=='check':
            print('GC47S_PASSPORT=PASS_EXISTING_GC47K_EXTENDED')
            print('GC47S_GC29=PASS_PRESENT')
            print('GC47S_CHECKPOINT=CLIENT_PILOT_OPERATOR_READY')
        elif opt.mode=='discover': discover()
        elif opt.mode=='run':
            need(opt.confirm_client_pilot,'CONFIRM_CLIENT_PILOT_REQUIRED')
            need(opt.client_name,'CLIENT_NAME_REQUIRED')
            start(gc29,opt.client_name,opt.job_id)
        elif opt.mode=='status':
            need(opt.client_name and opt.job_id and opt.attempt_id,'CLIENT_JOB_ATTEMPT_REQUIRED')
            status(opt.client_name,opt.job_id,opt.attempt_id)
        elif opt.mode=='collect':
            need(opt.confirm_review_collection,'CONFIRM_REVIEW_COLLECTION_REQUIRED')
            need(opt.client_name and opt.job_id and opt.attempt_id,'CLIENT_JOB_ATTEMPT_REQUIRED')
            collect(opt.client_name,opt.job_id,opt.attempt_id)
        print('GC47S_PRODUCTION_READY=FALSE DUAL_RUNTIME=DISABLED')
        return 0
    except (Blocked,ValueError,KeyError,TypeError,OSError,ImportError,zipfile.BadZipFile) as e:
        reason=str(e) if isinstance(e,Blocked) else type(e).__name__.upper()
        print('GC47S=BLOCKED_'+reason,file=sys.stderr)
        print('GC47S_NO_SILENT_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
