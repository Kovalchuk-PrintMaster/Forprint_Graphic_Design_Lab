# P04 — звірка чинного Prepress Hub з GC29 (read-only audit)

**Дата:** 2026-10-28. **GDL HEAD at source review:** `93b205e` (з журналу оператора).
**Prepress Hub snapshot HEAD:** `b26cce19f4700cadaf34323e4c2e2909bcf5fcd8`.
**Audit archive:** SHA256 `31856da56b97e38da1ccdeb822798b0f04c2a02815e325fd4b90619b6347f6df`.
**Status:** `SOURCE_VERIFIED_OWNER_PILOT_RULES_CONFIRMED_NOT_IMPLEMENTED`.
**Native GC29 patch і повторний Illustrator запуск не виконано.**

## Джерела

- `app/graphic_design_lab/greeting_card_builder_renderer.py` — SHA256 `54fe79f387e04fb4205388a697fcf1744407e0489904a8ea082aa1c5c15f1852`
- `coordination/graphic_design_lab/directions/greeting_cards/geometry_zones_v0_1.yaml` — SHA256 `871ac1d91e117dfefd074f4d73b78369165c7899e13db90b21f96aab00ca800f`
- `coordination/graphic_design_lab/directions/greeting_cards/page4_canonical_repair_profile_v0_1.yaml` — SHA256 `ded49cc466a152d246851bebf78a6067422c434dfb4e359a828c35058dbfdc02`
- `coordination/graphic_design_lab/directions/greeting_cards/signature_registry_v0_1.yaml` — SHA256 `d6e5acf5ce0154f32f236f2ca8c98e00e078217c4589d564ead1e38b6ffff577`
- `coordination/graphic_design_lab/directions/greeting_cards/deterministic_builder_v0_1.yaml` — SHA256 `74006ffde51b93bd6796d40a68f990f5120d6f5f07687f3fe721eedfaa5aa319`

У ZIP 11 файлів, SHA256 кожного збігся зі `SOURCE_AUDIT.json`. У цьому пакеті
не копіюються приватні матеріали клієнта і не модифікується Prepress Hub.

## Висновок із реального source code

| Контроль | Prepress Hub (верифікований source) | GC29 JSX (історичний r009 snapshot) | Вимога до GDL |
|---|---|---|---|
| Габарит привітання | `[32,32,182,212]` мм, 150×180 | ті самі 150×180 | Не змінювати |
| Кегль | 7 мм ≈ 19,8425 pt; fallback 18,5/17/16,5/16 pt | тільки 7 мм | Підлаштування з доказовим виміром |
| Міжряддя | 8 мм / 7 мм ratio, ascender-aware PDF | тільки 8 мм | Параметризувати разом із кеглем |
| Вміщення | фактичний `insert_textbox` у scratch PDF | `t.lines.length × 8 < 164 мм` | Прибрати самовільний 20-row поріг |
| Вирівнювання | вертикальний центр в effective safe rect | `spaceBefore` першого абзацу | Звірити з GC18 Illustrator Center action |
| Відступ унизу | 2 візуальні рядки | 164 мм hard limit | Не плутати з full-box height; аудити bounds |
| Підписант | GRIGO y=222, HERASYMENKO y=224.5 | baselines 227/235/243/251 для всіх | Variant-aware canonical sender contract |
| Графічний підпис | source-verified vector GRIGO, raster RGBA HERASYMENKO | окремий graphics layer | Preserve exact-source geometry |
| Watermark | 25%, source bbox | існує окремий шар | Огляд P04 без нової геометрії |
| DUAL | кандидат, вимкнено | не підтримується | Не активувати |

**Суперечність старого YAML:** `deterministic_builder_v0_1.yaml` ще декларує
`[22.5,20.0,17.0]`, тоді як актуальний `greeting_card_builder_renderer.py`
містить `[19.8425,18.5,17.0,16.5,16.0]`. Конкретні renderer
і `page4_canonical_repair_profile_v0_1.yaml` мають бути відправною точкою
source parity; **жоден legacy контракт не переписано автоматично**.

## Обмеження доказу

- Код `_fit_greeting` підтверджений, але цей audit **не запускав live Builder** та
  **не доводить повної нативної відповідності**.
- Не включено всі допоміжні `canonical_sender`/`sender_typography`/source private PDFs.
- Після першої спроби DEG результат — `BLOCKED_REVIEW_REQUIRED`, лише `result.json`.
- Невдала спроба збережена; нова має бути окремим attempt, без перезапису.
- Візуальний вигляд P04 прийнято як пілотну основу, не як customer або print approval.

## Пілотне рішення власника

Повний текст без зміни змісту; зона не збільшується; font size/leading адаптуються;
незначні візуальні відхилення не повинні переривати формування артефакту для
людського огляду. Відсутність/пошкодження ресурсів, втрата тексту чи помилка save
залишаються технічними блокерами. Координати підписів — із перевірених джерел.

## Наступні межі

1. Витягти відсутні sender planner dependencies з поточного Prepress Hub через
   окремий read-only audit (не містити приватні тексти в публічних логах).
2. Підготувати GC29 native fit patch у GDL із регресією довгого DEG тексту,
   geometry proof, source hash і окремим result status.
3. Запускати лише **новий attempt** через клієнтську SMB точку входу; стару
   stage/out зберігати. Виміряти фактичні native bounds, save-close-reopen.
4. Повернення результату до SMB output й автоматичне очищення лишити окремим
   work front до перевіреного return receipt.
