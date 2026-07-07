// Shared helpers for the k6 load/spike scripts (YTEST14).
//
// BASE_URL / LOGIN_USER / LOGIN_PASSWORD are k6 environment variables so the
// same script targets a local stack or a staging box without editing code:
//   k6 run -e BASE_URL=http://localhost:8000 -e LOGIN_USER=... loadtests/browse.js
import http from 'k6/http';
import { check } from 'k6';

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export function login() {
  const username = __ENV.LOGIN_USER || 'loadtest';
  const password = __ENV.LOGIN_PASSWORD || 'loadtest';
  const res = http.post(
    `${BASE_URL}/api/django/token/`,
    JSON.stringify({ username, password }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'login succeeded': (r) => r.status === 200 });
  if (res.status !== 200) {
    return null;
  }
  return res.json('access');
}

export function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };
}

// Percentile-based thresholds (never the mean — a slow p99 hurts real users
// even when the average looks fine). Shared by the load + spike scenarios;
// docs/testing.md notes the same rule for anyone adding a new script.
export const PERCENTILE_THRESHOLDS = {
  http_req_duration: ['p(95)<800', 'p(99)<1500'],
  http_req_failed: ['rate<0.005'],
};
