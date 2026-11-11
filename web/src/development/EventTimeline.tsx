import type { ProcessingEvent } from './useInspection';

const labels: Record<string, string> = {
  accepted: 'Upload accepted',
  delivery_requested: 'Queue delivery requested',
  delivery_deferred: 'Queue delivery deferred',
  delivery_resumed: 'Queue delivery resumed',
  worker_claimed: 'Worker claimed attempt',
  source_verified: 'Original verified',
  parse_started: 'Parsing started',
  parse_completed: 'Parsing completed',
  raw_result_saved: 'Raw result saved',
  published: 'Evidence published',
  attempt_failed: 'Attempt failed',
  retry_scheduled: 'Retry scheduled',
};

export function localTime(value: string | null): string {
  return value
    ? new Date(value).toLocaleTimeString([], {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      })
    : 'Not recorded';
}

export function EventTimeline({
  events,
  attempts,
}: {
  events: ProcessingEvent[];
  attempts: { id: string; attempt_no: number }[];
}) {
  return (
    <ol className="event-timeline" aria-label="Recorded processing events">
      {events.map((event) => {
        const number = attempts.find((attempt) => attempt.id === event.attempt_id)?.attempt_no;
        return (
          <li
            key={event.id}
            className={
              event.name === 'attempt_failed' || event.name === 'delivery_deferred'
                ? 'event-warning'
                : ''
            }
          >
            <time dateTime={event.occurred_at}>{localTime(event.occurred_at)}</time>
            <div>
              <p className="event-name">{labels[event.name] || event.name.replaceAll('_', ' ')}</p>
              <p className="event-description">
                Attempt {number ?? 'unknown'}
                {typeof event.details.duration_seconds === 'number' &&
                  ` · ${event.details.duration_seconds.toFixed(3)} s measured`}
                {typeof event.details.error_code === 'string' && ` · ${event.details.error_code}`}
                {typeof event.details.pages === 'number' &&
                  ` · ${event.details.pages} source pages`}
                {typeof event.details.elements === 'number' &&
                  ` · ${event.details.elements} elements`}
                {typeof event.details.delay_seconds === 'number' &&
                  ` · ${event.details.delay_seconds.toFixed(1)} s scheduled delay`}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
