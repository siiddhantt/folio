import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, FileText, LoaderCircle } from 'lucide-react';
import { errorMessage, request } from '../api';
import { Button, formatBytes, Notice } from '../components/ui';
import type { Capabilities } from '../types';

export function UploadPage({
  capabilities,
  compact = false,
}: {
  capabilities: Capabilities;
  compact?: boolean;
}) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const intent = useRef(crypto.randomUUID());
  const controller = useRef<AbortController | null>(null);
  const sizeError =
    file && file.size > capabilities.max_upload_bytes
      ? `Choose a PDF smaller than ${formatBytes(capabilities.max_upload_bytes)}.`
      : '';
  useEffect(() => () => controller.current?.abort(), []);
  function select(file: File | undefined) {
    intent.current = crypto.randomUUID();
    setError('');
    setFile(file || null);
  }
  async function upload() {
    if (!file || busy || file.size > capabilities.max_upload_bytes) return;
    setBusy(true);
    setError('');
    const operation = new AbortController();
    controller.current = operation;
    const body = new FormData();
    body.append('file', file);
    try {
      const result = await request<{ document_id: string }>('/documents', {
        method: 'POST',
        body,
        headers: { 'Idempotency-Key': intent.current },
        signal: operation.signal,
      });
      navigate(`/documents/${result.document_id}`);
    } catch (e) {
      if (!operation.signal.aborted) setError(errorMessage(e));
    } finally {
      if (!operation.signal.aborted) setBusy(false);
    }
  }
  const Heading = compact ? 'h2' : 'h1';
  return (
    <div className={`upload-page${compact ? ' upload-compact' : ''}`}>
      <section className="upload-section" aria-labelledby="upload-title">
        <Heading id="upload-title">Open a document</Heading>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void upload();
          }}
        >
          <label className={`file-picker ${busy ? 'is-busy' : ''}`}>
            <FileText className="file-icon" aria-hidden="true" />
            <span className="file-title">{file ? file.name : 'Choose a PDF'}</span>
            <span className="file-hint">
              {file
                ? `${formatBytes(file.size)} · Click to change`
                : `Up to ${formatBytes(capabilities.max_upload_bytes)} · ${capabilities.max_pages} pages`}
            </span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              aria-label="PDF document"
              disabled={busy}
              onChange={(event) => select(event.target.files?.[0])}
            />
          </label>
          {(sizeError || error) && <Notice error>{sizeError || error}</Notice>}
          <div className="upload-actions">
            <span className="file-hint">PDF · English OCR</span>
            <Button
              disabled={!file || busy || file.size > capabilities.max_upload_bytes}
              type="submit"
            >
              {busy ? 'Uploading…' : 'Open document'}
              {busy ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <ArrowRight aria-hidden="true" />
              )}
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}
