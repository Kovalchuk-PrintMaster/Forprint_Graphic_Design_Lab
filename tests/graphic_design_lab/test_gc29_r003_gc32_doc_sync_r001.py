"""GC29 r003 / GC32 documentation synchronization; evidence and authority guard."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MAP=ROOT/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
JSX=ROOT/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.jsx'
REG=ROOT/'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'
JSX_SHA='96b0549cc21cc82f35e1648e16f4ee25cb88fd8d9333c1ad6a38b16c9b306955'
REG_SHA='4dbd15881f3af7dd9d5f0b0c24e1e8af3346dbda4f2544759f8889fb5580a75e'


def test_doc_sync_exact_source_and_conservative_status():
    data=json.loads(MAP.read_text('utf-8'))
    progress=data['progress']
    assert hashlib.sha256(JSX.read_bytes()).hexdigest()==JSX_SHA
    assert hashlib.sha256(REG.read_bytes()).hexdigest()==REG_SHA
    assert JSX_SHA in progress['gc29_p04_fit_r003']
    assert 'NO_WINDOWS_EXECUTION' in progress['gc29_p04_fit_r003']
    assert 'FOUR_JSX_SOURCE_PINS_REBOUND' in progress['gc29_r003_crosswalk_r001']
    assert 'BLOCKED_REVIEW_REQUIRED' in progress['gc30_illustrator']
    assert 'HISTORICAL_ATTEMPT_PRESERVED' in progress['gc30_illustrator']
    assert 'NO_NATIVE_AI_ATTESTATION' in progress['ts_r009_source_crosswalk']
    assert 'VALIDATION_AWAITING_S01_RECHECK' in progress['gc32_documentation_sync_r001']


def test_approved_pilot_rules_unmodified_and_no_authority_granted():
    d=json.loads(MAP.read_text('utf-8'))
    assert d['worker']['root_hint']==r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
    register=d['approval_register']
    assert set(register['authority'].values())=={False}
    assert register['p04_prepress_source_reconciliation']['state']=='PILOT_OWNER_RULES_CONFIRMED_SOURCE_PARITY_NOT_YET_IMPLEMENTED'
    # Published owner-rule snapshot is not an attestation of later dev patch.
    assert register['p04_prepress_source_reconciliation']['native_fix_status']=='NOT_IMPLEMENTED_NO_RETRY'
    assert all(not row['runtime_authority'] for group in register['groups'] for row in group['questions'])
