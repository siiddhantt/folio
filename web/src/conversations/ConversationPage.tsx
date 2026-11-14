import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowDown, FileText } from 'lucide-react';
import { Button, Notice } from '../components/ui';
import { Answer } from './Answer';
import { NewChatButton } from './NewChatButton';
import { QuestionComposer } from './QuestionComposer';
import { SourcePanel } from './SourcePanel';
import { useConversation } from './useConversation';
import type { Citation, Conversation, Turn } from './types';

export function ConversationPage({
  revision,
  renamedConversation,
  onTurnChanged,
}: {
  revision: number;
  renamedConversation: Conversation | null;
  onTurnChanged: () => void;
}) {
  const { conversationId = '' } = useParams();
  return (
    <ConversationWorkspace
      key={conversationId}
      id={conversationId}
      revision={revision}
      renamedConversation={renamedConversation}
      onTurnChanged={onTurnChanged}
    />
  );
}

function ConversationWorkspace({
  id,
  revision,
  renamedConversation,
  onTurnChanged,
}: {
  id: string;
  revision: number;
  renamedConversation: Conversation | null;
  onTurnChanged: () => void;
}) {
  const {
    conversation,
    turns,
    active,
    historyLoading,
    observedHead,
    error,
    loaded,
    acceptTurn,
    reload,
    nextBefore,
    olderLoading,
    loadOlder,
    loadTurn,
  } = useConversation(id, revision, onTurnChanged, renamedConversation);
  const [source, setSource] = useState<{
    turnId: string;
    citations: Citation[];
    coverage: Turn['coverage'];
    selected?: string;
  } | null>(null);
  const [focusTurn, setFocusTurn] = useState<string | null>(null);
  const [unseenReply, setUnseenReply] = useState(false);
  const following = useRef(true);
  const messages = useRef<HTMLDivElement>(null);
  const latestTurn = turns.at(-1);
  useLayoutEffect(() => {
    if (!loaded) return;
    if (following.current) showLatest();
    else setUnseenReply(true);
  }, [loaded, latestTurn?.id, latestTurn?.state, latestTurn?.context_state]);
  function showLatest() {
    following.current = true;
    setUnseenReply(false);
    messages.current?.scrollTo({ top: messages.current.scrollHeight });
  }
  function trackReadingPosition() {
    const main = messages.current;
    if (!main) return;
    following.current = main.scrollHeight - main.scrollTop - main.clientHeight < 64;
    if (following.current) setUnseenReply(false);
  }
  const readingAnchor = useRef<{ element: HTMLElement; top: number } | null>(null);
  useLayoutEffect(() => {
    const anchor = readingAnchor.current;
    readingAnchor.current = null;
    const main = messages.current;
    if (anchor?.element.isConnected && main) {
      main.scrollTop += anchor.element.getBoundingClientRect().top - anchor.top;
    }
  }, [turns]);
  useLayoutEffect(() => {
    if (!focusTurn) return;
    const target = document.getElementById(`exchange-${focusTurn}`);
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'start' });
      setFocusTurn(null);
    }
  }, [focusTurn, turns]);
  async function showTurn(turnId: string) {
    following.current = false;
    if (await loadTurn(turnId)) setFocusTurn(turnId);
  }
  function loadEarlier() {
    void loadOlder(() => {
      following.current = false;
      const main = messages.current;
      if (!main) return;
      const top = main.getBoundingClientRect().top;
      const element = [...main.querySelectorAll<HTMLElement>('.chat-exchange')].find(
        (exchange) => exchange.getBoundingClientRect().bottom >= top,
      );
      if (element) readingAnchor.current = { element, top: element.getBoundingClientRect().top };
    });
  }
  useEffect(() => {
    if (conversation)
      document.title = `${conversation.title || conversation.document_name} · Folio`;
  }, [conversation?.title, conversation?.document_name]);
  return (
    <div className="chat-page">
      <div className="chat-heading">
        <div className="chat-heading-title">
          <FileText aria-hidden="true" />
          <div>
            <h1>{conversation?.title || conversation?.document_name || 'Conversation'}</h1>
            {conversation && <p className="chat-document-name">{conversation.document_name}</p>}
          </div>
        </div>
        {conversation && (
          <div className="chat-heading-actions">
            <Button variant="outline" size="sm" asChild>
              <Link to={`/documents/${conversation.document_id}`}>View document</Link>
            </Button>
            <NewChatButton indexId={conversation.index_id} />
          </div>
        )}
      </div>
      <div
        className="chat-scroll"
        ref={messages}
        onScroll={trackReadingPosition}
        role="region"
        aria-label="Conversation messages"
        tabIndex={0}
      >
        <div className="chat-content">
          <p className="sr-only" role="status">
            {turns.at(-1)?.state === 'ready' ? 'Answer ready.' : ''}
          </p>
          {error && (
            <Notice error>
              {error}{' '}
              <button className="inline-retry" onClick={reload}>
                Reload chat
              </button>
            </Notice>
          )}
          {!loaded && !error && (
            <p className="subtle" role="status">
              Loading conversation…
            </p>
          )}
          {loaded && conversation && (
            <>
              {nextBefore !== null && (
                <Button
                  className="earlier-exchanges"
                  variant="ghost"
                  disabled={olderLoading}
                  onClick={loadEarlier}
                >
                  {olderLoading ? 'Loading earlier exchanges…' : 'Load earlier exchanges'}
                </Button>
              )}
              {turns.map((turn, index) => (
                <Fragment key={turn.id}>
                  {index > 0 && turn.sequence > turns[index - 1].sequence + 1 && (
                    <p className="chat-history-gap" role="note">
                      Exchanges {turns[index - 1].sequence + 1}–{turn.sequence - 1} are not loaded.
                      Use Load earlier exchanges to read them.
                    </p>
                  )}
                  <section
                    id={`exchange-${turn.id}`}
                    aria-label={`Exchange ${turn.sequence}`}
                    tabIndex={-1}
                    className="chat-exchange"
                  >
                    <Answer
                      turn={turn}
                      onSource={(citation) =>
                        setSource({
                          turnId: turn.id,
                          citations: turn.citations,
                          coverage: turn.coverage,
                          selected: citation?.source_id,
                        })
                      }
                      onTurnReference={(turnId) => void showTurn(turnId)}
                    />
                  </section>
                </Fragment>
              ))}
            </>
          )}
        </div>
      </div>
      {loaded && conversation && (
        <div className="chat-composer-dock">
          {unseenReply && (
            <div className="chat-latest">
              <Button variant="outline" size="sm" onClick={showLatest}>
                <ArrowDown aria-hidden="true" /> Latest reply
              </Button>
            </div>
          )}
          <QuestionComposer
            conversationId={id}
            observedHead={observedHead}
            waiting={active || historyLoading}
            documentName={conversation.document_name}
            onAccepted={(turn) => {
              showLatest();
              acceptTurn(turn);
              onTurnChanged();
            }}
            onConflict={reload}
          />
        </div>
      )}
      {source && conversation && (
        <SourcePanel
          key={`${source.turnId}:${source.selected || 'all'}`}
          documentId={conversation.document_id}
          sources={source.citations}
          coverage={source.coverage}
          selected={source.selected}
          onClose={() => setSource(null)}
        />
      )}
    </div>
  );
}
