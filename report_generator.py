import os
import json
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Custom Canvas for dynamic footers (Page X of Y or Page X)
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#475569'))
        
        # Horizontal separator line
        self.setStrokeColor(colors.HexColor('#cbd5e1'))
        self.setLineWidth(0.5)
        self.line(54, 45, 612 - 54, 45) # 54 is 0.75 margin
        
        # Footer text (single line, left-aligned)
        footer_text = f"First-pass technical screening - preliminary, not final agency action | Page {self._pageNumber}"
        self.drawString(54, 32, footer_text)
        self.restoreState()


def add_section_heading(story, text, style):
    story.append(Paragraph(text, style))
    # horizontal line under title
    hr = Table([['']], colWidths=[504], rowHeights=[1.5])
    hr.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1.0, colors.HexColor('#1e3a8a')), # Dark blue line matching section text
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(hr)
    story.append(Spacer(1, 8))


def generate_correction_notice_pdf(review_data: dict, output_path: str):
    # Setup document: letter size, 0.75-inch (54 points) margins
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=65
    )

    # Setup styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=1,
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'HeaderSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        spaceAfter=4
    )
    
    doc_title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.black,
        alignment=1,
        spaceAfter=8
    )
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=12
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#1e3a8a'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    cell_lbl_style = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#1e3a8a')
    )
    
    cell_val_style = ParagraphStyle(
        'CellValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#0f172a')
    )
    
    list_item_style = ParagraphStyle(
        'ListItem',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=3,
        spaceAfter=3
    )
    
    body_text_style = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
    )

    story = []

    # 1. Header
    story.append(Paragraph("OFFICE OF PERMIT MANAGEMENT (OGPe)", title_style))
    story.append(Paragraph("Commonwealth of Puerto Rico", subtitle_style))
    story.append(Paragraph("PLAN REVIEW CORRECTION NOTICE", doc_title_style))
    
    # Thin horizontal blue line
    blue_line = Table([['']], colWidths=[504], rowHeights=[1.5])
    blue_line.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1e3a8a')),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(blue_line)
    story.append(Spacer(1, 10))

    # 2. Disclaimer Paragraph
    disclaimer_text = (
        "This notice itemizes deficiencies identified during a first-pass technical screening of the submitted "
        "construction documents against the applicable Puerto Rico Building Code, Puerto Rico Residential Code, "
        "ASCE 7-16, and applicable Puerto Rico amendments. Each item must be addressed and the corrected, "
        "signed-and-sealed set re-submitted for review. This screening is preliminary and does not constitute "
        "final agency action."
    )
    story.append(Paragraph(disclaimer_text, disclaimer_style))

    # Parse new database fields if present
    project_summary = review_data.get("project_summary", {})
    if not isinstance(project_summary, dict):
        project_summary = {}

    review_metadata = review_data.get("review_metadata", {})
    if not isinstance(review_metadata, dict):
        review_metadata = {}

    project_info = review_data.get("project", {})
    result_info = review_data.get("result", {})

    readiness_score = review_data.get("readiness_score")
    if readiness_score is None:
        readiness_score = result_info.get("readiness_score", 0)

    status = review_data.get("status")
    if status is None:
        status = result_info.get("status", "NOT READY FOR REVIEW")

    # Helper to resolve project summary table fields
    def get_summary_field(key, fallback_val):
        val = project_summary.get(key)
        if val is not None:
            return str(val)
        val = review_metadata.get(key)
        if val is not None:
            return str(val)
        return str(fallback_val)

    # 3. Project Summary Table
    summary_data = [
        [Paragraph("Project", cell_lbl_style), Paragraph(get_summary_field("Project", project_info.get("name", "Modelo D - Residencia")), cell_val_style)],
        [Paragraph("Submission Type", cell_lbl_style), Paragraph(get_summary_field("Submission Type", "First-pass plan review (drawings + structural calculation package)"), cell_val_style)],
        [Paragraph("Occupancy / Use", cell_lbl_style), Paragraph(get_summary_field("Occupancy / Use", project_info.get("project_type", "Residential") + " (IBC R-3 / IRC) — unit count to be confirmed"), cell_val_style)],
        [Paragraph("Stories / Construction", cell_lbl_style), Paragraph(get_summary_field("Stories / Construction", "2 stories; 1st: special reinforced masonry, 2nd: wood structural-panel shear walls"), cell_val_style)],
        [Paragraph("Footprint", cell_lbl_style), Paragraph(get_summary_field("Footprint", "Primary ≈ 20' × 24'; 2nd-floor main module ≈ 480 SF"), cell_val_style)],
        [Paragraph("Design Basis", cell_lbl_style), Paragraph(get_summary_field("Design Basis", f"{result_info.get('code_set_name', 'Unified Puerto Rico Code')} (PRBC/PRRC 2018, ASCE 7-16)"), cell_val_style)],
        [Paragraph("Reviewer", cell_lbl_style), Paragraph(get_summary_field("Reviewer", "OGPe — First-Pass Technical Screening System"), cell_val_style)],
        [Paragraph("Date of Review", cell_lbl_style), Paragraph(get_summary_field("Date of Review", "June 9, 2026"), cell_val_style)],
        [Paragraph("Disposition", cell_lbl_style), Paragraph(get_summary_field("Disposition", f"{status} — Return to applicant"), cell_val_style)],
        [Paragraph("Readiness Score", cell_lbl_style), Paragraph(f"<b>{get_summary_field('Readiness Score', f'{readiness_score} / 100')}</b>", cell_val_style)],
    ]
    
    summary_table = Table(summary_data, colWidths=[130, 374])
    summary_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e0f2fe')), # light blue left col
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # 4. Findings Introduction
    intro_style = ParagraphStyle(
        'IntroText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=10
    )
    story.append(Paragraph("Findings are grouped by severity. Each finding lists the sheet/object, drawing evidence, code reference, explanation, and the correction required to clear the item.", intro_style))

    # Fetch findings and sort ordered by severity and finding ID
    findings = review_data.get("findings", [])
    
    def severity_rank(f):
        sev = f.get("severity") or f.get("sev") or "Medium"
        if sev == "High":
            return 1
        elif sev == "Medium":
            return 2
        return 3

    sorted_findings = sorted(findings, key=lambda x: (severity_rank(x), x.get("id", "")))

    high_findings = [f for f in sorted_findings if (f.get("severity") or f.get("sev")) == "High"]
    medium_findings = [f for f in sorted_findings if (f.get("severity") or f.get("sev")) == "Medium"]
    low_findings = [f for f in sorted_findings if (f.get("severity") or f.get("sev")) == "Low"]

    def build_finding_table(f, header_bg, sev_label):
        lbl_style = cell_lbl_style
        val_style = cell_val_style
        
        header_text = f"<b>{f.get('id', '?')} — {f.get('title', 'Compliance Discrepancy')}</b>"
        hdr_style = ParagraphStyle('Hdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0f172a'))
        
        table_rows = [
            [Paragraph(header_text, hdr_style), ""], # spanned
            [Paragraph("Severity", lbl_style), Paragraph(sev_label, val_style)],
            [Paragraph("Sheet / Object", lbl_style), Paragraph(f.get("sheet") or f.get("sheet_id") or "N/A", val_style)],
            [Paragraph("Drawing Evidence", lbl_style), Paragraph(f.get("evidence", "No evidence specified."), val_style)],
            [Paragraph("PR Code Reference", lbl_style), Paragraph(f.get("code", "N/A"), val_style)],
            [Paragraph("Explanation", lbl_style), Paragraph(f.get("explanation", "Violation of applicable code requirement."), val_style)],
            [Paragraph("Required Correction", lbl_style), Paragraph(f.get("correction", "Provide correction on plans."), val_style)],
        ]
        
        t = Table(table_rows, colWidths=[120, 384])
        t.setStyle(TableStyle([
            ('SPAN', (0,0), (1,0)), # span header row
            ('BACKGROUND', (0,0), (-1,0), header_bg), # header background color
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    # 5. High-Severity Findings
    if high_findings:
        add_section_heading(story, "High-Severity Findings (Permit-Blocking)", section_title_style)
        for f in high_findings:
            t_flow = build_finding_table(f, colors.HexColor('#fee2e2'), "High")
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 6. Medium-Severity Findings
    if medium_findings:
        add_section_heading(story, "Medium-Severity Findings", section_title_style)
        for f in medium_findings:
            t_flow = build_finding_table(f, colors.HexColor('#fef3c7'), "Medium")
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 7. Low-Severity Findings
    if low_findings:
        add_section_heading(story, "Low-Severity Findings", section_title_style)
        for f in low_findings:
            t_flow = build_finding_table(f, colors.HexColor('#d1fae5'), "Low")
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 8. Missing Information Required for Review
    add_section_heading(story, "Missing Information Required for Review", section_title_style)
    missing_info = review_data.get("missing_information")
    if not missing_info:
        missing_info = [
            "Signed and sealed structural calculation report showing seismic site criteria.",
            "Complete electrical riser diagram and panel service load calculations.",
            "FEMA elevation certificate if structural footprint lies inside coastal special hazard zone."
        ]
    
    for i, item in enumerate(missing_info, 1):
        p_text = f"<b>{i}.</b> {item}"
        story.append(Paragraph(p_text, list_item_style))
    story.append(Spacer(1, 6))

    # 9. Reviewer Questions to Applicant
    add_section_heading(story, "Reviewer Questions to Applicant", section_title_style)
    questions = review_data.get("reviewer_questions")
    if not questions:
        questions = [
            "Confirm the exact count of independent dwelling units on sheet A-101 (layout indicates secondary unit potential).",
            "Provide the soil profile class used for design wind pressure calculations on structural notes."
        ]
        
    for i, q in enumerate(questions, 1):
        p_text = f"<b>{i}.</b> {q}"
        story.append(Paragraph(p_text, list_item_style))
    story.append(Spacer(1, 10))

    # 10. Permit Readiness & Determination
    add_section_heading(story, "Permit Readiness & Determination", section_title_style)
    
    overall_recommendation = review_data.get("overall_recommendation")
    if not overall_recommendation:
        overall_recommendation = result_info.get("overall_recommendation")
        
    narrative = ""
    if isinstance(overall_recommendation, str):
        narrative = overall_recommendation
    elif isinstance(overall_recommendation, dict):
        narrative = overall_recommendation.get("narrative") or overall_recommendation.get("text") or ""
        
    if not narrative:
        narrative = "The permit package lacks fundamental site-specific design calculations and professional seals required under PRBC 2018 §107. Correction details must be implemented."

    score_text = f"Permit Readiness Score: <b>{readiness_score} / 100</b>.<br/><br/>" \
                 f"Overall Recommendation: <b>{status}</b>.<br/><br/>" \
                 f"{narrative}"
    
    score_p = Paragraph(score_text, body_text_style)
    score_box = Table([[score_p]], colWidths=[504])
    score_box.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(KeepTogether([score_box, Spacer(1, 12)]))

    # 11. Signature Block
    sig_text = (
        "Reviewed by: ________________________________ Date: ______________<br/><br/>"
        "Title: Plan Reviewer, OGPe<br/><br/>"
        "Applicant response with corrections is required prior to resubmission."
    )
    sig_p = Paragraph(sig_text, body_text_style)
    sig_box = Table([[sig_p]], colWidths=[504])
    sig_box.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(KeepTogether([sig_box]))

    # Build the document using SimpleDocTemplate and our NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
