#!/usr/bin/env python3
"""GC30 r002B: transfer exactly one audited pilot ZIP into PREPRESS/jobs via SFTP.

Modes check, deliver, verify. Never unpacks, executes JSX, runs GC30 worker,
changes GC32/config, accesses Windows SMB, or writes outside D-root/jobs.
"""
from __future__ import annotations
import argparse
import importlib.util
from hashlib import sha256
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PHASE_A = ROOT/'scripts/graphic_design_lab/greeting_cards/gc30_sftp_payload_r002.py'
PHASE_A_SHA = '2e4ad18a5e25fa8642ff94a916b16936374752e20cc4cad22e9dcf6a8f7d0052'
TRANSPORT = ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py'
SOURCE = ROOT/'tmp/gc30_r002_exact_deg_20261027/gc30_exact_deg_sftp_payload_r002.zip'
PAYLOAD_SHA = 'd3b9329a51272fb195718d124d465da41c4002816c6d6b07c4c66c01e8982ca7'
PILOT = 'gdl_gc_deg_20261011__34b9b61741d5ca'
WIN_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
SFTP_ROOT = '/D:/ForPrint_Automation/GraficsDesignLab/Automation'
REMOTE_DIR = SFTP_ROOT+'/jobs/'+PILOT
REMOTE_FILE = REMOTE_DIR+'/payload.zip'
REMOTE_WIN = WIN_ROOT+'\\jobs\\'+PILOT+'\\payload.zip'
HOST = 'work@192.168.50.69'
KEY = '/root/.ssh/forprint_prepress_ed25519'
KNOWN = '/root/.ssh/known_hosts_forprint_prepress'

class Blocked(ValueError): pass
def need(ok,code):
    if not ok: raise Blocked(code)
def ordinary(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:return False
def sha(p):
    h=sha256()
    with p.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

def local_verify():
    need(ordinary(PHASE_A) and sha(PHASE_A)==PHASE_A_SHA,'GC30_B_PHASE_A_SOURCE_DRIFT')
    need(ordinary(SOURCE) and SOURCE.is_relative_to(ROOT/'tmp'),'GC30_B_PAYLOAD_MISSING_OR_OUTSIDE_TMP')
    need(SOURCE.stat().st_size<=150*1024*1024 and SOURCE.stat().st_size>0,'GC30_B_PAYLOAD_SIZE_INVALID')
    need(sha(SOURCE)==PAYLOAD_SHA,'GC30_B_PAYLOAD_HASH_DRIFT')
    a=load_module('gc30_r002_a',PHASE_A)
    # Independently check that the payload still matches the exact accepted job,
    # source hashes, ticket, and current queue. Do not trust the bundle alone.
    from zipfile import ZipFile
    client='Виктория Беспалова _+380 67 793 00 15'
    source_files,meta=a.source(client,root=ROOT)
    need(meta['ticket_id']==PILOT and len(meta['source_file_sha256'])==15,'GC30_B_SOURCE_IDENTITY_DRIFT')
    with ZipFile(SOURCE) as z:
        names=z.namelist()
        need(len(names)==len(set(names)) and set(names)==set(source_files)|{'offline_payload_manifest.json'},'GC30_B_ZIP_MEMBERS_DRIFT')
        for n,data in source_files.items():
            need(z.read(n)==data,'GC30_B_ZIP_SOURCE_DRIFT_'+n)
        import json
        bm=json.loads(z.read('offline_payload_manifest.json'))
        need(bm==meta and bm['target_subtree']=='jobs/'+PILOT and bm['production_ready'] is False and bm['illustrator_launch'] is False,'GC30_B_ZIP_MANIFEST_DRIFT')
    print('GC30_R002B_LOCAL_SOURCE=PASS TICKET='+PILOT+' ASSETS=12')
    print('GC30_R002B_PAYLOAD_SHA256='+PAYLOAD_SHA)
    return SOURCE.stat().st_size

def remote_cmd(ssh,mode,runner=subprocess.run):
    need(mode in ('check','verify'),'GC30_B_MODE_INVALID')
    p=WIN_ROOT+r'\jobs'
    target_dir=WIN_ROOT+'\\jobs\\'+PILOT
    # All paths are compile-time constants; no untrusted strings interpolated.
    body=(
        "$ErrorActionPreference='Stop';"
        "if($env:COMPUTERNAME -ine 'PREPRESS' -or [Environment]::UserName -ine 'Work'){Write-Output 'GC30_B_REMOTE=WRONG_WORKER';exit 21};"
        "$r='"+WIN_ROOT+"';$j='"+p+"';$d='"+target_dir+"';$f='"+REMOTE_WIN+"';"
        "foreach($x in @($r,$j)){if(-not(Test-Path -LiteralPath $x -PathType Container)){Write-Output 'GC30_B_REMOTE=BASE_MISSING';exit 22};"
        "$i=Get-Item -LiteralPath $x -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){Write-Output 'GC30_B_REMOTE=UNSAFE_LINK';exit 23}};"
    )
    if mode=='check':
        body+=("if(Test-Path -LiteralPath $d){Write-Output 'GC30_B_TARGET=EXISTS_BLOCKED';exit 24};"
               "Write-Output 'GC30_B_TARGET=ABSENT_SAFE';")
    else:
        body+=("if(-not(Test-Path -LiteralPath $d -PathType Container)){Write-Output 'GC30_B_TARGET=MISSING';exit 25};"
               "$i=Get-Item -LiteralPath $d -Force;if($i.Attributes -band [IO.FileAttributes]::ReparsePoint){exit 26};"
               "if(-not(Test-Path -LiteralPath $f -PathType Leaf)){Write-Output 'GC30_B_PAYLOAD=MISSING';exit 27};"
               "$fi=Get-Item -LiteralPath $f -Force;if($fi.Attributes -band [IO.FileAttributes]::ReparsePoint){Write-Output 'GC30_B_PAYLOAD=UNSAFE_LINK';exit 29};"
               "$files=@(Get-ChildItem -LiteralPath $d -Force);"
               "if($files.Count -ne 1 -or $files[0].Name -cne 'payload.zip'){Write-Output 'GC30_B_DIR_CONTENT=UNEXPECTED';exit 28};"
               "$h=(Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant();"
               "$s=(Get-Item -LiteralPath $f).Length;"
               "Write-Output ('GC30_B_PAYLOAD_SHA256='+$h);Write-Output ('GC30_B_PAYLOAD_BYTES='+$s);")
    try:
        res=ssh._powershell_ssh(body,runner=runner,timeout=60)
    except Exception as e:
        raise Blocked('GC30_B_REMOTE_TRANSPORT_'+type(e).__name__) from e
    out=res.stdout.decode('utf-8-sig',errors='replace')
    need(res.returncode==0,'GC30_B_REMOTE_RC_'+str(res.returncode)+' '+out[-200:])
    return out

def remote_check(ssh):
    out=remote_cmd(ssh,'check')
    need(out.count('GC30_B_TARGET=ABSENT_SAFE')==1,'GC30_B_REMOTE_TARGET_NOT_EMPTY')
    print('GC30_R002B_REMOTE_PREFLIGHT=PASS TARGET_ABSENT')

def remote_verify(ssh,bytes_count):
    out=remote_cmd(ssh,'verify')
    need('GC30_B_PAYLOAD_SHA256='+PAYLOAD_SHA in out,'GC30_B_REMOTE_SHA_MISMATCH')
    need('GC30_B_PAYLOAD_BYTES='+str(bytes_count) in out,'GC30_B_REMOTE_SIZE_MISMATCH')
    print('GC30_R002B_REMOTE_HASH=PASS SHA256='+PAYLOAD_SHA)
    print('GC30_R002B_REMOTE_DIRECTORY=PASS ONE_PAYLOAD_ONLY')

def sftp_transfer(runner=subprocess.run):
    # mkdir must succeed as an exclusive create. Batch mode stops on errors;
    # a failed partial upload is deliberately left for manual reconciliation.
    batch=('mkdir "'+REMOTE_DIR+'"\nput "'+str(SOURCE)+'" "'+REMOTE_FILE+'"\n').encode()
    command=['sftp','-b','-','-i',KEY,'-o','BatchMode=yes',
        '-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes',
        '-o','UserKnownHostsFile='+KNOWN,HOST]
    try:res=runner(command,input=batch,capture_output=True,timeout=120,check=False)
    except subprocess.TimeoutExpired as e:raise Blocked('GC30_B_SFTP_TIMEOUT_RECONCILE') from e
    need(res.returncode==0,'GC30_B_SFTP_RC_'+str(res.returncode)+'_RECONCILE_NO_RETRY')
    print('GC30_R002B_SFTP=DELIVERED_UNVERIFIED')

def run(mode,confirm):
    need(mode in ('check','deliver','verify'),'GC30_B_MODE_INVALID')
    need(confirm==(mode=='deliver'),'GC30_B_CONFIRMATION_REQUIRED')
    count=local_verify()
    ssh=load_module('gc30_r002_ssh',TRANSPORT)
    need(ssh.WINDOWS_ROOT==WIN_ROOT,'GC30_B_REMOTE_ROOT_DRIFT')
    if mode=='check':
        remote_check(ssh)
        print('GC30_R002B_WINDOWS_WRITE=NOT_EXECUTED')
        return
    if mode=='deliver':
        remote_check(ssh)
        sftp_transfer()
    remote_verify(ssh,count)
    print('GC30_R002B_TRANSFER=PASS_NON_AUTHORIZING')
    print('GC30_R002B_LOCAL_STAGE=NOT_EXECUTED')
    print('GC30_R002B_ILLUSTRATOR=NOT_LAUNCHED')
    print('GC30_R002B_PRODUCTION_READY=false')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','deliver','verify'),required=True)
    p.add_argument('--confirm-transfer',action='store_true')
    args=p.parse_args()
    try:run(args.mode,args.confirm_transfer);return 0
    except (Blocked,OSError,ValueError,KeyError) as e:
        print('GC30_R002B=BLOCKED reason='+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
