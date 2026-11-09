from uuid import uuid4

from psycopg.types.json import Jsonb

from folio.observability import record_event
from folio.ownership import locked_attempt, owns


def publish(database, claim, extraction, raw_artifact):
    if not extraction.pages or not extraction.elements:
        raise ValueError("Cannot publish evidence without pages and source elements")
    pages = {page.page_no for page in extraction.pages}
    for element in extraction.elements:
        if not element.locations or any(
            location.page_no not in pages for location in element.locations
        ):
            raise ValueError("Every source element must resolve to a physical page")
        cells = (element.table_data or {}).get("cells", [])
        if not (element.text or "").strip() and not any(
            cell.get("text", "").strip() for cell in cells
        ):
            raise ValueError("Source evidence must contain usable text or table cells")
    with locked_attempt(database, claim.request_id, claim.attempt_id) as (conn, request, attempt):
        if not owns(conn, request, attempt, claim.token):
            return None
        revision_id = uuid4()
        conn.execute(
            """INSERT INTO extraction_revisions
            (id,document_id,file_version_id,request_id,publishing_attempt_id,parser_manifest,
             normalization_version,raw_storage_key,raw_sha256,diagnostics)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                revision_id,
                request["document_id"],
                request["file_version_id"],
                request["id"],
                attempt["id"],
                Jsonb(extraction.parser_manifest),
                claim.config["normalization_version"],
                raw_artifact.key,
                raw_artifact.sha256,
                Jsonb(extraction.diagnostics),
            ),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO source_pages VALUES (%s,%s,%s,%s,%s,%s)",
                [
                    (
                        revision_id,
                        p.page_no,
                        p.width_pt,
                        p.height_pt,
                        p.content_observation,
                        Jsonb(p.diagnostics),
                    )
                    for p in extraction.pages
                ],
            )
            cursor.executemany(
                "INSERT INTO source_elements VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    (
                        revision_id,
                        e.element_id,
                        e.kind,
                        e.reading_order,
                        e.parent_element_id,
                        e.text,
                        Jsonb(e.table_data) if e.table_data is not None else None,
                        e.provider_ref,
                    )
                    for e in extraction.elements
                ],
            )
            cursor.executemany(
                "INSERT INTO element_locations VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    (
                        revision_id,
                        e.element_id,
                        number,
                        loc.page_no,
                        loc.char_start,
                        loc.char_end,
                        loc.x0,
                        loc.y0,
                        loc.x1,
                        loc.y1,
                    )
                    for e in extraction.elements
                    for number, loc in enumerate(e.locations)
                ],
            )
        conn.execute(
            """UPDATE processing_attempts SET state='succeeded',finished_at=clock_timestamp(),
            parser_status=%s,metrics=%s WHERE id=%s""",
            (
                extraction.parser_status,
                Jsonb({"parser_duration_seconds": extraction.duration_seconds}),
                attempt["id"],
            ),
        )
        conn.execute(
            "UPDATE ingestion_requests SET state='succeeded',finished_at=clock_timestamp() "
            "WHERE id=%s",
            (request["id"],),
        )
        conn.execute(
            "UPDATE documents SET active_revision_id=%s WHERE id=%s AND current_request_id=%s",
            (revision_id, request["document_id"], request["id"]),
        )
        record_event(conn, request["id"], attempt["id"], "published", revision_id=str(revision_id))
        return revision_id
