// QJW2 — LE REGISTRE DES CHAMPS DU TUNNEL « mon-toit ».
//
// POURQUOI CE FICHIER EXISTE. Le tunnel `mon-toit` vit en TROIS copies
// complètes (`src/pages/devis/mon-toit.astro`, `src/pages/en/…`,
// `src/pages/ar/…`), chacune avec sa propre fonction `buildBody()`. Les trois
// copies ont DIVERGÉ sans que rien ne le signale : la copie FR est aujourd'hui
// un SUPERSET strict — elle seule émet le bloc L-WEBT (`occupation_jour`, les
// 4 bascules d'équipement et leurs détails kW/créneau) et le jeton anti-fraude
// `appareilId`. Un visiteur anglophone ou arabophone remplit le même tunnel et
// ses réponses ne sont JAMAIS collectées.
//
// Ce module est la SOURCE UNIQUE DE VÉRITÉ de ce que le tunnel collecte : un
// tableau de descripteurs, dérivé en diffant les trois `buildBody` clé par clé
// sur la base de la copie FR (le superset). Il est livré SEUL — aucune page ne
// l'importe encore ; `corps.ts` (QJW3) le consomme, `i18n.ts` (QJW4) se clé
// dessus, la bascule des trois pages (QJW5) vient après.
//
// LA DISCIPLINE, RECOPIÉE VERBATIM DES TROIS PAGES : « nettoyer ou omettre,
// jamais fabriquer ». Une question qui n'a pas été posée est une clé ABSENTE du
// corps, jamais un défaut fabriqué. Concrètement : les booléens `equip_*` ne
// valent que `true` (jamais un `false` inventé pour une case décochée), un
// nombre non saisi est `undefined` (donc omis par `JSON.stringify`) et non un
// zéro, et un nombre RÉELLEMENT saisi à zéro ou négatif part tel quel — c'est
// `validateLead` (`src/lib/lead.ts`) qui le borne, pas ce registre.
//
// FORME DU REGISTRE. Les descripteurs sont déclarés dans un objet CLÉ PAR CLÉ
// (`CHAMPS_PAR_CLE`) puis aplatis en tableau (`CHAMPS_TUNNEL`). Ce détour a une
// seule raison, et elle est structurelle : `keyof typeof CHAMPS_PAR_CLE` donne
// l'UNION LITTÉRALE des clés du registre, sur laquelle QJW4 clé son `Record`
// de traductions — ajouter un champ sans ses trois traductions devient alors
// une erreur `tsc`, pas une omission silencieuse. L'ordre de déclaration est
// l'ordre d'émission des clés du corps (celui du littéral `buildBody()` FR).

import type { LeadModeId } from '../lead';

/** Les modes du tunnel dans lesquels une question peut être posée. */
export const MODES_TOUS: readonly LeadModeId[] = [
  'residentiel',
  'professionnel',
  'industriel',
  'commercial',
  'agricole',
];

/** Les deux profils « C&I » + l'alias historique — miroir d'`isProMode()`. */
export const MODES_PRO: readonly LeadModeId[] = ['professionnel', 'industriel', 'commercial'];

/**
 * Miroir pur d'`isProMode(mode)` des trois `.astro` : 'professionnel' reste
 * accepté comme alias de compatibilité (sessions en cours, anciens liens) même
 * si le site ne l'émet plus jamais.
 */
export function estModePro(mode: string): boolean {
  return (MODES_PRO as readonly string[]).includes(mode);
}

/** Les 6 paramètres de tracking repris de `sessionStorage` (capture first-touch). */
export const CLES_TRACKING = [
  'fbclid',
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
] as const;
export type CleTracking = (typeof CLES_TRACKING)[number];

/** Un repère de toiture (point unique posé par le visiteur sur la carte). */
export interface RepereToit {
  lat: number;
  lng: number;
}

/**
 * L'ÉTAT DU TUNNEL — l'objet simple que chaque page construit à partir de son
 * DOM avant d'appeler `construireCorps` (QJW3). Aucun type DOM ici : c'est ce
 * qui rend le registre et le constructeur de corps testables sans navigateur.
 *
 * Chaque champ porte la valeur BRUTE telle que la page la lit :
 * - une chaîne vide `''` = champ jamais rempli (helper `val()` des pages) ;
 * - `null` = nombre absent ou illisible (helper `num()` des pages) ;
 * - `false` = case décochée.
 * Le registre décide ensuite si cela s'émet ou s'omet — jamais la page.
 */
export interface EtatTunnel {
  // ——— identité + contact ———
  nomComplet: string;
  telephone: string;
  email: string;
  /** `val('mt-city')` — la ville/adresse saisie au clavier. */
  ville: string;
  /** La valeur de l'autocomplétion d'adresse. */
  adresseCarte: string;
  /** L'adresse de repli quand l'autocomplétion n'a pas démarré. */
  adresseSecours: string;
  consentement: boolean;
  /** Radio « Un conseiller peut m'appeler » cochée (sinon : WhatsApp uniquement). */
  appelAutorise: boolean;

  // ——— parcours ———
  mode: string;
  /**
   * `currentLang` — la locale ACTIVE. Les pages FR/AR la transmettent ; la page
   * EN passe `''` (`LEAD_LANGS` n'accepte que fr/ar, cf. WJ39) et la clé est
   * alors ABSENTE du corps — jamais une locale fabriquée.
   */
  languePreferee: string;

  // ——— facture résidentielle ———
  factureHiverMad: number | null;
  /** Le `<select>` de tranche (`mt-bill`), auto-dérivé du montant exact. */
  trancheFacture: string;

  // ——— facture professionnelle (C&I) ———
  /** La valeur saisie dans le panneau C&I ACTIF (industriel ou commercial). */
  factureProValeur: number | null;
  /** L'unité du panneau C&I actif : 'mad' ou 'kwh'. */
  factureProUnite: string;
  /**
   * Le tarif MAD/kWh des hypothèses du moteur — sert à dériver la tranche
   * quand la saisie est en kWh. `null` = tarif inconnu : on n'invente rien, la
   * tranche retombe sur le repli honnête (cf. `corps.ts`).
   */
  tarifProMadKwh: number | null;

  // ——— sous-panneau professionnel ———
  raisonSociale: string;
  tension: string;
  activite: string;
  categorieCommerciale: string;
  equipes: string;

  // ——— surface ———
  typeSurface: string;
  surfaceM2: number | null;

  // ——— sous-panneau agricole (pompage) ———
  sourceEau: string;
  uniteEau: string;
  profondeurM: number | null;
  hmtM: number | null;
  besoinEau: number | null;
  heuresPompage: number | null;
  culture: string;
  regionAgricole: string;
  surfaceHa: number | null;
  depenseCarburantMad: number | null;

  // ——— visite technique ———
  creneauVisitePartie: string;
  creneauVisiteSemaine: string;

  // ——— L-WEBT : « Affiner mon profil de consommation » (facultatif) ———
  occupationJour: string;
  equipChauffeEau: boolean;
  equipChauffeEauKw: number | null;
  equipChauffeEauCreneau: string;
  equipVoitureElectrique: boolean;
  equipVeKmSemaine: number | null;
  equipVeChargeurKw: number | null;
  equipVeCreneau: string;
  equipClim: boolean;
  equipClimPieces: number | null;
  equipClimKw: number | null;
  equipClimCreneau: string;
  equipPiscine: boolean;
  equipPiscinePompeKw: number | null;
  equipPiscineHeuresJour: number | null;
  equipPiscineCreneau: string;

  // ——— artefacts de session (générés par la page, jamais saisis) ———
  clientRef: string;
  idempotencyKey: string;
  eventId: string;
  /** Jeton anti-fraude d'appareil ; `''` quand le stockage est indisponible. */
  appareilId: string;
  /** Les chiffres EXACTEMENT tels qu'affichés dans le document d'estimation. */
  estimationAffichee: Record<string, number | string> | null;
  tracking: Partial<Record<CleTracking, string>>;
  repereToit: RepereToit | null;
  contourToit: Array<[number, number]>;

  // ——— anti-spam ———
  honeypot: string;
}

/**
 * UN DESCRIPTEUR DE CHAMP.
 *
 * - `cle`       : identifiant stable du champ dans le registre. C'est lui qui
 *                 clé la couche i18n (QJW4).
 * - `webhookKey`: le nom EXACT de la clé émise dans le corps envoyé à
 *                 `/api/capture-lead`. Le contrat réseau est ce nom-là, pas
 *                 `cle` — les deux ne coïncident pas partout (le bloc L-WEBT
 *                 est délibérément en snake_case : ce sont les noms des
 *                 colonnes `crm.Lead` que le webhook lit sans traduction).
 * - `domId`     : l'`id` de l'élément qui porte la réponse dans les trois
 *                 `.astro`. `null` quand la valeur ne vient PAS d'un élément
 *                 identifié (état interne, groupe de cartes désigné par une
 *                 classe, carte, jeton de session). Le test de parité (QJW6)
 *                 exige que tout `domId` non nul existe dans les TROIS sources.
 * - `modes`     : les modes où la QUESTION EST POSÉE. Documentaire : depuis la
 *                 coupe fondateur du 18/08/2026 la règle d'émission est « toute
 *                 valeur saisie non vide part », indépendamment du mode actif
 *                 au moment de l'envoi (un visiteur qui décrit son site
 *                 industriel puis revient sur « commercial » ne perd rien). Les
 *                 rares champs qui GARDENT un vrai gate portent ce gate dans
 *                 `lire`, seul endroit qui décide de l'émission.
 * - `lire`      : extraction PURE depuis l'état, gate d'émission compris.
 *                 Rendre `undefined` = « la question n'a pas été posée ».
 * - `nettoyer`  : normalisation PURE de la valeur brute. Rendre `undefined` =
 *                 OMETTRE la clé. Ne fabrique JAMAIS une valeur absente.
 * - `requis`    : la clé est TOUJOURS présente dans le corps, même vide ou
 *                 nulle, parce que `validateLead` doit pouvoir la juger et
 *                 rendre une erreur de champ. Invariant vérifié par les tests :
 *                 pour un descripteur `requis`, `nettoyer` ne rend JAMAIS
 *                 `undefined`.
 */
export interface DescripteurChamp {
  readonly cle: string;
  readonly webhookKey: string;
  readonly domId: string | null;
  readonly modes: readonly LeadModeId[];
  readonly lire: (etat: EtatTunnel) => unknown;
  readonly nettoyer: (brut: unknown) => unknown;
  readonly requis: boolean;
}

/** Un descripteur tel qu'il est déclaré : sa clé est le nom de la propriété. */
type DescripteurSansCle = Omit<DescripteurChamp, 'cle'>;

// ——— nettoyeurs réutilisables ———————————————————————————————————————————
// Chacun applique la discipline « nettoyer ou omettre, jamais fabriquer ».

/** Chaîne TOUJOURS émise (champ que `validateLead` doit pouvoir juger). */
const chaineRequise = (v: unknown): string => (typeof v === 'string' ? v : '');

/** Chaîne émise seulement si non vide — sinon la clé est ABSENTE. */
const chaineOuOmise = (v: unknown): string | undefined =>
  typeof v === 'string' && v !== '' ? v : undefined;

/** Booléen TOUJOURS émis (consentement, préférence de contact). */
const booleenRequis = (v: unknown): boolean => v === true;

/**
 * Booléen émis UNIQUEMENT quand il vaut `true`. Une case décochée est une
 * question sans réponse : la clé est ABSENTE, jamais un `false` fabriqué.
 */
const vraiOuOmis = (v: unknown): true | undefined => (v === true ? true : undefined);

/**
 * Nombre émis tel quel s'il est fini — ZÉRO ET NÉGATIF COMPRIS : ce sont des
 * réponses réelles, c'est `validateLead` qui les borne (`cleanBoundedSignedNumber`
 * accepte le signe et le zéro sans jamais inventer une valeur manquante).
 * `null` / absent / `NaN` → clé omise.
 */
const nombreOuOmis = (v: unknown): number | undefined =>
  typeof v === 'number' && Number.isFinite(v) ? v : undefined;

/**
 * Nombre TOUJOURS émis, `null` quand il est absent. Reproduit à l'identique
 * `factureHiver: num('mt-facture-hiver')` des trois pages : la clé est présente
 * avec `null`, ce que `validateLead` distingue d'une clé absente.
 */
const nombreOuNul = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** L'adresse retenue : saisie clavier, sinon autocomplétion, sinon repli. */
export function adresseRetenue(etat: EtatTunnel): string {
  return (etat.ville || etat.adresseCarte.trim() || etat.adresseSecours.trim() || '').trim();
}

// ——— les descripteurs, dans l'ordre d'émission ————————————————————————

const G_IDENTITE = {
  nomComplet: {
    webhookKey: 'fullName',
    domId: 'mt-name',
    modes: MODES_TOUS,
    lire: (e) => e.nomComplet,
    nettoyer: chaineRequise,
    requis: true,
  },
  telephone: {
    webhookKey: 'phone',
    domId: 'mt-phone',
    modes: MODES_TOUS,
    lire: (e) => e.telephone,
    nettoyer: chaineRequise,
    requis: true,
  },
  ville: {
    webhookKey: 'city',
    domId: 'mt-city',
    modes: MODES_TOUS,
    lire: adresseRetenue,
    nettoyer: chaineRequise,
    requis: true,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_FACTURE = {
  /**
   * La tranche est TOUJOURS cohérente avec ce qui a piloté l'estimation
   * affichée : résidentiel = le `<select>` (auto-dérivé du montant exact) ;
   * C&I = dérivée de la conso saisie ; agricole = plus requise (`lead.ts`,
   * mode 'agricole'). La dérivation C&I a besoin du catalogue de tranches et
   * vit donc dans `corps.ts` (`trancheProDepuisEtat`), qui SURCHARGE ce `lire`
   * pour les profils pro — le registre reste sans dépendance métier.
   */
  trancheFacture: {
    webhookKey: 'billRange',
    domId: 'mt-bill',
    modes: ['residentiel'],
    lire: (e) => (estModePro(e.mode) || e.mode === 'agricole' ? '' : e.trancheFacture),
    nettoyer: chaineRequise,
    requis: true,
  },
  /**
   * DÉRIVÉ pour tous les profils : plus aucun écran ne pose la question depuis
   * la coupe fondateur du 18/08, mais `validateLead` l'exige pour toute
   * soumission `mon-toit`. On dérive de VRAIES réponses quand il y en a
   * (bac acier → hangar, terrasse → toit plat) et on retombe sinon sur
   * 'autre', le bucket HONNÊTE : jamais une toiture précise inventée pour un
   * visiteur qu'on n'a pas interrogé.
   */
  typeToiture: {
    webhookKey: 'roofType',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => {
      if (!estModePro(e.mode)) return 'autre';
      if (e.typeSurface === 'bac_acier') return 'hangar';
      if (e.typeSurface === 'terrasse') return 'toit_plat';
      return 'autre';
    },
    nettoyer: chaineRequise,
    requis: true,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_CONSENTEMENT = {
  consentement: {
    webhookKey: 'consent',
    domId: 'mt-consent',
    modes: MODES_TOUS,
    lire: (e) => e.consentement,
    nettoyer: booleenRequis,
    requis: true,
  },
  /** Dérivé de la préférence explicite pour ne rien casser côté CRM/webhook. */
  whatsappSeulement: {
    webhookKey: 'whatsappOptIn',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => !e.appelAutorise,
    nettoyer: booleenRequis,
    requis: true,
  },
  preferenceContact: {
    webhookKey: 'contactPreference',
    domId: 'mt-contact-phone',
    modes: MODES_TOUS,
    lire: (e) => (e.appelAutorise ? 'phone_ok' : 'whatsapp_only'),
    nettoyer: chaineRequise,
    requis: true,
  },
  email: {
    webhookKey: 'email',
    domId: 'mt-email',
    modes: MODES_TOUS,
    lire: (e) => e.email,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  factureHiver: {
    webhookKey: 'factureHiver',
    domId: 'mt-facture-hiver',
    modes: ['residentiel'],
    lire: (e) => e.factureHiverMad,
    nettoyer: nombreOuNul,
    requis: true,
  },
  adresse: {
    webhookKey: 'adresse',
    domId: null,
    modes: MODES_TOUS,
    lire: adresseRetenue,
    nettoyer: chaineRequise,
    requis: true,
  },
  mode: {
    webhookKey: 'mode',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.mode,
    nettoyer: chaineRequise,
    requis: true,
  },
  languePreferee: {
    webhookKey: 'langue_preferee',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.languePreferee,
    nettoyer: chaineOuOmise,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_SESSION = {
  /**
   * Référence courte affichée par l'écran de succès — échoée telle quelle,
   * jamais une clé d'unicité serveur (cf. `lib/lead.ts`).
   */
  clientRef: {
    webhookKey: 'clientRef',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.clientRef,
    nettoyer: chaineRequise,
    requis: true,
  },
  /**
   * Jetons de DÉDOUBLONNAGE (CRM + Meta CAPI), stables pour toute la session
   * de saisie : un renvoi (échec réseau, double-clic, retour arrière) porte le
   * MÊME couple.
   */
  idempotencyKey: {
    webhookKey: 'idempotencyKey',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.idempotencyKey,
    nettoyer: chaineRequise,
    requis: true,
  },
  eventId: {
    webhookKey: 'eventId',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.eventId,
    nettoyer: chaineRequise,
    requis: true,
  },
  /**
   * LANE T-WEB — additive, jamais bloquante : stockage indisponible → `''` →
   * clé ABSENTE, jamais une chaîne vide envoyée.
   */
  appareilId: {
    webhookKey: 'appareilId',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.appareilId,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  /**
   * Préférence de créneau de visite technique (facultative, STATIQUE). La
   * réponse vient d'un GROUPE DE CARTES (`.mt-visit-part` / `.mt-visit-week`),
   * pas d'un élément portant un `id` : `domId` reste donc `null` — ce champ
   * décrit un id d'élément, jamais un sélecteur de classe.
   */
  creneauVisitePartie: {
    webhookKey: 'visitWindowPart',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.creneauVisitePartie,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  creneauVisiteSemaine: {
    webhookKey: 'visitWindowWeek',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.creneauVisiteSemaine,
    nettoyer: chaineOuOmise,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_PRO = {
  /**
   * Facultatif, additif, jamais bloquant : le champ part même si le mode a
   * changé depuis la saisie (`validateLead` juge chaque clé indépendamment).
   */
  raisonSociale: {
    webhookKey: 'raisonSociale',
    domId: 'mt-raison-sociale',
    modes: MODES_PRO,
    lire: (e) => e.raisonSociale,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  /**
   * `tension` et `activite` ont un DÉFAUT VISIBLE ('bt' / 'day') : elles ne
   * partent que si un profil C&I est actif — sinon on émettrait une donnée que
   * le visiteur n'a jamais choisie.
   */
  tensionRaccordement: {
    webhookKey: 'tensionRaccordement',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => (estModePro(e.mode) ? e.tension : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  profilActivite: {
    webhookKey: 'activityProfile',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => (estModePro(e.mode) ? e.activite : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  typeSurface: {
    webhookKey: 'surfaceType',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => e.typeSurface,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  surfaceM2: {
    webhookKey: 'surfaceM2',
    domId: 'mt-surface-m2',
    modes: MODES_PRO,
    lire: (e) => e.surfaceM2,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /**
   * La conso C&I vient du panneau ACTIF ; l'unité choisie décide laquelle des
   * deux clés part — jamais les deux, jamais une conversion inventée.
   */
  proMensuelKwh: {
    webhookKey: 'proMonthlyKwh',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => (e.factureProUnite === 'kwh' ? e.factureProValeur : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  proMensuelMad: {
    webhookKey: 'proMonthlyMad',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => (e.factureProUnite === 'mad' ? e.factureProValeur : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /** Hôtel ≠ bureau à facture égale : la catégorie n'a de sens qu'en commercial. */
  categorieCommerciale: {
    webhookKey: 'categorieCommerciale',
    domId: null,
    modes: ['commercial'],
    lire: (e) => (e.mode === 'commercial' ? e.categorieCommerciale : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  /** Les ÉQUIPES plafonnent honnêtement l'autoconsommation dans `estimatePro`. */
  equipes: {
    webhookKey: 'equipes',
    domId: null,
    modes: ['industriel'],
    lire: (e) => e.equipes,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  /**
   * `surface_toiture_m2` = surface de TOIT au sens strict (le backend distingue
   * le sol) : ne l'émettre que pour une VRAIE toiture. Ombrière et terrain sont
   * décrits par leurs booléens — jamais une fausse toiture. Le gate porte sur
   * le TYPE DE SURFACE (sémantique), pas sur le mode courant.
   */
  surfaceToitureM2: {
    webhookKey: 'surfaceToitureM2',
    domId: null,
    modes: MODES_PRO,
    lire: (e) =>
      e.typeSurface === 'bac_acier' || e.typeSurface === 'terrasse' ? e.surfaceM2 : undefined,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  ombriere: {
    webhookKey: 'ombriere',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => e.typeSurface === 'ombriere' || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
  terrain: {
    webhookKey: 'terrain',
    domId: null,
    modes: MODES_PRO,
    lire: (e) => e.typeSurface === 'terrain' || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_AGRICOLE = {
  sourceEau: {
    webhookKey: 'waterSource',
    domId: null,
    modes: ['agricole'],
    lire: (e) => e.sourceEau,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  profondeurM: {
    webhookKey: 'profondeurM',
    domId: 'mt-profondeur',
    modes: ['agricole'],
    lire: (e) => e.profondeurM,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  hmtM: {
    webhookKey: 'hmtM',
    domId: 'mt-hmt',
    modes: ['agricole'],
    lire: (e) => e.hmtM,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /**
   * Un SEUL champ de saisie (`mt-water-need`) pour deux clés : l'unité choisie
   * décide laquelle part. Jamais une conversion fabriquée entre les deux.
   */
  debitM3h: {
    webhookKey: 'debitM3h',
    domId: 'mt-water-need',
    modes: ['agricole'],
    lire: (e) => (e.uniteEau === 'm3h' ? e.besoinEau : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  besoinM3j: {
    webhookKey: 'besoinM3j',
    domId: 'mt-water-need',
    modes: ['agricole'],
    lire: (e) => (e.uniteEau === 'm3j' ? e.besoinEau : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /**
   * LE SEUL champ qui GARDE un gate de mode, et c'est délibéré : les autres
   * sont des saisies vides par défaut, celui-ci est un
   * `<input type="range" value="7">` (#mt-heures-pompage) dont la `.value`
   * vaut « 7 » AVANT toute interaction. Sans le gate, un lead résidentiel
   * transporterait « 7 h/j » que personne n'a saisi et le CRM l'afficherait
   * comme une réponse du visiteur sur une villa.
   */
  heuresPompage: {
    webhookKey: 'heuresPompage',
    domId: 'mt-heures-pompage',
    modes: ['agricole'],
    lire: (e) => (e.mode === 'agricole' ? e.heuresPompage : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  culture: {
    webhookKey: 'culture',
    domId: 'mt-culture',
    modes: ['agricole'],
    lire: (e) => e.culture,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  /**
   * Région agronomique (8 zones FAO). Elle pilote le moteur eau DE CE TUNNEL
   * (`lib/agronomy.ts`, aperçu d'estimation en direct) et voyage au webhook par
   * compatibilité ascendante — `lib/lead.ts` la valide et la transporte, mais
   * `crm/webhooks.py _extract_web_questionnaire` ne la PERSISTE pas encore.
   */
  regionAgricole: {
    webhookKey: 'regionAgricole',
    domId: null,
    modes: ['agricole'],
    lire: (e) => e.regionAgricole,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  surfaceHa: {
    webhookKey: 'surfaceHa',
    domId: 'mt-surface-ha',
    modes: ['agricole'],
    lire: (e) => e.surfaceHa,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /** Seule la DÉPENSE carburant alimente l'économie calculée. */
  depenseCarburantMad: {
    webhookKey: 'fuelSpendMad',
    domId: 'mt-fuel-spend',
    modes: ['agricole'],
    lire: (e) => e.depenseCarburantMad,
    nettoyer: nombreOuOmis,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_ESTIMATION = {
  /**
   * EXACTEMENT les chiffres affichés dans le document d'estimation : le
   * conseiller CRM voit ce que le client a vu — jamais plus.
   */
  estimationAffichee: {
    webhookKey: 'estimateShown',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.estimationAffichee,
    nettoyer: (v) => (v != null && typeof v === 'object' ? v : undefined),
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

/**
 * LE BLOC L-WEBT — « Affiner mon profil de consommation » (facultatif,
 * repliable). Les noms de clé sont en SNAKE_CASE délibérément : seule exception
 * à la convention camelCase du corps, ce sont les noms EXACTS des colonnes
 * `crm.Lead` (`occupation_jour`, `equip_piscine`, …) que
 * `webhooks.py _extract_web_questionnaire` lit directement, sans traduction.
 *
 * Case décochée = question jamais posée : la clé est ABSENTE, jamais un booléen
 * `false` fabriqué. Chaque détail (kW, pièces, km, heures, créneau) est GATÉ sur
 * sa case parente : jamais de saisie fantôme héritée d'une case décochée après
 * coup.
 */
const G_LWEBT = {
  occupationJour: {
    webhookKey: 'occupation_jour',
    domId: 'mt-occupation-jour',
    modes: ['residentiel'],
    lire: (e) => e.occupationJour,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  equipChauffeEau: {
    webhookKey: 'equip_chauffe_eau_electrique',
    domId: 'mt-equip-chauffe-eau',
    modes: ['residentiel'],
    lire: (e) => e.equipChauffeEau || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
  equipVoitureElectrique: {
    webhookKey: 'equip_voiture_electrique',
    domId: 'mt-equip-ve',
    modes: ['residentiel'],
    lire: (e) => e.equipVoitureElectrique || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
  equipVeKmSemaine: {
    webhookKey: 'equip_ve_km_semaine',
    domId: 'mt-equip-ve-km',
    modes: ['residentiel'],
    lire: (e) => (e.equipVoitureElectrique ? e.equipVeKmSemaine : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipClim: {
    webhookKey: 'equip_clim',
    domId: 'mt-equip-clim',
    modes: ['residentiel'],
    lire: (e) => e.equipClim || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
  equipClimPieces: {
    webhookKey: 'equip_clim_pieces',
    domId: 'mt-equip-clim-pieces',
    modes: ['residentiel'],
    lire: (e) => (e.equipClim ? e.equipClimPieces : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipPiscine: {
    webhookKey: 'equip_piscine',
    domId: 'mt-equip-piscine',
    modes: ['residentiel'],
    lire: (e) => e.equipPiscine || undefined,
    nettoyer: vraiOuOmis,
    requis: false,
  },
  equipPiscinePompeKw: {
    webhookKey: 'equip_piscine_pompe_kw',
    domId: 'mt-equip-piscine-kw',
    modes: ['residentiel'],
    lire: (e) => (e.equipPiscine ? e.equipPiscinePompeKw : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipChauffeEauKw: {
    webhookKey: 'equip_chauffe_eau_kw',
    domId: 'mt-equip-chauffe-eau-kw',
    modes: ['residentiel'],
    lire: (e) => (e.equipChauffeEau ? e.equipChauffeEauKw : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipChauffeEauCreneau: {
    webhookKey: 'equip_chauffe_eau_creneau',
    domId: 'mt-equip-chauffe-eau-creneau',
    modes: ['residentiel'],
    lire: (e) => (e.equipChauffeEau ? e.equipChauffeEauCreneau : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  equipVeChargeurKw: {
    webhookKey: 'equip_ve_chargeur_kw',
    domId: 'mt-equip-ve-kw',
    modes: ['residentiel'],
    lire: (e) => (e.equipVoitureElectrique ? e.equipVeChargeurKw : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipVeCreneau: {
    webhookKey: 'equip_ve_creneau',
    domId: 'mt-equip-ve-creneau',
    modes: ['residentiel'],
    lire: (e) => (e.equipVoitureElectrique ? e.equipVeCreneau : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  equipClimKw: {
    webhookKey: 'equip_clim_kw',
    domId: 'mt-equip-clim-kw',
    modes: ['residentiel'],
    lire: (e) => (e.equipClim ? e.equipClimKw : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipClimCreneau: {
    webhookKey: 'equip_clim_creneau',
    domId: 'mt-equip-clim-creneau',
    modes: ['residentiel'],
    lire: (e) => (e.equipClim ? e.equipClimCreneau : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
  equipPiscineHeuresJour: {
    webhookKey: 'equip_piscine_heures_jour',
    domId: 'mt-equip-piscine-heures',
    modes: ['residentiel'],
    lire: (e) => (e.equipPiscine ? e.equipPiscineHeuresJour : undefined),
    nettoyer: nombreOuOmis,
    requis: false,
  },
  equipPiscineCreneau: {
    webhookKey: 'equip_piscine_creneau',
    domId: 'mt-equip-piscine-creneau',
    modes: ['residentiel'],
    lire: (e) => (e.equipPiscine ? e.equipPiscineCreneau : undefined),
    nettoyer: chaineOuOmise,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_ANTISPAM = {
  /**
   * Honeypot : vide pour tout visiteur humain (champ masqué hors écran, jamais
   * rempli sciemment), rejeté côté serveur si non vide. TOUJOURS émis — son
   * absence serait elle-même un signal exploitable.
   */
  honeypot: {
    webhookKey: 'website_url',
    domId: 'mt-hp',
    modes: MODES_TOUS,
    lire: (e) => e.honeypot,
    nettoyer: chaineRequise,
    requis: true,
  },
} satisfies Record<string, DescripteurSansCle>;

/**
 * fbclid + UTM repris de `sessionStorage` (capture first-touch du Layout) :
 * seules les clés PRÉSENTES sont jointes — un visiteur sans paramètre de
 * tracking envoie un corps identique à avant (convention « absent plutôt que
 * vide »). Les six sont écrites une à une, jamais générées : le contrat réseau
 * doit rester lisible à l'œil dans ce fichier.
 */
const G_TRACKING = {
  fbclid: {
    webhookKey: 'fbclid',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.fbclid,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  utm_source: {
    webhookKey: 'utm_source',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.utm_source,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  utm_medium: {
    webhookKey: 'utm_medium',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.utm_medium,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  utm_campaign: {
    webhookKey: 'utm_campaign',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.utm_campaign,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  utm_content: {
    webhookKey: 'utm_content',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.utm_content,
    nettoyer: chaineOuOmise,
    requis: false,
  },
  utm_term: {
    webhookKey: 'utm_term',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.tracking.utm_term,
    nettoyer: chaineOuOmise,
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

const G_CARTE = {
  /** Repère FACULTATIF : joint s'il existe, ne BLOQUE jamais sans lui. */
  repereToit: {
    webhookKey: 'roofPoint',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.repereToit ?? undefined,
    nettoyer: (v) => (v != null && typeof v === 'object' ? v : undefined),
    requis: false,
  },
  gpsLat: {
    webhookKey: 'gpsLat',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.repereToit?.lat,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  gpsLng: {
    webhookKey: 'gpsLng',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => e.repereToit?.lng,
    nettoyer: nombreOuOmis,
    requis: false,
  },
  /**
   * Un contour n'est un polygone qu'à partir de 3 sommets : en dessous ce n'est
   * pas un tracé « à compléter », c'est une clé ABSENTE.
   */
  contourToit: {
    webhookKey: 'roofOutline',
    domId: null,
    modes: MODES_TOUS,
    lire: (e) => (e.contourToit.length >= 3 ? e.contourToit : undefined),
    nettoyer: (v) => (Array.isArray(v) && v.length >= 3 ? v : undefined),
    requis: false,
  },
} satisfies Record<string, DescripteurSansCle>;

/**
 * LE REGISTRE, clé par clé. L'ordre de déclaration est l'ordre d'émission des
 * clés du corps — celui du littéral `buildBody()` de la page FR avant bascule.
 */
export const CHAMPS_PAR_CLE = {
  ...G_IDENTITE,
  ...G_FACTURE,
  ...G_CONSENTEMENT,
  ...G_SESSION,
  ...G_PRO,
  ...G_AGRICOLE,
  ...G_ESTIMATION,
  ...G_LWEBT,
  ...G_ANTISPAM,
  ...G_TRACKING,
  ...G_CARTE,
};

/**
 * L'UNION LITTÉRALE des clés du registre. C'est elle qui rend la couche i18n
 * (QJW4) exhaustive à la compilation : un `Record<CleChamp, string>` incomplet
 * est une erreur `tsc`, pas une omission silencieuse.
 */
export type CleChamp = keyof typeof CHAMPS_PAR_CLE;

/** Toutes les clés du registre, dans l'ordre d'émission. */
export const CLES_CHAMPS = Object.keys(CHAMPS_PAR_CLE) as CleChamp[];

/**
 * LE REGISTRE APLATI — la source unique de vérité de ce que le tunnel
 * collecte, telle que `corps.ts` la parcourt.
 */
export const CHAMPS_TUNNEL: readonly DescripteurChamp[] = CLES_CHAMPS.map((cle) => ({
  cle,
  ...CHAMPS_PAR_CLE[cle],
}));

/** Les `domId` non nuls, dédoublonnés — surface vérifiée par le test de parité. */
export const DOM_IDS_TUNNEL: readonly string[] = Array.from(
  new Set(CHAMPS_TUNNEL.map((c) => c.domId).filter((id): id is string => id != null)),
);

/**
 * Un état vide — toutes les questions sans réponse. Sert de base aux tests et
 * aux adaptateurs de page : partir de là garantit qu'un champ oublié reste une
 * réponse ABSENTE plutôt qu'un `undefined` qui traverse une lecture.
 */
export function etatVide(): EtatTunnel {
  return {
    nomComplet: '',
    telephone: '',
    email: '',
    ville: '',
    adresseCarte: '',
    adresseSecours: '',
    consentement: false,
    appelAutorise: false,
    mode: '',
    languePreferee: '',
    factureHiverMad: null,
    trancheFacture: '',
    factureProValeur: null,
    factureProUnite: '',
    tarifProMadKwh: null,
    raisonSociale: '',
    tension: '',
    activite: '',
    categorieCommerciale: '',
    equipes: '',
    typeSurface: '',
    surfaceM2: null,
    sourceEau: '',
    uniteEau: '',
    profondeurM: null,
    hmtM: null,
    besoinEau: null,
    heuresPompage: null,
    culture: '',
    regionAgricole: '',
    surfaceHa: null,
    depenseCarburantMad: null,
    creneauVisitePartie: '',
    creneauVisiteSemaine: '',
    occupationJour: '',
    equipChauffeEau: false,
    equipChauffeEauKw: null,
    equipChauffeEauCreneau: '',
    equipVoitureElectrique: false,
    equipVeKmSemaine: null,
    equipVeChargeurKw: null,
    equipVeCreneau: '',
    equipClim: false,
    equipClimPieces: null,
    equipClimKw: null,
    equipClimCreneau: '',
    equipPiscine: false,
    equipPiscinePompeKw: null,
    equipPiscineHeuresJour: null,
    equipPiscineCreneau: '',
    clientRef: '',
    idempotencyKey: '',
    eventId: '',
    appareilId: '',
    estimationAffichee: null,
    tracking: {},
    repereToit: null,
    contourToit: [],
    honeypot: '',
  };
}
