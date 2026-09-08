/**
 * Source unique de vérité des INSTALLATIONS RÉELLES Taqinor et des VILLES de
 * la zone de service — pour les pages de réalisations (/realisations/*) et les
 * pages ville (/installation-solaire-*).
 *
 * INTÉGRITÉ (règle du WEB_PLAN) : chaque chiffre ici est un fait réel — rien
 * n'est inventé. Toute valeur non confirmée reste `null` et n'est jamais
 * affichée comme un nombre.
 *
 * Total installé : 17,04 + 11,36 + 5,68 + 5,68 + 3,72 + 11,44 (Bouskoura,
 * fondateur 08/09/2026) = 54,92 kWc — le total n'est plus affiché sur l'accueil
 * (WC5), les tests d'intégrité le vérifient. Ce sont des CAPACITÉS posées
 * (kWc), conservées telles quelles.
 *
 * WB1 — CORRECTION (2026-07-04, données Deye Cloud réelles du fondateur) :
 * les quatre `productionNum` ANNUELS d'origine (21406, 14271, 7135, 7135)
 * étaient FABRIQUÉS — ils partageaient exactement le même facteur kWh/kWc
 * (≈1256,2), impossible pour de vrais relevés sur des sites différents, et ils
 * ne correspondent à AUCUN relevé Deye. La flotte Deye RÉELLE (vue « TAQINOR
 * Solutions », tirée le 2026-07-04) compte 4 centrales récemment mises en
 * service (semaines→mois), soit 32,04 kWp, avec seulement des cumuls de
 * production « depuis la mise en service » (aucun chiffre ANNUEL légitime
 * n'existe encore) — voir MEASURED_FLEET ci-dessous. En conséquence : TOUTE
 * production annuelle est retirée (`production`/`productionNum` = `null`
 * partout → jamais affichée). Le seul chiffre de production publié sur le site
 * est désormais le CUMUL MESURÉ de la flotte, dans le héros de l'accueil
 * (source : MEASURED_FLEET). Ne JAMAIS réintroduire un chiffre annuel par
 * installation sans un vrai relevé Deye distinct par site.
 *
 * TODO FONDATEUR (pour restaurer des chiffres mesurés PAR installation) :
 *   1. Relevés Deye Cloud RÉELS et distincts par chantier + mois de mise en
 *      service exact (aujourd'hui seuls des cumuls « depuis la m.e.s. »).
 *   2. Ajouter la centrale d'Aïn Diab (Britel, 10 kWc, plus gros producteur —
 *      2,62 MWh cumulés) au roster dès qu'une PHOTO de chantier est disponible.
 *   3. Fournir les figures des 2 installations suivies sur Huawei FusionSolar
 *      (non tirées ici) pour compléter la flotte.
 *   4. Confirmer que l'installation d'El Jadida 17,04 kWc (réf. 468) est bien
 *      réelle et posée (elle n'est pas sur Deye) — sinon la retirer du total
 *      « 43,48 kWc installés ».
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
  /**
   * (2026-09) Optionnels : certains chantiers filmés/photographiés n'ont pas
   * encore de puissance installée CONFIRMÉE publiable (un chantier tourné
   * avant tout relevé) — absents plutôt que `0`/deviné, jamais affichés
   * comme un chiffre dans ce cas (chaque appelant garde `r.kwc &&`/`r.kwcNum &&`).
   */
  kwc?: string;
  kwcNum?: number;
  /** Mois d'année tel que publié — voir `dateType` pour sa signification exacte. */
  date: string;
  /**
   * (2026-09) Ce que `date` désigne : `'installed'` (mois de MISE EN SERVICE,
   * défaut — comportement historique inchangé pour toute entrée qui omet ce
   * champ) ou `'filmed'` (mois de TOURNAGE photo/vidéo, quand la mise en
   * service réelle n'est pas connue). `standardCaption` choisit
   * le verbe juste selon cette valeur ; ne jamais afficher « installé en » pour
   * une date qui n'est que celle du tournage.
   */
  dateType?: 'installed' | 'filmed';
  /** Production mesurée (Deye Cloud) — `null` si non publiée sur le site. */
  production: string | null;
  productionNum: number | null;
  /**
   * WB1 (2026-07-04) — `true` quand `production`/`productionNum` sont DÉRIVÉS
   * d'un rendement kWh/kWc mesuré (et non d'un relevé Deye Cloud distinct pour
   * CE chantier). Toute page consommatrice doit alors dire « estimée à partir
   * du rendement mesuré », jamais « mesurée »/« suivie sur Deye Cloud ». `false`
   * ou absent = relevé publié tel quel. Ne jamais définir sur `true` sans
   * ajouter la nuance correspondante partout où ce chantier est cité.
   */
  productionEstimated?: boolean;
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
  /**
   * (fondateur 2026-08-17) — libellé de l'entrée `MEASURED_FLEET` qui
   * correspond à CE chantier, quand l'appariement est DOCUMENTÉ dans ce
   * fichier. JAMAIS d'appariement deviné par ville + puissance : deux
   * chantiers d'une même ville peuvent partager la même puissance, et
   * plusieurs réalisations disent explicitement « pas de relevé distinct ».
   * Seule la réf. 400 est appariée à ce jour : son commentaire de production
   * cite le cumul réel « 1,13 MWh », identique à celui de
   * « Bd Fès (Casablanca) » (11,36 kWc de part et d'autre).
   * Absent = aucune production mesurée publiable pour ce chantier → la
   * mention est OMISE, jamais remplacée par une estimation.
   */
  measuredLabel?: string;
  /**
   * (2026-09) Vidéo de chantier RÉELLE et propre à cette installation — jamais
   * partagée entre chantiers. `src` : chemin complet du MP4 auto-hébergé.
   * `poster` : chemin RACINE sans extension (même convention que LiteVideo —
   * .avif/.webp dérivés). Absent = aucune vidéo pour ce chantier (pas de
   * lecteur rendu), comme pour toutes les entrées historiques.
   */
  video?: { src: string; poster: string; alt: string };
  /**
   * (2026-09) Lien vers le suivi de production en temps réel de CE chantier
   * (accès client), quand il existe et peut être partagé publiquement. Vide
   * tant que non fourni — jamais un lien générique/deviné.
   */
  monitoringUrl?: string;
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
    production: null, // WB1 (2026-07-04) : annuel fabriqué retiré — pas sur Deye.
    productionNum: null,
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
    production: null, // WB1 (2026-07-04) : annuel fabriqué retiré (cumul Deye réel : 1,13 MWh).
    productionNum: null,
    panneaux: '16 × Canadian Solar 710 Wc',
    onduleur: 'Deye 10 kW',
    batterie: '10 kWh Dyness (2 × DL5.0C)',
    segment: 'residentiel',
    // (fondateur 2026-08-17) seul appariement DOCUMENTÉ avec la flotte mesurée :
    // le commentaire `production` ci-dessus cite le cumul réel 1,13 MWh, celui
    // de « Bd Fès (Casablanca) » — même puissance (11,36 kWc) des deux côtés.
    measuredLabel: 'Bd Fès (Casablanca)',
    resume:
      'Une villa de Casablanca face à la skyline : 16 panneaux, onduleur hybride Deye et deux batteries Dyness, avec borne de recharge — production suivie en temps réel.',
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
    production: null, // WB1 (2026-07-04) : annuel fabriqué retiré — pas de relevé Deye distinct.
    productionNum: null,
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
    production: null, // WB1 (2026-07-04) : annuel fabriqué retiré — pas de relevé Deye distinct.
    productionNum: null,
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
    // (2026-09) Enrichissement médias — faits FONDATEUR (Reda, 08/09/2026) :
    // Nouaceur est l'UNIQUE installation de Nouaceur, 3,72 kWc / 6 × JA Solar /
    // octobre 2025 — valeurs déjà publiées CONFIRMÉES, inchangées. Chantier
    // photographié/filmé par le fondateur les 18-20/10/2025 ; 6 nouvelles
    // photos + 1 vidéo ajoutées (les 3 photos déjà publiées restent, à
    // l'identique, en fin de tableau). Production toujours non relevée → `null`.
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
      { name: 'nouaceur-toit', alt: 'Rangée de six panneaux solaires au coucher du soleil, palmiers en arrière-plan, Nouaceur', ratio: 16 / 9, widths: [2000, 1280, 768, 480] },
      { name: 'nouaceur-structure-lestage', alt: 'Deux installateurs Taqinor posent les blocs de lestage et les rails avant la pose des panneaux, Nouaceur', ratio: 4 / 3, widths: [1600, 1024, 640] },
      { name: 'nouaceur-equipe-rails', alt: "Gilet Taqinor et rails de fixation en cours d'alignement sur le toit, Nouaceur", ratio: 1, widths: [1600, 1024, 640] },
      { name: 'nouaceur-mesure-equipe', alt: "Trois installateurs Taqinor mesurent l'implantation des rails sur le toit, Nouaceur", ratio: 3 / 2, widths: [1600, 1024, 640] },
      { name: 'nouaceur-onduleur-must', alt: 'Onduleur solaire MUST installé sur un mur intérieur, à côté du coffret électrique, Nouaceur', ratio: 4 / 3, widths: [1600, 1024, 640] },
      { name: 'nouaceur-panneaux-couchant', alt: "Gros plan sur l'alignement des six panneaux solaires à la tombée du jour, Nouaceur", ratio: 3 / 2, widths: [1600, 1024, 640] },
      { name: 'equipe-gilet-taqinor', alt: "Installateur en gilet Taqinor posant les rails d'une structure, Nouaceur", ratio: 1, widths: [1600, 1024, 640], phase: 'during' as const },
      { name: 'mesure-rails', alt: 'Traçage et mesure au mètre des rails de fixation sur toiture, Nouaceur', ratio: 4 / 3, widths: [1600, 1024, 640], phase: 'before' as const },
      { name: 'entretien-jet', alt: "Nettoyage au jet d'eau du champ de panneaux, Nouaceur", ratio: 1, widths: [1600, 1024, 640], phase: 'after' as const },
    ],
    video: {
      src: '/videos/nouaceur-chantier.mp4',
      poster: '/videos/nouaceur-chantier-poster',
      alt: 'Équipe Taqinor au travail sur le chantier solaire de Nouaceur',
    },
  },
  {
    // (2026-09) Villa de Bouskoura — faits FONDATEUR (Reda, 08/09/2026) :
    // 16 panneaux de 715 Wc = 11,44 kWc, 2 batteries DYNESS 5 kWh (modules
    // DL5.0C visibles à l'image), onduleur hybride Deye, mise en service en
    // juillet 2026 ; chantier filmé le 09/07/2026 (photos + montage du
    // vidéaste). Production non relevée → `null`, jamais un chiffre deviné.
    // Coordonnées = centre-ville GeoNames (gazetier `villes_maroc`).
    slug: 'bouskoura-villa-2026',
    ref: 'BSK-07/26',
    ville: 'Bouskoura',
    region: 'Casablanca-Settat',
    lat: 33.4498,
    lng: -7.6524,
    kwc: '11,44 kWc',
    kwcNum: 11.44,
    date: 'juillet 2026',
    dateType: 'installed',
    production: null,
    productionNum: null,
    panneaux: '16 × 715 Wc',
    onduleur: 'Deye',
    batterie: '2 × DYNESS 5 kWh (DL5.0C)',
    segment: 'residentiel',
    resume:
      'Une villa à Bouskoura équipée de seize panneaux de 715 Wc (11,44 kWc), onduleur hybride Deye et deux batteries DYNESS de 5 kWh — mise en service en juillet 2026.',
    photos: [
      { name: 'bouskoura-toit', alt: 'Toiture-terrasse d’une villa entièrement couverte de panneaux solaires, Bouskoura', ratio: 16 / 9, widths: [2000, 1280, 768, 480] },
      { name: 'bouskoura-toit-large', alt: 'Vue aérienne large du toit solaire de la villa et du quartier, Bouskoura', ratio: 16 / 9, widths: [1600, 1024, 640] },
      { name: 'bouskoura-panneaux', alt: 'Gros plan sur l’alignement des panneaux solaires et leur structure de fixation, Bouskoura', ratio: 3 / 2, widths: [1600, 1024, 640] },
      { name: 'bouskoura-gilet-taqinor', alt: 'Gilet de travail Taqinor porté par un installateur sur le chantier de Bouskoura', ratio: 1, widths: [1600, 1024, 640] },
      { name: 'bouskoura-cablage-onduleur', alt: 'Câblage à l’intérieur du compartiment de raccordement de l’onduleur, chantier de Bouskoura', ratio: 4 / 3, widths: [1600, 1024, 640] },
      { name: 'bouskoura-coffret-technicien', alt: 'Un technicien Taqinor raccorde un coffret électrique, chantier de Bouskoura', ratio: 4 / 3, widths: [1600, 1024, 640] },
      { name: 'bouskoura-equipe-mur-technique', alt: 'Deux installateurs Taqinor devant l’onduleur et le tableau électrique, chantier de Bouskoura', ratio: 3 / 2, widths: [1600, 1024, 640] },
      { name: 'bouskoura-batterie-dyness', alt: 'Batterie de stockage DYNESS (module DL5.0C) installée sur le chantier de Bouskoura', ratio: 4 / 3, widths: [1600, 1024, 640] },
    ],
    video: {
      src: '/videos/bouskoura-chantier.mp4',
      poster: '/videos/bouskoura-chantier-poster',
      alt: 'Équipe Taqinor au travail sur le chantier solaire de Bouskoura',
    },
  },
];

/**
 * FLOTTE MESURÉE — cumuls de production « depuis la mise en service » réellement
 * relevés sur les applications de supervision. Ces cumuls sont les SEULS
 * chiffres de production réels. Les centrales étant récentes, aucun chiffre
 * ANNUEL légitime n'existe encore : NE JAMAIS transformer un cumul en
 * « production annuelle ». Source unique du chiffre de production affiché sur
 * l'accueil (héros) et les pages impact/production.
 *
 * IMPORTANT (WC10, 2026-07-05) : le champ `source` (deye/huawei) est INTERNE —
 * ne jamais afficher les marques « Deye Cloud » / « Huawei FusionSolar » ni le
 * mot « cloud » au client (le fondateur supervise sur les deux apps ; on parle
 * de « suivi de production en temps réel », pas d'une marque d'app).
 *
 * 2026-07-05 (Reda) : ajout des 2 installations suivies sur Huawei
 * (Omar Taouss 3,41 MWh ; Villa Haj Elofir 34,22 MWh). Total flotte ≈ 44,19 MWh.
 */
export interface MeasuredPlant {
  /** Libellé interne du site (jamais affiché tel quel au client). */
  label: string;
  /** Puissance installée (kWc) si connue, sinon null. */
  kwc: number | null;
  /** Cumul mesuré depuis la mise en service, en MWh. */
  lifetimeMWh: number;
  /** Application de supervision — INTERNE, jamais affichée (WC10). */
  source: 'deye' | 'huawei';
  /**
   * (fondateur 2026-08-17) DATE DU RELEVÉ (ISO), telle que déjà documentée
   * dans ce fichier — jamais une date devinée : la vue de la flotte suivie sur
   * la première application a été « tirée le 2026-07-04 » (en-tête WB1), les
   * deux centrales de la seconde ont été relevées et ajoutées le 2026-07-05
   * (note WC10 ci-dessus). Un cumul saisi sans date documentée laisse ce champ
   * absent : l'affichage omet alors la mention « relevé au … ».
   */
  readAt?: string;
}
export const MEASURED_FLEET: MeasuredPlant[] = [
  { label: 'Aïn Diab (Casablanca)', kwc: 10, lifetimeMWh: 2.62, source: 'deye', readAt: '2026-07-04' },
  { label: 'Casablanca (Rassam)', kwc: 5.68, lifetimeMWh: 1.41, source: 'deye', readAt: '2026-07-04' },
  { label: 'El Jadida (Benaissa)', kwc: 5, lifetimeMWh: 1.4, source: 'deye', readAt: '2026-07-04' },
  { label: 'Bd Fès (Casablanca)', kwc: 11.36, lifetimeMWh: 1.13, source: 'deye', readAt: '2026-07-04' },
  { label: 'Omar Taouss', kwc: null, lifetimeMWh: 3.41, source: 'huawei', readAt: '2026-07-05' },
  { label: 'Villa Haj Elofir', kwc: null, lifetimeMWh: 34.22, source: 'huawei', readAt: '2026-07-05' },
];
/** Cumul mesuré de la flotte = 2,62+1,41+1,40+1,13+3,41+34,22 ≈ 44,19 MWh. */
export const MEASURED_FLEET_LIFETIME_MWH = MEASURED_FLEET.reduce((s, p) => s + p.lifetimeMWh, 0);
/** Nombre d'installations réellement supervisées (production mesurée). */
export const MEASURED_FLEET_COUNT = MEASURED_FLEET.length;
/** Format FR (virgule décimale) pour l'affichage — « 44,19 ». */
export const MEASURED_FLEET_LIFETIME_MWH_FR = MEASURED_FLEET_LIFETIME_MWH.toFixed(2).replace('.', ',');

/**
 * (fondateur 2026-08-17) « 2026-07-05 » → « 05/07/2026 ». Chaîne vide si la
 * valeur n'est pas une date ISO complète — l'appelant OMET alors la mention
 * plutôt que d'afficher une date partielle ou inventée.
 */
export function formatDateFr(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso ?? ''));
  return m ? `${m[3]}/${m[2]}/${m[1]}` : '';
}

/**
 * Date du DERNIER relevé composant `MEASURED_FLEET_LIFETIME_MWH` (ISO) — donc
 * la date à laquelle ce cumul est vrai. `null` si aucune centrale ne porte de
 * date documentée : la mention « relevé au … » est alors omise partout.
 */
export const MEASURED_FLEET_READ_AT: string | null = (() => {
  const dates = MEASURED_FLEET.map((p) => p.readAt).filter((d): d is string => !!d).sort();
  return dates.length ? dates[dates.length - 1] : null;
})();

/** Même date au format FR (« 05/07/2026 ») — chaîne vide si non documentée. */
export const MEASURED_FLEET_READ_AT_FR = formatDateFr(MEASURED_FLEET_READ_AT);

/**
 * (fondateur 2026-08-17) centrale MESURÉE correspondant à une réalisation, ou
 * `null`. Aucun appariement heuristique (ville/puissance) : seule une
 * réalisation qui DÉCLARE son `measuredLabel` est appariée, et seulement si
 * l'entrée existe toujours dans la flotte.
 */
export function measuredPlantFor(r: Realisation | null | undefined): MeasuredPlant | null {
  const label = r?.measuredLabel;
  if (!label) return null;
  return MEASURED_FLEET.find((p) => p.label === label) ?? null;
}

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
 *
 * (2026-09) `pool` optionnel (défaut : `REALISATIONS`, comportement inchangé
 * pour tout appelant existant) — permet à un appelant qui AFFICHE le `kwc` du
 * résultat (ex. « X — 11,36 kWc — à environ Y km ») de restreindre la
 * recherche aux chantiers qui en publient un (`REALISATIONS.filter(r =>
 * r.kwc)`), pour retomber naturellement sur le suivant-plus-proche plutôt que
 * d'afficher un chantier réel mais sans chiffre publiable (ex. Bouskoura).
 */
export function nearestRealisation(
  lat: number,
  lng: number,
  maxKm = 80,
  pool: Realisation[] = REALISATIONS,
): NearestRealisation | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  let best: NearestRealisation | null = null;
  for (const r of pool) {
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
export function nearestRealisationByCityText(addressText: string, pool: Realisation[] = REALISATIONS): Realisation | null {
  const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const hay = norm(addressText || '');
  if (!hay.trim()) return null;
  for (const r of pool) {
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
 *     un tiret ou un zéro. WB1 (2026-07-04) : quand `r.productionEstimated`
 *     est vrai, le segment lit « estimés » au lieu de « mesurés » (voir la
 *     note d'intégrité en tête de fichier).
 * Locale-aware (FR par défaut) : seuls les connecteurs sont traduits, aucun
 * chiffre n'est reformulé (mêmes chiffres latins dans les trois locales).
 */
const CAPTION_STR: Record<'fr' | 'en' | 'ar', { installed: string; filmed: string; measured: string; estimated: string }> = {
  fr: { installed: 'installé en', filmed: 'filmé en', measured: 'kWh mesurés', estimated: 'kWh estimés' },
  en: { installed: 'installed in', filmed: 'filmed in', measured: 'kWh measured', estimated: 'kWh estimated' },
  ar: { installed: 'رُكِّبت في', filmed: 'صُوِّرت في', measured: 'kWh مقيسة', estimated: 'kWh مقدَّرة' },
};

/**
 * (2026-09) `kwc` est désormais optionnel (chantiers filmés avant tout relevé
 * de puissance, ex. Bouskoura) — ce segment est alors OMIS du tiret plutôt que
 * d'afficher `undefined`. `dateType: 'filmed'` bascule le verbe sur « filmé
 * en » pour ne jamais laisser croire à une mise en service confirmée.
 */
export const standardCaption = (r: Realisation, locale: 'fr' | 'en' | 'ar' = 'fr'): string => {
  const s = CAPTION_STR[locale] ?? CAPTION_STR.fr;
  const dateVerb = r.dateType === 'filmed' ? s.filmed : s.installed;
  const parts = [r.ville];
  if (r.kwc) parts.push(r.kwc);
  parts.push(`${dateVerb} ${r.date}`);
  if (r.production) {
    const unitLabel = r.productionEstimated ? s.estimated : s.measured;
    parts.push(`${r.production.replace(/\/an$/, '')} ${unitLabel}`);
  }
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
    featuredRefs: ['400', '134', 'NC-10/25', '468', '236', 'BSK-07/26'],
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
