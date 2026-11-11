export interface ProcessingRun {
  request_id: string;
  document_id: string;
  revision_id: string | null;
  filename: string;
  accepted_at: string;
  extraction_state: 'open' | 'succeeded' | 'failed';
  current_attempt_state: 'pending' | 'running' | 'succeeded' | 'failed';
  extraction_error_code: string | null;
  summary_state: 'not_scheduled' | 'pending' | 'running' | 'ready' | 'unavailable' | 'failed';
  summary_error_code: string | null;
}

export interface RunPage {
  items: ProcessingRun[];
  next_cursor: string | null;
}
