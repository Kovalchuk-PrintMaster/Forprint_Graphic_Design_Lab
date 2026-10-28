"""Crosswalk r009 source refresh for GC29 r003 (provenance preserved)."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / 'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
JSX = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.jsx'
OLD = '6370e060d40f4df19c6ed1770c41587228ea5dbc4693a59d05fce1d7432e619a'
NEW = '96b0549cc21cc82f35e1648e16f4ee25cb88fd8d9333c1ad6a38b16c9b306955'


def data():
    x = json.loads(REG.read_text('utf-8'))['native_source_crosswalk']
    return x, x['source_pin_reconciliation_r003']


def test_current_pinned_jsx_exact_sha():
    assert hashlib.sha256(JSX.read_bytes()).hexdigest() == NEW


def test_all_four_anchors_match_current_source_and_unique_tokens():
    x, rec = data()
    lines = JSX.read_text('utf-8').splitlines()
    assert len(rec['rebound_anchors']) == 4
    assert {v['element_id'] for v in rec['rebound_anchors']} == {'P01-030','P03-030','P04-020','P04-025'}
    for old in rec['rebound_anchors']:
        row = x['elements'][old['element_id']]
        found = [a for a in row['code_anchors'] if a['path'] == old['path'] and a['token'] == old['token']]
        assert len(found) == 1
        cur = found[0]
        assert cur['sha256'] == NEW == old['current_sha256']
        assert cur['line'] == old['current_line']
        assert cur['token'] in lines[cur['line']-1]
        assert sum(cur['token'] in l for l in lines) == 1


def test_historical_evidence_preserved_and_non_authorizing():
    x, rec = data()
    assert x['status'] == 'SOURCE_AUDIT_NON_AUTHORIZING'
    assert x['audit_head'] == rec['r009_audit_head_preserved'] == '912b05c'
    assert x['audit_archive_sha256'] == rec['r009_audit_archive_sha256_preserved']
    assert rec['source_sha256_before'] == OLD
    assert rec['source_sha256_after'] == NEW
    assert all(r['historical_sha256'] == OLD for r in rec['rebound_anchors'])
    assert [(r['element_id'],r['historical_line']) for r in rec['rebound_anchors']] == [('P01-030',66),('P03-030',56),('P04-020',76),('P04-025',94)]
    assert all(rec[k] is False for k in ('runtime_ai_attested','native_p04_fitted_in_illustrator','production_ready','approval_granted'))
    assert all(x[k] is False for k in ('runtime_result_supplied','native_artifact_inspected','automatic_approval'))


def test_unrelated_anchors_unchanged():
    x,_ = data()
    for eid,row in x['elements'].items():
        for a in row['code_anchors']:
            if a['path'].endswith('gc29_native_four_page_v0_1.jsx'):
                assert eid in {'P01-030','P03-030','P04-020','P04-025'}
            else:
                assert a['sha256'] != NEW
    assert len(x['elements']) == 20
    assert x['elements']['P03-030']['relation'] == 'NESTED_PATH_NOT_LAYER'
    assert x['elements']['P04-020']['relation'] == 'NAME_ALIAS_LIVE_TEXT'
