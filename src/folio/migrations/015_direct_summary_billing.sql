ALTER TABLE summary_attempts DROP CONSTRAINT summary_attempts_billing_state_check;
ALTER TABLE summary_attempts ADD CONSTRAINT summary_attempts_billing_state_check
    CHECK (billing_state IN ('not_invoked','reserved','unknown','known','estimated'));
