import { expect, test } from '@playwright/test';

for (const reading of ['following', 'reading earlier'] as const) {
  test(`new replies respect the reader ${reading}`, async ({ page }) => {
    test.setTimeout(30000);
    const chat = {
      id: 'chat-1',
      document_id: 'doc-1',
      document_name: 'Coverage.pdf',
      title: 'Coverage',
      index_id: 'index-1',
    };
    const first = {
      id: 'turn-1',
      conversation_id: chat.id,
      sequence: 1,
      question: 'First question',
      state: 'ready',
      error: null,
      answer: {
        outcome: 'answer',
        statements: [{ text: 'Earlier explanation. '.repeat(100), source_ids: [] }],
      },
      citations: [],
      coverage: { diagnostics: [], pages_without_content: [] },
    };
    const pending = {
      ...first,
      id: 'turn-2',
      sequence: 2,
      question: 'Explain the conditions',
      state: 'pending',
      answer: null,
    };
    let submitted = false;
    let finished = false;
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api', '');
      if (route.request().method() === 'POST') {
        expect(path).toBe('/conversations/chat-1/turns');
        submitted = true;
        await route.fulfill({ status: 202, json: pending });
        return;
      }
      const current = finished
        ? {
            ...pending,
            state: 'ready',
            answer: {
              outcome: 'answer',
              statements: [
                { text: 'A detailed condition. '.repeat(200), source_ids: [] },
                { text: 'Final detail.', source_ids: [] },
              ],
            },
          }
        : pending;
      const responses: Record<string, unknown> = {
        '/capabilities': { development_mode: false },
        '/conversations': { items: [chat], next_cursor: null },
        '/conversations/chat-1': chat,
        '/conversations/chat-1/turns': {
          items: submitted ? [first, current] : [first],
          next_before: null,
        },
        '/conversations/chat-1/turns/turn-2': current,
      };
      expect(path in responses, path).toBeTruthy();
      await route.fulfill({ json: responses[path] });
    });
    await page.goto('/conversations/chat-1');
    await page.getByRole('textbox', { name: 'Your question' }).fill(pending.question);
    await page.getByRole('button', { name: 'Send question', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toBeInViewport();
    const messages = page.getByRole('region', { name: 'Conversation messages', exact: true });
    if (reading === 'reading earlier') {
      await messages.evaluate((element) => {
        element.scrollTop = 0;
      });
    }
    finished = true;
    if (reading === 'reading earlier') {
      await expect(page.getByText('Final detail.', { exact: true })).toBeAttached({
        timeout: 6000,
      });
      expect(await messages.evaluate((element) => element.scrollTop)).toBe(0);
      await page.getByRole('button', { name: 'Latest reply', exact: true }).click();
    }
    await expect(page.getByText('Final detail.', { exact: true })).toBeInViewport({
      timeout: 6000,
    });
  });
}
