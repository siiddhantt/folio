export const questionIntentKey = (conversationId: string) => `folio:question:${conversationId}`;
export const questionDraftKey = (conversationId: string) => `folio:draft:${conversationId}`;
export const newChatDraftKey = 'folio:new-chat-draft';
export const newChatIntentKey = 'folio:new-chat-intent';

export function clearSubmittedDraft(operation: { id: string }) {
  try {
    if (JSON.parse(sessionStorage.getItem(newChatDraftKey) || 'null')?.id === operation.id) {
      sessionStorage.removeItem(newChatDraftKey);
    }
  } catch {
    // An unreadable draft cannot be identified as this submission's draft.
  }
}

export function clearConversationStorage(conversationId: string) {
  sessionStorage.removeItem(questionDraftKey(conversationId));
  sessionStorage.removeItem(questionIntentKey(conversationId));
  try {
    const intent = JSON.parse(sessionStorage.getItem(newChatIntentKey) || 'null');
    if (intent?.conversationId === conversationId) {
      sessionStorage.removeItem(newChatIntentKey);
      clearSubmittedDraft(intent);
    }
  } catch {
    // An unrelated or unreadable new-chat submission remains untouched.
  }
}
