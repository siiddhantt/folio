import type { FailureDiagnostics } from './development/types';

export interface Capabilities {
  max_upload_bytes: number;
  max_pages: number;
  development_mode: boolean;
}

export interface DocumentMetadata {
  id: string;
  display_name: string;
  created_at: string;
  current_request_id: string;
  active_revision_id: string | null;
}

export interface Attempt {
  id: string;
  attempt_no: number;
  state: 'pending' | 'running' | 'succeeded' | 'failed';
  available_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_detail: string | null;
  parser_status: string | null;
  retryable: boolean | null;
  metrics: Record<string, number> | null;
  dispatch_error: string | null;
  dispatch_count: number;
}

export interface RequestStatus {
  request_id: string;
  document_id: string;
  state: 'open' | 'succeeded' | 'failed';
  authorized_attempt_id: string;
  created_at: string;
  finished_at: string | null;
  attempts: Attempt[];
  revision_id: string | null;
}

export interface SourceElement {
  element_id: string;
  kind: string;
  reading_order: number;
  text: string | null;
  table_data: null | { row_count: number; column_count: number; cells: TableCell[] };
  locations: {
    page_no: number;
    x0: number | null;
    y0: number | null;
    x1: number | null;
    y1: number | null;
  }[];
}

export interface TableCell {
  row: number;
  column: number;
  row_span: number;
  column_span: number;
  text: string;
  column_header: boolean;
  row_header: boolean;
}

export interface Evidence {
  revision_id: string;
  pages: { page_no: number; content_observation: string; diagnostics: Diagnostic[] }[];
  diagnostics: Diagnostic[];
  elements: SourceElement[];
  next_after_order: number | null;
}

export interface Diagnostic {
  code?: string;
  page_no?: number;
  message?: string;
  error_message?: string;
  [key: string]: unknown;
}

export interface IndexStatus {
  index_id: string | null;
  state: 'not_started' | 'pending' | 'running' | 'ready' | 'unavailable' | 'failed';
  chunk_count: number;
  embedded_chunks: number;
  model_id: string | null;
  dimensions: number | null;
  error_code: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  available_at: string | null;
  lease_expires_at: string | null;
  dispatch_error: string | null;
  coverage: { diagnostics: Diagnostic[]; pages_without_content: number[] };
  exclusions: { element_id: string; reason: string }[];
  warnings: Diagnostic[];
}

export interface IndexInspection extends IndexStatus {
  has_more: boolean;
  attempts: {
    id: string;
    attempt_no: number;
    batch_no: number | null;
    state: 'running' | 'succeeded' | 'failed';
    started_at: string;
    finished_at: string | null;
    invoked_at: string | null;
    error_code: string | null;
    failure_diagnostics: FailureDiagnostics | null;
    billing_state: 'none' | 'reserved' | 'known' | 'unknown';
    reserved_usd: number | null;
    cost_usd: number | null;
    response_id: string | null;
    input_hash: string | null;
    chunk_ordinals: number[];
    usage: {
      prompt_tokens?: number | null;
      input_tokens?: number | null;
      model?: string;
      requested_provider?: string;
    };
  }[];
}
