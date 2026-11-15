ALTER TABLE embedding_invocations DROP CONSTRAINT embedding_invocations_billing_state_check;
ALTER TABLE embedding_invocations ADD CONSTRAINT embedding_invocations_billing_state_check
    CHECK (billing_state IN ('none','reserved','known','unknown','estimated'));
