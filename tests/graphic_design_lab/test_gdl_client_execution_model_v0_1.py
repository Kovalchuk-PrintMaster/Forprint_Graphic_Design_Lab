import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
INFRA=ROOT/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
HTML=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
DOC=ROOT/'coordination/graphic_design_lab/template_studio/gdl_client_entry_worker_lifecycle_v0_1.md'

@pytest.fixture
def model():
    return json.loads(INFRA.read_text(encoding='utf8'))['execution_model']

def test_schema_and_server_authority(model):
    assert model['schema_version']=='forprint_gdl_client_entry_worker_lifecycle_v0_1'
    assert model['normative_order'][:2]==['SERVER_GDL_AUTHORITY','CLIENT_SMB_OPERATIONAL_ENTRY']
    owners={x['id']:x['kind'] for x in model['role_ownership']}
    assert owners['s01']=='SOURCE_OF_TRUTH'
    assert owners['client_smb']=='OPERATIONAL_ENTRY_POINT'
    assert owners['workstation']=='REGENERABLE_EXECUTOR'

def test_two_branches_are_distinct(model):
    paths={p['id']:p for p in model['paths']}
    assert set(paths)=={'ready','bootstrap'}
    assert [s['id'] for s in paths['ready']['steps']]==[f'A{i}' for i in range(1,8)]
    assert [s['id'] for s in paths['bootstrap']['steps']]==[f'B{i}' for i in range(1,7)]
    assert 'PLANNED' in paths['bootstrap']['status'] or 'PROPOSED' in paths['bootstrap']['status']

def test_sources_do_not_pretend_two_flows_implemented(model):
    a,b=model['paths']
    assert a['steps'][-2]['status']=='NOT_EXECUTED'
    assert b['steps'][2]['status']=='NOT_IMPLEMENTED'
    assert b['steps'][4]['status']=='NOT_IMPLEMENTED'
    assert all(value is False for value in model['authority'].values())

def test_pilot_stage_but_no_native_output(model):
    evidence=model['pilot_evidence']
    assert evidence['reported_stage']=='STAGED_HASH_VERIFIED_NON_AUTHORIZING'
    assert evidence['files_verified']==16 and evidence['assets_verified']==12
    assert evidence['native_out_at_check']=='ABSENT'

def test_worker_reusable_and_single_root(model):
    p=model['workstation_layout']
    assert p['pilot_root']==r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
    assert set(p['existing_dirs'])=={'Worker/','cache/','config/','jobs/','logs/','runtime/'}
    assert p['worker_is_not_truth'] is True
    assert 'config/worker_config.json' in p['do_not_touch']

def test_no_windows_smb_dependency(model):
    assert 'NO_SMB_ACCESS_REQUIRED_FROM_WINDOWS_SSH_CONTEXT' in model['shared_boundaries']
    assert 'WINDOWS SSH' in model['launcher']['network_note'] or 'Windows SSH' in model['launcher']['network_note']

def test_html_both_routes_present():
    html=HTML.read_text(encoding='utf8')
    for s in ['exec-ready','exec-bootstrap','exec-flow','renderExecutionModel()',
              'execution_model','aria-pressed','Конвеєр і контроль']:
        assert s in html
    assert html.count('/*__TS_INFRA__*/')==1
    assert 'fetch(' not in html

def test_document_accurate_milestones():
    doc=DOC.read_text(encoding='utf8')
    for s in ['s01', 'SMB', '16 файлів', '12 assets', 'NOT_EXECUTED',
              'PLANNED_NOT_IMPLEMENTED','Make/CLI', 'mermaid']:
        assert s in doc
    assert 'сервіс уже реалізовано для всіх робочих станцій' not in doc

def test_old_workflow_updated():
    infra=json.loads(INFRA.read_text(encoding='utf8'))
    assert infra['schema_version']=='forprint_gdl_gc32_infrastructure_map_v0_1'
    assert 'PollOnce' not in json.dumps(infra['workflow'])
    assert infra['workflow'][0]['title']=='Клієнтська точка входу (SMB)'
    assert 'R002C_EXACT_DEG_PILOT' in infra['progress']['gc30_staging']
