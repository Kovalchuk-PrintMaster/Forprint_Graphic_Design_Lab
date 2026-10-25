"""Source-only GC21 regression tests; no client assets, Windows, or Illustrator."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'scripts/graphic_design_lab/greeting_cards/gc21_native_illustrator_builder_v0_1.py'
spec=importlib.util.spec_from_file_location('gc21', MODULE)
f1=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=f1
spec.loader.exec_module(f1)


def fake_scene():
    return {'schema_version': f1.SCENE_SCHEMA, 'pages':4, 'sender_variant':'HERASYMENKO',
      'front_family':'STANDARD','inside_image_mode':'PORTRAIT','size_mm':[214,301],
      'layers':[{'page':x,'role':f'P{x}.BACKGROUND','file':f'assets/p{x}.png',
                 'bbox_mm':[0,0,214,301],'kind':'raster','locked':True} for x in range(1,5)],
      'front_lines':['Привітання з нагоди','Дня Народження!'],
      'greeting_text':'Привітання тестовому отримувачу!\nДругий рядок.',
      'greeting_rgb':0x664422,
      'sender_lines':[{'id':f'P04.SENDER_LINE_0{i}', 'text':str(i), 'size_pt':12,
                       'x_mm':31,'baseline_from_top_mm':220+i*7,'rgb':0} for i in range(1,5)]}


def fake_job():
    return {'signature_selection':{'variant_id':'HERASYMENKO'},
        'structured_greeting_data':{'greeting_text':'Нейтральне тестове привітання'},
        'builder_v1':{'schema_version':'gdl_greeting_card_builder_payload_v0_1',
            'front':{'family':'STANDARD','occasion':{'display_text':'Привітання з нагоди Дня Народження!'}},
            'inside_image':{'mode':'PORTRAIT','asset_id':'exact-art','asset_sha256':'a'*64,
                            'accepted_artifact_ref':'approved-001'},
            'sender_text':{'signature_variant_id':'HERASYMENKO'}}}


def synthetic_reference_vector_page(count=120, delta_mm=0):
    """Emulate canonical 7 blue-ink GRIGO paths + 113 non-signature paths."""
    import pymupdf
    w, h = [x * 72 / 25.4 for x in f1.SIZE]
    d = pymupdf.open()
    p = d.new_page(width=w, height=h)
    mm_to_pt = 72 / 25.4
    coords = [
        (103.465, 213.348, 106.0, 216.0),
        (110.0, 215.0, 113.0, 219.0),
        (120.0, 225.0, 123.0, 229.0),
        (130.0, 230.0, 133.0, 234.0),
        (140.0, 235.0, 143.0, 238.0),
        (145.0, 239.0, 148.0, 242.0),
        (153.0, 245.0, 155.203 + delta_mm, 247.531),
    ]
    for a,b,c,d_mm in coords:
        r=pymupdf.Rect(a*mm_to_pt,b*mm_to_pt,c*mm_to_pt,d_mm*mm_to_pt)
        p.draw_rect(r,color=None,fill=(0.1,0.2,0.8))
    for i in range(count-len(coords)):
        x=10.0 + (i % 20)*.2
        y=70.0 + (i % 20)*.2
        p.draw_line((x*mm_to_pt,y*mm_to_pt),
                    ((x+.1)*mm_to_pt,(y+.1)*mm_to_pt),
                    color=(0,0,0),width=.2)
    return d,p


def test_real_reference_classification_separates_seven_of_120():
    d,p=synthetic_reference_vector_page()
    try:
        result=f1.audit_reference_p04_vectors(p)
        assert result['source_verified_grigo_vector_count']==7
        assert result['legacy_non_signature_drawing_count']==113
        assert result['reference_grigo_vectors_imported'] is False
        assert result['selected_sender']=='HERASYMENKO'
    finally:
        d.close()


def test_reference_vector_audit_rejects_changed_inventory():
    d,p=synthetic_reference_vector_page(count=119)
    try:
        with pytest.raises(f1.Blocked,match='P04_REFERENCE_VECTOR_INVENTORY_CHANGED'):
            f1.audit_reference_p04_vectors(p)
    finally:
        d.close()


def test_reference_vector_audit_rejects_signature_geometry_drift():
    d,p=synthetic_reference_vector_page(delta_mm=1.0)
    try:
        with pytest.raises(f1.Blocked,match='P04_CANONICAL_GRIGO_VECTOR_BBOX_MISMATCH'):
            f1.audit_reference_p04_vectors(p)
    finally:
        d.close()


def test_static_template_builds_real_four_artboards():
    jsx=f1.render_jsx(fake_scene())
    assert 'document.artboards.add(' in jsx
    assert 'document.layers.add()' in jsx
    assert 'document.textFrames.areaText(' in jsx
    assert 'document.textFrames.pointText(' in jsx
    assert 'document.saveAs(ai,save)' in jsx
    assert 'document.saveAs(pdf,pdfOpts)' in jsx
    assert 'document.exportFile(png,ExportType.PNG24,opt)' in jsx
    assert 'item.embed()' in jsx
    assert 'app.open(ai)' in jsx
    assert 'GC21_NATIVE_FOUR_ARTBOARD_V0_1' in jsx


def test_scene_encoding_is_safe_utf8_js_literal():
    scene=fake_scene(); scene['greeting_text']='Лапки " і новий\nрядок \\'
    jsx=f1.render_jsx(scene)
    assert '\\u041b' in jsx  # ensure_ascii, literal source safe for ExtendScript
    assert '/*__GC21_SCENE_JSON__*/' not in jsx
    assert '\\n' in jsx
    assert 'var scene = {' in jsx


def test_native_pipeline_does_not_import_pdf():
    source=f1.TEMPLATE.read_text(encoding='utf8')
    assert 'PDF import' not in source.replace('No PDF import','')
    assert 'app.open(pdf)' not in source
    assert 'File.openDialog(' not in source
    assert 'new IllustratorSaveOptions' in source


def test_front_exact_title():
    assert f1.p01_front_lines('Привітання з нагоди Дня Народження!')==[
        'Привітання з нагоди','Дня Народження!']


def test_front_unapproved_title_is_blocked():
    with pytest.raises(f1.Blocked,match='P01_OCCASION_VARIANT_NEEDS_SOURCE_LAYOUT_REVIEW'):
        f1.p01_front_lines('Нова листівка')


def test_exact_job_binding_accepts_pilot():
    job=fake_job(); doc={'artifacts':{'approved-001':{'source_asset_id':'exact-art','sha256':'a'*64}}}
    returned=f1.verify_selected_job({'jobs':[job]},doc)
    assert returned[1]['inside_image']['mode']=='PORTRAIT'
    assert returned[3]=='Нейтральне тестове привітання'


@pytest.mark.parametrize('field,value',[
 ('front',{'family':'BILINGUAL_OCCASION'}),
 ('inside_image',{'mode':'DEFAULT_ASSET'}),
 ('sender_text',{'signature_variant_id':'DUAL_GRIGO_HERASYMENKO'})
])
def test_nonpilot_variant_rejected(field,value):
    job=fake_job(); job['builder_v1'][field]=value
    with pytest.raises(f1.Blocked):
        f1.verify_selected_job({'jobs':[job]}, {'artifacts':{'approved-001':{
            'source_asset_id':'exact-art','sha256':'a'*64}}})


def test_accepted_portrait_sha_mismatch_rejected():
    job=fake_job()
    with pytest.raises(f1.Blocked,match='PORTRAIT_ARTIFACT_BINDING'):
        f1.verify_selected_job({'jobs':[job]}, {'artifacts':{'approved-001':{
            'source_asset_id':'exact-art','sha256':'b'*64}}})


def test_no_batch_fallback():
    with pytest.raises(f1.Blocked,match='PILOT_ONE_JOB_ONLY'):
        f1.verify_selected_job({'jobs':[fake_job(),fake_job()]},{'artifacts':{}})


def test_signature_text_is_canonical():
    assert f1.sender_expected([])==['З найщирішими побажаннями','Людмила Герасименко',
                                     'Віцепрезидент, Генеральний','директор ВГО АППУ']


def test_private_pack_keeps_client_text_out_of_manifest(tmp_path,monkeypatch):
    monkeypatch.setattr(f1,'ROOT',tmp_path)
    scene=fake_scene(); scene['greeting_text']='PRIVATE_TEST_GREETING_DO_NOT_PUBLISH'
    blobs={f'p{i}.png':b'not-a-real-image-but-private' for i in range(1,5)}
    jsx=f1.render_jsx(scene)
    folder=f1.prepare('gc21_private_test_r001',scene,blobs,jsx)
    payload=(folder/'run_gc21_in_illustrator.jsx').read_text()
    man=(folder/'scene_manifest.json').read_text()
    assert 'PRIVATE_TEST_GREETING_DO_NOT_PUBLISH' in payload
    assert 'PRIVATE_TEST_GREETING_DO_NOT_PUBLISH' not in man
    assert 'sender_lines' not in json.loads(man)
    assert json.loads(man).get('illustrator_executed') is not True
    assert (folder/'assets/p1.png').read_bytes()==blobs['p1.png']
    assert (folder/'README_PRIVATE.txt').is_file()


def test_private_pack_refuses_existing_destination(tmp_path,monkeypatch):
    monkeypatch.setattr(f1,'ROOT',tmp_path)
    name='gc21_test_existing'
    (tmp_path/'tmp'/name).mkdir(parents=True)
    with pytest.raises(f1.Blocked,match='OUTPUT_ALREADY_EXISTS'):
        f1.prepare(name,fake_scene(),{'x.png':b'abc'},'jsx')


def test_outdir_name_restrictions(tmp_path,monkeypatch):
    monkeypatch.setattr(f1,'ROOT',tmp_path)
    with pytest.raises(f1.Blocked,match='OUTPUT_NAME_INVALID'):
        f1.prepare('../escape',fake_scene(),{},'jsx')


def test_source_hashes_present_without_private_strings():
    assert set(f1.PILOT_HASHES)=={'bundle','resource_manifest','artifact_manifest'}
    assert all(len(x)==64 for x in f1.PILOT_HASHES.values())
    assert f1.REFERENCE_SHA.startswith('66ed88de')


def test_integration_four_page_private_scene_synthetic(tmp_path, monkeypatch):
    """Synthetic four-page reference and accepted asset; NO private customer data."""
    import io
    import hashlib
    import pymupdf
    from PIL import Image
    source=tmp_path/'legacy'; source.mkdir()
    lab=tmp_path/'lab'; lab.mkdir()
    (lab/'tmp').mkdir()
    def make_png(color, size=(100,120), alpha=False):
        mode='RGBA' if alpha else 'RGB'
        image=Image.new(mode,size,tuple(color))
        buf=io.BytesIO(); image.save(buf,'PNG')
        return buf.getvalue()
    paper=make_png((235,237,228))
    frame=make_png((210,85,35,200),(100,120),True)
    logo=make_png((20,150,120))
    photo=make_png((125,50,90,150),(180,180),True)
    watermark=make_png((180,180,180,80),(80,90),True)
    width,height=[v*72/25.4 for v in f1.SIZE]
    rect=pymupdf.Rect(0,0,width,height)
    doc=pymupdf.open()
    bboxes={}
    def insert(page, name, png, xy):
        box=pymupdf.Rect(*[v*72/25.4 for v in xy])
        page.insert_image(box,stream=png,overlay=True)
        bboxes[name]=box
    for i in range(4):
        page=doc.new_page(width=width,height=height)
        insert(page,f'paper{i}',paper,[0,0,214,301])
        if i in (0,2,3):insert(page,f'frame{i}',frame,[5,7,209,294])
        if i==0: insert(page,'logo',logo,[64,59,150,145])
        if i==2:insert(page,'portrait',photo,[0,20,214,280])
        if i==3:
            # Real source shape: 7 signature ink paths, 113 other PDF artifacts.
            coords=[(103.465,213.348,106,216),(110,215,113,219),(120,225,123,229),
                (130,230,133,234),(140,235,143,238),(145,239,148,242),
                (153,245,155.203,247.531)]
            for x0,y0,x1,y1 in coords:
                page.draw_rect(pymupdf.Rect(*[v*72/25.4 for v in (x0,y0,x1,y1)]),
                               color=None,fill=(.1,.2,.8))
            for j in range(113):
                y=(70+(j%20)*.2)*72/25.4
                x=(10+(j%20)*.2)*72/25.4
                page.draw_line((x,y),(x+.1,y+.1),color=(0,0,0),width=.1)
    ref=source/'reference.pdf';doc.save(ref); doc.close()
    with pymupdf.open(ref) as d:
        def digest(page,index):return page.get_image_info(hashes=True,xrefs=True)[index]['digest'].hex()
        hashes={'paper':digest(d[0],0),'frame':digest(d[0],1),'logo':digest(d[0],2),
                'portrait_reference':digest(d[2],2)}
        assert len(d[3].get_drawings())==120
        # PyMuPDF must preserve the alpha of the accepted transparent portrait template.
        item=d[2].get_image_info(hashes=True,xrefs=True)[2]
        assert any(int(v[0])==item['xref'] and int(v[1])>0 for v in d[2].get_images(full=True))
    sender=source/'sender.pdf'
    d=pymupdf.open()
    for i in range(4):d.new_page(width=width,height=height)
    d.save(sender);d.close()
    portrait_file=source/'accepted_portrait.png';portrait_file.write_bytes(photo)
    font_a=source/'monotype.ttf';font_a.write_bytes(b'SYNTHETIC_FONT_ONE')
    font_b=source/'zapf.ttf';font_b.write_bytes(b'SYNTHETIC_FONT_TWO')
    art={'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1',
         'artifacts':{'approved-001':{'source_asset_id':'exact-art','sha256':f1.sha(photo),
             'path':str(portrait_file)}}}
    resources={'schema_version':'gdl_greeting_card_private_resource_manifest_v0_1',
       'resources':{f1.RESOURCE_ID:{'path':str(ref)},f1.SENDER_SOURCE_ID:{'path':str(sender)},
         'font.front_occasion.monotype_corsiva.v1':{'path':str(font_a)},
         'font.greeting_sender.zapf_chancery_c.v1':{'path':str(font_b)}}}
    job=fake_job();job['builder_v1']['inside_image']['asset_sha256']=f1.sha(photo)
    bundle={'jobs':[job]}
    import yaml
    paths={}
    for key,obj in [('bundle',bundle),('resource_manifest',resources),('artifact_manifest',art)]:
        f=source/(key+'.yaml')
        f.write_text(yaml.safe_dump(obj,allow_unicode=True),encoding='utf8')
        paths[key]=str(f)
    conf=source/'config.json'; conf.write_text(json.dumps(paths),encoding='utf8')
    gc19=lab/'tmp/gc19';gc19.mkdir()
    gc20=lab/'tmp/gc20';gc20.mkdir()
    wm_p02=gc20/'p02_watermark_layer.png'; wm_p02.write_bytes(watermark)
    locked_p02=gc20/'p02_locked_background.png';locked_p02.write_bytes(paper)
    wm_p04=gc19/'p04_greeting_watermark.png';wm_p04.write_bytes(watermark)
    (gc19/'manifest.json').write_text(json.dumps({
      'source_pdf_sha256':f1.sha(ref.read_bytes()),'source_alpha_factor':.25,
      'state':'NATIVE_ASSETS_CANDIDATE_VISUAL_REVIEW_REQUIRED',
      'watermarks':[{'physical_page':4,'object_id':'P04_GREETING.WATERMARK',
                     'bbox_pdf_mm':[20,56,194,238],'sha256':f1.sha(watermark)}]}))
    (gc20/'scene_p02.json').write_text(json.dumps({
      'source_reference_pdf_sha256':f1.sha(ref.read_bytes()),
      'watermark_source_alpha_multiplier':.25,
      'state':'P02_NATIVE_LAYER_ASSETS_VISUAL_REVIEW_REQUIRED',
      'artboard_mm':[214,301],'physical_page':2,
      'watermark_bbox_pdf_mm':[20,60,194,241],
      'artifacts_sha256':{'p02_locked_background.png':f1.sha(paper),
                          'p02_watermark_layer.png':f1.sha(watermark)}}))
    monkeypatch.setattr(f1,'ROOT',lab)
    monkeypatch.setattr(f1,'PILOT_HASHES', {k:f1.sha(Path(v).read_bytes()) for k,v in paths.items()})
    monkeypatch.setattr(f1,'REFERENCE_SHA',f1.sha(ref.read_bytes()))
    monkeypatch.setattr(f1,'SENDER_SHA',f1.sha(sender.read_bytes()))
    monkeypatch.setattr(f1,'HASHES',hashes)
    monkeypatch.setattr(f1,'selected_signature_image',lambda p:(watermark,[83,215,128,274]))
    monkeypatch.setattr(f1,'greeting_style_from_pdf',lambda p:0x554433)
    monkeypatch.setattr(f1,'sender_spans_from_pdf',lambda p:[
      {'text':text,'spans':[{'text':text,'origin':[31*72/25.4,(220+i*7)*72/25.4],
                             'size':12.17,'color':0x111111}]}
        for i,text in enumerate(f1.sender_expected([]))])
    scene,blobs=f1.make_scene(conf,source,gc19,gc20)
    assert scene['pages']==4
    assert scene['p04_reference_vector_audit']['legacy_non_signature_drawing_count']==113
    assert len(scene['layers'])==12
    assert {obj['page'] for obj in scene['layers']}=={1,2,3,4}
    assert scene['greeting_text']=='Нейтральне тестове привітання'
    assert scene['greeting_rgb']==0x554433
    assert 'p03_accepted_portrait.png' in blobs
    assert 'p04_watermark.png' in blobs
    jsx=f1.render_jsx(scene)
    output=f1.prepare('gc21_fullcard_synthetic_001',scene,blobs,jsx)
    assert (output/'run_gc21_in_illustrator.jsx').is_file()
    assert len(list((output/'assets').iterdir()))==12
    metadata=json.loads((output/'scene_manifest.json').read_text())
    assert metadata['pages']==4
    assert 'greeting_text' not in metadata
    assert metadata['production_ready'] is False


class FakePageImages:
    def __init__(self, items):
        self.items = items
    def get_image_info(self, *, hashes, xrefs):
        assert hashes and xrefs
        return self.items


def synthetic_logo_record(digest, bbox=None, pixels=None):
    if bbox is None:
        bbox = f1.P01_LOGO_BBOX_MM
    if pixels is None:
        pixels = f1.P01_LOGO_PIXEL_SIZE
    return {'digest': bytes.fromhex(digest), 'bbox': [float(v)/f1.MM for v in bbox],
            'width': pixels[0], 'height': pixels[1], 'xref': 41}



def test_logo_full_md5_accepted_in_synthetic_test(monkeypatch):
    md5 = '0123456789abcdef0123456789abcdef'
    monkeypatch.setattr(f1,'HASHES',{**f1.HASHES,'logo':md5})
    item=synthetic_logo_record(md5)
    got,mode=f1.image_match_front_logo(FakePageImages([item]))
    assert got is item and mode=='EXACT_MD5'


def actual_matching_prefix_but_not_pseudo_md5():
    return '78b87a619527' + 'a0' * 10  # canonical prefix, unknown tail, 32 hex


def test_logo_prefix12_match_requires_canonical_geometry_and_size():
    item=synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5())
    got,mode=f1.image_match_front_logo(FakePageImages([item]))
    assert got is item and mode=='PINNED_PDF_PREFIX12_GEOMETRY_PIXELS'


def test_logo_prefix12_wrong_geometry_rejected():
    bb=list(f1.P01_LOGO_BBOX_MM);bb[0]+=1
    with pytest.raises(f1.Blocked,match='P01_LOGO_CANONICAL_GEOMETRY_MISMATCH'):
        f1.image_match_front_logo(FakePageImages([
            synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5(),bbox=bb)]))


def test_logo_prefix12_wrong_pixels_rejected():
    with pytest.raises(f1.Blocked,match='P01_LOGO_CANONICAL_PIXEL_SIZE_MISMATCH'):
        f1.image_match_front_logo(FakePageImages([
            synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5(),pixels=(950,946))]))


def test_logo_prefix12_duplicate_rejected():
    one=synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5())
    two=synthetic_logo_record('78b87a619527'+'b1'*10)
    with pytest.raises(f1.Blocked,match='P01_LOGO_SOURCE_NOT_UNIQUE'):
        f1.image_match_front_logo(FakePageImages([one,two]))


def test_logo_wrong_digest_prefix_rejected():
    with pytest.raises(f1.Blocked,match='P01_LOGO_SOURCE_NOT_UNIQUE'):
        f1.image_match_front_logo(FakePageImages([synthetic_logo_record('08b87a619527'+'b1'*10)]))


def test_logo_prefix_never_for_unverified_reference(monkeypatch):
    monkeypatch.setattr(f1,'REFERENCE_SHA','1'*64)
    with pytest.raises(f1.Blocked,match='P01_LOGO_PREFIX_ONLY_REQUIRES_CANONICAL_REFERENCE'):
        f1.image_match_front_logo(FakePageImages([
            synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5())]))


def test_logo_old_31_nibble_pseudo_md5_rejected(monkeypatch):
    monkeypatch.setattr(f1,'HASHES',{**f1.HASHES,
        'logo':'78b87a6195270a66b0e32e814f8f597'})
    with pytest.raises(f1.Blocked,match='P01_LOGO_CONFIG_DIGEST_INVALID'):
        f1.image_match_front_logo(FakePageImages([
            synthetic_logo_record(actual_matching_prefix_but_not_pseudo_md5())]))
