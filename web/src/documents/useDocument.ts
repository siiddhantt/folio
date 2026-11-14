import { useEffect, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { DocumentMetadata, RequestStatus } from '../types';

export function useDocument(documentId: string) {
  const [document, setDocument] = useState<DocumentMetadata | null>(null);
  const [status, setStatus] = useState<RequestStatus | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let metadata: DocumentMetadata | null = null;
    setDocument(null);
    setStatus(null);
    setError('');
    async function poll() {
      try {
        metadata ||= await request<DocumentMetadata>(
          `/documents/${encodeURIComponent(documentId)}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setDocument(metadata);
        const next = await request<RequestStatus>(
          `/ingestion-requests/${metadata.current_request_id}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setStatus(next);
        setError('');
        if (next.state === 'open') timer = setTimeout(poll, 2000);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError && e.status === 404
            ? 'This document could not be found.'
            : `${errorMessage(e)} Reconnecting…`,
        );
        if (!(e instanceof ApiError && e.status === 404)) timer = setTimeout(poll, 3000);
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [documentId]);
  return { document, status, error };
}
