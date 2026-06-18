// L57 — Pont entre la couche axios et le SessionProvider React. La couche API
// ne connaît pas React ; quand une session expire (401 non rejouable), elle
// émet un événement window que le SessionProvider écoute pour afficher une
// ré-authentification EN PLACE (sans rechargement → l'état du formulaire en
// cours est préservé).
export const SESSION_EXPIRED_EVENT = 'taqinor:session-expired'

/** Signale une session expirée (appelé par l'intercepteur axios). Idempotent
 *  côté écouteur : le provider ne montre qu'un seul modal. */
export function emitSessionExpired() {
  if (typeof window === 'undefined') return
  // Ne jamais demander une ré-auth sur l'écran de login lui-même.
  if (window.location?.pathname === '/login') return
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT))
}
