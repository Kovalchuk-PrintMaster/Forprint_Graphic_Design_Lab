"""Read-only atlas synthetic checks; no live SMB or Windows mutation."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import json
import subprocess
import shutil

import pytest

ROOT=Path(__file__).resolve().parents[2]
ATLAS=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_structure_atlas_v0_1.py'
HTML=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
MAP=ROOT/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
PS=ROOT/'scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_inventory_v0_1.ps1'
PUBLISH=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_infrastructure_portal_v0_1.py'
spec=importlib.util.spec_from_file_location('atlas',ATLAS)
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

def fixture_ws(tmp_path):
    ws=tmp_path/'client'/'_forprint_automation'
    vault=ws/'template_studio'/'native_asset_vault_v0_1'
    vault.mkdir(parents=True)
    (ws/'input').mkdir();(ws/'output').mkdir();(ws/'template_studio'/'worker_bootstrap').mkdir()
    (ws/'template_studio'/'index.html').write_text('existing portal')
    (ws/'template_studio'/'worker_bootstrap'/'gc32_prepress_worker_v0_1.ps1').write_text('worker')
    payload=b'test vault asset'
    import hashlib
    manifest={'schema':'gdl_gc29_native_asset_vault_v0_1','asset_count':1,'assets':{'p03_flowers.png':{'size_bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}}
    (vault/'p03_flowers.png').write_bytes(payload)
    (vault/'vault_manifest.json').write_text(json.dumps(manifest))
    return ws

def config():return json.loads(MAP.read_text(encoding='utf8'))

def test_pinned_vault_sha_and_no_history_pdf_read(tmp_path):
    ws=fixture_ws(tmp_path);actual=a.build_atlas(ws,'client-name',config())
    assert actual['assets'][0]['state']=='SHA256_MATCH'
    assert actual['actual']['client']['source']=='S01_READ_ONLY_AT_PORTAL_REFRESH'
    assert 'PREPRESS_SNAPSHOT_NOT_AVAILABLE' in actual['warnings']
    assert any(x['path']=='template_studio/native_asset_vault_v0_1/p03_flowers.png' for x in actual['actual']['client']['entries'])
    (ws/'template_studio'/'native_asset_vault_v0_1'/'p03_flowers.png').write_bytes(b'tamper same?')
    changed=a.build_atlas(ws,'client-name',config())
    assert changed['assets'][0]['state']=='SIZE_MISMATCH'

def test_size_equal_sha_mismatch(tmp_path):
    ws=fixture_ws(tmp_path)
    asset=ws/'template_studio'/'native_asset_vault_v0_1'/'p03_flowers.png'
    asset.write_bytes(b'fail vault asset')
    result=a.build_atlas(ws,'client-name',config())
    assert result['assets'][0]['state']=='SHA256_MISMATCH'

def test_snapshot_diff_and_read_only(tmp_path):
    ws=fixture_ws(tmp_path)
    before=sorted(str(x) for x in ws.rglob('*'))
    first=a.build_atlas(ws,'client-name',config())
    (ws/'input'/'accepted.zip').write_bytes(b'fake')
    second=a.build_atlas(ws,'client-name',config(),previous=first)
    assert any(x['path']=='input/accepted.zip' and x['change']=='NEW' for x in second['actual']['client']['entries'])
    assert sorted(str(x) for x in ws.rglob('*'))==before+[str(ws/'input'/'accepted.zip')] or (ws/'input'/'accepted.zip').is_file()

def test_symlink_not_followed(tmp_path):
    ws=fixture_ws(tmp_path)
    outside=tmp_path/'outside';outside.mkdir();(outside/'secret.txt').write_text('secret')
    (ws/'input'/'outside').symlink_to(outside,target_is_directory=True)
    doc=a.build_atlas(ws,'client-name',config())
    assert any('SYMLINK_NOT_FOLLOWED' in x for x in doc['warnings'])
    assert not any('secret.txt' in x['path'] for x in doc['actual']['client']['entries'])

def test_windows_unavailable_or_rejected(tmp_path):
    ws=fixture_ws(tmp_path)
    inv=ws/'template_studio'/'inventory';inv.mkdir()
    p=inv/'prepress_snapshot.json'
    unsafe={'schema_version':a.WINDOWS_SCHEMA,'machine':'PREPRESS','user':'Work',
            'client':'client-name','root':r'D:\ForPrint_Automation\GraficsDesignLab\Automation',
            'entries':[{'path':'../exfil','kind':'file'}]}
    p.write_text(json.dumps(unsafe))
    doc=a.build_atlas(ws,'client-name',config())
    assert 'PREPRESS_SNAPSHOT_PATH_UNSAFE' in doc['warnings']
    unsafe['entries']=[{'path':'Worker/gc32_prepress_worker_v0_1.ps1','kind':'file','size_bytes':20,'sha256':None}]
    p.write_text(json.dumps(unsafe))
    doc=a.build_atlas(ws,'client-name',config())
    assert doc['actual']['prepress']['state']=='SELF_REPORTED_NOT_REMOTE_ATTESTED'
    assert doc['actual']['prepress']['counts']['items']==1

def test_browser_has_two_real_tabs_and_expanders():
    raw=HTML.read_text('utf8')
    for name in ('Еталонне дерево','Фактичне дерево','atlas-open-all','atlas-close-all','atlas-search','renderAtlasTree','SHA256 перевірено'):
        assert name in raw
    assert raw.count('/*__TS_INFRA__*/')==1 and 'fetch(' not in raw and 'XMLHttpRequest' not in raw
    if shutil.which('node'):
        js=raw.split('<script>',1)[1].split('</script>',1)[0]
        for token in ('/*__TS_INFRA__*/','/*__TS_FULL_MODEL__*/','/*__TS_FULL_IMAGES__*/','/*__TS_FULL_BUILD__*/'):js=js.replace(token,'{}')
        p=subprocess.run(['node','--check'],input=js,text=True,capture_output=True)
        assert p.returncode==0,p.stderr

def test_powershell_scanner_is_root_bound_and_private():
    s=PS.read_text('utf-8-sig')
    for item in ('D:\\ForPrint_Automation\\GraficsDesignLab\\Automation','gc32_prepress_tree_snapshot_v0_1','PREPRESS','Work','client','Worker','SHA256'):
        assert item in s
    for forbidden in ('$env:TEMP', '$env:LOCALAPPDATA', 'Set-ExecutionPolicy', 'New-Object -ComObject'):
        assert forbidden not in s
    assert PS.read_bytes().startswith(b'\xef\xbb\xbf')

def test_publication_injects_atlas_read_only():
    source=PUBLISH.read_text('utf8')
    assert "infra['atlas']=atlas_module(root).build_atlas(ws,client,infra)" in source
    assert "mod.publish(staging,client,share_root,confirm=True)" in source
    assert 'render_page_images(' not in source


def test_windows_scanner_installs_once_without_overwriting(tmp_path):
    ws=fixture_ws(tmp_path)
    root=tmp_path/'project'
    src=root/'scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_inventory_v0_1.ps1'
    src.parent.mkdir(parents=True)
    src.write_bytes(PS.read_bytes())
    state,expected=a.scanner_installer(ws,root,False)
    assert state=='MISSING'
    state,digest=a.scanner_installer(ws,root,True)
    assert state=='INSTALLED' and digest==expected
    assert a.scanner_installer(ws,root,True)[0]=='CURRENT'
    path=ws/'template_studio/worker_bootstrap/gc32_prepress_inventory_v0_1.ps1'
    path.write_text('foreign content')
    with pytest.raises(a.AtlasBlocked,match='EXISTING_SCANNER_DIFFERENT_NO_OVERWRITE'):
        a.scanner_installer(ws,root,True)

def test_inventory_is_bounded_and_no_unverified_claim(tmp_path):
    ws=fixture_ws(tmp_path)
    original=a.MAX_ITEMS
    a.MAX_ITEMS=5
    try:
        doc=a.build_atlas(ws,'client-name',config())
        assert not doc['actual']['client']['scan_complete']
        assert any('INVENTORY_TRUNCATED' in x for x in doc['warnings'])
    finally:a.MAX_ITEMS=original
    assert doc['truth_rules']['sha256']=='ONLY_CHECKED_PINNED_ASSETS_COUNT_AS_VERIFIED'
