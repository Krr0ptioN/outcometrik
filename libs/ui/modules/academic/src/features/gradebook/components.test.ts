import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';

const mockState = vi.hoisted(() => ({
  session: {
    isPending: false,
    data: { user: { id: 1 }, roles: [{ role: 'instructor' }] },
  },
  workspace: {} as Record<string, unknown>,
  board: {} as Record<string, unknown>,
}));

vi.mock('@outcometrik/access', () => ({
  errorMessage: () => 'The request failed',
  SessionMenu: () => null,
  useSession: () => mockState.session,
}));
vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) =>
    queryKey[1] === 'instructor' ? mockState.workspace : mockState.board,
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
  }),
}));

import {
  computeNextGridCell,
  InstructorGradebook,
  isDraftDirty,
  paginateRoster,
  sortRosterDeterministically,
  validateGradeDraft,
} from './components';

beforeEach(() => {
  mockState.workspace = {
    data: { offerings: [] },
    isPending: false,
    isError: false,
  };
  mockState.board = { isPending: false, isError: false };
});

it('announces loading and missing instructor offerings', () => {
  mockState.workspace = { isPending: true };
  expect(renderToStaticMarkup(createElement(InstructorGradebook))).toContain(
    'Loading gradebook',
  );
  mockState.workspace = {
    data: { offerings: [] },
    isPending: false,
    isError: false,
  };
  expect(renderToStaticMarkup(createElement(InstructorGradebook))).toContain(
    'No offerings are assigned',
  );
});

it('announces board errors and empty assessment state', () => {
  mockState.workspace = {
    data: {
      offerings: [
        {
          id: 'o',
          label: 'CSE',
          course: 'Algorithms',
          term: 'Fall',
          roster: [],
        },
      ],
    },
    isPending: false,
    isError: false,
  };
  mockState.board = {
    isPending: false,
    isError: true,
    error: new Error('offline'),
  };
  let markup = renderToStaticMarkup(createElement(InstructorGradebook));
  expect(markup).toContain('role="alert"');
  expect(markup).toContain('The request failed');
  mockState.board = {
    isPending: false,
    isError: false,
    data: { assessments: [], batches: [], grades: [] },
  };
  markup = renderToStaticMarkup(createElement(InstructorGradebook));
  expect(markup).toContain('No approved assessments are available');
});

it('uses the saved grade limit and identifies each student input', () => {
  mockState.workspace = {
    data: {
      offerings: [
        {
          id: 'o',
          label: 'CSE',
          course: 'Algorithms',
          term: 'Fall',
          roster: [{ enrollment_id: 'e', name: 'Ada', status: 'enrolled' }],
        },
      ],
    },
    isPending: false,
    isError: false,
  };
  mockState.board = {
    isPending: false,
    isError: false,
    data: {
      assessments: [{ id: 'a', title: 'Exam', points_possible: '20' }],
      batches: [{ id: 'b', name: 'Final', released_at: null }],
      grades: [
        {
          id: 'g',
          enrollment: 'e',
          assessment: 'a',
          batch: 'b',
          batch_name: 'Final',
          state: 'scored',
          points_earned: '8',
          points_possible: '10',
          version: 1,
        },
      ],
    },
  };
  const markup = renderToStaticMarkup(createElement(InstructorGradebook));
  expect(markup).toContain('Grade state for Ada');
  expect(markup).toContain('Points earned for Ada (out of 10)');
  expect(markup).toContain('max="10"');
});

it('renders multi-assessment student×assessment matrix with distinct badges for Recorded zero, Missing, Exempt, Withdrawn, Released, and Unreleased', () => {
  mockState.workspace = {
    data: {
      offerings: [
        {
          id: 'off-1',
          label: 'CSE 301 · 01',
          course: 'Algorithms',
          term: '2026 Fall',
          input_revision: 4,
          roster: [
            { enrollment_id: 'e-1', name: 'Ada Lovelace', status: 'enrolled' },
            { enrollment_id: 'e-2', name: 'Alan Turing', status: 'enrolled' },
            {
              enrollment_id: 'e-3',
              name: 'Grace Hopper',
              status: 'withdrawn',
            },
          ],
        },
      ],
    },
    isPending: false,
    isError: false,
  };
  mockState.board = {
    isPending: false,
    isError: false,
    data: {
      assessments: [
        { id: 'a-mid', title: 'Midterm Exam', points_possible: '100.00' },
        { id: 'a-proj', title: 'Course Project', points_possible: '50.00' },
      ],
      batches: [
        { id: 'b-draft', name: 'Draft Batch', released_at: null },
        {
          id: 'b-rel',
          name: 'Released Batch',
          released_at: '2026-10-01T12:00:00Z',
        },
      ],
      grades: [
        {
          id: 'g-zero',
          enrollment: 'e-1',
          assessment: 'a-mid',
          batch: 'b-draft',
          batch_name: 'Draft Batch',
          state: 'scored',
          points_earned: '0.00',
          points_possible: '100.00',
          version: 1,
        },
        {
          id: 'g-missing',
          enrollment: 'e-1',
          assessment: 'a-proj',
          batch: 'b-draft',
          batch_name: 'Draft Batch',
          state: 'missing',
          points_earned: null,
          points_possible: '50.00',
          version: 1,
        },
        {
          id: 'g-exempt',
          enrollment: 'e-2',
          assessment: 'a-mid',
          batch: 'b-rel',
          batch_name: 'Released Batch',
          state: 'exempt',
          points_earned: null,
          points_possible: '100.00',
          version: 2,
        },
      ],
    },
  };

  const markup = renderToStaticMarkup(createElement(InstructorGradebook));
  expect(markup).toContain('Roster × assessment gradebook matrix');
  expect(markup).toContain('Midterm Exam');
  expect(markup).toContain('Course Project');
  expect(markup).toContain('Recorded zero');
  expect(markup).toContain('0.00 / 100.00');
  expect(markup).toContain('Missing');
  expect(markup).toContain('Exempt');
  expect(markup).toContain('Withdrawn');
  expect(markup).toContain('Unreleased (draft)');
  expect(markup).toContain('Released');
  expect(markup).toContain('Correction reason for Alan Turing');
  expect(markup).toContain('Save all changes');
  expect(markup).toContain('Page 1 of 1');
});

it('validates cell drafts against max points, numeric rules, and post-release reason requirements', () => {
  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '0', reason: '' },
      scoreLimit: '25.00',
      reasonRequired: false,
    }),
  ).toEqual({ valid: true, error: null });

  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '25.01', reason: '' },
      scoreLimit: '25.00',
      reasonRequired: false,
    }),
  ).toEqual({
    valid: false,
    error: 'Points earned must be between 0 and 25.00.',
  });

  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '-1', reason: '' },
      scoreLimit: '25.00',
      reasonRequired: false,
    }),
  ).toEqual({
    valid: false,
    error: 'Points earned must be between 0 and 25.00.',
  });

  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '   ', reason: '' },
      scoreLimit: '25.00',
      reasonRequired: false,
    }),
  ).toEqual({
    valid: false,
    error: 'Points earned are required when scored (0 to 25.00).',
  });

  expect(
    validateGradeDraft({
      draft: { state: 'missing', points: '0', reason: '' },
      scoreLimit: '25.00',
      reasonRequired: false,
    }),
  ).toEqual({
    valid: false,
    error: 'Points earned must be empty unless the grade state is Scored.',
  });

  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '20', reason: '  ' },
      scoreLimit: '25.00',
      reasonRequired: true,
    }),
  ).toEqual({
    valid: false,
    error: 'A reason is required for grades in a released batch.',
  });

  expect(
    validateGradeDraft({
      draft: { state: 'scored', points: '20', reason: 'Regrade approved' },
      scoreLimit: '25.00',
      reasonRequired: true,
    }),
  ).toEqual({ valid: true, error: null });
});

it('detects dirty drafts, sorts and paginates rosters deterministically, and computes keyboard cell navigation', () => {
  expect(
    isDraftDirty({ state: 'scored', points: '', reason: '' }, undefined),
  ).toBe(false);
  expect(
    isDraftDirty({ state: 'scored', points: '0', reason: '' }, undefined),
  ).toBe(true);
  expect(
    isDraftDirty({ state: 'missing', points: '', reason: '' }, undefined),
  ).toBe(true);

  const sorted = sortRosterDeterministically([
    { enrollment_id: 'e-2', name: 'Zoe', status: 'enrolled' },
    { enrollment_id: 'e-3', name: 'Ada', status: 'enrolled' },
    { enrollment_id: 'e-1', name: 'Ada', status: 'enrolled' },
  ]);
  expect(sorted.map((s) => s.enrollment_id)).toEqual(['e-1', 'e-3', 'e-2']);

  const page1 = paginateRoster(sorted, 1, 2);
  expect(page1.items.map((s) => s.enrollment_id)).toEqual(['e-1', 'e-3']);
  expect(page1.totalPages).toBe(2);

  const page2 = paginateRoster(sorted, 2, 2);
  expect(page2.items.map((s) => s.enrollment_id)).toEqual(['e-2']);

  expect(computeNextGridCell(0, 0, 3, 2, 'ArrowDown')).toEqual({
    rowIndex: 1,
    colIndex: 0,
  });
  expect(computeNextGridCell(0, 0, 3, 2, 'ArrowUp')).toEqual({
    rowIndex: 0,
    colIndex: 0,
  });
  expect(computeNextGridCell(1, 0, 3, 2, 'ArrowRight')).toEqual({
    rowIndex: 1,
    colIndex: 1,
  });
  expect(computeNextGridCell(1, 1, 3, 2, 'ArrowLeft')).toEqual({
    rowIndex: 1,
    colIndex: 0,
  });
  expect(computeNextGridCell(1, 1, 3, 2, 'Enter')).toBeNull();
});
