#!/usr/bin/env python3
"""GC47BM: unified, server-only GC47T work assembly (ZAP/APA/DEG/BAS).

All permanent roles resolved by the pinned GC47BE shared release, with
verified per-job variable sources. ZAP retains its proven GC47AQ composition
and GC47Y receipt; other profiles use pinned GC29 generic composition.
The *work format and asset resolver* are common; no production switchover.

Read-only clients/Git/Windows; private staging exclusively under disposable tmp;
only redacted metadata REPORT.json survives in an immutable evidence ZIP.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, stat, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = 'scripts/graphic_design_lab/greeting_cards'
BL = ('gc47bl_zap_receipt_manifest_proof_r001.py', 'f77ef10bd0c0e84f899e7b58c434b9a4df13aae0f1b83574bba42e448148f3b8')
BJ = ('gc47bj_zap_shared_native_input_rebuild_r001.py', 'd1dbeb461c2a13018e57f01089962c50bd87f3cd3f9ee2af0335a0671809cccc')
BH = ('gc47bh_native_work_contract_shadow_r001.py', '7addb7e8fda7b347eb1d686810005d677ad234052b1500f52d2b877263a0aa02')
ZAP = 'gdl_gc_zap_20261011'
JOBS = frozenset(('gdl_gc_zap_20261011','gdl_gc_apa_20261011','gdl_gc_deg_20261011','gdl_gc_bas_20261011'))
OUTPUT = 'gc47bm_unified_four_work_shadow_evidence_r001.zip'
EXPECTED_RELEASE = 'efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83'
EXPECTED_ZAP_MANIFEST = 'a4b4ec37c09a64d0b96ae60e820d990e4ae85f878ed7e23cbe3460bffcdcd3dd'
REQUIRED_ASSETS = {k:(13 if k=='gdl_gc_bas_20261011' else 12) for k in JOBS}

class Blocked(RuntimeError): pass

def need(cond,code):
    if not cond: raise Blocked(code)
def sha(data): return hashlib.sha256(data).hexdigest()
def regular(p):
    try: return stat.S_ISREG(Path(p).lstat().st_mode)
    except OSError: return False
def directory(p):
    try: return stat.S_ISDIR(Path(p).lstat().st_mode) and not Path(p).is_symlink()
    except OSError: return False

def load(root,pin):
    name,want=pin
    p=Path(root)/SCRIPTS/name
    need(regular(p) and sha(p.read_bytes())==want,'DEPENDENCY_PIN_'+name)
    spec=importlib.util.spec_from_file_location('gc47bm_'+name.replace('.','_'),p)
    need(spec is not None and spec.loader is not None,'IMPORT_'+name)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def verify_job_material(job,scene,jsx,manifest,assets,expected_manifest_sha):
    """One common strict native-work contract for all 4 jobs."""
    need(job in JOBS,'JOB_NOT_SUPPORTED')
    need(isinstance(scene,dict) and scene.get('job_id')==job and scene.get('pages')==4,'SCENE_JOB_OR_PAGES')
    need(scene.get('visual_approved') is False and scene.get('production_ready') is False,'SCENE_AUTHORITY')
    need(isinstance(jsx,bytes) and len(jsx)>100 and len(jsx)<15_000_000,'JSX_BYTES')
    need(isinstance(manifest,bytes) and sha(manifest)==expected_manifest_sha,'MANIFEST_REFERENCE_DRIFT')
    obj=json.loads(manifest.decode('utf8'))
    need(obj.get('job_id')==job and obj.get('jsx_sha256')==sha(jsx),'MANIFEST_JSX_BINDING')
    need(obj.get('visual_approved') is False and obj.get('production_ready') is False,'MANIFEST_AUTHORITY')
    need(isinstance(assets,dict) and len(assets)==REQUIRED_ASSETS[job],'ASSET_COUNT')
    need(set(obj.get('asset_sha256',{}))==set(assets),'MANIFEST_ASSET_SET')
    layers=scene.get('layers',[])
    need(isinstance(layers,list) and len(layers)==len(assets),'LAYER_COUNT')
    names=[];roles=[]
    for layer in layers:
        need(isinstance(layer,dict) and isinstance(layer.get('role'),str),'LAYER_ROLE')
        role=layer['role']; path=layer.get('file')
        need(isinstance(path,str) and re.fullmatch(r'assets/[a-z0-9_]+\.png',path) is not None,'LAYER_PATH')
        roles.append(role);names.append(path.split('/')[-1])
    need(len(set(roles))==len(roles) and len(set(names))==len(names) and set(names)==set(assets),'LAYER_DUP_OR_NAMES')
    for name,data in assets.items():
        need(re.fullmatch(r'[a-z0-9_]+\.png',name) is not None,'ASSET_NAME')
        need(isinstance(data,bytes) and 0<len(data)<=80*1024*1024,'ASSET_BYTES')
        need(sha(data)==obj['asset_sha256'][name],'ASSET_SHA_DRIFT')
    if job==ZAP:
        need(isinstance(obj.get('gc47y_source_receipt'),dict),'ZAP_RECEIPT_MISSING')
    else:
        need('gc47y_source_receipt' not in obj,'FOREIGN_ZAP_RECEIPT')
    # No client text in public manifest; JSX may contain it in private stage.
    for k in ('greeting_text','front_lines','sender_lines'):
        need(k not in obj,'CLIENT_TEXT_IN_MANIFEST')
    return obj

def compile_from_pinned(root,client):
    """Recompile from sources, not from four frozen manifest/JSX files."""
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPO')
    bl=load(root,BL);bj=load(root,BJ);bh=load(root,BH)
    proof=bl.analyse(root,client)  # Four-source manifest closure, fail closed.
    need(proof['status']=='PASS_FOUR_SOURCE_REBUILT_NATIVE_MANIFESTS_NO_WINDOWS','GC47BL_NOT_PASS')
    need(proof['shared_release_id']==EXPECTED_RELEASE,'SHARED_RELEASE_CHANGED')
    rows={row['job_id']:row for row in proof['profiles']}
    need(set(rows)==JOBS,'FOUR_PROFILE_PROOFS')
    bk=bl.load_pinned(root,bl.BK_NAME,bl.BK_SHA)
    y=bl.load_pinned(root,bl.Y_NAME,bl.Y_SHA)
    bg=bj.pinned(bj.BG_NAME,bj.BG_SHA,root)
    bf=bg.pinned_bf(root)
    report=bf.inspect(root,client)
    bg.validate_report(report)
    assets_by_job=bg.verified_sources(root,client,bf,report)
    need(set(assets_by_job)==JOBS,'FOUR_ASSET_SOURCES')
    bi=bj.pinned(bj.BI_NAME,bj.BI_SHA,root)
    cross=bi.analyse(root,client)
    need(cross['status']=='PASS_ZAP_SCENE_ROLE_METADATA_PARITY','ZAP_CROSSWALK')
    jsx,scene,s,ws=bj.rebuild_specialized_zap(root,client,bi,cross)
    zapassets=assets_by_job[ZAP]
    ref=s.native_run_dir(ws,ZAP,bj.ATTEMPT)
    reference_manifest=ref/'scene_manifest.json'
    need(regular(reference_manifest) and bj.file_sha(reference_manifest)==EXPECTED_ZAP_MANIFEST,'FROZEN_ZAP_MANIFEST')
    reference=json.loads(reference_manifest.read_bytes().decode('utf8'))
    bj.check_asset_bytes(zapassets,reference,ref/'assets')
    base=bk.manifest_object(scene,bg.ACCEPTED,zapassets,jsx)
    receipt=bl.derived_receipt(y,bg.ACCEPTED,sha(zapassets['p03_flowers.png']),scene)
    man=bk.gc29_bytes({**base,'gc47y_source_receipt':receipt})
    need(man==reference_manifest.read_bytes(),'ZAP_INDEPENDENT_MANIFEST_NOT_EQUAL')
    need(rows[ZAP]['manifest']=='PASS_BYTE_IDENTICAL','ZAP_CLOSURE_MISSING')
    result={ZAP:(scene,jsx,man,zapassets,'PINNED_GC47AQ_GC47Y')}

    # GC29 generic scene for APA, DEG, BAS; same shared assets and materializer.
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    az=bb.az_module(root)
    t=az.module(root,bh.TRANSPORT_NAME,'gc47bm_transport')
    source,gc29=t.source_check()
    workspace=source.workspace(client)
    vault=workspace/'template_studio/native_asset_vault_v0_1'
    catalog=gc29.verify_vault(vault)
    jobs,arts,archive=gc29.accepted_jobs(workspace)
    need(bj.file_sha(archive)==bg.ACCEPTED,'ACCEPTED_ZIP_CHANGED')
    need(set(job['job_id'] for job in jobs)==JOBS,'INPUT_JOB_SET_CHANGED')
    template=(root/SCRIPTS/bh.JSX_NAME).read_text('utf8')
    need(template.count('/*__GC29_SCENE__*/')==1,'GENERIC_JSX_MARKER')
    ledger={row['job_id']:row for row in report['profiles']}
    for job in jobs:
        jid=job['job_id']
        if jid==ZAP: continue
        logo=az.logo_from_accepted(job,arts,archive)
        gscene=gc29.compile_scene(job,catalog,logo)
        gc29.bind_illustrator_signature(gscene,vault,catalog)
        gjsx=template.replace('/*__GC29_SCENE__*/',json.dumps(gscene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
        assets=assets_by_job[jid]
        _,mismatches=bh.validate_work(gscene,gjsx,assets,ledger[jid]['source_bound_stage_map'],ledger[jid]['generic_jsx_sha256'],bg.ACCEPTED)
        need(not mismatches,'GENERIC_GEOMETRY_MISMATCH_'+jid)
        gman=bk.generic_bytes(bk.manifest_object(gscene,bg.ACCEPTED,assets,gjsx))
        need(rows[jid]['manifest_bytes_identical'] and sha(gman)==rows[jid]['computed_manifest_sha256'],'GENERIC_MANIFEST_NOT_PINNED_'+jid)
        result[jid]=(gscene,gjsx,gman,assets,'PINNED_GC29_GENERIC')
    need(set(result)==JOBS,'NOT_ALL_COMPILED')
    for jid,(scene,jsx,manifest,assets,_) in result.items():
        expected=EXPECTED_ZAP_MANIFEST if jid==ZAP else rows[jid]['computed_manifest_sha256']
        verify_job_material(jid,scene,jsx,manifest,assets,expected)
    return result,proof

def verify_ephemeral(root,compiled,bj):
    """Materialize each native work/ only in private tmp; remove even on failure."""
    root=Path(root);tmp=root/'tmp'
    need(directory(tmp),'TMP_REQUIRED')
    outputs=[]
    with tempfile.TemporaryDirectory(prefix='gc47bm_private_',dir=tmp) as stage:
        os.chmod(stage,0o700)
        for jid in sorted(compiled):
            scene,jsx,manifest,assets,source=compiled[jid]
            d=Path(stage)/jid;d.mkdir(mode=0o700)
            staged=bj.ephemeral_verify(d,jsx,manifest,assets)
            need(staged['all_work_bytes_readback'] and staged['work_file_count']==len(assets)+2,'WORK_READBACK')
            outputs.append({'job_id':jid,'builder':source,'asset_count':len(assets),
                            'jsx_sha256':sha(jsx),'manifest_sha256':sha(manifest),
                            'asset_ledger_sha256':sha(json.dumps({name:sha(blob) for name,blob in sorted(assets.items())},sort_keys=True).encode()),
                            'work_zip_sha256':staged['work_zip_sha256'],
                            'file_count':staged['work_file_count'],'readback':'PASS','scene_pages':4})
    need(len(outputs)==4,'WORK_COUNT')
    return outputs

def build_report(rows,proof):
    need(len(rows)==4 and set(row['job_id'] for row in rows)==JOBS,'REPORT_JOB_SET')
    return {'schema':'gdl_gc47bm_unified_native_work_shadow_r001',
            'status':'PASS_FOUR_UNIFIED_NATIVE_WORK_SHADOWS_NON_DISPATCH',
            'shared_release_id':EXPECTED_RELEASE,'release_active':False,
            'profiles':rows,'source_manifest_gate':proof['status'],
            'common_work_builder':'GC47BM_SINGLE_CONTRACT',
            'variable_roles':'P01_HEADING_P01_RECIPIENT_LOGO_P03_PHOTO_P04_GREETING_SENDER_SIGNATURE',
            'ephemeral_client_content_removed':True,
            'gc47ax_switched':False,'gc47bc_switched':False,'windows_contacted':False,
            'native_dispatch':False,'new_attempts':False,'queue_enabled':False,
            'git_mutated':False,'client_mutated':False,'visual_approved':False,'production_ready':False,
            'native_pixel_parity':'UNVERIFIED',
            'remaining_gates':['LIVE_SHARED_CONSUMER_NOT_SWITCHED','NATIVE_PIXEL_PARITY_UNVERIFIED',
              'APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED','CLEAN_RESTORE_UNVERIFIED','QUEUE_DISABLED']}

def write_evidence(root,report):
    out=Path(root)/'tmp'/OUTPUT
    need(directory(out.parent) and not out.exists() and not out.is_symlink(),'EVIDENCE_ALREADY_EXISTS')
    payload=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
    fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as stream:
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None and z.namelist()==['REPORT.json'],'EVIDENCE_CRC')
    return out

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=('check','inspect'),required=True)
    p.add_argument('--client-name')
    args=p.parse_args(argv)
    try:
        bj=load(ROOT,BJ);bl=load(ROOT,BL);load(ROOT,BH)
        if args.mode=='check':
            need(bj.RELEASE==EXPECTED_RELEASE and bl.OUTPUT,'FROZEN_SOURCE_CONTRACT')
            print('GC47BM_CHECK=PASS_PINNED_SOURCE_NO_WINDOWS');return 0
        need(isinstance(args.client_name,str) and args.client_name.strip(),'CLIENT_NAME_REQUIRED')
        compiled,proof=compile_from_pinned(ROOT,args.client_name)
        rows=verify_ephemeral(ROOT,compiled,bj)
        report=build_report(rows,proof)
        out=write_evidence(ROOT,report)
        for row in rows:print('GC47BM_PROFILE='+row['job_id']+' WORK=PASS_VERIFIED_EPHEMERAL')
        print('GC47BM_STATUS='+report['status'])
        print('GC47BM_EVIDENCE='+str(out))
        print('GC47BM_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_NO_QUEUE=TRUE')
        return 0
    except Exception as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC47BM=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:120],file=sys.stderr)
        print('GC47BM_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
