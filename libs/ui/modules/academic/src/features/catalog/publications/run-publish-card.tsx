'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useId, useMemo, useState } from 'react';
import { Calculator, RefreshCw, Send } from 'lucide-react';
import { errorMessage } from '@outcometrik/access';
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
  FieldGroup,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
} from '@outcometrik/ui';
import {
  buildPublishIdempotencyKey,
  parsePublicationConflict,
  publishCalculationRun,
  runProgramCalculation,
  type CalculationRun,
  type GovernancePublication,
  type PublicationAudience,
} from '../publications-api';

function shortHash(hash: string): string {
  return hash.length > 12 ? hash.slice(0, 12) : hash;
}

export interface RunPublishCardProps {
  programId: string;
  hasActivePoSet: boolean;
  hasApprovedSyllabus: boolean;
  latestRun: CalculationRun | null;
  publications: GovernancePublication[];
  terms: Array<{ id: string; label: string }>;
}

/**
 * Isolated Run Calculation & Publish card owning audience/term selection,
 * mutations, and 409 conflict recovery state so interactions never re-render
 * the Readiness Gates or Publication Series Table.
 */
export function RunPublishCard({
  programId,
  hasActivePoSet,
  hasApprovedSyllabus,
  latestRun,
  publications,
  terms,
}: RunPublishCardProps) {
  const queryClient = useQueryClient();
  const audienceSelectId = useId();
  const termSelectId = useId();

  const [audience, setAudience] = useState<PublicationAudience>('faculty');
  const [selectedTermId, setSelectedTermId] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [conflictState, setConflictState] = useState<{
    code: string;
    message: string;
  } | null>(null);

  const currentSeriesVersion = useMemo(() => {
    let max = 0;
    for (const p of publications) {
      if (p.offering === null && p.audience === audience && p.series_version > max) {
        max = p.series_version;
      }
    }
    return max;
  }, [publications, audience]);

  const nextSeriesVersion = currentSeriesVersion + 1;

  const runCalculationMutation = useMutation({
    mutationFn: (pid: string) => runProgramCalculation(pid),
    onSuccess: async (run) => {
      setConflictState(null);
      setStatusMessage(
        `Calculation run ${run.id.slice(0, 8)} completed (PO-Set v${run.po_set_version}).`,
      );
      await queryClient.invalidateQueries({
        queryKey: ['academic', 'calculation-runs', programId],
      });
    },
  });

  const runAndPublishMutation = useMutation({
    mutationFn: async (args: {
      programId: string;
      audience: PublicationAudience;
      termId: string | null;
      expectedSeriesVersion: number;
    }) => {
      const run = await runProgramCalculation(args.programId);
      const idempotencyKey = buildPublishIdempotencyKey({
        programId: args.programId,
        runId: run.id,
        expectedSeriesVersion: args.expectedSeriesVersion,
        audience: args.audience,
      });
      const publication = await publishCalculationRun({
        run: run.id,
        expected_series_version: args.expectedSeriesVersion,
        expected_input_hash: run.input_hash,
        audience: args.audience,
        idempotency_key: idempotencyKey,
        term: args.termId || null,
      });
      return { run, publication };
    },
    onSuccess: async ({ publication }) => {
      setConflictState(null);
      setStatusMessage(
        `Published Series v${publication.series_version} (${publication.audience}) — Publication ${publication.id.slice(0, 8)}.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ['academic', 'calculation-runs', programId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['academic', 'publications', programId],
        }),
        queryClient.invalidateQueries({
          queryKey: ['reports', 'coordinator-publications'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['reports', 'cohort-analytics'],
        }),
      ]);
    },
    onError: (err) => {
      const parsed = parsePublicationConflict(err);
      if (parsed.isConflict) {
        setConflictState({
          code: parsed.code ?? 'stale_input',
          message: parsed.message,
        });
      }
    },
  });

  const isBusy =
    runCalculationMutation.isPending || runAndPublishMutation.isPending;

  return (
    <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
      <CardHeader className="border-b border-border/70 pb-4">
        <CardTitle>
          <h2 className="text-base font-semibold tracking-tight">
            Run calculation &amp; publish immutable series
          </h2>
        </CardTitle>
        <CardDescription>
          Executes the deterministic decimal scoring kernel and seals Series v
          {nextSeriesVersion}. Existing publications remain immutable.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        <FieldGroup className="grid gap-3 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor={audienceSelectId}>Audience</FieldLabel>
            <NativeSelect
              id={audienceSelectId}
              value={audience}
              disabled={isBusy}
              onChange={(e) =>
                setAudience(e.target.value as PublicationAudience)
              }
            >
              <NativeSelectOption value="faculty">
                Faculty &amp; accreditation
              </NativeSelectOption>
              <NativeSelectOption value="student">
                Student portal release
              </NativeSelectOption>
            </NativeSelect>
          </Field>

          <Field>
            <FieldLabel htmlFor={termSelectId}>Term tag (optional)</FieldLabel>
            <NativeSelect
              id={termSelectId}
              value={selectedTermId}
              disabled={isBusy}
              onChange={(e) => setSelectedTermId(e.target.value)}
            >
              <NativeSelectOption value="">
                Cumulative (all terms)
              </NativeSelectOption>
              {terms.map((t) => (
                <NativeSelectOption key={t.id} value={t.id}>
                  {t.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>
        </FieldGroup>

        {latestRun && (
          <div className="rounded-[var(--radius-input,6px)] border border-border/80 bg-[var(--surface-subtle)]/50 p-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-foreground">
                Latest calculation run
              </span>
              <span className="tabular-mono text-muted-foreground">
                Run {latestRun.id.slice(0, 8)} · PO-Set v
                {latestRun.po_set_version}
              </span>
            </div>
            <p className="tabular-mono mt-1 text-[11px] text-muted-foreground">
              Input hash: {shortHash(latestRun.input_hash)} · Engine{' '}
              {latestRun.engine_version} · Policy {latestRun.policy_version}
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={isBusy || !hasActivePoSet}
            onClick={() => runCalculationMutation.mutate(programId)}
          >
            <Calculator className="size-4" aria-hidden="true" />
            {runCalculationMutation.isPending
              ? 'Calculating…'
              : 'Run calculation only'}
          </Button>

          <Button
            type="button"
            disabled={isBusy || !hasActivePoSet || !hasApprovedSyllabus}
            onClick={() =>
              runAndPublishMutation.mutate({
                programId,
                audience,
                termId: selectedTermId || null,
                expectedSeriesVersion: currentSeriesVersion,
              })
            }
          >
            <Send className="size-4" aria-hidden="true" />
            {runAndPublishMutation.isPending
              ? `Publishing Series v${nextSeriesVersion}…`
              : `Run calculation & publish Series v${nextSeriesVersion}`}
          </Button>
        </div>

        {statusMessage && (
          <p
            role="status"
            className="text-xs font-medium text-[var(--status-success-fg)]"
          >
            {statusMessage}
          </p>
        )}

        {conflictState && (
          <Alert variant="destructive">
            <AlertTitle>Publication conflict ({conflictState.code})</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>{conflictState.message}</p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={async () => {
                  setConflictState(null);
                  await Promise.all([
                    queryClient.invalidateQueries({
                      queryKey: ['academic', 'calculation-runs', programId],
                    }),
                    queryClient.invalidateQueries({
                      queryKey: ['academic', 'publications', programId],
                    }),
                  ]);
                  runCalculationMutation.mutate(programId);
                }}
              >
                <RefreshCw className="size-3.5" aria-hidden="true" />
                Re-run calculation &amp; refresh
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {runCalculationMutation.isError && (
          <Alert variant="destructive">
            <AlertTitle>Calculation failed</AlertTitle>
            <AlertDescription>
              {errorMessage(runCalculationMutation.error)}
            </AlertDescription>
          </Alert>
        )}

        {runAndPublishMutation.isError && !conflictState && (
          <Alert variant="destructive">
            <AlertTitle>Publication failed</AlertTitle>
            <AlertDescription>
              {parsePublicationConflict(runAndPublishMutation.error).message}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
