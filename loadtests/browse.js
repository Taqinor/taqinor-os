// YTEST14 — "load" scenario: a realistic READ-heavy traffic mix.
// Weighted mix: login (rare, ~5%) + list devis (40%) + list clients (35%) +
// devis detail (20%). Gate is the PERCENTILE (p95/p99), never the average —
// see docs/testing.md "percentile, pas moyenne".
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, login, authHeaders, PERCENTILE_THRESHOLDS } from './common.js';

export const options = {
  scenarios: {
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '2m', target: 20 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: PERCENTILE_THRESHOLDS,
};

export function setup() {
  const token = login();
  return { token };
}

export default function (data) {
  if (!data.token) {
    return; // login already flagged as a failed check in setup()
  }
  const headers = authHeaders(data.token);
  const roll = Math.random();

  if (roll < 0.40) {
    const r = http.get(`${BASE_URL}/api/django/ventes/devis/`, headers);
    check(r, { 'list devis 200': (res) => res.status === 200 });
  } else if (roll < 0.75) {
    const r = http.get(`${BASE_URL}/api/django/crm/clients/`, headers);
    check(r, { 'list clients 200': (res) => res.status === 200 });
  } else {
    const r = http.get(`${BASE_URL}/api/django/ventes/devis/`, headers);
    check(r, { 'devis browse 200': (res) => res.status === 200 });
  }

  sleep(1);
}
