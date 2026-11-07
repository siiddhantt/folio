CREATE TABLE documents (
    id uuid PRIMARY KEY,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    current_request_id uuid,
    active_revision_id uuid
);

CREATE TABLE file_versions (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id),
    original_filename text NOT NULL,
    media_type text NOT NULL CHECK (media_type = 'application/pdf'),
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    storage_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, id)
);

CREATE TABLE ingestion_requests (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id),
    file_version_id uuid NOT NULL,
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'succeeded', 'failed')),
    authorized_attempt_id uuid,
    requested_config jsonb NOT NULL,
    config_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    FOREIGN KEY (document_id, file_version_id) REFERENCES file_versions(document_id, id),
    UNIQUE (document_id, id),
    UNIQUE (document_id, file_version_id, id)
);

CREATE TABLE processing_attempts (
    id uuid PRIMARY KEY,
    request_id uuid NOT NULL REFERENCES ingestion_requests(id),
    attempt_no integer NOT NULL CHECK (attempt_no > 0),
    state text NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'running', 'succeeded', 'failed')),
    available_at timestamptz NOT NULL DEFAULT now(),
    claim_token uuid,
    lease_expires_at timestamptz,
    started_at timestamptz,
    finished_at timestamptz,
    error_code text,
    error_detail text,
    parser_status text,
    retryable boolean,
    metrics jsonb NOT NULL DEFAULT '{}',
    diagnostic_storage_key text,
    diagnostic_sha256 text,
    transport_job_id text,
    last_dispatched_at timestamptz,
    next_dispatch_at timestamptz NOT NULL DEFAULT now(),
    dispatch_claim_until timestamptz,
    dispatch_count integer NOT NULL DEFAULT 0 CHECK (dispatch_count >= 0),
    terminal_delivery_failures integer NOT NULL DEFAULT 0 CHECK (terminal_delivery_failures >= 0),
    dispatch_error text,
    UNIQUE (request_id, attempt_no),
    UNIQUE (request_id, id),
    CHECK (state <> 'running' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);

ALTER TABLE ingestion_requests ADD FOREIGN KEY (id, authorized_attempt_id)
    REFERENCES processing_attempts(request_id, id);

CREATE TABLE extraction_revisions (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents(id),
    file_version_id uuid NOT NULL,
    request_id uuid NOT NULL UNIQUE,
    publishing_attempt_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    parser_manifest jsonb NOT NULL,
    normalization_version integer NOT NULL,
    raw_storage_key text NOT NULL UNIQUE,
    raw_sha256 text NOT NULL,
    diagnostics jsonb NOT NULL,
    FOREIGN KEY (document_id, file_version_id, request_id)
        REFERENCES ingestion_requests(document_id, file_version_id, id),
    FOREIGN KEY (request_id, publishing_attempt_id) REFERENCES processing_attempts(request_id, id),
    UNIQUE (document_id, id)
);

ALTER TABLE documents ADD FOREIGN KEY (id, current_request_id)
    REFERENCES ingestion_requests(document_id, id);
ALTER TABLE documents ADD FOREIGN KEY (id, active_revision_id)
    REFERENCES extraction_revisions(document_id, id);

CREATE TABLE source_pages (
    revision_id uuid NOT NULL REFERENCES extraction_revisions(id),
    page_no integer NOT NULL CHECK (page_no > 0),
    width_pt double precision CHECK (width_pt > 0),
    height_pt double precision CHECK (height_pt > 0),
    content_observation text NOT NULL
        CHECK (content_observation IN ('content_recovered', 'no_content_recovered')),
    diagnostics jsonb NOT NULL,
    PRIMARY KEY (revision_id, page_no)
);

CREATE TABLE source_elements (
    revision_id uuid NOT NULL REFERENCES extraction_revisions(id),
    element_id text NOT NULL,
    kind text NOT NULL,
    reading_order integer NOT NULL CHECK (reading_order >= 0),
    parent_element_id text,
    text text,
    table_data jsonb,
    provider_ref text,
    PRIMARY KEY (revision_id, element_id),
    FOREIGN KEY (revision_id, parent_element_id)
        REFERENCES source_elements(revision_id, element_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE element_locations (
    revision_id uuid NOT NULL,
    element_id text NOT NULL,
    location_no integer NOT NULL CHECK (location_no >= 0),
    page_no integer NOT NULL,
    char_start integer,
    char_end integer,
    x0 double precision, y0 double precision, x1 double precision, y1 double precision,
    PRIMARY KEY (revision_id, element_id, location_no),
    FOREIGN KEY (revision_id, element_id) REFERENCES source_elements(revision_id, element_id),
    FOREIGN KEY (revision_id, page_no) REFERENCES source_pages(revision_id, page_no),
    CHECK ((char_start IS NULL AND char_end IS NULL)
        OR (char_start IS NOT NULL AND char_end IS NOT NULL AND char_start >= 0 AND char_end >= char_start)),
    CHECK ((x0 IS NULL AND y0 IS NULL AND x1 IS NULL AND y1 IS NULL)
        OR (x0 IS NOT NULL AND y0 IS NOT NULL AND x1 IS NOT NULL AND y1 IS NOT NULL
            AND x0 >= 0 AND y0 >= 0 AND x1 >= x0 AND y1 >= y0))
);

CREATE TABLE api_idempotency (
    scope text NOT NULL,
    operation text NOT NULL,
    key text NOT NULL,
    request_fingerprint text NOT NULL,
    request_id uuid NOT NULL REFERENCES ingestion_requests(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, operation, key)
);

CREATE INDEX requests_file ON ingestion_requests(file_version_id);
CREATE INDEX attempts_pending_dispatch ON processing_attempts(next_dispatch_at, id)
    WHERE state = 'pending';
CREATE INDEX attempts_expired ON processing_attempts(lease_expires_at, id)
    WHERE state = 'running';
CREATE INDEX evidence_reading_order ON source_elements(revision_id, reading_order, element_id);
CREATE INDEX locations_page ON element_locations(revision_id, page_no);
CREATE INDEX receipts_request ON api_idempotency(request_id);
