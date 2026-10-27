# ForPrint Graphic Design Lab — Template Studio FULL

**Машинозрозуміла архітектура та handoff для наступної GPT-помічниці**  
**Версія:** `ts_full_architecture_and_recovery_model_v0_1` · **дата:** 2026-10-26  
**Проєкт-власник:** `Forprint_Graphic_Design_Lab` · **контур:** `Template Studio / Greeting Cards`  
**Статус рішення:** APPROVED DIRECTION; implementation v0.1 is REFERENCE/OPERATOR UI; **NOT accepted Illustrator master; NOT print ready.**

Цей документ зберігає рішення, програмні контракти, джерела, обмеження, правила складання та наступні інженерні кроки. Його можна використати, навіть якщо попередній чат недоступний. Машинний реєстр: `coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json`. Інтерфейс/публікація — у репозиторії GDL; **джерелом операційних замовлень залишається існуючий Intake/Prepress-маршрут, а не браузер**.

## 0. Головна мета і межі

Побудувати для ForPrint **зрозумілий операторський графічний конструктор листівок**: всі 4 фізичні сторінки, кожна з еталонним переглядом, нумерацією елементів, правильними шарами, параметрами, умовами показу та контрольованим порядком виконання. Користувач відкриває одну локальну мережеву сторінку в браузері, перемикає сторінки та варіанти й може висловити правку за стабільним ID. З часом ця модель стане джерелом автоматичного створення багатошарових AI/PDF/PNG з доказовою відповідністю затвердженому PDF Builder.

**Поточна v0.1:** функціональний статичний браузерний *паспорт/панель контролю*, **не онлайн-редактор Illustrator**. Варіанти переключають параметри, елементи, координатні контури, статуси. Фактичний preview з зафіксованого PDF (той самий для variant без окремого паритетного рендеру). Немає удаваного «другого варіанта» з вигаданою графікою. Пробна зміна bbox генерує пропозицію JSON, а не змінює файлове джерело.

### Інваріанти

- Операційні клієнтські `input/`, `output/`, оригінальні ZIP і PDF Builder **не чіпати**.
- Всі версійні алгоритми/реєстри/тести/Make-команди — **в незалежній GDL**, не в Prepress Hub.
- Prepress Hub тільки **read-only source pin** (закритий commit `b26cce19f4700cadaf34323e4c2e2909bcf5fcd8`).
- Приклади в шаблоні — не дозвіл на друк, розсилку, дизайн approval, приймання непогоджених вхідних матеріалів або активацію candidate-гілок.
- Результат браузерного редагування має `approved=false`, `production_ready=false`, `operator_review_required=true`. Єдиною владою для канонічних змін залишається review/authorization.
- Будь-які незатверджені/недоведені властивості маркуються `INVENTORY_REQUIRED`, `CANDIDATE_GATED`, `REFERENCE_ONLY`, а не заповнюються здогадками.

## 1. Поточні доведені джерела

1. **GC23**: `coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json` — pinned variant catalog, геометрія P01 і P04, фізичний формат, стан authority. Це базове джерело semantics для TS_FULL; він вимагає відсутності source drift.
2. **Приватний PDF reference:** ресурс `template.greeting_card.dolinska.v1`, SHA256 `66ed88de51ce621fcc0067263e6fc740392a1a0e9ee39e88514089451b1f2e85`, 4 сторінки, ~94 MB; шлях береться через `gdl_greeting_card_private_resources_v0_1.yaml` у Prepress Hub, не фіксується як клієнтське джерело в Git.
3. **GC22**: структурна schematic foundation; це не готові artwork-template або Illustrator master.
4. **GC25–GC26**: перевірений Windows SMB → SSH → GDL read-only маршрут, `client_workspace()`/safe client path model.
5. **GC27 r001–r005**: p03 image reference, шаруватість, прозорість і зображення; зафіксована спроба Illustrator, але **візуальний parity approval не отриманий**. Ремонт r006 щодо clipping і його uncommitted state має лишатися окремим work front, не stage разом з TS_FULL.
6. **TS01 P01 pilot:** візуальна карта з елементами і HTML; TS_FULL використовує її погоджену концепцію, не переписуючи її файл без підтвердження. TS_FULL має свої унікальні файли і окремий Make target.

### Підтверджена геометрія

- Артборд 214 × 301 мм; обрізний 210 × 297 мм; bleed 2 мм.
- Чотири фізичні сторінки: P01 FRONT, P02 BACK, P03 INSIDE IMAGE, P04 GREETING.
- P01 STANDARD sender logo bbox `[64.5,59.5,149.5,144.5]` мм.
- P01 STANDARD occasion bbox `[32,203.5,182,248]` мм.
- P01 RECIPIENT_BRANDING_OVERLAY sender logo bbox `[69,39,145,115]`, occasion bbox `[32,203.5,182,248]`, recipient branding zone `[26,134,188,191]` мм.
- P01 BILINGUAL_OCCASION sender logo `[74,112,140,178]`, occasion `[21.5,191,194.5,262.5]` мм — runtime *catalog/review-only*; реальна bilingual дизайн-авторизація не встановлена.
- P02 locked canonical composition (source verified; окремі bbox не вигадувати).
- P03 папір `[0,0,214,301]` мм; reference variable-photo bbox `[-18.8139,20.854,240.4778,280.1457]` мм (may overscan artboard); reference frame bbox `[5.5,6.9265,208.5,294.0733]` мм; **точний внутрішній векторний clipping contour не доведений**.
- P04 target greeting bbox `[32,32,182,212]` мм; решта координат залежить від канонічних блоків текстів, font metrics і обраного підпису.

## 2. Принцип взаємодії користувача

**Є лише чотири верхні вкладки** P01/P02/P03/P04. Всередині кожної кнопки-перемикачі варіантів; це **не нові вкладки і не нові окремі документи**. Внизу/поруч — елементи і виконання; натиснути ID → підсвітити bbox → побачити layer/geometry/status/source/step → пробно змінити x/y/w/h → сформувати JSON-proposal, який наступна помічниця може перенести в проєкт після review.

- **P01:** front_family: STANDARD, RECIPIENT_BRANDING_OVERLAY, BILINGUAL_OCCASION; occasion: BIRTHDAY, JUBILEE. BIRTHDAY взято як базу, JUBILEE у v0.1 — UI-концепт без approved greeting text або confirmed source binding. Комбінація не вважається дозволеною на виробництво.
- **P02:** LOCKED_REFERENCE_ONLY; без випадкових варіантів і змін.
- **P03:** image_mode: DEFAULT_ASSET (квіти), PORTRAIT (перевірене фото); обидва зареєстровані, але actual preview source може бути іншим зображенням, поки окремий parity render не додано. Неточні маски не приймаються.
- **P04:** signature: GRIGO, HERASYMENKO, DUAL_GRIGO_HERASYMENKO. DUAL — candidate-gated, перемикач **не** авторизує runtime.

Кнопки на екрані мають людські назви; model ID не змінювати після погодження. Безремонтна міграція можлива тільки через versioned alias/redirect contract.

## 3. Елементи та шари

Машинна модель містить `pages[].elements[]`; поля:

| Поле | Тип | Семантика |
|---|---|---|
| id | string `Pnn-nnn` | стабільна адреса елемента для людини і виконавця |
| name_ua | string | людиночитна назва |
| role | enum/string | що саме означає графічно |
| layer | string | майбутній шар AI; для UI показує відповідальний шар |
| step | integer | послідовність збирання від меншого до більшого |
| bbox_mm | null/4 numbers | `[x0,y0,x1,y1]`, **PDF top-left mm**; null не означає нуль |
| status | string | статус доказовості/повноти/авторизації |
| locked | bool | чи дозволені зміни у master без окремого review |
| operation | string | машинна назва графічного кроку |
| visible_if | object | обмежена умова visibility за ключами variant groups |

### P01

1. `P01-010` `P01.PAPER` — source paper background, locked. Потрібен точний file reference/збереження різних anchor.
2. `P01-015` `P01.GOLD_FRAME` — decorative frame. Вектор/растр ідентифікувати у reference PDF; **не перекомпоновувати самовільно**.
3. `P01-020` `P01.SENDER_LOGO` — sender round logo. `bbox` від GC23; variant-dependent mapping.
4. `P01-025` `P01.RECIPIENT_BRANDING` — logo recipient only under overlay, separate source acceptance and geometry.
5. `P01-030` `P01.OCCASION_TEXT` — typed occasion greeting; font, leading, text are separate stage and must match verified source.
6. `P01-900` `_FORPRINT_OPERATOR_GUIDES_NONPRINT` — non-print guides only.

### P02

1. `P02-010` `P02.CANONICAL_LOCKED_BASE` — preserved canonical artwork, locked.
2. `P02-020` `P02.WATERMARK` — pinned mark from GC19, locked until independent review.
3. `P02-900` guides.

### P03

1. `P03-010` `P03.PAPER` — pinned paper, locked.
2. `P03-020` `P03.PHOTO_CONTENT` — accepted RGB/RGBA image normalized only by verified crop/scale; editable placement, approved asset SHA.
3. `P03-030` `P03.PHOTO_CLIP_PATH` — **vector editable clipping shape** plus photo in one Illustrator clipping group; exact inner contour must be extracted/rebuilt and approved, not guessed from decorative outer ornament.
4. `P03-040` `P03.GOLD_FRAME` — decorative frame **above clip group**; prefer genuine vector from source. Outer ornamental boundary is not automatically the same as clip shape.
5. `P03-900` guides.

**Historic P03 bug:** r005 incorrectly left unmasked overscan; r006 adds rectangular clip but visual shape differs from desired potentially figure-based clipping. No more arbitrary shifting: first inventory exact paths and clip semantics.

### P04

1. `P04-010` paper, locked.
2. `P04-015` gold frame, locked until source inventory.
3. `P04-020` greeting text, bbox `[32,32,182,212]`, font/lineflow from source.
4. `P04-025` sender text/position, source canonical, not generated from untrusted Intake signatures.
5. `P04-030` source-pinned physical signature, selected by variant, DUAL candidate-gated.
6. `P04-900` non-print guides.

## 4. Machine variant selection, projection and contract

State machine input example:

```json
{
  "schema_version": "forprint_ts_full_operator_selection_v0_1",
  "active_page": "P04",
  "variants": {
    "front_family": "STANDARD",
    "occasion": "BIRTHDAY",
    "image_mode": "DEFAULT_ASSET",
    "signature": "HERASYMENKO"
  },
  "authority": "VISUAL_REFERENCE_ONLY"
}
```

Pure variant selector must never infer that any Cartesian combination is valid for actual client job. Capability/provenance and authorizations must be separately checked through GC23+accepted Job manifest and explicit allowed combinations. UI-only `JUBILEE` choice has no accepted source binding. UI-only `BILINGUAL` is source-catalog registered but not generic runtime grant. `DUAL` explicitly candidate-gated.

**Formal dependencies:** project registry -> GC23 canonical model -> canonical PDF hash and private resources -> Builder output -> Illustrator parity -> operator design approval -> production review. Backwards edges prohibited: editing HTML proposal or visually selecting variant must not change source of truth.

## 5. Browser runtime and client deployment

### Architecture

```text
GDL repository (source, tests, Make/CLI)
  ├── coordination/graphic_design_lab/template_studio/ts_full_registry_v0_1.json
  ├── scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html
  ├── scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py
  └── tests/graphic_design_lab/test_ts_full_publisher_v0_1.py
         | SHA-pinned read-only preview build
         v
GDL tmp/tsfull_<release_name>/index.html (self-contained)
         | explicit make ts-full-publish / verified one-client boundary
         v
/srv/smb/In_Progress/data/<CLIENT>/_forprint_automation/
  ├── input/ (UNCHANGED)
  ├── output/ (UNCHANGED)
  └── template_studio/
        ├── index.html                  <-- STABLE browser bookmark
        ├── publication_manifest.json  <-- manifest SHA/content
        ├── .publish.lock               <-- serialized controlled updates
        └── releases/tsfull-<SHA>.html  <-- immutable history
```

No new web daemon, no HTTP server, no unauthenticated publicly reachable port. **Browser uses an existing authenticated/private SMB share**. Preferred Windows Explorer path based on actual mapped UNC server: `\\<YOUR_SMB_HOST>\In_Progress\<EXACT_CLIENT_FOLDER>\_forprint_automation\template_studio\index.html`. In supported browsers, opening the file may show a `file://...` URL, but behavior may differ with enterprise security policies: verify locally, do not assume an HTTP URL. The stable bookmark remains the same while `index.html` is safely replaced on s01. **No automatic hot-refresh**: after operator publishes the next build, browser refresh reads it.

User's phrase "без паролів" refers to *existing access on the server/share*, not permission to expose client PII on public Internet. Do not start public nginx/HTTP or weaken ACLs without a separate security design and explicit authorization.

### Publisher interface

- `make ts-full-check TS_FULL_RESOURCE_MANIFEST=...` verifies GC23 geometry and exact reference SHA. No files written.
- `make ts-full-build TS_FULL_RESOURCE_MANIFEST=... OUTPUT_NAME=tsfull_review_r001` creates new-only self-contained HTML and manifest under GDL tmp; never modifies client files.
- `make ts-full-publish CLIENT_NAME='...' BUILD_DIR=tmp/tsfull_review_r001 CONFIRM_PUBLISH=YES` writes only portal-owned paths in that exact client's workspace, preserves `input` and `output`, ensures prior portal ownership, keeps release history.
- `make ts-full-verify CLIENT_NAME='...'` validates current published index/release/manifest SHA. No changes.
- `make ts-full-test` synthetic tests on full registry and private fake SMB directory; PyMuPDF rendering is additionally proved on server real source by `check` and `build`.

**Update cycle:** edit registry or UI -> tests -> source check -> build unique new `OUTPUT_NAME` -> explicit publish -> verify -> refresh same bookmark. Build once; no copying to Windows. No background daemon or automatic client write. Git may contain independent uncommitted GC27 r006: **stage/commit only exact TS_FULL paths**; never reset/stash/clean unrelated files.

### Browser state, proposals

- Static HTML with all four preview images embedded as data URI. No fetch/ajax, no CDN, no Internet, no localStorage/cookies, no server write on click.
- JS tabs + variant groups + status + source-backed bbox overlay + element details.
- Control input X, Y, W, H modifies **only drawn blue guide** and proposal JSON; it does not transform reference preview or persist canonical data.
- Button `Зберегти JSON` / `Копіювати JSON` exports operator proposal `{schema_version,build_id,source_sha256,approved:false,production_ready:false,operator_review_required:true,changes[]}`. A reviewer manually applies authorized bounded project patch, not via browser.
- Every preview displays explicit status `reference only`. No ability to mistake selected `JUBILEE` or `DUAL` for approved graphic output.

## 6. Technical governance and safety

- Project write scope: new-only TS_FULL registry/source/tests plus appended Makefile section; **TS01 and GC27 files untouched**.
- Client write scope: only `_forprint_automation/template_studio/` for one exact client; do not write in input, output, home, browser configuration, prepress repo or public web root.
- `client_workspace` requires existing direct child under `/srv/smb/In_Progress/data` and no symlinks in ancestors.
- Private SHA-pinned PDF: max 512 MiB, streaming SHA256 check before rendering, 4 pages, correct geometry.
- Static portal HTML: max 18 MiB, output path versioned and owned; `publication_manifest.json` records content digest; verify before replacing owned file.
- Atomic stable-index update and immutable release files; no broad deletion, no automatic overwrite of foreign client files, no hardcoded plaintext customer input in project Git.
- Native `.ai` editability and geometric parity are independent acceptance checkpoints, not proven by preview HTML.
- No automatic use of generated proposals as pricing, inventory, graphics approval, customer communication or orders.
- PDF reference may contain private texts/images; **never commit generated HTML/previews to public/private Git without explicit project data policy**. Only put them into project `tmp/` and the authorized client's private SMB workspace.

## 7. Operator acceptance checklist (human-in-the-loop)

- Open index from client SMB share on Windows in Chrome/Edge using existing authenticated access.
- Confirm `P01 P02 P03 P04` tabs navigate and show canonical references.
- Test P01 STANDARD / Branding / Bilingual and Birthday / Jubilee; observe status warning on unrendered variants.
- P02 locked; no variant controls.
- P03 Flowers / Portrait switching changes config/status and source-backed control guides; does **not** claim genuine variant preview until approved render wired.
- P04 GRIGO / HERASYMENKO / DUAL with explicit DUAL candidate-gated state.
- Click `P01-020` and `P04-020`: bbox and layer/step display. Select edit dimensions, add proposal, copy/download JSON; confirm real pixels never shift and no client sources change.
- Run `make ts-full-verify`, check SHA and test browser refresh after a new authorized publication; check bookmark remains identical.
- Compare four actual Illustrator `.ai` pages with approved PDF Builder on equal-resolution rasterization after future renderer integration. Confirm font, logos, clip shapes, signatures, physical frame geometry, editable layers.

## 8. Roadmap with measurable gates

**TSF-01 (this delivery):** 4-page registry + one static offline operator UI + all variant controls + safe project CLI + private client publish + synthetic tests. Requires s01 install and real PDF source check before claiming deployment. Browser e2e must be checked by operator.

**TSF-02:** source inventory for frame/background/actual clip, verify vector status; derive exact Illustrator layer structure. No geometry guessed.

**TSF-03:** approved visual preview for each *valid accepted* variant/combo; job-based preview manifest with SHA and review evidence; prevent outdated reference art masquerading as rendered output.

**TSF-04:** native Illustrator multi-artboard builder with numbered groups, distinct PAPER/PHOTO/CLIP/FRAME and source-managed text/logo/signature; compare all 4 pages to PDF Builder, editable AI proof and machine Worker Result.

**TSF-05:** operator tweak roundtrip: export JSON proposal -> bounded verifier -> reviewer authorization -> update model -> generate new previews -> re-publish same index. Reject unauthorized delta and keep previous release history.

**TSF-06:** controlled integration of actual accepted client jobs and automatic handoff into Illustrator; governance, reproducibility, source SHA and visual parity before promotion/printing; no browser action alone authorizes execution.

## 9. Handoff to future assistant

1. Inspect active Git branch/head and exact `git status` / staged state. Last known confirmed head at start of TS_FULL: `51e096bce464045b5272cf45f929d9583eb0fd2d` (2026-10-26); subsequent commits must be resolved live.
2. Preserve independent GC27 r006 work: as observed from s01, two modified GC27 source files and one new test. Do not reset, auto stash or commit together with TS_FULL.
3. Read `ts_full_registry_v0_1.json`, this document, `ts_full_publisher_v0_1.py`, `Makefile`, `gc23_prepress_variant_contract_v0_1.json`. Do not infer an absent native component as implemented.
4. Verify TS_FULL installation and tests on s01; use exact-path staging, `git diff --check`, and full regression. Commit/push only exact TS_FULL write set; user performs server operations and returns evidence.
5. Source manifest known from previous work: `../forprint_prepress_hub/tmp/gdl_greeting_card_private_resources_v0_1.yaml`. Never trust changed SHA, never place private PDF in Git.
6. Client folder (one currently known): `Виктория Беспалова _+380 67 793 00 15`, root `/srv/smb/In_Progress/data`, automation `_forprint_automation` with `input/` and `output/` already present. Publisher asks explicit authorization and writes only `template_studio/`.
7. User wants browser bookmark and refresh, no manual per-iteration file copying; use static HTML + same SMB client folder; no public service needed.
8. Source page screenshots are **not necessarily the same as accepted customer job**; browser first renders pinned 94MB canonical PDF. Future actual variants must have separate acceptance evidence and previews.
9. User prefers full four-page navigation and variants on each page, not separate tabs per variation. P01 occasion/branding, P03 photo, P04 signatures, P02 locked. Human labels, machine IDs.
10. When encountering ambiguous layer/source authority, record a technical question for System Blueprint instead of unilaterally editing governance.

## 10. Definition of done for TS_FULL v0.1 vs final program

**v0.1 functional acceptance:** code and tests installed on s01, PDF SHA verify PASS, build PASS, client publish PASS + verify PASS, browser screenshot from actual SMB path shows four pages and switchable configuration, reload picks up new authorized build. **Visual parity for all variants and native AI is explicitly outside v0.1**.

**Final program acceptance:** all permitted combinations have generated previews matching approved reference, Illustrator files maintain named editable layers and true vector clipping, exact content/fonts/layout/SHA, machine-readable result verified independently, design approval and production gates retained. Only after that call this a production-ready graphics constructor.
