"""Saved Docling evidence to bounded, source-linked chunks; no model calls."""

import unittest
import warnings

import pytest

from folio.indexing.chunking import ChunkingError, prepare_chunks

pytestmark = pytest.mark.parser


def document():
    from docling_core.types.doc import DoclingDocument

    return DoclingDocument(name="Synthetic evidence")


def passage(doc, text, page, element_id, *, heading=False):
    from docling_core.types.doc import BoundingBox, DocItemLabel, ProvenanceItem

    provenance = ProvenanceItem(
        page_no=page,
        bbox=BoundingBox(l=10, t=10, r=200, b=40, coord_origin="TOPLEFT"),
        charspan=(0, len(text)),
    )
    if heading:
        item = doc.add_heading(text=text, prov=provenance)
    else:
        item = doc.add_text(label=DocItemLabel.TEXT, text=text, prov=provenance)
    return {
        "element_id": element_id,
        "provider_ref": item.self_ref,
        "locations": [{"page_no": page}],
    }


class ChunkPreparation(unittest.TestCase):
    def test_figure_footnote_keeps_its_source_and_surrounding_heading(self):
        from docling_core.types.doc import BoundingBox, DocItemLabel, ProvenanceItem

        doc = document()
        sources = [
            passage(doc, "Running costs", 1, "heading", heading=True),
            passage(doc, "The annual figure is 500.", 2, "body"),
        ]
        figure = doc.add_picture()
        footnote = doc.add_text(
            label=DocItemLabel.FOOTNOTE,
            text="Figures exclude maintenance.",
            parent=figure,
            prov=ProvenanceItem(
                page_no=2,
                bbox=BoundingBox(l=10, t=50, r=200, b=70, coord_origin="TOPLEFT"),
                charspan=(0, 27),
            ),
        )
        figure.footnotes.append(footnote.get_ref())
        sources.append(
            {
                "element_id": "footnote",
                "provider_ref": footnote.self_ref,
                "locations": [{"page_no": 2}],
            }
        )

        result = prepare_chunks(doc.export_to_dict(), sources, token_limit=128)

        chunk = next(c for c in result["chunks"] if "exclude maintenance" in c["text"])
        self.assertIn("Running costs", chunk["text"])
        self.assertIn({"element_id": "heading", "role": "context"}, chunk["sources"])
        self.assertIn({"element_id": "footnote", "role": "body"}, chunk["sources"])
        self.assertEqual(result["exclusions"], [])

    def test_heading_and_body_keep_separate_source_links(self):
        doc = document()
        sources = [
            passage(doc, "Building cover", 2, "heading", heading=True),
            passage(doc, "Garage cover reduces the building limit.", 3, "clause"),
        ]

        result = prepare_chunks(doc.export_to_dict(), sources, token_limit=128)

        self.assertEqual(len(result["chunks"]), 1)
        chunk = result["chunks"][0]
        self.assertEqual(chunk["text"], "Building cover\nGarage cover reduces the building limit.")
        self.assertEqual(
            chunk["sources"],
            [
                {"element_id": "heading", "role": "context"},
                {"element_id": "clause", "role": "body"},
            ],
        )
        self.assertEqual(result["exclusions"], [])
        self.assertLessEqual(chunk["tokens"], 128)

    def test_unknown_source_reference_cannot_be_an_exclusion(self):
        doc = document()
        source = passage(doc, "A located fact.", 1, "body")
        unrelated = {
            "element_id": "other",
            "provider_ref": "#/texts/999",
            "locations": [{"page_no": 1}],
        }
        with self.assertRaises(ChunkingError) as failed:
            prepare_chunks(doc.export_to_dict(), [source, unrelated])
        self.assertEqual(failed.exception.code, "CHUNK_SOURCE_UNAVAILABLE")

    def test_literal_token_spelling_survives_bounded_splits_as_document_text(self):
        doc = document()
        text = "The manual quotes <|endoftext|> as ordinary text. " * 30 + "Final qualification."
        sources = [passage(doc, text, 2, "manual")]

        result = prepare_chunks(doc.export_to_dict(), sources, token_limit=64)

        self.assertGreater(len(result["chunks"]), 1)
        self.assertTrue(all(chunk["tokens"] <= 64 for chunk in result["chunks"]))
        self.assertIn("Final qualification.", result["chunks"][-1]["text"])
        self.assertEqual(
            sum(chunk["text"].count("<|endoftext|>") for chunk in result["chunks"]), 30
        )
        for chunk in result["chunks"]:
            self.assertEqual(chunk["sources"], [{"element_id": "manual", "role": "body"}])

    def test_unmapped_or_unlocated_source_fails_before_returning_a_plan(self):
        doc = document()
        heading = passage(doc, "Important condition", 1, "heading", heading=True)
        body = passage(doc, "Coverage is limited.", 2, "body")
        for sources in ([body], [heading | {"locations": []}, body]):
            with self.subTest(sources=sources):
                with self.assertRaises(ChunkingError) as failed:
                    prepare_chunks(doc.export_to_dict(), sources)
                self.assertEqual(failed.exception.code, "CHUNK_SOURCE_UNAVAILABLE")

    def test_oversized_heading_cannot_disappear_from_an_accepted_plan_or_logs(self):
        doc = document()
        sources = [
            passage(doc, "Important qualification " * 100, 1, "heading", heading=True),
            passage(doc, "The shared limit is 500.", 2, "body"),
        ]
        with warnings.catch_warnings(record=True) as emitted:
            with self.assertRaises(ChunkingError) as failed:
                prepare_chunks(doc.export_to_dict(), sources, token_limit=64)
        self.assertEqual(failed.exception.code, "CHUNK_CONTEXT_LOST")
        self.assertEqual(emitted, [])

    def test_no_indexable_body_returns_an_explicit_failure(self):
        with self.assertRaises(ChunkingError) as failed:
            prepare_chunks(document().export_to_dict(), [])
        self.assertEqual(failed.exception.code, "NO_INDEXABLE_CONTENT")

    def test_standalone_and_equal_text_headings_keep_their_distinct_identities(self):
        doc = document()
        sources = [
            passage(doc, "Important qualification", 1, "standalone", heading=True),
            passage(doc, "Conditions", 2, "first-heading", heading=True),
            passage(doc, "First condition.", 3, "first-body"),
            passage(doc, "Conditions", 5, "second-heading", heading=True),
            passage(doc, "Second condition.", 6, "second-body"),
        ]
        result = prepare_chunks(doc.export_to_dict(), sources, token_limit=128)
        self.assertIn("Important qualification", "\n".join(c["text"] for c in result["chunks"]))
        self.assertEqual(
            {s["element_id"] for c in result["chunks"] for s in c["sources"]},
            {"standalone", "first-heading", "first-body", "second-heading", "second-body"},
        )
        self.assertEqual(result["exclusions"], [])
