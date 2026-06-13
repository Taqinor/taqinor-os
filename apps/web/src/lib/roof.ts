/**
 * Géométrie pure de l'estimateur de toiture (preview privé).
 *
 * Le visiteur trace son toit sur une carte satellite ; ce module convertit ce
 * tracé (sommets lng/lat) en une estimation INDICATIVE : aire géodésique,
 * pavage à l'échelle de panneaux réels (1,7 × 1,0 m, retrait de rive ~0,4 m),
 * puissance crête, production de repli et fourchette d'économies.
 *
 * Aucune dépendance, aucun DOM, aucune carte → testé unitairement
 * (tests/roof.test.ts). Toute la colle carte/tracé/saisie vit dans
 * src/scripts/roof-tool.ts (chargé paresseusement, hors de tout autre bundle).
 *
 * JAMAIS un devis : une fourchette préliminaire. Le chiffrage précis reste
 * l'étude technique (et le lead garde sa propre bande ROI, inchangée).
 */

/** Coordonnée GeoJSON : [longitude, latitude]. */
export type LngLat = [number, number];

// — Hypothèses panneau (standard du marché, modifiables ici uniquement) —
export const PANEL_LENGTH_M = 1.7; // grand côté (paysage : le long de l'axe est-ouest)
export const PANEL_WIDTH_M = 1.0; // petit côté
export const PANEL_WATT = 550; // Wc par panneau
export const SETBACK_M = 0.4; // retrait de rive (sécurité incendie / maintenance)
export const PANEL_GAP_M = 0.02; // jeu entre panneaux

// — Hypothèses énergie (Maroc) —
export const KWH_PER_KWC_YEAR = 1600; // productible de repli quand PVGIS est injoignable
export const TARIFF_MAD_PER_KWH = 1.4; // tarif moyen (aligné sur billRange.ts)
const SELF_CONSUMPTION_LOW = 0.6; // fourchette 60–90 % de la valeur produite
const SELF_CONSUMPTION_HIGH = 0.9;

const WGS84_RADIUS = 6378137; // m
const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;

/**
 * Aire d'un polygone WGS84 en m² (formule sphérique standard, identique à
 * @turf/area). Sens d'enroulement indifférent (valeur absolue). < 3 sommets → 0.
 */
export function geodesicAreaM2(ring: LngLat[]): number {
  if (!Array.isArray(ring) || ring.length < 3) return 0;
  let total = 0;
  for (let i = 0; i < ring.length; i++) {
    const [lng1, lat1] = ring[i];
    const [lng2, lat2] = ring[(i + 1) % ring.length];
    total += (lng2 - lng1) * DEG2RAD * (2 + Math.sin(lat1 * DEG2RAD) + Math.sin(lat2 * DEG2RAD));
  }
  return Math.abs((total * WGS84_RADIUS * WGS84_RADIUS) / 2);
}

/** Appartenance par lancer de rayon (anneau en coordonnées planes quelconques). */
export function pointInPolygon(pt: [number, number], ring: [number, number][]): boolean {
  const [x, y] = pt;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

/** Distance d'un point au segment [a,b] (coordonnées planes). */
function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const [px, py] = p;
  const [ax, ay] = a;
  const [bx, by] = b;
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((px - ax) * dx + (py - ay) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

/** Distance minimale d'un point à la frontière du polygone (toutes les arêtes). */
function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  }
  return min;
}

/** Orientation FR → azimut PVGIS (« aspect » : 0=Sud, -90=Est, 90=Ouest, 180=Nord). */
export function orientationToAspect(orientation: string): number {
  switch (orientation) {
    case 'sud-est':
      return -45;
    case 'sud-ouest':
      return 45;
    case 'est':
      return -90;
    case 'ouest':
      return 90;
    case 'nord':
      return 180;
    case 'sud':
    case 'inconnu':
    default:
      return 0; // hypothèse Sud (meilleur cas) quand l'orientation est inconnue
  }
}

/** Puissance crête (kWc) depuis le nombre de panneaux. */
export function kwcFromPanelCount(count: number, watt = PANEL_WATT): number {
  return (count * watt) / 1000;
}

/** Production annuelle de repli (kWh) quand PVGIS est injoignable. */
export function fallbackAnnualKwh(kwc: number, yieldPerKwc = KWH_PER_KWC_YEAR): number {
  return kwc * yieldPerKwc;
}

/** Fourchette d'économies annuelles (MAD) : 60–90 % de la valeur produite. */
export function annualSavingsBandMad(annualKwh: number): { low: number; high: number } {
  const value = annualKwh * TARIFF_MAD_PER_KWH;
  return {
    low: value * SELF_CONSUMPTION_LOW,
    high: value * SELF_CONSUMPTION_HIGH,
  };
}

export interface PanelLayoutOptions {
  /** Orientation du panneau dans le pavage. Paysage par défaut (grand côté E-O). */
  landscape?: boolean;
  wattPerPanel?: number;
}

export interface PanelLayout {
  /** Chaque panneau : anneau fermé à 5 sommets (lng/lat) prêt pour GeoJSON. */
  panels: LngLat[][];
  count: number;
  kwc: number;
  /** Aire géodésique du tracé (m²). */
  areaM2: number;
}

const MAX_GRID_CELLS = 200000; // garde-fou anti-pavage pathologique

/**
 * Pave le tracé d'une grille de panneaux à l'échelle, alignée nord-sud/est-ouest,
 * en retrait de la rive. Un panneau n'est retenu que si ses 4 coins sont à
 * l'intérieur du tracé ET à au moins SETBACK_M de la frontière — vrai retrait
 * sur n'importe quelle forme de toit, pas seulement les rectangles.
 */
export function layoutPanels(ring: LngLat[], opts: PanelLayoutOptions = {}): PanelLayout {
  const areaM2 = geodesicAreaM2(ring);
  const empty: PanelLayout = { panels: [], count: 0, kwc: 0, areaM2 };
  if (!Array.isArray(ring) || ring.length < 3) return empty;

  const watt = opts.wattPerPanel ?? PANEL_WATT;
  const landscape = opts.landscape ?? true;
  const panelW = landscape ? PANEL_LENGTH_M : PANEL_WIDTH_M; // le long de x (est-ouest)
  const panelH = landscape ? PANEL_WIDTH_M : PANEL_LENGTH_M; // le long de y (nord-sud)
  const cellW = panelW + PANEL_GAP_M;
  const cellH = panelH + PANEL_GAP_M;

  // Projection equirectangulaire locale (origine = premier sommet).
  const lng0 = ring[0][0];
  const lat0 = ring[0][1];
  const cosLat = Math.cos(lat0 * DEG2RAD);
  const toXY = ([lng, lat]: LngLat): [number, number] => [
    (lng - lng0) * DEG2M * cosLat,
    (lat - lat0) * DEG2M,
  ];
  const toLngLat = ([x, y]: [number, number]): LngLat => [
    lng0 + x / (DEG2M * cosLat),
    lat0 + y / DEG2M,
  ];

  const ringXY = ring.map(toXY);
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const [x, y] of ringXY) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }

  const cols = Math.floor((maxX - minX) / cellW);
  const rows = Math.floor((maxY - minY) / cellH);
  if (cols <= 0 || rows <= 0 || (cols + 1) * (rows + 1) > MAX_GRID_CELLS) {
    if ((cols + 1) * (rows + 1) > MAX_GRID_CELLS) return empty; // garde-fou
    return empty;
  }

  const accepted = (corners: [number, number][]): boolean =>
    corners.every((c) => pointInPolygon(c, ringXY) && distToBoundary(c, ringXY) >= SETBACK_M);

  const panels: LngLat[][] = [];
  for (let r = 0; r < rows; r++) {
    const y0 = minY + r * cellH;
    const y1 = y0 + panelH;
    for (let c = 0; c < cols; c++) {
      const x0 = minX + c * cellW;
      const x1 = x0 + panelW;
      const corners: [number, number][] = [
        [x0, y0],
        [x1, y0],
        [x1, y1],
        [x0, y1],
      ];
      if (!accepted(corners)) continue;
      const rringXY: [number, number][] = [...corners, corners[0]];
      panels.push(rringXY.map(toLngLat));
    }
  }

  return {
    panels,
    count: panels.length,
    kwc: kwcFromPanelCount(panels.length, watt),
    areaM2,
  };
}
