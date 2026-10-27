#!/usr/bin/env python3
"""GC30 r002C exact ticket: deliver a local-only stage helper and stage one payload.

Never access Windows SMB, invoke Illustrator, run PollOnce, register a Worker, or
write outside PREPRESS D-root/jobs/<exact ticket>. Fail closed on partial state.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.util
from pathlib import Path
import stat
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
PILOT='gdl_gc_deg_20261011__34b9b61741d5ca'
WIN_ROOT=r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
SFTP_ROOT='/D:/ForPrint_Automation/GraficsDesignLab/Automation'
REMOTE_WIN=WIN_ROOT+'\\jobs\\'+PILOT
REMOTE_SFTP=SFTP_ROOT+'/jobs/'+PILOT
NAME='gc30_exact_ticket_stage_r002c.ps1'
REMOTE_SCRIPT_WIN=REMOTE_WIN+'\\'+NAME
REMOTE_SCRIPT_SFTP=REMOTE_SFTP+'/'+NAME
PS1=ROOT/'scripts/graphic_design_lab/greeting_cards/windows'/NAME
PS1_SHA='1b173374acbad93223cee4a6ec89d169f741db171a9e51b2c8e1b8652ff6abeb'
B=ROOT/'scripts/graphic_design_lab/greeting_cards/gc30_sftp_deliver_r002b.py'
B_SHA='1870fec628e11305e448453bc8d0c249e0e3f275a533d16e7065f8a5d2f28588'
TRANSPORT=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py'
TRANSPORT_SHA='8c895207aeac424bc3b3ceb1518855ba5c26c43a1cd3cbcbb2ced83642aa75e7'
PAYLOAD_SHA='d3b9329a51272fb195718d124d465da41c4002816c6d6b07c4c66c01e8982ca7'
HOST='work@192.168.50.69'
KEY='/root/.ssh/forprint_prepress_ed25519'
KNOWN='/root/.ssh/known_hosts_forprint_prepress'

class Blocked(ValueError): pass
def need(ok,msg):
    if not ok: raise Blocked(msg)
def is_regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:return False
def sha(p):
    h=sha256()
    with p.open('rb') as stream:
        for part in iter(lambda:stream.read(1048576),b''):h.update(part)
    return h.hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

def source_check():
    need(is_regular(PS1) and sha(PS1)==PS1_SHA,'GC30_C_STAGE_SCRIPT_SOURCE_DRIFT')
    need(is_regular(B) and sha(B)==B_SHA,'GC30_C_DELIVERY_CODE_SOURCE_DRIFT')
    need(is_regular(TRANSPORT) and sha(TRANSPORT)==TRANSPORT_SHA,'GC30_C_SSH_SOURCE_DRIFT')
    b=module('gc30_c_prev_delivery',B)
    need(b.PILOT==PILOT and b.REMOTE_DIR==REMOTE_SFTP and b.PAYLOAD_SHA==PAYLOAD_SHA,'GC30_C_TRANSFER_BINDING_DRIFT')
    size=b.local_verify() # verifies A, live SMB ticket, queue, all 12 assets and the offline payload
    return size

def ssh_call(body,*,runner=subprocess.run,timeout=60):
    ssh=module('gc30_c_ssh_transport',TRANSPORT)
    need(ssh.WINDOWS_ROOT==WIN_ROOT,'GC30_C_REMOTE_ROOT_DRIFT')
    try:r=ssh._powershell_ssh(body,runner=runner,timeout=timeout)
    except Exception as e: raise Blocked('GC30_C_SSH_TRANSPORT_'+type(e).__name__) from e
    out=r.stdout.decode('utf-8-sig',errors='replace')
    need(r.returncode==0,'GC30_C_REMOTE_RC_'+str(r.returncode)+' '+out[-250:])
    return out

def remote_body(phase):
    need(phase in ('check','script','stage'),'GC30_C_PROBE_MODE_INVALID')
    base=(
        "$ErrorActionPreference='Stop';"
        "if($env:COMPUTERNAME -ine 'PREPRESS' -or [Environment]::UserName -ine 'Work'){exit 40};"
        "$r='"+WIN_ROOT+"';$j='"+WIN_ROOT+r'\jobs'+"';$d='"+REMOTE_WIN+"';"
        "$p=Join-Path $d 'payload.zip';$s=Join-Path $d '"+NAME+"';"
        "foreach($v in @($r,$j,$d)){if(-not(Test-Path -LiteralPath $v -PathType Container)){exit 41};"
        "$i=Get-Item -LiteralPath $v -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 42}};"
        "if(-not(Test-Path -LiteralPath $p -PathType Leaf)){exit 43};"
        "$i=Get-Item -LiteralPath $p -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 44};"
        "$h=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant();"
        "if($h -cne '"+PAYLOAD_SHA+"'){exit 45};"
    )
    if phase=='check':
        base+=("$a=@(Get-ChildItem -LiteralPath $d -Force);"
               "if($a.Count -ne 1 -or $a[0].Name -cne 'payload.zip'){exit 46};"
               "Write-Output 'GC30_C_REMOTE_READY=PASS_PAYLOAD_ONLY';")
    else:
        base+=("if(-not(Test-Path -LiteralPath $s -PathType Leaf)){exit 47};"
               "$i=Get-Item -LiteralPath $s -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 48};"
               "$h=(Get-FileHash -LiteralPath $s -Algorithm SHA256).Hash.ToLowerInvariant();"
               "if($h -cne '"+PS1_SHA+"'){exit 49};")
        if phase=='script':
            base+=("$a=@(Get-ChildItem -LiteralPath $d -Force);"
                   "if($a.Count -ne 2){exit 50};"
                   "Write-Output 'GC30_C_REMOTE_SCRIPT=PASS_HASHED';"
                   "& $s -Mode Check;")
        else:
            base+=("$a=@(Get-ChildItem -LiteralPath $d -Force);"
                   "if($a.Count -ne 4){exit 51};"
                   "Write-Output 'GC30_C_REMOTE_SCRIPT=PASS_HASHED';"
                   "& $s -Mode Verify;")
    return base

def remote_preflight():
    out=ssh_call(remote_body('check'))
    need('GC30_C_REMOTE_READY=PASS_PAYLOAD_ONLY' in out,'GC30_C_REMOTE_PAYLOAD_NOT_EXCLUSIVE')
    print('GC30_R002C_REMOTE_PREFLIGHT=PASS ONE_PAYLOAD_ONLY')

def script_check():
    out=ssh_call(remote_body('script'))
    need('GC30_C_REMOTE_SCRIPT=PASS_HASHED' in out and 'GC30_R002C_LOCAL_PREFLIGHT=PASS' in out, 'GC30_C_SCRIPT_CHECK_NOT_ATTESTED')
    print('GC30_R002C_HELPER=PASS_HASHED_LOCAL_CHECK')

def stage_verify():
    out=ssh_call(remote_body('stage'))
    need('GC30_C_REMOTE_SCRIPT=PASS_HASHED' in out and 'GC30_R002C_STAGE=PASS_NON_AUTHORIZING' in out and 'GC30_R002C_ILLUSTRATOR=NOT_LAUNCHED' in out,'GC30_C_STAGE_RESULT_NOT_ATTESTED')
    print('GC30_R002C_STAGE=PASS_NON_AUTHORIZING TICKET='+PILOT+' FILES=16 ASSETS=12')

def sftp_script(*,runner=subprocess.run):
    batch=('put "'+str(PS1)+'" "'+REMOTE_SCRIPT_SFTP+'"\n').encode()
    argv=['sftp','-b','-','-i',KEY,'-o','BatchMode=yes','-o','ConnectTimeout=10',
          '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+KNOWN,HOST]
    try:r=runner(argv,input=batch,capture_output=True,timeout=90,check=False)
    except subprocess.TimeoutExpired as e:raise Blocked('GC30_C_SFTP_TIMEOUT_RECONCILE') from e
    need(r.returncode==0,'GC30_C_SFTP_FAILED_RECONCILE_NO_RETRY')
    print('GC30_R002C_SCRIPT_SFTP=DELIVERED_UNVERIFIED')

def stage_execute():
    # Separate Check and Stage commands: no automatic execution on a failed check.
    script_check()
    s=REMOTE_SCRIPT_WIN
    out=ssh_call("$ErrorActionPreference='Stop';& '"+s+"' -Mode Stage -ConfirmStage",timeout=110)
    need('GC30_R002C_STAGE=PASS_NON_AUTHORIZING' in out,'GC30_C_LOCAL_STAGE_NOT_ATTESTED')
    stage_verify()

def run(mode,confirm):
    need(mode in ('check','stage','verify'),'GC30_C_MODE_INVALID')
    need(confirm==(mode=='stage'),'GC30_C_CONFIRMATION_REQUIRED')
    source_check()
    if mode=='check':
        remote_preflight()
        print('GC30_R002C_WINDOWS_WRITE=NOT_EXECUTED')
    elif mode=='stage':
        remote_preflight()
        sftp_script()
        # A partial copy or extraction is deliberately retained for manual reconciliation.
        stage_execute()
    else:
        stage_verify()
    print('GC30_R002C_ILLUSTRATOR=NOT_LAUNCHED')
    print('GC30_R002C_PRODUCTION_READY=false')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('check','stage','verify'))
    p.add_argument('--confirm-local-stage',action='store_true')
    a=p.parse_args()
    try:run(a.mode,a.confirm_local_stage);return 0
    except (Blocked,ValueError,KeyError,OSError,subprocess.SubprocessError) as e:
        print('GC30_R002C=BLOCKED reason='+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
