#!/usr/bin/env python3
"""ForPrint Studio Phase2C: one explicit lab-only, single-use dynamic Intake native pilot.

Reuses Phase2B materializer, canonical Illustrator Studio JSX and established
GC47S/GC47T transport/lifecycle; no second renderer or Windows worker.
An Intake handoff's self-reported review is NOT independent authorization.
Only the operator's interactive, single-use LAB approval can start a native pilot.
Portrait mode remains shadow-only until transport + visual layout are verified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'scripts/graphic_design_lab/greeting_cards'
import importlib.util as _progress_import
_PROGRESS_FILE=Path(__file__).with_name('illustrator_studio_progress_v1.py')
_progress_spec=_progress_import.spec_from_file_location('studio_progress_v1',_PROGRESS_FILE)
if _progress_spec is None or _progress_spec.loader is None:raise ImportError('STUDIO_PROGRESS_IMPORT_UNAVAILABLE')
_progress_mod=_progress_import.module_from_spec(_progress_spec)
_progress_spec.loader.exec_module(_progress_mod)
ConsoleProgress=_progress_mod.ConsoleProgress
published_review_state=_progress_mod.published_review_state
attempt_from_claim=_progress_mod.attempt_from_claim
READY=_progress_mod.READY
SHADOW=SRC/'illustrator_studio_intake_dynamic_preflight_v1.py'
BC=SRC/'gc47bc_profile_native_review_r001.py'
TRANSPORT=SRC/'gc47t_client_windows_bridge_r001.py'
SCHEMA='forprint_illustrator_studio_dynamic_native_lab_v1'
BINDING='studio_dynamic_native_binding_v1.json'
CLAIMS='studio_intake_dynamic_native_claims_v1'
HEX=re.compile(r'^[a-f0-9]{64}$')
ATTEMPT=re.compile(r'^p\d{14}-[a-f0-9]{8}$')

class Blocked(RuntimeError):pass

def need(cond,code):
    if not cond:raise Blocked(code)

def sha(data):return hashlib.sha256(data).hexdigest()

def regular(path):
    try:return stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink()
    except OSError:return False

def directory(path):
    try:return stat.S_ISDIR(path.lstat().st_mode) and not path.is_symlink()
    except OSError:return False

def json_bytes(obj):return (json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf8')

def load_sources():
    need(regular(SHADOW),'SOURCE_SHADOW_MISSING')
    # Phase2C uses exactly the verified Phase2B assembler. No geometry copy.
    import importlib.util
    def load(path,name):
        need(regular(path),'SOURCE_MISSING_'+path.name)
        spec=importlib.util.spec_from_file_location(name,path)
        need(spec and spec.loader,'IMPORT_'+path.name)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        return mod
    shadow=load(SHADOW,'studio_dynamic_shadow_v1')
    bc=load(BC,'studio_dynamic_lifecycle_bc_v1')
    return shadow,bc,load(TRANSPORT,'studio_dynamic_transport_t_v1')

def preflight(client,zip_name,job_id):
    shadow,bc,t=load_sources()
    audit=shadow.load_py(shadow.AUDIT,'studio_dynamic_pilot_audit')
    studio=shadow.load_py(shadow.STUDIO,'studio_dynamic_pilot_studio')
    s=shadow.load_py(shadow.GC47S,'studio_dynamic_pilot_gc47s')
    archive=shadow.input_archive(audit,client,zip_name)
    doc=audit.audit(archive)
    need(doc.get('status')=='HANDOFF_STRUCTURAL_PASS_STUDIO_BINDING_REQUIRED',
         'ZIP_NOT_ACCEPTED_HANDOFF_STRUCTURAL_PASS')
    digest=shadow.sha(archive.read_bytes())
    gc29=s.load_source()
    ws=s.workspace(client)
    vault=ws/'template_studio'/'native_asset_vault_v0_1'
    catalog=gc29.verify_vault(vault)
    with zipfile.ZipFile(archive) as z:
        bundle=audit.load_yaml(z.read('accepted_constructor_bundle.yaml'))
        art=audit.load_yaml(z.read('artifact_manifest.yaml'))
        jobs=bundle['jobs']
        need(isinstance(jobs,list) and len(jobs)>0,'BATCH_JOBS_EMPTY')
        chosen=[j for j in jobs if isinstance(j,dict) and j.get('job_id')==job_id]
        need(len(chosen)==1,'JOB_NOT_UNIQUE_IN_SELECTED_HANDOFF')
        record,work=shadow.assemble(gc29,studio,chosen[0],art['artifacts'],z,
                                    vault,catalog,digest,capture_material=True)
    need(record['status']=='SCENE_SHADOW_COMPILED_NOT_NATIVE_APPROVED','SOURCE_SHADOW_FAILED')
    need(sha(work['jsx'])==record['native_jsx_sha256'] and sha(work['manifest'])==record['manifest_sha256'],
         'MATERIAL_SHA_MISMATCH')
    man=json.loads(work['manifest'].decode('utf8'))
    need(man.get('job_id')==job_id and man.get('accepted_zip_sha256')==digest,
         'MATERIAL_SOURCE_MISMATCH')
    need(set(man.get('asset_sha256',{}))==set(work['assets']), 'MATERIAL_ASSET_INDEX_DRIFT')
    for name,content in work['assets'].items():
        need(sha(content)==man['asset_sha256'][name],'MATERIAL_ASSET_HASH_'+name)
    # The existing GC47T Windows transport accepts DEFAULT_ASSET only.
    supported=record['image_mode']=='DEFAULT_ASSET'
    return {'client':client,'zip_name':zip_name,'job_id':job_id,'archive':archive,
            'archive_sha256':digest,'record':record,'work':work,'ws':ws,'job':chosen[0],
            's':s,'gc29':gc29,'shadow':shadow,'bc':bc,'t':t,'native_supported':supported}

def public_plan(data):
    row=data['record'];support=data['native_supported']
    return {'schema_version':SCHEMA,'status':'READY_FOR_OPERATOR_LAB_SINGLE_USE' if support else 'BLOCKED_NATIVE_PORTRAIT_TRANSPORT_NOT_WIRED',
            'job_id':data['job_id'],'zip_name':data['zip_name'],'archive_sha256':data['archive_sha256'],
            'renderer_jsx_sha256':row['native_jsx_sha256'],'scene_manifest_sha256':row['manifest_sha256'],
            'asset_count':row['asset_count'],'front':row['front_family'],'image_mode':row['image_mode'],
            'signature':row['signature_variant'],'sender_rows':row['sender_rows'],
            'review_independently_attested':False,'native_dispatch':False,'production_ready':False,
            'automatic_queue':False,'automatic_retry':False,'single_attempt_only':True,
            'known_visual_review_issues':['P03_FRAME','P04_SENDER_SIGNATURE_COLLISION']}

def claims_dir(ws,create=False):
    home=ws/'template_studio'
    need(directory(home),'CLIENT_TEMPLATE_STUDIO_NOT_DIRECTORY')
    path=home/CLAIMS
    need(not path.is_symlink(),'NATIVE_CLAIM_DIR_SYMLINK')
    if create and not path.exists():
        try:path.mkdir(mode=0o750)
        except FileExistsError:pass
    if create:need(directory(path),'NATIVE_CLAIM_DIR_UNSAFE')
    return path

def claim_token(data):return sha((data['archive_sha256']+'\n'+data['job_id']).encode('ascii'))

def create_claim(data):
    path=claims_dir(data['ws'],True)/(claim_token(data)+'.json')
    need(not path.is_symlink(),'NATIVE_CLAIM_SYMLINK')
    obj={'schema_version':SCHEMA,'state':'CLAIMED_SINGLE_USE','job_id':data['job_id'],
         'archive_sha256':data['archive_sha256'],'jsx_sha256':data['record']['native_jsx_sha256'],
         'operator_action':'INTERACTIVE_LAB_PILOT_ACKNOWLEDGED',
         'independent_intake_review_attested':False,'production_ready':False,
         'automatic_retry':False}
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    try:
        fd=os.open(path,flags,0o640)
        with os.fdopen(fd,'wb') as f:f.write(json_bytes(obj));f.flush();os.fsync(f.fileno())
    except FileExistsError:raise Blocked('SINGLE_USE_ALREADY_CLAIMED_NO_RELAUNCH')
    return path

def store_claim_attempt(data,attempt):
    path=claims_dir(data['ws'])/(claim_token(data)+'.attempt.json')
    need(not path.exists() and not path.is_symlink(),'NATIVE_ATTEMPT_ALREADY_BOUND')
    obj={'schema_version':SCHEMA,'attempt_id':attempt,'job_id':data['job_id'],
         'archive_sha256':data['archive_sha256'],'production_ready':False}
    with path.open('xb') as f:f.write(json_bytes(obj));f.flush();os.fsync(f.fileno())

def claim_status(data):
    path=claims_dir(data['ws'])
    token=claim_token(data)
    claimed=path/(token+'.json');attempt=path/(token+'.attempt.json')
    need(not claimed.is_symlink() and not attempt.is_symlink(),'CLAIM_FILE_SYMLINK')
    result={'schema_version':SCHEMA,'claim':'CLAIMED' if regular(claimed) else 'NOT_CLAIMED',
            'attempt_id':None,'single_use_no_retry':True}
    if regular(attempt):result['attempt_id']=json.loads(attempt.read_text('utf8')).get('attempt_id')
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
    return 0

def staged_prepare(data):
    s=data['s'];gc29=data['gc29'];ws=data['ws'];job=data['job_id'];work=data['work']
    original=gc29.prepare
    invoked=[]
    def prepare(workspace,jid,attempt):
        need(workspace==ws and jid==job and ATTEMPT.fullmatch(attempt or ''),'ATTEMPT_SCOPE_MISMATCH')
        dest=s.native_run_dir(ws,jid,attempt)
        need(not dest.exists() and not dest.is_symlink(),'NATIVE_STAGE_ALREADY_EXISTS')
        need(directory(dest.parent),'NATIVE_STAGE_PARENT_INVALID')
        dest.mkdir(mode=0o750)
        (dest/'assets').mkdir(mode=0o750)
        for filename,blob in [('run_in_illustrator.jsx',work['jsx']),('scene_manifest.json',work['manifest'])]:
            with (dest/filename).open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        for name,blob in sorted(work['assets'].items()):
            need(re.fullmatch(r'[a-z0-9_]+\.png',name),'ASSET_NAME_INVALID')
            with (dest/'assets'/name).open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        manifest=json.loads((dest/'scene_manifest.json').read_text('utf8'))
        need(sha((dest/'run_in_illustrator.jsx').read_bytes())==manifest['jsx_sha256'],'STAGED_JSX_DRIFT')
        need(all(sha((dest/'assets'/n).read_bytes())==h for n,h in manifest['asset_sha256'].items()),
             'STAGED_ASSET_DRIFT')
        invoked.append(attempt)
        return dest,None
    gc29.prepare=prepare
    try:
        _,passport=s.current_passport()
        result=s.start_one(gc29,ws,data['job'],data['archive'],passport,job)
    finally:gc29.prepare=original
    need(result is not None and len(invoked)==1 and invoked[0]==result['attempt'],
         'NATIVE_ATTEMPT_PREPARATION_INCOMPLETE')
    need(result['state']=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED','NATIVE_PREPARE_STATE_BLOCKED')
    attempt=result['attempt']
    folder=s.pilot_dir(ws,job,attempt)
    st=s.read_obj(folder/'state.json')
    need(st['native_jsx_sha256']==data['record']['native_jsx_sha256'] and
         st['accepted_zip_sha256']==data['archive_sha256'],'ATTEMPT_SOURCE_BINDING_DRIFT')
    binding={'schema_version':SCHEMA,'job_id':job,'attempt_id':attempt,
             'archive_sha256':data['archive_sha256'],'zip_name':data['zip_name'],
             'jsx_sha256':data['record']['native_jsx_sha256'],
             'manifest_sha256':data['record']['manifest_sha256'],
             'studio_renderer_sha256':sha((ROOT/'scripts/graphic_design_lab/greeting_cards/illustrator_studio_renderer_v1.jsx').read_bytes()),
             'native_dispatch_count_max':1,'automatic_retry':False,
             'independent_intake_review_attested':False,'visual_approved':False,'production_ready':False}
    s.write_json_x(folder/BINDING,binding)
    store_claim_attempt(data,attempt)
    print('STUDIO_DYNAMIC_ATTEMPT='+attempt+' STATE='+result['state'],flush=True)
    return attempt

def bind_attempt(data,attempt):
    need(ATTEMPT.fullmatch(attempt or ''),'ATTEMPT_ID_INVALID')
    s=data['s'];ws=data['ws'];job=data['job_id']
    folder=s.pilot_dir(ws,job,attempt)
    r=s.read_obj(folder/BINDING)
    need(r.get('schema_version')==SCHEMA and r.get('job_id')==job and r.get('attempt_id')==attempt,
         'NOT_DYNAMIC_STUDIO_ATTEMPT')
    need(r.get('archive_sha256')==data['archive_sha256'] and
         r.get('jsx_sha256')==data['record']['native_jsx_sha256'] and
         r.get('manifest_sha256')==data['record']['manifest_sha256'],
         'NATIVE_BINDING_SOURCE_CHANGED')
    need(r.get('native_dispatch_count_max')==1 and r.get('automatic_retry') is False and
         r.get('production_ready') is False and r.get('visual_approved') is False and
         r.get('independent_intake_review_attested') is False,'NATIVE_AUTHORITY_DRIFT')
    st=s.read_obj(folder/'state.json')
    native=s.native_run_dir(ws,job,attempt)
    need(st.get('native_jsx_sha256')==r['jsx_sha256'] and st.get('accepted_zip_sha256')==r['archive_sha256'],
         'NATIVE_STATE_SOURCE_DRIFT')
    need(regular(native/'run_in_illustrator.jsx') and
         sha((native/'run_in_illustrator.jsx').read_bytes())==r['jsx_sha256'],
         'NATIVE_JSX_TAMPER')
    need(regular(native/'scene_manifest.json') and
         sha((native/'scene_manifest.json').read_bytes())==r['manifest_sha256'],
         'NATIVE_MANIFEST_TAMPER')
    for name,digest in data['work']['assets'].items():
        p=native/'assets'/name
        need(regular(p) and sha(p.read_bytes())==sha(digest),'NATIVE_ASSET_TAMPER_'+name)
    return r

def confirm_once(data):
    need(sys.stdin.isatty() and sys.stdout.isatty(),'INTERACTIVE_OPERATOR_TTY_REQUIRED')
    token='LAB_NATIVE_ONCE '+data['job_id']+' '+data['archive_sha256'][:12]
    print('УВАГА: один ЛАБОРАТОРНИЙ запуск Illustrator; НЕ production, НЕ погодження дизайну.')
    print('Intake review лише заявлений у ZIP, незалежного підтвердження немає.')
    print('Повторний запуск тієї самої пари ZIP+job автоматично ЗАБОРОНЕНО.')
    print('Введи точно:',token,flush=True)
    need(input('Підтвердження: ').strip()==token,'OPERATOR_DID_NOT_CONFIRM_SINGLE_USE')

def source_pilot(data,minutes=24):
    need(data['native_supported'],'PORTRAIT_NATIVE_TRANSPORT_NOT_SUPPORTED')
    need(1<=minutes<=30,'TIMEOUT_OUTSIDE_BOUNDS')
    ui=ConsoleProgress(data['job_id'],data['zip_name'])
    ui.milestone('INPUT')
    ui.warning('Review Intake із ZIP не є незалежним підтвердженням')
    confirm_once(data)
    ui.active('Оператор дозволив одну спробу · перевірка Windows/SSH')
    shadow,bc,t=data['shadow'],data['bc'],data['t']
    with bc.Exclusive():
        # Check all incumbent Windows/SSH source pins before irreversible claim.
        _,life,_=bc.sources()
        s,gc29=t.source_check()
        need(s.workspace(data['client'])==data['ws'],'CLIENT_WORKSPACE_DRIFT')
        t.ssh_options();life.prepare(t);t.windows_preflight()
        ui.milestone('PREFLIGHT')
        claim=create_claim(data)
        print('STUDIO_DYNAMIC_SINGLE_USE_CLAIM='+str(claim),flush=True)
        ui.warning('Одноразовий claim зафіксовано: повторний pilot заборонений')
        attempt=staged_prepare(data)
        bind_attempt(data,attempt)
        ui.milestone('PREPARED')
        transport=t.make_transport(s,data['ws'],data['job_id'],attempt)
        t.stage_remote(transport,attempt)
        ui.milestone('TRANSFER')
        response=t.kv_output(t.controller_command(attempt,'launch'))
        need(response.get('T1_LAUNCH')=='START_REQUESTED_SINGLE_USE','NATIVE_LAUNCH_UNCERTAIN_NO_RETRY')
        print('STUDIO_DYNAMIC_NATIVE=START_REQUESTED_SINGLE_USE',flush=True)
        ui.milestone('REQUESTED')
        ui.active('Очікуємо підтвердження native-результату; запуск запитано, не завершено')
        started=time.monotonic()
        end=started+minutes*60
        while time.monotonic()<end:
            state=t.status_remote(attempt).get('T1_NATIVE_STATE')
            if state=='AI_REOPENED_VISUAL_REVIEW_REQUIRED':
                ui.milestone('NATIVE')
                ui.active('Отримання та незалежна перевірка AI/PDF/PNG у клієнтському output')
                return collect(data,attempt,with_lock=False,progress=ui)
            if state=='BLOCKED_REVIEW_PARTIAL_OUTPUT':
                ui.error('Windows Worker повідомив про частковий результат; лише status/collect, НЕ повтор pilot')
                print('STUDIO_DYNAMIC_NATIVE=BLOCKED_PARTIAL_OUTPUT_STATUS_ONLY',flush=True)
                print('STUDIO_DYNAMIC_ATTEMPT='+attempt,flush=True)
                return 3
            ui.heartbeat(time.monotonic()-started,state)
            time.sleep(10)
        print('STUDIO_DYNAMIC_ATTEMPT='+attempt,flush=True)
        ui.warning('Ліміт очікування минув; стан невизначений, це НЕ доказ зависання Illustrator')
        raise Blocked('NATIVE_PENDING_USE_STATUS_OR_COLLECT_NO_RELAUNCH')

def collect(data,attempt,with_lock=True,progress=None):
    need(data['native_supported'],'PORTRAIT_NATIVE_TRANSPORT_NOT_SUPPORTED')
    bind_attempt(data,attempt)
    _,bc,t=data['shadow'],data['bc'],data['t']
    def action():
        _,life,_=bc.sources()
        s,_=t.source_check()
        t.collect_remote(s,data['ws'],data['job_id'],attempt)
        review=s.read_obj(s.review_dir(data['ws'],data['job_id'],attempt)/'verify.json')
        need(review['source_jsx_sha256']==data['record']['native_jsx_sha256'] and
             review['visual_approved'] is False and review['production_ready'] is False,
             'DYNAMIC_NATIVE_REVIEW_PROVENANCE_INVALID')
        print('STUDIO_DYNAMIC_REVIEW=CLIENT_OUTPUT_PUBLISHED_VISUAL_REVIEW_REQUIRED',flush=True)
        proof=published_review_state(s,data['ws'],data['job_id'],attempt,data['archive_sha256'])
        need(proof.get('status')==READY,'PUBLISHED_REVIEW_INDEPENDENT_RECHECK_FAILED')
        ui=progress or ConsoleProgress(data['job_id'],data['zip_name'])
        ui.milestone('OUTPUT')
        ui.ready(proof['review_relative'])
        try:life.prepare(t)
        except Exception:
            print('STUDIO_DYNAMIC_POSTFLIGHT=REQUIRES_OPERATOR_CHECK_NO_FORCE_KILL',flush=True)
            ui.warning('Результат опубліковано, але Illustrator потребує ручної перевірки завершення')
            return 3
        print('STUDIO_DYNAMIC_POSTFLIGHT=PASS_ILLUSTRATOR_CLOSED',flush=True)
        ui.milestone('POSTFLIGHT')
        return 0
    if not with_lock:return action()
    with bc.Exclusive():return action()

def batch_status(client,zip_name):
    """Review existing immutable claims/outputs for every job. Never dispatch."""
    shadow,bc,t=load_sources()
    audit=shadow.load_py(shadow.AUDIT,'studio_progress_batch_audit')
    s=shadow.load_py(shadow.GC47S,'studio_progress_batch_gc47s')
    archive=shadow.input_archive(audit,client,zip_name)
    result=audit.audit(archive)
    need(result.get('status')=='HANDOFF_STRUCTURAL_PASS_STUDIO_BINDING_REQUIRED',
         'BATCH_NOT_ACCEPTED_HANDOFF')
    digest=sha(archive.read_bytes());ws=s.workspace(client)
    with zipfile.ZipFile(archive) as z:
        document=audit.load_yaml(z.read('accepted_constructor_bundle.yaml'))
        jobs=document.get('jobs')
    need(isinstance(jobs,list) and 0<len(jobs)<=200,'BATCH_JOB_COUNT_INVALID')
    names=[j.get('job_id') if isinstance(j,dict) else None for j in jobs]
    need(all(isinstance(n,str) and s.ID_RE.fullmatch(n) for n in names) and len(set(names))==len(names),
         'BATCH_JOB_IDS_INVALID')
    rows=[]
    for jid in names:
        claim=attempt_from_claim(ws,digest,jid)
        row={'job_id':jid,'status':claim['status']}
        if claim['status']=='ATTEMPT_EXISTS':
            row.update(published_review_state(s,ws,jid,claim['attempt_id'],digest))
            if row['status']=='NOT_PUBLISHED':row['status']='ATTEMPT_EXISTS_RESULT_PENDING_OR_UNKNOWN'
            row['attempt_id']=claim['attempt_id']
        rows.append(row)
    ui=ConsoleProgress('ОГЛЯД ВСЬОГО BATCH',zip_name,batch_total=len(rows))
    ui.batch(rows)
    print('STUDIO_BATCH_STATUS='+json.dumps({'schema_version':'studio_batch_readonly_progress_v1',
          'total':len(rows),'ready_for_visual_review':sum(r['status']==READY for r in rows),
          'automatic_queue':False,'production_ready':False,'rows':rows},ensure_ascii=False,sort_keys=True))
    return 0

def run(mode,client,zip_name,job_id,attempt=None,timeout=24):
    if mode=='batch-status':return batch_status(client,zip_name)
    if mode=='pilot':print('[..] Аналіз Intake ZIP, нормалізація сцен і перевірка ресурсів (без native)',flush=True)
    data=preflight(client,zip_name,job_id)
    if mode=='plan':
        print(json.dumps(public_plan(data),ensure_ascii=False,sort_keys=True,indent=2))
        return 0 if data['native_supported'] else 3
    if mode=='claim-status':return claim_status(data)
    if mode=='pilot':return source_pilot(data,timeout)
    if mode in ('status','collect'):
        bind_attempt(data,attempt)
        if mode=='status':
            data['t'].mode_status(data['s'],client,job_id,attempt)
            proof=published_review_state(data['s'],data['ws'],job_id,attempt,data['archive_sha256'])
            ui=ConsoleProgress(job_id,zip_name)
            if proof.get('status')==READY:ui.ready(proof['review_relative'])
            elif proof.get('status')=='REVIEW_VERIFICATION_BLOCKED':ui.error('Опубліковані файли є, але перевірка їх цілісності НЕ пройдена')
            else:ui.warning('Результат ще не підтверджено в клієнтському output: '+proof['status'])
            return 0
        return collect(data,attempt)
    raise Blocked('MODE_UNKNOWN')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('plan','pilot','claim-status','status','collect','batch-status'),required=True)
    p.add_argument('--client-name',required=True)
    p.add_argument('--zip-name',required=True)
    p.add_argument('--job-id')
    p.add_argument('--attempt-id')
    p.add_argument('--timeout-minutes',type=int,default=24)
    a=p.parse_args(argv)
    try:
        if a.mode in ('status','collect'):need(bool(a.attempt_id),'ATTEMPT_ID_REQUIRED')
        else:need(not a.attempt_id,'UNEXPECTED_ATTEMPT_ID')
        if a.mode=='batch-status':need(not a.job_id,'BATCH_STATUS_NO_SELECTED_JOB')
        else:need(bool(a.job_id),'JOB_ID_REQUIRED')
        return run(a.mode,a.client_name,a.zip_name,a.job_id,a.attempt_id,a.timeout_minutes)
    except (Blocked,RuntimeError,ValueError,KeyError,TypeError,OSError,ImportError,zipfile.BadZipFile,subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
        code=str(e) if isinstance(e,Blocked) else type(e).__name__.upper()
        print('STUDIO_DYNAMIC_NATIVE=BLOCKED_'+re.sub('[^A-Z0-9_]','_',code.upper())[:128],file=sys.stderr)
        ConsoleProgress('ПОМИЛКА','операторська операція',stream=sys.stderr).error(
            'BLOCKED: '+re.sub('[^A-Z0-9_]','_',code.upper())[:128]+' · pilot НЕ повторювати')
        print('STUDIO_DYNAMIC_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
