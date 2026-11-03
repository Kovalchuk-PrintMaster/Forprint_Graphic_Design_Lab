#!/usr/bin/env python3
"""GC47AZ: source-bound FOUR-job, no-native scene/queue/recovery checkpoint.

Zero native dispatch, zero creation of client attempts, no client writes.
A report is explicitly bounded/sanitized; full greeting text and logo bytes stay
in memory, never in the output JSON. Existing ZAP GC47AX remains unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPECTED_HEAD = '83cefbef5d85ee2dfd28ced33e2a237ee78b67cb'
ARCHIVE_SHA = '90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
JOBS = (
 ('gdl_gc_zap_20261011','STANDARD','GRIGO'),
 ('gdl_gc_apa_20261011','STANDARD','GRIGO'),
 ('gdl_gc_deg_20261011','STANDARD','HERASYMENKO'),
 ('gdl_gc_bas_20261011','RECIPIENT_BRANDING_OVERLAY','HERASYMENKO'),
)
# Source hashes from GC47AW + GC47AX, reviewed again against GC47AY freeze.
PINS = {
 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py':'c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42',
 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.jsx':'96b0549cc21cc82f35e1648e16f4ee25cb88fd8d9333c1ad6a38b16c9b306955',
 'scripts/graphic_design_lab/greeting_cards/gc47s_client_pilot_v0_1.py':'556e46a041885b7ff84768e51df63037c04a78a7babab37484b4a3abef815362',
 'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py':'c99fde8a5f5805da57b5cca037cda17a34dea002a076042279bd274c4848ef46',
 'scripts/graphic_design_lab/greeting_cards/gc47ax_client_windows_bridge_r001.py':'9759fdac6d166bcbca4331d1881d0022917c8c0e33493fac2e4c4d50283a98bc',
 'scripts/graphic_design_lab/greeting_cards/gc47ax_illustrator_lifecycle_r001.py':'7da40974a4d2dcc26d3f11447fd1d40ee6300fd3104480d487fe4f34fccfd2d9',
 'scripts/graphic_design_lab/greeting_cards/gc47ax_postflight_r001.py':'f2e5e2636fc88622f861998d426b919e12678728514adac0992b5803fe3cd5c3',
 'scripts/graphic_design_lab/greeting_cards/gc47ax_versioned_native_pilot_r001.py':'7919ce9f770ee05cc979065434b7fabe1538f2c1adb7e07cd71ae781c9bd8998',
 'coordination/graphic_design_lab/greeting_cards/baselines/gc47aq_shadow_binding_zap_r001.json':'60c6eee5081cb4e77ce948a4e0731d320351b81648151be09bb2a28a4d659bb6',
}

class Blocked(ValueError): pass

def need(ok, code):
    if not ok:raise Blocked(code)

def sha_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for v in iter(lambda:f.read(1024*1024),b''): h.update(v)
    return h.hexdigest()

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False

def canonical_json(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')

def run_git(root,*args):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=30,check=False)
    need(p.returncode==0,'GIT_'+args[0].upper()+'_FAILED')
    return p.stdout.strip()

def pinned_sources(root=ROOT, require_head=True):
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPOSITORY_REQUIRED')
    if require_head:
        need(run_git(root,'rev-parse','HEAD')==EXPECTED_HEAD,'GIT_HEAD_CHANGED_NEEDS_REVIEW')
        need(run_git(root,'rev-parse','origin/main')==EXPECTED_HEAD,'ORIGIN_MAIN_CHANGED_NEEDS_REVIEW')
    for rel,exp in PINS.items():
        f=root/rel
        need(regular(f) and f.stat().st_size<=1_000_000,'PINNED_FILE_MISSING_OR_UNSAFE_'+f.name)
        need(sha_file(f)==exp,'PINNED_SOURCE_SHA_CHANGED_'+f.name)
    return {'status':'PASS_FROZEN_SOURCE_PINS', 'pin_count':len(PINS),
            'git_head_expected':EXPECTED_HEAD,'accepted_zip_sha256':ARCHIVE_SHA}

def module(root,filename,key):
    path=root/'scripts/graphic_design_lab/greeting_cards'/filename
    need(regular(path),'SOURCE_NOT_REGULAR_'+filename)
    spec=importlib.util.spec_from_file_location(key,path)
    need(spec is not None and spec.loader is not None,'MODULE_IMPORT_'+filename)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def logo_from_accepted(job, artifacts, archive):
    """Read only the exact accepted BAS logo from immutable ZIP; never extract."""
    b=job['builder_v1']['front']
    if b['family']!='RECIPIENT_BRANDING_OVERLAY':return None
    info=b['recipient_branding']; ref=info['accepted_artifact_ref']
    item=artifacts['artifacts'][ref]
    expected=info['asset_sha256']
    need(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected),'BRANDING_SHA_BAD')
    need(item['sha256']==expected,'BRANDING_SOURCE_BINDING')
    member=item.get('path') or item.get('archive_member')
    need(isinstance(member,str) and not member.startswith('/') and
         '..' not in member.split('/') and '\\' not in member,'BRANDING_ARCHIVE_MEMBER_UNSAFE')
    with zipfile.ZipFile(archive) as z:
        need(z.testzip() is None,'ACCEPTED_CRC')
        need(len(z.namelist())==len(set(z.namelist())),'ACCEPTED_DUPLICATES')
        need(member in z.namelist(),'BRANDING_MEMBER_MISSING')
        i=z.getinfo(member)
        need(0<i.file_size<=10_000_000,'BRANDING_MEMBER_SIZE')
        raw=z.read(i)
    need(hashlib.sha256(raw).hexdigest()==expected,'BRANDING_CONTENT_SHA_CHANGED')
    return raw

def scene_summary(job, scene, variant, generated, logo_present):
    need(scene.get('schema_version')=='gdl_gc29_native_scene_v0_1','SCENE_SCHEMA')
    need(scene['job_id']==job['job_id'] and scene['pages']==4,'SCENE_ID_OR_PAGES')
    need(scene['image_mode']=='DEFAULT_ASSET' and scene['family']==variant['front'] and
         scene['signature']==variant['signature'],'SCENE_VARIANT')
    roles=[x['role'] for x in scene['layers']]
    need(len(roles)==len(set(roles)),'DUPLICATE_SCENE_ROLES')
    need('P03.FRAME' in roles and 'P04.SIGNATURE' in roles,'SCENE_REQUIRED_LAYERS')
    need(('P01.RECIPIENT_BRANDING' in roles)==logo_present,'BRANDING_ROLE_MISMATCH')
    need(scene['visual_approved'] is False and scene['production_ready'] is False,'SCENE_AUTHORITY')
    sender=scene['sender_lines']
    need(isinstance(sender,list) and len(sender) in (3,4),'SENDER_ROWS')
    need(all(isinstance(x,str) and len(x)>0 for x in sender),'SENDER_CONTENT')
    warnings=['GC47AR_IS_ZAP_ONLY','P04_NATIVE_TEXT_FIT_NOT_REVIEWED',
              'P03_VISUAL_CROP_REQUIRES_REVIEW','FOUR_PAGE_VISUAL_APPROVAL_ABSENT']
    if variant['signature']=='HERASYMENKO':warnings.append('HERASYMENKO_SENDER_GEOMETRY_NEEDS_VARIANT_PROOF')
    if logo_present:warnings.append('BAS_RECIPIENT_BRANDING_VISUAL_REVIEW')
    return {'job_id':job['job_id'], 'variant':variant,'pages':4,
            'layer_roles':roles,'sender_row_count':len(sender),
            'sender_max_chars':max(len(x) for x in sender),
            'greeting_chars':len(scene['greeting_text']),
            'generated_signature_asset_names':sorted(generated),
            'accepted_branding_present':logo_present,
            'status':'SHADOW_COMPILED_NO_NATIVE', 'native_authorized':False,
            'visual_approved':False,'production_ready':False,
            'remaining_gates':warnings}

def queue_plan(summaries):
    ids=[x['job_id'] for x in summaries]
    need(ids==[x[0] for x in JOBS],'JOB_ORDER_OR_SET_CHANGED')
    return {'schema_version':'gdl_gc47az_bounded_queue_plan_r001',
        'mode':'PLAN_ONLY_NO_DISPATCH', 'accepted_zip_sha256':ARCHIVE_SHA,
        'one_illustrator_at_a_time':True,'automatic_retry':False,
        'queue_execution_enabled':False,'visual_approved':False,'production_ready':False,
        'stop_on':['PROFILE_NOT_SHADOW_PROVEN','EXPLICIT_ITEM_AUTHORITY_MISSING',
                   'ILLUSTRATOR_SESSION_UNAVAILABLE','NATIVE_STATE_UNCERTAIN',
                   'OUTPUT_PUBLICATION_NOT_VERIFIED','POSTFLIGHT_CLOSE_NOT_VERIFIED'],
        'items':[{'position':i+1,'job_id':x['job_id'],
                  'profile':x['variant'],
                  'state':('EXISTING_ZAP_SINGLE_USE_ONLY' if i==0 else 'BLOCKED_NATIVE_PROFILE_PROOF_REQUIRED'),
                  'queue_authorized':False} for i,x in enumerate(summaries)]}

def simulate_queue(plan, outcomes):
    """Pure control-plane model. Always fail closed, never calls native code."""
    need(plan['mode']=='PLAN_ONLY_NO_DISPATCH' and plan['queue_execution_enabled'] is False,
         'ACTIVE_QUEUE_NOT_SUPPORTED')
    history=[]
    for item in plan['items']:
        k=item['job_id'];e=outcomes.get(k)
        if e is None or not e.get('explicit_item_authority') or not e.get('shadow_proven'):
            history.append({'job_id':k,'state':'HALTED_UNAUTHORIZED_OR_UNPROVEN'});break
        if e.get('native_status')!='PUBLISHED_VERIFIED':
            history.append({'job_id':k,'state':'HALTED_NATIVE_UNCERTAIN_NO_RETRY'});break
        if e.get('postflight')!='CLOSED_VERIFIED':
            history.append({'job_id':k,'state':'HALTED_POSTFLIGHT_UNVERIFIED'});break
        history.append({'job_id':k,'state':'MODEL_PASS_NOT_A_LIVE_ATTEMPT'})
    return {'model_only':True,'native_invocations':0,'history':history,
            'next_job_auto_started':False}

def recovery_audit(root, ws, archive):
    required=list(PINS)
    tracked={r:run_git(root,'ls-files','--error-unmatch','--',r)==r for r in required}
    needed_dirs=['template_studio/native_asset_vault_v0_1',
                 'template_studio/native_runs','template_studio/greeting_card_pilots','input','output']
    external={p:directory(ws/p) for p in needed_dirs}
    # Recovery cannot be claimed merely because the files exist now.
    return {'schema_version':'gdl_gc47az_recovery_inventory_r001',
       'pinned_repo_sources_tracked':tracked,'tracked_count':sum(tracked.values()),
       'tracked_expected':len(required),'private_workspace_directories_present':external,
       'accepted_zip_sha256':sha_file(archive),
       'dependencies_on_tmp_in_new_gc47az_runtime':False,
       'clean_redeploy_verified':False,
       'windows_gui_restore_verified':False,
       'external_vault_restore_verified':False,
       'checkpoint':'SOURCE_INVENTORY_ONLY_NOT_DISASTER_RECOVERY_PROOF'}

def inspect(client,root=ROOT):
    src=pinned_sources(root)
    t=module(root,'gc47t_client_windows_bridge_r001.py','gc47az_pinned_gc47t')
    # Deeper source_check validates GC47S, GC29, GC47K, AF/Y and transport.
    s,gc29=t.source_check()
    ws=s.workspace(client)
    jobs,artifacts,archive=gc29.accepted_jobs(ws)
    need(regular(archive) and sha_file(archive)==ARCHIVE_SHA,'ACCEPTED_INPUT_CHANGED')
    need(len(jobs)==len(JOBS),'ACCEPTED_JOB_COUNT_CHANGED')
    need([j.get('job_id') for j in jobs]==[x[0] for x in JOBS],'ACCEPTED_JOB_ORDER_CHANGED')
    catalog=gc29.verify_vault(ws/'template_studio/native_asset_vault_v0_1')
    summaries=[]
    for job, expected in zip(jobs,JOBS):
        variant,supported=s.classify(job)
        need(supported,'RENDERER_VARIANT_NOT_SUPPORTED_'+expected[0])
        need(variant=={'front':expected[1],'image':'DEFAULT_ASSET','signature':expected[2]},
             'JOB_VARIANT_DRIFT_'+expected[0])
        logo=logo_from_accepted(job,artifacts,archive)
        scene=gc29.compile_scene(job,catalog,logo)
        generated=gc29.bind_illustrator_signature(scene,ws/'template_studio/native_asset_vault_v0_1',catalog)
        summaries.append(scene_summary(job,scene,variant,generated,logo is not None))
    return {'schema_version':'gdl_gc47az_four_profile_shadow_r001',
            'status':'PASS_FOUR_PROFILE_SOURCE_BOUND_NON_NATIVE',
            'source':src,'jobs':summaries, 'queue_plan':queue_plan(summaries),
            'queue_simulation':simulate_queue(queue_plan(summaries),{}),
            'recovery':recovery_audit(root,ws,archive),
            'client_content_exported':False,'windows_contacted':False,
            'client_files_modified':False,'attempts_created':False,
            'visual_approved':False,'production_ready':False}

def write_report(report,out,root=ROOT):
    """Disposable evidence under repo tmp; not required by runtime."""
    tmp=root/'tmp'
    need(directory(tmp) and not tmp.is_symlink(),'TMP_DELIVERY_DIR_MISSING')
    need(out.parent.resolve(strict=True)==tmp.resolve(strict=True),'REPORT_MUST_BE_PRIVATE_GDL_TMP')
    need(re.fullmatch(r'gc47az_multi_profile_evidence_[a-z0-9_-]{1,48}\.zip',out.name) is not None,'REPORT_NAME')
    need(not out.exists() and not out.is_symlink(),'REPORT_EXISTS')
    data=canonical_json(report)
    need(len(data)<400_000,'REPORT_SIZE')
    with out.open('xb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,obj in (('REPORT.json',report),('QUEUE_PLAN.json',report['queue_plan']),
                             ('RECOVERY_INVENTORY.json',report['recovery'])):
                zi=zipfile.ZipInfo(name);zi.external_attr=(0o100600<<16)
                zi.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(zi,canonical_json(obj))
    os.chmod(out,0o600)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None,'REPORT_ZIP_CRC')
    return sha_file(out)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','inspect'),required=True)
    p.add_argument('--client-name')
    p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    try:
        if a.mode=='check':
            r=pinned_sources()
            print('GC47AZ_PINS='+r['status'])
            print('GC47AZ_NO_SSH_NO_NATIVE_NO_CLIENT_MUTATION=TRUE')
            return 0
        need(a.client_name and a.output is not None,'CLIENT_AND_OUTPUT_REQUIRED')
        result=inspect(a.client_name)
        digest=write_report(result,a.output)
        print('GC47AZ_PROFILES=PASS_FOUR_SOURCE_BOUND_SHADOWS_NO_NATIVE')
        for j in result['jobs']:
            print('GC47AZ_JOB='+j['job_id']+' SIGNATURE='+j['variant']['signature']+
                  ' SENDER_ROWS='+str(j['sender_row_count'])+' STATE='+j['status'])
        print('GC47AZ_QUEUE=PLAN_ONLY_BLOCKED_NO_DISPATCH')
        print('GC47AZ_RECOVERY=INVENTORY_ONLY_CLEAN_DEPLOY_NOT_TESTED')
        print('GC47AZ_EVIDENCE='+str(a.output))
        print('GC47AZ_EVIDENCE_SHA256='+digest)
        print('GC47AZ_NATIVE_DISPATCH=FALSE CLIENT_MUTATION=FALSE GIT_MUTATION=FALSE')
        return 0
    except (Blocked,ValueError,KeyError,TypeError,OSError,ImportError,subprocess.TimeoutExpired,
            json.JSONDecodeError,zipfile.BadZipFile) as e:
        code=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47AZ=BLOCKED_'+re.sub('[^A-Z0-9_]', '_', code.upper())[:100],file=sys.stderr)
        print('GC47AZ_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
