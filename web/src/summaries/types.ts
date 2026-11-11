import type { Diagnostic } from '../types';

export interface SummaryClaim {
  text: string;
  source_ids: string[];
}

export interface DocumentSummary {
  revision_id: string;
  run_id: string | null;
  state: 'pending' | 'running' | 'ready' | 'unavailable' | 'failed' | 'not_scheduled';
  overview: SummaryClaim | null;
  points: SummaryClaim[];
  citations: { source_id: string; pages: number[] }[];
  coverage: {
    scope: 'available_evidence';
    diagnostics: Diagnostic[];
    pages_without_content: number[];
  };
  error: { code: string; message: string } | null;
}
