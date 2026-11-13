import { expect, test } from '@playwright/test';

test('a creation acknowledged after navigation preserves the question without submitting it', async ({
  page,
}) => {
  const choice = {
    document_id: 'document-1',
    index_id: 'index-1',
    display_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  const chat = {
    id: 'chat-1',
    document_id: choice.document_id,
    revision_id: 'revision-1',
    index_id: choice.index_id,
    document_name: choice.display_name,
    created_at: choice.created_at,
    max_turns: 1,
    question: null,
    state: 'empty',
  };
  let releaseCreation: (() => void) | undefined;
  let created = false;
  let submissions = 0;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      if (path === '/conversations') {
        await new Promise<void>((resolve) => {
          releaseCreation = resolve;
        });
        created = true;
        await route.fulfill({ status: 201, json: chat });
      } else {
        submissions += 1;
        throw new Error(`Unexpected submission after navigation: ${path}`);
      }
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversation-documents': { items: [choice], next_cursor: null },
      '/conversations': { items: created ? [chat] : [], next_cursor: null },
      '/conversations/chat-1': chat,
      '/conversations/chat-1/turns': { items: [], next_after: null },
    };
    expect(path in responses).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Your question' })
    .fill('Keep this question with its chat.');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect.poll(() => !!releaseCreation).toBeTruthy();
  await page.getByRole('link', { name: 'Folio home' }).click();
  const creationResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/conversations') && response.request().method() === 'POST',
  );
  releaseCreation!();
  await (await creationResponse).finished();
  await expect(page).toHaveURL(/\/$/);
  const sidebar = page.getByRole('complementary', { name: 'Conversation history' });
  await sidebar.getByRole('button', { name: 'Refresh conversations' }).click();
  await sidebar.getByRole('link', { name: /Coverage.pdf/ }).click();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'Keep this question with its chat.',
    { timeout: 5000 },
  );
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  expect(submissions).toBe(0);
});

test('home separates upload and a document-scoped chat that starts only when sent', async ({
  page,
}) => {
  const document = {
    document_id: 'document-1',
    index_id: 'index-1',
    display_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  const conversation = {
    id: 'chat-1',
    document_id: document.document_id,
    revision_id: 'revision-1',
    index_id: document.index_id,
    document_name: document.display_name,
    created_at: document.created_at,
    question: null,
    state: 'empty',
    max_turns: 1,
  };
  const mutations: { path: string; body: unknown }[] = [];
  let question = '';
  const turn = () => ({
    id: 'turn-1',
    conversation_id: 'chat-1',
    sequence: 1,
    question,
    state: 'failed',
    error: { code: 'TEST_FAILURE', message: 'The answer service is unavailable.' },
    answer: null,
    citations: [],
    coverage: { diagnostics: [], pages_without_content: [] },
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      mutations.push({ path, body });
      expect(route.request().headers()['idempotency-key']).toBeTruthy();
      if (path === '/conversations') await route.fulfill({ status: 201, json: conversation });
      else {
        expect(path).toBe('/conversations/chat-1/turns');
        question = body.question;
        await route.fulfill({ status: 202, json: turn() });
      }
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: [], next_cursor: null },
      '/conversation-documents': { items: [document], next_cursor: null },
      '/conversations/chat-1': conversation,
      '/conversations/chat-1/turns': { items: question ? [turn()] : [], next_after: null },
    };
    expect(path in responses, `Unexpected request ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/');
  const main = page.getByRole('main');
  await main.getByRole('link', { name: 'Upload', exact: true }).click({ timeout: 5000 });
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByLabel('PDF document')).toBeVisible();
  await page.getByRole('link', { name: 'Folio home' }).click();
  await main.getByRole('link', { name: 'New chat', exact: true }).click();
  await expect(page).toHaveURL(/\/new-chat$/);
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page
    .getByRole('textbox', { name: 'Your question' })
    .fill('Does the garage have a separate limit?');
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'Does the garage have a separate limit?',
  );
  await expect(page.getByRole('combobox', { name: 'Document', exact: true })).toHaveText(
    'Coverage.pdf',
  );
  expect(mutations).toEqual([]);
  await page.getByRole('button', { name: 'Send question', exact: true }).click();
  await expect(page).toHaveURL(/\/conversations\/chat-1$/);
  await expect(main.getByRole('article', { name: 'Your question' })).toHaveText(
    'Does the garage have a separate limit?',
  );
  expect(mutations).toEqual([
    { path: '/conversations', body: { index_id: 'index-1' } },
    {
      path: '/conversations/chat-1/turns',
      body: { question: 'Does the garage have a separate limit?', observed_head: 0 },
    },
  ]);
});

test('a late first-send replay cannot erase a newer chat draft', async ({ page }) => {
  const choice = {
    document_id: 'document-1',
    index_id: 'index-1',
    display_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  const chat = {
    id: 'chat-1',
    document_id: choice.document_id,
    revision_id: 'revision-1',
    index_id: choice.index_id,
    document_name: choice.display_name,
    created_at: choice.created_at,
    max_turns: 1,
    question: 'First question',
    state: 'failed',
  };
  const turn = {
    id: 'turn-1',
    conversation_id: chat.id,
    sequence: 1,
    question: chat.question,
    state: 'failed',
    error: { code: 'FAILED', message: 'Answer unavailable.' },
    answer: null,
    citations: [],
    coverage: { diagnostics: [], pages_without_content: [] },
  };
  let submissions = 0;
  let releaseFirst: (() => void) | undefined;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      if (path === '/conversations') await route.fulfill({ status: 201, json: chat });
      else {
        expect(path).toBe('/conversations/chat-1/turns');
        submissions += 1;
        if (submissions === 1)
          await new Promise<void>((resolve) => {
            releaseFirst = resolve;
          });
        await route.fulfill({ status: 202, json: turn });
      }
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: [], next_cursor: null },
      '/conversation-documents': { items: [choice], next_cursor: null },
      '/conversations/chat-1': chat,
      '/conversations/chat-1/turns': { items: [turn], next_after: null },
    };
    expect(path in responses).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  const openNewChat = async () => {
    await page.getByRole('link', { name: 'Folio home' }).click();
    await page.getByRole('main').getByRole('link', { name: 'New chat', exact: true }).click();
  };
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).fill(chat.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect.poll(() => submissions).toBe(1);
  await openNewChat();
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page).toHaveURL(/\/conversations\/chat-1$/);
  await openNewChat();
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).fill('A different draft');
  const lateResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/conversations/chat-1/turns') &&
      response.request().method() === 'POST',
  );
  releaseFirst!();
  await (await lateResponse).finished();
  await openNewChat();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'A different draft',
    { timeout: 5000 },
  );
});

test('a failed linked-document lookup never silently sends the previous document', async ({
  page,
}) => {
  const first = {
    document_id: 'document-a',
    index_id: 'index-a',
    display_name: 'First.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  await page.route('**/api/**', async (route) => {
    expect(route.request().method()).toBe('GET');
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/capabilities'))
      await route.fulfill({
        json: { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      });
    else if (url.pathname.endsWith('/conversations'))
      await route.fulfill({ json: { items: [], next_cursor: null } });
    else if (url.pathname.endsWith('/conversation-documents') && url.searchParams.has('index_id'))
      await route.fulfill({ status: 503, json: { detail: 'Document lookup unavailable.' } });
    else if (url.pathname.endsWith('/conversation-documents'))
      await route.fulfill({ json: { items: [first], next_cursor: null } });
    else throw new Error(`Unexpected request ${url.pathname}`);
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'First.pdf', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).fill('What does this report say?');
  await page.goto('/new-chat?document=index-b');
  await expect(page.getByRole('alert')).toContainText('Document lookup unavailable.');
  await expect(page.getByRole('combobox', { name: 'Document', exact: true })).toHaveText(
    'Choose a document',
    {
      timeout: 5000,
    },
  );
  await expect(page.getByRole('button', { name: 'Send question' })).toBeDisabled();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'What does this report say?',
  );
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'First.pdf', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Send question' })).toBeEnabled();
});

test('confirming an uncertain send by exact replay clears the completed new-chat draft', async ({
  page,
}) => {
  const choice = {
    document_id: 'document-1',
    index_id: 'index-1',
    display_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  const chat = {
    id: 'chat-1',
    document_id: choice.document_id,
    revision_id: 'revision-1',
    index_id: choice.index_id,
    document_name: choice.display_name,
    created_at: choice.created_at,
    max_turns: 1,
    question: 'What is covered?',
    state: 'failed',
  };
  let accepted = false;
  const failedTurn = {
    id: 'turn-1',
    conversation_id: chat.id,
    sequence: 1,
    question: chat.question,
    state: 'failed',
    error: { code: 'FAILED', message: 'Answer unavailable.' },
    answer: null,
    citations: [],
    coverage: { diagnostics: [], pages_without_content: [] },
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      if (path === '/conversations') await route.fulfill({ status: 201, json: chat });
      else {
        expect(path).toBe('/conversations/chat-1/turns');
        if (accepted) await route.fulfill({ status: 202, json: failedTurn });
        else {
          accepted = true;
          await route.abort('connectionfailed');
        }
      }
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: accepted ? [chat] : [], next_cursor: null },
      '/conversation-documents': { items: [choice], next_cursor: null },
      '/conversations/chat-1': chat,
      '/conversations/chat-1/turns': {
        items: [failedTurn],
        next_after: null,
      },
    };
    expect(path in responses).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).fill(chat.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.getByRole('link', { name: 'Folio home' }).click();
  await page
    .getByRole('complementary', { name: 'Conversation history' })
    .getByRole('link', { name: /What is covered/ })
    .click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Answer unavailable.');
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
  await page.getByRole('link', { name: 'Folio home' }).click();
  await page.getByRole('main').getByRole('link', { name: 'New chat', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue('', {
    timeout: 5000,
  });
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeEnabled();
});

test('empty choices keep a draft usable and a linked document can be selected beyond the first page', async ({
  page,
}) => {
  let available = false;
  const selected = {
    document_id: 'selected-doc',
    index_id: 'selected-index',
    display_name: 'Earlier report.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  await page.route('**/api/**', async (route) => {
    expect(route.request().method()).toBe('GET');
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    if (path === '/capabilities')
      await route.fulfill({
        json: { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [], next_cursor: null } });
    else if (path === '/conversation-documents')
      await route.fulfill({
        json: {
          items: available
            ? [
                url.searchParams.has('index_id')
                  ? selected
                  : { ...selected, index_id: 'recent-index', display_name: 'Recent report.pdf' },
              ]
            : [],
          next_cursor: null,
        },
      });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/new-chat');
  await expect(page.getByText('No documents are ready for chat.', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Upload a PDF' })).toHaveAttribute('href', '/upload');
  const question = page.getByRole('textbox', { name: 'Your question' });
  await question.fill('A long question\n'.repeat(30));
  expect(
    await question.evaluate(
      (input) => input.scrollHeight > input.clientHeight && input.clientHeight <= 200,
    ),
  ).toBeTruthy();
  await question.fill('What changed?');
  expect(await question.evaluate((input) => input.clientHeight < 120)).toBeTruthy();
  await expect(page.getByRole('button', { name: 'Send question' })).toBeDisabled();
  available = true;
  await page.goto('/new-chat?document=selected-index');
  await expect(page.getByRole('combobox', { name: 'Document', exact: true })).toHaveText(
    'Earlier report.pdf',
    { timeout: 5000 },
  );
  await expect(question).toHaveValue('What changed?');
  await expect(page.getByRole('button', { name: 'Send question' })).toBeEnabled();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});

test('an uncertain first send keeps both replay identities across reload and leaves navigation alone', async ({
  page,
}) => {
  const choice = {
    document_id: 'document-1',
    index_id: 'index-1',
    display_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
  };
  const creationKeys: string[] = [];
  const questionKeys: string[] = [];
  let finish: (() => void) | undefined;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      if (path === '/conversations') {
        creationKeys.push(route.request().headers()['idempotency-key']);
        if (creationKeys.length === 1) await route.abort('connectionfailed');
        else await route.fulfill({ status: 201, json: { id: 'chat-1' } });
      } else {
        expect(path).toBe('/conversations/chat-1/turns');
        expect(route.request().postDataJSON()).toEqual({
          question: 'What is covered?',
          observed_head: 0,
        });
        questionKeys.push(route.request().headers()['idempotency-key']);
        if (questionKeys.length === 1) await route.abort('connectionfailed');
        else {
          await new Promise<void>((resolve) => {
            finish = resolve;
          });
          await route.fulfill({ status: 202, json: { id: 'turn-1' } });
        }
      }
      return;
    }
    if (path === '/capabilities')
      await route.fulfill({
        json: { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [], next_cursor: null } });
    else if (path === '/conversation-documents')
      await route.fulfill({ json: { items: [choice], next_cursor: null } });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  await page.getByRole('textbox', { name: 'Your question' }).fill('What is covered?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'What is covered?',
  );
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  expect(creationKeys).toHaveLength(1);
  expect(questionKeys).toHaveLength(0);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  expect(creationKeys).toHaveLength(2);
  expect(questionKeys).toHaveLength(1);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect.poll(() => questionKeys.length).toBe(2);
  await page.getByRole('link', { name: 'Folio home' }).click();
  finish!();
  await expect(
    page.getByRole('main').getByRole('link', { name: 'Upload', exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  expect(creationKeys[0]).toBe(creationKeys[1]);
  expect(questionKeys[0]).toBe(questionKeys[1]);
});
