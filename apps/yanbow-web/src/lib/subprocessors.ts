/**
 * Registre des sous-traitants et hôtes tiers (YBW11, rempli par YBW26).
 *
 * La Content-Security-Policy du Worker (worker/headers.mjs) est CONSTRUITE à
 * partir de ce registre : un hôte tiers n'est autorisé par la CSP que s'il y a
 * une entrée ici. Registre VIDE au départ = CSP `'self'` seulement.
 */

/** Directives CSP qu'un sous-traitant peut ouvrir. */
export type DirectiveCsp = 'connect-src' | 'img-src' | 'script-src' | 'frame-src' | 'form-action' | 'font-src' | 'style-src';

export interface SousTraitant {
  /** Identifiant stable (ex. « cloudflare »). */
  id: string;
  /** Nom affiché sur la page Confidentialité. */
  nom: string;
  /** Rôle / finalité, en français. */
  role: string;
  /** Hôtes (origines https://…) ouverts dans la CSP, par directive. */
  csp: Partial<Record<DirectiveCsp, string[]>>;
}

export const SOUS_TRAITANTS: SousTraitant[] = [];

/** Hôtes à ajouter à chaque directive CSP, dédoublonnés, dans l'ordre du registre. */
export function sourcesCsp(registre: readonly SousTraitant[] = SOUS_TRAITANTS): Partial<Record<DirectiveCsp, string[]>> {
  const out: Partial<Record<DirectiveCsp, string[]>> = {};
  for (const st of registre) {
    for (const [directive, hotes] of Object.entries(st.csp) as [DirectiveCsp, string[]][]) {
      const liste = (out[directive] ??= []);
      for (const h of hotes) if (!liste.includes(h)) liste.push(h);
    }
  }
  return out;
}
