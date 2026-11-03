# ForPrint Studio v1 — Phase 2D: Operator Progress Monitor

## Архітектура

Єдиний конструктор `illustrator_studio_renderer_v1.jsx`, дизайн-конфіг, існуючі GC47S/GC47T Windows-передавання та одноразовий Native Phase2C незмінні за алгоритмом.

Операторський прогрес — лише відображення **фактично досягнутих контрольних точок** (не відсоток часу). Для відкритого Windows-очікування кожне опитування `T1_NATIVE_STATE` друкує короткий heartbeat із минулим часом; `NOT_RECORDED` — невизначений стан, **не** доказ виконання чи зависання Illustrator.

Шкала відображення:

1. Перевірено accepted Intake ZIP і зібрано scene.
2. Перевірено активну Windows-сесію PREPRESS, Illustrator і SSH.
3. Створено одноразову спробу зі staged JSX та ресурсами.
4. Файли передано в приватну директорію PREPRESS.
5. Контролер повернув `START_REQUESTED_SINGLE_USE` (це ще **не** PASS Illustrator).
6. Windows підтвердив `AI_REOPENED_VISUAL_REVIEW_REQUIRED`.
7. Опубліковані AI/PDF/PNG **повторно перевірені** за GC47S, SHA256, `verify.json`, `state.json`, повним набором артефактів і контрольними SHA lineage — лише після цього зелений `READY_FOR_VISUAL_REVIEW`.
8. Illustrator штатно закрито (якщо закриття невдале — warning, але вже перевірені файли залишаються доступними).

Колір: зелений `[OK]` — доведено, жовтий `[!]` — review / очікування / невизначеність, червоний `[X]` — зафіксована відмова. Для не-ANSI термінала plain text. `NO_COLOR=1` вимикає кольори.

## Статус усього архіву

`batch-status` показує N jobs, відповідні immutable single-use claims/attempt receipts і лічильник **готових до візуальної перевірки**, визначений лише з перевіреного опублікованого output, а не з існування каталогу. Не запускає Illustrator та не створює claims. `NOT_STARTED`, `CLAIMED_NO_ATTEMPT`, `ATTEMPT_EXISTS_RESULT_PENDING_OR_UNKNOWN`, `REVIEW_VERIFICATION_BLOCKED`, `READY_FOR_VISUAL_REVIEW` розрізняються. Якщо файли пошкоджено або не відповідають SHA, зелений заборонено.

Для CLI/Make/Launcher діють однакові перевірки та одна семантика. Авторизована черга **ще не реалізована**. Вона згодом може використовувати ці ж статуси N/M, але ні цей монітор, ні поточний Launcher не створюють додаткових спроб автоматично.

## Безпека

- `automatic_queue=false`, `automatic_retry=false`, `production_ready=false`, `visual_approved=false`.
- Постійні single-use claim та receipt лишаються в стабільному клієнтському `template_studio`; не зберігати runtime-докази у `tmp/`.
- Додаткова команда `batch-status` лише читає поточний Handoff/receipts та згенеровані результати; ніяких Windows команд, жодних змін клієнтських файлів.
- Не виводити сирі тексти привітань та фотографії в монітор.
- Помилка після claim не є дозволом на новий native pilot — використовувати `claim-status`, `status`, `collect` для існуючої спроби.
- Технічний паспорт Studio лишається єдиним машинним джерелом версій, інцидентів і невирішених обмежень.
