#!/usr/bin/env python3
"""GC47BL: independently reconstruct GC47Y final ZAP manifest and check 4 profiles.

GC47BK built the GC29 base manifest, not the GC47Y post-prepare receipt.
Compute that receipt from pinned GC47Y sources, NOT from reference manifest.
No Windows calls, native attempts, queue, Git change or client mutation.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, stat, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BK_NAME='gc47bk_native_manifest_rebuild_r001.py'
BK_SHA='da0d263f87f559d0645a84e40a7e621c4322d0487bcc4dee2f4b02737af548a3'
Y_NAME='gc47y_review_amendment_r001.py'
Y_SHA='30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312'
OUTPUT='gc47bl_four_manifest_receipt_evidence_r001.zip'
class Blocked(RuntimeError):pass
def need(test,code):
    if not test:raise Blocked(code)
def sha(value):return hashlib.sha256(value).hexdigest()
def regular(path):
    try:return stat.S_ISREG(Path(path).lstat().st_mode)
    except OSError:return False
def directory(path):
    try:return stat.S_ISDIR(Path(path).lstat().st_mode) and not Path(path).is_symlink()
    except OSError:return False
def load_pinned(repo,name,digest):
    path=Path(repo)/'scripts/graphic_design_lab/greeting_cards'/name
    need(regular(path) and sha(path.read_bytes())==digest,'DEPENDENCY_DRIFT_'+name)
    spec=importlib.util.spec_from_file_location('gc47bl_'+name.replace('.','_'),path)
    need(spec is not None and spec.loader is not None,'DEPENDENCY_IMPORT_'+name)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def derived_receipt(y,accepted,photo_sha,scene):
    """Same release contract as GC47Y.wrap_prepare, sourced independently.

    Never read gc47y_source_receipt from the reference to construct the result.
    """
    need(accepted==y.ACCEPTED_ZIP,'RECEIPT_ACCEPTED_SOURCE_DRIFT')
    need(photo_sha==y.FLOWER_NEW,'RECEIPT_PHOTO_SOURCE_DRIFT')
    old_amend=scene.get('gc47y_pilot_amendment')
    need(isinstance(old_amend,dict) and old_amend.get('schema')==y.SCHEMA and
         old_amend.get('photo_sha256')==y.FLOWER_NEW and
         old_amend.get('frame_sha256')==y.FRAME,'RECEIPT_SCENE_PROVENANCE_DRIFT')
    return {'schema':y.SCHEMA,'photo_sha256':photo_sha,'frame_sha256':y.FRAME,
            'accepted_zip_sha256':accepted,'operator_review_required':True}

def classify(base,reference,completed,bk):
    before=bk.changed_paths(base,reference)
    after=bk.changed_paths(completed,reference)
    if not before and not after:return 'PASS_BASE_ALREADY_IDENTICAL',before,after
    if before==['gc47y_source_receipt:MISSING'] and not after:
        return 'PASS_GC47Y_RECEIPT_ONLY_DIFFERENCE_RESOLVED',before,after
    return 'REVIEW_OTHER_OR_UNRESOLVED_MANIFEST_FIELDS',before,after

def analyse(root,client):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPOSITORY_REQUIRED')
    bk=load_pinned(root,BK_NAME,BK_SHA)
    y=load_pinned(root,Y_NAME,Y_SHA)
    bj=bk.read_pinned(root,bk.BJ_NAME,bk.BJ_SHA)
    bh=bk.read_pinned(root,bk.BH_NAME,bk.BH_SHA)
    bg=bj.pinned(bj.BG_NAME,bj.BG_SHA,root)
    bf=bg.pinned_bf(root)
    shared_report=bf.inspect(root,client)
    bg.validate_report(shared_report)
    sources=bg.verified_sources(root,client,bf,shared_report)
    need(set(sources)==bh.REQUIRED,'FOUR_PROFILE_ASSETS_NOT_PINNED')
    bi=bj.pinned(bj.BI_NAME,bj.BI_SHA,root)
    cross=bi.analyse(root,client)
    need(cross.get('status')=='PASS_ZAP_SCENE_ROLE_METADATA_PARITY','CROSSWALK_NOT_PASS')
    jsx,scene,s,ws=bj.rebuild_specialized_zap(root,client,bi,cross)
    native=s.native_run_dir(ws,bj.JOB,bj.ATTEMPT)
    original=native/'scene_manifest.json'
    need(regular(original) and bj.file_sha(original)==cross['reference']['native_scene_manifest_sha256'],
         'REFERENCE_MANIFEST_DRIFT')
    refbytes=original.read_bytes();reference=json.loads(refbytes.decode('utf8'))
    assets=sources[bj.JOB]
    bj.check_asset_bytes(assets,reference,native/'assets')
    base=bk.manifest_object(scene,bg.ACCEPTED,assets,jsx)
    need('gc47y_source_receipt' not in base,'GC29_COMPILER_ALREADY_HAS_RECEIPT')
    receipt=derived_receipt(y,bg.ACCEPTED,sha(assets['p03_flowers.png']),scene)
    completed={**base,'gc47y_source_receipt':receipt}
    status,before,after=classify(base,reference,completed,bk)
    rebuilt=bk.gc29_bytes(completed)
    if rebuilt!=refbytes and not after:status='REVIEW_JSON_WIRE_BYTES_ONLY'
    if rebuilt==refbytes and after:status='REVIEW_FIELDS_INCONSISTENT'
    # Original receipt must be independently constrained by pinned GC47Y, not copied.
    result={'job_id':bj.JOB,'manifest':'PASS_BYTE_IDENTICAL' if rebuilt==refbytes and not after else 'REVIEW_DIFFERENCES',
        'reconstruction_status':status,'reference_manifest_sha256':sha(refbytes),
        'reconstructed_manifest_sha256':sha(rebuilt),
        'prior_gc47bk_missing_paths':before,'remaining_difference_paths':after,
        'gc47y_source_receipt_derived_from_pinned_source':True,'source_receipt_same_as_reference':reference.get('gc47y_source_receipt')==receipt,
        'jsx_reference_sha256':sha(jsx),'asset_count':len(assets)}
    generic=bk.generic_manifests(root,client,bh,bg,shared_report,sources)
    rows=sorted([result]+generic,key=lambda row:row['job_id'])
    all_pass=(result['manifest']=='PASS_BYTE_IDENTICAL' and status in
         ('PASS_BASE_ALREADY_IDENTICAL','PASS_GC47Y_RECEIPT_ONLY_DIFFERENCE_RESOLVED') and
         all(row['manifest_bytes_identical'] for row in generic))
    return {'schema':'gdl_gc47bl_zap_receipt_manifest_proof_r001',
      'status':'PASS_FOUR_SOURCE_REBUILT_NATIVE_MANIFESTS_NO_WINDOWS' if all_pass else 'REVIEW_FOUR_MANIFESTS_NOT_IDENTICAL',
      'frozen_attempt':bj.ATTEMPT,'shared_release_id':bg.RELEASE,'profiles':rows,
      'client_mutated':False,'native_dispatch':False,'windows_contacted':False,
      'queue_enabled':False,'git_mutated':False,'shared_release_active':False,
      'visual_approved':False,'production_ready':False,'pixel_parity':'UNVERIFIED_NO_ILLUSTRATOR',
      'remaining_gates':['LIVE_SHARED_CONSUMER_NOT_SWITCHED','NATIVE_PIXEL_PARITY_UNVERIFIED',
      'APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED','EXTERNAL_CLEAN_RESTORE_UNVERIFIED','QUEUE_DISABLED']}

def write_private_report(root,result):
    out=Path(root)/'tmp'/OUTPUT
    need(directory(out.parent) and not out.exists() and not out.is_symlink(),'OUTPUT_NOT_NEW_OR_TMP_MISSING')
    payload=(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
    fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(out) as z:
        need(z.testzip() is None and z.namelist()==['REPORT.json'],'REPORT_CRC')
    return out

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=('check','inspect'),required=True)
    parser.add_argument('--client-name')
    args=parser.parse_args(argv)
    try:
        bk=load_pinned(ROOT,BK_NAME,BK_SHA)
        y=load_pinned(ROOT,Y_NAME,Y_SHA)
        if args.mode=='check':
            need(y.FLOWER_NEW and y.FRAME and bk.BJ_SHA,'PIN_MISSING')
            print('GC47BL_CHECK=PASS_FROZEN_BK_GC47Y_NO_NATIVE')
            return 0
        need(bool(args.client_name and args.client_name.strip()),'CLIENT_REQUIRED')
        result=analyse(ROOT,args.client_name)
        out=write_private_report(ROOT,result)
        for row in result['profiles']:
            print('GC47BL_PROFILE='+row['job_id']+' MANIFEST='+row['manifest'])
            if row['job_id']=='gdl_gc_zap_20261011':
                print('GC47BL_ZAP_RECEIPT='+row['reconstruction_status'])
                print('GC47BL_ZAP_REMAINING_PATHS='+','.join(row['remaining_difference_paths']))
        print('GC47BL_STATUS='+result['status'])
        print('GC47BL_EVIDENCE='+str(out))
        print('GC47BL_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_NO_QUEUE=TRUE')
        return 0 if result['status'].startswith('PASS_') else 2
    except Exception as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC47BL=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:120],file=sys.stderr)
        print('GC47BL_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
