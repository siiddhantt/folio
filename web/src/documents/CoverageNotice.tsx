import { useMemo, useState } from 'react';
import { Button } from '../components/ui';
import type { Evidence } from '../types';
import { describeCoverage, diagnosticText, rangeLabel } from './coverage';

function PageControls({
  page,
  total,
  label,
  onChange,
}: {
  page: number;
  total: number;
  label: string;
  onChange: (page: number) => void;
}) {
  if (total <= 10) return null;
  return (
    <div className="coverage-pagination">
      <Button
        variant="ghost"
        size="sm"
        disabled={page === 0}
        aria-label={`Previous ${label} page`}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </Button>
      <span>
        {page + 1} / {Math.ceil(total / 10)}
      </span>
      <Button
        variant="ghost"
        size="sm"
        disabled={(page + 1) * 10 >= total}
        aria-label={`Next ${label} page`}
        onClick={() => onChange(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}

export function CoverageNotice({
  evidence,
  onSourcePage,
}: {
  evidence: Evidence;
  onSourcePage: (page: number) => void;
}) {
  const coverage = useMemo(() => describeCoverage(evidence), [evidence]);
  const [open, setOpen] = useState(false);
  const [rangePage, setRangePage] = useState(0);
  const [diagnosticPage, setDiagnosticPage] = useState(0);
  if (!coverage.partial) return null;
  return (
    <aside className="coverage-notice" role="note" aria-label="Extraction coverage">
      <p>
        <strong>
          Content recovered from {coverage.recovered.toLocaleString()} of{' '}
          {coverage.total.toLocaleString()} pages.
        </strong>
      </p>
      <p>
        {coverage.timedOut
          ? 'Processing reached its time limit. Some content may be missing.'
          : 'Some content may be missing. Gaps may be blank or unreadable; their cause is unknown.'}
      </p>
      <details onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>Coverage details</summary>
        {open && (
          <div className="coverage-details">
            {coverage.ranges.length > 0 && (
              <>
                <h3>No text or table content recovered</h3>
                <div className="coverage-ranges">
                  {coverage.ranges.slice(rangePage * 10, (rangePage + 1) * 10).map((range) => (
                    <Button
                      key={range.start}
                      variant="outline"
                      size="sm"
                      onClick={() => onSourcePage(range.start)}
                    >
                      Inspect {rangeLabel(range)}
                    </Button>
                  ))}
                </div>
                <PageControls
                  page={rangePage}
                  total={coverage.ranges.length}
                  label="range"
                  onChange={setRangePage}
                />
              </>
            )}
            {coverage.diagnostics.length > 0 && (
              <>
                <h3>Reported limitations ({coverage.diagnostics.length.toLocaleString()})</h3>
                <ul>
                  {coverage.diagnostics
                    .slice(diagnosticPage * 10, (diagnosticPage + 1) * 10)
                    .map((item, index) => (
                      <li key={diagnosticPage * 10 + index}>
                        {diagnosticText(item)}
                        {typeof item.page_no === 'number'
                          ? ` (page ${item.page_no.toLocaleString()})`
                          : ''}
                      </li>
                    ))}
                </ul>
                <PageControls
                  page={diagnosticPage}
                  total={coverage.diagnostics.length}
                  label="diagnostic"
                  onChange={setDiagnosticPage}
                />
              </>
            )}
          </div>
        )}
      </details>
    </aside>
  );
}
