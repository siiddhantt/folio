import { Component, lazy, Suspense, type ReactNode } from 'react';

const PdfRenderer = lazy(() => import('./PdfRenderer'));
export interface PdfPreviewProps {
  documentId: string;
  page: number;
  onPageChange: (page: number) => void;
}

class PreviewBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p className="preview-message">Preview could not load. Open or download the original PDF.</p>
    ) : (
      this.props.children
    );
  }
}

export function PdfPreview(props: PdfPreviewProps) {
  return (
    <PreviewBoundary key={props.documentId}>
      <Suspense fallback={<p className="preview-message">Loading original…</p>}>
        <PdfRenderer {...props} />
      </Suspense>
    </PreviewBoundary>
  );
}
