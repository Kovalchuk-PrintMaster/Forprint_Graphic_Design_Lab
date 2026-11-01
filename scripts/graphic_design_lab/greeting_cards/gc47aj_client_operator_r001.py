#!/usr/bin/env python3
"""GC47AJ: Ukrainian client-folder UI for pinned GDL GC47AI. Non-release.

The installer places an *entrypoint only* in _forprint_automation/input;
all permission-bearing operations remain in the trusted GDL repository.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
AI_PATH = ROOT / 'scripts/graphic_design_lab/greeting_cards/gc47ai_illustrator_first_launcher_r001.py'
AI_SHA256 = '9b5cf00228e1dbe543cfba0c5aac0fcc2834f2c02ced904ded5632e7e41ea210'
MAX_ATTEMPTS = 300

class Blocked(Exception):
    pass


def need(condition, reason):
    if not condition:
        raise Blocked(reason)


def file_regular(p):
    try:
        return stat.S_ISREG(p.lstat().st_mode)
    except OSError:
        return False


def folder_regular(p):
    try:
        return stat.S_ISDIR(p.lstat().st_mode)
    except OSError:
        return False


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def ai_load():
    need(ROOT.name == 'forprint_graphic_design_lab' and folder_regular(ROOT / '.git'), 'GDL_ROOT_INVALID')
    need(file_regular(AI_PATH) and digest(AI_PATH) == AI_SHA256, 'GC47AI_SOURCE_CHANGED')
    spec = importlib.util.spec_from_file_location('gc47aj_pinned_gc47ai', AI_PATH)
    need(spec is not None and spec.loader is not None, 'GC47AI_IMPORT_UNAVAILABLE')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_context(ai, input_dir):
    """Authorize only the existing direct client input folder under the GDL SMB share."""
    raw = Path(input_dir)
    need(raw.is_absolute() and folder_regular(raw), 'INPUT_FOLDER_MISSING_OR_NOT_ABSOLUTE')
    need(raw.name == 'input' and raw.parent.name == '_forprint_automation', 'NOT_CLIENT_INPUT_FOLDER')
    # Crucial: do not resolve before checking for symlinks.
    for candidate in (raw, raw.parent, raw.parent.parent, ai.SHARE):
        need(folder_regular(candidate), 'UNSAFE_FOLDER_OR_SYMLINK')
    client = raw.parent.parent.name
    ws = ai.workspace(client)
    need(ws / 'input' == raw and ws / 'input' == raw.resolve(strict=True), 'CLIENT_FOLDER_IDENTITY_MISMATCH')
    return client, ws


def choose(items, title, show=lambda x: str(x)):
    if not items:
        print('Немає доступних пунктів.')
        return None
    print('\n' + title)
    for i, item in enumerate(items, 1):
        print(f'  {i}. {show(item)}')
    while True:
        val = input('Номер (0 — назад): ').strip()
        if val in ('0', 'q', 'Q', ''):
            return None
        if val.isascii() and val.isdecimal() and 1 <= int(val) <= len(items):
            return items[int(val) - 1]
        print('Введи номер із наведеного списку або 0, щоб повернутися.')


def source_summary(ai, client, ws):
    """ZIP listing is informational; accepted archive identity comes only from GC25/GC29."""
    zips = [(z, ai.inspect_zip(z, verify_crc=True)) for z in ai.input_zips(ws)]
    jobs, archive = ai.accepted_jobs(client)
    need(file_regular(archive) and archive.parent == ws / 'input', 'ACCEPTED_ZIP_OUTSIDE_CLIENT_INPUT')
    accepted = ai.inspect_zip(archive, verify_crc=True)
    matching = [z for z, record in zips if z == archive and record['sha256'] == accepted['sha256']]
    need(len(matching) == 1, 'ACCEPTED_ZIP_NOT_UNIQUE_IN_INPUT')
    return zips, jobs, archive, accepted


def show_source(ai, client, ws):
    zips, jobs, archive, accepted = source_summary(ai, client, ws)
    print('\n=== 1. ВХІДНІ ФАЙЛИ КЛІЄНТА ===')
    print(f'У input/ знайдено ZIP-архівів: {len(zips)}')
    for p, record in zips:
        status = 'ПРИЙНЯТИЙ ДЛЯ РОБОТИ' if p == archive else 'ІНФОРМАЦІЙНИЙ / НЕ ОБРАНИЙ'
        print(f"  • {p.name}\n    {status}, CRC: OK, файлів у ZIP: {record['members']}")
    print(f'\nДжерело, яке дозволено GC25/GC29: {archive.name}')
    print('Не кожен ZIP із input/ є готовим замовленням. Інші архіви не запускаються лише тому, що вони присутні.')
    print(f'Перевірка SHA256 прийнятого джерела: {accepted["sha256"]}')
    print('\nЗамовлення всередині прийнятого пакета:')
    for job in jobs:
        profile = job['profile']
        support = 'Illustrator: ПІДТРИМУЄТЬСЯ' if job['illustrator_supported'] else 'Illustrator: НЕ ПІДТРИМУЄТЬСЯ'
        print(f"  • {job['id']}: обкладинка={profile['front']}, зображення={profile['image']}, підпис={profile['signature']} [{support}]")
    return zips, jobs, archive, accepted


def route_choice():
    print('\n=== 3. СПОСІБ ВИКОНАННЯ ===')
    print('  1. Adobe Illustrator / PREPRESS — створює редагований AI, PDF і 4 PNG для перегляду.')
    print('  2. Сервер / локально — зарезервовано; рендерер ще не підтверджено, запуск ЗАБЛОКОВАНИЙ.')
    return choose(['illustrator', 'server-local'], 'Оберіть спосіб:',
                  show=lambda name: 'Adobe Illustrator — основний робочий шлях' if name == 'illustrator' else 'Сервер — поки недоступний')


def launch(ai, client, ws):
    print('\n=== 2. НОВИЙ ПРОГІН ЛИСТІВКИ (REVIEW ONLY) ===')
    _, jobs, archive, accepted = show_source(ai, client, ws)
    if not jobs:
        print('У прийнятому пакеті немає замовлень для вибору.')
        return 0
    print('\nТепер обираємо ЗАМОВЛЕННЯ (не ZIP). Одне замовлення — одна конкретна листівка.')
    selected = choose(jobs, 'Оберіть замовлення:',
                      show=lambda j: j['id'] + (' — Illustrator доступний' if j['illustrator_supported'] else ' — Illustrator не підтримує цей профіль'))
    if selected is None:
        return 0
    route = route_choice()
    if route is None:
        return 0
    if route == 'server-local':
        print('\nСерверний маршрут ще не має доведеного рендерера. Спробу не створено; жодних PDF/PNG не підмінено.')
        print('GC47AJ_SERVER_LOCAL=BLOCKED_RENDERER_CAPABILITY_NOT_PROVEN')
        return 0
    if not selected['illustrator_supported']:
        print('Ця конфігурація не підтримується наявним Illustrator-конструктором. Без запуску.')
        return 0
    # Do not change an accepted source after showing the operator which source is authorized.
    _, jobs_again, archive_again, accepted_again = source_summary(ai, client, ws)
    need(archive_again == archive and accepted_again['sha256'] == accepted['sha256'], 'SOURCE_CHANGED_BEFORE_CONFIRMATION')
    need(any(j == selected for j in jobs_again), 'JOB_CHANGED_BEFORE_CONFIRMATION')
    print('\n=== 4. ПЕРЕВІРКА ПЕРЕД ЗАПУСКОМ ===')
    print(f'Клієнт: {client}')
    print(f'Прийнятий ZIP: {archive.name}')
    print(f'Замовлення: {selected["id"]}')
    print('Маршрут: Windows PREPRESS → Adobe Illustrator')
    print('Вихід: нова ізольована спроба; AI, PDF, 4 PNG та дані перевірки у клієнтському output/.')
    print('Це НЕ погодження дизайну та НЕ дозвіл у виробництво.')
    print('Зверни увагу: запуск створює ОДНУ нову спробу. Автоматичного повторення після помилки немає.')
    text = 'LAUNCH ' + selected['id']
    if input(f'Для запуску введи точно «{text}» (або Enter для скасування): ').strip() != text:
        print('Запуск скасовано; нову спробу не створено.')
        return 0
    print('\nПеревіряю маршрут і виконую наявний GC47T. Вивід залишаю видимим для діагностики…', flush=True)
    rc = ai.pilot(client, selected['id'], 'illustrator', confirm=True)
    print('\nGC47AJ=ILLUSTRATOR_REVIEW_REQUEST_COMPLETED')
    print('Перевір клієнтський output/greeting_card_pilots/<job>/<attempt> та проведи візуальне погодження.')
    print('GC47AJ_PRODUCTION_READY=FALSE VISUAL_APPROVED=FALSE')
    return rc


def list_attempts(ai, ws):
    attempts = {}
    for kind, base in (('підготовка', ws / 'template_studio/greeting_card_pilots'),
                       ('результат', ws / 'output/greeting_card_pilots')):
        if not base.exists():
            continue
        need(folder_regular(base), 'UNSAFE_ATTEMPT_BASE')
        for job in base.iterdir():
            if not folder_regular(job) or not ai.JOB_RE.fullmatch(job.name):
                continue
            for attempt in job.iterdir():
                if not folder_regular(attempt) or not ai.ATTEMPT_RE.fullmatch(attempt.name):
                    continue
                key = (job.name, attempt.name)
                attempts.setdefault(key, set()).add(kind)
                need(len(attempts) <= MAX_ATTEMPTS, 'TOO_MANY_ATTEMPTS_FOR_MENU')
    return [(job, attempt, ('результат є' if 'результат' in kinds else 'ще без опублікованого результату'))
            for (job, attempt), kinds in sorted(attempts.items(), key=lambda kv: kv[0][1], reverse=True)]


def review(ai, client, ws):
    print('\n=== 5. ПОПЕРЕДНІ СПРОБИ І РЕЗУЛЬТАТИ ===')
    selected = choose(list_attempts(ai, ws), 'Оберіть спробу:',
                      show=lambda row: f'{row[1]} | {row[0]} | {row[2]}')
    if selected is None:
        return 0
    job, attempt, state = selected
    print(f'Замовлення: {job}, спроба: {attempt}, локальний стан: {state}')
    if state == 'результат є':
        print('Готовий результат уже опубліковано. Повторне отримання не пропоную.')
        print(f'Знайдеш його в output/greeting_card_pilots/{job}/{attempt}')
        actions = ['status']
    else:
        actions = ['status', 'collect']
    action = choose(actions, 'Що зробити?',
                    show=lambda x: 'Перевірити статус — без змін' if x == 'status' else 'Отримати/повернути результат, якщо готовий — потрібне підтвердження')
    if action is None:
        return 0
    if action == 'collect':
        phrase = f'COLLECT {attempt}'
        print('Це НЕ запуск нового рендерингу, але виконує контрольоване отримання результату.')
        if input(f'Введи точно «{phrase}» (або Enter для скасування): ').strip() != phrase:
            print('Отримання скасовано.')
            return 0
    return ai.status_or_collect(action, client, job, attempt, confirm=(action == 'collect'))


def help_screen():
    print('''
=== ЯК ПРАЦЮЄ FORPRINT LAUNCHER ===
1. input/ містить вхідні ZIP. Перевірка CRC не робить ZIP автоматично прийнятим.
2. GC25/GC29 визначає один ПРИЙНЯТИЙ пакет — тільки він може бути джерелом роботи.
   Якщо потрібно запустити інший ZIP, спочатку потрібно провести його через штатний intake.
3. Усередині пакета може бути кілька ЗАМОВЛЕНЬ — обираєш одну конкретну листівку.
4. Маршрут — це СПОСІБ ВИГОТОВЛЕННЯ, а не інше замовлення:
   Illustrator — підтримується; Server/Local — наразі заблокований.
5. Після перевірки показуємо підсумок; тільки буквальне LAUNCH дозволяє одну спробу.
6. Результат потрапляє в output/greeting_card_pilots/<job>/<attempt>.
7. Перегляд AI/PDF/PNG та виробниче погодження — окремі дії.
8. Помилка або timeout НЕ означають, що Illustrator не виконав роботу: спочатку статус,
   потім можливе отримання результату. Ніколи не повторюй LAUNCH автоматично.

Статус: лабораторний маршрут, PRODUCTION_READY=false. Prepress Hub не задіюється.
''')


def interactive(ai, client, ws):
    print('\n' + '='*64)
    print(' FORPRINT — КЛІЄНТСЬКИЙ ЗАПУСКАЧ ЛИСТІВОК  |  GC47AJ')
    print('='*64)
    print(f'Клієнт: {client}')
    print(f'Робоча папка: {ws}')
    print('Режим: лабораторний перегляд. Жодне замовлення не запускається автоматично.')
    while True:
        menu = ['Переглянути вхідні ZIP і доступні замовлення',
                'Створити нову листівку через Illustrator',
                'Перевірити готовність маршрутів (read-only)',
                'Попередні спроби / статус / отримати результат',
                'Довідка: що і коли обирати']
        choice = choose(menu, '=== ГОЛОВНЕ МЕНЮ ===')
        if choice is None:
            print('Завершено без додаткових дій.')
            return 0
        index = menu.index(choice)
        if index == 0:
            show_source(ai, client, ws)
        elif index == 1:
            result = launch(ai, client, ws)
            if result:
                return result
        elif index == 2:
            print('\nЧитаю готовність вузлів. Це не запускає Illustrator.')
            ai.call_existing(ai.GC47U, ['--mode', 'routes'])
        elif index == 3:
            result = review(ai, client, ws)
            if result:
                return result
        else:
            help_screen()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, help='Absolute existing _forprint_automation/input')
    parser.add_argument('--mode', choices=('interactive','check','sources','attempts'), default='interactive')
    args = parser.parse_args(argv)
    try:
        ai = ai_load()
        client, ws = resolve_context(ai, args.input_dir)
        ai.source_guard()
        if args.mode == 'check':
            print('GC47AJ_CLIENT_ENTRY=PASS_BOUND_TO_EXISTING_SMB_WORKSPACE')
            print(f'GC47AJ_CLIENT={client}')
            print('GC47AJ_NATIVE_DISPATCH=NOT_PERFORMED')
            return 0
        if args.mode == 'sources':
            show_source(ai, client, ws)
            return 0
        if args.mode == 'attempts':
            for job, attempt, state in list_attempts(ai, ws):
                print(f'GC47AJ_ATTEMPT={attempt} JOB={job} STATE={state}')
            return 0
        return interactive(ai, client, ws)
    except Exception as error:
        # Also handles the pinned GC47AI.Blocked, without hiding a failed dispatch.
        detail = str(error) if isinstance(error, (Blocked, OSError, ValueError, KeyError, EOFError, UnicodeError, zipfile.BadZipFile)) else type(error).__name__
        print('GC47AJ=BLOCKED_' + re.sub(r'[^A-Z0-9_]', '_', detail.upper())[:140], file=sys.stderr)
        print('GC47AJ_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE', file=sys.stderr)
        return 2



if __name__ == '__main__':
    raise SystemExit(main())
