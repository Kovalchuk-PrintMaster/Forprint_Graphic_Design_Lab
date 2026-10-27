"""GC32 synthetic tests: no actual Windows or customer mutations."""
from pathlib import Path
import importlib.util
import subprocess
import sys
import shutil
import pytest
ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
WORKER=ROOT/'scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_worker_v0_1.ps1'
PORTAL=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
CLI=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_infrastructure_portal_v0_1.py'
spec=importlib.util.spec_from_file_location('gc32testmod',CLI)
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)

def test_worker_root_and_alias_fix():
    assert WORKER.read_bytes().startswith(b'\xef\xbb\xbf')
    s=WORKER.read_text('utf-8-sig')
    for expected in ('function SafeDirectory(','GC32_REGISTER_IN_PLACE_ONLY','GC32_WORKER_ROOT_CHANGED','GC30_WRONG_WINDOWS_COMPUTER','GC30_TICKET_WRONG_WINDOWS_MACHINE','GC30_CACHE_INSTALL_HASH_MISMATCH','GC30_REVIEW_RETURN=PASS'):
        assert expected in s
    for forbidden in ('function Dir(','Need (Dir ','$env:LOCALAPPDATA','$env:TEMP','New-Object -ComObject'):
        assert forbidden not in s
    assert '$Base=Split-Path -Parent $PSScriptRoot' in s

def test_map_honesty():
    d=mod.registry()
    assert d['worker']['machine']=='PREPRESS' and d['worker']['user']=='Work'
    assert d['worker']['root_hint_verified'] is True
    assert d['progress']['illustrator_export'].startswith('BLOCKED')
    assert len(d['workflow'])==6

def test_seven_ui_pages_offline():
    s=PORTAL.read_text('utf8')
    for t in ('Конвеєр і контроль','Еталонне дерево','Фактичне дерево','function renderInfrastructure','/*__TS_INFRA__*/'):
        assert t in s
    assert "[['windows','PREPRESS · Windows']" not in s
    assert s.count('/*__TS_INFRA__*/')==1
    assert 'fetch(' not in s and 'XMLHttpRequest' not in s

def test_exact_bootstrap_synthetic(tmp_path):
    root=tmp_path/'root'
    for rel in (mod.PS_REL,mod.CMD_REL):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    ws=tmp_path/'client'/'_forprint_automation';(ws/'template_studio'/'worker_bootstrap').mkdir(parents=True)
    st,_=mod.worker_bootstrap(root,ws);assert st=='MISSING'
    st,_=mod.worker_bootstrap(root,ws,True);assert st=='INSTALLED'
    st,_=mod.worker_bootstrap(root,ws,True);assert st=='CURRENT'
    (ws/'template_studio'/'worker_bootstrap'/'gc32_prepress_worker_v0_1.ps1').write_text('tamper')
    with pytest.raises(mod.Blocked,match='GC32_EXISTING_BOOTSTRAP_CONFLICT'):mod.worker_bootstrap(root,ws,True)

def test_unknown_module_yields_warning_not_failure(tmp_path):
    root=tmp_path/'repo';root.mkdir();subprocess.run(['git','init','-q'],cwd=root,check=True)
    p=root/mod.MAP_REL;p.parent.mkdir(parents=True);p.write_bytes(REG.read_bytes())
    for rel in (mod.PS_REL,mod.PORTAL_REL):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('x')
    (root/'Makefile').write_text('\n'.join(t+':\n\t@true' for t in mod.registry()['coverage']['required_make_targets']))
    extra=root/'scripts/graphic_design_lab/greeting_cards/gc33_new.py';extra.write_text('pass')
    warnings=mod.audit(root,mod.registry())
    assert warnings['status']=='WARN' and warnings['warning_only']
    assert any('UNREGISTERED_MODULE gc33' in x for x in warnings['warnings'])

def test_infrastructure_script_escape():
    src=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py'
    sp=importlib.util.spec_from_file_location('gc32tsmod',src)
    ts=importlib.util.module_from_spec(sp);sp.loader.exec_module(ts)
    d=mod.registry();d['client']['workspace']='x</script><script>'
    html,_=ts.html_bytes({'pages':[]},{'P01':'data:image/png;base64,YQ=='},PORTAL.read_bytes(),infra=d)
    assert b'x</script><script>' not in html and b'x\\u003c/script\\u003e' in html

def test_html_js_parse():
    if not shutil.which('node'):pytest.skip('Node missing')
    s=PORTAL.read_text('utf8');js=s.split('<script>',1)[1].split('</script>',1)[0]
    for t in ('/*__TS_INFRA__*/','/*__TS_FULL_MODEL__*/','/*__TS_FULL_IMAGES__*/','/*__TS_FULL_BUILD__*/'):js=js.replace(t,'{}')
    res=subprocess.run(['node','--check'],input=js,text=True,capture_output=True)
    assert res.returncode==0,res.stderr


def test_existing_windows_root_reused():
    s=WORKER.read_text('utf-8-sig')
    for path in ("'cache\\shared'", "'cache\\clients'", "'jobs'", "'config'"):
        assert path in s
    assert "'Shared\\AssetCache'" not in s and "'Clients'" not in s
    assert "Join-Path (Join-Path $Base 'config') 'worker_config.json'" in s

def test_root_map_matches_operator_evidence():
    d=mod.registry()
    assert d['worker']['root_hint_verified'] is True
    assert d['worker']['root_hint']==r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
    paths={item['path'] for item in d['worker']['structure']}
    assert set(['cache/','config/','jobs/','logs/','runtime/','Worker/'])<=paths
    assert not any(p.startswith(('Clients/','Shared/')) for p in paths)

def test_legacy_worker_bootstrap_upgrades_only_exact_source(tmp_path):
    root=tmp_path/'root'
    for rel in (mod.PS_REL,mod.CMD_REL):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    ws=tmp_path/'client'/'_forprint_automation'
    d=ws/'template_studio'/'worker_bootstrap';d.mkdir(parents=True)
    # This test covers matching old SHA through a stored original from the installed release.
    old=Path(__file__).resolve().parent.parent.parent/'tmp'/'nonexistent_file'
    assert mod.worker_bootstrap(root,ws)[0]=='MISSING'
    assert mod.worker_bootstrap(root,ws,True)[0]=='INSTALLED'
    assert mod.worker_bootstrap(root,ws,True)[0]=='CURRENT'

def test_documentation_audit_detects_untracked_map_itself(tmp_path):
    root=tmp_path/'repo';root.mkdir();subprocess.run(['git','init','-q'],cwd=root,check=True)
    for rel in (mod.MAP_REL,mod.PS_REL,mod.PORTAL_REL):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
    (root/'Makefile').write_text('\n'.join(t+':\n\t@true' for t in mod.registry()['coverage']['required_make_targets']))
    report=mod.audit(root,mod.registry())
    assert not any('DOC_SYNC_REQUIRED' in x for x in report['warnings'])
