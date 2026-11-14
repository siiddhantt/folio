import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('upload a PDF, inspect its evidence, and revisit the document', async ({ page }) => {
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]+$/);
  await expect(page.getByRole('status')).toContainText('Evidence available');
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
  await page.reload();
  await expect(page.getByRole('status')).toContainText('Evidence available');
  await expect(page.getByRole('link', { name: 'Download PDF' })).toBeVisible();
});

test('usable content stays visible alongside a page coverage warning', async ({ page }) => {
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/mixed.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Partial extraction');
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText(
    '30 September 2027',
  );
  const coverage = page.getByRole('note', { name: 'Extraction coverage' });
  await expect(coverage).toContainText('Content recovered from 2 of 3 pages');
  await coverage.getByText('Coverage details', { exact: true }).click();
  await expect(coverage.getByRole('button', { name: 'Inspect page 3' })).toBeVisible();
});

test('table cells retain their relationships and link to the original page', async ({ page }) => {
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/table.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Evidence available');
  const table = page.getByRole('table', { name: 'Extracted table from page 2' });
  await expect(table.getByRole('row').filter({ hasText: 'Operations' })).toContainText('19');
  await expect(table.getByRole('columnheader', { name: '2026', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View page 2 in original', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Open page 2' })).toHaveAttribute(
    'href',
    /inline=true#page=2$/,
  );
});

test('development view shows observed stages from this actual upload', async ({ page }) => {
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]+$/);
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  const inspection = page.getByRole('region', { name: 'Development inspection' });
  await expect(inspection.getByText('Upload accepted', { exact: true })).toBeVisible();
  await expect(inspection.getByText('Parsing completed', { exact: true })).toBeVisible();
  await expect(inspection.getByText('Evidence published', { exact: true })).toBeVisible();
  await inspection.getByText('Document details', { exact: true }).click();
  await expect(inspection.getByText('SHA-256', { exact: true })).toBeVisible();
  await expect(inspection).not.toContainText('models_path');
});

test('an upstream diagnostic without a code does not hide usable evidence', async ({ page }) => {
  await page.route('**/api/revisions/*/evidence?*', async (route) => {
    const response = await route.fetch();
    const evidence = await response.json();
    evidence.diagnostics.push({ page_no: 2, error_message: 'Page decoding reported a limitation' });
    evidence.diagnostics.push({ page_no: 2, error_message: 'Unrecognized timeout configuration' });
    await route.fulfill({ response, json: evidence });
  });
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  const coverage = page.getByRole('note', { name: 'Extraction coverage' });
  await expect(coverage).toBeVisible();
  await expect(coverage).not.toContainText('Processing reached its time limit');
  await coverage.getByText('Coverage details', { exact: true }).click();
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText(
    'Page decoding reported a limitation',
  );
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText(
    'Unrecognized timeout configuration',
  );
});

test('retrying an upload after a lost response reopens the accepted document', async ({
  page,
  request,
}) => {
  let acceptedId = '';
  await page.route('**/api/documents', async (route) => {
    if (acceptedId) return route.continue();
    const response = await request.post(route.request().url(), {
      headers: { 'Idempotency-Key': route.request().headers()['idempotency-key'] },
      multipart: {
        file: {
          name: 'text.pdf',
          mimeType: 'application/pdf',
          buffer: await readFile('../tests/fixtures/text.pdf'),
        },
      },
    });
    expect(response.status()).toBe(202);
    acceptedId = (await response.json()).document_id;
    await route.abort('connectionfailed');
  });
  await page.goto('/upload');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Connection interrupted');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/documents/${acceptedId}$`));
  await expect(page.getByRole('status')).toContainText('Evidence available');
});

test('an unsupported encrypted PDF has a useful failure and its original remains accessible', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/upload');
  await page.getByRole('button', { name: 'Switch to dark mode' }).click();
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/encrypted.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Could not extract this PDF');
  await expect(page.getByRole('alert')).toContainText('Your original remains available');
  await expect(page.getByRole('link', { name: 'Download PDF' })).toBeVisible();
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  await page
    .getByRole('region', { name: 'Development inspection' })
    .locator('summary')
    .filter({ hasText: 'Extraction attempt 1' })
    .click();
  await expect(page.getByRole('region', { name: 'Development inspection' })).toContainText(
    'ENCRYPTED_PDF',
  );
  const width = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  expect(width.page).toBeLessThanOrEqual(width.viewport);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Switch to light mode' })).toBeVisible();
});
