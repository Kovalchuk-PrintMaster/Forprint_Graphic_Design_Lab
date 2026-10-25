#!/usr/bin/env python3
"""GC25: read-only independent-GDL Illustrator SMB queue capability audit.

This checks real accepted handoff *envelopes*, not that Illustrator can render them.
No client output, no source mutation, no requeue, no Prepress Hub imports.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import sys
import zipfile
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json'
SHARE_ROOTS = {'In_Progress': Path('/srv/smb/In_Progress/data')}
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
BLOCKED_TEXT = re.compile(r'\b(?:sanitized|placeholder|synthetic|lorem\s+ipsum)\b', re.I)
REQUIRED_HANDOFF = frozenset({'accepted_constructor_bundle.yaml','artifact_manifest.yaml','handoff_manifest.json'})
REQUIRED_STAGING = frozenset({'packet_manifest.json','BLOCKERS.yaml','SERVER_INGEST_STAGING.yaml'})
MAX_ARCHIVE_BYTES = 250_000_000
MAX_MEMBER_BYTES = 100_000_000
MAX_UNPACKED_BYTES = 500_000_000
MAX_MEMBERS = 300

class Blocked(ValueError):
    pass

def require(condition: Any, reason: str) -> None:
    if not condition:
        raise Blocked(reason)

def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),'CATALOG_MISSING')
    obj = json.loads(path.read_text(encoding='utf8'))
    require(isinstance(obj,dict),'CATALOG_INVALID')
    return obj

def digest(content: bytes) -> str:
    return sha256(content).hexdigest()

def token_to_relative(token: str) -> tuple[str, str]:
    require(isinstance(token,str) and len(token) <= 5000 and re.fullmatch('[A-Za-z0-9_-]+',token),'WORKSPACE_TOKEN_INVALID')
    try:
        raw = base64.urlsafe_b64decode(token+'='*(-len(token)%4)).decode('utf8')
    except (ValueError,UnicodeError) as exc:
        raise Blocked('WORKSPACE_TOKEN_INVALID') from exc
    parts = raw.split('/')
    require(len(parts)==2 and all(p not in ('','.','..') and '\\' not in p and '\x00' not in p for p in parts) and parts[1]=='_forprint_automation', 'WORKSPACE_TOKEN_LAYOUT_INVALID')
    return parts[0],parts[1]

def workspace_path(share: str, token: str, *, roots: dict[str, Path]|None=None) -> Path:
    directories=SHARE_ROOTS if roots is None else roots
    require(share in directories,'SHARE_NOT_SUPPORTED')
    root=directories[share].resolve(strict=True)
    parts=token_to_relative(token)
    folder=root.joinpath(*parts)
    require(not folder.is_symlink(),'WORKSPACE_SYMLINK')
    actual=folder.resolve(strict=True)
    require(actual.parent.parent==root and actual.is_dir(),'WORKSPACE_ESCAPE')
    for part in ('input','output'):
        p=actual/part
        require(p.is_dir() and not p.is_symlink(),'WORKSPACE_LAYOUT_INCOMPLETE')
    return actual

def safe_zip(z: zipfile.ZipFile) -> set[str]:
    info=z.infolist()
    require(0<len(info)<=MAX_MEMBERS,'ARCHIVE_MEMBER_COUNT')
    require(sum(i.file_size for i in info)<=MAX_UNPACKED_BYTES,'ARCHIVE_UNPACKED_TOO_LARGE')
    names=[];cases=set()
    for item in info:
        name=item.filename
        require(not item.is_dir() and 0<=item.file_size<=MAX_MEMBER_BYTES,'ARCHIVE_MEMBER_TYPE_OR_SIZE')
        require(name and not name.startswith('/') and '\\' not in name and '\x00' not in name and ':' not in name.split('/')[0] and all(p not in ('','.','..') for p in name.split('/')),'ARCHIVE_MEMBER_PATH')
        mode=(item.external_attr>>16)&0o170000
        require(mode in (0,0o100000),'ARCHIVE_MEMBER_NOT_REGULAR')
        require(name.casefold() not in cases,'ARCHIVE_DUPLICATE_MEMBER')
        cases.add(name.casefold());names.append(name)
    return set(names)

def file_record(z: zipfile.ZipFile,name: str, *,max_bytes: int=2_000_000) -> bytes:
    info=z.getinfo(name)
    require(info.file_size<=max_bytes,'ARCHIVE_META_TOO_LARGE')
    data=z.read(name)
    require(len(data)==info.file_size,'ARCHIVE_TRUNCATED')
    return data

def parse_yaml(contents: bytes) -> dict[str,Any]:
    obj=yaml.safe_load(contents)
    require(isinstance(obj,dict),'ARCHIVE_SCHEMA')
    return obj

def parse_json(contents: bytes) -> dict[str,Any]:
    obj=json.loads(contents.decode('utf8'))
    require(isinstance(obj,dict),'ARCHIVE_SCHEMA')
    return obj

def bundle_digest(bundle: dict[str,Any]) -> str:
    from copy import deepcopy
    doc=deepcopy(bundle)
    provenance=doc.get('provenance_manifest')
    require(isinstance(provenance,dict),'PROVENANCE_MISSING')
    provenance['bundle_sha256']=''
    return digest(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8'))

def check_accepted(z: zipfile.ZipFile, names: set[str], catalog: dict[str,Any]) -> dict[str,Any]:
    allowed=REQUIRED_HANDOFF
    require(names >= allowed,'HANDOFF_INCOMPLETE')
    require(not (names & REQUIRED_STAGING),'CONFLICTING_HANDOFF_STAGING')
    require(all(n in allowed or n.startswith('assets/') or n.startswith('intake_evidence/') for n in names),'HANDOFF_UNEXPECTED_MEMBER')
    braw=file_record(z,'accepted_constructor_bundle.yaml',max_bytes=10_000_000)
    araw=file_record(z,'artifact_manifest.yaml',max_bytes=10_000_000)
    handoff=parse_json(file_record(z,'handoff_manifest.json'))
    require(handoff.get('schema_version')=='gdl_intake_builder_handoff_v0_1' and handoff.get('mode')=='REVIEW_ONLY','HANDOFF_AUTHORITY_INVALID')
    require(handoff.get('accepted_bundle_file_sha256')==digest(braw) and handoff.get('artifact_manifest_file_sha256')==digest(araw),'HANDOFF_FILE_SHA_MISMATCH')
    bundle=parse_yaml(braw); artifacts=parse_yaml(araw)
    require(bundle.get('schema_version')=='gdl_greeting_card_accepted_constructor_bundle_v0_1','BUNDLE_SCHEMA_INVALID')
    prov=bundle.get('provenance_manifest') or {}; review=bundle.get('intake_review') or {}
    require(prov.get('algorithm')=='sha256_canonical_json_v0_1' and prov.get('bundle_sha256')==bundle_digest(bundle),'BUNDLE_PROVENANCE_SHA_INVALID')
    require(review.get('state')=='PASS' and isinstance(review.get('review_id'),str) and bool(review.get('review_id')),'OPERATOR_REVIEW_NOT_PASS')
    require(prov.get('intake_review_id')==review.get('review_id') and review.get('source_batch_id')==bundle.get('source_batch_id'),'REVIEW_BATCH_MISMATCH')
    require(not bundle.get('synthetic_fixture_only',False),'SYNTHETIC_BUNDLE_FORBIDDEN')
    auth=bundle.get('authority') or {}
    for k in ('provider_execution_performed','gdl_runtime_initialized','production_write_enabled','automatic_customer_messaging','automatic_design_approval'):
        require(auth.get(k) is False,'ACCEPTED_AUTHORITY_INVALID')
    jobs=bundle.get('jobs')
    require(isinstance(jobs,list) and 0<len(jobs)<=50,'HANDOFF_JOB_COUNT')
    artifact_mapping=artifacts.get('artifacts')
    require(artifacts.get('schema_version')=='gdl_greeting_card_builder_artifact_manifest_v0_1' and isinstance(artifact_mapping,dict),'ARTIFACT_SCHEMA_INVALID')
    expected={}
    summary=[]
    for job in jobs:
        require(isinstance(job,dict),'JOB_SCHEMA')
        p=job.get('builder_v1') or {}; front=p.get('front') or {}; img=p.get('inside_image') or {}; sender=p.get('sender_text') or {}
        fam=front.get('family'); imode=img.get('mode'); sig=sender.get('signature_variant_id')
        require(fam in catalog['front_variants'] and imode in catalog['photo_variants'] and sig in catalog['signature_variants'],'JOB_VARIANT_UNKNOWN')
        require((job.get('signature_selection') or {}).get('variant_id')==sig,'JOB_SIGNATURE_INCONSISTENT')
        require((front.get('occasion') or {}).get('kind')==(job.get('structured_greeting_data') or {}).get('occasion'),'JOB_OCCASION_INCONSISTENT')
        greeting=(job.get('structured_greeting_data') or {}).get('greeting_text')
        title=(front.get('occasion') or {}).get('display_text')
        require(all(isinstance(x,str) and x.strip() and len(x)<=20000 and not BLOCKED_TEXT.search(x) for x in (greeting,title)),'TEST_CONTENT_NOT_ACCEPTABLE')
        visual=(job.get('accepted_visual_assets') or [{}])[0] or {}
        require(visual.get('acceptance_basis') in ('SOURCE_ASSET_OPERATOR_REVIEW_PASS','CREATOR_INTERNAL_REVIEW_PASS'),'JOB_VISUAL_NOT_REVIEWED')
        if imode=='DEFAULT_ASSET':
            spec=catalog['photo_variants']['DEFAULT_ASSET']
            require(img.get('asset_id')==spec['asset_id'] and img.get('asset_sha256')==spec['sha256'] and img.get('accepted_artifact_ref') is None,'FLOWERS_BINDING_INVALID')
            require(visual.get('source_asset_id')==img.get('asset_id') and visual.get('provenance_sha256')==img.get('asset_sha256') and visual.get('acceptance_basis')=='SOURCE_ASSET_OPERATOR_REVIEW_PASS','FLOWERS_REVIEW_INVALID')
        else:
            require(visual.get('artifact_ref')==img.get('accepted_artifact_ref'),'PORTRAIT_REVIEW_BINDING')
            ref=img.get('accepted_artifact_ref');expected[ref]=(img.get('asset_id'),img.get('asset_sha256'))
        branding=job.get('branding_selection') or {}
        if fam=='RECIPIENT_BRANDING_OVERLAY':
            logo=front.get('recipient_branding') or {}
            require(branding.get('presence')=='PRESENT' and logo.get('asset_id')==branding.get('source_asset_id'),'BRANDING_CONTRACT_INVALID')
            expected[logo.get('accepted_artifact_ref')]=(logo.get('asset_id'),logo.get('asset_sha256'))
        else:
            require(branding.get('presence')!='PRESENT' and front.get('recipient_branding') is None,'BRANDING_UNEXPECTED')
        reasons=[]
        if fam!='STANDARD': reasons.append('P01_VARIANT_NOT_IN_GC21')
        if imode!='PORTRAIT': reasons.append('P03_DEFAULT_FLOWERS_NOT_IN_GC21')
        if sig!='HERASYMENKO': reasons.append('P04_SIGNATURE_NOT_IN_GC21')
        if title!='Привітання з нагоди Дня Народження!': reasons.append('P01_TITLE_NOT_IN_GC21')
        summary.append({'family':fam,'image':imode,'signature':sig,'native_gc21_capability':'NOT_IMPLEMENTED' if reasons else 'REQUIRES_GC24_RESOURCE_PREFLIGHT','blockers':reasons})
    require(set(artifact_mapping)==set(expected),'ARTIFACT_SET_MISMATCH')
    for ref,(asset_id,actual_sha) in expected.items():
        entry=artifact_mapping[ref]
        require(isinstance(entry,dict) and entry.get('source_asset_id')==asset_id and entry.get('sha256')==actual_sha,'ARTIFACT_BINDING_MISMATCH')
        path=entry.get('path')
        require(isinstance(path,str) and path.startswith('assets/') and path in names and SHA_RE.fullmatch(actual_sha),'ARTIFACT_MEMBER_MISSING')
        require(digest(z.read(path))==actual_sha,'ARTIFACT_BYTES_SHA_MISMATCH')
    require({x for x in names if x.startswith('assets/')}=={entry['path'] for entry in artifact_mapping.values()},'UNREFERENCED_ARTIFACT')
    return {'kind':'ACCEPTED_HANDOFF','jobs':len(jobs),'variants':summary,'native_ready_count':0,'status':'NATIVE_EXECUTOR_NOT_READY'}

def inspect_archive(path:Path,catalog:dict[str,Any])->dict[str,Any]:
    require(path.is_file() and not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),'ARCHIVE_NOT_REGULAR')
    require(path.stat().st_size<=MAX_ARCHIVE_BYTES,'ARCHIVE_TOO_LARGE')
    with zipfile.ZipFile(path) as z:
        names=safe_zip(z)
        if REQUIRED_STAGING <= names:
            require(not (names & REQUIRED_HANDOFF),'CONFLICTING_STAGING_HANDOFF')
            stage=parse_yaml(file_record(z,'SERVER_INGEST_STAGING.yaml'))
            blockers=parse_yaml(file_record(z,'BLOCKERS.yaml'))
            require(stage.get('packet_kind')=='STRUCTURED_INTAKE_STAGING_NOT_ACCEPTED_BUNDLE' and blockers.get('final_handoff_allowed') is False,'STAGING_CONTRACT_INVALID')
            return {'kind':'STAGING','status':'HISTORICAL_STAGING_BLOCKED','jobs':len((stage.get('asset_selection_rule') or {}).get('all_job_ids') or [])}
        if REQUIRED_HANDOFF <= names:
            return check_accepted(z,names,catalog)
        return {'kind':'OTHER','status':'NOT_GDL_ACCEPTED_HANDOFF','jobs':0}

def scan(workspace:Path,catalog:dict[str,Any])->tuple[list[dict[str,Any]],int]:
    folder=workspace/'input'
    require(folder.is_dir() and not folder.is_symlink(),'INPUT_DIR_MISSING')
    files=sorted((p for p in folder.iterdir() if p.name.lower().endswith('.zip')),key=lambda x:x.name.casefold())
    require(len(files)<=100,'TOO_MANY_INPUT_ARCHIVES')
    results=[]; errors=0
    for p in files:
        try:
            doc=inspect_archive(p,catalog)
        except (Blocked,zipfile.BadZipFile,KeyError,ValueError,TypeError,yaml.YAMLError,json.JSONDecodeError,UnicodeError,OSError) as exc:
            code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
            doc={'kind':'INVALID','status':'ARCHIVE_REJECTED','error_code':code,'jobs':0}
            errors+=1
        results.append({'source':p.name,**doc})
    return results,errors

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('check','run'),required=True)
    parser.add_argument('--share',default='In_Progress')
    parser.add_argument('--workspace-relative-b64',required=True)
    a=parser.parse_args()
    try:
        require(a.mode=='check','ILLUSTRATOR_NATIVE_RUN_NOT_IMPLEMENTED')
        ws=workspace_path(a.share,a.workspace_relative_b64)
        catalog=load_json(CATALOG)
        require(catalog.get('schema_version')=='forprint_gdl_gc23_variant_contract_v0_1' and catalog.get('p04_greeting_bbox_pdf_mm')==[32,32,182,212],'GC23_CATALOG_CHANGED')
        result,errors=scan(ws,catalog)
        for r in result:
            print('GC25_SOURCE='+r['source'])
            print('GC25_KIND='+r['kind']+' STATUS='+r['status']+' JOBS='+str(r['jobs']))
            for i,j in enumerate(r.get('variants',[])):
                print('GC25_JOB_INDEX='+str(i)+' FRONT='+j['family']+' IMAGE='+j['image']+' SIGNATURE='+j['signature']+' NATIVE='+j['native_gc21_capability'])
                for code in j['blockers']:print('GC25_NATIVE_GAP='+code)
            if r.get('error_code'): print('GC25_ERROR_CODE='+r['error_code'])
        print('GC25_ARCHIVES='+str(len(result))+' INVALID='+str(errors))
        print('GDL_GC25_ILLUSTRATOR_SMB=CHECK_COMPLETE_READ_ONLY')
        print('ILLUSTRATOR_EXECUTED=false CLIENT_FILES_CHANGED=false')
        return 2 if errors else 0
    except (Blocked,KeyError,ValueError,TypeError,OSError) as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GDL_GC25_ILLUSTRATOR_SMB=BLOCKED reason='+code,file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
