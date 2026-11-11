import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import { downloadExport, exportPath, saveFile } from './index';
import type { ExportRequest, SaveDeps } from './index';

const PUBLICATION = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const PROGRAM = '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55';
const student: ExportRequest = {
  publicationId: PUBLICATION,
  format: 'csv',
  scope: 'student',
};
const cohort: ExportRequest = {
  publicationId: PUBLICATION,
  format: 'pdf',
  scope: 'cohort',
  programId: PROGRAM,
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function stubFetch(response: Response | Error) {
  const fetcher = vi.fn(() =>
    response instanceof Error
      ? Promise.reject(response)
      : Promise.resolve(response),
  );
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}
function csv(
  headers: Record<string, string> = {},
  body = 'po,score\nPO1,85.0\n',
) {
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/csv; charset=utf-8', ...headers },
  });
}
async function rejection(promise: Promise<unknown>) {
  const error = await promise.then(
    () => null,
    (e: unknown) => e,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

it('builds student and cohort export paths', () => {
  expect(exportPath(student)).toBe(
    `/api/v1/reports/exports/?publication_id=${PUBLICATION}&format=csv&scope=student`,
  );
  expect(exportPath(cohort)).toBe(
    `/api/v1/reports/exports/?publication_id=${PUBLICATION}&format=pdf&scope=cohort&program_id=${PROGRAM}`,
  );
});

it('rejects invalid requests before any network call', async () => {
  const fetcher = stubFetch(csv());
  const bad = {
    publicationId: 'not-a-uuid',
    format: 'xlsx',
    scope: 'cohort',
    programId: undefined,
  } as unknown as ExportRequest;
  const error = await rejection(downloadExport(bad));
  expect(error.kind).toBe('validation');
  expect(Object.keys(error.details as object).sort()).toEqual([
    'format',
    'program_id',
    'publication_id',
  ]);
  const studentWithProgram = {
    ...student,
    programId: PROGRAM,
  } as unknown as ExportRequest;
  expect((await rejection(downloadExport(studentWithProgram))).details).toEqual(
    {
      program_id: 'A student export has no program.',
    },
  );
  expect(fetcher).not.toHaveBeenCalled();
});

it('downloads a file with strict same-origin, read-only request options', async () => {
  const fetcher = stubFetch(
    csv({
      'Content-Disposition': 'attachment; filename="po-report-2026-fall.csv"',
    }),
  );
  const controller = new AbortController();
  const file = await downloadExport(student, controller.signal);
  expect(file.filename).toBe('po-report-2026-fall.csv');
  expect(file.format).toBe('csv');
  expect(await file.blob.text()).toBe('po,score\nPO1,85.0\n');
  const [path, init] = fetcher.mock.calls[0] as unknown as [
    string,
    RequestInit,
  ];
  expect(path).toBe(exportPath(student));
  expect(init).toMatchObject({
    method: 'GET',
    credentials: 'same-origin',
    redirect: 'error',
    cache: 'no-store',
  });
  expect(new Headers(init.headers).get('Accept')).toBe('text/csv');
  expect(init.signal).toBeInstanceOf(AbortSignal);
});

it('sanitizes the server filename and keeps the requested extension', async () => {
  const cases: [string | null, string][] = [
    ['attachment; filename="../../etc/evil name.csv"', 'evil_name.csv'],
    ['attachment; filename=C:\\temp\\report.pdf', 'report.csv'],
    ['attachment; filename=".hidden"', 'hidden.csv'],
    ['attachment; filename="report"', 'report.csv'],
    ['attachment', 'outcome-report.csv'],
    [null, 'outcome-report.csv'],
  ];
  for (const [header, expected] of cases) {
    stubFetch(csv(header === null ? {} : { 'Content-Disposition': header }));
    expect((await downloadExport(student)).filename).toBe(expected);
  }
});

it('maps HTTP failures to the shared error kinds and keeps the status', async () => {
  const cases: [number, string][] = [
    [400, 'validation'],
    [401, 'unauthorized'],
    [403, 'forbidden'],
    [404, 'unexpected'],
    [500, 'unavailable'],
  ];
  for (const [status, kind] of cases) {
    stubFetch(Response.json({ detail: 'no' }, { status }));
    const error = await rejection(downloadExport(cohort));
    expect([error.kind, error.status]).toEqual([kind, status]);
    expect(error.details).toEqual({ detail: 'no' });
  }
  stubFetch(new Response('<html>gateway</html>', { status: 502 }));
  const error = await rejection(downloadExport(cohort));
  expect([error.kind, error.details]).toEqual(['unavailable', null]);
});

it('rejects responses that are not the requested file', async () => {
  stubFetch(Response.json({ ok: true }));
  expect((await rejection(downloadExport(student))).kind).toBe('unexpected');
  stubFetch(new Response(null, { status: 204 }));
  expect((await rejection(downloadExport(student))).kind).toBe('unexpected');
  stubFetch(csv({}, ''));
  expect((await rejection(downloadExport(student))).kind).toBe('unexpected');
  stubFetch(
    new Response('%PDF-1.7', {
      headers: { 'Content-Type': 'application/pdf' },
    }),
  );
  expect((await rejection(downloadExport(student))).kind).toBe('unexpected');
});

it('reports network failures but preserves caller cancellation', async () => {
  stubFetch(new TypeError('offline'));
  expect((await rejection(downloadExport(student))).kind).toBe('unavailable');
  const controller = new AbortController();
  const abort = new DOMException('Aborted', 'AbortError');
  stubFetch(abort);
  controller.abort();
  await expect(downloadExport(student, controller.signal)).rejects.toBe(abort);
});

it('saves a file through a temporary link and releases the object URL', () => {
  vi.useFakeTimers();
  const link = { href: '', download: '', click: vi.fn(), remove: vi.fn() };
  const deps: SaveDeps = {
    createLink: () => link,
    createObjectURL: vi.fn(() => 'blob:report'),
    revokeObjectURL: vi.fn(),
  };
  const blob = new Blob(['a']);
  saveFile({ blob, filename: 'r.csv', format: 'csv' }, deps);
  expect(deps.createObjectURL).toHaveBeenCalledWith(blob);
  expect([link.href, link.download]).toEqual(['blob:report', 'r.csv']);
  expect(link.click).toHaveBeenCalledOnce();
  expect(link.remove).toHaveBeenCalledOnce();
  expect(deps.revokeObjectURL).not.toHaveBeenCalled();
  vi.runAllTimers();
  expect(deps.revokeObjectURL).toHaveBeenCalledWith('blob:report');
});
