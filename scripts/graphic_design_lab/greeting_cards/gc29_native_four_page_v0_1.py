#!/usr/bin/env python3
"""GC29: source-PDF-free four-page Illustrator PRIVATE candidate, via frozen asset vault.

One-time `bootstrap` reads historic pinned reference/source PDFs to extract
individual assets. Later `prepare` reads only an accepted customer ZIP, the
frozen vault and project rules. It NEVER opens or locates a PDF in runtime.
No printing, publication, or automatic customer approval.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / 'gc29_native_four_page_v0_1.jsx'
GC23 = ROOT / 'coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json'
GC21 = HERE / 'gc21_native_illustrator_builder_v0_1.py'
SHARE = Path('/srv/smb/In_Progress/data')
REFERENCE_SHA = '66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85'
FLOWERS_SHA = 'd9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67'
HERASYMENKO_SHA = 'a5392be1234c026d1200cad288a3b4989f506f8eb32522dcbe6236bb221722a8'
SAFE = re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
SIZE = [214.0,301.0]
MM = 25.4/72.0

class Blocked(ValueError): pass

def need(v, code):
    if not v: raise Blocked(code)

def regular(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError: return False

def directory(p):
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError: return False

def digest(p):
    h=sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def write_json(p,v):
    with p.open('x',encoding='utf8') as f: json.dump(v,f,ensure_ascii=False,indent=2,sort_keys=True); f.write('\n')

def import_source(p):
    need(regular(p),'GC29_PROJECT_HELPER_MISSING')
    spec=importlib.util.spec_from_file_location('gc29_source_helper',str(p))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def bounded_path(raw,source_root):
    need(isinstance(raw,str) and raw.strip(),'RESOURCE_PATH_MISSING')
    p=Path(raw)
    if not p.is_absolute():p=source_root/p
    need(regular(p),'SOURCE_RESOURCE_NOT_REGULAR')
    return p

def source_resources(path,source_root):
    need(regular(path),'SOURCE_RESOURCE_MANIFEST_MISSING')
    doc=yaml.safe_load(path.read_text(encoding='utf8'))
    need(doc.get('schema_version')=='gdl_greeting_card_private_resource_manifest_v0_1','RESOURCE_SCHEMA')
    data=doc['resources']
    def resource(name,want):
        d=data[name]
        need(isinstance(d,dict),'RESOURCE_BINDING_NOT_MAPPING')
        # Private path-only bindings are canonical: actual bytes must match
        # the project-pinned expected SHA256 below. A supplied digest may not disagree.
        need('sha256' not in d or d['sha256']==want,'RESOURCE_SHA_BINDING_MISMATCH')
        p=bounded_path(d.get('path'),source_root)
        need(p.stat().st_size<=512*1024*1024 and digest(p)==want,'RESOURCE_SHA_CHECK_FAILED')
        return p
    return (resource('template.greeting_card.dolinska.v1',REFERENCE_SHA),
            resource('asset.flowers.default.v1',FLOWERS_SHA),
            resource('source.greeting_card.signature.herasymenko.v1',HERASYMENKO_SHA))

def to_svg(drawings, page):
    """Convert the seven pinned source GRIGO fill vectors to a portable SVG.
    Fail closed on unrecognized PDF path operations; do not flatten a PDF page.
    """
    from xml.sax.saxutils import escape
    def xy(pt): return f'{float(pt.x):.4f} {float(pt.y):.4f}'
    paths=[]
    for row in drawings:
        ops=[]
        for item in row['items']:
            typ=item[0]
            if typ=='l':
                ops.append('M '+xy(item[1])+' L '+xy(item[2]))
            elif typ=='c':
                ops.append('M '+xy(item[1])+' C '+' '.join(xy(x) for x in item[2:5]))
            elif typ=='re':
                r=item[1];ops.append(f'M {r.x0:.4f} {r.y0:.4f} H {r.x1:.4f} V {r.y1:.4f} H {r.x0:.4f} Z')
            else:
                raise Blocked('GRIGO_VECTOR_OPERATION_UNSUPPORTED_'+str(typ).upper())
        need(bool(ops),'GRIGO_VECTOR_EMPTY_PATH')
        fill=row.get('fill')
        need(fill is not None,'GRIGO_VECTOR_FILL_MISSING')
        color='#%02x%02x%02x'%tuple(max(0,min(255,round(float(x)*255))) for x in fill[:3])
        even='evenodd' if row.get('even_odd') else 'nonzero'
        paths.append('<path d="'+escape(' '.join(ops),{'"':'&quot;'})+'" fill="'+color+'" fill-rule="'+even+'"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="214mm" height="301mm" '
            'viewBox="0 0 606.6142 853.2283">'+''.join(paths)+'</svg>').encode('utf8')

def bootstrap(reference,flowers,sender,gc19_dir,gc20_dir,dest):
    """Historical-PDF materialization ONLY HERE, never in prepare/runtime."""
    import pymupdf
    from PIL import Image
    gc21=import_source(GC21)
    need(not dest.exists() and not dest.is_symlink(),'VAULT_DESTINATION_EXISTS')
    need(directory(gc19_dir) and directory(gc20_dir),'GC19_GC20_PRIVATE_ASSETS_REQUIRED')
    g19=json.loads((gc19_dir/'manifest.json').read_text('utf8'))
    g20=json.loads((gc20_dir/'scene_p02.json').read_text('utf8'))
    need(g19.get('source_pdf_sha256')==REFERENCE_SHA and g20.get('source_reference_pdf_sha256')==REFERENCE_SHA,'GC19_GC20_PROVENANCE_MISMATCH')
    need(digest(reference)==REFERENCE_SHA and digest(flowers)==FLOWERS_SHA and digest(sender)==HERASYMENKO_SHA,'BOOTSTRAP_SOURCE_SHA_MISMATCH')
    catalog=json.loads(GC23.read_text('utf8'))
    want=catalog['signature_variants']['GRIGO']
    need(want['source_sha256']==REFERENCE_SHA,'GRIGO_SOURCE_BINDING_DRIFT')
    assets={}; metas={}
    def add(name,content,bbox,kind='raster'):
        need(name not in assets and len(content)>200 and len(bbox)==4 and bbox[2]>bbox[0] and bbox[3]>bbox[1], 'ASSET_METADATA_INVALID')
        assets[name]=content
        metas[name]={'sha256':sha256(content).hexdigest(),'bbox_mm':[round(float(x),4) for x in bbox],'kind':kind,'size_bytes':len(content)}
    with pymupdf.open(reference) as pdf:
        need(len(pdf)==4,'REFERENCE_FOUR_PAGES_REQUIRED')
        for ix in (0,2,3):
            page=pdf[ix]
            for role,prefix in (('PAPER',gc21.HASHES['paper']),('FRAME',gc21.HASHES['frame'])):
                item=gc21.image_match(page,prefix)
                b,_=gc21.png_rgba_from_xref(pdf,page,item)
                add(f'p{ix+1:02}_{role.lower()}.png',b,gc21.bbox_mm(item))
        logo=gc21.image_match_front_logo(pdf[0])[0]
        b,_=gc21.png_rgba_from_xref(pdf,pdf[0],logo)
        add('p01_logo.png',b,gc21.bbox_mm(logo))
        portrait=gc21.image_match(pdf[2],gc21.HASHES['portrait_reference'])
        pb=gc21.bbox_mm(portrait)
        with Image.open(flowers) as raw:
            image=raw.convert('RGBA')
            target=(int(portrait['width']),int(portrait['height']))
            ratio=target[0]/target[1]
            if image.width/image.height>ratio:
                w=round(image.height*ratio); left=(image.width-w)//2; image=image.crop((left,0,left+w,image.height))
            else:
                h=round(image.width/ratio);top=(image.height-h)//2;image=image.crop((0,top,image.width,top+h))
            image=image.resize(target,Image.Resampling.LANCZOS)
            out=io.BytesIO();image.save(out,'PNG')
            add('p03_flowers.png',out.getvalue(),pb)
        # Use GC21 audited exact seven GRIGO vector paths; source PDF only at bootstrap.
        gc21.audit_reference_p04_vectors(pdf[3])
        selected=[]
        w,h=pdf[3].rect.width,pdf[3].rect.height
        for row in pdf[3].get_drawings():
            rect=pymupdf.Rect(row['rect'])
            if rect.width<=0 or rect.height<=0 or not ('f' in str(row.get('type','')).lower() or row.get('fill') is not None):continue
            cx=(rect.x0+rect.x1)/2;cy=(rect.y0+rect.y1)/2
            if cy<=h*.66 or cx<=w*.45 or rect.width>=w*.45 or rect.height>=h*.35:continue
            selected.append(row)
        need(len(selected)==7,'GRIGO_VECTOR_COUNT_MISMATCH')
        svg=to_svg(selected,pdf[3]);add('p04_grigo_signature.svg',svg,[0,0,214,301],kind='vector')
    # P02 locked base, P02/P04 watercolor opacity layers from source-pinned project products.
    for filename,bbox in [('p02_locked_background.png',[0,0,*SIZE]),('p02_watermark_layer.png',g20['watermark_bbox_pdf_mm'])]:
        p=gc20_dir/filename;need(regular(p) and digest(p)==g20['artifacts_sha256'][filename],'GC20_SHA_MISMATCH')
        add('p02_locked.png' if filename.startswith('p02_locked') else 'p02_watermark.png',p.read_bytes(),bbox)
    wm4=next((v for v in g19['watermarks'] if v.get('physical_page')==4),None)
    need(wm4 and wm4['object_id']=='P04_GREETING.WATERMARK','GC19_P04_MISSING')
    p=gc19_dir/'p04_greeting_watermark.png'
    need(regular(p) and digest(p)==wm4['sha256'],'GC19_P04_SHA_MISMATCH')
    add('p04_watermark.png',p.read_bytes(),wm4['bbox_pdf_mm'])
    hb,hbbox=gc21.selected_signature_image(sender)
    add('p04_herasymenko_signature.png',hb,hbbox)
    manifest={'schema':'gdl_gc29_native_asset_vault_v0_1','state':'FROZEN_PRIVATE_ASSETS_NOT_PRODUCTION',
              'source_sha256':{'canonical_reference_one_time':REFERENCE_SHA,'flowers_one_time':FLOWERS_SHA,'hera_one_time':HERASYMENKO_SHA},
              'page_mm':SIZE,'asset_count':len(metas),'assets':metas,
              'pdf_required_by_normal_runtime':False,'requires_visual_review':True}
    # Only write after all validation/extraction has passed.
    dest.mkdir(parents=True,mode=0o700)
    for name,content in assets.items():
        with (dest/name).open('xb') as f: f.write(content)
    write_json(dest/'vault_manifest.json',manifest)
    return manifest

def verify_vault(vault):
    need(directory(vault),'GC29_VAULT_NOT_INSTALLED')
    mp=vault/'vault_manifest.json'
    need(regular(mp),'GC29_VAULT_MANIFEST_MISSING')
    d=json.loads(mp.read_text('utf8'))
    need(d.get('schema')=='gdl_gc29_native_asset_vault_v0_1' and d.get('pdf_required_by_normal_runtime') is False,'GC29_VAULT_SCHEMA')
    need(len(d['assets'])>=12 and d['asset_count']==len(d['assets']),'GC29_VAULT_ASSET_COUNT')
    for name,entry in d['assets'].items():
        need(re.fullmatch(r'p\d\d_[a-z0-9_]+\.(png|svg)',name) is not None,'GC29_VAULT_ASSET_NAME')
        p=vault/name
        need(regular(p) and p.stat().st_size==entry['size_bytes'] and digest(p)==entry['sha256'],'GC29_VAULT_ASSET_SHA')
    return d

def workspace(client,share=SHARE):
    need(client and client not in ('.','..') and not any(c in client for c in '/\\\x00'),'CLIENT_NAME_INVALID')
    need(directory(share),'SMB_SHARE_MISSING')
    clientpath=share/client
    ws=clientpath/'_forprint_automation'
    for p in (clientpath,ws,ws/'input',ws/'output',ws/'template_studio'):
        need(directory(p),'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(ws.resolve(strict=True).parent.parent==share.resolve(strict=True),'CLIENT_WORKSPACE_ESCAPED')
    return ws

def install_vault(source,ws):
    mf=verify_vault(source)
    dest=ws/'template_studio'/'native_asset_vault_v0_1'
    need(not dest.exists() and not dest.is_symlink(),'VAULT_ALREADY_INSTALLED_NO_OVERWRITE')
    runs=ws/'template_studio'/'native_runs'
    need(not runs.is_symlink(),'CLIENT_NATIVE_RUNS_SYMLINK')
    if not runs.exists():runs.mkdir(mode=0o750)
    need(directory(runs),'CLIENT_NATIVE_RUNS_UNSAFE')
    dest.mkdir(mode=0o750)
    for name in [*mf['assets'].keys(),'vault_manifest.json']:
        shutil.copyfile(source/name,dest/name)
    verify_vault(dest)
    return dest

def accepted_jobs(ws):
    # Native runtime reads only accepted ZIP, NOT Builder PDF/Prepress Hub.
    archives=[]
    for p in (ws/'input').glob('*.zip'):
        if not regular(p) or not (0 < p.stat().st_size <= 40*1024*1024):continue
        with zipfile.ZipFile(p) as z:
            names=z.namelist()
            if set(['accepted_constructor_bundle.yaml','artifact_manifest.yaml','handoff_manifest.json']).issubset(names): archives.append(p)
    need(len(archives)==1,'ACCEPTED_HANDOFF_ARCHIVE_NOT_UNIQUE')
    p=archives[0]
    need(regular(p) and 0 < p.stat().st_size<=40*1024*1024,'ACCEPTED_ARCHIVE_SIZE_OR_TYPE')
    # Reuse the existing GC25 authoritative provenance and asset-binding gate.
    verifier=import_source(HERE/'gc25_illustrator_smb_preflight_v0_1.py')
    cat=json.loads(GC23.read_text('utf8'))
    with zipfile.ZipFile(p) as test_z:
        valid=verifier.check_accepted(test_z,verifier.safe_zip(test_z),cat)
        need(valid['kind']=='ACCEPTED_HANDOFF' and valid['status']=='NATIVE_EXECUTOR_NOT_READY','GC25_ACCEPTED_PREFLIGHT_FAILED')
    with zipfile.ZipFile(p) as z:
        names=z.namelist()
        need(len(names)==len(set(names)),'ARCHIVE_DUPLICATE_FILES')
        raw=z.read('accepted_constructor_bundle.yaml');art=z.read('artifact_manifest.yaml')
        h=json.loads(z.read('handoff_manifest.json'))
        need(h.get('accepted_bundle_file_sha256')==sha256(raw).hexdigest() and h.get('artifact_manifest_file_sha256')==sha256(art).hexdigest(),'ACCEPTED_MANIFEST_SHA')
        need(h.get('mode')=='REVIEW_ONLY','ACCEPTED_HANDOFF_AUTHORITY')
        b=yaml.safe_load(raw);a=yaml.safe_load(art)
        need(b.get('constructor_input_class')=='ACCEPTED_CONSTRUCTOR_BUNDLE' and (b.get('intake_review') or {}).get('state')=='PASS','ACCEPTED_CONSTRUCTOR_GATE')
        return b['jobs'],a,p

def compile_scene(job,vault_manifest,logo=None):
    # Native candidate includes real accepted text, not Builder PDF pages.
    b=job['builder_v1'];front=b['front'];inside=b['inside_image'];sender=b['sender_text']
    fam=front['family'];sig=sender['signature_variant_id'];im=inside['mode']
    need(front['occasion']['kind']=='BIRTHDAY','NATIVE_OCCASION_NEEDS_REVIEW')
    need(fam in ('STANDARD','RECIPIENT_BRANDING_OVERLAY'),'NATIVE_FRONT_FAMILY_NEEDS_REVIEW')
    need(im=='DEFAULT_ASSET' and inside['asset_sha256']==FLOWERS_SHA,'NATIVE_IMAGE_NEEDS_REVIEW')
    need(sig in ('GRIGO','HERASYMENKO'),'NATIVE_SIGNATURE_NEEDS_REVIEW')
    need((job.get('signature_selection') or {}).get('variant_id')==sig,'SIGNATURE_SELECTION_CONFLICT')
    greeting=job['structured_greeting_data']['greeting_text']
    need(isinstance(greeting,str) and 10<len(greeting)<8000,'GREETING_INVALID')
    title=front['occasion']['display_text']
    need(title=='Привітання з нагоди Дня Народження!','TITLE_LAYOUT_NEEDS_REVIEW')
    sid=job['job_id']
    layers=[]
    def asset(page,role,name,locked=False,bbox_override=None):
        v=vault_manifest['assets'][name]
        layers.append({'page':page,'role':role,'file':'assets/'+name,'kind':v['kind'],
                       'bbox_mm':bbox_override or v['bbox_mm'],'locked':locked})
    asset(1,'P01.PAPER','p01_paper.png',True)
    asset(1,'P01.FRAME','p01_frame.png')
    asset(1,'P01.SENDER_LOGO','p01_logo.png',False,
          [64.5,59.5,149.5,144.5] if fam=='STANDARD' else [69,39,145,115])
    asset(2,'P02.LOCKED_BASE','p02_locked.png',True)
    asset(2,'P02.WATERMARK','p02_watermark.png')
    asset(3,'P03.PAPER','p03_paper.png',True)
    asset(3,'P03.FLOWERS','p03_flowers.png')
    asset(3,'P03.FRAME','p03_frame.png')
    asset(4,'P04.PAPER','p04_paper.png',True)
    asset(4,'P04.WATERMARK','p04_watermark.png')
    asset(4,'P04.FRAME','p04_frame.png')
    asset(4,'P04.SIGNATURE', 'p04_grigo_signature.svg' if sig=='GRIGO' else 'p04_herasymenko_signature.png')
    if fam=='RECIPIENT_BRANDING_OVERLAY':
        need(logo is not None,'RECIPIENT_BRANDING_ASSET_MISSING')
        layers.append({'page':1,'role':'P01.RECIPIENT_BRANDING','kind':'raster','file':'assets/recipient_branding.png',
                      'bbox_mm':[26,134,188,191],'locked':False})
    name=' '.join(x['text'] for x in sender['lines'])
    need(len(sender['lines']) in (3,4),'SENDER_LINE_COUNT_UNSUPPORTED')
    return {'schema_version':'gdl_gc29_native_scene_v0_1','job_id':sid,'source_mode':'ACCEPTED_ZIP_PLUS_FROZEN_PROJECT_ASSETS',
            'pages':4,'page_mm':SIZE,'family':fam,'signature':sig,'image_mode':im,
            'front_lines':['Привітання з нагоди','Дня Народження!'],
            'occasion_bbox_mm':([32,203.5,182,248] if fam=='STANDARD' else [32,203.5,182,248]),
            'greeting_text':greeting,'sender_lines':[x['text'] for x in sender['lines']],
            'layers':layers,'visual_approved':False,'production_ready':False,'customer_approved':False,
            'review_required':['font metrics','P03 figure clipping','GRIGO/HERASYMENKO signature','P01 branding logo bbox','CMYK'],
            'frozen_asset_count':vault_manifest['asset_count']}

def rasterize_grigo_signature_svg(data: bytes) -> bytes:
    """Make a placement-compatible *graphic* PNG, keeping all sender text live.

    The immutable SVG remains in the vault with its SHA256. Conversion is from
    that verified SVG, never from a PDF or an arbitrary customer-provided file.
    """
    import pymupdf
    need(isinstance(data, bytes) and 200 < len(data) < 2_000_000,
         'GC31_SOURCE_SVG_SIZE_INVALID')
    need(data.lstrip().startswith(b'<svg') and b'http://www.w3.org/2000/svg' in data[:500],
         'GC31_SOURCE_SVG_HEADER_INVALID')
    try:
        with pymupdf.open(stream=data, filetype='svg') as doc:
            need(doc.page_count == 1, 'GC31_SOURCE_SVG_PAGE_COUNT')
            page = doc[0]
            # Source artboard is the 214 x 301 mm original, independent of PDF.
            need(abs(page.rect.width - 214 * 72 / 25.4) < 2 and
                 abs(page.rect.height - 301 * 72 / 25.4) < 2,
                 'GC31_SOURCE_SVG_ARTBOARD_MISMATCH')
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2),
                                  colorspace=pymupdf.csRGB, alpha=True)
            png = pix.tobytes('png')
    except Blocked:
        raise
    except (RuntimeError, ValueError, OSError) as exc:
        raise Blocked('GC31_SOURCE_SVG_RENDER_BLOCKED') from exc
    need(png.startswith(b'\x89PNG\r\n\x1a\n') and len(png) > 200,
         'GC31_DERIVED_PNG_INVALID')
    return png


def bind_illustrator_signature(scene, vault, vault_manifest):
    """GRIGO's facsimile is artwork; text rows remain editable TextFrames."""
    generated = {}
    for layer in scene['layers']:
        if layer.get('role') != 'P04.SIGNATURE':
            continue
        if layer['file'] == 'assets/p04_grigo_signature.svg':
            name = 'p04_grigo_signature.svg'
            source = vault / name
            record = vault_manifest['assets'][name]
            need(regular(source) and digest(source) == record['sha256'],
                 'GC31_SIGNATURE_SOURCE_SHA_INVALID')
            png = rasterize_grigo_signature_svg(source.read_bytes())
            generated['p04_grigo_signature.png'] = png
            layer['file'] = 'assets/p04_grigo_signature.png'
            layer['kind'] = 'raster'
            layer['source_graphic_sha256'] = record['sha256']
            scene['signature_graphic_placement'] = 'SOURCE_PINNED_SVG_TO_TRANSPARENT_PNG'
        else:
            scene['signature_graphic_placement'] = 'SOURCE_PINNED_RASTER'
    need(len(generated) <= 1, 'GC31_GRAPHIC_SIGNATURE_COUNT_INVALID')
    return generated


def prepare(ws,job_id,run_id):
    need(SAFE.fullmatch(run_id) is not None,'RUN_ID_INVALID')
    vault=ws/'template_studio'/'native_asset_vault_v0_1'
    catalog=verify_vault(vault)
    jobs,artifact,archive=accepted_jobs(ws)
    selected=[x for x in jobs if x['job_id']==job_id]
    need(len(selected)==1,'JOB_ID_NOT_ACCEPTED')
    job=selected[0]
    logo=None
    if job['builder_v1']['front']['family']=='RECIPIENT_BRANDING_OVERLAY':
        info=job['builder_v1']['front']['recipient_branding'];ref=info['accepted_artifact_ref']
        a=artifact['artifacts'][ref]
        need(a['sha256']==info['asset_sha256'],'RECIPIENT_BRANDING_SHA_MISMATCH')
        with zipfile.ZipFile(archive) as z:
            member=a.get('path') or a.get('archive_member')
            need(isinstance(member,str) and member in z.namelist(),'BRANDING_ARTIFACT_MISSING')
            logo=z.read(member)
        need(sha256(logo).hexdigest()==info['asset_sha256'],'BRANDING_ASSET_SHA_MISMATCH')
    scene=compile_scene(job,catalog,logo)
    generated=bind_illustrator_signature(scene,vault,catalog)
    template=TEMPLATE.read_text('utf8')
    marker='/*__GC29_SCENE__*/';need(template.count(marker)==1,'JSX_MARKER_INVALID')
    jsx=template.replace(marker,json.dumps(scene,ensure_ascii=True,separators=(',',':')))
    dest=ws/'template_studio'/'native_runs'/ (job_id+'__'+run_id)
    need(not dest.exists() and not dest.is_symlink(),'NATIVE_RUN_EXISTS_NO_OVERWRITE')
    need(directory(dest.parent),'NATIVE_RUNS_DIRECTORY_MISSING')
    dest.mkdir(mode=0o750)
    (dest/'assets').mkdir(mode=0o750)
    for layer in scene['layers']:
        name=Path(layer['file']).name
        if name=='recipient_branding.png':
            (dest/'assets'/name).write_bytes(logo)
        elif name in generated:
            (dest/'assets'/name).write_bytes(generated[name])
        else:
            shutil.copyfile(vault/name,dest/'assets'/name)
    (dest/'run_in_illustrator.jsx').write_text(jsx,encoding='utf8')
    # No private text in machine summary; it lives only in private generated JSX.
    public={k:v for k,v in scene.items() if k not in ('greeting_text','sender_lines','front_lines')}
    public['accepted_zip_sha256']=digest(archive)
    public['asset_sha256']={p.name:digest(p) for p in (dest/'assets').iterdir()}
    public['jsx_sha256']=digest(dest/'run_in_illustrator.jsx')
    write_json(dest/'scene_manifest.json',public)
    return dest,scene

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('bootstrap','vault-check','install-vault','list','prepare'))
    ap.add_argument('--source-root',type=Path,default=ROOT.parent/'forprint_prepress_hub')
    ap.add_argument('--resource-manifest',type=Path)
    ap.add_argument('--gc19-assets-dir',type=Path)
    ap.add_argument('--gc20-assets-dir',type=Path)
    ap.add_argument('--vault',type=Path)
    ap.add_argument('--client-name');ap.add_argument('--job-id');ap.add_argument('--run-id')
    ap.add_argument('--confirm-bootstrap',action='store_true')
    ap.add_argument('--confirm-install',action='store_true')
    ap.add_argument('--confirm-prepare',action='store_true')
    args=ap.parse_args()
    try:
        if args.mode=='bootstrap':
            need(args.confirm_bootstrap and args.resource_manifest and args.gc19_assets_dir and args.gc20_assets_dir and args.vault,'BOOTSTRAP_ARGS_REQUIRED')
            ref,flower,sender=source_resources(args.resource_manifest,args.source_root)
            result=bootstrap(ref,flower,sender,args.gc19_assets_dir,args.gc20_assets_dir,args.vault)
            print(f'GC29_VAULT_BOOTSTRAP=PASS ASSET_COUNT={result["asset_count"]} NORMAL_RUNTIME_REQUIRES_PDF=false')
        elif args.mode=='vault-check':
            need(args.vault is not None,'VAULT_REQUIRED')
            doc=verify_vault(args.vault)
            print(f'GC29_VAULT_CHECK=PASS ASSET_COUNT={doc["asset_count"]} PDF_RUNTIME_DEPENDENCY=false')
        else:
            need(args.client_name is not None,'CLIENT_NAME_REQUIRED')
            ws=workspace(args.client_name)
            if args.mode=='install-vault':
                need(args.confirm_install and args.vault is not None,'INSTALL_ARGS_REQUIRED')
                dest=install_vault(args.vault,ws)
                print('GC29_NATIVE_VAULT=INSTALLED_VERIFIED RELATIVE='+str(dest.relative_to(ws)))
            elif args.mode=='list':
                verify_vault(ws/'template_studio'/'native_asset_vault_v0_1')
                jobs,_,_=accepted_jobs(ws)
                for j in jobs:
                    b=j['builder_v1']; print('GC29_JOB='+j['job_id']+' FRONT='+b['front']['family']+' SIGNATURE='+b['sender_text']['signature_variant_id'])
                print('GC29_RUNTIME_LIST=PASS_NO_PDF_READ')
            elif args.mode=='prepare':
                need(args.confirm_prepare and args.job_id and args.run_id,'PREPARE_ARGS_REQUIRED')
                dest,scene=prepare(ws,args.job_id,args.run_id)
                print('GC29_NATIVE_SCENE=PREPARED_ILLUSTRATOR_PENDING')
                print('GC29_RUN_RELATIVE='+str(dest.relative_to(ws)))
                print('GC29_PAGES=4 SOURCE_PDF_RUNTIME_READ=false PRODUCTION_READY=false')
        return 0
    except (Blocked,OSError,KeyError,TypeError,ValueError,zipfile.BadZipFile) as e:
        print('GC29_NATIVE=BLOCKED reason='+ (str(e) if isinstance(e,Blocked) else type(e).__name__),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
