import axios from 'axios'

// Par défaut : MÊME ORIGINE que la page (chemins relatifs via nginx) — l'app
// fonctionne ainsi depuis localhost ET depuis une adresse privée Tailscale
// sans rebuild. VITE_API_URL ne sert qu'à pointer ailleurs explicitement.
import { originFrom } from './origin'
// L53 (toast d'erreur global) + L57 (session expirée). Ces modules sont
// volontairement sans React : ils émettent un toast / un événement window.
import { errorMessageFrom, toastError } from '../lib/toast'
import { emitSessionExpired } from '../providers/session-bridge'

const ORIGIN = originFrom(import.meta.env.VITE_API_URL)

const api = axios.create({
  baseURL: ORIGIN,
  withCredentials: true, // envoie les cookies httpOnly automatiquement
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
        // Le cookie refresh_token est envoye automatiquement par le navigateur
        await axios.post(
          `${ORIGIN}/api/django/auth/token/refresh/`,
          {},
          { withCredentials: true }
        )
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
