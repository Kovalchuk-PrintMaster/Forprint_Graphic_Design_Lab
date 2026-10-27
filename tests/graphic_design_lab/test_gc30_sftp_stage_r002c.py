import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

P=Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/greeting_cards/gc30_sftp_stage_r002c.py'
spec=importlib.util.spec_from_file_location('gc30_stage_test_module',P)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_exact_scope():
    assert m.PILOT=='gdl_gc_deg_20261011__34b9b61741d5ca'
    assert m.REMOTE_SFTP==m.SFTP_ROOT+'/jobs/'+m.PILOT
    assert m.REMOTE_SCRIPT_WIN.startswith(m.WIN_ROOT+'\\jobs\\'+m.PILOT+'\\')
    assert m.REMOTE_SCRIPT_SFTP.endswith('/'+m.NAME)
    assert m.NAME.endswith('.ps1')


def test_source_sha_pinned():
    assert m.sha(m.PS1)==m.PS1_SHA
    assert m.B_SHA=='1870fec628e11305e448453bc8d0c249e0e3f275a533d16e7065f8a5d2f28588'
    assert m.PAYLOAD_SHA=='d3b9329a51272fb195718d124d465da41c4002816c6d6b07c4c66c01e8982ca7'


def test_remote_probes_short_and_read_only():
    import base64
    for mode in ('check','script','stage'):
        body=m.remote_body(mode)
        assert len(base64.b64encode(body.encode('utf-16le')))+400 < 5000
        for forbidden in ('New-Item','Remove-Item','Copy-Item','Move-Item','Expand-Archive','Start-Process','PollOnce','Set-Content'):
            assert forbidden not in body
        assert 'payload.zip' in body and m.PAYLOAD_SHA in body
        if mode!='check': assert m.PS1_SHA in body


def test_sftp_script_only_one_put():
    calls=[]
    def runner(argv,**kw):
        calls.append((argv,kw))
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
    m.sftp_script(runner=runner)
    assert len(calls)==1
    argv,kw=calls[0]
    assert argv[0]=='sftp' and 'StrictHostKeyChecking=yes' in argv
    assert kw['input'].decode().splitlines()==[f'put "{m.PS1}" "{m.REMOTE_SCRIPT_SFTP}"']
    assert kw['timeout']==90


def test_sftp_failure_does_not_retry():
    def runner(*a,**kw):return SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
    with pytest.raises(m.Blocked,match='RECONCILE_NO_RETRY'):m.sftp_script(runner=runner)


def test_confirmation_strict(monkeypatch):
    monkeypatch.setattr(m,'source_check',lambda:1)
    with pytest.raises(m.Blocked,match='CONFIRMATION_REQUIRED'):m.run('stage',False)
    with pytest.raises(m.Blocked,match='CONFIRMATION_REQUIRED'):m.run('check',True)
    with pytest.raises(m.Blocked,match='CONFIRMATION_REQUIRED'):m.run('verify',True)


def test_check_never_writes(monkeypatch):
    events=[]
    monkeypatch.setattr(m,'source_check',lambda:1)
    monkeypatch.setattr(m,'remote_preflight',lambda:events.append('check'))
    monkeypatch.setattr(m,'sftp_script',lambda:events.append('upload'))
    m.run('check',False)
    assert events==['check']


def test_stage_sequence_exact(monkeypatch):
    events=[]
    monkeypatch.setattr(m,'source_check',lambda:1)
    monkeypatch.setattr(m,'remote_preflight',lambda:events.append('remote-check'))
    monkeypatch.setattr(m,'sftp_script',lambda:events.append('sftp'))
    monkeypatch.setattr(m,'stage_execute',lambda:events.append('stage'))
    m.run('stage',True)
    assert events==['remote-check','sftp','stage']


def test_ps1_static_safety_contract():
    text=m.PS1.read_text('utf8')
    for required in ('$ExpectedZipHash','ConvertFrom-Json',"ShaFile $ZipPath",'STAGED_HASH_VERIFIED_NON_AUTHORIZING','ShaStream','CreateNew','files_verified = 16','assets = 12','GC30_R002C_STAGE=PASS_NON_AUTHORIZING'):
        assert required in text
    for forbidden in ('\\\\192.168.50.10','Remove-Item','PollOnce','Start-Process','Invoke-Expression','& $jsx','C:\\Users\\'):
        assert forbidden not in text
    assert 'Worker\\worker_config.json' not in text


def test_verify_requires_stage_evidence(monkeypatch):
    calls=[]
    monkeypatch.setattr(m,'source_check',lambda:1)
    monkeypatch.setattr(m,'stage_verify',lambda:calls.append('verify'))
    m.run('verify',False)
    assert calls==['verify']
