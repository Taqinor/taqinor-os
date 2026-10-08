/**
 * Noms de la marque et des produits (YBW19) — SOURCE UNIQUE.
 *
 * Pages, navigation, balises meta, JSON-LD et valeurs du champ « produit » du
 * formulaire lisent ces constantes ; aucun nom produit n'est écrit en dur
 * ailleurs (hors dictionnaires et registre des affirmations — test
 * `tests/brand.test.ts`). Jamais de ™ ni de ® (la vérification du nom n'est
 * pas faite, YBWM14).
 */
import type { Locale } from '../i18n/config';

export const MARQUE = 'YanBow';

export const PRODUITS = {
  solarbow: { nom: 'SolarBow' },
  marketingbow: { nom: 'MarketingBow' },
} as const;

/** Slogan (D-YBW-12) — identique dans les deux langues ; coloration A/B en attente (YBWM11). */
export const SLOGAN: Record<Locale, string> = {
  fr: 'Your Arrow Needs 1Bow',
  en: 'Your Arrow Needs 1Bow',
};

/** Valeurs du champ « produit » du formulaire de rendez-vous (contrat YBW50). */
export const VALEURS_PRODUIT = ['solarbow', 'marketingbow', 'sur_mesure'] as const;
export type ValeurProduit = (typeof VALEURS_PRODUIT)[number];

/** Libellé d'une valeur du champ « produit ». */
export function libelleProduit(valeur: ValeurProduit, locale: Locale): string {
  if (valeur === 'sur_mesure') return locale === 'en' ? 'Custom software' : 'Développement sur mesure';
  return PRODUITS[valeur].nom;
}
