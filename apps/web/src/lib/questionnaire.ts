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
  'toiture',
  'gps',
  'photo_facture',
  'photo_compteur',
  'photo_tableau',
  'contact',
] as const;
export type QuestionnaireSectionId = (typeof QUESTIONNAIRE_SECTIONS)[number];

export function isQuestionnaireSectionId(v: unknown): v is QuestionnaireSectionId {
  return typeof v === 'string' && (QUESTIONNAIRE_SECTIONS as readonly string[]).includes(v);
}

export function isPhotoSection(section: QuestionnaireSectionId): boolean {
  return section === 'photo_facture' || section === 'photo_compteur' || section === 'photo_tableau';
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
    id: 'toit',
    sections: ['toiture', 'gps'],
    title: { fr: 'Votre toit', en: 'Your roof', ar: 'سطحكم' },
  },
  {
    id: 'photos',
    sections: ['photo_facture', 'photo_compteur', 'photo_tableau'],
    title: { fr: 'Vos photos', en: 'Your photos', ar: 'صوركم' },
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
export type OccupationJourId = (typeof OCCUPATION_JOUR_VALUES)[number];

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

/** 'oui'/'non' → booléen explicite, sinon `undefined` (question pas encore répondue). */
export function cleanOuiNon(v: unknown): boolean | undefined {
  if (v === 'oui') return true;
  if (v === 'non') return false;
  return undefined;
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
    case 'photo_facture':
    case 'photo_compteur':
    case 'photo_tableau':
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
}

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
): QuestionnairePostBody {
  const body: QuestionnairePostBody = { section, reponses: buildSectionReponses(section, raw) };
  if (isPhotoSection(section) && isValidPhotoDataUrl(photoDataUrl)) {
    body.photo = photoDataUrl;
  }
  if (appareilId) body.appareil_id = appareilId;
  return body;
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
