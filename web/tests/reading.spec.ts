import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('large extraction gaps stay compact while recovered content remains readable', async ({
  page,
}) => {
  let alternating = false;
  await page.route('**/api/revisions/*/evidence?*', async (route) => {
    const response = await route.fetch();
    const evidence = await response.json();
    evidence.pages = Array.from({ length: 3000 }, (_, index) => ({
      page_no: index + 1,
      content_observation: (alternating ? index % 2 === 0 : index < 3)
        ? 'content_recovered'
        : 'no_content_recovered',
      diagnostics:
        index < 3
          ? []
          : [
              {
                category: 'timeout',
                error_message: 'Document timeout exceeded',
                page_no: index + 1,
              },
            ],
    }));
    evidence.diagnostics = [{ category: 'timeout', error_message: 'Document timeout exceeded' }];
    await route.fulfill({ response, json: evidence });
  });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  const content = page.getByRole('region', { name: 'Extracted evidence' });
  await expect(content).toContainText('125,000');
  const coverage = page.getByRole('note', { name: 'Extraction coverage' });
  await expect(coverage).toContainText('Content recovered from 3 of 3,000 pages', {
    timeout: 10000,
  });
  await expect(coverage).toContainText('Processing reached its time limit');
  await expect(coverage.getByRole('button')).toHaveCount(0);
  await coverage.getByText('Coverage details', { exact: true }).click();
  await expect(coverage.getByRole('button', { name: 'Inspect pages 4–3,000' })).toBeVisible();
  await expect(coverage.getByRole('listitem')).toHaveCount(10);
  await coverage.getByRole('button', { name: 'Next diagnostic page' }).click();
  await expect(coverage.getByRole('listitem')).toHaveCount(10);
  await expect(page.getByRole('status')).toContainText('Partial extraction');
  alternating = true;
  await page.reload();
  await expect(coverage).toContainText('Content recovered from 1,500 of 3,000 pages');
  await coverage.getByText('Coverage details', { exact: true }).click();
  await expect(coverage.getByRole('button', { name: /^Inspect page / })).toHaveCount(10);
  await coverage.getByRole('button', { name: 'Next range page' }).click();
  await expect(coverage.getByRole('button', { name: /^Inspect page / })).toHaveCount(10);
  await expect(
    coverage.getByRole('button', { name: 'Inspect page 22', exact: true }),
  ).toBeVisible();
  await expect(coverage.getByRole('listitem')).toHaveCount(10);
});

test('activity opens in a keyboard-accessible side panel without replacing content', async ({
  page,
}) => {
  await page.setViewportSize({ width: 960, height: 520 });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
  const activity = page.getByRole('button', { name: 'Activity', exact: true });
  await expect(activity).toBeVisible({ timeout: 10000 });
  await activity.focus();
  await page.keyboard.press('Enter');
  const panel = page.getByRole('dialog', { name: 'Activity', exact: true });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('list', { name: 'Recorded processing events' })).toContainText(
    'Evidence published',
  );
  await panel.getByRole('button', { name: 'Close activity' }).focus();
  await page.keyboard.press('Tab');
  const inspection = panel.getByRole('region', { name: 'Development inspection' });
  await expect(inspection).toBeFocused({ timeout: 3000 });
  await page.keyboard.press('PageDown');
  await expect.poll(() => inspection.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  await panel.getByRole('button', { name: 'Close activity' }).focus();
  await page.keyboard.press('Shift+Tab');
  expect(await panel.evaluate((node) => node.contains(document.activeElement))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(panel).not.toBeVisible();
  await expect(activity).toBeFocused();
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
});

test('the original renders one page and mobile citations switch views without losing content', async ({
  page,
}) => {
  test.setTimeout(30000);
  const time = '2026-01-01T12:00:00Z';
  await page.route('**/api/**', async (route) => {
    expect(route.request().method()).toBe('GET');
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path.endsWith('/original')) {
      await route.fulfill({
        contentType: 'application/pdf',
        body: await readFile('../tests/fixtures/text.pdf'),
      });
      return;
    }
    const responses: Record<string, unknown> = {
      '/capabilities': { development_mode: false, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: [], next_cursor: null },
      '/documents/reading-document': {
        id: 'reading-document',
        display_name: 'Operating report.pdf',
        created_at: time,
        current_request_id: 'reading-request',
        active_revision_id: 'reading-revision',
      },
      '/ingestion-requests/reading-request': {
        request_id: 'reading-request',
        document_id: 'reading-document',
        revision_id: 'reading-revision',
        state: 'succeeded',
        authorized_attempt_id: 'reading-attempt',
        created_at: time,
        finished_at: time,
        attempts: [],
      },
      '/revisions/reading-revision/evidence': {
        revision_id: 'reading-revision',
        diagnostics: [],
        next_after_order: null,
        pages: [1, 2].map((page_no) => ({
          page_no,
          content_observation: 'content_recovered',
          diagnostics: [],
        })),
        elements: Array.from({ length: 10 }, (_, index) => ({
          element_id: `paragraph-${index}`,
          reading_order: index,
          kind: 'text',
          table_data: null,
          text:
            index === 9
              ? 'Revenue was 125,000.'
              : 'The operating report describes revenue, costs and annual changes. Read the original page to verify each figure and qualification.',
          locations: [{ page_no: index === 9 ? 2 : 1, x0: null, y0: null, x1: null, y1: null }],
        })),
      },
      '/revisions/reading-revision/summary': { state: 'not_scheduled' },
      '/revisions/reading-revision/index': { state: 'not_started', index_id: null },
    };
    expect(path in responses, `Unexpected API read: ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  let originalRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/original?inline=true')) originalRequests += 1;
  });
  await page.goto('/documents/reading-document');
  const content = page.getByRole('region', { name: 'Extracted evidence' });
  await expect(content).toContainText('125,000');
  const original = page.getByRole('region', { name: 'Original PDF' });
  await expect(original.getByLabel('PDF page number')).toHaveValue('1', { timeout: 10000 });
  await expect(original.getByText('Sample operating report', { exact: true })).toBeVisible();
  const loadedRequests = originalRequests;
  expect(loadedRequests).toBeGreaterThan(0);
  await original.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(original.getByLabel('PDF page number')).toHaveValue('2');
  await expect(original).toContainText('125,000');
  await expect(original.locator('canvas')).toHaveCount(1);
  await expect(original.locator('iframe')).toHaveCount(0);
  expect(originalRequests).toBe(loadedRequests);
  await page.setViewportSize({ width: 390, height: 520 });
  await expect(page.getByRole('tab', { name: 'Content', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(original).not.toBeVisible();
  const citation = content
    .getByRole('button', { name: 'View page 2 in original', exact: true })
    .first();
  await citation.scrollIntoViewIfNeeded();
  const readingPosition = await page.getByRole('main').evaluate((node) => node.scrollTop);
  expect(readingPosition).toBeGreaterThan(0);
  await citation.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('tab', { name: 'Original', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(original.getByLabel('PDF page number')).toHaveValue('2');
  await expect(original).toContainText('125,000');
  await expect(page.getByRole('tab', { name: 'Original', exact: true })).toBeFocused({
    timeout: 3000,
  });
  const paper = original.getByRole('region', { name: 'Original page', exact: true });
  await paper.focus();
  await page.keyboard.press('PageDown');
  await expect.poll(() => paper.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  await page.getByRole('tab', { name: 'Content', exact: true }).click();
  await expect(content).toContainText('125,000');
  await expect
    .poll(() => page.getByRole('main').evaluate((node) => node.scrollTop), { timeout: 5000 })
    .toBeCloseTo(readingPosition, -1);
  const width = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(width.page).toBeLessThanOrEqual(width.viewport);
});

test('a canvas rendering failure leaves evidence usable and another page can still open', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const fillRect = CanvasRenderingContext2D.prototype.fillRect;
    CanvasRenderingContext2D.prototype.fillRect = function (...args) {
      if (
        this.canvas instanceof HTMLCanvasElement &&
        this.canvas.classList.contains('react-pdf__Page__canvas')
      ) {
        CanvasRenderingContext2D.prototype.fillRect = fillRect;
        throw new Error('Synthetic canvas rendering failure');
      }
      return fillRect.apply(this, args);
    };
  });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  const original = page.getByRole('region', { name: 'Original PDF' });
  await expect(original.getByLabel('PDF page number')).toHaveValue('1');
  await expect(original).toContainText('This page could not be displayed', { timeout: 5000 });
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
  await expect(page.getByRole('link', { name: 'Download PDF' })).toBeVisible();
  await original.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(original).toContainText('125,000');
  await expect(original.locator('canvas')).toBeVisible();
  await expect(original).not.toContainText('This page could not be displayed');
});

test('a failed parse with partial parser output is still labeled as failed', async ({ page }) => {
  await page.route('**/api/ingestion-requests/*', async (route) => {
    const response = await route.fetch();
    const status = await response.json();
    status.state = 'failed';
    status.revision_id = null;
    status.attempts = status.attempts.map((attempt: object) => ({
      ...attempt,
      state: 'failed',
      parser_status: 'partial_success',
      error_code: 'NO_USABLE_CONTENT',
      error_detail: 'No usable text or tables were recovered.',
    }));
    await route.fulfill({ response, json: status });
  });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Could not extract this PDF', {
    timeout: 5000,
  });
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText(
    'No extracted content',
  );
  await expect(page.getByRole('link', { name: 'Download PDF' })).toBeVisible();
});
