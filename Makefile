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
