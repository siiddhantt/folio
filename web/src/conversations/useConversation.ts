import { useEffect, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { Conversation, Turn } from './types';
import { questionDraftKey, questionIntentKey } from './storage';

export function useConversation(
  id: string,
  revision: number,
  onTurnChanged: () => void,
  renamedConversation: Conversation | null,
) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    if (renamedConversation?.id === id) setConversation(renamedConversation);
  }, [id, renamedConversation]);
  function hideMissing(reason: unknown) {
    if (reason instanceof ApiError && reason.status === 404) {
      setMissing(true);
      setConversation(null);
      setTurn(null);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    request<Conversation>(`/conversations/${id}`, { signal: controller.signal })
      .then((next) => {
        if (!controller.signal.aborted) setConversation(next);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          hideMissing(e);
          setError(errorMessage(e));
        }
      });
    return () => controller.abort();
  }, [id, revision, refresh]);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    request<{ items: Turn[]; next_after: number | null }>(
      `/conversations/${id}/turns?after=0&limit=20`,
      { signal: controller.signal },
    )
      .then((history) => {
        if (controller.signal.aborted) return;
        setTurn(history.items[0] || null);
        setLoaded(true);
        if (history.items.length) {
          sessionStorage.removeItem(questionIntentKey(id));
          sessionStorage.removeItem(questionDraftKey(id));
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          hideMissing(e);
          setError(errorMessage(e));
        }
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
        else onTurnChanged();
      } catch (e) {
        if (controller.signal.aborted) return;
        hideMissing(e);
        setError(errorMessage(e));
        if (!(e instanceof ApiError && e.status === 404)) timer = setTimeout(poll, 3000);
      }
    }
    timer = setTimeout(poll, 1000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, turnId, active, onTurnChanged]);
  return {
    conversation: missing ? null : conversation,
    turn: missing ? null : turn,
    error,
    loaded: loaded && !!conversation && !missing,
    setTurn,
    reload: () => {
      setMissing(false);
      setRefresh((value) => value + 1);
    },
  };
}
