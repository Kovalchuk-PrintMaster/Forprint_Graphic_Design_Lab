#!/usr/bin/env python3
"""GC47U: fast read-only route catalogue and fail-closed dispatch gate.

All results are momentary observations, not promises. GC47T repeats its Windows
preflight at dispatch; a controller may still refuse later because GUI state moved.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from typing import Any

GDL_ROOT = Path(__file__).resolve().parents[3]
PREPRESS_HOST = '192.168.50.69'
PREPRESS_USER = 'work'
PREPRESS_PORT = 22
KEY = '/root/.ssh/forprint_prepress_ed25519'
KNOWN = '/root/.ssh/known_hosts_forprint_prepress'
SHARE = Path('/srv/smb/In_Progress/data')
PYTHON_VENV = GDL_ROOT / '.venv_gdl/bin/python'
BRIDGE = GDL_ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py'
GC29 = GDL_ROOT / 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py'
GC47S = GDL_ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47s_client_pilot_v0_1.py'
ROUTE_KEYS = ('local-gc29', 'illustrator', 'acrobat')
TCP_TIMEOUT = 1.2
SSH_TIMEOUT = 7.0

PS_PROBE = r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
if($env:COMPUTERNAME -ine 'PREPRESS' -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){Write-Output 'U1_NODE=BLOCKED_IDENTITY';exit 0}
if((Get-Service Schedule -EA Stop).Status -ne 'Running'){Write-Output 'U1_NODE=BLOCKED_SCHEDULER';exit 0}
$pr=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent());if(!$pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){Write-Output 'U1_NODE=BLOCKED_ADMIN_TOKEN';exit 0}
$q=@(& quser.exe 2>$null);if($LASTEXITCODE -ne 0){Write-Output 'U1_NODE=BLOCKED_SESSION_QUERY';exit 0}
$ids=@();foreach($line in $q){$m=[regex]::Match([string]$line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b');if($m.Success){$ids+=([int]$m.Groups[1].Value)}}
$ids=@($ids | Select-Object -Unique);if($ids.Count -ne 1 -or $ids[0] -le 0){Write-Output 'U1_NODE=BLOCKED_NO_ACTIVE_SESSION';exit 0}
if(@(Get-Process explorer -EA SilentlyContinue | Where-Object {$_.SessionId -eq $ids[0]}).Count -lt 1){Write-Output 'U1_NODE=BLOCKED_NO_EXPLORER';exit 0}
if(!(Test-Path -LiteralPath 'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs' -PathType Container)){Write-Output 'U1_NODE=BLOCKED_JOBS_ROOT';exit 0}
if(!(Test-Path -LiteralPath 'C:\Program Files\Adobe\Adobe Illustrator 2026' -PathType Container)){Write-Output 'U1_NODE=BLOCKED_ILLUSTRATOR_INSTALL';exit 0}
if(@(Get-Process Illustrator -EA SilentlyContinue).Count -gt 0){Write-Output 'U1_NODE=BUSY_ILLUSTRATOR_OPEN';exit 0}
Write-Output 'U1_NODE=READY' '''

class Blocked(ValueError):
    pass


def regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def folder(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def safe_status(value: str) -> str:
    return value if re.fullmatch(r'[A-Z][A-Z0-9_]*', value) else 'UNKNOWN_UNTRUSTED_RESPONSE'


def local_node(root: Path = GDL_ROOT, share: Path = SHARE) -> tuple[str, str]:
    # The health tool itself executes on s01, so no ICMP to localhost is useful.
    if root.name != 'forprint_graphic_design_lab' or not folder(root / '.git'):
        return 'BLOCKED_GDL_ROOT', 'BLOCKED_GDL_ROOT'
    if not folder(share):
        return 'BLOCKED_SMB_UNMOUNTED', 'BLOCKED_SMB_UNMOUNTED'
    if not all(regular(root / rel) for rel in (
        'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.py',
        'scripts/graphic_design_lab/greeting_cards/gc47s_client_pilot_v0_1.py',
        'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py',
    )):
        return 'BLOCKED_GDL_RENDERER_MISSING', 'BLOCKED_GDL_RENDERER_MISSING'
    # Virtualenv Python is commonly a symlink to the executable interpreter.
    # Follow only this venv executable path; keep strict lstat checks for SSH keys.
    venv_python = root / '.venv_gdl/bin/python'
    if not venv_python.is_file() or not os.access(venv_python, os.X_OK):
        return 'BLOCKED_VENV_MISSING', 'BLOCKED_VENV_MISSING'
    return 'READY_LOCAL_S01', 'READY_GC29_PREPARE_ONLY'


def power_shell_argv(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded]


def remote_node(host: str = PREPRESS_HOST, *, tcp_timeout: float = TCP_TIMEOUT,
                ssh_timeout: float = SSH_TIMEOUT) -> tuple[str, str]:
    if not regular(Path(KEY)) or not regular(Path(KNOWN)):
        return 'UNKNOWN_SSH_CONFIGURATION', 'UNKNOWN_SSH_CONFIGURATION'
    try:
        with socket.create_connection((host, PREPRESS_PORT), timeout=tcp_timeout):
            pass
    except (ConnectionError, OSError, TimeoutError):
        return 'OFFLINE_TCP22_UNREACHABLE', 'OFFLINE_TCP22_UNREACHABLE'
    options = ['-T', '-i', KEY, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=3',
               '-o', 'ConnectionAttempts=1', '-o', f'UserKnownHostsFile={KNOWN}',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=2',
               '-o', 'ServerAliveCountMax=1']
    try:
        p = subprocess.run(['ssh', *options, f'{PREPRESS_USER}@{host}',
                            *power_shell_argv(PS_PROBE)],
                           capture_output=True, text=True, timeout=ssh_timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 'UNKNOWN_SSH_TIMEOUT', 'UNKNOWN_SSH_TIMEOUT'
    if p.returncode != 0:
        return 'UNKNOWN_SSH_AUTH_OR_COMMAND', 'UNKNOWN_SSH_AUTH_OR_COMMAND'
    matches = re.findall(r'(?m)^U1_NODE=([A-Z][A-Z0-9_]*)\s*$', p.stdout)
    if len(matches) != 1:
        return 'UNKNOWN_REMOTE_RESPONSE', 'UNKNOWN_REMOTE_RESPONSE'
    status = safe_status(matches[0])
    if status not in {
        'READY', 'BLOCKED_IDENTITY', 'BLOCKED_SCHEDULER', 'BLOCKED_ADMIN_TOKEN',
        'BLOCKED_SESSION_QUERY', 'BLOCKED_NO_ACTIVE_SESSION', 'BLOCKED_NO_EXPLORER',
        'BLOCKED_JOBS_ROOT', 'BLOCKED_ILLUSTRATOR_INSTALL',
        'BUSY_ILLUSTRATOR_OPEN',
    }:
        return 'UNKNOWN_REMOTE_RESPONSE', 'UNKNOWN_REMOTE_RESPONSE'
    return 'ONLINE_SSH_AUTHENTICATED', status


def snapshot(*, check_remote: bool = True, root: Path = GDL_ROOT,
             share: Path = SHARE) -> dict[str, Any]:
    start = time.monotonic()
    node_s01, local_route = local_node(root, share)
    if check_remote:
        node_prepress, illustrator = remote_node()
    else:
        node_prepress, illustrator = 'NOT_CHECKED', 'NOT_CHECKED'
    result = {
        'schema_version': 'gdl_gc47u_route_readiness_v0_1',
        'nodes': {'s01': node_s01, 'prepress': node_prepress},
        'routes': {'local-gc29': local_route,
                   'illustrator': illustrator if node_s01 == 'READY_LOCAL_S01' else 'BLOCKED_LOCAL_S01',
                   'acrobat': 'NOT_CONFIGURED_CAPABILITY_ENDPOINT'},
        'capabilities': {
            'local-gc29': 'PREPARE_ONLY_NO_RENDER',
            'illustrator': 'GC47T_FOUR_ARTBOARD_NATIVE_NON_RELEASE',
            'acrobat': 'NO_ATTESTED_EXECUTOR_OR_ENDPOINT',
        },
        'ttl_seconds': 0,
        'elapsed_ms': round((time.monotonic()-start)*1000),
        'non_release': True,
        'write_performed': False,
    }
    return result


def route_ready(status: str, route: str) -> bool:
    if route == 'local-gc29':
        return status == 'READY_GC29_PREPARE_ONLY'
    if route == 'illustrator':
        return status == 'READY'
    return False


def display(result: dict[str, Any]) -> None:
    print('GC47U_S01='+result['nodes']['s01'])
    print('GC47U_PREPRESS='+result['nodes']['prepress'])
    for name, tag in [('LOCAL_GC29', 'local-gc29'), ('ILLUSTRATOR', 'illustrator'),
                      ('ACROBAT', 'acrobat')]:
        print('GC47U_ROUTE_'+name+'='+result['routes'][tag])
    print('GC47U_ROUTE_LOCAL_GC29_CAPABILITY=PREPARE_ONLY_NO_RENDER')
    print('GC47U_ELAPSED_MS='+str(result['elapsed_ms']))
    print('GC47U_CHECKPOINT=READ_ONLY_NO_DISPATCH_NON_RELEASE')


def get_jobs(client: str, result: dict[str, Any], root: Path = GDL_ROOT) -> None:
    # Never interpret untrusted CLI client path ourselves: reuse GC47S/GC29 validators.
    if result['nodes']['s01'] != 'READY_LOCAL_S01':
        print('GC47U_CLIENT_OPTIONS=BLOCKED_LOCAL_S01')
        return
    modfile = root / 'scripts/graphic_design_lab/greeting_cards/gc47t_client_windows_bridge_r001.py'
    spec = importlib.util.spec_from_file_location('gc47u_existing_bridge', modfile)
    if spec is None or spec.loader is None:
        print('GC47U_CLIENT_OPTIONS=BLOCKED_SOURCE_IMPORT')
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    s, gc29 = mod.source_check()
    ws = s.workspace(client)
    jobs, _, _ = gc29.accepted_jobs(ws)
    print('GC47U_CLIENT_ACCEPTED_JOBS='+str(len(jobs)))
    for job in jobs:
        variants, supported = s.classify(job)
        # IDs only; do not display client texts, photographs, personal info, paths.
        jobid = job['job_id']
        if not (isinstance(jobid, str) and s.ID_RE.fullmatch(jobid)):
            raise Blocked('INVALID_JOB_ID')
        routes = 'local-gc29' if supported and route_ready(result['routes']['local-gc29'], 'local-gc29') else 'NONE'
        if supported and route_ready(result['routes']['illustrator'], 'illustrator'):
            routes += ',illustrator' if routes != 'NONE' else 'illustrator'
        print('GC47U_JOB='+jobid+' PROFILE='+variants['front']+'/'+variants['image']+'/'+variants['signature']+' READY_ROUTES='+routes)
    print('GC47U_OPTIONS=READ_ONLY_CLIENT_MATRIX')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('routes','options','gate'), required=True)
    parser.add_argument('--route', choices=ROUTE_KEYS)
    parser.add_argument('--client-name')
    parser.add_argument('--format', choices=('kv', 'json'), default='kv')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'gate' and not args.route:
            raise Blocked('ROUTE_REQUIRED')
        if args.mode == 'options' and not args.client_name:
            raise Blocked('CLIENT_NAME_REQUIRED')
        result = snapshot()
        if args.format == 'json':
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            display(result)
        if args.mode == 'options':
            get_jobs(args.client_name, result)
        if args.mode == 'gate':
            status = result['routes'][args.route]
            if not route_ready(status, args.route):
                print('GC47U_GATE=BLOCKED_ROUTE_'+args.route.upper().replace('-', '_')+'_'+status)
                print('GC47U_DISPATCH=FALSE')
                return 2
            print('GC47U_GATE=PASS_ROUTE_'+args.route.upper().replace('-', '_')+'_TRANSIENT_READINESS')
            print('GC47U_DISPATCH=CALLER_MUST_RECHECK_BEFORE_ATTEMPT')
        return 0
    except (Blocked, ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        code = str(exc) if isinstance(exc, Blocked) else type(exc).__name__.upper()
        print('GC47U=BLOCKED_'+safe_status(code), file=sys.stderr)
        print('GC47U_DISPATCH=FALSE PRODUCTION_READY=FALSE', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
