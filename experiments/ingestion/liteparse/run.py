"""Local LiteParse measurements; no expected answers or quality assertions."""

import time

PROCESS_START = time.perf_counter()

import argparse
import base64
import dataclasses
import hashlib
import importlib.metadata
import json
import platform
import resource
import subprocess
import sys
import traceback
from pathlib import Path
from statistics import median


def json_default(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"Unsupported JSON type: {type(value).__name__}")


def write_json(path, value):
    path.write_text(json.dumps(value, default=json_default, ensure_ascii=False, indent=2), encoding="utf-8")


def command_version(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    return {"exit_code": result.returncode, "output": (result.stdout + result.stderr).strip()}


def peak_rss():
    # Linux ru_maxrss is KiB. These are lifetime high-water marks, not per-file
    # deltas, instantaneous use, or simultaneous parent+child process-tree peaks.
    return {
        "self_cumulative_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "terminated_children_cumulative_max_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    }


def normalize(raw, filename):
    is_pdf = Path(filename).suffix.lower() == ".pdf"
    total = raw["total_pages"]
    seen = {page["page_num"] for page in raw["pages"]}
    missing = sorted(set(range(1, total + 1)) - seen)
    errors = raw.get("page_errors", [])
    image_errors = raw.get("image_error_count", 0)
    pages = []
    for page in raw["pages"]:
        spans = []
        for item in page["text_items"]:
            spans.append({
                "text": item["text"],
                "bbox": {key: item[key] for key in ("x", "y", "width", "height")},
                "character_offsets": None,
                "extraction_method": "not_exposed_per_span",
                "words": item.get("words", []),
            })
        blocks = page.get("blocks") or []
        cells = []
        for block_index, block in enumerate(blocks):
            for row_index, row in enumerate(block.get("rows") or []):
                for column_index, cell in enumerate(row):
                    cells.append({
                        "block_index": block_index,
                        "row_index": row_index,
                        "column_index": column_index,
                        "text": cell["text"],
                        "bbox": cell.get("bbox"),
                    })
        pages.append({
            "page_number": page["page_num"],
            "physical_page": page["page_num"] if is_pdf else None,
            "converted_page_number": None if is_pdf else page["page_num"],
            "page_label": page.get("page_label"),
            "width": page["width"],
            "height": page["height"],
            "coordinate_system": "top-left, 72-DPI viewport; bbox x/y/width/height",
            "text": page["text"],
            "markdown": page.get("markdown", ""),
            "source_spans": spans,
            "layout_blocks": blocks,
            "table_cells": cells,
            "diagnostics": {
                "complexity": page.get("complexity"),
                "content_bounds": page.get("content_bounds"),
                "empty_text": not bool(page["text"].strip()),
            },
        })
    status = "partial" if errors or image_errors or missing else "success"
    if not any(page["text"].strip() for page in pages) and status == "success":
        status = "empty"
    return {
        "filename": filename,
        "status": status,
        "source_locator_kind": "physical_pdf_page" if is_pdf else "libreoffice_rendered_page",
        "physical_page_count": total if is_pdf else None,
        "parser_reported_page_count": total,
        "returned_page_count": len(pages),
        "text": raw["text"],
        "pages": pages,
        "page_errors": errors,
        "diagnostics": {
            "missing_parser_pages": missing,
            "image_error_count": image_errors,
            "ocr_failed_page_numbers": None,
            "ocr_diagnostic_limit": "2.18.0 exposes aggregate image errors, not failed OCR page identifiers in ParseResult",
            "status_semantics": "success means no reported failure or missing page; not verified extraction completeness",
            "non_pdf_provenance": None if is_pdf else "Page positions belong to an ephemeral LibreOffice rendering, not stable source pagination.",
        },
    }


def main():
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument("--fixtures", type=Path, default=Path("/fixtures"))
    args_parser.add_argument("--results", type=Path, default=Path("/results/liteparse"))
    args_parser.add_argument("--warm-repeats", type=int, default=2)
    args_parser.add_argument("--ocr-workers", type=int, default=2)
    args = args_parser.parse_args()
    if args.warm_repeats < 1 or args.ocr_workers < 1:
        args_parser.error("warm-repeats and ocr-workers must be positive")
    args.results.mkdir(parents=True, exist_ok=True)
    fixtures = sorted(path for path in args.fixtures.iterdir() if path.suffix.lower() in {".pdf", ".docx"})
    if not fixtures:
        args_parser.error("No PDF or DOCX fixtures found")

    import_started = time.perf_counter()
    from liteparse import LiteParse
    import_seconds = time.perf_counter() - import_started
    tessdata = Path("/usr/share/tesseract-ocr/5/tessdata/eng.traineddata")
    if not tessdata.is_file():
        raise RuntimeError("English OCR assets must already be in the image; runtime download is not part of this experiment")
    config = {
        "ocr_enabled": True,
        "ocr_language": "eng",
        "tessdata_path": str(tessdata.parent),
        "num_workers": args.ocr_workers,
        "continue_on_page_error": True,
        "ocr_failure_fatal": True,
        "extract_blocks": True,
        "include_complexity": True,
        "extract_content_bounds": True,
        "extract_text_metadata": True,
        "keep_headers_footers": True,
        "output_format": "json",
        "quiet": True,
    }
    init_started = time.perf_counter()
    parser = LiteParse(**config)
    init_seconds = time.perf_counter() - init_started
    versions = {
        "python": sys.version,
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "liteparse": importlib.metadata.version("liteparse"),
        "upstream_commit": "40abdffd435403ec30341b30511dfb8daba5bf5a",
        "system_tesseract_cli": command_version(["tesseract", "--version"]),
        "libreoffice": command_version(["libreoffice", "--version"]),
        "ocr_assets": {
            "source": "Debian bookworm tesseract-ocr-eng package; explicit data path overrides LiteParse's auto-download",
            "english_sha256": hashlib.sha256(tessdata.read_bytes()).hexdigest(),
            "engine_note": "LiteParse's bundled native Tesseract engine is not necessarily the system CLI version",
        },
    }
    metadata = {
        "versions": versions,
        "config": dataclasses.asdict(parser.get_config()),
        "startup": {"import_seconds": import_seconds, "constructor_seconds": init_seconds,
                    "runner_to_ready_seconds": time.perf_counter() - PROCESS_START,
                    "excludes": "Python interpreter bootstrap before this script starts"},
        "timing_note": "One persistent parser. First pass per file is cold-for-that-file, but only the first fixture is process-cold. Repeats are warmed; no OS cache eviction. Parse timers exclude JSON serialization and output writes; DOCX conversion is included.",
        "memory_note": "ru_maxrss is cumulative high-water RSS; child value covers terminated children and is not simultaneous tree memory. Measure container peak separately.",
        "fixture_order": [path.name for path in fixtures],
    }
    write_json(args.results / "environment.json", metadata)
    summaries = []
    for fixture in fixtures:
        runs = []
        first_normalized = None
        for repeat in range(args.warm_repeats + 1):
            started = time.perf_counter()
            stage = "parse"
            try:
                result = parser.parse(str(fixture))
                elapsed = time.perf_counter() - started
                stage = "serialization_or_normalization"
                raw = dataclasses.asdict(result)
                normalized = normalize(raw, fixture.name)
            except Exception as error:
                elapsed = time.perf_counter() - started
                raw = {"exception": {"stage": stage, "type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}}
                normalized = {"filename": fixture.name, "status": "failed", "pages": [],
                              "page_errors": [], "diagnostics": raw}
            run = {
                "phase": "cold_for_file" if repeat == 0 else "warm",
                "repeat": repeat,
                "elapsed_seconds": elapsed,
                "status": normalized["status"],
                **peak_rss(),
            }
            runs.append(run)
            # Save every measured result, including failures, to expose drift.
            suffix = "" if repeat == 0 else f".warm{repeat}"
            write_json(args.results / f"{fixture.name}{suffix}.raw.json", raw)
            normalized.update({"elapsed_seconds": elapsed, "measurement": run,
                               "versions": versions, "config": metadata["config"]})
            write_json(args.results / f"{fixture.name}{suffix}.normalized.json", normalized)
            if repeat == 0:
                first_normalized = normalized
            print(json.dumps({"filename": fixture.name, **run}), flush=True)
        warm_runs = [run for run in runs if run["phase"] == "warm"]
        warm_comparable = len({run["status"] for run in warm_runs}) == 1 and all(
            run["status"] != "failed" for run in warm_runs
        )
        summaries.append({"filename": fixture.name, "status": first_normalized["status"],
                          "input_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
                          "runs": runs, "warm_statuses_consistent": warm_comparable,
                          "warm_median_seconds": median(run["elapsed_seconds"] for run in warm_runs) if warm_comparable else None})
        write_json(args.results / "summary.json", {**metadata, "documents": summaries, **peak_rss()})
    parser.close()


if __name__ == "__main__":
    main()
