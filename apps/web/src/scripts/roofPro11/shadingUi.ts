/**
 * WJ19 — UI « Ombres voisines » (shadow-tracing) du builder pro-11.
 *
 * L'utilisateur trace une ombre VISIBLE sur l'image satellite (clic 1 = pied de
 * l'obstacle, clic 2 = bout de l'ombre). La hauteur est DÉDUITE (h = L·tan α) de la
 * position du soleil au moment supposé de la prise de vue (hypothèse ÉTIQUETÉE,
 * défaut ~10 h 30 solaire mi-saison — orbites héliosynchrones), puis :
 *   - l'obstruction est rendue en 3D (scene3d la lit via ctx.shadeObstructions) et
 *     projette une vraie ombre Three.js ;
 *   - la production PVGIS horaire est DÉRATÉE (ctx.shadeFactors, appliqué par la
 *     fenêtre de production) et le chiffre annuel suit (ctx.shadeAnnualFactor,
 *     appliqué par l'optimiseur).
 *
 * Tout le calcul vit dans le module PUR lib/shadingEngine.ts (testé). Ici : état,
 * câblage DOM, tracé sur la carte. Aucun réseau, aucun lead. Tous les nœuds DOM
 * sont optionnels (le harness jsdom ne les fournit pas) — l'outil tourne sans eux.
 */
import type * as maplibregl from 'maplibre-gl';
import { directPerduParHeure, moisDuJour, phraseDirectPerdu, svgCourbeDirectPerdu } from './courbeDirectPerdu'; // ACAL717
import { modeExpertActif } from './orientationOmbre'; // ACAL717
import { dateImageCapturee } from './imageCapture'; // ACAL496 / ACAL509
import { phraseVerdictOmbrage } from './verdictOmbrage'; // ACAL715
import { choixOptimisationCourant, poserChoixOptimisation } from './optimizer'; // ACAL548 (usage dans les fonctions seulement : import circulaire sûr)
import { identifiantsModulesParCellule } from './libellesAffectation'; // ACAL729
import { clePanAffectation } from './scene3d'; // ACAL1947 — la clé de pan de la coloration par chaîne (ACAL1516)
import {
  declarationSoleilPriseDeVue,
  SHADE_OBSTRUCTION_HALF_WIDTH_M,
  hourlyShadeFactors,
  annualShadeFactor,
  obstructionHeightFromShadow,
  shadeObstructionsENU,
  shadowVector,
  pointSolarAccess,
  pointSolarAccessMonth,
  solarAccessSummary,
  proposeShadedRemoval,
  couleurAccesActive, // maquette Panneaux : palette choisie par l'hôte (site = solarAccessColorRGB)
  type SolarAccessSummary,
  type ShadeRemovalProposal,
  type ShadeObstruction,
  type ShadeObstructionENU,
} from '../../lib/shadingEngine';
import { roofObstacleShadeEntries, type Obstacle } from '../../lib/obstacles';
import { hourlyHorizonFactors, maskedHourCount, type HorizonProfile } from '../../lib/horizonEngine';
import { environmentShadeEntries, type EnvironmentObject } from './environment';
import { fallbackPerKwc, type PerKwcProduction } from '../../lib/productionEngine';
import { pointInPolygon, type LngLat } from '../../lib/roof';
import { DEG2M, DEG2RAD, FLOORS, FLOOR_HEIGHT_M, GOLD } from './constants';
import {
  appliquerPropositionOsm,
  appliquerSaisie,
  batimentPourId,
  hauteurExtrusion,
  idBatimentDuPan,
  mentionEtages,
  propositionOsm,
  type Batiment,
  type BatimentOsmServeur,
  type PropositionOsm,
} from './batiment'; // CALX100 — la hauteur vient du DOCUMENT, plus d'une Map locale
import { OBSTACLE_TYPES } from './types'; // ACAL1532 — la seule définition des types d'obstacle
import { etiquette, registreAtelier } from './numerotation'; // CALX111 câblage
import { $, esc } from './dom';
import { phraseCouleursAcces, poserLegendeAcces } from './legendeAcces'; // ACAL441, ACAL1821
import { signerSources, tableOmbrage, type TableOmbrage } from './tableOmbrage'; // ACAL459
import { facteurVueCiel, vueCielDuPan, type FacteurVueCiel } from './vueCiel'; // ACAL460
import { type Ctx } from './context';
import { redessinerSansReposer } from './panExistant'; // ACAL1900

export interface ShadingUiDeps {
  map: maplibregl.Map;
  setStatus: (msg: string) => void;
  /** Re-rend la zone active (3D + carte de résultat + fenêtre de production). */
  recalcDisplays: () => void;
  /** ACAL1900 — re-rend la pose TENUE telle quelle (layoutEditor.renderCustomLayout) : un changement d'ombrage la
   *  redessine sans la re-poser. Absent (site public) : `recalcDisplays`, comme avant. */
  renderPoseTenue?: () => void;
  /** WJ21 — applique la teinte d'accès solaire aux panneaux 3D (scene3d), ou l'efface
   *  (colorFor null). Injecté en wrapper paresseux (scene3d est construit après). */
  applyHeatmap: (colorFor: ((cellIndex: number) => { r: number; g: number; b: number }) | null) => void;
  /** CAL235 — RETIRE les modules proposés (geste EXPLICITE de l'utilisateur, annulable
   *  par Ctrl+Z comme le reste de l'atelier). Renvoie le nombre réellement retiré — 0 si
   *  le retrait n'est pas applicable, et alors RIEN ne change. Optionnel : absent, la
   *  proposition est affichée mais non applicable (l'écran le dit). */
  removePanels?: (cellIndexes: readonly number[]) => number;
}

export interface ShadingUi {
  /** Intercepte un clic carte quand le tracé d'ombre est actif. true = consommé. */
  handleMapClick: (lngLat: LngLat) => boolean;
  /** Recalcule hauteurs (hypothèse de prise de vue) + facteurs + affichages. */
  recomputeShading: () => void;
  /** ACAL1900 — redessine la zone active sans re-poser une pose tenue (soleil, bande climatique). */
  redessiner: () => void;
  /** ACAL27 — redessine liste + lignes des ombres tracées (après hydratation), sans recalcul. */
  rafraichirOmbres: () => void;
  /** WJ21 — ré-applique la heatmap d'accès solaire si elle est active (après un re-rendu
   *  qui a recréé les instances de panneaux). No-op si la heatmap est OFF. */
  refreshHeatmap: () => void;
  /** CAL97 — accès solaire CHIFFRÉ du pan actif (par module + agrégat), ou null quand
   *  aucune obstruction n'est renseignée : le chiffre est alors ABSENT, jamais estimé.
   *  Lu par les consommateurs (affichage, sérialisation CAL248). */
  solarAccess: () => SolarAccessSummary | null;
  /** ACAL138 — accès solaire ANNUEL sur les modules POSÉS donnés (valeur persistée). */
  solarAccessAnnuel: (points: readonly { x: number; y: number }[]) => SolarAccessSummary | null;
  /** ACAL726 — allume la carte d'accès (année entière) le temps de `fn`, puis la remet dans son état
   *  d'avant ; `null` sans source d'ombrage (rien à teinter : `fn` n'est pas appelée). */
  avecCarteDAcces: <T>(fn: () => Promise<T>) => Promise<T | null>;
  /** ACAL726 — méta de table d'ombrage du pan actif (`g` = sa géométrie vivante, ou `null`). */
  metaTableOmbrage: (g: { panels: ReadonlyArray<{ cx: number; cy: number }>; tiltDeg: number; azimuthDeg: number } | null) =>
    { shadeTableByZone: Record<string, TableOmbrage | null>; signatureOmbrage: string; skyViewByZone: Record<string, FacteurVueCiel | null> };
  /** ACAL459 — table d'ombrage direct par direction du soleil, sur les modules POSÉS donnés
   *  (`null` sans module ni obstruction) ; `signatureTable` = signature des sources qui la porte. */
  tableOmbrage: (points: readonly { x: number; y: number }[]) => TableOmbrage | null;
  signatureTable: () => string;
  /** ACAL460 — facteur de vue du ciel (diffus isotrope) du pan, sur les modules POSÉS (`null` sans module ni obstruction). */
  vueCiel: (points: readonly { x: number; y: number }[], penteDeg: number, azimutDeg: number) => FacteurVueCiel | null;
  /** Efface toutes les ombres tracées (« Effacer » / nouveau tracé). */
  reset: () => void;
  /** CAL93 — fixe (ou efface, `null`) le profil d'horizon lointain (CAL92 ou saisi),
   *  recalcule son dérate PROPRE (jamais mélangé à l'ombrage proche) et re-rend. */
  setHorizonProfile: (profile: import('../../lib/horizonEngine').HorizonProfile | null) => void;
  /** CAL93 — état courant du dérate d'horizon (pour l'écran/les tests) : `hasProfile`
   *  (au moins deux points exploitables), `maskedHours` (sur 12×24) et `annualFactor`
   *  (1 = aucun effet). */
  horizonStatus: () => { hasProfile: boolean; maskedHours: number; annualFactor: number };
  /** CALX122 — lecture géométrique d'ombrage PAR MODULE du pan actif, alignée sur
   *  `ctx.layoutPlan.grid.panels` : nombre d'heures représentatives masquées (sur les 288
   *  = 12 mois × 24 h de la matrice déjà calculée) et le premier mois concerné — jamais un
   *  kWh. `null` = ABSENT (aucune source d'ombrage saisie — jamais un « 0 heure » qui
   *  ferait croire à un calcul qui n'a pas eu lieu). */
  moduleShadeReadings: () => ModuleShadeReading[] | null;
  /** CALX122 — texte d'info-bulle prêt à afficher au survol d'UN module (`cellIndex`,
   *  même indexation que la heatmap WJ21/`buildHeatmapColorFn`). `null` si non calculable
   *  pour ce module (pan sans modules posés, indice hors plan). Le CÂBLAGE réel au survol
   *  3D reste un crochet attendu côté `scene3d.ts`/`roof-tool-pro11.ts` (hors périmètre). */
  moduleShadeTooltip: (cellIndex: number) => string | null;
  /**
   * CALX132 — reçoit l'empreinte OSM du bâtiment ACTIF (`batiment` de `GET crm/leads/<id>/
   * roof-footprint/`, contrat CALX106 `calepinage_empreinte_osm.json`) et affiche sa
   * PROPOSITION (jamais appliquée d'office) au panneau « Bâtiment ». `null`/absent efface
   * la proposition affichée. CROCHET ATTENDU : aucune page n'appelle encore cette méthode
   * aujourd'hui — `ToitureDesign.jsx` ne lit que `fp.data.polygon` de cette même réponse et
   * ignore `fp.data.batiment` (hors périmètre de cette lane, `roofPro11/batiment.ts`/
   * `batiment.test.ts` seuls).
   */
  setBatimentOsmPropose: (batiment: BatimentOsmServeur | null | undefined) => void;
  /** ACAL1405 — relit la hauteur, sa provenance et le panneau « Bâtiment » depuis le document (réouverture). */
  syncHeightUi: () => void;
}

/**
 * CALX132 — libellé FRANÇAIS du bouton de reprise, dérivé UNIQUEMENT des champs de la
 * proposition (jamais recalculé) : « Reprendre la hauteur OSM (7,5 m — openstreetmap, way
 * 123) », ou la variante « niveaux » quand OSM ne connaît que le nombre d'étages. Pure —
 * testée hors DOM dans `shadingUi.test.ts`.
 */
export function libelleBoutonOsm(p: PropositionOsm): string {
  const way = typeof p.osmWayId === 'number' ? `, way ${p.osmWayId}` : '';
  if (typeof p.hauteurM === 'number') {
    const h = p.hauteurM.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    return `Reprendre la hauteur OSM (${h} m — openstreetmap${way})`;
  }
  if (typeof p.etages === 'number') {
    return `Reprendre les niveaux OSM (${p.etages} — openstreetmap${way})`;
  }
  return 'Reprendre la proposition OSM';
}

const SHADE_SRC = 'rp9-shade-lines';

/**
 * CAL60 — hauteur de bâtiment EFFECTIVE (m) utilisée pour l'ombrage. `overrideM` est la
 * valeur SAISIE par l'utilisateur (ou null si aucune saisie) : finie et positive → elle
 * pilote le calcul ; sinon on retombe sur le repli HISTORIQUE (FLOORS × FLOOR_HEIGHT_M,
 * deux étages), affiché comme une HYPOTHÈSE — jamais une mesure. Pure, testable sans DOM.
 */
export function effectiveBuildingHeightM(overrideM: number | null | undefined): number {
  if (typeof overrideM === 'number' && Number.isFinite(overrideM) && overrideM > 0) return overrideM;
  return FLOORS * FLOOR_HEIGHT_M;
}

/**
 * CAL66 + CAL67 — SOURCE UNIFIÉE des obstructions d'ombrage. Jusqu'ici le dérate ne
 * lisait QUE les ombres tracées (WJ19) : une cheminée dessinée sur le toit avec sa
 * hauteur saisie (CAL66) et un arbre posé hors contour (CAL67) n'ombraient RIEN. Les
 * trois sources produisent désormais la MÊME forme (`ShadeObstructionENU`) et sont
 * concaténées ici, une fois pour toutes — `recomputeFactors` (production) comme
 * `buildHeatmapColorFn` (carte d'accès solaire) lisent cette unique liste.
 *
 * Référentiels (règle d'honnêteté, jamais un mélange silencieux) :
 *  - ombres tracées et objets d'environnement sont référencés au SOL → on leur retranche
 *    la hauteur du bâtiment (`roofHeightM`, saisie CAL60 ou hypothèse affichée) ;
 *  - un obstacle de TOITURE est déjà mesuré au-dessus du plan du champ → sa hauteur est
 *    prise telle quelle.
 *
 * Aucune source renseignée ⇒ liste vide ⇒ matrice d'ombrage inchangée (comportement
 * strictement identique à avant CAL66/CAL67). PURE : testable sans DOM ni carte.
 */
export function unifiedShadeEntries(
  shadeObstructions: readonly ShadeObstruction[] | null | undefined,
  obstacles: readonly Obstacle[] | null | undefined,
  environment: readonly EnvironmentObject[] | null | undefined,
  origin: LngLat,
  roofHeightM: number,
): ShadeObstructionENU[] {
  return [
    ...shadeObstructionsENU(shadeObstructions ?? [], origin, roofHeightM),
    ...roofObstacleShadeEntries(obstacles, origin),
    ...environmentShadeEntries(environment ?? [], origin, roofHeightM),
  ];
}

/**
 * ACAL26 — empreinte des SOURCES d'ombrage proche de la session : ombres tracées (pied et
 * bout — la hauteur s'en déduit), obstacles de toiture à hauteur saisie, objets
 * d'environnement. Tant qu'elle n'a pas bougé depuis l'ouverture, la matrice ENREGISTRÉE
 * du document (`ctx.ombrageEnregistre`) prime sur le recalcul : rouvrir un dossier ne fait
 * plus remonter la production en silence. PURE.
 */
export function signatureSourcesOmbrage(ctx: Pick<Ctx, 'shadeObstructions' | 'obstacles' | 'environment'>): string {
  return JSON.stringify({
    s: (ctx.shadeObstructions ?? []).map((o) => [o.id, o.base, o.tip, o.halfWidthM ?? null]),
    o: (ctx.obstacles ?? [])
      .filter((o) => typeof o.heightM === 'number' && o.heightM > 0)
      .map((o) => [o.id, o.centerLng, o.centerLat, o.lengthM, o.widthM, o.heightM, o.type ?? null]),
    e: ctx.environment ?? [],
  });
}

/**
 * ACAL27 — LE calcul de la matrice d'ombrage proche depuis les sources de la session
 * (ombres tracées + obstacles à hauteur + environnement), extrait de `recomputeFactors`
 * pour être rejoué hors DOM : une ombre tracée relue du document redonne la MÊME matrice.
 * Aucune source ou tracé ouvert ⇒ `null` (aucun dérate inventé). PURE.
 */
export function matriceOmbrageDesSources(
  ctx: Pick<Ctx, 'shadeObstructions' | 'obstacles' | 'environment' | 'centroid' | 'centroidLat' | 'vertices'>,
  roofHeightM: number,
  poses?: readonly { x: number; y: number }[],
): { factors: number[][] | null; entries: number } {
  const sources =
    (ctx.shadeObstructions ?? []).length > 0 ||
    (ctx.obstacles ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0) ||
    (ctx.environment ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0);
  if (!sources || (ctx.vertices ?? []).length < 3) return { factors: null, entries: 0 };
  const enu = unifiedShadeEntries(ctx.shadeObstructions, ctx.obstacles, ctx.environment, ctx.centroid, roofHeightM);
  if (!enu.length) return { factors: null, entries: 0 };
  // ACAL1407 (D-ACAL-83) — la MOYENNE des matrices des panneaux posés ; sans panneau, d'une grille du pan.
  const grille = poses?.length ? poses : grilleDuPan(ctx.vertices, ctx.centroid, enu);
  const mats = (grille.length ? grille : [{ x: 0, y: 0 }]).map((p) => hourlyShadeFactors(ctx.centroidLat, enu, p.x, p.y));
  // Couture ACAL1407 — la moyenne est arrondie comme le document l'enregistre (prefill.ts::serializeShading,
  // 3 décimales) : la production de la session est celle que le document rouvert recalcule, à l'identique.
  const moyenne = (m: number, h: number) => Math.round((mats.reduce((s, mat) => s + mat[m][h], 0) / mats.length) * 1000) / 1000;
  return { factors: mats[0].map((row, m) => row.map((_v, h) => moyenne(m, h))), entries: enu.length };
}

/** ACAL1407 — points d'une grille du pan (ENU autour de `origin`, ≈ 10 par côté, pas ≥ 1 m), hors des empreintes d'obstacle. */
function grilleDuPan(vertices: readonly LngLat[], origin: LngLat, exclus: readonly ShadeObstructionENU[]): { x: number; y: number }[] {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  const ring = vertices.map(([lng, lat]): [number, number] => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M]);
  const [xs, ys] = [ring.map((p) => p[0]), ring.map((p) => p[1])];
  const pas = Math.max(1, Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) / 10);
  const out: { x: number; y: number }[] = [];
  for (let x = Math.min(...xs) + pas / 2; x < Math.max(...xs); x += pas) {
    for (let y = Math.min(...ys) + pas / 2; y < Math.max(...ys); y += pas) {
      const libre = !exclus.some((o) => o.footprint && pointInPolygon([x, y], o.footprint as [number, number][]));
      if (libre && pointInPolygon([x, y], ring)) out.push({ x, y });
    }
  }
  return out;
}

/** ACAL1407 — les centres des modules POSÉS du pan actif (même règle que `serializeLayout`), ou `[]`. */
function pointsPosesDuPan(ctx: Pick<Ctx, 'freeMode' | 'freeState' | 'layoutPlan' | 'layoutState' | 'layoutOptimalCount'>): { x: number; y: number }[] {
  if (ctx.freeMode && ctx.freeState) return ctx.freeState.panels.map((p) => ({ x: p.cx, y: p.cy }));
  const cells = ctx.layoutPlan?.grid.panels ?? [];
  const occupes = ctx.layoutState && ctx.layoutState.cells.length === cells.length ? [...ctx.layoutState.occupied].sort((a, b) => a - b) : null;
  const rangs = occupes ?? Array.from({ length: Math.max(0, Math.min(cells.length, Math.round(ctx.layoutOptimalCount ?? 0))) }, (_, i) => i);
  return rangs.filter((i) => i >= 0 && i < cells.length).map((i) => ({ x: cells[i].cx, y: cells[i].cy }));
}

/** ACAL1407 — empreinte au centimètre d'une liste de modules posés. */
const empreinteDesPoses = (points: readonly { x: number; y: number }[]): string =>
  JSON.stringify(points.map((p) => [Math.round(p.x * 100), Math.round(p.y * 100)]));

/** CAL95 — noms des mois pour le sélecteur saisonnier de la carte d'accès solaire. */
export const HEATMAP_MONTH_LABELS: readonly string[] = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** Un point de module à évaluer pour la carte d'accès solaire (ENU, mètres). */
export interface HeatmapPoint {
  cx: number;
  cy: number;
}

/**
 * CAL95 — valeurs d'accès solaire (0–1) de chaque module, en lecture ANNUELLE (`month`
 * null, le défaut historique) ou pour UN MOIS donné (0 = janvier). Le mois n'ajoute
 * aucun modèle : c'est la MÊME intégrale horaire dératée, restreinte au jour-type PVGIS
 * du mois — décembre (soleil bas, ombres longues) sort donc plus rouge que juin sans
 * qu'aucun coefficient saisonnier ne soit inventé.
 *
 * Aucune obstruction → tout à 1 (plein soleil uniforme) : la carte est verte partout,
 * ce qui est la lecture honnête d'un toit sans obstruction renseignée. PURE.
 */
export function heatmapAccessValues(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  panels: readonly HeatmapPoint[],
  month: number | null,
): number[] {
  if (!obstructions.length) return panels.map(() => 1);
  return panels.map((p) =>
    month == null
      ? pointSolarAccess(latitudeDeg, obstructions, prod, p.cx, p.cy)
      : pointSolarAccessMonth(latitudeDeg, obstructions, prod, p.cx, p.cy, month),
  );
}

// ═══════════ CALX122 — LECTURE GÉOMÉTRIQUE D'OMBRAGE PAR MODULE ═══════════
// Jusqu'ici la matrice 12 × 24 (`hourlyShadeFactors`/`ctx.shadeFactors`, prefill.ts:
// 375-408) ne disait QUE de combien la production était rabotée (`heatmapAccessValues`,
// `solarAccessSummary`) — jamais COMBIEN d'heures représentatives une obstruction couvre
// réellement un module donné, ni depuis quel mois. Cette lecture réutilise la MÊME
// matrice, évaluée à la position du module plutôt qu'au centroïde, et se contente de
// COMPTER les cellules masquées : aucun kWh n'est lu ni produit ici.

/** CALX122 — lecture géométrique d'un module : heures masquées + premier mois concerné. */
export interface ModuleShadeReading {
  /** Nombre d'heures représentatives masquées, sur les 288 (12 mois × 24 h) de la
   *  matrice — même unité que le dérate d'horizon lointain (CAL93, « heure(s) sur 288 »). */
  maskedHours: number;
  /** Premier mois (0 = janvier) où au moins une heure est masquée, ou `null` si aucune
   *  (obstruction(s) saisie(s) mais hors de la trajectoire solaire de ce module — un vrai
   *  zéro géométrique, jamais une absence de lecture). */
  firstMonthIndex: number | null;
}

/**
 * CALX122 — lecture géométrique PURE d'un point (cx, cy) : recalcule SA PROPRE matrice
 * 12 × 24 (`hourlyShadeFactors`, évaluée à sa position) et compte les cellules masquées
 * (facteur < 1). Aucune obstruction ⇒ matrice inchangée ⇒ 0 heure, aucun mois — un vrai
 * zéro, distinct de l'ABSENCE de lecture publiée par `moduleShadeReadingsForPanels`
 * quand aucune source n'a été saisie du tout. PURE : testable sans DOM ni carte.
 */
export function moduleShadeReading(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  cx: number,
  cy: number,
): ModuleShadeReading {
  const matrix = hourlyShadeFactors(latitudeDeg, obstructions, cx, cy);
  let maskedHours = 0;
  let firstMonthIndex: number | null = null;
  matrix.forEach((row, m) => {
    let maskedInMonth = 0;
    for (const v of row) if (v < 1) maskedInMonth++;
    if (maskedInMonth > 0) {
      maskedHours += maskedInMonth;
      if (firstMonthIndex == null) firstMonthIndex = m;
    }
  });
  return { maskedHours, firstMonthIndex };
}

/**
 * CALX122 — lecture géométrique de CHAQUE module d'un pan. `hasSource` distingue « rien à
 * publier » d'un « vrai zéro » : sans AUCUNE source d'ombrage saisie (`false`), le
 * résultat est `null` — le compte est ABSENT, jamais un « 0 heure » qui ferait croire à
 * un calcul qui n'a pas eu lieu. Une source saisie (`true`) publie systématiquement un
 * compte par module, même à 0 (obstruction sous le niveau du toit ou hors trajectoire
 * solaire — cf. `moduleShadeReading`). PURE : testable sans DOM ni carte.
 */
export function moduleShadeReadingsForPanels(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  panels: readonly HeatmapPoint[],
  hasSource: boolean,
): ModuleShadeReading[] | null {
  if (!hasSource) return null;
  return panels.map((p) => moduleShadeReading(latitudeDeg, obstructions, p.cx, p.cy));
}

/** Item 14 (T4-U1-023) — la phrase « Ombrage par module » sur les panneaux POSÉS seulement : les cellules rendues
 *  (`indicesPoses`, ordre du rendu 3D), sinon les `count` premières cellules du pavage — la même règle que
 *  `scene3d.ts` pour choisir les cellules posées. Avant : toutes les cellules du pavage (« 3 module(s) sur 6 » pour 3
 *  panneaux posés). `null` quand aucun panneau n'est posé. */
export function phraseOmbrageParModule(
  lectures: readonly ModuleShadeReading[],
  indicesPoses: readonly number[] | null | undefined,
  count: number,
): string | null {
  const posees = indicesPoses && indicesPoses.length
    ? indicesPoses.map((i) => lectures[i]).filter((r): r is ModuleShadeReading => Boolean(r))
    : lectures.slice(0, Math.max(0, count));
  if (!posees.length) return null;
  const shaded = posees.filter((r) => r.maskedHours > 0);
  if (!shaded.length) {
    return `Ombrage par module (lecture géométrique, ${posees.length} module(s)) : aucune heure masquée — `
      + 'les obstructions renseignées ne couvrent la trajectoire solaire d’aucun module.';
  }
  const hours = shaded.map((r) => r.maskedHours);
  const firstMonths = shaded.map((r) => r.firstMonthIndex).filter((m): m is number => m != null);
  const earliestMonth = firstMonths.length ? Math.min(...firstMonths) : null;
  return 'Ombrage par module (lecture géométrique, sur 288 heures représentatives = 12 mois × 24 h) : '
    + `${shaded.length} module(s) sur ${posees.length} couvert(s) par une obstruction, de ${Math.min(...hours)} à ${Math.max(...hours)} heure(s)`
    + (earliestMonth != null ? `, dès ${HEATMAP_MONTH_LABELS[earliestMonth]}` : '')
    + '. Aucune production n’est calculée ici.';
}

// ═══════ CALX115 — SEUIL D'ACCÈS SOLAIRE : ÉCARTER DES EMPLACEMENTS, PAS DÉRATER ═══════
// Jusqu'ici l'ombrage n'agissait QU'APRÈS la pose : la proposition de retrait
// (`proposeShadedRemoval`, plus bas) attend que les modules soient posés puis attend un
// clic. Le seuil d'Aurora (`irradiance_constraints.min_sap` / `min_tsrf`) fait l'inverse :
// un emplacement dont l'accès solaire calculé est sous le seuil n'est PAS un emplacement,
// il sort du posable AVANT que le pavage ne le retienne. Le seuil est SAISI
// (`optimisation.seuilAccesSolaire`, contrat CALX88) : rien n'est proposé par défaut.
//
// DEUX RÈGLES TIENNENT CE BLOC :
//  1. Aucun seuil saisi (ou seuil à 0) ⇒ AUCUN emplacement écarté : la pose est celle
//     d'aujourd'hui, à l'emplacement près, et la phrase le dit.
//  2. Un seuil ne s'applique JAMAIS sans mesure. Sans obstruction retenue, la carte
//     d'accès solaire vaut 1 partout (`heatmapAccessValues`) — c'est l'ABSENCE de mesure,
//     pas du plein soleil : le seuil est alors REFUSÉ en nommant `optimisation.seuilAccesSolaire`
//     et la raison, jamais appliqué à des valeurs qui n'ont rien mesuré (D-CALX 7).

/** Le champ du contrat v2 que les refus de seuil NOMMENT (CALX88). */
const CHAMP_SEUIL = 'optimisation.seuilAccesSolaire';

/** CALX115 — ce que le seuil a RÉELLEMENT fait au posable, et pourquoi. */
export interface FiltrageAccesSolaire {
  /** Rangs (dans `panels`) des emplacements RETENUS pour le pavage. */
  retenus: number[];
  /** Rangs ÉCARTÉS : leur accès solaire CALCULÉ est sous le seuil. */
  ecartes: number[];
  /** Le seuil réellement appliqué (0–1), ou `null` quand aucun ne l'a été. */
  seuilApplique: number | null;
  /** Vrai quand un seuil SAISI a dû être écarté (hors contrat, ou sans mesure). */
  refuse: boolean;
  /** Le champ du contrat nommé par le refus, ou `null`. */
  champ: string | null;
  /** Phrase FR à publier : elle dit COMBIEN d'emplacements sont écartés, ou pourquoi
   *  aucun ne l'est — jamais un silence. */
  motif: string;
}

/** Part d'accès solaire en français (« 70 % »), sans chiffre inventé : c'est la valeur
 *  saisie ou calculée, seulement mise en forme. */
function pctAcces(v: number): string {
  return `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;
}

/** Tous les emplacements retenus, aucun écarté — la pose d'aujourd'hui. */
function toutRetenu(nombre: number, motif: string, refuse = false, champ: string | null = null): FiltrageAccesSolaire {
  return {
    retenus: Array.from({ length: Math.max(0, nombre) }, (_, i) => i),
    ecartes: [],
    seuilApplique: null,
    refuse,
    champ,
    motif,
  };
}

/**
 * CALX115 — quels emplacements restent POSABLES sous le seuil d'accès solaire SAISI ? PURE.
 *
 * `seuilSaisi` arrive du document (`optimisation.seuilAccesSolaire`, CALX88) : c'est un
 * `unknown`, jamais un nombre du code. `mesureDisponible` dit si une source d'ombrage a
 * seulement été saisie (l'équivalent de `hasShadeSources()`), et `obstructions` ce qu'il
 * en RESTE une fois ramené au plan du champ : les deux doivent tenir, sinon rien n'est
 * mesuré et le seuil est refusé en le disant.
 *
 * L'accès solaire est lu en ANNUEL (`heatmapAccessValues`, mois `null`) — la même intégrale
 * horaire dératée que la carte d'accès solaire WJ21/CAL95, aucun modèle nouveau.
 */
export function filtrerEmplacementsSousSeuil(
  seuilSaisi: unknown,
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  panels: readonly HeatmapPoint[],
  mesureDisponible: boolean,
): FiltrageAccesSolaire {
  const total = panels.length;
  if (seuilSaisi == null || seuilSaisi === '') {
    return toutRetenu(
      total,
      `Aucun seuil d’accès solaire saisi (« ${CHAMP_SEUIL} » absente) : aucun emplacement n’est écarté, la pose est celle d’aujourd’hui.`,
    );
  }
  if (typeof seuilSaisi !== 'number' || !Number.isFinite(seuilSaisi) || seuilSaisi < 0 || seuilSaisi > 1) {
    return toutRetenu(
      total,
      `« ${CHAMP_SEUIL} » : « ${String(seuilSaisi)} » n’est pas une part d’accès solaire entre 0 et 1 — ` +
        `le seuil est écarté et aucun emplacement n’est retiré du posable.`,
      true,
      CHAMP_SEUIL,
    );
  }
  if (seuilSaisi === 0) {
    // Seuil à 0 : aucun accès solaire ne peut lui être inférieur. On le dit plutôt que de
    // lancer un calcul dont le résultat est connu — et la pose reste celle d'aujourd'hui.
    return {
      ...toutRetenu(total, `Seuil d’accès solaire à ${pctAcces(0)} : aucun emplacement n’est sous le seuil, la pose est celle d’aujourd’hui.`),
      seuilApplique: 0,
    };
  }
  if (!mesureDisponible) {
    return toutRetenu(
      total,
      `Seuil d’accès solaire de ${pctAcces(seuilSaisi)} écarté : aucune obstruction, aucun obstacle et aucun objet ` +
        `d’environnement à hauteur saisie sur ce toit — aucun accès solaire n’y est calculé, et une mesure absente ` +
        `ne vaut pas du plein soleil. Aucun emplacement n’est écarté.`,
      true,
      CHAMP_SEUIL,
    );
  }
  if (!obstructions.length) {
    return toutRetenu(
      total,
      `Seuil d’accès solaire de ${pctAcces(seuilSaisi)} écarté : aucune des sources d’ombrage saisies ne dépasse le ` +
        `plan du champ, donc aucun accès solaire n’est calculé ici — une mesure absente ne vaut pas du plein soleil. ` +
        `Aucun emplacement n’est écarté.`,
      true,
      CHAMP_SEUIL,
    );
  }
  if (!total) {
    return {
      ...toutRetenu(0, `Seuil d’accès solaire de ${pctAcces(seuilSaisi)} : aucun emplacement à évaluer sur ce pan.`),
      seuilApplique: seuilSaisi,
    };
  }
  const acces = heatmapAccessValues(latitudeDeg, obstructions, prod, panels, null);
  const retenus: number[] = [];
  const ecartes: number[] = [];
  acces.forEach((a, i) => (a < seuilSaisi ? ecartes : retenus).push(i));
  return {
    retenus,
    ecartes,
    seuilApplique: seuilSaisi,
    refuse: false,
    champ: null,
    motif: ecartes.length
      ? `Seuil d’accès solaire de ${pctAcces(seuilSaisi)} : ${ecartes.length} emplacement(s) sur ${total} écarté(s) ` +
        `du posable avant le pavage (accès solaire calculé sous le seuil).`
      : `Seuil d’accès solaire de ${pctAcces(seuilSaisi)} : aucun des ${total} emplacements n’est sous le seuil — ` +
        `la pose est celle d’aujourd’hui.`,
  };
}

/** ACAL497 — la ligne de la liste des ombres : une hauteur DÉDUITE de l'ombre et du soleil déclaré se dit « à confirmer ». */
export function libelleLigneOmbre(rang: number, ombreM: number, hauteurM: number): string {
  const un = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `Ombre ${rang} : ombre ${un(ombreM)} m → hauteur estimée ~${un(hauteurM)} m — à confirmer (déduite de l’ombre et du soleil déclaré)`;
}

/**
 * CALX115 — hauteur de bâtiment EFFECTIVE (m) du pan, pour l'ombrage. Exportée pour que
 * l'optimiseur lise EXACTEMENT la même hauteur que l'atelier (`roofHeightM` ci-dessous
 * l'appelle) : une seule règle de hauteur, jamais deux qui dérivent. Hauteur SAISIE du
 * bâtiment du document (CALX100) si elle existe, sinon l'hypothèse affichée (CAL60).
 */
export function hauteurToitPourOmbrageM(
  batiments: readonly Batiment[] | null | undefined,
  buildingId: string | null | undefined,
): number {
  const lu = hauteurExtrusion(batimentPourId(batiments, idBatimentDuPan(buildingId)));
  return effectiveBuildingHeightM(lu.origine === 'saisie' ? lu.hauteurM : null);
}

/** ACAL726 — exécute `fn` avec la carte d'accès allumée en année entière, puis la remet dans son état
 *  d'avant (éteinte, avec son mois) ; déjà allumée, elle reste telle quelle. Sans source d'ombrage : `null`. */
export async function executerAvecCarte<T>(
  etat: { on: boolean; mois: number | null },
  appliquer: (on: boolean, mois: number | null) => void,
  sources: boolean,
  fn: () => Promise<T>,
): Promise<T | null> {
  if (!sources) return null;
  if (etat.on) return fn();
  appliquer(true, null);
  try {
    return await fn();
  } finally {
    appliquer(false, etat.mois);
  }
}

/**
 * ACAL1532 — qui fait l'ombre, en mots : « de la cheminée » (un type), « de la cheminée et du climatiseur » (deux),
 * sinon « des obstacles du toit ». Les ombres tracées / objets d'environnement ne se nomment pas : « des ombres relevées ».
 * `null` quand rien ne fait d'ombre. PURE.
 */
export function designationDeLOmbre(
  obstacles: readonly { type?: string; heightM?: number }[] | null | undefined,
  nbOmbresTracees = 0,
  environnement: readonly { heightM?: number; supposeCoupe?: boolean }[] | null | undefined = [],
): string | null {
  const hauts = (obstacles ?? []).filter((o) => typeof o.heightM === 'number' && o.heightM > 0);
  const autres = nbOmbresTracees > 0 || (environnement ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0 && o.supposeCoupe !== true);
  if (!hauts.length) return autres ? 'des ombres relevées' : null;
  if (autres) return 'des obstacles du toit et des ombres relevées';
  const noms = [...new Set(hauts.map((o) => (o.type ? OBSTACLE_TYPES.find((t) => t.id === o.type)?.de : undefined) ?? 'de l’obstacle'))];
  return noms.length === 1 ? noms[0] : noms.length === 2 ? `${noms[0]} et ${noms[1]}` : 'des obstacles du toit';
}

/** ACAL729 — le début de l'info-bulle d'un module : « Accès solaire 82 % (année entière) · chaîne 2 · », ou rien. */
export function teteInfoBulleModule(acces: number | null, chaine: string | null): string {
  const morceaux = [
    acces == null ? null : `Accès solaire ${(acces * 100).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} % (année entière)`,
    chaine,
  ].filter((m): m is string => !!m);
  return morceaux.length ? `${morceaux.join(' · ')} · ` : '';
}

/** ACAL714 — le seuil de retrait réglé par la société : un nombre fini dans [0, 1], sinon `null`. */
export function seuilRetraitDesReglages(reglages: { simulation?: unknown } | null | undefined): number | null {
  const sim = reglages?.simulation as { seuil_acces_retrait?: { valeur?: unknown } | null } | null | undefined;
  const v = sim?.seuil_acces_retrait?.valeur;
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1 ? v : null;
}

const pctFr = (v: number) => `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;

const estSeuil = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1;

/** ACAL548 — le seuil EFFECTIF : la valeur de CE dossier si elle existe, sinon le réglage de la société, sinon `null`. */
export function seuilEffectifAccesSolaire(
  valeurDossier: unknown,
  reglages: { simulation?: unknown } | null | undefined,
): { valeur: number; origine: 'dossier' | 'societe' } | null {
  if (estSeuil(valeurDossier)) return { valeur: valeurDossier, origine: 'dossier' };
  const societe = seuilRetraitDesReglages(reglages);
  return societe == null ? null : { valeur: societe, origine: 'societe' };
}

/** ACAL548 — la phrase qui dit d'où vient le seuil (jamais écrite si aucune valeur n'existe). */
export function phraseOrigineSeuil(valeurDossier: unknown, reglages: { simulation?: unknown } | null | undefined): string {
  const societe = seuilRetraitDesReglages(reglages);
  const lSociete = societe == null ? '' : `réglage de votre société : ${pctFr(societe)}`;
  if (!estSeuil(valeurDossier)) return lSociete;
  const lDossier = `valeur de ce dossier : ${pctFr(valeurDossier)}`;
  return lSociete ? `${lDossier} — ${lSociete}` : lDossier;
}

export type SeuilSaisi = { ok: true; valeur: number | null } | { ok: false; erreur: string };

/** ACAL548 — lit le champ « Accès solaire minimal (%) » : « 80 » ⇒ 0,8 ; vide ⇒ `null` (clé retirée) ;
 *  un texte non numérique ou hors 0 à 100 est REFUSÉ en le disant, jamais corrigé. */
export function lireSeuilSaisi(texte: string): SeuilSaisi {
  const t = texte.trim().replace(',', '.');
  if (t === '') return { ok: true, valeur: null };
  const n = /^\d+(\.\d+)?$/.test(t) ? Number(t) : NaN;
  if (!Number.isFinite(n) || n < 0 || n > 100) return { ok: false, erreur: 'Saisissez un nombre entre 0 et 100' };
  return { ok: true, valeur: n / 100 };
}

/** ACAL714 — le bloc « proposition de retrait » (CAL235) ; sans seuil réglé il dit où le régler, sans bouton. */
export function htmlProposition(
  proposal: ShadeRemovalProposal | null,
  seuil: number | null,
  peutRetirer: boolean,
  modulesVises: string,
  origine: 'dossier' | 'societe' = 'societe',
): string {
  if (seuil == null) {
    return '<div class="mt-1 opacity-80">Retrait proposé : aucun seuil réglé par votre société (Réglages › simulation).</div>';
  }
  if (!proposal) return '';
  return `<div class="mt-2 border border-white/10 bg-nuit-900/40 p-2">` +
    `<div><span class="font-semibold text-white">Proposition</span> — retirer les ` +
    `<span class="fig">${proposal.count}</span> module(s) dont l’accès solaire est sous ` +
    `${esc(pctFr(proposal.threshold))} (${origine === 'dossier' ? `seuil de ce dossier (${esc(pctFr(proposal.threshold))})` : 'seuil de votre société'}) : <span class="fig">−${esc(proposal.kwcLost.toLocaleString('fr-FR', { maximumFractionDigits: 2 }))}</span> kWc, ` +
    `accès solaire moyen des ${proposal.remaining} restants ` +
    `<span class="fig">${esc(pctFr(proposal.averageBefore))}</span> → <span class="fig">${esc(pctFr(proposal.averageAfter))}</span>.</div>` +
    `<div class="mt-1 opacity-80">Modules visés : ${esc(modulesVises)}.</div>` + // CALX111 câblage
    (peutRetirer
      ? `<button type="button" id="rp9-solar-access-apply" class="mt-2 border border-white/20 px-2 py-1 font-semibold text-white hover:bg-white/10">Retirer ces modules</button>` +
        `<span class="ml-2 opacity-80">Rien n’est retiré tant que vous ne cliquez pas ; Ctrl+Z annule.</span>`
      : '<div class="mt-1 opacity-80">Retrait non applicable sur cet écran — la proposition reste informative.</div>')
    + '</div>';
}

export function createShadingUi(ctx: Ctx, deps: ShadingUiDeps): ShadingUi {
  const { map, setStatus, applyHeatmap } = deps;
  // ACAL1900 — l'ombrage (relu au boot, hauteur, horizon, effacement) REDESSINE : une pose tenue n'est pas re-posée.
  // Seul le seuil d'accès solaire (qui écarte des emplacements) re-résout (`deps.recalcDisplays`).
  const recalcDisplays = () => redessinerSansReposer(ctx, deps.recalcDisplays, deps.renderPoseTenue);

  const addBtn = $<HTMLButtonElement>('rp9-shade-add');
  const clearBtn = $<HTMLButtonElement>('rp9-shade-clear');
  const hourEl = $<HTMLInputElement>('rp9-shade-hour');
  const hourValueEl = $('rp9-shade-hour-value');
  const listEl = $('rp9-shade-list');
  const noteEl = $('rp9-shade-note');
  // CAL60 + CALX100 — hauteur de bâtiment SAISISSABLE (par bâtiment CAL59 : la zone active
  // porte celle de SON bâtiment). CE QUI CHANGE AVEC CALX100 : elle ne vit PLUS dans une
  // `Map` locale jamais sérialisée — elle vit dans `ctx.batiments` (`buildings[]` du
  // document, contrat CALX84), elle y RETOURNE à chaque saisie avec sa provenance, et elle
  // survit donc au rechargement du dossier. Sans saisie, la 3D reste sur la hauteur de
  // DESSIN annoncée (`batiment.ts`), exactement l'hypothèse affichée d'aujourd'hui.
  const heightEl = $<HTMLInputElement>('rp9-shade-height');
  const heightNoteEl = $('rp9-shade-height-note');
  const buildingKey = (): string => idBatimentDuPan(ctx.activeArea()?.buildingId);
  const batimentActif = (): Batiment | null => batimentPourId(ctx.batiments, buildingKey());
  /** Hauteur EFFECTIVE (m) de la zone active — saisie si présente, sinon l'hypothèse.
   *  CALX115 — une SEULE règle de hauteur, partagée avec l'optimiseur. */
  const roofHeightM = (): number => hauteurToitPourOmbrageM(ctx.batiments, ctx.activeArea()?.buildingId);
  function syncHeightUi() {
    const bat = batimentActif();
    const lu = hauteurExtrusion(bat);
    const override = lu.origine === 'saisie' ? lu.hauteurM : null;
    if (heightEl && document.activeElement !== heightEl) heightEl.value = override != null ? fmt1(override) : '';
    if (heightNoteEl) heightNoteEl.textContent = lu.mention;
    syncPanneauBatiment(bat);
  }

  // ═══ CALX100 — PANNEAU « BÂTIMENT » (créé par le module, pas par la page hôte) ═══
  // La page ne fournit que le champ de hauteur CAL60 (`rp9-shade-height`). Les autres
  // champs du bâtiment — nombre d'étages, hauteur d'étage, PROVENANCE de la hauteur, et
  // le relevé d'acrotère de CALX101 — sont créés ici s'ils manquent, patron
  // `ensureAccessBlock`/`obstaclesUi.ts` : AUCUNE page à modifier, et absent de tout DOM
  // (harness jsdom minimal) tout ce bloc est un no-op.
  const panneauBatiment = ensurePanneauBatiment();
  const batEtagesEl = $<HTMLInputElement>('rp11-bat-etages');
  const batHauteurEtageEl = $<HTMLInputElement>('rp11-bat-hauteur-etage');
  const batSourceEl = $<HTMLInputElement>('rp11-bat-source');
  const batAcrotereEl = $<HTMLInputElement>('rp11-bat-acrotere');
  const batErreurEl = $('rp11-bat-erreur');
  const batNoteEl = $('rp11-bat-note');
  // CALX132 — la PROPOSITION OSM affichée (jamais écrite tant que le bouton n'est pas
  // cliqué) : `null` = rien à proposer (aucun tag OSM exploitable, ou pas encore reçue —
  // voir le crochet attendu sur `setBatimentOsmPropose`, interface `ShadingUi`).
  const batOsmBoutonEl = $<HTMLButtonElement>('rp11-bat-osm-bouton');
  const batOsmNoteEl = $('rp11-bat-osm-note');
  let propositionOsmCourante: PropositionOsm | null = null;

  function ensurePanneauBatiment(): HTMLElement | null {
    const existing = $('rp11-batiment');
    if (existing) return existing;
    const anchor = heightNoteEl?.parentElement ?? heightEl?.parentElement;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const box = document.createElement('div');
    box.id = 'rp11-batiment';
    box.className = 'mt-2 space-y-1 text-xs text-lune-soft';
    const champ = (id: string, label: string, aide: string, type = 'number', step = '0.1') =>
      `<label class="block"><span class="text-lune-faint">${esc(label)}</span>
        <input id="${id}" type="${type}"${type === 'number' ? ` step="${step}" min="0"` : ''}
          class="mt-0.5 w-full rounded border border-white/20 bg-nuit-900/60 px-2 py-1 text-xs text-lune-soft"
          placeholder="${esc(aide)}" /></label>`;
    box.innerHTML = [
      '<p class="text-lune-faint">Bâtiment — ce qui est SAISI ici voyage avec le dossier ; ce qui est vide reste vide.</p>',
      champ('rp11-bat-source', 'Provenance de la hauteur', 'mesurée au télémètre, lue sur le permis…', 'text'),
      champ('rp11-bat-etages', 'Nombre d’étages (information d’écran)', 'non renseigné', 'number', '1'),
      champ('rp11-bat-hauteur-etage', 'Hauteur d’un étage (m)', 'non renseignée'),
      champ('rp11-bat-acrotere', 'Relevé d’acrotère (m)', 'non renseigné'),
      '<p id="rp11-bat-note" class="text-lune-faint"></p>',
      '<p id="rp11-bat-erreur" class="text-alert-300"></p>',
      // CALX132 — PROPOSITION OSM : masquée (aucun texte, aucun bouton visible) tant
      // qu'aucune empreinte n'a été reçue (`setBatimentOsmPropose`) — jamais affichée par
      // défaut, jamais appliquée sans ce clic.
      '<p id="rp11-bat-osm-note" class="text-lune-faint"></p>',
      '<button type="button" id="rp11-bat-osm-bouton" hidden ' +
        'class="border border-white/20 px-2 py-1 font-semibold text-white hover:bg-white/10"></button>',
    ].join('');
    anchor.appendChild(box);
    return box;
  }

  /** Remet les champs du panneau sur ce que le DOCUMENT porte (jamais l'inverse). */
  function syncPanneauBatiment(bat: Batiment | null) {
    if (!panneauBatiment) return;
    const poser = (el: HTMLInputElement | null, v: number | null | undefined, entier = false) => {
      if (!el || document.activeElement === el) return;
      el.value = typeof v === 'number' && Number.isFinite(v) && v > 0 ? (entier ? String(Math.round(v)) : fmt1(v)) : '';
    };
    poser(batEtagesEl, bat?.etages, true);
    poser(batHauteurEtageEl, bat?.hauteurEtageM);
    poser(batAcrotereEl, bat?.hauteurAcrotereM);
    if (batSourceEl && document.activeElement !== batSourceEl) batSourceEl.value = bat?.source ?? '';
    if (batNoteEl) batNoteEl.textContent = mentionEtages(bat) ?? '';
    renderPropositionOsm();
  }

  /**
   * CALX132 — affiche (ou masque) le bouton de reprise de la proposition OSM courante.
   * Rien n'est écrit ici : ce n'est qu'un RENDU, la seule écriture possible est le clic
   * (`appliquerPropositionOsmActive`).
   */
  function renderPropositionOsm() {
    if (batOsmNoteEl) batOsmNoteEl.textContent = propositionOsmCourante?.mention ?? '';
    if (batOsmBoutonEl) {
      if (propositionOsmCourante) {
        batOsmBoutonEl.hidden = false;
        batOsmBoutonEl.textContent = libelleBoutonOsm(propositionOsmCourante);
      } else {
        batOsmBoutonEl.hidden = true;
        batOsmBoutonEl.textContent = '';
      }
    }
  }

  /**
   * CALX132 — CLIC EXPLICITE : la proposition OSM courante est acceptée et rejoint le
   * document, par le même chemin qu'une saisie humaine (`appliquerSaisie`, mêmes refus
   * nommés). Rien de ceci ne s'exécute ailleurs qu'ici — le calcul de la proposition
   * (`setBatimentOsmPropose`) n'écrit jamais tout seul.
   */
  function appliquerPropositionOsmActive() {
    if (!propositionOsmCourante) return;
    const res = appliquerPropositionOsm(ctx.batiments, buildingKey(), propositionOsmCourante);
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme toute saisie de bâtiment
    ctx.batiments = res.batiments;
    if (batErreurEl) batErreurEl.textContent = res.refus.map((r) => r.message).join(' ');
    syncHeightUi();
    recalcDisplays();
    if (hasShadeSources()) recomputeShading();
  }
  batOsmBoutonEl?.addEventListener('click', () => appliquerPropositionOsmActive());

  /** Nombre saisi à la française (virgule tolérée) ; vide/illisible → `null` = EFFACER. */
  function nombreSaisi(el: HTMLInputElement | null): number | null {
    const raw = (el?.value ?? '').replace(/\s/g, '').replace(',', '.').trim();
    if (!raw) return null;
    const v = Number(raw);
    return Number.isFinite(v) && v > 0 ? v : null;
  }

  /**
   * CALX100 — écrit la saisie dans `ctx.batiments` (le DOCUMENT), puis re-synchronise.
   * Un refus n'efface rien en silence : il s'affiche SOUS le champ fautif et le bandeau
   * le NOMME (règle fondateur 08/09), la valeur d'avant restant en place.
   */
  function appliquerSaisieBatiment() {
    const res = appliquerSaisie(ctx.batiments, buildingKey(), {
      hauteurM: nombreSaisi(heightEl),
      etages: nombreSaisi(batEtagesEl),
      hauteurEtageM: nombreSaisi(batHauteurEtageEl),
      hauteurAcrotereM: nombreSaisi(batAcrotereEl),
      source: batSourceEl?.value ?? null,
    });
    ctx.pushWorkshopHistory?.(); // CAL100 — la saisie du bâtiment s'annule comme le reste
    ctx.batiments = res.batiments;
    if (batErreurEl) batErreurEl.textContent = res.refus.map((r) => r.message).join(' ');
    if (res.refus.length) {
      setStatus('Hauteur non enregistrée — champ « Provenance de la hauteur » à renseigner.');
      batSourceEl?.focus?.();
    }
    syncHeightUi();
    recalcDisplays(); // la 3D extrude désormais cette hauteur : elle doit se re-dessiner
    if (hasShadeSources()) recomputeShading();
  }
  // CAL93 — note du dérate d'horizon LOINTAIN (optionnelle, DOM créé par HorizonPanel/la
  // page hôte ; absente en tests unitaires du builder — no-op).
  const horizonNoteEl = $('rp9-horizon-note');
  // WJ21 — carte d'accès solaire (heatmap d'irradiance).
  const heatmapBtn = $<HTMLButtonElement>('rp9-heatmap-toggle');
  const heatmapNoteEl = $('rp9-heatmap-note');
  // CAL97 — bloc où l'accès solaire CHIFFRÉ est publié (créé s'il manque dans la page).
  const accessEl = ensureAccessBlock();
  function ensureAccessBlock(): HTMLElement | null {
    const existing = $('rp9-solar-access');
    if (existing) return existing;
    const anchor = heatmapNoteEl?.parentElement ?? heatmapBtn?.parentElement;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const box = document.createElement('div');
    box.id = 'rp9-solar-access';
    box.className = 'mt-2 text-xs text-lune-soft';
    anchor.appendChild(box);
    return box;
  }
  // CALX122 — bloc où la lecture géométrique d'ombrage PAR MODULE (heures masquées +
  // premier mois) est publiée, juste sous l'accès solaire chiffré (CAL97) — créé s'il
  // manque dans la page (même patron que `ensureAccessBlock`).
  const shadeHoursEl = ensureShadeHoursBlock();
  function ensureShadeHoursBlock(): HTMLElement | null {
    const existing = $('rp9-shade-hours');
    if (existing) return existing;
    const anchor = accessEl?.parentElement ?? heatmapNoteEl?.parentElement ?? heatmapBtn?.parentElement;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const box = document.createElement('div');
    box.id = 'rp9-shade-hours';
    box.className = 'mt-2 text-xs text-lune-soft';
    anchor.appendChild(box);
    return box;
  }
  let heatmapOn = false;
  // CAL95 — LECTURE SAISONNIÈRE de la carte : null = annuel (le défaut historique),
  // 0–11 = un mois. Le sélecteur est créé ici s'il n'existe pas déjà dans la page (même
  // patron que le sélecteur de type d'obstacle, PV61) — aucune page n'a à être modifiée.
  let heatmapMonth: number | null = null;
  const heatmapMonthEl = ensureHeatmapMonthPicker();
  function ensureHeatmapMonthPicker(): HTMLSelectElement | null {
    const existing = $<HTMLSelectElement>('rp9-heatmap-month');
    if (existing) return existing;
    if (!heatmapBtn?.parentElement || typeof document.createElement !== 'function') return null;
    const select = document.createElement('select');
    select.id = 'rp9-heatmap-month';
    select.className = 'rp9-input';
    select.setAttribute('aria-label', 'Période de la carte d’accès solaire');
    const annual = document.createElement('option');
    annual.value = '';
    annual.textContent = 'Année entière';
    select.appendChild(annual);
    HEATMAP_MONTH_LABELS.forEach((label, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = label.charAt(0).toUpperCase() + label.slice(1);
      select.appendChild(opt);
    });
    heatmapBtn.parentElement.appendChild(select);
    return select;
  }

  // — Hypothèse du moment de prise de vue (jour de l'année + heure solaire) —
  // ACAL496 — la date est celle SAISIE (ACAL509), l'heure celle saisie ici : jamais une valeur supposée.
  let imageryHour: number | null = null;

  // — Tracé en cours : null = inactif ; sinon le pied déjà posé (ou null en attente) —
  let tracing = false;
  let pendingBase: LngLat | null = null;
  let shadeCounter = 0;

  const fmtH = (h: number) => {
    const whole = Math.floor(h);
    const mins = Math.round((h - whole) * 60);
    return mins > 0 ? `${whole} h ${String(mins).padStart(2, '0')}` : `${whole} h`;
  };
  const fmt1 = (n: number) => n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const fmt2 = (n: number) => n.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
  /** CAL235 — dernière proposition affichée (les modules visés), ou null. */
  let lastProposal: { indices: number[] } | null = null;

  /** ACAL496 — le soleil de la prise de vue d'après la date et l'heure DÉCLARÉES, ou le motif. */
  const imagerySun = () => declarationSoleilPriseDeVue(ctx.centroidLat, dateImageCapturee()?.date, imageryHour);
  const imagerySunElevation = (): number | null => {
    const d = imagerySun();
    return d.ok ? d.elevationDeg : null;
  };

  /** CAL66/CAL67 — les obstructions vues de la zone active, TOUTES sources confondues
   *  (ombres tracées + obstacles de toiture à hauteur saisie + objets d'environnement). */
  const activeShadeEntries = (): ShadeObstructionENU[] =>
    unifiedShadeEntries(ctx.shadeObstructions, ctx.obstacles, ctx.environment, ctx.centroid, roofHeightM());

  /** CAL66/CAL67 — y a-t-il seulement quelque chose à ombrer ? (au moins une ombre tracée,
   *  un obstacle à hauteur saisie ou un objet d'environnement à hauteur saisie). */
  const hasShadeSources = (): boolean =>
    ctx.shadeObstructions.length > 0 ||
    ctx.obstacles.some((o) => typeof o.heightM === 'number' && o.heightM > 0) ||
    (ctx.environment ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0 && o.supposeCoupe !== true); // ACAL502

  /** Nombre d'obstructions RETENUES au dernier calcul (après retrait de la hauteur de
   *  toit) — pilote le libellé honnête de la note, cf. `renderList`. */
  let lastEntryCount = 0;
  /** ACAL1407 — empreinte des modules posés de la matrice en vigueur, et de la première pose relue d'un document. */
  let poseDeLaMatrice: string | null = null;
  let poseEnregistree: string | null = null;

  /** (Re)calcule la matrice de dérate + le facteur annuel depuis la source unifiée.
   *  Horizon évalué au CENTROÏDE du tracé (documenté) ; hauteur de champ = toit 3D. */
  function recomputeFactors() {
    // ACAL26 — la matrice ENREGISTRÉE du document rouvert est conservée tant qu'aucune
    // source d'ombrage n'a été modifiée dans la session ; la première modification la
    // retire pour de bon (le recalcul reprend la main). ACAL1407 — déplacer les panneaux
    // posés en est une aussi (la matrice est leur moyenne) : la première pose relue est retenue.
    const enregistre = ctx.ombrageEnregistre;
    const poses = pointsPosesDuPan(ctx);
    const pose = empreinteDesPoses(poses);
    if (enregistre) {
      const signature = signatureSourcesOmbrage(ctx);
      if (enregistre.signature === null) [enregistre.signature, poseEnregistree] = [signature, null];
      if (poseEnregistree === null && poses.length) poseEnregistree = pose;
      if (enregistre.signature === signature && (poseEnregistree === null || poseEnregistree === pose)) {
        poseDeLaMatrice = pose;
        lastEntryCount = ctx.vertices.length >= 3 ? activeShadeEntries().length : 0;
        ctx.shadeFactors = enregistre.matrice.map((r) => r.slice());
        ctx.shadeAnnualFactor = annualShadeFactor(ctx.prodPerKwc ?? fallbackPerKwc(), ctx.shadeFactors, ctx.centroidLat);
        return;
      }
      ctx.ombrageEnregistre = null;
    }
    // ACAL27 — l'UNIQUE calcul, partagé avec la relecture du document (`matriceOmbrageDesSources`).
    const calcul = matriceOmbrageDesSources(ctx, roofHeightM(), poses);
    poseDeLaMatrice = pose;
    lastEntryCount = calcul.entries;
    if (!calcul.factors) {
      ctx.shadeFactors = null;
      ctx.shadeAnnualFactor = 1;
      return;
    }
    ctx.shadeFactors = calcul.factors;
    // Facteur annuel pondéré par la vraie saisonnalité : profils PVGIS si présents,
    // sinon le repli interne étiqueté (forme saisonnière plausible, même pondération).
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    ctx.shadeAnnualFactor = annualShadeFactor(prod, ctx.shadeFactors, ctx.centroidLat); // ACAL381
  }

  /**
   * CAL93 — (re)calcule le dérate d'HORIZON LOINTAIN depuis `ctx.horizonProfile`, TOUJOURS
   * un poste séparé de `recomputeFactors` (ombrage proche) ci-dessus : sa propre matrice
   * (`ctx.horizonFactors`), son propre facteur annuel (`ctx.horizonAnnualFactor`), jamais
   * fondus dans `shadeFactors`/`shadeAnnualFactor`. Profil absent ou < 2 points ⇒ 1 (aucun
   * effet, chiffres inchangés — comportement d'avant CAL93).
   */
  function recomputeHorizonFactors() {
    const points = ctx.horizonProfile?.points ?? null;
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    // ACAL378 — le jour-type pondère la matrice : un repli en cloche garde la perte mensuelle vraie.
    const factors = hourlyHorizonFactors(ctx.centroidLat, points, undefined, prod);
    ctx.horizonFactors = factors;
    if (!factors) {
      ctx.horizonAnnualFactor = 1;
      return;
    }
    ctx.horizonAnnualFactor = annualShadeFactor(prod, factors);
  }

  /** CAL93 — état publié du dérate d'horizon, lu par l'écran (HorizonPanel) et les tests. */
  function horizonStatus(): { hasProfile: boolean; maskedHours: number; annualFactor: number } {
    return {
      hasProfile: !!ctx.horizonFactors,
      maskedHours: maskedHourCount(ctx.horizonFactors ?? null),
      annualFactor: typeof ctx.horizonAnnualFactor === 'number' ? ctx.horizonAnnualFactor : 1,
    };
  }

  /** CAL93 — note dédiée à l'horizon, TOUJOURS distincte de la note d'ombrage proche
   *  (`renderList`) — jamais la même phrase, jamais le même chiffre fondu. */
  function renderHorizonNote() {
    if (!horizonNoteEl) return;
    const s = horizonStatus();
    if (!s.hasProfile) {
      horizonNoteEl.textContent = '';
      return;
    }
    const lossPct = Math.round((1 - s.annualFactor) * 100);
    horizonNoteEl.textContent =
      s.maskedHours > 0
        ? `Horizon PVGIS : ${s.maskedHours} heure(s) sur 288 (12 mois × 24 h) masquée(s) par le relief lointain — ` +
          `−${lossPct} % de production annuelle (part diffuse et réfléchie conservée, selon la hauteur du soleil). Poste séparé de l’ombrage proche.`
        : 'Horizon PVGIS renseigné : aucune heure masquée pour ce champ.';
  }

  /** CAL93 — fixe (ou efface) le profil d'horizon et recalcule SON dérate propre. */
  function setHorizonProfile(profile: HorizonProfile | null) {
    ctx.horizonProfile = profile;
    recomputeHorizonFactors();
    renderHorizonNote();
    recalcDisplays();
  }

  /** Recalcule les hauteurs déduites (l'hypothèse de prise de vue a pu changer). */
  function recomputeHeights() {
    const elev = imagerySunElevation();
    if (elev == null) return; // ACAL496 — rien de déclaré : les hauteurs relues du document restent
    for (const o of ctx.shadeObstructions) {
      const v = shadowVector(o.base, o.tip);
      const h = obstructionHeightFromShadow(v.lengthM, elev);
      if (h != null) o.heightM = h;
    }
  }

  function recomputeShading() {
    recomputeHeights();
    recomputeFactors();
    recomputeHorizonFactors(); // CAL93 — poste séparé, recalculé au même rythme
    renderHorizonNote();
    renderList();
    drawShadeLines();
    syncHeightUi(); // CAL60 — la zone active a pu changer (bâtiment différent)
    recalcDisplays();
    // WJ21 — le re-rendu (recalcDisplays) a recréé les instances de panneaux : ré-applique
    // la teinte d'accès solaire si la heatmap est active.
    refreshHeatmap();
    renderSolarAccess(); // CAL97 — le chiffre publié suit les obstructions
    renderModuleShadeReadings(); // CALX122 — la lecture par module suit les obstructions
  }

  // WJ21 — CARTE D'ACCÈS SOLAIRE : teinte chaque panneau par sa part RÉELLE d'irradiation
  // annuelle reçue (obstructions tracées retirées du soleil direct, diffus conservé),
  // pondérée par les vrais profils PVGIS. Astronomie pure, aucune API, aucun chiffre
  // inventé (même modèle que le dérate de production, évalué par panneau).
  /** ACAL1621 — y a-t-il des modules à teinter ? (plan pavé, au moins un panneau, contour fermé) */
  const carteChiffrable = (): boolean => {
    const plan = ctx.layoutPlan;
    return !!plan && plan.grid.panels.length > 0 && ctx.vertices.length >= 3;
  };
  function buildHeatmapColorFn(): ((cellIndex: number) => { r: number; g: number; b: number }) | null {
    const plan = ctx.layoutPlan;
    if (!plan || !carteChiffrable()) return null;
    const enu = activeShadeEntries(); // CAL66/CAL67 — toutes les sources, pas seulement les ombres tracées
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    const panels = plan.grid.panels;
    // CAL95 — accès solaire pré-calculé par cellule (0–1), en lecture annuelle ou d'un
    // mois. Sans obstruction → tout à 1 (plein soleil uniforme), ce qui est honnête.
    const access = heatmapAccessValues(ctx.centroidLat, enu, prod, panels, heatmapMonth);
    return (cellIndex: number) => {
      const a = cellIndex >= 0 && cellIndex < access.length ? access[cellIndex] : 1;
      return couleurAccesActive(a);
    };
  }

  /** ACAL717 — courbe « direct perdu » du mois de la date choisie, sous la barre du soleil (expert). */
  function rafraichirCourbeDirectPerdu() {
    const hote = $('rp9-direct-perdu') ?? (() => {
      const ancre = $('rp9-sun-controls');
      if (!ancre || typeof document.createElement !== 'function') return null;
      const d = document.createElement('div');
      d.id = 'rp9-direct-perdu';
      d.className = 'mt-2 text-xs text-lune-soft';
      ancre.insertAdjacentElement('afterend', d);
      return d;
    })();
    if (!hote) return;
    hote.hidden = !modeExpertActif();
    const plan = ctx.layoutPlan;
    if (hote.hidden || !plan || !plan.grid.panels.length) { hote.innerHTML = ''; return; }
    if (!hasShadeSources()) { hote.textContent = 'Direct perdu : aucune ombre saisie.'; return; }
    const mois = moisDuJour(ctx.sunDay);
    const serie = directPerduParHeure(ctx.centroidLat, activeShadeEntries(), plan.grid.panels.map((p) => ({ x: p.cx, y: p.cy })), mois);
    const phrase = phraseDirectPerdu(serie, HEATMAP_MONTH_LABELS[mois]);
    hote.innerHTML = `${svgCourbeDirectPerdu(serie, phrase)}<p>${esc(phrase)}</p>`;
  }

  /** ACAL1620 — le chiffre d'accès et la lecture par module suivent le plan et les sources À L'ÉCRAN : un document rouvert
   *  (obstacle relu, panneaux posés après la naissance de l'UI) disait « non renseigné » jusqu'à une retouche. Mémorisé par
   *  plan + sources + mois + seuil : un redessin qui ne change rien ne recalcule rien. */
  let cleAccesPublie: string | null = null;
  let planAccesPublie: unknown = null;
  function rafraichirAccesPublie() {
    const cle = JSON.stringify([signatureSourcesOmbrage(ctx), hasShadeSources(), heatmapMonth, seuilRetrait(), ctx.vertices.length, ctx.layoutPlan?.grid.panels.length ?? 0]);
    if (cle === cleAccesPublie && ctx.layoutPlan === planAccesPublie) return;
    cleAccesPublie = cle;
    planAccesPublie = ctx.layoutPlan;
    renderSolarAccess();
    renderModuleShadeReadings();
  }

  function refreshHeatmap() {
    rafraichirCourbeDirectPerdu();
    rafraichirAccesPublie(); // ACAL1620
    if (!heatmapOn) return;
    applyHeatmap(buildHeatmapColorFn());
  }

  /**
   * CAL97 — accès solaire CHIFFRÉ du pan actif. `null` = le chiffre est ABSENT (aucun
   * module posé, ou aucune obstruction renseignée : rien n'a été vérifié, on ne publie
   * donc pas un « 100 % » qui ferait croire à une vérification d'ombrage).
   */
  /** ACAL138 — l'accès solaire PERSISTÉ : sur les modules POSÉS fournis (dans l'ordre de
   *  `geometry.panels`), sur l'ANNÉE entière — jamais le mois du sélecteur de la carte. */
  function solarAccessAnnuel(points: readonly { x: number; y: number }[]): SolarAccessSummary | null {
    if (!points.length || ctx.vertices.length < 3) return null;
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    return solarAccessSummary(ctx.centroidLat, activeShadeEntries(), prod, points, null, undefined, seuilRetrait());
  }

  /** ACAL459 — la table d'ombrage par direction du pan actif (même source d'obstructions). */
  const signatureTable = () => signerSources(signatureSourcesOmbrage(ctx));
  const tableOmbrageActive = (points: readonly { x: number; y: number }[]): TableOmbrage | null =>
    ctx.vertices.length < 3 ? null : tableOmbrage(points, activeShadeEntries(), signatureTable());

  const vueCielActive = (points: readonly { x: number; y: number }[], penteDeg: number, azimutDeg: number): FacteurVueCiel | null =>
    ctx.vertices.length < 3 ? null : vueCielDuPan(facteurVueCiel(points, activeShadeEntries(), penteDeg, azimutDeg), signatureTable());

  /** ACAL714 — le seuil de retrait du RÉGLAGE société (`simulation.seuil_acces_retrait`), ou `null`. */
  const seuilEffectif = () => seuilEffectifAccesSolaire(choixOptimisationCourant()?.seuilAccesSolaire, ctx.opts?.reglagesAtelier); // ACAL548
  const seuilRetrait = (): number | null => seuilEffectif()?.valeur ?? null;

  function solarAccess(): SolarAccessSummary | null {
    const plan = ctx.layoutPlan;
    if (!plan || !plan.grid.panels.length || ctx.vertices.length < 3) return null;
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    const points = plan.grid.panels.map((p) => ({ x: p.cx, y: p.cy }));
    return solarAccessSummary(ctx.centroidLat, activeShadeEntries(), prod, points, heatmapMonth, undefined, seuilRetrait());
  }

  /**
   * CALX111 câblage — désignation HUMAINE du module de rang `i` dans le pavage : le numéro
   * STABLE du document quand la numérotation est en service (il survit à un retrait et à
   * une réouverture du dossier), sinon le rang dans le pavage — le libellé d'aujourd'hui,
   * inchangé. Jamais un numéro inventé : `etiquette` rend une chaîne vide quand le module
   * ne porte pas de `n`, et c'est alors le rang qui s'affiche.
   */
  function etiquetteModule(i: number): string {
    const panId = ctx.activeAreaId;
    const numerote = registreAtelier.modules(panId)[i];
    return etiquette(numerote, registreAtelier.convention(panId)) || `nº${i + 1}`;
  }

  /** ACAL1532 — les obstacles de toit dont l'ombre atteint les modules SIGNALÉS (même `perModule` que la proposition :
   *  sous le seuil réglé, sinon tout module dont l'accès est < 1). Un obstacle haut qui n'ombre aucun d'eux n'est pas nommé. */
  function obstaclesQuiOmbrent(s: SolarAccessSummary): Obstacle[] {
    const plan = ctx.layoutPlan;
    if (!plan) return [];
    const seuil = seuilRetrait() ?? 1;
    const signales = plan.grid.panels.filter((_, i) => s.perModule[i] < seuil);
    if (!signales.length) return [];
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    return ctx.obstacles.filter((o) => {
      const seul = roofObstacleShadeEntries([o], ctx.centroid);
      return seul.length > 0 && signales.some((p) => pointSolarAccess(ctx.centroidLat, seul, prod, p.cx, p.cy) < 1 - 1e-6);
    });
  }

  /** ACAL1532 — ce que l'écran Panneaux lit de `#rp9-solar-access` SANS parser le texte : le nom de l'obstacle
   *  (`data-ombre-de`) et, SEULEMENT sans seuil réglé, la perte annuelle de `shadeAnnualFactor` (`data-ombre-perte`,
   *  % entier ≥ 1). Recalculé à chaque rendu, jamais écrit au document ; aucun seuil par défaut. */
  function publierOmbrePourEcran(el: HTMLElement, s: SolarAccessSummary | null) {
    const de = s ? designationDeLOmbre(obstaclesQuiOmbrent(s), ctx.shadeObstructions?.length ?? 0, ctx.environment) : null;
    if (de) el.dataset.ombreDe = de; else delete el.dataset.ombreDe;
    const perte = s && seuilRetrait() == null && ctx.shadeFactors ? Math.round((1 - ctx.shadeAnnualFactor) * 100) : 0;
    if (perte >= 1) el.dataset.ombrePerte = String(perte); else delete el.dataset.ombrePerte;
  }

  /** CAL97 — publie le chiffre (et sa méthode) à côté de la carte, ou dit clairement
   *  POURQUOI il est absent — jamais une estimation de remplacement. */
  function renderSolarAccess() {
    const el = accessEl;
    if (!el) return;
    const s = solarAccess();
    publierOmbrePourEcran(el, s);
    if (!s) {
      el.textContent = hasShadeSources()
        ? 'Accès solaire : non calculé (aucun module posé sur ce pan).'
        : 'Accès solaire : non renseigné — aucune obstruction n’a été saisie et l’horizon lointain n’est pas modélisé. Le chiffre est volontairement ABSENT plutôt qu’estimé.';
      return;
    }
    const pct = (v: number) => `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;
    const periode = s.month == null ? 'année entière' : HEATMAP_MONTH_LABELS[s.month];
    // CAL235 — PROPOSITION (jamais appliquée d'office) de retirer les modules les plus
    // ombragés. Chaque chiffre vient des calculs existants : compte, kWc perdu (puissance
    // unitaire RÉELLE du plan), effet sur l'accès solaire moyen. Aucun modèle nouveau.
    const seuil = seuilRetrait();
    const proposal = proposeShadedRemoval(s.perModule, panelKwcOfPlan(), seuil);
    lastProposal = proposal ? { indices: proposal.indices } : null;
    const origineSeuil = seuilEffectif()?.origine ?? 'societe';
    const proposalHtml = htmlProposition(proposal, seuil, !!deps.removePanels, proposal ? proposal.indices.map(etiquetteModule).join(', ') : '', origineSeuil);
    el.innerHTML =
      `<div><span class="font-semibold text-white">Accès solaire (${esc(periode)})</span> — ` +
      `moyenne du pan <span class="fig">${esc(pct(s.average))}</span> sur ${s.count} module(s), ` +
      `du plus ombragé <span class="fig">${esc(pct(s.min))}</span> au plus dégagé <span class="fig">${esc(pct(s.max))}</span>` +
      (s.lowCount && seuil != null ? `, dont ${s.lowCount} sous le seuil ${origineSeuil === 'dossier' ? 'de ce dossier' : 'de votre société'} (${esc(pct(seuil))})` : '') +
      '.</div>' +
      (modeExpertActif() ? `<div class="mt-1 text-white">${esc(phraseVerdictOmbrage(s, ctx.opts?.reglagesAtelier, periode))}</div>` : '') + // ACAL715
      `<div class="mt-1 opacity-80">${esc(s.method.description)}</div>` +
      `<ul class="mt-1 list-disc pl-4 opacity-80">${s.assumptions.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>` +
      proposalHtml;
  }

  /** CAL235 — puissance unitaire (kWc) du panneau du plan COURANT, jamais supposée : elle
   *  vient du pavage lui-même (kWc total ÷ nombre de cellules). 0 si indisponible, ce qui
   *  éteint simplement la proposition. */
  function panelKwcOfPlan(): number {
    const g = ctx.layoutPlan?.grid;
    if (!g || !g.panels.length || !Number.isFinite(g.kwc) || g.kwc <= 0) return 0;
    return g.kwc / g.panels.length;
  }

  /** CALX122 — lecture géométrique par module du pan actif (cf. `moduleShadeReadingsForPanels`
   *  ci-dessus) : `null` tant qu'aucune source d'ombrage n'est saisie, ou tant qu'aucun
   *  module n'est posé sur ce pan. */
  function moduleShadeReadings(): ModuleShadeReading[] | null {
    const plan = ctx.layoutPlan;
    if (!plan || !plan.grid.panels.length || ctx.vertices.length < 3) return null;
    return moduleShadeReadingsForPanels(ctx.centroidLat, activeShadeEntries(), plan.grid.panels, hasShadeSources());
  }

  /** CALX122 — texte d'info-bulle prêt à afficher au survol d'UN module. Aucune
   *  production ici — le survol reste géométrique, comme le compte publié dans le
   *  panneau (`renderModuleShadeReadings`). Attacher ce texte au survol 3D reste un
   *  crochet attendu côté scene3d.ts/roof-tool-pro11.ts, hors périmètre de cette tâche. */
  function moduleShadeTooltip(cellIndex: number): string | null {
    const readings = moduleShadeReadings();
    if (!readings) {
      return hasShadeSources()
        ? 'Ombrage : non calculé (aucun module posé sur ce pan).'
        : 'Ombrage : non renseigné — aucune obstruction n’a été saisie.';
    }
    const r = cellIndex >= 0 && cellIndex < readings.length ? readings[cellIndex] : null;
    if (!r) return null;
    const ombrage = r.maskedHours > 0 && r.firstMonthIndex != null
      ? `Ombrage : ${r.maskedHours} heure(s) sur 288 masquée(s) par une obstruction, dès ${HEATMAP_MONTH_LABELS[r.firstMonthIndex]}.`
      : 'Ombrage : aucune heure masquée pour ce module.';
    // ACAL729 — accès annuel du module et sa chaîne (table servie), en TÊTE ; rien d'inventé sinon.
    const aire = ctx.areas.find((a) => a.id === ctx.activeAreaId);
    const id = identifiantsModulesParCellule(ctx.activePanelCellIndex ?? [], clePanAffectation(aire, ctx.activeAreaId))[cellIndex]; // ACAL1947 — la clé de la coloration
    // ACAL1641 — une ligne SERVIE sans chaîne = module « non raccordé » ; module absent de la table (ou table non servie) : rien dit.
    const servi = ctx.affectationColoration;
    const chaine = id && servi ? servi.labelByModule?.get(id) ?? (servi.colorByModule?.has(id) ? 'non raccordé' : null) : null;
    return teteInfoBulleModule(accesAnnuelDuModule(cellIndex), chaine) + ombrage;
  }

  /** ACAL729 — accès solaire ANNUEL d'un module du pan actif (mémorisé par plan + sources), ou `null`. */
  let memoAccesTooltip: { plan: unknown; signature: string; resume: SolarAccessSummary | null } | null = null;
  function accesAnnuelDuModule(cellIndex: number): number | null {
    const plan = ctx.layoutPlan;
    if (!plan) return null;
    const signature = signatureTable();
    if (!memoAccesTooltip || memoAccesTooltip.plan !== plan || memoAccesTooltip.signature !== signature) {
      memoAccesTooltip = { plan, signature, resume: solarAccessAnnuel(plan.grid.panels.map((p) => ({ x: p.cx, y: p.cy }))) };
    }
    return memoAccesTooltip.resume?.perModule[cellIndex] ?? null;
  }

  /** CALX122 — publie, PAR MODULE, la lecture géométrique d'ombrage (heures masquées +
   *  premier mois) à côté de l'accès solaire CHIFFRÉ (CAL97) : sans source d'ombrage
   *  saisie, le compte est ABSENT — jamais un « 0 heure ». Aucun kWh ici. */
  function renderModuleShadeReadings() {
    const el = shadeHoursEl;
    if (!el) return;
    const readings = moduleShadeReadings();
    if (!readings) {
      el.textContent = hasShadeSources()
        ? 'Ombrage par module : non calculé (aucun module posé sur ce pan).'
        : 'Ombrage par module : non renseigné — aucune obstruction n’a été saisie. Le nombre d’heures est volontairement ABSENT plutôt qu’estimé à zéro.';
      return;
    }
    // Item 14 (T4-U1-023) — sur les panneaux POSÉS (cellules rendues), jamais toutes les cellules du pavage.
    el.textContent = phraseOmbrageParModule(readings, ctx.activePanelCellIndex, ctx.layoutPlan?.pack?.count ?? 0)
      ?? 'Ombrage par module : non calculé (aucun module posé sur ce pan).';
  }

  // ACAL1621 — sans source d'ombrage OU sans module à teinter (aucun plan, aucun panneau : `buildHeatmapColorFn` rendrait
  // null), rien n'est capturé : `null`, comme sans source — jamais la vue 3D ordinaire présentée comme une carte de chaleur.
  const avecCarteDAcces = <T,>(fn: () => Promise<T>) => executerAvecCarte(
    { on: heatmapOn, mois: heatmapMonth },
    (on, mois) => { heatmapMonth = mois; setHeatmap(on); },
    hasShadeSources() && carteChiffrable(),
    fn,
  );

  const metaTableOmbrage: ShadingUi['metaTableOmbrage'] = (g) => {
    const points = (g?.panels ?? []).map((p) => ({ x: p.cx, y: p.cy }));
    // ACAL1407 — appelée avant chaque sérialisation : la matrice enregistrée suit les modules posés. Couture :
    // comparée à la pose que `recomputeFactors` mesure (pointsPosesDuPan), et seulement quand une matrice est
    // en vigueur — un document sans matrice ne s'en voit pas écrire une par un simple enregistrement.
    const pose = empreinteDesPoses(pointsPosesDuPan(ctx));
    if (hasShadeSources() && (poseDeLaMatrice !== null || ctx.shadeFactors) && poseDeLaMatrice !== pose) recomputeFactors();
    return { shadeTableByZone: { [ctx.activeAreaId]: tableOmbrageActive(points) }, signatureOmbrage: signatureTable(), skyViewByZone: { [ctx.activeAreaId]: g ? vueCielActive(points, g.tiltDeg, g.azimuthDeg) : null } };
  };

  function setHeatmap(on: boolean) {
    heatmapOn = on;
    if (heatmapBtn) heatmapBtn.setAttribute('aria-pressed', String(on));
    syncHeatmapNote();
    applyHeatmap(on ? buildHeatmapColorFn() : null);
  }

  /** CAL95 — légende de la carte : la même lecture honnête qu'avant, avec la PÉRIODE
   *  évaluée nommée (année entière par défaut, ou le mois choisi). */
  function syncHeatmapNote() {
    if (!heatmapNoteEl) return;
    if (!heatmapOn) {
      heatmapNoteEl.textContent = '';
      poserLegendeAcces(heatmapNoteEl, null); // ACAL441
      return;
    }
    poserLegendeAcces(heatmapNoteEl, heatmapMonth == null ? 'année entière' : HEATMAP_MONTH_LABELS[heatmapMonth]); // ACAL441
    const periode = heatmapMonth == null ? 'toute l’année' : `en ${HEATMAP_MONTH_LABELS[heatmapMonth]}`;
    heatmapNoteEl.textContent =
      `Carte d’accès solaire (${heatmapMonth == null ? 'année entière' : HEATMAP_MONTH_LABELS[heatmapMonth]}) : ` +
      `${phraseCouleursAcces(periode)} (calcul astronomique, pondéré par l’irradiation réelle du lieu). ` + // ACAL1821
      'Obstacles de toiture à hauteur saisie, objets d’environnement et ombres tracées la font varier.';
  }

  /** Ligne pointillée base→bout de chaque ombre tracée, sur la carte 2D. */
  function drawShadeLines() {
    const src = map.getSource(SHADE_SRC) as maplibregl.GeoJSONSource | undefined;
    const data = {
      type: 'FeatureCollection',
      features: ctx.shadeObstructions.map((o) => ({
        type: 'Feature',
        properties: {},
        geometry: { type: 'LineString', coordinates: [o.base, o.tip] },
      })),
    };
    if (src) {
      src.setData(data as never);
      return;
    }
    try {
      map.addSource(SHADE_SRC, { type: 'geojson', data: data as never });
      map.addLayer({
        id: SHADE_SRC,
        type: 'line',
        source: SHADE_SRC,
        paint: { 'line-color': '#8f9bb8', 'line-width': 2, 'line-dasharray': [1, 1.2] },
      });
      map.addLayer({
        id: `${SHADE_SRC}-pts`,
        type: 'circle',
        source: SHADE_SRC,
        paint: { 'circle-radius': 4, 'circle-color': '#8f9bb8', 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 1.5 },
      });
    } catch {
      /* style pas encore chargé : les lignes apparaîtront au prochain redraw */
    }
  }

  function renderList() {
    if (noteEl) {
      // CAL66/CAL67 — la note porte sur TOUTES les sources d'ombre, pas seulement les
      // ombres tracées : une cheminée à hauteur saisie ou un arbre voisin comptent autant.
      if (!hasShadeSources()) {
        noteEl.textContent = '';
      } else if (!lastEntryCount) {
        noteEl.textContent = 'Obstruction(s) renseignée(s) sous le niveau du toit : aucune heure masquée pour ce champ.';
      } else {
        const lossPct = Math.round((1 - ctx.shadeAnnualFactor) * 100);
        noteEl.textContent =
          lossPct > 0
            ? `Ombrage (ombres tracées, obstacles de toiture à hauteur saisie, objets d’environnement) : −${lossPct} % de production annuelle (heures masquées ramenées à la part diffuse ~25 %). Hypothèse de prise de vue affichée ci-dessus — pas une mesure.`
            : 'Obstruction(s) renseignée(s) : aucune heure masquée pour ce champ.';
      }
    }
    if (!listEl) return;
    listEl.innerHTML = '';
    ctx.shadeObstructions.forEach((o, i) => {
      const v = shadowVector(o.base, o.tip);
      const row = document.createElement('div');
      row.className = 'flex flex-wrap items-center gap-2 border border-white/10 bg-nuit-900/40 p-2 text-xs text-lune-soft';
      row.innerHTML =
        `<span>${esc(libelleLigneOmbre(i + 1, v.lengthM, o.heightM))}</span>` +
        `<button type="button" data-shade-del="${esc(o.id)}" class="ml-auto border border-alert-300/60 px-2 py-1 font-semibold text-alert-300 hover:bg-alert-300/10">× Supprimer</button>`;
      listEl.appendChild(row);
    });
  }

  function setTracing(on: boolean) {
    tracing = on;
    pendingBase = null;
    if (addBtn) addBtn.setAttribute('aria-pressed', String(on));
    if (on) {
      setStatus('Ombre : cliquez le PIED de l’obstacle (arbre, immeuble…), puis le BOUT de son ombre sur l’image.');
    }
  }

  function handleMapClick(lngLat: LngLat): boolean {
    if (!tracing) return false;
    if (ctx.vertices.length < 3 || !ctx.closed) {
      setStatus('Tracez et fermez d’abord le toit — l’ombrage se calcule pour ce champ.');
      return true;
    }
    const soleil = imagerySun();
    if (!soleil.ok) {
      setStatus(soleil.motif);
      return true;
    }
    if (!pendingBase) {
      pendingBase = lngLat;
      setStatus('Pied posé — cliquez maintenant le BOUT de l’ombre.');
      return true;
    }
    const base = pendingBase;
    const v = shadowVector(base, lngLat);
    const h = obstructionHeightFromShadow(v.lengthM, soleil.elevationDeg);
    if (h == null || v.lengthM < 0.5) {
      setStatus('Ombre trop courte (ou soleil rasant) pour déduire une hauteur — re-tracez.');
      pendingBase = null;
      return true;
    }
    ctx.shadeObstructions.push({
      // ACAL27 — jamais un doublon d'une ombre RELUE du document : le compteur part du plus
      // grand numéro déjà présent.
      id: `shade-${(shadeCounter = Math.max(shadeCounter, ...ctx.shadeObstructions.map((o) => Number(/^shade-(\d+)$/.exec(o.id)?.[1] ?? 0))) + 1)}`,
      base,
      tip: lngLat,
      heightM: h,
      halfWidthM: SHADE_OBSTRUCTION_HALF_WIDTH_M,
    });
    setTracing(false);
    recomputeShading();
    setStatus(`Obstacle ajouté : hauteur estimée ~${fmt1(h)} m (déduite de l’ombre ; ${soleil.ligne}).`);
    return true;
  }

  function reset() {
    ctx.shadeObstructions.length = 0;
    ctx.ombrageEnregistre = null; // ACAL26 — effacer l'ombrage est une modification
    ctx.shadeObstructionsNonLues = []; // ACAL27 — « Effacer » vide aussi les ombres relues
    recomputeFactors(); // ACAL1407 — les obstacles et l'environnement restants gardent leur ombre
    setTracing(false);
    renderList();
    drawShadeLines();
  }

  // — Câblage DOM (tous les nœuds optionnels) —
  addBtn?.addEventListener('click', () => setTracing(!tracing));
  clearBtn?.addEventListener('click', () => {
    reset();
    recalcDisplays();
  });
  if (hourEl) {
    hourEl.addEventListener('input', () => {
      const v = hourEl.value.trim() === '' ? NaN : Number(hourEl.value.trim().replace(',', '.')); // ACAL1436 — virgule décimale acceptée
      if (!Number.isFinite(v) || v < 0 || v > 24) {
        imageryHour = null;
        if (hourValueEl) hourValueEl.textContent = 'Heure solaire illisible : un nombre entre 0 et 24.';
        return;
      }
      imageryHour = v;
      if (hourValueEl) hourValueEl.textContent = fmtH(v);
      if (hasShadeSources()) recomputeShading();
    });
  }
  listEl?.addEventListener('click', (e) => {
    const del = (e.target as HTMLElement).closest<HTMLElement>('[data-shade-del]');
    if (!del?.dataset.shadeDel) return;
    const idx = ctx.shadeObstructions.findIndex((o) => o.id === del.dataset.shadeDel);
    if (idx >= 0) {
      ctx.shadeObstructions.splice(idx, 1);
      recomputeShading();
    }
  });
  // WJ21 — bascule de la carte d'accès solaire (heatmap d'irradiance).
  heatmapBtn?.addEventListener('click', () => setHeatmap(!heatmapOn));
  // CAL95 — changer de mois ne change RIEN au modèle : la même intégrale horaire, lue
  // sur le jour-type PVGIS du mois choisi (annuel = valeur vide).
  heatmapMonthEl?.addEventListener('change', () => {
    const raw = heatmapMonthEl.value;
    const v = raw === '' ? null : Number(raw);
    heatmapMonth = v != null && Number.isInteger(v) && v >= 0 && v <= 11 ? v : null;
    syncHeatmapNote();
    if (heatmapOn) applyHeatmap(buildHeatmapColorFn());
    renderSolarAccess(); // CAL97 — le chiffre publié porte la période choisie
  });

  // CAL60 + CALX100 — hauteur de bâtiment saisie (`change` : blur/Entrée, jamais à chaque
  // frappe, même règle que le reste de l'atelier — W81). Vide ou invalide → le champ est
  // EFFACÉ (non renseigné), jamais mis à 0, et la 3D repart sur sa hauteur de dessin
  // annoncée. La valeur part dans `buildings[]` du document, avec sa provenance.
  for (const el of [heightEl, batEtagesEl, batHauteurEtageEl, batSourceEl, batAcrotereEl]) {
    el?.addEventListener('change', () => appliquerSaisieBatiment());
  }
  syncHeightUi();

  // CAL235 — l'application du retrait est un GESTE EXPLICITE : rien ne part sans ce clic,
  // et ce qu'il fait est annulable (Ctrl+Z, CAL100). Refuser ne change rien au plan.
  accessEl?.addEventListener('click', (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>('#rp9-solar-access-apply');
    if (!btn || !lastProposal || !deps.removePanels) return;
    const removed = deps.removePanels(lastProposal.indices);
    if (!removed) {
      setStatus('Retrait impossible sur cette disposition — rien n’a changé.');
      return;
    }
    setStatus(`${removed} module(s) retiré(s) — Ctrl+Z annule ce geste.`);
    recomputeShading();
  });

  // ACAL548 — « Accès solaire minimal (%) » : écrit `optimisation.seuilAccesSolaire` (les autres clés sont gardées).
  const seuilEl = $<HTMLInputElement>('rp9-seuil-acces');
  const seuilErreurEl = $('rp9-seuil-acces-erreur');
  const seuilNoteEl = $('rp9-seuil-acces-note');
  function syncSeuilUi() {
    const doc = choixOptimisationCourant()?.seuilAccesSolaire;
    if (seuilEl && document.activeElement !== seuilEl) {
      seuilEl.value = estSeuil(doc) ? (doc * 100).toLocaleString('fr-FR', { maximumFractionDigits: 2, useGrouping: false }) : '';
    }
    if (seuilNoteEl) seuilNoteEl.textContent = phraseOrigineSeuil(doc, ctx.opts?.reglagesAtelier);
  }
  seuilEl?.addEventListener('change', () => {
    const lu = lireSeuilSaisi(seuilEl.value);
    if (seuilErreurEl) seuilErreurEl.textContent = lu.ok ? '' : lu.erreur;
    seuilEl.setAttribute('aria-invalid', lu.ok ? 'false' : 'true');
    if (!lu.ok) return; // rien ne change, rien n'est corrigé en silence
    const suivant = { ...(choixOptimisationCourant() ?? {}) };
    if (lu.valeur == null) delete suivant.seuilAccesSolaire;
    else suivant.seuilAccesSolaire = lu.valeur;
    poserChoixOptimisation(Object.keys(suivant).length ? suivant : null);
    deps.recalcDisplays(); // ACAL1900 — écarte des emplacements : re-résout, même une pose tenue
    renderSolarAccess();
    syncSeuilUi();
  });
  syncSeuilUi();

  recomputeHorizonFactors(); // CAL93 — état initial (document rechargé avec un profil)
  renderHorizonNote();
  renderSolarAccess(); // CAL97 — état initial (dossier rechargé avec des obstructions)
  renderModuleShadeReadings(); // CALX122 — état initial

  /**
   * CALX132 — reçoit l'empreinte OSM du bâtiment ACTIF et calcule sa PROPOSITION
   * (`propositionOsm`, pure) — jamais appliquée d'office. `null`/absent, ou un bâtiment
   * sans tag exploitable, efface le bouton (aucune proposition à afficher).
   */
  function setBatimentOsmPropose(batiment: BatimentOsmServeur | null | undefined) {
    propositionOsmCourante = propositionOsm(batiment);
    renderPropositionOsm();
  }

  /** ACAL27 — redessine la liste et les lignes des ombres tracées après une hydratation,
   *  SANS recalcul (la matrice enregistrée reste en vigueur, cf. `recomputeFactors`). */
  function rafraichirOmbres() {
    syncSeuilUi(); // ACAL548 — le champ se relit depuis le document
    renderList();
    drawShadeLines();
    rafraichirAccesPublie(); // ACAL1620
  }

  return {
    handleMapClick,
    rafraichirOmbres,
    recomputeShading,
    redessiner: recalcDisplays, // ACAL1900 — soleil, bande climatique : redessin sans re-pose
    refreshHeatmap,
    reset,
    solarAccess,
    solarAccessAnnuel, // ACAL138
    tableOmbrage: tableOmbrageActive, // ACAL459
    signatureTable,
    vueCiel: vueCielActive, // ACAL460
    avecCarteDAcces, // ACAL726
    metaTableOmbrage, // ACAL726 (extrait de roof-tool-pro11.ts)
    setHorizonProfile,
    // ACAL378 — la matrice dépend de la latitude : recalculée quand le centroïde change
    // (sinon un document rouvert garde celle de la latitude par défaut, 33,5°).
    recomputeHorizon: () => {
      recomputeHorizonFactors();
      // ACAL381 — le facteur annuel de l'ombrage proche lit lui aussi la latitude du toit.
      if (ctx.shadeFactors) ctx.shadeAnnualFactor = annualShadeFactor(ctx.prodPerKwc ?? fallbackPerKwc(), ctx.shadeFactors, ctx.centroidLat);
      renderHorizonNote();
      syncHeightUi(); // ACAL1405 — appelé à la fermeture du pan relu : le bâtiment de CE pan
    },
    horizonStatus,
    syncHeightUi, // ACAL1405
    moduleShadeReadings,
    moduleShadeTooltip,
    setBatimentOsmPropose,
  };
}
