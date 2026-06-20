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
import { type SvgBox } from '../../lib/productionWindow';
import { type SpecificDateProfile, type ScaledProduction } from '../../lib/productionEngine';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';
import { type LiveSolveResult } from '../../lib/estimatorBrainV7';
import { type PitchedLiveResult } from '../../lib/estimatorBrainV8';
import { type Appliance, type HourlyCurve } from '../../lib/applianceConsumption';
import { type InitOptions, type RoofType, type AreaRecord } from './types';

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

  // — Type/pente/face du toit actif (mutable) —
  roofType: RoofType;
  pitchDeg: number;
  facingAzimuthDeg: number;

  // — Besoin « panneaux nécessaires » de la zone active (mutable) —
  neededPanels: number;
  neededAuto: boolean;

  // — Résultats vivants des optimiseurs (mutable) —
  liveResult: LiveSolveResult | null;
  pitchedLiveResult: PitchedLiveResult | null;

  // — « Plusieurs zones » —
  /** Liste des enregistrements de zone (mutée en place dans roof-tool-pro11.ts). */
  readonly areas: AreaRecord[];
  /** Identifiant de la zone active. */
  activeAreaId: string;
  /** Enregistrement de la zone active (ou undefined). */
  activeArea: () => AreaRecord | undefined;

  // — État de la fenêtre de production (mutable) —
  /** Index 0–11 du mois sélectionné dans la fenêtre de production. */
  prodMonth: number;
  /** Profil de la date précise (mis à l'échelle) ou null = jour TYPE du mois. */
  prodSpecificDate: SpecificDateProfile | null;
  /** Production mise à l'échelle (panneaux courants) ou null. */
  prodScaled: ScaledProduction | null;
  /** Nombre de panneaux du plan de production courant. */
  prodPanels: number;
  /** Latitude du centroïde du tracé (pour le dimensionnement). */
  centroidLat: number;

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
