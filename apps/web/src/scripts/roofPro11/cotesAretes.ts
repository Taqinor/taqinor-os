// ACAL1328 — COTES D'ARÊTES du toit tracé (maquette Main v2 : « 12,4 m » posé au milieu de chaque bord). Affichage
// seul : les cotes sont recalculées des sommets à chaque re-pose du tracé, rien n'est écrit dans le document. La
// longueur est celle de l'outil de mesure (`mesureUi.ts::segmentDistanceM`) — aucune seconde formule. Le calque
// n'est posé que si l'hôte le demande (atelier ERP), jamais sur le site public ; il se tait en 3D et en présentation.
import { type LngLat } from '../../lib/roof';
import { segmentDistanceM } from './mesureUi';
import { enPresentation, montreALEtape, surEtape, surPresentation } from './presentationCarte';

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
  getLayersOrder?(): string[];
  hasImage?(id: string): boolean;
  addImage?(id: string, image: { width: number; height: number; data: Uint8ClampedArray }, o: Record<string, unknown>): unknown;
  setPaintProperty?(id: string, nom: string, v: unknown): unknown;
  getContainer?(): Element;
  /** T4-B4-008 — repeindre la pilule (même taille) quand le thème change. Absente (carte de test) : sans effet. */
  updateImage?(id: string, image: { width: number; height: number; data: Uint8ClampedArray }): unknown;
}

/** ACAL2042 — le contour FERMÉ du toit choisi (calque propre : la ligne du tracé `rp9-line` est vidée à la fermeture, « la 3D
 *  la remplace ») et ses coins (`rp9-pts`) : trait or plein 2 px, poignée ronde à fond de surface et filet or (maquettes
 *  Main / ToitSombre), aux jetons du thème lus sur la carte. Sommets inchangés ; en Plan seulement, comme les cotes. */
export const CALQUE_CONTOUR = 'rp9-contour-choisi';
const CONTOUR = CALQUE_CONTOUR;
const COINS = 'rp9-pts';
const rgb = (v: string): string | null => {
  const m = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/.exec(v.trim());
  return m ? `rgb(${m[1]}, ${m[2]}, ${m[3]})` : null;
};
function styleContour(el: Element | undefined): Array<[string, string, unknown]> {
  const jeton = (nom: string, repli: string) => (el && typeof getComputedStyle === 'function' ? rgb(getComputedStyle(el).getPropertyValue(nom)) : null) ?? repli;
  return [
    [CONTOUR, 'line-color', jeton('--cal-action', 'rgb(226, 181, 74)')],
    [COINS, 'circle-radius', 6], [COINS, 'circle-color', jeton('--cal-surface', 'rgb(255, 255, 255)')],
    [COINS, 'circle-stroke-color', jeton('--cal-or-trait', 'rgb(201, 154, 43)')], [COINS, 'circle-stroke-width', 2.5],
    // T4-B4-008 — le texte de la cote suit le thème (maquette ToitSombre : clair sur une pilule bleu nuit).
    [CALQUE_COTES, 'text-color', jeton('--cal-texte-1', 'rgb(12, 19, 53)')],
  ];
}

type Rgba = [number, number, number, number];
/** `rgb(…)` / `rgba(…)` (virgules ou espaces, alpha 0-1) → [r, g, b, a 0-255] ; illisible : `null`. */
function rgbaDe(v: string): Rgba | null {
  const m = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+))?/.exec(v.trim());
  return m ? [Number(m[1]), Number(m[2]), Number(m[3]), Math.round((m[4] === undefined ? 1 : Number(m[4])) * 255)] : null;
}
/** T4-B4-008 — fond et filet de la pilule aux jetons du thème (`--cal-flottante`, `--cal-flottante-filet`) : blanche en
 *  clair (maquette Main), bleu nuit à filet clair en sombre (maquette ToitSombre). Sans jeton lisible : la pilule blanche. */
function couleursPilule(el: Element | undefined): { fond: Rgba; filet: Rgba | null } {
  const lire = (nom: string) => (el && typeof getComputedStyle === 'function' ? rgbaDe(getComputedStyle(el).getPropertyValue(nom)) : null);
  return { fond: lire('--cal-flottante') ?? [255, 255, 255, 255], filet: lire('--cal-flottante-filet') };
}

/** ACAL1924 — la couche 3D (bâtiment, dalle, panneaux : `scene3d.ts`, id `rp9-3d`) ajoutée APRÈS ce calque le couvrait :
 *  sur un toit, seul le « m » qui dépassait du bord restait lisible. */
const COUCHE_3D = 'rp9-3d';
const PILULE = 'rp9-cote-pilule';

/** La pilule (maquette Main : « 12,4 m » dans une pilule blanche ; ToitSombre : bleu nuit à filet clair), extensible autour du
 *  texte. `filet` : un trait de 2 px d'image (1 px à l'écran, pixelRatio 2) sur le bord. */
function pilule(fond: Rgba = [255, 255, 255, 255], filet: Rgba | null = null): { width: number; height: number; data: Uint8ClampedArray } {
  const [w, h, r] = [48, 32, 16];
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const dx = Math.max(r - x - 0.5, x + 0.5 - (w - r), 0);
    const dy = Math.max(r - y - 0.5, y + 0.5 - (h - r), 0);
    const d = r - Math.hypot(dx, dy); // distance au bord, vers l'intérieur
    const a = Math.max(0, Math.min(1, d));
    const c = filet && d < 2 ? filet : fond;
    data.set([c[0], c[1], c[2], Math.round(a * c[3])], (y * w + x) * 4);
  }
  return { width: w, height: h, data };
}

/** Monte le calque (si `demande`) : re-pose des sommets (`rp9-pts`) ⇒ cotes recalculées ; pente ⇒ visibilité. */
export function monterCotesAretes(map: CarteCotes, contours: () => Array<{ sommets: readonly LngLat[]; ferme: boolean; actif?: boolean }>, demande: boolean): void {
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
  const contour = () => ({ type: 'FeatureCollection', features: contours().filter((c) => c.actif && c.ferme && c.sommets.length >= 3).map((c) => ({
    type: 'Feature', geometry: { type: 'LineString', coordinates: [...c.sommets, c.sommets[0]] }, properties: {},
  })) });
  map.addSource(CONTOUR, { type: 'geojson', data: contour() as never }); // ACAL2042
  map.addLayer({ id: CONTOUR, type: 'line', source: CONTOUR, layout: { 'line-join': 'round' }, paint: { 'line-color': 'rgb(226, 181, 74)', 'line-width': 2 } });
  // Même police et même halo que les étiquettes de mesure (`rp9-mesure-label`).
  let teinte = couleursPilule(map.getContainer?.());
  const poserPilule = () => { if (map.addImage && !map.hasImage?.(PILULE)) map.addImage(PILULE, pilule(teinte.fond, teinte.filet), { pixelRatio: 2, stretchX: [[16, 32]], stretchY: [[15, 17]], content: [10, 6, 38, 26] }); };
  poserPilule();
  map.on('styleimagemissing', (e) => { if ((e as { id?: string }).id === PILULE) poserPilule(); }); // un changement de style vide les images
  map.addLayer({
    id: CALQUE_COTES, type: 'symbol', source: CALQUE_COTES,
    layout: { 'text-field': ['get', 'texte'], 'text-size': 12, 'text-font': ['Open Sans Bold', 'Noto Sans Bold'], 'symbol-placement': 'point', 'text-allow-overlap': true,
      'icon-image': PILULE, 'icon-text-fit': 'both', 'icon-text-fit-padding': [3, 8, 3, 8], 'icon-allow-overlap': true }, // ACAL1924
    paint: { 'text-color': '#0c1335' },
  });
  // ACAL1924 / ACAL2042 — contour, coins puis cotes au-dessus de la couche 3D (ajoutée après), à chaque repos de la carte où
  // elle est passée dessus ; le style du contour suit le thème (posé seulement s'il change : pas de boucle de rendu).
  const pose = new Map<string, unknown>();
  map.on('idle', () => {
    // `getLayersOrder` compte la couche 3D (personnalisée, absente de `getStyle().layers`) : nos trois calques en FIN de pile.
    const voulus = [CONTOUR, COINS, CALQUE_COTES].filter((id) => map.getLayer?.(id));
    const ordre = map.getLayersOrder?.() ?? [];
    if (ordre.includes(COUCHE_3D) && ordre.slice(-voulus.length).join() !== voulus.join()) for (const id of voulus) map.moveLayer?.(id);
    for (const [id, nom, v] of styleContour(map.getContainer?.())) {
      if (!map.getLayer?.(id) || pose.get(`${id}|${nom}`) === v) continue;
      map.setPaintProperty?.(id, nom, v);
      pose.set(`${id}|${nom}`, v);
    }
    // T4-B4-008 — la pilule suit le thème (repeinte seulement s'il change : pas de boucle de rendu).
    const neuve = couleursPilule(map.getContainer?.());
    if (JSON.stringify(neuve) !== JSON.stringify(teinte)) {
      teinte = neuve;
      if (map.hasImage?.(PILULE)) map.updateImage?.(PILULE, pilule(teinte.fond, teinte.filet));
    }
  });
  const visibilite = () => {
    // Suites v2 — cotes et contour or sont ceux de la maquette Toit (`Main`) : à l'étape Toit seulement quand l'hôte en déclare une.
    const vis = map.getPitch() <= PENTE_PLAN_MAX && !enPresentation(map) && montreALEtape(map, 'toit') ? 'visible' : 'none';
    for (const id of [CALQUE_COTES, CONTOUR]) if (map.getLayoutProperty(id, 'visibility') !== vis) map.setLayoutProperty(id, 'visibility', vis);
  };
  map.on('sourcedata', (e) => {
    if (e?.sourceId !== 'rp9-pts') return;
    map.getSource(CALQUE_COTES)?.setData(donnees() as never);
    map.getSource(CONTOUR)?.setData(contour() as never);
  });
  map.on('pitch', visibilite);
  surPresentation(map, visibilite);
  surEtape(map, visibilite);
  visibilite();
}
