import type { IndexInspection } from '../types';
import { FailureDetails } from './FailureDetails';

const timestamp = (value: string | null) =>
  value ? new Date(value).toLocaleString() : 'Not recorded';
const money = (value: number) => `$${value.toFixed(8)}`;

export function IndexingAttempts({ indexing }: { indexing?: IndexInspection | null }) {
  if (!indexing) return null;
  return (
    <section aria-label="Indexing execution" className="summary-execution">
      <h3>
        Indexing{' '}
        <span className={`attempt-state ${indexing.state}`}>
          {indexing.state.replaceAll('_', ' ')}
        </span>
      </h3>
      <p>
        {indexing.embedded_chunks.toLocaleString()} of {indexing.chunk_count.toLocaleString()}{' '}
        chunks embedded
      </p>
      <details className="configuration-record">
        <summary>Index record</summary>
        <dl className="identity-list">
          <dt>Index ID</dt>
          <dd>
            <code>{indexing.index_id || 'Not started'}</code>
          </dd>
          <dt>Model</dt>
          <dd>{indexing.model_id || 'Not selected'}</dd>
          <dt>Dimensions</dt>
          <dd>{indexing.dimensions?.toLocaleString() ?? 'Not selected'}</dd>
          <dt>Created</dt>
          <dd>{timestamp(indexing.created_at)}</dd>
          <dt>Started</dt>
          <dd>{timestamp(indexing.started_at)}</dd>
          <dt>Finished</dt>
          <dd>{timestamp(indexing.finished_at)}</dd>
          <dt>Eligible at</dt>
          <dd>{timestamp(indexing.available_at)}</dd>
          <dt>Ownership deadline</dt>
          <dd>{timestamp(indexing.lease_expires_at)}</dd>
          <dt>Excluded source elements</dt>
          <dd>{indexing.exclusions.length.toLocaleString()}</dd>
          <dt>Pages without recovered content</dt>
          <dd>{indexing.coverage.pages_without_content.length.toLocaleString()}</dd>
          {indexing.dispatch_error && (
            <>
              <dt>Delivery error</dt>
              <dd>{indexing.dispatch_error}</dd>
            </>
          )}
          {indexing.error_code && (
            <>
              <dt>Outcome</dt>
              <dd>
                <code>{indexing.error_code}</code>
              </dd>
            </>
          )}
        </dl>
      </details>
      {indexing.has_more && <p className="subtle">Showing the latest 50 attempts.</p>}
      {indexing.attempts.map((attempt) => (
        <details className="attempt-record" key={attempt.id}>
          <summary>
            Indexing attempt {attempt.attempt_no}
            <span className={`attempt-state ${attempt.state}`}>{attempt.state}</span>
          </summary>
          <dl className="identity-list">
            <dt>Attempt ID</dt>
            <dd>
              <code>{attempt.id}</code>
            </dd>
            <dt>Batch</dt>
            <dd>{attempt.batch_no ?? 'Preparing chunks'}</dd>
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
                  none: 'Not invoked',
                  reserved: 'Awaiting result',
                  known: 'Known',
                  unknown: 'Unknown',
                }[attempt.billing_state]
              }
            </dd>
            {attempt.billing_state === 'known' && attempt.cost_usd != null && (
              <>
                <dt>Cost</dt>
                <dd>{money(attempt.cost_usd)}</dd>
              </>
            )}
            {(attempt.billing_state === 'reserved' || attempt.billing_state === 'unknown') &&
              attempt.reserved_usd != null && (
                <>
                  <dt>Reserved allowance</dt>
                  <dd>{money(attempt.reserved_usd)}</dd>
                </>
              )}
            <dt>Reported input tokens</dt>
            <dd>{attempt.usage.prompt_tokens?.toLocaleString() ?? 'Not reported'}</dd>
            {attempt.usage.input_tokens != null && (
              <>
                <dt>Reserved input tokens</dt>
                <dd>{attempt.usage.input_tokens.toLocaleString()}</dd>
              </>
            )}
            {attempt.chunk_ordinals.length > 0 && (
              <>
                <dt>Chunk numbers</dt>
                <dd>{attempt.chunk_ordinals.join(', ')}</dd>
              </>
            )}
            {attempt.input_hash && (
              <>
                <dt>Batch input hash</dt>
                <dd>
                  <code>{attempt.input_hash}</code>
                </dd>
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
            {attempt.usage.model && (
              <>
                <dt>Reported model</dt>
                <dd>{attempt.usage.model}</dd>
              </>
            )}
            {attempt.usage.requested_provider && (
              <>
                <dt>Requested provider</dt>
                <dd>{attempt.usage.requested_provider}</dd>
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
