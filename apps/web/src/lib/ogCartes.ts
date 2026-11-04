/**
 * WAUD72 — choix de la carte de partage (Open Graph) d'une page.
 *
 * 1. Une page restée sur le repli `accueil` reçoit la carte de SON sujet quand son chemin en a une
 *    (tunnel, FAQ, réalisations, à-propos, billets…) — accueil.png ne sert plus qu'à l'accueil et aux
 *    pages légales.
 * 2. Une page EN/AR reçoit la variante de sa langue (`<carte>-en.png` / `<carte>-ar.png`, générées par
 *    scripts/generate-og.mjs pour CHAQUE carte de base) : plus de texte français partagé depuis /en/ ou
 *    /ar/. Les cartes déjà localisées (`ville-<slug>-<fr|en|ar>`) et la carte neutre des propositions
 *    tokenisées restent telles quelles.
 */
export type LocaleOg = 'fr' | 'en' | 'ar';

/** Chemin FR (sans préfixe de langue, barre finale) → carte de base. */
export const CARTE_PAR_CHEMIN: Record<string, string> = {
  '/devis/mon-toit/': 'tunnel',
  '/faq/': 'faq',
  '/marocains-du-monde/': 'marocains-du-monde',
  '/pourquoi-taqinor/': 'pourquoi-taqinor',
  '/realisations/': 'realisations',
  '/à-propos/': 'a-propos',
  '/blog/bienvenue-blog-taqinor/': 'blog',
  '/blog/loi-82-21-autoproduction-2026/': 'loi-82-21',
  '/blog/prix-installation-solaire-maroc-2026/': 'prix',
  '/blog/recharger-voiture-electrique-solaire-cout-maroc/': 'recharge-voiture-electrique-solaire',
};

/** Cartes qui ne se déclinent pas par langue. */
const SANS_VARIANTE = new Set(['proposition']);

export function carteOg(ogSlug: string, cheminFr: string, locale: LocaleOg): string {
  let chemin = cheminFr;
  try {
    chemin = decodeURIComponent(cheminFr);
  } catch {
    /* chemin déjà décodé */
  }
  if (!chemin.endsWith('/')) chemin += '/';
  const base = ogSlug === 'accueil' ? (CARTE_PAR_CHEMIN[chemin] ?? 'accueil') : ogSlug;
  if (locale === 'fr' || SANS_VARIANTE.has(base) || /-(fr|en|ar)$/.test(base)) return base;
  return `${base}-${locale}`;
}
