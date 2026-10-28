"""GC29 P04 pilot native fit: source-only governance and synthetic JS execution.

This test does NOT run Illustrator or certify visual parity with Prepress Hub.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc29_native_four_page_v0_1.jsx'
CANONICAL = ROOT / 'coordination/graphic_design_lab/greeting_cards/gdl_gc_p04_prepress_source_reconciliation_v0_1.json'


def code():
    return TEMPLATE.read_text('utf-8')


def test_gc29_p04_source_bound_tiers_and_geometry():
    s = code()
    assert s.count('function greeting(font)') == 1
    assert 'var tiers=[7*PT,18.5,17,16.5,16];' in s
    assert 'var leadingMm=fontPt/PT*8/7;' in s
    assert '150*PT,180*PT' in s
    assert 'GC29_GREETING_OVERFLOW_REVIEW_REQUIRED' not in s
    assert 'rows*8' not in s
    assert 'function nativeFitProof(frame)' in s
    assert 'lastVisibleOffset(frame)' in s


def test_only_layout_changes_and_no_leaked_private_text():
    s = code()
    assert '/*__GC29_SCENE__*/' in s
    assert 'scene.greeting_text' in s
    assert 'source_pdf_runtime_used":false' in s
    assert "need(!target.exists,'GC29_OUTPUT_EXISTS_NO_OVERWRITE')" in s
    assert 'AI_REOPENED_VISUAL_REVIEW_REQUIRED' in s
    assert 'P04_GREETING_FIT_UNPROVEN_REVIEW_REQUIRED' in s
    assert 'opened.close(SaveOptions.DONOTSAVECHANGES)' in s
    assert 'D.close(SaveOptions.DONOTSAVECHANGES)' in s
    assert 'p04_greeting_fit_state' in s
    assert 'production_ready":false' in s
    assert 'sender(font)' in s
    assert 'var baselines=[227,235,243,251];' in s, 'sender coordinates intentionally unchanged until private canonical registries recovered'
    assert len(re.findall(r'function greeting\(', s)) == 1


def test_prepress_source_profile_bound_to_existing_registry():
    import json
    d = json.loads(CANONICAL.read_text('utf-8'))['source_profile_verified']
    assert d['greeting_bbox_pdf_mm'] == [32.0, 32.0, 182.0, 212.0]
    assert [round(x,2) for x in d['renderer_fallback_tiers_pt']] == [19.84,18.5,17.,16.5,16.]
    assert d['sender']['DUAL_GRIGO_HERASYMENKO']['status'].startswith('RUNTIME_DISABLED')


def test_node_syntax_for_compiled_jsx():
    if not shutil.which('node'):
        pytest.skip('NODE_NOT_INSTALLED_STATIC_CHECKS_STILL_RUN')
    s = code().replace('#target illustrator','').replace('/*__GC29_SCENE__*/', '{}')
    r = subprocess.run(['node','--check'],input=s,text=True,capture_output=True,timeout=10)
    assert r.returncode == 0,r.stderr


def test_javascript_native_fit_synthetic_probe():
    node = shutil.which('node')
    if not node:
        pytest.skip('NODE_NOT_INSTALLED_STATIC_CHECKS_STILL_RUN')
    s = code()
    funcs = s[s.index('  function significantLength('):s.index('  function sender(font){')]
    # Simulate frame object only. Verifies fit-loop logic, never Illustrator ink metrics.
    harness = r'''
      var PT=72/25.4,H=301*PT;
      var fitState='NOT_ATTEMPTED',fitFontPt=null,fitLeadingMm=null;
      var fitLines=0,fitVisible=0,fitCharacters=0,fitAttempts=0,centered=false;
      var scene={greeting_text:TEXT};
      var Justification={CENTER:1};
      var ElementPlacement={PLACEATBEGINNING:1};
      var app={redraw:function(){}};
      var L={move:function(){}},shape={move:function(){}};
      var ch={size:19.8425,leading:0,autoLeading:false};
      var paragraph={paragraphAttributes:{spaceBefore:0}};
      var frame={name:'', contents:'', paragraphs:[paragraph],
        textRange:{characterAttributes:ch,paragraphAttributes:{justification:0,spaceAfter:0,spaceBefore:0}}};
      Object.defineProperty(frame.textRange,'characters',{get:function(){
        return frame.contents.split('').map(function(c,i){return {contents:c,characterOffset:i};});
      }});
      Object.defineProperty(frame,'lines',{get:function(){
        var count=Math.max(1,Math.ceil(frame.contents.length/ROWCHARS));
        var num=Math.min(count,Math.floor(180*PT/(ch.leading||8*PT)));
        var a=[];for(var i=0;i<num;i++){
          var first=i*ROWCHARS,last=Math.min(frame.contents.length,(i+1)*ROWCHARS);
          var chars=[];for(var j=first;j<last;j++)chars.push({characterOffset:j,contents:frame.contents.charAt(j)});
          a.push({characters:chars});
        }return a;
      }});
      var D={pathItems:{rectangle:function(){return shape;}},textFrames:{areaText:function(){return frame;}}};
      function ax(){return 0;}
      function layer(){return L;}
      function setFont(){}
      function need(x,code){if(!x)throw new Error(code);}
    '''
    for txt,chars,expected in [('Short synthetic greeting',12,'VISIBLE_CONTENT_FITS'), ('X'*900,10,'FIT_UNPROVEN_REVIEW_REQUIRED')]:
        script = harness.replace('TEXT',repr(txt)).replace('ROWCHARS',str(chars))+'\n'+funcs+'\ngreeting({});\n'
        script += 'if(fitState!=='+repr(expected)+')throw new Error("FIT_STATE="+fitState);\n'
        script += 'if(fitAttempts<1||fitAttempts>5)throw new Error("BAD_TRIAL_COUNT");\n'
        script += 'if(frame.contents!==scene.greeting_text)throw new Error("CONTENT_MUTATED");\n'
        script += 'if(fitState==="FIT_UNPROVEN_REVIEW_REQUIRED" && fitAttempts!==5)throw new Error("FALLBACK_NOT_TRIED");\n'
        result = subprocess.run([node,'-'],input=script,text=True,capture_output=True,timeout=10)
        assert result.returncode == 0,result.stderr
