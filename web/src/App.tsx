import { useEffect, useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import { History, PanelsTopLeft, SlidersHorizontal } from 'lucide-react';
import { request, errorMessage } from './api';
import type { Capabilities } from './types';
import { ThemeToggle } from './components/ThemeToggle';
import { Button, Notice } from './components/ui';
import { HomePage } from './conversations/HomePage';
import { ConversationPage } from './conversations/ConversationPage';
import { DocumentPage } from './documents/DocumentPage';
import { SettingsPage } from './configuration/SettingsPage';
import { RunsPage } from './runs/RunsPage';

export function App() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const location = useLocation();
  useEffect(() => {
    const refresh = () => setReload((value) => value + 1);
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    request<Capabilities>('/capabilities', { signal: controller.signal })
      .then(setCapabilities)
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [reload, location.pathname]);
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
        <div className="header-actions">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/runs" aria-current={location.pathname === '/runs' ? 'page' : undefined}>
              <History aria-hidden="true" />
              Runs
            </Link>
          </Button>
          {capabilities?.development_mode && (
            <Button variant="ghost" size="icon" asChild>
              <Link
                to="/development/settings"
                aria-label="Development settings"
                title="Development settings"
              >
                <SlidersHorizontal aria-hidden="true" />
              </Link>
            </Button>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main id="main">
        {error && !capabilities ? (
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
            <Route path="/" element={<HomePage capabilities={capabilities} />} />
            <Route path="/conversations/:conversationId" element={<ConversationPage />} />
            <Route path="/runs" element={<RunsPage />} />
            {capabilities.development_mode && (
              <Route
                path="/development/settings"
                element={<SettingsPage onSaved={() => setReload((value) => value + 1)} />}
              />
            )}
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
