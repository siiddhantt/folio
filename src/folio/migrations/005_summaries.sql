CREATE TABLE summary_runs (
    id uuid PRIMARY KEY,
    revision_id uuid NOT NULL UNIQUE,
    document_id uuid NOT NULL REFERENCES documents(id),
    policy jsonb NOT NULL,
    state text NOT NULL CHECK (state IN ('pending','running','ready','unavailable','failed')),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0 AND attempt_count <= 2),
    claim_token uuid,
    lease_expires_at timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    next_dispatch_at timestamptz NOT NULL DEFAULT now(),
    dispatch_token uuid,
    dispatch_claim_until timestamptz,
    transport_job_id text,
    delivery_failures integer NOT NULL DEFAULT 0 CHECK (delivery_failures >= 0),
    dispatch_error text,
    input_manifest jsonb,
    result jsonb,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    FOREIGN KEY (document_id,revision_id) REFERENCES extraction_revisions(document_id,id),
    CHECK (state <> 'running' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
    CHECK (state <> 'ready' OR result IS NOT NULL)
);

CREATE TABLE summary_attempts (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES summary_runs(id),
    attempt_no integer NOT NULL CHECK (attempt_no > 0 AND attempt_no <= 2),
    claim_token uuid NOT NULL,
    invoked_at timestamptz,
    reserved_usd numeric NOT NULL DEFAULT 0 CHECK (reserved_usd >= 0),
    cost_usd numeric CHECK (cost_usd >= 0),
    billing_state text NOT NULL DEFAULT 'not_invoked'
        CHECK (billing_state IN ('not_invoked','reserved','known','unknown')),
    response_id text,
    usage jsonb NOT NULL DEFAULT '{}',
    error_code text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (run_id,attempt_no)
);

CREATE TABLE summary_budget_account (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    budget_usd numeric NOT NULL CHECK (budget_usd > 0)
);

CREATE INDEX summaries_pending ON summary_runs(next_dispatch_at,id) WHERE state='pending';
CREATE INDEX summaries_expired ON summary_runs(lease_expires_at,id) WHERE state='running';
CREATE INDEX summaries_document ON summary_runs(document_id);
