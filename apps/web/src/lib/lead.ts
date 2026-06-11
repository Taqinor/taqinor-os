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
    const res = await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
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
 * Meta Conversions API (CAPI_URL) — fire-and-forget. Le service vit dans
 * taqinor-os et peut ne pas être déployé : l'absence est tolérée en silence.
 * Uniquement pour les leads qualifiés (signal publicitaire propre).
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
    await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        event: 'Lead',
        fbclid: record.fbclid,
        utm: record.utm,
        phoneE164: record.phoneE164,
        city: record.city,
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
