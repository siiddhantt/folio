import { Button, Notice } from '../components/ui';
import { LoaderCircle } from 'lucide-react';
import { Markdown } from '../components/Markdown';
import { AnswerSources } from './AnswerSources';
import type { Citation, Turn } from './types';

export function Answer({
  turn,
  onSource,
  onTurnReference,
}: {
  turn: Turn;
  onSource: (citation?: Citation) => void;
  onTurnReference: (turnId: string) => void;
}) {
  const active = turn.state === 'pending' || turn.state === 'running';
  const sources = turn.citations;
  return (
    <>
      <article className="question-message" aria-label="Your question">
        <p>{turn.question}</p>
      </article>
      {active ? (
        <p className="answer-pending" role="status">
          <LoaderCircle aria-hidden="true" />
          <span>
            {turn.context_state === 'preparing'
              ? 'Preparing conversation context…'
              : turn.state === 'pending'
                ? 'Waiting to answer…'
                : 'Finding evidence and preparing an answer…'}
          </span>
        </p>
      ) : turn.error ? (
        <Notice error>{turn.error.message}</Notice>
      ) : turn.answer ? (
        <article className="answer-message" aria-label="Folio answer">
          {turn.answer.outcome !== 'answer' && (
            <p className="answer-outcome">
              {turn.answer.outcome === 'clarification'
                ? 'More detail needed'
                : turn.answer.outcome === 'transcript'
                  ? 'From this conversation'
                  : 'Insufficient evidence'}
            </p>
          )}
          {turn.answer.statements.map((statement, index) => (
            <div key={index} className="answer-statement">
              <Markdown
                trailing={
                  statement.source_ids.length
                    ? statement.source_ids.map((id) => {
                        const citation = turn.citations.find((source) => source.source_id === id);
                        if (!citation) return null;
                        return (
                          <Button
                            key={id}
                            variant="ghost"
                            size="xs"
                            onClick={() => onSource(citation)}
                            aria-label={`See passage ${sources.indexOf(citation) + 1} for this statement`}
                          >
                            {sources.indexOf(citation) + 1}
                          </Button>
                        );
                      })
                    : undefined
                }
              >
                {statement.text}
              </Markdown>
              {!!statement.turn_ids?.length && (
                <div className="answer-citations">
                  {statement.turn_ids.map((id) => (
                    <Button
                      key={id}
                      variant="outline"
                      size="sm"
                      onClick={() => onTurnReference(id)}
                    >
                      View original exchange
                    </Button>
                  ))}
                </div>
              )}
            </div>
          ))}
          <AnswerSources sources={sources} onSource={onSource} />
        </article>
      ) : (
        <Notice error>No answer was saved for this question.</Notice>
      )}
    </>
  );
}
