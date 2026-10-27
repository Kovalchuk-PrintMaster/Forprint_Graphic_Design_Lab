"""TS r008: source-honest element passports. No renderer or approval capability."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT/'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
HTML = ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
PUBLISHER = ROOT/'scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py'

def source():
    return json.loads(REGISTRY.read_text('utf-8'))

def test_complete_one_to_one_passports():
    m = source()
    expected = {e['id']: e for p in m['pages'] for e in p['elements']}
    assert len(expected) == 20
    assert set(m['element_passports']) == set(expected)
    for key, record in m['element_passports'].items():
        assert record['expected_native_layer'] == expected[key]['layer']
        assert record['native_binding'] == 'NOT_ATTESTED_IN_TEMPLATE_STUDIO'
        assert record['authority'] == 'OPERATOR_REFERENCE_ONLY_NO_EXECUTION'
        for field in ('source_anchor', 'next_verification', 'evidence_state'):
            assert isinstance(record[field],str) and record[field].strip()

def test_claims_are_source_bounded():
    m=source()['element_passports']
    assert m['P01-020']['evidence_state'] == 'SOURCE_BBOX_VERIFIED'
    assert m['P03-030']['evidence_state'] == 'VECTOR_CONTOUR_UNPROVEN'
    assert 'clipping contour' in m['P03-030']['next_verification']
    assert m['P04-030']['evidence_state'] == 'VARIANT_SOURCE_REVIEW'
    assert 'DUAL' in m['P04-030']['next_verification']
    assert m['P02-010']['evidence_state'] == 'LOCKED_REFERENCE'

def test_html_passports_are_readonly_and_no_external_fetch():
    text=HTML.read_text('utf-8')
    assert 'Функціональний паспорт елемента' in text
    assert 'MODEL.element_passports' in text
    assert 'proof.next_verification' in text
    assert 'proof.native_binding' in text
    assert 'no_execution' not in text.lower() or 'NO_EXECUTION' in text
    assert 'fetch(' not in text and 'XMLHttpRequest' not in text
    assert text.count('/*__TS_FULL_MODEL__*/')==1
    assert text.count('/*__TS_FULL_BUILD__*/')==1

def test_html_node_syntax():
    if not shutil.which('node'):
        return
    script=HTML.read_text('utf8').split('<script>',1)[1].split('</script>',1)[0]
    for marker in ('/*__TS_INFRA__*/','/*__TS_FULL_MODEL__*/','/*__TS_FULL_IMAGES__*/','/*__TS_FULL_BUILD__*/'):
        script=script.replace(marker,'{}')
    out=subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
    assert out.returncode==0,out.stderr

def test_publisher_embedding_is_deterministic():
    spec=importlib.util.spec_from_file_location('ts008_pub',PUBLISHER)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    model=module.load_registry()
    assert set(model['element_passports'])==set(source()['element_passports'])
    imgs={k:'data:image/png;base64,YQ==' for k in ('P01','P02','P03','P04')}
    first=module.html_bytes(model,imgs,HTML.read_bytes())
    second=module.html_bytes(model,imgs,HTML.read_bytes())
    assert first==second
    assert b'OPERATOR_REFERENCE_ONLY_NO_EXECUTION' in first[0]
