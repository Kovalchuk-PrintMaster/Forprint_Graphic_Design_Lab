#!/usr/bin/env python3
"""GC47AM: bounded Windows SMB execute bit + Unicode terminal bootstrap.

Only the existing Windows client CMD bytes and read-derived execute bits on
CMD/PS1 may change. No directory ACL, chown, SSH, launch or renderer.
"""
from __future__ import annotations
import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SHARE = Path('/srv/smb/In_Progress/data')
REL = Path('scripts/graphic_design_lab/greeting_cards')
AK_SHA = '8299e0598ede804265848677473bb97eb564303349c857200244987801652c66'
AL_SHA = 'bc53e1b7d6392f94f93ac64645126a55a5ecb1b1797c60d4741f08788895c67e'
CMD_NAME = 'ForPrint_Launcher.cmd'
PS1_NAME = 'ForPrint_Launcher.ps1'
CMD_OLD_SHA = 'bdee768859b6dedfd7f699c76c24800add9a58056328aab27447033ae773a110'

class Blocked(Exception): pass

def need(test, message):
    if not test: raise Blocked(message)

def sha(data): return hashlib.sha256(data).hexdigest()

def regular(path):
    try: return stat.S_ISREG(path.lstat().st_mode)
    except OSError: return False

def directory(path):
    try: return stat.S_ISDIR(path.lstat().st_mode)
    except OSError: return False

def import_pinned(path, digest, name):
    need(regular(path) and sha(path.read_bytes()) == digest, 'PINNED_MODULE_CHANGED_'+name)
    spec=importlib.util.spec_from_file_location(name, path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# ASCII-only CMD: safely survives legacy Windows code pages. PowerShell text is UTF-8 BOM.
# Prefer Windows Terminal for Unicode, with a conservative classic-CMD fallback.
# No extra SSH invocation is performed: the chosen host invokes exactly one PS1.
CMD_NEW = '''@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "FORPRINT_PS=%~dp0ForPrint_Launcher.ps1"
if not exist "%FORPRINT_PS%" (
  echo GC47AM_BLOCKED=CLIENT_POWERSHELL_FILE_MISSING
  pause
  exit /b 2
)
chcp 65001 >nul
if defined WT_SESSION (
  echo GC47AM_CONSOLE=EXISTING_WINDOWS_TERMINAL
  goto run_powershell
)
where wt.exe >nul 2>nul
if not errorlevel 1 (
  wt.exe -w new new-tab --title ForPrint_Launcher powershell.exe -NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "%FORPRINT_PS%"
  if not errorlevel 1 exit /b 0
)
echo GC47AM_CONSOLE=CLASSIC_CMD_UTF8_FALLBACK
:run_powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%FORPRINT_PS%"
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo GC47AM: Check the error before retrying a previous Illustrator attempt.
if "%RC%"=="0" echo GC47AM: Operator menu closed. Production approval was not granted.
echo.
pause
exit /b %RC%
'''.replace('\n','\r\n').encode('ascii')
CMD_NEW_SHA=sha(CMD_NEW)

def with_execute_where_read(mode):
    """Permission classes with r gain x; never grants new read or write."""
    return mode | ((mode & 0o444) >> 2)

def acl_state(path):
    try:
        v=os.getxattr(path, 'system.posix_acl_access', follow_symlinks=False)
        return 'EXTENDED_POSIX_ACL' if v else 'NONE'
    except OSError as exc:
        if exc.errno in (errno.ENODATA, getattr(errno,'ENOATTR',errno.ENODATA), errno.ENOTSUP, getattr(errno,'EOPNOTSUPP',errno.ENOTSUP)):
            return 'NONE_OR_UNSUPPORTED'
        raise Blocked('ACL_INSPECTION_FAILED_'+exc.__class__.__name__)

def context(client, root=ROOT, share=SHARE):
    ak=import_pinned(root/REL/'gc47ak_windows_client_deploy_r001.py',AK_SHA,'gc47am_original_ak')
    al=import_pinned(root/REL/'gc47al_windows_client_repair_r001.py',AL_SHA,'gc47am_original_al')
    workspace=ak.workspace(client, share)
    input_dir=workspace/'input'
    cmd,ps1=input_dir/CMD_NAME,input_dir/PS1_NAME
    need(regular(cmd) and regular(ps1), 'CLIENT_SCRIPT_MISSING_OR_NOT_REGULAR')
    ch=sha(cmd.read_bytes())
    need(ch in (CMD_OLD_SHA,CMD_NEW_SHA), 'CMD_CHANGED_NO_OVERWRITE')
    expected=al.generate_ps1(client,ak)
    need(sha(ps1.read_bytes())==sha(expected), 'PS1_CHANGED_NO_OVERWRITE')
    files=[cmd,ps1]
    modes={p.name:stat.S_IMODE(p.lstat().st_mode) for p in files}
    acls={p.name:acl_state(p) for p in files}
    return workspace,cmd,ps1,ch,modes,acls

def report(client, root=ROOT, share=SHARE):
    workspace,cmd,ps1,ch,modes,acls=context(client,root,share)
    print('GC47AM_CLIENT_WORKSPACE='+str(workspace))
    print('GC47AM_CMD_SOURCE='+('GC47AK_ORIGINAL' if ch==CMD_OLD_SHA else 'GC47AM_WINDOWS_TERMINAL_BOOTSTRAP'))
    for name in (CMD_NAME,PS1_NAME):
        old=modes[name]
        print('GC47AM_PERMISSION_'+ ('CMD' if name==CMD_NAME else 'PS1')+'=CURRENT_'+format(old,'04o')+'_TARGET_'+format(with_execute_where_read(old),'04o'))
        print('GC47AM_POSIX_ACL_'+ ('CMD' if name==CMD_NAME else 'PS1')+'='+acls[name])
    print('GC47AM_NO_FOLDER_ACL_CHANGE=TRUE NO_CHOWN=TRUE NO_SSH_EXEC=TRUE NO_NATIVE_DISPATCH=TRUE')
    return workspace,cmd,ps1,ch,modes,acls

def atomic_cmd_replace(path,content,mode):
    fd,temp=tempfile.mkstemp(prefix='.gc47am_',suffix='.tmp',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as out:
            out.write(content);out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
        need(sha(path.read_bytes())==sha(content),'CMD_POST_REPLACE_SHA_MISMATCH')
    finally:
        if os.path.lexists(temp): os.unlink(temp)

def apply(client, root=ROOT, share=SHARE):
    workspace,cmd,ps1,ch,modes,acls=context(client,root,share)
    for name,status in acls.items():
        need(status!='EXTENDED_POSIX_ACL', 'EXTENDED_FILE_ACL_REVIEW_REQUIRED_'+name)
    need(directory(root/'tmp'),'GDL_TMP_DIR_MISSING')
    need(all(m & 0o444 for m in modes.values()),'SCRIPT_NOT_READABLE_BY_ANY_CLASS')
    # Guard against writable scripts by everyone, unrelated to this patch.
    need(all((m & 0o002)==0 for m in modes.values()), 'WORLD_WRITABLE_SCRIPT_UNSAFE')
    desired={p.name:with_execute_where_read(modes[p.name]) for p in (cmd,ps1)}
    if ch==CMD_NEW_SHA and all(modes[k]==v for k,v in desired.items()):
        return 'ALREADY_REPAIRED'
    backup_dir=root/'tmp'/'gc47am_windows_client_backup_r001'/sha(client.encode('utf-8'))[:20]
    original_cmd=cmd.read_bytes()
    snapshot={'version':1,'client_sha256':sha(client.encode('utf-8')),
              'original_cmd_sha256':ch,'cmd_mode':modes[CMD_NAME],
              'ps1_sha256':sha(ps1.read_bytes()),'ps1_mode':modes[PS1_NAME]}
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True,mode=0o700)
        for name,data in [('ForPrint_Launcher.cmd.original',original_cmd),('state.json',json.dumps(snapshot,ensure_ascii=False,indent=2).encode('utf-8'))]:
            dst=backup_dir/name
            with dst.open('xb') as f:
                os.fchmod(f.fileno(),0o600)
                f.write(data);f.flush();os.fsync(f.fileno())
    else:
        need(directory(backup_dir),'BACKUP_UNSAFE')
        note=backup_dir/'state.json'
        need(regular(note),'BACKUP_METADATA_MISSING')
        prior=json.loads(note.read_text('utf-8'))
        need(prior['client_sha256']==snapshot['client_sha256'],'BACKUP_CLIENT_ID_MISMATCH')
        need(prior['ps1_sha256']==snapshot['ps1_sha256'],'BACKUP_PS1_CHANGED')
    try:
        if ch==CMD_OLD_SHA:
            atomic_cmd_replace(cmd,CMD_NEW,modes[CMD_NAME])
        # Add X to exactly those classes that already have R. Do not modify folders.
        for path in (cmd,ps1):
            wanted=desired[path.name]
            if stat.S_IMODE(path.lstat().st_mode)!=wanted:
                os.chmod(path,wanted,follow_symlinks=False)
        _,_,_,out_hash,final_modes,_=context(client,root,share)
        need(out_hash==CMD_NEW_SHA and all(final_modes[k]==v for k,v in desired.items()),'AFTER_INSTALL_VERIFY_FAILED')
        return 'REPAIRED_GUARDED_WINDOWS_TERMINAL_AND_SCRIPT_EXECUTE'
    except BaseException:
        # Restore source and original permissions when mid-update fails.
        if sha(cmd.read_bytes())!=sha(original_cmd):
            atomic_cmd_replace(cmd,original_cmd,modes[CMD_NAME])
        for path in (cmd,ps1):
            if regular(path): os.chmod(path,modes[path.name],follow_symlinks=False)
        raise

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('check','install'),required=True)
    ap.add_argument('--client-name',required=True)
    ap.add_argument('--confirm-install',action='store_true')
    args=ap.parse_args(argv)
    try:
        report(args.client_name)
        if args.mode=='install':
            need(args.confirm_install,'EXPLICIT_INSTALL_CONFIRMATION_REQUIRED')
            print('GC47AM_CLIENT_REPAIR='+apply(args.client_name))
            report(args.client_name)
        print('GC47AM_WINDOWS_EXEC=NOT_TESTED_LIVE PRODUCTION_READY=FALSE')
        return 0
    except (Blocked, OSError, ValueError, KeyError) as e:
        print('GC47AM=BLOCKED_'+(str(e) if isinstance(e,Blocked) else type(e).__name__.upper()),file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
