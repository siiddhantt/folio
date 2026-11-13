CREATE TABLE conversation_memories (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL,
    index_id uuid NOT NULL,
    predecessor_id uuid,
    covered_through integer NOT NULL CHECK(covered_through > 0),
    input jsonb NOT NULL,
    input_sha256 text NOT NULL CHECK(length(input_sha256) = 64),
    source_tokens integer NOT NULL CHECK(source_tokens > 0),
    policy jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','ready','failed','unavailable')),
    foreground boolean NOT NULL DEFAULT false,
    deferred_reason text,
    result jsonb,
    result_tokens integer,
    input_manifest jsonb,
    error_code text,
    attempt_count integer NOT NULL DEFAULT 0,
    preflight_failures integer NOT NULL DEFAULT 0,
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
    UNIQUE(id,conversation_id,index_id),
    UNIQUE NULLS NOT DISTINCT(conversation_id,predecessor_id,covered_through),
    FOREIGN KEY(conversation_id,index_id) REFERENCES conversations(id,index_id),
    FOREIGN KEY(predecessor_id,conversation_id,index_id) REFERENCES conversation_memories(id,conversation_id,index_id),
    CHECK(state <> 'ready' OR (result IS NOT NULL AND result_tokens > 0))
);

CREATE TABLE memory_attempts (
    id uuid PRIMARY KEY,
    memory_id uuid NOT NULL REFERENCES conversation_memories(id),
    attempt_no integer NOT NULL,
    token uuid NOT NULL,
    reserved_usd numeric NOT NULL CHECK(reserved_usd >= 0),
    reserved_input integer NOT NULL CHECK(reserved_input > 0),
    cost_usd numeric CHECK(cost_usd >= 0),
    billing_state text NOT NULL DEFAULT 'reserved' CHECK(billing_state IN ('reserved','unknown','known')),
    metadata jsonb NOT NULL DEFAULT '{}',
    invoked_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    error_code text,
    failure_diagnostics jsonb,
    UNIQUE(memory_id,attempt_no)
);

ALTER TABLE conversation_turns
    ADD COLUMN memory_check_needed boolean NOT NULL DEFAULT false,
    ADD COLUMN memory_dependency_id uuid,
    ADD COLUMN context_deadline timestamptz,
    ADD CONSTRAINT turn_memory_scope FOREIGN KEY(memory_dependency_id,conversation_id,index_id)
        REFERENCES conversation_memories(id,conversation_id,index_id);

CREATE INDEX turns_memory_check ON conversation_turns(conversation_id,sequence) WHERE memory_check_needed;
CREATE UNIQUE INDEX one_active_memory ON conversation_memories(conversation_id) WHERE state IN ('pending','running');
CREATE INDEX memories_ready ON conversation_memories(conversation_id,covered_through DESC) WHERE state='ready';
CREATE INDEX memories_due ON conversation_memories(next_dispatch_at,id) WHERE state='pending' AND deferred_reason IS NULL;
CREATE INDEX memories_expired ON conversation_memories(lease_expires_at,id) WHERE state='running';
