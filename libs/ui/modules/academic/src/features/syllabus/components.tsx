'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { ApiError } from '@outcometrik/api';
import { errorMessage } from '@outcometrik/access';
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Field,
  FieldGroup,
  FieldLabel,
  Input,
  NativeSelect,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@outcometrik/ui';
import {
  changeProgramOutcomeSet,
  getProgramOutcomeSets,
  getProgramOutcomes,
  type ProgramOutcomeSet,
  changeSyllabus,
  deleteSyllabusPOContribution,
  getSyllabi,

  saveSyllabusPOContribution,

  getSyllabusMappingValidation,
  replaceAssessmentLOMappings,
  replaceLOPOMappings,

  type Assessment,
  type CoursePOContribution,
  type Outcome,
  type Syllabus,
} from './api';

function OutcomeForm({
  value,
  save,
  pending,
}: {
  value?: Outcome;
  save: (data: object) => void;
  pending: boolean;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save({
      code: data.get('code'),
      description: data.get('description'),
      order: Number(data.get('order')),
    });
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">
        {value ? `Edit ${value.code}` : 'Add learning outcome'}
      </h5>
      <FieldGroup>
        <Field>
          <FieldLabel>
            Code
            <Input
              name="code"
              required
              maxLength={32}
              defaultValue={value?.code}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Description
            <Input
              name="description"
              required
              defaultValue={value?.description}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Order
            <Input
              name="order"
              type="number"
              min="0"
              required
              defaultValue={value?.order}
            />
          </FieldLabel>
        </Field>
      </FieldGroup>
      <Button type="submit" disabled={pending}>
        {value ? 'Save outcome' : 'Add outcome'}
      </Button>
    </form>
  );
}
function AssessmentForm({
  value,
  save,
  pending,
}: {
  value?: Assessment;
  save: (data: object) => void;
  pending: boolean;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    save({
      code: data.get('code'),
      kind: data.get('kind'),
      order: Number(data.get('order')),
      max_points: data.get('max_points'),
      is_required: data.has('is_required'),
      is_active: data.has('is_active'),
    });
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded border p-3">
      <h5 className="font-medium">
        {value ? `Edit ${value.code}` : 'Add assessment'}
      </h5>
      <FieldGroup>
        <Field>
          <FieldLabel>
            Code
            <Input
              name="code"
              required
              maxLength={32}
              defaultValue={value?.code}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Kind
            <NativeSelect name="kind" defaultValue={value?.kind ?? 'exam'}>
              {['exam', 'homework', 'project', 'quiz', 'lab', 'other'].map(
                (kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ),
              )}
            </NativeSelect>
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Order
            <Input
              name="order"
              type="number"
              min="0"
              required
              defaultValue={value?.order}
            />
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel>
            Maximum points
            <Input
              name="max_points"
              type="number"
              min="0.01"
              step="0.01"
              required
              defaultValue={value?.max_points}
            />
          </FieldLabel>
        </Field>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            name="is_required"
            defaultChecked={value?.is_required ?? true}
          />{' '}
          Required
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            name="is_active"
            defaultChecked={value?.is_active ?? true}
          />{' '}
          Active
        </label>
      </FieldGroup>
      <Button type="submit" disabled={pending}>
        {value ? 'Save assessment' : 'Add assessment'}
      </Button>
    </form>
  );
}


function CoursePOContributionSection({
  syllabus,
  programId,
  canApprove,
  onChanged,
}: {
  syllabus: Syllabus;
  programId?: string;
  canApprove: boolean;
  onChanged: () => void;
}) {
  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', programId],
    queryFn: ({ signal }) => getProgramOutcomeSets(programId ?? '', signal),
    enabled: Boolean(programId),
  });
  const boundSet = poSetsQuery.data?.find(
    (item) => item.version === syllabus.po_set_version,
  );
  const outcomesQuery = useQuery({
    queryKey: ['academic', 'po-set-outcomes', boundSet?.id],
    queryFn: ({ signal }) => getProgramOutcomes(boundSet?.id ?? '', signal),
    enabled: Boolean(boundSet?.id),
  });

  const saveMutation = useMutation({
    mutationFn: ({
      program_outcome,
      weight,
      contributionId,
    }: {
      program_outcome: string;
      weight: number;
      contributionId?: string;
    }) =>
      saveSyllabusPOContribution(
        syllabus.id,
        { program_outcome, weight },
        contributionId,
      ),
    onSuccess: () => onChanged(),
  });

  const deleteMutation = useMutation({
    mutationFn: (contributionId: string) =>
      deleteSyllabusPOContribution(syllabus.id, contributionId),
    onSuccess: () => onChanged(),
  });

  const contributions: CoursePOContribution[] = syllabus.po_contributions ?? [];
  const isEditable = canApprove && syllabus.status === 'draft';
  const pending = saveMutation.isPending || deleteMutation.isPending;

  return (
    <section
      className="space-y-3"
      aria-label="Course-to-PO Contribution Weights (1–5)"
    >
      <div className="space-y-1">
        <h4 className="font-medium">Course-to-PO Contribution Weights (1–5)</h4>
        <p className="text-xs text-muted-foreground">
          Governance policy: Program Coordinator at offering syllabus version
          level. Unmapped POs produce <code>NOT_ASSESSED</code> (never 0).
        </p>
      </div>
      {syllabus.status === 'approved' && (
        <p className="text-xs text-muted-foreground">
          This syllabus version is approved and its contribution weights are
          locked. Create a new syllabus revision to change weights (which marks
          prior calculations stale without mutating earlier publications).
        </p>
      )}
      {saveMutation.isError && (
        <p role="alert">{errorMessage(saveMutation.error)}</p>
      )}
      {deleteMutation.isError && (
        <p role="alert">{errorMessage(deleteMutation.error)}</p>
      )}
      {outcomesQuery.isPending && boundSet && (
        <p role="status">Loading bound program outcomes…</p>
      )}
      {outcomesQuery.isError && (
        <p role="alert">{errorMessage(outcomesQuery.error)}</p>
      )}
      {outcomesQuery.data ? (
        <ul className="space-y-2">
          {outcomesQuery.data.map((po) => {
            const existing = contributions.find(
              (c) =>
                c.program_outcome === po.id ||
                c.program_outcome_code === po.code,
            );
            return (
              <li
                key={po.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm"
              >
                <div>
                  <span className="font-medium">{po.code}</span>: {po.label}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {existing ? (
                    <Badge variant="outline">Weight {existing.weight}/5</Badge>
                  ) : (
                    <Badge variant="secondary">Not mapped (NOT_ASSESSED)</Badge>
                  )}
                  {isEditable && (
                    <form
                      className="flex items-center gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const data = new FormData(event.currentTarget);
                        const rawWeight = Number(data.get('weight'));
                        saveMutation.mutate({
                          program_outcome: po.id,
                          weight: rawWeight,
                          contributionId: existing?.id,
                        });
                      }}
                    >
                      <label className="sr-only" htmlFor={`po-weight-${po.id}`}>
                        {po.code} contribution weight
                      </label>
                      <NativeSelect
                        id={`po-weight-${po.id}`}
                        name="weight"
                        defaultValue={String(existing?.weight ?? 3)}
                        aria-label={`${po.code} contribution weight`}
                      >
                        {[1, 2, 3, 4, 5].map((w) => (
                          <option key={w} value={w}>
                            {w}
                          </option>
                        ))}
                      </NativeSelect>
                      <Button type="submit" size="sm" disabled={pending}>
                        {existing ? 'Update weight' : 'Assign weight'}
                      </Button>
                      {existing && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={pending}
                          onClick={() => deleteMutation.mutate(existing.id)}
                        >
                          Remove
                        </Button>
                      )}
                    </form>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ) : contributions.length ? (
        <ul className="space-y-1 text-sm">
          {contributions.map((item) => (
            <li key={item.id} className="flex items-center gap-2">
              <span className="font-medium">{item.program_outcome_code}</span>
              <Badge variant="outline">Weight {item.weight}/5</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          No course-to-PO contribution weights mapped (NOT_ASSESSED).
        </p>
      )}
    </section>
  );
}

export interface MatrixCellError {
  matrix: 'alo' | 'lopo';
  cellKey: string;
  rowCode: string;
  colCode: string;
  rule: 'INVALID_RANGE';
  message: string;
}

export interface ALoCellValidationResult {
  valid: boolean;
  numericValue: number;
  error: string | null;
}

export interface LoPoCellValidationResult {
  valid: boolean;
  numericValue: number;
  error: string | null;
}

export interface ALoMatrixValidation {
  valid: boolean;
  errors: MatrixCellError[];
  errorByCell: Record<string, MatrixCellError>;
  payload: Array<{
    assessment: string;
    learning_outcome: string;
    weight: string;
  }>;
}

export interface LoPoMatrixValidation {
  valid: boolean;
  errors: MatrixCellError[];
  errorByCell: Record<string, MatrixCellError>;
  payload: Array<{
    learning_outcome: string;
    program_outcome: string;
    weight: number;
  }>;
}

export interface LiveLODiagnostic {
  id: string;
  code: string;
  status: 'MAPPED' | 'UNMAPPED';
  totalAssessmentWeight: number;
  mappedPoCount: number;
  isOrphan: boolean;
}

export interface LivePODiagnostic {
  id: string;
  code: string;
  status: 'ASSESSED' | 'NOT_ASSESSED' | 'UNREACHABLE';
  totalLoWeight: number;
}

export interface TraceabilityAssessmentShare {
  assessmentId: string;
  assessmentCode: string;
  weight: number;
  shareLabel: string;
}

export interface TraceabilityPOLink {
  poId: string;
  poCode: string;
  weight: number;
  poTotalWeight: number;
  poShareLabel: string;
}

export interface TraceabilityPathRow {
  loId: string;
  loCode: string;
  loStatus: 'MAPPED' | 'UNMAPPED';
  isOrphan: boolean;
  totalAssessmentWeight: number;
  assessmentShares: TraceabilityAssessmentShare[];
  poLinks: TraceabilityPOLink[];
}

export interface LiveMappingDiagnostics {
  aLoValidation: ALoMatrixValidation;
  loPoValidation: LoPoMatrixValidation;
  allCellErrors: MatrixCellError[];
  incompatibleVersion: boolean;
  incompatibleVersionMessage: string | null;
  loDiagnostics: LiveLODiagnostic[];
  poDiagnostics: LivePODiagnostic[];
  unmappedLOs: string[];
  orphanedLOs: string[];
  unreachablePOs: string[];
  unassessedPOs: string[];
  traceabilityRows: TraceabilityPathRow[];
}

export function formatWeightNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
}

export function buildALoBaseline(version: Syllabus): Record<string, string> {
  const baseline: Record<string, string> = {};
  for (const mapping of version.assessment_lo_mappings ?? []) {
    if (mapping.is_active && Number(mapping.weight) > 0) {
      baseline[`${mapping.assessment}:${mapping.learning_outcome}`] =
        mapping.weight;
    }
  }
  return baseline;
}

export function buildLoPoBaseline(version: Syllabus): Record<string, string> {
  const baseline: Record<string, string> = {};
  for (const mapping of version.lo_po_mappings ?? []) {
    if (mapping.is_active && mapping.weight >= 1 && mapping.weight <= 5) {
      baseline[`${mapping.learning_outcome}:${mapping.program_outcome}`] =
        String(mapping.weight);
    }
  }
  return baseline;
}

export function isALoCellDirty(
  draftValue: string | undefined,
  baselineValue: string | undefined,
): boolean {
  const rawDraft = (draftValue ?? '').trim();
  const rawBase = (baselineValue ?? '').trim();
  if (rawDraft === rawBase) return false;
  const draftNum = rawDraft === '' ? 0 : Number(rawDraft);
  const baseNum = rawBase === '' ? 0 : Number(rawBase);
  if (
    !Number.isFinite(draftNum) ||
    Number.isNaN(draftNum) ||
    draftNum < 0 ||
    !Number.isFinite(baseNum) ||
    Number.isNaN(baseNum) ||
    baseNum < 0
  ) {
    return true;
  }
  return draftNum !== baseNum;
}

export function isLoPoCellDirty(
  draftValue: string | undefined,
  baselineValue: string | undefined,
): boolean {
  const rawDraft = (draftValue ?? '').trim();
  const rawBase = (baselineValue ?? '').trim();
  if (rawDraft === rawBase) return false;
  const draftValid = rawDraft === '' || /^[0-5]$/.test(rawDraft);
  const baseValid = rawBase === '' || /^[0-5]$/.test(rawBase);
  if (!draftValid || !baseValid) return true;
  const draftNum = rawDraft === '' ? 0 : Number(rawDraft);
  const baseNum = rawBase === '' ? 0 : Number(rawBase);
  return draftNum !== baseNum;
}

export function validateALoCell(
  assessmentCode: string,
  loCode: string,
  rawValue: string,
): ALoCellValidationResult {
  const trimmed = rawValue.trim();
  if (trimmed === '') {
    return { valid: true, numericValue: 0, error: null };
  }
  const num = Number(trimmed);
  if (!Number.isFinite(num) || Number.isNaN(num) || num < 0) {
    return {
      valid: false,
      numericValue: Number.NaN,
      error: `Cell [${assessmentCode} → ${loCode}]: A→LO weight must be a nonnegative number (>= 0).`,
    };
  }
  return { valid: true, numericValue: num, error: null };
}

export function validateLoPoCell(
  loCode: string,
  poCode: string,
  rawValue: string,
): LoPoCellValidationResult {
  const trimmed = rawValue.trim();
  if (trimmed === '') {
    return { valid: true, numericValue: 0, error: null };
  }
  const isWholeNumber = /^\d+$/.test(trimmed);
  const num = isWholeNumber ? Number(trimmed) : Number.NaN;
  if (!isWholeNumber || !Number.isInteger(num) || num < 0 || num > 5) {
    return {
      valid: false,
      numericValue: Number.NaN,
      error: `Cell [${loCode} → ${poCode}]: LO→PO weight must be an integer from 1 to 5 (or 0 for unmapped).`,
    };
  }
  return { valid: true, numericValue: num, error: null };
}

export function validateALoMatrix(
  assessments: readonly Assessment[],
  learningOutcomes: readonly Outcome[],
  draft: Record<string, string>,
): ALoMatrixValidation {
  const errors: MatrixCellError[] = [];
  const errorByCell: Record<string, MatrixCellError> = {};
  const payload: ALoMatrixValidation['payload'] = [];

  for (const assessment of assessments) {
    for (const lo of learningOutcomes) {
      const cellKey = `${assessment.id}:${lo.id}`;
      const raw = draft[cellKey] ?? '';
      const result = validateALoCell(assessment.code, lo.code, raw);
      if (!result.valid && result.error) {
        const err: MatrixCellError = {
          matrix: 'alo',
          cellKey,
          rowCode: assessment.code,
          colCode: lo.code,
          rule: 'INVALID_RANGE',
          message: result.error,
        };
        errors.push(err);
        errorByCell[cellKey] = err;
      } else if (result.numericValue > 0) {
        payload.push({
          assessment: assessment.id,
          learning_outcome: lo.id,
          weight: raw.trim(),
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    errorByCell,
    payload,
  };
}

export function validateLoPoMatrix(
  learningOutcomes: readonly Outcome[],
  programOutcomes: ReadonlyArray<{ id: string; code: string }>,
  draft: Record<string, string>,
): LoPoMatrixValidation {
  const errors: MatrixCellError[] = [];
  const errorByCell: Record<string, MatrixCellError> = {};
  const payload: LoPoMatrixValidation['payload'] = [];

  for (const lo of learningOutcomes) {
    for (const po of programOutcomes) {
      const cellKey = `${lo.id}:${po.id}`;
      const raw = draft[cellKey] ?? '';
      const result = validateLoPoCell(lo.code, po.code, raw);
      if (!result.valid && result.error) {
        const err: MatrixCellError = {
          matrix: 'lopo',
          cellKey,
          rowCode: lo.code,
          colCode: po.code,
          rule: 'INVALID_RANGE',
          message: result.error,
        };
        errors.push(err);
        errorByCell[cellKey] = err;
      } else if (result.numericValue >= 1 && result.numericValue <= 5) {
        payload.push({
          learning_outcome: lo.id,
          program_outcome: po.id,
          weight: result.numericValue,
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    errorByCell,
    payload,
  };
}

export function computeLiveMappingDiagnostics({
  version,
  programOutcomes,
  aLoDraft,
  loPoDraft,
  activePoSetVersion,
}: {
  version: Syllabus;
  programOutcomes: ReadonlyArray<{ id: string; code: string }>;
  aLoDraft: Record<string, string>;
  loPoDraft: Record<string, string>;
  activePoSetVersion?: number | null;
}): LiveMappingDiagnostics {
  const aLoValidation = validateALoMatrix(
    version.assessments,
    version.learning_outcomes,
    aLoDraft,
  );
  const loPoValidation = validateLoPoMatrix(
    version.learning_outcomes,
    programOutcomes,
    loPoDraft,
  );
  const allCellErrors = [...aLoValidation.errors, ...loPoValidation.errors];

  let incompatibleVersion = false;
  let incompatibleVersionMessage: string | null = null;
  if (version.po_set_version === null) {
    incompatibleVersion = true;
    incompatibleVersionMessage =
      'INCOMPATIBLE_VERSION: This syllabus is not bound to any PO-set version. Bind the program’s active PO-set before approval.';
  } else if (
    activePoSetVersion !== undefined &&
    activePoSetVersion !== null &&
    version.po_set_version !== activePoSetVersion
  ) {
    incompatibleVersion = true;
    incompatibleVersionMessage = `INCOMPATIBLE_VERSION: Syllabus is bound to PO-set v${version.po_set_version}, but the program’s active PO-set is v${activePoSetVersion}. Bind the active PO-set before approval.`;
  }

  const activeAssessments = version.assessments.filter((a) => a.is_active);
  const loTotalMap = new Map<string, number>();
  const loSharesMap = new Map<
    string,
    Array<{ assessmentId: string; assessmentCode: string; weight: number }>
  >();

  for (const lo of version.learning_outcomes) {
    let total = 0;
    const shares: Array<{
      assessmentId: string;
      assessmentCode: string;
      weight: number;
    }> = [];
    for (const assessment of activeAssessments) {
      const cellKey = `${assessment.id}:${lo.id}`;
      const res = validateALoCell(
        assessment.code,
        lo.code,
        aLoDraft[cellKey] ?? '',
      );
      if (res.valid && res.numericValue > 0) {
        total += res.numericValue;
        shares.push({
          assessmentId: assessment.id,
          assessmentCode: assessment.code,
          weight: res.numericValue,
        });
      }
    }
    loTotalMap.set(lo.id, total);
    loSharesMap.set(lo.id, shares);
  }

  const loPoLinksByLo = new Map<
    string,
    Array<{ poId: string; poCode: string; weight: number }>
  >();
  const poLinksByPo = new Map<
    string,
    Array<{ loId: string; loCode: string; weight: number }>
  >();
  for (const lo of version.learning_outcomes) {
    loPoLinksByLo.set(lo.id, []);
  }
  for (const po of programOutcomes) {
    poLinksByPo.set(po.id, []);
  }

  for (const lo of version.learning_outcomes) {
    for (const po of programOutcomes) {
      const cellKey = `${lo.id}:${po.id}`;
      const res = validateLoPoCell(lo.code, po.code, loPoDraft[cellKey] ?? '');
      if (res.valid && res.numericValue >= 1 && res.numericValue <= 5) {
        loPoLinksByLo.get(lo.id)?.push({
          poId: po.id,
          poCode: po.code,
          weight: res.numericValue,
        });
        poLinksByPo.get(po.id)?.push({
          loId: lo.id,
          loCode: lo.code,
          weight: res.numericValue,
        });
      }
    }
  }

  const loDiagnostics: LiveLODiagnostic[] = [];
  const loStatusById = new Map<string, 'MAPPED' | 'UNMAPPED'>();
  const unmappedLOs: string[] = [];
  const orphanedLOs: string[] = [];

  for (const lo of version.learning_outcomes) {
    const totalAssessmentWeight = loTotalMap.get(lo.id) ?? 0;
    const status: 'MAPPED' | 'UNMAPPED' =
      totalAssessmentWeight > 0 ? 'MAPPED' : 'UNMAPPED';
    loStatusById.set(lo.id, status);
    const mappedPoCount = loPoLinksByLo.get(lo.id)?.length ?? 0;
    const isOrphan =
      (status === 'MAPPED' && mappedPoCount === 0) ||
      (status === 'UNMAPPED' && mappedPoCount > 0);

    if (status === 'UNMAPPED') {
      unmappedLOs.push(lo.code);
    }
    if (isOrphan) {
      orphanedLOs.push(lo.code);
    }
    loDiagnostics.push({
      id: lo.id,
      code: lo.code,
      status,
      totalAssessmentWeight,
      mappedPoCount,
      isOrphan,
    });
  }

  const poDiagnostics: LivePODiagnostic[] = [];
  const poTotalWeightById = new Map<string, number>();
  const unreachablePOs: string[] = [];
  const unassessedPOs: string[] = [];

  for (const po of programOutcomes) {
    const links = poLinksByPo.get(po.id) ?? [];
    const reachableLinks = links.filter(
      (link) => loStatusById.get(link.loId) === 'MAPPED',
    );
    const unreachableLinks = links.filter(
      (link) => loStatusById.get(link.loId) !== 'MAPPED',
    );

    if (reachableLinks.length > 0) {
      const totalLoWeight = reachableLinks.reduce(
        (sum, link) => sum + link.weight,
        0,
      );
      poTotalWeightById.set(po.id, totalLoWeight);
      poDiagnostics.push({
        id: po.id,
        code: po.code,
        status: 'ASSESSED',
        totalLoWeight,
      });
    } else if (unreachableLinks.length > 0) {
      poTotalWeightById.set(po.id, 0);
      unreachablePOs.push(po.code);
      poDiagnostics.push({
        id: po.id,
        code: po.code,
        status: 'UNREACHABLE',
        totalLoWeight: 0,
      });
    } else {
      poTotalWeightById.set(po.id, 0);
      unassessedPOs.push(po.code);
      poDiagnostics.push({
        id: po.id,
        code: po.code,
        status: 'NOT_ASSESSED',
        totalLoWeight: 0,
      });
    }
  }

  const traceabilityRows: TraceabilityPathRow[] = loDiagnostics.map((loDiag) => {
    const rawShares = loSharesMap.get(loDiag.id) ?? [];
    const totalW = loDiag.totalAssessmentWeight;
    const assessmentShares: TraceabilityAssessmentShare[] = rawShares.map(
      (share) => {
        const pct = totalW > 0 ? ((share.weight / totalW) * 100).toFixed(1) : '0.0';
        return {
          assessmentId: share.assessmentId,
          assessmentCode: share.assessmentCode,
          weight: share.weight,
          shareLabel: `${share.assessmentCode} (${formatWeightNumber(share.weight)}/${formatWeightNumber(totalW)}, ${pct}%)`,
        };
      },
    );

    const rawPoLinks = loPoLinksByLo.get(loDiag.id) ?? [];
    const poLinks: TraceabilityPOLink[] = rawPoLinks.map((link) => {
      const poTotal = poTotalWeightById.get(link.poId) ?? 0;
      const ratioPart =
        poTotal > 0 ? `${link.weight}/${poTotal}` : 'unreachable';
      return {
        poId: link.poId,
        poCode: link.poCode,
        weight: link.weight,
        poTotalWeight: poTotal,
        poShareLabel: `${link.poCode} (weight ${link.weight}, ${ratioPart})`,
      };
    });

    return {
      loId: loDiag.id,
      loCode: loDiag.code,
      loStatus: loDiag.status,
      isOrphan: loDiag.isOrphan,
      totalAssessmentWeight: totalW,
      assessmentShares,
      poLinks,
    };
  });

  return {
    aLoValidation,
    loPoValidation,
    allCellErrors,
    incompatibleVersion,
    incompatibleVersionMessage,
    loDiagnostics,
    poDiagnostics,
    unmappedLOs,
    orphanedLOs,
    unreachablePOs,
    unassessedPOs,
    traceabilityRows,
  };
}

export function getNextMatrixCellCoord(
  rowIndex: number,
  colIndex: number,
  rowCount: number,
  colCount: number,
  key: string,
): { rowIndex: number; colIndex: number } | null {
  if (rowCount <= 0 || colCount <= 0) return null;
  if (key === 'ArrowUp') {
    return { rowIndex: Math.max(0, rowIndex - 1), colIndex };
  }
  if (key === 'ArrowDown') {
    return { rowIndex: Math.min(rowCount - 1, rowIndex + 1), colIndex };
  }
  if (key === 'ArrowLeft') {
    return { rowIndex, colIndex: Math.max(0, colIndex - 1) };
  }
  if (key === 'ArrowRight') {
    return { rowIndex, colIndex: Math.min(colCount - 1, colIndex + 1) };
  }
  return null;
}

export function isVersionConflictError(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 409 || error.kind === 'conflict')
  );
}

export function SyllabusMappingStudio({
  version,
  canDraft,
  programId,
  activePoSetVersion,
  initialALoOverrides,
  initialLoPoOverrides,
  onSaved,
}: {
  version: Syllabus;
  canDraft: boolean;
  programId?: string;
  activePoSetVersion?: number | null;
  initialALoOverrides?: Record<string, string>;
  initialLoPoOverrides?: Record<string, string>;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const valKey = [
    'academic',
    'syllabus-mapping-validation',
    version.id,
    version.mapping_revision ?? 1,
  ];
  const validationQuery = useQuery({
    queryKey: valKey,
    queryFn: ({ signal }) => getSyllabusMappingValidation(version.id, signal),
  });
  const poSetsQuery = useQuery({
    queryKey: ['academic', 'po-sets', programId],
    queryFn: ({ signal }) => getProgramOutcomeSets(programId ?? '', signal),
    enabled: Boolean(programId) && activePoSetVersion === undefined,
  });

  const [aLoOverridesBySyllabus, setALoOverridesBySyllabus] = useState<
    Record<string, Record<string, string>>
  >(() => (initialALoOverrides ? { [version.id]: initialALoOverrides } : {}));
  const [loPoOverridesBySyllabus, setLoPoOverridesBySyllabus] = useState<
    Record<string, Record<string, string>>
  >(() => (initialLoPoOverrides ? { [version.id]: initialLoPoOverrides } : {}));

  const aLoBaseline = buildALoBaseline(version);
  const loPoBaseline = buildLoPoBaseline(version);
  const aLoOverrides = aLoOverridesBySyllabus[version.id] ?? {};
  const loPoOverrides = loPoOverridesBySyllabus[version.id] ?? {};

  const report = validationQuery.data;
  const programOutcomes: Array<{ id: string; code: string }> = (
    report?.po_statuses ?? []
  ).map((po) => ({
    id: po.program_outcome_id,
    code: po.code,
  }));

  const aLoDraft: Record<string, string> = {};
  let dirtyALoCount = 0;
  for (const assessment of version.assessments) {
    for (const lo of version.learning_outcomes) {
      const key = `${assessment.id}:${lo.id}`;
      const baseVal = aLoBaseline[key] ?? '';
      const val = key in aLoOverrides ? aLoOverrides[key] : baseVal;
      aLoDraft[key] = val;
      if (isALoCellDirty(val, baseVal)) {
        dirtyALoCount += 1;
      }
    }
  }

  const loPoDraft: Record<string, string> = {};
  let dirtyLoPoCount = 0;
  for (const lo of version.learning_outcomes) {
    for (const po of programOutcomes) {
      const key = `${lo.id}:${po.id}`;
      const baseVal = loPoBaseline[key] ?? '';
      const val = key in loPoOverrides ? loPoOverrides[key] : baseVal;
      loPoDraft[key] = val;
      if (isLoPoCellDirty(val, baseVal)) {
        dirtyLoPoCount += 1;
      }
    }
  }

  const resolvedActivePoSetVersion =
    activePoSetVersion !== undefined
      ? activePoSetVersion
      : poSetsQuery.data?.find((item) => item.active)?.version;

  const liveDiagnostics = computeLiveMappingDiagnostics({
    version,
    programOutcomes,
    aLoDraft,
    loPoDraft,
    activePoSetVersion: resolvedActivePoSetVersion,
  });

  const aLoMutation = useMutation({
    mutationFn: (
      mappings: Array<{
        assessment: string;
        learning_outcome: string;
        weight: string;
      }>,
    ) =>
      replaceAssessmentLOMappings(
        version.id,
        version.mapping_revision ?? 1,
        mappings,
      ),
    onSuccess: async () => {
      setALoOverridesBySyllabus((prev) => {
        const next = { ...prev };
        delete next[version.id];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: valKey });
      onSaved();
    },
  });

  const loPoMutation = useMutation({
    mutationFn: (
      mappings: Array<{
        learning_outcome: string;
        program_outcome: string;
        weight: number;
      }>,
    ) =>
      replaceLOPOMappings(version.id, version.mapping_revision ?? 1, mappings),
    onSuccess: async () => {
      setLoPoOverridesBySyllabus((prev) => {
        const next = { ...prev };
        delete next[version.id];
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: valKey });
      onSaved();
    },
  });

  const editable = canDraft && version.status === 'draft';
  const hasConflict =
    (aLoMutation.isError && isVersionConflictError(aLoMutation.error)) ||
    (loPoMutation.isError && isVersionConflictError(loPoMutation.error));
  const isSaving = aLoMutation.isPending || loPoMutation.isPending;
  const totalDirtyCount = dirtyALoCount + dirtyLoPoCount;

  const versionStateLabel =
    version.status === 'draft'
      ? canDraft
        ? 'Draft (editable)'
        : 'Draft (read-only)'
      : version.status === 'approved'
        ? 'Approved (locked / read-only)'
        : 'Retired (read-only)';

  const syncStateLabel = hasConflict
    ? 'Version conflict (409)'
    : isSaving
      ? 'Saving…'
      : totalDirtyCount > 0
        ? 'Unsaved changes'
        : `Saved (Revision v${version.mapping_revision ?? 1})`;

  const loDiagMap = new Map(
    liveDiagnostics.loDiagnostics.map((item) => [item.id, item]),
  );
  const poDiagMap = new Map(
    liveDiagnostics.poDiagnostics.map((item) => [item.id, item]),
  );

  function updateALoCell(cellKey: string, value: string) {
    setALoOverridesBySyllabus((prev) => ({
      ...prev,
      [version.id]: {
        ...(prev[version.id] ?? {}),
        [cellKey]: value,
      },
    }));
  }

  function updateLoPoCell(cellKey: string, value: string) {
    setLoPoOverridesBySyllabus((prev) => ({
      ...prev,
      [version.id]: {
        ...(prev[version.id] ?? {}),
        [cellKey]: value,
      },
    }));
  }

  function discardALoDraft() {
    setALoOverridesBySyllabus((prev) => {
      const next = { ...prev };
      delete next[version.id];
      return next;
    });
    aLoMutation.reset();
  }

  function discardLoPoDraft() {
    setLoPoOverridesBySyllabus((prev) => {
      const next = { ...prev };
      delete next[version.id];
      return next;
    });
    loPoMutation.reset();
  }

  function handleRefreshAfterConflict() {
    aLoMutation.reset();
    loPoMutation.reset();
    void queryClient.invalidateQueries({ queryKey: valKey });
    onSaved();
  }

  function handleMatrixKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
    prefix: 'alo' | 'lopo',
    rowIndex: number,
    colIndex: number,
    rowCount: number,
    colCount: number,
  ) {
    const { key } = event;
    if (
      key !== 'ArrowUp' &&
      key !== 'ArrowDown' &&
      key !== 'ArrowLeft' &&
      key !== 'ArrowRight'
    ) {
      return;
    }
    const input = event.currentTarget;
    if (
      !event.altKey &&
      !event.ctrlKey &&
      key === 'ArrowLeft' &&
      input.selectionStart !== null &&
      input.selectionStart > 0
    ) {
      return;
    }
    if (
      !event.altKey &&
      !event.ctrlKey &&
      key === 'ArrowRight' &&
      input.selectionEnd !== null &&
      input.selectionEnd < input.value.length
    ) {
      return;
    }
    const next = getNextMatrixCellCoord(
      rowIndex,
      colIndex,
      rowCount,
      colCount,
      key,
    );
    if (!next) return;
    event.preventDefault();
    const target = input
      .closest('table')
      ?.querySelector<HTMLElement>(
        `[data-matrix-cell="${prefix}-${next.rowIndex}-${next.colIndex}"]`,
      );
    target?.focus();
  }

  function submitALo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editable || !liveDiagnostics.aLoValidation.valid) return;
    aLoMutation.mutate(liveDiagnostics.aLoValidation.payload);
  }

  function submitLoPo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editable || !liveDiagnostics.loPoValidation.valid) return;
    loPoMutation.mutate(liveDiagnostics.loPoValidation.payload);
  }

  return (
    <section
      className="space-y-4 rounded border p-3"
      aria-label="Curriculum Mapping Matrices"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-medium">
          Curriculum mapping matrices (A→LO &amp; LO→PO)
        </h4>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={editable ? 'outline' : 'secondary'}>
            {versionStateLabel}
          </Badge>
          <Badge
            variant={
              hasConflict
                ? 'destructive'
                : totalDirtyCount > 0
                  ? 'secondary'
                  : 'outline'
            }
          >
            {syncStateLabel}
          </Badge>
          {liveDiagnostics.allCellErrors.length > 0 && (
            <Badge variant="destructive">
              INVALID_RANGE ({liveDiagnostics.allCellErrors.length})
            </Badge>
          )}
          {liveDiagnostics.incompatibleVersion && (
            <Badge variant="destructive">INCOMPATIBLE_VERSION</Badge>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Assessment→LO weights are nonnegative relative values (no sum-to-100
        constraint). Active LO→PO links carry integer weights 1–5 (or 0 for
        unmapped); unmapped LOs are UNMAPPED and unassessed POs are NOT_ASSESSED
        (never numeric zero). Use arrow keys to navigate between matrix cells.
      </p>

      {version.status === 'approved' && (
        <Alert>
          <AlertDescription>
            <strong>Locked / Read-Only:</strong> Approved syllabus versions are
            immutable to preserve historical evidence. Click{' '}
            <strong>Create revision</strong> above to start a new editable draft
            version.
          </AlertDescription>
        </Alert>
      )}

      {!canDraft && version.status === 'draft' && (
        <Alert>
          <AlertDescription>
            <strong>Read-Only:</strong> You do not have drafting permission to
            edit mapping matrices for this offering.
          </AlertDescription>
        </Alert>
      )}

      {liveDiagnostics.incompatibleVersion &&
        liveDiagnostics.incompatibleVersionMessage && (
          <div role="alert" className="rounded border border-destructive p-3 text-sm">
            <p className="font-medium">INCOMPATIBLE_VERSION</p>
            <p>{liveDiagnostics.incompatibleVersionMessage}</p>
          </div>
        )}

      {hasConflict && (
        <div
          role="alert"
          className="space-y-2 rounded border border-destructive p-3 text-sm"
        >
          <p className="font-medium">Version conflict (409)</p>
          <p>
            Another user saved a newer mapping revision on the server. Your
            unsaved draft edits have been preserved below. Refresh server
            mappings to load the latest revision before re-applying your
            changes.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleRefreshAfterConflict}
          >
            Refresh server mappings
          </Button>
        </div>
      )}

      {liveDiagnostics.allCellErrors.length > 0 && (
        <div
          role="alert"
          className="space-y-1 rounded border border-destructive p-3 text-sm"
        >
          <p className="font-medium">
            Mapping validation errors ({liveDiagnostics.allCellErrors.length})
          </p>
          <ul className="list-disc space-y-1 pl-5">
            {liveDiagnostics.allCellErrors.map((err) => (
              <li key={`${err.matrix}-${err.cellKey}`}>{err.message}</li>
            ))}
          </ul>
        </div>
      )}

      {validationQuery.isPending && (
        <p role="status">Validating mapping matrices…</p>
      )}
      {validationQuery.isError && (
        <p role="alert">{errorMessage(validationQuery.error)}</p>
      )}
      {aLoMutation.isError && !isVersionConflictError(aLoMutation.error) && (
        <p role="alert">{errorMessage(aLoMutation.error)}</p>
      )}
      {loPoMutation.isError && !isVersionConflictError(loPoMutation.error) && (
        <p role="alert">{errorMessage(loPoMutation.error)}</p>
      )}

      {version.assessments.length > 0 &&
      version.learning_outcomes.length > 0 ? (
        <form onSubmit={submitALo} className="space-y-3" noValidate>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h5 className="text-sm font-medium">
              1. Assessment → Learning Outcome (A→LO) relative weights
            </h5>
            {dirtyALoCount > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">
                  Unsaved A→LO changes ({dirtyALoCount} cells)
                </Badge>
                {editable && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={discardALoDraft}
                    disabled={aLoMutation.isPending}
                  >
                    Discard unsaved changes
                  </Button>
                )}
              </div>
            )}
          </div>
          <Table>
            <TableCaption>
              Assessment to Learning Outcome (A→LO) relative weight matrix
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Assessment</TableHead>
                {version.learning_outcomes.map((lo) => {
                  const diag = loDiagMap.get(lo.id);
                  return (
                    <TableHead key={lo.id} scope="col">
                      <div className="flex flex-col gap-1">
                        <span>{lo.code}</span>
                        {diag && (
                          <div className="flex flex-wrap gap-1">
                            <Badge
                              variant={
                                diag.status === 'MAPPED'
                                  ? 'outline'
                                  : 'secondary'
                              }
                            >
                              {diag.status === 'MAPPED'
                                ? `MAPPED (Σ=${formatWeightNumber(diag.totalAssessmentWeight)})`
                                : 'UNMAPPED'}
                            </Badge>
                            {diag.isOrphan && (
                              <Badge variant="secondary">ORPHAN</Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </TableHead>
                  );
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {version.assessments.map((assessment, rowIndex) => (
                <TableRow key={assessment.id}>
                  <th
                    scope="row"
                    className="p-2 text-left align-middle font-medium whitespace-nowrap"
                  >
                    {assessment.code}{' '}
                    <span className="text-xs font-normal text-muted-foreground">
                      ({assessment.max_points} pts
                      {assessment.is_active ? '' : ', inactive'})
                    </span>
                  </th>
                  {version.learning_outcomes.map((lo, colIndex) => {
                    const cellKey = `${assessment.id}:${lo.id}`;
                    const value = aLoDraft[cellKey] ?? '';
                    const cellError =
                      liveDiagnostics.aLoValidation.errorByCell[cellKey];
                    const errorId = `alo-err-${version.id}-${assessment.id}-${lo.id}`;
                    return (
                      <TableCell key={lo.id}>
                        {editable ? (
                          <div>
                            <Input
                              aria-label={`Assessment ${assessment.code} to ${lo.code} relative weight`}
                              aria-invalid={cellError ? 'true' : undefined}
                              aria-describedby={cellError ? errorId : undefined}
                              data-matrix-cell={`alo-${rowIndex}-${colIndex}`}
                              name={`alo_${assessment.id}_${lo.id}`}
                              type="text"
                              inputMode="decimal"
                              placeholder="0"
                              value={value}
                              onChange={(event) =>
                                updateALoCell(cellKey, event.target.value)
                              }
                              onKeyDown={(event) =>
                                handleMatrixKeyDown(
                                  event,
                                  'alo',
                                  rowIndex,
                                  colIndex,
                                  version.assessments.length,
                                  version.learning_outcomes.length,
                                )
                              }
                              className="w-24"
                            />
                            {cellError && (
                              <p
                                id={errorId}
                                className="mt-1 text-xs text-destructive"
                              >
                                {cellError.message}
                              </p>
                            )}
                          </div>
                        ) : (
                          <span>
                            {value.trim() !== '' && Number(value) > 0
                              ? value
                              : '—'}
                          </span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {editable && (
            <Button
              type="submit"
              disabled={
                aLoMutation.isPending || !liveDiagnostics.aLoValidation.valid
              }
            >
              {aLoMutation.isPending ? 'Saving…' : 'Save A→LO matrix'}
            </Button>
          )}
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">
          Add at least one learning outcome and one assessment to configure the
          A→LO matrix.
        </p>
      )}

      {version.learning_outcomes.length > 0 && programOutcomes.length > 0 ? (
        <form
          onSubmit={submitLoPo}
          className="space-y-3 border-t pt-3"
          noValidate
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h5 className="text-sm font-medium">
              2. Learning Outcome → Program Outcome (LO→PO) integer weights
              (1–5)
            </h5>
            {dirtyLoPoCount > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">
                  Unsaved LO→PO changes ({dirtyLoPoCount} cells)
                </Badge>
                {editable && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={discardLoPoDraft}
                    disabled={loPoMutation.isPending}
                  >
                    Discard unsaved changes
                  </Button>
                )}
              </div>
            )}
          </div>
          <Table>
            <TableCaption>
              Learning Outcome to Program Outcome (LO→PO) integer weight matrix
              (1 to 5, or 0 for unmapped)
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Learning Outcome</TableHead>
                {programOutcomes.map((po) => {
                  const diag = poDiagMap.get(po.id);
                  return (
                    <TableHead key={po.id} scope="col">
                      <div className="flex flex-col gap-1">
                        <span>{po.code}</span>
                        {diag && (
                          <Badge
                            variant={
                              diag.status === 'ASSESSED'
                                ? 'outline'
                                : diag.status === 'UNREACHABLE'
                                  ? 'destructive'
                                  : 'secondary'
                            }
                          >
                            {diag.status === 'ASSESSED'
                              ? `ASSESSED (Σ=${diag.totalLoWeight})`
                              : diag.status}
                          </Badge>
                        )}
                      </div>
                    </TableHead>
                  );
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {version.learning_outcomes.map((lo, rowIndex) => {
                const loDiag = loDiagMap.get(lo.id);
                return (
                  <TableRow key={lo.id}>
                    <th
                      scope="row"
                      className="p-2 text-left align-middle font-medium whitespace-nowrap"
                    >
                      <div className="flex flex-wrap items-center gap-1">
                        <span>{lo.code}</span>
                        {loDiag?.isOrphan && (
                          <Badge variant="secondary">ORPHAN</Badge>
                        )}
                      </div>
                    </th>
                    {programOutcomes.map((po, colIndex) => {
                      const cellKey = `${lo.id}:${po.id}`;
                      const value = loPoDraft[cellKey] ?? '';
                      const cellError =
                        liveDiagnostics.loPoValidation.errorByCell[cellKey];
                      const errorId = `lopo-err-${version.id}-${lo.id}-${po.id}`;
                      return (
                        <TableCell key={po.id}>
                          {editable ? (
                            <div>
                              <Input
                                aria-label={`${lo.code} to ${po.code} integer weight (1 to 5, or 0 for unmapped)`}
                                aria-invalid={cellError ? 'true' : undefined}
                                aria-describedby={
                                  cellError ? errorId : undefined
                                }
                                data-matrix-cell={`lopo-${rowIndex}-${colIndex}`}
                                name={`lopo_${lo.id}_${po.id}`}
                                type="text"
                                inputMode="numeric"
                                placeholder="0"
                                value={value}
                                onChange={(event) =>
                                  updateLoPoCell(cellKey, event.target.value)
                                }
                                onKeyDown={(event) =>
                                  handleMatrixKeyDown(
                                    event,
                                    'lopo',
                                    rowIndex,
                                    colIndex,
                                    version.learning_outcomes.length,
                                    programOutcomes.length,
                                  )
                                }
                                className="w-20"
                              />
                              {cellError && (
                                <p
                                  id={errorId}
                                  className="mt-1 text-xs text-destructive"
                                >
                                  {cellError.message}
                                </p>
                              )}
                            </div>
                          ) : (
                            <span>
                              {value.trim() !== '' && Number(value) >= 1
                                ? value
                                : '—'}
                            </span>
                          )}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          {editable && (
            <Button
              type="submit"
              disabled={
                loPoMutation.isPending || !liveDiagnostics.loPoValidation.valid
              }
            >
              {loPoMutation.isPending ? 'Saving…' : 'Save LO→PO matrix'}
            </Button>
          )}
        </form>
      ) : null}

      {liveDiagnostics.traceabilityRows.length > 0 && (
        <div
          className="space-y-2 border-t pt-3"
          aria-label="Equivalent traceability summary table"
        >
          <h5 className="text-sm font-medium">
            3. Equivalent Assessment → LO → PO traceability summary
          </h5>
          <Table>
            <TableCaption>
              Equivalent textual summary of active Assessment to Learning
              Outcome to Program Outcome traceability paths
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Learning Outcome</TableHead>
                <TableHead scope="col">A→LO Relative Shares</TableHead>
                <TableHead scope="col">LO→PO Weights</TableHead>
                <TableHead scope="col">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {liveDiagnostics.traceabilityRows.map((row) => (
                <TableRow key={row.loId}>
                  <th
                    scope="row"
                    className="p-2 text-left align-middle font-medium whitespace-nowrap"
                  >
                    {row.loCode}
                  </th>
                  <TableCell>
                    {row.assessmentShares.length > 0
                      ? row.assessmentShares
                          .map((share) => share.shareLabel)
                          .join(' + ')
                      : 'None (UNMAPPED)'}
                  </TableCell>
                  <TableCell>
                    {row.poLinks.length > 0
                      ? row.poLinks.map((link) => link.poShareLabel).join(', ')
                      : 'None (NOT_ASSESSED)'}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      <Badge
                        variant={
                          row.loStatus === 'MAPPED' ? 'outline' : 'secondary'
                        }
                      >
                        {row.loStatus === 'MAPPED'
                          ? `MAPPED (Σ=${formatWeightNumber(row.totalAssessmentWeight)})`
                          : 'UNMAPPED'}
                      </Badge>
                      {row.isOrphan && (
                        <Badge variant="secondary">ORPHAN</Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div
        className="space-y-2 border-t pt-3 text-sm"
        aria-label="Mapping diagnostics"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">Live draft diagnostics:</span>
          {liveDiagnostics.unmappedLOs.length > 0 && (
            <Badge variant="secondary">
              UNMAPPED: {liveDiagnostics.unmappedLOs.join(', ')}
            </Badge>
          )}
          {liveDiagnostics.orphanedLOs.length > 0 && (
            <Badge variant="secondary">
              ORPHAN: {liveDiagnostics.orphanedLOs.join(', ')}
            </Badge>
          )}
          {liveDiagnostics.unreachablePOs.length > 0 && (
            <Badge variant="destructive">
              UNREACHABLE: {liveDiagnostics.unreachablePOs.join(', ')}
            </Badge>
          )}
          {liveDiagnostics.unassessedPOs.length > 0 && (
            <Badge variant="secondary">
              NOT_ASSESSED: {liveDiagnostics.unassessedPOs.join(', ')}
            </Badge>
          )}
          {liveDiagnostics.unmappedLOs.length === 0 &&
            liveDiagnostics.orphanedLOs.length === 0 &&
            liveDiagnostics.unreachablePOs.length === 0 &&
            !liveDiagnostics.incompatibleVersion &&
            liveDiagnostics.allCellErrors.length === 0 && (
              <Badge variant="outline">Draft paths valid</Badge>
            )}
        </div>

        {report && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">Server pre-approval readiness:</span>
              <Badge
                variant={report.is_valid_for_approval ? 'outline' : 'secondary'}
              >
                {report.is_valid_for_approval
                  ? 'Ready for approval'
                  : 'Issues detected'}
              </Badge>
            </div>
            {report.errors.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm" role="alert">
                {report.errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export function SyllabusWorkspace({
  offering,
  programId,
  canDraft,
  canApprove,
}: {
  offering: string;
  programId?: string;
  canDraft: boolean;
  canApprove: boolean;
}) {
  const queryClient = useQueryClient();
  const key = ['academic', 'syllabi', offering];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getSyllabi(offering, signal),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body?: object;
      method?: string;
    }) => changeSyllabus(path, body, method),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const versions = query.data ?? [];
  const version: Syllabus | undefined =
    versions.find((item) => item.id === selected) ??
    versions.find((item) => item.status === 'draft') ??
    versions.find((item) => item.status === 'approved') ??
    versions.at(-1);
  const run = (path: string, body?: object, method?: string) =>
    mutation.mutate({ path, body, method });
  return (
    <section className="mt-5 space-y-4 border-t pt-4" aria-label="Syllabus">
      <h3 className="font-semibold">Syllabus</h3>
      {query.isPending && <p role="status">Loading syllabus versions…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {mutation.isPending && <p role="status">Saving changes…</p>}
      {query.isSuccess && !versions.length && <p>No syllabus versions yet.</p>}
      {query.isSuccess &&
        canDraft &&
        !versions.some(
          (item) => item.status === 'draft' || item.status === 'approved',
        ) && (
          <Button
            disabled={mutation.isPending}
            onClick={() => run('', { offering })}
          >
            Create draft
          </Button>
        )}
      {version && (
        <>
          <label className="block">
            Version{' '}
            <NativeSelect
              value={version.id}
              onChange={(event) => setSelected(event.target.value)}
            >
              {versions.map((item) => (
                <option key={item.id} value={item.id}>
                  Version {item.version} · {item.status}
                </option>
              ))}
            </NativeSelect>
          </label>
          <p className="text-sm">
            {version.status === 'approved'
              ? `Approved ${version.approved_at ? new Date(version.approved_at).toLocaleString() : ''}`
              : version.status === 'draft'
                ? 'Draft — changes are editable until approval.'
                : 'Retired — preserved for history.'}{' '}
            {version.po_set_version !== null &&
              `PO set version ${version.po_set_version}.`}
          </p>
          {canDraft && version.status === 'draft' && (
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => run(`${version.id}/bind-active-po-set/`)}
            >
              Bind active outcome set
            </Button>
          )}
          {canApprove && version.status === 'draft' && (
            <Button
              disabled={mutation.isPending}
              onClick={() => run(`${version.id}/approve/`)}
            >
              Approve syllabus
            </Button>
          )}
          {canDraft &&
            version.status === 'approved' &&
            !versions.some((item) => item.status === 'draft') && (
              <Button
                disabled={mutation.isPending}
                onClick={() => {
                  setSelected(null);
                  run(`${version.id}/revise/`);
                }}
              >
                Create revision
              </Button>
            )}
          {canDraft &&
            version.status === 'draft' &&
            version.learning_outcomes.length === 0 &&
            version.assessments.length === 0 &&
            (version.po_contributions?.length ?? 0) === 0 &&
            (version.assessment_lo_mappings?.length ?? 0) === 0 &&
            (version.lo_po_mappings?.length ?? 0) === 0 && (
              <Button
                variant="outline"
                disabled={mutation.isPending}
                onClick={() => run(`${version.id}/retire/`)}
              >
                Retire empty draft
              </Button>
            )}
          <section className="space-y-3">
            <h4 className="font-medium">Learning outcomes</h4>
            {!version.learning_outcomes.length && (
              <p>No learning outcomes yet.</p>
            )}
            {version.learning_outcomes.map((item) =>
              canDraft && version.status === 'draft' ? (
                <OutcomeForm
                  key={item.id}
                  value={item}
                  pending={mutation.isPending}
                  save={(data) =>
                    run(
                      `${version.id}/learning-outcomes/${item.id}/`,
                      data,
                      'PATCH',
                    )
                  }
                />
              ) : (
                <p key={item.id}>
                  {item.order}. {item.code}: {item.description}
                </p>
              ),
            )}
            {canDraft && version.status === 'draft' && (
              <OutcomeForm
                key={`${version.id}-new-outcome`}
                pending={mutation.isPending}
                save={(data) => run(`${version.id}/learning-outcomes/`, data)}
              />
            )}
          </section>
          <section className="space-y-3">
            <h4 className="font-medium">Assessments</h4>
            {!version.assessments.length && <p>No assessments yet.</p>}
            {version.assessments.map((item) =>
              canDraft && version.status === 'draft' ? (
                <AssessmentForm
                  key={item.id}
                  value={item}
                  pending={mutation.isPending}
                  save={(data) =>
                    run(`${version.id}/assessments/${item.id}/`, data, 'PATCH')
                  }
                />
              ) : (
                <p key={item.id}>
                  {item.order}. {item.code} · {item.kind} · {item.max_points}{' '}
                  points · {item.is_required ? 'required' : 'optional'} ·{' '}
                  {item.is_active ? 'active' : 'inactive'}
                </p>
              ),
            )}
            {canDraft && version.status === 'draft' && (
              <AssessmentForm
                key={`${version.id}-new-assessment`}
                pending={mutation.isPending}
                save={(data) => run(`${version.id}/assessments/`, data)}
              />
            )}
          </section>

          <CoursePOContributionSection
            syllabus={version}
            programId={programId}
            canApprove={canApprove}
            onChanged={() => void queryClient.invalidateQueries({ queryKey: key })}
          />
          <SyllabusMappingStudio
            version={version}
            canDraft={canDraft}
            programId={programId}
            onSaved={() => void queryClient.invalidateQueries({ queryKey: key })}
          />
        </>
      )}
    </section>
  );
}

export function ProgramOutcomeSets({ program }: { program: string }) {
  const client = useQueryClient();
  const key = ['academic', 'po-sets', program];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getProgramOutcomeSets(program, signal),
  });
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) =>
      changeProgramOutcomeSet(path, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      path: '',
      body: {
        program,
        version: Number(data.get('version')),
        effective_date: data.get('effective_date'),
        source_reference: data.get('source_reference'),
      },
    });
  }
  return (
    <section className="space-y-3">
      <h3 className="font-medium">Program outcome sets</h3>
      {query.isPending && <p role="status">Loading outcome sets…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {query.data?.length === 0 && (
        <p>
          No outcome sets yet. An active set is required to create a syllabus.
        </p>
      )}
      {query.data?.map((set) => (
        <OutcomeSetEditor
          key={set.id}
          set={set}
          onActivated={() => client.invalidateQueries({ queryKey: key })}
        />
      ))}
      <form onSubmit={create} className="space-y-3 rounded border p-3">
        <h4 className="font-medium">Register outcome set</h4>
        <FieldGroup>
          <Field>
            <FieldLabel>
              Version
              <Input name="version" type="number" min="1" required />
            </FieldLabel>
          </Field>
          <Field>
            <FieldLabel>
              Effective date
              <Input name="effective_date" type="date" required />
            </FieldLabel>
          </Field>
          <Field>
            <FieldLabel>
              Source reference
              <Input name="source_reference" required />
            </FieldLabel>
          </Field>
        </FieldGroup>
        <Button type="submit" disabled={mutation.isPending}>
          Register outcome set
        </Button>
      </form>
    </section>
  );
}

function OutcomeSetEditor({
  set,
  onActivated,
}: {
  set: ProgramOutcomeSet;
  onActivated: () => void;
}) {
  const client = useQueryClient();
  const key = ['academic', 'po-set-outcomes', set.id];
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getProgramOutcomes(set.id, signal),
  });
  const mutation = useMutation({
    mutationFn: ({
      path,
      body,
      method,
    }: {
      path: string;
      body?: object;
      method?: string;
    }) => changeProgramOutcomeSet(path, body, method),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: key });
      onActivated();
    },
  });
  const missing = Array.from({ length: 11 }, (_, i) => i + 1).filter(
    (number) => !query.data?.some((outcome) => outcome.code === `PO${number}`),
  );
  function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const order = Number(data.get('order'));
    mutation.mutate(
      {
        path: `${set.id}/outcomes/`,
        body: {
          code: `PO${order}`,
          order,
          label: data.get('label'),
          description: data.get('description'),
          source_reference: data.get('source_reference'),
        },
      },
      { onSuccess: () => form.reset() },
    );
  }
  return (
    <section
      className="space-y-3 rounded border p-3"
      aria-label={`Outcome set version ${set.version}`}
    >
      <h4 className="font-medium">
        Version {set.version} ·{' '}
        {set.active ? 'active' : set.activated_at ? 'retired' : 'draft'}
      </h4>
      <p>
        {set.effective_date} · {set.source_reference}
      </p>
      {query.isPending && <p role="status">Loading outcome definitions…</p>}
      {query.isError && <p role="alert">{errorMessage(query.error)}</p>}
      {mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}
      {query.data && (
        <>
          <p>{query.data.length} of 11 outcome definitions</p>
          <ul>
            {query.data.map((outcome) => (
              <li key={outcome.id}>
                {set.activated_at ? (
                  <p>
                    {outcome.code}: {outcome.label} — {outcome.description} (
                    {outcome.source_reference})
                  </p>
                ) : (
                  <form
                    className="space-y-2 border-b py-3"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const data = new FormData(event.currentTarget);
                      mutation.mutate({
                        path: `${set.id}/outcomes/${outcome.id}/`,
                        method: 'PATCH',
                        body: {
                          label: data.get('label'),
                          description: data.get('description'),
                          source_reference: data.get('source_reference'),
                        },
                      });
                    }}
                  >
                    <h5 className="font-medium">Edit {outcome.code}</h5>
                    <FieldGroup>
                      <Field>
                        <FieldLabel>
                          Label
                          <Input
                            name="label"
                            defaultValue={outcome.label}
                            required
                          />
                        </FieldLabel>
                      </Field>
                      <Field>
                        <FieldLabel>
                          Description
                          <Input
                            name="description"
                            defaultValue={outcome.description}
                            required
                          />
                        </FieldLabel>
                      </Field>
                      <Field>
                        <FieldLabel>
                          Source reference
                          <Input
                            name="source_reference"
                            defaultValue={outcome.source_reference}
                            required
                          />
                        </FieldLabel>
                      </Field>
                    </FieldGroup>
                    <Button type="submit" disabled={mutation.isPending}>
                      Save {outcome.code}
                    </Button>
                  </form>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {query.data && !set.activated_at && missing.length > 0 && (
        <form onSubmit={add} className="space-y-3">
          <h5 className="font-medium">Add outcome definition</h5>
          <FieldGroup>
            <Field>
              <FieldLabel>
                Outcome
                <NativeSelect name="order">
                  {missing.map((number) => (
                    <option key={number} value={number}>
                      PO{number}
                    </option>
                  ))}
                </NativeSelect>
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Label
                <Input name="label" required />
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Description
                <Input name="description" required />
              </FieldLabel>
            </Field>
            <Field>
              <FieldLabel>
                Source reference
                <Input name="source_reference" required />
              </FieldLabel>
            </Field>
          </FieldGroup>
          <Button type="submit" disabled={mutation.isPending}>
            Add definition
          </Button>
        </form>
      )}
      {query.data && !set.activated_at && missing.length === 0 && (
        <Button
          variant="outline"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ path: `${set.id}/activate/` })}
        >
          Activate version {set.version}
        </Button>
      )}
    </section>
  );
}
