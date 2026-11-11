import { useMutation } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { exportAndSave } from '../run';
import type { ExportRequest } from '../types';

/** Download one report; an in-flight download is cancelled when the component unmounts. */
export function useExportReport() {
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  return useMutation({
    mutationFn: (request: ExportRequest) => {
      const next = new AbortController();
      controller.current = next;
      return exportAndSave(request, next.signal);
    },
  });
}
