"""One concrete local Docling integration, invoked only after a worker claim."""

import importlib.metadata
import json
import time
from pathlib import Path

from .evidence import Element, Extraction, ExtractionError, Location, Page

DOCLING_VERSION = "2.148.0"
HERON_REVISION = "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"


def _inspect_pdf(path, max_pages, diagnostics):
    import pypdfium2

    try:
        document = pypdfium2.PdfDocument(path)
    except pypdfium2.PdfiumError as exc:
        if exc.err_code == pypdfium2.raw.FPDF_ERR_PASSWORD:
            raise ExtractionError("ENCRYPTED_PDF", "Encrypted PDFs are not supported.") from exc
        raise ExtractionError(
            "INVALID_PDF",
            "The PDF could not be opened.",
            diagnostics=[{"pdfium_error_code": exc.err_code}],
        ) from exc
    with document:
        if pypdfium2.raw.FPDF_GetSecurityHandlerRevision(document.raw) >= 0:
            raise ExtractionError("ENCRYPTED_PDF", "Encrypted PDFs are not supported.")
        page_count = len(document)
        if page_count > max_pages:
            raise ExtractionError(
                "PAGE_LIMIT_EXCEEDED",
                "The PDF exceeds the configured page limit.",
                diagnostics=[{"page_count": page_count, "max_pages": max_pages}],
            )
        inventory = {}
        for index in range(page_count):
            page = None
            width = height = None
            try:
                page = document[index]
                width, height = page.get_size()
            except Exception as exc:
                diagnostics.append(
                    {
                        "code": "PAGE_GEOMETRY_UNAVAILABLE",
                        "page_no": index + 1,
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            finally:
                if page is not None:
                    page.close()
            inventory[str(index + 1)] = {"size": {"width": width, "height": height}}
        return inventory


def _converter(models_path: Path, timeout_seconds: float):
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        LayoutObjectDetectionOptions,
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
        TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        artifacts_path=models_path,
        document_timeout=timeout_seconds,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=1),
        do_ocr=True,
        do_table_structure=True,
        enable_remote_services=False,
        ocr_options=TesseractCliOcrOptions(lang=["eng"], force_full_page_ocr=False),
        table_structure_options=TableStructureOptions(mode=TableFormerMode.ACCURATE),
    )
    layout = LayoutObjectDetectionOptions.from_preset("layout_heron_default")
    layout.model_spec = layout.model_spec.model_copy(update={"revision": HERON_REVISION})
    options.layout_options = layout
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)},
    )
    return converter, options.model_dump(mode="json")


def _elements(raw, page_metadata, diagnostics, normalization_version):
    by_reference = {
        item["self_ref"]: item
        for collection in ("texts", "tables", "groups", "pictures")
        for item in raw.get(collection, [])
    }
    elements = []
    visited = set()

    def visit(reference, parent_id=None):
        if reference in visited:
            return
        visited.add(reference)
        item = by_reference[reference]
        element_id = None
        table_data = None
        if item.get("label") == "table" or (
            normalization_version >= 2 and item.get("label") == "document_index"
        ):
            data = item["data"]
            table_data = {
                "row_count": data["num_rows"],
                "column_count": data["num_cols"],
                "cells": [
                    {
                        "row": cell["start_row_offset_idx"],
                        "column": cell["start_col_offset_idx"],
                        "row_span": cell["row_span"],
                        "column_span": cell["col_span"],
                        "text": cell["text"],
                        "column_header": cell["column_header"],
                        "row_header": cell["row_header"],
                        "row_section": cell["row_section"],
                    }
                    for cell in data["table_cells"]
                ],
            }
        has_table_content = table_data and any(cell["text"].strip() for cell in table_data["cells"])
        if item.get("text", "").strip() or has_table_content:
            element_id = f"e{len(elements) + 1}"
            locations = []
            for provenance in item.get("prov", []):
                page_no = provenance["page_no"]
                if type(page_no) is not int or str(page_no) not in page_metadata:
                    continue
                box = provenance.get("bbox")
                coordinates = (None, None, None, None)
                if box:
                    if box["coord_origin"] == "BOTTOMLEFT":
                        height = page_metadata[str(page_no)]["size"]["height"]
                        if height is not None:
                            coordinates = (box["l"], height - box["t"], box["r"], height - box["b"])
                    elif box["coord_origin"] == "TOPLEFT":
                        coordinates = (box["l"], box["t"], box["r"], box["b"])
                locations.append(Location(page_no, *coordinates))
            if locations:
                elements.append(
                    Element(
                        element_id,
                        item.get("label", "text"),
                        len(elements),
                        parent_id,
                        item.get("text"),
                        table_data,
                        reference,
                        locations,
                    )
                )
            else:
                diagnostics.append(
                    {
                        "code": "SOURCE_LOCATION_UNAVAILABLE",
                        "provider_ref": reference,
                        "message": "Unlocated content is retained in the raw result only.",
                    }
                )
                element_id = None
        for child in item.get("children", []):
            visit(child["$ref"], element_id or parent_id)

    # Docling supplies separate trees; retain each tree's order without inventing
    # an interleaving between body text and page furniture.
    for tree in ("body", "furniture"):
        for child in raw.get(tree, {}).get("children", []):
            visit(child["$ref"])
    return elements


def parse_pdf(path: Path, config: dict) -> Extraction:
    """Extract locally; duration includes admission, imports, model setup and mapping."""
    started = time.perf_counter()
    max_pages = config.get("max_pages", 100)
    timeout_seconds = config.get("timeout_seconds", 240)
    normalization_version = config.get("normalization_version", 2)
    models_path = Path(config.get("models_path", "/models"))
    actual_version = importlib.metadata.version("docling")
    expected_version = config.get("parser_version", DOCLING_VERSION)
    if actual_version != expected_version:
        raise ExtractionError(
            "PARSER_VERSION_MISMATCH",
            "The worker does not match the requested parser version.",
            diagnostics=[{"expected_version": expected_version, "actual_version": actual_version}],
            parser_manifest={"name": "docling", "version": actual_version},
        )
    diagnostics = []
    page_metadata = _inspect_pdf(path, max_pages, diagnostics)
    converter, options = _converter(models_path, timeout_seconds)
    manifest = {
        "name": "docling",
        "version": actual_version,
        "configuration": {
            "max_pages": max_pages,
            "timeout_seconds": timeout_seconds,
            "parser_version": expected_version,
            "models_path": str(models_path),
            "pipeline_options": options,
        },
        "models": json.loads((models_path / "manifest.json").read_text(encoding="utf-8")),
        "normalization_version": str(normalization_version),
    }
    result = converter.convert(path, raises_on_error=False, max_num_pages=max_pages)
    diagnostics.extend(error.model_dump(mode="json") for error in result.errors)
    raw = None
    try:
        raw = result.document.export_to_dict()
        elements = _elements(raw, page_metadata, diagnostics, normalization_version)
        recovered = {location.page_no for element in elements for location in element.locations}
        if result.status.value == "partial_success":
            diagnostics.append(
                {
                    "code": "PARSER_PARTIAL_RESULT",
                    "page_no": None,
                    "message": "Partial conversion; recovered evidence remains available.",
                }
            )
        pages = []
        for number, page in sorted(page_metadata.items(), key=lambda entry: int(entry[0])):
            number = int(number)
            if number not in recovered:
                diagnostics.append(
                    {
                        "code": "NO_CONTENT_RECOVERED",
                        "page_no": number,
                        "cause": None,
                        "message": "No usable content recovered; the cause is unknown.",
                    }
                )
            pages.append(
                Page(
                    number,
                    page["size"]["width"],
                    page["size"]["height"],
                    "content_recovered" if number in recovered else "no_content_recovered",
                    [item for item in diagnostics if item.get("page_no") == number],
                )
            )
        if not elements:
            raise ExtractionError(
                "NO_USABLE_CONTENT",
                "No usable text or table evidence was recovered.",
                diagnostics=diagnostics,
                parser_status=result.status.value,
                parser_manifest=manifest,
                raw=raw,
            )
        return Extraction(
            pages,
            elements,
            diagnostics,
            result.status.value,
            manifest,
            raw,
            time.perf_counter() - started,
        )
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(
            "NORMALIZATION_FAILED",
            "The parser result could not be mapped to evidence.",
            diagnostics=diagnostics
            + [{"code": "NORMALIZATION_FAILED", "type": type(exc).__name__, "message": str(exc)}],
            parser_status=result.status.value,
            parser_manifest=manifest,
            raw=raw,
        ) from exc
