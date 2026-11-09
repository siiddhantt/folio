import { useEffect, useState } from 'react';
import { Link, Route, Routes } from 'react-router-dom';
import { PanelsTopLeft } from 'lucide-react';
import { request, errorMessage } from './api';
import type { Capabilities } from './types';
import { ThemeToggle } from './components/ThemeToggle';
import { Button, Notice } from './components/ui';
import { UploadPage } from './documents/UploadPage';
import { DocumentPage } from './documents/DocumentPage';

export function App() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    request<Capabilities>('/capabilities', { signal: controller.signal })
      .then(setCapabilities)
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [reload]);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <Link className="wordmark" to="/" aria-label="Folio home">
          <PanelsTopLeft aria-hidden="true" />
          Folio
        </Link>
        <ThemeToggle />
      </header>
      <main id="main">
        {error ? (
          <div className="page-message">
            <Notice error>{error} Folio could not load its settings.</Notice>
            <Button variant="outline" onClick={() => setReload(reload + 1)}>
              Reconnect
            </Button>
          </div>
        ) : !capabilities ? (
          <p className="page-message">Connecting to Folio…</p>
        ) : (
          <Routes>
            <Route path="/" element={<UploadPage capabilities={capabilities} />} />
            <Route
              path="/documents/:documentId"
              element={<DocumentPage capabilities={capabilities} />}
            />
            <Route
              path="*"
              element={
                <div className="page-message">
                  <h1>Page not found</h1>
                  <Link to="/">Upload a document</Link>
                </div>
              }
            />
          </Routes>
        )}
      </main>
    </>
  );
}
