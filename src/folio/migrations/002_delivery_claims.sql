ALTER TABLE processing_attempts ADD COLUMN dispatch_token uuid;
ALTER TABLE source_elements ADD UNIQUE (revision_id, reading_order);
