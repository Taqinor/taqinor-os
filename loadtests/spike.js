// YTEST14 — "spike" scenario: a SUDDEN surge (vs. browse.js's steady ramp),
// modeling e.g. a marketing push driving a burst of concurrent logins+reads.
// Kept as a distinct scenario/file per spec — a spike's failure mode (queue
// saturation, connection pool exhaustion) is different from sustained load's.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, login, authHeaders, PERCENTILE_THRESHOLDS } from './common.js';

export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 5 },    // baseline
        { duration: '10s', target: 100 },  // sudden surge
        { duration: '30s', target: 100 },  // hold at peak
        { duration: '10s', target: 5 },    // sudden drop
        { duration: '20s', target: 5 },    // recovery observation
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
    return;
  }
  const headers = authHeaders(data.token);
  const r = http.get(`${BASE_URL}/api/django/ventes/devis/`, headers);
  check(r, { 'devis list 200 under spike': (res) => res.status === 200 });
  sleep(0.5);
}
