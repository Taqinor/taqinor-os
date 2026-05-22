import axios from 'axios'

const VITE_URL = import.meta.env.VITE_IA_API_URL ?? 'http://localhost'
const ORIGIN = new URL(VITE_URL).origin

const iaApi_instance = axios.create({
  baseURL: ORIGIN,
})

// ── Requête : inject token + préfixe /api/fastapi ─────────────
iaApi_instance.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/fastapi' + config.url
  }
  return config
})

const iaApi = {
  queryAgent: (question) =>
    iaApi_instance.post('/sql-agent/query', { question }),

  getSchema: () =>
    iaApi_instance.get('/sql-agent/schema'),

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
