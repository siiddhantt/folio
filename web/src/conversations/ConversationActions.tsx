import { useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Dialog } from 'radix-ui';
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import { ApiError, errorMessage, request } from '../api';
import { Button, Notice } from '../components/ui';
import { Input } from '../components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import type { Conversation } from './types';
import { clearConversationStorage } from './storage';

export interface ConversationAction {
  conversation: Conversation;
  trigger: HTMLElement | null;
  kind: 'rename' | 'delete';
}

export function ConversationMenu({
  conversation,
  onAction,
}: {
  conversation: Conversation;
  onAction: (action: ConversationAction) => void;
}) {
  const trigger = useRef<HTMLButtonElement>(null);
  const openingDialog = useRef(false);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          ref={trigger}
          className="history-actions-trigger"
          variant="ghost"
          size="icon-sm"
          aria-label={`Actions for ${conversation.title || conversation.question || conversation.document_name}`}
        >
          <MoreHorizontal aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        onCloseAutoFocus={(event) => {
          if (openingDialog.current) {
            event.preventDefault();
            openingDialog.current = false;
          }
        }}
      >
        <DropdownMenuItem
          onSelect={() => {
            openingDialog.current = true;
            onAction({ conversation, trigger: trigger.current, kind: 'rename' });
          }}
        >
          <Pencil aria-hidden="true" /> Rename
        </DropdownMenuItem>
        <DropdownMenuItem
          className="conversation-delete-action"
          onSelect={() => {
            openingDialog.current = true;
            onAction({ conversation, trigger: trigger.current, kind: 'delete' });
          }}
        >
          <Trash2 aria-hidden="true" /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ConversationActionDialog({
  action,
  onClose,
  onChanged,
  onNavigate,
  onDeleted,
  onRenamed,
}: {
  action: ConversationAction;
  onClose: () => void;
  onChanged: () => void;
  onNavigate: () => void;
  onDeleted: (id: string) => void;
  onRenamed: (conversation: Conversation) => void;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const currentPath = useRef(pathname);
  currentPath.current = pathname;
  const [title, setTitle] = useState(
    action.conversation.title || action.conversation.question || action.conversation.document_name,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [version, setVersion] = useState<number | null>(action.conversation.title_version);
  async function refreshTitle() {
    try {
      const latest = await request<Conversation>(`/conversations/${action.conversation.id}`);
      setVersion(latest.title_version);
      setError(
        `This chat was renamed elsewhere to “${latest.title}”. Review your title and save again.`,
      );
      onChanged();
    } catch (reason) {
      setError(`${errorMessage(reason)} Reload the latest title before saving.`);
    }
  }
  async function save() {
    if (busy) return;
    if (!title.trim()) {
      setError('Enter a chat title.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      if (version === null) {
        await refreshTitle();
        return;
      }
      const renamed = await request<Conversation>(`/conversations/${action.conversation.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), expected_version: version }),
      });
      onRenamed(renamed);
      onChanged();
      onClose();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setVersion(null);
        await refreshTitle();
      } else setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await request<void>(`/conversations/${action.conversation.id}`, { method: 'DELETE' });
      clearConversationStorage(action.conversation.id);
      onDeleted(action.conversation.id);
      onChanged();
      onClose();
      if (currentPath.current === `/conversations/${action.conversation.id}`) {
        onNavigate();
        navigate('/new-chat', { replace: true });
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }
  const deleting = action.kind === 'delete';
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="conversation-action-overlay" />
        <Dialog.Content
          className="conversation-action-dialog"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (action.trigger?.isConnected) action.trigger.focus();
            else document.getElementById('main')?.focus({ preventScroll: true });
          }}
        >
          <Dialog.Title>{deleting ? 'Delete chat?' : 'Rename chat'}</Dialog.Title>
          <Dialog.Description>
            {deleting
              ? `“${title}” will be removed from Folio. Internal transcript, diagnostics and billing records are retained. Calls already admitted may still incur charges.`
              : 'Choose a short title for this conversation.'}
          </Dialog.Description>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (deleting) void remove();
              else void save();
            }}
          >
            {!deleting && (
              <>
                <label htmlFor="conversation-title">Chat title</label>
                <Input
                  id="conversation-title"
                  name="title"
                  value={title}
                  maxLength={60}
                  disabled={busy}
                  onChange={(event) => setTitle(event.target.value)}
                  aria-invalid={!!error}
                  aria-describedby={error ? 'conversation-action-error' : undefined}
                />
              </>
            )}
            {error && (
              <div id="conversation-action-error">
                <Notice error>{error}</Notice>
              </div>
            )}
            <div className="conversation-dialog-actions">
              <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant={deleting ? 'destructive' : 'default'} disabled={busy}>
                {deleting
                  ? busy
                    ? 'Deleting…'
                    : 'Delete chat'
                  : busy
                    ? 'Saving…'
                    : version === null
                      ? 'Reload latest title'
                      : 'Save title'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
