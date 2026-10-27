#!/usr/bin/env python3
"""TS r010: bounded, non-authorizing, read-only inventory of existing native results.

Never invokes Illustrator/SSH, never modifies Windows/SMB, never treats a
worker's JSON self-report as independent evidence of a native AI structure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'forprint_ts_r010_native_evidence_inventory_v0_1'
EXPECTED = ('design.ai', 'review.pdf', 'preview_p01.png', 'preview_p02.png',
            'preview_p03.png', 'preview_p04.png', 'result.json')
GC27_EXPECTED = ('p03_proof.ai', 'p03_proof.pdf', 'preview_p03.png', 'result.json')
MAX_RUNS_PER_ROOT = 100
MAX_FILE_SIZE = 250 * 1024 * 1024
MAX_JSON_SIZE = 256 * 1024
NAME = re.compile(r'^[A-Za-z0-9_.-]{1,160}$')
RUN_ID = re.compile(r'^[A-Za-z0-9_-]{8,100}$')
SAFE_RUN_LABEL = re.compile(r'^gdl_gc_[a-z0-9_]+__[a-f0-9]{14}$')


def safe_dir(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        return stat.S_ISDIR(mode) and not stat.S_ISLNK(mode)
    except FileNotFoundError:
        return False


def safe_file(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        return stat.S_ISREG(mode) and not stat.S_ISLNK(mode)
    except FileNotFoundError:
        return False


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect_file(path: Path) -> dict:
    if path.is_symlink():
        return {'state': 'UNSAFE_SYMLINK', 'sha256': None}
    if not path.exists():
        return {'state': 'MISSING', 'sha256': None}
    if not safe_file(path):
        return {'state': 'NOT_REGULAR_FILE', 'sha256': None}
    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        return {'state': 'SIZE_LIMIT', 'bytes': size, 'sha256': None}
    return {'state': 'PRESENT_HASHED', 'bytes': size, 'sha256': digest(path)}


def read_limited_json(path: Path) -> tuple[dict | None, str]:
    if not safe_file(path):
        return None, 'NOT_AVAILABLE_OR_UNSAFE'
    if path.stat().st_size > MAX_JSON_SIZE:
        return None, 'JSON_SIZE_LIMIT'
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (UnicodeError, ValueError, OSError):
        return None, 'JSON_INVALID'
    if not isinstance(data, dict):
        return None, 'JSON_NOT_OBJECT'
    return data, 'JSON_READABLE'


def selected_result(data: dict | None) -> dict:
    if data is None:
        return {'state': 'NOT_AVAILABLE', 'schema_version': None,
                'self_report_reopen': False, 'visual_approved': False,
                'production_ready': False}
    state = data.get('state')
    schema = data.get('schema_version')
    # Deliberately do not publish free-form error strings or private fields.
    return {'state': state if isinstance(state, str) and len(state) < 128 else 'INVALID_STATE',
            'schema_version': schema if isinstance(schema, str) and len(schema) < 128 else None,
            'self_report_reopen': state in ('AI_REOPENED_VISUAL_REVIEW_REQUIRED',
                                             'P03_NATIVE_AI_REOPENED_VISUAL_REVIEW_REQUIRED'),
            'visual_approved': data.get('visual_approved') is True,
            'production_ready': data.get('production_ready') is True}


def artifact_set(folder: Path, expected: tuple[str, ...]) -> dict:
    if folder.is_symlink():
        return {'directory': 'UNSAFE_SYMLINK', 'artifacts': {}, 'result': selected_result(None),
                'result_parse': 'NOT_READ'}
    if not safe_dir(folder):
        return {'directory': 'MISSING', 'artifacts': {}, 'result': selected_result(None),
                'result_parse': 'NOT_READ'}
    files = {name: inspect_file(folder / name) for name in expected}
    obj, parse = read_limited_json(folder / 'result.json')
    return {'directory': 'PRESENT', 'artifacts': files,
            'result': selected_result(obj), 'result_parse': parse}


def evidence_for_run(name: str, ws: Path, native: Path | None, returned: Path | None) -> dict:
    src = native if native is not None else ws / 'template_studio' / 'native_runs' / name
    out = src / 'out'
    dest = returned if returned is not None else ws / 'output' / 'illustrator_review' / name
    run = {'run_name': name if SAFE_RUN_LABEL.fullmatch(name) else 'sha256-'+hashlib.sha256(name.encode('utf8')).hexdigest()[:16], 'source_scope': 'SMB_SELF_REPORT_AND_FILE_HASHES_ONLY',
           'authority': 'NO_APPROVAL_NO_EXECUTION',
           'scene_manifest': inspect_file(src / 'scene_manifest.json') if safe_dir(src) else {'state':'NOT_AVAILABLE'},
           'jsx': inspect_file(src / 'run_in_illustrator.jsx') if safe_dir(src) else {'state':'NOT_AVAILABLE'},
           'worker_out': artifact_set(out, EXPECTED),
           'returned_review': artifact_set(dest, EXPECTED)}
    scene, status = read_limited_json(src / 'scene_manifest.json') if safe_dir(src) else (None, 'NOT_AVAILABLE')
    run['scene_parse'] = status
    run['scene_scope'] = {'pages_declared': scene.get('pages') if scene and type(scene.get('pages')) is int else None,
                          'production_ready_declared_false': scene.get('production_ready') is False if scene else False}
    for label, p in [('queued_ticket', ws / 'template_studio' / 'dispatch' / 'queued' / (name + '.json')),
                     ('worker_stage', ws / 'template_studio' / 'dispatch' / 'status' / (name + '.stage.json'))]:
        run[label] = inspect_file(p) if safe_dir(p.parent) else {'state':'NOT_AVAILABLE'}
    a, b = run['worker_out'], run['returned_review']
    if a['directory'] == 'PRESENT' and b['directory'] == 'PRESENT':
        common = []
        unequal = []
        for n in EXPECTED:
            fa, fb = a['artifacts'][n], b['artifacts'][n]
            if fa.get('sha256') is not None and fb.get('sha256') is not None:
                (common if fa['sha256'] == fb['sha256'] else unequal).append(n)
        run['return_comparison'] = {'identical_files': len(common), 'different_files': unequal,
                                    'all_seven_equal': len(common) == len(EXPECTED)}
    else:
        run['return_comparison'] = {'all_seven_equal': False, 'state': 'NOT_COMPARABLE'}
    reported = [a['result'], b['result']]
    run['self_report_reopen_present'] = any(r['self_report_reopen'] for r in reported)
    run['native_layers_attested'] = False
    run['independent_reopen_attested'] = False
    run['visual_parity_attested'] = False
    run['production_authority_granted'] = False
    return run


def list_safe_children(root: Path, max_count: int) -> tuple[list[Path], bool, list[str]]:
    if not safe_dir(root):
        return [], False, []
    children = sorted(root.iterdir(), key=lambda p: p.name)
    # Include only simple safe names; unusual names are accounted for, not opened.
    invalid = [p for p in children if not NAME.fullmatch(p.name)]
    valid = [p for p in children if NAME.fullmatch(p.name)]
    truncated = len(valid) > max_count
    return valid[:max_count], truncated or bool(invalid), invalid[:10]


def scan(ws: Path, optional_gc27_dirs: list[Path] | None = None) -> dict:
    if not safe_dir(ws):
        raise ValueError('CLIENT_WORKSPACE_MISSING_OR_UNSAFE')
    native = ws / 'template_studio' / 'native_runs'
    returned = ws / 'output' / 'illustrator_review'
    entries_a, trunc_a, invalid_a = list_safe_children(native, MAX_RUNS_PER_ROOT)
    entries_b, trunc_b, invalid_b = list_safe_children(returned, MAX_RUNS_PER_ROOT)
    # Inventory includes symlink status; never descend through directory symlinks.
    from_native = {p.name: p for p in entries_a}
    from_returned = {p.name: p for p in entries_b}
    names = sorted(set(from_native) | set(from_returned))
    runs = [evidence_for_run(n, ws, from_native.get(n), from_returned.get(n)) for n in names]
    gc27 = []
    for p in optional_gc27_dirs or []:
        if p.is_symlink() or not safe_dir(p):
            gc27.append({'scope':'GC27_SINGLE_PAGE', 'directory':'UNSAFE_OR_MISSING',
                         'artifacts':{}, 'native_layers_attested':False})
        else:
            gc27.append({'scope':'GC27_SINGLE_PAGE',
                         'run_id_sha256_prefix':hashlib.sha256(str(p).encode('utf8')).hexdigest()[:16],
                         'out':artifact_set(p / 'out', GC27_EXPECTED),
                         'native_layers_attested':False,
                         'visual_parity_attested':False})
    return {'schema_version': SCHEMA, 'source_kind': 'BOUNDED_EXISTING_SMB_EVIDENCE_INVENTORY',
            'scan_truncated': trunc_a or trunc_b,
            'scan_boundaries': {'native_runs_max_direct_children':MAX_RUNS_PER_ROOT,
                                'returned_review_max_direct_children':MAX_RUNS_PER_ROOT,
                                'no_recursive_client_search':True, 'max_file_hash_bytes':MAX_FILE_SIZE},
            'unexpected_name_counts': {'native_runs':len(invalid_a), 'returned_review':len(invalid_b)},
            'counts': {'run_candidates':len(runs), 'gc27_optional_dirs':len(gc27),
                       'runs_with_worker_self_report_reopen':sum(x['self_report_reopen_present'] for x in runs),
                       'runs_with_returned_hash_parity':sum(x['return_comparison'].get('all_seven_equal',False) for x in runs)},
            'runs':runs, 'gc27':gc27,
            'conclusion': {'source_files_only':False,
                           'metadata_and_sha256_only':True,
                           'independent_ai_reopen_attested':False,
                           'illustrator_layer_parity_attested':False,
                           'visual_approved':False,
                           'client_published':False,
                           'production_ready':False,
                           'automatic_promotion':False}}


def cli(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('check','capture'), required=True)
    p.add_argument('--gdl-root', type=Path, required=True)
    p.add_argument('--client-name', required=True)
    p.add_argument('--share-root', type=Path, default=Path('/srv/smb/In_Progress/data'))
    p.add_argument('--run-id')
    p.add_argument('--gc27-private-run', action='append', type=Path, default=[])
    p.add_argument('--confirm-local-report', action='store_true')
    a = p.parse_args(argv)
    root = a.gdl_root.absolute()
    if not safe_dir(root) or not safe_dir(root / 'tmp'):
        raise SystemExit('TS_R010_BLOCKED=GDL_ROOT_OR_TMP_UNSAFE')
    if not a.client_name or a.client_name in ('.','..') or any(c in a.client_name for c in '/\\\x00'):
        raise SystemExit('TS_R010_BLOCKED=INVALID_CLIENT_NAME')
    if not safe_dir(a.share_root):
        raise SystemExit('TS_R010_BLOCKED=SHARE_UNAVAILABLE')
    client = a.share_root / a.client_name
    ws = client / '_forprint_automation'
    if not safe_dir(client) or not safe_dir(ws):
        raise SystemExit('TS_R010_BLOCKED=CLIENT_WORKSPACE_UNSAFE_OR_MISSING')
    for private in a.gc27_private_run:
        resolved = private.absolute()
        try:
            rel = resolved.relative_to(root / 'tmp')
        except ValueError:
            raise SystemExit('TS_R010_BLOCKED=PRIVATE_RUN_OUTSIDE_GDL_TMP')
        if len(rel.parts) > 2:
            raise SystemExit('TS_R010_BLOCKED=PRIVATE_RUN_TOO_DEEP')
    print('TS_R010_WORKSPACE=AVAILABLE')
    print('TS_R010_SOURCE_MUTATION=FORBIDDEN')
    if a.mode == 'check':
        print('TS_R010_PREFLIGHT=PASS_READ_ONLY')
        return 0
    if not a.confirm_local_report or not a.run_id or not RUN_ID.fullmatch(a.run_id):
        raise SystemExit('TS_R010_BLOCKED=EXPLICIT_LOCAL_REPORT_CONFIRMATION_REQUIRED')
    base = root / 'tmp' / 'ts_r010_native_evidence'
    if base.is_symlink():
        raise SystemExit('TS_R010_BLOCKED=UNSAFE_REPORT_ROOT')
    if not base.exists(): base.mkdir(mode=0o700)
    if not safe_dir(base):
        raise SystemExit('TS_R010_BLOCKED=UNSAFE_REPORT_ROOT')
    dest = base / a.run_id
    if dest.exists() or dest.is_symlink():
        raise SystemExit('TS_R010_BLOCKED=EXISTING_REPORT_NO_OVERWRITE')
    report = scan(ws, a.gc27_private_run)
    report['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    report['client_name_not_exported'] = True
    dest.mkdir(mode=0o700)
    path = dest / 'inventory.json'
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + '\n',encoding='utf8')
    (dest / 'inventory.sha256').write_text(digest(path) + '  inventory.json\n', encoding='ascii')
    print('TS_R010_CAPTURE=PASS_READ_ONLY_SOURCES')
    print('TS_R010_RUN_DIR=' + str(dest.relative_to(root)))
    print('TS_R010_RUNS=' + str(report['counts']['run_candidates']))
    print('TS_R010_SELF_REPORTED_REOPEN=' + str(report['counts']['runs_with_worker_self_report_reopen']))
    print('TS_R010_HASH_PARITY=' + str(report['counts']['runs_with_returned_hash_parity']))
    print('TS_R010_SCAN_TRUNCATED=' + str(report['scan_truncated']).lower())
    print('TS_R010_NATIVE_ATTESTATION=NOT_GRANTED')
    return 0


if __name__ == '__main__':
    raise SystemExit(cli())
