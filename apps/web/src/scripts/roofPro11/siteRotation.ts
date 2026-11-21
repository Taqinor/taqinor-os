// ACAL514 — rotation de TOUT le site autour du barycentre des sommets de ses pans. PURE : aucune
// carte, aucun DOM. La seule formule de rotation est `snap.ts::pivoterPoint` (CALX97).
// Le « site » est un document au schéma v2 (ou la composition équivalente de l'atelier) :
// `zones[]`, `outline`, `environment[]`, `exclusionZones[]`, `measurements[]`.
import type { LngLat } from '../../lib/roof';
import { centroideAnneau, pivoterPoint } from './snap';

type Obj = Record<string, unknown>;
export type VerdictSite = { ok: true; site: Obj } | { ok: false; motif: string };

/** Miroir de `backend/.../services/repere.py::CHEMINS_TRANSLATES` pour ce qui TOURNE (sans `pin`
 *  ni `parcelle.vertices`, repères réels) ; le reste est refusé (`CLES_REFUSEES`). */
export const CHEMINS_TOURNES: Record<string, ['point' | 'couple' | 'couples' | 'centre', 'lng_lat' | 'lat_lng']> = {
  outline: ['couples', 'lat_lng'],
  'zones[].vertices': ['couples', 'lng_lat'],
  'zones[].obstacles[]': ['centre', 'lng_lat'],
  'zones[].obstacles[].contour': ['couples', 'lng_lat'],
  'zones[].geometry.origin': ['couple', 'lng_lat'],
  'environment[]': ['centre', 'lng_lat'],
  'environment[].footprint': ['couples', 'lng_lat'],
  'environment[].trace': ['couples', 'lng_lat'],
  'exclusionZones[].vertices': ['couples', 'lng_lat'],
  'exclusionZones[].axe': ['couples', 'lng_lat'],
  'measurements[].points': ['couples', 'lng_lat'],
  'reperesChantier[].point': ['couple', 'lng_lat'], // ACAL599 : repère posé sur le bâtiment, il le suit
};
export const CLES_REFUSEES = ['electrical', 'poseSurfaces', 'shadeObstructions', 'underlay'] as const;

const estObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const porte = (v: unknown): boolean =>
  v != null && !(Array.isArray(v) && v.length === 0) && !(estObj(v) && Object.keys(v).length === 0);

function* porteurs(noeud: unknown, segments: string[]): Generator<unknown> {
  if (segments.length === 0) { yield noeud; return; }
  if (!estObj(noeud)) return;
  const [tete, ...reste] = segments;
  if (tete.endsWith('[]')) {
    const liste = noeud[tete.slice(0, -2)];
    if (Array.isArray(liste)) for (const e of liste) yield* porteurs(e, reste);
  } else if (tete in noeud) yield* porteurs(noeud[tete], reste);
}

function tournerCouple(c: unknown, ordre: string, f: (p: LngLat) => LngLat): unknown {
  if (!Array.isArray(c) || c.length < 2 || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return c;
  const [lng, lat] = ordre === 'lng_lat' ? [c[0], c[1]] : [c[1], c[0]];
  const p = f([lng, lat]);
  return [...(ordre === 'lng_lat' ? p : [p[1], p[0]]), ...c.slice(2)];
}

/** Tourne le site de `angleDeg` (sens horaire, SAISI : aucune valeur par défaut). Un refus nomme la
 *  cause : angle illisible, clé non tournable, pan portant des panneaux posés. */
export function pivoterSite(site: Obj, angleDeg: number): VerdictSite {
  if (!Number.isFinite(angleDeg)) return { ok: false, motif: 'Rotation du site refusée — saisissez un angle en degrés.' };
  for (const cle of CLES_REFUSEES) {
    if (porte(site?.[cle])) return { ok: false, motif: `Le site porte \`${cle}\` : rien à pivoter sans le corrompre.` };
  }
  const zones = (Array.isArray(site?.zones) ? site.zones : []).filter(estObj);
  for (const [i, z] of zones.entries()) {
    const g = estObj(z.geometry) ? z.geometry : estObj(z.geometrieEnregistree) ? z.geometrieEnregistree : {};
    const r = estObj(z.result) ? z.result : {};
    const posés = Number(g.count) > 0 || Number(r.panels) > 0 || (Array.isArray(g.panels) && g.panels.length > 0);
    if (posés) {
      const nom = typeof z.label === 'string' && z.label ? z.label : `Pan ${i + 1}`;
      return { ok: false, motif: `${nom} : des panneaux sont posés — retirez la pose avant de pivoter le site.` };
    }
  }
  const sommets = zones.flatMap((z) => (Array.isArray(z.vertices) ? (z.vertices as LngLat[]) : []));
  const centre = centroideAnneau(sommets);
  if (!centre) return { ok: false, motif: 'Rotation du site refusée — aucun pan n’a encore de contour.' };
  const copie = JSON.parse(JSON.stringify(site)) as Obj;
  const tourner = (p: LngLat): LngLat => pivoterPoint(p, angleDeg, centre);
  for (const [chemin, [forme, ordre]] of Object.entries(CHEMINS_TOURNES)) {
    const segs = chemin.split('.');
    const feuille = segs[segs.length - 1];
    if (forme === 'centre') {
      for (const o of porteurs(copie, segs)) {
        if (!estObj(o) || !Number.isFinite(o.centerLng) || !Number.isFinite(o.centerLat)) continue;
        [o.centerLng, o.centerLat] = tourner([o.centerLng as number, o.centerLat as number]);
      }
      continue;
    }
    for (const parent of porteurs(copie, segs.slice(0, -1))) {
      if (!estObj(parent) || !(feuille in parent)) continue;
      const v = parent[feuille];
      parent[feuille] = forme === 'couple' ? tournerCouple(v, ordre, tourner)
        : Array.isArray(v) ? v.map((c) => tournerCouple(c, ordre, tourner)) : v;
    }
  }
  for (const z of Array.isArray(copie.zones) ? copie.zones : []) {
    if (estObj(z) && Number.isFinite(z.facingAzimuthDeg)) z.facingAzimuthDeg = (((z.facingAzimuthDeg as number) + angleDeg) % 360 + 360) % 360;
  }
  return { ok: true, site: copie };
}
