/**
 * WJ1 — ESTIMATION INSTANTANÉE À PARTIR DE LA FACTURE SEULE (avant la porte de
 * contact). Module PUR, sans DOM ni carte : il RÉUTILISE le cerveau honnête
 * `estimatorBrainV2.ts` (barème RÉGIE ONEE, table PVGIS committée) pour
 * transformer une facture mensuelle (MAD) en :
 *   - une puissance recommandée (kWc) dimensionnée au besoin annuel ;
 *   - une production annuelle (kWh) au sud optimal de la latitude ;
 *   - une FOURCHETTE d'économies annuelles (MAD) — autoconsommation d'abord,
 *     loi 82-21 : on ne valorise que les kWh autoconsommés, AUCUNE ligne
 *     d'injection/net-billing (tarif BT ANRE non publié).
 *
 * Le repère sur le toit est FACULTATIF : sans tracé, l'estimation vient de la
 * facture seule (sud optimal, latitude par défaut Casablanca). Le tracé/affinage
 * vient ensuite. AUCUN chiffre inventé : tout trace au cerveau testé. Quand la
 * facture est absente ou non chiffrable, on renvoie `null` (l'écran affiche alors
 * « estimation indisponible », jamais une valeur fabriquée).
 *
 * L'amortissement réutilise le `paybackLabel` déjà committé des bandes de tranche
 * (billRange.ts) — une constante existante, pas un nombre inventé : on ne dispose
 * d'aucun prix €/kWc fiable côté site, donc on ne calcule PAS un payback chiffré.
 *
 * WJ69 — UN SEUL MOTEUR D'ESTIMATION. Ce module pointait auparavant vers
 * `estimatorBrain.ts` (V1) ; il pointe désormais vers `estimatorBrainV2.ts`.
 * Les 5 fonctions importées ci-dessous sont PROUVÉES identiques (mêmes
 * signatures ET mêmes corps — vérifié fonction par fonction, voir
 * BRAIN_V2_NOTES.md et tests/estimatorBrainV2.test.ts « parité V2 == V1 »)
 * SAUF `optimalSouthTiltDeg`, qui gagne un second paramètre `aspect`
 * OPTIONNEL (défaut 0 = plein sud, le comportement V1 exact) — cet appel ici
 * ne passe qu'un seul argument (la latitude), donc le comportement reste
 * BYTE-IDENTIQUE pour cette page. La sortie de `estimateFromBill` est donc
 * INCHANGÉE ; V2 apporte en plus (non appelé ici) le balayage d'inclinaison
 * capé au besoin, les tarifs par régie (WJ23) et la bande de confiance
 * climatique (WJ22) — cf. WJ70/WJ71 pour leur surface publique.
 */
import {
  PANEL2_WATT,
  annualSavingsMad,
  billToAnnualKwh,
  optimalSouthTiltDeg,
  specificYield,
  tariffForCity,
} from './estimatorBrainV2';
import { LOCAL_PAYBACK_BY_KWC, type PaybackHint } from './billRange';

/** Latitude par défaut quand le client n'a pas (encore) posé de repère : Casablanca
 *  — même défaut conservateur que roofPro2.ts. Affiné dès qu'un repère est posé. */
export const DEFAULT_LAT = 33.5;

/** Marge de couverture (cible + 10 %) — alignée sur estimatorBrain.recommend(). */
const COVERAGE_MARGIN = 1.1;

export interface BillEstimate {
  /** Puissance recommandée arrondie (kWc), dimensionnée au besoin annuel. */
  kwc: number;
  /** Production annuelle estimée (kWh, sud optimal de la latitude). */
  productionKwhYr: number;
  /** Économies annuelles MAD — borne basse / haute (autoconsommation 75–100 %). */
  savingsLow: number;
  savingsHigh: number;
  /** Économies MENSUELLES MAD (fourchette) — cadrage « ≈ X MAD/mois ». */
  savingsMonthlyLow: number;
  savingsMonthlyHigh: number;
  /** Libellé d'amortissement indicatif (constante billRange, jamais inventé). */
  paybackLabel: string;
  /** Latitude réellement utilisée (repère si fourni, sinon défaut). */
  latitudeUsed: number;
}

/** Arrondi « commercial » d'une fourchette MAD à la centaine la plus proche. */
function roundMad(v: number): number {
  if (!Number.isFinite(v) || v <= 0) return 0;
  return Math.round(v / 100) * 100;
}

/**
 * Estimation à partir de la facture mensuelle (MAD). `opts.lat` affine la
 * production dès qu'un repère est posé ; `opts.city` choisit la grille tarifaire.
 * Renvoie `null` si la facture n'est pas un nombre fini > 0 (estimation honnête
 * indisponible — surtout pas un chiffre fabriqué).
 */
export function estimateFromBill(
  monthlyBillMad: number,
  opts: { lat?: number; city?: string } = {},
): BillEstimate | null {
  if (!Number.isFinite(monthlyBillMad) || monthlyBillMad <= 0) return null;

  const lat = Number.isFinite(opts.lat) ? (opts.lat as number) : DEFAULT_LAT;
  const grid = tariffForCity(opts.city);

  // Besoin annuel (kWh) déduit de la facture (barème sélectif inversé, honnête).
  const targetAnnualKwh = billToAnnualKwh(monthlyBillMad, grid);
  if (!(targetAnnualKwh > 0)) return null;

  // Dimensionnement au besoin : kWc pour couvrir la cible + marge, au sud optimal.
  const tilt = optimalSouthTiltDeg(lat);
  const yld = specificYield(lat, tilt, 0);
  if (!(yld > 0)) return null;
  const kwcExact = (targetAnnualKwh * COVERAGE_MARGIN) / yld;
  // Arrondi au demi-kWc le plus proche, jamais sous 1 kWc (cohérent avec le besoin).
  const kwc = Math.max(1, Math.round(kwcExact * 2) / 2);

  const productionKwhYr = kwc * yld;
  const { low, high } = annualSavingsMad(productionKwhYr, targetAnnualKwh, grid);

  const payback = paybackForKwc(kwc);

  return {
    kwc,
    productionKwhYr: Math.round(productionKwhYr),
    savingsLow: roundMad(low),
    savingsHigh: roundMad(high),
    savingsMonthlyLow: roundMad(low / 12),
    savingsMonthlyHigh: roundMad(high / 12),
    paybackLabel: payback,
    latitudeUsed: lat,
  };
}

/** Libellé d'amortissement par taille (constante committée, jamais inventé). */
function paybackForKwc(kwc: number): string {
  let chosen: PaybackHint = LOCAL_PAYBACK_BY_KWC[LOCAL_PAYBACK_BY_KWC.length - 1];
  for (const hint of LOCAL_PAYBACK_BY_KWC) {
    if (kwc <= hint.maxKwc) {
      chosen = hint;
      break;
    }
  }
  return chosen.paybackLabel;
}

/**
 * Formatage MAD lisible (séparateur d'espace insécable, sans décimale) — pur,
 * indépendant de la locale du navigateur pour rester déterministe (tests).
 */
export function formatMad(v: number): string {
  const n = Math.max(0, Math.round(v));
  return n.toLocaleString('fr-FR').replace(/ | |,/g, ' ').trim();
}

/** Fourchette MAD « X – Y » (déjà arrondie). Si bornes égales, un seul nombre. */
export function formatMadRange(low: number, high: number): string {
  if (low <= 0 && high <= 0) return '—';
  if (Math.round(low) === Math.round(high)) return `${formatMad(high)} MAD`;
  return `${formatMad(low)} – ${formatMad(high)} MAD`;
}
