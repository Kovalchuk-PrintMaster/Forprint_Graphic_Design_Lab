"""GC27 P03 source-mask/native JSX integration tests, synthetic assets only."""
from __future__ import annotations
import importlib.util
import io
import json
from hashlib import sha256
from pathlib import Path
import sys
import types
import zipfile

from PIL import Image
import pymupdf
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT/'scripts/graphic_design_lab/greeting_cards/gc27_p03_default_flowers_v0_1.py'
spec=importlib.util.spec_from_file_location('gc27_p03_test_module',FILE)
gc27=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=gc27
spec.loader.exec_module(gc27)

def bsha(b):return sha256(b).hexdigest()

def png(rgb, *, size=(220,320), alpha=None):
    im=Image.new('RGBA' if alpha is not None else 'RGB',size,(*rgb,alpha) if alpha is not None else rgb)
    io_=io.BytesIO();im.save(io_,'PNG');return io_.getvalue()


def build_zip(path, *, default=True, staging=False, tainted=False):
    if staging:
        files={'packet_manifest.json':b'{}',
            'SERVER_INGEST_STAGING.yaml':yaml.safe_dump({'packet_kind':'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE'}).encode(),
            'BLOCKERS.yaml':yaml.safe_dump({'final_handoff_allowed':False}).encode()}
    else:
        data={
          'schema_version':'gdl_greeting_card_accepted_constructor_bundle_v0_1',
          'source_batch_id':'synthetic-gc27-check','synthetic_fixture_only':False,
          'intake_review':{'review_id':'accepted-test-only','state':'PASS','source_batch_id':'synthetic-gc27-check'},
          'authority':{k:False for k in ('provider_execution_performed','gdl_runtime_initialized','production_write_enabled','automatic_customer_messaging','automatic_design_approval')},
          'jobs':[],
          'provenance_manifest':{'algorithm':'sha256_canonical_json_v0_1','bundle_sha256':'','intake_review_id':'accepted-test-only'},
        }
        for i in range(4):
            image={'mode':'DEFAULT_ASSET','asset_id':'flowers.default.v1','asset_sha256':'d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67','accepted_artifact_ref':None}
            if not default and i==1:
                image={'mode':'PORTRAIT','asset_id':'portrait-test','asset_sha256':bsha(b'a'),'accepted_artifact_ref':'portrait-ref'}
            data['jobs'].append({
              'structured_greeting_data':{'greeting_text':'Нейтральне привітання для перевірки','occasion':'BIRTHDAY'},
              'signature_selection':{'variant_id':'HERASYMENKO'},
              'branding_selection':{'presence':'ABSENT'},
              'accepted_visual_assets':[{'acceptance_basis':'SOURCE_ASSET_OPERATOR_REVIEW_PASS',
                 'source_asset_id':image['asset_id'],'provenance_sha256':image['asset_sha256'],
                 'artifact_ref':image['accepted_artifact_ref']}],
              'builder_v1':{'front':{'family':'STANDARD',
                  'occasion':{'kind':'BIRTHDAY','display_text':'Привітання з нагоди Дня Народження!'}},
                  'inside_image':image,'sender_text':{'signature_variant_id':'HERASYMENKO'}}})
        # Imported GC25 checks only the accepted envelope / variant selections.
        data['provenance_manifest']['bundle_sha256']=gc27.dependencies()[2].bundle_digest(data)
        blob=yaml.safe_dump(data,allow_unicode=True).encode('utf8')
        art={'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1','artifacts':
             {'portrait-ref':{'source_asset_id':'portrait-test','path':'assets/portrait.png','sha256':bsha(b'a')}} if not default else {}}
        a=yaml.safe_dump(art).encode('utf8')
        hand={'schema_version':'gdl_intake_builder_handoff_v0_1','mode':'REVIEW_ONLY',
           'accepted_bundle_file_sha256':bsha(blob),'artifact_manifest_file_sha256':bsha(a)}
        files={'accepted_constructor_bundle.yaml':blob,'artifact_manifest.yaml':a,
               'handoff_manifest.json':json.dumps(hand).encode('utf8')}
        if not default:files['assets/portrait.png']=b'a'
        if tainted: files['accepted_constructor_bundle.yaml']=blob+b'changed'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,payload in files.items():z.writestr(name,payload)


def sample_assets(tmp_path):
    paper=png((233,233,220))
    frame=png((191,100,48),alpha=130)
    masked=png((140,40,190),size=(430,560),alpha=130)
    d=pymupdf.open(); rect=lambda b:pymupdf.Rect(*[v*72/25.4 for v in b])
    bbox=[19,32,195,268]
    for i in range(4):
        page=d.new_page(width=214*72/25.4,height=301*72/25.4)
        page.insert_image(rect([0,0,214,301]),stream=paper)
        if i == 2:page.insert_image(rect(bbox),stream=masked,keep_proportion=False)
        page.insert_image(rect([5,7,209,294]),stream=frame)
    ref=tmp_path/'canonical.pdf';d.save(ref);d.close()
    flowers=tmp_path/'flowers.png';flowers.write_bytes(png((225,70,50),size=(700,530)))
    with pymupdf.open(ref) as doc:
        p=doc[2]
        info=p.get_image_info(hashes=True,xrefs=True)
        assert len(info)==3
        hashes={'paper':info[0]['digest'].hex(),'portrait_reference':info[1]['digest'].hex(),
                'frame':info[2]['digest'].hex()}
        chosen=p.get_images(full=True)
        assert any(int(v[1])>0 for v in chosen)
    return ref, flowers, hashes

@pytest.fixture
def prepared(tmp_path, monkeypatch):
    gc21,gc23,gc25,gc26=gc27.dependencies()
    ref, flowers, hashes=sample_assets(tmp_path)
    monkeypatch.setattr(gc21,'REFERENCE_SHA',gc27.file_sha(ref))
    monkeypatch.setattr(gc21,'HASHES',hashes)
    snap=gc23.catalog()
    snap['pinned_sha256']['reference_pdf']=gc27.file_sha(ref)
    # The real accepted bundle pins official flowers SHA256. Synthetic image bytes
    # cannot reproduce that cryptographic hash. Mock only that signed asset's
    # hash read in these tests; production script never substitutes identities.
    original_file_sha=gc27.file_sha
    synthetic_flowers_digest=original_file_sha(flowers)
    pinned_flowers=snap['photo_variants']['DEFAULT_ASSET']['sha256']
    monkeypatch.setattr(gc27,'file_sha',lambda p: pinned_flowers if Path(p)==flowers and original_file_sha(flowers)==synthetic_flowers_digest else original_file_sha(p))
    manifest=tmp_path/'private_resources.yaml'
    manifest.write_text(yaml.safe_dump({'schema_version':'gdl_greeting_card_private_resource_manifest_v0_1',
        'resources':{
          snap['resource_ids']['reference_pdf']:{'path':str(ref),'sha256':gc27.file_sha(ref)},
          snap['resource_ids']['flowers']:{'path':str(flowers),'sha256':gc27.file_sha(flowers)}
        }}),encoding='utf8')
    workspace=tmp_path/'client/_forprint_automation';(workspace/'input').mkdir(parents=True)
    (workspace/'output').mkdir()
    archive=workspace/'input/gdl_reviewed_synthetic.zip';build_zip(archive)
    monkeypatch.setattr(gc26,'client_workspace',lambda name:workspace)
    monkeypatch.setattr(gc23,'catalog',lambda:snap)
    lab=tmp_path/'lab';lab.mkdir();(lab/'tmp').mkdir()
    monkeypatch.setattr(gc27,'ROOT',lab)
    return gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab


def test_static_scene_template_is_one_page_native_and_private():
    text=gc27.TEMPLATE.read_text(encoding='utf8')
    assert 'GC27_P03_DEFAULT_FLOWERS_NATIVE_PROOF_V0_1' in text
    assert 'placed.embed()' in text and 'app.open(ai)' in text
    assert 'doc.saveAs(ai,aiOpt)' in text and 'doc.saveAs(pdf,pdfOpt)' in text
    assert 'document.exportFile(' not in text
    assert 'doc.exportFile(' in text
    assert 'doc.layers.add()' in text
    assert 'PDF import' not in text


def test_real_gdl_scripts_required_not_prepress_import():
    text=FILE.read_text()
    assert 'from app.graphic_design_lab' not in text
    assert 'gc21_native_illustrator_builder_v0_1.py' in text
    assert 'gc25_illustrator_smb_preflight_v0_1.py' in text


def test_input_is_accepted_and_all_four_default(prepared):
    gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    result=gc27.verify_handoff(archive,gc23.catalog(),gc25)
    assert result['jobs']==4 and all(j['image']=='DEFAULT_ASSET' for j in result['variants'])


def test_refuses_historical_blocked_zip(prepared):
    _,gc23,gc25,_,*rest=prepared
    archive=rest[4];staging=archive.with_name('gdl_staging.zip')
    build_zip(staging,staging=True)
    with pytest.raises(gc27.Blocked,match='ACCEPTED_HANDOFF_REQUIRED'):
        gc27.verify_handoff(staging,gc23.catalog(),gc25)


def test_refuses_tampered_handoff(prepared):
    _,gc23,gc25,_,*rest=prepared
    archive=rest[4];tampered=archive.with_name('gdl_modified.zip')
    build_zip(tampered,tainted=True)
    with pytest.raises(Exception): gc27.verify_handoff(tampered,gc23.catalog(),gc25)


def test_refuses_mixed_portrait_input(prepared):
    _,gc23,gc25,_,*rest=prepared
    archive=rest[4];mixed=archive.with_name('gdl_mixed.zip')
    build_zip(mixed,default=False)
    with pytest.raises(gc27.Blocked,match='P03_FLOWERS_ONLY_BOUNDED_PROOF'):
        gc27.verify_handoff(mixed,gc23.catalog(),gc25)


def test_p03_composition_keeps_mask_and_geometry(prepared):
    gc21,gc23,_,_,ref,flowers,manifest,*_=prepared
    scene,assets=gc27.compose_p03(ref,flowers,gc21)
    assert scene['source_reference_sha256']==gc27.file_sha(ref)
    assert scene['default_flowers_sha256']==gc27.file_sha(flowers)
    assert scene['reference_mask_present'] is True
    assert scene['source_placement_bbox_pdf_mm']==[19,32,195,268]
    assert [x['role'] for x in scene['layers']]==['P03.PAPER','P03.DEFAULT_FLOWERS','P03.FRAME']
    assert len(assets)==3
    assert scene['production_ready'] is False and scene['pdf_builder_pixel_parity_verified'] is False
    with Image.open(io.BytesIO(assets['p03_default_flowers_masked.png'])) as out:
        assert out.mode=='RGBA' and out.size == tuple(scene['source_mask_dimensions'])
        assert out.getchannel('A').getextrema()[1] < 255


def test_cannot_accept_reference_digest_drift(prepared):
    gc21,_,_,_,ref,flowers,*_=prepared
    ref.write_bytes(ref.read_bytes()+b'changed')
    with pytest.raises(gc27.Blocked,match='GC21_REFERENCE_SHA_MISMATCH'):
        gc27.compose_p03(ref,flowers,gc21)


def test_resources_manifest_sha_valid(prepared):
    gc21,gc23,_,_,ref,flowers,manifest,*_=prepared
    resolved=gc27.resource_paths(manifest,gc23.catalog(),gc23)
    assert resolved==(ref,flowers)


def test_reject_resource_sha_mismatch(prepared):
    gc21,gc23,_,_,ref,flowers,manifest,*_=prepared
    flowers.write_bytes(flowers.read_bytes()+b'changed')
    with pytest.raises(gc27.Blocked,match='PRIVATE_RESOURCE_SHA_MISMATCH'):
        gc27.resource_paths(manifest,gc23.catalog(),gc23)


def test_client_zip_path_rejects_traversal(prepared):
    *_,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    with pytest.raises(gc27.Blocked,match='PACKAGE_NAME_INVALID'):
        gc27.client_handoff('name','../not-a-zip',gc26)


def test_check_never_writes_private_output(prepared, capsys):
    gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    opts=types.SimpleNamespace(mode='check',confirm_private_prepare=False,output_name=None,
        client_name='client',package_name=archive.name,resource_manifest=manifest,source_root=None)
    before=set((lab/'tmp').iterdir());assert gc27.run(opts,deps=(gc21,gc23,gc25,gc26))==0
    assert set((lab/'tmp').iterdir())==before
    text=capsys.readouterr().out
    assert 'GDL_GC27_P03=SOURCE_CHECK_PASS_NO_FILES_WRITTEN' in text
    assert 'Нейтральне привітання' not in text


def test_prepare_requires_confirmation(prepared):
    gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    opts=types.SimpleNamespace(mode='prepare',confirm_private_prepare=False,output_name='gc27_proof_one',
        client_name='client',package_name=archive.name,resource_manifest=manifest,source_root=None)
    with pytest.raises(gc27.Blocked,match='PREPARE_CONFIRMATION_REQUIRED'):
        gc27.run(opts,deps=(gc21,gc23,gc25,gc26))


def test_prepared_private_package_no_overwrite(prepared):
    gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    opts=types.SimpleNamespace(mode='prepare',confirm_private_prepare=True,output_name='gc27_proof_one',
        client_name='client',package_name=archive.name,resource_manifest=manifest,source_root=None)
    assert gc27.run(opts,deps=(gc21,gc23,gc25,gc26))==0
    out=lab/'tmp/gc27_proof_one'
    assert (out/'run_gc27_p03_in_illustrator.jsx').is_file()
    assert len(list((out/'assets').iterdir()))==3
    assert (out/'scene_manifest.json').is_file()
    assert (out/'README_PRIVATE.txt').is_file()
    assert not (out/'out').exists()
    with pytest.raises(gc27.Blocked,match='OUTPUT_ALREADY_EXISTS'):
        gc27.run(opts,deps=(gc21,gc23,gc25,gc26))


def test_no_arbitrary_destination_name(prepared):
    gc21,gc23,gc25,gc26,ref,flowers,manifest,archive,workspace,lab=prepared
    opts=types.SimpleNamespace(mode='prepare',confirm_private_prepare=True,output_name='../bad',
        client_name='client',package_name=archive.name,resource_manifest=manifest,source_root=None)
    with pytest.raises(gc27.Blocked,match='OUTPUT_NAME_INVALID'):
        gc27.run(opts,deps=(gc21,gc23,gc25,gc26))


def test_relative_resource_paths_require_explicit_source_root(prepared, tmp_path):
    gc21,gc23,_,_,ref,flowers,manifest,*_=prepared
    relative_root=tmp_path
    data=yaml.safe_load(manifest.read_text())
    for key in data['resources']:
        data['resources'][key]['path']=Path(data['resources'][key]['path']).name
    relative_manifest=tmp_path/'relative_manifest.yaml'
    relative_manifest.write_text(yaml.safe_dump(data))
    with pytest.raises(gc27.Blocked,match='RELATIVE_RESOURCE_SOURCE_ROOT_REQUIRED'):
        gc27.resource_paths(relative_manifest,gc23.catalog(),gc23)
    assert gc27.resource_paths(relative_manifest,gc23.catalog(),gc23,relative_root)==(ref,flowers)


# GC27 r001 regression: resource size ceilings must be role-specific.
def test_r001_large_pinned_reference_passes_prior_50mb_boundary(tmp_path, monkeypatch):
    source=tmp_path/'large_canonical.pdf'
    with source.open('wb') as handle:
        handle.truncate(51_000_000)
    expected='a'*64
    monkeypatch.setattr(gc27, 'file_sha', lambda path: expected)
    assert gc27.pin_private_file(str(source), expected, kind='reference_pdf') == source


def test_r001_reference_ceiling_fail_closed_before_hash(tmp_path, monkeypatch):
    source=tmp_path/'oversized_reference.pdf'
    with source.open('wb') as handle:
        handle.truncate(gc27.MAX_REFERENCE_PDF_BYTES+1)
    monkeypatch.setattr(gc27, 'file_sha', lambda path: pytest.fail('hash should not run'))
    with pytest.raises(gc27.Blocked,match='PRIVATE_REFERENCE_PDF_TOO_LARGE'):
        gc27.pin_private_file(str(source), 'a'*64, kind='reference_pdf')


def test_r001_flowers_ceiling_fail_closed_before_hash(tmp_path, monkeypatch):
    source=tmp_path/'oversized_flowers.png'
    with source.open('wb') as handle:
        handle.truncate(gc27.MAX_DEFAULT_FLOWERS_BYTES+1)
    monkeypatch.setattr(gc27, 'file_sha', lambda path: pytest.fail('hash should not run'))
    with pytest.raises(gc27.Blocked,match='PRIVATE_FLOWERS_IMAGE_TOO_LARGE'):
        gc27.pin_private_file(str(source), 'b'*64, kind='default_flowers')


def test_r001_large_under_limit_still_needs_pinned_sha(tmp_path):
    source=tmp_path/'valid_size_but_unpinned.pdf'
    source.write_bytes(b'not an authorized PDF')
    with pytest.raises(gc27.Blocked,match='PRIVATE_RESOURCE_SHA_MISMATCH'):
        gc27.pin_private_file(str(source), 'c'*64, kind='reference_pdf')


def test_r001_unknown_kind_and_empty_rejected(tmp_path):
    source=tmp_path/'empty.pdf'
    source.write_bytes(b'')
    with pytest.raises(gc27.Blocked,match='PRIVATE_RESOURCE_KIND_UNSUPPORTED'):
        gc27.pin_private_file(str(source), 'c'*64, kind='nonexistent')
    with pytest.raises(gc27.Blocked,match='PRIVATE_RESOURCE_EMPTY'):
        gc27.pin_private_file(str(source), 'c'*64, kind='reference_pdf')


def test_r001_oversized_dimensions_rejected_before_decode(prepared, monkeypatch):
    # Exact resource bytes are still checked on normal run; here only test pixel safety.
    gc21, _, _, _, ref, flowers, manifest, *_ = prepared
    old_open = Image.open

    class HugeImage:
        width = 100_000
        height = 100_000
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def open_checked(path, *args, **kwargs):
        if isinstance(path, (str, Path)) and Path(path) == flowers:
            return HugeImage()
        return old_open(path, *args, **kwargs)
    monkeypatch.setattr(Image, 'open', open_checked)
    with pytest.raises(gc27.Blocked, match='P03_FLOWERS_IMAGE_PIXEL_LIMIT'):
        gc27.compose_p03(ref, flowers, gc21)


# GC27 r002: keep reference-PDF placement even when deliberately over the edge.
@pytest.mark.parametrize('bbox', [
    [-24, 18, 222, 270], [19, -10, 195, 305],
    [-15, -20, 235, 325], [19, 32, 195, 268],
])
def test_r002_source_pinned_overscan_preserved(bbox):
    assert gc27.validate_p03_layer_bbox(bbox, 'P03.DEFAULT_FLOWERS') == list(map(float,bbox))


@pytest.mark.parametrize('bbox,reason', [
    ([220, 12, 280, 140], 'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL'),
    ([-500, 12, 20, 140], 'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL'),
    ([-1000, 12, 20, 140], 'P03_SOURCE_OVERSCAN_TOO_LARGE'),
    ([0, 0, float('nan'), 201], 'P03_CANONICAL_BBOX_INVALID'),
    ([0, 0, float('inf'), 201], 'P03_CANONICAL_BBOX_INVALID'),
    ([20, 30, 10, 200], 'P03_CANONICAL_BBOX_INVALID'),
    ([20, 30, 30], 'P03_CANONICAL_BBOX_INVALID'),
])
def test_r002_source_geometry_fail_closed(bbox, reason):
    with pytest.raises(gc27.Blocked, match=reason):
        gc27.validate_p03_layer_bbox(bbox,'P03.DEFAULT_FLOWERS')


def test_r002_fixed_layers_are_not_allowed_source_overscan():
    for role in ('P03.PAPER', 'P03.FRAME'):
        with pytest.raises(gc27.Blocked, match='P03_FIXED_LAYER_BBOX_INVALID'):
            gc27.validate_p03_layer_bbox([-20, 7, 209, 294], role)
        assert gc27.validate_p03_layer_bbox([-2, -2, 216, 303],role)==[-2.,-2.,216.,303.]


def test_r002_bounded_overscan_reaches_native_scene(prepared, monkeypatch):
    gc21,gc23,_,_,ref,flowers,manifest,*_=prepared
    orig = gc21.bbox_mm
    def outside_for_portrait(item):
        found = orig(item)
        if found == [19, 32, 195, 268]:
            return [-24, 32, 220, 268]
        return found
    monkeypatch.setattr(gc21,'bbox_mm',outside_for_portrait)
    scene,assets=gc27.compose_p03(ref,flowers,gc21)
    assert scene['source_placement_bbox_pdf_mm']==[-24.,32.,220.,268.]
    assert scene['layers'][1]['bbox_mm']==[-24.,32.,220.,268.]
    assert len(assets)==3
    jsx=gc27.render_jsx(scene)
    assert 'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL' in jsx
    assert 'b[0] >= 0' not in jsx


def test_r002_illustrator_and_python_overscan_gates_mirror():
    contents=gc27.TEMPLATE.read_text()
    assert 'b[2]-b[0] <= 4*214' in contents
    assert 'b[3]-b[1] <= 4*301' in contents
    assert 'overlapW*overlapH >= 0.10*214*301' in contents
    assert 'b[0] >= -5' in contents
    assert gc27.P03_MAX_SOURCE_SCALE==4.0
    assert gc27.P03_MIN_VISIBLE_ARTBOARD_FRACTION==0.10
    assert gc27.P03_FIXED_LAYER_BLEED_TOLERANCE_MM==5.0
