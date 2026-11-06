# Docling measurement adapter

This is an experiment, not Folio's ingestion implementation. It reads only the
named fixtures and never loads a `.env` file, reference answers, or a cloud API.

Build from this folder with `docker build --platform linux/amd64 -t folio-docling:2.148.0 .`.
The build pins the Python base digest, CPU PyTorch wheel
hashes, Docling version, its upstream Linux/Python dependency constraints, and
the two model revisions. Constraints do not install the entire upstream list.
Debian packages use the base image's ordinary mirrors after the initial dated
snapshot mirror repeatedly stalled. The image records all installed Python and
system package versions at build time and runtime; future rebuilds can receive
newer Debian packages. Retain the actual image used for this comparison.
Top-level Python dependencies are version-pinned, but their downloaded wheels
are not all hash-locked; retain the image digest and `environment.json` when
reporting results. No image build or extraction result is implied by these files.

The comparison image adds one code-only layer from the completed immutable base
to preserve parser diagnostics if artifact export fails. That follow-up runs
both adapter-contract tests without repeating package or model downloads.
The one-off recipe and logs are retained under ignored `tmp/ingestion`; the
reported image ID must be the final derived image. Use `Dockerfile` for a fresh
build elsewhere.

Model downloads run only in the build's `--prefetch` step. The model manifest
records exact revisions and file SHA-256 values. The standard Heron layout
checkpoint is Apache-2.0; the TableFormer repository declares Apache-2.0 and
CDLA-Permissive-2.0. Source cards are included with the model artifacts:

- https://huggingface.co/docling-project/docling-layout-heron
- https://huggingface.co/docling-project/docling-models

Docling code is MIT. The Debian Tesseract executable and English language data
are local; their package versions/copyright files remain inside the image.
OCR uses Tesseract CLI, English, and Docling's selective OCR behavior rather than
forcing OCR over every page. TableFormer accurate mode and the pinned Heron model
run on CPU. Remote services, formula enrichment and picture descriptions are off.

Use the [comparison coordinator](../README.md) for the authoritative sequential
comparison command and shared resource limits. A standalone diagnostic run uses
a read-only fixture mount, writable result mount, no network, and matching
limits (substitute real paths):

```sh
docker run --rm --network none --cpus 4 --memory 6g --memory-swap 6g \
  --mount type=bind,src=/absolute/fixtures,dst=/fixtures,readonly \
  --mount type=bind,src=/absolute/results,dst=/results \
  folio-docling:2.148.0 --fixtures /fixtures --results /results
```

Each file gets `docling/<filename>/run-{1,2,3}/{raw,normalized,conversion}.json`.
`raw.json` is the unflattened DoclingDocument export, or null when conversion
raised before any usable export. `conversion.json` retains parser status,
diagnostics, confidence and timing fields. Nonfinite confidence values become
JSON null, meaning unavailable, not zero. `normalized.json` retains text-item
source spans and table cell structure without claiming semantic correctness.
`environment.json` records actual configuration, versions and models;
`summary.json` is updated after each completed run.

One process and converter are reused. The first successful pipeline use includes
lazy model loading. Repeats reuse that process, but a failure before initialization
does not warm the model. The recorded `same_process_warm` label means reused
process only; first format occurrence is also flagged, without claiming that
pipeline initialization succeeded. Conversion
wall time excludes imports/converter construction, downloads, hashing and output
serialization. CPU threads are limited to one; files run serially. The 120-second
Docling document timeout can produce partial output, but is not an OS-level kill
guarantee for native code. Apply a container-level timeout from the coordinator.

`ru_maxrss` values are cumulative Linux high-water marks for the process and its
children, not per-file peaks or container-wide memory. Measure the container's
cgroup memory separately. For a native crash or OOM, the coordinator should record
the exit and rerun one fixture in a fresh container (`--files file.pdf`). Never
turn a missing artifact into a fabricated parser failure or successful result.

The table source is table-level provenance; individual cells retain only the
provenance supplied by Docling. DOCX items without page provenance do not receive
invented physical pages. Table text is kept in `tables`, not inserted into the
convenience `text` field. Successful return is not proof of complete coverage.
