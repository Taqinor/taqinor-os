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
import * as cf from 'cloudflare:workers';

const API_BASE_PAR_DEFAUT = 'https://api.taqinor.ma';

export function jsonResponse(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  const entetes = { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers };
  return new Response(JSON.stringify(data), { status, headers: entetes });
}

export function resolveApiBase(): string {
  const runtimeEnv = (cf.env ?? {}) as { PUBLIC_API_BASE?: string };
  const depuisRuntime = runtimeEnv.PUBLIC_API_BASE?.trim();
  const depuisBuild = (import.meta.env.PUBLIC_API_BASE as string | undefined)?.trim();
  return depuisRuntime || depuisBuild || API_BASE_PAR_DEFAUT;
}

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
