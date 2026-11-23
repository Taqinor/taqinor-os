// ACAL1328 — COTES D'ARÊTES du toit tracé (maquette Main v2 : « 12,4 m » posé au milieu de chaque bord). Affichage
// seul : les cotes sont recalculées des sommets à chaque re-pose du tracé, rien n'est écrit dans le document. La
// longueur est celle de l'outil de mesure (`mesureUi.ts::segmentDistanceM`) — aucune seconde formule. Le calque
// n'est posé que si l'hôte le demande (atelier ERP), jamais sur le site public ; il se tait en 3D et en présentation.
import { type LngLat } from '../../lib/roof';
import { segmentDistanceM } from './mesureUi';
import { enPresentation, surPresentation } from './presentationCarte';

export const CALQUE_COTES = 'rp9-cotes';
/** Pente de caméra (°) au-delà de laquelle la carte est en 3D (même seuil que `EtapeToit.helpers.js::lireVue`). */
const PENTE_PLAN_MAX = 1;
/** Arête plus courte (m) : deux sommets confondus, aucune cote « 0,0 m ». */
const ARETE_MIN_M = 0.05;

export interface CoteArete { milieu: LngLat; longueurM: number; texte: string }

/** « 12,4 m » : une décimale, virgule. */
export const texteCote = (m: number): string =>
  `${m.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} m`;

/** Les cotes d'un contour : fermé (≥ 3 sommets) ⇒ une par arête, dernière → première comprise ; en cours ⇒ n − 1. */
export function cotesDesAretes(sommets: readonly LngLat[], ferme: boolean): CoteArete[] {
  const n = Array.isArray(sommets) ? sommets.length : 0;
  if (n < 2) return [];
  const cotes: CoteArete[] = [];
  for (let i = 0; i < (ferme && n >= 3 ? n : n - 1); i++) {
    const a = sommets[i];
    const b = sommets[(i + 1) % n];
    const longueurM = segmentDistanceM(a, b);
    if (longueurM < ARETE_MIN_M) continue;
    cotes.push({ milieu: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], longueurM, texte: texteCote(longueurM) });
  }
  return cotes;
}

/** Ce que le calque lit de la carte MapLibre. */
interface CarteCotes {
  addSource(id: string, s: { type: 'geojson'; data: never }): unknown;
  getSource(id: string): { setData(d: never): unknown } | undefined;
  addLayer(l: Record<string, unknown>): unknown;
  getLayoutProperty(id: string, nom: string): unknown;
  setLayoutProperty(id: string, nom: string, v: 'visible' | 'none'): unknown;
  getPitch(): number;
  on(type: string, fn: (e: { sourceId?: string }) => void): unknown;
}

/** Monte le calque (si `demande`) : re-pose des sommets (`rp9-pts`) ⇒ cotes recalculées ; pente ⇒ visibilité. */
export function monterCotesAretes(map: CarteCotes, contours: () => Array<{ sommets: readonly LngLat[]; ferme: boolean }>, demande: boolean): void {
  if (!demande) return;
  const donnees = () => ({
    type: 'FeatureCollection',
    features: contours().flatMap((c) => cotesDesAretes(c.sommets, c.ferme)).map((c) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: c.milieu }, properties: { texte: c.texte },
    })),
  });
  map.addSource(CALQUE_COTES, { type: 'geojson', data: donnees() as never });
  // Même police et même halo que les étiquettes de mesure (`rp9-mesure-label`).
  map.addLayer({
    id: CALQUE_COTES, type: 'symbol', source: CALQUE_COTES,
    layout: { 'text-field': ['get', 'texte'], 'text-size': 12, 'text-font': ['Open Sans Bold', 'Noto Sans Bold'], 'symbol-placement': 'point', 'text-allow-overlap': true },
    paint: { 'text-color': '#ffffff', 'text-halo-color': '#070b1d', 'text-halo-width': 1.6 },
  });
  const visibilite = () => {
    const vis = map.getPitch() <= PENTE_PLAN_MAX && !enPresentation(map) ? 'visible' : 'none';
    if (map.getLayoutProperty(CALQUE_COTES, 'visibility') !== vis) map.setLayoutProperty(CALQUE_COTES, 'visibility', vis);
  };
  map.on('sourcedata', (e) => { if (e?.sourceId === 'rp9-pts') map.getSource(CALQUE_COTES)?.setData(donnees() as never); });
  map.on('pitch', visibilite);
  surPresentation(map, visibilite);
  visibilite();
}
