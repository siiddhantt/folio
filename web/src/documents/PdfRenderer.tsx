import { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import { originalUrl } from '../api';
import { PdfToolbar } from './PdfToolbar';
import type { PdfPreviewProps } from './PdfPreview';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();
const options = {
  cMapUrl: '/pdf-assets/cmaps/',
  standardFontDataUrl: '/pdf-assets/standard_fonts/',
  wasmUrl: '/pdf-assets/wasm/',
  iccUrl: '/pdf-assets/iccs/',
  isEvalSupported: false,
};
const failure = (
  <p className="preview-message">
    This page could not be displayed. Open or download the original PDF.
  </p>
);

export default function PdfRenderer({ documentId, page, onPageChange }: PdfPreviewProps) {
  const container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [total, setTotal] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [fitWidth, setFitWidth] = useState(false);
  useEffect(() => {
    const node = container.current;
    if (!node) return;
    const splitView = window.matchMedia('(min-width: 761px) and (min-height: 480px)');
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.floor(entry.contentRect.width);
      const height = splitView.matches ? Math.floor(entry.contentRect.height) : 0;
      if (width > 0)
        setSize((previous) =>
          previous.width === width && previous.height === height ? previous : { width, height },
        );
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    container.current?.scrollTo({ top: 0, left: 0 });
  }, [page]);
  return (
    <>
      {total > 0 && (
        <PdfToolbar
          page={page}
          total={total}
          zoom={zoom}
          fitLabel={fitWidth && size.height > 0 ? 'Fit page' : 'Fit width'}
          onFit={() => {
            setFitWidth(size.height > 0 && !fitWidth);
            setZoom(1);
          }}
          onPageChange={onPageChange}
          onZoomChange={setZoom}
        />
      )}
      <div
        className="pdf-page-viewport"
        ref={container}
        role="region"
        aria-label="Original page"
        tabIndex={0}
      >
        <Document
          file={originalUrl(documentId, true)}
          options={options}
          suspense={false}
          onLoadSuccess={({ numPages }) => {
            setTotal(numPages);
            if (page > numPages) onPageChange(numPages);
          }}
          onItemClick={({ pageNumber }) => onPageChange(pageNumber)}
          externalLinkTarget="_blank"
          externalLinkRel="noopener noreferrer"
          loading={<p className="preview-message">Loading original…</p>}
          error={failure}
        >
          <PdfPage
            key={page}
            page={page}
            width={size.width}
            fitHeight={fitWidth ? 0 : size.height}
            zoom={zoom}
          />
        </Document>
      </div>
      {total > 0 && (
        <p className="sr-only" aria-live="polite">
          Original page {page} of {total}
        </p>
      )}
    </>
  );
}

function PdfPage({
  page,
  width,
  fitHeight,
  zoom,
}: {
  page: number;
  width: number;
  fitHeight: number;
  zoom: number;
}) {
  const [failed, setFailed] = useState(false);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const loadedPage = useCallback((source: pdfjs.PDFPageProxy) => {
    const viewport = source.getViewport({ scale: 1 });
    setDimensions({ width: viewport.width, height: viewport.height });
  }, []);
  if (failed) return failure;
  const ready = dimensions !== null && width > 0;
  const fittedWidth =
    ready && fitHeight > 0
      ? Math.min(width, (fitHeight * dimensions.width) / dimensions.height)
      : width;
  const renderWidth = ready
    ? Math.max(
        1,
        Math.floor(
          Math.min(fittedWidth * zoom, 1600, (2400 * dimensions.width) / dimensions.height),
        ),
      )
    : 1;
  return (
    <Page
      pageNumber={page}
      onLoadSuccess={loadedPage}
      onRenderError={() => setFailed(true)}
      width={renderWidth}
      devicePixelRatio={Math.min(window.devicePixelRatio || 1, 2)}
      renderMode={ready ? 'canvas' : 'none'}
      renderTextLayer={ready}
      renderAnnotationLayer={ready}
      loading={<p className="preview-message">Loading page {page}…</p>}
      error={failure}
    />
  );
}
