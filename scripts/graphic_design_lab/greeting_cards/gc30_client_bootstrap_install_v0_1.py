#!/usr/bin/env python3
"""Install one GC30 submit-only launcher + dedicated-host worker bootstrap (create-only)."""
from __future__ import annotations
import argparse
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys

ROOT=Path(__file__).resolve().parents[3]
SHARE=Path('/srv/smb/In_Progress/data')
WINDOWS=ROOT/'scripts/graphic_design_lab/greeting_cards/windows'
SOURCES={
 'gc30_submit_only_v0_1.ps1':'27c0ad408d3d396a649a7e51f21b500c1daa952a5e6cc34fb97903b12aa33013',
 'Створити_листівку.cmd':'3035044742d2ba2a12c0cfec7e6eb857d51409c10117da24fdc1416190613dd3',
 'gc30_dedicated_worker_v0_1.ps1':'f0ba8071f59721aa1570f506c17564020caabb6ed8d846eb933ad3605abe0261',
}
class Blocked(ValueError):pass

def need(v,code):
    if not v:raise Blocked(code)

def is_file(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:return False

def is_dir(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError:return False

def sha(b):return sha256(b).hexdigest()

def run(client,mode,confirm,*,root=ROOT,share=SHARE):
    need(mode in ('check','install'),'GC30_INSTALL_MODE_INVALID')
    need((mode=='install')==confirm,'GC30_INSTALL_CONFIRMATION_MISMATCH')
    need(isinstance(client,str) and bool(client) and client not in ('.','..') and not any(c in client for c in '/\\\0'),'GC30_CLIENT_INVALID')
    ws=share/client/'_forprint_automation'
    need(is_dir(share) and is_dir(ws) and is_dir(ws/'input') and is_dir(ws/'template_studio'),'GC30_CLIENT_WORKSPACE_UNSAFE')
    need(ws.resolve(strict=True).parent.parent==share.resolve(strict=True),'GC30_CLIENT_ESCAPED_SHARE')
    win=root/'scripts/graphic_design_lab/greeting_cards/windows'
    boot=ws/'template_studio'/'worker_bootstrap'
    need(not boot.is_symlink(),'GC30_BOOTSTRAP_SYMLINK')
    targets=[]
    for name,want in SOURCES.items():
        src=win/name;need(is_file(src),'GC30_SOURCE_MISSING')
        data=src.read_bytes();need(sha(data)==want,'GC30_SOURCE_SHA_INVALID')
        parent=ws/'input' if name!='gc30_dedicated_worker_v0_1.ps1' else boot
        if name=='gc30_dedicated_worker_v0_1.ps1':
            need((not boot.exists()) or is_dir(boot),'GC30_BOOTSTRAP_UNSAFE')
        dst=parent/name
        if dst.exists() or dst.is_symlink():
            need(is_file(dst) and sha(dst.read_bytes())==want,'GC30_EXISTING_CLIENT_FILE_CONFLICT')
            status='CURRENT'
        else:status='MISSING'
        targets.append((name,want,data,dst,status))
    if mode=='install':
        if not boot.exists():boot.mkdir(mode=0o750)
        for name,want,data,dst,status in targets:
            if status=='MISSING':
                fd=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
                with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            need(is_file(dst) and sha(dst.read_bytes())==want,'GC30_INSTALL_VERIFY_FAILED')
    for name,_,_,_,state in targets:print(f'GC30_INSTALL_FILE={name} STATE={"CURRENT" if mode=="install" else state}')
    print('GC30_CLIENT_BOOTSTRAP='+('INSTALL_VERIFIED' if mode=='install' else 'CHECK_READ_ONLY'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','install'),required=True)
    p.add_argument('--client-name',required=True)
    p.add_argument('--confirm-install',action='store_true')
    a=p.parse_args()
    try:run(a.client_name,a.mode,a.confirm_install);return 0
    except (Blocked,OSError) as e:
        print('GC30_CLIENT_BOOTSTRAP=BLOCKED reason='+(str(e) if isinstance(e,Blocked) else type(e).__name__),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
