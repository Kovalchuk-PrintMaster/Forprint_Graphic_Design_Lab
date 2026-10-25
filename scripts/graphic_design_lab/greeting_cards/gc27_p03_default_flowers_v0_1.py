#!/usr/bin/env python3
"""GC27: source-verified P03 DEFAULT_ASSET native Illustrator *proof*, not a four-page render.

Uses only GDL-owned GC21/GC23/GC25 contracts. Does not import Prepress Hub.
No client writes; private images and generated JSX reside under GDL/tmp only.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
from hashlib import sha256
from pathlib import Path
import re
import sys
import zipfile
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / 'gc27_p03_default_flowers_proof_v0_1.jsx'
# Role-specific safety ceilings for exact SHA256-pinned, server-only resources.
# These are bounded safety ceilings, NOT grounds for accepting different bytes.
MAX_REFERENCE_PDF_BYTES = 512 * 1024 * 1024
MAX_DEFAULT_FLOWERS_BYTES = 128 * 1024 * 1024
MAX_DEFAULT_FLOWERS_PIXELS = 70_000_000
PRIVATE_RESOURCE_LIMITS = {
    'reference_pdf': MAX_REFERENCE_PDF_BYTES,
    'default_flowers': MAX_DEFAULT_FLOWERS_BYTES,
}
# A canonical PDF may place the portrait partly outside its 214x301-mm
# artboard for intended cropping. Preserve its exact SOURCE bbox, never clamp.
# A bounded intersection and finite coordinate gate still reject bad geometry.
P03_ARTBOARD_MM = (214.0, 301.0)
P03_MAX_SOURCE_SCALE = 4.0
P03_MIN_VISIBLE_ARTBOARD_FRACTION = 0.10
P03_FIXED_LAYER_BLEED_TOLERANCE_MM = 5.0
NAME_RE = re.compile(r'^gc27_[a-z0-9][a-z0-9_-]{3,56}$')
ZIP_RE = re.compile(r'^[A-Za-z0-9_.-]{3,128}\.zip$')

class Blocked(ValueError):
    pass


def require(test: Any, reason: str) -> None:
    if not test:
        raise Blocked(reason)


def load_module(path: Path, name: str) -> Any:
    require(path.is_file() and not path.is_symlink(), 'GDL_DEPENDENCY_NOT_FOUND')
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, 'GDL_DEPENDENCY_INVALID')
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def dependencies() -> tuple[Any, Any, Any, Any]:
    names = ('gc21_native_illustrator_builder_v0_1.py',
             'gc23_prepress_variant_contract_v0_1.py',
             'gc25_illustrator_smb_preflight_v0_1.py',
             'gc26_illustrator_client_launcher_deploy_v0_1.py')
    return tuple(load_module(HERE / p, 'gc27_' + str(i)) for i, p in enumerate(names))


def file_sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def pin_private_file(value: Any, expected: str, source_root: Path | None = None,
                     *, kind: str) -> Path:
    require(isinstance(value, str) and bool(value.strip()), 'PRIVATE_RESOURCE_PATH_MISSING')
    p = Path(value)
    if not p.is_absolute():
        require(source_root is not None and source_root.is_dir() and not source_root.is_symlink(),
                'RELATIVE_RESOURCE_SOURCE_ROOT_REQUIRED')
        p = source_root / p
    require(p.is_file() and not p.is_symlink(), 'PRIVATE_RESOURCE_FILE_UNAVAILABLE')
    require(kind in PRIVATE_RESOURCE_LIMITS, 'PRIVATE_RESOURCE_KIND_UNSUPPORTED')
    size = p.stat().st_size
    require(size > 0, 'PRIVATE_RESOURCE_EMPTY')
    require(size <= PRIVATE_RESOURCE_LIMITS[kind],
            'PRIVATE_REFERENCE_PDF_TOO_LARGE' if kind == 'reference_pdf'
            else 'PRIVATE_FLOWERS_IMAGE_TOO_LARGE')
    # Streaming digest remains mandatory even when size is within the new bound.
    require(file_sha(p) == expected, 'PRIVATE_RESOURCE_SHA_MISMATCH')
    return p


def resource_paths(resource_manifest: Path, snap: dict[str, Any], gc23: Any,
                   source_root: Path | None = None) -> tuple[Path, Path]:
    require(resource_manifest.is_file() and not resource_manifest.is_symlink(), 'RESOURCE_MANIFEST_MISSING')
    resources = gc23.load_mapping(resource_manifest)
    require(resources.get('schema_version') == 'gdl_greeting_card_private_resource_manifest_v0_1',
            'RESOURCE_MANIFEST_SCHEMA')
    mapping = resources.get('resources') or {}
    require(isinstance(mapping, dict), 'RESOURCES_NOT_MAPPING')
    ref_id = snap['resource_ids']['reference_pdf']
    flowers_id = snap['resource_ids']['flowers']
    def get(item: str, expected: str, kind: str) -> Path:
        binding = mapping.get(item) or {}
        require(isinstance(binding, dict), 'RESOURCE_BINDING_NOT_MAPPING')
        require(binding.get('sha256', expected) == expected, 'RESOURCE_BINDING_SHA_MISMATCH')
        return pin_private_file(binding.get('path'), expected, source_root, kind=kind)
    ref = get(ref_id, snap['pinned_sha256']['reference_pdf'], 'reference_pdf')
    flowers = get(flowers_id, snap['photo_variants']['DEFAULT_ASSET']['sha256'], 'default_flowers')
    return ref, flowers


def client_handoff(client_name: str, package_name: str, gc26: Any) -> Path:
    require(bool(ZIP_RE.fullmatch(package_name)), 'PACKAGE_NAME_INVALID')
    root = gc26.client_workspace(client_name)
    file = root / 'input' / package_name
    require(file.is_file() and not file.is_symlink(), 'PACKAGE_NOT_REGULAR')
    return file


def verify_handoff(path: Path, snap: dict[str, Any], gc25: Any) -> dict[str, Any]:
    result = gc25.inspect_archive(path, snap)
    require(result['kind'] == 'ACCEPTED_HANDOFF' and result['jobs'] > 0,
            'ACCEPTED_HANDOFF_REQUIRED')
    require(len(result['variants']) == result['jobs'], 'JOB_VARIANTS_INVALID')
    require(all(job['image'] == 'DEFAULT_ASSET' for job in result['variants']),
            'P03_FLOWERS_ONLY_BOUNDED_PROOF')
    require(result['status'] == 'NATIVE_EXECUTOR_NOT_READY', 'HANDOFF_STATUS_MISMATCH')
    return result


def validate_p03_layer_bbox(bbox: Any, role: str) -> list[float]:
    """Reject invalid placement, but permit source-pinned image overscan.

    The visible PDF/Illustrator artboard is fixed. Extending beyond it is not a
    license to alter source dimensions or translate coordinates; the artwork
    must substantially overlap the physical page, and extreme scale is refused.
    """
    import math
    require(isinstance(bbox, (list, tuple)) and len(bbox) == 4,
            'P03_CANONICAL_BBOX_INVALID')
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) for v in bbox), 'P03_CANONICAL_BBOX_INVALID')
    x0, y0, x1, y1 = map(float, bbox)
    width, height = P03_ARTBOARD_MM
    require(x1 > x0 and y1 > y0, 'P03_CANONICAL_BBOX_INVALID')
    if role == 'P03.DEFAULT_FLOWERS':
        require(x1-x0 <= width*P03_MAX_SOURCE_SCALE and
                y1-y0 <= height*P03_MAX_SOURCE_SCALE,
                'P03_SOURCE_OVERSCAN_TOO_LARGE')
        visible_w = max(0.0, min(x1, width) - max(x0, 0.0))
        visible_h = max(0.0, min(y1, height) - max(y0, 0.0))
        require(visible_w*visible_h >= width*height*P03_MIN_VISIBLE_ARTBOARD_FRACTION,
                'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL')
    elif role in ('P03.PAPER', 'P03.FRAME'):
        bleed = P03_FIXED_LAYER_BLEED_TOLERANCE_MM
        require(-bleed <= x0 < x1 <= width+bleed and
                -bleed <= y0 < y1 <= height+bleed,
                'P03_FIXED_LAYER_BBOX_INVALID')
    else:
        require(False, 'P03_UNKNOWN_LAYER_ROLE')
    return [float(v) for v in bbox]


def normalize_accepted_flowers(source_path: Path, target_size: tuple[int, int]) -> bytes:
    """Reproduce PDF Builder normalize_portrait_bytes for SHA-pinned flowers.

    Preserve RGBA supplied by accepted resource. Do NOT import legacy portrait
    PDF smask; a replaced image must not inherit an unrelated silhouette.
    """
    from PIL import Image
    width, height = target_size
    require(width > 0 and height > 0, 'P03_NORMALIZE_TARGET_INVALID')
    with Image.open(source_path) as source:
        require(source.width > 50 and source.height > 50,
                'P03_FLOWERS_IMAGE_TOO_SMALL')
        require(source.width * source.height <= MAX_DEFAULT_FLOWERS_PIXELS,
                'P03_FLOWERS_IMAGE_PIXEL_LIMIT')
        image = source.convert('RGBA')
    source_ratio = image.width / image.height
    target_ratio = width / height
    if source_ratio > target_ratio:
        crop_width = round(image.height * target_ratio)
        left = (image.width - crop_width) // 2
        box = (left, 0, left + crop_width, image.height)
    else:
        crop_height = round(image.width / target_ratio)
        top = (image.height - crop_height) // 2
        box = (0, top, image.width, top + crop_height)
    image = image.crop(box).resize((width, height), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=False)
    return output.getvalue()


def compose_p03(reference: Path, flowers: Path, gc21: Any) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Use source-pinned P03 bbox and normalized accepted-asset alpha only.

    The legacy portrait source mask is verified but NOT composited with flowers.
    Full visual/pixel parity remains subject to independent Illustrator review.
    """
    import pymupdf
    from PIL import Image

    require(file_sha(reference) == gc21.REFERENCE_SHA, 'GC21_REFERENCE_SHA_MISMATCH')
    require(reference != flowers, 'FLOWERS_REFERENCE_IDENTITY_CONFLICT')
    with pymupdf.open(reference) as doc:
        require(doc.page_count == 4, 'CANONICAL_REFERENCE_FOUR_PAGES_REQUIRED')
        page = doc[2]
        require(all(abs(float(n) * gc21.MM - size) < 0.03
                    for n, size in zip((page.rect.width, page.rect.height), gc21.SIZE)),
                'P03_PAGE_GEOMETRY_CHANGED')
        chosen = gc21.image_match(page, gc21.HASHES['portrait_reference'])
        reference_bbox = gc21.bbox_mm(chosen)
        # The pinned canonical PDF can intentionally overscan the artboard.
        # Retain its exact bbox; Illustrator exports only the artboard region.
        reference_bbox = validate_p03_layer_bbox(reference_bbox, 'P03.DEFAULT_FLOWERS')
        mask_xref = next((int(entry[1] or 0) for entry in page.get_images(full=True)
                          if int(entry[0]) == int(chosen['xref'])), 0)
        require(mask_xref > 0, 'P03_REFERENCE_SOFT_MASK_MISSING')
        # Reference portrait smask is provenance only. The Prepress PDF Builder
        # REPLACES that portrait with normalized accepted flowers. Re-applying
        # the OLD portrait's silhouette to flowers breaks approved P03 parity.
        # Keep the source mask identity/dimension audit but never multiply it.
        with Image.open(io.BytesIO(doc.extract_image(mask_xref)['image'])) as img:
            reference_portrait_mask = img.convert('L')
        target_size = (int(chosen['width']), int(chosen['height']))
        require(reference_portrait_mask.size == target_size and min(target_size) > 100,
                'P03_REFERENCE_MASK_PIXEL_SIZE_CHANGED')
        require(reference_portrait_mask.getextrema() != (0, 0), 'P03_REFERENCE_MASK_EMPTY')
        normalized_flowers = normalize_accepted_flowers(flowers, target_size)
        images = {}
        layers = []
        def add(role: str, filename: str, payload: bytes, bbox: list[float], locked: bool = False) -> None:
            require(filename not in images, 'DUPLICATE_P03_LAYER_ASSET')
            images[filename] = payload
            checked_bbox = validate_p03_layer_bbox(bbox, role)
            layers.append({'role': role, 'page': 3, 'kind': 'raster',
                           'file': 'assets/' + filename, 'bbox_mm': checked_bbox, 'locked': locked})
        for kind, locked in [('paper', True), ('frame', False)]:
            item = gc21.image_match(page, gc21.HASHES[kind])
            blob, _ = gc21.png_rgba_from_xref(doc, page, item)
            if kind == 'paper':
                add('P03.PAPER', 'p03_source_paper.png', blob, gc21.bbox_mm(item), locked)
            else:
                frame = (blob, gc21.bbox_mm(item), locked)
        add('P03.DEFAULT_FLOWERS', 'p03_default_flowers_normalized.png', normalized_flowers, reference_bbox)
        add('P03.FRAME', 'p03_source_frame.png', *frame)
    scene = {
        'schema_version': 'gdl_gc27_p03_default_flowers_scene_v0_1',
        'state': 'PRIVATE_SOURCE_PINNED_P03_PROOF_NOT_EXECUTED',
        'page': 3, 'artboard_mm': [214, 301], 'trim_mm': [210, 297], 'bleed_mm': 2,
        'source_reference_sha256': file_sha(reference),
        'default_flowers_sha256': file_sha(flowers),
        'reference_mask_present': True,
        'reference_mask_applied_to_flowers': False,
        'flowers_alpha_origin': 'ACCEPTED_RESOURCE_RGBA_ONLY',
        'source_mask_dimensions': list(target_size),
        'source_placement_bbox_pdf_mm': reference_bbox,
        'layers': layers,
        'illustrator_executed': False, 'native_full_card_supported': False,
        'pdf_builder_pixel_parity_verified': False, 'production_ready': False,
        'visual_approval': 'NOT_RECORDED',
        'required_manual_checks': ['P03 accepted-asset alpha and crop (not source portrait mask)', 'source-vs-native pixel review',
                                   'layer editability', 'AI reopen proof', 'CMYK deferred'],
    }
    return scene, images


def render_jsx(scene: dict[str, Any]) -> str:
    require(TEMPLATE.is_file() and not TEMPLATE.is_symlink(), 'GC27_TEMPLATE_MISSING')
    contents = TEMPLATE.read_text(encoding='utf8')
    marker = '/*__GC27_PRIVATE_SCENE_JSON__*/'
    require(contents.count(marker) == 1 and
            contents.count('GC27_P03_DEFAULT_FLOWERS_NATIVE_PROOF_V0_1') == 1,
            'GC27_TEMPLATE_INVALID')
    return contents.replace(marker, json.dumps(scene, ensure_ascii=True, sort_keys=True, separators=(',', ':')))


def store_private(name: str, scene: dict[str, Any], assets: dict[str, bytes], jsx: str) -> Path:
    require(bool(NAME_RE.fullmatch(name)), 'OUTPUT_NAME_INVALID')
    tmp = ROOT / 'tmp'
    require(tmp.is_dir() and not tmp.is_symlink(), 'PRIVATE_TMP_DIRECTORY_REQUIRED')
    dest = tmp / name
    require(not dest.exists() and not dest.is_symlink(), 'OUTPUT_ALREADY_EXISTS')
    dest.mkdir(mode=0o700)
    try:
        asset_dir = dest / 'assets'
        asset_dir.mkdir(mode=0o700)
        for filename, raw in sorted(assets.items()):
            require(re.fullmatch(r'p03_[a-z0-9_]+\.png', filename), 'ASSET_FILENAME_INVALID')
            (asset_dir / filename).write_bytes(raw)
        (dest / 'run_gc27_p03_in_illustrator.jsx').write_text(jsx, encoding='utf8')
        record = dict(scene)
        record['asset_sha256'] = {k: sha256(v).hexdigest() for k, v in sorted(assets.items())}
        record['jsx_sha256'] = sha256(jsx.encode('utf8')).hexdigest()
        (dest / 'scene_manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2,
                                                             sort_keys=True) + '\n', encoding='utf8')
        (dest / 'README_PRIVATE.txt').write_text(
            'GC27 P03 source-verified one-page Illustrator proof, PRIVATE.\n'
            'Copy this entire folder to Windows Illustrator; execute run_gc27_p03_in_illustrator.jsx.\n'
            'Review out/p03_proof.ai, p03_proof.pdf, preview_p03.png, result.json.\n'
            'Do not publish, print, or push images/JSX/PDF/AI to Git.\n', encoding='utf8')
    except BaseException:
        # Keep partially written private evidence for operator inspection; no cleanup.
        raise
    return dest


def run(a: argparse.Namespace, *, deps: tuple[Any, Any, Any, Any] | None = None) -> int:
    require(a.mode == 'check' or a.mode == 'prepare', 'MODE_UNSUPPORTED')
    require((a.mode == 'prepare') == bool(a.confirm_private_prepare), 'PREPARE_CONFIRMATION_REQUIRED')
    require((a.mode == 'prepare') == bool(a.output_name), 'OUTPUT_NAME_MODE_MISMATCH')
    gc21, gc23, gc25, gc26 = deps or dependencies()
    snap = gc23.catalog()
    path = client_handoff(a.client_name, a.package_name, gc26)
    check = verify_handoff(path, snap, gc25)
    ref, flowers = resource_paths(a.resource_manifest, snap, gc23, a.source_root)
    scene, assets = compose_p03(ref, flowers, gc21)
    require(len(assets) == 3 and len(scene['layers']) == 3, 'P03_NATIVE_LAYER_INVENTORY')
    jsx = render_jsx(scene)
    if a.mode == 'prepare':
        out = store_private(a.output_name, scene, assets, jsx)
        print('GC27_PRIVATE_RESULT=' + str(out.relative_to(ROOT)))
        print('GDL_GC27_P03=PREPARED_ILLUSTRATOR_NOT_EXECUTED')
    else:
        print('GDL_GC27_P03=SOURCE_CHECK_PASS_NO_FILES_WRITTEN')
    print('GC27_ACCEPTED_JOBS=' + str(check['jobs']))
    print('GC27_NATIVE_LAYERS=3')
    print('GC27_REFERENCE_MASK=VERIFIED_NOT_APPLIED_TO_FLOWERS')
    print('GC27_CLIENT_CONTENT_LOGGED=false PRODUCTION_READY=false')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('check', 'prepare'), required=True)
    p.add_argument('--client-name', required=True)
    p.add_argument('--package-name', required=True)
    p.add_argument('--resource-manifest', type=Path, required=True)
    p.add_argument('--source-root', type=Path, default=None, help='Explicit root for relative private resource paths')
    p.add_argument('--output-name')
    p.add_argument('--confirm-private-prepare', action='store_true')
    a = p.parse_args()
    try:
        return run(a)
    except Exception as exc:
        if isinstance(exc, Blocked):
            reason = str(exc)
        elif isinstance(exc, zipfile.BadZipFile):
            reason = 'ARCHIVE_NOT_VALID_ZIP'
        else:
            reason = type(exc).__name__
        print('GDL_GC27_P03=BLOCKED reason=' + reason, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
