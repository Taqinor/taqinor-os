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
  // `q` (NTSAN18 — écran Réception) cherche par nom/prénom/CIN/téléphone.
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
    // NTSAN18 — bouton « Patient arrivé » de l'écran Réception : bascule le
    // statut en salle d'attente (le serveur reste source de vérité).
    checkin: (id) => api.patch(`/sante/rendezvous/${id}/`, { statut: 'arrive' }),
  },

  // ── Nomenclature des actes (NTSAN7 — paramétrage clinique) ──
  // `actif` est en lecture seule côté API : le soft-disable passe par les
  // actions dédiées (jamais un DELETE physique une fois l'acte utilisé).
  actesMedicaux: {
    list: (params) => api.get('/sante/actes-medicaux/', { params }),
    create: (data) => api.post('/sante/actes-medicaux/', data),
    update: (id, data) => api.patch(`/sante/actes-medicaux/${id}/`, data),
    desactiver: (id) => api.post(`/sante/actes-medicaux/${id}/desactiver/`),
    activer: (id) => api.post(`/sante/actes-medicaux/${id}/activer/`),
  },
}

export default santeApi
