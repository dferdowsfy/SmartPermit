"""
annotate.py — burn AI-review findings onto a PDF using PyMuPDF (fitz).

Input  : a source PDF + a list of findings (the LLM output).
Output : an annotated PDF, per-page PNG thumbnails (with the marks baked in),
         a full-resolution PNG of each page, and a manifest.json the frontend
         uses to draw the Apple-Preview-style sidebar marks and overlay markers.

Each finding may carry:
    id, severity ("High"|"Medium"|"Low"), title, page (1-based),
    bbox (normalized [x0,y0,x1,y1] in 0..1), code, evidence, correction.
Findings without a page (package-level) are attached to page 1 as notes.
"""

from __future__ import annotations
import json, os
from typing import Any
import fitz  # PyMuPDF

SEV_COLOR = {
    "High":   (0.86, 0.15, 0.15),   # red-600
    "Medium": (0.85, 0.55, 0.05),   # amber-600
    "Low":    (0.42, 0.45, 0.50),   # gray-500
}


def _rect_from_bbox(page: fitz.Page, bbox: list[float] | None) -> fitz.Rect:
    w, h = page.rect.width, page.rect.height
    if not bbox:
        # default: small box in the upper-left if no location was returned
        return fitz.Rect(0.06 * w, 0.10 * h, 0.30 * w, 0.20 * h)
    x0, y0, x1, y1 = bbox
    return fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h)


def annotate_pdf(src_pdf: str, findings: list[dict[str, Any]], out_dir: str,
                 thumb_zoom: float = 0.32, page_zoom: float = 1.4) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(src_pdf)
    n_pages = doc.page_count

    # group findings by page (1-based); package-level -> page 1
    by_page: dict[int, list[dict]] = {}
    for f in findings:
        p = f.get("page") or 1
        p = max(1, min(p, n_pages))
        by_page.setdefault(p, []).append(f)

    manifest_pages = []

    for pno in range(n_pages):
        page = doc[pno]
        w, h = page.rect.width, page.rect.height
        page_findings = by_page.get(pno + 1, [])
        markers = []

        for f in page_findings:
            sev = f.get("severity", "Medium")
            color = SEV_COLOR.get(sev, SEV_COLOR["Medium"])
            fid = f.get("id", "?")
            rect = _rect_from_bbox(page, f.get("bbox"))

            # 1) location rectangle
            try:
                rann = page.add_rect_annot(rect)
                rann.set_colors(stroke=color)
                rann.set_border(width=1.5)
                rann.set_opacity(0.9)
                rann.update()
            except Exception:
                pass

            # 2) visible label bubble (finding id) drawn above the rect so it
            #    renders reliably in both the PDF and the raster thumbnails
            try:
                lbl = f" {fid} "
                lab_w = max(30, 5.6 * len(lbl) + 6)
                lab = fitz.Rect(rect.x0, max(2, rect.y0 - 13), rect.x0 + lab_w, max(13, rect.y0 - 1))
                page.draw_rect(lab, color=color, fill=color, width=0)
                page.insert_textbox(lab, lbl, fontsize=7.5, color=(1, 1, 1),
                                    fontname="hebo", align=1)
            except Exception:
                pass

            # 3) sticky note (popup) with the full finding detail
            try:
                note = (
                    f"[{fid}] {sev} — {f.get('title','')}\n"
                    f"Code: {f.get('code','')}\n\n"
                    f"Evidence: {f.get('evidence','')}\n\n"
                    f"Required correction: {f.get('correction','')}"
                )
                ta = page.add_text_annot(fitz.Point(min(rect.x1 + 4, w - 20), rect.y0), note, icon="Note")
                ta.set_colors(stroke=color)
                ta.update()
            except Exception:
                pass

            markers.append({
                "id": fid, "severity": sev, "title": f.get("title", ""),
                "code": f.get("code", ""), "evidence": f.get("evidence", ""),
                "correction": f.get("correction", ""),
                "bbox": f.get("bbox") or [round(rect.x0 / w, 4), round(rect.y0 / h, 4),
                                          round(rect.x1 / w, 4), round(rect.y1 / h, 4)],
            })

        # render thumbnail + full page (after annotating, so marks are baked in)
        thumb = page.get_pixmap(matrix=fitz.Matrix(thumb_zoom, thumb_zoom))
        full = page.get_pixmap(matrix=fitz.Matrix(page_zoom, page_zoom))
        thumb_name = f"page-{pno+1:02d}.thumb.png"
        full_name = f"page-{pno+1:02d}.png"
        thumb.save(os.path.join(out_dir, thumb_name))
        full.save(os.path.join(out_dir, full_name))

        manifest_pages.append({
            "page": pno + 1,
            "label": _sheet_label(page),
            "thumb": thumb_name,
            "image": full_name,
            "width": w, "height": h,
            "annotated": len(markers) > 0,
            "annotation_count": len(markers),
            "markers": markers,
        })

    annotated_path = os.path.join(out_dir, "annotated.pdf")
    doc.save(annotated_path, deflate=True)
    doc.close()

    manifest = {"source": os.path.basename(src_pdf), "annotated_pdf": "annotated.pdf",
                "page_count": n_pages, "pages": manifest_pages}
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def _sheet_label(page: fitz.Page) -> str:
    """Pull a sheet id like 'A-101' from the page text if present."""
    import re
    txt = page.get_text("text")
    m = re.search(r"\b([A-Z]{1,2}-\d{3})\b", txt)
    return m.group(1) if m else f"Page {page.number + 1}"


if __name__ == "__main__":
    import sys
    src = sys.argv[1]
    findings = json.load(open(sys.argv[2]))
    out = sys.argv[3] if len(sys.argv) > 3 else "review_output"
    man = annotate_pdf(src, findings, out)
    n = sum(1 for p in man["pages"] if p["annotated"])
    print(f"Annotated {sum(p['annotation_count'] for p in man['pages'])} findings "
          f"across {n}/{man['page_count']} pages -> {out}/annotated.pdf")
