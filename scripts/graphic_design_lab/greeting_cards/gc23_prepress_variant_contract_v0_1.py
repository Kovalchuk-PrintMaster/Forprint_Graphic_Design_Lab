#!/usr/bin/env python3
"""GC23 v0.1: project-owned, source-pinned greeting-card variant preflight.

Read-only contract adapter, not an Illustrator/PDF renderer and not a production
release. GDL carries a versioned source snapshot and does not import Prepress
Hub Python at runtime. Private bytes are checked, never published or logged.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json'
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
REV_RE = re.compile(r'^r[0-9]{3}$')
BLOCKED_TEXT = re.compile(r'\b(?:sanitized|placeholder|synthetic|lorem\s+ipsum)\b', re.IGNORECASE)


class GateError(ValueError):
    """Safe machine code, never private source details."""


def need(condition: bool, code: str) -> None:
    if not condition:
        raise GateError(code)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def load_mapping(path: Path) -> dict[str, Any]:
    need(path.is_file() and not path.is_symlink(), 'INPUT_NOT_REGULAR')
    need(path.stat().st_size <= 20_000_000, 'INPUT_TOO_LARGE')
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding='utf8'))
    else:
        data = yaml.safe_load(path.read_text(encoding='utf8'))
    need(isinstance(data, dict), 'INPUT_MAPPING_REQUIRED')
    return data


def catalog(path: Path = CATALOG) -> dict[str, Any]:
    source = load_mapping(path)
    need(source.get('schema_version') == 'forprint_gdl_gc23_variant_contract_v0_1', 'CATALOG_SCHEMA')
    need(source['physical_order'] == ['P01_FRONT', 'P02_BACK', 'P03_INSIDE_IMAGE', 'P04_GREETING'], 'PAGE_ORDER')
    need(source['physical_size_mm'] == [214,301], 'MEDIA_GEOMETRY')
    need(source['p04_greeting_bbox_pdf_mm'] == [32,32,182,212], 'GREETING_150X180')
    need(set(source['front_variants']) == {'STANDARD','RECIPIENT_BRANDING_OVERLAY','BILINGUAL_OCCASION'}, 'FRONT_FAMILY_SET')
    need(set(source['photo_variants']) == {'PORTRAIT','DEFAULT_ASSET'}, 'PHOTO_FAMILY_SET')
    need(set(source['signature_variants']) == {'GRIGO','HERASYMENKO','DUAL_GRIGO_HERASYMENKO'}, 'SIGNATURE_FAMILY_SET')
    need(source['authorities']['illustrator_parity_proven'] is False, 'PARITY_AUTHORITY')
    for item in source['source_file_digests'].values():
        need(bool(SHA_RE.fullmatch(item)), 'SOURCE_DIGEST_INVALID')
    return source


def verify_source(source_root: Path, snap: dict[str, Any]) -> int:
    need(source_root.is_dir() and not source_root.is_symlink(), 'SOURCE_ROOT_MISSING')
    count = 0
    for rel, digest in snap['source_file_digests'].items():
        need(not Path(rel).is_absolute() and '..' not in Path(rel).parts, 'SOURCE_PATH_INVALID')
        p = source_root / rel
        need(p.is_file() and not p.is_symlink(), 'SOURCE_FILE_MISSING')
        need(sha_file(p) == digest, 'PINNED_SOURCE_MISMATCH')
        count += 1
    zones = load_mapping(source_root / 'coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml')
    observed = zones['pages']['physical_4']['zones']['inside_text.greeting']['bbox_pdf_mm']
    need(observed == snap['p04_greeting_bbox_pdf_mm'], 'SOURCE_P04_BBOX_MISMATCH')
    skeleton = load_mapping(source_root / 'coordination/graphic_design_lab/directions/greeting_cards/product_skeleton_v0_1.yaml')
    front = {x['id']: x for x in skeleton['variant_model']['front']['semantic_families']}
    for name, variant in snap['front_variants'].items():
        need(front[name]['sender_logo_bbox_mm'] == variant['sender_logo_bbox_mm'], 'SOURCE_FRONT_LOGO_BBOX_MISMATCH')
        need(front[name]['occasion_bbox_mm'] == variant['occasion_bbox_mm'], 'SOURCE_FRONT_OCCASION_BBOX_MISMATCH')
    signatures = load_mapping(source_root / 'coordination/graphic_design_lab/directions/greeting_cards/signature_variant_catalog_v0_1.yaml')
    need({x['variant_id'] for x in signatures['variants']} == set(snap['signature_variants']), 'SOURCE_SIGNATURE_CATALOG_MISMATCH')
    return count


def canonical_bundle_sha(bundle: Mapping[str, Any]) -> str:
    """Byte-compatible with Prepress Hub compute_bundle_sha256 v0.1."""
    payload = deepcopy(dict(bundle))
    provenance = mapping(payload.get('provenance_manifest'))
    provenance['bundle_sha256'] = ''
    payload['provenance_manifest'] = provenance
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf8')
    return hashlib.sha256(encoded).hexdigest()


def resolve_private(value: Any, source_root: Path) -> Path:
    need(isinstance(value, str) and bool(value.strip()) and '\x00' not in value, 'PRIVATE_PATH_MISSING')
    p = Path(value).expanduser()
    return (p if p.is_absolute() else source_root / p).resolve()


def private_resource(res: dict[str, Any], logical_id: str, source_root: Path, expected_sha: str) -> str:
    info = mapping(res.get(logical_id))
    p = resolve_private(info.get('path'), source_root)
    need(p.is_file() and not p.is_symlink(), 'PRIVATE_RESOURCE_UNAVAILABLE')
    need(sha_file(p) == expected_sha, 'PRIVATE_RESOURCE_SHA_MISMATCH')
    if info.get('sha256') is not None:
        need(info['sha256'] == expected_sha, 'RESOURCE_MANIFEST_SHA_MISMATCH')
    return expected_sha


def bound_artifact(art: dict[str, Any], ref: Any, asset_id: Any, digest: Any, source_root: Path) -> str:
    need(isinstance(ref, str) and bool(ref), 'ARTIFACT_REF_MISSING')
    need(isinstance(asset_id, str) and bool(asset_id), 'ARTIFACT_ID_MISSING')
    need(isinstance(digest, str) and SHA_RE.fullmatch(digest) is not None, 'ARTIFACT_SHA_INVALID')
    item = mapping(mapping(art.get('artifacts')).get(ref))
    need(item.get('source_asset_id') == asset_id and item.get('sha256') == digest, 'ARTIFACT_BINDING_MISMATCH')
    p = resolve_private(item.get('path'), source_root)
    need(p.is_file() and not p.is_symlink(), 'ARTIFACT_FILE_MISSING')
    need(sha_file(p) == digest, 'ARTIFACT_FILE_SHA_MISMATCH')
    return digest


def check_text(value: Any, which: str) -> None:
    need(isinstance(value, str) and bool(value.strip()), which+'_MISSING')
    need(not BLOCKED_TEXT.search(value), which+'_SANITIZED_OR_PLACEHOLDER')
    need(len(value) <= 20000, which+'_TOO_LARGE')


def projection(inputs_config: Path, source_root: Path, snap: dict[str, Any]) -> dict[str, Any]:
    config = load_mapping(inputs_config)
    need(set(config) == {'bundle','resource_manifest','artifact_manifest'}, 'INPUTS_CONFIG_KEYS')
    raw = {name:resolve_private(config[name],source_root) for name in config}
    bundle = load_mapping(raw['bundle'])
    resources = load_mapping(raw['resource_manifest'])
    artifacts = load_mapping(raw['artifact_manifest'])
    need(artifacts.get('schema_version') == 'gdl_greeting_card_builder_artifact_manifest_v0_1', 'ARTIFACT_MANIFEST_SCHEMA')
    res = mapping(resources.get('resources'))
    need(resources.get('schema_version') == 'gdl_greeting_card_private_resource_manifest_v0_1', 'RESOURCE_MANIFEST_SCHEMA')
    hashes = {}
    for mode in ('reference_pdf','front_font','greeting_font'):
        hashes[mode] = private_resource(res,snap['resource_ids'][mode],source_root,snap['pinned_sha256'][mode])
    provenance = mapping(bundle.get('provenance_manifest'))
    need(provenance.get('algorithm') == 'sha256_canonical_json_v0_1', 'BUNDLE_PROVENANCE_ALGORITHM')
    need(provenance.get('bundle_sha256') == canonical_bundle_sha(bundle), 'BUNDLE_PROVENANCE_SHA_MISMATCH')
    jobs = bundle.get('jobs')
    need(isinstance(jobs, list) and bool(jobs), 'NO_JOBS')
    need(len(jobs) <= 50, 'TOO_MANY_JOBS')
    plans=[]
    for idx, raw_job in enumerate(jobs):
        job = mapping(raw_job)
        payload = mapping(job.get('builder_v1'))
        need(payload.get('schema_version') == 'gdl_greeting_card_builder_payload_v0_1', 'BUILDER_PAYLOAD_SCHEMA')
        need(isinstance(payload.get('revision'),str) and REV_RE.fullmatch(payload['revision']) is not None, 'REVISION_INVALID')
        front = mapping(payload.get('front'))
        image = mapping(payload.get('inside_image'))
        sender = mapping(payload.get('sender_text'))
        fam, mode, sig = front.get('family'),image.get('mode'),sender.get('signature_variant_id')
        need(isinstance(fam, str) and fam in snap['front_variants'], 'FRONT_FAMILY_UNKNOWN')
        need(isinstance(mode, str) and mode in snap['photo_variants'], 'IMAGE_MODE_UNKNOWN')
        need(isinstance(sig, str) and sig in snap['signature_variants'], 'SIGNATURE_VARIANT_UNKNOWN')
        need(mapping(job.get('signature_selection')).get('variant_id') == sig, 'SIGNATURE_SELECTION_MISMATCH')
        need(mapping(front.get('occasion')).get('kind') == mapping(job.get('structured_greeting_data')).get('occasion'), 'OCCASION_KIND_MISMATCH')
        check_text(mapping(front.get('occasion')).get('display_text'), 'OCCASION_TEXT')
        check_text(mapping(job.get('structured_greeting_data')).get('greeting_text'), 'GREETING_TEXT')
        branding = mapping(job.get('branding_selection'))
        if fam == 'RECIPIENT_BRANDING_OVERLAY':
            need(branding.get('presence') == 'PRESENT', 'BRANDING_SELECTION_MISSING')
            logo=mapping(front.get('recipient_branding'))
            exact=mapping(mapping(job.get('exact_person_text_asset_bindings')).get('recipient_branding'))
            need(exact.get('source_asset_id') == logo.get('asset_id') == branding.get('source_asset_id'), 'BRANDING_SOURCE_MISMATCH')
            bound_artifact(artifacts,logo.get('accepted_artifact_ref'),logo.get('asset_id'),logo.get('asset_sha256'),source_root)
        else:
            need(branding.get('presence') != 'PRESENT' and front.get('recipient_branding') is None, 'UNEXPECTED_RECIPIENT_BRANDING')
        exact_portrait=mapping(mapping(job.get('exact_person_text_asset_bindings')).get('portrait'))
        need(exact_portrait.get('source_asset_id') == image.get('asset_id'), 'PORTRAIT_EXACT_BINDING_MISMATCH')
        visuals = job.get('accepted_visual_assets')
        need(isinstance(visuals,list) and len(visuals) == 1, 'ACCEPTED_VISUAL_REQUIRED')
        visual = mapping(visuals[0])
        need(visual.get('acceptance_basis') in {'CREATOR_INTERNAL_REVIEW_PASS','SOURCE_ASSET_OPERATOR_REVIEW_PASS'}, 'VISUAL_ACCEPTANCE_BASIS')
        if mode == 'PORTRAIT':
            need(visual.get('artifact_ref') == image.get('accepted_artifact_ref'), 'PORTRAIT_VISUAL_REF_MISMATCH')
            if visual.get('acceptance_basis') == 'SOURCE_ASSET_OPERATOR_REVIEW_PASS':
                need(visual.get('provenance_sha256') == image.get('asset_sha256'), 'PORTRAIT_VISUAL_SHA_MISMATCH')
            bound_artifact(artifacts,image.get('accepted_artifact_ref'),image.get('asset_id'),image.get('asset_sha256'),source_root)
        else:
            need(visual.get('acceptance_basis') == 'SOURCE_ASSET_OPERATOR_REVIEW_PASS', 'FLOWERS_OPERATOR_REVIEW_REQUIRED')
            need(visual.get('provenance_sha256') == image.get('asset_sha256')
                 and visual.get('source_asset_id') == image.get('asset_id'), 'FLOWERS_VISUAL_BINDING_MISMATCH')
            expected=snap['photo_variants']['DEFAULT_ASSET']
            need(image.get('asset_id') == expected['asset_id'] and image.get('asset_sha256') == expected['sha256'] and image.get('accepted_artifact_ref') is None,'DEFAULT_FLOWERS_IDENTITY_MISMATCH')
            private_resource(res,snap['resource_ids']['flowers'],source_root,expected['sha256'])
        signature_spec=snap['signature_variants'][sig]
        private_resource(res,signature_spec['source_id'],source_root,signature_spec['source_sha256'])
        variants=[snap['front_variants'][fam]['runtime'],snap['photo_variants'][mode]['runtime'],signature_spec['runtime']]
        general=all(v=='STANDARD_RUNTIME_LIST' for v in variants)
        plans.append({
            'job_index':idx, 'revision':payload['revision'],
            'front_family':fam, 'inside_image_mode':mode, 'signature_variant':sig,
            'gate':'CONTRACT_VALID_RUNTIME_FAMILY' if general else 'CONTRACT_VALID_SEPARATE_SOURCE_RUNTIME_REVIEW',
            'p01_sender_logo_bbox_pdf_mm':snap['front_variants'][fam]['sender_logo_bbox_mm'],
            'p01_occasion_bbox_pdf_mm':snap['front_variants'][fam]['occasion_bbox_mm'],
            'p01_recipient_logo_zone_pdf_mm':snap['front_variants'][fam]['recipient_branding_zone_mm'],
            'p04_greeting_bbox_pdf_mm':snap['p04_greeting_bbox_pdf_mm'],
            'requires_actual_design_visual_review':True,
            'illustrator_execution_authorized':False,
        })
    return {'schema_version':'gdl_gc23_variant_projection_v0_1','source_commit':snap['source_closed_commit'],
       'input_sha256':{key:sha_file(path) for key,path in raw.items()},
       'source_pinned_resource_sha256':hashes,'jobs':plans,
       'native_illustrator_parity_verified':False,'production_ready':False,
       'client_published':False,'private_text_in_projection':False}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=['catalog','source-check','preflight'],required=True)
    p.add_argument('--catalog',type=Path,default=CATALOG)
    p.add_argument('--prepress-root',type=Path)
    p.add_argument('--inputs-config',type=Path)
    p.add_argument('--source-root',type=Path)
    p.add_argument('--output-json',type=Path,help='Optional new output inside GDL tmp/; no overwrite')
    a=p.parse_args()
    try:
        snap=catalog(a.catalog)
        if a.mode=='catalog':
            for field in ('front_variants','photo_variants','signature_variants'):
                for key,v in snap[field].items():
                    print('GC23_VARIANT='+field+':'+key+':'+v['runtime'])
            print('GC23_GREETING_BBOX='+str(snap['p04_greeting_bbox_pdf_mm']))
            print('GDL_GC23_VARIANT_CATALOG=PASS')
        elif a.mode=='source-check':
            need(a.prepress_root is not None, 'PREPRESS_ROOT_REQUIRED')
            n=verify_source(a.prepress_root,snap)
            print('GC23_PINNED_SOURCE_FILE_COUNT='+str(n))
            print('GDL_GC23_SOURCE_PARITY=PASS_READ_ONLY')
        else:
            need(a.inputs_config is not None and a.source_root is not None, 'PRIVATE_INPUTS_REQUIRED')
            doc=projection(a.inputs_config,a.source_root,snap)
            if a.output_json is not None:
                target=a.output_json.resolve(strict=False)
                tmp=(ROOT/'tmp').resolve()
                need(target.is_relative_to(tmp) and not target.exists(), 'OUTPUT_MUST_BE_NEW_UNDER_GDL_TMP')
                need(target.parent.is_dir() and not target.parent.is_symlink(), 'OUTPUT_PARENT_MISSING')
                with target.open('x',encoding='utf8') as stream:
                    json.dump(doc,stream,ensure_ascii=False,sort_keys=True,indent=2)
                    stream.write('\n')
            for job in doc['jobs']:
                print('GC23_JOB_INDEX='+str(job['job_index'])+' GATE='+job['gate']+' FRONT='+job['front_family']+' IMAGE='+job['inside_image_mode']+' SIGNATURE='+job['signature_variant'])
            print('GC23_JOBS='+str(len(doc['jobs'])))
            print('GDL_GC23_VARIANT_PREFLIGHT=PASS_REVIEW_ONLY')
        return 0
    except (GateError, KeyError, TypeError, yaml.YAMLError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        code=str(exc) if isinstance(exc,GateError) else type(exc).__name__
        print('GDL_GC23_VARIANT_CONTRACT=BLOCKED reason='+code,file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
