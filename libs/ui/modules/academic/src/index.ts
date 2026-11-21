'use client';

export {
  CoordinatorAcademicOverview,
  InstructorDashboard,
  StudentDashboard,
} from './features/workspace/components';
export {
  RosterCsvImportDialog,
  RosterCsvImportPanel,
} from './features/workspace/roster-import';
export { AcademicCatalogDashboard } from './features/catalog/components';
export {
  CoordinatorPublicationsManager,
} from './features/catalog/publications-manager';
export {
  buildPublishIdempotencyKey,
  getCalculationRuns,
  getProgramPublications,
  parsePublicationConflict,
  publishCalculationRun,
  resolvePublicationFreshness,
  runProgramCalculation,
} from './features/catalog/publications-api';
export type {
  CalculationRun,
  GovernancePublication,
  PublicationAudience,
  PublicationConflictInfo,
  PublicationFreshness,
  PublishRunPayload,
} from './features/catalog/publications-api';
export {
  CoordinatorApprovalsPanel,
  validateCoursePoRelevanceWeight,
} from './features/syllabus/coordinator-approvals';
export type { RelevanceWeightValidation } from './features/syllabus/coordinator-approvals';
export {
  CoordinatorPOSetManager,
  resolvePoSetLifecycle,
} from './features/syllabus/coordinator-po-sets';
export type { PoSetLifecycleState } from './features/syllabus/coordinator-po-sets';
export { InstructorGradebook, StudentGradeSummary } from './features/gradebook/components';

