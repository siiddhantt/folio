import { useEffect, useState } from 'react';
import { errorMessage, request } from '../api';
import type { RunPage } from './types';

export function useRuns(before: string | null) {
  const [data, setData] = useState<RunPage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setData(null);
    setError('');
    setLoading(true);
    async function read() {
      try {
        const result = await request<RunPage>(
          `/ingestion-requests?limit=25${before ? `&before=${encodeURIComponent(before)}` : ''}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setData(result);
        setError('');
        if (
          result.items.some(
            (run) =>
              run.extraction_state === 'open' || ['pending', 'running'].includes(run.summary_state),
          )
        )
          timer = setTimeout(read, 3000);
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void read();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [before, refresh]);
  return { data, error, loading, reload: () => setRefresh((value) => value + 1) };
}
