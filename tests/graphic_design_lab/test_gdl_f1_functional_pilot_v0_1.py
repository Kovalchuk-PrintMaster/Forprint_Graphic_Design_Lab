"""F1 contract and synthetic transport tests; no Windows or Illustrator launch."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'scripts/graphic_design_lab/worker_runtime'
sys.path.insert(0,str(D))
import gdl_f1_functional_pilot_v0_1 as f1


def test_source_contract():
    _,_,src,spec=f1.source_check()
    assert src.count('app.documents.add')==1
    assert spec['task_id']==f1.TASK
    assert spec['kind']=='SYNTHETIC_ONLY'

@pytest.mark.parametrize('mode',('check','launch','verify'))
def test_render_proven_controller_with_new_task_only(mode):
    import windows_worker_w2_5_3_limited_native_illustrator_probe_v0_1 as old
    encoded,runner_sha,jsx_sha=f1.render(mode)
    assert f1.TASK in encoded
    assert f1.TASK_NAME in encoded
    assert f1.W253_TASK not in encoded
    assert f1.W253_TASK_NAME not in encoded
    assert encoded.count('Start-ScheduledTask')==1
    assert 'FileMode]::CreateNew' in encoded
    assert 'RunLevel Limited' in encoded
    assert old.TASK_ID!=f1.TASK
    assert f1.HEXSHA.fullmatch(runner_sha) and f1.HEXSHA.fullmatch(jsx_sha)
    assert '__RUNNER_B64__' not in encoded
    assert "'$Mode = '__MODE__'" not in encoded
    # The rendered runner is real PS bytes; verify the F1 run metadata.
    import re
    m=re.search(r"\$RunnerB64 = '([^']+)'",encoded)
    assert m
    runner=base64.b64decode(m.group(1))
    assert f1.TASK.encode() in runner
    assert f1.W253_TASK.encode() not in runner
    assert b'editable_point_text=$Proof' in runner
    assert b'editable_area_text=$Proof' not in runner
    assert hashlib.sha256(runner).hexdigest()==runner_sha


def test_compiled_jsx_is_ascii_and_editable():
    encoded,runner_sha,jsx_sha=f1.render('check')
    import re
    m=re.search(r"\$JsxB64 = '([^']+)'",encoded)
    assert m
    jsx=base64.b64decode(m.group(1))
    assert hashlib.sha256(jsx).hexdigest()==jsx_sha
    jsx.decode('ascii')
    for x in (b'ExportType.PNG24',b'PDFSaveOptions',b'IllustratorSaveOptions',
              b'reopened.save()',b'TextType.POINTTEXT',b'FORPRINT_NATIVE_AI_REOPENED'):
        assert x in jsx
    assert b'gdl-w253-limited-native-001' not in jsx
    assert b'gdl-f1-functional-design-001' in jsx


def controller_sample(mode):
    _,runner_sha,jsx_sha=f1.render('check')
    return dict(schema_version=f1.SCHEMA,mode=mode,host='PREPRESS',
        ssh_account=r'PREPRESS\Work',task_id=f1.TASK,attempt_id=f1.ATTEMPT,
        task_name=f1.TASK_NAME,jsx_sha256=jsx_sha,runner_sha256=runner_sha,
        scheduler_run_level='Limited',smb_mutation=False,
        client_files_touched=False,cleanup_executed=False,production_ready=False,
        windows_mutation=(mode=='launch'),native_result=None,
        session_id=2,state={
            'check':'READY_FOR_LIMITED_NATIVE_PROOF',
            'launch':'LIMITED_NATIVE_PROOF_STARTED_RESULT_PENDING',
            'verify':'WAITING_FOR_LIMITED_NATIVE_RESULT'}[mode])

@pytest.mark.parametrize('mode',('check','launch','verify'))
def test_reports_validate_known_states(mode):
    d=controller_sample(mode)
    _,rs,js=f1.render('check')
    assert f1.validate_controller(json.dumps(d),mode,rs,js)['mode']==mode

@pytest.mark.parametrize('bad',('host','task_id','jsx_sha256','task_name','scheduler_run_level','production_ready'))
def test_bad_reports_fail_closed(bad):
    d=controller_sample('check');d[bad]='TAMPERED'
    _,rs,js=f1.render('check')
    with pytest.raises(f1.F1Blocked):f1.validate_controller(json.dumps(d),'check',rs,js)


def test_verify_accepts_native_result_but_never_automatically_accepts():
    d=controller_sample('verify')
    d['state']='LIMITED_NATIVE_AI_REOPENED_VERIFIED'
    d['native_result']={
        'schema_version':f1.RUN_SCHEMA,'task_id':f1.TASK,'attempt_id':f1.ATTEMPT,
        'state':'PASS_NATIVE_AI_REOPENED','font_name':'APPLICATION_DEFAULT',
        'runner_sha256':d['runner_sha256'],'jsx_sha256':d['jsx_sha256'],
        'token_limited_verified':True,'native_ai_saved_reopened':True,
        'editable_point_text':True,'production_ready':False,'ai_sha256':'a'*64,'ai_bytes':50000}
    _,rs,js=f1.render('check')
    assert f1.validate_controller(json.dumps(d),'verify',rs,js)['state']==d['state']
    d['native_result']['editable_point_text']=False
    with pytest.raises(f1.F1Blocked):f1.validate_controller(json.dumps(d),'verify',rs,js)


def synthetic_return():
    blobs={'native_probe.ai':b'%!PS-Adobe-3.0'+b'A'*2000,
           'preview.pdf':b'%PDF-1.7\n'+b'P'*2000,
           'preview.png':b'\x89PNG\r\n\x1a\n'+b'Q'*2000}
    _,rsha,jsha=f1.render('check')
    result={'state':'PASS_NATIVE_AI_REOPENED','task_id':f1.TASK,'attempt_id':f1.ATTEMPT,
            'jsx_sha256':jsha,'runner_sha256':rsha,'token_limited_verified':True,
            'editable_point_text':True,'ai_sha256':f1.sha(blobs['native_probe.ai']),
            'ai_bytes':len(blobs['native_probe.ai'])}
    blobs['native_runner_result.json']=json.dumps(result).encode('utf-8')
    d={'schema':'gdl_f1_return_v0_1','task_id':f1.TASK,'attempt_id':f1.ATTEMPT,
       'client_data':False,'files':{k:{'bytes':len(v),'sha256':f1.sha(v),
       'content':base64.b64encode(v).decode('ascii')} for k,v in blobs.items()}}
    return d,rsha,jsha


def test_return_bytes_and_write_once(tmp_path):
    d,rs,js=synthetic_return()
    blobs=f1.decode_return(json.dumps(d),rs,js)
    out=tmp_path/'f1_return'
    m=f1.write_local(blobs,out)
    assert set(p.name for p in out.iterdir()) == {'design.ai','preview.pdf','preview.png','runner_result.json','manifest.json'}
    assert m['task_id']==f1.TASK
    with pytest.raises(f1.F1Blocked):f1.write_local(blobs,out)

@pytest.mark.parametrize('bad',('pdf','png','sha','task','missing'))
def test_bad_return_rejected(bad):
    d,rs,js=synthetic_return()
    if bad=='pdf':
        b=b'INVALID_PDF'+b'X'*2000
        d['files']['preview.pdf'].update(bytes=len(b),sha256=f1.sha(b),content=base64.b64encode(b).decode())
    elif bad=='png':
        b=b'INVALID_PNG'+b'X'*2000
        d['files']['preview.png'].update(bytes=len(b),sha256=f1.sha(b),content=base64.b64encode(b).decode())
    elif bad=='sha':d['files']['native_probe.ai']['sha256']='0'*64
    elif bad=='task':d['task_id']='some-other-task'
    else:del d['files']['preview.png']
    with pytest.raises(f1.F1Blocked):f1.decode_return(json.dumps(d),rs,js)


def test_remote_read_script_has_no_mutation_calls():
    text=f1.REMOTE_RETURN
    assert 'ReadAllBytes' in text and 'Get-FileHash' in text
    for x in ('Start-ScheduledTask','Register-ScheduledTask','DoJavaScript','Remove-Item','Set-ItemProperty','WriteAllBytes'):
        assert x not in text


def test_cli_source_mode_no_windows_call(monkeypatch,capsys):
    def forbidden(*a,**kw):raise AssertionError('no external calls')
    monkeypatch.setattr(f1,'ssh_run',forbidden)
    assert f1.main(['--mode','source-check'])==0
    assert 'SOURCE_CHECK_PASS' in capsys.readouterr().out


def test_cli_launch_requires_explicit_confirmation(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('must not use network')
    monkeypatch.setattr(f1,'ssh_run',forbidden)
    argv=['--mode','launch','--host','192.168.50.69','--user','work',
          '--identity-file','/tmp/key','--known-hosts','/tmp/known']
    assert f1.main(argv)==2


def test_f1_intentionally_does_not_modify_native_c3_task():
    for mode in ('check','launch','verify'):
        content,_,_=f1.render(mode)
        assert 'gdl-w27c-native-001' not in content
        assert 'gdl-w27g-synthetic-fence-001' not in content
