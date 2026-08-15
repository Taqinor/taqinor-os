/**
 * Logique PURE de la page /proposition/<token> — refonte « 8 chapitres ».
 *
 * Deux responsabilités, toutes deux sans DOM / sans réseau / sans dépendance,
 * donc testables sous vitest (tests/propositionPageChart.test.ts) :
 *
 *  1. LE GRAPHIQUE FUSIONNÉ « Votre production ». La page montrait trois blocs
 *     graphiques distincts empilés — barres mensuelles (« Production estimée »),
 *     courbe journalière (« Votre journée solaire ») et, pour les devis à deux
 *     options, un TROISIÈME graphe batterie (« Et avec une batterie ? »). Trois
 *     dessins concurrents du MÊME sujet = la définition même des « données non
 *     structurées » reprochées à la page. Ils fusionnent ici en UN SEUL bloc :
 *     un sélecteur de vue (année ↔ journée), les onglets de profil
 *     (Standard/Été/Ramadan) et la batterie en CALQUE de la vue journée —
 *     jamais un second graphique côte à côte. Cette machine à états décide
 *     quel calque est visible ; la page se contente d'appliquer le résultat.
 *
 *  2. L'EXTRACTION DU TOKEN depuis une route catch-all. L'URL accepte désormais
 *     `/proposition/<token>` ET `/proposition/<slug-décoratif>/<token>` (le nom
 *     du client dans le lien, pour qu'un lien partagé « se lise »). Le token est
 *     TOUJOURS le DERNIER segment ; le slug n'est jamais validé ni interprété.
 */

/** Les deux échelles de temps du graphique fusionné. */
export type ProductionView = 'annee' | 'journee';

/** Silhouettes de consommation disponibles pour la vue journée (WJ119). */
export type CurveVariantId = 'normal' | 'ete' | 'ramadan';

export const PRODUCTION_VIEWS: readonly ProductionView[] = ['annee', 'journee'];
export const CURVE_VARIANT_IDS: readonly CurveVariantId[] = ['normal', 'ete', 'ramadan'];

/** Ce que le SERVEUR a réellement rendu (aucun calque n'est inventé ici). */
export interface ProductionAvailability {
  /** Barres mensuelles production/consommation présentes. */
  monthly: boolean;
  /** Courbe journalière présente. */
  daily: boolean;
  /** Variantes de profil réellement pré-rendues (au moins `normal`). */
  variants: readonly CurveVariantId[];
  /** Calque batterie (simulateur horaire) présent. */
  battery: boolean;
}

/** État courant du bloc « Votre production ». */
export interface ProductionState {
  view: ProductionView;
  variant: CurveVariantId;
  /** Le client a coché « Avec batterie » (mémorisé même en vue année). */
  battery: boolean;
}

/** Ce qui doit être visible à l'écran — un seul dessin à la fois, toujours. */
export interface ProductionLayers {
  /** Barres mensuelles visibles. */
  monthly: boolean;
  /** Courbe journalière « nue » visible. */
  daily: boolean;
  /** Calque batterie visible (REMPLACE la courbe nue, jamais en plus). */
  battery: boolean;
  /** Variante de courbe à afficher (toujours une valeur disponible). */
  variant: CurveVariantId;
  /** Le sélecteur année/journée n'a de sens qu'avec les deux vues. */
  showViewTabs: boolean;
  /** Onglets Standard/Été/Ramadan : vue journée + ≥ 2 variantes rendues. */
  showVariantTabs: boolean;
  /** Case « Avec batterie » : vue journée + calque batterie rendu. */
  showBatteryToggle: boolean;
}

/** Normalise une disponibilité partielle (lecture défensive). */
function normalize(a: Partial<ProductionAvailability> | null | undefined): ProductionAvailability {
  const daily = !!a?.daily;
  const rawVariants = Array.isArray(a?.variants) ? a!.variants : [];
  const variants = CURVE_VARIANT_IDS.filter((v) => rawVariants.includes(v));
  return {
    monthly: !!a?.monthly,
    daily,
    // Une courbe journalière rendue implique au moins la silhouette standard.
    variants: daily && variants.length === 0 ? (['normal'] as const) : variants,
    // Le calque batterie ne peut exister que par-dessus une courbe journalière.
    battery: !!a?.battery && daily,
  };
}

/** Les vues réellement proposables, dans l'ordre d'affichage. */
export function availableViews(a: Partial<ProductionAvailability> | null | undefined): ProductionView[] {
  const av = normalize(a);
  const views: ProductionView[] = [];
  if (av.monthly) views.push('annee');
  if (av.daily) views.push('journee');
  return views;
}

/** Le bloc entier n'est rendu que s'il reste au moins un dessin honnête. */
export function hasProductionBlock(a: Partial<ProductionAvailability> | null | undefined): boolean {
  return availableViews(a).length > 0;
}

/**
 * État de départ : la vue ANNÉE d'abord quand elle existe (le chiffre annuel
 * est l'information que le client cherche en premier), sinon la journée. La
 * batterie démarre TOUJOURS décochée — le prix affiché plus bas est celui de
 * l'option retenue, pas d'un calque exploratoire.
 */
export function initialProductionState(
  a: Partial<ProductionAvailability> | null | undefined,
): ProductionState {
  const av = normalize(a);
  const views = availableViews(av);
  return {
    view: views[0] ?? 'annee',
    variant: av.variants[0] ?? 'normal',
    battery: false,
  };
}

/** Bascule de vue (ignorée si la vue demandée n'est pas rendue). */
export function setProductionView(
  state: ProductionState,
  view: ProductionView,
  a: Partial<ProductionAvailability> | null | undefined,
): ProductionState {
  if (!availableViews(a).includes(view)) return state;
  return { ...state, view };
}

/** Bascule de silhouette (ignorée si la variante n'est pas pré-rendue). */
export function setCurveVariant(
  state: ProductionState,
  variant: CurveVariantId,
  a: Partial<ProductionAvailability> | null | undefined,
): ProductionState {
  if (!normalize(a).variants.includes(variant)) return state;
  return { ...state, variant };
}

/**
 * Coche/décoche le calque batterie. Cocher depuis la vue ANNÉE ramène
 * automatiquement à la vue JOURNÉE : le calque n'a de sens que là, et un
 * client qui coche « Avec batterie » attend de VOIR quelque chose changer.
 */
export function setBatteryLayer(
  state: ProductionState,
  on: boolean,
  a: Partial<ProductionAvailability> | null | undefined,
): ProductionState {
  const av = normalize(a);
  if (!av.battery) return { ...state, battery: false };
  if (!on) return { ...state, battery: false };
  return { ...state, battery: true, view: 'journee' };
}

/**
 * Résout l'état en calques visibles. INVARIANT CENTRAL de la refonte : au plus
 * UN dessin visible à la fois (`monthly`, `daily` et `battery` ne sont jamais
 * deux à `true`). Le calque batterie REMPLACE la courbe nue.
 */
export function productionLayers(
  state: ProductionState,
  a: Partial<ProductionAvailability> | null | undefined,
): ProductionLayers {
  const av = normalize(a);
  const views = availableViews(av);
  const view: ProductionView = views.includes(state.view) ? state.view : (views[0] ?? 'annee');
  const variant: CurveVariantId = av.variants.includes(state.variant)
    ? state.variant
    : (av.variants[0] ?? 'normal');
  const batteryOn = view === 'journee' && av.battery && state.battery;
  return {
    monthly: view === 'annee' && av.monthly,
    daily: view === 'journee' && av.daily && !batteryOn,
    battery: batteryOn,
    variant,
    showViewTabs: views.length > 1,
    showVariantTabs: view === 'journee' && av.variants.length > 1,
    showBatteryToggle: view === 'journee' && av.battery,
  };
}

// ── Route catch-all : /proposition/<token> ET /proposition/<slug>/<token> ────

/**
 * Découpe le paramètre catch-all en segments non vides. Astro fournit le reste
 * du chemin comme UNE chaîne (« slug/token ») ; on accepte aussi un tableau
 * déjà découpé pour rester agnostique de la version du routeur.
 */
export function proposalPathSegments(param: string | string[] | null | undefined): string[] {
  const raw = Array.isArray(param) ? param.join('/') : (param ?? '');
  return String(raw)
    .split('/')
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/**
 * Le token est TOUJOURS le dernier segment. Tout ce qui précède est décoratif
 * (nom du client dans l'URL) et n'est ni validé ni transmis au backend : le
 * token extrait ici est le SEUL identifiant utilisé pour le fetch serveur, la
 * signature, l'OTP, la télémétrie et le PDF. Chaîne vide → la page 404.
 */
export function tokenFromSegments(param: string | string[] | null | undefined): string {
  const segments = proposalPathSegments(param);
  return segments.length > 0 ? segments[segments.length - 1] : '';
}

/** Le préfixe décoratif (vide quand l'URL ne porte que le token). */
export function decorativeSlug(param: string | string[] | null | undefined): string {
  const segments = proposalPathSegments(param);
  return segments.length > 1 ? segments.slice(0, -1).join('/') : '';
}
