import { Link, useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { Button, Notice } from '../components/ui';
import type { ProcessingRun } from './types';
import { useRuns } from './useRuns';

function extractionLabel(run: ProcessingRun) {
  if (run.extraction_state === 'succeeded') return 'Evidence available';
  if (run.extraction_state === 'failed') return 'Failed';
  return run.current_attempt_state === 'running' ? 'Processing' : 'Waiting';
}

function summaryLabel(run: ProcessingRun) {
  if (run.summary_error_code === 'SUMMARY_DISABLED') return 'Disabled';
  return {
    not_scheduled: 'Not scheduled',
    pending: 'Waiting',
    running: 'Generating',
    ready: 'Ready',
    unavailable: 'Unavailable',
    failed: 'Failed',
  }[run.summary_state];
}

export function RunsPage() {
  const [params, setParams] = useSearchParams();
  const before = params.get('before');
  const { data, error, loading, reload } = useRuns(before);
  return (
    <section className="runs-page" aria-labelledby="runs-heading">
      <div className="runs-heading">
        <h1 id="runs-heading">Processing runs</h1>
        <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
          <RefreshCw aria-hidden="true" /> Refresh
        </Button>
      </div>
      {error && <Notice error>{error} Use Refresh to try again.</Notice>}
      {loading && (
        <p className="subtle" role="status">
          Loading runs…
        </p>
      )}
      {data && !data.items.length && (
        <p className="runs-empty">
          No processing runs here. <Link to="/upload">Upload a PDF</Link>
        </p>
      )}
      {!!data?.items.length && (
        <table className="runs-table" aria-label="Processing runs">
          <thead>
            <tr>
              <th>Document</th>
              <th>Uploaded</th>
              <th>Extraction</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((run) => (
              <tr key={run.request_id}>
                <td className="run-document">
                  <Link to={`/documents/${run.document_id}`}>{run.filename}</Link>
                </td>
                <td data-label="Uploaded">
                  <time dateTime={run.accepted_at}>
                    {new Date(run.accepted_at).toLocaleString(undefined, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </time>
                </td>
                <td
                  data-label="Extraction"
                  className={run.extraction_state === 'failed' ? 'run-failed' : ''}
                >
                  {extractionLabel(run)}
                </td>
                <td
                  data-label="Summary"
                  className={run.summary_state === 'failed' ? 'run-failed' : ''}
                >
                  {summaryLabel(run)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {(before || data?.next_cursor) && (
        <nav className="runs-pagination" aria-label="Run pages">
          <Button
            variant="outline"
            size="sm"
            disabled={!before || loading}
            onClick={() => setParams({})}
          >
            Newest
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!data?.next_cursor || loading}
            onClick={() => {
              if (data?.next_cursor) setParams({ before: data.next_cursor });
            }}
          >
            Older
          </Button>
        </nav>
      )}
    </section>
  );
}
