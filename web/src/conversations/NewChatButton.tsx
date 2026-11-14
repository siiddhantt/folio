import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquarePlus } from 'lucide-react';
import { errorMessage, request } from '../api';
import { Button } from '../components/ui';
import type { IndexStatus } from '../types';

export function NewChatButton({ indexId }: { indexId: string }) {
  return (
    <Button variant="outline" size="sm" asChild>
      <Link to={`/new-chat?document=${encodeURIComponent(indexId)}`}>
        <MessageSquarePlus aria-hidden="true" />
        New chat
      </Link>
    </Button>
  );
}

export function DocumentChatAction({ revisionId }: { revisionId: string }) {
  const [index, setIndex] = useState<IndexStatus | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await request<IndexStatus>(`/revisions/${revisionId}/index`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setIndex(next);
        setError('');
        if (next.state === 'pending' || next.state === 'running') timer = setTimeout(poll, 2000);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(errorMessage(e));
        timer = setTimeout(poll, 3000);
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [revisionId]);
  if (index?.state === 'ready' && index.index_id) return <NewChatButton indexId={index.index_id} />;
  const waiting = !index || index.state === 'pending' || index.state === 'running';
  return (
    <Button
      variant="outline"
      size="sm"
      disabled
      title={
        error ||
        (waiting
          ? 'Waiting for document indexing'
          : 'A complete document index is needed to start a chat')
      }
    >
      <MessageSquarePlus aria-hidden="true" />
      {waiting ? 'Preparing chat…' : 'Chat unavailable'}
    </Button>
  );
}
