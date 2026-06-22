/**
 * POST /api/capture-lead — endpoint de la CAPTURE CLIENT (page /devis/mon-toit).
 *
 * W112. Miroir de la structure de /api/preview-lead : même rate-limit anti-spam
 * (bucket distinct), même validation (validateLead), même construction
 * (buildLeadRecord), même transfert CRM tolérant (forwardLead) — mais SANS toucher
 * /api/preview-lead. La SEULE différence : on joint au lead transmis le REPÈRE du
 * toit posé par le client (`roofPoint`), le contour optionnel (`roofOutline`) et la
 * consommation (`billKwh`) — exactement les champs supplémentaires que le récepteur
 * Django accepte. L'étude solaire (panneaux/optimiseur) se fait ENSUITE côté Meriem.
 *
 * Comme /api/preview-lead, on ne BLOQUE jamais l'UX sur une panne webhook (transfert
 * en arrière-plan, même tolérance) et on ne journalise AUCUNE PII.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  buildLeadRecord,
  forwardLead,
  redactLeadForLog,
  runSimulation,
  validateLead,
  type LeadEnv,
} from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

/** {lat,lng} fini, ou null. Garde-fou : on n'attache qu'un repère numériquement valide. */
function cleanRoofPoint(v: unknown): { lat: number; lng: number } | null {
  if (!v || typeof v !== 'object') return null;
  const o = v as { lat?: unknown; lng?: unknown };
  const lat = Number(o.lat);
  const lng = Number(o.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { lat, lng };
}

/** [[lat,lng],…] (≥ 3 paires finies), borné à 200 sommets, ou []. */
function cleanRoofOutline(v: unknown): Array<[number, number]> {
  if (!Array.isArray(v)) return [];
  const out: Array<[number, number]> = [];
  for (const p of v.slice(0, 200)) {
    if (!Array.isArray(p) || p.length < 2) continue;
    const lat = Number(p[0]);
    const lng = Number(p[1]);
    if (Number.isFinite(lat) && Number.isFinite(lng)) out.push([lat, lng]);
  }
  return out.length >= 3 ? out : [];
}

/** Nombre fini > 0, sinon null (factures : jamais un nombre absurde / négatif). */
function cleanMoney(v: unknown): number | null {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** Nombre fini, sinon null (coordonnées GPS du repère). */
function cleanCoord(v: unknown): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Mode de raccordement reconnu (sinon null — on ne devine pas). */
function cleanRaccordement(v: unknown): 'monophase' | 'triphase' | 'inconnu' | null {
  return v === 'monophase' || v === 'triphase' || v === 'inconnu' ? v : null;
}

/** Adresse (chaîne nettoyée bornée), ou null. */
function cleanAdresse(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.trim().slice(0, 200);
  return s.length > 0 ? s : null;
}

export const POST: APIRoute = async ({ request }) => {
  // Même garde-fou anti-spam que /api/preview-lead (bucket distinct par endpoint).
  const rl = rateLimit(`capture-lead:${clientIpFromRequest(request)}`);
  if (!rl.allowed) {
    return json({ ok: false, errors: { rate: 'Trop de tentatives, réessayez dans un instant.' } }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, errors: { body: 'JSON invalide' } }, 400);
  }

  const validation = validateLead(body);
  if (!validation.ok) return json({ ok: false, errors: validation.errors }, 400);
  const lead = validation.lead;

  const env = (cf.env ?? {}) as LeadEnv;
  const band = await runSimulation(lead, env, fetch);
  const page = request.headers.get('referer');
  const baseRecord = buildLeadRecord(lead, band, new Date(), page);

  // Champs supplémentaires acceptés par le récepteur Django : repère, contour,
  // consommation, PROFIL ÉNERGÉTIQUE (W1/W3) + adresse/GPS lus depuis la carte.
  // Ajoutés UNIQUEMENT s'ils sont valides — sinon l'enregistrement transmis reste
  // identique à celui de /api/preview-lead. `factureEte`/`eteDifferente` sont liés :
  // une seule pièce d'info (été ≠ hiver) avec sa valeur d'été.
  const b = (body ?? {}) as Record<string, unknown>;
  const roofPoint = cleanRoofPoint(b.roofPoint);
  const roofOutline = cleanRoofOutline(b.roofOutline);
  const billKwh = Number(b.billKwh);
  // W1/W3 — profil énergétique
  const factureHiver = cleanMoney(b.factureHiver);
  const eteDifferente = b.eteDifferente === true;
  // été non différent ⇒ factureEte forcé à null (jamais une valeur résiduelle).
  const factureEte = eteDifferente ? cleanMoney(b.factureEte) : null;
  const raccordement = cleanRaccordement(b.raccordement);
  const adresse = cleanAdresse(b.adresse);
  // W3 — GPS issu du repère (priorité au repère validé ; sinon les champs gps* bruts).
  const gpsLat = roofPoint ? roofPoint.lat : cleanCoord(b.gpsLat);
  const gpsLng = roofPoint ? roofPoint.lng : cleanCoord(b.gpsLng);
  const record = {
    ...baseRecord,
    ...(roofPoint ? { roofPoint } : {}),
    ...(roofOutline.length >= 3 ? { roofOutline } : {}),
    ...(Number.isFinite(billKwh) && billKwh > 0 ? { billKwh } : {}),
    ...(factureHiver != null ? { factureHiver } : {}),
    // `factureEte` est explicitement émis (number|null) pour signaler « été identique »
    // quand eteDifferente est faux — le récepteur peut s'y fier.
    factureEte,
    eteDifferente,
    ...(raccordement ? { raccordement } : {}),
    ...(adresse ? { adresse } : {}),
    ...(gpsLat != null ? { gpsLat } : {}),
    ...(gpsLng != null ? { gpsLng } : {}),
  };

  const background = (async () => {
    const fw = await forwardLead(record, env, fetch);
    if (!fw.delivered && baseRecord.qualified) {
      // Aucune PII dans les logs (id haché, indicateurs, raison) — comme preview-lead.
      console.log(
        `[capture-lead] non transmis au CRM (${fw.reason}) — lead qualifié:`,
        JSON.stringify(redactLeadForLog(baseRecord)),
      );
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  // Jamais bloquer l'UX sur le webhook (même tolérance que le flux existant).
  return json({ ok: true, qualified: baseRecord.qualified });
};
