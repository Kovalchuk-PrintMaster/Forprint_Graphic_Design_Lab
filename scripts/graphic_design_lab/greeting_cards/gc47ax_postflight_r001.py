#!/usr/bin/env python3
"""GC47AX: one authorized GC47AS native pilot followed by guarded post-publish close.

Only GC47AR ZAP is supported. Does not queue or re-dispatch on failure.
Native result must be collected and verified by GC47AR before postflight begins.
A postflight failure NEVER invalidates the already published review result.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
CAN = Path(__file__).resolve().parent
AS_NAME = 'gc47ax_illustrator_lifecycle_r001.py'
AS_SHA = '7da40974a4d2dcc26d3f11447fd1d40ee6300fd3104480d487fe4f34fccfd2d9'
CONFIRM = 'GC47AX_ONE_VERSIONED_RENDER_AND_SAFE_FINAL_CLOSE'
STATE_ROOT = ROOT.parent / '.state' / 'graphic_design_lab'
LOCK = STATE_ROOT / 'lifecycle' / 'gc47ax_single_lifecycle_r001.lock'

class Blocked(RuntimeError):
    pass

def need(condition, label):
    if not condition:
        raise Blocked(label)

def load_lifecycle(root=ROOT, can=CAN):
    need(root.name == 'forprint_graphic_design_lab' and (root/'.git').is_dir(), 'REPOSITORY')
    p = can/AS_NAME
    need(stat.S_ISREG(p.lstat().st_mode), 'GC47AS_NOT_REGULAR')
    need(hashlib.sha256(p.read_bytes()).hexdigest() == AS_SHA, 'GC47AS_SHA_DRIFT')
    spec = importlib.util.spec_from_file_location('gc47au_pinned_as',p)
    need(spec is not None and spec.loader is not None, 'GC47AS_IMPORT')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    need(hasattr(m,'main') and hasattr(m,'verify_local'), 'GC47AS_API')
    m.verify_local()
    return m

def sequence(lifecycle, client, timeout=24):
    """Single native attempt, followed by a *distinct* safe-close only on success."""
    rc = lifecycle.main(['--mode','pilot','--client-name',client,
          '--confirm-native-once','--confirmation','GC47AS_SINGLE_NATIVE_REVIEW',
          '--timeout-minutes',str(timeout)])
    if rc != 0:
        print('GC47AX_RENDER=UNVERIFIED_OR_BLOCKED',flush=True)
        print('GC47AX_POSTFLIGHT=SKIPPED_NATIVE_STATE_UNCERTAIN',flush=True)
        print('GC47AX_NO_AUTO_RETRY=TRUE USE_STATUS_AND_COLLECT_ONLY',flush=True)
        return 2
    # GC47AS -> GC47AR can return success ONLY after verified GC47S publication.
    print('GC47AX_RENDER=PASS_PUBLISHED_REVIEW_FROM_GC47AR',flush=True)
    print('GC47AX_POSTFLIGHT=BEGIN_SAVED_ONLY',flush=True)
    rc = lifecycle.main(['--mode','prepare','--client-name',client,
          '--confirm-graceful-close','--confirmation','GC47AS_PREPARE_SAVED_ONLY'])
    if rc != 0:
        print('GC47AX_RENDER_RESULT=RETAINED_PUBLISHED_REVIEW',flush=True)
        print('GC47AX_POSTFLIGHT=BLOCKED_ILLUSTRATOR_STATE_REQUIRES_REVIEW',flush=True)
        print('GC47AX_QUEUE=HALTED_NO_NEW_ATTEMPT',flush=True)
        return 3
    print('GC47AX_POSTFLIGHT=PASS_ILLUSTRATOR_CLOSED',flush=True)
    print('GC47AX_QUEUE=READY_FOR_SEPARATELY_AUTHORIZED_NEXT_ITEM',flush=True)
    print('GC47AX_PRODUCTION_READY=FALSE VISUAL_APPROVED=FALSE',flush=True)
    return 0

def exclusive_run(lifecycle,client,timeout=24,root=ROOT):
    base=root.parent / '.state' / 'graphic_design_lab'
    lock=base/'lifecycle'/'gc47ax_single_lifecycle_r001.lock'
    # Canonical state survives arbitrary cleaning of repo tmp/.
    for parent in (base,lock.parent):
        need(parent.is_dir() and not parent.is_symlink(), 'STATE_DIRECTORY_MISSING_OR_LINK')
        st=parent.stat()
        need(st.st_uid==os.geteuid() and stat.S_IMODE(st.st_mode)==0o700,'STATE_OWNER_OR_MODE')

    flags=os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW
    fd=os.open(lock,flags,0o600)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'LOCK_NOT_REGULAR')
        need(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600, 'LOCK_PERMISSIONS')
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise Blocked('ACTIVE_GC47AX_PILOT_OR_CLEANUP')
        # Check inode continuity: a renamed lock must never be accepted.
        pinned=os.fstat(fd)
        now=lock.lstat()
        need((pinned.st_ino,pinned.st_dev)==(now.st_ino,now.st_dev),'LOCK_INODE_REPLACED')
        return sequence(lifecycle,client,timeout)
    finally:
        os.close(fd)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('check','pilot'))
    p.add_argument('--client-name')
    p.add_argument('--confirm-once-and-post-close',action='store_true')
    p.add_argument('--confirmation')
    p.add_argument('--timeout-minutes',type=int,default=24)
    a=p.parse_args(argv)
    try:
        lifecycle=load_lifecycle()
        if a.mode=='check':
            print('GC47AX_SOURCE=PASS_PINNED_GC47AS_GC47AR',flush=True)
            print('GC47AX_NO_NATIVE_DISPATCH=TRUE',flush=True)
            return 0
        need(bool(a.client_name),'CLIENT_REQUIRED')
        need(a.confirm_once_and_post_close and a.confirmation==CONFIRM,'EXPLICIT_SINGLE_PILOT_AND_POST_CLOSE_REQUIRED')
        need(1<=a.timeout_minutes<=30,'TIMEOUT_RANGE')
        return exclusive_run(lifecycle,a.client_name,a.timeout_minutes)
    except (Blocked,OSError,ValueError,ImportError) as e:
        print('GC47AX=BLOCKED_'+str(e),file=sys.stderr)
        print('GC47AX_NO_AUTO_RETRY=TRUE NO_FORCE_KILL=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
