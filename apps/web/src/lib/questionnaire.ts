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

export const QUESTIONNAIRE_SECTIONS = [
  'contact',
  'gps',
  'energie',
  'photo_facture',
  'photo_compteur',
  'photo_tableau',
  'toiture',
  'occupation',
  'equipements',
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
  prefill: Record<string, unknown>;
  repondu: Partial<Record<QuestionnaireSectionId, boolean>>;
  /** ADDENDUM — jeton d'aperçu interne : champs désactivés, aucun POST. */
  interne: boolean;
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

  const interne = b.interne === true;

  return { entreprise, prenom, sections, prefill, repondu, interne };
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
