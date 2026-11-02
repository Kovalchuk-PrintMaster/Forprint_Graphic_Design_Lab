#!/usr/bin/env python3
"""GC47Y ZAP-only, source-bound laboratory source amendment for GC47T.

The accepted archive and vault are immutable. The amendment applies ONLY to
new private GC47S attempts. Never changes client input, prior attempts, or GDL
GC29 canonical sources. It is not a production/customer approval.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat

SCHEMA='gdl_gc47y_review_amendment_r001'
JOB='gdl_gc_zap_20261011'
ACCEPTED_ZIP='90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064'
FLOWER_OLD='56392d9d229c665137bc52e550e629ba506c2dd8a9f209ea1b5bb214762f9c1e'
FLOWER_NEW='8d909fd3edb629e2ee2ac2fe4ee83726ba144f63b8e9f48945d963743d9cb637'
FRAME='d55aa31d5212250bb413b527b62af16f559e0bae0bbf5635ac1358b1d2a5c86f'
CLIP_SEGMENTS=878
FONT_PT=18.5

def require(ok,code):
    if not ok: raise ValueError('GC47Y_'+code)

def sha(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as fd:
        for b in iter(lambda:fd.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def regular(p:Path):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def check_sources(ws:Path,job:dict,accepted_archive:Path):
    require(job.get('job_id')==JOB,'JOB_OUTSIDE_AMENDMENT_SCOPE')
    b=job.get('builder_v1') or {}
    require((b.get('front') or {}).get('family')=='STANDARD','FRONT_VARIANT_CHANGED')
    require((b.get('inside_image') or {}).get('mode')=='DEFAULT_ASSET','PHOTO_PROFILE_CHANGED')
    require((b.get('sender_text') or {}).get('signature_variant_id')=='GRIGO','SENDER_PROFILE_CHANGED')
    require((job.get('signature_selection') or {}).get('variant_id')=='GRIGO','SENDER_CHOICE_CHANGED')
    require(regular(accepted_archive) and sha(accepted_archive)==ACCEPTED_ZIP,'ACCEPTED_SOURCE_DRIFT')
    client=ws.parent
    for relative in ('info','info/sample','info/frame'):
        p=client/relative
        require(p.is_dir() and not p.is_symlink(),'SOURCE_PARENT_NOT_NORMAL_'+relative.replace('/','_'))
    photo=client/'info/sample/flower_photo.png'
    frame=client/'info/frame/compound_path.pdf'
    require(regular(photo) and regular(frame),'SOURCE_NOT_REGULAR')
    require(photo.stat().st_size==1013089 and sha(photo)==FLOWER_NEW,'PHOTO_SHA_SIZE_DRIFT')
    require(frame.stat().st_size==871628 and sha(frame)==FRAME,'FRAME_SHA_SIZE_DRIFT')
    # Check image header and exact aspect ratio without mandatory image libs here.
    with photo.open('rb') as f: hdr=f.read(24)
    require(hdr[:8]==bytes.fromhex('89504e470d0a1a0a') and
            int.from_bytes(hdr[16:20],'big')==703 and int.from_bytes(hdr[20:24],'big')==1060,
            'PHOTO_DIMENSION_DRIFT')
    with frame.open('rb') as f:require(f.read(5)==b'%PDF-','FRAME_NOT_PDF')
    return photo,frame

def amend_scene(scene:dict):
    require(scene.get('schema_version')=='gdl_gc29_native_scene_v0_1' and scene.get('job_id')==JOB,'SCENE_CHANGED')
    require(scene.get('image_mode')=='DEFAULT_ASSET' and scene.get('signature')=='GRIGO','SCENE_PROFILE_CHANGED')
    flowers=[x for x in scene.get('layers',[]) if x.get('role')=='P03.FLOWERS']
    require(len(flowers)==1 and flowers[0].get('file')=='assets/p03_flowers.png','FLOWER_ROLE_CHANGED')
    width=198.0;height=round(width*1060/703,6)
    require(height<301,'PHOTO_BBOX_OUTSIDE_ARTBOARD')
    flowers[0]['bbox_mm']=[round((214-width)/2,6),round((301-height)/2,6),
                           round((214+width)/2,6),round((301+height)/2,6)]
    scene['gc47y_pilot_amendment']={'schema':SCHEMA,'photo_sha256':FLOWER_NEW,
        'frame_sha256':FRAME,'clip_main_segments':CLIP_SEGMENTS,'p04_fit_tier_pt':FONT_PT,
        'photo_visual_approved':False,'full_card_verified':False,'production_ready':False}
    return scene

def wrap_prepare(gc29,original,ws,job,archive):
    """Return new attempt-specific wrapper bound to a unique accepted job.

    GC47S creates receipt *after* this returns, so sha of JSX/scene is correctly
    snapshotted. Only newly allocated GDL private run assets are modified.
    """
    photo,frame=check_sources(ws,job,archive)
    original_compile=gc29.compile_scene
    def local_compile(selected,vault_manifest,logo=None):
        need=selected.get('job_id')==JOB
        require(need,'SELECTED_JOB_CHANGED')
        scene=original_compile(selected,vault_manifest,logo)
        return amend_scene(scene)
    def private_prepare(workspace,job_id,run_id):
        require(workspace==ws and job_id==JOB,'ATTEMPT_SCOPE_CHANGED')
        check_sources(ws,job,archive)
        gc29.compile_scene=local_compile
        try:
            dest,scene=original(workspace,job_id,run_id)
        finally:gc29.compile_scene=original_compile
        require(dest==workspace/'template_studio/native_runs'/(job_id+'__'+run_id),'RUN_LOCATION_CHANGED')
        asset=dest/'assets/p03_flowers.png'
        require(regular(asset) and sha(asset)==FLOWER_OLD,'ORIGINAL_NEW_RUN_FLOWER_DRIFT')
        # Copy to newly created private run only. Do not modify frozen vault.
        staged=dest/'assets/p03_flowers.png.gc47y_tmp'
        require(not staged.exists(),'PHOTO_OVERRIDE_PARTIAL_EXISTS')
        with staged.open('xb') as fd:
            with photo.open('rb') as src:
                for block in iter(lambda:src.read(1<<20),b''):fd.write(block)
            fd.flush();os.fsync(fd.fileno())
        require(sha(staged)==FLOWER_NEW,'PHOTO_STAGE_HASH_DRIFT')
        os.replace(staged,asset)
        manifest=dest/'scene_manifest.json'
        require(regular(manifest),'SCENE_MANIFEST_NOT_WRITTEN')
        public=json.loads(manifest.read_text('utf8'))
        require(public.get('asset_sha256',{}).get('p03_flowers.png')==FLOWER_OLD,'ORIGINAL_MANIFEST_DRIFT')
        public['asset_sha256']['p03_flowers.png']=FLOWER_NEW
        public['gc47y_pilot_amendment']=scene['gc47y_pilot_amendment']
        required={'photo_sha256':FLOWER_NEW,'frame_sha256':FRAME,'accepted_zip_sha256':ACCEPTED_ZIP}
        public['gc47y_source_receipt']={'schema':SCHEMA,**required,'operator_review_required':True}
        ptmp=dest/'scene_manifest.json.gc47y_tmp'
        require(not ptmp.exists(),'MANIFEST_OVERRIDE_PARTIAL_EXISTS')
        with ptmp.open('x',encoding='utf8') as fd:json.dump(public,fd,sort_keys=True,indent=2,ensure_ascii=False);fd.write('\n')
        os.replace(ptmp,manifest)
        require(sha(asset)==FLOWER_NEW and json.loads(manifest.read_text('utf8'))['asset_sha256']['p03_flowers.png']==FLOWER_NEW,'FINAL_SOURCE_BINDING_FAILED')
        return dest,scene
    return private_prepare
