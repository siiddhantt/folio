import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { FileText } from 'lucide-react';
import { Button, Notice } from '../components/ui';
import { Answer } from './Answer';
import { NewChatButton } from './NewChatButton';
import { QuestionComposer } from './QuestionComposer';
import { SourcePanel } from './SourcePanel';
import { useConversation } from './useConversation';
import type { Citation, Conversation } from './types';

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
  const [source, setSource] = useState<{ turnId: string; citation: Citation } | null>(null);
  const [focusTurn, setFocusTurn] = useState<string | null>(null);
  const [submittedTurn, setSubmittedTurn] = useState<string | null>(null);
  const initiallyScrolled = useRef(false);
  const readingAnchor = useRef<{ element: HTMLElement; top: number } | null>(null);
  useLayoutEffect(() => {
    const anchor = readingAnchor.current;
    readingAnchor.current = null;
    const main = document.getElementById('main');
    if (anchor?.element.isConnected && main) {
      main.scrollTop += anchor.element.getBoundingClientRect().top - anchor.top;
    }
  }, [turns]);
  useLayoutEffect(() => {
    if (loaded && !initiallyScrolled.current) {
      initiallyScrolled.current = true;
      const main = document.getElementById('main');
      main?.scrollTo({ top: main.scrollHeight });
    }
  }, [loaded]);
  useLayoutEffect(() => {
    if (!submittedTurn) return;
    document.getElementById(`exchange-${submittedTurn}`)?.scrollIntoView({ block: 'start' });
    setSubmittedTurn(null);
  }, [submittedTurn, turns]);
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
    if (await loadTurn(turnId)) setFocusTurn(turnId);
  }
  function loadEarlier() {
    void loadOlder(() => {
      const main = document.getElementById('main');
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
      <div className={`chat-content${loaded && !turns.length ? ' chat-empty' : ''}`}>
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
                    onSource={(citation) => setSource({ turnId: turn.id, citation })}
                    onTurnReference={(turnId) => void showTurn(turnId)}
                  />
                </section>
              </Fragment>
            ))}
            {turns.some(
              (turn) =>
                turn.coverage.pages_without_content.length > 0 ||
                turn.coverage.diagnostics.length > 0,
            ) && (
              <p className="chat-coverage" role="note">
                Some document content may be missing.{' '}
                <Link to={`/documents/${conversation.document_id}`}>
                  Check the document’s extraction details
                </Link>{' '}
                when verifying answers.
              </p>
            )}
            <QuestionComposer
              conversationId={id}
              observedHead={observedHead}
              waiting={active || historyLoading}
              documentName={conversation.document_name}
              onAccepted={(turn) => {
                acceptTurn(turn);
                setSubmittedTurn(turn.id);
                onTurnChanged();
              }}
              onConflict={reload}
            />
          </>
        )}
      </div>
      {source && conversation && (
        <SourcePanel
          key={`${source.turnId}:${source.citation.source_id}`}
          documentId={conversation.document_id}
          source={source.citation}
          onClose={() => setSource(null)}
        />
      )}
    </div>
  );
}
