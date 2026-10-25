"""GC27 r003 source-level invariant tests. Native Illustrator requires Windows proof."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'scripts/graphic_design_lab/greeting_cards/gc27_p03_default_flowers_proof_v0_1.jsx'

def code():
    return SOURCE.read_text(encoding='utf8')

def test_one_default_layer_reused_as_paper():
    s=code()
    assert "must(doc.layers.length === 1, 'P03_INITIAL_LAYER_COUNT_INVALID');" in s
    assert 'var layer=(j===0)?doc.layers[0]:doc.layers.add();' in s
    assert 'var layer=doc.layers.add();' not in s

def test_layer_names_keep_source_defined_order():
    s=code()
    assert "scene.layers[0].role === 'P03.PAPER'" in s
    assert "scene.layers[1].role === 'P03.DEFAULT_FLOWERS'" in s
    assert "scene.layers[2].role === 'P03.FRAME'" in s
    assert "layer.name=layerSpec.role;" in s

def test_three_layers_and_reopen_gate_remain():
    s=code()
    assert "doc.artboards.length === 1 && doc.layers.length === 3" in s
    assert "reopened.artboards.length === 1 && reopened.layers.length === 3" in s
    assert "reopened.layers.getByName('P03.DEFAULT_FLOWERS')" in s

def test_no_print_authority_and_no_asset_transformation():
    s=code()
    assert 'scene.production_ready' in s
    assert 'production_ready:false' in s
    assert 'pdf_builder_pixel_parity_verified:false' in s
    assert 'P03_SOURCE_VISIBLE_INTERSECTION_TOO_SMALL' in s
    assert 'placed.embed();' in s

def test_layer_placement_scope_one_reuse_two_additions():
    s=code()
    assert s.count('var layer=(j===0)?doc.layers[0]:doc.layers.add();')==1
    assert len(re.findall(r'doc\.layers\.add\(\)',s))==1
    assert s.index('doc.artboards[0].artboardRect') < s.index('P03_INITIAL_LAYER_COUNT_INVALID') < s.index('var layer=(j===0)')

def test_no_unreviewed_publish_added():
    s=code()
    assert "visual_approved:false" in s
    assert "NATIVE_FULL_CARD" not in s
    assert "must(!target.exists, 'OUTPUT_EXISTS_NO_OVERWRITE');" in s
