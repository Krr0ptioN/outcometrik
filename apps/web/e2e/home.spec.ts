import { expect, test } from '@playwright/test';

test('shows available API and keyboard navigation', async ({ page }) => {
  await page.route('**/api/health/status', (route) =>
    route.fulfill({ json: { status: 'ok' } }),
  );
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Outcometrik' })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('API available');
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('link', { name: 'Skip to main content' }),
  ).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
});
for (const status of [401, 403, 400, 409, 503]) {
  test(`handles HTTP ${status} and recovers on retry`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/api/health/status', (route) =>
      route.fulfill({ status, json: { detail: 'error' } }),
    );
    await page.goto('/');
    await expect(page.getByRole('status')).not.toHaveText(
      'Checking API availability…',
    );
    await expect(
      page.getByRole('button', { name: 'Check again' }),
    ).toBeEnabled();
    await page.route('**/api/health/status', (route) =>
      route.fulfill({ json: { status: 'ok' } }),
    );
    await page.getByRole('button', { name: 'Check again' }).click();
    await expect(page.getByRole('status')).toHaveText('API available');
    expect(errors).toEqual([]);
  });
}
test('shows loading, empty workspace, and network failure', async ({
  page,
}) => {
  await page.route('**/api/health/status', () => {});
  await page.goto('/');
  await expect(page.getByRole('status')).toHaveText(
    'Checking API availability…',
  );
  await expect(page.getByRole('button', { name: 'Checking…' })).toBeDisabled();
  await expect(page.getByText(/No courses to display yet/)).toBeVisible();
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/health/status', (route) => route.abort());
  await page.reload();
  await expect(page.getByRole('status')).toHaveText(
    'API unavailable. Please try again.',
  );
});
