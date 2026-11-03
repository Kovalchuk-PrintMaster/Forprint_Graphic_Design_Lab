#!/usr/bin/env python3
"""GC47BH: assemble and validate ephemeral real GC47T work/ payloads from GC47BE.

No native launch, attempt allocation, dispatch, activation, client writes, queue, or git.
The work/ bundle holds customer content only in 0700 ephemeral staging and is deleted.
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
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
BG_NAME='gc47bg_shared_stage_bridge_shadow_r001.py'
BG_SHA='e1b6535fd3ac06850283e9449fb8f6dbdaf4c7e26a85fc6b9bd2a9a41efd1d31'
JSX_NAME='gc29_native_four_page_v0_1.jsx'
JSX_SHA='96b0549cc21cc82f35e1648e16f4ee25cb88fd8d9333c1ad6a38b16c9b306955'
TRANSPORT_NAME='gc47t_client_windows_bridge_r001.py'
TRANSPORT_SHA='c99fde8a5f5805da57b5cca037cda17a34dea002a076042279bd274c4848ef46'
REPORT_NAME='gc47bh_native_work_contract_evidence_r001.zip'
REQUIRED={'gdl_gc_zap_20261011','gdl_gc_apa_20261011','gdl_gc_deg_20261011','gdl_gc_bas_20261011'}
SAFE=re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')

class Blocked(RuntimeError): pass

def need(cond,code):
    if not cond:raise Blocked(code)

def sha(data):return hashlib.sha256(data).hexdigest()

def regular(p):
    try:return stat.S_ISREG(Path(p).lstat().st_mode)
    except OSError:return False

def directory(p):
    try:return stat.S_ISDIR(Path(p).lstat().st_mode) and not Path(p).is_symlink()
    except OSError:return False

def file_sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def load_pins(root=ROOT):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPOSITORY_REQUIRED')
    base=root/'scripts/graphic_design_lab/greeting_cards'
    checks={BG_NAME:BG_SHA,JSX_NAME:JSX_SHA,TRANSPORT_NAME:TRANSPORT_SHA}
    for name,want in checks.items():
        path=base/name
        need(regular(path) and file_sha(path)==want,'PIN_DRIFT_'+name.upper().replace('.','_'))
    src=base/BG_NAME
    spec=importlib.util.spec_from_file_location('gc47bh_frozen_gc47bg',src)
    need(spec is not None and spec.loader is not None,'BG_IMPORT_SPEC')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def public_scene(scene,accepted_sha,assets,jsx):
    """Exactly the non-secret GC29 manifest fields GC47T requires."""
    need(scene.get('pages')==4 and scene.get('image_mode')=='DEFAULT_ASSET','SCENE_CONTRACT')
    need(scene.get('visual_approved') is False and scene.get('production_ready') is False,'SCENE_AUTHORITY')
    for k in ('greeting_text','sender_lines','front_lines'):
        need(k in scene,'SCENE_TEXT_REQUIRED_'+k)
    doc={k:v for k,v in scene.items() if k not in ('greeting_text','sender_lines','front_lines')}
    doc['accepted_zip_sha256']=accepted_sha
    doc['asset_sha256']={name:sha(data) for name,data in sorted(assets.items())}
    doc['jsx_sha256']=sha(jsx)
    return doc

def validate_work(scene,jsx,assets,ledger,expected_jsx,accepted_sha):
    need(isinstance(jsx,bytes) and sha(jsx)==expected_jsx,'GENERIC_JSX_PARITY')
    need(isinstance(assets,dict) and len(assets)==len(ledger),'ASSET_COUNT')
    slot={p['asset_name']:p for p in ledger}
    need(len(slot)==len(ledger) and set(assets)==set(slot),'ASSET_NAMES')
    byrole={p['role']:p for p in ledger}
    need(len(byrole)==len(ledger),'ASSET_ROLES')
    native_roles={v['role']:v for v in scene['layers']}
    need(len(native_roles)==len(scene['layers'])==len(ledger),'SCENE_ROLES')
    need(set(byrole)==set(native_roles),'SCENE_ROLE_SET')
    mismatches=[]
    for role,layer in native_roles.items():
        name=Path(layer['file']).name
        need(layer['file']=='assets/'+name and SAFE.fullmatch(name) is not None,'SCENE_ASSET_PATH')
        row=byrole[role]
        need(name==row['asset_name'] and sha(assets[name])==row['sha256'],'SCENE_RESOURCE_DRIFT')
        if [round(float(x),5) for x in layer['bbox_mm']]!=[round(float(x),5) for x in row['bbox_mm']]:
            mismatches.append(role)
    need(scene['job_id'] in REQUIRED,'JOB_SET')
    need(mismatches==(['P03.FLOWERS'] if scene['job_id']=='gdl_gc_zap_20261011' else []),
         'UNEXPECTED_LAYER_GEOMETRY_MISMATCH')
    # This ZAP photo geometry discrepancy belongs to the specialized GC47Y renderer.
    # It must NOT be promoted as a generic bridge without real native parity evidence.
    manifest=public_scene(scene,accepted_sha,assets,jsx)
    need(manifest['jsx_sha256']==expected_jsx,'MANIFEST_JSX_SHA')
    need(manifest['pages']==4 and manifest['job_id']==scene['job_id'],'MANIFEST_NATIVE_BINDING')
    return manifest,mismatches

def write_private(path,data):
    p=Path(path)
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(data)
        f.flush()
    need(regular(p) and file_sha(p)==sha(data),'WORK_READBACK_SHA')

def stage_work(folder,scene,jsx,assets,ledger,expected_jsx,accepted_sha):
    """Build the actual GC47T work/ shape. Never writes in client's native_runs."""
    folder=Path(folder)
    need(directory(folder) and stat.S_IMODE(folder.stat().st_mode)==0o700,'PRIVATE_STAGE_DIR_REQUIRED')
    manifest,issues=validate_work(scene,jsx,assets,ledger,expected_jsx,accepted_sha)
    work=folder/'work';work.mkdir(mode=0o700)
    assetsdir=work/'assets';assetsdir.mkdir(mode=0o700)
    json_bytes=(json.dumps(manifest,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode('ascii')
    write_private(work/'run_in_illustrator.jsx',jsx)
    write_private(work/'scene_manifest.json',json_bytes)
    for name,data in sorted(assets.items()):write_private(assetsdir/name,data)
    # Unlike GC47T, no controller/runner and no native attempt; work-only rehearsal.
    bundle=folder/'work_contract_shadow.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(work.rglob('*')):
            if not file.is_file():continue
            need(regular(file),'STAGED_SYMLINK')
            name=file.relative_to(folder).as_posix()
            need(name.startswith('work/') and '..' not in Path(name).parts,'ZIP_SCOPE')
            z.write(file,name)
    os.chmod(bundle,0o600)
    verify_work_zip(bundle,expected_jsx,manifest)
    return {'job_id':scene['job_id'],'asset_count':len(assets),
            'native_work_sha256':file_sha(bundle),'scene_manifest_sha256':sha(json_bytes),
            'generic_jsx_sha256':sha(jsx),'all_asset_sha256_verified':True,
            'geometry_mismatch_roles':issues,
            'native_generic_work_contract': 'SHADOW_VALIDATED_WITH_ZAP_GEOMETRY_GATE' if issues else 'SHADOW_VALIDATED',
            'native_launch_authorized':False}

def verify_work_zip(bundle,expected_jsx,manifest):
    with zipfile.ZipFile(bundle) as z:
        need(z.testzip() is None,'ZIP_CRC_FAILED')
        files=set(z.namelist())
        expected={'work/run_in_illustrator.jsx','work/scene_manifest.json'}|{'work/assets/'+n for n in manifest['asset_sha256']}
        need(files==expected,'WORK_ZIP_FILE_SET')
        need(sha(z.read('work/run_in_illustrator.jsx'))==expected_jsx,'ZIP_JSX_READBACK')
        public=json.loads(z.read('work/scene_manifest.json'))
        need(public==manifest,'ZIP_MANIFEST_READBACK')
        for name,want in manifest['asset_sha256'].items():
            need(sha(z.read('work/assets/'+name))==want,'ZIP_ASSET_SHA_'+name)
    return True

def run_shadow(root,client):
    root=Path(root);bg=load_pins(root);bf=bg.pinned_bf(root)
    # Recalculate all provenance proofs from installed canonical source and client ZIP.
    report=bf.inspect(root,client)
    bg.validate_report(report)
    source_map=bg.verified_sources(root,client,bf,report)
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    az=bb.az_module(root)
    t=az.module(root,TRANSPORT_NAME,'gc47bh_transport_contract')
    s,gc29=t.source_check()
    ws=s.workspace(client)
    vault=ws/'template_studio/native_asset_vault_v0_1'
    manifest=gc29.verify_vault(vault)
    jobs,arts,archive=gc29.accepted_jobs(ws)
    need(file_sha(archive)==bg.ACCEPTED,'SOURCE_ARCHIVE_CHANGED')
    need(set(j['job_id'] for j in jobs)==REQUIRED,'PROFILE_ID_SET')
    template=(root/'scripts/graphic_design_lab/greeting_cards'/JSX_NAME).read_text('utf8')
    need(template.count('/*__GC29_SCENE__*/')==1,'JSX_MARKER')
    stage_parent=root/'tmp'
    need(directory(stage_parent),'TMP_MISSING')
    out=stage_parent/REPORT_NAME
    need(not out.exists() and not out.is_symlink(),'REPORT_EXISTS_NO_OVERWRITE')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='gc47bh_private_',dir=stage_parent) as stage:
        os.chmod(stage,0o700)
        byid={p['job_id']:p for p in report['profiles']}
        for job in jobs:
            jid=job['job_id'];p=byid[jid]
            logo=az.logo_from_accepted(job,arts,archive)
            scene=gc29.compile_scene(job,manifest,logo)
            gc29.bind_illustrator_signature(scene,vault,manifest)
            jsx=template.replace('/*__GC29_SCENE__*/',json.dumps(scene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
            dest=Path(stage)/jid;dest.mkdir(mode=0o700)
            rows.append(stage_work(dest,scene,jsx,source_map[jid],p['source_bound_stage_map'],
                                   p['generic_jsx_sha256'],bg.ACCEPTED))
    # Entire work/ staging, including customer texts, images and private archives deleted.
    rows.sort(key=lambda p:p['job_id'])
    need(len(rows)==4 and sum(bool(r['geometry_mismatch_roles']) for r in rows)==1,'PROFILE_RECONCILIATION')
    result={'schema':'gdl_gc47bh_native_work_contract_shadow_r001',
            'status':'PASS_FOUR_EPHEMERAL_GC47T_WORK_CONTRACT_SHADOWS',
            'release_id':bg.RELEASE,'accepted_zip_sha256':bg.ACCEPTED,
            'profiles':rows,'private_work_payloads_removed':True,
            'all_native_work_zip_crc_sha_passed':True,
            'generic_renderer_work_contract_verified':True,
            'specialized_zap_native_parity':'UNVERIFIED_GEOMETRY_DIFF_REQUIRES_GC47Y',
            'pixel_parity':'UNVERIFIED_NO_ILLUSTRATOR',
            'gc47ax_consumer_switched':False,'gc47bc_consumer_switched':False,
            'native_dispatch':False,'client_mutated':False,'git_mutated':False,'queue_enabled':False,
            'production_ready':False,'visual_approved':False,
            'remaining_gates':['ZAP_SPECIALIZED_JSX_AND_P03_CROP_PARITY_REQUIRED',
              'APA_DEG_BAS_VISUAL_NATIVE_PROOF_REQUIRED','EXTERNAL_RESTORE_NOT_TESTED','QUEUE_DISABLED']}
    payload=(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf8')
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None,'EVIDENCE_ZIP_CRC')
    return result,out

def main(argv=None):
    a=argparse.ArgumentParser()
    a.add_argument('--mode',choices=('check','shadow'),required=True)
    a.add_argument('--client-name')
    opt=a.parse_args(argv)
    try:
        bg=load_pins()
        if opt.mode=='check':
            bf=bg.pinned_bf();bf.pins(ROOT)
            print('GC47BH_CHECK=PASS_FROZEN_BG_BF_GC29_GC47T_NO_NATIVE');return 0
        need(isinstance(opt.client_name,str) and opt.client_name.strip(),'CLIENT_NAME_REQUIRED')
        result,out=run_shadow(ROOT,opt.client_name)
        for p in result['profiles']:
            print('GC47BH_PROFILE='+p['job_id']+' WORK_SHA=PASS GEOMETRY='+(
                'REVIEW_REQUIRED' if p['geometry_mismatch_roles'] else 'MATCH'))
        print('GC47BH_WORK=PASS_FOUR_EPHEMERAL_NATIVE_WORK_CONTRACTS')
        print('GC47BH_EPHEMERAL=REMOVED_CLIENT_CONTENT')
        print('GC47BH_SPECIALIZED_ZAP_PARITY=UNVERIFIED')
        print('GC47BH_EVIDENCE='+str(out))
        print('GC47BH_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_NO_QUEUE=TRUE')
        return 0
    except (Blocked,OSError,ValueError,KeyError,TypeError,ImportError,zipfile.BadZipFile,json.JSONDecodeError) as e:
        code=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47BH=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:120])
        print('GC47BH_NO_NATIVE_NO_CLIENT_WRITE=TRUE')
        return 2
if __name__=='__main__':raise SystemExit(main())
