#!/usr/bin/env python3
"""GC47AC internal GC47T review transport, no direct operator entrypoint.

Input SCP remains unchanged. Verified output transfer goes via binary SSH into
private GDL tmp, then verified copy to the existing client attempt. No retry,
no Illustrator execution, no overwrite of existing or incomplete output.
"""
from __future__ import annotations
import base64
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from zipfile import ZipFile, BadZipFile

ATTEMPT_RE=re.compile(r'^p\d{14}-[0-9a-f]{8}$')
SHA_RE=re.compile(r'^[0-9a-f]{64}$')

class Blocked(ValueError):pass

def need(ok,reason):
    if not ok:raise Blocked(reason)

def is_regular(p):
    try:return stat.S_ISREG(p.lstat().st_mode)
    except OSError:return False

def is_dir(p):
    try:return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:return False

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def verify_zip(path,expected,required,max_transfer):
    need(is_regular(path),'ZIP_NOT_REGULAR')
    size=path.stat().st_size
    need(0<size<=max_transfer,'ZIP_SIZE_LIMIT')
    need(sha(path)==expected,'ZIP_SHA_MISMATCH')
    try:
        with ZipFile(path) as z:
            info=z.infolist()
            need(len(info)==len(required) and {i.filename for i in info}==set(required),'ZIP_MEMBERS')
            need(all(not i.is_dir() and 100<i.file_size<max_transfer for i in info),'ZIP_MEMBER_SIZE')
            need(sum(i.file_size for i in info)<600*1024*1024,'ZIP_EXPANSION_LIMIT')
            need(z.testzip() is None,'ZIP_CRC')
    except (BadZipFile,OSError,EOFError) as e:
        raise Blocked('ZIP_INVALID') from e
    return size

def ps_args(script,ssh_options,host):
    need(len(script)<6500,'PS_SCRIPT_SIZE')
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    need(len(encoded)<16000,'PS_ENCODED_SIZE')
    return ['ssh','-T',*ssh_options(),host,'powershell.exe','-NoLogo','-NoProfile',
            '-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',encoded]

def probe(ssh_options,host,runner=subprocess.run):
    script=r'''$ErrorActionPreference='Stop';$v=New-Object byte[] 4096;
for($i=0;$i -lt $v.Length;$i++){$v[$i]=[byte]($i%256)}
$o=[Console]::OpenStandardOutput();$o.Write($v,0,$v.Length);$o.Flush()'''
    r=runner(ps_args(script,ssh_options,host),capture_output=True,timeout=40,check=False)
    need(r.returncode==0,'BINARY_PROBE_SSH_RC')
    need(r.stdout==bytes(range(256))*16,'BINARY_PROBE_CONTENT')

def remote_evidence(attempt,expected,remote_ps,max_transfer):
    need(ATTEMPT_RE.fullmatch(attempt) is not None,'ATTEMPT_INVALID')
    name='gc47t_'+attempt+'_review_r001.zip'
    ps=rf'''$ErrorActionPreference='Stop';$p=Join-Path $HOME '{name}';
$f=Get-Item -LiteralPath $p -Force -EA Stop;
if($f.PSIsContainer -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint)){{throw 'GC47AC_REMOTE_NOT_REGULAR'}}
Write-Output ('T1_GC47AC_BYTES='+$f.Length)
Write-Output ('T1_GC47AC_SHA='+((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()))'''
    fields={}
    for line in remote_ps(ps,timeout=180).splitlines():
        if line.startswith('T1_GC47AC_') and '=' in line:
            k,v=line.strip().split('=',1)
            need(k not in fields,'REMOTE_DUPLICATE');fields[k]=v
    raw=fields.get('T1_GC47AC_BYTES','')
    need(raw.isdecimal(),'REMOTE_SIZE_FORMAT')
    size=int(raw)
    need(0<size<=max_transfer,'REMOTE_SIZE_LIMIT')
    need(fields.get('T1_GC47AC_SHA')==expected,'REMOTE_SHA_DRIFT')
    return size

def stream(attempt,size,partial,ssh_options,host,runner=subprocess.run):
    need(ATTEMPT_RE.fullmatch(attempt) is not None,'ATTEMPT_INVALID')
    need(is_dir(partial.parent) and not partial.exists() and not partial.is_symlink(),'PART_EXISTS')
    name='gc47t_'+attempt+'_review_r001.zip'
    ps=rf'''$ErrorActionPreference='Stop';$p=Join-Path $HOME '{name}';
$f=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
try {{
 if($f.Length -ne {size}){{throw 'GC47AC_REMOTE_SIZE_CHANGED'}}
 $o=[Console]::OpenStandardOutput();$b=New-Object byte[] 262144;
 while(($n=$f.Read($b,0,$b.Length)) -gt 0){{$o.Write($b,0,$n)}}
 $o.Flush()
}} finally {{ $f.Dispose() }}'''
    with partial.open('xb') as out:
        result=runner(ps_args(ps,ssh_options,host),stdout=out,stderr=subprocess.PIPE,timeout=900,check=False)
        out.flush();os.fsync(out.fileno())
    need(result.returncode==0,'BINARY_STREAM_SSH_RC')
    need(partial.stat().st_size==size,'BINARY_STREAM_SIZE')

def copy_verified(src,dst,expected,required,max_transfer):
    size=verify_zip(src,expected,required,max_transfer)
    need(is_dir(dst.parent) and not dst.exists() and not dst.is_symlink(),'DEST_EXISTS_OR_UNSAFE')
    with src.open('rb') as f,dst.open('xb') as out:
        shutil.copyfileobj(f,out,length=1<<20)
        out.flush();os.fsync(out.fileno())
    need(dst.stat().st_size==size,'SMB_COPY_SIZE')
    verify_zip(dst,expected,required,max_transfer)

def receive_once(attempt,expected,dst,*,remote_ps,ssh_options,host,root,required,max_transfer):
    """Transport only ONE existing Windows result; source SHA supplied by controller."""
    need(ATTEMPT_RE.fullmatch(attempt) is not None,'ATTEMPT_INVALID')
    need(SHA_RE.fullmatch(expected) is not None,'EXPECTED_SHA_INVALID')
    need(is_dir(root/'tmp'),'PROJECT_TMP_UNSAFE')
    stage_root=root/'tmp/gc47ac_verified_review_transport_r001'
    if not stage_root.exists() and not stage_root.is_symlink():stage_root.mkdir(mode=0o700)
    need(is_dir(stage_root) and stat.S_IMODE(stage_root.stat().st_mode)==0o700,'STAGE_ROOT_MODE')
    work=stage_root/attempt
    if not work.exists() and not work.is_symlink():work.mkdir(mode=0o700)
    need(is_dir(work) and stat.S_IMODE(work.stat().st_mode)==0o700,'STAGE_ATTEMPT_MODE')
    part=work/'review_download.part'
    verified=work/'review_native_verified.zip'
    size=remote_evidence(attempt,expected,remote_ps,max_transfer)
    if is_regular(verified):
        need(not part.exists() and not part.is_symlink(),'PART_PRESENT')
        need(verify_zip(verified,expected,required,max_transfer)==size,'VERIFIED_REMOTE_SIZE')
        print('GC47AC_STREAM=REUSE_VERIFIED_PROJECT_TMP_NO_TRANSFER',flush=True)
    else:
        need(not verified.exists() and not verified.is_symlink(),'VERIFIED_UNSAFE')
        need(not part.exists() and not part.is_symlink(),'PARTIAL_PRESENT_NO_AUTO_RETRY')
        probe(ssh_options,host)
        print('GC47AC_TRANSFER=RAW_BINARY_SSH_TO_PROJECT_TMP',flush=True)
        stream(attempt,size,part,ssh_options,host)
        need(verify_zip(part,expected,required,max_transfer)==size,'STREAM_ARCHIVE_SIZE')
        need(remote_evidence(attempt,expected,remote_ps,max_transfer)==size,'REMOTE_CHANGED_DURING_STREAM')
        part.rename(verified)
        print('GC47AC_STREAM=PASS_SHA256_ZIP_CRC_PROJECT_TMP',flush=True)
    copy_verified(verified,dst,expected,required,max_transfer)
    print('GC47AC_PROMOTE=PASS_VERIFIED_SMB_COPY',flush=True)
