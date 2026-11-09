import { Notice } from '../components/ui';
import type { Diagnostic, Evidence } from '../types';

function diagnosticText(item: Diagnostic): string {
  if (typeof item.message === 'string' && item.message) return item.message;
  if (typeof item.error_message === 'string' && item.error_message) return item.error_message;
  if (typeof item.code === 'string' && item.code)
    return item.code.replaceAll('_', ' ').toLowerCase();
  return 'The parser reported an extraction limitation';
}

export function CoverageNotice({
  evidence,
  onSourcePage,
}: {
  evidence: Evidence;
  onSourcePage: (page: number) => void;
}) {
  const emptyPages = evidence.pages.filter(
    (page) => page.content_observation === 'no_content_recovered',
  );
  const diagnostics = [
    ...new Map(
      [...evidence.diagnostics, ...evidence.pages.flatMap((page) => page.diagnostics)]
        .filter((item) => item.code !== 'NO_CONTENT_RECOVERED')
        .map((item) => [JSON.stringify(item), item]),
    ).entries(),
  ];
  if (!emptyPages.length && !diagnostics.length) return null;
  return (
    <Notice>
      <strong>Some content may be missing</strong>
      {emptyPages.map((page) => (
        <div className="coverage-gap" key={page.page_no}>
          <p>No text or table content was recovered on page {page.page_no}.</p>
          <button className="page-link" onClick={() => onSourcePage(page.page_no)}>
            Inspect page {page.page_no} ↗
          </button>
        </div>
      ))}
      {diagnostics.map(([key, item]) => (
        <p key={key}>
          {diagnosticText(item)}
          {typeof item.page_no === 'number' ? ` (page ${item.page_no})` : ''}.
        </p>
      ))}
      <p className="coverage-explanation">
        Gaps may be blank or unreadable content; the cause is unknown.
      </p>
    </Notice>
  );
}
