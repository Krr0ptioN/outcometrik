import { expect, test } from '@playwright/test';

test('instructor creates and edits syllabus configuration', async ({
  page,
  context,
}) => {
  await context.addCookies([
    { name: 'csrftoken', value: 'token', url: 'http://127.0.0.1:3000' },
  ]);
  await page.route('**/api/auth/session/', (route) =>
    route.fulfill({
      json: {
        user: {
          id: 1,
          username: 'teacher',
          email: 'teacher@example.com',
          first_name: 'T',
          last_name: 'E',
          is_active: true,
        },
        scopes: [],
        roles: [
          {
            role: 'instructor',
            scope: {
              id: 'o1',
              kind: 'offering',
              label: 'Course',
              parent_id: null,
            },
          },
        ],
      },
    }),
  );
  await page.route('**/api/v1/workspaces/instructor/', (route) =>
    route.fulfill({
      json: {
        offerings: [
          {
            id: 'o1',
            label: 'CSE301',
            course: 'Algorithms',
            program: 'CS',
            term: 'Fall',
            roster: [],
          },
        ],
      },
    }),
  );
  const syllabus = {
    id: 's1',
    offering: 'o1',
    version: 1,
    status: 'draft',
    approved_at: null,
    po_set_version: 1,
    learning_outcomes: [] as object[],
    assessments: [] as object[],
  };
  let created = false;
  await page.route('**/api/v1/syllabi/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === 'GET')
      return route.fulfill({
        json: { results: created ? [syllabus] : [], next: null },
      });
    if (url.pathname === '/api/v1/syllabi/') created = true;
    else if (url.pathname.endsWith('/learning-outcomes/'))
      syllabus.learning_outcomes.push({ id: 'l1', ...request.postDataJSON() });
    else if (url.pathname.endsWith('/assessments/'))
      syllabus.assessments.push({ id: 'a1', ...request.postDataJSON() });
    return route.fulfill({ json: syllabus });
  });
  await page.goto('/instructor');
  await expect(page.getByText('No syllabus versions yet.')).toBeVisible();
  await page.getByRole('button', { name: 'Create draft' }).click();
  const outcome = page
    .locator('form')
    .filter({ hasText: 'Add learning outcome' });
  await outcome.getByLabel('Code').fill('LO1');
  await outcome.getByLabel('Description').fill('Explain algorithms');
  await outcome.getByLabel('Order').fill('1');
  await outcome.getByRole('button', { name: 'Add outcome' }).click();
  await expect(page.getByRole('heading', { name: 'Edit LO1' })).toBeVisible();
  const assessment = page.locator('form').filter({ hasText: 'Add assessment' });
  await assessment.getByLabel('Code').fill('EX1');
  await assessment.getByLabel('Order').fill('1');
  await assessment.getByLabel('Maximum points').fill('100');
  await assessment.getByRole('button', { name: 'Add assessment' }).click();
  await expect(page.getByRole('heading', { name: 'Edit EX1' })).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Approve syllabus' }),
  ).toHaveCount(0);
});
