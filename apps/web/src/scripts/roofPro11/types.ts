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
  // W112 — mode CAPTURE CLIENT (page /devis/mon-toit) : ne construit QUE la carte +
  // le géocodeur + le pin/tracé. AUCUN optimiseur, AUCUNE scène 3D, AUCUNE carte de
  // production — les panneaux n'apparaissent JAMAIS. Le flux complet (non-capture)
  // reste octet pour octet identique quand le drapeau est absent/false.
  captureOnly?: boolean;
  // W112 — callback déclenché à chaque changement du pin/tracé en mode capture
  // (pin {lat,lng} | null + tracé optionnel [[lat,lng],…]). Permet à la page de
  // refléter l'état (activer le bouton « envoyer », pré-remplir l'adresse, etc.).
  // W2 — `address` (libellé géocodé INVERSE depuis le repère) est joint quand il est
  // disponible : un changement géométrique du pin déclenche d'abord un onCaptureChange
  // SANS adresse (immédiat), puis un second AVEC `address` une fois le reverse-geocode
  // résolu. La page lit `pin.lat`/`pin.lng` comme GPS et `address` comme adresse.
  onCaptureChange?: (state: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]>; address?: string | null }) => void;
  // W113 — HYDRATATION optionnelle depuis un lead (le fetch est fait par la page,
  // pas par l'outil). Sème le pin/tracé de la carte + les champs contact à partir
  // d'un payload lead. Le boot complet reste inchangé quand `hydrate` est absent.
  hydrate?: { lead?: LeadPayload };
  // W114/W115 — l'outil expose une petite API à la page (sérialiser le layout
  // finalisé, capturer le PNG 3D) une fois le boot complet terminé. Invoqué
  // seulement en boot complet (jamais en capture). Absent → comportement inchangé.
  onApiReady?: (api: RoofToolApi) => void;
}

/** W114/W115 — API minimale exposée par l'outil à la page de design. */
export interface RoofToolApi {
  /** Layout finalisé sérialisé en JSON pur (zones + repère). `billKwh` optionnel. */
  serializeLayout: (billKwh?: number | null) => unknown;
  /** Instantané PNG (data URL) de la 3D rendue, ou null. */
  snapshot: () => string | null;
}

/** W113 — payload lead minimal consommé par l'hydratation (forme du GET
 *  /api/django/crm/leads/<id>/). Tous les champs optionnels : un champ absent
 *  ne sème rien. `roof_point` = pin {lat,lng}, `roof_outline` = [[lat,lng],…]. */
export interface LeadPayload {
  roof_point?: { lat: number; lng: number } | null;
  roof_outline?: Array<[number, number]> | null;
  bill_kwh?: number | null;
  fullName?: string;
  phone?: string;
  city?: string;
  [k: string]: unknown;
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
  /** W94 — famille du plan (sélection de la constante bifaciale flat/tilted +
   * libellé de la fourchette). Optionnel (rétro-compatible). */
  family?: ConfigFamily;
  /** W94 — inclinaison du plan (°) : < 12° ou E-O → gain bifacial FLAT, sinon TILTED. */
  tiltDeg?: number;
  /** W94 — besoin annuel (kWh) pour plafonner les économies de la fourchette
   * Année 1 ↔ Année 25 à la facture, à CHAQUE horizon. Optionnel (rétro-compatible). */
  target?: number;
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
  /** W107 — lift VERTICAL (m) appliqué au pan incliné pour que les pans connectés se
   *  rejoignent sur une faîtière COMMUNE (le plan monte de `ridgeLiftM` sans changer sa
   *  pente). Défaut 0 (pan isolé / toit plat) → rendu inchangé, octet pour octet. */
  ridgeLiftM?: number;
}

/** W69 — pavage gagnant courant (pack + grid + tilt + family + flush) pour
 * re-rendre la 3D avec l'occupation personnalisée (« Personnaliser la disposition »). */
export interface LayoutPlan {
  pack: PackResult;
  grid: PanelGrid;
  tiltDeg: number;
  family: ConfigFamily;
  flush: boolean;
}

export interface AreaRecord {
  id: string;
  label: string;
  vertices: LngLat[];
  obstacles: Obstacle[];
  roofType: RoofType;
  pitchDeg: number;
  facingAzimuthDeg: number;
  /** W106 — la face de ce pan a-t-elle été fixée À LA MAIN (override par zone) ? Si oui,
   *  l'auto-inférence d'adjacence ne l'écrase jamais. Optionnel (rétro-compatible, défaut false). */
  facingManual?: boolean;
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
