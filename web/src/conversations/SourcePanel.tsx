import { useRef, useState } from 'react';
import { Dialog } from 'radix-ui';
import { X } from 'lucide-react';
import { Button } from '../components/ui';
import { PdfPreview } from '../documents/PdfPreview';
import { SourcePages } from '../documents/SourcePages';
import type { Citation } from './types';

export function SourcePanel({
  documentId,
  source,
  onClose,
}: {
  documentId: string;
  source: Citation;
  onClose: () => void;
}) {
  const [page, setPage] = useState(source.pages[0] || 1);
  const trigger = useRef(document.activeElement as HTMLElement | null);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="chat-source-overlay" />
        <Dialog.Content
          className="chat-source-panel"
          aria-describedby={undefined}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            trigger.current?.focus();
          }}
        >
          <div className="chat-source-heading">
            <Dialog.Title>Source</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close source">
                <X aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>
          <div className="chat-source-content">
            <details className="source-passage">
              <summary>Retrieved passage · {source.source_id}</summary>
              <p>{source.text}</p>
              <SourcePages pages={source.pages} onSourcePage={setPage} />
            </details>
            <PdfPreview documentId={documentId} page={page} onPageChange={setPage} />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
