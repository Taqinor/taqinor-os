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
import type maplibregl from 'maplibre-gl';
import { sunDirection } from '../../lib/roofPro2';
import {
  IMAGERY_SUN_DEFAULT,
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
  SOLAR_ACCESS_LOW,
  solarAccessColorRGB,
  type SolarAccessSummary,
  type ShadeObstruction,
  type ShadeObstructionENU,
} from '../../lib/shadingEngine';
import { roofObstacleShadeEntries, type Obstacle } from '../../lib/obstacles';
import { hourlyHorizonFactors, maskedHourCount, type HorizonProfile } from '../../lib/horizonEngine';
import { environmentShadeEntries, type EnvironmentObject } from './environment';
import { fallbackPerKwc, type PerKwcProduction } from '../../lib/productionEngine';
import { type LngLat } from '../../lib/roof';
import { FLOORS, FLOOR_HEIGHT_M, GOLD } from './constants';
import {
  appliquerSaisie,
  batimentPourId,
  hauteurExtrusion,
  idBatimentDuPan,
  mentionEtages,
  type Batiment,
} from './batiment'; // CALX100 — la hauteur vient du DOCUMENT, plus d'une Map locale
import { etiquette, registreAtelier } from './numerotation'; // CALX111 câblage
import { $, esc } from './dom';
import { type Ctx } from './context';

export interface ShadingUiDeps {
  map: maplibregl.Map;
  setStatus: (msg: string) => void;
  /** Re-rend la zone active (3D + carte de résultat + fenêtre de production). */
  recalcDisplays: () => void;
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
  /** WJ21 — ré-applique la heatmap d'accès solaire si elle est active (après un re-rendu
   *  qui a recréé les instances de panneaux). No-op si la heatmap est OFF. */
  refreshHeatmap: () => void;
  /** CAL97 — accès solaire CHIFFRÉ du pan actif (par module + agrégat), ou null quand
   *  aucune obstruction n'est renseignée : le chiffre est alors ABSENT, jamais estimé.
   *  Lu par les consommateurs (affichage, sérialisation CAL248). */
  solarAccess: () => SolarAccessSummary | null;
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

export function createShadingUi(ctx: Ctx, deps: ShadingUiDeps): ShadingUi {
  const { map, setStatus, recalcDisplays, applyHeatmap } = deps;

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
  const activeHeightOverride = (): number | null => {
    const lu = hauteurExtrusion(batimentActif());
    return lu.origine === 'saisie' ? lu.hauteurM : null;
  };
  /** Hauteur EFFECTIVE (m) de la zone active — saisie si présente, sinon l'hypothèse. */
  const roofHeightM = (): number => effectiveBuildingHeightM(activeHeightOverride());
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
  }

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
  let imageryDay: number = IMAGERY_SUN_DEFAULT.dayOfYear;
  let imageryHour: number = IMAGERY_SUN_DEFAULT.solarHour;

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

  /** Élévation solaire de l'hypothèse courante à la latitude du toit. */
  const imagerySunElevation = (): number =>
    sunDirection(ctx.centroidLat, imageryDay, imageryHour).elevationDeg;

  /** CAL66/CAL67 — les obstructions vues de la zone active, TOUTES sources confondues
   *  (ombres tracées + obstacles de toiture à hauteur saisie + objets d'environnement). */
  const activeShadeEntries = (): ShadeObstructionENU[] =>
    unifiedShadeEntries(ctx.shadeObstructions, ctx.obstacles, ctx.environment, ctx.centroid, roofHeightM());

  /** CAL66/CAL67 — y a-t-il seulement quelque chose à ombrer ? (au moins une ombre tracée,
   *  un obstacle à hauteur saisie ou un objet d'environnement à hauteur saisie). */
  const hasShadeSources = (): boolean =>
    ctx.shadeObstructions.length > 0 ||
    ctx.obstacles.some((o) => typeof o.heightM === 'number' && o.heightM > 0) ||
    (ctx.environment ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0);

  /** Nombre d'obstructions RETENUES au dernier calcul (après retrait de la hauteur de
   *  toit) — pilote le libellé honnête de la note, cf. `renderList`. */
  let lastEntryCount = 0;

  /** (Re)calcule la matrice de dérate + le facteur annuel depuis la source unifiée.
   *  Horizon évalué au CENTROÏDE du tracé (documenté) ; hauteur de champ = toit 3D. */
  function recomputeFactors() {
    if (!hasShadeSources() || ctx.vertices.length < 3) {
      lastEntryCount = 0;
      ctx.shadeFactors = null;
      ctx.shadeAnnualFactor = 1;
      return;
    }
    const enu = activeShadeEntries();
    lastEntryCount = enu.length;
    if (!enu.length) {
      ctx.shadeFactors = null;
      ctx.shadeAnnualFactor = 1;
      return;
    }
    ctx.shadeFactors = hourlyShadeFactors(ctx.centroidLat, enu);
    // Facteur annuel pondéré par la vraie saisonnalité : profils PVGIS si présents,
    // sinon le repli interne étiqueté (forme saisonnière plausible, même pondération).
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    ctx.shadeAnnualFactor = annualShadeFactor(prod, ctx.shadeFactors);
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
    const factors = hourlyHorizonFactors(ctx.centroidLat, points);
    ctx.horizonFactors = factors;
    if (!factors) {
      ctx.horizonAnnualFactor = 1;
      return;
    }
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
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
          `−${lossPct} % de production annuelle (part diffuse conservée ~25 %). Poste séparé de l’ombrage proche.`
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
  function buildHeatmapColorFn(): ((cellIndex: number) => { r: number; g: number; b: number }) | null {
    const plan = ctx.layoutPlan;
    if (!plan || !plan.grid.panels.length || ctx.vertices.length < 3) return null;
    const enu = activeShadeEntries(); // CAL66/CAL67 — toutes les sources, pas seulement les ombres tracées
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    const panels = plan.grid.panels;
    // CAL95 — accès solaire pré-calculé par cellule (0–1), en lecture annuelle ou d'un
    // mois. Sans obstruction → tout à 1 (plein soleil uniforme), ce qui est honnête.
    const access = heatmapAccessValues(ctx.centroidLat, enu, prod, panels, heatmapMonth);
    return (cellIndex: number) => {
      const a = cellIndex >= 0 && cellIndex < access.length ? access[cellIndex] : 1;
      return solarAccessColorRGB(a);
    };
  }

  function refreshHeatmap() {
    if (!heatmapOn) return;
    applyHeatmap(buildHeatmapColorFn());
  }

  /**
   * CAL97 — accès solaire CHIFFRÉ du pan actif. `null` = le chiffre est ABSENT (aucun
   * module posé, ou aucune obstruction renseignée : rien n'a été vérifié, on ne publie
   * donc pas un « 100 % » qui ferait croire à une vérification d'ombrage).
   */
  function solarAccess(): SolarAccessSummary | null {
    const plan = ctx.layoutPlan;
    if (!plan || !plan.grid.panels.length || ctx.vertices.length < 3) return null;
    const prod = ctx.prodPerKwc ?? fallbackPerKwc();
    const points = plan.grid.panels.map((p) => ({ x: p.cx, y: p.cy }));
    return solarAccessSummary(ctx.centroidLat, activeShadeEntries(), prod, points, heatmapMonth);
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

  /** CAL97 — publie le chiffre (et sa méthode) à côté de la carte, ou dit clairement
   *  POURQUOI il est absent — jamais une estimation de remplacement. */
  function renderSolarAccess() {
    const el = accessEl;
    if (!el) return;
    const s = solarAccess();
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
    const proposal = proposeShadedRemoval(s.perModule, panelKwcOfPlan(), SOLAR_ACCESS_LOW);
    lastProposal = proposal ? { indices: proposal.indices } : null;
    const proposalHtml = proposal
      ? `<div class="mt-2 border border-white/10 bg-nuit-900/40 p-2">` +
        `<div><span class="font-semibold text-white">Proposition</span> — retirer les ` +
        `<span class="fig">${proposal.count}</span> module(s) dont l’accès solaire est sous ` +
        `${esc(pct(proposal.threshold))} : <span class="fig">−${esc(fmt2(proposal.kwcLost))}</span> kWc, ` +
        `accès solaire moyen des ${proposal.remaining} restants ` +
        `<span class="fig">${esc(pct(proposal.averageBefore))}</span> → <span class="fig">${esc(pct(proposal.averageAfter))}</span>.</div>` +
        `<div class="mt-1 opacity-80">Modules visés : ${esc(proposal.indices.map(etiquetteModule).join(', '))}.</div>` + // CALX111 câblage
        (deps.removePanels
          ? `<button type="button" id="rp9-solar-access-apply" class="mt-2 border border-white/20 px-2 py-1 font-semibold text-white hover:bg-white/10">Retirer ces modules</button>` +
            `<span class="ml-2 opacity-80">Rien n’est retiré tant que vous ne cliquez pas ; Ctrl+Z annule.</span>`
          : '<div class="mt-1 opacity-80">Retrait non applicable sur cet écran — la proposition reste informative.</div>')
      + '</div>'
      : '';
    el.innerHTML =
      `<div><span class="font-semibold text-white">Accès solaire (${esc(periode)})</span> — ` +
      `moyenne du pan <span class="fig">${esc(pct(s.average))}</span> sur ${s.count} module(s), ` +
      `du plus ombragé <span class="fig">${esc(pct(s.min))}</span> au plus dégagé <span class="fig">${esc(pct(s.max))}</span>` +
      (s.lowCount ? `, dont ${s.lowCount} sous ${esc(pct(SOLAR_ACCESS_LOW))}` : '') +
      '.</div>' +
      `<div class="mt-1 opacity-80">${esc(s.method)}</div>` +
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
    return r.maskedHours > 0 && r.firstMonthIndex != null
      ? `Ombrage : ${r.maskedHours} heure(s) sur 288 masquée(s) par une obstruction, dès ${HEATMAP_MONTH_LABELS[r.firstMonthIndex]}.`
      : 'Ombrage : aucune heure masquée pour ce module.';
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
    const shaded = readings.filter((r) => r.maskedHours > 0);
    if (!shaded.length) {
      el.textContent =
        `Ombrage par module (lecture géométrique, ${readings.length} module(s)) : aucune heure masquée — ` +
        'les obstructions renseignées ne couvrent la trajectoire solaire d’aucun module.';
      return;
    }
    const hours = shaded.map((r) => r.maskedHours);
    const minH = Math.min(...hours);
    const maxH = Math.max(...hours);
    const firstMonths = shaded.map((r) => r.firstMonthIndex).filter((m): m is number => m != null);
    const earliestMonth = firstMonths.length ? Math.min(...firstMonths) : null;
    el.textContent =
      'Ombrage par module (lecture géométrique, sur 288 heures représentatives = 12 mois × 24 h) : ' +
      `${shaded.length} module(s) sur ${readings.length} couvert(s) par une obstruction, de ${minH} à ${maxH} heure(s)` +
      (earliestMonth != null ? `, dès ${HEATMAP_MONTH_LABELS[earliestMonth]}` : '') +
      '. Aucune production n’est calculée ici.';
  }

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
      return;
    }
    const periode = heatmapMonth == null ? 'toute l’année' : `en ${HEATMAP_MONTH_LABELS[heatmapMonth]}`;
    heatmapNoteEl.textContent =
      `Carte d’accès solaire (${heatmapMonth == null ? 'année entière' : HEATMAP_MONTH_LABELS[heatmapMonth]}) : ` +
      `vert = plein soleil ${periode}, rouge = souvent à l’ombre (calcul astronomique, pondéré par l’irradiation réelle du lieu). ` +
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
        `<span class="font-semibold text-white">Ombre ${i + 1}</span>` +
        `<span>ombre ${esc(fmt1(v.lengthM))} m → hauteur estimée ~<span class="fig">${esc(fmt1(o.heightM))}</span> m</span>` +
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
    if (!pendingBase) {
      pendingBase = lngLat;
      setStatus('Pied posé — cliquez maintenant le BOUT de l’ombre.');
      return true;
    }
    const base = pendingBase;
    const v = shadowVector(base, lngLat);
    const h = obstructionHeightFromShadow(v.lengthM, imagerySunElevation());
    if (h == null || v.lengthM < 0.5) {
      setStatus('Ombre trop courte (ou soleil rasant) pour déduire une hauteur — re-tracez.');
      pendingBase = null;
      return true;
    }
    ctx.shadeObstructions.push({
      id: `shade-${++shadeCounter}`,
      base,
      tip: lngLat,
      heightM: h,
      halfWidthM: SHADE_OBSTRUCTION_HALF_WIDTH_M,
    });
    setTracing(false);
    recomputeShading();
    setStatus(`Obstacle ajouté : hauteur estimée ~${fmt1(h)} m (déduite de l’ombre, hypothèse de prise de vue affichée).`);
    return true;
  }

  function reset() {
    ctx.shadeObstructions.length = 0;
    ctx.shadeFactors = null;
    ctx.shadeAnnualFactor = 1;
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
      const v = Number(hourEl.value);
      if (!Number.isFinite(v)) return;
      imageryHour = v;
      if (hourValueEl) hourValueEl.textContent = fmtH(v);
      if (hasShadeSources()) recomputeShading();
    });
  }
  document.querySelectorAll<HTMLButtonElement>('[data-shade-season]').forEach((b) => {
    b.addEventListener('click', () => {
      const d = Number(b.dataset.shadeSeason);
      if (!Number.isFinite(d)) return;
      imageryDay = d;
      document.querySelectorAll<HTMLButtonElement>('[data-shade-season]').forEach((o) =>
        o.setAttribute('aria-pressed', String(o === b)),
      );
      if (hasShadeSources()) recomputeShading();
    });
  });
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

  recomputeHorizonFactors(); // CAL93 — état initial (document rechargé avec un profil)
  renderHorizonNote();
  renderSolarAccess(); // CAL97 — état initial (dossier rechargé avec des obstructions)
  renderModuleShadeReadings(); // CALX122 — état initial

  return {
    handleMapClick,
    recomputeShading,
    refreshHeatmap,
    reset,
    solarAccess,
    setHorizonProfile,
    horizonStatus,
    moduleShadeReadings,
    moduleShadeTooltip,
  };
}
