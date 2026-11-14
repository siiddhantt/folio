export interface FailureDiagnostics {
  error_type: string;
  errno?: number;
  error_frames: { module: string; function: string; line: number }[];
}

export interface SummaryInspection {
  id: string;
  state: 'pending' | 'running' | 'ready' | 'unavailable' | 'failed';
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  attempts: {
    id: string;
    attempt_no: number;
    state: 'running' | 'succeeded' | 'failed';
    started_at: string;
    finished_at: string | null;
    invoked_at: string | null;
    error_code: string | null;
    response_id: string | null;
    billing_state: 'not_invoked' | 'reserved' | 'known' | 'unknown';
    reserved_usd: number | null;
    cost_usd: number | null;
    usage: {
      prompt_tokens?: number | null;
      completion_tokens?: number | null;
      reasoning_tokens?: number | null;
      finish_reason?: string;
      response_characters?: number;
      model?: string;
      provider?: string;
    } | null;
    failure_diagnostics: FailureDiagnostics | null;
  }[];
}
