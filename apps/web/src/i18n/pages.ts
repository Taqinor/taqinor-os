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
import { DEFAULT_LOCALE, isLocale, LOCALES, type Locale } from './config';
import { CITIES, REALISATIONS } from '../lib/realisations';

const ALL_LOCALES: readonly Locale[] = LOCALES;

/**
 * Chemins RACINE traduits en EN + AR. Tout chemin listé ici DOIT avoir
 * src/pages/en/<path>.astro ET src/pages/ar/<path>.astro construits (pour les
 * routes dynamiques, le gabarit [city]/[slug] couvre tous les slugs). Le FR
 * (racine) existe pour tous.
 *
 * W67 lot 2 (2026-06-19) : tout le reste du site public passe en EN/AR —
 * accueil, segments (résidentiel/professionnel/MRE), équipement,
 * régularisation, loi 82-21, guides, réalisations (hub + études de cas) et
 * pages ville. Les chemins dynamiques (villes, études de cas) sont dérivés des
 * données réelles (CITIES / REALISATIONS) pour ne jamais diverger des routes
 * réellement construites par getStaticPaths.
 */
const STATIC_TRANSLATED: readonly string[] = [
  // Lot 1 (foundation)
  '/contact',
  '/nos-solutions',
  '/pompage-solaire',
  '/batteries-stockage',
  '/maintenance-monitoring',
  '/faq',
  '/garanties',
  '/financement',
  '/pourquoi-taqinor',
  '/à-propos',
  '/mentions-legales',
  '/politique-de-confidentialite',
  // Lot 2 (W67) — le reste du site public
  '/',
  '/résidentiel',
  '/professionnel',
  '/marocains-du-monde',
  '/équipement',
  '/regularization-article-33',
  '/loi-82-21',
  '/realisations',
  '/guides',
  '/guides/faut-il-des-batteries',
  '/guides/loi-82-21-expliquee',
  '/guides/onduleur-hybride-ou-reseau',
  // W294 — fermeture de l'écart EN/AR des guides (routes EN/AR livrées ci-dessous).
  '/guides/quelle-taille-de-batterie',
  '/guides/combien-de-panneaux-pour-ma-maison',
  '/guides/on-grid-off-grid-ou-hybride',
  '/guides/batterie-lithium-ou-gel',
  '/guides/electricite-pendant-les-coupures',
  '/guides/entretien-et-duree-de-vie-des-panneaux',
  '/guides/mon-toit-peut-il-supporter-des-panneaux',
  '/guides/monocristallin-ou-polycristallin',
  '/guides/orientation-inclinaison-ombrage',
  // W295 — blog EN/AR pour les deux articles "argent" (routes EN/AR livrées ci-dessous).
  '/blog',
  '/blog/prix-installation-solaire-maroc-2026',
  '/blog/rentabilite-solaire-par-ville-maroc',
  // WJ38 — parcours devis « Mon toit » localisé (routes EN/AR livrées) : les CTA
  // devis/étude basculent d'eux-mêmes vers /en/... et /ar/... via quoteJourneyHref.
  '/devis/mon-toit',
  // W293 — pilier évergreen « Prix panneaux solaires Maroc » (routes EN/AR livrées).
  '/prix-panneaux-solaires-maroc',
  // i18n-registration — 4 pages autonomes livrées avec leurs routes EN/AR
  // (W279 impact, W354 production, W355 ensoleillement, W338 parrainage) mais
  // jamais enregistrées ici : hreflang manquants jusqu'à ce correctif.
  '/impact-taqinor',
  '/production-mesuree',
  '/ensoleillement-maroc',
  '/parrainage',
  // WB15 — même écart : routes EN/AR livrées mais jamais enregistrées, donc
  // aucun hreflang émis sur les 3 URLs.
  '/methodologie-estimation',
  // W254 — pilier « recharge VE au solaire » : routes EN/AR livrées ci-dessous.
  '/recharge-voiture-electrique-solaire',
];

/**
 * W348 — lead magnet WhatsApp-first « 10 questions avant de signer » :
 * FR + AR seulement (pas de mirroir EN livré par cette tâche). Déclaré à part
 * de STATIC_TRANSLATED (qui force ALL_LOCALES) pour ne jamais annoncer un
 * hreflang EN vers une route qui n'existe pas.
 */
const PARTIAL_TRANSLATED: Record<string, readonly Locale[]> = {
  '/ressources/10-questions-avant-de-signer': ['fr', 'ar'],
};

/**
 * WJ36 — chemin RACINE du parcours devis « Mon toit » : la cible canonique de
 * TOUS les CTA devis/étude du site (en-tête, héros, CtaBand, CTA collant,
 * CTA en page). WJ38 (localisation EN/AR) est LIVRÉ : les routes
 * src/pages/{en,ar}/devis/mon-toit.astro existent et `/devis/mon-toit` est
 * déclaré dans STATIC_TRANSLATED ci-dessus, donc `quoteJourneyHref('en'|'ar')`
 * renvoie `/en/...` / `/ar/...` et tous les CTA basculent d'eux-mêmes selon la
 * locale (repli FR seulement si une locale venait à manquer — jamais de lien mort).
 */
export const QUOTE_JOURNEY_PATH = '/devis/mon-toit';

const TRANSLATED: Record<string, readonly Locale[]> = Object.fromEntries([
  ...STATIC_TRANSLATED.map((p) => [p, ALL_LOCALES] as const),
  ...CITIES.map((c) => [`/installation-solaire-${c.slug}`, ALL_LOCALES] as const),
  ...REALISATIONS.map((r) => [`/realisations/${r.slug}`, ALL_LOCALES] as const),
  ...Object.entries(PARTIAL_TRANSLATED),
]);

/** Tous les chemins racine déclarés traduits (pour les gardes de tests). */
export const TRANSLATED_PATHS: readonly string[] = Object.keys(TRANSLATED);

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

/**
 * WJ36 — href du parcours devis pour la locale courante. TOUS les CTA
 * devis/étude passent par ici (ou par `L(QUOTE_JOURNEY_PATH)`) : c'est le
 * point de bascule unique de WJ38 (voir QUOTE_JOURNEY_PATH ci-dessus).
 */
export function quoteJourneyHref(locale: Locale): string {
  return localizeNavHref(QUOTE_JOURNEY_PATH, locale);
}
