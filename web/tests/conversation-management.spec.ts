import { expect, test } from '@playwright/test';

test('a late deleted-chat response cannot clear a newer uncertain submission', async ({ page }) => {
  test.setTimeout(30000);
  let releaseFirst!: () => void;
  const firstPending = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  const keys: string[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      keys.push(route.request().headers()['idempotency-key']);
      const number = keys.length;
      if (number === 1) await firstPending;
      await route.fulfill({
        status: number <= 2 ? 410 : 503,
        json: { detail: 'Submission unavailable.' },
      });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [], next_cursor: null } });
    else if (path === '/conversation-documents')
      await route.fulfill({
        json: {
          items: [{ document_id: 'doc-1', index_id: 'index-1', display_name: 'Coverage.pdf' }],
          next_cursor: null,
        },
      });
    else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/new-chat');
  await page.getByRole('combobox', { name: 'Document', exact: true }).click();
  await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
  const question = page.getByRole('textbox', { name: 'Your question' });
  await question.fill('Old question');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect.poll(() => keys.length).toBe(1);
  await page.getByRole('link', { name: 'Folio home' }).click();
  await page.getByRole('main').getByRole('link', { name: 'New chat', exact: true }).click();
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(question).toBeEditable();
  await question.fill('New question');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  const lateResponse = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.status() === 410,
  );
  releaseFirst();
  await (await lateResponse).finished();
  await page.reload();
  await expect(question).toHaveValue('New question');
  await expect(question).toBeDisabled();
  expect(keys[0]).toBe(keys[1]);
  expect(keys[2]).not.toBe(keys[0]);
});

test('a confirmed missing chat releases a saved-question retry and offers a new chat', async ({
  page,
}) => {
  test.setTimeout(30000);
  const chat = {
    id: 'chat-1',
    document_id: 'doc-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    title: 'Garage coverage',
    title_source: null,
    title_version: 0,
    question: null,
    state: 'empty',
    max_turns: 1,
  };
  const keys: string[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      keys.push(route.request().headers()['idempotency-key']);
      await route.fulfill({
        status: keys.length === 1 ? 503 : 404,
        json: { detail: 'Conversation not found.' },
      });
    } else if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1') await route.fulfill({ json: chat });
    else if (path.endsWith('/turns'))
      await route.fulfill({ json: { items: [], next_after: null } });
    else if (path === '/conversation-documents')
      await route.fulfill({ json: { items: [], next_cursor: null } });
    else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/conversations/chat-1');
  const question = page.getByRole('textbox', { name: 'Your question' });
  await question.fill('Keep this question');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
  await page.reload();
  await expect(question).toBeDisabled();
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(question).toBeEditable({ timeout: 5000 });
  await expect(question).toHaveValue('Keep this question');
  expect(keys[1]).toBe(keys[0]);
  expect(await page.evaluate(() => sessionStorage.getItem('folio:question:chat-1'))).toBeNull();
  await page.getByRole('link', { name: 'Start a new chat' }).click();
  await expect(page).toHaveURL(/\/new-chat$/);
  await expect(question).toBeEditable();
});

for (const terminal of [
  { stage: 'creation', status: 410 },
  { stage: 'question', status: 404 },
]) {
  test(`a confirmed ${terminal.status} ${terminal.stage} response releases the matching new-chat retry`, async ({
    page,
  }) => {
    test.setTimeout(30000);
    const choice = { document_id: 'doc-1', index_id: 'index-1', display_name: 'Coverage.pdf' };
    const creationKeys: string[] = [];
    let questions = 0;
    await page.route('**/api/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api', '');
      if (route.request().method() === 'POST') {
        if (path === '/conversations') {
          creationKeys.push(route.request().headers()['idempotency-key']);
          if (terminal.stage === 'creation' && creationKeys.length <= 2) {
            await route.fulfill({
              status: creationKeys.length === 1 ? 503 : terminal.status,
              json: { detail: 'Chat is no longer available.' },
            });
          } else await route.fulfill({ status: 201, json: { id: 'deleted-chat' } });
        } else {
          questions += 1;
          await route.fulfill({
            status: terminal.stage === 'question' && questions === 2 ? terminal.status : 503,
            json: { detail: 'Chat is no longer available.' },
          });
        }
      } else if (path === '/capabilities')
        await route.fulfill({ json: { development_mode: false } });
      else if (path === '/conversations')
        await route.fulfill({ json: { items: [], next_cursor: null } });
      else if (path === '/conversation-documents')
        await route.fulfill({ json: { items: [choice], next_cursor: null } });
      else throw new Error(`Unexpected API path ${path}`);
    });
    await page.goto('/new-chat');
    await page.getByRole('combobox', { name: 'Document', exact: true }).click();
    await page.getByRole('option', { name: 'Coverage.pdf', exact: true }).click();
    const question = page.getByRole('textbox', { name: 'Your question' });
    await question.fill('Keep my question');
    await page.getByRole('button', { name: 'Send question' }).click();
    await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
    await page.reload();
    await expect(question).toBeDisabled();
    await page.getByRole('button', { name: 'Send question' }).click();
    await expect(question).toBeEditable({ timeout: 5000 });
    await expect(question).toHaveValue('Keep my question');
    await expect(page).toHaveURL(/\/new-chat$/);
    expect(await page.evaluate(() => sessionStorage.getItem('folio:new-chat-intent'))).toBeNull();
    expect(
      await page.evaluate(() => sessionStorage.getItem('folio:question:deleted-chat')),
    ).toBeNull();
    await page.getByRole('button', { name: 'Send question' }).click();
    await expect(page.getByRole('alert')).toContainText('Retry sends the same question.');
    expect(creationKeys.at(-1)).not.toBe(creationKeys[0]);
  });
}

test('a deleted-chat poll removes the loaded transcript from the page', async ({ page }) => {
  test.setTimeout(30000);
  const chat = {
    id: 'chat-1',
    document_id: 'doc-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    title: 'Garage coverage',
    title_source: null,
    title_version: 0,
    created_at: '2026-01-01T12:00:00Z',
    question: 'Does the garage qualify?',
    state: 'running',
    max_turns: 1,
  };
  let deleted = false;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat], next_cursor: null } });
    else if (path === '/conversations/chat-1') await route.fulfill({ json: chat });
    else if (path === '/conversations/chat-1/turns')
      await route.fulfill({
        json: {
          items: [
            {
              id: 'turn-1',
              conversation_id: 'chat-1',
              question: chat.question,
              sequence: 1,
              state: 'running',
              answer: null,
              error: null,
              citations: [],
              coverage: { diagnostics: [], pages_without_content: [] },
            },
          ],
          next_after: null,
        },
      });
    else if (path === '/conversations/chat-1/turns/turn-1') {
      deleted = true;
      await route.fulfill({ status: 404, json: { detail: 'Question not found.' } });
    } else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await expect(
    page.getByRole('main').getByText('Does the garage qualify?', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Question not found.');
  expect(deleted).toBeTruthy();
  await expect(
    page.getByRole('main').getByText('Does the garage qualify?', { exact: true }),
  ).toHaveCount(0, { timeout: 5000 });
});

test('a delayed history load cannot replace a newly renamed title', async ({ page }) => {
  test.setTimeout(30000);
  let releaseHistory!: () => void;
  const historyReady = new Promise<void>((resolve) => {
    releaseHistory = resolve;
  });
  let title = 'Initial title';
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    const chat = () => ({
      id: 'chat-1',
      document_id: 'doc-1',
      revision_id: 'revision-1',
      index_id: 'index-1',
      document_name: 'Coverage.pdf',
      title,
      title_source: 'manual',
      title_version: 0,
      created_at: '2026-01-01T12:00:00Z',
      question: null,
      state: 'empty',
      max_turns: 1,
    });
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat()], next_cursor: null } });
    else if (path.endsWith('/turns')) {
      await historyReady;
      await route.fulfill({ json: { items: [], next_after: null } });
    } else if (path === '/conversations/chat-1') {
      if (route.request().method() === 'PATCH') title = 'Updated title';
      await route.fulfill({ json: chat() });
    } else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await page.getByRole('button', { name: 'Actions for Initial title' }).click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  const dialog = page.getByRole('dialog', { name: 'Rename chat' });
  await dialog.getByRole('textbox', { name: 'Chat title' }).fill('Updated title');
  await dialog.getByRole('button', { name: 'Save title' }).click();
  await expect(page.getByRole('heading', { name: 'Updated title', exact: true })).toBeVisible();
  releaseHistory();
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Updated title', exact: true })).toBeVisible({
    timeout: 5000,
  });
});

test('renaming a chat updates its title without losing the draft and survives reload', async ({
  page,
}) => {
  test.setTimeout(30000);
  let refreshAvailable = true;
  let chat = {
    id: 'chat-1',
    document_id: 'doc-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    title: 'Garage coverage',
    title_source: 'generated',
    title_version: 0,
    created_at: '2026-01-01T12:00:00Z',
    question: null,
    state: 'empty',
    max_turns: 1,
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') {
      await route.fulfill({ json: { development_mode: false } });
    } else if (path === '/conversations') {
      await route.fulfill(
        refreshAvailable
          ? { json: { items: [chat], next_cursor: null } }
          : { status: 503, json: { detail: 'History refresh unavailable.' } },
      );
    } else if (path === '/conversations/chat-1/turns') {
      await route.fulfill({ json: { items: [], next_after: null } });
    } else if (path === '/conversations/chat-1') {
      if (route.request().method() === 'PATCH') {
        expect(route.request().postDataJSON()).toEqual({
          title: 'My garage questions',
          expected_version: 0,
        });
        chat = { ...chat, title: 'My garage questions', title_source: 'manual', title_version: 1 };
        refreshAvailable = false;
        await route.fulfill({ json: chat });
      } else {
        await route.fulfill(
          refreshAvailable
            ? { json: chat }
            : { status: 503, json: { detail: 'Chat refresh unavailable.' } },
        );
      }
    } else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await expect(page.getByRole('heading', { name: 'Garage coverage', exact: true })).toBeVisible({
    timeout: 5000,
  });
  const draft = page.getByRole('textbox', { name: 'Your question' });
  await draft.fill('What about a detached garage?');
  await page.getByRole('button', { name: 'Actions for Garage coverage' }).click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  const dialog = page.getByRole('dialog', { name: 'Rename chat' });
  await dialog.getByRole('textbox', { name: 'Chat title' }).fill('My garage questions');
  await dialog.getByRole('button', { name: 'Save title' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'My garage questions', exact: true }),
  ).toBeVisible();
  await expect(draft).toHaveValue('What about a detached garage?');
  await expect(page).toHaveTitle('My garage questions · Folio');
  await expect(page.getByRole('link', { name: /My garage questions/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry history' })).toBeVisible();
  refreshAvailable = true;
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'My garage questions', exact: true }),
  ).toBeVisible();
  await expect(draft).toHaveValue('What about a detached garage?');
});

test('deleting an inactive chat keeps the view, deleting the active chat opens a clean new chat', async ({
  page,
}) => {
  test.setTimeout(30000);
  const deleted = new Set<string>();
  let historyUnavailable = false;
  const chats = ['first', 'second'].map((id) => ({
    id,
    document_id: 'doc-1',
    revision_id: 'revision-1',
    index_id: 'index-1',
    document_name: 'Coverage.pdf',
    title: `${id} chat`,
    title_source: 'manual',
    title_version: 0,
    created_at: '2026-01-01T12:00:00Z',
    question: null,
    state: 'empty',
    max_turns: 1,
  }));
  await page.addInitScript(() => {
    if (sessionStorage.getItem('test-seeded')) return;
    sessionStorage.setItem('test-seeded', 'true');
    const document = { document_id: 'doc-1', index_id: 'index-1', display_name: 'Coverage.pdf' };
    sessionStorage.setItem(
      'folio:new-chat-intent',
      JSON.stringify({
        id: 'old-draft',
        conversationId: 'second',
        question: 'Old question',
        document,
        creationKey: 'create-second',
        questionKey: 'question-second',
      }),
    );
    sessionStorage.setItem(
      'folio:new-chat-draft',
      JSON.stringify({ id: 'different-draft', question: 'Unrelated new question', document }),
    );
    sessionStorage.setItem(
      'folio:question:second',
      JSON.stringify({ key: 'question-second', question: 'Old question' }),
    );
    sessionStorage.setItem('folio:draft:second', 'Old question');
    sessionStorage.setItem('folio:question:unrelated', 'unrelated intent');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill(
        historyUnavailable
          ? { status: 503, json: { detail: 'History unavailable.' } }
          : {
              json: { items: chats.filter((chat) => !deleted.has(chat.id)), next_cursor: null },
            },
      );
    else if (path === '/conversation-documents')
      await route.fulfill({
        json: {
          items: [
            {
              document_id: 'doc-1',
              index_id: 'index-1',
              display_name: 'Coverage.pdf',
              created_at: '2026-01-01T12:00:00Z',
            },
          ],
          next_cursor: null,
        },
      });
    else {
      const id = path.split('/')[2];
      if (route.request().method() === 'DELETE') {
        deleted.add(id);
        historyUnavailable = id === 'second';
        await route.fulfill({ status: 204 });
      } else if (path.endsWith('/turns'))
        await route.fulfill({ json: { items: [], next_after: null } });
      else await route.fulfill({ json: chats.find((chat) => chat.id === id) });
    }
  });
  await page.goto('/conversations/first');
  await page.getByRole('textbox', { name: 'Your question' }).fill('Keep this current draft');
  await page.getByRole('button', { name: 'Actions for second chat' }).click();
  await page.getByRole('menuitem', { name: 'Delete' }).click({ timeout: 5000 });
  const dialog = page.getByRole('dialog', { name: 'Delete chat?' });
  await expect(dialog).toContainText(
    'Internal transcript, diagnostics and billing records are retained.',
  );
  await dialog.getByRole('button', { name: 'Delete chat', exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page).toHaveURL(/\/conversations\/first$/);
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'Keep this current draft',
  );
  await expect(page.getByRole('button', { name: 'Retry history' })).toBeVisible();
  await expect(page.getByRole('link', { name: /second chat/ })).toHaveCount(0, { timeout: 5000 });
  historyUnavailable = false;
  await page.reload();
  await expect(page.getByRole('link', { name: /second chat/ })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Open conversation history' }).click();
  const drawer = page.getByRole('dialog', { name: 'Conversation history' });
  await drawer.getByRole('button', { name: 'Actions for first chat' }).click();
  await page.getByRole('menuitem', { name: 'Delete' }).click();
  await dialog.getByRole('button', { name: 'Delete chat', exact: true }).click();
  await expect(page).toHaveURL(/\/new-chat$/);
  await expect(drawer).not.toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('textbox', { name: 'Your question' })).toHaveValue(
    'Unrelated new question',
  );
  await expect(page.getByRole('textbox', { name: 'Your question' })).toBeEditable();
  const stored = await page.evaluate(() => ({
    first: sessionStorage.getItem('folio:draft:first'),
    second: sessionStorage.getItem('folio:question:second'),
    transferred: sessionStorage.getItem('folio:new-chat-intent'),
    unrelated: sessionStorage.getItem('folio:question:unrelated'),
  }));
  expect(stored).toEqual({
    first: null,
    second: null,
    transferred: null,
    unrelated: 'unrelated intent',
  });
});

test('a mobile rename conflict keeps the typed title for a deliberate retry', async ({ page }) => {
  test.setTimeout(30000);
  await page.setViewportSize({ width: 390, height: 844 });
  let version = 0;
  let title = 'Garage coverage';
  const versions: number[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    const chat = () => ({
      id: 'chat-1',
      document_id: 'doc-1',
      revision_id: 'revision-1',
      index_id: 'index-1',
      document_name: 'Coverage.pdf',
      title,
      title_source: 'manual',
      title_version: version,
      created_at: '2026-01-01T12:00:00Z',
      question: null,
      state: 'empty',
      max_turns: 1,
    });
    if (path === '/capabilities') await route.fulfill({ json: { development_mode: false } });
    else if (path === '/conversations')
      await route.fulfill({ json: { items: [chat()], next_cursor: null } });
    else if (path.endsWith('/turns'))
      await route.fulfill({ json: { items: [], next_after: null } });
    else if (path === '/conversations/chat-1') {
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON();
        versions.push(body.expected_version);
        if (versions.length === 1) {
          title = 'Other tab title';
          version = 1;
          await route.fulfill({
            status: 409,
            json: { detail: 'This chat title changed. Reload it before renaming.' },
          });
          return;
        }
        title = body.title;
        version = 2;
      }
      await route.fulfill({ json: chat() });
    } else throw new Error(`Unexpected API path ${path}`);
  });
  await page.goto('/conversations/chat-1');
  await page.getByRole('button', { name: 'Open conversation history' }).click();
  const drawer = page.getByRole('dialog', { name: 'Conversation history' });
  await drawer.getByRole('button', { name: 'Actions for Garage coverage' }).click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  const dialog = page.getByRole('dialog', { name: 'Rename chat' });
  await expect(dialog).toHaveCount(1);
  const input = dialog.getByRole('textbox', { name: 'Chat title' });
  await input.fill('My chosen title');
  await dialog.getByRole('button', { name: 'Save title' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Other tab title', { timeout: 5000 });
  await expect(input).toHaveValue('My chosen title');
  await dialog.getByRole('button', { name: 'Save title' }).click();
  await expect(dialog).not.toBeVisible();
  expect(versions).toEqual([0, 1]);
  await expect(drawer.getByRole('link', { name: /My chosen title/ })).toBeVisible();
  await expect(drawer.getByRole('button', { name: 'Actions for My chosen title' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole('heading', { name: 'My chosen title' })).toBeVisible();
});
