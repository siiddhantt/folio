# Synthetic PDFs

These PDFs contain invented facts and were generated for Folio. They contain no
user documents. The generation source is
[`generate.py`](generate.py).
The small committed inputs let tests run without requiring a renderer or fixture
generation before every check.

- `text.pdf`: three physical pages; revenue USD 125,000 on page 2.
- `table.pdf`: ruled and borderless department/year tables; Operations has 19 in 2026.
- `scanned.pdf`: a rasterized English renewal notice; September 30, 2027.
- `mixed.pdf`: native text, the scanned notice, then a deliberately blank page.
- `damaged.pdf`: an unsupported content-stream filter on page 2; CEDAR-17 and
  MAPLE-42 remain on the neighboring pages. Empty extraction cannot identify its cause.
- `encrypted.pdf`: a password-protected copy of `text.pdf`, made with pypdf.
  Its test password is `fixture-password`; no application credential is involved.

The generator also creates a DOCX for the earlier comparison. DOCX is not an
accepted application input. Expected facts are asserted independently in parser
tests and the HTTP smoke check; these small inputs are not a general accuracy benchmark.

## Regenerate for inspection

Use Python 3.12 and Poppler's `pdftoppm` on PATH (or pass its full path with
`--pdftoppm`). From the repository root, install optional generator dependencies
in an isolated uv environment and write to an ignored directory:

```sh
uv run --with reportlab --with pypdf --with python-docx python tests/fixtures/generate.py --output .local/fixture-regeneration
```

The output separates inputs, reference facts/hashes and page previews. Review
changes before replacing committed inputs. The encrypted fixture was derived
separately from `text.pdf` using `PdfWriter.encrypt("fixture-password")`;
the generator produces the other five PDFs and the comparison DOCX.
