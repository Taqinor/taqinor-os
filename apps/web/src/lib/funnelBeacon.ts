/**
 * WJ59 — Step-level funnel analytics (same-origin, no new dependency).
 *
 * A tiny privacy-light beacon: which step of the /devis/mon-toit assistant was
 * REACHED or ABANDONED. Research on this class of funnel (progress-bar-style
 * multi-step forms) shows that visible progress indicators shift WHERE
 * visitors abandon rather than reducing abandonment itself — without
 * step-level data the next optimization round is guessing at the real leak.
 *
 * HARD PRIVACY CONTRACT (never relaxed): a beacon event carries ONLY a step
 * id/label, an action (reached/abandoned), an anonymous session token (random,
 * per-tab, never a device/user id), and the page path. It NEVER carries name,
 * phone, email, address, city, GPS, roof outline, or any other field accepted
 * by `lib/lead.ts`. `validateBeaconEvent` enforces this by an ALLOWLIST of
 * known-safe keys — an unknown key is dropped, never passed through.
 *
 * TRANSPORT — deliberately NOT the CRM lead webhook (`LEAD_WEBHOOK_URL`): that
 * receiver (`backend/django_core/apps/crm/webhooks.py`) unconditionally
 * creates a CRM `Lead` row for every payload it accepts (defaulting the name
 * to "Lead site web" when absent) — reusing it here would flood the CRM with a
 * fake lead per funnel step, which defeats the entire point of a lightweight
 * measurement signal. Until a dedicated, non-lead-shaped receiver exists
 * (`FUNNEL_WEBHOOK_URL`, a founder-provisioned endpoint — absent by default),
 * this module only produces a REDACTED, aggregate-friendly log line
 * (`redactBeaconForLog`) exactly like the existing lead pipeline does for
 * undelivered leads (`redactLeadForLog` in `lib/lead.ts`). Wiring a real
 * dashboard/webhook later is additive: the shape below already tolerates it.
 */

// WJ104 — `proposal` ajouté aux étapes suivies : le cycle de vie de
// /proposition/[token] (vue, signature) est un DELTA sur ce même beacon
// step-level plutôt qu'un canal séparé — voir `src/lib/telemetryEvents.ts`
// pour le vocabulaire d'événement de plus haut niveau qui s'appuie dessus
// (estimate_viewed/callback_requested/proposal_viewed/proposal_signed).
export const FUNNEL_STEP_IDS = ['toit', 'facture', 'estimation', 'contact', 'proposal'] as const;
export type FunnelStepId = (typeof FUNNEL_STEP_IDS)[number];

// WJ104 — 3 actions ADDITIVES sur le même vocabulaire fermé step+action
// (jamais un canal ni un endpoint séparé) : `viewed` (l'étape a réellement
// affiché son contenu utile — l'estimation rendue, ou la proposition ouverte),
// `callback_requested` (demande de rappel explicite, DISTINCTE d'un opt-in
// WhatsApp), `signed` (signature électronique de la proposition). `reached`/
// `abandoned` (WJ59) restent inchangés pour tout call-site existant.
export const FUNNEL_ACTIONS = ['reached', 'abandoned', 'viewed', 'callback_requested', 'signed'] as const;
export type FunnelAction = (typeof FUNNEL_ACTIONS)[number];

export interface FunnelBeaconEvent {
  step: FunnelStepId;
  action: FunnelAction;
  /** Jeton anonyme généré côté navigateur (aléatoire, par onglet) — jamais un
   *  identifiant d'appareil/utilisateur, jamais dérivé d'une donnée de contact. */
  sessionToken: string;
  /** Chemin de la page (ex. "/devis/mon-toit"), jamais l'URL complète (pas de
   *  query string — un futur fbclid/UTM ne doit jamais transiter ici). */
  path: string;
}

export interface FunnelEnv {
  /** Webhook DÉDIÉ, distinct du webhook de lead CRM (cf. note ci-dessus).
   *  Absent par défaut : le beacon reste alors log-only, jamais bloquant. */
  FUNNEL_WEBHOOK_URL?: string;
  FUNNEL_WEBHOOK_SECRET?: string;
}

function cleanStr(v: unknown, max = 64): string {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
}

function isEnum<T extends string>(v: unknown, allowed: readonly T[]): v is T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v);
}

/** Chemin sûr : commence par "/", jamais de query string ni de fragment
 *  (une valeur qui en contient est tronquée à la partie avant "?"/"#" — on
 *  n'écarte pas tout l'événement pour ça, un chemin "sale" n'est pas un
 *  problème de vie privée en soi, seulement les paramètres qu'il pourrait
 *  porter). */
function cleanPath(v: unknown): string {
  const raw = cleanStr(v, 200);
  if (!raw.startsWith('/')) return '/devis/mon-toit';
  return raw.split('?')[0].split('#')[0] || '/devis/mon-toit';
}

/** Jeton de session : alphanumérique borné — anti-garbage minimal, jamais une
 *  validation de format stricte (ce n'est qu'une clé de dédup best-effort). */
function cleanSessionToken(v: unknown): string {
  const raw = cleanStr(v, 40);
  return /^[A-Za-z0-9_-]{4,40}$/.test(raw) ? raw : '';
}

export type BeaconValidationResult =
  | { ok: true; event: FunnelBeaconEvent }
  | { ok: false; error: string };

/**
 * ALLOWLIST stricte : seules ces 4 clés existent dans un événement validé.
 * Toute autre clé du corps reçu (y compris fullName/phone/email/city/gpsLat…)
 * est silencieusement IGNORÉE — jamais lue, jamais transmise plus loin.
 */
export function validateBeaconEvent(body: unknown): BeaconValidationResult {
  const b = (body ?? {}) as Record<string, unknown>;

  if (!isEnum(b.step, FUNNEL_STEP_IDS)) return { ok: false, error: 'step invalide' };
  if (!isEnum(b.action, FUNNEL_ACTIONS)) return { ok: false, error: 'action invalide' };

  const sessionToken = cleanSessionToken(b.sessionToken);
  if (!sessionToken) return { ok: false, error: 'sessionToken invalide' };

  const path = cleanPath(b.path);

  return {
    ok: true,
    event: { step: b.step, action: b.action, sessionToken, path },
  };
}

/** Vue SÛRE pour les logs — jamais de PII possible ici puisque l'événement
 *  validé ne porte déjà que 4 champs non identifiants. */
export function redactBeaconForLog(event: FunnelBeaconEvent): Record<string, unknown> {
  return {
    step: event.step,
    action: event.action,
    path: event.path,
    // Le jeton lui-même n'identifie personne (aléatoire, par onglet) — on le
    // garde tel quel pour permettre une dédup/agrégation basique côté logs.
    sessionToken: event.sessionToken,
  };
}

/**
 * Transfert best-effort vers un webhook DÉDIÉ (jamais le webhook de lead CRM —
 * cf. note en tête de fichier). Absence de configuration ou panne réseau :
 * jamais levé, jamais bloquant pour l'appelant.
 */
export async function forwardBeacon(
  event: FunnelBeaconEvent,
  env: FunnelEnv,
  fetchFn: typeof fetch = fetch,
): Promise<{ delivered: boolean; reason?: string }> {
  const url = env.FUNNEL_WEBHOOK_URL?.trim();
  if (!url) return { delivered: false, reason: 'no-webhook-configured' };
  try {
    const headers: Record<string, string> = { 'content-type': 'application/json' };
    const secret = env.FUNNEL_WEBHOOK_SECRET?.trim();
    if (secret) headers['x-webhook-secret'] = secret;
    const res = await fetchFn(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(event),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return { delivered: false, reason: `webhook-status-${res.status}` };
    return { delivered: true };
  } catch (e) {
    return { delivered: false, reason: `webhook-error-${e instanceof Error ? e.name : 'unknown'}` };
  }
}
