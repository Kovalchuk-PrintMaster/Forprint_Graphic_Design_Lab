# ForPrint Illustrator Studio — Phase 2C: dynamic single-use native LAB

## Межа

Це НЕ окремий конструктор: з Phase2B використовується спільна функція `assemble(..., capture_material=True)`, яка повертає byte-identical JSX, маніфест та assets. JSX — тільки `illustrator_studio_renderer_v1.jsx`, оформлення — тільки `design_config_v1.json`, паспорт — тільки `technical_passport_v1.json`.

## Схема

`input/selected.zip` -> strict audit -> one `job_id` -> Phase2B verified material -> existing GC47S attempt -> existing GC47T Windows transport -> existing GC47S collect -> client `output/greeting_card_pilots`.

Суворе обмеження першого native-пілота: `inside_image.mode=DEFAULT_ASSET`. `PORTRAIT` проходить Phase2B shadow, але native у Phase2C **BLOCKED**: чинний GC47T перевіряє `image_mode=DEFAULT_ASSET`. Ніякого прихованого заміщення портрета квітами. Графічні дефекти P03 рамки та P04 sender/signature залишаються у паспорті.

## Безпека і повноваження

- ZIP-структура, SHA, asset bytes, job data перевіряються до створення спроби. Самозаявлене `intake_review=PASS` не є незалежним операторським підтвердженням.
- `plan` не контактує з Windows. Native `pilot` вимагає справжній TTY і точне текстове підтвердження `LAB_NATIVE_ONCE <job_id> <sha_prefix>`.
- Перед створенням attempt зберігається **durable single-use claim** у клієнтській `template_studio/studio_intake_dynamic_native_claims_v1/`. Повтор того самого ZIP SHA+job блокується навіть після невизначеного збою/timeout; оператор користується `claim-status`, `status`, `collect` (тільки існуюча спроба).
- Native транспорт, lock, Windows worker, verification, postflight повторно використовуються, не дублюються.
- Production, черга, retries, автоматичне затвердження візуального результату відключені. ZIP у `tmp/` служить лише доставкою й disposable staging. Runtime не залежить від `tmp/`.
- Структурний PASS та успішний native LAB не встановлюють `visual_approved=true` і не закривають STUDIO-INTAKE-004 до повного приймання.

## Операторські Make

`make gdl-studio-intake-native-plan CLIENT_NAME='…' ZIP_NAME='…' JOB_ID='…'`

`make gdl-studio-intake-native-pilot CLIENT_NAME='…' ZIP_NAME='…' JOB_ID='…'`

`make gdl-studio-intake-native-claim-status CLIENT_NAME='…' ZIP_NAME='…' JOB_ID='…'`

`make gdl-studio-intake-native-status CLIENT_NAME='…' ZIP_NAME='…' JOB_ID='…' ATTEMPT_ID='…'`

`make gdl-studio-intake-native-collect CLIENT_NAME='…' ZIP_NAME='…' JOB_ID='…' ATTEMPT_ID='…'`

**НЕ робити повторного `pilot` після будь-якої невизначеності.** Не редагувати чи видаляти claim без окремого аудиту. Після першого native результату окремо зафіксувати scoped Git commit/push без історичних не пов'язаних файлів.
