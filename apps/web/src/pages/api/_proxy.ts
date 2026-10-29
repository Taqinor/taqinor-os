/**
 * Socle partagé des proxys SAME-ORIGIN de `src/pages/api/*` (ACAL345 : une seule copie).
 *
 * - `jsonResponse` : réponse JSON `no-store` ;
 * - `resolveApiBase` : PUBLIC_API_BASE runtime (cf.env) OU build, sinon https://api.taqinor.ma ;
 * - `relayJson` : un appel amont dont on garde le statut et le JSON (null si illisible) ;
 *   `null` quand le backend est injoignable (l'appelant répond alors 502).
 *
 * Jamais LEAD_WEBHOOK_URL ici (secret réservé à la capture, cf. WJ109).
 */
import { resolveApiBase } from './_apiBase';
import { jsonResponse } from '../../lib/apiJson';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

// Une seule copie (lib/apiJson.ts, ./_apiBase.ts — ENF19) ; ré-exportées pour les importeurs historiques de ce socle.
export { jsonResponse, resolveApiBase };

export interface RelayResult {
  status: number;
  payload: unknown;
}

/** Appel amont ; `null` si le backend est injoignable, `payload` null si le corps n'est pas du JSON. */
export async function relayJson(url: string, init: RequestInit): Promise<RelayResult | null> {
  let reponse: Response;
  try {
    reponse = await fetch(url, init);
  } catch {
    return null;
  }
  const payload: unknown = await reponse.json().catch(() => null);
  return { status: reponse.status, payload };
}

/** En-têtes de réponse amont conservés par `relayBinaire` (ASEC53) — jamais `set-cookie`. */
const ENTETES_BINAIRE = ['content-type', 'content-disposition', 'content-length', 'x-content-type-options', 'x-robots-tag'];

/**
 * ASEC53 (D-ASEC-53-RELAIS) — relais d'un flux BINAIRE (PDF, image) : statut et corps amont
 * transmis tels quels (flux, jamais relu ni réencodé), `content-type` / `content-disposition`
 * conservés. Cache toujours PRIVÉ (la réponse dépend de la preuve du navigateur) : la valeur
 * amont si elle est déjà `private`/`no-store`, sinon `private, no-store`. `null` si injoignable.
 */
export async function relayBinaire(url: string, init: RequestInit): Promise<Response | null> {
  let reponse: Response;
  try {
    reponse = await fetch(url, init);
  } catch {
    return null;
  }
  const entetes = new Headers();
  for (const nom of ENTETES_BINAIRE) {
    const valeur = reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  const cache = reponse.headers.get('cache-control') ?? '';
  entetes.set('cache-control', /\b(private|no-store)\b/.test(cache) ? cache : 'private, no-store');
  return new Response(reponse.body, { status: reponse.status, headers: entetes });
}

/**
 * Garde commune des proxys `proposition-*` : limite de débit par IP, corps JSON, jeton de
 * proposition. Renvoie la réponse d'erreur à retourner telle quelle, sinon `{ body, token }`.
 */
export async function corpsAvecToken(
  request: Request,
  cle: string,
  limit: number,
): Promise<Response | { body: Record<string, unknown>; token: string }> {
  const rl = rateLimit(`${cle}:${clientIpFromRequest(request)}`, { limit, windowMs: 60_000 });
  if (!rl.allowed) {
    return jsonResponse({ ok: false, status: 429, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return jsonResponse({ ok: false, status: 400, detail: 'Requête invalide.' }, 400);
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) return jsonResponse({ ok: false, status: 400, detail: 'Lien de proposition manquant.' }, 400);
  return { body, token };
}
