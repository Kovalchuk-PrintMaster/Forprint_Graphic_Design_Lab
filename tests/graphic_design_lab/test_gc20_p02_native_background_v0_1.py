from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys

import pytest
import pymupdf
from PIL import Image, ImageDraw
import yaml

D = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards'
sys.path.insert(0, str(D))
import gc19_native_watermark_assets_v0_1 as gc19
import gc20_p02_native_background_v0_1 as gc20


@pytest.fixture
def fixed(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    (repo / 'tmp').mkdir(parents=True)
    monkeypatch.setattr(gc20, 'ROOT', repo)
    wm = Image.new('RGBA', (120, 150), (10, 100, 120, 0))
    draw = ImageDraw.Draw(wm)
    draw.ellipse((7, 9, 110, 140), fill=(90, 125, 178, 200))
    data = io.BytesIO(); wm.save(data, format='PNG')
    doc = pymupdf.open()
    for i in range(4):
        p = doc.new_page(width=214 / 25.4 * 72, height=301 / 25.4 * 72)
        p.draw_rect(p.rect, fill=(0.97, 0.93, 0.82), color=None)
        p.draw_line(p.rect.tl + (20, 20), p.rect.br - (20, 20), color=(0.5, 0.4, 0.2), width=1.2)
        if i in (1, 3):
            coords = (gc20.BACK_BBOX if i == 1 else (19.869, 56.405, 194.131, 237.97))
            x0,y0,x1,y1 = (x * 72 / 25.4 for x in coords)
            p.insert_image(pymupdf.Rect(x0,y0,x1,y1), stream=data.getvalue(), keep_proportion=False)
    pdf = tmp_path / 'reference.pdf'
    pdf.write_bytes(doc.tobytes())
    with pymupdf.open(pdf) as reader:
        digest = reader[1].get_image_info(hashes=True, xrefs=True)[0]['digest'].hex()
    monkeypatch.setattr(gc19, 'WATERMARK_MD5', digest)
    pdfhash = gc19.digest_file(pdf)
    mf = tmp_path / 'resources.yaml'
    mf.write_text(yaml.safe_dump({'schema_version': gc19.RESOURCE_MANIFEST_SCHEMA,
       'resources': {gc19.RESOURCE_ID: {'path': str(pdf), 'sha256': pdfhash}}}))
    report, assets = gc19.prepared_assets(pdf)
    gc19dir = repo / 'tmp' / 'gc19_existing'
    gc19dir.mkdir()
    for name, b in assets.items():
        (gc19dir / name).write_bytes(b)
    (gc19dir/'manifest.json').write_text(json.dumps(report))
    return repo, pdf, mf, gc19dir


def test_inputs_and_source_untouched(fixed):
    _, pdf, mf, folder = fixed
    before = pdf.read_bytes()
    src, watermark, report, entry = gc20.inputs(mf, folder)
    assert src == pdf and watermark.name == 'p02_back_watermark.png'
    assert report['watermark_count'] == 2
    assert entry['physical_page'] == 2
    assert pdf.read_bytes() == before


def test_create_exact_two_layers_and_review(fixed):
    _, pdf, mf, folder = fixed
    before = pdf.read_bytes()
    _, wm, r, entry = gc20.inputs(mf, folder)
    blobs = gc20.make_layers(pdf, wm, entry, 150)
    assert set(blobs) == {'p02_locked_background.png', 'p02_watermark_layer.png', 'p02_review.png'}
    assert blobs['p02_watermark_layer.png'] == wm.read_bytes()
    with Image.open(io.BytesIO(blobs['p02_locked_background.png'])) as base, Image.open(io.BytesIO(blobs['p02_review.png'])) as rev:
        assert base.size == rev.size
        assert base.mode == rev.mode == 'RGB'
        # Watermark must contribute a real, separate visible difference.
        assert base.tobytes() != rev.tobytes()
        assert base.getpixel((0, 0)) == rev.getpixel((0, 0))
    # Compare a pixel inside the old watermark area and one outside against
    # the original reference render, ensuring the locked background really
    # excludes its previous watermark rather than merely layering above it.
    with pymupdf.open(pdf) as ref:
        orig = Image.open(io.BytesIO(ref[1].get_pixmap(dpi=150, alpha=False).tobytes('png'))).convert('RGB')
    with Image.open(io.BytesIO(blobs['p02_locked_background.png'])) as im:
        clean = im.convert('RGB')
    assert orig.getpixel((0, 0)) == clean.getpixel((0, 0))
    center = (round(clean.width * 0.5), round(clean.height * 0.5))
    assert orig.getpixel(center) != clean.getpixel(center)
    assert pdf.read_bytes() == before


def test_private_output_scene_and_no_overwrite(fixed):
    repo, pdf, mf, folder = fixed
    _, wm, report, entry = gc20.inputs(mf, folder)
    blobs = gc20.make_layers(pdf, wm, entry, 150)
    target = gc20.write('gc20_p02_v001', pdf, entry, 150, blobs, report)
    scene = json.loads((target / 'scene_p02.json').read_text())
    assert scene['production_ready'] is False
    assert scene['native_ai_created'] is False
    assert scene['composition'][0]['locked'] is True
    assert scene['composition'][1]['layer'] == 'P02.WATERMARK'
    assert (target / 'p02_review.png').is_file()
    with pytest.raises(gc20.GC20Blocked, match='OUTPUT_EXISTS'):
        gc20.write('gc20_p02_v001', pdf, entry, 150, blobs, report)


def test_gc19_image_must_stay_unchanged(fixed):
    _, _, mf, folder = fixed
    (folder / 'p02_back_watermark.png').write_bytes(b'tampered')
    with pytest.raises(gc20.GC20Blocked, match='GC19_IMAGE_CHANGED'):
        gc20.inputs(mf, folder)


def test_read_only_cli_check_and_guards(fixed, capsys):
    repo, _, mf, folder = fixed
    assert gc20.main(['--mode','check','--resource-manifest',str(mf),
                      '--gc19-assets-dir',str(folder)]) == 0
    assert 'CHECK_PASS' in capsys.readouterr().out
    assert gc20.main(['--mode','export','--resource-manifest',str(mf),
                      '--gc19-assets-dir',str(folder),'--output-name','x123']) == 2
    assert not (repo/'tmp'/'x123').exists()


def test_reject_bad_target_and_wrong_dpi(fixed):
    repo, pdf, mf, folder = fixed
    _, wm, report, entry = gc20.inputs(mf, folder)
    with pytest.raises(gc20.GC20Blocked, match='DPI_NOT_SUPPORTED'):
        gc20.make_layers(pdf,wm,entry,600)
    with pytest.raises(gc20.GC20Blocked, match='OUTPUT_NAME_INVALID'):
        gc20.write('../insecure',pdf,entry,150,{},report)


def test_resource_manifest_optional_sha_still_bound_to_gc19(fixed, capsys):
    _, pdf, mf, folder = fixed
    config = yaml.safe_load(mf.read_text())
    config['resources'][gc19.RESOURCE_ID].pop('sha256')
    mf.write_text(yaml.safe_dump(config))
    found, _, manifest, _ = gc20.inputs(mf, folder)
    assert found == pdf
    assert manifest['source_pdf_sha256'] == gc19.digest_file(pdf)
    assert gc20.main(['--mode','check', '--resource-manifest',str(mf),
                      '--gc19-assets-dir',str(folder)]) == 0
    assert 'CHECK_PASS' in capsys.readouterr().out


def test_resource_manifest_optional_sha_does_not_disable_gc19_binding(fixed):
    _, pdf, mf, folder = fixed
    config = yaml.safe_load(mf.read_text())
    config['resources'][gc19.RESOURCE_ID].pop('sha256')
    mf.write_text(yaml.safe_dump(config))
    pdf.write_bytes(pdf.read_bytes() + b'\n% synthetic source changed\n')
    with pytest.raises(gc20.GC20Blocked, match='GC19_EVIDENCE_MISMATCH'):
        gc20.inputs(mf, folder)


def test_explicit_wrong_manifest_digest_remains_blocked(fixed):
    _, _, mf, folder = fixed
    config = yaml.safe_load(mf.read_text())
    config['resources'][gc19.RESOURCE_ID]['sha256'] = '0' * 64
    mf.write_text(yaml.safe_dump(config))
    with pytest.raises(gc20.GC20Blocked, match='REFERENCE_SHA_MISMATCH'):
        gc20.inputs(mf, folder)
