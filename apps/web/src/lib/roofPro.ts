/**
 * Calepinage « pro » : rangées de panneaux INCLINÉS sur châssis lestés (toit plat).
 *
 * Contrairement à src/lib/roof.ts (`layoutPanels`, panneaux collés à plat), ce
 * module dispose les panneaux en RANGÉES PARALLÈLES espacées, chacune inclinée à
 * `PANEL_TILT_DEG` vers l'orientation choisie. L'espacement inter-rangées réel
 * (anti-ombrage) fait que MOINS de panneaux entrent — c'est PLUS juste, et c'est
 * ce nombre qui pilote kWc → production → économies.
 *
 * Géométrie pure (aucune dépendance, aucun DOM, aucune carte) → testée
 * unitairement (tests/roofPro.test.ts). Le rendu 3D (Three.js) vit dans
 * src/scripts/roof-tool-pro.ts. Décisions géométriques : voir SOLAR_3D_RATIONALE.md.
 *
 * RÉUTILISE roof.ts (aire géodésique, point-dans-polygone, dimensions panneau,
 * puissance crête) — roof.ts n'est PAS modifié. JAMAIS un devis : une fourchette.
 */
import {
  geodesicAreaM2,
  pointInPolygon,
  kwcFromPanelCount,
  PANEL_LENGTH_M,
  PANEL_WIDTH_M,
  type LngLat,
} from './roof';

// — Décisions géométriques (toutes ajustables ici ; cf. SOLAR_3D_RATIONALE.md) —
export const PANEL_TILT_DEG = 12; // inclinaison des panneaux (plage densité 10–15°)
export const ROW_GAP_RISE_FACTOR = 1.5; // jeu inter-rangées = facteur × hauteur projetée
export const PERIMETER_SETBACK_M = 0.5; // retrait de rive
export const PANEL_SIDE_GAP_M = 0.02; // jeu entre panneaux d'une même rangée
export const FRONT_STRUT_M = 0.08; // hauteur du montant avant (bas) du châssis

const WGS84_RADIUS = 6378137; // m
const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;
const MAX_CELLS = 200000; // garde-fou anti-calepinage pathologique

/** Panneau placé : centre en mètres ENU (x=est, y=nord) relatif à `origin`. */
export interface ProPanel {
  cx: number;
  cy: number;
}

export interface ProLayout {
  /** Origine de projection (centroïde du tracé) — pour ancrer la scène 3D. */
  origin: LngLat;
  /** Contour du bâtiment en mètres ENU relatif à `origin` (anneau ouvert). */
  ringENU: [number, number][];
  panels: ProPanel[];
  count: number;
  kwc: number;
  /** Aire géodésique du tracé (m²). */
  areaM2: number;
  /** Angle de l'axe des rangées depuis l'est (rad) — partagé par tous les panneaux. */
  rowAngleRad: number;
  /** Inclinaison des panneaux (rad). */
  tiltRad: number;
  dims: {
    /** Côté le long de la rangée (m, paysage = grand côté). */
    alongRow: number;
    /** Côté dans le sens de la pente (m). */
    slope: number;
    /** Empreinte au sol dans le sens de la pente (m) = slope × cos(tilt). */
    depthFootprint: number;
    /** Hauteur projetée du bord haut (m) = slope × sin(tilt). */
    rise: number;
    /** Hauteur du montant avant (m). */
    frontStrut: number;
  };
}

/** Vecteur horizontal (E,N) vers lequel les panneaux « regardent » (et s'inclinent). */
function facingVector(orientation: string): [number, number] {
  const inv = 1 / Math.SQRT2;
  switch (orientation) {
    case 'nord':
      return [0, 1];
    case 'est':
      return [1, 0];
    case 'ouest':
      return [-1, 0];
    case 'sud-est':
      return [inv, -inv];
    case 'sud-ouest':
      return [-inv, -inv];
    case 'sud':
    case 'inconnu':
    default:
      return [0, -1]; // Sud (meilleur cas) par défaut
  }
}

function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  }
  return min;
}

/**
 * Dispose des rangées de panneaux inclinés (toit plat) sur le tracé. Un panneau
 * n'est retenu que si ses 4 coins (empreinte au sol) sont DANS le tracé ET à au
 * moins `PERIMETER_SETBACK_M` de la rive — vrai retrait sur n'importe quelle forme.
 */
export interface ProLayoutOptions {
  /** Inclinaison des panneaux en degrés (toit plat ≈ 12 ; toit en pente = pente). */
  tiltDeg?: number;
  /** Facteur de jeu inter-rangées (toit plat 1.5 ; pose affleurante = 0). */
  rowGapFactor?: number;
}

export function layoutProRows(ring: LngLat[], orientation = 'sud', opts: ProLayoutOptions = {}): ProLayout {
  const areaM2 = geodesicAreaM2(ring);
  const tiltDeg = opts.tiltDeg ?? PANEL_TILT_DEG;
  const rowGapFactor = opts.rowGapFactor ?? ROW_GAP_RISE_FACTOR;
  const tiltRad = tiltDeg * DEG2RAD;
  const alongRow = PANEL_LENGTH_M; // 1,7 m le long de la rangée (paysage)
  const slope = PANEL_WIDTH_M; // 1,0 m dans le sens de la pente
  const depthFootprint = slope * Math.cos(tiltRad);
  const rise = slope * Math.sin(tiltRad);
  const dims = { alongRow, slope, depthFootprint, rise, frontStrut: FRONT_STRUT_M };

  const empty: ProLayout = {
    origin: ring.length ? ring[0] : [0, 0],
    ringENU: [],
    panels: [],
    count: 0,
    kwc: 0,
    areaM2,
    rowAngleRad: 0,
    tiltRad,
    dims,
  };
  if (!Array.isArray(ring) || ring.length < 3) return empty;

  // Projection equirectangulaire locale, origine = centroïde du tracé.
  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  const cosLat = Math.cos(olat * DEG2RAD);
  const toENU = ([lng, lat]: LngLat): [number, number] => [
    (lng - olng) * DEG2M * cosLat,
    (lat - olat) * DEG2M,
  ];
  const ringENU = ring.map(toENU);

  // Repère des rangées : s = axe de pente (vers l'orientation) ; u = axe des rangées.
  const f = facingVector(orientation);
  const s: [number, number] = f; // les rangées s'empilent le long de s
  const u: [number, number] = [-f[1], f[0]]; // axe long des rangées (perpendiculaire)
  const rowAngleRad = Math.atan2(u[1], u[0]);

  // Coordonnées (u,v) du tracé.
  const ringUV = ringENU.map(([x, y]) => [x * u[0] + y * u[1], x * s[0] + y * s[1]] as [number, number]);
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }

  const rowPitch = depthFootprint + rowGapFactor * rise;
  const colPitch = alongRow + PANEL_SIDE_GAP_M;
  const rows = Math.floor((vMax - vMin) / rowPitch);
  const cols = Math.floor((uMax - uMin) / colPitch);
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) {
    return { ...empty, origin: [olng, olat], ringENU };
  }

  const toENUfromUV = (uu: number, vv: number): [number, number] => [
    uu * u[0] + vv * s[0],
    uu * u[1] + vv * s[1],
  ];
  const ok = (corners: [number, number][]): boolean =>
    corners.every((c) => pointInPolygon(c, ringENU) && distToBoundary(c, ringENU) >= PERIMETER_SETBACK_M);

  const panels: ProPanel[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + PERIMETER_SETBACK_M + r * rowPitch;
    const v1 = v0 + depthFootprint;
    if (v1 > vMax - PERIMETER_SETBACK_M + 1e-6) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + PERIMETER_SETBACK_M + c * colPitch;
      const u1 = u0 + alongRow;
      const corners: [number, number][] = [
        toENUfromUV(u0, v0),
        toENUfromUV(u1, v0),
        toENUfromUV(u1, v1),
        toENUfromUV(u0, v1),
      ];
      if (!ok(corners)) continue;
      const center = toENUfromUV(u0 + alongRow / 2, v0 + depthFootprint / 2);
      panels.push({ cx: center[0], cy: center[1] });
    }
  }

  return {
    origin: [olng, olat],
    ringENU,
    panels,
    count: panels.length,
    kwc: kwcFromPanelCount(panels.length),
    areaM2,
    rowAngleRad,
    tiltRad,
    dims,
  };
}
