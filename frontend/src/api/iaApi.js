import axios from 'axios'

// Même origine que la page par défaut (chemins relatifs via nginx) —
// fonctionne depuis localhost ET depuis l'adresse privée Tailscale.
import { originFrom } from './origin'
// Ré-authentification gracieuse partagée avec le client principal (axios.js) :
// on émet l'événement « session expirée » plutôt que de recharger durement la
// page, ce qui préserve l'état des formulaires OCR/agent en cours.
import { emitSessionExpired } from '../providers/session-bridge'

const ORIGIN = originFrom(import.meta.env.VITE_IA_API_URL)

const iaApi_instance = axios.create({
  baseURL: ORIGIN,
  withCredentials: true, // envoie les cookies httpOnly automatiquement
})

// ── Requete : prefixe /api/fastapi uniquement ─────────────────
// Plus d'injection manuelle du token — le cookie est envoye automatiquement
iaApi_instance.interceptors.request.use((config) => {
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/fastapi' + config.url
  }
  return config
})

// ── Reponse : refresh silencieux sur 401 ──────────────────────
iaApi_instance.interceptors.response.use(
  (response) => response,
  async (error) => {
    // `error.config` est absent sur les erreurs de configuration/setup : on le
    // garde optionnel pour ne jamais lever depuis l'intercepteur lui-même.
    const originalRequest = error.config || {}
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        await axios.post(
          `${ORIGIN}/api/django/auth/token/refresh/`,
          {},
          { withCredentials: true }
        )
        return iaApi_instance(originalRequest)
      } catch {
        // Refresh echoue : la session est reellement expiree.
      }
      // Ré-authentification gracieuse EN PLACE (pas de rechargement dur) —
      // identique au client principal : le SessionProvider affiche un modal de
      // reconnexion et les formulaires OCR/agent ouverts sont préservés.
      emitSessionExpired()
    }
    return Promise.reject(error)
  }
)

const iaApi = {
  queryAgent: (question) =>
    iaApi_instance.post('/sql-agent/query', { question }),

  // AG3 — exécute une action SENSIBLE précédemment PROPOSÉE par l'agent, via le
  // jeton opaque (`confirm_token`) renvoyé dans la proposition. Miroir frontend
  // de POST /sql-agent/confirm (AG2). Le bouton « Confirmer » de la carte de
  // proposition l'appelle ; « Annuler » se contente d'écarter la carte.
  confirmAction: (token) =>
    iaApi_instance.post('/sql-agent/confirm', { token }),

  getSchema: () =>
    iaApi_instance.get('/sql-agent/schema'),

  getChatHistory: () =>
    iaApi_instance.get('/sql-agent/history'),

  clearChatHistory: () =>
    iaApi_instance.delete('/sql-agent/history'),

  processDocument: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return iaApi_instance.post('/ocr/process_document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  processStockDocument: ({ file, docType = '' }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) formData.append('doc_type', docType)
    return iaApi_instance.post('/ocr/process_stock_document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  saveOcrDocument: (data) =>
    iaApi_instance.post('/ocr/save_document', data),

  getOcrDocuments: (limit = 50, offset = 0) =>
    iaApi_instance.get(`/ocr/documents?limit=${limit}&offset=${offset}`),

  deleteOcrDocument: (id) =>
    iaApi_instance.delete(`/ocr/documents/${id}`),
}

export default iaApi
