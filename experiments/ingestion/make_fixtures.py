"""Generate small synthetic inputs and a separate source-of-truth manifest."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def text_pdf(path, pages):
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    for number, lines in enumerate(pages, 1):
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(54, 785, lines[0])
        pdf.setFont("Helvetica", 12)
        for index, line in enumerate(lines[1:]):
            pdf.drawString(54, 745 - index * 26, line)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(54, 35, f"Synthetic fixture - physical page {number}")
        pdf.showPage()
    pdf.save()


def raster_pdf(path, image):
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    pdf.drawImage(str(image), 0, 0, width=A4[0], height=A4[1])
    pdf.save()


def table_pdf(path):
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    for title, rows, grid in [
        ("Headcount with grid", [("Engineering", "20", "27"), ("Support", "12", "18")], True),
        ("Headcount without grid", [("Operations", "14", "19"), ("Finance", "8", "11")], False),
    ]:
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(54, 785, title)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(54, 750, "Each number belongs to its department and column year.")
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(68, 695, "Department")
        pdf.drawString(260 if grid else 242, 695, "2025")
        pdf.drawString(390 if grid else 372, 695, "2026")
        pdf.setFont("Helvetica", 12)
        for index, row in enumerate(rows):
            y = 655 - index * 40
            for x, text in zip((68, 270, 400), row):
                pdf.drawString(x, y, text)
        if grid:
            for y in (720, 680, 640, 600):
                pdf.line(54, y, 500, y)
            for x in (54, 230, 360, 500):
                pdf.line(x, 600, x, 720)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(54, 35, "Synthetic fixture - inspect row and year associations")
        pdf.showPage()
    pdf.save()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--pdftoppm", default="pdftoppm")
    args = cli.parse_args()
    fixtures = args.output / "fixtures"
    reference = args.output / "reference"
    previews = args.output / "previews"
    for directory in (fixtures, reference, previews):
        directory.mkdir(parents=True, exist_ok=True)

    text_pdf(fixtures / "text.pdf", [
        ["Sample operating report", "This synthetic report contains three physical pages."],
        ["Reporting facts", "Reporting period: 1 April 2026 to 30 June 2026.", "Revenue: USD 125,000."],
        ["Service terms", "Notice period: 45 days.", "These facts are for parser validation only."],
    ])
    text_pdf(reference / "scan-source.pdf", [[
        "Renewal appendix", "Renewal date: 30 September 2027.",
        "Service fee: USD 7,500.", "Appendix - printed page 7.",
    ]])
    subprocess.run([
        args.pdftoppm, "-f", "1", "-singlefile", "-r", "180", "-png",
        str(reference / "scan-source.pdf"), str(reference / "scan-page"),
    ], check=True, capture_output=True)
    raster_pdf(fixtures / "scanned.pdf", reference / "scan-page.png")
    text_pdf(reference / "mixed-first.pdf", [["Budget", "Approved budget: USD 120,000."]])
    writer = PdfWriter()
    writer.append(str(reference / "mixed-first.pdf"))
    writer.append(str(fixtures / "scanned.pdf"))
    writer.add_blank_page(width=A4[0], height=A4[1])
    writer.write(str(fixtures / "mixed.pdf"))
    table_pdf(fixtures / "table.pdf")

    text_pdf(reference / "damaged-original.pdf", [
        ["Before the damaged page", "Recovery marker: CEDAR-17."],
        ["Content that will be corrupted", "Hold period: 99 days."],
        ["After the damaged page", "Recovery marker: MAPLE-42."],
    ])
    writer = PdfWriter()
    writer.append(str(reference / "damaged-original.pdf"))
    broken = DecodedStreamObject()
    broken.set_data(b"deliberately undecodable fixture stream")
    broken[NameObject("/Filter")] = NameObject("/FolioInvalidDecode")
    writer.pages[1][NameObject("/Contents")] = writer._add_object(broken)
    writer.write(str(fixtures / "damaged.pdf"))

    document = Document()
    document.core_properties.created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    document.core_properties.modified = datetime(2026, 1, 1, tzinfo=timezone.utc)
    document.core_properties.author = "Folio"
    document.add_heading("Sample operating note", 0)
    document.add_paragraph("Reporting period: 1 April 2026 to 30 June 2026.")
    document.add_paragraph("Revenue: USD 125,000.")
    document.add_heading("Headcount", 1)
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    for cell, value in zip(table.rows[0].cells, ("Department", "2025", "2026")):
        cell.text = value
    for row in (("Engineering", "20", "27"), ("Support", "12", "18")):
        for cell, value in zip(table.add_row().cells, row):
            cell.text = value
    document.add_paragraph("Synthetic fixture; Word layout does not define stable physical pages.")
    document.save(str(fixtures / "document.docx"))

    expected = {
        "text.pdf": {"facts": {"2": ["1 April 2026", "30 June 2026", "125,000"], "3": ["45 days"]}},
        "scanned.pdf": {"facts": {"1": ["30 September 2027", "7,500"]}, "printed_page": 7},
        "mixed.pdf": {"facts": {"1": ["120,000"], "2": ["30 September 2027", "7,500"]}, "blank_pages": [3]},
        "table.pdf": {"tables": {"1": [["Engineering", "20", "27"], ["Support", "12", "18"]], "2": [["Operations", "14", "19"], ["Finance", "8", "11"]]}, "columns": ["Department", "2025", "2026"]},
        "damaged.pdf": {"facts": {"1": ["CEDAR-17"], "3": ["MAPLE-42"]}, "damage": "Page 2 content stream has an unsupported filter. Observe actual rendering and diagnostics; a page exception is not guaranteed."},
        "document.docx": {"facts": ["1 April 2026", "30 June 2026", "125,000"], "table": [["Engineering", "20", "27"], ["Support", "12", "18"]], "source_locator": "Inspect native structure or explicitly identify converted PDF pages; do not invent original Word pages."},
    }
    manifest = []
    for path in sorted(fixtures.iterdir()):
        manifest.append({"file": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if path.suffix == ".pdf":
            page_count = len(PdfReader(path).pages)
            for page in range(1, page_count + 1):
                rendered = subprocess.run([
                    args.pdftoppm, "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", "700", "-png",
                    str(path), str(previews / f"{path.stem}-{page}"),
                ], capture_output=True, text=True)
                if rendered.stderr:
                    (previews / f"{path.stem}-{page}.render.txt").write_text(rendered.stderr, encoding="utf-8")
    (reference / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (reference / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(manifest)} synthetic inputs; references are outside the parser input mount.")


if __name__ == "__main__":
    main()
