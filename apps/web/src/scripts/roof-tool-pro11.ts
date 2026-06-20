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
  pitchedDeckZ,
  pvgisCoarsePairs,
  pvgisMatrixCandidatePairs,
  pvgisRefinePairs,
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
import { obstacleRing, type Obstacle } from '../lib/obstacles';
import { areaLabel } from '../lib/roofAreas';
import { buildSatelliteStyle, roofImageRequest, roofVertexUV, mapboxStaticRoofImageUrl } from '../lib/roofConfig';
import { type RoofTypeSelect } from '../lib/roofTypeSelect';
import { type ScaledProduction, type PerKwcProduction, type SpecificDateProfile } from '../lib/productionEngine';
import {
  cycleMonth,
  cycleDay,
  daysInMonth,
  DEFAULT_GRAPH_BOX,
  type ProductionScope,
  type ProductionSource,
  type SvgBox,
} from '../lib/productionWindow';
import {
  emptyCurve,
  type Appliance,
  type HourlyCurve,
} from '../lib/applianceConsumption';
import { type LayoutState } from '../lib/layoutVariability';

import {
  type InitOptions,
  type TiltMode,
  type OrientMode,
  type AzimuthMode,
  type MarginMode,
  type CardData,
  type ZoneRenderPlan,
  type AreaRecord,
  type RenderConfigOpts,
} from './roofPro11/types';
import {
  GOLD,
  MOROCCO_CENTER,
  FLOOR_HEIGHT_M,
  PITCH_VIEW,
  DECK_THK,
  FLOORS,
  OBSTACLE_BOX_H_M,
  DEG2RAD,
  DEG2M,
} from './roofPro11/constants';
import { $, fmt, fmtMad, esc } from './roofPro11/dom';
import { makeCanadianPanelTexture } from './roofPro11/panelTexture';
import { type Ctx } from './roofPro11/context';
import { createGraphs } from './roofPro11/graphs';
import { createPrefill } from './roofPro11/prefill';
import { createZones } from './roofPro11/zones';
import { createConsumption } from './roofPro11/consumption';
import { createProdWindow } from './roofPro11/prodWindow';
import { createMatrix } from './roofPro11/matrix';
import { createLayoutEditor } from './roofPro11/layoutEditor';
import { createObstaclesUi } from './roofPro11/obstaclesUi';
import { createMapDraw } from './roofPro11/mapDraw';

let booted = false;

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
  // — Recherche d'adresse (rp9-search / rp9-address) : DOM piloté par roofPro11/mapDraw.ts —
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
  // — Obstacles : le DOM (bouton ajouter/effacer, panneau d'édition, saisies longueur/
  // largeur, +/−, suppr.) est piloté par le module roofPro11/obstaclesUi.ts. —
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
  // W69 — « Personnaliser la disposition » : le panneau complet est piloté par le module
  // roofPro11/layoutEditor. L'entrée ne garde QUE les références nécessaires pour remettre
  // le panneau à zéro depuis reset()/clearEditorState() (mêmes nœuds, même comportement).
  const layoutWindowEl = $('rp9-layout-window');
  const layoutToggleEl = $<HTMLButtonElement>('rp9-layout-toggle');
  const layoutPanelEl = $('rp9-layout-panel');
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
  let lastDraw: LngLat | null = null; // dernier point pointé pendant un glissé-dessin
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

  // — Contexte partagé pont vers les modules extraits (split modulaire). Les champs
  // d'état mutables sont exposés par accesseur : le code resté dans ce fichier garde
  // ses `let` bruts, les modules lisent/écrivent via `ctx.*` — comportement INCHANGÉ.
  const ctx: Ctx = {
    opts,
    svgBox: SVG_BOX,
    dom: {
      addAreaBtn,
      areasWindowEl,
      areasListEl,
      areasTotalPanelsEl,
      areasTotalKwcEl,
      areasTotalProdEl,
      areasTotalSavingsEl,
    },
    get vertices() {
      return vertices;
    },
    set vertices(v) {
      vertices = v;
    },
    get closed() {
      return closed;
    },
    set closed(v) {
      closed = v;
    },
    get obstacles() {
      return obstacles;
    },
    set obstacles(v) {
      obstacles = v;
    },
    get selectedObsId() {
      return selectedObsId;
    },
    set selectedObsId(v) {
      selectedObsId = v;
    },
    get obsCounter() {
      return obsCounter;
    },
    set obsCounter(v) {
      obsCounter = v;
    },
    get obstacleMode() {
      return obstacleMode;
    },
    set obstacleMode(v) {
      obstacleMode = v;
    },
    get drawStart() {
      return drawStart;
    },
    set drawStart(v) {
      drawStart = v;
    },
    get drawing() {
      return drawing;
    },
    set drawing(v) {
      drawing = v;
    },
    get suppressClick() {
      return suppressClick;
    },
    set suppressClick(v) {
      suppressClick = v;
    },
    get lastDraw() {
      return lastDraw;
    },
    set lastDraw(v) {
      lastDraw = v;
    },
    get moveObs() {
      return moveObs;
    },
    set moveObs(v) {
      moveObs = v;
    },
    get obstacleMeshes() {
      return obstacleMeshes;
    },
    get sceneOrigin() {
      return sceneOrigin;
    },
    set sceneOrigin(v) {
      sceneOrigin = v;
    },
    get roofType() {
      return roofType;
    },
    set roofType(v) {
      roofType = v;
    },
    get pitchDeg() {
      return pitchDeg;
    },
    set pitchDeg(v) {
      pitchDeg = v;
    },
    get facingAzimuthDeg() {
      return facingAzimuthDeg;
    },
    set facingAzimuthDeg(v) {
      facingAzimuthDeg = v;
    },
    get neededPanels() {
      return neededPanels;
    },
    set neededPanels(v) {
      neededPanels = v;
    },
    get neededAuto() {
      return neededAuto;
    },
    set neededAuto(v) {
      neededAuto = v;
    },
    get rec() {
      return rec;
    },
    set rec(v) {
      rec = v;
    },
    get useRecommended() {
      return useRecommended;
    },
    set useRecommended(v) {
      useRecommended = v;
    },
    get liveResult() {
      return liveResult;
    },
    set liveResult(v) {
      liveResult = v;
    },
    get pitchedLiveResult() {
      return pitchedLiveResult;
    },
    set pitchedLiveResult(v) {
      pitchedLiveResult = v;
    },
    get matrixResult() {
      return matrixResult;
    },
    set matrixResult(v) {
      matrixResult = v;
    },
    get matrixSort() {
      return matrixSort;
    },
    set matrixSort(v) {
      matrixSort = v;
    },
    get matrixFilter() {
      return matrixFilter;
    },
    set matrixFilter(v) {
      matrixFilter = v;
    },
    areas,
    get activeAreaId() {
      return activeAreaId;
    },
    set activeAreaId(v) {
      activeAreaId = v;
    },
    activeArea,
    get prodMonth() {
      return prodMonth;
    },
    set prodMonth(v) {
      prodMonth = v;
    },
    get prodSpecificDate() {
      return prodSpecificDate;
    },
    set prodSpecificDate(v) {
      prodSpecificDate = v;
    },
    get prodScaled() {
      return prodScaled;
    },
    set prodScaled(v) {
      prodScaled = v;
    },
    get prodPanels() {
      return prodPanels;
    },
    set prodPanels(v) {
      prodPanels = v;
    },
    get centroidLat() {
      return centroidLat;
    },
    set centroidLat(v) {
      centroidLat = v;
    },
    get consMode() {
      return consMode;
    },
    set consMode(v) {
      consMode = v;
    },
    get consCurve() {
      return consCurve;
    },
    set consCurve(v) {
      consCurve = v;
    },
    get consHandEdited() {
      return consHandEdited;
    },
    set consHandEdited(v) {
      consHandEdited = v;
    },
    get consAppliances() {
      return consAppliances;
    },
    set consAppliances(v) {
      consAppliances = v;
    },
    get consDailyTarget() {
      return consDailyTarget;
    },
    set consDailyTarget(v) {
      consDailyTarget = v;
    },
    get consApplCounter() {
      return consApplCounter;
    },
    set consApplCounter(v) {
      consApplCounter = v;
    },
    get centroid() {
      return centroid;
    },
    set centroid(v) {
      centroid = v;
    },
    get prodScope() {
      return prodScope;
    },
    set prodScope(v) {
      prodScope = v;
    },
    get prodDay() {
      return prodDay;
    },
    set prodDay(v) {
      prodDay = v;
    },
    get prodToken() {
      return prodToken;
    },
    set prodToken(v) {
      prodToken = v;
    },
    get prodPerKwc() {
      return prodPerKwc;
    },
    set prodPerKwc(v) {
      prodPerKwc = v;
    },
    get prodSource() {
      return prodSource;
    },
    set prodSource(v) {
      prodSource = v;
    },
    get prodTarget() {
      return prodTarget;
    },
    set prodTarget(v) {
      prodTarget = v;
    },
    get prodPlaneKey() {
      return prodPlaneKey;
    },
    set prodPlaneKey(v) {
      prodPlaneKey = v;
    },
    get layoutMode() {
      return layoutMode;
    },
    set layoutMode(v) {
      layoutMode = v;
    },
    get layoutState() {
      return layoutState;
    },
    set layoutState(v) {
      layoutState = v;
    },
    get layoutPlan() {
      return layoutPlan;
    },
    set layoutPlan(v) {
      layoutPlan = v;
    },
    get layoutOptimalCount() {
      return layoutOptimalCount;
    },
    set layoutOptimalCount(v) {
      layoutOptimalCount = v;
    },
    get layoutSel() {
      return layoutSel;
    },
    set layoutSel(v) {
      layoutSel = v;
    },
  };
  const graphs = createGraphs(ctx);
  const prefill = createPrefill(ctx);
  const prefillLead = prefill.prefillLead;
  const zones = createZones(ctx);
  const liveActiveResult = zones.liveActiveResult;
  const snapshotActiveAreaResult = zones.snapshotActiveAreaResult;
  const snapshotActiveAreaGeometry = zones.snapshotActiveAreaGeometry;
  const syncAddAreaButton = zones.syncAddAreaButton;
  const renderAreasPanel = zones.renderAreasPanel;
  // W68 — « Affiner ma consommation ». Les dépendances optimiseur/facture sont
  // injectées en wrappers paresseux (les bindings sont déclarés plus bas).
  const consumption = createConsumption(
    ctx,
    {
      consWindowEl,
      consToggleEl,
      consPanelEl,
      consTotalEl,
      consSelfEl,
      consSavingsEl,
      consBattEl,
      consGraphEl,
      consInputsEl,
      consRecalEl,
      applKindEl,
      applAddEl,
      applAcEl,
      acBtuEl,
      acEerEl,
      acHoursEl,
      acWattsEl,
      applEvEl,
      evKwEl,
      evHoursEl,
      evKmEl,
      applNoteEl,
      applListEl,
    },
    {
      renderActive: () => renderActive(),
      clampNeeded: (n) => clampNeeded(n),
      monthlyBill: () => monthlyBill(),
      fmt1,
    },
  );
  const renderConsumption = consumption.renderConsumption;
  // W50 — fenêtre « Production estimée ». `renderLayoutPanel` est injectée en wrapper
  // paresseux (fonction déclarée plus bas, hoistée mais référencée à l'exécution).
  const prodWindow = createProdWindow(
    ctx,
    {
      prodWindowEl,
      prodScopeWrap,
      prodMonthPickerEl,
      prodMonthLabelEl,
      prodDayPickerEl,
      prodDayLabelEl,
      prodDayResetEl,
      prodHeadlineEl,
      prodSubEl,
      prodGraphEl,
      prodSourceEl,
      prodSavingsEl,
    },
    {
      graphs,
      renderConsumption,
      renderLayoutPanel: () => renderLayoutPanel(),
      snapshotActiveAreaResult,
      renderAreasPanel,
    },
  );
  const updateProductionWindow = prodWindow.updateProductionWindow;
  const prodConfigFromState = prodWindow.prodConfigFromState;
  const syncProductionWindow = prodWindow.syncProductionWindow;
  // V6 — MATRICE (toit plat). `renderConfig`/`monthlyBill` injectés en wrappers
  // paresseux (déclarés plus bas, référencés à l'exécution).
  const matrix = createMatrix(ctx, {
    renderConfig: (o) => renderConfig(o),
    monthlyBill: () => monthlyBill(),
    obstructionRings,
  });
  const paintComparison = matrix.paintComparison;
  const renderMatrixRow = matrix.renderMatrixRow;
  const highlightRow = matrix.highlightRow;
  const recomputeMatrix = matrix.recomputeMatrix;
  const setMatrixSort = matrix.setMatrixSort;

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

  // W69 — « Personnaliser la disposition ». `renderScene`/`renderActive`/`obstacleMode`
  // sont déclarés plus bas : injectés en wrappers paresseux (hoistés, référencés à
  // l'exécution). Le module câble lui-même +/−/reset/grille tactile/glissé 3D.
  const layoutEditor = createLayoutEditor(ctx, {
    map,
    renderScene: (pack, grid, tiltDeg, family, maxCount, flush, occupiedSet) =>
      renderScene(pack, grid, tiltDeg, family, maxCount, flush, occupiedSet),
    prodConfigFromState,
    updateProductionWindow,
    snapshotActiveAreaResult,
    renderAreasPanel,
    renderActive: () => renderActive(),
    isObstacleMode: () => obstacleMode,
  });
  // Seul `renderLayoutPanel` est appelé depuis l'entrée (injecté dans la fenêtre de
  // production) ; les autres méthodes du module pilotent son propre câblage interne.
  const renderLayoutPanel = layoutEditor.renderLayoutPanel;

  // — Obstacles (zones d'exclusion). `recalc` est déclaré plus bas : injecté en wrapper
  // paresseux. Le module câble lui-même le bouton « ajouter »/« effacer » + l'édition
  // numérique ; l'entrée garde le DISPATCHER carte (partagé avec le tracé) qui appelle
  // beginDraw/moveDraw/endDraw/tryBeginMove/doMove/endMove.
  const obstaclesUi = createObstaclesUi(ctx, {
    map,
    recalc: () => recalc(),
    setStatus,
  });
  const redrawObstacles = obstaclesUi.redrawObstacles;
  const clearPreview = obstaclesUi.clearPreview;
  const syncObsEdit = obstaclesUi.syncObsEdit;
  const selectObstacle = obstaclesUi.selectObstacle;
  const obstacleAtPoint = obstaclesUi.obstacleAtPoint;
  const setObstacleMode = obstaclesUi.setObstacleMode;
  const beginDraw = obstaclesUi.beginDraw;
  const moveDraw = obstaclesUi.moveDraw;
  const endDraw = obstaclesUi.endDraw;
  const tryBeginMove = obstaclesUi.tryBeginMove;
  const doMove = obstaclesUi.doMove;
  const endMove = obstaclesUi.endMove;

  // — Tracé du contour + recherche d'adresse (géocodage W75). Le module câble lui-même
  // le formulaire de recherche ; l'entrée garde la construction de la carte, le boot
  // map.on('load') (couche WebGL) et l'orchestration close().
  const mapDraw = createMapDraw(ctx, {
    map,
    setStatus,
    updateAreaReadout,
  });
  const redrawTrace = mapDraw.redrawTrace;
  const addVertex = mapDraw.addVertex;
  const geocode = mapDraw.geocode;

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

  // ═══════════ TRACÉ + GÉOCODAGE : voir roofPro11/mapDraw.ts ═══════════
  // redrawTrace/addVertex (garde W76) + geocode (garde anti-course W75) + le câblage du
  // formulaire de recherche vivent dans le module ; créés plus haut via createMapDraw(ctx, …).

  // ═══════════ OBSTACLES (zones d'exclusion) : voir roofPro11/obstaclesUi.ts ═══════════
  // redrawObstacles/setPreviewRect/clearPreview/syncObsEdit/selectObstacle/updateSelected/
  // deleteSelected/addObstacle/obstacleAtPoint + le glissé-dessin/déplacement + l'édition
  // numérique vivent dans le module ; créés plus bas via createObstaclesUi(ctx, …).

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

  // ═══════════ W50 — fenêtre « Production estimée » : voir roofPro11/prodWindow.ts ═══════════

  // ═══════════ « PLUSIEURS ZONES » — instantané + panneau de total : voir roofPro11/zones.ts ═══════════

  // ═══════════ W68 — « Affiner ma consommation » : voir roofPro11/consumption.ts ═══════════

  // ═══════════ W69 — « Personnaliser la disposition » : voir roofPro11/layoutEditor.ts ═══════════
  // `layoutCap`/`ensureLayoutState`/`renderCustomLayout`/`screenToENU`/`renderLayoutPanel`/
  // `setLayoutMode` + le câblage (+/−/reset/grille tactile/glissé 3D) vivent dans le module ;
  // ils sont créés plus bas via createLayoutEditor(ctx, …) une fois `map`/`renderScene`/etc.
  // disponibles. L'entrée n'en garde que les bindings d'état (layoutPlan/…, sur ctx).

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

  // ═══════════ V6 — MATRICE de comparaison (toit plat) : voir roofPro11/matrix.ts ═══════════

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

  // — Mode obstacle / glissé-dessin / glissé-déplacement : voir roofPro11/obstaclesUi.ts —

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

  // ═══════════ W68 — câblage « Affiner ma consommation » : voir roofPro11/consumption.ts ═══════════
  consumption.wire();

  // ═══════════ W69 — câblage « Personnaliser la disposition » : voir roofPro11/layoutEditor.ts ═══════════

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

  // — Obstacles : bouton « ajouter »/« effacer » + édition numérique : voir roofPro11/obstaclesUi.ts —

  // — Recherche d'adresse (géocodage W75) : voir roofPro11/mapDraw.ts —
}
