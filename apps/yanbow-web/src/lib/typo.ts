/**
 * Typographie française et polices critiques (YBW39).
 *
 * Règles (vérifiées sur le HTML RENDU par tests/fonts.test.ts) :
 *  - espace insécable U+00A0 avant `;` `:` `?` `!` et à l'intérieur de « » ;
 *  - JAMAIS U+202F (espace fine insécable), U+2009 (espace fine) ni U+2192 (→) :
 *    absents des polices du site → carré vide ou police de secours ;
 *    les flèches sont des icônes SVG.
 */

export const NBSP = ' ';
/** Caractères interdits dans le HTML rendu (absents des polices). */
export const INTERDITS: Record<string, string> = {
  ' ': 'espace fine insécable U+202F',
  ' ': 'espace fine U+2009',
  '→': 'flèche U+2192 (utiliser une icône SVG)',
};

/**
 * Applique la typographie française à un texte : espaces fines → U+00A0,
 * U+00A0 avant `; : ? !` (une seule fois devant une suite comme « ?! »), et à
 * l'intérieur des guillemets. Ne touche pas un deux-points collé (heure 10:30,
 * `https://`) : seulement une ponctuation suivie d'une espace, d'un guillemet
 * fermant ou de la fin du texte.
 */
export function typoFr(texte: string): string {
  return texte
    .replace(/[  ]/g, NBSP)
    .replace(/(\S)[  ]?([;:?!]+)(?=[\s»"')\]]|$)/g, `$1${NBSP}$2`)
    .replace(/«[  ]*/g, `«${NBSP}`)
    .replace(/[  ]*»/g, `${NBSP}»`);
}

/** Écarts typographiques d'un texte FRANÇAIS (vide = conforme). */
export function ecartsTypoFr(texte: string): string[] {
  const out: string[] = [];
  for (const [c, nom] of Object.entries(INTERDITS)) if (texte.includes(c)) out.push(nom);
  for (const m of texte.matchAll(/(\S)( ?)([;:?!]+)(?=[\s»"')\]]|$)/g)) {
    out.push(`« ${m[0]} » : espace insécable U+00A0 attendue avant « ${m[3]} »`);
  }
  if (/«(?! )/.test(texte)) out.push('« : espace insécable attendue après le guillemet ouvrant');
  if (/(?<! )»/.test(texte)) out.push('» : espace insécable attendue avant le guillemet fermant');
  return out;
}

/**
 * Les 2 fichiers de police CRITIQUES préchargés (direction A provisoire :
 * Outfit pour les titres, Instrument Sans pour le texte — YBW42/YBW44).
 * Noms versionnés écrits par scripts/build-fonts.mjs.
 */
export const POLICES_PRECHARGEES = ['/fonts/outfit-latin-wght-5.3.0.woff2', '/fonts/instrument-sans-latin-wght-5.3.0.woff2'] as const;
