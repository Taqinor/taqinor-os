import axios from 'axios'

// Par défaut : MÊME ORIGINE que la page (chemins relatifs via nginx) — l'app
// fonctionne ainsi depuis localhost ET depuis une adresse privée Tailscale
// sans rebuild. VITE_API_URL ne sert qu'à pointer ailleurs explicitement.
import { originFrom } from './origin'
// L53 (toast d'erreur global) + L57 (session expirée). Ces modules sont
// volontairement sans React : ils émettent un toast / un événement window.
import { errorMessageFrom, toastError } from '../lib/toast'
import { emitSessionExpired } from '../providers/session-bridge'
// VX161 — refresh 401 partagé avec iaApi.js (une seule promesse en vol,
// jamais un POST /token/refresh/ par requête en échec).
import { refreshSession } from './refreshCoordinator'

const ORIGIN = originFrom(import.meta.env.VITE_API_URL)

// VX55 — aucun timeout n'existait sur l'instance axios : sur une 3G qui cale,
// un écran gelait indéfiniment (aucune requête n'échouait jamais). 20 s laisse
// de la marge aux endpoints lents (export, PDF) tout en bornant l'attente.
const REQUEST_TIMEOUT_MS = 20000

const api = axios.create({
  baseURL: ORIGIN,
  withCredentials: true, // envoie les cookies httpOnly automatiquement
  timeout: REQUEST_TIMEOUT_MS,
})

// ── Requete : prefixe /api/django uniquement ──────────────────
// Plus d'injection manuelle du token — le cookie est envoye automatiquement
api.interceptors.request.use((config) => {
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/django' + config.url
  }
  return config
})

// ── Reponse : refresh silencieux sur 401 ──────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config || {}
    const isAuthEndpoint = originalRequest.url?.includes('/token/')
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isAuthEndpoint
    ) {
      originalRequest._retry = true
      try {
        // Le cookie refresh_token est envoye automatiquement par le navigateur.
        // VX161 — promesse de refresh PARTAGÉE (avec iaApi.js) : N 401
        // simultanés n'émettent qu'UN SEUL POST refresh.
        await refreshSession(ORIGIN)
        // Rejoue la requete originale — le nouveau cookie access_token est pris
        return api(originalRequest)
      } catch {
        // Refresh echoue : la session est reellement expiree.
      }
      // L57 — Ré-authentification gracieuse EN PLACE (pas de rechargement dur,
      // l'état des formulaires ouverts est préservé). Le SessionProvider écoute
      // cet événement et affiche un modal de reconnexion. La redirection vers
      // /login reste un repli ultime si personne n'écoute (ex. avant montage).
      emitSessionExpired()
      return Promise.reject(error)
    }

    // L53 — Bridge global : toute requête échouée surface un toast d'erreur FR,
    // sauf si l'appelant a explicitement opté pour la gestion locale
    // (`config.suppressErrorToast = true`) ou s'il s'agit d'une annulation.
    if (!originalRequest.suppressErrorToast && !axios.isCancel?.(error)) {
      // VX55 — un timeout (ECONNABORTED, `timeout: 20000` ci-dessus) est
      // distinct d'une annulation volontaire (AbortController, cf. thunks
      // {signal}) : celle-ci ne doit PAS toaster (l'écran a changé/démonté),
      // celui-là DOIT — l'utilisateur doit savoir que le réseau a calé.
      if (error.code === 'ECONNABORTED') {
        toastError('La connexion a expiré. Vérifiez votre connexion et réessayez.')
        return Promise.reject(error)
      }
      const status = error.response?.status
      // On NE toaste PAS les 401 (gérés ci-dessus) ni les 404 (souvent attendus,
      // ex. recherche/feature parquée) — ils restent gérés localement.
      if (status !== 401 && status !== 404) {
        toastError(errorMessageFrom(error))
      }
    }
    return Promise.reject(error)
  }
)

export default api
