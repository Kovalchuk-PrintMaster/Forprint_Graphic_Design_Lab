import importlib.util
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

HERE = Path(__file__).resolve().parents[2]
SOURCE = HERE/'scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py'
spec = importlib.util.spec_from_file_location('gc32ssh', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CLIENT='Виктория Беспалова _+380 67 793 00 15'


def snapshot():
    return {'schema_version':m.SCHEMA,'machine':'PREPRESS','user':'Work','client':CLIENT,
            'root':m.WINDOWS_ROOT,'captured_utc':'2026-10-26T12:00:00Z',
            'entries':[{'path':'jobs/gdl-gc21-card-001','kind':'dir','size_bytes':None,'sha256':None},
                       {'path':'Worker/gc32_prepress_worker_v0_1.ps1','kind':'file','size_bytes':10,'sha256':'a'*64}],
            'operator_export_only':True,'production_authority':False,'scan_truncated':False}


def test_check_snapshot_binding_and_normalization():
    s=m.check_snapshot(snapshot(),CLIENT)
    assert s['root']==m.WINDOWS_ROOT and len(s['entries'])==2
    assert s['entries'][1]['sha256']=='a'*64


@pytest.mark.parametrize('change', [
    {'machine':'OTHER'},{'user':'Nobody'},{'root':'C:\\Temp'},{'client':'Another'},
    {'production_authority':True},{'operator_export_only':False},
])
def test_reject_binding_or_authority(change):
    s=snapshot();s.update(change)
    with pytest.raises(m.Blocked):m.check_snapshot(s,CLIENT)


@pytest.mark.parametrize('path',['../escape','jobs/../../foreign','/abs','a\\b','foo//bar','x/./y'])
def test_reject_unsafe_paths(path):
    s=snapshot();s['entries'][0]['path']=path
    with pytest.raises(m.Blocked):m.check_snapshot(s,CLIENT)


def test_reject_case_colliding_paths():
    s=snapshot();s['entries'].append({'path':'JOBS/gdl-gc21-card-001','kind':'dir'})
    with pytest.raises(m.Blocked):m.check_snapshot(s,CLIENT)


def test_lifecycle_does_not_grant_cleanup_authority():
    s=m.check_snapshot(snapshot(),CLIENT)
    report=m.lifecycle_report(s)
    assert report['authority']=={'moving':False,'quarantine':False,'deletion':False}
    assert report['counts']['HISTORY_REVIEW']==1
    assert report['counts']['UNCLASSIFIED_REVIEW']==0


def scanner(tmp_path):
    file=tmp_path/'scanner.ps1'
    file.write_text("param([string]$ClientBase64)\n" + ("# Verified GC32 scanner\n"*20) +
                    "Write-Output $ClientBase64\n", encoding='utf8')
    return file


def test_ssh_calls_short_pinned_local_scanner(tmp_path):
    ps=scanner(tmp_path)
    payload=json.dumps(snapshot(),ensure_ascii=False)
    commands=[]
    def fake_runner(argv,**kwargs):
        commands.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout=('GC32_SNAPSHOT_JSON='+payload+'\n').encode('utf8'),stderr=b'')
    doc=m.ssh_capture(CLIENT,ps,runner=fake_runner)
    assert doc['client']==CLIENT
    cmd,kw=commands[0]
    assert cmd[:3]==['ssh','-T','-i']
    assert 'StrictHostKeyChecking=yes' in cmd
    assert kw.get('input') is None
    assert len(' '.join(cmd)) < 5000
    payload=base64.b64decode(cmd[-1]).decode('utf-16le')
    assert 'Get-FileHash' in payload and 'ClientBase64' in payload
    assert m.sha(ps.read_bytes()) in payload
    assert 'Console]::In.ReadToEnd' not in payload
    assert CLIENT not in payload


def test_remote_missing_or_changed_scanner_fail_closed(tmp_path):
    ps=scanner(tmp_path)
    for code in ('SCANNER_MISSING','SCANNER_SHA_CHANGED','SCAN_EXCEPTION'):
        def fake(*args,**kwargs):
            return SimpleNamespace(returncode=72,stdout=b'',stderr=('GC32_REMOTE_'+code).encode())
        with pytest.raises(m.Blocked,match='GC32_REMOTE_'+code):
            m.ssh_capture(CLIENT,ps,runner=fake)


def test_network_failure_is_distinct(tmp_path):
    ps=scanner(tmp_path)
    def fake(*a,**k):return SimpleNamespace(returncode=255,stdout=b'',stderr=b'host down')
    with pytest.raises(m.Blocked,match='GC32_SCANNER_EXECUTION_FAILED_RC_255'):
        m.ssh_capture(CLIENT,ps,runner=fake)


def test_scanner_check_missing_and_current(tmp_path):
    ps=scanner(tmp_path)
    for state in ('MISSING','CURRENT','CONFLICT'):
        def fake(*args,**kwargs):
            return SimpleNamespace(returncode=0,stdout=('GC32_SCANNER_STATE='+state+'\n').encode(),stderr=b'')
        assert m.scanner_check(ps,runner=fake)==state


def test_scanner_install_requires_confirmation_and_exact_copy(tmp_path):
    ps=scanner(tmp_path)
    with pytest.raises(m.Blocked,match='GC32_SCANNER_INSTALL_CONFIRM_REQUIRED'):
        m.scanner_install(ps,confirm=False)
    calls=[]
    outputs=['GC32_SCANNER_STATE=MISSING', 'GC32_SCANNER_STAGE_PREFLIGHT=PASS',
             'GC32_SCANNER_INSTALLED=PASS', 'GC32_SCANNER_STATE=CURRENT']
    def fake(cmd,**kwargs):
        calls.append((cmd,kwargs))
        return SimpleNamespace(returncode=0,stdout=(outputs.pop(0)+'\n').encode(),stderr=b'')
    scps=[]
    def scp(cmd,**kwargs):
        scps.append((cmd,kwargs))
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
    assert m.scanner_install(ps,confirm=True,runner=fake,copier=scp)=='INSTALLED_VERIFIED'
    assert len(calls)==4 and len(scps)==1
    assert scps[0][0][0]=='scp'
    assert scps[0][0][-2]==str(ps)
    assert scps[0][0][-1].startswith(m.HOST+':gc32_scanner_stage_')


def test_scanner_install_conflict_no_mutation(tmp_path):
    ps=scanner(tmp_path)
    def fake(*a,**k):return SimpleNamespace(returncode=0,stdout=b'GC32_SCANNER_STATE=CONFLICT\n',stderr=b'')
    def forbidden(*a,**k):raise AssertionError('NO SCP ON CONFLICT')
    with pytest.raises(m.Blocked,match='GC32_SCANNER_EXISTING_CONFLICT_NO_OVERWRITE'):
        m.scanner_install(ps,confirm=True,runner=fake,copier=forbidden)


def test_scanner_ps_source_is_parameterized_and_no_smb_write():
    content=m.SRC_PS.read_text('utf8')
    assert 'param(' in content and 'ClientBase64' in content
    assert '__CLIENT_BASE64__' not in content
    assert 'New-Item' not in content and 'Set-Content' not in content
    assert 'GC32_SNAPSHOT_JSON=' in content

def test_pub_requires_valid_capture_and_preserves_previous(tmp_path,monkeypatch):
    root=tmp_path/'project';root.mkdir()
    src=root/'scripts/graphic_design_lab/greeting_cards/windows/ps.ps1'
    src.parent.mkdir(parents=True)
    src.write_text('__CLIENT_BASE64__',encoding='utf8')
    monkeypatch.setattr(m,'SRC_PS',src)
    run=m.export_capture(root,CLIENT,m.check_snapshot(snapshot(),CLIENT))
    ws=tmp_path/'share'/CLIENT/'_forprint_automation'
    (ws/'template_studio').mkdir(parents=True)
    dest=m.publish_capture(ws,run,CLIENT)
    assert json.loads(dest.read_text('utf8'))['machine']=='PREPRESS'
    with pytest.raises(m.Blocked,match='SNAPSHOT_ALREADY_CURRENT'):
        m.publish_capture(ws,run,CLIENT)
    old=dest.read_bytes()
    updated=snapshot();updated['entries'].append({'path':'cache','kind':'dir'})
    run2=m.export_capture(root,CLIENT,m.check_snapshot(updated,CLIENT))
    m.publish_capture(ws,run2,CLIENT)
    assert (run2/'previous_prepress_snapshot.json').read_bytes()==old


def test_tampered_capture_and_target_symlink_block(tmp_path,monkeypatch):
    root=tmp_path/'project';root.mkdir()
    src=root/'s.ps1';src.write_text('__CLIENT_BASE64__')
    monkeypatch.setattr(m,'SRC_PS',src)
    doc=m.check_snapshot(snapshot(),CLIENT)
    run=m.export_capture(root,CLIENT,doc)
    (run/'prepress_snapshot.json').write_text('{}')
    with pytest.raises(m.Blocked,match='CAPTURE_DIGEST_OR_BINDING_CHANGED'):
        m.validate_capture(run,CLIENT)
    run=m.export_capture(root,CLIENT,doc)
    ws=tmp_path/'share'/CLIENT/'_forprint_automation'
    (ws/'template_studio'/'inventory').mkdir(parents=True)
    (ws/'template_studio'/'inventory'/'prepress_snapshot.json').symlink_to(src)
    with pytest.raises(m.Blocked,match='EXISTING_SNAPSHOT_SYMLINK_FORBIDDEN'):
        m.publish_capture(ws,run,CLIENT)


def test_windows_path_normalization_uses_escaped_regex():
    # PowerShell -replace takes a regex: one slash is invalid, two mean literal backslash.
    import re as regex
    source=m.SRC_PS.read_text(encoding='utf8')
    match=regex.search(r"path=\(\$rel -replace '([^']*)','/'\)",source)
    assert match is not None
    assert match.group(1) == r'\\'
    assert regex.sub(match.group(1),'/',r'Worker\gc32_prepress_ssh_snapshot_v0_1.ps1') == 'Worker/gc32_prepress_ssh_snapshot_v0_1.ps1'
