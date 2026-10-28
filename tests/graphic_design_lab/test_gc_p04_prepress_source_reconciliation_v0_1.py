"""P04 pilot source reconciliation — static non-authorizing guard."""
from pathlib import Path
import json
import hashlib

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"coordination/graphic_design_lab/greeting_cards/gdl_gc_p04_prepress_source_reconciliation_v0_1.json"
DOC=ROOT/"coordination/graphic_design_lab/greeting_cards/gdl_gc_p04_prepress_source_reconciliation_v0_1.md"
PASSPORT=ROOT/"coordination/graphic_design_lab/template_studio/gdl_gc_review_and_output_passport_v0_1.md"
MAP=ROOT/"coordination/graphic_design_lab/template_studio/gc32_infrastructure_map_v0_1.json"

def test_source_snapshots_and_exact_hashes():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    assert d["schema_version"] == "gdl_gc_p04_prepress_source_reconciliation_v0_1"
    assert d["source_snapshot"]["git_head"] == "b26cce19f4700cadaf34323e4c2e2909bcf5fcd8"
    assert len(d["source_snapshot"]["source_file_sha256"])==11
    assert d["source_snapshot"]["source_file_sha256"]["app/graphic_design_lab/greeting_card_builder_renderer.py"] == "54fe79f387e04fb4205388a697fcf1744407e0489904a8ea082aa1c5c15f1852"
    assert all(len(h)==64 for h in d["source_snapshot"]["source_file_sha256"].values())

def test_owner_rules_not_tech_approval():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    r=d["owner_confirmed_pilot_rules"]
    assert r["greeting_bbox_fixed_mm"]==[32,32,182,212]
    assert all(r[k] for k in ("no_customer_text_rewrite","auto_adjust_font_size","auto_adjust_leading","no_enlargement_of_greeting_box","preserve_editable_native_area_text"))
    assert d["source_profile_verified"]["current_minimum_is_final_owner_approval"] is False
    assert set(d["authority"].values()) == {False}

def test_signature_variant_boundaries():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    s=d["source_profile_verified"]["sender"]
    assert s["GRIGO"]["start_y_pdf_mm"]==222.0
    assert s["HERASYMENKO"]["start_y_pdf_mm"]==224.5
    assert s["HERASYMENKO"]["signature_bbox_pdf_mm"]==[82.877,214.875,128.258,274.141]
    assert s["DUAL_GRIGO_HERASYMENKO"]["status"].startswith("RUNTIME_DISABLED")

def test_native_mismatch_not_hidden():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    n=d["native_gc29_source_observed"]
    assert n["rejects_with"]=="GC29_GREETING_OVERFLOW_REVIEW_REQUIRED"
    assert n["saved_ai_verified"] is False
    assert n["sender_variant_geometry_binding"] is False
    assert len(d["source_conflicts_to_reconcile"]) >= 5

def test_review_register_records_owner_feedback():
    reg=json.loads(MAP.read_text(encoding="utf-8"))["approval_register"]
    p=reg["p04_prepress_source_reconciliation"]
    assert p["path"]=="coordination/graphic_design_lab/greeting_cards/gdl_gc_p04_prepress_source_reconciliation_v0_1.json"
    assert p["native_fix_status"]=="NOT_IMPLEMENTED_NO_RETRY"
    q={q["id"]:q for group in reg["groups"] for q in group["questions"]}
    for i in ["GC-REV-008", "GC-REV-009"]:
        assert q[i]["state"]=="OWNER_DIRECTION_TO_FORMALIZE"
        assert q[i]["pilot_owner_decision_id"]
        assert q[i]["runtime_authority"] is False
    assert set(reg["authority"].values())=={False}

def test_documents_include_current_provenance_and_no_relaunch():
    a=DOC.read_text(encoding="utf-8")
    b=PASSPORT.read_text(encoding="utf-8")
    for tok in ["_fit_greeting", "Prepress Hub", "GC29", "DUAL", "не виконано", "222", "224.5"]:
        assert tok.lower() in (a+b).lower(),tok
    assert "GC29_GREETING_OVERFLOW_REVIEW_REQUIRED" in b
    assert "не дозволяє" in b
