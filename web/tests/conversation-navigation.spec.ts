import { expect, test } from '@playwright/test';

test('history stays available, recovers a failed load and supports mobile keyboard navigation', async ({
  page,
}) => {
  test.setTimeout(30000);
  const chats = ['Where does cover apply?', 'What is excluded?'].map((question, index) => ({
    id: `chat-${index + 1}`,
    document_id: `doc-${index + 1}`,
    revision_id: `revision-${index + 1}`,
    index_id: `index-${index + 1}`,
    document_name: index ? 'Exclusions.pdf' : 'Coverage.pdf',
    question,
    state: index ? 'failed' : 'ready',
    created_at: '2026-01-01T12:00:00Z',
    max_turns: 1,
  }));
  let historyAvailable = false;
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    expect(route.request().method()).toBe('GET');
    if (path === '/capabilities') {
      await route.fulfill({
        json: { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      });
    } else if (path === '/conversation-documents') {
      await route.fulfill({ json: { items: [], next_cursor: null } });
    } else if (path === '/conversations') {
      if (!historyAvailable) {
        await route.fulfill({ status: 503, json: { detail: 'History temporarily unavailable.' } });
      } else {
        const older = url.searchParams.has('before');
        await route.fulfill({
          json: { items: [chats[older ? 1 : 0]], next_cursor: older ? null : 'chat-1' },
        });
      }
    } else {
      const chat = chats.find((item) => path.startsWith(`/conversations/${item.id}`));
      if (!chat) throw new Error(`Unexpected API path ${path}`);
      const turn = {
        id: `turn-${chat.id}`,
        conversation_id: chat.id,
        sequence: 1,
        question: chat.question,
        state: chat.state,
        error: chat.state === 'failed' ? { code: 'FAILED', message: 'Answer unavailable.' } : null,
        answer:
          chat.state === 'ready'
            ? {
                outcome: 'answer',
                statements: [
                  { text: 'Coverage applies at the described location.', source_ids: [] },
                ],
              }
            : null,
        citations: [],
        coverage: { diagnostics: [], pages_without_content: [] },
      };
      await route.fulfill({
        json: path.endsWith('/turns') ? { items: [turn], next_after: null } : chat,
      });
    }
  });
  await page.goto('/conversations/chat-1');
  const sidebar = page.getByRole('complementary', { name: 'Conversation history' });
  await expect(sidebar).toBeVisible({ timeout: 5000 });
  await expect(sidebar.getByRole('button', { name: 'Retry history' })).toBeVisible({
    timeout: 5000,
  });
  historyAvailable = true;
  await sidebar.getByRole('button', { name: 'Retry history' }).click();
  await expect(sidebar.getByRole('link', { name: /Where does cover apply/ })).toHaveAttribute(
    'aria-current',
    'page',
  );
  const selectedRow = sidebar.getByRole('link', { name: /Where does cover apply/ }).locator('..');
  expect(await selectedRow.evaluate((row) => getComputedStyle(row).backgroundColor)).not.toBe(
    'rgba(0, 0, 0, 0)',
  );
  await sidebar.getByRole('button', { name: 'Older conversations' }).click();
  await sidebar.getByRole('link', { name: /What is excluded/ }).click();
  await expect(page.getByRole('main').getByText('Answer unavailable.')).toBeVisible();
  await expect(sidebar.getByRole('link', { name: /What is excluded/ })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await sidebar.getByRole('button', { name: 'Latest conversations' }).click();

  await page.setViewportSize({ width: 390, height: 844 });
  const toggle = page.getByRole('button', { name: 'Open conversation history' });
  await toggle.click();
  const drawer = page.getByRole('dialog', { name: 'Conversation history' });
  await expect(drawer).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
  await expect(toggle).toBeFocused();
  await toggle.click();
  await drawer.getByRole('link', { name: /Where does cover apply/ }).click();
  await expect(drawer).not.toBeVisible();
  await expect(page).toHaveURL(/\/conversations\/chat-1$/);
  await expect(
    page.getByRole('main').getByText('Coverage applies at the described location.'),
  ).toBeVisible();
  await expect(toggle).toBeFocused();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await toggle.click();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole('main')).toBeFocused();
  historyAvailable = false;
  await sidebar.getByRole('button', { name: 'Refresh conversations' }).click();
  await expect(sidebar.getByRole('button', { name: 'Retry history' })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: /Where does cover apply/ })).toBeVisible();
  const newConversation = sidebar.getByRole('link', { name: 'New conversation', exact: true });
  await expect(newConversation).toBeVisible({ timeout: 5000 });
  await newConversation.click();
  await expect(page).toHaveURL(/\/new-chat$/);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await toggle.click();
  await drawer.getByRole('link', { name: 'New conversation', exact: true }).click();
  await expect(drawer).not.toBeVisible();
  await expect(page).toHaveURL(/\/new-chat$/);
});

test('switching chats keeps drafts and a new chat returns history to the latest page', async ({
  page,
}) => {
  test.setTimeout(30000);
  const chat = (id: string) => ({
    id,
    document_id: 'document-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: `${id}.pdf`,
    created_at: '2026-01-01T12:00:00Z',
    max_turns: 1,
    question: id === 'older' ? 'What is covered?' : null,
    state: id === 'older' ? 'failed' : 'empty',
  });
  let created = false;
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      if (path === '/conversations') {
        created = true;
        await route.fulfill({ status: 201, json: chat('new') });
      } else {
        expect(path).toBe('/conversations/new/turns');
        await route.fulfill({ status: 202, json: { id: 'new-turn' } });
      }
    } else if (path === '/capabilities') {
      await route.fulfill({
        json: { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      });
    } else if (path === '/conversation-documents') {
      await route.fulfill({
        json: {
          items: [
            {
              document_id: 'document-1',
              index_id: 'index-1',
              display_name: 'Coverage.pdf',
              created_at: '2026-01-01T12:00:00Z',
            },
          ],
          next_cursor: null,
        },
      });
    } else if (path === '/conversations') {
      const older = url.searchParams.has('before');
      await route.fulfill({
        json: {
          items: older
            ? [chat('older')]
            : [...(created ? [chat('new')] : []), chat('first'), chat('second')],
          next_cursor: older ? null : 'second',
        },
      });
    } else {
      const id = path.split('/')[2];
      expect(['first', 'second', 'older', 'new']).toContain(id);
      const turns =
        id === 'older'
          ? [
              {
                id: 'failed-turn',
                conversation_id: id,
                sequence: 1,
                question: chat(id).question,
                state: 'failed',
                error: { code: 'FAILED', message: 'Answer unavailable.' },
                answer: null,
                citations: [],
                coverage: { diagnostics: [], pages_without_content: [] },
              },
            ]
          : [];
      await route.fulfill({
        json: path.endsWith('/turns') ? { items: turns, next_after: null } : chat(id),
      });
    }
  });
  await page.goto('/conversations/first');
  const sidebar = page.getByRole('complementary', { name: 'Conversation history' });
  await page.getByRole('textbox', { name: 'Your question' }).fill('Does this cover the garage?');
  await sidebar.getByRole('link', { name: /second.pdf/ }).click();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
  await sidebar.getByRole('link', { name: /first.pdf/ }).click();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'Does this cover the garage?',
    { timeout: 5000 },
  );
  await sidebar.getByRole('button', { name: 'Older conversations' }).click();
  await sidebar.getByRole('link', { name: /What is covered/ }).click();
  await page.getByRole('link', { name: 'New chat', exact: true }).click();
  await expect(page).toHaveURL(/\/new-chat\?document=index-1$/);
  await page.getByRole('textbox', { name: 'Your question' }).fill('What is covered?');
  await page.getByRole('button', { name: 'Send question', exact: true }).click();
  await expect(page).toHaveURL(/\/conversations\/new$/);
  await expect(sidebar.getByRole('link', { name: /new.pdf/ })).toHaveAttribute(
    'aria-current',
    'page',
    { timeout: 5000 },
  );
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
});
