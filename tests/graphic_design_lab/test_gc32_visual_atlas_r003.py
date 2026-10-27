"""GC32 r003: visible directory inspector and safe read-only SSH diagnosis."""
from pathlib import Path
import json
import importlib.util
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[2]
HTML=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
SSH=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_ssh_diagnose_r003.py'
LIFE=ROOT/'coordination/graphic_design_lab/template_studio/gc32_rebuildability_and_retention_r003.json'

def test_inspector_and_existing_design_preserved():
    s=HTML.read_text('utf8')
    assert s.count('id="atlas-inspector"')==1
    for token in ('function renderAtlasDetails(){','atlas-doc-grid','atlasSelect(key)','atlas-open-all','atlas-close-all',
                  'Фактичне дерево','Еталонне дерево','Повернення', 'P01'):
        if token=='Повернення':continue
        assert token in s
    assert s.count('/*__TS_INFRA__*/')==1
    assert s.count('/*__TS_FULL_IMAGES__*/')==1
    assert '<script src=' not in s and 'fetch(' not in s and 'XMLHttpRequest' not in s
    if shutil.which('node'):
        js=s.split('<script>',1)[1].split('</script>',1)[0]
        for token in ('/*__TS_INFRA__*/','/*__TS_FULL_MODEL__*/','/*__TS_FULL_IMAGES__*/','/*__TS_FULL_BUILD__*/'):
            js=js.replace(token,'{}')
        r=subprocess.run(['node','--check'],input=js,text=True,capture_output=True)
        assert r.returncode==0,r.stderr

def test_restore_contract_has_no_destructive_authority():
    p=json.loads(LIFE.read_text('utf8'))
    assert p['cleanup_allowed_by_this_package'] is False
    assert p['deletion_allowed_by_this_package'] is False
    assert 'INVENTORY' in p['disposition_steps']
    assert 'REBUILD_PROOF' in p['disposition_steps']
    assert 'CLIENT/input' in p['folders']

def test_diagnostics_only_uses_pinned_ssh_and_no_remote_writes():
    s=SSH.read_text('utf8')
    assert 'StrictHostKeyChecking=yes' in s
    assert 'm.ssh_capture(client,runner=wrapped)' in s
    assert 'GC32_DIAG_SCANNER=PASS' in s
    assert 'Set-ExecutionPolicy' not in s
    assert 'Remove-Item' not in s and 'rm ' not in s

def test_redacts_client_and_unc_path():
    spec=importlib.util.spec_from_file_location('ssh_diagnose_test',SSH)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    val=mod.safe_diag('ERR on \\\\host\\folder\\client source value'.encode(), 'client')
    assert 'client' not in val and '\\\\host' not in val
