import { expect, it } from 'vitest';
import {
  CANONICAL_PO_CODES,
  buildStudentPOProfile,
  roundHalfUpOneDecimal,
} from './profile';
import type { StudentOutcomeScore } from './types';

function makeScore(
  overrides: Partial<StudentOutcomeScore>,
): StudentOutcomeScore {
  return {
    id: 'score-1',
    run: 'run-1',
    level: 'cumulative_po',
    student: 1,
    offering: null,
    learning_outcome: null,
    program_outcome: null,
    outcome_code: 'PO1',
    value: null,
    display_value: null,
    numerator: null,
    denominator: null,
    coverage: '0.0000',
    status: 'NOT_ASSESSED',
    evidence: { contributions: [], missing: [], exemptions: [] },
    ...overrides,
  };
}

it('rounds exact decimal strings using ROUND_HALF_UP to 1 decimal place', () => {
  expect(roundHalfUpOneDecimal('84.952381')).toBe('85.0');
  expect(roundHalfUpOneDecimal('82.857143')).toBe('82.9');
  expect(roundHalfUpOneDecimal('0')).toBe('0.0');
  expect(roundHalfUpOneDecimal('0.000000')).toBe('0.0');
  expect(roundHalfUpOneDecimal('0.05')).toBe('0.1');
  expect(roundHalfUpOneDecimal('99.95')).toBe('100.0');
});

it('always produces all 11 POs with null for unassessed/incomplete/exempt and 0.0 for real measured zero', () => {
  const scores: StudentOutcomeScore[] = [
    makeScore({
      id: 's1',
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
            syllabus_version: 1,
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
      },
    }),
    makeScore({
      id: 's2',
      outcome_code: 'PO2',
      value: '0.000000',
      display_value: '0.0',
      numerator: '0.000000',
      denominator: '3.000000',
      coverage: '1.0000',
      status: 'OK',
    }),
    makeScore({
      id: 's3',
      outcome_code: 'PO3',
      value: null,
      display_value: null,
      coverage: '0.5000',
      status: 'INCOMPLETE',
      evidence: { missing: ['CSE321'] },
    }),
    makeScore({
      id: 's4',
      outcome_code: 'PO4',
      value: null,
      display_value: null,
      coverage: '0.0000',
      status: 'ALL_EXEMPT',
      evidence: { exemptions: [{ course_code: 'CSE331', reason: 'Medical' }] },
    }),
  ];

  const profile = buildStudentPOProfile(scores);
  expect(profile.map((item) => item.code)).toEqual([...CANONICAL_PO_CODES]);

  const po1 = profile[0];
  expect(po1.value).toBe(85);
  expect(po1.displayValue).toBe('85.0');
  expect(po1.statusLabel).toBe('Measured');
  expect(po1.coverageDisplay).toBe('100%');
  expect(po1.courses[0].course_code).toBe('CSE311');
  expect(po1.courses[0].lo_contributions[0].assessment_contributions[0].assessment_code).toBe(
    'Midterm',
  );

  // Real measured zero is distinct from unassessed!
  const po2 = profile[1];
  expect(po2.value).toBe(0);
  expect(po2.displayValue).toBe('0.0');
  expect(po2.statusLabel).toBe('Measured');

  // Incomplete & All exempt are strictly null, never 0.
  const po3 = profile[2];
  expect(po3.value).toBeNull();
  expect(po3.displayValue).toBe('—');
  expect(po3.statusLabel).toBe('Incomplete');
  expect(po3.missing).toEqual(['CSE321']);

  const po4 = profile[3];
  expect(po4.value).toBeNull();
  expect(po4.displayValue).toBe('—');
  expect(po4.statusLabel).toBe('All exempt');
  expect(po4.exemptions).toEqual([{ label: 'CSE331', reason: 'Medical' }]);

  // PO5–PO11 filled in automatically as NOT_ASSESSED with null value.
  for (let idx = 4; idx < 11; idx += 1) {
    expect(profile[idx].status).toBe('NOT_ASSESSED');
    expect(profile[idx].statusLabel).toBe('Not assessed');
    expect(profile[idx].value).toBeNull();
    expect(profile[idx].displayValue).toBe('—');
  }
});

it('joins offering-level course_po rows with frozen lo rows for full drill-down', () => {
  const scores: StudentOutcomeScore[] = [
    makeScore({
      id: 'lo-score-1',
      level: 'lo',
      learning_outcome: 'lo-uuid-1',
      outcome_code: 'LO1',
      value: '86.000000',
      display_value: '86.0',
      numerator: '8600.000000',
      denominator: '100.000000',
      coverage: '1.0000',
      status: 'OK',
      evidence: {
        contributions: [
          {
            assessment_code: 'Midterm',
            weight: '60',
            points_earned: '90',
            points_possible: '100',
            normalized_score: '90',
            grade_state: 'scored',
            grade_version: 1,
          },
        ],
      },
    }),
    makeScore({
      id: 'cpo-score-1',
      level: 'course_po',
      outcome_code: 'PO-1',
      value: '86.000000',
      display_value: '86.0',
      numerator: '172.000000',
      denominator: '2.000000',
      coverage: '1.0000',
      status: 'OK',
      evidence: {
        syllabus_version: 2,
        contributions: [
          {
            learning_outcome_id: 'lo-uuid-1',
            lo_code: 'LO1',
            weight: '2',
            value: '86',
          },
        ],
      },
    }),
  ];

  const profile = buildStudentPOProfile(scores);
  expect(profile).toHaveLength(11);
  expect(profile[0].code).toBe('PO1');
  expect(profile[0].displayValue).toBe('86.0');
  expect(profile[0].learningOutcomes).toHaveLength(1);
  expect(profile[0].learningOutcomes[0].assessment_contributions[0].assessment_code).toBe(
    'Midterm',
  );
  expect(profile[0].sourceRevisions).toContain('Syllabus v2');
});
