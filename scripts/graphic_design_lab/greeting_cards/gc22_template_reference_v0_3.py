#!/usr/bin/env python3
"""ForPrint GC22: source-bound, PII-free structural template review (not artwork).

Modes:
  inspect: read-only source checks and proposed layout
  prepare: write new-only 4-page schematic PDF + PNGs under GDL tmp
  verify: read-only validation of an already prepared reference
  publish: verify the staged copy and publish new-only into one SMB client workspace

This script NEVER copies a client's private reference PDF or prints greetings.
It must NOT be mistaken for a final artwork template or customer approval.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MM_TO_PT = 72.0 / 25.4
REFERENCE_SHA = '66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85'
SKELETON = 'greeting_card_a3_single_fold_v0_1'
SHARE_ROOT = Path('/srv/smb/In_Progress/data')
FILES = {
    'product_skeleton': 'coordination/graphic_design_lab/directions/greeting_cards/product_skeleton_v0_1.yaml',
    'geometry_zones': 'coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml',
    'page4_repair': 'coordination/graphic_design_lab/directions/greeting_cards/page4_canonical_repair_profile_v0_1.yaml',
    'product_reconciliation': 'coordination/graphic_design_lab/directions/greeting_cards/goal_driven_v0_1/02_PRODUCT/greeting_card_skeleton_v0_1.yaml',
    'sender_registry': 'coordination/graphic_design_lab/directions/greeting_cards/canonical_sender_blocks_v0_1.yaml',
    'workspace_contract': 'coordination/graphic_design_lab/client_workflows/client_workspace_architecture_v0_1.yaml',
}

class Blocked(Exception):
    pass

def require(ok, msg):
    if not ok:
        raise Blocked(msg)

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):
            digest.update(part)
    return digest.hexdigest()

def inside(parent, child):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False

def p04_candidate_greeting_bbox(candidate):
    """Resolve both historical representation shapes; require one explicit bbox.

    Early synthetic fixture: geometry: {target_bbox_pdf_mm: [...]}
    Real reconciled skeleton: geometry: descriptive string; target_bbox_pdf_mm: [...]
    This must never change the 150 x 180 mm authority or silently select a
    conflicting representation.
    """
    require(isinstance(candidate, dict), 'P04_RECONCILIATION_SCHEMA_INVALID')
    elements = candidate.get('elements')
    require(isinstance(elements, list), 'P04_RECONCILIATION_ELEMENTS_INVALID')
    matches = [entry for entry in elements
               if isinstance(entry, dict) and entry.get('id') == 'P04.GREETING_BODY']
    require(len(matches) == 1, 'P04_GREETING_BODY_NOT_UNIQUE')
    entry = matches[0]
    geometry = entry.get('geometry')
    nested = geometry.get('target_bbox_pdf_mm') if isinstance(geometry, dict) else None
    direct = entry.get('target_bbox_pdf_mm')
    if direct is not None and nested is not None:
        require(direct == nested, 'P04_CANDIDATE_DUPLICATE_BBOX_CONFLICT')
    value = direct if direct is not None else nested
    require(isinstance(value, list) and len(value) == 4
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in value), 'P04_CANDIDATE_BBOX_INVALID')
    require(value[2] > value[0] and value[3] > value[1],
            'P04_CANDIDATE_BBOX_INVALID')
    return value

def load_inputs(prepress, gc19):
    import yaml
    require(prepress.is_dir(), 'PREPRESS_SOURCE_ROOT_MISSING')
    rows = {}
    digests = {}
    for key, rel in FILES.items():
        p = prepress / rel
        require(p.is_file() and not p.is_symlink(), 'SOURCE_' + key.upper() + '_MISSING_OR_SYMLINK')
        rows[key] = yaml.safe_load(p.read_text(encoding='utf-8'))
        digests[key] = sha(p)
    product, zones, repair = rows['product_skeleton'], rows['geometry_zones'], rows['page4_repair']
    candidate = rows['product_reconciliation']
    require(product.get('skeleton_id') == SKELETON, 'SKELETON_ID_MISMATCH')
    require(product['geometry_model']['physical_page_count'] == 4, 'PAGE_COUNT_MISMATCH')
    require(product['geometry_model']['media_size'] == [214.0,301.0], 'MEDIA_SIZE_MISMATCH')
    require(zones['page_coordinate_system']['physical_pdf_mm'] == [214.0,301.0], 'ZONE_MEDIA_MISMATCH')
    require(zones['page_coordinate_system']['trim_mm'] == [210.0,297.0], 'TRIM_SIZE_MISMATCH')
    z1 = zones['pages']['physical_1']['existing_slots']
    z4 = zones['pages']['physical_4']['zones']
    greeting = z4['inside_text.greeting']['bbox_pdf_mm']
    candidate_bbox = p04_candidate_greeting_bbox(candidate)
    require(greeting == repair['greeting_bbox_pdf_mm'] == candidate_bbox, 'P04_LIVE_GEOMETRY_CONFLICT_REVIEW_REQUIRED')
    require(greeting == [32.0,32.0,182.0,212.0], 'P04_EXPECTED_150X180_NOT_CONFIRMED')
    require(z4['inside_text.greeting']['max_width_mm']==150.0, 'P04_MAX_WIDTH_MISMATCH')
    require(z1['front.sender_logo']['bbox_pdf_mm']==[64.5,59.5,149.5,144.5], 'P01_LOGO_BBOX_MISMATCH')
    require(rows['workspace_contract']['workspace_dir_name']=='_forprint_automation', 'CLIENT_WORKSPACE_CONTRACT_MISMATCH')
    require('templates' in rows['workspace_contract']['tree'], 'CLIENT_TEMPLATES_CONTRACT_MISSING')
    require(gc19.is_file() and not gc19.is_symlink(), 'GC19_MANIFEST_MISSING')
    wm = json.loads(gc19.read_text('utf-8'))
    require(wm.get('source_pdf_sha256')==REFERENCE_SHA, 'GC19_REFERENCE_SHA_MISMATCH')
    wm_rows = {v['object_id']:v['bbox_pdf_mm'] for v in wm['watermarks']}
    require(set(wm_rows)=={'P02_BACK.WATERMARK','P04_GREETING.WATERMARK'}, 'GC19_PAGE_BINDING_MISMATCH')
    sender_rows=rows['sender_registry']['variants']['HERASYMENKO']['bboxes_pdf_mm']
    require(len(sender_rows)==4 and all(len(x)==4 for x in sender_rows),'HERASYMENKO_SENDER_ROWS_NOT_CONFIRMED')
    digests['gc19_manifest'] = sha(gc19)
    return {
        'source_sha256': digests,
        'boxes': {
            'p01_sender_logo':z1['front.sender_logo']['bbox_pdf_mm'],
            'p01_occasion':z1['front.occasion_text']['bbox_pdf_mm'],
            'p02_watermark':wm_rows['P02_BACK.WATERMARK'],
            'p04_greeting':greeting,
            'p04_watermark':wm_rows['P04_GREETING.WATERMARK'],
            'p04_signature_herasymenko':z4['inside_text.signature']['herasymenko_bbox_pdf_mm'],
            'p04_sender_rows_herasymenko':sender_rows,
        },
        'notes': ['P03 portrait and clip require actual Builder/mask geometry; no invented rectangle.',
                  '150x180 is live GC16/GC17 candidate; human visual approval is not implied.',
                  'Watermark preview rectangles indicate position, not ink opacity.',
                  'This is a PII-free schematic guide, NOT the canonical art PDF.'],
    }

def render(data, destination):
    import pymupdf
    w, h = 214*MM_TO_PT, 301*MM_TO_PT
    doc=pymupdf.open()
    titles=[('P01 FRONT','STANDARD / cover'),('P02 BACK','locked artwork / watermark'),
            ('P03 PHOTO','accepted portrait / mask / frame'),('P04 GREETING','text / sender / signature')]
    b=data['boxes']
    content=[ [('SENDER LOGO',b['p01_sender_logo']),( 'OCCASION',b['p01_occasion'])],
              [('WATERMARK',b['p02_watermark'])],
              [],
              [('WATERMARK',b['p04_watermark']),('GREETING 150 x 180',b['p04_greeting']),
               ('HERASYMENKO SIGNATURE',b['p04_signature_herasymenko'])]
               + [(f'SENDER ROW {n}', box) for n,box in enumerate(b['p04_sender_rows_herasymenko'],1)] ]
    def rect_mm(box): return pymupdf.Rect(*(float(x)*MM_TO_PT for x in box))
    for i,(title,sub) in enumerate(titles):
        p=doc.new_page(width=w,height=h)
        p.draw_rect(pymupdf.Rect(0,0,w,h), color=(0.65,0.67,0.70), fill=(0.97,0.97,0.97))
        p.draw_rect(rect_mm([2,2,212,299]),color=(0.11,0.25,0.45),width=1.5)
        p.insert_text((18,25),title,fontname='helv',fontsize=17,color=(0.1,0.2,0.3))
        p.insert_text((18,40),sub,fontname='helv',fontsize=9,color=(0.2,0.3,0.4))
        for j,(label,coords) in enumerate(content[i]):
            box=rect_mm(coords)
            iswm = label=='WATERMARK'
            c=(0.48,0.45,0.65) if iswm else ((0.12,0.45,0.35) if 'GREETING' in label else (0.77,0.34,0.22))
            p.draw_rect(box,color=c,width=1.8 if not iswm else 1,dashes='[3 3] 0' if iswm else None)
            # Place short labels at top inside boxes when space allows, otherwise on top edge.
            p.insert_text((max(4,box.x0+4), min(h-5,box.y0+11)),label,fontname='helv',fontsize=7,color=c)
        if i==2:
            for ix,line in enumerate(['CASE-SPECIFIC PORTRAIT FROM ACCEPTED ARTIFACT',
                                      'CROP / MASK / FRAME = SOURCE BUILDER GEOMETRY',
                                      'NO INFERRED PORTRAIT RECTANGLE']):
                p.insert_text((35*MM_TO_PT,(135+ix*9)*MM_TO_PT),line,fontname='helv',fontsize=8,
                              color=(0.35,0.36,0.38))
        p.insert_text((18,h-25),'2 mm bleed  /  210 x 297 mm trim  /  top-left PDF coordinates',fontsize=8,color=(0.2,0.3,0.4))
        p.insert_text((18,h-13),'REFERENCE SCHEMATIC ONLY - NOT CLIENT ART OR PRINT PROOF',fontsize=7,color=(0.7,0.22,0.2))
    pdf=destination/'greeting_card_layout_guide.pdf'
    doc.save(str(pdf),garbage=4,deflate=True)
    imgs=[]
    for i,p in enumerate(doc,1):
        image=destination/f'preview_p{i:02}.png'
        p.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4),alpha=False).save(str(image))
        imgs.append(image)
    doc.close()
    return [pdf]+imgs

def stage(args,data):
    out=args.output_dir
    require(out is not None and out.is_absolute() and not out.exists(), 'STAGE_TARGET_MUST_BE_NEW_ABSOLUTE')
    require(out == out.resolve(strict=False), 'STAGE_PATH_MUST_BE_NORMALIZED')
    root=args.gdl_root.resolve(strict=True)
    require(inside(root/'tmp',out), 'STAGE_MUST_BE_INSIDE_GDL_TMP')
    require((root/'tmp').is_dir() and not (root/'tmp').is_symlink(), 'GDL_TMP_INVALID')
    for part in reversed([p for p in [out.parent, *out.parents] if p != root]):
        if part.exists(): require(part.is_dir() and not part.is_symlink(), 'STAGE_PARENT_UNSAFE')
    out.mkdir(parents=True,exist_ok=False)
    artifacts=render(data,out)
    result={ 'schema_version':'forprint_gdl_gc22_client_template_visual_reference_v0_1',
             'status':'SCHEMATIC_REVIEW_ONLY_NOT_APPROVED',
             'skeleton_id':SKELETON,'canonical_art_source':'EXTERNAL_PRIVATE_SERVER_REFERENCE_NOT_COPIED',
             'private_customer_content_included':False,'customer_approval':False,'production_ready':False,
             **data,'outputs_sha256':{p.name:sha(p) for p in artifacts}}
    (out/'reference_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return out

def verify_staged_reference(prepress: Path, gc19: Path, gdl_root: Path, output_dir: Path):
    """Fail closed on drift, altered artifacts, wrong PDF pages or missing previews.

    This is read-only and never modifies PDF, PNG, manifest, original client data
    or another repository. Intended to verify the existing review_r001 stage.
    """
    import pymupdf
    from PIL import Image
    require(gdl_root is not None and output_dir is not None,
            'VERIFY_REQUIRED_PATH_MISSING')
    root = gdl_root.resolve(strict=True)
    stage = output_dir.resolve(strict=True)
    require(stage.is_dir() and not output_dir.is_symlink(), 'VERIFY_STAGE_INVALID')
    require(inside(root/'tmp', stage), 'VERIFY_STAGE_OUTSIDE_GDL_TMP')
    require(not (root/'tmp').is_symlink(), 'VERIFY_GDL_TMP_SYMLINK')
    manifest_path = stage/'reference_manifest.json'
    require(manifest_path.is_file() and not manifest_path.is_symlink(),
            'VERIFY_MANIFEST_MISSING')
    manifest = json.loads(manifest_path.read_text('utf-8'))
    require(manifest.get('schema_version') ==
            'forprint_gdl_gc22_client_template_visual_reference_v0_1',
            'VERIFY_MANIFEST_SCHEMA_INVALID')
    require(manifest.get('status') == 'SCHEMATIC_REVIEW_ONLY_NOT_APPROVED' and
            manifest.get('private_customer_content_included') is False and
            manifest.get('production_ready') is False and
            manifest.get('customer_approval') is False,
            'VERIFY_MANIFEST_AUTHORITY_INVALID')
    live = load_inputs(prepress, gc19)
    require(manifest.get('source_sha256') == live['source_sha256'],
            'VERIFY_SOURCE_DRIFT')
    require(manifest.get('boxes') == live['boxes'], 'VERIFY_GEOMETRY_DRIFT')
    expected = {'greeting_card_layout_guide.pdf',
                'preview_p01.png', 'preview_p02.png',
                'preview_p03.png', 'preview_p04.png'}
    hashes = manifest.get('outputs_sha256')
    require(isinstance(hashes, dict) and set(hashes) == expected,
            'VERIFY_OUTPUT_MANIFEST_INVALID')
    require({p.name for p in stage.iterdir()} == expected | {'reference_manifest.json'},
            'VERIFY_UNEXPECTED_OR_MISSING_FILES')
    for name, digest in hashes.items():
        require(re.fullmatch('[0-9a-f]{64}', digest or '') is not None,
                'VERIFY_SHA_FORMAT_INVALID')
        path = stage/name
        require(path.is_file() and not path.is_symlink() and sha(path) == digest,
                'VERIFY_OUTPUT_SHA_MISMATCH')
    with pymupdf.open(str(stage/'greeting_card_layout_guide.pdf')) as doc:
        require(len(doc) == 4, 'VERIFY_PDF_PAGE_COUNT')
        for page in doc:
            require(abs(page.rect.width - 214 * MM_TO_PT) < .1 and
                    abs(page.rect.height - 301 * MM_TO_PT) < .1,
                    'VERIFY_PDF_PAGE_GEOMETRY')
    for i in range(1, 5):
        with Image.open(stage/f'preview_p{i:02}.png') as img:
            img.verify()
    return {'page_count': 4, 'png_count': 4,
            'p04_greeting_bbox_pdf_mm': live['boxes']['p04_greeting'],
            'source_file_count': len(live['source_sha256'])}

def workspace_checked(path):
    require(path is not None and path.is_absolute(), 'EXPLICIT_CLIENT_WORKSPACE_REQUIRED')
    root=SHARE_ROOT.resolve(strict=True)
    raw=path
    require(not raw.is_symlink(), 'CLIENT_WORKSPACE_SYMLINK_FORBIDDEN')
    candidate=raw.resolve(strict=True)
    require(inside(root,candidate), 'OUTSIDE_SMB_ROOT')
    require(candidate.parent.parent==root and candidate.name=='_forprint_automation','UNSUPPORTED_CLIENT_WORKSPACE_PATH')
    require(not candidate.parent.is_symlink() and candidate.is_dir(), 'CLIENT_WORKSPACE_UNSAFE')
    require((candidate/'input').is_dir() and (candidate/'output').is_dir(), 'CLIENT_LEGACY_IN_OUT_MISSING')
    return candidate

def a_not_none(obj): return obj is not None

def publish(args):
    # Exact, non-destructive replica of generated *schematic*, not the private source art.
    workspace=workspace_checked(args.client_workspace)
    require(a_not_none(args.gdl_root) and a_not_none(args.prepress_root) and a_not_none(args.gc19_manifest),
            'SOURCE_BINDING_REQUIRED_FOR_PUBLISH')
    current=load_inputs(args.prepress_root,args.gc19_manifest)
    origin=args.output_dir
    require(origin is not None and origin.is_dir() and not origin.is_symlink(), 'STAGED_TEMPLATE_MISSING')
    mpath=origin/'reference_manifest.json'
    require(mpath.is_file() and not mpath.is_symlink(), 'STAGED_MANIFEST_MISSING')
    m=json.loads(mpath.read_text('utf-8'))
    require(m.get('source_sha256')==current['source_sha256'],'STAGED_TEMPLATE_SOURCE_DRIFT')
    require(m.get('schema_version')=='forprint_gdl_gc22_client_template_visual_reference_v0_1' and
            m.get('private_customer_content_included') is False,'STAGED_MANIFEST_SCHEMA_INVALID')
    for name,digest in m['outputs_sha256'].items():
        require(bool(re.fullmatch(r'[a-zA-Z0-9_.-]+',name)), 'UNSAFE_OUTPUT_NAME')
        p=origin/name
        require(p.is_file() and not p.is_symlink() and sha(p)==digest,'STAGED_OUTPUT_INTEGRITY_FAILED')
    root=args.gdl_root.resolve(strict=True)
    require(inside(root/'tmp',origin.resolve(strict=True)),'PUBLISH_ORIGIN_NOT_GDL_TMP')
    target=workspace/'templates'/'normalized'/SKELETON/'review_r001'
    require(not target.exists() and not target.is_symlink(), 'CLIENT_TARGET_EXISTS_NO_OVERWRITE')
    for p in (workspace/'templates',workspace/'templates'/'normalized',target.parent):
        if p.exists(): require(p.is_dir() and not p.is_symlink(), 'CLIENT_FOLDER_UNSAFE')
    # Create-new only; all source bytes validated before mutation.
    target.mkdir(parents=True,exist_ok=False)
    for name in [*m['outputs_sha256'],'reference_manifest.json']:
        with (target/name).open('xb') as f:
            f.write((origin/name).read_bytes())
    for name,digest in m['outputs_sha256'].items():
        require(sha(target/name)==digest,'CLIENT_COPY_HASH_MISMATCH')
    return target

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=['inspect','prepare','verify','publish'])
    p.add_argument('--prepress-root',type=Path)
    p.add_argument('--gc19-manifest',type=Path)
    p.add_argument('--gdl-root',type=Path)
    p.add_argument('--output-dir',type=Path)
    p.add_argument('--client-workspace',type=Path)
    p.add_argument('--confirm-client-publish',action='store_true')
    a=p.parse_args()
    try:
        if a.mode in ('inspect','prepare'):
            require(a.prepress_root is not None and a.gc19_manifest is not None,'SOURCE_ARGUMENTS_REQUIRED')
            data=load_inputs(a.prepress_root,a.gc19_manifest)
            print('GDL_GC22_SOURCE_GEOMETRY=PASS')
            print('P04_GREETING_BBOX_PDF_MM='+json.dumps(data['boxes']['p04_greeting']))
            print('SOURCE_FILES_VERIFIED='+str(len(data['source_sha256'])))
            if a.mode=='prepare':
                require(a.gdl_root is not None,'GDL_ROOT_REQUIRED')
                stage(a,data)
                print('GDL_GC22_SCHEMATIC_PREPARE=PASS')
        elif a.mode == 'verify':
            require(a.prepress_root is not None and a.gc19_manifest is not None and
                    a.gdl_root is not None and a.output_dir is not None,
                    'VERIFY_ARGUMENTS_REQUIRED')
            report = verify_staged_reference(a.prepress_root, a.gc19_manifest,
                                             a.gdl_root, a.output_dir)
            print('GDL_GC22_STAGED_REFERENCE=PASS')
            print('PDF_PAGE_COUNT=' + str(report['page_count']))
            print('PNG_PAGE_COUNT=' + str(report['png_count']))
            print('P04_GREETING_BBOX_PDF_MM=' + json.dumps(report['p04_greeting_bbox_pdf_mm']))
            print('SOURCE_FILES_VERIFIED=' + str(report['source_file_count']))
        else:
            require(a.confirm_client_publish,'EXPLICIT_CLIENT_PUBLISH_CONFIRMATION_REQUIRED')
            target=publish(a)
            print('GDL_GC22_CLIENT_VISUAL_COPY=PASS')
            print('COPY_IS_SCHEMATIC_NOT_PRIVATE_REFERENCE_PDF=true')
        return 0
    except (Blocked, OSError, KeyError, TypeError, ValueError) as ex:
        msg=str(ex) if isinstance(ex,Blocked) else type(ex).__name__
        print('GDL_GC22_TEMPLATE_VISUAL=BLOCKED reason='+msg,file=sys.stderr)
        return 2
if __name__=='__main__':
    sys.exit(main())
