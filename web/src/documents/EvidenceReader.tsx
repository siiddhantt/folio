import { useEffect, useRef, useState } from 'react';
import { errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import type { Evidence, SourceElement } from '../types';
import { CoverageNotice } from './CoverageNotice';
import { EvidenceTable } from './EvidenceTable';
import { SourcePages } from './SourcePages';
import { describeCoverage } from './coverage';

export function EvidenceReader({
  revisionId,
  onSourcePage,
  onCoverage,
}: {
  revisionId: string;
  onSourcePage: (page: number) => void;
  onCoverage: (partial: boolean) => void;
}) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const lifetime = useRef<AbortController | null>(null);
  async function load(after = -1, signal = lifetime.current?.signal) {
    setBusy(true);
    setError('');
    try {
      const next = await request<Evidence>(
        `/revisions/${revisionId}/evidence?after_order=${after}`,
        { signal },
      );
      if (!signal?.aborted) onCoverage(describeCoverage(next).partial);
      if (!signal?.aborted)
        setEvidence((previous) => ({
          ...next,
          elements:
            after === -1 ? next.elements : [...(previous?.elements || []), ...next.elements],
        }));
    } catch (e) {
      if (!signal?.aborted) setError(errorMessage(e));
    } finally {
      if (!signal?.aborted) setBusy(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void load(-1, controller.signal);
    return () => controller.abort();
  }, [revisionId]);
  return (
    <>
      {evidence && <CoverageNotice evidence={evidence} onSourcePage={onSourcePage} />}
      {error && (
        <Notice error>
          {error}{' '}
          <Button variant="outline" onClick={() => void load(evidence?.next_after_order ?? -1)}>
            Try again
          </Button>
        </Notice>
      )}
      {evidence?.elements.map((element) => (
        <EvidenceBlock key={element.element_id} element={element} onSourcePage={onSourcePage} />
      ))}
      {busy && <p className="subtle">Loading evidence…</p>}
      {evidence?.next_after_order != null && (
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void load(evidence.next_after_order!)}
        >
          Load more evidence
        </Button>
      )}
    </>
  );
}

function EvidenceBlock({
  element,
  onSourcePage,
}: {
  element: SourceElement;
  onSourcePage: (page: number) => void;
}) {
  const pages = [...new Set(element.locations.map((location) => location.page_no))];
  return (
    <article className="evidence-block">
      <div className="evidence-meta">
        <SourcePages pages={pages} onSourcePage={onSourcePage} />
      </div>
      {element.table_data ? (
        <EvidenceTable element={element} />
      ) : (
        <p
          className={
            ['title', 'section_header'].includes(element.kind) ? 'evidence-title' : 'evidence-text'
          }
        >
          {element.text}
        </p>
      )}
    </article>
  );
}
