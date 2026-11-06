"""Artifact-contract checks, independent of parser quality or benchmark facts."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import run
from run import normalize_document


class ResultContract(unittest.TestCase):
    def test_partial_result_keeps_source_and_error(self):
        document = {
            "pages": {"2": {"page_no": 2}},
            "texts": [{"self_ref": "#/texts/0", "text": "Visible passage",
                       "prov": [{"page_no": 2, "charspan": [0, 15],
                                 "bbox": {"l": 1, "t": 2, "r": 3, "b": 4}}]}],
            "tables": [],
        }
        errors = [{"page_no": 3, "category": "backend_failure", "error_message": "Unreadable"}]
        result = normalize_document(document, "partial_success", errors, "sample.pdf")
        self.assertEqual(result["status"], "partial_success")
        self.assertEqual(result["errors"], errors)
        self.assertEqual(result["spans"][0]["text"], "Visible passage")
        self.assertEqual(result["spans"][0]["sources"][0]["physical_page"], 2)
        self.assertEqual(result["spans"][0]["sources"][0]["charspan"], [0, 15])

    def test_export_failure_keeps_parser_diagnostics_in_emitted_artifacts(self):
        parser_error = {"page_no": 3, "category": "backend_failure", "error_message": "Unreadable"}
        parsed = SimpleNamespace(
            status=SimpleNamespace(value="partial_success"),
            errors=[SimpleNamespace(model_dump=lambda **kwargs: parser_error)],
            document=SimpleNamespace(export_to_dict=Mock(side_effect=ValueError("Cannot export"))),
            input=SimpleNamespace(page_count=3), pages=[],
        )
        converter = SimpleNamespace(convert=lambda *args, **kwargs: parsed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            (fixtures / "sample.pdf").write_bytes(b"Synthetic adapter input; parser is stubbed.")
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            argv = ["run.py", "--fixtures", str(fixtures), "--results", str(root / "results"),
                    "--models", str(root), "--repeats", "1"]
            with patch.object(run, "create_converter", return_value=(converter, {})), \
                 patch.object(run, "version_manifest", return_value={}), \
                 patch.object(run, "memory_high_water", return_value={}), \
                 patch("sys.argv", argv), patch("builtins.print"):
                run.main()
            output = root / "results" / "docling" / "sample.pdf" / "run-1"
            conversion = json.loads((output / "conversion.json").read_text(encoding="utf-8"))
            normalized = json.loads((output / "normalized.json").read_text(encoding="utf-8"))
            self.assertEqual(conversion["status"], "partial_success")
            self.assertEqual(conversion["errors"], [parser_error])
            self.assertEqual(conversion["adapter_errors"][0]["type"], "ValueError")
            self.assertEqual(normalized["status"], "adapter_error")
            self.assertIn(parser_error, normalized["errors"])


if __name__ == "__main__":
    unittest.main()
