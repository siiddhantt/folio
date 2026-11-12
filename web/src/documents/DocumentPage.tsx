import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download } from 'lucide-react';
import { originalUrl } from '../api';
import { Button, Notice } from '../components/ui';
import type { Capabilities, RequestStatus } from '../types';
import { useDocument } from './useDocument';
import { DeveloperPanel } from '../development/DeveloperPanel';
import { DocumentReader } from './DocumentReader';
import { DocumentChatAction } from '../conversations/NewChatButton';

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
  return <DocumentWorkspace key={documentId} documentId={documentId} capabilities={capabilities} />;
}

function DocumentWorkspace({
  documentId,
  capabilities,
}: {
  documentId: string;
  capabilities: Capabilities;
}) {
  const { document, status, error } = useDocument(documentId);
  const [partial, setPartial] = useState(false);
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
              <div className="document-title-copy">
                <h1>{document.display_name}</h1>
                <p
                  role="status"
                  className={`document-status ${status?.state === 'failed' ? 'text-destructive' : ''}`}
                >
                  {status?.state === 'succeeded' &&
                  (partial || latest?.parser_status === 'partial_success')
                    ? 'Partial extraction'
                    : status
                      ? processingLabel(status)
                      : 'Loading…'}
                </p>
              </div>
            </div>
            <div className="document-actions">
              {status?.revision_id && (
                <DocumentChatAction key={status.revision_id} revisionId={status.revision_id} />
              )}
              <Button variant="outline" size="sm" asChild>
                <a href={originalUrl(documentId)}>
                  <Download aria-hidden="true" />
                  Download PDF
                </a>
              </Button>
              {capabilities.development_mode && status && (
                <DeveloperPanel key={status.request_id} requestId={status.request_id} />
              )}
            </div>
          </div>
          {status?.state === 'failed' && (
            <Notice error>
              {latest?.error_detail || 'No usable evidence could be recovered.'} Your original
              remains available.
            </Notice>
          )}
          <DocumentReader documentId={documentId} status={status} onCoverage={setPartial} />
        </>
      )}
    </div>
  );
}
