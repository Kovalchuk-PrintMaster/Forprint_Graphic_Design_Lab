#!/usr/bin/env python3
"""GC47AK: add-only deployment of a Windows CMD/PowerShell client entry.

No changes to existing launchers; no Windows execution and no renderer dispatch.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
SHARE = Path('/srv/smb/In_Progress/data')
BRIDGE = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_bridge_r001.py'
CMD = 'ForPrint_Launcher.cmd'
PS1 = 'ForPrint_Launcher.ps1'
HELP = 'ForPrint_Launcher_ПОЧАТИ_ТУТ.txt'

class Blocked(Exception):
    pass

def need(v, why):
    if not v: raise Blocked(why)

def is_dir(p):
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except OSError: return False

def is_file(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except OSError: return False

def sha(data): return hashlib.sha256(data).hexdigest()

def workspace(client, share=SHARE):
    need(client and client not in ('.', '..') and len(client) <= 150, 'CLIENT_INVALID')
    need(not any(ord(c) < 32 or c in '/\\' for c in client), 'CLIENT_NAME_UNSAFE')
    need(is_dir(share), 'SMB_SHARE_UNSAFE_OR_MISSING')
    ws = share/client/'_forprint_automation'
    for d in (share/client, ws, ws/'input', ws/'output', ws/'template_studio'):
        need(is_dir(d), 'CLIENT_WORKSPACE_UNSAFE_OR_MISSING')
    need(ws.resolve(strict=True).parent.parent == share.resolve(strict=True), 'WORKSPACE_OUTSIDE_SHARE')
    return ws

def cmd_bytes():
    content = '''@echo off
setlocal
chcp 65001 >nul
set "FORPRINT_PS=%~dp0ForPrint_Launcher.ps1"
if not exist "%FORPRINT_PS%" (
  echo GC47AK BLOCKED: PowerShell launcher was not found beside this CMD file.
  pause
  exit /b 2
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%FORPRINT_PS%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo GC47AK: Check the diagnostic above. Do not launch the same job again before inspecting its attempt.
if "%RC%"=="0" echo GC47AK: The operator menu has closed. Production approval was NOT granted.
echo.
pause
exit /b %RC%
'''
    return content.replace('\n', '\r\n').encode('utf-8')

def ps1_bytes():
    # This wrapper deliberately never executes code from ZIP files in input/.
    return r'''[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9_-]+$')][string]$SshAlias = 's01')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding

try {
    # Must be launched from the original UNC SMB path, not from a copied or mapped folder.
    $inputDir = (Get-Item -LiteralPath $PSScriptRoot -ErrorAction Stop).FullName.TrimEnd([char]92)
    $pattern = '^\\\\[^\\]+\\In_Progress\\data\\([^\\]+)\\_forprint_automation\\input$'
    $match = [regex]::Match($inputDir, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { throw 'GC47AK_ORIGINAL_CLIENT_UNC_REQUIRED' }
    $client = $match.Groups[1].Value
    if ($client -eq '.' -or $client -eq '..' -or $client.Length -gt 150 -or $client -match '[\x00-\x1F]') {
        throw 'GC47AK_CLIENT_IDENTITY_UNSAFE'
    }
    $client = $client.Normalize([Text.NormalizationForm]::FormC)
    $workspace = Split-Path -Parent $inputDir
    $clientRoot = Split-Path -Parent $workspace
    foreach ($path in @($inputDir,$workspace,$clientRoot)) {
        $entry = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if (-not $entry.PSIsContainer -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'GC47AK_UNSAFE_CLIENT_FOLDER_OR_LINK'
        }
    }
    $raw = [Text.Encoding]::UTF8.GetBytes($client)
    if ($raw.Length -gt 600) {throw 'GC47AK_CLIENT_ID_TOO_LONG'}
    $token = [Convert]::ToBase64String($raw).TrimEnd('=').Replace('+','-').Replace('/','_')
    if ($token -cnotmatch '^[A-Za-z0-9_-]+$') {throw 'GC47AK_CLIENT_TOKEN_INVALID'}
    $ssh = Get-Command ssh.exe -CommandType Application -ErrorAction Stop
    $remote = 'cd /srv/software_development/forprint-project/forprint_graphic_design_lab && exec .venv_gdl/bin/python -u -B scripts/graphic_design_lab/greeting_cards/gc47ak_windows_bridge_r001.py --mode interactive --client-b64 ' + $token
    Write-Host '============================================================'
    Write-Host ' FORPRINT | КЛІЄНТСЬКИЙ ЗАПУСК ЛИСТІВОК'
    Write-Host '============================================================'
    Write-Host ('Клієнт: ' + $client)
    Write-Host 'Вхідні ZIP → прийнятий пакет → замовлення → маршрут → перегляд.'
    Write-Host 'Це режим перегляду. Новий Illustrator-запуск потребує окремого підтвердження.'
    Write-Host 'Підключення до s01 через SSH. Ключі та паролі у клієнтській папці не зберігаються.'
    Write-Host 'Для виходу без запуску оберіть 0 у головному меню.'
    Write-Host ''
    # IMPORTANT: No output capture/pipeline: SSH must inherit the live console stdin.
    # -tt forces PTY for remote input(); a single SSH call is made, with NO retries.
    # StrictHostKeyChecking requires an already verified trusted host key.
    & $ssh.Source -tt -o 'StrictHostKeyChecking=yes' -o 'ConnectTimeout=12' -o 'ServerAliveInterval=30' -o 'ServerAliveCountMax=4' $SshAlias $remote
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {throw ('GC47AK_SSH_OR_REMOTE_EXIT_' + $rc)}
    Write-Host 'GC47AK_WINDOWS_ENTRY=COMPLETE_REVIEW_ONLY'
    exit 0
} catch {
    Write-Host ('GC47AK_WINDOWS_ENTRY=BLOCKED ' + $_.Exception.Message)
    Write-Host 'Без автоматичного повторного запуску. Якщо обірвався SSH після підтвердження, спочатку перевірте попередні спроби.'
    exit 2
}
'''.replace('\n','\r\n').encode('utf-8-sig')

def help_bytes():
    return '''FORPRINT | WINDOWS LAUNCHER GC47AK | ПОЧАТИ ТУТ

Де: \\<сервер>\\In_Progress\\data\\<клієнт>\\_forprint_automation\\input

Подвійний клік: ForPrint_Launcher.cmd

1. ПЕРЕГЛЯНУТИ ВХІДНІ ZIP — інформація про файли, відокремлено прийнятий пакет.
2. СТВОРИТИ ЛИСТІВКУ — вибір замовлення із прийнятого пакета, потім маршруту.
   Adobe Illustrator / PREPRESS — діюча гілка. Server/Local — ЗАБЛОКОВАНА.
   Запуск лише після буквального підтвердження LAUNCH <ідентифікатор>.
3. ПЕРЕВІРИТИ ГОТОВНІСТЬ — read-only перевірка PREPRESS та Illustrator.
4. ПОПЕРЕДНІ СПРОБИ — пошук результату, статус, отримання лише з підтвердженням.
5. ДОВІДКА — пояснення ZIP / замовлення / маршруту та обмежень.
0. ВИХІД — без нового запуску.

Потрібно: Windows з powershell.exe і ssh.exe; налаштований SSH alias s01;
відомий і перевірений серверний SSH host key; чинний доступ до s01.
При потребі SSH запитає пароль у консолі. Паролі/ключі у файлах не зберігати.

Якщо SSH перервався ПІСЛЯ підтвердження LAUNCH, НІКОЛИ не повторюйте
запуск без перевірки попередньої спроби. Віддалений процес міг завершитися.

Інструмент використовує GC47AJ/GC47AI/GC47T на s01, а не старі GC28/GC29.
Старий «Створити_листівку.cmd» не перезаписано і він НЕ є новим Launcher.
Усі результати лише для перегляду. PRODUCTION_READY=false.
'''.encode('utf-8-sig')

def entries(ws):
    return [(ws/'input'/CMD,cmd_bytes()),(ws/'input'/PS1,ps1_bytes()),(ws/'input'/HELP,help_bytes())]

def inspect(client, share=SHARE):
    ws = workspace(client,share)
    need(is_file(BRIDGE), 'GC47AK_BRIDGE_NOT_INSTALLED')
    all_entries = entries(ws)
    old, missing = [], []
    for path,content in all_entries:
        if is_file(path) and sha(path.read_bytes()) == sha(content): old.append(path)
        elif path.exists() or path.is_symlink(): raise Blocked('EXISTING_FILE_DIFFERS_NO_OVERWRITE_'+path.name)
        else: missing.append(path)
    need(len(old) in (0,len(all_entries)), 'PARTIAL_CLIENT_INSTALL_NO_OVERWRITE')
    return ws, old, missing

def install(client, share=SHARE):
    ws, old, missing = inspect(client,share)
    if old: return 'ALREADY_INSTALLED'
    created = []
    try:
        for path,data in entries(ws):
            with path.open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            created.append(path)
            need(sha(path.read_bytes()) == sha(data), 'WRITTEN_HASH_MISMATCH')
        return 'INSTALLED_SIDE_BY_SIDE'
    except BaseException:
        for path in reversed(created): path.unlink(missing_ok=True)
        raise

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('check','install'), required=True)
    p.add_argument('--client-name',required=True)
    p.add_argument('--confirm-install',action='store_true')
    args=p.parse_args(argv)
    try:
        ws,old,missing=inspect(args.client_name)
        print('GC47AK_CLIENT_WORKSPACE='+str(ws))
        print('GC47AK_EXISTING_LEGACY_PRESERVED=TRUE')
        if args.mode=='check': state='ALREADY_INSTALLED' if old else 'READY_ADD_ONLY'
        else:
            need(args.confirm_install, 'CONFIRM_INSTALL_REQUIRED')
            state=install(args.client_name)
        print('GC47AK_CLIENT_ENTRY='+state)
        print('GC47AK_NO_NATIVE_DISPATCH=TRUE NO_OLD_LAUNCHER_OVERWRITE=TRUE NO_HUB_CHANGE=TRUE')
        return 0
    except (Blocked, OSError, ValueError) as e:
        print('GC47AK_CLIENT_ENTRY=BLOCKED_'+(str(e) if isinstance(e,Blocked) else type(e).__name__),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
