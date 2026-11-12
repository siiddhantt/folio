CREATE TABLE conversations (
    id uuid PRIMARY KEY,
    index_id uuid NOT NULL REFERENCES document_indexes(id),
    creation_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(id,index_id)
);

CREATE TABLE conversation_turns (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL,
    index_id uuid NOT NULL,
    sequence integer NOT NULL CHECK(sequence > 0),
    idempotency_key text NOT NULL,
    question text NOT NULL CHECK(length(question) BETWEEN 1 AND 4000),
    policy jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending'
        CHECK(state IN ('pending','running','ready','failed','unavailable')),
    result jsonb,
    query_vector vector(1536),
    input_manifest jsonb,
    error_code text,
    attempt_count integer NOT NULL DEFAULT 0,
    claim_token uuid,
    lease_expires_at timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    next_dispatch_at timestamptz NOT NULL DEFAULT now(),
    transport_job_id text,
    delivery_failures integer NOT NULL DEFAULT 0,
    dispatch_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    UNIQUE(id,index_id),
    UNIQUE(conversation_id,sequence),
    UNIQUE(conversation_id,idempotency_key),
    FOREIGN KEY(conversation_id,index_id) REFERENCES conversations(id,index_id),
    CHECK(state <> 'ready' OR result IS NOT NULL)
);

CREATE TABLE turn_attempts (
    id uuid PRIMARY KEY,
    turn_id uuid NOT NULL REFERENCES conversation_turns(id),
    token uuid NOT NULL,
    attempt_no integer NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_code text,
    failure_diagnostics jsonb,
    UNIQUE(id,turn_id),
    UNIQUE(turn_id,attempt_no)
);

CREATE TABLE turn_invocations (
    id uuid PRIMARY KEY,
    turn_id uuid NOT NULL REFERENCES conversation_turns(id),
    attempt_id uuid NOT NULL,
    stage text NOT NULL CHECK(stage IN ('embedding','answer')),
    reserved_usd numeric NOT NULL CHECK(reserved_usd >= 0),
    reserved_input integer NOT NULL CHECK(reserved_input > 0),
    cost_usd numeric CHECK(cost_usd >= 0),
    billing_state text NOT NULL DEFAULT 'reserved' CHECK(billing_state IN ('reserved','unknown','known')),
    metadata jsonb NOT NULL DEFAULT '{}',
    invoked_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    FOREIGN KEY(attempt_id,turn_id) REFERENCES turn_attempts(id,turn_id),
    UNIQUE(attempt_id,stage)
);

CREATE TABLE turn_evidence (
    turn_id uuid NOT NULL,
    index_id uuid NOT NULL,
    label text NOT NULL,
    rank integer NOT NULL CHECK(rank > 0),
    chunk_ordinal integer NOT NULL,
    distance double precision NOT NULL,
    PRIMARY KEY(turn_id,label),
    UNIQUE(turn_id,rank),
    FOREIGN KEY(turn_id,index_id) REFERENCES conversation_turns(id,index_id),
    FOREIGN KEY(index_id,chunk_ordinal) REFERENCES index_chunks(index_id,ordinal)
);

CREATE INDEX conversations_created ON conversations(created_at DESC,id DESC);
CREATE UNIQUE INDEX one_active_turn ON conversation_turns(conversation_id) WHERE state IN ('pending','running');
CREATE INDEX turns_due ON conversation_turns(next_dispatch_at,id) WHERE state='pending';
CREATE INDEX turns_expired ON conversation_turns(lease_expires_at,id) WHERE state='running';
CREATE INDEX turn_charges ON turn_invocations(turn_id);
