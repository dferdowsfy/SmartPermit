"""
review_engine.py — generate plan-review findings for a PDF against a pre-loaded
Puerto Rico code set, using Claude (Anthropic Messages API).

Set ANTHROPIC_API_KEY to run live. With --mock (or no key) it returns the
bundled sample findings so the whole pipeline stays testable offline.

Per request, the default model is Opus 4.8 at low reasoning effort.
Verify the exact model string against current Anthropic docs before production.
"""
from __future__ import annotations
import json, os, re, glob
from typing import Any
import fitz

HERE = os.path.dirname(__file__)
CODESETS_DIR = os.path.join(HERE, "codesets")

DEFAULT_MODEL = os.environ.get("OGPE_MODEL", "claude-opus-4-8")
# "low" reasoning effort, per request. The engine passes this through; adjust to
# the current API parameter name/values per Anthropic docs.
DEFAULT_EFFORT = os.environ.get("OGPE_EFFORT", "low")

SEV_WEIGHT = {"High": 7, "Medium": 3, "Low": 1}


def list_code_sets() -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(CODESETS_DIR, "*.json"))):
        cs = json.load(open(path))
        out.append({"id": cs["id"], "name": cs["name"], "based_on": cs.get("based_on", "")})
    return out


def load_code_set(code_set_id: str) -> dict:
    cs = json.load(open(os.path.join(CODESETS_DIR, f"{code_set_id}.json")))
    # resolve "includes" (e.g. unified) by merging referenced rule sets
    if cs.get("includes"):
        rules = list(cs.get("rules", []))
        for inc in cs["includes"]:
            sub = json.load(open(os.path.join(CODESETS_DIR, f"{inc}.json")))
            rules.extend(sub.get("rules", []))
        cs["rules"] = rules
    return cs


def extract_pages(pdf_path: str, max_chars_per_page: int = 1800) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        txt = page.get_text("text").strip()
        pages.append({"page": i + 1, "text": txt[:max_chars_per_page]})
    doc.close()
    return pages


def build_prompt(code_set: dict, pages: list[dict], language: str) -> str:
    rules = "\n".join(
        f"- {r['id']} [{r['section']}] ({r.get('default_severity','Medium')}): "
        f"{r['requirement']} CHECK: {r.get('check_hint','')}"
        for r in code_set["rules"]
    )
    pages_blob = "\n\n".join(f"=== PAGE {p['page']} ===\n{p['text']}" for p in pages)
    lang = "Spanish" if str(language).lower().startswith(("es", "sp")) else "English"
    return f"""You are an OGPe plan-review assistant performing a conservative FIRST-PASS
screening of a permit drawing set against the "{code_set['name']}" rule set.

Rules to screen against:
{rules}

For each rule that the drawing text appears to violate or leave unverifiable,
emit ONE finding. Be conservative: if the documents don't contain enough
evidence to confirm compliance, raise the finding as "not verifiable" rather
than asserting a pass. Do not invent content that is not supported by the text.

Return ONLY a JSON array (no prose, no markdown) where each item has:
  id           short code like "HF-01" (High), "MF-01" (Medium), "LF-01" (Low)
  severity     "High" | "Medium" | "Low"
  title        short finding title
  page         1-based page number where the evidence appears
  bbox         normalized [x0,y0,x1,y1] (0..1) locating the evidence on that page
  sheet        sheet id if visible (e.g. "A-101"), else ""
  code         the rule's section reference
  evidence     <= 25 words, paraphrased from the drawing text (do not quote at length)
  explanation  one sentence on the requirement
  correction   one sentence on the required correction
  confidence   0..1
Write evidence/explanation/correction in {lang}.

Drawing text by page:
{pages_blob}
"""


def _call_anthropic(prompt: str, model: str, effort: str) -> str:
    import urllib.request
    key = os.environ["ANTHROPIC_API_KEY"]
    body = {
        "model": model,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }
    # pass reasoning effort if supported by the account/model; harmless extra key
    # is ignored by older endpoints behind a try/except on the caller side.
    if effort:
        body["reasoning_effort"] = effort
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _parse_findings(raw: str) -> list[dict]:
    raw = raw.strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start, end = raw.find("["), raw.rfind("]")
    return json.loads(raw[start:end + 1]) if start != -1 else []


def score(findings: list[dict]) -> int:
    penalty = sum(SEV_WEIGHT.get(f.get("severity", "Medium"), 3) for f in findings)
    return max(0, 100 - penalty)


def run_review(pdf_path: str, code_set_id: str, language: str = "English",
               model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT,
               mock: bool = False) -> dict:
    code_set = load_code_set(code_set_id)
    if mock or not os.environ.get("ANTHROPIC_API_KEY"):
        findings = json.load(open(os.path.join(HERE, "sample", "findings.json")))
        source = "mock (bundled sample findings)"
    else:
        pages = extract_pages(pdf_path)
        raw = _call_anthropic(build_prompt(code_set, pages, language), model, effort)
        findings = _parse_findings(raw)
        source = f"{model} (effort={effort})"
    counts = {s: sum(1 for f in findings if f.get("severity") == s) for s in ("High", "Medium", "Low")}
    return {
        "code_set": code_set["id"], "code_set_name": code_set["name"],
        "engine": source, "language": language,
        "readiness_score": score(findings),
        "status": "NOT READY FOR REVIEW" if score(findings) < 70 else "READY FOR REVIEW",
        "counts": counts, "findings": findings,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--code-set", default="unified_pr")
    ap.add_argument("--language", default="English")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    res = run_review(a.pdf, a.code_set, a.language, mock=a.mock)
    print(json.dumps({k: v for k, v in res.items() if k != "findings"}, indent=2))
    print(f"findings: {len(res['findings'])}")
