import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import { exportAndSave } from './run';
import type { ExportRequest } from './types';

const request: ExportRequest = {
  publicationId: '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01',
  format: 'csv',
  scope: 'student',
};

afterEach(() => vi.unstubAllGlobals());

it('saves the file once after a successful download', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response('po,score\n', {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename="r.csv"',
        },
      }),
    ),
  );
  const save = vi.fn();
  const file = await exportAndSave(request, undefined, save);
  expect(save).toHaveBeenCalledExactlyOnceWith(file);
  expect(file.filename).toBe('r.csv');
});

it('saves nothing when the download fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(Response.json({}, { status: 403 })),
  );
  const save = vi.fn();
  await expect(exportAndSave(request, undefined, save)).rejects.toBeInstanceOf(
    ApiError,
  );
  expect(save).not.toHaveBeenCalled();
});
