CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_indexes (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL UNIQUE,
    document_id uuid NOT NULL,
    policy jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending','running','ready','failed','unavailable')),
    manifest jsonb,
    chunk_count integer CHECK (chunk_count > 0),
    attempt_count integer NOT NULL DEFAULT 0,
    failures integer NOT NULL DEFAULT 0,
    claim_token uuid,
    lease_expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    next_dispatch_at timestamptz NOT NULL DEFAULT now(),
    transport_job_id text,
    dispatch_error text,
    delivery_failures integer NOT NULL DEFAULT 0,
    error_code text,
    UNIQUE (id,revision_id),
    FOREIGN KEY (document_id,revision_id) REFERENCES extraction_revisions(document_id,id)
);

CREATE TABLE index_chunks (
    index_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    batch_no integer NOT NULL CHECK (batch_no > 0),
    text text NOT NULL CHECK (length(text) > 0),
    tokens integer NOT NULL CHECK (tokens > 0),
    sha256 text NOT NULL CHECK (length(sha256)=64),
    embedding vector(1536),
    PRIMARY KEY (index_id,ordinal),
    UNIQUE (index_id,revision_id,ordinal),
    FOREIGN KEY (index_id,revision_id) REFERENCES document_indexes(id,revision_id)
);

CREATE TABLE chunk_sources (
    index_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    chunk_ordinal integer NOT NULL,
    source_order integer NOT NULL,
    element_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('body','context')),
    PRIMARY KEY (index_id,chunk_ordinal,element_id),
    FOREIGN KEY (index_id,revision_id,chunk_ordinal)
        REFERENCES index_chunks(index_id,revision_id,ordinal),
    FOREIGN KEY (revision_id,element_id) REFERENCES source_elements(revision_id,element_id)
);

CREATE TABLE indexing_attempts (
    id uuid PRIMARY KEY,
    index_id uuid NOT NULL REFERENCES document_indexes(id),
    attempt_no integer NOT NULL,
    token uuid NOT NULL,
    batch_no integer,
    state text NOT NULL DEFAULT 'running' CHECK (state IN ('running','succeeded','failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_code text,
    failure_diagnostics jsonb,
    UNIQUE (index_id,attempt_no)
);

CREATE TABLE embedding_invocations (
    id uuid PRIMARY KEY,
    index_id uuid NOT NULL REFERENCES document_indexes(id),
    batch_no integer,
    attempt_id uuid NOT NULL UNIQUE REFERENCES indexing_attempts(id),
    reserved_usd numeric(20,12) NOT NULL DEFAULT 0 CHECK (reserved_usd >= 0),
    cost_usd numeric(20,12) CHECK (cost_usd >= 0),
    invoked_at timestamptz,
    finished_at timestamptz,
    billing_state text NOT NULL DEFAULT 'none'
        CHECK (billing_state IN ('none','reserved','known','unknown')),
    metadata jsonb NOT NULL DEFAULT '{}'
);

CREATE INDEX indexes_due ON document_indexes(next_dispatch_at,id) WHERE state='pending';
CREATE INDEX indexes_expired ON document_indexes(lease_expires_at,id) WHERE state='running';
CREATE INDEX chunks_batch ON index_chunks(index_id,batch_no,ordinal);
CREATE INDEX embedding_charges ON embedding_invocations(index_id);
