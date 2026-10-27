#!/usr/bin/env python3
"""ForPrint GDL Template Studio TS01: source-pinned P01 STANDARD visual passport.

Read-only check, or create-new private images + offline operator HTML under GDL/tmp.
Does not modify artwork, source PDF, Prepress Hub, or approved contracts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import html
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import fitz
from PIL import Image, ImageDraw, ImageFont
import yaml

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "coordination/graphic_design_lab/template_studio/ts01_p01_standard_elements_v0_1.json"
CATALOG = ROOT / "coordination/graphic_design_lab/greeting_cards/gc23_prepress_variant_contract_v0_1.json"
TMP = ROOT / "tmp"
SCHEMA = "forprint_gdl_template_studio_p01_standard_v0_1"
MM = 72 / 25.4
MAX_PDF = 512 * 1024 * 1024
NAME_RE = re.compile(r"^ts01_p01_[a-z0-9_]{4,72}$")


class GateError(ValueError):
    pass


def require(test: bool, code: str) -> None:
    if not test:
        raise GateError(code)


def file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "REGISTRY_MISSING_OR_UNSAFE")
    data = json.loads(path.read_text(encoding="utf8"))
    require(isinstance(data, dict), "REGISTRY_INVALID")
    return data


def validated_registry(reg: dict[str, Any], gc23: dict[str, Any]) -> list[dict[str, Any]]:
    require(reg.get("schema_version") == SCHEMA, "TS01_REGISTRY_SCHEMA_INVALID")
    require(reg.get("template_id") == "greeting_card.p01.standard", "TS01_TEMPLATE_ID_INVALID")
    require(reg.get("media_mm") == gc23.get("physical_size_mm") == [214, 301], "TS01_MEDIA_CONTRACT_CHANGED")
    require(reg.get("trim_mm") == gc23.get("trim_size_mm") == [210, 297], "TS01_TRIM_CONTRACT_CHANGED")
    require(reg.get("physical_page") == 1 and reg.get("layout_variant") == "STANDARD", "TS01_VARIANT_INVALID")
    require(reg.get("coordinate_system") == "PDF_TOP_LEFT_MM", "TS01_COORDINATE_SYSTEM_INVALID")
    approval = reg.get("approval") or {}
    require(all(approval.get(x) is False for x in ("design_approved", "production_ready", "automatic_promotion")),
            "TS01_AUTHORITY_FORBIDDEN")
    elements = reg.get("elements")
    require(isinstance(elements, list) and len(elements) == 5, "TS01_ELEMENT_COUNT_INVALID")
    ids = [e.get("id") for e in elements]
    require(ids == ["P01-010", "P01-015", "P01-020", "P01-030", "P01-900"], "TS01_ELEMENT_IDS_INVALID")
    steps = [e.get("step") for e in elements]
    require(steps == sorted(set(steps)), "TS01_OPERATION_ORDER_INVALID")
    pinned = gc23.get("front_variants", {}).get("STANDARD", {})
    expected = {"P01-020": pinned.get("sender_logo_bbox_mm"), "P01-030": pinned.get("occasion_bbox_mm")}
    for e in elements:
        require(isinstance(e, dict) and str(e.get("layer", "")).startswith(("P01.", "_FORPRINT_")), "TS01_LAYER_INVALID")
        require(isinstance(e.get("parameter_controls"), list) and isinstance(e.get("default_locked"), bool), "TS01_PARAMS_INVALID")
        box = e.get("bbox_pdf_mm")
        if e["id"] in expected:
            require(box == expected[e["id"]], "TS01_PINNED_ELEMENT_GEOMETRY_DRIFT")
            require(e.get("geometry_status") == "SOURCE_PINNED_GC23_STANDARD", "TS01_PINNED_STATUS_INVALID")
            require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in box), "TS01_BBOX_NONFINITE")
            require(0 <= box[0] < box[2] <= 214 and 0 <= box[1] < box[3] <= 301, "TS01_BBOX_OUTSIDE_MEDIA")
        else:
            require(box is None, "TS01_UNVERIFIED_BBOX_MUST_BE_NULL")
    return elements


def resolve_source(manifest: Path, source_root: Path | None, gc23: dict[str, Any]) -> Path:
    require(manifest.is_file() and not manifest.is_symlink(), "TS01_RESOURCE_MANIFEST_MISSING")
    data = yaml.safe_load(manifest.read_text(encoding="utf8"))
    require(isinstance(data, dict) and data.get("schema_version") == "gdl_greeting_card_private_resource_manifest_v0_1", "TS01_MANIFEST_SCHEMA")
    ref_id = gc23["resource_ids"]["reference_pdf"]
    expected = gc23["pinned_sha256"]["reference_pdf"]
    binding = data.get("resources", {}).get(ref_id)
    require(isinstance(binding, dict), "TS01_REFERENCE_BINDING_MISSING")
    require(binding.get("sha256", expected) == expected, "TS01_REFERENCE_BINDING_SHA_INVALID")
    val = binding.get("path")
    require(isinstance(val, str) and val.strip(), "TS01_REFERENCE_PATH_INVALID")
    ref = Path(val)
    if not ref.is_absolute():
        require(source_root is not None and source_root.is_dir() and not source_root.is_symlink(), "TS01_REFERENCE_ROOT_REQUIRED")
        ref = source_root / ref
    require(ref.is_file() and not ref.is_symlink(), "TS01_REFERENCE_FILE_MISSING_OR_UNSAFE")
    require(0 < ref.stat().st_size <= MAX_PDF, "TS01_REFERENCE_SIZE_INVALID")
    require(file_sha(ref) == expected, "TS01_REFERENCE_SHA_MISMATCH")
    return ref


def inspect_pdf(ref: Path) -> None:
    with fitz.open(ref) as doc:
        require(doc.page_count == 4, "TS01_REFERENCE_NOT_FOUR_PAGES")
        p = doc[0]
        require(abs(p.rect.width - 214 * MM) < 0.15 and abs(p.rect.height - 301 * MM) < 0.15,
                "TS01_REFERENCE_PAGE_GEOMETRY_DRIFT")


def generate_svg(elements: list[dict[str, Any]]) -> str:
    rows = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 214 301" aria-label="P01 operator controls">']
    for e in elements:
        box = e["bbox_pdf_mm"]
        if box is None:
            continue
        x0, y0, x1, y1 = box
        rows.append(f'<g data-element-id="{html.escape(e["id"])}">')
        rows.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#2563eb" fill-opacity="0.08" stroke="#2563eb" stroke-width="0.8" stroke-dasharray="2,1.1"/>')
        rows.append(f'<rect x="{x0}" y="{max(0,y0-7)}" width="30" height="6.5" fill="#132f57"/>')
        rows.append(f'<text x="{x0+1.2}" y="{max(5.5,y0-1.9)}" font-size="4.25" fill="white" font-family="sans-serif">{e["id"]}</text></g>')
    rows.append('</svg>')
    return "\n".join(rows) + "\n"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def control_png(source: Image.Image, elements: list[dict[str, Any]]) -> Image.Image:
    image = source.copy().convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    sx, sy = image.width / 214, image.height / 301
    f = font(16)
    for e in elements:
        box = e.get("bbox_pdf_mm")
        if box is None:
            continue
        x0, y0, x1, y1 = box
        x0, y0, x1, y1 = (round(x0*sx), round(y0*sy), round(x1*sx), round(y1*sy))
        draw.rectangle((x0,y0,x1,y1), fill=(31,98,200,28), outline=(11,61,143,250), width=3)
        label = e["id"] + "  " + e["role"]
        draw.rectangle((x0, max(0, y0-26), min(image.width-1, x0+310), max(24,y0)), fill=(14,46,87,232))
        draw.text((x0+7, max(1,y0-24)), label, fill=(255,255,255,255), font=f)
    return image


def build_html(reg: dict[str, Any], svg: str) -> str:
    elements = reg["elements"]
    cards = []
    for e in elements:
        bbox = e.get("bbox_pdf_mm")
        if bbox:
            x0,y0,x1,y1 = bbox
            geometry = f'X {x0:g} · Y {y0:g} · W {x1-x0:g} · H {y1-y0:g} мм'
        else:
            geometry = 'Геометрія: ще не виміряна з джерела'
        cards.append(f'''<button type="button" class="item" data-select="{e['id']}">
          <strong>{e['id']} — {html.escape(e['display_name_ua'])}</strong>
          <small>{geometry}</small><small>Шар: {html.escape(e['layer'])} · Крок: {e['step']}</small>
          <small>Статус: {html.escape(e['geometry_status'])}</small>
          </button>''')
    markup = "\n".join(cards)
    # The image is a private, local file; the dashboard has no network dependencies.
    return '''<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ForPrint TS01 · P01 STANDARD</title>
<style>
:root{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#15243a;background:#f3f5f9}*{box-sizing:border-box}body{margin:0;padding:20px}header{max-width:1450px;margin:auto auto 18px}h1{margin:.25rem 0}p{line-height:1.45}main{max-width:1450px;margin:auto;display:grid;grid-template-columns:minmax(340px,540px) minmax(300px,1fr);gap:24px}section{background:white;border:1px solid #d9e1ec;border-radius:14px;padding:16px}.figure{position:relative;width:min(100%,510px);margin:auto;aspect-ratio:214/301;border:1px solid #cbd4e2}.figure>img,.figure>svg{position:absolute;inset:0;width:100%;height:100%}.figure>svg{pointer-events:none}.figure>svg g{pointer-events:all;cursor:pointer}.figure svg g.active rect:first-child{stroke:#e85d27;stroke-width:1.4;fill:#ffb780;fill-opacity:.17}.tools{margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap}button{cursor:pointer;border-radius:8px;border:1px solid #c5d2e2;background:white;padding:10px}.item{display:block;text-align:left;width:100%;margin:7px 0}.item.active{border-color:#e85d27;background:#fff4ea}.item strong,.item small{display:block}.item small{color:#475569;padding-top:3px}.notice{background:#fff8eb;border-left:4px solid #d88c27;padding:10px;margin:12px 0}.muted{color:#52627a;font-size:.9rem}@media(max-width:820px){main{grid-template-columns:1fr}body{padding:10px}}
</style></head><body><header><h1>ForPrint Template Studio · TS01 / P01 STANDARD</h1>
<p>Еталонна обкладинка + візуальний паспорт елементів. Натисни на ID елемента, щоб побачити його межі.</p>
<div class="notice"><b>REFERENCE / NON-PRODUCTION</b>: це візуальна контрольна карта з PDF Builder, а не готовий редагований Illustrator-шаблон. Зміни параметрів потребують окремого погодження.</div></header>
<main><section><div class="tools"><button id="toggle" type="button">Показати / приховати контрольні межі</button><button id="clear" type="button">Скинути вибір</button></div>
<div class="figure"><img src="design_view_p01.png" alt="Чистий вигляд P01 з канонічного PDF"><div id="overlay"><!--SVGHERE--></div></div>
<p class="muted">PDF coordinate origin: верхній лівий кут · media 214 × 301 мм · trim 210 × 297 мм</p></section>
<section><h2>Елементи й послідовність</h2><!--CARDSHERE--><p class="muted">Поки source-pinned координати є лише для P01-020 та P01-030. Фон і рамка залишаються на етапі інвентаризації.</p>
<h3>Як дати правку</h3><p>Назви ID та зміну: наприклад, «P01-020, ширина 75 мм, підняти на 5 мм». Це пропозиція для наступної версії, не автоматичне редагування канонічного шаблону.</p>
</section></main><script>
const controls=[...document.querySelectorAll('[data-select]')];const groups=[...document.querySelectorAll('svg g[data-element-id]')];
function choose(id){controls.forEach(x=>x.classList.toggle('active',x.dataset.select===id));groups.forEach(x=>x.classList.toggle('active',x.dataset.elementId===id));}
controls.forEach(x=>x.addEventListener('click',()=>choose(x.dataset.select)));groups.forEach(x=>x.addEventListener('click',()=>choose(x.dataset.elementId)));
document.getElementById('toggle').addEventListener('click',()=>{let el=document.getElementById('overlay');el.hidden=!el.hidden;});document.getElementById('clear').addEventListener('click',()=>choose(''));
</script></body></html>'''.replace('<!--SVGHERE-->',svg.replace('<svg ', '<svg style="position:absolute;inset:0;width:100%;height:100%" ',1)).replace('<!--CARDSHERE-->',markup)


def output_check(name: str) -> Path:
    require(NAME_RE.fullmatch(name) is not None, "TS01_OUTPUT_NAME_INVALID")
    require(TMP.is_dir() and not TMP.is_symlink(), "TS01_TMP_MISSING_OR_UNSAFE")
    out = TMP / name
    require(not out.exists() and not out.is_symlink(), "TS01_OUTPUT_EXISTS_NO_OVERWRITE")
    return out


def prepare(ref: Path, reg: dict[str, Any], elements: list[dict[str, Any]], out: Path) -> None:
    # Source checks have finished. These are new-only temporary files, never customer published.
    out.mkdir(mode=0o700)
    with fitz.open(ref) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    image.save(out / "design_view_p01.png")
    control_png(image, elements).save(out / "control_view_p01.png")
    svg = generate_svg(elements)
    (out / "control_overlay_p01.svg").write_text(svg, encoding="utf8")
    (out / "operator_view_p01.html").write_text(build_html(reg, svg), encoding="utf8")
    proposal = {"schema_version":"gdl_ts01_operator_proposal_v0_1","authority":"PROPOSAL_ONLY_NOT_APPROVED",
                "source_template":"greeting_card.p01.standard","changes":[],
                "example_not_executed":{"element_id":"P01-020","requested_change":{"width_mm":75,"move_y_mm":-5}}}
    (out / "operator_change_proposal.json").write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    manifest = {"schema_version":"gdl_ts01_p01_visual_passport_result_v0_1", "state":"VISUAL_REFERENCE_REVIEW_REQUIRED",
                "template_id":reg["template_id"], "element_count":len(elements),
                "source_reference_pdf_sha256":file_sha(ref), "design_approved":False,"production_ready":False,
                "illustrator_native_template_created":False, "source_private":True,
                "geometry_status":{e["id"]:e["geometry_status"] for e in elements}}
    manifest["artifacts_sha256"] = {p.name:file_sha(p) for p in sorted(out.iterdir()) if p.is_file()}
    (out / "result.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True,choices=("check","prepare"))
    p.add_argument("--resource-manifest",required=True,type=Path)
    p.add_argument("--source-root",type=Path)
    p.add_argument("--output-name")
    p.add_argument("--confirm-private-prepare", action="store_true")
    a = p.parse_args(argv)
    try:
        require((a.mode == "prepare") == bool(a.confirm_private_prepare), "TS01_CONFIRMATION_REQUIRED")
        require((a.mode == "prepare") == bool(a.output_name), "TS01_OUTPUT_NAME_MODE_MISMATCH")
        gc23, reg = load_json(CATALOG), load_json(REGISTRY)
        require(gc23.get("schema_version") == "forprint_gdl_gc23_variant_contract_v0_1", "TS01_GC23_SCHEMA_CHANGED")
        elements = validated_registry(reg, gc23)
        ref = resolve_source(a.resource_manifest, a.source_root, gc23)
        inspect_pdf(ref)
        if a.mode == "prepare":
            out = output_check(a.output_name)
            prepare(ref,reg,elements,out)
            print("TS01_PRIVATE_RESULT=tmp/"+a.output_name)
            print("GDL_TS01_P01=PREPARED_REFERENCE_VISUAL_REVIEW_REQUIRED")
        else:
            print("GDL_TS01_P01=SOURCE_CHECK_PASS_READ_ONLY")
        print("TS01_ELEMENT_COUNT="+str(len(elements)))
        print("TS01_GC23_PINNED_GEOMETRIES=2")
        print("TS01_SOURCE_ONLY_NO_CUSTOMER_WRITE=true")
        print("TS01_ILLUSTRATOR_MASTER_READY=false")
        return 0
    except (GateError, OSError, ValueError, KeyError, fitz.FileDataError, yaml.YAMLError) as exc:
        code = str(exc) if isinstance(exc, GateError) else type(exc).__name__
        print("GDL_TS01_P01=BLOCKED reason="+code,file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
