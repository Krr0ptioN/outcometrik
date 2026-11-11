import { ApiError, request, type Page } from '@outcometrik/api';

export type GradeState = 'scored' | 'missing' | 'exempt' | 'withdrawn' | 'incomplete';

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

function isPage<T>(value: unknown, isRow: (row: unknown) => row is T): value is Page<T> {
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
  return ['scored', 'missing', 'exempt', 'withdrawn', 'incomplete'].includes(String(value));
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
    (typeof value.old_points_earned === 'string' || value.old_points_earned === null) &&
    isGradeState(value.new_state) &&
    (typeof value.new_points_earned === 'string' || value.new_points_earned === null) &&
    typeof value.reason === 'string' &&
    (typeof value.changed_by === 'number' || value.changed_by === null) &&
    typeof value.created_at === 'string'
  );
}

function unwrapPage<T>(data: unknown, isRow: (row: unknown) => row is T): T[] {
  if (Array.isArray(data) && data.every(isRow)) return data;
  if (isPage(data, isRow)) return data.results;
  throw new ApiError('unexpected', 200);
}

export async function getApprovedAssessments(offering: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ offering, page_size: '200' });
  const data: unknown = await request(`/api/v1/assessments/?${query}`, {
    signal,
    cache: 'no-store',
  });
  return unwrapPage(data, isAssessment);
}

export async function getGradeBatches(offering: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ offering, page_size: '200' });
  const data: unknown = await request(`/api/v1/grade-batches/?${query}`, {
    signal,
    cache: 'no-store',
  });
  return unwrapPage(data, isGradeBatch);
}

export async function getGrades(offering: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ offering, page_size: '200' });
  const data: unknown = await request(`/api/v1/grades/?${query}`, {
    signal,
    cache: 'no-store',
  });
  return unwrapPage(data, isGrade);
}

export async function getReleasedStudentGrades(signal?: AbortSignal) {
  const data: unknown = await request('/api/v1/grades/?page_size=200', {
    signal,
    cache: 'no-store',
  });
  return unwrapPage(data, isGrade);
}

export async function getGradeHistory(gradeId: string, signal?: AbortSignal) {
  const data: unknown = await request(`/api/v1/grades/${encodeURIComponent(gradeId)}/history/`, {
    signal,
    cache: 'no-store',
  });
  if (!Array.isArray(data) || !data.every(isHistoryEntry)) throw new ApiError('unexpected', 200);
  return data;
}

export function createGradeBatch(offering: string, name: string) {
  return request<GradeBatch>('/api/v1/grade-batches/', {
    method: 'POST',
    body: { offering, name },
  });
}

export function releaseGradeBatch(batchId: string) {
  return request<GradeBatch>(`/api/v1/grade-batches/${encodeURIComponent(batchId)}/release/`, {
    method: 'POST',
  });
}

export function createGrade(input: GradeWrite) {
  return request<GradeRecord>('/api/v1/grades/', { method: 'POST', body: input });
}

export function correctGrade(gradeId: string, input: GradeCorrection) {
  return request<GradeRecord>(`/api/v1/grades/${encodeURIComponent(gradeId)}/`, {
    method: 'PATCH',
    body: input,
  });
}
