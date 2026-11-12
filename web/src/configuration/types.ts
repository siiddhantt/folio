export interface Controls {
  max_pages: number;
  max_upload_bytes: number;
  parser_timeout_seconds: number;
  summary_enabled: boolean;
  summary_input_limit_tokens: number;
  summary_max_output_tokens: number;
  summary_reasoning_effort: string;
}

export interface Configuration {
  revision: number;
  updated_at: string;
  values: Controls;
  runtime: {
    model_id: string | null;
    provider: string | null;
    token_margin: number | null;
    reasoning_options: string[];
    summary_configuration_error: string | null;
    job_timeout_seconds: number;
    lease_seconds: number;
    summary_timeout_seconds: number | null;
    document_budget_usd: string | null;
    budget_usd: string;
    admission_error: string | null;
    spent_usd: string;
    held_usd: string;
    remaining_usd: string;
  };
}
