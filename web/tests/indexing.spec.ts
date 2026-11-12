import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('Activity follows indexing after extraction and preserves unknown charges', async ({
  page,
}) => {
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
  let reads = 0;
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
      const pending = ++reads === 1;
      responses[path] = {
        ...status,
        file_version_id: 'file-1',
        configuration: {},
        summary_configuration: null,
        summary: null,
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
              state: 'failed',
              started_at: time,
              finished_at: time,
              invoked_at: time,
              error_code: 'EMBEDDING_TIMEOUT',
              billing_state: 'unknown',
              reserved_usd: 0.00000034,
              cost_usd: null,
              response_id: null,
              input_hash: null,
              chunk_ordinals: [],
              usage: { prompt_tokens: null },
              failure_diagnostics: {
                error_type: 'TimeoutError',
                error_frames: [
                  { module: 'folio.indexing.processing', function: 'process_index', line: 42 },
                ],
              },
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
  const indexing = page.getByRole('region', { name: 'Indexing execution' });
  await expect(indexing).toContainText('1 of 2 chunks embedded', { timeout: 5000 });
  await expect(indexing).toContainText('2 of 2 chunks embedded', { timeout: 10000 });
  await expect(indexing).toContainText('ready');
  await indexing.getByText('Indexing attempt 1', { exact: false }).click();
  await expect(indexing).toContainText('Unknown');
  await expect(indexing).toContainText('$0.00000034', { timeout: 5000 });
  await expect(indexing).toContainText('Not reported');
  await expect(indexing).toContainText('TimeoutError');
  await expect(indexing).toContainText('folio.indexing.processing.process_index:42');
  await expect(indexing.getByText('$0.000000', { exact: true })).toHaveCount(0);
});
