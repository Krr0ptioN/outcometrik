import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  changeSyllabus,
  getProgramOutcomeSets,
  getProgramOutcomes,
  getSyllabi,
  getSyllabusMappingValidation,
  replaceAssessmentLOMappings,
  replaceLOPOMappings,
} from './api';

afterEach(() => vi.unstubAllGlobals());
const syllabus = {
  id: 's1',
  offering: 'o1',
  version: 1,
  status: 'draft',
  approved_at: null,
  po_set_version: 1,
  mapping_revision: 1,
  learning_outcomes: [],
  assessments: [],
  assessment_lo_mappings: [],
  lo_po_mappings: [],
};
it('loads and validates all syllabus pages for an offering', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ results: [syllabus], next: 'next' }))
    .mockResolvedValueOnce(
      Response.json({
        results: [{ ...syllabus, id: 's2', version: 2 }],
        next: null,
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  expect((await getSyllabi('o1')).map((item) => item.version)).toEqual([1, 2]);
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/syllabi/?offering=o1&page=2');
});
it('rejects malformed syllabus and outcome set responses', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ results: [{ id: 'bad' }], next: null }),
      ),
  );
  await expect(getSyllabi('o1')).rejects.toBeInstanceOf(ApiError);
  await expect(getProgramOutcomeSets('p1')).rejects.toBeInstanceOf(ApiError);
});
it('sends scoped child edits with CSRF protection', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({}));
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=token' });
  await changeSyllabus('s1/learning-outcomes/l1/', { code: 'LO1' }, 'PATCH');
  expect(fetcher.mock.calls[0][0]).toBe(
    '/api/v1/syllabi/s1/learning-outcomes/l1/',
  );
  expect(fetcher.mock.calls[0][1].method).toBe('PATCH');
  expect(fetcher.mock.calls[0][1].headers.get('X-CSRFToken')).toBe('token');
});

it('loads and validates outcome definitions before activation', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json([
        {
          id: 'p1',
          code: 'PO1',
          order: 1,
          label: 'Knowledge',
          description: 'Describe knowledge',
          source_reference: 'Policy',
        },
      ]),
    )
    .mockResolvedValueOnce(Response.json([{ id: 'p2', code: 'PO2' }]));
  vi.stubGlobal('fetch', fetcher);
  expect((await getProgramOutcomes('set1'))[0].code).toBe('PO1');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/po-sets/set1/outcomes/');
  await expect(getProgramOutcomes('set1')).rejects.toBeInstanceOf(ApiError);
});

it('replaces assessment-to-LO and LO-to-PO mapping matrices with revision checking', async () => {
  const updatedSyllabus = {
    ...syllabus,
    mapping_revision: 2,
    assessment_lo_mappings: [
      {
        id: 'm1',
        syllabus: 's1',
        assessment: 'a1',
        learning_outcome: 'lo1',
        weight: '60.00',
        is_active: true,
      },
    ],
    lo_po_mappings: [
      {
        id: 'mp1',
        syllabus: 's1',
        learning_outcome: 'lo1',
        program_outcome: 'po1',
        weight: 2,
        is_active: true,
      },
    ],
  };
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json(updatedSyllabus))
    .mockResolvedValueOnce(
      Response.json({ ...updatedSyllabus, mapping_revision: 3 }),
    )
    .mockResolvedValueOnce(Response.json({ invalid: true }));
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=token' });

  const resALo = await replaceAssessmentLOMappings('s1', 1, [
    { assessment: 'a1', learning_outcome: 'lo1', weight: '60.00' },
  ]);
  expect(resALo.mapping_revision).toBe(2);
  expect(fetcher.mock.calls[0][0]).toBe(
    '/api/v1/syllabi/s1/assessment-lo-mappings/',
  );

  const resLoPo = await replaceLOPOMappings('s1', 2, [
    { learning_outcome: 'lo1', program_outcome: 'po1', weight: 2 },
  ]);
  expect(resLoPo.mapping_revision).toBe(3);
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/syllabi/s1/lo-po-mappings/');

  await expect(replaceLOPOMappings('s1', 3, [])).rejects.toBeInstanceOf(
    ApiError,
  );
});

it('loads and validates syllabus mapping diagnostic report', async () => {
  const report = {
    syllabus_id: 's1',
    mapping_revision: 3,
    is_valid_for_approval: true,
    lo_statuses: [
      {
        learning_outcome_id: 'lo1',
        code: 'LO1',
        status: 'MAPPED',
        total_assessment_weight: '100.00',
        mapped_po_count: 1,
      },
    ],
    po_statuses: [
      {
        program_outcome_id: 'po1',
        code: 'PO1',
        status: 'ASSESSED',
        total_lo_weight: 2,
      },
      {
        program_outcome_id: 'po2',
        code: 'PO2',
        status: 'NOT_ASSESSED',
        total_lo_weight: 0,
      },
    ],
    unmapped_learning_outcomes: [],
    orphaned_learning_outcomes: [],
    unreachable_program_outcomes: [],
    errors: [],
  };
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json(report))
    .mockResolvedValueOnce(Response.json({ syllabus_id: 's1' }));
  vi.stubGlobal('fetch', fetcher);

  const validated = await getSyllabusMappingValidation('s1');
  expect(validated.is_valid_for_approval).toBe(true);
  expect(validated.lo_statuses[0].status).toBe('MAPPED');
  expect(validated.po_statuses[1].status).toBe('NOT_ASSESSED');
  expect(fetcher.mock.calls[0][0]).toBe(
    '/api/v1/syllabi/s1/mapping-validation/',
  );

  await expect(getSyllabusMappingValidation('s1')).rejects.toBeInstanceOf(
    ApiError,
  );
});
