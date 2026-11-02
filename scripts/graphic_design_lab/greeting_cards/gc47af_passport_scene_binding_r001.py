#!/usr/bin/env python3
"""GC47AF current accepted ZAP card: read-only, versioned GC47K scene binding.

No client data are written to GC47K. This is a non-release exact-baseline
profile. A later reviewed version can open approved parameter ranges.
"""
from __future__ import annotations
import copy
import hashlib
import json

KEY='gc47af_current_render_profile_v0_1'
BASE='gc47ae_current_card_baseline_v0_1'
SCHEMA='gdl_gc47af_passport_render_profile_r001'
JOB='gdl_gc_zap_20261011'
ATTEMPT='p20261030165430-a7f8dedf'
PHOTO='8d909fd3edb629e2ee2ac2fe4ee83726ba144f63b8e9f48945d963743d9cb637'
FRAME='d55aa31d5212250bb413b527b62af16f559e0bae0bbf5635ac1358b1d2a5c86f'
PROFILE_SHA='f824c7eb362f0b8fc8f84a085a66ee6691e955261294f8d4b8b09ed7c48f7924'

class Blocked(ValueError): pass

def need(cond,code):
    if not cond: raise Blocked('GC47AF_'+code)

def check_types(x):
    """Reject implicit coercion, NaN, duplicates are handled by registry reader."""
    def integer(v):return type(v) is int
    def number(v):return type(v) in (int,float) and -1e9<float(v)<1e9
    p=x['render']
    p01=p['P01']; p03=p['P03']; p04=p['P04']
    g=p04['greeting'];s=p04['sender']
    need(p01['font_name']=='MonotypeCorsiva' and integer(p01['font_pt']) and p01['font_pt']==52,'P01_FONT')
    need(number(p01['horizontal_anchor_mm']) and p01['horizontal_anchor_mm']==107,'P01_ANCHOR')
    need(p01['baselines_mm']==[222,243] and len(p01['baselines_mm'])==2,'P01_LINES')
    need(p['P02']=={'passport_id':'P02-010','locked':True},'P02_LOCK')
    need(p03['photo_sha256']==PHOTO and p03['compound_path_pdf_sha256']==FRAME and
         integer(p03['clip_segments']) and p03['clip_segments']==878 and
         p03['image_mode']=='DEFAULT_ASSET' and p03['resource_replacement_allowed'] is False,'P03_SOURCE')
    need(g['passport_id']=='P04-020' and g['native_id']=='P04-030.GREETING_SOURCE' and
         g['font_name']=='ZapfChanceryC' and number(g['font_pt']) and g['font_pt']==18.5 and
         g['box_mm']==[32,32,182,212] and
         g['fit_behavior']=='FIXED_18_5_PT_PILOT_CHECK_NOT_GENERAL_SHRINK_TO_FIT','P04_GREETING')
    need(s['passport_id']=='P04-025' and s['native_id_prefix']=='P04-060.SENDER_LINE_' and
         integer(s['row_count']) and s['row_count']==4 and s['left_mm']==32 and
         s['font_name']=='ZapfChanceryC' and s['font_pt_by_row']==[12,15,12,12] and
         s['baselines_mm']==[227,235,243,251] and s['canonical_six_rows_not_substituted'] is True,'P04_SENDER')
    need(p04['signature']=={'passport_id':'P04-030','asset_role':'P04.SIGNATURE'},'P04_SIGNATURE')


def validate_profile(pipeline,job_id=JOB):
    need(isinstance(pipeline,dict),'PIPELINE_TYPE')
    b=pipeline.get(BASE)
    need(isinstance(b,dict) and b.get('schema_version')=='gdl_gc47ae_current_card_baseline_r001','BASELINE_MISSING')
    need(b['scope']['client_job_id']==JOB and b['scope']['attempt_id']==ATTEMPT,'BASELINE_ID')
    need(b['authority']['visual_approved'] is False and b['authority']['production_ready'] is False,'BASELINE_AUTHORITY')
    need(b['current_design']['P04']['sender_live_count']==4 and b['current_design']['P04']['grigo_registry_canonical_count']==6,'BASELINE_ROWS')
    r=pipeline.get(KEY)
    need(isinstance(r,dict),'PROFILE_MISSING')
    need(r.get('schema_version')==SCHEMA and r.get('status')=='PASSIVE_LAB_RENDER_PROFILE_NOT_APPROVED','PROFILE_SCHEMA')
    need(r.get('job_id')==job_id==JOB and r.get('source_baseline_attempt')==ATTEMPT,'PROFILE_JOB')
    need(r.get('profile')=={'front':'STANDARD','input_image_mode':'DEFAULT_ASSET','signature':'GRIGO'},'PROFILE_VARIANT')
    a=r.get('authority',{})
    need(isinstance(a,dict) and a=={'production_ready':False,'visual_approved':False,'dual_runtime_enabled':False,'auto_runtime_retry':False,'no_client_publication':True},'PROFILE_AUTHORITY')
    c=r.get('compatibility',{})
    need(isinstance(c,dict) and c=={'gc47y_zap_only':True,'generic_font_fit_verified':False,'operator_approved_configuration_changes':False,'source_asset_sha_verified':True},'PROFILE_COMPAT')
    need(r.get('history')=='GC47AE_BASELINE_NON_AUTHORITATIVE_ONLY_NO_DESIGN_CHANGE','PROFILE_HISTORY')
    need(isinstance(r.get('render'),dict),'PROFILE_RENDER_MISSING')
    check_types(r)
    # prevent unreviewed metadata or arbitrary script injection in immutable v1 profile
    fingerprint=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('ascii')).hexdigest()
    need(fingerprint==PROFILE_SHA,'PROFILE_SHA_DRIFT')
    return copy.deepcopy(r)


def wrap_compile(original_compile,pipeline,job_id):
    profile=validate_profile(pipeline,job_id)
    def bound_compile(selected,vault_manifest,logo=None):
        need(selected.get('job_id')==job_id,'SELECTED_JOB_CHANGED')
        scene=original_compile(selected,vault_manifest,logo)
        need(scene.get('job_id')==JOB and scene.get('signature')=='GRIGO' and
             scene.get('image_mode')=='DEFAULT_ASSET' and
             scene.get('family')=='STANDARD','SCENE_PROFILE_CHANGED')
        need(len(scene.get('sender_lines',[]))==4 and len(scene.get('front_lines',[]))==2,'LIVE_ROW_COUNT_CHANGED')
        need('gc47af_render_profile' not in scene and 'gc47af_photo_sha256' not in scene,'SCENE_PREBOUND')
        scene['gc47af_render_profile']=copy.deepcopy(profile)
        scene['gc47af_photo_sha256']=PHOTO
        return scene
    return bound_compile
