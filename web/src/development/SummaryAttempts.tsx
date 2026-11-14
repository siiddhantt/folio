import { FailureDetails } from './FailureDetails';
import type { SummaryInspection } from './types';

const timestamp = (value: string | null) =>
  value ? new Date(value).toLocaleString() : 'Not recorded';
const money = (value: number) => `$${value.toFixed(6)}`;

export function SummaryAttempts({ summary }: { summary: SummaryInspection | null }) {
  if (!summary) return null;
  return (
    <section aria-label="Summary execution" className="summary-execution">
      <h3>
        Summary <span className={`attempt-state ${summary.state}`}>{summary.state}</span>
      </h3>
      <details className="configuration-record">
        <summary>Summary record</summary>
        <dl className="identity-list">
          <dt>Run ID</dt>
          <dd>
            <code>{summary.id}</code>
          </dd>
          <dt>Created</dt>
          <dd>{timestamp(summary.created_at)}</dd>
          <dt>Started</dt>
          <dd>{timestamp(summary.started_at)}</dd>
          <dt>Finished</dt>
          <dd>{timestamp(summary.finished_at)}</dd>
          {summary.error_code && (
            <>
              <dt>Outcome</dt>
              <dd>
                <code>{summary.error_code}</code>
              </dd>
            </>
          )}
        </dl>
      </details>
      {summary.attempts.map((attempt) => (
        <details className="attempt-record" key={attempt.id}>
          <summary>
            Summary attempt {attempt.attempt_no}
            <span className={`attempt-state ${attempt.state}`}>{attempt.state}</span>
          </summary>
          <dl className="identity-list">
            <dt>Attempt ID</dt>
            <dd>
              <code>{attempt.id}</code>
            </dd>
            <dt>Started</dt>
            <dd>{timestamp(attempt.started_at)}</dd>
            <dt>Provider invoked</dt>
            <dd>{timestamp(attempt.invoked_at)}</dd>
            <dt>Finished</dt>
            <dd>{timestamp(attempt.finished_at)}</dd>
            <dt>Billing</dt>
            <dd>
              {
                {
                  not_invoked: 'Not invoked',
                  reserved: 'Awaiting result',
                  known: 'Known',
                  unknown: 'Unknown',
                }[attempt.billing_state]
              }
            </dd>
            {attempt.billing_state === 'known' && attempt.cost_usd !== null && (
              <>
                <dt>Cost</dt>
                <dd>{money(attempt.cost_usd)}</dd>
              </>
            )}
            {(attempt.billing_state === 'reserved' || attempt.billing_state === 'unknown') &&
              attempt.reserved_usd !== null && (
                <>
                  <dt>Reserved allowance</dt>
                  <dd>{money(attempt.reserved_usd)}</dd>
                </>
              )}
            <dt>Input tokens</dt>
            <dd>{attempt.usage?.prompt_tokens?.toLocaleString() ?? 'Not reported'}</dd>
            <dt>Output tokens</dt>
            <dd>{attempt.usage?.completion_tokens?.toLocaleString() ?? 'Not reported'}</dd>
            {attempt.usage?.reasoning_tokens != null && (
              <>
                <dt>Reasoning tokens</dt>
                <dd>{attempt.usage.reasoning_tokens.toLocaleString()}</dd>
              </>
            )}
            {attempt.usage?.finish_reason && (
              <>
                <dt>Finish reason</dt>
                <dd>{attempt.usage.finish_reason}</dd>
              </>
            )}
            {attempt.response_id && (
              <>
                <dt>Provider response</dt>
                <dd>
                  <code>{attempt.response_id}</code>
                </dd>
              </>
            )}
            {attempt.usage?.model && (
              <>
                <dt>Reported model</dt>
                <dd>{attempt.usage.model}</dd>
              </>
            )}
            {attempt.usage?.provider && (
              <>
                <dt>Reported provider</dt>
                <dd>{attempt.usage.provider}</dd>
              </>
            )}
            {attempt.error_code && (
              <>
                <dt>Failure</dt>
                <dd>
                  <code>{attempt.error_code}</code>
                </dd>
              </>
            )}
            <FailureDetails diagnostics={attempt.failure_diagnostics} />
          </dl>
        </details>
      ))}
    </section>
  );
}
