/**
 * Émetteur du rapport d'erreurs (YBW20) : `window.onerror` et
 * `unhandledrejection` envoient `{ type, message, fichier, ligne, colonne,
 * page }` à `/api/client-error` — chemin de page SANS requête ni fragment,
 * aucun identifiant, aucun cookie, au plus 5 rapports par chargement.
 * Inclus par la mise en page commune (YBW60) ; par la sonde en attendant.
 */
const MAX_RAPPORTS = 5;
let envoyes = 0;

function envoyer(rapport: Record<string, unknown>): void {
  if (envoyes >= MAX_RAPPORTS) return;
  envoyes += 1;
  try {
    void fetch('/api/client-error', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...rapport, page: location.pathname }),
      keepalive: true,
      credentials: 'omit',
    }).catch(() => undefined);
  } catch {
    /* le rapport ne doit jamais créer une nouvelle erreur */
  }
}

window.addEventListener('error', (e) => {
  let fichier = '';
  try {
    fichier = e.filename ? new URL(e.filename).pathname : '';
  } catch {
    fichier = '';
  }
  envoyer({ type: 'error', message: String(e.message ?? ''), fichier, ligne: e.lineno || null, colonne: e.colno || null });
});

window.addEventListener('unhandledrejection', (e) => {
  const raison = e.reason instanceof Error ? e.reason.message : String(e.reason ?? '');
  envoyer({ type: 'rejection', message: raison });
});
