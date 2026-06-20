/**
 * Types partagés par les modules roofPro11.
 * Extraits de roof-tool-pro11.ts (split modulaire 2026-06-20) — INCHANGÉS.
 */
import { type RoofTypeSelect } from '../../lib/roofTypeSelect';

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
