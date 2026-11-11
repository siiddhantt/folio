CREATE INDEX requests_history ON ingestion_requests (created_at DESC,id DESC);

ALTER TABLE processing_attempts ADD COLUMN failure_diagnostics jsonb;
ALTER TABLE summary_attempts ADD COLUMN failure_diagnostics jsonb;
