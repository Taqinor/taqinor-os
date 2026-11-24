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
  /** ACAL1924 — passer au-dessus de la couche 3D ; la pilule blanche de la cote. Absents (carte de test) : sans effet. */
  getLayer?(id: string): unknown;
  moveLayer?(id: string): unknown;
  getStyle?(): { layers?: Array<{ id: string }> } | undefined;
  hasImage?(id: string): boolean;
  addImage?(id: string, image: { width: number; height: number; data: Uint8ClampedArray }, o: Record<string, unknown>): unknown;
}

/** ACAL1924 — la couche 3D (bâtiment, dalle, panneaux : `scene3d.ts`, id `rp9-3d`) ajoutée APRÈS ce calque le couvrait :
 *  sur un toit, seul le « m » qui dépassait du bord restait lisible. */
const COUCHE_3D = 'rp9-3d';
const PILULE = 'rp9-cote-pilule';

/** La pilule blanche (maquette Main : « 12,4 m » dans une pilule), extensible autour du texte. */
function pilule(): { width: number; height: number; data: Uint8ClampedArray } {
  const [w, h, r] = [48, 32, 16];
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const dx = Math.max(r - x - 0.5, x + 0.5 - (w - r), 0);
    const dy = Math.max(r - y - 0.5, y + 0.5 - (h - r), 0);
    const a = Math.max(0, Math.min(1, r - Math.hypot(dx, dy)));
    data.set([255, 255, 255, Math.round(a * 255)], (y * w + x) * 4);
  }
  return { width: w, height: h, data };
}

/** Monte le calque (si `demande`) : re-pose des sommets (`rp9-pts`) ⇒ cotes recalculées ; pente ⇒ visibilité. */
export function monterCotesAretes(map: CarteCotes, contours: () => Array<{ sommets: readonly LngLat[]; ferme: boolean }>, demande: boolean): void {
  if (!demande) return;
  // ACAL1924 — une arête PARTAGÉE par deux pans (faîtage) n'est cotée qu'une fois.
  const unique = (c: CoteArete, i: number, toutes: CoteArete[]) => toutes.findIndex((d) => Math.abs(d.milieu[0] - c.milieu[0]) < 1e-7 && Math.abs(d.milieu[1] - c.milieu[1]) < 1e-7) === i;
  const donnees = () => ({
    type: 'FeatureCollection',
    features: contours().flatMap((c) => cotesDesAretes(c.sommets, c.ferme)).filter(unique).map((c) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: c.milieu }, properties: { texte: c.texte },
    })),
  });
  map.addSource(CALQUE_COTES, { type: 'geojson', data: donnees() as never });
  // Même police et même halo que les étiquettes de mesure (`rp9-mesure-label`).
  const poserPilule = () => { if (map.addImage && !map.hasImage?.(PILULE)) map.addImage(PILULE, pilule(), { pixelRatio: 2, stretchX: [[16, 32]], stretchY: [[15, 17]], content: [10, 6, 38, 26] }); };
  poserPilule();
  map.on('styleimagemissing', (e) => { if ((e as { id?: string }).id === PILULE) poserPilule(); }); // un changement de style vide les images
  map.addLayer({
    id: CALQUE_COTES, type: 'symbol', source: CALQUE_COTES,
    layout: { 'text-field': ['get', 'texte'], 'text-size': 12, 'text-font': ['Open Sans Bold', 'Noto Sans Bold'], 'symbol-placement': 'point', 'text-allow-overlap': true,
      'icon-image': PILULE, 'icon-text-fit': 'both', 'icon-text-fit-padding': [3, 8, 3, 8], 'icon-allow-overlap': true }, // ACAL1924
    paint: { 'text-color': '#0c1335' },
  });
  // ACAL1924 — au-dessus de la couche 3D (ajoutée après), à chaque repos de la carte où elle est passée dessus.
  map.on('idle', () => {
    const calques = map.getStyle?.()?.layers ?? [];
    if (map.getLayer?.(COUCHE_3D) && calques[calques.length - 1]?.id !== CALQUE_COTES) map.moveLayer?.(CALQUE_COTES);
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
