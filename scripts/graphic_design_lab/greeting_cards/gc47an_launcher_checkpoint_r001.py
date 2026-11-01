#!/usr/bin/env python3
"""GC47AN: read-only launcher acceptance; opt-in narrowly scoped Git checkpoint.

Never launches Illustrator, collects a result, approves production, changes SMB ACL,
or writes into Prepress Hub. Git commit requires --confirm-commit. Push is separate opt-in.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SHARE = Path('/srv/smb/In_Progress/data')
REL = 'scripts/graphic_design_lab/greeting_cards/'
# Immutable as-installed source snapshots from GC47AI through GC47AM.
LOCKED = {
 'scripts/graphic_design_lab/greeting_cards/gc47ai_illustrator_first_launcher_r001.py': '9b5cf00228e1dbe543cfba0c5aac0fcc2834f2c02ced904ded5632e7e41ea210',
 'tests/graphic_design_lab/test_gc47ai_illustrator_first_launcher_r001.py': '108b0c5490a346c2c7bbc86e013b41f0adf9ccd403b27e1422f06e6e693f1779',
 'scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py': '11c917af001771dfa6e9e338492594d8e044c8c579a7f3b78f5e4bc423b360a6',
 'scripts/graphic_design_lab/greeting_cards/gc47aj_client_entry_deploy_r001.py': 'ec0259d1c696f1ed9fd543039cec303ca03420b2c8ee39ac42815de23c442e48',
 'tests/graphic_design_lab/test_gc47aj_client_operator_r001.py': '5b0a1a0a41ff280278463259aa7e291a2ec085bd222cb9356f1e2c20d2f6f3d0',
 'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_bridge_r001.py': 'cd95b413c6543e0896f2cf2b89ec1e73d2397fe669b45fe5ad6a6d621f45c824',
 'scripts/graphic_design_lab/greeting_cards/gc47ak_windows_client_deploy_r001.py': '8299e0598ede804265848677473bb97eb564303349c857200244987801652c66',
 'tests/graphic_design_lab/test_gc47ak_windows_client_r001.py': 'e632c5065157f51b98cb4df946eb527193b29d44eab032f9836d5872cd94f62b',
 'scripts/graphic_design_lab/greeting_cards/gc47al_windows_client_repair_r001.py': 'bc53e1b7d6392f94f93ac64645126a55a5ecb1b1797c60d4741f08788895c67e',
 'tests/graphic_design_lab/test_gc47al_windows_client_repair_r001.py': 'c8db9d3e5bd174a7aa623724607149a911e8d82a5bfaa5a8cd0ff00e7fe90b3c',
 'scripts/graphic_design_lab/greeting_cards/gc47am_windows_access_unicode_r001.py': '2826ba9c15512f13f98ba0cf586405ae62b9c8fee24d89eb178b3f4569290bec',
 'tests/graphic_design_lab/test_gc47am_windows_access_unicode_r001.py': '41f40412d226ed3b4410af3f8dc9e75ac8124369e7d95f97f0d4368c98d146eb',
}
GC47AN_SELF = 'scripts/graphic_design_lab/greeting_cards/gc47an_launcher_checkpoint_r001.py'
GC47AN_TEST = 'tests/graphic_design_lab/test_gc47an_launcher_checkpoint_r001.py'

# Exact original fragments, so commit can stage only Launcher additions even
# when Makefile contained unrelated unstaged changes before GC47AI.
AI_FRAGMENT = '''
# GC47AI Illustrator-first operator launcher r001 (additive, non-release).
GC47AI_CLI := scripts/graphic_design_lab/greeting_cards/gc47ai_illustrator_first_launcher_r001.py
GC47AI_PY := .venv_gdl/bin/python
.PHONY: gdl-card-launcher gdl-card-launcher-test gdl-card-launcher-check gdl-card-launcher-list gdl-card-launcher-inspect gdl-card-launcher-routes
gdl-card-launcher:
\t$(GC47AI_PY) -B $(GC47AI_CLI) --mode interactive
gdl-card-launcher-test:
\t$(GC47AI_PY) -B tests/graphic_design_lab/test_gc47ai_illustrator_first_launcher_r001.py
gdl-card-launcher-check:
\t$(GC47AI_PY) -B $(GC47AI_CLI) --mode check
gdl-card-launcher-list:
\t$(GC47AI_PY) -B $(GC47AI_CLI) --mode list
gdl-card-launcher-inspect:
\t@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME required"; exit 2)
\t$(GC47AI_PY) -B $(GC47AI_CLI) --mode inspect --client-name "$(CLIENT_NAME)"
gdl-card-launcher-routes:
\t$(GC47AI_PY) -B $(GC47AI_CLI) --mode routes
# GC47AI_END
'''
AJ_FRAGMENT = '''
# GC47AJ: client-local entrypoint; operator logic GDL-owned; review only.
GC47AJ_PY := .venv_gdl/bin/python
GC47AJ_UI := scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py
GC47AJ_DEPLOY := scripts/graphic_design_lab/greeting_cards/gc47aj_client_entry_deploy_r001.py
.PHONY: gdl-client-launcher-test gdl-client-launcher-check gdl-client-launcher-install

gdl-client-launcher-test:
\t$(GC47AJ_PY) -B tests/graphic_design_lab/test_gc47aj_client_operator_r001.py

gdl-client-launcher-check:
\t@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME=... required"; exit 2)
\t$(GC47AJ_PY) -B $(GC47AJ_DEPLOY) --mode check --client-name "$(CLIENT_NAME)"

gdl-client-launcher-install:
\t@test -n "$(CLIENT_NAME)" -a "$(CONFIRM_INSTALL)" = YES || (echo "CLIENT_NAME=... CONFIRM_INSTALL=YES required"; exit 2)
\t$(GC47AJ_PY) -B $(GC47AJ_DEPLOY) --mode install --client-name "$(CLIENT_NAME)" --confirm-install
# GC47AJ_END
'''
AN_FRAGMENT = '''
# GC47AN: scoped acceptance/commit gate; never renders or approves production.
GC47AN_CLI := scripts/graphic_design_lab/greeting_cards/gc47an_launcher_checkpoint_r001.py
.PHONY: gdl-launcher-acceptance gdl-launcher-acceptance-test gdl-launcher-git-plan
gdl-launcher-acceptance:
\t.venv_gdl/bin/python -B $(GC47AN_CLI) --mode audit --client-name "$(CLIENT_NAME)" --job "$(JOB)" --attempt "$(ATTEMPT)"
gdl-launcher-acceptance-test:
\t.venv_gdl/bin/python -B tests/graphic_design_lab/test_gc47an_launcher_checkpoint_r001.py
gdl-launcher-git-plan:
\t.venv_gdl/bin/python -B $(GC47AN_CLI) --mode plan --client-name "$(CLIENT_NAME)" --job "$(JOB)" --attempt "$(ATTEMPT)"
# GC47AN_END
'''
FRAGMENTS = (AI_FRAGMENT, AJ_FRAGMENT, AN_FRAGMENT)
ARTIFACTS = ('design.ai','review.pdf','preview_p01.png','preview_p02.png',
             'preview_p03.png','preview_p04.png','passport_snapshot.json','SHA256SUMS')

class Blocked(Exception): pass

def need(ok, why):
    if not ok: raise Blocked(why)

def regular(path):
    try: return stat.S_ISREG(path.lstat().st_mode)
    except OSError: return False

def directory(path):
    try: return stat.S_ISDIR(path.lstat().st_mode)
    except OSError: return False

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def git(repo,*args,input_bytes=None,check=True):
    p=subprocess.run(['git','-C',str(repo),*args],input=input_bytes,capture_output=True,check=False)
    if check and p.returncode:
        raise Blocked('GIT_'+re.sub(r'[^A-Z0-9]+','_',args[0].upper())+'_FAILED')
    return p

def verify_sources(repo):
    need(repo.name=='forprint_graphic_design_lab' and directory(repo/'.git'), 'INVALID_GDL_ROOT')
    need(regular(repo/'Makefile'),'MAKEFILE_UNSAFE')
    for path,expected in LOCKED.items():
        need(regular(repo/path) and sha256(repo/path)==expected, 'FROZEN_SOURCE_CHANGED_'+Path(path).name)
    for path in (GC47AN_SELF,GC47AN_TEST):
        need(regular(repo/path),'GC47AN_SOURCE_MISSING_'+Path(path).name)
    body=(repo/'Makefile').read_text('utf-8')
    need(all(body.count(f)==1 for f in FRAGMENTS),'MAKEFILE_LAUNCHER_FRAGMENT_CHANGED')
    need(body.endswith(''.join(FRAGMENTS)),'MAKEFILE_LAUNCHER_FRAGMENTS_NOT_AT_TAIL')
    need((repo/'.venv_gdl/bin/python').exists(),'GDL_VENV_MISSING')
    return 14

def client_path(client,share=SHARE):
    need(client not in ('','.','..') and len(client)<=150 and not any(ord(c)<32 or c in '/\\' for c in client),'UNSAFE_CLIENT_NAME')
    need(directory(share), 'SMB_SHARE_MISSING')
    ws=share/client/'_forprint_automation'
    for folder in (share/client,ws,ws/'input',ws/'output'):
        need(directory(folder),'CLIENT_FOLDER_MISSING_OR_SYMLINK')
    need(ws.resolve(strict=True).parent.parent==share.resolve(strict=True),'CLIENT_BOUNDARY_INVALID')
    return ws

def verify_client(ws, client):
    input_dir=ws/'input'
    cmd=input_dir/'ForPrint_Launcher.cmd'; ps=input_dir/'ForPrint_Launcher.ps1'
    need(regular(cmd) and regular(ps),'CLIENT_WINDOWS_LAUNCHER_MISSING')
    # SHA is pinned to the Windows Terminal bootstrap produced by GC47AM.
    need(sha256(cmd)=='1fa24482bf20fbfc8967f2e2b97395b50adb09e96ce744a9bccaea9dbc4aeba8', 'CLIENT_CMD_DRIFT')
    need(bool(stat.S_IMODE(cmd.lstat().st_mode)&0o111),'CLIENT_CMD_EXECUTE_BIT_MISSING')
    need(bool(stat.S_IMODE(ps.lstat().st_mode)&0o111),'CLIENT_PS1_EXECUTE_BIT_MISSING')
    # Verify exactly the pinned GC47AL PS1 generator, not merely a substring.
    import importlib.util
    def load(name, path):
        spec=importlib.util.spec_from_file_location(name,path)
        need(spec is not None and spec.loader is not None,'WINDOWS_SOURCE_IMPORT_UNAVAILABLE')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    ak=load('gc47an_source_ak',ROOT/REL/'gc47ak_windows_client_deploy_r001.py')
    al=load('gc47an_source_al',ROOT/REL/'gc47al_windows_client_repair_r001.py')
    need(ps.read_bytes()==al.generate_ps1(client,ak),'CLIENT_PS1_DRIFT')
    return input_dir

def parse_sums(content):
    result={}
    for line in content.splitlines():
        if not line.strip():continue
        m=re.fullmatch(r'([0-9a-fA-F]{64}) [ *]([^\r\n]+)',line)
        need(m is not None,'BAD_SHA256SUMS_FORMAT')
        name=m.group(2)
        need(name not in result and '/' not in name and '\\' not in name and name not in ('.','..'),'UNSAFE_SHA256SUMS_MEMBER')
        result[name]=m.group(1).lower()
    return result

def verify_review(ws,job,attempt):
    need(re.fullmatch(r'gdl_gc_[a-z0-9_]+_\d{8}',job) is not None,'JOB_ID_INVALID')
    need(re.fullmatch(r'p\d{14}-[a-f0-9]{8}',attempt) is not None,'ATTEMPT_ID_INVALID')
    base=ws/'output'/'greeting_card_pilots'/job/attempt
    for d in (ws/'output'/'greeting_card_pilots',ws/'output'/'greeting_card_pilots'/job,base):
        need(directory(d),'PUBLISHED_REVIEW_MISSING_OR_SYMLINK')
    for name in ARTIFACTS:need(regular(base/name),'REVIEW_ARTIFACT_MISSING_'+name)
    sums=parse_sums((base/'SHA256SUMS').read_text('utf-8'))
    for name in ARTIFACTS:
        if name=='SHA256SUMS':continue
        need(name in sums and sha256(base/name)==sums[name],'REVIEW_SHA256_INVALID_'+name)
    passport=json.loads((base/'passport_snapshot.json').read_text('utf-8'))
    need(isinstance(passport,dict),'PASSPORT_SNAPSHOT_NOT_OBJECT')
    # Do not infer approval from presence of AI/PDF/PNG.
    return base,len(ARTIFACTS)-1

def make_index_overlay(current,fragments=FRAGMENTS):
    for f in fragments:
        need(current.count(f) in (0,1),'INDEX_MAKE_FRAGMENT_DUPLICATE')
    existing=[f for f in fragments if f in current]
    need(existing==list(fragments[:len(existing)]),'INDEX_MAKE_FRAGMENT_OUT_OF_ORDER')
    return current + ''.join(f for f in fragments if f not in current)

def git_plan(repo):
    need(git(repo,'branch','--show-current').stdout.decode().strip()=='main','REQUIRE_MAIN_BRANCH')
    need(git(repo,'diff','--cached','--quiet',check=False).returncode==0,'PREEXISTING_STAGED_CHANGES')
    index=git(repo,'show',':Makefile').stdout.decode('utf-8')
    work=(repo/'Makefile').read_text('utf-8')
    need(work.endswith(''.join(FRAGMENTS)), 'MAKEFILE_LAUNCHER_FRAGMENTS_NOT_AT_TAIL')
    overlay=make_index_overlay(index)
    # Ensure the overlay adds only our appendix and leaves preexisting index untouched.
    need(overlay.startswith(index),'INDEX_REWRITE_REFUSED')
    files=tuple(LOCKED)+(GC47AN_SELF,GC47AN_TEST)
    for f in files:
        need(regular(repo/f),'SOURCE_MISSING_'+Path(f).name)
    return files,overlay,index

def do_commit(repo, push=False):
    verify_sources(repo)
    files, overlay, original_index=git_plan(repo)
    # Gate before any Git mutation. Non-launcher changes in worktree remain unstaged.
    git(repo,'add','--',*files)
    try:
        if overlay!=original_index:
            # Stage an index-only Makefile appendix, NOT unrelated worktree changes.
            stage=git(repo,'ls-files','--stage','--','Makefile').stdout.decode()
            need(len(stage.splitlines())==1,'MAKEFILE_INDEX_STAGE_AMBIGUOUS')
            mode=stage.split()[0]
            need(mode in ('100644','100755'),'MAKEFILE_INDEX_MODE_UNSAFE')
            blob=git(repo,'hash-object','-w','--stdin',input_bytes=overlay.encode()).stdout.decode().strip()
            need(re.fullmatch('[0-9a-f]{40,64}',blob) is not None,'GIT_BLOB_INVALID')
            git(repo,'update-index','--add','--cacheinfo',f'{mode},{blob},Makefile')
        staged=git(repo,'diff','--cached','--name-only','-z').stdout.decode().split('\0')
        actual={x for x in staged if x}
        need(actual and actual <= set(files)|{'Makefile'},'UNEXPECTED_STAGED_PATHS')
        need(git(repo,'diff','--cached','--check',check=False).returncode==0,'STAGED_DIFF_WHITESPACE_ERRORS')
        git(repo,'commit','-m','feat(gdl): checkpoint GC47AN Illustrator-first client launcher (non-release)')
    except Exception:
        # No reset: retain staged snapshot for operator review after any failure.
        raise
    head=git(repo,'rev-parse','HEAD').stdout.decode().strip()
    print('GC47AN_COMMIT='+head)
    print('GC47AN_STAGED_PATHS='+','.join(sorted(actual)))
    print('GC47AN_UNRELATED_WORKTREE_CHANGES_PRESERVED=TRUE')
    if push:
        git(repo,'push','origin','HEAD:main')
        print('GC47AN_PUSH=PASS_ORIGIN_MAIN_NON_FORCE')
    else:
        print('GC47AN_PUSH=NOT_REQUESTED')


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('audit','plan','commit'))
    ap.add_argument('--client-name',default=os.environ.get('GC47AN_CLIENT_NAME'))
    ap.add_argument('--job',default=os.environ.get('GC47AN_JOB'))
    ap.add_argument('--attempt',default=os.environ.get('GC47AN_ATTEMPT'))
    ap.add_argument('--repo-root',type=Path,default=ROOT)
    ap.add_argument('--confirm-commit',action='store_true')
    ap.add_argument('--push',action='store_true')
    args=ap.parse_args(argv)
    try:
        need(bool(args.client_name) and bool(args.job) and bool(args.attempt),'CLIENT_JOB_ATTEMPT_REQUIRED')
        root=args.repo_root
        count=verify_sources(root)
        ws=client_path(args.client_name)
        verify_client(ws,args.client_name)
        result,number=verify_review(ws,args.job,args.attempt)
        print(f'GC47AN_SOURCE_LOCK=PASS_{count}_FILES')
        print('GC47AN_WINDOWS_CLIENT_ENTRY=PASS_PRESENT_REVIEW_ONLY')
        print('GC47AN_REVIEW_SHA256=PASS_'+str(number)+'_ARTIFACTS')
        print('GC47AN_JOB='+args.job+' ATTEMPT='+args.attempt)
        print('GC47AN_RESULT='+str(result.relative_to(ws)))
        print('GC47AN_VISUAL_APPROVED=FALSE PRODUCTION_READY=FALSE DUAL_RUNTIME=DISABLED')
        if args.mode in ('plan','commit'):
            files,overlay,index=git_plan(root)
            print('GC47AN_GIT_PLAN=READY_SCOPE_LOCKED')
            print('GC47AN_FILES_TO_STAGE='+str(len(files))+' PLUS_SCOPED_MAKEFILE_APPENDIX')
            print('GC47AN_MAKEFILE_UNRELATED_WORKTREE_DIFF=EXCLUDED')
        if args.mode=='commit':
            need(args.confirm_commit,'EXPLICIT_COMMIT_APPROVAL_REQUIRED')
            do_commit(root,push=args.push)
        else:
            need(not args.push,'PUSH_REQUIRES_COMMIT_MODE')
            print('GC47AN_GIT_MUTATION=NONE')
        print('GC47AN_CHECKPOINT=LAUNCHER_TECHNICAL_ACCEPTANCE_NON_RELEASE')
        return 0
    except (Blocked,OSError,ValueError,UnicodeError,json.JSONDecodeError) as e:
        detail=str(e) if isinstance(e,Blocked) else type(e).__name__
        print('GC47AN=BLOCKED_'+re.sub('[^A-Za-z0-9_]','_',detail).upper(),file=sys.stderr)
        print('GC47AN_NO_NATIVE_DISPATCH=TRUE NO_AUTOMATIC_RETRY=TRUE',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
