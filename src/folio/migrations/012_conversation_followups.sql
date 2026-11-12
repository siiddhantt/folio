ALTER TABLE conversation_turns
    ADD COLUMN parent_sequence integer NOT NULL DEFAULT 0,
    ADD COLUMN context_snapshot jsonb,
    ADD COLUMN resolution jsonb,
    ADD CONSTRAINT turn_parent_sequence CHECK(parent_sequence = sequence - 1);

ALTER TABLE turn_invocations DROP CONSTRAINT turn_invocations_stage_check;
ALTER TABLE turn_invocations ADD CONSTRAINT turn_invocations_stage_check
    CHECK(stage IN ('embedding','answer','rewrite'));
