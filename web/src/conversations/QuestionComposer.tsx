import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ApiError, errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import type { Turn } from './types';
import { questionDraftKey, questionIntentKey } from './storage';

export interface QuestionIntent {
  key: string;
  question: string;
  observed_head: number;
}

function savedIntent(id: string): QuestionIntent | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(questionIntentKey(id)) || 'null');
    return typeof value?.key === 'string' && typeof value?.question === 'string'
      ? {
          key: value.key,
          question: value.question,
          observed_head: Number.isInteger(value.observed_head) ? value.observed_head : 0,
        }
      : null;
  } catch {
    return null;
  }
}

export function QuestionComposer({
  conversationId,
  observedHead,
  waiting,
  documentName,
  onAccepted,
  onConflict,
}: {
  conversationId: string;
  observedHead: number;
  waiting: boolean;
  documentName: string;
  onAccepted: (turn: Turn) => void;
  onConflict: () => void;
}) {
  const [intent, setIntent] = useState(() => savedIntent(conversationId));
  const [question, setQuestion] = useState(
    () => intent?.question || sessionStorage.getItem(questionDraftKey(conversationId)) || '',
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);
  function ownsIntent(operation: QuestionIntent) {
    const current = savedIntent(conversationId);
    return (
      current?.key === operation.key &&
      current?.question === operation.question &&
      current?.observed_head === operation.observed_head
    );
  }
  async function send() {
    if (busy || missing || !question.trim()) return;
    if (waiting && !intent) return;
    const operation = intent || {
      key: crypto.randomUUID(),
      question: question.trim(),
      observed_head: observedHead,
    };
    setIntent(operation);
    sessionStorage.setItem(questionIntentKey(conversationId), JSON.stringify(operation));
    setBusy(true);
    setError('');
    try {
      const turn = await request<Turn>(`/conversations/${conversationId}/turns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation.key },
        body: JSON.stringify({
          question: operation.question,
          observed_head: operation.observed_head,
        }),
      });
      if (!ownsIntent(operation)) return;
      sessionStorage.removeItem(questionIntentKey(conversationId));
      sessionStorage.removeItem(questionDraftKey(conversationId));
      setIntent(null);
      setQuestion('');
      onAccepted(turn);
    } catch (e) {
      if (!ownsIntent(operation)) return;
      setError(errorMessage(e));
      if (e instanceof ApiError && [400, 404, 409, 410, 422].includes(e.status)) {
        sessionStorage.removeItem(questionIntentKey(conversationId));
        setIntent(null);
        if ([404, 410].includes(e.status)) setMissing(true);
        if (e.status === 409) onConflict();
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
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
        unavailable={missing || (waiting && !intent)}
        error={error && `${error}${intent ? ' Retry sends the same question.' : ''}`}
        scope={<span className="subtle">{documentName}</span>}
      />
      {missing && (
        <p className="subtle">
          <Link to="/new-chat">Start a new chat</Link> to ask this question.
        </p>
      )}
    </>
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
          rows={1}
          maxLength={4000}
          value={question}
          disabled={busy || locked}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          onKeyDown={(event) => {
            if (
              event.key === 'Enter' &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing &&
              event.nativeEvent.keyCode !== 229
            ) {
              event.preventDefault();
              if (!busy && !unavailable && question.trim())
                event.currentTarget.form?.requestSubmit();
            }
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
      <p className="composer-notice">AI-generated answers. Check the sources.</p>
      {error && <Notice error>{error}</Notice>}
    </form>
  );
}
