#!/usr/bin/env python3
"""GC32: single-root worker bootstrap and HTML infrastructure passport.

No legacy cleanup; no old PDF reads; publication only with explicit confirmation.
Unregistered changes cause WARNING, never silent acceptance or policy mutation.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
MAP_REL='coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
PS_REL='scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_worker_v0_1.ps1'
CMD_REL='scripts/graphic_design_lab/greeting_cards/windows/Запустити_виконавця.cmd'
PORTAL_REL='scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py'
ATLAS_REL='scripts/graphic_design_lab/greeting_cards/gc32_structure_atlas_v0_1.py'
SHARE_ROOT=Path('/srv/smb/In_Progress/data')
TARGET_REL='template_studio/worker_bootstrap/gc32_prepress_worker_v0_1.ps1'
class Blocked(ValueError): pass

def need(cond,code):
    if not cond:raise Blocked(code)

def regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError:return False

def directory(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError:return False

def sha(data):return sha256(data).hexdigest()

def registry(root=ROOT):
    p=root/MAP_REL
    need(regular(p),'GC32_MAP_MISSING')
    d=json.loads(p.read_text('utf8'))
    need(d.get('schema_version')=='forprint_gdl_gc32_infrastructure_map_v0_1','GC32_MAP_SCHEMA')
    need(d['worker']['machine']=='PREPRESS' and d['worker']['user']=='Work','GC32_BOUND_WORKER_DRIFT')
    need(d['worker']['root_hint_verified'] is True and d['worker']['root_hint']==r'D:\ForPrint_Automation\GraficsDesignLab\Automation','GC32_WINDOWS_ROOT_NOT_VERIFIED')
    for part in ('worker','client','workflow','coverage','progress','boundaries'):
        need(part in d,'GC32_SECTION_MISSING_'+part)
    need(d['coverage']['policy'].startswith('WARNING_ONLY'),'GC32_POLICY_INVALID')
    return d

def watch_family(path):
    if not path.startswith(('scripts/graphic_design_lab/','tests/graphic_design_lab/','coordination/graphic_design_lab/')):return None
    n=Path(path).name
    m=re.match(r'(gc\d{2})(?:_|-)',n)
    if m and int(m.group(1)[2:])>=27:return m.group(1)
    if ('template_studio/' in path or n.startswith(('ts01_','ts02_','ts_full_'))):return 'ts'
    return None

def audit(root=ROOT,meta=None):
    if meta is None:meta=registry(root)
    report=[]; detected=[]
    # Files not committed yet are still included. No filesystem traversal outside repo.
    try:
        p=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=8)
        detected=[x for x in p.stdout.decode('utf8','replace').split('\0') if x]
    except (OSError,subprocess.SubprocessError):
        report.append('GIT_INVENTORY_UNAVAILABLE: перевірено тільки обов’язкові файли')
    supported=set(meta['coverage']['watched_families'])
    unknown=sorted({watch_family(x) for x in detected if watch_family(x) and watch_family(x) not in supported})
    for x in unknown:report.append('UNREGISTERED_MODULE '+x+': додати до паспорта інфраструктури')
    make=root/'Makefile'
    if regular(make):
        m=make.read_text('utf8')
        for x in meta['coverage']['required_make_targets']:
            if re.search(r'(?m)^'+re.escape(x)+r':',m) is None:report.append('UNDOCUMENTED_MAKE_TARGET_MISSING '+x)
    else:report.append('MAKEFILE_UNAVAILABLE')
    for x in (MAP_REL,PS_REL,PORTAL_REL):
        if not regular(root/x):report.append('MISSING_DOCUMENTED_FILE '+x)
    try:
        r=subprocess.run(['git','status','--porcelain','--untracked-files=all'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=8)
        changes=[line[3:] for line in r.stdout.decode('utf8','replace').splitlines() if len(line)>=4]
        observed=[x for x in changes if watch_family(x) and x!=MAP_REL]
        if observed and MAP_REL not in changes:
            report.append('DOC_SYNC_REQUIRED: змінено контрольовані файли без оновлення gc32_infrastructure_map_v0_1.json')
    except (OSError,subprocess.SubprocessError):pass
    return {'status':'WARN' if report else 'OK','warnings':report,'audited_families':sorted(supported),'warning_only':True}

def workspace(client,share_root=SHARE_ROOT):
    need(bool(client) and client not in ('.','..') and '/' not in client and '\\' not in client,'GC32_CLIENT_NAME_INVALID')
    need(directory(share_root),'GC32_SHARE_ROOT_UNAVAILABLE')
    p=share_root/client/'_forprint_automation'
    for d in (p,p/'input',p/'output',p/'template_studio'):
        need(directory(d),'GC32_CLIENT_WORKSPACE_MISSING_OR_SYMLINK')
    return p

def worker_bootstrap(root,ws,confirm=False):
    target_dir=ws/'template_studio'/'worker_bootstrap'
    if target_dir.exists() or target_dir.is_symlink():
        need(directory(target_dir),'GC32_EXISTING_BOOTSTRAP_DIR_UNSAFE')
    elif confirm:
        need(directory(target_dir.parent),'GC32_BOOTSTRAP_PARENT_INVALID')
        target_dir.mkdir(mode=0o750)
    wanted={}
    for rel in (PS_REL,CMD_REL):
        src=root/rel
        need(regular(src),'GC32_WORKER_SOURCE_MISSING')
        raw=src.read_bytes()
        if rel==PS_REL:
            need(raw.startswith(b'\xef\xbb\xbf') and b'$env:LOCALAPPDATA' not in raw,'GC32_WORKER_SOURCE_INVALID')
        tgt=target_dir/src.name
        if tgt.exists() or tgt.is_symlink():
            need(regular(tgt),'GC32_EXISTING_BOOTSTRAP_UNSAFE')
        wanted[tgt]=raw
    old_worker_sha='6c5d7142206bb497043ee834e5a79c366979e4f81650aba595f4e6c4c5715113'
    missing=[];upgrade=[]
    for target,data in wanted.items():
        if not target.exists():missing.append(target);continue
        need(regular(target),'GC32_EXISTING_BOOTSTRAP_UNSAFE')
        if target.read_bytes()==data:continue
        need(target.name==Path(PS_REL).name and sha(target.read_bytes())==old_worker_sha,'GC32_EXISTING_BOOTSTRAP_CONFLICT')
        upgrade.append(target)
    if not confirm:
        return ('UPGRADE_AVAILABLE' if upgrade else ('MISSING' if missing else 'CURRENT')),sha(wanted[target_dir/Path(PS_REL).name])
    for target,data in wanted.items():
        if target in upgrade:
            archive=target_dir/'history'
            if not archive.exists():archive.mkdir(mode=0o750)
            need(directory(archive),'GC32_HISTORY_DIR_UNSAFE')
            backup=archive/(target.name+'.'+old_worker_sha[:12]+'.bak')
            old=target.read_bytes()
            if backup.exists():need(regular(backup) and backup.read_bytes()==old,'GC32_BACKUP_CONFLICT')
            else:
                fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(fd,'wb') as f:f.write(old);f.flush();os.fsync(f.fileno())
            tmp=target_dir/(target.name+'.incoming.'+str(os.getpid()))
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            need(sha(tmp.read_bytes())==sha(data),'GC32_BOOTSTRAP_STAGE_SHA_MISMATCH')
            need(sha(target.read_bytes())==old_worker_sha,'GC32_BOOTSTRAP_SOURCE_CHANGED_DURING_UPGRADE')
            os.replace(tmp,target)
        elif target in missing:
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        need(regular(target) and sha(target.read_bytes())==sha(data),'GC32_INSTALL_VERIFY_FAILED')
    state=('UPGRADED' if upgrade else ('INSTALLED' if missing else 'CURRENT'))
    return state,sha(wanted[target_dir/Path(PS_REL).name])

def portal_module(root=ROOT):
    p=root/PORTAL_REL
    need(regular(p),'GC32_PORTAL_MODULE_MISSING')
    spec=importlib.util.spec_from_file_location('gc32_import_ts_full',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def atlas_module(root=ROOT):
    p=root/ATLAS_REL
    need(regular(p),'GC32_ATLAS_MODULE_MISSING')
    spec=importlib.util.spec_from_file_location('gc32_structure_atlas_module',p)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def images_from_html(blob):
    raw=blob.decode('utf8')
    prefix='const IMAGES = '
    need(raw.count(prefix)==1,'GC32_IMAGES_BINDING_MISSING')
    start=raw.index(prefix)+len(prefix)
    imgs,end=json.JSONDecoder().raw_decode(raw[start:])
    need(isinstance(imgs,dict) and set(imgs)=={'P01','P02','P03','P04'},'GC32_IMAGE_SET_CHANGED')
    need(all(isinstance(v,str) and v.startswith('data:image/png;base64,') for v in imgs.values()),'GC32_IMAGES_INVALID')
    return imgs

def refresh_portal(client,root=ROOT,share_root=SHARE_ROOT,confirm=False):
    mod=portal_module(root)
    ws=workspace(client,share_root)
    portal=ws/'template_studio'
    old=mod.verify_current(portal)
    imgs=images_from_html((portal/'index.html').read_bytes())
    model=mod.load_registry(root)
    infra=registry(root)
    infra['client']['workspace']=client+'/_forprint_automation'
    infra['audit']=audit(root,infra)
    # Fresh, read-only s01 inventory + optional operator-exported Windows snapshot.
    infra['atlas']=atlas_module(root).build_atlas(ws,client,infra)
    template=(root/'scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html').read_bytes()
    raw,build_id=mod.html_bytes(model,imgs,template,infra=infra)
    if not confirm:
        return 'CHECK_PASS_READ_ONLY',build_id,infra['audit']
    # Always go through the existing publication gate + immutable release.
    staging=root/'tmp'/('gc32_portal_refresh_'+build_id)
    if staging.exists():
        need(directory(staging),'GC32_EXISTING_STAGING_UNSAFE')
        rec=json.loads((staging/'build_manifest.json').read_text('utf8'))
        need((staging/'index.html').read_bytes()==raw and rec['sha256']==sha(raw),'GC32_EXISTING_STAGE_CONFLICT')
    else:
        staging.mkdir(mode=0o700)
        (staging/'index.html').write_bytes(raw)
        (staging/'build_manifest.json').write_text(json.dumps({'schema_version':'forprint_ts_full_build_v0_1','build_id':build_id,'sha256':sha(raw),'source_sha256':mod.SOURCE_SHA},indent=2)+'\n','utf8')
    mod.publish(staging,client,share_root,confirm=True)
    return 'PUBLISHED_VERIFIED',build_id,infra['audit']

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--mode',choices=['audit','worker-check','worker-install','portal-check','portal-refresh'],required=True)
    a.add_argument('--client-name')
    a.add_argument('--confirm',action='store_true')
    args=a.parse_args()
    try:
        need((args.mode in ('worker-install','portal-refresh'))==args.confirm,'GC32_CONFIRMATION_MODE_INVALID')
        if args.mode=='audit':
            state=audit()
            print('GC32_DOCUMENTATION_AUDIT='+state['status'])
            for item in state['warnings']:print('GC32_WARNING='+item)
            return 0
        need(args.client_name,'GC32_CLIENT_REQUIRED')
        if args.mode.startswith('worker'):
            st,key=worker_bootstrap(ROOT,workspace(args.client_name),confirm=args.confirm)
            print('GC32_WORKER_BOOTSTRAP='+st+' SHA256='+key)
        else:
            st,build_id,doc=refresh_portal(args.client_name,confirm=args.confirm)
            print('GC32_PORTAL='+st+' BUILD_ID='+build_id+' PDF_READ=false')
            print('GC32_DOCUMENTATION_AUDIT='+doc['status'])
            for warn in doc['warnings']:print('GC32_WARNING='+warn)
        return 0
    except (Blocked,OSError,ValueError,KeyError,TypeError) as exc:
        name=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC32=BLOCKED reason='+name,file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
