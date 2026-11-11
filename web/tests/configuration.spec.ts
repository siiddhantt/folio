import { expect, test } from '@playwright/test';

test('console saves limits for a real upload and rejects a stale form', async ({
  page,
  request,
}) => {
  const endpoint = '/api/development/settings';
  const originalResponse = await request.get(endpoint);
  expect(originalResponse.ok()).toBeTruthy();
  const original = await originalResponse.json();
  let ownedRevision: number | null = null;
  try {
    await page.goto('/');
    await page.getByRole('link', { name: 'Development settings' }).click();
    await expect(page.getByRole('heading', { name: 'Development' })).toBeVisible();
    await page.getByLabel('Maximum pages', { exact: true }).fill('701');
    await page.getByLabel('Maximum upload bytes', { exact: true }).fill('2097152');
    await page.getByLabel('Automatic summaries', { exact: true }).uncheck();
    const savedResponse = page.waitForResponse(
      (response) => response.url().endsWith(endpoint) && response.request().method() === 'PUT',
    );
    await page.getByRole('button', { name: 'Save settings', exact: true }).click();
    const saved = await (await savedResponse).json();
    ownedRevision = saved.revision;
    await expect(page.getByRole('status')).toHaveText('Settings saved.');
    await page.reload();
    await expect(page.getByLabel('Maximum pages', { exact: true })).toHaveValue('701');

    const concurrent = await request.put(endpoint, {
      headers: { 'X-Folio-Development': '1' },
      data: { revision: ownedRevision, values: { ...saved.values, max_pages: 702 } },
    });
    expect(concurrent.ok()).toBeTruthy();
    ownedRevision = (await concurrent.json()).revision;
    await page.getByLabel('Maximum pages', { exact: true }).fill('703');
    await page.getByRole('button', { name: 'Save settings', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText('Settings changed in another tab');
    await page.getByRole('button', { name: 'Reload settings', exact: true }).click();
    await expect(page.getByLabel('Maximum pages', { exact: true })).toHaveValue('702');

    await page.getByRole('link', { name: 'Folio home' }).click();
    await expect(page.getByText(/702 pages/)).toBeVisible();
    await page
      .getByLabel('PDF document', { exact: true })
      .setInputFiles('../tests/fixtures/text.pdf');
    await page.getByRole('button', { name: 'Open document', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Evidence available');
    await page.getByRole('button', { name: 'Activity', exact: true }).click();
    const inspection = page.getByRole('region', { name: 'Development inspection' });
    await inspection.getByText('Configuration for this request', { exact: true }).click();
    await expect(
      inspection.locator('.configuration-pair').filter({ hasText: 'settings revision' }),
    ).toContainText(String(ownedRevision));
    await page.getByRole('button', { name: 'Close activity' }).click();
    await expect(page.getByRole('region', { name: 'Document summary' })).toContainText('disabled');
  } finally {
    if (ownedRevision !== null) {
      const current = await (await request.get(endpoint)).json();
      expect(current.revision, 'Do not overwrite an unrelated concurrent edit').toBe(ownedRevision);
      const restored = await request.put(endpoint, {
        headers: { 'X-Folio-Development': '1' },
        data: { revision: ownedRevision, values: original.values },
      });
      expect(restored.ok()).toBeTruthy();
    }
  }
});

test('focus refresh revalidates a selected file without discarding it', async ({
  page,
  request,
}) => {
  const endpoint = '/api/development/settings';
  const original = await (await request.get(endpoint)).json();
  let ownedRevision = original.revision;
  try {
    await page.goto('/');
    await page
      .getByLabel('PDF document', { exact: true })
      .setInputFiles('../tests/fixtures/text.pdf');
    const smaller = await request.put(endpoint, {
      headers: { 'X-Folio-Development': '1' },
      data: { revision: ownedRevision, values: { ...original.values, max_upload_bytes: 100 } },
    });
    expect(smaller.ok()).toBeTruthy();
    ownedRevision = (await smaller.json()).revision;
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.getByRole('button', { name: 'Open document', exact: true })).toBeDisabled();
    await expect(page.getByRole('alert')).toContainText('Choose a PDF smaller than 1 KB.', {
      timeout: 5000,
    });
    const larger = await request.put(endpoint, {
      headers: { 'X-Folio-Development': '1' },
      data: { revision: ownedRevision, values: original.values },
    });
    expect(larger.ok()).toBeTruthy();
    ownedRevision = (await larger.json()).revision;
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.getByRole('button', { name: 'Open document', exact: true })).toBeEnabled();
    await expect(page.getByRole('alert')).not.toBeVisible();
    await expect(page.getByText('text.pdf', { exact: true })).toBeVisible();
  } finally {
    const current = await (await request.get(endpoint)).json();
    expect(current.revision, 'Do not overwrite an unrelated concurrent edit').toBe(ownedRevision);
    const restored = await request.put(endpoint, {
      headers: { 'X-Folio-Development': '1' },
      data: { revision: ownedRevision, values: original.values },
    });
    expect(restored.ok()).toBeTruthy();
  }
});
