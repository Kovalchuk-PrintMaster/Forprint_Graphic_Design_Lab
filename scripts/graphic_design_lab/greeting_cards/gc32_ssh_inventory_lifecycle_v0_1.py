#!/usr/bin/env python3
"""GC32: authenticated s01->PREPRESS read-only inventory, verified snapshot, cleanup *proposals*.

Modes: capture (SSH, writes only to project tmp), publish (server-owned inventory snapshot).
Neither mode moves, quarantines, deletes, or renders any client or Windows file.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import uuid

HOST = 'work@192.168.50.69'
KEY = '/root/.ssh/forprint_prepress_ed25519'
KNOWN = '/root/.ssh/known_hosts_forprint_prepress'
ROOT = Path(__file__).resolve().parents[3]
SRC_PS = ROOT / 'scripts/graphic_design_lab/greeting_cards/windows/gc32_prepress_ssh_snapshot_v0_1.ps1'
CLIENT_ROOT = Path('/srv/smb/In_Progress/data')
WINDOWS_ROOT = r'D:\ForPrint_Automation\GraficsDesignLab\Automation'
SCHEMA = 'forprint_gdl_gc32_prepress_tree_snapshot_v0_1'
MAX_SNAPSHOT_BYTES = 512000
MAX_ITEMS = 450
SHA_RE = re.compile(r'^[0-9a-f]{64}$')

class Blocked(Exception): pass

def need(ok: bool, error: str):
    if not ok: raise Blocked(error)

def ordinary(p: Path):
    try: return stat.S_ISREG(p.lstat().st_mode)
    except FileNotFoundError: return False

def directory(p: Path):
    try: return stat.S_ISDIR(p.lstat().st_mode)
    except FileNotFoundError: return False

def sha(data:bytes)->str: return sha256(data).hexdigest()

def client_workspace(name:str, share:Path=CLIENT_ROOT)->Path:
    need(isinstance(name,str) and 0<len(name)<=180 and name not in ('.','..') and
         '/' not in name and '\\' not in name and '\x00' not in name, 'CLIENT_NAME_INVALID')
    need(directory(share), 'SHARE_ROOT_NOT_AVAILABLE')
    ws=share/name/'_forprint_automation'
    need(directory(share/name) and directory(ws) and directory(ws/'template_studio'), 'CLIENT_WORKSPACE_NOT_READY')
    need(ws.resolve(strict=True).parent.parent == share.resolve(strict=True), 'WORKSPACE_OUTSIDE_SHARE')
    return ws

def check_snapshot(doc:dict,client:str)->dict:
    need(isinstance(doc,dict), 'SNAPSHOT_NOT_OBJECT')
    need(doc.get('schema_version')==SCHEMA and doc.get('machine')=='PREPRESS' and
         str(doc.get('user','')).lower()=='work' and doc.get('client')==client and
         doc.get('root')==WINDOWS_ROOT, 'SNAPSHOT_BINDING_MISMATCH')
    need(doc.get('operator_export_only') is True and doc.get('production_authority') is False,
         'SNAPSHOT_AUTHORITY_INVALID')
    items=doc.get('entries')
    need(isinstance(items,list) and len(items)<=MAX_ITEMS, 'SNAPSHOT_ITEMS_INVALID')
    seen=set(); parsed=[]
    for item in items:
        need(isinstance(item,dict), 'SNAPSHOT_ITEM_INVALID')
        p=item.get('path'); kind=item.get('kind'); hash_value=item.get('sha256')
        need(isinstance(p,str) and 0<len(p)<512 and '\\' not in p and '\x00' not in p and
             all(s not in ('.','..','') for s in p.split('/')) and not p.startswith('/'),
             'SNAPSHOT_PATH_INVALID')
        need(p.casefold() not in seen and kind in ('file','dir'), 'SNAPSHOT_PATH_DUPLICATE_OR_KIND_INVALID')
        seen.add(p.casefold())
        need(hash_value is None or (isinstance(hash_value,str) and SHA_RE.fullmatch(hash_value)),
             'SNAPSHOT_SHA_INVALID')
        n=item.get('size_bytes')
        need(n is None or (type(n) is int and n>=0), 'SNAPSHOT_SIZE_INVALID')
        parsed.append({'path':p,'kind':kind,'size_bytes':n,'sha256':hash_value})
    need(isinstance(doc.get('captured_utc'),str) and len(doc['captured_utc'])<45,
         'SNAPSHOT_DATE_INVALID')
    # Canonical shape compatible with the existing GC32 atlas parser.
    return {'schema_version':SCHEMA,'machine':'PREPRESS','user':'Work',
            'client':client,'root':WINDOWS_ROOT,'captured_utc':doc['captured_utc'],
            'entries':parsed,'operator_export_only':True,'production_authority':False,
            'scan_truncated':doc.get('scan_truncated') is True}

# GC32 r005: one pinned scanner file on PREPRESS; all commands sent via short
# verified PowerShell -EncodedCommand. No streamed script body or SMB write.
SCANNER_REMOTE_PATH = WINDOWS_ROOT + r'\Worker\gc32_prepress_ssh_snapshot_v0_1.ps1'


def _ssh_options():
    return ['-i', KEY, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=10', '-o', f'UserKnownHostsFile={KNOWN}',
            '-o', 'StrictHostKeyChecking=yes']


def _powershell_ssh(body: str, *, runner=subprocess.run, timeout: int = 45):
    encoded=base64.b64encode(body.encode('utf-16le')).decode('ascii')
    args=['ssh','-T',*_ssh_options(),HOST,'powershell.exe','-NoLogo',
          '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
          '-EncodedCommand',encoded]
    need(len(' '.join(args)) < 5000, 'GC32_SHORT_COMMAND_TOO_LONG')
    try:
        return runner(args,timeout=timeout,check=False,capture_output=True)
    except subprocess.TimeoutExpired as e:
        raise Blocked('GC32_REMOTE_TIMEOUT') from e


def _safe_result(res, prefix: str):
    if res.returncode == 0:
        return res.stdout.decode('utf-8-sig',errors='replace')
    stderr=res.stderr.decode('utf-8-sig',errors='replace')
    # Only enumerated codes from our own remote wrapper are surfaced.
    for code in ('SCANNER_MISSING','SCANNER_SHA_CHANGED','WRONG_WORKER',
                 'STAGE_EXISTS','STAGE_MISSING','STAGE_SHA_CHANGED',
                 'INSTALL_TARGET_EXISTS','SCAN_EXCEPTION','SCANNER_SHA_UNAVAILABLE'):
        if 'GC32_REMOTE_'+code in stderr:
            raise Blocked('GC32_REMOTE_'+code)
    raise Blocked(prefix+'_RC_'+str(res.returncode))


def _scanner_hash(source: Path) -> str:
    need(ordinary(source),'SSH_SNAPSHOT_SOURCE_MISSING')
    data=source.read_bytes()
    need(200 < len(data) < 70000,'SSH_SNAPSHOT_SOURCE_SIZE_INVALID')
    need(b'param(' in data and b'ClientBase64' in data and
         b'__CLIENT_BASE64__' not in data,'GC32_VERSIONED_SCANNER_CONTRACT_INVALID')
    return sha(data)


def scanner_check(source: Path = SRC_PS, *, runner=subprocess.run) -> str:
    digest=_scanner_hash(source)
    body=("$ErrorActionPreference='Stop';"
          "$p='"+SCANNER_REMOTE_PATH+"';"
          "if($env:COMPUTERNAME -ine 'PREPRESS' -or $env:USERNAME -ine 'Work'){"
          "[Console]::Error.WriteLine('GC32_REMOTE_WRONG_WORKER');exit 71};"
          "if(-not(Test-Path -LiteralPath $p -PathType Leaf)){"
          "Write-Output 'GC32_SCANNER_STATE=MISSING';exit 0};"
          "$h=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant();"
          "if($h -ne '"+digest+"'){Write-Output 'GC32_SCANNER_STATE=CONFLICT';exit 0};"
          "Write-Output 'GC32_SCANNER_STATE=CURRENT'")
    value=_safe_result(_powershell_ssh(body,runner=runner),'GC32_SCANNER_CHECK_FAILED')
    matches=[x.strip().split('=',1)[1] for x in value.splitlines()
             if x.strip().startswith('GC32_SCANNER_STATE=')]
    need(len(matches)==1 and matches[0] in ('MISSING','CURRENT','CONFLICT'),
         'GC32_SCANNER_CHECK_RESULT_INVALID')
    return matches[0]


def scanner_install(source: Path = SRC_PS, *, confirm: bool,
                    runner=subprocess.run, copier=subprocess.run) -> str:
    need(confirm,'GC32_SCANNER_INSTALL_CONFIRM_REQUIRED')
    digest=_scanner_hash(source)
    state=scanner_check(source,runner=runner)
    if state == 'CURRENT':return 'CURRENT'
    need(state=='MISSING','GC32_SCANNER_EXISTING_CONFLICT_NO_OVERWRITE')
    filename='gc32_scanner_stage_'+digest[:16]+'.ps1'
    # The configured OpenSSH home is the established GC21 SCP staging route.
    # It is only temporary; after successful SHA validation the file moves
    # to the single Automation/Worker root. No new permanent root is created.
    pre=("$ErrorActionPreference='Stop';"
         "$dst='"+SCANNER_REMOTE_PATH+"';$stage=Join-Path $HOME '"+filename+"';"
         "if($env:COMPUTERNAME -ine 'PREPRESS' -or $env:USERNAME -ine 'Work'){"
         "[Console]::Error.WriteLine('GC32_REMOTE_WRONG_WORKER');exit 71};"
         "if(-not(Test-Path -LiteralPath (Split-Path -Parent $dst) -PathType Container)){"
         "[Console]::Error.WriteLine('GC32_REMOTE_SCANNER_MISSING');exit 72};"
         "if((Test-Path -LiteralPath $dst) -or (Test-Path -LiteralPath $stage)){"
         "[Console]::Error.WriteLine('GC32_REMOTE_STAGE_EXISTS');exit 73};"
         "Write-Output 'GC32_SCANNER_STAGE_PREFLIGHT=PASS'")
    output=_safe_result(_powershell_ssh(pre,runner=runner),'GC32_STAGE_PREFLIGHT_FAILED')
    need('GC32_SCANNER_STAGE_PREFLIGHT=PASS' in output,'GC32_STAGE_PREFLIGHT_OUTPUT_INVALID')
    cmd=['scp',*_ssh_options(),str(source),HOST+':'+filename]
    try:
        cp=copier(cmd,timeout=60,check=False,capture_output=True)
    except subprocess.TimeoutExpired as e:
        raise Blocked('GC32_SCP_TIMEOUT_POSSIBLE_STAGE_FILE') from e
    need(cp.returncode==0,'GC32_SCP_FAILED_POSSIBLE_STAGE_FILE')
    install=("$ErrorActionPreference='Stop';"
         "$dst='"+SCANNER_REMOTE_PATH+"';$stage=Join-Path $HOME '"+filename+"';"
         "if(-not(Test-Path -LiteralPath $stage -PathType Leaf)){"
         "[Console]::Error.WriteLine('GC32_REMOTE_STAGE_MISSING');exit 72};"
         "if(Test-Path -LiteralPath $dst){"
         "[Console]::Error.WriteLine('GC32_REMOTE_INSTALL_TARGET_EXISTS');exit 73};"
         "$h=(Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash.ToLowerInvariant();"
         "if($h -ne '"+digest+"'){"
         "[Console]::Error.WriteLine('GC32_REMOTE_STAGE_SHA_CHANGED');exit 74};"
         "Move-Item -LiteralPath $stage -Destination $dst -ErrorAction Stop;"
         "$h2=(Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLowerInvariant();"
         "if($h2 -ne '"+digest+"'){"
         "[Console]::Error.WriteLine('GC32_REMOTE_SCANNER_SHA_CHANGED');exit 75};"
         "Write-Output 'GC32_SCANNER_INSTALLED=PASS'")
    output=_safe_result(_powershell_ssh(install,runner=runner),'GC32_SCANNER_INSTALL_FAILED')
    need('GC32_SCANNER_INSTALLED=PASS' in output,'GC32_SCANNER_INSTALL_RESULT_INVALID')
    need(scanner_check(source,runner=runner)=='CURRENT','GC32_POSTINSTALL_SHA_MISMATCH')
    return 'INSTALLED_VERIFIED'


def ssh_capture(client: str, source: Path = SRC_PS, *, runner=subprocess.run) -> dict:
    digest=_scanner_hash(source)
    need(isinstance(client,str) and client and not any(x in client for x in ('\\','/','\x00')),
         'GC32_CLIENT_ARG_INVALID')
    token=base64.b64encode(client.encode('utf8')).decode('ascii')
    body=("$ErrorActionPreference='Stop';"
          "$p='"+SCANNER_REMOTE_PATH+"';"
          "if($env:COMPUTERNAME -ine 'PREPRESS' -or $env:USERNAME -ine 'Work'){"
          "[Console]::Error.WriteLine('GC32_REMOTE_WRONG_WORKER');exit 71};"
          "if(-not(Test-Path -LiteralPath $p -PathType Leaf)){"
          "[Console]::Error.WriteLine('GC32_REMOTE_SCANNER_MISSING');exit 72};"
          "$h=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant();"
          "if($h -ne '"+digest+"'){"
          "[Console]::Error.WriteLine('GC32_REMOTE_SCANNER_SHA_CHANGED');exit 73};"
          "try{& $p -ClientBase64 '"+token+"'}"
          "catch{[Console]::Error.WriteLine('GC32_REMOTE_SCAN_EXCEPTION');exit 74}")
    res=_powershell_ssh(body,runner=runner,timeout=95)
    stdout=_safe_result(res,'GC32_SCANNER_EXECUTION_FAILED')
    need(len(res.stdout)<MAX_SNAPSHOT_BYTES+10000,'PREPRESS_OUTPUT_OVERSIZE')
    lines=[line.split('GC32_SNAPSHOT_JSON=',1)[1] for line in stdout.splitlines()
           if line.startswith('GC32_SNAPSHOT_JSON=')]
    need(len(lines)==1,'PREPRESS_JSON_MARKER_NOT_UNIQUE')
    need(len(lines[0].encode('utf8'))<MAX_SNAPSHOT_BYTES,'PREPRESS_JSON_OVERSIZE')
    try: doc=json.loads(lines[0])
    except ValueError as exc: raise Blocked('PREPRESS_JSON_INVALID') from exc
    return check_snapshot(doc,client)

def lifecycle_report(snapshot:dict)->dict:
    """No implicit cleanup authority: all unpinned jobs are review-only."""
    rows=[]; counts={'STRUCTURE_REGISTERED':0,'HISTORY_REVIEW':0,'UNCLASSIFIED_REVIEW':0}
    protected={'cache','config','jobs','logs','runtime','Worker',
               'Worker/gc32_prepress_worker_v0_1.ps1','config/worker_config.json'}
    for obj in snapshot['entries']:
        path=obj['path']
        if path in protected:status='STRUCTURE_REGISTERED';reason='Required directory or worker binding'
        elif re.match(r'^jobs/gdl-(?:gc|w)[A-Za-z0-9_-]+$',path):
            status='HISTORY_REVIEW';reason='Legacy/test branch; verify acceptance and dependencies before disposition'
        else:
            status='UNCLASSIFIED_REVIEW';reason='Ownership and retention not yet established'
        rows.append({'path':path,'kind':obj['kind'],'status':status,'reason':reason})
        counts[status]+=1
    return {'schema_version':'gc32_lifecycle_inventory_proposal_v0_1',
            'source_snapshot_sha256':sha(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode('utf-8')),
            'counts':counts,'records':rows,
            'authority':{'moving':False,'quarantine':False,'deletion':False},
            'policy':'No automatic deletion or move. Lifecycle review requires owner, dependency audit, recovery plan and explicit confirmation.'}

def client_lifecycle_report(ws:Path)->dict:
    """Bounded server-side client catalogue. Never follows links or reads file content."""
    from collections import Counter
    records=[]; stack=[(ws,0)]; partial=False; skipped=[]
    skip={'template_studio/native_runs','template_studio/releases',
          'output/layout_candidates','template_studio/worker_bootstrap/history'}
    while stack:
        folder,depth=stack.pop()
        try: children=sorted(os.scandir(folder),key=lambda x:x.name.casefold())
        except OSError:
            partial=True;continue
        for child in children:
            if len(records)>=900:
                partial=True;break
            p=Path(child.path);relative=p.relative_to(ws).as_posix()
            try:
                st=p.lstat()
            except OSError:
                partial=True;continue
            typ=('dir' if stat.S_ISDIR(st.st_mode) else
                 'file' if stat.S_ISREG(st.st_mode) else 'other')
            if relative in ('input','output','template_studio','template_studio/index.html') or \
              relative.startswith('template_studio/native_asset_vault_v0_1/'):
                status='REGISTERED_ACTIVE_OR_PINNED'
            elif relative.startswith('template_studio/releases'):
                status='RELEASE_HISTORY_PROTECTED'
            elif relative.startswith('output/'):
                status='OUTPUT_EVIDENCE_REVIEW'
            elif relative.startswith('input/'):
                status='SOURCE_INPUT_REVIEW'
            elif relative.startswith('template_studio/native_runs'):
                status='ATTEMPT_HISTORY_REVIEW'
            else:
                status='UNCLASSIFIED_REVIEW'
            records.append({'path':relative,'kind':typ,'status':status})
            if typ=='dir' and depth<6 and relative not in skip:
                stack.append((p,depth+1))
            elif typ=='dir' and relative in skip:
                skipped.append(relative)
        if partial:break
    return {'schema_version':'gc32_client_lifecycle_proposal_v0_1',
            'records':records,'counts':dict(Counter(x['status'] for x in records)),
            'inventory_truncated':partial,'branches_not_descended':skipped,
            'authority':{'moving':False,'quarantine':False,'deletion':False}}

def export_capture(root:Path,client:str,doc:dict,ws:Path|None=None)->Path:
    base=root/'tmp/gc32_ssh_inventory'
    need(not base.is_symlink(),'TMP_ROOT_SYMLINK_FORBIDDEN')
    base.mkdir(parents=True,exist_ok=True)
    run=base/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    run.mkdir(mode=0o700)
    snap=json.dumps(doc,ensure_ascii=False,indent=2).encode('utf8')+b'\n'
    need(len(snap)<MAX_SNAPSHOT_BYTES,'CAPTURE_JSON_TOO_LARGE')
    proposal=json.dumps(lifecycle_report(doc),ensure_ascii=False,indent=2).encode('utf8')+b'\n'
    client_proposal=(json.dumps(client_lifecycle_report(ws),ensure_ascii=False,indent=2).encode('utf8')+b'\n') if ws else b'{}\n'
    mf={'schema_version':'gc32_ssh_snapshot_capture_manifest_v0_1',
        'client':client,'snapshot_sha256':sha(snap),'source_ps_sha256':sha(SRC_PS.read_bytes()),
        'capture_timestamp_utc':doc['captured_utc'], 'snapshot_file':'prepress_snapshot.json',
        'lifecycle_file':'lifecycle_proposal.json','validated':True}
    for fn,body in [('prepress_snapshot.json',snap),('lifecycle_proposal.json',proposal),('client_lifecycle_proposal.json',client_proposal),
                    ('capture_manifest.json',json.dumps(mf,ensure_ascii=False,indent=2).encode('utf8')+b'\n')]:
        with (run/fn).open('xb') as file:file.write(body)
    return run

def validate_capture(run:Path,client:str)->bytes:
    need(directory(run) and not run.is_symlink(),'CAPTURE_DIRECTORY_UNSAFE')
    snap=run/'prepress_snapshot.json'; mf=run/'capture_manifest.json'
    need(ordinary(snap) and ordinary(mf),'CAPTURE_FILES_MISSING')
    need(snap.stat().st_size<MAX_SNAPSHOT_BYTES and mf.stat().st_size<12000,'CAPTURE_FILE_OVERSIZE')
    raw=snap.read_bytes()
    try:manifest=json.loads(mf.read_text('utf8'));doc=json.loads(raw)
    except ValueError as exc:raise Blocked('CAPTURE_JSON_INVALID') from exc
    need(manifest.get('schema_version')=='gc32_ssh_snapshot_capture_manifest_v0_1' and
         manifest.get('client')==client and manifest.get('snapshot_sha256')==sha(raw),
         'CAPTURE_DIGEST_OR_BINDING_CHANGED')
    check_snapshot(doc,client)
    return raw

def publish_capture(ws:Path,run:Path,client:str)->Path:
    raw=validate_capture(run,client)
    folder=ws/'template_studio/inventory'
    need(not folder.is_symlink(),'CLIENT_INVENTORY_SYMLINK_FORBIDDEN')
    if not folder.exists():folder.mkdir(mode=0o750)
    need(directory(folder),'CLIENT_INVENTORY_UNSAFE')
    target=folder/'prepress_snapshot.json'
    need(not target.is_symlink(),'EXISTING_SNAPSHOT_SYMLINK_FORBIDDEN')
    if target.exists():
        need(ordinary(target),'EXISTING_SNAPSHOT_NOT_REGULAR')
        old=target.read_bytes()
        need(len(old)<MAX_SNAPSHOT_BYTES,'EXISTING_SNAPSHOT_OVERSIZE')
        need(old!=raw,'SNAPSHOT_ALREADY_CURRENT')
        # Back up before replacement, only into the capture directory (owned by s01).
        with (run/'previous_prepress_snapshot.json').open('xb') as file:file.write(old)
    incoming=folder/('prepress_snapshot.incoming.'+uuid.uuid4().hex+'.json')
    try:
        with incoming.open('xb') as file:
            file.write(raw);file.flush();os.fsync(file.fileno())
        need(sha(incoming.read_bytes())==sha(raw),'STAGING_DIGEST_INVALID')
        os.replace(incoming,target)
        need(sha(target.read_bytes())==sha(raw),'PUBLICATION_DIGEST_INVALID')
    finally:
        # Do not delete uncertain partial/incomplete writes automatically.
        pass
    return target

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('capture','publish','review','scanner-check','scanner-install'))
    p.add_argument('--client-name',required=True)
    p.add_argument('--run-dir',type=Path)
    p.add_argument('--confirm-publish',action='store_true')
    p.add_argument('--confirm-install',action='store_true')
    a=p.parse_args(argv)
    try:
        ws=client_workspace(a.client_name)
        if a.mode=='scanner-check':
            need(not a.confirm_install and not a.confirm_publish and a.run_dir is None,
                 'SCANNER_CHECK_ARGS_INVALID')
            print('GC32_REMOTE_SCANNER_STATE='+scanner_check())
            return 0
        if a.mode=='scanner-install':
            need(a.confirm_install and not a.confirm_publish and a.run_dir is None,
                 'SCANNER_INSTALL_ARGS_INVALID')
            print('GC32_REMOTE_SCANNER_INSTALL='+scanner_install(confirm=True))
            return 0
        need(not a.confirm_install,'SCANNER_CONFIRM_SCOPE_INVALID')
        if a.mode=='capture':
            need(a.run_dir is None and not a.confirm_publish,'CAPTURE_ARGS_INVALID')
            doc=ssh_capture(a.client_name)
            path=export_capture(ROOT,a.client_name,doc,ws)
            print('GC32_SSH_CAPTURE=PASS WINDOWS=PREPRESS USER=Work ITEMS='+str(len(doc['entries'])))
            print('GC32_CAPTURE_RUN='+str(path.relative_to(ROOT)))
            print('GC32_SCAN_TRUNCATED='+str(doc['scan_truncated']).lower())
            print('GC32_LIFECYCLE=PROPOSAL_ONLY NO_MOVES_NO_DELETES')
        elif a.mode=='review':
            need(a.run_dir is not None and not a.confirm_publish,'REVIEW_ARGS_INVALID')
            raw=validate_capture(a.run_dir,a.client_name)
            doc=json.loads(raw)
            summary=lifecycle_report(doc)['counts']
            print('GC32_CAPTURE_REVIEW=PASS '+ ' '.join(k+'='+str(v) for k,v in summary.items()))
            print('GC32_CLIENT_PUBLISHED=false')
        else:
            need(a.run_dir is not None and a.confirm_publish,'PUBLISH_EXPLICIT_CONFIRMATION_REQUIRED')
            target=publish_capture(ws,a.run_dir,a.client_name)
            print('GC32_PREPRESS_SNAPSHOT=SERVER_PUBLISHED_VERIFIED')
            print('GC32_PREPRESS_SOURCE=SSH_AUTHENTICATED_SELF_REPORT')
            print('GC32_HTML_REFRESH_REQUIRED=true')
            print('GC32_TARGET='+str(target.relative_to(ws)))
        return 0
    except (Blocked,OSError,UnicodeError,ValueError,subprocess.SubprocessError) as exc:
        code=str(exc) if isinstance(exc,Blocked) else type(exc).__name__
        print('GC32_SSH_INVENTORY=BLOCKED reason='+code,file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
