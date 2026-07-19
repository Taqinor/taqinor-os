import api from './axios'

// Module Outillage (F1 / F2) — équipement durable, séparé du stock vendable.
const outillageApi = {
  // ── Outils (F1) ──
  getOutils: (params) => api.get('/outillage/outils/', { params }),
  getOutil: (id) => api.get(`/outillage/outils/${id}/`),
  createOutil: (data) => api.post('/outillage/outils/', data),
  updateOutil: (id, data) => api.patch(`/outillage/outils/${id}/`, data),
  deleteOutil: (id) => api.delete(`/outillage/outils/${id}/`),

  // ── FG80/WIR28 — calibration périodique ──
  // Corps optionnel {date_calibration: 'YYYY-MM-DD'} — défaut serveur = aujourd'hui.
  calibrer: (id, data) => api.post(`/outillage/outils/${id}/calibrer/`, data ?? {}),

  // ── Kits d'outillage (F2) ──
  getKits: () => api.get('/outillage/kits/'),
  saveKit: (id, data) => id
    ? api.patch(`/outillage/kits/${id}/`, data)
    : api.post('/outillage/kits/', data),
  deleteKit: (id) => api.delete(`/outillage/kits/${id}/`),

  // ── Outils d'un kit (F2) ──
  saveKitItem: (id, data) => id
    ? api.patch(`/outillage/kit-items/${id}/`, data)
    : api.post('/outillage/kit-items/', data),
  deleteKitItem: (id) => api.delete(`/outillage/kit-items/${id}/`),
}

export default outillageApi
