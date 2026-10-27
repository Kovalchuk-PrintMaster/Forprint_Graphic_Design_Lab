"""TS r009 source-audit-only role binding; no AI runtime verification or authority."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
HTML=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'


def audit():
    reg=json.loads(REG.read_text('utf8'))
    x=reg['native_source_crosswalk']
    return reg,x,x['elements']


def test_all_passports_have_source_status():
    reg,x,els=audit()
    assert x['status']=='SOURCE_AUDIT_NON_AUTHORIZING'
    assert x['runtime_result_supplied'] is False
    assert x['native_artifact_inspected'] is False
    assert x['automatic_approval'] is False
    assert len(els)==20
    assert set(els)==set(reg['element_passports'])
    for row in els.values():
        assert row['runtime_evidence']=='NOT_PROVIDED_NOT_ATTESTED'
        assert row['source_scope']=='SOURCE_ONLY_NOT_EXECUTED'
        assert isinstance(row['finding_ua'],str) and len(row['finding_ua'])>25


def test_code_anchors_pinned_if_available():
    _,_,els=audit()
    for row in els.values():
        for anchor in row['code_anchors']:
            path=ROOT/anchor['path']
            assert not path.is_symlink()
            assert isinstance(anchor['sha256'],str) and len(anchor['sha256'])==64
            assert isinstance(anchor['line'],int) and anchor['line']>0
            if path.is_file():
                assert hashlib.sha256(path.read_bytes()).hexdigest()==anchor['sha256']
                lines=path.read_text('utf8').splitlines()
                assert anchor['token'] in lines[anchor['line']-1]


def test_ui_guides_not_claimed_as_native_layers():
    _,_,els=audit()
    for p in ['P01','P02','P03','P04']:
        row=els[p+'-900']
        assert row['relation']=='UI_GUIDE_ONLY'
        assert row['candidate_roles']==[] and row['code_anchors']==[]


def test_p03_clip_not_claimed_independent_native_layer():
    _,_,els=audit()
    row=els['P03-030']
    assert row['relation']=='NESTED_PATH_NOT_LAYER'
    assert 'P03-030.CLIP_SHAPE' in row['candidate_roles'][0]
    assert 'прямокутний' in row['finding_ua']
    assert els['P03-020']['relation']=='MULTIPLE_BRANCH_CANDIDATES'


def test_live_text_and_signature_separated():
    _,_,els=audit()
    assert els['P04-020']['relation']=='NAME_ALIAS_LIVE_TEXT'
    assert els['P04-025']['relation']=='NAME_ALIAS_LIVE_TEXT'
    assert els['P04-030']['relation']=='DIRECT_SOURCE_ROLE'


def test_ui_and_legacy_passports_retained():
    reg,_,_=audit()
    txt=HTML.read_text('utf8')
    assert 'const MODEL = /*__TS_FULL_MODEL__*/' in txt
    assert txt.count('MODEL.native_source_crosswalk')==1
    assert 'binding.runtime_evidence' in txt
    assert len(reg['pages'])==4
    assert all('native_binding' in row and row['native_binding']=='NOT_ATTESTED_IN_TEMPLATE_STUDIO' for row in reg['element_passports'].values())
    assert reg['authority']['native_illustrator_render_enabled'] is False
