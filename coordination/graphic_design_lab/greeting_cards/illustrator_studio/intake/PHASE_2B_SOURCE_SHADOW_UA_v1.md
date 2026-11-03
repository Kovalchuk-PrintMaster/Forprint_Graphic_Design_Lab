# Illustrator Studio v1 — Phase 2B: універсальний Intake Source Shadow

Версія: `1.0.0`; режим: **SOURCE_BOUND_SHADOW_NO_NATIVE**; owner: ForPrint Graphic Design Lab.

## Вхід і вихід

Оператор вибирає конкретний ZIP із `_forprint_automation/input/` за точною назвою файлу. Пакет має відповідати `gdl_greeting_card_accepted_constructor_bundle_v0_1`, `gdl_greeting_card_builder_artifact_manifest_v0_1` та `gdl_intake_builder_handoff_v0_1`. ZIP із блокерами / Creator task / сирі дані не приймаються як Handoff. Якщо в input декілька ZIP, вибір **явний**.

Phase 2B перевіряє інтегральні SHA256, канонічний bundle hash, фактичні payload-ресурси, унікальність кожного job_id у межах ZIP, семантику front / occasion / greeting / sender / signature, P03 DEFAULT_ASSET / PORTRAIT і згенеровані assets. Розширення на довільну кількість **різних** job_id у batch здійснюється без редагування конструкторських `JOBS` pin. Усі картки проходять через канонічні `illustrator_studio_renderer_v1.jsx` + `design_config_v1.json`. Динамічні вихідні файли тільки в **одноразовій** тимчасовій директорії і автоматично видаляються. До клієнтського `output/`, `template_studio/native_runs`, Windows, Illustrator, production не записується нічого.

Результат — JSON у stdout, **без текстів привітань і без приватних зображень**. Для кожного job: `SCENE_SHADOW_COMPILED_NOT_NATIVE_APPROVED` або `JOB_SHADOW_BLOCKED` із конкретною причиною; загальний статус `ALL_JOBS_SHADOW_COMPILED_NO_NATIVE` чи `SOME_JOBS_BLOCKED_NO_NATIVE`.

## Обов'язкові обмеження

1. Історичний запускач з чотирма прийнятими профілями та його verified native route не змінюється.
2. Handoff review ID в самому ZIP **не є незалежним доказом** операторського приймання. Phase 2B не створює approval, не приховує REVIEW_REQUIRED, не вмикає `production_ready`.
3. Портрет тільки PNG RGBA із реальною прозорістю й SHA. Перевірка PNG/alpha не доводить фотокорекцію та збереження особи; візуальна ідентичність і bbox залишаються REVIEW_REQUIRED. Legacy JPG не підвищується до PASS.
4. Для портрета GC29 викликається тільки для одноразового **розрахунку спільної геометрії**. Фінальна кандидатна сцена має `image_mode=PORTRAIT`, роль `P03.PORTRAIT`, підв'язаний accepted PNG. Ніякого підставляння квітів у фінальну сцену.
5. Стандартні квіти беруться тільки із локального, SHA-перевіреного vault. ZIP не має приносити альтернативні квіти. Підписи тільки `GRIGO` або `HERASYMENKO`, інші — BLOCKED.
6. Інструкція Intake, дизайн та основний паспорт — єдині канонічні джерела правди. `tmp/` — тільки disposable work і ZIP delivery, не робочий runtime.
7. Shadow PASS **не означає native PASS**. Окремо потрібні незалежне джерело operator-review authority, native adapter до existing worker, bounded attempt/receipt/status/collect, візуальний acceptance і перевірка на PREPRESS.

## Оператор

Запуск з Make:

`make gdl-studio-intake-shadow-check CLIENT_NAME='назва клієнта' ZIP_NAME='gdl_intake_handoff.zip'`

Або в єдиному `ForPrint_Launcher.cmd` — меню Studio, пункт **6**, точна назва ZIP із `input/`. Пункт 6 ніколи не запускає Illustrator.

## Поточна аудиторська база 2026-11-03

- `gdl_flowers_reviewed_08a42021b6a897e3.zip` — 4 jobs, envelope/hash PASS, незалежна operator-review attestation не верифікована; може проходити shadow-компіляцію.
- `gdl_intake_blocked_packet_flowers_20261014.zip` — STAGING_BLOCKED, не підлягає shadow-компіляції.
- Натепер Stage 2B — bounded integration dry-run, а не активація native нових jobs. Інцидент `STUDIO-INTAKE-004` лишається OPEN_GENERALIZATION.
