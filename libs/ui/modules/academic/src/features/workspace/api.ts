import { ApiError, request } from '@outcometrik/api';

export interface InstructorOffering {
  id: string;
  label: string;
  course: string;
  program: string;
  term: string;
  roster: { enrollment_id: string; student_id: number; name: string; status: string }[];
}
export interface StudentCourse {
  enrollment_id: string;
  offering_id: string;
  course_code: string;
  course: string;
  program: string;
  term: string;
  section: string;
  enrollment_status: string;
}
export interface CoordinatorWorkspace {
  programs: { id: string; label: string; department: string }[];
  offerings: { id: string; program_id: string; label: string; course: string; term: string; enrolled: number }[];
  students: { id: number; username: string; first_name: string; last_name: string; program_id: string; student_number: string; membership_status: string }[];
}
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function isInstructorOffering(value: unknown): value is InstructorOffering {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.label === 'string' &&
    typeof value.course === 'string' &&
    typeof value.program === 'string' &&
    typeof value.term === 'string' &&
    Array.isArray(value.roster) &&
    value.roster.every(
      (row) =>
        isRecord(row) &&
        typeof row.enrollment_id === 'string' &&
        typeof row.student_id === 'number' &&
        typeof row.name === 'string' &&
        typeof row.status === 'string',
    )
  );
}
function isStudentCourse(value: unknown): value is StudentCourse {
  return (
    isRecord(value) &&
    ['enrollment_id', 'offering_id', 'course_code', 'course', 'program', 'term', 'section', 'enrollment_status'].every(
      (key) => typeof value[key] === 'string',
    )
  );
}
function isCoordinatorWorkspace(value: unknown): value is CoordinatorWorkspace {
  return (
    isRecord(value) &&
    Array.isArray(value.programs) &&
    value.programs.every((row) => isRecord(row) && typeof row.id === 'string' && typeof row.label === 'string' && typeof row.department === 'string') &&
    Array.isArray(value.offerings) &&
    value.offerings.every((row) => isRecord(row) && typeof row.id === 'string' && typeof row.program_id === 'string' && typeof row.label === 'string' && typeof row.course === 'string' && typeof row.term === 'string' && typeof row.enrolled === 'number') &&
    Array.isArray(value.students) &&
    value.students.every((row) => isRecord(row) && typeof row.id === 'number' && typeof row.username === 'string' && typeof row.first_name === 'string' && typeof row.last_name === 'string' && typeof row.program_id === 'string' && typeof row.student_number === 'string' && typeof row.membership_status === 'string')
  );
}
export async function getCoordinatorWorkspace(signal?: AbortSignal) {
  const data: unknown = await request('/api/v1/workspaces/coordinator/', { signal, cache: 'no-store' });
  if (!isCoordinatorWorkspace(data)) throw new ApiError('unexpected', 200);
  return data;
}
export async function getInstructorWorkspace(signal?: AbortSignal) {
  const data: unknown = await request('/api/v1/workspaces/instructor/', { signal, cache: 'no-store' });
  if (!isRecord(data) || !Array.isArray(data.offerings) || !data.offerings.every(isInstructorOffering))
    throw new ApiError('unexpected', 200);
  return { offerings: data.offerings };
}
export async function getStudentWorkspace(signal?: AbortSignal) {
  const data: unknown = await request('/api/v1/workspaces/student/', { signal, cache: 'no-store' });
  if (!isRecord(data) || !Array.isArray(data.courses) || !data.courses.every(isStudentCourse) || !Array.isArray(data.outcomes))
    throw new ApiError('unexpected', 200);
  return { courses: data.courses, outcomes: data.outcomes };
}
