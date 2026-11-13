import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { QuestionInput } from './QuestionComposer';
import type { Conversation, Turn } from './types';
import {
  questionDraftKey,
  questionIntentKey,
  newChatDraftKey as draftKey,
  newChatIntentKey as intentKey,
  clearSubmittedDraft,
} from './storage';

interface DocumentChoice {
  document_id: string;
  index_id: string;
  display_name: string;
  created_at: string;
}
interface DocumentChoices {
  items: DocumentChoice[];
  next_cursor: string | null;
}
interface Draft {
  id: string;
  document: DocumentChoice | null;
  question: string;
}
interface NewChatIntent extends Draft {
  document: DocumentChoice;
  creationKey: string;
  questionKey: string;
  conversationId?: string;
}

function savedDraft(): Draft {
  try {
    const value = JSON.parse(sessionStorage.getItem(draftKey) || 'null');
    return {
      id: typeof value?.id === 'string' ? value.id : crypto.randomUUID(),
      question: typeof value?.question === 'string' ? value.question : '',
      document: typeof value?.document?.index_id === 'string' ? value.document : null,
    };
  } catch {
    return { id: crypto.randomUUID(), document: null, question: '' };
  }
}

function savedIntent(): NewChatIntent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(intentKey) || 'null');
    if (
      typeof value?.conversationId === 'string' &&
      !sessionStorage.getItem(questionIntentKey(value.conversationId))
    ) {
      // The saved chat confirmed or resolved the transferred submission.
      sessionStorage.removeItem(intentKey);
      clearSubmittedDraft(value);
      return null;
    }
    return typeof value?.id === 'string' &&
      typeof value?.creationKey === 'string' &&
      typeof value?.questionKey === 'string' &&
      typeof value?.question === 'string' &&
      typeof value?.document?.index_id === 'string'
      ? value
      : null;
  } catch {
    return null;
  }
}

function ownsIntent(operation: NewChatIntent): boolean {
  try {
    const current = JSON.parse(sessionStorage.getItem(intentKey) || 'null');
    return (
      current?.creationKey === operation.creationKey &&
      current?.questionKey === operation.questionKey
    );
  } catch {
    return false;
  }
}

function clearTransferredIntent(operation: NewChatIntent, keepDraft = false) {
  if (!operation.conversationId) return;
  const key = questionIntentKey(operation.conversationId);
  try {
    if (JSON.parse(sessionStorage.getItem(key) || 'null')?.key === operation.questionKey) {
      sessionStorage.removeItem(key);
      if (!keepDraft) sessionStorage.removeItem(questionDraftKey(operation.conversationId));
    }
  } catch {
    /* Leave a different pending submission untouched. */
  }
}

export function NewConversationPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const preselected = params.get('document');
  const mounted = useRef(true);
  const [intent, setIntent] = useState(savedIntent);
  const [draft, setDraft] = useState<Draft>(() =>
    intent ? { id: intent.id, document: intent.document, question: intent.question } : savedDraft(),
  );
  const [documents, setDocuments] = useState<DocumentChoice[]>([]);
  const [before, setBefore] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [listError, setListError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [selectionLoading, setSelectionLoading] = useState(!!preselected && !intent);
  const [selectionError, setSelectionError] = useState('');
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!preselected || intent) return;
    const controller = new AbortController();
    setSelectionLoading(true);
    setSelectionError('');
    setDraft((previous) => {
      const next = { ...previous, document: null };
      sessionStorage.setItem(draftKey, JSON.stringify(next));
      return next;
    });
    request<DocumentChoices>(
      `/conversation-documents?index_id=${encodeURIComponent(preselected)}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        const document = result.items[0] || null;
        setDraft((previous) => {
          const next = { ...previous, document };
          sessionStorage.setItem(draftKey, JSON.stringify(next));
          return next;
        });
        if (!document)
          setSelectionError(
            'This document is not ready for a new chat. Choose another document or check its processing run.',
          );
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setSelectionError(errorMessage(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setSelectionLoading(false);
      });
    return () => controller.abort();
  }, [preselected]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError('');
    request<DocumentChoices>(
      `/conversation-documents?limit=20${before ? `&before=${encodeURIComponent(before)}` : ''}`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        setDocuments((previous) =>
          before
            ? [
                ...previous,
                ...result.items.filter(
                  (item) => !previous.some((value) => value.index_id === item.index_id),
                ),
              ]
            : result.items,
        );
        setNextCursor(result.next_cursor);
        setLoaded(true);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setListError(errorMessage(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [before, refresh]);

  function changeDraft(value: Draft) {
    setDraft(value);
    sessionStorage.setItem(draftKey, JSON.stringify(value));
  }

  async function send() {
    if (busy || !draft.document || !draft.question.trim()) return;
    let operation: NewChatIntent = intent || {
      ...draft,
      document: draft.document,
      question: draft.question.trim(),
      creationKey: crypto.randomUUID(),
      questionKey: crypto.randomUUID(),
    };
    setIntent(operation);
    sessionStorage.setItem(intentKey, JSON.stringify(operation));
    setBusy(true);
    setError('');
    try {
      if (!operation.conversationId) {
        const conversation = await request<Conversation>('/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation.creationKey },
          body: JSON.stringify({ index_id: operation.document.index_id }),
        });
        operation = { ...operation, conversationId: conversation.id };
      }
      if (!ownsIntent(operation)) return;
      const id = operation.conversationId!;
      sessionStorage.setItem(
        questionIntentKey(id),
        JSON.stringify({
          key: operation.questionKey,
          question: operation.question,
          observed_head: 0,
        }),
      );
      sessionStorage.setItem(questionDraftKey(id), operation.question);
      sessionStorage.setItem(intentKey, JSON.stringify(operation));
      if (!mounted.current) return;
      setIntent(operation);
      await request<Turn>(`/conversations/${id}/turns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation.questionKey },
        body: JSON.stringify({ question: operation.question, observed_head: 0 }),
      });
      clearTransferredIntent(operation);
      if (ownsIntent(operation)) {
        sessionStorage.removeItem(intentKey);
        clearSubmittedDraft(operation);
        if (mounted.current)
          navigate(`/conversations/${id}`, { state: { createdConversation: id } });
      }
    } catch (reason) {
      if (reason instanceof ApiError && [404, 410].includes(reason.status)) {
        if (ownsIntent(operation)) {
          sessionStorage.removeItem(intentKey);
          clearTransferredIntent(operation);
          if (mounted.current) {
            setIntent(null);
            setError(
              'This chat is no longer available. Your question is ready to send in a new chat.',
            );
          }
        }
        return;
      }
      if (
        reason instanceof ApiError &&
        [400, 409, 422].includes(reason.status) &&
        ownsIntent(operation)
      ) {
        sessionStorage.removeItem(intentKey);
        if (mounted.current) setIntent(null);
        if (operation.conversationId) {
          clearTransferredIntent(operation, reason.status === 409);
          if (reason.status === 409) clearSubmittedDraft(operation);
          if (mounted.current)
            navigate(`/conversations/${operation.conversationId}`, {
              state: { createdConversation: operation.conversationId },
            });
          return;
        }
      }
      if (mounted.current) setError(errorMessage(reason));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  const choices =
    draft.document && !documents.some((value) => value.index_id === draft.document!.index_id)
      ? [draft.document, ...documents]
      : documents;
  return (
    <section className="new-conversation-page" aria-labelledby="new-chat-title">
      <h1 id="new-chat-title">New chat</h1>
      <QuestionInput
        question={draft.question}
        onChange={(question) => changeDraft({ ...draft, question })}
        onSend={send}
        busy={busy}
        locked={!!intent}
        retry={!!intent}
        unavailable={!draft.document || selectionLoading}
        error={error && `${error}${intent ? ' Retry sends the same question.' : ''}`}
        scope={
          <>
            <label className="sr-only" htmlFor="chat-document">
              Document
            </label>
            <Select
              name="document"
              value={draft.document?.index_id || ''}
              disabled={busy || !!intent || selectionLoading || !choices.length}
              onValueChange={(value) => {
                setSelectionError('');
                changeDraft({
                  ...draft,
                  document: choices.find((choice) => choice.index_id === value) || null,
                });
              }}
            >
              <SelectTrigger id="chat-document" title={draft.document?.display_name}>
                <SelectValue placeholder="Choose a document" />
              </SelectTrigger>
              <SelectContent>
                {choices.map((document) => (
                  <SelectItem key={document.index_id} value={document.index_id}>
                    {document.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />
      <p className="subtle document-choice-status" role="status">
        {loading || selectionLoading ? 'Loading documents…' : ''}
      </p>
      {selectionError && <Notice error>{selectionError}</Notice>}
      {listError && (
        <Notice error>
          {listError}{' '}
          <button className="inline-retry" onClick={() => setRefresh((value) => value + 1)}>
            Retry documents
          </button>
        </Notice>
      )}
      {loaded && !choices.length && !listError && !selectionLoading && (
        <p className="subtle">
          No documents are ready for chat. <Link to="/upload">Upload a PDF</Link> or{' '}
          <Link to="/runs">check processing runs</Link>.
        </p>
      )}
      {nextCursor && (
        <Button variant="ghost" size="sm" disabled={loading} onClick={() => setBefore(nextCursor)}>
          More documents
        </Button>
      )}
      {intent && !busy && !error && (
        <p className="subtle">
          Your last submission needs confirmation. Retry sends the same question.
        </p>
      )}
    </section>
  );
}
