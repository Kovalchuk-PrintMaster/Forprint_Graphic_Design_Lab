#!/usr/bin/env python3
"""GC47T: one accepted GC29 client job -> one PREPRESS Illustrator native pilot -> GC47S output.

Single-use, source-bound, non-release. Resume only read-only status and collection;
never automatically launch/relaunch a previously claimed attempt. No live API except
known-host-pinned SSH; input SCP and verified output binary SSH.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[3]
GC47S=ROOT/'scripts/graphic_design_lab/greeting_cards/gc47s_client_pilot_v0_1.py'
GC47T=ROOT/'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py'
GC47V_TRACE_TEMPLATE=ROOT/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_gc47w_fit_recovery_r001.jsx'
GC47V_TRACE_SHA='b82d87510612ad2129a3ca46abeb3efa21a67861d723c9fba909dce3776cffa6'
GC47Y_TEMPLATE=ROOT/'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_gc47af_passport_runtime_r001.jsx'
GC47AF_HELPER=ROOT/'scripts/graphic_design_lab/greeting_cards/gc47af_passport_scene_binding_r001.py'
GC47Y_HELPER=ROOT/'scripts/graphic_design_lab/greeting_cards/gc47y_review_amendment_r001.py'
GC47Y_TEMPLATE_SHA='ffa5a4dfeb27382be47529619d3962900b59fe6c8b8d456192beb07a0ed3ae17'
GC47AF_HELPER_SHA='3e13ef9a11db5b587052271930069852a6c24baa80d0d5f3c326bb3aed402203'
GC47Y_HELPER_SHA='30d4da860d94a6d3f8b634b56a1bb96b678923d37e300535635cc3c11d516312'
GC47AC_TRANSPORT=ROOT/'scripts/graphic_design_lab/greeting_cards/gc47ac_verified_review_transport_r001.py'
GC47AC_TRANSPORT_SHA='fb53ef3accdc05758b9e836c8683784d8b0e10e179ebfa84066a95c1f29b8dab'
PACKAGE=GC47T.parent
GC47S_SHA='556e46a041885b7ff84768e51df63037c04a78a7babab37484b4a3abef815362'
HOST='work@192.168.50.69'
KEY='/root/.ssh/forprint_prepress_ed25519'
KNOWN='/root/.ssh/known_hosts_forprint_prepress'
WINDOWS_BASE=r'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gdl-gc47t-client-pilot-001'
REQUIRED=('design.ai','review.pdf','preview_p01.png','preview_p02.png','preview_p03.png','preview_p04.png','result.json')
ATTEMPT_RE=re.compile(r'^p\d{14}-[0-9a-f]{8}$')
SHA_RE=re.compile(r'^[0-9a-f]{64}$')
JSX='run_in_illustrator.jsx'
CTRL='gc47t_windows_controller_r001.ps1'
RUNNER='gc47t_windows_runner_r001.ps1'
BINDING='gc47t_bindings_r001.json'
MAX_TRANSFER=300*1024*1024

class Blocked(ValueError): pass

def need(v,c):
    if not v: raise Blocked(c)

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def folder(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False

def sha_bytes(data): return hashlib.sha256(data).hexdigest()

def sha_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def json_bytes(x): return (json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode('ascii')

def load_gc47s():
    need(regular(GC47S) and sha_file(GC47S)==GC47S_SHA,'GC47S_OPERATOR_DRIFT')
    spec=importlib.util.spec_from_file_location('gc47t_verified_gc47s',GC47S)
    need(spec is not None and spec.loader is not None,'GC47S_IMPORT_ERROR')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def source_check():
    need(ROOT.name=='forprint_graphic_design_lab' and folder(ROOT/'.git'),'GDL_ROOT_INVALID')
    need(regular(GC47T),'GC47T_SCRIPT_MISSING')
    s=load_gc47s(); gc29=s.load_source();_,loop=s.current_passport()
    need(loop.get('windows_worker')=='NOT_WIRED','GC47S_ORIGINAL_PASSPORT_DRIFT')
    d=s.read_obj(s.REGISTRY,5_000_000)['greeting_card_machine_pipeline_v0_1']
    ext=d.get('client_pilot_windows_execution_v0_1')
    need(isinstance(ext,dict) and ext.get('schema_version')=='gdl_gc47t_interactive_windows_execution_v0_1','GC47T_PASSPORT_EXTENSION_MISSING')
    need(ext.get('production_ready') is False and ext.get('dual_runtime_enabled') is False,'GC47T_AUTHORITY_DRIFT')
    for n in (CTRL,RUNNER):need(regular(PACKAGE/n),'GC47T_WORKER_SOURCE_MISSING')
    need(regular(GC47V_TRACE_TEMPLATE) and sha_file(GC47V_TRACE_TEMPLATE)==GC47V_TRACE_SHA, 'GC47W_TRACE_TEMPLATE_DRIFT')
    need(regular(GC47Y_TEMPLATE) and sha_file(GC47Y_TEMPLATE)==GC47Y_TEMPLATE_SHA,'GC47Y_TEMPLATE_DRIFT')
    need(regular(GC47Y_HELPER) and sha_file(GC47Y_HELPER)==GC47Y_HELPER_SHA,'GC47Y_HELPER_DRIFT')
    need(regular(GC47AF_HELPER) and sha_file(GC47AF_HELPER)==GC47AF_HELPER_SHA,'GC47AF_HELPER_DRIFT')
    gc47af_mod().validate_profile(d, job_id='gdl_gc_zap_20261011')
    need(regular(GC47AC_TRANSPORT) and sha_file(GC47AC_TRANSPORT)==GC47AC_TRANSPORT_SHA,'GC47AC_TRANSPORT_DRIFT')
    return s,gc29

def validate_job(s,gc29,client,job_id):
    ws=s.workspace(client)
    need(isinstance(job_id,str) and s.ID_RE.fullmatch(job_id),'JOB_ID_INVALID')
    jobs,_,archive=gc29.accepted_jobs(ws)
    chosen=[j for j in jobs if j.get('job_id')==job_id]
    need(len(chosen)==1,'ACCEPTED_JOB_NOT_UNIQUE_OR_MISSING')
    variants,supported=s.classify(chosen[0])
    need(supported,'RENDERER_VARIANT_NOT_IMPLEMENTED_NO_ATTEMPT_CREATED')
    gc29.verify_vault(ws/'template_studio/native_asset_vault_v0_1')
    return ws,chosen[0],archive,variants

def ssh_options():
    for path in (KEY,KNOWN):need(regular(Path(path)),'PREPRESS_SSH_CREDENTIALS_MISSING')
    return ['-i',KEY,'-o','BatchMode=yes','-o','ConnectTimeout=10',
            '-o',f'UserKnownHostsFile={KNOWN}','-o','StrictHostKeyChecking=yes']

def remote_ps(script,timeout=80):
    need(len(script)<6500,'REMOTE_PS_SCRIPT_TOO_LONG')
    cmd=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    need(len(cmd)<16000,'ENCODED_REMOTE_COMMAND_TOO_LONG')
    argv=['ssh','-T',*ssh_options(),HOST,'powershell.exe','-NoLogo','-NoProfile',
          '-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',cmd]
    p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False)
    if p.returncode:
        match=re.search(r'GC47T_(?:CTRL:|WORKER:)?[A-Z0-9_]+',p.stderr+'\n'+p.stdout)
        raise Blocked('PREPRESS_'+(match.group(0) if match else 'REMOTE_COMMAND_FAILED_RC_'+str(p.returncode)))
    return p.stdout

def scp_to(remote_name,src):
    need(re.fullmatch(r'[A-Za-z0-9_.-]+',remote_name) is not None,'REMOTE_NAME_INVALID')
    subprocess.run(['scp',*ssh_options(),str(src),HOST+':'+remote_name],check=True,timeout=180)

def ps_safe_id(attempt): need(bool(ATTEMPT_RE.fullmatch(attempt)),'ATTEMPT_ID_INVALID');return attempt

def make_transport(s,ws,job,attempt):
    ps_safe_id(attempt)
    base=s.pilot_dir(ws,job,attempt);run=s.native_run_dir(ws,job,attempt)
    state=s.read_obj(base/'state.json');scene=s.read_obj(run/'scene_manifest.json')
    need(state['state']=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED','GC47S_NOT_PREPARED')
    need(state['attempt_id']==attempt and state['job_id']==job,'GC47S_ATTEMPT_BINDING')
    need(state['native_jsx_sha256']==sha_file(run/JSX),'NATIVE_JSX_DRIFT')
    need(scene['job_id']==job and scene['pages']==4 and scene['image_mode']=='DEFAULT_ASSET','GC29_SCENE_NOT_SUPPORTED')
    need(scene['signature'] in ('GRIGO','HERASYMENKO'),'GC29_SIGNER_NOT_SUPPORTED')
    files={}
    for n in (CTRL,RUNNER): files['input/'+n]=(PACKAGE/n).read_bytes()
    files['work/'+JSX]=(run/JSX).read_bytes()
    files['work/scene_manifest.json']=(run/'scene_manifest.json').read_bytes()
    resources=run/'assets';need(folder(resources),'SCENE_ASSET_DIR_MISSING')
    for entry in sorted(resources.iterdir(),key=lambda p:p.name):
        need(regular(entry) and re.fullmatch(r'[a-z0-9_]+\.(png|svg)',entry.name) is not None,'SCENE_ASSET_UNSAFE')
        need(entry.stat().st_size<80*1024*1024,'ASSET_TOO_BIG')
        files['work/assets/'+entry.name]=entry.read_bytes()
    need(len(files)>7,'SCENE_ASSETS_MISSING')
    for layer in scene['layers']:
        need('work/'+layer['file'] in files,'SCENE_LAYER_ASSET_MISSING')
    need(sum(map(len,files.values())) < MAX_TRANSFER,'STAGED_SCENE_TOO_LARGE')
    binding={'schema':'gc47t_windows_binding_r001','attempt':attempt,'job':job,
        'accepted_zip_sha256':state['accepted_zip_sha256'],
        'passport_registry_sha256':state['passport_registry_sha256'],
        'production_ready':False,'visual_approved':False,'dual_runtime_enabled':False,
        'files':{k:sha_bytes(v) for k,v in files.items()}}
    files['input/'+BINDING]=json_bytes(binding)
    dest=base/'gc47t_windows_transport_r001.zip'
    need(not dest.exists() and not dest.is_symlink(),'TRANSPORT_ALREADY_EXISTS_NO_RETRY')
    with dest.open('xb') as h:
        with ZipFile(h,'w',compression=ZIP_DEFLATED,compresslevel=6) as z:
            for name,payload in sorted(files.items()):
                info=ZipInfo(name,date_time=(2026,10,30,0,0,0));info.compress_type=ZIP_DEFLATED
                info.external_attr=(0o100600<<16)
                z.writestr(info,payload,compress_type=ZIP_DEFLATED,compresslevel=6)
    return dest

def windows_preflight():
    """Read-only PREPRESS GUI / host check before allocating a client attempt."""
    script=r'''$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ine 'PREPRESS'){throw 'GC47T_HOST_MISMATCH'}
if([Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){throw 'GC47T_USER_MISMATCH'}
if((Get-Service Schedule).Status -ne 'Running'){throw 'GC47T_SCHEDULER_STOPPED'}
if(@(Get-Process Illustrator -EA SilentlyContinue).Count -ne 0){throw 'GC47T_ILLUSTRATOR_OPEN'}
$q=@(& quser.exe 2>$null);if($LASTEXITCODE -ne 0){throw 'GC47T_QUSER_FAILED'}
$ids=@();foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success){$ids+=([int]$m.Groups[1].Value)}}
$ids=@($ids|Select-Object -Unique);if($ids.Count -ne 1 -or $ids[0] -le 0){throw 'GC47T_NO_ACTIVE_WORK_SESSION'}
if(@(Get-Process explorer -EA SilentlyContinue | Where-Object {$_.SessionId -eq $ids[0]}).Count -lt 1){throw 'GC47T_NO_ACTIVE_EXPLORER'}
if(!(Test-Path -LiteralPath 'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs' -PathType Container)){throw 'GC47T_JOBS_ROOT_MISSING'}
Write-Output 'T1_PRECHECK=READY_ACTIVE_WORK_ILLUSTRATOR_CLOSED' '''
    need('T1_PRECHECK=READY_ACTIVE_WORK_ILLUSTRATOR_CLOSED' in remote_ps(script), 'WINDOWS_GUI_PREFLIGHT_BLOCKED')
    print('GC47T_PREPRESS=READY_ACTIVE_WORK_ILLUSTRATOR_CLOSED',flush=True)


def stage_remote(bundle,attempt):
    ps_safe_id(attempt)
    remote_name='gc47t_'+attempt+'_transport_r001.zip'
    script=rf'''$ErrorActionPreference='Stop';$p=Join-Path $HOME '{remote_name}';$a='{WINDOWS_BASE}\\{attempt}';
if(Test-Path -LiteralPath $p){{throw 'GC47T_STAGE_ZIP_EXISTS'}}
if(Test-Path -LiteralPath $a){{throw 'GC47T_STAGE_ATTEMPT_EXISTS'}}
if(!(Test-Path -LiteralPath 'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs' -PathType Container)){{throw 'GC47T_JOBS_ROOT_MISSING'}}
Write-Output 'T1_STAGE_PREFLIGHT=PASS' '''
    need('T1_STAGE_PREFLIGHT=PASS' in remote_ps(script),'WINDOWS_STAGE_PREFLIGHT_FAILED')
    scp_to(remote_name,bundle)
    digest=sha_file(bundle)
    script=rf'''$ErrorActionPreference='Stop';$p=Join-Path $HOME '{remote_name}';$a='{WINDOWS_BASE}\\{attempt}';
if(!(Test-Path -LiteralPath $p -PathType Leaf)){{throw 'GC47T_TRANSPORT_NOT_FOUND'}}
if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne '{digest}'){{throw 'GC47T_STAGE_SHA_MISMATCH'}}
if(Test-Path -LiteralPath $a){{throw 'GC47T_ATTEMPT_EXISTS'}}
$b='{WINDOWS_BASE}';if(!(Test-Path -LiteralPath $b)){{[void](New-Item -Path $b -ItemType Directory -ErrorAction Stop)}}
[void](New-Item -Path $a -ItemType Directory -ErrorAction Stop)
Expand-Archive -LiteralPath $p -DestinationPath $a -ErrorAction Stop
[void](New-Item -Path (Join-Path $a 'export') -ItemType Directory -ErrorAction Stop)
$b=Get-Content -LiteralPath (Join-Path $a 'input\\{BINDING}') -Raw -Encoding UTF8 | ConvertFrom-Json
if($b.schema -cne 'gc47t_windows_binding_r001' -or $b.attempt -cne '{attempt}'){{throw 'GC47T_BINDING_INVALID'}}
foreach($e in $b.files.PSObject.Properties){{$f=Join-Path $a ($e.Name.Replace('/','\\'));if(!(Test-Path -LiteralPath $f -PathType Leaf)){{throw 'GC47T_STAGED_FILE_MISSING'}};if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$e.Value){{throw 'GC47T_STAGED_FILE_SHA_DRIFT'}}}}
Write-Output 'T1_STAGE=PASS_SINGLE_SOURCE_BOUND_ATTEMPT' '''
    need('T1_STAGE=PASS_SINGLE_SOURCE_BOUND_ATTEMPT' in remote_ps(script,timeout=180),'WINDOWS_STAGE_NOT_CONFIRMED')
    print('GC47T_STAGE=PASS_PREPRESS_PRIVATE_ATTEMPT',flush=True)

def controller_command(attempt,mode):
    ps_safe_id(attempt);need(mode in ('launch','status','collect'),'CONTROLLER_MODE_INVALID')
    script=rf'''$ErrorActionPreference='Stop';$a='{WINDOWS_BASE}\\{attempt}';$c=Join-Path $a 'input\\{CTRL}';
if(!(Test-Path -LiteralPath $c -PathType Leaf)){{throw 'GC47T_CONTROLLER_MISSING'}}
& $c -Mode '{mode}' -AttemptId '{attempt}'
if($LASTEXITCODE -ne 0){{exit 2}} '''
    return remote_ps(script,timeout=90)

def kv_output(out):
    result={}
    for line in out.splitlines():
        if line.startswith('T1_') and '=' in line:
            k,v=line.strip().split('=',1)
            need(k not in result,'REMOTE_DUPLICATE_RESULT_KEY');result[k]=v
    return result

def status_remote(attempt):
    r=kv_output(controller_command(attempt,'status'))
    need(r.get('T1_STATUS')=='READ_ONLY_NON_RELEASE','WINDOWS_STATUS_UNTRUSTED')
    need(r.get('T1_NATIVE_STATE') in ('NOT_RECORDED','BLOCKED_REVIEW_PARTIAL_OUTPUT','AI_REOPENED_VISUAL_REVIEW_REQUIRED'),'WINDOWS_STATE_INVALID')
    return r

def collect_remote(s,ws,job,attempt):
    base=s.pilot_dir(ws,job,attempt)
    state=s.read_obj(base/'state.json')
    need(state.get('native_jsx_sha256'),'GC47S_NATIVE_SHA_MISSING')
    need(status_remote(attempt).get('T1_NATIVE_STATE')=='AI_REOPENED_VISUAL_REVIEW_REQUIRED','NATIVE_RESULT_NOT_READY_FOR_COLLECTION')
    r=kv_output(controller_command(attempt,'collect'))
    expected=r.get('T1_REVIEW_ZIP_SHA256')
    need(r.get('T1_COLLECT') in ('ZIP_READY_NON_RELEASE','ZIP_EXISTS_READ_ONLY') and isinstance(expected,str) and SHA_RE.fullmatch(expected),'WINDOWS_COLLECTION_NOT_ATTESTED')
    local=base/'gc47t_windows_review_r001.zip'
    if not local.exists() and not local.is_symlink():
        need(regular(GC47AC_TRANSPORT) and sha_file(GC47AC_TRANSPORT)==GC47AC_TRANSPORT_SHA,
             'GC47AC_TRANSPORT_DRIFT')
        spec=importlib.util.spec_from_file_location('gc47ac_verified_native_review_transport',GC47AC_TRANSPORT)
        need(spec is not None and spec.loader is not None,'GC47AC_TRANSPORT_IMPORT')
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        try:
            mod.receive_once(attempt,expected,local,remote_ps=remote_ps,ssh_options=ssh_options,
                             host=HOST,root=ROOT,required=REQUIRED,max_transfer=MAX_TRANSFER)
        except mod.Blocked as e:
            raise Blocked('GC47AC_'+str(e)) from e
    need(regular(local) and sha_file(local)==expected,'REVIEW_ARCHIVE_SHA_MISMATCH')
    run=s.native_run_dir(ws,job,attempt)
    final=run/'out'
    if not final.exists():
        tmp=run/'gc47t_verify_incoming_r001'
        need(not tmp.exists() and not tmp.is_symlink(),'INCOMING_TEMP_EXISTS')
        tmp.mkdir(mode=0o700)
        try:
            with ZipFile(local) as z:
                infos=z.infolist()
                need(len(infos)==len(REQUIRED) and {e.filename for e in infos}==set(REQUIRED),'REVIEW_ZIP_MEMBERS_INVALID')
                need(sum(e.file_size for e in infos) < 600*1024*1024,'REVIEW_UNPACKED_TOO_LARGE')
                for item in infos:
                    need(not item.is_dir() and 100<item.file_size<MAX_TRANSFER,'REVIEW_ZIP_ENTRY_INVALID')
                    data=z.read(item)
                    with (tmp/item.filename).open('xb') as fd:fd.write(data)
            s.verify_native(tmp,state)
            tmp.rename(final)
        finally:
            if tmp.exists():
                import shutil;shutil.rmtree(tmp)
    else:
        need(folder(final),'NATIVE_OUT_NOT_DIRECTORY')
        s.verify_native(final,state)
    if not s.review_dir(ws,job,attempt).exists():s.collect(ws.parent.name,job,attempt)
    need(folder(s.review_dir(ws,job,attempt)),'CLIENT_REVIEW_OUTPUT_NOT_PUBLISHED')
    print('GC47T_REVIEW=CLIENT_OUTPUT_COMPLETE_VISUAL_REVIEW_REQUIRED',flush=True)
    print('GC47T_CHECKPOINT=LAB_FOUR_PAGE_REVIEW_READY_NOT_APPROVED',flush=True)

def gc47af_mod():
    need(regular(GC47AF_HELPER) and sha_file(GC47AF_HELPER)==GC47AF_HELPER_SHA,'GC47AF_HELPER_DRIFT')
    spec=importlib.util.spec_from_file_location('gc47af_passport_scene_binding',GC47AF_HELPER)
    need(spec is not None and spec.loader is not None,'GC47AF_HELPER_IMPORT')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def run_pilot(s,gc29,client,job_id,timeout_minutes):
    ws,job,_,variants=validate_job(s,gc29,client,job_id)
    print('GC47T_VARIANT=SUPPORTED_GC29_'+variants['front']+'_'+variants['signature'],flush=True)
    # Fail early on credentials before allocating an attempt.
    ssh_options()
    windows_preflight()
    # GC47V: instrument only NEW GC47T native attempts. The canonical GC29
    # template and the GC47S source-pinned operator remain unchanged.
    # gc29.prepare binds TEMPLATE into the newly generated private JSX;
    # its SHA is recorded by GC47S, scene manifest and transport binding.
    need(regular(GC47V_TRACE_TEMPLATE) and sha_file(GC47V_TRACE_TEMPLATE)==GC47V_TRACE_SHA,
         'GC47W_TRACE_TEMPLATE_DRIFT')
    if job_id=='gdl_gc_zap_20261011':
        need(regular(GC47Y_TEMPLATE) and sha_file(GC47Y_TEMPLATE)==GC47Y_TEMPLATE_SHA,
             'GC47Y_TEMPLATE_DRIFT')
        need(regular(GC47Y_HELPER) and sha_file(GC47Y_HELPER)==GC47Y_HELPER_SHA,
             'GC47Y_HELPER_DRIFT')
        spec=importlib.util.spec_from_file_location('gc47y_source_bound_revision',GC47Y_HELPER)
        need(spec is not None and spec.loader is not None,'GC47Y_IMPORT_ERROR')
        am=importlib.util.module_from_spec(spec);spec.loader.exec_module(am)
        _,_,archive=gc29.accepted_jobs(ws)
        am.check_sources(ws,job,archive)  # pre-attempt fail-closed
        gc29.TEMPLATE=GC47Y_TEMPLATE
        # Chain BEFORE GC47Y's accepted-source amendment, so GC29 embeds the
        # passport-derived scene in the attempt-specific JSX and manifest.
        reg=s.read_obj(s.REGISTRY,5_000_000)['greeting_card_machine_pipeline_v0_1']
        gc29.compile_scene=gc47af_mod().wrap_compile(gc29.compile_scene,reg,job_id)
        gc29.prepare=am.wrap_prepare(gc29,gc29.prepare,ws,job,archive)
        print('GC47Y_ZAP_REVIEW_AMENDMENT=PHOTO_COMPOUND_CLIP_18_5PT_NON_RELEASE',flush=True)
        print('GC47AF_RENDER_PROFILE=BOUND_CURRENT_GC47K_VERSIONED_NON_RELEASE',flush=True)
    else:
        gc29.TEMPLATE=GC47V_TRACE_TEMPLATE
    _,passport=s.current_passport()
    # Accepted archive must be the exact one returned by GC29; never generate a new one.
    _,_,archive=gc29.accepted_jobs(ws)
    outcome=s.start_one(gc29,ws,job,archive,passport)
    need(outcome is not None and outcome['state']=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED','GC47S_NATIVE_PREPARE_BLOCKED')
    attempt=outcome['attempt']
    print('GC47T_JOB='+job_id+' ATTEMPT='+attempt+' STATE=PREPARED',flush=True)
    print('GC47Y_P04_FIT=FIXED_FALLBACK_18_5_PT_NATIVE_REVIEW_REQUIRED' if job_id=='gdl_gc_zap_20261011' else 'GC47W_P04_FIT=SOURCE_BOUND_GC47N_INSPIRED_NEW_ATTEMPT_ONLY',flush=True)
    print('GC47V_TRACE=ENABLED_NEW_NATIVE_ATTEMPT_LOCAL_PREPRESS_ONLY',flush=True)
    bundle=make_transport(s,ws,job_id,attempt)
    stage_remote(bundle,attempt)
    result=kv_output(controller_command(attempt,'launch'))
    need(result.get('T1_LAUNCH')=='START_REQUESTED_SINGLE_USE','WINDOWS_LAUNCH_NOT_ATTESTED_NO_RETRY')
    print('GC47T_LAUNCH=START_REQUESTED_SINGLE_USE',flush=True)
    start=time.monotonic()
    while time.monotonic()-start < timeout_minutes*60:
        r=status_remote(attempt)
        if r['T1_NATIVE_STATE']=='AI_REOPENED_VISUAL_REVIEW_REQUIRED':
            collect_remote(s,ws,job_id,attempt);return
        if r['T1_NATIVE_STATE']=='BLOCKED_REVIEW_PARTIAL_OUTPUT':
            raise Blocked('WINDOWS_NATIVE_BLOCKED_PARTIAL_OUTPUT_STATUS_ONLY')
        time.sleep(10)
    raise Blocked('PENDING_WINDOWS_NATIVE_USE_STATUS_AND_COLLECT_DO_NOT_RELAUNCH')

def trace_last_remote(attempt):
    """Optional GC47V diagnostic of locally staged JSX, never claims native success."""
    ps_safe_id(attempt)
    script=rf'''$ErrorActionPreference='Stop';$f='{WINDOWS_BASE}\{attempt}\work\gc29_checkpoint_trace_r001.log';
if(!(Test-Path -LiteralPath $f -PathType Leaf)){{Write-Output 'T1_GC47V_TRACE=ABSENT';exit 0}}
$i=Get-Item -LiteralPath $f -Force
if(($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $i.Length -gt 10000){{throw 'GC47T_TRACE_UNSAFE'}}
$all=@(Get-Content -LiteralPath $f -Encoding UTF8)
if($all.Count -lt 2 -or $all[0] -cne 'GC47V_TRACE_V1' -or $all.Count -gt 150){{throw 'GC47T_TRACE_BAD_FORMAT'}}
foreach($line in $all){{if($line -cnotmatch '^(GC47V_TRACE_V1|GC47V_[A-Z0-9_]+)$'){{throw 'GC47T_TRACE_BAD_LINE'}}}}
Write-Output ('T1_GC47V_TRACE='+[string]$all[-1])'''
    result=kv_output(remote_ps(script))
    value=result.get('T1_GC47V_TRACE')
    need(value=='ABSENT' or bool(re.fullmatch(r'GC47V_[A-Z0-9_]+',value or '')),'GC47V_TRACE_UNTRUSTED')
    return value

def mode_status(s,client,job,attempt):
    ws=s.workspace(client)
    state=s.read_obj(s.pilot_dir(ws,job,attempt)/'state.json')
    need(state.get('job_id')==job and state.get('attempt_id')==attempt,'ATTEMPT_MISMATCH')
    r=status_remote(attempt)
    print('GC47T_ATTEMPT='+attempt)
    for k,v in sorted(r.items()):print(k+'='+v)
    print('GC47V_TRACE_LAST='+trace_last_remote(attempt))
    print('GC47T_CLIENT_REVIEW='+('PRESENT' if folder(s.review_dir(ws,job,attempt)) else 'ABSENT'))
    print('GC47T_CHECKPOINT=READ_ONLY_NATIVE_STATUS_NON_RELEASE')

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('check','pilot','status','collect'))
    ap.add_argument('--client-name');ap.add_argument('--job-id');ap.add_argument('--attempt-id')
    ap.add_argument('--confirm-native-once',action='store_true')
    ap.add_argument('--timeout-minutes',type=int,default=24)
    opt=ap.parse_args(argv)
    try:
        s,gc29=source_check()
        if opt.mode=='check':
            if opt.client_name and opt.job_id:
                _,_,_,v=validate_job(s,gc29,opt.client_name,opt.job_id)
                print('GC47T_SELECTED_PROFILE='+v['front']+'/'+v['image']+'/'+v['signature'])
            print('GC47T_CHECKPOINT=SOURCE_AND_PASSPORT_READY_NO_WINDOWS_EXEC')
        else:
            need(bool(opt.client_name and opt.job_id),'CLIENT_AND_JOB_REQUIRED')
            if opt.mode=='pilot':
                need(opt.confirm_native_once,'EXPLICIT_SINGLE_NATIVE_EXECUTION_CONFIRMATION_REQUIRED')
                need(1<=opt.timeout_minutes<=30,'PILOT_TIMEOUT_INVALID')
                run_pilot(s,gc29,opt.client_name,opt.job_id,opt.timeout_minutes)
            else:
                need(bool(opt.attempt_id),'ATTEMPT_ID_REQUIRED')
                ps_safe_id(opt.attempt_id)
                if opt.mode=='status':mode_status(s,opt.client_name,opt.job_id,opt.attempt_id)
                else:
                    need(opt.confirm_native_once,'COLLECTION_CONFIRMATION_REQUIRED')
                    ws=s.workspace(opt.client_name)
                    collect_remote(s,ws,opt.job_id,opt.attempt_id)
        print('GC47T_PRODUCTION_READY=FALSE DUAL_RUNTIME=DISABLED')
        return 0
    except (Blocked,ValueError,OSError,KeyError,TypeError,TimeoutError,subprocess.CalledProcessError,subprocess.TimeoutExpired,ImportError) as e:
        print('GC47T=BLOCKED_'+(str(e) if isinstance(e,Blocked) else type(e).__name__.upper()),file=sys.stderr)
        print('GC47T_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
