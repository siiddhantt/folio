import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const time = '2026-01-01T12:00:00Z';
const chat = {
  id: 'chat-1',
  document_id: 'document-1',
  revision_id: 'revision-1',
  index_id: 'index-1',
  document_name: 'Coverage.pdf',
  title: 'Garage coverage',
  title_source: 'generated',
  title_version: 0,
  created_at: time,
  question: 'How much coverage applies?',
  state: 'ready',
  head_sequence: 1,
  max_turns: null,
};

test('a newer metadata head cannot silently advance a draft beyond the loaded transcript', async ({
  page,
}) => {
  test.setTimeout(30000);
  const first = readyTurn(1, chat.question, 'The answer I have read.', 'First evidence.');
  let submitted: unknown;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      submitted = route.request().postDataJSON();
      await route.fulfill({
        status: 409,
        json: { detail: 'Read the latest exchange before sending again.' },
      });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [{ ...chat, head_sequence: 2 }], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: 2 } });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items: [first], next_before: null, next_after: null } });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await composer.fill('Follow up on the answer I read');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(
    page.getByText('Read the latest exchange before sending again.', { exact: true }),
  ).toBeVisible();
  expect(submitted).toEqual({ question: 'Follow up on the answer I read', observed_head: 1 });
  await expect(composer).toHaveValue('Follow up on the answer I read');
});
function readyTurn(sequence: number, question: string, text: string, passage: string) {
  return {
    id: `turn-${sequence}`,
    conversation_id: chat.id,
    sequence,
    parent_sequence: sequence - 1,
    question,
    resolved_question: question,
    state: 'ready',
    created_at: time,
    started_at: time,
    finished_at: time,
    error: null,
    answer: { outcome: 'answer', statements: [{ text, source_ids: ['S1'] }] },
    citations: [{ source_id: 'S1', chunk_ordinal: sequence, text: passage, pages: [1] }],
    coverage: { diagnostics: [], pages_without_content: [] },
  };
}

test('long chats scroll within the reader and keep the app header in view', async ({ page }) => {
  const turns = Array.from({ length: 6 }, (_, i) =>
    readyTurn(i + 1, `Question ${i + 1}`, 'A source-backed answer. '.repeat(18), 'Evidence.'),
  );
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1') await route.fulfill({ json: chat });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items: turns, next_before: null } });
    else throw new Error(`Unexpected request ${path}`);
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/conversations/chat-1');
    await page.getByRole('textbox', { name: 'Your question' }).click();
    await expect(page.locator('.site-header')).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(844);
  }
});

test('waiting for history preparation stays readable and resumes without another send', async ({
  page,
}) => {
  const answer = readyTurn(1, 'What did we decide?', 'The saved answer.', 'Evidence.');
  let finished = false;
  const current = () =>
    finished
      ? answer
      : { ...answer, state: 'pending', context_state: 'preparing', answer: null, citations: [] };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    expect(route.request().method()).toBe('GET');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1') await route.fulfill({ json: chat });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items: [current()], next_before: null } });
    else if (path === '/conversations/chat-1/turns/turn-1')
      await route.fulfill({ json: current() });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await expect(page.getByText('Preparing conversation context…')).toBeVisible();
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await composer.fill('Keep this next question');
  await expect(page.getByRole('button', { name: 'Send question' })).toBeDisabled();
  finished = true;
  await expect(page.getByText('The saved answer.', { exact: true })).toBeVisible();
  await expect(composer).toHaveValue('Keep this next question');
  await expect(page.getByRole('button', { name: 'Send question' })).toBeEnabled();
});

test('a first-send conflict opens the current chat with its rejected question still editable', async ({
  page,
}) => {
  test.setTimeout(30000);
  const choice = {
    document_id: chat.document_id,
    index_id: chat.index_id,
    display_name: chat.document_name,
    created_at: time,
  };
  const first = readyTurn(
    1,
    'A question accepted in another tab?',
    'The latest saved answer.',
    'Evidence.',
  );
  const second = readyTurn(
    2,
    'Keep my first question draft',
    'The deliberate follow-up answer.',
    'More evidence.',
  );
  const keys: string[] = [];
  let creations = 0;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST' && path === '/conversations') {
      creations += 1;
      await route.fulfill({ status: 201, json: chat });
    } else if (route.request().method() === 'POST') {
      keys.push(route.request().headers()['idempotency-key']);
      expect(route.request().postDataJSON()).toEqual({
        question: second.question,
        observed_head: keys.length === 1 ? 0 : 1,
      });
      await route.fulfill(
        keys.length === 1
          ? { status: 409, json: { detail: 'Conversation changed. Review the latest exchange.' } }
          : { status: 202, json: second },
      );
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversation-documents')
      await route.fulfill({ json: { items: [choice], next_cursor: null } });
    else if (path === '/conversations/chat-1') await route.fulfill({ json: chat });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items: [first], next_before: null, next_after: null } });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).selectOption(chat.index_id);
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await composer.fill(second.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page).toHaveURL(/\/conversations\/chat-1$/);
  await expect(page.getByRole('region', { name: 'Exchange 1', exact: true })).toContainText(
    first.answer.statements[0].text,
  );
  await expect(composer).toBeEditable();
  await expect(composer).toHaveValue(second.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    second.answer.statements[0].text,
  );
  expect(creations).toBe(1);
  expect(keys).toHaveLength(2);
  expect(keys[1]).not.toBe(keys[0]);
  await page.getByRole('main').getByRole('link', { name: 'New chat', exact: true }).click();
  await expect(composer).toHaveValue('', { timeout: 5000 });
});

test('a follow-up stays in the same chat and each saved S1 opens its own evidence', async ({
  page,
}) => {
  test.setTimeout(30000);
  const first = readyTurn(
    1,
    chat.question,
    'Garage coverage is part of the building limit.',
    'The garage reduces the available building limit.',
  );
  const second = readyTurn(
    2,
    'What about business use?',
    'Business use is excluded here.',
    'A garage used for business is excluded.',
  );
  const turns = [first];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path.endsWith('/original')) {
      await route.fulfill({
        contentType: 'application/pdf',
        body: await readFile('../tests/fixtures/text.pdf'),
      });
    } else if (route.request().method() === 'POST') {
      expect(path).toBe('/conversations/chat-1/turns');
      expect(route.request().postDataJSON()).toEqual({
        question: second.question,
        observed_head: 1,
      });
      turns.push(second);
      await route.fulfill({
        status: 202,
        json: { ...second, state: 'pending', answer: null, citations: [] },
      });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({
        json: { items: [{ ...chat, head_sequence: turns.length }], next_cursor: null },
      });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: turns.length } });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items: turns, next_before: null, next_after: null } });
    else if (path === '/conversations/chat-1/turns/turn-2') await route.fulfill({ json: second });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await expect(composer).toBeVisible({ timeout: 5000 });
  await composer.fill(second.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByText(second.answer.statements[0].text, { exact: true })).toBeVisible();
  await expect(composer).toBeEditable();
  await expect(composer).toHaveValue('');
  await page.reload();
  const firstExchange = page.getByRole('region', { name: 'Exchange 1', exact: true });
  const secondExchange = page.getByRole('region', { name: 'Exchange 2', exact: true });
  await expect(firstExchange).toContainText(first.question);
  await expect(secondExchange).toContainText(second.question);
  for (const [exchange, passage] of [
    [firstExchange, first.citations[0].text],
    [secondExchange, second.citations[0].text],
  ] as const) {
    await exchange.getByRole('button', { name: 'Source S1, page 1' }).click();
    const source = page.getByRole('dialog', { name: 'Source', exact: true });
    await source.getByText('Retrieved passage · S1').click();
    await expect(source.getByText(passage, { exact: true })).toBeVisible();
    await source.getByRole('button', { name: 'Close source' }).click();
    await expect(exchange.getByRole('button', { name: 'Source S1, page 1' })).toBeFocused();
  }
});

test('an uncertain follow-up replays its saved head while its accepted turn is pending', async ({
  page,
}) => {
  test.setTimeout(30000);
  const first = readyTurn(1, chat.question, 'First answer.', 'First evidence.');
  const second = readyTurn(2, 'What about business use?', 'Second answer.', 'Second evidence.');
  const pending = { ...second, state: 'pending', answer: null, citations: [] };
  const submissions: { key: string; body: unknown }[] = [];
  let releasePoll!: () => void;
  let polling = false;
  const delayedPoll = new Promise<void>((resolve) => {
    releasePoll = resolve;
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      submissions.push({
        key: route.request().headers()['idempotency-key'],
        body: route.request().postDataJSON(),
      });
      await route.fulfill(
        submissions.length === 1
          ? { status: 503, json: { detail: 'Reply interrupted.' } }
          : { status: 202, json: second },
      );
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: submissions.length ? 2 : 1 } });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({
        json: {
          items: submissions.length ? [first, pending] : [first],
          next_before: null,
          next_after: null,
        },
      });
    else if (path === '/conversations/chat-1/turns/turn-2') {
      polling = true;
      await delayedPoll;
      await route.fulfill({ json: pending });
    } else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const composer = page.getByRole('textbox', { name: 'Your question' });
  const send = page.getByRole('button', { name: 'Send question' });
  await composer.fill(second.question);
  await send.click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.reload();
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    'Waiting to answer…',
  );
  await expect(composer).toHaveValue(second.question);
  await expect(composer).toBeDisabled();
  await expect(send).toBeEnabled();
  await expect.poll(() => polling).toBeTruthy();
  await send.click();
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    'Second answer.',
  );
  expect(submissions).toHaveLength(2);
  expect(submissions[1]).toEqual(submissions[0]);
  expect(submissions[1].body).toEqual({ question: second.question, observed_head: 1 });
  await composer.fill('My next unsent question');
  releasePoll();
  await expect(composer).toHaveValue('My next unsent question');
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    'Second answer.',
  );
});

test('a stale-head conflict refreshes history before another send while retaining the draft and failures', async ({
  page,
}) => {
  test.setTimeout(30000);
  const failed = {
    ...readyTurn(1, 'First question?', '', ''),
    state: 'failed',
    answer: null,
    citations: [],
    error: { code: 'CHAT_OUTPUT_INVALID', message: 'The first answer could not be completed.' },
  };
  const other = readyTurn(2, 'A question from another tab?', 'Other tab response.', 'Evidence.');
  const next = readyTurn(3, 'My follow-up draft?', 'Follow-up response.', 'More evidence.');
  let attempts = 0;
  let releaseHistory!: () => void;
  const refreshed = new Promise<void>((resolve) => {
    releaseHistory = resolve;
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      attempts += 1;
      expect(route.request().postDataJSON()).toEqual({
        question: next.question,
        observed_head: attempts === 1 ? 1 : 2,
      });
      await route.fulfill(
        attempts === 1
          ? { status: 409, json: { detail: 'Conversation changed. Review the latest exchange.' } }
          : { status: 202, json: next },
      );
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: attempts ? attempts + 1 : 1 } });
    else if (path === '/conversations/chat-1/turns') {
      if (attempts) await refreshed;
      await route.fulfill({
        json: { items: attempts ? [failed, other] : [failed], next_before: null, next_after: null },
      });
    } else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const composer = page.getByRole('textbox', { name: 'Your question' });
  const send = page.getByRole('button', { name: 'Send question' });
  await composer.fill(next.question);
  await send.click();
  await expect(
    page.getByText('Conversation changed. Review the latest exchange.', { exact: true }),
  ).toBeVisible();
  await expect(composer).toHaveValue(next.question);
  await expect(send).toBeDisabled({ timeout: 5000 });
  releaseHistory();
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    'Other tab response.',
  );
  await send.click();
  await expect(page.getByRole('region', { name: 'Exchange 3', exact: true })).toContainText(
    'Follow-up response.',
  );
  await expect(page.getByRole('region', { name: 'Exchange 1', exact: true })).toContainText(
    'The first answer could not be completed.',
  );
  await expect(composer).toHaveValue('');
});

test('history pages and transcript references open original exchanges without PDF citations', async ({
  page,
}) => {
  test.setTimeout(30000);
  const earlier = [
    readyTurn(1, 'My first exact question?', 'First response.', 'First passage.'),
    readyTurn(2, 'Second question?', 'Second response.', 'Second passage.'),
    readyTurn(3, 'Third question?', 'Third response.', 'Third passage.'),
  ];
  const recent = Array.from({ length: 19 }, (_, index) =>
    readyTurn(index + 4, `Question ${index + 4}?`, 'A saved response.', 'Document evidence.'),
  );
  const recall = {
    ...readyTurn(23, 'What was my first question?', '', ''),
    answer: {
      outcome: 'transcript',
      statements: [
        { text: 'You asked “My first exact question?”', source_ids: [], turn_ids: ['turn-1'] },
      ],
    },
    citations: [],
  };
  let referenceReads = 0;
  let olderReads = 0;
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    expect(route.request().method()).toBe('GET');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [{ ...chat, head_sequence: 23 }], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: 23 } });
    else if (path === '/conversations/chat-1/turns') {
      expect(url.searchParams.has('after')).toBeFalsy();
      if (url.searchParams.has('before_sequence')) {
        expect(url.searchParams.get('before_sequence')).toBe('4');
        olderReads += 1;
        await route.fulfill({ json: { items: earlier, next_before: null, next_after: null } });
      } else
        await route.fulfill({
          json: { items: [...recent, recall], next_before: 4, next_after: null },
        });
    } else if (path === '/conversations/chat-1/turns/turn-1') {
      referenceReads += 1;
      await route.fulfill({ json: earlier[0] });
    } else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const recalled = page.getByRole('region', { name: 'Exchange 23', exact: true });
  await expect(recalled.getByRole('button', { name: 'View original exchange' })).toBeVisible({
    timeout: 5000,
  });
  await expect(recalled.getByRole('button', { name: /^Source/ })).toHaveCount(0);
  await recalled.getByRole('button', { name: 'View original exchange' }).click();
  const original = page.getByRole('region', { name: 'Exchange 1', exact: true });
  await expect(original).toBeFocused();
  await expect(original).toContainText('My first exact question?');
  await expect(page.getByText('Exchanges 2–3 are not loaded.', { exact: false })).toBeVisible();
  expect(referenceReads).toBe(1);
  await page.getByRole('button', { name: 'Load earlier exchanges' }).click();
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toContainText(
    'Second question?',
  );
  await expect(original).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Load earlier exchanges' })).toHaveCount(0);
  expect(olderReads).toBe(1);
});

test('new questions remain visible while polling and older-page loads preserve reading position', async ({
  page,
}) => {
  test.setTimeout(30000);
  await page.setViewportSize({ width: 1200, height: 700 });
  const recent = Array.from({ length: 20 }, (_, index) =>
    readyTurn(
      index + 21,
      `Recent question ${index + 21}?`,
      'A saved answer with document evidence.',
      'Evidence.',
    ),
  );
  const earlier = Array.from({ length: 20 }, (_, index) =>
    readyTurn(index + 1, `Older question ${index + 1}?`, 'An older saved answer.', 'Evidence.'),
  );
  const next = readyTurn(41, 'My newest question?', 'The newest answer is ready.', 'New evidence.');
  let accepted = false;
  let olderRequested = false;
  let releasePoll!: () => void;
  let releaseOlder!: () => void;
  const pollReady = new Promise<void>((resolve) => {
    releasePoll = resolve;
  });
  const olderReady = new Promise<void>((resolve) => {
    releaseOlder = resolve;
  });
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      accepted = true;
      await route.fulfill({
        status: 202,
        json: { ...next, state: 'pending', answer: null, citations: [] },
      });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: accepted ? 41 : 40 } });
    else if (path === '/conversations/chat-1/turns') {
      if (url.searchParams.has('before_sequence')) {
        olderRequested = true;
        await olderReady;
        await route.fulfill({ json: { items: earlier, next_before: null, next_after: null } });
      } else await route.fulfill({ json: { items: recent, next_before: 21, next_after: null } });
    } else if (path === '/conversations/chat-1/turns/turn-41') {
      await pollReady;
      await route.fulfill({ json: next });
    } else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await expect(composer).toBeInViewport({ timeout: 5000 });
  await composer.fill(next.question);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(
    page
      .getByRole('region', { name: 'Exchange 41', exact: true })
      .getByText(next.question, { exact: true }),
  ).toBeInViewport();
  const oldView = page.getByRole('region', { name: 'Exchange 21', exact: true });
  await oldView.scrollIntoViewIfNeeded();
  const main = page.getByRole('main');
  const readingPosition = await main.evaluate((element) => element.scrollTop);
  releasePoll();
  await expect(page.getByText(next.answer.statements[0].text, { exact: true })).toHaveCount(1);
  expect(await main.evaluate((element) => element.scrollTop)).toBeCloseTo(readingPosition, 0);
  await page.getByRole('button', { name: 'Load earlier exchanges' }).click();
  await expect.poll(() => olderRequested).toBeTruthy();
  const oldTop = (await oldView.boundingBox())!.y;
  releaseOlder();
  await expect(page.getByRole('region', { name: 'Exchange 1', exact: true })).toHaveCount(1);
  expect((await oldView.boundingBox())!.y).toBeCloseTo(oldTop, 0);
});

test('a delayed older page cannot hide the gap discovered by a newer history refresh', async ({
  page,
}) => {
  test.setTimeout(30000);
  const group = (first: number) =>
    Array.from({ length: 20 }, (_, index) =>
      readyTurn(first + index, `Question ${first + index}?`, 'Saved answer.', 'Evidence.'),
    );
  let changed = false;
  let olderRequested = false;
  let releaseOlder!: () => void;
  const olderReady = new Promise<void>((resolve) => {
    releaseOlder = resolve;
  });
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      changed = true;
      await route.fulfill({ status: 409, json: { detail: 'Review the latest exchange.' } });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: changed ? 80 : 40 } });
    else if (path === '/conversations/chat-1/turns') {
      const before = url.searchParams.get('before_sequence');
      if (before === '21') {
        olderRequested = true;
        await olderReady;
        await route.fulfill({ json: { items: group(1), next_before: null, next_after: null } });
      } else if (before === '61')
        await route.fulfill({ json: { items: group(41), next_before: 41, next_after: null } });
      else if (!before)
        await route.fulfill({
          json: {
            items: group(changed ? 61 : 21),
            next_before: changed ? 61 : 21,
            next_after: null,
          },
        });
      else throw new Error(`Unexpected earlier page ${before}`);
    } else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const earlier = page.getByRole('button', { name: 'Load earlier exchanges', exact: true });
  await earlier.click();
  await expect.poll(() => olderRequested).toBeTruthy();
  const composer = page.getByRole('textbox', { name: 'Your question' });
  await composer.fill('Keep this draft after the conflict');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('region', { name: 'Exchange 80', exact: true })).toHaveCount(1);
  releaseOlder();
  await expect(page.getByRole('region', { name: 'Exchange 1', exact: true })).toHaveCount(1);
  await expect(page.getByText('Exchanges 41–60 are not loaded.', { exact: false })).toHaveCount(1);
  await expect(earlier).toBeEnabled({ timeout: 5000 });
  await earlier.click();
  await expect(page.getByRole('region', { name: 'Exchange 41', exact: true })).toHaveCount(1);
  await expect(page.getByText('Exchanges 41–60 are not loaded.', { exact: false })).toHaveCount(0);
  await expect(composer).toHaveValue('Keep this draft after the conflict');
});

test('the pinned document extraction gap is shown once across multiple exchanges', async ({
  page,
}) => {
  test.setTimeout(30000);
  const items = [1, 2].map((sequence) => ({
    ...readyTurn(sequence, `Question ${sequence}?`, 'Saved answer.', 'Evidence.'),
    coverage: { pages_without_content: [3], diagnostics: [] },
  }));
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1')
      await route.fulfill({ json: { ...chat, head_sequence: 2 } });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({ json: { items, next_before: null, next_after: null } });
    else throw new Error(`Unexpected request ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await expect(page.getByRole('region', { name: 'Exchange 2', exact: true })).toHaveCount(1);
  const note = page.getByRole('note').filter({ hasText: 'Some document content may be missing.' });
  await expect(note).toHaveCount(1, { timeout: 5000 });
  await expect(note.getByRole('link', { name: /extraction details/ })).toHaveAttribute(
    'href',
    '/documents/document-1',
  );
});
