// LOAD-01: HTTP load tests against the running API (k6).
// SCENARIO = smoke | load | stress | spike | soak   (see docs/perf/LOAD-TESTING.md)
import http from 'k6/http';
import { sleep, fail } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8001';
const SCENARIO = __ENV.SCENARIO || 'smoke';
const PASSWORD = __ENV.PERF_LOAD_PASSWORD;
const API = __ENV.API_PREFIX || '/api/v1';
// VERIFY against config/urls.py if the smoke run fails at login.
const SESSION_PATH = __ENV.AUTH_SESSION_PATH || '/api/auth/session/';
const LOGIN_PATH = __ENV.AUTH_LOGIN_PATH || '/api/auth/login/';
const STUDENTS = parseInt(__ENV.LOAD_STUDENTS || '5', 10);
const SOAK_MINUTES = __ENV.SOAK_MINUTES || '45';
const INCLUDE_PDF = __ENV.INCLUDE_PDF === '1';
// VERIFY against reports/serializers.py (ExportQuerySerializer). {pub} = a publication id.
const EXPORT_QS = __ENV.EXPORT_QUERY || 'publication_id={pub}&scope=cohort&program_id={program}';
// VERIFY the filter / page-size names against GradeService.get_queryset and AcademicPagination.
const GRADEBOOK_QS = __ENV.GRADEBOOK_QUERY || 'offering={offering}&page_size=200';

const META = JSON.parse(open('/perf/seed-meta.json'));
const TARGETS = JSON.parse(open('/perf/targets.json'));

// PROPOSED p95 budgets (ms). The PRD sets no targets: used only where targets.json is null.
const PROPOSED_P95_MS = {
  publication_list_staff: 500,
  publication_list_student: 300,
  analytics_cohort_program: 800,
  gradebook_page_200: 800,
  export_cohort_csv: 2000,
  export_cohort_pdf: 5000,
};
const MIX = [
  ['publication_list_staff', 30],
  ['publication_list_student', 25],
  ['analytics_cohort_program', 20],
  ['gradebook_page_200', 15],
  ['export_cohort_csv', 8],
  ['export_cohort_pdf', INCLUDE_PDF ? 2 : 0],
].filter(([, w]) => w > 0);
const ENDPOINTS = MIX.map(([n]) => n);

function p95For(name) {
  const t = TARGETS[name];
  return t && t.p95_ms != null ? t.p95_ms : PROPOSED_P95_MS[name];
}

const thresholds = { http_req_failed: ['rate<0.01'] };
if (SCENARIO !== 'smoke') {
  for (const e of ENDPOINTS) {
    thresholds[`http_req_duration{endpoint:${e}}`] = [`p(95)<${p95For(e)}`];
    thresholds[`http_req_failed{endpoint:${e}}`] = ['rate<0.01'];
  }
}

const SCENARIOS = {
  smoke: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '2m' },
  load: {
    executor: 'ramping-vus',
    stages: [
      { duration: '1m', target: 20 },
      { duration: '5m', target: 20 },
      { duration: '30s', target: 0 },
    ],
  },
  stress: {
    executor: 'ramping-vus',
    stages: [
      { duration: '2m', target: 20 },
      { duration: '2m', target: 50 },
      { duration: '2m', target: 100 },
      { duration: '2m', target: 200 },
      { duration: '2m', target: 300 },
      { duration: '1m', target: 0 },
    ],
  },
  spike: {
    executor: 'ramping-vus',
    stages: [
      { duration: '30s', target: 5 },
      { duration: '10s', target: 100 },
      { duration: '1m', target: 100 },
      { duration: '10s', target: 5 },
      { duration: '2m', target: 5 },
      { duration: '10s', target: 0 },
    ],
  },
  soak: {
    executor: 'ramping-vus',
    stages: [
      { duration: '2m', target: 4 },
      { duration: `${SOAK_MINUTES}m`, target: 4 },
      { duration: '1m', target: 0 },
    ],
  },
};
if (!SCENARIOS[SCENARIO]) fail(`Unknown SCENARIO '${SCENARIO}'`);

export const options = {
  scenarios: { [SCENARIO]: { ...(SCENARIOS[SCENARIO].executor === 'ramping-vus' ? { gracefulRampDown: '30s' } : {}), ...SCENARIOS[SCENARIO] } },
  thresholds,
};

http.setResponseCallback(http.expectedStatuses(200));

// Log in once per user (LoginThrottle allows 10/min per IP), then share the session cookie.
function login(username) {
  const jar = new http.CookieJar();
  const s = http.get(`${BASE}${SESSION_PATH}`, { jar, tags: { endpoint: 'login' } });
  const csrf = s.cookies.csrftoken && s.cookies.csrftoken[0].value;
  if (!csrf) return null;
  const r = http.post(
    `${BASE}${LOGIN_PATH}`,
    JSON.stringify({ username, password: PASSWORD }),
    {
      jar,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      cookies: { csrftoken: csrf },
      tags: { endpoint: 'login' },
    },
  );
  if (r.status !== 200) {
    console.error(`login ${username}: HTTP ${r.status}`);
    return null;
  }
  const sid = r.cookies.sessionid && r.cookies.sessionid[0].value;
  return sid ? { sessionid: sid } : null;
}

function rows(res) {
  if (res.status !== 200) return [];
  const body = res.json();
  return Array.isArray(body) ? body : body.results || [];
}

export function setup() {
  if (!PASSWORD) fail('PERF_LOAD_PASSWORD is not set.');
  const coord = login('perf.coordinator');
  if (!coord) fail('Coordinator login failed (password, session path, or throttle).');
  const students = [];
  for (let i = 1; i <= STUDENTS; i++) {
    const s = login(`perf.student.${String(i).padStart(5, '0')}`);
    if (s) students.push(s);
  }
  if (!students.length) fail('No student could log in.');

  const offeringIds = rows(
    http.get(`${BASE}${API}/offerings/`, { cookies: coord, tags: { endpoint: 'setup' } }),
  )
    .map((r) => r.id)
    .slice(0, 4);
  const publicationId = (rows(
    http.get(`${BASE}${API}/publications/`, { cookies: coord, tags: { endpoint: 'setup' } }),
  )[0] || {}).id;
  if (!offeringIds.length || !publicationId) fail('Seeded offerings/publications not found.');
  return { coord, students, offeringIds, publicationId, programId: META.program_id };
}

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

function hitRaw(name, d) {
  const p = (session, extra = {}) => ({
    cookies: session,
    tags: { endpoint: name, name },
    ...extra,
  });
  switch (name) {
    case 'publication_list_staff':
      return http.get(`${BASE}${API}/publications/`, p(d.coord));
    case 'publication_list_student':
      return http.get(`${BASE}${API}/publications/`, p(pick(d.students)));
    case 'analytics_cohort_program':
      return http.get(`${BASE}${API}/analytics/cohort/?program=${d.programId}`, p(d.coord));
    case 'gradebook_page_200': {
      const qs = GRADEBOOK_QS.replace('{offering}', pick(d.offeringIds));
      return http.get(`${BASE}${API}/grades/?${qs}`, p(d.coord));
    }
    case 'export_cohort_csv':
    case 'export_cohort_pdf': {
      const fmt = name === 'export_cohort_csv' ? 'csv' : 'pdf';
      const qs = EXPORT_QS.replace('{pub}', d.publicationId).replace('{program}', d.programId);
      return http.get(
        `${BASE}${API}/reports/exports/?${qs}&format=${fmt}`,
        p(d.coord, { responseType: 'none' }),
      );
    }
  }
}

function weighted() {
  const total = MIX.reduce((n, [, w]) => n + w, 0);
  let r = Math.random() * total;
  for (const [name, w] of MIX) {
    if ((r -= w) <= 0) return name;
  }
  return MIX[0][0];
}

export default function (data) {
  if (SCENARIO === 'smoke') {
    ENDPOINTS.forEach((n) => hit(n, data));
    return;
  }
  hit(weighted(), data);
  sleep(1 + Math.random()); // think time
}

function hit(name, d) {
  const res = hitRaw(name, d);
  if (SCENARIO === 'smoke' && res) console.log(`TIMING ${name} ${res.timings.duration.toFixed(0)}ms HTTP ${res.status}`);
  if (res && res.status >= 400) {
    console.error(`FAILED ${name}: HTTP ${res.status} ${res.url}`);
  }
  return res;
}
