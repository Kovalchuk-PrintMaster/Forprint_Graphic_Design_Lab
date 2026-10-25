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
