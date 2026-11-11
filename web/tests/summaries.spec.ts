import { expect, test } from '@playwright/test';

test('summary follows its own processing state and citations open the source', async ({ page }) => {
  let reads = 0;
  await page.route('**/api/revisions/*/summary', async (route) => {
    const response = await page.request.get(
      route
        .request()
        .url()
        .replace(/summary$/, 'evidence'),
    );
    const evidence = await response.json();
    const source = evidence.elements.find((element: { text: string }) =>
      element.text?.includes('125,000'),
    );
    const claim = {
      text: 'The report records revenue of 125,000.',
      source_ids: [source.element_id],
    };
    await route.fulfill({
      json: {
        revision_id: evidence.revision_id,
        state: ++reads === 1 ? 'running' : 'ready',
        overview: claim,
        points: [claim, claim, claim],
        citations: [{ source_id: source.element_id, pages: [source.locations[0].page_no] }],
        coverage: { scope: 'available_evidence', diagnostics: [], pages_without_content: [] },
        error: null,
      },
    });
  });
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Evidence available');
  const summary = page.getByRole('region', { name: 'Document summary' });
  await expect(summary).toContainText('Preparing summary', { timeout: 5000 });
  await expect(summary).toContainText('The report records revenue of 125,000.');
  await summary
    .getByRole('button', { name: 'View page 2 in original', exact: true })
    .first()
    .click();
  await expect(page.getByRole('link', { name: 'Open page 2' })).toHaveAttribute('href', /#page=2$/);
  await page.reload();
  await expect(summary).toContainText('The report records revenue of 125,000.');
});

test('an unavailable summary leaves recovered evidence and source access usable', async ({
  page,
}) => {
  await page.route('**/api/revisions/*/summary', (route) =>
    route.fulfill({
      json: {
        state: 'unavailable',
        overview: null,
        points: [],
        citations: [],
        coverage: { scope: 'available_evidence', diagnostics: [], pages_without_content: [] },
        error: {
          code: 'SUMMARY_INPUT_LIMIT',
          message: 'This document exceeds the current summary limit.',
        },
      },
    }),
  );
  await page.goto('/');
  await page
    .getByLabel('PDF document', { exact: true })
    .setInputFiles('../tests/fixtures/text.pdf');
  await page.getByRole('button', { name: 'Open document', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Document summary' })).toContainText(
    'exceeds the current summary limit',
  );
  await expect(page.getByRole('region', { name: 'Extracted evidence' })).toContainText('125,000');
  await page
    .getByRole('region', { name: 'Extracted evidence' })
    .getByRole('button', { name: 'View page 2 in original', exact: true })
    .first()
    .click();
  await expect(page.getByRole('link', { name: 'Open page 2' })).toHaveAttribute('href', /#page=2$/);
});
