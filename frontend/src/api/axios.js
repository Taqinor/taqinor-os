import axios from 'axios'

const VITE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost'

// Extrait l'origine (protocol + host + port) quelle que soit la valeur de VITE_API_URL
// Ex: 'http://localhost/api/django' → 'http://localhost'
const ORIGIN = new URL(VITE_URL).origin

const api = axios.create({
  baseURL: ORIGIN,
})

// ── Requête : inject token + préfixe /api/django ──────────────
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // Toutes les routes Django arrivent sous la forme /something/ → on préfixe
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/django' + config.url
  }
  return config
})

// ── Réponse : refresh silencieux sur 401 ──────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    // Never intercept auth endpoints — let Login.jsx handle its own 401
    const isAuthEndpoint = originalRequest.url?.includes('/token/')
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true
      const refreshToken = sessionStorage.getItem('refresh')
      if (refreshToken) {
        try {
          const { data } = await axios.post(
            `${ORIGIN}/api/django/token/refresh/`,
            { refresh: refreshToken }
          )
          sessionStorage.setItem('token', data.access)
          originalRequest.headers.Authorization = `Bearer ${data.access}`
          return api(originalRequest)
        } catch {
          // Refresh failed — clear tokens and redirect to login
        }
      }
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('refresh')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
