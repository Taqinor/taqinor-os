/**
 * Traitement serveur des leads : validation, simulation (proxy ou fallback
 * local), construction de l'enregistrement (consentement horodaté, fbclid +
 * UTM persistés), transfert CRM toléré à l'absence, CAPI fire-and-forget.
 *
 * Tout est paramétré par (env, fetchFn) pour rester testable hors Workers.
 */
import { isBillRangeId, localEstimateBand, qualifiesForCrm, type BillRangeId, type EstimateBand } from './billRange';
import { normalizeMoroccanPhone } from './phone';

export const ROOF_TYPES = [
  { id: 'villa', label: 'Villa' },
  { id: 'hangar', label: 'Hangar industriel' },
  { id: 'toit_plat', label: 'Toit plat' },
  { id: 'autre', label: 'Autre' },
] as const;
export type RoofTypeId = (typeof ROOF_TYPES)[number]['id'];

export const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as const;
export type UtmKey = (typeof UTM_KEYS)[number];

// ——— WJ30 : vocabulaires des champs FACULTATIFS élargis (pass-through webhook) ———
export const LEAD_MODES = ['residentiel', 'professionnel', 'agricole'] as const;
export type LeadModeId = (typeof LEAD_MODES)[number];

export const RACCORDEMENTS = ['monophase', 'triphase', 'inconnu'] as const;
export type RaccordementId = (typeof RACCORDEMENTS)[number];

export const LEAD_LANGS = ['fr', 'ar'] as const;
export type LeadLangId = (typeof LEAD_LANGS)[number];

// ——— WJ31 : vocabulaires des questions de capture élargies (facultatives) ———
export const DISTRIBUTEURS = ['onee', 'lydec', 'redal', 'inconnu'] as const;
export type DistributeurId = (typeof DISTRIBUTEURS)[number];

export const OMBRAGES = ['aucun', 'partiel', 'important'] as const;
export type OmbrageId = (typeof OMBRAGES)[number];

export const FUTURE_LOADS = ['clim', 've', 'pompe'] as const;
export type FutureLoadId = (typeof FUTURE_LOADS)[number];

export const OCCUPANT_TYPES = ['proprietaire', 'locataire', 'decideur'] as const;
export type OccupantTypeId = (typeof OCCUPANT_TYPES)[number];

export const PROJECT_TIMINGS = ['maintenant', '3mois', 'renseignement'] as const;
export type ProjectTimingId = (typeof PROJECT_TIMINGS)[number];

export const FINANCING_INTENTS = ['comptant', 'financement', 'indecis'] as const;
export type FinancingIntentId = (typeof FINANCING_INTENTS)[number];

// ——— WJ51 : préférence de contact explicite (facultative, pass-through webhook) ———
// Remplace la promesse floue « pas d'appels commerciaux » par un choix nommé,
// mappé sur le champ `canal` du CRM. Facultatif : une soumission sans ce champ
// reste valide (repli implicite WhatsApp, cohérent avec whatsappOptIn coché
// par défaut).
export const CONTACT_PREFERENCES = ['whatsapp_only', 'phone_ok'] as const;
export type ContactPreferenceId = (typeof CONTACT_PREFERENCES)[number];

/**
 * Bornes GPS ≈ Maroc (Tanger ~35,9 N → Lagouira ~20,8 N ; Atlantique ~-17,2 O →
 * frontière est ~-1,0). Garde-fou anti-garbage : un repère hors bornes est
 * ÉCARTÉ silencieusement — le lead passe sans lui, jamais bloqué.
 */
export const MOROCCO_GPS_BOUNDS = { latMin: 20, latMax: 37, lngMin: -18, lngMax: 0 } as const;

export function isMoroccoLat(lat: number): boolean {
  return Number.isFinite(lat) && lat >= MOROCCO_GPS_BOUNDS.latMin && lat <= MOROCCO_GPS_BOUNDS.latMax;
}
export function isMoroccoLng(lng: number): boolean {
  return Number.isFinite(lng) && lng >= MOROCCO_GPS_BOUNDS.lngMin && lng <= MOROCCO_GPS_BOUNDS.lngMax;
}

export interface LeadEnv {
  SIMULATOR_API_URL?: string;
  LEAD_WEBHOOK_URL?: string;
  /** Secret partagé avec le récepteur taqinor-os (X-Webhook-Secret). */
  LEAD_WEBHOOK_SECRET?: string;
  CAPI_URL?: string;
  WHATSAPP_NUMBER?: string;
}

export interface ValidatedLead {
  fullName: string;
  phoneE164: string;
  whatsappOptIn: boolean;
  city: string;
  roofType: RoofTypeId;
  billRange: BillRangeId;
  consent: true;
  fbclid: string | null;
  utm: Partial<Record<UtmKey, string>>;
  // — WJ30 : champs FACULTATIFS élargis. Présents UNIQUEMENT si la valeur reçue
  //   est valide : un champ facultatif malformé est ÉCARTÉ (jamais bloquant), et
  //   un champ absent reste absent — le contrat de fil existant est inchangé
  //   octet pour octet pour les soumissions d'aujourd'hui.
  email?: string;
  factureHiver?: number;
  factureEte?: number | null;
  eteDifferente?: boolean;
  billKwh?: number;
  raccordement?: RaccordementId;
  adresse?: string;
  mode?: LeadModeId;
  langue_preferee?: LeadLangId;
  roofPoint?: { lat: number; lng: number };
  gpsLat?: number;
  gpsLng?: number;
  roofOutline?: Array<[number, number]>;
  // — WJ31 : questions de capture « best-in-world », toutes FACULTATIVES, même
  //   discipline que WJ30 (validées une à une, écartées si malformées, jamais
  //   bloquantes — la soumission reste possible en sautant tout ceci).
  distributeur?: DistributeurId;
  roofAgeYears?: number;
  ombrage?: OmbrageId;
  futureLoads?: FutureLoadId[];
  batteryInterest?: boolean;
  occupantType?: OccupantTypeId;
  projectTiming?: ProjectTimingId;
  financingIntent?: FinancingIntentId;
  /** Le client a pris une photo compteur/facture EN LOCAL (jamais uploadée : pas
   *  d'endpoint d'upload aujourd'hui — cf. PLAN2 QK6 OCR). Signal booléen SEUL :
   *  aucune donnée binaire ne quitte le navigateur. */
  hasMeterPhoto?: boolean;
  // — WJ51 : préférence de contact explicite (facultative — mappée sur `canal` CRM).
  contactPreference?: ContactPreferenceId;
  // — WJ52 : référence courte générée CÔTÉ CLIENT (aucune garantie d'unicité
  //   globale — un simple artefact affiché au visiteur + échoé au webhook pour
  //   corréler une conversation WhatsApp ; jamais utilisée comme clé d'unicité
  //   serveur). Bornée en longueur/format pour rester un artefact honnête.
  clientRef?: string;
}

export type ValidationResult =
  | { ok: true; lead: ValidatedLead }
  | { ok: false; errors: Record<string, string> };

function cleanStr(v: unknown, max = 200): string {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
}

// ——— WJ30 : nettoyeurs des champs FACULTATIFS (rejettent le garbage, ne bloquent jamais) ———

/** Plafonds de bon sens anti-garbage (jamais affichés — validation serveur only). */
const MAX_BILL_MAD = 1_000_000;
const MAX_KWH = 10_000_000;

/** E-mail facultatif — garde-fou minimal (pas une RFC complète), borné à 254. */
function cleanOptionalEmail(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.trim().slice(0, 254);
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s) ? s : null;
}

/** Nombre fini > 0 borné, sinon null (factures/kWh : jamais négatif ni absurde). */
function cleanPositiveNumber(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 && n <= max ? n : null;
}

/** Valeur d'une liste fermée, sinon null (on ne devine pas). */
function cleanEnum<T extends string>(v: unknown, allowed: readonly T[]): T | null {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : null;
}

/** {lat,lng} fini DANS les bornes ≈ Maroc, ou null. */
function cleanRoofPoint(v: unknown): { lat: number; lng: number } | null {
  if (!v || typeof v !== 'object') return null;
  const o = v as { lat?: unknown; lng?: unknown };
  const lat = Number(o.lat);
  const lng = Number(o.lng);
  if (!isMoroccoLat(lat) || !isMoroccoLng(lng)) return null;
  return { lat, lng };
}

/** Entier fini borné [0, max] (âge de toit en années), sinon null. */
function cleanBoundedInt(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= max ? Math.round(n) : null;
}

/** Liste de puces d'une liste fermée : garde uniquement les valeurs connues,
 *  déduplique, borne à la taille du vocabulaire. Jamais bloquant : les entrées
 *  inconnues sont juste écartées silencieusement. Tableau vide ⇒ absent. */
function cleanEnumList<T extends string>(v: unknown, allowed: readonly T[]): T[] {
  if (!Array.isArray(v)) return [];
  const set = new Set<T>();
  for (const item of v) {
    if (typeof item === 'string' && (allowed as readonly string[]).includes(item)) set.add(item as T);
  }
  return Array.from(set).slice(0, allowed.length);
}

/** [[lat,lng],…] (≥ 3 paires finies dans les bornes ≈ Maroc), borné à 200 sommets, ou []. */
function cleanRoofOutline(v: unknown): Array<[number, number]> {
  if (!Array.isArray(v)) return [];
  const out: Array<[number, number]> = [];
  for (const p of v.slice(0, 200)) {
    if (!Array.isArray(p) || p.length < 2) continue;
    const lat = Number(p[0]);
    const lng = Number(p[1]);
    if (isMoroccoLat(lat) && isMoroccoLng(lng)) out.push([lat, lng]);
  }
  return out.length >= 3 ? out : [];
}

/**
 * WJ30 — champs FACULTATIFS élargis : chacun est validé individuellement et
 * ÉCARTÉ s'il est malformé. Ne produit JAMAIS d'erreur : un lead qui passait
 * hier passe toujours, avec ou sans ces champs.
 */
function validateOptionalFields(b: Record<string, unknown>): Partial<ValidatedLead> {
  const opt: Partial<ValidatedLead> = {};

  const email = cleanOptionalEmail(b.email);
  if (email) opt.email = email;

  const factureHiver = cleanPositiveNumber(b.factureHiver, MAX_BILL_MAD);
  if (factureHiver != null) opt.factureHiver = factureHiver;

  // Été ≠ hiver : une seule pièce d'info (le toggle) avec sa valeur d'été.
  // Été non différent ⇒ factureEte forcé à null (jamais une valeur résiduelle).
  if (typeof b.eteDifferente === 'boolean') {
    opt.eteDifferente = b.eteDifferente;
    opt.factureEte = b.eteDifferente ? cleanPositiveNumber(b.factureEte, MAX_BILL_MAD) : null;
  }

  const billKwh = cleanPositiveNumber(b.billKwh, MAX_KWH);
  if (billKwh != null) opt.billKwh = billKwh;

  const raccordement = cleanEnum(b.raccordement, RACCORDEMENTS);
  if (raccordement) opt.raccordement = raccordement;

  const adresse = cleanStr(b.adresse, 200);
  if (adresse) opt.adresse = adresse;

  const mode = cleanEnum(b.mode, LEAD_MODES);
  if (mode) opt.mode = mode;

  const langue = cleanEnum(b.langue_preferee ?? b.langue, LEAD_LANGS);
  if (langue) opt.langue_preferee = langue;

  const roofPoint = cleanRoofPoint(b.roofPoint);
  if (roofPoint) {
    opt.roofPoint = roofPoint;
    // Le repère validé PRIME sur les champs gps* bruts.
    opt.gpsLat = roofPoint.lat;
    opt.gpsLng = roofPoint.lng;
  } else {
    const gpsLat = Number(b.gpsLat);
    const gpsLng = Number(b.gpsLng);
    if (b.gpsLat != null && isMoroccoLat(gpsLat)) opt.gpsLat = gpsLat;
    if (b.gpsLng != null && isMoroccoLng(gpsLng)) opt.gpsLng = gpsLng;
  }

  const roofOutline = cleanRoofOutline(b.roofOutline);
  if (roofOutline.length >= 3) opt.roofOutline = roofOutline;

  // ——— WJ31 : questions de capture élargies (facultatives) ———
  const distributeur = cleanEnum(b.distributeur, DISTRIBUTEURS);
  if (distributeur) opt.distributeur = distributeur;

  const roofAgeYears = cleanBoundedInt(b.roofAgeYears, 100);
  if (roofAgeYears != null) opt.roofAgeYears = roofAgeYears;

  const ombrage = cleanEnum(b.ombrage, OMBRAGES);
  if (ombrage) opt.ombrage = ombrage;

  const futureLoads = cleanEnumList(b.futureLoads, FUTURE_LOADS);
  if (futureLoads.length > 0) opt.futureLoads = futureLoads;

  if (typeof b.batteryInterest === 'boolean') opt.batteryInterest = b.batteryInterest;

  const occupantType = cleanEnum(b.occupantType, OCCUPANT_TYPES);
  if (occupantType) opt.occupantType = occupantType;

  const projectTiming = cleanEnum(b.projectTiming, PROJECT_TIMINGS);
  if (projectTiming) opt.projectTiming = projectTiming;

  const financingIntent = cleanEnum(b.financingIntent, FINANCING_INTENTS);
  if (financingIntent) opt.financingIntent = financingIntent;

  if (typeof b.hasMeterPhoto === 'boolean') opt.hasMeterPhoto = b.hasMeterPhoto;

  // ——— WJ51 : préférence de contact explicite (facultative) ———
  const contactPreference = cleanEnum(b.contactPreference, CONTACT_PREFERENCES);
  if (contactPreference) opt.contactPreference = contactPreference;

  // ——— WJ52 : référence courte générée côté client (facultative, jamais bloquante) ———
  const clientRef = cleanStr(b.clientRef, 24);
  // Anti-garbage minimal : lettres/chiffres/tirets seulement (le format généré
  // par buildClientRef() plus bas) — une valeur malformée est simplement écartée.
  if (clientRef && /^[A-Z0-9-]{4,24}$/i.test(clientRef)) opt.clientRef = clientRef;

  return opt;
}

export function validateLead(body: unknown): ValidationResult {
  const b = (body ?? {}) as Record<string, unknown>;
  const errors: Record<string, string> = {};

  const fullName = cleanStr(b.fullName);
  if (fullName.length < 2) errors.fullName = 'Nom complet requis';

  const phone = normalizeMoroccanPhone(cleanStr(b.phone, 30));
  if (!phone.ok) errors.phone = phone.error ?? 'Numéro invalide';

  const city = cleanStr(b.city, 100);
  if (city.length < 2) errors.city = 'Ville / commune requise';

  const roofType = cleanStr(b.roofType, 20);
  if (!ROOF_TYPES.some((r) => r.id === roofType)) errors.roofType = 'Type de toiture requis';

  const billRange = cleanStr(b.billRange, 20);
  if (!isBillRangeId(billRange)) errors.billRange = 'Tranche de facture requise';

  if (b.consent !== true) errors.consent = 'Le consentement est requis pour être recontacté';

  if (Object.keys(errors).length > 0) return { ok: false, errors };

  const utm: Partial<Record<UtmKey, string>> = {};
  for (const k of UTM_KEYS) {
    const v = cleanStr(b[k], 300);
    if (v) utm[k] = v;
  }
  const fbclid = cleanStr(b.fbclid, 500) || null;

  return {
    ok: true,
    lead: {
      fullName,
      phoneE164: phone.e164!,
      whatsappOptIn: b.whatsappOptIn === true,
      city,
      roofType: roofType as RoofTypeId,
      billRange: billRange as BillRangeId,
      consent: true,
      fbclid,
      utm,
      // WJ30 — le webhook reçoit désormais TOUT ce que la capture a collecté
      // (facture exacte, GPS, contour, mode, raccordement, e-mail, langue…) :
      // champs facultatifs, validés un à un, écartés si malformés, jamais bloquants.
      ...validateOptionalFields(b),
    },
  };
}

/**
 * Bande kWc + ROI : proxy vers SIMULATOR_API_URL si configurée (timeout 5 s),
 * sinon estimation locale. Le navigateur n'appelle JAMAIS l'API directement.
 */
export async function runSimulation(
  lead: ValidatedLead,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<EstimateBand> {
  const fallback = localEstimateBand(lead.billRange);
  const url = env.SIMULATOR_API_URL?.trim();
  if (!url) return fallback;
  try {
    const res = await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ billRange: lead.billRange, roofType: lead.roofType, city: lead.city }),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return fallback;
    const data = (await res.json()) as Partial<EstimateBand>;
    if (typeof data.kwcLabel !== 'string' || typeof data.paybackLabel !== 'string') return fallback;
    return {
      kwcMin: typeof data.kwcMin === 'number' ? data.kwcMin : fallback.kwcMin,
      kwcMax: typeof data.kwcMax === 'number' ? data.kwcMax : fallback.kwcMax,
      kwcLabel: data.kwcLabel,
      paybackLabel: data.paybackLabel,
      source: 'simulator',
    };
  } catch {
    return fallback;
  }
}

export interface LeadRecord extends ValidatedLead {
  consentTimestamp: string; // ISO 8601 — horodatage serveur du consentement
  qualified: boolean; // false => ne doit jamais atteindre le CRM
  band: EstimateBand;
  page: string | null;
  submittedAt: string;
}

export function buildLeadRecord(
  lead: ValidatedLead,
  band: EstimateBand,
  now: Date,
  page: string | null = null,
): LeadRecord {
  const iso = now.toISOString();
  return {
    ...lead,
    consentTimestamp: iso,
    submittedAt: iso,
    qualified: qualifiesForCrm(lead.billRange),
    band,
    page,
  };
}

/**
 * WJ52 — référence client courte, générée CÔTÉ NAVIGATEUR juste avant l'envoi
 * (aucun appel serveur, aucune garantie d'unicité globale — c'est un artefact
 * pour combler le vide post-soumission, pas une clé d'unicité). Format
 * `TQ-XXXX` (4 caractères alphanumériques majuscules, alphabet sans 0/O/1/I
 * pour éviter toute confusion à l'oral/à l'écrit sur WhatsApp). Le préfixe
 * `TQ-` (Taqinor) + le format sont bornés par le regex de validation côté
 * `validateOptionalFields` ci-dessus (`^[A-Z0-9-]{4,24}$`).
 */
const CLIENT_REF_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export function buildClientRef(rand: () => number = Math.random): string {
  let code = '';
  for (let i = 0; i < 4; i++) {
    code += CLIENT_REF_ALPHABET[Math.floor(rand() * CLIENT_REF_ALPHABET.length)];
  }
  return `TQ-${code}`;
}

/**
 * Identifiant court, NON réversible, dérivé du téléphone E.164 — pour corréler
 * deux lignes de log d'un même lead SANS jamais journaliser le numéro. FNV-1a
 * 32 bits (suffisant pour une corrélation de logs, pas pour de la sécurité) ;
 * pur, synchrone, aucune dépendance, fonctionne hors Workers (tests).
 */
export function leadLogId(phoneE164: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < phoneE164.length; i++) {
    h ^= phoneE164.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

/**
 * Vue d'un lead SÛRE pour les logs (ERR32) : aucune PII (nom, téléphone, ville,
 * e-mail, consentement) ne doit atterrir dans les logs Cloudflare. On ne
 * journalise que des diagnostics non identifiants — un id corrélable haché, des
 * indicateurs/longueurs, et des champs de campagne déjà publics (UTM/fbclid
 * sont des paramètres d'URL, pas de la PII). Le payload PII complet n'est
 * JAMAIS sérialisé pour les logs.
 */
export function redactLeadForLog(record: LeadRecord): Record<string, unknown> {
  return {
    id: leadLogId(record.phoneE164),
    qualified: record.qualified,
    billRange: record.billRange,
    roofType: record.roofType,
    whatsappOptIn: record.whatsappOptIn,
    hasName: record.fullName.length > 0,
    hasCity: record.city.length > 0,
    bandSource: record.band.source,
    kwcLabel: record.band.kwcLabel,
    fbclid: record.fbclid ? 'present' : 'absent',
    utmKeys: Object.keys(record.utm).sort(),
    submittedAt: record.submittedAt,
    page: record.page,
    enrichment: 'enrichment' in record ? 'present' : 'absent',
  };
}

/**
 * Transfert CRM (LEAD_WEBHOOK_URL). Tolère l'absence de configuration et les
 * pannes : ne lève jamais, retourne l'état de livraison pour le log.
 */
export async function forwardLead(
  record: LeadRecord,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<{ delivered: boolean; reason?: string }> {
  if (!record.qualified) return { delivered: false, reason: 'below-threshold' };
  const url = env.LEAD_WEBHOOK_URL?.trim();
  if (!url) return { delivered: false, reason: 'no-webhook-configured' };
  try {
    // Secret statique attendu par le récepteur taqinor-os
    // (apps/crm/webhooks.py, en-tête X-Webhook-Secret). Sans secret
    // configuré, le récepteur refuse tout : les deux vont ensemble.
    //
    // ERR110 — RISQUE DE REJEU (documenté, PAS corrigé ici). Le protocole de
    // fil est un secret partagé STATIQUE (x-webhook-secret), sans signature
    // HMAC, ni horodatage signé, ni nonce. Un attaquant qui capture une requête
    // valide (TLS terminé chez un proxy, fuite de logs côté récepteur, etc.)
    // peut la REJOUER tant que le secret ne tourne pas. Durcir cela (HMAC sur
    // corps+timestamp, fenêtre anti-rejeu, nonce) EXIGE une modification
    // COORDONNÉE du récepteur (apps/crm/webhooks.py) : c'est un suivi côté
    // récepteur, HORS PÉRIMÈTRE de ce correctif côté site. On NE CHANGE PAS le
    // contrat de fil ici.
    //
    // Atténuation additive non cassante : on joint un en-tête x-webhook-timestamp
    // (ISO 8601) que le récepteur actuel IGNORE sans danger. Quand le récepteur
    // saura le vérifier (suivi coordonné), il pourra rejeter les requêtes trop
    // anciennes sans rien casser pour les clients existants.
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      'x-webhook-timestamp': new Date().toISOString(),
    };
    const secret = env.LEAD_WEBHOOK_SECRET?.trim();
    if (secret) headers['x-webhook-secret'] = secret;
    const res = await fetchFn(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(record),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { delivered: false, reason: `webhook-status-${res.status}` };
    return { delivered: true };
  } catch (e) {
    return { delivered: false, reason: `webhook-error-${e instanceof Error ? e.name : 'unknown'}` };
  }
}

/**
 * SHA-256 hex (minuscule) via Web Crypto — aucune dépendance, disponible dans
 * les Workers ET sous Node ≥ 18 (globalThis.crypto.subtle), donc testable.
 */
async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Hash SHA-256 du téléphone selon la spec Meta « Advanced Matching » : chiffres
 * uniquement, indicatif pays inclus, sans « + », espaces ni symboles. Notre
 * `phoneE164` est déjà au format +212XXXXXXXXX → on retire tout non-chiffre.
 */
export async function hashPhoneForCapi(phoneE164: string): Promise<string> {
  const digits = phoneE164.replace(/\D+/g, '');
  return sha256Hex(digits);
}

/**
 * Hash SHA-256 de la ville selon la spec Meta : minuscules, sans espace ni
 * ponctuation, trim (a–z et lettres accentuées conservées : Meta normalise
 * surtout la casse/les espaces ; on retire espaces et ponctuation latine).
 */
export async function hashCityForCapi(city: string): Promise<string> {
  const normalized = city
    .trim()
    .toLowerCase()
    .replace(/[\s\p{P}]+/gu, '');
  return sha256Hex(normalized);
}

/**
 * Meta Conversions API (CAPI_URL) — fire-and-forget. Le service vit dans
 * taqinor-os et peut ne pas être déployé : l'absence est tolérée en silence.
 * Uniquement pour les leads qualifiés (signal publicitaire propre).
 *
 * ERR111 — la PII de correspondance avancée (téléphone, ville) est HACHÉE en
 * SHA-256 AVANT de quitter apps/web. Le relais CAPI vit dans taqinor-os, n'est
 * pas inspectable depuis ce dépôt et « peut ne pas être déployé » : on ne peut
 * donc pas SUPPOSER qu'il hache. La spec Meta EXIGE des paramètres clients
 * hachés (SHA-256, normalisés) ; on hache donc à la source. Les champs sortent
 * sous `ph`/`ct` (noms de la spec Meta « user_data », déjà hachés) ; on n'envoie
 * PLUS jamais `phoneE164`/`city` en clair vers le relais.
 */
export async function fireCapi(
  record: LeadRecord,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<{ sent: boolean }> {
  if (!record.qualified) return { sent: false };
  const url = env.CAPI_URL?.trim();
  if (!url) return { sent: false };
  try {
    const [ph, ct] = await Promise.all([
      hashPhoneForCapi(record.phoneE164),
      hashCityForCapi(record.city),
    ]);
    await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        event: 'Lead',
        fbclid: record.fbclid,
        utm: record.utm,
        // PII hachée SHA-256 (jamais en clair) — noms `ph`/`ct` de la spec Meta.
        ph,
        ct,
        billRange: record.billRange,
        timestamp: record.submittedAt,
        page: record.page,
      }),
      signal: AbortSignal.timeout(5000),
    });
    return { sent: true };
  } catch {
    return { sent: false };
  }
}
