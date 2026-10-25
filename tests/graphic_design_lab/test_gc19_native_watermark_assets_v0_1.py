"""Synthetic, private-data-free contract tests for GC19 watermark extraction."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
import pymupdf
from PIL import Image

SRC = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards/gc19_native_watermark_assets_v0_1.py'
spec = importlib.util.spec_from_file_location('gc19_native_watermarks', SRC)
gc19 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc19)


def fixture_pdf(tmp_path: Path, pages=(1, 3)):
    doc = pymupdf.open()
    raw = Image.new('RGBA', (9, 7), (80, 150, 210, 128))
    buffer = io.BytesIO()
    raw.save(buffer, 'PNG')
    stream = buffer.getvalue()
    src = tmp_path / 'source.pdf'
    for i in range(4):
        page = doc.new_page(width=214 * 72 / 25.4, height=301 * 72 / 25.4)
        if i in pages:
            page.insert_image(pymupdf.Rect(30, 50, 230, 260), stream=stream,
                              keep_proportion=False)
    doc.save(src)
    doc.close()
    with pymupdf.open(src) as pdf:
        sample = pdf[pages[0]].get_image_info(hashes=True, xrefs=True)
        digest = sample[0]['digest'].hex()
    return src, digest


def test_exact_pages_and_geometry_and_alpha(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path)
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    before = gc19.digest_file(src)
    report, assets = gc19.prepared_assets(src)
    assert report['watermark_count'] == 2
    assert report['source_pdf_sha256'] == before
    assert report['source_pdf_mutated'] is False
    assert [row['physical_page'] for row in report['watermarks']] == [2, 4]
    assert list(assets) == ['p02_back_watermark.png', 'p04_greeting_watermark.png']
    assert [row['bbox_pdf_mm'] for row in report['watermarks']] == [
        [round(30 * gc19.MM_PER_PT, 3), round(50 * gc19.MM_PER_PT, 3),
         round(230 * gc19.MM_PER_PT, 3), round(260 * gc19.MM_PER_PT, 3)]
    ] * 2
    with pymupdf.open(src) as pdf:
        image_record = pdf[1].get_image_info(hashes=True, xrefs=True)[0]
        xref = image_record['xref']
        raw_source = pdf.extract_image(xref)['image']
        with Image.open(io.BytesIO(raw_source)) as original:
            source_rgb = original.convert('RGB').getpixel((0, 0))
    for blob in assets.values():
        with Image.open(io.BytesIO(blob)) as im:
            assert im.mode == 'RGBA'
            assert im.getpixel((0, 0))[:3] == source_rgb  # preserve PDF source RGB exactly
            assert abs(im.getpixel((0, 0))[3] - 32) <= 1  # PDF alpha quantization
    assert gc19.digest_file(src) == before


def test_missing_page4_refused(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path, pages=(1,))
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    with pytest.raises(gc19.GC19Blocked, match='P04_WATERMARK_EXPECTED_1_FOUND_0'):
        gc19.prepared_assets(src)


def test_extra_page1_refused(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path, pages=(0, 1, 3))
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    with pytest.raises(gc19.GC19Blocked, match='P01_WATERMARK_EXPECTED_0_FOUND_1'):
        gc19.prepared_assets(src)


def test_output_write_once(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path)
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    monkeypatch.setattr(gc19, 'ROOT', tmp_path)
    report, assets = gc19.prepared_assets(src)
    d = gc19.export('gc19_synthetic_test', report, assets)
    assert sorted(x.name for x in d.iterdir()) == [
        'manifest.json', 'p02_back_watermark.png', 'p04_greeting_watermark.png'
    ]
    with pytest.raises(gc19.GC19Blocked, match='OUTPUT_EXISTS_NO_OVERWRITE'):
        gc19.export('gc19_synthetic_test', report, assets)
    assert not (tmp_path / 'tmp' / 'anything_else').exists()


def test_no_export_from_inspection(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path)
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    monkeypatch.setattr(gc19, 'ROOT', tmp_path)
    assert gc19.main(['--mode', 'inspect', '--reference-pdf', str(src)]) == 0
    assert not (tmp_path / 'tmp').exists()


def test_no_export_without_explicit_confirmation(tmp_path, monkeypatch):
    src, digest = fixture_pdf(tmp_path)
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    monkeypatch.setattr(gc19, 'ROOT', tmp_path)
    assert gc19.main(['--mode', 'export', '--reference-pdf', str(src), '--output-name', 'gc19_example']) == 2
    assert not (tmp_path / 'tmp').exists()
