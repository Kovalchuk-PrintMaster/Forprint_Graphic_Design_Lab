#!/usr/bin/env python3
"""GC47BD: one design catalog, four variable-data scenes. CANDIDATE only.

Use source-bound GC29 vault for inventory, then seed a *non-active*, immutable,
common GDL design release in persistent sibling .state; never change GC47AX,
private client artifacts, or Illustrator. No production route here.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,re,shutil,stat,tempfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
CONTRACT=ROOT/'coordination/graphic_design_lab/greeting_cards/shared_design/gc47bd_unified_scene_contract_v0_1.json'
GC29=ROOT/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py'
GC29_SHA='c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42'
SHARE=Path('/srv/smb/In_Progress/data')
JOBS=('gdl_gc_zap_20261011','gdl_gc_apa_20261011','gdl_gc_deg_20261011','gdl_gc_bas_20261011')
SCHEMA='gdl_gc47bd_shared_design_release_v0_1'
class Blocked(ValueError):pass
def need(v,code):
    if not v:raise Blocked('GC47BD_'+code)
def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False
def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False
def load_contract(root=ROOT):
    p=root/'coordination/graphic_design_lab/greeting_cards/shared_design/gc47bd_unified_scene_contract_v0_1.json'
    need(regular(p) and p.stat().st_size<100000,'CONTRACT_MISSING')
    obj=json.loads(p.read_text('utf8'))
    need(obj['schema']=='gdl_gc47bd_unified_scene_contract_v0_1','CONTRACT_SCHEMA')
    need(obj['page_mm']==[214,301] and obj['physical_pages']==4,'PAGE_GEOMETRY')
    need(set(obj['common_roles'])=={'P01.PAPER','P01.FRAME','P01.SENDER_LOGO','P02.LOCKED_BASE','P02.WATERMARK','P03.PAPER','P03.FLOWERS','P03.FRAME','P04.PAPER','P04.WATERMARK','P04.FRAME'},'COMMON_ROLE_SET')
    need(obj['runtime_activation'] is False and obj['production_ready'] is False,'ACTIVATION_FORBIDDEN')
    need(set(obj['signature_sources'])=={'GRIGO','HERASYMENKO'},'SIGNATURE_SOURCES')
    need(obj['front_logo_bboxes_mm']=={'STANDARD':[64.5,59.5,149.5,144.5],'RECIPIENT_BRANDING_OVERLAY':[69,39,145,115]},'LOGO_RULE')
    return obj

def gc29_module(root=ROOT):
    p=root/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py'
    need(regular(p) and file_sha(p)==GC29_SHA,'GC29_SOURCE_DRIFT')
    spec=importlib.util.spec_from_file_location('gc47bd_gc29',str(p))
    need(spec and spec.loader,'GC29_IMPORT')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def accepted_logo(job,artifact,archive):
    front=job['builder_v1']['front']
    if front['family']!='RECIPIENT_BRANDING_OVERLAY':return None
    info=front['recipient_branding'];rec=artifact['artifacts'][info['accepted_artifact_ref']]
    need(rec['sha256']==info['asset_sha256'],'BRANDING_SHA_BINDING')
    name=rec.get('path') or rec.get('archive_member')
    need(isinstance(name,str) and not name.startswith('/') and '..' not in Path(name).parts,'BRANDING_PATH')
    with zipfile.ZipFile(archive) as z:
        need(name in z.namelist(),'BRANDING_MISSING')
        data=z.read(name)
    need(len(data)<15_000_000 and sha(data)==rec['sha256'] and data.startswith(b'\x89PNG\r\n\x1a\n'),'BRANDING_BYTES')
    return data

def source_inventory(root,client):
    contract=load_contract(root);mod=gc29_module(root)
    need(isinstance(client,str) and len(client)<256 and client not in ('.','..') and all(ch not in client for ch in '/\\\x00'),'CLIENT')
    # Reuse pinned GC29 safe workspace and accepted-handoff guards.
    ws=mod.workspace(client)
    vault=ws/'template_studio/native_asset_vault_v0_1'
    manifest=mod.verify_vault(vault)
    jobs,artifact,archive=mod.accepted_jobs(ws)
    need(tuple(j['job_id'] for j in jobs)==JOBS,'ACCEPTED_JOBS_DRIFT')
    assets=manifest['assets']
    required=set(contract['common_roles'].values())|set(contract['signature_sources'].values())
    need(required.issubset(assets),'VAULT_ASSET_MISSING')
    catalog={}
    for name in sorted(required):
        entry=assets[name];p=vault/name
        need(regular(p) and file_sha(p)==entry['sha256'],'ASSET_SHA_DRIFT')
        catalog[name]={'sha256':entry['sha256'],'kind':entry['kind'],'bbox_mm':entry['bbox_mm'],'size_bytes':entry['size_bytes']}
    profiles=[];source_consistency={role:set() for role in contract['common_roles']}
    for job in jobs:
        logo=accepted_logo(job,artifact,archive)
        scene=mod.compile_scene(job,manifest,logo)
        need(scene['job_id']==job['job_id'] and scene['pages']==4,'SCENE_ID')
        need(scene['visual_approved'] is False and scene['production_ready'] is False,'SCENE_AUTHORITY')
        roles={layer['role']:layer for layer in scene['layers']}
        need(len(roles)==len(scene['layers']),'DUPLICATE_ROLE')
        for role,name in contract['common_roles'].items():
            need(role in roles and roles[role]['file']=='assets/'+name,'COMMON_ROLE_SOURCE_'+role)
            expected=contract['front_logo_bboxes_mm'][scene['family']] if role=='P01.SENDER_LOGO' else catalog[name]['bbox_mm']
            need(roles[role]['bbox_mm']==expected,'COMMON_ROLE_BBOX_'+role)
            source_consistency[role].add(name)
        sig=contract['signature_sources'][scene['signature']]
        need(roles['P04.SIGNATURE']['file']=='assets/'+sig,'SIGNATURE_SELECTOR')
        need(('P01.RECIPIENT_BRANDING' in roles)==(scene['family']=='RECIPIENT_BRANDING_OVERLAY'),'BRANDING_SELECTOR')
        if logo is not None:
            need(roles['P01.RECIPIENT_BRANDING']['bbox_mm']==contract['recipient_brand_bbox_mm'],'BRANDING_BBOX')
        # Keep every private greeting and sender line OUT of the evidence report.
        profiles.append({'job_id':job['job_id'],'family':scene['family'],'signature':scene['signature'],
            'occasion_kind':job['builder_v1']['front']['occasion']['kind'],
            'image_mode':scene['image_mode'],'sender_rows':len(scene['sender_lines']),
            'greeting_char_count':len(scene['greeting_text']),
            'recipient_brand_present':logo is not None,
            'common_asset_sources':len(contract['common_roles']),
            'shared_release_digest':None})
    need(all(len(values)==1 for values in source_consistency.values()),'DUPLICATED_OR_MIXED_COMMON_SOURCE')
    release={'schema':SCHEMA,'design_family':'four_page_greeting_card','physical_pages':4,'page_mm':[214,301],
        'assets':catalog,'common_roles':contract['common_roles'],
        'signature_sources':contract['signature_sources'],
        'front_logo_bboxes_mm':contract['front_logo_bboxes_mm'],
        'recipient_brand_bbox_mm':contract['recipient_brand_bbox_mm'],
        'activation':'NOT_ACTIVE','visual_approved':False,'production_ready':False,
        'assets_origin':'GC29_VERIFIED_PRIVATE_VAULT','client_specific_content_in_release':False}
    # Stable digest excludes paths, timestamps and private client identifiers.
    release_id=sha(json.dumps(release,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode())
    for p in profiles:p['shared_release_digest']=release_id
    report={'schema':'gdl_gc47bd_shared_design_proof_r001','status':'PASS_FOUR_PROFILES_ONE_SHARED_ASSET_CATALOG',
        'release_id':release_id,'release_activation':False,'profiles':profiles,
        'common_role_count':len(contract['common_roles']),'shared_asset_count':len(catalog),
        'asset_hashes':{k:v['sha256'] for k,v in catalog.items()},
        'front_logo_placement_modes':sorted(contract['front_logo_bboxes_mm']),
        'mutable_job_fields':contract['variable_fields'],
        'native_dispatch':False,'client_files_modified':False,'git_mutation':False,
        'remaining_gates':['CENTRAL_RELEASE_SEED_REQUIRED','NATIVE_BRIDGE_NOT_INTEGRATED',
          'APA_DEG_BAS_NATIVE_VISUAL_REVIEW','JUBILEE_NOT_VALIDATED','PORTRAIT_NOT_VALIDATED','RELEASE_ACTIVATION_NOT_AUTHORIZED']}
    return release,report,vault

def project_shared_assets(release,job):
    """Pure consumer API. One release revision affects every new job by lookup.
    No client content, Illustrator, or filesystem required to resolve common roles.
    """
    need(release.get('schema')==SCHEMA,'RELEASE_SCHEMA')
    need(job.get('family') in release['front_logo_bboxes_mm'],'UNKNOWN_FAMILY')
    need(job.get('signature') in release['signature_sources'],'UNKNOWN_SIGNATURE')
    mapping={}
    for role,name in release['common_roles'].items():
        entry=release['assets'][name]
        mapping[role]={'asset_name':name,'sha256':entry['sha256'],
          'bbox_mm':(release['front_logo_bboxes_mm'][job['family']] if role=='P01.SENDER_LOGO' else entry['bbox_mm'])}
    name=release['signature_sources'][job['signature']]
    mapping['P04.SIGNATURE']={'asset_name':name,'sha256':release['assets'][name]['sha256'],
        'bbox_mm':release['assets'][name]['bbox_mm']}
    need((job.get('recipient_brand_present') is True)==(job['family']=='RECIPIENT_BRANDING_OVERLAY'),'BRANDING_DELTA')
    return mapping

def common_store(root):
    # Never store canonical runtime/design assets in tmp or the client workspace.
    return root.parent/'.state'/'graphic_design_lab'/'shared_design'/'releases'

def seed_release(root,release,vault):
    store=common_store(root)
    # .state is an existing private root. Avoid mkdir(parents=True) across trust boundary.
    parent=root.parent/'.state'/'graphic_design_lab'
    need(directory(parent) and not parent.is_symlink(),'DURABLE_STATE_PARENT_REQUIRED')
    st=parent.stat();need(st.st_uid==os.geteuid() and stat.S_IMODE(st.st_mode)==0o700,'STATE_PARENT_PERMISSIONS')
    base=parent/'shared_design';releases=base/'releases'
    for p in (base,releases):
        if not p.exists():p.mkdir(mode=0o700)
        need(directory(p) and not p.is_symlink() and stat.S_IMODE(p.stat().st_mode)==0o700,'STATE_STORE_INSECURE')
    release_id=sha(json.dumps(release,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode())
    dest=store/release_id
    need(not dest.is_symlink(),'RELEASE_SYMLINK_DENIED')
    if dest.exists():
        verify_seed(dest,release)
        return 'ALREADY_IDENTICAL'
    temp=Path(tempfile.mkdtemp(prefix='.gc47bd_seed_',dir=store))
    try:
        assets_dir=temp/'assets';assets_dir.mkdir(mode=0o700)
        for name,entry in release['assets'].items():
            src=vault/name;need(regular(src) and file_sha(src)==entry['sha256'],'SEED_SOURCE_CHANGED')
            dst=assets_dir/name
            with src.open('rb') as inp,dst.open('xb') as out:
                for chunk in iter(lambda:inp.read(1024*1024),b''):out.write(chunk)
            dst.chmod(0o600)
            need(file_sha(dst)==entry['sha256'],'SEED_COPY_SHA')
        mf=temp/'release.json';mf.write_text(json.dumps(release,ensure_ascii=True,sort_keys=True,indent=2)+'\n','utf8');mf.chmod(0o600)
        verify_seed(temp,release)
        os.rename(temp,dest) # immutable snapshot; never overwrite current release
        verify_seed(dest,release)
        return 'SEEDED_NON_ACTIVE'
    finally:
        if temp.exists():shutil.rmtree(temp)

def verify_seed(path,release):
    need(directory(path) and not path.is_symlink(),'RELEASE_DIR_INVALID')
    mf=path/'release.json';need(regular(mf) and json.loads(mf.read_text('utf8'))==release,'RELEASE_MANIFEST_DRIFT')
    need(release['activation']=='NOT_ACTIVE' and release['visual_approved'] is False,'RELEASE_NOT_PRIVATE_CANDIDATE')
    expected=set(release['assets'])
    assets=path/'assets';need(directory(assets) and not assets.is_symlink(),'ASSET_DIR_INVALID')
    need({p.name for p in assets.iterdir()}==expected,'RELEASE_ASSET_SET')
    for name,entry in release['assets'].items():
        p=assets/name;need(regular(p) and p.stat().st_size==entry['size_bytes'] and file_sha(p)==entry['sha256'],'RELEASE_ASSET_DRIFT')

def save_evidence(root,report):
    target=root/'tmp/gc47bd_shared_design_evidence_r001.zip'
    need(directory(target.parent) and not target.parent.is_symlink(),'DELIVERY_TMP_REQUIRED')
    need(not target.exists() and not target.is_symlink(),'EVIDENCE_EXISTS')
    with target.open('xb') as out:
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('REPORT.json',json.dumps(report,indent=2,ensure_ascii=True,sort_keys=True)+'\n')
    return target

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--mode',required=True,choices=('check','inspect','seed'))
    p.add_argument('--client-name');p.add_argument('--confirm-private-seed',action='store_true')
    args=p.parse_args(argv)
    try:
        load_contract();gc29_module()
        if args.mode=='check':print('GC47BD_CHECK=PASS_SOURCE_BOUND_CONTRACT_NON_NATIVE');return 0
        need(args.client_name,'CLIENT_REQUIRED')
        release,report,vault=source_inventory(ROOT,args.client_name)
        print('GC47BD_PROFILES=PASS_FOUR_PROFILES_ONE_SHARED_ASSET_CATALOG',flush=True)
        print('GC47BD_RELEASE_ID='+report['release_id'],flush=True)
        if args.mode=='seed':
            need(args.confirm_private_seed,'PRIVATE_SEED_EXPLICIT_CONFIRMATION_REQUIRED')
            need(not (ROOT/'tmp/gc47bd_shared_design_evidence_r001.zip').exists(),'EVIDENCE_EXISTS_NO_SEED')
            state=seed_release(ROOT,release,vault)
            print('GC47BD_SHARED_RELEASE='+state,flush=True)
            report['shared_release_store']=state
        path=save_evidence(ROOT,report)
        print('GC47BD_EVIDENCE='+str(path),flush=True)
        print('GC47BD_NATIVE_DISPATCH=FALSE CLIENT_MUTATION=FALSE GIT_MUTATION=FALSE',flush=True)
        print('GC47BD_PRODUCTION_READY=FALSE SHARED_RELEASE_ACTIVE=FALSE',flush=True)
        return 0
    except Exception as exc:
        print('GC47BD=BLOCKED_'+str(exc).splitlines()[0][:170],flush=True)
        print('GC47BD_NO_NATIVE_NO_CLIENT_WRITE_NO_GIT_MUTATION=TRUE',flush=True)
        return 2
if __name__=='__main__':raise SystemExit(main())
