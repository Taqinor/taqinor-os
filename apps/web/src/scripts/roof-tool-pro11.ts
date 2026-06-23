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
import {
  recommend,
  billToAnnualKwh,
  neededPanelsForTarget,
  TILT_SWEEP_MIN,
  type Recommendation,
  type PackResult,
  type PanelGrid,
  type ConfigFamily,
} from '../lib/estimatorBrainV2';
import { PERIMETER_SETBACK_M, WINTER_SOLSTICE_DAY } from '../lib/roofPro2';
import {
  reoptimize,
  type FlatPins,
  type PitchedRecommendation,
} from '../lib/estimatorBrainV3';
import {
  type MatrixSortKey,
  type MatrixV6Result,
} from '../lib/estimatorBrainV6';
import {
  type LiveSolveResult,
} from '../lib/estimatorBrainV7';
import {
  type PitchedLayoutAxis,
  type PitchedLiveResult,
  type PitchedMarginAxis,
} from '../lib/estimatorBrainV8';
import { isSimplePolygon, roofAreaLabel, type LngLat } from '../lib/roof';
import { inferZoneFacingAmong } from '../lib/roofAdjacency';
import { obstacleRing, type Obstacle } from '../lib/obstacles';
import { areaLabel } from '../lib/roofAreas';
import { buildSatelliteStyle } from '../lib/roofConfig';
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
  PITCH_VIEW,
} from './roofPro11/constants';
import { $, fmt, fmtMad, esc } from './roofPro11/dom';
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
import { createScene3d } from './roofPro11/scene3d';
import { createOptimizer } from './roofPro11/optimizer';
import { bootCaptureOnly } from './roofPro11/captureBoot';
import { hydrateFromLead, serializeLayout } from './roofPro11/prefill';

let booted = false;

export function initRoofToolPro8(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  // W112 — mode CAPTURE CLIENT (/devis/mon-toit) : carte + géocodeur + pin/tracé
  // SEULEMENT. On dévie AVANT toute construction lourde (createScene3d /
  // createOptimizer / createMatrix ne sont jamais appelés ici), donc aucun panneau,
  // aucune 3D, aucune carte de production ne peut apparaître. Le boot complet ci-
  // dessous reste octet pour octet identique quand le drapeau est absent/false.
  if (opts.captureOnly) {
    bootCaptureOnly(opts);
    return;
  }

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
  // W92 — « Annuler le dernier point » : visible pendant le tracé, masqué dès la fermeture/reset.
  const undoPointBtn = $<HTMLButtonElement>('rp9-undo-point');
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
  // W87 — soleil réel : curseur d'heure solaire + bascule saison qui pilotent
  // ctx.sunHour / ctx.sunDay (la scène 3D positionne un VRAI soleil et son ombre).
  const sunHourEl = $<HTMLInputElement>('rp9-sun-hour');
  const sunHourValueEl = $('rp9-sun-hour-value');
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
  // Correction FINE du sens de la pente (curseur 0–359° + lecture vivante).
  const facingRangeEl = $<HTMLInputElement>('rp9-facing-range');
  const facingValueEl = $('rp9-facing-value');
  const facingNoteEl = $('rp9-facing-note'); // W106 — note « face auto-orientée / réglée à la main »
  const overhangInputEl = $<HTMLInputElement>('rp9-overhang-input'); // W109 — débord panneaux (m)
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
  const consResetEl = $<HTMLButtonElement>('rp9-cons-reset');
  const consPaybackEl = $('rp9-cons-payback');
  const consSeasonalToggleEl = $<HTMLButtonElement>('rp9-cons-seasonal-toggle');
  const consSeasonalControlsEl = $('rp9-cons-seasonal-controls');
  const consSummerFactorEl = $<HTMLInputElement>('rp9-cons-summer');
  const consWinterFactorEl = $<HTMLInputElement>('rp9-cons-winter');
  const consMonthlyChartEl = $('rp9-cons-month-chart');
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
  // W77 — sommet en attente (clic capté, pas encore posé pendant le délai anti-dblclick) :
  // on le mémorise pour le POSER si un second tap arrive vite (tracé rapide), au lieu de le
  // jeter. `lastTapMs`/`lastTapPt` détectent le double-tap tactile (fenêtre ~300 ms + même
  // endroit) pour FINIR le tracé au doigt (parité avec le dblclick desktop).
  let pendingVertex: LngLat | null = null;
  let pendingVertexPt: maplibregl.Point | null = null;
  let lastTapMs = 0;
  let lastTapPt: maplibregl.Point | null = null;
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
  // W92 — glissé-déplacement d'un SOMMET du tracé (delta lng/lat sur ctx.vertices[idx]).
  let moveVertex: { idx: number; startLng: number; startLat: number; vLng: number; vLat: number; moved: boolean } | null = null;
  let rec: Recommendation | null = null;
  // W113 — repère VISIBLE du pin client (étude Meriem) : quand un lead n'apporte qu'un
  // pin (pas de contour ≥3 sommets), on plante un marqueur laiton à l'endroit exact pointé
  // par le client, distinct du contour que Meriem trace. Posé dans applyHydration, retiré
  // dans clearEditorState (nouveau lead / effacement). null hors flux d'hydratation.
  let clientPinMarker: maplibregl.Marker | null = null;
  const removeClientPinMarker = () => {
    if (clientPinMarker) {
      clientPinMarker.remove();
      clientPinMarker = null;
    }
  };
  // V3 — type de toit (plat = modèle existant, défaut ; pente = pose affleurante),
  // pente + face SAISIES (imposent l'inclinaison et l'azimut de l'array), et le
  // résultat pente courant. `pinned` = axes que l'utilisateur a explicitement figés
  // (le bouton Optimum tient ces axes et re-résout le reste).
  type RoofType = 'flat' | 'pitched';
  let roofType: RoofType = 'flat';
  let pitchDeg = 22;
  let facingAzimuthDeg = 180;
  // W106 — la face d'un pan a-t-elle été FIXÉE À LA MAIN (boutons « Face du pan »
  // ou azimut fin) ? Si oui, l'inférence d'adjacence à l'ajout d'une zone NE
  // l'écrase JAMAIS (le choix manuel gagne, par zone, persisté dans l'enregistrement).
  let facingManual = false;
  // W106 — la face courante vient-elle d'être AUTO-déduite d'un pan voisin (vs réglée
  // à la main / par défaut sud) ? Pilote la note « face auto-orientée » sous les contrôles.
  let facingAutoInferred = false;
  let pitchedRec: PitchedRecommendation | null = null;
  const pinned = new Set<'family' | 'tilt' | 'orient' | 'azimuth' | 'margin'>();

  // Les obstacles sont stockés par centre + dimensions ; le cerveau reçoit leurs
  // rectangles lng/lat comme obstructions (zones d'exclusion).
  const obstructionRings = (): LngLat[][] => obstacles.map(obstacleRing);
  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const dimsLabel = (o: Obstacle) => `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;
  let centroid: LngLat = [0, 0];
  let centroidLat = 33.5;
  // W87 — heure solaire (0–24) et jour de l'année qui pilotent le VRAI soleil de la
  // scène 3D. Défaut = midi solaire au solstice d'hiver (jour 355) : le PIRE cas
  // d'ombrage, où les rangées espacées par l'angle de design se dégagent visiblement.
  let sunHour = 12;
  let sunDay = WINTER_SOLSTICE_DAY;
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

  // W109 — débord panneaux autorisé au-delà de la rive (m), saisi dans #rp9-overhang-input.
  // 0 par défaut → calepinage/solve inchangés. Change la CAPACITÉ géométrique seulement :
  // posé = min(besoin, ce qui tient) reste plafonné au besoin (cap facture intact).
  let overhangM = 0;

  // W1 — Azimut de FACE pour l'array sud, selon le groupe AZIMUT : « aligné toit »
  // suit les arêtes (rec.roofAlignedAzimuthDeg), sinon plein sud (180).
  const azimuthDegOf = (): number =>
    sel.azimuth === 'aligned' && rec ? rec.roofAlignedAzimuthDeg : 180;

  // W1 — Cache PVGIS partagé entre TOUS les réglages (production, par config plate).
  // Vidé par l'entrée à chaque nouvelle localisation (close/clearEditorState/loadArea) ;
  // lu/écrit par l'optimiseur (roofPro11/optimizer.ts) via ctx.pvgisCache.
  const pvgisCache = new Map<string, number | null>();
  // V4 — rendement spécifique PVGIS (kWh/kWc/an) par (tilt|aspect), pose 'free'.
  const v4YieldCache = new Map<string, number | null>();
  // V6 — MATRICE complète (toit plat) : balayage dense RENVOYÉ pour affichage, avec
  // l'état de tri/filtre du tableau (le balayage/affinage PVGIS vit dans l'optimiseur).
  let matrixResult: MatrixV6Result | null = null;
  let matrixSort: { key: MatrixSortKey; dir: 'asc' | 'desc' } = { key: 'annualKwh', dir: 'desc' };
  let matrixFilter = 'all';

  // W34/W35 — derniers résultats des optimiseurs vivants (plat = V7, pente = V8).
  let liveResult: LiveSolveResult | null = null;
  // W35 — verrous pose/marge du toit en pente (axes libres) ; le besoin partage
  // `neededAuto`. Réf STABLE muté en place, partagé avec l'optimiseur via ctx.pitchedLocks.
  const pitchedLocks: { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis } = {};
  let pitchedLiveResult: PitchedLiveResult | null = null;

  // V5 — toit en pente : cache rendement spécifique PVGIS (kWh/kWc/an) par (pente|face),
  // pose 'building'. Vidé par l'entrée ; lu/écrit par l'optimiseur via ctx.pitchedYieldCache.
  const pitchedYieldCache = new Map<string, number | null>();
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
  // W95 — profil saisonnier (été ≠ hiver). Désactivé par défaut (12 mois identiques).
  let consSeasonal = false;
  let consSummerFactor = 1.3; // conso d'été ≈ +30 % (clim) par défaut, éditable
  let consWinterFactor = 0.9; // conso d'hiver ≈ −10 % par défaut, éditable

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
      facingManual: false,
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
    get moveVertex() {
      return moveVertex;
    },
    set moveVertex(v) {
      moveVertex = v;
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
    get activePanelMesh() {
      return activePanelMesh;
    },
    set activePanelMesh(v) {
      activePanelMesh = v;
    },
    get activePanelCellIndex() {
      return activePanelCellIndex;
    },
    set activePanelCellIndex(v) {
      activePanelCellIndex = v;
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
    get facingManual() {
      return facingManual;
    },
    set facingManual(v) {
      facingManual = v;
    },
    get overhangM() {
      return overhangM;
    },
    set overhangM(v) {
      overhangM = v;
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
    get pitchedRec() {
      return pitchedRec;
    },
    set pitchedRec(v) {
      pitchedRec = v;
    },
    get sel() {
      return sel;
    },
    set sel(v) {
      sel = v;
    },
    pinned,
    pitchedLocks,
    get pvgisPerKwc() {
      return pvgisPerKwc;
    },
    set pvgisPerKwc(v) {
      pvgisPerKwc = v;
    },
    get pitchedPvgisPerKwc() {
      return pitchedPvgisPerKwc;
    },
    set pitchedPvgisPerKwc(v) {
      pitchedPvgisPerKwc = v;
    },
    pvgisCache,
    v4YieldCache,
    pitchedYieldCache,
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
    get sunHour() {
      return sunHour;
    },
    set sunHour(v) {
      sunHour = v;
    },
    get sunDay() {
      return sunDay;
    },
    set sunDay(v) {
      sunDay = v;
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
    get consSeasonal() {
      return consSeasonal;
    },
    set consSeasonal(v) {
      consSeasonal = v;
    },
    get consSummerFactor() {
      return consSummerFactor;
    },
    set consSummerFactor(v) {
      consSummerFactor = v;
    },
    get consWinterFactor() {
      return consWinterFactor;
    },
    set consWinterFactor(v) {
      consWinterFactor = v;
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
      consResetEl,
      consPaybackEl,
      consSeasonalToggleEl,
      consSeasonalControlsEl,
      consSummerFactorEl,
      consWinterFactorEl,
      consMonthlyChartEl,
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
    renderConfig: (o) => optimizer.renderConfig(o),
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
  // W91 — bouton « ma position » : GeolocateControl natif de MapLibre (aucune dépendance
  // ajoutée). Sur `geolocate`, on recentre nous-mêmes en zoom 19 (le contrôle natif ne
  // garantit pas le zoom toit) en respectant reduced-motion (jumpTo sinon flyTo).
  const geolocate = new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: false,
    showUserLocation: true,
  });
  map.addControl(geolocate, 'top-right');
  geolocate.on('geolocate', (e: { coords?: { longitude: number; latitude: number } }) => {
    const c = e?.coords;
    if (!c) return;
    const target = { center: [c.longitude, c.latitude] as LngLat, zoom: 19, pitch: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.flyTo({ ...target, essential: true });
  });
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
    // W88 — surlignage/pick des panneaux 3D : `setPanelHighlight` (scene3d) est déclaré plus
    // bas → wrapper paresseux (référencé seulement à l'exécution d'un survol/clic 3D).
    setPanelHighlight: (cellIndex) => setPanelHighlight(cellIndex),
  });
  // `renderLayoutPanel` est appelé depuis l'entrée (injecté dans la fenêtre de production) ;
  // W79 — `occupiedCenters`/`reenterCustomLayout` permettent à recalc() de re-entrer la
  // disposition personnalisée (re-snap sur la nouvelle lattice) après une édition d'obstacle
  // ou d'axe pendant que l'éditeur est ouvert. Les autres méthodes pilotent le câblage interne.
  const renderLayoutPanel = layoutEditor.renderLayoutPanel;
  const occupiedCenters = layoutEditor.occupiedCenters;
  const reenterCustomLayout = layoutEditor.reenterCustomLayout;

  // — Obstacles (zones d'exclusion). `recalc` est déclaré plus bas : injecté en wrapper
  // paresseux. Le module câble lui-même le bouton « ajouter »/« effacer » + l'édition
  // numérique ; l'entrée garde le DISPATCHER carte (partagé avec le tracé) qui appelle
  // beginDraw/moveDraw/endDraw/tryBeginMove/doMove/endMove.
  const obstaclesUi = createObstaclesUi(ctx, {
    map,
    recalc: () => recalc(),
    setStatus,
    // W92 — wrapper paresseux : `redrawTrace` (du module mapDraw) est assigné plus bas ;
    // référencé seulement à l'exécution d'un glissé-sommet, donc pas de TDZ.
    redrawTrace: () => redrawTrace(),
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
  // W92 — glissé d'un SOMMET du tracé (généralisation du glissé d'obstacle).
  const tryBeginVertexMove = obstaclesUi.tryBeginVertexMove;
  const doVertexMove = obstaclesUi.doVertexMove;
  const endVertexMove = obstaclesUi.endVertexMove;

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

  // Change C : meshes d'obstacles 3D (transparents) suivis par id pour les DÉPLACER
  // en direct pendant un glissé, et l'origine ENU de la scène courante (centroïde).
  // Pont partagé (sur ctx) avec scene3d (rempli par renderScene) et obstaclesUi (drag).
  const obstacleMeshes = new Map<string, THREE.Mesh>();
  let sceneOrigin: LngLat = [0, 0];
  // W88 — InstancedMesh des panneaux de la zone active + mapping instance→cellule (lattice),
  // remplis par renderScene ; lus par l'éditeur de disposition pour le pick/highlight/suppr.
  let activePanelMesh: THREE.InstancedMesh | null = null;
  let activePanelCellIndex: number[] = [];

  const empty = { type: 'FeatureCollection', features: [] } as const;

  // — Scène 3D Three.js (couche WebGL custom MapLibre) : voir roofPro11/scene3d.ts. Le
  // module possède le renderer/scène/caméra/soleil + la photo de toit (W70) ; l'entrée
  // garde la construction de la carte et le boot map.on('load') (qui ajoute customLayer).
  const scene3d = createScene3d(ctx, { map, lowEnd, shadowSize });
  const customLayer = scene3d.customLayer;
  const disposeScene = scene3d.disposeScene;
  const renderScene = scene3d.renderScene;
  const setPanelHighlight = scene3d.setPanelHighlight; // W88 — surlignage/pick des panneaux 3D

  // — Moteur d'optimisation vivante (W34/V7 plat + W35/V8 pente + matrice V6 PVGIS) :
  // voir roofPro11/optimizer.ts. `syncChips`/`renderMatrixOptimumCard` sont déclarés plus
  // bas → injectés en wrappers paresseux (référencés à l'exécution, pas au boot). L'entrée
  // garde l'orchestration recompute()/recalc()/close() + le câblage DOM, qui appellent
  // ces fonctions via l'objet renvoyé.
  const optimizer = createOptimizer(ctx, {
    renderScene,
    paintComparison,
    highlightRow,
    syncProductionWindow,
    prefillLead,
    syncChips: () => syncChips(),
    renderMatrixOptimumCard: () => renderMatrixOptimumCard(),
    monthlyBill: () => monthlyBill(),
    obstructionRings,
    setStatus,
  });
  const liveResolveFlat = optimizer.liveResolveFlat;
  const liveResolvePitched = optimizer.liveResolvePitched;
  const renderSelection = optimizer.renderSelection;
  const renderConfig = optimizer.renderConfig;
  const pitchedRecompute = optimizer.pitchedRecompute;
  const resetFlatLocks = optimizer.resetFlatLocks;
  const resetPitchedLocks = optimizer.resetPitchedLocks;
  const computeMatrixPvgis = optimizer.computeMatrixPvgis;

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
    // W113 — HYDRATATION depuis un lead (étude Meriem) : sème le contour/pin du client
    // + les champs contact AVANT le géocodage, puis ferme le tracé et lance le calcul.
    // Quand `hydrate` est absent, ce bloc est sauté → boot inchangé.
    const seeded = opts.hydrate?.lead ? applyHydration(opts.hydrate.lead) : false;
    // W93 — `initialQuery` est programmatique : on auto-sélectionne le 1ᵉʳ résultat (vol
    // direct), au lieu d'ouvrir la liste de suggestions. On ne géocode pas si on a déjà
    // hydraté un contour/pin (le vol vers le lead l'emporte).
    if (!seeded && opts.initialQuery) void geocode(opts.initialQuery, true);
    else if (!seeded) setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  /** W113 — applique l'hydratation d'un lead à l'état d'édition (zone active) : sème le
   *  contour (ou un pin centré), recentre la carte, pré-remplit les champs contact du
   *  diagnostic, puis ferme + recalc si un vrai contour (≥3 sommets) est fourni. Renvoie
   *  true si quelque chose a été semé (pour ne pas re-géocoder par-dessus). */
  function applyHydration(lead: import('./roofPro11/types').LeadPayload): boolean {
    const h = hydrateFromLead(lead);
    // Champs contact du diagnostic (handoff, jamais un POST — même garde que prefill).
    const setIf = (id: string, v?: string) => {
      const el = $<HTMLInputElement>(id);
      if (el && v && !el.value.trim()) el.value = v;
    };
    setIf('lf-name', h.contact.name);
    setIf('lf-phone', h.contact.phone);
    setIf('lf-city', h.contact.city);
    if (h.vertices.length >= 3) {
      vertices = [...h.vertices];
      // fige la géométrie sur la zone active puis ferme (lance l'optimiseur via close()).
      const a = activeArea();
      if (a) a.vertices = [...vertices];
      close();
      return true;
    }
    if (h.center) {
      const target = { center: h.center, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      // Plante un marqueur laiton BIEN VISIBLE à l'endroit exact pointé par le client, pour
      // que Meriem voie son repère (distinct du contour qu'elle trace). On remplace tout
      // marqueur précédent (ré-hydratation d'un autre lead).
      removeClientPinMarker();
      clientPinMarker = new maplibregl.Marker({ color: '#e8b54a' })
        .setLngLat(h.center)
        .addTo(map);
      setStatus('Repère du client chargé — tracez le contour du toit pour lancer le calcul.');
      return true;
    }
    return false;
  }

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  // ═══════════ TRACÉ + GÉOCODAGE : voir roofPro11/mapDraw.ts ═══════════
  // redrawTrace/addVertex (garde W76) + geocode (garde anti-course W75) + le câblage du
  // formulaire de recherche vivent dans le module ; créés plus haut via createMapDraw(ctx, …).

  // ═══════════ OBSTACLES (zones d'exclusion) : voir roofPro11/obstaclesUi.ts ═══════════
  // redrawObstacles/setPreviewRect/clearPreview/syncObsEdit/selectObstacle/updateSelected/
  // deleteSelected/addObstacle/obstacleAtPoint + le glissé-dessin/déplacement + l'édition
  // numérique vivent dans le module ; créés plus bas via createObstaclesUi(ctx, …).

  // — Plafond « panneaux nécessaires » (Change A) —
  const clampNeeded = (n: number): number => Math.max(1, Math.min(400, Math.round(n)));

  // ═══════════ OPTIMISEUR VIVANT (W34/V7 plat + W35/V8 pente + matrice V6 PVGIS) ═══════════
  // tiltOf/gridFor/placedFor/syncNeedControl/renderConfig/syncTiltControl + tout le solveur
  // vivant (buildFlatLocks/liveResolveFlat/renderLiveWinner/…), le toit en pente
  // (flushToPack/liveResolvePitched/renderPitchedWinner/paintPitchedComparison/…), les cartes
  // (paintCard/paintMaxLine) et l'affinage PVGIS (fetchPvgis/v4SpecificYield/buildMatrix/
  // computeMatrixPvgis + caches) vivent dans roofPro11/optimizer.ts ; créés plus haut via
  // createOptimizer(ctx, …). L'entrée garde l'orchestration recompute()/recalc()/close() +
  // le câblage DOM, qui appellent ces fonctions via l'objet `optimizer`.
  // ── V6 — MATRICE de comparaison (toit plat) : voir aussi roofPro11/matrix.ts ──

  /** Recalcul/rendu selon le type de toit actif (plat = pipeline pro-5 inchangé). */
  function recalc() {
    // W79 — si l'éditeur de disposition est ouvert, on CAPTURE les centres ENU des panneaux
    // posés à la main AVANT le recalc : recompute()/pitchedRecompute() re-pavent le toit
    // (nouvelle lattice via renderScene → layoutState nullé), ce qui sinon ferait retomber
    // silencieusement la pose personnalisée sur l'optimum et périmerait les readouts.
    const prevCenters = layoutMode ? occupiedCenters() : null;
    if (roofType === 'pitched') pitchedRecompute();
    else recompute();
    // W79 — après le re-pavage, on RE-ENTRE la disposition personnalisée : re-snap de chaque
    // centre capturé vers la cellule valide la plus proche de la NOUVELLE lattice (les
    // panneaux survivent, re-snappés), puis re-rendu panneaux/grille/note (readouts à jour).
    if (prevCenters) reenterCustomLayout(prevCenters);
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
    syncFacingNote(); // W106 — la note de face apparaît/disparaît avec le mode pente
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
  /** W106 — Sur un toit EN PENTE, déduit la face (`facingAzimuthDeg`) du pan qu'on vient
   *  de fermer à partir des AUTRES zones déjà tracées (faîtière commune) plutôt que de
   *  retomber sur le sud (180°). Pignon → face ~opposée à la faîtière partagée ; mono-pente
   *  → copie la face du voisin. N'agit QUE si : toit en pente, override manuel ABSENT, une
   *  adjacence est trouvée (`connected`) avec une confiance raisonnable. Sinon laisse
   *  180°/le choix utilisateur. Lit la lib PURE roofAdjacency ; n'écrit rien d'autre que
   *  `facingAzimuthDeg` + les drapeaux d'état (manual/auto). */
  function autoInferFacing() {
    facingAutoInferred = false;
    if (roofType !== 'pitched' || facingManual || vertices.length < 3) return;
    const ring: LngLat[] = [...vertices];
    const others = areas.filter((a) => a.id !== activeAreaId && a.vertices.length >= 3);
    if (others.length === 0) return;
    const neighbours = others.map((a) => [...a.vertices] as LngLat[]);
    // Un voisin n'apporte sa face connue à la mono-pente que s'il est lui-même en pente.
    const neighbourFacings = others.map((a) => (a.roofType === 'pitched' ? a.facingAzimuthDeg : undefined));
    const res = inferZoneFacingAmong(ring, neighbours, neighbourFacings);
    if (!res.connected || res.confidence < 0.2) return;
    facingAzimuthDeg = res.facingAzimuthDeg;
    facingAutoInferred = true;
  }

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
    if (undoPointBtn) undoPointBtn.hidden = true; // W92 — plus d'annulation après fermeture
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
    // W92 — on GARDE les pastilles de sommets (avec leur `idx`) comme POIGNÉES éditables :
    // un coin posé reste glissable après fermeture. redrawTrace re-pose les points indexés
    // depuis ctx.vertices ; on efface ENSUITE la ligne plate (la 3D la remplace).
    redrawTrace();
    srcOf('rp9-line')?.setData(empty as never);
    if (configPanel) configPanel.hidden = false;
    go3DView();
    syncRoofTypeChips();
    // W106 — pan en pente adjacent à un autre : auto-oriente sa face vers la faîtière
    // commune (sauf override manuel). Les puces « Face du pan » reflètent la valeur déduite.
    autoInferFacing();
    syncFacingChips();
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
    removeClientPinMarker(); // W113 — retire le repère client (nouveau lead / effacement)
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
    // W106 — nouveau tracé : l'override manuel de face repart à zéro pour que la nouvelle
    // zone puisse s'auto-orienter vers une faîtière voisine à la fermeture.
    facingManual = false;
    facingAutoInferred = false;
    syncFacingNote();
    srcOf('rp9-line')?.setData(empty as never);
    srcOf('rp9-pts')?.setData(empty as never);
    clearPreview();
    redrawObstacles();
    syncObsEdit();
    disposeScene();
    scene3d.resetTextures(); // photo de toit + matrice modèle (scene3d en est propriétaire)
    map.triggerRepaint();
    if (configPanel) configPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    if (undoPointBtn) undoPointBtn.hidden = true; // W92 — masqué tant qu'aucun coin n'est posé
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
    facingManual = a.facingManual ?? false; // W106 — restaure l'override manuel par zone
    facingAutoInferred = false; // note d'inférence repart propre à la sélection de zone
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
    // Sens de pente PROPRE à la zone restaurée : aligne boutons cardinaux + curseur fin
    // (la pose se re-résout ensuite via recalc → liveResolvePitched).
    syncFacingChips();
    syncFacingSlider();
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
    // W92 — un SOMMET du tracé a priorité sur un obstacle (pastille au-dessus).
    if (tryBeginVertexMove([e.lngLat.lng, e.lngLat.lat], e.point)) return;
    tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on('mousemove', (e) => {
    if (drawing) moveDraw([e.lngLat.lng, e.lngLat.lat]);
    else if (moveVertex) doVertexMove([e.lngLat.lng, e.lngLat.lat]);
    else if (moveObs) doMove([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on('mouseup', (e) => {
    if (drawing) endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
    else if (moveVertex) endVertexMove();
    else if (moveObs) endMove();
  });
  map.on('touchstart', (e) => {
    suppressClick = false;
    if (obstacleMode) {
      beginDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    if (!e.points || e.points.length === 1) {
      // W92 — un SOMMET du tracé a priorité sur un obstacle (pastille au-dessus).
      if (tryBeginVertexMove([e.lngLat.lng, e.lngLat.lat], e.point)) return;
      tryBeginMove([e.lngLat.lng, e.lngLat.lat], e.point);
    }
  });
  map.on('touchmove', (e) => {
    if (drawing) {
      e.preventDefault();
      moveDraw([e.lngLat.lng, e.lngLat.lat]);
    } else if (moveVertex) {
      e.preventDefault();
      doVertexMove([e.lngLat.lng, e.lngLat.lat]);
    } else if (moveObs) {
      e.preventDefault();
      doMove([e.lngLat.lng, e.lngLat.lat]);
    }
  });
  // W77 — fenêtre/distance du double-tap tactile pour FINIR le tracé (parité dblclick).
  // Deux taps proches dans le temps ET l'espace = « terminer » ; deux taps éloignés = deux
  // coins distincts (tracé rapide) → on les pose tous les deux, jamais d'oubli.
  const TAP_FINISH_MS = 300;
  const DOUBLE_TAP_PX = 24;

  /** Pose IMMÉDIATEMENT le sommet en attente (annule le délai anti-dblclick). Sert quand un
   *  second tap distinct arrive vite : le coin déjà capté ne doit pas être jeté (W77). */
  function flushPendingVertex() {
    if (clickTimer) {
      clearTimeout(clickTimer);
      clickTimer = null;
    }
    if (pendingVertex) {
      const v = pendingVertex;
      pendingVertex = null;
      pendingVertexPt = null;
      addVertex(v);
    }
  }
  /** Annule le sommet en attente SANS le poser (geste « terminer » : double-clic / double-tap). */
  function cancelPendingVertex() {
    if (clickTimer) {
      clearTimeout(clickTimer);
      clickTimer = null;
    }
    pendingVertex = null;
    pendingVertexPt = null;
  }

  map.on('touchend', (e) => {
    if (drawing) {
      endDraw([e.lngLat.lng, e.lngLat.lat], e.point);
      return;
    }
    if (moveObs) {
      endMove();
      return;
    }
    // W77 — double-tap tactile = « terminer » (le dblclick desktop ne se déclenche pas au
    // doigt de façon fiable). On ne finit QUE si le tap précédent est proche dans le temps
    // ET l'espace ; sinon ce sont deux coins distincts (le synthétique `click` les posera).
    if (obstacleMode || closed) return;
    const now = Date.now();
    const pt = e.point;
    const isDoubleTap =
      lastTapPt != null &&
      now - lastTapMs <= TAP_FINISH_MS &&
      Math.abs(pt.x - lastTapPt.x) < DOUBLE_TAP_PX &&
      Math.abs(pt.y - lastTapPt.y) < DOUBLE_TAP_PX;
    if (isDoubleTap && vertices.length >= 3) {
      lastTapMs = 0;
      lastTapPt = null;
      cancelPendingVertex(); // le 1ᵉʳ tap du double-tap ne pose pas de sommet (parité dblclick)
      suppressClick = true; // neutralise le `click` synthétique de ce tap
      close();
      return;
    }
    lastTapMs = now;
    lastTapPt = pt;
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
    // W77 — un nouveau clic pendant le délai anti-dblclick : s'il est LOIN du sommet en
    // attente, c'est un VRAI coin suivant (tracé rapide) → on pose d'abord le précédent
    // (aucun coin perdu). S'il est au MÊME endroit, c'est un double-clic « terminer » : on
    // ne pose rien, le handler `dblclick` annulera le sommet en attente et fermera (parité
    // desktop INCHANGÉE : un double-clic ne laisse jamais de sommet parasite).
    if (pendingVertex) {
      const near =
        pendingVertexPt != null &&
        Math.abs(e.point.x - pendingVertexPt.x) < DOUBLE_TAP_PX &&
        Math.abs(e.point.y - pendingVertexPt.y) < DOUBLE_TAP_PX;
      if (near) return; // double-clic au même endroit → laisser dblclick gérer
      flushPendingVertex();
    }
    pendingVertex = lngLat;
    pendingVertexPt = e.point;
    clickTimer = setTimeout(() => {
      clickTimer = null;
      const v = pendingVertex;
      pendingVertex = null;
      pendingVertexPt = null;
      if (v) addVertex(v);
    }, 240);
  });
  map.on('dblclick', (e) => {
    e.preventDefault();
    cancelPendingVertex();
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
  function syncPitchChips() {
    document.querySelectorAll<HTMLButtonElement>('[data-pitch]').forEach((b) => {
      b.setAttribute('aria-pressed', String(Number(b.dataset.pitch) === Math.round(pitchDeg)));
    });
  }
  function syncFacingChips() {
    document.querySelectorAll<HTMLButtonElement>('[data-facing]').forEach((b) => {
      b.setAttribute('aria-pressed', String(Number(b.dataset.facing) === Math.round(facingAzimuthDeg)));
    });
    syncFacingNote();
  }
  // Boussole 8 points (FR) : nom cardinal de l'azimut courant pour la lecture vivante.
  const facingName = (az: number): string => {
    const names = ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ouest', 'Ouest', 'Nord-Ouest'];
    const a = ((az % 360) + 360) % 360;
    return names[Math.round(a / 45) % 8];
  };
  // Aligne le curseur fin + sa lecture sur l'azimut courant (clic bouton, zone
  // restaurée/sélectionnée, ou réglage cardinal). Changer de zone active montre
  // ainsi le sens de pente PROPRE à cette zone.
  const syncFacingSlider = () => {
    const az = ((facingAzimuthDeg % 360) + 360) % 360;
    if (facingRangeEl) facingRangeEl.value = String(az);
    if (facingValueEl) facingValueEl.textContent = `${facingName(az)} · ${Math.round(az)}°`;
  };
  /** W106 — note honnête sous « Face du pan » : auto-orientée vers une faîtière voisine,
   *  réglée à la main, ou défaut (sud / pan isolé). Vide en mode plat. */
  function syncFacingNote() {
    if (!facingNoteEl) return;
    if (roofType !== 'pitched') {
      facingNoteEl.textContent = '';
      return;
    }
    if (facingManual) {
      facingNoteEl.textContent = 'Face réglée à la main (votre choix est tenu pour cette zone).';
    } else if (facingAutoInferred) {
      facingNoteEl.textContent = 'Face auto-orientée vers la faîtière commune avec une zone voisine — cliquez « Face du pan » pour la corriger.';
    } else {
      facingNoteEl.textContent = '';
    }
  }
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
      // W106 — choix manuel : il GAGNE et est PER-ZONE (persisté via snapshotActiveAreaGeometry) ;
      // l'auto-inférence d'adjacence ne l'écrasera plus pour cette zone.
      facingManual = true;
      facingAutoInferred = false;
      const a = activeArea();
      if (a) a.facingManual = true;
      syncFacingChips();
      syncFacingSlider();
      if (roofType === 'pitched' && closed) pitchedRecompute();
    });
  });
  // Curseur FIN du sens de la pente (0–359°) : règle n'importe quelle direction,
  // par zone, sans jamais rejeter le nombre tapé. Normalise dans [0,360) puis
  // re-résout la pose en pente (zone fermée), exactement comme les boutons cardinaux.
  facingRangeEl?.addEventListener('input', () => {
    const v = Number(facingRangeEl.value);
    if (!Number.isFinite(v)) return;
    facingAzimuthDeg = ((v % 360) + 360) % 360;
    if (facingValueEl) facingValueEl.textContent = `${facingName(facingAzimuthDeg)} · ${Math.round(facingAzimuthDeg)}°`;
    syncFacingChips();
    if (roofType === 'pitched' && closed) pitchedRecompute();
  });
  syncFacingSlider();

  // W109 — débord panneaux autorisé (m) : valeur typée NON snappée (step="any"), bornée ≥ 0
  // côté logique seulement. Change la CAPACITÉ géométrique (plus de panneaux aux rives) puis
  // re-résout/re-rend (recalc gère plat ET pente) ; le cap besoin (facture) reste intact.
  overhangInputEl?.addEventListener('input', () => {
    const v = Number(overhangInputEl.value);
    overhangM = Number.isFinite(v) && v > 0 ? v : 0;
    if (closed) recalc();
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
  // W87 — heure du soleil : déplace ctx.sunHour (6–18 h, midi = 12) et re-rend la scène
  // ACTIVE (renderActive → renderScene repositionne le VRAI soleil + son ombre portée).
  // Ne touche AUCUN axe de config (la disposition est inchangée), seul le soleil bouge.
  if (sunHourEl) {
    sunHourEl.addEventListener('input', () => {
      const h = Math.round(Number(sunHourEl.value));
      if (!Number.isFinite(h)) return;
      ctx.sunHour = h;
      if (sunHourValueEl) sunHourValueEl.textContent = `${h} h`;
      renderActive();
    });
  }
  // W87 — saison : hiver (solstice = pire cas d'ombrage, défaut) ou été (jour 172).
  document.querySelectorAll<HTMLButtonElement>('[data-sun-season]').forEach((b) => {
    b.addEventListener('click', () => {
      ctx.sunDay = b.dataset.sunSeason === 'summer' ? 172 : WINTER_SOLSTICE_DAY;
      document.querySelectorAll<HTMLButtonElement>('[data-sun-season]').forEach((o) =>
        o.setAttribute('aria-pressed', String(o === b)),
      );
      renderActive();
    });
  });
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

  // W114/W115 — expose une petite API à la page de design (étude Meriem) : sérialiser
  // le layout finalisé (W113) + instantané PNG de la 3D (W115). Boot complet seulement
  // (jamais en capture). Absent → aucun effet.
  opts.onApiReady?.({
    serializeLayout: (billKwh?: number | null) =>
      serializeLayout(ctx, billKwh ?? (closed && vertices.length >= 3 ? billToAnnualKwh(monthlyBill()) : null)),
    snapshot: () => scene3d.snapshot(),
  });
}
