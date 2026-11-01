#!/usr/bin/env python3
"""GC47AJ: safe additive deployment of a small CLI entry into client input/.

Never deletes or modifies earlier GC26/GC28/GC29 customer launchers.
Python core remains inside the GDL repo. Installing an entry is not a native dispatch.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py'
PYTHON = ROOT / '.venv_gdl/bin/python'
SHARE = Path('/srv/smb/In_Progress/data')
ENTRY = 'ForPrint_Launcher_GC47AJ.sh'
HELP = 'ForPrint_Launcher_GC47AJ_ПОЧАТИ_ТУТ.txt'

class Blocked(Exception): pass

def need(v, reason):
    if not v: raise Blocked(reason)

def is_dir(p):
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except OSError: return False

def is_file(p):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except OSError: return False

def sha_bytes(b): return hashlib.sha256(b).hexdigest()

def workspace(client, share=SHARE):
    need(client and client not in ('.', '..') and not any(c in client for c in ('/', '\\', '\0', '\n', '\r')), 'INVALID_CLIENT_NAME')
    need(is_dir(share), 'SHARE_NOT_FOUND_OR_SYMLINK')
    client_dir=share/client
    ws=client_dir/'_forprint_automation'
    for folder in (client_dir,ws,ws/'input',ws/'output',ws/'template_studio'):
        need(is_dir(folder), 'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(ws.resolve(strict=True).parent.parent == share.resolve(strict=True), 'WORKSPACE_BOUNDARY')
    return ws

def wrapper_bytes(root=ROOT):
    interp=shlex.quote(str(root/'.venv_gdl/bin/python'))
    source=shlex.quote(str(root/'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py'))
    return (f'''#!/bin/sh
# GC47AJ client-folder entrypoint: only delegates to verified GDL code.
# Run on s01 with: sh ./ForPrint_Launcher_GC47AJ.sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec {interp} -B {source} --input-dir "$HERE" --mode interactive
''').encode('utf-8')

def guide_bytes():
    return '''FORPRINT — ЗАПУСК ЛИСТІВОК ІЗ ПАПКИ КЛІЄНТА (GC47AJ)

Місце: _forprint_automation/input/

На сервері s01 зайти в цю папку і запустити:
    sh ./ForPrint_Launcher_GC47AJ.sh

1. Переглянути ZIP — показує файли input і ПОЗНАЧАЄ авторитетно прийнятий ZIP.
2. Створити листівку — обрати замовлення у ПРИЙНЯТОМУ ZIP, потім маршрут.
3. Маршрути — перевірка без створення спроби.
4. Попередні спроби — перегляд статусу і, за підтвердженням, отримання готового результату.
5. Довідка — пояснення усіх етапів.

УВАГА: серверний рендерер відкладений. Illustrator — тільки review, не виробничий випуск.
Клієнтські файли та старі запускачі не замінюються. Новий вхід — окремий файл.
Виклик із Windows провідника подвійним кліком НЕ передбачений цією версією:
це штатний s01/SSH операторський CLI. Windows GUI потребує окремого джерельно
перевіреного мосту та жодних вбудованих паролів/SSH-ключів у клієнтській папці.
'''.encode('utf-8')

def entries(ws, root=ROOT):
    return [(ws/'input'/ENTRY, wrapper_bytes(root)), (ws/'input'/HELP, guide_bytes())]

def inspect(client, share=SHARE, root=ROOT):
    ws=workspace(client,share)
    need(is_file(root/'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py'), 'TRUSTED_GDL_OPERATOR_MISSING')
    need(is_file(root/'.venv_gdl/bin/python') or (root/'.venv_gdl/bin/python').is_symlink(), 'PYTHON_MISSING')
    existing=[]
    missing=[]
    for path, data in entries(ws,root):
        if is_file(path) and sha_bytes(path.read_bytes())==sha_bytes(data):
            existing.append(path)
        elif path.exists() or path.is_symlink():
            raise Blocked('EXISTING_CLIENT_LAUNCHER_FILE_DIFFERS_NO_OVERWRITE_'+path.name)
        else:
            missing.append(path)
    need(len(existing) in (0,len(entries(ws,root))), 'PARTIAL_CLIENT_DEPLOYMENT_NO_OVERWRITE')
    legacy=sorted(p.name for p in (ws/'input').iterdir()
                  if p.name not in (ENTRY,HELP) and p.suffix.lower() in ('.sh','.ps1','.bat','.cmd') and is_file(p))
    return ws, existing, missing, legacy

def install(client, share=SHARE, root=ROOT):
    ws,existing,missing,legacy=inspect(client,share,root)
    if existing:
        return 'ALREADY_INSTALLED'
    created=[]
    try:
        for path,data in entries(ws,root):
            with path.open('xb') as f:
                f.write(data);f.flush();os.fsync(f.fileno())
            os.chmod(path,0o644)
            created.append(path)
            need(sha_bytes(path.read_bytes()) == sha_bytes(data), 'POST_INSTALL_SHA_MISMATCH')
        return 'INSTALLED_SIDE_BY_SIDE'
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('check','install'),required=True)
    ap.add_argument('--client-name',required=True)
    ap.add_argument('--confirm-install',action='store_true')
    o=ap.parse_args(argv)
    try:
        ws, existing, missing, legacy=inspect(o.client_name)
        print(f'GC47AJ_CLIENT_WORKSPACE={ws}')
        print(f'GC47AJ_EXISTING_OTHER_LAUNCHERS={len(legacy)}')
        for name in legacy: print('GC47AJ_PRESERVED_LAUNCHER=' + name)
        if o.mode=='check':
            print('GC47AJ_CLIENT_ENTRY=' + ('ALREADY_INSTALLED' if existing else 'READY_ADD_ONLY'))
        else:
            need(o.confirm_install, 'EXPLICIT_CLIENT_INSTALL_CONFIRMATION_REQUIRED')
            print('GC47AJ_CLIENT_ENTRY=' + install(o.client_name))
        print('GC47AJ_NO_OLD_LAUNCHER_MUTATION=TRUE NO_WINDOWS_EXEC=TRUE NO_NATIVE_DISPATCH=TRUE')
        return 0
    except (Blocked,OSError,ValueError) as e:
        print('GC47AJ_CLIENT_ENTRY=BLOCKED_'+ (str(e) if isinstance(e,Blocked) else type(e).__name__),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
