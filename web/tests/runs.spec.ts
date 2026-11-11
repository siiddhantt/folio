import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('Runs reopens a persisted upload without becoming home history', async ({ page, request }) => {
  const filename = `Reading report ${Date.now()}.pdf`;
  const uploaded = await request.post('/api/documents', {
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    multipart: {
      file: {
        name: filename,
        mimeType: 'application/pdf',
        buffer: await readFile('../tests/fixtures/text.pdf'),
      },
    },
  });
  expect(uploaded.ok()).toBeTruthy();
  const receipt = await uploaded.json();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Processing runs' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Runs', exact: true }).click({ timeout: 5000 });
  await expect(page.getByRole('heading', { name: 'Processing runs' })).toBeVisible();
  await page.reload();
  const row = page.getByRole('row').filter({ hasText: filename });
  await expect(row).toContainText('Disabled');
  await row.getByRole('link', { name: filename }).click();
  await expect(page).toHaveURL(new RegExp(`/documents/${receipt.document_id}$`));
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
});

test('Activity follows summary completion and keeps an uncertain bill distinct from zero', async ({
  page,
}) => {
  let reads = 0;
  await page.route('**/api/development/ingestion-requests/*', async (route) => {
    const response = await route.fetch();
    const inspection = await response.json();
    const running = ++reads === 1;
    inspection.summary = {
      id: 'summary-1',
      state: running ? 'running' : 'failed',
      created_at: inspection.created_at,
      started_at: inspection.created_at,
      finished_at: running ? null : inspection.finished_at,
      error_code: running ? null : 'SUMMARY_PROVIDER_TIMEOUT',
      attempts: [
        {
          id: 'summary-attempt-1',
          attempt_no: 1,
          state: running ? 'running' : 'failed',
          started_at: inspection.created_at,
          invoked_at: inspection.created_at,
          finished_at: running ? null : inspection.finished_at,
          error_code: running ? null : 'SUMMARY_PROVIDER_TIMEOUT',
          response_id: null,
          billing_state: running ? 'reserved' : 'unknown',
          reserved_usd: 0.03,
          cost_usd: null,
          usage: { prompt_tokens: null, completion_tokens: null, reasoning_tokens: null },
          failure_diagnostics: running
            ? null
            : {
                error_type: 'TimeoutError',
                error_frames: [
                  { module: 'folio.summaries.processing', function: 'execute', line: 42 },
                ],
              },
        },
      ],
    };
    await route.fulfill({ response, json: inspection });
  });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Evidence available');
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const summary = page.getByRole('region', { name: 'Summary execution' });
  await expect(summary).toContainText('running', { timeout: 5000 });
  await expect(summary).toContainText('failed', { timeout: 10000 });
  await summary.getByText('Summary attempt 1', { exact: false }).click();
  await expect(summary).toContainText('Unknown');
  await expect(summary).toContainText('$0.030000');
  await expect(summary).toContainText('TimeoutError');
  await expect(summary).toContainText('folio.summaries.processing.execute:42');
  await expect(summary).not.toContainText('$0.000000');
});
