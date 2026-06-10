"""
annotate.py — burn AI-review findings onto a PDF using PyMuPDF (fitz).

Input  : a source PDF + a list of findings (the LLM output).
Output : an annotated PDF (for download), per-page PNG thumbnails (with marks
         baked in for the sidebar overview), clean full-resolution PNGs (no
         burned-in annotations, overlays are handled by the HTML viewer), and
         a manifest.json the frontend uses to draw pin overlays.

Each finding may carry:
    id, severity ("High"|"Medium"|"Low"), title, page (1-based),
    bbox (normalized [x0,y0,x1,y1] in 0..1), code, evidence, correction.
Findings without a page (package-level) are attached to page 1 as notes.
"""

from __future__ import annotations
import json, os, re
from typing import Any
import fitz  # PyMuPDF

SEV_COLOR = {
    "High":   (0.86, 0.15, 0.15),   # red-600
    "Medium": (0.85, 0.55, 0.05),   # amber-600
    "Low":    (0.42, 0.45, 0.50),   # gray-500
}


def _rect_from_bbox(page: fitz.Page, f: dict) -> fitz.Rect:
    w, h = page.rect.width, page.rect.height

    # Priority 1 & 2: exact text / OCR match using search_for
    search_targets = []

    # Check search_text field
    st = f.get("search_text")
    if st:
        search_targets.append(st)

    # Extract quoted text from evidence
    ev = f.get("evidence", "")
    if ev:
        single_quotes = re.findall(r"'(.*?)'", ev)
        double_quotes = re.findall(r'"(.*?)"', ev)
        search_targets.extend(single_quotes)
        search_targets.extend(double_quotes)
        # Also try the raw evidence text if short enough
        clean_ev = ev.strip('"\'')
        if 3 < len(clean_ev) < 60:
            search_targets.append(clean_ev)

    for target in search_targets:
        target = target.strip()
        if not target or len(target) < 3:
            continue
        rects = page.search_for(target)
        if rects:
            return rects[0]

    # Priority 3: Fallback to model-generated coordinates
    bbox = f.get("bbox")
    if not bbox:
        return fitz.Rect(0.06 * w, 0.10 * h, 0.30 * w, 0.20 * h)
    x0, y0, x1, y1 = bbox
    return fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h)


def annotate_pdf(src_pdf: str, findings: list[dict[str, Any]], out_dir: str,
                 thumb_zoom: float = 0.32, page_zoom: float = 1.4,
                 render_images: bool = True, filename: str = "annotated.pdf") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(src_pdf)
    n_pages = doc.page_count

    # Group findings by page (1-based); package-level → page 1
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

        # ─── Step 1: Render CLEAN full-res PNG BEFORE adding any annotations ───
        # This is what the HTML viewer displays — crisp, uncluttered drawings.
        if render_images:
            full = page.get_pixmap(matrix=fitz.Matrix(page_zoom, page_zoom))
            full_name = f"page-{pno+1:02d}.png"
            full.save(os.path.join(out_dir, full_name))
        else:
            full_name = f"page-{pno+1:02d}.png"

        # ─── Step 2: Add PDF annotations (for download PDF + thumbnail preview) ─
        for f in page_findings:
            sev = f.get("severity", "Medium")
            color = SEV_COLOR.get(sev, SEV_COLOR["Medium"])
            fid = f.get("id", "?")
            rect = _rect_from_bbox(page, f)

            # Thin bordered rectangle showing the finding region
            try:
                rann = page.add_rect_annot(rect)
                rann.set_colors(stroke=color)
                rann.set_border(width=1.5)
                rann.set_opacity(0.9)
                rann.update()
            except Exception:
                pass

            # Small colored label bubble above the rect with the finding ID
            try:
                lbl = f" {fid} "
                lab_w = max(30, 5.6 * len(lbl) + 6)
                lab = fitz.Rect(rect.x0, max(2, rect.y0 - 13),
                                rect.x0 + lab_w, max(13, rect.y0 - 1))
                page.draw_rect(lab, color=color, fill=color, width=0)
                page.insert_textbox(lab, lbl, fontsize=7.5, color=(1, 1, 1),
                                    fontname="hebo", align=1)
            except Exception:
                pass

            # Sticky note popup with full finding detail
            try:
                note = (
                    f"[{fid}] {sev} — {f.get('title', '')}\n"
                    f"Code: {f.get('code', '')}\n\n"
                    f"Evidence: {f.get('evidence', '')}\n\n"
                    f"Required correction: {f.get('correction', '')}"
                )
                ta = page.add_text_annot(
                    fitz.Point(min(rect.x1 + 4, w - 20), rect.y0),
                    note, icon="Note"
                )
                ta.set_colors(stroke=color)
                ta.update()
            except Exception:
                pass

            markers.append({
                "id": fid, "severity": sev, "title": f.get("title", ""),
                "code": f.get("code", ""), "evidence": f.get("evidence", ""),
                "correction": f.get("correction", ""),
                "x": round(rect.x0, 2),
                "y": round(rect.y0, 2),
                "bbox": [round(rect.x0 / w, 4), round(rect.y0 / h, 4),
                         round(rect.x1 / w, 4), round(rect.y1 / h, 4)],
            })

        # ─── Step 3: Render annotated THUMBNAIL (marks baked in for sidebar) ────
        if render_images:
            thumb = page.get_pixmap(matrix=fitz.Matrix(thumb_zoom, thumb_zoom))
            thumb_name = f"page-{pno+1:02d}.thumb.png"
            thumb.save(os.path.join(out_dir, thumb_name))
        else:
            thumb_name = f"page-{pno+1:02d}.thumb.png"

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

    # Save the fully annotated PDF for download
    annotated_path = os.path.join(out_dir, filename)
    try:
        doc.bake(annots=True)
    except Exception as e:
        print(f"Error baking/flattening annotations: {e}")
    doc.save(annotated_path, deflate=True)
    doc.close()

    manifest = {
        "source": os.path.basename(src_pdf),
        "annotated_pdf": filename,
        "page_count": n_pages,
        "pages": manifest_pages,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return manifest


def _sheet_label(page: fitz.Page) -> str:
    """Pull a sheet id like 'A-101' from the page text if present."""
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
