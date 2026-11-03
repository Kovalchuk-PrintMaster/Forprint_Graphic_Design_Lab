#!/usr/bin/env python3
"""ForPrint Illustrator Studio Intake interface v1: read-only ZIP classifier.

No customer write, no Illustrator/Windows native, no supported run authority.
This reads and verifies existing v0.1 handoff envelope and data linkage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

try:
    import yaml
except ImportError:
    yaml = None

SCHEMA = 'forprint_illustrator_studio_intake_audit_v1'
FLOWER_ID='flowers.default.v1'
FLOWER_SHA='d9113f8d6f9627f9b106f5550e6187aaa562139fef6122e4834e7d4f2f3bbd67'
REQUIRED={'accepted_constructor_bundle.yaml','artifact_manifest.yaml','handoff_manifest.json'}
HEX=re.compile(r'^[0-9a-f]{64}$')
MAX_COMPRESSED=128*1024*1024
MAX_EXPANDED=512*1024*1024
MAX_MEMBERS=400
MAX_CONFIG=8*1024*1024
SHARE=Path('/srv/smb/In_Progress/data')

class Invalid(Exception): pass

def need(test, msg):
    if not test:raise Invalid(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def safe_name(s):
    if not isinstance(s,str) or not s or len(s)>320 or '\\' in s or '\x00' in s or s.startswith('/') or re.match('^[A-Za-z]:',s):return False
    pp=PurePosixPath(s)
    return all(p not in ('..','.') for p in pp.parts) and str(pp)==s.rstrip('/')
def load_yaml(b):
    need(yaml is not None,'PYYAML_REQUIRED')
    need(len(b)<=MAX_CONFIG,'CONFIG_TOO_BIG')
    return yaml.safe_load(b)
def info_base(p):return {'schema_version':SCHEMA,'file':p.name,'sha256':sha(p.read_bytes()),'status':'UNCLASSIFIED','job_ids':[],'checks':[],'warnings':[],'blockers':[],'native_dispatch':False,'production_ready':False}

def audit(path,policy='new',studio_pin=None):
    p=Path(path)
    need(p.is_file() and not p.is_symlink(),'REGULAR_ZIP_REQUIRED')
    need(p.stat().st_size<=MAX_COMPRESSED,'COMPRESSED_LIMIT_EXCEEDED')
    out=info_base(p)
    try:
        with zipfile.ZipFile(p) as z:
            infos=z.infolist();need(len(infos)<=MAX_MEMBERS,'MEMBER_LIMIT_EXCEEDED')
            seen=set();expanded=0
            for i in infos:
                need(safe_name(i.filename),'ZIP_UNSAFE_MEMBER')
                need(i.filename not in seen,'ZIP_DUPLICATE_MEMBER');seen.add(i.filename)
                expanded+=i.file_size
                need(expanded<=MAX_EXPANDED,'ZIP_EXPANSION_LIMIT')
                need(not bool(i.flag_bits&1),'ZIP_ENCRYPTED_ENTRY')
                mode=(i.external_attr>>16)&0o170000
                need(mode in (0,stat.S_IFREG,stat.S_IFDIR),'ZIP_SPECIAL_FILE')
            need(z.testzip() is None,'ZIP_CRC_FAIL')
            if REQUIRED <= seen:
                handoff(z,seen,out,policy,studio_pin)
            elif 'BLOCKERS.yaml' in seen or 'SERVER_INGEST_STAGING.yaml' in seen:
                out['status']='STAGING_BLOCKED_NOT_HANDOFF'
                out['checks'].append('STAGING_MARKERS_PRESENT')
                if 'BLOCKERS.yaml' in seen and yaml is not None:
                    blockers=load_yaml(z.read('BLOCKERS.yaml'))
                    if isinstance(blockers,dict):
                        out['blockers']=[x.get('code','UNKNOWN') for x in blockers.get('blockers',[]) if isinstance(x,dict)]
            elif 'creator_tasks.json' in seen or 'creator_task.yaml' in seen:
                out['status']='CREATOR_TASK_NOT_HANDOFF'
            else:
                out['status']='RAW_OR_UNKNOWN_INTAKE_ONLY'
    except (zipfile.BadZipFile,RuntimeError,EOFError) as e:
        raise Invalid('ZIP_INVALID_'+type(e).__name__) from e
    return out

def handoff(z,seen,out,policy,studio_pin):
    raw={k:z.read(k) for k in REQUIRED}
    for b in raw.values():need(len(b)<=MAX_CONFIG,'HANDOFF_CONFIG_LIMIT')
    envelope=json.loads(raw['handoff_manifest.json'])
    need(envelope.get('schema_version')=='gdl_intake_builder_handoff_v0_1','HANDOFF_SCHEMA')
    need(envelope.get('mode')=='REVIEW_ONLY','HANDOFF_REVIEW_ONLY_REQUIRED')
    need(envelope.get('accepted_bundle_file_sha256')==sha(raw['accepted_constructor_bundle.yaml']),'BUNDLE_FILE_SHA_MISMATCH')
    need(envelope.get('artifact_manifest_file_sha256')==sha(raw['artifact_manifest.yaml']),'ARTIFACT_FILE_SHA_MISMATCH')
    bundle=load_yaml(raw['accepted_constructor_bundle.yaml']);artifacts=load_yaml(raw['artifact_manifest.yaml'])
    need(isinstance(bundle,dict) and bundle.get('schema_version')=='gdl_greeting_card_accepted_constructor_bundle_v0_1','BUNDLE_SCHEMA')
    need(isinstance(artifacts,dict) and artifacts.get('schema_version')=='gdl_greeting_card_builder_artifact_manifest_v0_1','ARTIFACT_SCHEMA')
    review=bundle.get('intake_review');prov=bundle.get('provenance_manifest')
    need(isinstance(review,dict) and review.get('state')=='PASS' and review.get('basis')=='OPERATOR_REVIEWED_NORMALIZED_BATCH','REVIEW_PASS_EVIDENCE_REQUIRED')
    need(isinstance(review.get('review_id'),str) and review['review_id'] and isinstance(review.get('reviewer_source'),str) and review['reviewer_source'],'REVIEW_ID_REQUIRED')
    need(isinstance(prov,dict) and prov.get('algorithm')=='sha256_canonical_json_v0_1','BUNDLE_HASH_ALGORITHM')
    need(prov.get('source_batch_id')==bundle.get('source_batch_id')==review.get('source_batch_id'),'SOURCE_BATCH_REVIEW_MISMATCH')
    need(prov.get('intake_review_id')==review['review_id'],'PROVENANCE_REVIEW_ID_MISMATCH')
    expected=prov.get('bundle_sha256')
    need(isinstance(expected,str) and HEX.fullmatch(expected),'BUNDLE_CANONICAL_HASH_MISSING')
    prov['bundle_sha256']=''
    calc=sha(json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8'))
    need(calc==expected,'BUNDLE_CANONICAL_SHA_MISMATCH')
    prov['bundle_sha256']=expected
    am=artifacts.get('artifacts')
    need(isinstance(am,dict),'ARTIFACTS_FORMAT')
    for key,entry in am.items():
        need(isinstance(key,str) and isinstance(entry,dict),'ARTIFACT_ENTRY')
        path=entry.get('path');digest=entry.get('sha256')
        need(isinstance(path,str) and safe_name(path) and path.startswith('assets/') and path in seen,'ARTIFACT_PATH_UNSAFE_OR_MISSING')
        need(isinstance(digest,str) and HEX.fullmatch(digest) and sha(z.read(path))==digest,'ARTIFACT_SHA_MISMATCH')
    jobs=bundle.get('jobs')
    need(isinstance(jobs,list) and 1<=len(jobs)<=200,'JOBS_CARDINALITY')
    ids=set();legacy=[]
    for job in jobs:
        need(isinstance(job,dict),'JOB_NOT_OBJECT')
        j=job.get('job_id');need(isinstance(j,str) and re.fullmatch('[A-Za-z0-9_.-]{4,96}',j) and j not in ids,'JOB_ID_INVALID_OR_DUPLICATE')
        ids.add(j)
        for k in ('structured_greeting_data','exact_person_text_asset_bindings','accepted_visual_assets','branding_selection','signature_selection','builder_v1'):
            need(k in job,'JOB_MISSING_'+k.upper())
        g=job['structured_greeting_data'];b=job['builder_v1'];s=job['signature_selection']
        need(isinstance(g,dict) and isinstance(g.get('greeting_text'),str) and bool(g['greeting_text'].strip()),'GREETING_MISSING')
        need(isinstance(s,dict) and s.get('variant_id') in ('GRIGO','HERASYMENKO','DUAL_GRIGO_HERASYMENKO'),'SIGNATURE_UNKNOWN_REVIEW_REQUIRED')
        need(isinstance(b,dict) and b.get('schema_version')=='gdl_greeting_card_builder_payload_v0_1','BUILDER_PAYLOAD_SCHEMA')
        image=b.get('inside_image');need(isinstance(image,dict),'INSIDE_IMAGE_MISSING')
        mode=image.get('mode')
        if mode=='DEFAULT_ASSET':
            need(image.get('asset_id')==FLOWER_ID and image.get('asset_sha256')==FLOWER_SHA,'DEFAULT_FLOWERS_PIN_MISMATCH')
            need(image.get('accepted_artifact_ref') is None,'DEFAULT_ASSET_CREATOR_REF_FORBIDDEN')
        elif mode=='PORTRAIT':
            ref=image.get('accepted_artifact_ref');digest=image.get('asset_sha256')
            need(isinstance(ref,str) and ref in am and am[ref].get('sha256')==digest,'PORTRAIT_ARTIFACT_BINDING_MISMATCH')
            asset=am[ref]['path']
            if not asset.lower().endswith('.png'):
                legacy.append(j)
            else:
                # Format is not sufficient to attest actual transparent pixels or visual quality.
                try:
                    from PIL import Image
                    import io
                    im=Image.open(io.BytesIO(z.read(asset)))
                    if im.mode not in ('RGBA','LA') or 'A' not in im.getbands():legacy.append(j)
                    elif im.getchannel('A').getextrema()[0]>=255:legacy.append(j)
                except ImportError:out['warnings'].append('PIL_NOT_INSTALLED_ALPHA_UNVERIFIED')
                except Exception:raise Invalid('PORTRAIT_IMAGE_DECODE_FAILED')
        else:raise Invalid('UNSUPPORTED_INSIDE_IMAGE_MODE')
        out['job_ids'].append(j)
    out['checks']+=['ZIP_CRC_PASS','HANDOFF_ENVELOPE_HASHES_PASS','CANONICAL_BUNDLE_HASH_PASS','ARTIFACT_BYTES_SHA_PASS','REVIEW_FIELDS_PRESENT_NOT_INDEPENDENTLY_ATTESTED','ALL_JOBS_SEMANTIC_SHAPE_PASS']
    if studio_pin:
        need(isinstance(studio_pin,str) and HEX.fullmatch(studio_pin),'STUDIO_PIN_INVALID')
        out['studio_pin_match']=(studio_pin==out['sha256'])
    if legacy:
        out['warnings'].append('PORTRAIT_REQUIRE_NEW_RGBA_REVIEW:'+','.join(legacy))
        out['status']='HANDOFF_LEGACY_PORTRAIT_REVIEW_REQUIRED'
    else:
        out['status']='HANDOFF_STRUCTURAL_PASS_STUDIO_BINDING_REQUIRED'
    out['warnings'].append('MANIFEST_REVIEW_SELF_DECLARATION_NOT_OPERATOR_ATTESTATION')
    out['warnings'].append('PHASE2_DYNAMIC_STUDIO_INTAKE_NOT_WIRED')

def client_input_dir(client):
    need(isinstance(client,str) and 0<len(client)<=160 and client not in ('.','..') and not any(x in client for x in ('/','\\','\x00')),'CLIENT_NAME_INVALID')
    candidate=SHARE/client/'_forprint_automation'/'input'
    for path in (SHARE,SHARE/client,SHARE/client/'_forprint_automation',candidate):
        need(path.is_dir() and not path.is_symlink(),'CLIENT_INPUT_PATH_MISSING_OR_UNSAFE')
    need(candidate.resolve().parents[2]==SHARE.resolve(),'CLIENT_INPUT_ESCAPED_SHARE')
    return candidate

def main(argv=None):
    ap=argparse.ArgumentParser(description='Studio Intake phase1 read-only ZIP audit: never launches Illustrator')
    x=ap.add_mutually_exclusive_group(required=True)
    x.add_argument('--file',type=Path)
    x.add_argument('--input-dir',type=Path)
    x.add_argument('--client-name',default=None)
    ap.add_argument('--policy',choices=('new','legacy'),default='new')
    ap.add_argument('--studio-accepted-sha',default=None)
    opt=ap.parse_args(argv)
    try:
        if opt.file: paths=[opt.file]
        else:
            d=client_input_dir(opt.client_name) if opt.client_name is not None else opt.input_dir
            need(d.is_dir() and not d.is_symlink(),'INPUT_DIRECTORY_REQUIRED')
            paths=sorted(x for x in d.iterdir() if x.is_file() and not x.is_symlink() and x.name.lower().endswith('.zip'))
            need(len(paths)<=200,'INPUT_ARCHIVE_COUNT_LIMIT')
        for p in paths:
            try:
                result=audit(p,opt.policy,opt.studio_accepted_sha)
            except Exception as e:
                result={'schema_version':SCHEMA,'file':p.name,'status':'ZIP_REJECTED','blockers':[str(e) if isinstance(e,Invalid) else type(e).__name__],'native_dispatch':False,'production_ready':False}
            print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        if not paths:print(json.dumps({'schema_version':SCHEMA,'status':'NO_ZIPS_IN_INPUT','native_dispatch':False},sort_keys=True))
        return 0
    except Invalid as e:
        print('STUDIO_INTAKE_AUDIT_BLOCKED='+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
