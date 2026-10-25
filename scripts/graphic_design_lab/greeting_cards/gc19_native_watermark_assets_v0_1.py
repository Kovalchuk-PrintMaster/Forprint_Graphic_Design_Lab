#!/usr/bin/env python3
"""GC19: derive separate, source-faithful watermarks for native Illustrator pages 2/4.

Source/reference only: never modifies the reference PDF, old PDF Builder, client
workspace, Windows, Git, or an existing output directory. Exports ONLY isolated
watermark pixels with preserved source RGB, source soft mask and attenuated alpha.
Not a complete Illustrator builder; native layout and visual approval are pending.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import sys

WATERMARK_MD5 = "216f5696fab35f44f4b18c8efe82cefa"
RESOURCE_ID = "template.greeting_card.dolinska.v1"
RESOURCE_MANIFEST_SCHEMA = "gdl_greeting_card_private_resource_manifest_v0_1"
ALPHA_FACTOR = 0.25  # source-alpha multiplier, not absolute visual opacity
MM_PER_PT = 25.4 / 72.0
EXPECTED_PAGES = {1: "P02_BACK", 3: "P04_GREETING"}  # zero-based PDF indices
FILENAMES = {1: "p02_back_watermark.png", 3: "p04_greeting_watermark.png"}
ROOT = Path(__file__).resolve().parents[3]
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{3,63}$")


class GC19Blocked(ValueError):
    pass


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda: f.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def resolve_reference(args: argparse.Namespace) -> Path:
    if args.reference_pdf is not None:
        src = args.reference_pdf
    else:
        import yaml
        mf = args.resource_manifest
        if not mf.is_file() or mf.is_symlink():
            raise GC19Blocked('PRIVATE_RESOURCE_MANIFEST_INVALID')
        config = yaml.safe_load(mf.read_text('utf8'))
        if not isinstance(config, dict) or config.get('schema_version') != RESOURCE_MANIFEST_SCHEMA:
            raise GC19Blocked('PRIVATE_RESOURCE_SCHEMA_INVALID')
        resources = config.get('resources')
        binding = resources.get(RESOURCE_ID) if isinstance(resources, dict) else None
        if not isinstance(binding, dict) or not isinstance(binding.get('path'), str):
            raise GC19Blocked('REFERENCE_PDF_BINDING_MISSING')
        src = Path(binding['path'])
        if not src.is_absolute():
            raise GC19Blocked('REFERENCE_PATH_NOT_ABSOLUTE')
        expected_hash = binding.get('sha256')
        if expected_hash is not None and (not isinstance(expected_hash, str) or
                                          not re.fullmatch(r'[0-9a-f]{64}', expected_hash)):
            raise GC19Blocked('REFERENCE_SHA256_FORMAT_INVALID')
    if not src.is_absolute() or not src.is_file() or src.is_symlink():
        raise GC19Blocked('REFERENCE_PDF_UNAVAILABLE')
    if src.suffix.lower() != '.pdf':
        raise GC19Blocked('REFERENCE_NOT_PDF')
    if args.resource_manifest is not None and expected_hash is not None:
        if digest_file(src) != expected_hash:
            raise GC19Blocked('REFERENCE_SHA256_MISMATCH')
    return src


def prepared_assets(source: Path) -> tuple[dict, dict[str, bytes]]:
    import pymupdf
    from PIL import Image, ImageChops

    assets: dict[str, bytes] = {}
    sections: list[dict] = []
    with pymupdf.open(source) as doc:
        if doc.page_count != 4:
            raise GC19Blocked('EXPECTED_FOUR_PAGE_REFERENCE')
        for i, page in enumerate(doc):
            matched = [v for v in page.get_image_info(hashes=True, xrefs=True)
                       if isinstance(v.get('digest'), bytes) and
                       v['digest'].hex() == WATERMARK_MD5]
            expected = 1 if i in EXPECTED_PAGES else 0
            if len(matched) != expected:
                raise GC19Blocked(f'P{i+1:02d}_WATERMARK_EXPECTED_{expected}_FOUND_{len(matched)}')
            if not matched:
                continue
            item = matched[0]
            xref = int(item.get('xref') or 0)
            if xref <= 0:
                raise GC19Blocked('WATERMARK_NO_REFERENCE_XREF')
            mask = 0
            for row in page.get_images(full=True):
                if int(row[0]) == xref:
                    mask = int(row[1] or 0)
                    break
            if mask <= 0:
                raise GC19Blocked('WATERMARK_SOFT_MASK_MISSING')
            if int(item.get('width', 0)) * int(item.get('height', 0)) > 25_000_000:
                raise GC19Blocked('WATERMARK_PIXELS_TOO_MANY')
            raw_image = doc.extract_image(xref)['image']
            raw_mask = doc.extract_image(mask)['image']
            with Image.open(io.BytesIO(raw_image)) as im, Image.open(io.BytesIO(raw_mask)) as sm:
                rgba = im.convert('RGBA')
                mask_img = sm.convert('L')
            if mask_img.size != rgba.size:
                raise GC19Blocked('MASK_PIXEL_DIMENSIONS_MISMATCH')
            if rgba.width * rgba.height > 25_000_000:
                raise GC19Blocked('WATERMARK_PIXELS_TOO_MANY')
            src_alpha = ImageChops.multiply(rgba.getchannel('A'), mask_img)
            rgba.putalpha(src_alpha.point(lambda x: int(round(x * ALPHA_FACTOR))))
            buf = io.BytesIO()
            rgba.save(buf, 'PNG')
            data = buf.getvalue()
            filename = FILENAMES[i]
            assets[filename] = data
            sections.append({
                'object_id': EXPECTED_PAGES[i] + '.WATERMARK',
                'physical_page': i + 1,
                'filename': filename,
                'bbox_pdf_mm': [round(float(v) * MM_PER_PT, 3) for v in item['bbox']],
                'pixel_size': [rgba.width, rgba.height],
                'alpha_source_multiplier': ALPHA_FACTOR,
                'soft_mask_merged': True,
                'rgba_preserved_except_alpha_attenuation': True,
                'sha256': hashlib.sha256(data).hexdigest(),
            })
    report = {
        'schema_version': 'gdl_gc19_native_watermark_asset_manifest_v0_1',
        'state': 'NATIVE_ASSETS_CANDIDATE_VISUAL_REVIEW_REQUIRED',
        'source_pdf_sha256': digest_file(source),
        'source_pdf_mutated': False,
        'source_text_extracted': False,
        'watermark_count': len(sections),
        'source_alpha_factor': ALPHA_FACTOR,
        'layout_note': 'Use EACH PNG once, in its own editable/replaceable Illustrator layer at bbox_pdf_mm; do not retain the original watermark underneath.',
        'visual_approval': 'NOT_RECORDED',
        'production_ready': False,
        'watermarks': sections,
    }
    return report, assets


def export(out_name: str, report: dict, assets: dict[str, bytes]) -> Path:
    if not NAME_RE.fullmatch(out_name):
        raise GC19Blocked('OUTPUT_NAME_INVALID')
    base = ROOT / 'tmp'
    if base.exists() and (base.is_symlink() or not base.is_dir()):
        raise GC19Blocked('TMP_ROOT_INVALID')
    target = base / out_name
    if target.exists() or target.is_symlink():
        raise GC19Blocked('OUTPUT_EXISTS_NO_OVERWRITE')
    base.mkdir(mode=0o700, exist_ok=True)
    target.mkdir(mode=0o700)
    for name, blob in assets.items():
        with (target / name).open('xb') as f:
            f.write(blob)
    with (target / 'manifest.json').open('x', encoding='utf8') as f:
        json.dump(report, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', required=True, choices=('inspect', 'export'))
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--reference-pdf', type=Path)
    source.add_argument('--resource-manifest', type=Path)
    p.add_argument('--output-name')
    p.add_argument('--confirm-export', action='store_true')
    args = p.parse_args(argv)
    try:
        if (args.mode == 'export') != args.confirm_export:
            raise GC19Blocked('EXPORT_CONFIRMATION_MISMATCH')
        if (args.mode == 'export') != (args.output_name is not None):
            raise GC19Blocked('OUTPUT_ARGUMENT_MISMATCH')
        reference = resolve_reference(args)
        report, assets = prepared_assets(reference)
        if args.mode == 'export':
            dest = export(args.output_name, report, assets)
            print('ARTIFACT_FOLDER=' + str(dest.relative_to(ROOT)))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print('GDL_GC19_NATIVE_WATERMARK_ASSETS=' + ('EXPORTED_REVIEW_REQUIRED' if args.mode == 'export' else 'INSPECT_PASS'))
        return 0
    except (GC19Blocked, OSError, KeyError, ValueError, TypeError) as exc:
        code = str(exc) if isinstance(exc, GC19Blocked) else type(exc).__name__
        print('GDL_GC19_NATIVE_WATERMARK_ASSETS=BLOCKED reason=' + code, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
