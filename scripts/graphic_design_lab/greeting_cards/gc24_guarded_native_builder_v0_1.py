#!/usr/bin/env python3
"""GC24: approved-input gate for the existing GC21 native Illustrator *pilot*.

This is deliberately NOT a new renderer or variant activation. GC23 approves
source identities / semantic contract; GC21 still supports only the explicitly
proven STANDARD/PORTRAIT/HERASYMENKO scene. No Prepress Hub runtime imports.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
GC23_PATH = HERE / 'gc23_prepress_variant_contract_v0_1.py'
GC21_PATH = HERE / 'gc21_native_illustrator_builder_v0_1.py'

# These exact historical GC09B pilot input digests must NEVER authorize
# a customer-facing candidate, including when user-supplied explicitly.
FORBIDDEN_GC09B_INPUT_SHA = frozenset({
    '0aedc7e09db54a9cc2fb1e85085bd4305f232a51983121839634a83fe5dab709',
    'f01312d36937791fd5fbc876ed357ba84b9c5bf888691eb40fb1cae955f8a43e',
    'cb67ce7ad9e9832f6b9a63b5f00529986f54e21c4c50e1f5f468364d7064c0c4',
})
LEGACY_DIR = 'gdl_gc09b_real_pdf_proof_20261010'
BIRTHDAY_TITLE = 'Привітання з нагоди Дня Народження!'

class GC24Blocked(ValueError):
    pass


def require(value: Any, reason: str) -> None:
    if not value:
        raise GC24Blocked(reason)


def import_checked(path: Path, name: str) -> Any:
    require(path.is_file() and not path.is_symlink(), 'REQUIRED_MODULE_MISSING')
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, 'MODULE_LOAD_BLOCKED')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def real_input_preflight(config: Path, source_root: Path, gc23: Any) -> tuple[dict, dict]:
    """Check accepted input without writing files or disclosing customer data."""
    require(config.is_file() and not config.is_symlink(), 'INPUT_CONFIG_MISSING')
    require(LEGACY_DIR not in config.resolve().parts, 'GC09B_SANITIZED_INPUT_PATH_BLOCKED')
    snap = gc23.catalog()
    projection = gc23.projection(config, source_root, snap)
    require(len(projection['jobs']) == 1, 'GC21_SINGLE_JOB_ONLY')
    plan = projection['jobs'][0]
    require(plan['gate'] == 'CONTRACT_VALID_RUNTIME_FAMILY', 'VARIANT_RUNTIME_GATE_REQUIRED')
    require(plan['front_family'] == 'STANDARD', 'GC21_FRONT_VARIANT_NOT_IMPLEMENTED')
    require(plan['inside_image_mode'] == 'PORTRAIT', 'GC21_PHOTO_VARIANT_NOT_IMPLEMENTED')
    require(plan['signature_variant'] == 'HERASYMENKO', 'GC21_SENDER_VARIANT_NOT_IMPLEMENTED')
    config_map = gc23.load_mapping(config)
    require(set(config_map) == {'bundle','resource_manifest','artifact_manifest'}, 'CONFIG_KEYS_INVALID')
    files = {name: gc23.resolve_private(raw, source_root) for name, raw in config_map.items()}
    digests = {name: sha256_file(path) for name, path in files.items()}
    require(not set(digests.values()).intersection(FORBIDDEN_GC09B_INPUT_SHA), 'GC09B_SANITIZED_INPUT_SHA_BLOCKED')
    bundle = gc23.load_mapping(files['bundle'])
    job = bundle['jobs'][0]
    # The first native Illustrator renderer only draws one exact source title.
    require(job['builder_v1']['front']['occasion']['display_text'] == BIRTHDAY_TITLE,
            'GC21_OCCASION_VARIANT_NOT_IMPLEMENTED')
    require(all(re.fullmatch(r'[0-9a-f]{64}', value) for value in digests.values()),
            'INPUT_SHA_INVALID')
    return projection, digests


def run(args: argparse.Namespace, *, gc23: Any = None, gc21: Any = None) -> int:
    require((args.mode == 'prepare') == bool(args.confirm_private_prepare),
            'PREPARE_CONFIRMATION_REQUIRED')
    require((args.mode == 'prepare') == (args.output_name is not None),
            'OUTPUT_MODE_MISMATCH')
    require((args.mode == 'prepare') == bool(args.confirm_reviewed_real_inputs),
            'REAL_INPUT_REVIEW_CONFIRMATION_REQUIRED')
    require(args.source_root.is_dir(), 'SOURCE_ROOT_MISSING')
    gc23 = gc23 if gc23 is not None else import_checked(GC23_PATH, 'gc24_gc23_contract')
    _, digests = real_input_preflight(args.inputs_config, args.source_root, gc23)
    gc21 = gc21 if gc21 is not None else import_checked(GC21_PATH, 'gc24_gc21_native')
    require(args.gc19_assets_dir.is_dir() and args.gc20_scene_dir.is_dir(),
            'GC19_GC20_SOURCE_MISSING')
    root_tmp = (ROOT / 'tmp').resolve()
    for d in (args.gc19_assets_dir, args.gc20_scene_dir):
        require(not d.is_symlink() and d.resolve().is_relative_to(root_tmp),
                'GC19_GC20_NOT_UNDER_GDL_TMP')
    # Replace historical fixed pilot input hashes *only in this process*,
    # with the SHA256 of GC23-verified accepted inputs. The fixed source PDF,
    # font, canonical signature, artwork and mask proofs remain checked by GC21.
    gc21.PILOT_HASHES = dict(digests)
    scene, assets = gc21.make_scene(args.inputs_config, args.source_root,
                                     args.gc19_assets_dir, args.gc20_scene_dir)
    require(scene.get('job_count') == 1 and scene.get('front_family') == 'STANDARD'
            and scene.get('inside_image_mode') == 'PORTRAIT'
            and scene.get('sender_variant') == 'HERASYMENKO',
            'SCENE_VARIANT_MISMATCH')
    require(scene.get('source_hashes') == digests, 'SCENE_INPUT_HASH_MISMATCH')
    jsx = gc21.render_jsx(scene)
    require(len(scene['layers']) >= 10 and len(assets) >= 10,
            'NATIVE_SCENE_COMPONENTS_MISSING')
    if args.mode == 'prepare':
        destination = gc21.prepare(args.output_name, scene, assets, jsx)
        print('GC24_ARTIFACT_FOLDER=' + str(destination.relative_to(ROOT)))
        print('GDL_GC24_NATIVE=PREPARED_PRIVATE_VISUAL_REVIEW_REQUIRED')
    else:
        print('GDL_GC24_NATIVE=REAL_INPUT_SOURCE_CHECK_PASS_NO_FILES_WRITTEN')
    print('GC24_INPUT_PROVENANCE=SHA256_VERIFIED_GC23_APPROVED')
    print('GC24_FRONT=STANDARD IMAGE=PORTRAIT SIGNATURE=HERASYMENKO')
    print('CUSTOMER_TEXT_PRINTED=false PRODUCTION_READY=false')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=('check', 'prepare'))
    parser.add_argument('--inputs-config', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--gc19-assets-dir', required=True, type=Path)
    parser.add_argument('--gc20-scene-dir', required=True, type=Path)
    parser.add_argument('--output-name')
    parser.add_argument('--confirm-private-prepare', action='store_true')
    parser.add_argument('--confirm-reviewed-real-inputs', action='store_true')
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        # Keep private file paths, input content, and raw exception strings out
        # of CLI output. Only emit an allowlisted machine code or class name.
        reason = str(exc) if isinstance(exc, GC24Blocked) else type(exc).__name__
        if not isinstance(exc, GC24Blocked) and type(exc).__name__ == 'GateError':
            reason = str(exc)
        print('GDL_GC24_NATIVE=BLOCKED reason=' + reason, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
