#!/usr/bin/env python3
"""GC47AP: source-bound, non-authorizing parameteric scene prototype.

NEVER edits canonical GDL, client SMB, existing attempt, GC47T or git.
Produces private candidate evidence only, not an Illustrator executable launch.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, stat, tempfile, zipfile
from pathlib import Path

SCHEMA = 'gdl_gc47ap_parametric_candidate_r001'
SOURCE_PINS = {
 'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json':'ee4c8b09245e66baf34a2975e71b3902d26a1f318901ec06bc47cbbc0bb2447e',
 'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py':'c99fde8a5f5805da57b5cca037cda17a34dea002a076042279bd274c4848ef46',
 'scripts/graphic_design_lab/greeting_cards/gc47af_passport_scene_binding_r001.py':'3e13ef9a11db5b587052271930069852a6c24baa80d0d5f3c326bb3aed402203',
 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_gc47af_passport_runtime_r001.jsx':'ffa5a4dfeb27382be47529619d3962900b59fe6c8b8d456192beb07a0ed3ae17',
 'scripts/graphic_design_lab/greeting_cards/gc47y_review_amendment_r001.py':'30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312',
 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py':'c891a34d0ff46029f53f29348b006f90a4c78b0372970ef989e971aff44bbd42',
}
REG = next(k for k in SOURCE_PINS if k.endswith('ts_full_registry_v0_1.json'))
JSX = next(k for k in SOURCE_PINS if k.endswith('gc47af_passport_runtime_r001.jsx'))
BASE_KEY='gc47ae_current_card_baseline_v0_1'
PROFILE_KEY='gc47af_current_render_profile_v0_1'
FIELDS={'P03.FRAME.bbox_mm','P04.GREETING.box_mm','P04.SENDER.left_mm','P04.SENDER.font_pt_by_row','P04.SENDER.baselines_mm'}

class Blocked(ValueError): pass

def require(value, code):
    if not value: raise Blocked('GC47AP_'+code)

def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(p.read_bytes())
def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def verify_sources(root):
    require(root.name=='forprint_graphic_design_lab','GDL_ROOT')
    for rel,want in SOURCE_PINS.items():
        p=root/rel
        require(regular(p) and p.stat().st_size<7_000_000,'SOURCE_MISSING_OR_UNSAFE_'+p.name)
        require(sha(p)==want,'SOURCE_SHA_DRIFT_'+p.name)
    reg=json.loads((root/REG).read_text('utf8'))
    pipeline=reg['greeting_card_machine_pipeline_v0_1']
    base=pipeline[BASE_KEY]
    profile=pipeline[PROFILE_KEY]
    require(base['scope']['client_job_id']=='gdl_gc_zap_20261011','BASELINE_JOB_DRIFT')
    require(base['authority']['production_ready'] is False and base['authority']['visual_approved'] is False,'BASELINE_AUTHORITY')
    require(profile['authority']=={'production_ready':False,'visual_approved':False,'dual_runtime_enabled':False,'auto_runtime_retry':False,'no_client_publication':True},'PROFILE_AUTHORITY')
    require(profile['schema_version']=='gdl_gc47af_passport_render_profile_r001','PROFILE_SCHEMA')
    p3=base['current_design']['asset_layers_current_attempt']['P03.FRAME']
    require(p3['page']==3 and p3['bbox_mm']==[5.5,6.9265,208.5,294.0733],'FRAME_REFERENCE_CHANGED')
    require(profile['render']['P04']['greeting']['box_mm']==[32,32,182,212],'P04_BASELINE')
    require(profile['render']['P04']['sender']['font_pt_by_row']==[12,15,12,12],'P04_FONT_BASELINE')
    require(profile['render']['P04']['sender']['baselines_mm']==[227,235,243,251],'P04_SENDER_BASELINE')
    require(base['current_design']['P04']['grigo_registry_canonical_count']==6 and base['current_design']['P04']['sender_live_count']==4,'GRIGO_COUNTS')
    return base,profile

def isnum(x):return type(x) in (int,float) and -1e6<float(x)<1e6

def vec4(v,code):
    require(type(v)==list and len(v)==4 and all(isnum(x) for x in v),code)
    return [float(x) for x in v]

def validate_overrides(base,profile, changes):
    require(type(changes)==dict and set(changes)<=FIELDS and len(changes)<=5,'UNKNOWN_FIELD')
    layer=base['current_design']['asset_layers_current_attempt']['P03.FRAME']['bbox_mm']
    for field,val in changes.items():
        if field=='P03.FRAME.bbox_mm':
            b=vec4(val,'P03_FRAME_TYPE')
            require(all(abs(a-c)<=5.0 for a,c in zip(b,layer)) and b[2]-b[0]>185 and b[3]-b[1]>275,'P03_FRAME_BOUND')
            require(0<=b[0]<b[2]<=214 and 0<=b[1]<b[3]<=301,'P03_FRAME_PAGE')
        elif field=='P04.GREETING.box_mm':
            b=vec4(val,'P04_BOX_TYPE');cur=profile['render']['P04']['greeting']['box_mm']
            require(all(abs(a-c)<=5.0 for a,c in zip(b,cur)) and 0<=b[0]<b[2]<=214 and 0<=b[1]<b[3]<=301 and b[2]-b[0]>=140 and b[3]-b[1]>=170,'P04_BOX_BOUND')
        elif field=='P04.SENDER.left_mm':
            require(isnum(val) and 25<=float(val)<=39,'P04_SENDER_LEFT_BOUND')
        elif field=='P04.SENDER.font_pt_by_row':
            b=vec4(val,'P04_FONT_TYPE');cur=profile['render']['P04']['sender']['font_pt_by_row']
            require(all(9<=a<=18 and abs(a-c)<=2 for a,c in zip(b,cur)),'P04_FONT_BOUND')
        elif field=='P04.SENDER.baselines_mm':
            b=vec4(val,'P04_BASELINE_TYPE');cur=profile['render']['P04']['sender']['baselines_mm']
            require(all(abs(a-c)<=4.0 for a,c in zip(b,cur)) and all(b[i+1]-b[i]>=4 for i in range(3)),'P04_BASELINES_BOUND')
    return changes

def candidate(base,profile,changes):
    validate_overrides(base,profile,changes)
    proposed=copy.deepcopy(profile)
    frame=copy.deepcopy(base['current_design']['asset_layers_current_attempt']['P03.FRAME']['bbox_mm'])
    for field,value in changes.items():
        if field=='P03.FRAME.bbox_mm':frame=copy.deepcopy(value)
        elif field=='P04.GREETING.box_mm':proposed['render']['P04']['greeting']['box_mm']=copy.deepcopy(value)
        elif field=='P04.SENDER.left_mm':proposed['render']['P04']['sender']['left_mm']=copy.deepcopy(value)
        elif field=='P04.SENDER.font_pt_by_row':proposed['render']['P04']['sender']['font_pt_by_row']=copy.deepcopy(value)
        elif field=='P04.SENDER.baselines_mm':proposed['render']['P04']['sender']['baselines_mm']=copy.deepcopy(value)
    # Keep old schema untouched: candidate is separate, not a replacement GC47AF profile.
    return {'schema_version':SCHEMA, 'source_profile_schema':proposed['schema_version'],
        'source_profile':proposed, 'original_profile_sha256':digest(jsonbytes(profile)), 'P03_FRAME_bbox_mm':frame,
        'requested_changes':copy.deepcopy(changes), 'authority':{
            'visual_approved':False,'production_ready':False,'dual_runtime_enabled':False,
            'runtime_activation':False,'native_execution_allowed':False,'auto_retry':False,
            'client_publication_allowed':False}}

def transform_scene(scene,baseline,proposal):
    """Pure scene prototype; NOT integrated into GC47T. Enforce single frame."""
    require(scene.get('job_id')=='gdl_gc_zap_20261011' and scene.get('signature')=='GRIGO' and scene.get('image_mode')=='DEFAULT_ASSET','SCENE_IDENTITY')
    require(scene.get('production_ready') is False and scene.get('visual_approved') is False,'SCENE_AUTHORITY')
    layers=[v for v in scene.get('layers',[]) if v.get('role')=='P03.FRAME']
    require(len(layers)==1 and layers[0]['page']==3,'SCENE_FRAME_MISSING')
    before=baseline['current_design']['asset_layers_current_attempt']['P03.FRAME']['bbox_mm']
    require([round(x,5) for x in layers[0]['bbox_mm']]==[round(x,5) for x in before],'SCENE_FRAME_BASELINE_DRIFT')
    require('gc47af_render_profile' in scene,'SCENE_PROFILE_MISSING')
    require(digest(jsonbytes(scene['gc47af_render_profile']))==proposal['original_profile_sha256'],'SCENE_PROFILE_DRIFT')
    out=copy.deepcopy(scene)
    next((x for x in out['layers'] if x['role']=='P03.FRAME'))['bbox_mm']=copy.deepcopy(proposal['P03_FRAME_bbox_mm'])
    out['gc47af_render_profile']=copy.deepcopy(proposal['source_profile'])
    out['gc47ap_proposal']={'schema_version':SCHEMA,'runtime_activation':False,'visual_approved':False,'production_ready':False}
    return out

def patch_jsx(text):
    # Patch duplicated P04 fit geometry to read the same box used for drawing.
    original="""    // Fixed PDF zone [32,32,182,212] mm on the FOURTH artboard.\n    need(Math.abs(minX-(ax(4)+32*PT))<0.1 &&\n         Math.abs(maxX-(ax(4)+182*PT))<0.1 &&\n         Math.abs(minY-(H-212*PT))<0.1 &&\n         Math.abs(maxY-(H-32*PT))<0.1,'GC47W_FIXED_BOX_CHANGED');"""
    updated="""    // GC47AP: use the SAME passport rectangle for drawing and fidelity checks.\n    var zone=spec.render.P04.greeting.box_mm;\n    need(Math.abs(minX-(ax(4)+zone[0]*PT))<0.1 &&\n         Math.abs(maxX-(ax(4)+zone[2]*PT))<0.1 &&\n         Math.abs(minY-(H-zone[3]*PT))<0.1 &&\n         Math.abs(maxY-(H-zone[1]*PT))<0.1,'GC47AP_PROFILE_BOX_CHANGED');"""
    require(text.count(original)==1,'JSX_ANCHOR_NOT_UNIQUE')
    text=text.replace(original,updated)
    guard_old="""      p.greeting.font_name==='ZapfChanceryC' && p.greeting.font_pt===18.5 &&
      b.length===4 && b[0]===32 && b[1]===32 && b[2]===182 && b[3]===212 &&
      s.passport_id==='P04-025' && s.row_count===4 && scene.sender_lines.length===4 &&
      s.font_name==='ZapfChanceryC' && s.left_mm===32 &&
      s.font_pt_by_row.length===4 && s.baselines_mm.length===4 &&
      s.font_pt_by_row[0]===12 && s.font_pt_by_row[1]===15 &&
      s.font_pt_by_row[2]===12 && s.font_pt_by_row[3]===12 &&
      s.baselines_mm[0]===227 && s.baselines_mm[1]===235 &&
      s.baselines_mm[2]===243 && s.baselines_mm[3]===251 &&"""
    guard_new="""      p.greeting.font_name==='ZapfChanceryC' && p.greeting.font_pt===18.5 &&
      b.length===4 && isFinite(b[0]) && isFinite(b[1]) && isFinite(b[2]) && isFinite(b[3]) &&
      b[0]>=27 && b[0]<=37 && b[1]>=27 && b[1]<=37 &&
      b[2]>=177 && b[2]<=187 && b[3]>=207 && b[3]<=217 &&
      b[2]-b[0]>=140 && b[3]-b[1]>=170 &&
      s.passport_id==='P04-025' && s.row_count===4 && scene.sender_lines.length===4 &&
      s.font_name==='ZapfChanceryC' && s.left_mm>=25 && s.left_mm<=39 &&
      s.font_pt_by_row.length===4 && s.baselines_mm.length===4 &&
      s.font_pt_by_row[0]>=10 && s.font_pt_by_row[0]<=14 &&
      s.font_pt_by_row[1]>=13 && s.font_pt_by_row[1]<=17 &&
      s.font_pt_by_row[2]>=10 && s.font_pt_by_row[2]<=14 &&
      s.font_pt_by_row[3]>=10 && s.font_pt_by_row[3]<=14 &&
      s.baselines_mm[0]>=223 && s.baselines_mm[0]<=231 &&
      s.baselines_mm[1]>=231 && s.baselines_mm[1]<=239 &&
      s.baselines_mm[2]>=239 && s.baselines_mm[2]<=247 &&
      s.baselines_mm[3]>=247 && s.baselines_mm[3]<=255 &&
      s.baselines_mm[1]-s.baselines_mm[0]>=4 &&
      s.baselines_mm[2]-s.baselines_mm[1]>=4 &&
      s.baselines_mm[3]-s.baselines_mm[2]>=4 &&"""
    require(text.count(guard_old)==1,'JSX_GUARD_NOT_UNIQUE')
    text=text.replace(guard_old,guard_new)
    fit_old='(lineCount+2)*leadingMm<=179.5;'
    fit_new='(lineCount+2)*leadingMm<=(spec.render.P04.greeting.box_mm[3]-spec.render.P04.greeting.box_mm[1]-0.5);'
    require(text.count(fit_old)==1,'JSX_FIT_NOT_UNIQUE')
    return text.replace(fit_old,fit_new)

def jsonbytes(o):return (json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf8')

def archive_files(root,zip_path,files):
    require(not zip_path.exists() and not zip_path.is_symlink(),'EVIDENCE_ALREADY_EXISTS')
    with zipfile.ZipFile(zip_path,'x',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            require(name and not name.startswith('/') and '..' not in name.split('/'),'ZIP_PATH')
            z.writestr(name,data)
    with zipfile.ZipFile(zip_path) as z:require(z.testzip() is None,'ZIP_CRC')

def stage(root,out,changes):
    require(not out.exists() and not out.is_symlink(),'STAGE_EXISTS')
    require(out.parent.is_dir() and not out.parent.is_symlink(),'STAGE_PARENT')
    baseline,profile=verify_sources(root)
    proposed=candidate(baseline,profile,changes)
    patched=patch_jsx((root/JSX).read_text('utf8'))
    # JS source candidate alone is insufficient for native launch: GC47T remains pinned to baseline.
    evidence={'schema_version':SCHEMA, 'source_pins':SOURCE_PINS,
      'baseline_render':profile['render'], 'requested_changes':changes,
      'candidate_sha256':digest(jsonbytes(proposed)),
      'jsx_candidate_sha256':digest(patched.encode('utf8')),
      'source_jsx_sha256':SOURCE_PINS[JSX], 'baseline_geometry_identical': changes=={},
      'P03_FRAME':proposed['P03_FRAME_bbox_mm'], 'P04_box':proposed['source_profile']['render']['P04']['greeting']['box_mm'],
      'GC47T_unchanged':True,'GC47AF_unchanged':True, 'GC47K_unchanged':True,
      'source_render_linked_to_live':False, 'needs_operator_native_review':True,
      'production_ready':False, 'visual_approved':False,
      'activation_blockers':['GC47T_VERSIONED_BRIDGE_NOT_INTEGRATED','GC47AF_PROFILE_HASH_STILL_PINS_BASELINE','NATIVE_VISUAL_EQUIVALENCE_NOT_RUN']}
    evidence_files={'candidate_profile.json':jsonbytes(proposed),
       'candidate_jsx/gc29_native_four_page_gc47ap_candidate_r001.jsx':patched.encode('utf8'),
       'PROVENANCE_AND_LIMITS.json':jsonbytes(evidence)}
    os.mkdir(out,0o700)
    try:
        for name,data in evidence_files.items():
            p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as h:h.write(data)
        zpath=out/'gc47ap_candidate_evidence.zip'
        archive_files(root,zpath,evidence_files)
    except Exception:
        # preserve partial private artifacts for operator diagnostics, no destructive cleanup.
        raise
    return zpath,evidence

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--mode',required=True,choices=['check','stage'])
    a.add_argument('--root',type=Path,required=True)
    a.add_argument('--output',type=Path)
    a.add_argument('--draft-json',type=Path)
    x=a.parse_args()
    try:
        base,profile=verify_sources(x.root)
        print('GC47AP_SOURCE_PINS=PASS_6_OF_6')
        print('GC47AP_BASELINE=PASS_GC47K_GC47AF_GC47AE')
        if x.mode=='stage':
            require(x.output is not None,'STAGE_OUTPUT_REQUIRED')
            changes={}
            if x.draft_json:
                require(regular(x.draft_json) and x.draft_json.stat().st_size<10_000,'DRAFT_FILE_UNSAFE')
                d=json.loads(x.draft_json.read_text('utf8'))
                require(type(d)==dict and set(d)=={'schema_version','changes'} and d['schema_version']=='gc47ap_edit_proposal_r001','DRAFT_SCHEMA')
                changes=d['changes']
            z,e=stage(x.root,x.output,changes)
            print('GC47AP_STAGE='+str(x.output))
            print('GC47AP_EVIDENCE='+str(z))
            print('GC47AP_PROPOSAL_CHANGES='+str(len(changes)))
        print('GC47AP_NO_NATIVE_DISPATCH=TRUE NO_PASSPORT_WRITE=TRUE NO_GIT_MUTATION=TRUE')
        print('GC47AP_CHECKPOINT=SOURCE_BOUND_PARAMETRIC_CANDIDATE_NON_AUTHORIZING')
    except (Blocked,ValueError,KeyError,OSError,json.JSONDecodeError) as e:
        print('GC47AP_BLOCKED='+str(e));raise SystemExit(2)

if __name__=='__main__':main()
