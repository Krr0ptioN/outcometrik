import { StatusDot } from '@outcometrik/ui';
import type { Syllabus } from '../api';

export type RelevanceWeightValidation =
  | { ok: true; value: number | null }
  | { ok: false; error: string };

/**
 * Validates a Course→PO relevance weight input.
 * Empty string clears the weight; otherwise must be an integer 1–5.
 */
export function validateCoursePoRelevanceWeight(
  raw: string,
): RelevanceWeightValidation {
  const trimmed = raw.trim();
  if (trimmed === '') return { ok: true, value: null };
  if (!/^[1-5]$/.test(trimmed)) {
    return {
      ok: false,
      error: 'Relevance weight must be an integer between 1 and 5.',
    };
  }
  return { ok: true, value: Number(trimmed) };
}

export function SyllabusStatusDot({ status }: { status: Syllabus['status'] }) {
  if (status === 'approved') {
    return <StatusDot variant="success" label="Approved (locked)" />;
  }
  if (status === 'draft') {
    return <StatusDot variant="warning" label="Pending draft" />;
  }
  return <StatusDot variant="neutral" label="Retired" />;
}
