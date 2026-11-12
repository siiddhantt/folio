import { useState } from 'react';
import { ArrowUp } from 'lucide-react';
import { ApiError, errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import type { Turn } from './types';
import { questionDraftKey, questionIntentKey } from './useConversation';

interface Intent {
  key: string;
  question: string;
}

function savedIntent(id: string): Intent | null {
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
    <form
      className="question-composer"
      onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}
    >
      <label className="sr-only" htmlFor="question">
        Your question
      </label>
      <textarea
        id="question"
        placeholder="Ask about this document…"
        rows={4}
        maxLength={4000}
        value={question}
        disabled={busy || !!intent}
        onChange={(event) => {
          setQuestion(event.target.value);
          sessionStorage.setItem(questionDraftKey(conversationId), event.target.value);
        }}
      />
      {error && (
        <Notice error>
          {error} {intent && 'Retry sends the same question.'}
        </Notice>
      )}
      <div className="composer-actions">
        <span className="subtle">One question per chat for now.</span>
        <Button type="submit" disabled={busy || !question.trim()} aria-label="Send question">
          {busy ? 'Sending…' : intent ? 'Retry question' : 'Send'}
          <ArrowUp aria-hidden="true" />
        </Button>
      </div>
    </form>
  );
}
