import { expect, it } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  buildExportRequest,
  exportAvailability,
  exportErrorMessage,
  isExportFormat,
} from './export-state';

const PUBLICATION = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const PROGRAM = '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55';

it('is unavailable until a publication exists, and for cohorts until a program is chosen', () => {
  expect(exportAvailability({ publicationId: null, scope: 'student' })).toBe(
    'no-publication',
  );
  expect(
    exportAvailability({
      publicationId: '',
      scope: 'cohort',
      programId: PROGRAM,
    }),
  ).toBe('no-publication');
  expect(
    exportAvailability({ publicationId: PUBLICATION, scope: 'cohort' }),
  ).toBe('needs-program');
  expect(
    exportAvailability({
      publicationId: PUBLICATION,
      scope: 'cohort',
      programId: null,
    }),
  ).toBe('needs-program');
  expect(
    exportAvailability({ publicationId: PUBLICATION, scope: 'student' }),
  ).toBe('ready');
  expect(
    exportAvailability({
      publicationId: PUBLICATION,
      scope: 'cohort',
      programId: PROGRAM,
    }),
  ).toBe('ready');
});

it('builds requests only when ready and never gives a student export a program', () => {
  expect(
    buildExportRequest({ publicationId: null, scope: 'student' }, 'csv'),
  ).toBeNull();
  expect(
    buildExportRequest({ publicationId: PUBLICATION, scope: 'cohort' }, 'pdf'),
  ).toBeNull();
  expect(
    buildExportRequest(
      { publicationId: PUBLICATION, scope: 'student', programId: PROGRAM },
      'csv',
    ),
  ).toEqual({ publicationId: PUBLICATION, format: 'csv', scope: 'student' });
  expect(
    buildExportRequest(
      { publicationId: PUBLICATION, scope: 'cohort', programId: PROGRAM },
      'pdf',
    ),
  ).toEqual({
    publicationId: PUBLICATION,
    format: 'pdf',
    scope: 'cohort',
    programId: PROGRAM,
  });
});

it('accepts only the supported formats', () => {
  expect(isExportFormat('csv')).toBe(true);
  expect(isExportFormat('pdf')).toBe(true);
  expect(['xlsx', '', null, undefined, 1].some(isExportFormat)).toBe(false);
});

it('explains each failure in plain language without echoing server details', () => {
  const leak = { detail: 'Student 4411 in Physics is not in your program' };
  const messages = [
    new ApiError('unauthorized', 401, leak),
    new ApiError('forbidden', 403, leak),
    new ApiError('unexpected', 404, leak),
    new ApiError('validation', 400, leak),
    new ApiError('conflict', 409, leak),
    new ApiError('unavailable', 500, leak),
    new ApiError('unexpected', 413, leak),
    new ApiError('unexpected', 200),
    new TypeError('boom'),
  ].map(exportErrorMessage);
  expect(new Set(messages.slice(0, 7)).size).toBe(7);
  expect(messages[0]).toMatch(/sign in/i);
  expect(messages[1]).toMatch(/permission/i);
  expect(messages[2]).toMatch(/not available/i);
  expect(messages[5]).toMatch(/not affected/i);
  expect(messages[6]).toMatch(/too large/i);
  expect(messages[7]).toBe(messages[8]);
  for (const message of messages) expect(message).not.toMatch(/4411|Physics/);
});
