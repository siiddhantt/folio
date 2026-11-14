ALTER TABLE turn_invocations DROP CONSTRAINT turn_invocations_billing_state_check;
ALTER TABLE turn_invocations ADD CONSTRAINT turn_invocations_billing_state_check
    CHECK(billing_state IN ('reserved','unknown','known','estimated'));

ALTER TABLE memory_attempts DROP CONSTRAINT memory_attempts_billing_state_check;
ALTER TABLE memory_attempts ADD CONSTRAINT memory_attempts_billing_state_check
    CHECK(billing_state IN ('reserved','unknown','known','estimated'));
