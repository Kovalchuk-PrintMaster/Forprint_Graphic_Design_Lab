#!/usr/bin/env python3
"""GC47AX lifecycle: guarded PREPRESS Illustrator lifecycle for one GC47AR native pilot.

Review-only inspect is read-only. `prepare` may gracefully quit Illustrator only
when every open document is already saved, from the actual Work GUI session.
`pilot` performs this preparation then calls the source-pinned GC47AR pilot.
Never terminates processes forcibly, never retries a failed native attempt.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
AR_FILE = 'gc47ax_versioned_native_pilot_r001.py'
AR_SHA = '7919ce9f770ee05cc979065434b7fabe1538f2c1adb7e07cd71ae781c9bd8998'
CONTROLLER = 'gc47as_windows_controller_r001.ps1'
WORKER = 'gc47as_windows_worker_r001.ps1'
# Set at build time; pin the checked source helper against replacement.
SOURCE_SHA = {'gc47as_windows_controller_r001.ps1': '33540f0f676c3fe8632cfb3c02bc21542ec9088bc964d7a4a58e46cbef67b2a3',
              'gc47as_windows_worker_r001.ps1': '39248d31f9f88e9fda5134a2a74bdf2cb325a9608d9949a1ff547c111ee7b071'}
REMOTE_BASE = r'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gc47as_lifecycle_r001'
JOB = 'gdl_gc_zap_20261011'

class Blocked(RuntimeError): pass

def need(ok, code):
    if not ok: raise Blocked('GC47AS_'+code)

def isfile(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except OSError: return False

def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1<<20), b''): h.update(part)
    return h.hexdigest()

def load_ar():
    p=CAN/AR_FILE
    need(isfile(p) and sha_file(p)==AR_SHA,'GC47AR_SOURCE_SHA_DRIFT')
    spec=importlib.util.spec_from_file_location('gc47as_pinned_ar',p)
    need(spec is not None and spec.loader is not None,'GC47AR_IMPORT')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    need(hasattr(mod,'verify_shadow_and_job') and hasattr(mod,'run_pilot'),'GC47AR_INTERFACE_DRIFT')
    return mod

def verify_local():
    need(ROOT.name=='forprint_graphic_design_lab' and (ROOT/'.git').is_dir(),'WRONG_REPO')
    for n, expected in SOURCE_SHA.items():
        path=CAN/n
        need(isfile(path) and sha_file(path)==expected,'HELPER_SHA_DRIFT_'+n)
    return load_ar()

def ps_literal(s):
    need(isinstance(s,str) and "'" not in s and '\n' not in s and '\r' not in s,'REMOTE_LITERAL')
    return "'"+s+"'"

def remote(t,script,timeout=80):
    # Delegates to already source-pinned GC47T known-host / SSH transport.
    return t.remote_ps(script,timeout=timeout)

def remote_inspect(t):
    ps=r'''$ErrorActionPreference='Stop';
if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){throw 'GC47AS_IDENTITY'}
$q=@(& quser.exe 2>$null);if($LASTEXITCODE -ne 0){throw 'GC47AS_QUSER'}
$ids=@();foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success){$ids+=([int]$m.Groups[1].Value)}}
$ids=@($ids|Select-Object -Unique);if($ids.Count -ne 1 -or $ids[0] -le 0){throw 'GC47AS_ACTIVE_SESSION'}
$p=@(Get-Process Illustrator -EA SilentlyContinue)
if($p.Count -eq 0){Write-Output 'GC47AS_INSPECT=CLOSED'}
elseif($p.Count -eq 1 -and $p[0].SessionId -eq $ids[0]){Write-Output 'GC47AS_INSPECT=OPEN_IN_WORK_SESSION'}
else{Write-Output 'GC47AS_INSPECT=BLOCKED_AMBIGUOUS_OR_FOREIGN_SESSION'}
Write-Output 'GC47AS_INSPECT_NO_MUTATION=TRUE'
'''
    data=remote(t,ps)
    need('GC47AS_INSPECT_NO_MUTATION=TRUE' in data,'INSPECT_UNTRUSTED')
    print(data.strip(),flush=True)
    return data

def deploy(t, name, run_id):
    """Upload pinned script and install only into dedicated GC47AS subdirectory."""
    need(name in SOURCE_SHA,'UNLISTED_HELPER')
    need(re.fullmatch(r'[a-f0-9]{16}',run_id) is not None,'RUN_ID')
    local=CAN/name; need(isfile(local) and sha_file(local)==SOURCE_SHA[name],'HELPER_CHANGED')
    stage=f'gc47as_{run_id}_{name}'
    t.scp_to(stage,local)
    ps=f'''$ErrorActionPreference='Stop';$base={ps_literal(REMOTE_BASE)};$stage=Join-Path $HOME {ps_literal(stage)};
if(!(Test-Path -LiteralPath $stage -PathType Leaf)){{throw 'GC47AS_STAGE_MISSING'}}
if((Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash.ToLowerInvariant() -cne {ps_literal(SOURCE_SHA[name])}){{throw 'GC47AS_STAGE_SHA'}}
$root=Split-Path -Parent $base;if(!(Test-Path -LiteralPath $root -PathType Container)){{throw 'GC47AS_JOBS_ROOT_MISSING'}}
if(!(Test-Path -LiteralPath $base)){{[void](New-Item -Path $base -ItemType Directory -ErrorAction Stop)}}
$d=Get-Item -LiteralPath $base -Force;if(($d.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){{throw 'GC47AS_BASE_REPARSE'}}
$dest=Join-Path $base {ps_literal(name)};
if(Test-Path -LiteralPath $dest){{
 $f=Get-Item -LiteralPath $dest -Force;if(($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){{throw 'GC47AS_DEST_REPARSE'}}
 if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -cne {ps_literal(SOURCE_SHA[name])}){{throw 'GC47AS_DEST_CONFLICT'}}
}}else{{Copy-Item -LiteralPath $stage -Destination $dest -ErrorAction Stop}}
Remove-Item -LiteralPath $stage -Force -ErrorAction Stop
Write-Output 'GC47AS_DEPLOY=PASS_PINNED_{name}' '''
    out=remote(t,ps)
    need('GC47AS_DEPLOY=PASS_PINNED_'+name in out,'DEPLOY_NOT_ATTESTED')

def prepare(t, run_id=None):
    run_id=run_id or os.urandom(8).hex()
    need(re.fullmatch(r'[a-f0-9]{16}',run_id) is not None,'RUN_ID')
    # Fail closed on another user's session; do not allocate lifecycle task when closed.
    status=remote_inspect(t)
    if 'GC47AS_INSPECT=CLOSED' in status:
        t.windows_preflight()  # independent, transient remote gate
        print('GC47AS_PREPARE=PASS_ALREADY_CLOSED',flush=True)
        return run_id
    need('GC47AS_INSPECT=OPEN_IN_WORK_SESSION' in status,'AMBIGUOUS_REMOTE_PROCESS')
    for name in (WORKER,CONTROLLER): deploy(t,name,run_id)
    script=f'''$ErrorActionPreference='Stop';$base={ps_literal(REMOTE_BASE)};$p=Join-Path $base {ps_literal(CONTROLLER)};
if(!(Test-Path -LiteralPath $p -PathType Leaf)){{throw 'GC47AS_CONTROLLER_MISSING'}}
if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne {ps_literal(SOURCE_SHA[CONTROLLER])}){{throw 'GC47AS_CONTROLLER_SHA_DRIFT'}}
& $p -Mode prepare -RunId {ps_literal(run_id)}
if($LASTEXITCODE -ne 0){{exit 2}}'''
    # Single attempt of the lifecycle task; on timeout do not issue a second prepare.
    try: output=remote(t,script,timeout=110)
    except Exception as exc:
        print('GC47AS_RUN_ID='+run_id,flush=True)
        raise Blocked('GC47AS_PREPARE_UNCERTAIN_CHECK_WINDOWS_TASK_NO_AUTO_RETRY') from exc
    print(output.strip(),flush=True)
    need('GC47AS_RUN_ID='+run_id in output,'RUN_RECEIPT_MISMATCH')
    good=any('GC47AS_STATE='+s in output for s in ('ALREADY_CLOSED','GRACEFULLY_CLOSED_SAVED_DOCUMENTS'))
    need(good,'LIFECYCLE_NOT_READY_NO_NATIVE_DISPATCH')
    print('GC47AS_PREPARE=PASS_ILLUSTRATOR_CLOSED',flush=True)
    return run_id

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',required=True,choices=('check','inspect','prepare','pilot'))
    parser.add_argument('--client-name')
    parser.add_argument('--confirm-graceful-close',action='store_true')
    parser.add_argument('--confirm-native-once',action='store_true')
    parser.add_argument('--confirmation')
    parser.add_argument('--timeout-minutes',type=int,default=24)
    args=parser.parse_args(argv)
    try:
        ar=verify_local()
        if args.mode=='check':
            ar.sources();ar.read_report(ROOT/ar.SHADOW_REL)
            print('GC47AS_CHECK=PASS_SOURCES_LIFECYCLE_HELPERS_NO_WINDOWS',flush=True)
            return 0
        need(bool(args.client_name),'CLIENT_REQUIRED')
        data=ar.verify_shadow_and_job(args.client_name)
        t=data[4];t.ssh_options()
        if args.mode=='inspect':
            remote_inspect(t)
            print('GC47AS_CHECKPOINT=PREPRESS_ILLUSTRATOR_READ_ONLY',flush=True)
            return 0
        if args.mode=='prepare':
            need(args.confirm_graceful_close and args.confirmation=='GC47AS_PREPARE_SAVED_ONLY',
                 'EXPLICIT_GRACEFUL_CLOSE_AUTHORITY_REQUIRED')
        else:
            need(args.confirm_native_once and args.confirmation=='GC47AS_SINGLE_NATIVE_REVIEW',
                 'EXPLICIT_SINGLE_NATIVE_AUTHORITY_REQUIRED')
            need(1<=args.timeout_minutes<=30,'TIMEOUT_OUT_OF_RANGE')
        prepare(t)
        # Source-pinned GC47T now independently verifies readiness again.
        t.windows_preflight()
        print('GC47AS_GC47T_GATE=PASS_TRANSIENT_PREPARED',flush=True)
        if args.mode=='pilot':
            print('GC47AS_NATIVE=DELEGATING_GC47AR_SINGLE_USE',flush=True)
            ar.run_pilot(data,args.timeout_minutes)
            print('GC47AS_CHECKPOINT=VERSIONED_NATIVE_REVIEW_VISUAL_REQUIRED',flush=True)
        else:print('GC47AS_NATIVE_DISPATCH=NOT_PERFORMED',flush=True)
        return 0
    except Exception as exc:
        print('GC47AS=BLOCKED_'+str(exc),file=sys.stderr)
        print('GC47AS_NO_TASKKILL=TRUE NO_NATIVE_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
