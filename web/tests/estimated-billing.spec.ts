import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('Activity labels direct summary and embedding costs as estimates', async ({ page }) => {
  const time = '2026-01-01T12:00:00Z';
  const status = {
    request_id: 'request-1',
    document_id: 'document-1',
    revision_id: 'revision-1',
    state: 'succeeded',
    authorized_attempt_id: 'extraction-1',
    created_at: time,
    finished_at: time,
    attempts: [],
  };
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
      '/capabilities': { development_mode: true, max_pages: 100, max_upload_bytes: 26214400 },
      '/conversations': { items: [], next_cursor: null },
      '/documents/document-1': {
        id: 'document-1',
        display_name: 'Controlled document',
        created_at: time,
        current_request_id: 'request-1',
        active_revision_id: 'revision-1',
      },
      '/ingestion-requests/request-1': status,
      '/revisions/revision-1/evidence': {
        revision_id: 'revision-1',
        pages: [],
        diagnostics: [],
        elements: [],
        next_after_order: null,
      },
      '/revisions/revision-1/summary': { state: 'not_scheduled' },
      '/revisions/revision-1/index': { state: 'not_started', index_id: null },
    };
    if (path === '/development/ingestion-requests/request-1') {
      const pending = false;
      responses[path] = {
        ...status,
        file_version_id: 'file-1',
        configuration: {},
        summary_configuration: null,
        summary: {
          id: 'summary-1',
          state: 'ready',
          created_at: time,
          started_at: time,
          finished_at: time,
          error_code: null,
          attempts: [
            {
              id: 'summary-attempt-1',
              attempt_no: 1,
              state: 'succeeded',
              started_at: time,
              finished_at: time,
              invoked_at: time,
              error_code: null,
              response_id: 'response-1',
              billing_state: 'estimated',
              reserved_usd: 0.17,
              cost_usd: 0.001575,
              usage: { prompt_tokens: 100, completion_tokens: 100, cost_basis: 'token_estimate' },
              failure_diagnostics: null,
            },
          ],
        },
        events: [],
        next_after_id: null,
        source: { sha256: 'a'.repeat(64), byte_size: 100, media_type: 'application/pdf' },
        indexing: {
          index_id: 'index-1',
          state: pending ? 'pending' : 'ready',
          chunk_count: 2,
          embedded_chunks: pending ? 1 : 2,
          model_id: 'openai/text-embedding-3-small',
          dimensions: 1536,
          error_code: null,
          created_at: time,
          started_at: time,
          finished_at: pending ? null : time,
          coverage: { diagnostics: [], pages_without_content: [] },
          exclusions: [],
          warnings: [],
          has_more: false,
          attempts: [
            {
              id: 'attempt-1',
              attempt_no: 1,
              batch_no: 1,
              state: 'succeeded',
              started_at: time,
              finished_at: time,
              invoked_at: time,
              error_code: null,
              billing_state: 'estimated',
              reserved_usd: 0.00000034,
              cost_usd: 0.000002,
              response_id: null,
              input_hash: null,
              chunk_ordinals: [],
              usage: { prompt_tokens: null },
              failure_diagnostics: null,
            },
          ],
        },
      };
    }
    expect(path in responses, `Unexpected API read: ${path}`).toBeTruthy();
    await route.fulfill({ json: responses[path] });
  });
  await page.goto('/documents/document-1');
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const summary = page.getByRole('region', { name: 'Summary execution' });
  await summary.getByText('Summary attempt 1', { exact: false }).click();
  await expect(summary.getByText('Estimated', { exact: true })).toBeVisible({ timeout: 2000 });
  await expect(summary.getByText('Estimated cost', { exact: true })).toBeVisible();
  await expect(summary).toContainText('$0.001575');
  const indexing = page.getByRole('region', { name: 'Indexing execution' });
  await indexing.getByText('Indexing attempt 1', { exact: false }).click();
  await expect(indexing.getByText('Estimated', { exact: true })).toBeVisible({ timeout: 2000 });
  await expect(indexing.getByText('Estimated cost', { exact: true })).toBeVisible();
  await expect(indexing).toContainText('$0.00000200');
});
