#!/usr/bin/env python3
"""One-use GC21 operator: s01 -> PREPRESS via existing authenticated SSH.

Modes: stage, check, launch, status. No implicit retries or cleanup.
The bundle contains only controller/runner code, never private client assets.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

HOST = 'work@192.168.50.69'
KEY = '/root/.ssh/forprint_prepress_ed25519'
KNOWN = '/root/.ssh/known_hosts_forprint_prepress'
JOB = r'D:\ForPrint_Automation\GraficsDesignLab\Automation\jobs\gdl-gc21-card-001\a0001'
CONTROL = 'gc21_windows_controller_v0_1.ps1'
RUNNER = 'gc21_windows_runner_v0_1.ps1'
REMOTE_ZIP = 'gc21_remote_executor_v0_1.zip'
EXPECTED_ZIP_NAME = 'ForPrint_GDL_GC21_Remote_SingleUse_Operator_v0_1_20261025.zip'


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def ssh_options() -> list[str]:
    return ['-i', KEY, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', f'UserKnownHostsFile={KNOWN}', '-o', 'StrictHostKeyChecking=yes']


def ps_command(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded]


def remote(script: str, *, timeout=90) -> None:
    command = ['ssh', '-T', *ssh_options(), HOST, *ps_command(script)]
    result = subprocess.run(command, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f'PREPRESS_SSH_OR_POWERSHELL_RC_{result.returncode}')


def verify_local_bundle(path: Path) -> tuple[str, dict]:
    if not path.is_file() or path.is_symlink() or path.name != EXPECTED_ZIP_NAME:
        raise ValueError('OPERATOR_BUNDLE_MISSING_OR_INVALID')
    with ZipFile(path) as z:
        names = set(z.namelist())
        if names != {CONTROL, RUNNER, 'bundle_manifest.json', '00_README_UA.md'}:
            raise ValueError('OPERATOR_BUNDLE_UNEXPECTED_ENTRIES')
        if any(z.getinfo(name).file_size > 40000 for name in names):
            raise ValueError('OPERATOR_BUNDLE_FILE_TOO_LARGE')
        mf = json.loads(z.read('bundle_manifest.json'))
        if mf['schema'] != 'gdl_gc21_remote_single_use_bundle_v0_1':
            raise ValueError('BUNDLE_SCHEMA_MISMATCH')
        for fn in (RUNNER, CONTROL):
            if sha(z.read(fn)) != mf['files_sha256'][fn]:
                raise ValueError('BUNDLE_FILE_HASH_MISMATCH')
    return sha(path.read_bytes()), mf


def stage(bundle: Path) -> None:
    digest, mf = verify_local_bundle(bundle)
    # Fail before scp if a prior upload exists, or runner already staged.
    remote(f"""
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$z=Join-Path $HOME '{REMOTE_ZIP}'
$i='{JOB}\\input'
if(Test-Path -LiteralPath $z){{throw 'GC21_REMOTE_UPLOAD_ALREADY_EXISTS'}}
if(-not(Test-Path -LiteralPath $i -PathType Container)){{throw 'GC21_ATTEMPT_INPUT_MISSING'}}
foreach($n in @('{CONTROL}','{RUNNER}')){{
 if(Test-Path -LiteralPath (Join-Path $i $n)){{throw 'GC21_ALREADY_STAGED'}}
}}
Write-Output 'GDL_GC21_REMOTE_STAGE_PREFLIGHT=PASS'
""")
    subprocess.run(['scp', *ssh_options(), str(bundle), f'{HOST}:{REMOTE_ZIP}'],
                   check=True, timeout=120)
    remote(f"""
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$z=Join-Path $HOME '{REMOTE_ZIP}'
$i='{JOB}\\input'
if(-not(Test-Path -LiteralPath $z -PathType Leaf)){{throw 'GC21_ZIP_NOT_FOUND'}}
if((Get-FileHash -LiteralPath $z -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{digest}'){{throw 'GC21_TRANSFER_SHA_MISMATCH'}}
foreach($n in @('{CONTROL}','{RUNNER}')){{
 if(Test-Path -LiteralPath (Join-Path $i $n)){{throw 'GC21_EXISTING_RUNNER_NO_OVERWRITE'}}
}}
Expand-Archive -LiteralPath $z -DestinationPath $i -ErrorAction Stop
if((Get-FileHash -LiteralPath (Join-Path $i '{CONTROL}') -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{mf['files_sha256'][CONTROL]}'){{throw 'GC21_CONTROLLER_STAGE_SHA_MISMATCH'}}
if((Get-FileHash -LiteralPath (Join-Path $i '{RUNNER}') -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{mf['files_sha256'][RUNNER]}'){{throw 'GC21_RUNNER_STAGE_SHA_MISMATCH'}}
Move-Item -LiteralPath $z -Destination (Join-Path $i '{REMOTE_ZIP}') -ErrorAction Stop
Write-Output 'GDL_GC21_REMOTE_STAGE=PASS'
""", timeout=120)


def run_mode(mode: str, manifest: dict) -> None:
    controller = f'{JOB}\\input\\{CONTROL}'
    remote(f"""
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$path='{controller}'
if(-not(Test-Path -LiteralPath $path -PathType Leaf)){{throw 'GC21_CONTROLLER_MISSING_RUN_STAGE_FIRST'}}
if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{manifest['files_sha256'][CONTROL]}'){{throw 'GC21_CONTROLLER_TAMPERED'}}
& $path -Mode '{mode}'
if($LASTEXITCODE -ne 0){{exit 2}}
""", timeout=35 if mode != 'launch' else 60)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=('stage', 'check', 'launch', 'status'), required=True)
    ap.add_argument('--bundle', type=Path, default=Path('tmp') / EXPECTED_ZIP_NAME)
    args = ap.parse_args(argv)
    try:
        _, manifest = verify_local_bundle(args.bundle)
        if args.mode == 'stage':
            stage(args.bundle)
        else:
            run_mode(args.mode, manifest)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        print(f'GDL_GC21_REMOTE_OPERATOR=BLOCKED code={type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
