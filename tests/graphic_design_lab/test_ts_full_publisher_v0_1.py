"""Synthetic TS FULL contracts. No real client, no private PDF, no Prepress writes."""
from __future__ import annotations
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT/'scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py'
spec=importlib.util.spec_from_file_location('ts_full_v01',CLI)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

@pytest.fixture
def local_root(tmp_path):
    r=tmp_path/'testrepo'
    for p in ['coordination/graphic_design_lab/template_studio',
        'coordination/graphic_design_lab/greeting_cards',
        'scripts/graphic_design_lab/template_studio','tmp']:(r/p).mkdir(parents=True)
    (r/mod.REGISTRY.relative_to(mod.ROOT)).write_bytes(mod.REGISTRY.read_bytes())
    (r/mod.HTML_TEMPLATE.relative_to(mod.ROOT)).write_bytes(mod.HTML_TEMPLATE.read_bytes())
    (r/mod.GC23.relative_to(mod.ROOT)).write_bytes(mod.GC23.read_bytes())
    return r

def test_registry_four_pages_and_stable_ids():
    m=mod.load_registry();assert [p['id'] for p in m['pages']]==['P01','P02','P03','P04']
    ids=[e['id'] for p in m['pages'] for e in p['elements']]
    assert len(ids)==len(set(ids))

def test_variants_are_registered():
    m=mod.load_registry();assert len(m['variant_groups']['front_family']['values'])==3
    assert len(m['variant_groups']['signature']['values'])==3
    assert m['variant_groups']['signature']['values'][-1]['availability'].startswith('CANDIDATE_GATED')

def test_jubilee_is_only_conceptual():
    m=mod.load_registry();assert m['variant_groups']['occasion']['values'][1]['availability']=='CONCEPTUAL_UI_ONLY_NO_ACCEPTED_BINDING'

def test_source_geometry_bound_to_gc23():
    m=mod.load_registry();e={x['id']:x for p in m['pages'] for x in p['elements']}
    assert e['P01-020']['bbox_mm']==[64.5,59.5,149.5,144.5]
    assert e['P04-020']['bbox_mm']==[32,32,182,212]
    assert e['P03-030']['bbox_mm'] is None

def test_no_client_authority():
    m=mod.load_registry();assert m['authority']['automatic_publication_of_print'] is False
    assert m['authority']['native_illustrator_render_enabled'] is False
    assert m['authority']['edit_proposal_is_authority'] is False

def test_unknown_page_rejected(local_root):
    path=local_root/mod.REGISTRY.relative_to(mod.ROOT)
    doc=json.loads(path.read_text());doc['pages'][3]['id']='P05';path.write_text(json.dumps(doc))
    with pytest.raises(mod.Blocked,match='PAGE_SET_CHANGED'):mod.load_registry(local_root)

def test_duplicate_id_rejected(local_root):
    path=local_root/mod.REGISTRY.relative_to(mod.ROOT)
    doc=json.loads(path.read_text());doc['pages'][2]['elements'][1]['id']='P01-020';path.write_text(json.dumps(doc))
    with pytest.raises(mod.Blocked,match='DUPLICATE_ELEMENT_IDS'):mod.load_registry(local_root)

def test_source_geometry_drift_rejected(local_root):
    path=local_root/mod.REGISTRY.relative_to(mod.ROOT)
    doc=json.loads(path.read_text());doc['pages'][0]['elements'][2]['bbox_mm']=[0,0,100,100];path.write_text(json.dumps(doc))
    with pytest.raises(mod.Blocked,match='P01_LOGO_GEOMETRY_DRIFT'):mod.load_registry(local_root)

def test_html_self_contained_and_no_fetch():
    s=mod.HTML_TEMPLATE.read_text();assert s.count('/*__TS_FULL_MODEL__*/')==1
    assert 'fetch(' not in s and 'XMLHttpRequest' not in s
    assert 'file://' in mod.__doc__ or 'SMB' in mod.__doc__

def test_html_escape_script_in_model():
    model=mod.load_registry();model['studio_id']='bad</script><script>attack()'
    raw,build_id=mod.html_bytes(model,{'P01':'data:image/png;base64,YQ=='},mod.HTML_TEMPLATE.read_bytes())
    assert b'bad</script><script>' not in raw and b'bad\\u003c/script\\u003e' in raw
    assert build_id.startswith('tsfull-')

def test_html_deterministic():
    a=mod.html_bytes(mod.load_registry(),{'P01':'data:image/png;base64,YQ=='},mod.HTML_TEMPLATE.read_bytes())
    b=mod.html_bytes(mod.load_registry(),{'P01':'data:image/png;base64,YQ=='},mod.HTML_TEMPLATE.read_bytes())
    assert a==b

def fake_build(tmp_path):
    b=tmp_path/'staging';b.mkdir()
    src=mod.HTML_TEMPLATE.read_bytes()
    raw,id=mod.html_bytes(mod.load_registry(),{'P01':'data:image/png;base64,YQ=='},src)
    (b/'index.html').write_bytes(raw)
    (b/'build_manifest.json').write_text(json.dumps({'schema_version':'forprint_ts_full_build_v0_1','build_id':id,'sha256':mod.digest(raw),'source_sha256':mod.SOURCE_SHA}))
    return b,raw,id

def fake_share(tmp_path):
    root=tmp_path/'SMB'; ws=root/'Вікторія'/'_forprint_automation';(ws/'input').mkdir(parents=True);(ws/'output').mkdir()
    (ws/'input'/'accepted.zip').write_bytes(b'do not alter')
    return root,ws

def test_build_manifest_tamper_rejected(tmp_path):
    b,raw,id=fake_build(tmp_path);(b/'index.html').write_bytes(raw+b'changed')
    with pytest.raises(mod.Blocked,match='BUILD_SHA_MISMATCH'):mod.read_build(b)

def test_publish_requires_confirmation(tmp_path):
    b,_,_=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    with pytest.raises(mod.Blocked,match='EXPLICIT_PUBLICATION'):mod.publish(b,'Вікторія',r,False)
    assert not (ws/'template_studio').exists()

def test_publish_and_verify_client_input_unchanged(tmp_path):
    b,raw,id=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    portal,rec=mod.publish(b,'Вікторія',r,True)
    assert rec['build_id']==id and (portal/'index.html').read_bytes()==raw
    assert mod.verify_current(portal)==rec
    assert (ws/'input'/'accepted.zip').read_bytes()==b'do not alter'
    assert not any((ws/'output').iterdir())
    assert (portal/'releases'/(id+'.html')).read_bytes()==raw

def test_publish_repeated_identical_idempotent(tmp_path):
    b,raw,id=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    mod.publish(b,'Вікторія',r,True);mod.publish(b,'Вікторія',r,True)
    assert (ws/'template_studio'/'index.html').read_bytes()==raw

def test_publish_refuses_modified_index(tmp_path):
    b,raw,id=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    portal,_=mod.publish(b,'Вікторія',r,True)
    (portal/'index.html').write_bytes(b'edited')
    with pytest.raises(mod.Blocked,match='PORTAL_INDEX_FOREIGN_OR_MODIFIED'):mod.publish(b,'Вікторія',r,True)
    assert (portal/'index.html').read_bytes()==b'edited'

def test_existing_foreign_index_not_overwritten(tmp_path):
    b,_,_=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    portal=ws/'template_studio';portal.mkdir();(portal/'index.html').write_text('foreign')
    with pytest.raises(mod.Blocked,match='PORTAL_OUTPUT_INCOMPLETE'):mod.publish(b,'Вікторія',r,True)
    assert (portal/'index.html').read_text()=='foreign'

def test_client_symlink_rejected(tmp_path):
    b,_,_=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    (ws/'input').rename(ws/'actual-input')
    (ws/'input').symlink_to(ws/'actual-input',target_is_directory=True)
    with pytest.raises(mod.Blocked,match='CLIENT_WORKSPACE_MISSING_OR_SYMLINK'):mod.publish(b,'Вікторія',r,True)

def test_client_traversal_rejected(tmp_path):
    r,ws=fake_share(tmp_path)
    with pytest.raises(mod.Blocked,match='CLIENT_NAME_INVALID'):mod.workspace('../Вікторія',r)

def test_release_conflict_rejected(tmp_path):
    b,raw,id=fake_build(tmp_path);r,ws=fake_share(tmp_path)
    portal,_=mod.publish(b,'Вікторія',r,True)
    rel=portal/'releases'/(id+'.html');rel.write_bytes(b'other')
    with pytest.raises(mod.Blocked,match='PORTAL_RELEASE_MISMATCH'):mod.publish(b,'Вікторія',r,True)

def test_client_publish_name_is_separate_from_input_output():
    assert mod.target_portal(Path('/private/_forprint_automation')).name=='template_studio'
