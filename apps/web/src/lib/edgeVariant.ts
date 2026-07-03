/**
 * Staged-rollout primitive (WJ93) — un tirage de variante PAR REQUÊTE, sans
 * cookie et sans identifiant persisté (voir docs/experimentation-policy.md).
 *
 * Deux modes :
 *  - déterministe : hash stable d'une valeur déjà disponible pour CETTE
 *    requête (ex. un header, un id de commande éphémère) — la même valeur
 *    donne toujours la même variante, mais rien n'est stocké entre requêtes ;
 *  - aléatoire : tirage sans état, utile quand aucune clé stable n'existe.
 *
 * Ni l'un ni l'autre ne pose de Set-Cookie ni n'écrit de storage : c'est
 * l'appelant qui décide quoi faire du résultat pour LA réponse en cours.
 * Aucune dépendance externe.
 */

/** Poids relatif d'une variante dans un tirage à N variantes. */
export interface WeightedVariant<T extends string> {
  variant: T;
  /** Poids relatif (> 0). N'a pas besoin de sommer à 1 — normalisé en interne. */
  weight: number;
}

function normalizeWeights<T extends string>(variants: readonly WeightedVariant<T>[]): WeightedVariant<T>[] {
  if (variants.length === 0) throw new Error('edgeVariant: at least one variant is required');
  const total = variants.reduce((sum, v) => sum + v.weight, 0);
  if (!(total > 0)) throw new Error('edgeVariant: variant weights must sum to a positive number');
  return variants.map((v) => ({ variant: v.variant, weight: v.weight / total }));
}

/** FNV-1a 32 bits — même fonction de hash que lead.ts (leadLogId), stable et sans dépendance. */
function fnv1a(input: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function pick<T extends string>(fraction: number, normalized: WeightedVariant<T>[]): T {
  let acc = 0;
  for (const v of normalized) {
    acc += v.weight;
    if (fraction < acc) return v.variant;
  }
  // Filet de sécurité en cas d'arrondi flottant : dernière variante.
  return normalized[normalized.length - 1].variant;
}

/**
 * Tirage DÉTERMINISTE : hash d'une clé fournie par l'appelant (ex. un header
 * de requête, un id de commande) vers l'une des variantes pondérées. Même clé
 * → même variante, toujours ; aucun état n'est conservé entre appels.
 */
export function pickVariantFromKey<T extends string>(key: string, variants: readonly WeightedVariant<T>[]): T {
  const normalized = normalizeWeights(variants);
  const fraction = fnv1a(key) / 0xffffffff;
  return pick(fraction, normalized);
}

/**
 * Tirage ALÉATOIRE sans état, pour quand aucune clé stable n'est disponible
 * pour cette requête. Toujours sans cookie : le résultat n'est valable que
 * pour la réponse en cours — l'appelant ne doit PAS le persister lui-même
 * pour retrouver la même variante à la requête suivante (voir la doctrine
 * « no inferential A/B » dans docs/experimentation-policy.md : on compare des
 * cohortes/périodes, pas des visiteurs suivis).
 */
export function pickRandomVariant<T extends string>(variants: readonly WeightedVariant<T>[]): T {
  const normalized = normalizeWeights(variants);
  return pick(Math.random(), normalized);
}

/**
 * Sucre pour le cas binaire le plus courant d'un rollout étagé : une
 * proportion `rolloutFraction` (0–1) de requêtes voit `on`, le reste `off`.
 * Déterministe si `key` est fourni, sinon aléatoire sans état.
 */
export function stagedRollout(rolloutFraction: number, key?: string): 'on' | 'off' {
  const fraction = Math.min(1, Math.max(0, rolloutFraction));
  const variants: WeightedVariant<'on' | 'off'>[] = [
    { variant: 'on', weight: fraction },
    { variant: 'off', weight: 1 - fraction },
  ];
  return key !== undefined ? pickVariantFromKey(key, variants) : pickRandomVariant(variants);
}
