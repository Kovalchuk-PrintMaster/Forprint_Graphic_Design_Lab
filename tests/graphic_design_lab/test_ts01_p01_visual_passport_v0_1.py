"""Synthetic tests for TS01. No client's private PDF or SMB share required."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import fitz
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/graphic_design_lab/template_studio/ts01_p01_visual_passport_v0_1.py'
REGISTRY = ROOT / 'coordination/graphic_design_lab/template_studio/ts01_p01_standard_elements_v0_1.json'
CATALOG = ROOT / 'coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json'
spec = importlib.util.spec_from_file_location('ts01_p01', SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def catalog_fixture():
    return {
        'schema_version': 'forprint_gdl_gc23_variant_contract_v0_1',
        'physical_size_mm': [214, 301], 'trim_size_mm': [210, 297],
        'front_variants': {'STANDARD': {'sender_logo_bbox_mm': [64.5,59.5,149.5,144.5],
                                        'occasion_bbox_mm': [32,203.5,182,248]}},
        'resource_ids': {'reference_pdf': 'template.reference'},
        'pinned_sha256': {'reference_pdf': '0'*64},
    }


@pytest.fixture
def scene(tmp_path, monkeypatch):
    catalog = catalog_fixture()
    reference = tmp_path / 'ref.pdf'
    with fitz.open() as doc:
        for _ in range(4):
            doc.new_page(width=214*mod.MM, height=301*mod.MM)
        doc[0].draw_rect(fitz.Rect(5,5,250,450),color=(0.9,0.65,0.2),width=4)
        doc.save(reference)
    catalog['pinned_sha256']['reference_pdf'] = mod.file_sha(reference)
    catalog_path = tmp_path / 'gc23.json'
    catalog_path.write_text(json.dumps(catalog),encoding='utf8')
    manifest = tmp_path / 'private_resource.yaml'
    manifest.write_text(yaml.safe_dump({
        'schema_version': 'gdl_greeting_card_private_resource_manifest_v0_1',
        'resources': {'template.reference': {'path':str(reference),'sha256':mod.file_sha(reference)}}
    }),encoding='utf8')
    folder=tmp_path/'tmp';folder.mkdir()
    monkeypatch.setattr(mod,'CATALOG',catalog_path)
    monkeypatch.setattr(mod,'REGISTRY',REGISTRY)
    monkeypatch.setattr(mod,'TMP',folder)
    return catalog, reference, manifest, folder


def test_registry_source_ids():
    doc=json.loads(REGISTRY.read_text())
    assert len(doc['elements'])==5
    assert [e['id'] for e in doc['elements']]==['P01-010','P01-015','P01-020','P01-030','P01-900']
    assert doc['approval']=={'design_approved':False,'production_ready':False,'automatic_promotion':False}


def test_pinned_geometry():
    els=mod.validated_registry(mod.load_json(REGISTRY),catalog_fixture())
    assert [e for e in els if e['bbox_pdf_mm'] is not None][0]['bbox_pdf_mm']==[64.5,59.5,149.5,144.5]
    assert [e for e in els if e['bbox_pdf_mm'] is not None][1]['bbox_pdf_mm']==[32,203.5,182,248]


@pytest.mark.parametrize('element_id,key,val',[
 ('P01-020','bbox_pdf_mm',[64.5,59,149.5,144.5]),
 ('P01-010','bbox_pdf_mm',[0,0,214,301]),
 ('P01-030','geometry_status','GUESSED')
])
def test_reject_drift(element_id,key,val):
    doc=mod.load_json(REGISTRY)
    for e in doc['elements']:
        if e['id']==element_id:e[key]=val
    with pytest.raises(mod.GateError):mod.validated_registry(doc,catalog_fixture())


def test_reject_approval_escalation():
    doc=mod.load_json(REGISTRY)
    doc['approval']['production_ready']=True
    with pytest.raises(mod.GateError,match='AUTHORITY'):
        mod.validated_registry(doc,catalog_fixture())


def test_read_only_check(scene,capsys):
    _,_,manifest,folder=scene
    assert mod.main(['--mode','check','--resource-manifest',str(manifest)])==0
    assert list(folder.iterdir())==[]
    assert 'SOURCE_CHECK_PASS_READ_ONLY' in capsys.readouterr().out


def test_prepare_produces_all_outputs(scene):
    _,_,manifest,folder=scene
    name='ts01_p01_synthetic_test'
    assert mod.main(['--mode','prepare','--resource-manifest',str(manifest),
                     '--output-name',name,'--confirm-private-prepare'])==0
    out=folder/name
    assert {p.name for p in out.iterdir()}=={
        'design_view_p01.png','control_view_p01.png','control_overlay_p01.svg',
        'operator_view_p01.html','operator_change_proposal.json','result.json'
    }
    result=json.loads((out/'result.json').read_text())
    assert result['state']=='VISUAL_REFERENCE_REVIEW_REQUIRED'
    assert result['element_count']==5 and not result['illustrator_native_template_created']
    assert all(mod.file_sha(out/name)==digest for name,digest in result['artifacts_sha256'].items())
    assert 'P01-020' in (out/'operator_view_p01.html').read_text()
    assert 'P01-030' in (out/'control_overlay_p01.svg').read_text()
    assert mod.main(['--mode','prepare','--resource-manifest',str(manifest),
                     '--output-name',name,'--confirm-private-prepare'])==2


def test_expected_dimensions(scene):
    _,_,manifest,folder=scene
    assert mod.main(['--mode','prepare','--resource-manifest',str(manifest),
                     '--output-name','ts01_p01_dimensions_test','--confirm-private-prepare'])==0
    from PIL import Image
    out=folder/'ts01_p01_dimensions_test'
    with Image.open(out/'design_view_p01.png') as a, Image.open(out/'control_view_p01.png') as b:
        assert a.size==b.size
        assert abs(a.width/a.height - 214/301)<.005


@pytest.mark.parametrize('name',['../../bad','TS01_UPPER','ts01_p01_x','ts01_p01_normal/../evil','ts01_p01_hello.zip'])
def test_unsafe_output_name(scene,name):
    _,_,manifest,folder=scene
    assert mod.main(['--mode','prepare','--resource-manifest',str(manifest),
                     '--output-name',name,'--confirm-private-prepare'])==2
    assert not list(folder.iterdir())


def test_missing_confirmation(scene):
    _,_,manifest,folder=scene
    assert mod.main(['--mode','prepare','--resource-manifest',str(manifest),
                     '--output-name','ts01_p01_not_confirmed'])==2
    assert not list(folder.iterdir())


def test_digest_tampering_blocked(scene):
    _,ref,manifest,folder=scene
    ref.write_bytes(ref.read_bytes()+b'changed')
    assert mod.main(['--mode','check','--resource-manifest',str(manifest)])==2
    assert not list(folder.iterdir())


def test_no_production_commands_or_client_writes():
    src=SCRIPT.read_text()
    assert 'customer_approved' not in src and 'client_published' not in src
    assert 'ROOT / "tmp"' in src
    assert 'source_reference_pdf_sha256' in src
    assert 'illustrator_native_template_created":False' in src


def test_unverified_assets_still_pending():
    doc=json.loads(REGISTRY.read_text())
    assert doc['elements'][0]['bbox_pdf_mm'] is None
    assert doc['elements'][1]['bbox_pdf_mm'] is None
    assert 'SOURCE_EXTRACTION_REQUIRED' == doc['elements'][0]['geometry_status']
