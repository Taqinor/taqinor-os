/**
 * Texte public d'une affirmation du registre (YBW61-66) — la SEULE façon pour
 * une page d'affirmer un fait : la phrase rendue EST `texte_fr` (typographie
 * française appliquée) ou `texte_en`, jamais une reformulation. `cite` LÈVE si
 * l'identifiant est inconnu ou non publiable : la page ne se construit pas.
 * Le rendu porte `data-affirmation="<ID>"` (composant `Affirmation.astro`),
 * lu par la fiche de relecture YBW67 et par `tests/pages.test.ts`.
 *
 * (Module séparé de claims.ts : claims.ts doit rester SANS import de valeur,
 * scripts/check-claims.mjs le transpile seul.)
 */
import type { Locale } from '../i18n/config';
import { AFFIRMATIONS, cite, type Affirmation } from './claims';
import { typoFr } from './typo';

/** La phrase publique de l'affirmation `id` dans `locale` ; LÈVE si inconnue, non publiable ou non traduite. */
export function texteAffirmation(id: string, locale: Locale): string {
  const a = cite(id);
  if (locale === 'fr') return typoFr(a.texte_fr);
  if (!a.texte_en) throw new Error(`affirmation ${id} : aucune version anglaise approuvée (YBW70)`);
  return a.texte_en;
}

/**
 * Les identifiants PUBLIABLES parmi `ids`, dans leur ordre (un module de page
 * ne s'affiche que s'il en reste au moins un). Ne lève jamais.
 */
export function publiables(ids: readonly string[], registre: readonly Affirmation[] = AFFIRMATIONS): string[] {
  return ids.filter((id) => registre.find((a) => a.id === id)?.publiable === true);
}
