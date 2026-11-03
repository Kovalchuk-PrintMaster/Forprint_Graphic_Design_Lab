#!/usr/bin/env python3
"""ForPrint Illustrator Studio: one canonical 4-page JSX renderer + config + passport.

One editable renderer for ALL profile variations. GC47BM is a read-only intake
compatibility adapter for the currently accepted four pilot jobs; GC47BC/GC47T
remain trusted transport/lifecycle adapters only. NONE of the historical P04
transformers are involved in native JSX generation. LAB ONLY, fail closed.
"""
from __future__ import annotations
import argparse, base64, hashlib, importlib.util, json, os, re, stat, sys, tempfile, time
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'scripts/graphic_design_lab/greeting_cards'
BASE=ROOT/'coordination/graphic_design_lab/greeting_cards/illustrator_studio'
CFG=BASE/'design_config_v1.json'
JSX=SRC/'illustrator_studio_renderer_v1.jsx'
PASSPORT=BASE/'technical_passport_v1.json'
BM=SRC/'gc47bm_unified_native_work_shadow_r001.py'
BC=SRC/'gc47bc_profile_native_review_r001.py'
BM_SHA='2a48585844e57f8bfdf420e0ec1146f7e7a337f1f022ce4d7b7ccf0995fd4f2b'
BC_SHA='1ce159b623de30f2128048553d845ffb30ed344643685bbd2b84293502346169'
ZAP='gdl_gc_zap_20261011'
JOBS=(ZAP,'gdl_gc_apa_20261011','gdl_gc_deg_20261011','gdl_gc_bas_20261011')
ATTEMPT=re.compile(r'^p\d{14}-[a-f0-9]{8}$')
RECEIPT='illustrator_studio_native_binding_v1.json'
SCHEMA='forprint_illustrator_studio_attempt_v1'
CONFIRM='ILLUSTRATOR_STUDIO_SINGLE_NATIVE '

class Blocked(RuntimeError): pass
def need(test,why):
    if not test:raise Blocked(why)
def sha(value):return hashlib.sha256(value).hexdigest()
def regular(path):
    try:return stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink()
    except OSError:return False
def safe_json(path,max_bytes=100000):
    need(regular(path) and path.stat().st_size<=max_bytes,'FILE_UNAVAILABLE_'+path.name.upper())
    return json.loads(path.read_text('utf8'))
def load_python(path,digest,key):
    need(regular(path) and sha(path.read_bytes())==digest,'LEGACY_INTAKE_PIN_DRIFT_'+path.name.upper())
    spec=importlib.util.spec_from_file_location(key,path)
    need(spec is not None and spec.loader is not None,'MODULE_IMPORT_FAILED')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def config():
    d=safe_json(CFG)
    need(d.get('schema_version')=='forprint_illustrator_studio_design_v1','CONFIG_SCHEMA')
    need(d.get('page_mm')==[214,301] and d.get('gap_mm')==18,'CANVAS_UNSUPPORTED')
    need(tuple(d.get('allowed_profiles',()))==JOBS,'JOB_CONTRACT_CHANGED')
    need(d.get('shared_design_release_id')=='efa4ab376797978c52835f5e14e228789c0951763cf2ac72462c670fd82eec83','SHARED_DESIGN_RELEASE_UNVERIFIED')
    p=d['p04']
    need(p['text_box_mm']==[32,32,150,180] and p['font_name']=='ZapfChanceryC','P04_UNSUPPORTED_GEOMETRY_OR_FONT')
    need(p['max_chars']<=1500 and 0<p['long_text_threshold']<p['max_chars'],'POLICY_BOUNDS')
    for k in ('short_tiers_pt','long_tiers_pt'):
        rows=p[k];need(1<=len(rows)<=12 and all(type(n) in (int,float) and 10<=n<=25 for n in rows),'TIER_INVALID')
    need(d['sender']['font_sizes_pt'] and len(d['sender']['font_sizes_pt'])==len(d['sender']['baselines_mm'])==4,'SENDER_LAYOUT')
    need(d['p03']['frame_asset_policy']=='SHARED_RELEASE_FIXED_ROLE_P03_FRAME','P03_FRAME_SOURCE_CHANGED')
    need(all(d['policy'].get(x) is False for x in ('production_ready','visual_approved','automatic_retry','automatic_queue','tmp_runtime_dependency')),'AUTOMATION_AUTHORITY_CHANGED')
    return d

def render_template():
    need(regular(JSX),'RENDERER_UNAVAILABLE')
    b=JSX.read_bytes();need(10000<len(b)<100000,'RENDERER_SIZE')
    s=b.decode('utf8')
    need(s.count('/*__GC29_SCENE__*/')==1 and s.count('function greeting(font)')==1 and s.count('function sender(font)')==1,'RENDERER_FORMAT')
    a=s.split('  function greeting(font){',1)[1].split('  function sender(font){',1)[0]
    need('t.remove()' in a and 'visible===exact' in a and 'app.redraw()' not in a and 'ch.size=' not in a and 'ch.leading=' not in a,'RENDERER_P04_SAFETY')
    need('scene.studio_settings' in s and 'production_ready":false' in s,'RENDERER_PROVENANCE_OR_AUTHORITY')
    return s

def dependencies():
    need(ROOT.name=='forprint_graphic_design_lab' and (ROOT/'.git').is_dir(),'GDL_REPO_REQUIRED')
    bm=load_python(BM,BM_SHA,'studio_pinned_gc47bm_intake')
    bc=load_python(BC,BC_SHA,'studio_pinned_gc47bc_transport')
    need(bm.EXPECTED_RELEASE==config()['shared_design_release_id'] and set(JOBS)==set(bm.JOBS),'INTAKE_RELEASE_OR_JOB_SET')
    need(set(bc.JOBS)==set(JOBS)-{ZAP},'TRANSPORT_JOB_SET')
    return bm,bc

def compile_profiles(client,bm,bc):
    compiled,proof=bm.compile_from_pinned(ROOT,client)
    need(proof.get('status')=='PASS_FOUR_SOURCE_REBUILT_NATIVE_MANIFESTS_NO_WINDOWS' and set(compiled)==set(JOBS),'INTAKE_FOUR_PROFILES_NOT_VERIFIED')
    for job in JOBS:
        scene,legacy_jsx,manifest,assets,_=compiled[job]
        need(scene.get('job_id')==job and scene.get('pages')==4 and scene.get('production_ready') is False,'INTAKE_SCENE')
        need(len(assets) in (12,13),'INTAKE_ASSETS')
        original=json.loads(manifest.decode('utf8'))
        need(original['jsx_sha256']==sha(legacy_jsx) and set(original['asset_sha256'])==set(assets),'INTAKE_MANIFEST_SOURCE_MISMATCH')
        for name,blob in assets.items():need(sha(blob)==original['asset_sha256'][name],'INTAKE_ASSET_DRIFT')
    return compiled

def candidate(job,compiled,settings,source):
    scene,legacy_jsx,oldmanifest,assets,kind=compiled[job]
    newscene=dict(scene);newscene['studio_settings']=settings
    newscene['studio_renderer']='ILLUSTRATOR_STUDIO_ONE_CANONICAL_JSX_V1'
    jsx=source.replace('/*__GC29_SCENE__*/',json.dumps(newscene,ensure_ascii=True,separators=(',',':'))).encode('utf8')
    parsed=json.loads(oldmanifest.decode('utf8'))
    parsed['jsx_sha256']=sha(jsx)
    parsed['studio_renderer_sha256']=sha(source.encode('utf8'))
    parsed['studio_design_config_sha256']=sha(CFG.read_bytes())
    parsed['studio_version']='v1'
    parsed['studio_source']='ONE_RENDERER_FOR_ALL_FOUR_PROFILES'
    parsed['production_ready']=False;parsed['visual_approved']=False
    manifest=(json.dumps(parsed,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    return {'scene':newscene,'original_sha':sha(legacy_jsx),'jsx':jsx,'jsx_sha':sha(jsx),
            'manifest':manifest,'assets':assets,'shared_release':settings['shared_design_release_id'],
            'renderer_sha':sha(source.encode('utf8')),'design_sha':sha(CFG.read_bytes()),'intake_kind':kind}

def atomic_replace(path,data):
    need(regular(path),'STAGED_FILE_NOT_REGULAR')
    fd,temp=tempfile.mkstemp(prefix='.studio_',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o640);os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def context(client,job,bc):
    if job!=ZAP:return bc.profile_inputs(client,job)
    bb,life,post=bc.sources()
    az=bb.az_module(ROOT,bc.CAN)
    t=az.module(ROOT,'gc47t_client_windows_bridge_r001.py','studio_transport')
    s,gc29=t.source_check()
    ws,j,archive,variant=t.validate_job(s,gc29,client,job)
    need(bc.file_sha(archive)==bc.ACCEPTED_SHA,'ZAP_ACCEPTED_ARCHIVE_CHANGED')
    return {'t':t,'s':s,'gc29':gc29,'life':life,'post':post,
            'ws':ws,'job':j,'archive':archive,'client':client,'job_id':job}

def prepare_attempt(data,candidate,bc):
    s=data['s'];gc29=data['gc29'];ws=data['ws'];job=data['job_id']
    _,passport=s.current_passport()
    original=gc29.prepare;written={}
    def prepare(workspace,jid,attempt):
        need(workspace==ws and jid==job and ATTEMPT.fullmatch(attempt),'ATTEMPT_SCOPE')
        result=original(workspace,jid,attempt)
        run=s.native_run_dir(workspace,jid,attempt)
        jsx=run/'run_in_illustrator.jsx';manifest=run/'scene_manifest.json';directory=run/'assets'
        need(regular(jsx) and regular(manifest) and directory.is_dir() and not directory.is_symlink(),'PREPARED_WORK_MISSING')
        obj=s.read_obj(manifest)
        need(obj.get('job_id')==jid and obj.get('pages')==4 and obj.get('jsx_sha256')==sha(jsx.read_bytes()),'PREPARED_WORK_BINDING')
        if jid!=ZAP:need(sha(jsx.read_bytes())==candidate['original_sha'],'GENERIC_SOURCE_CHANGED')
        need(set(x.name for x in directory.iterdir())==set(candidate['assets']),'PREPARED_ASSETS_NOT_SOURCE_BOUND')
        # ZAP intentionally overrides the historical default photo; common resolver is authority.
        for name,blob in candidate['assets'].items():
            dest=directory/name;need(regular(dest),'UNSAFE_ASSET_'+name)
            if jid!=ZAP:need(sha(dest.read_bytes())==sha(blob),'PREPARED_ASSET_DRIFT_'+name)
        for name,blob in candidate['assets'].items():atomic_replace(directory/name,blob)
        atomic_replace(jsx,candidate['jsx']);atomic_replace(manifest,candidate['manifest'])
        need(sha(jsx.read_bytes())==candidate['jsx_sha'] and s.read_obj(manifest)['jsx_sha256']==candidate['jsx_sha'],'STUDIO_STAGE_VERIFY')
        written['sha']=candidate['jsx_sha']
        return result
    gc29.prepare=prepare
    try:r=s.start_one(gc29,ws,data['job'],data['archive'],passport,job)
    finally:gc29.prepare=original
    need(r is not None,'NO_ATTEMPT_CREATED')
    attempt=r['attempt']
    print('STUDIO_ATTEMPT='+attempt+' STATE='+r['state'],flush=True)
    need(r['state']=='PREPARED_WINDOWS_EXECUTION_NOT_WIRED' and written.get('sha')==candidate['jsx_sha'],'PREPARE_INCOMPLETE_NO_RETRY')
    folder=s.pilot_dir(ws,job,attempt)
    need(s.read_obj(folder/'state.json')['native_jsx_sha256']==candidate['jsx_sha'],'STATE_JSX_SHA_MISMATCH')
    s.write_json_x(folder/RECEIPT,{
      'schema_version':SCHEMA,'job_id':job,'attempt_id':attempt,
      'source_jsx_sha256':candidate['original_sha'],
      'native_jsx_sha256':candidate['jsx_sha'],
      'canonical_renderer_sha256':candidate['renderer_sha'],
      'canonical_design_sha256':candidate['design_sha'],
      'shared_release_id':candidate['shared_release'],
      'accepted_zip_sha256':bc.ACCEPTED_SHA,'one_canonical_renderer':True,
      'native_dispatch_count_max':1,'automatic_retry':False,
      'visual_approved':False,'production_ready':False,
      'technical_passport':'coordination/graphic_design_lab/greeting_cards/illustrator_studio/technical_passport_v1.json',
      'visual_issues':['P03_LEGACY_FRAME','P04_SENDER_SIGNATURE_COLLISION']})
    return attempt

def bound(data,attempt,bc):
    need(ATTEMPT.fullmatch(attempt or '') is not None,'ATTEMPT_ID_REQUIRED')
    s=data['s'];ws=data['ws'];job=data['job_id']
    base=s.pilot_dir(ws,job,attempt)
    r=s.read_obj(base/RECEIPT)
    need(r.get('schema_version')==SCHEMA and r.get('job_id')==job and r.get('attempt_id')==attempt,'NOT_STUDIO_ATTEMPT')
    need(r.get('shared_release_id')==config()['shared_design_release_id'] and r.get('accepted_zip_sha256')==bc.ACCEPTED_SHA,'ATTEMPT_SOURCE_PROVENANCE')
    need(r.get('one_canonical_renderer') is True and r.get('native_dispatch_count_max')==1 and r.get('automatic_retry') is False and r.get('production_ready') is False and r.get('visual_approved') is False,'ATTEMPT_AUTHORITY')
    path=s.native_run_dir(ws,job,attempt)
    need(s.read_obj(base/'state.json').get('native_jsx_sha256')==r['native_jsx_sha256'],'STATE_DRIFT')
    need(regular(path/'run_in_illustrator.jsx') and sha((path/'run_in_illustrator.jsx').read_bytes())==r['native_jsx_sha256'],'JSX_TAMPER')
    need(s.read_obj(path/'scene_manifest.json').get('jsx_sha256')==r['native_jsx_sha256'],'MANIFEST_TAMPER')
    return r

def collect(data,attempt,bc):
    receipt=bound(data,attempt,bc)
    t=data['t'];s=data['s'];ws=data['ws'];job=data['job_id']
    t.collect_remote(s,ws,job,attempt)
    review=s.read_obj(s.review_dir(ws,job,attempt)/'verify.json')
    need(review.get('attempt_id')==attempt and review.get('job_id')==job and review.get('source_jsx_sha256')==receipt['native_jsx_sha256'],'REVIEW_PROVENANCE')
    need(review.get('production_ready') is False and review.get('visual_approved') is False,'REVIEW_AUTHORITY')
    print('STUDIO_NATIVE_REVIEW=PUBLISHED_NON_RELEASE',flush=True)
    print('STUDIO_REVIEW_RELATIVE='+str(s.review_dir(ws,job,attempt).relative_to(ws)),flush=True)
    return bc.safe_postflight(data)

def run_one(data,c,bc,timeout):
    t=data['t'];life=data['life'];s=data['s'];ws=data['ws'];job=data['job_id']
    with bc.Exclusive():
        t.ssh_options();life.prepare(t);t.windows_preflight()
        attempt=prepare_attempt(data,c,bc)
        bound(data,attempt,bc)
        transport=t.make_transport(s,ws,job,attempt)
        t.stage_remote(transport,attempt)
        result=t.kv_output(t.controller_command(attempt,'launch'))
        need(result.get('T1_LAUNCH')=='START_REQUESTED_SINGLE_USE','LAUNCH_UNCERTAIN_NO_RETRY')
        print('STUDIO_NATIVE=START_REQUESTED_SINGLE_USE',flush=True)
        until=time.monotonic()+timeout*60
        while time.monotonic()<until:
            current=t.status_remote(attempt)['T1_NATIVE_STATE']
            if current=='AI_REOPENED_VISUAL_REVIEW_REQUIRED':return collect(data,attempt,bc)
            if current=='BLOCKED_REVIEW_PARTIAL_OUTPUT':
                print('STUDIO_NATIVE=BLOCKED_PARTIAL_OUTPUT_STATUS_ONLY',flush=True)
                print('STUDIO_ATTEMPT='+attempt,flush=True);return 2
            time.sleep(10)
        print('STUDIO_ATTEMPT='+attempt,flush=True)
        raise Blocked('PENDING_STATUS_ONLY_NO_RETRY')

def passport_summary():
    p=safe_json(PASSPORT)
    need(p['schema_version']=='forprint_illustrator_studio_technical_passport_v1','PASSPORT_SCHEMA')
    print('STUDIO_PASSPORT_STATUS='+p['status'])
    print('STUDIO_PASSPORT_OPEN='+str(len([v for v in p['issues'] if v['status'].startswith('OPEN')])))
    for i in p['issues']:
        print(i['id']+'='+i['status']+' '+i['title'])
    return 0

def export_passport():
    """Regenerate human-readable view from the single canonical JSON only."""
    source=safe_json(PASSPORT)
    need(source.get('schema_version')=='forprint_illustrator_studio_technical_passport_v1','PASSPORT_SCHEMA')
    rows=['# ForPrint Illustrator Studio — технічний паспорт (генерується з JSON)','',
          '**Єдине джерело:** `technical_passport_v1.json`. Не редагувати це представлення.','',
          '**Статус:** '+source['status'],'','## Контрольні native-прогони (історичні)','']
    for item in source['proven_native_reference']:
        rows.append('- `'+item['job_id']+'` — '+item['attempt']+'; '+item['native']+'; '+item['visual'])
    rows+=['','## Проблеми й рішення','']
    for issue in source['issues']:
        rows+=['### '+issue['id']+' — '+issue['title'],'',
               '- Статус: `'+issue['status']+'`',
               '- Причина: '+issue.get('cause',''),
               '- Рішення: '+issue.get('resolution',''),
               '- Перевірка: '+issue.get('verification',''),'']
    rows+=['## Правило змін','',source['change_policy'],'',
           'Production-ready=false, visual-approved=false, queue=false.','']
    output=BASE/'TECHNICAL_PASSPORT_VIEW_UA.md'
    need(output.parent.is_dir() and not output.parent.is_symlink(),'PASSPORT_DIR')
    content=('\n'.join(rows)).encode('utf8')
    if output.exists():atomic_replace(output,content)
    else:
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o644)
        with os.fdopen(fd,'wb') as f:f.write(content)
    print('STUDIO_PASSPORT_EXPORT=PASS_DERIVED_FROM_SINGLE_JSON')
    return 0

def inspect(client,check_windows):
    settings=config();source=render_template();bm,bc=dependencies()
    rows=compile_profiles(client,bm,bc)
    for job in JOBS:
        c=candidate(job,rows,settings,source)
        print('STUDIO_PROFILE='+job+' RENDERER_SHA='+c['renderer_sha']+' JSX_SHA='+c['jsx_sha']+' ASSETS='+str(len(c['assets'])))
    if check_windows:
        # Read-only GUI check once, not four repeated remote checks.
        d=context(client,'gdl_gc_deg_20261011',bc)
        bc.readonly_preflight(d)
    print('STUDIO_ONE_CANONICAL_RENDERER=PASS NO_NATIVE_DISPATCH=TRUE')
    return 0

def encode_client(client):
    return base64.urlsafe_b64encode(client.encode('utf8')).decode('ascii').rstrip('=')
def decode_client(token):
    need(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,900}',token or '')),'CLIENT_TOKEN')
    c=base64.urlsafe_b64decode(token+'='*((-len(token))%4)).decode('utf8')
    need(bool(c.strip()) and len(c)<160 and '\x00' not in c and c not in ('.','..'),'CLIENT_VALUE')
    need(encode_client(c)==token,'CLIENT_CANONICAL_TOKEN')
    return c

def interactive(client):
    print('\nFORPRINT ILLUSTRATOR STUDIO v1 — ONE CANONICAL RENDERER')
    print('Чотири профілі; native лабораторний, без автоматичного повтору.')
    while True:
        print('\n1. Джерела / план (без Illustrator)')
        print('2. Створити листівку (один native-запуск)')
        print('3. Технічний паспорт')
        # STUDIO_INTAKE_INSTRUCTION_MENU_V1_BEGIN
        print('4. Згенерувати ZIP-інструкцію для Intake (без Illustrator)')
        print('5. Перевірити ZIP у клієнтському input (без Illustrator)')
        # STUDIO_INTAKE_INSTRUCTION_MENU_V1_END
        # STUDIO_DYNAMIC_SOURCE_SHADOW_MENU_V1_BEGIN
        print('6. Попередня перевірка нового Intake ZIP (один JSX, без Illustrator)')
        # STUDIO_DYNAMIC_SOURCE_SHADOW_MENU_V1_END
        # STUDIO_DYNAMIC_NATIVE_LAB_MENU_V1_BEGIN
        print('7. Один лабораторний native-запуск нового Intake ZIP (тільки DEFAULT_ASSET)')
        # STUDIO_DYNAMIC_NATIVE_LAB_MENU_V1_END
        # STUDIO_PROGRESS_MENU_V1_BEGIN
        print('8. Прогрес усіх листівок у Intake ZIP (без Illustrator)')
        # STUDIO_PROGRESS_MENU_V1_END
        print('0. Вийти')
        choice=input('Дія: ').strip()
        # STUDIO_DYNAMIC_SOURCE_SHADOW_ACTIONS_V1_BEGIN
        if choice=='6':
            file_name=input('Точна назва Handoff ZIP з клієнтської папки input: ').strip()
            if not file_name:print('Скасовано.');continue
            code=subprocess.run([sys.executable,'-B',str(SRC/'illustrator_studio_intake_dynamic_preflight_v1.py'),
                                 '--client-name',client,'--zip-name',file_name],check=False).returncode
            if code:print('Новий пакет потребує доопрацювання / перевірки; код:',code)
            continue
        # STUDIO_DYNAMIC_SOURCE_SHADOW_ACTIONS_V1_END
        # STUDIO_DYNAMIC_NATIVE_LAB_ACTIONS_V1_BEGIN
        if choice=='7':
            z=input('Назва прийнятого Handoff ZIP у input: ').strip()
            j=input('Точний job_id з Handoff: ').strip()
            if not z or not j:print('Скасовано.');continue
            args=[sys.executable,'-B',str(SRC/'illustrator_studio_intake_dynamic_native_v1.py'),
                  '--client-name',client,'--zip-name',z,'--job-id',j]
            code=subprocess.run([*args,'--mode','plan'],check=False).returncode
            if code:print('Native-пілот заблокований; перевір план.');continue
            print('Виконається одна native-спроба після окремого точного підтвердження.')
            code=subprocess.run([*args,'--mode','pilot'],check=False).returncode
            if code:print('Пілот не завершено; не повторюй команду. Перевір claim/status. Код:',code)
            continue
        # STUDIO_DYNAMIC_NATIVE_LAB_ACTIONS_V1_END
        # STUDIO_PROGRESS_ACTIONS_V1_BEGIN
        if choice=='8':
            z=input('Назва прийнятого Handoff ZIP у input: ').strip()
            if not z:print('Скасовано.');continue
            argv=[sys.executable,'-B',str(SRC/'illustrator_studio_intake_dynamic_native_v1.py'),
                  '--mode','batch-status','--client-name',client,'--zip-name',z]
            subprocess.run(argv,check=False)
            continue
        # STUDIO_PROGRESS_ACTIONS_V1_END
        if choice=='0':return 0
        if choice=='1':inspect(client,False);continue
        if choice=='3':passport_summary();continue
        # STUDIO_INTAKE_INSTRUCTION_ACTIONS_V1_BEGIN
        if choice=='4':
            code=subprocess.run([sys.executable,'-B',str(SRC/'illustrator_studio_intake_instruction_v1.py'),
                                 '--mode','generate','--client-name',client],check=False).returncode
            if code:print('Генерацію заблоковано; причина в журналі вище. Код:',code)
            continue
        if choice=='5':
            code=subprocess.run([sys.executable,'-B',str(SRC/'illustrator_studio_intake_audit_v1.py'),
                                 '--client-name',client],check=False).returncode
            if code:print('Аудит не завершено; причина в журналі вище. Код:',code)
            continue
        # STUDIO_INTAKE_INSTRUCTION_ACTIONS_V1_END
        if choice!='2':print('Невідома дія');continue
        for i,j in enumerate(JOBS,1):print(str(i)+'. '+j)
        num=input('Номер профілю, або 0: ').strip()
        if num=='0':continue
        if num not in '1234' or len(num)!=1:print('Невідомий профіль');continue
        job=JOBS[int(num)-1];confirmation=CONFIRM+job
        print('Це створить РІВНО ОДНУ нову спробу Illustrator. Попередній attempt не повторюється.')
        print('Дозвіл:',confirmation)
        if input('Введи дослівно дозвіл: ').strip()!=confirmation:
            print('Скасовано.');continue
        return execute('pilot',client,job,None,24,True,confirmation)

def execute(mode,client,job,attempt,timeout,authorized,confirmation):
    if mode=='passport':return passport_summary()
    if mode=='passport-export':return export_passport()
    if mode=='check':
        config();render_template();passport_summary()
        print('STUDIO_LOCAL_CHECK=PASS_ONE_RENDERER_ONE_CONFIG_ONE_PASSPORT_NO_NATIVE')
        return 0
    need(bool(client),'CLIENT_REQUIRED')
    if mode=='interactive':return interactive(client)
    if mode in ('plan','inspect'):
        need(not job and not authorized,'PLAN_NO_JOB_OR_AUTHORITY')
        return inspect(client,mode=='inspect')
    need(job in JOBS,'UNKNOWN_JOB')
    need(mode in ('pilot','status','collect'),'MODE_INVALID')
    if mode=='pilot':
        need(authorized and confirmation==CONFIRM+job,'EXPLICIT_ONE_ATTEMPT_CONFIRMATION_REQUIRED')
        need(not attempt and 1<=timeout<=30,'PILOT_ARGS')
    else:
        need(not authorized and ATTEMPT.fullmatch(attempt or ''),'READONLY_EXISTING_ATTEMPT_REQUIRED')
    bm,bc=dependencies()
    data=context(client,job,bc)
    if mode=='status':
        bound(data,attempt,bc)
        data['t'].mode_status(data['s'],client,job,attempt)
        print('STUDIO_STATUS=READ_ONLY_NO_RETRY');return 0
    if mode=='collect':
        need(confirmation=='ILLUSTRATOR_STUDIO_COLLECT_EXISTING '+job,'COLLECT_CONFIRMATION_REQUIRED')
        with bc.Exclusive():return collect(data,attempt,bc)
    settings=config();source=render_template()
    rows=compile_profiles(client,bm,bc)
    c=candidate(job,rows,settings,source)
    print('STUDIO_JOB='+job+' SOURCE=ONE_CANONICAL_JSX CONFIG='+c['design_sha'])
    return run_one(data,c,bc,timeout)

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',required=True,choices=('check','passport','passport-export','plan','inspect','interactive','pilot','status','collect'))
    ap.add_argument('--client-name');ap.add_argument('--client-b64')
    ap.add_argument('--job-id');ap.add_argument('--attempt-id')
    ap.add_argument('--timeout-minutes',type=int,default=24)
    ap.add_argument('--confirm-native-once',action='store_true');ap.add_argument('--confirmation')
    a=ap.parse_args(argv)
    try:
        need(not (a.client_name and a.client_b64),'DUPLICATE_CLIENT_ARGUMENTS')
        client=a.client_name or (decode_client(a.client_b64) if a.client_b64 else None)
        return execute(a.mode,client,a.job_id,a.attempt_id,a.timeout_minutes,a.confirm_native_once,a.confirmation)
    except (OSError,ValueError,KeyError,TypeError,Blocked,ImportError) as e:
        code=str(e) if isinstance(e,Blocked) else type(e).__name__
        safe=re.sub(r'[^A-Z0-9_]','_',code.upper())[:128]
        print('STUDIO=BLOCKED_'+safe,file=sys.stderr)
        print('STUDIO_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE',file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
