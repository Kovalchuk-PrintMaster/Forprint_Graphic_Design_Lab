# ForPrint Studio Intake Interface v1 — архітектура й поетапне впровадження

## Одне джерело правди

Канонічні: `illustrator_studio_renderer_v1.jsx`, `design_config_v1.json`, `technical_passport_v1.json`. Зовнішня підготовка замовлень — `intake/INTAKE_OPERATOR_PROMPT_UA_v1.md` та `intake/intake_interface_contract_v1.json`. Ці файли належать до Studio, не створюють другого генератора. Всі майбутні Intake-рішення, інтерфейси і зміни — тут; історичні GC10–GC47 лишаються як адаптери/докази до окремої міграції, не друге джерело дизайну.

## Фаза 1 (цей пакет)

- Єдиний постійний Intake prompt: користувач надсилає сирі матеріали одним/двома архівами або набором файлів, без пояснень.
- Один machine-readable контракт для `PORTRAIT`/`DEFAULT_ASSET`, Creator task/correction/review, provenance, review і `gdl_intake_handoff.zip`.
- Read-only валідатор ZIP та scanner `CLIENT_NAME → /srv/smb/In_Progress/data/<client>/_forprint_automation/input`, який розрізняє final handoff/staging/Creator/raw, перевіряє CRC, path safety, файл-маніфести, sha256, canonical bundle hash, артефакти, job bindings, режим фото. НЕ є authority для виконання Illustrator і НЕ засвідчує незалежно операторські підписи.
- Розширення одного паспорта `technical_passport_v1.json` та представлення, що генерується з цього JSON. У статусі інциденту `STUDIO-INTAKE-004` залишаємо OPEN_GENERALIZATION, доки Studio не навчиться приймати нові job IDs.
- Add-only source: жодних змін рендерера, Windows Worker, Launcher або існуючих клієнтських ZIP. Make-маршрут тільки для read-only check/scan.

## Фаза 2 (НЕ входить до пакета; обов'язковий окремий етап)

- Замінити `JOBS`, `BM_SHA`, `BC_SHA`, `ACCEPTED_SHA` й жорстко прикріплену четвірку робіт у Studio на bounded узагальнений intake-loader: конкретний ZIP → bytes SHA → archive contract → semantic review evidence → resource registry → 1..N jobs → native attempts.
- Не обходити перевірені події, стани та замки GC47T. Новий Handoff не може породити native-run до проходження незалежного read-only preflight.
- Підтримувати нову схему не шляхом `DEFAULT_ASSET`→`PORTRAIT`, а окремою прив'язкою `flowers.default.v1` до приватного верифікованого ресурсу Studio з SHA `d9113f8d...`.
- Валідація нових фото: реальна alpha маска, людина не переплутана, перевірена якість, source/result/creator-review evidence. Однакові правила для 1..N jobs. Два ZIP у input не означають одну фінальну партію без формального batch binding.
- Вбудувати scan/inspect перед launch у клієнтський Launcher. Початковий автоматичний scan НЕ створює native attempts, НЕ пише в input, НЕ виробляє фальшиві PASS. Кожен запуск — окремий bounded confirmed native decision.
- Додати тести порушених SHA, ZIP-bomb, traversal, namespace, ambiguous identity, missing alpha, брендингу, підписів, multi-job, idempotent intake, нових job IDs, recovery, чистого клону Git та runtime state без `tmp/`.
- Тільки потім запустити один спеціально затверджений новий клієнтський ZIP у Illustrator, прийняти візуально, зафіксувати commit/push та оновити passport evidence. Не включати production/queue автоматично.

## Історичні три пакети (перевірено байти)

1. `gdl_flowers_reviewed_08a42021b6a897e3.zip` — 4 jobs, accepted Handoff; SHA `90efe86afb294ddf130bc9a09affe0f99780ab5abeb0f15be316b005f4c60064` збігається із прив'язкою існуючого GC47BC. Присутній операторський `PASS` у пакеті; сам zip не є незалежним доказом підпису.
2. `gdl_intake_handoff.zip` — 2 jobs, accepted Handoff за форматом; SHA `6c26a8a8138cb406b09e87fced86d59ec774619ac672c2d6609fb77c14c8d3c0`. Фото JPG, відповідно до нового правила прозорості — `LEGACY_PORTRAIT_REVIEW_REQUIRED`. Не поточний SHA-pinned Handoff Studio.
3. `gdl_intake_blocked_packet_flowers_20261014.zip` — staging/blocked, **не** готовий handoff. SHA `08a42021b6a897e388310e3066cba190300c766019656f423a76d650a9abcacd`. Історичні блокери описані всередині; деякі з них пізніше частково закриті наступними роботами. Цей конкретний ZIP від того не стає accepted.

## Важливі межі

- `CONFIRMED` із назви/частини прізвища без доказу заборонено. Intake повертає bounded питання тільки коли потрібно.
- `FINAL_HANDOFF_READY` не дає `STUDIO_NATIVE_PASS`; Studio робить власний захищений вхідний контроль.
- Уникати змішування старого JPEG reviewed/без альфи та нового вимогливого стандарту з прозорістю. Старі архіви можна переглядати, але не мовчки приймати як новий якісний портрет.
- `tmp/` — тільки доставлення ZIP і staging; стабільний код/контракти зберігаються у репозиторії; приватні ресурси й об'єкти клієнта — у підтверджених приватних сховищах.
