import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquarePlus } from 'lucide-react';
import { errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import type { IndexStatus } from '../types';
import type { Conversation } from './types';

export function NewChatButton({ indexId }: { indexId: string }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function create() {
    if (busy) return;
    setBusy(true);
    setError('');
    const storageKey = `folio:new-chat:${indexId}`;
    const key = sessionStorage.getItem(storageKey) || crypto.randomUUID();
    sessionStorage.setItem(storageKey, key);
    try {
      const conversation = await request<Conversation>('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
        body: JSON.stringify({ index_id: indexId }),
      });
      sessionStorage.removeItem(storageKey);
      navigate(`/conversations/${conversation.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="new-chat-action">
      <Button variant="outline" size="sm" disabled={busy} onClick={() => void create()}>
        <MessageSquarePlus aria-hidden="true" />
        {busy ? 'Opening…' : 'New chat'}
      </Button>
      {error && <Notice error>{error} Try New chat again to recover the same request.</Notice>}
    </div>
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
