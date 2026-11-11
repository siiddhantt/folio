import { useEffect, useState, type FormEvent } from 'react';
import { ChevronLeft, ChevronRight, Minus, Plus } from 'lucide-react';
import { Button } from '../components/ui';
import { Input } from '../components/ui/input';

export function PdfToolbar({
  page,
  total,
  zoom,
  onPageChange,
  onZoomChange,
}: {
  page: number;
  total: number;
  zoom: number;
  onPageChange: (page: number) => void;
  onZoomChange: (zoom: number) => void;
}) {
  const [draft, setDraft] = useState(String(page));
  useEffect(() => setDraft(String(page)), [page]);
  function commit(event?: FormEvent) {
    event?.preventDefault();
    const value = Number(draft);
    const next =
      Number.isInteger(value) && draft.trim() ? Math.max(1, Math.min(total, value)) : page;
    setDraft(String(next));
    onPageChange(next);
  }
  return (
    <div className="pdf-toolbar" aria-label="PDF controls">
      <form noValidate onSubmit={commit} className="pdf-pagination">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        <Input
          aria-label="PDF page number"
          type="number"
          inputMode="numeric"
          min={1}
          max={total}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => commit()}
        />
        <span>of {total.toLocaleString()}</span>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Next page"
          disabled={page >= total}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </form>
      <div className="pdf-zoom">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          disabled={zoom <= 0.75}
          onClick={() => onZoomChange(zoom - 0.25)}
        >
          <Minus aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onZoomChange(1)}>
          Fit width
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          disabled={zoom >= 2}
          onClick={() => onZoomChange(zoom + 0.25)}
        >
          <Plus aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
