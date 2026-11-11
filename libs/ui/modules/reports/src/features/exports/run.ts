import { downloadExport } from './api';
import { saveFile } from './download';
import type { ExportFile, ExportRequest } from './types';

/** Downloads a report and, only if that fully succeeds, hands it to the browser. */
export async function exportAndSave(
  request: ExportRequest,
  signal?: AbortSignal,
  save: (file: ExportFile) => void = saveFile,
): Promise<ExportFile> {
  const file = await downloadExport(request, signal);
  save(file);
  return file;
}
