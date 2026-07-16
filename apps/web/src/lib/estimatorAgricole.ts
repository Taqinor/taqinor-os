/**
 * Estimateur AGRICOLE (pompage solaire) du parcours public /devis/mon-toit,
 * mode « agricole ». Module PUR : aucun DOM, aucune dépendance — mêmes règles
 * d'honnêteté que billEstimate.ts (entrées hydrauliques manquantes ⇒ ok:false,
 * l'écran affiche un repli honnête ; jamais un chiffre fabriqué).
 *
 * Miroir de frontend/src/features/ventes/solar.js — garder aligné.
 * Reprend la chaîne pompage de l'ERP : CV_TO_KW (0.7355), champ PV ≈ 1.4 ×
 * puissance pompe avec panneaux 710 W (champFromKw, solar.js ~l.866-886),
 * heures de pompage par défaut 7 h (HEURES_POMPAGE_DEFAUT), m³/jour =
 * débit × heures. Ce module AJOUTE le dimensionnement hydraulique amont
 * (HMT × débit → kW pompe, formule AMEE) que l'ERP obtient, lui, des courbes
 * constructeur réelles (debitAtHmt/selectPompeByCurve) — l'ERP reste la source
 * autoritaire au moment du devis chiffré.
 */

// ── Constantes MIROIR de frontend/src/features/ventes/solar.js ──────────────
/** 1 CV = 0.7355 kW — miroir solar.js CV_TO_KW. */
export const CV_TO_KW = 0.7355;
/** Heures de pompage effectives/jour — miroir solar.js HEURES_POMPAGE_DEFAUT. */
export const HEURES_POMPAGE_DEFAUT = 7;
/** Champ PV ≈ 1.4 × puissance pompe (marché 1.3–1.5×) — miroir champFromKw. */
export const PV_FACTOR = 1.4;
/** Puissance panneau de référence (W) — miroir solar.js (panneau 710 W). */
export const PANEL_W = 710;

// ── Hypothèses PROPRES à ce module (documentées) ──────────────────────────────
/**
 * Puissance hydraulique : P(kW) = débit(m³/h) × HMT(m) × 2.725 / 1000.
 * 2.725 = ρ·g/3600 (1000 kg/m³ × 9.81 m/s² / 3600 s) — formule standard
 * du dimensionnement pompage (guides AMEE/pompage solaire).
 */
export const HYDRAULIC_COEFF = 2.725;
/**
 * Rendement global groupe motopompe (hypothèses prudentes usuelles) :
 * immergée ≈ 0.55, surface ≈ 0.50. Défaut : immergée (cas forage majoritaire).
 */
export const PUMP_EFF = { immergee: 0.55, surface: 0.5 } as const;
/** Paliers CV commerciaux des pompes du marché (catalogue usuel). */
export const CV_STEPS = [0.5, 1, 1.5, 2, 3, 4, 5.5, 7.5, 10, 12.5, 15, 20, 25, 30] as const;
/** Hauteur de refoulement par défaut quand seul le puits est connu (m). */
export const REFOULEMENT_DEFAUT_M = 2;
/** Pertes de charge (friction) : +10 % sur la HMT estimée. */
export const FRICTION_FACTOR = 1.1;
/** Bornes de plausibilité (au-delà : étude dédiée, pas d'estimation en ligne). */
export const HMT_MIN_M = 3;
export const HMT_MAX_M = 400;
export const DEBIT_MIN_M3H = 0.3;
export const DEBIT_MAX_M3H = 120;
/**
 * Économie sur le gasoil remplacé : bande 75–90 % de la dépense actuelle
 * (le solaire couvre l'essentiel du pompage diurne ; on ne promet jamais 100 %).
 */
export const FUEL_SAVING_LOW = 0.75;
export const FUEL_SAVING_HIGH = 0.9;

export interface AgriInputs {
  hmtM?: number | null;
  profondeurM?: number | null;
  refoulementM?: number | null;
  debitM3h?: number | null;
  besoinM3j?: number | null;
  heuresPompage?: number | null;
  pompeType?: 'immergee' | 'surface' | null;
  fuelSpendMadMonth?: number | null;
}

export interface AgriEstimate {
  ok: true;
  hmtM: number;
  hmtEstimated: boolean;
  debitM3h: number;
  pompeKw: number;
  pompeCv: number;
  champKwc: number;
  nbPanneaux: number;
  m3Jour: number;
  heures: number;
  fuelSavingMadYearLow?: number;
  fuelSavingMadYearHigh?: number;
  hypotheses: { pumpEff: number; pvFactor: number };
}

export type AgriEstimateResult = AgriEstimate | { ok: false; reason: 'missing_hydraulics' | 'out_of_range' | 'invalid' };

/** Nombre fourni (≠ null/undefined) mais inutilisable (NaN/négatif) ? */
function isBadNumber(v: number | null | undefined): boolean {
  if (v == null) return false;
  return !Number.isFinite(v) || v < 0;
}

/** Valeur fournie ET strictement positive ? (0 = non renseigné, jamais deviné) */
function pos(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v > 0;
}

const round1 = (v: number) => Math.round(v * 10) / 10;
const round2 = (v: number) => Math.round(v * 100) / 100;

/**
 * Estimation pompage : HMT + débit → puissance pompe (CV commercial) → champ
 * PV 1.4× (miroir champFromKw) + m³/jour. Compositions pompage : NI onduleur
 * NI batterie (règle ERP) — ce module ne dimensionne que pompe + champ.
 */
export function estimateAgricole(inputs: AgriInputs): AgriEstimateResult {
  const { hmtM, profondeurM, refoulementM, debitM3h, besoinM3j, heuresPompage, pompeType, fuelSpendMadMonth } = inputs;

  // Garde 'invalid' : une valeur FOURNIE mais NaN/négative n'est jamais devinée.
  if (
    isBadNumber(hmtM) || isBadNumber(profondeurM) || isBadNumber(refoulementM) ||
    isBadNumber(debitM3h) || isBadNumber(besoinM3j) || isBadNumber(heuresPompage) ||
    isBadNumber(fuelSpendMadMonth)
  ) {
    return { ok: false, reason: 'invalid' };
  }
  // Plus de 24 h de pompage/jour n'existe pas.
  if (pos(heuresPompage) && heuresPompage > 24) return { ok: false, reason: 'invalid' };

  // Il faut AU MOINS une info de hauteur (HMT ou profondeur) ET une info de
  // débit (m³/h ou besoin m³/j) — sinon on ne chiffre pas (repli honnête).
  if (!(pos(hmtM) || pos(profondeurM)) || !(pos(debitM3h) || pos(besoinM3j))) {
    return { ok: false, reason: 'missing_hydraulics' };
  }

  const heures = pos(heuresPompage) ? heuresPompage : HEURES_POMPAGE_DEFAUT;

  // HMT : déclarée telle quelle, sinon estimée = (profondeur + refoulement,
  // défaut 2 m) + 10 % de pertes de charge (friction) — flaggée hmtEstimated.
  let hmt: number;
  let hmtEstimated: boolean;
  if (pos(hmtM)) {
    hmt = hmtM;
    hmtEstimated = false;
  } else {
    const refoulement = typeof refoulementM === 'number' && Number.isFinite(refoulementM) && refoulementM >= 0
      ? refoulementM
      : REFOULEMENT_DEFAUT_M;
    hmt = ((profondeurM as number) + refoulement) * FRICTION_FACTOR;
    hmtEstimated = true;
  }

  // Débit : déclaré, sinon dérivé du besoin journalier sur les heures de pompage.
  const debit = pos(debitM3h) ? debitM3h : (besoinM3j as number) / heures;

  if (hmt < HMT_MIN_M || hmt > HMT_MAX_M || debit < DEBIT_MIN_M3H || debit > DEBIT_MAX_M3H) {
    return { ok: false, reason: 'out_of_range' };
  }

  // Puissance : hydraulique (AMEE) / rendement groupe, puis CV commercial
  // (plus petit palier ≥ besoin ; au-delà du catalogue 30 CV, arrondi au CV
  // entier supérieur — étude sur mesure, mais l'ordre de grandeur reste honnête).
  const eff = PUMP_EFF[pompeType ?? 'immergee'];
  const hydraulicKw = (debit * hmt * HYDRAULIC_COEFF) / 1000;
  const pompeKwNeeded = hydraulicKw / eff;
  const cvNeeded = pompeKwNeeded / CV_TO_KW;
  const pompeCv = CV_STEPS.find((s) => s >= cvNeeded) ?? Math.ceil(cvNeeded);

  // Champ PV — MIROIR EXACT de solar.js champFromKw(cv × CV_TO_KW) :
  // kW arrondi 2 déc., champ 1.4×, panneaux 710 W (min 2), kWc recalculé
  // depuis le nombre de panneaux réellement posés.
  const pompeKw = round2(pompeCv * CV_TO_KW);
  const champKw = round2(pompeKw * PV_FACTOR);
  const nbPanneaux = Math.max(2, Math.ceil((champKw * 1000) / PANEL_W));
  const champKwc = Math.round((nbPanneaux * PANEL_W) / 10) / 100;

  // m³/jour = débit × heures — même règle que l'ERP (calculé UNE fois ici).
  const m3Jour = Math.round(debit * heures);

  const base: AgriEstimate = {
    ok: true,
    hmtM: round1(hmt),
    hmtEstimated,
    debitM3h: round1(debit),
    pompeKw,
    pompeCv,
    champKwc,
    nbPanneaux,
    m3Jour,
    heures,
    hypotheses: { pumpEff: eff, pvFactor: PV_FACTOR },
  };

  // Gasoil remplacé (facultatif) : bande annuelle 75–90 % de la dépense déclarée.
  if (pos(fuelSpendMadMonth)) {
    base.fuelSavingMadYearLow = Math.round(fuelSpendMadMonth * 12 * FUEL_SAVING_LOW);
    base.fuelSavingMadYearHigh = Math.round(fuelSpendMadMonth * 12 * FUEL_SAVING_HIGH);
  }

  return base;
}
