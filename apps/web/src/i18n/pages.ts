/**
 * Registre de DISPONIBILITÉ des traductions par page (W67) — source unique de
 * vérité pour : (a) quelles locales le sélecteur de langue propose sur une page,
 * (b) quels `hreflang` la page émet, (c) vers quelle URL le chrome (en-tête /
 * pied de page) pointe un lien selon la locale courante.
 *
 * Clé = chemin RACINE sans préfixe de locale (ex. '/contact', '/' pour
 * l'accueil). Valeur = locales RÉELLEMENT traduites pour ce chemin. Le FR est
 * TOUJOURS présent (rendu inchangé à la racine) ; on ajoute 'en'/'ar' au fur et
 * à mesure que les routes /en/<path> et /ar/<path> existent vraiment.
 *
 * INVARIANT anti-lien-mort : ne jamais déclarer ici une locale dont la route
 * n'est pas construite — sinon le chrome produirait un lien vers une page
 * inexistante. Quand une page n'a que le FR, elle n'apparaît PAS dans ce
 * registre (ou seulement avec ['fr']) → le sélecteur ne s'affiche pas et son
 * rendu FR reste strictement identique.
 */
import { DEFAULT_LOCALE, isLocale, type Locale } from './config';

/**
 * Chemins traduits en EN + AR. Tout chemin listé ici DOIT avoir
 * src/pages/en/<path>.astro ET src/pages/ar/<path>.astro construits.
 * Le FR (racine) existe pour tous.
 */
const TRANSLATED: Record<string, readonly Locale[]> = {
  '/contact': ['fr', 'en', 'ar'],
  '/nos-solutions': ['fr', 'en', 'ar'],
  '/faq': ['fr', 'en', 'ar'],
  '/garanties': ['fr', 'en', 'ar'],
  '/mentions-legales': ['fr', 'en', 'ar'],
  '/politique-de-confidentialite': ['fr', 'en', 'ar'],
};

/** Normalise un chemin racine : retire le slash final (sauf la racine). */
function normalizeRoot(rootPath: string): string {
  if (!rootPath || rootPath === '/') return '/';
  const noTrail = rootPath.replace(/\/+$/, '');
  return noTrail === '' ? '/' : noTrail;
}

/**
 * Locales disponibles pour un chemin RACINE. Toujours au moins [fr]. Une page
 * non traduite renvoie ['fr'] → pas de sélecteur, rendu FR inchangé.
 */
export function localesForPath(rootPath: string): Locale[] {
  const key = normalizeRoot(rootPath);
  const list = TRANSLATED[key];
  if (list && list.length) return [...list];
  return [DEFAULT_LOCALE];
}

/** Une page a-t-elle une traduction dans `locale` ? (le FR est toujours vrai) */
export function hasLocale(rootPath: string, locale: Locale): boolean {
  return localesForPath(rootPath).includes(locale);
}

/**
 * Localise un lien de NAVIGATION pour la locale courante SANS jamais créer de
 * lien mort : si la cible existe dans `locale`, on préfixe (`/en/...`,
 * `/ar/...`) ; sinon on retombe sur le FR (racine), qui existe toujours.
 * `rootPath` doit être un chemin racine (sans préfixe de locale).
 */
export function localizeNavHref(rootPath: string, locale: Locale): string {
  const clean = rootPath.startsWith('/') ? rootPath : '/' + rootPath;
  if (locale === DEFAULT_LOCALE || !isLocale(locale)) return clean;
  if (!hasLocale(clean, locale)) return clean; // repli FR — jamais de lien mort
  return `/${locale}${clean === '/' ? '' : clean}`;
}
