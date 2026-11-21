'use client';

import { errorMessage } from '@outcometrik/access';
import { createQueryState } from '@outcometrik/ui';

/**
 * Module-scoped Factory Method instance for `@outcometrik/academic`.
 * Pre-binds `errorMessage` so query-backed organisms never repeat error formatting boilerplate.
 */
export const AcademicQuery = createQueryState({ formatError: errorMessage });
