#!/usr/bin/env python3
"""GC47AI: GDL existing-chain operator launcher, Illustrator-first, lab review only.

No redesign, intake conversion, renderer, automatic retry or production approval.
Client ZIPs are examined, never extracted or modified by this launcher.
Actual dispatch delegates to pinned GC47U + GC47T (GC47S/GC29/GC25 inside).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SHARE = Path('/srv/smb/In_Progress/data')
SRC = ROOT / 'scripts/graphic_design_lab'
GC47T = SRC / 'greeting_cards/gc47t_client_windows_bridge_r001.py'
GC47U = SRC / 'worker_runtime/gc47u_node_readiness_v0_1.py'
VENV = ROOT / '.venv_gdl/bin/python'
EXPECTED = {
    'greeting_cards/gc47t_client_windows_bridge_r001.py': 'c99fde8a5f5805da57b5cca037cda17a34dea002a076042279bd274c4848ef46',
    'worker_runtime/gc47u_node_readiness_v0_1.py': '2babaff06047db6090d0f92eec2944513baac9d73a1187e6d023f5b115471201',
}
MAX_CLIENTS = 1000
MAX_ARCHIVES = 100
MAX_ZIP = 40 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_MEMBERS = 300
JOB_RE = re.compile(r'^[a-z0-9][a-z0-9_.-]{3,95}$')
ATTEMPT_RE = re.compile(r'^p\d{14}-[0-9a-f]{8}$')

class Blocked(Exception):
    pass


def need(value, code):
    if not value:
        raise Blocked(code)


def regular(path):
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def folder(path):
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_guard():
    need(ROOT.name == 'forprint_graphic_design_lab' and folder(ROOT / '.git'), 'GDL_ROOT_INVALID')
    need(VENV.exists() and os.access(VENV, os.X_OK), 'GDL_PYTHON_VENV_MISSING')
    for relative, expected in EXPECTED.items():
        candidate = SRC / relative
        need(regular(candidate) and sha256(candidate) == expected, 'SOURCE_DRIFT_' + candidate.name.upper().replace('.', '_'))
    need(regular(ROOT / 'coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json'), 'GC47K_MISSING')


def workspace(client, share=SHARE):
    need(isinstance(client, str) and bool(client) and client not in ('.', '..') and
         not any(x in client for x in ('/', '\\', '\x00', '\n', '\r')), 'CLIENT_NAME_INVALID')
    need(folder(share), 'SMB_SHARE_MISSING')
    root = share.resolve(strict=True)
    client_dir = share / client
    ws = client_dir / '_forprint_automation'
    for node in (client_dir, ws, ws / 'input', ws / 'output', ws / 'template_studio'):
        need(folder(node), 'CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    need(ws.resolve(strict=True).parent.parent == root, 'WORKSPACE_OUTSIDE_SHARE')
    return ws


def clients(share=SHARE):
    need(folder(share), 'SMB_SHARE_MISSING')
    names = []
    for entry in share.iterdir():
        if len(names) >= MAX_CLIENTS:
            raise Blocked('CLIENT_SCAN_LIMIT')
        if not folder(entry):
            continue
        try:
            workspace(entry.name, share)
        except (Blocked, ValueError, OSError):
            continue
        names.append(entry.name)
    return sorted(names, key=str.casefold)


def input_zips(ws):
    files = []
    for p in (ws / 'input').iterdir():
        if p.name.lower().endswith('.zip') and regular(p):
            need(0 < p.stat().st_size <= MAX_ZIP, 'CLIENT_ZIP_SIZE_INVALID')
            files.append(p)
    need(len(files) <= MAX_ARCHIVES, 'CLIENT_ARCHIVE_SCAN_LIMIT')
    return sorted(files, key=lambda x: x.name.casefold())


def inspect_zip(path, verify_crc=True):
    """Review-only validation; does NOT mark the archive accepted by GC25."""
    need(regular(path) and 0 < path.stat().st_size <= MAX_ZIP, 'CLIENT_ZIP_INVALID')
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        need(0 < len(infos) <= MAX_MEMBERS, 'ZIP_MEMBER_COUNT')
        names, folded, total = set(), set(), 0
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            need(not info.is_dir() and not pure.is_absolute() and
                 all(part not in ('', '.', '..') for part in pure.parts) and
                 '\\' not in name and '\x00' not in name and
                 not name.startswith('/') and '//' not in name and '/./' not in name and not name.startswith('./') and not name.endswith('/.') and not re.match(r'^[A-Za-z]:', name) and
                 not stat.S_ISLNK(info.external_attr >> 16), 'ZIP_MEMBER_PATH_OR_TYPE_UNSAFE')
            need(name not in names and name.casefold() not in folded, 'ZIP_DUPLICATE_MEMBER')
            need(not (info.flag_bits & 0x1), 'ZIP_ENCRYPTED')
            need(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'ZIP_UNSUPPORTED_COMPRESSION')
            names.add(name)
            folded.add(name.casefold())
            total += info.file_size
            need(info.file_size <= MAX_EXPANDED and total <= MAX_EXPANDED, 'ZIP_EXPANDED_SIZE_LIMIT')
            if info.file_size > 1_000_000:
                need(info.compress_size > 0 and info.file_size / info.compress_size < 250,
                     'ZIP_COMPRESSION_RATIO_LIMIT')
        if verify_crc:
            need(z.testzip() is None, 'ZIP_CRC_FAILED')
    return {'name': path.name, 'bytes': path.stat().st_size,
            'members': len(infos), 'sha256': sha256(path),
            'crc_checked': verify_crc}


def trusted_bridge():
    source_guard()
    spec = importlib.util.spec_from_file_location('gc47ai_existing_gc47t', GC47T)
    need(spec and spec.loader, 'GC47T_SOURCE_IMPORT_INVALID')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def accepted_jobs(client, share=SHARE):
    bridge = trusted_bridge()
    s, gc29 = bridge.source_check()
    # Existing operators own authoritative GC25/GC29 intake proof.
    # On production server the same share is used; no alternate injected share.
    ws = workspace(client, share)
    need(ws == s.workspace(client), 'SHARE_BOUNDARY_MISMATCH')
    jobs, _manifest, archive = gc29.accepted_jobs(ws)
    summary = []
    for job in jobs:
        job_id = job.get('job_id')
        need(isinstance(job_id, str) and JOB_RE.fullmatch(job_id), 'ACCEPTED_JOB_ID_INVALID')
        profile, supported = s.classify(job)
        summary.append({'id': job_id, 'profile': profile, 'illustrator_supported': supported})
    need(len({j['id'] for j in summary}) == len(summary), 'ACCEPTED_JOB_DUPLICATE')
    return summary, archive


def call_existing(script, args, runner=subprocess.run):
    """Subprocess boundary, no shell, no retry. Testable with an injected runner."""
    source_guard()
    command = [str(VENV), '-B', str(script), *args]
    ret = runner(command, cwd=ROOT, check=False)
    need(ret.returncode == 0, 'EXISTING_CHAIN_FAILED_RC_' + str(ret.returncode))


def selected_job(client, job):
    need(isinstance(job, str) and JOB_RE.fullmatch(job), 'JOB_ID_UNSAFE')
    jobs, archive = accepted_jobs(client)
    match = [j for j in jobs if j['id'] == job]
    need(len(match) == 1, 'JOB_NOT_ACCEPTED')
    need(match[0]['illustrator_supported'], 'ILLUSTRATOR_PROFILE_NOT_IMPLEMENTED')
    need(regular(archive), 'ACCEPTED_ARCHIVE_MISSING')
    inspect_zip(archive, verify_crc=True)
    return match[0]


def pilot(client, job, route, confirm=False, runner=subprocess.run):
    need(route in ('illustrator', 'server-local'), 'UNKNOWN_ROUTE')
    # Server/local must block without preparing any attempt or invoking GC29.
    if route == 'server-local':
        print('GC47AI_SERVER_LOCAL=BLOCKED_RENDERER_CAPABILITY_NOT_PROVEN')
        print('GC47AI_NO_FAKE_OUTPUT=TRUE NO_DISPATCH=TRUE')
        return 2
    need(confirm, 'EXPLICIT_SINGLE_USE_CONFIRMATION_REQUIRED')
    chosen = selected_job(client, job)
    print('GC47AI_PROFILE=' + '/'.join(str(chosen['profile'][k]) for k in ('front','image','signature')), flush=True)
    # First gate is only transient; GC47T rechecks preflight before starting.
    call_existing(GC47U, ['--mode', 'gate', '--route', 'illustrator'], runner)
    call_existing(GC47T, ['--mode', 'check', '--client-name', client, '--job-id', job], runner)
    print('GC47AI_DISPATCH=EXACTLY_ONE_GC47T_ATTEMPT_NO_AUTO_RETRY', flush=True)
    call_existing(GC47T, ['--mode','pilot','--client-name',client,'--job-id',job,
                         '--confirm-native-once'], runner)
    print('GC47AI_CHECKPOINT=ILLUSTRATOR_REVIEW_ONLY_NON_RELEASE')
    return 0


def status_or_collect(mode, client, job, attempt, confirm=False, runner=subprocess.run):
    need(JOB_RE.fullmatch(job or '') and ATTEMPT_RE.fullmatch(attempt or ''), 'JOB_OR_ATTEMPT_UNSAFE')
    workspace(client)
    if mode == 'collect':
        need(confirm, 'EXPLICIT_COLLECTION_CONFIRMATION_REQUIRED')
    args = ['--mode',mode,'--client-name',client,'--job-id',job,'--attempt-id',attempt]
    if mode == 'collect':
        args.append('--confirm-native-once')
    call_existing(GC47T, args, runner)
    return 0


def choose(items, caption):
    need(items, 'NO_' + caption.upper().replace(' ', '_'))
    for index, value in enumerate(items, 1):
        print(f'  {index}. {value}')
    raw = input(caption + ' [1-' + str(len(items)) + ', q=exit]: ').strip()
    need(raw.isdecimal() and 1 <= int(raw) <= len(items), 'SELECTION_CANCELLED_OR_INVALID')
    return items[int(raw)-1]


def interactive():
    print('GC47AI=ILLUSTRATOR_FIRST_LAB_REVIEW_NON_RELEASE')
    client = choose(clients(), 'Client')
    ws = workspace(client)
    zips = input_zips(ws)
    print('GC47AI_INTAKE_ZIPS=' + str(len(zips)))
    for p in zips:
        record = inspect_zip(p)
        print('GC47AI_INPUT=' + record['name'] + ' CRC=PASS SHA256=' + record['sha256'])
    jobs, archive = accepted_jobs(client)
    print('GC47AI_ACCEPTED_SOURCE_SHA256=' + sha256(archive))
    job = choose([j['id'] for j in jobs], 'Job')
    route = choose(['illustrator','server-local'], 'Route')
    if route == 'server-local':
        return pilot(client, job, route)
    chosen = [j for j in jobs if j['id'] == job][0]
    need(chosen['illustrator_supported'], 'ILLUSTRATOR_PROFILE_NOT_IMPLEMENTED')
    print('ONE_NATIVE_ATTEMPT, no automatic repeat, no production approval.')
    typed = input('Type LAUNCH ' + job + ' to authorize a single Illustrator attempt: ').strip()
    need(typed == 'LAUNCH ' + job, 'OPERATOR_CONFIRMATION_FAILED')
    return pilot(client, job, route, confirm=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', required=True, choices=('check','list','inspect','routes','interactive','pilot','status','collect'))
    ap.add_argument('--client-name')
    ap.add_argument('--job-id')
    ap.add_argument('--route', choices=('illustrator','server-local'), default='illustrator')
    ap.add_argument('--attempt-id')
    ap.add_argument('--confirm-native-once',action='store_true')
    o=ap.parse_args(argv)
    try:
        if o.mode == 'check':
            bridge = trusted_bridge()
            bridge.source_check()
            print('GC47AI_SOURCE=GC47T_GC47U_PINNED_GC47K_PROFILE_VERIFIED_READ_ONLY')
        elif o.mode == 'list':
            for index, client in enumerate(clients(),1):
                print('GC47AI_CLIENT_INDEX=' + str(index) + ' CLIENT=' + client)
            print('GC47AI_LIST=PRIVATE_OPERATOR_VIEW_ONLY')
        elif o.mode == 'inspect':
            need(o.client_name, 'CLIENT_NAME_REQUIRED')
            ws = workspace(o.client_name)
            for p in input_zips(ws):
                record = inspect_zip(p)
                print('GC47AI_INPUT=' + record['name'] + ' MEMBERS=' + str(record['members']) + ' SHA256=' + record['sha256'] + ' CRC=PASS')
            jobs, archive = accepted_jobs(o.client_name)
            print('GC47AI_ACCEPTED_ZIP_SHA256=' + sha256(archive))
            for job in jobs:
                print('GC47AI_JOB=' + job['id'] + ' PROFILE=' + '/'.join(str(job['profile'][k]) for k in ('front','image','signature')) + ' ILLUSTRATOR_SUPPORTED=' + str(job['illustrator_supported']).upper())
            print('GC47AI_INSPECT=GC25_ACCEPTED_GATE_PLUS_ZIP_CRC_NON_RELEASE')
        elif o.mode == 'routes':
            call_existing(GC47U, ['--mode','routes'])
        elif o.mode == 'interactive':
            return interactive()
        elif o.mode == 'pilot':
            need(o.client_name and o.job_id, 'CLIENT_AND_JOB_REQUIRED')
            return pilot(o.client_name,o.job_id,o.route,o.confirm_native_once)
        elif o.mode in ('status','collect'):
            need(o.client_name and o.job_id and o.attempt_id, 'CLIENT_JOB_ATTEMPT_REQUIRED')
            return status_or_collect(o.mode,o.client_name,o.job_id,o.attempt_id,o.confirm_native_once)
        print('GC47AI_PRODUCTION_READY=FALSE VISUAL_APPROVED=FALSE DUAL_RUNTIME=DISABLED')
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, EOFError) as exc:
        code = str(exc) if isinstance(exc,Blocked) else type(exc).__name__.upper()
        print('GC47AI=BLOCKED_' + re.sub(r'[^A-Z0-9_]', '_', code.upper())[:130], file=sys.stderr)
        print('GC47AI_NO_AUTO_RETRY=TRUE NO_RELEASE=TRUE', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
