# Illustrator Studio — межа фази 2B (нові клієнтські Handoff ZIP)

**Стан фази 2A:** дійсно підтримано лише генерацію версійованої інструкції Intake із канонічних джерел, її доставлення до приватної папки клієнта, read-only огляд ZIP у input та реєстрацію в технічному паспорті. Це не означає запуск нових замовлень.

**Перед 2B треба перевірити на сервері:** чинні gc47bm/gc47bc/gc47t/gc29/gc47s адаптери та їх SHA; відповідність actual private resource catalog; доказ independent operator review; портретний PNG alpha і візуальне приймання; нові job_id без чотирьох pin, багатозаявкові batch, вибір потрібного Handoff при кількох ZIP; відновлення/повторні спроби; незалежна native staging перевірка; publisher receipt та атомарний commit.

**Жодного bypass:** не дозволяти native новому ZIP через зміну тільки `JOBS`, `ACCEPTED_SHA`, `BM_SHA` чи імітацію `PASS` — це не означатиме, що новий bundle породжує правильні native scene/assets. Не вмикати автоматичну чергу. Новий bounded loader має пройти receipt provenance, binary resource binding, signature, branding та content/geometry contract.

**Джерела правди:** `intake_interface_contract_v1.json` для Intake, `intake_instruction_catalog_v1.json` для версійованих пакунків, `technical_passport_v1.json` для стану, `illustrator_studio_renderer_v1.jsx` та `design_config_v1.json` для native-дизайну. `tmp/` тільки staging/ZIP, не runtime.
