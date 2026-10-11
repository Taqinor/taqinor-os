/**
 * LANE Q-B — Logique PURE du questionnaire client public (« remplissez chez
 * vous, à votre rythme »).
 *
 * Aucune dépendance DOM ni réseau : parsing défensif de la réponse GET,
 * construction/sanitisation du corps POST (par SECTION), petites listes
 * fermées et helpers de validation locaux à ce module (le fichier reste
 * autonome — même discipline « jamais bloquant, jamais un défaut inventé »
 * que src/lib/lead.ts, mais SANS en dépendre : cette page vit dans sa propre
 * lane file-disjointe).
 *
 * Contrat backend (lane parallèle, verbatim) :
 *   GET  /api/django/crm/public/questionnaire/<token>/
 *     → { entreprise, prenom, sections: SectionId[], prefill: {champ: valeur|null},
 *         repondu: {section: true}, interne?: true }
 *   POST même URL, PAR SECTION :
 *     { section, reponses: {...}, photo?: "data:image/jpeg;base64,…" }
 *     → { ok: true, enregistrees: [...] } ; 404 générique si token invalide/expiré.
 *
 * ADDENDUM (ordre fondateur, en cours de lane) — un jeton d'APERÇU INTERNE
 * (le commercial relit le questionnaire depuis l'ERP) fait porter `interne:
 * true` par le GET : la page affiche alors tous les champs DÉSACTIVÉS, sans
 * barre de progression, et n'émet plus aucun POST (le backend le refuserait
 * de toute façon — la page ne le tente même pas).
 */

// ── Sections ─────────────────────────────────────────────────────────────

/**
 * Whitelist ET ordre d'affichage — miroir EXACT de
 * `crm.QuestionnaireLien.SECTIONS_CLES` (le serveur reste la source de
 * vérité : la page affiche `data.sections` dans l'ordre reçu).
 *
 * ORDRE (recherche 25/08/2026) — engagement croissant, sensible en dernier :
 * occupation/équipements (une tape) → énergie (un chiffre lu sur la facture)
 * → toiture/GPS (estimer une surface, accorder une permission) → les trois
 * photos (effort physique) → coordonnées (données personnelles, TOUJOURS en
 * dernier). L'ancien ordre commençait par `contact` : exactement l'inverse.
 */
export const QUESTIONNAIRE_SECTIONS = [
  'occupation',
  'equipements',
  'energie',
  'pompage',
  // CIW406 — sections du lead PRO (commercial / industriel), contrat CIQ400
  // `questionnaire_lead.json` (`segment_pro`) : le serveur ne les sert qu'à un
  // lead pro, et ne lui sert JAMAIS occupation / équipements / toiture / énergie.
  'reseau',
  'activite',
  'toiture',
  'site',
  'gps',
  'photo_facture',
  'photo_compteur',
  'photo_tableau',
  'photo_pompe',
  'photo_forage',
  'photo_factures',
  'photo_poste',
  'societe',
  'contact',
] as const;
export type QuestionnaireSectionId = (typeof QUESTIONNAIRE_SECTIONS)[number];

export function isQuestionnaireSectionId(v: unknown): v is QuestionnaireSectionId {
  return typeof v === 'string' && (QUESTIONNAIRE_SECTIONS as readonly string[]).includes(v);
}

export function isPhotoSection(section: QuestionnaireSectionId): boolean {
  return (
    section === 'photo_facture' ||
    section === 'photo_compteur' ||
    section === 'photo_tableau' ||
    section === 'photo_pompe' ||
    section === 'photo_forage' ||
    section === 'photo_factures' ||
    section === 'photo_poste'
  );
}

/** Libellés fr/en/ar + pictogramme — affichage seul, jamais lu par la logique. */
export interface SectionMeta {
  icon: string;
  title: { fr: string; en: string; ar: string };
}
export const SECTION_META: Record<QuestionnaireSectionId, SectionMeta> = {
  contact: { icon: '📇', title: { fr: 'Coordonnées', en: 'Contact details', ar: 'معلومات التواصل' } },
  gps: { icon: '📍', title: { fr: 'Position GPS', en: 'GPS location', ar: 'الموقع الجغرافي' } },
  energie: { icon: '⚡', title: { fr: 'Énergie', en: 'Energy', ar: 'الطاقة' } },
  photo_facture: { icon: '🧾', title: { fr: 'Photo de la facture', en: 'Photo of your bill', ar: 'صورة الفاتورة' } },
  photo_compteur: { icon: '🔢', title: { fr: 'Photo du compteur', en: 'Photo of the meter', ar: 'صورة العداد' } },
  photo_tableau: { icon: '🔌', title: { fr: 'Photo du tableau électrique', en: 'Photo of the electrical panel', ar: 'صورة اللوحة الكهربائية' } },
  toiture: { icon: '🏠', title: { fr: 'Toiture', en: 'Roof', ar: 'السطح' } },
  pompage: { icon: '💧', title: { fr: 'Votre pompage', en: 'Your water pumping', ar: 'الضخ والسقي' } },
  photo_pompe: { icon: '⚙️', title: { fr: 'Photo de la pompe (plaque)', en: 'Photo of the pump (nameplate)', ar: 'صورة المضخة (اللوحة)' } },
  photo_forage: { icon: '🕳️', title: { fr: 'Photo du forage', en: 'Photo of the borehole', ar: 'صورة البئر' } },
  reseau: { icon: '🔌', title: { fr: 'Votre raccordement et votre consommation', en: 'Your grid connection and consumption', ar: 'الربط بالشبكة والاستهلاك' } },
  activite: { icon: '🏭', title: { fr: 'Votre activité et vos horaires', en: 'Your activity and opening hours', ar: 'نشاطكم وأوقات العمل' } },
  site: { icon: '📐', title: { fr: 'La surface disponible', en: 'The available surface', ar: 'المساحة المتاحة' } },
  societe: { icon: '🏢', title: { fr: 'Votre société', en: 'Your company', ar: 'شركتكم' } },
  photo_factures: { icon: '🧾', title: { fr: 'Les 12 dernières factures', en: 'Your last 12 bills', ar: 'آخر 12 فاتورة' } },
  photo_poste: { icon: '🔢', title: { fr: 'Compteur / poste de livraison', en: 'Meter / delivery substation', ar: 'العداد / محطة التسليم' } },
  occupation: { icon: '🕒', title: { fr: 'Occupation du logement', en: 'Home occupancy', ar: 'شغل المنزل' } },
  equipements: { icon: '🧰', title: { fr: 'Équipements', en: 'Appliances', ar: 'التجهيزات' } },
};

// ── Contrat GET ──────────────────────────────────────────────────────────

export interface QuestionnaireGetResponse {
  entreprise: string;
  prenom: string;
  /** Sous-ensemble ACTIF, dans l'ordre voulu par le backend (source de vérité de l'ordre d'affichage). */
  sections: QuestionnaireSectionId[];
  /**
   * GRAIN FIN (ordre fondateur 25/08/2026 « on ne redemande JAMAIS une donnée
   * déjà connue ») — par section, les SEULES colonnes que la page a le droit
   * de dessiner. Une colonne connue du lead y figure (elle revient
   * pré-remplie, donc confirmable) ; une colonne vide qu'une autre donnée
   * connue couvre déjà en est absente (l'adresse d'un client qui a donné son
   * GPS) et sa question disparaît.
   *
   * Une section ABSENTE de cette carte n'est PAS restreinte : on dessine tout.
   * C'est le repli volontaire face à un backend plus ancien — mieux vaut une
   * question de trop qu'un champ caché par erreur.
   */
  champs: Partial<Record<QuestionnaireSectionId, string[]>>;
  prefill: Record<string, unknown>;
  repondu: Partial<Record<QuestionnaireSectionId, boolean>>;
  /** ADDENDUM — jeton d'aperçu interne : champs désactivés, aucun POST. */
  interne: boolean;
}

/** `true` si la page doit dessiner la question `cle` de `section`. */
export function champDemande(
  champs: Partial<Record<QuestionnaireSectionId, string[]>>,
  section: QuestionnaireSectionId,
  cle: string,
): boolean {
  const liste = champs[section];
  return liste === undefined ? true : liste.includes(cle);
}

/** Parseur défensif : `null` si la forme est inexploitable (jamais une valeur devinée). */
export function parseQuestionnaireGet(body: unknown): QuestionnaireGetResponse | null {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  const b = body as Record<string, unknown>;

  const entreprise = typeof b.entreprise === 'string' ? b.entreprise : '';
  const prenom = typeof b.prenom === 'string' ? b.prenom : '';

  const sectionsRaw = Array.isArray(b.sections) ? b.sections : [];
  const sections = sectionsRaw.filter(isQuestionnaireSectionId);
  if (sections.length === 0) return null;

  const prefillRaw = b.prefill;
  const prefill =
    prefillRaw && typeof prefillRaw === 'object' && !Array.isArray(prefillRaw)
      ? (prefillRaw as Record<string, unknown>)
      : {};

  const reponduRaw = b.repondu;
  const reponduSrc =
    reponduRaw && typeof reponduRaw === 'object' && !Array.isArray(reponduRaw)
      ? (reponduRaw as Record<string, unknown>)
      : {};
  const repondu: Partial<Record<QuestionnaireSectionId, boolean>> = {};
  for (const s of sections) {
    if (reponduSrc[s] === true) repondu[s] = true;
  }

  const champsRaw = b.champs;
  const champs: Partial<Record<QuestionnaireSectionId, string[]>> = {};
  if (champsRaw && typeof champsRaw === 'object' && !Array.isArray(champsRaw)) {
    for (const s of sections) {
      const liste = (champsRaw as Record<string, unknown>)[s];
      // Une entrée malformée est IGNORÉE (section non restreinte) plutôt que
      // traduite en liste vide : cacher toutes les questions d'un écran sur un
      // parsing douteux serait pire que d'en poser une de trop.
      if (Array.isArray(liste)) {
        champs[s] = liste.filter((v): v is string => typeof v === 'string');
      }
    }
  }

  const interne = b.interne === true;

  return { entreprise, prenom, sections, champs, prefill, repondu, interne };
}

/** URL backend GET/POST — même chemin pour les deux méthodes (contrat). */
export function questionnaireEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/crm/public/questionnaire/${encodeURIComponent(token)}/`;
}

/**
 * Chemin du proxy SAME-ORIGIN pour les POST du NAVIGATEUR (recalage
 * orchestrateur 25/08) : le patron établi des pages publiques
 * (/api/proposition-*) — le backend n'est jamais exposé au navigateur et
 * aucun CORS n'est ouvert. Le GET SSR, lui, appelle `questionnaireEndpoint`
 * directement côté serveur (pas de CORS en jeu).
 */
export const QUESTIONNAIRE_PROXY_PATH = '/api/questionnaire-repondre';

/**
 * Index de la section à afficher à l'ouverture : la PREMIÈRE non répondue —
 * « il reprend où il s'est arrêté ». Toutes répondues ⇒ la dernière (relisible,
 * jamais un index hors bornes). Liste vide ⇒ 0 (garde-fou, ne devrait pas
 * arriver : `parseQuestionnaireGet` refuse déjà une liste de sections vide).
 */
export function initialSectionIndex(
  sections: readonly QuestionnaireSectionId[],
  repondu: Partial<Record<QuestionnaireSectionId, boolean>>,
): number {
  if (sections.length === 0) return 0;
  const idx = sections.findIndex((s) => !repondu[s]);
  return idx === -1 ? sections.length - 1 : idx;
}

export function progressLabel(index: number, total: number): string {
  return `Étape ${index + 1} sur ${total}`;
}

// ── ÉCRANS : le regroupement des sections en pages ───────────────────────
//
// « finally the number of pages those questions should be in » (ordre
// fondateur 25/08/2026). La SECTION reste l'unité d'ENREGISTREMENT — le
// contrat POST ne bouge pas, un écran POSTe simplement chacune des siennes.
// L'ÉCRAN, lui, est l'unité de LECTURE : 9 sections faisaient 9 pages, dont
// trois pages consécutives ne demandaient qu'une photo chacune.
//
// Le regroupement suit les sources UX : GOV.UK « one thing per page » veut une
// chose par page, mais précise qu'une « chose » n'est pas forcément un champ
// unique (une date = 3 champs) ; NN/g « 4 principles to reduce cognitive load »
// demande de GROUPER les champs liés. Les trois photos sont une seule chose
// (« photographiez votre installation ») ; `toiture`+`gps` en sont une autre
// (« votre toit : lequel, et où »). Résultat : 6 écrans au maximum au lieu de
// 9, et typiquement 3 ou 4 (les sections déjà connues ne sont pas servies).
//
// INVARIANT : les sections d'un écran sont CONSÉCUTIVES dans
// QUESTIONNAIRE_SECTIONS — la page les dessine dans l'ordre reçu du serveur,
// un groupe non consécutif produirait un écran troué. Épinglé par un test.

export interface EcranDef {
  id: string;
  sections: readonly QuestionnaireSectionId[];
  title: { fr: string; en: string; ar: string };
}

export const ECRANS: readonly EcranDef[] = [
  {
    id: 'presence',
    sections: ['occupation'],
    title: { fr: 'Votre présence en journée', en: 'Your daytime presence', ar: 'وجودكم خلال النهار' },
  },
  {
    id: 'equipements',
    sections: ['equipements'],
    title: { fr: 'Vos équipements', en: 'Your appliances', ar: 'تجهيزاتكم' },
  },
  {
    id: 'electricite',
    sections: ['energie'],
    title: { fr: 'Votre électricité', en: 'Your electricity', ar: 'كهرباؤكم' },
  },
  {
    id: 'pompage',
    sections: ['pompage'],
    title: { fr: 'Votre pompage', en: 'Your water pumping', ar: 'الضخ والسقي' },
  },
  {
    id: 'reseau',
    sections: ['reseau'],
    title: { fr: 'Votre raccordement', en: 'Your grid connection', ar: 'الربط بالشبكة' },
  },
  {
    id: 'activite',
    sections: ['activite'],
    title: { fr: 'Votre activité', en: 'Your activity', ar: 'نشاطكم' },
  },
  {
    id: 'toit',
    sections: ['toiture', 'site', 'gps'],
    title: { fr: 'Votre toit', en: 'Your roof', ar: 'سطحكم' },
  },
  {
    id: 'photos',
    sections: [
      'photo_facture', 'photo_compteur', 'photo_tableau', 'photo_pompe', 'photo_forage',
      'photo_factures', 'photo_poste',
    ],
    title: { fr: 'Vos photos', en: 'Your photos', ar: 'صوركم' },
  },
  {
    id: 'societe',
    sections: ['societe'],
    title: { fr: 'Votre société', en: 'Your company', ar: 'شركتكم' },
  },
  {
    id: 'coordonnees',
    sections: ['contact'],
    title: { fr: 'Vos coordonnées', en: 'Your contact details', ar: 'معلومات التواصل' },
  },
];

export interface EcranActif extends EcranDef {
  /** Sections RÉELLEMENT servies par le serveur, dans l'ordre reçu. */
  actives: QuestionnaireSectionId[];
}

/**
 * Écrans à traverser : ceux qui portent au moins une section servie.
 * Une section servie qu'aucun écran ne réclame (clé future, backend en avance
 * sur le site) obtient son PROPRE écran à la fin plutôt que de disparaître —
 * une question perdue en silence serait pire qu'un écran de plus.
 */
export function ecransActifs(sections: readonly QuestionnaireSectionId[]): EcranActif[] {
  const restantes = new Set<QuestionnaireSectionId>(sections);
  const out: EcranActif[] = [];
  for (const ecran of ECRANS) {
    const actives = sections.filter((s) => ecran.sections.includes(s));
    if (actives.length === 0) continue;
    actives.forEach((s) => restantes.delete(s));
    out.push({ ...ecran, actives });
  }
  for (const orpheline of sections) {
    if (!restantes.has(orpheline)) continue;
    const meta = SECTION_META[orpheline];
    out.push({
      id: `section-${orpheline}`,
      sections: [orpheline],
      actives: [orpheline],
      title: meta ? meta.title : { fr: orpheline, en: orpheline, ar: orpheline },
    });
  }
  return out;
}

/**
 * Écran d'ouverture : le premier dont une section reste sans réponse — « il
 * reprend où il s'est arrêté ». Tout répondu ⇒ le dernier (relisible).
 */
export function initialEcranIndex(
  ecrans: readonly EcranActif[],
  repondu: Partial<Record<QuestionnaireSectionId, boolean>>,
): number {
  if (ecrans.length === 0) return 0;
  const idx = ecrans.findIndex((e) => e.actives.some((s) => !repondu[s]));
  return idx === -1 ? ecrans.length - 1 : idx;
}

// ── Petites listes fermées (vocabulaire des champs) ─────────────────────

export const RACCORDEMENT_VALUES = ['mono', 'tri'] as const;
export type RaccordementId = (typeof RACCORDEMENT_VALUES)[number];

// Même vocabulaire que ROOF_TYPES (src/lib/lead.ts) — reprise DÉLIBÉRÉE du
// vocable déjà établi ailleurs sur le site, pas une invention.
export const TYPE_TOITURE_VALUES = ['villa', 'hangar', 'toit_plat', 'autre'] as const;
export type TypeToitureId = (typeof TYPE_TOITURE_VALUES)[number];

export const OWNERSHIP_VALUES = ['proprietaire', 'locataire'] as const;
export type OwnershipId = (typeof OWNERSHIP_VALUES)[number];

// Mêmes libellés/valeurs que le tunnel /devis/mon-toit (L-WEBT, crm.Lead.occupation_jour).
export const OCCUPATION_JOUR_VALUES = ['present', 'absent', 'partiel'] as const;
// AGW408 — vocabulaire du bloc pompage, IDENTIQUE au contrat
// `lead_pompage.json` (colonnes crm.Lead : choix fermés).
export const SOURCE_EAU_VALUES = ['puits', 'forage', 'bassin', 'riviere'] as const;
export const IRRIGATION_METHODE_VALUES = ['goutte', 'aspersion', 'gravitaire'] as const;
export const POMPE_ALIM_VALUES = ['aucune', 'diesel', 'butane', 'electrique'] as const;
export const MOIS_IRRIGATION_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

export type OccupationJourId = (typeof OCCUPATION_JOUR_VALUES)[number];

// CIW406 — vocabulaire des sections PRO, IDENTIQUE au contrat `lead_pro.json`
// (colonnes crm.Lead : choix fermés). Épinglé par un test contre le JSON.
export const TENSION_VALUES = ['bt', 'mt', 'ne_sait_pas'] as const;
export const TYPE_SURFACE_VALUES = ['toiture', 'ombriere', 'terrain'] as const;
export const TYPE_TOITURE_PRO_VALUES = [
  'terrasse_beton', 'tole_metal', 'tuiles', 'bac_acier', 'fibrociment', 'autre',
] as const;
export const REGIME_EQUIPES_VALUES = ['1x8', '2x8', '3x8', 'continu', 'ne_sait_pas'] as const;
export const OUI_NON_VALUES = ['oui', 'non'] as const;
export const TVA_RECUPERABLE_VALUES = ['oui', 'non', 'ne_sait_pas'] as const;
export const CATEGORIE_COMMERCIALE_VALUES = [
  'hotel', 'restaurant', 'commerce', 'bureau', 'sante', 'ecole', 'hammam', 'boulangerie', 'froid', 'autre',
] as const;
/** Jours d'ouverture : 1 (lundi) à 7 (dimanche). */
export const JOURS_OUVERTURE_VALUES = [1, 2, 3, 4, 5, 6, 7] as const;
/** Au plus 12 mois de relevé (contrat `releve_conso.max_elements`). */
export const RELEVE_CONSO_MAX_MOIS = 12;

export interface CategorieQuestion {
  key: string;
  type: 'number' | 'bool' | 'select';
  /** Valeurs fermées d'une question `select`. */
  options?: readonly string[];
}
/**
 * Questions propres à chaque catégorie commerciale = clés FERMÉES de
 * `reponses_categorie_par_categorie.cles` (contrat `lead_pro.json`, miroir de
 * `crm.Lead.REPONSES_CATEGORIE_CLES`). Les libellés FR/EN/AR vivent dans la page.
 */
export const REPONSES_CATEGORIE_QUESTIONS: Record<string, readonly CategorieQuestion[]> = {
  hotel: [
    { key: 'chambres', type: 'number' },
    { key: 'occupation_pct', type: 'number' },
    { key: 'piscine', type: 'bool' },
    { key: 'heures_piscine', type: 'number' },
    { key: 'blanchisserie', type: 'bool' },
    { key: 'reception_24h', type: 'bool' },
  ],
  restaurant: [
    { key: 'chambres_froides', type: 'number' },
    { key: 'horaires', type: 'select', options: ['midi', 'soir', 'continu'] },
    { key: 'cuisson', type: 'select', options: ['electrique', 'gaz'] },
    { key: 'ouvert_journee_ramadan', type: 'bool' },
  ],
  commerce: [
    { key: 'surface_vente_m2', type: 'number' },
    { key: 'chambres_froides', type: 'number' },
  ],
  bureau: [
    { key: 'effectif', type: 'number' },
    { key: 'clim', type: 'bool' },
  ],
  sante: [
    { key: 'lits', type: 'number' },
    { key: 'garde_nuit', type: 'bool' },
  ],
  ecole: [
    { key: 'effectif', type: 'number' },
    { key: 'internat', type: 'bool' },
    { key: 'fermeture_estivale', type: 'bool' },
  ],
  hammam: [
    { key: 'surface_m2', type: 'number' },
    { key: 'chauffe', type: 'select', options: ['electrique', 'gaz'] },
  ],
  boulangerie: [
    { key: 'four', type: 'select', options: ['electrique', 'gaz'] },
    { key: 'cuisson_nocturne', type: 'bool' },
  ],
  froid: [
    { key: 'temperature_consigne', type: 'number' },
    { key: 'volume_m3', type: 'number' },
    { key: 'saisonnalite_recolte', type: 'bool' },
  ],
  autre: [],
};

export type EquipementKey =
  | 'equip_piscine'
  | 'equip_voiture_electrique'
  | 'equip_clim'
  | 'equip_chauffe_eau_electrique';
export const EQUIPEMENT_KEYS: readonly EquipementKey[] = [
  'equip_piscine',
  'equip_voiture_electrique',
  'equip_clim',
  'equip_chauffe_eau_electrique',
];

/** Bornes GPS ≈ Maroc — mêmes bornes que src/lib/lead.ts (copie locale, module autonome). */
export const MOROCCO_GPS_BOUNDS = { latMin: 20, latMax: 37, lngMin: -18, lngMax: 0 } as const;
export function isMoroccoLat(lat: number): boolean {
  return Number.isFinite(lat) && lat >= MOROCCO_GPS_BOUNDS.latMin && lat <= MOROCCO_GPS_BOUNDS.latMax;
}
export function isMoroccoLng(lng: number): boolean {
  return Number.isFinite(lng) && lng >= MOROCCO_GPS_BOUNDS.lngMin && lng <= MOROCCO_GPS_BOUNDS.lngMax;
}

// ── Nettoyeurs anti-garbage (jamais bloquants : une valeur malformée est ÉCARTÉE) ──

export function cleanStr(v: unknown, max = 200): string {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
}

export function cleanEmail(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.trim().slice(0, 254);
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s) ? s : null;
}

export function cleanPositiveNumber(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 && n <= max ? n : null;
}

export function cleanBoundedInt(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= max ? Math.round(n) : null;
}

export function cleanEnum<T extends string>(v: unknown, allowed: readonly T[]): T | null {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : null;
}

/** AGW408 — mois d'irrigation : entiers 1-12 DISTINCTS, triés ; liste vide ⇒ `null` (rien à envoyer). */
export function cleanMoisIrrigation(v: unknown): number[] | null {
  if (!Array.isArray(v)) return null;
  const mois = new Set<number>();
  for (const m of v) {
    const n = Number(m);
    if (Number.isInteger(n) && n >= 1 && n <= 12) mois.add(n);
  }
  return mois.size > 0 ? [...mois].sort((a, b) => a - b) : null;
}

/** 'oui'/'non' → booléen explicite, sinon `undefined` (question pas encore répondue). */
export function cleanOuiNon(v: unknown): boolean | undefined {
  if (v === 'oui') return true;
  if (v === 'non') return false;
  return undefined;
}

// ── CIW406 — sections PRO : nettoyeurs dédiés ───────────────────────────

/** Nombre fini (négatif admis : une consigne de froid vaut −18 °C), borné. */
export function cleanBoundedNumber(v: unknown, min: number, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= min && n <= max ? n : null;
}

/** Entiers DISTINCTS de `[min, max]`, triés ; liste vide ⇒ `null`. */
export function cleanEntiersDistincts(v: unknown, min: number, max: number): number[] | null {
  if (!Array.isArray(v)) return null;
  const out = new Set<number>();
  for (const x of v) {
    const n = Number(x);
    if (Number.isInteger(n) && n >= min && n <= max) out.add(n);
  }
  return out.size > 0 ? [...out].sort((a, b) => a - b) : null;
}

export interface ReleveMois {
  mois: string;
  kwh: number;
  kwh_pointe?: number;
  kwh_pleines?: number;
  kwh_creuses?: number;
}

/**
 * Relevé de consommation (contrat `releve_conso`) : au plus 12 mois DISTINCTS
 * « AAAA-MM », chacun avec des kWh ≥ 0 (une ligne sans kWh est écartée — jamais
 * un 0 fabriqué). Les registres pointe / pleines / creuses ne valent qu'en
 * moyenne tension (`mt`) : hors MT ils ne partent jamais. Aucun mois valide ⇒ `null`.
 */
export function cleanReleveConso(
  v: unknown,
  tension: string | null | undefined,
): { mois: ReleveMois[]; source: 'declare' } | null {
  if (!Array.isArray(v)) return null;
  const vus = new Set<string>();
  const out: ReleveMois[] = [];
  for (const ligne of v) {
    if (!ligne || typeof ligne !== 'object') continue;
    const l = ligne as Record<string, unknown>;
    const mois = typeof l.mois === 'string' ? l.mois.trim() : '';
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(mois) || vus.has(mois)) continue;
    const kwh = cleanBoundedNumber(l.kwh, 0, 100_000_000);
    if (kwh == null) continue;
    const propre: ReleveMois = { mois, kwh };
    if (tension === 'mt') {
      const pointe = cleanBoundedNumber(l.kwh_pointe, 0, 100_000_000);
      const pleines = cleanBoundedNumber(l.kwh_pleines, 0, 100_000_000);
      const creuses = cleanBoundedNumber(l.kwh_creuses, 0, 100_000_000);
      if (pointe != null) propre.kwh_pointe = pointe;
      if (pleines != null) propre.kwh_pleines = pleines;
      if (creuses != null) propre.kwh_creuses = creuses;
    }
    vus.add(mois);
    out.push(propre);
    if (out.length >= RELEVE_CONSO_MAX_MOIS) break;
  }
  return out.length > 0 ? { mois: out, source: 'declare' } : null;
}

/**
 * Réponses propres à la catégorie : SEULES les clés fermées de la catégorie
 * choisie, typées (nombre / oui-non / liste fermée) ; vide ⇒ `null`.
 */
export function cleanReponsesCategorie(
  categorie: string | null,
  v: unknown,
): Record<string, number | boolean | string> | null {
  if (!categorie || !v || typeof v !== 'object' || Array.isArray(v)) return null;
  const questions = REPONSES_CATEGORIE_QUESTIONS[categorie] ?? [];
  const src = v as Record<string, unknown>;
  const out: Record<string, number | boolean | string> = {};
  for (const q of questions) {
    const brut = src[q.key];
    if (q.type === 'number') {
      const n = cleanBoundedNumber(brut, -100, 100_000_000);
      if (n != null) out[q.key] = n;
    } else if (q.type === 'bool') {
      const b = cleanOuiNon(brut);
      if (b !== undefined) out[q.key] = b;
    } else {
      const e = cleanEnum(brut, (q.options ?? []) as readonly string[]);
      if (e) out[q.key] = e;
    }
  }
  return Object.keys(out).length > 0 ? out : null;
}

// ── Photos (data URL base64) ─────────────────────────────────────────────

/** Plafond d'upload par photo (contrat : ≤ 10 Mo). */
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

/** `true` si `v` est un data URL image bien formé et sous le plafond de taille. */
export function isValidPhotoDataUrl(v: unknown): v is string {
  if (typeof v !== 'string' || !v.startsWith('data:image/')) return false;
  const commaIdx = v.indexOf(',');
  if (commaIdx < 0) return false;
  const b64 = v.slice(commaIdx + 1);
  if (!b64) return false;
  const approxBytes = Math.floor((b64.length * 3) / 4);
  return approxBytes > 0 && approxBytes <= MAX_PHOTO_BYTES;
}

// ── Construction du corps POST, PAR SECTION ──────────────────────────────

/**
 * Extrait + nettoie les `reponses` d'UNE section à partir d'un objet brut de
 * valeurs de formulaire (ex. issu de `Object.fromEntries(new FormData(...))`
 * complété des booléens/nombres déjà typés par la page). Une section photo_*
 * ne porte jamais de `reponses` (le cliché voyage dans `photo`, séparément).
 */
export function buildSectionReponses(
  section: QuestionnaireSectionId,
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  switch (section) {
    case 'contact': {
      const email = cleanEmail(raw.email);
      if (email) out.email = email;
      const adresse = cleanStr(raw.adresse, 200);
      if (adresse) out.adresse = adresse;
      const ville = cleanStr(raw.ville, 100);
      if (ville) out.ville = ville;
      break;
    }
    case 'gps': {
      const lat = Number(raw.gps_lat);
      const lng = Number(raw.gps_lng);
      if (raw.gps_lat != null && raw.gps_lat !== '' && isMoroccoLat(lat)) out.gps_lat = lat;
      if (raw.gps_lng != null && raw.gps_lng !== '' && isMoroccoLng(lng)) out.gps_lng = lng;
      break;
    }
    case 'energie': {
      const factureHiver = cleanPositiveNumber(raw.facture_hiver, 1_000_000);
      if (factureHiver != null) out.facture_hiver = factureHiver;
      const consoKwh = cleanPositiveNumber(raw.conso_mensuelle_kwh, 1_000_000);
      if (consoKwh != null) out.conso_mensuelle_kwh = consoKwh;
      const eteDifferente = cleanOuiNon(raw.ete_differente);
      if (eteDifferente !== undefined) {
        out.ete_differente = eteDifferente;
        if (eteDifferente) {
          const factureEte = cleanPositiveNumber(raw.facture_ete, 1_000_000);
          if (factureEte != null) out.facture_ete = factureEte;
        }
      }
      const raccordement = cleanEnum(raw.raccordement, RACCORDEMENT_VALUES);
      if (raccordement) out.raccordement = raccordement;
      break;
    }
    case 'reseau': {
      const tension = cleanEnum(raw.tension_raccordement, TENSION_VALUES);
      if (tension) out.tension_raccordement = tension;
      const kva = cleanBoundedNumber(raw.compteur_puissance_kva, 0.01, 100_000);
      if (kva != null) out.compteur_puissance_kva = kva;
      const kwh = cleanBoundedNumber(raw.conso_mensuelle_kwh, 0.01, 100_000_000);
      if (kwh != null) out.conso_mensuelle_kwh = kwh;
      const releve = cleanReleveConso(raw.releve_conso, tension);
      if (releve) out.releve_conso = releve;
      // cos φ : décimal ]0 ; 1], jamais supposé (colonne industriel seulement,
      // le serveur ne la sert pas à un commerce).
      const cos = cleanBoundedNumber(raw.cos_phi, 0.01, 1);
      if (cos != null) out.cos_phi = cos;
      break;
    }
    case 'activite': {
      const categorie = cleanEnum(raw.categorie_commerciale, CATEGORIE_COMMERCIALE_VALUES);
      if (categorie) {
        out.categorie_commerciale = categorie;
        const rc = cleanReponsesCategorie(categorie, raw.reponses_categorie);
        if (rc) out.reponses_categorie = rc;
      }
      const secteur = cleanStr(raw.secteur_industriel, 120);
      if (secteur) out.secteur_industriel = secteur;
      const exportUe = cleanEnum(raw.export_ue_declare, OUI_NON_VALUES);
      if (exportUe) out.export_ue_declare = exportUe;
      const equipes = cleanEnum(raw.regime_equipes, REGIME_EQUIPES_VALUES);
      if (equipes) out.regime_equipes = equipes;
      const jours = cleanEntiersDistincts(raw.jours_ouverture, 1, 7);
      if (jours) out.jours_ouverture = jours;
      const debut = cleanBoundedInt(raw.heure_debut, 24);
      const fin = cleanBoundedInt(raw.heure_fin, 24);
      // Le serveur écarte la paire si début ≥ fin : on ne l'envoie pas non plus.
      if (debut != null && fin != null && debut < fin) {
        out.heure_debut = debut;
        out.heure_fin = fin;
      }
      const fermeture = cleanEntiersDistincts(raw.fermeture_mois, 1, 12);
      if (fermeture) out.fermeture_mois = fermeture;
      const groupe = cleanEnum(raw.groupe_electrogene, OUI_NON_VALUES);
      if (groupe) out.groupe_electrogene = groupe;
      // Les détails du groupe ne valent que s'il y en a un (jamais une valeur
      // restée dans un champ masqué) ; litres ET dirhams DÉCLARÉS, jamais déduits.
      if (groupe === 'oui') {
        const gkva = cleanBoundedNumber(raw.groupe_kva, 0.01, 1_000_000);
        if (gkva != null) out.groupe_kva = gkva;
        const litres = cleanBoundedNumber(raw.groupe_litres_mois, 0.01, 10_000_000);
        if (litres != null) out.groupe_litres_mois = litres;
        const mad = cleanBoundedNumber(raw.groupe_depense_mad_mois, 0.01, 100_000_000);
        if (mad != null) out.groupe_depense_mad_mois = mad;
      }
      const pv = cleanBoundedNumber(raw.pv_existant_kwc, 0.01, 1_000_000);
      if (pv != null) out.pv_existant_kwc = pv;
      break;
    }
    case 'site': {
      const surface = cleanEnum(raw.type_surface, TYPE_SURFACE_VALUES);
      if (surface) out.type_surface = surface;
      const type = cleanEnum(raw.type_toiture, TYPE_TOITURE_PRO_VALUES);
      if (type) out.type_toiture = type;
      const m2 = cleanPositiveNumber(raw.surface_toiture_m2, 10_000_000);
      if (m2 != null) out.surface_toiture_m2 = m2;
      break;
    }
    case 'societe': {
      for (const [cle, max] of [
        ['societe', 255], ['ice', 30], ['rc', 30], ['if_fiscal', 30], ['adresse_siege', 500],
        ['fonction_contact', 120], ['contact_secondaire_nom', 255],
        ['contact_secondaire_telephone', 50], ['contact_secondaire_fonction', 120],
      ] as const) {
        const val = cleanStr(raw[cle], max);
        if (val) out[cle] = val;
      }
      const emailSecondaire = cleanEmail(raw.contact_secondaire_email);
      if (emailSecondaire) out.contact_secondaire_email = emailSecondaire;
      const tva = cleanEnum(raw.tva_recuperable, TVA_RECUPERABLE_VALUES);
      if (tva) out.tva_recuperable = tva;
      break;
    }
    case 'photo_facture':
    case 'photo_compteur':
    case 'photo_tableau':
    case 'photo_pompe':
    case 'photo_forage':
    case 'photo_factures':
    case 'photo_poste':
      // Rien dans `reponses` — la photo voyage dans le champ `photo` du corps POST.
      break;
    case 'toiture': {
      const type = cleanEnum(raw.type_toiture, TYPE_TOITURE_VALUES);
      if (type) out.type_toiture = type;
      // « Je ne sais pas » (case cochée) ⇒ la surface reste absente, jamais 0/devinée.
      if (raw.surface_inconnue !== true) {
        const surface = cleanPositiveNumber(raw.surface_toiture_m2, 100_000);
        if (surface != null) out.surface_toiture_m2 = surface;
      }
      // Clé backend RÉELLE : `roof_age` (crm.Lead — vérifié au fold 25/08,
      // le contrat Q-A l'a corrigée ; `roof_age_years` n'existe pas côté Lead).
      const age = cleanBoundedInt(raw.roof_age, 100);
      if (age != null) out.roof_age = age;
      const ownership = cleanEnum(raw.ownership, OWNERSHIP_VALUES);
      if (ownership) out.ownership = ownership;
      break;
    }
    case 'pompage': {
      const source = cleanEnum(raw.source_eau, SOURCE_EAU_VALUES);
      if (source) out.source_eau = source;
      const niveau = cleanPositiveNumber(raw.niveau_statique_m, 1_000);
      if (niveau != null) out.niveau_statique_m = niveau;
      const besoin = cleanPositiveNumber(raw.besoin_eau_m3j, 100_000);
      if (besoin != null) out.besoin_eau_m3j = besoin;
      const surface = cleanPositiveNumber(raw.surface_irriguee_ha, 100_000);
      if (surface != null) out.surface_irriguee_ha = surface;
      const culture = cleanStr(raw.culture, 100);
      if (culture) out.culture = culture;
      const methode = cleanEnum(raw.irrigation_methode, IRRIGATION_METHODE_VALUES);
      if (methode) out.irrigation_methode = methode;
      const alim = cleanEnum(raw.pompe_alim_actuelle, POMPE_ALIM_VALUES);
      if (alim) out.pompe_alim_actuelle = alim;
      // Les questions carburant ne valent que pour une pompe à butane /
      // diesel : si la réponse « alimentation » dit autre chose, on ne
      // transmet pas une valeur laissée dans un champ masqué.
      const carburantPose = alim === undefined || alim === null || alim === 'butane' || alim === 'diesel';
      if (carburantPose) {
        if (alim === null || alim === 'butane') {
          const bouteilles = cleanPositiveNumber(raw.butane_bouteilles_jour, 1_000);
          if (bouteilles != null) out.butane_bouteilles_jour = bouteilles;
        }
        const prix = cleanPositiveNumber(raw.carburant_prix_unitaire_mad, 99_999);
        if (prix != null) out.carburant_prix_unitaire_mad = prix;
        const depense = cleanPositiveNumber(raw.depense_carburant_mad_mois, 10_000_000);
        if (depense != null) out.depense_carburant_mad_mois = depense;
      }
      const mois = cleanMoisIrrigation(raw.mois_irrigation);
      if (mois) out.mois_irrigation = mois;
      const compteur = cleanOuiNon(raw.compteur_eau);
      if (compteur !== undefined) out.compteur_eau = compteur;
      break;
    }
    case 'occupation': {
      const occ = cleanEnum(raw.occupation_jour, OCCUPATION_JOUR_VALUES);
      if (occ) out.occupation_jour = occ;
      break;
    }
    case 'equipements': {
      for (const key of EQUIPEMENT_KEYS) {
        const v = cleanOuiNon(raw[key]);
        if (v !== undefined) out[key] = v;
      }
      if (out.equip_piscine === true) {
        const kw = cleanPositiveNumber(raw.equip_piscine_pompe_kw, 50);
        if (kw != null) out.equip_piscine_pompe_kw = kw;
      }
      if (out.equip_voiture_electrique === true) {
        const km = cleanPositiveNumber(raw.equip_ve_km_semaine, 5_000);
        if (km != null) out.equip_ve_km_semaine = km;
      }
      if (out.equip_clim === true) {
        const pieces = cleanPositiveNumber(raw.equip_clim_pieces, 50);
        if (pieces != null) out.equip_clim_pieces = Math.round(pieces);
      }
      break;
    }
  }

  return out;
}

export interface QuestionnairePostBody {
  section: QuestionnaireSectionId;
  reponses: Record<string, unknown>;
  photo?: string;
  /** LANE T-WEB (25/08/2026) — empreinte d'appareil anonyme, additive (voir
   *  lib/visite.ts `appareilId`) : présente uniquement quand fournie par
   *  l'appelant, jamais fabriquée ici. */
  appareil_id?: string;
  /** QJR633 — pré-remplissage affiché (contrat QJR512), limité à la section. */
  prefill_vu?: Record<string, unknown>;
}

/** Colonnes écrites par section (miroir de `colonnes_ecrites`, contrat QJR512). */
const SECTION_COLONNES_ECRITES: Partial<Record<QuestionnaireSectionId, readonly string[]>> = {
  contact: ['email', 'adresse', 'ville'],
  gps: ['gps_lat', 'gps_lng'],
  energie: ['facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh', 'raccordement'],
  toiture: ['type_toiture', 'surface_toiture_m2', 'roof_age', 'ownership'],
  occupation: ['occupation_jour'],
  reseau: ['tension_raccordement', 'compteur_puissance_kva', 'conso_mensuelle_kwh', 'releve_conso', 'cos_phi'],
  activite: [
    'categorie_commerciale', 'reponses_categorie', 'secteur_industriel', 'export_ue_declare',
    'regime_equipes', 'jours_ouverture', 'heure_debut', 'heure_fin', 'fermeture_mois',
    'groupe_electrogene', 'groupe_kva', 'groupe_litres_mois', 'groupe_depense_mad_mois', 'pv_existant_kwc',
  ],
  site: ['type_surface', 'type_toiture', 'surface_toiture_m2'],
  societe: [
    'societe', 'ice', 'rc', 'if_fiscal', 'adresse_siege', 'fonction_contact',
    'contact_secondaire_nom', 'contact_secondaire_telephone', 'contact_secondaire_email',
    'contact_secondaire_fonction', 'tva_recuperable',
  ],
  pompage: [
    'source_eau', 'niveau_statique_m', 'besoin_eau_m3j', 'surface_irriguee_ha', 'culture',
    'irrigation_methode', 'pompe_alim_actuelle', 'butane_bouteilles_jour',
    'carburant_prix_unitaire_mad', 'depense_carburant_mad_mois', 'mois_irrigation', 'compteur_eau',
  ],
  equipements: [
    'equip_piscine', 'equip_piscine_pompe_kw', 'equip_voiture_electrique', 'equip_ve_km_semaine',
    'equip_clim', 'equip_clim_pieces', 'equip_chauffe_eau_electrique',
  ],
};

/**
 * Construit le corps POST complet d'une section. `photoDataUrl` n'est repris
 * que pour une section photo_* ET s'il est un data URL image valide et sous
 * le plafond de taille — sinon il est simplement omis (jamais un envoi
 * malformé, jamais une seconde tentative silencieuse). `appareilId`
 * (LANE T-WEB) est ADDITIF : omis quand absent/vide, jamais bloquant.
 */
export function buildQuestionnairePostBody(
  section: QuestionnaireSectionId,
  raw: Record<string, unknown>,
  photoDataUrl?: string | null,
  appareilId?: string,
  prefillVu?: Record<string, unknown> | null,
): QuestionnairePostBody {
  const body: QuestionnairePostBody = { section, reponses: buildSectionReponses(section, raw) };
  if (isPhotoSection(section) && isValidPhotoDataUrl(photoDataUrl)) {
    body.photo = photoDataUrl;
  }
  if (appareilId) body.appareil_id = appareilId;
  // QJR633 — ce que le client a VU pré-rempli (sous-ensemble du prefill du GET
  // limité aux colonnes de la section, tel que reçu) : le serveur distingue
  // « confirmé » de « modifié ». Jamais pour une section photo.
  if (prefillVu && !isPhotoSection(section)) {
    const vu: Record<string, unknown> = {};
    for (const col of SECTION_COLONNES_ECRITES[section] ?? []) {
      if (Object.prototype.hasOwnProperty.call(prefillVu, col)) vu[col] = prefillVu[col];
    }
    if (Object.keys(vu).length > 0) body.prefill_vu = vu;
  }
  return body;
}

/**
 * ALEA4 (D-ALEA-4) — « vu » après un envoi réussi : les valeurs que le client
 * vient d'ENVOYER deviennent ce qu'il a vu pré-rempli. Le POST suivant porte
 * donc `prefill_vu = valeurs envoyées` et le serveur ne réécrase pas une
 * correction de l'équipe sur un champ que le client n'a pas retouché. Pur :
 * ne mute pas `prefill`, ne touche aucun champ non envoyé.
 */
export function prefillApresEnvoi(
  prefill: Record<string, unknown>,
  reponses: Record<string, unknown>,
): Record<string, unknown> {
  return { ...prefill, ...reponses };
}

/**
 * ALEA46 — envoie UNE section au proxy same-origin (le jeton voyage dans le corps) et ne
 * fusionne le « vu » (ALEA4) qu'APRÈS une réponse acceptée : un refus ou une panne réseau
 * rend `prefill` inchangé. `fetchImpl` est injecté (la page passe `fetch`).
 */
export async function envoyerSectionQuestionnaire(
  fetchImpl: typeof fetch,
  token: string,
  body: QuestionnairePostBody,
  prefill: Record<string, unknown>,
): Promise<{ result: QuestionnairePostResult; prefill: Record<string, unknown> }> {
  try {
    const res = await fetchImpl(QUESTIONNAIRE_PROXY_PATH, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ token, ...body }),
    });
    const result = parseQuestionnairePostResponse(res.status, await res.json().catch(() => null));
    return { result, prefill: result.ok ? prefillApresEnvoi(prefill, body.reponses) : prefill };
  } catch {
    return { result: { ok: false, enregistrees: [], detail: 'Connexion impossible. Vérifiez votre réseau et réessayez.' }, prefill };
  }
}

/**
 * `true` si le corps POST n'a RIEN de neuf à envoyer (aucune réponse, aucune
 * photo) — la page doit alors sauter l'appel réseau plutôt que poster un
 * objet vide (ex. section déjà répondue et rouverte sans y toucher, ou
 * section volontairement passée).
 */
export function isEmptyPostBody(body: QuestionnairePostBody): boolean {
  return Object.keys(body.reponses).length === 0 && !body.photo;
}

// ── Réponse POST ─────────────────────────────────────────────────────────

export interface QuestionnairePostResult {
  ok: boolean;
  enregistrees: string[];
  detail?: string;
}

/** Normalise (statut HTTP, JSON upstream) → une forme unique lue par la page. */
export function parseQuestionnairePostResponse(status: number, body: unknown): QuestionnairePostResult {
  const b = body && typeof body === 'object' && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
  const ok = status >= 200 && status < 300 && b.ok === true;
  const enregistreesRaw = Array.isArray(b.enregistrees) ? b.enregistrees : [];
  const enregistrees = enregistreesRaw.filter((v): v is string => typeof v === 'string');
  const detail = typeof b.detail === 'string' ? b.detail : undefined;
  return { ok, enregistrees, detail };
}

/** `true` tant que le jeton est un APERÇU INTERNE : aucun POST ne doit partir. */
export function isInternalPreview(data: Pick<QuestionnaireGetResponse, 'interne'>): boolean {
  return data.interne === true;
}
