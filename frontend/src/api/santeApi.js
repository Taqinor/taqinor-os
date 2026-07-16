import api from './axios'

/* ============================================================================
   Santé (apps/sante) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /sante/... ».
   Basenames DRF confirmés côté backend : praticiens / salles / patients /
   rendezvous. Le calendrier `rendezvous` accepte les filtres
   ?praticien=&salle=&date_debut=&date_fin= (NTSAN4).
   ========================================================================== */

const santeApi = {
  // ── Praticiens ──
  praticiens: {
    list: (params) => api.get('/sante/praticiens/', { params }),
  },

  // ── Salles ──
  salles: {
    list: (params) => api.get('/sante/salles/', { params }),
  },

  // ── Patients ──
  patients: {
    list: (params) => api.get('/sante/patients/', { params }),
    get: (id) => api.get(`/sante/patients/${id}/`),
    create: (data) => api.post('/sante/patients/', data),
    update: (id, data) => api.patch(`/sante/patients/${id}/`, data),
  },

  // ── Rendez-vous (agenda) ──
  rendezvous: {
    list: (params) => api.get('/sante/rendezvous/', { params }),
    create: (data) => api.post('/sante/rendezvous/', data),
    update: (id, data) => api.patch(`/sante/rendezvous/${id}/`, data),
    remove: (id) => api.delete(`/sante/rendezvous/${id}/`),
  },
}

export default santeApi
