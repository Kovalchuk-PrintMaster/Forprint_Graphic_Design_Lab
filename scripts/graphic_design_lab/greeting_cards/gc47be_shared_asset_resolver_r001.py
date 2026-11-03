#!/usr/bin/env python3
"""GC47BE shared-design v0.2: persistent immutable common assets vs per-job media.

Does NOT modify GC47AX/GC47BC, change active design, create native attempt,
write client files, or dispatch to PREPRESS. Dedicated safe resolver API for later bridge.
"""
from __future__ import annotations
import argparse, ast, hashlib, importlib.util, json, os, shutil, stat, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
BD = BASE/'gc47bd_shared_scene_contract_r001.py'
BD_SHA = '26ad8135522db4c7972283c842fd67f3d692d840efde4a111ba9ba16a7f64b77'
GC47Y = BASE/'gc47y_review_amendment_r001.py'
GC47Y_SHA = '30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312'
CONTRACT = ROOT/'coordination/graphic_design_lab/greeting_cards/shared_design/gc47be_common_variable_boundary_v0_2.json'
EXPECTED_PARENT = 'd2d4fa834c0f49a021e96b148aff69fa1df605d1a1a3adde738359a13b24d029'
ZAP = 'gdl_gc_zap_20261011'
JOBS = ('gdl_gc_zap_20261011','gdl_gc_apa_20261011','gdl_gc_deg_20261011','gdl_gc_bas_20261011')
SCHEMA = 'gdl_gc47be_shared_design_release_v0_2'
EVIDENCE_NAME = 'gc47be_common_variable_parity_evidence_r001.zip'

class Blocked(RuntimeError): pass

def need(condition, code):
    if not condition: raise Blocked(code)

def sha_bytes(b): return hashlib.sha256(b).hexdigest()

def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def digest(obj):return sha_bytes(json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('utf8'))

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False

def read_contract(root=ROOT):
    p=root/'coordination/graphic_design_lab/greeting_cards/shared_design/gc47be_common_variable_boundary_v0_2.json'
    need(regular(p) and p.stat().st_size < 20000,'CONTRACT_NOT_REGULAR')
    o=json.loads(p.read_text('utf8'))
    need(o['schema']=='gdl_gc47be_common_variable_boundary_v0_2' and o['status']=='CANDIDATE_NON_ACTIVE','CONTRACT_SCHEMA')
    need(o['page_mm']==[214,301] and o['physical_pages']==4,'PAGE_SIZE')
    fixed=o['fixed_roles']; variables=o['variable_slots']
    need(set(fixed)=={'P01.PAPER','P01.FRAME','P01.SENDER_LOGO','P02.LOCKED_BASE','P02.WATERMARK','P03.PAPER','P03.FRAME','P04.PAPER','P04.WATERMARK','P04.FRAME'},'PHOTO_MUST_NOT_BE_FIXED')
    need(len(set(variables))==len(variables) and {'P03.FLOWERS','P04.SIGNATURE','P04.GREETING','P04.SENDER_LINES','P01.OCCASION_TEXT','P01.RECIPIENT_BRANDING'}.issubset(set(variables)),'PHOTO_VARIABLE_REQUIRED')
    need(o['photo_source_policy']=='VERIFIED_DEFAULT_OR_JOB_BOUND_SHA256_OVERRIDE','PHOTO_PROVENANCE_POLICY')
    need(o['native_activation'] is False and o['queue_activation'] is False and o['production_ready'] is False,'NO_ACTIVATION')
    return o

def import_bd(root=ROOT):
    p=root/'scripts/graphic_design_lab/greeting_cards/gc47bd_shared_scene_contract_r001.py'
    need(regular(p) and file_sha(p)==BD_SHA,'GC47BD_SOURCE_DRIFT')
    s=importlib.util.spec_from_file_location('gc47be_pinned_bd',p)
    need(s is not None and s.loader is not None,'GC47BD_LOAD_FAILED')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m

def historical_zap_reference(root=ROOT):
    p=root/'scripts/graphic_design_lab/greeting_cards/gc47y_review_amendment_r001.py'
    need(regular(p) and file_sha(p)==GC47Y_SHA,'GC47Y_SOURCE_DRIFT')
    tree=ast.parse(p.read_text('utf8'))
    found={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            name=node.targets[0].id
            if name in {'FLOWER_OLD','FLOWER_NEW','JOB','ACCEPTED_ZIP'}:
                found[name]=ast.literal_eval(node.value)
    need(found.get('JOB')==ZAP and found.get('FLOWER_OLD') and found.get('FLOWER_NEW') and
         found['FLOWER_OLD']!=found['FLOWER_NEW'],'ZAP_PHOTO_DELTA_UNPROVEN')
    for key in ('FLOWER_OLD','FLOWER_NEW','ACCEPTED_ZIP'):
        need(isinstance(found[key],str) and len(found[key])==64 and all(x in '0123456789abcdef' for x in found[key]),'ZAP_PIN_FORMAT')
    return found

def store_path(root=ROOT):
    return root.parent/'.state'/'graphic_design_lab'/'shared_design'/'releases'

def check_store(root=ROOT):
    # Only read a pre-existing durable private store. Never create directories in inspect/check.
    g=root.parent/'.state'/'graphic_design_lab'
    for p in (g,g/'shared_design',g/'shared_design'/'releases'):
        need(directory(p) and not p.is_symlink(),'DURABLE_STORE_MISSING_OR_LINK')
        s=p.stat()
        need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'DURABLE_STORE_OWNER_OR_MODE')
    need('tmp' not in root.parent.parts and 'tmp' not in g.parts,'DURABLE_STORE_IN_TMP')
    return g/'shared_design'/'releases'

def safe_manifest(store,release_id,expected_schema):
    need(len(release_id)==64 and all(c in '0123456789abcdef' for c in release_id),'RELEASE_ID')
    p=store/release_id
    need(directory(p) and not p.is_symlink(),'RELEASE_DIR_MISSING_OR_LINK')
    mf=p/'release.json'
    need(regular(mf) and mf.stat().st_size<100000,'RELEASE_MANIFEST_MISSING')
    obj=json.loads(mf.read_text('utf8'))
    need(obj.get('schema')==expected_schema and digest(obj)==release_id,'RELEASE_DIGEST_OR_SCHEMA')
    need(obj.get('activation')=='NOT_ACTIVE' and obj.get('production_ready') is False and obj.get('visual_approved') is False,'RELEASE_UNEXPECTED_AUTHORITY')
    asset_dir=p/'assets'
    need(directory(asset_dir) and not asset_dir.is_symlink(),'RELEASE_ASSETS_DIR')
    need(set(q.name for q in asset_dir.iterdir())==set(obj['assets']),'RELEASE_ASSET_SET')
    for name,entry in obj['assets'].items():
        need(name==Path(name).name and name not in ('.','..'),'BAD_ASSET_NAME')
        f=asset_dir/name
        need(regular(f) and f.stat().st_size==entry['size_bytes'] and file_sha(f)==entry['sha256'],'ASSET_DRIFT_'+name)
    return obj

def derive_v2(old,contract,zap):
    need(old.get('schema')=='gdl_gc47bd_shared_design_release_v0_1','PARENT_SCHEMA')
    need(old['assets']['p03_flowers.png']['sha256']==zap['FLOWER_OLD'],'DEFAULT_PHOTO_NOT_ORIGINAL')
    need(set(old['common_roles'])==set(contract['fixed_roles'])|{'P03.FLOWERS'},'LEGACY_FIXED_ROLE_SET')
    need(old['common_roles']['P03.FLOWERS']==contract['photo_default_asset'],'LEGACY_PHOTO_ALIAS')
    common={k:old['common_roles'][k] for k in contract['fixed_roles']}
    need(set(common.values()).issubset(set(old['assets'])),'FIXED_MISSING_ASSETS')
    need(old['page_mm']==contract['page_mm'] and old['physical_pages']==contract['physical_pages'],'PAGES_DRIFT')
    need(set(old['signature_sources'])==set(contract['signature_variants']),'SIGNATURE_DRIFT')
    need(set(old['front_logo_bboxes_mm'])==set(contract['front_logo_modes']),'FRONT_LOGO_MODES')
    return {
        'schema':SCHEMA,'design_family':old['design_family'],'physical_pages':old['physical_pages'],
        'page_mm':old['page_mm'],'assets':old['assets'],'common_roles':common,
        'signature_sources':old['signature_sources'],'front_logo_bboxes_mm':old['front_logo_bboxes_mm'],
        'recipient_brand_bbox_mm':old['recipient_brand_bbox_mm'],
        'variable_role_sources':{'P03.FLOWERS':{'default_asset':contract['photo_default_asset'],
            'override_policy':contract['photo_source_policy']},
            'P04.SIGNATURE':{'selection':'PER_JOB_FROM_SHARED_SIGNATURE_CATALOG'}},
        'variable_slots':contract['variable_slots'], 'parent_release_id':EXPECTED_PARENT,
        'activation':'NOT_ACTIVE','visual_approved':False,'production_ready':False,
        'assets_origin':'GC47BD_PRIVATE_IMMUTABLE_RELEASE','client_specific_content_in_release':False}

def check_release_inputs(root=ROOT):
    contract=read_contract(root);bd=import_bd(root);zap=historical_zap_reference(root)
    store=check_store(root)
    old=safe_manifest(store,EXPECTED_PARENT,'gdl_gc47bd_shared_design_release_v0_1')
    new=derive_v2(old,contract,zap)
    return bd,store,old,new,zap

def seed_from_parent(store,new):
    # Immutable non-active sibling release. Copies exclusively from persistent prior release.
    rid=digest(new);dest=store/rid
    if dest.exists() or dest.is_symlink():
        need(not dest.is_symlink(),'DEST_RELEASE_SYMLINK')
        found=safe_manifest(store,rid,SCHEMA)
        need(found==new,'RELEASE_CONFLICT')
        return rid,'ALREADY_IDENTICAL'
    temporary=Path(tempfile.mkdtemp(prefix='.gc47be_seed_',dir=store))
    try:
        (temporary/'assets').mkdir(mode=0o700)
        src=store/EXPECTED_PARENT/'assets'
        for name,entry in new['assets'].items():
            from_file=src/name;to_file=temporary/'assets'/name
            need(regular(from_file) and file_sha(from_file)==entry['sha256'],'PARENT_CHANGED_DURING_SEED')
            with from_file.open('rb') as fin,to_file.open('xb') as fout:
                for chunk in iter(lambda:fin.read(1<<20),b''):fout.write(chunk)
            to_file.chmod(0o600)
            need(file_sha(to_file)==entry['sha256'],'SEED_SHA')
        mf=temporary/'release.json'
        mf.write_text(json.dumps(new,ensure_ascii=True,sort_keys=True,indent=2)+'\n','utf8')
        mf.chmod(0o600)
        # Same verifier before and after atomic rename.
        os.rename(temporary,dest)
        found=safe_manifest(store,rid,SCHEMA)
        need(found==new,'SEED_MANIFEST_MISMATCH')
        return rid,'SEEDED_NON_ACTIVE'
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def resolve_for_job(store,release_id,job):
    """The future consumers use this API, not a client-specific vault.

    Returns exact durable paths for fixed roles; P03 photo is a separate variable
    slot. No automatic choice of a different photo for a historical attempt.
    """
    manifest=safe_manifest(store,release_id,SCHEMA)
    need(job['family'] in manifest['front_logo_bboxes_mm'],'FRONT_VARIANT_UNSUPPORTED')
    need(job['signature'] in manifest['signature_sources'],'SIGNATURE_UNSUPPORTED')
    fixed={}
    for role,name in manifest['common_roles'].items():
        entry=manifest['assets'][name]
        fixed[role]={'path':str(store/release_id/'assets'/name),'sha256':entry['sha256'],
                     'bbox_mm':manifest['front_logo_bboxes_mm'][job['family']] if role=='P01.SENDER_LOGO' else entry['bbox_mm']}
    name=manifest['signature_sources'][job['signature']]
    signature={'path':str(store/release_id/'assets'/name),'sha256':manifest['assets'][name]['sha256'],
               'bbox_mm':manifest['assets'][name]['bbox_mm']}
    default_name=manifest['variable_role_sources']['P03.FLOWERS']['default_asset']
    photo=job.get('photo_override')
    if photo is not None:
        need(isinstance(photo,dict) and photo.get('status')=='VERIFIED_SOURCE_BOUND' and
             isinstance(photo.get('sha256'),str) and len(photo['sha256'])==64 and
             all(c in '0123456789abcdef' for c in photo['sha256']),'PHOTO_OVERRIDE_REQUIRES_SHA_RECEIPT')
        photo_binding={'source':'JOB_OVERRIDE','sha256':photo['sha256'],'requires_external_asset_verification':True}
    else:
        photo_binding={'source':'DEFAULT_CATALOG','sha256':manifest['assets'][default_name]['sha256'],
                       'path':str(store/release_id/'assets'/default_name),'requires_external_asset_verification':False}
    need(bool(job.get('recipient_brand_present'))==(job['family']=='RECIPIENT_BRANDING_OVERLAY'),'RECIPIENT_BRAND_SCOPE')
    return {'release_id':release_id,'fixed':fixed,'signature':signature,'photo':photo_binding,
            'visual_approved':False,'production_ready':False,'native_enabled':False}

def inspect_all(root,client):
    bd,store,old,new,zap=check_release_inputs(root)
    # Build current accepted-source scenes read only; never use a client vault as the runtime authority.
    original,old_report,_=bd.source_inventory(root,client)
    need(digest(original)==EXPECTED_PARENT and original==old,'CURRENT_ACCEPTED_VAULT_NOT_FROZEN_PARENT')
    rid=digest(new);exists=(store/rid).exists()
    if exists:
        installed=safe_manifest(store,rid,SCHEMA)
        need(installed==new,'INSTALLED_V2_DRIFT')
    rows=[]
    for old_job in old_report['profiles']:
        job_id=old_job['job_id'];need(job_id in JOBS,'JOB_SET')
        job={'family':old_job['family'],'signature':old_job['signature'],
             'recipient_brand_present':old_job['recipient_brand_present']}
        if job_id==ZAP:
            # Historical ZAP's post-source amendment must not silently regress to vault default.
            job['photo_override']={'sha256':zap['FLOWER_NEW'],'status':'VERIFIED_SOURCE_BOUND'}
        # If v2 not yet installed, use a pure in-memory view; no unsafe fallback to old path.
        if exists: binding=resolve_for_job(store,rid,job)
        else:
            need(job['family'] in new['front_logo_bboxes_mm'] and job['signature'] in new['signature_sources'],'PROFILE')
            binding={'fixed':{x:None for x in new['common_roles']},
                     'photo':{'source':'JOB_OVERRIDE' if job_id==ZAP else 'DEFAULT_CATALOG'}}
        need(len(binding['fixed'])==10 and 'P03.FLOWERS' not in binding['fixed'],'INVARIANT_ROLES')
        rows.append({'job_id':job_id,'family':job['family'],'signature':job['signature'],
                     'fixed_roles':len(binding['fixed']), 'photo_binding':binding['photo']['source'],
                     'photo_sha256':zap['FLOWER_NEW'] if job_id==ZAP else old['assets']['p03_flowers.png']['sha256']})
    need(len(rows)==4 and set(x['job_id'] for x in rows)==set(JOBS),'FOUR_PROFILES')
    return new,{'schema':'gdl_gc47be_common_variable_parity_evidence_r001',
       'status':'PASS_FIXED_VARIABLE_BOUNDARY_SOURCE_ATTESTED_NON_NATIVE',
       'parent_release_id':EXPECTED_PARENT,'new_release_id':rid,
       'old_release_seed':'VERIFIED','new_release_seed':'ALREADY_IDENTICAL' if exists else 'NOT_YET_SEEDED',
       'common_fixed_role_count':len(new['common_roles']),'asset_catalog_count':len(new['assets']),
       'photo_role':'P03.FLOWERS','photo_is_variable':True,
       'zap_reference':{'old_catalog_sha256':zap['FLOWER_OLD'],
                  'published_route_source_sha256':zap['FLOWER_NEW'],
                  'drift_class':'INTENDED_JOB_SPECIFIC_PHOTO_OVERRIDE_NOT_FIXED_ASSET'},
       'profiles':rows,'native_route_switched':False,'native_dispatch':False,
       'client_mutated':False,'git_mutated':False,'visual_approved':False,'production_ready':False,
       'remaining_gates':['GC47AX_NATIVE_CONSUMER_NOT_SWITCHED','GC47BC_NATIVE_CONSUMER_NOT_SWITCHED',
         'RENDER_PARITY_UNVERIFIED','RELEASE_NOT_ACTIVE','APA_DEG_BAS_NATIVE_REVIEW_UNVERIFIED',
         'AUTOMATED_QUEUE_DISABLED']}

def write_evidence(root,report):
    tmp=root/'tmp';need(directory(tmp) and not tmp.is_symlink(),'OUTPUT_TMP')
    path=tmp/EVIDENCE_NAME;need(not path.exists() and not path.is_symlink(),'EVIDENCE_EXISTS')
    with path.open('xb') as fh:
        with zipfile.ZipFile(fh,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('REPORT.json',json.dumps(report,ensure_ascii=True,sort_keys=True,indent=2)+'\n')
    return path

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=('check','inspect','seed'))
    p.add_argument('--client-name')
    p.add_argument('--confirm-non-active-seed',action='store_true')
    args=p.parse_args(argv)
    try:
        read_contract();import_bd();historical_zap_reference()
        if args.mode=='check':
            print('GC47BE_CHECK=PASS_BOUNDARY_SOURCES_NO_NATIVE');return 0
        need(isinstance(args.client_name,str) and bool(args.client_name.strip()),'CLIENT_REQUIRED')
        new,report=inspect_all(ROOT,args.client_name)
        print('GC47BE_BOUNDARY=PASS_TEN_FIXED_ROLES_P03_PHOTO_VARIABLE',flush=True)
        print('GC47BE_ZAP_PHOTO=PINNED_OVERRIDE_NOT_CATALOG_DEFAULT',flush=True)
        if args.mode=='seed':
            need(args.confirm_non_active_seed,'EXPLICIT_NON_ACTIVE_SEED_CONFIRMATION_REQUIRED')
            need(not (ROOT/'tmp'/EVIDENCE_NAME).exists(),'EVIDENCE_EXISTS_NO_SEED')
            store=check_store();rid,state=seed_from_parent(store,new)
            report['new_release_seed']=state
            print('GC47BE_SHARED_RELEASE='+state,flush=True)
            print('GC47BE_RELEASE_ID='+rid,flush=True)
        path=write_evidence(ROOT,report)
        print('GC47BE_EVIDENCE='+str(path),flush=True)
        print('GC47BE_NATIVE_DISPATCH=FALSE CLIENT_MUTATION=FALSE GIT_MUTATION=FALSE',flush=True)
        print('GC47BE_SHARED_RELEASE_ACTIVE=FALSE PRODUCTION_READY=FALSE',flush=True)
        return 0
    except Exception as e:
        print('GC47BE=BLOCKED_'+str(e).splitlines()[0][:170],flush=True)
        print('GC47BE_NO_NATIVE_NO_CLIENT_MUTATION_NO_GIT=TRUE',flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())
