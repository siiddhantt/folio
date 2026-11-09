import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Download, FileText } from 'lucide-react';
import { originalUrl } from '../api';
import { Button, Notice } from '../components/ui';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import type { Capabilities, RequestStatus } from '../types';
import { useDocument } from './useDocument';
import { EvidenceReader } from './EvidenceReader';
import { DeveloperPanel } from '../development/DeveloperPanel';

function processingLabel(status: RequestStatus): string {
  if (status.state === 'succeeded') return 'Evidence available';
  if (status.state === 'failed') return 'Could not extract this PDF';
  const current =
    status.attempts.find((attempt) => attempt.id === status.authorized_attempt_id) ||
    status.attempts.at(-1);
  if (current?.state === 'running')
    return current.attempt_no > 1 ? 'Processing again' : 'Processing document';
  return (current?.attempt_no || 0) > 1 ? 'Waiting to retry' : 'Waiting to process';
}

export function DocumentPage({ capabilities }: { capabilities: Capabilities }) {
  const { documentId = '' } = useParams();
  const { document, status, error } = useDocument(documentId);
  const [sourcePage, setSourcePage] = useState(1);
  const latest = status?.attempts.at(-1);
  return (
    <div className="document-page">
      {error && <Notice error>{error}</Notice>}
      {!document ? (
        !error && <p className="page-message">Loading document…</p>
      ) : (
        <>
          <div className="document-heading">
            <div className="document-title">
              <Button variant="ghost" size="icon" asChild>
                <Link to="/" aria-label="Open another document" title="Open another document">
                  <ArrowLeft aria-hidden="true" />
                </Link>
              </Button>
              <h1>{document.display_name}</h1>
            </div>
            <div className="document-actions">
              <Badge
                variant="secondary"
                role="status"
                className={status?.state === 'failed' ? 'text-destructive' : ''}
              >
                {status ? processingLabel(status) : 'Loading…'}
              </Badge>
              <Button variant="outline" size="sm" asChild>
                <a href={originalUrl(documentId)}>
                  <Download aria-hidden="true" />
                  Download PDF
                </a>
              </Button>
            </div>
          </div>
          <Separator />
          {status?.state === 'failed' && (
            <Notice error>
              {latest?.error_detail || 'No usable evidence could be recovered.'} Your original
              remains available.
            </Notice>
          )}
          {capabilities.development_mode && status && (
            <DeveloperPanel key={status.request_id} requestId={status.request_id} />
          )}
          <div className="reading-layout">
            <section className="evidence-column" aria-label="Extracted evidence">
              <div className="section-caption">
                <h2>Content</h2>
              </div>
              {status?.revision_id ? (
                <EvidenceReader
                  key={status.revision_id}
                  revisionId={status.revision_id}
                  onSourcePage={setSourcePage}
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
            <section className="source-column" aria-label="Original PDF">
              <div className="source-heading">
                <h2>Original</h2>
                <Button variant="ghost" size="sm" asChild>
                  <a
                    href={`${originalUrl(documentId, true)}#page=${sourcePage}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open page {sourcePage} <ArrowUpRight aria-hidden="true" />
                  </a>
                </Button>
              </div>
              {status?.state === 'succeeded' ? (
                <iframe
                  key={`${documentId}-${sourcePage}`}
                  title={`Original PDF, page ${sourcePage}`}
                  src={`${originalUrl(documentId, true)}#page=${sourcePage}`}
                />
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
          </div>
        </>
      )}
    </div>
  );
}
