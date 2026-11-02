#!/usr/bin/env python3
"""GC47AX: guarded client-folder pilot UI -> GC47AS -> GC47AR -> GC47AS close.

An additive testing entry. It never changes the installed GC47AJ/GC47AK UI,
GC47T, GC47K or PREPRESS code. Only ZAP is currently eligible for this
versioned runtime. No server renderer; no automatic attempts or retries.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
CAN = ROOT / 'scripts/graphic_design_lab/greeting_cards'
BRIDGE = CAN / 'gc47ak_windows_bridge_r001.py'
BRIDGE_SHA = 'cd95b413c6543e0896f2cf2b89ec1e73d2397fe669b45fe5ad6a6d621f45c824'
LIFECYCLE = CAN / 'gc47ax_illustrator_lifecycle_r001.py'
LIFECYCLE_SHA = '7da40974a4d2dcc26d3f11447fd1d40ee6300fd3104480d487fe4f34fccfd2d9'
VERSIONED_JOB = 'gdl_gc_zap_20261011'
POSTFLIGHT = CAN / 'gc47ax_postflight_r001.py'
POSTFLIGHT_SHA = 'f2e5e2636fc88622f861998d426b919e12678728514adac0992b5803fe3cd5c3'

class Blocked(RuntimeError):
    pass

def require(condition, reason):
    if not condition:
        raise Blocked(reason)

def load_pinned(path, expected, name):
    try:
        is_regular = stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        is_regular = False
    require(is_regular, 'PINNED_SOURCE_NOT_REGULAR_' + name)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'PINNED_SOURCE_CHANGED_' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, 'PINNED_SOURCE_IMPORT_' + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def get_runtime():
    require(ROOT.name == 'forprint_graphic_design_lab' and (ROOT / '.git').is_dir(), 'NOT_GDL_REPOSITORY')
    bridge = load_pinned(BRIDGE, BRIDGE_SHA, 'gc47ax_pinned_ak')
    lifecycle = load_pinned(LIFECYCLE, LIFECYCLE_SHA, 'gc47ax_pinned_as')
    require(hasattr(bridge, 'decode_client') and hasattr(bridge, 'bound_context'), 'GC47AK_API_CHANGED')
    require(hasattr(lifecycle, 'main') and hasattr(lifecycle, 'verify_local'), 'GC47AS_API_CHANGED')
    postflight = load_pinned(POSTFLIGHT,POSTFLIGHT_SHA,'gc47ax_pinned_postflight')
    require(hasattr(postflight,'main'), 'GC47AX_POSTFLIGHT_API_CHANGED')
    return bridge, lifecycle, postflight

def preflight(bridge, lifecycle, token):
    client = bridge.decode_client(token)
    ui = bridge.load_ui()
    ai, ws = bridge.bound_context(ui, client)
    # This only verifies pinned Python/PS1 and shadow sources; it does not
    # contact PREPRESS or allocate a task/attempt.
    lifecycle.verify_local()
    return client, ui, ai, ws

def show_pilot_info(job):
    print('\n=== ПЕРЕД ЗАПУСКОМ ===')
    print('Замовлення:', job)
    print('Варіант: GC47K / параметричний Illustrator (GC47AR).')
    print('Система сама перевірить Illustrator на PREPRESS.')
    print('Якщо Illustrator відкритий і ВСІ документи збережені — штатно закриє його.')
    print('Якщо є незбережені зміни, інша сесія чи невизначений стан — запуск блокується.')
    print('Після цього GC47AR створить РІВНО ОДНУ native-спробу без автоповтору.')
    print('ПІСЛЯ ПЕРЕВІРЕНОЇ ПУБЛІКАЦІЇ AI/PDF/PNG Illustrator буде штатно закритий, якщо документи збережені.')
    print('Якщо закриття заблоковано, результат зберігається, але наступне замовлення не запускається.')
    print('Результат: AI, PDF та 4 PNG для перегляду, без виробничого погодження.')
    print('Серверний рендерер не використовується. Після timeout спершу перевірити статус.')

def launch_versioned(ui, ai, ws, client, postflight):
    print('\n=== СТВОРИТИ ЛИСТІВКУ / КЕРОВАНИЙ ILLUSTRATOR ===')
    _, jobs, archive, accepted = ui.show_source(ai, client, ws)
    if not jobs:
        print('Немає прийнятих замовлень.')
        return 0
    print('\nЗАМОВЛЕННЯ — конкретна листівка, а не ZIP. Для цієї версії GC47AX')
    print('автоматичний параметричний цикл перевірений тільки для ZAP.')
    selected = ui.choose(jobs, 'Оберіть замовлення:',
        show=lambda j: j['id'] + (' — ПІДТВЕРДЖЕНИЙ GC47AR' if j['id'] == VERSIONED_JOB else ' — ЩЕ НЕ ІНТЕГРОВАНО В GC47AR'))
    if selected is None:
        return 0
    if selected['id'] != VERSIONED_JOB:
        print('GC47AX=BLOCKED_VERSIONED_PROFILE_NOT_YET_SUPPORTED_NO_DISPATCH')
        print('Інші замовлення не підміняємо перевіреним маршрутом ZAP.')
        return 0
    if not selected.get('illustrator_supported'):
        print('GC47AX=BLOCKED_ILLUSTRATOR_VARIANT_NOT_SUPPORTED')
        return 0
    print('\nСПОСІБ ВИКОНАННЯ:')
    route = ui.choose(['illustrator', 'server-local'], 'Оберіть маршрут:',
        show=lambda r: 'Illustrator / PREPRESS — автоматична підготовка і один прогін' if r == 'illustrator'
           else 'Server / Local — НЕ ДОСТУПНИЙ')
    if route is None:
        return 0
    if route != 'illustrator':
        print('GC47AX_SERVER_LOCAL=BLOCKED_RENDERER_CAPABILITY_NOT_PROVEN')
        return 0
    _, jobs_again, archive_again, accepted_again = ui.source_summary(ai, client, ws)
    require(archive_again == archive and accepted_again['sha256'] == accepted['sha256'], 'ACCEPTED_ZIP_CHANGED')
    require(any(j == selected for j in jobs_again), 'JOB_CHANGED')
    show_pilot_info(selected['id'])
    phrase = 'LAUNCH_VERSIONED ' + VERSIONED_JOB
    answer = input('Щоб дозволити одну native-спробу (і безпечне закриття Illustrator), введи точно «' + phrase + '»: ').strip()
    if answer != phrase:
        print('Скасовано. Нічого не запущено.')
        return 0
    # Single synchronous delegate. GC47AS performs all independent checks,
    # graceful lifecycle and ONE GC47AR native attempt. No retry here.
    # One operator authorization covers preparation, one render and safe post-publish close.
    return postflight.main(['--mode', 'pilot', '--client-name', client,
         '--confirm-once-and-post-close', '--confirmation', postflight.CONFIRM, '--timeout-minutes', '24'])

def help_screen(ui):
    ui.help_screen()
    print('GC47AX: додатковий контрольований параметричний маршрут для ZAP.')
    print('Один LAUNCH_VERSIONED дозволяє підготовку, один рендеринг і безпечне закриття після публікації.')
    print('Автоматична черга ще не активована: кожне завдання потребує окремого дозволу.')
    print('Інші замовлення поки не активовані в GC47AR. Інші замовлення потребують окремої інтеграції.')
    print('GC47AX — контрольований штатний ZAP-маршрут, лише лабораторний перегляд.')

def interactive(client, ui, ai, ws, lifecycle, postflight):
    print('\n' + '=' * 64)
    print(' FORPRINT | КЕРОВАНИЙ ILLUSTRATOR | GC47AX (КОНСОЛІДОВАНИЙ)')
    print('=' * 64)
    print('Клієнт:', client)
    print('Робоча папка:', ws)
    print('Лише лабораторний перегляд; запуск тільки після буквального підтвердження.')
    menu = [
        'Вхідні ZIP та замовлення',
        'Створити листівку: підготовка → Illustrator → результат → автоматичне закриття (ZAP)',
        'Перевірити стан Illustrator / PREPRESS (без змін)',
        'Попередні спроби, статус та результати',
        'Довідка',
    ]
    while True:
        selected = ui.choose(menu, '\n=== ГОЛОВНЕ МЕНЮ ===')
        if selected is None:
            print('GC47AX_EXIT=NO_NEW_ACTION')
            return 0
        index = menu.index(selected)
        if index == 0:
            ui.show_source(ai, client, ws)
        elif index == 1:
            result = launch_versioned(ui, ai, ws, client, postflight)
            if result:
                return result
        elif index == 2:
            print('GC47AX_INSPECT=READ_ONLY_NO_CLOSE_NO_NATIVE')
            result = lifecycle.main(['--mode','inspect','--client-name',client])
            if result:
                print('Перевірку заблоковано; native-спробу не створено.')
        elif index == 3:
            result = ui.review(ai, client, ws)
            if result:
                return result
        else:
            help_screen(ui)

def execute(mode, token):
    bridge, lifecycle, postflight = get_runtime()
    client, ui, ai, ws = preflight(bridge, lifecycle, token)
    if mode == 'check':
        print('GC47AX_SOURCE=PASS_PINNED_AJ_AK_AS')
        print('GC47AX_CLIENT_CONTEXT=PASS_BOUND_SMB')
        print('GC47AX_NATIVE_DISPATCH=NOT_PERFORMED')
        return 0
    if mode == 'sources':
        ui.show_source(ai, client, ws)
        return 0
    require(mode == 'interactive', 'MODE_INVALID')
    return interactive(client, ui, ai, ws, lifecycle, postflight)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--client-b64', required=True)
    p.add_argument('--mode', choices=('check', 'sources', 'interactive'), default='interactive')
    args = p.parse_args(argv)
    try:
        return execute(args.mode, args.client_b64)
    except (Blocked, OSError, ValueError, EOFError, ImportError, RuntimeError) as exc:
        detail = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        print('GC47AX=BLOCKED_' + re.sub('[^A-Z0-9_]', '_', detail.upper())[:120], file=sys.stderr)
        print('GC47AX_NO_AUTO_RETRY=TRUE PRODUCTION_READY=FALSE', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
