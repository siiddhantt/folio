# Folio document interface

Accepted November 9: a minimal local upload and document-detail interface, with
React, TypeScript and Vite, light/dark appearance, source inspection and a
development-only view of real processing activity.

## One useful outcome

A person uploads their PDF, follows its actual processing outcome, inspects
recovered text/tables and known gaps, and opens the original. The document URL
survives refresh. No sample documents or scenario switches are built into the
runtime. Controlled files remain test inputs only.

The HTTP API remains the authority. Use the existing upload, document, status,
evidence and original routes behind a same-origin `/api` proxy. Poll open
requests; stop on terminal outcomes and cancel obsolete requests on navigation.
Connection errors do not change ingestion state. Reuse an idempotency key when
retrying an uncertain upload of the same selected file; deliberate new uploads
get new keys. A pending retry must not appear as a terminal failure.

Source content is rendered as text, never executable HTML. Tables retain row,
column, header and span relationships. Evidence pagination preserves order.
Source-page links open the original. The November 11 revision replaces native
embedded PDF chrome with one locally rendered page and explicit open/download
fallbacks. Preview loads after usable extraction; open and
download links remain available while pending or failed. This avoids automatically
activating an encrypted PDF's native password viewer before input validation.
Evidence availability does not imply full coverage or
that summary/chat capabilities exist.

Accepted November 11: keep Content and Original side by side on desktop; switch
between them with tabs on narrow screens. A citation selects the original page
and its tab. Preserve loaded content and reading position across tab switches.
Keep status separate from document actions. Partial extraction uses a compact
recovered-page count, truthful reason where known, grouped missing-page ranges,
and bounded expandable details. See D17 for dependency and verification choices.

## Small UI foundation

React/Vite was selected over server-rendered templates for the later interactive
source/chat workflow while retaining the existing Python API. No server rendering
or second application backend is needed now. Use a small router, typed HTTP
functions, feature components and a few reused controls. Extract abstractions
when there is actual reuse; do not create a broad component framework.

The November 13 conversation polish extends this foundation with shared
Radix-backed Select, menu and sheet composition where used. Answer formatting
uses pinned `react-markdown` and `remark-gfm`, without raw HTML or remote images.
The [conversation reading contract](conversations.md#reading-answers--november-13)
describes the composer and cited-passage drawer. Model/provider output remains
untrusted data; Markdown support does not change source validation.

The owner selected a restrained shadcn foundation after reviewing the first UI.
Use neutral light/dark surfaces, one locally bundled DM Sans family, compact
controls and a document/source split with page references in the content gutter.
Remove promotional headings, taglines, numbered stages, footers and repeated
reassurance. Show explanatory copy when it identifies an actual limitation or
helps a person take an action. Preserve accessible names and factual warnings.

Button, Badge, Alert and Separator source was generated from the official
[shadcn registry](https://ui.shadcn.com/docs/installation/vite) using CLI 4.23.0
on November 9. Components live in `web/src/components/ui`; their styles use
Tailwind 4.3.5 with local neutral tokens. The shared `cn` helper combines class
names through clsx/tailwind-merge. Source is checked in and the MIT notice is in
`web/public/licenses/shadcn.txt`; the font notice is alongside it. Changes to the
component source are reviewed like application code; there are no automatic
registry updates. Layout CSS belongs to the relevant feature. Avoid decorative
dashboards and empty future-feature controls.

## Development inspection

The November 11 revision moves inspection into an Activity side panel. Opening
it does not move the reading layout; closing restores focus to its trigger.
The panel has its own bounded scroll area, an accessible title and Escape
dismissal. Detailed identifiers/settings remain secondary to the event timeline.

An explicit server setting gates the inspection endpoint and UI. It is disabled
by default and is not authentication. Inspect only on the existing localhost
deployment boundary. The view exposes source identity, safe configuration,
attempts and genuinely observed stage events; it never reveals credentials,
claim tokens, raw document text in telemetry or machine paths.

Persist lifecycle events beside authoritative transitions. Additional observed
stages are fenced by current ownership and do not change retry authority. A
killed process may leave a started stage without a completion. Older documents
can have no stage history. Do not manufacture timestamps, percentage completion,
per-page parser progress or an exact crash time. PostgreSQL records the document
outcome; an RQ handler returning normally is not proof of successful extraction.

## Verification and owner checkpoint

Accepted test interfaces: the real browser upload-to-evidence journey and the
existing HTTP/persistence/processing contracts. Browser checks cover visible
behavior and use the actual API/worker/parser for the core journey. API checks
cover gating, safe diagnostics and source response behavior. Keep one behavior
under implementation at a time, observing a failing check before implementing it.

The owner walkthrough follows a real chosen PDF from browser Network requests
through persisted attempt/stage history to source evidence. Recovery can be
demonstrated by stopping/restarting local infrastructure with ordinary commands;
no product feature simulates success or injects fictional failures. Explain why
acceptance, execution and publication are separate boundaries.

The November 11 [development console](development-console.md) adds persisted
processing controls beside the theme toggle. It applies only to new uploads;
per-document generation controls remain deferred.

Conversation entry, history and controls are implemented separately; see the
[conversation contract](conversations.md). Runs lists accepted uploads. A richer
searchable document library, full tracing collectors, live OCR percentages,
streaming updates, authentication and public hosting remain deferred.
