'use client';

import { useId, useState } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Field,
  FieldDescription,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
} from '@outcometrik/ui';
import {
  buildExportRequest,
  exportAvailability,
  exportErrorMessage,
  isExportFormat,
} from '../export-state';
import type { ExportTarget } from '../export-state';
import { useExportReport } from '../hooks/use-export-report';
import type { ExportFormat } from '../types';

export interface ExportPanelProps extends ExportTarget {
  title?: string;
}

const UNAVAILABLE = {
  'no-publication':
    'No published report is available yet. Reports appear here once results are published.',
  'needs-program': 'Choose a program to export its cohort report.',
} as const;

export function ExportPanel({
  title = 'Download report',
  ...target
}: ExportPanelProps) {
  const formatId = useId();
  const [format, setFormat] = useState<ExportFormat>('csv');
  const exportReport = useExportReport();
  const availability = exportAvailability(target);
  const request = buildExportRequest(target, format);
  const description =
    target.scope === 'student'
      ? 'Your own published outcome results.'
      : 'Published outcome results for the selected program.';
  const status = exportReport.isPending
    ? 'Preparing your report…'
    : exportReport.isSuccess
      ? `Downloaded ${exportReport.data.filename}.`
      : '';

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>{title}</h2>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {availability !== 'ready' ? (
          <p className="text-sm text-muted-foreground">
            {UNAVAILABLE[availability]}
          </p>
        ) : (
          <>
            <Field>
              <FieldLabel htmlFor={formatId}>File format</FieldLabel>
              <NativeSelect
                id={formatId}
                value={format}
                disabled={exportReport.isPending}
                onChange={(event) => {
                  if (!isExportFormat(event.target.value)) return;
                  setFormat(event.target.value);
                  exportReport.reset();
                }}
              >
                <NativeSelectOption value="csv">
                  CSV (spreadsheet)
                </NativeSelectOption>
                <NativeSelectOption value="pdf">
                  PDF (print or share)
                </NativeSelectOption>
              </NativeSelect>
              <FieldDescription>
                Not assessed values are never shown as zero in either format.
              </FieldDescription>
            </Field>
            <Button
              type="button"
              disabled={!request || exportReport.isPending}
              aria-busy={exportReport.isPending}
              onClick={() => request && exportReport.mutate(request)}
            >
              {exportReport.isPending
                ? 'Preparing…'
                : `Download ${format.toUpperCase()}`}
            </Button>
            {/* Always rendered so assistive technology announces changes to it. */}
            <p role="status" className="min-h-5 text-sm text-muted-foreground">
              {status}
            </p>
            {exportReport.isError && (
              <Alert variant="destructive">
                <AlertTitle>Download failed</AlertTitle>
                <AlertDescription>
                  {exportErrorMessage(exportReport.error)}
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
