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
  climateDerateFactor,
  optimalSouthTiltDeg,
  productionConfidenceBand,
  specificYield,
  tariffForCity,
  type ProductionBand,
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
  /**
   * WJ71 — bande de confiance climatique (kWh production, puis MAD économies
   * dérivées à la même proportion), SURFACÉE PAR DÉFAUT sur l'estimation
   * publique. Avant WJ71, `productionConfidenceBand`/`climateDerateFactor`
   * (estimatorBrainV2.ts, WJ22) n'étaient appelés QUE dans le labo privé — la
   * page publique affichait un seul chiffre de production sans jamais dire
   * qu'un été côtier chaud/poussiéreux le réduit réellement de ~15–20 %.
   * `productionBand.low` est le même `productionKwhYr` déjà affiché × le
   * dérate climatique documenté (jamais un chiffre en MOINS inventé — une
   * décomposition documentée de pertes déjà réelles) ; `high` = le chiffre nu
   * déjà affiché. Les économies suivent la MÊME proportion (le modèle
   * d'économies n'a pas de fonction dérate propre — on applique le même ratio
   * production pour rester honnête sans réinventer un second modèle).
   */
  productionBand: ProductionBand;
  savingsLowBand: number;
  savingsHighBand: number;
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

  // WJ71 — bande de confiance climatique, DÉFAUT ON pour l'estimation publique
  // (cf. note d'interface ci-dessus). `high` = le chiffre nu déjà affiché
  // (identique à productionKwhYr avant arrondi) ; `low` = ce même chiffre ×
  // le dérate climatique documenté (été côtier : thermique + salissure + brume).
  const productionBand = productionConfidenceBand(productionKwhYr);
  // Les économies suivent la MÊME proportion basse/haute que la production —
  // on ne réinvente pas un second modèle d'économies, on reflète honnêtement
  // que moins de kWh produits ⇒ proportionnellement moins de kWh autoconsommés.
  const bandRatioLow = productionKwhYr > 0 ? productionBand.low / productionKwhYr : 1;

  return {
    kwc,
    productionKwhYr: Math.round(productionKwhYr),
    savingsLow: roundMad(low),
    savingsHigh: roundMad(high),
    savingsMonthlyLow: roundMad(low / 12),
    savingsMonthlyHigh: roundMad(high / 12),
    paybackLabel: payback,
    latitudeUsed: lat,
    productionBand,
    savingsLowBand: roundMad(low * bandRatioLow),
    savingsHighBand: roundMad(high),
  };
}

/**
 * WJ71 — dérate climatique BRUT (0–1], exposé pour l'affichage d'un libellé
 * (« ≈ X % en été côtier ») sans que l'appelant ait à réimporter
 * estimatorBrainV2 directement. Fonction compagnon PURE, aucun état.
 */
export function climateConfidenceFactor(): number {
  return climateDerateFactor();
}

/**
 * WJ70 — HONNÊTETÉ DU SÉLECTEUR DISTRIBUTEUR. `distributeur` (ONEE/Lydec/
 * Redal, collecté par le formulaire — cf. `DISTRIBUTEURS` dans lib/lead.ts)
 * ne change AUJOURD'HUI aucun chiffre affiché : `tariffForCity`/
 * `TARIFF_BY_CITY` (estimatorBrainV2.ts, WJ23) égalent encore Lydec/Redal au
 * barème RÉGIE ONEE — la grille exacte des délégataires attend une vraie
 * facture récente par ville (voir le commentaire de TARIFF_BY_CITY). Router
 * le choix collecté vers un calcul qui ne produit RIEN de différent serait
 * une fausse promesse de personnalisation. Cette fonction retourne donc un
 * texte honnête à afficher À CÔTÉ du sélecteur, jamais un chiffre inventé —
 * dès que WG2 livre les vraies grilles délégataires, `tariffForCity`
 * commencera à diverger et cette note perdra sa raison d'être (à retirer
 * alors).
 */
export function distributeurHonestyNote(locale: 'fr' | 'ar' = 'fr'): string {
  return locale === 'ar'
    ? 'التقدير أدناه يعتمد حالياً على تعريفة المكتب الوطني (ONEE) المتحفظة لجميع الموزعين، إلى حين توفر شبكات أسعار حقيقية لكل موزع.'
    : "Cette estimation utilise pour l'instant le barème ONEE (conservateur) pour tous les distributeurs, en attendant les grilles tarifaires réelles par distributeur.";
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
