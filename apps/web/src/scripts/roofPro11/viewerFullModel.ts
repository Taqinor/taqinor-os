/**
 * ═══════════════════════════════════════════════════════════════════════════
 * VISIONNEUSE PLEINE — LA MOITIÉ PURE (aucun Three.js, aucun MapLibre, aucun DOM)
 * ═══════════════════════════════════════════════════════════════════════════
 * Traduit le `roof_layout` PUBLIC (celui que `parseRoofLayout` de
 * lib/proposition.ts valide déjà, exposé par le backend via
 * `_safe_roof_layout`) en ce que le VRAI moteur de rendu du builder attend :
 * un `ZoneRenderPlan` par pan (`pack` + `grid` + tilt/famille/pose affleurante),
 * exactement la forme que `roofPro11/scene3d.ts` `renderScene` /
 * `appendOtherZones` consomment dans l'ERP.
 *
 * Pourquoi un module séparé : le rendu 3D lui-même n'est pas testable en CI
 * (WebGL), mais TOUT ce qui peut se tromper l'est — le repère ENU des panneaux,
 * la pose (portrait/paysage) du module, le choix du pan « actif », le refus
 * propre d'un layout sans calepinage réel, et le cadrage de la caméra. Cette
 * logique vit donc ICI, testée unitairement ; `viewerFullBoot.ts` ne fait plus
 * que brancher ce plan sur une carte MapLibre + `createScene3d`.
 *
 * RIEN N'EST INVENTÉ : les positions viennent de `zone.geometry.panels`
 * (les cellules RÉELLEMENT posées dans l'ERP, édition manuelle comprise), la
 * pose vient de `inferPanelPose` (lib/proposition.ts — mesure du pas de colonne
 * réel, source de vérité unique déjà testée par WJ130), et les dimensions du
 * module viennent de `lib/roofPro2.ts` (les constantes que scene3d dessine).
 */
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { PANEL2_LONG_M, PANEL2_SHORT_M, PANEL2_WATT } from '../../lib/roofPro2';
import {
  inferPanelPose,
  type RoofLayout,
  type RoofLayoutZone,
  type RoofLayoutZoneGeometry,
  type ViewerPanelPose,
} from '../../lib/proposition';
import {
  type ConfigFamily,
  type PackedPanel,
  type PackResult,
  type PanelGrid,
} from '../../lib/estimatorBrainV2';
import { DEG2M, DEG2RAD } from './constants';
import { type AreaRecord, type ZoneRenderPlan } from './types';

/** Mètres par pixel à l'équateur au zoom 0 — MapLibre travaille en tuiles 512 px
 *  (circonférence terrestre 40 075 016,686 m ÷ 512). `mpp = M_PER_PX_Z0 ×
 *  cos(lat) ÷ 2^zoom` : c'est la relation qu'inverse `zoomForSpanM`. */
export const M_PER_PX_Z0 = 40075016.686 / 512;

/** Part de la boîte occupée par le toit au cadrage initial (le reste = marge
 *  visuelle autour du bâtiment). 0,7 = le toit remplit ~70 % du plus petit côté. */
export const VIEWER_FULL_FILL_RATIO = 0.7;

/** Bornes de zoom du cadrage initial : au-delà de 20 l'imagerie satellite est
 *  ré-échantillonnée (flou) — le client peut toujours zoomer plus à la main. */
export const VIEWER_FULL_MIN_ZOOM = 2;
export const VIEWER_FULL_MAX_ZOOM = 20;

/** Une zone prête à rendre : son plan de rendu (null = pan sans calepinage réel,
 *  scene3d le dessinera en VOLUME NU via `buildBareZoneRing`, comme dans l'ERP)
 *  + ce qu'il faut pour bâtir son `AreaRecord`. */
export interface ViewerFullZone {
  id: string;
  label: string;
  /** Contour [lng,lat] du pan (convention `AreaRecord.vertices`). */
  vertices: LngLat[];
  obstacles: Obstacle[];
  roofType: 'flat' | 'pitched';
  pitchDeg: number;
  facingAzimuthDeg: number;
  neededPanels: number;
  /** Plan de rendu du VRAI moteur, ou null (pan sans `geometry` exploitable). */
  plan: ZoneRenderPlan | null;
  /** Panneaux RÉELLEMENT posés sur ce pan (0 sans plan). */
  panelCount: number;
}

/** Plan complet de la visionneuse : les zones + le pan « actif » + le cadrage. */
export interface ViewerFullPlan {
  zones: ViewerFullZone[];
  /** Index (dans `zones`) du pan rendu comme ACTIF — toujours un pan avec plan.
   *  C'est lui qui reçoit la photo satellite drapée sur sa dalle (scene3d
   *  n'en drape qu'une, celle de la zone active : parité ERP exacte). */
  activeIndex: number;
  /** Centre [lng,lat] de la vue = centroïde de TOUS les sommets — le MÊME que
   *  `buildViewerModel`/`roofLayoutOutlineLatLng` (une moyenne ne dépend pas de
   *  l'ordre), donc la carte et la 3D se centrent sur le même point. */
  center: LngLat;
  /** Plus grande étendue (m) de l'emprise de toutes les zones (E-O ou N-S). */
  spanM: number;
  /** Somme des panneaux RÉELLEMENT posés (jamais une cible dimensionnée). */
  totalPanels: number;
}

/** Aire (m²) d'un anneau plan, valeur absolue (formule du lacet). */
function ringAreaM2(ring: Array<[number, number]>): number {
  let s = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    s += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
  }
  return Math.abs(s) / 2;
}

/**
 * Convertit un contour [lng,lat] en ENU mètres (x=Est, y=Nord) dans le repère
 * `origin` — EXACTEMENT la conversion du builder (`DEG2M`/`cos(lat)` de
 * roofPro11/constants.ts), pour que le contour et les centres de panneaux
 * (`geometry.panels`, déjà en ENU dans ce même repère `geometry.origin`)
 * tombent au même endroit au millimètre près.
 */
export function ringENUFromVertices(vertices: LngLat[], origin: LngLat): Array<[number, number]> {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return vertices.map(([lng, lat]) => [
    (lng - origin[0]) * DEG2M * cosLat,
    (lat - origin[1]) * DEG2M,
  ]);
}

/**
 * Pose de REPLI quand `inferPanelPose` n'est pas concluant (une seule colonne
 * occupée, ou pavage MIXTE PV62 — dont la pose par panneau n'est de toute façon
 * pas publiée par le backend) : MÊME règle que `defaultViewerPose` de
 * lib/proposition.ts — portrait sur pan affleurant, paysage sur toit plat.
 */
function fallbackPose(g: RoofLayoutZoneGeometry): ViewerPanelPose {
  return g.flush ? 'portrait' : 'landscape';
}

/**
 * `PanelGrid` (forme attendue par scene3d) reconstruite depuis le calepinage
 * RÉEL d'un pan. scene3d ne lit de la grille que `panels`, `rowWidthM` et
 * `slopeLenM` : ce sont ces trois-là qui doivent être exacts — les autres
 * champs existent pour honorer le type et restent cohérents (jamais un chiffre
 * client : la puissance affichée au client vient du payload devis, pas d'ici).
 */
export function gridFromGeometry(g: RoofLayoutZoneGeometry): PanelGrid {
  const pose = inferPanelPose(g) ?? fallbackPose(g);
  // Portrait = grand côté DANS LA PENTE (mêmes deux poses que le builder :
  // lib/estimatorBrainV2 `makeGrid('portrait', PANEL2_LONG_M, PANEL2_SHORT_M)`).
  const slopeLenM = pose === 'portrait' ? PANEL2_LONG_M : PANEL2_SHORT_M;
  const rowWidthM = pose === 'portrait' ? PANEL2_SHORT_M : PANEL2_LONG_M;
  const panels: PackedPanel[] = g.panels.map((p) =>
    p.face ? { cx: p.cx, cy: p.cy, face: p.face } : { cx: p.cx, cy: p.cy },
  );
  const tilt = g.tiltDeg * DEG2RAD;
  return {
    panelOrientation: pose,
    count: panels.length,
    kwc: (panels.length * PANEL2_WATT) / 1000,
    // Pas d'empilement : NON publié par le backend et JAMAIS lu par scene3d
    // (les centres réels portent déjà l'espacement) — 0 = « non renseigné ».
    rowPitchM: 0,
    panels,
    slopeLenM,
    rowWidthM,
    footprintPerPanelM2: slopeLenM * Math.cos(tilt) * rowWidthM,
  };
}

/**
 * `PackResult` (forme attendue par scene3d) d'un pan. scene3d n'en lit que
 * `origin`, `ringENU` et `azimuthDeg` ; `portrait`/`landscape`/`best` pointent
 * volontairement sur LA MÊME grille (il n'y a plus rien à optimiser : le pavage
 * est déjà figé, c'est celui vendu au client).
 */
export function packFromZone(zone: RoofLayoutZone, g: RoofLayoutZoneGeometry, grid: PanelGrid): PackResult {
  const ring = ringENUFromVertices(zone.vertices, g.origin);
  const areaM2 = ringAreaM2(ring);
  return {
    origin: [g.origin[0], g.origin[1]] as LngLat,
    ringENU: ring,
    azimuthDeg: g.azimuthDeg,
    tiltDeg: g.tiltDeg,
    family: g.family as ConfigFamily,
    areaM2,
    usableAreaM2: areaM2,
    portrait: grid,
    landscape: grid,
    best: grid,
  };
}

/** Obstacles d'un pan au format builder (`Obstacle`). Les identifiants sont
 *  synthétiques et STABLES (le backend n'en publie pas) : ils ne servent qu'à
 *  la Map interne de scene3d — en lecture seule rien ne les manipule. */
export function obstaclesOfZone(zone: RoofLayoutZone): Obstacle[] {
  return zone.obstacles.map((o, i) => ({
    id: `${zone.id}-obs-${i}`,
    centerLng: o.centerLng,
    centerLat: o.centerLat,
    lengthM: o.lengthM,
    widthM: o.widthM,
  }));
}

/** Plan de rendu d'un pan, ou null si son calepinage réel est absent/vide. */
export function zoneRenderPlan(zone: RoofLayoutZone): ZoneRenderPlan | null {
  const g = zone.geometry;
  if (!g || g.panels.length === 0) return null;
  const grid = gridFromGeometry(g);
  const pack = packFromZone(zone, g, grid);
  return {
    pack,
    grid,
    tiltDeg: g.tiltDeg,
    family: g.family as ConfigFamily,
    flush: g.flush,
    // Tous les panneaux posés sont dessinés : `count` == `grid.panels.length`
    // (jamais `geometry.count`, qui pourrait diverger — on dessine ce qu'on a).
    count: grid.panels.length,
    obstacles: obstaclesOfZone(zone),
  };
}

/**
 * Traduit un `roof_layout` validé en plan de visionneuse complet.
 *
 * Renvoie `null` — refus PROPRE, l'appelant garde alors la visionneuse
 * simplifiée `viewerOnly.ts` — quand :
 *  - le layout est absent / sans zone ;
 *  - AUCUNE zone ne porte de calepinage réel (`geometry`) exploitable : ce sont
 *    les anciens liens (roof_layout d'avant WJ24), où le mode « pleine » n'aurait
 *    QUE des volumes nus à montrer, c'est-à-dire moins que l'existant.
 * Une zone SANS geometry au milieu de zones qui en ont n'est pas un refus : elle
 * est rendue en volume nu, exactement comme dans l'ERP (W78).
 */
export function buildViewerFullPlan(layout: RoofLayout | null | undefined): ViewerFullPlan | null {
  if (!layout || !Array.isArray(layout.zones) || layout.zones.length === 0) return null;

  const zones: ViewerFullZone[] = layout.zones.map((z) => {
    const plan = zoneRenderPlan(z);
    return {
      id: z.id,
      label: z.label,
      vertices: z.vertices.map(([lng, lat]) => [lng, lat] as LngLat),
      obstacles: obstaclesOfZone(z),
      roofType: z.roofType,
      pitchDeg: z.pitchDeg,
      facingAzimuthDeg: z.facingAzimuthDeg,
      neededPanels: z.neededPanels,
      plan,
      panelCount: plan ? plan.grid.panels.length : 0,
    };
  });

  // Pan ACTIF = celui qui porte le PLUS de panneaux posés (le toit principal,
  // celui que le client regarde) parmi ceux qui ont un calepinage réel. Le
  // backend ne publie pas l'`activeAreaId` de l'ERP (whitelist `_safe_roof_layout`)
  // : cette règle est déterministe, jamais aléatoire, et à égalité garde le
  // premier pan (l'ordre de l'ERP).
  let activeIndex = -1;
  for (let i = 0; i < zones.length; i++) {
    if (!zones[i].plan) continue;
    if (activeIndex < 0 || zones[i].panelCount > zones[activeIndex].panelCount) activeIndex = i;
  }
  if (activeIndex < 0) return null;

  // Centre = centroïde de TOUS les sommets (même règle que buildViewerModel).
  let lng0 = 0;
  let lat0 = 0;
  let n = 0;
  for (const z of zones) {
    for (const [lng, lat] of z.vertices) {
      lng0 += lng;
      lat0 += lat;
      n++;
    }
  }
  if (n === 0) return null;
  lng0 /= n;
  lat0 /= n;

  // Emprise (m) autour de ce centre : la plus grande des deux étendues.
  const cosLat = Math.cos(lat0 * DEG2RAD);
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const z of zones) {
    for (const [lng, lat] of z.vertices) {
      const x = (lng - lng0) * DEG2M * cosLat;
      const y = (lat - lat0) * DEG2M;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  const spanM = Math.max(maxX - minX, maxY - minY, 1);

  let totalPanels = 0;
  for (const z of zones) totalPanels += z.panelCount;

  return { zones, activeIndex, center: [lng0, lat0] as LngLat, spanM, totalPanels };
}

/**
 * Zoom MapLibre cadrant une emprise de `spanM` mètres dans une boîte de
 * `viewportPx` pixels, à la latitude `latDeg`. Inverse la relation Web Mercator
 * `mpp = M_PER_PX_Z0 × cos(lat) ÷ 2^zoom`, avec une marge (`fillRatio`) pour que
 * le bâtiment ne touche pas les bords. Borné [2 ; 20] — le client reste libre de
 * zoomer/dézoomer ensuite jusqu'à voir toute la ville (aucune contrainte de
 * `minZoom`/`maxBounds` n'est posée sur la carte).
 */
export function zoomForSpanM(
  spanM: number,
  viewportPx: number,
  latDeg: number,
  fillRatio: number = VIEWER_FULL_FILL_RATIO,
): number {
  const span = Number.isFinite(spanM) && spanM > 0 ? spanM : 1;
  const px = Number.isFinite(viewportPx) && viewportPx > 0 ? viewportPx : 1;
  const ratio = fillRatio > 0 && fillRatio <= 1 ? fillRatio : VIEWER_FULL_FILL_RATIO;
  const cos = Math.max(0.05, Math.cos((Number.isFinite(latDeg) ? latDeg : 0) * DEG2RAD));
  // Mètres par pixel qu'il FAUT pour que `span / ratio` tienne dans la boîte.
  const mppNeeded = span / ratio / px;
  const z = Math.log2((M_PER_PX_Z0 * cos) / mppNeeded);
  if (!Number.isFinite(z)) return VIEWER_FULL_MIN_ZOOM;
  return Math.max(VIEWER_FULL_MIN_ZOOM, Math.min(VIEWER_FULL_MAX_ZOOM, z));
}

/**
 * `AreaRecord[]` du contexte builder pour ces zones. scene3d s'en sert pour
 * dessiner les AUTRES pans (`appendOtherZones` : leurs `renderPlan`, ou leur
 * volume nu à défaut) et pour aligner les faîtières des pans connectés (W107).
 * `result` reste null (aucun chiffre : la visionneuse ne calcule rien).
 */
export function viewerAreaRecords(plan: ViewerFullPlan): AreaRecord[] {
  return plan.zones.map((z) => ({
    id: z.id,
    label: z.label,
    vertices: z.vertices,
    obstacles: z.obstacles,
    roofType: z.roofType,
    pitchDeg: z.pitchDeg,
    facingAzimuthDeg: z.facingAzimuthDeg,
    neededPanels: z.neededPanels,
    neededAuto: false,
    result: null,
    renderPlan: z.plan,
  }));
}
