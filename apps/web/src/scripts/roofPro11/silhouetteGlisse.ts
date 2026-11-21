// ACAL551 — silhouette du panneau (ou du lot) glissé, peinte à la position visée : rouge quand une
// contrainte DURE l'interdit, ambre quand seule une marge réglable (retrait, écart) est franchie.
// La cause reste écrite en toutes lettres dans la note (jamais la couleur seule). Aperçu de geste :
// rien n'est enregistré, rien ne bouge ; la silhouette disparaît au relâchement.
import {
  panelCornersUV, toENU, toUV,
  type FreeCheck, type FreeGeom, type FreePanel, type FreeViolation,
} from '../../lib/freeLayout';
import { enuToLngLat } from './viewerOnly';
import type { LngLat } from '../../lib/roof';

export type NatureSilhouette = 'dur' | 'relachable';
export type SilhouetteFeature = {
  type: 'Feature';
  properties: { nature: NatureSilhouette };
  geometry: { type: 'Polygon'; coordinates: number[][][] };
};

const SOURCE = 'rp9-glisse-silhouette';
const COUCHE = 'rp9-glisse-silhouette';
const ROUGE = '#ff6b6b'; // comme les obstacles
const AMBRE = '#ffb020';

/** Libellé FR d'une contrainte violée — on NOMME ce qui bloque, jamais « impossible ». */
export function violationLabel(v: FreeViolation): string {
  switch (v) {
    case 'outline':
      return 'le panneau sortirait du toit';
    case 'overlap':
      return 'il chevaucherait un autre panneau';
    case 'obstacle':
      return 'il tomberait sur un obstacle (ou son dégagement)';
    case 'setback':
      return 'il passerait sous le retrait de rive que vous avez fixé';
    case 'gap':
      return 'il passerait sous l’écart entre panneaux que vous avez fixé';
    default:
      return 'placement invalide';
  }
}

export const cm = (m: number): string => `${Math.round(m * 100)} cm`;

/** Le texte des distances MESURÉES (rive / voisin) et de ce qui bloque. */
export function texteDeMesure(chk: FreeCheck): string {
  const edge = Number.isFinite(chk.edgeM) ? cm(chk.edgeM) : '—';
  const near = chk.panelM === null ? '—' : cm(chk.panelM);
  const verdict = chk.ok ? '' : ` — ${chk.violations.map(violationLabel).join(', ')}`;
  return `Rive : ${edge} · Voisin : ${near}${verdict}`;
}

/** Contrainte dure ⇒ `dur` (rouge) ; seule une marge réglable franchie ⇒ `relachable` (ambre) ; valide ⇒ rien. */
export function natureSilhouette(check: FreeCheck | null | undefined): NatureSilhouette | null {
  if (!check || check.ok) return null;
  if (check.hard) return 'dur';
  return check.violations.some((v) => v === 'setback' || v === 'gap') ? 'relachable' : null;
}

/** Une silhouette par membre du lot : ses 4 coins (ENU → lng/lat), anneau fermé. */
export function silhouetteGeoJSON(
  coins: readonly (readonly [number, number][])[],
  origine: LngLat,
  nature: NatureSilhouette,
): SilhouetteFeature[] {
  return coins.map((c) => {
    const anneau = c.map(([x, y]) => enuToLngLat(x, y, [origine[0], origine[1]]));
    return { type: 'Feature', properties: { nature }, geometry: { type: 'Polygon', coordinates: [[...anneau, anneau[0]]] } };
  });
}

/** Les silhouettes du lot glissé à (dx, dy) : `null` si la position est valide ou si rien ne se dessine. */
export function silhouetteDuLot(
  g: FreeGeom,
  panels: readonly FreePanel[],
  membres: readonly { index: number; cx: number; cy: number }[],
  dx: number,
  dy: number,
  check: FreeCheck | null | undefined,
  origine: LngLat | null | undefined,
): SilhouetteFeature[] | null {
  const nature = natureSilhouette(check);
  if (!nature || !origine) return null;
  const coins = membres.map((m) => {
    const [cu, cv] = toUV(g, m.cx + dx, m.cy + dy);
    return panelCornersUV(g, cu, cv, panels[m.index]?.angleDeg ?? 0).map(([u, v]) => toENU(g, u, v));
  });
  return silhouetteGeoJSON(coins, origine, nature);
}

interface CarteSilhouette {
  getSource?: (id: string) => unknown;
  addSource?: (id: string, spec: unknown) => void;
  addLayer?: (spec: unknown) => void;
}

/** Peint (ou efface, `null`) les silhouettes : source et couche créées à la demande ; ne plante jamais
 *  sur une carte sans `getSource` ni sur un style pas encore chargé. */
export function peindreSilhouette(map: unknown, features: SilhouetteFeature[] | null): void {
  const carte = map as CarteSilhouette | null;
  if (!carte || typeof carte.getSource !== 'function') return;
  const data = { type: 'FeatureCollection', features: features ?? [] };
  try {
    const src = carte.getSource(SOURCE) as { setData?: (d: unknown) => void } | undefined;
    if (src?.setData) {
      src.setData(data);
      return;
    }
    if (!features || typeof carte.addSource !== 'function' || typeof carte.addLayer !== 'function') return;
    carte.addSource(SOURCE, { type: 'geojson', data });
    carte.addLayer({
      id: COUCHE,
      type: 'fill',
      source: SOURCE,
      paint: { 'fill-color': ['match', ['get', 'nature'], 'dur', ROUGE, AMBRE], 'fill-opacity': 0.45 },
    });
  } catch {
    // style pas chargé : l'aperçu est un confort, jamais une erreur visible
  }
}
