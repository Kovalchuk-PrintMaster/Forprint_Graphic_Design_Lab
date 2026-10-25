PYTHON ?= python3
.PHONY: f1-source-check f1-test
f1-source-check:
	$(PYTHON) -B scripts/graphic_design_lab/worker_runtime/gdl_f1_functional_pilot_v0_1.py --mode source-check
f1-test:
	$(PYTHON) -m pytest -q tests/graphic_design_lab/test_gdl_f1_functional_pilot_v0_1.py
