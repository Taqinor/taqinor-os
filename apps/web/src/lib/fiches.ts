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
  STRUCTURE_WARRANTY_YEARS,
} from './warranty';

export type FicheCategorie =
  | 'Panneaux photovoltaïques'
  | 'Onduleurs réseau'
  | 'Onduleurs hybrides'
  | 'Batteries'
  | 'Structure & pose'
  | 'Protection & câblage'
  | 'Supervision & comptage'
  | 'Grands projets';

/** Garantie structurée : durée + précision optionnelle (ex. seuil de performance). */
export interface FicheWarranty {
  years: number;
  /** Précision affichée sous la durée (ex. "≥ 87,4 % de la puissance initiale"). */
  note?: string;
}

/** Une question fréquente du GABARIT 7 BLOCS (bloc 7). */
export interface FicheFaq {
  q: string;
  r: string;
}

export interface Fiche {
  slug: string;
  nom: string;
  marque: string;
  modele: string;
  categorie: FicheCategorie;
  /** Accroche courte (1 phrase) — vérifiée, sans chiffre inventé. */
  resume: string;
  // ── GABARIT 7 BLOCS (fondateur 2026-08-18) ────────────────────────────────
  // Les fiches PRODUIT (marquées) ont toujours vécu sur `faits` + `garantie` ;
  // les fiches de FAMILLE (postes génériques, grands projets) ont besoin d'un
  // gabarit complet parce qu'elles n'ont aucune fiche constructeur derrière
  // elles. Les blocs 1/2/4/6/7 sont donc OPTIONNELS : une valeur absente est
  // OMISE au rendu (règle dure « faits vérifiés uniquement »), jamais remplacée
  // par un placeholder.
  /** BLOC 1 — RÔLE : à quoi sert ce poste dans l'installation (1-2 phrases). */
  role?: string;
  /** BLOC 2 — BÉNÉFICES : ce que ce poste change concrètement pour l'acheteur. */
  benefices?: string[];
  /** BLOC 3 — SPECS : faits techniques vérifiés (page Équipement + fiche officielle). */
  faits: string[];
  /** BLOC 4 — NORMES de référence (texte normatif exact, jamais un seuil inventé). */
  normes?: string[];
  /** BLOC 5 — GARANTIE commerciale Taqinor (texte affiché, ex. "Garantie 10 ans"). */
  garantie: string;
  /** Même garantie, structurée {years, note} — pour le JSON-LD et un futur usage tabulaire. */
  warranty: FicheWarranty;
  /** BLOC 6 — CE QUE L'ACHETEUR DOIT VÉRIFIER (points de contrôle avant réception). */
  verifier?: string[];
  /** BLOC 7 — FAQ : les questions réellement posées sur ce poste. */
  faq?: FicheFaq[];
  /** Catégories avec lesquelles ce produit se combine typiquement dans une installation
   *  (« se combine avec »). Ne référence jamais sa propre catégorie. */
  pairsWith: FicheCategorie[];
  /**
   * Fiches SŒURS explicites, par slug — pour les paires que `pairsWith` ne peut
   * pas exprimer parce qu'elles partagent la MÊME catégorie : protection DC ↔
   * protection AC (les deux moitiés de l'ancien coffret combiné, donc les deux
   * moitiés qu'un lien déjà émis doit pouvoir atteindre), câblage ↔ accessoires
   * de pose. Ne se référence jamais soi-même (verrouillé par le test).
   */
  voirAussi?: string[];
  /**
   * Fiche constructeur officielle — ou la page officielle de la NORME qui fait
   * foi pour un poste sans constructeur. `null` quand aucune source officielle
   * n'a été VÉRIFIÉE : le bouton de téléchargement est alors OMIS (règle
   * fondateur « faits vérifiés uniquement » — jamais un lien deviné qui tombe
   * en 404 sous les yeux du client).
   */
  datasheet: string | null;
  /**
   * G4 (2026-08-19) — fiche constructeur MONOPHASÉE additionnelle, pour une
   * gamme qui existe aussi en monophasé sous un AUTRE modèle que celui de
   * `datasheet` (ex. onduleur hybride Deye : `datasheet` = SG05LP3 triphasé,
   * `datasheetMono` = SG05LP1 monophasé — deux fiches constructeur réelles,
   * un seul `modele` affiché qui les nomme toutes les deux). `undefined` pour
   * toute fiche à gamme unique : n'invente jamais un second lien qui n'existe
   * pas.
   */
  datasheetMono?: string;
  /** Copie auto-hébergée `/fiches/<slug>.pdf` — null tant qu'elle n'est pas déposée. */
  pdf: string | null;
  /**
   * PHOTO d'illustration auto-hébergée sous `/fiches/photos/` (jamais un
   * hotlink). Optionnelle et OMISE quand elle n'existe pas : une fiche sans
   * photo juste ET libre de droits reste sans photo, jamais de remplissage.
   *
   * DROITS (règle fondateur 2026-08-18) : deux classes, et deux seulement.
   *  · PHOTO DE CHANTIER TAQINOR — droits fondateur : nos propres photos, celles
   *    dont les originaux vivent déjà dans `public/photos/`. C'est la MEILLEURE
   *    classe (c'est notre matériel, notre équipe, notre pose réelle) ; aucune
   *    attribution n'est due, donc aucun `photoCredit`.
   *  · Photo libre externe : uniquement Wikimedia Commons (CC BY / CC BY-SA /
   *    CC0 / domaine public explicite), Unsplash ou Pexels.
   * Jamais de média constructeur : leurs médiathèques exigent une autorisation
   * écrite pour l'usage commercial. Le registre complet — fichier, fiche,
   * source (page de licence, ou l'original `/photos/` dont la photo dérive),
   * auteur, licence — vit dans `public/fiches/photos/CREDITS.md`.
   */
  photo?: string;
  /**
   * Ligne de crédit courte affichée sous la photo (« © Auteur — licence »)
   * quand la licence EXIGE l'attribution (CC BY, CC BY-SA). Absent pour une
   * image CC0 / domaine public, où aucune attribution n'est due.
   */
  photoCredit?: string;
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
    modele: 'SUN-…-SG05LP3 / SG05LP1',
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
    // Fondateur 2026-08-15 : génération réellement en pose = SG05 (10 kW =
    // SUN-10K-SG05LP3-EU-SM2 confirmé, mono = gamme SG05LP1) — l'ancien lien
    // pointait vers la datasheet SG04LP3, une génération dépassée.
    datasheet:
      'https://www.deyeinverter.com/deyeinverter/2024/09/27/datasheet_sun-3-12k-sg05lp3-eu-sm2_240927_en.pdf',
    // G4 (2026-08-19, plainte fondateur « the deye 5kw datasheet is still the
    // sg04 ») — datasheet OFFICIELLE deyeinverter.com de la gamme MONOPHASÉE
    // SUN-3.6/5/6/7.6/8K-SG05LP1-EU (le 5 kW réellement posé y figure
    // nommément) : sans ce second lien, le SG04LP1 ne survivait nulle part
    // dans le code mais restait absent de la seule source publique vérifiée.
    datasheetMono:
      'https://www.deyeinverter.com/deyeinverter/2023/07/31/datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf',
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
  // ── DÉCOUPAGE 11 FAMILLES (fondateur 2026-08-18) ──────────────────────────
  // Les postes GÉNÉRIQUES du devis sont les lignes que le client paie sans
  // jamais savoir ce qu'elles contiennent. Ils n'ont pas de fiche constructeur :
  // leurs fiches sont EXPLICATIVES et leurs faits sont NORMATIFS (NF C 15-100,
  // guide UTE C 15-712-1, NF EN 50618, CEI 62852, CEI 60947-3, CEI 60269-6,
  // CEI 61643-31/-11) — jamais une spec produit inventée, jamais un chiffre que
  // la norme fixe au cas par cas (seuils, sections, calibres : ils sortent de
  // l'étude, pas d'ici). RÈGLES DE MARQUE, décidées le 18/08 :
  //   · protection AC → Schneider peut être nommé (CONFIRMÉ fondateur) ;
  //   · protection DC → AUCUNE marque pour l'instant (bascule Citel décidée mais
  //     pas encore achetée, et une offre deux-gammes est à l'étude) ;
  //   · câblage → Nexans peut être nommé (CONFIRMÉ fondateur) ; les CONNECTEURS
  //     restent SANS marque (« d'origine, certifiés du fabricant de vos
  //     panneaux ») tant que la référence n'est pas arrêtée.
  // Jamais un nombre d'installations, nulle part.
  // ── STRUCTURE / SOCLES : DEUX FICHES, PAS UNE (fondateur 18/08/2026) ──────
  // « It is better to have a page for each. » L'ancienne fiche unique mélangeait
  // le CHÂSSIS (les triangles qui portent les modules) et les SOCLES (les plots
  // béton qui les lestent) : deux pièces différentes, deux questions différentes
  // du client (« ça tient comment ? » / « faut-il percer ? »). Les cotes citées
  // ci-dessous sont celles de la fiche géométrique donnée par le fondateur le
  // 18/08 — les mêmes constantes que la scène 3D du calepineur
  // (`src/scripts/roofPro11/scene3d.ts` : PROFILE_M, PLATINE_*, SOCLE_*).
  {
    slug: 'structure-fixation',
    nom: 'Structure de fixation',
    marque: 'Poste générique',
    modele: 'Triangles boulonnés en profilé C galvanisé perforé 41 × 41 mm',
    categorie: 'Structure & pose',
    resume:
      'Ce qui tient vos panneaux pendant trente ans de vent, de soleil et de pluie — un triangle assemblé sur place à chaque jointure de panneaux.',
    role:
      'La structure porte les modules et transmet les efforts du vent jusqu’aux socles. Sur toiture-terrasse, ce n’est ni un châssis d’un seul tenant ni un trio de montants par module : c’est un TRIANGLE assemblé sur place à chaque jointure de panneaux, trois pièces boulonnées, chaque pied sur son propre socle béton.',
    benefices: [
      'Les modules restent plans et alignés : pas de contrainte mécanique sur le verre, pas de micro-fissure de cellule',
      'La reprise d’efforts est calculée pour le site : un panneau ne part pas au premier coup de chergui',
      'Un triangle par jointure porte les deux panneaux voisins à la fois : moins de pièces au sol, un montage démontable pièce par pièce',
      'Tout est boulonné au trou existant du profilé perforé : aucune découpe, aucune soudure sur votre toiture',
    ],
    faits: [
      'Triangle assemblé à CHAQUE jointure de panneaux : trois pièces boulonnées sur place, jamais un châssis d’un seul tenant',
      'Profilé C galvanisé PERFORÉ, section 41 × 41 mm — l’assemblage se fait au trou existant',
      'Platine acier de pied 120 × 60 mm, épaisseur 8 mm, boulonnée sous chaque montant',
      'Visserie inox, mise à la terre de la structure incluse',
      'Acier galvanisé à chaud ou aluminium anodisé anticorrosion, selon l’exposition du site',
      'Le profil, l’entraxe et l’inclinaison sont fixés par l’étude — jamais un catalogue',
    ],
    normes: [
      'Charges climatiques : Eurocode 1 — EN 1991-1-4 (vent) et EN 1991-1-3 (neige)',
      'Dimensionnement : Eurocode 3 (acier) ou Eurocode 9 (aluminium)',
      'Galvanisation à chaud : ISO 1461',
      'Mise à la terre des masses : NF C 15-100',
    ],
    garantie: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans (structure) · garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: STRUCTURE_WARRANTY_YEARS,
      note: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans sur la structure ; garantie de pose et de main-d’œuvre Taqinor ${INSTALL_WARRANTY_YEARS} ans.`,
    },
    verifier: [
      'La note de calcul au vent existe et cite la zone et l’altitude RÉELLES du site',
      'La visserie est inox — pas d’acier zingué en toiture',
      'Il y a bien un triangle à chaque jointure de panneaux, pas un montant sur deux',
      'La continuité de terre de la structure est mesurée à la réception',
    ],
    faq: [
      {
        q: 'Sur toiture inclinée, faut-il percer la couverture ?',
        r: 'Oui : là, les fixations traversent la couverture et sont étanchées point par point. C’est la toiture-terrasse qui se pose SANS percement, parce que la structure y est simplement lestée — voir la fiche « Socles de lestage ». L’étude tranche selon votre toiture.',
      },
      {
        q: 'Acier ou aluminium ?',
        r: 'L’aluminium anodisé est plus léger et tient mieux l’air marin ; l’acier galvanisé à chaud encaisse des portées plus longues. L’exposition du site décide, pas le prix.',
      },
      {
        q: 'Pourquoi un triangle à chaque jointure plutôt qu’un châssis continu ?',
        r: 'Parce qu’un triangle porte les deux panneaux voisins à la fois : la même rigidité avec moins de pièces posées sur votre dalle, et un ensemble qui se démonte pièce par pièce si la toiture doit être reprise un jour.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques', 'Protection & câblage'],
    voirAussi: ['socles-lestage', 'accessoires-pose'],
    // Aucune source officielle VÉRIFIÉE en ligne pour ce poste : lien omis
    // plutôt que deviné (le contenu ci-dessus reste, lui, entièrement sourcé).
    datasheet: null,
    pdf: null,
    // PHOTO DE CHANTIER TAQINOR (droits fondateur) : l'équipe montant les
    // triangles en profilé C galvanisé perforé. Elle remplace une photo
    // Wikimedia d'une toiture suisse sur plots ronds en caoutchouc — un
    // matériel qui n'est PAS le nôtre. Aucune attribution due : pas de crédit.
    photo: '/fiches/photos/structure-triangles-taqinor.jpg',
  },
  {
    slug: 'socles-lestage',
    nom: 'Socles de lestage',
    marque: 'Poste générique',
    modele: 'Plots béton préfabriqués — pose sans percement',
    categorie: 'Structure & pose',
    resume:
      'La seule pièce posée à même votre dalle : elle tient l’installation par son poids, sans qu’un seul trou soit percé dans l’étanchéité.',
    role:
      'Sur toiture-terrasse, la structure n’est pas vissée au bâtiment : elle est LESTÉE. Un plot béton préfabriqué est posé sous chaque pied de triangle, et c’est leur masse qui reprend les efforts du vent. C’est le seul poste du devis en contact direct avec votre étanchéité.',
    benefices: [
      'AUCUN percement de l’étanchéité : rien à reprendre, rien à ré-étancher, aucune garantie de toiture remise en cause',
      'L’installation reste démontable : les socles se déposent et se reposent sans laisser un seul point d’ancrage',
      'La charge est répartie pied par pied au lieu d’être concentrée sur quelques points de fixation',
    ],
    faits: [
      'Plots béton préfabriqués CARRÉS de 30 × 30 × 20 cm',
      'Un socle sous CHAQUE pied de triangle — jamais une longrine continue',
      'Posés à même la dalle, sur l’étanchéité existante : aucun percement, aucun scellement, aucune reprise',
      'La charge de lestage à mettre en œuvre est fixée par l’étude au vent du site — jamais un nombre de plots au catalogue',
    ],
    normes: [
      'Charges de vent à reprendre par le lestage : Eurocode 1 — EN 1991-1-4 (la charge retenue sort de l’étude du site, pas d’un tableau)',
      'Poids propre et descente de charges sur la dalle : Eurocode 1 — EN 1991-1-1',
    ],
    garantie: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans (structure) · garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: STRUCTURE_WARRANTY_YEARS,
      note: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans sur la structure lestée ; garantie de pose et de main-d’œuvre Taqinor ${INSTALL_WARRANTY_YEARS} ans.`,
    },
    verifier: [
      'Votre étanchéité est INTACTE après la pose : aucun trou, aucun scellement, constaté à la réception',
      'Il y a bien un socle sous chaque pied — aucun pied ne repose directement sur la dalle',
      'La charge de lestage retenue figure dans la note de calcul au vent, avec la zone et l’altitude RÉELLES du site',
    ],
    faq: [
      {
        q: 'Faut-il percer ma toiture ?',
        r: 'Sur toiture-terrasse, non : l’installation est lestée par des plots béton carrés de 30 × 30 × 20 cm, un sous chaque pied, posés sur l’étanchéité existante. Sur toiture inclinée, ce sont les fixations de la structure qui traversent la couverture et qui sont étanchées point par point — voir la fiche « Structure de fixation ». C’est l’étude qui tranche.',
      },
      {
        q: 'Ma dalle supporte-t-elle ce poids ?',
        r: 'C’est exactement ce que l’étude vérifie avant la pose : la charge de lestage et sa répartition pied par pied sont calculées sur VOTRE toiture. Si la dalle ne les accepte pas, la pose lestée n’est pas retenue — on ne force jamais un lestage sur un support qui ne l’encaisse pas.',
      },
      {
        q: 'Pourquoi des plots carrés plutôt qu’une longrine continue ?',
        r: 'Parce qu’un plot sous chaque pied répartit la charge là où elle arrive vraiment, et laisse l’eau circuler librement sur la terrasse entre les rangées. Un ouvrage continu ferait barrage et concentrerait le poids sur des lignes entières de la dalle.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques'],
    voirAussi: ['structure-fixation'],
    // Aucune source officielle VÉRIFIÉE en ligne pour ce poste : lien omis
    // plutôt que deviné.
    datasheet: null,
    pdf: null,
    // PHOTO DE CHANTIER TAQINOR (droits fondateur) : l'équipe positionnant les
    // supports béton préfabriqués et les rails sur une toiture-terrasse.
    // Aucune attribution due : pas de crédit rendu.
    photo: '/fiches/photos/socles-beton-taqinor.jpg',
  },
  {
    slug: 'protection-dc',
    nom: 'Protection DC (côté panneaux)',
    marque: 'Poste générique',
    modele: 'Coffret DC — composition selon étude',
    categorie: 'Protection & câblage',
    resume:
      'Entre vos panneaux et l’onduleur, un courant continu qui ne s’éteint pas tout seul : ce coffret est la seule façon de le couper et de l’encaisser.',
    role:
      'Le côté continu d’une installation solaire produit dès qu’il fait jour — on ne peut pas « l’éteindre ». Le coffret DC apporte les deux choses que le réseau ne fournit pas de ce côté : un point de coupure franc sous charge, et un chemin d’écoulement pour les surtensions.',
    benefices: [
      'Un point de coupure unique et repéré : intervention, maintenance et secours peuvent isoler le champ en une manœuvre',
      'La surtension d’origine atmosphérique s’écoule vers la terre au lieu de traverser l’onduleur',
      'En multi-chaînes, un défaut sur une chaîne ne se propage pas aux autres',
    ],
    faits: [
      'Interrupteur-sectionneur entre le champ et l’onduleur — la seule façon de couper sous charge',
      'Parafoudre DC lorsque l’exposition du site l’impose',
      'Fusibles gPV et porte-fusibles dès que plusieurs chaînes sont mises en parallèle (seuil fixé par le guide)',
      'Coffret et presse-étoupes en indice de protection adapté à l’emplacement',
      'Calibres, tension d’emploi et nombre de départs sortent de l’étude électrique du projet',
    ],
    normes: [
      'Guide UTE C 15-712-1 — installations photovoltaïques raccordées au réseau',
      'NF C 15-100 — installations électriques à basse tension',
      'CEI 60947-3 — appareillage de coupure : interrupteurs et interrupteurs-sectionneurs',
      'CEI 60269-6 — fusibles pour la protection des systèmes photovoltaïques (gPV)',
      'CEI 61643-31 — parafoudres pour installations photovoltaïques',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    verifier: [
      'La tension d’emploi DC de chaque organe est supérieure à la tension à vide du champ par grand froid',
      'Les fusibles sont bien de type gPV — un fusible domestique ne coupe pas un arc continu',
      'Le coffret porte un repérage lisible et le schéma de l’installation',
    ],
    faq: [
      {
        q: 'Pourquoi un coffret séparé du tableau de la maison ?',
        r: 'Parce que le continu et l’alternatif ne se coupent pas de la même manière et n’ont pas les mêmes tensions d’emploi. Les mélanger dans un seul coffret oblige à un compromis sur les deux.',
      },
      {
        q: 'Le parafoudre DC est-il obligatoire ?',
        r: 'Il est requis selon l’exposition du site et la longueur des liaisons — c’est l’analyse du risque prévue par le guide qui le déclenche, pas une règle unique pour tout le Maroc.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides'],
    // L'AUTRE MOITIÉ du coffret d'hier : un lien déjà émis vers
    // /produits/tableau-protection-ac-dc atterrit ici, il doit pouvoir finir là-bas.
    voirAussi: ['protection-ac'],
    // Page officielle AFNOR du guide qui fait foi pour ce poste (pas un PDF
    // constructeur : ce poste n'a pas de constructeur).
    datasheet:
      'https://norminfo.afnor.org/norme/ute-c15-712-1/installations-electriques-a-basse-tension-guide-pratique-installations-photovoltaiques-sans-stockage-et-raccordees-au-reseau-public-de-distribution/105394',
    pdf: null,
    photo: '/fiches/photos/coffret-protection-dc.jpg',
    photoCredit: '© Asurnipal — Wikimedia Commons, CC BY-SA 4.0',
  },
  {
    slug: 'protection-ac',
    nom: 'Protection AC (côté réseau)',
    marque: 'Poste générique',
    modele: 'Coffret AC — composition selon étude',
    categorie: 'Protection & câblage',
    resume:
      'Entre l’onduleur et votre tableau, l’organe qui protège les personnes et le bâtiment — et qui permet de déconnecter l’installation du réseau.',
    role:
      'Le coffret AC est le point de rencontre entre votre installation solaire et le reste du bâtiment. Il assure trois fonctions que rien d’autre ne remplit : protéger les personnes contre le défaut d’isolement, protéger le câble contre la surcharge, et permettre de séparer l’installation du réseau.',
    benefices: [
      'La protection différentielle coupe avant qu’un défaut ne devienne dangereux pour une personne',
      'Un organe de séparation dédié : couper le solaire ne coupe pas la maison',
      'La surtension venue du réseau est écrêtée avant d’atteindre l’onduleur',
    ],
    faits: [
      'Disjoncteur dédié, calibré sur le courant de sortie de l’onduleur et sur la section du câble',
      'Dispositif différentiel de type A au minimum — le type exigé par l’onduleur prime toujours',
      'Parafoudre AC de type 2 lorsque l’exposition du site l’impose',
      'Organe de séparation accessible et repéré, côté réseau',
      'Matériel modulaire de marque Schneider (choix Taqinor confirmé)',
      'Calibres et courbes sortent de l’étude électrique du projet',
    ],
    normes: [
      'NF C 15-100 — installations électriques à basse tension',
      'Guide UTE C 15-712-1 — couplage au réseau d’une installation photovoltaïque',
      'CEI 61643-11 — parafoudres basse tension pour réseaux de distribution',
      'CEI 61008 / CEI 61009 — dispositifs à courant différentiel résiduel',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    verifier: [
      'Le type de différentiel (A, F ou B) est celui que la notice de VOTRE onduleur exige',
      'Le calibre du disjoncteur est cohérent avec la section réellement posée, pas avec la puissance commerciale',
      'L’organe de séparation est accessible sans outil et clairement identifié',
    ],
    faq: [
      {
        q: 'Puis-je réutiliser le disjoncteur qui est déjà dans mon tableau ?',
        r: 'Non : l’installation solaire est un départ à part entière, avec son propre calibre et sa propre protection différentielle. La partager, c’est perdre la sélectivité — un défaut solaire couperait toute la maison.',
      },
      {
        q: 'Différentiel 30 mA ou 300 mA ?',
        r: 'Cela dépend de la fonction visée (protection des personnes ou protection contre l’incendie) et du schéma de liaison à la terre du site. Les deux existent dans nos coffrets ; l’étude tranche.',
      },
    ],
    pairsWith: ['Onduleurs réseau', 'Onduleurs hybrides', 'Supervision & comptage'],
    voirAussi: ['protection-dc'],
    datasheet:
      'https://norminfo.afnor.org/norme/ute-c15-712-1/installations-electriques-a-basse-tension-guide-pratique-installations-photovoltaiques-sans-stockage-et-raccordees-au-reseau-public-de-distribution/105394',
    pdf: null,
    photo: '/fiches/photos/coffret-protection-ac.jpg',
    photoCredit: '© Asurnipal — Wikimedia Commons, CC BY-SA 4.0',
  },
  {
    slug: 'cablage',
    nom: 'Câblage',
    marque: 'Poste générique',
    modele: 'Câble solaire H1Z2Z2-K · connecteurs d’origine — sections selon étude',
    categorie: 'Protection & câblage',
    resume:
      'La ligne la moins racontée du devis, et celle qui décide de la tenue de tout le reste : ce qui relie les panneaux à l’onduleur reste en plein soleil toute la vie de l’installation.',
    role:
      'Le câblage transporte toute votre production, du premier module jusqu’au tableau. Un câble sous-dimensionné ne tombe pas en panne : il chauffe, et vous fait perdre quelques pour cent de production chaque jour, pendant vingt-cinq ans.',
    benefices: [
      'La section est calculée pour tenir la chute de tension du projet — la production arrive au tableau, elle ne se dissipe pas en chaleur',
      'Le câble solaire tient l’UV et l’écart de température d’une toiture marocaine, là où un câble bâtiment durcit et se fissure',
      'Connecteurs d’une seule et même origine : c’est la panne d’installation la plus fréquente qui disparaît',
    ],
    faits: [
      'Câble solaire H1Z2Z2-K (norme NF EN 50618) : double isolation, tenue UV et intempéries, pour la partie continue',
      'Marque Nexans (choix Taqinor confirmé)',
      'Sections courantes du référentiel : 4, 6, 10 et 16 mm² — la section retenue sort du calcul de chute de tension',
      'Connecteurs d’origine, certifiés du fabricant de vos panneaux : mâle et femelle du MÊME fabricant, jamais de panachage',
      'Longueurs et sections de chaque liaison sont fixées par l’étude électrique, pas par un forfait',
    ],
    normes: [
      'NF EN 50618 — câbles électriques pour systèmes photovoltaïques',
      'CEI 62852 — connecteurs pour systèmes photovoltaïques en courant continu',
      'NF C 15-100 — sections, chutes de tension et protection des canalisations',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    verifier: [
      'Le câble porte bien le marquage H1Z2Z2-K sur sa gaine — c’est lisible à l’œil nu',
      'Les connecteurs mâle et femelle d’une même liaison portent la même marque et la même référence',
      'La chute de tension calculée du projet vous est communiquée, liaison par liaison',
    ],
    faq: [
      {
        q: 'Pourquoi ne pas panacher les connecteurs ?',
        r: 'Deux connecteurs « compatibles » de marques différentes n’ont pas exactement la même géométrie de contact. L’accouplement chauffe, s’oxyde, puis lâche — et la garantie du fabricant tombe. C’est pour cela qu’ils sont d’origine, du fabricant de vos panneaux.',
      },
      {
        q: 'Une section plus grosse, est-ce toujours mieux ?',
        r: 'Au-delà de ce que le calcul demande, non : on paie du cuivre qui ne rapporte plus rien. La bonne section est celle qui tient la chute de tension visée sur la longueur réelle.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides'],
    voirAussi: ['accessoires-pose', 'protection-dc'],
    // Page officielle AFNOR de la norme qui définit le câble solaire.
    datasheet:
      'https://norminfo.afnor.org/norme/nf-en-50618/cables-electriques-pour-systemes-photovoltaiques/105484',
    pdf: null,
    // Connecteurs solaires démontés : corps mâle/femelle, contacts à sertir,
    // presse-étoupes. Aucune marque lisible — cohérent avec la décision
    // fondateur de ne publier AUCUNE référence commerciale de connecteur.
    photo: '/fiches/photos/connecteurs-solaires.jpg',
    photoCredit: '© Asurnipal — Wikimedia Commons, CC BY-SA 4.0',
  },
  {
    slug: 'accessoires-pose',
    nom: 'Accessoires de pose',
    marque: 'Poste générique',
    modele: 'Cheminement · presse-étoupes · mise à la terre',
    categorie: 'Structure & pose',
    resume:
      'Tout ce qui fait qu’une installation vieillit bien plutôt que mal : le câble est guidé, les entrées sont étanches, les masses sont à la terre.',
    role:
      'Ce poste regroupe les fournitures de pose qui n’apparaissent sur aucune photo : le cheminement des câbles, l’étanchéité des entrées de coffret, et la mise à la terre des masses métalliques. C’est la différence entre une installation propre et une installation qui se dégrade.',
    benefices: [
      'Le câble ne repose jamais à même la couverture : plus de frottement, plus de gaine ouverte au bout de cinq ans',
      'Chaque entrée de coffret reste étanche : l’eau n’entre pas là où passe le câble',
      'Les masses métalliques sont reliées à la terre : un défaut d’isolement devient détectable au lieu d’être dangereux',
    ],
    faits: [
      'Chemins de câbles et goulottes : le câble est guidé et protégé sur tout son parcours',
      'Presse-étoupes en indice de protection adapté à chaque entrée de coffret',
      'Mise à la terre des masses : conducteur de protection, liaison équipotentielle et accessoires de raccordement',
      'Visserie inox et petites fournitures de fixation',
      'Quantités fixées par le parcours réel relevé sur site',
    ],
    normes: [
      'NF C 15-100 — mise à la terre, liaisons équipotentielles et cheminement des canalisations',
      'Guide UTE C 15-712-1 — mise à la terre du champ photovoltaïque',
      'CEI 60529 — indices de protection IP des enveloppes et des entrées de câble',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque composant conserve la garantie de son fabricant.',
    },
    verifier: [
      'La valeur de la prise de terre est MESURÉE et vous est communiquée à la réception',
      'Aucun câble ne pend ni ne frotte : tout est sur chemin de câble, goulotte ou collier UV',
      'Les presse-étoupes sont serrés au diamètre du câble, pas au diamètre du perçage',
    ],
    faq: [
      {
        q: 'Pourquoi cette ligne n’est-elle pas incluse dans « installation » ?',
        r: 'Parce que ce sont des FOURNITURES, dont les quantités dépendent du parcours réel de vos câbles. Les noyer dans un forfait de pose reviendrait à vous les facturer sans que vous puissiez les vérifier.',
      },
      {
        q: 'La mise à la terre existe déjà chez moi — faut-il la refaire ?',
        r: 'Pas nécessairement : elle est mesurée, et complétée seulement si la valeur relevée ne convient pas. La mesure vous est remise dans tous les cas.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques', 'Protection & câblage'],
    voirAussi: ['cablage', 'structure-fixation'],
    datasheet:
      'https://norminfo.afnor.org/norme/ute-c15-712-1/installations-electriques-a-basse-tension-guide-pratique-installations-photovoltaiques-sans-stockage-et-raccordees-au-reseau-public-de-distribution/105394',
    pdf: null,
    photo: '/fiches/photos/chemin-de-cables.jpg',
    photoCredit: '© Santeri Viinamäki — Wikimedia Commons, CC BY-SA 4.0',
  },
  // ── GRANDS PROJETS (fondateur 2026-08-18) ─────────────────────────────────
  // Trois fiches NORMATIVES et GÉNÉRIQUES, écrites pour un acheteur
  // professionnel : rôle, normes applicables, et ce qu'il doit exiger de son
  // installateur — quel qu'il soit. AUCUNE MARQUE, aucun chiffre de projet,
  // aucun nombre d'installations. Ces trois postes n'existent pas au catalogue
  // résidentiel : ils ne sont donc appariés à aucune ligne de devis
  // résidentiel, et se consultent depuis la bibliothèque /produits.
  {
    slug: 'poste-mt-raccordement',
    nom: 'Poste MT et raccordement',
    marque: 'Poste générique',
    modele: 'Poste de livraison HTA — composition selon étude et prescriptions du distributeur',
    categorie: 'Grands projets',
    resume:
      'Au-delà d’une certaine puissance, on ne se raccorde plus au tableau : on se raccorde au réseau moyenne tension, avec un poste et un contrat.',
    role:
      'Le poste de livraison est la frontière physique et juridique entre le réseau du distributeur et votre installation. Il porte la cellule d’arrivée, la protection générale, le transformateur et le comptage. Sa conformité conditionne la mise sous tension : sans procès-verbal favorable, aucune production ne démarre.',
    benefices: [
      'La puissance raccordable n’est plus limitée par le branchement basse tension du site',
      'Le point de livraison, le comptage et les responsabilités sont contractuellement établis',
      'Les protections de découplage rendent l’installation compatible avec l’exploitation du réseau',
    ],
    faits: [
      'Cellules HTA d’arrivée et de protection, transformateur, tableau général basse tension et comptage',
      'Protection de découplage : l’installation se sépare du réseau lorsque celui-ci sort de ses tolérances',
      'Génie civil, ventilation, accès et sécurité du local imposés par le distributeur',
      'La composition exacte découle de l’étude de raccordement et des prescriptions du gestionnaire de réseau',
    ],
    normes: [
      'NF C 13-100 — postes de livraison raccordés à un réseau de distribution publique HTA',
      'NF C 13-200 — installations électriques à haute tension',
      'NF C 15-100 — partie basse tension en aval du poste',
      'Prescriptions techniques du gestionnaire de réseau (ONEE ou régie) — elles priment localement',
      'Loi 82-21 relative à l’autoproduction d’énergie électrique',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque équipement conserve la garantie de son constructeur.',
    },
    verifier: [
      'L’étude de raccordement a été instruite par le gestionnaire de réseau AVANT la commande du poste',
      'Les réglages de la protection de découplage sont ceux notifiés par le distributeur, et sont procès-verbalisés',
      'Le contrôle initial par un organisme agréé est prévu au planning, pas découvert à la fin',
      'Le régime de neutre et le schéma de liaison à la terre du site sont explicitement documentés',
    ],
    faq: [
      {
        q: 'À partir de quelle puissance faut-il un poste MT ?',
        r: 'Le seuil n’est pas une constante : il dépend de la puissance de raccordement demandée et de l’état du réseau au droit du site. C’est l’étude de raccordement du distributeur qui le fixe, projet par projet.',
      },
      {
        q: 'Qui est propriétaire du poste ?',
        r: 'Selon le montage retenu, le poste peut être privé (à votre charge, en aval du point de livraison) ou intégrer des ouvrages concédés. La frontière de propriété doit figurer noir sur blanc dans la convention de raccordement.',
      },
    ],
    pairsWith: ['Onduleurs réseau', 'Supervision & comptage'],
    datasheet: null,
    pdf: null,
    photo: '/fiches/photos/poste-livraison-mt.jpg',
    photoCredit: '© Cjp24 — Wikimedia Commons, CC BY-SA 4.0',
  },
  {
    slug: 'supervision-comptage',
    nom: 'Supervision et comptage (grands projets)',
    marque: 'Poste générique',
    modele: 'Comptage de production · acquisition · supervision — architecture selon étude',
    categorie: 'Grands projets',
    resume:
      'Sur une grande installation, la production n’est pas une impression : c’est une mesure, opposable, sur laquelle reposent le contrat et le financement.',
    role:
      'La chaîne de supervision et de comptage mesure ce que l’installation produit, ce que le site consomme et ce qui transite au point de livraison. Elle sert à trois choses à la fois : facturer, prouver la performance contractuelle, et détecter une dérive avant qu’elle ne coûte une saison de production.',
    benefices: [
      'La production est mesurée au point de livraison : la facturation et le suivi contractuel reposent sur la même donnée',
      'Une dérive de performance se voit en jours, pas en fin d’année',
      'Les données sont exportables et conservées : un financeur ou un auditeur peut les rejouer',
    ],
    faits: [
      'Comptage de production et comptage bidirectionnel au point de livraison',
      'Acquisition des onduleurs, capteurs d’irradiance et de température de module',
      'Calcul du ratio de performance à partir de grandeurs mesurées, jamais estimées',
      'Alarmes, historisation et export des données ; l’architecture de communication est fixée par l’étude',
    ],
    normes: [
      'CEI 61724-1 — surveillance des performances des systèmes photovoltaïques',
      'CEI 62053 — équipements de comptage de l’énergie électrique',
      'Prescriptions de comptage du gestionnaire de réseau (ONEE ou régie)',
    ],
    garantie: `Garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: INSTALL_WARRANTY_YEARS,
      note: 'Garantie de pose et de main-d’œuvre Taqinor ; chaque équipement conserve la garantie de son constructeur.',
    },
    verifier: [
      'La classe de précision du comptage est écrite au contrat, et pas seulement « conforme »',
      'Le ratio de performance est calculé selon la CEI 61724-1, avec la classe de surveillance annoncée',
      'Les données brutes vous appartiennent et sont exportables sans passer par le fournisseur',
      'La durée de conservation des historiques est contractualisée',
    ],
    faq: [
      {
        q: 'Le portail du fabricant d’onduleurs ne suffit-il pas ?',
        r: 'Il donne une vision par onduleur, pas une mesure au point de livraison, et sa donnée n’est pas opposable. Pour un contrat de performance ou un financement, c’est le comptage qui fait foi.',
      },
      {
        q: 'Faut-il des capteurs d’irradiance ?',
        r: 'Dès que l’on veut un ratio de performance exploitable : sans mesure de l’ensoleillement reçu, on ne peut pas distinguer une mauvaise semaine de météo d’une installation qui décroche.',
      },
    ],
    pairsWith: ['Onduleurs réseau', 'Protection & câblage'],
    datasheet: null,
    pdf: null,
  },
  {
    slug: 'structures-grandes-installations',
    nom: 'Structures pour grandes installations',
    marque: 'Poste générique',
    modele: 'Toiture industrielle, ombrière ou pose au sol — système selon étude',
    categorie: 'Grands projets',
    resume:
      'À l’échelle d’une toiture industrielle, d’une ombrière ou d’un champ au sol, la structure devient un ouvrage de génie civil — avec sa note de calcul et sa réception.',
    role:
      'Sur un grand projet, la structure ne se choisit plus sur catalogue : elle se calcule. Charges de vent et de neige du site, capacité portante de la charpente existante ou du sol, tenue à la corrosion sur la durée du contrat — chacun de ces points peut à lui seul disqualifier une solution.',
    benefices: [
      'La charpente existante est vérifiée AVANT commande : pas de renforcement découvert en cours de chantier',
      'Le système de fixation est adapté à la couverture réelle (bac acier, membrane, sandwich) et préserve la garantie de la toiture',
      'La durabilité est dimensionnée sur la durée d’exploitation visée, pas sur la durée de la garantie commerciale',
    ],
    faits: [
      'Trois familles : intégration sur toiture industrielle, ombrière de parking, pose au sol',
      'Note de calcul établie sur les charges climatiques et sismiques du site réel',
      'Vérification de la capacité portante de la charpente ou étude géotechnique pour le sol',
      'Traitement anticorrosion adapté à l’ambiance du site (bord de mer, industrielle, rurale)',
    ],
    normes: [
      'Eurocode 1 — EN 1991-1-4 (actions du vent) et EN 1991-1-3 (charges de neige)',
      'Eurocode 3 (structures en acier) et Eurocode 9 (structures en aluminium)',
      'Règlement de construction parasismique marocain (RPS) pour les ouvrages concernés',
      'ISO 1461 — revêtements par galvanisation à chaud',
      'ISO 12944 — protection anticorrosion par systèmes de peinture, selon la catégorie de corrosivité',
    ],
    garantie: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans (structure) · garantie de pose Taqinor ${INSTALL_WARRANTY_YEARS} ans`,
    warranty: {
      years: STRUCTURE_WARRANTY_YEARS,
      note: `Garantie ${STRUCTURE_WARRANTY_YEARS} ans sur la structure ; garantie de pose et de main-d’œuvre Taqinor ${INSTALL_WARRANTY_YEARS} ans. Chaque composant conserve la garantie de son fabricant.`,
    },
    verifier: [
      'La note de calcul est signée par un bureau d’études structure, et cite la zone de vent et le site réels',
      'La vérification de la charpente existante est un document distinct de l’offre commerciale',
      'La catégorie de corrosivité retenue (ISO 12944) correspond à l’ambiance du site',
      'Le procès-verbal d’étanchéité de la couverture est prévu à la réception',
    ],
    faq: [
      {
        q: 'Ma charpente peut-elle supporter des panneaux ?',
        r: 'C’est la première question à instruire, avant toute offre. Les modules et leur structure ajoutent une charge permanente et modifient la prise au vent : seule une vérification de la charpente permet de répondre, et elle se documente.',
      },
      {
        q: 'Ombrière ou toiture : que choisir ?',
        r: 'L’ombrière libère la toiture et rend un service en plus (protection des véhicules), mais c’est un ouvrage neuf avec fondations. La toiture est moins coûteuse quand la charpente le permet. La capacité portante et le foncier disponible tranchent.',
      },
    ],
    pairsWith: ['Panneaux photovoltaïques', 'Protection & câblage'],
    datasheet: null,
    pdf: null,
    // Ombrière de parking — l'une des trois familles décrites par la fiche.
    // Domaine public (agent du DoE américain) : AUCUNE attribution due, donc
    // pas de `photoCredit` (on n'invente pas un crédit qui n'est pas exigé).
    photo: '/fiches/photos/ombriere-parking.jpg',
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
  'Structure & pose',
  'Protection & câblage',
  'Supervision & comptage',
  'Grands projets',
];

/**
 * LES 11 FAMILLES du découpage fondateur (2026-08-18), dans l'ordre où on les
 * raconte : 8 familles résidentielles puis 3 postes de grands projets. Chaque
 * famille pointe le ou les slugs qui la servent — `panneaux` et `onduleur`
 * gardent leurs fiches de MARQUE (le client doit lire les faits de SON
 * matériel), `structure` porte depuis le 18/08/2026 SES DEUX pages (le châssis
 * et les socles qui le lestent), les cinq autres familles résidentielles ont
 * une fiche unique.
 *
 * Cette table est la source de vérité du découpage : le test de catalogue la
 * confronte à `FICHES`, donc retirer une fiche sans toucher ici casse le test.
 */
export const FICHE_FAMILLES: readonly { id: string; libelle: string; slugs: readonly string[] }[] = [
  { id: 'panneaux', libelle: 'Panneaux', slugs: ['canadian-solar-710', 'jinko-710'] },
  { id: 'onduleur', libelle: 'Onduleur', slugs: ['onduleur-deye-hybride', 'onduleur-huawei-reseau'] },
  { id: 'batterie', libelle: 'Batterie', slugs: ['batterie-dyness'] },
  // Deux fiches depuis le 18/08/2026 : le CHÂSSIS et les SOCLES qui le lestent
  // — deux pages, une seule famille de devis (la ligne « Structures » et la
  // ligne « Socles » sont deux postes du même chapitre).
  { id: 'structure', libelle: 'Structure', slugs: ['structure-fixation', 'socles-lestage'] },
  { id: 'cablage', libelle: 'Câblage', slugs: ['cablage'] },
  { id: 'protection-dc', libelle: 'Protection DC', slugs: ['protection-dc'] },
  { id: 'protection-ac', libelle: 'Protection AC', slugs: ['protection-ac'] },
  { id: 'accessoires-pose', libelle: 'Accessoires de pose', slugs: ['accessoires-pose'] },
  { id: 'poste-mt-raccordement', libelle: 'Poste MT et raccordement', slugs: ['poste-mt-raccordement'] },
  { id: 'supervision-comptage', libelle: 'Supervision et comptage (grands projets)', slugs: ['supervision-comptage'] },
  {
    id: 'structures-grandes-installations',
    libelle: 'Structures pour grandes installations',
    slugs: ['structures-grandes-installations'],
  },
];

/**
 * ANCIEN SLUG → SLUG ACTUEL. Le découpage du 18/08 a éclaté
 * `tableau-protection-ac-dc` en deux fiches et renommé `accessoires-cablage`.
 * Des devis et des e-mails DÉJÀ ÉMIS portent les anciennes URL : elles ne
 * doivent jamais tomber en 404.
 *
 * DEUX PORTEURS, un seul dictionnaire :
 *  · ici, pour que `ficheBySlug` résolve un ancien slug côté code (proposition,
 *    page Équipement…) ;
 *  · `worker/redirects.mjs`, qui émet le 301 avant même qu'Astro voie la
 *    requête. `tests/redirect.test.ts` vérifie que les deux listes coïncident —
 *    ajouter un alias ici sans l'ajouter là-bas casse le test.
 *
 * Le coffret combiné « AC/DC » atterrit sur la fiche DC : c'est la moitié
 * spécifiquement photovoltaïque du poste, et elle renvoie vers la fiche AC.
 */
export const FICHE_ALIASES: Readonly<Record<string, string>> = {
  'tableau-protection-ac-dc': 'protection-dc',
  'accessoires-cablage': 'cablage',
};

/** Slug canonique d'une URL de fiche : l'alias résolu, ou le slug tel quel. */
export function resolveFicheSlug(slug: string | null | undefined): string {
  const s = String(slug ?? '').trim();
  return FICHE_ALIASES[s] ?? s;
}

export function fichesByCategorie(): { categorie: FicheCategorie; fiches: Fiche[] }[] {
  return FICHE_CATEGORIES
    .map((categorie) => ({ categorie, fiches: FICHES.filter((f) => f.categorie === categorie) }))
    .filter((g) => g.fiches.length > 0);
}

/** La fiche d'un slug — un ANCIEN slug est résolu par `FICHE_ALIASES`. */
export function ficheBySlug(slug: string): Fiche | undefined {
  const canonique = resolveFicheSlug(slug);
  return FICHES.find((f) => f.slug === canonique);
}

/**
 * Lien de téléchargement : la copie auto-hébergée si elle existe, sinon la
 * source officielle (fiche constructeur ou page de la norme). `null` quand
 * AUCUNE source officielle n'a été vérifiée pour ce poste — le bouton est
 * alors OMIS plutôt que de pointer vers un lien deviné.
 */
export function ficheDownloadHref(f: Fiche): string | null {
  return f.pdf ?? f.datasheet;
}

/**
 * « Se combine avec » (W326) : les fiches des catégories que `f.pairsWith`
 * référence, groupées par catégorie — pour un bloc de liens croisés en pied de
 * fiche produit (via RelatedLinks). Exclut toujours `f` lui-même.
 */
export function relatedFiches(f: Fiche): { categorie: FicheCategorie; fiches: Fiche[] }[] {
  const parCategorie = f.pairsWith
    .map((categorie) => ({
      categorie,
      fiches: FICHES.filter((other) => other.categorie === categorie && other.slug !== f.slug),
    }))
    .filter((g) => g.fiches.length > 0);

  // Les fiches SŒURS de la MÊME catégorie (protection DC ↔ AC, câblage ↔
  // accessoires de pose) : `pairsWith` ne peut pas les exprimer, elles sont
  // donc nommées slug par slug. Elles rejoignent leur propre groupe de
  // catégorie, ou en créent un si `pairsWith` ne l'a pas déjà produit.
  for (const slug of f.voirAussi ?? []) {
    const soeur = FICHES.find((other) => other.slug === slug && other.slug !== f.slug);
    if (!soeur) continue;
    const groupe = parCategorie.find((g) => g.categorie === soeur.categorie);
    if (groupe) {
      if (!groupe.fiches.some((x) => x.slug === soeur.slug)) groupe.fiches.push(soeur);
    } else {
      parCategorie.push({ categorie: soeur.categorie, fiches: [soeur] });
    }
  }
  return parCategorie;
}
