/**
 * Réponse JSON `no-store` commune des endpoints `src/pages/api/*` (ENF19 : une seule copie).
 * Sans import `cloudflare:workers` : utilisable par les routes qui doivent rester découplées
 * du socle `_proxy` (ex. roof-*).
 */
export function jsonResponse(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  const entetes = { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers };
  return new Response(JSON.stringify(data), { status, headers: entetes });
}
