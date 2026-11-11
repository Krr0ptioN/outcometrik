import { ApiError } from '@outcometrik/api';
import type { ExportFormat, ExportRequest } from './types';

export interface ExportTarget {
  /** The publication to export; null when none has been published yet. */
  publicationId: string | null;
  scope: ExportRequest['scope'];
  /** Required for cohort exports. */
  programId?: string | null;
}
export type ExportAvailability = 'no-publication' | 'needs-program' | 'ready';

export function isExportFormat(value: unknown): value is ExportFormat {
  return value === 'csv' || value === 'pdf';
}

export function exportAvailability(target: ExportTarget): ExportAvailability {
  if (!target.publicationId) return 'no-publication';
  if (target.scope === 'cohort' && !target.programId) return 'needs-program';
  return 'ready';
}

/** Returns the request to send, or null while the target is not ready to export. */
export function buildExportRequest(
  target: ExportTarget,
  format: ExportFormat,
): ExportRequest | null {
  if (exportAvailability(target) !== 'ready' || !target.publicationId)
    return null;
  if (target.scope === 'student')
    return { publicationId: target.publicationId, format, scope: 'student' };
  return {
    publicationId: target.publicationId,
    format,
    scope: 'cohort',
    programId: target.programId ?? '',
  };
}

const GENERIC = 'The report could not be downloaded. Please try again.';

/**
 * Plain-language message for a failed export. Server error bodies are deliberately not
 * shown: they must not be a way to learn about data outside the user's scope.
 */
export function exportErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return GENERIC;
  if (error.kind === 'unauthorized')
    return 'Your session has expired. Sign in again to download this report.';
  if (error.kind === 'forbidden')
    return 'You do not have permission to export this report.';
  if (error.status === 404)
    return 'This report is not available. It may be unpublished or outside your access.';
  if (error.status === 413)
    return 'This report is too large to download directly. Ask a coordinator for a smaller export.';
  if (error.kind === 'validation')
    return 'The report selection is not valid. Check it and try again.';
  if (error.kind === 'conflict')
    return 'The publication changed while exporting. Reload the page and try again.';
  if (error.kind === 'unavailable')
    return 'The report could not be generated right now. Published results are not affected. Please try again.';
  return GENERIC;
}
