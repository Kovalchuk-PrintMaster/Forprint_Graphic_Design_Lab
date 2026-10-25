"""GC24 guarded handoff tests: fake private bytes, no Illustrator/Windows."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT/'scripts/graphic_design_lab/greeting_cards/gc24_guarded_native_builder_v0_1.py'
GC23_TEST = ROOT/'tests/graphic_design_lab/test_gc23_prepress_variant_contract_v0_1.py'

def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    sys.modules[name]=result
    spec.loader.exec_module(result)
    return result

mod=load(RUNNER,'gc24_test_runner')
fixtures=load(GC23_TEST,'gc24_gc23_test_fixture')
gc23=fixtures.mod
_active_snapshot = None

@pytest.fixture(autouse=True)
def synthetic_catalog_only_for_gc24_tests(monkeypatch):
    global _active_snapshot
    _active_snapshot = None
    original=gc23.catalog
    monkeypatch.setattr(gc23,'catalog',lambda path=None: _active_snapshot if _active_snapshot is not None else original())


def make_input(tmp_path,**variants):
    global _active_snapshot
    data = fixtures.synthetic_job(tmp_path,**variants)
    _active_snapshot=data[0]
    return data


def args(cfg,root,assets,*, mode='check', confirm=False, name=None):
    return argparse.Namespace(mode=mode,inputs_config=cfg,source_root=root,
            gc19_assets_dir=assets[0],gc20_scene_dir=assets[1],
            output_name=name,confirm_private_prepare=mode=='prepare',
            confirm_reviewed_real_inputs=confirm)


def test_approved_input_unpinned_to_historical_gc09b(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    result,digests=mod.real_input_preflight(cfg,root,gc23)
    assert result['jobs'][0]['front_family']=='STANDARD'
    assert set(digests)=={'bundle','resource_manifest','artifact_manifest'}
    assert all(len(x)==64 for x in digests.values())
    assert not mod.FORBIDDEN_GC09B_INPUT_SHA.intersection(digests.values())


def test_legacy_gc09b_path_rejected_even_if_new_contents(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    folder=root/mod.LEGACY_DIR
    folder.mkdir()
    bad=folder/'new_input.json'
    bad.write_bytes(cfg.read_bytes())
    with pytest.raises(mod.GC24Blocked,match='GC09B_SANITIZED_INPUT_PATH_BLOCKED'):
        mod.real_input_preflight(bad,root,gc23)


def test_explicitly_selected_legacy_sha_rejected(tmp_path,monkeypatch):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    input_files=json.loads(cfg.read_text())
    actual=mod.sha256_file(Path(input_files['bundle']))
    monkeypatch.setattr(mod,'FORBIDDEN_GC09B_INPUT_SHA',frozenset({actual}))
    with pytest.raises(mod.GC24Blocked,match='GC09B_SANITIZED_INPUT_SHA_BLOCKED'):
        mod.real_input_preflight(cfg,root,gc23)


def test_sanitized_greeting_rejected_before_renderer(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    bundle=root/'bundle.yaml'
    data=yaml.safe_load(bundle.read_text())
    data['jobs'][0]['structured_greeting_data']['greeting_text']='Sanitized birthday greeting.'
    data['provenance_manifest']['bundle_sha256']=gc23.canonical_bundle_sha(data)
    bundle.write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf8')
    with pytest.raises(gc23.GateError,match='GREETING_TEXT_SANITIZED_OR_PLACEHOLDER'):
        mod.real_input_preflight(cfg,root,gc23)


@pytest.mark.parametrize('changes,code',[({'family':'RECIPIENT_BRANDING_OVERLAY'},'GC21_FRONT_VARIANT_NOT_IMPLEMENTED'),
    ({'mode':'DEFAULT_ASSET'},'GC21_PHOTO_VARIANT_NOT_IMPLEMENTED'),
    ({'variant':'GRIGO'},'GC21_SENDER_VARIANT_NOT_IMPLEMENTED'),
    ({'variant':'DUAL_GRIGO_HERASYMENKO'},'VARIANT_RUNTIME_GATE_REQUIRED'),
    ({'family':'BILINGUAL_OCCASION'},'VARIANT_RUNTIME_GATE_REQUIRED')])
def test_not_implemented_branch_remains_closed(tmp_path,changes,code):
    snap,cfg,root,job,_=make_input(tmp_path,**changes)
    with pytest.raises(mod.GC24Blocked,match=code):
        mod.real_input_preflight(cfg,root,gc23)


def test_title_not_implemented_rejected(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    bundle=root/'bundle.yaml'
    data=yaml.safe_load(bundle.read_text())
    data['jobs'][0]['builder_v1']['front']['occasion']['display_text']='Привітання з Ювілеєм!'
    data['provenance_manifest']['bundle_sha256']=gc23.canonical_bundle_sha(data)
    bundle.write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf8')
    with pytest.raises(mod.GC24Blocked,match='GC21_OCCASION_VARIANT_NOT_IMPLEMENTED'):
        mod.real_input_preflight(cfg,root,gc23)


def test_preflight_is_read_only(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    mod.real_input_preflight(cfg,root,gc23)
    after={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    assert after==before


def test_prepare_requires_both_confirmations(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    a=args(cfg,root,(tmp_path/'a',tmp_path/'b'),mode='prepare',name='real_sample')
    with pytest.raises(mod.GC24Blocked,match='REAL_INPUT_REVIEW_CONFIRMATION_REQUIRED'):
        mod.run(a,gc23=gc23,gc21=object())


def test_check_rejects_prepare_confirmation(tmp_path):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    a=args(cfg,root,(tmp_path/'a',tmp_path/'b'),confirm=True)
    with pytest.raises(mod.GC24Blocked,match='REAL_INPUT_REVIEW_CONFIRMATION_REQUIRED'):
        mod.run(a,gc23=gc23,gc21=object())


class FakeNative:
    PILOT_HASHES={}
    def __init__(self):
        self.calls=[]
    def make_scene(self,cfg,root,watermark,p02):
        self.calls.append('scene')
        return {'job_count':1,'front_family':'STANDARD','inside_image_mode':'PORTRAIT',
                'sender_variant':'HERASYMENKO','source_hashes':dict(self.PILOT_HASHES),
                'layers':[{'role':str(i)} for i in range(12)]}, {str(i):b'x' for i in range(12)}
    def render_jsx(self,scene):
        self.calls.append('jsx')
        return 'TEST_JSX'
    def prepare(self,name,scene,blobs,jsx):
        self.calls.append('prepare')
        return mod.ROOT/'tmp'/name


def test_check_dynamic_hash_and_no_write(tmp_path,monkeypatch,capsys):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    a,b=tmp_path/'tmp/a',tmp_path/'tmp/b'
    a.mkdir(parents=True);b.mkdir()
    fake=FakeNative()
    rc=mod.run(args(cfg,root,(a,b)),gc23=gc23,gc21=fake)
    assert rc==0 and fake.calls==['scene','jsx']
    assert set(fake.PILOT_HASHES)=={'bundle','resource_manifest','artifact_manifest'}
    assert 'CUSTOMER_TEXT_PRINTED=false' in capsys.readouterr().out


def test_prepare_requires_explicit_confirm_and_only_private_output(tmp_path,monkeypatch,capsys):
    snap,cfg,root,job,_=make_input(tmp_path,variant='HERASYMENKO')
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    a,b=tmp_path/'tmp/a',tmp_path/'tmp/b'
    a.mkdir(parents=True);b.mkdir()
    fake=FakeNative()
    rc=mod.run(args(cfg,root,(a,b),mode='prepare',confirm=True,name='gc24_real_001'),
               gc23=gc23,gc21=fake)
    assert rc==0 and fake.calls==['scene','jsx','prepare']
    assert 'GDL_GC24_NATIVE=PREPARED_PRIVATE_VISUAL_REVIEW_REQUIRED' in capsys.readouterr().out


def test_gate_does_not_import_prepress_at_runtime():
    content=RUNNER.read_text()
    assert 'from app.graphic_design_lab' not in content
    assert 'FORBIDDEN_GC09B_INPUT_SHA' in content
    assert "GC23_PATH =" in content
    assert "gc21.PILOT_HASHES = dict(digests)" in content
