import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, FileText } from 'lucide-react';
import { Button, Notice } from '../components/ui';
import { Answer } from './Answer';
import { NewChatButton } from './NewChatButton';
import { QuestionComposer } from './QuestionComposer';
import { SourcePanel } from './SourcePanel';
import { useConversation } from './useConversation';
import type { Citation } from './types';

export function ConversationPage() {
  const { conversationId = '' } = useParams();
  return <ConversationWorkspace key={conversationId} id={conversationId} />;
}

function ConversationWorkspace({ id }: { id: string }) {
  const { conversation, turn, error, loaded, setTurn, reload } = useConversation(id);
  const [source, setSource] = useState<Citation | null>(null);
  const active = turn?.state === 'pending' || turn?.state === 'running';
  return (
    <div className="chat-page">
      <div className="chat-heading">
        <div className="chat-heading-title">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/" aria-label="All conversations">
              <ArrowLeft aria-hidden="true" />
            </Link>
          </Button>
          <h1>{conversation?.document_name || 'Conversation'}</h1>
        </div>
        {conversation && (
          <Button variant="outline" size="sm" asChild>
            <Link to={`/documents/${conversation.document_id}`}>
              <FileText aria-hidden="true" />
              Document
            </Link>
          </Button>
        )}
      </div>
      <div className="chat-content">
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
        {loaded &&
          conversation &&
          (turn ? (
            <>
              <Answer turn={turn} onSource={setSource} />
              {!active && (
                <div className="chat-complete">
                  <p className="subtle">One question per chat for now.</p>
                  <NewChatButton indexId={conversation.index_id} />
                </div>
              )}
            </>
          ) : (
            <QuestionComposer conversationId={id} onAccepted={setTurn} onConflict={reload} />
          ))}
      </div>
      {source && conversation && (
        <SourcePanel
          key={source.source_id}
          documentId={conversation.document_id}
          source={source}
          onClose={() => setSource(null)}
        />
      )}
    </div>
  );
}
