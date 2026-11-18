import { useCallback, useEffect, useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import { ChevronLeft, ChevronRight, History, SlidersHorizontal } from 'lucide-react';
import { Dialog } from 'radix-ui';
import { request, errorMessage } from './api';
import type { Capabilities } from './types';
import { ThemeToggle } from './components/ThemeToggle';
import { Button, Notice } from './components/ui';
import { BackButton } from './components/BackButton';
import { HomePage } from './conversations/HomePage';
import { NewConversationPage } from './conversations/NewConversationPage';
import { ConversationPage } from './conversations/ConversationPage';
import { ConversationSidebar } from './conversations/ConversationSidebar';
import type { Conversation } from './conversations/types';
import { DocumentPage } from './documents/DocumentPage';
import { UploadPage } from './documents/UploadPage';
import { SettingsPage } from './configuration/SettingsPage';
import { RunsPage } from './runs/RunsPage';

export function App() {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('folio-sidebar-collapsed') === 'true';
    } catch {
      return false;
    }
  });
  const sidebarLabel = sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar';
  function toggleSidebar() {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    try {
      localStorage.setItem('folio-sidebar-collapsed', String(next));
    } catch {
      /* Browser storage is optional. */
    }
  }
  const [historyRevision, setHistoryRevision] = useState(0);
  const [renamedConversation, setRenamedConversation] = useState<Conversation | null>(null);
  const refreshHistory = useCallback(() => setHistoryRevision((value) => value + 1), []);
  const location = useLocation();
  useEffect(() => {
    const media = window.matchMedia('(min-width: 1100px)');
    const close = () => {
      if (media.matches) setHistoryOpen(false);
    };
    media.addEventListener('change', close);
    return () => media.removeEventListener('change', close);
  }, []);
  useEffect(() => {
    setRenamedConversation(null);
    const titles: Record<string, string> = {
      '/runs': 'Processing runs',
      '/new-chat': 'New chat',
      '/upload': 'Upload',
      '/development/settings': 'Development settings',
    };
    document.title = titles[location.pathname] ? `${titles[location.pathname]} · Folio` : 'Folio';
    if (window.matchMedia('(min-width: 1100px)').matches) {
      document.getElementById('main')?.focus({ preventScroll: true });
    }
    document.getElementById('main')?.scrollTo(0, 0);
  }, [location.pathname]);
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
    <Dialog.Root open={historyOpen} onOpenChange={setHistoryOpen}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <Link className="wordmark" to="/" aria-label="Folio home">
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
      <div className={`app-workspace${capabilities && !sidebarCollapsed ? ' has-history' : ''}`}>
        {capabilities && (
          <>
            <button
              type="button"
              className="sidebar-edge desktop-edge"
              aria-label={sidebarLabel}
              title={sidebarLabel}
              aria-expanded={!sidebarCollapsed}
              aria-controls="conversation-sidebar"
              onClick={toggleSidebar}
            >
              {sidebarCollapsed ? (
                <ChevronRight aria-hidden="true" />
              ) : (
                <ChevronLeft aria-hidden="true" />
              )}
            </button>
            <Dialog.Trigger asChild>
              <button
                type="button"
                className="sidebar-edge drawer-edge"
                aria-label="Open conversation history"
                title="Open conversation history"
              >
                <ChevronRight aria-hidden="true" />
              </button>
            </Dialog.Trigger>
            <ConversationSidebar
              revision={historyRevision}
              onChanged={refreshHistory}
              onRenamed={setRenamedConversation}
              onNavigate={() => setHistoryOpen(false)}
            />
          </>
        )}
        <main id="main" tabIndex={-1}>
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
              <Route path="/" element={<HomePage />} />
              <Route path="/new-chat" element={<NewConversationPage />} />
              <Route path="/upload" element={<UploadPage capabilities={capabilities} />} />
              <Route
                path="/conversations/:conversationId"
                element={
                  <ConversationPage
                    revision={historyRevision}
                    renamedConversation={renamedConversation}
                    onTurnChanged={refreshHistory}
                  />
                }
              />
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
                    <div className="page-title">
                      <BackButton />
                      <h1>Page not found</h1>
                    </div>
                    <Link to="/">Go home</Link>
                  </div>
                }
              />
            </Routes>
          )}
        </main>
      </div>
    </Dialog.Root>
  );
}
