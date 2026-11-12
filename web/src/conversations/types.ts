import type { Diagnostic } from '../types';

export type TurnState = 'pending' | 'running' | 'ready' | 'failed' | 'unavailable';

export interface Conversation {
  id: string;
  document_id: string;
  revision_id: string;
  index_id: string;
  document_name: string;
  title: string;
  title_source: 'generated' | 'manual' | null;
  title_version: number;
  created_at: string;
  question: string | null;
  state: 'empty' | TurnState;
  head_sequence: number;
  max_turns: null;
}

export interface Citation {
  source_id: string;
  chunk_ordinal: number;
  text: string;
  pages: number[];
}

export interface Turn {
  id: string;
  conversation_id: string;
  sequence: number;
  parent_sequence: number;
  resolved_question: string | null;
  question: string;
  state: TurnState;
  context_state?: 'preparing' | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: { code: string; message: string } | null;
  answer: {
    outcome: 'answer' | 'clarification' | 'insufficient_evidence' | 'transcript';
    statements: { text: string; source_ids: string[]; turn_ids?: string[] }[];
  } | null;
  citations: Citation[];
  coverage: { pages_without_content: number[]; diagnostics: Diagnostic[] };
}
