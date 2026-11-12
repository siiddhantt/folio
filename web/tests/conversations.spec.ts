import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('a saved chat accepts one question, reloads its answer and opens the cited PDF', async ({
  page,
}) => {
  const time = '2026-01-01T12:00:00Z';
  const conversation = {
    id: 'chat-1',
    document_id: 'document-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    created_at: time,
    question: null,
    state: 'empty',
    max_turns: 1,
  };
  let question = '';
  let submissions = 0;
  let creations = 0;
  const turn = () => ({
    id: 'turn-1',
    conversation_id: 'chat-1',
    sequence: 1,
    question,
    state: 'ready',
    created_at: time,
    started_at: time,
    finished_at: time,
    error: null,
    answer: {
      outcome: 'answer',
      statements: [{ text: 'The building limit includes garage coverage.', source_ids: ['S1'] }],
    },
    citations: [
      {
        source_id: 'S1',
        chunk_ordinal: 1,
        text: 'Garage coverage is included in the building limit.',
        pages: [1],
      },
    ],
    coverage: { diagnostics: [], pages_without_content: [] },
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path.endsWith('/original')) {
      await route.fulfill({
        contentType: 'application/pdf',
        body: await readFile('../tests/fixtures/text.pdf'),
      });
      return;
    }
    if (route.request().method() === 'POST') {
      if (path === '/conversations') {
        expect(route.request().postDataJSON()).toEqual({ index_id: 'index-1' });
        expect(route.request().headers()['idempotency-key']).toBeTruthy();
        creations += 1;
        await route.fulfill({ status: 201, json: { ...conversation, id: 'chat-2' } });
        return;
      }
      expect(path).toBe('/conversations/chat-1/turns');
      expect(route.request().headers()['idempotency-key']).toBeTruthy();
      question = route.request().postDataJSON().question;
      submissions += 1;
      await route.fulfill({
        status: 202,
        json: { ...turn(), state: 'pending', answer: null, citations: [] },
      });
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: [{ ...conversation, question }], next_cursor: null },
      '/conversations/chat-1': { ...conversation, question, state: question ? 'ready' : 'empty' },
      '/conversations/chat-1/turns': { items: question ? [turn()] : [], next_after: null },
      '/conversations/chat-1/turns/turn-1': question ? turn() : null,
      '/conversations/chat-2': { ...conversation, id: 'chat-2' },
      '/conversations/chat-2/turns': { items: [], next_after: null },
    };
    expect(path in responses, `unexpected request ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Conversations', exact: true })).toBeVisible({
    timeout: 5000,
  });
  await page.getByRole('link', { name: /Coverage.pdf/ }).click();
  await page
    .getByRole('textbox', { name: 'Your question' })
    .fill('Does the garage have a separate limit?');
  await page.getByRole('button', { name: 'Send question', exact: true }).click();
  await expect(
    page.getByText('The building limit includes garage coverage.', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveCount(0);
  await expect(page.getByText('One question per chat for now.', { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByText('Does the garage have a separate limit?', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('The building limit includes garage coverage.', { exact: true }),
  ).toBeVisible();
  expect(submissions).toBe(1);
  await page.getByRole('button', { name: 'Source S1, page 1', exact: true }).click();
  const source = page.getByRole('dialog', { name: 'Source', exact: true });
  await expect(source).toBeVisible();
  await expect(source.getByRole('spinbutton', { name: 'PDF page number' })).toHaveValue('1');
  await page.getByRole('button', { name: 'Close source', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Source S1, page 1', exact: true })).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByText('The building limit includes garage coverage.', { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy();
  expect(creations).toBe(0);
  await page.getByRole('button', { name: 'New chat', exact: true }).click();
  await expect(page).toHaveURL(/\/conversations\/chat-2$/);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
  expect(creations).toBe(1);
  expect(submissions).toBe(1);
});

test('an uncertain question can be retried after reload without creating a new intent', async ({
  page,
}) => {
  const conversation = {
    id: 'retry-chat',
    document_id: 'document-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
    question: null,
    state: 'empty',
    max_turns: 1,
  };
  const failed = {
    id: 'turn-1',
    conversation_id: 'retry-chat',
    sequence: 1,
    question: 'Does the garage have a separate limit?',
    state: 'failed',
    created_at: conversation.created_at,
    started_at: conversation.created_at,
    finished_at: conversation.created_at,
    error: { code: 'PROVIDER_UNAVAILABLE', message: 'The answer service is unavailable.' },
    answer: null,
    citations: [],
    coverage: { diagnostics: [], pages_without_content: [] },
  };
  const keys: string[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      expect(path).toBe('/conversations/retry-chat/turns');
      expect(route.request().postDataJSON()).toEqual({ question: failed.question });
      keys.push(route.request().headers()['idempotency-key']);
      if (keys.length === 1) await route.abort('connectionfailed');
      else await route.fulfill({ status: 202, json: { ...failed, state: 'pending', error: null } });
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations/retry-chat': conversation,
      '/conversations/retry-chat/turns': {
        items: keys.length > 1 ? [failed] : [],
        next_after: null,
      },
      '/conversations/retry-chat/turns/turn-1': failed,
    };
    expect(path in responses, `unexpected request ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/conversations/retry-chat');
  await page.getByRole('textbox', { name: 'Your question' }).fill(failed.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(failed.question);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText(failed.error.message);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[1]).toBe(keys[0]);
  await page.reload();
  await expect(page.getByRole('alert')).toContainText(failed.error.message);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveCount(0);
});

test('clarification and evidence limits remain readable without invented source buttons', async ({
  page,
}) => {
  const conversation = {
    id: 'limited-chat',
    document_id: 'document-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    created_at: '2026-01-01T12:00:00Z',
    question: 'What is the limit?',
    state: 'ready',
    max_turns: 1,
  };
  let answer = {
    outcome: 'clarification',
    statements: [{ text: 'Which coverage limit do you mean?', source_ids: [] }],
  };
  await page.route('**/api/**', async (route) => {
    expect(route.request().method()).toBe('GET');
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations/limited-chat': conversation,
      '/conversations/limited-chat/turns': {
        items: [
          {
            id: 'turn-1',
            conversation_id: conversation.id,
            sequence: 1,
            question: conversation.question,
            state: 'ready',
            created_at: conversation.created_at,
            started_at: conversation.created_at,
            finished_at: conversation.created_at,
            error: null,
            answer,
            citations: [],
            coverage: { diagnostics: [], pages_without_content: [3] },
          },
        ],
        next_after: null,
      },
    };
    expect(path in responses, `unexpected request ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/conversations/limited-chat');
  await expect(page.getByText('More detail needed', { exact: true })).toBeVisible();
  await expect(page.getByRole('article', { name: 'Folio answer' })).toContainText(
    answer.statements[0].text,
  );
  await expect(page.getByRole('button', { name: /^Source / })).toHaveCount(0);
  answer = {
    outcome: 'insufficient_evidence',
    statements: [{ text: 'The supplied passages do not establish this limit.', source_ids: [] }],
  };
  await page.reload();
  await expect(page.getByText('Insufficient evidence', { exact: true })).toBeVisible();
  await expect(page.getByRole('article', { name: 'Folio answer' })).toContainText(
    answer.statements[0].text,
  );
  await expect(page.getByRole('button', { name: /^Source / })).toHaveCount(0);
  await expect(page.getByRole('note')).toContainText('Some document content may be missing.');
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New chat', exact: true })).toBeVisible();
});
