import api from './axios'

/* ============================================================================
   NTOBS33 — client API du panneau admin interne « Historique brut » des
   changements de statut de composant (avant publication d'incident).
   Directeur/Administrateur uniquement côté serveur (`IsDirecteurOrAdmin`).
   ========================================================================== */
const statuspageApi = {
  // GET .../historique-statut/ — les 30 derniers changements RÉELLEMENT
  // détectés (tous composants confondus), jamais un par tick de 5 min.
  getHistoriqueStatut: () => api.get('/statuspage/historique-statut/'),
  // GET .../historique-statut/{id}/prefill-incident/ — pré-remplit (sans RIEN
  // créer) les champs d'un futur IncidentPublic à partir de cet événement.
  prefillIncident: (logId) =>
    api.get(`/statuspage/historique-statut/${logId}/prefill-incident/`),
}

export default statuspageApi
