"""Build a private PDF from saved measurements and color rules in memory."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def analysis_pdf(analysis, comparisons):
    data = BytesIO()
    ink, wine, blush = [colors.HexColor(value) for value in ("#321d24", "#741d37", "#f0e1df")]
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("GivynTitle", fontName="Times-Roman", fontSize=33, leading=36,
                              textColor=ink, spaceAfter=7))
    styles.add(ParagraphStyle("GivynSection", fontName="Times-Roman", fontSize=21, leading=25,
                              textColor=wine, spaceBefore=15, spaceAfter=6, keepWithNext=True))
    styles.add(ParagraphStyle("GivynBody", fontName="Helvetica", fontSize=9.5, leading=14,
                              textColor=ink, spaceAfter=7))
    styles.add(ParagraphStyle("GivynTable", fontName="Helvetica", fontSize=8.8, leading=12,
                              textColor=ink))
    styles.add(ParagraphStyle("GivynGroup", fontName="Times-Roman", fontSize=18, leading=21,
                              textColor=wine, spaceBefore=11, spaceAfter=5, keepWithNext=True))
    doc = SimpleDocTemplate(data, pagesize=A4, title="GIVYN Personal Color Analysis",
                            author="GIVYN", topMargin=52, bottomMargin=52, leftMargin=48, rightMargin=48)
    story = []

    def paragraph(text, style="GivynBody"):
        return Paragraph(escape(str(text)).replace("ΔE00", "Delta E00").replace("−", "-"), styles[style])

    def add(text, style="GivynBody"):
        story.append(paragraph(text, style))

    skin, undertone, contrast, season = (analysis[key] for key in ("skin", "undertone", "contrast", "season"))
    add("GIVYN")
    add(f"{'Explore' if season.get('tentative') else 'Your'} {season['name']} color profile", "GivynTitle")
    add(f"Analysis {analysis['id']}  |  {analysis['created_at'][:10]}  |  Knowledge base {analysis['knowledge_version']}")
    add(season["description"])
    add("Measurements and estimates", "GivynSection")
    lab, hsv = skin["lab"], skin["hsv"]
    add(f"Photo skin sample {skin['hex']} | RGB {skin['rgb']} | HSV {hsv['h']} degrees, "
        f"{hsv['s']}%, {hsv['v']}% | CIE Lab {lab['l']}, {lab['a']}, {lab['b']}.")
    add(f"Skin depth: {skin['depth']}, approximately Monk {skin['monk_index']}.")
    for warning in analysis.get("capture_warnings", []):
        add(warning["message"])
    add(f"Undertone: {undertone['category']} ({undertone['confidence'].lower()} confidence). {undertone['reason']}")
    add(f"Facial contrast: {contrast['level']}. {contrast['reason']}")
    add("Seasonal inference", "GivynSection")
    add(f"{season['confidence']} confidence. {season['reason']}")
    if season["alternative"]:
        add(f"Alternative: {season['alternative']}.")
    add(season.get("score_label", "Weighted matches") + ": " + ", ".join(f"{row['name']} {row['score']}/100" for row in season["ranked"]) + ".")
    add("Rule evidence: " + (" ".join(season["rules"]) or "The weighted feature match determined this result."))
    if season.get("method") == "trained_model":
        evidence = season["evaluation"]
        add(f"Experimental model {season['version']} uses regional CIE Lab measurements, with parameters learned from labeled "
            f"research data. Skin-and-hair means are used when hair is available; skin-only results have weak evidence. "
            f"Model support is not personal accuracy. Undertone and contrast descriptions remain separate heuristic estimates.")
        add(f"Training rows: {evidence['training_rows']}. Held-out feature accuracy: {100 * evidence['test']['accuracy']:.1f}% "
            f"on {evidence['test']['rows']} rows from {evidence['test_identities']} supplied identities. {evidence['scope']}")
        add(f"Feature source: {evidence['source']}. Research use only.")
        add(f"Measurement sensitivity agreement: {season['stability']['agreement']}%. {season['stability']['description']}")
    else:
        add("The heuristic fit uses undertone tendency (43%), contrast (28%), photo saturation (21%), lightness (4%) "
            "and brightness (4%). Missing contrast is omitted and the other weights are normalized.")
    for caution in season.get("cautions", []):
        add(caution)
    for label, feature in analysis.get("features", {}).items():
        add(f"{label.capitalize()}: {feature['hex']}, source {feature.get('source', 'provided')}." if feature else f"{label.capitalize()}: unavailable.")
    for label in analysis["limitations"]:
        add(label)

    add("Personal palette", "GivynSection")
    for group, swatches in analysis["palette"].items():
        add(group, "GivynGroup")
        rows = [["", "Color", "Why it fits"]]
        for swatch in swatches:
            rows.append(["", paragraph(f"{swatch['name']}\n{swatch['hex']}", "GivynTable"),
                         paragraph(swatch["explanation"], "GivynTable")])
        table = Table(rows, colWidths=[21, 123, doc.width - 144], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), blush), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (1, 0), (-1, -1), .35, blush),
            *[("BACKGROUND", (0, index), (0, index), colors.HexColor(item["hex"]))
              for index, item in enumerate(swatches, 1)],
        ]))
        story.extend([table, Spacer(1, 8)])
    story.append(PageBreak())
    add("Recent color comparisons", "GivynTitle")
    add("Color fit combines CIEDE2000 proximity to a favorable swatch (76%), temperature fit (14%), "
        "and saturation fit (10%). Metal fit compares the estimated undertone and seasonal tendency.")
    if not comparisons:
        add("Run a compatibility check in the Color Studio to include comparison results in your report.")
    for comparison in comparisons[:12]:
        for item in comparison["result"]["colors"]:
            add(f"{item.get('name', item['hex'])} {item['hex']} · {item['score']}/100. {item['explanation']}")

    def footer(canvas, document):
        canvas.setStrokeColor(blush)
        canvas.line(48, 40, A4[0] - 48, 40)
        canvas.setFillColor(wine)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(48, 27, "GIVYN  /  PERSONAL COLOR ANALYSIS")
        canvas.drawRightString(A4[0] - 48, 27, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    data.seek(0)
    return data
