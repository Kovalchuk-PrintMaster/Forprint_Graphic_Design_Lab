"""GC23 source-pinned variant semantics; synthetic private assets only."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT/'scripts/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.py'
spec = importlib.util.spec_from_file_location('gc23_variant',PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)


def _write(path, contents):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(contents)
    return path


def synthetic_job(tmp_path, family='STANDARD', mode='PORTRAIT', variant='GRIGO'):
    source=tmp_path/'private'; source.mkdir()
    snap=deepcopy(mod.catalog())
    blobs={
      'reference_pdf':b'fake protected PDF bytes',
      'front_font':b'fake front font bytes',
      'greeting_font':b'fake greeting font bytes',
      'flowers':b'fake registered flowers bytes',
      'GRIGO':b'fake grigo source',
      'HERASYMENKO':b'fake herasymenko source',
      'DUAL_GRIGO_HERASYMENKO':b'fake dual source',
      'portrait':b'fake PNG bytes',
      'logo':b'fake recipient logo bytes',
    }
    manifest={'schema_version':'gdl_greeting_card_private_resource_manifest_v0_1','resources':{}}
    for label in ('reference_pdf','front_font','greeting_font','flowers'):
        p=_write(source/f'{label}.bin',blobs[label])
        snap['pinned_sha256'][label]=mod.sha_file(p)
        manifest['resources'][snap['resource_ids'][label]]={'path':str(p),'sha256':mod.sha_file(p)}
    snap['photo_variants']['DEFAULT_ASSET']['sha256']=mod.sha_file(source/'flowers.bin')
    for sig in snap['signature_variants']:
        p=_write(source/f'{sig}.bin',blobs[sig])
        sid=snap['signature_variants'][sig]['source_id']
        snap['signature_variants'][sig]['source_sha256']=mod.sha_file(p)
        # GRIGO uses the reference PDF exactly, not a new file.
        if sid == snap['resource_ids']['reference_pdf']:
            manifest['resources'][sid]={'path':str(source/'reference_pdf.bin'),'sha256':mod.sha_file(source/'reference_pdf.bin')}
            snap['signature_variants'][sig]['source_sha256']=mod.sha_file(source/'reference_pdf.bin')
        else:
            manifest['resources'][sid]={'path':str(p),'sha256':mod.sha_file(p)}
    portrait=_write(source/'portrait.png',blobs['portrait'])
    logo=_write(source/'logo.png',blobs['logo'])
    portrait_sha=mod.sha_file(portrait)
    logo_sha=mod.sha_file(logo)
    assets={'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1',
        'artifacts':{'p001':{'source_asset_id':'portrait001','sha256':portrait_sha,'path':str(portrait)},
                     'l001':{'source_asset_id':'logo001','sha256':logo_sha,'path':str(logo)}}}
    job={'job_id':'test-001','signature_selection':{'variant_id':variant},
         'structured_greeting_data':{'occasion':'BIRTHDAY','greeting_text':'Вітаємо з днем народження!'},
         'branding_selection':{'presence':'PRESENT' if family=='RECIPIENT_BRANDING_OVERLAY' else 'ABSENT',
                               'source_asset_id':'logo001' if family=='RECIPIENT_BRANDING_OVERLAY' else None},
         'exact_person_text_asset_bindings':{'portrait':{'source_asset_id':'portrait001'}},
         'builder_v1':{'schema_version':'gdl_greeting_card_builder_payload_v0_1','revision':'r001',
                      'front':{'family':family,'occasion':{'kind':'BIRTHDAY','display_text':'Привітання з нагоди Дня Народження!'}},
                      'inside_image':{'mode':'PORTRAIT','asset_id':'portrait001',
                                      'asset_sha256':portrait_sha,'accepted_artifact_ref':'p001'},
                      'sender_text':{'signature_variant_id':variant}}}
    if family=='RECIPIENT_BRANDING_OVERLAY':
        job['builder_v1']['front']['recipient_branding']={
            'asset_id':'logo001','asset_sha256':logo_sha,'accepted_artifact_ref':'l001'}
        job['exact_person_text_asset_bindings']['recipient_branding']={'source_asset_id':'logo001'}
    if mode=='DEFAULT_ASSET':
        job['builder_v1']['inside_image']={'mode':'DEFAULT_ASSET','asset_id':'flowers.default.v1',
            'asset_sha256':mod.sha_file(source/'flowers.bin'),'accepted_artifact_ref':None}
        job['exact_person_text_asset_bindings']['portrait']={'source_asset_id':'flowers.default.v1'}
    job['accepted_visual_assets']=[{
        'acceptance_basis':'SOURCE_ASSET_OPERATOR_REVIEW_PASS',
        'artifact_ref':'p001' if mode=='PORTRAIT' else None,
        'source_asset_id':job['builder_v1']['inside_image']['asset_id'],
        'provenance_sha256':job['builder_v1']['inside_image']['asset_sha256']
    }]
    bundle={'jobs':[job], 'provenance_manifest':{'algorithm':'sha256_canonical_json_v0_1','bundle_sha256':''}}
    bundle['provenance_manifest']['bundle_sha256']=mod.canonical_bundle_sha(bundle)
    config={}
    for name,data in (('bundle',bundle),('resource_manifest',manifest),('artifact_manifest',assets)):
        path=source/(name+'.yaml')
        path.write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf8')
        config[name]=str(path)
    cfg=source/'inputs.json';cfg.write_text(json.dumps(config),encoding='utf8')
    return snap,cfg,source,job,assets


def test_contract_snapshot_readable():
    snap=mod.catalog()
    assert snap['source_closed_commit'].startswith('b26cce19')
    assert len(snap['source_file_digests'])==34
    assert snap['p04_greeting_bbox_pdf_mm']==[32,32,182,212]
    assert not snap['authorities']['illustrator_parity_proven']


def test_three_front_families_and_actual_positions():
    families=mod.catalog()['front_variants']
    assert set(families)=={'STANDARD','RECIPIENT_BRANDING_OVERLAY','BILINGUAL_OCCASION'}
    assert families['STANDARD']['sender_logo_bbox_mm']==[64.5,59.5,149.5,144.5]
    assert families['RECIPIENT_BRANDING_OVERLAY']['sender_logo_bbox_mm']==[69,39,145,115]
    assert families['BILINGUAL_OCCASION']['sender_logo_bbox_mm']==[74,112,140,178]


def test_two_photo_modes_and_three_sender_variants():
    snap=mod.catalog()
    assert set(snap['photo_variants'])=={'PORTRAIT','DEFAULT_ASSET'}
    assert set(snap['signature_variants'])=={'GRIGO','HERASYMENKO','DUAL_GRIGO_HERASYMENKO'}
    assert snap['signature_variants']['DUAL_GRIGO_HERASYMENKO']['runtime']=='CANDIDATE_GATED_IN_BUILDER'


@pytest.mark.parametrize('family,mode,signature',[
    ('STANDARD','PORTRAIT','GRIGO'),
    ('STANDARD','DEFAULT_ASSET','HERASYMENKO'),
    ('RECIPIENT_BRANDING_OVERLAY','PORTRAIT','GRIGO'),
    ('STANDARD','PORTRAIT','HERASYMENKO'),
])
def test_supported_semantic_plans(tmp_path,family,mode,signature):
    snap,cfg,root,job,assets=synthetic_job(tmp_path,family,mode,signature)
    result=mod.projection(cfg,root,snap)
    assert len(result['jobs'])==1
    assert result['jobs'][0]['gate']=='CONTRACT_VALID_RUNTIME_FAMILY'
    assert not result['native_illustrator_parity_verified']
    assert not result['production_ready']
    assert not result['client_published']
    assert 'Вітаємо' not in json.dumps(result,ensure_ascii=False)
    assert str(root) not in json.dumps(result,ensure_ascii=False)


@pytest.mark.parametrize('family,variant',[
    ('BILINGUAL_OCCASION','GRIGO'),
    ('STANDARD','DUAL_GRIGO_HERASYMENKO'),
])
def test_catalog_only_variants_not_silently_enabled(tmp_path,family,variant):
    snap,cfg,root,job,assets=synthetic_job(tmp_path,family=family,variant=variant)
    plan=mod.projection(cfg,root,snap)['jobs'][0]
    assert plan['gate']=='CONTRACT_VALID_SEPARATE_SOURCE_RUNTIME_REVIEW'
    assert plan['illustrator_execution_authorized'] is False


def test_real_gc21_placeholder_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    job['structured_greeting_data']['greeting_text']='Sanitized birthday greeting.'
    bundle=root/'bundle.yaml'
    data=mod.load_mapping(bundle)
    data['jobs']=[job]
    data['provenance_manifest']['bundle_sha256']=mod.canonical_bundle_sha(data)
    bundle.write_text(yaml.safe_dump(data),encoding='utf8')
    with pytest.raises(mod.GateError,match='GREETING_TEXT_SANITIZED_OR_PLACEHOLDER'):
        mod.projection(cfg,root,snap)


def test_signature_mismatch_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    job['signature_selection']['variant_id']='HERASYMENKO'
    data=mod.load_mapping(root/'bundle.yaml')
    data['jobs']=[job]
    data['provenance_manifest']['bundle_sha256']=mod.canonical_bundle_sha(data)
    (root/'bundle.yaml').write_text(yaml.safe_dump(data),encoding='utf8')
    with pytest.raises(mod.GateError,match='SIGNATURE_SELECTION_MISMATCH'):
        mod.projection(cfg,root,snap)


def test_changed_portrait_file_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    (root/'portrait.png').write_bytes(b'changed after acceptance')
    with pytest.raises(mod.GateError,match='ARTIFACT_FILE_SHA_MISMATCH'):
        mod.projection(cfg,root,snap)


def test_missing_overlay_logo_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path,family='RECIPIENT_BRANDING_OVERLAY')
    (root/'logo.png').unlink()
    with pytest.raises(mod.GateError,match='ARTIFACT_FILE_MISSING'):
        mod.projection(cfg,root,snap)


def test_private_font_sha_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    (root/'front_font.bin').write_bytes(b'changed')
    with pytest.raises(mod.GateError,match='PRIVATE_RESOURCE_SHA_MISMATCH'):
        mod.projection(cfg,root,snap)


def test_source_fingerprints_checked_fail_closed(tmp_path):
    snap=mod.catalog()
    snap['source_file_digests']={'one.yaml':sha256(b'x: 1\n').hexdigest()}
    _write(tmp_path/'one.yaml',b'x: 2\n')
    with pytest.raises(mod.GateError,match='PINNED_SOURCE_MISMATCH'):
        mod.verify_source(tmp_path,snap)


def test_catalog_does_not_activate_authority(tmp_path):
    snap=mod.catalog()
    assert not snap['authorities']['gdl_can_generate_production']
    assert not snap['authorities']['dual_runtime_general_authorized']
    assert not snap['authorities']['bilingual_runtime_general_authorized']


def test_pinned_source_in_sync_if_fixture_available():
    import os
    p=os.environ.get('GC23_PREPRESS_ROOT')
    if not p:
        pytest.skip('Set GC23_PREPRESS_ROOT to live Prepress Hub for exact SHA audit')
    assert mod.verify_source(Path(p),mod.catalog())==34


def test_tampered_bundle_provenance_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    doc=mod.load_mapping(root/'bundle.yaml')
    doc['jobs'][0]['structured_greeting_data']['greeting_text']='Заміна без зміни provenance'
    (root/'bundle.yaml').write_text(yaml.safe_dump(doc,allow_unicode=True),encoding='utf8')
    with pytest.raises(mod.GateError,match='BUNDLE_PROVENANCE_SHA_MISMATCH'):
        mod.projection(cfg,root,snap)


def test_unaccepted_portrait_blocked(tmp_path):
    snap,cfg,root,job,assets=synthetic_job(tmp_path)
    doc=mod.load_mapping(root/'bundle.yaml')
    doc['jobs'][0].pop('accepted_visual_assets')
    doc['provenance_manifest']['bundle_sha256']=mod.canonical_bundle_sha(doc)
    (root/'bundle.yaml').write_text(yaml.safe_dump(doc,allow_unicode=True),encoding='utf8')
    with pytest.raises(mod.GateError,match='ACCEPTED_VISUAL_REQUIRED'):
        mod.projection(cfg,root,snap)
