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

import { InstructorGradebook } from './components';

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
