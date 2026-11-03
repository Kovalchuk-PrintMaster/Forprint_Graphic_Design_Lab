#!/usr/bin/env python3
"""GC47BF: source-bound, read-only stage-plan parity for four GDL greeting cards.

Uses immutable GC47BE release for fixed assets, signature source and default photo;
retains exact per-job ZAP photo and accepted BAS brand. It does NOT write JSX,
stage files, switch a consumer, use SSH, authorize native work or enable a queue.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, re, stat, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CAN=Path(__file__).resolve().parent
RELEASE='efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83'
PARENT='d2d4fa834c0f49a021e96b148aff69fa1df605d1a1a3adde738359a13b24d029'
ACCEPTED='90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
SHA={
  'gc47be_shared_asset_resolver_r001.py':'fe0dbe363d0f484349c4e9d947e1f0ae786e152f1ff5e6e5e672b55add1aa6be',
  'gc47bb_source_bound_geometry_proof_r001.py':'ade96e19fbfea59d80331a74c14f1a32710847cbf14318791ee1ec6c8f95a254',
  'gc47y_review_amendment_r001.py':'30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312',
  'gc29_native_four_page_v0_1.py':'c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42',
}
GENERIC_JSX={
'gdl_gc_zap_20261011':'bb3b919d2b5623ac870ae3fdbb4d8d4aa9fcac3875fe37a65e1db3923b4b93bc',
'gdl_gc_apa_20261011':'f4066e725e947d5a5c865e40683270b910cb6c27eda9f1f133dc891ab1bfd7da',
'gdl_gc_deg_20261011':'c8346efe2b9148b1417ef157595be73339d4679251cf9f4eb342242929ae42e0',
'gdl_gc_bas_20261011':'053c1b44459b9a22e1b72b6dcb3fac4d47cfaa4cfdeef7ca306de546f40d1cb0',
}
SCHEMA='gdl_gc47bf_shared_stage_plan_parity_r001'
EVIDENCE='gc47bf_shared_scene_parity_evidence_r001.zip'
class Blocked(ValueError):pass
def need(cond,code):
    if not cond: raise Blocked(code)
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1<<20),b''):h.update(c)
    return h.hexdigest()
def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False
def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode) and not p.is_symlink()
    except OSError:return False
def load(name,root=ROOT):
    p=root/'scripts/graphic_design_lab/greeting_cards'/name
    need(regular(p) and file_sha(p)==SHA[name],'DEPENDENCY_DRIFT_'+name)
    spec=importlib.util.spec_from_file_location('gc47bf_'+name.replace('.','_'),p)
    need(spec is not None and spec.loader is not None,'DEPENDENCY_IMPORT_'+name)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def pins(root=ROOT):
    need(root.name=='forprint_graphic_design_lab' and (root/'.git').is_dir(),'WRONG_GDL_REPOSITORY')
    for k in SHA:
        p=root/'scripts/graphic_design_lab/greeting_cards'/k
        need(regular(p) and file_sha(p)==SHA[k],'SOURCE_PIN_DRIFT_'+k)
    return True

def check_stage_bindings(scene,binding,manifest,legacy,store,generated,logo,photo_override=None):
    """Pure role comparison, requiring central bytes for all 10 fixed roles.

    Paths to prior client-vault files are read only for parity, not returned.
    Returned ledger has only logical names, SHA, origin category and bbox.
    """
    need(scene['pages']==4 and scene['page_mm']==[214,301],'PAGE_OR_GEOMETRY_DRIFT')
    need(scene['visual_approved'] is False and scene['production_ready'] is False,'AUTHORITY_DRIFT')
    fixed=binding['fixed'];need(len(fixed)==10 and 'P03.FLOWERS' not in fixed,'FIXED_PHOTO_ROLE_REGRESSION')
    layers=scene['layers'];roles={x['role']:x for x in layers}
    need(len(roles)==len(layers),'DUPLICATED_ROLES')
    need(set(roles)==set(fixed)|{'P03.FLOWERS','P04.SIGNATURE'}|({'P01.RECIPIENT_BRANDING'} if logo is not None else set()),'ROLE_SET')
    ledger=[]
    for role,meta in sorted(fixed.items()):
        layer=roles[role];name=Path(meta['path']).name
        need(layer['file']=='assets/'+name,'COMMON_ASSET_FILENAME_DRIFT_'+role)
        need(layer['bbox_mm']==meta['bbox_mm'],'COMMON_GEOMETRY_DRIFT_'+role)
        need(meta['sha256']==manifest['assets'][name]['sha256']==legacy['assets'][name]['sha256'],'COMMON_SHA_DIFF_'+role)
        path=Path(meta['path']);need(regular(path) and file_sha(path)==meta['sha256'],'COMMON_DURABLE_BYTES_DRIFT_'+role)
        need(layer['kind']==manifest['assets'][name]['kind'],'COMMON_KIND_DRIFT_'+role)
        ledger.append({'role':role,'asset_name':name,'sha256':meta['sha256'],'source':'COMMON_DURABLE_RELEASE','bbox_mm':layer['bbox_mm']})
    photo=roles['P03.FLOWERS'];pm=binding['photo'];need(photo['file']=='assets/p03_flowers.png','PHOTO_STAGE_SLOT')
    if pm['source']=='DEFAULT_CATALOG':
        need(photo_override is None and regular(Path(pm['path'])) and file_sha(Path(pm['path']))==pm['sha256'],'DEFAULT_PHOTO_DRIFT')
        need(pm['sha256']==manifest['assets']['p03_flowers.png']['sha256']==legacy['assets']['p03_flowers.png']['sha256'],'DEFAULT_PHOTO_SHA')
        need(photo['bbox_mm']==manifest['assets']['p03_flowers.png']['bbox_mm'],'DEFAULT_PHOTO_BBOX')
    elif pm['source']=='JOB_OVERRIDE':
        need(photo_override is not None and regular(photo_override) and file_sha(photo_override)==pm['sha256'],'JOB_PHOTO_NOT_SOURCE_VERIFIED')
        need(pm['sha256'] != manifest['assets']['p03_flowers.png']['sha256'],'JOB_OVERRIDE_MUST_BE_DIFFERENT')
    else: raise Blocked('PHOTO_SOURCE_UNSUPPORTED')
    ledger.append({'role':'P03.FLOWERS','asset_name':'p03_flowers.png','sha256':pm['sha256'],
                   'source':pm['source'],'bbox_mm':photo['bbox_mm']})
    sig=roles['P04.SIGNATURE'];sm=binding['signature'];sname=Path(sm['path']).name
    need(regular(Path(sm['path'])) and file_sha(Path(sm['path']))==sm['sha256'],'SIGNATURE_DURABLE_DRIFT')
    need(sm['sha256']==manifest['assets'][sname]['sha256']==legacy['assets'][sname]['sha256'],'SIGNATURE_SOURCE_PARITY')
    if sname.endswith('.svg'):
        need(sig['file']=='assets/p04_grigo_signature.png' and sig.get('source_graphic_sha256')==sm['sha256'] and
             'p04_grigo_signature.png' in generated,'DERIVED_GRIGO_SOURCE_DRIFT')
        # Real output is checked independently against centralized SVG in caller.
        staged_sha=sha_bytes(generated['p04_grigo_signature.png'])
        source='DERIVED_FROM_COMMON_SVG'
    else:
        need(sig['file']=='assets/'+sname and not generated,'HERASYMENKO_SOURCE_DRIFT')
        staged_sha=sm['sha256'];source='COMMON_DURABLE_SIGNATURE'
    need(sig['bbox_mm']==sm['bbox_mm'],'SIGNATURE_BBOX_DRIFT')
    ledger.append({'role':'P04.SIGNATURE','asset_name':Path(sig['file']).name,'sha256':staged_sha,
                   'source':source,'source_sha256':sm['sha256'],'bbox_mm':sig['bbox_mm']})
    if logo is not None:
        brand=roles['P01.RECIPIENT_BRANDING']
        need(brand['file']=='assets/recipient_branding.png' and brand['bbox_mm']==manifest['recipient_brand_bbox_mm'] and
             brand['kind']=='raster','BRANDING_GEOMETRY_DRIFT')
        ledger.append({'role':'P01.RECIPIENT_BRANDING','asset_name':'recipient_branding.png',
                       'sha256':sha_bytes(logo),'source':'ACCEPTED_JOB_BRANDING','bbox_mm':brand['bbox_mm']})
    need(len(ledger)==len(layers),'STAGE_PLAN_INCOMPLETE')
    return ledger

def inspect(root,client):
    pins(root)
    be=load('gc47be_shared_asset_resolver_r001.py',root)
    bb=load('gc47bb_source_bound_geometry_proof_r001.py',root)
    y=load('gc47y_review_amendment_r001.py',root)
    # Verify both immutable releases and their parent relationship from durable state.
    store=be.check_store(root)
    manifest=be.safe_manifest(store,RELEASE,be.SCHEMA)
    old=be.safe_manifest(store,PARENT,'gdl_gc47bd_shared_design_release_v0_1')
    need(manifest['parent_release_id']==PARENT,'RELEASE_PARENT_CHANGED')
    need(manifest['common_roles']=={k:old['common_roles'][k] for k in manifest['common_roles']},'FIXED_ROLE_MAPPING_CHANGED')
    need(set(manifest['common_roles'])==set(be.read_contract(root)['fixed_roles']),'FIXED_ROLE_CONTRACT_DRIFT')
    for name in manifest['assets']:
        need(manifest['assets'][name]==old['assets'][name],'PARENT_ASSET_CHANGED_'+name)
    # Rebuild historical generic JSX candidates in memory for all four.
    historical=bb.native_candidates(root,client)
    need(historical['status']=='PASS_FOUR_GENERIC_JSX_CANDIDATES_GEOMETRY_TRIAGED_NON_NATIVE','GENERIC_SOURCE_PROOF_MISSING')
    map_hist={x['job_id']:x for x in historical['profiles']}
    need(set(map_hist)==set(GENERIC_JSX),'GENERIC_PROFILE_SET')
    az=bb.az_module(root)
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bf_t')
    s,gc29=t.source_check()
    ws=s.workspace(client);vault=ws/'template_studio/native_asset_vault_v0_1'
    legacy=gc29.verify_vault(vault);jobs,arts,archive=gc29.accepted_jobs(ws)
    need(file_sha(archive)==ACCEPTED,'ACCEPTED_JOB_ARCHIVE_CHANGED')
    need(set(x['job_id'] for x in jobs)==set(GENERIC_JSX),'JOB_ID_SET')
    template=gc29.TEMPLATE.read_text('utf8');need(template.count('/*__GC29_SCENE__*/')==1,'JSX_TEMPLATE_MARKER')
    rows=[]
    for job in jobs:
        jid=job['job_id'];brand=az.logo_from_accepted(job,arts,archive)
        scene=gc29.compile_scene(job,legacy,brand)
        generated=gc29.bind_illustrator_signature(scene,vault,legacy)
        jsx=template.replace('/*__GC29_SCENE__*/',json.dumps(scene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
        need(sha_bytes(jsx)==GENERIC_JSX[jid]==map_hist[jid]['jsx_sha256'],'GENERIC_JSX_CHANGED_'+jid)
        family=scene['family'];signature=scene['signature']
        verified_photo=None
        if jid==be.ZAP:
            verified_photo,_=y.check_sources(ws,job,archive)
            y.amend_scene(scene)  # Shadow only. Historical ZAP amend is not generic JSX parity.
        job_resolve={'family':family,'signature':signature,'recipient_brand_present':brand is not None}
        if verified_photo is not None:
            job_resolve['photo_override']={'sha256':y.FLOWER_NEW,'status':'VERIFIED_SOURCE_BOUND'}
        binding=be.resolve_for_job(store,RELEASE,job_resolve)
        need(binding['release_id']==RELEASE and binding['native_enabled'] is False,'CONSUMER_AUTHORITY')
        ledger=check_stage_bindings(scene,binding,manifest,legacy,store,generated,brand,verified_photo)
        if signature=='GRIGO':
            actual_png=gc29.rasterize_grigo_signature_svg(Path(binding['signature']['path']).read_bytes())
            need(sha_bytes(actual_png)==sha_bytes(generated['p04_grigo_signature.png']),'CENTRAL_SVG_RASTER_PARITY')
        expected=set(('COMMON_DURABLE_RELEASE','DEFAULT_CATALOG','JOB_OVERRIDE','COMMON_DURABLE_SIGNATURE','DERIVED_FROM_COMMON_SVG','ACCEPTED_JOB_BRANDING'))
        need(set(x['source'] for x in ledger).issubset(expected),'STAGE_PLAN_SOURCE')
        rows.append({'job_id':jid,'family':family,'signature':signature,'page_count':4,
                     'fixed_role_count':10,'asset_count_to_stage':len(ledger),
                     'generic_jsx_sha256':sha_bytes(jsx),'generic_jsx_unchanged':True,
                     'photo_binding':binding['photo']['source'],'photo_sha256':binding['photo']['sha256'],
                     'signature_staged_sha256':next(x['sha256'] for x in ledger if x['role']=='P04.SIGNATURE'),
                     'recipient_brand_present':brand is not None,
                     'source_bound_stage_map':ledger,'render_parity':'UNVERIFIED_NATIVE_NOT_RUN',
                     'specialized_zap_versioned_jsx_parity':'NOT_ASSERTED' if jid==be.ZAP else 'NOT_APPLICABLE'})
    need(len(rows)==4,'PROFILE_COUNT')
    return {'schema':SCHEMA,'status':'PASS_FOUR_PROFILE_SHARED_STAGE_SOURCE_PARITY_NO_NATIVE',
            'shared_release_id':RELEASE,'parent_release_id':PARENT,
            'accepted_zip_sha256':ACCEPTED,'fixed_roles':10,'variable_photo':True,
            'profiles':rows,'stage_map_is_shadow_only':True,'all_generic_jsx_unchanged':True,
            'native_scene_pixel_parity':'UNVERIFIED','gc47ax_consumer_switched':False,
            'gc47bc_consumer_switched':False,'shared_release_activated':False,
            'queue_enabled':False,'client_mutated':False,'git_mutated':False,
            'native_dispatched':False,'visual_approved':False,'production_ready':False,
            'remaining_gates':['EXPLICIT_VERSIONED_NATIVE_BRIDGE_SHADOW_REQUIRED',
                'ZAP_SPECIALIZED_NATIVE_RENDER_PARITY_REQUIRED',
                'APA_DEG_BAS_NATIVE_TYPOGRAPHY_CROP_BRANDING_REVIEW',
                'EXTERNAL_RESTORE_NOT_TESTED','QUEUE_DISABLED']}

def write_report(root,report):
    tmp=root/'tmp';need(directory(tmp),'TMP_DELIVERY_UNAVAILABLE')
    out=tmp/EVIDENCE;need(not out.exists() and not out.is_symlink(),'EVIDENCE_ALREADY_EXISTS')
    with out.open('xb') as f:
        with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED) as z:
            i=zipfile.ZipInfo('REPORT.json');i.external_attr=(0o100600<<16)
            z.writestr(i,json.dumps(report,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
    os.chmod(out,0o600)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None,'EVIDENCE_CRC_FAILURE')
    return out

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('check','inspect'),required=True)
    p.add_argument('--client-name')
    args=p.parse_args(argv)
    try:
        pins()
        if args.mode=='check':
            print('GC47BF_CHECK=PASS_PINNED_SOURCES_NO_CLIENT_NO_WINDOWS');return 0
        need(args.client_name and args.client_name.strip(),'CLIENT_REQUIRED')
        report=inspect(ROOT,args.client_name)
        for x in report['profiles']:
            print('GC47BF_PROFILE='+x['job_id']+' STAGED_ASSETS='+str(x['asset_count_to_stage'])+' PHOTO='+x['photo_binding'],flush=True)
        out=write_report(ROOT,report)
        print('GC47BF_STAGE_PARITY=PASS_FOUR_SOURCE_BOUND_PLANS_NO_NATIVE',flush=True)
        print('GC47BF_GENERIC_JSX=PASS_BYTE_IDENTICAL_REFERENCE',flush=True)
        print('GC47BF_NATIVE_RENDER_PARITY=UNVERIFIED',flush=True)
        print('GC47BF_EVIDENCE='+str(out),flush=True)
        print('GC47BF_NO_CLIENT_WRITE_NO_NATIVE_NO_GIT_NO_QUEUE=TRUE',flush=True)
        return 0
    except (Blocked,ValueError,OSError,TypeError,KeyError,ImportError,zipfile.BadZipFile,json.JSONDecodeError) as e:
        label=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47BF=BLOCKED_'+re.sub('[^A-Z0-9_]', '_',label.upper())[:110],file=sys.stderr,flush=True)
        print('GC47BF_NO_NATIVE_NO_CLIENT_WRITE=TRUE',file=sys.stderr,flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())
