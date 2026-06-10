# OGPe AI Plan Review — testable build

A first-pass permit-screening pipeline: a PDF drawing set is checked against a
**pre-loaded Puerto Rico code set** by an LLM (Grok 4.20 via OpenRouter), and the findings are **burned onto
the PDF with PyMuPDF** and shown in an Apple-Preview-style viewer.

```
backend/
  app.py             FastAPI: /api/code-sets, /api/review, /files/*
  review_engine.py   builds the prompt from a code set + PDF text, calls the LLM,
                     parses findings (or returns bundled sample findings offline)
  annotate.py        PyMuPDF: rectangles + ID label bubbles + sticky-note popups,
                     renders per-page PNGs/thumbnails + manifest.json
  make_sample.py     generates a sample "Modelo D" set + findings.json
  codesets/          pre-loaded rule sets: prrc_2018, prbc_2018, unified_pr
  sample/            modelo-d.pdf, findings.json
  review_output/     example run output (annotated.pdf, page PNGs, manifest.json)
ogpe-viewer-v2.jsx   front-end: code-set picker + Preview-style annotation viewer
```

## Run it

```bash
pip install -r requirements.txt

# 1) regenerate the sample set (optional; already included)
python make_sample.py

# 2) prove the annotation pipeline (no API key needed)
python annotate.py sample/modelo-d.pdf sample/findings.json review_output
#    -> review_output/annotated.pdf  + page-NN.png + manifest.json

# 3) run a full review (offline mock unless a key is set)
python review_engine.py sample/modelo-d.pdf --code-set unified_pr --mock

# 4) serve the API and browser viewer
uvicorn app:app --reload
#    UI   http://localhost:8000/
#    GET  http://localhost:8000/api/code-sets
#    POST http://localhost:8000/api/review   (multipart: file, code_set, language, ...)
```

## Saved review history / token-free viewer testing

Every submitted review is persisted under `reviews/{review_id}/` with the
source PDF (`source.pdf`), API payload (`review.json`), PyMuPDF-generated
viewer manifest, page images, thumbnails, and `annotated.pdf`. The web UI now
includes a **History** screen that lists those submissions and can reopen either
the dashboard or the interactive annotation viewer without calling the LLM.

Useful endpoints:

- `GET /api/reviews` lists saved submissions and artifact availability.
- `GET /api/reviews/{id}/load` loads a saved review payload for the dashboard or
  viewer without re-running AI.
- `POST /api/reviews/{id}/rerender` rebuilds `annotated.pdf`, page PNGs,
  thumbnails, and `manifest.json` from the stored `source.pdf` plus cached
  findings only, so viewer work can be tested without consuming tokens.
- `POST /api/reviews/{id}/generate-report` creates/downloads the correction
  notice PDF from cached findings.

## Live AI

```bash
export OPENROUTER_API_KEY=sk-or-...
export OGPE_MODEL=x-ai/grok-4.20      # Grok 4.20 via OpenRouter
export OGPE_EFFORT=low                # low reasoning effort
```

Without a key, `run_review` returns the bundled sample findings so the front end,
annotation, and viewer can be exercised end-to-end. Confirm the exact model
string against OpenRouter docs;
`review_engine._call_openrouter` is the single place that talks to the API.

## How the pieces connect

- **Pre-loaded code sets.** `codesets/*.json` hold paraphrased rule summaries
  (section + requirement + check hint). `unified_pr` merges PRRC + PRBC via
  `includes`. The front-end selector and `/api/code-sets` read these.
- **Review.** `build_prompt()` injects the selected rules + extracted page text
  and asks the LLM for a strict JSON findings array, including a 1-based `page`
  and a normalized `bbox` so each finding can be placed on the drawing.
- **Annotation (PyMuPDF).** `annotate.py` converts each `bbox` to page
  coordinates and adds a location rectangle, a colored ID-label bubble, and a
  sticky-note popup carrying the full evidence/correction. It then rasterizes
  each page (marks baked in) for the thumbnail rail and focal view, and writes
  `manifest.json` (which pages are annotated + marker coords).
- **Readiness score.** Deterministic: `100 − (High×7 + Medium×3 + Low×1)`,
  clamped at 0. Tune the weights in `review_engine.SEV_WEIGHT`.

## Notes / honesty

- The code sets are **authored rule summaries with section references**, not the
  licensed IRC/PRBC text (ICC copyright). License the official code for
  production and treat these as advisory screening rules.
- The viewer's pages are stand-ins in the `.jsx` preview; in the deployed app the
  thumbnails/focal images are the PyMuPDF-rendered PNGs from `/files/{id}/`.
- This is a **first-pass screening aid**, not a substitute for a licensed
  reviewer's determination.
```
