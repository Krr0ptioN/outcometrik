import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockState = vi.hoisted(() => ({
  workspace: {
    data: {
      programs: [
        { id: 'prog-1', label: 'CSE-BS · Computer Engineering', department: 'CSE' },
      ],
      offerings: [
        {
          id: 'off-1',
          program_id: 'prog-1',
          label: 'CSE 311-01',
          course: 'Database Systems',
          term: '2025 Fall',
          enrolled: 40,
        },
      ],
      students: [],
    } as unknown,
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  syllabi: {
    data: [
      {
        id: 'syl-2',
        offering: 'off-1',
        version: 2,
        status: 'draft',
        approved_at: null,
        po_set_version: 2,
        learning_outcomes: [
          { id: 'lo-1', code: 'LO1', description: 'Design relational schemas', order: 1 },
        ],
        assessments: [
          {
            id: 'a-1',
            code: 'MID',
            kind: 'exam',
            order: 1,
            is_required: true,
            is_active: true,
            max_points: '100.00',
          },
        ],
        po_contributions: [
          {
            id: 'c-1',
            program_outcome: 'po-1',
            program_outcome_code: 'PO1',
            weight: 4,
          },
        ],
        assessment_lo_mappings: [
          { assessment: 'a-1', learning_outcome: 'lo-1', weight: '0.60', is_active: true },
        ],
        lo_po_mappings: [
          { learning_outcome: 'lo-1', program_outcome: 'po-1', weight: 4, is_active: true },
        ],
      },
    ] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  poSets: {
    data: [
      {
        id: 'set-2',
        version: 2,
        active: true,
        activated_at: '2026-01-10T00:00:00Z',
        effective_date: '2026-01-10',
        source_reference: 'MÜDEK 2026',
      },
      {
        id: 'set-1',
        version: 1,
        active: false,
        activated_at: '2024-09-01T00:00:00Z',
        effective_date: '2024-09-01',
        source_reference: 'MÜDEK 2024',
      },
    ] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  outcomes: {
    data: [
      {
        id: 'po-1',
        code: 'PO1',
        label: 'Engineering Fundamentals',
        description: 'Apply mathematics, science, and engineering knowledge.',
        source_reference: 'MÜDEK 2026',
        order: 1,
      },
    ] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  validation: {
    data: {
      syllabus_id: 'syl-2',
      mapping_revision: 1,
      is_valid_for_approval: true,
      lo_statuses: [
        {
          learning_outcome_id: 'lo-1',
          code: 'LO1',
          status: 'MAPPED',
          total_assessment_weight: '0.60',
          mapped_po_count: 1,
        },
      ],
      po_statuses: [
        {
          program_outcome_id: 'po-1',
          code: 'PO1',
          status: 'ASSESSED',
          total_lo_weight: 4,
        },
      ],
      unmapped_learning_outcomes: [],
      orphaned_learning_outcomes: [],
      unreachable_program_outcomes: [],
      errors: [],
    } as unknown,
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  programCourses: {
    data: [
      { id: 'pc-1', program: 'prog-1', course: 'course-1' },
      { id: 'pc-2', program: 'prog-2', course: 'course-1' },
    ] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  courses: {
    data: [{ id: 'course-1', code: 'CSE 311', title: 'Database Systems' }] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
  offerings: {
    data: [{ id: 'off-1', course: 'course-1', program: 'prog-1' }] as unknown[],
    isPending: false,
    isError: false,
    error: null as unknown,
  },
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  }),
  useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
    const key = queryKey[1];
    if (key === 'coordinator') return mockState.workspace;
    if (key === 'syllabi') return mockState.syllabi;
    if (key === 'po-sets') return mockState.poSets;
    if (key === 'po-set-outcomes') return mockState.outcomes;
    if (key === 'syllabus-validation') return mockState.validation;
    if (key === 'program-courses') return mockState.programCourses;
    if (key === 'courses') return mockState.courses;
    if (key === 'offerings') return mockState.offerings;
    return { data: undefined, isPending: false, isError: false, error: null };
  },
}));

import {
  CoordinatorApprovalsPanel,
  validateCoursePoRelevanceWeight,
} from './coordinator-approvals';
import {
  CoordinatorPOSetManager,
  resolvePoSetLifecycle,
} from './coordinator-po-sets';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('validateCoursePoRelevanceWeight', () => {
  it('accepts integers 1–5 and blank string to clear', () => {
    expect(validateCoursePoRelevanceWeight('')).toEqual({ ok: true, value: null });
    expect(validateCoursePoRelevanceWeight('  ')).toEqual({ ok: true, value: null });
    for (let n = 1; n <= 5; n += 1) {
      expect(validateCoursePoRelevanceWeight(String(n))).toEqual({
        ok: true,
        value: n,
      });
    }
  });

  it('rejects 0, 6, decimals, negatives, and non-numeric strings', () => {
    for (const invalid of ['0', '6', '2.5', '-1', 'abc', '10']) {
      const result = validateCoursePoRelevanceWeight(invalid);
      expect(result.ok).toBe(false);
    }
  });
});

describe('resolvePoSetLifecycle', () => {
  it('distinguishes active, archived, and draft PO sets', () => {
    expect(
      resolvePoSetLifecycle({ active: true, activated_at: '2026-01-10T00:00:00Z' }),
    ).toBe('active');
    expect(
      resolvePoSetLifecycle({ active: false, activated_at: '2024-09-01T00:00:00Z' }),
    ).toBe('archived');
    expect(resolvePoSetLifecycle({ active: false, activated_at: null })).toBe(
      'draft',
    );
  });
});

describe('CoordinatorApprovalsPanel', () => {
  it('renders pending draft syllabus preview, A×LO and LO×PO matrices, Approve & lock CTA, and M:N Course→PO weights', () => {
    const markup = renderToStaticMarkup(createElement(CoordinatorApprovalsPanel));

    expect(markup).toContain('Syllabus approval queue');
    expect(markup).toContain('CSE 311-01');
    expect(markup).toContain('Ready for approval');
    expect(markup).toContain('Approve &amp; lock');
    expect(markup).toContain('Assessment × Learning Outcome (A×LO)');
    expect(markup).toContain('Learning Outcome × Program Outcome (LO×PO)');
    expect(markup).toContain('Course → PO 1–5 relevance weights matrix');
    expect(markup).toContain('2 programs');
  });
});

describe('CoordinatorPOSetManager', () => {
  it('renders active v2 and archived v1 PO sets with authoritative outcomes table', () => {
    const markup = renderToStaticMarkup(createElement(CoordinatorPOSetManager));

    expect(markup).toContain('v2 Active');
    expect(markup).toContain('v1 Archived');
    expect(markup).toContain('PO1');
    expect(markup).toContain('Engineering Fundamentals');
    expect(markup).toContain('New draft PO set');
    expect(markup).toContain('Immutable active version');
  });
});
