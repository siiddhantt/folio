import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, X } from 'lucide-react';
import { Button } from '../components/ui';
import { Sheet, SheetClose, SheetContent, SheetTitle } from '../components/ui/sheet';
import { PdfPreview } from '../documents/PdfPreview';
import type { Citation } from './types';

export function SourcePanel({
  documentId,
  sources,
  selected,
  onClose,
}: {
  documentId: string;
  sources: Citation[];
  selected?: string;
  onClose: () => void;
}) {
  const [page, setPage] = useState<number | null>(null);
  const [activeSource, setActiveSource] = useState(selected);
  const trigger = useRef(document.activeElement as HTMLElement | null);
  const selectedPassage = useRef<HTMLElement>(null);
  useEffect(() => {
    if (page === null && selectedPassage.current) {
      selectedPassage.current.focus({ preventScroll: true });
      selectedPassage.current.scrollIntoView({ block: 'start' });
    }
  }, [page, activeSource]);
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent
        aria-describedby={undefined}
        onOpenAutoFocus={(event) => {
          if (selectedPassage.current) {
            event.preventDefault();
            selectedPassage.current.focus({ preventScroll: true });
            selectedPassage.current.scrollIntoView({ block: 'start' });
          }
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (trigger.current?.isConnected) trigger.current.focus();
        }}
      >
        <div className="chat-source-heading">
          <SheetTitle>Sources</SheetTitle>
          <SheetClose asChild>
            <Button variant="ghost" size="icon" aria-label="Close sources">
              <X aria-hidden="true" />
            </Button>
          </SheetClose>
        </div>
        <div className="chat-source-content">
          {page === null ? (
            sources.map((source, index) => (
              <article
                key={source.source_id}
                ref={source.source_id === activeSource ? selectedPassage : undefined}
                tabIndex={-1}
                className="source-passage"
                aria-label={`Passage ${index + 1}`}
              >
                <h3>Passage {index + 1}</h3>
                <p>{source.text}</p>
                <div className="answer-citations">
                  {source.pages.map((number) => (
                    <Button
                      key={number}
                      variant="outline"
                      size="sm"
                      aria-label={`View page ${number} in original`}
                      onClick={() => {
                        setActiveSource(source.source_id);
                        setPage(number);
                      }}
                    >
                      Page {number}
                    </Button>
                  ))}
                </div>
              </article>
            ))
          ) : (
            <>
              <Button
                autoFocus
                variant="ghost"
                size="sm"
                className="source-back"
                onClick={() => setPage(null)}
              >
                <ArrowLeft aria-hidden="true" />
                Back to passages
              </Button>
              <PdfPreview documentId={documentId} page={page} onPageChange={setPage} />
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
