# Folio status

Updated: 2026-11-06

## Accepted direction

- Product name: Folio.
- Public source development is acceptable. Hosting a public service is a separate decision.
- Use OpenRouter as the initial API gateway. GPT-6 Luna is a preferred evaluation candidate; exact model choice and live-call budgets remain open.
- Preserve user ownership through explanations, staged architectural decisions, and bounded agent delegation.
- Implement small vertical slices with behavior tests written first.
- Maintain reviewed, pinned skills and durable repository guidance.
- General-purpose document assistance, using facts in reports/documents as initial examples rather than a domain restriction.
- Commentless, Git-ignored local `.env` with a safe configuration template.
- PDFs with native text and English OCR, using Docling; one selected PDF per conversation. DOCX and other formats are deferred.
- Configurable generation model and token budgets, with model-specific validation and quality checks when values change.
- Preserve usable partial extraction with explicit coverage warnings in document results, summaries, and answers.
- Local Docker development from the start; hosting remains a separate decision.
- Select ingestion capabilities from observed source preservation, diagnostics, and local resource use; the Docling/LiteParse comparison is complete.

## Completed

- Created product-focused agent instructions, an initial requirements agreement, a staged decision guide, and an AI-use record.
- Accounted for document processing, conversations, persistence, monitoring, documentation, demonstrations, and optional capabilities in the requirements.
- Identified the difference between required PostgreSQL storage and the open retrieval-engine choice.
- Installed and verified the selected skills and their provenance; see `docs/skills.md`.
- Created a commentless configuration template. No usable credential is stored in the repository.
- Published the initial source and documentation at [siiddhantt/folio](https://github.com/siiddhantt/folio).
- Checked primary technical documentation and read practitioner guidance directly; the decision guide records the relevant sources and limits of the evidence.
- Verified documentation links, requirement-ledger coverage, excluded local data/secrets, and installed skill integrity. No application test results are claimed.
- Verified local credential presence, Git exclusion, and successful OpenRouter authentication using a read-only metadata request. No inference request was made.
- Ran the approved offline Docker comparison: six identical synthetic fixtures, three attempts per parser, matching container limits. Independent output review found correct facts/OCR in both engines, stronger table structure in Docling, and undetected corruption in both. See `docs/ingestion.md` for measured time/memory and limitations.
- Preserved parser diagnostics across adapter export failures with an observed failing-then-passing artifact test. No application correctness claim follows from the experiment checks.

## In progress

- Live model quality, request budgets, and runtime configuration remain unverified. Successful credential authentication does not establish model quality or an agreed application spending budget.
- Docling and PDFs with English OCR are selected. The detailed source contract, table behavior, encrypted-file policy, input/resource limits, and representative OCR quality checks remain open; DOCX is deferred.

## Next decision

Define the source/evidence contract for the accepted Docling/PDF/English-OCR scope. Then settle input limits, grounded-answer behavior, processing-state/recovery details, and queue integration. Partial-content availability and local Docker operation are accepted.

Recommendations not marked accepted in the decision guide remain proposals. No application implementation has begun.

## Handoff discipline

Record accepted decisions, evidence, checks actually run, and the next unresolved question here after each meaningful increment. Never replace unknowns with assumed acceptance.
