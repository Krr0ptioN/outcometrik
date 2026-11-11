import type { ExportFile } from './types';

export interface DownloadLink {
  href: string;
  download: string;
  click(): void;
  remove(): void;
}
export interface SaveDeps {
  createLink(): DownloadLink;
  createObjectURL(blob: Blob): string;
  revokeObjectURL(url: string): void;
}
// Resolved at call time so importing this module never touches browser globals (SSR safe).
function browserDeps(): SaveDeps {
  return {
    createLink: () => {
      const link = document.createElement('a');
      document.body.append(link);
      return link;
    },
    createObjectURL: (blob) => URL.createObjectURL(blob),
    revokeObjectURL: (url) => URL.revokeObjectURL(url),
  };
}

/** Hands a downloaded report to the browser's save flow. */
export function saveFile(
  file: ExportFile,
  deps: SaveDeps = browserDeps(),
): void {
  const url = deps.createObjectURL(file.blob);
  const link = deps.createLink();
  link.href = url;
  link.download = file.filename;
  link.click();
  link.remove();
  // Revoking in the same tick can cancel the download in some browsers.
  setTimeout(() => deps.revokeObjectURL(url), 0);
}
