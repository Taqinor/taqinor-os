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

// VX162 — canal de diffusion CROSS-ONGLETS pour le logout. Avant : seul
// l'onglet où l'utilisateur clique « Déconnexion » se déconnecte ; sur un
// poste partagé (accueil/atelier), un onglet B continue de MUTER des données
// au nom d'un utilisateur délibérément déconnecté jusqu'à son PREMIER 401
// tardif. Fix : `logoutUser.fulfilled` publie sur ce canal, chaque onglet
// s'abonne (SessionProvider) et se déconnecte localement SANS attendre un
// échec réseau. Feature-detect : `BroadcastChannel` absent (vieux Safari) →
// no-op silencieux, comportement inchangé (repli sur le 401).
const SESSION_CHANNEL_NAME = 'taqinor-session'
const hasBroadcastChannel = typeof BroadcastChannel !== 'undefined'
const sessionChannel = hasBroadcastChannel ? new BroadcastChannel(SESSION_CHANNEL_NAME) : null

/** Publie un logout vers tous les AUTRES onglets (appelé par `logoutUser`
 *  une fois le logout local dispatché). */
export function broadcastLogout() {
  sessionChannel?.postMessage({ type: 'logout' })
}

/** S'abonne aux logouts publiés par d'autres onglets. Retourne une fonction
 *  de désabonnement (compatible cleanup d'effet React). No-op si
 *  `BroadcastChannel` est indisponible. */
export function subscribeToSessionLogout(onLogout) {
  if (!sessionChannel) return () => {}
  const handler = (event) => {
    if (event?.data?.type === 'logout') onLogout()
  }
  sessionChannel.addEventListener('message', handler)
  return () => sessionChannel.removeEventListener('message', handler)
}
