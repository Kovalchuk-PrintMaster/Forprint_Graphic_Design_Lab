#!/usr/bin/env python3
"""GC26: deploy the GC25 read-only Illustrator launcher into ONE SMB client input.

GDL on s01 owns rebuildable logic. No changes to Prepress Hub or existing files.
Modes: discover (read-only), check (read-only), install (create missing only).
No update/replace/delete; run under the operator's regular s01 authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SHARE_ROOT = Path('/srv/smb/In_Progress/data')
PINNED_LAUNCHER_SHA256 = {
    'gdl_greeting_card_illustrator_check_v0_1.ps1': '2968ca4b47365509809fc02a518e9bac8a1e37f48b841e135b0872dbb0906cd7',
    'launch_greeting_card_illustrator_check_v0_1.cmd': 'c375f8956dbd6f0fac8a6e82578f9086bc6756274ae40d96306ea39eba46493a',
}
SOURCES = (
    'scripts/graphic_design_lab/greeting_cards/windows/gdl_greeting_card_illustrator_check_v0_1.ps1',
    'scripts/graphic_design_lab/greeting_cards/windows/launch_greeting_card_illustrator_check_v0_1.cmd',
)

class Blocked(ValueError):
    """A safe, machine-readable refusal; no private customer details."""


def need(condition: Any, reason: str) -> None:
    if not condition:
        raise Blocked(reason)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def regular(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(info.st_mode)


def directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(info.st_mode)


def sources(root: Path = ROOT) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for relative in SOURCES:
        path = root / relative
        need(regular(path), 'PROJECT_LAUNCHER_SOURCE_MISSING_OR_UNSAFE')
        data = path.read_bytes()
        need(100 <= len(data) <= 100_000, 'PROJECT_LAUNCHER_SOURCE_SIZE_INVALID')
        result[path.name] = data
    need(len(result) == 2, 'PROJECT_LAUNCHER_SOURCE_COUNT')
    ps = result['gdl_greeting_card_illustrator_check_v0_1.ps1']
    cmd = result['launch_greeting_card_illustrator_check_v0_1.cmd']
    need(b'forprint_graphic_design_lab' in ps and b'gc25-illustrator-queue-check' in ps,
         'PROJECT_LAUNCHER_ROUTE_CHANGED')
    need(b'gdl_greeting_card_illustrator_check_v0_1.ps1' in cmd,
         'PROJECT_LAUNCHER_PAIR_CHANGED')
    for name, content in result.items():
        need(digest(content) == PINNED_LAUNCHER_SHA256[name],
             'PROJECT_LAUNCHER_SOURCE_SHA_CHANGED')
    return result


def client_workspace(name: str, share_root: Path = SHARE_ROOT) -> Path:
    need(isinstance(name, str) and bool(name.strip()) and name not in ('.', '..')
         and '/' not in name and '\\' not in name and '\x00' not in name,
         'CLIENT_NAME_INVALID')
    need(directory(share_root), 'SMB_SHARE_ROOT_MISSING_OR_UNSAFE')
    root = share_root.resolve(strict=True)
    client = root / name
    workspace = client / '_forprint_automation'
    incoming = workspace / 'input'
    outgoing = workspace / 'output'
    for p in (client, workspace, incoming, outgoing):
        need(directory(p), 'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(workspace.resolve(strict=True).parent.parent == root,
         'CLIENT_WORKSPACE_OUTSIDE_SHARE')
    return workspace


def audit(workspace: Path, data: dict[str, bytes]) -> dict[str, str]:
    folder = workspace / 'input'
    need(directory(folder), 'INPUT_DIRECTORY_UNSAFE')
    result = {}
    for filename, wanted in data.items():
        target = folder / filename
        if target.is_symlink():
            raise Blocked('CLIENT_LAUNCHER_SYMLINK_FORBIDDEN')
        if target.exists():
            need(regular(target), 'CLIENT_LAUNCHER_NOT_REGULAR')
            result[filename] = 'CURRENT' if digest(target.read_bytes()) == digest(wanted) else 'CONFLICT'
        else:
            result[filename] = 'MISSING'
    return result


def deploy(workspace: Path, data: dict[str, bytes], *, confirm: bool) -> dict[str, str]:
    need(confirm, 'EXPLICIT_INSTALL_CONFIRMATION_REQUIRED')
    before = audit(workspace, data)
    need('CONFLICT' not in before.values(), 'EXISTING_CLIENT_LAUNCHER_DIFFERS_NO_OVERWRITE')
    result = dict(before)
    for filename, content in data.items():
        if before[filename] == 'CURRENT':
            continue
        target = workspace / 'input' / filename
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o644)
        except FileExistsError as exc:
            raise Blocked('CONCURRENT_TARGET_EXISTS_RECONCILE') from exc
        try:
            with os.fdopen(fd, 'wb') as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            # Leave a possibly partial file in place for operator reconciliation.
            # Never delete, replace, or silently retry client files.
            raise
        need(regular(target) and digest(target.read_bytes()) == digest(content),
             'INSTALLED_FILE_VERIFY_FAILED')
        result[filename] = 'INSTALLED'
    need(set(audit(workspace, data).values()) == {'CURRENT'},
         'POSTINSTALL_VERIFICATION_FAILED')
    return result


def discover(share_root: Path = SHARE_ROOT) -> tuple[int, int]:
    need(directory(share_root), 'SMB_SHARE_ROOT_MISSING_OR_UNSAFE')
    clients = 0
    candidates = 0
    for client in sorted(share_root.iterdir(), key=lambda x: x.name.casefold()):
        if not directory(client):
            continue
        clients += 1
        try:
            ws = client_workspace(client.name, share_root)
        except Blocked:
            continue
        candidates += 1
        input_dir = ws / 'input'
        pdf_launcher = (input_dir / 'launch_greeting_card_queue.cmd').is_file()
        illustrator_launcher = (input_dir / 'launch_greeting_card_illustrator_check_v0_1.cmd').is_file()
        zip_count = sum(1 for p in input_dir.iterdir() if p.suffix.casefold() == '.zip' and regular(p))
        print(f'GC26_CLIENT={client.name} PDF_LAUNCHER={str(pdf_launcher).lower()} '
              f'ILLUSTRATOR_LAUNCHER={str(illustrator_launcher).lower()} INPUT_ZIPS={zip_count}')
    print(f'GC26_DISCOVERED_WORKSPACES={candidates} CLIENT_DIRECTORIES={clients}')
    return candidates, clients


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('discover', 'check', 'install'), required=True)
    parser.add_argument('--client-name')
    parser.add_argument('--confirm-install', action='store_true')
    a = parser.parse_args()
    try:
        need(a.mode != 'discover' or (a.client_name is None and not a.confirm_install),
             'DISCOVER_ACCEPTS_NO_CLIENT_OR_CONFIRMATION')
        if a.mode == 'discover':
            discover()
            print('GDL_GC26_CLIENT_DEPLOY=DISCOVER_PASS_READ_ONLY')
            return 0
        need(a.client_name is not None, 'CLIENT_NAME_REQUIRED')
        need(a.mode == 'install' or not a.confirm_install, 'CHECK_MUST_BE_READ_ONLY')
        ws = client_workspace(a.client_name)
        data = sources()
        if a.mode == 'check':
            result = audit(ws, data)
            for filename, state in result.items():
                print(f'GC26_TARGET={filename} STATUS={state} SOURCE_SHA256={digest(data[filename])}')
            need('CONFLICT' not in result.values(), 'EXISTING_CLIENT_LAUNCHER_DIFFERS_NO_OVERWRITE')
            print('GDL_GC26_CLIENT_DEPLOY=CHECK_PASS_READ_ONLY')
            return 0
        result = deploy(ws, data, confirm=a.confirm_install)
        for filename, state in result.items():
            print(f'GC26_TARGET={filename} STATUS={state} SHA256={digest(data[filename])}')
        print('GDL_GC26_CLIENT_DEPLOY=INSTALL_VERIFIED')
        print('PDF_LAUNCHER_UNCHANGED=true CLIENT_ZIPS_UNCHANGED=true NATIVE_RENDER=false')
        return 0
    except (Blocked, OSError) as exc:
        error = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        print(f'GDL_GC26_CLIENT_DEPLOY=BLOCKED reason={error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
