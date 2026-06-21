/**
 * Source unique de vérité des FICHES TECHNIQUES publiées sur taqinor.ma.
 *
 * INTÉGRITÉ (même règle que `brands.ts`) : marques, familles de modèles et
 * faits techniques sont VÉRIFIÉS — repris de la page Équipement déjà validée
 * par le fondateur et/ou de la fiche constructeur officielle liée dans
 * `datasheet`. Aucune spec n'est inventée ici : les chiffres détaillés vivent
 * dans le PDF officiel (lien `datasheet`), pas transcrits à la main.
 *
 * `slug` est l'identifiant d'URL `/produits/<slug>` ET la cible des liens du
 * devis premium (le moteur Django mappe chaque ligne d'équipement vers ce même
 * slug — voir `apps/ventes/quote_engine/residential/theme.py:fiche_slug`).
 * `pdf` pointe vers une copie auto-hébergée sous `/public/fiches/<slug>.pdf`
 * quand elle existe ; sinon la page renvoie vers `datasheet` (source officielle).
 */

export type FicheCategorie =
  | 'Panneaux photovoltaïques'
  | 'Onduleurs réseau'
  | 'Onduleurs hybrides'
  | 'Batteries'
  | 'Supervision & comptage';

export interface Fiche {
  slug: string;
  nom: string;
  marque: string;
  modele: string;
  categorie: FicheCategorie;
  /** Accroche courte (1 phrase) — vérifiée, sans chiffre inventé. */
  resume: string;
  /** Faits techniques vérifiés (page Équipement validée + fiche officielle). */
  faits: string[];
  /** Garantie commerciale Taqinor pour cette famille. */
  garantie: string;
  /** Fiche constructeur officielle (source faisant foi pour le détail). */
  datasheet: string;
  /** Copie auto-hébergée `/fiches/<slug>.pdf` — null tant qu'elle n'est pas déposée. */
  pdf: string | null;
}

export const FICHES: Fiche[] = [
  {
    slug: 'canadian-solar-710',
    nom: 'Panneau Canadian Solar 710 Wc',
    marque: 'Canadian Solar',
    modele: 'TOPBiHiKu7 (CS7N-…TB-AG)',
    categorie: 'Panneaux photovoltaïques',
    resume:
      "Module bifacial N-type TOPCon : il capte aussi la lumière réfléchie par la toiture, du rendement gagné sans surface en plus.",
    faits: [
      'Cellule N-type TOPCon, technologie bifaciale',
      'Plage de puissance 705 – 720 Wc',
      'Conforme IEC 61215 et IEC 61730',
    ],
    garantie: 'Garantie produit 12 ans · performance 25 ans',
    datasheet:
      'https://static.csisolar.com/wp-content/uploads/2022/12/12090125/CS-Datasheet-TOPBiHiKu7-TOPCon_CS7N-TB-AG_v1.62C3_EN.pdf',
    pdf: '/fiches/canadian-solar-710.pdf',
  },
  {
    slug: 'jinko-710',
    nom: 'Panneau Jinko 710 Wc',
    marque: 'Jinko',
    modele: 'Tiger Neo (N-type)',
    categorie: 'Panneaux photovoltaïques',
    resume:
      "La cellule N-type Tiger Neo va chercher le rendement plutôt que la surface — utile quand la toiture est comptée.",
    faits: [
      'Cellule N-type monocristalline haut rendement',
      'Plage de puissance ≈ 700 – 720 Wc',
      'Conforme IEC 61215 et IEC 61730',
    ],
    garantie: 'Garantie produit 12 ans · performance 25 ans',
    // Datasheet officielle Tiger Neo 66HL5-BDV 710-735 Wc (CDN Jinko global) —
    // self-hostée ci-dessous ; la page produit /en/site/tigerneo n'est pas un PDF.
    datasheet:
      'https://jinkosolarcdn.shwebspace.com/uploads/JKM710-735N-66HL5-BDV-Z4-EN.pdf',
    pdf: '/fiches/jinko-710.pdf',
  },
  {
    slug: 'onduleur-huawei-reseau',
    nom: 'Onduleur réseau Huawei SUN2000',
    marque: 'Huawei',
    modele: 'SUN2000 (série string)',
    categorie: 'Onduleurs réseau',
    resume:
      "Onduleur string pur quand l'étude ne retient pas de batterie : il optimise chaîne par chaîne, un panneau à l'ombre ne tire plus toute la rangée.",
    faits: [
      'Optimisation par chaîne (MPPT multiples)',
      'Rendement européen élevé',
      'Du résidentiel à la toiture tertiaire',
    ],
    garantie: 'Garantie 10 ans',
    datasheet:
      'https://solar.huawei.com/-/media/Solar/attachment/pdf/apac/datasheet/SUN2000-5-10KTL-M0-M1.pdf',
    pdf: '/fiches/onduleur-huawei-reseau.pdf',
  },
  {
    slug: 'onduleur-deye-hybride',
    nom: 'Onduleur hybride Deye',
    marque: 'Deye',
    modele: 'SUN-…-SG04LP3 / SG04LP1',
    categorie: 'Onduleurs hybrides',
    resume:
      "Le chef d'orchestre de l'installation : il arbitre en temps réel entre panneaux, batterie et réseau.",
    faits: [
      'Monophasé et triphasé, 5 – 30 kW',
      'Gestion batterie CAN BMS intégrée',
      'Conforme CEI 61727 et VDE-AR-N-4105',
    ],
    garantie: 'Garantie 10 ans',
    datasheet:
      'https://www.deyeinverter.com/deyeinverter/2024/10/21/datasheet_sun-5-12k-sg04lp3_241021_en.pdf',
    pdf: '/fiches/onduleur-deye-hybride.pdf',
  },
  {
    slug: 'batterie-dyness',
    nom: 'Batterie Dyness DL5.0C',
    marque: 'Dyness',
    modele: 'DL5.0C / DL5.0C PRO',
    categorie: 'Batteries',
    resume:
      "Le lithium-fer-phosphate ne s'emballe pas thermiquement : le choix de la sûreté pour du stockage chez soi.",
    faits: [
      'Chimie LFP (LiFePO4) — 5,12 kWh par module, 51,2 V',
      'Plus de 6 000 cycles, empilable par tranches de 5 kWh',
      'Conforme IEC 62619 et UN38.3',
    ],
    garantie: 'Garantie 10 ans',
    datasheet:
      'https://www.dyness.com/Public/Uploads/uploadfile/files/20241023/DynessDL5.0CdatasheetEN.pdf',
    pdf: '/fiches/batterie-dyness.pdf',
  },
  {
    slug: 'smart-meter-huawei',
    nom: 'Smart Meter Huawei',
    marque: 'Huawei',
    modele: 'DTSU666-H (Smart Power Sensor)',
    categorie: 'Supervision & comptage',
    resume:
      "Le compteur intelligent mesure les flux dans les deux sens — la base d'un pilotage honnête de l'autoconsommation.",
    faits: [
      'Mesure de puissance bidirectionnelle',
      'Pilotage de l’autoconsommation / anti-injection',
      'Communication avec l’onduleur',
    ],
    garantie: 'Garantie 2 ans',
    datasheet:
      'https://solar.huawei.com/~/media/Solar/attachment/pdf/es/datasheet/SmartPowerSensor.pdf',
    pdf: '/fiches/smart-meter-huawei.pdf',
  },
  {
    slug: 'wifi-dongle-huawei',
    nom: 'Dongle WiFi Huawei',
    marque: 'Huawei',
    modele: 'Smart Dongle-WLAN-FE',
    categorie: 'Supervision & comptage',
    resume:
      "Une installation qu'on ne mesure pas est une installation qu'on croit sur parole : ce dongle relie la toiture au suivi en ligne.",
    faits: [
      'Supervision WiFi / Ethernet',
      'Production à la minute, historiques et alertes',
      'Accès client via application mobile',
    ],
    garantie: 'Garantie 2 ans',
    datasheet:
      'https://solar.huawei.com/-/media/Solar/attachment/pdf/mea/datasheet/SmartDongle-WLAN-FE.pdf',
    pdf: '/fiches/wifi-dongle-huawei.pdf',
  },
];

export const FICHE_CATEGORIES: FicheCategorie[] = [
  'Panneaux photovoltaïques',
  'Onduleurs réseau',
  'Onduleurs hybrides',
  'Batteries',
  'Supervision & comptage',
];

export function fichesByCategorie(): { categorie: FicheCategorie; fiches: Fiche[] }[] {
  return FICHE_CATEGORIES
    .map((categorie) => ({ categorie, fiches: FICHES.filter((f) => f.categorie === categorie) }))
    .filter((g) => g.fiches.length > 0);
}

export function ficheBySlug(slug: string): Fiche | undefined {
  return FICHES.find((f) => f.slug === slug);
}

/** Lien de téléchargement : la copie auto-hébergée si elle existe, sinon la
 *  source officielle constructeur (toujours fonctionnel). */
export function ficheDownloadHref(f: Fiche): string {
  return f.pdf ?? f.datasheet;
}
