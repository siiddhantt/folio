def request_status(database, request_id):
    with database.transaction() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        request = connection.execute(
            """SELECT id AS request_id,document_id,file_version_id,state,created_at,finished_at
            FROM ingestion_requests WHERE id=%s""",
            (request_id,),
        ).fetchone()
        if request is None:
            return None
        request["attempts"] = connection.execute(
            """SELECT id,attempt_no,state,available_at,started_at,finished_at,
            error_code,error_detail,
            parser_status,retryable,metrics,dispatch_error,dispatch_count,terminal_delivery_failures
            FROM processing_attempts WHERE request_id=%s ORDER BY attempt_no""",
            (request_id,),
        ).fetchall()
        revision = connection.execute(
            "SELECT id FROM extraction_revisions WHERE request_id=%s", (request_id,)
        ).fetchone()
        request["revision_id"] = revision["id"] if revision else None
        return request


def document_metadata(database, document_id):
    with database.transaction() as connection:
        return connection.execute("SELECT * FROM documents WHERE id=%s", (document_id,)).fetchone()


def original_file(database, document_id):
    with database.transaction() as connection:
        return connection.execute(
            """SELECT f.* FROM documents d JOIN ingestion_requests r ON r.id=d.current_request_id
            JOIN file_versions f ON f.id=r.file_version_id WHERE d.id=%s""",
            (document_id,),
        ).fetchone()


def revision_evidence(database, revision_id, after_order=-1, limit=50):
    with database.transaction() as connection:
        revision = connection.execute(
            """SELECT id AS revision_id,document_id,file_version_id,request_id,created_at,
            parser_manifest,normalization_version,diagnostics
            FROM extraction_revisions WHERE id=%s""",
            (revision_id,),
        ).fetchone()
        if revision is None:
            return None
        revision["pages"] = connection.execute(
            "SELECT page_no,width_pt,height_pt,content_observation,diagnostics FROM source_pages "
            "WHERE revision_id=%s ORDER BY page_no",
            (revision_id,),
        ).fetchall()
        elements = connection.execute(
            """SELECT element_id,kind,reading_order,parent_element_id,text,table_data
            FROM source_elements WHERE revision_id=%s AND reading_order>%s
            ORDER BY reading_order LIMIT %s""",
            (revision_id, after_order, limit + 1),
        ).fetchall()
        revision["next_after_order"] = (
            elements[limit - 1]["reading_order"] if len(elements) > limit else None
        )
        revision["elements"] = elements[:limit]
        locations = connection.execute(
            """SELECT element_id,page_no,char_start,char_end,x0,y0,x1,y1 FROM element_locations
            WHERE revision_id=%s AND element_id=ANY(%s) ORDER BY element_id,location_no""",
            (revision_id, [e["element_id"] for e in elements[:limit]]),
        ).fetchall()
        grouped = {}
        for location in locations:
            grouped.setdefault(location.pop("element_id"), []).append(location)
        for element in revision["elements"]:
            element["locations"] = grouped.get(element["element_id"], [])
        return revision
