ALTER TABLE conversations
    ADD COLUMN title text CHECK(length(title) BETWEEN 1 AND 60),
    ADD COLUMN title_source text CHECK(title_source IN ('generated','manual')),
    ADD COLUMN title_version integer NOT NULL DEFAULT 0 CHECK(title_version >= 0),
    ADD COLUMN deleted_at timestamptz,
    ADD CONSTRAINT conversation_title_source CHECK((title IS NULL) = (title_source IS NULL));
