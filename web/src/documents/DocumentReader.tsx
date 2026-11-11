import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Tabs } from 'radix-ui';
import { ArrowUpRight, FileText } from 'lucide-react';
import { originalUrl } from '../api';
import { Button } from '../components/ui';
import type { RequestStatus } from '../types';
import { SummaryPanel } from '../summaries/SummaryPanel';
import { EvidenceReader } from './EvidenceReader';
import { PdfPreview } from './PdfPreview';

export function DocumentReader({
  documentId,
  status,
  onCoverage,
}: {
  documentId: string;
  status: RequestStatus | null;
  onCoverage: (partial: boolean) => void;
}) {
  const [page, setPage] = useState(1);
  const [view, setView] = useState('content');
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 760px)').matches);
  const [previewOpened, setPreviewOpened] = useState(!narrow);
  const workspace = useRef<HTMLDivElement>(null);
  const originalTab = useRef<HTMLButtonElement>(null);
  const focusOriginal = useRef(false);
  const positions = useRef<Record<string, number | null>>({ content: 0, original: null });
  const nextScroll = useRef<number | null>(null);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)');
    const changed = () => {
      setNarrow(media.matches);
      if (!media.matches) setPreviewOpened(true);
    };
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  function selectView(next: string, sourceJump = false) {
    if (narrow) {
      positions.current[view] = window.scrollY;
      nextScroll.current = sourceJump
        ? (workspace.current?.offsetTop ?? 0)
        : (positions.current[next] ?? workspace.current?.offsetTop ?? 0);
      focusOriginal.current = sourceJump;
    }
    if (next === 'original') setPreviewOpened(true);
    setView(next);
  }
  useLayoutEffect(() => {
    if (focusOriginal.current) {
      originalTab.current?.focus({ preventScroll: true });
      focusOriginal.current = false;
    }
    if (nextScroll.current !== null) {
      window.scrollTo({ top: nextScroll.current, behavior: 'instant' });
      nextScroll.current = null;
    }
  }, [view]);
  const changePage = useCallback((next: number) => setPage(next), []);
  function showSource(next: number) {
    setPage(next);
    if (narrow) selectView('original', true);
  }
  return (
    <Tabs.Root
      className="reading-workspace"
      ref={workspace}
      value={view}
      onValueChange={selectView}
      activationMode="manual"
    >
      <Tabs.List className="reading-tabs" aria-label="Document view">
        <Tabs.Trigger value="content">Content</Tabs.Trigger>
        <Tabs.Trigger value="original" ref={originalTab}>
          Original
        </Tabs.Trigger>
      </Tabs.List>
      <div className="reading-layout">
        <Tabs.Content
          value="content"
          forceMount
          hidden={narrow && view !== 'content'}
          className="evidence-column reading-panel"
        >
          {status?.revision_id && (
            <SummaryPanel
              key={status.revision_id}
              revisionId={status.revision_id}
              onSourcePage={showSource}
            />
          )}
          <section aria-label="Extracted evidence">
            <div className="section-caption">
              <h2>Content</h2>
            </div>
            {status?.revision_id ? (
              <EvidenceReader
                key={status.revision_id}
                revisionId={status.revision_id}
                onSourcePage={showSource}
                onCoverage={onCoverage}
              />
            ) : (
              <div className="waiting-copy">
                <p>
                  {status?.state === 'failed'
                    ? 'No extracted content.'
                    : 'Waiting for extracted content…'}
                </p>
              </div>
            )}
          </section>
        </Tabs.Content>
        <Tabs.Content
          value="original"
          forceMount
          hidden={narrow && view !== 'original'}
          className="source-column reading-panel"
        >
          <section aria-label="Original PDF">
            <div className="source-heading">
              <h2>Original</h2>
              <Button variant="ghost" size="sm" asChild>
                <a
                  href={`${originalUrl(documentId, true)}#page=${page}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open page {page} <ArrowUpRight aria-hidden="true" />
                </a>
              </Button>
            </div>
            {status?.state === 'succeeded' && previewOpened ? (
              <PdfPreview documentId={documentId} page={page} onPageChange={changePage} />
            ) : (
              <div className="source-placeholder">
                <FileText aria-hidden="true" />
                <p>
                  {status?.state === 'failed'
                    ? 'Preview unavailable'
                    : 'Preview available after processing'}
                </p>
              </div>
            )}
          </section>
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}
