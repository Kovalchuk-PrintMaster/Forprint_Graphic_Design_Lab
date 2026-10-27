#!/usr/bin/env python3
"""GC32 structure atlas: bounded, read-only client inventory and optional PREPRESS evidence.

Executed only by GDL publication at operator request. No PDF opening, content extraction,
archive unpacking, symlink following, privileged access or automatic publication.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import stat

SCHEMA = 'forprint_gdl_gc32_structure_atlas_v0_1'
WINDOWS_SCHEMA = 'forprint_gdl_gc32_prepress_tree_snapshot_v0_1'
MAX_ITEMS = 900
MAX_DEPTH = 6
MAX_MANIFEST = 256 * 1024
MAX_HASH_BYTES = 100 * 1024 * 1024
MAX_WINDOWS_SNAPSHOT = 512 * 1024
MUST_EXIST = ('input', 'output', 'template_studio', 'template_studio/index.html',
              'template_studio/native_asset_vault_v0_1/vault_manifest.json',
              'template_studio/worker_bootstrap/gc32_prepress_worker_v0_1.ps1')
SKIP_DESCEND = {'template_studio/releases', 'template_studio/worker_bootstrap/history',
                'template_studio/native_runs'}

class AtlasBlocked(ValueError):
    pass

def _regular(path: Path) -> bool:
    try: return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError: return False

def _dir(path: Path) -> bool:
    try: return stat.S_ISDIR(path.lstat().st_mode)
    except FileNotFoundError: return False

def _hex64(s: object) -> bool:
    return isinstance(s,str) and len(s)==64 and all(c in '0123456789abcdef' for c in s)

def _file_hash(path: Path):
    digest=sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()

def _rel_safe(s):
    return (isinstance(s,str) and 0<len(s)<512 and '\\' not in s and '\x00' not in s and
            not s.startswith('/') and all(p not in ('','.', '..') for p in s.split('/')))

def _read_vault(ws: Path):
    vault=ws/'template_studio/native_asset_vault_v0_1'
    mpath=vault/'vault_manifest.json'
    if not _regular(mpath):
        return [], ['VAULT_MANIFEST_MISSING_OR_UNSAFE']
    if mpath.stat().st_size>MAX_MANIFEST:
        return [], ['VAULT_MANIFEST_OVERSIZE']
    try: manifest=json.loads(mpath.read_text('utf8'))
    except (ValueError,UnicodeError): return [], ['VAULT_MANIFEST_UNREADABLE']
    if manifest.get('schema')!='gdl_gc29_native_asset_vault_v0_1':
        return [], ['VAULT_SCHEMA_UNEXPECTED']
    assets=manifest.get('assets')
    if not isinstance(assets,dict) or len(assets)>60:
        return [], ['VAULT_ASSETS_INVALID']
    results=[];warnings=[]
    hints={
      'paper':'Фон сторінки', 'frame':'Декоративна рамка',
      'logo':'Логотип', 'flowers':'Квіти / фотоконтент',
      'watermark':'Водяний знак', 'signature':'Графічний підпис',
      'sender':'Відправник', 'locked_background':'Зафіксований фон',
    }
    for name,b in sorted(assets.items()):
        if not isinstance(name,str) or '/' in name or '\\' in name or name in ('.','..') or not isinstance(b,dict):
            warnings.append('VAULT_MEMBER_UNSAFE');continue
        wanted=b.get('sha256'); size=b.get('size_bytes'); f=vault/name
        purpose=next((v for k,v in hints.items() if k in name),'Графічний ресурс шаблону')
        item={'id':name,'path':'template_studio/native_asset_vault_v0_1/'+name,'purpose':purpose,
              'expected_sha256':wanted if _hex64(wanted) else None,'actual_sha256':None,
              'state':'NOT_CHECKED','size_bytes':None}
        try:
            if not _regular(f): item['state']='MISSING_OR_UNSAFE'
            else:
                st=f.stat();item['size_bytes']=st.st_size
                if not _hex64(wanted) or not isinstance(size,int) or size<0: item['state']='INVALID_PIN'
                elif st.st_size!=size: item['state']='SIZE_MISMATCH'
                elif st.st_size>MAX_HASH_BYTES: item['state']='NOT_HASHED_TOO_LARGE'
                else:
                    item['actual_sha256']=_file_hash(f)
                    item['state']='SHA256_MATCH' if item['actual_sha256']==wanted else 'SHA256_MISMATCH'
        except OSError: item['state']='READ_ERROR'
        results.append(item)
        if item['state']!='SHA256_MATCH':warnings.append('VAULT_ASSET_'+item['state']+': '+name)
    if manifest.get('asset_count')!=len(assets):warnings.append('VAULT_ASSET_COUNT_MISMATCH')
    return results,warnings

def _read_previous_atlas(portal:Path):
    """Use immutable existing publication as baseline; never trust arbitrary external input."""
    index=portal/'index.html'
    if not _regular(index):return None
    try:
        raw=index.read_text('utf8')
        tag='const INFRA = '
        if raw.count(tag)!=1:return None
        infra,_=json.JSONDecoder().raw_decode(raw[raw.index(tag)+len(tag):])
        atlas=infra.get('atlas') if isinstance(infra,dict) else None
        if isinstance(atlas,dict) and atlas.get('schema_version')==SCHEMA:return atlas
    except (ValueError,UnicodeError,OSError):pass
    return None

def _tree(ws:Path, prev:dict|None):
    if not _dir(ws):raise AtlasBlocked('CLIENT_WORKSPACE_UNSAFE')
    records=[];warnings=[];limit=False
    stack=[(ws,0)]
    while stack:
        folder,depth=stack.pop()
        try:
            with os.scandir(folder) as stream:
                children=[]
                for entry in stream:
                    children.append(entry)
                    if len(children)>=1800:
                        warnings.append('DIRECTORY_SCAN_LIMIT_REACHED: '+folder.relative_to(ws).as_posix())
                        limit=True
                        break
                children.sort(key=lambda e:e.name.casefold())
        except OSError:
            warnings.append('DIRECTORY_NOT_READABLE: '+folder.relative_to(ws).as_posix());continue
        for entry in children:
            if len(records)>=MAX_ITEMS:limit=True;break
            p=Path(entry.path);rel=p.relative_to(ws).as_posix()
            # Preserve only the metadata needed for the operator, no content or credentials.
            try:
                info=p.lstat()
                kind=('link' if stat.S_ISLNK(info.st_mode) else
                      'dir' if stat.S_ISDIR(info.st_mode) else
                      'file' if stat.S_ISREG(info.st_mode) else 'other')
            except OSError:
                warnings.append('STAT_FAILED: '+rel);continue
            record={'path':rel,'kind':kind,'size_bytes':info.st_size if kind=='file' else None,
                    'modified_ns':info.st_mtime_ns if kind=='file' else None,
                    'state':'PRESENT' if kind in ('file','dir') else 'UNSAFE_ENTRY',
                    'change':'BASELINE'}
            records.append(record)
            if kind=='link':warnings.append('SYMLINK_NOT_FOLLOWED: '+rel)
            if kind=='dir' and depth<MAX_DEPTH and rel not in SKIP_DESCEND:
                stack.append((p,depth+1))
        if limit:break
    current={x['path']:x for x in records}
    previous={x['path']:x for x in (prev or {}).get('actual',{}).get('client',{}).get('entries',[])
              if isinstance(x,dict) and isinstance(x.get('path'),str)}
    if previous:
        for x in records:
            past=previous.get(x['path'])
            if past is None:x['change']='NEW'
            elif x['kind']!=past.get('kind'):x['change']='TYPE_CHANGED'
            elif x['path']=='template_studio/index.html':x['change']='PORTAL_SELF_REFRESH'
            elif x['kind']=='file' and (x['size_bytes']!=past.get('size_bytes') or x['modified_ns']!=past.get('modified_ns')):
                x['change']='METADATA_CHANGED_NOT_SHA_PROOF'
            else:x['change']='UNCHANGED'
    removed=[] if limit else sorted(set(previous)-set(current))
    for p in MUST_EXIST:
        if p not in current:warnings.append('REQUIRED_PATH_MISSING: '+p)
    if limit:warnings.append('INVENTORY_TRUNCATED_AT_'+str(MAX_ITEMS))
    counts={k:sum(1 for x in records if x['change']==k) for k in ('NEW','TYPE_CHANGED','METADATA_CHANGED_NOT_SHA_PROOF')}
    counts.update({'items':len(records),'removed':len(removed)})
    return {'source':'S01_READ_ONLY_AT_PORTAL_REFRESH','scan_complete':not limit,
            'scan_scope':'BOUNDED_SKIP_RELEASES_AND_NATIVE_RUN_CONTENTS','entries':records,
            'removed':removed,'counts':counts},warnings

def _prepress(ws:Path,client:str, previous:dict|None):
    p=ws/'template_studio/inventory/prepress_snapshot.json'
    if not _regular(p):return {'source':'NO_WINDOWS_SNAPSHOT','state':'NOT_SCANNED','entries':[]},['PREPRESS_SNAPSHOT_NOT_AVAILABLE']
    if p.stat().st_size>MAX_WINDOWS_SNAPSHOT:
        return {'source':'INVALID_WINDOWS_SNAPSHOT','state':'INVALID','entries':[]},['PREPRESS_SNAPSHOT_OVERSIZE']
    try:raw=json.loads(p.read_text('utf8'))
    except (ValueError,UnicodeError):return {'source':'INVALID_WINDOWS_SNAPSHOT','state':'INVALID','entries':[]},['PREPRESS_SNAPSHOT_JSON_INVALID']
    if (not isinstance(raw,dict) or raw.get('schema_version')!=WINDOWS_SCHEMA or
        raw.get('machine')!='PREPRESS' or raw.get('user')!='Work' or raw.get('client')!=client or
        raw.get('root')!=r'D:\ForPrint_Automation\GraficsDesignLab\Automation'):
        return {'source':'INVALID_WINDOWS_SNAPSHOT','state':'INVALID','entries':[]},['PREPRESS_SNAPSHOT_BINDING_MISMATCH']
    nodes=raw.get('entries')
    if not isinstance(nodes,list) or len(nodes)>500:
        return {'source':'INVALID_WINDOWS_SNAPSHOT','state':'INVALID','entries':[]},['PREPRESS_SNAPSHOT_ENTRIES_INVALID']
    results=[]
    for item in nodes:
        if not isinstance(item,dict) or not _rel_safe(item.get('path')) or item.get('kind') not in ('file','dir'):
            return {'source':'INVALID_WINDOWS_SNAPSHOT','state':'INVALID','entries':[]},['PREPRESS_SNAPSHOT_PATH_UNSAFE']
        results.append({'path':item['path'],'kind':item['kind'],
                        'size_bytes':item.get('size_bytes') if isinstance(item.get('size_bytes'),int) else None,
                        'sha256':item.get('sha256') if _hex64(item.get('sha256')) else None,
                        'change':'WINDOWS_SELF_REPORTED'})
    # The published file is a validated self-report captured through the server SSH
    # route.  It is not an independent remote attestation of every Windows file.
    return {'source':'PUBLISHED_WINDOWS_SELF_REPORT','state':'SELF_REPORTED_NOT_REMOTE_ATTESTED',
            'captured_utc':str(raw.get('captured_utc',''))[:35], 'entries':results,
            'counts':{'items':len(results)}, 'root':raw['root'],
            'scan_truncated':raw.get('scan_truncated') if type(raw.get('scan_truncated')) is bool else None,
            'scan_scope':'BOUNDED_CONFIG_WORKER_CACHE_AND_THIS_CLIENT_JOBS',
            'scan_policy':'MAX_450_RECORDS_DEPTH_3_SELECT_FIRST_150_PER_SEGMENT',
            'content_hash_scope':'SMALL_SELECTED_FILES_ONLY_NOT_COMPLETE_DISK_PROOF'},[]

def build_atlas(ws:Path,client:str,meta:dict,previous:dict|None=None):
    """Return declarative map + bounded fresh observations, never mutation."""
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    if previous is None:previous=_read_previous_atlas(ws/'template_studio')
    client_tree,warnings=_tree(ws,previous)
    descriptions={x['path'].rstrip('/'):x['title'] for x in meta['client']['structure']}
    for item in client_tree['entries']:
        path=item['path'].rstrip('/')
        if path in descriptions:item['purpose']=descriptions[path]
        elif path.startswith('template_studio/native_asset_vault_v0_1/'):
            item['purpose']='Ресурс бібліотеки; детальна SHA256-перевірка праворуч'
        elif path.startswith('output/'):
            item['purpose']='Вихідний артефакт або звіт (не підтверджений друк)'
        elif path.startswith('input/'):
            item['purpose']='Клієнтський Intake/операторський запускач; вміст не відкривався'
    assets,asset_warnings=_read_vault(ws)
    win,win_warnings=_prepress(ws,client,previous)
    conceptual={
       'client': [{'path':x['path'],'purpose':x['title'],'lifecycle':x['state']} for x in meta['client']['structure']],
       'prepress': [{'path':x['path'],'purpose':x['title'],'lifecycle':x['state']} for x in meta['worker']['structure']]
    }
    return {'schema_version':SCHEMA,'version':'0.1','captured_utc':now,
            'conceptual':conceptual,
            'actual':{'client':client_tree,'prepress':win},
            'assets':assets,'warnings':warnings+asset_warnings+win_warnings,
            'privacy':'PRIVATE_OPERATOR_ONLY',
            'truth_rules':{'client':'SERVER_FILESYSTEM_OBSERVED','prepress':'WINDOWS_SELF_REPORTED_NOT_ATTESTED',
                           'sha256':'ONLY_CHECKED_PINNED_ASSETS_COUNT_AS_VERIFIED',
                           'refresh':'SNAPSHOT_AT_EXPLICIT_PORTAL_REFRESH_NOT_LIVE_BROWSER'}}


def scanner_installer(ws:Path, root:Path, confirm:bool=False):
    """Create-only one optional scanner in the existing client worker_bootstrap folder."""
    src=root/'scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_inventory_v0_1.ps1'
    dest=ws/'template_studio/worker_bootstrap/gc32_prepress_inventory_v0_1.ps1'
    if not _regular(src) or not _dir(dest.parent):raise AtlasBlocked('SCANNER_SOURCE_OR_BOOTSTRAP_PARENT_MISSING')
    data=src.read_bytes()
    if not data.startswith(b'\xef\xbb\xbf') or len(data)>50_000:
        raise AtlasBlocked('SCANNER_SOURCE_INVALID')
    if dest.exists() or dest.is_symlink():
        if not _regular(dest) or _file_hash(dest)!=sha256(data).hexdigest():
            raise AtlasBlocked('EXISTING_SCANNER_DIFFERENT_NO_OVERWRITE')
        return 'CURRENT',sha256(data).hexdigest()
    if not confirm:return 'MISSING',sha256(data).hexdigest()
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
    with os.fdopen(fd,'wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if _file_hash(dest)!=sha256(data).hexdigest():raise AtlasBlocked('INSTALLED_SCANNER_HASH_MISMATCH')
    return 'INSTALLED',sha256(data).hexdigest()


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('check','scanner-check','scanner-install'),default='check')
    parser.add_argument('--client-name',required=True)
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    client=args.client_name
    if not client or client in ('.','..') or '/' in client or "\\" in client or '\x00' in client:
        raise SystemExit('GC32_ATLAS=BLOCKED CLIENT_NAME_INVALID')
    if args.confirm!=(args.mode=='scanner-install'):
        raise SystemExit('GC32_ATLAS=BLOCKED CONFIRMATION_MODE_INVALID')
    root=Path(__file__).resolve().parents[3]
    map_path=root/'coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json'
    ws=Path('/srv/smb/In_Progress/data')/client/'_forprint_automation'
    if not _dir(ws) or not _regular(map_path):
        raise SystemExit('GC32_ATLAS=BLOCKED WORKSPACE_OR_MAP_MISSING')
    try:
        if args.mode.startswith('scanner-'):
            state,digest=scanner_installer(ws,root,args.confirm)
            print('GC32_ATLAS_WINDOWS_SCANNER='+state+' SHA256='+digest)
            return
        model=json.loads(map_path.read_text('utf8'))
        report=build_atlas(ws,client,model)
        print('GC32_ATLAS=CHECK_READ_ONLY CLIENT_ITEMS='+str(report['actual']['client']['counts']['items']))
        print('GC32_ATLAS_PINNED_ASSETS='+str(len(report['assets'])))
        print('GC32_ATLAS_PREPRESS='+str(report['actual']['prepress']['state']))
        for w in report['warnings'][:35]:print('GC32_ATLAS_WARNING='+w)
        if len(report['warnings'])>35:print('GC32_ATLAS_WARNING=ADDITIONAL_WARNINGS_REDACTED')
    except (AtlasBlocked,OSError,ValueError) as exc:
        raise SystemExit('GC32_ATLAS=BLOCKED REASON='+str(exc)[:120]) from None

if __name__=='__main__':main()
