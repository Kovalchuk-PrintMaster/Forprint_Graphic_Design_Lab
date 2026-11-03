#!/usr/bin/env python3
"""GC47BG: materialize four *ephemeral* shared-design stage asset sets.

Guarded shadow integration: reads durable immutable GC47BE, client-specific variable
assets only from verified accepted sources, revalidates via GC47BF; no native
attempts, Windows SSH, client writes, rendering, queue or activation.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, stat, tempfile, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
CAN=Path(__file__).resolve().parent
BF='gc47bf_shared_scene_stage_parity_r001.py'
BF_SHA='d5a5b58b6778885288c1fdfc31e626fbe98a5b9b6c47fa9a3bc86521564639e1'
RELEASE='efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83'
ACCEPTED='90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
EXPECTED={
 'gdl_gc_zap_20261011':('bb3b919d2b5623ac870ae3fdbb4d8d4aa9fcac3875fe37a65e1db3923b4b93bc',12),
 'gdl_gc_apa_20261011':('f4066e725e947d5a5c865e40683270b910cb6c27eda9f1f133dc891ab1bfd7da',12),
 'gdl_gc_deg_20261011':('c8346efe2b9148b1417ef157595be73339d4679251cf9f4eb342242929ae42e0',12),
 'gdl_gc_bas_20261011':('053c1b44459b9a22e1b72b6dcb3fac4d47cfaa4cfdeef7ca306de546f40d1cb0',13),
}
EVIDENCE='gc47bg_shared_stage_bridge_evidence_r001.zip'
class Blocked(RuntimeError):pass
def need(cond,code):
    if not cond:raise Blocked(code)
def sha_bytes(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def regular(path):
    try:return stat.S_ISREG(Path(path).lstat().st_mode)
    except OSError:return False
def directory(path):
    try:return stat.S_ISDIR(Path(path).lstat().st_mode) and not Path(path).is_symlink()
    except OSError:return False

def pinned_bf(root=ROOT):
    root=Path(root)
    need(root.name=='forprint_graphic_design_lab' and directory(root/'.git'),'GDL_REPOSITORY')
    p=root/'scripts/graphic_design_lab/greeting_cards'/BF
    need(regular(p) and file_sha(p)==BF_SHA,'GC47BF_SOURCE_DRIFT')
    spec=importlib.util.spec_from_file_location('gc47bg_pinned_bf',p)
    need(spec is not None and spec.loader is not None,'GC47BF_IMPORT')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def validate_report(report):
    need(report.get('status')=='PASS_FOUR_PROFILE_SHARED_STAGE_SOURCE_PARITY_NO_NATIVE','SHADOW_STATUS')
    need(report.get('shared_release_id')==RELEASE and report.get('accepted_zip_sha256')==ACCEPTED,'SOURCE_ID_DRIFT')
    need(report.get('fixed_roles')==10 and report.get('variable_photo') is True,'COMMON_VARIABLE_REGRESSION')
    for k in ('native_dispatched','gc47ax_consumer_switched','gc47bc_consumer_switched','shared_release_activated',
              'production_ready','visual_approved','queue_enabled'):
        need(report.get(k) is False,'UNEXPECTED_AUTHORITY_'+k)
    need(report.get('all_generic_jsx_unchanged') is True and
         report.get('native_scene_pixel_parity')=='UNVERIFIED','NATIVE_PARITY_INCORRECTLY_CLAIMED')
    ps=report.get('profiles');need(isinstance(ps,list) and len(ps)==4,'PROFILE_COUNT')
    need(set(p['job_id'] for p in ps)==set(EXPECTED),'PROFILE_SET')
    for p in ps:
        jid=p['job_id'];digest,n=EXPECTED[jid]
        ledger=p['source_bound_stage_map']
        need(p['generic_jsx_sha256']==digest and p['generic_jsx_unchanged'] is True,'GENERIC_JSX_DRIFT_'+jid)
        need(len(ledger)==p['asset_count_to_stage']==n,'STAGE_COUNT_'+jid)
        need(len(set(a['asset_name'] for a in ledger))==n,'STAGE_NAME_COLLISION_'+jid)
        need(len(set(a['role'] for a in ledger))==n,'STAGE_ROLE_COLLISION_'+jid)
        need(sum(a['source']=='COMMON_DURABLE_RELEASE' for a in ledger)==10,'COMMON_COUNT_'+jid)
        need(p['photo_binding']==('JOB_OVERRIDE' if jid.endswith('_zap_20261011') else 'DEFAULT_CATALOG'),
             'PHOTO_PROVENANCE_'+jid)
        for a in ledger:
            need(isinstance(a.get('sha256'),str) and re.fullmatch(r'[0-9a-f]{64}',a['sha256']), 'ASSET_SHA_FORMAT')
            need(a['asset_name']==Path(a['asset_name']).name and a['asset_name'].endswith('.png') and
                 len(a['asset_name'])<=96,'ASSET_PATH_UNSAFE')
    return True

def verified_sources(root,client,bf,report):
    """Map every stage slot to immutable durable resource, or verified job media."""
    be=bf.load('gc47be_shared_asset_resolver_r001.py',root)
    bb=bf.load('gc47bb_source_bound_geometry_proof_r001.py',root)
    y=bf.load('gc47y_review_amendment_r001.py',root)
    store=be.check_store(root)
    mf=be.safe_manifest(store,RELEASE,be.SCHEMA)
    az=bb.az_module(root)
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bg_t')
    s,gc29=t.source_check()
    ws=s.workspace(client)
    jobs,arts,archive=gc29.accepted_jobs(ws)
    need(bf.file_sha(archive)==ACCEPTED,'ACCEPTED_SOURCE_CHANGED')
    by_id={p['job_id']:p for p in report['profiles']}
    need(set(p['job_id'] for p in jobs)==set(EXPECTED),'CLIENT_JOBS_CHANGED')
    routes={}
    for job in jobs:
        jid=job['job_id'];p=by_id[jid]
        logo=az.logo_from_accepted(job,arts,archive)
        override=None
        if jid=='gdl_gc_zap_20261011':override,_=y.check_sources(ws,job,archive)
        source_bytes={}
        for slot in p['source_bound_stage_map']:
            name=slot['asset_name'];kind=slot['source']
            if kind in ('COMMON_DURABLE_RELEASE','DEFAULT_CATALOG','COMMON_DURABLE_SIGNATURE'):
                path=store/RELEASE/'assets'/name
                need(regular(path),'DURABLE_ASSET_MISSING_'+name)
                data=path.read_bytes()
            elif kind=='JOB_OVERRIDE':
                need(override is not None and regular(override),'ZAP_PHOTO_PROOF_MISSING')
                data=override.read_bytes()
            elif kind=='ACCEPTED_JOB_BRANDING':
                need(jid=='gdl_gc_bas_20261011' and isinstance(logo,bytes),'BRANDING_PROOF_MISSING')
                data=logo
            elif kind=='DERIVED_FROM_COMMON_SVG':
                svg=store/RELEASE/'assets'/mf['signature_sources']['GRIGO']
                need(regular(svg) and bf.file_sha(svg)==slot['source_sha256'],'SIGNATURE_SVG_DRIFT')
                data=gc29.rasterize_grigo_signature_svg(svg.read_bytes())
            else:raise Blocked('STAGE_SOURCE_NOT_SUPPORTED')
            need(sha_bytes(data)==slot['sha256'],'MATERIALIZED_SOURCE_SHA_DRIFT_'+jid+'_'+name)
            need(name not in source_bytes,'DUPLICATE_STAGE_ASSET')
            source_bytes[name]=data
        routes[jid]=source_bytes
    return routes

def materialize_one(folder,ledger,source_bytes):
    """Stage verified bytes only in a private disposable directory; no persistent dependency."""
    folder=Path(folder)
    need(directory(folder) and stat.S_IMODE(folder.stat().st_mode)==0o700,'STAGING_DIR_NOT_PRIVATE')
    need(len(ledger)==len(source_bytes) and set(source_bytes)=={a['asset_name'] for a in ledger},'MATERIALIZED_ROLE_SET')
    result=[]
    for slot in sorted(ledger,key=lambda a:a['asset_name']):
        name=slot['asset_name'];data=source_bytes[name]
        need(isinstance(data,bytes) and 0<len(data)<=150*1024*1024,'ASSET_SIZE')
        need(sha_bytes(data)==slot['sha256'],'STAGE_SOURCE_SHA_'+name)
        path=folder/name
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
        fd=os.open(path,flags,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush()
        need(regular(path) and file_sha(path)==slot['sha256'],'STAGE_READBACK_SHA_'+name)
        result.append({'role':slot['role'],'asset_name':name,'sha256':slot['sha256'],
                       'source':slot['source'],'bbox_mm':slot['bbox_mm'],'size_bytes':len(data)})
    return result

def run_shadow(root,client):
    root=Path(root);bf=pinned_bf(root)
    report=bf.inspect(root,client)
    validate_report(report)
    sources=verified_sources(root,client,bf,report)
    tmp=root/'tmp';need(directory(tmp),'TMP_UNAVAILABLE')
    output=tmp/EVIDENCE;need(not output.exists() and not output.is_symlink(),'EVIDENCE_ALREADY_EXISTS')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='gc47bg_ephemeral_',dir=tmp) as stage:
        os.chmod(stage,0o700)
        for profile in report['profiles']:
            jid=profile['job_id'];folder=Path(stage)/jid;folder.mkdir(mode=0o700)
            material=materialize_one(folder,profile['source_bound_stage_map'],sources[jid])
            need(len(material)==EXPECTED[jid][1],'MATERIALIZED_COUNT')
            rows.append({'job_id':jid,'profile_generic_jsx_sha256':profile['generic_jsx_sha256'],
                         'stage_asset_count':len(material),'photo_binding':profile['photo_binding'],
                         'stage_ledger':material,'materialized_sha_verified':True})
    # All raw staged client media is now removed; only metadata receipt remains.
    result={'schema':'gdl_gc47bg_shared_stage_bridge_shadow_r001',
            'status':'PASS_SHARED_RELEASE_BYTES_MATERIALIZED_AND_REMOVED_NO_NATIVE',
            'release_id':RELEASE,'accepted_zip_sha256':ACCEPTED,'profiles':rows,
            'all_generic_jsx_unchanged':True,'all_stage_bytes_sha_verified':True,
            'ephemeral_stage_removed':True,'render_parity':'UNVERIFIED_NATIVE_NOT_RUN',
            'specialized_zap_parity':'NOT_PROVEN','native_dispatch':False,
            'consumer_switched':False,'shared_release_activated':False,'client_mutated':False,
            'git_mutated':False,'queue_enabled':False,'production_ready':False,'visual_approved':False,
            'remaining_gates':['NATIVE_BRIDGE_CANDIDATE_NOT_ACTIVATED','ZAP_NATIVE_PIXEL_PARITY_REQUIRED',
                               'APA_DEG_BAS_NATIVE_VISUAL_REVIEW_REQUIRED','EXTERNAL_RESTORE_NOT_TESTED',
                               'QUEUE_DISABLED']}
    payload=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode('utf8')+b'\n'
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'wb') as f:
        with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('REPORT.json',payload)
    with zipfile.ZipFile(output) as z:need(z.testzip() is None,'REPORT_ZIP_CRC')
    return result,output

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('check','shadow'))
    p.add_argument('--client-name')
    a=p.parse_args(argv)
    try:
        bf=pinned_bf()
        if a.mode=='check':
            bf.pins(ROOT)
            print('GC47BG_CHECK=PASS_FROZEN_BF_SOURCES_NO_NATIVE');return 0
        need(isinstance(a.client_name,str) and a.client_name.strip(),'CLIENT_REQUIRED')
        result,out=run_shadow(ROOT,a.client_name)
        for row in result['profiles']:
            print('GC47BG_PROFILE='+row['job_id']+' ASSETS='+str(row['stage_asset_count'])+' SHA=PASS',flush=True)
        print('GC47BG_STAGE=PASS_FOUR_EPHEMERAL_SOURCE_BOUND_ASSET_SETS',flush=True)
        print('GC47BG_EPHEMERAL_STAGE=REMOVED_AFTER_VERIFIED_READBACK',flush=True)
        print('GC47BG_NATIVE_PIXEL_PARITY=UNVERIFIED',flush=True)
        print('GC47BG_EVIDENCE='+str(out),flush=True)
        print('GC47BG_NO_NATIVE_NO_CLIENT_MUTATION_NO_QUEUE_NO_GIT=TRUE',flush=True)
        return 0
    except (Blocked,OSError,ValueError,TypeError,KeyError,ImportError,zipfile.BadZipFile) as e:
        msg=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47BG=BLOCKED_'+re.sub('[^A-Z0-9_]', '_',msg.upper())[:100],flush=True)
        print('GC47BG_NO_NATIVE_NO_CLIENT_WRITE=TRUE',flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())
