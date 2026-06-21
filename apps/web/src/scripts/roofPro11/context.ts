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
import * as THREE from 'three';
import type maplibregl from 'maplibre-gl';
import { type SvgBox, type ProductionScope, type ProductionSource } from '../../lib/productionWindow';
import { type SpecificDateProfile, type ScaledProduction, type PerKwcProduction } from '../../lib/productionEngine';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { type LiveSolveResult } from '../../lib/estimatorBrainV7';
import { type PitchedLiveResult, type PitchedLayoutAxis, type PitchedMarginAxis } from '../../lib/estimatorBrainV8';
import { type Recommendation, type ConfigFamily } from '../../lib/estimatorBrainV2';
import { type PitchedRecommendation } from '../../lib/estimatorBrainV3';
import { type MatrixSortKey, type MatrixV6Result } from '../../lib/estimatorBrainV6';
import { type Appliance, type HourlyCurve } from '../../lib/applianceConsumption';
import { type LayoutState } from '../../lib/layoutVariability';
import {
  type InitOptions,
  type RoofType,
  type AreaRecord,
  type LayoutPlan,
  type TiltMode,
  type OrientMode,
  type AzimuthMode,
  type MarginMode,
} from './types';

/** Axes que l'utilisateur a explicitement épinglés (toit plat) — ref STABLE. */
export type PinnedAxis = 'family' | 'tilt' | 'orient' | 'azimuth' | 'margin';
/** Sélection d'affichage des puces (miroir du gagnant courant / des verrous). */
export interface SelState {
  family: ConfigFamily;
  tilt: TiltMode;
  orient: OrientMode;
  azimuth: AzimuthMode;
  margin: MarginMode;
}
/** Verrous pose/marge du toit en pente (W35) — ref STABLE (objet muté en place). */
export interface PitchedLocks {
  layout?: PitchedLayoutAxis;
  margin?: PitchedMarginAxis;
}

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

  // — Obstacles : sélection + glissé-dessin + glissé-déplacement (mutable) —
  /** Identifiant de l'obstacle sélectionné, ou null. */
  selectedObsId: string | null;
  /** Compteur d'identifiants d'obstacle (obs-N). */
  obsCounter: number;
  /** Le mode « ajout d'obstacle » est-il actif ? */
  obstacleMode: boolean;
  /** Glissé-dessin d'un obstacle en cours (point de départ) ou null. */
  drawStart: { lngLat: LngLat; point: maplibregl.Point } | null;
  /** Un glissé-dessin est-il en cours ? */
  drawing: boolean;
  /** Ignorer le « click » de synthèse émis après un glissé. */
  suppressClick: boolean;
  /** Dernier point pointé pendant un glissé-dessin (replis tactile). */
  lastDraw: LngLat | null;
  /** Glissé-déplacement d'un obstacle existant (delta lng/lat) ou null. */
  moveObs:
    | { id: string; startLng: number; startLat: number; centerLng: number; centerLat: number; moved: boolean }
    | null;
  /** W92 — glissé-déplacement d'un SOMMET du tracé (index + delta lng/lat) ou null. */
  moveVertex:
    | { idx: number; startLng: number; startLat: number; vLng: number; vLat: number; moved: boolean }
    | null;

  // — Scène 3D partagée avec le déplacement d'obstacle en direct —
  /** Meshes 3D des obstacles, par id (ref STABLE — Map remplie par renderScene). */
  readonly obstacleMeshes: Map<string, THREE.Mesh>;
  /** Origine ENU de la scène 3D courante (lng/lat du pack actif). */
  sceneOrigin: LngLat;
  /** W88 — InstancedMesh des panneaux de la zone ACTIVE (rempli par renderScene) pour le
   *  pick/highlight 3D, ou null. */
  activePanelMesh: THREE.InstancedMesh | null;
  /** W88 — mapping instance i → index de cellule de la lattice (ordre des panneaux posés
   *  rendus), pour relier un panneau 3D survolé/tapé à sa cellule (highlight + suppression). */
  activePanelCellIndex: number[];

  // — Type/pente/face du toit actif (mutable) —
  roofType: RoofType;
  pitchDeg: number;
  facingAzimuthDeg: number;
  /** W106 — la face du pan actif a-t-elle été fixée À LA MAIN (override par zone) ? */
  facingManual: boolean;

  // — Besoin « panneaux nécessaires » de la zone active (mutable) —
  neededPanels: number;
  neededAuto: boolean;

  // — Recommandation/optimum courant + flag « caler sur la reco » (mutable) —
  rec: Recommendation | null;
  useRecommended: boolean;
  /** Recommandation pente courante (V3) — partagée avec l'optimiseur pente. */
  pitchedRec: PitchedRecommendation | null;

  // — Sélection/verrous de l'optimiseur (partagés avec les handlers DOM de l'entrée) —
  /** Miroir d'affichage des puces (gagnant courant / valeurs verrouillées). */
  sel: SelState;
  /** Axes épinglés (toit plat) — Set à ref STABLE, muté en place. */
  readonly pinned: Set<PinnedAxis>;
  /** Verrous pose/marge (toit en pente) — objet à ref STABLE, muté en place. */
  readonly pitchedLocks: PitchedLocks;

  // — Affinages PVGIS (rendement par kWc), partagés entrée ↔ optimiseur (mutable) —
  /** Rendement PVGIS (kWh/kWc/an) du plan plat recommandé, ou null = repli table. */
  pvgisPerKwc: number | null;
  /** Rendement PVGIS (kWh/kWc/an) du plan en pente (pose « building »), ou null. */
  pitchedPvgisPerKwc: number | null;

  // — Caches PVGIS (refs STABLES, vidés par l'entrée, lus/écrits par l'optimiseur) —
  /** Cache production (kWh) par config plate — clé lat,lon|famille|tilt|azimut. */
  readonly pvgisCache: Map<string, number | null>;
  /** Cache rendement spécifique (kWh/kWc/an) par (tilt|aspect), pose 'free'. */
  readonly v4YieldCache: Map<string, number | null>;
  /** Cache rendement spécifique (kWh/kWc/an) par (pente|face), pose 'building'. */
  readonly pitchedYieldCache: Map<string, number | null>;

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
  /** W87 — heure solaire (0–24) pilotant le VRAI soleil de la scène 3D (midi = 12). */
  sunHour: number;
  /** W87 — jour de l'année (1–365) pour la saison du soleil (solstice d'hiver = 355). */
  sunDay: number;

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
  /** W95 — le profil saisonnier (été ≠ hiver) est-il activé ? */
  consSeasonal: boolean;
  /** W95 — facteur multiplicatif de la conso l'été (mois juin→sept.). */
  consSummerFactor: number;
  /** W95 — facteur multiplicatif de la conso l'hiver. */
  consWinterFactor: number;
}
