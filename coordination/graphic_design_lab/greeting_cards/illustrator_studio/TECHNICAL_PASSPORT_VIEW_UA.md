# ForPrint Illustrator Studio — технічний паспорт (генерується з JSON)

**Єдине джерело:** `technical_passport_v1.json`. Не редагувати це представлення.

**Статус:** CANONICAL_STUDIO_V1_NATIVE_VERIFIED_LAB_VISUAL_ISSUES_OPEN

## Контрольні native-прогони (історичні)

- `gdl_gc_zap_20261011` — p20261102115307-e7858645; PASS_PRIOR_ROUTE; REVIEW_REQUIRED
- `gdl_gc_apa_20261011` — p20261103125458-20d9b170; PASS_GC47BU; ACCEPTED_WITH_P03_NOTE
- `gdl_gc_deg_20261011` — p20261103162336-41622db1; PASS_GC47BX; SENDER_SIGNATURE_COLLISION
- `gdl_gc_bas_20261011` — p20261103163623-f32468c5; PASS_GC47BX; SENDER_SIGNATURE_COLLISION
- `gdl_gc_bas_20261011` — p20261103171848-dde45f16; PASS_ILLUSTRATOR_STUDIO_V1_CANONICAL; REVIEW_REQUIRED

## Проблеми й рішення

### GDL-OPS-001 — SSH PowerShell: довгі або неправильно передані команди

- Статус: `RESOLVED_VERIFIED`
- Причина: Для GC32 зафіксовано обмеження способу передавання і необхідність коротких SHA-прив’язаних команд; первинні конкретні exception-тексти для всіх випадків не збережені.
- Рішення: Використовувати зафіксований SSH-ключ та known_hosts, PowerShell UTF-16LE EncodedCommand і короткий перевірений сканер; не подавати великі сценарії через stdin.
- Перевірка: GC32 SSH scanner / inventory та пізніші GC47T запуски мали успішні транспортні checkpoint; для нових версій обов’язково повторити source pin і read-only probe.

### GDL-OPS-002 — Windows SSH-сесія не має доступу до клієнтського SMB

- Статус: `RESOLVED_VERIFIED`
- Причина: Контекст автентифікації PREPRESS\Work через SSH відрізняється від серверного контексту доступу до SMB.
- Рішення: s01 читає прийнятий ZIP у SMB, формує SHA-pinned payload і доставляє його через SFTP/SCP на PREPRESS; зворотне передавання проходить серверну SHA256-перевірку.
- Перевірка: GC30 r002C: 16 файлів/12 активів stage PASS. GC47AC та GC47S: перевірене повернення ZAP AI/PDF/PNG. Не узагальнювати на всі Windows ACL.

### GDL-OPS-003 — PREPRESS увімкнений, але відсутня сесія Work

- Статус: `RESOLVED_VERIFIED`
- Причина: Windows стартував без інтерактивного входу Work. SSH-сеанс не еквівалентний GUI-сеансу.
- Рішення: Для окремого обмеженого облікового запису Work налаштовано Windows Autologon поза Git/SMB; після цього діагностика повернула WORK_SESSION=ACTIVE, EXPLORER=YES, AUTOLOGON=ENABLED.
- Перевірка: GC47AV: PASS_WORK_SESSION_PRESENT; GC47AU після цього виконав ZAP і штатно закрив Illustrator. Перевірка після кожного нового boot лишається необхідною.

### GDL-OPS-004 — Відкритий Illustrator блокував наступну native-спробу

- Статус: `RESOLVED_VERIFIED`
- Причина: Режим single-use потребує чистого старту; GC47T навмисно не запускає другу копію Illustrator.
- Рішення: GC47AS перевіряє COM і Saved для кожного документа, викликає штатний Quit без taskkill; GC47AU/GC47AX закриває Illustrator після перевіреної публікації.
- Перевірка: GC47AU ZAP p20261102115307-e7858645: AI/PDF/PNG опубліковано, POSTFLIGHT=PASS_ILLUSTRATOR_CLOSED, FORCE_KILL=FALSE.

### GDL-OPS-005 — APA: два падіння Illustrator після запуску native Worker

- Статус: `MITIGATED_NATIVE_VERIFIED_UNDER_REVIEW`
- Причина: GC47BT pinpointed dynamic font metrics. Adobe crash SIGABRT/purecall; internal Adobe root cause not proven.
- Рішення: GC47BU APA 18.5pt one-time font; GC47BX fresh frame per candidate DEG and BAS. Native output successful; no post-content tier mutation.
- Перевірка: APA p20261103125458-20d9b170; DEG p20261103162336-41622db1; BAS p20261103163623-f32468c5.

### GDL-OPS-006 — BLOCKED_BLOCKED та прихована помилка DoJavaScript

- Статус: `OPEN_FIX_REQUIRED`
- Причина: GC47BC у верхньому catch використовує тип чужого Blocked, а Windows Worker маскує неочікувані COM/JSX винятки загальним кодом.
- Рішення: Виправлення ще не встановлено. Рекомендовано нормалізований код + фаза + редагований короткий stack/category + GC47V checkpoint_trace без тексту клієнта.
- Перевірка: Вимагати тести на приховані error codes, відсутність приватних даних і одиничність запуску; live-паритет окремо.

### GDL-OPS-007 — P03 clipping: unmasked overscan та непідтверджений внутрішній контур

- Статус: `HISTORICAL_REVIEW`
- Причина: Відсутній перевірений внутрішній vector clipping contour; фото не можна підганяти довільним зміщенням.
- Рішення: Технічний обхід r006 існує, але дизайн не погоджено. Перед змінами відновити точні source path / clipping semantics і провести native visual review.
- Перевірка: Див. TS_FULL architecture recovery P03 і джерела GC47AQ/GC47Y; результат генератора сам по собі не є approval.

### GDL-OPS-008 — P04: довгий текст не вміщується у native area text

- Статус: `HISTORICAL_REVIEW`
- Причина: Різниця між історичною native line-fit логікою і source-derived параметрами тексту; повне native acceptance для всіх підписів не доведено.
- Рішення: Є історичні адаптивні GC29/GC47W механізми; застосовувати лише за конкретним SHA й після порівняння текстових символів, bounds та AI/PDF/PNG.
- Перевірка: DEG історично blocked; ZAP окремо виконувався успішно. Для нового DEG потрібне власне native acceptance.

### GDL-OPS-009 — Канонічні залежності та lock у tmp/

- Статус: `RESOLVED_VERIFIED`
- Причина: Проміжна реалізація прив’язала потрібні файли production-маршруту до disposable staging.
- Рішення: GC47AX переніс source baseline до coordination і lifecycle lock до стабільного .state за межами tmp; GC47AY обмеженим commit/push зафіксував потрібні джерела.
- Перевірка: GC47AX_VERIFY=PASS_CANONICAL_BASELINE_STATE_ONE_LAUNCHER; Git main 83cefbef5d85ee2dfd28ced33e2a237ee78b67cb.

### GDL-OPS-010 — GRIGO SVG через native PlacedItem — історичний blocker

- Статус: `HISTORICAL_REVIEW`
- Причина: У GC30 контрактному списку блокерів описано відмову PlacedItem від SVG; стан для пізніших GC47X потребує повторного підтвердження.
- Рішення: Пізніші GC29 маршрути використовують перетворення SVG → PNG із перевіреною SHA-прив’язкою. Не переносити це автоматично на інші SVG без доказів.
- Перевірка: Перевірити GC47BF/GC47BG binding та поточний native proof; historical note не означає активний blocker для ZAP.

### STUDIO-P03-001 — P03: legacy frame on floral photo page

- Статус: `OPEN_VISUAL`
- Причина: Current GC47BE P03.FRAME role resolves historical frame. New approved frame variant not pinned.
- Рішення: Create versioned GC47BE release with new frame; edit one shared role, do not patch per job.
- Перевірка: APA P03 preview from 2026-11-03 shows old frame; other pages use current frame.

### STUDIO-P04-002 — DEG/BAS: sender text formatting and signature collision

- Статус: `OPEN_VISUAL`
- Причина: Generic renderer sender baselines and source signature image bbox overlap; correct sender style/placement not yet captured as canonical specifications.
- Рішення: Edit canonical design_config_v1.json (sender), add signature zone guard and update shared asset metadata; apply same to all profiles.
- Перевірка: Screenshots DEG/BAS P04 from 2026-11-03: sender lines clash with blue handwritten signature.

### STUDIO-REN-003 — Canonical Illustrator Studio v1 not yet native validated

- Статус: `RESOLVED_NATIVE_VERIFIED_LAB`
- Причина: Canonical renderer previously required independent native validation; historic pilot evidence was insufficient.
- Рішення: One authorized BAS pilot through illustrator_studio_cli_v1.py, same canonical renderer/config for all four profiles; retain nonrelease authority.
- Перевірка: BAS attempt p20261103171848-dde45f16; verified Studio local receipt and client review verify.json; AI/PDF/PNG published; visual approval remains pending.

### STUDIO-INTAKE-004 — Four accepted profiles pinned in historical source adapter

- Статус: `OPEN_GENERALIZATION`
- Причина: GC47BM/GC47BC accept current four jobs with frozen source hashes; new orders require a separate intake contract.
- Рішення: Extend intake adapter to accept new job IDs with validated archive, without modifying renderer or design config.
- Перевірка: No arbitrary future job source support claimed for v1.

### STUDIO-RESTORE-005 — Clean restore / independent deployment not verified

- Статус: `OPEN_RESTORE`
- Причина: PREPRESS interactive Work, SSH known_hosts, durable GC47BE asset store and accepted client inputs are external to Git.
- Рішення: Restore exercise with verified credentials/storage; never copy secrets into Git or ZIP.
- Перевірка: Native attempts successful only on current installed infrastructure.

## Правило змін

All shared design changes: edit design_config_v1.json and/or illustrator_studio_renderer_v1.jsx; all asset changes: new GC47BE immutable shared release and one role mapping; all defects: update ONLY technical_passport_v1.json. Do not patch historical GC47BZ experiments.

Production-ready=false, visual-approved=false, queue=false.
