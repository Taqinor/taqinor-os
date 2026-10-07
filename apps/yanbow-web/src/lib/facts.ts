/**
 * Registre des VALEURS chiffrées (YBW18) — le seul endroit où un nombre avec
 * unité peut vivre (`scripts/check-claims.mjs` refuse un chiffre avec unité
 * dans les dictionnaires et le registre des affirmations).
 *
 * Règle « faits vérifiés seulement » : chaque valeur porte sa source, la date
 * à laquelle elle a été relevée et la personne qui en répond. Vide au départ :
 * le site n'affiche aujourd'hui AUCUN chiffre.
 */

export interface Fait {
  valeur: string | number;
  unite?: string;
  /** Où la valeur a été relevée (chemin:ligne du dépôt, URL, document). */
  source: string;
  /** Date du relevé (AAAA-MM-JJ). */
  date: string;
  /** Qui en répond (ex. « Reda »). */
  proprietaire: string;
}

export const FAITS: Record<string, Fait> = {};

/** La valeur `id` ; LÈVE si elle n'est pas au registre. */
export function fait(id: string, registre: Record<string, Fait> = FAITS): Fait {
  const f = registre[id];
  if (!f) throw new Error(`fait inconnu : ${id}`);
  return f;
}
