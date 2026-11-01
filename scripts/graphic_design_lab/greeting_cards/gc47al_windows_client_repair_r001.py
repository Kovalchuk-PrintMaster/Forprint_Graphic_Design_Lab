#!/usr/bin/env python3
"""GC47AL: exact-source, guarded Windows operator entry repair.

No render, no SSH, no prepress mutations. Existing GC47AK CMD stays byte-identical.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OLD_MODULE = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_client_deploy_r001.py'
OLD_MODULE_SHA = '8299e0598ede804265848677473bb97eb564303349c857200244987801652c66'
SHARE = Path('/srv/smb/In_Progress/data')
CLIENT_CMD = 'ForPrint_Launcher.cmd'
CLIENT_PS1 = 'ForPrint_Launcher.ps1'
CLIENT_HELP = 'ForPrint_Launcher_ПОЧАТИ_ТУТ.txt'
OLD_HASHES = {
    CLIENT_CMD: 'bdee768859b6dedfd7f699c76c24800add9a58056328aab27447033ae773a110',
    CLIENT_PS1: 'ef5853c2290aeceff6af93154c335c82a7ceb4cbee768918946c6c6ac2cb25ec',
    CLIENT_HELP: '71fd4c8c852558daada53549f00471736b6495a3e0de25617871f85b8608fa3a',
}

class Blocked(Exception):
    pass

def need(value, reason):
    if not value: raise Blocked(reason)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def is_dir(path: Path) -> bool:
    try: return stat.S_ISDIR(path.lstat().st_mode)
    except OSError: return False

def is_file(path: Path) -> bool:
    try: return stat.S_ISREG(path.lstat().st_mode)
    except OSError: return False

def read_ak(module_path: Path = OLD_MODULE):
    need(is_file(module_path), 'GC47AK_ORIGINAL_MODULE_MISSING')
    need(sha(module_path.read_bytes()) == OLD_MODULE_SHA, 'GC47AK_ORIGINAL_MODULE_HASH_CHANGED')
    spec = importlib.util.spec_from_file_location('gc47ak_original_pinned', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def generate_ps1(client: str, ak) -> bytes:
    old_bytes = ak.ps1_bytes()
    need(sha(old_bytes) == OLD_HASHES[CLIENT_PS1], 'OLD_PS1_GENERATOR_MISMATCH')
    source = old_bytes.decode('utf-8-sig')
    token = base64.b64encode(client.encode('utf-8')).decode('ascii')
    old_encoding = '[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)\r\n$OutputEncoding = [Console]::OutputEncoding'
    new_encoding = '''# Keep PowerShell, SSH and console on UTF-8. The console font is a Windows setting.
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
} catch {
    Write-Host 'GC47AL_CONSOLE_ENCODING=FALLBACK_CHECK_WINDOWS_TERMINAL'
}'''.replace('\n', '\r\n')
    need(source.count(old_encoding) == 1, 'OLD_ENCODING_ANCHOR_CHANGED')
    source = source.replace(old_encoding, new_encoding, 1)

    start = '    # Must be launched from the original UNC SMB path, not from a copied or mapped folder.\r\n'
    end = '    $workspace = Split-Path -Parent $inputDir\r\n'
    need(source.count(start) == 1 and source.count(end) == 1, 'OLD_PATH_ANCHORS_CHANGED')
    before, remainder = source.split(start, 1)
    _, after = remainder.split(end, 1)
    # Server continues verifying the exact client workspace and SSH operator authority.
    replacement = r'''    # GC47AL: support a verified UNC or Windows-mapped network drive.
    # The bound client name is pinned by the s01 installer, never taken from ZIP data.
    $inputDir = (Get-Item -LiteralPath $PSScriptRoot -ErrorAction Stop).FullName.TrimEnd([char]92)
    $pathMatch = [regex]::Match($inputDir, '^(?<parent>.+)\\(?<client>[^\\]+)\\_forprint_automation\\input$', 'IgnoreCase')
    if (-not $pathMatch.Success) { throw 'GC47AL_CLIENT_FOLDER_LAYOUT_REQUIRED' }
    $client = $pathMatch.Groups['client'].Value
    $expected = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__CLIENT_TOKEN_B64__'))
    if ($client -cne $expected) { throw 'GC47AL_CLIENT_FOLDER_NOT_BOUND_TO_INSTALL' }
    if ($client -eq '.' -or $client -eq '..' -or $client.Length -gt 150 -or $client -match '[\x00-\x1F]') {
        throw 'GC47AL_CLIENT_IDENTITY_UNSAFE'
    }
    if ($client -cne $client.Normalize([Text.NormalizationForm]::FormC)) { throw 'GC47AL_CLIENT_NOT_NFC' }
    if ($inputDir -match '^\\\\[^\\]+\\[^\\]+\\') {
        Write-Host 'GC47AL_NETWORK_PATH=VERIFIED_UNC_SHAPE'
    } elseif ($inputDir -match '^(?<letter>[A-Za-z]):\\') {
        $driveLetter = $Matches['letter']
        $device = $driveLetter + ':'
        $provider = $null
        try {
            $disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter ("DeviceID='" + $device + "'") -ErrorAction Stop
            if ($disk -and $disk.DriveType -eq 4) { $provider = $disk.ProviderName }
        } catch { }
        if (-not $provider) {
            try {
                $disk = Get-WmiObject Win32_LogicalDisk -Filter ("DeviceID='" + $device + "'") -ErrorAction Stop
                if ($disk -and $disk.DriveType -eq 4) { $provider = $disk.ProviderName }
            } catch { }
        }
        if (-not $provider) {
            try {
                $psDrive = Get-PSDrive -Name $driveLetter -PSProvider FileSystem -ErrorAction Stop
                if ($psDrive -and $psDrive.DisplayRoot) { $provider = $psDrive.DisplayRoot }
            } catch { }
        }
        if (-not $provider -or $provider -notmatch '^\\\\[^\\]+\\[^\\]+') {
            throw 'GC47AL_MAPPED_NETWORK_DRIVE_NOT_VERIFIED_USE_UNC_OR_NON_ELEVATED_EXPLORER'
        }
        Write-Host 'GC47AL_NETWORK_PATH=VERIFIED_MAPPED_NETWORK'
    } else {
        throw 'GC47AL_LOCAL_COPY_NOT_ALLOWED_USE_NETWORK_CLIENT_FOLDER'
    }
    $client = $client.Normalize([Text.NormalizationForm]::FormC)
'''.replace('__CLIENT_TOKEN_B64__', token).replace('\n', '\r\n')
    source = before + replacement + end + after
    need(source.count('& $ssh.Source') == 1, 'SSH_CALL_COUNT_CHANGED')
    need(source.count('gc47ak_windows_bridge_r001.py') == 1, 'BRIDGE_CHANGED')
    need('GC47AK_ORIGINAL_CLIENT_UNC_REQUIRED' not in source, 'OLD_BLOCK_STILL_PRESENT')
    return ('\ufeff' + source).encode('utf-8')

def generate_help(ak) -> bytes:
    need(sha(ak.help_bytes()) == OLD_HASHES[CLIENT_HELP], 'OLD_HELP_GENERATOR_MISMATCH')
    doc = '''FORPRINT | WINDOWS CLIENT LAUNCHER GC47AL | ІНСТРУКЦІЯ

ВІДКРИТТЯ: двічі клацнути ForPrint_Launcher.cmd в папці клієнта
...\\<клієнт>\\_forprint_automation\\input\\ (через мережеву папку SMB).
Дозволені: прямий шлях UNC або перевірений підключений мережевий диск.
Локальна копія файлів не є клієнтською папкою та блокується.

МЕНЮ: 1 — вхідні ZIP; 2 — створити листівку; 3 — готовність;
4 — попередні спроби/результати; 5 — довідка; 0 — вихід.
ZIP — це вхідний пакет, замовлення — конкретна листівка, маршрут — спосіб
виконання. Тільки прийнятий GC25/GC29 пакет може запускати листівку.
Illustrator працює через s01/PREPRESS. Server/local зараз заблокований.

ЯКЩО УКРАЇНСЬКИЙ ТЕКСТ ПОКАЗУЄ ?????:
  1. Відкрити у Windows Terminal (рекомендовано) або у властивостях CMD
     встановити шрифт Consolas / Cascadia Mono.
  2. Перед стартом у CMD виконати chcp 65001 (запускач це вже робить).
  3. У Windows Terminal виставити Font face: Cascadia Mono / Consolas.
  4. Файл PS1 збережений в UTF-8 BOM; не зберігати повторно як ANSI.

ЯКЩО GC47AL_MAPPED_NETWORK_DRIVE_NOT_VERIFIED:
  - відкрити через справжній UNC-шлях у Провіднику Windows;
  - не запускати з підвищеного (Administrator) CMD: права/підключення диска
    можуть відрізнятися від звичайного облікового запису.

Потрібен перевірений SSH alias s01 та SSH host key. Секретів у файлах немає.
ПІСЛЯ LAUNCH не повторювати запуск автоматично, навіть після обриву SSH:
спочатку переглянути статус попередньої спроби.

Пакет GC47AL — ремонт Windows входу, НЕ новий рендерер.
GC47AK bridge, GC47AJ/GC47AI/GC47T та паспорт GC47K не змінюються.
PRODUCTION_READY=false. Всі результати — лише для перегляду.
'''
    return doc.encode('utf-8-sig')

def expected_paths(client: str, share: Path = SHARE, root: Path = ROOT, ak=None):
    ak = ak or read_ak(root / OLD_MODULE.relative_to(ROOT))
    ws = ak.workspace(client, share)
    return ak, ws, {
        CLIENT_CMD: ak.cmd_bytes(),
        CLIENT_PS1: generate_ps1(client, ak),
        CLIENT_HELP: generate_help(ak),
    }

def inspect(client: str, share: Path = SHARE, root: Path = ROOT, ak=None):
    ak, ws, revised = expected_paths(client, share, root, ak)
    statuses = {}
    for name in (CLIENT_CMD, CLIENT_PS1, CLIENT_HELP):
        p = ws/'input'/name
        need(is_file(p), 'CLIENT_ENTRY_NOT_REGULAR_'+name)
        current = sha(p.read_bytes())
        if name != CLIENT_CMD and current == sha(revised[name]):
            statuses[name] = 'NEW'
        elif current == OLD_HASHES[name]:
            statuses[name] = 'OLD'
        else:
            raise Blocked('CLIENT_ENTRY_CHANGED_NO_OVERWRITE_'+name)
    need(statuses[CLIENT_CMD] == 'OLD', 'WINDOWS_CMD_MUST_REMAIN_GC47AK')
    need(statuses[CLIENT_PS1] == statuses[CLIENT_HELP], 'PARTIAL_CLIENT_REPAIR_REVIEW_REQUIRED')
    return ws, statuses, revised

def atomic_replace(path: Path, data: bytes):
    # Temporary file is created in the same SMB directory for atomic rename.
    fd, temp = tempfile.mkstemp(prefix='.gc47al_', suffix='.tmp', dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(path.lstat().st_mode))
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        need(sha(path.read_bytes()) == sha(data), 'POST_REPLACE_HASH_MISMATCH_'+path.name)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def repair(client: str, share: Path = SHARE, root: Path = ROOT, ak=None):
    ws, states, revised = inspect(client, share, root, ak)
    if states[CLIENT_PS1] == 'NEW':
        return 'ALREADY_REPAIRED'
    backup = root/'tmp'/'gc47al_windows_client_backups_r001'/sha(client.encode('utf-8'))[:20]
    need(not backup.exists() and not backup.is_symlink(), 'BACKUP_ALREADY_EXISTS_REVIEW_REQUIRED')
    backup.mkdir(parents=True, mode=0o700)
    originals = {name: (ws/'input'/name).read_bytes() for name in (CLIENT_PS1, CLIENT_HELP)}
    try:
        for name, data in originals.items():
            p = backup/name
            with p.open('xb') as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(data); f.flush(); os.fsync(f.fileno())
            need(sha(p.read_bytes()) == sha(data), 'BACKUP_HASH_FAILED_'+name)
        for name in (CLIENT_PS1, CLIENT_HELP):
            atomic_replace(ws/'input'/name, revised[name])
        _, final, _ = inspect(client, share, root, ak)
        need(final[CLIENT_PS1] == 'NEW', 'POST_INSTALL_INSPECTION_FAILED')
        return 'REPAIRED_GUARDED_WITH_BACKUP'
    except BaseException:
        # Restore both originals if something failed in the middle.
        for name, data in originals.items():
            atomic_replace(ws/'input'/name, data)
        raise

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('check','install'),required=True)
    p.add_argument('--client-name',required=True)
    p.add_argument('--confirm-install', action='store_true')
    args=p.parse_args(argv)
    try:
        ws, states, revised=inspect(args.client_name)
        print('GC47AL_CLIENT_WORKSPACE='+str(ws))
        print('GC47AL_ORIGINAL_WINDOWS_CMD_PRESERVED=TRUE')
        print('GC47AL_PREFLIGHT='+ ('ALREADY_REPAIRED' if states[CLIENT_PS1]=='NEW' else 'READY_GUARDED_REPAIR'))
        if args.mode=='install':
            need(args.confirm_install, 'EXPLICIT_INSTALL_CONFIRMATION_REQUIRED')
            print('GC47AL_CLIENT_REPAIR='+repair(args.client_name))
        print('GC47AL_NO_SSH_EXEC=TRUE NO_NATIVE_DISPATCH=TRUE NO_GIT_COMMIT=TRUE')
        return 0
    except (Blocked, OSError, UnicodeError, ValueError) as e:
        print('GC47AL=BLOCKED_'+(str(e) if isinstance(e,Blocked) else type(e).__name__.upper()),file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
