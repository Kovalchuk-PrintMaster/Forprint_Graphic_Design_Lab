#!/usr/bin/env python3
"""GC47BI: immutable-source ZAP scene crosswalk against last live successful attempt.

Read only for client, PREPRESS, Git, and shared design. Writes metadata-only evidence ZIP
in disposable repo/tmp, no rendering, Windows contact, changes to canonical scene or activation.
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
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
BF_NAME='gc47bf_shared_scene_stage_parity_r001.py'
BF_SHA='d5a5b58b6778885288c1fdfc31e626fbe98a5b9b6c47fa9a3bc86521564639e1'
JOB='gdl_gc_zap_20261011'
ATTEMPT='p20261102115307-e7858645'
ACCEPTED='90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
RELEASE='efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83'
PHOTO_SHA='8d909fd3edb629e2ee2ac2fe4ee83726ba144f63b8e9f48945d963743d9cb637'
OUTPUT_NAME='gc47bi_zap_native_scene_crosswalk_evidence_r001.zip'
REVIEW_FILES={'design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png'}
SHA_RE=re.compile(r'^[a-f0-9]{64}$')
SAFE_NAME=re.compile(r'^[a-zA-Z0-9_.-]{1,96}$')

class Blocked(RuntimeError):pass

def need(ok,reason):
    if not ok: raise Blocked(reason)

def regular(p):
    try:return stat.S_ISREG(Path(p).lstat().st_mode)
    except OSError:return False

def directory(p):
    try:return stat.S_ISDIR(Path(p).lstat().st_mode) and not Path(p).is_symlink()
    except OSError:return False

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def safe_json(path,limit=4_000_000):
    p=Path(path)
    need(regular(p) and 0<p.stat().st_size<limit,'UNSAFE_OR_MISSING_JSON_'+p.name)
    val=json.loads(p.read_text('utf-8'))
    need(isinstance(val,dict),'JSON_OBJECT_REQUIRED_'+p.name)
    return val

def load_bf(root=ROOT):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPO_REQUIRED')
    source=root/'scripts/graphic_design_lab/greeting_cards'/BF_NAME
    need(regular(source) and sha(source)==BF_SHA,'FROZEN_BF_SOURCE_SHA_CHANGED')
    spec=importlib.util.spec_from_file_location('gc47bi_bound_bf',source)
    need(spec is not None and spec.loader is not None,'BF_IMPORT_SPEC')
    bf=importlib.util.module_from_spec(spec);spec.loader.exec_module(bf)
    bf.pins(root)
    return bf

def receipt_checks(review):
    """No arbitrary paths or unlisted read; SHA256SUMS verification is full and exact."""
    review=Path(review)
    need(directory(review),'PUBLISHED_REVIEW_MISSING')
    f=review/'SHA256SUMS'
    need(regular(f) and f.stat().st_size<=16_384,'REVIEW_SHA_LEDGER_MISSING')
    table={}
    for raw in f.read_text('ascii').splitlines():
        m=re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9_.-]{1,96})',raw)
        need(m is not None,'REVIEW_SHA_LEDGER_FORMAT')
        wanted,name=m.groups()
        need(name not in table,'REVIEW_SHA_DUPLICATE')
        table[name]=wanted
    need(REVIEW_FILES.issubset(table),'REVIEW_OUTPUT_REQUIRED_FILES')
    for name,digest in table.items():
        path=review/name
        need(regular(path) and sha(path)==digest,'REVIEW_SHA_MISMATCH_'+name)
    return {'verified_file_count':len(table),'required_six_output_files':True,
            'review_sha256sums_sha256':sha(f)}

def compare_role_map(legacy,ledger):
    """Compare reference native manifest against canonical shared stage ledger.

    Only role names, SHA and bbox leave this function; no texts or asset bytes.
    """
    need(legacy.get('job_id')==JOB and legacy.get('pages')==4,'REFERENCE_JOB_OR_PAGES')
    need(legacy.get('visual_approved') is False and legacy.get('production_ready') is False,'REFERENCE_AUTHORITY')
    need(isinstance(legacy.get('asset_sha256'),dict),'REFERENCE_ASSET_DIGESTS_MISSING')
    layers=legacy.get('layers');need(isinstance(layers,list),'REFERENCE_LAYERS_MISSING')
    by_role={p.get('role'):p for p in layers if isinstance(p,dict)}
    need(len(by_role)==len(layers),'REFERENCE_DUPLICATE_LAYER_ROLE')
    need(isinstance(ledger,list) and len(ledger)==12,'STAGE_LEDGER_SIZE')
    stage={p['role']:p for p in ledger}
    need(len(stage)==12 and len({p['asset_name'] for p in ledger})==12,'STAGE_ROLE_OR_FILE_COLLISION')
    need(sum(p['source']=='COMMON_DURABLE_RELEASE' for p in ledger)==10,'TEN_COMMON_ROLES_REQUIRED')
    mismatches=[]; matched=[]
    for role,expected in sorted(stage.items()):
        name=expected['asset_name']; src=by_role.get(role)
        if src is None:
            mismatches.append({'role':role,'field':'missing_in_reference'});continue
        srcpath=src.get('file')
        if srcpath!='assets/'+name:
            mismatches.append({'role':role,'field':'asset_file'})
        want=expected['sha256']
        if legacy['asset_sha256'].get(name)!=want:
            mismatches.append({'role':role,'field':'sha256'})
        actual=src.get('bbox_mm');target=expected.get('bbox_mm')
        if (not isinstance(actual,list) or not isinstance(target,list) or len(actual)!=4 or len(target)!=4 or
            any(not isinstance(a,(int,float)) or isinstance(a,bool) or abs(float(a)-float(b))>0.00001
                for a,b in zip(actual,target))):
            mismatches.append({'role':role,'field':'bbox_mm'})
        if not any(k['role']==role for k in mismatches):matched.append(role)
    extras=sorted(set(by_role)-set(stage))
    for role in extras: mismatches.append({'role':role,'field':'reference_extra_role'})
    need(stage['P03.FLOWERS']['source']=='JOB_OVERRIDE' and
         stage['P03.FLOWERS']['sha256']==PHOTO_SHA,'ZAP_JOB_PHOTO_OVERRIDE_REQUIRED')
    need(stage['P04.SIGNATURE']['source']=='DERIVED_FROM_COMMON_SVG','GRIGO_SOURCE_PROVENANCE')
    return {'shared_roles':10,'variable_roles':2,'matched_role_count':len(matched),
            'mismatch_count':len(mismatches),'mismatches':mismatches,
            'role_metadata_parity':'MATCH' if not mismatches else 'DIFFERENCES_REVIEW_REQUIRED',
            'client_text_exported':False,'asset_payload_exported':False}

def analyse(root,client,attempt=ATTEMPT):
    need(attempt==ATTEMPT,'REFERENCE_ATTEMPT_MUST_BE_FROZEN')
    bf=load_bf(root)
    source=bf.inspect(root,client)
    need(source.get('status')=='PASS_FOUR_PROFILE_SHARED_STAGE_SOURCE_PARITY_NO_NATIVE','BF_SOURCE_PARITY')
    need(source.get('shared_release_id')==RELEASE and source.get('accepted_zip_sha256')==ACCEPTED,
         'RELEASE_OR_ACCEPTED_SOURCE_CHANGED')
    profiles={p['job_id']:p for p in source['profiles']}
    need(len(profiles)==4 and JOB in profiles,'FOUR_PROFILE_PROVENANCE')
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    az=bb.az_module(root)
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bi_bound_transport')
    s,gc29=t.source_check()
    ws=s.workspace(client)
    base=s.pilot_dir(ws,JOB,attempt)
    run=s.native_run_dir(ws,JOB,attempt)
    review=s.review_dir(ws,JOB,attempt)
    state=safe_json(base/'state.json')
    need(state.get('attempt_id')==attempt and state.get('job_id')==JOB and
         state.get('accepted_zip_sha256')==ACCEPTED,'REFERENCE_STATE_IDENTITY')
    jsx=run/'run_in_illustrator.jsx'
    need(regular(jsx) and sha(jsx)==state.get('native_jsx_sha256'),'REFERENCE_JSX_STATE_SHA')
    legacy=safe_json(run/'scene_manifest.json')
    receipt=legacy.get('gc47y_source_receipt')
    need(isinstance(receipt,dict) and receipt.get('photo_sha256')==PHOTO_SHA and
         receipt.get('accepted_zip_sha256')==ACCEPTED,'REFERENCE_GC47Y_PHOTO_BINDING')
    review_data=receipt_checks(review)
    cross=compare_role_map(legacy,profiles[JOB]['source_bound_stage_map'])
    need(cross['shared_roles']==10,'SHARED_ROLE_INVARIANT')
    other=[{'job_id':jid,'generic_jsx_sha256':profiles[jid]['generic_jsx_sha256'],
            'native_proof':'NOT_EXECUTED_BY_GC47BI'} for jid in sorted(profiles) if jid!=JOB]
    result={'schema':'gdl_gc47bi_zap_native_scene_crosswalk_r001',
            'source':'FROZEN_BF_FOUR_PROFILE_RECALCULATION',
            'accepted_zip_sha256':ACCEPTED,'shared_release_id':RELEASE,
            'reference':{'job_id':JOB,'attempt_id':ATTEMPT,'native_jsx_sha256':sha(jsx),
                         'native_scene_manifest_sha256':sha(run/'scene_manifest.json'),**review_data},
            'specialized_zap':cross,'other_profiles':other,
            'status':'PASS_ZAP_SCENE_ROLE_METADATA_PARITY' if cross['mismatch_count']==0
                     else 'REVIEW_ZAP_SCENE_ROLE_DIFFERENCES',
            'native_pixel_parity':'UNVERIFIED_NO_ILLUSTRATOR',
            'new_native_attempt':False,'windows_contacted':False,
            'gc47ax_consumer_switched':False,'gc47bc_consumer_switched':False,
            'shared_release_active':False,'client_mutated':False,'git_mutated':False,
            'queue_enabled':False,'production_ready':False,'visual_approved':False,
            'remaining_gates':['SPECIALIZED_JSX_RENDER_PARITY_REQUIRED','APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED',
                                'EXTERNAL_CLEAN_RESTORE_UNVERIFIED','QUEUE_DISABLED']}
    return result

def export_report(root,report):
    tmp=Path(root)/'tmp';need(directory(tmp),'REPO_TMP_MISSING')
    path=tmp/OUTPUT_NAME;need(not path.exists() and not path.is_symlink(),'REPORT_ALREADY_EXISTS_NO_OVERWRITE')
    payload=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(path) as z:
        need(z.testzip() is None and z.namelist()==['REPORT.json'],'REPORT_ZIP_READBACK')
    return path

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=['check','inspect'])
    p.add_argument('--client-name')
    a=p.parse_args(argv)
    try:
        bf=load_bf(ROOT)
        if a.mode=='check':
            print('GC47BI_CHECK=PASS_PINNED_BF_NO_NATIVE_NO_WINDOWS');return 0
        need(isinstance(a.client_name,str) and a.client_name.strip(),'CLIENT_NAME_REQUIRED')
        result=analyse(ROOT,a.client_name)
        output=export_report(ROOT,result)
        print('GC47BI_ZAP='+result['status'])
        print('GC47BI_ROLE_MATCH='+str(result['specialized_zap']['matched_role_count'])+'/12')
        print('GC47BI_OTHER_PROFILES=APA_DEG_BAS_NATIVE_STILL_UNVERIFIED')
        print('GC47BI_PIXEL_PARITY=UNVERIFIED')
        print('GC47BI_EVIDENCE='+str(output))
        print('GC47BI_NO_WINDOWS_NO_NATIVE_NO_CLIENT_MUTATION_NO_GIT_NO_QUEUE=TRUE')
        return 0
    except (Blocked,OSError,ValueError,TypeError,KeyError,ImportError,zipfile.BadZipFile) as err:
        code=str(err) if isinstance(err,Blocked) else type(err).__name__
        print('GC47BI=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:120],file=sys.stderr)
        print('GC47BI_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
