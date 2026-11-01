#!/usr/bin/env python3
"""GC47AK: SSH TTY entry for the verified GC47AJ Ukrainian operator UI.

No authority is derived from the client-side CMD/PS1 files. The server
validates the requested identity against its own bounded SMB workspace.
This module is a non-release handoff only, not an additional renderer.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
from pathlib import Path
import re
import stat
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py'
UI_SHA256 = '11c917af001771dfa6e9e338492594d8e044c8c579a7f3b78f5e4bc423b360a6'
TOKEN_RE = re.compile(r'[A-Za-z0-9_-]{2,800}\Z', re.ASCII)

class Blocked(Exception):
    pass

def need(test, reason):
    if not test:
        raise Blocked(reason)

def regular(path):
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def encode_client(client):
    need(isinstance(client, str) and client not in ('', '.', '..'), 'CLIENT_EMPTY_OR_SPECIAL')
    need(client == unicodedata.normalize('NFC', client), 'CLIENT_UNICODE_NOT_NFC')
    need(len(client) <= 150, 'CLIENT_TOO_LONG')
    need(not any(ord(c) < 32 or c in '/\\' for c in client), 'CLIENT_PATH_CHARACTER')
    raw = client.encode('utf-8')
    need(len(raw) <= 600, 'CLIENT_UTF8_TOO_LONG')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

def decode_client(token):
    need(isinstance(token, str) and TOKEN_RE.fullmatch(token), 'CLIENT_TOKEN_INVALID')
    try:
        raw = base64.b64decode(token + '=' * (-len(token) % 4), altchars=b'-_', validate=True)
        client = raw.decode('utf-8', errors='strict')
    except (ValueError, UnicodeError) as exc:
        raise Blocked('CLIENT_TOKEN_DECODE_FAILED') from exc
    need(encode_client(client) == token, 'CLIENT_TOKEN_NOT_CANONICAL')
    return client

def load_ui():
    need(ROOT.name == 'forprint_graphic_design_lab', 'GDL_ROOT_INVALID')
    need((ROOT / '.git').exists(), 'GDL_GIT_MISSING')
    need(regular(UI) and digest(UI) == UI_SHA256, 'GC47AJ_SOURCE_NOT_PINNED')
    spec = importlib.util.spec_from_file_location('gc47ak_pinned_gc47aj', UI)
    need(spec is not None and spec.loader is not None, 'GC47AJ_IMPORT_UNAVAILABLE')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def bound_context(ui, client):
    # Check both identity and symlink boundaries in the trusted, existing AJ guard.
    ai = ui.ai_load()
    ws = ai.workspace(client)
    actual_client, actual_ws = ui.resolve_context(ai, ws / 'input')
    need(actual_client == client and actual_ws == ws, 'CLIENT_CONTEXT_MISMATCH')
    ai.source_guard()
    return ai, ws

def execute(mode, token):
    client = decode_client(token)
    ui = load_ui()
    ai, ws = bound_context(ui, client)
    if mode == 'check':
        print('GC47AK_WINDOWS_BRIDGE=PASS_PINNED_GDL_CONTEXT')
        print('GC47AK_CLIENT=' + client)
        print('GC47AK_NATIVE_DISPATCH=NOT_PERFORMED')
        return 0
    if mode == 'sources':
        ui.show_source(ai, client, ws)
        return 0
    if mode == 'attempts':
        for job, attempt, state in ui.list_attempts(ai, ws):
            print('GC47AK_ATTEMPT=' + attempt + ' JOB=' + job + ' STATE=' + state)
        return 0
    need(mode == 'interactive', 'MODE_INVALID')
    print('GC47AK_ENTRY=WINDOWS_SSH_TTY_TO_PINNED_GC47AJ')
    print('GC47AK_MODE=REVIEW_ONLY NO_AUTOMATIC_NATIVE_DISPATCH NO_AUTOMATIC_RETRY')
    return ui.interactive(ai, client, ws)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('check', 'sources', 'attempts', 'interactive'), default='interactive')
    parser.add_argument('--client-b64', required=True)
    args = parser.parse_args(argv)
    try:
        return execute(args.mode, args.client_b64)
    except (Blocked, OSError, ValueError, UnicodeError, EOFError) as exc:
        reason = str(exc) if isinstance(exc, Blocked) else type(exc).__name__.upper()
        print('GC47AK=BLOCKED_' + re.sub(r'[^A-Z0-9_]', '_', reason.upper())[:120], file=sys.stderr)
        print('GC47AK_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
