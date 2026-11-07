"""PDF-to-evidence contract checks using synthetic, inspectable documents."""

import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from folio.parsing import ExtractionError, parse_pdf

pytestmark = pytest.mark.parser
FIXTURES = Path(os.environ.get("FOLIO_TEST_PDFS", str(Path(__file__).parent / "fixtures")))
CONFIG = {"max_pages": 100, "timeout_seconds": 240, "models_path": "/models"}


class ParserContract(unittest.TestCase):
    def test_text_keeps_physical_pages_and_top_left_source_box(self):
        result = parse_pdf(FIXTURES / "text.pdf", CONFIG)
        revenue = next(element for element in result.elements if "125,000" in (element.text or ""))
        self.assertEqual([page.page_no for page in result.pages], [1, 2, 3])
        self.assertEqual(result.elements[0].text, "Sample operating report")
        self.assertEqual(revenue.locations[0].page_no, 2)
        self.assertAlmostEqual(revenue.locations[0].x0, 54, places=1)
        # The parser may group the period and revenue lines into one passage.
        # The revenue's printed baseline is about 123 points from the page top.
        self.assertGreater(revenue.locations[0].y0, 60)
        self.assertLess(revenue.locations[0].y0, 123)
        self.assertGreater(revenue.locations[0].y1, 123)
        self.assertLess(revenue.locations[0].y1, 140)
        self.assertIsNone(revenue.locations[0].char_start)
        self.assertIsNone(revenue.locations[0].char_end)
        self.assertEqual(result.parser_manifest["version"], "2.148.0")
        self.assertEqual(result.parser_manifest["configuration"]["timeout_seconds"], 240)
        self.assertTrue(result.raw["texts"])
        json.dumps(asdict(result), allow_nan=False)

    def test_table_keeps_department_year_headers_and_reading_order(self):
        result = parse_pdf(FIXTURES / "table.pdf", CONFIG)
        tables = [element for element in result.elements if element.kind == "table"]
        self.assertEqual(len(tables), 2)
        table = tables[1]
        cells = {(cell["row"], cell["column"]): cell for cell in table.table_data["cells"]}
        self.assertEqual(
            [cells[0, column]["text"] for column in range(3)], ["Department", "2025", "2026"]
        )
        self.assertEqual(
            [cells[1, column]["text"] for column in range(3)], ["Operations", "14", "19"]
        )
        self.assertTrue(cells[0, 2]["column_header"])
        self.assertEqual(table.locations[0].page_no, 2)
        self.assertLess(table.locations[0].y0, table.locations[0].y1)
        heading = next(
            element for element in result.elements if element.text == "Headcount without grid"
        )
        self.assertLess(heading.reading_order, table.reading_order)

    def test_ocr_evidence_remains_available_with_unknown_no_content_page(self):
        result = parse_pdf(FIXTURES / "mixed.pdf", CONFIG)
        renewal = next(
            element for element in result.elements if "30 September 2027" in (element.text or "")
        )
        self.assertEqual(renewal.locations[0].page_no, 2)
        self.assertEqual(result.pages[2].content_observation, "no_content_recovered")
        warning = next(
            item for item in result.diagnostics if item.get("code") == "NO_CONTENT_RECOVERED"
        )
        self.assertEqual(warning["page_no"], 3)
        self.assertIsNone(warning["cause"])
        self.assertIn(warning, result.pages[2].diagnostics)

    def test_empty_pdf_is_unavailable_with_retained_diagnostics(self):
        import pypdfium2

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "empty.pdf"
            with pypdfium2.PdfDocument.new() as document:
                page = document.new_page(595, 842)
                page.close()
                document.save(path)
            with self.assertRaises(ExtractionError) as raised:
                parse_pdf(path, CONFIG)
        error = raised.exception
        self.assertEqual(error.code, "NO_USABLE_CONTENT")
        self.assertFalse(error.retryable)
        self.assertIsNotNone(error.raw)
        self.assertIsNotNone(error.parser_status)
        self.assertTrue(
            any(item.get("code") == "NO_CONTENT_RECOVERED" for item in error.diagnostics)
        )

    def test_page_limit_rejects_the_document_without_silent_truncation(self):
        with self.assertRaises(ExtractionError) as raised:
            parse_pdf(FIXTURES / "text.pdf", {**CONFIG, "max_pages": 2})
        self.assertEqual(raised.exception.code, "PAGE_LIMIT_EXCEEDED")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.diagnostics[0]["page_count"], 3)

    def test_reported_partial_result_keeps_evidence_and_full_page_inventory(self):
        raw = {
            "body": {"children": [{"$ref": "#/texts/0"}]},
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "label": "text",
                    "text": "Sample operating report",
                    "prov": [{"page_no": 1}],
                }
            ],
            "pages": {},
        }
        diagnostic = {"page_no": 2, "error_message": "Page decoding failed"}
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="partial_success"),
            errors=[SimpleNamespace(model_dump=lambda **kwargs: diagnostic)],
            document=SimpleNamespace(export_to_dict=lambda: raw),
        )
        # Control the third-party parser result; exercise Folio only via parse_pdf.
        with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
            result = parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual(result.parser_status, "partial_success")
        self.assertEqual(result.elements[0].text, "Sample operating report")
        self.assertEqual([page.page_no for page in result.pages], [1, 2, 3])
        self.assertIn(diagnostic, result.diagnostics)
        self.assertIn(diagnostic, result.pages[1].diagnostics)
        self.assertTrue(
            any(item.get("code") == "PARSER_PARTIAL_RESULT" for item in result.diagnostics)
        )

    def test_encrypted_pdf_has_a_specific_terminal_error(self):
        with self.assertRaises(ExtractionError) as raised:
            parse_pdf(FIXTURES / "encrypted.pdf", CONFIG)
        self.assertEqual(raised.exception.code, "ENCRYPTED_PDF")
        self.assertFalse(raised.exception.retryable)

    def test_invalid_pdf_has_a_specific_terminal_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.pdf"
            path.write_bytes(b"%PDF-1.7\nnot a valid PDF")
            with self.assertRaises(ExtractionError) as raised:
                parse_pdf(path, CONFIG)
        self.assertEqual(raised.exception.code, "INVALID_PDF")
        self.assertFalse(raised.exception.retryable)

    def test_unlocated_text_is_not_published_as_usable_evidence(self):
        raw = {
            "body": {"children": [{"$ref": "#/texts/0"}]},
            "pages": {},
            "texts": [
                {"self_ref": "#/texts/0", "label": "text", "text": "Unlocated passage", "prov": []}
            ],
        }
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="success"),
            errors=[],
            document=SimpleNamespace(export_to_dict=lambda: raw),
        )
        with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
            with self.assertRaises(ExtractionError) as raised:
                parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual(raised.exception.code, "NO_USABLE_CONTENT")
        self.assertEqual(raised.exception.raw, raw)
        self.assertTrue(
            any(
                item.get("code") == "SOURCE_LOCATION_UNAVAILABLE"
                for item in raised.exception.diagnostics
            )
        )

    def test_separate_furniture_content_is_retained_once_with_its_location(self):
        raw = {
            "body": {"children": []},
            "furniture": {"children": [{"$ref": "#/texts/0"}]},
            "pages": {},
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "label": "page_header",
                    "text": "Document reference ABC-27",
                    "prov": [{"page_no": 1}],
                }
            ],
        }
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="success"),
            errors=[],
            document=SimpleNamespace(export_to_dict=lambda: raw),
        )
        with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
            result = parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual(
            [element.text for element in result.elements], ["Document reference ABC-27"]
        )
        self.assertEqual(result.elements[0].locations[0].page_no, 1)

    def test_export_failure_retains_original_parser_diagnostics(self):
        diagnostic = {"page_no": 2, "error_message": "Original page failure"}
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="partial_success"),
            errors=[SimpleNamespace(model_dump=lambda **kwargs: diagnostic)],
            document=SimpleNamespace(export_to_dict=Mock(side_effect=ValueError("Bad export"))),
        )
        with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
            with self.assertRaises(ExtractionError) as raised:
                parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual(raised.exception.code, "NORMALIZATION_FAILED")
        self.assertEqual(raised.exception.parser_status, "partial_success")
        self.assertIn(diagnostic, raised.exception.diagnostics)

    def test_parser_cannot_invent_a_physical_page_for_source_content(self):
        raw = {
            "body": {"children": [{"$ref": "#/texts/0"}]},
            "pages": {"4": {"size": {"width": 595, "height": 842}}},
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "label": "text",
                    "text": "Impossible page",
                    "prov": [{"page_no": 4}],
                }
            ],
        }
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="success"),
            errors=[],
            document=SimpleNamespace(export_to_dict=lambda: raw),
        )
        with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
            with self.assertRaises(ExtractionError) as raised:
                parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual(raised.exception.code, "NO_USABLE_CONTENT")
        self.assertEqual(raised.exception.raw, raw)

    def test_unreadable_page_geometry_does_not_discard_recovered_content(self):
        raw = {
            "body": {"children": [{"$ref": "#/texts/0"}]},
            "pages": {},
            "texts": [
                {
                    "self_ref": "#/texts/0",
                    "label": "text",
                    "text": "Located by page",
                    "prov": [
                        {
                            "page_no": 1,
                            "bbox": {
                                "coord_origin": "BOTTOMLEFT",
                                "l": 10,
                                "b": 10,
                                "r": 20,
                                "t": 20,
                            },
                        }
                    ],
                }
            ],
        }
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="partial_success"),
            errors=[],
            document=SimpleNamespace(export_to_dict=lambda: raw),
        )
        with patch(
            "pypdfium2.PdfPage.get_size",
            side_effect=[RuntimeError("Bad geometry"), (595, 842), (595, 842)],
        ):
            with patch("docling.document_converter.DocumentConverter.convert", return_value=parsed):
                result = parse_pdf(FIXTURES / "text.pdf", CONFIG)
        self.assertEqual([page.page_no for page in result.pages], [1, 2, 3])
        self.assertIsNone(result.pages[0].height_pt)
        self.assertEqual(result.pages[1].height_pt, 842)
        self.assertEqual(result.elements[0].locations[0].page_no, 1)
        self.assertIsNone(result.elements[0].locations[0].y0)
        self.assertTrue(
            any(
                item.get("code") == "PAGE_GEOMETRY_UNAVAILABLE"
                for item in result.pages[0].diagnostics
            )
        )

    def test_frozen_parser_version_must_match_the_running_worker(self):
        with self.assertRaises(ExtractionError) as raised:
            parse_pdf(FIXTURES / "text.pdf", {**CONFIG, "parser_version": "0.0.0"})
        self.assertEqual(raised.exception.code, "PARSER_VERSION_MISMATCH")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.parser_manifest["version"], "2.148.0")

    def test_damaged_middle_page_keeps_neighbors_without_claiming_the_cause(self):
        result = parse_pdf(FIXTURES / "damaged.pdf", CONFIG)
        cedar = next(element for element in result.elements if "CEDAR-17" in (element.text or ""))
        maple = next(element for element in result.elements if "MAPLE-42" in (element.text or ""))
        self.assertEqual(cedar.locations[0].page_no, 1)
        self.assertEqual(maple.locations[0].page_no, 3)
        self.assertEqual(result.pages[1].content_observation, "no_content_recovered")
        gap = next(
            item
            for item in result.pages[1].diagnostics
            if item.get("code") == "NO_CONTENT_RECOVERED"
        )
        self.assertIsNone(gap["cause"])


if __name__ == "__main__":
    unittest.main()
