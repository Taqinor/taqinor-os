// RWEB17-M0 — CONTRAT D'ÉTAT UNIQUE du tunnel « mon-toit » (fusion FR/EN/AR).
//
// POURQUOI. Les trois pages `devis/mon-toit.astro`, `en/…` et `ar/…` portent
// chacune leurs `let` de haut niveau (état de page). Pour que les sections
// extraites (RWEB17-M1…M8) partagent UN état, ce module en fixe le contrat :
// `EtatPage` (type) et `creerEtat(savedWizard, locale)` (valeurs initiales,
// reprises À L'IDENTIQUE des initialisations de la page FR). Livré SEUL : aucune
// page ne l'importe encore (M10 les câble).
//
// DIVERGENCES FR/EN/AR VÉRIFIÉES (47 `let` de haut niveau sur FR et AR, 46 sur
// EN) : la seule est `currentLang` ('fr' | 'ar'), absente de la page EN. Choix :
// `EtatPage` garde les 47 champs ; `currentLang` démarre à 'fr' sur TOUTES les
// locales et la locale EN ne le lit jamais (la langue affichée vient de
// `langueActive()` de la section « parcours », M2 : `currentLang` en FR et AR,
// 'en' en EN). Tous les autres `let` ont le même type et le même défaut sur les
// trois pages.
//
// TABLE DES SECTIONS ET PROPRIÉTAIRES DES `let` — la « table §2 » du plan n'est
// pas dans le dépôt : elle est DÉRIVÉE du texte de M1-M8. Une section écrit SEULS
// ses `let` ; elle lit les autres via `ctx.etat`.
//   M1 persistance             : restoring, hasEnteredData, dedupIdempotencyKey,
//                                dedupEventId, clientRef
//   M2 parcours                : mode, cityTouched, currentLang, step, revealed,
//                                firstRender
//   M3 sélections (15 `let`)   : visitWindowPart, visitWindowWeek,
//                                occupationJour, proUnit, tension, activity,
//                                tensionTouched, activityTouched, surfaceType,
//                                waterSource, waterUnit, commercialCategory,
//                                ccUnit, equipes, regionAgricole
//   M4 carte et toiture        : capturePin, captureOutline, capturePans,
//                                captureLayout, started, mapFetchDone,
//                                roofInputMode, confirmedPinKey,
//                                roofImageSpecPromise, panels3dStarted
//   M5 estimation pro/agricole : lastProTarifMadKwh
//   M6 estimation résidentielle: lastKwcLabel, lastSavingsLabel, lastKwc,
//                                docRendered, estimateShown, docEngaged
//   M7 validation              : (aucun `let`)
//   M8 envoi et sortie         : submitted, exitShown, exitTriggerEl,
//                                funnelAbandonSent
// (`mode` va à M2 : le plan attribue à M3 « les 15 `let` de sélection », et
// M2 porte les modes.)
//
// ORDRE D'INSTALLATION (celui des instructions de haut niveau de la page FR) :
//   1. persistance (M1)         — jeton de funnel, instantané, `beforeunload`
//   2. parcours (M2)            — modes, étapes, langue
//   3. sélections (M3)          — groupes de cartes, occupation, équipements
//   4. carte et toiture (M4)    — capture, repli, aperçu 3D
//   5. estimation pro/agricole (M5)
//   6. estimation résidentielle et document (M6)
//   7. validation (M7)
//   8. envoi et sortie (M8)     — init finale
// (M1 d'abord : toutes les autres sections appellent `saveWizardState` et
// `markDataEntered`.)

import { buildIdempotencyKey } from '../lead';
import type { RoofLayoutPublic } from '../roofLayoutPublic';

export type LocaleTunnel = 'fr' | 'en' | 'ar';

/** Forme structurelle de `RoofImageSpec` (scripts/roofPro11/viewerOnly) : ce
 *  type n'entre pas dans la garde `tsc` de src/lib, donc il est recopié, avec
 *  `provider` en chaîne. */
export interface RoofImageSpecEtat {
  image: HTMLImageElement;
  extent: [number, number, number, number];
  origin: [number, number];
  provider: string;
  attribution: string;
}

/** Instantané `mt-wizard-v1` (sessionStorage) — déplacé depuis les pages. */
export interface WizardSnapshot {
  mode?: string;
  step?: number;
  // COUPE FONDATEUR 21/08 — `revealed` : sur l'écran 1, l'estimation + le
  // formulaire de contact sont révélés SUR PLACE (plus d'étape 3). Un
  // instantané de l'ANCIEN assistant 3 étapes (step === 2, sans `revealed`) est
  // migré à la relecture (voir `revealed` dans `creerEtat`).
  revealed?: boolean;
  // Jetons de dédoublonnage persistés avec le brouillon.
  idempotencyKey?: string;
  eventId?: string;
  visitWindowPart?: string;
  visitWindowWeek?: string;
  // États des groupes de cartes/segments PRO + AGRICOLE.
  sel?: Record<string, string>;
  fields?: Record<string, string>;
  checks?: Record<string, boolean>;
  capturePin?: { lat: number; lng: number } | null;
  captureOutline?: Array<[number, number]>;
  capturePans?: Array<Array<[number, number]>>;
  captureLayout?: RoofLayoutPublic | null;
}

export interface EtatPage {
  capturePin: { lat: number; lng: number } | null;
  captureOutline: Array<[number, number]>;
  capturePans: Array<Array<[number, number]>>;
  captureLayout: RoofLayoutPublic | null;
  cityTouched: boolean;
  currentLang: 'fr' | 'ar';
  restoring: boolean;
  hasEnteredData: boolean;
  dedupIdempotencyKey: string;
  dedupEventId: string;
  mode: string;
  visitWindowPart: string;
  visitWindowWeek: string;
  occupationJour: string;
  started: boolean;
  mapFetchDone: boolean;
  step: number;
  revealed: boolean;
  firstRender: boolean;
  proUnit: string;
  tension: string;
  activity: string;
  tensionTouched: boolean;
  activityTouched: boolean;
  surfaceType: string;
  waterSource: string;
  waterUnit: string;
  commercialCategory: string;
  ccUnit: string;
  equipes: string;
  regionAgricole: string;
  roofInputMode: 'point' | 'draw';
  confirmedPinKey: string;
  lastKwcLabel: string;
  lastSavingsLabel: string;
  lastKwc: number | null;
  docRendered: boolean;
  estimateShown: Record<string, number | string> | null;
  lastProTarifMadKwh: number | null;
  roofImageSpecPromise: Promise<RoofImageSpecEtat | null> | null;
  docEngaged: boolean;
  panels3dStarted: boolean;
  clientRef: string;
  submitted: boolean;
  exitShown: boolean;
  exitTriggerEl: HTMLElement | null;
  funnelAbandonSent: boolean;
}

/** Jeton de dédoublonnage technique (copie de la page FR). */
export function newDedupToken(): string {
  try {
    const c = globalThis.crypto;
    // `randomUUID` n'existe qu'en contexte sécurisé : repli sur le générateur
    // maison déjà validé par le même regex (^[A-Za-z0-9_-]{8,64}$).
    if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  } catch {
    /* accès crypto refusé : on prend le repli */
  }
  return buildIdempotencyKey();
}

/** État initial de la page : les initialisations des `let` de la page FR, à
 *  l'identique, à partir de l'instantané relu (ou `null`). `locale` n'influe sur
 *  aucune valeur (voir l'en-tête : `currentLang` vaut 'fr' partout). */
export function creerEtat(savedWizard: WizardSnapshot | null, _locale: LocaleTunnel): EtatPage {
  const savedSel = savedWizard?.sel ?? {};
  const savedStepRaw = savedWizard?.step;
  return {
    capturePin: null,
    captureOutline: [],
    capturePans: [],
    captureLayout: null,
    cityTouched: false,
    currentLang: 'fr',
    restoring: false,
    hasEnteredData: false,
    dedupIdempotencyKey: savedWizard?.idempotencyKey || newDedupToken(),
    dedupEventId: savedWizard?.eventId || newDedupToken(),
    mode: savedWizard?.mode || '',
    visitWindowPart: savedWizard?.visitWindowPart || '',
    visitWindowWeek: savedWizard?.visitWindowWeek || '',
    occupationJour: savedWizard?.sel?.occupationJour || '',
    started: false,
    mapFetchDone: false,
    step: savedStepRaw != null ? Math.max(0, Math.min(1, savedStepRaw)) : 0,
    revealed: savedWizard?.revealed === true || savedStepRaw === 2,
    firstRender: true,
    proUnit: savedSel.proUnit || 'mad',
    tension: savedSel.tension || 'bt',
    activity: savedSel.activity || 'day',
    tensionTouched: savedSel.tensionTouched === '1',
    activityTouched: savedSel.activityTouched === '1',
    surfaceType: savedSel.surfaceType || '',
    waterSource: savedSel.waterSource || '',
    waterUnit: savedSel.waterUnit || 'm3h',
    commercialCategory: savedSel.commercialCategory || '',
    ccUnit: savedSel.ccUnit || 'mad',
    equipes: savedSel.equipes || '',
    regionAgricole: savedSel.regionAgricole || '',
    roofInputMode: savedSel.roofInputMode === 'draw' ? 'draw' : 'point',
    confirmedPinKey: '',
    lastKwcLabel: '',
    lastSavingsLabel: '',
    lastKwc: null,
    docRendered: false,
    estimateShown: null,
    lastProTarifMadKwh: null,
    roofImageSpecPromise: null,
    docEngaged: false,
    panels3dStarted: false,
    clientRef: '',
    submitted: false,
    exitShown: false,
    exitTriggerEl: null,
    funnelAbandonSent: false,
  };
}
