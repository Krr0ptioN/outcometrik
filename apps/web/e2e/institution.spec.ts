import { expect, test } from '@playwright/test';

test('institution administrator creates structure and accounts, manages access, and signs out', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/admin');
  await expect(
    page.getByRole('heading', { name: 'Sign in to continue.' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Go to sign in' }).click();
  await page.getByLabel('Username', { exact: true }).fill('institution.admin');
  await page
    .getByLabel('Password', { exact: true })
    .fill('E2e-Admin-Password-2026!');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(
    page.getByRole('heading', { name: 'Institution overview.' }),
  ).toBeVisible();
  await expect(page.getByRole('complementary')).toContainText(
    'Northbridge University',
  );
  await page
    .getByRole('button', { name: 'Programs & offerings', exact: true })
    .click();
  await page.getByRole('button', { name: 'Add program or offering' }).click();
  await page
    .getByRole('dialog')
    .getByLabel('Name', { exact: true })
    .fill('Computer Engineering');
  await page
    .getByRole('button', { name: 'Add program →', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: 'Computer Engineering' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Add program or offering' }).click();
  await page
    .getByRole('combobox', { name: 'Type', exact: true })
    .selectOption('offering');
  await page
    .getByRole('dialog')
    .getByLabel('Name', { exact: true })
    .fill('CSE 301 · Fall 2026');
  await page
    .getByRole('button', { name: 'Add course offering →', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByText('CSE 301 · Fall 2026', { exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'People & access', exact: true })
    .click();
  for (const person of [
    { username: 'ada.student', role: 'student', name: 'Ada' },
    { username: 'grace.instructor', role: 'instructor', name: 'Grace' },
  ]) {
    await page
      .getByRole('button', { name: 'Create account', exact: true })
      .click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('First name').fill(person.name);
    await dialog.getByLabel('Last name').fill('Test');
    await dialog
      .getByLabel('Institution email')
      .fill(`${person.username}@example.edu`);
    await dialog.getByLabel('Username', { exact: true }).fill(person.username);
    await dialog.getByLabel('Initial password').fill('Learner-Access-2026!');
    await dialog
      .getByRole('combobox', { name: 'Initial role', exact: true })
      .selectOption(person.role);
    await dialog
      .getByRole('button', { name: 'Create account →', exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole('button', {
        name: `Manage access for ${person.username}`,
      }),
    ).toBeVisible();
  }
  const search = page.getByRole('textbox', { name: 'Search people' });
  await search.fill('ada.student');
  await expect(
    page.getByRole('button', { name: 'Manage access for grace.instructor' }),
  ).toHaveCount(0);
  await expect(search).toBeFocused();
  await search.fill('');
  await expect(
    page.getByRole('button', { name: 'Manage access for grace.instructor' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Manage access for ada.student' })
    .click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Revoke student/ })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  // Account membership persists after its last role is revoked, so access can be restored.
  await page
    .getByRole('button', { name: 'Manage access for ada.student' })
    .click();
  await page
    .getByRole('dialog')
    .getByRole('combobox', { name: 'Role', exact: true })
    .selectOption('student');
  await page
    .getByRole('button', { name: 'Assign access →', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page
    .getByRole('button', { name: 'Manage access for grace.instructor' })
    .click();
  await page
    .getByRole('combobox', { name: 'Access type', exact: true })
    .selectOption('capability');
  await page
    .getByRole('combobox', { name: 'Capability', exact: true })
    .selectOption('grades.release');
  await page
    .getByRole('button', { name: 'Assign access →', exact: true })
    .click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByText('1 direct grant', { exact: true })).toBeVisible();
  await page.screenshot({
    path: '/tmp/outcometrik-institution-dashboard.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Activity log', exact: true }).click();
  await expect(
    page.getByText('capability granted', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username', { exact: true }).fill('ada.student');
  await page
    .getByLabel('Password', { exact: true })
    .fill('Learner-Access-2026!');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto('/admin');
  await expect(
    page.getByRole('heading', { name: 'Administrator access required' }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
