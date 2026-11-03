#!/usr/bin/env python3
"""Source-bound generalized Intake -> ONE Studio renderer SHADOW materialization.

Never sends work to Windows, launches Illustrator, installs runtime from ZIP,
mutates source archives, or asserts operator/visual review. This is a pre-native
bridge verification for arbitrary accepted Intake job IDs. Staging is disposable;
result JSON contains NO customer text/images (only IDs, hashes and statuses).
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'scripts/graphic_design_lab/greeting_cards'
AUDIT = SRC / 'illustrator_studio_intake_audit_v1.py'
STUDIO = SRC / 'illustrator_studio_cli_v1.py'
GC47S = SRC / 'gc47s_client_pilot_v0_1.py'
TMP = ROOT / 'tmp'
SCHEMA = 'forprint_studio_intake_dynamic_source_shadow_v1'
HEX = re.compile(r'^[0-9a-f]{64}$')
SAFE_JOB = re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
SAFE_PACKAGE = re.compile(r'^[^/\\\x00]{1,200}\.zip$', re.IGNORECASE)
MAX_ARCHIVE_BYTES = 40 * 1024 * 1024
MAX_GREETING_CHARS = 1100

class Blocked(RuntimeError): pass

def need(ok, code):
    if not ok: raise Blocked(code)

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode) and not p.is_symlink()
    except OSError:return False

def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode) and not p.is_symlink()
    except OSError:return False

def sha(b):return hashlib.sha256(b).hexdigest()

def load_py(path, key):
    need(regular(path),'PINNED_SOURCE_MISSING_'+path.name)
    spec=importlib.util.spec_from_file_location(key,path)
    need(spec and spec.loader,'SOURCE_MODULE_INVALID_'+path.name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def to_json(obj): return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')

def input_archive(audit, client, file_name):
    folder=audit.client_input_dir(client)
    need(SAFE_PACKAGE.fullmatch(file_name) is not None,'SELECTED_ZIP_FILENAME_INVALID')
    path=folder/file_name
    need(regular(path) and 0<path.stat().st_size<=MAX_ARCHIVE_BYTES,'SELECTED_ZIP_MISSING_OR_OVERSIZED')
    need(path.resolve().parent==folder.resolve(),'SELECTED_ZIP_ESCAPES_INPUT')
    return path

def decide_job(job):
    """Make unverified variants visible; no silent substitutions or review claims."""
    need(isinstance(job,dict),'JOB_NOT_OBJECT')
    job_id=job.get('job_id')
    need(isinstance(job_id,str) and SAFE_JOB.fullmatch(job_id),'JOB_ID_UNSAFE')
    b=job.get('builder_v1')
    need(isinstance(b,dict),'BUILDER_PAYLOAD_MISSING')
    front=b.get('front');inside=b.get('inside_image');sender=b.get('sender_text')
    need(all(isinstance(x,dict) for x in (front,inside,sender)),'SCENE_COMPONENTS_MISSING')
    greet=job.get('structured_greeting_data')
    need(isinstance(greet,dict) and isinstance(greet.get('greeting_text'),str),'GREETING_MISSING')
    need(10 < len(greet['greeting_text']) <= MAX_GREETING_CHARS,'GREETING_EXCEEDS_CANONICAL_STUDIO_P04_POLICY')
    occasion=front.get('occasion')
    need(isinstance(occasion,dict) and occasion.get('kind')=='BIRTHDAY','OCCASION_NOT_SUPPORTED')
    need(occasion.get('display_text')=='Привітання з нагоди Дня Народження!','OCCASION_TITLE_LAYOUT_UNSUPPORTED')
    family=front.get('family')
    need(family in ('STANDARD','RECIPIENT_BRANDING_OVERLAY'),'FRONT_FAMILY_NOT_SUPPORTED')
    signature=sender.get('signature_variant_id')
    need(signature in ('GRIGO','HERASYMENKO'),'SIGNATURE_NATIVE_UNSUPPORTED')
    need((job.get('signature_selection') or {}).get('variant_id')==signature,'SIGNATURE_SELECTION_CONFLICT')
    lines=sender.get('lines')
    need(isinstance(lines,list) and len(lines) in (3,4),'SENDER_ROWS_UNSUPPORTED')
    need(all(isinstance(l,dict) and isinstance(l.get('text'),str) and
             l['text'].strip() and len(l['text'])<=180 for l in lines),'SENDER_LINE_INVALID')
    mode=inside.get('mode')
    need(mode in ('PORTRAIT','DEFAULT_ASSET'),'P03_IMAGE_MODE_UNSUPPORTED')
    return {'job_id':job_id,'front':family,'signature':signature,'image_mode':mode,
            'sender_rows':len(lines),'greeting_chars':len(greet['greeting_text'])}

def read_verified_asset(z, artifacts, ref, expected, require_png=True):
    need(isinstance(ref,str) and ref in artifacts,'ASSET_REF_MISSING')
    entry=artifacts[ref]
    need(isinstance(entry,dict) and entry.get('sha256')==expected,'ASSET_DIGEST_BINDING')
    path=entry.get('path')
    need(isinstance(path,str) and path.startswith('assets/') and not ('..' in path.split('/')),'ASSET_MEMBER_UNSAFE')
    try: payload=z.read(path)
    except KeyError:raise Blocked('ASSET_MEMBER_NOT_FOUND')
    need(sha(payload)==expected,'ASSET_BYTES_DIGEST_MISMATCH')
    if require_png:need(path.lower().endswith('.png') and payload.startswith(b'\x89PNG\r\n\x1a\n'),'ASSET_MUST_BE_PNG')
    need(len(payload)<80*1024*1024,'ASSET_TOO_LARGE')
    return payload

def portrait_proof(payload):
    from PIL import Image
    with Image.open(io.BytesIO(payload)) as im:
        need(im.format=='PNG' and im.mode=='RGBA','PORTRAIT_MUST_BE_RGBA_PNG')
        need(128<=im.width<=12000 and 128<=im.height<=12000,'PORTRAIT_DIMENSION_OUT_OF_BOUND')
        alpha=im.getchannel('A').getextrema()
        need(alpha[0] < 255 and alpha[1] > 0,'PORTRAIT_ALPHA_NOT_MEANINGFUL')
        return {'width':im.width,'height':im.height,'alpha_present':True}

def assemble(gc29,studio,job,artifact,z,vault,catalog,archive_sha, capture_material=False):
    row=decide_job(job)
    b=job['builder_v1'];mode=row['image_mode']
    flowers=gc29.FLOWERS_SHA
    # GC29 is the proven geometry adapter for P01/P02/P04. When a portrait is
    # supplied, *only a disposable layout copy* uses floral mode to obtain
    # shared geometry; the final scene is explicitly PORTRAIT, never flowers.
    geom=copy.deepcopy(job)
    if mode=='PORTRAIT':
        geom['builder_v1']['inside_image']={'mode':'DEFAULT_ASSET','asset_sha256':flowers,'asset_id':'flowers.default.v1'}
    logo=None
    if row['front']=='RECIPIENT_BRANDING_OVERLAY':
        brand=b['front'].get('recipient_branding')
        need(isinstance(brand,dict),'BRANDING_BINDING_REQUIRED')
        logo=read_verified_asset(z,artifact,brand.get('accepted_artifact_ref'),brand.get('asset_sha256'))
    scene=gc29.compile_scene(geom,catalog,logo)
    need(scene['job_id']==row['job_id'] and scene['pages']==4,'SCENE_COMPILER_ID_DRIFT')
    if mode=='PORTRAIT':
        asset=b['inside_image'];ref=asset.get('accepted_artifact_ref');digest=asset.get('asset_sha256')
        portrait=read_verified_asset(z,artifact,ref,digest)
        portrait_info=portrait_proof(portrait)
        flower_layers=[x for x in scene['layers'] if x['role']=='P03.FLOWERS']
        need(len(flower_layers)==1,'P03_SHARED_GEOMETRY_NOT_UNIQUE')
        flower_layers[0]['role']='P03.PORTRAIT'
        flower_layers[0]['file']='assets/p03_portrait.png'
        scene['image_mode']='PORTRAIT'
        scene['portrait_source_sha256']=digest
        scene['portrait_layout_state']='SHADOW_ONLY_NOT_NATIVE_VISUAL_APPROVED'
    else:
        asset=b['inside_image']
        need(asset.get('asset_id')=='flowers.default.v1' and asset.get('asset_sha256')==flowers,'FLOWERS_STANDARD_PIN_MISMATCH')
        need(asset.get('accepted_artifact_ref') is None,'FLOWERS_CREATOR_REF_FORBIDDEN')
        portrait=None;portrait_info=None
    generated=gc29.bind_illustrator_signature(scene,vault,catalog)
    layers=scene['layers'];need(isinstance(layers,list) and len(layers) in (12,13),'SCENE_LAYER_COUNT')
    assets={}
    for layer in layers:
        name=Path(layer['file']).name
        need(layer['file']=='assets/'+name and re.fullmatch(r'[a-z0-9_]+\.png',name) and name not in assets,'SCENE_ASSET_NAME_OR_DUPLICATE')
        if name=='recipient_branding.png':blob=logo
        elif name=='p03_portrait.png':blob=portrait
        elif name in generated:blob=generated[name]
        else:
            path=vault/name;need(regular(path),'VAULT_RESOURCE_MISSING_'+name)
            need(catalog['assets'][name]['sha256']==gc29.digest(path),'VAULT_ASSET_SHA_DRIFT_'+name)
            blob=path.read_bytes()
        need(isinstance(blob,bytes) and 200<len(blob)<80*1024*1024,'WORK_ASSET_EMPTY_OR_INVALID')
        assets[name]=blob
    settings=studio.config();renderer=studio.render_template()
    scene['studio_settings']=settings
    scene['studio_renderer']='ILLUSTRATOR_STUDIO_ONE_CANONICAL_JSX_V1'
    scene['visual_approved']=False;scene['production_ready']=False
    rendered=renderer.replace('/*__GC29_SCENE__*/',json.dumps(scene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
    need(len(rendered)>10000 and b'/*__GC29_SCENE__*/' not in rendered,'STUDIO_RENDERER_MATERIALIZATION_FAILED')
    # Redacted native-style manifest: text is intentionally excluded.
    public={k:v for k,v in scene.items() if k not in ('greeting_text','sender_lines','front_lines','studio_settings')}
    public['asset_sha256']={k:sha(v) for k,v in sorted(assets.items())}
    public['jsx_sha256']=sha(rendered)
    public['accepted_zip_sha256']=archive_sha
    public['studio_design_config_sha256']=sha(studio.CFG.read_bytes())
    public['studio_renderer_sha256']=sha(studio.JSX.read_bytes())
    public['production_ready']=False;public['visual_approved']=False
    report={'job_id':row['job_id'],'status':'SCENE_SHADOW_COMPILED_NOT_NATIVE_APPROVED',
            'image_mode':mode,'front_family':row['front'],'signature_variant':row['signature'],
            'sender_rows':row['sender_rows'],'greeting_chars':row['greeting_chars'],
            'asset_count':len(assets),'native_jsx_sha256':sha(rendered),'manifest_sha256':sha(to_json(public)),
            'notes':['REVIEW_FIELDS_NOT_INDEPENDENTLY_ATTESTED','NATIVE_DISPATCH_NOT_WIRED']}
    if mode=='PORTRAIT':report['notes'].append('PORTRAIT_BBOX_VISUAL_REVIEW_REQUIRED');report['portrait_geometry']=portrait_info
    if row['front']=='RECIPIENT_BRANDING_OVERLAY':report['notes'].append('BRANDING_BBOX_VISUAL_REVIEW_REQUIRED')
    # Verify work bytes without permanent local output. Never create an attempt.
    need(directory(TMP),'REPO_TMP_MISSING')
    with tempfile.TemporaryDirectory(prefix='studio_dynamic_shadow_',dir=TMP) as td:
        os.chmod(td,0o700);root=Path(td)
        (root/'assets').mkdir(mode=0o700)
        (root/'run_in_illustrator.jsx').write_bytes(rendered)
        (root/'scene_manifest.json').write_bytes(to_json(public))
        for name,blob in assets.items():(root/'assets'/name).write_bytes(blob)
        need(sha((root/'run_in_illustrator.jsx').read_bytes())==public['jsx_sha256'],'SHADOW_JSX_READBACK')
        need(all(sha((root/'assets'/name).read_bytes())==public['asset_sha256'][name] for name in assets),'SHADOW_ASSET_READBACK')
        need(json.loads((root/'scene_manifest.json').read_text('utf8'))['job_id']==row['job_id'],'SHADOW_MANIFEST_READBACK')
    if capture_material:
        return report, {'jsx':rendered,'manifest':to_json(public),
                        'assets':assets,'archive_sha256':archive_sha}
    return report

def scan(client, file_name):
    audit=load_py(AUDIT,'studio_phase2b_pinned_auditor')
    studio=load_py(STUDIO,'studio_phase2b_canonical_studio')
    s=load_py(GC47S,'studio_phase2b_pinned_client_pilot')
    target=input_archive(audit,client,file_name)
    archive_sha=sha(target.read_bytes())
    summary=audit.audit(target)
    need(summary['status']=='HANDOFF_STRUCTURAL_PASS_STUDIO_BINDING_REQUIRED',
         'SELECTED_ZIP_NOT_CURRENT_ACCEPTED_HANDOFF_'+summary['status'])
    # Neither a handoff self-claim nor a structural pass proves operator review.
    gc29=s.load_source()  # exact source SHA pinned by incumbent client pilot
    ws=s.workspace(client)
    vault=ws/'template_studio'/'native_asset_vault_v0_1'
    catalog=gc29.verify_vault(vault)
    with zipfile.ZipFile(target) as z:
        bundle=audit.load_yaml(z.read('accepted_constructor_bundle.yaml'))
        art=audit.load_yaml(z.read('artifact_manifest.yaml'))
        jobs=bundle['jobs'];artifact=art['artifacts'];rows=[]
        for job in jobs:
            jid=job['job_id'] if isinstance(job,dict) else 'INVALID_JOB'
            try: rows.append(assemble(gc29,studio,job,artifact,z,vault,catalog,archive_sha))
            except Exception as exc:
                if isinstance(exc,(Blocked,)) or isinstance(exc,(KeyError,TypeError,ValueError,IndexError,ImportError)):
                    code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
                    rows.append({'job_id':jid,'status':'JOB_SHADOW_BLOCKED','blockers':[code[:160]]})
                else:raise
    ok=all(x['status']=='SCENE_SHADOW_COMPILED_NOT_NATIVE_APPROVED' for x in rows)
    result={'schema_version':SCHEMA,'status':'ALL_JOBS_SHADOW_COMPILED_NO_NATIVE' if ok else 'SOME_JOBS_BLOCKED_NO_NATIVE',
            'package_name':target.name,'package_sha256':archive_sha,'jobs_total':len(rows),'jobs':rows,
            'structural_audit_status':summary['status'],'review_independent_attestation':'NOT_ESTABLISHED',
            'studio_one_renderer_sha256':sha(studio.JSX.read_bytes()),
            'native_dispatch':False,'native_attempt_created':False,'operator_review_authorized':False,
            'production_ready':False,'automatic_queue':False,'new_zip_native_wired':False}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    return 0 if ok else 3

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--client-name',required=True)
    p.add_argument('--zip-name',required=True)
    args=p.parse_args(argv)
    try:return scan(args.client_name,args.zip_name)
    except Exception as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('STUDIO_DYNAMIC_PREFLIGHT=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:180],file=sys.stderr)
        print('NO_NATIVE_DISPATCH=TRUE NO_PRODUCTION=TRUE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
