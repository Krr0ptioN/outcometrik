'use client';

import {
  createContext,
  useContext,
  type ReactNode,
} from 'react';
import type {
  CohortCourseOption,
  CohortProgramOption,
  CohortTermOption,
  CoordinatorPublication,
} from '../types';

export interface CohortOverviewContextValue {
  programs: CohortProgramOption[];
  publications: CoordinatorPublication[];
  publicationsPending: boolean;
  terms: CohortTermOption[];
  courses: CohortCourseOption[];
  activeProgramId: string;
  activePublicationId: string;
  selectedTermId: string;
  selectedCourseId: string;
  activePoSetVersion: number | undefined;
  hasActiveFilters: boolean;
  onProgramChange: (programId: string) => void;
  onPublicationChange: (publicationId: string) => void;
  onTermChange: (termId: string) => void;
  onCourseChange: (courseId: string) => void;
  onResetFilters: () => void;
}

const CohortOverviewContext =
  createContext<CohortOverviewContextValue | null>(null);

export function CohortOverviewProvider({
  value,
  children,
}: {
  value: CohortOverviewContextValue;
  children: ReactNode;
}) {
  return (
    <CohortOverviewContext.Provider value={value}>
      {children}
    </CohortOverviewContext.Provider>
  );
}

export function useCohortOverviewContext(): CohortOverviewContextValue {
  const ctx = useContext(CohortOverviewContext);
  if (!ctx) {
    throw new Error(
      'useCohortOverviewContext must be used inside <CohortOverviewProvider>.',
    );
  }
  return ctx;
}
