PYTHON ?= python3
.PHONY: f1-source-check f1-test
f1-source-check:
	$(PYTHON) -B scripts/graphic_design_lab/worker_runtime/gdl_f1_functional_pilot_v0_1.py --mode source-check
f1-test:
	$(PYTHON) -m pytest -q tests/graphic_design_lab/test_gdl_f1_functional_pilot_v0_1.py

# GC19: isolated Illustrator-native watermark assets from existing card reference.
GC19_NATIVE_WATERMARK_CLI := scripts/graphic_design_lab/greeting_cards/gc19_native_watermark_assets_v0_1.py
.PHONY: gc19-watermark-test gc19-watermark-inspect gc19-watermark-export

gc19-watermark-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc19_native_watermark_assets_v0_1.py

gc19-watermark-inspect:
	@test -n "$(RESOURCE_MANIFEST)" || (echo "Set RESOURCE_MANIFEST=/private/path/resources.yaml"; exit 2)
	$(PYTHON) -B $(GC19_NATIVE_WATERMARK_CLI) --mode inspect --resource-manifest "$(RESOURCE_MANIFEST)"

gc19-watermark-export:
	@test -n "$(RESOURCE_MANIFEST)" -a -n "$(OUTPUT_NAME)" || (echo "Set RESOURCE_MANIFEST=... OUTPUT_NAME=gc19_..."; exit 2)
	$(PYTHON) -B $(GC19_NATIVE_WATERMARK_CLI) --mode export --resource-manifest "$(RESOURCE_MANIFEST)" --output-name "$(OUTPUT_NAME)" --confirm-export

.PHONY: gc20-p02-test gc20-p02-check gc20-p02-export
gc20-p02-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc20_p02_native_background_v0_1.py
gc20-p02-check:
	@test -n "$(RESOURCE_MANIFEST)" -a -n "$(GC19_ASSETS_DIR)" || (echo "RESOURCE_MANIFEST and GC19_ASSETS_DIR required"; exit 2)
	$(PYTHON) -B scripts/graphic_design_lab/greeting_cards/gc20_p02_native_background_v0_1.py --mode check --resource-manifest "$(RESOURCE_MANIFEST)" --gc19-assets-dir "$(GC19_ASSETS_DIR)"
gc20-p02-export:
	@test -n "$(RESOURCE_MANIFEST)" -a -n "$(GC19_ASSETS_DIR)" -a -n "$(OUTPUT_NAME)" || (echo "RESOURCE_MANIFEST, GC19_ASSETS_DIR and OUTPUT_NAME required"; exit 2)
	$(PYTHON) -B scripts/graphic_design_lab/greeting_cards/gc20_p02_native_background_v0_1.py --mode export --resource-manifest "$(RESOURCE_MANIFEST)" --gc19-assets-dir "$(GC19_ASSETS_DIR)" --output-name "$(OUTPUT_NAME)" --confirm-export

# GC21: source-verified private 4-artboard Illustrator candidate (not production).
GC21_NATIVE_CLI ?= scripts/graphic_design_lab/greeting_cards/gc24_guarded_native_builder_v0_1.py
GC21_INPUTS_CONFIG ?=
GC21_SOURCE_ROOT ?= ../forprint_prepress_hub
GC21_GC19_DIR ?= tmp/gc19_native_watermarks_20261025_r001
GC21_GC20_DIR ?= tmp/gc20_p02_locked_base_20261025_r001
.PHONY: gc21-native-test gc21-native-check gc21-native-prepare
gc21-native-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc21_native_illustrator_builder_v0_1.py tests/graphic_design_lab/test_gc24_guarded_native_builder_v0_1.py
gc21-native-check:
	@test -n "$(GC21_INPUTS_CONFIG)" || (echo "Set GC21_INPUTS_CONFIG=/private/accepted/inputs.json"; exit 2)
	$(PYTHON) -B $(GC21_NATIVE_CLI) --mode check --inputs-config "$(GC21_INPUTS_CONFIG)" --source-root "$(GC21_SOURCE_ROOT)" --gc19-assets-dir "$(GC21_GC19_DIR)" --gc20-scene-dir "$(GC21_GC20_DIR)"
gc21-native-prepare:
	@test -n "$(GC21_INPUTS_CONFIG)" -a -n "$(OUTPUT_NAME)" -a "$(REAL_INPUTS_CONFIRM)" = "YES" || (echo "Set GC21_INPUTS_CONFIG=... OUTPUT_NAME=... REAL_INPUTS_CONFIRM=YES"; exit 2)
	$(PYTHON) -B $(GC21_NATIVE_CLI) --mode prepare --confirm-private-prepare --confirm-reviewed-real-inputs --inputs-config "$(GC21_INPUTS_CONFIG)" --source-root "$(GC21_SOURCE_ROOT)" --gc19-assets-dir "$(GC21_GC19_DIR)" --gc20-scene-dir "$(GC21_GC20_DIR)" --output-name "$(OUTPUT_NAME)"

# GC21 PREPRESS: single-use remote Illustrator pilot over SSH; no automatic retries.
GC21_REMOTE := scripts/graphic_design_lab/worker_runtime/gc21_s01_remote_operator_v0_1.py
.PHONY: gc21-remote-test gc21-remote-stage gc21-remote-check gc21-remote-launch gc21-remote-status
gc21-remote-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc21_s01_remote_operator_v0_1.py
gc21-remote-stage:
	$(PYTHON) -B $(GC21_REMOTE) --mode stage
gc21-remote-check:
	$(PYTHON) -B $(GC21_REMOTE) --mode check
gc21-remote-launch:
	$(PYTHON) -B $(GC21_REMOTE) --mode launch
gc21-remote-status:
	$(PYTHON) -B $(GC21_REMOTE) --mode status

# GC22: structural schematic preview. The Prepress Hub owns geometry; GDL reads only.
GC22_TOOL := scripts/graphic_design_lab/greeting_cards/gc22_template_reference_v0_3.py
GC22_SOURCE ?= ../forprint_prepress_hub
GC22_GC19 ?= tmp/gc19_native_watermarks_20261025_r001/manifest.json
GC22_OUT ?= tmp/template_catalog/greeting_card_a3_single_fold_v0_1/review_r001
.PHONY: gc22-template-test gc22-template-inspect gc22-template-verify gc22-template-prepare
gc22-template-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc22_template_reference_v0_3.py
gc22-template-inspect:
	$(PYTHON) -B $(GC22_TOOL) --mode inspect --prepress-root "$(abspath $(GC22_SOURCE))" --gc19-manifest "$(abspath $(GC22_GC19))"
gc22-template-verify:
	$(PYTHON) -B $(GC22_TOOL) --mode verify --prepress-root "$(abspath $(GC22_SOURCE))" --gc19-manifest "$(abspath $(GC22_GC19))" --gdl-root "$(CURDIR)" --output-dir "$(abspath $(GC22_OUT))"
gc22-template-prepare:
	$(PYTHON) -B $(GC22_TOOL) --mode prepare --prepress-root "$(abspath $(GC22_SOURCE))" --gc19-manifest "$(abspath $(GC22_GC19))" --gdl-root "$(CURDIR)" --output-dir "$(abspath $(GC22_OUT))"

# GC23: source-pinned variant contract (read-only, no renderer / publication authority).
GC23_VARIANTS := scripts/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.py
GC23_PREPRESS_SOURCE ?= ../forprint_prepress_hub
.PHONY: gc23-variants-test gc23-variants-catalog gc23-variants-source-check gc23-variants-preflight
gc23-variants-test:
	GC23_PREPRESS_ROOT="$(abspath $(GC23_PREPRESS_SOURCE))" $(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc23_prepress_variant_contract_v0_1.py
gc23-variants-catalog:
	$(PYTHON) -B $(GC23_VARIANTS) --mode catalog
gc23-variants-source-check:
	$(PYTHON) -B $(GC23_VARIANTS) --mode source-check --prepress-root "$(abspath $(GC23_PREPRESS_SOURCE))"
gc23-variants-preflight:
	@test -n "$(INPUTS_CONFIG)" -a -n "$(SOURCE_ROOT)" || (echo "INPUTS_CONFIG and SOURCE_ROOT required"; exit 2)
	$(PYTHON) -B $(GC23_VARIANTS) --mode preflight --inputs-config "$(INPUTS_CONFIG)" --source-root "$(SOURCE_ROOT)"

# GC24: safe GC21 real-accepted-input route; no new renderer and no production authority.
.PHONY: gc24-guard-test
gc24-guard-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc24_guarded_native_builder_v0_1.py

# GC25: independent GDL Illustrator SMB preflight launcher; read-only, no native render.
GC25_ILLUSTRATOR_QUEUE := scripts/graphic_design_lab/greeting_cards/gc25_illustrator_smb_preflight_v0_1.py
.PHONY: gc25-illustrator-queue-test gc25-illustrator-queue-check
gc25-illustrator-queue-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc25_illustrator_smb_preflight_v0_1.py
gc25-illustrator-queue-check:
	@test -n "$(SHARE)" -a -n "$(WORKSPACE_RELATIVE_B64)" || (echo "SHARE and WORKSPACE_RELATIVE_B64 required"; exit 2)
	$(PYTHON) -B $(GC25_ILLUSTRATOR_QUEUE) --mode check --share "$(SHARE)" --workspace-relative-b64 "$(WORKSPACE_RELATIVE_B64)"

# GC26: rebuildable one-client Illustrator Windows launcher (create missing only).
GC26_CLIENT_INSTALLER := scripts/graphic_design_lab/greeting_cards/gc26_illustrator_client_launcher_deploy_v0_1.py
.PHONY: gc26-launcher-test gc26-launcher-discover gc26-launcher-check gc26-launcher-install
gc26-launcher-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc26_illustrator_client_launcher_deploy_v0_1.py
gc26-launcher-discover:
	$(PYTHON) -B $(GC26_CLIENT_INSTALLER) --mode discover
gc26-launcher-check:
	@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME required"; exit 2)
	$(PYTHON) -B $(GC26_CLIENT_INSTALLER) --mode check --client-name "$(CLIENT_NAME)"
gc26-launcher-install:
	@test -n "$(CLIENT_NAME)" -a "$(CONFIRM_INSTALL)" = YES || (echo "CLIENT_NAME=... CONFIRM_INSTALL=YES required"; exit 2)
	$(PYTHON) -B $(GC26_CLIENT_INSTALLER) --mode install --client-name "$(CLIENT_NAME)" --confirm-install

# GC27: independent P03 DEFAULT_ASSET native Illustrator proof; NOT full four-page card.
GC27_P03_NATIVE := scripts/graphic_design_lab/greeting_cards/gc27_p03_default_flowers_v0_1.py
GC27_CLIENT_NAME ?=
GC27_PACKAGE_NAME ?=
GC27_RESOURCE_MANIFEST ?=
GC27_RESOURCE_SOURCE_ROOT ?= ../forprint_prepress_hub
.PHONY: gc27-p03-test gc27-p03-check gc27-p03-prepare
gc27-p03-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc27_p03_default_flowers_v0_1.py
gc27-p03-check:
	@test -n "$(GC27_CLIENT_NAME)" -a -n "$(GC27_PACKAGE_NAME)" -a -n "$(GC27_RESOURCE_MANIFEST)" || (echo "GC27_CLIENT_NAME, GC27_PACKAGE_NAME, GC27_RESOURCE_MANIFEST required"; exit 2)
	$(PYTHON) -B $(GC27_P03_NATIVE) --mode check --client-name "$(GC27_CLIENT_NAME)" --package-name "$(GC27_PACKAGE_NAME)" --resource-manifest "$(GC27_RESOURCE_MANIFEST)" --source-root "$(GC27_RESOURCE_SOURCE_ROOT)"
gc27-p03-prepare:
	@test -n "$(GC27_CLIENT_NAME)" -a -n "$(GC27_PACKAGE_NAME)" -a -n "$(GC27_RESOURCE_MANIFEST)" -a -n "$(OUTPUT_NAME)" -a "$(CONFIRM_PRIVATE_PREPARE)" = YES || (echo "GC27_CLIENT_NAME, GC27_PACKAGE_NAME, GC27_RESOURCE_MANIFEST, OUTPUT_NAME, CONFIRM_PRIVATE_PREPARE=YES required"; exit 2)
	$(PYTHON) -B $(GC27_P03_NATIVE) --mode prepare --confirm-private-prepare --client-name "$(GC27_CLIENT_NAME)" --package-name "$(GC27_PACKAGE_NAME)" --resource-manifest "$(GC27_RESOURCE_MANIFEST)" --source-root "$(GC27_RESOURCE_SOURCE_ROOT)" --output-name "$(OUTPUT_NAME)"

# TS01 Template Studio: P01 STANDARD reference visual passport, no native master or client publication.
TS01_P01_CLI := scripts/graphic_design_lab/template_studio/ts01_p01_visual_passport_v0_1.py
TS01_RESOURCE_MANIFEST ?=
TS01_SOURCE_ROOT ?= ../forprint_prepress_hub
.PHONY: ts01-p01-test ts01-p01-check ts01-p01-prepare
ts01-p01-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_ts01_p01_visual_passport_v0_1.py
ts01-p01-check:
	@test -n "$(TS01_RESOURCE_MANIFEST)" || (echo "Set TS01_RESOURCE_MANIFEST=/private/path/resources.yaml"; exit 2)
	$(PYTHON) -B $(TS01_P01_CLI) --mode check --resource-manifest "$(TS01_RESOURCE_MANIFEST)" --source-root "$(TS01_SOURCE_ROOT)"
ts01-p01-prepare:
	@test -n "$(TS01_RESOURCE_MANIFEST)" -a -n "$(OUTPUT_NAME)" -a "$(CONFIRM_PRIVATE_PREPARE)" = YES || (echo "Set TS01_RESOURCE_MANIFEST=... OUTPUT_NAME=ts01_p01_... CONFIRM_PRIVATE_PREPARE=YES"; exit 2)
	$(PYTHON) -B $(TS01_P01_CLI) --mode prepare --confirm-private-prepare --resource-manifest "$(TS01_RESOURCE_MANIFEST)" --source-root "$(TS01_SOURCE_ROOT)" --output-name "$(OUTPUT_NAME)"

# Template Studio FULL: private static 4-page operator GUI, no render or print authority.
TS_FULL_CLI := scripts/graphic_design_lab/template_studio/ts_full_publisher_v0_1.py
TS_FULL_RESOURCE_MANIFEST ?=
TS_FULL_SOURCE_ROOT ?= ../forprint_prepress_hub
.PHONY: ts-full-test ts-full-check ts-full-build ts-full-publish ts-full-verify
ts-full-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_ts_full_publisher_v0_1.py
ts-full-check:
	@test -n "$(TS_FULL_RESOURCE_MANIFEST)" || (echo "TS_FULL_RESOURCE_MANIFEST required"; exit 2)
	$(PYTHON) -B $(TS_FULL_CLI) --mode check --resource-manifest "$(TS_FULL_RESOURCE_MANIFEST)" --source-root "$(TS_FULL_SOURCE_ROOT)"
ts-full-build:
	@test -n "$(TS_FULL_RESOURCE_MANIFEST)" -a -n "$(OUTPUT_NAME)" || (echo "TS_FULL_RESOURCE_MANIFEST OUTPUT_NAME required"; exit 2)
	$(PYTHON) -B $(TS_FULL_CLI) --mode build --resource-manifest "$(TS_FULL_RESOURCE_MANIFEST)" --source-root "$(TS_FULL_SOURCE_ROOT)" --output-name "$(OUTPUT_NAME)"
ts-full-publish:
	@test -n "$(CLIENT_NAME)" -a -n "$(BUILD_DIR)" -a "$(CONFIRM_PUBLISH)" = YES || (echo "CLIENT_NAME BUILD_DIR CONFIRM_PUBLISH=YES required"; exit 2)
	$(PYTHON) -B $(TS_FULL_CLI) --mode publish --client-name "$(CLIENT_NAME)" --build-dir "$(BUILD_DIR)" --confirm-publish
ts-full-verify:
	@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME required"; exit 2)
	$(PYTHON) -B $(TS_FULL_CLI) --mode verify --client-name "$(CLIENT_NAME)"

# GC32: single PREPRESS root + TS FULL infrastructure portal, docs WARN only.
GC32_INFRA := scripts/graphic_design_lab/greeting_cards/gc32_infrastructure_portal_v0_1.py
GC32_CLIENT ?=
.PHONY: gc32-test gc32-documentation-check gc32-worker-check gc32-worker-install gc32-portal-check gc32-portal-refresh
gc32-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc32_single_root_portal_v0_1.py
	$(PYTHON) -B $(GC32_INFRA) --mode audit
gc32-documentation-check:
	$(PYTHON) -B $(GC32_INFRA) --mode audit
gc32-worker-check:
	@test -n "$(GC32_CLIENT)" || (echo "GC32_CLIENT required"; exit 2)
	$(PYTHON) -B $(GC32_INFRA) --mode worker-check --client-name "$(GC32_CLIENT)"
gc32-worker-install:
	@test -n "$(GC32_CLIENT)" -a "$(CONFIRM_INSTALL)" = YES || (echo "GC32_CLIENT / CONFIRM_INSTALL=YES required"; exit 2)
	$(PYTHON) -B $(GC32_INFRA) --mode worker-install --client-name "$(GC32_CLIENT)" --confirm
gc32-portal-check:
	@test -n "$(GC32_CLIENT)" || (echo "GC32_CLIENT required"; exit 2)
	$(PYTHON) -B $(GC32_INFRA) --mode portal-check --client-name "$(GC32_CLIENT)"
gc32-portal-refresh:
	@test -n "$(GC32_CLIENT)" -a "$(CONFIRM_PUBLISH)" = YES || (echo "GC32_CLIENT / CONFIRM_PUBLISH=YES required"; exit 2)
	$(PYTHON) -B $(GC32_INFRA) --mode portal-refresh --client-name "$(GC32_CLIENT)" --confirm

# GC32 Atlas: one canonical portal with conceptual + observed directory trees.
GC32_ATLAS := scripts/graphic_design_lab/greeting_cards/gc32_structure_atlas_v0_1.py
.PHONY: gc32-atlas-test gc32-atlas-check
gc32-atlas-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc32_structure_atlas_v0_1.py tests/graphic_design_lab/test_gc32_single_root_portal_v0_1.py
gc32-atlas-check:
	@test -n "$(GC32_CLIENT)" || (echo "Set GC32_CLIENT=..."; exit 2)
	$(PYTHON) -B $(GC32_ATLAS) --client-name "$(GC32_CLIENT)"

.PHONY: gc32-atlas-scanner-check gc32-atlas-scanner-install
gc32-atlas-scanner-check:
	@test -n "$(GC32_CLIENT)" || (echo "Set GC32_CLIENT=..."; exit 2)
	$(PYTHON) -B $(GC32_ATLAS) --mode scanner-check --client-name "$(GC32_CLIENT)"
gc32-atlas-scanner-install:
	@test -n "$(GC32_CLIENT)" -a "$(CONFIRM_INSTALL)" = YES || (echo "GC32_CLIENT and CONFIRM_INSTALL=YES required"; exit 2)
	$(PYTHON) -B $(GC32_ATLAS) --mode scanner-install --client-name "$(GC32_CLIENT)" --confirm

# GC32 Atlas: remote PREPRESS inventory over EXISTING SSH, without Windows->SMB writes.
GC32_SSH_INVENTORY := scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py
.PHONY: gc32-ssh-inventory-test gc32-ssh-inventory-capture gc32-ssh-inventory-review gc32-ssh-inventory-publish
gc32-ssh-inventory-test:
	$(PYTHON) -m pytest -q -p no:cacheprovider tests/graphic_design_lab/test_gc32_ssh_inventory_lifecycle_v0_1.py
gc32-ssh-inventory-capture:
	@test -n "$(GC32_CLIENT)" || (echo "GC32_CLIENT required"; exit 2)
	$(PYTHON) -B $(GC32_SSH_INVENTORY) --mode capture --client-name "$(GC32_CLIENT)"
gc32-ssh-inventory-review:
	@test -n "$(GC32_CLIENT)" -a -n "$(GC32_CAPTURE_DIR)" || (echo "GC32_CLIENT and GC32_CAPTURE_DIR required"; exit 2)
	$(PYTHON) -B $(GC32_SSH_INVENTORY) --mode review --client-name "$(GC32_CLIENT)" --run-dir "$(GC32_CAPTURE_DIR)"
gc32-ssh-inventory-publish:
	@test -n "$(GC32_CLIENT)" -a -n "$(GC32_CAPTURE_DIR)" -a "$(CONFIRM_PUBLISH)" = YES || (echo "GC32_CLIENT, GC32_CAPTURE_DIR and CONFIRM_PUBLISH=YES required"; exit 2)
	$(PYTHON) -B $(GC32_SSH_INVENTORY) --mode publish --client-name "$(GC32_CLIENT)" --run-dir "$(GC32_CAPTURE_DIR)" --confirm-publish

# GC32 r005: versioned PREPRESS inventory scanner under the existing Automation/Worker root.
# One-time installation via s01 -> PREPRESS, then SHA-verified read-only capture.
.PHONY: gc32-ssh-scanner-check gc32-ssh-scanner-install

gc32-ssh-scanner-check:
	@test -n "$(GC32_CLIENT)" || (echo "GC32_CLIENT required"; exit 2)
	$(PYTHON) -B scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py --mode scanner-check --client-name "$(GC32_CLIENT)"

gc32-ssh-scanner-install:
	@test -n "$(GC32_CLIENT)" -a "$(CONFIRM_INSTALL)" = "YES" || (echo "GC32_CLIENT=... CONFIRM_INSTALL=YES required"; exit 2)
	$(PYTHON) -B scripts/graphic_design_lab/greeting_cards/gc32_ssh_inventory_lifecycle_v0_1.py --mode scanner-install --client-name "$(GC32_CLIENT)" --confirm-install

# GC47AI Illustrator-first operator launcher r001 (additive, non-release).
GC47AI_CLI := scripts/graphic_design_lab/greeting_cards/gc47ai_illustrator_first_launcher_r001.py
GC47AI_PY := .venv_gdl/bin/python
.PHONY: gdl-card-launcher gdl-card-launcher-test gdl-card-launcher-check gdl-card-launcher-list gdl-card-launcher-inspect gdl-card-launcher-routes
gdl-card-launcher:
	$(GC47AI_PY) -B $(GC47AI_CLI) --mode interactive
gdl-card-launcher-test:
	$(GC47AI_PY) -B tests/graphic_design_lab/test_gc47ai_illustrator_first_launcher_r001.py
gdl-card-launcher-check:
	$(GC47AI_PY) -B $(GC47AI_CLI) --mode check
gdl-card-launcher-list:
	$(GC47AI_PY) -B $(GC47AI_CLI) --mode list
gdl-card-launcher-inspect:
	@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME required"; exit 2)
	$(GC47AI_PY) -B $(GC47AI_CLI) --mode inspect --client-name "$(CLIENT_NAME)"
gdl-card-launcher-routes:
	$(GC47AI_PY) -B $(GC47AI_CLI) --mode routes
# GC47AI_END

# GC47AJ: client-local entrypoint; operator logic GDL-owned; review only.
GC47AJ_PY := .venv_gdl/bin/python
GC47AJ_UI := scripts/graphic_design_lab/greeting_cards/gc47aj_client_operator_r001.py
GC47AJ_DEPLOY := scripts/graphic_design_lab/greeting_cards/gc47aj_client_entry_deploy_r001.py
.PHONY: gdl-client-launcher-test gdl-client-launcher-check gdl-client-launcher-install

gdl-client-launcher-test:
	$(GC47AJ_PY) -B tests/graphic_design_lab/test_gc47aj_client_operator_r001.py

gdl-client-launcher-check:
	@test -n "$(CLIENT_NAME)" || (echo "CLIENT_NAME=... required"; exit 2)
	$(GC47AJ_PY) -B $(GC47AJ_DEPLOY) --mode check --client-name "$(CLIENT_NAME)"

gdl-client-launcher-install:
	@test -n "$(CLIENT_NAME)" -a "$(CONFIRM_INSTALL)" = YES || (echo "CLIENT_NAME=... CONFIRM_INSTALL=YES required"; exit 2)
	$(GC47AJ_PY) -B $(GC47AJ_DEPLOY) --mode install --client-name "$(CLIENT_NAME)" --confirm-install
# GC47AJ_END

# GC47AN: scoped acceptance/commit gate; never renders or approves production.
GC47AN_CLI := scripts/graphic_design_lab/greeting_cards/gc47an_launcher_checkpoint_r001.py
.PHONY: gdl-launcher-acceptance gdl-launcher-acceptance-test gdl-launcher-git-plan
gdl-launcher-acceptance:
	.venv_gdl/bin/python -B $(GC47AN_CLI) --mode audit --client-name "$(CLIENT_NAME)" --job "$(JOB)" --attempt "$(ATTEMPT)"
gdl-launcher-acceptance-test:
	.venv_gdl/bin/python -B tests/graphic_design_lab/test_gc47an_launcher_checkpoint_r001.py
gdl-launcher-git-plan:
	.venv_gdl/bin/python -B $(GC47AN_CLI) --mode plan --client-name "$(CLIENT_NAME)" --job "$(JOB)" --attempt "$(ATTEMPT)"
# GC47AN_END
