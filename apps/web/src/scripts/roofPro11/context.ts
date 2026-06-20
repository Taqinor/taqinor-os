/**
 * Contexte partagé qui ponte la fermeture (« god closure ») de
 * `initRoofToolPro8` vers les modules roofPro11 extraits (split modulaire
 * 2026-06-20). Chaque champ d'état MUTABLE est exposé par accesseur
 * (get/set) afin que le code resté dans `roof-tool-pro11.ts` continue d'utiliser
 * ses `let` bruts tandis que les modules extraits lisent/écrivent via `ctx.*` —
 * comportement INCHANGÉ.
 *
 * L'interface grandit module par module ; on n'ajoute ici QUE ce qu'un module
 * extrait référence réellement.
 */
import { type SvgBox, type ProductionScope, type ProductionSource } from '../../lib/productionWindow';
import { type SpecificDateProfile, type ScaledProduction, type PerKwcProduction } from '../../lib/productionEngine';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { type LiveSolveResult } from '../../lib/estimatorBrainV7';
import { type PitchedLiveResult } from '../../lib/estimatorBrainV8';
import { type Recommendation } from '../../lib/estimatorBrainV2';
import { type MatrixSortKey, type MatrixV6Result } from '../../lib/estimatorBrainV6';
import { type Appliance, type HourlyCurve } from '../../lib/applianceConsumption';
import { type LayoutState } from '../../lib/layoutVariability';
import { type InitOptions, type RoofType, type AreaRecord, type LayoutPlan } from './types';

/** Références DOM partagées avec les modules extraits (sous-ensemble du DOM du
 * builder ; chaque champ peut être null — le harness jsdom ne fournit pas tout). */
export interface CtxDom {
  // — « Plusieurs zones » —
  addAreaBtn: HTMLButtonElement | null;
  areasWindowEl: HTMLElement | null;
  areasListEl: HTMLElement | null;
  areasTotalPanelsEl: HTMLElement | null;
  areasTotalKwcEl: HTMLElement | null;
  areasTotalProdEl: HTMLElement | null;
  areasTotalSavingsEl: HTMLElement | null;
}

export interface Ctx {
  // — Options d'initialisation (figées au boot) —
  readonly opts: InitOptions;

  // — Constantes de rendu graphes (figées au boot) —
  readonly svgBox: SvgBox;

  // — Références DOM (figées au boot) —
  readonly dom: CtxDom;

  // — Géométrie du tracé courant (mutable) —
  /** Sommets lng/lat du tracé du toit actif. */
  vertices: LngLat[];
  /** Le tracé de la zone active est-il fermé ? */
  closed: boolean;
  /** Obstacles (zones d'exclusion) de la zone active. */
  obstacles: Obstacle[];
  /** Centroïde lng/lat du tracé fermé. */
  centroid: LngLat;

  // — Type/pente/face du toit actif (mutable) —
  roofType: RoofType;
  pitchDeg: number;
  facingAzimuthDeg: number;

  // — Besoin « panneaux nécessaires » de la zone active (mutable) —
  neededPanels: number;
  neededAuto: boolean;

  // — Recommandation/optimum courant + flag « caler sur la reco » (mutable) —
  rec: Recommendation | null;
  useRecommended: boolean;

  // — Résultats vivants des optimiseurs (mutable) —
  liveResult: LiveSolveResult | null;
  pitchedLiveResult: PitchedLiveResult | null;

  // — V6 MATRICE (toit plat) : balayage complet + tri/filtre (mutable) —
  matrixResult: MatrixV6Result | null;
  matrixSort: { key: MatrixSortKey; dir: 'asc' | 'desc' };
  matrixFilter: string;

  // — « Plusieurs zones » —
  /** Liste des enregistrements de zone (mutée en place dans roof-tool-pro11.ts). */
  readonly areas: AreaRecord[];
  /** Identifiant de la zone active. */
  activeAreaId: string;
  /** Enregistrement de la zone active (ou undefined). */
  activeArea: () => AreaRecord | undefined;

  // — État de la fenêtre de production (mutable) —
  /** Portée de la fenêtre (année / mois / jour). */
  prodScope: ProductionScope;
  /** Index 0–11 du mois sélectionné dans la fenêtre de production. */
  prodMonth: number;
  /** Jour sélectionné (1-based) ou null = jour TYPE du mois. */
  prodDay: number | null;
  /** Jeton anti-course pour les requêtes /api/roof-production. */
  prodToken: number;
  /** Production PAR 1 kWc (pour rescale client) ou null. */
  prodPerKwc: PerKwcProduction | null;
  /** Profil de la date précise (mis à l'échelle) ou null = jour TYPE du mois. */
  prodSpecificDate: SpecificDateProfile | null;
  /** Source de la production courante (pvgis / estimate…). */
  prodSource: ProductionSource;
  /** Production mise à l'échelle (panneaux courants) ou null. */
  prodScaled: ScaledProduction | null;
  /** Nombre de panneaux du plan de production courant. */
  prodPanels: number;
  /** Besoin annuel (kWh) pour les économies plafonnées. */
  prodTarget: number;
  /** Clé d'identité du plan de production courant. */
  prodPlaneKey: string;
  /** Latitude du centroïde du tracé (pour le dimensionnement). */
  centroidLat: number;

  // — W69 « Personnaliser la disposition » (lecture pour la fenêtre de production) —
  /** Le mode disposition personnalisée est-il actif ? */
  layoutMode: boolean;
  /** Lattice de disposition (occupation éditée) ou null. */
  layoutState: LayoutState | null;
  /** Pavage gagnant courant (re-rendu de la 3D avec occupation personnalisée). */
  layoutPlan: LayoutPlan | null;
  /** Comptage de l'optimiseur (sert à la réinitialisation de la disposition). */
  layoutOptimalCount: number;
  /** Index du panneau sélectionné (repli tactile) ou null. */
  layoutSel: number | null;

  // — W68 « Affiner ma consommation » (mutable) —
  /** Le panneau « Affiner » est-il ouvert ? */
  consMode: boolean;
  /** Courbe horaire (24 h) de consommation effectivement utilisée. */
  consCurve: HourlyCurve;
  /** L'utilisateur a-t-il édité la courbe à la main (override) ? */
  consHandEdited: boolean;
  /** Appareils ajoutés au calculateur de consommation. */
  consAppliances: Appliance[];
  /** Socle journalier (kWh) dérivé de la facture. */
  consDailyTarget: number;
  /** Compteur d'appareils « autre » ajoutés. */
  consApplCounter: number;
}
