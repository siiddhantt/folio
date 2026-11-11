# Processing runs

Runs in the header opens processing history. It is separate from future
conversation history: an upload is work performed on a PDF, while a conversation
will contain a person's questions and answers.

One accepted upload creates one row. Replaying the same upload receipt does not
create another row; a deliberate new upload does. A failed worker that retries
adds an attempt inside the same row. Extraction and summary have separate states:
a readable PDF with a failed summary still has usable evidence.

## Follow one upload

1. Upload a PDF. The acceptance transaction saves the document, original-file
   record, request, captured configuration and first processing attempt together.
2. Open Runs. Its read-only query returns a small page of requests and their
   extraction/summary states. Reading history never schedules processing.
3. Open the document, then Activity. Recorded events explain the observed order;
   attempts show authoritative execution state, timing, failure and configuration.
   Summary execution includes its own attempts and usage.
4. Reload or restart the application. PostgreSQL retains those records; the
   artifact volume retains the original and extracted content. Removing these
   volumes removes the data. Persistence is not a backup.

For example, a readable report can have Extraction **Evidence available** and
Summary **Failed**. If the model request timed out after invocation, its bill may
be unknown. Activity shows the held reservation separately from a known cost;
it must not present an unknown bill as zero. A failure before any provider call
is different and is shown as not invoked.

Saved exception diagnostics contain only the exception type, optional operating
system error number and bounded Folio module/function/line locations. They help
find the relevant code without retaining arbitrary exception messages, local
variables, full paths or document text. They are visible only through the
development inspection route. Older failures may have no saved exception details.
The absence of a stack location is not evidence that no failure occurred.

## Why the history index exists

The list asks PostgreSQL for requests ordered by `(created_at DESC, id DESC)`.
The matching index lets it walk that order and stop after one page. The ID breaks
ties when requests share a timestamp. The next-page cursor carries the last
time/ID pair, so a new upload does not shift older rows between pages.

This does not justify an index for every combination of fields. Each index costs
space and work on writes. Add another only for a real query, then inspect its
plan with `EXPLAIN (ANALYZE, BUFFERS)` on representative data. Small tables may
correctly use a sequential scan because reading the whole table is cheaper.

Owner exercise: upload the same PDF twice deliberately. Find two rows, open one,
and locate its request ID and captured settings. Then compare an encrypted PDF:
its original remains downloadable, extraction fails, and no summary is scheduled.

Retrieval, conversation history, reprocessing and deletion are separate slices.
If document replacement is introduced, opening an old run must use that run's
file and revision rather than silently opening the document's latest version.

## Source reading order

1. [RunsPage](../web/src/runs/RunsPage.tsx) and
   [useRuns](../web/src/runs/useRuns.ts): bounded pages, separate state labels and
   polling while work is active.
2. [history](../src/folio/ingestion/history.py) and
   [migration 007](../src/folio/migrations/007_history.sql): the actual query,
   cursor and index. Change listing behavior here rather than assembling it in
   the browser from every document's details.
3. [development inspection](../src/folio/ingestion/development.py) and
   [summary inspection](../src/folio/summaries/inspection.py): consistent database
   snapshots and small safe projections for Activity.
4. [observability](../src/folio/observability.py), ingestion
   [recovery](../src/folio/ingestion/recovery.py) and summary
   [lifecycle](../src/folio/summaries/lifecycle.py): one safe exception extractor,
   saved with the outcome only while the worker still owns the attempt.

The last ownership check matters if two workers overlap. An expired worker may
return after its replacement has started; it cannot attach an obsolete error or
replace the newer result. A transaction makes the failed state and its captured
diagnostics become visible together, rather than exposing half an update.
