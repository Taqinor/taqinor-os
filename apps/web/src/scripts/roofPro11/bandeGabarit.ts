/**
 * ACAL1432 — poser une zone depuis un gabarit réglementaire de genre « bande » (côté + largeur SAISIS dans les
 * réglages de la société) le long de l'arête voulue du pan actif, sans glisser de rectangle. PUR : aucune largeur ni
 * côté inventé — ce qui manque est rendu comme motif.
 */
import { DEG2M_GEO, DEG2RAD_GEO } from '../../lib/geo';
import { type LngLat } from '../../lib/roof';
import { type GabaritZone } from './types';

/** Direction visée par chaque côté, en (est, nord). `perimetre` = toutes les aretes. */
const DIRECTION: Record<string, [number, number]> = { nord: [0, 1], sud: [0, -1], est: [1, 0], ouest: [-1, 0] };

export type VerdictBande = { ok: true; bandes: LngLat[][] } | { ok: false; motif: string };

/** Vrai quand le gabarit se pose seul (bande) ; un gabarit de contour garde le glissé. */
export const estBande = (g: GabaritZone): boolean => g.genre === 'bande';

export function bandesDepuisGabarit(contour: readonly LngLat[], g: GabaritZone): VerdictBande {
  if (g.largeurM == null) return { ok: false, motif: `La largeur de la bande « ${g.libelle} » n’est pas saisie dans les réglages de la société.` };
  if (!g.cote) return { ok: false, motif: `Le côté de la bande « ${g.libelle} » n’est pas saisi dans les réglages de la société.` };
  if (contour.length < 3) return { ok: false, motif: 'Tracez d’abord le pan : la bande se pose le long de son arête.' };
  const cosLat = Math.cos(contour[0][1] * DEG2RAD_GEO);
  const m = contour.map(([lng, lat]) => [lng * DEG2M_GEO * cosLat, lat * DEG2M_GEO] as [number, number]);
  const aire = m.reduce((s, p, i) => s + (p[0] * m[(i + 1) % m.length][1] - m[(i + 1) % m.length][0] * p[1]), 0);
  const aretes = m.map((p, i) => {
    const q = m[(i + 1) % m.length];
    const [dx, dy] = [q[0] - p[0], q[1] - p[1]];
    const long = Math.hypot(dx, dy);
    const sens = aire > 0 ? 1 : -1; // sommets anti-horaires : la normale sortante est (dy, -dx)
    return { i, p, q, long, n: long > 0 ? [(sens * dy) / long, (-sens * dx) / long] as [number, number] : ([0, 0] as [number, number]) };
  }).filter((a) => a.long > 0);
  const dir = DIRECTION[g.cote];
  const retenues = dir
    ? [aretes.reduce((b, a) => {
        const sa = a.n[0] * dir[0] + a.n[1] * dir[1];
        const sb = b.n[0] * dir[0] + b.n[1] * dir[1];
        return sa > sb + 1e-9 || (Math.abs(sa - sb) <= 1e-9 && a.long > b.long) ? a : b;
      })]
    : aretes; // « perimetre » : tout le tour
  const versGeo = ([x, y]: [number, number]): LngLat => [x / (DEG2M_GEO * cosLat), y / DEG2M_GEO];
  const bandes = retenues.map(({ p, q, n }) => {
    const rentre = (a: [number, number]): [number, number] => [a[0] - n[0] * g.largeurM!, a[1] - n[1] * g.largeurM!];
    return [versGeo(p), versGeo(q), versGeo(rentre(q)), versGeo(rentre(p))];
  });
  return { ok: true, bandes };
}
