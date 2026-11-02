#!/usr/bin/env python3
"""GC47AX: explicit, single-use, versioned GC47K Illustrator review pilot.

Never replaces GC47T, GC47K, GC47AQ or the Windows client launcher.
Check/preflight modes do not allocate attempts. Pilot runs a *new* GC47S
attempt using the GC47AQ/GC47AP bound scene, then delegates the existing
GC47T PREPRESS transport, controller and verified GC47S review collection.
No automatic retries or production approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
AQ_NAME='gc47aq_shadow_integration_r001.py'
SHADOW_REL='coordination/graphic_design_lab/greeting_cards/baselines/gc47aq_shadow_binding_zap_r001.json'
SHADOW_SHA='60c6eee5081cb4e77ce948a4e0731d320351b81648151be09bb2a28a4d659bb6'
JOB='gdl_gc_zap_20261011'
EXPECTED_ACCEPTED='90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
REVIEW_BIND='gc47ar_versioned_review_binding_r001.json'
SCHEMA='gdl_gc47ar_versioned_native_review_r001'

class Blocked(ValueError):pass

def require(v, code):
    if not v:raise Blocked('GC47AR_'+code)

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def safe_load(p,key):
    import importlib.util
    require(regular(p),'MISSING_'+p.name)
    spec=importlib.util.spec_from_file_location(key,p)
    require(spec is not None and spec.loader is not None,'IMPORT_'+key)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def read_report(path,root=ROOT):
    exact=root/SHADOW_REL
    require(path == exact,'SHADOW_PATH_MUST_BE_CANONICAL')
    require(regular(path) and path.stat().st_size<10000,'SHADOW_REPORT_MISSING_OR_UNSAFE')
    require(sha(path)==SHADOW_SHA,'SHADOW_REPORT_SHA_DRIFT')
    r=json.loads(path.read_text('utf8'))
    require(r.get('schema_version')=='gdl_gc47aq_shadow_binding_r001' and
            r.get('status')=='PASS_REAL_ACCEPTED_INPUT_SHADOW_ONLY', 'SHADOW_REPORT_STATUS')
    require(r.get('job_id')==JOB and r.get('accepted_zip_sha256')==EXPECTED_ACCEPTED,'SHADOW_INPUT_CHANGED')
    require(r.get('native_attempt_created') is False and r.get('windows_contacted') is False and
            r.get('runtime_activation') is False and r.get('production_ready') is False and
            r.get('visual_approved') is False and r.get('dual_runtime_enabled') is False,
            'SHADOW_AUTHORITY_CHANGED')
    require(r.get('proposed_fields')==[] and r.get('render',{}).get('P04',{}).get('live_row_count')==4,
            'SHADOW_NON_BASELINE')
    require(r.get('pages')==4 and r.get('variant')=={'family':'STANDARD','image_mode':'DEFAULT_ASSET','signature':'GRIGO'},
            'SHADOW_VARIANT')
    return r

def sources(root=ROOT,can=CAN):
    require(root.name=='forprint_graphic_design_lab' and (root/'.git').is_dir(), 'GDL_ROOT')
    aq=safe_load(can/AQ_NAME,'gc47ar_pinned_shadow')
    ap,baseline,proposal=aq.gate(root,can)
    require(proposal['requested_changes']=={} and proposal['authority']['runtime_activation'] is False and
            proposal['authority']['native_execution_allowed'] is False,'CANDIDATE_NOT_BASELINE')
    t=safe_load(can/'gc47t_client_windows_bridge_r001.py','gc47ar_pinned_gc47t')
    y=safe_load(can/'gc47y_review_amendment_r001.py','gc47ar_pinned_gc47y')
    s,gc29=t.source_check()
    require(t.sha_file(can/'gc47t_client_windows_bridge_r001.py')==aq.GC47T_SHA,'GC47T_PIN_CHANGED')
    require(t.GC47T==can/'gc47t_client_windows_bridge_r001.py','GC47T_PATH')
    require(t.GC47AC_TRANSPORT_SHA=='fb53ef3accdc05758b9e836c8683784d8b0e10e179ebfa84066a95c1f29b8dab',
            'TRANSPORT_PIN')
    return aq,ap,baseline,proposal,t,y,s,gc29

def verify_shadow_and_job(client,root=ROOT,can=CAN):
    aq,ap,baseline,proposal,t,y,s,gc29=sources(root,can)
    r=read_report(root/SHADOW_REL,root)
    require(r['template_jsx_sha256']==aq.JSX_SHA and
            r['candidate_baseline_profile_sha256']==aq.PRO_SHA,'SHADOW_CANDIDATE_DRIFT')
    current=aq.run_shadow(root,can,client,JOB)
    require(current['compiled_jsx_sha256']==r['compiled_jsx_sha256'] and
            current['accepted_zip_sha256']==r['accepted_zip_sha256'] and
            current['effective_proposal_sha256']==r['effective_proposal_sha256'],
            'CURRENT_SCENE_NOT_SHADOW_EQUIVALENT')
    ws,job,archive,variants=t.validate_job(s,gc29,client,JOB)
    require(t.sha_file(archive)==EXPECTED_ACCEPTED,'ACCEPTED_ARCHIVE_DRIFT')
    require(variants=={'front':'STANDARD','image':'DEFAULT_ASSET','signature':'GRIGO'},'VARIANT_SCOPE')
    y.check_sources(ws,job,archive)
    return aq,ap,baseline,proposal,t,y,s,gc29,ws,job,archive,r

def prepare_versioned(s,gc29,ap,baseline,proposal,t,y,ws,job,archive,expected_hash):
    """One immutable GC47S attempt. Everything prior to this must be non-mutating."""
    original_compile=gc29.compile_scene
    original_prepare=gc29.prepare
    original_template=gc29.TEMPLATE
    original_amend=y.amend_scene
    reg=s.read_obj(s.REGISTRY,5_000_000)['greeting_card_machine_pipeline_v0_1']
    need_template=CAN/'gc29_native_four_page_gc47aq_candidate_r001.jsx'
    require(regular(need_template) and t.sha_file(need_template)==
            'a9c0692849aa5c850993d0f943031c59559c923fd64ac257f6b1c18d972fd63a',
            'CANDIDATE_JSX_DRIFT')
    def versioned_amend(scene):
        return ap.transform_scene(original_amend(scene),baseline,proposal)
    try:
        gc29.TEMPLATE=need_template
        gc29.compile_scene=t.gc47af_mod().wrap_compile(original_compile,reg,JOB)
        y.amend_scene=versioned_amend
        gc29.prepare=y.wrap_prepare(gc29,original_prepare,ws,job,archive)
        _,passport=s.current_passport()
        outcome=s.start_one(gc29,ws,job,archive,passport)
    finally:
        gc29.TEMPLATE=original_template
        gc29.compile_scene=original_compile
        gc29.prepare=original_prepare
        y.amend_scene=original_amend
    require(outcome is not None and outcome.get('state')=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED',
            'NEW_ATTEMPT_PREPARE_NOT_READY_NO_RETRY')
    attempt=outcome['attempt']
    base=s.pilot_dir(ws,JOB,attempt)
    run=s.native_run_dir(ws,JOB,attempt)
    state=s.read_obj(base/'state.json')
    scene=s.read_obj(run/'scene_manifest.json')
    require(state.get('native_jsx_sha256')==expected_hash and t.sha_file(run/t.JSX)==expected_hash,
            'VERSIONED_JSX_SHA_DOES_NOT_MATCH_SHADOW_NO_RETRY')
    require(scene.get('gc47ap_proposal')=={'schema_version':'gdl_gc47ap_parametric_candidate_r001',
            'runtime_activation':False,'visual_approved':False,'production_ready':False},
            'CANDIDATE_SCENE_PROVENANCE')
    require(scene.get('gc47y_source_receipt',{}).get('photo_sha256')==y.FLOWER_NEW,
            'PHOTO_SOURCE_RECEIPT')
    require(scene.get('asset_sha256',{}).get('p03_flowers.png')==y.FLOWER_NEW,
            'PHOTO_SHA_SOURCE')
    require(scene.get('pages')==4 and scene.get('job_id')==JOB and scene.get('signature')=='GRIGO',
            'SCENE_VARIANT_CHANGED')
    binding={'schema_version':SCHEMA,'attempt_id':attempt,'job_id':JOB,
         'accepted_zip_sha256':EXPECTED_ACCEPTED,'compiled_jsx_sha256':expected_hash,
         'candidate_jsx_sha256':'a9c0692849aa5c850993d0f943031c59559c923fd64ac257f6b1c18d972fd63a',
         'shadow_report_sha256':SHADOW_SHA,'production_ready':False,
         'visual_approved':False,'dual_runtime_enabled':False,'automatic_retry':False,
         'route':'VERSIONED_ILLUSTRATOR_SINGLE_USE_REVIEW_ONLY'}
    # The sidecar is created in this attempt ONLY. Never overwritten/rebuilt by status/collect.
    s.write_json_x(base/REVIEW_BIND,binding)
    return attempt

def require_versioned_attempt(s,ws,attempt):
    require(bool(s.ID_RE.fullmatch(attempt)),'ATTEMPT_ID_INVALID')
    base=s.pilot_dir(ws,JOB,attempt)
    b=s.read_obj(base/REVIEW_BIND)
    require(b.get('schema_version')==SCHEMA and b.get('attempt_id')==attempt and b.get('job_id')==JOB,
            'VERSIONED_BINDING_MISSING')
    require(b.get('shadow_report_sha256')==SHADOW_SHA and b.get('accepted_zip_sha256')==EXPECTED_ACCEPTED and
            b.get('route')=='VERSIONED_ILLUSTRATOR_SINGLE_USE_REVIEW_ONLY' and
            b.get('production_ready') is False and b.get('visual_approved') is False and
            b.get('dual_runtime_enabled') is False and b.get('automatic_retry') is False,
            'VERSIONED_BINDING_AUTHORITY')
    state=s.read_obj(base/'state.json')
    run=s.native_run_dir(ws,JOB,attempt)
    require(state.get('attempt_id')==attempt and state.get('job_id')==JOB and
            state.get('state')=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED' and
            state.get('native_jsx_sha256')==b.get('compiled_jsx_sha256')==sha(run/'run_in_illustrator.jsx'),
            'ATTEMPT_JSX_OR_STATE_DRIFT')
    return b

def run_pilot(data,timeout_minutes):
    aq,ap,baseline,proposal,t,y,s,gc29,ws,job,archive,report=data
    # BEFORE attempt allocation: exact job/source/sha, known-host credentials,
    # work-session readiness, and the original GC47T transport prerequisites.
    t.ssh_options()
    t.windows_preflight()
    attempt=prepare_versioned(s,gc29,ap,baseline,proposal,t,y,ws,job,archive,report['compiled_jsx_sha256'])
    print('GC47AR_JOB='+JOB+' ATTEMPT='+attempt+' STATE=PREPARED',flush=True)
    print('GC47AR_NO_AUTO_RETRY=TRUE; ON FAILURE USE STATUS/COLLECT ONLY',flush=True)
    bundle=t.make_transport(s,ws,JOB,attempt)
    t.stage_remote(bundle,attempt)
    result=t.kv_output(t.controller_command(attempt,'launch'))
    require(result.get('T1_LAUNCH')=='START_REQUESTED_SINGLE_USE','LAUNCH_NOT_ATTESTED_NO_RETRY')
    print('GC47AR_LAUNCH=START_REQUESTED_SINGLE_USE',flush=True)
    start=time.monotonic()
    while time.monotonic()-start < timeout_minutes*60:
        status=t.status_remote(attempt)
        if status['T1_NATIVE_STATE']=='AI_REOPENED_VISUAL_REVIEW_REQUIRED':
            t.collect_remote(s,ws,JOB,attempt)
            print('GC47AR_CHECKPOINT=VERSIONED_NATIVE_REVIEW_READY_VISUAL_APPROVAL_REQUIRED',flush=True)
            return
        if status['T1_NATIVE_STATE']=='BLOCKED_REVIEW_PARTIAL_OUTPUT':
            raise Blocked('WINDOWS_PARTIAL_OUTPUT_STATUS_ONLY_DO_NOT_RELAUNCH')
        time.sleep(10)
    raise Blocked('PENDING_CHECK_STATUS_DO_NOT_RELAUNCH')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('check','preflight','pilot','status','collect'))
    p.add_argument('--client-name');p.add_argument('--job-id',default=JOB)
    p.add_argument('--attempt-id');p.add_argument('--timeout-minutes',type=int,default=24)
    p.add_argument('--confirm-native-once',action='store_true')
    p.add_argument('--confirmation')
    a=p.parse_args(argv)
    try:
        require(a.job_id==JOB,'JOB_NOT_SUPPORTED')
        if a.mode=='check':
            sources()
            read_report(ROOT/SHADOW_REL)
            print('GC47AR_CHECK=PASS_PINNED_CANDIDATE_SHADOW_SOURCE_NO_NATIVE')
        elif a.mode in ('preflight','pilot'):
            require(bool(a.client_name),'CLIENT_REQUIRED')
            if a.mode=='pilot':
                require(a.confirm_native_once and a.confirmation=='GC47AR_SINGLE_NATIVE_REVIEW',
                        'EXPLICIT_OPERATOR_NATIVE_AUTHORITY_REQUIRED')
                require(1<=a.timeout_minutes<=30,'TIMEOUT_OUT_OF_RANGE')
            data=verify_shadow_and_job(a.client_name)
            print('GC47AR_SHADOW=PASS_RECOMPILED_JSX_SHA_MATCH')
            data[4].ssh_options();data[4].windows_preflight()
            print('GC47AR_PREFLIGHT=PASS_SOURCE_JOB_GUI_NO_ATTEMPT')
            if a.mode=='pilot':
                # Recheck remote at the exact handoff boundary; it may have changed.
                run_pilot(data,a.timeout_minutes)
        else:
            require(a.client_name and a.attempt_id,'CLIENT_AND_ATTEMPT_REQUIRED')
            require(a.mode!='collect' or (a.confirm_native_once and a.confirmation=='GC47AR_COLLECT_REVIEW'),
                    'COLLECT_EXPLICIT_CONFIRMATION_REQUIRED')
            aq,ap,base,proposal,t,y,s,gc29=sources()
            ws=s.workspace(a.client_name)
            require_versioned_attempt(s,ws,a.attempt_id)
            if a.mode=='status':t.mode_status(s,a.client_name,JOB,a.attempt_id)
            else:t.collect_remote(s,ws,JOB,a.attempt_id)
        print('GC47AR_PRODUCTION_READY=FALSE VISUAL_APPROVED=FALSE DUAL_RUNTIME=DISABLED')
        return 0
    except (Blocked,ValueError,OSError,KeyError,TypeError,TimeoutError,ImportError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired,json.JSONDecodeError) as e:
        print('GC47AR=BLOCKED_'+str(e),file=sys.stderr)
        print('GC47AR_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
