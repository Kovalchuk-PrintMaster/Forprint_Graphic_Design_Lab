#!/usr/bin/env python3
"""GC47AQ: versioned GC47K/GC47AF/GC47AP binding, real-input shadow proof only.

No write to client SMB, repo canonical files, PREPRESS, Git or native attempts.
Read-only accepted job + vault; output only bounded, PRIVATE hashed evidence in GDL tmp.
"""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, stat, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
SRC = CAN/'gc47ap_parametric_candidate_r001.py'
SRC_SHA='26026fd6860e40274cdaaf2bd9307424435b974d038427b88a411146e9687bb9'
GC47T=CAN/'gc47t_client_windows_bridge_r001.py'
GC47T_SHA='c99fde8a5f5805da57b5cca037cda17a34dea002a076042279bd274c4848ef46'
GC47Y=CAN/'gc47y_review_amendment_r001.py'
GC47Y_SHA='30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312'
JSX=CAN/'gc29_native_four_page_gc47aq_candidate_r001.jsx'
JSX_SHA='a9c0692849aa5c850993d0f943031c59559c923fd64ac257f6b1c18d972fd63a'
PRO=CAN/'gc47aq_baseline_candidate_r001.json'
PRO_SHA='ca398e5cf4c7c9966ccd052b816b16bb00ef5dfe2a946175cc8534480c2e579a'
JOB='gdl_gc_zap_20261011'
SCHEMA='gdl_gc47aq_shadow_binding_r001'
MARK='/*__GC29_SCENE__*/'

class Blocked(ValueError):pass
def require(ok,code):
    if not ok:raise Blocked('GC47AQ_'+code)
def hashbytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return hashbytes(p.read_bytes())
def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def safe_load(path,key):
    spec=importlib.util.spec_from_file_location(key,path)
    require(spec is not None and spec.loader is not None,'MODULE_IMPORT')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def gate(root=ROOT,can=CAN):
    require(root.name=='forprint_graphic_design_lab' and (root/'.git').is_dir(), 'WRONG_GDL_ROOT')
    p=can/'gc47ap_parametric_candidate_r001.py'; t=can/'gc47t_client_windows_bridge_r001.py'; y=can/'gc47y_review_amendment_r001.py'; j=can/JSX.name; x=can/PRO.name
    for path,want in ((p,SRC_SHA),(t,GC47T_SHA),(y,GC47Y_SHA),(j,JSX_SHA),(x,PRO_SHA)):
        require(regular(path) and path.stat().st_size<=1_000_000,'SOURCE_UNSAFE_'+path.name)
        require(sha(path)==want,'SOURCE_DRIFT_'+path.name)
    ap=safe_load(p,'gc47aq_gc47ap')
    base,original=ap.verify_sources(root)  # exact SIX upstream source pins, GC47K baseline
    proposal=json.loads(x.read_text('utf8'))
    require(proposal==ap.candidate(base,original,{}),'PROPOSAL_NON_BASELINE_OR_DRIFT')
    require(proposal['requested_changes']=={},'UNAPPROVED_EDITS')
    require(all(value is False for value in proposal['authority'].values()),'CANDIDATE_AUTHORITY')
    original_jsx=(root/ap.JSX).read_text('utf8')
    require(ap.patch_jsx(original_jsx)==j.read_text('utf8'),'JSX_PATCH_INCONSISTENT')
    require(j.read_text('utf8').count(MARK)==1,'SCENE_MARKER')
    require('gc47ap_proposal' not in original_jsx,'CANONICAL_JSX_TAINTED')
    return ap,base,proposal

def apply_pipeline(gc29,af,y,ap,reg,base,proposal,selected,catalog,job_id):
    """Same sequence as GC47T/GC47Y but in memory. No call to GC29.prepare/start_one."""
    require(job_id==JOB and selected.get('job_id')==JOB,'JOB_SCOPE')
    bound=af.wrap_compile(gc29.compile_scene,reg,JOB)
    scene=bound(selected,catalog)
    scene=y.amend_scene(scene)
    scene=ap.transform_scene(scene,base,proposal)
    require(scene['gc47af_render_profile']==proposal['source_profile'],'PROFILE_BIND_FAILED')
    require(scene['gc47ap_proposal']['runtime_activation'] is False,'RUNTIME_AUTHORITY')
    require(scene['production_ready'] is False and scene['visual_approved'] is False,'SCENE_AUTHORITY')
    p3=[layer for layer in scene['layers'] if layer['role']=='P03.FRAME']
    require(len(p3)==1 and p3[0]['bbox_mm']==proposal['P03_FRAME_bbox_mm'],'FRAME_BIND_FAILED')
    require(scene['gc47af_render_profile']['render']['P04']['sender']['font_pt_by_row']==[12,15,12,12],'GRIGO_FONTS_CHANGED')
    require(len(scene['sender_lines'])==4,'GRIGO_LIVE_ROWS_CHANGED')
    return scene

def sanitized_report(scene,proposal,archive_sha,js_hash,source_hashes,generated):
    # No private text, no paths, no client name, no phone number in portable report.
    p=scene['gc47af_render_profile']['render']
    require(len(scene['layers'])>=3,'LAYER_SET_TOO_SHORT')
    return {'schema_version':SCHEMA,'status':'PASS_REAL_ACCEPTED_INPUT_SHADOW_ONLY',
      'job_id':JOB,'accepted_zip_sha256':archive_sha,'source_sha256':source_hashes,
      'compiled_jsx_sha256':js_hash,'template_jsx_sha256':JSX_SHA,'candidate_baseline_profile_sha256':PRO_SHA,
      'effective_proposal_sha256':hashbytes((json.dumps(proposal,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')),
      'proposed_fields':sorted(proposal['requested_changes']),
      'pages':scene['pages'],'variant':{'family':scene['family'],'image_mode':scene['image_mode'],'signature':scene['signature']},
      'render':{'P01':{'font_pt':p['P01']['font_pt'],'baselines_mm':p['P01']['baselines_mm']},
        'P02':{'locked':p['P02']['locked']},
        'P03':{'frame_bbox_mm':proposal['P03_FRAME_bbox_mm'],'photo_sha256':p['P03']['photo_sha256']},
        'P04':{'greeting_box_mm':p['P04']['greeting']['box_mm'],'sender_left_mm':p['P04']['sender']['left_mm'],
            'sender_font_pt_by_row':p['P04']['sender']['font_pt_by_row'],
            'sender_baselines_mm':p['P04']['sender']['baselines_mm'],'live_row_count':len(scene['sender_lines'])}},
      'generated_signature_assets':{name:hashbytes(value) for name,value in generated.items()},
      'native_attempt_created':False,'client_files_modified':False,'windows_contacted':False,
      'runtime_activation':False,'visual_approved':False,'production_ready':False,'dual_runtime_enabled':False,
      'known_remaining_gates':['VERSIONED_NATIVE_EXECUTION_NOT_AUTHORIZED',
         'NATIVE_VISUAL_EQUIVALENCE_NOT_VERIFIED','PRODUCTION_APPROVAL_NOT_GRANTED']}

def run_shadow(root,can,client,job,draft=None):
    ap,base,proposal=gate(root,can)
    if draft is not None:
        require(regular(draft) and draft.stat().st_size<10000,'DRAFT_UNSAFE')
        d=json.loads(draft.read_text('utf8'))
        require(type(d)==dict and set(d)=={'schema_version','changes'} and d['schema_version']=='gc47ap_edit_proposal_r001','DRAFT_SCHEMA')
        proposal=ap.candidate(base,proposal['source_profile'],d['changes'])
        require(all(v is False for v in proposal['authority'].values()),'DRAFT_AUTHORITY')
    require(job==JOB,'JOB_NOT_SUPPORTED')
    t=safe_load(can/GC47T.name,'gc47aq_gc47t')
    y=safe_load(can/GC47Y.name,'gc47aq_gc47y')
    # GC47T.source_check enforces GC47S, GC29, GC47AF, GC47Y, GC47AC, GC47K source pins.
    s,gc29=t.source_check()
    ws,selected,archive,variants=t.validate_job(s,gc29,client,job)
    require(variants['front']=='STANDARD' and variants['image']=='DEFAULT_ASSET' and variants['signature']=='GRIGO','VARIANT')
    photo,frame=y.check_sources(ws,selected,archive)
    vault=ws/'template_studio/native_asset_vault_v0_1'
    catalog=gc29.verify_vault(vault)
    reg=s.read_obj(s.REGISTRY,5_000_000)['greeting_card_machine_pipeline_v0_1']
    af=t.gc47af_mod()
    scene=apply_pipeline(gc29,af,y,ap,reg,base,proposal,selected,catalog,job)
    generated=gc29.bind_illustrator_signature(scene,vault,catalog)
    marker_text=(can/JSX.name).read_text('utf8')
    packed=json.dumps(scene,ensure_ascii=True,separators=(',',':'))
    require(MARK not in packed and marker_text.count(MARK)==1,'RENDER_INJECTION_OR_MARKER')
    compiled=marker_text.replace(MARK,packed)
    require(MARK not in compiled,'JSX_REPLACE_FAILED')
    require('gc47ap_proposal' in compiled,'JSX_PROPOSAL_NOT_EMBEDDED')
    h=hashbytes(compiled.encode('utf8'))
    src={rel:ap.SOURCE_PINS[rel] for rel in sorted(ap.SOURCE_PINS)}
    # Accepted job/source and frame/photo checked in native read-only path.
    return sanitized_report(scene,proposal,sha(archive),h,src,generated)

def write_evidence(out,report,root):
    require(not out.exists() and not out.is_symlink(),'OUTPUT_ALREADY_EXISTS')
    require(out.parent.is_dir() and not out.parent.is_symlink(),'OUTPUT_PARENT')
    require(out.parent.resolve(strict=True)==(root/'tmp').resolve(strict=True),'PRIVATE_GDL_TMP_ONLY')
    require(out.name.startswith('gc47aq_shadow_') and len(out.name)<80,'OUTPUT_NAME')
    out.mkdir(mode=0o700)
    path=out/'gc47aq_shadow_evidence.zip'
    data=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')
    (out/'GC47AQ_SHADOW_REPORT.json').write_bytes(data)
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        info=zipfile.ZipInfo('GC47AQ_SHADOW_REPORT.json'); info.external_attr=(0o100600<<16)
        info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    with zipfile.ZipFile(path) as z:require(z.testzip() is None,'ZIP_CRC')
    os.chmod(out/'GC47AQ_SHADOW_REPORT.json',0o600)
    os.chmod(path,0o600)
    return path

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('check','shadow'))
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--client-name');p.add_argument('--job-id');p.add_argument('--output',type=Path);p.add_argument('--draft-json',type=Path)
    a=p.parse_args(argv)
    try:
        require(a.mode=='shadow' or a.draft_json is None,'DRAFT_ONLY_IN_SHADOW')
        gate(a.root,CAN)
        print('GC47AQ_PINS=PASS_CANDIDATE_AND_SIX_ORIGINAL_SOURCES')
        if a.mode=='shadow':
            require(a.client_name and a.job_id==JOB and a.output,'SHADOW_ARGUMENTS')
            report=run_shadow(a.root,CAN,a.client_name,a.job_id,a.draft_json)
            out=write_evidence(a.output,report,a.root)
            print('GC47AQ_SHADOW=PASS_REAL_ACCEPTED_JOB_VERSIONED_SCENE_NON_NATIVE')
            print('GC47AQ_SHADOW_EVIDENCE='+str(out))
            print('GC47AQ_GENERATED_JSX_SHA256='+report['compiled_jsx_sha256'])
        else:
            print('GC47AQ_CHECK=PASS_NO_CLIENT_READ_NO_NATIVE')
        print('GC47AQ_GC47T_UNCHANGED=TRUE GC47K_UNCHANGED=TRUE')
        print('GC47AQ_WINDOWS_CONTACTED=FALSE NATIVE_ATTEMPT_CREATED=FALSE PRODUCTION_READY=FALSE')
        print('GC47AQ_CHECKPOINT=VERSIONED_SHADOW_BINDING_NON_AUTHORIZING')
        return 0
    except (Blocked,ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,RuntimeError) as e:
        print('GC47AQ_BLOCKED='+str(e),file=sys.stderr)
        print('GC47AQ_NO_AUTO_RETRY=TRUE NO_NATIVE_DISPATCH=TRUE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
