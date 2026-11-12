import { useEffect, useRef, useState } from 'react';
import { ApiError, errorMessage, request } from '../api';
import type { Conversation, Turn } from './types';

function mergeTurns(previous: Turn[], incoming: Turn[]) {
  const values = new Map(previous.map((turn) => [turn.id, turn]));
  for (const turn of incoming) {
    const saved = values.get(turn.id);
    if (!saved || saved.state === 'pending' || saved.state === 'running') values.set(turn.id, turn);
  }
  return [...values.values()].sort((a, b) => a.sequence - b.sequence);
}

export function useConversation(
  id: string,
  revision: number,
  onTurnChanged: () => void,
  renamedConversation: Conversation | null,
) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [missing, setMissing] = useState(false);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [olderLoading, setOlderLoading] = useState(false);
  const latestPageRevision = useRef(0);
  const operations = useRef<AbortController | null>(null);
  useEffect(() => {
    operations.current = new AbortController();
    return () => operations.current?.abort();
  }, []);
  useEffect(() => {
    if (renamedConversation?.id === id) setConversation(renamedConversation);
  }, [id, renamedConversation]);
  function hideMissing(reason: unknown) {
    if (reason instanceof ApiError && reason.status === 404) {
      setMissing(true);
      setConversation(null);
      setTurns([]);
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
    setHistoryLoading(true);
    request<{ items: Turn[]; next_before: number | null }>(`/conversations/${id}/turns?limit=20`, {
      signal: controller.signal,
    })
      .then((history) => {
        if (controller.signal.aborted) return;
        latestPageRevision.current += 1;
        setTurns((previous) => mergeTurns(previous, history.items));
        setNextBefore(history.next_before ?? null);
        setLoaded(true);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          hideMissing(e);
          setError(errorMessage(e));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setHistoryLoading(false);
      });
    return () => controller.abort();
  }, [id, refresh]);
  const activeTurn = turns.find((turn) => turn.state === 'pending' || turn.state === 'running');
  const active = !!activeTurn;
  const turnId = activeTurn?.id;
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
        setTurns((previous) => mergeTurns(previous, [next]));
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
  async function loadOlder(beforeDisplay: () => void) {
    const signal = operations.current?.signal;
    if (nextBefore === null || olderLoading || !signal) return;
    const requestedRevision = latestPageRevision.current;
    setOlderLoading(true);
    try {
      const history = await request<{ items: Turn[]; next_before: number | null }>(
        `/conversations/${id}/turns?before_sequence=${nextBefore}&limit=20`,
        { signal },
      );
      if (signal.aborted) return;
      beforeDisplay();
      setTurns((previous) => mergeTurns(previous, history.items));
      if (requestedRevision === latestPageRevision.current) setNextBefore(history.next_before);
      setError('');
    } catch (reason) {
      if (!signal.aborted) {
        hideMissing(reason);
        setError(errorMessage(reason));
      }
    } finally {
      if (!signal.aborted) setOlderLoading(false);
    }
  }
  async function loadTurn(turnId: string) {
    const saved = turns.find((turn) => turn.id === turnId);
    if (saved) return saved;
    const signal = operations.current?.signal;
    if (!signal) return null;
    try {
      const turn = await request<Turn>(`/conversations/${id}/turns/${turnId}`, { signal });
      if (signal.aborted) return null;
      setTurns((previous) => mergeTurns(previous, [turn]));
      setError('');
      return turn;
    } catch (reason) {
      if (!signal.aborted) {
        hideMissing(reason);
        setError(errorMessage(reason));
      }
      return null;
    }
  }
  return {
    conversation: missing ? null : conversation,
    turns: missing ? [] : turns,
    active: active && !missing,
    historyLoading,
    nextBefore,
    olderLoading,
    loadOlder,
    loadTurn,
    observedHead: turns.at(-1)?.sequence || 0,
    error,
    loaded: loaded && !!conversation && !missing,
    acceptTurn: (turn: Turn) => setTurns((previous) => mergeTurns(previous, [turn])),
    reload: () => {
      setMissing(false);
      setRefresh((value) => value + 1);
    },
  };
}
