CREATE TABLE processing_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id uuid NOT NULL REFERENCES ingestion_requests(id),
    attempt_id uuid NOT NULL,
    name text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    details jsonb NOT NULL DEFAULT '{}',
    FOREIGN KEY (request_id, attempt_id) REFERENCES processing_attempts(request_id, id)
);

CREATE INDEX events_request_order ON processing_events(request_id, id);
