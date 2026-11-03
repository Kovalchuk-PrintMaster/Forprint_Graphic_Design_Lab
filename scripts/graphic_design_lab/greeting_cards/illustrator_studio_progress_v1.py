#!/usr/bin/env python3
"""Read-only verified-output progress presentation for the one canonical Studio.

Never starts native work. A green READY means the already published output has
passed the existing GC47S verification again, not that art has visual approval.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

READY='READY_FOR_VISUAL_REVIEW'
STEPS={
 'INPUT':(1,'Intake ZIP і матеріали перевірено'),
 'PREFLIGHT':(2,'PREPRESS та Illustrator перевірено'),
 'PREPARED':(3,'Сцену й одноразову спробу підготовлено'),
 'TRANSFER':(4,'Робочі файли передано на PREPRESS'),
 'REQUESTED':(5,'Контролер прийняв запит на запуск'),
 'NATIVE':(6,'Illustrator підтвердив native-результат'),
 'OUTPUT':(7,'AI / PDF / PNG перевірено й опубліковано'),
 'POSTFLIGHT':(8,'Illustrator штатно закрито'),
}
SHA=re.compile(r'^[0-9a-f]{64}$')
ATTEMPT=re.compile(r'^p\d{14}-[a-f0-9]{8}$')

def regular(path):
    try:
        st=path.lstat()
        return stat.S_ISREG(st.st_mode) and not path.is_symlink()
    except OSError:return False

def directory(path):
    try:
        st=path.lstat()
        return stat.S_ISDIR(st.st_mode) and not path.is_symlink()
    except OSError:return False

def filehash(path):
    d=hashlib.sha256()
    with path.open('rb') as stream:
        for buf in iter(lambda:stream.read(1024*1024),b''):d.update(buf)
    return d.hexdigest()

def published_review_state(s,ws,jid,attempt,archive_sha=None):
    """Read-only and fail closed: output folder alone is never proof of READY."""
    if not isinstance(attempt,str) or not ATTEMPT.fullmatch(attempt):
        return {'status':'NO_ATTEMPT'}
    folder=s.review_dir(ws,jid,attempt)
    if not directory(folder):return {'status':'NOT_PUBLISHED'}
    try:
        # Never follow a symlink in the client output lineage.
        cursor=folder
        while cursor!=ws:
            if not directory(cursor):raise ValueError('UNSAFE_REVIEW_PARENT')
            if cursor==cursor.parent:raise ValueError('REVIEW_OUTSIDE_WORKSPACE')
            cursor=cursor.parent
        proof=folder/'verify.json'
        need=[*s.REQUIRED_NATIVE,'verify.json']
        if not all(regular(folder/name) for name in need):raise ValueError('MISSING_VERIFIED_ARTIFACT')
        v=json.loads(proof.read_text('utf8'))
        state_file=s.pilot_dir(ws,jid,attempt)/'state.json'
        if not regular(state_file):raise ValueError('MISSING_ATTEMPT_STATE')
        st=json.loads(state_file.read_text('utf8'))
        if v.get('job_id')!=jid or v.get('attempt_id')!=attempt or st.get('job_id')!=jid or st.get('attempt_id')!=attempt:
            raise ValueError('JOB_ATTEMPT_BINDING_MISMATCH')
        if archive_sha is not None and (not SHA.fullmatch(str(archive_sha)) or st.get('accepted_zip_sha256')!=archive_sha):
            raise ValueError('ARCHIVE_LINEAGE_MISMATCH')
        if v.get('source_jsx_sha256')!=st.get('native_jsx_sha256') or not SHA.fullmatch(str(v.get('source_jsx_sha256',''))):
            raise ValueError('JSX_LINEAGE_MISMATCH')
        if v.get('visual_approved') is not False or v.get('production_ready') is not False:
            raise ValueError('AUTHORITY_MISMATCH')
        hashes=v.get('files_sha256')
        if not isinstance(hashes,dict) or set(hashes)!=set(s.REQUIRED_NATIVE):raise ValueError('ARTIFACT_INDEX_MISMATCH')
        for name,digest in hashes.items():
            p=folder/name
            if not SHA.fullmatch(str(digest)) or p.stat().st_size>600*1024*1024 or filehash(p)!=digest:
                raise ValueError('ARTIFACT_HASH_MISMATCH')
        # Independent native-format and text-coverage verification already used by GC47S.
        actual=s.verify_native(folder,st)
        if actual!=hashes:raise ValueError('GC47S_ARTIFACT_VERIFICATION_MISMATCH')
        return {'status':READY,'review_relative':str(folder.relative_to(ws)), 'files_verified':len(hashes)}
    except Exception as e:
        return {'status':'REVIEW_VERIFICATION_BLOCKED','reason':type(e).__name__}

def attempt_from_claim(ws,zip_sha,jid):
    """Look only at existing immutable claim receipts, never create a claim."""
    if not SHA.fullmatch(str(zip_sha)) or not isinstance(jid,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{3,95}',jid):
        return {'status':'INVALID_CLAIM_KEY'}
    claims=ws/'template_studio'/'studio_intake_dynamic_native_claims_v1'
    if not directory(claims):return {'status':'NOT_STARTED'}
    token=hashlib.sha256((zip_sha+'\n'+jid).encode('ascii')).hexdigest()
    claim=claims/(token+'.json'); pointer=claims/(token+'.attempt.json')
    if claim.is_symlink() or pointer.is_symlink():return {'status':'CLAIM_UNSAFE'}
    if not regular(claim):return {'status':'NOT_STARTED' if not pointer.exists() else 'CLAIM_INCONSISTENT'}
    try:
        c=json.loads(claim.read_text('utf8'))
        if c.get('state')!='CLAIMED_SINGLE_USE' or c.get('job_id')!=jid or c.get('archive_sha256')!=zip_sha:
            return {'status':'CLAIM_INCONSISTENT'}
        if not regular(pointer):return {'status':'CLAIMED_NO_ATTEMPT'}
        p=json.loads(pointer.read_text('utf8'))
        att=p.get('attempt_id')
        if p.get('job_id')!=jid or p.get('archive_sha256')!=zip_sha or not isinstance(att,str) or not ATTEMPT.fullmatch(att):
            return {'status':'CLAIM_INCONSISTENT'}
        return {'status':'ATTEMPT_EXISTS','attempt_id':att}
    except (OSError,ValueError,TypeError,KeyError):return {'status':'CLAIM_INCONSISTENT'}

class ConsoleProgress:
    """Compact ANSI presentation. 8 milestones are evidence gates, NOT time/percent."""
    def __init__(self,job,zip_name,stream=None,batch_index=1,batch_total=1):
        self.out=stream if stream is not None else sys.stdout
        self.tty=bool(getattr(self.out,'isatty',lambda:False)()) and not os.environ.get('NO_COLOR')
        self.job=re.sub(r'[\x00-\x1f\x7f]', '?', str(job));self.zip_name=re.sub(r'[\x00-\x1f\x7f]', '?', str(zip_name))
        self.index=batch_index;self.total=batch_total;self.completed=0
        self._line('cyan','═'*64)
        self._line('cyan',f'  FORPRINT STUDIO · {self.index}/{self.total} · {self.job}')
        self._line('cyan',f'  Джерело: {self.zip_name}')
        self._line('cyan','═'*64)
    def _line(self,color,text):
        colorcode={'red':'31','yellow':'33','green':'32','cyan':'36','plain':'0'}[color]
        encoded=(f'\033[{colorcode}m{text}\033[0m' if self.tty else text)
        print(encoded,file=self.out,flush=True)
    def milestone(self,key):
        num,description=STEPS[key];self.completed=max(self.completed,num)
        self._line('green',f'  [OK {num}/8] {description}')
    def active(self,text):self._line('cyan',f'  [..] {text}')
    def warning(self,text):self._line('yellow',f'  [!] {text}')
    def error(self,text):self._line('red',f'  [X] {text}')
    def heartbeat(self,elapsed,state):
        # NOT_RECORDED does NOT imply Illustrator is running or stalled.
        self._line('yellow',f'  [.. {int(elapsed)} с] Очікуємо native-результат; контролер: {state}')
    def ready(self,relative):
        self._line('green','═'*64)
        self._line('green','  ГОТОВО ДО ВІЗУАЛЬНОЇ ПЕРЕВІРКИ · AI / PDF / PNG')
        self._line('green',f'  Папка: {relative}')
        self._line('yellow','  LAB ONLY · дизайн ще не затверджений · production вимкнено')
        self._line('green','═'*64)
    def batch(self,rows):
        total=len(rows);ready=sum(x.get('status')==READY for x in rows)
        self._line('green' if ready==total and total else 'cyan',f'  ГОТОВО ДО ПЕРЕГЛЯДУ: {ready} З {total} · черга не запускається')
        for i,row in enumerate(rows,1):
            status=row['status'];level='green' if status==READY else ('red' if status in ('REVIEW_VERIFICATION_BLOCKED','CLAIM_UNSAFE','CLAIM_INCONSISTENT') else 'yellow')
            self._line(level,f'  {i}/{total} {row["job_id"]}: {status}')
