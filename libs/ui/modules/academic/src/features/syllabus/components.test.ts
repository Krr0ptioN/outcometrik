import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';

const mockState = vi.hoisted(() => ({
  validation: {} as Record<string, unknown>,
  poSets: {} as Record<string, unknown>,
  aLoMutation: {
    isPending: false,
    isError: false,
    error: null as unknown,
    mutate: vi.fn(),
    reset: vi.fn(),
  },
  loPoMutation: {
    isPending: false,
    isError: false,
    error: null as unknown,
    mutate: vi.fn(),
    reset: vi.fn(),
  },
  mutationCallIndex: 0,
}));

vi.mock('@outcometrik/access', () => ({
  errorMessage: (err: unknown) =>
    err instanceof Error ? err.message : 'The request failed',
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: unknown[] }) =>
    queryKey[1] === 'po-sets' ? mockState.poSets : mockState.validation,
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
  useMutation: () => {
    const idx = mockState.mutationCallIndex % 2;
    mockState.mutationCallIndex += 1;
    return idx === 0 ? mockState.aLoMutation : mockState.loPoMutation;
  },
}));

import type { Syllabus, SyllabusMappingValidation } from './api';
import {
  buildALoBaseline,
  buildLoPoBaseline,
  computeLiveMappingDiagnostics,
  getNextMatrixCellCoord,
  isALoCellDirty,
  isLoPoCellDirty,
  isVersionConflictError,
  SyllabusMappingStudio,
  validateALoCell,
  validateALoMatrix,
  validateLoPoCell,
  validateLoPoMatrix,
} from './components';

const prdSyllabus: Syllabus = {
  id: 'syl-1',
  offering: 'off-1',
  version: 1,
  status: 'draft',
  approved_at: null,
  po_set_version: 1,
  mapping_revision: 3,
  learning_outcomes: [
    { id: 'lo1', code: 'LO1', description: 'Analyze algorithms', order: 1 },
    { id: 'lo2', code: 'LO2', description: 'Implement data structures', order: 2 },
  ],
  assessments: [
    {
      id: 'a1',
      code: 'A1',
      kind: 'exam',
      order: 1,
      is_required: true,
      is_active: true,
      max_points: '100.00',
    },
    {
      id: 'a2',
      code: 'A2',
      kind: 'project',
      order: 2,
      is_required: true,
      is_active: true,
      max_points: '100.00',
    },
  ],
  assessment_lo_mappings: [
    { assessment: 'a1', learning_outcome: 'lo1', weight: '60', is_active: true },
    { assessment: 'a2', learning_outcome: 'lo1', weight: '40', is_active: true },
    { assessment: 'a1', learning_outcome: 'lo2', weight: '40', is_active: true },
    { assessment: 'a2', learning_outcome: 'lo2', weight: '100', is_active: true },
  ],
  lo_po_mappings: [
    { learning_outcome: 'lo1', program_outcome: 'po1', weight: 2, is_active: true },
    { learning_outcome: 'lo2', program_outcome: 'po1', weight: 1, is_active: true },
    { learning_outcome: 'lo2', program_outcome: 'po2', weight: 1, is_active: true },
  ],
};

const prdValidationReport: SyllabusMappingValidation = {
  syllabus_id: 'syl-1',
  mapping_revision: 3,
  is_valid_for_approval: true,
  lo_statuses: [
    {
      learning_outcome_id: 'lo1',
      code: 'LO1',
      status: 'MAPPED',
      total_assessment_weight: '100.00',
      mapped_po_count: 1,
    },
    {
      learning_outcome_id: 'lo2',
      code: 'LO2',
      status: 'MAPPED',
      total_assessment_weight: '140.00',
      mapped_po_count: 2,
    },
  ],
  po_statuses: [
    {
      program_outcome_id: 'po1',
      code: 'PO1',
      status: 'ASSESSED',
      total_lo_weight: 3,
    },
    {
      program_outcome_id: 'po2',
      code: 'PO2',
      status: 'ASSESSED',
      total_lo_weight: 1,
    },
    {
      program_outcome_id: 'po3',
      code: 'PO3',
      status: 'NOT_ASSESSED',
      total_lo_weight: 0,
    },
  ],
  unmapped_learning_outcomes: [],
  orphaned_learning_outcomes: [],
  unreachable_program_outcomes: [],
  errors: [],
};

beforeEach(() => {
  mockState.mutationCallIndex = 0;
  mockState.validation = {
    isPending: false,
    isError: false,
    data: prdValidationReport,
  };
  mockState.poSets = {
    isPending: false,
    isError: false,
    data: [{ id: 'set-1', version: 1, active: true }],
  };
  mockState.aLoMutation = {
    isPending: false,
    isError: false,
    error: null,
    mutate: vi.fn(),
    reset: vi.fn(),
  };
  mockState.loPoMutation = {
    isPending: false,
    isError: false,
    error: null,
    mutate: vi.fn(),
    reset: vi.fn(),
  };
});

describe('UI-01 SyllabusMappingStudio', () => {
  it('validates the PRD mapping example (60/40 and 40/100 A→LO; 2:1 and 1 LO→PO) and builds atomic payloads', () => {
    const aLoDraft = buildALoBaseline(prdSyllabus);
    const loPoDraft = buildLoPoBaseline(prdSyllabus);

    const aLoRes = validateALoMatrix(
      prdSyllabus.assessments,
      prdSyllabus.learning_outcomes,
      aLoDraft,
    );
    expect(aLoRes.valid).toBe(true);
    expect(aLoRes.errors).toEqual([]);
    expect(aLoRes.payload).toEqual([
      { assessment: 'a1', learning_outcome: 'lo1', weight: '60' },
      { assessment: 'a1', learning_outcome: 'lo2', weight: '40' },
      { assessment: 'a2', learning_outcome: 'lo1', weight: '40' },
      { assessment: 'a2', learning_outcome: 'lo2', weight: '100' },
    ]);

    const poList = prdValidationReport.po_statuses.map((po) => ({
      id: po.program_outcome_id,
      code: po.code,
    }));
    const loPoRes = validateLoPoMatrix(
      prdSyllabus.learning_outcomes,
      poList,
      loPoDraft,
    );
    expect(loPoRes.valid).toBe(true);
    expect(loPoRes.errors).toEqual([]);
    expect(loPoRes.payload).toEqual([
      { learning_outcome: 'lo1', program_outcome: 'po1', weight: 2 },
      { learning_outcome: 'lo2', program_outcome: 'po1', weight: 1 },
      { learning_outcome: 'lo2', program_outcome: 'po2', weight: 1 },
    ]);

    const diagnostics = computeLiveMappingDiagnostics({
      version: prdSyllabus,
      programOutcomes: poList,
      aLoDraft,
      loPoDraft,
      activePoSetVersion: 1,
    });

    expect(diagnostics.allCellErrors).toEqual([]);
    expect(diagnostics.incompatibleVersion).toBe(false);
    expect(diagnostics.unmappedLOs).toEqual([]);
    expect(diagnostics.orphanedLOs).toEqual([]);
    expect(diagnostics.unreachablePOs).toEqual([]);
    expect(diagnostics.unassessedPOs).toEqual(['PO3']);

    // Verify PRD relative shares and 2:1 / 1 ratios in traceability summary
    expect(diagnostics.traceabilityRows[0]).toMatchObject({
      loCode: 'LO1',
      loStatus: 'MAPPED',
      totalAssessmentWeight: 100,
    });
    expect(
      diagnostics.traceabilityRows[0].assessmentShares.map((s) => s.shareLabel),
    ).toEqual(['A1 (60/100, 60.0%)', 'A2 (40/100, 40.0%)']);
    expect(
      diagnostics.traceabilityRows[0].poLinks.map((l) => l.poShareLabel),
    ).toEqual(['PO1 (weight 2, 2/3)']);

    expect(diagnostics.traceabilityRows[1]).toMatchObject({
      loCode: 'LO2',
      loStatus: 'MAPPED',
      totalAssessmentWeight: 140,
    });
    expect(
      diagnostics.traceabilityRows[1].assessmentShares.map((s) => s.shareLabel),
    ).toEqual(['A1 (40/140, 28.6%)', 'A2 (100/140, 71.4%)']);
    expect(
      diagnostics.traceabilityRows[1].poLinks.map((l) => l.poShareLabel),
    ).toEqual(['PO1 (weight 1, 1/3)', 'PO2 (weight 1, 1/1)']);

    const markup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: prdSyllabus,
        canDraft: true,
        activePoSetVersion: 1,
        onSaved: vi.fn(),
      }),
    );
    expect(markup).toContain('Draft (editable)');
    expect(markup).toContain('Saved (Revision v3)');
    expect(markup).toContain('MAPPED (Σ=100)');
    expect(markup).toContain('MAPPED (Σ=140)');
    expect(markup).toContain('ASSESSED (Σ=3)');
    expect(markup).toContain('ASSESSED (Σ=1)');
    expect(markup).toContain('NOT_ASSESSED');
    expect(markup).toContain('A1 (60/100, 60.0%) + A2 (40/100, 40.0%)');
    expect(markup).toContain('A1 (40/140, 28.6%) + A2 (100/140, 71.4%)');
    expect(markup).toContain('PO1 (weight 2, 2/3)');
    expect(markup).toContain('PO1 (weight 1, 1/3), PO2 (weight 1, 1/1)');
  });

  it('reports exact cell coordinates and rules for invalid A→LO and LO→PO weights and sets aria-invalid', () => {
    expect(validateALoCell('MID1', 'LO1', '-10')).toEqual({
      valid: false,
      numericValue: Number.NaN,
      error:
        'Cell [MID1 → LO1]: A→LO weight must be a nonnegative number (>= 0).',
    });
    expect(validateALoCell('MID1', 'LO1', 'abc').valid).toBe(false);
    expect(validateALoCell('MID1', 'LO1', '').numericValue).toBe(0);
    expect(validateALoCell('MID1', 'LO1', '0').numericValue).toBe(0);

    for (const bad of ['2.5', '-1', '6', 'abc']) {
      expect(validateLoPoCell('LO1', 'PO1', bad)).toEqual({
        valid: false,
        numericValue: Number.NaN,
        error:
          'Cell [LO1 → PO1]: LO→PO weight must be an integer from 1 to 5 (or 0 for unmapped).',
      });
    }
    expect(validateLoPoCell('LO1', 'PO1', '0')).toEqual({
      valid: true,
      numericValue: 0,
      error: null,
    });
    expect(validateLoPoCell('LO1', 'PO1', '5')).toEqual({
      valid: true,
      numericValue: 5,
      error: null,
    });

    const markup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: {
          ...prdSyllabus,
          assessments: [
            { ...prdSyllabus.assessments[0], code: 'MID1' },
            prdSyllabus.assessments[1],
          ],
        },
        canDraft: true,
        activePoSetVersion: 1,
        initialALoOverrides: { 'a1:lo1': '-10' },
        initialLoPoOverrides: { 'lo1:po1': '2.5' },
        onSaved: vi.fn(),
      }),
    );

    expect(markup).toContain('INVALID_RANGE (2)');
    expect(markup).toContain('Unsaved A→LO changes (1 cells)');
    expect(markup).toContain('Unsaved LO→PO changes (1 cells)');
    expect(markup).toContain('Discard unsaved changes');
    expect(markup).toContain('aria-invalid="true"');
    expect(markup).toContain('aria-describedby="alo-err-syl-1-a1-lo1"');
    expect(markup).toContain('aria-describedby="lopo-err-syl-1-lo1-po1"');
    expect(markup).toContain(
      'Cell [MID1 → LO1]: A→LO weight must be a nonnegative number (&gt;= 0).',
    );
    expect(markup).toContain(
      'Cell [LO1 → PO1]: LO→PO weight must be an integer from 1 to 5 (or 0 for unmapped).',
    );
    expect(markup).toContain('role="alert"');
  });

  it('surfaces UNMAPPED LOs, ORPHAN LOs, UNREACHABLE POs, NOT_ASSESSED POs, and INCOMPATIBLE_VERSION', () => {
    const poList = [
      { id: 'po1', code: 'PO1' },
      { id: 'po2', code: 'PO2' },
    ];
    // LO1 has A→LO weight 50 but no PO links (ORPHAN)
    // LO2 has no A→LO weight (UNMAPPED) but links to PO1 (ORPHAN + makes PO1 UNREACHABLE)
    // PO2 has no links (NOT_ASSESSED)
    const diagnostics = computeLiveMappingDiagnostics({
      version: { ...prdSyllabus, po_set_version: 1 },
      programOutcomes: poList,
      aLoDraft: { 'a1:lo1': '50', 'a2:lo1': '0', 'a1:lo2': '', 'a2:lo2': '' },
      loPoDraft: { 'lo1:po1': '0', 'lo2:po1': '3', 'lo2:po2': '0' },
      activePoSetVersion: 2,
    });

    expect(diagnostics.incompatibleVersion).toBe(true);
    expect(diagnostics.incompatibleVersionMessage).toContain(
      'INCOMPATIBLE_VERSION',
    );
    expect(diagnostics.unmappedLOs).toEqual(['LO2']);
    expect(diagnostics.orphanedLOs).toEqual(['LO1', 'LO2']);
    expect(diagnostics.unreachablePOs).toEqual(['PO1']);
    expect(diagnostics.unassessedPOs).toEqual(['PO2']);

    const markup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: {
          ...prdSyllabus,
          po_set_version: 1,
          assessment_lo_mappings: [
            {
              assessment: 'a1',
              learning_outcome: 'lo1',
              weight: '50',
              is_active: true,
            },
          ],
          lo_po_mappings: [
            {
              learning_outcome: 'lo2',
              program_outcome: 'po1',
              weight: 3,
              is_active: true,
            },
          ],
        },
        canDraft: true,
        activePoSetVersion: 2,
        onSaved: vi.fn(),
      }),
    );

    expect(markup).toContain('INCOMPATIBLE_VERSION');
    expect(markup).toContain('UNMAPPED');
    expect(markup).toContain('ORPHAN');
    expect(markup).toContain('UNREACHABLE');
    expect(markup).toContain('NOT_ASSESSED');
  });

  it('blocks edits for approved versions and unauthorized users (read-only mode)', () => {
    const approvedMarkup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: {
          ...prdSyllabus,
          status: 'approved',
          approved_at: '2026-10-01T12:00:00Z',
        },
        canDraft: true,
        activePoSetVersion: 1,
        onSaved: vi.fn(),
      }),
    );
    expect(approvedMarkup).toContain('Approved (locked / read-only)');
    expect(approvedMarkup).toContain('Locked / Read-Only:');
    expect(approvedMarkup).toContain('Create revision');
    expect(approvedMarkup).not.toContain('Save A→LO matrix');
    expect(approvedMarkup).not.toContain('Save LO→PO matrix');
    expect(approvedMarkup).not.toContain('<input');

    mockState.mutationCallIndex = 0;
    const unauthorizedMarkup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: prdSyllabus,
        canDraft: false,
        activePoSetVersion: 1,
        onSaved: vi.fn(),
      }),
    );
    expect(unauthorizedMarkup).toContain('Draft (read-only)');
    expect(unauthorizedMarkup).toContain('You do not have drafting permission');
    expect(unauthorizedMarkup).not.toContain('Save A→LO matrix');
    expect(unauthorizedMarkup).not.toContain('Save LO→PO matrix');
    expect(unauthorizedMarkup).not.toContain('<input');
  });

  it('preserves unsaved draft edits on 409 Conflict and prompts user to refresh server mappings', () => {
    const conflictErr = new ApiError('conflict', 409, {
      code: 'version_conflict',
    });
    expect(isVersionConflictError(conflictErr)).toBe(true);
    expect(isVersionConflictError(new ApiError('validation', 400))).toBe(false);

    mockState.aLoMutation = {
      isPending: false,
      isError: true,
      error: conflictErr,
      mutate: vi.fn(),
      reset: vi.fn(),
    };

    const markup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: prdSyllabus,
        canDraft: true,
        activePoSetVersion: 1,
        initialALoOverrides: { 'a1:lo1': '75' },
        onSaved: vi.fn(),
      }),
    );

    expect(markup).toContain('Version conflict (409)');
    expect(markup).toContain('role="alert"');
    expect(markup).toContain('Your unsaved draft edits have been preserved');
    expect(markup).toContain('Refresh server mappings');
    expect(markup).toContain('Unsaved A→LO changes (1 cells)');
    expect(markup).toContain('value="75"');
  });

  it('supports keyboard matrix cell navigation, dirty detection, and screen-reader table accessibility', () => {
    expect(getNextMatrixCellCoord(0, 0, 2, 3, 'ArrowDown')).toEqual({
      rowIndex: 1,
      colIndex: 0,
    });
    expect(getNextMatrixCellCoord(0, 0, 2, 3, 'ArrowUp')).toEqual({
      rowIndex: 0,
      colIndex: 0,
    });
    expect(getNextMatrixCellCoord(1, 0, 2, 3, 'ArrowRight')).toEqual({
      rowIndex: 1,
      colIndex: 1,
    });
    expect(getNextMatrixCellCoord(1, 2, 2, 3, 'ArrowRight')).toEqual({
      rowIndex: 1,
      colIndex: 2,
    });
    expect(getNextMatrixCellCoord(1, 1, 2, 3, 'ArrowLeft')).toEqual({
      rowIndex: 1,
      colIndex: 0,
    });
    expect(getNextMatrixCellCoord(0, 0, 2, 3, 'Tab')).toBeNull();

    expect(isALoCellDirty('60', '60.00')).toBe(false);
    expect(isALoCellDirty('', '0')).toBe(false);
    expect(isALoCellDirty('65', '60')).toBe(true);
    expect(isALoCellDirty('-1', '60')).toBe(true);

    expect(isLoPoCellDirty('2', '2')).toBe(false);
    expect(isLoPoCellDirty('', '0')).toBe(false);
    expect(isLoPoCellDirty('3', '2')).toBe(true);
    expect(isLoPoCellDirty('2.5', '2')).toBe(true);

    const markup = renderToStaticMarkup(
      createElement(SyllabusMappingStudio, {
        version: prdSyllabus,
        canDraft: true,
        activePoSetVersion: 1,
        onSaved: vi.fn(),
      }),
    );

    expect(markup).toContain('<caption');
    expect(markup).toContain('scope="col"');
    expect(markup).toContain('scope="row"');
    expect(markup).toContain(
      'aria-label="Assessment A1 to LO1 relative weight"',
    );
    expect(markup).toContain(
      'aria-label="LO1 to PO1 integer weight (1 to 5, or 0 for unmapped)"',
    );
    expect(markup).toContain('data-matrix-cell="alo-0-0"');
    expect(markup).toContain('data-matrix-cell="lopo-0-0"');
    expect(markup).toContain(
      'Equivalent Assessment → LO → PO traceability summary',
    );
  });
});
