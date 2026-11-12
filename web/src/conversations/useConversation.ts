import { useEffect, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { Conversation, Turn } from './types';

export const questionIntentKey = (conversationId: string) => `folio:question:${conversationId}`;

export function useConversation(id: string) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    Promise.all([
      request<Conversation>(`/conversations/${id}`, { signal: controller.signal }),
      request<{ items: Turn[]; next_after: number | null }>(
        `/conversations/${id}/turns?after=0&limit=20`,
        { signal: controller.signal },
      ),
    ])
      .then(([next, history]) => {
        if (controller.signal.aborted) return;
        setConversation(next);
        setTurn(history.items[0] || null);
        setLoaded(true);
        if (history.items.length) sessionStorage.removeItem(questionIntentKey(id));
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [id, refresh]);
  const active = turn?.state === 'pending' || turn?.state === 'running';
  const turnId = turn?.id;
  useEffect(() => {
    if (!active || !turnId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await request<Turn>(`/conversations/${id}/turns/${turnId}`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setTurn(next);
        setError('');
        if (next.state === 'pending' || next.state === 'running') timer = setTimeout(poll, 1500);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(errorMessage(e));
        if (!(e instanceof ApiError && e.status === 404)) timer = setTimeout(poll, 3000);
      }
    }
    timer = setTimeout(poll, 1000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, turnId, active]);
  return {
    conversation,
    turn,
    error,
    loaded,
    setTurn,
    reload: () => setRefresh((value) => value + 1),
  };
}
