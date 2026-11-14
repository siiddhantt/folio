ALTER TABLE summary_budget_account
    ADD COLUMN admission_error text CHECK (admission_error = 'RESERVATION_EXCEEDED');
