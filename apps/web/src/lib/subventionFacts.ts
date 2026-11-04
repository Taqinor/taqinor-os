/**
 * WAUD73 — faits publiés de la page « Subvention et aides » : UNE source pour les chiffres.
 * La règle FDA est celle déjà publiée sur /pompage-solaire (D-AGR-6, Guide FDA 2024) ; le tarif
 * d'excédent vient de constants82_21.ts (ANRE 04/26). Aucun autre montant n'a le droit d'apparaître
 * sur la page (test : tout chiffre affiché vient d'ici).
 */
export const FDA_TAUX_PCT = 30;
export const FDA_PLAFOND_PAR_HA_DH = 3000;
export const FDA_PLAFOND_PAR_KWC_DH = 3000;
export const FDA_PLAFOND_PAR_PROJET_DH = 30000;
export const FDA_SOURCE_FR = 'Guide FDA 2024, p. 20-23 — relevé le 2 octobre 2026';
export const FDA_SOURCE_EN = 'FDA Guide 2024, pp. 20-23 — read on 2 October 2026';
export const FDA_SOURCE_AR = 'دليل FDA 2024، ص 20-23 — اطُّلع عليه في 2 أكتوبر 2026';

/** Période de validité du tarif d'excédent ANRE (décision 04/26), telle que citée par constants82_21.ts. */
export const ANRE_PERIODE_FR = '1er mars 2026 au 28 février 2027';
export const ANRE_PERIODE_EN = '1 March 2026 to 28 February 2027';
export const ANRE_PERIODE_AR = 'من فاتح مارس 2026 إلى 28 فبراير 2027';
