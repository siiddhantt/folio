import { useEffect, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { DocumentSummary } from './types';

export function useSummary(revisionId: string) {
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setSummary(null);
    setError('');
    async function poll() {
      try {
        const next = await request<DocumentSummary>(`/revisions/${revisionId}/summary`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setSummary(next);
        setError('');
        if (next.state === 'pending' || next.state === 'running') timer = setTimeout(poll, 2000);
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
  }, [revisionId]);
  return { summary, error };
}
