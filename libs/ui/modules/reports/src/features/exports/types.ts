export type ExportFormat = 'csv' | 'pdf';

interface ExportRequestBase {
  /** UUID of an immutable publication. */
  publicationId: string;
  format: ExportFormat;
}
/** The signed-in student's own data; the server derives the student from the session. */
export interface StudentExportRequest extends ExportRequestBase {
  scope: 'student';
  programId?: undefined;
}
/** A program-level report; the server decides whether the user may export it. */
export interface CohortExportRequest extends ExportRequestBase {
  scope: 'cohort';
  programId: string;
}
export type ExportRequest = StudentExportRequest | CohortExportRequest;

export interface ExportFile {
  blob: Blob;
  /** Sanitized for use as a download name; never a path. */
  filename: string;
  format: ExportFormat;
}
