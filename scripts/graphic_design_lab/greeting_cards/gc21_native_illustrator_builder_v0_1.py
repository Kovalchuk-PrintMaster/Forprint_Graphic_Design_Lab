#!/usr/bin/env python3
"""GC21: source-bound, four-artboard Illustrator *candidate* from existing accepted card.

No Windows execution and no reuse of an imported entire PDF. Extract only
canonical individual artwork from source-verified PDFs, plus exact accepted
portrait and greeting text. All private JSX/assets stay under this repo's tmp/.
A prepared scene is NOT a validated Illustrator artifact or print-ready file.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent
TEMPLATE = SCRIPTS / 'gc21_four_artboard_native_v0_1.jsx'
SIZE = (214.0, 301.0)
MM = 25.4 / 72
PILOT_HASHES = {
    'bundle': '0aedc7e09db54a9cc2fb1e85085bd4305f232a51983121839634a83fe5dab709',
    'resource_manifest': 'f01312d36937791fd5fbc876ed357ba84b9c5bf888691eb40fb1cae955f8a43e',
    'artifact_manifest': 'cb67ce7ad9e9832f6b9a63b5f00529986f54e21c4c50e1f5f468364d7064c0c4',
}
RESOURCE_ID = 'template.greeting_card.dolinska.v1'
SENDER_SOURCE_ID = 'source.greeting_card.signature.herasymenko.v1'
SENDER_SHA = 'a5392be1234c026d1200cad288a3b4989f506f8eb32522dcbe6236bb221722a8'
REFERENCE_SHA = '66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85'
CANONICAL_REFERENCE_SHA = '66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85'
P01_LOGO_BBOX_MM = (64.26, 59.26, 149.74, 144.47)
P01_LOGO_PIXEL_SIZE = (949, 946)
HASHES = {
 'paper': '7e00983a508f9c59fb6148e9d33a52ca',
 'frame': 'b136196cfb1dcc996333e75707257946',
 'logo': '78b87a619527',  # source-map MD5 prefix; old 31-hex pseudo-MD5 was invalid
 'portrait_reference': '853869badb84',
}
SCENE_SCHEMA = 'gdl_gc21_native_four_artboards_scene_v0_1'
VALID_NAME = re.compile(r'^[a-z][a-z0-9_-]{3,63}$')

class Blocked(ValueError):
    pass

def need(ok, code):
    if not ok:
        raise Blocked(code)

def sha(data):
    return sha256(data).hexdigest()

def regular(p):
    return p.is_file() and not p.is_symlink()

def yaml_data(p):
    need(regular(p), 'INPUT_FILE_MISSING')
    data = yaml.safe_load(p.read_text(encoding='utf8'))
    need(isinstance(data, dict), 'INPUT_MAPPING_REQUIRED')
    return data

def exact_sha_file(p, wanted, code):
    need(regular(p) and len(wanted) == 64 and sha(p.read_bytes()) == wanted, code)

def resolve_private(value, source_root):
    need(isinstance(value, str) and value, 'PRIVATE_PATH_MISSING')
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = source_root / p
    need(regular(p), 'PRIVATE_FILE_MISSING')
    return p

def png_rgba_from_xref(doc, page, item):
    """Native source image + original PDF soft mask, not page flattening."""
    from PIL import Image, ImageChops
    xref = item['xref']
    need(isinstance(xref, int) and xref > 0, 'IMAGE_XREF_REQUIRED')
    info = doc.extract_image(xref)
    with Image.open(io.BytesIO(info['image'])) as im:
        rgba = im.convert('RGBA')
    smask = next((int(v[1] or 0) for v in page.get_images(full=True)
                  if int(v[0]) == xref), 0)
    if smask:
        with Image.open(io.BytesIO(doc.extract_image(smask)['image'])) as im:
            mask = im.convert('L')
        need(mask.size == rgba.size, 'SOFT_MASK_DIMENSIONS')
        rgba.putalpha(ImageChops.multiply(rgba.getchannel('A'), mask))
    b = io.BytesIO()
    rgba.save(b, 'PNG')
    return b.getvalue(), rgba.size

def image_match(page, digest, expected=1):
    items = [v for v in page.get_image_info(hashes=True, xrefs=True)
             if isinstance(v.get('digest'), bytes) and v['digest'].hex().startswith(digest)]
    need(len(items) == expected, 'REFERENCE_IMAGE_COUNT_' + digest[:10])
    return items[0] if items else None

def bbox_mm(item):
    return [round(float(v) * MM, 4) for v in item['bbox']]


def image_match_front_logo(page):
    """P01-only source-bound logo identification; no replacement or guessing.

    The historical GC21 value was a malformed *31-nibble* pseudo-MD5.
    What the real source-map actually proves is the 12-hex prefix 78b87a619527.
    That prefix is accepted ONLY for the SHA256-pinned canonical PDF and only
    with unique 949x946 px image at the audited coordinates on physical P01.
    Synthetic tests may use a real 32-hex MD5 to verify strict generic behavior.
    make_scene() verifies exact PDF SHA256 before this function is called.
    """
    digest = HASHES['logo']
    need(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{12}|[0-9a-f]{32}', digest),
         'P01_LOGO_CONFIG_DIGEST_INVALID')
    prefix_only = len(digest) == 12
    if prefix_only:
        need(digest == '78b87a619527' and REFERENCE_SHA == CANONICAL_REFERENCE_SHA,
             'P01_LOGO_PREFIX_ONLY_REQUIRES_CANONICAL_REFERENCE')
    items = [v for v in page.get_image_info(hashes=True, xrefs=True)
             if isinstance(v.get('digest'), bytes) and v['digest'].hex().startswith(digest)]
    need(len(items) == 1, 'P01_LOGO_SOURCE_NOT_UNIQUE')
    chosen = items[0]
    if prefix_only:
        bb = bbox_mm(chosen)
        need(len(bb) == 4 and all(abs(a-b) <= .1 for a,b in zip(bb,P01_LOGO_BBOX_MM)),
             'P01_LOGO_CANONICAL_GEOMETRY_MISMATCH')
        need((chosen.get('width'), chosen.get('height')) == P01_LOGO_PIXEL_SIZE,
             'P01_LOGO_CANONICAL_PIXEL_SIZE_MISMATCH')
        need(isinstance(chosen.get('xref'), int) and chosen['xref'] > 0,
             'P01_LOGO_XREF_REQUIRED')
    return chosen, ('PINNED_PDF_PREFIX12_GEOMETRY_PIXELS' if prefix_only else 'EXACT_MD5')


def p01_front_lines(text):
    expected = 'Привітання з нагоди Дня Народження!'
    need(text == expected, 'P01_OCCASION_VARIANT_NEEDS_SOURCE_LAYOUT_REVIEW')
    return ['Привітання з нагоди', 'Дня Народження!']

def sender_spans_from_pdf(pdf):
    import pymupdf
    exact_sha_file(pdf, SENDER_SHA, 'SENDER_SOURCE_SHA_CHANGED')
    rows=[]
    with pymupdf.open(pdf) as d:
        need(len(d)==4, 'SENDER_SOURCE_PAGES')
        for block in d[3].get_text('dict', sort=True).get('blocks', []):
            if block.get('type') != 0 or block['bbox'][1] * MM < 198:
                continue
            for line in block.get('lines', []):
                spans=[s for s in line.get('spans',[]) if str(s.get('text','')).strip()]
                if not spans: continue
                text=''.join(str(s['text']) for s in spans).strip()
                rows.append({'text':text,'bbox_mm':[round(float(v)*MM,3) for v in line['bbox']], 'spans':spans})
    return rows

def sender_expected(rows):
    # Source-verified legacy registry; text is not inferred from customer input.
    return [
       'З найщирішими побажаннями',
       'Людмила Герасименко',
       'Віцепрезидент, Генеральний',
       'директор ВГО АППУ',
    ]

# These are the frozen GRIGO vectors of the exact reference PDF, NOT the
# HERASYMENKO signature. The source itself is SHA256-pinned before inspection.
# Prepress Hub's canonical embedded-component inspector established 7 real
# GRIGO ink drawings and 113 noncontributing legacy PDF drawing artifacts.
REFERENCE_P04_DRAWING_COUNT = 120
GRIGO_DRAWING_COUNT = 7
GRIGO_VECTOR_BBOX_MM = (103.465, 213.348, 155.203, 247.531)


def audit_reference_p04_vectors(page):
    """Classify the known 120 reference paths; never import them as this sender.

    Adapted from the canonical Prepress Hub
    greeting_card_embedded_components._select_grigo_signature_drawings.
    Geometry and totals remain fail-closed; no generic 'ignore all paths' rule.
    The caller verifies the *exact* immutable reference PDF SHA256 first.
    """
    import pymupdf
    drawings = page.get_drawings()
    need(len(drawings) == REFERENCE_P04_DRAWING_COUNT,
         'P04_REFERENCE_VECTOR_INVENTORY_CHANGED')
    page_w, page_h = float(page.rect.width), float(page.rect.height)
    chosen = []
    for item in drawings:
        rect = pymupdf.Rect(item['rect'])
        if rect.width <= 0 or rect.height <= 0:
            continue
        if not ('f' in str(item.get('type') or '').lower() or item.get('fill') is not None):
            continue
        center_x = (float(rect.x0) + float(rect.x1)) / 2
        center_y = (float(rect.y0) + float(rect.y1)) / 2
        if (center_y <= page_h * .66 or center_x <= page_w * .45
                or rect.width >= page_w * .45 or rect.height >= page_h * .35):
            continue
        chosen.append(item)
    need(len(chosen) == GRIGO_DRAWING_COUNT,
         'P04_CANONICAL_GRIGO_VECTOR_COUNT_MISMATCH')
    union = pymupdf.Rect(chosen[0]['rect'])
    for item in chosen[1:]:
        union.include_rect(pymupdf.Rect(item['rect']))
    bbox = [round(float(v) * MM, 3) for v in union]
    need(all(abs(a - b) <= .03 for a, b in zip(bbox, GRIGO_VECTOR_BBOX_MM)),
         'P04_CANONICAL_GRIGO_VECTOR_BBOX_MISMATCH')
    return {
        'reference_drawing_count': REFERENCE_P04_DRAWING_COUNT,
        'source_verified_grigo_vector_count': len(chosen),
        'legacy_non_signature_drawing_count': len(drawings) - len(chosen),
        'selected_sender': 'HERASYMENKO',
        'reference_grigo_vectors_imported': False,
        'reference_other_vectors_imported': False,
    }


def greeting_style_from_pdf(pdf):
    import pymupdf
    exact_sha_file(pdf, SENDER_SHA, 'SENDER_SOURCE_SHA_CHANGED')
    colors=set()
    with pymupdf.open(pdf) as d:
        page=d[3]
        for block in page.get_text('dict').get('blocks', []):
            if block.get('type')!=0: continue
            for line in block.get('lines', []):
                for sp in line.get('spans', []):
                    b=[float(v)*MM for v in sp.get('bbox', [0,0,0,0])]
                    if b[1]>=32 and b[3]<=212 and 10<=float(sp.get('size',0))<=35 and str(sp.get('text','')).strip():
                        colors.add(int(sp['color']))
    need(len(colors)==1,'P04_GREETING_SOURCE_COLOR_NOT_UNIQUE')
    return next(iter(colors))

def selected_signature_image(pdf):
    import pymupdf
    exact_sha_file(pdf, SENDER_SHA, 'SENDER_SOURCE_SHA_CHANGED')
    target=(82.877, 214.875, 128.258, 274.141)
    with pymupdf.open(pdf) as d:
        page=d[3]
        items=page.get_image_info(hashes=True,xrefs=True)
        # Source signature image must overlap its canonical signature zone.
        candidates=[]
        for item in items:
            b=bbox_mm(item)
            md5=item.get('digest',b'').hex() if isinstance(item.get('digest'),bytes) else ''
            if (not any(md5.startswith(h) for h in (HASHES['paper'], HASHES['frame'],
                                                     '216f5696fab35f44f4b18c8efe82cefa')) and
                b[0]<target[2] and b[2]>target[0] and b[1]<target[3] and b[3]>target[1] and
                float(item.get('width',0))>50 and float(item.get('height',0))>50):
                candidates.append(item)
        need(len(candidates)==1, 'HERASYMENKO_SIGNATURE_IMAGE_NOT_UNIQUE')
        item=candidates[0]
        data,_=png_rgba_from_xref(d,page,item)
        return data, bbox_mm(item)

def verify_selected_job(bundle, artifact_manifest):
    need(isinstance(bundle.get('jobs'),list) and len(bundle['jobs'])==1,'PILOT_ONE_JOB_ONLY')
    job=bundle['jobs'][0]
    b=job.get('builder_v1') or {}
    need(isinstance(b,dict) and b.get('schema_version')=='gdl_greeting_card_builder_payload_v0_1', 'BUILDER_SCHEMA')
    need((b.get('front') or {}).get('family')=='STANDARD','FRONT_NOT_STANDARD')
    need((b.get('inside_image') or {}).get('mode')=='PORTRAIT','IMAGE_NOT_PORTRAIT')
    need((job.get('signature_selection') or {}).get('variant_id')=='HERASYMENKO'
         and (b.get('sender_text') or {}).get('signature_variant_id')=='HERASYMENKO', 'SENDER_NOT_HERASYMENKO')
    image=b['inside_image']
    asset_ref=image.get('accepted_artifact_ref')
    artifact=(artifact_manifest.get('artifacts') or {}).get(asset_ref)
    need(isinstance(artifact,dict) and asset_ref and artifact.get('source_asset_id')==image.get('asset_id')
         and artifact.get('sha256')==image.get('asset_sha256'), 'PORTRAIT_ARTIFACT_BINDING')
    greeting=(job.get('structured_greeting_data') or {}).get('greeting_text')
    need(isinstance(greeting,str) and greeting.strip() and len(greeting)<=8000, 'GREETING_MISSING')
    title=((b.get('front') or {}).get('occasion') or {}).get('display_text')
    need(isinstance(title,str) and title, 'OCCASION_MISSING')
    return job,b,artifact,greeting,title

def make_scene(config, source_root, gc19_dir, gc20_dir):
    import pymupdf
    from PIL import Image, ImageChops
    need(regular(config), 'PRIVATE_INPUT_CONFIG_MISSING')
    paths=json.loads(config.read_text('utf8'))
    need(isinstance(paths,dict) and set(paths)==set(PILOT_HASHES), 'PRIVATE_CONFIG_KEYS')
    inp={key:resolve_private(val,source_root) for key,val in paths.items()}
    for key,p in inp.items():
        exact_sha_file(p,PILOT_HASHES[key], 'PILOT_SOURCE_CHANGED_'+key)
    bundle=yaml_data(inp['bundle']); resources=yaml_data(inp['resource_manifest']); art=yaml_data(inp['artifact_manifest'])
    need(resources.get('schema_version')=='gdl_greeting_card_private_resource_manifest_v0_1','RESOURCE_SCHEMA')
    need(art.get('schema_version')=='gdl_greeting_card_builder_artifact_manifest_v0_1','ARTIFACT_SCHEMA')
    job,b,artifact,greeting,title=verify_selected_job(bundle,art)
    res=resources.get('resources') or {}
    ref_binding=res.get(RESOURCE_ID) or {}; sender_binding=res.get(SENDER_SOURCE_ID) or {}
    ref=resolve_private(ref_binding.get('path'),source_root)
    sender=resolve_private(sender_binding.get('path'),source_root)
    exact_sha_file(ref,REFERENCE_SHA,'REFERENCE_SHA_CHANGED')
    exact_sha_file(sender,SENDER_SHA,'HERASYMENKO_SOURCE_SHA_CHANGED')
    portrait=resolve_private(artifact.get('path'),source_root)
    exact_sha_file(portrait,b['inside_image']['asset_sha256'],'ACCEPTED_PORTRAIT_SHA_CHANGED')
    for key in ('font.front_occasion.monotype_corsiva.v1','font.greeting_sender.zapf_chancery_c.v1'):
        p=resolve_private((res.get(key) or {}).get('path'),source_root)
        pinned=(res.get(key) or {}).get('sha256')
        if pinned is not None: exact_sha_file(p,pinned,'FONT_SHA_CHANGED')
    gc19_scene=gc19_dir/'manifest.json'; gc20_scene=gc20_dir/'scene_p02.json'
    need(regular(gc19_scene) and regular(gc20_scene),'GC19_GC20_MANIFEST_MISSING')
    g19=json.loads(gc19_scene.read_text('utf8'));g20=json.loads(gc20_scene.read_text('utf8'))
    need(g19.get('source_pdf_sha256')==REFERENCE_SHA and g20.get('source_reference_pdf_sha256')==REFERENCE_SHA, 'REFERENCE_CHAIN_BROKEN')
    need(g19.get('state')=='NATIVE_ASSETS_CANDIDATE_VISUAL_REVIEW_REQUIRED' and
         g20.get('state')=='P02_NATIVE_LAYER_ASSETS_VISUAL_REVIEW_REQUIRED', 'SOURCE_STATE_MISMATCH')
    need(g19.get('source_alpha_factor')==.25 and g20.get('watermark_source_alpha_multiplier')==.25,'WATERMARK_ATTENUATION')
    need(g20.get('artboard_mm')==list(SIZE) and g20.get('physical_page')==2, 'P02_SCENE_INVALID')
    blobs={}
    layers=[]
    def add_image(page,role,filename,blob,bbox,locked=False):
        need(filename not in blobs,'DUPLICATE_ASSET_FILENAME')
        need(len(bbox)==4 and bbox[2]>bbox[0] and bbox[3]>bbox[1], 'ASSET_BBOX_INVALID')
        blobs[filename]=blob
        layers.append({'page':page,'kind':'raster','role':role,'file':'assets/'+filename,'bbox_mm':[round(float(n),4) for n in bbox], 'locked':locked})
    # Source-verified individually imported reference components; no full-page PDF import.
    with pymupdf.open(ref) as doc:
        need(doc.page_count==4, 'REFERENCE_FOUR_PAGES')
        # The exact reference has seven GRIGO signature vectors plus 113 old,
        # noncontributing drawing artifacts. Neither belongs in HERASYMENKO.
        # Source SHA, total count, signed-ink selector and canonical bbox all bind.
        p04_vector_audit = audit_reference_p04_vectors(doc[3])
        for page in doc:
            need(all(abs(float(a)*MM-v)<0.03 for a,v in zip((page.rect.width,page.rect.height),SIZE)), 'REFERENCE_PAGE_DIMENSIONS')
        for i,page in enumerate(doc):
            for role,digest in [('paper','paper')]:
                item=image_match(page,HASHES[digest])
                dat,_=png_rgba_from_xref(doc,page,item)
                if i!=1: add_image(i+1,f'P{i+1:02d}.PAPER',f'p{i+1:02d}_paper.png',dat,bbox_mm(item),True)
            if i in (0,2,3):
                item=image_match(page,HASHES['frame'])
                dat,_=png_rgba_from_xref(doc,page,item)
                add_image(i+1,f'P{i+1:02d}.FRAME',f'p{i+1:02d}_frame.png',dat,bbox_mm(item),False)
        logo, logo_match_mode=image_match_front_logo(doc[0])
        dat,_=png_rgba_from_xref(doc,doc[0],logo)
        add_image(1,'P01.SENDER_LOGO','p01_sender_logo.png',dat,bbox_mm(logo))
        reference_portrait=[x for x in doc[2].get_image_info(hashes=True,xrefs=True)
                            if isinstance(x.get('digest'),bytes) and x['digest'].hex().startswith(HASHES['portrait_reference'])]
        need(len(reference_portrait)==1,'P03_REFERENCE_PORTRAIT')
        sample=reference_portrait[0]
        source_mask=next((int(v[1] or 0) for v in doc[2].get_images(full=True)
                          if int(v[0])==int(sample['xref'])),0)
        need(source_mask>0,'P03_REFERENCE_SOFT_MASK_MISSING')
        with Image.open(io.BytesIO(doc.extract_image(source_mask)['image'])) as mask_obj:
            mask=mask_obj.convert('L')
        with Image.open(portrait) as original:
            image=original.convert('RGBA')
        w,h=int(sample['width']),int(sample['height'])
        ratio=w/h
        if image.width/image.height > ratio:
            crop_w=round(image.height*ratio); left=(image.width-crop_w)//2
            image=image.crop((left,0,left+crop_w,image.height))
        else:
            crop_h=round(image.width/ratio); top=(image.height-crop_h)//2
            image=image.crop((0,top,image.width,top+crop_h))
        image=image.resize((w,h),Image.Resampling.LANCZOS)
        need(mask.size==image.size,'P03_MASK_DIMENSIONS')
        image.putalpha(ImageChops.multiply(image.getchannel('A'),mask))
        bio=io.BytesIO(); image.save(bio,'PNG')
        add_image(3,'P03.ACCEPTED_PORTRAIT','p03_accepted_portrait.png',bio.getvalue(),bbox_mm(sample))
    # New watermark overlay exactly once, source P02 watermark is absent from GC20 locked base.
    for name in ('p02_locked_background.png','p02_watermark_layer.png'):
        p=gc20_dir/name
        need(regular(p) and sha(p.read_bytes())==(g20.get('artifacts_sha256') or {}).get(name),'GC20_ASSET_SHA_'+name)
    add_image(2,'P02.LOCKED_BASE','p02_locked_background.png',(gc20_dir/'p02_locked_background.png').read_bytes(),[0,0,*SIZE],True)
    add_image(2,'P02.WATERMARK','p02_watermark.png',(gc20_dir/'p02_watermark_layer.png').read_bytes(),g20['watermark_bbox_pdf_mm'])
    wm4=next((x for x in g19['watermarks'] if x.get('physical_page')==4),None)
    need(wm4 is not None and wm4.get('object_id')=='P04_GREETING.WATERMARK','GC19_P04_MISSING')
    p=gc19_dir/'p04_greeting_watermark.png'
    need(regular(p) and sha(p.read_bytes())==wm4['sha256'],'GC19_P04_ASSET_SHA')
    add_image(4,'P04.WATERMARK','p04_watermark.png',p.read_bytes(),wm4['bbox_pdf_mm'])
    signature_bytes,signature_bbox=selected_signature_image(sender)
    greeting_rgb=greeting_style_from_pdf(sender)
    add_image(4,'P04.HERASYMENKO_SIGNATURE','p04_signature_herasymenko.png',signature_bytes,signature_bbox)
    rows=sender_spans_from_pdf(sender)
    need([x['text'] for x in rows] == sender_expected(rows), 'CANONICAL_SENDER_TEXT_MISMATCH')
    # Sender baseline and formatting come from the exact source-verified signature PDF.
    senders=[]
    for idx,row in enumerate(rows):
        need(len(row['spans'])==1,'SENDER_MULTISPAN_REVIEW_REQUIRED')
        span=row['spans'][0]; origin=span.get('origin',[])
        need(len(origin)==2 and 9<float(span['size'])<30,'SENDER_FONT_METRICS')
        senders.append({'id':'P04.SENDER_LINE_%02d'%(idx+1),'text':row['text'],
          'x_mm':round(float(origin[0])*MM,4),'baseline_from_top_mm':round(float(origin[1])*MM,4),
          'size_pt':round(float(span['size']),4),'rgb':int(span['color'])})
    need((b['sender_text'] or {}).get('signature_variant_id')=='HERASYMENKO','SENDER_VARIANT_CHANGED')
    front_lines=p01_front_lines(title)
    scene={
      'schema_version':SCENE_SCHEMA,'state':'PRIVATE_NATIVE_JSX_CANDIDATE_NOT_EXECUTED',
      'source_hashes':PILOT_HASHES,'reference_pdf_sha256':REFERENCE_SHA,
      'job_count':1,'front_family':'STANDARD','inside_image_mode':'PORTRAIT','sender_variant':'HERASYMENKO',
      'size_mm':list(SIZE),'bleed_mm':2,'pages':4,
      'watermark_alpha_factor':0.25,
      'p01_logo_match_mode':logo_match_mode,
      'p04_reference_vector_audit':p04_vector_audit,
      'privacy':'CLIENT_TEXT_IN_PRIVATE_TMP_ONLY',
      'layers':layers,'front_lines':front_lines,
      'greeting_text':greeting,'greeting_rgb':greeting_rgb,'sender_lines':senders,
      'production_ready':False,'illustrator_executed':False,'visual_approval':'NOT_RECORDED',
      'required_manual_checks':['P01 typography','P03 portrait mask/crop','P04 signature and live text',
                                'P02/P04 opacity','export/round-trip','CMYK/production preflight']
    }
    return scene,blobs

def render_jsx(scene):
    need(regular(TEMPLATE), 'JSX_TEMPLATE_MISSING')
    raw=TEMPLATE.read_text(encoding='utf8')
    need(raw.count('/*__GC21_SCENE_JSON__*/')==1 and raw.count('GC21_NATIVE_FOUR_ARTBOARD_V0_1')==1,'JSX_TEMPLATE_INVALID')
    literal=json.dumps(scene,ensure_ascii=True,sort_keys=True,separators=(',',':'))
    # JSON safely embeds customer text and doesn't require a private sidecar reader.
    return raw.replace('/*__GC21_SCENE_JSON__*/',literal)

def prepare(name,scene,blobs,jsx):
    need(VALID_NAME.fullmatch(name) is not None,'OUTPUT_NAME_INVALID')
    base=ROOT/'tmp'
    need(not base.is_symlink(),'TMP_SYMLINK')
    dest=base/name
    need(not dest.exists() and not dest.is_symlink(),'OUTPUT_ALREADY_EXISTS')
    base.mkdir(mode=0o700,exist_ok=True)
    dest.mkdir(mode=0o700)
    (dest/'assets').mkdir(mode=0o700)
    for n,data in blobs.items():
        with (dest/'assets'/n).open('xb') as f:f.write(data)
    with (dest/'run_gc21_in_illustrator.jsx').open('x',encoding='utf8') as f: f.write(jsx)
    public_scene=dict(scene)
    public_scene.pop('greeting_text')
    public_scene.pop('greeting_rgb')
    public_scene.pop('sender_lines')
    public_scene.pop('front_lines')
    public_scene['asset_sha256']={name:sha(blob) for name,blob in sorted(blobs.items())}
    public_scene['jsx_sha256']=sha(jsx.encode('utf8'))
    with (dest/'scene_manifest.json').open('x',encoding='utf8') as f:
        json.dump(public_scene,f,ensure_ascii=False,indent=2,sort_keys=True)
    with (dest/'README_PRIVATE.txt').open('x',encoding='utf8') as f:
        f.write('PRIVATE GC21 Illustrator candidate. This folder contains customer content.\n'
                'Copy the ENTIRE folder with assets to the Windows workstation.\n'
                'Use File > Scripts > Other Script in interactive Illustrator.\n'
                'Never run the blocked F1 scheduler, never publish generated JSX or assets to Git.\n'
                'Review design.ai, review.pdf, preview_p01..p04.png and result.json locally.\n')
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','prepare'),required=True)
    p.add_argument('--inputs-config',required=True,type=Path)
    p.add_argument('--source-root',required=True,type=Path)
    p.add_argument('--gc19-assets-dir',required=True,type=Path)
    p.add_argument('--gc20-scene-dir',required=True,type=Path)
    p.add_argument('--output-name')
    p.add_argument('--confirm-private-prepare',action='store_true')
    a=p.parse_args()
    try:
        need((a.mode=='prepare')==a.confirm_private_prepare,'PREPARE_CONFIRMATION_REQUIRED')
        need((a.mode=='prepare')==(a.output_name is not None),'OUTPUT_MODE_MISMATCH')
        for d in (a.gc19_assets_dir,a.gc20_scene_dir):
            need(d.is_dir() and not d.is_symlink() and d.resolve().is_relative_to((ROOT/'tmp').resolve()),'LAB_TMP_ASSETS_ONLY')
        scene,blobs=make_scene(a.inputs_config,a.source_root,a.gc19_assets_dir,a.gc20_scene_dir)
        jsx=render_jsx(scene)
        need(len(scene['layers'])>=10 and len(blobs)>=10,'FOUR_PAGE_COMPONENTS_MISSING')
        if a.mode=='prepare':
            dest=prepare(a.output_name,scene,blobs,jsx)
            print('ARTIFACT_FOLDER='+str(dest.relative_to(ROOT)))
            print('GDL_GC21_NATIVE=PREPARED_PRIVATE_ILLUSTRATOR_EXECUTION_PENDING')
        else:
            print('GDL_GC21_NATIVE=SOURCE_CHECK_PASS_WINDOWS_NOT_EXECUTED')
        print('FOUR_PAGES=4 LAYER_COUNT='+str(len(scene['layers'])))
        print('CUSTOMER_TEXT_PRINTED=false PRODUCTION_READY=false')
        return 0
    except (Blocked,OSError,ValueError,KeyError,TypeError,ImportError) as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GDL_GC21_NATIVE=BLOCKED reason='+code,file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
