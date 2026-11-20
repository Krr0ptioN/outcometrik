import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '@outcometrik/api';
import {
  getStudentPublicationScores,
  getStudentPublications,
} from './api';

const PUB_ID = '8f0d3c3e-6a1b-4c7e-9d11-2b5f4a7c9e01';
const PROGRAM_ID = '0b9a7e22-5c3d-4f61-8a40-7d2e1c6b3f55';
const RUN_ID = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';

const VALID_PUB = {
  id: PUB_ID,
  program: PROGRAM_ID,
  program_code: 'CSE-BS',
  program_title: 'Computer Engineering',
  offering: null,
  offering_label: null,
  term: null,
  term_label: '2026 Fall',
  run: RUN_ID,
  scope_kind: 'program',
  series_version: 1,
  po_set_version: 1,
  audience: 'student',
  published_at: '2026-11-15T10:00:00Z',
  stale: false,
  program_outcomes: [
    {
      code: 'PO1',
      label: 'Engineering Fundamentals',
      description: 'Apply math and engineering.',
      ordering: 1,
    },
  ],
};

const VALID_SCORE = {
  id: '2a3b4c5d-6e7f-4a8b-9c0d-1e2f3a4b5c6d',
  run: RUN_ID,
  level: 'cumulative_po',
  student: 42,
  offering: null,
  learning_outcome: null,
  program_outcome: '3a3b4c5d-6e7f-4a8b-9c0d-1e2f3a4b5c6d',
  outcome_code: 'PO1',
  value: '84.952381',
  display_value: '85.0',
  numerator: '339.809524',
  denominator: '4.000000',
  coverage: '1.0000',
  status: 'OK',
  evidence: {
    kernel_version: '1.0',
    policy_version: 'calc-policy-v1',
    contributions: [],
    missing: [],
    exemptions: [],
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubJsonFetch(body: unknown, status = 200) {
  const fetcher = vi.fn(() => Promise.resolve(Response.json(body, { status })));
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

async function expectApiError(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => null,
    (err: unknown) => err,
  );
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

it('fetches paginated student publications with cache: no-store and filters faculty rows', async () => {
  const fetcher = stubJsonFetch({
    count: 2,
    next: null,
    previous: null,
    results: [VALID_PUB, { ...VALID_PUB, id: '99999999-6a1b-4c7e-9d11-2b5f4a7c9e01', audience: 'faculty' }],
  });
  const controller = new AbortController();

  const pubs = await getStudentPublications(controller.signal);
  expect(pubs).toHaveLength(1);
  expect(pubs[0].id).toBe(PUB_ID);
  expect(pubs[0].program_outcomes[0].code).toBe('PO1');

  const [path, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
  expect(path).toBe('/api/v1/publications/');
  expect(init).toMatchObject({
    method: 'GET',
    cache: 'no-store',
    credentials: 'same-origin',
    redirect: 'error',
  });
});

it('rejects malformed publication payloads with ApiError("unexpected", 200)', async () => {
  stubJsonFetch({ bad: 'shape' });
  const err1 = await expectApiError(getStudentPublications());
  expect([err1.kind, err1.status]).toEqual(['unexpected', 200]);

  stubJsonFetch({ results: [{ id: PUB_ID, stale: 'not-a-boolean' }] });
  const err2 = await expectApiError(getStudentPublications());
  expect([err2.kind, err2.status]).toEqual(['unexpected', 200]);
});

it('fetches student publication scores with cache: no-store and validates UUID', async () => {
  const fetcher = stubJsonFetch([VALID_SCORE]);
  const badUuidErr = await expectApiError(getStudentPublicationScores('not-a-uuid'));
  expect([badUuidErr.kind, badUuidErr.status]).toEqual(['validation', 0]);
  expect(fetcher).not.toHaveBeenCalled();

  const scores = await getStudentPublicationScores(PUB_ID);
  expect(scores).toHaveLength(1);
  expect(scores[0].outcome_code).toBe('PO1');
  expect(scores[0].display_value).toBe('85.0');

  const [path, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
  expect(path).toBe(`/api/v1/publications/${PUB_ID}/scores/`);
  expect(init).toMatchObject({
    method: 'GET',
    cache: 'no-store',
  });
});

it('rejects malformed score payloads with ApiError("unexpected", 200)', async () => {
  stubJsonFetch({ not: 'an array' });
  const err1 = await expectApiError(getStudentPublicationScores(PUB_ID));
  expect([err1.kind, err1.status]).toEqual(['unexpected', 200]);

  stubJsonFetch([{ ...VALID_SCORE, status: 'BOGUS_STATUS' }]);
  const err2 = await expectApiError(getStudentPublicationScores(PUB_ID));
  expect([err2.kind, err2.status]).toEqual(['unexpected', 200]);
});
