#!/usr/bin/env python3
"""Deterministic, source-pinned ForPrint Intake instruction ZIP export.

One canonical source in Studio repo; output belongs to private client automation folder.
Never launches Illustrator, never promotes received files to native/production PASS.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
INTAKE = ROOT/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'
CATALOG = INTAKE/'intake_instruction_catalog_v1.json'
SHARE = Path('/srv/smb/In_Progress/data')
OUTPUT_DIR_CANONICAL = 'intake_instruction'
PACKAGE_PREFIX = 'ForPrint_Intake_Instruction'
SCHEMA = 'forprint_studio_intake_instruction_export_v1'
MAX_SOURCE_SIZE = 2*1024*1024
MAX_PAYLOAD = 12*1024*1024
HEX = re.compile(r'[0-9a-f]{64}')
ID = re.compile(r'[a-z][a-z0-9_]{2,64}')
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')

class Blocked(RuntimeError):
    pass

def require(condition, reason):
    if not condition:
        raise Blocked(reason)

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def regular(path):
    try:
        return stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink()
    except OSError:
        return False

def directory(path):
    try:
        return stat.S_ISDIR(path.lstat().st_mode) and not path.is_symlink()
    except OSError:
        return False

def valid_client(client):
    return (isinstance(client,str) and 0<len(client)<=160 and client.strip()==client
            and client not in ('.','..') and not any(c in client for c in ('/','\\','\0')))

def load_catalog(root=ROOT):
    folder = root/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'
    path = folder/'intake_instruction_catalog_v1.json'
    require(regular(path) and path.stat().st_size<=131072,'CATALOG_NOT_REGULAR_OR_TOO_LARGE')
    data=json.loads(path.read_text(encoding='utf8'))
    require(data.get('schema_version')=='forprint_studio_intake_instruction_catalog_v1','CATALOG_SCHEMA')
    rows=data.get('recipes')
    require(isinstance(rows,list) and 1<=len(rows)<=16,'RECIPE_COUNT_INVALID')
    unique=set();active=0
    for row in rows:
        require(isinstance(row,dict),'RECIPE_NOT_OBJECT')
        ident=row.get('recipe_id');version=row.get('version')
        require(isinstance(ident,str) and ID.fullmatch(ident),'RECIPE_ID_INVALID')
        require(isinstance(version,str) and VERSION.fullmatch(version),'RECIPE_VERSION_INVALID')
        require((ident,version) not in unique,'RECIPE_DUPLICATE');unique.add((ident,version))
        require(row.get('status') in ('ACTIVE','EXPERIMENTAL','RETIRED'),'RECIPE_STATUS_INVALID')
        active+=int(row['status']=='ACTIVE')
        content=row.get('content')
        require(isinstance(content,list) and 4<=len(content)<=40,'RECIPE_CONTENT_INVALID')
        seen=set();total=0
        for entry in content:
            require(isinstance(entry,dict),'ENTRY_NOT_OBJECT')
            source=entry.get('source');target=entry.get('package_path');digest=entry.get('sha256')
            require(isinstance(source,str) and isinstance(target,str),'RECIPE_PATH_TYPE')
            for name in (source,target):
                p=PurePosixPath(name)
                require(len(name)<=220 and not name.startswith('/') and '\\' not in name and
                        p.parts and all(x not in ('..','.') for x in p.parts) and str(p)==name,
                        'RECIPE_PATH_UNSAFE')
            require(source==target and target not in seen,'RECIPE_SOURCE_OR_PACKAGE_PATH_COLLISION')
            require(target!='RELEASE_INFO.json' and target!='SHA256SUMS','RESERVED_PACKAGE_PATH')
            seen.add(target)
            require(isinstance(digest,str) and HEX.fullmatch(digest),'RECIPE_DIGEST_INVALID')
            f=folder/source
            require(regular(f) and f.stat().st_size<=MAX_SOURCE_SIZE,'CANONICAL_FILE_MISSING_OR_UNSAFE_'+source)
            blob=f.read_bytes();require(sha(blob)==digest,'CANONICAL_SOURCE_DRIFT_VERSION_BUMP_REQUIRED_'+source)
            total+=len(blob);require(total<=MAX_PAYLOAD,'RECIPE_BYTES_LIMIT')
        require('00_START_HERE_UA.md' in seen and
                any(x.startswith('INTAKE_OPERATOR_PROMPT_UA_') and x.endswith('.md') for x in seen) and
                any(x.startswith('intake_interface_contract_') and x.endswith('.json') for x in seen),
                'RECIPE_CORE_FILES_MISSING')
        require(any(s.startswith('reference_contracts/') for s in seen),'REFERENCE_CONTRACTS_MISSING')
    require(active==1,'SINGLE_ACTIVE_RECIPE_REQUIRED')
    return rows

def choose_recipe(rows,requested=None):
    if requested is None:
        return next(x for x in rows if x['status']=='ACTIVE')
    row=next((x for x in rows if x['recipe_id']+'@'+x['version']==requested),None)
    require(row is not None,'RECIPE_NOT_FOUND')
    require(row['status']!='RETIRED','RECIPE_RETIRED')
    return row

def zip_member(name,blob):
    info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    info.external_attr=(0o100644<<16)
    info.create_system=3
    return info,blob

def render(root,recipe):
    folder=root/'coordination/graphic_design_lab/greeting_cards/illustrator_studio/intake'
    blobs={e['package_path']:(folder/e['source']).read_bytes() for e in recipe['content']}
    fingerprint=sha(json.dumps({'id':recipe['recipe_id'],'version':recipe['version'],
                'files':{k:sha(v) for k,v in sorted(blobs.items())}},
                ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('ascii'))
    release={'schema_version':SCHEMA,'recipe_id':recipe['recipe_id'],
             'recipe_version':recipe['version'],'status':recipe['status'],
             'source_fingerprint_sha256':fingerprint,
             'purpose':'INTAKE_INSTRUCTION_ONLY_NOT_AN_ACCEPTED_CUSTOMER_HANDOFF',
             'native_dispatch':False,'production_ready':False,
             'content_sha256':{k:sha(v) for k,v in sorted(blobs.items())}}
    blobs['RELEASE_INFO.json']=(json.dumps(release,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    sums=''.join(f'{sha(v)}  {k}\n' for k,v in sorted(blobs.items()))
    blobs['SHA256SUMS']=sums.encode('ascii')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,blob in sorted(blobs.items()):
            info,data=zip_member(name,blob)
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    return stream.getvalue(),fingerprint

def client_folder(share,client,create=False):
    require(valid_client(client),'CLIENT_NAME_INVALID')
    require(directory(share),'SHARE_ROOT_NOT_DIRECTORY')
    root=share/client;automation=root/'_forprint_automation'
    require(directory(root) and directory(automation),'CLIENT_AUTOMATION_ROOT_MISSING_OR_UNSAFE')
    # Respect an existing client-level folder (or automation subfolder); never create a duplicate.
    matches=[p for parent in (root,automation) for p in parent.iterdir()
             if re.sub('[^a-z0-9]','',p.name.casefold())=='intakeinstruction']
    require(len(matches)<=1,'MULTIPLE_INTAKE_INSTRUCTION_DIRECTORIES')
    dest=matches[0] if matches else automation/OUTPUT_DIR_CANONICAL
    require(not dest.is_symlink(),'INSTRUCTION_DIR_SYMLINK')
    if create and not dest.exists():dest.mkdir(mode=0o750)
    require((not dest.exists() and not create) or directory(dest),'INSTRUCTION_DIR_UNSAFE')
    return dest

def outfile_name(recipe,fingerprint):
    return f'{PACKAGE_PREFIX}_{recipe["recipe_id"]}_v{recipe["version"].replace(".","_")}_{fingerprint[:12]}.zip'

def generate(root,share,client,requested=None):
    rows=load_catalog(root)
    recipe=choose_recipe(rows,requested)
    payload,fingerprint=render(root,recipe)
    target=client_folder(share,client,True)/outfile_name(recipe,fingerprint)
    require(not target.is_symlink(),'PACKAGE_DEST_SYMLINK')
    if target.exists():
        require(regular(target) and sha(target.read_bytes())==sha(payload),'EXISTING_PACKAGE_CONFLICT_OR_TAMPER')
        action='REUSED_VERIFIED_UNCHANGED'
    else:
        fd,temp=tempfile.mkstemp(dir=target.parent,prefix='.forprint_intake_')
        try:
            with os.fdopen(fd,'wb') as stream:
                stream.write(payload);stream.flush();os.fsync(stream.fileno())
            os.chmod(temp,0o640)
            require(not target.exists(),'CONCURRENT_PACKAGE_TARGET_CONFLICT')
            os.replace(temp,target)
        finally:
            if os.path.lexists(temp):os.unlink(temp)
        action='NEW_IMMUTABLE_PACKAGE'
    print('STUDIO_INTAKE_INSTRUCTION='+action)
    print('RECIPE='+recipe['recipe_id']+'@'+recipe['version'])
    print('PACKAGE='+str(target))
    print('PACKAGE_SHA256='+sha(payload))
    print('RECIPE_FINGERPRINT_SHA256='+fingerprint)
    print('NATIVE_LAUNCHED=FALSE PRODUCTION_READY=FALSE')
    return target

def verify_client(root,share,client):
    rows=load_catalog(root)
    dest=client_folder(share,client,False)
    require(directory(dest),'INSTRUCTION_DIR_MISSING')
    for recipe in rows:
        if recipe['status']=='RETIRED':continue
        blob,fingerprint=render(root,recipe)
        p=dest/outfile_name(recipe,fingerprint)
        if p.exists():
            require(regular(p) and sha(p.read_bytes())==sha(blob),'INSTRUCTION_PACKAGE_CHANGED_'+p.name)
            print('STUDIO_INTAKE_INSTRUCTION_VERIFY=PASS '+p.name)
    return 0

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('list','check','generate','verify-client'))
    ap.add_argument('--client-name')
    ap.add_argument('--recipe')
    opt=ap.parse_args(argv)
    try:
        rows=load_catalog()
        if opt.mode=='list':
            for r in rows:
                print('STUDIO_INTAKE_RECIPE='+r['recipe_id']+'@'+r['version']+' STATUS='+r['status'])
            return 0
        if opt.mode=='check':
            print('STUDIO_INTAKE_INSTRUCTION_SOURCE=PASS '+str(len(rows))+' recipes')
            print('STUDIO_INTAKE_INSTRUCTION_NATIVE=NOT_WIRED')
            return 0
        require(bool(opt.client_name),'CLIENT_NAME_REQUIRED')
        if opt.mode=='generate':generate(ROOT,SHARE,opt.client_name,opt.recipe)
        else:verify_client(ROOT,SHARE,opt.client_name)
        return 0
    except (Blocked,ValueError,KeyError,OSError,zipfile.BadZipFile) as e:
        print('STUDIO_INTAKE_INSTRUCTION_BLOCKED='+str(e)[:220],file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
