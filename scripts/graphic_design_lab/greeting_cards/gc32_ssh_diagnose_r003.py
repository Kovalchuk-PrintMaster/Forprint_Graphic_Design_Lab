#!/usr/bin/env python3
"""Read-only s01 -> PREPRESS SSH diagnostics for GC32. No remote writes.

Stages: authenticated SSH hostname; remote PowerShell; current GC32 scanner.
Logs only bounded, client-redacted diagnostic stderr on failure. No mutation.
"""
from __future__ import annotations
import argparse
import base64
import importlib.util
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
GC32=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py'

def load_gc32():
    spec=importlib.util.spec_from_file_location('gc32_ssh_current',GC32)
    if spec is None or spec.loader is None: raise RuntimeError('GC32_SOURCE_MISSING')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def options(m):
    return ['ssh','-T','-i',m.KEY,'-o','BatchMode=yes','-o','ConnectTimeout=10',
            '-o',f'UserKnownHostsFile={m.KNOWN}','-o','StrictHostKeyChecking=yes',m.HOST]

def powershell(script):
    arg=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return ['powershell.exe','-NoLogo','-NoProfile','-NonInteractive',
            '-ExecutionPolicy','Bypass','-EncodedCommand',arg]

def safe_diag(stderr:bytes,client:str)->str:
    raw=stderr.decode('utf-8-sig',errors='replace').replace(client,'[CLIENT]')
    lines=[]
    for line in raw.splitlines():
        if not line.strip():continue
        line=re.sub(r'\\\\[^\s]+','[UNC_PATH]',line)
        line=re.sub(r'[A-Za-z]:\\[^\s]+','[WINDOWS_PATH]',line)
        line=line[:220]
        lines.append(line)
    return ' | '.join(lines[:3])[:520] or 'NO_STDERR'

def diagnostic(client, runner=subprocess.run):
    m=load_gc32()
    phases=[('SSH_HOST',options(m)+['hostname'],25),
       ('REMOTE_POWERSHELL',options(m)+powershell("Write-Output ('GC32_REMOTE_PS_OK:'+$env:COMPUTERNAME+':'+$env:USERNAME)"),30)]
    for label,cmd,seconds in phases:
        try: r=runner(cmd,check=False,capture_output=True,timeout=seconds)
        except subprocess.TimeoutExpired: print('GC32_DIAG_'+label+'=TIMEOUT');return 2
        if r.returncode:
            print('GC32_DIAG_'+label+'=BLOCKED RC='+str(r.returncode))
            print('GC32_DIAG_DETAIL='+safe_diag(r.stderr,client));return 2
        output=r.stdout.decode('utf-8-sig',errors='replace').strip()
        if label=='REMOTE_POWERSHELL' and 'GC32_REMOTE_PS_OK:PREPRESS:WORK' not in output.upper():
            print('GC32_DIAG_REMOTE_POWERSHELL=OUTPUT_IDENTITY_UNVERIFIED');return 2
        print('GC32_DIAG_'+label+'=PASS')
    def wrapped(cmd,**kwargs):
        r=runner(cmd,**kwargs)
        if r.returncode:
            print('GC32_DIAG_SCANNER=REMOTE_RC_'+str(r.returncode))
            print('GC32_DIAG_DETAIL='+safe_diag(r.stderr,client))
        return r
    try: snapshot=m.ssh_capture(client,runner=wrapped)
    except (m.Blocked,OSError,subprocess.SubprocessError,UnicodeError,ValueError) as exc:
        print('GC32_DIAG_SCANNER=BLOCKED CLASS='+type(exc).__name__+
              ' CODE='+(str(exc) if isinstance(exc,m.Blocked) else 'GENERIC'))
        return 2
    print('GC32_DIAG_SCANNER=PASS ITEMS='+str(len(snapshot['entries'])))
    print('GC32_DIAG_REMOTE_WRITES=false SERVER_WRITES=false')
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--client-name',required=True)
    a=p.parse_args()
    if '/' in a.client_name or '\\' in a.client_name or not a.client_name.strip():
        print('GC32_DIAG=BLOCKED CLIENT_NAME_INVALID');return 2
    return diagnostic(a.client_name)

if __name__=='__main__':raise SystemExit(main())
