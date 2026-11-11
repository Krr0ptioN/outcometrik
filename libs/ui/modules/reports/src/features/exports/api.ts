import { ApiError } from '@outcometrik/api';
import type { ApiErrorKind } from '@outcometrik/api';
import type { ExportFile, ExportFormat, ExportRequest } from './types';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MEDIA_TYPES: Record<ExportFormat, string> = {
  csv: 'text/csv',
  pdf: 'application/pdf',
};
// Generating a PDF can take longer than the shared 10 s JSON timeout.
const TIMEOUT_MS = 30_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function isUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID.test(value);
}

/**
 * Builds the export URL, or throws a validation ApiError naming every invalid field.
 * Server-side rules stay authoritative; this only stops obviously malformed requests.
 */
export function exportPath(input: ExportRequest): `/api/${string}` {
  const value: Record<string, unknown> = { ...input };
  const errors: Record<string, string> = {};
  if (!isUuid(value.publicationId))
    errors.publication_id = 'Choose a valid publication.';
  if (value.format !== 'csv' && value.format !== 'pdf')
    errors.format = 'Choose CSV or PDF.';
  if (value.scope === 'cohort') {
    if (!isUuid(value.programId)) errors.program_id = 'Choose a valid program.';
  } else if (value.scope === 'student') {
    if (value.programId !== undefined)
      errors.program_id = 'A student export has no program.';
  } else {
    errors.scope = 'Choose a student or cohort report.';
  }
  if (Object.keys(errors).length) throw new ApiError('validation', 0, errors);
  const query = new URLSearchParams({
    publication_id: input.publicationId,
    format: input.format,
    scope: input.scope,
  });
  if (input.scope === 'cohort') query.set('program_id', input.programId);
  return `/api/v1/reports/exports/?${query}`;
}

function errorKind(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 400 || status === 422) return 'validation';
  if (status === 409) return 'conflict';
  if (status >= 500) return 'unavailable';
  // 404 (missing, unpublished or hidden publication) stays 'unexpected'; callers read `status`.
  return 'unexpected';
}

/** Returns a safe download name: no path, only [A-Za-z0-9._-], and the right extension. */
function safeFilename(
  contentDisposition: string | null,
  format: ExportFormat,
): string {
  const fallback = `outcome-report.${format}`;
  const match = /filename\s*=\s*(?:"([^"]*)"|([^;]*))/i.exec(
    contentDisposition ?? '',
  );
  const raw = (match?.[1] ?? match?.[2] ?? '').trim();
  const base = raw.split(/[\\/]/).pop() ?? '';
  const cleaned = base
    .replace(/[^A-Za-z0-9._-]+/g, '_')
    .replace(/^[._]+/, '')
    .slice(0, 100);
  if (!cleaned) return fallback;
  const stem = cleaned.replace(/\.(csv|pdf)$/i, '');
  return stem ? `${stem}.${format}` : fallback;
}

/**
 * Downloads one report. The shared `request()` only handles JSON, so this uses `fetch`
 * directly with the same-origin, no-redirect rules and the shared error vocabulary.
 */
export async function downloadExport(
  input: ExportRequest,
  signal?: AbortSignal,
): Promise<ExportFile> {
  const path = exportPath(input);
  const combined = AbortSignal.any([
    AbortSignal.timeout(TIMEOUT_MS),
    ...(signal ? [signal] : []),
  ]);
  let response: Response;
  try {
    response = await fetch(path, {
      method: 'GET',
      headers: { Accept: MEDIA_TYPES[input.format] },
      credentials: 'same-origin',
      redirect: 'error',
      cache: 'no-store',
      signal: combined,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('unavailable', 0);
  }
  if (!response.ok) {
    let details: unknown = null;
    try {
      const body: unknown = await response.json();
      details = isRecord(body) ? body : null;
    } catch {
      // Error bodies are optional; the status already carries the meaning.
    }
    throw new ApiError(errorKind(response.status), response.status, details);
  }
  const contentType = response.headers
    .get('Content-Type')
    ?.split(';')[0]
    ?.trim()
    .toLowerCase();
  if (response.status !== 200 || contentType !== MEDIA_TYPES[input.format])
    throw new ApiError('unexpected', response.status);
  let blob: Blob;
  try {
    blob = await response.blob();
  } catch {
    if (signal?.aborted) throw signal.reason;
    throw new ApiError('unavailable', response.status);
  }
  if (blob.size === 0) throw new ApiError('unexpected', response.status);
  return {
    blob,
    filename: safeFilename(
      response.headers.get('Content-Disposition'),
      input.format,
    ),
    format: input.format,
  };
}
