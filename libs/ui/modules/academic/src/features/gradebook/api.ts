import { ApiError, request, type Page } from '@outcometrik/api';

export type GradeState =
  | 'scored'
  | 'missing'
  | 'exempt'
  | 'withdrawn'
  | 'incomplete';

export interface ApprovedAssessment {
  id: string;
  offering: string;
  title: string;
  points_possible: string;
  status: 'approved';
}

export interface GradeBatch {
  id: string;
  offering: string;
  name: string;
  released_at: string | null;
  created_at: string;
}

export interface GradeRecord {
  id: string;
  offering: string;
  enrollment: string;
  assessment: string;
  assessment_title: string;
  batch: string;
  batch_name: string;
  state: GradeState;
  points_earned: string | null;
  points_possible: string;
  version: number;
  updated_at: string;
}

export interface GradeHistoryEntry {
  version: number;
  old_state: GradeState | '';
  old_points_earned: string | null;
  new_state: GradeState;
  new_points_earned: string | null;
  reason: string;
  changed_by: number | null;
  created_at: string;
}

export interface GradeWrite {
  enrollment: string;
  assessment: string;
  batch: string;
  state: GradeState;
  points_earned: string | null;
  reason: string;
}

export interface GradeCorrection {
  expected_version: number;
  state: GradeState;
  points_earned: string | null;
  reason: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isPage<T>(
  value: unknown,
  isRow: (row: unknown) => row is T,
): value is Page<T> {
  return (
    isRecord(value) &&
    typeof value.count === 'number' &&
    (typeof value.next === 'string' || value.next === null) &&
    (typeof value.previous === 'string' || value.previous === null) &&
    Array.isArray(value.results) &&
    value.results.every(isRow)
  );
}

function isAssessment(value: unknown): value is ApprovedAssessment {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.offering === 'string' &&
    typeof value.title === 'string' &&
    typeof value.points_possible === 'string' &&
    value.status === 'approved'
  );
}

function isGradeBatch(value: unknown): value is GradeBatch {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.offering === 'string' &&
    typeof value.name === 'string' &&
    (typeof value.released_at === 'string' || value.released_at === null) &&
    typeof value.created_at === 'string'
  );
}

function isGradeState(value: unknown): value is GradeState {
  return ['scored', 'missing', 'exempt', 'withdrawn', 'incomplete'].includes(
    String(value),
  );
}

function isGrade(value: unknown): value is GradeRecord {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.offering === 'string' &&
    typeof value.enrollment === 'string' &&
    typeof value.assessment === 'string' &&
    typeof value.assessment_title === 'string' &&
    typeof value.batch === 'string' &&
    typeof value.batch_name === 'string' &&
    isGradeState(value.state) &&
    (typeof value.points_earned === 'string' || value.points_earned === null) &&
    typeof value.points_possible === 'string' &&
    typeof value.version === 'number' &&
    typeof value.updated_at === 'string'
  );
}

function isHistoryEntry(value: unknown): value is GradeHistoryEntry {
  return (
    isRecord(value) &&
    typeof value.version === 'number' &&
    (value.old_state === '' || isGradeState(value.old_state)) &&
    (typeof value.old_points_earned === 'string' ||
      value.old_points_earned === null) &&
    isGradeState(value.new_state) &&
    (typeof value.new_points_earned === 'string' ||
      value.new_points_earned === null) &&
    typeof value.reason === 'string' &&
    (typeof value.changed_by === 'number' || value.changed_by === null) &&
    typeof value.created_at === 'string'
  );
}

async function requestAllPages<T>(
  path: `/api/${string}`,
  params: URLSearchParams,
  signal: AbortSignal | undefined,
  isRow: (row: unknown) => row is T,
): Promise<T[]> {
  const rows: T[] = [];
  let page = 1;
  while (true) {
    params.set('page', String(page));
    const data: unknown = await request(`${path}?${params}`, {
      signal,
      cache: 'no-store',
    });
    if (Array.isArray(data) && data.every(isRow)) return [...rows, ...data];
    if (!isPage(data, isRow)) throw new ApiError('unexpected', 200);
    rows.push(...data.results);
    if (!data.next) return rows;
    // A malformed or inconsistent response must not cause an endless request loop.
    if (!data.results.length || rows.length >= data.count)
      throw new ApiError('unexpected', 200);
    page += 1;
  }
}

async function requestValidated<T>(
  path: `/api/${string}`,
  options: Parameters<typeof request>[1],
  isValue: (value: unknown) => value is T,
  status: number,
): Promise<T> {
  const data: unknown = await request(path, options);
  if (!isValue(data)) throw new ApiError('unexpected', status);
  return data;
}

export function getApprovedAssessments(offering: string, signal?: AbortSignal) {
  return requestAllPages(
    '/api/v1/assessments/',
    new URLSearchParams({ offering, page_size: '200' }),
    signal,
    isAssessment,
  );
}

export function getGradeBatches(offering: string, signal?: AbortSignal) {
  return requestAllPages(
    '/api/v1/grade-batches/',
    new URLSearchParams({ offering, page_size: '200' }),
    signal,
    isGradeBatch,
  );
}

export function getGrades(offering: string, signal?: AbortSignal) {
  return requestAllPages(
    '/api/v1/grades/',
    new URLSearchParams({ offering, page_size: '200' }),
    signal,
    isGrade,
  );
}

export function getReleasedStudentGrades(signal?: AbortSignal) {
  return requestAllPages(
    '/api/v1/grades/',
    new URLSearchParams({ page_size: '200' }),
    signal,
    isGrade,
  );
}

export async function getGradeHistory(gradeId: string, signal?: AbortSignal) {
  const data: unknown = await request(
    `/api/v1/grades/${encodeURIComponent(gradeId)}/history/`,
    {
      signal,
      cache: 'no-store',
    },
  );
  if (!Array.isArray(data) || !data.every(isHistoryEntry))
    throw new ApiError('unexpected', 200);
  return data;
}

export function createGradeBatch(offering: string, name: string) {
  return requestValidated(
    '/api/v1/grade-batches/',
    { method: 'POST', body: { offering, name } },
    isGradeBatch,
    201,
  );
}

export function releaseGradeBatch(batchId: string) {
  return requestValidated(
    `/api/v1/grade-batches/${encodeURIComponent(batchId)}/release/`,
    { method: 'POST' },
    isGradeBatch,
    200,
  );
}

export function createGrade(input: GradeWrite) {
  return requestValidated(
    '/api/v1/grades/',
    { method: 'POST', body: input },
    isGrade,
    201,
  );
}

export function correctGrade(gradeId: string, input: GradeCorrection) {
  return requestValidated(
    `/api/v1/grades/${encodeURIComponent(gradeId)}/`,
    { method: 'PATCH', body: input },
    isGrade,
    200,
  );
}
