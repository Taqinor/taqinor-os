import axios from 'axios'

/* VX161 — refresh 401 UNIQUE partagé entre `axios.js` (client Django) et
   `iaApi.js` (client FastAPI/IA).
   ----------------------------------------------------------------------------
   Avant : chaque instance posait `_retry` PAR REQUÊTE — N requêtes 401
   simultanées (dans une seule instance OU réparties entre les deux) déclenchent
   N `POST /token/refresh/` en parallèle contre le MÊME `refresh_token`. En
   rotation à usage unique, un seul de ces POST réussit ; les autres invalident
   la session et déclenchent un `emitSessionExpired()` intempestif sur une
   session pourtant valide (ex. une page métier + le Copilote IA au même
   instant).

   Fix : une promesse de refresh UNIQUE, partagée process-wide. Le premier
   appelant (quelle que soit l'instance) déclenche le POST ; tout appel
   suivant, tant que ce POST n'est pas résolu, REÇOIT LA MÊME promesse au lieu
   d'en lancer un nouveau. Réinitialisée en `finally` : le PROCHAIN 401 (après
   résolution) relance un refresh frais. Fonction PURE (aucun React). */
let inFlightRefresh = null

// ERR-JPB-REFRESH-MUET-SESSION-EXPIREE — ce POST est en axios BRUT : il n'hérite
// pas du délai de l'instance, un serveur muet gelait toutes les requêtes en 401.
const DELAI_REFRESH_MS = 15000
const DELAI_REPRISE_MS = 2000

export const MESSAGE_PANNE_REFRESH = 'La connexion au serveur a échoué. Réessayez dans un instant.'

export function refreshSession(origin) {
  if (!inFlightRefresh) {
    inFlightRefresh = axios
      .post(`${origin}/api/django/auth/token/refresh/`, {}, { withCredentials: true, timeout: DELAI_REFRESH_MS })
      .finally(() => { inFlightRefresh = null })
  }
  return inFlightRefresh
}

/* ERR-JPB-REFRESH-MUET-SESSION-EXPIREE — un refresh sans réponse (coupure, délai)
   ou en 5xx (502 d'un déploiement), ou bridé (429), ne dit RIEN de la session :
   elle est peut-être encore valide. Seul un refus du serveur l'expire. */
export function estPanneDeRefresh(err) {
  const statut = err?.response?.status
  return statut == null || statut >= 500 || statut === 429
}

const pause = (ms) => new Promise((resolve) => { setTimeout(resolve, ms) })

/* Après une panne de refresh : UN réessai différé, puis la requête est rejouée.
   Panne persistante → signalée et rejetée, sans modale ; refus → la modale reste. */
export async function reprendreApresPanne(origin, {
  rejouer, expirer, signaler, rafraichir = refreshSession, attendre = pause,
}) {
  await attendre(DELAI_REPRISE_MS)
  try {
    await rafraichir(origin)
  } catch (err) {
    if (estPanneDeRefresh(err)) signaler(err)
    else expirer()
    throw err
  }
  return rejouer()
}

export default refreshSession
