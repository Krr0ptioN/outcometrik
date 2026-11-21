'use client';

import { memo, useId } from 'react';
import {
  Button,
  Field,
  FieldGroup,
  FieldLabel,
  NativeSelect,
  NativeSelectOption,
} from '@outcometrik/ui';
import { formatPublicationLabel } from './cohort-formatters';
import { useCohortOverviewContext } from './cohort-overview-context';

/**
 * Filter bar consuming `CohortOverviewContext` directly (zero prop drilling).
 */
export const CohortFilterBar = memo(function CohortFilterBar() {
  const {
    programs,
    publications,
    publicationsPending,
    terms,
    courses,
    activeProgramId,
    activePublicationId,
    selectedTermId,
    selectedCourseId,
    hasActiveFilters,
    onProgramChange,
    onPublicationChange,
    onTermChange,
    onCourseChange,
    onResetFilters,
  } = useCohortOverviewContext();

  const programSelectId = useId();
  const publicationSelectId = useId();
  const termSelectId = useId();
  const courseSelectId = useId();

  return (
    <div className="space-y-2">
      <FieldGroup className="grid gap-3 rounded-[var(--radius-card,10px)] border border-border/80 bg-[var(--surface-subtle)]/50 p-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field>
          <FieldLabel
            htmlFor={programSelectId}
            className="text-xs font-medium text-muted-foreground"
          >
            Program
          </FieldLabel>
          <NativeSelect
            id={programSelectId}
            value={activeProgramId}
            className="bg-card"
            onChange={(event) => onProgramChange(event.target.value)}
          >
            {programs.map((program) => (
              <NativeSelectOption key={program.id} value={program.id}>
                {program.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <Field>
          <FieldLabel
            htmlFor={publicationSelectId}
            className="text-xs font-medium text-muted-foreground"
          >
            Publication snapshot
          </FieldLabel>
          <NativeSelect
            id={publicationSelectId}
            value={activePublicationId}
            className="bg-card"
            disabled={publicationsPending || publications.length === 0}
            onChange={(event) => onPublicationChange(event.target.value)}
          >
            {publications.length === 0 ? (
              <NativeSelectOption value="">
                {publicationsPending
                  ? 'Loading snapshots…'
                  : 'No published snapshots'}
              </NativeSelectOption>
            ) : (
              publications.map((pub) => (
                <NativeSelectOption key={pub.id} value={pub.id}>
                  {formatPublicationLabel(pub)}
                </NativeSelectOption>
              ))
            )}
          </NativeSelect>
        </Field>

        <Field>
          <FieldLabel
            htmlFor={termSelectId}
            className="text-xs font-medium text-muted-foreground"
          >
            Term
          </FieldLabel>
          <NativeSelect
            id={termSelectId}
            value={selectedTermId}
            className="bg-card"
            onChange={(event) => onTermChange(event.target.value)}
          >
            <NativeSelectOption value="">All terms</NativeSelectOption>
            {terms.map((term) => (
              <NativeSelectOption key={term.id} value={term.id}>
                {term.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>

        <Field>
          <FieldLabel
            htmlFor={courseSelectId}
            className="text-xs font-medium text-muted-foreground"
          >
            Course
          </FieldLabel>
          <NativeSelect
            id={courseSelectId}
            value={selectedCourseId}
            className="bg-card"
            onChange={(event) => onCourseChange(event.target.value)}
          >
            <NativeSelectOption value="">All courses</NativeSelectOption>
            {courses.map((course) => (
              <NativeSelectOption key={course.id} value={course.id}>
                {course.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
      </FieldGroup>

      {hasActiveFilters && (
        <div className="flex items-center justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onResetFilters}
            className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Reset filters
          </Button>
        </div>
      )}
    </div>
  );
});
