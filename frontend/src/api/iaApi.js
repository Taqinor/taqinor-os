import axios from 'axios'

const VITE_URL = import.meta.env.VITE_IA_API_URL ?? 'http://localhost'
const ORIGIN = new URL(VITE_URL).origin

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
    const originalRequest = error.config
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
        // Refresh echoue
      }
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

const iaApi = {
  queryAgent: (question) =>
    iaApi_instance.post('/sql-agent/query', { question }),

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
