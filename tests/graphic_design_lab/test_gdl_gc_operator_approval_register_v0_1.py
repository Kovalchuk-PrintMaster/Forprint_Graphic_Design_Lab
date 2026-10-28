import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json"
UI = ROOT / "scripts/graphic_design_lab/template_studio/ts_full_ui_v0_1.html"
DOC = ROOT / "coordination/graphic_design_lab/template_studio/gdl_gc_review_and_output_passport_v0_1.md"

@pytest.fixture
def model():
    return json.loads(MAP.read_text(encoding="utf-8"))["approval_register"]

def test_machine_schema_and_authority(model):
    assert model["schema_version"] == "forprint_gdl_gc_operator_review_register_v0_1"
    assert model["normative_rule"] == "ONLY_EXPLICIT_OWNER_AGREEMENTS_BECOME_CANONICAL_CONSTRUCTOR_RULES"
    assert model["source_of_truth"].startswith("s01/")
    assert model["operator_entry"] == "client_SMB/_forprint_automation"
    assert set(model["authority"].values()) == {False}

def test_grouped_questions_unique_and_tied_to_blocks(model):
    assert len(model["groups"]) == 5
    ids = [q["id"] for g in model["groups"] for q in g["questions"]]
    assert len(ids) == 14 and len(set(ids)) == 14
    for group in model["groups"]:
        assert group["theme"] and group["title_ua"]
        for q in group["questions"]:
            assert q["block_id"] and q["observed"] and q["question_to_owner"] and q["working_proposal"]
            assert q["runtime_authority"] is False
            assert q["state"] in {"OPEN_FOR_OWNER_REVIEW","OWNER_DIRECTION_TO_FORMALIZE","FUTURE_DECISION"}

def test_first_native_result_not_misrepresented(model):
    p = model["pilot"]
    assert p["observed_state"] == "BLOCKED_REVIEW_REQUIRED"
    assert p["observed_error"] == "GC29_GREETING_OVERFLOW_REVIEW_REQUIRED"
    assert p["saved_ai_verified"] is False
    assert p["result_json_only"] is True
    assert p["artboards_visible_in_screenshot"] == 4
    assert p["no_production_authority"] is True

def test_naming_is_compact_safe_and_not_implemented(model):
    n = model["naming_working_proposal"]
    assert n["format"] == "{zip_stem}_YYMMDD-HHMMSS"
    assert len(n["example"]) < 25
    assert n["input_basename_source"] == "OPERATOR_CHOSEN_SOURCE_ZIP_STEM"
    assert n["status"] == "PROPOSAL_NOT_IMPLEMENTED"
    assert "ATOMIC" in n["collision_policy"]
    assert "NO_OVERWRITE" in n["collision_policy"]

def test_cleanup_not_authorized(model):
    assert model["authority"]["automatic_cleanup"] is False
    q = {x["block_id"]: x for g in model["groups"] for x in g["questions"]}
    assert "DELETE_FORBIDDEN" in q["WORKER.CLEANUP"]["working_proposal"]
    assert q["WORKER.OPTIONAL_PERSISTENCE"]["state"] == "FUTURE_DECISION"

def test_html_has_real_tab_and_derived_rendering(model):
    h = UI.read_text(encoding="utf-8")
    for token in ["Питання на погодження", "id=\"review-shell\"", "function renderReview()", "function reviewDraft()", "INFRA.approval_register", "groups.forEach(", "review-notes"]:
        if token == "review-notes":
            assert "reviewNotes" in h
        else:
            assert token in h
    assert h.count("/*__TS_INFRA__*/") == 1
    assert "fetch(" not in h

def test_readonly_draft_export(model):
    h = UI.read_text(encoding="utf-8")
    assert "automatic_approval:false" in h
    assert "automatic_runtime_write:false" in h
    assert "approved:false" in h
    assert "review-download" in h and "review-copy" in h
    assert "reviewNotes[q.id]" in h

def test_doc_explicitly_separates_owner_direction_and_final_rules():
    d = DOC.read_text(encoding="utf-8")
    for token in ["Observed", "Operator expected", "Approved rule", "НЕ дозвіл на очищення", "YYMMDD-HHMMSS", "MAKE", "NO_AUTO_CLEANUP"]:
        assert token.lower() in d.lower()
    assert "compound_path(2).pdf" in d and "flower_photo.png" in d
    assert "GC29_GREETING_OVERFLOW_REVIEW_REQUIRED" in d

def test_existing_execution_model_and_atlas_not_overwritten():
    data = json.loads(MAP.read_text(encoding="utf-8"))
    assert data["execution_model"]["schema_version"] == "forprint_gdl_client_entry_worker_lifecycle_v0_1"
    assert len(data["execution_model"]["paths"]) == 2
    assert "structure_atlas_visual_revision" in data
