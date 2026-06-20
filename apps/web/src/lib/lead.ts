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
}

export type ValidationResult =
  | { ok: true; lead: ValidatedLead }
  | { ok: false; errors: Record<string, string> };

function cleanStr(v: unknown, max = 200): string {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
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
