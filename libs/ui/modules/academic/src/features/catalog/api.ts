import { ApiError, request } from '@outcometrik/api';

export interface CatalogRow extends Record<string, unknown> {
  id: string;
}

export type CatalogResource =
  | 'departments'
  | 'programs'
  | 'terms'
  | 'courses'
  | 'program-courses'
  | 'offerings'
  | 'program-memberships'
  | 'instructor-assignments'
  | 'enrollments';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseCatalogPage(value: unknown): CatalogRow[] {
  if (
    !isRecord(value) ||
    !Array.isArray(value.results) ||
    !value.results.every((row) => isRecord(row) && typeof row.id === 'string')
  ) {
    throw new ApiError('unexpected', 200);
  }
  return value.results as CatalogRow[];
}

export async function getCatalogRows(
  resource: CatalogResource,
  params: Record<string, string>,
  signal?: AbortSignal,
) {
  async function getPage(page: number) {
    const query = new URLSearchParams({
      page_size: '200',
      page: String(page),
      ...params,
    });
    const data: unknown = await request(`/api/v1/${resource}/?${query}`, {
      signal,
      cache: 'no-store',
    });
    if (!isRecord(data) || typeof data.count !== 'number') {
      throw new ApiError('unexpected', 200);
    }
    return { count: data.count, rows: parseCatalogPage(data) };
  }

  const first = await getPage(1);
  const pageCount = Math.ceil(first.count / 200);
  if (pageCount <= 1) return first.rows;
  const remainder = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) => getPage(index + 2)),
  );
  return [...first.rows, ...remainder.flatMap((page) => page.rows)];
}

export async function createCatalogRecord(
  resource: CatalogResource,
  body: Record<string, string | number>,
) {
  const data = await request(`/api/v1/${resource}/`, { method: 'POST', body });
  if (!isRecord(data) || typeof data.id !== 'string') {
    throw new ApiError('unexpected', 201);
  }
  return data;
}
