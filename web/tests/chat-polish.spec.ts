import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const chat = {
  id: 'chat-1',
  document_id: 'document-1',
  index_id: 'index-1',
  document_name: 'Coverage.pdf',
  title: 'Coverage',
  state: 'ready',
  head_sequence: 1,
  created_at: '2026-01-01T12:00:00Z',
};
const answer = {
  id: 'turn-1',
  conversation_id: chat.id,
  sequence: 1,
  question: 'What is covered?',
  state: 'ready',
  error: null,
  answer: {
    outcome: 'answer',
    statements: [{ text: 'A documented answer. '.repeat(250), source_ids: [] as string[] }],
  },
  citations: [] as { source_id: string; chunk_ordinal: number; text: string; pages: number[] }[],
  coverage: { diagnostics: [], pages_without_content: [2] },
};

async function savedChat(page: Page, turn = answer) {
  const submissions: unknown[] = [];
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'POST') {
      submissions.push(route.request().postDataJSON());
      await route.fulfill({ status: 409, json: { detail: 'Another exchange arrived.' } });
    } else if (path.endsWith('/original')) {
      await route.fulfill({
        contentType: 'application/pdf',
        body: await readFile('../tests/fixtures/text.pdf'),
      });
    } else {
      const responses: Record<string, unknown> = {
        '/capabilities': { development_mode: false },
        '/conversations': { items: [chat], next_cursor: null },
        '/conversations/chat-1': chat,
        '/conversations/chat-1/turns': { items: [turn], next_before: null },
      };
      expect(path in responses, path).toBeTruthy();
      await route.fulfill({ json: responses[path] });
    }
  });
  await page.goto('/conversations/chat-1');
  return submissions;
}

test('composer stays visible while reading and Enter sends only outside multiline or IME input', async ({
  page,
}) => {
  const submissions = await savedChat(page);
  const input = page.getByRole('textbox', { name: 'Your question' });
  await input.fill('First line');
  await input.press('Shift+Enter');
  await input.pressSequentially('Second');
  await expect(input).toHaveValue('First line\nSecond');
  await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true });
  expect(submissions).toHaveLength(0);
  await input.press('Enter');
  await expect.poll(() => submissions.length).toBe(1);
  expect(submissions[0]).toEqual({ question: 'First line\nSecond', observed_head: 1 });
  for (const width of [1440, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await input.fill('A short question');
    const before = await input.boundingBox();
    await page.getByRole('article', { name: 'Your question' }).scrollIntoViewIfNeeded();
    const after = await input.boundingBox();
    expect(after!.y).toBeCloseTo(before!.y, 0);
    expect(after!.height).toBeLessThan(60);
    await expect(input).toBeInViewport();
    const content = await page.locator('.chat-content').boundingBox();
    const dock = await page.locator('.chat-composer-dock').boundingBox();
    expect(dock!.x).toBeCloseTo(content!.x, 0);
    expect(dock!.width).toBeCloseTo(content!.width, 0);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(844);
  }
  const notice = page.getByText('AI-generated answers. Check the sources.', { exact: true });
  await expect(notice).toBeVisible();
  expect((await notice.boundingBox())!.y).toBeGreaterThan((await input.boundingBox())!.y);
  await expect(page.getByText('Extraction gaps may affect answers.')).toHaveCount(0);
});

test('Markdown stays readable without executable markup or remote images', async ({ page }) => {
  const markdown =
    '**Coverage**\n\n- First condition\n- Second condition\n\n| Limit | Amount |\n| --- | --- |\n| Garage | 10% |\n\n[Unsafe](javascript:alert(1)) ![tracking](https://example.com/tracker.png) <script>alert(1)</script>';
  await savedChat(page, {
    ...answer,
    answer: { outcome: 'answer', statements: [{ text: markdown, source_ids: [] }] },
  });
  const response = page.getByRole('article', { name: 'Folio answer' });
  await expect(response.locator('strong')).toHaveText('Coverage');
  await expect(response.getByRole('listitem')).toHaveCount(2);
  await expect(response.getByRole('cell', { name: '10%' })).toBeVisible();
  await expect(response.locator('img, script, a[href^="javascript:"]')).toHaveCount(0);
});

test('citations sit inline with the final formatted paragraph and open their passage', async ({
  page,
}) => {
  await savedChat(page, {
    ...answer,
    answer: {
      outcome: 'answer',
      statements: [
        { text: 'A short introduction.\n\nThe limit is **10%**.', source_ids: ['S1'] },
        { text: 'Conditions still apply.', source_ids: ['S1'] },
        { text: '- First item\n- Second item', source_ids: ['S1'] },
        { text: '```text\nA quoted example.\n```', source_ids: ['S1'] },
      ],
    },
    citations: [
      {
        source_id: 'S1',
        chunk_ordinal: 0,
        text: 'The limit is 10%, subject to conditions.',
        pages: [1],
      },
    ],
  });
  const response = page.getByRole('article', { name: 'Folio answer' });
  const paragraph = response.locator('p').filter({ hasText: 'The limit is 10%.' });
  const citation = response
    .getByRole('button', { name: 'See passage 1 for this statement' })
    .first();
  const textBox = await paragraph.boundingBox();
  const citationBox = await citation.boundingBox();
  expect(
    Math.abs(citationBox!.y + citationBox!.height / 2 - (textBox!.y + textBox!.height / 2)),
  ).toBeLessThan(8);
  expect(citationBox!.x).toBeGreaterThan(textBox!.x + textBox!.width);
  await expect(response.getByRole('listitem')).toHaveCount(2);
  await expect(response.locator('pre')).toHaveText('A quoted example.\n');
  await expect(response.locator('pre button')).toHaveCount(0);
  await citation.click();
  await expect(page.getByRole('dialog', { name: 'Sources' })).toContainText(
    'The limit is 10%, subject to conditions.',
  );
});

test('passage previews open every cited passage with a page link and restore focus', async ({
  page,
}) => {
  const citations = Array.from({ length: 6 }, (_, index) => ({
    source_id: `S${index + 1}`,
    chunk_ordinal: index,
    text: `Evidence passage ${index + 1}: ${'The exact wording and its qualification. '.repeat(30)}`,
    pages: [1],
  }));
  await savedChat(page, {
    ...answer,
    citations,
    answer: {
      outcome: 'answer',
      statements: [
        { text: 'A supported answer.', source_ids: citations.map((source) => source.source_id) },
      ],
    },
  });
  const response = page.getByRole('article', { name: 'Folio answer' });
  await expect(response.getByRole('button', { name: /^Source S/ })).toHaveCount(5);
  await expect(response.getByText(/Evidence passage 1:/)).toBeVisible();
  const more = response.getByRole('button', { name: '1 more source' });
  await more.click();
  const drawer = page.getByRole('dialog', { name: 'Sources', exact: true });
  await expect(drawer.getByRole('link', { name: 'Extraction details' })).toHaveAttribute(
    'href',
    '/documents/document-1',
  );
  await expect(drawer.getByRole('article')).toHaveCount(6);
  await expect(drawer.getByText(citations[5].text, { exact: true })).toBeVisible();
  await drawer.getByRole('button', { name: 'View page 1 in original' }).last().click();
  await expect(drawer.getByRole('spinbutton', { name: 'PDF page number' })).toHaveValue('1');
  await drawer.getByRole('button', { name: 'Back to passages' }).click();
  await expect(drawer.getByRole('article')).toHaveCount(6);
  await page.keyboard.press('Escape');
  await expect(more).toBeFocused();
  await response.getByRole('button', { name: /^Source S5, page 1:/ }).click();
  await expect(drawer.getByRole('heading', { name: 'Passage 5', exact: true })).toBeInViewport();
});

test('document dropdown supports keyboard selection inside the composer', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false },
      '/conversations': { items: [], next_cursor: null },
      '/conversation-documents': {
        items: [
          {
            document_id: 'doc-1',
            index_id: 'index-1',
            display_name: 'Coverage.pdf',
            created_at: chat.created_at,
          },
        ],
        next_cursor: null,
      },
    };
    expect(route.request().method()).toBe('GET');
    expect(path in responses).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/new-chat');
  const document = page.getByRole('combobox', { name: 'Document', exact: true });
  await document.focus();
  await document.press('Enter');
  await expect(page.getByRole('listbox')).toBeVisible();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(document).toHaveText('Coverage.pdf');
  await expect(document).toBeFocused();
});

test('settings dropdown resets unsaved selection and submits the selected value', async ({
  page,
}) => {
  const values = {
    max_pages: 100,
    max_upload_bytes: 26214400,
    parser_timeout_seconds: 300,
    summary_enabled: true,
    summary_input_limit_tokens: 16384,
    summary_max_output_tokens: 4096,
    summary_reasoning_effort: 'none',
  };
  const configuration = {
    revision: 1,
    updated_at: chat.created_at,
    values,
    runtime: {
      job_timeout_seconds: 420,
      reasoning_options: ['none', 'low'],
      budget_usd: '1',
      spent_usd: '0',
      held_usd: '0',
      remaining_usd: '1',
    },
  };
  let submitted: { values: typeof values } | undefined;
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (route.request().method() === 'PUT') {
      submitted = route.request().postDataJSON();
      await route.fulfill({ json: { ...configuration, revision: 2, values: submitted!.values } });
    } else {
      const responses: Record<string, unknown> = {
        '/capabilities': { development_mode: true },
        '/conversations': { items: [], next_cursor: null },
        '/development/settings': configuration,
      };
      expect(path in responses).toBeTruthy();
      await route.fulfill({ json: responses[path] });
    }
  });
  await page.goto('/development/settings');
  const effort = page.getByRole('combobox', { name: 'Reasoning effort' });
  await effort.click();
  await page.getByRole('option', { name: 'low', exact: true }).click();
  await page.getByRole('button', { name: 'Reset unsaved changes' }).click();
  await expect(effort).toHaveText('none');
  await effort.click();
  await page.getByRole('option', { name: 'low', exact: true }).click();
  await page.getByRole('button', { name: 'Save settings', exact: true }).click();
  await expect.poll(() => submitted?.values.summary_reasoning_effort).toBe('low');
  await expect(effort).toHaveText('low');
});
