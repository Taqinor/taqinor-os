/**
 * POST /api/roof-yield — production annuelle (kWh) PVGIS pour l'estimateur
 * « cerveau » (/preview/toiture-3d-pro-3), inclinaison ET azimut paramétrés.
 *
 * Proxy serveur (le navigateur n'appelle JAMAIS PVGIS). On reçoit une ou
 * plusieurs « jambes » { kwc, tiltDeg, aspect } et on SOMME leur production —
 * une jambe pour le sud, deux jambes (−90/+90) pour l'Est-Ouest. PVGIS
 * lent/injoignable → la page bascule sur sa table committée (repli instantané) :
 * ici on renvoie simplement source:'estimate' sans jambe PVGIS.
 *
 * Ne touche AUCUNE donnée de lead. Route additive : /api/roof-estimate (15°,
 * formulaire live) reste strictement inchangée.
 *
 * W316 — rate-limit GÉNÉREUX et DÉDIÉ : cet endpoint est appelé à chaque
 * ajustement d'inclinaison/azimut pendant que le visiteur manipule l'outil
 * interactif (plusieurs appels par minute sont un usage NORMAL, pas un abus).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { fetchPvgisAnnualKwhAtTilt } from '../../lib/roofEstimate';
import { jsonResponse as json } from '../../lib/apiJson';
import { num, preludeRoofProxy } from '../../lib/roofApiCommon';

interface Leg {
  kwc: number;
  tiltDeg: number;
  aspect: number;
}

export const POST: APIRoute = async ({ request }) => {
  // W317/W316 — same-origin + rate-limit + corps JSON + lat/lon : prélude commun (roofApiCommon).
  const pre = await preludeRoofProxy(request, 'roof-yield');
  if ('response' in pre) return pre.response;
  const { body, lat, lon } = pre;

  const rawLegs = Array.isArray(body.legs) ? (body.legs as unknown[]) : [];
  const legs: Leg[] = rawLegs
    .map((l) => l as Record<string, unknown>)
    .map((l) => ({ kwc: num(l.kwc), tiltDeg: num(l.tiltDeg), aspect: num(l.aspect) }))
    .filter((l) => Number.isFinite(l.kwc) && l.kwc > 0 && Number.isFinite(l.tiltDeg) && Number.isFinite(l.aspect));

  if (!legs.length) return json({ ok: false, error: 'aucune jambe valide' }, 400);
  if (legs.length > 4) return json({ ok: false, error: 'trop de jambes' }, 400);

  // Pose : 'building' par défaut (inchangé pour pro-3/4/5/6) ; 'free' pour le toit
  // PLAT racké de pro-7 (W20). Toute autre valeur retombe sur 'building'.
  const mountingplace = body.mountingplace === 'free' ? 'free' : 'building';

  let total = 0;
  for (const leg of legs) {
    const e = await fetchPvgisAnnualKwhAtTilt(lat, lon, leg.kwc, leg.aspect, leg.tiltDeg, fetch, mountingplace);
    if (e === null) return json({ ok: true, annualKwh: null, source: 'estimate' }); // repli table côté page
    total += e;
  }

  return json({ ok: true, annualKwh: Math.round(total), source: 'pvgis' });
};
