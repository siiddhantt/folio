import { Link, NavLink } from 'react-router-dom';
import { Dialog } from 'radix-ui';
import { FilePlus2, RefreshCw, X } from 'lucide-react';
import { Button } from '../components/ui';
import { useConversationList } from './useConversationList';

export function ConversationSidebar({
  revision,
  onNavigate,
}: {
  revision: number;
  onNavigate: () => void;
}) {
  const history = useConversationList(revision);
  const content = (
    <>
      <Button variant="outline" className="sidebar-open-document" asChild>
        <Link to="/" onClick={onNavigate}>
          <FilePlus2 aria-hidden="true" />
          Open document
        </Link>
      </Button>
      <div className="sidebar-section-heading">
        <h2>Conversations</h2>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Refresh conversations"
          onClick={history.reload}
          disabled={history.loading}
        >
          <RefreshCw aria-hidden="true" />
        </Button>
      </div>
      <nav
        key={history.before || 'latest'}
        aria-label="Conversations"
        className="conversation-history-list"
        aria-busy={history.loading}
      >
        {history.error && (
          <div className="sidebar-message">
            <p role="alert">History could not load.</p>
            <Button variant="outline" size="sm" onClick={history.reload}>
              Retry history
            </Button>
          </div>
        )}
        {!history.data ? (
          !history.error && (
            <p className="sidebar-message" role="status">
              Loading conversations…
            </p>
          )
        ) : !history.data.items.length ? (
          <p className="sidebar-message">Your conversations will appear here.</p>
        ) : (
          <ul>
            {history.data.items.map((conversation) => (
              <li key={conversation.id}>
                <NavLink
                  to={`/conversations/${conversation.id}`}
                  onClick={onNavigate}
                  title={conversation.question || conversation.document_name}
                >
                  <span className="history-title">
                    {conversation.question || conversation.document_name}
                  </span>
                  <span className="history-detail">
                    <span>
                      {conversation.question ? conversation.document_name : 'No question yet'}
                    </span>
                    {(conversation.state === 'failed' || conversation.state === 'unavailable') && (
                      <span className="history-failure">Unanswered</span>
                    )}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </nav>
      {(history.before || history.data?.next_cursor) && (
        <div className="history-pagination">
          {history.before && (
            <Button
              variant="ghost"
              size="sm"
              aria-label="Latest conversations"
              onClick={() => history.setBefore(null)}
              disabled={history.loading}
            >
              Latest
            </Button>
          )}
          {history.data?.next_cursor && (
            <Button
              variant="ghost"
              size="sm"
              aria-label="Older conversations"
              onClick={() => history.setBefore(history.data!.next_cursor)}
              disabled={history.loading || !!history.error}
            >
              Older
            </Button>
          )}
        </div>
      )}
    </>
  );
  return (
    <>
      <aside className="conversation-sidebar" aria-label="Conversation history">
        {content}
      </aside>
      <Dialog.Portal>
        <Dialog.Overlay className="history-overlay" />
        <Dialog.Content
          className="history-drawer"
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            if (window.matchMedia('(min-width: 1100px)').matches) {
              event.preventDefault();
              document.getElementById('main')?.focus({ preventScroll: true });
            }
          }}
        >
          <div className="history-drawer-heading">
            <Dialog.Title>Conversation history</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close conversation history">
                <X aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>
          <div className="history-drawer-body">{content}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </>
  );
}
