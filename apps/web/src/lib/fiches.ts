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

import {
  PANEL_PRODUCT_WARRANTY_YEARS,
  PANEL_PERFORMANCE_WARRANTY_YEARS,
  PANEL_PERFORMANCE_FLOOR_FR,
  INSTALL_WARRANTY_YEARS,
} from './warranty';

export type FicheCategorie =
  | 'Panneaux photovoltaïques'
  | 'Onduleurs réseau'
  | 'Onduleurs hybrides'
  | 'Batteries'
  | 'Protection & câblage'
  | 'Supervision & comptage';

/** Garantie structurée : durée + précision optionnelle (ex. seuil de performance). */
export interface FicheWarranty {
  years: number;
  /** Précision affichée sous la durée (ex. "≥ 87,4 % de la puissance initiale"). */
  note?: string;
}

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
  /** Garantie commerciale Taqinor pour cette famille (texte affiché, ex. "Garantie 10 ans"). */
  garantie: string;
  /** Même garantie, structurée {years, note} — pour le JSON-LD et un futur usage tabulaire. */
  warranty: FicheWarranty;
  /** Catégories avec lesquelles ce produit se combine typiquement dans une installation
   *  (« se combine avec »). Ne référence jamais sa propre catégorie. */
  pairsWith: FicheCategorie[];
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
    garantie: `Garantie produit ${PANEL_PRODUCT_WARRANTY_YEARS} ans · performance linéaire ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans`,
    warranty: {
      years: PANEL_PERFORMANCE_WARRANTY_YEARS,
      note: `Garantie produit ${PANEL_PRODUCT_WARRANTY_YEARS} ans · garantie performance linéaire ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans (${PANEL_PERFORMANCE_FLOOR_FR} de la puissance initiale)`,
    },
    pairsWith: ['Onduleurs réseau', 'Onduleurs hybrides', 'Supervision & comptage'],
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
    garantie: `Garantie produit ${PANEL_PRODUCT_WARRANTY_YEARS} ans · performance linéaire ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans`,
    warranty: {
      years: PANEL_PERFORMANCE_WARRANTY_YEARS,
      note: `Garantie produit ${PANEL_PRODUCT_WARRANTY_YEARS} ans · garantie performance linéaire ${PANEL_PERFORMANCE_WARRANTY_YEARS} ans (${PANEL_PERFORMANCE_FLOOR_FR} de la puissance initiale)`,
    },
    pairsWith: ['Onduleurs réseau', 'Onduleurs hybrides', 'Supervision & comptage'],
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
    warranty: { years: 10 },
    pairsWith: ['Panneaux photovoltaïques', 'Supervision & comptage'],
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
    warranty: { years: 10 },
    pairsWith: ['Panneaux photovoltaïques', 'Batteries', 'Supervision & comptage'],
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
    warranty: {
      years: 10,
      // WA13 : terme selon le document de garantie émis par le distributeur
      // marocain ; certaines variantes régionales de la DL5.0C affichent 7 ans.
      note: '≥ 70 % de capacité — selon le document de garantie du distributeur (certaines variantes régionales affichent 7 ans)',
    },
    pairsWith: ['Onduleurs hybrides', 'Supervision & comptage'],
    datasheet:
      'https://www.dyness.com/Public/Uploads/uploadfile/files/20241023/DynessDL5.0CdatasheetEN.pdf',
    pdf: '/fiches/batterie-dyness.pdf',
  },
  // ── WJ131 · DEUX POSTES GÉNÉRIQUES DU DEVIS ───────────────────────────────
  // « Tableau De Protection AC/DC » et « Accessoires » sont les deux lignes que
  // le client paie sans jamais savoir ce qu'elles contiennent. Elles n'ont ni
  // marque ni fiche constructeur : leurs fiches sont donc EXPLICATIVES et leurs
  // faits sont NORMATIFS (NF C 15-100, guide UTE C 15-712-1, NF EN 50618,
  // CEI 62852) — jamais une spec produit inventée, jamais un chiffre que la
  // norme fixe au cas par cas (seuils, sections, calibres : ils sortent de
  // l'étude, pas d'ici).
  {
    slug: 'tableau-protection-ac-dc',
    nom: 'Tableau de protection AC/DC',
    marque: 'Poste générique',
    modele: 'Coffret AC + coffret DC — composition selon étude',
    categorie: 'Protection & câblage',
    resume:
      "Le poste qu'on ne regarde jamais et qui protège tout le reste : couper, isoler, encaisser la surtension — avant l'onduleur, avant la maison.",
    faits: [
      'Côté AC : disjoncteur dédié + dispositif différentiel de type A au minimum, selon ce qu’exige l’onduleur',
      'Côté AC : parafoudre de type 2 lorsque l’exposition du site l’impose',
      'Côté DC : interrupteur-sectionneur entre le champ et l’onduleur — la seule façon de couper sous charge',
      'Côté DC : parafoudre DC et fusibles gPV dès que plusieurs chaînes sont mises en parallèle (seuil fixé par le guide)',
      'Règles de référence : NF C 15-100 et guide UTE C 15-712-1 — la composition exacte sort de l’étude',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    pairsWith: ['Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides'],
    // Page officielle AFNOR du guide qui fait foi pour ce poste (pas un PDF
    // constructeur : ce poste n'a pas de constructeur).
    datasheet:
      'https://norminfo.afnor.org/norme/ute-c15-712-1/installations-electriques-a-basse-tension-guide-pratique-installations-photovoltaiques-sans-stockage-et-raccordees-au-reseau-public-de-distribution/105394',
    pdf: null,
  },
  {
    slug: 'accessoires-cablage',
    nom: 'Accessoires de câblage',
    marque: 'Poste générique',
    modele: 'Câble H1Z2Z2-K · connecteurs MC4 · cheminement',
    categorie: 'Protection & câblage',
    resume:
      "La ligne la moins racontée du devis, et celle qui décide de la tenue de tout le reste : ce qui relie les panneaux à l'onduleur reste en plein soleil toute la vie de l'installation.",
    faits: [
      'Câble solaire H1Z2Z2-K (norme NF EN 50618) : double isolation, tenue UV et intempéries, pour la partie continue',
      'Connecteurs PV de type MC4 (norme CEI 62852) : mâle et femelle du MÊME fabricant — jamais deux marques accouplées',
      'Chemin de câble et goulotte : le câble est guidé et protégé, jamais posé à même la couverture',
      'Presse-étoupes : chaque entrée de coffret reste étanche',
      'Sections et longueurs calculées pour tenir la chute de tension du projet',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    pairsWith: ['Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides'],
    // Page officielle AFNOR de la norme qui définit le câble solaire.
    datasheet:
      'https://norminfo.afnor.org/norme/nf-en-50618/cables-electriques-pour-systemes-photovoltaiques/105484',
    pdf: null,
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
    warranty: { years: 2 },
    pairsWith: ['Onduleurs réseau', 'Onduleurs hybrides'],
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
    warranty: { years: 2 },
    pairsWith: ['Onduleurs réseau', 'Onduleurs hybrides'],
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
  'Protection & câblage',
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

/**
 * « Se combine avec » (W326) : les fiches des catégories que `f.pairsWith`
 * référence, groupées par catégorie — pour un bloc de liens croisés en pied de
 * fiche produit (via RelatedLinks). Exclut toujours `f` lui-même.
 */
export function relatedFiches(f: Fiche): { categorie: FicheCategorie; fiches: Fiche[] }[] {
  return f.pairsWith
    .map((categorie) => ({
      categorie,
      fiches: FICHES.filter((other) => other.categorie === categorie && other.slug !== f.slug),
    }))
    .filter((g) => g.fiches.length > 0);
}
