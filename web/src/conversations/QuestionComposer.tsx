import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowUp } from 'lucide-react';
import { ApiError, errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import type { Turn } from './types';
import { questionDraftKey, questionIntentKey } from './useConversation';

export interface QuestionIntent {
  key: string;
  question: string;
}

function savedIntent(id: string): QuestionIntent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(questionIntentKey(id)) || 'null');
    return typeof value?.key === 'string' && typeof value?.question === 'string' ? value : null;
  } catch {
    return null;
  }
}

export function QuestionComposer({
  conversationId,
  onAccepted,
  onConflict,
}: {
  conversationId: string;
  onAccepted: (turn: Turn) => void;
  onConflict: () => void;
}) {
  const [intent, setIntent] = useState(() => savedIntent(conversationId));
  const [question, setQuestion] = useState(
    () => intent?.question || sessionStorage.getItem(questionDraftKey(conversationId)) || '',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function send() {
    if (busy || !question.trim()) return;
    const operation = intent || { key: crypto.randomUUID(), question: question.trim() };
    setIntent(operation);
    sessionStorage.setItem(questionIntentKey(conversationId), JSON.stringify(operation));
    setBusy(true);
    setError('');
    try {
      const turn = await request<Turn>(`/conversations/${conversationId}/turns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation.key },
        body: JSON.stringify({ question: operation.question }),
      });
      sessionStorage.removeItem(questionIntentKey(conversationId));
      sessionStorage.removeItem(questionDraftKey(conversationId));
      onAccepted(turn);
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof ApiError && [400, 409, 422].includes(e.status)) {
        sessionStorage.removeItem(questionIntentKey(conversationId));
        setIntent(null);
        if (e.status === 409) onConflict();
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <QuestionInput
      question={question}
      onChange={(value) => {
        setQuestion(value);
        sessionStorage.setItem(questionDraftKey(conversationId), value);
      }}
      onSend={send}
      busy={busy}
      locked={!!intent}
      retry={!!intent}
      error={error && `${error}${intent ? ' Retry sends the same question.' : ''}`}
      scope={<span className="subtle">One question per chat for now.</span>}
    />
  );
}

export function QuestionInput({
  question,
  onChange,
  onSend,
  busy = false,
  locked = false,
  retry = false,
  unavailable = false,
  error = '',
  scope,
}: {
  question: string;
  onChange: (value: string) => void;
  onSend: () => void | Promise<void>;
  busy?: boolean;
  locked?: boolean;
  retry?: boolean;
  unavailable?: boolean;
  error?: string;
  scope?: ReactNode;
}) {
  const id = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const textarea = input.current;
    if (!textarea) return;
    const resize = () => {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    };
    resize();
    let width = textarea.clientWidth;
    const observer = new ResizeObserver(() => {
      if (textarea.clientWidth !== width) {
        width = textarea.clientWidth;
        resize();
      }
    });
    observer.observe(textarea);
    return () => observer.disconnect();
  }, [question]);
  return (
    <form
      className="question-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (!busy && !unavailable) void onSend();
      }}
    >
      <div className="composer-surface">
        <label className="sr-only" htmlFor={id}>
          Your question
        </label>
        <textarea
          ref={input}
          id={id}
          name="question"
          placeholder="Ask about this document…"
          rows={2}
          maxLength={4000}
          value={question}
          disabled={busy || locked}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
        <div className="composer-actions">
          <div className="composer-scope">{scope}</div>
          <Button
            type="submit"
            disabled={busy || unavailable || !question.trim()}
            aria-label="Send question"
          >
            {busy ? 'Sending…' : retry ? 'Retry question' : 'Send'}
            <ArrowUp aria-hidden="true" />
          </Button>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
    </form>
  );
}
