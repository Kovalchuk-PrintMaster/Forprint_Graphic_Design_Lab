#!/usr/bin/env python3
"""F1: one synthetic editable Illustrator design, reusing W2.5.3 Limited GUI controller.

Only explicit operator launch. No production/customer data, no retry or cleanup.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from windows_worker_w2_5_3_limited_native_illustrator_probe_v0_1 import (
    source_check as w253_source_check, render as w253_render,
    NativeBlocked,
)
from windows_worker_w2_host_inspector_v0_1 import ssh_command, InspectionBlocked
from windows_worker_w2_3_workspace_initializer_v0_1 import PS_STDIN_BRIDGE

ROOT=Path(__file__).resolve().parents[3]
SPEC=ROOT/'coordination/graphic_design_lab/functional_pilot/gdl_f1_design_spec_v0_1.json'
TEMPLATE=Path(__file__).with_name('gdl_f1_functional_design_template_v0_1.jsx')
TASK='gdl-f1-functional-design-001'
ATTEMPT='a0001'
TASK_NAME='ForPrint-GDL-F1-Functional-Design'
W253_TASK='gdl-w253-limited-native-001'
W253_TASK_NAME='ForPrint-GDL-W2-5-3-Limited-Native-Proof'
SCHEMA='gdl_windows_w2_5_3_native_controller_v0_1'
RUN_SCHEMA='gdl_windows_w2_5_3_native_runner_v0_1'
HEXSHA=re.compile(r'^[0-9a-f]{64}$')
WIN_ROOT=r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
REMOTE_ACCOUNT=r'PREPRESS\Work'

class F1Blocked(RuntimeError): pass

def require(ok, code):
    if not ok: raise F1Blocked(code)

def sha(blob): return hashlib.sha256(blob).hexdigest()

def source_check():
    """Reuse already installed W2.5.3 exactly; do not create parallel Scheduler adapter."""
    try: ctrl,runner,unused_jsx=w253_source_check()
    except (NativeBlocked,ValueError,OSError) as exc: raise F1Blocked('W253_BASELINE_NOT_VALID') from exc
    require(SPEC.is_file() and not SPEC.is_symlink() and TEMPLATE.is_file() and not TEMPLATE.is_symlink(), 'F1_INPUT_FILES')
    j=json.loads(SPEC.read_text('utf-8'))
    require(type(j) is dict and set(j)=={'schema_version','kind','task_id','attempt_id','format_mm',
        'headline','subtitle','body','footer','accent_rgb'},'SPEC_FIELDS')
    require(j['schema_version']=='gdl_f1_functional_design_spec_v0_1' and j['kind']=='SYNTHETIC_ONLY' and
        j['task_id']==TASK and j['attempt_id']==ATTEMPT and j['format_mm']==[210,297], 'SPEC_SCOPE')
    for k in ('headline','subtitle','body','footer'):
        s=j[k]
        require(type(s) is str and 5<=len(s)<=68 and all(32<=ord(ch) and ch not in '\r\n' for ch in s),'INVALID_TEXT_'+k)
    require(type(j['accent_rgb']) is list and len(j['accent_rgb'])==3 and
        all(type(x) is int and 0<=x<=255 for x in j['accent_rgb']), 'INVALID_RGB')
    template=TEMPLATE.read_text('utf-8')
    require(len(template)<12000 and 'FORPRINT_NATIVE_AI_REOPENED' in template and
        'TextType.POINTTEXT' in template and 'preview.pdf' in template and
        'ExportType.PNG24' in template and 'app.open(ai)' in template, 'JSX_REQUIRED_ACTIONS')
    for name in ('__F1_HEADLINE__','__F1_SUBTITLE__','__F1_BODY__','__F1_FOOTER__','__F1_ACCENT__'):
        require(template.count(name)==1,'JSX_TEMPLATE_MARKER')
    for bad in ('alert(', 'confirm(', 'prompt(', 'File.openDialog', 'app.quit('):
        require(bad not in template,'JSX_UNATTENDED')
    return ctrl,runner,template,j

def render(mode):
    ctrl,runner,template,spec=source_check()
    require(mode in ('check','launch','verify'),'UNSUPPORTED_REMOTE_MODE')
    for old,new in ((W253_TASK,TASK),(W253_TASK_NAME,TASK_NAME)):
        require(ctrl.count(old)>=1,'CONTROLLER_BASELINE_CHANGED')
        ctrl=ctrl.replace(old,new)
    require(runner.count(W253_TASK.encode())>=1,'RUNNER_BASELINE_CHANGED')
    runner=runner.replace(W253_TASK.encode(),TASK.encode())
    # Baseline runner only records a label; F1 uses Illustrator application font.
    require(runner.count(b"$FontName = 'ZapfChanceryC'")==1,'RUNNER_FONT_BASELINE')
    runner=runner.replace(b"$FontName = 'ZapfChanceryC'",b"$FontName = 'APPLICATION_DEFAULT'")
    require(runner.count(b'editable_area_text=$Proof')==1,'RUNNER_EDITABILITY_BASELINE')
    runner=runner.replace(b'editable_area_text=$Proof',b'editable_point_text=$Proof')
    insert={'__F1_HEADLINE__':json.dumps(spec['headline'],ensure_ascii=True),
        '__F1_SUBTITLE__':json.dumps(spec['subtitle'],ensure_ascii=True),
        '__F1_BODY__':json.dumps(spec['body'],ensure_ascii=True),
        '__F1_FOOTER__':json.dumps(spec['footer'],ensure_ascii=True),
        '__F1_ACCENT__':','.join(str(v) for v in spec['accent_rgb'])}
    for marker,value in insert.items():template=template.replace(marker,value)
    jsx=template.encode('ascii','backslashreplace')
    require('__F1_' not in template and len(jsx)<16000,'JSX_COMPILE')
    try: content,rs,js=w253_render(mode,ctrl,runner,jsx)
    except NativeBlocked as exc: raise F1Blocked('BASE_RENDER_BLOCKED') from exc
    return content,rs,js

def validate_controller(text,mode,runner_sha,jsx_sha):
    try: d=json.loads(text.strip())
    except (ValueError,TypeError) as exc:raise F1Blocked('INVALID_WINDOWS_CONTROLLER_OUTPUT') from exc
    require(type(d) is dict and d.get('schema_version')==SCHEMA, 'CONTROLLER_SCHEMA')
    for k,val in {'mode':mode,'host':'PREPRESS','ssh_account':REMOTE_ACCOUNT,
                  'task_id':TASK,'attempt_id':ATTEMPT,'task_name':TASK_NAME,
                  'jsx_sha256':jsx_sha,'runner_sha256':runner_sha,
                  'scheduler_run_level':'Limited','smb_mutation':False,
                  'client_files_touched':False,'cleanup_executed':False,
                  'production_ready':False}.items():
        require(d.get(k)==val, 'CONTROLLER_BINDING_'+k)
    require((mode=='launch') is (d.get('windows_mutation') is True), 'SIDE_EFFECT_MISMATCH')
    if mode=='check':
        require(d.get('state')=='READY_FOR_LIMITED_NATIVE_PROOF' and
                d.get('native_result') is None and type(d.get('session_id')) is int and d['session_id']>0,
                'F1_CHECK_BLOCKED')
    elif mode=='launch':
        require(d.get('state')=='LIMITED_NATIVE_PROOF_STARTED_RESULT_PENDING', 'F1_LAUNCH_UNCONFIRMED')
    else:
        require(d.get('state') in ('WAITING_FOR_LIMITED_NATIVE_RESULT',
               'LIMITED_NATIVE_RESULT_REQUIRES_REVIEW','LIMITED_NATIVE_AI_REOPENED_VERIFIED'), 'F1_VERIFY_STATE')
        if d['state']=='LIMITED_NATIVE_AI_REOPENED_VERIFIED':
            r=d.get('native_result')
            require(type(r) is dict, 'MISSING_RUNNER_RESULT')
            for k,v in {'schema_version':RUN_SCHEMA,'task_id':TASK,'attempt_id':ATTEMPT,
                        'state':'PASS_NATIVE_AI_REOPENED','font_name':'APPLICATION_DEFAULT',
                        'jsx_sha256':jsx_sha,'runner_sha256':runner_sha,
                        'token_limited_verified':True,'native_ai_saved_reopened':True,
                        'editable_point_text':True,'production_ready':False}.items():
                require(r.get(k)==v,'RUNNER_BINDING_'+k)
            require(HEXSHA.fullmatch(str(r.get('ai_sha256'))) and type(r.get('ai_bytes')) is int and
                    r['ai_bytes']>1000, 'RUNNER_NATIVE_AI')
    return d

def ssh_run(content,args,timeout=110):
    require(args.host=='192.168.50.69' and args.user=='work', 'UNEXPECTED_HOST')
    bridge=base64.b64encode(PS_STDIN_BRIDGE.encode('utf-16le')).decode('ascii')
    try:
        command=ssh_command(host=args.host,user=args.user,identity_file=args.identity_file,
                            known_hosts=args.known_hosts,encoded=bridge)
        p=subprocess.run(command,input=content,text=True,capture_output=True,encoding='utf-8',
                         errors='replace',timeout=timeout)
    except (InspectionBlocked,OSError,subprocess.TimeoutExpired) as exc:
        raise F1Blocked('SSH_UNKNOWN_STATE_NO_BLIND_RETRY') from exc
    require(p.returncode==0, 'WINDOWS_REFUSED_RC_'+str(p.returncode)+'_NO_BLIND_RETRY')
    return p.stdout

REMOTE_RETURN=r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
try{
 $root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
 $dir=Join-Path $root 'jobs\gdl-f1-functional-design-001\a0001\export'
 if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){throw 'USER'}
 $files=@('native_probe.ai','preview.pdf','preview.png','native_runner_result.json')
 $records=@{}
 foreach($name in $files){
  $p=Join-Path $dir $name
  $i=Get-Item -LiteralPath $p -Force -ErrorAction Stop
  if($i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $i.Length -lt 100){throw 'UNSAFE_FILE'}
  if($i.Length -gt 20000000){throw 'TOO_LARGE'}
  $bytes=[IO.File]::ReadAllBytes($p)
  $records[$name]=@{bytes=$bytes.Length;sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant();content=[Convert]::ToBase64String($bytes)}
 }
 $r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($records['native_runner_result.json'].content))|ConvertFrom-Json
 if($r.state -ne 'PASS_NATIVE_AI_REOPENED' -or $r.task_id -ne 'gdl-f1-functional-design-001' -or
    $r.attempt_id -ne 'a0001' -or $r.ai_sha256 -cne $records['native_probe.ai'].sha256 -or
    $r.ai_bytes -ne $records['native_probe.ai'].bytes){throw 'RUNNER_MISMATCH'}
 [Console]::Out.WriteLine((ConvertTo-Json -InputObject @{schema='gdl_f1_return_v0_1';files=$records;task_id='gdl-f1-functional-design-001';attempt_id='a0001';client_data=$false} -Compress -Depth 6))
 exit 0
}catch{[Console]::Error.WriteLine('F1_RETURN_BLOCKED_PRESERVE_EVIDENCE');exit 2}
'''

def decode_return(raw, expected_runner_sha,expected_jsx_sha):
    try:d=json.loads(raw.strip())
    except ValueError as exc:raise F1Blocked('RETURN_JSON') from exc
    require(type(d) is dict and set(d)=={'schema','files','task_id','attempt_id','client_data'},'RETURN_FIELDS')
    require(d['schema']=='gdl_f1_return_v0_1' and d['task_id']==TASK and d['attempt_id']==ATTEMPT and
            d['client_data'] is False,'RETURN_BINDING')
    records=d['files'];names={'native_probe.ai','preview.pdf','preview.png','native_runner_result.json'}
    require(type(records) is dict and set(records)==names,'RETURN_ARTIFACTS')
    blobs={}
    for name,r in records.items():
        require(type(r) is dict and set(r)=={'bytes','sha256','content'},'RETURN_ITEM')
        require(type(r['bytes']) is int and 100<=r['bytes']<=20000000 and
                HEXSHA.fullmatch(str(r['sha256'])),'RETURN_DIGEST')
        try:data=base64.b64decode(r['content'],validate=True)
        except (ValueError,TypeError) as exc:raise F1Blocked('RETURN_BASE64') from exc
        require(len(data)==r['bytes'] and sha(data)==r['sha256'],'RETURN_SHA')
        blobs[name]=data
    require(blobs['preview.pdf'].startswith(b'%PDF-'),'PDF_HEADER')
    require(blobs['preview.png'].startswith(b'\x89PNG\r\n\x1a\n'),'PNG_HEADER')
    try: report=json.loads(blobs['native_runner_result.json'].decode('utf-8-sig'))
    except (ValueError,UnicodeError) as exc:raise F1Blocked('REPORT_JSON') from exc
    require(report.get('state')=='PASS_NATIVE_AI_REOPENED' and report.get('task_id')==TASK and
            report.get('attempt_id')==ATTEMPT and report.get('runner_sha256')==expected_runner_sha and
            report.get('jsx_sha256')==expected_jsx_sha and report.get('token_limited_verified') is True and
            report.get('editable_point_text') is True and report.get('ai_sha256')==sha(blobs['native_probe.ai']) and
            report.get('ai_bytes')==len(blobs['native_probe.ai']), 'RUNNER_RETURN_VALIDATION')
    return blobs

def write_local(blobs,outdir):
    require(not outdir.exists() and not outdir.is_symlink(),'RETURN_DIRECTORY_OCCUPIED')
    # CreateNew local files and no overwrite; preserve partial evidence on failure.
    outdir.mkdir(mode=0o700)
    mapping={'native_probe.ai':'design.ai','preview.pdf':'preview.pdf',
             'preview.png':'preview.png','native_runner_result.json':'runner_result.json'}
    manifest={'schema_version':'gdl_f1_return_manifest_v0_1','task_id':TASK,
              'attempt_id':ATTEMPT,'production_ready':False,'automatic_acceptance':False,
              'artifacts':{mapping[k]:sha(v) for k,v in blobs.items()}}
    staged={mapping[k]:v for k,v in blobs.items()}
    staged['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    for name,data in staged.items():
        fd=os.open(outdir/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
    return manifest

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('source-check','check','launch','verify','retrieve'))
    p.add_argument('--confirm-f1-launch',action='store_true')
    p.add_argument('--confirm-f1-retrieve',action='store_true')
    p.add_argument('--host');p.add_argument('--user');p.add_argument('--identity-file',type=Path)
    p.add_argument('--known-hosts',type=Path)
    p.add_argument('--output-dir',type=Path)
    a=p.parse_args(argv)
    try:
        _,rsha,jsha=render('check')
        if a.mode=='source-check':
            require(not any((a.host,a.user,a.identity_file,a.known_hosts,a.confirm_f1_launch,
                             a.confirm_f1_retrieve,a.output_dir)),'SOURCE_CHECK_ARGS')
            print('GDL_F1_FUNCTIONAL_PILOT=SOURCE_CHECK_PASS')
            print('WORKER_EXECUTION=false WINDOWS_WRITE=false')
            return 0
        require(all((a.host,a.user,a.identity_file,a.known_hosts)), 'SSH_ARGUMENTS_REQUIRED')
        require(a.confirm_f1_launch == (a.mode=='launch'), 'LAUNCH_CONFIRMATION_MISMATCH')
        require(a.confirm_f1_retrieve == (a.mode=='retrieve'), 'RETRIEVE_CONFIRMATION_MISMATCH')
        require((a.mode=='retrieve') == (a.output_dir is not None),'OUTPUT_DIRECTORY_MISMATCH')
        if a.mode=='retrieve':
            require(str(a.output_dir).startswith('tmp/') and len(a.output_dir.parts)==2,
                    'RETURN_LOCAL_TMP_ONLY')
            require(not (ROOT/a.output_dir).exists(),'RETURN_ALREADY_EXISTS')
            raw=ssh_run(REMOTE_RETURN,a,timeout=150)
            manifest=write_local(decode_return(raw,rsha,jsha),ROOT/a.output_dir)
            print(json.dumps(manifest,sort_keys=True,indent=2,ensure_ascii=False))
            print('GDL_F1_FUNCTIONAL_PILOT=ARTIFACTS_RETURNED_LOCAL_REVIEW_REQUIRED')
        else:
            content,rsha,jsha=render(a.mode)
            report=validate_controller(ssh_run(content,a),a.mode,rsha,jsha)
            print(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True))
            print('GDL_F1_FUNCTIONAL_PILOT='+report['state'])
        return 0
    except (F1Blocked,OSError,ValueError,UnicodeError) as e:
        print('GDL_F1_FUNCTIONAL_PILOT=BLOCKED reason='+str(e),file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
