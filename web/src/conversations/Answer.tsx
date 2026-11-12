import { Button, Notice } from '../components/ui';
import type { Citation, Turn } from './types';

export function Answer({ turn, onSource }: { turn: Turn; onSource: (citation: Citation) => void }) {
  const active = turn.state === 'pending' || turn.state === 'running';
  return (
    <>
      <article className="question-message" aria-label="Your question">
        <p>{turn.question}</p>
      </article>
      {active ? (
        <p className="answer-pending" role="status">
          {turn.state === 'pending'
            ? 'Waiting to answer…'
            : 'Finding evidence and preparing an answer…'}
        </p>
      ) : turn.error ? (
        <Notice error>{turn.error.message}</Notice>
      ) : turn.answer ? (
        <article className="answer-message" aria-label="Folio answer">
          {turn.answer.outcome !== 'answer' && (
            <p className="answer-outcome">
              {turn.answer.outcome === 'clarification'
                ? 'More detail needed'
                : 'Insufficient evidence'}
            </p>
          )}
          {turn.answer.statements.map((statement, index) => (
            <div key={index} className="answer-statement">
              <p>{statement.text}</p>
              {!!statement.source_ids.length && (
                <div className="answer-citations">
                  {statement.source_ids.map((id) => {
                    const citation = turn.citations.find((source) => source.source_id === id);
                    if (!citation) return null;
                    return (
                      <Button
                        key={id}
                        variant="outline"
                        size="sm"
                        onClick={() => onSource(citation)}
                        aria-label={`Source ${id}, page ${citation.pages[0]}`}
                      >
                        {citation.pages.length > 1 ? 'Pages' : 'Page'} {citation.pages.join(', ')}
                      </Button>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </article>
      ) : (
        <Notice error>No answer was saved for this question.</Notice>
      )}
      {(turn.coverage.pages_without_content.length > 0 || turn.coverage.diagnostics.length > 0) && (
        <p className="chat-coverage" role="note">
          Some document content may be missing.{' '}
          <span>Check the document’s extraction details when verifying this answer.</span>
        </p>
      )}
    </>
  );
}
