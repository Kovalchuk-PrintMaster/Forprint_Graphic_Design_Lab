"""TS r007: read-only Atlas, bounded PREPRESS evidence and separate stable definition identity."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import shutil

ROOT=Path(__file__).resolve().parents[2]
ATLAS=ROOT/'scripts/graphic_design_lab/greeting_cards/gc32_structure_atlas_v0_1.py'
HTML=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html'
TS=ROOT/'scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py'
MAP=ROOT/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'

def get_mod(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_prepress_passes_bounded_scope_and_truncated_truth(tmp_path):
    atlas=get_mod(ATLAS,'r007_atlas')
    client='Test Client'
    folder=tmp_path/'template_studio'/'inventory'
    folder.mkdir(parents=True)
    base={'schema_version':atlas.WINDOWS_SCHEMA,'machine':'PREPRESS','user':'Work',
          'client':client,'root':r'D:\ForPrint_Automation\GraficsDesignLab\Automation',
          'captured_utc':'2026-10-27T11:10:03Z','entries':[{'path':'Worker/gc32_prepress_ssh_snapshot_v0_1.ps1','kind':'file','size_bytes':100,'sha256':None}]}
    for flag in [False,True,None]:
        base['scan_truncated']=flag
        (folder/'prepress_snapshot.json').write_text(json.dumps(base))
        item, warnings=atlas._prepress(tmp_path,client,None)
        assert not warnings
        assert item['scan_truncated'] is flag
        assert item['counts']['items']==1
        assert item['source']=='PUBLISHED_WINDOWS_SELF_REPORT'
        assert item['state']=='SELF_REPORTED_NOT_REMOTE_ATTESTED'
        assert 'BOUNDED' in item['scan_scope']

def test_stable_definition_vs_fresh_snapshot_id():
    ts=get_mod(TS,'r007_ts')
    html=HTML.read_bytes()
    img={k:'data:image/png;base64,YQ==' for k in ('P01','P02','P03','P04')}
    model={'pages':[]}
    infra=json.loads(MAP.read_text())
    infra['audit']={'status':'OK'}
    infra['atlas']={'captured_utc':'2026-10-27T10:00:00Z'}
    a,aid=ts.html_bytes(model,img,html,infra=infra)
    infra['audit']={'status':'WARN'}
    infra['atlas']={'captured_utc':'2026-10-27T10:01:00Z'}
    infra['progress']={'new_external_status':'MOVED'}
    b,bid=ts.html_bytes(model,img,html,infra=infra)
    assert aid!=bid
    ra=re.search(rb'const BUILD = (\{[^;]+\});',a)
    rb=re.search(rb'const BUILD = (\{[^;]+\});',b)
    assert ra and rb
    assert json.loads(ra.group(1))['definition_id']==json.loads(rb.group(1))['definition_id']
    assert json.loads(ra.group(1))['id']!=json.loads(rb.group(1))['id']

def test_ui_is_single_atlas_and_offline():
    h=HTML.read_text('utf8')
    # r007 preserves a single Atlas and offline UI; later tabs are additive.
    # Validate the navigation registry, not an immutable literal list of all tabs.
    nav = re.search(
        r"(\[\['process','Конвеєр і контроль'\](?:,\['[^']+','[^']+'\])+\])\.forEach\(\(\[id,label\]\)",
        h,
    )
    assert nav, "Navigation tabs registry missing or malformed"
    tabs = re.findall(r"\['([^']+)','([^']+)'\]", nav.group(1))
    ids = [tab_id for tab_id, _ in tabs]
    assert len(ids) == len(set(ids)), "Duplicate navigation tab id"
    assert tabs[0] == ('process', 'Конвеєр і контроль')
    for tab in (
        ('atlas-concept', 'Еталонне дерево'),
        ('atlas-actual', 'Фактичне дерево'),
    ):
        assert tabs.count(tab) == 1, tab
    assert ids.index('atlas-concept') < ids.index('atlas-actual')
    assert "id.startsWith('atlas-')?renderAtlas()" in h
    assert "[['windows','PREPRESS · Windows']" not in h
    assert 'snap.scan_truncated' in h and 'snap.scan_scope' in h
    assert 'SSH-самозвіт PREPRESS' in h
    assert h.count('/*__TS_INFRA__*/')==1 and 'fetch(' not in h
    if shutil.which('node'):
        script=h.split('<script>',1)[1].split('</script>',1)[0]
        for part in ('/*__TS_INFRA__*/','/*__TS_FULL_MODEL__*/','/*__TS_FULL_IMAGES__*/','/*__TS_FULL_BUILD__*/'):
            script=script.replace(part,'{}')
        p=subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
        assert p.returncode==0,p.stderr

def test_source_map_marks_missing_head_targets_as_nonrelease():
    data=json.loads(MAP.read_text())
    record=data['coverage']['source_checkpoint_boundary']
    assert record['release_ready'] is False
    assert 'gc30-queue' in record['other_workflow_targets_worktree_only']
    assert 'Worker/gc32_prepress_ssh_snapshot_v0_1.ps1' in [e['path'] for e in data['worker']['structure']]
