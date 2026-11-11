import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import { getInstructorWorkspace, getStudentWorkspace } from './api';

afterEach(() => vi.unstubAllGlobals());

it('parses assigned instructor offerings and roster rows', async () => {
  const fetcher = vi.fn().mockResolvedValue(
    Response.json({
      offerings: [
        {
          id: 'offering-1',
          label: 'CSE 301 · 01',
          course: 'Algorithms',
          program: 'Computer Science',
          term: '2026 Fall',
          roster: [
            { enrollment_id: 'enrollment-1', student_id: 7, name: 'Ada', status: 'enrolled' },
          ],
        },
      ],
    }),
  );
  vi.stubGlobal('fetch', fetcher);
  const result = await getInstructorWorkspace();
  expect(result.offerings[0].roster[0].name).toBe('Ada');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/workspaces/instructor/');
});

it('rejects malformed student course data and preserves cancellation', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ courses: [{ course: 'leak' }], outcomes: [] }));
  vi.stubGlobal('fetch', fetcher);
  await expect(getStudentWorkspace()).rejects.toBeInstanceOf(ApiError);
  const controller = new AbortController();
  fetcher.mockResolvedValue(Response.json({ courses: [], outcomes: [] }));
  await getStudentWorkspace(controller.signal);
  expect(fetcher.mock.calls[1][1].signal).toBeInstanceOf(AbortSignal);
});
