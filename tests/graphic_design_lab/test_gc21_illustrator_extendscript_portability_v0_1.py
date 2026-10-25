"""GC21: Illustrator ExtendScript compatibility contracts (no Windows required)."""
from pathlib import Path
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
J=ROOT/'scripts/graphic_design_lab/greeting_cards/gc21_four_artboard_native_v0_1.jsx'
GEN=ROOT/'scripts/graphic_design_lab/greeting_cards/gc21_native_illustrator_builder_v0_1.py'
spec=importlib.util.spec_from_file_location('gc21_generator_extendscript',GEN)
g=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=g
spec.loader.exec_module(g)


def test_native_template_writes_json_without_unsupported_json_global():
    text=J.read_text(encoding='utf8')
    assert 'function quoteJson(value)' in text
    assert 'JSON.stringify(' not in text
    assert 'JSON.parse(' not in text
    assert 'p.write(body);' in text
    for key in ('schema','state','error','artboards','layer_count','ai_reopened','visual_approval','production_ready'):
        assert '"'+key+'"' in text


def test_template_uses_only_documented_layer_id_and_proves_png_files():
    text=J.read_text(encoding='utf8')
    assert 'l.note =' not in text
    assert 'l.name = name;' in text
    assert 'PNG_EXPORT_MISSING_P0' in text
    assert "must(pngReady.exists && pngReady.length>1000" in text
    assert "'NATIVE_AI_REOPENED_REVIEW_REQUIRED'" in text
    assert 'reopened.textFrames.length===7' in text


def test_greeting_card_four_artboard_template_remains_source_bound():
    text=J.read_text(encoding='utf8')
    assert text.count('/*__GC21_SCENE_JSON__*/')==1
    assert 'document.artboards.add(' in text
    assert "scene.sender_variant === 'HERASYMENKO'" in text
    assert "scene.front_family === 'STANDARD'" in text
    assert 'document.textFrames.length===7' in text
    assert 'document.saveAs(ai,save);' in text
    assert 'document.saveAs(pdf,pdfOpts);' in text


def test_render_does_not_lose_unicode_greeting():
    scene={'schema_version':g.SCENE_SCHEMA,'pages':4,'sender_variant':'HERASYMENKO',
        'front_family':'STANDARD','inside_image_mode':'PORTRAIT', 'greeting_text':'Привіт! "Ім’я"\\新',
        'layers':[]}
    jsx=g.render_jsx(scene)
    assert 'function quoteJson(value)' in jsx
    assert 'Привіт' not in jsx # private customer string encoded with JSON ensure_ascii=True
    assert json.dumps('Привіт',ensure_ascii=True)[1:-1] in jsx
