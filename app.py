"""
app.py — OGPe AI Plan Review API.

Endpoints
  GET  /api/code-sets                 -> pre-loaded code sets (for the selector)
  POST /api/review                    -> upload PDF + options, returns review result
  GET  /api/reviews                   -> saved review history
  GET  /api/reviews/{id}/load         -> load a saved review without re-running AI
  GET  /api/reviews/{id}/manifest     -> page manifest (Preview-style sidebar + markers)
  POST /api/reviews/{id}/rerender     -> rebuild annotated viewer assets from saved findings
  GET  /files/{id}/...                -> annotated.pdf, page-NN.png, page-NN.thumb.png

Run:
  pip install -r requirements.txt
  uvicorn app:app --reload
  # live AI: export ANTHROPIC_API_KEY=...   (otherwise the mock path is used)
"""
from __future__ import annotations
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

import review_engine
from annotate import annotate_pdf

HERE = os.path.dirname(__file__)

if os.environ.get("VERCEL"):
    REVIEWS = "/tmp/reviews"
else:
    REVIEWS = os.path.join(HERE, "reviews")

SAMPLE = os.path.join(HERE, "sample", "modelo-d.pdf")
STATIC = os.path.join(HERE, "static")
os.makedirs(REVIEWS, exist_ok=True)

REVIEW_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def _review_dir(review_id: str) -> str:
    if not REVIEW_ID_RE.fullmatch(review_id):
        raise ValueError("invalid review id")
    return os.path.join(REVIEWS, review_id)


def _review_json_path(review_id: str) -> str:
    return os.path.join(_review_dir(review_id), "review.json")


def _load_review(review_id: str) -> dict | None:
    p = _review_json_path(review_id)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


def _save_review(review_id: str, payload: dict) -> None:
    with open(_review_json_path(review_id), "w") as fh:
        json.dump(payload, fh, indent=2)


app = FastAPI(title="OGPe AI Plan Review")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/files", StaticFiles(directory=REVIEWS), name="files")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def home():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/code-sets")
def code_sets():
    return review_engine.list_code_sets()


@app.post("/api/review")
async def review(
    project_name: str = Form("Modelo D"),
    municipality: str = Form("San Juan"),
    permit_type: str = Form("Residential"),
    code_set: str = Form("unified_pr"),
    project_type: str = Form("Residential"),
    language: str = Form("English"),
    mock: bool = Form(False),
    file: UploadFile | None = File(None),
):
    rid = uuid.uuid4().hex[:12]
    rdir = os.path.join(REVIEWS, rid)
    os.makedirs(rdir, exist_ok=True)

    src = os.path.join(rdir, "source.pdf")
    if file is not None:
        with open(src, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
    else:
        shutil.copyfile(SAMPLE, src)  # demo: fall back to the sample set

    result = review_engine.run_review(src, code_set, language, mock=mock)
    manifest = annotate_pdf(src, result["findings"], rdir)

    payload = {
        "review_id": rid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file_name": (
            os.path.basename(file.filename)
            if file is not None and file.filename
            else os.path.basename(SAMPLE)
        ),
        "project": {
            "name": project_name,
            "municipality": municipality,
            "permit_type": permit_type,
            "project_type": project_type,
        },
        "result": {k: v for k, v in result.items() if k != "findings"},
        "findings": result["findings"],
        "manifest": manifest,
        "files_base": f"/files/{rid}",
    }
    _save_review(rid, payload)
    return JSONResponse(payload)


@app.get("/api/reviews/{rid}/manifest")
def manifest(rid: str):
    try:
        p = os.path.join(_review_dir(rid), "manifest.json")
    except ValueError:
        return JSONResponse({"error": "invalid review id"}, 400)
    if not os.path.exists(p):
        return JSONResponse({"error": "not found"}, 404)
    with open(p) as fh:
        return JSONResponse(json.load(fh))


@app.post("/api/reviews/{review_id}/generate-report")
def generate_report(review_id: str, lang: str = "en"):
    try:
        review_data = _load_review(review_id)
        rdir = _review_dir(review_id)
    except ValueError:
        return JSONResponse({"error": "invalid review id"}, 400)
    if review_data is None:
        return JSONResponse({"error": "review not found"}, 404)

    if lang == "es":
        output_filename = f"OGPe_Notificacion_Correcciones_{review_id}.pdf"
    else:
        output_filename = f"OGPe_Correction_Notice_{review_id}.pdf"
    output_path = os.path.join(rdir, output_filename)

    from report_generator import generate_correction_notice_pdf
    generate_correction_notice_pdf(review_data, output_path, lang)
    report_url = f"/files/{review_id}/{output_filename}"

    return JSONResponse({
        "report_url": report_url,
        "file_name": output_filename,
    })


@app.post("/api/reviews/{review_id}/generate-annotated-pdf")
def generate_annotated_pdf(review_id: str, lang: str = "en"):
    p = os.path.join(REVIEWS, review_id, "review.json")
    if not os.path.exists(p):
        return JSONResponse({"error": "review not found"}, 404)
    
    with open(p) as fh:
        review_data = json.load(fh)
        
    src = os.path.join(REVIEWS, review_id, "source.pdf")
    
    if lang == "es":
        from report_generator import translate_finding
        translated_findings = [translate_finding(f, "es") for f in review_data.get("findings", [])]
        output_filename = f"planos_anotados_{review_id}.pdf"
    else:
        translated_findings = review_data.get("findings", [])
        output_filename = f"annotated_plans_{review_id}.pdf"
        
    out_dir = os.path.join(REVIEWS, review_id)
    annotate_pdf(src, translated_findings, out_dir, render_images=False, filename=output_filename)
    
    report_url = f"/files/{review_id}/{output_filename}"
    return JSONResponse({
        "report_url": report_url,
        "file_name": output_filename
    })


@app.get("/api/reviews")
def list_reviews():
    reviews = []
    for d in os.listdir(REVIEWS):
        if not REVIEW_ID_RE.fullmatch(d):
            continue
        try:
            rdir = _review_dir(d)
            p = os.path.join(rdir, "review.json")
            if not os.path.exists(p):
                continue
            mtime = os.path.getmtime(p)
            with open(p) as f:
                data = json.load(f)
            report_name = f"OGPe_Correction_Notice_{d}.pdf"
            reviews.append({
                "id": d,
                "created_at": data.get("created_at"),
                "source_file_name": data.get("source_file_name", ""),
                "project": data.get("project", {}),
                "result": data.get("result", {}),
                "findings_count": len(data.get("findings", [])),
                "mtime": mtime,
                "files_base": data.get("files_base", f"/files/{d}"),
                "has_source_pdf": os.path.exists(os.path.join(rdir, "source.pdf")),
                "has_manifest": os.path.exists(os.path.join(rdir, "manifest.json")),
                "has_annotated_pdf": os.path.exists(os.path.join(rdir, "annotated.pdf")),
                "report_url": (
                    f"/files/{d}/{report_name}"
                    if os.path.exists(os.path.join(rdir, report_name))
                    else None
                ),
            })
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            continue
    reviews.sort(key=lambda x: x["mtime"], reverse=True)
    return JSONResponse(reviews)


@app.get("/api/reviews/{review_id}/load")
def load_review(review_id: str):
    try:
        review_data = _load_review(review_id)
    except ValueError:
        return JSONResponse({"error": "invalid review id"}, 400)
    if review_data is not None:
        return JSONResponse(review_data)
    return JSONResponse({"error": "not found"}, 404)


@app.post("/api/reviews/{review_id}/rerender")
def rerender_review(review_id: str):
    """Rebuild annotated viewer files from stored source.pdf + findings without calling the LLM."""
    try:
        review_data = _load_review(review_id)
        rdir = _review_dir(review_id)
    except ValueError:
        return JSONResponse({"error": "invalid review id"}, 400)
    if review_data is None:
        return JSONResponse({"error": "review not found"}, 404)

    src = os.path.join(rdir, "source.pdf")
    if not os.path.exists(src):
        return JSONResponse({"error": "source PDF not found for this review"}, 404)

    manifest = annotate_pdf(src, review_data.get("findings", []), rdir)
    review_data["manifest"] = manifest
    review_data["rerendered_at"] = datetime.now(timezone.utc).isoformat()
    _save_review(review_id, review_data)
    return JSONResponse(review_data)
