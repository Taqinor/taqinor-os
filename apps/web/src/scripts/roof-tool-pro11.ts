/**
 * Estimateur de toiture PILOTÉ PAR LA FACTURE — preview privé
 * /preview/toiture-3d-pro-11 (CERVEAUX V7 + V8 — W34 + W35).
 *
 * COPIE de roof-tool-pro10.ts : pro-3..pro-10 restent des baselines INTACTES. W35 ajoute
 * l'OPTIMISEUR CONTRAINT VIVANT au TOIT EN PENTE via estimatorBrainV8 (`solveLivePitched`),
 * jumeau de l'optimiseur plat V7 (W34, conservé ici tel quel) avec deux différences
 * imposées par la physique de la pose affleurante : PAS d'axe inclinaison (l'inclinaison
 * = la pente) et orientation FIXÉE « aligné toit » (azimut = la face ; plein sud / Est-
 * Ouest impossibles, donc omis). Axes LIBRES en pente : pose (portrait/paysage), marge de
 * rive, et la cible « panneaux nécessaires ». Verrouiller un axe le TIENT et re-résout les
 * autres (verrous cumulatifs) ; chaque axe montre sa valeur « Recommandé » ; production
 * PVGIS au (pente, face) réels, pose `mountingplace='building'`, repli table « estimé ».
 * La pose affleurante COPLANAIRE et la 3D du toit en pente sont INCHANGÉES (modèle V6).
 *
 * W34 (toit plat) reste tel quel : `renderSelection()` = alias de `liveResolveFlat()`
 * (estimatorBrainV7), chaque groupe verrouille son axe et re-résout en direct au GPS exact.
 *
 * pro-9 (estimatorBrainV6) corrigeait DEUX choses de pro-8, sans toucher V2/V3/V4/V5 :
 *
 *  FIX 1 — TOIT EN PENTE = VRAI PLAN INCLINÉ. pro-8 gardait le calepinage plat et se
 *  contentait d'incliner chaque panneau : tous restaient à la même hauteur (montage
 *  lesté à plat). Ici, en pente (`flush`), la SURFACE DE TOIT elle-même devient un
 *  plan incliné (sommets de la dalle relevés via `pitchedDeckZ`, la photo reste
 *  géo-alignée) et chaque panneau est posé COPLANAIRE et AFFLEURANT dessus
 *  (`flushPanelCenterAt`, décalage constant le long de la normale) — AUCUN châssis
 *  triangulaire (gardé par `flush`), aucun espacement inter-rangées (coplanaire).
 *  La géométrie pure + ses tests vivent dans estimatorBrainV6 (le build ne voit pas
 *  la carte rendue : tout est ancré sur du vérifiable).
 *
 *  FIX 2 — L'OPTIMISEUR BALAIE *ET AFFICHE* LA MATRICE COMPLÈTE (toit plat).
 *  `fineGridMatrixV6` balaie dense (inclinaison 0→35° pas 5°, azimut sud ±45° pas
 *  15° + aligné toit + Est-Ouest, portrait/paysage, marge gardée/retirée), production
 *  PVGIS au GPS exact (repli table), et RENVOIE toutes les lignes. Le tableau les
 *  AFFICHE — triable (kWh/an, panneaux, % besoin), filtrable par orientation/pose,
 *  l'optimum réel épinglé en tête et badgé « Recommandé ».
 *
 * Reprend le rendu haute fidélité (vrais panneaux Canadian Solar 720 W, Three.js dans
 * une couche MapLibre, vrai sud géo-ancré, soleil/ombres). Le diagnostic enrichi est
 * seulement PRÉ-REMPLI (jamais de lead posté). Aucune nouvelle dépendance.
 *
 * Voir apps/web/BRAIN_V6_NOTES.md, BRAIN_V5_NOTES.md, BRAIN_V4_NOTES.md.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import * as THREE from 'three';
import { PANEL2_THICK_M } from '../lib/roofPro2';
import {
  recommend,
  packConfig,
  productionKwh,
  billToAnnualKwh,
  annualSavingsMad,
  neededPanelsForTarget,
  roofDominantAzimuthDeg,
  tariffForCity,
  TILT_SWEEP_MIN,
  type Recommendation,
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../lib/estimatorBrainV2';
import { PERIMETER_SETBACK_M, PANEL2_LONG_M, PANEL2_SHORT_M } from '../lib/roofPro2';
import {
  reoptimize,
  recommendPitched,
  type FlatPins,
  type FlushPack,
  type FlushGrid,
  type PitchedRecommendation,
  type RoofPlane,
} from '../lib/estimatorBrainV3';
import { pitchedPlaneLeg } from '../lib/estimatorBrainV5';
import {
  PITCHED_FLUSH_STANDOFF_M,
  eaveUpSlopeCoord,
  fineGridMatrixV6,
  flushPanelCenterAt,
  matrixGroupKey,
  pitchedDeckZ,
  pvgisCoarsePairs,
  pvgisMatrixCandidatePairs,
  pvgisRefinePairs,
  sortMatrix,
  type MatrixEvalV6,
  type MatrixSortKey,
  type MatrixV6Result,
} from '../lib/estimatorBrainV6';
import {
  solveLive,
  type AxisLocks,
  type LayoutAxis,
  type LiveConfigEval,
  type LiveSolveResult,
} from '../lib/estimatorBrainV7';
import {
  solveLivePitched,
  type PitchedLayoutAxis,
  type PitchedLiveResult,
  type PitchedMarginAxis,
} from '../lib/estimatorBrainV8';
import { isSimplePolygon, roofAreaLabel, ringBBox, type LngLat } from '../lib/roof';
import {
  obstacleRing,
  obstacleFromDrag,
  defaultObstacle,
  scaledObstacle,
  resizedObstacle,
  OBSTACLE_STEP_FACTOR,
  type Obstacle,
} from '../lib/obstacles';
import { aggregateAreas, areaLabel, emptyResult, type AreaResult } from '../lib/roofAreas';
import { buildSatelliteStyle, roofImageRequest, roofVertexUV, mapboxStaticRoofImageUrl } from '../lib/roofConfig';
import { type RoofTypeSelect } from '../lib/roofTypeSelect';
import { PANEL_KWC, type ScaledProduction, type PerKwcProduction, type SpecificDateProfile } from '../lib/productionEngine';
import {
  yearSeries,
  monthSeries,
  daySeries,
  barGeometry,
  dayCurvePath,
  dayAreaPath,
  cycleMonth,
  cycleDay,
  daysInMonth,
  rescaleByPanels,
  annualSavings,
  monthlySavings,
  dailySavings,
  fmtKwh,
  fmtSavings,
  sourceLabel as prodSourceLabel,
  isEstimate,
  MONTH_NAMES_FR,
  DEFAULT_GRAPH_BOX,
  type ProductionScope,
  type ProductionSource,
  type SvgBox,
} from '../lib/productionWindow';
import {
  HOURS_PER_DAY,
  emptyCurve,
  curveTotal,
  baselineCurve,
  composeConsumption,
  rescaleToDaily,
  selfConsumptionDailyKwh,
  savingsFromHourly,
  annualConsumptionFromDaily,
  batterySizing,
  acWattsFromBtu,
  kwhFromWattsHours,
  evKwhFromDistance,
  applianceFromTypical,
  APPLIANCE_TYPICALS,
  AC_BTU_PRESETS,
  AC_EER_DEFAULT_NON_INVERTER,
  EV_CHARGER_KW_PRESETS,
  EV_KWH_PER_100KM_DEFAULT,
  type Appliance,
  type HourlyCurve,
} from '../lib/applianceConsumption';
import {
  createLayoutState,
  occupiedCount,
  emptyIndices,
  nearestEmptyCell,
  movePanelToPoint,
  movePanelToCell,
  addFirstEmpty,
  removeLast,
  resetToOptimal,
  type LayoutState,
} from '../lib/layoutVariability';

interface InitOptions {
  maptilerKey: string;
  mapboxToken?: string;
  reducedMotion: boolean;
  initialQuery?: string;
  onReady?: () => void;
  // Sélecteur « type de toit » créé EAGERLY par le script de page : il détient les
  // puces `[data-rooftype]` (câblées dès le chargement, donc le bouton « Toit en
  // pente » répond avant ce boot). On honore son choix initial puis on s'abonne.
  roofType?: RoofTypeSelect;
}

const GOLD = '#f3cc66';
const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];
const FLOOR_HEIGHT_M = 3;
const PITCH_VIEW = 58;
const DECK_THK = 0.06;
const FLOORS = 2;
const OBSTACLE_BOX_H_M = 0.8; // hauteur du volume d'obstacle rendu en 3D
const OBSTACLE_TAP_PX = 8; // en deçà : un clic/tap, au-delà : un glissé
const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);
const fmtMad = (n: number) => `${fmt(Math.round(n))} MAD`;

function makeCanadianPanelTexture(): THREE.Texture {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 280;
  const ctx = c.getContext('2d')!;
  const g = ctx.createLinearGradient(0, 0, 512, 280);
  g.addColorStop(0, '#0c0c0f');
  g.addColorStop(1, '#050507');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 512, 280);
  const cols = 24;
  const rowsHalf = 3;
  const pad = 14;
  const seam = 6;
  const w = 512 - pad * 2;
  const hHalf = (280 - pad * 2 - seam) / 2;
  const cw = w / cols;
  const ch = hHalf / rowsHalf;
  ctx.strokeStyle = 'rgba(40,46,60,0.55)';
  ctx.lineWidth = 1;
  for (let half = 0; half < 2; half++) {
    const y0 = half === 0 ? pad : pad + hHalf + seam;
    for (let i = 0; i <= cols; i++) {
      const x = pad + i * cw;
      ctx.beginPath();
      ctx.moveTo(x, y0);
      ctx.lineTo(x, y0 + hHalf);
      ctx.stroke();
    }
    for (let j = 0; j <= rowsHalf; j++) {
      const y = y0 + j * ch;
      ctx.beginPath();
      ctx.moveTo(pad, y);
      ctx.lineTo(pad + w, y);
      ctx.stroke();
    }
  }
  ctx.strokeStyle = 'rgba(20,24,34,0.9)';
  ctx.lineWidth = seam;
  ctx.beginPath();
  ctx.moveTo(pad, 140);
  ctx.lineTo(512 - pad, 140);
  ctx.stroke();
  ctx.strokeStyle = 'rgba(150,156,168,0.85)';
  ctx.lineWidth = 10;
  ctx.strokeRect(5, 5, 502, 270);
  const tex = new THREE.Texture(c);
  tex.needsUpdate = true;
  tex.anisotropy = 8;
  return tex;
}

type TiltMode = 'reco' | number;
type OrientMode = 'auto' | 'portrait' | 'landscape';
// W1 : groupe AZIMUT (plein sud ou aligné sur les arêtes du toit) et groupe MARGE
// de rive (garder la marge de design ou la retirer pour récupérer la rive).
type AzimuthMode = 'south' | 'aligned';
type MarginMode = 'keep' | 'remove';

export function initRoofToolPro8(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }

  const nav = navigator as Navigator & { deviceMemory?: number };
  const lowEnd = (nav.deviceMemory != null && nav.deviceMemory <= 4) || (navigator.hardwareConcurrency || 8) <= 4;
  const shadowSize = lowEnd ? 1024 : 2048;

  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('rp9-map');
  const statusEl = $('rp9-status');
  const billEl = $<HTMLInputElement>('rp9-bill');
  const billKwhEl = $('rp9-bill-kwh');
  const finishBtn = $<HTMLButtonElement>('rp9-finish');
  const clearBtn = $<HTMLButtonElement>('rp9-clear');
  const searchForm = $<HTMLFormElement>('rp9-search');
  const addressEl = $<HTMLInputElement>('rp9-address');
  const configPanel = $('rp9-config');
  // W1 : groupe AZIMUT, masqué quand le toit n'est pas tourné (cf. syncAzimuthGroupVisibility).
  const azimuthGroup = $('rp9-azimuth-group');
  const compassArrow = $('rp9-compass-arrow');
  const areaValueEl = $('rp9-area-value');
  const needInputEl = $<HTMLInputElement>('rp9-need-input');
  const needMinusEl = $<HTMLButtonElement>('rp9-need-minus');
  const needPlusEl = $<HTMLButtonElement>('rp9-need-plus');
  const needNoteEl = $('rp9-need-note');
  // V2 : contrôle d'inclinaison (curseur 5–35° + bouton « reco »).
  const tiltRangeEl = $<HTMLInputElement>('rp9-tilt-range');
  const tiltValueEl = $('rp9-tilt-value');
  const tiltRecoBtn = $<HTMLButtonElement>('rp9-tilt-reco');
  const obstacleBtn = $<HTMLButtonElement>('rp9-obstacle');
  const obstacleClearBtn = $<HTMLButtonElement>('rp9-obstacle-clear');
  const obsEditPanel = $('rp9-obs-edit');
  const obsLengthEl = $<HTMLInputElement>('rp9-obs-length');
  const obsWidthEl = $<HTMLInputElement>('rp9-obs-width');
  const obsDimsEl = $('rp9-obs-dims');
  const obsDeleteBtn = $<HTMLButtonElement>('rp9-obs-delete');
  const obsPlusBtn = $<HTMLButtonElement>('rp9-obs-plus');
  const obsMinusBtn = $<HTMLButtonElement>('rp9-obs-minus');
  // V3 : bouton Optimum, toggle type de toit, et contrôles toit en pente.
  const optimumBtn = $<HTMLButtonElement>('rp9-optimum');
  const optimumNoteEl = $('rp9-optimum-note');
  // V4 : carte « Optimum calculé » (PVGIS source de vérité) — sa propre ligne.
  const optimumCard = $('rp9-optimum-card');
  const optimumLabelEl = $('rp9-optimum-label');
  const optimumSourceEl = $('rp9-optimum-source');
  const optimumKwcEl = $('rp9-optimum-kwc');
  const optimumPanelsEl = $('rp9-optimum-panels');
  const optimumProdEl = $('rp9-optimum-prod');
  const optimumCoverEl = $('rp9-optimum-cover');
  const optimumWhyEl = $('rp9-optimum-why');
  const optimumApplyBtn = $<HTMLButtonElement>('rp9-optimum-apply');
  const flatControlsEl = $('rp9-flat-controls');
  // W35 — les contrôles PROPRES au toit plat (orientation/inclinaison/azimut). « Panneaux »
  // (pose) et « Marge » restent visibles en pente (axes libres), donc hors de ce bloc.
  const flatOnlyEl = $('rp9-flat-only');
  const pitchedControlsEl = $('rp9-pitched-controls');
  const pitchRangeEl = $<HTMLInputElement>('rp9-pitch-range');
  const pitchValueEl = $('rp9-pitch-value');
  const pitchedNoteEl = $('rp9-pitched-note');
  // W50 — Fenêtre « Production estimée » (Année / Mois / Jour). Tous facultatifs :
  // l'outil fonctionne sans elle (repli gracieux).
  const prodWindowEl = $('rp9-prod-window');
  const prodScopeWrap = $('rp9-prod-scope');
  const prodMonthPickerEl = $('rp9-prod-month-picker');
  const prodMonthLabelEl = $('rp9-prod-month-label');
  const prodMonthPrevEl = $<HTMLButtonElement>('rp9-prod-month-prev');
  const prodMonthNextEl = $<HTMLButtonElement>('rp9-prod-month-next');
  const prodDayPickerEl = $('rp9-prod-day-picker');
  const prodDayLabelEl = $('rp9-prod-day-label');
  const prodDayPrevEl = $<HTMLButtonElement>('rp9-prod-day-prev');
  const prodDayNextEl = $<HTMLButtonElement>('rp9-prod-day-next');
  const prodDayResetEl = $<HTMLButtonElement>('rp9-prod-day-reset');
  const prodHeadlineEl = $('rp9-prod-headline');
  const prodSubEl = $('rp9-prod-sub');
  const prodGraphEl = $('rp9-prod-graph');
  const prodSourceEl = $('rp9-prod-source');
  const prodSavingsEl = $('rp9-prod-savings');
  // W68 — « Affiner ma consommation » : courbe horaire éditable + calculateur d'appareils.
  const consWindowEl = $('rp9-cons-window');
  const consToggleEl = $<HTMLButtonElement>('rp9-cons-toggle');
  const consPanelEl = $('rp9-cons-panel');
  const consTotalEl = $('rp9-cons-total');
  const consSelfEl = $('rp9-cons-self');
  const consSavingsEl = $('rp9-cons-savings');
  const consBattEl = $('rp9-cons-batt');
  const consGraphEl = $('rp9-cons-graph');
  const consInputsEl = $('rp9-cons-inputs');
  const consRecalEl = $<HTMLButtonElement>('rp9-cons-recal');
  const applKindEl = $<HTMLSelectElement>('rp9-appl-kind');
  const applAddEl = $<HTMLButtonElement>('rp9-appl-add');
  const applAcEl = $('rp9-appl-ac');
  const acBtuEl = $<HTMLSelectElement>('rp9-ac-btu');
  const acEerEl = $<HTMLInputElement>('rp9-ac-eer');
  const acHoursEl = $<HTMLInputElement>('rp9-ac-hours');
  const acWattsEl = $('rp9-ac-watts');
  const applEvEl = $('rp9-appl-ev');
  const evKwEl = $<HTMLSelectElement>('rp9-ev-kw');
  const evHoursEl = $<HTMLInputElement>('rp9-ev-hours');
  const evKmEl = $<HTMLInputElement>('rp9-ev-km');
  const applNoteEl = $('rp9-appl-note');
  const applListEl = $('rp9-appl-list');
  // W69 — « Personnaliser la disposition » : déplacement/ajout/suppression sur la lattice.
  const layoutWindowEl = $('rp9-layout-window');
  const layoutToggleEl = $<HTMLButtonElement>('rp9-layout-toggle');
  const layoutPanelEl = $('rp9-layout-panel');
  const layoutCountEl = $('rp9-layout-count');
  const layoutKwcEl = $('rp9-layout-kwc');
  const layoutFreeEl = $('rp9-layout-free');
  const layoutCoverEl = $('rp9-layout-cover');
  const layoutMinusEl = $<HTMLButtonElement>('rp9-layout-minus');
  const layoutPlusEl = $<HTMLButtonElement>('rp9-layout-plus');
  const layoutResetEl = $<HTMLButtonElement>('rp9-layout-reset');
  const layoutGridEl = $('rp9-layout-grid');
  const layoutNoteEl = $('rp9-layout-note');
  // « Plusieurs zones » — tous facultatifs (le harness jsdom ne les fournit pas) :
  // chaque accès est null-gardé, l'outil monte et tourne sans aucun de ces éléments.
  const addAreaBtn = $<HTMLButtonElement>('rp9-add-area');
  const areasWindowEl = $('rp9-areas-window');
  const areasListEl = $('rp9-areas-list');
  const areasTotalPanelsEl = $('rp9-areas-total-panels');
  const areasTotalKwcEl = $('rp9-areas-total-kwc');
  const areasTotalProdEl = $('rp9-areas-total-prod');
  const areasTotalSavingsEl = $('rp9-areas-total-savings');
  if (!mapEl) return;

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

  // Readout « surface du toit » : aire BRUTE du tracé (obstacles non déduits),
  // mise à jour à chaque sommet/retracé, effacée quand le tracé est vide.
  const updateAreaReadout = () => {
    if (areaValueEl) areaValueEl.textContent = roofAreaLabel(vertices) ?? '—';
  };

  // — État —
  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  let obstacleMode = false;
  let obstacles: Obstacle[] = [];
  let selectedObsId: string | null = null;
  let obsCounter = 0;
  // Glissé en cours pour dessiner un obstacle.
  let drawStart: { lngLat: LngLat; point: maplibregl.Point } | null = null;
  let drawing = false;
  let suppressClick = false; // ignore le « click » de synthèse après un glissé
  // Change C : déplacement (glissé) d'un obstacle existant. Delta-based (newCenter =
  // centre de départ + déplacement lng/lat) → robuste au parallaxe en vue inclinée.
  let moveObs: { id: string; startLng: number; startLat: number; centerLng: number; centerLat: number; moved: boolean } | null = null;
  let rec: Recommendation | null = null;
  // V3 — type de toit (plat = modèle existant, défaut ; pente = pose affleurante),
  // pente + face SAISIES (imposent l'inclinaison et l'azimut de l'array), et le
  // résultat pente courant. `pinned` = axes que l'utilisateur a explicitement figés
  // (le bouton Optimum tient ces axes et re-résout le reste).
  type RoofType = 'flat' | 'pitched';
  let roofType: RoofType = 'flat';
  let pitchDeg = 22;
  let facingAzimuthDeg = 180;
  let pitchedRec: PitchedRecommendation | null = null;
  const pinned = new Set<'family' | 'tilt' | 'orient' | 'azimuth' | 'margin'>();

  // Les obstacles sont stockés par centre + dimensions ; le cerveau reçoit leurs
  // rectangles lng/lat comme obstructions (zones d'exclusion).
  const obstructionRings = (): LngLat[][] => obstacles.map(obstacleRing);
  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const dimsLabel = (o: Obstacle) => `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;
  let centroid: LngLat = [0, 0];
  let centroidLat = 33.5;
  let useRecommended = true;
  let sel: { family: ConfigFamily; tilt: TiltMode; orient: OrientMode; azimuth: AzimuthMode; margin: MarginMode } = {
    family: 'south',
    tilt: 'reco',
    orient: 'auto',
    azimuth: 'south',
    margin: 'keep',
  };
  // Affinage PVGIS stocké en rendement (kWh/kWc/an) pour suivre le nombre de
  // panneaux RÉELLEMENT posé (qui peut descendre sous le besoin si le toit/les
  // obstacles contraignent) — jamais un kWh absolu figé sur le besoin.
  let pvgisPerKwc: number | null = null;

  // W1 — Marge de rive courante (m) déduite du toggle « Marge ». keep = marge de
  // design (PERIMETER_SETBACK_M) ; remove = pleine rive (0).
  const setbackOf = (): number => (sel.margin === 'remove' ? 0 : PERIMETER_SETBACK_M);

  // W1 — Azimut de FACE pour l'array sud, selon le groupe AZIMUT : « aligné toit »
  // suit les arêtes (rec.roofAlignedAzimuthDeg), sinon plein sud (180).
  const azimuthDegOf = (): number =>
    sel.azimuth === 'aligned' && rec ? rec.roofAlignedAzimuthDeg : 180;

  // W1 — Aspect PVGIS (écart au sud) d'une famille selon son azimut de face réel :
  // Sud → azimut−180 ; E-O → azimut−90.
  const aspectForLeg = (family: ConfigFamily, azimuthDeg: number): number =>
    family === 'eastwest' ? azimuthDeg - 90 : azimuthDeg - 180;

  // W1 — Cache PVGIS partagé entre TOUS les réglages — clé lat,lon|famille|tilt|azimut.
  // Une même config n'est jamais re-demandée ; un échec/null bascule en repli table
  // (mémorisé pour ne pas re-tenter). Réutilisé entre les bascules d'options.
  const pvgisCache = new Map<string, number | null>();
  const pvgisKey = (family: ConfigFamily, tiltDeg: number, azimuthDeg: number): string =>
    `${centroid[1].toFixed(5)},${centroid[0].toFixed(5)}|${family}|${tiltDeg}|${Math.round(azimuthDeg)}`;

  // V4 — rendement spécifique PVGIS (kWh/kWc/an) par (tilt|aspect) au GPS exact,
  // pose 'free' (toit plat racké). Cache partagé/réutilisé ; null = repli table
  // mémorisé. Jeton anti-course : seul le dernier tracé/réglage applique son résultat.
  const v4YieldCache = new Map<string, number | null>();
  const v4Key = (tiltDeg: number, aspect: number): string => `${Math.round(tiltDeg)}|${Math.round(aspect * 10) / 10}`;
  // V6 — MATRICE complète (toit plat) : le balayage dense RENVOYÉ pour affichage
  // (toutes les lignes), avec l'état de tri/filtre du tableau. Le rendement spécifique
  // PVGIS partage le cache V4 (mêmes (tilt|aspect)). Jeton anti-course propre.
  let matrixResult: MatrixV6Result | null = null;
  let matrixSort: { key: MatrixSortKey; dir: 'asc' | 'desc' } = { key: 'annualKwh', dir: 'desc' };
  let matrixFilter = 'all';
  let matrixToken = 0;

  // W34 — OPTIMISEUR CONTRAINT VIVANT (toit plat, cerveau V7). Dernier résultat du
  // solveur (gagnant contraint + valeurs « Recommandé » par axe). `liveToken` +
  // `liveTiltTimer` débattent l'affinage PVGIS d'une inclinaison verrouillée hors grille.
  let liveResult: LiveSolveResult | null = null;
  let liveToken = 0;
  let liveTiltTimer: ReturnType<typeof setTimeout> | null = null;

  // W35 — OPTIMISEUR CONTRAINT VIVANT (toit en pente, cerveau V8). Mêmes règles que le
  // plat, mais seuls axes libres = pose + marge (inclinaison = pente, azimut = face,
  // imposés). `pitchedLocks` = axes verrouillés ; le besoin partage `neededAuto`.
  const pitchedLocks: { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis } = {};
  let pitchedLiveResult: PitchedLiveResult | null = null;

  // V5 — toit en pente : rendement spécifique PVGIS (kWh/kWc/an) du SEUL plan
  // (pente, face), pose 'building' (affleurant, moins ventilé). Indépendant de la
  // taille → interrogé à kWc=1 et mis à l'échelle. Cache par (pente|face), repli
  // table. Jeton anti-course propre au mode pente.
  const pitchedYieldCache = new Map<string, number | null>();
  const pitchedKey = (pitch: number, facing: number): string => `${Math.round(pitch)}|${Math.round(facing)}`;
  let pitchedToken = 0;
  let pitchedPvgisPerKwc: number | null = null;

  // ═══════════ W50 — FENÊTRE « PRODUCTION ESTIMÉE » (Année / Mois / Jour) ═══════════
  // Reflète le plan courant (winner de l'optimiseur). On garde la production PAR 1 kWc
  // renvoyée par /api/roof-production pour pouvoir RESCALER côté client (édition du nombre
  // de panneaux) sans nouvel appel serveur. Jeton anti-course : seule la dernière requête
  // applique son résultat. Toutes les figures « estimé » si la source est le repli interne.
  interface ProdPlaneKey {
    lat: number;
    lon: number;
    tiltDeg: number;
    aspect: number;
    mountingplace: 'building' | 'free';
  }
  let prodScope: ProductionScope = 'year';
  let prodMonth = 0; // index 0–11 (mois sélectionné)
  let prodDay: number | null = null; // null = jour TYPE du mois ; sinon date précise (1-based)
  let prodToken = 0;
  let prodPerKwc: PerKwcProduction | null = null; // production PAR 1 kWc (pour rescale client)
  let prodScaled: ScaledProduction | null = null; // production mise à l'échelle (panneaux courants)
  let prodSpecificDate: SpecificDateProfile | null = null; // profil de la date précise (mis à l'échelle)
  let prodSource: ProductionSource = 'estimate';
  let prodPanels = 0;
  let prodTarget = 0; // besoin annuel (kWh) pour les économies plafonnées
  let prodPlaneKey = '';
  const SVG_BOX: SvgBox = DEFAULT_GRAPH_BOX;

  // ═══════════ W68 — VARIABILITÉ de consommation (« Affiner ma consommation ») ═══════════
  // `consCurve` = courbe horaire de conso (24 kWh) effectivement utilisée pour
  // l'autoconsommation/les économies/la batterie. `consHandEdited` : l'utilisateur a édité
  // la courbe à la main (sinon elle est recomposée du socle + appareils à chaque changement
  // de facture). `consAppliances` : appareils ajoutés. `consDailyTarget` = kWh/jour issu de
  // la facture (socle). `consMode` : le panneau « Affiner » est-il ouvert ?
  let consMode = false;
  let consCurve: HourlyCurve = emptyCurve();
  let consHandEdited = false;
  let consAppliances: Appliance[] = [];
  let consDailyTarget = 0; // socle journalier (kWh) dérivé de la facture
  let consApplCounter = 0;

  // ═══════════ W69 — VARIABILITÉ de disposition (« Personnaliser la disposition ») ═══════════
  // `layoutMode` : le mode est-il actif ? `layoutState` : la lattice (toutes cellules
  // valides du pavage gagnant) + occupation. `layoutOptimalCount` : comptage de
  // l'optimiseur (pour la réinitialisation). `layoutSel` : index du panneau sélectionné
  // (repli tactile). `layoutPlan` : le pavage gagnant courant (pack + grid + tilt + family
  // + flush) pour re-rendre la 3D avec l'occupation personnalisée.
  let layoutMode = false;
  let layoutState: LayoutState | null = null;
  let layoutOptimalCount = 0;
  let layoutSel: number | null = null;
  let layoutPlan:
    | { pack: PackResult; grid: PanelGrid; tiltDeg: number; family: ConfigFamily; flush: boolean }
    | null = null;

  const prodPlaneKeyOf = (p: ProdPlaneKey): string =>
    `${p.lat.toFixed(4)},${p.lon.toFixed(4)},${Math.round(p.tiltDeg)},${Math.round(p.aspect)},${p.mountingplace}`;
  // Plafond « panneaux nécessaires » (Change A) : dicté par la facture, PERSISTE à
  // travers les bascules d'orientation/calepinage et l'édition d'obstacles. Posés =
  // min(neededPanels, ce qui tient). `neededAuto` : tant que vrai, on le redérive de
  // la facture ; un réglage manuel (+/−/saisie) le fige jusqu'au prochain changement
  // de facture ou nouveau tracé.
  let neededPanels = 0;
  let neededAuto = true;

  // ═══════════ « PLUSIEURS ZONES » — modèle additif « zone sélectionnée » ═══════════
  // L'utilisateur trace la zone 1 (flux existant), puis peut en AJOUTER d'autres ; le
  // total SOMME tout. RISQUE MINIMAL : on ne rend JAMAIS toutes les zones en même temps
  // en 3D — la 3D montre la SEULE zone active (renderScene inchangé). Chaque zone est un
  // enregistrement : sa géométrie + un instantané de résultat. La zone ACTIVE est éditée
  // par le pipeline mono-zone existant ; sa géométrie VIVE EST l'état `vertices`/`obstacles`/
  // `roofType`/`pitchDeg`/`facingAzimuthDeg`/`neededPanels`/`neededAuto`. `activeAreaId`
  // désigne la zone en cours. On initialise avec UNE zone active (comportement mono-zone
  // strictement inchangé tant qu'il n'y a qu'une zone).
  // Plan de RE-RENDU d'une zone : tout ce qu'il faut pour redessiner son bâtiment +
  // ses panneaux SANS ré-optimiser. Stocké sur la zone ACTIVE à chaque renderScene ;
  // les AUTRES zones sont re-dessinées (subduées) à partir de leur plan, à leur vraie
  // position relative (offset GPS → ENU). `count` = nombre de panneaux RÉELLEMENT posés.
  interface ZoneRenderPlan {
    pack: PackResult;
    grid: PanelGrid;
    tiltDeg: number;
    family: ConfigFamily;
    flush: boolean;
    count: number;
    obstacles: Obstacle[];
  }
  interface AreaRecord {
    id: string;
    label: string;
    vertices: LngLat[];
    obstacles: Obstacle[];
    roofType: RoofType;
    pitchDeg: number;
    facingAzimuthDeg: number;
    neededPanels: number;
    neededAuto: boolean;
    result: AreaResult | null;
    renderPlan: ZoneRenderPlan | null;
  }
  let areaCounter = 0;
  const newAreaRecord = (): AreaRecord => {
    const id = `area-${++areaCounter}`;
    return {
      id,
      label: areaLabel(areaCounter - 1),
      vertices: [],
      obstacles: [],
      roofType: 'flat',
      pitchDeg: 22,
      facingAzimuthDeg: 180,
      neededPanels: 0,
      neededAuto: true,
      result: null,
      renderPlan: null,
    };
  };
  const areas: AreaRecord[] = [newAreaRecord()];
  let activeAreaId = areas[0].id;
  const activeArea = (): AreaRecord | undefined => areas.find((a) => a.id === activeAreaId);

  const monthlyBill = (): number => {
    const raw = parseFloat((billEl?.value || '').replace(/\s/g, '').replace(',', '.'));
    return Number.isFinite(raw) && raw > 0 ? raw : 0;
  };

  // — Three.js —
  const map = new maplibregl.Map({
    container: mapEl,
    // Imagerie satellite : Mapbox (Maxar Vivid, plus nette sur le Maroc) si un
    // token PUBLIC_MAPBOX_TOKEN est posé, sinon REPLI inchangé sur le style
    // hybride MapTiler. La géolocalisation/recherche reste sur MapTiler (clé
    // toujours requise) — Mapbox n'apporte QUE l'imagerie.
    style: buildSatelliteStyle({ maptilerKey: opts.maptilerKey, mapboxToken: opts.mapboxToken }) as maplibregl.StyleSpecification | string,
    center: MOROCCO_CENTER,
    zoom: 5,
    pitch: 0,
    maxPitch: 75,
    attributionControl: { compact: true },
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });
  opts.onReady?.();

  map.on('error', (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[roof-tool-pro6] erreur carte (non bloquante) :', msg);
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.doubleClickZoom.disable();

  const updateCompass = () => {
    if (compassArrow) compassArrow.style.transform = `rotate(${-map.getBearing()}deg)`;
  };
  map.on('rotate', updateCompass);
  map.on('pitch', updateCompass);
  updateCompass();

  let renderer: THREE.WebGLRenderer | null = null;
  let scene: THREE.Scene | null = null;
  let sceneRoot: THREE.Group | null = null;
  let threeCamera: THREE.Camera | null = null;
  let sun: THREE.DirectionalLight | null = null;
  let modelMatrix: THREE.Matrix4 | null = null;
  const panelTex = makeCanadianPanelTexture();
  // Change B : photo satellite posée sur la face supérieure du toit. Texture mise en
  // cache par bbox (chargée UNE fois par tracé) ; matériau du deck courant suivi pour
  // l'appliquer dès l'arrivée de l'image. Repli silencieux (deck gris) si pas de token
  // Mapbox ou échec de chargement.
  let roofTex: THREE.Texture | null = null;
  let roofTexKey = '';
  let deckMaterial: THREE.MeshStandardMaterial | null = null;
  // Change C : meshes d'obstacles 3D (transparents) suivis par id pour les DÉPLACER
  // en direct pendant un glissé, et l'origine ENU de la scène courante (centroïde).
  const obstacleMeshes = new Map<string, THREE.Mesh>();
  let sceneOrigin: LngLat = [0, 0];

  const AXIS_X = new THREE.Vector3(1, 0, 0);
  const AXIS_Z = new THREE.Vector3(0, 0, 1);
  const _q = new THREE.Quaternion();
  const _qz = new THREE.Quaternion();
  const _qx = new THREE.Quaternion();
  const _scl = new THREE.Vector3(1, 1, 1);
  const compose = (px: number, py: number, pz: number, rotZ: number, rotX: number): THREE.Matrix4 => {
    _qz.setFromAxisAngle(AXIS_Z, rotZ);
    _qx.setFromAxisAngle(AXIS_X, rotX);
    _q.copy(_qz).multiply(_qx);
    return new THREE.Matrix4().compose(new THREE.Vector3(px, py, pz), _q, _scl);
  };

  const empty = { type: 'FeatureCollection', features: [] } as const;

  const customLayer = {
    id: 'rp9-3d',
    type: 'custom' as const,
    renderingMode: '3d' as const,
    onAdd(_m: maplibregl.Map, gl: WebGLRenderingContext | WebGL2RenderingContext) {
      threeCamera = new THREE.Camera();
      scene = new THREE.Scene();
      sceneRoot = new THREE.Group();
      scene.add(sceneRoot);
      scene.add(new THREE.AmbientLight(0xb9c8ee, 0.5));
      scene.add(new THREE.HemisphereLight(0xcfe0ff, 0x20242e, 0.5));
      sun = new THREE.DirectionalLight(0xfff2d6, 2.5);
      sun.castShadow = true;
      sun.shadow.mapSize.set(shadowSize, shadowSize);
      sun.shadow.bias = -0.0005;
      sun.shadow.normalBias = 0.03;
      scene.add(sun);
      scene.add(sun.target);
      renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: !lowEnd });
      renderer.autoClear = false;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
    },
    render(_gl: WebGLRenderingContext | WebGL2RenderingContext, args: maplibregl.CustomRenderMethodInput) {
      if (!renderer || !scene || !threeCamera || !modelMatrix) return;
      const m = new THREE.Matrix4().fromArray(Array.from(args.defaultProjectionData.mainMatrix));
      threeCamera.projectionMatrix = m.multiply(modelMatrix);
      renderer.resetState();
      renderer.render(scene, threeCamera);
    },
    // W70 — libère TOUTES les ressources GPU quand la couche est retirée (navigation
    // client Astro, démontage de la carte) : meshes/matériaux de scène (disposeScene),
    // textures partagées (panneau + photo de toit) et le WebGLRenderer lui-même. Sans
    // cela le renderer + ses textures fuient à chaque départ de la page.
    onRemove(_m: maplibregl.Map, _gl: WebGLRenderingContext | WebGL2RenderingContext) {
      disposeScene();
      panelTex.dispose();
      roofTex?.dispose();
      roofTex = null;
      renderer?.dispose();
      renderer = null;
    },
  };

  /** Libère un objet (et sa géométrie/ses matériaux). L'étiquette d'obstacle porte
   *  une texture canvas UNIQUE par rendu → libérée ici ; les textures PARTAGÉES
   *  (texture de panneau, photo de toit en cache) ne sont jamais touchées. */
  function disposeObject(obj: THREE.Object3D) {
    const holder = obj as THREE.Mesh & { material?: THREE.Material | THREE.Material[] };
    const isSprite = (obj as THREE.Sprite).isSprite === true;
    // La géométrie d'un Sprite est PARTAGÉE (interne à three) → ne pas la libérer.
    if (!isSprite) holder.geometry?.dispose?.();
    const mat = holder.material;
    const mats = Array.isArray(mat) ? mat : mat ? [mat] : [];
    for (const m of mats) {
      if (isSprite) (m as THREE.SpriteMaterial).map?.dispose?.(); // texture canvas unique
      m.dispose();
    }
  }

  function disposeScene() {
    if (!sceneRoot) return;
    for (const child of [...sceneRoot.children]) {
      child.traverse(disposeObject); // inclut les arêtes/étiquettes enfants
      sceneRoot.remove(child);
    }
  }

  function setOrigin(origin: LngLat) {
    const mc = maplibregl.MercatorCoordinate.fromLngLat(origin, 0);
    const sUnit = mc.meterInMercatorCoordinateUnits();
    modelMatrix = new THREE.Matrix4().makeTranslation(mc.x, mc.y, mc.z).scale(new THREE.Vector3(sUnit, -sUnit, sUnit));
  }

  function makeIM(geo: THREE.BufferGeometry, mat: THREE.Material | THREE.Material[], matrices: THREE.Matrix4[], cast = true, receive = false): THREE.InstancedMesh | null {
    if (!matrices.length) return null;
    const im = new THREE.InstancedMesh(geo, mat as THREE.Material, matrices.length);
    im.castShadow = cast;
    im.receiveShadow = receive;
    for (let i = 0; i < matrices.length; i++) im.setMatrixAt(i, matrices[i]);
    im.instanceMatrix.needsUpdate = true;
    return im;
  }

  /** UV de la face supérieure du toit = VRAIE position (Web Mercator) de chaque
   *  sommet dans l'étendue EXACTE de l'image satellite (calculée par
   *  roofImageRequest, et NON la bbox demandée — l'endpoint Static élargit la bbox).
   *  Le sommet, en ENU, est reprojeté en lng/lat via l'origine de la scène puis en
   *  UV. Le mesh ÉTANT le polygone tracé (ShapeGeometry), seule l'imagerie du
   *  contour est peinte, alignée au pixel près sur le calepinage et les obstacles. */
  function setDeckUVs(geo: THREE.BufferGeometry, origin: LngLat, extent: [number, number, number, number]) {
    const cosLat = Math.cos(origin[1] * DEG2RAD);
    const pos = geo.attributes.position;
    const uv = new Float32Array(pos.count * 2);
    for (let i = 0; i < pos.count; i++) {
      const lng = origin[0] + pos.getX(i) / (DEG2M * cosLat);
      const lat = origin[1] + pos.getY(i) / DEG2M;
      const [u, v] = roofVertexUV(lng, lat, extent);
      uv[i * 2] = u;
      uv[i * 2 + 1] = v;
    }
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  }

  /** Pose (ou réapplique) la photo satellite sur la face supérieure du toit. Image
   *  demandée par centre+zoom (étendue déterministe) → cachée par cette étendue,
   *  chargée une seule fois par tracé. Sans token Mapbox ou en cas d'échec : deck
   *  gris inchangé (gracieux). */
  function applyRoofPhoto(deck: THREE.Mesh, mat: THREE.MeshStandardMaterial, origin: LngLat) {
    deckMaterial = mat;
    if (!opts.mapboxToken || vertices.length < 3) return;
    const req = roofImageRequest(ringBBox(vertices));
    setDeckUVs(deck.geometry, origin, req.extent);
    const key = req.extent.map((n) => n.toFixed(6)).join(',');
    if (roofTex && roofTexKey === key) {
      mat.map = roofTex;
      mat.color.set(0xffffff);
      mat.needsUpdate = true;
      return;
    }
    const url = mapboxStaticRoofImageUrl(opts.mapboxToken, req.center, req.zoom, req.w, req.h);
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const tex = new THREE.Texture(img);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 8;
      tex.needsUpdate = true;
      // W70 — libère l'ANCIENNE texture de toit avant de la remplacer (fuite GPU à chaque
      // re-tracé sur une nouvelle bbox). On NE libère QUE l'orpheline : si la texture courante
      // est encore montée sur le matériau du deck (.map), three la libérera à la prochaine
      // recomposition du matériau — la libérer ici corromprait le rendu en cours.
      if (roofTex && roofTex !== tex && roofTex !== deckMaterial?.map) roofTex.dispose();
      roofTex = tex;
      roofTexKey = key;
      // Réapplique sur le deck COURANT (un bascule a pu le recréer entre-temps).
      if (deckMaterial) {
        deckMaterial.map = tex;
        deckMaterial.color.set(0xffffff);
        deckMaterial.needsUpdate = true;
        map.triggerRepaint();
      }
    };
    img.onerror = () => {
      /* imagerie indisponible → on garde le deck gris, sans erreur visible */
    };
    img.src = url;
  }

  /** Étiquette de taille (« L × l m ») dessinée sur un canevas → sprite 3D posé SUR
   *  la boîte d'obstacle (Change B). Enfant du mesh : suit la boîte quand on la
   *  déplace. Toujours face caméra, sans test de profondeur (lisible par-dessus la
   *  3D, jamais masquée par le bâtiment), dimensionnée en mètres réels (lisible sur
   *  mobile sans écraser la boîte ni les panneaux). */
  function makeDimSprite(text: string): THREE.Sprite {
    const fontPx = 60;
    const padX = 26;
    const padY = 16;
    const font = `bold ${fontPx}px "Inter", system-ui, -apple-system, Segoe UI, sans-serif`;
    const measure = document.createElement('canvas').getContext('2d');
    if (measure) measure.font = font;
    const textW = measure ? measure.measureText(text).width : text.length * fontPx * 0.55;
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(textW + padX * 2);
    canvas.height = fontPx + padY * 2;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.font = font;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const r = 18;
      const w = canvas.width;
      const h = canvas.height;
      ctx.beginPath();
      ctx.moveTo(r, 0);
      ctx.arcTo(w, 0, w, h, r);
      ctx.arcTo(w, h, 0, h, r);
      ctx.arcTo(0, h, 0, 0, r);
      ctx.arcTo(0, 0, w, 0, r);
      ctx.closePath();
      ctx.fillStyle = 'rgba(7, 11, 29, 0.84)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = 'rgba(243, 204, 102, 0.7)'; // teinte laiton (GOLD) discrète
      ctx.stroke();
      ctx.lineWidth = 6;
      ctx.strokeStyle = 'rgba(7, 11, 29, 0.95)';
      ctx.strokeText(text, w / 2, h / 2 + 2);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, w / 2, h / 2 + 2);
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    tex.needsUpdate = true;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
    const worldW = 1.9; // largeur ~1,9 m → lisible sans masquer la boîte/les panneaux
    sprite.scale.set(worldW, (worldW * canvas.height) / canvas.width, 1);
    sprite.renderOrder = 20;
    return sprite;
  }

  /** CHEMIN DE CONSTRUCTION UNIQUE d'une zone : bâtiment + dalle (deck) + panneaux
   *  (+ châssis/lest en toit plat). Utilisé par renderScene pour la zone ACTIVE
   *  (offX=offY=0, dim=false → octet pour octet identique à avant) ET par
   *  appendOtherZones pour les AUTRES zones (offset GPS→ENU + dim=true subdué). Tout
   *  est ajouté à `sceneRoot`. NE touche PAS `setOrigin`/`disposeScene` (renderScene
   *  en reste propriétaire) ni la photo satellite (zone active uniquement). En dim, les
   *  obstacles de la zone (depuis `plan.obstacles`) sont rendus en boîtes subduées sans
   *  étiquette ni enregistrement (non manipulables). Renvoie la dalle (+ son matériau,
   *  pour la photo) et l'anneau TRANSLATÉ (pour l'enveloppe d'ombre). */
  function buildZoneMeshes(
    plan: ZoneRenderPlan,
    offX: number,
    offY: number,
    dim: boolean,
    occupiedSet?: Set<number>,
  ): { deck: THREE.Mesh; deckMat: THREE.MeshStandardMaterial; ring: [number, number][] } {
    const { pack, grid, tiltDeg, family, flush } = plan;
    const wallH = FLOORS * FLOOR_HEIGHT_M;
    const ring: [number, number][] = pack.ringENU.map(([x, y]) => [x + offX, y + offY]);

    // Bâtiment
    const shape = new THREE.Shape();
    ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
    shape.closePath();
    const buildingMat = new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 });
    if (dim) {
      // Zone NON active : bâtiment subdué (plus sombre + légèrement transparent) pour
      // que la zone ACTIVE (en cours d'édition) ressorte clairement.
      buildingMat.color.set(0x9aa3b4);
      buildingMat.transparent = true;
      buildingMat.opacity = 0.55;
    }
    const building = new THREE.Mesh(
      new THREE.ExtrudeGeometry(shape, { depth: wallH, bevelEnabled: false }),
      buildingMat,
    );
    building.castShadow = true;
    building.receiveShadow = true;
    sceneRoot!.add(building);

    const baseZ = wallH + DECK_THK;
    // FIX 1 (V6) — en pente (flush), réf. d'égout (le point le plus AVAL du tracé) :
    // la pente monte à partir de l'égout, rien ne passe sous le toit.
    const pitchEaveCoord = flush ? eaveUpSlopeCoord(ring, pack.azimuthDeg) : 0;
    const deckMat = new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 });
    if (dim) {
      deckMat.color.set(0x8b9099);
      deckMat.transparent = true;
      deckMat.opacity = 0.7;
    }
    const deckGeo = new THREE.ShapeGeometry(shape);
    if (flush) {
      // FIX 1 (V6) — la SURFACE DE TOIT elle-même devient un plan INCLINÉ : chaque
      // sommet de la dalle est relevé à la hauteur du plan (pente × distance à
      // l'égout). La photo détourée, mappée par position HORIZONTALE (applyRoofPhoto),
      // reste géo-alignée. Plat : dalle horizontale (inchangé).
      const dpos = deckGeo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < dpos.count; i++) {
        dpos.setZ(i, pitchedDeckZ(dpos.getX(i), dpos.getY(i), pitchEaveCoord, 0, tiltDeg, pack.azimuthDeg));
      }
      dpos.needsUpdate = true;
      deckGeo.computeVertexNormals();
    }
    const deck = new THREE.Mesh(deckGeo, deckMat);
    deck.position.z = wallH + 0.02;
    deck.receiveShadow = true;
    sceneRoot!.add(deck);

    // Axes de visée à partir de l'azimut de la famille.
    const azRad = pack.azimuthDeg * DEG2RAD;
    const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
    const u: [number, number] = [-f[1], f[0]];
    const rowAngleRad = Math.atan2(u[1], u[0]);
    const ca = Math.cos(rowAngleRad);
    const sa = Math.sin(rowAngleRad);
    const rx = (lx: number, ly: number): [number, number] => [lx * ca - ly * sa, lx * sa + ly * ca];

    const alongRow = grid.rowWidthM;
    const slope = grid.slopeLenM;
    const tilt = tiltDeg * DEG2RAD;
    const rise = slope * Math.sin(tilt);
    const depthFootprint = slope * Math.cos(tilt);
    const frontStrut = 0.1;
    const halfAlong = alongRow / 2;
    const halfDepth = depthFootprint / 2;

    const glassMat = new THREE.MeshPhysicalMaterial({ map: panelTex, color: 0xffffff, metalness: 0.1, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x9aa0aa, metalness: 0.85, roughness: 0.35 });
    const backMat = new THREE.MeshStandardMaterial({ color: 0xe6e8ee, metalness: 0.1, roughness: 0.6 });
    if (dim) {
      // Panneaux légèrement désaturés/assombris pour les zones non actives.
      glassMat.color.set(0xb8bcc6);
      frameMat.color.set(0x70757e);
      backMat.color.set(0xb0b3ba);
    }
    const panelMats = [frameMat, frameMat, frameMat, frameMat, glassMat, backMat];
    const panelGeo = new THREE.BoxGeometry(alongRow, slope, PANEL2_THICK_M);
    const jboxGeo = new THREE.BoxGeometry(0.4, 0.12, 0.035);
    jboxGeo.translate(0, 0, -(PANEL2_THICK_M / 2 + 0.02));
    const jboxMat = new THREE.MeshStandardMaterial({ color: 0x15171c, metalness: 0.3, roughness: 0.6 });
    const rackMat = new THREE.MeshStandardMaterial({ color: 0x40454f, metalness: 0.75, roughness: 0.4 });
    const ballastMat = new THREE.MeshStandardMaterial({ color: 0x9b9a90, metalness: 0, roughness: 0.95 });

    // Cellules POSÉES : disposition personnalisée explicite (zone active en mode
    // calepinage → ces cellules exactes, possiblement non contiguës) sinon les
    // `plan.count` premières cellules du pavage (comportement historique).
    const panels = occupiedSet
      ? grid.panels.filter((_, i) => occupiedSet.has(i))
      : grid.panels.slice(0, Math.max(0, plan.count));
    const panelMatsArr: THREE.Matrix4[] = [];
    const frontMats: THREE.Matrix4[] = [];
    const backMats: THREE.Matrix4[] = [];
    const railMats: THREE.Matrix4[] = [];
    const ballastMats: THREE.Matrix4[] = [];
    const railGeo = new THREE.BoxGeometry(0.05, slope, 0.05);
    const frontGeo = new THREE.BoxGeometry(0.06, 0.06, frontStrut);
    const backGeo = new THREE.BoxGeometry(0.06, 0.06, frontStrut + rise);
    const ballastGeo = new THREE.BoxGeometry(0.34, 0.18, 0.12);
    const ends = [-halfAlong + 0.08, 0, halfAlong - 0.08];

    for (const p of panels) {
      const cx = p.cx + offX;
      const cy = p.cy + offY;
      // Pour l'Est-Ouest : le sens d'inclinaison vient de la FACE du panneau
      // (chevrons dos à dos faces E/O), fournie par le cerveau. Sud : tilt simple.
      const signedTilt = family === 'eastwest' ? (p.face === 'E' ? -tilt : tilt) : tilt;
      // Toit plat : panneau surélevé sur châssis (frontStrut + montée d'ombre).
      // Toit en pente (flush) : FIX 1 (V6) — panneau COPLANAIRE, AFFLEURANT sur le
      // plan incliné. compose(yaw, tilt) donne déjà au panneau la normale du toit
      // (donc tous les panneaux sont coplanaires) ; flushPanelCenterAt pose le CENTRE
      // sur le plan + un décalage CONSTANT le long de la normale → le centre monte
      // avec la pente (vrai plan incliné, pas un calepinage plat de panneaux inclinés).
      if (flush) {
        const c = flushPanelCenterAt(p.cx, p.cy, pitchEaveCoord, baseZ, tiltDeg, pack.azimuthDeg, PITCHED_FLUSH_STANDOFF_M);
        panelMatsArr.push(compose(c.x + offX, c.y + offY, c.z, rowAngleRad, signedTilt));
      } else {
        const pZ = baseZ + frontStrut + rise / 2 + 0.07;
        panelMatsArr.push(compose(cx, cy, pZ, rowAngleRad, signedTilt));
      }
      if (!flush) for (const xe of ends) {
        const lowDepth = signedTilt >= 0 ? -halfDepth : halfDepth;
        const highDepth = -lowDepth;
        const fpt = rx(xe, lowDepth);
        frontMats.push(compose(cx + fpt[0], cy + fpt[1], baseZ + frontStrut / 2, rowAngleRad, 0));
        const bpt = rx(xe, highDepth);
        backMats.push(compose(cx + bpt[0], cy + bpt[1], baseZ + (frontStrut + rise) / 2, rowAngleRad, 0));
        const cpt = rx(xe, 0);
        railMats.push(compose(cx + cpt[0], cy + cpt[1], baseZ + frontStrut + rise / 2, rowAngleRad, signedTilt));
      }
      if (!flush) for (const xe of [-halfAlong + 0.08, halfAlong - 0.08]) {
        const bf = rx(xe, -halfDepth - 0.02);
        ballastMats.push(compose(cx + bf[0], cy + bf[1], baseZ + 0.06, rowAngleRad, 0));
        const bb = rx(xe, halfDepth + 0.02);
        ballastMats.push(compose(cx + bb[0], cy + bb[1], baseZ + 0.06, rowAngleRad, 0));
      }
    }

    const meshes = [
      makeIM(panelGeo, panelMats, panelMatsArr, true, false),
      makeIM(jboxGeo, jboxMat, panelMatsArr, true, false),
      makeIM(frontGeo, rackMat, frontMats, true, false),
      makeIM(backGeo, rackMat, backMats, true, false),
      makeIM(railGeo, rackMat, railMats, true, false),
      makeIM(ballastGeo, ballastMat, ballastMats, true, true),
    ];
    for (const me of meshes) if (me) sceneRoot!.add(me);

    // Zones NON actives : obstacles rendus en boîtes subduées (sans étiquette ni drag),
    // à leur vraie position relative. La zone active gère ses obstacles vivants ailleurs.
    if (dim && plan.obstacles.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of plan.obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat + offX;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M + offY;
        const tint = 0xc06464;
        const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, OBSTACLE_BOX_H_M);
        const mat = new THREE.MeshStandardMaterial({
          color: tint,
          metalness: 0.1,
          roughness: 0.7,
          transparent: true,
          opacity: 0.3,
          depthWrite: false,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(ox, oy, wallH + OBSTACLE_BOX_H_M / 2 + 0.05);
        mesh.renderOrder = 3;
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: 0.6 }),
        );
        mesh.add(edges);
        sceneRoot!.add(mesh);
      }
    }

    return { deck, deckMat, ring };
  }

  /** Re-dessine TOUTES les zones SAUF l'active, à leur vraie position relative (« toutes
   *  les zones empilées »). Pour chaque zone disposant d'un `renderPlan`, on calcule
   *  l'offset ENU entre son origine GPS et celle de la zone active, puis on construit ses
   *  meshes (subdués) via le MÊME chemin que la zone active. N'appelle JAMAIS
   *  disposeScene/setOrigin (propriété de renderScene). Renvoie les anneaux TRANSLATÉS
   *  des autres zones, pour étendre l'enveloppe d'ombre. No-op (→ []) tant qu'il n'y a
   *  qu'une zone ou qu'aucune autre n'a de plan. */
  function appendOtherZones(activeOrigin: LngLat): [number, number][][] {
    if (!sceneRoot) return [];
    const rings: [number, number][][] = [];
    const cosLat = Math.cos(activeOrigin[1] * DEG2RAD);
    for (const a of areas) {
      if (a.id === activeAreaId || !a.renderPlan) continue;
      const plan = a.renderPlan;
      const offX = (plan.pack.origin[0] - activeOrigin[0]) * DEG2M * cosLat;
      const offY = (plan.pack.origin[1] - activeOrigin[1]) * DEG2M;
      const built = buildZoneMeshes(plan, offX, offY, true);
      rings.push(built.ring);
    }
    return rings;
  }

  // — Rendu d'une config (Sud sur châssis OU Est-Ouest en chevrons). `flush` (V3,
  //   toit en pente) pose les panneaux AFFLEURANTS sur la pente : pas de châssis ni
  //   de lest, panneau couché à l'inclinaison du toit. flush=false ⇒ rendu toit plat
  //   octet pour octet identique à pro-5. —
  function renderScene(pack: PackResult, grid: PanelGrid, tiltDeg: number, family: ConfigFamily, maxCount: number, flush = false, occupiedSet?: Set<number>) {
    if (!sceneRoot || !sun) return;
    // W69 — un rendu SANS occupation explicite vient de l'optimiseur : on mémorise le
    // plan gagnant (pack/grid/tilt/family/flush) + le comptage optimal, pour pouvoir
    // re-rendre une disposition PERSONNALISÉE (occupation non contiguë) sur le MÊME plan.
    if (!occupiedSet) {
      layoutPlan = { pack, grid, tiltDeg, family, flush };
      layoutOptimalCount = Math.max(0, Math.min(grid.panels.length, Math.round(maxCount)));
      // Un rendu optimiseur = le PLAN a (peut-être) changé : la disposition personnalisée
      // courante n'a plus de sens (cellules différentes) → on la repart de l'optimum.
      layoutState = null;
      layoutSel = null;
    }
    setOrigin(pack.origin);
    sceneOrigin = pack.origin;
    obstacleMeshes.clear();
    disposeScene();

    const wallH = FLOORS * FLOOR_HEIGHT_M;

    // W69 — disposition personnalisée : si un ensemble d'index occupés est fourni, on
    // rend EXACTEMENT ces cellules (potentiellement non contiguës) ; sinon on garde le
    // comportement historique (les `maxCount` premières cellules du pavage).
    const drawnPanels = occupiedSet
      ? grid.panels.filter((_, i) => occupiedSet.has(i))
      : grid.panels.slice(0, Math.max(0, maxCount));

    // Bâtiment + dalle + panneaux de la zone ACTIVE : MÊME chemin de construction que les
    // autres zones (buildZoneMeshes), à offset NUL et sans atténuation → octet pour octet
    // identique à avant. Les obstacles VIVANTS (tinte sélection + étiquette + drag) et la
    // photo satellite restent gérés ici car ils dépendent de l'état d'édition courant.
    const activePlan: ZoneRenderPlan = { pack, grid, tiltDeg, family, flush, count: drawnPanels.length, obstacles };
    const built = buildZoneMeshes(activePlan, 0, 0, false, occupiedSet);
    // Change B : pose la photo satellite (géo-alignée, détourée au tracé) sur la
    // face supérieure. L'origine de la scène sert à reprojeter les sommets en lng/lat.
    applyRoofPhoto(built.deck, built.deckMat, pack.origin);

    // Obstacles marqués (Change C) : volume SEMI-TRANSPARENT à la VRAIE taille
    // (largeur E-O × longueur N-S), posé sur le toit, avec une arête visible — la
    // photo satellite dessous (le vrai climatiseur/cheminée) transparaît, ce qui
    // confirme que la boîte est bien posée dessus. Sélectionné → teinte or. Zone active
    // uniquement : étiquette de taille + enregistrement pour le glissé en direct.
    if (obstacles.length) {
      const cosLat = Math.cos(pack.origin[1] * DEG2RAD);
      for (const o of obstacles) {
        const ox = (o.centerLng - pack.origin[0]) * DEG2M * cosLat;
        const oy = (o.centerLat - pack.origin[1]) * DEG2M;
        const selected = o.id === selectedObsId;
        const tint = selected ? 0xf3cc66 : 0xff6b6b;
        const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, OBSTACLE_BOX_H_M);
        const mat = new THREE.MeshStandardMaterial({
          color: tint,
          metalness: 0.1,
          roughness: 0.7,
          transparent: true,
          opacity: selected ? 0.5 : 0.42,
          depthWrite: false, // laisse la texture du toit transparaître
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(ox, oy, wallH + OBSTACLE_BOX_H_M / 2 + 0.05);
        mesh.renderOrder = 3;
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: 0.95 }),
        );
        mesh.add(edges);
        // Change B : taille affichée SUR la boîte, en 3D (plus de libellé « en
        // dessous » sur la carte). Enfant du mesh → suit la boîte au déplacement.
        const label = makeDimSprite(dimsLabel(o));
        label.position.set(0, 0, OBSTACLE_BOX_H_M / 2 + 0.6);
        mesh.add(label);
        sceneRoot.add(mesh);
        obstacleMeshes.set(o.id, mesh);
      }
    }

    // W-MULTI : mémorise le plan de re-rendu de la zone ACTIVE pour que les AUTRES
    // zones puissent être re-dessinées (subduées) à leur vraie position relative.
    const aRec = activeArea();
    if (aRec) aRec.renderPlan = { pack, grid, tiltDeg, family, flush, count: drawnPanels.length, obstacles: obstacles.map((o) => ({ ...o })) };

    // — Soleil d'affichage (matin clair, élévation liée à la latitude) —
    // Bornes d'ombre = enveloppe de TOUTES les zones rendues (active + autres), pour que
    // l'ombre ne soit pas tronquée quand plusieurs zones coexistent. `appendOtherZones`
    // (appelée plus bas) ajoute les anneaux translatés des autres zones à cette liste.
    const shadowRings: [number, number][][] = [built.ring];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const otherRings = appendOtherZones(pack.origin);
    for (const r of otherRings) shadowRings.push(r);
    for (const r of shadowRings) for (const [x, y] of r) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
    const cxm = (minX + maxX) / 2;
    const cym = (minY + maxY) / 2;
    const span = Math.max(maxX - minX, maxY - minY, wallH) + 8;
    // Aucun « tapis » sombre : le fond satellite réel (les vrais environs) reste
    // visible autour du bâtiment, qui se lit comme un volume 3D posé dans son
    // contexte, son toit texturé sur le dessus (détouré au tracé). La photo du toit
    // (surélevée) et le sol viennent de la même imagerie source.
    const roofZ = wallH + 0.5;
    const latAbs = Math.abs(pack.origin[1]);
    const dispElevDeg = Math.max(28, (90 - latAbs) * 0.62);
    const dispAzDeg = pack.azimuthDeg - 45;
    const azR = dispAzDeg * DEG2RAD;
    const elR = dispElevDeg * DEG2RAD;
    const dist = span * 2.5;
    sun.target.position.set(cxm, cym, roofZ);
    sun.position.set(cxm + Math.sin(azR) * Math.cos(elR) * dist, cym + Math.cos(azR) * Math.cos(elR) * dist, roofZ + Math.sin(elR) * dist);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = -span;
    sc.right = span;
    sc.top = span;
    sc.bottom = -span;
    sc.near = 0.5;
    sc.far = dist * 2;
    sc.updateProjectionMatrix();

    map.triggerRepaint();
  }

  // — Carte / tracé —
  map.on('load', () => {
    map.addSource('rp9-line', { type: 'geojson', data: empty as never });
    map.addSource('rp9-pts', { type: 'geojson', data: empty as never });
    map.addSource('rp9-obs', { type: 'geojson', data: empty as never });
    map.addSource('rp9-obs-preview', { type: 'geojson', data: empty as never });
    map.addLayer({ id: 'rp9-line', type: 'line', source: 'rp9-line', paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
    map.addLayer({ id: 'rp9-pts', type: 'circle', source: 'rp9-pts', paint: { 'circle-radius': 5, 'circle-color': GOLD, 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 1.5 } });
    // Obstacles : remplissage (plus vif si sélectionné) + contour + étiquette L×l.
    map.addLayer({
      id: 'rp9-obs',
      type: 'fill',
      source: 'rp9-obs',
      paint: { 'fill-color': '#ff6b6b', 'fill-opacity': ['case', ['get', 'selected'], 0.5, 0.3] },
    });
    map.addLayer({
      id: 'rp9-obs-outline',
      type: 'line',
      source: 'rp9-obs',
      paint: { 'line-color': ['case', ['get', 'selected'], GOLD, '#ff6b6b'], 'line-width': ['case', ['get', 'selected'], 3, 1.5] },
    });
    // W1 : la taille de chaque obstacle s'affiche À LA FOIS sur la carte 2D
    // (cette étiquette symbol « L × l m ») ET sur la boîte en 3D (sprite, cf.
    // makeDimSprite, dans renderScene) — multi-obstacles lisibles dans les deux vues.
    map.addLayer({
      id: 'rp9-obs-label',
      type: 'symbol',
      source: 'rp9-obs',
      layout: { 'text-field': ['get', 'dims'], 'text-size': 13, 'text-font': ['Open Sans Bold', 'Noto Sans Bold'], 'text-allow-overlap': true, 'symbol-placement': 'point' },
      paint: { 'text-color': '#ffffff', 'text-halo-color': '#070b1d', 'text-halo-width': 1.6 },
    });
    map.addLayer({
      id: 'rp9-obs-preview',
      type: 'line',
      source: 'rp9-obs-preview',
      paint: { 'line-color': GOLD, 'line-width': 2, 'line-dasharray': [1.5, 1] },
    });
    map.addLayer(customLayer);
    updateCompass();
    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: vertices }, properties: {} } as never);
    srcOf('rp9-pts')?.setData({ type: 'FeatureCollection', features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })) } as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
    updateAreaReadout();
  }

  function redrawObstacles() {
    srcOf('rp9-obs')?.setData({
      type: 'FeatureCollection',
      features: obstacles.map((o) => {
        const ring = obstacleRing(o);
        return {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] },
          properties: { id: o.id, selected: o.id === selectedObsId, dims: dimsLabel(o) },
        };
      }),
    } as never);
  }

  function setPreviewRect(a: LngLat, b: LngLat) {
    const ring: LngLat[] = [a, [b[0], a[1]], b, [a[0], b[1]], a];
    srcOf('rp9-obs-preview')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ring }, properties: {} } as never);
  }
  function clearPreview() {
    srcOf('rp9-obs-preview')?.setData(empty as never);
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    // W76 — refuse un point qui ferait CROISER le contour (nœud papillon). isSimplePolygon
    // traite l'anneau comme FERMÉ (dernier→premier), donc tester [...vertices, v] vérifie à
    // la fois la nouvelle arête et l'arête de fermeture implicite v→1ᵉʳ sommet. Un anneau
    // croisé fausse l'aire géodésique (la shoelace s'annule) et le pavage.
    if (vertices.length >= 3 && !isSimplePolygon([...vertices, v])) {
      setStatus('Ce point croiserait votre tracé — placez-le ailleurs pour garder un contour simple.');
      return;
    }
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et lancer le calcul.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  // — Sélection + édition d'un obstacle —
  function syncObsEdit() {
    const o = obstacles.find((x) => x.id === selectedObsId) ?? null;
    if (obsEditPanel) obsEditPanel.hidden = !o;
    if (!o) return;
    if (obsLengthEl && document.activeElement !== obsLengthEl) obsLengthEl.value = fmt1(o.lengthM);
    if (obsWidthEl && document.activeElement !== obsWidthEl) obsWidthEl.value = fmt1(o.widthM);
    if (obsDimsEl) obsDimsEl.textContent = dimsLabel(o);
  }

  function selectObstacle(id: string | null) {
    selectedObsId = id;
    redrawObstacles();
    syncObsEdit();
  }

  /** Remplace l'obstacle sélectionné par une version transformée, puis recalcule. */
  function updateSelected(transform: (o: Obstacle) => Obstacle) {
    const idx = obstacles.findIndex((x) => x.id === selectedObsId);
    if (idx < 0) return;
    obstacles[idx] = transform(obstacles[idx]);
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  function deleteSelected() {
    if (!selectedObsId) return;
    obstacles = obstacles.filter((x) => x.id !== selectedObsId);
    selectedObsId = null;
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  function addObstacle(o: Obstacle) {
    obstacles.push(o);
    selectedObsId = o.id;
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  /** Obstacle touché au point écran `pt`, ou null. */
  function obstacleAtPoint(pt: maplibregl.Point): string | null {
    const hits = map.queryRenderedFeatures(pt, { layers: ['rp9-obs'] });
    const id = hits[0]?.properties?.id;
    return typeof id === 'string' ? id : null;
  }

  // — Sélection de config → grille —
  function tiltOf(family: ConfigFamily): number {
    if (sel.tilt === 'reco') {
      if (useRecommended && rec) return rec.recommended.tiltDeg;
      return family === 'eastwest' ? 10 : (rec?.maxPerPanelTiltDeg ?? 29);
    }
    return sel.tilt;
  }

  function gridFor(pack: PackResult): PanelGrid {
    if (sel.orient === 'portrait') return pack.portrait;
    if (sel.orient === 'landscape') return pack.landscape;
    return pack.best;
  }

  // — Plafond « panneaux nécessaires » (Change A) —
  const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));
  /** Posés = min(plafond besoin, ce qui tient). Sans facture (besoin 0) il n'y a
   *  pas de besoin à plafonner → on montre ce qui tient (comportement historique). */
  const placedFor = (grid: PanelGrid): number =>
    neededPanels > 0 ? Math.max(0, Math.min(neededPanels, grid.count)) : grid.count;

  /** Synchronise le contrôle éditable + sa note honnête (besoin vs ce qui tient). */
  function syncNeedControl(fitCount: number, familyLabel: string) {
    const active = neededPanels > 0;
    if (needInputEl) {
      needInputEl.disabled = !active;
      if (document.activeElement !== needInputEl) needInputEl.value = active ? fmt(neededPanels) : '—';
    }
    if (needMinusEl) needMinusEl.disabled = !active || neededPanels <= 1;
    if (needPlusEl) needPlusEl.disabled = !active || neededPanels >= 400;
    if (!needNoteEl) return;
    if (!active) {
      needNoteEl.textContent = 'Indiquez votre facture pour dimensionner le nombre de panneaux.';
      return;
    }
    const placed = Math.min(neededPanels, fitCount);
    if (placed < neededPanels) {
      needNoteEl.textContent = `${fmt(neededPanels)} nécessaires — ${fmt(placed)} tiennent en ${familyLabel} (toit ou obstacles). On pose ${fmt(placed)}.`;
    } else if (fitCount > neededPanels) {
      needNoteEl.textContent = `${fmt(neededPanels)} couvrent votre facture (+10 %) — il reste de la place sur le toit, laissée libre.`;
    } else {
      needNoteEl.textContent = `On pose ${fmt(placed)} panneaux.`;
    }
  }

  interface RenderConfigOpts {
    pack: PackResult;
    grid: PanelGrid;
    family: ConfigFamily;
    tiltDeg: number;
    /** Azimut de face réel du pavage (W1) : production à l'aspect correspondant. */
    azimuthDeg: number;
    isReco: boolean;
    title: string;
    why: string;
    sourceLabel?: string;
    rowId: string | null;
  }

  /** Rendu UNIFIÉ : pose min(besoin, ce qui tient), recalcule kWc/kWh/économies
   *  depuis ce nombre POSÉ (jamais la capacité max de la config). */
  function renderConfig(o: RenderConfigOpts) {
    const placed = placedFor(o.grid);
    const kwc = o.grid.count > 0 ? (o.grid.kwc * placed) / o.grid.count : 0;
    // W1 : production à l'aspect réel (le rendement/panneau baisse honnêtement
    // quand l'array suit un toit tourné).
    const aspect = aspectForLeg(o.family, o.azimuthDeg);
    const tableAnnual = productionKwh(centroidLat, o.family, o.tiltDeg, kwc, aspect);
    // Affinage PVGIS : rendement par kWc × kWc POSÉ (suit le plafond/contrainte).
    const annualKwh = o.isReco && pvgisPerKwc != null ? pvgisPerKwc * kwc : tableAnnual;
    const target = rec ? rec.targetAnnualKwh : billToAnnualKwh(monthlyBill());
    const savings = annualSavingsMad(annualKwh, target); // plafonné à la conso
    renderScene(o.pack, o.grid, o.tiltDeg, o.family, placed);
    paintCard(
      {
        title: o.title,
        isReco: o.isReco,
        count: placed,
        kwc,
        annualKwh,
        pct: target > 0 ? (annualKwh / target) * 100 : 0,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: o.why,
      },
      o.sourceLabel,
    );
    syncNeedControl(o.grid.count, o.family === 'eastwest' ? 'Est-Ouest' : 'plein sud');
    syncTiltControl(o.tiltDeg, o.isReco);
    if (o.isReco) paintMaxLine();
    highlightRow(o.rowId);
  }

  /** Reflète l'inclinaison RÉELLEMENT dessinée dans le curseur + son libellé.
   *  Ne touche pas le curseur pendant que l'utilisateur le manipule. */
  function syncTiltControl(tiltDeg: number, isReco: boolean) {
    const t = Math.round(tiltDeg);
    if (tiltRangeEl && document.activeElement !== tiltRangeEl) tiltRangeEl.value = String(t);
    if (tiltValueEl) tiltValueEl.textContent = `${t}°${isReco ? ' · reco' : ''}`;
    if (tiltRecoBtn) tiltRecoBtn.setAttribute('aria-pressed', String(isReco && useRecommended));
  }

  // ═════════════ W34 — OPTIMISEUR CONTRAINT VIVANT (toit plat, cerveau V7) ═════════════
  // renderSelection() est désormais un ALIAS de liveResolveFlat() : recompute,
  // renderActive et tous les handlers d'options passent par le solveur vivant. Chaque
  // option est un AXE ; un clic VERROUILLE cet axe (épingle dans `pinned`) et RE-RÉSOUT
  // en direct tous les axes encore AUTO (les verrous s'accumulent), via solveLive (V7,
  // PVGIS au GPS exact, repli table « estimé »). Chaque groupe affiche la valeur
  // « Recommandé » = la valeur que cet axe prendrait s'il était libéré, les autres
  // verrous tenus — donc l'utilisateur voit qu'il a choisi X mais que Y est recommandé.

  /** Verrous courants dérivés des axes épinglés (pinned) + de la cible « besoin ».
   *  L'orientation (un seul axe V7) est reconstruite depuis les groupes Orientation
   *  (famille) et Azimut de la page. */
  function buildFlatLocks(): AxisLocks {
    const locks: AxisLocks = {};
    if (pinned.has('family') && sel.family === 'eastwest') locks.orientation = 'eastwest';
    else if (pinned.has('azimuth') && sel.azimuth === 'aligned') locks.orientation = 'aligned';
    else if ((pinned.has('family') && sel.family === 'south') || (pinned.has('azimuth') && sel.azimuth === 'south'))
      locks.orientation = 'south';
    if (pinned.has('tilt') && sel.tilt !== 'reco') locks.tiltDeg = sel.tilt;
    if (pinned.has('orient') && sel.orient !== 'auto') locks.layout = sel.orient as LayoutAxis;
    if (pinned.has('margin')) locks.margin = sel.margin;
    if (!neededAuto && neededPanels > 0) locks.need = neededPanels;
    return locks;
  }

  /** Reflète le gagnant courant dans `sel` (miroir d'affichage des puces). */
  function mapWinnerToSel(w: LiveConfigEval) {
    sel = {
      family: w.family,
      tilt: w.tiltDeg,
      orient: w.layout,
      azimuth: w.orientation === 'aligned' ? 'aligned' : 'south',
      margin: w.margin,
    };
  }

  function liveOrientationLabel(w: LiveConfigEval): string {
    if (w.family === 'eastwest') return 'Est-Ouest';
    return w.orientation === 'aligned' ? 'Sud (aligné toit)' : 'Plein sud';
  }

  /** Pose le badge « Recommandé » sur la valeur recommandée de CHAQUE groupe (axe
   *  libéré, autres verrous tenus) — reste correct même si l'utilisateur a verrouillé
   *  une autre valeur. */
  function updateLiveBadges(res: LiveSolveResult) {
    const rcm = res.recommended;
    const show = (b: Element | null, on: boolean) => {
      const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
      if (badge) badge.hidden = !on;
    };
    const recFamily = rcm.orientation === 'eastwest' ? 'eastwest' : 'south';
    document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => show(b, b.dataset.family === recFamily));
    const tiltRounded = Math.round(rcm.tiltDeg);
    const tiltChips = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-tilt]'));
    const numericMatch = tiltChips.find((b) => b.dataset.tilt !== 'reco' && Number(b.dataset.tilt) === tiltRounded);
    tiltChips.forEach((b) => {
      if (numericMatch) show(b, b === numericMatch);
      else show(b, b.dataset.tilt === 'reco');
    });
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      show(b, b.dataset.orient !== 'auto' && b.dataset.orient === rcm.layout),
    );
    const azReco = rcm.orientation === 'aligned' ? 'aligned' : 'south';
    document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => show(b, b.dataset.azimuth === azReco));
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => show(b, b.dataset.margin === rcm.margin));
  }

  /** Rend le gagnant vivant (3D + carte + contrôles) avec SES chiffres (PVGIS/estimé). */
  function renderLiveWinner(res: LiveSolveResult, isReco: boolean) {
    const w = res.winner;
    const ring: LngLat[] = [...vertices];
    const setbackM = w.margin === 'keep' ? PERIMETER_SETBACK_M : 0;
    const pack = packConfig(ring, centroidLat, {
      family: w.family,
      tiltDeg: w.tiltDeg,
      azimuthDeg: w.azimuthDeg,
      obstructions: obstructionRings(),
      setbackM,
    });
    const grid = w.layout === 'portrait' ? pack.portrait : pack.landscape;
    renderScene(pack, grid, w.tiltDeg, w.family, w.placedCount);
    const cov = Math.round(w.pctOfTarget);
    const why = isReco
      ? `Meilleure combinaison pour votre facture : ${liveOrientationLabel(w)} à ${w.tiltDeg}°, ${w.placedCount} panneaux ≈ ${cov} % de la facture. Touchez une option pour la verrouiller — le reste se re-résout.`
      : `Vos choix sont tenus, le reste a été re-résolu : ${w.placedCount} panneaux ≈ ${cov} % de la facture. Les badges « Recommandé » montrent l'option optimale de chaque groupe.`;
    paintCard(
      {
        title: `${liveOrientationLabel(w)} ${w.tiltDeg}° · ${w.layoutLabel}`,
        isReco,
        count: w.placedCount,
        kwc: w.kwc,
        annualKwh: w.annualKwh,
        pct: w.pctOfTarget,
        savingsLow: w.savingsLow,
        savingsHigh: w.savingsHigh,
        why,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS au GPS exact)' : '(production estimée — table par latitude)',
    );
    syncNeedControl(grid.count, liveOrientationLabel(w));
    syncTiltControl(w.tiltDeg, isReco);
    paintMaxLine();
    highlightRow(null);
    if (optimumNoteEl) {
      optimumNoteEl.textContent = isReco
        ? 'Optimum vivant : tout est calé sur la meilleure combinaison (chaque groupe badgé « Recommandé »). Verrouillez une option et le reste se re-résout en direct.'
        : 'Optimum vivant : votre choix est tenu, le reste se re-résout pour maximiser la génération. « Réinitialiser » relâche tous les verrous.';
    }
  }

  // ═══════════ W50 — rendu de la fenêtre « Production estimée » ═══════════

  /** Configuration de production du plan courant (déduite du winner de l'optimiseur). */
  interface ProdConfig {
    lat: number;
    lon: number;
    tiltDeg: number;
    aspect: number;
    mountingplace: 'building' | 'free';
    panels: number;
    target: number;
  }

  /** Échappe le texte pour l'insérer en toute sécurité dans un attribut/texte SVG. */
  const esc = (s: string): string =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  /** Graphe ANNÉE : 12 barres mensuelles (kWh/mois), étiquettes mensuelles courtes. */
  function renderYearGraph(prod: ScaledProduction): string {
    const { bars } = yearSeries(prod);
    const rects = barGeometry(bars, SVG_BOX, 0.25);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    const bodies = rects
      .map(
        (r) =>
          `<rect x="${r.x.toFixed(2)}" y="${r.y.toFixed(2)}" width="${r.width.toFixed(2)}" height="${r.height.toFixed(2)}" rx="1.5" fill="var(--color-brass-400, #e8b54a)"><title>${esc(r.label)} : ${esc(fmtKwh(r.kwh))}</title></rect>`,
      )
      .join('');
    // Les barres portent déjà l'étiquette mensuelle courte (« janv. »…) via yearSeries.
    const labels = rects
      .map(
        (r) =>
          `<text x="${(r.x + r.width / 2).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${esc(r.label)}</text>`,
      )
      .join('');
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${bodies}${labels}`;
  }

  /** Graphe MOIS : ~N barres journalières (kWh/jour) du mois sélectionné. */
  function renderMonthGraph(prod: ScaledProduction): string {
    const { bars } = monthSeries(prod, prodMonth);
    const rects = barGeometry(bars, SVG_BOX, 0.15);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    const bodies = rects
      .map(
        (r) =>
          `<rect x="${r.x.toFixed(2)}" y="${r.y.toFixed(2)}" width="${r.width.toFixed(2)}" height="${r.height.toFixed(2)}" fill="var(--color-brass-400, #e8b54a)"><title>jour ${esc(r.label)} : ${esc(fmtKwh(r.kwh))}</title></rect>`,
      )
      .join('');
    // Étiquettes clairsemées (1, milieu, dernier) pour éviter l'encombrement.
    const last = rects.length;
    const ticks = last > 0 ? [0, Math.floor(last / 2), last - 1] : [];
    const labels = ticks
      .map((i) => {
        const r = rects[i];
        if (!r) return '';
        return `<text x="${(r.x + r.width / 2).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${esc(r.label)}</text>`;
      })
      .join('');
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${bodies}${labels}`;
  }

  /** Graphe JOUR : courbe 24 h de puissance (kW) + aire remplie. */
  function renderDayGraph(prod: ScaledProduction): string {
    const { points } = daySeries(prod, prodMonth, prodSpecificDate);
    const area = dayAreaPath(points, SVG_BOX);
    const line = dayCurvePath(points, SVG_BOX);
    const baseY = SVG_BOX.height - SVG_BOX.padBottom;
    // Repères d'heures (0, 6, 12, 18, 23 h).
    const plotW = SVG_BOX.width - SVG_BOX.padLeft - SVG_BOX.padRight;
    const xAt = (h: number) => SVG_BOX.padLeft + (h / 23) * plotW;
    const ticks = [0, 6, 12, 18, 23]
      .map(
        (h) =>
          `<text x="${xAt(h).toFixed(2)}" y="${(SVG_BOX.height - 5).toFixed(2)}" text-anchor="middle" font-size="7" fill="var(--color-lune-faint, #6f7791)">${h}h</text>`,
      )
      .join('');
    const areaEl = area
      ? `<path d="${area}" fill="var(--color-brass-400, #e8b54a)" fill-opacity="0.18"/>`
      : '';
    const lineEl = line
      ? `<path d="${line}" fill="none" stroke="var(--color-brass-400, #e8b54a)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`
      : '';
    return `<line x1="${SVG_BOX.padLeft}" y1="${baseY}" x2="${SVG_BOX.width - SVG_BOX.padRight}" y2="${baseY}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>${areaEl}${lineEl}${ticks}`;
  }

  /** Rend la fenêtre de production complète (toggle, pickers, headline, graphe, économies). */
  function renderProdWindow() {
    if (!prodWindowEl) return;
    const prod = prodScaled;
    if (!prod || prodPanels <= 0) {
      prodWindowEl.hidden = true;
      return;
    }
    prodWindowEl.hidden = false;
    const estimated = isEstimate(prodSource);
    const approx = estimated; // « estimé » → on préfixe « ~ »
    const tag = estimated ? ' (estimé)' : '';

    // Visibilité des pickers selon le scope.
    if (prodMonthPickerEl) prodMonthPickerEl.hidden = prodScope === 'year';
    if (prodDayPickerEl) prodDayPickerEl.hidden = prodScope !== 'day';

    // Boutons de scope : aria-pressed reflète le scope courant.
    if (prodScopeWrap) {
      prodScopeWrap.querySelectorAll<HTMLButtonElement>('[data-prod-scope]').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.prodScope === prodScope));
      });
    }

    // Libellés des pickers.
    if (prodMonthLabelEl) prodMonthLabelEl.textContent = MONTH_NAMES_FR[prodMonth];
    if (prodDayLabelEl) {
      prodDayLabelEl.textContent =
        prodDay == null ? `jour type · ${MONTH_NAMES_FR[prodMonth]}` : `${prodDay} ${MONTH_NAMES_FR[prodMonth]}`;
    }
    if (prodDayResetEl) prodDayResetEl.hidden = prodDay == null;

    let headline = '';
    let sub = '';
    let graph = '';
    let savingsTxt = '';

    if (prodScope === 'year') {
      const { totalKwh } = yearSeries(prod);
      headline = `${fmtKwh(totalKwh, approx)}/an${tag}`;
      sub = 'Production annuelle estimée · 12 mois';
      graph = renderYearGraph(prod);
      const s = annualSavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/an` : '';
    } else if (prodScope === 'month') {
      const { totalKwh } = monthSeries(prod, prodMonth);
      headline = `${fmtKwh(totalKwh, approx)}${tag}`;
      sub = `Production de ${MONTH_NAMES_FR[prodMonth]} · ${daysInMonth(prodMonth)} jours`;
      graph = renderMonthGraph(prod);
      const s = monthlySavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/mois` : '';
    } else {
      const { totalKwh, isTypical } = daySeries(prod, prodMonth, prodSpecificDate);
      headline = `${fmtKwh(totalKwh, approx)}${tag}`;
      const dayTxt = prodDay == null ? `jour type de ${MONTH_NAMES_FR[prodMonth]}` : `${prodDay} ${MONTH_NAMES_FR[prodMonth]}`;
      sub = `Courbe horaire · ${dayTxt}${isTypical ? ' (moyenne du mois)' : ''}`;
      graph = renderDayGraph(prod);
      const s = dailySavings(totalKwh, prodTarget);
      savingsTxt = prodTarget > 0 ? `Économies estimées (plafonnées) : ${fmtSavings(s.low, s.high)}/jour` : '';
    }

    if (prodHeadlineEl) prodHeadlineEl.textContent = headline;
    if (prodSubEl) prodSubEl.textContent = sub;
    if (prodGraphEl) prodGraphEl.innerHTML = graph;
    if (prodSourceEl) prodSourceEl.textContent = `Source : ${prodSourceLabel(prodSource)}`;
    if (prodSavingsEl) prodSavingsEl.textContent = savingsTxt;
    // W68 — la fenêtre « Affiner ma consommation » suit le même plan/production.
    renderConsumption();
  }

  /**
   * Met à jour la fenêtre de production pour le plan courant. Si le PLAN (GPS/inclinaison/
   * azimut/pose) a changé, on interroge /api/roof-production (serveur → PVGIS, jamais le
   * client directement). Si seul le NOMBRE de panneaux change (même plan), on RESCALE côté
   * client (linéaire en kWc) sans appel serveur. La date précise sélectionnée est
   * re-demandée au serveur (la silhouette inter-années ne se rescale pas en pur kWc côté
   * client sans la série horaire — on la garde donc serveur-side, rescalée par le serveur).
   */
  function updateProductionWindow(cfg: ProdConfig) {
    if (!prodWindowEl) return;
    prodPanels = Math.max(0, Math.round(cfg.panels));
    prodTarget = Math.max(0, cfg.target);
    if (prodPanels <= 0) {
      prodScaled = null;
      prodPerKwc = null;
      renderProdWindow();
      return;
    }
    const planKey = prodPlaneKeyOf(cfg);
    const planeChanged = planKey !== prodPlaneKey;
    const dateChanged = prodScope === 'day' && prodDay != null;

    // Plan inchangé ET pas de date à (re)charger → rescale CLIENT pur (zéro appel serveur).
    if (!planeChanged && !dateChanged && prodPerKwc) {
      prodScaled = rescaleByPanels(prodPerKwc, prodPanels, PANEL_KWC);
      renderProdWindow();
      return;
    }

    const token = ++prodToken;
    const wantDay = prodScope === 'day' && prodDay != null;
    const dayMonth = prodMonth + 1; // l'API attend 1-based
    void fetch('/api/roof-production', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        lat: cfg.lat,
        lon: cfg.lon,
        tiltDeg: cfg.tiltDeg,
        aspect: cfg.aspect,
        mountingplace: cfg.mountingplace,
        placedPanels: prodPanels,
        ...(wantDay ? { dateMonth: dayMonth, dateDay: prodDay } : {}),
      }),
    })
      .then((r) => r.json())
      .then((data: ProductionApiResponse) => {
        if (token !== prodToken) return; // une requête plus récente a pris la main
        if (!data || data.ok !== true) return;
        // On reconstitue la production PAR 1 kWc (pour rescaler ensuite côté client) en
        // divisant la réponse mise à l'échelle par le kWc posé renvoyé.
        const placedKwc = typeof data.placedKwc === 'number' && data.placedKwc > 0 ? data.placedKwc : prodPanels * PANEL_KWC;
        prodPerKwc = perKwcFromResponse(data, placedKwc);
        prodScaled = {
          source: data.source,
          placedKwc,
          annualKwh: data.annualKwh,
          monthlyKwh: data.monthlyKwh,
          typicalDayByMonth: data.typicalDayByMonth,
          dailyKwhByMonth: data.dailyKwhByMonth,
        };
        prodSource = data.source;
        prodPlaneKey = planKey;
        prodSpecificDate = data.specificDate ?? null;
        renderProdWindow();
      })
      .catch(() => {
        /* réseau indisponible : on garde l'affichage précédent (repli gracieux) */
      });
  }

  /** Réponse JSON de /api/roof-production (forme consommée par la fenêtre). */
  interface ProductionApiResponse {
    ok: boolean;
    source: ProductionSource;
    placedKwc?: number;
    annualKwh: number;
    monthlyKwh: number[];
    dailyKwhByMonth: number[];
    typicalDayByMonth: number[][];
    specificDate: SpecificDateProfile | null;
  }

  /** Reconstitue une production PAR 1 kWc à partir d'une réponse mise à l'échelle. */
  function perKwcFromResponse(data: ProductionApiResponse, placedKwc: number): PerKwcProduction {
    const inv = placedKwc > 0 ? 1 / placedKwc : 0;
    return {
      source: data.source,
      annualKwh: data.annualKwh * inv,
      monthlyKwh: data.monthlyKwh.map((v) => v * inv),
      typicalDayByMonth: data.typicalDayByMonth.map((prof) => prof.map((v) => v * inv)),
      dailyKwhByMonth: data.dailyKwhByMonth.map((v) => v * inv),
    };
  }

  /** Déduit la config de production du winner de l'optimiseur courant (plat ou pente). */
  function prodConfigFromState(): ProdConfig | null {
    if (!closed || vertices.length < 3) return null;
    if (roofType === 'pitched') {
      const res = pitchedLiveResult;
      if (!res || res.northFacing) return null;
      const w = res.winner;
      if (w.placedCount <= 0) return null;
      return {
        lat: centroid[1],
        lon: centroid[0],
        tiltDeg: res.pitchDeg,
        aspect: res.facingAzimuthDeg - 180, // jambe sud : aspect = azimut − 180
        mountingplace: 'building',
        panels: w.placedCount,
        target: res.target,
      };
    }
    const res = liveResult;
    if (!res) return null;
    const w = res.winner;
    if (w.placedCount <= 0) return null;
    return {
      lat: centroid[1],
      lon: centroid[0],
      tiltDeg: w.tiltDeg,
      aspect: w.aspect,
      mountingplace: 'free', // toit plat racké
      panels: w.placedCount,
      target: res.target,
    };
  }

  /** Synchronise la fenêtre de production avec l'état courant (appelée après chaque rendu). */
  function syncProductionWindow() {
    if (!prodWindowEl) {
      // Même sans la fenêtre de production, on garde l'instantané de zone + le total à jour.
      snapshotActiveAreaResult();
      renderAreasPanel();
      return;
    }
    const cfg = prodConfigFromState();
    if (!cfg) {
      prodScaled = null;
      prodPerKwc = null;
      prodPanels = 0;
      renderProdWindow();
      renderLayoutPanel();
      snapshotActiveAreaResult();
      renderAreasPanel();
      return;
    }
    // W69 — en mode disposition personnalisée, le NOMBRE posé vient de l'occupation
    // éditée (pas de l'optimiseur) ; le plan (GPS/tilt/azimut) reste celui du gagnant.
    if (layoutMode && layoutState) {
      updateProductionWindow({ ...cfg, panels: occupiedCount(layoutState) });
    } else {
      updateProductionWindow(cfg);
    }
    renderLayoutPanel();
    // « Plusieurs zones » — APRÈS chaque recompute/rendu de la zone active, on écrit son
    // résultat courant (gagnant vivant) dans l'enregistrement de la zone active, puis on
    // rafraîchit le total. Hook unique partagé par les optimiseurs plat ET pente.
    snapshotActiveAreaResult();
    renderAreasPanel();
  }

  // ═══════════ « PLUSIEURS ZONES » — instantané du résultat + panneau de total ═══════════

  /** Résultat VIVANT de la zone active (gagnant de l'optimiseur courant) — plat
   *  (`liveResult.winner`) ou pente (`pitchedLiveResult.winner`). null si rien de calculé
   *  ou pose nulle (zone sans panneaux). */
  function liveActiveResult(): AreaResult | null {
    if (!closed || vertices.length < 3) return null;
    if (roofType === 'pitched') {
      const res = pitchedLiveResult;
      if (!res || res.northFacing) return null;
      const w = res.winner;
      if (w.placedCount <= 0) return null;
      return { panels: w.placedCount, kwc: w.kwc, annualKwh: w.annualKwh, savingsLow: w.savingsLow, savingsHigh: w.savingsHigh };
    }
    const res = liveResult;
    if (!res) return null;
    const w = res.winner;
    if (w.placedCount <= 0) return null;
    return { panels: w.placedCount, kwc: w.kwc, annualKwh: w.annualKwh, savingsLow: w.savingsLow, savingsHigh: w.savingsHigh };
  }

  /** Écrit l'instantané du résultat vivant dans l'enregistrement de la zone active. */
  function snapshotActiveAreaResult() {
    const a = activeArea();
    if (a) a.result = liveActiveResult();
  }

  /** Capture la GÉOMÉTRIE + l'état d'édition courants de la zone active dans son
   *  enregistrement (sans toucher au résultat, géré par le snapshot ci-dessus). */
  function snapshotActiveAreaGeometry() {
    const a = activeArea();
    if (!a) return;
    a.vertices = [...vertices];
    a.obstacles = obstacles.map((o) => ({ ...o }));
    a.roofType = roofType;
    a.pitchDeg = pitchDeg;
    a.facingAzimuthDeg = facingAzimuthDeg;
    a.neededPanels = neededPanels;
    a.neededAuto = neededAuto;
  }

  /** Active/désactive le bouton « + Ajouter une zone » : autorisé seulement quand la
   *  zone active est FERMÉE (un tracé valide existe). */
  function syncAddAreaButton() {
    if (addAreaBtn) addAreaBtn.disabled = !closed || vertices.length < 3;
  }

  /** Rend le panneau « Zones » : total agrégé (zone active = résultat LIVE, pas le snapshot
   *  potentiellement périmé) + une ligne par zone. Masqué tant qu'aucune zone n'a de résultat. */
  function renderAreasPanel() {
    syncAddAreaButton();
    if (!areasWindowEl) return;
    const liveActive = liveActiveResult();
    // Résultats agrégés : la zone active prend son résultat LIVE, les autres leur snapshot.
    const results = areas.map((a) => (a.id === activeAreaId ? liveActive : a.result));
    const anyResult = results.some((r) => r != null);
    areasWindowEl.hidden = !anyResult;
    if (!anyResult) return;
    const total = aggregateAreas(results);
    if (areasTotalPanelsEl) areasTotalPanelsEl.textContent = `${fmt(total.panels)} × 720 W`;
    if (areasTotalKwcEl) areasTotalKwcEl.textContent = `${total.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`;
    if (areasTotalProdEl) areasTotalProdEl.textContent = total.annualKwh > 0 ? `${fmt(Math.round(total.annualKwh))} kWh/an` : '—';
    if (areasTotalSavingsEl) areasTotalSavingsEl.textContent = total.savingsHigh > 0 ? `${fmtMad(total.savingsLow)} – ${fmtMad(total.savingsHigh)}/an` : '—';
    if (!areasListEl) return;
    areasListEl.innerHTML = areas
      .map((a, i) => {
        const r = a.id === activeAreaId ? liveActive : a.result;
        const active = a.id === activeAreaId;
        const panels = r ? fmt(r.panels) : '—';
        const kwc = r ? `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc` : 'à tracer';
        const rowClass = active
          ? 'border-brass-400 bg-brass-400/10'
          : 'border-white/10 bg-nuit-900/40';
        const delBtn =
          areas.length > 1
            ? `<button type="button" data-area-del="${a.id}" aria-label="Supprimer ${esc(a.label)}" class="border border-alert-300/60 px-2.5 py-1 text-xs font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">×</button>`
            : '';
        const viewBtn = active
          ? `<span class="text-xs font-semibold text-brass-300">● active</span>`
          : `<button type="button" data-area-select="${a.id}" class="border border-white/25 px-2.5 py-1 text-xs font-semibold text-lune-soft transition-colors hover:border-brass-400 hover:text-brass-300">Voir</button>`;
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border ${rowClass} p-3 text-sm" data-area-row="${a.id}">
          <span class="font-semibold text-white">${esc(areaLabel(i))}</span>
          <span class="text-xs text-lune-faint">${panels} panneaux · ${kwc}</span>
          <span class="ml-auto flex items-center gap-2">${viewBtn}${delBtn}</span>
        </li>`;
      })
      .join('');
  }

  // ═══════════ W68 — « Affiner ma consommation » : logique de rendu/recompute ═══════════

  /** kWh/jour dérivé de la facture (le socle). billToAnnualKwh ÷ 365. */
  function billDailyKwh(): number {
    const annual = billToAnnualKwh(monthlyBill());
    return annual > 0 ? annual / 365 : 0;
  }

  /** Profil horaire de PUISSANCE (kW) du jour-type courant (production), aligné 24 h.
   *  Source = la même production PVGIS que la fenêtre (jour-type du mois sélectionné,
   *  ou la date précise). Vide si aucun plan n'est calculé. */
  function productionHourly(): HourlyCurve {
    if (!prodScaled) return emptyCurve();
    if (prodSpecificDate && Array.isArray(prodSpecificDate.hourlyKw) && prodSpecificDate.hourlyKw.length === HOURS_PER_DAY) {
      return prodSpecificDate.hourlyKw.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
    }
    const prof = prodScaled.typicalDayByMonth[prodMonth];
    if (Array.isArray(prof) && prof.length === HOURS_PER_DAY) return prof.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
    return emptyCurve();
  }

  /** Recompose la courbe de conso depuis le socle (facture) + appareils, SAUF si
   *  l'utilisateur l'a éditée à la main (auquel cas on garde son override). */
  function rebuildConsCurve() {
    consDailyTarget = billDailyKwh();
    if (consHandEdited) return; // override manuel respecté
    const base = baselineCurve(consDailyTarget);
    consCurve = composeConsumption(base, consAppliances);
  }

  /** Met à jour le besoin « panneaux nécessaires » quand des appareils « en plus »
   *  augmentent la conso (taille-au-besoin via le chemin existant). N'agit qu'en mode
   *  auto (l'utilisateur n'a pas figé le besoin).
   *
   *  GARDE DE RÉ-ENTRANCE (correctif du FIGEAGE) : ce chemin boucle —
   *  applyConsumptionToSizing → renderActive → liveResolveFlat (qui réécrit `neededPanels`
   *  depuis la FACTURE, ≠ besoin issu de la conso) → syncProductionWindow → renderProdWindow
   *  → renderConsumption → applyConsumptionToSizing → … Comme les deux besoins divergent, la
   *  page bouclait à l'infini dès qu'on ouvrait « Affiner ma consommation ». On garde donc la
   *  ré-entrance ET on FIGE le besoin issu de la conso (`neededAuto = false`) pour que
   *  liveResolveFlat ne le rebascule pas — la boucle se termine en un seul cycle. */
  let inConsSizing = false;
  function applyConsumptionToSizing() {
    if (!neededAuto || inConsSizing) return;
    const dailyTotal = curveTotal(consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    if (annualCons <= 0) return;
    const n = neededPanelsForTarget(annualCons, centroidLat);
    if (n <= 0) return;
    const clamped = clampNeeded(n);
    if (clamped === neededPanels) return;
    inConsSizing = true;
    neededPanels = clamped;
    neededAuto = false; // besoin issu de la conso → figé (liveResolveFlat ne le réécrit plus)
    renderActive(); // re-résout l'optimiseur avec le nouveau besoin (chemin existant)
    inConsSizing = false;
  }

  /** Rendu du graphe de conso (barres glissables) + superposition production (or pâle). */
  function renderConsGraph() {
    if (!consGraphEl) return;
    const W = 480;
    const H = 160;
    const padBottom = 16;
    const padTop = 8;
    const plotH = H - padTop - padBottom;
    const prod = productionHourly();
    const maxC = consCurve.reduce((m, v) => Math.max(m, v), 0);
    const maxP = prod.reduce((m, v) => Math.max(m, v), 0);
    const max = Math.max(maxC, maxP, 1e-6);
    const slot = W / HOURS_PER_DAY;
    const barW = slot * 0.74;
    const yFor = (v: number) => padTop + (plotH - (v / max) * plotH);
    // Aire de production (or pâle) en arrière-plan.
    let prodPath = '';
    prod.forEach((v, h) => {
      const x = h * slot + slot / 2;
      prodPath += `${h === 0 ? 'M' : 'L'}${x.toFixed(1)} ${yFor(v).toFixed(1)} `;
    });
    const baseY = (H - padBottom).toFixed(1);
    const prodArea = maxP > 0
      ? `<path d="${prodPath}L${(W).toFixed(1)} ${baseY} L0 ${baseY} Z" fill="var(--color-brass-400,#e8b54a)" fill-opacity="0.10"/><path d="${prodPath}" fill="none" stroke="var(--color-brass-400,#e8b54a)" stroke-opacity="0.4" stroke-width="1.5"/>`
      : '';
    // Barres de conso (glissables) — chacune porte data-hour.
    const bars = consCurve
      .map((v, h) => {
        const x = h * slot + (slot - barW) / 2;
        const y = yFor(v);
        const barH = Math.max(0, H - padBottom - y);
        return `<rect class="rp9-cons-bar" data-hour="${h}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${barH.toFixed(1)}" rx="1" fill="var(--color-azur-300,#7fb4e8)" fill-opacity="0.85" tabindex="0" role="slider" aria-label="Consommation à ${h} h" aria-valuenow="${v.toFixed(2)}"><title>${h} h : ${v.toFixed(2)} kWh</title></rect>`;
      })
      .join('');
    const ticks = [0, 6, 12, 18, 23]
      .map((h) => `<text x="${(h * slot + slot / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" text-anchor="middle" font-size="8" fill="var(--color-lune-faint,#6f7791)">${h}h</text>`)
      .join('');
    consGraphEl.innerHTML = `<line x1="0" y1="${baseY}" x2="${W}" y2="${baseY}" stroke="var(--color-white,#fff)" stroke-opacity="0.12" stroke-width="1"/>${prodArea}${bars}${ticks}`;
  }

  /** Saisie numérique des 24 heures (obligatoire mobile + mouvement réduit). */
  function renderConsInputs() {
    if (!consInputsEl) return;
    consInputsEl.innerHTML = consCurve
      .map(
        (v, h) =>
          `<label class="rp9-cons-hour">${h}h<input type="text" inputmode="decimal" data-hour="${h}" value="${v.toFixed(2)}" aria-label="Consommation à ${h} h en kWh" /></label>`,
      )
      .join('');
  }

  /** Recompute complet de la conso (synthèse + graphe + saisie) + impact sizing/batterie. */
  function renderConsumption() {
    if (!consWindowEl) return;
    // La fenêtre n'apparaît que lorsqu'un plan de production existe.
    const ready = !!prodScaled && prodPanels > 0;
    consWindowEl.hidden = !ready;
    if (!ready) return;
    rebuildConsCurve();
    if (!consMode) return; // panneau replié : rien à dessiner

    const prod = productionHourly();
    const dailyTotal = curveTotal(consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    const selfDaily = selfConsumptionDailyKwh(consCurve, prod);
    const savings = savingsFromHourly(consCurve, prod, annualCons, tariffForCity(undefined));
    const batt = batterySizing(consCurve, prod);

    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(selfDaily)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = annualCons > 0 ? fmtSavings(savings.low, savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = batt.batteries > 0 ? `${batt.batteries} × 6 kWh` : 'aucune';

    renderConsGraph();
    renderConsInputs();
    renderApplianceList();
    applyConsumptionToSizing();
  }

  /** Liste des appareils ajoutés : créneau + bascule « en plus » / « déjà compris » + suppr. */
  function renderApplianceList() {
    if (!applListEl) return;
    if (consAppliances.length === 0) {
      applListEl.innerHTML = '<li class="text-xs text-lune-faint">Aucun appareil ajouté — votre courbe suit le type calé sur la facture.</li>';
      return;
    }
    applListEl.innerHTML = consAppliances
      .map((a, i) => {
        const onTop = a.billing === 'onTop';
        return `<li class="flex flex-wrap items-center gap-x-3 gap-y-1 border border-white/10 bg-nuit-900/40 p-3 text-sm" data-appl="${i}">
          <span class="font-semibold text-white">${esc(a.label)}</span>
          <span class="text-xs text-lune-faint">${fmt1(a.dailyKwh)} kWh/j · ${a.startHour}h–${((a.endHour % 24) + 24) % 24}h</span>
          <button type="button" data-appl-toggle="${i}" class="ml-auto border px-2.5 py-1 text-xs font-semibold transition-colors ${onTop ? 'border-brass-400 text-brass-300' : 'border-white/25 text-lune-soft'}">${onTop ? 'En plus de la facture' : 'Déjà compris'}</button>
          <button type="button" data-appl-del="${i}" aria-label="Supprimer" class="border border-alert-300/60 px-2.5 py-1 text-xs font-semibold text-alert-300 transition-colors hover:bg-alert-300/10">×</button>
        </li>`;
      })
      .join('');
  }

  // ═══════════ W69 — « Personnaliser la disposition » : lattice + 3D + recompute ═══════════

  /** Plafond de comptage (besoin/footprint) pour l'ajout : on ne dépasse jamais ce qui
   *  TIENT physiquement (grid.panels.length) ni le besoin si l'utilisateur l'a figé. */
  function layoutCap(): number {
    const fit = layoutPlan ? layoutPlan.grid.panels.length : 0;
    // Le besoin plafonne aussi (taille-au-besoin) : on autorise jusqu'au max(besoin, fit
    // optimal) mais jamais au-delà de ce qui tient — la lattice borne déjà tout.
    return fit;
  }

  /** (Re)crée l'état de disposition depuis le plan gagnant courant (toutes cellules
   *  valides occupées jusqu'au comptage optimal). */
  function ensureLayoutState() {
    if (!layoutPlan) {
      layoutState = null;
      return;
    }
    if (!layoutState) {
      layoutState = createLayoutState(layoutPlan.grid.panels, layoutOptimalCount);
      layoutSel = null;
    }
  }

  /** Re-rend la 3D avec l'occupation PERSONNALISÉE courante (même plan, même rendement
   *  par panneau ; seul le NOMBRE change), puis recompute la production/économies par le
   *  chemin PVGIS-par-comptage existant (la fenêtre de production suit prodPanels). */
  function renderCustomLayout() {
    if (!layoutPlan || !layoutState) return;
    const occ = new Set(layoutState.occupied);
    renderScene(layoutPlan.pack, layoutPlan.grid, layoutPlan.tiltDeg, layoutPlan.family, occ.size, layoutPlan.flush, occ);
    // Recompute par COMPTAGE (jamais un rendement inventé) : on met prodPanels au nombre
    // posé et on laisse la fenêtre de production rescaler en kWc (linéaire) côté client.
    const count = occ.size;
    const cfg = prodConfigFromState();
    if (cfg) updateProductionWindow({ ...cfg, panels: count });
    // « Plusieurs zones » — garde l'instantané + le total à jour après chaque édition de
    // disposition (le résultat de zone suit le gagnant vivant, hook partagé).
    snapshotActiveAreaResult();
    renderAreasPanel();
  }

  /** Convertit un point ÉCRAN (carte) en coordonnées ENU relatives à l'origine de la
   *  scène — c'est le « raycast sur le plan du toit » : on déprojette en lng/lat puis on
   *  passe en mètres locaux (même repère que PackedPanel.cx/cy). */
  function screenToENU(point: maplibregl.Point): { x: number; y: number } | null {
    if (!layoutPlan) return null;
    const ll = map.unproject(point);
    const origin = layoutPlan.pack.origin;
    const cosLat = Math.cos(origin[1] * DEG2RAD);
    return { x: (ll.lng - origin[0]) * DEG2M * cosLat, y: (ll.lat - origin[1]) * DEG2M };
  }

  /** Rendu du plan tactile des emplacements (cellules occupées/libres) + synthèse. */
  function renderLayoutPanel() {
    if (!layoutWindowEl) return;
    const ready = !!layoutPlan && layoutPlan.grid.panels.length > 0 && closed;
    layoutWindowEl.hidden = !ready;
    if (!ready) return;
    if (!layoutMode) return;
    ensureLayoutState();
    if (!layoutState) return;

    const count = occupiedCount(layoutState);
    const free = emptyIndices(layoutState).length;
    const kwc = count * PANEL_KWC;
    if (layoutCountEl) layoutCountEl.textContent = fmt(count);
    if (layoutKwcEl) layoutKwcEl.textContent = `${fmt1(kwc)} kWc`;
    if (layoutFreeEl) layoutFreeEl.textContent = fmt(free);
    const cover = neededPanels > 0 ? Math.round((count / neededPanels) * 100) : 0;
    if (layoutCoverEl) layoutCoverEl.textContent = neededPanels > 0 ? `${cover} %` : '—';
    if (layoutMinusEl) layoutMinusEl.disabled = count <= 0;
    if (layoutPlusEl) layoutPlusEl.disabled = free <= 0 || count >= layoutCap();

    // Mini-plan des cellules : occupées (bleu) / libres (gris→vert au survol).
    if (layoutGridEl && layoutState) {
      layoutGridEl.innerHTML = layoutState.cells
        .map((c) => {
          const occupied = layoutState!.occupied.has(c.index);
          const selected = layoutSel === c.index;
          return `<button type="button" class="rp9-layout-cell" data-cell="${c.index}" data-occupied="${occupied}" aria-pressed="${selected}" aria-label="${occupied ? 'Panneau' : 'Emplacement libre'} ${c.index + 1}"></button>`;
        })
        .join('');
    }
    if (layoutNoteEl && !layoutNoteEl.textContent) {
      layoutNoteEl.textContent = 'Touchez un panneau (bleu) pour le sélectionner, puis un emplacement libre (vert) pour l’y déplacer. Ou utilisez + / −.';
    }
  }

  /** Entrée/sortie du mode personnalisation. */
  function setLayoutMode(on: boolean) {
    layoutMode = on;
    if (layoutToggleEl) layoutToggleEl.setAttribute('aria-pressed', String(on));
    if (layoutPanelEl) layoutPanelEl.hidden = !on;
    // Vue de DESSUS pendant le déplacement : à plat (pitch 0), la déprojection écran→toit est
    // exacte (aucune parallaxe de hauteur), donc glisser un panneau sur la 3D « accroche »
    // vraiment au bon panneau. On restaure la vue inclinée en sortant.
    const view = on ? { pitch: 0 } : { pitch: PITCH_VIEW };
    if (opts.reducedMotion) map.jumpTo(view);
    else map.easeTo({ ...view, duration: 500, essential: true });
    if (on) {
      layoutState = null; // repart de l'optimum courant
      ensureLayoutState();
      renderCustomLayout();
    } else {
      // En sortant, on re-rend la disposition de l'optimiseur (recalc rebranche tout).
      layoutSel = null;
      if (closed) renderActive();
    }
    renderLayoutPanel();
  }

  /** Cœur W34 : re-résolution CONTRAINTE vivante (verrous courants) + rendu + badges. */
  function liveResolveFlat() {
    if (!closed || vertices.length < 3 || roofType !== 'flat') return;
    const ring: LngLat[] = [...vertices];
    const bill = monthlyBill();
    const locks = buildFlatLocks();
    const yieldFn = (tiltDeg: number, aspect: number): number | null => {
      const v = v4YieldCache.get(v4Key(tiltDeg, aspect));
      return v == null ? null : v;
    };
    const res = solveLive(ring, centroidLat, bill, obstructionRings(), locks, { yieldFn });
    liveResult = res;
    if (neededAuto) neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : 0;
    const hasLocks = !!(locks.orientation || locks.tiltDeg != null || locks.layout || locks.margin || locks.need != null);
    useRecommended = !hasLocks;
    mapWinnerToSel(res.winner);
    if (azimuthGroup) azimuthGroup.hidden = !res.hasAlignedChoice;
    renderLiveWinner(res, !hasLocks);
    updateLiveBadges(res);
    syncChips();
    ensurePvgisForLockedTilt(locks);
    syncProductionWindow(); // W50 — reflète le plan gagnant dans la fenêtre de production
  }

  /** Affine PVGIS pour une inclinaison VERROUILLÉE hors grille (curseur fin), en
   *  arrière-plan (débattu) puis re-résout. La grille standard est déjà couverte par
   *  computeMatrixPvgis ; ici on n'interroge QUE l'inclinaison choisie. */
  function ensurePvgisForLockedTilt(locks: AxisLocks) {
    if (roofType !== 'flat' || locks.tiltDeg == null || !closed) return;
    const t = Math.round(locks.tiltDeg);
    const roofAz = roofDominantAzimuthDeg([...vertices]);
    const aspects = [...new Set(pvgisMatrixCandidatePairs(centroidLat, roofAz).map((p) => p.aspect))];
    const missing = aspects.filter((a) => !v4YieldCache.has(v4Key(t, a)));
    if (!missing.length) return;
    if (liveTiltTimer != null) clearTimeout(liveTiltTimer);
    const token = ++liveToken;
    liveTiltTimer = setTimeout(() => {
      void Promise.all(missing.map((a) => v4SpecificYield(t, a))).then(() => {
        if (token !== liveToken || roofType !== 'flat') return;
        liveResolveFlat();
      });
    }, 280);
  }

  /** « Réinitialiser » (toit plat) : relâche TOUS les verrous → optimum global. */
  function resetFlatLocks() {
    pinned.clear();
    neededAuto = true;
    useRecommended = true;
    liveResolveFlat();
  }

  /** renderSelection : alias historique → solveur vivant (toit plat). */
  function renderSelection() {
    liveResolveFlat();
  }

  interface CardData {
    title: string;
    isReco: boolean;
    count: number;
    kwc: number;
    annualKwh: number;
    pct: number;
    savingsLow: number;
    savingsHigh: number;
    why: string;
  }

  function paintCard(d: CardData, sourceLabel?: string) {
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    set('rp9-reco-title', d.isReco ? `${d.title}  ·  ✓ recommandé` : d.title);
    set('rp9-reco-kwc', `${d.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rp9-reco-panels', `${fmt(d.count)} × 720 W`);
    set('rp9-reco-prod', d.annualKwh > 0 ? `${fmt(Math.round(d.annualKwh))} kWh/an` : '—');
    set('rp9-reco-cover', d.pct > 0 ? `${Math.round(d.pct)} %` : '—');
    set('rp9-reco-savings', `${fmtMad(d.savingsLow)} – ${fmtMad(d.savingsHigh)}/an`);
    const why = $('rp9-reco-why');
    if (why) why.textContent = d.why + (sourceLabel ? ` ${sourceLabel}` : '');
    const bif = $('rp9-reco-bifacial');
    if (bif) {
      const gain = d.annualKwh * 0.05;
      bif.textContent = d.annualKwh > 0 ? `+ gain bifacial (estimation prudente, ~+5 %) : ~${fmt(Math.round(gain))} kWh/an — non compté dans le chiffre ci-dessus.` : '';
    }
    $('rp9-results')?.classList.add('rp9-results--ready');
    const cta = $<HTMLButtonElement>('rp9-cta');
    if (cta && d.count > 0) {
      cta.hidden = false;
      cta.onclick = () => prefillLead(d);
    }
  }

  function paintMaxLine() {
    if (!rec) return;
    const maxline = $('rp9-maxline');
    if (maxline) {
      maxline.textContent = `Rendement max par panneau : ~${rec.maxPerPanelTiltDeg}° plein sud. Énergie totale max sur CE toit : ~${rec.maxRoofEnergyTiltDeg}° (un toit limité gagne à être plus plat pour loger plus de panneaux).`;
    }
  }

  // — Comparatif —
  // ── V6 — MATRICE complète : balayage dense AFFICHÉ (triable, filtrable) ──────────
  // FIX 2 : on ne montre plus ~6 configs nommées, mais TOUTES les lignes évaluées par
  // fineGridMatrixV6, avec l'optimum réel épinglé en tête et badgé « Recommandé ».

  /** Clé stable d'une ligne (famille|inclinaison|azimut|pose|marge) — sert d'id de
   *  ligne (réutilise le highlight existant) et de comparaison au gagnant. */
  function matrixRowKey(r: MatrixEvalV6): string {
    return `${r.family}|${r.tiltDeg}|${Math.round(r.azimuthDeg)}|${r.orientation}|${r.margin}`;
  }

  function isMatrixWinner(r: MatrixEvalV6): boolean {
    const w = matrixResult?.winner;
    return !!w && matrixRowKey(r) === matrixRowKey(w);
  }

  /** Lignes ordonnées selon le tri + filtre courants (vrai regroupement, lisible). */
  function matrixOrderedRows(): MatrixEvalV6[] {
    if (!matrixResult) return [];
    const rows = matrixFilter === 'all' ? matrixResult.rows : matrixResult.rows.filter((r) => matrixGroupKey(r) === matrixFilter);
    return sortMatrix(rows, matrixSort.key, matrixSort.dir);
  }

  /** (Re)peuple le menu de filtre par orientation/pose à partir de la matrice. */
  function syncMatrixFilter() {
    const sel = $<HTMLSelectElement>('rp9-matrix-filter');
    if (!sel || !matrixResult) return;
    const groups = [...new Set(matrixResult.rows.map(matrixGroupKey))].sort();
    const want = ['all', ...groups];
    const current = want.join('|');
    if (sel.dataset.built !== current) {
      sel.innerHTML =
        `<option value="all">Toutes les orientations (${matrixResult.rows.length} configs)</option>` +
        groups.map((g) => `<option value="${g}">${g}</option>`).join('');
      sel.dataset.built = current;
    }
    if (matrixFilter !== 'all' && !groups.includes(matrixFilter)) matrixFilter = 'all';
    sel.value = matrixFilter;
  }

  /** Reflète l'en-tête de tri actif (flèche + aria-sort sur la cellule) sur les
   *  colonnes triables. `data-rp9-sort` vit sur le bouton ; aria-sort sur son <th>. */
  function syncMatrixSortHeaders() {
    for (const btn of Array.from(document.querySelectorAll<HTMLElement>('[data-rp9-sort]'))) {
      const key = btn.dataset.rp9Sort as MatrixSortKey;
      const active = key === matrixSort.key;
      btn.dataset.active = active ? 'true' : 'false';
      const th = btn.closest('th');
      if (th) th.setAttribute('aria-sort', active ? (matrixSort.dir === 'desc' ? 'descending' : 'ascending') : 'none');
      const arrow = btn.querySelector('.rp9-sort-arrow');
      if (arrow) arrow.textContent = active ? (matrixSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
    }
  }

  function paintComparison() {
    // W35 — la matrice plate ne doit JAMAIS repeindre le tableau en mode pente
    // (le comparatif pente est rendu par paintPitchedComparison).
    if (roofType !== 'flat' || !rec || !matrixResult) return;
    const tbody = $('rp9-compare');
    const wrap = $('rp9-compare-wrap');
    if (!tbody) return;
    syncMatrixFilter();
    syncMatrixSortHeaders();
    const target = matrixResult.targetAnnualKwh;
    const winner = matrixResult.winner;
    // Optimum réel ÉPINGLÉ en tête, puis le reste de la matrice (triée/filtrée).
    const rest = matrixOrderedRows().filter((r) => !isMatrixWinner(r));
    const rows = [winner, ...rest];
    tbody.innerHTML = '';
    for (const r of rows) {
      const tr = document.createElement('tr');
      const key = matrixRowKey(r);
      tr.dataset.id = key;
      const win = isMatrixWinner(r);
      const cover = target > 0 ? Math.round(r.pctOfTarget) : 0;
      const badge = win ? ' <span style="color:var(--color-brass-300)">✓ Recommandé</span>' : '';
      tr.innerHTML =
        `<td>${r.label}${badge}</td>` +
        `<td class="num">${fmt(r.placedCount)}</td>` +
        `<td class="num">${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(r.annualKwh))}</td>` +
        `<td class="num">${cover} %</td>` +
        `<td class="num">${fmtMad(r.savingsLow)} – ${fmtMad(r.savingsHigh)}</td>`;
      tr.addEventListener('click', () => renderMatrixRow(r));
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
    highlightRow(isMatrixWinner(winner) ? matrixRowKey(winner) : null);
  }

  /** Rend EXACTEMENT cette ligne de la matrice en 3D (azimut span quelconque géré) :
   *  pavage à l'azimut/marge de la ligne, puis le rendu unifié toit plat. */
  function renderMatrixRow(r: MatrixEvalV6) {
    if (!closed || vertices.length < 3) return;
    useRecommended = false;
    const ring: LngLat[] = [...vertices];
    const setbackM = r.margin === 'keep' ? PERIMETER_SETBACK_M : 0;
    const pack = packConfig(ring, centroidLat, {
      family: r.family,
      tiltDeg: r.tiltDeg,
      azimuthDeg: r.azimuthDeg,
      obstructions: obstructionRings(),
      setbackM,
    });
    const grid = r.orientation === 'portrait' ? pack.portrait : pack.landscape;
    renderConfig({
      pack,
      grid,
      family: r.family,
      tiltDeg: r.tiltDeg,
      azimuthDeg: pack.azimuthDeg,
      isReco: isMatrixWinner(r),
      title: `${r.label}${isMatrixWinner(r) ? '  ·  ✓ recommandé' : ''}`,
      why: isMatrixWinner(r)
        ? matrixResult?.optimumRow.reason ?? ''
        : 'Vous explorez une configuration de la matrice. La ligne « Recommandé » reste le meilleur compromis pour votre facture.',
      sourceLabel: matrixResult?.yieldSource === 'pvgis' ? '(production affinée via PVGIS au GPS exact)' : '(production estimée — table par latitude)',
      rowId: matrixRowKey(r),
    });
  }

  function highlightRow(id: string | null) {
    const tbody = $('rp9-compare');
    if (!tbody) return;
    for (const tr of Array.from(tbody.querySelectorAll('tr'))) {
      (tr as HTMLElement).dataset.active = (id != null && (tr as HTMLElement).dataset.id === id) ? 'true' : 'false';
    }
  }

  /** Recalcule la matrice (estimation instantanée) et la peint. Le balayage PVGIS au
   *  GPS exact suit en asynchrone (computeMatrixPvgis). */
  function recomputeMatrix() {
    if (!closed || vertices.length < 3 || roofType !== 'flat') return;
    const ring: LngLat[] = [...vertices];
    matrixResult = fineGridMatrixV6(ring, centroidLat, monthlyBill(), obstructionRings());
    paintComparison();
  }

  // Bascule de tri (clic sur en-tête) : même colonne → inverse le sens, sinon nouvelle
  // colonne en décroissant. Repeint sans re-balayer (la matrice est déjà calculée).
  function setMatrixSort(key: MatrixSortKey) {
    if (roofType !== 'flat') return; // le tri/filtre n'existent qu'en toit plat
    if (matrixSort.key === key) matrixSort.dir = matrixSort.dir === 'desc' ? 'asc' : 'desc';
    else matrixSort = { key, dir: 'desc' };
    paintComparison();
  }

  // ═══════════ V3 — Optimum (recherche pleine) + toit en pente (pose affleurante) ═══════════

  const facingLabel = (az: number): string => {
    const m: Record<number, string> = { 180: 'sud', 135: 'sud-est', 225: 'sud-ouest', 90: 'est', 270: 'ouest', 0: 'nord' };
    return m[Math.round(az)] ?? `${Math.round(az)}°`;
  };

  // Adaptateurs FlushPack/FlushGrid (V3) → PackResult/PanelGrid pour réutiliser le
  // rendu 3D existant en mode affleurant (flush=true). family='south' (mono-MPPT,
  // jamais de chevron), azimut = face du pan, inclinaison = pente.
  function flushGridToPanelGrid(fg: FlushGrid): PanelGrid {
    const slopeLenM = fg.orientation === 'portrait' ? PANEL2_LONG_M : PANEL2_SHORT_M;
    const rowWidthM = fg.orientation === 'portrait' ? PANEL2_SHORT_M : PANEL2_LONG_M;
    return {
      panelOrientation: fg.orientation,
      count: fg.count,
      kwc: fg.kwc,
      rowPitchM: fg.rowPitchM,
      panels: fg.panels,
      slopeLenM,
      rowWidthM,
      footprintPerPanelM2: fg.footprintPerPanelM2,
    };
  }
  function flushToPack(fp: FlushPack): PackResult {
    return {
      origin: fp.origin,
      ringENU: fp.ringENU,
      azimuthDeg: fp.facingAzimuthDeg,
      tiltDeg: fp.pitchDeg,
      family: 'south',
      areaM2: fp.areaM2,
      usableAreaM2: fp.usableAreaM2,
      portrait: flushGridToPanelGrid(fp.portrait),
      landscape: flushGridToPanelGrid(fp.landscape),
      best: flushGridToPanelGrid(fp.best),
    };
  }

  function pitchedWhy(): string {
    if (!pitchedRec) return '';
    const p = pitchedRec.planes[0];
    if (p.northFacing) {
      return `Ce pan est orienté ${facingLabel(facingAzimuthDeg)} (trop au nord) : aucune pose recommandée. Choisissez un pan orienté sud, est ou ouest.`;
    }
    const cover = Math.round(pitchedRec.pctOfTarget);
    const head = `Pose affleurante sur la pente (~${Math.round(p.pitchDeg)}°, face ${facingLabel(facingAzimuthDeg)})`;
    if (pitchedRec.roofLimited) {
      return `${head} : ${pitchedRec.totalPlacedCount} panneaux, ~${cover} % de votre consommation. Ce pan ne couvre pas tout le besoin.`;
    }
    return `${head} : dimensionné à votre besoin — ${pitchedRec.totalPlacedCount} panneaux, ~${cover} %. Inclinaison et azimut imposés par le toit.`;
  }
  function pitchedNote(): string {
    if (!pitchedRec) return '';
    const p = pitchedRec.planes[0];
    const yld = pitchedPvgisPerKwc != null ? Math.round(pitchedPvgisPerKwc) : Math.round(p.perPanelYield);
    const src = pitchedPvgisPerKwc != null ? 'PVGIS, pose « building »' : 'table committée (PVGIS indisponible)';
    return `Inclinaison ${Math.round(p.pitchDeg)}° = pente · azimut ${Math.round(p.facingAzimuthDeg)}° = face (imposés, non balayés). Rendement ${src} : ~${yld} kWh/kWc/an. Panneaux qui tiennent sur ce pan : ${p.fitCount}.`;
  }

  function renderPitched() {
    if (!pitchedRec) return;
    const plane = pitchedRec.planes[0];
    const fp = plane.pack;
    const fg = plane.orientation === 'portrait' ? fp.portrait : fp.landscape;
    renderScene(flushToPack(fp), flushGridToPanelGrid(fg), fp.pitchDeg, 'south', plane.placedCount, true);
    // V5 : production de vérité = PVGIS au (pente, face) réels, pose 'building'.
    // Disponible → on remplace la valeur table par le chiffre PVGIS et on recalcule
    // couverture + économies de façon cohérente ; sinon repli table (« estimé »).
    const target = pitchedRec.targetAnnualKwh;
    const usePvgis = pitchedPvgisPerKwc != null && pitchedRec.totalKwc > 0 && !plane.northFacing;
    const annualKwh = usePvgis ? pitchedRec.totalKwc * (pitchedPvgisPerKwc as number) : pitchedRec.totalAnnualKwh;
    const pct = target > 0 ? (annualKwh / target) * 100 : 0;
    const savings = usePvgis ? annualSavingsMad(annualKwh, target, tariffForCity(undefined)) : { low: pitchedRec.savingsLow, high: pitchedRec.savingsHigh };
    paintCard(
      {
        title: `Toit en pente ~${Math.round(fp.pitchDeg)}° · face ${facingLabel(facingAzimuthDeg)}`,
        isReco: true,
        count: pitchedRec.totalPlacedCount,
        kwc: pitchedRec.totalKwc,
        annualKwh,
        pct,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: pitchedWhy(),
      },
      usePvgis ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(plane.fitCount, 'pente');
    if (pitchedNoteEl) pitchedNoteEl.textContent = pitchedNote();
    if (pitchValueEl) pitchValueEl.textContent = `${Math.round(fp.pitchDeg)}°`;
    highlightRow(null);
  }

  // ═══════════ W35 — OPTIMISEUR CONTRAINT VIVANT (toit en pente, cerveau V8) ═══════════
  // Jumeau de l'optimiseur plat (W34) : axes libres = pose + marge (+ cible besoin),
  // inclinaison = pente et azimut = face IMPOSÉS (jamais optimisés). Verrouiller un axe
  // le tient et re-résout l'autre ; production PVGIS au (pente, face), pose 'building'.

  /** Verrous pente courants (pose + marge) + cible besoin (partagée via neededAuto). */
  function buildPitchedLocks(): { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number } {
    const locks: { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number } = {};
    if (pitchedLocks.layout) locks.layout = pitchedLocks.layout;
    if (pitchedLocks.margin) locks.margin = pitchedLocks.margin;
    if (!neededAuto && neededPanels > 0) locks.need = neededPanels;
    return locks;
  }

  function liveResolvePitched() {
    if (!closed || vertices.length < 3 || roofType !== 'pitched') return;
    const ring: LngLat[] = [...vertices];
    const bill = monthlyBill();
    const locks = buildPitchedLocks();
    const yieldFn = (pitch: number, facing: number): number | null => {
      const v = pitchedYieldCache.get(pitchedKey(pitch, facing));
      return v == null ? null : v;
    };
    const res = solveLivePitched(ring, centroidLat, bill, pitchDeg, facingAzimuthDeg, obstructionRings(), locks, { yieldFn });
    pitchedLiveResult = res;
    if (neededAuto) neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : 0;
    const hasLocks = !!(locks.layout || locks.margin || locks.need != null);
    renderPitchedWinner(res, !hasLocks);
    updatePitchedBadges(res);
    paintPitchedComparison(res);
    syncPitchedChips(res);
    syncProductionWindow(); // W50 — reflète le plan gagnant (pente) dans la fenêtre de production
  }

  function renderPitchedWinner(res: PitchedLiveResult, isReco: boolean) {
    const w = res.winner;
    renderScene(flushToPack(w.pack), flushGridToPanelGrid(w.grid), w.pack.pitchDeg, 'south', w.placedCount, true);
    const cov = Math.round(w.pctOfTarget);
    const tiltTxt = `${Math.round(pitchDeg)}°`;
    const why = res.northFacing
      ? `Ce pan est orienté nord (face ${facingLabel(facingAzimuthDeg)}) : aucune pose rentable proposée. Indiquez la vraie face descendante du pan.`
      : isReco
        ? `Pose affleurante optimale : ${w.placedCount} panneaux (${w.layoutLabel}, ${w.marginLabel}) ≈ ${cov} % de la facture. Inclinaison ${tiltTxt} = pente, azimut = face — imposés par la toiture, non optimisés.`
        : `Vos choix sont tenus, le reste re-résolu : ${w.placedCount} panneaux ≈ ${cov} % de la facture. Les badges « Recommandé » montrent la pose/marge optimale.`;
    paintCard(
      {
        title: `Toit en pente ~${tiltTxt} · face ${facingLabel(facingAzimuthDeg)} · ${w.layoutLabel}`,
        isReco,
        count: w.placedCount,
        kwc: w.kwc,
        annualKwh: w.annualKwh,
        pct: w.pctOfTarget,
        savingsLow: w.savingsLow,
        savingsHigh: w.savingsHigh,
        why,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(w.grid.count, 'pente');
    if (pitchValueEl) pitchValueEl.textContent = tiltTxt;
    if (pitchedNoteEl) {
      pitchedNoteEl.textContent = `Inclinaison ${tiltTxt} = pente · azimut ${Math.round(facingAzimuthDeg)}° = face (imposés, non balayés). Pose affleurante, sans rangées espacées. Panneaux qui tiennent : ${w.fitCount}.`;
    }
    highlightRow(null);
    if (optimumNoteEl) {
      optimumNoteEl.textContent = isReco
        ? 'Optimum vivant (pente) : pose et marge calées au mieux ; inclinaison et azimut imposés par le toit.'
        : 'Optimum vivant (pente) : votre choix est tenu, pose/marge re-résolues autour. « Réinitialiser » relâche tout.';
    }
  }

  /** Badge « Recommandé » sur la pose (data-orient) et la marge (data-margin) en pente. */
  function updatePitchedBadges(res: PitchedLiveResult) {
    const show = (b: Element | null, on: boolean) => {
      const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
      if (badge) badge.hidden = !on;
    };
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      show(b, b.dataset.orient !== 'auto' && b.dataset.orient === res.recommended.layout),
    );
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => show(b, b.dataset.margin === res.recommended.margin));
  }

  /** Puces pose/marge : la valeur du gagnant affichée pressée (verrou ou auto). */
  function syncPitchedChips(res: PitchedLiveResult) {
    const w = res.winner;
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.orient === w.layout)),
    );
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset.margin === w.margin)),
    );
  }

  /** Tableau comparatif de l'espace LIBRE en pente (≤ 4 lignes : pose × marge),
   *  l'optimum badgé « Recommandé ». Réutilise le tableau de la matrice plate. */
  function paintPitchedComparison(res: PitchedLiveResult) {
    const tbody = $('rp9-compare');
    const wrap = $('rp9-compare-wrap');
    if (!tbody) return;
    const rowKey = (r: PitchedLiveResult['winner']) => `${r.layout}|${r.margin}`;
    const wk = rowKey(res.winner);
    const rows = [...res.rows].sort((a, b) => b.annualKwh - a.annualKwh);
    tbody.innerHTML = '';
    for (const r of rows) {
      const tr = document.createElement('tr');
      const key = rowKey(r);
      tr.dataset.id = key;
      const badge = key === wk ? ' <span style="color:var(--color-brass-300)">✓ Recommandé</span>' : '';
      tr.innerHTML =
        `<td>${r.label}${badge}</td>` +
        `<td class="num">${fmt(r.placedCount)}</td>` +
        `<td class="num">${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })}</td>` +
        `<td class="num">${fmt(Math.round(r.annualKwh))}</td>` +
        `<td class="num">${Math.round(r.pctOfTarget)} %</td>` +
        `<td class="num">${fmtMad(r.savingsLow)} – ${fmtMad(r.savingsHigh)}</td>`;
      tr.addEventListener('click', () => {
        pitchedLocks.layout = r.layout;
        pitchedLocks.margin = r.margin;
        liveResolvePitched();
      });
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
    highlightRow(wk);
  }

  /** « Réinitialiser » (toit en pente) : relâche les verrous pose/marge → optimum global. */
  function resetPitchedLocks() {
    delete pitchedLocks.layout;
    delete pitchedLocks.margin;
    neededAuto = true;
    liveResolvePitched();
  }

  // V5 — rendement spécifique PVGIS (kWh/kWc/an) du plan en pente, pose 'building',
  // à kWc=1 (mis à l'échelle ensuite). Cache par (pente|face), repli table (null).
  async function pitchedSpecificYield(pitch: number, facing: number): Promise<number | null> {
    const key = pitchedKey(pitch, facing);
    if (pitchedYieldCache.has(key)) return pitchedYieldCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: centroid[1], lon: centroid[0], mountingplace: 'building', legs: [pitchedPlaneLeg(pitch, facing, 1)] }),
      });
      const data = await res.json();
      const v = res.ok && data.ok && typeof data.annualKwh === 'number' ? data.annualKwh : null;
      pitchedYieldCache.set(key, v);
      return v;
    } catch {
      pitchedYieldCache.set(key, null);
      return null;
    }
  }

  // Affine la production du toit en pente avec PVGIS (une seule requête, cachée).
  async function refinePitchedPvgis() {
    if (!pitchedRec) return;
    const p = pitchedRec.planes[0];
    if (!p || p.northFacing) return;
    const token = ++pitchedToken;
    const perKwc = await pitchedSpecificYield(p.pitchDeg, p.facingAzimuthDeg);
    if (token !== pitchedToken || perKwc == null) return;
    pitchedPvgisPerKwc = perKwc;
    // W35 — le cache PVGIS (pente, face) est rempli : re-résout l'optimiseur vivant.
    if (roofType === 'pitched') liveResolvePitched();
  }

  function pitchedRecompute() {
    if (!closed || vertices.length < 3) return;
    const ring: LngLat[] = [...vertices];
    const plane: RoofPlane = { ring, pitchDeg, facingAzimuthDeg, obstructions: obstructionRings() };
    pitchedRec = recommendPitched([plane], centroidLat, monthlyBill());
    pitchedPvgisPerKwc = null; // nouvelle config → chiffre PVGIS obsolète (repli table)
    if (neededAuto) {
      const n = neededPanelsForTarget(pitchedRec.targetAnnualKwh, centroidLat);
      neededPanels = n > 0 ? clampNeeded(n) : 0;
    }
    // W35 — l'optimiseur vivant en pente rend le gagnant + son comparatif (pose × marge).
    liveResolvePitched();
    setStatus('Mode pente : pose affleurante, inclinaison et azimut imposés par le toit.');
    void refinePitchedPvgis(); // production de vérité PVGIS (building) au (pente, face)
  }

  /** Recalcul/rendu selon le type de toit actif (plat = pipeline pro-5 inchangé). */
  function recalc() {
    if (roofType === 'pitched') pitchedRecompute();
    else recompute();
  }
  function renderActive() {
    if (roofType === 'pitched') liveResolvePitched();
    else renderSelection();
  }

  /** Axes que l'utilisateur a explicitement épinglés (le bouton Optimum les tient). */
  function currentPins(): FlatPins {
    const pins: FlatPins = {};
    if (pinned.has('family')) pins.family = sel.family;
    if (pinned.has('tilt') && sel.tilt !== 'reco') pins.tiltDeg = sel.tilt;
    if (pinned.has('orient') && sel.orient !== 'auto') pins.orientation = sel.orient;
    if (pinned.has('azimuth')) pins.azimuth = sel.azimuth;
    if (pinned.has('margin')) pins.margin = sel.margin;
    return pins;
  }

  /** Bouton « Optimum » : cale tout sur le VRAI meilleur compromis (recherche
   *  pleine). Avec une épingle, on la tient et on re-résout le reste. */
  function applyOptimum() {
    if (!closed || vertices.length < 3) return;
    if (roofType === 'pitched') {
      pitchedRecompute();
      if (optimumNoteEl) optimumNoteEl.textContent = 'Optimum (pente) : pose affleurante dimensionnée au besoin sur ce pan (inclinaison/azimut imposés).';
      return;
    }
    const ring: LngLat[] = [...vertices];
    const pins = currentPins();
    const re = reoptimize(pins, ring, centroidLat, monthlyBill(), obstructionRings());
    const w = re.winner;
    useRecommended = false;
    sel = { family: w.family, tilt: w.tiltDeg, orient: w.orientation, azimuth: w.azimuth, margin: w.margin };
    syncChips();
    recompute(); // la marge/l'azimut peuvent changer la surface utile + rafraîchit les badges
    if (optimumNoteEl) {
      optimumNoteEl.textContent = Object.keys(pins).length > 0
        ? 'Optimum : votre épingle est tenue, tout le reste a été re-résolu autour.'
        : 'Optimum : meilleur compromis sur tout l’espace (inclinaison, azimut, calepinage, marge), plafonné au besoin.';
    }
  }

  function syncRoofTypeChips() {
    document.querySelectorAll<HTMLButtonElement>('[data-rooftype]').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.rooftype === roofType));
    });
  }
  function setRoofType(t: RoofType) {
    if (roofType === t) return;
    roofType = t;
    // W35 — on masque SEULEMENT les contrôles propres au plat (#rp9-flat-only) ; la pose
    // et la marge (axes libres en pente) restent visibles. Le bloc pente apparaît en pente.
    if (flatOnlyEl) flatOnlyEl.hidden = t !== 'flat';
    if (pitchedControlsEl) pitchedControlsEl.hidden = t !== 'pitched';
    if (t === 'pitched' && azimuthGroup) azimuthGroup.hidden = true;
    // V6 : la carte « Optimum calculé » est propre au toit plat ; recompute la rouvre
    // en mode plat. Le tableau comparatif est repeuplé selon le mode (plat ou pente).
    if (optimumCard && t !== 'flat') optimumCard.hidden = true;
    syncRoofTypeChips();
    if (optimumNoteEl) {
      optimumNoteEl.textContent = t === 'pitched'
        ? 'Optimum vivant (pente) : pose et marge calées au mieux ; inclinaison et azimut imposés par le toit.'
        : 'Tout est calé sur le meilleur compromis. Verrouillez une option et le reste se re-résout en direct.';
    }
    if (closed) recalc();
  }

  // — Recalcul complet (cerveau) —
  function recompute() {
    if (!closed || vertices.length < 3) return;
    const ring: LngLat[] = [...vertices];
    const bill = monthlyBill();
    // W1 : la marge de rive courante (toggle) entre dans le cerveau, et pro-5 ACTIVE
    // le balayage d'azimut aligné-toit (opt-in ; pro-4 ne l'active pas → inchangé).
    rec = recommend(ring, centroidLat, bill, obstructionRings(), { setbackM: setbackOf(), enableRoofAligned: true });
    pvgisPerKwc = null;
    // W1 : (ré)affiche/masque le groupe AZIMUT selon que le toit est tourné, et
    // repose les badges « Recommandé » de chaque groupe depuis rec.recommendedOptions.
    syncAzimuthGroupVisibility();
    updateRecoBadges();
    // Plafond « besoin » : redérivé de la facture tant que l'utilisateur ne l'a pas
    // figé. INDÉPENDANT des obstacles — eux ne changent que « ce qui tient », pas le
    // besoin énergétique — donc une édition d'obstacle ne réécrit jamais ce nombre.
    if (neededAuto) {
      const n = neededPanelsForTarget(rec.targetAnnualKwh, centroidLat);
      neededPanels = n > 0 ? clampNeeded(n) : 0;
    }
    // FIX 2 (V6) — la MATRICE complète remplace les ~6 lignes : balayage estimé
    // instantané affiché, puis affiné PVGIS au GPS exact ci-dessous.
    recomputeMatrix();
    renderSelection();
    if (rec.recommended.count === 0) {
      setStatus('Surface trop petite pour une rangée — élargissez le tracé.');
    } else if (rec.roofLimited) {
      setStatus('Calcul prêt. Ce toit ne couvre pas toute la facture : l’Est-Ouest maximise ce qui est possible.');
    } else {
      setStatus('Calcul prêt. Comparez les configurations, faites pivoter la 3D, puis recevez l’étude.');
    }
    // W34 — l'affinage PVGIS passe par la matrice (computeMatrixPvgis remplit le cache
    // partagé v4YieldCache, puis re-résout le solveur vivant) : pas de fetch séparé.
    // V6 — la matrice complète + l'optimum « calculé » notés sur le rendement PVGIS
    // au GPS exact (sa propre ligne, badge « Recommandé »).
    if (rec.recommended.count > 0) void computeMatrixPvgis();
  }

  // W1 — Jambes PVGIS pour une famille/azimut donné. Sud = une jambe (aspect =
  // azimut−180). Est-Ouest = deux jambes, base = azimut−90, ∓90.
  function legsFor(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, kwc: number) {
    if (family === 'eastwest') {
      const base = azimuthDeg - 90;
      return [
        { kwc: kwc / 2, tiltDeg, aspect: base - 90 },
        { kwc: kwc / 2, tiltDeg, aspect: base + 90 },
      ];
    }
    return [{ kwc, tiltDeg, aspect: azimuthDeg - 180 }];
  }

  /**
   * W1 — Production PVGIS live (kWh) pour une config, avec CACHE partagé entre TOUS
   * les réglages : une même config (lat,lon|famille|tilt|azimut) n'est jamais
   * re-demandée. PVGIS injoignable/null → on mémorise null (repli table côté
   * appelant) sans erreur visible. On ne requête QUE les configs réellement
   * affichées (recommandée + sélection visible), jamais tout l'espace théorique.
   */
  async function fetchPvgis(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, kwc: number): Promise<number | null> {
    if (kwc <= 0) return null;
    const key = pvgisKey(family, tiltDeg, azimuthDeg);
    if (pvgisCache.has(key)) return pvgisCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: centroid[1], lon: centroid[0], legs: legsFor(family, tiltDeg, azimuthDeg, kwc) }),
      });
      const data = await res.json();
      if (res.ok && data.ok && typeof data.annualKwh === 'number') {
        pvgisCache.set(key, data.annualKwh);
        return data.annualKwh;
      }
      pvgisCache.set(key, null); // PVGIS a répondu « estimate » → repli table mémorisé
      return null;
    } catch {
      // Pas d'erreur visible : la table committée a déjà fourni un chiffre.
      pvgisCache.set(key, null);
      return null;
    }
  }

  async function refinePvgis() {
    if (!rec) return;
    const r = rec.recommended;
    const kwh = await fetchPvgis(r.family, r.tiltDeg, r.azimuthDeg, r.kwc);
    if (kwh != null && r.kwc > 0) {
      // Stocke le rendement (kWh/kWc) — réappliqué au nombre POSÉ, qui peut être
      // sous le besoin si le toit/les obstacles contraignent.
      pvgisPerKwc = kwh / r.kwc;
      if (useRecommended) renderSelection();
    }
  }

  // ── V4 — PVGIS SOURCE DE VÉRITÉ : optimum de grille fine au GPS exact ────────
  // Rendement spécifique (kWh/kWc/an) pour un (tilt, aspect) — kWc=1, pose 'free'
  // (toit plat racké). Mémorisé/réutilisé ; PVGIS null → repli table (null en cache).
  async function v4SpecificYield(tiltDeg: number, aspect: number): Promise<number | null> {
    const key = v4Key(tiltDeg, aspect);
    if (v4YieldCache.has(key)) return v4YieldCache.get(key) ?? null;
    try {
      const res = await fetch('/api/roof-yield', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat: centroid[1], lon: centroid[0], mountingplace: 'free', legs: [{ kwc: 1, tiltDeg, aspect }] }),
      });
      const data = await res.json();
      if (res.ok && data.ok && typeof data.annualKwh === 'number') {
        v4YieldCache.set(key, data.annualKwh);
        return data.annualKwh;
      }
      v4YieldCache.set(key, null);
      return null;
    } catch {
      v4YieldCache.set(key, null);
      return null;
    }
  }

  // V6 — la MATRICE complète notée sur le rendement PVGIS du GPS EXACT, en
  // COARSE-THEN-FINE pour rester rapide et dans les limites de débit PVGIS : le
  // rendement spécifique est interrogé UNE fois par (tilt, aspect), mis en cache et
  // réutilisé (cache partagé v4YieldCache). Phase 1 = grille grossière (tous aspects)
  // → trouve la base ; phase 2 = grille fine autour de l'aspect gagnant. Les cellules
  // non interrogées retombent gracieusement sur l'estimation maison (« estimé »).
  const buildMatrix = (ring: LngLat[], bill: number) => {
    const yieldFn = (tiltDeg: number, aspect: number): number | null => {
      const v = v4YieldCache.get(v4Key(tiltDeg, aspect));
      return v == null ? null : v;
    };
    matrixResult = fineGridMatrixV6(ring, centroidLat, bill, obstructionRings(), { yieldFn });
    paintComparison();
    renderMatrixOptimumCard();
    // W34 — le cache PVGIS vient d'être enrichi : re-résout le solveur vivant pour que
    // le gagnant affiché + les badges « Recommandé » suivent la production PVGIS exacte.
    if (roofType === 'flat') liveResolveFlat();
  };

  async function computeMatrixPvgis() {
    if (!closed || vertices.length < 3 || roofType !== 'flat') return;
    const token = ++matrixToken;
    const ring: LngLat[] = [...vertices];
    const bill = monthlyBill();
    const roofAz = roofDominantAzimuthDeg(ring);
    // Phase 1 — GROSSIÈRE : tous les aspects, inclinaisons grossières → la base.
    await Promise.all(pvgisCoarsePairs(centroidLat, roofAz).map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return; // un tracé/réglage plus récent a pris la main
    buildMatrix(ring, bill);
    // Phase 2 — FINE : on raffine la grille fine complète autour de l'aspect gagnant.
    const refine = pvgisRefinePairs(centroidLat, roofAz, matrixResult ? matrixResult.winner.aspect : 0);
    if (!refine.length) return;
    await Promise.all(refine.map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return;
    buildMatrix(ring, bill);
  }

  /** Carte « Optimum calculé » alimentée par le VRAI maximum de la matrice. */
  function renderMatrixOptimumCard() {
    if (!optimumCard || !matrixResult) return;
    const w = matrixResult.winner;
    optimumCard.hidden = false;
    if (optimumLabelEl) optimumLabelEl.textContent = matrixResult.optimumRow.label;
    if (optimumSourceEl) optimumSourceEl.textContent = matrixResult.yieldSource === 'pvgis' ? 'PVGIS · GPS exact' : 'estimé · table committée';
    if (optimumKwcEl) optimumKwcEl.textContent = w.kwc > 0 ? fmt(Math.round(w.kwc * 100) / 100) : '—';
    if (optimumPanelsEl) optimumPanelsEl.textContent = String(w.placedCount);
    if (optimumProdEl) optimumProdEl.textContent = w.annualKwh > 0 ? fmt(Math.round(w.annualKwh)) : '—';
    if (optimumCoverEl) optimumCoverEl.textContent = `${Math.round(w.pctOfTarget)} %`;
    if (optimumWhyEl) optimumWhyEl.textContent = matrixResult.optimumRow.reason;
  }

  // Applique l'optimum RÉEL de la matrice (PVGIS) : rend EXACTEMENT le gagnant (azimut
  // span quelconque géré), puis note la raison.
  function applyMatrixOptimum() {
    if (!matrixResult) { applyOptimum(); return; }
    renderMatrixRow(matrixResult.winner);
    if (optimumNoteEl) optimumNoteEl.textContent = 'Optimum (PVGIS) : le vrai maximum de la matrice au GPS exact, plafonné au besoin.';
  }

  // Le bouton « ⚡ Optimum » : en toit plat sans épingle, on cale sur l'optimum RÉEL de
  // la matrice (PVGIS) ; avec une épingle (ou en mode pente), on garde la
  // ré-optimisation contrainte V3 qui tient l'épingle.
  function applyOptimumSmart() {
    if (roofType === 'flat' && matrixResult && Object.keys(currentPins()).length === 0) {
      applyMatrixOptimum();
      return;
    }
    applyOptimum();
  }

  function prefillLead(d: CardData) {
    // Pré-remplit le diagnostic enrichi — RÉUTILISE le même formulaire et toute sa
    // plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) : on n'écrit que
    // dans ses champs, on ne poste AUCUN lead ici.
    const area = $<HTMLInputElement>('lf-area');
    const orient = $<HTMLSelectElement>('lf-orient');
    const kwc = $<HTMLInputElement>('lf-kwc-est');
    if (area) area.value = String(Math.round(geodesicArea()));
    if (orient) orient.value = 'sud'; // Sud et Est-Ouest se rapportent tous deux au sud
    if (kwc) kwc.value = String(Math.round(d.kwc * 100) / 100);
    const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
    if (details) details.open = true;
    document.getElementById('simulateur')?.scrollIntoView({ behavior: opts.reducedMotion ? 'auto' : 'smooth', block: 'start' });
  }

  function geodesicArea(): number {
    // surface tracée (m²) pour pré-remplir le champ « surface toit »
    const ring = vertices;
    if (ring.length < 3) return 0;
    let total = 0;
    for (let i = 0; i < ring.length; i++) {
      const [lng1, lat1] = ring[i];
      const [lng2, lat2] = ring[(i + 1) % ring.length];
      total += (lng2 - lng1) * DEG2RAD * (2 + Math.sin(lat1 * DEG2RAD) + Math.sin(lat2 * DEG2RAD));
    }
    return Math.abs((total * WGS84_RADIUS * WGS84_RADIUS) / 2);
  }

  // — Fermeture du tracé —
  function close() {
    if (closed || vertices.length < 3) return;
    // W76 — refuse de fermer un contour qui se croise (nœud papillon) : l'aire géodésique
    // serait fausse et le calepinage remplirait une forme aberrante. On reste à tracer.
    if (!isSimplePolygon(vertices)) {
      setStatus('Votre tracé se croise — corrigez le contour (« Effacer » puis re-tracez) avant de fermer.');
      return;
    }
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    let lng = 0;
    let lat = 0;
    for (const [x, y] of vertices) {
      lng += x;
      lat += y;
    }
    centroid = [lng / vertices.length, lat / vertices.length];
    centroidLat = centroid[1];
    pvgisCache.clear(); // W1 : nouvelle localisation → clés PVGIS obsolètes
    v4YieldCache.clear(); // V4 : nouvelle localisation → rendements PVGIS obsolètes
    matrixResult = null;
    pitchedYieldCache.clear(); // V5 : nouvelle localisation → rendement pente obsolète
    pitchedPvgisPerKwc = null;
    prodPlaneKey = ''; // W50 : nouvelle localisation → fenêtre de production à re-charger
    prodPerKwc = null;
    if (optimumCard) optimumCard.hidden = true;
    srcOf('rp9-line')?.setData(empty as never);
    srcOf('rp9-pts')?.setData(empty as never);
    if (configPanel) configPanel.hidden = false;
    go3DView();
    syncRoofTypeChips();
    recalc();
  }

  function go3DView() {
    const target = { center: centroid, pitch: PITCH_VIEW } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 1100, essential: true });
  }

  /** Remet l'ÉDITEUR (géométrie + sous-panneaux) à l'état « prêt à tracer », SANS toucher
   *  la facture ni la liste des zones. Partagé par « Effacer » (reset complet) et
   *  « + Ajouter une zone » (nouveau tracé vierge sur la même facture). */
  function clearEditorState() {
    vertices = [];
    closed = false;
    obstacles = [];
    selectedObsId = null;
    setObstacleMode(false);
    drawing = false;
    drawStart = null;
    moveObs = null;
    rec = null;
    pvgisPerKwc = null;
    pvgisCache.clear();
    v4YieldCache.clear();
    matrixResult = null;
    pitchedYieldCache.clear();
    pitchedPvgisPerKwc = null;
    if (optimumCard) optimumCard.hidden = true;
    roofTex?.dispose();
    roofTex = null;
    roofTexKey = '';
    deckMaterial = null;
    neededPanels = 0;
    neededAuto = true;
    if (needInputEl) {
      needInputEl.value = '—';
      needInputEl.disabled = true;
    }
    if (needMinusEl) needMinusEl.disabled = true;
    if (needPlusEl) needPlusEl.disabled = true;
    if (needNoteEl) needNoteEl.textContent = '';
    useRecommended = true;
    sel = { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' };
    srcOf('rp9-line')?.setData(empty as never);
    srcOf('rp9-pts')?.setData(empty as never);
    clearPreview();
    redrawObstacles();
    syncObsEdit();
    disposeScene();
    modelMatrix = null;
    map.triggerRepaint();
    if (configPanel) configPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    updateAreaReadout();
    const wrap = $('rp9-compare-wrap');
    if (wrap) wrap.hidden = true;
    $('rp9-results')?.classList.remove('rp9-results--ready');
    const cta = $<HTMLButtonElement>('rp9-cta');
    if (cta) cta.hidden = true;
    // W50 — réinitialise la fenêtre de production (cache client purgé, scope par défaut).
    prodScope = 'year';
    prodMonth = 0;
    prodDay = null;
    prodPerKwc = null;
    prodScaled = null;
    prodSpecificDate = null;
    prodPanels = 0;
    prodPlaneKey = '';
    if (prodWindowEl) prodWindowEl.hidden = true;
    // W68 — réinitialise l'affinage de consommation (courbe + appareils).
    consMode = false;
    consCurve = emptyCurve();
    consHandEdited = false;
    consAppliances = [];
    consDailyTarget = 0;
    if (consToggleEl) consToggleEl.setAttribute('aria-expanded', 'false');
    if (consPanelEl) consPanelEl.hidden = true;
    if (consWindowEl) consWindowEl.hidden = true;
    // W69 — réinitialise la disposition personnalisée.
    layoutMode = false;
    layoutState = null;
    layoutPlan = null;
    layoutOptimalCount = 0;
    layoutSel = null;
    if (layoutToggleEl) layoutToggleEl.setAttribute('aria-pressed', 'false');
    if (layoutPanelEl) layoutPanelEl.hidden = true;
    if (layoutWindowEl) layoutWindowEl.hidden = true;
    if (layoutNoteEl) layoutNoteEl.textContent = '';
    syncChips();
    const target = { pitch: 0, bearing: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 600 });
    updateCompass();
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  /** « Effacer » (reset complet) : vide l'éditeur ET ramène la liste des zones à UNE
   *  seule zone vide active. */
  function reset() {
    clearEditorState();
    areas.length = 0;
    areaCounter = 0;
    const fresh = newAreaRecord();
    areas.push(fresh);
    activeAreaId = fresh.id;
    if (areasWindowEl) areasWindowEl.hidden = true;
    renderAreasPanel();
  }

  // ═══════════ « PLUSIEURS ZONES » — ajouter / sélectionner / supprimer ═══════════

  /** Charge l'enregistrement d'une zone dans l'état d'édition (géométrie + réglages),
   *  recompute le centroïde, et la rend en 3D via le pipeline mono-zone. */
  function loadArea(a: AreaRecord) {
    vertices = [...a.vertices];
    obstacles = a.obstacles.map((o) => ({ ...o }));
    roofType = a.roofType;
    pitchDeg = a.pitchDeg;
    facingAzimuthDeg = a.facingAzimuthDeg;
    neededPanels = a.neededPanels;
    neededAuto = a.neededAuto;
    closed = a.vertices.length >= 3;
    selectedObsId = null;
    // Recentre sur la zone chargée (mêmes caches purgés qu'à la fermeture du tracé).
    if (vertices.length >= 3) {
      let lng = 0;
      let lat = 0;
      for (const [x, y] of vertices) {
        lng += x;
        lat += y;
      }
      centroid = [lng / vertices.length, lat / vertices.length];
      centroidLat = centroid[1];
    }
    pvgisCache.clear();
    v4YieldCache.clear();
    matrixResult = null;
    pitchedYieldCache.clear();
    pitchedPvgisPerKwc = null;
    prodPlaneKey = '';
    prodPerKwc = null;
    // Sous-panneaux liés à la zone active : on repart propre pour la zone chargée.
    layoutMode = false;
    layoutState = null;
    layoutPlan = null;
    layoutOptimalCount = 0;
    layoutSel = null;
    if (layoutToggleEl) layoutToggleEl.setAttribute('aria-pressed', 'false');
    if (layoutPanelEl) layoutPanelEl.hidden = true;
    consMode = false;
    consHandEdited = false;
    if (consToggleEl) consToggleEl.setAttribute('aria-expanded', 'false');
    if (consPanelEl) consPanelEl.hidden = true;
    redrawTrace();
    redrawObstacles();
    syncObsEdit();
    syncRoofTypeChips();
    if (flatOnlyEl) flatOnlyEl.hidden = roofType !== 'flat';
    if (pitchedControlsEl) pitchedControlsEl.hidden = roofType !== 'pitched';
    if (configPanel) configPanel.hidden = !closed;
    updateAreaReadout();
    if (closed) {
      go3DView();
      recalc();
    } else {
      renderAreasPanel();
      setStatus('Zone vide sélectionnée — tracez son contour.');
    }
  }

  /** « + Ajouter une zone » : fige la zone active (géométrie + résultat), crée une
   *  NOUVELLE zone vide, l'active et vide l'éditeur pour un tracé vierge (facture +
   *  liste des zones conservées). N'agit que si la zone active est fermée. */
  function addArea() {
    if (!closed || vertices.length < 3) return;
    snapshotActiveAreaGeometry();
    snapshotActiveAreaResult();
    const fresh = newAreaRecord();
    areas.push(fresh);
    activeAreaId = fresh.id;
    clearEditorState();
    renderAreasPanel();
    setStatus(`${fresh.label} — tracez le contour de cette nouvelle zone (double-cliquez pour fermer).`);
  }

  /** « Voir » une zone : fige la zone active d'abord, puis charge la zone choisie. */
  function selectArea(id: string) {
    if (id === activeAreaId) return;
    const target = areas.find((a) => a.id === id);
    if (!target) return;
    snapshotActiveAreaGeometry();
    snapshotActiveAreaResult();
    activeAreaId = id;
    loadArea(target);
  }

  /** Supprime une zone. Si c'était l'active, on bascule sur la première restante (chargée),
   *  ou — s'il n'en reste aucune — on fait un reset complet (jamais zéro zone). */
  function deleteArea(id: string) {
    const idx = areas.findIndex((a) => a.id === id);
    if (idx < 0) return;
    const wasActive = id === activeAreaId;
    areas.splice(idx, 1);
    if (areas.length === 0) {
      reset();
      return;
    }
    if (wasActive) {
      const next = areas[0];
      activeAreaId = next.id;
      loadArea(next);
    } else {
      renderAreasPanel();
    }
  }

  // — Mode obstacle : on désactive le pan pour glisser-dessiner le rectangle —
  function setObstacleMode(on: boolean) {
    obstacleMode = on;
    obstacleBtn?.setAttribute('aria-pressed', String(on));
    if (on) {
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
    } else {
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      drawing = false;
      drawStart = null;
      clearPreview();
    }
  }

  let lastDraw: LngLat | null = null;
  function beginDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!obstacleMode || !closed) return;
    drawStart = { lngLat, point };
    drawing = true;
    lastDraw = lngLat;
  }
  function moveDraw(lngLat: LngLat) {
    if (!drawing || !drawStart) return;
    lastDraw = lngLat;
    setPreviewRect(drawStart.lngLat, lngLat);
  }
  function endDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!drawing || !drawStart) return;
    drawing = false;
    clearPreview();
    const start = drawStart;
    drawStart = null;
    suppressClick = true;
    const end = lngLat ?? lastDraw ?? start.lngLat;
    const dx = Math.abs(point.x - start.point.x);
    const dy = Math.abs(point.y - start.point.y);
    const id = `obs-${++obsCounter}`;
    if (dx < OBSTACLE_TAP_PX && dy < OBSTACLE_TAP_PX) {
      // simple tap : sélectionne un obstacle existant, sinon en crée un par défaut
      const hit = obstacleAtPoint(point);
      if (hit) {
        setObstacleMode(false);
        selectObstacle(hit);
        setStatus('Obstacle sélectionné — ajustez sa taille au doigt ou au clavier.');
        return;
      }
      addObstacle(defaultObstacle(id, end));
    } else {
      addObstacle(obstacleFromDrag(id, start.lngLat, end));
    }
    setObstacleMode(false);
    setStatus('Obstacle ajouté — le calepinage l’évite. Touchez-le pour l’ajuster, ou ajoutez-en un autre.');
  }

  // — Déplacement d'un obstacle (glissé), Change C —
  /** Tente de saisir un obstacle sous le pointeur pour le déplacer. Renvoie true si
   *  un glissé de déplacement démarre (→ on neutralise le pan de la carte). */
  function tryBeginMove(lngLat: LngLat, point: maplibregl.Point): boolean {
    // W69 — en mode « Personnaliser la disposition », le glissé sert à déplacer un
    // PANNEAU (handlers dédiés plus bas). On ne saisit donc PAS un obstacle ici, sinon
    // les deux drags démarrent ensemble et relâcher déclenche un recalc qui efface la
    // disposition personnalisée.
    if (!closed || obstacleMode || layoutMode) return false;
    const hit = obstacleAtPoint(point);
    if (!hit) return false;
    const o = obstacles.find((x) => x.id === hit);
    if (!o) return false;
    selectObstacle(hit);
    moveObs = { id: hit, startLng: lngLat[0], startLat: lngLat[1], centerLng: o.centerLng, centerLat: o.centerLat, moved: false };
    map.dragPan.disable();
    return true;
  }
  function doMove(lngLat: LngLat) {
    if (!moveObs) return;
    const idx = obstacles.findIndex((x) => x.id === moveObs!.id);
    if (idx < 0) return;
    // Delta lng/lat : annule le parallaxe absolu de la vue inclinée.
    const centerLng = moveObs.centerLng + (lngLat[0] - moveObs.startLng);
    const centerLat = moveObs.centerLat + (lngLat[1] - moveObs.startLat);
    moveObs.moved = true;
    obstacles[idx] = { ...obstacles[idx], centerLng, centerLat };
    redrawObstacles();
    // Déplacement 3D EN DIRECT du seul mesh concerné (pas de re-pavage par image).
    const mesh = obstacleMeshes.get(moveObs.id);
    if (mesh) {
      const cosLat = Math.cos(sceneOrigin[1] * DEG2RAD);
      mesh.position.x = (centerLng - sceneOrigin[0]) * DEG2M * cosLat;
      mesh.position.y = (centerLat - sceneOrigin[1]) * DEG2M;
      map.triggerRepaint();
    }
  }
  function endMove() {
    if (!moveObs) return;
    const moved = moveObs.moved;
    moveObs = null;
    map.dragPan.enable();
    suppressClick = true; // évite la désélection au click de synthèse
    // Re-pavage + recalcul seulement si l'obstacle a réellement bougé.
    if (moved) recalc();
  }

  // — Interactions carte —
  map.on('mousedown', (e) => {
    suppressClick = false;
    if (obstacleMode) {
      beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('mousemove', (e) => {
    if (drawing) moveDraw([e.lngLat.lng, e.lngLat.lat]);
    else if (moveObs) doMove([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mouseup', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
    else if (moveObs) endMove();
  });
  map.on('touchstart', (e) => {
    suppressClick = false;
    if (obstacleMode) {
      beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    if (!e.points || e.points.length === 1) tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('touchmove', (e) => {
    if (drawing) {
      e.preventDefault();
      moveDraw([e.lngLat.lng, e.lngLat.lat]);
    } else if (moveObs) {
      e.preventDefault();
      doMove([e.lngLat.lng, e.lngLat.lat]);
    }
  });
  map.on('touchend', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
    else if (moveObs) endMove();
  });

  map.on('click', (e) => {
    if (suppressClick) {
      suppressClick = false;
      return;
    }
    if (obstacleMode) return; // le glissé gère le dessin
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
    if (closed) {
      // sélection/désélection d'un obstacle existant
      selectObstacle(obstacleAtPoint(e.point));
      return;
    }
    if (clickTimer) return;
    clickTimer = setTimeout(() => {
      clickTimer = null;
      addVertex(lngLat);
    }, 240);
  });
  map.on('dblclick', (e) => {
    e.preventDefault();
    if (clickTimer) {
      clearTimeout(clickTimer);
      clickTimer = null;
    }
    close();
  });

  finishBtn?.addEventListener('click', close);
  clearBtn?.addEventListener('click', reset);

  // — « Plusieurs zones » : ajouter une zone + sélection/suppression dans la liste —
  addAreaBtn?.addEventListener('click', addArea);
  areasListEl?.addEventListener('click', (e) => {
    const t = e.target as HTMLElement;
    const sel = t.closest<HTMLElement>('[data-area-select]');
    const del = t.closest<HTMLElement>('[data-area-del]');
    if (sel?.dataset.areaSelect) selectArea(sel.dataset.areaSelect);
    else if (del?.dataset.areaDel) deleteArea(del.dataset.areaDel);
  });

  // — Facture —
  function updateBillKwh() {
    const kwh = billToAnnualKwh(monthlyBill());
    if (billKwhEl) billKwhEl.textContent = kwh > 0 ? `${fmt(Math.round(kwh))} kWh` : '—';
  }
  // Le recalcul complet (balayage dense fineGridMatrixV6 + rafale de requêtes PVGIS)
  // est LOURD : le lancer à CHAQUE frappe figeait la page pendant qu'on tape la facture.
  // On débounce donc le recalcul (la conversion kWh, légère, reste instantanée).
  let billTimer: ReturnType<typeof setTimeout> | null = null;
  billEl?.addEventListener('input', () => {
    updateBillKwh();
    // Changer la facture = nouveau besoin : on relâche le réglage manuel éventuel.
    neededAuto = true;
    // W68 — un nouveau socle de facture recompose la courbe de conso (override repris).
    consHandEdited = false;
    if (!closed) return;
    if (billTimer != null) clearTimeout(billTimer);
    billTimer = setTimeout(() => {
      billTimer = null;
      recalc();
    }, 320);
  });
  updateBillKwh();

  // — Plafond « panneaux nécessaires » : +/− et saisie directe (Change A) —
  function setNeeded(n: number) {
    neededPanels = clampNeeded(n);
    neededAuto = false; // figé sur le choix de l'utilisateur jusqu'au prochain changement de facture/tracé
    renderActive();
  }
  needMinusEl?.addEventListener('click', () => {
    if (neededPanels > 0) setNeeded(neededPanels - 1);
  });
  needPlusEl?.addEventListener('click', () => setNeeded(neededPanels + 1));
  needInputEl?.addEventListener('input', () => {
    const v = parseInt((needInputEl.value || '').replace(/\D/g, ''), 10);
    if (Number.isFinite(v) && v > 0) setNeeded(v);
  });
  needInputEl?.addEventListener('blur', () => {
    if (needInputEl) needInputEl.value = neededPanels > 0 ? fmt(neededPanels) : '—';
  });

  // ═══════════ W68 — câblage « Affiner ma consommation » ═══════════
  // Remplissage des selects (appareils, presets BTU, presets chargeur VE).
  function populateConsSelects() {
    if (applKindEl && applKindEl.options.length === 0) {
      for (const t of APPLIANCE_TYPICALS) {
        const o = document.createElement('option');
        o.value = t.kind;
        o.textContent = t.label;
        applKindEl.appendChild(o);
      }
      const other = document.createElement('option');
      other.value = 'autre';
      other.textContent = 'Autre appareil…';
      applKindEl.appendChild(other);
    }
    if (acBtuEl && acBtuEl.options.length === 0) {
      for (const p of AC_BTU_PRESETS) {
        const o = document.createElement('option');
        o.value = String(p.btu);
        o.textContent = `${fmt(p.btu)} BTU (≈ ${p.cv} CV)`;
        acBtuEl.appendChild(o);
      }
    }
    if (evKwEl && evKwEl.options.length === 0) {
      for (const kw of EV_CHARGER_KW_PRESETS) {
        const o = document.createElement('option');
        o.value = String(kw);
        o.textContent = `${fmt1(kw)} kW`;
        evKwEl.appendChild(o);
      }
      evKwEl.value = '7.4';
    }
  }
  populateConsSelects();

  // Ouvrir / fermer le panneau d'affinage.
  consToggleEl?.addEventListener('click', () => {
    consMode = !consMode;
    consToggleEl.setAttribute('aria-expanded', String(consMode));
    if (consPanelEl) consPanelEl.hidden = !consMode;
    renderConsumption();
  });

  // Saisie / preset spécifiques selon l'appareil choisi.
  function syncApplianceInputs() {
    const kind = applKindEl?.value ?? '';
    if (applAcEl) applAcEl.hidden = kind !== 'clim';
    if (applEvEl) applEvEl.hidden = kind !== 'ev';
    if (kind === 'clim') refreshAcWatts();
  }
  applKindEl?.addEventListener('change', syncApplianceInputs);
  syncApplianceInputs();

  function readNum(el: HTMLInputElement | null, fallback: number): number {
    const v = parseFloat((el?.value ?? '').replace(',', '.'));
    return Number.isFinite(v) && v > 0 ? v : fallback;
  }

  function refreshAcWatts() {
    const btu = readNum(acBtuEl as unknown as HTMLInputElement, 9000);
    const eer = readNum(acEerEl, AC_EER_DEFAULT_NON_INVERTER);
    const hours = readNum(acHoursEl, 6);
    const watts = acWattsFromBtu(btu, eer);
    const kwh = kwhFromWattsHours(watts, hours);
    if (acWattsEl) acWattsEl.textContent = `≈ ${fmt(Math.round(watts))} W · ${fmt1(kwh)} kWh/j`;
  }
  acBtuEl?.addEventListener('change', refreshAcWatts);
  acEerEl?.addEventListener('input', refreshAcWatts);
  acHoursEl?.addEventListener('input', refreshAcWatts);

  // Ajouter un appareil → recompose la courbe et recompute tout.
  applAddEl?.addEventListener('click', () => {
    const kind = applKindEl?.value ?? '';
    let appliance: Appliance | null = null;
    if (kind === 'clim') {
      const btu = readNum(acBtuEl as unknown as HTMLInputElement, 9000);
      const eer = readNum(acEerEl, AC_EER_DEFAULT_NON_INVERTER);
      const hours = readNum(acHoursEl, 6);
      const watts = acWattsFromBtu(btu, eer);
      appliance = { kind: 'clim', label: `Climatisation ${fmt(btu)} BTU`, dailyKwh: kwhFromWattsHours(watts, hours), startHour: 13, endHour: 23, billing: 'onTop' };
    } else if (kind === 'ev') {
      const km = parseFloat((evKmEl?.value ?? '').replace(',', '.'));
      let kwh: number;
      if (Number.isFinite(km) && km > 0) {
        kwh = evKwhFromDistance(km, EV_KWH_PER_100KM_DEFAULT);
      } else {
        const kw = readNum(evKwEl as unknown as HTMLInputElement, 7.4);
        const hours = readNum(evHoursEl, 3);
        kwh = kwhFromWattsHours(kw * 1000, hours);
      }
      appliance = { kind: 'ev', label: 'Recharge voiture électrique', dailyKwh: kwh, startHour: 11, endHour: 15, billing: 'onTop' };
    } else if (kind === 'autre') {
      appliance = { kind: 'autre', label: `Autre appareil ${++consApplCounter}`, dailyKwh: 1, startHour: 18, endHour: 22, billing: 'onTop' };
    } else {
      const t = APPLIANCE_TYPICALS.find((x) => x.kind === kind);
      if (t) appliance = applianceFromTypical(t);
    }
    if (!appliance) return;
    consAppliances.push(appliance);
    consHandEdited = false; // un nouvel appareil recompose la courbe (l'override manuel est repris)
    if (applNoteEl) applNoteEl.textContent = `${appliance.label} ajouté (${fmt1(appliance.dailyKwh)} kWh/j).`;
    renderConsumption();
  });

  // Bascule « en plus » ↔ « déjà compris » et suppression d'un appareil (délégation).
  applListEl?.addEventListener('click', (e) => {
    const t = e.target as HTMLElement;
    const toggle = t.closest<HTMLElement>('[data-appl-toggle]');
    const del = t.closest<HTMLElement>('[data-appl-del]');
    if (toggle) {
      const i = parseInt(toggle.dataset.applToggle ?? '', 10);
      const a = consAppliances[i];
      if (a) {
        a.billing = a.billing === 'onTop' ? 'inBill' : 'onTop';
        consHandEdited = false;
        renderConsumption();
      }
    } else if (del) {
      const i = parseInt(del.dataset.applDel ?? '', 10);
      if (i >= 0 && i < consAppliances.length) {
        consAppliances.splice(i, 1);
        consHandEdited = false;
        renderConsumption();
      }
    }
  });

  // « Recaler sur ma facture » : remet le total de la courbe ÉDITÉE à la valeur facture.
  consRecalEl?.addEventListener('click', () => {
    consCurve = rescaleToDaily(consCurve, billDailyKwh());
    consHandEdited = true; // c'est un override manuel recalé
    renderConsumption();
  });

  // Saisie numérique des heures (délégation sur le conteneur).
  consInputsEl?.addEventListener('input', (e) => {
    const inp = e.target as HTMLInputElement;
    const h = parseInt(inp.dataset.hour ?? '', 10);
    if (!Number.isFinite(h) || h < 0 || h >= HOURS_PER_DAY) return;
    const v = parseFloat((inp.value || '').replace(',', '.'));
    consCurve[h] = Number.isFinite(v) && v >= 0 ? v : 0;
    consHandEdited = true;
    // On ne re-rend pas la saisie (curseur), seulement le reste de la synthèse.
    renderConsGraph();
    renderConsumptionSummaryOnly();
  });

  // Glissé d'une barre du graphe de conso (pointer) — fallback tactile + tap.
  let consDragHour: number | null = null;
  function hourFromEvent(target: EventTarget | null): number | null {
    const rect = (target as HTMLElement | null)?.closest<HTMLElement>('[data-hour]');
    if (!rect) return null;
    const h = parseInt(rect.dataset.hour ?? '', 10);
    return Number.isFinite(h) ? h : null;
  }
  function valueFromPointer(clientY: number): number {
    if (!consGraphEl) return 0;
    const box = consGraphEl.getBoundingClientRect();
    const H = 160;
    const padTop = 8;
    const padBottom = 16;
    const plotH = H - padTop - padBottom;
    // Position relative dans le SVG (viewBox 0..160 en Y).
    const yViewBox = ((clientY - box.top) / box.height) * H;
    const frac = Math.max(0, Math.min(1, (H - padBottom - yViewBox) / plotH));
    const prod = productionHourly();
    const maxC = consCurve.reduce((m, v) => Math.max(m, v), 0);
    const maxP = prod.reduce((m, v) => Math.max(m, v), 0);
    // Même plancher d'échelle que renderConsGraph (1e-6) : sinon le glissé et le dessin
    // des barres utilisent deux échelles différentes et la barre saisie ne suit pas le doigt.
    const max = Math.max(maxC, maxP, 1e-6);
    return frac * max;
  }
  consGraphEl?.addEventListener('pointerdown', (e) => {
    const h = hourFromEvent(e.target);
    if (h == null) return;
    consDragHour = h;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    consCurve[h] = valueFromPointer(e.clientY);
    consHandEdited = true;
    renderConsGraph();
    renderConsumptionSummaryOnly();
    e.preventDefault();
  });
  consGraphEl?.addEventListener('pointermove', (e) => {
    if (consDragHour == null) return;
    consCurve[consDragHour] = valueFromPointer(e.clientY);
    renderConsGraph();
    renderConsumptionSummaryOnly();
  });
  const endConsDrag = () => {
    if (consDragHour == null) return;
    consDragHour = null;
    renderConsInputs(); // resynchronise la saisie numérique après un glissé
    renderConsumption();
  };
  consGraphEl?.addEventListener('pointerup', endConsDrag);
  consGraphEl?.addEventListener('pointercancel', endConsDrag);
  // Clavier (mouvement réduit / accessibilité) : ↑/↓ ajuste la barre focalisée.
  consGraphEl?.addEventListener('keydown', (e) => {
    const h = hourFromEvent(e.target);
    if (h == null) return;
    const step = e.shiftKey ? 0.5 : 0.1;
    if (e.key === 'ArrowUp') consCurve[h] += step;
    else if (e.key === 'ArrowDown') consCurve[h] = Math.max(0, consCurve[h] - step);
    else return;
    consHandEdited = true;
    e.preventDefault();
    renderConsGraph();
    renderConsInputs();
    renderConsumptionSummaryOnly();
  });

  /** Recompute UNIQUEMENT la synthèse (total/autoconso/économies/batterie) sans
   *  retoucher la saisie ni la liste — pour ne pas casser le focus pendant l'édition. */
  function renderConsumptionSummaryOnly() {
    if (!prodScaled || !consMode) return;
    const prod = productionHourly();
    const dailyTotal = curveTotal(consCurve);
    const annualCons = annualConsumptionFromDaily(dailyTotal);
    const selfDaily = selfConsumptionDailyKwh(consCurve, prod);
    const savings = savingsFromHourly(consCurve, prod, annualCons, tariffForCity(undefined));
    const batt = batterySizing(consCurve, prod);
    if (consTotalEl) consTotalEl.textContent = `${fmt1(dailyTotal)} kWh`;
    if (consSelfEl) consSelfEl.textContent = `${fmt1(selfDaily)} kWh/j`;
    if (consSavingsEl) consSavingsEl.textContent = annualCons > 0 ? fmtSavings(savings.low, savings.high) + ' MAD' : '—';
    if (consBattEl) consBattEl.textContent = batt.batteries > 0 ? `${batt.batteries} × 6 kWh` : 'aucune';
  }

  // ═══════════ W69 — câblage « Personnaliser la disposition » ═══════════
  layoutToggleEl?.addEventListener('click', () => setLayoutMode(!layoutMode));

  // + / − : ajoute/retire un panneau (touch + mouvement réduit, sans glissé fin).
  layoutPlusEl?.addEventListener('click', () => {
    if (!layoutMode || !layoutState) return;
    const r = addFirstEmpty(layoutState, layoutCap());
    if (r.ok) {
      if (layoutNoteEl) layoutNoteEl.textContent = `Panneau ajouté — ${r.count} posés.`;
      renderCustomLayout();
      renderLayoutPanel();
    } else if (layoutNoteEl) {
      layoutNoteEl.textContent = 'Plus d’emplacement valide disponible sur ce toit.';
    }
  });
  layoutMinusEl?.addEventListener('click', () => {
    if (!layoutMode || !layoutState) return;
    const r = removeLast(layoutState);
    if (r.ok) {
      layoutSel = null;
      if (layoutNoteEl) {
        layoutNoteEl.textContent = neededPanels > 0 && r.count < neededPanels
          ? `Panneau retiré — ${r.count} posés. La disposition ne couvre plus tout le besoin (${fmt(neededPanels)}).`
          : `Panneau retiré — ${r.count} posés.`;
      }
      renderCustomLayout();
      renderLayoutPanel();
    }
  });
  // Réinitialiser la disposition optimale.
  layoutResetEl?.addEventListener('click', () => {
    if (!layoutState) return;
    resetToOptimal(layoutState, layoutOptimalCount);
    layoutSel = null;
    if (layoutNoteEl) layoutNoteEl.textContent = `Disposition optimale restaurée — ${occupiedCount(layoutState)} panneaux.`;
    renderCustomLayout();
    renderLayoutPanel();
  });

  // Plan tactile : tap-sélection d'un panneau → tap-cible d'un emplacement libre.
  layoutGridEl?.addEventListener('click', (e) => {
    if (!layoutMode || !layoutState) return;
    const btn = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]');
    if (!btn) return;
    const idx = parseInt(btn.dataset.cell ?? '', 10);
    if (!Number.isFinite(idx)) return;
    const occupied = layoutState.occupied.has(idx);
    if (layoutSel == null) {
      // 1er tap : sélectionne un panneau OCCUPÉ.
      if (occupied) {
        layoutSel = idx;
        if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau sélectionné — touchez un emplacement libre (vert) pour l’y déplacer.';
        renderLayoutPanel();
      } else if (layoutNoteEl) {
        layoutNoteEl.textContent = 'Touchez d’abord un panneau (bleu).';
      }
      return;
    }
    // 2e tap : déplace vers la cible si elle est VIDE valide ; sinon rejet (rouge).
    const res = movePanelToCell(layoutState, layoutSel, idx);
    if (res.ok) {
      if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
      layoutSel = null;
      renderCustomLayout();
    } else {
      if (layoutNoteEl) layoutNoteEl.textContent = occupied ? 'Emplacement déjà occupé — choisissez un emplacement libre.' : 'Cible invalide.';
      // re-sélection si on a touché un autre panneau occupé
      if (occupied) layoutSel = idx;
      else layoutSel = null;
    }
    renderLayoutPanel();
  });

  // Glissé sur la 3D : raycast (déprojection) → snap à la cellule VIDE valide la plus
  // proche, commit au relâchement. Désactive le pan de la carte pendant le glissé.
  let layoutDrag: { from: number; startPoint: maplibregl.Point; moved: boolean } | null = null;
  function layoutPanelAt(point: maplibregl.Point): number | null {
    if (!layoutState) return null;
    const enu = screenToENU(point);
    if (!enu) return null;
    // Cellule OCCUPÉE la plus proche du point (le panneau qu'on saisit).
    let best = -1;
    let bestD = Infinity;
    for (const c of layoutState.cells) {
      if (!layoutState.occupied.has(c.index)) continue;
      const d = (c.cx - enu.x) ** 2 + (c.cy - enu.y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = c.index;
      }
    }
    // Seuil de saisie : ~1 panneau de rayon (sinon on considère qu'on n'a rien saisi).
    const grabR2 = (PANEL2_LONG_M * 0.7) ** 2;
    return best >= 0 && bestD <= grabR2 ? best : null;
  }
  map.on('mousedown', (e) => {
    if (!layoutMode || obstacleMode || !layoutState) return;
    const from = layoutPanelAt(e.point);
    if (from == null) return;
    layoutDrag = { from, startPoint: e.point, moved: false };
    layoutSel = from;
    map.dragPan.disable();
    map.getCanvas().style.cursor = 'grabbing';
    renderLayoutPanel();
    e.preventDefault();
  });
  map.on('mousemove', (e) => {
    if (!layoutDrag || !layoutState) return;
    // Un déplacement réel ne commence qu'au-delà d'un seuil pixel : sinon un simple
    // clic sur un panneau le ferait sauter vers la cellule vide la plus proche.
    if (!layoutDrag.moved && (Math.abs(e.point.x - layoutDrag.startPoint.x) >= OBSTACLE_TAP_PX || Math.abs(e.point.y - layoutDrag.startPoint.y) >= OBSTACLE_TAP_PX)) {
      layoutDrag.moved = true;
    }
    if (!layoutDrag.moved) return;
    const enu = screenToENU(e.point);
    if (!enu) return;
    const target = nearestEmptyCell(layoutState, enu.x, enu.y);
    if (layoutNoteEl) layoutNoteEl.textContent = target >= 0 ? 'Relâchez sur un emplacement valide (vert).' : 'Aucun emplacement libre — il reviendra à sa place.';
  });
  map.on('mouseup', (e) => {
    if (!layoutDrag || !layoutState) {
      return;
    }
    // Clic sans glissé (pas de mouvement au-delà du seuil) → on NE déplace pas le
    // panneau : on l'a seulement sélectionné. Seul un vrai glissé le repositionne.
    const enu = layoutDrag.moved ? screenToENU(e.point) : null;
    if (enu) {
      const res = movePanelToPoint(layoutState, layoutDrag.from, enu.x, enu.y);
      if (res.ok && res.toIndex !== layoutDrag.from) {
        if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
        renderCustomLayout();
      } else if (layoutNoteEl) {
        layoutNoteEl.textContent = 'Aucun emplacement libre à cet endroit — le panneau est resté en place.';
      }
    }
    layoutDrag = null;
    layoutSel = null;
    map.dragPan.enable();
    map.getCanvas().style.cursor = '';
    renderLayoutPanel();
  });

  // — Chips de config —
  function syncChips() {
    document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
      const active = !useRecommended && b.dataset.family === sel.family;
      b.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll<HTMLButtonElement>('[data-tilt]').forEach((b) => {
      const val = b.dataset.tilt === 'reco' ? 'reco' : Number(b.dataset.tilt);
      const active = useRecommended ? b.dataset.tilt === 'reco' : sel.tilt === val;
      b.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
      // En mode recommandé, l'orientation panneau est « auto » par défaut.
      const effOrient = useRecommended ? 'auto' : sel.orient;
      b.setAttribute('aria-pressed', String(b.dataset.orient === effOrient));
    });
    // W1 : groupes AZIMUT et MARGE.
    document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.azimuth === sel.azimuth));
    });
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => {
      b.setAttribute('aria-pressed', String(b.dataset.margin === sel.margin));
    });
  }

  // W1 — Le groupe AZIMUT n'a de sens que sur un toit TOURNÉ. roofAlignedAzimuthDeg
  // ===180 ⇒ toit aligné ⇒ aucun choix réel ⇒ on cache tout le groupe (et on force
  // « sud »).
  function syncAzimuthGroupVisibility() {
    const rotated = !!rec && Math.abs(rec.roofAlignedAzimuthDeg - 180) > 1e-6;
    if (azimuthGroup) azimuthGroup.hidden = !rotated;
    if (!rotated && sel.azimuth !== 'south') {
      sel = { ...sel, azimuth: 'south' };
      syncChips();
    }
  }

  /**
   * W1 — Pose le marqueur « Recommandé » sur la bonne option de CHAQUE groupe,
   * calculé depuis rec.recommendedOptions (pur, indépendant de la sélection
   * courante) : l'utilisateur voit « vous avez choisi X mais Y est recommandé ».
   */
  function updateRecoBadges() {
    const show = (b: Element | null, on: boolean) => {
      const badge = b?.querySelector<HTMLElement>('.rp9-reco-badge');
      if (badge) badge.hidden = !on;
    };
    const ro = rec?.recommendedOptions;
    // Famille
    document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
      show(b, !!ro && b.dataset.family === ro.family);
    });
    // Inclinaison : badge le chip numérique == tilt arrondi, sinon le chip « reco ».
    const tiltRounded = ro ? Math.round(ro.tiltDeg) : null;
    const tiltChips = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-tilt]'));
    const numericMatch = tiltChips.find((b) => b.dataset.tilt !== 'reco' && Number(b.dataset.tilt) === tiltRounded);
    tiltChips.forEach((b) => {
      if (!ro) return show(b, false);
      if (numericMatch) show(b, b === numericMatch);
      else show(b, b.dataset.tilt === 'reco'); // aucun chip numérique ne colle → badge « Recommandé »
    });
    // Portrait / paysage (« Auto » jamais badgé)
    document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
      show(b, !!ro && b.dataset.orient !== 'auto' && b.dataset.orient === ro.panelOrientation);
    });
    // Azimut : 'south' si l'azimut recommandé est plein sud, sinon 'aligned'.
    const azReco = ro ? (ro.azimuthDeg === 180 ? 'south' : 'aligned') : null;
    document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => {
      show(b, b.dataset.azimuth === azReco);
    });
    // Marge ('keep' / 'remove')
    document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => {
      show(b, !!ro && b.dataset.margin === ro.margin);
    });
  }

  // W34 — Chaque groupe d'options est un AXE. Un clic VERROUILLE cet axe puis re-résout
  // en direct (renderSelection = liveResolveFlat). Re-cliquer la valeur déjà verrouillée
  // RELÂCHE cet axe (retour AUTO). Les verrous s'accumulent ; « Réinitialiser » relâche tout.
  document.querySelectorAll<HTMLButtonElement>('[data-family]').forEach((b) => {
    b.addEventListener('click', () => {
      const fam = b.dataset.family as ConfigFamily;
      // re-clic sur l'orientation déjà verrouillée (sans sous-verrou azimut) → AUTO
      if (pinned.has('family') && !pinned.has('azimuth') && sel.family === fam) {
        pinned.delete('family');
        renderSelection();
        return;
      }
      pinned.add('family');
      pinned.delete('azimuth'); // choisir une famille relâche le sous-verrou azimut
      sel = { ...sel, family: fam, azimuth: 'south' };
      renderSelection();
    });
  });
  document.querySelectorAll<HTMLButtonElement>('[data-tilt]').forEach((b) => {
    b.addEventListener('click', () => {
      if (b.dataset.tilt === 'reco') {
        pinned.delete('tilt'); // « Recommandé » = inclinaison AUTO (re-résolue)
        sel = { ...sel, tilt: 'reco' }; // W46 — efface la valeur numérique figée (sinon currentPins/affichage la garde)
      } else {
        const v = Number(b.dataset.tilt);
        if (pinned.has('tilt') && sel.tilt === v) pinned.delete('tilt'); // re-clic → AUTO
        else {
          pinned.add('tilt');
          sel = { ...sel, tilt: v };
        }
      }
      renderSelection();
    });
  });
  document.querySelectorAll<HTMLButtonElement>('[data-orient]').forEach((b) => {
    b.addEventListener('click', () => {
      const o = b.dataset.orient as OrientMode;
      if (roofType === 'pitched') {
        // W35 — pose = axe LIBRE en pente. « Auto » ou re-clic → AUTO ; sinon verrouille.
        if (o === 'auto' || pitchedLocks.layout === o) delete pitchedLocks.layout;
        else if (o === 'portrait' || o === 'landscape') pitchedLocks.layout = o;
        liveResolvePitched();
        return;
      }
      if (o === 'auto' || (pinned.has('orient') && sel.orient === o)) {
        pinned.delete('orient'); // « Auto » ou re-clic → pose AUTO
      } else {
        pinned.add('orient');
        sel = { ...sel, orient: o };
      }
      renderSelection();
    });
  });
  // W34 — Groupe AZIMUT (plein sud / aligné toit) = sous-axe de l'orientation.
  document.querySelectorAll<HTMLButtonElement>('[data-azimuth]').forEach((b) => {
    b.addEventListener('click', () => {
      const az = b.dataset.azimuth as AzimuthMode;
      if (pinned.has('azimuth') && sel.azimuth === az) {
        pinned.delete('azimuth'); // re-clic → AUTO
        if (az === 'aligned') pinned.delete('family');
      } else {
        pinned.add('azimuth');
        pinned.delete('family');
        sel = { ...sel, family: 'south', azimuth: az };
      }
      renderSelection();
    });
  });
  // W34 — Groupe MARGE (garder / retirer la rive). solveLive re-pave avec le bon
  // retrait → le solveur vivant suffit (la matrice balaie déjà les deux marges).
  document.querySelectorAll<HTMLButtonElement>('[data-margin]').forEach((b) => {
    b.addEventListener('click', () => {
      const m = b.dataset.margin as MarginMode;
      if (roofType === 'pitched') {
        // W35 — marge = axe LIBRE en pente. re-clic → AUTO ; sinon verrouille.
        if (pitchedLocks.margin === m) delete pitchedLocks.margin;
        else if (m === 'keep' || m === 'remove') pitchedLocks.margin = m;
        liveResolvePitched();
        return;
      }
      if (pinned.has('margin') && sel.margin === m) pinned.delete('margin'); // re-clic → AUTO
      else {
        pinned.add('margin');
        sel = { ...sel, margin: m };
      }
      renderSelection();
    });
  });

  // W34/W35 — Bouton « Réinitialiser » : relâche tous les verrous → optimum global vivant
  // (toit plat = W34 ; toit en pente = W35, pose/marge re-libérées).
  optimumBtn?.addEventListener('click', () => {
    if (!closed || vertices.length < 3) return;
    if (roofType === 'pitched') resetPitchedLocks();
    else resetFlatLocks();
  });
  optimumApplyBtn?.addEventListener('click', applyMatrixOptimum);
  // FIX 2 (V6) — tri (clic en-tête) + filtre par orientation de la MATRICE affichée.
  // Pur repaint : la matrice est déjà calculée, aucun re-balayage.
  document.querySelectorAll<HTMLElement>('[data-rp9-sort]').forEach((th) => {
    th.addEventListener('click', () => setMatrixSort(th.dataset.rp9Sort as MatrixSortKey));
  });
  $<HTMLSelectElement>('rp9-matrix-filter')?.addEventListener('change', (e) => {
    matrixFilter = (e.target as HTMLSelectElement).value;
    paintComparison();
  });

  // ── W50 — FENÊTRE DE PRODUCTION : toggle Année/Mois/Jour + cyclage mois/jour ──
  // Le toggle de scope : Année (12 mois) / Mois (jours du mois) / Jour (24 h). Changer de
  // scope ne refait PAS d'appel serveur si le plan est inchangé (les données sont déjà en
  // cache côté client) → cyclage instantané.
  if (prodScopeWrap) {
    prodScopeWrap.querySelectorAll<HTMLButtonElement>('[data-prod-scope]').forEach((b) => {
      b.addEventListener('click', () => {
        const s = b.dataset.prodScope as ProductionScope;
        if (s !== 'year' && s !== 'month' && s !== 'day') return;
        prodScope = s;
        // Entrer en Jour démarre sur le JOUR TYPE du mois (prodDay = null) ; on garde le
        // mois sélectionné. La date précise n'est demandée qu'à l'usage des flèches jour.
        if (s !== 'day') prodSpecificDate = null;
        syncProductionWindow();
      });
    });
  }
  const cycleProdMonth = (dir: number) => {
    prodMonth = cycleMonth(prodMonth, dir);
    prodDay = null; // changer de mois retombe sur le jour type du nouveau mois
    prodSpecificDate = null;
    syncProductionWindow();
  };
  prodMonthPrevEl?.addEventListener('click', () => cycleProdMonth(-1));
  prodMonthNextEl?.addEventListener('click', () => cycleProdMonth(1));
  const cycleProdDay = (dir: number) => {
    // Depuis le jour type (null), la première flèche pointe sur le 1er (dir>0) ou le
    // dernier (dir<0) jour du mois ; ensuite on cycle dans le mois.
    if (prodDay == null) prodDay = dir > 0 ? 1 : daysInMonth(prodMonth);
    else prodDay = cycleDay(prodMonth, prodDay, dir);
    syncProductionWindow();
  };
  prodDayPrevEl?.addEventListener('click', () => cycleProdDay(-1));
  prodDayNextEl?.addEventListener('click', () => cycleProdDay(1));
  prodDayResetEl?.addEventListener('click', () => {
    prodDay = null; // retour au jour TYPE du mois
    prodSpecificDate = null;
    syncProductionWindow();
  });

  // Les puces `[data-rooftype]` sont détenues par le contrôleur EAGER
  // (createRoofTypeSelect, dans le script de page) : il bascule `aria-pressed` sur
  // chaque puce dès le chargement — bien avant ce boot lourd — et nous notifie. On
  // honore d'abord un choix « pente » fait avant le boot, puis on s'abonne aux
  // changements pour appliquer les effets 3D + cerveau (setRoofType). Repli défensif
  // (aucun contrôleur fourni) : on auto-câble comme avant.
  if (opts.roofType) {
    setRoofType(opts.roofType.get());
    opts.roofType.subscribe(setRoofType);
  } else {
    document.querySelectorAll<HTMLButtonElement>('[data-rooftype]').forEach((b) => {
      b.addEventListener('click', () => setRoofType(b.dataset.rooftype as RoofType));
    });
  }
  const syncPitchChips = () => {
    document.querySelectorAll<HTMLButtonElement>('[data-pitch]').forEach((b) => {
      b.setAttribute('aria-pressed', String(Number(b.dataset.pitch) === Math.round(pitchDeg)));
    });
  };
  const syncFacingChips = () => {
    document.querySelectorAll<HTMLButtonElement>('[data-facing]').forEach((b) => {
      b.setAttribute('aria-pressed', String(Number(b.dataset.facing) === Math.round(facingAzimuthDeg)));
    });
  };
  document.querySelectorAll<HTMLButtonElement>('[data-pitch]').forEach((b) => {
    b.addEventListener('click', () => {
      pitchDeg = Number(b.dataset.pitch);
      if (pitchRangeEl) pitchRangeEl.value = String(Math.round(pitchDeg));
      if (pitchValueEl) pitchValueEl.textContent = `${Math.round(pitchDeg)}°`;
      syncPitchChips();
      if (roofType === 'pitched' && closed) pitchedRecompute();
    });
  });
  pitchRangeEl?.addEventListener('input', () => {
    const v = Number(pitchRangeEl.value);
    if (!Number.isFinite(v)) return;
    pitchDeg = v;
    if (pitchValueEl) pitchValueEl.textContent = `${Math.round(v)}°`;
    syncPitchChips();
    if (roofType === 'pitched' && closed) pitchedRecompute();
  });
  document.querySelectorAll<HTMLButtonElement>('[data-facing]').forEach((b) => {
    b.addEventListener('click', () => {
      facingAzimuthDeg = Number(b.dataset.facing);
      syncFacingChips();
      if (roofType === 'pitched' && closed) pitchedRecompute();
    });
  });

  // — V2 : curseur d'inclinaison (exploration fine) + bouton « reco » —
  if (tiltRangeEl) {
    tiltRangeEl.min = String(TILT_SWEEP_MIN);
    tiltRangeEl.max = '35';
    tiltRangeEl.step = '1';
    const onTilt = () => {
      const v = Number(tiltRangeEl.value);
      if (!Number.isFinite(v)) return;
      // W34 — le curseur VERROUILLE l'inclinaison ; les autres axes se re-résolvent
      // autour (via liveResolveFlat). PVGIS de l'inclinaison hors grille est affiné
      // en arrière-plan (ensurePvgisForLockedTilt).
      pinned.add('tilt');
      sel = { ...sel, tilt: v };
      if (tiltValueEl) tiltValueEl.textContent = `${Math.round(v)}°`;
      renderSelection();
    };
    tiltRangeEl.addEventListener('input', onTilt);
  }
  // W46 — bouton « Recommandé » de l'inclinaison = AFFORDANCE PAR AXE : il LIBÈRE LE
  // SEUL axe inclinaison (retour AUTO) en TENANT tous les autres verrous accumulés, puis
  // re-résout. Il NE doit PAS tout réinitialiser (« Réinitialiser » fait ça). Auparavant
  // un `pinned.clear()` ici effaçait silencieusement orientation/azimut/pose/marge déjà
  // verrouillés — l'optimiseur SEMBLAIT « cesser de tenir » les choix après quelques
  // verrous. On aligne ce bouton sur la puce data-tilt="reco" : delete('tilt') seulement.
  tiltRecoBtn?.addEventListener('click', () => {
    pinned.delete('tilt');
    sel = { ...sel, tilt: 'reco' };
    renderSelection();
  });

  obstacleBtn?.addEventListener('click', () => {
    if (!closed) {
      setStatus('Fermez d’abord le tracé du toit, puis ajoutez vos obstacles.');
      return;
    }
    setObstacleMode(!obstacleMode);
    selectObstacle(null);
    setStatus(
      obstacleMode
        ? 'Glissez sur le toit pour dessiner un obstacle (cheminée, climatiseur, lanterneau…).'
        : 'Ajout d’obstacle annulé.',
    );
  });
  obstacleClearBtn?.addEventListener('click', () => {
    if (!obstacles.length) return;
    obstacles = [];
    selectedObsId = null;
    setObstacleMode(false);
    redrawObstacles();
    syncObsEdit();
    if (closed) recalc();
    setStatus('Obstacles effacés — le calepinage reprend tout le toit.');
  });

  // — Édition de l'obstacle sélectionné (saisie exacte + boutons + / − + suppr.) —
  const parseNum = (s: string): number => parseFloat((s || '').replace(/\s/g, '').replace(',', '.'));
  obsLengthEl?.addEventListener('input', () => {
    if (!selectedObsId) return;
    const L = parseNum(obsLengthEl.value);
    if (!Number.isFinite(L)) return;
    updateSelected((o) => resizedObstacle(o, L, o.widthM));
  });
  obsWidthEl?.addEventListener('input', () => {
    if (!selectedObsId) return;
    const w = parseNum(obsWidthEl.value);
    if (!Number.isFinite(w)) return;
    updateSelected((o) => resizedObstacle(o, o.lengthM, w));
  });
  obsLengthEl?.addEventListener('blur', syncObsEdit);
  obsWidthEl?.addEventListener('blur', syncObsEdit);
  obsPlusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, OBSTACLE_STEP_FACTOR)));
  obsMinusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, 1 / OBSTACLE_STEP_FACTOR)));
  obsDeleteBtn?.addEventListener('click', deleteSelected);

  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (q) void geocode(q);
  });

  async function geocode(query: string) {
    setStatus('Recherche de l’adresse…');
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=1&language=fr`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('geocode');
      const data = (await res.json()) as { features?: Array<{ center?: [number, number] }> };
      const center = data.features?.[0]?.center;
      if (!center) {
        setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
        return;
      }
      const target = { center, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.');
    } catch {
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }
}
