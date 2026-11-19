import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  applyGradeImport,
  dryRunGradeImport,
  getGradeBatches,
  getGradeImportTemplate,
  getGrades,
  saveGradesBulk,
} from './api';

afterEach(() => vi.unstubAllGlobals());

const batch = (id: string) => ({
  id,
  offering: 'offering-1',
  name: `Batch ${id}`,
  released_at: null,
  created_at: '2026-01-01T00:00:00Z',
});

it('retrieves all grade batches without following untrusted pagination URLs', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        next: 'https://example.invalid/next',
        previous: null,
        results: [batch('1')],
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        count: 2,
        next: null,
        previous: 'previous',
        results: [batch('2')],
      }),
    );
  vi.stubGlobal('fetch', fetcher);
  const controller = new AbortController();

  expect(
    (await getGradeBatches('offering-1', controller.signal)).map(
      (item) => item.id,
    ),
  ).toEqual(['1', '2']);
  expect(fetcher.mock.calls[1][0]).toBe(
    '/api/v1/grade-batches/?offering=offering-1&page_size=200&page=2',
  );
  expect(fetcher.mock.calls[1][1].signal).toBeInstanceOf(AbortSignal);
});

it('rejects inconsistent pagination instead of silently omitting grades', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      Response.json({
        count: 1,
        next: 'next',
        previous: null,
        results: [],
      }),
    ),
  );
  await expect(getGrades('offering-1')).rejects.toBeInstanceOf(ApiError);
});

it('sends bulk grade save payload with expected revision and idempotency key and validates response', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(
    Response.json({
      offering: 'offering-1',
      input_revision: 3,
      idempotency_key: 'idem-123',
      grades: [
        {
          id: 'g-1',
          offering: 'offering-1',
          enrollment: 'enr-1',
          assessment: 'asmt-1',
          assessment_title: 'Midterm',
          batch: 'batch-1',
          batch_name: 'Main',
          state: 'scored',
          points_earned: '0.00',
          points_possible: '100.00',
          version: 1,
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    }),
  );
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=test-csrf-token' });

  const response = await saveGradesBulk({
    offering: 'offering-1',
    expected_input_revision: 2,
    idempotency_key: 'idem-123',
    items: [
      {
        enrollment: 'enr-1',
        assessment: 'asmt-1',
        batch: 'batch-1',
        state: 'scored',
        points_earned: '0.00',
        reason: '',
      },
    ],
  });

  expect(response.input_revision).toBe(3);
  expect(response.grades[0].points_earned).toBe('0.00');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/grades/bulk/');
  expect(fetcher.mock.calls[0][1].cache).toBe('no-store');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    offering: 'offering-1',
    expected_input_revision: 2,
    idempotency_key: 'idem-123',
    items: [
      {
        enrollment: 'enr-1',
        assessment: 'asmt-1',
        batch: 'batch-1',
        state: 'scored',
        points_earned: '0.00',
        reason: '',
      },
    ],
  });
});

it('rejects malformed bulk grade save responses', async () => {
  vi.stubGlobal('document', { cookie: 'csrftoken=test-csrf-token' });
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValueOnce(
      Response.json({
        offering: 'offering-1',
        input_revision: 'invalid',
        grades: [],
      }),
    ),
  );
  await expect(
    saveGradesBulk({
      offering: 'offering-1',
      idempotency_key: 'idem-bad',
      items: [],
    }),
  ).rejects.toBeInstanceOf(ApiError);
});

it('fetches and validates the CSV grade import template', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(
    Response.json({
      offering_id: 'offering-1',
      columns: [
        'student_identifier',
        'assessment',
        'state',
        'points_earned',
        'reason',
      ],
      required_columns: [
        'student_identifier',
        'assessment',
        'state',
        'points_earned',
      ],
      max_bytes: 5242880,
      max_rows: 10000,
      sample_csv:
        'student_identifier,assessment,state,points_earned,reason\nS1001,Midterm,scored,85.00,\n',
    }),
  );
  vi.stubGlobal('fetch', fetcher);

  const template = await getGradeImportTemplate('offering-1');
  expect(template.max_rows).toBe(10000);
  expect(template.sample_csv).toContain('student_identifier');
  expect(fetcher.mock.calls[0][0]).toBe(
    '/api/v1/grades/import/template/?offering=offering-1',
  );
  expect(fetcher.mock.calls[0][1].cache).toBe('no-store');
});

it('posts CSV dry-run and apply payloads and validates responses', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        offering: 'offering-1',
        sanitized_filename: 'grades.csv',
        file_checksum: 'a'.repeat(64),
        expected_input_revision: 2,
        total_rows: 1,
        valid_rows: 1,
        invalid_rows: 0,
        create_count: 1,
        update_count: 0,
        unchanged_count: 0,
        can_apply: true,
        errors: [],
        rows: [
          {
            row_number: 1,
            student_identifier: 'S1001',
            enrollment_id: 'enr-1',
            assessment_identifier: 'Midterm',
            assessment_id: 'asmt-1',
            state: 'scored',
            points_earned: '90.00',
            reason: '',
            action: 'create',
            errors: [],
          },
        ],
      }),
    )
    .mockResolvedValueOnce(
      Response.json(
        {
          offering: 'offering-1',
          batch: 'batch-1',
          batch_name: 'CSV Import (grades.csv)',
          batch_released: false,
          idempotency_key: 'idem-csv-1',
          file_checksum: 'a'.repeat(64),
          sanitized_filename: 'grades.csv',
          total_rows: 1,
          created_count: 1,
          updated_count: 0,
          unchanged_count: 0,
          resulting_input_revision: 2,
        },
        { status: 201 },
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  vi.stubGlobal('document', { cookie: 'csrftoken=test-csrf-token' });

  const csvText =
    'student_identifier,assessment,state,points_earned\nS1001,Midterm,scored,90\n';
  const report = await dryRunGradeImport({
    offering: 'offering-1',
    csv_text: csvText,
    filename: 'grades.csv',
  });
  expect(report.can_apply).toBe(true);
  expect(report.create_count).toBe(1);
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/grades/import/dry-run/');

  const applied = await applyGradeImport({
    offering: 'offering-1',
    csv_text: csvText,
    idempotency_key: 'idem-csv-1',
    file_checksum: report.file_checksum,
    expected_input_revision: report.expected_input_revision,
    filename: 'grades.csv',
  });
  expect(applied.created_count).toBe(1);
  expect(applied.batch_released).toBe(false);
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/grades/import/apply/');
});

it('rejects malformed CSV dry-run responses', async () => {
  vi.stubGlobal('document', { cookie: 'csrftoken=test-csrf-token' });
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValueOnce(Response.json({ offering: 'offering-1' })),
  );
  await expect(
    dryRunGradeImport({ offering: 'offering-1', csv_text: 'bad' }),
  ).rejects.toBeInstanceOf(ApiError);
});
