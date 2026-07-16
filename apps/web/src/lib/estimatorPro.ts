/**
 * Estimateur PROFESSIONNEL (C&I — autoconsommation) du parcours public
 * /devis/mon-toit, mode « professionnel ». Module PUR : aucun DOM, aucune
 * dépendance — mêmes règles d'honnêteté que billEstimate.ts (jamais un chiffre
 * fabriqué : entrées manquantes ⇒ ok:false, l'écran affiche un repli honnête).
 *
 * Miroir de frontend/src/features/ventes/solar.js — garder aligné.
 * La logique reprend computeEtudeIndustrielle (solar.js ~l.807-841) :
 * production mensuelle = GHI[i] × kWc × EFFICIENCY, autoconsommé =
 * min(production, conso × part diurne), taux d'autoconso/couverture identiques.
 * Ce module AJOUTE seulement le dimensionnement inverse (kWc depuis la conso)
 * et une fourchette économies/payback — l'ERP reste la source autoritaire au
 * moment du devis chiffré.
 */

// ── Constantes MIROIR de frontend/src/features/ventes/solar.js ──────────────
// GHI mensuelle Maroc (kWh/m²) — copie EXACTE de solar.js GHI (elle-même
// miroir de backend quote_engine/constants.py, parité testée côté ERP).
export const GHI = [
  83.99, 96.79, 133.43, 155.3, 175.28, 179.62,
  179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
] as const;
/** Rendement global — miroir solar.js EFFICIENCY. */
export const EFFICIENCY = 0.8;
/** Puissance panneau de référence (W) — miroir solar.js (panneau 710 W). */
export const PANEL_W = 710;

// ── Hypothèses PROPRES à ce module (documentées, à affiner) ──────────────────
/**
 * Tarifs électricité PROFESSIONNELS (MAD/kWh TTC) — CONSTANTES D'HYPOTHÈSE,
 * chiffres INDICATIFS des grilles ONEE à affiner avec de vraies factures :
 *  - MT (moyenne tension) : blend ≈ 1,15 MAD/kWh TTC (heures pleines/creuses/
 *    pointe confondues, ordre de grandeur ONEE MT usage général) ;
 *  - BT professionnel (force motrice / usage pro basse tension) : ≈ 1,40.
 * Jamais présentés comme un tarif exact — uniquement une base d'estimation.
 */
export const TARIF_MT_MAD_KWH = 1.15;
export const TARIF_BT_PRO_MAD_KWH = 1.4;

/**
 * Part diurne de la consommation selon le profil d'activité.
 * 'day' = 0.80 : ALIGNÉ sur l'ERP (solar.js DAY_USAGE_DEFAULTS —
 * Commerciale/Industrielle = 80 %, le défaut du curseur DevisGenerator pour
 * un site actif en journée) — préféré au 0.85 initialement proposé, pour que
 * l'estimation publique et l'étude ERP partent de la même hypothèse.
 * 'day_evening' (activité jour + soirée) et 'continuous' (24/7) n'ont pas
 * d'équivalent ERP : hypothèses propres documentées (0.65 / 0.45).
 */
export const DAY_SHARE_BY_PROFILE = {
  day: 0.8,
  day_evening: 0.65,
  continuous: 0.45,
} as const;
/** Sans profil déclaré : 0.80, le défaut ERP (dayUsagePct 80 % en C&I). */
export const DEFAULT_DAY_SHARE = 0.8;

/** Surface ≈ 6 m²/kWc (panneaux 710 W + allées/ombres, hypothèse marché). */
export const M2_PER_KWC = 6;

/**
 * Prix indicatif du kWc installé C&I (MAD TTC) — BANDE D'HYPOTHÈSE (jamais un
 * devis) : 8 500–11 000 MAD/kWc selon taille/toiture. À affiner.
 */
export const PRIX_KWC_LOW = 8500;
export const PRIX_KWC_HIGH = 11000;

/** Garde-fous anti-garbage : au-delà, étude dédiée (pas d'estimation en ligne). */
export const MAX_CONSO_MENSUELLE_KWH = 200_000;
export const MAX_BILL_PRO_MAD = 1_000_000;

/** Somme GHI annuelle (kWh/m²) — dérivée, pour le dimensionnement inverse. */
const GHI_SUM = GHI.reduce((s, v) => s + v, 0);

export interface ProInputs {
  monthlyKwh?: number | null;
  monthlyMad?: number | null;
  raccordement?: 'bt' | 'mt' | null;
  activityProfile?: 'day' | 'day_evening' | 'continuous' | null;
  surfaceType?: 'bac_acier' | 'terrasse' | 'ombriere' | 'terrain' | null;
  surfaceM2?: number | null;
}

export interface ProEstimate {
  ok: true;
  kwc: number;
  nbPanneaux: number;
  prodAnnuelleKwh: number;
  consoAnnuelleKwh: number;
  tauxAutoconso: number;
  tauxCouverture: number;
  ecoAnnuelleMadLow: number;
  ecoAnnuelleMadHigh: number;
  paybackYearsLow: number;
  paybackYearsHigh: number;
  surfaceCapped: boolean;
  hypotheses: { tarifMadKwh: number; dayShare: number; prixKwcLow: number; prixKwcHigh: number };
}

export type ProEstimateResult = ProEstimate | { ok: false; reason: 'missing_conso' | 'too_large' | 'invalid' };

/** Nombre fourni (≠ null/undefined/0) mais inutilisable (NaN/négatif) ? */
function isBadNumber(v: number | null | undefined): boolean {
  if (v == null) return false;
  return !Number.isFinite(v) || v < 0;
}

/**
 * Estimation professionnelle « autoconsommation d'abord » (philosophie loi
 * 82-21 : pas d'injection valorisée — on dimensionne pour couvrir la part
 * DIURNE de la consommation, jamais plus).
 */
export function estimatePro(inputs: ProInputs): ProEstimateResult {
  const { monthlyKwh, monthlyMad, raccordement, activityProfile, surfaceM2 } = inputs;

  // Garde 'invalid' : une valeur FOURNIE mais NaN/négative n'est jamais devinée.
  if (isBadNumber(monthlyKwh) || isBadNumber(monthlyMad) || isBadNumber(surfaceM2)) {
    return { ok: false, reason: 'invalid' };
  }

  // Tarif d'hypothèse selon le raccordement (défaut BT : la plupart des petits
  // pros sont en basse tension — hypothèse documentée, jamais un tarif exact).
  const tarif = raccordement === 'mt' ? TARIF_MT_MAD_KWH : TARIF_BT_PRO_MAD_KWH;

  // Conso mensuelle : kWh déclarés prioritaires, sinon facture / tarif.
  const hasKwh = typeof monthlyKwh === 'number' && monthlyKwh > 0;
  const hasMad = typeof monthlyMad === 'number' && monthlyMad > 0;
  if (!hasKwh && !hasMad) return { ok: false, reason: 'missing_conso' };

  const consoMensuelle = hasKwh ? (monthlyKwh as number) : (monthlyMad as number) / tarif;
  if (consoMensuelle > MAX_CONSO_MENSUELLE_KWH || (hasMad && (monthlyMad as number) > MAX_BILL_PRO_MAD)) {
    return { ok: false, reason: 'too_large' };
  }

  const consoAnnuelle = consoMensuelle * 12;
  const dayShare = (activityProfile && DAY_SHARE_BY_PROFILE[activityProfile]) || DEFAULT_DAY_SHARE;

  // Dimensionnement : production annuelle ≈ conso annuelle × part diurne
  // (autoconsommation d'abord — on ne dimensionne jamais pour injecter).
  // Production annuelle par kWc = ΣGHI × EFFICIENCY (miroir computeEtudeIndustrielle).
  const prodParKwc = GHI_SUM * EFFICIENCY;
  const kwcCible = (consoAnnuelle * dayShare) / prodParKwc;
  // Arrondi au demi-kWc, plancher 2 kWc (taille C&I minimale sensée).
  let kwc = Math.max(2, Math.round(kwcCible * 2) / 2);

  // Plafond surface : ≈ 6 m²/kWc. Le toit gagne toujours sur le besoin (on ne
  // chiffre jamais plus que ce qui tient) — arrondi VERS LE BAS au demi-kWc.
  let surfaceCapped = false;
  if (typeof surfaceM2 === 'number' && surfaceM2 > 0) {
    const maxKwc = Math.max(0.5, Math.floor((surfaceM2 / M2_PER_KWC) * 2) / 2);
    if (kwc > maxKwc) {
      kwc = maxKwc;
      surfaceCapped = true;
    }
  }

  const nbPanneaux = Math.ceil((kwc * 1000) / PANEL_W);

  // Production/autoconsommation recalculées avec le kWc FINAL — mêmes formules
  // que solar.js computeEtudeIndustrielle (prod mensuelle GHI × kwc × EFF).
  const prodM = GHI.map((g) => g * kwc * EFFICIENCY);
  const prodA = prodM.reduce((a, b) => a + b, 0);
  const autoconsomme = Math.min(prodA, consoAnnuelle * dayShare);
  const tauxAutoconso = prodA > 0 ? Math.round((autoconsomme / prodA) * 1000) / 10 : 0;
  const tauxCouverture = Math.round((autoconsomme / consoAnnuelle) * 1000) / 10;

  // Économies = kWh autoconsommés × tarif d'hypothèse, bande ±10 % (le tarif
  // réel du site varie autour du blend indicatif). Les bornes sont arrondies
  // à un grain lisible et HONNÊTE (une fourchette d'estimation à 6 chiffres
  // significatifs serait de la fausse précision) : plancher/plafond au grain,
  // donc la fourchette ne rétrécit jamais.
  const eco = autoconsomme * tarif;
  const ecoGrain = eco * 0.9 >= 20_000 ? 1000 : 100;
  const ecoAnnuelleMadLow = Math.max(ecoGrain, Math.floor((eco * 0.9) / ecoGrain) * ecoGrain);
  const ecoAnnuelleMadHigh = Math.ceil((eco * 1.1) / ecoGrain) * ecoGrain;

  // Payback = investissement d'hypothèse / économies : borne basse optimiste
  // (prix bas / éco haute), borne haute prudente (prix haut / éco basse).
  const paybackYearsLow = Math.round(((PRIX_KWC_LOW * kwc) / ecoAnnuelleMadHigh) * 10) / 10;
  const paybackYearsHigh = Math.round(((PRIX_KWC_HIGH * kwc) / ecoAnnuelleMadLow) * 10) / 10;

  return {
    ok: true,
    kwc,
    nbPanneaux,
    prodAnnuelleKwh: Math.round(prodA),
    consoAnnuelleKwh: Math.round(consoAnnuelle),
    tauxAutoconso,
    tauxCouverture,
    ecoAnnuelleMadLow,
    ecoAnnuelleMadHigh,
    paybackYearsLow,
    paybackYearsHigh,
    surfaceCapped,
    hypotheses: { tarifMadKwh: tarif, dayShare, prixKwcLow: PRIX_KWC_LOW, prixKwcHigh: PRIX_KWC_HIGH },
  };
}
