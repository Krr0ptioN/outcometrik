'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Lock } from 'lucide-react';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Skeleton,
} from '@outcometrik/ui';
import {
  approveSyllabus,
  getSyllabusMappingValidation,
  type ProgramOutcome,
  type Syllabus,
} from '../api';
import { SyllabusMatrixPreview } from './syllabus-matrix-preview';
import { SyllabusStatusDot } from './validation';

type QueueFilter = 'draft' | 'approved' | 'all';

export interface QueueOfferingSummary {
  id: string;
  label: string;
  course: string;
  term: string;
}

export interface SyllabusApprovalQueueProps {
  syllabi: Syllabus[];
  syllabiPending: boolean;
  syllabiError: unknown;
  offeringById: Map<string, QueueOfferingSummary>;
  programOutcomes: ProgramOutcome[];
}

export function SyllabusApprovalQueue({
  syllabi,
  syllabiPending,
  syllabiError,
  offeringById,
  programOutcomes,
}: SyllabusApprovalQueueProps) {
  const queryClient = useQueryClient();
  const [queueFilter, setQueueFilter] = useState<QueueFilter>('draft');
  const [selectedSyllabusId, setSelectedSyllabusId] = useState<string>('');
  const [confirmApproveOpen, setConfirmApproveOpen] = useState(false);

  const draftCount = useMemo(
    () => syllabi.filter((s) => s.status === 'draft').length,
    [syllabi],
  );
  const approvedCount = useMemo(
    () => syllabi.filter((s) => s.status === 'approved').length,
    [syllabi],
  );

  const filteredSyllabi = useMemo(() => {
    if (queueFilter === 'all') return syllabi;
    return syllabi.filter((s) => s.status === queueFilter);
  }, [syllabi, queueFilter]);

  const activeSyllabus =
    filteredSyllabi.find((s) => s.id === selectedSyllabusId) ??
    filteredSyllabi[0] ??
    null;

  const validationQuery = useQuery({
    queryKey: ['academic', 'syllabus-validation', activeSyllabus?.id ?? null],
    queryFn: ({ signal }) =>
      getSyllabusMappingValidation(activeSyllabus?.id ?? '', signal),
    enabled: Boolean(activeSyllabus?.id),
  });

  const approveMutation = useMutation({
    mutationFn: (syllabusId: string) => approveSyllabus(syllabusId),
    onSuccess: async () => {
      setConfirmApproveOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['academic', 'syllabi'] }),
        queryClient.invalidateQueries({
          queryKey: ['academic', 'syllabus-validation'],
        }),
      ]);
    },
  });

  return (
    <>
      <Card className="border-border bg-card shadow-[var(--shadow-sm)]">
        <CardHeader className="border-b border-border/70 pb-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>
                <h2 className="text-lg font-semibold tracking-tight">
                  Syllabus approval queue
                </h2>
              </CardTitle>
              <CardDescription>
                Inspect A×LO and LO×PO mapping matrices and validation checks
                before locking a syllabus version.
              </CardDescription>
            </div>
            <div
              role="tablist"
              aria-label="Filter syllabus queue"
              className="inline-flex items-center rounded-[var(--radius-input,6px)] border border-border bg-muted/50 p-0.5"
            >
              {(
                [
                  { id: 'draft', label: `Pending drafts (${draftCount})` },
                  { id: 'approved', label: `Approved (${approvedCount})` },
                  { id: 'all', label: `All (${syllabi.length})` },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={queueFilter === tab.id}
                  onClick={() => setQueueFilter(tab.id)}
                  className={`rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
                    queueFilter === tab.id
                      ? 'bg-card text-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-5">
          {syllabiPending ? (
            <div className="space-y-3" role="status">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-44 w-full" />
            </div>
          ) : syllabiError ? (
            <Alert variant="destructive">
              <AlertTitle>Unable to load syllabi</AlertTitle>
              <AlertDescription>{errorMessage(syllabiError)}</AlertDescription>
            </Alert>
          ) : filteredSyllabi.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>
                  {queueFilter === 'draft'
                    ? 'No draft syllabi awaiting approval'
                    : 'No syllabi in this filter'}
                </EmptyTitle>
                <EmptyDescription>
                  Switch to Approved or All to inspect locked syllabus versions.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div
                role="listbox"
                aria-label="Syllabi in queue"
                className="space-y-2"
              >
                {filteredSyllabi.map((syllabus) => {
                  const offering = offeringById.get(syllabus.offering);
                  const isSelected = activeSyllabus?.id === syllabus.id;
                  return (
                    <button
                      key={syllabus.id}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => setSelectedSyllabusId(syllabus.id)}
                      className={`w-full rounded-[var(--radius-card,10px)] border p-3 text-left transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring ${
                        isSelected
                          ? 'border-[var(--accent-border)] bg-[var(--accent-soft)]'
                          : 'border-border bg-card hover:bg-[var(--surface-hover)]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                          {offering?.label ?? syllabus.offering.slice(0, 8)}
                        </span>
                        <Badge
                          variant="outline"
                          className="tabular-mono shrink-0 text-[11px]"
                        >
                          v{syllabus.version}
                        </Badge>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {offering?.term ?? ''}
                      </p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <SyllabusStatusDot status={syllabus.status} />
                        {syllabus.po_set_version !== null ? (
                          <span className="tabular-mono text-[11px] text-muted-foreground">
                            PO-Set v{syllabus.po_set_version}
                          </span>
                        ) : null}
                      </div>
                    </button>
                  );
                })}
              </div>

              {activeSyllabus ? (
                <div className="min-w-0 space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-4 rounded-[var(--radius-card,10px)] border border-border bg-[var(--surface-subtle)]/40 p-4">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold tracking-tight">
                          {offeringById.get(activeSyllabus.offering)?.label ??
                            'Offering'}{' '}
                          — Syllabus v{activeSyllabus.version}
                        </h3>
                        <SyllabusStatusDot status={activeSyllabus.status} />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {offeringById.get(activeSyllabus.offering)?.course} ·{' '}
                        {offeringById.get(activeSyllabus.offering)?.term}
                        {activeSyllabus.approved_at
                          ? ` · Locked ${activeSyllabus.approved_at.slice(0, 10)}`
                          : ''}
                      </p>
                    </div>

                    {activeSyllabus.status === 'draft' ? (
                      <Button
                        type="button"
                        onClick={() => setConfirmApproveOpen(true)}
                        disabled={
                          approveMutation.isPending ||
                          (validationQuery.data !== undefined &&
                            !validationQuery.data.is_valid_for_approval)
                        }
                      >
                        <Lock className="size-4" aria-hidden="true" />
                        Approve &amp; lock
                      </Button>
                    ) : (
                      <Badge
                        variant="secondary"
                        className="inline-flex items-center gap-1.5"
                      >
                        <Lock className="size-3" aria-hidden="true" />
                        Immutable locked version
                      </Badge>
                    )}
                  </div>

                  {approveMutation.isError ? (
                    <Alert variant="destructive">
                      <AlertTitle>Approval blocked</AlertTitle>
                      <AlertDescription>
                        {errorMessage(approveMutation.error)}
                      </AlertDescription>
                    </Alert>
                  ) : null}

                  <SyllabusMatrixPreview
                    syllabus={activeSyllabus}
                    programOutcomes={programOutcomes}
                    validation={validationQuery.data}
                    validationPending={validationQuery.isPending}
                  />
                </div>
              ) : null}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmApproveOpen} onOpenChange={setConfirmApproveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve and permanently lock syllabus?</DialogTitle>
            <DialogDescription>
              Approving{' '}
              <strong>
                {activeSyllabus
                  ? `${offeringById.get(activeSyllabus.offering)?.label ?? 'Syllabus'} v${activeSyllabus.version}`
                  : 'this syllabus'}
              </strong>{' '}
              permanently locks its learning outcomes, assessments, A×LO
              mappings, LO×PO mappings, and Course→PO relevance weights. Any
              future edits will require creating a new draft revision.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setConfirmApproveOpen(false)}
              disabled={approveMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              disabled={!activeSyllabus || approveMutation.isPending}
              onClick={() =>
                activeSyllabus && approveMutation.mutate(activeSyllabus.id)
              }
            >
              {approveMutation.isPending
                ? 'Locking…'
                : 'Confirm approve & lock'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
