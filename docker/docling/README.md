# Docling base image

Folio's production worker extends `folio-docling:2.148.0`. This image supplies
Docling, CPU PyTorch, English Tesseract OCR, and the layout and table models.
Folio's extraction implementation lives in
[`src/folio/ingestion/parsing`](../../src/folio/ingestion/parsing), outside this
build context.

Build from the repository root with a Docker Linux daemon supporting amd64:

```sh
docker build --platform linux/amd64 -t folio-docling:2.148.0 docker/docling
```

The build needs network access to download packages and model assets. It requires
no inference API key. The worker image adds Folio's application dependencies;
follow the [repository setup](../../README.md) after building this base.

## Models and offline operation

`run.py --prefetch --models /models` downloads the two pinned model revisions
during the build. `/models/manifest.json` records their revisions, licenses,
relative paths, sizes, and SHA-256 hashes. Model cards and license files stay
with the assets. Folio reads this manifest into each extraction's provenance.

The final image sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Parsing uses
the bundled `/models` tree and local Tesseract executable. Keep that tree and its
manifest together; changing model versions also requires reviewing Folio's
parser configuration and its recorded evidence.

## Dependencies and licenses

The Dockerfile pins the Python base digest, CPU wheel hashes, Docling 2.148.0,
Transformers 5.20.2, and model revisions. `constraints.txt` comes from Docling's
upstream `v2.148.0` lock; it constrains dependencies without installing the whole
list. Debian packages can change between builds, and Python wheels are not all
hash-locked. Retain the actual image digest and generated `pip-freeze.txt` and
`dpkg-versions.txt` when recording a result.

Docling code is MIT. The [Heron model](https://huggingface.co/docling-project/docling-layout-heron)
is Apache-2.0; the [TableFormer repository](https://huggingface.co/docling-project/docling-models)
declares Apache-2.0 and CDLA-Permissive-2.0. Tesseract and its English data retain
their package copyright files inside the image.

## Retained comparison adapter

`run.py` also contains the standalone extraction measurement adapter, and
`test_normalization.py` checks its output contract. The Dockerfile runs those
checks before fetching models. The adapter retains source locations and parser
diagnostics; a successful conversion does not prove complete extraction.

The base image's default entrypoint runs that adapter. `docker/worker.Dockerfile`
replaces it with Folio's worker, which uses the application parser. The adapter's
PDF/DOCX comparison support does not expand Folio's accepted PDF-only input scope.
