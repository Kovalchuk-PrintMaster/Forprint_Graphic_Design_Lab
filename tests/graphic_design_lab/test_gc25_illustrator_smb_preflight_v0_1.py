"""GC25 independent GDL SMB client launcher - synthetic read-only tests.
No customer bytes or Windows execution required.
"""
from __future__ import annotations
import base64
import importlib.util
import io
import json
from hashlib import sha256
from pathlib import Path
import sys
import zipfile

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'scripts/graphic_design_lab/greeting_cards/gc25_illustrator_smb_preflight_v0_1.py'
spec=importlib.util.spec_from_file_location('gc25_smb',MODULE)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

SHA=sha256(b'test-logo').hexdigest()
CAT={'front_variants':{'STANDARD':{},'RECIPIENT_BRANDING_OVERLAY':{},'BILINGUAL_OCCASION':{}},
     'photo_variants':{'PORTRAIT':{},'DEFAULT_ASSET':{'asset_id':'flowers.default.v1','sha256':'d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67'}},
     'signature_variants':{'GRIGO':{},'HERASYMENKO':{},'DUAL_GRIGO_HERASYMENKO':{}}}

def token(path):
    return base64.urlsafe_b64encode(path.encode('utf8')).decode('ascii').rstrip('=')

def write_zip(path, members):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in members.items():z.writestr(name,data)

def synthetic_handoff():
    data={'schema_version':'gdl_greeting_card_accepted_constructor_bundle_v0_1',
      'source_batch_id':'synthetic-test',
      'intake_review':{'review_id':'approved-synthetic-review','state':'PASS','source_batch_id':'synthetic-test'},
      'authority':{k:False for k in ('provider_execution_performed','gdl_runtime_initialized','production_write_enabled','automatic_customer_messaging','automatic_design_approval')},
      'jobs':[{'structured_greeting_data':{'greeting_text':'Тестове привітання','occasion':'BIRTHDAY'},
        'signature_selection':{'variant_id':'HERASYMENKO'},'branding_selection':{'presence':'ABSENT'},
        'accepted_visual_assets':[{'acceptance_basis':'CREATOR_INTERNAL_REVIEW_PASS','artifact_ref':'portrait-ref'}],
        'builder_v1':{'front':{'family':'STANDARD','occasion':{'kind':'BIRTHDAY','display_text':'Привітання з нагоди Дня Народження!'}},
          'inside_image':{'mode':'PORTRAIT','asset_id':'portrait-source','asset_sha256':SHA,'accepted_artifact_ref':'portrait-ref'},
          'sender_text':{'signature_variant_id':'HERASYMENKO'}}}],
      'provenance_manifest':{'algorithm':'sha256_canonical_json_v0_1','bundle_sha256':'','intake_review_id':'approved-synthetic-review'}}
    data['provenance_manifest']['bundle_sha256']=mod.bundle_digest(data)
    manifest={'schema_version':'gdl_greeting_card_builder_artifact_manifest_v0_1','artifacts':{
      'portrait-ref':{'source_asset_id':'portrait-source','path':'assets/portrait.png','sha256':SHA}}}
    blob=yaml.safe_dump(data,allow_unicode=True).encode('utf8');a=yaml.safe_dump(manifest).encode('utf8')
    hand={'schema_version':'gdl_intake_builder_handoff_v0_1','mode':'REVIEW_ONLY',
          'accepted_bundle_file_sha256':mod.digest(blob),'artifact_manifest_file_sha256':mod.digest(a)}
    return {'accepted_constructor_bundle.yaml':blob,'artifact_manifest.yaml':a,
        'handoff_manifest.json':json.dumps(hand).encode('utf8'),'assets/portrait.png':b'test-logo'}

@pytest.fixture
def ws(tmp_path):
    root=tmp_path/'share';folder=root/'Вікторія'/'_forprint_automation'
    (folder/'input').mkdir(parents=True); (folder/'output').mkdir()
    return root,folder

def test_unicode_client_folder(ws):
    root,folder=ws
    assert mod.workspace_path('In_Progress',token('Вікторія/_forprint_automation'),roots={'In_Progress':root})==folder

@pytest.mark.parametrize('path',['a/../_forprint_automation','a//_forprint_automation','a/./_forprint_automation',
    '/a/_forprint_automation','a/extra/_forprint_automation','a/not_the_correct_folder'])
def test_bad_workspace_token(ws,path):
    root,folder=ws
    with pytest.raises(mod.Blocked):mod.workspace_path('In_Progress',token(path),roots={'In_Progress':root})

def test_bad_share(ws):
    root,folder=ws
    with pytest.raises(mod.Blocked,match='SHARE_NOT_SUPPORTED'):
        mod.workspace_path('Another',token('Вікторія/_forprint_automation'),roots={'In_Progress':root})

def test_symlink_workspace_rejected(ws):
    root,folder=ws
    new_client=root/'test_link';new_client.mkdir()
    symlink=new_client/'_forprint_automation';symlink.symlink_to(folder,target_is_directory=True)
    with pytest.raises(mod.Blocked):mod.workspace_path('In_Progress',token('test_link/_forprint_automation'),roots={'In_Progress':root})

def test_accept_valid_fixture(ws):
    root,folder=ws;p=folder/'input'/'gdl_intake_handoff.zip'
    write_zip(p,synthetic_handoff())
    before=p.read_bytes();rec=mod.inspect_archive(p,CAT)
    assert rec['kind']=='ACCEPTED_HANDOFF' and rec['jobs']==1
    assert rec['variants'][0]['native_gc21_capability']=='REQUIRES_GC24_RESOURCE_PREFLIGHT'
    assert rec['native_ready_count']==0 and before==p.read_bytes()

def test_sanitized_refused(ws):
    _,folder=ws;members=synthetic_handoff()
    bundle=yaml.safe_load(members['accepted_constructor_bundle.yaml'])
    bundle['jobs'][0]['structured_greeting_data']['greeting_text']='Sanitized birthday greeting.'
    bundle['provenance_manifest']['bundle_sha256']=mod.bundle_digest(bundle)
    raw=yaml.safe_dump(bundle,allow_unicode=True).encode('utf8');members['accepted_constructor_bundle.yaml']=raw
    hand=json.loads(members['handoff_manifest.json']);hand['accepted_bundle_file_sha256']=mod.digest(raw)
    members['handoff_manifest.json']=json.dumps(hand).encode('utf8')
    p=folder/'input'/'sanitized.zip';write_zip(p,members)
    with pytest.raises(mod.Blocked,match='TEST_CONTENT_NOT_ACCEPTABLE'):mod.inspect_archive(p,CAT)

def test_modified_asset_refused(ws):
    _,folder=ws;members=synthetic_handoff();members['assets/portrait.png']=b'other'
    p=folder/'input'/'changed.zip';write_zip(p,members)
    with pytest.raises(mod.Blocked,match='ARTIFACT_BYTES_SHA_MISMATCH'):mod.inspect_archive(p,CAT)

def test_old_staging_remains_blocked(ws):
    _,folder=ws;p=folder/'input'/'blocked.zip'
    write_zip(p,{'BLOCKERS.yaml':yaml.safe_dump({'final_handoff_allowed':False}).encode(),
     'SERVER_INGEST_STAGING.yaml':yaml.safe_dump({'packet_kind':'STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE'}).encode(),
     'packet_manifest.json':b'{}'})
    record=mod.inspect_archive(p,CAT)
    assert record['kind']=='STAGING' and record['status']=='HISTORICAL_STAGING_BLOCKED'

def test_conflicting_staging_blocked(ws):
    _,folder=ws;members=synthetic_handoff();members['BLOCKERS.yaml']=b'a: true'
    members['SERVER_INGEST_STAGING.yaml']=b'status: blocked';members['packet_manifest.json']=b'{}'
    p=folder/'input'/'conflict.zip';write_zip(p,members)
    with pytest.raises(mod.Blocked,match='CONFLICTING_STAGING_HANDOFF'):mod.inspect_archive(p,CAT)

def test_traversal_member_rejected(ws):
    _,folder=ws;p=folder/'input'/'traversal.zip'
    write_zip(p,{'../bad.txt':b'x'})
    with pytest.raises(mod.Blocked,match='ARCHIVE_MEMBER_PATH'):mod.inspect_archive(p,CAT)

def test_duplicate_casefold_members_rejected(ws):
    _,folder=ws;p=folder/'input'/'dups.zip'
    write_zip(p,{'a.txt':b'x','A.TXT':b'x'})
    with pytest.raises(mod.Blocked,match='ARCHIVE_DUPLICATE_MEMBER'):mod.inspect_archive(p,CAT)

def test_unknown_zip_not_processed(ws):
    _,folder=ws;p=folder/'input'/'other.zip';write_zip(p,{'readme.txt':b'x'})
    assert mod.inspect_archive(p,CAT)['kind']=='OTHER'

def test_scan_preserves_files_and_reports_invalid(ws):
    _,folder=ws;good=folder/'input'/'handoff.zip';bad=folder/'input'/'bad.zip'
    write_zip(good,synthetic_handoff());bad.write_bytes(b'not a zip')
    before={x.name:x.read_bytes() for x in (folder/'input').iterdir()}
    result,errors=mod.scan(folder,CAT)
    after={x.name:x.read_bytes() for x in (folder/'input').iterdir()}
    assert errors==1 and len(result)==2 and before==after

def test_windows_route_uses_own_repo_not_prepress():
    scripts=MODULE.parent/'windows'
    ps=(scripts/'gdl_greeting_card_illustrator_check_v0_1.ps1').read_text()
    cmd=(scripts/'launch_greeting_card_illustrator_check_v0_1.cmd').read_text()
    assert 'forprint_graphic_design_lab' in ps and 'forprint_prepress_hub' not in ps
    assert 'gc25-illustrator-queue-check' in ps and 'powershell.exe' in cmd
    assert 'gc25-illustrator-queue-check' in (ROOT/'Makefile').read_text()
