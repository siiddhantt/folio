"""Local Docling measurement adapter; it never reads reference answers or secrets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path


MODELS = [
    {"repo": "docling-project/docling-layout-heron",
     "revision": "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
     "license": "Apache-2.0", "patterns": ["*.json", "*.safetensors", "README.md", "LICENSE*"]},
    {"repo": "docling-project/docling-models",
     "revision": "2199320848bb9a8a519d22e4b528185a4f9a6f64",
     "license": ["Apache-2.0", "CDLA-Permissive-2.0"],
     "patterns": ["model_artifacts/tableformer/**", "README.md", "LICENSE*"]},
]


def normalize_document(document, status, errors, filename):
    """Expose evidence and parser diagnostics without inferring extraction quality."""
    document = document or {}

    def sources(item):
        return [{"physical_page": p.get("page_no"), "bbox": p.get("bbox"),
                 "charspan": p.get("charspan")} for p in item.get("prov", [])]

    spans = [{"source_ref": item.get("self_ref"), "label": item.get("label"),
              "text": item.get("text", ""), "sources": sources(item)}
             for item in document.get("texts", [])]
    tables = [{"source_ref": item.get("self_ref"), "sources": sources(item),
               "structure": item.get("data", {})} for item in document.get("tables", [])]
    return {
        "filename": filename, "status": status, "errors": errors,
        "page_metadata": document.get("pages", {}), "spans": spans, "tables": tables,
        "text": "\n".join(item["text"] for item in spans),
        "coverage_inference": "No complete-coverage claim; preserve parser diagnostics and inspect source.",
        "page_provenance_note": "Physical PDF pages only when supplied by the parser; no invented DOCX pagination.",
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Docling confidence fields can contain NaN for unavailable scores.
    def clean(item):
        if isinstance(item, float) and not (-float("inf") < item < float("inf")):
            return None
        if isinstance(item, dict):
            return {str(k): clean(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v) for v in item]
        return item
    path.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def prefetch(models_dir):
    """Build-time only: pin model revisions, retain cards, and inventory artifacts."""
    from huggingface_hub import snapshot_download

    started = time.perf_counter()
    for model in MODELS:
        snapshot_download(repo_id=model["repo"], revision=model["revision"],
                          local_dir=models_dir / model["repo"].replace("/", "--"),
                          allow_patterns=model["patterns"])
    inventory = []
    for path in sorted(models_dir.rglob("*")):
        if path.is_file() and ".cache" not in path.parts:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            inventory.append({"path": str(path.relative_to(models_dir)), "bytes": path.stat().st_size,
                              "sha256": digest})
    write_json(models_dir / "manifest.json", {"models": MODELS, "files": inventory,
               "prefetch_elapsed_seconds": time.perf_counter() - started})


def create_converter(models_dir):
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        LayoutObjectDetectionOptions, PdfPipelineOptions, TableFormerMode,
        TableStructureOptions, TesseractCliOcrOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        artifacts_path=models_dir, document_timeout=120.0,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=1),
        do_ocr=True, do_table_structure=True, enable_remote_services=False,
        ocr_options=TesseractCliOcrOptions(lang=["eng"], force_full_page_ocr=False),
        table_structure_options=TableStructureOptions(mode=TableFormerMode.ACCURATE),
    )
    layout = LayoutObjectDetectionOptions.from_preset("layout_heron_default")
    layout.model_spec = layout.model_spec.model_copy(update={"revision": MODELS[0]["revision"]})
    options.layout_options = layout
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
                                  format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    return converter, options.model_dump(mode="json")


def version_manifest():
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    return {"python": sys.version, "platform": platform.platform(), "packages": dict(sorted(versions.items())),
            "tesseract": subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=True).stdout,
            "system_packages": subprocess.run(["dpkg-query", "-W"], capture_output=True, text=True, check=True).stdout}


def memory_high_water():
    import resource
    return {"process_ru_maxrss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "children_ru_maxrss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            "scope": "Cumulative process/child high water on Linux, NOT per-file peak or container memory."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("/fixtures"))
    parser.add_argument("--results", type=Path, default=Path("/results"))
    parser.add_argument("--models", type=Path, default=Path("/models"))
    parser.add_argument("--files", nargs="+")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--prefetch", action="store_true")
    args = parser.parse_args()
    if args.prefetch:
        prefetch(args.models)
        return
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    names = args.files or [p.name for p in sorted(args.fixtures.iterdir()) if p.suffix.lower() in {".pdf", ".docx"}]
    files = []
    fixture_root = args.fixtures.resolve()
    for name in names:
        path = (fixture_root / name).resolve()
        if path.parent != fixture_root or not path.is_file():
            parser.error(f"Expected an existing file directly in fixtures: {name}")
        files.append(path)
    output = args.results / "docling"
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    converter, config = create_converter(args.models)
    initialization_seconds = time.perf_counter() - started
    versions = version_manifest()
    model_manifest = json.loads((args.models / "manifest.json").read_text(encoding="utf-8"))
    write_json(output / "environment.json", {"versions": versions, "configuration": config, "models": model_manifest,
               "converter_initialization_seconds": initialization_seconds,
               "timing_scope": "convert() wall time only; excludes prefetch, imports/converter construction and artifact serialization. First conversion includes lazy model loading.",
               "repeat_policy": "One converter/process; first conversion cold, later conversions warm. Format pipelines initialize lazily."})
    measurements = []
    seen_formats = set()
    conversion_index = 0
    for path in files:
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for repeat in range(1, args.repeats + 1):
            run_dir = output / path.name / f"run-{repeat}"
            phase = "first_document_cold" if conversion_index == 0 else "same_process_warm"
            first_format_use = path.suffix.lower() not in seen_formats
            raw = None
            metadata = {}
            stage = "convert"
            elapsed_start = time.perf_counter()
            try:
                result = converter.convert(path, raises_on_error=False)
                elapsed = time.perf_counter() - elapsed_start
                stage = "export"
                status = result.status.value
                errors = [e.model_dump(mode="json") for e in result.errors]
                # Keep parser diagnostics even when our artifact export fails.
                metadata = {"status": status, "errors": errors}
                metadata.update({"parser_reported_page_count": result.input.page_count,
                                 "processed_page_numbers": [p.page_no for p in result.pages]})
                raw = result.document.export_to_dict()
                metadata.update({"confidence": result.confidence.model_dump(mode="json"),
                                 "timings": {k: v.model_dump(mode="json") for k, v in result.timings.items()}})
            except Exception as exc:
                if stage == "convert":
                    elapsed = time.perf_counter() - elapsed_start
                status = "exception" if stage == "convert" else "adapter_error"
                adapter_error = {"category": status, "stage": stage, "type": type(exc).__name__,
                                 "error_message": str(exc), "page_no": None}
                errors = list(metadata.get("errors", [])) + [adapter_error]
                if metadata:
                    metadata["adapter_errors"] = [adapter_error]
            normalized = normalize_document(raw, status, errors, path.name)
            measurement = {"filename": path.name, "source_sha256": source_hash, "repeat": repeat,
                           "status": status, "elapsed_seconds": elapsed, "cache_phase": phase,
                           "first_format_use": first_format_use, "memory": memory_high_water()}
            normalized.update(measurement)
            normalized["conversion_metadata"] = metadata
            normalized["environment_file"] = "../../environment.json"
            write_json(run_dir / "raw.json", raw)
            write_json(run_dir / "normalized.json", normalized)
            write_json(run_dir / "conversion.json", metadata or {"status": status, "errors": errors})
            measurements.append(measurement)
            # Persist after every run so completed work survives a later native crash.
            write_json(output / "summary.json", {"parser": "docling", "measurements": measurements,
                       "environment_file": "environment.json", "aggregate_speed_claim": None})
            print(json.dumps(measurement), flush=True)
            seen_formats.add(path.suffix.lower())
            conversion_index += 1


if __name__ == "__main__":
    main()
