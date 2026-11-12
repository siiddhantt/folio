import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import { UploadPage } from '../documents/UploadPage';
import type { Capabilities } from '../types';
import type { Conversation } from './types';

export function HomePage({ capabilities }: { capabilities: Capabilities }) {
  const [params, setParams] = useSearchParams();
  const before = params.get('before');
  const [data, setData] = useState<{ items: Conversation[]; next_cursor: string | null } | null>(
    null,
  );
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    setData(null);
    request<{ items: Conversation[]; next_cursor: string | null }>(
      `/conversations?limit=20${before ? `&before=${encodeURIComponent(before)}` : ''}`,
      { signal: controller.signal },
    )
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [before, refresh]);
  return (
    <div className="home-layout">
      <section className="conversation-list" aria-labelledby="conversations-title">
        <div className="conversation-list-heading">
          <h1 id="conversations-title">Conversations</h1>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Refresh conversations"
            onClick={() => setRefresh(refresh + 1)}
          >
            <RefreshCw aria-hidden="true" />
          </Button>
        </div>
        {error && <Notice error>{error}</Notice>}
        {!data && !error && (
          <p className="subtle" role="status">
            Loading conversations…
          </p>
        )}
        {data && !data.items.length && (
          <p className="conversation-empty">No conversations yet. Open a PDF to start.</p>
        )}
        {!!data?.items.length && (
          <ul>
            {data.items.map((conversation) => (
              <li key={conversation.id}>
                <Link to={`/conversations/${conversation.id}`}>
                  <span className="conversation-list-title">
                    {conversation.question || 'New chat'}
                  </span>
                  <span className="conversation-list-meta">
                    <span>{conversation.document_name}</span>
                    <time dateTime={conversation.created_at}>
                      {new Date(conversation.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                      })}
                    </time>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {(before || data?.next_cursor) && (
          <nav className="runs-pagination" aria-label="Conversation pages">
            {before && (
              <Button variant="outline" size="sm" onClick={() => setParams({})}>
                Latest
              </Button>
            )}
            {data?.next_cursor && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setParams({ before: data.next_cursor! })}
              >
                Older
              </Button>
            )}
          </nav>
        )}
      </section>
      <UploadPage capabilities={capabilities} compact />
    </div>
  );
}
