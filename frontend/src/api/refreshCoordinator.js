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

export function refreshSession(origin) {
  if (!inFlightRefresh) {
    inFlightRefresh = axios
      .post(`${origin}/api/django/auth/token/refresh/`, {}, { withCredentials: true })
      .finally(() => { inFlightRefresh = null })
  }
  return inFlightRefresh
}

export default refreshSession
