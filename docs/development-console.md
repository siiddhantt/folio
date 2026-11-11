# Development console

The console changes Folio's document-processing controls for experiments on the
local instance. It is available only when development mode is enabled. The
owner selected this behavior on November 11. The implementation and its measured
checks are recorded in [status](status.md).

With development mode enabled, use the settings control beside the theme toggle
or visit `/development/settings`. The browser calls `GET /development/settings`
to load the values and `PUT /development/settings` to save them. The latter sends
the complete typed controls plus the revision it read. Reload discards unsaved
form edits; it does not reset configuration or spending.

## Scope

| Editable | Read-only or environment-managed |
| --- | --- |
| Maximum pages and file bytes | Model and provider |
| Parser timeout within the worker's execution window | Worker job timeout, ownership lease and supervision |
| Automatic summaries for new uploads | Credentials, service URLs, artifact/model paths |
| Summary input/output limits and reasoning effort | Token-count margin, retry policy and spending allowance |

Raising the page limit only changes the page-count check. A larger PDF can still
exceed the parser/job timeout or the summary input allowance. A file's small
byte size does not imply few pages. Folio keeps these limits separate because
they bound different work.

The existing page setting is `FOLIO_MAX_PAGES`, initially 100. The upload screen
checks file size and displays page limits; the worker opens the PDF and counts
pages before Docling extraction/OCR. Its “Parsing started” event currently
includes this preliminary inspection. An immediate `PAGE_LIMIT_EXCEEDED` does
not mean that hundreds of pages were processed.

## A reproducible experiment

Suppose the console shows revision 4 with a two-page limit. Upload a three-page
PDF, then save a three-page limit as revision 5. The first upload retains revision
4 and fails its page check. Upload the PDF again with a new upload intent; it
receives revision 5 and can proceed. The original result remains available for
comparison. This does not rewrite history or automatically retry old work.

Summary settings follow the same rule. Disabling automatic summaries affects new
uploads; it is not a cancellation switch for already accepted work. A document
still parsing keeps the summary policy captured when its upload began.

## Persistence and concurrency

One typed PostgreSQL settings record stores the editable values, revision and
update time. The environment supplies its initial values once. Afterward, saved
values survive service restarts and remain authoritative even if the console is
hidden by disabling development mode. Non-editable settings still come from the
environment.

A save includes the revision shown in the form. If another tab saved first, the
server returns a conflict and the form must reload. This is optimistic concurrency:
the editor does not hold a database lock while a person thinks, but the save
checks that the version is still current.

The database performs that check and update in one statement:
`UPDATE ... WHERE id=true AND revision=<the version you read>`. Two tabs cannot
both successfully replace the same revision. The primary key already indexes the
single settings row; an additional revision index would not help this lookup.
Values use a JSON column with a fixed application schema, not an arbitrary bag
of environment variables. A complete settings save is atomic: readers see either
the old set or the new set, never half of each.

Each upload captures the values once, before multipart spooling. The file-size
checks and saved ingestion/summary policies use that same snapshot. Workers read
the request's saved policy, not whatever the console happens to show later.

An already accepted idempotency key can replay the original file after the byte
limit is lowered. The upload allowance for that replay is at least the stored
original file size. Folio still reads and checks the bytes and filename; knowing
a key never skips identity verification. A fresh key uses the current limit.
An oversized changed file can be rejected before its identity is compared.

The console never resets earlier spending or changes the approved allowance.
Model admission still checks the selected route, tokenizer, context, prices and
remaining funds before inference. Known bills and held amounts remain separate.

The development endpoint is local tooling, not a public administration API.
It is server-gated, excludes credentials, and validates mutation origin/content
and version. Local Docker port binding remains part of the deployment boundary;
this console does not introduce authentication or authorize public exposure.

## Source reading order

1. [Controls and validation](../src/folio/configuration/models.py): the seven
   editable values and constraints the console can check locally.
2. [Persistence and snapshot capture](../src/folio/configuration/store.py): the
   versioned save, read-only spending view and one snapshot per upload.
3. [Upload boundary](../src/folio/ingestion/routes.py), then
   [processing](../src/folio/ingestion/processing.py): where that snapshot enters
   the request and reaches the eventual summary intent.

As an ownership exercise, open two console tabs. Save a change in the first, then
try saving from the second. Find the revision check in the persistence module
that prevents the second tab from silently undoing the first tab's edit.
