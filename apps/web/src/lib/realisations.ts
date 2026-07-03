/**
 * Source unique de vérité des INSTALLATIONS RÉELLES Taqinor et des VILLES de
 * la zone de service — pour les pages de réalisations (/realisations/*) et les
 * pages ville (/installation-solaire-*).
 *
 * INTÉGRITÉ (règle du WEB_PLAN) : chaque chiffre ici est DÉJÀ publié ailleurs
 * sur le site public (accueil, résidentiel, professionnel, équipement) — rien
 * n'est inventé. Toute valeur absente du site (ex. la production mesurée de
 * Nouaceur, ou l'onduleur/batterie d'une réf. non détaillée) reste `null` et
 * n'est jamais affichée comme un nombre.
 *
 * Total installé : 17,04 + 11,36 + 5,68 + 5,68 + 3,72 = 43,48 kWc (= le chiffre
 * « 43,48 kWc installés » de l'accueil).
 */

export interface RealisationPhoto {
  name: string;
  alt: string;
  ratio: number;
  widths: number[];
  /** W181 — Point focal CSS object-position (ex. 'center top'). Défaut : 'center'. */
  objectPosition?: string;
  /** W184 — Rôle dans le diptych avant/pendant/après. */
  phase?: 'before' | 'during' | 'after';
}

export interface Realisation {
  /** Slug sous /realisations/ */
  slug: string;
  /** Référence dossier entreprise (ex. « 468 ») */
  ref: string;
  ville: string;
  /** Région administrative (pour le rattachement honnête aux pages ville). */
  region: string;
  /**
   * W342 — coordonnées GPS PUBLIQUES du centre-ville (source : coordonnées
   * géographiques municipales usuelles, PAS l'adresse exacte du chantier —
   * jamais publiée pour la vie privée du client). Suffisant pour un calcul de
   * proximité honnête (haversine, à l'échelle de la ville) ; ne sert QUE ce
   * calcul de distance, jamais affiché tel quel.
   */
  lat: number;
  lng: number;
  kwc: string;
  kwcNum: number;
  /** Mois d'installation tel que publié. */
  date: string;
  /** Production mesurée (Deye Cloud) — `null` si non publiée sur le site. */
  production: string | null;
  productionNum: number | null;
  /** Nombre + modèle de panneaux, tel que publié. */
  panneaux: string;
  /** Onduleur tel que publié — `null` si non détaillé sur le site. */
  onduleur: string | null;
  /** Stockage tel que publié — `null` si non détaillé / pas de batterie. */
  batterie: string | null;
  segment: 'residentiel' | 'professionnel';
  /** Phrase de contexte, neutre, factuelle. */
  resume: string;
  photos: RealisationPhoto[];
}

export const REALISATIONS: Realisation[] = [
  {
    slug: 'el-jadida-17-kwc',
    ref: '468',
    ville: 'El Jadida',
    region: 'Casablanca-Settat',
    lat: 33.2549,
    lng: -8.5058,
    kwc: '17,04 kWc',
    kwcNum: 17.04,
    date: 'avril 2026',
    production: '21 406 kWh/an',
    productionNum: 21406,
    panneaux: '24 × Canadian Solar 710 Wc',
    onduleur: 'Deye 15 kW (triphasé)',
    batterie: '15 kWh Dyness',
    segment: 'residentiel',
    resume:
      'La plus grande installation résidentielle livrée par Taqinor en 2026 : une toiture de villa d’El Jadida équipée en 24 panneaux, onduleur hybride triphasé et stockage lithium.',
    photos: [
      { name: 'reflet-468', alt: 'Le soleil se reflète sur la rangée de panneaux pendant la pose, El Jadida', ratio: 3 / 2, widths: [1600, 1024, 640], phase: 'during' as const },
      { name: 'equipe-trois', alt: 'Équipe Taqinor devant la longue rangée de panneaux en fin de chantier, El Jadida', ratio: 3 / 2, widths: [1600, 1024, 640], phase: 'after' as const },
      { name: 'detail-cablage', alt: 'Gros plan sur les bornes des batteries Dyness et le coffret de protections, câblage soigné, El Jadida', ratio: 4 / 3, widths: [1600, 1024, 640], phase: 'after' as const },
    ],
  },
  {
    slug: 'casablanca-11-kwc',
    ref: '400',
    ville: 'Casablanca',
    region: 'Casablanca-Settat',
    lat: 33.5731,
    lng: -7.5898,
    kwc: '11,36 kWc',
    kwcNum: 11.36,
    date: 'avril 2026',
    production: '14 271 kWh/an',
    productionNum: 14271,
    panneaux: '16 × Canadian Solar 710 Wc',
    onduleur: 'Deye 10 kW',
    batterie: '10 kWh Dyness (2 × DL5.0C)',
    segment: 'residentiel',
    resume:
      'Une villa de Casablanca face à la skyline : 16 panneaux, onduleur hybride Deye et deux batteries Dyness, avec borne de recharge — production suivie sur Deye Cloud.',
    photos: [
      { name: 'hero-skyline', alt: 'Rangée de panneaux solaires devant la skyline de Casablanca et un minaret, lumière dorée', ratio: 16 / 9, widths: [2000, 1280, 768, 480], phase: 'after' as const },
      { name: 'portrait-400', alt: "L'ingénieur devant le champ de panneaux, skyline de Casablanca", ratio: 4 / 3, widths: [1600, 1024, 640], phase: 'after' as const },
      { name: 'mur-technique-dyness', alt: "Mur technique d'une installation Taqinor à Casablanca : onduleur hybride Deye, deux batteries Dyness et borne de recharge", ratio: 4 / 3, widths: [1600, 1024, 640], phase: 'after' as const },
    ],
  },
  {
    slug: 'el-jadida-6-kwc',
    ref: '236',
    ville: 'El Jadida',
    region: 'Casablanca-Settat',
    lat: 33.2549,
    lng: -8.5058,
    kwc: '5,68 kWc',
    kwcNum: 5.68,
    date: 'mars 2026',
    production: '7 135 kWh/an',
    productionNum: 7135,
    panneaux: '8 × Canadian Solar 710 Wc',
    onduleur: 'Deye 5 kW',
    batterie: '5 kWh Dyness',
    segment: 'residentiel',
    resume:
      'Une installation résidentielle compacte sur toit plat à El Jadida : huit panneaux, onduleur hybride et une batterie 5 kWh, dimensionnés sur la facture du foyer.',
    photos: [
      { name: 'champ-villa', alt: 'Champ de huit panneaux sur toit plat de villa, El Jadida', ratio: 3 / 2, widths: [1600, 1024, 640] },
    ],
  },
  {
    slug: 'casablanca-6-kwc',
    ref: '134',
    ville: 'Casablanca',
    region: 'Casablanca-Settat',
    lat: 33.5731,
    lng: -7.5898,
    kwc: '5,68 kWc',
    kwcNum: 5.68,
    date: 'mars 2026',
    production: '7 135 kWh/an',
    productionNum: 7135,
    panneaux: '8 × Canadian Solar 710 Wc',
    onduleur: null,
    batterie: null,
    segment: 'residentiel',
    resume:
      'Une villa de Casablanca équipée de huit panneaux Canadian Solar 710 Wc — même puissance que notre installation d’El Jadida, pour un profil de consommation comparable.',
    photos: [
      { name: 'pose-134', alt: "L'équipe incline un panneau pendant la pose, Casablanca", ratio: 4 / 3, widths: [1600, 1024, 640] },
    ],
  },
  {
    slug: 'nouaceur-4-kwc',
    ref: 'NC-10/25',
    ville: 'Nouaceur',
    region: 'Casablanca-Settat',
    lat: 33.3667,
    lng: -7.5833,
    kwc: '3,72 kWc',
    kwcNum: 3.72,
    date: 'octobre 2025',
    production: null,
    productionNum: null,
    panneaux: '6 × JA Solar',
    onduleur: null,
    batterie: null,
    segment: 'residentiel',
    resume:
      'Une installation à Nouaceur, dans la périphérie de Casablanca : six panneaux JA Solar posés avec le même soin d’implantation que nos chantiers de plus grande taille.',
    photos: [
      { name: 'equipe-gilet-taqinor', alt: "Installateur en gilet Taqinor posant les rails d'une structure, Nouaceur", ratio: 1, widths: [1600, 1024, 640], phase: 'during' as const },
      { name: 'mesure-rails', alt: 'Traçage et mesure au mètre des rails de fixation sur toiture, Nouaceur', ratio: 4 / 3, widths: [1600, 1024, 640], phase: 'before' as const },
      { name: 'entretien-jet', alt: "Nettoyage au jet d'eau du champ de panneaux, Nouaceur", ratio: 1, widths: [1600, 1024, 640], phase: 'after' as const },
    ],
  },
];

export const realisationBySlug = (slug: string): Realisation | undefined =>
  REALISATIONS.find((r) => r.slug === slug);

export const realisationByRef = (ref: string): Realisation | undefined =>
  REALISATIONS.find((r) => r.ref === ref);

/**
 * W342 — « L'installation la plus proche de chez vous » : distance haversine
 * en km entre deux points GPS. Calcul client-side pur (aucun appel réseau,
 * aucune dépendance) — la même formule que tout manuel de géodésie standard.
 */
export function haversineKm(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const R = 6371; // rayon terrestre moyen, km
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * sinLng * sinLng;
  return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

export interface NearestRealisation {
  realisation: Realisation;
  distanceKm: number;
}

/**
 * W342 — l'installation réelle la plus proche d'un point GPS donné (le repère
 * posé par le visiteur sur son toit, ou le point du premier zone de toiture
 * côté proposition). Honnêtement scopé aux villes réelles de `REALISATIONS` —
 * jamais une ville inventée. `maxKm` (défaut 80 km, ≈ le rayon Grand
 * Casablanca–El Jadida–Nouaceur) évite d'annoncer « la plus proche » pour un
 * visiteur à Tanger ou Agadir, où le chantier le plus proche resterait à
 * plusieurs centaines de km — pas une vraie preuve de proximité.
 */
export function nearestRealisation(
  lat: number,
  lng: number,
  maxKm = 80,
): NearestRealisation | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  let best: NearestRealisation | null = null;
  for (const r of REALISATIONS) {
    const distanceKm = haversineKm(lat, lng, r.lat, r.lng);
    if (!best || distanceKm < best.distanceKm) best = { realisation: r, distanceKm };
  }
  if (!best || best.distanceKm > maxKm) return null;
  return best;
}

/**
 * W342 — repli par nom de ville (pas de GPS disponible, ex. proposition sans
 * `roof_layout`) : recherche insensible à la casse/accents dans le texte
 * d'adresse fourni. Retourne la PREMIÈRE réalisation dont la ville apparaît
 * dans le texte — jamais une correspondance floue/devinée.
 */
export function nearestRealisationByCityText(addressText: string): Realisation | null {
  const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const hay = norm(addressText || '');
  if (!hay.trim()) return null;
  for (const r of REALISATIONS) {
    if (hay.includes(norm(r.ville))) return r;
  }
  return null;
}

/**
 * W283 — Standard de légende par étude de cas : « [Ville] — X kWc — installé
 * en [mois année] — Z kWh mesurés ». Construit UNIQUEMENT à partir de champs
 * réels de `Realisation` :
 *   - ville + kwc : toujours présents, toujours affichés.
 *   - date : le seul repère temporel réellement publié est le mois/année
 *     d'installation (`r.date`, ex. « avril 2026 ») — aucune durée de
 *     chantier en jours n'est mesurée nulle part sur le site, donc ce
 *     segment lit « installé en <mois année> » plutôt qu'un décompte de
 *     jours inventé.
 *   - production : uniquement quand `r.production` est renseignée (non
 *     `null`) ; sinon ce segment est omis intégralement plutôt que réduit à
 *     un tiret ou un zéro.
 * Locale-aware (FR par défaut) : seuls les connecteurs sont traduits, aucun
 * chiffre n'est reformulé (mêmes chiffres latins dans les trois locales).
 */
const CAPTION_STR: Record<'fr' | 'en' | 'ar', { installed: string; measured: string }> = {
  fr: { installed: 'installé en', measured: 'kWh mesurés' },
  en: { installed: 'installed in', measured: 'kWh measured' },
  ar: { installed: 'رُكِّبت في', measured: 'kWh مقيسة' },
};

export const standardCaption = (r: Realisation, locale: 'fr' | 'en' | 'ar' = 'fr'): string => {
  const s = CAPTION_STR[locale] ?? CAPTION_STR.fr;
  const parts = [r.ville, r.kwc, `${s.installed} ${r.date}`];
  if (r.production) parts.push(`${r.production.replace(/\/an$/, '')} ${s.measured}`);
  return parts.join(' — ');
};

export interface City {
  slug: string;
  /** Nom de la ville. */
  name: string;
  /** Préposition « à » / « à » — forme « à <ville> ». */
  intro: string;
  /**
   * Heures d'ensoleillement annuelles — DONNÉE MÉTÉO PUBLIQUE indicative
   * (normales climatologiques). Voir CITY_PAGES_NOTES.md pour la méthode.
   * Volontairement arrondies, jamais présentées comme une mesure Taqinor.
   */
  sunshineHours: string;
  /** Réfs de réalisations à mettre en avant (vide = aucune dans/près de la ville). */
  featuredRefs: string[];
  /**
   * Vrai si Taqinor a une installation DANS ou PRÈS de la ville (sinon la page
   * reste honnête : zone de service couverte, chantiers les plus proches cités).
   */
  hasLocalInstall: boolean;
}

/**
 * Les 5 villes = exactement la zone de service du NAP (Casablanca, Rabat,
 * Marrakech, Tanger, Agadir). Les installations réelles connues sont toutes en
 * région Casablanca-Settat (Casablanca, El Jadida, Nouaceur) : seule la page
 * Casablanca met donc en avant des chantiers réels ; les autres restent
 * factuelles (zone couverte + chantiers les plus proches), sans rien inventer.
 */
export const CITIES: City[] = [
  {
    slug: 'casablanca',
    name: 'Casablanca',
    intro: 'à Casablanca',
    sunshineHours: '≈ 2 950',
    featuredRefs: ['400', '134', 'NC-10/25', '468', '236'],
    hasLocalInstall: true,
  },
  {
    slug: 'rabat',
    name: 'Rabat',
    intro: 'à Rabat',
    sunshineHours: '≈ 2 900',
    featuredRefs: [],
    hasLocalInstall: false,
  },
  {
    slug: 'marrakech',
    name: 'Marrakech',
    intro: 'à Marrakech',
    sunshineHours: '≈ 3 000',
    featuredRefs: [],
    hasLocalInstall: false,
  },
  {
    slug: 'tanger',
    name: 'Tanger',
    intro: 'à Tanger',
    sunshineHours: '≈ 2 800',
    featuredRefs: [],
    hasLocalInstall: false,
  },
  {
    slug: 'agadir',
    name: 'Agadir',
    intro: 'à Agadir',
    sunshineHours: '≈ 3 400',
    featuredRefs: [],
    hasLocalInstall: false,
  },
];

export const cityBySlug = (slug: string): City | undefined =>
  CITIES.find((c) => c.slug === slug);
