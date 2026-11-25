/**
 * T4-X2-010 — LA POSE ENREGISTRÉE D'UN PAN NON ACTIF SE LIT, ELLE NE DISPARAÎT PAS.
 *
 * Constat (test utilisateur, calepinage à plusieurs zones) : un toit de 24 panneaux, rouvert
 * alors qu'un AUTRE pan était actif à l'enregistrement, affichait « 0 modules · 0 kWc · à
 * calculer » et paraissait vide sur la carte, alors que le document portait toujours ses 24
 * panneaux (la barre du projet, qui lit le document, les comptait). Cause : à la relecture,
 * un pan reçoit `result: null` et `renderPlan: null` (`prefill.ts` — `deserializeLayout`) ;
 * or le tableau du site lisait `result` (`zones.ts` → `computePanStats`) et la scène ne
 * dessine les autres pans que par leur `renderPlan` (`scene3d.ts` → `appendOtherZones`).
 *
 * La règle d'ici : un pan NON actif se lit sur ce que le document émet pour lui — sa géométrie
 * enregistrée (`geometrieEnregistree`, réémise verbatim par `serializeLayout`) — et se dessine
 * par le plan que la visionneuse publique bâtit déjà depuis la même géométrie (`zoneRenderPlan`).
 * Aucun chiffre neuf : `count` et `kwc` sont ceux du document.
 */
import { type LngLat } from '../../lib/roof';
import { type RoofLayoutModule, type RoofLayoutZone } from '../../lib/proposition';
import { type AreaRecord, type ZoneRenderPlan } from './types';
import { zoneRenderPlan } from './viewerFullModel';

/** Ce qu'un pan pose : nombre de modules et kWc. */
export interface PoseDuPan {
  panels: number;
  kwc: number;
}

/** La pose ENREGISTRÉE d'un pan (celle que le document émet pour lui), ou `null` sans géométrie. */
export function poseEnregistreeDuPan(a: Pick<AreaRecord, 'geometrieEnregistree'>): PoseDuPan | null {
  const g = a.geometrieEnregistree;
  if (!g || !Array.isArray(g.panels)) return null;
  const panels = Number.isFinite(g.count) ? g.count : g.panels.length;
  return { panels, kwc: Number.isFinite(g.kwc) ? g.kwc : 0 };
}

/**
 * La pose AFFICHÉE d'un pan : le résultat vivant pour le pan actif ; pour un autre pan, sa pose
 * enregistrée (ce que le document dira), sinon l'instantané de la session. Une seule lecture
 * pour la liste des pans, le tableau par pan, le tableau du site et leurs totaux.
 */
export function poseAfficheeDuPan<R extends PoseDuPan>(
  a: Pick<AreaRecord, 'id' | 'geometrieEnregistree'> & { result: R | null },
  actifId: string,
  vivant: R | null,
): PoseDuPan | null {
  if (a.id === actifId) return vivant;
  return poseEnregistreeDuPan(a) ?? a.result;
}

/**
 * Le plan de rendu d'un pan NON actif depuis sa géométrie enregistrée (même construction que la
 * visionneuse publique), pour que la carte le montre posé dès la réouverture. Le pan actif n'en
 * reçoit jamais (la scène pose le sien au premier rendu) ; un plan déjà présent est gardé.
 */
export function poserPlansEnregistres(
  areas: AreaRecord[],
  actifId: string,
  modules?: readonly RoofLayoutModule[] | null,
): void {
  for (const a of areas) {
    if (a.id === actifId || a.renderPlan || a.vertices.length < 3) continue;
    const g = a.geometrieEnregistree;
    if (!g || !Array.isArray(g.panels) || !g.panels.length) continue;
    const zone = {
      id: a.id,
      label: a.label,
      vertices: a.vertices.map(([lng, lat]) => [lng, lat] as LngLat),
      obstacles: [],
      roofType: a.roofType,
      pitchDeg: a.pitchDeg,
      facingAzimuthDeg: a.facingAzimuthDeg,
      neededPanels: a.neededPanels,
      geometry: g,
    } as unknown as RoofLayoutZone;
    const plan: ZoneRenderPlan | null = zoneRenderPlan(zone, Array.isArray(modules) ? modules : null);
    if (plan) a.renderPlan = { ...plan, obstacles: a.obstacles.map((o) => ({ ...o })) };
  }
}
