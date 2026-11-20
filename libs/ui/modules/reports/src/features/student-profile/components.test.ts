import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, expect, it, vi } from 'vitest';
import type { StudentOutcomeScore, StudentPublication } from './types';

const mockState = vi.hoisted(() => ({
  publications: {} as Record<string, unknown>,
  scores: {} as Record<string, unknown>,
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: readonly unknown[] }) =>
    queryKey[1] === 'student-publications'
      ? mockState.publications
      : mockState.scores,
}));

import { StudentPOProfile } from './components/student-po-profile';

const PUB_ID = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const RUN_ID = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';

const SAMPLE_PUB: StudentPublication = {
  id: PUB_ID,
  program: '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55',
  program_code: 'CSE-BS',
  program_title: 'B.S. in Computer Engineering',
  offering: null,
  offering_label: null,
  term: null,
  term_label: '2026 Fall',
  run: RUN_ID,
  scope_kind: 'program',
  series_version: 2,
  po_set_version: 1,
  audience: 'student',
  published_at: '2026-11-15T10:30:00Z',
  stale: false,
  program_outcomes: Array.from({ length: 11 }, (_, idx) => ({
    code: `PO${idx + 1}`,
    label: `Outcome ${idx + 1}`,
    description: `Description for PO${idx + 1}`,
    ordering: idx + 1,
  })),
};

const SAMPLE_SCORES: StudentOutcomeScore[] = [
  {
    id: 'score-po1',
    run: RUN_ID,
    level: 'cumulative_po',
    student: 10,
    offering: null,
    learning_outcome: null,
    program_outcome: 'po-1',
    outcome_code: 'PO1',
    value: '84.952381',
    display_value: '85.0',
    numerator: '339.809524',
    denominator: '4.000000',
    coverage: '1.0000',
    status: 'OK',
    evidence: {
      kernel_version: '1.0',
      policy_version: 'calc-policy-v1',
      contributions: [
        {
          course_code: 'CSE311',
          offering_id: 'off-1',
          term: '2026-fall',
          syllabus_id: 'syl-1',
          syllabus_version: 3,
          attempt_number: 1,
          weight: '4',
          course_po_status: 'OK',
          course_po_value: '84.952381',
          value: '84.952381',
          lo_contributions: [
            {
              lo_code: 'LO1',
              learning_outcome_id: 'lo-1',
              weight: '2',
              value: '86',
              numerator: '8600',
              denominator: '100',
              assessment_contributions: [
                {
                  assessment_code: 'Midterm',
                  weight: '60',
                  points_earned: '90',
                  points_possible: '100',
                  normalized_score: '90',
                  grade_state: 'scored',
                  grade_version: 1,
                  batch_released_at: '2026-11-10T00:00:00Z',
                },
              ],
            },
          ],
        },
      ],
      missing: [],
      exemptions: [],
    },
  },
  {
    id: 'score-po2',
    run: RUN_ID,
    level: 'cumulative_po',
    student: 10,
    offering: null,
    learning_outcome: null,
    program_outcome: 'po-2',
    outcome_code: 'PO2',
    value: '0.000000',
    display_value: '0.0',
    numerator: '0.000000',
    denominator: '3.000000',
    coverage: '1.0000',
    status: 'OK',
    evidence: { contributions: [], missing: [], exemptions: [] },
  },
];

beforeEach(() => {
  mockState.publications = {
    isPending: false,
    isError: false,
    data: [SAMPLE_PUB],
    refetch: vi.fn(),
  };
  mockState.scores = {
    isPending: false,
    isError: false,
    data: SAMPLE_SCORES,
    refetch: vi.fn(),
  };
});

it('renders accessible loading, empty, and error states', () => {
  mockState.publications = { isPending: true, isError: false };
  const loadingHtml = renderToStaticMarkup(createElement(StudentPOProfile));
  expect(loadingHtml).toContain('role="status"');
  expect(loadingHtml).toContain('Loading published outcome snapshots');

  mockState.publications = {
    isPending: false,
    isError: true,
    error: new Error('offline'),
    refetch: vi.fn(),
  };
  const errorHtml = renderToStaticMarkup(createElement(StudentPOProfile));
  expect(errorHtml).toContain('role="alert"');
  expect(errorHtml).toContain('Unable to load published outcome profile');

  mockState.publications = {
    isPending: false,
    isError: false,
    data: [],
    refetch: vi.fn(),
  };
  const actionsSpy = vi.fn(() => createElement('div', null, 'export-slot'));
  const emptyHtml = renderToStaticMarkup(
    createElement(StudentPOProfile, { renderActions: actionsSpy }),
  );
  expect(emptyHtml).toContain('No published outcome snapshots yet');
  expect(actionsSpy).toHaveBeenCalledWith(null);
});

it('renders all 11 POs with 0-100 scale, semantic data table, measured 0.0, and null Not assessed', () => {
  const actionsSpy = vi.fn((pubId: string | null) =>
    createElement('div', null, `export:${pubId}`),
  );
  const html = renderToStaticMarkup(
    createElement(StudentPOProfile, { renderActions: actionsSpy }),
  );

  // Metadata header & current badge
  expect(html).toContain('8f0d3c3e');
  expect(html).toContain('1c2d3e4f');
  expect(html).toContain('v1');
  expect(html).toContain('v2');
  expect(html).toContain('Current');

  // Explicit 0-100 axis ticks and accessible table semantics
  expect(html).toContain('Program Outcome attainment chart (0 to 100 scale)');
  expect(html).toContain('scope="col"');
  expect(html).toContain('scope="row"');
  expect(html).toContain('<caption');

  // All 11 PO codes present
  for (let i = 1; i <= 11; i += 1) {
    expect(html).toContain(`PO${i}`);
  }

  // PO1 measured 85.0, PO2 real measured 0.0, PO3..PO11 Not assessed (never 0)
  expect(html).toContain('85.0');
  expect(html).toContain('0.0');
  expect(html).toContain('Measured');
  expect(html).toContain('Not assessed');
  expect(html).toContain('Inspect evidence');
  expect(html).toContain('aria-expanded="false"');

  // Export action wired with active publicationId
  expect(actionsSpy).toHaveBeenCalledWith(PUB_ID);
  expect(html).toContain(`export:${PUB_ID}`);
});

it('renders explicit Stale badge without rewriting historical values', () => {
  mockState.publications = {
    isPending: false,
    isError: false,
    data: [{ ...SAMPLE_PUB, stale: true }],
    refetch: vi.fn(),
  };
  const html = renderToStaticMarkup(createElement(StudentPOProfile));
  expect(html).toContain(
    'Stale — source grades/mappings changed since publication; historical snapshot preserved',
  );
  expect(html).toContain('Historical snapshot is stale');
  expect(html).toContain('85.0');
});

it('renders keyboard-accessible evidence drill-down with formula, numerator, denominator, weights, and revisions', () => {
  const html = renderToStaticMarkup(
    createElement(StudentPOProfile, { initialExpandedCode: 'PO1' }),
  );

  expect(html).toContain('aria-expanded="true"');
  expect(html).toContain(`aria-controls="po-evidence-${PUB_ID}-PO1"`);
  expect(html).toContain('Hide evidence');
  expect(html).toContain('Σ (weight × source_score) / Σ (weight)');
  expect(html).toContain('339.809524 / 4.000000');
  expect(html).toContain('CSE311');
  expect(html).toContain('Course→PO weight: 4');
  expect(html).toContain('Syllabus v3');
  expect(html).toContain('LO1');
  expect(html).toContain('LO→PO weight: 2');
  expect(html).toContain('Midterm');
  expect(html).toContain('Raw: 90/100');
  expect(html).toContain('Normalized: 90.0 / 100');
  expect(html).toContain('Grade v1');
  expect(html).toContain('Kernel 1.0');
  expect(html).toContain('Policy calc-policy-v1');
});
