#!/usr/bin/env python3
"""ForPrint Template Studio full 4-page read-only operator UI over private SMB.

Project code/registry lives in independent GDL. The only client writes are to
_forprint_automation/template_studio after explicit publish confirmation.
Does not alter input/, output/, Prepress Hub, native AI, or production flags.
"""
from __future__ import annotations
import argparse
import base64
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

import fitz
import yaml

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / 'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
INFRA_REGISTRY = ROOT / 'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
HTML_TEMPLATE = ROOT / 'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
GC23 = ROOT / 'coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json'
SHARE_ROOT = Path('/srv/smb/In_Progress/data')
SOURCE_RESOURCE_ID = 'template.greeting_card.dolinska.v1'
SOURCE_SHA = '66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85'
MEDIA_MM = [214, 301]
MARKER = '<!-- FORPRINT_TS_FULL_STATIC_PORTAL_V0_1 -->'
MAX_PDF = 512 * 1024 * 1024
MAX_HTML = 18 * 1024 * 1024

class Blocked(ValueError): pass

def need(expr: Any, code: str):
    if not expr: raise Blocked(code)

def regular(p: Path) -> bool:
    try: return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError: return False

def directory(p: Path) -> bool:
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError: return False

def digest(raw: bytes) -> str: return sha256(raw).hexdigest()

def file_sha(p: Path) -> str:
    h=sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def load_registry(root: Path=ROOT):
    p=root/REGISTRY.relative_to(ROOT)
    need(regular(p), 'REGISTRY_MISSING')
    model=json.loads(p.read_text(encoding='utf-8'))
    need(model.get('schema_version')=='forprint_gdl_template_studio_full_registry_v0_1','REGISTRY_SCHEMA')
    pages=model.get('pages')
    need(isinstance(pages,list) and [x['id'] for x in pages]==['P01','P02','P03','P04'],'PAGE_SET_CHANGED')
    all_ids=[]
    for pg in pages:
        elements=pg['elements']
        need(all(isinstance(e.get('step'),int) and re.fullmatch(r'P0[1-4]-\d{3}',e.get('id','')) for e in elements),'ELEMENT_ID_INVALID')
        need([e['step'] for e in elements]==sorted({e['step'] for e in elements}), 'ELEMENT_STEP_ORDER_INVALID')
        for e in elements:
            all_ids.append(e['id'])
            b=e.get('bbox_mm')
            if b is not None:
                need(isinstance(b,list) and len(b)==4 and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in b) and b[2]>b[0] and b[3]>b[1],'ELEMENT_BBOX_INVALID')
        for group in pg['variant_groups']:
            need(group in model['variant_groups'],'UNREGISTERED_VARIANT_GROUP')
    need(len(all_ids)==len(set(all_ids)), 'DUPLICATE_ELEMENT_IDS')
    group=model['variant_groups']
    for key,g in group.items():
        allowed=[v['id'] for v in g['values']]
        need(len(allowed)==len(set(allowed)) and g['default'] in allowed,'VARIANT_CATALOG_INVALID')
    p01=next(p for p in pages if p['id']=='P01')
    gc23=json.loads((root/GC23.relative_to(ROOT)).read_text(encoding='utf-8'))
    need(gc23['schema_version']=='forprint_gdl_gc23_variant_contract_v0_1','GC23_SCHEMA')
    need(gc23['source_closed_commit']=='b26cce19f4700cadaf34323e4c2e2909bcf5fcd8','SOURCE_COMMIT_CHANGED')
    need(gc23['physical_order']==['P01_FRONT','P02_BACK','P03_INSIDE_IMAGE','P04_GREETING'],'SOURCE_PAGE_ORDER_CHANGED')
    need(gc23['pinned_sha256']['reference_pdf']==SOURCE_SHA,'SOURCE_SHA_CHANGED')
    need(gc23['physical_size_mm']==MEDIA_MM, 'PAGE_SIZE_CHANGED')
    indexed={e['id']:e for p in pages for e in p['elements']}
    need(indexed['P01-020']['bbox_mm']==gc23['front_variants']['STANDARD']['sender_logo_bbox_mm'],'P01_LOGO_GEOMETRY_DRIFT')
    need(indexed['P01-030']['bbox_mm']==gc23['front_variants']['STANDARD']['occasion_bbox_mm'],'P01_OCCASION_GEOMETRY_DRIFT')
    need(indexed['P04-020']['bbox_mm']==gc23['p04_greeting_bbox_pdf_mm'],'P04_GREETING_GEOMETRY_DRIFT')
    for category,registrations in [('front_family',gc23['front_variants']),('image_mode',gc23['photo_variants']),('signature',gc23['signature_variants'])]:
        need(set(v['id'] for v in group[category]['values'])==set(registrations),'SOURCE_VARIANT_CATALOG_DRIFT')
    need(group['occasion']['values'][1]['availability']=='CONCEPTUAL_UI_ONLY_NO_ACCEPTED_BINDING','JUBILEE_AUTHORITY_DRIFT')
    need(model['authority']['automatic_design_approval'] is False and model['authority']['client_source_mutation'] is False and model['authority']['native_illustrator_render_enabled'] is False,'AUTHORITY_INVALID')
    model['_source_front_variants']={k:{'sender_logo_bbox_mm':v['sender_logo_bbox_mm'],'occasion_bbox_mm':v['occasion_bbox_mm']} for k,v in gc23['front_variants'].items()}
    return model

def source_pdf(manifest: Path, source_root: Path, root: Path=ROOT) -> Path:
    need(regular(manifest),'RESOURCE_MANIFEST_MISSING')
    resources=yaml.safe_load(manifest.read_text(encoding='utf-8'))
    need(isinstance(resources,dict) and resources.get('schema_version')=='gdl_greeting_card_private_resource_manifest_v0_1','RESOURCE_MANIFEST_SCHEMA')
    binding=resources.get('resources',{}).get(SOURCE_RESOURCE_ID)
    need(isinstance(binding,dict),'SOURCE_BINDING_MISSING')
    need(binding.get('sha256',SOURCE_SHA)==SOURCE_SHA,'SOURCE_BINDING_SHA_DRIFT')
    path=binding.get('path')
    need(isinstance(path,str) and bool(path.strip()),'SOURCE_PATH_INVALID')
    p=Path(path)
    if not p.is_absolute():
        need(directory(source_root),'SOURCE_ROOT_INVALID')
        p=source_root/p
    need(regular(p),'REFERENCE_FILE_MISSING_OR_SYMLINK')
    need(0<p.stat().st_size<=MAX_PDF,'REFERENCE_FILE_SIZE_INVALID')
    need(file_sha(p)==SOURCE_SHA,'REFERENCE_SHA_MISMATCH')
    with fitz.open(p) as doc:
        need(doc.page_count==4,'REFERENCE_PAGE_COUNT_INVALID')
        for page in doc:
            mm=[page.rect.width*25.4/72,page.rect.height*25.4/72]
            need(all(abs(a-b)<0.2 for a,b in zip(mm,MEDIA_MM)), 'REFERENCE_PAGE_GEOMETRY_INVALID')
    return p

def render_page_images(pdf: Path) -> dict[str,str]:
    images={}
    with fitz.open(pdf) as doc:
        for i,page_id in enumerate(['P01','P02','P03','P04']):
            page=doc[i]
            pix=page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False,colorspace=fitz.csRGB)
            img=pix.tobytes('png')
            need(5000<len(img)<4_000_000,'PREVIEW_IMAGE_SIZE_INVALID')
            images[page_id]='data:image/png;base64,'+base64.b64encode(img).decode('ascii')
    return images

def load_infrastructure(root:Path=ROOT) -> dict:
    p=root/INFRA_REGISTRY.relative_to(ROOT)
    need(regular(p),'INFRA_REGISTRY_MISSING')
    data=json.loads(p.read_text(encoding='utf8'))
    need(data.get('schema_version')=='forprint_gdl_gc32_infrastructure_map_v0_1','INFRA_SCHEMA_INVALID')
    return data

def html_bytes(model:dict,images:dict,template:bytes,source_sha:str=SOURCE_SHA,infra:dict|None=None) -> tuple[bytes,str]:
    need(MARKER.encode() not in template, 'HTML_TEMPLATE_MARKER_COLLISION')
    t=template.decode('utf-8')
    need(t.count('/*__TS_FULL_MODEL__*/')==1 and t.count('/*__TS_FULL_IMAGES__*/')==1 and t.count('/*__TS_FULL_BUILD__*/')==1,'HTML_TEMPLATE_TOKEN_INVALID')
    if infra is None: infra=load_infrastructure(ROOT)
    need(isinstance(infra,dict) and infra.get('schema_version')=='forprint_gdl_gc32_infrastructure_map_v0_1','INFRA_SCHEMA_INVALID')
    need(t.count('/*__TS_INFRA__*/')==1,'INFRA_TOKEN_MISSING')
    id_seed=json.dumps({'registry':model,'infra':infra,'template_sha256':digest(template),'source':source_sha},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')
    build_id='tsfull-'+digest(id_seed)[:16]
    safe=lambda o:json.dumps(o,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=(MARKER+'\n'+t.replace('/*__TS_FULL_MODEL__*/',safe(model)).replace('/*__TS_FULL_IMAGES__*/',safe(images)).replace('/*__TS_FULL_BUILD__*/',safe({'id':build_id,'source_sha256':source_sha})).replace('/*__TS_INFRA__*/',safe(infra))).encode('utf-8')
    need(len(html)<MAX_HTML,'PORTAL_HTML_TOO_LARGE')
    return html,build_id

def read_build(build_dir:Path) -> tuple[bytes,dict]:
    need(directory(build_dir),'BUILD_DIR_UNAVAILABLE')
    index=build_dir/'index.html'; receipt=build_dir/'build_manifest.json'
    need(regular(index) and regular(receipt),'BUILD_OUTPUT_MISSING')
    raw=index.read_bytes(); record=json.loads(receipt.read_text(encoding='utf-8'))
    need(raw.startswith(MARKER.encode()) and record['schema_version']=='forprint_ts_full_build_v0_1','BUILD_OWNERSHIP_INVALID')
    need(len(raw)<MAX_HTML and record['sha256']==digest(raw) and record['source_sha256']==SOURCE_SHA,'BUILD_SHA_MISMATCH')
    need(re.fullmatch(r'tsfull-[a-f0-9]{16}',record['build_id']),'BUILD_ID_INVALID')
    return raw,record

def build(name:str, pdf:Path, root:Path=ROOT):
    need(re.fullmatch(r'tsfull_[a-z0-9_]{3,55}',name or '') is not None, 'OUTPUT_NAME_INVALID')
    parent=root/'tmp'; need(directory(parent), 'PROJECT_TMP_DIR_MISSING')
    dest=parent/name
    need(not dest.exists() and not dest.is_symlink(),'BUILD_OUTPUT_EXISTS_NO_OVERWRITE')
    model=load_registry(root)
    template_path=root/HTML_TEMPLATE.relative_to(ROOT)
    need(regular(template_path),'HTML_TEMPLATE_MISSING')
    raw,build_id=html_bytes(model,render_page_images(pdf),template_path.read_bytes(),infra=load_infrastructure(root))
    dest.mkdir(mode=0o700)
    (dest/'index.html').write_bytes(raw)
    receipt={'schema_version':'forprint_ts_full_build_v0_1','build_id':build_id,'sha256':digest(raw),'source_sha256':SOURCE_SHA,'page_count':4,'private_reference':True,'client_render_authority':False,'portal_subdir':'template_studio'}
    (dest/'build_manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return dest,receipt

def workspace(client_name:str,share_root:Path=SHARE_ROOT) -> Path:
    need(bool(client_name) and client_name not in ('.','..') and '/' not in client_name and '\\' not in client_name and '\0' not in client_name,'CLIENT_NAME_INVALID')
    need(directory(share_root),'SHARE_ROOT_MISSING_OR_UNSAFE')
    root=share_root.resolve(strict=True)
    client=root/client_name; ws=client/'_forprint_automation'
    for p in (client,ws,ws/'input',ws/'output'):
        need(directory(p),'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(ws.resolve(strict=True).parent.parent==root,'CLIENT_WORKSPACE_ESCAPE')
    return ws

def target_portal(ws:Path)->Path:
    portal=ws/'template_studio'
    if portal.exists() or portal.is_symlink():need(directory(portal),'EXISTING_PORTAL_NOT_DIRECTORY_OR_SYMLINK')
    return portal

def verify_current(portal:Path)->dict:
    index=portal/'index.html'; meta=portal/'publication_manifest.json'
    need(regular(index) and regular(meta),'PORTAL_OUTPUT_INCOMPLETE')
    raw=index.read_bytes(); rec=json.loads(meta.read_text(encoding='utf8'))
    need(raw.startswith(MARKER.encode()),'PORTAL_INDEX_FOREIGN_OR_MODIFIED')
    need(rec.get('schema_version')=='forprint_ts_full_publication_v0_1' and rec.get('sha256')==digest(raw),'PORTAL_SHA_MISMATCH')
    release=portal/'releases'/(rec['build_id']+'.html')
    need(regular(release) and release.read_bytes()==raw,'PORTAL_RELEASE_MISMATCH')
    return rec

def safe_atomic_replace(path:Path,payload:bytes):
    tmp=path.with_name('.'+path.name+'.tsfull-new-'+str(os.getpid()))
    need(not tmp.exists() and not tmp.is_symlink(),'TEMP_FILE_CONFLICT')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
    with os.fdopen(fd,'wb') as f:
        f.write(payload);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    need(regular(path) and file_sha(path)==digest(payload),'ATOMIC_WRITE_VERIFY_FAILED')

def publish(build_dir:Path,client_name:str,share_root:Path=SHARE_ROOT,confirm:bool=False):
    need(confirm,'EXPLICIT_PUBLICATION_CONFIRMATION_REQUIRED')
    raw,b=read_build(build_dir)
    ws=workspace(client_name,share_root)
    portal=target_portal(ws)
    if not portal.exists():portal.mkdir(mode=0o755)
    releases=portal/'releases'
    if releases.exists() or releases.is_symlink():need(directory(releases),'RELEASES_PATH_UNSAFE')
    else:releases.mkdir(mode=0o755)
    lock=portal/'.publish.lock'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o644)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        if (portal/'index.html').exists() or (portal/'publication_manifest.json').exists():
            verify_current(portal)
        release=releases/(b['build_id']+'.html')
        if release.exists() or release.is_symlink():
            need(regular(release) and release.read_bytes()==raw,'RELEASE_ID_CONFLICT')
        else:
            f=os.open(release,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
            with os.fdopen(f,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        record={'schema_version':'forprint_ts_full_publication_v0_1','build_id':b['build_id'],'sha256':digest(raw),'source_sha256':SOURCE_SHA,'static_offline_portal':True,'production_authority':False}
        # Stable index is replaced only after immutable release verifies. Keep client work files untouched.
        safe_atomic_replace(portal/'index.html',raw)
        safe_atomic_replace(portal/'publication_manifest.json',(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        verify_current(portal)
        return portal,record
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=['check','build','publish','verify'])
    p.add_argument('--resource-manifest',type=Path)
    p.add_argument('--source-root',type=Path,default=Path('../forprint_prepress_hub'))
    p.add_argument('--output-name')
    p.add_argument('--build-dir',type=Path)
    p.add_argument('--client-name')
    p.add_argument('--confirm-publish',action='store_true')
    args=p.parse_args()
    try:
        need(args.mode=='publish' or not args.confirm_publish,'CONFIRM_ONLY_FOR_PUBLISH')
        if args.mode in ('check','build'):
            need(args.resource_manifest is not None,'RESOURCE_MANIFEST_REQUIRED')
            load_registry(); src=source_pdf(args.resource_manifest,args.source_root)
            if args.mode=='check':
                print('TS_FULL_SOURCE=CHECK_PASS_SHA_VERIFIED_READ_ONLY PAGES=4');return 0
            need(args.output_name is not None,'OUTPUT_NAME_REQUIRED')
            dest,rec=build(args.output_name,src)
            print('TS_FULL_BUILD=PASS_PRIVATE_REF_ONLY'); print('BUILD_DIR='+str(dest));print('BUILD_SHA256='+rec['sha256']);return 0
        need(args.client_name is not None,'CLIENT_NAME_REQUIRED')
        if args.mode=='verify':
            ws=workspace(args.client_name)
            portal=target_portal(ws)
            rec=verify_current(portal)
            print('TS_FULL_PORTAL=VERIFY_PASS '+rec['build_id']);print('CLIENT_INDEX='+str(portal/'index.html'));print('INDEX_SHA256='+rec['sha256']);return 0
        need(args.build_dir is not None,'BUILD_DIR_REQUIRED')
        portal,rec=publish(args.build_dir,args.client_name,confirm=args.confirm_publish)
        print('TS_FULL_PORTAL=PUBLISHED_VERIFIED');print('CLIENT_INDEX='+str(portal/'index.html'));print('INDEX_SHA256='+rec['sha256']);print('CLIENT_INPUT_UNCHANGED=true CLIENT_OUTPUT_UNCHANGED=true NATIVE_RENDER=false');return 0
    except (Blocked,ValueError,OSError,KeyError,fitz.FileDataError,yaml.YAMLError) as exc:
        reason=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('TS_FULL=BLOCKED reason='+reason,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
