import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
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
});

test('clicking the sidebar divider collapses it and clicking the left edge restores it', async ({
  page,
}) => {
  await page.goto('/');
  const sidebar = page.getByRole('complementary', { name: 'Conversation history' });
  await expect(sidebar).toBeVisible();
  const box = (await sidebar.boundingBox())!;
  await page.mouse.click(box.x + box.width - 1, box.y + box.height / 3);
  await expect(sidebar).toBeHidden({ timeout: 2500 });
  await page.mouse.click(2, box.y + (2 * box.height) / 3);
  await expect(sidebar).toBeVisible();
  await expect(page.getByRole('banner').getByRole('button', { name: /sidebar/i })).toHaveCount(0);
});

test('desktop sidebar can be collapsed with the keyboard and restored after reload', async ({
  page,
}) => {
  await page.goto('/');
  const sidebar = page.getByRole('complementary', { name: 'Conversation history' });
  const collapse = page.getByRole('button', { name: 'Collapse sidebar' });
  const expand = page.getByRole('button', { name: 'Expand sidebar' });
  await expect(collapse).toBeVisible({ timeout: 3000 });
  const expandedWidth = (await page.getByRole('main').boundingBox())!.width;
  await collapse.focus();
  await page.keyboard.press('Enter');
  await expect(expand).toBeFocused();
  await expect(expand).toHaveAttribute('aria-expanded', 'false');
  await expect(sidebar).toBeHidden();
  expect((await page.getByRole('main').boundingBox())!.width).toBeGreaterThan(expandedWidth);
  await page.reload();
  await expect(expand).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const drawerButton = page.getByRole('button', { name: 'Open conversation history' });
  await expect(
    page.getByRole('banner').getByRole('button', { name: 'Open conversation history' }),
  ).toHaveCount(0);
  await drawerButton.click();
  await expect(page.getByRole('dialog', { name: 'Conversation history' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(drawerButton).toBeFocused();
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(expand).toHaveAttribute('aria-expanded', 'false');
  await expand.click();
  await expect(sidebar).toBeVisible();
});

test('Back returns to the previous Folio screen and direct links fall back to home', async ({
  page,
}) => {
  test.setTimeout(30000);
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
