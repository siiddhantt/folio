CREATE TABLE runtime_configuration (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    values jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
