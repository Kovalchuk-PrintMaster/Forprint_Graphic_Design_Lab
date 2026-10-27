import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

P=Path(__file__).resolve().parents[2]/'scripts/graphic_design_lab/greeting_cards/gc30_sftp_deliver_r002b.py'
spec=importlib.util.spec_from_file_location('gc30_r002b_delivery',P)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

def test_exact_boundary():
    assert m.PILOT=='gdl_gc_deg_20261011__34b9b61741d5ca'
    assert m.REMOTE_FILE.startswith(m.SFTP_ROOT+'/jobs/'+m.PILOT+'/')
    assert m.REMOTE_FILE.endswith('/payload.zip')
    assert 'Clients/' not in m.REMOTE_FILE and 'Shared/' not in m.REMOTE_FILE
    assert m.PAYLOAD_SHA=='d3b9329a51272fb195718d124d465da41c4002816c6d6b07c4c66c01e8982ca7'

def test_sftp_batch_scope(capsys):
    calls=[]
    def runner(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
    m.sftp_transfer(runner)
    assert len(calls)==1
    argv,kwargs=calls[0]
    assert argv[0]=='sftp' and 'BatchMode=yes' in argv
    assert 'StrictHostKeyChecking=yes' in argv
    lines=kwargs['input'].decode().splitlines()
    assert len(lines)==2 and lines[0]=='mkdir "'+m.REMOTE_DIR+'"'
    assert lines[1]=='put "'+str(m.SOURCE)+'" "'+m.REMOTE_FILE+'"'
    assert kwargs['timeout']==120

def test_sftp_failure_no_retry():
    def runner(*args,**kwargs):return SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
    with pytest.raises(m.Blocked,match='RECONCILE_NO_RETRY'):m.sftp_transfer(runner)

def test_remote_probe_no_mutation():
    calls=[]
    class SSH:
        @staticmethod
        def _powershell_ssh(body,**kwargs):
            calls.append(body)
            return SimpleNamespace(returncode=0,stdout=b'GC30_B_TARGET=ABSENT_SAFE\r\n',stderr=b'')
    m.remote_check(SSH)
    assert 'GC30_B_TARGET=ABSENT_SAFE' in calls[0]
    for forbidden in ('New-Item','Remove-Item','Copy-Item','Move-Item','Expand-Archive','PollOnce'):
        assert forbidden not in calls[0]
    # The GC32 wrapper has a strict encoded-command length limit.
    import base64
    encoded=base64.b64encode(calls[0].encode('utf-16le'))
    assert len(encoded)+400 < 5000

def test_remote_probe_blocks_existing():
    class SSH:
        @staticmethod
        def _powershell_ssh(*a,**kw):return SimpleNamespace(returncode=24,stdout=b'GC30_B_TARGET=EXISTS_BLOCKED',stderr=b'')
    with pytest.raises(m.Blocked,match='REMOTE_RC_24'):m.remote_check(SSH)

def test_remote_verify_hash_and_size():
    digest=m.PAYLOAD_SHA
    class SSH:
        @staticmethod
        def _powershell_ssh(*a,**kw):
            out=f'GC30_B_PAYLOAD_SHA256={digest}\r\nGC30_B_PAYLOAD_BYTES=7215\r\n'
            return SimpleNamespace(returncode=0,stdout=out.encode(),stderr=b'')
    m.remote_verify(SSH,7215)
    with pytest.raises(m.Blocked,match='SIZE_MISMATCH'):m.remote_verify(SSH,7214)

def test_delivery_requires_confirmation(monkeypatch):
    monkeypatch.setattr(m,'local_verify',lambda:123)
    with pytest.raises(m.Blocked,match='CONFIRMATION_REQUIRED'):m.run('deliver',False)
    with pytest.raises(m.Blocked,match='CONFIRMATION_REQUIRED'):m.run('check',True)

def test_remote_win_path():
    assert m.REMOTE_WIN==m.WIN_ROOT+'\\jobs\\'+m.PILOT+'\\payload.zip'
    assert m.HOST=='work@192.168.50.69'
