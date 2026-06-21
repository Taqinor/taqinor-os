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
