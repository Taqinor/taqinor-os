/**
 * W317 — garde-fou Origin/Sec-Fetch-Site des POST same-origin (ENF19 : une seule copie, partagée
 * par `lib/lead.ts` — qui la ré-exporte — et par les routes `roof-*`, qui restent ainsi découplées
 * de toute plomberie de lead/CRM).
 *
 * `Sec-Fetch-Site` (posé par le navigateur, non forgeable depuis JS) fait foi ; à défaut (client
 * hors-navigateur), on retombe sur `Origin` comparé à `request.url` — un mismatch EXPLICITE est
 * rejeté, mais l'absence totale des deux en-têtes (navigation directe sans fetch, tests, outils
 * serveur-à-serveur légitimes) n'est PAS bloquée : ce garde-fou cible le cross-site FORGÉ, pas les
 * clients qui n'envoient simplement pas ces en-têtes.
 */
export function isSameOriginRequest(request: Request): boolean {
  const secFetchSite = request.headers.get('sec-fetch-site');
  if (secFetchSite) return secFetchSite !== 'cross-site';

  const origin = request.headers.get('origin');
  if (!origin) return true; // aucun signal exploitable → laissé passer (voir note ci-dessus)
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false; // Origin illisible : on ne peut pas prouver l'égalité → rejeté
  }
}
