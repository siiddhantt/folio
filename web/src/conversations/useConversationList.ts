import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { errorMessage, request } from '../api';
import type { Conversation } from './types';

interface ConversationList {
  items: Conversation[];
  next_cursor: string | null;
}

export function useConversationList(revision: number) {
  const { pathname, state } = useLocation();
  const [before, setBefore] = useState<string | null>(null);
  const [data, setData] = useState<ConversationList | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const removed = useRef(new Set<string>());
  useEffect(() => {
    if (state?.createdConversation) setBefore(null);
  }, [state?.createdConversation]);
  useEffect(() => {
    const onFocus = () => setRefresh((value) => value + 1);
    const onVisible = () => {
      if (document.visibilityState === 'visible') onFocus();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    setLoading(true);
    request<ConversationList>(
      `/conversations?limit=20${before ? `&before=${encodeURIComponent(before)}` : ''}`,
      {
        signal: controller.signal,
      },
    )
      .then((value) => {
        if (!controller.signal.aborted) {
          setData({ ...value, items: value.items.filter((item) => !removed.current.has(item.id)) });
          setError('');
          setLoading(false);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setError(errorMessage(error));
          setLoading(false);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          // Wait for each read to finish so slow responses are not repeatedly cancelled.
          timer = setTimeout(() => {
            if (document.visibilityState === 'visible') setRefresh((value) => value + 1);
          }, 15000);
        }
      });
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [pathname, before, revision, refresh]);
  return {
    data,
    error,
    loading,
    before,
    setBefore,
    reload: () => setRefresh((value) => value + 1),
    update: (conversation: Conversation) => {
      setData((previous) =>
        previous
          ? {
              ...previous,
              items: previous.items.map((item) =>
                item.id === conversation.id ? conversation : item,
              ),
            }
          : null,
      );
    },
    remove: (id: string) => {
      removed.current.add(id);
      setData((previous) =>
        previous ? { ...previous, items: previous.items.filter((item) => item.id !== id) } : null,
      );
    },
  };
}
