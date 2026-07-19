import api from './axios'

/* ============================================================================
   WIR160 — Softphone VoIP (apps/voip) — client API. Préfixe `/voip/` (axios
   ajoute déjà `/api/django`). La société et l'utilisateur sont TOUJOURS posés
   côté serveur (jamais dans le corps). Le secret SIP est write-only côté
   backend : jamais renvoyé, on ne l'affiche donc jamais.
   ========================================================================== */

const voipApi = {
  // XPLT21 — configuration VoIP de la société (singleton get-or-default).
  getParametres: () => api.get('/voip/parametres/'),
  updateParametres: (data) => api.patch('/voip/parametres/', data),

  // XPLT21 — identifiants SIP de l'utilisateur courant (strictement les siens).
  getMesIdentifiants: () => api.get('/voip/mes-identifiants/'),
  updateMesIdentifiants: (data) => api.patch('/voip/mes-identifiants/', data),

  // Journal des appels (lecture seule, scopé société).
  getAppels: (params) => api.get('/voip/appels/', { params }),

  // Click-to-call : amorce un appel sortant (409 si softphone non configuré).
  appelSortant: (numero) => api.post('/voip/appels/sortant/', { numero }),

  // Clôture d'un appel en cours (issue optionnelle).
  terminerAppel: (id, data) => api.post(`/voip/appels/${id}/terminer/`, data),
}

export default voipApi
