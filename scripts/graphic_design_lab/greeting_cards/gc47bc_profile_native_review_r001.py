#!/usr/bin/env python3
"""GC47BC: isolated source-bound APA/DEG/BAS native review, one explicit attempt only.

No new Windows worker, no modification of GC47AX/Launcher/Makefile. Source
binding is to immutable GC47BB JSX identities and the accepted client ZIP.
A native run is LAB REVIEW ONLY. Never auto-retry or queue jobs.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
BB_NAME = 'gc47bb_source_bound_geometry_proof_r001.py'
BB_SHA = 'ade96e19fbfea59d80331a74c14f1a32710847cbf14318791ee1ec6c8f95a254'
LIFE_NAME = 'gc47ax_illustrator_lifecycle_r001.py'
LIFE_SHA = '7da40974a4d2dcc26d3f11447fd1d40ee6300fd3104480d487fe4f34fccfd2d9'
POST_NAME = 'gc47ax_postflight_r001.py'
POST_SHA = 'f2e5e2636fc88622f861998d426b919e12678728514adac0992b5803fe3cd5c3'
EXPECTED_HEAD = '83cefbef5d85ee2dfd28ced33e2a237ee78b67cb'
ACCEPTED_SHA = '90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
SCHEMA = 'gdl_gc47bc_profile_native_review_r001'
REVIEW_BINDING = 'gc47bc_profile_review_binding_r001.json'
STATE_ROOT = ROOT.parent/'.state'/'graphic_design_lab'/'lifecycle'
LOCK = STATE_ROOT/'gc47ax_single_lifecycle_r001.lock' # same inode/lock as GC47AX
JOBS = {
 'gdl_gc_apa_20261011': {'front':'STANDARD','signature':'GRIGO',
   'jsx_sha256':'f4066e725e947d5a5c865e40683270b910cb6c27eda9f1f133dc891ab1bfd7da','greeting_chars':574,'sender_rows':4},
 'gdl_gc_deg_20261011': {'front':'STANDARD','signature':'HERASYMENKO',
   'jsx_sha256':'c8346efe2b9148b1417ef157595be73339d4679251cf9f4eb342242929ae42e0','greeting_chars':898,'sender_rows':3},
 'gdl_gc_bas_20261011': {'front':'RECIPIENT_BRANDING_OVERLAY','signature':'HERASYMENKO',
   'jsx_sha256':'053c1b44459b9a22e1b72b6dcb3fac4d47cfaa4cfdeef7ca306de546f40d1cb0','greeting_chars':876,'sender_rows':3}
}

class Blocked(RuntimeError): pass

def need(ok,code):
    if not ok: raise Blocked(code)

def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def regular(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except OSError: return False

def import_pinned(path,expected,key):
    need(regular(path) and file_sha(path)==expected,'PINNED_MODULE_DRIFT_'+path.name)
    sp=importlib.util.spec_from_file_location(key,path)
    need(sp is not None and sp.loader is not None,'MODULE_IMPORT_FAILED')
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    return m

def sources(root=ROOT,can=CAN):
    need(root.name=='forprint_graphic_design_lab' and (root/'.git').is_dir(),'GDL_REPOSITORY_REQUIRED')
    bb=import_pinned(can/BB_NAME,BB_SHA,'gc47bc_pinned_bb')
    life=import_pinned(can/LIFE_NAME,LIFE_SHA,'gc47bc_pinned_life')
    post=import_pinned(can/POST_NAME,POST_SHA,'gc47bc_pinned_post')
    need(post.LOCK==root.parent/'.state'/'graphic_design_lab'/'lifecycle'/'gc47ax_single_lifecycle_r001.lock',
         'CANONICAL_LOCK_CHANGED')
    need(bb.az_module(root,can).EXPECTED_HEAD==EXPECTED_HEAD,'SOURCE_HEAD_PIN_DRIFT')
    need(bb.az_module(root,can).ARCHIVE_SHA==ACCEPTED_SHA,'ACCEPTED_SOURCE_PIN_DRIFT')
    life.verify_local() # Check existing SHA-verified controller, worker, GC47AX/AR
    return bb,life,post

def profile_inputs(client,job_id,root=ROOT,can=CAN):
    need(job_id in JOBS,'JOB_NOT_SUPPORTED_ZAP_OR_UNKNOWN')
    need(isinstance(client,str) and client.strip(),'CLIENT_REQUIRED')
    bb,life,post=sources(root,can)
    report=bb.native_candidates(root,client) # source-bound; memory only
    need(report['status']=='PASS_FOUR_GENERIC_JSX_CANDIDATES_GEOMETRY_TRIAGED_NON_NATIVE',
         'FOUR_PROFILE_SOURCE_PROOF')
    need(report['source_sha256']==ACCEPTED_SHA and report['git_head_expected']==EXPECTED_HEAD,
         'SOURCE_PROVENANCE_CHANGED')
    entries={p['job_id']:p for p in report['profiles']}
    need(set(entries)==set(JOBS)|{'gdl_gc_zap_20261011'},'PROFILE_SET_CHANGED')
    expected=JOBS[job_id];item=entries[job_id]
    need(item['jsx_sha256']==expected['jsx_sha256'] and item['greeting_chars']==expected['greeting_chars'] and
         item['sender_row_count']==expected['sender_rows'],'PROFILE_JSX_OR_TEXT_DRIFT')
    need(item['variant']=={'front':expected['front'],'image':'DEFAULT_ASSET','signature':expected['signature']},
         'PROFILE_VARIANT_CHANGED')
    need(item['pages']==4 and item['source_geometry_validated'] is True and
         item['status']=='CANDIDATE_JSX_COMPILED_IN_MEMORY_NO_NATIVE','PROFILE_CANDIDATE_NOT_VERIFIED')
    need(item['native_authorized'] is False and item['production_ready'] is False and
         item['visual_approved'] is False,'NATIVE_SOURCE_AUTHORITY_DRIFT')
    expected_warning={'P03_NATIVE_CROP_UNVERIFIED','P04_NATIVE_FONT_FIT_UNVERIFIED','VISUAL_APPROVAL_ABSENT',
                      'GENERIC_GC29_JSX_NOT_GC47AX_APPROVED_ZAP',
                      'SOURCE_BOUND_OUTSIDE_MEDIA_REVIEW_REQUIRED_P03_FLOWERS'}
    need(expected_warning.issubset(set(item['blocking_gates'])),'PROFILE_RISK_GATES_MISSING')
    if expected['signature']=='HERASYMENKO':
        need('HERASYMENKO_THREE_ROW_GEOMETRY_UNVERIFIED' in item['blocking_gates'],'SIGNATURE_REVIEW_GUARD')
    if job_id.endswith('_bas_20261011'):
        need('BAS_P01_BRANDING_PLACEMENT_UNVERIFIED' in item['blocking_gates'] and
             item['branding_png']=={'height_px':1097,'width_px':1954},'BRANDING_REVIEW_GUARD')
    az=bb.az_module(root,can)
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bc_pinned_gc47t')
    s,gc29=t.source_check()
    ws,job,archive,variant=t.validate_job(s,gc29,client,job_id)
    need(file_sha(archive)==ACCEPTED_SHA,'ACCEPTED_ARCHIVE_SHA_DRIFT')
    need(variant==item['variant'],'ACCEPTED_PROFILE_DRIFT')
    return {'report':item,'t':t,'s':s,'gc29':gc29,'life':life,'ws':ws,'job':job,
            'archive':archive,'post':post,'client':client,'job_id':job_id}

def lock_owner(root=ROOT):
    parent=root.parent/'.state'/'graphic_design_lab'
    path=parent/'lifecycle'
    for p in (parent,path):
        need(p.is_dir() and not p.is_symlink(),'STATE_DIRECTORY_MISSING_OR_SYMLINK')
        st=p.stat()
        need(st.st_uid==os.geteuid() and stat.S_IMODE(st.st_mode)==0o700,'STATE_OWNER_OR_PERMISSIONS')
    return path/'gc47ax_single_lifecycle_r001.lock'

class Exclusive:
    def __init__(self,root=ROOT): self.root=root;self.fd=None
    def __enter__(self):
        path=lock_owner(self.root)
        self.fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            st=os.fstat(self.fd)
            need(stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o600,'STATE_LOCK_MODE')
            try: fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise Blocked('ANOTHER_GC47AX_OR_GC47BC_LIFECYCLE_ACTIVE')
            now=path.lstat()
            need((st.st_dev,st.st_ino)==(now.st_dev,now.st_ino),'LOCK_INODE_CHANGED')
            return self
        except BaseException:
            os.close(self.fd);self.fd=None;raise
    def __exit__(self,*exc):
        if self.fd is not None:os.close(self.fd);self.fd=None

def readonly_preflight(data):
    t=data['t'];t.ssh_options()
    data['life'].remote_inspect(t)
    print('GC47BC_PREFLIGHT=PASS_SOURCE_BOUND_GUI_INSPECTION_ONLY',flush=True)

def binding(s,ws,job,attempt):
    need(bool(s.ID_RE.fullmatch(attempt)),'ATTEMPT_FORMAT')
    obj=s.read_obj(s.pilot_dir(ws,job,attempt)/REVIEW_BINDING)
    need(obj['schema_version']==SCHEMA and obj['attempt_id']==attempt and obj['job_id']==job,
         'ATTEMPT_SOURCE_BINDING_MISSING')
    need(obj['jsx_sha256']==JOBS[job]['jsx_sha256'] and obj['accepted_zip_sha256']==ACCEPTED_SHA and
         obj['native_dispatch_count_max']==1 and obj['production_ready'] is False and
         obj['visual_approved'] is False and obj['automatic_retry'] is False,'ATTEMPT_AUTHORITY_DRIFT')
    st=s.read_obj(s.pilot_dir(ws,job,attempt)/'state.json')
    need(st.get('attempt_id')==attempt and st.get('job_id')==job and
         st.get('state')=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED' and
         st.get('native_jsx_sha256')==obj['jsx_sha256'],'ATTEMPT_STATE_CHANGED')
    return obj

def make_one_attempt(data):
    s=data['s'];t=data['t'];gc29=data['gc29'];ws=data['ws'];job=data['job_id']
    _,passport=s.current_passport()
    result=s.start_one(gc29,ws,data['job'],data['archive'],passport,job)
    need(result is not None,'NATIVE_ATTEMPT_NOT_PREPARED_NO_RETRY')
    attempt=result['attempt']
    print('GC47BC_JOB='+job+' ATTEMPT='+attempt+' STATE='+result['state'],flush=True)
    print('GC47BC_NO_AUTO_RETRY=TRUE ON_FAILURE_STATUS_OR_COLLECT_ONLY',flush=True)
    need(result['state']=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED','NATIVE_ATTEMPT_PREPARE_BLOCKED')
    run=s.native_run_dir(ws,job,attempt);state=s.read_obj(s.pilot_dir(ws,job,attempt)/'state.json')
    scene=s.read_obj(run/'scene_manifest.json')
    exp=data['report']['jsx_sha256']
    need(state.get('native_jsx_sha256')==exp and t.sha_file(run/'run_in_illustrator.jsx')==exp,
         'PREPARED_JSX_NOT_EQUAL_SOURCE_BOUND_PROOF_NO_RETRY')
    need(scene.get('pages')==4 and scene.get('signature')==JOBS[job]['signature'] and
         scene.get('family')==JOBS[job]['front'],'SCENE_VARIANT_NOT_BOUND_NO_RETRY')
    rec={'schema_version':SCHEMA,'job_id':job,'attempt_id':attempt,
         'accepted_zip_sha256':ACCEPTED_SHA,'jsx_sha256':exp,
         'native_dispatch_count_max':1,'automatic_retry':False,
         'visual_approved':False,'production_ready':False,
         'renderer_variant':'GENERIC_GC29_FIRST_NATIVE_PROFILE_REVIEW'}
    s.write_json_x(s.pilot_dir(ws,job,attempt)/REVIEW_BINDING,rec)
    return attempt

def publish_complete(data,attempt):
    s=data['s'];job=data['job_id'];ws=data['ws']
    binding(s,ws,job,attempt)
    data['t'].collect_remote(s,ws,job,attempt)
    p=s.review_dir(ws,job,attempt)
    verify=s.read_obj(p/'verify.json')
    need(verify.get('job_id')==job and verify.get('attempt_id')==attempt and
         verify.get('source_jsx_sha256')==JOBS[job]['jsx_sha256'] and
         verify.get('visual_approved') is False and verify.get('production_ready') is False,
         'PUBLISHED_RESULT_PROVENANCE_UNVERIFIED')
    print('GC47BC_RENDER=PASS_PUBLISHED_NATIVE_REVIEW',flush=True)
    print('GC47BC_REVIEW_RELATIVE='+str(p.relative_to(ws)),flush=True)

def safe_postflight(data):
    # Close only after native publication attested by GC47S; never force-kill.
    print('GC47BC_POSTFLIGHT=BEGIN_SAVED_ONLY',flush=True)
    try:
        data['life'].prepare(data['t'])
    except Exception:
        print('GC47BC_RENDER_RESULT=RETAINED_PUBLISHED_REVIEW',flush=True)
        print('GC47BC_POSTFLIGHT=BLOCKED_ILLUSTRATOR_STATE_REQUIRES_REVIEW',flush=True)
        print('GC47BC_QUEUE=HALTED_NO_NEW_ATTEMPT',flush=True)
        return 3
    print('GC47BC_POSTFLIGHT=PASS_ILLUSTRATOR_CLOSED',flush=True)
    print('GC47BC_QUEUE=NOT_ENABLED_NEW_ITEM_REQUIRES_SEPARATE_AUTHORITY',flush=True)
    print('GC47BC_PRODUCTION_READY=FALSE VISUAL_APPROVED=FALSE',flush=True)
    return 0

def pilot(data,timeout_minutes):
    t=data['t'];life=data['life'];s=data['s'];ws=data['ws'];job=data['job_id']
    with Exclusive():
        # Window state may have changed after read-only source checks.
        t.ssh_options()
        life.prepare(t)  # can close only already-saved Illustrator docs
        t.windows_preflight()
        attempt=make_one_attempt(data)
        # No fallback or retry after allocation; manual status/collect only.
        transport=t.make_transport(s,ws,job,attempt)
        t.stage_remote(transport,attempt)
        outcome=t.kv_output(t.controller_command(attempt,'launch'))
        need(outcome.get('T1_LAUNCH')=='START_REQUESTED_SINGLE_USE',
             'NATIVE_LAUNCH_UNCERTAIN_STATUS_ONLY_NO_RETRY')
        print('GC47BC_NATIVE=START_REQUESTED_SINGLE_USE',flush=True)
        until=time.monotonic()+60*timeout_minutes
        while time.monotonic()<until:
            state=t.status_remote(attempt)['T1_NATIVE_STATE']
            if state=='AI_REOPENED_VISUAL_REVIEW_REQUIRED':
                publish_complete(data,attempt)
                return safe_postflight(data)
            if state=='BLOCKED_REVIEW_PARTIAL_OUTPUT':
                raise Blocked('WINDOWS_PARTIAL_OUTPUT_STATUS_ONLY_NO_RETRY')
            time.sleep(10)
        raise Blocked('NATIVE_PENDING_STATUS_ONLY_NO_RETRY')

def status_or_collect(data,attempt,collect=False):
    t=data['t'];s=data['s'];ws=data['ws'];job=data['job_id']
    binding(s,ws,job,attempt)
    if not collect:
        t.mode_status(s,data['client'],job,attempt)
        print('GC47BC_STATUS=READ_ONLY_NO_RETRY',flush=True)
        return 0
    with Exclusive():
        binding(s,ws,job,attempt)
        publish_complete(data,attempt)
        return safe_postflight(data)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','inspect','pilot','status','collect'),required=True)
    p.add_argument('--client-name');p.add_argument('--job-id')
    p.add_argument('--attempt-id');p.add_argument('--timeout-minutes',type=int,default=24)
    p.add_argument('--confirm-native-once',action='store_true')
    p.add_argument('--confirm-collect',action='store_true')
    p.add_argument('--confirmation')
    args=p.parse_args(argv)
    try:
        bb,life,post=sources()
        if args.mode=='check':
            need(not args.confirm_native_once and not args.confirm_collect,'CHECK_NOT_AUTHORITY')
            print('GC47BC_CHECK=PASS_PINNED_BB_AX_COMMON_LOCK_NO_NATIVE',flush=True)
            print('GC47BC_NATIVE_DISPATCH=FALSE QUEUE_ENABLED=FALSE',flush=True)
            return 0
        need(args.job_id in JOBS,'JOB_NOT_SUPPORTED_OR_ZAP')
        if args.mode=='pilot':
            need(args.confirm_native_once and args.confirmation=='GC47BC_SINGLE_NATIVE_REVIEW '+args.job_id,
                 'EXPLICIT_PROFILE_NATIVE_AUTHORITY_REQUIRED')
            need(1<=args.timeout_minutes<=30,'TIMEOUT_BOUNDS')
        if args.mode=='collect':
            need(args.confirm_collect and args.confirmation=='GC47BC_COLLECT_EXISTING '+args.job_id,
                 'COLLECT_AUTHORITY_REQUIRED')
        if args.mode in ('status','collect'):
            need(isinstance(args.attempt_id,str) and bool(re.fullmatch(r'p\d{14}-[0-9a-f]{8}',args.attempt_id)),
                 'EXISTING_ATTEMPT_REQUIRED')
        data=profile_inputs(args.client_name,args.job_id)
        print('GC47BC_PROFILE='+args.job_id+' SOURCE=EXACT_BB_JSX_SHA_BOUND',flush=True)
        if args.mode=='inspect':
            readonly_preflight(data);return 0
        if args.mode=='pilot':return pilot(data,args.timeout_minutes)
        return status_or_collect(data,args.attempt_id,collect=args.mode=='collect')
    except Exception as exc:
        label=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC47BC=BLOCKED_'+re.sub('[^A-Z0-9_]', '_',label.upper())[:100],file=sys.stderr)
        print('GC47BC_NO_NATIVE_RETRY=TRUE NO_TASKKILL=TRUE QUEUE_ENABLED=FALSE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
