# Understanding Folio's first ingestion slice

Reading guide, November 7, 2026. The source links below follow the implemented and accepted first ingestion slice.
Use [status](status.md) for completed checks and their limits, and [the system design](ingestion-system.md) for the full contract.
Summaries, retrieval and chat remain future work; this guide follows a PDF only as far as inspectable evidence.

**Start with one PDF.** A person uploads a report, receives an identifier, then checks its processing result.
The original bytes, the request to process them, and the extracted evidence are different things.
`D1` identifies the document, `F1` its immutable PDF bytes, `J1` the processing request, and `R1` a published extraction.
A later parser run can produce another extraction from F1; replacement bytes would be a new file version.
The schema supports these distinctions; it does not imply a replacement or version-history feature already exists.

Read the current code in this order:

| File | Question it answers |
| --- | --- |
| [api.py](../src/folio/api.py) | What does HTTP accept, return, and expose for inspection? |
| [acceptance.py](../src/folio/acceptance.py) | When is an upload accepted, and how does replay avoid another document? |
| [storage.py](../src/folio/storage.py) | How are bytes saved under an opaque key and checked against their hash? |
| [database.py](../src/folio/database.py) | Where do connections and transaction lifetimes come from? |
| [migrations](../src/folio/migrations) | Which identities, relationships and ordering constraints does PostgreSQL enforce? |
| [dispatcher.py](../src/folio/dispatcher.py) | How does committed pending work reach RQ, including after a delivery failure? |
| [ownership.py](../src/folio/ownership.py) | Which attempt may run, and which token may change its outcome? |
| [processing.py](../src/folio/processing.py) | How does a worker claim, parse, stage and finish one attempt? |
| [parsing/parser.py](../src/folio/parsing/parser.py) | How does Docling become Folio evidence rather than a schema every caller must know? |
| [publication.py](../src/folio/publication.py), [recovery.py](../src/folio/recovery.py) | Where do success, failure and bounded retry become durable? |
| [queries.py](../src/folio/queries.py) | How do callers inspect consistent status and paginated evidence? |

**A transaction protects a particular boundary.** In the current acceptance code, the PDF is saved first.
HTTP first spools a bounded multipart upload; artifact storage then copies/hash-checks it in chunks. No transaction spans that upload.
One PostgreSQL transaction then creates the document, file version, request, pending attempt and upload receipt.
Atomicity means these database changes commit together or roll back together: a failed receipt insertion must not leave a second accepted document.
The receipt's primary key makes concurrent requests with the same scoped key compete at the database, rather than trusting an earlier application check.
The losing transaction rolls back before comparing the stored fingerprint; changed input returns a conflict.
[PostgreSQL transactions](https://www.postgresql.org/docs/18/tutorial-transactions.html).

That transaction does not include the filesystem or Redis. The file may exist even if the database commit fails.
`storage.py` flushes bytes and finalizes the file; `acceptance.py` preserves it when the commit outcome could be uncertain.
Deleting on every exception could erase the original belonging to a transaction that actually committed.
The dispatcher reads committed work from PostgreSQL, so an API crash before enqueue does not erase the request.
Redis transports work; PostgreSQL records what Folio owes the caller. Moving files to S3 would not combine these commits.
[S3's atomicity is per object key](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel).

**Multiple workers need ownership, not just a queue.** `claim_attempt` uses a short transaction to claim an authorized pending attempt.
A row lock prevents another transaction from changing that same claim at the same time; unrelated jobs can still progress.
Commit the claim before loading models or parsing. Holding a database lock for an entire PDF conversion would keep competitors waiting unnecessarily.
Acquire related locks in a consistent order to reduce deadlocks. Ordinary reads are not all blocked by a row lock.
[PostgreSQL row locking](https://www.postgresql.org/docs/18/explicit-locking.html#LOCKING-ROWS).

The claim also has a token and an expiry time, called a lease. Expiry revokes permission to publish; it does not prove the old process stopped.
Suppose worker A pauses, its lease expires, and recovery authorizes worker B. A might later finish with a perfectly valid-looking result.
`publish` checks the authorized attempt, token and deadline again while holding the appropriate locks; `finish_failure` does the same.
This ownership check is the fence that rejects A's stale write. Failure updates need the same protection.
The migration's unique `extraction_revisions.request_id` is an additional guard against two published revisions for one request.
These rules target one published result per request; they do not promise that parsing executes exactly once.
Dispatch has a separate token: its acknowledgment checks both `dispatch_token` and transport job ID, preventing a delayed dispatcher from rewriting newer bookkeeping.

For dispatchers choosing rows from a shared list, `FOR UPDATE SKIP LOCKED` can let one dispatcher move past work another has claimed.
It is useful for queue-like selection, not a blanket replacement for every by-ID worker claim.
It skips conflicting row locks, not all possible blocking, and does not promise strict first-in-first-out processing.
[PostgreSQL's locking clause](https://www.postgresql.org/docs/18/sql-select.html#SQL-FOR-UPDATE-SHARE).

**Indexes answer access patterns; they do not replace those correctness rules.** Think of an index as an ordered way to find rows without examining every row.
The migration's `evidence_reading_order` index is ordered by `(revision_id, reading_order, element_id)`.
It groups one extraction's evidence together, then orders it by reading position and element ID.
That matches “show the first 50 elements in revision R1.” It can also help a lookup constrained only by revision.
It is not automatically the best index for “find this reading position across every revision.”
Migration 002 also makes `(revision_id, reading_order)` unique, so pagination cannot skip tied reading positions. Index usefulness and uniqueness are separate design questions.

For a B-tree `(a, b, c)`, leading equality conditions and then the first range condition usually narrow the scanned interval most effectively.
Later conditions can still filter inside the index. The order of predicates written in SQL does not reorder the index.
PostgreSQL 18 can use **skip scan** to probe omitted leading values when that is economical, especially with few distinct leading values.
Therefore, “missing the first column makes the index unusable” is too strong; “every column subset is equally efficient” is also wrong.
[Multicolumn indexes and skip scan](https://www.postgresql.org/docs/18/indexes-multicolumn.html).

Do not create every combination of three columns. PostgreSQL can combine separate indexes with bitmap AND/OR, but this adds scans and loses their ordering.
A frequent ordered query may benefit more from one matching composite index. Extra indexes also cost space and write maintenance.
Choose from actual queries and measurements. [Combining indexes](https://www.postgresql.org/docs/18/indexes-bitmap-scans.html).

The current migration also contains two partial indexes, each covering only a useful subset of attempts:

| Index | Ordered columns | Rows included |
| --- | --- | --- |
| `attempts_pending_dispatch` | `next_dispatch_at, id` | `state = 'pending'` |
| `attempts_expired` | `lease_expires_at, id` | `state = 'running'` |

Completed history stays outside these indexes. Time comparisons belong in the query; putting `now()` into the index predicate would violate its immutability requirement.
The planner must also recognize that a query satisfies the partial predicate; a generic `state = $1` plan may not establish that it means pending.
[Partial indexes](https://www.postgresql.org/docs/18/indexes-partial.html), [index expression restrictions](https://www.postgresql.org/docs/18/sql-createindex.html).

A primary key or unique constraint already creates a supporting unique index. Avoid adding an identical index under another name.
A foreign key checks a relationship but does not automatically index the referencing columns.
For example, `source_elements`' primary key supports `(revision_id, element_id)` identity, while its separate reading-order index serves an ordered listing.
[PostgreSQL constraints](https://www.postgresql.org/docs/18/ddl-constraints.html).

**Inspect a real plan.** Run this read-only SQL in `psql` against a migrated local database with published evidence.
It selects the latest revision for convenience; the plan also includes that small selection step.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT element_id, kind, reading_order
FROM source_elements
WHERE revision_id = (
    SELECT id FROM extraction_revisions
    ORDER BY created_at DESC, id DESC
    LIMIT 1
)
ORDER BY reading_order, element_id
LIMIT 50;
```

No result or speedup is assumed here. With no published revision it returns no rows, which is not a useful performance experiment.
Compare estimated and actual row counts, index/sequential scans, sorting and buffers read. A sequential scan on a tiny table can be the right choice.
`ANALYZE` executes the statement; this example deliberately contains only SELECTs. A fast plan does not demonstrate safe concurrent claims.
[Using EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html).

**Scaling spends several budgets.** On one host, additional RQ workers can process additional documents concurrently while sharing the artifact volume.
RQ normally executes one job per worker. More workers also mean more model memory, CPU pressure and simultaneous database activity.
Measure before increasing the initial worker count. [RQ workers](https://python-rq.org/docs/workers/).

`database.py` currently sets a pool maximum of eight connections per Database instance. That is not an application-wide ceiling.
Three concurrently alive processes with one such pool each can allow up to 24 connections, plus migrations, consoles and other direct connections.
Count API processes, dispatchers and workhorses; actual open connections depend on pool demand and lifecycle.
Budget their combined ceiling below PostgreSQL's available slots. [Psycopg pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [PostgreSQL connection limits](https://www.postgresql.org/docs/18/runtime-config-connection.html).

Across hosts, a local named volume is not automatically shared. Workers need shared artifact storage such as S3, plus network/access and failure handling.
Adding an S3 implementation is a deployment change to test, not evidence that the local system already supports multiple hosts.
[Docker volume lifecycle and sharing](https://docs.docker.com/engine/storage/volumes/).

File/page limits and worker time/memory bounds limit individual jobs. They do not bound an indefinitely growing queue or disk usage.
Backpressure means deliberately slowing or rejecting new admissions when capacity is exhausted; admission quotas and full storage budgets still need explicit behavior.
Deletion and online artifact cleanup also remain separate work. Removing a database row alone does not remove its bytes or settle references from old evidence.
The initial cleanup contract uses maintenance with artifact writers stopped; age alone does not prove an unreferenced file is abandoned.

| Interview prompt | Answer to defend using Folio |
| --- | --- |
| Why keep PostgreSQL intent when Redis has the task? | Enqueue and database commit are separate; committed pending work allows recovery from that gap. |
| Why check a token after a worker already claimed the job? | Its permission may expire during parsing, and a replacement worker may now own publication. |
| Why not index every combination? | Indexes should support frequent access/order patterns; redundant indexes add maintenance without necessarily improving those queries. |

Owner exercises: trace one upload from `api.py` to the commit and point out the first operation outside PostgreSQL; explain why changed input with the same key conflicts.
Then run the SELECT plan on real evidence and explain one chosen scan. Follow the expired-worker example through `owns`, `recover_expired` and the [recovery tests](../tests/test_recovery.py).
Compare the [HTTP smoke](../scripts/smoke.py), [operational recovery exercise](../scripts/check_recovery.py) and [native supervision probe](../tests/test_supervision.py) with the bounded results in [status](status.md); do not assume every crash interleaving was tested.
The goal is to locate the responsible code, predict one failure and explain the tradeoff, without memorizing Docling or PostgreSQL internals.
