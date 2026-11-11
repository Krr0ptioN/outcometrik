import { expect, test } from '@playwright/test';

test('institution administrator reviews structure, creates accounts, manages access, and signs out', async ({
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
  await expect(
    page.getByRole('heading', { name: 'Computer Engineering' }),
  ).toBeVisible();
  await expect(page.getByText('CSE301 01', { exact: true })).toBeVisible();
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
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  const coordinatorDialog = page.getByRole('dialog');
  await coordinatorDialog.getByLabel('First name').fill('Casey');
  await coordinatorDialog.getByLabel('Last name').fill('Coordinator');
  await coordinatorDialog
    .getByLabel('Institution email')
    .fill('casey.coordinator@example.edu');
  await coordinatorDialog
    .getByLabel('Username', { exact: true })
    .fill('casey.coordinator');
  await coordinatorDialog
    .getByLabel('Initial password')
    .fill('Orbit!Saffron42Quartz');
  await coordinatorDialog
    .getByRole('combobox', { name: 'Assign to', exact: true })
    .selectOption({ label: 'Computer Engineering · program' });
  await coordinatorDialog
    .getByRole('combobox', { name: 'Initial role', exact: true })
    .selectOption('program-coordinator');
  await coordinatorDialog
    .getByRole('button', { name: 'Create account →', exact: true })
    .click();
  await expect(coordinatorDialog).toHaveCount(0);
  const search = page.getByRole('textbox', { name: 'Search people' });
  await search.fill('casey.coordinator');
  await page
    .getByRole('button', { name: 'Manage access for casey.coordinator' })
    .click();
  const coordinatorAccess = page.getByRole('dialog');
  await coordinatorAccess
    .getByRole('combobox', { name: 'Role', exact: true })
    .selectOption('instructor');
  await coordinatorAccess
    .getByRole('button', { name: 'Assign access →', exact: true })
    .click();
  await expect(coordinatorAccess).toHaveCount(0);
  await page
    .getByRole('button', { name: 'Manage access for casey.coordinator' })
    .click();
  const coordinatorGrant = page.getByRole('dialog');
  await coordinatorGrant
    .getByRole('combobox', { name: 'Access type', exact: true })
    .selectOption('capability');
  await coordinatorGrant
    .getByRole('combobox', { name: 'Capabilities', exact: true })
    .click();
  const capabilityOptions = page.getByRole('listbox', {
    name: 'Capabilities',
  });
  await capabilityOptions.getByRole('option', { name: 'grades.export' }).click();
  await capabilityOptions
    .getByRole('option', { name: 'outcomes.view' })
    .click();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await coordinatorGrant
    .getByRole('button', { name: 'Assign access →', exact: true })
    .click();
  await expect(coordinatorGrant).toHaveCount(0);
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
  await page.getByRole('combobox', { name: 'Capabilities', exact: true }).click();
  const releaseOptions = page.getByRole('listbox', { name: 'Capabilities' });
  await releaseOptions
    .getByRole('option', { name: 'grades.release' })
    .click();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
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
  ).toHaveCount(3);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username', { exact: true }).fill('ada.student');
  await page
    .getByLabel('Password', { exact: true })
    .fill('Learner-Access-2026!');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page).toHaveURL(/\/student$/);
  await expect(
    page.getByRole('heading', { name: 'Student dashboard' }),
  ).toBeVisible();
  await page.goto('/admin');
  await expect(
    page.getByRole('heading', { name: 'Administrator access required' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username', { exact: true }).fill('grace.instructor');
  await page
    .getByLabel('Password', { exact: true })
    .fill('Learner-Access-2026!');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page).toHaveURL(/\/instructor$/);
  await expect(
    page.getByRole('heading', { name: 'Instructor dashboard' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Username', { exact: true }).fill('casey.coordinator');
  await page
    .getByLabel('Password', { exact: true })
    .fill('Orbit!Saffron42Quartz');
  await page.getByRole('button', { name: 'Sign in to your workspace' }).click();
  await expect(page).toHaveURL(/\/coordinator$/);
  await expect(
    page.getByRole('heading', { name: 'Coordinator dashboard' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Academic roster' }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
