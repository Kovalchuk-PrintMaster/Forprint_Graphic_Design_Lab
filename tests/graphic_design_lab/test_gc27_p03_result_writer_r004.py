"""GC27 r004: structured Illustrator result survives ExtendScript ES3 runtime.

No live Illustrator or private client data required.
"""
from pathlib import Path
import json
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]
JSX=ROOT/'scripts/graphic_design_lab/greeting_cards/gc27_p03_default_flowers_proof_v0_1.jsx'

def text(): return JSX.read_text(encoding='utf-8')

def test_json_stringify_dependency_removed():
    assert 'JSON.stringify' not in text()
    assert 'function resultJson()' in text()

def test_fixed_schema_and_no_auto_authority():
    s=text()
    for value in ('gdl_gc27_p03_native_proof_result_v0_1',
                  'native_full_card_supported\":false', 'visual_approved\":false',
                  'pdf_builder_pixel_parity_verified\":false', 'production_ready\":false'):
        assert value in s

def test_report_before_file_open():
    s=text()
    a=s.index('    function putResult()')
    b=s.index('    try {\n        must(scene.schema_version',a)
    part=s[a:b]
    assert part.index('var payload = resultJson()') < part.index("file.open('w')")
    assert "if (file.exists) { return; }" in part
    assert "finally { file.close(); }" in part

def test_source_document_and_reopen_checks_unchanged():
    s=text()
    assert 'must(doc.layers.length === 1' in s
    assert 'var layer=(j===0)?doc.layers[0]:doc.layers.add();' in s
    assert 'reopened.layers.getByName(\'P03.DEFAULT_FLOWERS\')' in s
    assert "must(!target.exists, 'OUTPUT_EXISTS_NO_OVERWRITE');" in s

def test_error_propagated_to_machine_json():
    s=text()
    assert "code=String(err.message || err);" in s
    assert 'putResult();' in s
    assert "',\"error\":' + jsonQuote(code)" in s

@pytest.mark.skipif(shutil.which('node') is None,reason='Node optional for ES3-compatible JS reporter check')
@pytest.mark.parametrize('state,error',[
    ('P03_NATIVE_AI_REOPENED_VISUAL_REVIEW_REQUIRED','NONE'),
    ('BLOCKED_REVIEW_REQUIRED','Missing source'),
    ('BLOCKED_REVIEW_REQUIRED','Невірний \\ шлях "Привіт"\n'),
])
def test_reporter_executes_and_parses_as_json(state,error):
    src=text()
    first=src.index('    function jsonQuote(')
    last=src.index('    try {\n        must(scene.schema_version',first)
    js=src[first:last]
    harness="const vm=require('vm');\nconst code=JSON.parse(process.argv[1]);\nconst stateValue=JSON.parse(process.argv[2]);\nconst errorValue=JSON.parse(process.argv[3]);\nconst writes=[];\nconst mock={outcome:stateValue,code:errorValue,target:{exists:true,fsName:'/tmp/out'},must:(v,name)=>{if(!v)throw Error(name)},\n File:class {constructor(){this.exists=false;this.length=0;}open(){return true;}write(x){writes.push(x);this.exists=true;this.length=Buffer.byteLength(x);return true;}close(){}}};\nvm.createContext(mock);vm.runInContext(code,mock);vm.runInContext('putResult()',mock);\nprocess.stdout.write(writes[0]);\n"
    result=subprocess.run(['node','-e',harness,json.dumps(js),json.dumps(state),json.dumps(error)],
        check=True,capture_output=True,text=True)
    doc=json.loads(result.stdout)
    assert doc['state']==state and doc['error']==error
    assert doc['visual_approved'] is False
    assert doc['production_ready'] is False
