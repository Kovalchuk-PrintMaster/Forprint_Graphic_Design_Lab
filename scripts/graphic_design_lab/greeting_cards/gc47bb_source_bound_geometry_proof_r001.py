#!/usr/bin/env python3
"""GC47BB — source-bound geometry triage and four-profile Illustrator candidate proof (read-only).

Takes real accepted jobs from GC47AZ, compiles GENERIC GC29 JSX for each in
memory and produces a strictly sanitized report. Never dispatches, stages a
client attempt, modifies a file in client workspace, or changes a GUI session.
The generic JSX is NOT a substitute for GC47AX's reviewed ZAP candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import math
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
AZ = 'gc47az_multi_profile_shadow_r001.py'
AZ_SHA = '7d3382bd9e75acce7a8e4152ecf18d282ed6e3f003614c3b8959d207d5fa1d5d'
SCHEMA = 'gdl_gc47bb_four_profile_geometry_review_r001'
JSX_MARK = '/*__GC29_SCENE__*/'
MAX_JSX_BYTES = 2_000_000
GC47BA_R001_SHA = '4e5ce51c0bbc51227a8366e9c4421e61110a9437721fc4e512e1cb9215482dbd'
PAGE_MM = (214.0, 301.0)
ALLOWED_SCENE_OVERRIDES = {'P01.SENDER_LOGO', 'P01.RECIPIENT_BRANDING'}


class Blocked(ValueError):
    pass

def need(v, code):
    if not v:
        raise Blocked(code)

def isfile(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except OSError: return False

def isdir(p):
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except OSError: return False

def digest(data):
    return hashlib.sha256(data).hexdigest()

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def read_json(p):
    need(isfile(p) and p.stat().st_size<2_000_000,'REPORT_NOT_REGULAR_OR_TOO_LARGE')
    return json.loads(p.read_text('utf8'))

def az_module(root=ROOT,can=CAN):
    p=can/AZ
    need(isfile(p) and sha(p)==AZ_SHA, 'AZ_MODULE_NOT_PINNED')
    spec=importlib.util.spec_from_file_location('gc47bb_pinned_az',p)
    need(spec is not None and spec.loader is not None,'AZ_IMPORT')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def valid_rect(box, page=(214,301)):
    if not isinstance(box,list) or len(box)!=4 or any(type(x) not in (int,float) for x in box): return False
    a,b,c,d=map(float,box)
    return 0<=a<c<=page[0] and 0<=b<d<=page[1]

def png_metadata(data):
    if not isinstance(data,bytes) or len(data)<24 or data[:8]!=b'\x89PNG\r\n\x1a\n':return None
    w=int.from_bytes(data[16:20],'big');h=int.from_bytes(data[20:24],'big')
    if not (0<w<=30000 and 0<h<=30000):return None
    return {'width_px':w,'height_px':h}

def geometry_review(layers, vault, page=PAGE_MM):
    """Triages source-pinned asset overflow; never grants native permission.

    A source-pinned bbox crossing the artboard must be reported as an UNRESOLVED
    visual/clip gate. Strictly reject mismatched asset geometry, invalid shape,
    misplaced manual overrides, and source assets with zero page intersection.
    """
    need(isinstance(vault,dict) and vault.get('schema')=='gdl_gc29_native_asset_vault_v0_1',
         'VAULT_MANIFEST_INVALID')
    entries=vault.get('assets')
    need(isinstance(entries,dict) and len(entries)>=12,'VAULT_ASSETS_INVALID')
    classified=[]
    for layer in layers:
        role=layer['role'];box=layer.get('bbox_mm');name=layer.get('file')
        need(isinstance(box,list) and len(box)==4 and all(type(x) in (int,float) for x in box)
             and all(math.isfinite(float(x)) for x in box),'BBOX_INVALID_'+role.replace('.','_'))
        x0,y0,x1,y1=map(float,box)
        need(x0<x1 and y0<y1 and all(abs(v)<1_000_000 for v in (x0,y0,x1,y1)),
             'BBOX_DEGENERATE_'+role.replace('.','_'))
        need(x1>0 and y1>0 and x0<page[0] and y0<page[1],
             'BBOX_NOT_INTERSECTING_ARTBOARD_'+role.replace('.','_'))
        if role=='P01.RECIPIENT_BRANDING':
            need(name=='assets/recipient_branding.png' and layer.get('kind')=='raster'
                 and box==[26,134,188,191],'BRANDING_OVERRIDE_CHANGED')
            source_binding='PINNED_ACCEPTED_BRANDING_WITH_FIXED_OVERRIDE'
        else:
            need(isinstance(name,str) and name.startswith('assets/') and
                 '/' not in name[7:] and '..' not in name,'LAYER_ASSET_PATH_INVALID_'+role.replace('.','_'))
            # GC31 derives a transparent PNG from the pinned GRIGO SVG.
            # It is not a separate vault asset; preserve its source binding.
            derived=(role=='P04.SIGNATURE' and name=='assets/p04_grigo_signature.png')
            if derived:
                meta=entries.get('p04_grigo_signature.svg')
                need(isinstance(meta,dict) and
                     layer.get('source_graphic_sha256')==meta.get('sha256') and
                     layer.get('kind')=='raster' and meta.get('kind')=='vector',
                     'SIGNATURE_DERIVED_SOURCE_DRIFT')
            else:
                meta=entries.get(name[7:])
            need(isinstance(meta,dict) and isinstance(meta.get('sha256'),str) and
                 re.fullmatch('[0-9a-f]{64}',meta['sha256']) is not None and
                 (derived or meta.get('kind')==layer.get('kind')),'SOURCE_ASSET_NOT_BOUND_'+role.replace('.','_'))
            original=meta.get('bbox_mm')
            if role=='P01.SENDER_LOGO':
                need(box in ([64.5,59.5,149.5,144.5],[69,39,145,115]),'LOGO_OVERRIDE_CHANGED')
                source_binding='VAULT_SHA_WITH_PINNED_GC29_LOGO_OVERRIDE'
            else:
                need(isinstance(original,list) and len(original)==4 and
                     all(type(v) in (int,float) for v in original) and
                     all(math.isfinite(float(v)) for v in original) and
                     all(abs(float(a)-float(b))<=0.0001 for a,b in zip(original,box)),
                     'SOURCE_BBOX_DRIFT_'+role.replace('.','_'))
                source_binding=('DERIVED_PNG_FROM_PINNED_SVG_SOURCE' if derived
                                else 'EXACT_VAULT_SOURCE_BBOX')
        outside=[round(max(0.0,-x0),4),round(max(0.0,-y0),4),
                 round(max(0.0,x1-page[0]),4),round(max(0.0,y1-page[1]),4)]
        state='OUTSIDE_MEDIA_SOURCE_BOUND_VISUAL_REVIEW' if any(v>0.0001 for v in outside) else 'WITHIN_MEDIA_SOURCE_BOUND'
        classified.append({'role':role,'bbox_mm':[round(v,4) for v in (x0,y0,x1,y1)],
                           'outside_mm_left_top_right_bottom':outside,
                           'source_binding':source_binding,'state':state})
    return classified

def summarize_candidate(scene, job, logo, generated, jsx, old_shadow, vault=None):
    """No client text, logo bytes, usernames, or asset raw paths in report."""
    sid=job['job_id'];profile=old_shadow['variant']
    need(scene['job_id']==sid and scene['pages']==4,'SCENE_JOB_PAGES')
    need(scene.get('family')==profile['front'] and scene.get('signature')==profile['signature'] and
         scene.get('image_mode')==profile['image'],'SCENE_PROFILE_MISMATCH')
    need(scene['visual_approved'] is False and scene['production_ready'] is False,'AUTHORITY_DRIFT')
    roles=[r['role'] for r in scene['layers']]
    need(len(roles)==len(set(roles)),'DUPLICATE_ROLES')
    need(roles==old_shadow['layer_roles'],'SHADOW_ROLE_DRIFT')
    need(len(scene['sender_lines'])==old_shadow['sender_row_count'] and
         max(map(len,scene['sender_lines']))==old_shadow['sender_max_chars'],'SHADOW_SENDER_DRIFT')
    greeting=scene['greeting_text'];need(isinstance(greeting,str) and len(greeting)==old_shadow['greeting_chars'],'SHADOW_GREETING_DRIFT')
    need(len(generated)==len(old_shadow['generated_signature_asset_names']),'SHADOW_SIGNATURE_DRIFT')
    need((logo is not None)==old_shadow['accepted_branding_present'],'SHADOW_BRANDING_DRIFT')
    if vault is None:
        # Offline unit fixtures retain the strict legacy check; production
        # always supplies a GC29 SHA-verified source vault for triage.
        for r in scene['layers']:
            need(valid_rect(r['bbox_mm']),'ASSET_BBOX_OUTSIDE_ARTBOARD_'+r['role'].replace('.','_'))
        geometry=[]
    else:
        geometry=geometry_review(scene['layers'],vault)

    for key in ('P01.PAPER','P02.LOCKED_BASE','P03.FLOWERS','P04.SIGNATURE'):
        need(key in roles,'REQUIRED_ROLE_MISSING_'+key.replace('.','_'))
    logo_info=png_metadata(logo) if logo is not None else None
    if logo is not None:need(logo_info is not None,'BAS_BRANDING_NOT_VALID_PNG')
    need(scene.get('signature_graphic_placement') in ('SOURCE_PINNED_RASTER','SOURCE_PINNED_SVG_TO_TRANSPARENT_PNG'),
         'SIGNATURE_GRAPHIC_NOT_PINNED')
    need(isinstance(jsx,bytes) and 1_000<len(jsx)<MAX_JSX_BYTES,'JSX_SIZE_INVALID')
    warnings=['GENERIC_GC29_JSX_NOT_GC47AX_APPROVED_ZAP','P04_NATIVE_FONT_FIT_UNVERIFIED',
              'P03_NATIVE_CROP_UNVERIFIED','VISUAL_APPROVAL_ABSENT']
    if profile['signature']=='HERASYMENKO':warnings.append('HERASYMENKO_THREE_ROW_GEOMETRY_UNVERIFIED')
    if logo is not None:warnings.append('BAS_P01_BRANDING_PLACEMENT_UNVERIFIED')
    if len(greeting)>=800:warnings.append('LONG_GREETING_NATIVE_MEASUREMENT_REQUIRED')
    for g in geometry:
        if g['state']=='OUTSIDE_MEDIA_SOURCE_BOUND_VISUAL_REVIEW':
            warnings.append('SOURCE_BOUND_OUTSIDE_MEDIA_REVIEW_REQUIRED_'+g['role'].replace('.','_'))
    return {'job_id':sid,'variant':profile,'pages':4, 'renderer_variant':'GENERIC_GC29_READONLY_CANDIDATE',
            'jsx_sha256':digest(jsx),'jsx_size_bytes':len(jsx),
            'rendered_text_exported':False,'greeting_chars':len(greeting),
            'greeting_line_breaks':greeting.count('\n'),
            'greeting_longest_line_chars':max(map(len,greeting.splitlines() or [''])),
            'sender_row_count':len(scene['sender_lines']),
            'sender_max_chars':max(map(len,scene['sender_lines'])),
            'signature_placement':scene['signature_graphic_placement'],
            'branding_png':logo_info, 'layer_count':len(roles),
            'geometry_review':geometry, 'source_geometry_validated':vault is not None,
            'native_authorized':False,'queue_authorized':False,
            'production_ready':False,'visual_approved':False,
            'status':'CANDIDATE_JSX_COMPILED_IN_MEMORY_NO_NATIVE',
            'blocking_gates':warnings}

def native_candidates(root,client):
    az=az_module(root)
    proof=az.inspect(client,root)
    need(proof['status']=='PASS_FOUR_PROFILE_SOURCE_BOUND_NON_NATIVE' and
         proof['source']['git_head_expected']==az.EXPECTED_HEAD and
         proof['client_files_modified'] is False and proof['attempts_created'] is False,
         'AZ_SHADOW_NOT_PROVEN')
    t=az.module(root,'gc47t_client_windows_bridge_r001.py','gc47bb_gc47t')
    s,gc29=t.source_check()
    ws=s.workspace(client)
    jobs,arts,archive=gc29.accepted_jobs(ws)
    need(az.sha_file(archive)==az.ARCHIVE_SHA,'ACCEPTED_ARCHIVE_CHANGED')
    need([j['job_id'] for j in jobs]==[j[0] for j in az.JOBS],'JOB_ORDER_CHANGED')
    vault=ws/'template_studio/native_asset_vault_v0_1';catalog=gc29.verify_vault(vault)
    template=gc29.TEMPLATE
    need(isfile(template) and sha(template)==az.PINS['scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.jsx'],
         'GENERIC_JSX_TEMPLATE_DRIFT')
    text=template.read_text('utf8')
    need(text.count(JSX_MARK)==1 and len(text)<600_000,'JSX_TEMPLATE_MARKER')
    reports=[]
    for job,old in zip(jobs,proof['jobs']):
        logo=az.logo_from_accepted(job,arts,archive)
        scene=gc29.compile_scene(job,catalog,logo)
        generated=gc29.bind_illustrator_signature(scene,vault,catalog)
        packed=json.dumps(scene,ensure_ascii=True,separators=(',',':'))
        need(JSX_MARK not in packed,'JSX_SCENE_MARKER_INJECTION')
        jsx=text.replace(JSX_MARK,packed).encode('utf8')
        need(JSX_MARK.encode() not in jsx,'UNREPLACED_MARKER')
        reports.append(summarize_candidate(scene,job,logo,generated,jsx,old,catalog))
    rec=proof['recovery']
    state=root.parent/'.state'/'graphic_design_lab'/'lifecycle'
    can_lock=state/'gc47ax_single_lifecycle_r001.lock'
    state_present=isdir(state) and not state.is_symlink() and state.parent.is_dir() and not state.parent.is_symlink()
    if state_present:
        st=state.stat();state_present=stat.S_IMODE(st.st_mode)==0o700 and st.st_uid==os.geteuid()
    need(rec['tracked_count']==rec['tracked_expected']==9,'REPO_RECOVERY_SOURCE_NOT_TRACKED')
    plan={'mode':'NON_EXECUTING_CANDIDATE_REVIEW', 'queue_enabled':False,
          'all_items_explicitly_authorized':False,'automatic_retry':False,
          'required_between_items':['NATIVE_RESULT_VERIFIED','POSTFLIGHT_ILLUSTRATOR_CLOSED','NEW_ITEM_AUTHORITY'],
          'items':[{'job_id':r['job_id'],'position':i+1,'native_ready':False,
                    'queue_authorized':False,'state':'NATIVE_PROFILE_PROOF_REQUIRES_REVIEW'} for i,r in enumerate(reports)]}
    return {'schema_version':SCHEMA,'status':'PASS_FOUR_GENERIC_JSX_CANDIDATES_GEOMETRY_TRIAGED_NON_NATIVE',
            'source_sha256':az.ARCHIVE_SHA,'git_head_expected':az.EXPECTED_HEAD,
            'generic_jsx_template_sha256':sha(template),
            'profiles':reports,'queue':plan,
            'recovery':{'canonical_state_directory_present_and_scoped':state_present,
                        'canonical_lock_location':'GDL_SIBLING_STATE_OUTSIDE_TMP',
                        'all_pinned_repo_sources_tracked':True,
                        'external_vault_restore_verified':False,
                        'windows_gui_restore_verified':False,
                        'clean_redeploy_verified':False,
                        'source_inventory_only':True},
            'client_files_modified':False,'client_content_exported':False,
            'client_attempts_created':False,'windows_contacted':False,
            'native_dispatch':False,'visual_approved':False,'production_ready':False}

def save_report(root,out,report):
    target=root/'tmp'
    need(isdir(target) and not target.is_symlink(),'DELIVERY_TMP_NOT_DIRECTORY')
    need(out.parent.resolve(strict=True)==target.resolve(strict=True) and
         re.fullmatch(r'gc47bb_geometry_candidate_evidence_[a-z0-9_-]{1,40}\.zip',out.name),
         'OUTPUT_OUTSIDE_DELIVERY_TMP')
    need(not out.exists() and not out.is_symlink(),'EVIDENCE_WOULD_OVERWRITE')
    data=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
    need(len(data)<120_000,'EVIDENCE_TOO_LARGE')
    with out.open('xb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,obj in [('CANDIDATE_REPORT.json',report),('QUEUE_GATE.json',report['queue']),('RECOVERY_GATE.json',report['recovery'])]:
                info=zipfile.ZipInfo(name); info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(0o100600<<16)
                z.writestr(info,(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8'))
    os.chmod(out,0o600)
    with zipfile.ZipFile(out) as z:need(z.testzip() is None,'EVIDENCE_CRC')
    return sha(out)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','inspect'),required=True)
    p.add_argument('--client-name');p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    try:
        az=az_module();z=az.pinned_sources()
        print('GC47BB_PINS='+z['status'])
        old=CAN/'gc47ba_native_candidate_proof_r001.py'
        need(isfile(old) and sha(old)==GC47BA_R001_SHA,'GC47BA_BASELINE_DRIFT')
        if a.mode=='check':
            print('GC47BB_CHECK=PASS_FROZEN_SOURCES_GEOMETRY_TRIAGE_NO_CLIENT_NO_WINDOWS')
            return 0
        need(a.client_name and a.output is not None,'CLIENT_AND_EVIDENCE_REQUIRED')
        report=native_candidates(ROOT,a.client_name)
        digest=save_report(ROOT,a.output,report)
        for item in report['profiles']:
            source_overflow=sum(g['state']=='OUTSIDE_MEDIA_SOURCE_BOUND_VISUAL_REVIEW' for g in item['geometry_review'])
            print('GC47BB_JOB='+item['job_id']+' STATUS='+item['status']+' GATES='+str(len(item['blocking_gates']))+' SOURCE_OVERFLOW_ROLES='+str(source_overflow))
        print('GC47BB_PROFILES=PASS_FOUR_GENERIC_JSX_CANDIDATES_GEOMETRY_TRIAGED_NON_NATIVE')
        print('GC47BB_QUEUE=BLOCKED_NO_DISPATCH')
        print('GC47BB_RECOVERY=INVENTORY_ONLY_NOT_CLEAN_REDEPLOY')
        print('GC47BB_EVIDENCE='+str(a.output))
        print('GC47BB_EVIDENCE_SHA256='+digest)
        print('GC47BB_NATIVE_DISPATCH=FALSE CLIENT_MUTATION=FALSE GIT_MUTATION=FALSE')
        return 0
    except (Blocked,ValueError,OSError,TypeError,KeyError,ImportError,zipfile.BadZipFile,json.JSONDecodeError) as e:
        label=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47BB=BLOCKED_'+re.sub('[^A-Z0-9_]', '_',label.upper())[:90],file=sys.stderr)
        print('GC47BB_NO_NATIVE_NO_CLIENT_MUTATION=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
