/**
 * Constantes physiques / tarifaires PARTAGÉES de l'estimateur (étape 2 de l'unification
 * des « cerveaux »). Module PUR, SANS aucun import (comme `systemLoss.ts`) : déplacement
 * à l'identique depuis `estimatorBrainV2.ts` (grille ONEE/régie, constantes LFP) et
 * `batterySim.ts` (DoD). Ces deux fichiers importent et RÉ-EXPORTENT les mêmes noms.
 */

// ===== Modèle de facturation — barème RÉGIE ONEE « usage domestique » (juin 2026) =====
// Coût de l'ÉNERGIE uniquement (les tranches au kWh). Prix CONSOMMATEUR TTC : la
// TVA 20 % est DÉJÀ incluse dans ces taux — ne JAMAIS rajouter de TVA par-dessus.
// Les frais fixes (TPPAN, redevances, taxes d'abonnement) ne sont PAS modélisés :
// invariants au solaire, ils s'annulent dans le calcul d'économies.
//
// DEUX RÉGIMES au Maroc : le barème RÉGIE/gouvernement (Marrakech, Agadir, El Jadida
// et toutes les zones ONEE/régie) et des grilles contractuelles plus chères dans les
// trois villes ex-délégataires (Casablanca/Lydec, Rabat/Redal, Tanger/Amendis).
// POUR L'INSTANT toutes les villes utilisent le barème RÉGIE (défaut conservateur) —
// voir TARIFF_BY_CITY et ESTIMATOR_BRAIN_NOTES.md.

export interface TariffTranche {
  upToKwh: number;
  rate: number;
}
export interface TariffGrid {
  /** Tranches PROGRESSIVES (≤ seuil) : chaque tranche facturée à son propre tarif. */
  progressive: TariffTranche[];
  /** Tranches SÉLECTIVES (> seuil) : TOUTE la conso au tarif de SA tranche. */
  selective: TariffTranche[];
  /** Conso mensuelle (kWh) au-delà de laquelle on bascule en facturation sélective. */
  selectiveThresholdKwh: number;
  /** Tolérance de tranche (kWh) : on n'entre dans la tranche suivante qu'à +tolérance. */
  boundaryToleranceKwh: number;
}

/**
 * Barème RÉGIE ONEE « usage domestique » — prix consommateur TTC, ORDRE
 * FONDATEUR (19/08/2026) : TVA 20 % depuis le 01/01/2026 (16 % en 2024, 18 %
 * en 2025) — les six prix ont été re-dérivés HT × 1,20 (HT = ancien TTC 2025
 * ÷ 1,18) ; ancre fondateur (facture réelle) = tranche > 500 kWh =
 * 1,622856 MAD/kWh TTC. Détail complet de la dérivation HT/TTC par tranche :
 * apps/ventes/quote_engine/pricing.py ONEE_TRANCHES (miroir exact). Prochaine
 * hausse de TVA : refaire HT × nouveau taux sur les six bases HT documentées
 * là-bas — jamais repartir d'un TTC déjà taxé.
 *  - ≤ 150 kWh/mois → PROGRESSIF : 0–100 = 0,916272 ; 101–150 = 1,091388.
 *  - > 150 kWh/mois → SÉLECTIF (toute la conso au tarif de sa tranche) :
 *    151–210 = 1,091388 ; 211–310 = 1,187388 ; 311–510 = 1,381704 ;
 *    > 510 = 1,622856.
 * Les bornes nominales 200/300/500 + la tolérance de 10 kWh donnent les bornes
 * EFFECTIVES 210/310/510 (un client n'entre dans la tranche supérieure qu'à +10 kWh).
 * Remplace l'ancienne grille trop haute (201–300=1,18 ; 301–500=1,45 ; >500=1,66 —
 * 1,66 était le tarif FORCE-MOTRICE, pas le domestique).
 *
 * QJW12 — DÉCISION FONDATEUR D5 (29/08/2026) : la tranche 311–510 kWh passe de
 * 1,405116 à 1,381704 MAD/kWh TTC. Le 1,405116 venait de l'hypothèse « HT
 * constant » au passage de TVA 18 → 20 % ; la facture SRM n° 643769639 du
 * 08/05/2026 (359 kWh, énergie 1,15142 HT × 1,20 = 1,381704 TTC) montre que
 * c'est le TTC qui est resté constant et le HT qui a baissé. Les cinq autres
 * prix ne bougent PAS : aucune facture 2026 ne les couvre, et on ne corrige
 * jamais un chiffre sans preuve. Valeur de référence, alignée avec tout l'ERP :
 * apps/ventes/quote_engine/bareme.py, TRANCHES_2026 (T5).
 */
export const REGIE_TARIFF: TariffGrid = {
  progressive: [
    { upToKwh: 100, rate: 0.916272 },
    { upToKwh: 150, rate: 1.091388 },
  ],
  selective: [
    { upToKwh: 200, rate: 1.091388 }, // effectif 151–210
    { upToKwh: 300, rate: 1.187388 }, // effectif 211–310
    { upToKwh: 500, rate: 1.381704 }, // effectif 311–510 (prouvé facture SRM 08/05/2026)
    { upToKwh: Infinity, rate: 1.622856 }, // > 510
  ],
  selectiveThresholdKwh: 150,
  boundaryToleranceKwh: 10,
};

/**
 * Grille tarifaire par ville. POUR L'INSTANT chaque ville est égalée au barème RÉGIE
 * (défaut conservateur) : cela SOUS-estime légèrement les économies dans les trois
 * villes ex-délégataires — la posture SÛRE, jamais l'inverse. Les grilles
 * délégataires EXACTES attendent une vraie facture récente par ville.
 */
export const TARIFF_BY_CITY: Record<string, TariffGrid> = {
  // Casablanca/Lydec — la prime réelle sur le haut de grille ≈ +10,5 % (relevés HT :
  // 1,0220 pour 151–210 · 1,1119 pour 211–310 · 1,5193 pour > 510). Égalée au barème
  // régie POUR L'INSTANT (grille exacte en attente d'une vraie facture Lydec).
  Casablanca: REGIE_TARIFF,
  // Rabat/Redal — la MOINS chère des trois (au plus proche du barème régie). Égalée
  // au barème régie pour l'instant.
  Rabat: REGIE_TARIFF,
  // Tanger/Amendis — la PLUS chère des trois. Égalée au barème régie pour l'instant
  // (grille exacte en attente d'une vraie facture Amendis).
  Tanger: REGIE_TARIFF,
};

/** Profondeur de décharge utile d'un pack LFP : 90 % (les LFP tolèrent une DoD élevée ;
 *  on garde 10 % de réserve pour la longévité). Fiche LFP résidentiel standard. */
export const LFP_DOD = 0.9;
/** Rendement ALLER-RETOUR (charge→décharge, onduleur inclus) d'un système LFP : 90 %
 *  (cellules ~95–98 %, l'onduleur/BMS enlève le reste). Prudent. */
export const LFP_ROUND_TRIP_EFFICIENCY = 0.9;
/** Dégradation de capacité annuelle d'un LFP : ~2 %/an (garanties usuelles ~70 % à 10 ans
 *  → ~3 %/an ; 2 %/an médiane observée LFP moderne). Conservateur pour le cashflow. */
export const LFP_ANNUAL_CAPACITY_FADE = 0.02;
/** Tailles de pack LFP RÉELLES du marché (kWh nominal). L'appelant choisit la plus proche
 *  du besoin de stockage. */
export const LFP_PACK_SIZES_KWH = [5, 10, 15, 20] as const;

/**
 * Profondeur de décharge (DoD) LFP retenue = 0,90. Le lithium LFP tolère 90-95 % de
 * DoD sans dégradation notable (contre ~50 % au plomb) ; on retient 0,90 (borne
 * BASSE de la fourchette 90-95 %) — choix PRUDENT : la capacité utile affichée est
 * plutôt sous-estimée que sur-promise. Réglable ici.
 */
export const BATTERY_DEPTH_OF_DISCHARGE = LFP_DOD; // doublon unifié : 0,9, même valeur que LFP_DOD
