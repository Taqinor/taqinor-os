// YTEST14 — write-path slice of the traffic mix: creating a devis.
// Kept in its own script (vs. folded into browse.js) so a write-heavy
// regression doesn't get diluted by the read-heavy scenario's volume.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, login, authHeaders, PERCENTILE_THRESHOLDS } from './common.js';

export const options = {
  scenarios: {
    create_devis: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '20s', target: 5 },
        { duration: '1m', target: 5 },
        { duration: '20s', target: 0 },
      ],
    },
  },
  thresholds: PERCENTILE_THRESHOLDS,
};

export function setup() {
  const token = login();
  if (!token) {
    return { token: null, clientId: null };
  }
  // Reuse (or create once) a single client to attach devis to — this script
  // measures the WRITE endpoint's latency, not client provisioning.
  const headers = authHeaders(token);
  const list = http.get(`${BASE_URL}/api/django/crm/clients/?page_size=1`, headers);
  let clientId = null;
  if (list.status === 200) {
    const body = list.json();
    const results = body.results || body;
    if (Array.isArray(results) && results.length > 0) {
      clientId = results[0].id;
    }
  }
  if (!clientId) {
    const created = http.post(
      `${BASE_URL}/api/django/crm/clients/`,
      JSON.stringify({ nom: 'LoadTest', prenom: 'K6', telephone: '+212600000000' }),
      headers,
    );
    if (created.status === 201) {
      clientId = created.json('id');
    }
  }
  return { token, clientId };
}

export default function (data) {
  if (!data.token || !data.clientId) {
    return;
  }
  const headers = authHeaders(data.token);
  const payload = JSON.stringify({
    client: data.clientId,
    statut: 'brouillon',
    taux_tva: '20.00',
  });
  const r = http.post(`${BASE_URL}/api/django/ventes/devis/`, payload, headers);
  check(r, { 'create devis 201': (res) => res.status === 201 });
  sleep(1);
}
