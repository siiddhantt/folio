import { useEffect, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { Attempt, IndexInspection, RequestStatus } from '../types';
import type { FailureDiagnostics, SummaryInspection } from './types';

export interface ProcessingEvent {
  id: number;
  attempt_id: string;
  name: string;
  occurred_at: string;
  details: Record<string, unknown>;
}

export interface Inspection extends Omit<RequestStatus, 'revision_id' | 'attempts'> {
  file_version_id: string;
  source: { sha256: string; byte_size: number; media_type: string };
  configuration: Record<string, unknown>;
  summary_configuration: Record<string, unknown> | null;
  summary: SummaryInspection | null;
  indexing?: IndexInspection | null;
  attempts: (Attempt & {
    failure_diagnostics: FailureDiagnostics | null;
    lease_expires_at: string | null;
    transport_job_id: string | null;
    last_dispatched_at: string | null;
    next_dispatch_at: string;
    terminal_delivery_failures: number;
  })[];
  events: ProcessingEvent[];
  next_after_id: number | null;
}

export function useInspection(requestId: string, open: boolean) {
  const [data, setData] = useState<Inspection | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let after = 0;
    const events = new Map<number, ProcessingEvent>();
    setData(null);
    setError('');
    async function poll() {
      try {
        const snapshot = await request<Inspection>(
          `/development/ingestion-requests/${requestId}?after_id=${after}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        snapshot.events.forEach((event) => events.set(event.id, event));
        after = snapshot.events.at(-1)?.id ?? after;
        setData({ ...snapshot, events: [...events.values()] });
        setError('');
        if (
          snapshot.next_after_id !== null ||
          snapshot.state === 'open' ||
          snapshot.summary?.state === 'pending' ||
          snapshot.summary?.state === 'running' ||
          snapshot.indexing?.state === 'pending' ||
          snapshot.indexing?.state === 'running'
        )
          timer = setTimeout(poll, snapshot.next_after_id !== null ? 0 : 2000);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(errorMessage(e));
        if (!(e instanceof ApiError && e.status === 404)) timer = setTimeout(poll, 3000);
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [requestId, open, reload]);
  return { data, error, reconnect: () => setReload(reload + 1) };
}
