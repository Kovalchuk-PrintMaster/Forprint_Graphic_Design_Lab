#!/usr/bin/env python3
"""GC47BJ: rebuild frozen specialized ZAP JSX + durable resolved assets in memory.

Compare all native work input bytes to previously successful frozen ZAP attempt.
Never dispatch, allocate a native attempt, alter client, switch consumers or activate design.
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
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
CAN=Path(__file__).resolve().parent
BI_NAME='gc47bi_zap_native_scene_crosswalk_r001.py'
BI_SHA='0eedf8a628c65681eecf528615d8dc417365eb4700385da95f1b359263d81a7e'
BG_NAME='gc47bg_shared_stage_bridge_shadow_r001.py'
BG_SHA='e1b6535fd3ac06850283e9449fb8f6dbdaf4c7e26a85fc6b9bd2a9a41efd1d31'
AQ_NAME='gc47aq_shadow_integration_r001.py'
AQ_SHA='eb91be0e27405a89e1f3d1fbd0827bb85f3e4a18fcc9d4ac7bbb97dd3fc22d01'
JOB='gdl_gc_zap_20261011'
ATTEMPT='p20261102115307-e7858645'
RELEASE='efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83'
OUTPUT='gc47bj_zap_shared_native_input_evidence_r001.zip'
SAFE=re.compile(r'^[a-z0-9_]+\.png$')
class Blocked(RuntimeError):pass

def need(v,code):
    if not v:raise Blocked(code)
def sha(data):return hashlib.sha256(data).hexdigest()
def regular(p):
    try:return stat.S_ISREG(Path(p).lstat().st_mode)
    except OSError:return False
def directory(p):
    try:return stat.S_ISDIR(Path(p).lstat().st_mode) and not Path(p).is_symlink()
    except OSError:return False
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
    return h.hexdigest()
def pinned(name,expected,root=ROOT):
    p=Path(root)/'scripts/graphic_design_lab/greeting_cards'/name
    need(regular(p) and file_sha(p)==expected,'SOURCE_DRIFT_'+name)
    spec=importlib.util.spec_from_file_location('gc47bj_'+name.replace('.','_'),p)
    need(spec is not None and spec.loader is not None,'IMPORT_FAILED_'+name)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

def rebuild_specialized_zap(root,client,bi,cross):
    """Compile actual GC47AQ specialized in-memory scene; NOT reference JSX replay."""
    aq=pinned(AQ_NAME,AQ_SHA,root)
    ap,base,proposal=aq.gate(root,root/'scripts/graphic_design_lab/greeting_cards')
    bf=bi.load_bf(root)
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    az=bb.az_module(root)
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bj_transport')
    s,gc29=t.source_check()
    ws,selected,archive,variant=t.validate_job(s,gc29,client,JOB)
    need(file_sha(archive)==bi.ACCEPTED,'ACCEPTED_ZIP_CHANGED')
    y=bf.load('gc47y_review_amendment_r001.py',root)
    y.check_sources(ws,selected,archive)
    vault=ws/'template_studio/native_asset_vault_v0_1'
    catalog=gc29.verify_vault(vault)
    reg=s.read_obj(s.REGISTRY,5_000_000)['greeting_card_machine_pipeline_v0_1']
    scene=aq.apply_pipeline(gc29,t.gc47af_mod(),y,ap,reg,base,proposal,selected,catalog,JOB)
    generated=gc29.bind_illustrator_signature(scene,vault,catalog)
    need('p04_grigo_signature.png' in generated,'SIGNATURE_DERIVATIVE_ABSENT')
    template=(root/'scripts/graphic_design_lab/greeting_cards'/aq.JSX.name).read_text('utf8')
    need(template.count(aq.MARK)==1,'SPECIALIZED_TEMPLATE_MARKER')
    jsx=template.replace(aq.MARK,json.dumps(scene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
    need(sha(jsx)==cross['reference']['native_jsx_sha256'], 'SPECIALIZED_JSX_NOT_REFERENCE_IDENTICAL')
    return jsx,scene,s,ws

def check_asset_bytes(source_map,legacy,reference_assets):
    """Source map MUST originate from canonical resolver, not from old native run."""
    need(isinstance(source_map,dict) and len(source_map)==12,'STAGED_ASSET_COUNT')
    need(isinstance(legacy.get('asset_sha256'),dict),'REFERENCE_ASSET_LEDGER')
    need(set(legacy['asset_sha256'])==set(source_map),'REFERENCE_ASSET_SET')
    need(directory(reference_assets),'REFERENCE_ASSET_DIR')
    need(set(p.name for p in reference_assets.iterdir())==set(source_map),'REFERENCE_ASSET_EXTRA_OR_MISSING')
    records=[]
    for name,bytes_ in sorted(source_map.items()):
        need(SAFE.fullmatch(name) is not None,'UNSAFE_ASSET_NAME')
        need(isinstance(bytes_,bytes) and 0<len(bytes_)<=80*1024*1024,'ASSET_SIZE_INVALID')
        digest=sha(bytes_)
        need(digest==legacy['asset_sha256'][name],'SHARED_ASSET_NOT_MANIFEST_IDENTICAL_'+name)
        orig=reference_assets/name
        need(regular(orig) and file_sha(orig)==digest,'SHARED_ASSET_NOT_REFERENCE_IDENTICAL_'+name)
        records.append({'asset':name,'sha256':digest,'byte_count':len(bytes_)})
    return records

def write_private(path,data):
    path=Path(path)
    need(not path.exists() and not path.is_symlink(),'STAGE_PATH_ALREADY_EXISTS')
    fd=os.open(path,os.O_WRONLY|os.O_EXCL|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)
    need(regular(path) and file_sha(path)==sha(data),'STAGE_READBACK_FAILED')

def ephemeral_verify(stage,jsx,manifest,assets):
    """Build private ephemeral GC47T work shape then verify ZIP and remove by caller."""
    stage=Path(stage)
    need(directory(stage) and stat.S_IMODE(stage.stat().st_mode)==0o700,'STAGE_PRIVATE_REQUIRED')
    work=stage/'work';work.mkdir(mode=0o700)
    a=work/'assets';a.mkdir(mode=0o700)
    material={'work/run_in_illustrator.jsx':jsx,'work/scene_manifest.json':manifest}
    material.update({'work/assets/'+name:data for name,data in assets.items()})
    for name,data in material.items():
        need(name.startswith('work/') and '..' not in Path(name).parts,'STAGE_SCOPE')
        write_private(stage/name,data)
    bundle=stage/'work_shadow.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(material.items()):z.write(stage/name,name)
    with zipfile.ZipFile(bundle) as z:
        need(z.testzip() is None and set(z.namelist())==set(material),'STAGE_ZIP_FILE_SET_OR_CRC')
        for name,data in material.items():need(sha(z.read(name))==sha(data),'STAGE_ZIP_SHA_'+name)
    return {'work_file_count':len(material),'work_zip_sha256':file_sha(bundle),'all_work_bytes_readback':True}

def inspect(root,client):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPOSITORY_REQUIRED')
    bi=pinned(BI_NAME,BI_SHA,root)
    bg=pinned(BG_NAME,BG_SHA,root)
    cross=bi.analyse(root,client)
    need(cross['status']=='PASS_ZAP_SCENE_ROLE_METADATA_PARITY' and
         cross['specialized_zap']['mismatch_count']==0 and
         cross['reference']['attempt_id']==ATTEMPT,'GC47BI_REFERENCE_CROSSWALK_NOT_PASS')
    bf=bi.load_bf(root)
    report=bf.inspect(root,client);bg.validate_report(report)
    all_sources=bg.verified_sources(root,client,bf,report)
    need(set(all_sources)==set(bg.EXPECTED),'FOUR_PROFILE_RESOLVER_SOURCE_SET')
    jsx,scene,s,ws=rebuild_specialized_zap(root,client,bi,cross)
    run=s.native_run_dir(ws,JOB,ATTEMPT)
    need(directory(run),'REFERENCE_NATIVE_RUN_MISSING')
    origjsx=run/'run_in_illustrator.jsx';origmanifest=run/'scene_manifest.json';origassets=run/'assets'
    need(regular(origjsx) and file_sha(origjsx)==sha(jsx),'SPECIALIZED_JSX_REFERENCE_MISMATCH')
    need(regular(origmanifest) and file_sha(origmanifest)==cross['reference']['native_scene_manifest_sha256'],
         'REFERENCE_MANIFEST_SHA_DRIFT')
    manifest_bytes=origmanifest.read_bytes();legacy=json.loads(manifest_bytes.decode('utf8'))
    refroles={x['role']:x for x in legacy['layers']}
    need(len(refroles)==len(legacy['layers'])==12,'REFERENCE_ROLE_COLLISION')
    now={x['role']:x for x in scene['layers']}
    need(set(now)==set(refroles),'RECOMPILED_SCENE_ROLE_SET')
    for role in now:
        need(now[role]['file']==refroles[role]['file'] and now[role]['bbox_mm']==refroles[role]['bbox_mm'],
             'RECOMPILED_SCENE_GEOMETRY_'+role)
    assets=all_sources[JOB]
    records=check_asset_bytes(assets,legacy,origassets)
    tmp=root/'tmp';need(directory(tmp),'REPOSITORY_TMP_REQUIRED')
    output=tmp/OUTPUT;need(not output.exists() and not output.is_symlink(),'REPORT_ALREADY_EXISTS')
    with tempfile.TemporaryDirectory(prefix='gc47bj_private_',dir=tmp) as folder:
        os.chmod(folder,0o700)
        work=ephemeral_verify(folder,jsx,manifest_bytes,assets)
    result={'schema':'gdl_gc47bj_zap_shared_native_input_rebuild_r001',
      'status':'PASS_ZAP_FROZEN_NATIVE_WORK_INPUT_BYTE_PARITY_WITH_SHARED_ASSETS',
      'reference_attempt':ATTEMPT,'job_id':JOB,'shared_release_id':RELEASE,
      'specialized_jsx_source':'RECOMPILED_GC47AQ_PINNED_SOURCES',
      'specialized_jsx_sha256':sha(jsx),'reference_manifest_sha256':sha(manifest_bytes),
      'manifest_source':'FROZEN_REFERENCE_MANIFEST_NOT_NEW_COMPILER_OUTPUT',
      'common_role_count':10,'variable_role_count':2,'assets':records,
      'durable_asset_source':'GC47BE_SHARED_RELEASE_PLUS_VERIFIED_ZAP_OVERRIDE',
      'stage':work,'ephemeral_stage_removed':True,
      'gc47ax_consumer_switched':False,'gc47bc_consumer_switched':False,
      'new_native_attempt':False,'windows_contacted':False,'native_dispatch':False,
      'client_mutated':False,'git_mutated':False,'shared_release_active':False,
      'queue_enabled':False,'visual_approved':False,'production_ready':False,
      'pixel_parity':'UNVERIFIED_NEW_ILLUSTRATOR_RUN_NOT_EXECUTED',
      'remaining_gates':['NEW_SHARED_DESIGN_CONSUMER_NOT_IMPLEMENTED','NEW_NATIVE_PIXEL_PARITY_UNVERIFIED',
        'APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED','EXTERNAL_CLEAN_RESTORE_UNVERIFIED','QUEUE_DISABLED']}
    payload=(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
    fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(output) as z:need(z.testzip() is None and z.namelist()==['REPORT.json'],'REPORT_CRC')
    return result,output

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=('check','inspect'))
    p.add_argument('--client-name')
    a=p.parse_args(argv)
    try:
        bi=pinned(BI_NAME,BI_SHA)
        bg=pinned(BG_NAME,BG_SHA)
        if a.mode=='check':
            bi.load_bf(ROOT);bg.pinned_bf(ROOT)
            print('GC47BJ_CHECK=PASS_SOURCE_BOUND_NON_NATIVE');return 0
        need(isinstance(a.client_name,str) and a.client_name.strip(),'CLIENT_NAME_REQUIRED')
        result,pth=inspect(ROOT,a.client_name)
        print('GC47BJ_STATUS='+result['status'])
        print('GC47BJ_WORK_INPUT=PASS_JSX_MANIFEST_12_ASSETS')
        print('GC47BJ_EPHEMERAL=REMOVED')
        print('GC47BJ_PIXEL_PARITY=UNVERIFIED')
        print('GC47BJ_EVIDENCE='+str(pth))
        print('GC47BJ_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_NO_QUEUE=TRUE')
        return 0
    except Exception as e:
        code=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47BJ=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:110],file=sys.stderr)
        print('GC47BJ_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
