/**
 * Types partagés par les modules roofPro11.
 * Extraits de roof-tool-pro11.ts (split modulaire 2026-06-20) — INCHANGÉS.
 */
import { type RoofTypeSelect } from '../../lib/roofTypeSelect';
import { type PackResult, type PanelGrid, type ConfigFamily } from '../../lib/estimatorBrainV2';
import { type Obstacle } from '../../lib/obstacles';
import { type AreaResult } from '../../lib/roofAreas';
import { type LngLat } from '../../lib/roof';
import { type ProductionSource, type SpecificDateProfile } from '../../lib/productionEngine';

export interface InitOptions {
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

export type TiltMode = 'reco' | number;
export type OrientMode = 'auto' | 'portrait' | 'landscape';
// W1 : groupe AZIMUT (plein sud ou aligné sur les arêtes du toit) et groupe MARGE
// de rive (garder la marge de design ou la retirer pour récupérer la rive).
export type AzimuthMode = 'south' | 'aligned';
export type MarginMode = 'keep' | 'remove';

export type RoofType = 'flat' | 'pitched';

/** Données d'une carte « résultat » (recommandation / optimum), partagées entre
 * le rendu de carte et le pré-remplissage du diagnostic. */
export interface CardData {
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

// ═══════════ « PLUSIEURS ZONES » — enregistrements de zone ═══════════
// Plan de RE-RENDU d'une zone : tout ce qu'il faut pour redessiner son bâtiment +
// ses panneaux SANS ré-optimiser. `count` = nombre de panneaux RÉELLEMENT posés.
export interface ZoneRenderPlan {
  pack: PackResult;
  grid: PanelGrid;
  tiltDeg: number;
  family: ConfigFamily;
  flush: boolean;
  count: number;
  obstacles: Obstacle[];
}

export interface AreaRecord {
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

// ═══════════ W50 — fenêtre « Production estimée » ═══════════
/** Clé d'identité du PLAN de production (GPS/inclinaison/azimut/pose). */
export interface ProdPlaneKey {
  lat: number;
  lon: number;
  tiltDeg: number;
  aspect: number;
  mountingplace: 'building' | 'free';
}

/** Configuration de production du plan courant (déduite du winner de l'optimiseur). */
export interface ProdConfig {
  lat: number;
  lon: number;
  tiltDeg: number;
  aspect: number;
  mountingplace: 'building' | 'free';
  panels: number;
  target: number;
}

/** Réponse JSON de /api/roof-production (forme consommée par la fenêtre). */
export interface ProductionApiResponse {
  ok: boolean;
  source: ProductionSource;
  placedKwc?: number;
  annualKwh: number;
  monthlyKwh: number[];
  dailyKwhByMonth: number[];
  typicalDayByMonth: number[][];
  specificDate: SpecificDateProfile | null;
}

/** Options du rendu UNIFIÉ d'une configuration toit plat (carte + 3D + contrôles). */
export interface RenderConfigOpts {
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
