"""
app.py — OGPe AI Plan Review API.

Endpoints
  GET  /api/code-sets                 -> pre-loaded code sets (for the selector)
  POST /api/review                    -> upload PDF + options, returns review result
  GET  /api/reviews/{id}/manifest     -> page manifest (Preview-style sidebar + markers)
  GET  /files/{id}/...                -> annotated.pdf, page-NN.png, page-NN.thumb.png

Run:
  pip install -r requirements.txt
  uvicorn app:app --reload
  # live AI: export ANTHROPIC_API_KEY=...   (otherwise the mock path is used)
"""
from __future__ import annotations
import os, uuid, shutil, json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse

import review_engine
from annotate import annotate_pdf

HERE = os.path.dirname(__file__)
REVIEWS = os.path.join(HERE, "reviews")
SAMPLE = os.path.join(HERE, "sample", "modelo-d.pdf")
STATIC = os.path.join(HERE, "static")
os.makedirs(REVIEWS, exist_ok=True)

app = FastAPI(title="OGPe AI Plan Review")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/files", StaticFiles(directory=REVIEWS), name="files")


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
        "project": {"name": project_name, "municipality": municipality,
                    "permit_type": permit_type, "project_type": project_type},
        "result": {k: v for k, v in result.items() if k != "findings"},
        "findings": result["findings"],
        "manifest": manifest,
        "files_base": f"/files/{rid}",
    }
    with open(os.path.join(rdir, "review.json"), "w") as fh:
        json.dump(payload, fh, indent=2)
    return JSONResponse(payload)


@app.get("/api/reviews/{rid}/manifest")
def manifest(rid: str):
    p = os.path.join(REVIEWS, rid, "manifest.json")
    return JSONResponse(json.load(open(p))) if os.path.exists(p) else JSONResponse({"error": "not found"}, 404)
