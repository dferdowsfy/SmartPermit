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


def translate_finding(f, lang):
    if lang != "es":
        return f
    # Mappings based on standard code/sections or keywords
    code_matches = [
        { "key": "107.2", "title": "Plano arquitectónico incompleto", "evidence": "El índice de hojas incluye planos no sometidos.", "explanation": "Se requiere un conjunto arquitectónico completo para evaluar los medios de egreso, las separaciones y las disposiciones de seguridad humana.", "correction": "Someter el conjunto arquitectónico completo que coincida con el índice." },
        { "key": "107", "title": "Falta sello profesional", "evidence": "No hay sello/firma/fecha del CIAPR en ningún bloque de título.", "explanation": "Los documentos de construcción en Puerto Rico deben llevar el sello y la firma de un profesional licenciado por el Colegio de Ingenieros y Agrimensores de Puerto Rico (CIAPR).", "correction": "Aplicar sello, firma y fecha con licencia del CIAPR a cada plano." },
        { "key": "R310", "title": "Apertura de escape y rescate de emergencia (EERO) no verificable", "evidence": "Dormitorio requiere apertura de escape libre neta y antepecho adecuados.", "explanation": "Cada dormitorio requiere una apertura de escape y rescate de emergencia operable >= 5.7 pies cuadrados, con antepecho <= 44 pulgadas.", "correction": "Especificar apertura libre neta + altura de antepecho; proveer EERO operable que cumpla por dormitorio." },
        { "key": "R302.6", "title": "Separación garaje/vivienda incompleta", "evidence": "Habitación habitable sobre el garaje; no hay techo de placa de yeso Tipo X de 5/8\".", "explanation": "El espacio habitable sobre un garaje requiere una separación de techo de placa de yeso Tipo X de 5/8 de pulgada y penetraciones protegidas.", "correction": "Especificar techo de garaje de Tipo X de 5/8\" + penetraciones protegidas." },
        { "key": "R202", "title": "Cantidad de unidades de vivienda ambigua", "evidence": "Segunda cocina + nivel inferior separable; cantidad de unidades no declarada.", "explanation": "La cantidad de unidades determina la ruta de código aplicable (PRRC frente a PRBC) y los requisitos de separación.", "correction": "Declarar la cantidad de unidades; si son dos unidades, mostrar separación + egreso independiente." },
        { "key": "1609.2", "title": "Protección contra escombros arrastrados por el viento no mostrada", "evidence": "Gran acristalamiento fijo, sin contraventanas; San Juan está en la región de escombros.", "explanation": "Las aperturas acristaladas en la región de escombros arrastrados por el viento requieren vidrio resistente a impactos o protección de apertura probada.", "correction": "Añadir un programa de protección de aperturas con presiones de diseño por apertura." },
        { "key": "1613", "title": "Categoría de diseño sísmico no declarada", "evidence": "Las notas indican 'Zona Sísmica C'; no hay Ss/S1 del sitio ni SDC.", "explanation": "El sistema lateral y cualquier detalle de hormigón deben diseñarse de acuerdo con la SDC del sitio.", "correction": "Proveer Ss/S1, derivar SDC, mostrar sistema lateral + detalles del Capítulo 18 de ACI 318." },
        { "key": "1609", "title": "Velocidad de viento no basada en PR", "evidence": "Las notas indican 76/90 mph; PR es de ~145-170 mph última.", "explanation": "La velocidad de viento de diseño última debe cumplir con el mapa de viento de PR (típicamente 145-170 mph).", "correction": "Volver a declarar la velocidad de viento de diseño del mapa de PR / Herramienta de Peligros de ASCE 7." },
        { "key": "amend", "title": "Faltan conectores resistentes a la corrosión", "evidence": "Conectores 'STD GALVANIZED' para miembros expuestos.", "explanation": "Las enmiendas del código de edificación de Puerto Rico requieren herrajes resistentes a la corrosión para miembros expuestos.", "correction": "Actualizar los conectores/anclajes expuestos a la clase de corrosión requerida." },
        { "key": "corrosion", "title": "Faltan conectores resistentes a la corrosión", "evidence": "Conectores 'STD GALVANIZED' para miembros expuestos.", "explanation": "Las enmiendas del código de edificación de Puerto Rico requieren herrajes resistentes a la corrosión para miembros expuestos.", "correction": "Actualizar los conectores/anclajes expuestos a la clase de corrosión requerida." },
        { "key": "IECC", "title": "Cumplimiento energético no corresponde a Zona 1A", "evidence": "Arrastres de clima frío (carga de nieve en el terreno de 71 psf).", "explanation": "El modelado de cumplimiento energético debe ser para la Zona Climática 1A (cálido-húmedo) utilizando objetivos de SHGC.", "correction": "Reejecutar el análisis energético para la Zona 1A; eliminar elementos de nieve/clima frío." },
        { "key": "R312", "title": "Falta diseño de baranda de protección", "evidence": "Borde del balcón con caída >30\"; no se proporciona detalle.", "explanation": "Se requieren protecciones donde la caída supere las 30 pulgadas; la altura mínima es de 36 pulgadas.", "correction": "Añadir detalle de baranda: mínimo 36\", aberturas <4\" de esfera, cargas de 50 plf/200 lb." },
        { "key": "QA_lbl", "title": "Vistas ilustrativas sin etiquetar", "evidence": "Vistas de diagramas no etiquetadas como 'no aptas para construcción'.", "explanation": "Los planos estructurales esquemáticos deben distinguirse claramente de los detalles de construcción.", "correction": "Etiquetar vistas como esquemáticas frente a vistas para construcción." },
        { "key": "lbl", "title": "Vistas ilustrativas sin etiquetar", "evidence": "Vistas de diagramas no etiquetadas como 'no aptas para construcción'.", "explanation": "Los planos estructurales esquemáticos deben distinguirse claramente de los detalles de construcción.", "correction": "Etiquetar vistas como esquemáticas frente a vistas para construcción." },
        { "key": "R311.7", "title": "Ancho de escalera por debajo del mínimo", "evidence": "Nota de escalera 'ancho mín 34in'.", "explanation": "El ancho mínimo de la escalera según el Código Residencial Internacional es de 36 pulgadas.", "correction": "Corregir nota a un ancho libre mínimo de 36\"." },
        { "key": "QA_win", "title": "Falta columna de apertura libre neta", "evidence": "El programa carece de columna de apertura libre neta.", "explanation": "Se requiere una columna de apertura libre neta en los programas de ventanas para verificar el cumplimiento de los EEROs.", "correction": "Añadir una columna de apertura libre neta al programa de ventanas." },
        { "key": "win", "title": "Falta columna de apertura libre neta", "evidence": "El programa carece de columna de apertura libre neta.", "explanation": "Se requiere una columna de apertura libre neta en los programas de ventanas para verificar el cumplimiento de los EEROs.", "correction": "Añadir una columna de apertura libre neta al programa de ventanas." },
        { "key": "AppG", "title": "Determinación de zona de inundación ausente", "evidence": "Parcela costera; no se muestra zona FEMA ni BFE.", "explanation": "Las parcelas costeras requieren consideraciones de diseño de inundaciones para resistir olas y fuerzas hidrodinámicas.", "correction": "Añadir determinación de inundación; si es SFHA mostrar BFE + ASCE 24." },
        { "key": "flood", "title": "Determinación de zona de inundación ausente", "evidence": "Parcela costera; no se muestra zona FEMA ni BFE.", "explanation": "Las parcelas costeras requieren consideraciones de diseño de inundaciones para resistir olas y fuerzas hidrodinámicas.", "correction": "Añadir determinación de inundación; si es SFHA mostrar BFE + ASCE 24." },
        { "key": "QA", "title": "Discrepancia en el índice de planos", "evidence": "El índice incluye planos que no están presentan en el paquete.", "explanation": "El índice de planos debe coincidir exactamente con los planos presentados para evitar vacíos en la documentación.", "correction": "Conciliar el índice con los planos presentados." }
    ]

    code = str(f.get("code") or "").lower()
    title = str(f.get("title") or "").lower()
    fid = str(f.get("id") or "").lower()

    tr = None
    for m in code_matches:
        key = m["key"].lower()
        if key in code or key in title or key in fid:
            tr = m
            break

    if not tr:
        if "seal" in title or "signature" in title:
            tr = next((x for x in code_matches if x["key"] == "107"), None)
        elif "architectural" in title and ("incomplete" in title or "partial" in title):
            tr = next((x for x in code_matches if x["key"] == "107.2"), None)
        elif "eero" in title or "escape" in title or "sleeping" in title:
            tr = next((x for x in code_matches if x["key"] == "R310"), None)
        elif "garage" in title or "separation" in title:
            tr = next((x for x in code_matches if x["key"] == "R302.6"), None)
        elif "dwelling" in title or "unit count" in title:
            tr = next((x for x in code_matches if x["key"] == "R202"), None)
        elif "windborne" in title or "debris" in title:
            tr = next((x for x in code_matches if x["key"] == "1609.2"), None)
        elif "seismic" in title or "sdc" in title:
            tr = next((x for x in code_matches if x["key"] == "1613"), None)
        elif "wind speed" in title:
            tr = next((x for x in code_matches if x["key"] == "1609"), None)
        elif "corrosion" in title or "exposed" in title:
            tr = next((x for x in code_matches if x["key"] == "amend"), None)
        elif "energy" in title or "iecc" in title or "climate" in title:
            tr = next((x for x in code_matches if x["key"] == "IECC"), None)
        elif "guardrail" in title or "guard" in title:
            tr = next((x for x in code_matches if x["key"] == "R312"), None)
        elif "illustrative" in title or "rendering" in title or "construction" in title:
            tr = next((x for x in code_matches if x["key"] == "QA_lbl"), None)
        elif "stair" in title or "width" in title:
            tr = next((x for x in code_matches if x["key"] == "R311.7"), None)
        elif "window" in title or "schedule" in title:
            tr = next((x for x in code_matches if x["key"] == "QA_win"), None)
        elif "flood" in title:
            tr = next((x for x in code_matches if x["key"] == "AppG"), None)
        elif "index" in title or "drawing index" in title:
            tr = next((x for x in code_matches if x["key"] == "QA"), None)

    if not tr:
        mapping = {
          "HF-01": { "title": "Falta sello profesional", "evidence": "No hay sello/firma/fecha del CIAPR en ningún bloque de título.", "explanation": "Los documentos de construcción en Puerto Rico deben llevar el sello y la firma de un profesional licenciado por el Colegio de Ingenieros y Agrimensores de Puerto Rico (CIAPR).", "correction": "Aplicar sello, firma y fecha con licencia del CIAPR a cada plano." },
          "HF-02": { "title": "Plano arquitectónico incompleto", "evidence": "El índice de hojas incluye planos no sometidos.", "explanation": "Se requiere un conjunto arquitectónico completo para evaluar los medios de egreso, las separaciones y las disposiciones de seguridad humana.", "correction": "Someter el conjunto arquitectónico completo que coincida con el índice." },
          "LF-03": { "title": "Discrepancia en el índice de planos", "evidence": "El índice incluye planos que no están presentes en el paquete.", "explanation": "El índice de planos debe coincidir exactamente con los planos presentados para evitar vacíos en la documentación.", "correction": "Conciliar el índice con los planos presentados." },
          "HF-07": { "title": "EERO no verificable", "evidence": "Dormitorio 2 = Vidrio Fijo 36x72; no se tabuló apertura libre neta.", "explanation": "Cada habitación requiere una apertura de escape y rescate de emergencia operable >= 5.7 pies cuadrados, con antepecho <= 44 pulgadas.", "correction": "Añadir columnas de apertura libre neta + altura de antepecho; proveer EERO operable que cumpla por dormitorio." },
          "MF-05": { "title": "Separación garaje/vivienda incompleta", "evidence": "Habitación habitable sobre el garaje; no hay techo de placa de yeso Tipo X de 5/8\".", "explanation": "El espacio habitable sobre un garaje requiere una separación de techo de placa de yeso Tipo X de 5/8 de pulgada y penetraciones protegidas.", "correction": "Especificar techo de garaje de Tipo X de 5/8\" + penetraciones protegidas." },
          "HF-06": { "title": "Cantidad de unidades de vivienda ambigua", "evidence": "Segunda cocina + nivel inferior separable; cantidad de unidades no declarada.", "explanation": "La cantidad de unidades determina la ruta de código aplicable (PRRC frente a PRBC) y los requisitos de separación.", "correction": "Declarar la cantidad de unidades; si son dos unidades, mostrar separación + egreso independiente." },
          "HF-08": { "title": "Protección contra escombros arrastrados por el viento no mostrada", "evidence": "Gran acristalamiento fijo, sin contraventanas; San Juan está en la región de escombros.", "explanation": "Las aperturas acristaladas en la región de escombros arrastrados por el viento requieren vidrio resistente a impactos o protección de apertura probada.", "correction": "Añadir un programa de protección de aperturas con presiones de diseño por apertura." },
          "HF-09": { "title": "Categoría de diseño sísmico no declarada", "evidence": "Las notas indican 'Zona Sísmica C'; no hay Ss/S1 del sitio ni SDC.", "explanation": "El sistema lateral y cualquier detalle de hormigón deben diseñarse de acuerdo con la SDC del sitio.", "correction": "Proveer Ss/S1, derivar SDC, mostrar sistema lateral + detalles del Capítulo 18 de ACI 318." },
          "MF-01": { "title": "Velocidad de viento no basada en PR", "evidence": "Las notas indican 76/90 mph; PR es de ~145-170 mph última.", "explanation": "La velocidad de viento de diseño última debe cumplir con el mapa de viento de PR (típicamente 145-170 mph).", "correction": "Volver a declarar la velocidad de viento de diseño del mapa de PR / Herramienta de Peligros de ASCE 7." },
          "MF-03": { "title": "Faltan conectores resistentes a la corrosión", "evidence": "Conectores 'STD GALVANIZED' para miembros expuestos.", "explanation": "Las enmiendas del código de edificación de Puerto Rico requieren herrajes resistentes a la corrosión para miembros expuestos.", "correction": "Actualizar los conectores/anclajes expuestos a la clase de corrosión requerida." },
          "MF-06": { "title": "Cumplimiento energético no corresponde a Zona 1A", "evidence": "Arrastres de clima frío (carga de nieve en el terreno de 71 psf).", "explanation": "El modelado de cumplimiento energético debe ser para la Zona Climática 1A (cálido-húmedo) utilizando objetivos de SHGC.", "correction": "Reejecutar el análisis energético para la Zona 1A; eliminar elementos de nieve/clima frío." },
          "HF-05": { "title": "Falta diseño de baranda de protección", "evidence": "Borde del balcón con caída >30\"; no se proporciona detalle.", "explanation": "Se requieren protecciones donde la caída supere las 30 pulgadas; la altura mínima es de 36 pulgadas.", "correction": "Añadir detalle de baranda: mínimo 36\", aberturas <4\" de esfera, cargas de 50 plf/200 lb." },
          "LF-04": { "title": "Vistas ilustrativas sin etiquetar", "evidence": "Vistas de diagramas no etiquetadas como 'no aptas para construcción'.", "explanation": "Los planos estructurales esquemáticos deben distinguirse claramente de los detalles de construcción.", "correction": "Etiquetar vistas como esquemáticas frente a vistas para construcción." },
          "MF-04": { "title": "Ancho de escalera por debajo del mínimo", "evidence": "Nota de escalera 'ancho mín 34in'.", "explanation": "El ancho mínimo de la escalera según el Código Residencial Internacional es de 36 pulgadas.", "correction": "Corregir nota a un ancho libre mínimo de 36\"." },
          "LF-01": { "title": "Brecha de numeración en el programa de ventanas", "evidence": "Las etiquetas omiten W1-19.", "explanation": "Las brechas de numeración en las etiquetas del programa de ventanas pueden indicar componentes faltantes de los planos estructurales.", "correction": "Confirmar que no se haya omitido ninguna ventana; renumerar o anotar la brecha." },
          "LF-02": { "title": "Falta columna de apertura libre neta", "evidence": "El programa carece de columna de apertura libre neta.", "explanation": "Se requiere una columna de apertura libre neta en los programas de ventanas para verificar el cumplimiento de los EEROs.", "correction": "Añadir una columna de apertura libre neta al programa de ventanas." },
          "MF-02": { "title": "Determinación de zona de inundación ausente", "evidence": "Parcela costera; no se muestra zona FEMA ni BFE.", "explanation": "Las parcelas costeras requieren consideraciones de diseño de inundaciones para resistir olas y fuerzas hidrodinámicas.", "correction": "Añadir determinación de inundación; si es SFHA mostrar BFE + ASCE 24." }
        }
        tr = mapping.get(f.get("id", ""))

    if not tr:
        return f
    
    translated = dict(f)
    translated["title"] = tr.get("title") or f.get("title")
    translated["evidence"] = tr.get("evidence") or f.get("evidence")
    translated["explanation"] = tr.get("explanation") or f.get("explanation")
    translated["correction"] = tr.get("correction") or f.get("correction")
    return translated


def generate_correction_notice_pdf(review_data: dict, output_path: str, lang: str = "en"):
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
    if lang == "es":
        story.append(Paragraph("OFICINA DE GERENCIA DE PERMISOS (OGPe)", title_style))
        story.append(Paragraph("Estado Libre Asociado de Puerto Rico", subtitle_style))
        story.append(Paragraph("NOTIFICACIÓN DE CORRECCIONES DE REVISIÓN DE PLANOS", doc_title_style))
    else:
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
    if lang == "es":
        disclaimer_text = (
            "Esta notificación detalla las deficiencias identificadas durante una revisión técnica preliminar de los "
            "documentos de construcción presentados con relación al Código de Construcción de Puerto Rico, el Código "
            "Residencial de Puerto Rico, ASCE 7-16 y las enmiendas aplicables de Puerto Rico. Cada elemento debe ser "
            "corregido y el conjunto de planos corregido, firmado y sellado debe ser re-sometido para revisión. Esta "
            "revisión es preliminar y no constituye una acción final de la agencia."
        )
    else:
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

    # Values translations
    lbl_project = "Proyecto" if lang == "es" else "Project"
    lbl_sub_type = "Tipo de Sométido" if lang == "es" else "Submission Type"
    val_sub_type = "Revisión preliminar de planos (planos + paquete de cálculos estructurales)" if lang == "es" else "First-pass plan review (drawings + structural calculation package)"
    lbl_occ_use = "Ocupación / Uso" if lang == "es" else "Occupancy / Use"
    val_occ_use = (project_info.get("project_type", "Residential") + " (IBC R-3 / IRC) — cantidad de unidades a ser confirmada") if lang == "es" else (project_info.get("project_type", "Residential") + " (IBC R-3 / IRC) — unit count to be confirmed")
    if lang == "es":
        val_occ_use = val_occ_use.replace("Residential", "Residencial").replace("Commercial", "Comercial").replace("Mixed Use", "Uso Mixto")
    
    lbl_stories = "Pisos / Construcción" if lang == "es" else "Stories / Construction"
    val_stories = "2 pisos; 1ro: mampostería reforzada especial, 2do: muros de corte de paneles estructurales de madera" if lang == "es" else "2 stories; 1st: special reinforced masonry, 2nd: wood structural-panel shear walls"
    
    lbl_footprint = "Área de Huella" if lang == "es" else "Footprint"
    val_footprint = "Principal ≈ 20' × 24'; módulo principal del 2do piso ≈ 480 pies cuadrados" if lang == "es" else "Primary ≈ 20' × 24'; 2nd-floor main module ≈ 480 SF"
    
    lbl_design_basis = "Base de Diseño" if lang == "es" else "Design Basis"
    lbl_reviewer = "Revisor" if lang == "es" else "Reviewer"
    val_reviewer = "OGPe — Sistema de Revisión Técnica Preliminar" if lang == "es" else "OGPe — First-Pass Technical Screening System"
    
    lbl_date = "Fecha de Revisión" if lang == "es" else "Date of Review"
    val_date = "9 de junio de 2026" if lang == "es" else "June 9, 2026"
    
    lbl_disposition = "Disposición" if lang == "es" else "Disposition"
    status_es = "LISTO PARA REVISIÓN" if readiness_score >= 70 else "NO LISTO PARA REVISIÓN"
    status_str = status_es if lang == "es" else status
    val_disposition = f"{status_str} — Devolver al solicitante" if lang == "es" else f"{status} — Return to applicant"
    
    lbl_readiness = "Puntuación de Preparación" if lang == "es" else "Readiness Score"

    # 3. Project Summary Table
    summary_data = [
        [Paragraph(lbl_project, cell_lbl_style), Paragraph(get_summary_field("Project", project_info.get("name", "Modelo D - Residencia")), cell_val_style)],
        [Paragraph(lbl_sub_type, cell_lbl_style), Paragraph(get_summary_field("Submission Type", val_sub_type), cell_val_style)],
        [Paragraph(lbl_occ_use, cell_lbl_style), Paragraph(get_summary_field("Occupancy / Use", val_occ_use), cell_val_style)],
        [Paragraph(lbl_stories, cell_lbl_style), Paragraph(get_summary_field("Stories / Construction", val_stories), cell_val_style)],
        [Paragraph(lbl_footprint, cell_lbl_style), Paragraph(get_summary_field("Footprint", val_footprint), cell_val_style)],
        [Paragraph(lbl_design_basis, cell_lbl_style), Paragraph(get_summary_field("Design Basis", f"{result_info.get('code_set_name', 'Unified Puerto Rico Code')} (PRBC/PRRC 2018, ASCE 7-16)"), cell_val_style)],
        [Paragraph(lbl_reviewer, cell_lbl_style), Paragraph(get_summary_field("Reviewer", val_reviewer), cell_val_style)],
        [Paragraph(lbl_date, cell_lbl_style), Paragraph(get_summary_field("Date of Review", val_date), cell_val_style)],
        [Paragraph(lbl_disposition, cell_lbl_style), Paragraph(get_summary_field("Disposition", val_disposition), cell_val_style)],
        [Paragraph(lbl_readiness, cell_lbl_style), Paragraph(f"<b>{get_summary_field('Readiness Score', f'{readiness_score} / 100')}</b>", cell_val_style)],
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
    if lang == "es":
        intro_text = "Los hallazgos se agrupan por severidad. Cada hallazgo detalla el plano/objeto, la evidencia del dibujo, la referencia del código, la explicación y la corrección requerida para resolver el elemento."
    else:
        intro_text = "Findings are grouped by severity. Each finding lists the sheet/object, drawing evidence, code reference, explanation, and the correction required to clear the item."
    story.append(Paragraph(intro_text, intro_style))

    # Fetch findings, translate them, and sort ordered by severity and finding ID
    raw_findings = review_data.get("findings", [])
    findings = [translate_finding(f, lang) for f in raw_findings]
    
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
        
        lbl_severity = "Severidad" if lang == "es" else "Severity"
        lbl_sheet = "Plano / Objeto" if lang == "es" else "Sheet / Object"
        lbl_evidence = "Evidencia del Plano" if lang == "es" else "Drawing Evidence"
        lbl_ref = "Referencia del Código de PR" if lang == "es" else "PR Code Reference"
        lbl_expl = "Explicación" if lang == "es" else "Explanation"
        lbl_corr = "Corrección Requerida" if lang == "es" else "Required Correction"

        title_discrepancy = "Discrepancia de Cumplimiento" if lang == "es" else "Compliance Discrepancy"
        header_text = f"<b>{f.get('id', '?')} — {f.get('title', title_discrepancy)}</b>"
        hdr_style = ParagraphStyle('Hdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#0f172a'))
        
        table_rows = [
            [Paragraph(header_text, hdr_style), ""], # span header row
            [Paragraph(lbl_severity, lbl_style), Paragraph(sev_label, val_style)],
            [Paragraph(lbl_sheet, lbl_style), Paragraph(f.get("sheet") or f.get("sheet_id") or "N/A", val_style)],
            [Paragraph(lbl_evidence, lbl_style), Paragraph(f.get("evidence", "No evidence specified." if lang != "es" else "No se especificó evidencia."), val_style)],
            [Paragraph(lbl_ref, lbl_style), Paragraph(f.get("code", "N/A"), val_style)],
            [Paragraph(lbl_expl, lbl_style), Paragraph(f.get("explanation", "Violation of applicable code requirement." if lang != "es" else "Violación del requisito de código aplicable."), val_style)],
            [Paragraph(lbl_corr, lbl_style), Paragraph(f.get("correction", "Provide correction on plans." if lang != "es" else "Proveer la corrección en los planos."), val_style)],
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
        title_high = "Hallazgos de Severidad Alta (Bloquean Permiso)" if lang == "es" else "High-Severity Findings (Permit-Blocking)"
        label_high = "Alto" if lang == "es" else "High"
        add_section_heading(story, title_high, section_title_style)
        for f in high_findings:
            t_flow = build_finding_table(f, colors.HexColor('#fee2e2'), label_high)
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 6. Medium-Severity Findings
    if medium_findings:
        title_med = "Hallazgos de Severidad Media" if lang == "es" else "Medium-Severity Findings"
        label_med = "Medio" if lang == "es" else "Medium"
        add_section_heading(story, title_med, section_title_style)
        for f in medium_findings:
            t_flow = build_finding_table(f, colors.HexColor('#fef3c7'), label_med)
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 7. Low-Severity Findings
    if low_findings:
        title_low = "Hallazgos de Severidad Baja" if lang == "es" else "Low-Severity Findings"
        label_low = "Bajo" if lang == "es" else "Low"
        add_section_heading(story, title_low, section_title_style)
        for f in low_findings:
            t_flow = build_finding_table(f, colors.HexColor('#d1fae5'), label_low)
            story.append(KeepTogether([t_flow, Spacer(1, 8)]))

    # 8. Missing Information Required for Review
    title_missing = "Información Faltante Requerida para Revisión" if lang == "es" else "Missing Information Required for Review"
    add_section_heading(story, title_missing, section_title_style)
    missing_info = review_data.get("missing_information")
    if not missing_info:
        if lang == "es":
            missing_info = [
                "Informe de cálculo estructural firmado y sellado que muestre los criterios sísmicos del sitio.",
                "Diagrama vertical eléctrico completo y cálculos de carga de servicio del panel.",
                "Certificado de elevación de FEMA si la huella estructural se encuentra dentro de una zona costera de riesgo especial."
            ]
        else:
            missing_info = [
                "Signed and sealed structural calculation report showing seismic site criteria.",
                "Complete electrical riser diagram and panel service load calculations.",
                "FEMA elevation certificate if structural footprint lies inside coastal special hazard zone."
            ]
    else:
        translated_missing = []
        for item in missing_info:
            if "Signed and sealed structural" in item:
                translated_missing.append("Informe de cálculo estructural firmado y sellado que muestre los criterios sísmicos del sitio.")
            elif "Complete electrical riser" in item:
                translated_missing.append("Diagrama vertical eléctrico completo y cálculos de carga de servicio del panel.")
            elif "FEMA elevation certificate" in item:
                translated_missing.append("Certificado de elevación de FEMA si la huella estructural se encuentra dentro de una zona costera de riesgo especial.")
            else:
                translated_missing.append(item)
        if lang == "es":
            missing_info = translated_missing
    
    for i, item in enumerate(missing_info, 1):
        p_text = f"<b>{i}.</b> {item}"
        story.append(Paragraph(p_text, list_item_style))
    story.append(Spacer(1, 6))

    # 9. Reviewer Questions to Applicant
    title_questions = "Preguntas del Revisor al Solicitante" if lang == "es" else "Reviewer Questions to Applicant"
    add_section_heading(story, title_questions, section_title_style)
    questions = review_data.get("reviewer_questions")
    if not questions:
        if lang == "es":
            questions = [
                "Confirmar la cantidad exacta de unidades de vivienda independientes en el plano A-101 (la distribución indica potencial de unidad secundaria).",
                "Proveer la clase de perfil de suelo utilizada para los cálculos de presión de viento de diseño en las notas estructurales."
            ]
        else:
            questions = [
                "Confirm the exact count of independent dwelling units on sheet A-101 (layout indicates secondary unit potential).",
                "Provide the soil profile class used for design wind pressure calculations on structural notes."
            ]
    else:
        translated_q = []
        for q in questions:
            if "Confirm the exact count" in q:
                translated_q.append("Confirmar la cantidad exacta de unidades de vivienda independientes en el plano A-101 (la distribución indica potencial de unidad secundaria).")
            elif "Provide the soil profile" in q:
                translated_q.append("Proveer la clase de perfil de suelo utilizada para los cálculos de presión de viento de diseño en las notas estructurales.")
            else:
                translated_q.append(q)
        if lang == "es":
            questions = translated_q
        
    for i, q in enumerate(questions, 1):
        p_text = f"<b>{i}.</b> {q}"
        story.append(Paragraph(p_text, list_item_style))
    story.append(Spacer(1, 10))

    # 10. Permit Readiness & Determination
    title_readiness = "Determinación y Preparación del Permiso" if lang == "es" else "Permit Readiness & Determination"
    add_section_heading(story, title_readiness, section_title_style)
    
    overall_recommendation = review_data.get("overall_recommendation")
    if not overall_recommendation:
        overall_recommendation = result_info.get("overall_recommendation")
        
    narrative = ""
    if isinstance(overall_recommendation, str):
        narrative = overall_recommendation
    elif isinstance(overall_recommendation, dict):
        narrative = overall_recommendation.get("narrative") or overall_recommendation.get("text") or ""
        
    if not narrative:
        if lang == "es":
            narrative = "El paquete de permisos carece de cálculos de diseño específicos del sitio y sellos profesionales requeridos bajo el PRBC 2018 §107. Se deben implementar los detalles de corrección."
        else:
            narrative = "The permit package lacks fundamental site-specific design calculations and professional seals required under PRBC 2018 §107. Correction details must be implemented."
    else:
        if lang == "es":
            if "The permit package lacks" in narrative:
                narrative = "El paquete de permisos carece de cálculos de diseño específicos del sitio y sellos profesionales requeridos bajo el PRBC 2018 §107. Se deben implementar los detalles de corrección."
            elif "readiness" in narrative.lower():
                narrative = narrative.replace("High number of high severity issues.", "Gran cantidad de problemas de severidad alta.")

    if lang == "es":
        score_text = f"Puntuación de Preparación de Permiso: <b>{readiness_score} / 100</b>.<br/><br/>" \
                     f"Recomendación General: <b>{status_str}</b>.<br/><br/>" \
                     f"{narrative}"
    else:
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
    if lang == "es":
        sig_text = (
            "Revisado por: ________________________________ Fecha: ______________<br/><br/>"
            "Título: Revisor de Planos, OGPe<br/><br/>"
            "Se requiere la respuesta del solicitante con las correcciones antes de volver a someter."
        )
    else:
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
