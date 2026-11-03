#!/usr/bin/env python3
"""GC47BK: independently rebuild source-bound native manifests offline.

ZAP uses the real specialized pinned JSX and durable common assets, and is
compared against a frozen successful native attempt. APA/DEG/BAS get an
independently regenerated generic manifest, compared to prior shadow evidence.
Never dispatches, mutates the client, authorizes production, or edits Git.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, stat, sys, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BJ_NAME='gc47bj_zap_shared_native_input_rebuild_r001.py'
BJ_SHA='d1dbeb461c2a13018e57f01089962c50bd87f3cd3f9ee2af0335a0671809cccc'
BH_NAME='gc47bh_native_work_contract_shadow_r001.py'
BH_SHA='7addb7e8fda7b347eb1d686810005d677ad234052b1500f52d2b877263a0aa02'
EVIDENCE='gc47bk_server_manifest_rebuild_evidence_r001.zip'
GENERIC_MANIFESTS={
  'gdl_gc_apa_20261011':'0f5a4339be2dd7973f67f840f837eeffcd96a7ad9fe3c56a56632a71d35d1f6c',
  'gdl_gc_deg_20261011':'102439fbbf9e05726e01a28e9e8ad5990c739f18eb35d3bd393a7adc7bffc9ac',
  'gdl_gc_bas_20261011':'1bf6e3c8d9f99517589be32bb2b4738dcac1819bfebe7c12a8b96109fa928aa2',
}
class Blocked(RuntimeError):pass

def need(v,msg):
    if not v:raise Blocked(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def regular(p):
    try:return stat.S_ISREG(Path(p).lstat().st_mode)
    except OSError:return False
def directory(p):
    try:return stat.S_ISDIR(Path(p).lstat().st_mode) and not Path(p).is_symlink()
    except OSError:return False
def read_pinned(root,name,digest):
    p=Path(root)/'scripts/graphic_design_lab/greeting_cards'/name
    need(regular(p) and sha(p.read_bytes())==digest,'DEPENDENCY_PIN_DRIFT_'+name)
    spec=importlib.util.spec_from_file_location('gc47bk_'+name.replace('.','_'),p)
    need(spec and spec.loader,'DEPENDENCY_SPEC')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def manifest_object(scene,accepted,assets,jsx):
    """Reconstruct GC29 public manifest from independently compiled scene.

    The JSX itself contains customer text, but no such text is exposed in the
    machine manifest or in our report.
    """
    need(isinstance(scene,dict) and scene.get('pages')==4,'SCENE_PAGES')
    need(scene.get('visual_approved') is False and scene.get('production_ready') is False,'SCENE_AUTHORITY')
    need(isinstance(assets,dict) and len(assets) in (12,13),'ASSET_COUNT')
    names=[row.get('file','').removeprefix('assets/') for row in scene.get('layers',[])]
    need(len(names)==len(assets) and len(set(names))==len(names),'ASSET_ROLES')
    need(set(names)==set(assets),'ASSET_NAMES')
    need(re.fullmatch(r'[a-f0-9]{64}',accepted) is not None,'ACCEPTED_SHA')
    for name,data in assets.items():
        need(re.fullmatch(r'[a-z0-9_]+\.png',name) is not None,'ASSET_NAME_INVALID')
        need(isinstance(data,bytes) and 0<len(data)<=150_000_000,'ASSET_BYTES_INVALID')
    obj={k:v for k,v in scene.items() if k not in ('greeting_text','sender_lines','front_lines')}
    obj['accepted_zip_sha256']=accepted
    obj['asset_sha256']={name:sha(data) for name,data in sorted(assets.items())}
    obj['jsx_sha256']=sha(jsx)
    return obj

def gc29_bytes(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
def generic_bytes(obj):
    return (json.dumps(obj,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode('ascii')

def changed_paths(left,right):
    """Only return JSON field paths (no client data) for a blocking difference."""
    result=[]
    def walk(a,b,path):
        if len(result)>=30:return
        if type(a)!=type(b):result.append(path+':TYPE');return
        if isinstance(a,dict):
            for key in sorted(set(a)|set(b)):
                p=path+'.'+key if path else key
                if key not in a or key not in b:result.append(p+':MISSING')
                else:walk(a[key],b[key],p)
        elif isinstance(a,list):
            if len(a)!=len(b):result.append(path+':COUNT')
            else:
                for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'['+str(i)+']')
        elif a!=b:result.append(path+':VALUE')
    walk(left,right,'')
    return result

def zap_manifest(root,client,bj,bg,report,sources):
    bi=bj.pinned(bj.BI_NAME,bj.BI_SHA,root)
    cross=bi.analyse(root,client)
    need(cross['status']=='PASS_ZAP_SCENE_ROLE_METADATA_PARITY','CROSSWALK_GATE')
    jsx,scene,s,ws=bj.rebuild_specialized_zap(root,client,bi,cross)
    assets=sources[bj.JOB]
    need(scene['job_id']==bj.JOB,'ZAP_JOB_ID')
    # GC47BJ check against complete frozen source ledger + bytes.
    run=s.native_run_dir(ws,bj.JOB,bj.ATTEMPT)
    origmanifest=run/'scene_manifest.json'
    need(regular(origmanifest) and bj.file_sha(origmanifest)==cross['reference']['native_scene_manifest_sha256'],
         'REFERENCE_MANIFEST_DRIFT')
    reference=origmanifest.read_bytes()
    old=json.loads(reference.decode('utf8'))
    bj.check_asset_bytes(assets,old,run/'assets')
    obj=manifest_object(scene,bg.ACCEPTED,assets,jsx)
    new=gc29_bytes(obj)
    fields=changed_paths(obj,old)
    return {'job_id':bj.JOB,'mode':'SPECIALIZED_ZAP','asset_count':len(assets),
      'computed_manifest_sha256':sha(new),'frozen_manifest_sha256':sha(reference),
      'manifest_fields_identical':not fields,'manifest_bytes_identical':new==reference,
      'mismatch_paths':fields,'jsx_sha256':sha(jsx),
      'status':'PASS_BYTE_IDENTICAL' if new==reference and not fields else 'REVIEW_MANIFEST_DIFFERENCES'}

def generic_manifests(root,client,bh,bg,report,sources):
    bf=bg.pinned_bf(root)
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    az=bb.az_module(root)
    t=az.module(root,bh.TRANSPORT_NAME,'gc47bk_transport')
    s,gc29=t.source_check()
    ws=s.workspace(client)
    vault=ws/'template_studio/native_asset_vault_v0_1'
    vm=gc29.verify_vault(vault)
    jobs,arts,archive=gc29.accepted_jobs(ws)
    need(bh.file_sha(archive)==bg.ACCEPTED,'ACCEPTED_SOURCE_CHANGED')
    byid={p['job_id']:p for p in report['profiles']}
    template=(Path(root)/'scripts/graphic_design_lab/greeting_cards'/bh.JSX_NAME).read_text('utf8')
    need(template.count('/*__GC29_SCENE__*/')==1,'TEMPLATE_MARKER')
    need(set(j['job_id'] for j in jobs)==set(GENERIC_MANIFESTS)|{ 'gdl_gc_zap_20261011' },'JOBS_SET')
    rows=[]
    for job in jobs:
        jid=job['job_id']
        if jid not in GENERIC_MANIFESTS:continue
        logo=az.logo_from_accepted(job,arts,archive)
        scene=gc29.compile_scene(job,vm,logo)
        gc29.bind_illustrator_signature(scene,vault,vm)
        jsx=template.replace('/*__GC29_SCENE__*/',json.dumps(scene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
        ledger=byid[jid]['source_bound_stage_map']
        obj,issues=bh.validate_work(scene,jsx,sources[jid],ledger,byid[jid]['generic_jsx_sha256'],bg.ACCEPTED)
        need(not issues,'GENERIC_GEOMETRY_DRIFT_'+jid)
        rebuilt=manifest_object(scene,bg.ACCEPTED,sources[jid],jsx)
        need(obj==rebuilt,'MANIFEST_COMPILER_CONTRACT_DRIFT_'+jid)
        wire=generic_bytes(rebuilt)
        rows.append({'job_id':jid,'mode':'GENERIC','asset_count':len(sources[jid]),
          'computed_manifest_sha256':sha(wire),'frozen_shadow_manifest_sha256':GENERIC_MANIFESTS[jid],
          'manifest_bytes_identical':sha(wire)==GENERIC_MANIFESTS[jid],
          'jsx_sha256':sha(jsx),
          'status':'PASS_DETERMINISTIC_SHADOW' if sha(wire)==GENERIC_MANIFESTS[jid] else 'REVIEW_MANIFEST_DIFFERENCES'})
    need(len(rows)==3,'GENERIC_COUNT')
    return rows

def inspect(root,client):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPO_REQUIRED')
    bj=read_pinned(root,BJ_NAME,BJ_SHA)
    bh=read_pinned(root,BH_NAME,BH_SHA)
    bg=bj.pinned(bj.BG_NAME,bj.BG_SHA,root)
    bf=bg.pinned_bf(root)
    report=bf.inspect(root,client)
    bg.validate_report(report)
    sources=bg.verified_sources(root,client,bf,report)
    need(set(sources)==bh.REQUIRED,'FOUR_ASSET_SETS')
    rows=[zap_manifest(root,client,bj,bg,report,sources)]
    rows+=generic_manifests(root,client,bh,bg,report,sources)
    rows.sort(key=lambda x:x['job_id'])
    valid=all(r['manifest_bytes_identical'] for r in rows)
    result={'schema':'gdl_gc47bk_native_manifest_rebuild_r001',
      'status':'PASS_FOUR_MANIFESTS_REBUILT_FROM_SOURCES_NO_NATIVE' if valid else 'REVIEW_FOUR_MANIFESTS_NOT_IDENTICAL',
      'accepted_zip_sha256':bg.ACCEPTED,'shared_release_id':bg.RELEASE,
      'profiles':rows,'native_dispatch':False,'windows_contacted':False,'new_native_attempt':False,
      'client_mutated':False,'git_mutated':False,'shared_release_active':False,'queue_enabled':False,
      'production_ready':False,'visual_approved':False,'pixel_parity':'UNVERIFIED_NO_ILLUSTRATOR',
      'remaining_gates':['LIVE_SHARED_CONSUMER_NOT_SWITCHED','NATIVE_PIXEL_PARITY_UNVERIFIED',
       'APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED','EXTERNAL_CLEAN_RESTORE_UNVERIFIED','QUEUE_DISABLED']}
    tmp=root/'tmp';need(directory(tmp),'TMP_REQUIRED')
    out=tmp/EVIDENCE;need(not out.exists() and not out.is_symlink(),'REPORT_EXISTS')
    data=(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf8')
    fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',data)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None and z.namelist()==['REPORT.json'],'ZIP_CRC')
    return result,out

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('check','inspect'),required=True)
    ap.add_argument('--client-name');ns=ap.parse_args(argv)
    try:
        read_pinned(ROOT,BJ_NAME,BJ_SHA)
        read_pinned(ROOT,BH_NAME,BH_SHA)
        if ns.mode=='check':
            print('GC47BK_CHECK=PASS_PINNED_COMPILERS_NO_WINDOWS');return 0
        need(isinstance(ns.client_name,str) and ns.client_name.strip(),'CLIENT_REQUIRED')
        result,out=inspect(ROOT,ns.client_name)
        for row in result['profiles']:
            print('GC47BK_PROFILE='+row['job_id']+' MANIFEST='+row['status'])
        print('GC47BK_STATUS='+result['status'])
        print('GC47BK_PIXEL_PARITY=UNVERIFIED')
        print('GC47BK_EVIDENCE='+str(out))
        print('GC47BK_NO_WINDOWS_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_NO_QUEUE=TRUE')
        return 0 if result['status'].startswith('PASS_') else 2
    except Exception as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC47BK=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:120],file=sys.stderr)
        print('GC47BK_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
