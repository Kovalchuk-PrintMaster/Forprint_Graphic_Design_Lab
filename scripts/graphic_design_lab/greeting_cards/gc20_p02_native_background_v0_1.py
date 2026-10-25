#!/usr/bin/env python3
"""GC20 P02: native-layer candidate from SAME locked reference page minus watermark.

Exports a high-resolution locked P02 background + separate source-derived GC19
watermark + composed review PNG for later native Illustrator assembly.
This is NOT yet an AI document or proof of vector parity/production readiness.
Original reference PDF and GC19 artifacts remain untouched; tmp-only writes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys

import gc19_native_watermark_assets_v0_1 as gc19

ROOT = Path(__file__).resolve().parents[3]
GC19_SCHEMA = 'gdl_gc19_native_watermark_asset_manifest_v0_1'
SCHEMA = 'gdl_gc20_native_p02_layer_candidate_v0_1'
NAME_RE = re.compile(r'^[a-z][a-z0-9_-]{3,63}$')
ALLOWED_DPI = {150, 300}
BACK_BBOX = (19.869, 59.717, 194.131, 241.283)
SIZE_MM = (214.0, 301.0)


class GC20Blocked(ValueError):
    pass


def must(condition: bool, reason: str) -> None:
    if not condition:
        raise GC20Blocked(reason)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def inputs(reference_manifest: Path, gc19_dir: Path) -> tuple[Path, Path, dict, dict]:
    import pymupdf
    import yaml

    must(_regular(reference_manifest), 'PRIVATE_RESOURCE_MANIFEST_MISSING')
    conf = yaml.safe_load(reference_manifest.read_text('utf-8'))
    must(isinstance(conf, dict) and
         conf.get('schema_version') == gc19.RESOURCE_MANIFEST_SCHEMA,
         'RESOURCE_SCHEMA_INVALID')
    binding = conf.get('resources', {}).get(gc19.RESOURCE_ID)
    must(isinstance(binding, dict), 'REFERENCE_BINDING_MISSING')
    raw = binding.get('path')
    must(isinstance(raw, str) and Path(raw).is_absolute(), 'REFERENCE_PATH_INVALID')
    pdf = Path(raw)
    must(_regular(pdf) and pdf.suffix.lower() == '.pdf', 'REFERENCE_PDF_NOT_REGULAR')
    pdf_digest = gc19.digest_file(pdf)
    # This private manifest may omit an explicit SHA. GC19's verified export
    # manifest independently binds the exact reference PDF by SHA256 below.
    # If the resource manifest DOES supply SHA, keep the original strict pin.
    pinned_sha = binding.get('sha256')
    if pinned_sha is not None:
        must(isinstance(pinned_sha, str) and
             re.fullmatch(r'[0-9a-f]{64}', pinned_sha) is not None and
             pinned_sha == pdf_digest, 'REFERENCE_SHA_MISMATCH')

    must(not gc19_dir.is_symlink() and gc19_dir.is_dir(), 'GC19_DIR_INVALID')
    must(gc19_dir.resolve().is_relative_to((ROOT / 'tmp').resolve()), 'GC19_OUTSIDE_LAB_TMP')
    manifest_file = gc19_dir / 'manifest.json'
    png_file = gc19_dir / 'p02_back_watermark.png'
    must(_regular(manifest_file) and _regular(png_file), 'GC19_FILES_MISSING')
    doc = json.loads(manifest_file.read_text('utf-8'))
    must(isinstance(doc, dict) and doc.get('schema_version') == GC19_SCHEMA
         and doc.get('source_pdf_sha256') == pdf_digest
         and doc.get('source_alpha_factor') == .25
         and doc.get('watermark_count') == 2
         and doc.get('source_pdf_mutated') is False
         and doc.get('production_ready') is False, 'GC19_EVIDENCE_MISMATCH')
    entries = doc.get('watermarks')
    must(isinstance(entries, list) and len(entries) == 2, 'GC19_WATERMARK_COUNT')
    entry = next((e for e in entries if isinstance(e, dict) and e.get('physical_page') == 2), None)
    must(isinstance(entry, dict) and entry.get('object_id') == 'P02_BACK.WATERMARK'
         and entry.get('filename') == png_file.name
         and entry.get('soft_mask_merged') is True
         and entry.get('alpha_source_multiplier') == .25
         and len(entry.get('bbox_pdf_mm', [])) == 4
         and all(abs(float(a) - b) < .12 for a, b in zip(entry['bbox_pdf_mm'], BACK_BBOX)),
         'GC19_P02_BINDING_INVALID')
    blob = png_file.read_bytes()
    must(digest(blob) == entry.get('sha256'), 'GC19_IMAGE_CHANGED')
    with pymupdf.open(stream=pdf.read_bytes(), filetype='pdf') as ref:
        must(ref.page_count == 4, 'CANONICAL_PAGE_COUNT')
        must(abs(ref[1].rect.width * gc19.MM_PER_PT - SIZE_MM[0]) < .03
             and abs(ref[1].rect.height * gc19.MM_PER_PT - SIZE_MM[1]) < .03,
             'CANONICAL_P02_SIZE')
        for index, page in enumerate(ref):
            found = [x for x in page.get_image_info(hashes=True, xrefs=True)
                     if isinstance(x.get('digest'), bytes) and
                     x['digest'].hex() == gc19.WATERMARK_MD5]
            must(len(found) == (1 if index in (1, 3) else 0),
                 'CANONICAL_WATERMARK_MAP_P' + str(index + 1))
            if index == 1:
                e = found[0]
                must(int(e.get('xref') or 0) > 0, 'P02_XREF_REQUIRED')
                must(all(abs(float(a) * gc19.MM_PER_PT - b) < .12
                         for a, b in zip(e['bbox'], entry['bbox_pdf_mm'])),
                     'P02_WATERMARK_GEOMETRY_CHANGED')
    return pdf, png_file, doc, entry


def make_layers(pdf: Path, watermark: Path, entry: dict, dpi: int) -> dict[str, bytes]:
    import pymupdf
    from PIL import Image

    must(dpi in ALLOWED_DPI, 'DPI_NOT_SUPPORTED')
    with pymupdf.open(stream=pdf.read_bytes(), filetype='pdf') as copy:
        p02 = copy[1]
        found = [x for x in p02.get_image_info(hashes=True, xrefs=True)
                 if isinstance(x.get('digest'), bytes) and
                 x['digest'].hex() == gc19.WATERMARK_MD5]
        must(len(found) == 1, 'P02_TARGET_NOT_UNIQUE')
        p02.delete_image(int(found[0]['xref']))  # in-memory PDF copy ONLY
        remaining = [x for x in p02.get_image_info(hashes=True, xrefs=True)
                     if isinstance(x.get('digest'), bytes) and
                     x['digest'].hex() == gc19.WATERMARK_MD5]
        must(len(remaining) == 0, 'P02_WATERMARK_STILL_PRESENT')
        pix = p02.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
        locked = pix.tobytes(output='png')

    from PIL import Image as PILImage
    with PILImage.open(io.BytesIO(locked)) as im:
        base = im.convert('RGBA')
    with PILImage.open(watermark) as im:
        wm = im.convert('RGBA')
    l, t, r, b = [float(x) for x in entry['bbox_pdf_mm']]
    w, h = base.size
    x0 = round(l / SIZE_MM[0] * w)
    y0 = round(t / SIZE_MM[1] * h)
    x1 = round(r / SIZE_MM[0] * w)
    y1 = round(b / SIZE_MM[1] * h)
    must(x1 > x0 and y1 > y0 and x0 >= 0 and y0 >= 0 and x1 <= w and y1 <= h,
         'WATERMARK_RENDER_BOUNDS')
    overlay = PILImage.new('RGBA', base.size, (0, 0, 0, 0))
    overlay.paste(wm.resize((x1-x0, y1-y0), PILImage.Resampling.LANCZOS), (x0, y0))
    review = PILImage.alpha_composite(base, overlay).convert('RGB')
    buf = io.BytesIO()
    review.save(buf, format='PNG', optimize=True)
    return {'p02_locked_background.png': locked,
            'p02_watermark_layer.png': watermark.read_bytes(),
            'p02_review.png': buf.getvalue()}


def write(out_name: str, pdf: Path, source_entry: dict, dpi: int,
          assets: dict[str, bytes], source_gc19_manifest: dict) -> Path:
    must(NAME_RE.fullmatch(out_name) is not None, 'OUTPUT_NAME_INVALID')
    dest = ROOT / 'tmp' / out_name
    must(not dest.exists() and not dest.is_symlink(), 'OUTPUT_EXISTS_NO_OVERWRITE')
    must(not (ROOT / 'tmp').is_symlink(), 'TMP_SYMLINK_FORBIDDEN')
    (ROOT / 'tmp').mkdir(mode=0o700, exist_ok=True)
    dest.mkdir(mode=0o700)
    details = {
        'schema_version': SCHEMA,
        'state': 'P02_NATIVE_LAYER_ASSETS_VISUAL_REVIEW_REQUIRED',
        'source_reference_pdf_sha256': gc19.digest_file(pdf),
        'source_gc19_manifest_pdf_sha256': source_gc19_manifest['source_pdf_sha256'],
        'source_pdf_mutated': False, 'windows_executed': False,
        'production_ready': False, 'native_ai_created': False,
        'physical_page': 2, 'role': 'P02_BACK',
        'artboard_mm': list(SIZE_MM), 'render_dpi': dpi,
        'watermark_object_id': source_entry['object_id'],
        'watermark_bbox_pdf_mm': source_entry['bbox_pdf_mm'],
        'watermark_source_alpha_multiplier': .25,
        'composition': [
            {'filename': 'p02_locked_background.png', 'layer': 'P02.LOCKED_BASE',
             'bbox_pdf_mm': [0, 0, *SIZE_MM], 'locked': True,
             'note': 'Rasterized copy of exact reference P02 with its original watermark removed'},
            {'filename': 'p02_watermark_layer.png', 'layer': 'P02.WATERMARK',
             'bbox_pdf_mm': source_entry['bbox_pdf_mm'], 'locked': False,
             'note': 'Place only once, never over original watermark'},
        ],
        'preview_filename': 'p02_review.png',
        'preview_is_print_proof': False,
        'vector_fidelity': 'NOT_PROVEN_LOCKED_RASTER_BASE_CANDIDATE',
        'artifacts_sha256': {name: digest(blob) for name, blob in assets.items()},
    }
    for filename, blob in assets.items():
        with (dest / filename).open('xb') as stream:
            stream.write(blob)
    with (dest / 'scene_p02.json').open('x', encoding='utf8') as stream:
        json.dump(details, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('check', 'export'), required=True)
    p.add_argument('--resource-manifest', type=Path, required=True)
    p.add_argument('--gc19-assets-dir', type=Path, required=True)
    p.add_argument('--output-name')
    p.add_argument('--dpi', type=int, default=300)
    p.add_argument('--confirm-export', action='store_true')
    args = p.parse_args(argv)
    try:
        must(args.dpi in ALLOWED_DPI, 'DPI_NOT_SUPPORTED')
        must((args.mode == 'export') == args.confirm_export, 'CONFIRMATION_MISMATCH')
        must((args.mode == 'export') == (args.output_name is not None), 'OUTPUT_ARGUMENT_MISMATCH')
        pdf, wm, manifest, entry = inputs(args.resource_manifest, args.gc19_assets_dir)
        if args.mode == 'check':
            print('GDL_GC20_P02_NATIVE_BACKGROUND=CHECK_PASS')
            print('PDF_MUTATION=false WINDOWS_EXECUTION=false')
            return 0
        blobs = make_layers(pdf, wm, entry, args.dpi)
        dest = write(args.output_name, pdf, entry, args.dpi, blobs, manifest)
        print('ARTIFACT_FOLDER=' + str(dest.relative_to(ROOT)))
        print('GDL_GC20_P02_NATIVE_BACKGROUND=EXPORTED_VISUAL_REVIEW_REQUIRED')
        return 0
    except (GC20Blocked, gc19.GC19Blocked, KeyError, OSError, ValueError,
            TypeError, ImportError) as exc:
        label = str(exc) if isinstance(exc, (GC20Blocked, gc19.GC19Blocked)) else type(exc).__name__
        print('GDL_GC20_P02_NATIVE_BACKGROUND=BLOCKED reason=' + label, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
