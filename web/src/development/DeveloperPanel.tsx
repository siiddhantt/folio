import { useState } from 'react';
import { Dialog } from 'radix-ui';
import { Activity, X } from 'lucide-react';
import { Button, formatBytes, Notice } from '../components/ui';
import { EventTimeline, localTime } from './EventTimeline';
import { useInspection } from './useInspection';
import { FailureDetails } from './FailureDetails';
import { SummaryAttempts } from './SummaryAttempts';
import { IndexingAttempts } from './IndexingAttempts';

export function DeveloperPanel({ requestId }: { requestId: string }) {
  const [open, setOpen] = useState(false);
  const { data, error, reconnect } = useInspection(requestId, open);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="outline" size="sm">
          <Activity aria-hidden="true" />
          Activity
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="activity-overlay" />
        <Dialog.Content className="activity-panel">
          <header className="activity-heading">
            <Dialog.Title>Activity</Dialog.Title>
            <Dialog.Description className="sr-only">
              Recorded processing events and settings for this document.
            </Dialog.Description>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close activity">
                <X aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </header>
          <section aria-label="Development inspection" className="developer-content" tabIndex={0}>
            {error && (
              <Notice error>
                {error}{' '}
                <Button variant="outline" onClick={reconnect}>
                  Reconnect details
                </Button>
              </Notice>
            )}
            {!data && !error && <p>Loading processing history…</p>}
            {data && (
              <div className="inspection-grid">
                <div>
                  <h3>Extraction events</h3>
                  {data.events.length ? (
                    <EventTimeline events={data.events} attempts={data.attempts} />
                  ) : (
                    <p className="subtle">No stage history was recorded for this upload.</p>
                  )}
                  <p className="inspection-note">Local times. History may have gaps.</p>
                </div>
                <div className="inspection-records">
                  <details className="configuration-record">
                    <summary>Document details</summary>
                    <dl className="identity-list">
                      <dt>Request</dt>
                      <dd>
                        <code>{data.request_id}</code>
                      </dd>
                      <dt>Document</dt>
                      <dd>
                        <code>{data.document_id}</code>
                      </dd>
                      <dt>Original</dt>
                      <dd>
                        {formatBytes(data.source.byte_size)} · {data.source.media_type}
                      </dd>
                      <dt>SHA-256</dt>
                      <dd>
                        <code>{data.source.sha256}</code>
                      </dd>
                    </dl>
                  </details>
                  {data.attempts.map((attempt) => (
                    <details className="attempt-record" key={attempt.id}>
                      <summary>
                        Extraction attempt {attempt.attempt_no}
                        <span className={`attempt-state ${attempt.state}`}>{attempt.state}</span>
                      </summary>
                      <dl className="identity-list">
                        <dt>Attempt ID</dt>
                        <dd>
                          <code>{attempt.id}</code>
                        </dd>
                        <dt>Eligible at</dt>
                        <dd>{localTime(attempt.available_at)}</dd>
                        <dt>Started</dt>
                        <dd>{localTime(attempt.started_at)}</dd>
                        <dt>Finished</dt>
                        <dd>{localTime(attempt.finished_at)}</dd>
                        <dt>Ownership deadline</dt>
                        <dd>{localTime(attempt.lease_expires_at)}</dd>
                        <dt>Delivery reservations</dt>
                        <dd>{attempt.dispatch_count}</dd>
                        <dt>Enqueue acknowledged</dt>
                        <dd>{localTime(attempt.last_dispatched_at)}</dd>
                        <dt>Transport job</dt>
                        <dd>
                          <code>{attempt.transport_job_id || 'Not recorded'}</code>
                        </dd>
                        {attempt.dispatch_error && (
                          <>
                            <dt>Delivery error</dt>
                            <dd>{attempt.dispatch_error}</dd>
                          </>
                        )}
                        {attempt.error_code && (
                          <>
                            <dt>Failure</dt>
                            <dd>
                              {attempt.error_code}: {attempt.error_detail}
                            </dd>
                          </>
                        )}
                        {attempt.retryable !== null && (
                          <>
                            <dt>Retryable</dt>
                            <dd>{attempt.retryable ? 'Yes' : 'No'}</dd>
                          </>
                        )}
                        {attempt.parser_status && (
                          <>
                            <dt>Parser status</dt>
                            <dd>{attempt.parser_status}</dd>
                          </>
                        )}
                        {Object.entries(attempt.metrics ?? {}).map(([name, value]) => (
                          <div className="configuration-pair" key={name}>
                            <dt>{name.replaceAll('_', ' ')}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                        <FailureDetails diagnostics={attempt.failure_diagnostics} />
                      </dl>
                    </details>
                  ))}
                  <SummaryAttempts summary={data.summary} />
                  <IndexingAttempts indexing={data.indexing} />
                  <details className="configuration-record">
                    <summary>Configuration for this request</summary>
                    <dl className="identity-list">
                      {Object.entries(data.configuration).map(([name, value]) => (
                        <div className="configuration-pair" key={name}>
                          <dt>{name.replaceAll('_', ' ')}</dt>
                          <dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                  {data.summary_configuration && (
                    <details className="configuration-record">
                      <summary>Summary settings for this request</summary>
                      <dl className="identity-list">
                        {Object.entries(data.summary_configuration).map(([name, value]) => (
                          <div className="configuration-pair" key={name}>
                            <dt>{name.replaceAll('_', ' ')}</dt>
                            <dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd>
                          </div>
                        ))}
                      </dl>
                    </details>
                  )}
                </div>
              </div>
            )}
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
