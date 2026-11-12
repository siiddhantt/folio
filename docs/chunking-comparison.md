# Chunking comparison

Observed November 12, 2026, before choosing the application policy. The owner
subsequently selected Docling HybridChunker with peer merging and heading
preservation at an initial 512-token ceiling. The production implementation and
contract tests now replace the temporary comparison scripts; generated review
artifacts remain local and ignored.

Input: [FEMA NFIP Dwelling Form, October 2021](https://www.fema.gov/sites/default/files/documents/fema_F-122-Dwelling-SFIP_2021.pdf),
32 physical pages, SHA-256
`4e91d6417cba13c18d4402083a0c02811da8264be6fcb8557c6afa4f8b6e2e74`.
The saved extraction was reused without parsing, uploads or paid calls.
Runtime: Docling 2.148.0, docling-core 2.106.0, tiktoken 0.14.0.
No tables were extracted; this comparison does not validate table chunking.

| Mode | Chunks | Submitted-text tokens | Largest chunk | Body source items omitted |
| --- | ---: | ---: | ---: | ---: |
| Whole-paragraph baseline | 31 | 14,929 | 512 | 0 |
| Docling, unmerged | 151 | 17,025 | 489 | 0 |
| Docling, merged | 62 | 16,346 | 494 | 0 |

The baseline packed whole body text elements without repeated headings or
overlap; it omitted separate list markers and did not serialize tables. Docling
used its structural serializer and `cl100k_base`, counting repeated heading
context within the ceiling. Token totals therefore differ for more than one
reason. A single warm comparison took about 0.04/0.15/0.15 seconds, excluding
loading and parsing; this is not a capacity benchmark.

Default Docling output omitted five heading items. A failing contract test
reproduced the omission; `always_emit_headings=True` preserved them. All final
modes link the 569 body source items. The 64 outside-body items are inventoried
separately: 60 footers, two headers and two text items. Source-identity coverage
does not prove complete character preservation or semantic quality.

Concrete observations:

- Unmerged chunk 27 contains the complete garage clause in 80 tokens. Body `e89`
  and context `e84` refer to physical page 5. Its limit, coverage reduction and
  exclusions stay together. Merged chunk 10 retains it with neighbouring text
  across pages 5–6 in 478 tokens.
- Unmerged chunks 19–20 separate the mudflow definition across physical pages
  4–5. Merged chunk 7 joins it with neighbouring definitions in 490 tokens;
  sources `e63` and `e66` preserve both pages.
- Merged chunk 59 still contains an isolated 14-token continuation on page 32
  classified upstream as a heading. Keeping it prevents silent omission but
  does not repair the semantic structure.
- The stored page-2 no-content observation remains visible. That page was
  visually blank; Folio does not infer that every missing page is blank.

The temporary review displayed full text, exclusions and whole-element page
links. Browser inspection checked desktop and narrow layouts. Six initial
offline checks and independent review covered the comparison; production tests
now additionally cover literal tokenizer-control text and strict source mapping.
Locations identify original elements, not exact highlights within split chunks.

Read [chunking.py](../src/folio/indexing/chunking.py) and
[test_chunking.py](../tests/test_chunking.py) for the maintained behavior.
The [indexing guide](indexing.md) explains persisted chunks, inspection routes
and verification. Retrieval and answer quality still need separate evaluation.
