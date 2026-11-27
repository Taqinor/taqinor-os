// D-ACAL-169 (a) — relais PUBLIC de la puissance du panneau par défaut.
//
// Contrat : backend/django_core/apps/stock/contract_samples/panneau_par_defaut_site.json.
// GET /api/panneau-defaut → lit `GET {API_BASE}/api/django/public/stock/panneau-par-defaut/`
// et rend TOUJOURS 200 avec exactement { pmax_wc, source } (source : designe | aucun).
// ERP en panne, lent (> 2 s), illisible ou hors contrat → { pmax_wc: null, source: 'aucun' } :
// le site retombe alors sur son panneau habituel, rien ne bloque. Aucun nom, identifiant,
// prix ou stock ne traverse ce relais (seul un watt numérique fini > 0 est recopié).
// Aucun secret nouveau : en-têtes IP visiteur existants (entetesIpVisiteur).
export const prerender = false;

import type { APIRoute } from 'astro';
import { appelAmontJson } from '../../lib/apiPreludeJeton';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';
import { jsonResponse as json } from '../../lib/apiJson';
import { entetesIpVisiteur, resolveApiBase } from './_apiBase';

export const DELAI_ERP_MS = 2000;

export type PanneauDefautPublic =
  | { pmax_wc: number; source: 'designe' }
  | { pmax_wc: null; source: 'aucun' };

const AUCUN: PanneauDefautPublic = { pmax_wc: null, source: 'aucun' };
const SANS_CACHE = { 'cache-control': 'no-store' };
const CACHE_COURT = { 'cache-control': 'public, max-age=300, s-maxage=300' };

export function panneauDefautEndpoint(apiBase: string): string {
  return `${apiBase.replace(/\/+$/, '')}/api/django/public/stock/panneau-par-defaut/`;
}

/** Réduit la réponse ERP au contrat : un watt fini > 0 sur un 200, sinon « aucun ». */
export function normaliserPanneauDefaut(status: number, payload: unknown): PanneauDefautPublic {
  if (status !== 200 || !payload || typeof payload !== 'object' || Array.isArray(payload)) return AUCUN;
  const watt = (payload as { pmax_wc?: unknown }).pmax_wc;
  if (typeof watt !== 'number' || !Number.isFinite(watt) || watt <= 0) return AUCUN;
  return { pmax_wc: watt, source: 'designe' };
}

export const GET: APIRoute = async ({ request }) => {
  const ip = clientIpFromRequest(request);
  // Débit local : au-delà, le site garde son panneau habituel sans solliciter l'ERP.
  if (!rateLimit(`panneau-defaut:${ip}`, { limit: 60, windowMs: 60_000 }).allowed) {
    return json(AUCUN, 200, SANS_CACHE);
  }
  const amont = await appelAmontJson(panneauDefautEndpoint(resolveApiBase()), {
    method: 'GET',
    headers: { accept: 'application/json', ...entetesIpVisiteur(ip) },
    signal: AbortSignal.timeout(DELAI_ERP_MS),
  });
  if (!amont) return json(AUCUN, 200, SANS_CACHE);
  const forme = normaliserPanneauDefaut(amont.status, amont.payload);
  return json(forme, 200, forme.source === 'designe' ? CACHE_COURT : SANS_CACHE);
};
