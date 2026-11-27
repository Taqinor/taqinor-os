/**
 * Moteur d'optimisation VIVANTE du builder pro-11 (toit plat W34/cerveau V7 +
 * toit en pente W35/cerveau V8 + matrice V6). Extrait de roof-tool-pro11.ts
 * (split modulaire 2026-06-20) — comportement INCHANGÉ, octet pour octet.
 *
 * Contient : la résolution contrainte vivante (`liveResolveFlat`/
 * `liveResolvePitched`), le rendu du gagnant (`renderLiveWinner`/
 * `renderPitchedWinner`/`renderConfig`/`renderPitched`), les badges/puces/
 * comparatifs (`updateLiveBadges`/`updatePitchedBadges`/`syncPitchedChips`/
 * `paintPitchedComparison`), les contrôles (`syncNeedControl`/`syncTiltControl`),
 * la carte de résultat (`paintCard`/`paintMaxLine`), les adaptateurs flush
 * (`flushToPack`/`flushGridToPanelGrid`), les verrous (`buildFlatLocks`/
 * `buildPitchedLocks`/`resetFlatLocks`/`resetPitchedLocks`), la matrice PVGIS
 * (`buildMatrix`/`computeMatrixPvgis`) et tous les accès PVGIS (caches +
 * `fetchPvgis`/`v4SpecificYield`/`pitchedSpecificYield`/`ensurePvgisForLockedTilt`/
 * `refinePitchedPvgis`).
 *
 * L'orchestration `recompute()`/`recalc()`/`close()` + le câblage des événements
 * DOM RESTENT dans l'entrée et appellent ces fonctions via l'objet renvoyé.
 * L'état partagé (sélection/verrous/affinages PVGIS/caches) passe par `ctx`.
 */
import {
  packConfig,
  productionKwh,
  billToAnnualKwh,
  annualSavingsMad,
  neededPanelsForTarget,
  roofDominantAzimuthDeg,
  tariffForCity,
  degradationFactor,
  clipDcAcKwh,
  effectiveDcAcRatio,
  BIFACIAL_GAIN_FLAT,
  BIFACIAL_GAIN_TILTED,
  ANNUAL_DEGRADATION,
  LIFETIME_YEARS,
  climateDerateFactor,
  productionConfidenceBand,
  type PackResult,
  type PackedPanel,
  type PanelGrid,
  type ConfigFamily,
} from '../../lib/estimatorBrainV2';
import { PERIMETER_SETBACK_M, PANEL2_LONG_M, PANEL2_SHORT_M, uniformSetbacks, type PerimeterSetbacks } from '../../lib/roofPro2';
import { supplementsParArete } from '../../lib/roofSetbackEdge'; // CALX95 câblage
// CALX109 câblage — les VRAIES cotes du module posé sur le pan actif. Même discipline que
// `retraitsParArete` ci-dessous (OPT-B/CALX95) : on lit le DOCUMENT (`AreaRecord.moduleId` +
// le catalogue de la société), on n'invente aucune dimension, et rien n'est passé au moteur
// tant que personne n'a choisi — le balayage reste alors celui d'aujourd'hui, octet pour octet.
import {
  cotesPourPan,
  estRefus,
  lireModulesDisponibles,
  catalogueAvecModulesDuDocument,
  kwcDuPan,
  MODULE_PAR_DEFAUT_ATELIER,
  resoudreModuleDuPan,
  type ModuleDocument,
} from './moduleSelect';
import { type Panel2Module } from '../../lib/roofPro2';
import {
  recommendPitched,
  type FlushPack,
  type FlushGrid,
  type RoofPlane,
} from '../../lib/estimatorBrainV3';
import { pitchedPlaneLeg } from '../../lib/estimatorBrainV5';
import {
  fineGridMatrixV6,
  pvgisCoarsePairs,
  pvgisMatrixCandidatePairs,
  pvgisRefinePairs,
  resoudreCibleOptimisation,
  type CibleOptimisation,
  type CibleResolue,
  type ChoixOptimisation,
  type MatrixEvalV6,
  type MatrixV6Result,
} from '../../lib/estimatorBrainV6';
import { majNoteChassis, optionChassis } from './chassisPavage'; // ACAL585
import { phraseDensiteMax } from './phrasesRecommandation'; // ACAL1919
import { axesDepartage, distanceAuBord } from './departageGeometrie'; // CAL83
import {
  anneauPosableParArete, // CALX95 câblage
  solveLive,
  type AxisLocks,
  type LayoutAxis,
  type LiveConfigEval,
  type LiveSolveResult,
} from '../../lib/estimatorBrainV7';
import {
  solveLivePitched,
  type PitchedLiveResult,
  type PitchedLayoutAxis,
  type PitchedMarginAxis,
} from '../../lib/estimatorBrainV8';
import { defaultEastWestGeometry, type EastWestGeometry } from '../../lib/estimatorBrainV2';
import { pointInPolygon, type LngLat } from '../../lib/roof';
import { fallbackPerKwc } from '../../lib/productionEngine';
import {
  filtrerEmplacementsSousSeuil,
  hauteurToitPourOmbrageM,
  seuilEffectifAccesSolaire, // ACAL548
  unifiedShadeEntries,
  type FiltrageAccesSolaire,
} from './shadingUi'; // CALX115 — le seuil d'accès solaire lu par le posable
import { $, celluleEconomies, fmt, fmtKwc, fmtMad, renommerDt } from './dom';
import { besoinDeLaFacture, estPompage, estLePlus, noteLePlus, peindreChampBesoin, raisonSansValeur, VALEURS_HORS_LIGNE, compteDevis, couvertureServie, phraseSurplus, peindreBande, phraseTaillesDuChiffrage, productionServie, quiDuDevis, suiteAuDevis, texteEconomie, texteSurDevis, cibleDeLAtelier, phraseTiennent } from './affichageErp'; import { peindrePhraseTailles, suiteCouverture } from './tailleConception'; // R2-13/16/17, ACAL2022, T4-X9-007
import { type CardData, type ChiffrageAtelier, type RenderConfigOpts, type RenderSceneFn } from './types';
import { type Ctx } from './context';
import { besoinAutoRelu } from './cible'; // ACAL367
import { lignesSensDePose, afficherSensDePose } from './orientationOmbre'; // ACAL552
import { maxDuSolveur, phraseCouvertureMax, type MaxDuToit } from './cibleProduction'; // ACAL547, ACAL1903
import { heatmapAccessValues } from './shadingUi'; // ACAL552
import { causeDuPanVide, contourPanENU, mesurerPanVide, motifPenteNord, noterMotifPanVide, retraitApplique, type MotifPanVide } from './motifPanVide'; // ACAL549, ACAL1970
import { cotesDePavage } from '../../lib/roofPro2';
import { carteDeLaPoseTenue, direEcartALaPose, motifPanExistant, poseTenue } from './panExistant'; import { noteTailleAuto } from './tailleAuto'; import { chiffresDeLaPose, partRaccordeeDuPan, texteChiffresVariante } from './chiffresVariante'; // ACAL574, ACAL1900, ACAL1331, T4-V2-021

// ═══════════ PV64 — TROIS VARIANTES LISIBLES DU BALAYAGE DÉJÀ CALCULÉ ═══════════
// Le balayage V6 (`fineGridMatrixV6`) évalue déjà des centaines de configurations, mais
// le tableau complet est illisible sur un téléphone. On en EXTRAIT trois points
// REPRÉSENTATIFS, sans RIEN recalculer (couche d'affichage + sélection pure) :
//  1. la densité maximale plein sud (le plus de panneaux posés en famille « sud ») ;
//  2. la meilleure « tente » Est-Ouest dos à dos ;
//  3. le meilleur azimut ALIGNÉ sur les arêtes du toit.
// Cliquer une carte ne fait que poser les VERROUS d'axes correspondants et relancer le
// solveur vivant existant — aucun second moteur, aucun chiffre inventé.

/** CAL87 — inclinaison est-ouest de RÉFÉRENCE pour calculer les valeurs par défaut à
 *  AFFICHER tant qu'aucun gagnant n'est connu (les cartes de variante est-ouest du
 *  balayage V6 sont évaluées à 10° et 15°). N'entre dans AUCUN pavage. */
const EW_DEFAULT_TILT_DEG = 10;

export type VariantCardId = 'couvre-besoin' | 'south-max' | 'eastwest' | 'aligned';

export interface VariantCard {
  id: VariantCardId;
  /** Libellé FR de la carte. */
  title: string;
  /** Pourquoi cette variante existe (une phrase). */
  reason: string;
  count: number;
  kwc: number;
  annualKwh: number;
  /** La ligne du balayage dont la carte est le reflet (source des verrous au clic). */
  row: MatrixEvalV6;
}

const VARIANT_TITLES: Record<VariantCardId, string> = {
  'couvre-besoin': 'Couvre le besoin',
  'south-max': 'Densité maximale (plein sud)',
  eastwest: 'Est-Ouest dos à dos',
  aligned: 'Aligné sur le toit',
};

/** Clé d'identité d'une ligne de balayage (dédoublonnage des cartes). */
function variantRowKey(r: MatrixEvalV6): string {
  return `${r.family}|${r.tiltDeg}|${Math.round(r.azimuthDeg * 10)}|${r.orientation}|${r.margin}`;
}

/**
 * PV64 — extrait jusqu'à 3 variantes représentatives du balayage V6 DÉJÀ calculé.
 * PURE : ne pave rien, ne résout rien, ne touche pas au DOM. Une catégorie sans ligne
 * (pas d'Est-Ouest évalué, toit déjà plein sud donc pas d'axe « aligné ») est simplement
 * ABSENTE — on n'invente pas une carte pour remplir la grille. Deux catégories qui
 * pointent la MÊME configuration n'en produisent qu'une (la première dans l'ordre).
 */
export function pickVariantCards(result: MatrixV6Result | null | undefined): VariantCard[] {
  const rows = result?.rows;
  if (!Array.isArray(rows) || rows.length === 0) return [];
  /** Meilleure ligne d'un sous-ensemble selon un score, départage par énergie annuelle. */
  const pick = (filter: (r: MatrixEvalV6) => boolean, score: (r: MatrixEvalV6) => number): MatrixEvalV6 | null => {
    let best: MatrixEvalV6 | null = null;
    let bestScore = -Infinity;
    for (const r of rows) {
      if (!filter(r)) continue;
      const sc = score(r);
      if (sc > bestScore || (sc === bestScore && best !== null && r.annualKwh > best.annualKwh)) {
        best = r;
        bestScore = sc;
      }
    }
    return best;
  };
  const candidates: { id: VariantCardId; row: MatrixEvalV6 | null; reason: (r: MatrixEvalV6) => string }[] = [
    {
      // ACAL547 — le plus petit nombre de panneaux qui atteint le besoin du balayage (≥ 100 %) ;
      // c'est une ESTIMATION du navigateur (production annuelle ÷ besoin), dite telle quelle.
      id: 'couvre-besoin',
      row: pick((r) => r.pctOfTarget >= 100, (r) => -r.placedCount),
      reason: (r) => `${r.placedCount} panneaux suffisent (estimation : ${Math.round(r.pctOfTarget)} % du besoin) à ${r.tiltDeg}°, ${r.layoutLabel}.`,
    },
    {
      id: 'south-max',
      // Densité = le plus de panneaux qui TIENNENT (fitCount, pas le nombre posé, plafonné au besoin). À égalité, le plus productif.
      row: pick((r) => r.family === 'south', (r) => r.fitCount),
      reason: phraseDensiteMax, // ACAL1919 — un seul nombre, ou les deux nommés
    },
    {
      id: 'eastwest',
      row: pick((r) => r.family === 'eastwest', (r) => r.annualKwh),
      reason: (r) => `Tente Est-Ouest à ${r.tiltDeg}° : ${r.placedCount} panneaux, la densité sans rangées espacées.`,
    },
    {
      id: 'aligned',
      row: pick((r) => r.azimuthAxis === 'aligned', (r) => r.annualKwh),
      reason: (r) => `Rangées alignées sur les arêtes du toit (${Math.round(r.azimuthDeg)}°) : ${r.placedCount} panneaux.`,
    },
  ];
  const seen = new Set<string>();
  const cards: VariantCard[] = [];
  for (const c of candidates) {
    if (!c.row) continue;
    const key = variantRowKey(c.row);
    if (seen.has(key)) continue;
    seen.add(key);
    cards.push({
      id: c.id,
      title: VARIANT_TITLES[c.id],
      reason: c.reason(c.row),
      count: c.row.placedCount,
      kwc: c.row.kwc,
      annualKwh: c.row.annualKwh,
      row: c.row,
    });
  }
  return cards;
}

export { phraseCouvertureMax }; // ACAL547 — vit dans cibleProduction.ts (re-exportée pour ses appelants)

/* ═════════ CALX114 — L'OBJECTIF SAISI DU DOCUMENT, LU PAR LES DEUX BALAYAGES ═════════
   `optimisation` (CALX88) voyage par le DOCUMENT. L'atelier le dépose ICI, et les deux
   appelants du balayage V6 — le tableau matrice (`matrix.ts`) et l'affinage PVGIS
   (`buildMatrix` plus bas) — le lisent au même endroit : sans ce point unique, la ligne
   « Recommandé » et la carte reco classeraient sur deux objectifs différents, ce qui
   était précisément le désaccord que W73 avait coûté à corriger sur la source PVGIS.
   Rien n'est décidé ici : aucun objectif par défaut n'est écrit, l'absence de choix est
   rendue telle quelle et NOMMÉE par `resoudreCibleOptimisation`.
   DEUX CROCHETS ATTENDUS, côté `prefill.ts` (ce module ne lit ni n'écrit le document) :
   à l'OUVERTURE, `prefill.ts` lit `optimisation` et appelle `poserChoixOptimisation` ;
   à la SÉRIALISATION, `serializeLayout` écrit `choixOptimisationCourant()` dans le
   document — sans ce second crochet, l'objectif choisi à l'écran serait perdu au
   rechargement, exactement comme la hauteur de bâtiment de CAL60. */
let choixOptimisation: ChoixOptimisation | null = null;

/** CALX114 — dépose le fragment `optimisation` SAISI (document, puce). Rend la cible
 *  telle qu'elle sera appliquée si aucune mesure n'existe — le balayage, lui, mesure
 *  d'abord puis re-résout, donc c'est lui qui a le dernier mot. */
export function poserChoixOptimisation(choix: ChoixOptimisation | null | undefined): CibleResolue {
  choixOptimisation = choix ?? null;
  return resoudreCibleOptimisation(choixOptimisation);
}

/** CALX114 — n'écrit QUE la cible, sans toucher aux autres clés saisies (priorité de
 *  remplissage, seuil d'accès solaire). `null` retire le choix : on revient à « aucun
 *  objectif saisi », qui reste un état nommé, pas un silence. */
export function poserCibleOptimisation(cible: CibleOptimisation | null): CibleResolue {
  const suivant: ChoixOptimisation = { ...(choixOptimisation ?? {}) };
  if (cible) suivant.cible = cible;
  else delete suivant.cible;
  return poserChoixOptimisation(suivant);
}

/** CALX114 — le fragment `optimisation` courant (null = rien n'a été saisi). */
export function choixOptimisationCourant(): ChoixOptimisation | null {
  return choixOptimisation;
}

/** CALX114 — la cible SAISIE et reconnue par le contrat, ou null (une valeur hors
 *  contrat n'en presse aucune : elle est refusée, pas traduite). */
export function cibleOptimisationSaisie(): CibleOptimisation | null {
  return resoudreCibleOptimisation(choixOptimisation).saisie;
}

/**
 * ACAL79 — LA borne des besoins DÉDUITS (facture, consommation) : [1, 400] panneaux. Seule
 * définition de l'atelier : `roof-tool-pro11.ts` et `consumption.ts` l'importent d'ici.
 * Elle ne s'applique JAMAIS à une cible VENDUE (voir `besoinVendu`).
 */
export function clampNeeded(n: number): number {
  return Math.max(1, Math.min(400, Math.round(n)));
}

/**
 * ACAL79 — la cible VENDUE d'un devis telle que l'atelier l'impose : le nombre de panneaux
 * du devis, arrondi, jamais plafonné (un devis vendu à 450 panneaux s'ouvre à 450, pas à
 * 400 — sinon le dialogue « Le calepinage diverge du devis » s'ouvrait à tort et sa
 * confirmation ramenait les lignes du devis à 400). `null` (aucune ligne panneau) ⇒ 0.
 */
export function besoinVendu(panneaux: number | null | undefined): number {
  return typeof panneaux === 'number' && Number.isFinite(panneaux) ? Math.max(0, Math.round(panneaux)) : 0;
}

/** ACAL356 — borne d'UN facteur annuel de dérate (WJ19/CAL93) : hors ]0;1[ ⇒ 1 (aucun dérate inventé). */
const borneDerate = (f: number | undefined): number => (typeof f === 'number' && f > 0 && f < 1 ? f : 1);
/** ACAL356 — LE dérate annuel de la production vivante : ombrage tracé × horizon lointain (deux
 *  postes qui se MULTIPLIENT), appliqué par `renderConfig`, les gagnants vivants et le document. */
export function facteurDerateAnnuel(c: Pick<Ctx, 'shadeAnnualFactor' | 'horizonAnnualFactor'>): number {
  return borneDerate(c.shadeAnnualFactor) * borneDerate(c.horizonAnnualFactor);
}

/** ACAL994/2022 — l'économie de l'année 1 SERVIE (`opts.chiffrage`, relu après « Enregistrer » par `majChiffrage`) remplace l'estimation de la carte
 *  et du Total : LUE du bloc servi, jamais calculée ici (ERP : sinon « au prochain enregistrement »). Site public (`chiffrage` absent) : l'estimation. */
const etatsEco = new WeakMap<object, { chiffrage: ChiffrageAtelier | null | undefined; estimes: Record<string, string>; kwcs: Record<string, number | null>; dernier: ChiffrageAtelier | null; horsLigne: boolean }>(); // T4-X9-003 — `kwcs` : le kWc posé de chaque case
const etatEco = (c: Pick<Ctx, 'opts'>) => {
  let e = etatsEco.get(c);
  if (!e) etatsEco.set(c, (e = { chiffrage: c.opts?.chiffrage, estimes: {}, kwcs: {}, dernier: c.opts?.chiffrage ?? null, horsLigne: false }));
  return e;
};
export function economieAffichee(c: Pick<Ctx, 'opts'>, id: 'carte' | 'total', estime: string, kwc?: number | null): string {
  const e = etatEco(c);
  e.estimes[id] = estime; if (kwc !== undefined) e.kwcs[id] = kwc; // T4-X9-003 — relu par majChiffrage : le Total reste contrôlé après « Enregistrer »
  return texteEconomie(e.chiffrage, e.kwcs[id], estime); // ACAL2022 — ERP : la servie (au kWc posé), sinon « au prochain enregistrement »
}

/** ACAL80 — le point de rendement PVGIS par défaut (pages publiques d'apps/web). */
export const RENDEMENT_PVGIS_DEFAUT = '/api/roof-yield';

/**
 * ACAL80 — LE seul appel au point de rendement. `url` null ⇒ AUCUNE requête : l'ERP n'a
 * pas cette route (son nginx ne sert pas apps/web — 42 erreurs 405 par ouverture de
 * l'atelier) ; l'appelant retombe alors sur la table committée (cache à null), exactement
 * comme quand PVGIS est injoignable. Rend le kWh annuel, ou null.
 */
export async function lireRendement(
  url: string | null,
  corps: unknown,
  fetcher: typeof fetch = fetch,
): Promise<number | null> {
  if (!url) return null;
  const res = await fetcher(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(corps),
  });
  const data = await res.json();
  return res.ok && data.ok && typeof data.annualKwh === 'number' ? data.annualKwh : null;
}

/** Dépendances injectées (rendu 3D + matrice + fenêtres + entrée). Les fonctions
 *  déclarées plus tard dans l'entrée sont passées en wrappers paresseux pour éviter
 *  les TDZ ; les modules frères sont passés directement. */
export interface OptimizerDeps {
  /** Rendu 3D d'une config (scene3d). */
  renderScene: RenderSceneFn;
  /** Repeint le tableau matrice (toit plat) — module matrix. */
  paintComparison: () => void;
  /** Surligne la ligne gagnante (ou null) du tableau comparatif — module matrix. */
  highlightRow: (id: string | null) => void;
  /** Reflète le plan gagnant dans la fenêtre de production — module prodWindow. */
  syncProductionWindow: () => void;
  /** Pré-remplit le diagnostic depuis la carte de résultat — module prefill. */
  prefillLead: (d: CardData) => void;
  /** Met à jour l'état pressé des puces de config — entrée. */
  syncChips: () => void;
  /** Repeint la carte « Optimum calculé » depuis la matrice — entrée. */
  renderMatrixOptimumCard: () => void;
  /** Facture mensuelle (MAD) saisie — entrée. */
  monthlyBill: () => number;
  /** ACAL777 — facture lue par les cartes seulement (saisie, sinon celle du lead) ; absente = `monthlyBill`. */
  factureCarte?: () => number;
  /** Anneaux lng/lat des obstacles (zones d'exclusion) — entrée. */
  obstructionRings: () => LngLat[][];
  /** PV61 — dégagement (m) de CHAQUE obstacle selon son type, même ordre que
   *  `obstructionRings()`. Optionnel : absent → dégagement uniforme (historique). */
  obstructionClearances?: () => number[];
  /** PV63 — retraits de rive SAISIS (latéral / extrémité / acrotère) quand la marge est
   *  gardée — entrée. Optionnel : absent → retrait unique PERIMETER_SETBACK_M. */
  setbacksOf?: () => PerimeterSetbacks;
  /** Affiche un message dans le bandeau de statut — entrée. */
  setStatus: (msg: string) => void;
}

export interface Optimizer {
  /** Cœur W34 : re-résolution CONTRAINTE vivante (toit plat) + rendu + badges. */
  liveResolveFlat: () => void;
  /** Cœur W35 : re-résolution CONTRAINTE vivante (toit en pente) + rendu + badges. */
  liveResolvePitched: () => void;
  /** Alias historique → liveResolveFlat (toit plat). */
  renderSelection: () => void;
  /** Rendu UNIFIÉ d'une config toit plat (carte + 3D + contrôles). */
  renderConfig: (o: RenderConfigOpts) => void;
  /** Recalcul/rendu de l'optimiseur en pente (recommandation + vivant + PVGIS). */
  pitchedRecompute: () => void;
  /** « Réinitialiser » (toit plat) : relâche tous les verrous → optimum global. */
  resetFlatLocks: () => void;
  /** « Réinitialiser » (toit en pente) : relâche pose/marge → optimum global. */
  resetPitchedLocks: () => void;
  /** Construit la matrice V6 (estimé) + repeint + re-résout — appelée par computeMatrixPvgis. */
  buildMatrix: (ring: LngLat[], bill: number) => void;
  /** Affine la matrice au PVGIS exact (coarse-then-fine) — appelée par recompute. */
  computeMatrixPvgis: () => Promise<void>;
  /** Plafonne le besoin (1–400, arrondi) — partagé avec l'entrée. */
  clampNeeded: (n: number) => number;
  /** ACAL470 — énergie annuelle par panneau de la carte affichée et nombre qui tient ; null sans carte. */
  peindreCartePosee: (n: number) => void; // ACAL1900 — l'ERP : la carte au nombre de la pose TENUE rendue (renderCustomLayout)
  etatCarte: () => { kwhParPanneau: number; tiennent: number; maxSens: MaxDuToit | null } | null; // ACAL1618, ACAL1903
}

/** ACAL975 — la phrase « gain bifacial » d'une carte : VIDE pour une pose affleurante (la face arrière n'y est
 *  pratiquement pas éclairée) ou sans production ; sinon la constante FLAT (E-O, < 12°) ou TILTED (sud incliné). */
export function libelleGainBifacial(d: Pick<CardData, 'annualKwh' | 'family' | 'tiltDeg' | 'flush'>): string {
  if (d.flush || !(d.annualKwh > 0)) return '';
  const gain = d.family === 'eastwest' || (d.tiltDeg != null && d.tiltDeg < 12) ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
  return `+ gain bifacial (estimation prudente, ~+${Math.round(gain * 100)} %) : ~${fmt(Math.round(d.annualKwh * gain))} kWh/an — non compté dans le chiffre ci-dessus.`;
}

export function createOptimizer(ctx: Ctx, deps: OptimizerDeps): Optimizer {
  const {
    renderScene,
    paintComparison,
    highlightRow,
    syncProductionWindow,
    prefillLead,
    syncChips,
    renderMatrixOptimumCard,
    monthlyBill,
    obstructionRings,
    setStatus,
  } = deps;
  const factureCarte = deps.factureCarte ?? monthlyBill; // ACAL777
  /** PV61 — dégagements par obstacle (type) ; dépendance absente → uniforme. */
  const obstructionClearances = (): number[] | undefined => deps.obstructionClearances?.();
  /** PV63 — retraits saisis quand la marge est GARDÉE ; absent → retrait unique. */
  const keepSetbacks = (): PerimeterSetbacks | undefined => deps.setbacksOf?.();
  /** PV63 — retraits effectifs d'une marge donnée : pleine rive = zéro partout. */
  const setbacksForMargin = (margin: 'keep' | 'remove'): PerimeterSetbacks | undefined =>
    margin === 'keep' ? keepSetbacks() : uniformSetbacks(0);

  /** CALX95 câblage — supplément de retrait PROPRE à chaque arête du pan actif, tel que le
   *  DOCUMENT le porte (`zones[].edges[].retraitM`, CALX81). Le retrait de CATÉGORIE passé
   *  ici est celui déjà appliqué au pourtour (retrait latéral saisi, sinon le retrait unique
   *  historique) : `supplementsParArete` ne retient que ce qu'une arête AJOUTE. Aucune arête
   *  saisie ⇒ table VIDE ⇒ anneau posable = contour tracé, pavage d'aujourd'hui. */
  const retraitsParArete = (): Record<number, number> =>
    supplementsParArete(ctx.activeArea()?.edges, keepSetbacks()?.lateralM ?? PERIMETER_SETBACK_M);

  /** CALX109 câblage — le catalogue CHOISISSABLE de la société, lu UNE fois (`ctx.opts` est
   *  figé au boot). Vide sans catalogue : l'atelier reste sur son module par défaut. */
  const catalogueModules = lireModulesDisponibles(ctx.opts?.modulesDisponibles).choisissables;
  /** ACAL80 — le point de rendement INJECTÉ par la page (null dans l'ERP : aucune requête). */
  const urlRendement: string | null =
    ctx.opts?.rendementPvgis === undefined ? RENDEMENT_PVGIS_DEFAUT : ctx.opts.rendementPvgis;

  /**
   * CALX109 câblage — les cotes du module posé sur le pan ACTIF, ou `undefined`.
   *
   * `undefined` dans DEUX cas, et c'est volontaire : (1) le pan n'a choisi aucun module —
   * l'option est alors ABSENTE du solve, donc `JSON.stringify(res)` est identique à celui
   * d'aujourd'hui, octet pour octet ; (2) le `moduleId` du pan est introuvable au catalogue ou
   * sa fiche n'a pas de cotes — on ne pave JAMAIS avec une dimension supposée (le refus, lui,
   * est déjà NOMMÉ par le sélecteur de `zones.ts`).
   */
  const cotesDuModuleDuPanActif = (): Panel2Module | undefined => {
    const moduleId = ctx.activeArea()?.moduleId;
    if (!moduleId) return undefined;
    // ACAL30 — un module archivé (repris du document) se pave avec SES cotes, jamais le défaut.
    const cotes = cotesPourPan(catalogueAvecModulesDuDocument(catalogueModules, ctx.modulesDuDocument).catalogue, moduleId);
    return estRefus(cotes) ? undefined : cotes;
  };
  /** ACAL851 — le module CHOISI du pan actif (même résolution que ses cotes), `null` sans choix. */
  const moduleDuPanActif = (): ModuleDocument | null => {
    const moduleId = ctx.activeArea()?.moduleId;
    if (!moduleId) return null;
    const module = resoudreModuleDuPan(catalogueAvecModulesDuDocument(catalogueModules, ctx.modulesDuDocument).catalogue, moduleId);
    return estRefus(module) ? null : module;
  }; const prodServieAuKwc = (k: number | null): number | null => (modeErp() ? productionServie(etatEco(ctx).chiffrage, k) : null); // T4-V2-021 — production servie au kWc posé

  /* ═════════ CALX115 — LE SEUIL D'ACCÈS SOLAIRE RETIRE DES EMPLACEMENTS DU POSABLE ═════════
     `optimisation.seuilAccesSolaire` (contrat CALX88) voyage par le DOCUMENT et arrive ici
     par le MÊME dépôt que la cible CALX114 (`poserChoixOptimisation`). Le pavage rend des
     CELLULES candidates ; celles dont l'accès solaire calculé est sous le seuil n'en sont
     pas : elles sortent du posable AVANT que la pose ne les retienne, et le nombre écarté
     est PUBLIÉ (jamais un compte qui baisse en silence).
     Sans seuil saisi — le défaut — rien n'est calculé du tout : `poseSousSeuil` rend le
     plafond de `placedFor` et aucun jeu de cellules, donc la pose et la 3D sont celles
     d'aujourd'hui, à l'emplacement près. */

  /** CALX115 — les emplacements d'un pavage jugés contre le seuil SAISI, ou `null` quand
   *  le document n'en porte aucun (cas par défaut : aucun calcul n'est lancé). */
  function filtrageSeuil(panels: readonly PackedPanel[]): FiltrageAccesSolaire | null {
    // ACAL548 — la valeur de CE dossier prime ; à défaut, le réglage de la société ; sans rien, aucun filtre.
    const seuil = choixOptimisationCourant()?.seuilAccesSolaire ?? seuilEffectifAccesSolaire(null, ctx.opts?.reglagesAtelier)?.valeur;
    if (seuil == null || seuil === '') return null;
    const { obstructions, source } = obstructionsEtSource();
    return filtrerEmplacementsSousSeuil(
      seuil,
      ctx.centroidLat,
      obstructions,
      ctx.prodPerKwc ?? fallbackPerKwc(),
      panels,
      source,
    );
  }

  /** ACAL552 — UNE définition des obstructions retenues et de la « source saisie » (`hasShadeSources`). */
  function obstructionsEtSource() {
    const hauteurM = hauteurToitPourOmbrageM(ctx.batiments, ctx.activeArea()?.buildingId);
    const obstructions = unifiedShadeEntries(
      ctx.shadeObstructions,
      ctx.obstacles,
      ctx.environment,
      ctx.centroid,
      hauteurM,
    );
    const source =
      ctx.shadeObstructions.length > 0 ||
      ctx.obstacles.some((o) => typeof o.heightM === 'number' && o.heightM > 0) ||
      (ctx.environment ?? []).some((o) => typeof o.heightM === 'number' && o.heightM > 0);
    return { obstructions, source };
  }

  /** ACAL552 — accès (0..1) par emplacement ; `null` sans source saisie. */
  function accesSolaireDe(panels: readonly { cx: number; cy: number }[]): number[] | null {
    const { obstructions, source } = obstructionsEtSource();
    if (!source) return null;
    return heatmapAccessValues(ctx.centroidLat, obstructions, ctx.prodPerKwc ?? fallbackPerKwc(), panels, null);
  }

  /** Dernière phrase de seuil annoncée — pour publier CHAQUE état une fois et ne pas
   *  répéter la même à chaque re-rendu. */
  let dernierMotifSeuil: string | null = null;

  /**
   * CALX115 — pose EFFECTIVE d'un pavage sous le seuil d'accès solaire SAISI :
   *  - `placed` = le plafond habituel (`placedFor`) diminué des emplacements écartés ;
   *  - `occupied` = les cellules à dessiner (absent = les `placed` premières, comme avant).
   * Aucun seuil saisi, seuil refusé, ou aucun emplacement sous le seuil ⇒ valeurs
   * STRICTEMENT identiques à aujourd'hui (`placedFor`, aucun jeu de cellules).
   */
  function poseSousSeuil(grid: PanelGrid, annoncer = true): { placed: number; occupied?: Set<number>; ecartes: number } {
    const plafond = placedFor(grid);
    const f = filtrageSeuil(grid.panels);
    if (!f) return { placed: plafond, ecartes: 0 };
    if (annoncer && (f.refuse || f.ecartes.length)) { // ACAL1533 — le chiffrage des deux sens n'annonce rien
      if (f.motif !== dernierMotifSeuil) {
        dernierMotifSeuil = f.motif;
        setStatus(f.motif);
      }
    }
    if (!f.ecartes.length) return { placed: plafond, ecartes: 0 };
    // La CAPACITÉ du pan baisse d'autant : le seuil retire des emplacements, il n'en
    // fabrique aucun ailleurs. Le plafond « besoin » s'applique ensuite à cette capacité
    // réduite, par la MÊME règle que partout (`placedFor`, qui ne lit que `count`).
    const capacite = Math.max(0, grid.panels.length - f.ecartes.length);
    const placed = placedFor({ ...grid, count: capacite });
    const ecartes = new Set(f.ecartes);
    const occupied = new Set<number>();
    for (let i = 0; i < grid.panels.length && occupied.size < placed; i++) {
      if (!ecartes.has(i)) occupied.add(i);
    }
    return { placed: occupied.size, occupied, ecartes: f.ecartes.length }; // ACAL1526 — le nombre écarté, pour la note
  }

  // — DOM propre à l'optimiseur (mêmes nœuds que l'entrée ; getElementById idempotent) —
  const needInputEl = $<HTMLInputElement>('rp9-need-input');
  const needMinusEl = $<HTMLButtonElement>('rp9-need-minus');
  const needPlusEl = $<HTMLButtonElement>('rp9-need-plus');
  const needNoteEl = $('rp9-need-note');
  const tiltRangeEl = $<HTMLInputElement>('rp9-tilt-range');
  const tiltValueEl = $('rp9-tilt-value');
  const tiltRecoBtn = $<HTMLButtonElement>('rp9-tilt-reco');
  const azimuthGroup = $('rp9-azimuth-group');
  const optimumNoteEl = $('rp9-optimum-note');
  const pitchValueEl = $('rp9-pitch-value');
  const pitchedNoteEl = $('rp9-pitched-note');

  // — Affinage PVGIS : clés de cache + jetons/timer anti-course (internes) —
  const pvgisKey = (family: ConfigFamily, tiltDeg: number, azimuthDeg: number): string =>
    `${ctx.centroid[1].toFixed(5)},${ctx.centroid[0].toFixed(5)}|${family}|${tiltDeg}|${Math.round(azimuthDeg)}`;
  const v4Key = (tiltDeg: number, aspect: number): string => `${Math.round(tiltDeg)}|${Math.round(aspect * 10) / 10}`;
  const pitchedKey = (pitch: number, facing: number): string => `${Math.round(pitch)}|${Math.round(facing)}`;
  let matrixToken = 0;
  let liveToken = 0;
  let liveTiltTimer: ReturnType<typeof setTimeout> | null = null;
  let pitchedToken = 0;

  // W1 — Aspect PVGIS (écart au sud) d'une famille selon son azimut de face réel :
  // Sud → azimut−180 ; E-O → azimut−90.
  const aspectForLeg = (family: ConfigFamily, azimuthDeg: number): number =>
    family === 'eastwest' ? azimuthDeg - 90 : azimuthDeg - 180;

  // — Plafond « panneaux nécessaires » (Change A) : la borne UNIQUE, au niveau du module
  // (ACAL79 — la copie de roof-tool-pro11.ts est supprimée). —
  /** Posés = min(plafond besoin, ce qui tient). Sans besoin (0) HORS devis (mode lead/
   *  estimateur) il n'y a pas de besoin à plafonner → on montre ce qui tient (comportement
   *  historique). L2 — EN DEVIS (`ctx.devisMode`), un besoin nul est une CIBLE VENDUE DE
   *  ZÉRO (devis sans ligne panneau, incident DEV-202608-0016) : on ne pose RIEN tant que
   *  personne (facture/saisie manuelle) n'a fixé un nombre — jamais un remplissage inventé.
   *  CAL37 — un document SANS cible vendue (`ctx.cibleVendue` faux : un calepinage sans
   *  devis lié) n'a rien vendu du tout : le besoin nul y redevient « aucune cible », et on
   *  montre ce qui tient, comme en mode lead. Devis/AO ne passent jamais ce drapeau. */
  // ACAL470 — énergie/panneau de la carte affichée + ce qui tient (lus par `cibleProduction`).
  // R3-04 — aussi la couverture (`pct`) de la tuile affichée ; R2-16 — et `factureInconnue`, pour repeindre la bande « Année 1 ».
  let derniereCarte: (CardData & { factureInconnue: boolean; sourceLabel?: string }) | null = null;
  let dernierFit = 0;
  let derniereNote: { fit: number; famille: string; motif?: MotifPanVide | null; ecartes?: number; pack?: PackResult | null } | null = null; // R2-13, ACAL1618
  /** ACAL1903 — le maximum que « + » ATTEINT : le gagnant vivant (mêmes verrous, besoin non plafonné) RE-PAVÉ et passé au seuil
   *  d'accès solaire comme au rendu (`paveDuGagnant`, `poseSousSeuil`), sa production écrêtée + dératée comme la carte ; `null` en pente. */
  const maxSensCarte = (): MaxDuToit | null => {
    const w = derniereNote?.pack ? resoudreVivant({ ...buildFlatLocks(), need: clampNeeded(Number.MAX_SAFE_INTEGER), needImposedZero: false }).winner : null;
    const grille = w ? paveDuGagnant(w).grid : null;
    const ecartes = grille ? filtrageSeuil(grille.panels)?.ecartes.length ?? 0 : 0;
    return maxDuSolveur(w, (g) => clipDcAcKwh(g.annualKwh, effectiveDcAcRatio(g.family)) * facteurDerateAnnuel(ctx), grille && ecartes ? grille.panels.length - ecartes : undefined);
  };
  const placedFor = (grid: PanelGrid): number =>
    ctx.neededPanels > 0
      ? Math.max(0, Math.min(ctx.neededPanels, grid.count))
      : ctx.devisMode && ctx.cibleVendue
        ? 0
        : grid.count;

  /** Synchronise le contrôle éditable + sa note honnête (besoin vs ce qui tient).
   *  L2 — en mode devis, les libellés parlent du DEVIS (jamais « votre facture », un
   *  champ qui n'existe même pas dans cet écran) et affichent « X posés / N au devis »
   *  (repère DOM stable `rp9-need-note`, préfixe HUD existant). */
  /** ACAL549 — cause mesurée du pan actif vide (besoin > 0, rien posé), notée pour le document. */
  const motifPanActif = (pack: PackResult, grid: PanelGrid, placed: number, retraitM: number | null, module?: Panel2Module): MotifPanVide | null =>
    noterMotifPanVide(ctx.activeAreaId, ctx.neededPanels > 0 && placed === 0
      ? causeDuPanVide(mesurerPanVide(pack, grid, retraitM, cotesDePavage(module), filtrageSeuil(grid.panels), contourPanENU(ctx.vertices), retraitsParArete())) : null);
  /** R2-13/22/23 — l'atelier ERP (`opts.chiffrage` défini, `null` compris) dit « cible » pour LA cible servie (`cibleServie`) — sans cible servie, pour le nombre MODIFIABLE comme avant — et « au devis » que pour un devis lié (compte réel de CE devis). Site public : libellé d'avant. */
  const modeErp = (): boolean => ctx.opts?.chiffrage !== undefined; const wattPose = (): number => (moduleDuPanActif() ?? MODULE_PAR_DEFAUT_ATELIER).pmaxWc; const besoinFacture = (): number | null => besoinDeLaFacture(ctx.opts, wattPose()); const cibleServie = () => cibleDeLAtelier(ctx, wattPose()); // T4-X8-012 — le besoin de la facture au module posé (servi)
  const surDevis = (placed: number): string => texteSurDevis(placed, ctx.neededPanels, modeErp(), Boolean(ctx.opts?.devisLie && ctx.cibleVendue), ctx.panneauxDevis, quiDuDevis(ctx.opts), cibleServie()); // ACAL1951, T4-X8-012 (une cible)
  /** ACAL1526 — `ecartes` = emplacements retirés par le seuil d'accès solaire (`poseSousSeuil`) : la capacité dite
   *  est celle qui reste, donc la note lit la pose DESSINÉE (jamais « il reste de la place » sur une pose rognée). */
  function syncNeedControl(fitCount: number, familyLabel: string, motif?: MotifPanVide | null, ecartes = 0, pack: PackResult | null = null) {
    dernierFit = fitCount;
    derniereNote = { fit: fitCount, famille: familyLabel, motif, ecartes, pack };
    const capacite = Math.max(0, fitCount - ecartes);
    const active = ctx.neededPanels > 0;
    // L2 — en mode devis, le champ reste ACTIONNABLE même à 0 : aucune facture n'existe
    // dans cet écran pour dériver un besoin automatiquement (le champ facture est retiré
    // en devis), donc la SEULE porte de sortie d'une cible imposée à zéro est la saisie
    // manuelle/+ — désactiver le champ à 0 comme en mode lead la condamnerait pour de bon
    // (« fixez le nombre » sans aucun moyen de le faire). Mode lead inchangé : le champ
    // reste désactivé tant qu'aucune facture n'a dérivé un besoin.
    const editable = active || ctx.devisMode;
    if (needInputEl) {
      needInputEl.disabled = !editable;
      peindreChampBesoin(needInputEl, active ? ctx.neededPanels : 0, modeErp(), modeErp() ? besoinFacture() : null, document.activeElement !== needInputEl); // T4-X8-012 — « le plus » : le besoin de la facture, jamais 400
    }
    if (needMinusEl) needMinusEl.disabled = !active || ctx.neededPanels <= 1;
    if (needPlusEl) needPlusEl.disabled = !editable || ctx.neededPanels >= 400;
    if (!needNoteEl) return;
    if (!active) {
      // CAL37 — trois situations DISTINCTES, jamais la phrase d'une autre : un devis
      // sans ligne panneau (cible vendue de zéro), un calepinage sans cible du tout
      // (on pose ce qui tient), et le mode lead (la facture dimensionne).
      needNoteEl.textContent = ctx.devisMode && ctx.cibleVendue
        ? 'Ce devis ne porte aucun panneau — fixez le nombre (facture ou saisie) pour poser des modules.'
        : ctx.devisMode
          ? `${cibleServie() ? `La cible est de ${fmt(cibleServie()!.panneaux)} panneaux (${cibleServie()!.origine})` : 'Aucune cible de puissance sur ce calepinage'} — on pose ce qui tient (${fmt(fitCount)}). Saisissez un nombre pour le plafonner.`
          : 'Indiquez votre facture pour dimensionner le nombre de panneaux.';
      return;
    }
    const placed = motif ? 0 : Math.min(ctx.neededPanels, capacite); // ACAL549 — un motif = un pan vide mesuré
    if (placed < ctx.neededPanels && !motif && ecartes > 0) {
      const s = ecartes > 1 ? 's' : '';
      const seuil = `${fmt(ecartes)} emplacement${s} écarté${s} par le seuil d’accès solaire`; // ACAL1526
      needNoteEl.textContent = ctx.devisMode ? `${surDevis(placed)} — ${seuil}.` : `${fmt(ctx.neededPanels)} nécessaires — ${seuil}. On pose ${fmt(placed)}.`;
    } else if (placed < ctx.neededPanels) {
      const cause = motif ? ` — ${motif.message}` : ' (toit ou obstacles)'; // ACAL549
      needNoteEl.textContent = ctx.devisMode
        ? `${surDevis(placed)} — ${phraseTiennent(placed, cibleServie())} en ${familyLabel}${cause}.`
        : `${fmt(ctx.neededPanels)} nécessaires — ${fmt(placed)} tiennent en ${familyLabel}${cause}. On pose ${fmt(placed)}.`;
    } else if (capacite > ctx.neededPanels) {
      needNoteEl.textContent = ctx.devisMode
        ? `${surDevis(placed)} — il reste de la place sur le toit, laissée libre.`
        : `${fmt(ctx.neededPanels)} couvrent votre facture (+10 %) — il reste de la place sur le toit, laissée libre.`;
    } else {
      needNoteEl.textContent = ctx.devisMode ? `${surDevis(placed)}.` : `On pose ${fmt(placed)} panneaux.`;
    } needNoteEl.textContent = modeErp() && estLePlus(ctx.neededPanels) && !motif ? noteLePlus(placed, besoinFacture()) : noteTailleAuto(ctx, placed, derniereCarte, needNoteEl.textContent ?? '', surDevis(placed)); // ACAL1331, T4-X8-012 — le choix dit en mots
  }

  // WJ19 — dérate d'ombrage tracé appliqué aux chiffres ANNUELS affichés (1 = aucun
  // ombrage → identique à avant). Les économies sont recalculées depuis le kWh dératé,
  // donc elles restent plafonnées à la facture. Le libellé de source l'affiche.
  const shadeFactor = (): number => borneDerate(ctx.shadeAnnualFactor);
  const shadeLabel = (): string => {
    const f = shadeFactor();
    return f < 1 ? ` · ombrage tracé −${Math.round((1 - f) * 100)} %` : '';
  };
  // CAL93 — dérate d'HORIZON LOINTAIN, TOUJOURS un poste SÉPARÉ de l'ombrage proche
  // ci-dessus (jamais fondu dans `shadeFactor`) : les deux facteurs se MULTIPLIENT.
  // 1 = aucun profil d'horizon renseigné → chiffres strictement inchangés.
  const horizonFactor = (): number => borneDerate(ctx.horizonAnnualFactor);
  const horizonLabel = (): string => {
    const f = horizonFactor();
    return f < 1 ? ` · horizon PVGIS −${Math.round((1 - f) * 100)} %` : '';
  };

  /** Rendu UNIFIÉ : pose min(besoin, ce qui tient), recalcule kWc/kWh/économies
   *  depuis ce nombre POSÉ (jamais la capacité max de la config). */
  function renderConfig(o: RenderConfigOpts) {
    // CALX115 — la pose suit le seuil d'accès solaire SAISI ; sans seuil, `placed` vaut
    // exactement `placedFor(o.grid)` et `occupied` est absent (rendu d'aujourd'hui).
    const { placed, occupied, ecartes } = poseSousSeuil(o.grid);
    const kwc = o.grid.count > 0 ? (o.grid.kwc * placed) / o.grid.count : 0;
    // W1 : production à l'aspect réel (le rendement/panneau baisse honnêtement
    // quand l'array suit un toit tourné).
    const aspect = aspectForLeg(o.family, o.azimuthDeg);
    const tableAnnual = productionKwh(ctx.centroidLat, o.family, o.tiltDeg, kwc, aspect);
    // Affinage PVGIS : rendement par kWc × kWc POSÉ (suit le plafond/contrainte).
    // WJ19 — puis dérate d'ombrage tracé (1 = aucun → inchangé).
    const annualKwh =
      (o.isReco && ctx.pvgisPerKwc != null ? ctx.pvgisPerKwc * kwc : tableAnnual) * facteurDerateAnnuel(ctx);
    const target = ctx.rec && ctx.rec.targetAnnualKwh > 0 ? ctx.rec.targetAnnualKwh : billToAnnualKwh(factureCarte()); // ACAL777
    const savings = annualSavingsMad(annualKwh, target); // plafonné à la conso
    renderScene(o.pack, o.grid, o.tiltDeg, o.family, placed, false, occupied); // CALX115
    majNoteChassis(o.pack, o.grid); // ACAL585 — « n châssis de N × M posés » ou le motif
    afficherSensDePose(lignesSensDePose(o.pack, accesSolaireDe, (g) => poseSousSeuil(g as PanelGrid, false)), { // ACAL552, ACAL1533
      affichee: o.grid === o.pack.portrait ? 'portrait' : o.grid === o.pack.landscape ? 'landscape' : undefined,
      choisir: (sens) => choisirSensDePose(sens, { family: o.family, tilt: o.tiltDeg, azimuth: ctx.sel.azimuth, margin: ctx.sel.margin }),
    });
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
        family: o.family,
        tiltDeg: o.tiltDeg,
        target,
      },
      o.sourceLabel,
    );
    syncNeedControl(o.grid.count, o.family === 'eastwest' ? 'Est-Ouest' : 'plein sud', motifPanActif(o.pack, o.grid, placed, null), ecartes, o.pack); // ACAL549 : retrait non transmis ici ; ACAL1526, ACAL1618
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
    if (tiltRecoBtn) tiltRecoBtn.setAttribute('aria-pressed', String(isReco && ctx.useRecommended));
  }

  // ═════════════ W34 — OPTIMISEUR CONTRAINT VIVANT (toit plat, cerveau V7) ═════════════
  // renderSelection() est un ALIAS de liveResolveFlat() : recompute, renderActive et tous
  // les handlers d'options passent par le solveur vivant. Chaque option est un AXE ; un
  // clic VERROUILLE cet axe (épingle dans `pinned`) et RE-RÉSOUT en direct tous les axes
  // encore AUTO (les verrous s'accumulent), via solveLive (V7, PVGIS au GPS exact, repli
  // table « estimé »). Chaque groupe affiche la valeur « Recommandé » = la valeur que cet
  // axe prendrait s'il était libéré, les autres verrous tenus.

  /** Verrous courants dérivés des axes épinglés (pinned) + de la cible « besoin ».
   *  L'orientation (un seul axe V7) est reconstruite depuis les groupes Orientation
   *  (famille) et Azimut de la page.
   *  L2 — c'est ICI, pas `placedFor` (qui ne gate que le rendu d'une carte matrice
   *  choisie manuellement), que passe le rendu PRIMAIRE (`liveResolveFlat`, appelé à
   *  CHAQUE recompute — dont l'hydratation devis au boot) : en mode devis avec un
   *  besoin nul (cible vendue de zéro, devis sans ligne panneau), on IMPOSE
   *  `needImposedZero` pour que `solveLive` (estimatorBrainV7) ne retombe pas sur son
   *  repli « remplir ce qui tient » — voir sa docstring. Mode lead/estimateur inchangé. */
  function buildFlatLocks(): AxisLocks {
    const locks: AxisLocks = {};
    if (ctx.pinned.has('family') && ctx.sel.family === 'eastwest') locks.orientation = 'eastwest';
    else if (ctx.pinned.has('azimuth') && ctx.sel.azimuth === 'aligned') locks.orientation = 'aligned';
    else if ((ctx.pinned.has('family') && ctx.sel.family === 'south') || (ctx.pinned.has('azimuth') && ctx.sel.azimuth === 'south'))
      locks.orientation = 'south';
    if (ctx.pinned.has('tilt') && ctx.sel.tilt !== 'reco') locks.tiltDeg = ctx.sel.tilt;
    if (ctx.pinned.has('orient') && ctx.sel.orient !== 'auto') locks.layout = ctx.sel.orient as LayoutAxis;
    if (ctx.pinned.has('margin')) locks.margin = ctx.sel.margin;
    const besoin = ctx.neededAuto ? besoinAutoRelu(ctx.documentRelu, ctx.activeAreaId, monthlyBill()) : ctx.neededPanels; // ACAL367
    if (besoin > 0) locks.need = besoin;
    if (ctx.devisMode && ctx.cibleVendue && ctx.neededPanels <= 0) locks.needImposedZero = true;
    return locks;
  }

  /** Reflète le gagnant courant dans `sel` (miroir d'affichage des puces). */
  function mapWinnerToSel(w: LiveConfigEval) {
    ctx.sel = {
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
  /** Re-pave le gagnant vivant (rendu ET maximum « + », ACAL1903) : son pack et sa grille. */
  function paveDuGagnant(w: LiveSolveResult['winner']) {
    // CALX95 câblage — on re-pave le MÊME anneau posable que le solveur a évalué (retraits
    // d'arête rognés) ; sinon le compte affiché parlerait d'un contour que le solveur n'a
    // pas vu. Aucune arête saisie ⇒ c'est le contour tracé lui-même, rendu inchangé.
    const ring: LngLat[] = anneauPosableParArete([...ctx.vertices], retraitsParArete());
    const setbackM = w.margin === 'keep' ? PERIMETER_SETBACK_M : 0;
    const pack = packConfig(ring, ctx.centroidLat, {
      family: w.family,
      tiltDeg: w.tiltDeg,
      azimuthDeg: w.azimuthDeg,
      obstructions: obstructionRings(),
      obstructionClearancesM: obstructionClearances(), // PV61 — dégagement par type
      setbacksM: setbacksForMargin(w.margin), // PV63 — latéral / extrémité / acrotère
      setbackM,
      overhangM: ctx.overhangM, // W109 — le gagnant rendu déborde comme le solve l'a évalué
      colGapM: ctx.colGapM, // CAL75 — écart réglable, re-pavé à chaud (défaut : inchangé)
      rowGapExtraM: ctx.rowGapExtraM,
      module: cotesDuModuleDuPanActif(), // ACAL1523 — les cotes du module DU PAN, comme le solveur
      chassis: optionChassis(ctx.activeArea?.()?.chassis), // ACAL1523 — le châssis N × M saisi, comme le solveur
    });
    // PV62 — pose MIXTE : grille dédiée du pack (repli meilleur uniforme si le mixte perd).
    return { pack, setbackM, grid: w.layout === 'mixed' ? pack.mixed ?? pack.best : w.layout === 'portrait' ? pack.portrait : pack.landscape };
  }
  function renderLiveWinner(res: LiveSolveResult, isReco: boolean) {
    const w = res.winner;
    const { pack, grid, setbackM } = paveDuGagnant(w);
    // CAL75 — le solveur (V7) a choisi cette config à l'écart D'ÉTUDE ; un écart personnalisé
    // change ce qui tient VRAIMENT dans ce même contour → le compte AFFICHÉ vient du pack
    // RE-PAVÉ (placedFor, même plafond besoin que partout ailleurs), kWc/kWh mis à l'échelle
    // du VRAI compte rendu (jamais un chiffre en désaccord avec la 3D affichée). Écart
    // absent/par défaut → grid.count === w.placedCount → scale = 1 → chiffres INCHANGÉS.
    // CALX115 — le seuil d'accès solaire SAISI retire ses emplacements du posable AVANT
    // que la pose ne les retienne ; sans seuil, `placedCount` vaut exactement
    // `placedFor(grid)` et `occupied` est absent — chiffres et 3D INCHANGÉS.
    const { placed: placedCount, occupied, ecartes } = poseSousSeuil(grid);
    const gapScale = w.placedCount > 0 ? placedCount / w.placedCount : placedCount > 0 ? 1 : 0;
    renderScene(pack, grid, w.tiltDeg, w.family, placedCount, false, occupied);
    majNoteChassis(pack, grid); // ACAL1523 — « n châssis de N × M posés » ou le motif, comme renderConfig
    afficherSensDePose(lignesSensDePose(pack, accesSolaireDe, (g) => poseSousSeuil(g as PanelGrid, false)), { // ACAL552, ACAL1533
      affichee: w.layout,
      choisir: (sens) => choisirSensDePose(sens, { family: w.family, tilt: w.tiltDeg, azimuth: w.orientation === 'aligned' ? 'aligned' : 'south', margin: w.margin }),
    });
    // W94 — écrête la production AFFICHÉE au plafond AC de l'onduleur (le solveur V7
    // calcule le kWh DC brut sans clip) : un Sud est inchangé (ratio = design), une
    // « tente » E-O sur-densifiée est ramenée sous la valeur non écrêtée. On recalcule
    // couverture + économies (plafonnées à la conso) à partir du kWh écrêté.
    // ACAL356 — puis le dérate ombrage × horizon de `renderConfig` (1 ⇒ inchangé).
    const annualKwh = clipDcAcKwh(w.annualKwh, effectiveDcAcRatio(w.family)) * gapScale * facteurDerateAnnuel(ctx);
    const kwc = w.kwc * gapScale;
    const target = ctx.rec && ctx.rec.targetAnnualKwh > 0 ? ctx.rec.targetAnnualKwh : billToAnnualKwh(factureCarte()); // ACAL777
    const savings = annualSavingsMad(annualKwh, target);
    const pct = target > 0 ? (annualKwh / target) * 100 : 0;
    const cov = Math.round(pct);
    // W74 — AUCUNE config viable (toit trop petit / contraint à néant) : on n'affiche
    // PAS un faux « 0 panneau gagnant », mais un message honnête.
    // L2 — devis sans ligne panneau (cible vendue = 0) : message dédié AVANT le générique
    // « facture » (absente en devis) — jamais un calepinage inventé sur un toit viable.
    const why = res.noViableConfig
      ? `Configuration non viable sur ce toit : aucun panneau ne tient (tracé trop petit ou entièrement occupé par des obstacles). Agrandissez la zone ou retirez des obstacles.`
      : ctx.devisMode && ctx.cibleVendue && ctx.neededPanels <= 0
        ? `Ce devis ne porte aucun panneau — aucune pose proposée. Fixez un nombre (facture ou saisie) pour calepiner.`
        : isReco
          ? `Meilleure combinaison pour votre facture : ${liveOrientationLabel(w)} à ${w.tiltDeg}°, ${placedCount} panneaux${couverture(target, cov)}. Touchez une option pour la verrouiller — le reste se re-résout.`
          : `Vos choix sont tenus, le reste a été re-résolu : ${placedCount} panneaux${couverture(target, cov)}. Les badges « Recommandé » montrent l'option optimale de chaque groupe.`;
    paintCard(
      {
        title: `${liveOrientationLabel(w)} ${w.tiltDeg}° · ${w.layoutLabel}`,
        isReco,
        count: placedCount,
        kwc,
        annualKwh,
        pct,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why,
        family: w.family,
        tiltDeg: w.tiltDeg,
        target,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS au GPS exact)' : '(production estimée — table par latitude)',
    );
    syncNeedControl(grid.count, liveOrientationLabel(w), motifPanActif(pack, grid, placedCount, retraitApplique(setbacksForMargin(w.margin), setbackM)), ecartes, pack); // ACAL1526, ACAL1618
    syncTiltControl(w.tiltDeg, isReco);
    paintMaxLine();
    highlightRow(null);
    if (optimumNoteEl) {
      optimumNoteEl.textContent = isReco
        ? 'Optimum vivant : tout est calé sur la meilleure combinaison (chaque groupe badgé « Recommandé »). Verrouillez une option et le reste se re-résout en direct.'
        : 'Optimum vivant : votre choix est tenu, le reste se re-résout pour maximiser la génération. « Réinitialiser » relâche tous les verrous.';
    }
  }

  // ═══════ CAL87 — GÉOMÉTRIE EST-OUEST PARAMÉTRABLE (faîtage + écart inter-chevrons) ═══════
  // L'est-ouest dos à dos existait comme variante CALCULÉE, mais son faîtage et son écart
  // entre chevrons étaient FIGÉS dans le pavage. On les expose : deux champs SAISIS, dont
  // les valeurs par défaut sont EXACTEMENT celles appliquées aujourd'hui (affichées comme
  // telles). Laisser les champs à leur défaut ⇒ variante est-ouest IDENTIQUE. La politique
  // d'espacement du NOYAU (ombre de faîte est-ouest) reste à CAL167 : rien ici ne touche
  // `core/calepinage`.

  /** Saisie utilisateur (m) ou null = « valeur par défaut affichée ». */
  let ewRidgeGapM: number | null = null;
  let ewInterTentGapM: number | null = null;

  /** CAL87 — l'inclinaison est-ouest courante, pour calculer les valeurs par défaut à
   *  AFFICHER (et elles seules : le pavage, lui, les recalcule à chaque inclinaison). */
  const ewTiltDeg = (): number => {
    const t = ctx.liveResult?.winner?.tiltDeg;
    return typeof t === 'number' && Number.isFinite(t) && t > 0 ? t : EW_DEFAULT_TILT_DEG;
  };

  /** CAL87 — valeurs par défaut affichées dans les champs : celles du pavage d'aujourd'hui. */
  function ewDefaults(): { ridgeGapM: number; interTentGapM: number } {
    return defaultEastWestGeometry(ctx.centroidLat, ewTiltDeg(), PANEL2_SHORT_M);
  }

  /** CAL87 — ce qui part au solveur : `undefined` tant que RIEN n'a été saisi (le pavage
   *  garde alors son comportement d'aujourd'hui, au byte près). */
  function eastWestGeometryInput(): EastWestGeometry | undefined {
    if (ewRidgeGapM == null && ewInterTentGapM == null) return undefined;
    return {
      ...(ewRidgeGapM != null ? { ridgeGapM: ewRidgeGapM } : {}),
      ...(ewInterTentGapM != null ? { interTentGapM: ewInterTentGapM } : {}),
    };
  }

  const ewRidgeEl = $<HTMLInputElement>('rp9-ew-ridge');
  const ewGapEl = $<HTMLInputElement>('rp9-ew-gap');
  const ewNoteEl = $('rp9-ew-note');

  /** CAL87 — remet les libellés à jour : une valeur SAISIE est annoncée comme saisie, un
   *  champ vide affiche la valeur appliquée par défaut, annoncée comme telle. */
  function syncEwUi() {
    const d = ewDefaults();
    const m = (n: number) => `${n.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} m`;
    if (ewRidgeEl && document.activeElement !== ewRidgeEl) {
      ewRidgeEl.placeholder = m(d.ridgeGapM);
      if (ewRidgeGapM == null) ewRidgeEl.value = '';
    }
    if (ewGapEl && document.activeElement !== ewGapEl) {
      ewGapEl.placeholder = m(d.interTentGapM);
      if (ewInterTentGapM == null) ewGapEl.value = '';
    }
    if (ewNoteEl) {
      ewNoteEl.textContent =
        `Est-Ouest dos à dos — faîtage ${ewRidgeGapM != null ? `${m(ewRidgeGapM)} (saisi)` : `${m(d.ridgeGapM)} (valeur appliquée aujourd’hui)`}, ` +
        `écart entre chevrons ${ewInterTentGapM != null ? `${m(ewInterTentGapM)} (saisi)` : `${m(d.interTentGapM)} (ombre de faîte résiduelle + passage de maintenance, valeur appliquée aujourd’hui)`}.`;
    }
  }

  /** CAL87 — lecture d'un champ : vide ⇒ retour au défaut ; négatif ⇒ 0 ; sinon la valeur
   *  telle quelle (on n'arrondit ni ne rejette une frappe — règle de la maison). */
  function readEwInput(raw: string): number | null {
    const cleaned = String(raw ?? '').replace(/\s/g, '').replace(',', '.').trim();
    if (!cleaned) return null;
    const v = Number(cleaned);
    if (!Number.isFinite(v)) return null;
    return v < 0 ? 0 : v;
  }

  ewRidgeEl?.addEventListener('change', () => {
    ewRidgeGapM = readEwInput(ewRidgeEl.value);
    syncEwUi();
    liveResolveFlat();
  });
  ewGapEl?.addEventListener('change', () => {
    ewInterTentGapM = readEwInput(ewGapEl.value);
    syncEwUi();
    liveResolveFlat();
  });

  /** ACAL1533 — un clic sur « Portrait : N panneaux » / « Paysage : … » : la pose AFFICHÉE est tenue (famille,
   *  inclinaison, azimut, marge verrouillés comme une carte de variante, PV64) et seul le sens change — le nombre
   *  annoncé, chiffré sur ce même pavage par `poseSousSeuil`, est donc celui qu'on obtient ; la marge ne bouge pas. */
  function choisirSensDePose(sens: 'portrait' | 'landscape', tenue: { family: ConfigFamily; tilt: number; azimuth: 'south' | 'aligned'; margin: 'keep' | 'remove' }) {
    ctx.sel = { family: tenue.family, tilt: tenue.tilt, orient: sens, azimuth: tenue.azimuth, margin: tenue.margin };
    for (const axe of ['family', 'tilt', 'orient', 'azimuth', 'margin'] as const) ctx.pinned.add(axe);
    ctx.useRecommended = false;
    liveResolveFlat();
  }

  /** Cœur W34 : re-résolution CONTRAINTE vivante (verrous courants) + rendu + badges. */
  /** ACAL574 — un pan « existant » ne se re-résout pas : ses modules restent ceux posés (refus nommé).
   *  ACAL1404 — seulement une fois sa pose affichée (`ctx.layoutPlan`) : au chargement (hydratation, pan rouvert,
   *  plan remis à null) il se pave pour que `hydrateLayout` y repose la pose enregistrée, sans rien dire ;
   *  `annoncer` faux = recalcul de fond (affinage PVGIS), qui n'est pas un geste : refus muet. */
  function refusPanExistant(annoncer = true): boolean {
    if (!ctx.layoutPlan) return false;
    const i = Array.isArray(ctx.areas) ? ctx.areas.findIndex((a) => a.id === ctx.activeAreaId) : -1;
    const motif = i >= 0 ? motifPanExistant(ctx.areas[i], i) : null;
    if (motif && annoncer) setStatus(motif);
    return motif != null;
  }
  /** ACAL1903 — le solveur vivant du pan actif sous des verrous donnés : le rendu courant, ou le maximum du toit. */
  const resoudreVivant = (locks: AxisLocks) => solveLive([...ctx.vertices], ctx.centroidLat, monthlyBill(), obstructionRings(), locks, {
      yieldFn: (tiltDeg: number, aspect: number): number | null => ctx.v4YieldCache.get(v4Key(tiltDeg, aspect)) ?? null,
      overhangM: ctx.overhangM,
      obstructionClearancesM: obstructionClearances(), // PV61
      setbacksM: keepSetbacks(), // PV63
      retraitsParAreteM: retraitsParArete(), // CALX95 — retrait propre à chaque arête saisie
      eastWestGeometry: eastWestGeometryInput(), // CAL87 — faîtage + écart inter-chevrons saisis
      module: cotesDuModuleDuPanActif(), // CALX109 — vraies cotes du module posé sur ce pan
      chassis: optionChassis(ctx.activeArea?.()?.chassis), // ACAL585 — châssis N × M saisi sur ce pan
    });
  function liveResolveFlat(annoncer = true) {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'flat' || refusPanExistant(annoncer) || (!annoncer && poseTenue(ctx))) return; // ACAL1900 — le fond ne re-pose pas une pose tenue
    const locks = buildFlatLocks();
    const res = resoudreVivant(locks);
    ctx.liveResult = res;
    if (ctx.neededAuto) ctx.neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : besoinAutoRelu(ctx.documentRelu, ctx.activeAreaId, monthlyBill());
    const hasLocks = !!(locks.orientation || locks.tiltDeg != null || locks.layout || locks.margin || locks.need != null);
    ctx.useRecommended = !hasLocks;
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
    if (ctx.roofType !== 'flat' || locks.tiltDeg == null || !ctx.closed) return;
    const t = Math.round(locks.tiltDeg);
    const roofAz = roofDominantAzimuthDeg([...ctx.vertices]);
    const aspects = [...new Set(pvgisMatrixCandidatePairs(ctx.centroidLat, roofAz).map((p) => p.aspect))];
    const missing = aspects.filter((a) => !ctx.v4YieldCache.has(v4Key(t, a)));
    if (!missing.length) return;
    if (liveTiltTimer != null) clearTimeout(liveTiltTimer);
    const token = ++liveToken;
    liveTiltTimer = setTimeout(() => {
      void Promise.all(missing.map((a) => v4SpecificYield(t, a))).then(() => {
        if (token !== liveToken || ctx.roofType !== 'flat') return;
        liveResolveFlat(false); // ACAL1900 — affinage de fond (débattu), pas un geste
      });
    }, 280);
  }

  /** « Réinitialiser » (toit plat) : relâche TOUS les verrous → optimum global. */
  function resetFlatLocks() {
    ctx.pinned.clear();
    ctx.neededAuto = true;
    ctx.useRecommended = true;
    liveResolveFlat();
  }

  /** renderSelection : alias historique → solveur vivant (toit plat). */
  function renderSelection() {
    liveResolveFlat();
  }

  /** V1-02 — la cible (kWh/an) d'une carte : celle du solveur si positive, sinon la facture du lead servie (ACAL777), sinon 0. */
  const cibleDeCarte = (cibleSolveur: number): number => (cibleSolveur > 0 ? cibleSolveur : billToAnnualKwh(factureCarte()));

  /** ACAL852 — la phrase de couverture : « ≈ N % de la facture », ou « facture inconnue » quand la cible est absente ou nulle. */
  const couverture = (target: number, cov: number) => // T4-X5-005 — ERP : aucun pourcentage dans la phrase (la part est dans sa case)
    suiteCouverture(target, cov, modeErp());

  /** ACAL994/2022 — d'où vient l'économie : servie ⇒ « au dernier enregistrement » (+ option) ; hors ligne ⇒ dernier calcul ; sinon « au prochain enregistrement ». Site public : aucune ligne. */
  function etiquetteEconomie() {
    const hote = $('rp9-reco-savings');
    if (!hote) return;
    const { chiffrage } = etatEco(ctx);
    let ligne = hote.parentElement?.querySelector<HTMLElement>('[data-economie-etat]') ?? null;
    if (chiffrage === undefined) return void ligne?.remove();
    if (!ligne) {
      ligne = document.createElement('p');
      ligne.className = 'mt-1 text-xs text-muted-foreground';
      ligne.setAttribute('data-economie-etat', '');
      hote.insertAdjacentElement('afterend', ligne);
    }
    const eco = chiffrage?.economie_annee1_mad;
    ligne.textContent = etatEco(ctx).horsLigne ? VALEURS_HORS_LIGNE : eco?.etat === 'servi' && typeof eco.valeur === 'number'
      ? `au dernier enregistrement${eco.option ? ` · ${eco.option.replace(/_/g, ' ')}` : ''}`
      : raisonSansValeur(chiffrage, derniereCarte?.kwc, 'économie').replace(/^—$/, ''); // T4-X9-007 (la phrase est sous les cartes) ; ACAL2022 + M5 (la vraie raison, avec les deux tailles) — l'estimation du navigateur n'est plus montrée en ERP
  }

  /** ACAL994 — après « Enregistrer » : le bloc relu remplace le précédent ; la carte et le Total sont repeints à l'instant. */
  function majChiffrage(chiffrage: ChiffrageAtelier | null, panneauxDevis?: number | null) {
    if (panneauxDevis !== undefined) ctx.panneauxDevis = compteDevis(panneauxDevis); // R2-13 — le compte du devis relu avec le contexte
    const e = etatEco(ctx);
    e.horsLigne = chiffrage === null && e.dernier != null; if (chiffrage) e.dernier = chiffrage; e.chiffrage = e.horsLigne ? e.dernier : chiffrage; // ACAL2022 — hors ligne après un servi : dernier calcul, dit
    if (ctx.opts) ctx.opts.chiffrage = e.chiffrage; // demande croisée — le Total (zones.ts) relit le bloc relu
    const cibles = [['carte', $('rp9-reco-savings')], ['total', ctx.dom.areasTotalSavingsEl]] as const;
    for (const [id, el] of cibles) if (el && e.estimes[id] !== undefined) el.textContent = economieAffichee(ctx, id, e.estimes[id]); // T4-X9-003 — le kWc mémorisé de chaque case (celui que la carte et le Total ont peint)
    etiquetteEconomie();
    if (derniereCarte) paintCard(derniereCarte, derniereCarte.sourceLabel); // R2-16 + demande croisée — production, bande et économie relues
    if (derniereNote) syncNeedControl(derniereNote.fit, derniereNote.famille, derniereNote.motif, derniereNote.ecartes, derniereNote.pack); // R2-13, ACAL1526 — « au devis » relu avec le contexte
    if (derniereCarte?.tenue) direEcartALaPose(derniereCarte.count, ctx, wattPose(), fmt, false, suiteAuDevis(ctx)); } // ACAL1900, ACAL1951 — la note du nombre parle de la pose tenue

  /** ACAL1900 — l'ERP : la carte (et ce qui la lit : bande, indicateurs, Guidé) suit la pose TENUE rendue (n panneaux). */
  function peindreCartePosee(n: number) { const d = modeErp() && derniereCarte ? carteDeLaPoseTenue(derniereCarte, n, fmt) : null; if (d) { paintCard(d, derniereCarte?.sourceLabel); direEcartALaPose(n, ctx, wattPose(), fmt, false, suiteAuDevis(ctx)); } }
  /** ACAL1914 — la part des panneaux du pan actif que les chaînes raccordent (table servie), ou `null` : estimation inchangée. */
  const partRaccordee = (): number | null => partRaccordeeDuPan(ctx.affectationColoration, ctx.activeAreaId);
  /** ACAL1914 — la table d'affectation vient d'arriver : la carte est repeinte avec la même estimation, comptée sur les raccordés. */
  function repeindreCarte() { if (derniereCarte) paintCard(derniereCarte, derniereCarte.sourceLabel); }
  function paintCard(d: CardData, sourceLabel?: string) {
    for (const p of Array.from(document.querySelectorAll<HTMLElement>('[data-couverture-max]'))) p.hidden = modeErp() && d.pct >= 100; // R3-04
    // ACAL852 — sans facture (cible absente ou nulle ET aucune économie) : « facture inconnue », jamais « 0 MAD – 0 MAD/an ».
    const factureInconnue = !((d.target ?? ctx.prodTarget) > 0) && !(d.savingsHigh > 0);
    derniereCarte = { ...d, factureInconnue, sourceLabel };
    const set = (id: string, v: string) => { const el = $(id); if (el) el.textContent = v; };
    set('rp9-reco-title', d.isReco ? `${d.title}  ·  ✓ recommandé` : d.title);
    // W97 §2 — kWc = panneaux × 0,72 (PANEL2_WATT) : toujours ≤ 2 décimales exactes.
    // 1 décimale arrondissait CHAQUE zone indépendamment, si bien que la somme des
    // deux cartes affichées pouvait diverger jusqu'à 0,1 kWc du total agrégé
    // (round(a) + round(b) ≠ round(a+b)) — cf. zones.ts. 2 décimales affichent la
    // valeur exacte (aucune perte), donc la somme affichée == le total affiché.
    // ACAL851 — la puissance du module RÉELLEMENT posé (« 8 × 710 W ») ; sans choix, le défaut.
    // T4-V2-021 — UNE définition (chiffresVariante.ts), relue telle quelle par la carte de la variante posée.
    const { kwc, watt, annualKwh: prodPose } = chiffresDeLaPose(d, moduleDuPanActif(), prodServieAuKwc, partRaccordee());
    set('rp9-reco-kwc', kwc == null ? '—' : `${fmtKwc(kwc)} kWc`);
    set('rp9-reco-panels', watt ? `${fmt(d.count)} × ${fmt(watt)} W` : `${fmt(d.count)} panneaux`);
    // R2-17 — à kWc égal, la production SERVIE (celle du PDF) remplace l'estimation du navigateur (`prodServieAuKwc`).
    const pServie = modeErp() ? prodServieAuKwc(kwc) : null, cServie = modeErp() ? couvertureServie(etatEco(ctx).chiffrage, kwc) : null;
    set('rp9-reco-prod', modeErp() ? (pServie != null ? `${fmt(Math.round(pServie))} kWh/an` : raisonSansValeur(etatEco(ctx).chiffrage, kwc, 'production')) : prodPose != null ? `${fmt(Math.round(prodPose))} kWh/an` : '—');
    renommerDt($('rp9-reco-cover'), modeErp() ? 'De la consommation' : null, true); // R2-05 — l'ERP : jamais « couverture » (mot du PDF) ; T4-X7-002 — la part servie (`couverture_pct`) est l'énergie autoconsommée ÷ consommation : le nom des Résultats
    set('rp9-reco-cover', modeErp() ? (cServie != null ? `${Math.round(cServie)} %` : '—') : d.pct > 0 ? `${Math.round(d.pct)} %` : '—');
    // R2-08 — l'ERP donne UNE estimation (la borne prudente) : la fourchette 75-100 % n'encadrait rien du calcul du serveur.
    set('rp9-reco-savings', economieAffichee(ctx, 'carte', factureInconnue ? '— facture inconnue' : modeErp() ? `≈ ${fmtMad(d.savingsLow)}/an` : `${fmtMad(d.savingsLow)} – ${fmtMad(d.savingsHigh)}/an`, kwc)); if (modeErp()) peindrePhraseTailles($('rp9-reco-savings')?.closest('dl'), 'rp9-reco-tailles', phraseTaillesDuChiffrage(etatEco(ctx).chiffrage, kwc)); // T4-X9-007 — la phrase UNE fois, sous les cartes
    etiquetteEconomie(); if (ctx.matrixResult && ctx.roofType === 'flat') renderVariantCards(); // T4-V2-021 — la variante posée suit la carte
    // ACAL778 — la note « chiffre du devis » seulement si un devis est lié (option `devisLie`, jamais `cibleVendue`).
    const noteEco = $('rp9-reco-savings-note');
    if (noteEco) noteEco.hidden = !ctx.opts?.devisLie;
    const why = $('rp9-reco-why');
    // R2-17 — une pose très au-dessus de la consommation est DITE (les deux nombres), sans rien bloquer.
    if (why) why.textContent = d.why + (sourceLabel ? ` ${sourceLabel}` : '') + (modeErp() ? phraseSurplus(d.annualKwh, d.target) : '');
    // ACAL894 — la provenance de la carte, lue par le bandeau « Estimation rapide » de l'ERP.
    if (why) why.dataset.sourceProd = sourceLabel ?? '';
    const bif = $('rp9-reco-bifacial');
    if (bif) bif.textContent = libelleGainBifacial(d); // W94 + ACAL975 (vide en pose affleurante)
    // W94 — fourchette honnête Année 1 ↔ Année 25 : la production baisse sous la
    // dégradation linéaire des panneaux ((1 − deg)^24 en année 25) et les économies
    // restent plafonnées à la facture À CHAQUE horizon (annualSavingsMad bill-capé).
    // R2-16 — la bande « Année 1 → Année 25 » (ERP : UNE économie ; site public : la fourchette d'avant), au kWc DE LA CARTE.
    peindreBande($('rp9-reco-band'), d, d.target ?? ctx.prodTarget, modeErp(), etatEco(ctx).chiffrage, factureInconnue, kwc);
    // WJ22 — couche de pertes climatiques HONNÊTES (opt-in) : rend la production/les
    // économies en FOURCHETTE (été côtier chaud/poussiéreux = borne basse ↔ chiffre nu =
    // borne haute), au lieu d'un chiffre unique sur-estimé de ~15–20 % l'été. Les
    // économies de la borne basse passent par annualSavingsMad → plafonnées à la facture
    // (jamais au-dessus du coût évitable). Défaut OFF → élément vide, chiffre inchangé.
    const climate = $('rp9-reco-climate');
    if (climate) {
      if (ctx.climateBandOn && d.annualKwh > 0) {
        const derate = climateDerateFactor();
        const pband = productionConfidenceBand(d.annualKwh, derate);
        const target = d.target ?? ctx.prodTarget;
        // Économies de la borne BASSE (production dératée) — plafonnées à la facture.
        const savLowBand = target > 0 ? annualSavingsMad(pband.low, target) : { low: d.savingsLow * derate, high: d.savingsHigh * derate };
        const lossPct = Math.round((1 - derate) * 100);
        climate.textContent =
          `Fourchette honnête (pertes réelles chaleur + poussière + brume, jusqu'à −${lossPct} % l'été côtier) : ` +
          `production ~${fmt(Math.round(pband.low))} – ${fmt(Math.round(pband.high))} kWh/an ` +
          `(milieu ~${fmt(Math.round(pband.point))}) · économies ~${fmtMad(savLowBand.high)} – ${fmtMad(d.savingsHigh)}/an. ` +
          `Économies toujours plafonnées à votre facture.`;
      } else {
        climate.textContent = '';
      }
    }
    $('rp9-results')?.classList.add('rp9-results--ready');
    const cta = $<HTMLButtonElement>('rp9-cta');
    if (cta && d.count > 0) {
      cta.hidden = false;
      cta.onclick = () => prefillLead(d);
    }
  }

  // ── PV64 — rendu + sélection des trois cartes de variante ────────────────────
  /** Conteneur des cartes, créé sous le bloc résultat si la page ne le fournit pas. */
  function variantsHost(): HTMLElement | null {
    const existing = $('rp9-variants');
    if (existing) return existing;
    const results = $('rp9-results');
    if (!results || typeof document.createElement !== 'function') return null;
    const host = document.createElement('div');
    host.id = 'rp9-variants';
    host.className = 'rp9-variants';
    results.appendChild(host);
    return host;
  }

  /** La carte `c` correspond-elle à la configuration actuellement affichée ? */
  function variantIsCurrent(c: VariantCard): boolean {
    const w = ctx.liveResult?.winner;
    if (!w) return false;
    const azAxis = w.orientation === 'aligned' ? 'aligned' : 'south';
    return (
      w.family === c.row.family &&
      Math.round(w.tiltDeg) === Math.round(c.row.tiltDeg) &&
      w.layout === c.row.orientation &&
      w.margin === c.row.margin &&
      azAxis === (c.row.azimuthAxis === 'aligned' ? 'aligned' : 'south')
    );
  }

  /**
   * PV64 — peint les trois cartes (compte / kWc / kWh) issues du balayage DÉJÀ calculé.
   * Aucun nouveau solve : c'est de l'affichage. Un clic VERROUILLE les axes de la carte
   * et relance le solveur vivant existant (même chemin qu'un clic sur une puce).
   */
  function renderVariantCards() {
    const host = variantsHost();
    if (!host) return;
    const cards = pickVariantCards(ctx.matrixResult);
    if (!cards.length || ctx.roofType !== 'flat') {
      host.innerHTML = '';
      host.hidden = true;
      return;
    }
    host.hidden = false;
    host.innerHTML = '';
    host.style.cssText = 'display:grid;gap:0.5rem'; // R3-25 — une carte par ligne, espacées
    for (const c of cards) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'rp9-variant';
      btn.style.cssText = 'display:flex;flex-direction:column;gap:0.125rem;text-align:left'; // R3-25 — titre, chiffres, raison : chacun sa ligne
      btn.dataset.variant = c.id;
      btn.setAttribute('aria-pressed', String(variantIsCurrent(c)));
      btn.title = c.reason;
      const title = document.createElement('strong');
      title.textContent = c.title;
      const figures = document.createElement('span');
      figures.className = 'rp9-variant-figures';
      figures.textContent = texteChiffresVariante(c, variantIsCurrent(c) && derniereCarte ? chiffresDeLaPose(derniereCarte, moduleDuPanActif(), prodServieAuKwc, partRaccordee()) : null, moduleDuPanActif(), fmt, fmtKwc, modeErp() && estPompage(etatEco(ctx).chiffrage) ? 'pompage' : modeErp()); // T4-V2-021, T4-X2-006 ; ACAL1268
      const why = document.createElement('span');
      why.className = 'rp9-variant-why';
      why.textContent = c.reason;
      btn.append(title, figures, why);
      btn.addEventListener('click', () => applyVariant(c));
      host.appendChild(btn);
    }
    const max = phraseCouvertureMax(ctx.matrixResult, modeErp() ? derniereCarte?.pct : 0); // ACAL547 + R3-04
    if (max) host.insertAdjacentHTML('beforeend', `<p class="rp9-variant-why" role="note" data-couverture-max>${max}</p>`);
  }

  /**
   * PV64 — applique une carte : ses axes deviennent des VERROUS (comme si l'utilisateur
   * avait cliqué chaque puce), puis le solveur vivant re-résout et re-rend. Aucune
   * nouvelle physique n'est calculée ici.
   */
  function applyVariant(c: VariantCard) {
    ctx.sel = {
      family: c.row.family,
      tilt: c.row.tiltDeg,
      orient: c.row.orientation,
      azimuth: c.row.azimuthAxis === 'aligned' ? 'aligned' : 'south',
      margin: c.row.margin,
    };
    ctx.pinned.add('family');
    ctx.pinned.add('tilt');
    ctx.pinned.add('orient');
    ctx.pinned.add('azimuth');
    ctx.pinned.add('margin');
    ctx.useRecommended = false;
    liveResolveFlat();
    renderVariantCards(); // reflète la carte désormais sélectionnée
  }

  function paintMaxLine() {
    if (!ctx.rec) return;
    const maxline = $('rp9-maxline');
    if (maxline) {
      maxline.textContent = `Rendement max par panneau : ~${ctx.rec.maxPerPanelTiltDeg}° plein sud. Énergie totale max sur CE toit : ~${ctx.rec.maxRoofEnergyTiltDeg}° (un toit limité gagne à être plus plat pour loger plus de panneaux).`;
    }
  }

  // ═══════════ V3 — toit en pente (pose affleurante) ═══════════

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
    if (!ctx.pitchedRec) return '';
    const p = ctx.pitchedRec.planes[0];
    if (p.northFacing) {
      return `Ce pan est orienté ${facingLabel(ctx.facingAzimuthDeg)} (trop au nord) : aucune pose recommandée. Choisissez un pan orienté sud, est ou ouest.`;
    }
    const cover = Math.round(ctx.pitchedRec.pctOfTarget);
    const head = `Pose affleurante sur la pente (~${Math.round(p.pitchDeg)}°, face ${facingLabel(ctx.facingAzimuthDeg)})`;
    if (ctx.pitchedRec.roofLimited) {
      return `${head} : ${ctx.pitchedRec.totalPlacedCount} panneaux, ~${cover} % de votre consommation. Ce pan ne couvre pas tout le besoin.`;
    }
    return `${head} : dimensionné à votre besoin — ${ctx.pitchedRec.totalPlacedCount} panneaux, ~${cover} %. Inclinaison et azimut imposés par le toit.`;
  }
  function pitchedNote(): string {
    if (!ctx.pitchedRec) return '';
    const p = ctx.pitchedRec.planes[0];
    const yld = ctx.pitchedPvgisPerKwc != null ? Math.round(ctx.pitchedPvgisPerKwc) : Math.round(p.perPanelYield);
    const src = ctx.pitchedPvgisPerKwc != null ? 'PVGIS, pose « building »' : 'table committée (PVGIS indisponible)';
    return `Inclinaison ${Math.round(p.pitchDeg)}° = pente · azimut ${Math.round(p.facingAzimuthDeg)}° = face (imposés, non balayés). Rendement ${src} : ~${yld} kWh/kWc/an. Panneaux qui tiennent sur ce pan : ${p.fitCount}.`;
  }

  function renderPitched() {
    if (!ctx.pitchedRec) return;
    const plane = ctx.pitchedRec.planes[0];
    const fp = plane.pack;
    const fg = plane.orientation === 'portrait' ? fp.portrait : fp.landscape;
    renderScene(flushToPack(fp), flushGridToPanelGrid(fg), fp.pitchDeg, 'south', plane.placedCount, true);
    // V5 : production de vérité = PVGIS au (pente, face) réels, pose 'building'.
    // Disponible → on remplace la valeur table par le chiffre PVGIS et on recalcule
    // couverture + économies de façon cohérente ; sinon repli table (« estimé »).
    const targetSolveur = ctx.pitchedRec.targetAnnualKwh;
    const target = cibleDeCarte(targetSolveur); // V1-02 — la facture du lead, repli d'AFFICHAGE (toit en pente aussi)
    const usePvgis = ctx.pitchedPvgisPerKwc != null && ctx.pitchedRec.totalKwc > 0 && !plane.northFacing;
    const f = facteurDerateAnnuel(ctx); // ACAL356 — 1 ⇒ chiffres inchangés
    const annualKwh = (usePvgis ? ctx.pitchedRec.totalKwc * (ctx.pitchedPvgisPerKwc as number) : ctx.pitchedRec.totalAnnualKwh) * f;
    const pct = target > 0 ? (annualKwh / target) * 100 : 0;
    const savings = usePvgis || f < 1 || (targetSolveur <= 0 && target > 0) ? annualSavingsMad(annualKwh, target, tariffForCity(undefined)) : { low: ctx.pitchedRec.savingsLow, high: ctx.pitchedRec.savingsHigh };
    paintCard(
      {
        title: `Toit en pente ~${Math.round(fp.pitchDeg)}° · face ${facingLabel(ctx.facingAzimuthDeg)}`,
        isReco: true,
        count: ctx.pitchedRec.totalPlacedCount,
        kwc: ctx.pitchedRec.totalKwc,
        annualKwh,
        pct,
        savingsLow: savings.low,
        savingsHigh: savings.high,
        why: pitchedWhy(),
        family: 'south', // pose affleurante mono-orientation → pas d'écrêtage E-O
        flush: true, // ACAL975 — pose affleurante : pas de gain bifacial
        tiltDeg: fp.pitchDeg,
        target,
      },
      usePvgis ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(plane.fitCount, 'pente', noterMotifPanVide(ctx.activeAreaId, motifPenteNord(plane.northFacing, plane.placedCount, ctx.neededPanels, ctx.facingAzimuthDeg, fp.pitchDeg))); // ACAL1970
    if (pitchedNoteEl) pitchedNoteEl.textContent = pitchedNote();
    if (pitchValueEl) pitchValueEl.textContent = `${Math.round(fp.pitchDeg)}°`;
    highlightRow(null);
  }

  // ═══════════ W35 — OPTIMISEUR CONTRAINT VIVANT (toit en pente, cerveau V8) ═══════════
  // Jumeau de l'optimiseur plat (W34) : axes libres = pose + marge (+ cible besoin),
  // inclinaison = pente et azimut = face IMPOSÉS (jamais optimisés). Verrouiller un axe
  // le tient et re-résout l'autre ; production PVGIS au (pente, face), pose 'building'.

  /** Verrous pente courants (pose + marge) + cible besoin (partagée via neededAuto).
   *  L2 — pendant du `placedFor` plat : en mode devis (`ctx.devisMode`) avec un besoin
   *  nul (cible vendue de zéro, devis sans ligne panneau), on IMPOSE `needImposedZero`
   *  pour que `solveLivePitched` (estimatorBrainV8) ne retombe pas sur son repli
   *  « remplir ce qui tient » — voir sa docstring. Mode lead/estimateur inchangé. */
  function buildPitchedLocks(): { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number; needImposedZero?: boolean } {
    const locks: { layout?: PitchedLayoutAxis; margin?: PitchedMarginAxis; need?: number; needImposedZero?: boolean } = {};
    if (ctx.pitchedLocks.layout) locks.layout = ctx.pitchedLocks.layout;
    if (ctx.pitchedLocks.margin) locks.margin = ctx.pitchedLocks.margin;
    const besoin = ctx.neededAuto ? besoinAutoRelu(ctx.documentRelu, ctx.activeAreaId, monthlyBill()) : ctx.neededPanels; // ACAL367
    if (besoin > 0) locks.need = besoin;
    if (ctx.devisMode && ctx.cibleVendue && ctx.neededPanels <= 0) locks.needImposedZero = true;
    return locks;
  }

  function liveResolvePitched(annoncer = true) {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'pitched' || refusPanExistant(annoncer) || (!annoncer && poseTenue(ctx))) return; // ACAL574, ACAL1404, ACAL1900
    const ring: LngLat[] = [...ctx.vertices];
    const bill = monthlyBill();
    const locks = buildPitchedLocks();
    const yieldFn = (pitch: number, facing: number): number | null => {
      const v = ctx.pitchedYieldCache.get(pitchedKey(pitch, facing));
      return v == null ? null : v;
    };
    const res = solveLivePitched(ring, ctx.centroidLat, bill, ctx.pitchDeg, ctx.facingAzimuthDeg, obstructionRings(), locks, {
      yieldFn,
      overhangM: ctx.overhangM,
      obstructionClearancesM: obstructionClearances(), // PV61
      setbacksM: keepSetbacks(), // PV63
      retraitsParAreteM: retraitsParArete(), // CALX95 — retrait propre à chaque arête saisie
      module: cotesDuModuleDuPanActif(), // CALX109 — vraies cotes du module posé sur ce pan
    });
    ctx.pitchedLiveResult = res;
    if (ctx.neededAuto) ctx.neededPanels = res.neededPanels > 0 ? clampNeeded(res.neededPanels) : besoinAutoRelu(ctx.documentRelu, ctx.activeAreaId, monthlyBill());
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
    // ACAL356 — dérate ombrage × horizon ; économies recalculées du kWh dératé (1 ⇒ chiffres du solveur).
    const f = facteurDerateAnnuel(ctx);
    // V1-02 — cible du solveur nulle (champ facture absent en ERP) : la facture du lead sert à l'AFFICHAGE seulement.
    const cible = cibleDeCarte(res.target);
    const repli = !(res.target > 0) && cible > 0;
    const pctCarte = repli ? (w.annualKwh * f / cible) * 100 : w.pctOfTarget * f;
    const eco = f < 1 || repli ? annualSavingsMad(w.annualKwh * f, cible) : { low: w.savingsLow, high: w.savingsHigh };
    const cov = Math.round(pctCarte);
    const tiltTxt = `${Math.round(ctx.pitchDeg)}°`;
    // W74 — pan orienté nord (production quasi nulle) ET pan non viable (trop petit /
    // contraint à néant) ont chacun leur message honnête, distincts d'un faux gagnant.
    // L2 — devis sans ligne panneau (cible vendue = 0) : message dédié AVANT le générique
    // « optimale » (qui parlerait à tort de « facture », absente en devis) — jamais un
    // calepinage inventé sur un pan pourtant tout à fait viable.
    const why = res.northFacing
      ? `Ce pan est orienté nord (face ${facingLabel(ctx.facingAzimuthDeg)}) : production quasi nulle, aucune pose rentable proposée. Indiquez la vraie face descendante du pan.`
      : res.noViableConfig
        ? `Configuration non viable sur ce toit : aucun panneau ne tient sur ce pan (trop petit ou entièrement occupé par des obstacles). Agrandissez le pan ou retirez des obstacles.`
        : ctx.devisMode && ctx.cibleVendue && ctx.neededPanels <= 0
          ? `Ce devis ne porte aucun panneau — aucune pose proposée sur ce pan. Fixez un nombre (facture ou saisie) pour calepiner.`
          : isReco
            ? `Pose affleurante optimale : ${w.placedCount} panneaux (${w.layoutLabel}, ${w.marginLabel})${couverture(cible, cov)}. Inclinaison ${tiltTxt} = pente, azimut = face — imposés par la toiture, non optimisés.`
            : `Vos choix sont tenus, le reste re-résolu : ${w.placedCount} panneaux${couverture(cible, cov)}. Les badges « Recommandé » montrent la pose/marge optimale.`;
    paintCard(
      {
        title: `Toit en pente ~${tiltTxt} · face ${facingLabel(ctx.facingAzimuthDeg)} · ${w.layoutLabel}`,
        isReco,
        count: w.placedCount,
        kwc: w.kwc,
        annualKwh: w.annualKwh * f,
        pct: pctCarte,
        savingsLow: eco.low,
        savingsHigh: eco.high,
        why,
        family: 'south', // pose affleurante mono-orientation → pas d'écrêtage E-O
        flush: true, // ACAL975 — pose affleurante : pas de gain bifacial
        tiltDeg: w.pack.pitchDeg,
        target: ctx.pitchedRec ? cibleDeCarte(ctx.pitchedRec.targetAnnualKwh) : undefined,
      },
      w.yieldSource === 'pvgis' ? '(production PVGIS · pose affleurante « building »)' : '(production estimée · table committée — PVGIS indisponible)',
    );
    syncNeedControl(w.grid.count, 'pente', noterMotifPanVide(ctx.activeAreaId, motifPenteNord(res.northFacing, w.placedCount, ctx.neededPanels, ctx.facingAzimuthDeg, ctx.pitchDeg))); // ACAL1970
    if (pitchValueEl) pitchValueEl.textContent = tiltTxt;
    if (pitchedNoteEl) {
      pitchedNoteEl.textContent = `Inclinaison ${tiltTxt} = pente · azimut ${Math.round(ctx.facingAzimuthDeg)}° = face (imposés, non balayés). Pose affleurante, sans rangées espacées. Panneaux qui tiennent : ${w.fitCount}.`;
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
        celluleEconomies(wrap, r.savingsLow, r.savingsHigh);
      tr.addEventListener('click', () => {
        ctx.pitchedLocks.layout = r.layout;
        ctx.pitchedLocks.margin = r.margin;
        liveResolvePitched();
      });
      tbody.appendChild(tr);
    }
    if (wrap) wrap.hidden = false;
    highlightRow(wk);
  }

  /** « Réinitialiser » (toit en pente) : relâche les verrous pose/marge → optimum global. */
  function resetPitchedLocks() {
    delete ctx.pitchedLocks.layout;
    delete ctx.pitchedLocks.margin;
    ctx.neededAuto = true;
    liveResolvePitched();
  }

  // V5 — rendement spécifique PVGIS (kWh/kWc/an) du plan en pente, pose 'building',
  // à kWc=1 (mis à l'échelle ensuite). Cache par (pente|face), repli table (null).
  async function pitchedSpecificYield(pitch: number, facing: number): Promise<number | null> {
    const key = pitchedKey(pitch, facing);
    if (ctx.pitchedYieldCache.has(key)) return ctx.pitchedYieldCache.get(key) ?? null;
    try {
      const v = await lireRendement(urlRendement, { lat: ctx.centroid[1], lon: ctx.centroid[0], mountingplace: 'building', legs: [pitchedPlaneLeg(pitch, facing, 1)] }); // ACAL80
      ctx.pitchedYieldCache.set(key, v);
      return v;
    } catch {
      ctx.pitchedYieldCache.set(key, null);
      return null;
    }
  }

  // Affine la production du toit en pente avec PVGIS (une seule requête, cachée).
  async function refinePitchedPvgis() {
    if (!ctx.pitchedRec) return;
    const p = ctx.pitchedRec.planes[0];
    if (!p || p.northFacing) return;
    const token = ++pitchedToken;
    const perKwc = await pitchedSpecificYield(p.pitchDeg, p.facingAzimuthDeg);
    if (token !== pitchedToken || perKwc == null) return;
    ctx.pitchedPvgisPerKwc = perKwc;
    // W35 — le cache PVGIS (pente, face) est rempli : re-résout l'optimiseur vivant.
    if (ctx.roofType === 'pitched') liveResolvePitched(false); // ACAL1404 — fond, pas un geste
  }

  function pitchedRecompute() {
    if (!ctx.closed || ctx.vertices.length < 3) return;
    const ring: LngLat[] = [...ctx.vertices];
    const plane: RoofPlane = {
      ring,
      pitchDeg: ctx.pitchDeg,
      facingAzimuthDeg: ctx.facingAzimuthDeg,
      obstructions: obstructionRings(),
      obstructionClearancesM: obstructionClearances(), // PV61
      setbacksM: keepSetbacks(), // PV63
    };
    ctx.pitchedRec = recommendPitched([plane], ctx.centroidLat, monthlyBill());
    ctx.pitchedPvgisPerKwc = null; // nouvelle config → chiffre PVGIS obsolète (repli table)
    if (ctx.neededAuto) {
      const n = neededPanelsForTarget(ctx.pitchedRec.targetAnnualKwh, ctx.centroidLat);
      ctx.neededPanels = n > 0 ? clampNeeded(n) : besoinAutoRelu(ctx.documentRelu, ctx.activeAreaId, monthlyBill());
    }
    // W35 — l'optimiseur vivant en pente rend le gagnant + son comparatif (pose × marge).
    liveResolvePitched();
    setStatus('Mode pente : pose affleurante, inclinaison et azimut imposés par le toit.');
    void refinePitchedPvgis(); // production de vérité PVGIS (building) au (pente, face)
  }

  // ── V4 — PVGIS SOURCE DE VÉRITÉ ──────────────────────────────────────────────

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
    if (ctx.pvgisCache.has(key)) return ctx.pvgisCache.get(key) ?? null;
    try {
      const kwh = await lireRendement(urlRendement, { lat: ctx.centroid[1], lon: ctx.centroid[0], legs: legsFor(family, tiltDeg, azimuthDeg, kwc) }); // ACAL80
      if (kwh != null) {
        ctx.pvgisCache.set(key, kwh);
        return kwh;
      }
      ctx.pvgisCache.set(key, null); // PVGIS a répondu « estimate » → repli table mémorisé
      return null;
    } catch {
      // Pas d'erreur visible : la table committée a déjà fourni un chiffre.
      ctx.pvgisCache.set(key, null);
      return null;
    }
  }

  async function refinePvgis() {
    if (!ctx.rec) return;
    const r = ctx.rec.recommended;
    const kwh = await fetchPvgis(r.family, r.tiltDeg, r.azimuthDeg, r.kwc);
    if (kwh != null && r.kwc > 0) {
      // Stocke le rendement (kWh/kWc) — réappliqué au nombre POSÉ, qui peut être
      // sous le besoin si le toit/les obstacles contraignent.
      ctx.pvgisPerKwc = kwh / r.kwc;
      if (ctx.useRecommended) renderSelection();
    }
  }

  // ── V4 — PVGIS SOURCE DE VÉRITÉ : optimum de grille fine au GPS exact ────────
  // Rendement spécifique (kWh/kWc/an) pour un (tilt, aspect) — kWc=1, pose 'free'
  // (toit plat racké). Mémorisé/réutilisé ; PVGIS null → repli table (null en cache).
  async function v4SpecificYield(tiltDeg: number, aspect: number): Promise<number | null> {
    const key = v4Key(tiltDeg, aspect);
    if (ctx.v4YieldCache.has(key)) return ctx.v4YieldCache.get(key) ?? null;
    try {
      const kwh = await lireRendement(urlRendement, { lat: ctx.centroid[1], lon: ctx.centroid[0], mountingplace: 'free', legs: [{ kwc: 1, tiltDeg, aspect }] }); // ACAL80
      if (kwh != null) {
        ctx.v4YieldCache.set(key, kwh);
        return kwh;
      }
      ctx.v4YieldCache.set(key, null);
      return null;
    } catch {
      ctx.v4YieldCache.set(key, null);
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
      const v = ctx.v4YieldCache.get(v4Key(tiltDeg, aspect));
      return v == null ? null : v;
    };
    // ACAL1504 — le balayage pave le MÊME anneau posable que le solveur vivant (retrait propre à chaque arête).
    ctx.matrixResult = fineGridMatrixV6(anneauPosableParArete(ring, retraitsParArete()), ctx.centroidLat, bill, obstructionRings(), {
      yieldFn,
      overhangM: ctx.overhangM,
      obstructionClearancesM: obstructionClearances(), // PV61
      setbacksM: keepSetbacks(), // PV63
      optimisation: choixOptimisation, // CALX114 — l'objectif SAISI, null = celui d'hier
      neededPanelsPose: ctx.neededPanels, // ACAL1918 — même plafond que le tableau « Comparer les poses »
    });
    paintComparison();
    renderMatrixOptimumCard();
    renderVariantCards(); // PV64 — trois variantes lisibles du MÊME balayage
    // W34 — le cache PVGIS vient d'être enrichi : re-résout le solveur vivant pour que
    // le gagnant affiché + les badges « Recommandé » suivent la production PVGIS exacte.
    if (ctx.roofType === 'flat') liveResolveFlat(false); // ACAL1404 — fond, pas un geste
  };

  async function computeMatrixPvgis() {
    if (!ctx.closed || ctx.vertices.length < 3 || ctx.roofType !== 'flat') return;
    const token = ++matrixToken;
    const ring: LngLat[] = [...ctx.vertices];
    const bill = factureCarte(); // ACAL1505 — cible du balayage : saisie, sinon la facture du lead (le vivant garde monthlyBill)
    const roofAz = roofDominantAzimuthDeg(ring);
    // Phase 1 — GROSSIÈRE : tous les aspects, inclinaisons grossières → la base.
    await Promise.all(pvgisCoarsePairs(ctx.centroidLat, roofAz).map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return; // un tracé/réglage plus récent a pris la main
    buildMatrix(ring, bill);
    // Phase 2 — FINE : on raffine la grille fine complète autour de l'aspect gagnant.
    const refine = pvgisRefinePairs(ctx.centroidLat, roofAz, ctx.matrixResult ? ctx.matrixResult.winner.aspect : 0);
    if (!refine.length) return;
    await Promise.all(refine.map((p) => v4SpecificYield(p.tiltDeg, p.aspect)));
    if (token !== matrixToken) return;
    buildMatrix(ring, bill);
  }

  // tiltOf/gridFor : helpers de sélection historiques (conservés tels quels).
  function tiltOf(family: ConfigFamily): number {
    if (ctx.sel.tilt === 'reco') {
      if (ctx.useRecommended && ctx.rec) return ctx.rec.recommended.tiltDeg;
      return family === 'eastwest' ? 10 : (ctx.rec?.maxPerPanelTiltDeg ?? 29);
    }
    return ctx.sel.tilt;
  }

  function gridFor(pack: PackResult): PanelGrid {
    if (ctx.sel.orient === 'portrait') return pack.portrait;
    if (ctx.sel.orient === 'landscape') return pack.landscape;
    if (ctx.sel.orient === 'mixed') return pack.mixed ?? pack.best; // PV62
    return pack.best;
  }

  // tiltOf/gridFor/renderPitched/refinePvgis : helpers historiques conservés tels quels
  // (déjà non appelés avant le split — surface préservée à l'identique, jamais ré-écrite).

  return {
    liveResolveFlat,
    liveResolvePitched,
    renderSelection,
    renderConfig,
    pitchedRecompute,
    resetFlatLocks,
    resetPitchedLocks,
    buildMatrix,
    computeMatrixPvgis,
    clampNeeded,
    majChiffrage, peindreCartePosee, repeindreCarte, // ACAL1900, ACAL1914
    etatCarte: () => (derniereCarte && derniereCarte.count > 0 && derniereCarte.annualKwh > 0 ? { kwhParPanneau: derniereCarte.annualKwh / derniereCarte.count, tiennent: dernierFit, get maxSens() { return maxSensCarte(); } } : null), // ACAL1903 — le solveur ne tourne qu'à la lecture
  };
}

/* ════════════════════════════════════════════════════════════════════════════
   CAL83 — LA PRIORITÉ DE REMPLISSAGE D'UNE ZONE, ET RIEN QUE LE DÉPARTAGE.
   ----------------------------------------------------------------------------
   Constat : l'ordre de remplissage est IMPLICITE dans le pavage
   (`lib/roofPro2.ts`, balayage des rangées depuis `vMin`, colonnes depuis
   `uMin`). La grille est donc ancrée au coin « bas-gauche » de la boîte
   englobante du tracé dans le repère (u, v) ; tout le mou — ce qui reste entre
   la dernière rangée posée et la rive opposée — se retrouve TOUJOURS du même
   côté. L'utilisateur ne peut pas dire « commence par le sud », « colle au
   faîtage », ni « éloigne-toi de la cheminée ».

   LA RÈGLE, NON NÉGOCIABLE : une priorité DÉPARTAGE, elle n'arbitre JAMAIS le
   compte. On ne re-pave rien et on ne relâche aucune contrainte : on TRANSLATE
   le pavage déjà posé à l'intérieur de son mou, et on n'accepte une translation
   que si les N panneaux restent TOUS valides (empreinte dans le tracé, retrait
   de rive tenu). Un décalage qui ferait tomber ne serait-ce qu'un panneau est
   refusé — à compte égal la priorité choisit, elle ne fait jamais perdre un
   module. Le décalage 0 (le comportement d'aujourd'hui) est toujours candidat,
   donc le pire cas est l'identité.

   LES AXES (u, v) SONT CEUX DU PAVAGE, pas une seconde convention :
   `azimuthDeg` est l'azimut d'empilement des rangées, `f = (sin az, cos az)` le
   vecteur de visée (E, N), `v` la progression des rangées le long de `f`, `u`
   l'axe long des rangées. Sur un pan incliné, l'azimut d'empilement est celui
   de la PENTE DESCENDANTE : `v` croît donc du FAÎTAGE (v petit) vers l'ÉGOUT
   (v grand). C'est une lecture de la géométrie existante, pas une convention
   inventée pour l'occasion.

   « MEILLEUR ENSOLEILLEMENT » n'est pas une intuition : il départage sur la
   distance aux sources d'ombre DÉCLARÉES (obstacles relevés). Aucune source
   déclarée ⇒ aucun départage possible, et on le DIT (`motif`) au lieu
   d'inventer un classement.
   ══════════════════════════════════════════════════════════════════════════ */

/** CAL83 — priorité de remplissage d'une zone. `aucune` = comportement historique. */
export type PrioriteRemplissage =
  | 'aucune'
  | 'faitage'
  | 'egout'
  | 'rive-debut'
  | 'rive-fin'
  | 'ensoleillement';

/** Libellés FR des priorités (l'écran ne les réinvente pas). */
export const PRIORITES_REMPLISSAGE: ReadonlyArray<{ id: PrioriteRemplissage; label: string }> = [
  { id: 'aucune', label: 'Aucune (ordre du pavage)' },
  { id: 'faitage', label: 'Coller au faîtage' },
  { id: 'egout', label: 'Coller à l’égout' },
  { id: 'rive-debut', label: 'Coller à la rive de départ' },
  { id: 'rive-fin', label: 'Coller à la rive opposée' },
  { id: 'ensoleillement', label: 'Meilleur ensoleillement (loin des ombres)' },
];

export interface EntreeDepartage {
  /** Contour du pan en MÈTRES, repère local ENU du pavage (`PackResult.ringENU`). */
  ringENU: [number, number][];
  /** Le pavage DÉJÀ posé : son compte est acquis et ne sera jamais réduit. */
  panels: PackedPanel[];
  /** Azimut d'empilement des rangées (degrés, 0=N, 90=E, 180=S, 270=O). */
  azimuthDeg: number;
  /** Largeur d'un panneau le long de la rangée (m) — `PanelGrid.rowWidthM`. */
  rowWidthM: number;
  /** Empreinte au sol d'UN panneau (m²) — `PanelGrid.footprintPerPanelM2`. */
  footprintPerPanelM2: number;
  /** Retrait de rive à tenir (m). Absent → `PERIMETER_SETBACK_M`. */
  setbackM?: number;
  /** Centres des sources d'ombre relevées (m, même repère). Sert à `ensoleillement`. */
  sourcesOmbreENU?: [number, number][];
}

export interface ResultatDepartage {
  /** Le pavage retenu — MÊME compte, positions éventuellement décalées. */
  panels: PackedPanel[];
  count: number;
  /** Décalage appliqué le long des rangées (m). */
  decalageU_m: number;
  /** Décalage appliqué dans le sens de progression des rangées (m). */
  decalageV_m: number;
  /** Un décalage a-t-il réellement été appliqué ? */
  departage: boolean;
  /** Pourquoi rien n'a bougé, quand rien n'a bougé (jamais un silence). */
  motif: string | null;
}

/** Pas d'exploration du mou (m) : 1 cm, sous la tolérance de pose. */
const PAS_DEPARTAGE_M = 0.01;
/** Mou maximal exploré (m) — au-delà, il y aurait une rangée de plus, pas du mou. */
const MOU_MAX_M = 20;

/**
 * CAL83 — le pavage translaté de (du, dv) tient-il ENCORE, panneau par panneau ?
 * Les 4 coins de chaque empreinte doivent rester dans le tracé et à `setback` de
 * la rive : exactement le test du pavage (`roofPro2.layoutProRows2`), pas un
 * critère plus doux inventé pour faire passer un décalage.
 */
function pavageValide(e: EntreeDepartage, du: number, dv: number): boolean {
  const { u, v } = axesDepartage(e.azimuthDeg);
  const setback = Number.isFinite(e.setbackM as number) ? (e.setbackM as number) : PERIMETER_SETBACK_M;
  const demiU = e.rowWidthM / 2;
  const demiV = (e.rowWidthM > 0 ? e.footprintPerPanelM2 / e.rowWidthM : 0) / 2;
  const dx = du * u[0] + dv * v[0];
  const dy = du * u[1] + dv * v[1];
  for (const p of e.panels) {
    const cx = p.cx + dx;
    const cy = p.cy + dy;
    for (const su of [-demiU, demiU]) {
      for (const sv of [-demiV, demiV]) {
        const coin: [number, number] = [cx + su * u[0] + sv * v[0], cy + su * u[1] + sv * v[1]];
        if (!pointInPolygon(coin, e.ringENU)) return false;
        if (distanceAuBord(coin, e.ringENU) < setback - 1e-9) return false;
      }
    }
  }
  return true;
}

/** Le plus grand décalage VALIDE dans une direction donnée (m), 0 si le mou est nul. */
function mouDisponible(e: EntreeDepartage, sensU: number, sensV: number): number {
  let retenu = 0;
  for (let d = PAS_DEPARTAGE_M; d <= MOU_MAX_M + 1e-9; d += PAS_DEPARTAGE_M) {
    if (!pavageValide(e, sensU * d, sensV * d)) break;
    retenu = d;
  }
  return retenu;
}

/** Distance minimale entre un pavage décalé et les sources d'ombre déclarées (m). */
function degagementOmbre(e: EntreeDepartage, du: number, dv: number): number {
  const sources = e.sourcesOmbreENU ?? [];
  if (!sources.length || !e.panels.length) return 0;
  const { u, v } = axesDepartage(e.azimuthDeg);
  const dx = du * u[0] + dv * v[0];
  const dy = du * u[1] + dv * v[1];
  let min = Infinity;
  for (const p of e.panels) {
    for (const s of sources) {
      min = Math.min(min, Math.hypot(p.cx + dx - s[0], p.cy + dy - s[1]));
    }
  }
  return min;
}

/** Applique un décalage (u, v) à un pavage — translation pure, compte inchangé. */
function translater(e: EntreeDepartage, du: number, dv: number): PackedPanel[] {
  const { u, v } = axesDepartage(e.azimuthDeg);
  const dx = du * u[0] + dv * v[0];
  const dy = du * u[1] + dv * v[1];
  return e.panels.map((p) => ({ ...p, cx: p.cx + dx, cy: p.cy + dy }));
}

/**
 * CAL83 — DÉPARTAGE un pavage déjà posé selon la priorité de remplissage.
 *
 * Le compte est un invariant : `resultat.count === entree.panels.length`, quelle
 * que soit la priorité. Seules les POSITIONS bougent, et seulement là où le mou
 * du tracé le permet sans faire sortir un seul panneau.
 */
export function departagerRemplissage(
  entree: EntreeDepartage,
  priorite: PrioriteRemplissage,
): ResultatDepartage {
  const immobile = (motif: string | null): ResultatDepartage => ({
    panels: entree.panels.map((p) => ({ ...p })),
    count: entree.panels.length,
    decalageU_m: 0,
    decalageV_m: 0,
    departage: false,
    motif,
  });

  if (!entree.panels.length) return immobile('Aucun panneau posé : rien à départager.');
  if (!Array.isArray(entree.ringENU) || entree.ringENU.length < 3) {
    return immobile('Tracé incomplet : le départage ne peut pas vérifier les rives.');
  }
  if (priorite === 'aucune') return immobile(null);

  if (priorite === 'ensoleillement') {
    const sources = entree.sourcesOmbreENU ?? [];
    if (!sources.length) {
      return immobile(
        'Aucune source d’ombre déclarée : le meilleur ensoleillement ne peut pas être départagé.',
      );
    }
    // On explore les quatre sens du mou et on garde le dégagement le plus grand.
    let meilleur = { du: 0, dv: 0, score: degagementOmbre(entree, 0, 0) };
    const sensOmbre: Array<[number, number]> = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    for (const [su, sv] of sensOmbre) {
      const mou = mouDisponible(entree, su, sv);
      for (let d = PAS_DEPARTAGE_M; d <= mou + 1e-9; d += PAS_DEPARTAGE_M) {
        const score = degagementOmbre(entree, su * d, sv * d);
        if (score > meilleur.score + 1e-9) meilleur = { du: su * d, dv: sv * d, score };
      }
    }
    if (Math.abs(meilleur.du) < 1e-9 && Math.abs(meilleur.dv) < 1e-9) {
      return immobile('Le pavage est déjà le plus éloigné possible des ombres déclarées.');
    }
    return {
      panels: translater(entree, meilleur.du, meilleur.dv),
      count: entree.panels.length,
      decalageU_m: meilleur.du,
      decalageV_m: meilleur.dv,
      departage: true,
      motif: null,
    };
  }

  // v croît du faîtage vers l'égout ; u croît de la rive de départ vers l'opposée.
  const sensPriorite: Record<
    Exclude<PrioriteRemplissage, 'aucune' | 'ensoleillement'>,
    [number, number]
  > = {
    faitage: [0, -1],
    egout: [0, 1],
    'rive-debut': [-1, 0],
    'rive-fin': [1, 0],
  };
  const [su, sv] = sensPriorite[priorite];
  const mou = mouDisponible(entree, su, sv);
  if (mou <= 0) return immobile('Le pavage est déjà collé de ce côté : aucun mou à reprendre.');
  return {
    panels: translater(entree, su * mou, sv * mou),
    count: entree.panels.length,
    decalageU_m: su * mou,
    decalageV_m: sv * mou,
    departage: true,
    motif: null,
  };
}
