import axios from 'axios'

// Par défaut : MÊME ORIGINE que la page (chemins relatifs via nginx) — l'app
// fonctionne ainsi depuis localhost ET depuis une adresse privée Tailscale
// sans rebuild. VITE_API_URL ne sert qu'à pointer ailleurs explicitement.
const VITE_URL = import.meta.env.VITE_API_URL || ''
const ORIGIN = VITE_URL ? new URL(VITE_URL).origin : ''

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
    const originalRequest = error.config
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
        // Refresh echoue — redirection vers login
      }
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
