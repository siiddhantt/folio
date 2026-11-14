import { Notice } from '../components/ui';
import { SourcePages } from '../documents/SourcePages';
import type { SummaryClaim } from './types';
import { useSummary } from './useSummary';

export function SummaryPanel({
  revisionId,
  onSourcePage,
}: {
  revisionId: string;
  onSourcePage: (page: number) => void;
}) {
  const { summary, error } = useSummary(revisionId);
  if (summary?.state === 'not_scheduled') return null;
  const ready = summary?.state === 'ready';
  const gaps =
    summary &&
    (summary.coverage.pages_without_content.length > 0 || summary.coverage.diagnostics.length > 0);
  function claim(item: SummaryClaim) {
    const pages = summary!.citations
      .filter((citation) => item.source_ids.includes(citation.source_id))
      .flatMap((citation) => citation.pages);
    return (
      <>
        {item.text} <SourcePages pages={pages} onSourcePage={onSourcePage} />
      </>
    );
  }
  return (
    <section className="summary-panel" aria-label="Document summary" aria-live="polite">
      <div className="section-caption">
        <h2>Summary</h2>
      </div>
      {error ? (
        <Notice error>{error}</Notice>
      ) : ready && summary?.overview ? (
        <>
          {gaps && (
            <Notice>
              This summary covers recovered content. Some source content may be missing.
            </Notice>
          )}
          <p>{claim(summary.overview)}</p>
          <ul className="summary-points">
            {summary.points.map((point, index) => (
              <li key={index}>{claim(point)}</li>
            ))}
          </ul>
        </>
      ) : summary?.error ? (
        <p className="subtle">{summary.error.message}</p>
      ) : (
        <p className="subtle">Preparing summary…</p>
      )}
    </section>
  );
}
