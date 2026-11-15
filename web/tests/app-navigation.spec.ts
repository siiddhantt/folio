import { expect, test } from '@playwright/test';

test('Back returns to the previous Folio screen and direct links fall back to home', async ({
  page,
}) => {
  test.setTimeout(30000);
  await page.route('**/api/**', async (route) => {
    expect(route.request().method()).toBe('GET');
    const path = new URL(route.request().url()).pathname.replace('/api', '');
    if (path === '/capabilities') {
      await route.fulfill({
        json: { development_mode: true, max_pages: 100, max_upload_bytes: 26214400 },
      });
    } else if (path === '/development/settings') {
      await route.fulfill({ status: 503, json: { detail: 'Settings temporarily unavailable.' } });
    } else {
      expect(path).toBe('/conversations');
      await route.fulfill({ json: { items: [], next_cursor: null } });
    }
  });

  await page.goto('/');
  await page.getByRole('main').getByRole('link', { name: 'Upload', exact: true }).click();
  await page.getByRole('link', { name: 'Development settings' }).click();
  await expect(page.getByRole('heading', { name: 'Development', exact: true })).toBeVisible();
  const back = page.getByRole('main').getByRole('button', { name: 'Go back', exact: true });
  await expect(back).toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('banner').getByRole('button', { name: 'Go back' })).toHaveCount(0);
  await back.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByRole('main')).toBeFocused();
  await page.reload();
  await back.click();
  await expect(page).toHaveURL(/\/$/);
  await expect(back).toHaveCount(0);

  await page.goto('about:blank');
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto('/development/settings');
  await expect(back).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await back.click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('main')).toBeFocused();
});
