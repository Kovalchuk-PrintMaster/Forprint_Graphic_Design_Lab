from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/template_studio/ts_r010_native_evidence_inventory_v0_1.py'
sp = importlib.util.spec_from_file_location('ts_r010_native_evidence', SCRIPT)
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)


def workspace(tmp_path):
    ws=tmp_path/'client'/'_forprint_automation'
    (ws/'template_studio'/'native_runs').mkdir(parents=True)
    (ws/'output'/'illustrator_review').mkdir(parents=True)
    return ws


def result(folder, state='AI_REOPENED_VISUAL_REVIEW_REQUIRED', name='result.json'):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/name).write_text(json.dumps({'schema_version':'gdl_gc29_native_result_v0_1',
        'state':state,'production_ready':False,'visual_approved':False,
        'private_sender_lines':['THIS MUST NOT LEAK']}), encoding='utf8')


def test_missing_native_result_not_attested(tmp_path):
    ws=workspace(tmp_path)
    d=m.scan(ws)
    assert d['counts']['run_candidates']==0
    assert not d['conclusion']['independent_ai_reopen_attested']
    assert not d['conclusion']['production_ready']


def test_self_report_never_native_attestation(tmp_path):
    ws=workspace(tmp_path)
    out=ws/'template_studio'/'native_runs'/'gdl_gc_run__123456789abcde'/'out'
    result(out)
    evidence=m.scan(ws)
    e=evidence['runs'][0]
    assert e['self_report_reopen_present']
    assert not e['independent_reopen_attested']
    assert not e['native_layers_attested']
    assert not e['visual_parity_attested']
    assert 'THIS MUST NOT LEAK' not in json.dumps(evidence)


def test_compares_copied_files_by_digest(tmp_path):
    ws=workspace(tmp_path)
    name='gdl_gc_run__123456789abcde'
    out=ws/'template_studio'/'native_runs'/name/'out'
    dest=ws/'output'/'illustrator_review'/name
    for p in (out, dest):
        result(p)
        for file in m.EXPECTED:
            if file != 'result.json': (p/file).write_bytes(b'x'*200)
    run=m.scan(ws)['runs'][0]
    assert run['return_comparison']['all_seven_equal']
    assert not run['native_layers_attested']


def test_detects_changed_return(tmp_path):
    ws=workspace(tmp_path)
    name='gdl_gc_run__123456789abcde'
    out=ws/'template_studio'/'native_runs'/name/'out'
    dest=ws/'output'/'illustrator_review'/name
    for p in (out,dest):
        result(p)
        for file in m.EXPECTED:
            if file != 'result.json':(p/file).write_bytes(b'x'*200)
    (dest/'design.ai').write_bytes(b'mismatched')
    comparison=m.scan(ws)['runs'][0]['return_comparison']
    assert not comparison['all_seven_equal']
    assert comparison['different_files']==['design.ai']


def test_skips_symlink_files(tmp_path):
    ws=workspace(tmp_path)
    run=ws/'template_studio'/'native_runs'/'gdl_gc_run__123456789abcde'
    out=run/'out';out.mkdir(parents=True)
    secret=tmp_path/'outside.txt';secret.write_text('SECRET')
    (out/'design.ai').symlink_to(secret)
    report=m.scan(ws)
    assert report['runs'][0]['worker_out']['artifacts']['design.ai']['state']=='UNSAFE_SYMLINK'
    assert 'SECRET' not in json.dumps(report)


def test_rejects_oversize_json(tmp_path):
    ws=workspace(tmp_path)
    out=ws/'template_studio'/'native_runs'/'run1'/'out'
    out.mkdir(parents=True)
    (out/'result.json').write_bytes(b'{' + b' '*m.MAX_JSON_SIZE+b'}')
    report=m.scan(ws)
    assert report['runs'][0]['worker_out']['result_parse']=='JSON_SIZE_LIMIT'


def test_truncated_scan(tmp_path, monkeypatch):
    ws=workspace(tmp_path)
    monkeypatch.setattr(m, 'MAX_RUNS_PER_ROOT', 1)
    for name in ('run1','run2'):(ws/'template_studio'/'native_runs'/name).mkdir()
    r=m.scan(ws)
    assert r['scan_truncated']
    assert r['counts']['run_candidates']==1


def test_gc27_single_page_never_full_card(tmp_path):
    ws=workspace(tmp_path)
    d=tmp_path/'gc27proof'
    result(d/'out',state='P03_NATIVE_AI_REOPENED_VISUAL_REVIEW_REQUIRED')
    (d/'out'/'p03_proof.ai').write_bytes(b'x'*200)
    r=m.scan(ws,[d])
    assert len(r['gc27'])==1
    assert not r['gc27'][0]['native_layers_attested']
    assert not r['gc27'][0]['visual_parity_attested']


def test_no_untrusted_error_message(tmp_path):
    ws=workspace(tmp_path)
    out=ws/'template_studio'/'native_runs'/'run1'/'out'
    out.mkdir(parents=True)
    (out/'result.json').write_text(json.dumps({'state':'BLOCKED_REVIEW_REQUIRED',
        'error':'CONFIDENTIAL_CLIENT_TEXT'}))
    assert 'CONFIDENTIAL_CLIENT_TEXT' not in json.dumps(m.scan(ws))


def test_client_validation_cli(tmp_path, capsys):
    root=tmp_path/'gdl';(root/'tmp').mkdir(parents=True)
    share=tmp_path/'share';share.mkdir()
    (share/'client'/'_forprint_automation').mkdir(parents=True)
    rc=m.cli(['--mode','check','--gdl-root',str(root),'--share-root',str(share),'--client-name','client'])
    assert rc==0
    assert 'TS_R010_PREFLIGHT=PASS_READ_ONLY' in capsys.readouterr().out
    assert not (root/'tmp'/'ts_r010_native_evidence').exists()


def test_capture_exclusive_and_local_only(tmp_path):
    root=tmp_path/'gdl';(root/'tmp').mkdir(parents=True)
    share=tmp_path/'share';share.mkdir()
    (share/'client'/'_forprint_automation').mkdir(parents=True)
    a=['--mode','capture','--gdl-root',str(root),'--share-root',str(share),
       '--client-name','client','--run-id','gc270ct2026', '--confirm-local-report']
    assert m.cli(a)==0
    inv=root/'tmp'/'ts_r010_native_evidence'/'gc270ct2026'/'inventory.json'
    assert inv.is_file()
    assert not (share/'client'/'_forprint_automation'/'output').exists()
    try:
        m.cli(a)
    except SystemExit as exc:
        assert 'EXISTING_REPORT_NO_OVERWRITE' in str(exc)
    else:
        assert False, 'Existing capture must not be overwritten'
